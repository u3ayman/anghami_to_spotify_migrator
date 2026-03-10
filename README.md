# Anghami to Spotify Migration Tool

Migrate your **playlists** and **liked songs** from Anghami to Spotify.

No Anghami API needed — uses browser automation (or a manual console script) to extract your data.

---

## Prerequisites

- **Python 3.9+**
- **Google Chrome** (for Anghami extraction)
- A **Spotify account** (free or premium)

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a Spotify Developer App (free, takes 2 minutes)

1. Go to **https://developer.spotify.com/dashboard**
2. Log in with your Spotify account
3. Click **"Create App"**
   - App name: anything (e.g., "Anghami Migration")
   - App description: anything
   - Redirect URI: `http://127.0.0.1:8888/callback` (**important — must match exactly**)
4. Once created, go to **Settings** and copy:
   - **Client ID**
   - **Client Secret**

### 3. (Optional) Save credentials to a `.env` file

Create a `.env` file in this folder:

```
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Or just run the tool — it will ask you to enter them.

---

## Usage

### Option A: Full Automated Migration

```bash
python main.py
```

This will:
1. Open a Chrome window to Anghami — **log in manually**
2. Scrape your liked songs and playlists
3. Search for each song on Spotify
4. Create playlists and save liked songs on Spotify

### Option B: Export Anghami Only (no Spotify import)

```bash
python main.py --export-only
```

Saves your data to `anghami_export.json` for later import.

### Option C: Import from a JSON file

```bash
python main.py --from-json anghami_export.json
```

Skips the browser step — imports directly from a previously exported file.

---

## Manual Export (if browser automation fails)

If Selenium doesn't work, you can export manually:

1. Open **https://play.anghami.com** in Chrome
2. Log in to your account
3. Press **F12** → go to the **Console** tab
4. Copy-paste the entire contents of `anghami_export.js` and press **Enter**
5. Wait for it to finish — a file `anghami_export.json` will download
6. Run:

```bash
python main.py --from-json anghami_export.json
```

---

## JSON Format

If you want to create the export file manually (or edit it), use this format:

```json
{
  "liked_songs": [
    {"title": "Song Name", "artist": "Artist Name"},
    {"title": "Another Song", "artist": "Another Artist"}
  ],
  "playlists": [
    {
      "name": "My Playlist",
      "songs": [
        {"title": "Song Name", "artist": "Artist Name"}
      ]
    }
  ]
}
```

---

## Output Files

| File | Description |
|------|-------------|
| `anghami_export.json` | Your exported Anghami data (songs + playlists) |
| `unmatched_songs.json` | Songs that couldn't be found on Spotify |
| `.env` | Your Spotify credentials (if you chose to save) |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Chrome doesn't open | Make sure Google Chrome is installed |
| ChromeDriver error | The tool auto-downloads the right driver, but make sure Chrome is up to date |
| Spotify auth fails | Double-check your Client ID, Secret, and that the redirect URI matches exactly |
| Songs not found on Spotify | Some songs may have different names or not be available. Check `unmatched_songs.json` |
| Anghami scraping finds 0 songs | Anghami may have changed their website. Use the manual JS export instead |

---

## How It Works

1. **Anghami Extraction**: Opens Anghami's web player in Chrome, navigates to your liked songs and each playlist, and scrapes the song titles and artists from the page DOM.

2. **Spotify Search**: For each song, searches Spotify using progressively looser queries (exact match → partial match → title-only) to maximize matches.

3. **Spotify Import**: Creates playlists on your Spotify account and adds matched songs. Liked songs are saved to your Spotify library.
