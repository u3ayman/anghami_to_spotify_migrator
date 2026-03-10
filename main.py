"""
Anghami to Spotify Migration Tool
===================================
Migrates your playlists and liked songs from Anghami to Spotify.

Usage:
    python main.py              - Full migration (scrape Anghami + import to Spotify)
    python main.py --from-json  - Import from a previously saved JSON export
    python main.py --export-only - Only export from Anghami, don't import
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from anghami_extractor import extract_from_anghami, load_from_json
from spotify_importer import create_spotify_client, import_all


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║       Anghami  ──►  Spotify Migration Tool           ║
╚══════════════════════════════════════════════════════╝
    """)


def get_spotify_credentials():
    """Get Spotify API credentials from environment or user input."""
    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()

    if not client_id:
        print("\nSpotify API credentials not found in environment.")
        print("You need a Spotify Developer app. Follow these steps:")
        print("  1. Go to https://developer.spotify.com/dashboard")
        print("  2. Create an app (any name)")
        print("  3. Set redirect URI to: http://127.0.0.1:8888/callback")
        print("  4. Copy the Client ID and Client Secret\n")

        client_id = input("Enter Spotify Client ID: ").strip()
        client_secret = input("Enter Spotify Client Secret: ").strip()

        # Offer to save for next time
        save = input("\nSave credentials to .env file for next time? (y/n): ").strip().lower()
        if save == "y":
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"SPOTIFY_CLIENT_ID={client_id}\n")
                f.write(f"SPOTIFY_CLIENT_SECRET={client_secret}\n")
                f.write(f"SPOTIFY_REDIRECT_URI={redirect_uri}\n")
            print(f"Saved to {env_path}")

    return client_id, client_secret, redirect_uri


def save_unmatched_report(unmatched, filepath="unmatched_songs.json"):
    """Save a report of songs that couldn't be found on Spotify."""
    output = os.path.join(os.path.dirname(__file__), filepath)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)
    print(f"\nUnmatched songs report saved to: {output}")


def main():
    parser = argparse.ArgumentParser(description="Migrate Anghami to Spotify")
    parser.add_argument(
        "--from-json",
        type=str,
        metavar="FILE",
        help="Path to a JSON file with Anghami export data (skip browser scraping)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Only export data from Anghami (don't import to Spotify)",
    )
    args = parser.parse_args()

    print_banner()

    # ── Step 1: Get Anghami data ──
    if args.from_json:
        if not os.path.isfile(args.from_json):
            print(f"Error: File not found: {args.from_json}")
            sys.exit(1)
        print(f"Loading data from: {args.from_json}")
        data = load_from_json(args.from_json)
    else:
        print("Step 1: Extract data from Anghami")
        print("This will open a Chrome browser. You'll need to log in manually.\n")
        try:
            data = extract_from_anghami()
        except KeyboardInterrupt:
            print("\nAborted by user.")
            sys.exit(0)
        except Exception as e:
            print(f"\nError during Anghami extraction: {e}")
            print("\nTip: If browser automation fails, try the manual approach:")
            print("  1. Open play.anghami.com in your browser")
            print("  2. Log in to your account")
            print("  3. Open browser Dev Tools (F12) -> Console")
            print("  4. Paste and run the script from anghami_export.js")
            print("  5. Save the output as anghami_export.json")
            print("  6. Run: python main.py --from-json anghami_export.json")
            sys.exit(1)

    if args.export_only:
        print("\nExport complete. Use --from-json to import later.")
        sys.exit(0)

    # Show summary
    liked = len(data.get("liked_songs", []))
    playlists = len(data.get("playlists", []))
    playlist_songs = sum(len(p.get("songs", [])) for p in data.get("playlists", []))
    print(f"\nAnghami data summary:")
    print(f"  Liked songs:  {liked}")
    print(f"  Playlists:    {playlists} ({playlist_songs} songs total)")

    if liked == 0 and playlist_songs == 0:
        print("\nNo songs found to migrate. Check your Anghami export.")
        sys.exit(0)

    # ── Step 2: Import to Spotify ──
    print("\nStep 2: Import to Spotify")

    client_id, client_secret, redirect_uri = get_spotify_credentials()

    try:
        sp, user_id = create_spotify_client(client_id, client_secret, redirect_uri)
    except Exception as e:
        print(f"\nError connecting to Spotify: {e}")
        print("Make sure your Client ID, Secret, and Redirect URI are correct.")
        sys.exit(1)

    # Confirm before proceeding
    print(f"\nReady to import {liked} liked songs and {playlists} playlists to Spotify.")
    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # Run the import
    unmatched = import_all(sp, user_id, data)

    # ── Step 3: Report ──
    print("\n" + "=" * 60)
    print("  MIGRATION COMPLETE")
    print("=" * 60)

    if unmatched:
        print(f"\n{len(unmatched)} songs could not be found on Spotify.")
        save_unmatched_report(unmatched)
        print("\nThese songs may have different names on Spotify or may not be available.")
        print("Check unmatched_songs.json for the full list.")
    else:
        print("\nAll songs were successfully matched and imported!")

    print("\nDone! Enjoy your music on Spotify 🎵")


if __name__ == "__main__":
    main()
