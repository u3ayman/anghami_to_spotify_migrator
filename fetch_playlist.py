"""
Direct Anghami playlist fetcher — no browser needed.
Tries multiple approaches to get playlist data from Anghami.
"""

import json
import re
import sys

import requests

PLAYLIST_ID = "216538677"
PLAYLIST_URL = f"https://play.anghami.com/playlist/{PLAYLIST_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Referer": "https://play.anghami.com/",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Origin": "https://play.anghami.com",
    "Referer": "https://play.anghami.com/",
}


def try_gateway_api(playlist_id):
    """Try Anghami's gateway/bus API used by the web player."""
    print("Trying Anghami gateway API...")

    endpoints = [
        f"https://bus.anghami.com/rest/v1/playlist.get?id={playlist_id}",
        f"https://bus.anghami.com/rest/v1/playlist/{playlist_id}",
        f"https://api.anghami.com/rest/v1/playlist.get?id={playlist_id}",
        f"https://api.anghami.com/gateway.php?type=playlist&id={playlist_id}",
        f"https://bus.anghami.com/gateway.php?type=playlist&id={playlist_id}",
    ]

    for url in endpoints:
        try:
            print(f"  Trying: {url}")
            resp = requests.get(url, headers=API_HEADERS, timeout=15)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Got JSON response with keys: {list(data.keys())[:10]}")
                return data
        except requests.exceptions.JSONDecodeError:
            print(f"  Not JSON, response starts with: {resp.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")

    return None


def try_html_scrape(playlist_url):
    """Fetch the playlist HTML page and extract embedded data."""
    print("\nTrying HTML page scrape...")

    try:
        resp = requests.get(playlist_url, headers=HEADERS, timeout=15)
        print(f"  Status: {resp.status_code}")
        html = resp.text

        # Save raw HTML for debugging
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Saved raw HTML to debug_page.html ({len(html)} chars)")

        songs = []

        # Method 1: Look for JSON-LD structured data
        ld_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        for match in ld_matches:
            try:
                ld = json.loads(match)
                print(f"  Found JSON-LD: {ld.get('@type', 'unknown')}")
                if isinstance(ld, dict) and "track" in ld:
                    for track in ld["track"]:
                        songs.append({
                            "title": track.get("name", ""),
                            "artist": track.get("byArtist", {}).get("name", "Unknown Artist") if isinstance(track.get("byArtist"), dict) else str(track.get("byArtist", "Unknown Artist")),
                        })
                if isinstance(ld, dict) and ld.get("@type") == "MusicPlaylist":
                    tracks = ld.get("track", [])
                    if isinstance(tracks, list):
                        for t in tracks:
                            name = t.get("name", "")
                            artist = "Unknown Artist"
                            if "byArtist" in t:
                                ba = t["byArtist"]
                                artist = ba.get("name", str(ba)) if isinstance(ba, dict) else str(ba)
                            if name:
                                songs.append({"title": name, "artist": artist})
            except json.JSONDecodeError:
                continue

        if songs:
            print(f"  Extracted {len(songs)} songs from JSON-LD")
            return songs

        # Method 2: Look for __NEXT_DATA__ or similar SSR data
        next_data = re.findall(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data:
            try:
                nd = json.loads(next_data[0])
                print(f"  Found __NEXT_DATA__ with keys: {list(nd.keys())[:5]}")
                # Save for inspection
                with open("debug_next_data.json", "w", encoding="utf-8") as f:
                    json.dump(nd, f, indent=2, ensure_ascii=False)
                print("  Saved to debug_next_data.json")
            except json.JSONDecodeError:
                pass

        # Method 3: Look for any embedded JSON with song data
        json_patterns = [
            r'"songs"\s*:\s*(\[.*?\])',
            r'"tracks"\s*:\s*(\[.*?\])',
            r'"playlist"\s*:\s*(\{.*?\})',
            r'"data"\s*:\s*(\{.*?"song.*?\})',
        ]
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    print(f"  Found embedded JSON matching pattern: {pattern[:30]}...")
                    if isinstance(data, list) and len(data) > 0:
                        print(f"  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
                except json.JSONDecodeError:
                    continue

        # Method 4: Look for og:title and other meta tags for at least playlist info
        og_title = re.findall(r'<meta property="og:title" content="(.*?)"', html)
        og_desc = re.findall(r'<meta property="og:description" content="(.*?)"', html)
        if og_title:
            print(f"  Page title: {og_title[0]}")
        if og_desc:
            print(f"  Description: {og_desc[0][:200]}")

        # Method 5: Find all text that looks like song data in the HTML
        # Look for patterns like song titles near artist names
        title_matches = re.findall(r'"title"\s*:\s*"([^"]+)"', html)
        artist_matches = re.findall(r'"artist"\s*:\s*"([^"]+)"', html)
        if title_matches:
            print(f"  Found {len(title_matches)} 'title' fields in HTML")
            print(f"  First 5: {title_matches[:5]}")
        if artist_matches:
            print(f"  Found {len(artist_matches)} 'artist' fields in HTML")

        return songs

    except Exception as e:
        print(f"  Error: {e}")
        return []


def try_oembed(playlist_url):
    """Try oEmbed endpoint."""
    print("\nTrying oEmbed...")
    try:
        url = f"https://play.anghami.com/oembed?url={playlist_url}&format=json"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response: {json.dumps(data, indent=2)[:500]}")
            return data
    except Exception as e:
        print(f"  Error: {e}")
    return None


def try_share_page(playlist_id):
    """Try the share/embed versions of the page."""
    print("\nTrying alternate page versions...")

    urls = [
        f"https://play.anghami.com/playlist/{playlist_id}",
        f"https://anghami.com/playlist/{playlist_id}",
        f"https://play.anghami.com/embed/playlist/{playlist_id}",
    ]

    for url in urls:
        try:
            print(f"  Trying: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            print(f"  Status: {resp.status_code}, Final URL: {resp.url}")
            if resp.status_code == 200 and len(resp.text) > 500:
                # Check for useful data
                html = resp.text
                song_refs = re.findall(r'/song/(\d+)', html)
                if song_refs:
                    print(f"  Found {len(set(song_refs))} unique song references")

                # Look for any JSON data embedded
                scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
                for s in scripts:
                    if '"title"' in s and '"artist"' in s:
                        print(f"  Found script with title+artist data ({len(s)} chars)")
                        # Try to extract
                        with open("debug_script.txt", "w", encoding="utf-8") as f:
                            f.write(s)
        except Exception as e:
            print(f"  Error: {e}")

    return None


def main():
    print("=" * 60)
    print(f"  Fetching Anghami Playlist: {PLAYLIST_ID}")
    print("=" * 60)

    # Try all approaches
    api_data = try_gateway_api(PLAYLIST_ID)
    html_songs = try_html_scrape(PLAYLIST_URL)
    oembed = try_oembed(PLAYLIST_URL)
    try_share_page(PLAYLIST_ID)

    # Check what we got
    songs = []

    if api_data:
        print("\n✅ Got data from API!")
        # Try to extract songs from API response
        for key in ["songs", "tracks", "data", "playlist"]:
            if key in api_data:
                items = api_data[key]
                if isinstance(items, dict) and "songs" in items:
                    items = items["songs"]
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("name") or item.get("SongTitle") or ""
                            artist = item.get("artist") or item.get("ArtistName") or item.get("artistName") or "Unknown"
                            if isinstance(artist, dict):
                                artist = artist.get("name", "Unknown")
                            if title:
                                songs.append({"title": title, "artist": artist})

    if html_songs:
        songs = html_songs

    if songs:
        export = {
            "liked_songs": [],
            "playlists": [{"name": "Soft", "songs": songs}]
        }
        with open("anghami_export.json", "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Exported {len(songs)} songs to anghami_export.json")
        print("Run: python main.py --from-json anghami_export.json")
    else:
        print("\n⚠️  Could not extract songs automatically.")
        print("Check debug_page.html to see what Anghami returned.")
        print("\nNext steps: You may need to manually create the JSON.")
        print("See README.md for the JSON format.")


if __name__ == "__main__":
    main()
