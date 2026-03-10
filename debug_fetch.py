import requests, json

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})

# Try main page first to get cookies
print("1. Getting main page...")
r = s.get("https://play.anghami.com/", timeout=15)
print(f"   Status: {r.status_code}, Len: {len(r.text)}")
print(f"   Cookies: {dict(s.cookies)}")

# Now try the playlist
print("\n2. Getting playlist page...")
r = s.get("https://play.anghami.com/playlist/216538677", timeout=15)
print(f"   Status: {r.status_code}, Len: {len(r.text)}")
if r.text:
    with open("debug_page2.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("   Saved to debug_page2.html")
    print(f"   First 300 chars: {r.text[:300]}")

# Try the API with cookies from the session
print("\n3. Trying API with session cookies...")
s.headers.update({
    "Accept": "application/json",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Origin": "https://play.anghami.com",
    "Referer": "https://play.anghami.com/",
})

for url in [
    "https://bus.anghami.com/rest/v1/playlist.get?id=216538677&count=100",
    "https://bus.anghami.com/rest/v1/GWPlaylistGet.view?id=216538677",
]:
    print(f"   Trying: {url}")
    r = s.get(url, timeout=15)
    print(f"   Status: {r.status_code}, Len: {len(r.text)}")
    if r.text:
        print(f"   Response: {r.text[:500]}")
