"""
Anghami Extractor - Extracts playlists and liked songs from Anghami.

Uses Selenium to automate the Anghami web player and scrape song data.
Falls back to reading from a JSON file exported via the browser console script.
"""

import json
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


ANGHAMI_BASE = "https://play.anghami.com"


def create_driver():
    """Create a Chrome WebDriver instance using the user's real Chrome profile."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Use the user's real Chrome profile so Anghami sees a normal browser
    # This also preserves existing login sessions
    import os
    chrome_profile = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    if os.path.isdir(chrome_profile):
        options.add_argument(f"--user-data-dir={chrome_profile}")
        options.add_argument("--profile-directory=Default")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Remove webdriver flag to avoid detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver


def wait_for_login(driver, timeout=300):
    """
    Navigate to Anghami and wait for the user to log in manually.
    Returns True once the user appears to be logged in.
    """
    driver.get(ANGHAMI_BASE)
    print("\n" + "=" * 60)
    print("  ANGHAMI LOGIN")
    print("=" * 60)
    print("A Chrome window has opened with Anghami.")
    print("Please log in to your Anghami account.")
    print("Once you're logged in and see your library, press ENTER here.")
    print("=" * 60)
    input("\n>>> Press ENTER after you've logged in... ")
    return True


def scroll_to_load_all(driver, container_css=None, pause=1.5, max_scrolls=100):
    """Scroll down repeatedly to load all lazy-loaded content."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        if container_css:
            driver.execute_script(
                f"document.querySelector('{container_css}').scrollTop = "
                f"document.querySelector('{container_css}').scrollHeight"
            )
        else:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_songs_from_page(driver):
    """
    Extract song data from the currently loaded page.
    Looks for common Anghami DOM patterns for song rows.
    """
    songs = []

    # Try multiple CSS selectors that Anghami's web player may use
    selectors = [
        # Song row containers (common patterns)
        "section.song-row",
        "div.song-row",
        "div.track-row",
        "div[class*='song']",
        "div[class*='track']",
        "tr[class*='song']",
        "tr[class*='track']",
        "div[class*='SongItem']",
        "div[class*='TrackItem']",
    ]

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if not elements:
                continue

            for el in elements:
                try:
                    # Try to extract title and artist from the element
                    title = None
                    artist = None

                    # Look for title in various sub-elements
                    for title_sel in [
                        "[class*='title']",
                        "[class*='name']",
                        "[class*='song-name']",
                        "a[class*='title']",
                        "span[class*='title']",
                        ".cell-title span",
                        ".cell-title a",
                    ]:
                        try:
                            title_el = el.find_element(By.CSS_SELECTOR, title_sel)
                            if title_el.text.strip():
                                title = title_el.text.strip()
                                break
                        except Exception:
                            continue

                    # Look for artist
                    for artist_sel in [
                        "[class*='artist']",
                        "[class*='subtitle']",
                        ".cell-artist span",
                        ".cell-artist a",
                        "span[class*='artist']",
                        "a[class*='artist']",
                    ]:
                        try:
                            artist_el = el.find_element(By.CSS_SELECTOR, artist_sel)
                            if artist_el.text.strip():
                                artist = artist_el.text.strip()
                                break
                        except Exception:
                            continue

                    if title:
                        songs.append({
                            "title": title,
                            "artist": artist or "Unknown Artist",
                        })
                except Exception:
                    continue

            if songs:
                break  # Found songs with this selector, stop trying others
        except Exception:
            continue

    # Fallback: use JavaScript to extract from the page's data layer
    if not songs:
        try:
            js_songs = driver.execute_script("""
                // Try to find song elements by text content patterns
                let results = [];
                let allLinks = document.querySelectorAll('a');
                let processed = new Set();

                // Look for links that point to /song/ paths
                for (let a of allLinks) {
                    let href = a.getAttribute('href') || '';
                    if (href.includes('/song/') && !processed.has(href)) {
                        processed.add(href);
                        let title = a.textContent.trim();
                        if (title && title.length > 0 && title.length < 200) {
                            // Try to find the artist nearby
                            let parent = a.closest('[class*="song"], [class*="track"], [class*="row"], tr, li');
                            let artist = 'Unknown Artist';
                            if (parent) {
                                let artistEls = parent.querySelectorAll('[class*="artist"], [class*="subtitle"]');
                                for (let ae of artistEls) {
                                    if (ae.textContent.trim()) {
                                        artist = ae.textContent.trim();
                                        break;
                                    }
                                }
                            }
                            results.push({title: title, artist: artist});
                        }
                    }
                }
                return results;
            """)
            if js_songs:
                songs = js_songs
        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique_songs = []
    for s in songs:
        key = (s["title"].lower(), s["artist"].lower())
        if key not in seen:
            seen.add(key)
            unique_songs.append(s)

    return unique_songs


def extract_liked_songs(driver):
    """Navigate to the liked songs page and extract them."""
    print("\nExtracting liked songs...")

    # Navigate to favourites / liked songs
    liked_urls = [
        f"{ANGHAMI_BASE}/favorites",
        f"{ANGHAMI_BASE}/favourites",
        f"{ANGHAMI_BASE}/library/songs",
    ]

    for url in liked_urls:
        try:
            driver.get(url)
            time.sleep(3)

            # Check if the page loaded meaningful content
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if len(body_text) > 100:
                break
        except Exception:
            continue

    scroll_to_load_all(driver)
    songs = extract_songs_from_page(driver)
    print(f"  Found {len(songs)} liked songs.")
    return songs


def extract_playlists(driver):
    """Navigate to the playlists page and extract all playlists with their songs."""
    print("\nExtracting playlists...")

    # Navigate to the library/playlists page
    playlist_urls = [
        f"{ANGHAMI_BASE}/library/playlists",
        f"{ANGHAMI_BASE}/library",
    ]

    for url in playlist_urls:
        try:
            driver.get(url)
            time.sleep(3)
            break
        except Exception:
            continue

    time.sleep(3)

    # Find all playlist links on the page
    playlist_links = []
    try:
        js_playlists = driver.execute_script("""
            let results = [];
            let allLinks = document.querySelectorAll('a');
            let seen = new Set();
            for (let a of allLinks) {
                let href = a.getAttribute('href') || '';
                if (href.includes('/playlist/') && !seen.has(href)) {
                    seen.add(href);
                    let name = a.textContent.trim() ||
                               a.getAttribute('title') ||
                               a.getAttribute('aria-label') || 'Unnamed Playlist';
                    // Clean up the name
                    name = name.split('\\n')[0].trim();
                    if (name.length > 0 && name.length < 200) {
                        results.push({name: name, href: href});
                    }
                }
            }
            return results;
        """)
        if js_playlists:
            playlist_links = js_playlists
    except Exception:
        pass

    print(f"  Found {len(playlist_links)} playlists.")

    playlists = []
    for i, pl in enumerate(playlist_links):
        name = pl["name"]
        href = pl["href"]

        # Build full URL
        if href.startswith("/"):
            full_url = ANGHAMI_BASE + href
        elif href.startswith("http"):
            full_url = href
        else:
            full_url = ANGHAMI_BASE + "/" + href

        print(f"  [{i + 1}/{len(playlist_links)}] Extracting: {name}")

        try:
            driver.get(full_url)
            time.sleep(3)
            scroll_to_load_all(driver)
            songs = extract_songs_from_page(driver)
            print(f"    -> {len(songs)} songs")
            playlists.append({"name": name, "songs": songs})
        except Exception as e:
            print(f"    -> Error: {e}")
            playlists.append({"name": name, "songs": []})

    return playlists


def extract_from_anghami():
    """
    Main extraction function. Opens a browser, waits for login,
    then scrapes liked songs and playlists.
    Returns a dict with 'liked_songs' and 'playlists'.
    """
    driver = create_driver()
    try:
        wait_for_login(driver)

        liked_songs = extract_liked_songs(driver)
        playlists = extract_playlists(driver)

        data = {
            "liked_songs": liked_songs,
            "playlists": playlists,
        }

        # Save to JSON as backup
        output_path = os.path.join(os.path.dirname(__file__), "anghami_export.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nData saved to {output_path}")

        return data
    finally:
        driver.quit()


def load_from_json(filepath):
    """
    Load previously exported Anghami data from a JSON file.

    Expected format:
    {
        "liked_songs": [{"title": "...", "artist": "..."}],
        "playlists": [
            {"name": "Playlist Name", "songs": [{"title": "...", "artist": "..."}]}
        ]
    }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate structure
    if "liked_songs" not in data:
        data["liked_songs"] = []
    if "playlists" not in data:
        data["playlists"] = []

    total_songs = len(data["liked_songs"])
    for pl in data["playlists"]:
        total_songs += len(pl.get("songs", []))

    print(f"Loaded {len(data['liked_songs'])} liked songs and "
          f"{len(data['playlists'])} playlists ({total_songs} total songs).")

    return data
