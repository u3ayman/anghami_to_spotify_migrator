"""
Spotify Importer - Searches for songs on Spotify and creates playlists / saves likes.

Uses Spotipy with the Authorization Code flow so we can modify the user's library.
"""

import re
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPES = [
    "user-library-modify",      # Save tracks to "Liked Songs"
    "playlist-modify-public",   # Create / edit public playlists
    "playlist-modify-private",  # Create / edit private playlists
]


def create_spotify_client(client_id, client_secret, redirect_uri="http://127.0.0.1:8888/callback"):
    """
    Authenticate with Spotify and return a Spotipy client.
    Opens a browser for the user to authorize the app.
    """
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
        open_browser=True,
    ))
    user = sp.current_user()
    print(f"Logged into Spotify as: {user['display_name']} ({user['id']})")
    return sp, user["id"]


def clean_query(text):
    """Remove parenthetical info and special characters for better search results."""
    # Remove content in parentheses like (Official Audio), (feat. XYZ)
    text = re.sub(r"\(.*?\)", "", text)
    # Remove content in brackets
    text = re.sub(r"\[.*?\]", "", text)
    # Remove special characters except spaces and basic punctuation
    text = re.sub(r"[^\w\s\-']", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_track(sp, title, artist):
    """
    Search for a track on Spotify. Tries progressively looser queries.
    Returns the Spotify track URI or None.
    """
    queries = [
        # Exact search with track and artist fields
        f'track:"{clean_query(title)}" artist:"{clean_query(artist)}"',
        # Slightly looser: no quotes
        f"track:{clean_query(title)} artist:{clean_query(artist)}",
        # Even looser: just the title and artist as plain text
        f"{clean_query(title)} {clean_query(artist)}",
        # Last resort: title only
        f"{clean_query(title)}",
    ]

    for query in queries:
        try:
            results = sp.search(q=query, type="track", limit=5)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                # Return the first result
                return tracks[0]["uri"]
        except spotipy.exceptions.SpotifyException:
            time.sleep(1)
            continue
        except Exception:
            continue

    return None


def import_liked_songs(sp, liked_songs):
    """
    Search for each liked song on Spotify and save it to the user's library.
    Returns stats about matched/unmatched songs.
    """
    print("\n" + "=" * 60)
    print("  IMPORTING LIKED SONGS")
    print("=" * 60)

    matched = []
    unmatched = []

    for i, song in enumerate(liked_songs):
        title = song["title"]
        artist = song.get("artist", "")
        print(f"  [{i + 1}/{len(liked_songs)}] {title} - {artist}", end=" ... ")

        uri = search_track(sp, title, artist)
        if uri:
            matched.append(uri)
            print("FOUND")
        else:
            unmatched.append(song)
            print("NOT FOUND")

        # Rate limiting: Spotify allows ~30 requests/sec, be conservative
        if (i + 1) % 20 == 0:
            time.sleep(1)

    # Save matched tracks to library in batches of 50
    if matched:
        # Extract track IDs from URIs
        track_ids = [uri.split(":")[-1] for uri in matched]
        for batch_start in range(0, len(track_ids), 50):
            batch = track_ids[batch_start:batch_start + 50]
            try:
                sp.current_user_saved_tracks_add(batch)
            except Exception as e:
                print(f"  Warning: Failed to save batch: {e}")
            time.sleep(0.5)

    print(f"\n  Liked Songs: {len(matched)} matched, {len(unmatched)} not found.")
    return matched, unmatched


def import_playlist(sp, user_id, playlist_name, songs):
    """
    Create a Spotify playlist and add the matched songs.
    Returns stats about matched/unmatched songs.
    """
    print(f"\n  Playlist: {playlist_name} ({len(songs)} songs)")

    matched = []
    unmatched = []

    for i, song in enumerate(songs):
        title = song["title"]
        artist = song.get("artist", "")
        print(f"    [{i + 1}/{len(songs)}] {title} - {artist}", end=" ... ")

        uri = search_track(sp, title, artist)
        if uri:
            matched.append(uri)
            print("FOUND")
        else:
            unmatched.append(song)
            print("NOT FOUND")

        if (i + 1) % 20 == 0:
            time.sleep(1)

    if not matched:
        print(f"    No songs matched for '{playlist_name}', skipping playlist creation.")
        return matched, unmatched

    # Create the playlist
    try:
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=False,
            description=f"Migrated from Anghami",
        )
        playlist_id = playlist["id"]
        print(f"    Created playlist: {playlist_name} (ID: {playlist_id})")
    except Exception as e:
        print(f"    Error creating playlist: {e}")
        return matched, unmatched

    # Add tracks in batches of 100
    for batch_start in range(0, len(matched), 100):
        batch = matched[batch_start:batch_start + 100]
        try:
            sp.playlist_add_items(playlist_id, batch)
        except Exception as e:
            print(f"    Warning: Failed to add batch: {e}")
        time.sleep(0.5)

    print(f"    Added {len(matched)} songs, {len(unmatched)} not found.")
    return matched, unmatched


def import_playlists(sp, user_id, playlists):
    """Import all playlists to Spotify."""
    print("\n" + "=" * 60)
    print("  IMPORTING PLAYLISTS")
    print("=" * 60)

    total_matched = 0
    total_unmatched = 0
    all_unmatched = []

    for pl in playlists:
        name = pl["name"]
        songs = pl.get("songs", [])
        if not songs:
            print(f"\n  Skipping empty playlist: {name}")
            continue

        matched, unmatched = import_playlist(sp, user_id, name, songs)
        total_matched += len(matched)
        total_unmatched += len(unmatched)
        for s in unmatched:
            all_unmatched.append({"playlist": name, **s})

    print(f"\n  Playlists total: {total_matched} matched, {total_unmatched} not found.")
    return all_unmatched


def import_all(sp, user_id, data):
    """
    Import everything: liked songs and playlists.
    Returns a report of unmatched songs.
    """
    all_unmatched = []

    # Import liked songs
    if data.get("liked_songs"):
        _, unmatched_likes = import_liked_songs(sp, data["liked_songs"])
        for s in unmatched_likes:
            all_unmatched.append({"source": "Liked Songs", **s})
    else:
        print("\nNo liked songs to import.")

    # Import playlists
    if data.get("playlists"):
        unmatched_pl = import_playlists(sp, user_id, data["playlists"])
        for s in unmatched_pl:
            all_unmatched.append({"source": s.pop("playlist", "Unknown"), **s})
    else:
        print("\nNo playlists to import.")

    return all_unmatched
