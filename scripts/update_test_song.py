import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is on sys.path when running via absolute file path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spotify_client import SpotifyClient
from guess_cli import canonicalize_title


def fetch_track(sp_client: SpotifyClient, title: str, artist: str | None) -> Dict[str, Any]:
    sp = sp_client.api
    if artist:
        query = f"track:{title} artist:{artist}"
    else:
        query = f"track:{title}"
    results = sp.search(q=query, type="track", limit=1)
    items = results.get("tracks", {}).get("items", [])
    if not items:
        raise SystemExit("No matching track found")
    t = items[0]

    artists = [{"id": a.get("id"), "name": a.get("name", "")} for a in t.get("artists", [])]
    artist_names = ", ".join(a["name"] for a in artists if a.get("name"))
    album = t.get("album", {})
    external_ids = t.get("external_ids", {})

    return {
        "title": t.get("name", ""),
        "artist": artist_names,
        "canonical_title": canonicalize_title(t.get("name", "")),
        "uri": t.get("uri", ""),
        "duration_ms": int(t.get("duration_ms") or 0),
        "album": album.get("name", ""),
        "release_date": album.get("release_date", ""),
        "track_number": int(t.get("track_number") or 0),
        "disc_number": int(t.get("disc_number") or 0),
        "explicit": bool(t.get("explicit", False)),
        "popularity": int(t.get("popularity") or 0),
        "preview_url": t.get("preview_url", "") or "",
        "isrc": external_ids.get("isrc", ""),
        "external_urls": {"spotify": t.get("external_urls", {}).get("spotify", "")},
        "artists": artists,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Update sample test song JSON from Spotify search")
    parser.add_argument("--title", default="Believer", help="Track title to search")
    parser.add_argument("--artist", default="Imagine Dragons", help="Artist filter (optional)")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "test_data" / "sample_song.json"),
        help="Path to output JSON file",
    )
    args = parser.parse_args()

    client = SpotifyClient()
    track = fetch_track(client, args.title, args.artist)

    out_path = Path(args.output)
    # Merge with existing JSON if present to preserve extra demo fields
    existing: Dict[str, Any] = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    merged = {**existing, **track}

    # If duration exists, regenerate example offsets nicely spaced
    dur = int(merged.get("duration_ms") or 0)
    if dur > 0:
        step = max(15000, dur // 12)
        merged["offsets_ms_examples"] = [i for i in range(0, max(1, dur - 10000), step)][:6]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

