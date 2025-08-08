import time
from typing import Optional

import spotipy
from debug import debug


class SpotifyPlayer:
    """Simple playback helper for previewing tracks for a short time window."""

    def __init__(self, sp: spotipy.Spotify) -> None:
        self.sp = sp
        self._restriction_warned = False

    def get_active_device_id(self) -> Optional[str]:
        devices = self.sp.devices().get("devices", [])
        debug(f"Devices: {devices}")
        # Prefer active and not restricted
        for d in devices:
            if d.get("is_active") and not d.get("is_restricted"):
                return d.get("id")
        # Fallback: any not restricted
        for d in devices:
            if not d.get("is_restricted"):
                return d.get("id")
        # Final fallback: any device
        return devices[0].get("id") if devices else None

    def _try_pause(self, device_id: Optional[str]) -> bool:
        try:
            if device_id:
                self.sp.pause_playback(device_id=device_id)
            else:
                self.sp.pause_playback()
            return True
        except spotipy.exceptions.SpotifyException as e:
            # 403 restriction or other errors
            if not self._restriction_warned:
                print(f"Playback error: {e}")
                self._restriction_warned = True
            return False

    def _try_fade_out(self, device_id: Optional[str], steps: int = 4, duration: float = 0.6) -> bool:
        # Remove volume fade behavior to avoid surprising volume changes
        return False

    def play_track_for(self, track_uri: str, seconds: float = 1.0, start_ms: Optional[int] = None) -> None:
        """Start playback of the given track on the active device for N seconds, then pause.

        If start_ms is provided, begin from that offset.
        """
        device_id = self.get_active_device_id()
        if not device_id:
            print("No active Spotify device found. Open Spotify on a device and try again.")
            return

        try:
            if start_ms is not None:
                try:
                    debug(f"start_playback uri={track_uri} device={device_id} position_ms={int(max(0, start_ms))}")
                    self.sp.start_playback(device_id=device_id, uris=[track_uri], position_ms=int(max(0, start_ms)))
                except spotipy.exceptions.SpotifyException:
                    # Retry without position if restricted
                    debug("position_ms restricted; retrying without offset")
                    self.sp.start_playback(device_id=device_id, uris=[track_uri])
            else:
                debug(f"start_playback uri={track_uri} device={device_id}")
                self.sp.start_playback(device_id=device_id, uris=[track_uri])
            time.sleep(max(0.1, seconds))
            # Attempt a pause; if restricted, silently ignore without volume changes
            debug("pause_playback attempt")
            self._try_pause(device_id)
        except spotipy.exceptions.SpotifyException as e:
            print(f"Playback error: {e}")

