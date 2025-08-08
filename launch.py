from typing import Dict, List

import argparse
from spotify_client import SpotifyClient
from spotify_player import SpotifyPlayer
from guess_cli import run_game
from ui_app import run_ui
from debug import set_verbose, set_verbosity, set_color_enabled, debug


def preload_liked_songs(sp_client: SpotifyClient, max_items: int = 500) -> List[Dict[str, str]]:
    songs = sp_client.get_liked_tracks(max_items=max_items)
    # Ensure expected keys for game: title, artist, uri
    normalized: List[Dict[str, str]] = []
    for s in songs:
        normalized.append(
            {
                "title": s.get("title", ""),
                "artist": s.get("artist", ""),
                "uri": s.get("uri", ""),
                "duration_ms": int(s.get("duration_ms", 0)),
            }
        )
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="SPGuess launcher")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v: normal, -vv: extreme)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored debug output")
    args = parser.parse_args()
    set_verbosity(min(2, int(args.verbose or 0)))
    set_color_enabled(not args.no_color)
    if args.verbose:
        level = "EXTREME" if args.verbose >= 2 else "NORMAL"
        debug(f"Verbose mode: {level}")
    print("---===### SPGuess Launcher ###===---")
    print("Authenticating with Spotify and loading your liked songs...")

    client = SpotifyClient()
    debug("Spotify client initialized")
    sp_api = client.api
    player = SpotifyPlayer(sp_api)
    debug("Spotify player ready")

    liked_songs = preload_liked_songs(client, max_items=500)
    debug(f"Loaded {len(liked_songs)} liked songs")
    if not liked_songs:
        print("No liked songs found. Please like some songs on Spotify and try again.")
        return

    device_id = player.get_active_device_id()
    if not device_id:
        print("No active Spotify device found. Open Spotify on a device and try again.")
        return

    print(f"Loaded {len(liked_songs)} liked songs. Starting UI...")
    run_ui(
        liked_songs,
        spotify_player=player,
        attempts_per_round=3,
        lives=3,
        seconds_base=1.0,
        seconds_growth=0.75,
        randomize_offset=True,
        per_round_seconds=60,
    )


if __name__ == "__main__":
    main()

