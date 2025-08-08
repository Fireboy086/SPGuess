from typing import Dict, List

from spotify_client import SpotifyClient
from spotify_player import SpotifyPlayer
from guess_cli import run_game
from ui_app import run_ui


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
    print("---===### SPGuess Launcher ###===---")
    print("Authenticating with Spotify and loading your liked songs...")

    client = SpotifyClient()
    sp_api = client.api
    player = SpotifyPlayer(sp_api)

    liked_songs = preload_liked_songs(client, max_items=500)
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

