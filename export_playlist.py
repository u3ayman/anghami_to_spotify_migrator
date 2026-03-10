"""
Anghami Playlist Exporter — uses undetected-chromedriver to bypass bot detection.
Close ALL Chrome windows before running this!
"""

import json
import time
import undetected_chromedriver as uc


def main():
    print("=" * 60)
    print("  Anghami Playlist Exporter")
    print("=" * 60)
    print("\nMake sure ALL Chrome windows are closed!")
    input("Press ENTER to continue...")

    print("\nLaunching Chrome...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)

    # Go to Anghami
    print("Opening Anghami...")
    driver.get("https://play.anghami.com/")
    time.sleep(3)

    print("\n" + "=" * 60)
    print("  LOG IN to your Anghami account in the Chrome window.")
    print("  Then press ENTER here.")
    print("=" * 60)
    input("\n>>> Press ENTER after logging in... ")

    # Now navigate to the playlist
    playlist_url = "https://play.anghami.com/playlist/216538677"
    print(f"\nNavigating to playlist: {playlist_url}")
    driver.get(playlist_url)
    time.sleep(5)

    print("Scrolling to load all songs...")
    # Anghami lazy-loads songs with IntersectionObserver
    # We need to scroll repeatedly and wait for new rows to appear
    stale_count = 0
    for i in range(200):
        # Count current rows
        row_count = driver.execute_script("return document.querySelectorAll('a.table-row, .table-row').length")
        
        # Scroll the page to the bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        
        # Also scroll any inner scrollable containers
        driver.execute_script("""
            document.querySelectorAll('.container-table100, [class*="container"], [class*="content"], main, [class*="scroll"]').forEach(el => {
                el.scrollTop = el.scrollHeight;
            });
        """)
        
        # Scroll the last visible row into view to trigger IntersectionObserver
        driver.execute_script("""
            let rows = document.querySelectorAll('a.table-row, .table-row');
            if (rows.length > 0) {
                rows[rows.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        """)
        time.sleep(1.5)
        
        # Check if new rows appeared
        new_count = driver.execute_script("return document.querySelectorAll('a.table-row, .table-row').length")
        print(f"  Scroll {i+1}: {new_count} rows loaded", end="\r")
        
        if new_count == row_count:
            stale_count += 1
            # Give it more chances — sometimes loading is slow
            if stale_count >= 5:
                # One last aggressive scroll attempt
                driver.execute_script("""
                    window.scrollTo(0, 0);
                """)
                time.sleep(1)
                driver.execute_script("""
                    window.scrollTo(0, document.body.scrollHeight);
                    let rows = document.querySelectorAll('a.table-row, .table-row');
                    if (rows.length > 0) {
                        rows[rows.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
                    }
                """)
                time.sleep(3)
                final_count = driver.execute_script("return document.querySelectorAll('a.table-row, .table-row').length")
                if final_count == new_count:
                    break
                else:
                    stale_count = 0  # Reset, more songs appeared
        else:
            stale_count = 0  # Reset counter when new rows load
    
    total_rows = driver.execute_script("return document.querySelectorAll('a.table-row, .table-row').length")
    print(f"\nDone scrolling. Total rows found: {total_rows}")

    # Run inspectPage equivalent in JS to see what's on the page
    print("\nExtracting songs from page...")
    info = driver.execute_script("""
        let result = { url: window.location.href, songs: [], pageTitle: document.title };

        let seen = new Set();

        // Anghami uses: a.table-row > .cell-title span (title), .cell-artist (artist)
        document.querySelectorAll('a.table-row, .table-row').forEach(row => {
            let titleEl = row.querySelector('.cell-title span, .cell-title a, .cell-title');
            let artistEl = row.querySelector('.cell-artist span, .cell-artist a, .cell-artist');

            if (titleEl) {
                let title = titleEl.textContent.trim();
                let artist = artistEl ? artistEl.textContent.trim() : 'Unknown Artist';
                if (title && title.length > 0 && title.length < 300) {
                    let key = title.toLowerCase() + '|' + artist.toLowerCase();
                    if (!seen.has(key)) {
                        seen.add(key);
                        result.songs.push({ title, artist });
                    }
                }
            }
        });

        return result;
    """)

    print(f"  URL: {info['url']}")
    print(f"  Page title: {info['pageTitle']}")
    print(f"  Songs extracted: {len(info['songs'])}")

    if info['songs']:
        print(f"\n  First 5 songs:")
        for s in info['songs'][:5]:
            print(f"    {s['title']} - {s['artist']}")

        # Save export
        export = {
            "liked_songs": [],
            "playlists": [{"name": "Soft", "songs": info['songs']}]
        }
        with open("anghami_export.json", "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Exported {len(info['songs'])} songs to anghami_export.json")
        print("Next: python main.py --from-json anghami_export.json")
    else:
        print("\n⚠️  No songs found automatically.")

    # Always save page source for debugging
    page_source = driver.page_source
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    print(f"Page source saved to debug_page.html ({len(page_source)} chars)")

    body_text = driver.find_element("tag name", "body").text
    with open("debug_text.txt", "w", encoding="utf-8") as f:
        f.write(body_text)
    print(f"Page visible text saved to debug_text.txt ({len(body_text)} chars)")

    input("\nPress ENTER to close the browser...")
    driver.quit()


if __name__ == "__main__":
    main()
