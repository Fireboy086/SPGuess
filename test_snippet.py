import argparse
import json
import time
from pathlib import Path
from typing import List, Tuple

import requests

from spotify_client import SpotifyClient
from spotify_player import SpotifyPlayer


def parse_lrc(lrc_text: str) -> List[Tuple[int, str]]:
    lines: List[Tuple[int, str]] = []
    for raw in lrc_text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        # Match [mm:ss.xx] or [mm:ss] or [hh:mm:ss.xx]
        import re
        for tag in re.findall(r"\[(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?)\]", raw):
            timestr = tag
            parts = timestr.split(":")
            if len(parts) == 3:
                h, m, s = parts
                sec = float(s)
                total_ms = int((int(h) * 3600 + int(m) * 60 + sec) * 1000)
            else:
                m, s = parts
                sec = float(s)
                total_ms = int((int(m) * 60 + sec) * 1000)
            text = re.sub(r"^\[[^]]+\]+", "", raw).strip()
            lines.append((total_ms, text))
    lines.sort(key=lambda x: x[0])
    return lines


def fetch_lrclib_lrc(title: str, artist: str) -> List[Tuple[int, str]]:
    # LRCLIB public API: https://lrclib.net/docs
    params = {"track_name": title, "artist_name": artist}
    r = requests.get("https://lrclib.net/api/get", params=params, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    synced = data.get("syncedLyrics") or ""
    if not synced:
        return []
    return parse_lrc(synced)


def find_line_at(lrc_lines: List[Tuple[int, str]], ms: int) -> str:
    prior = ""
    for t, text in lrc_lines:
        if t <= ms:
            if text:
                prior = text
        else:
            break
    return prior


def main() -> None:
    parser = argparse.ArgumentParser(description="Test snippet and lyric fetch")
    parser.add_argument("--time-ms", type=int, default=None, help="Specific time in ms to fetch lyric line")
    args = parser.parse_args()
    data_path = Path(__file__).resolve().parent / "test_data" / "sample_song.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))

    print("---===### SAMPLE SONG DATA ###===---")
    for key in [
        "title",
        "artist",
        "canonical_title",
        "uri",
        "duration_ms",
        "album",
        "release_date",
        "track_number",
        "disc_number",
        "explicit",
        "popularity",
        "preview_url",
        "isrc",
    ]:
        print(f"{key}: {data.get(key)}")

    print("\n---===### OFFSETS ###===---")
    print(data.get("offsets_ms_examples", []))
    print("---===### PROGRESS ###===---")
    print(data.get("progress_ms_examples", []))

    # Lyrics via LRCLIB
    title = data.get("canonical_title") or data.get("title") or ""
    artist = (data.get("artist") or "").split(",")[0]
    lrc_lines = fetch_lrclib_lrc(title=title, artist=artist)
    if lrc_lines:
        print("\n---===### LYRICS (LRCLIB) ###===---")
        targets = [args.time_ms] if args.time_ms is not None else data.get("progress_ms_examples", [])
        for t in targets:
            line = find_line_at(lrc_lines, int(t))
            print(f"t={t}ms -> {line}")
    else:
        print("\nNo synced lyrics found via LRCLIB for this track.")

    if not data.get("uri"):
        print("No Spotify URI provided; skipping playback test.")
        return

    client = SpotifyClient()
    player = SpotifyPlayer(client.api)
    device_id = player.get_active_device_id()
    if not device_id:
        print("No active Spotify device; open Spotify and try again.")
        return

    print("\nAttempting 3 short snippets...")
    duration = 1.0
    for i, start in enumerate(data.get("offsets_ms_examples", [])[:3], start=1):
        print(f"Snippet {i}: start_ms={start}, seconds={duration}")
        player.play_track_for(data["uri"], seconds=duration, start_ms=int(start))
        time.sleep(0.3)


if __name__ == "__main__":
    main()

