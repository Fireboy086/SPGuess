import os
from pathlib import Path
from typing import Dict, List, Optional

import configparser
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyPKCE
from spotipy.cache_handler import CacheFileHandler


# Default scopes cover reading liked songs/playlists and controlling playback
DEFAULT_SCOPES = "user-library-read playlist-read-private user-read-playback-state user-modify-playback-state"

# Optional app-wide public defaults (safe with PKCE). Replace with your own.
DEFAULT_CLIENT_ID = "d173d609d4cf489d97e80c2d1d7232e3"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def _find_creds_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates.append(Path.cwd() / ".Creds.ini")
    candidates.append(Path(__file__).resolve().parent / ".Creds.ini")
    for path in candidates:
        if path.exists():
            return path
    return None


def load_spotify_creds(config_path: Optional[str] = None) -> Dict[str, str]:
    parser = configparser.ConfigParser()
    creds = {"client_id": "", "client_secret": "", "redirect_uri": ""}
    creds_file = _find_creds_file(config_path)
    if creds_file is not None:
        parser.read(creds_file)
        if parser.has_section("Spotify"):
            section = parser["Spotify"]
            creds["client_id"] = section.get("ClientID", "").strip()
            creds["client_secret"] = section.get("ClientSecret", "").strip()
            creds["redirect_uri"] = section.get("RedirectURI", "").strip()

    # Fallback to environment variables if any field missing
    creds["client_id"] = creds["client_id"] or os.getenv("SPOTIPY_CLIENT_ID", "")
    creds["client_secret"] = creds["client_secret"] or os.getenv("SPOTIPY_CLIENT_SECRET", "")
    creds["redirect_uri"] = creds["redirect_uri"] or os.getenv("SPOTIPY_REDIRECT_URI", "")

    # Final fallback to public defaults for PKCE flow (no secret)
    if not creds["client_id"] and DEFAULT_CLIENT_ID:
        creds["client_id"] = DEFAULT_CLIENT_ID
    if not creds["redirect_uri"] and DEFAULT_REDIRECT_URI:
        creds["redirect_uri"] = DEFAULT_REDIRECT_URI
    return creds


class SpotifyClient:
    """Thin wrapper around Spotipy for auth and common queries."""

    def __init__(self, scopes: Optional[str] = None, creds_file: Optional[str] = None) -> None:
        self.scopes = scopes or DEFAULT_SCOPES
        creds = load_spotify_creds(creds_file)
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        redirect_uri = creds.get("redirect_uri")

        # Use a user-writable token cache file to avoid repeated consent prompts
        from pathlib import Path as _Path
        cache_path = _Path.home() / ".spguess_token_cache"
        cache_handler = CacheFileHandler(cache_path=str(cache_path))

        if client_id and redirect_uri and not client_secret:
            # PKCE flow: no client secret required; safe to share client_id publicly
            auth = SpotifyPKCE(
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=self.scopes,
                cache_handler=cache_handler,
            )
        elif client_id and client_secret and redirect_uri:
            auth = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=self.scopes,
                cache_handler=cache_handler,
            )
        else:
            # Fall back to env-configured OAuth (may include secret)
            auth = SpotifyOAuth(scope=self.scopes, cache_handler=cache_handler)
        self._sp = spotipy.Spotify(auth_manager=auth)

    @property
    def api(self) -> spotipy.Spotify:
        return self._sp

    def get_liked_tracks(self, max_items: int = 200) -> List[Dict[str, str]]:
        """Fetch up to max_items of the user's saved tracks.

        Returns a list of dicts with keys: title, artist, uri, preview_url, duration_ms.
        """
        collected: List[Dict[str, str]] = []
        limit = 50
        offset = 0

        while len(collected) < max_items:
            remaining = max_items - len(collected)
            page_limit = limit if remaining > limit else remaining
            results = self._sp.current_user_saved_tracks(limit=page_limit, offset=offset)
            items = results.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track") or {}
                if not track:
                    continue
                title: str = track.get("name", "")
                artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
                uri: str = track.get("uri", "")
                preview_url: Optional[str] = track.get("preview_url")
                duration_ms: int = int(track.get("duration_ms") or 0)
                collected.append(
                    {
                        "title": title,
                        "artist": artists,
                        "uri": uri,
                        "preview_url": preview_url or "",
                        "duration_ms": duration_ms,
                    }
                )

            if len(items) < page_limit:
                break
            offset += page_limit

        return collected

