import time
from typing import Optional

import spotipy


class SpotifyPlayer:
    """Simple playback helper for previewing tracks for a short time window."""

    def __init__(self, sp: spotipy.Spotify) -> None:
        self.sp = sp
        self._restriction_warned = False

    def get_active_device_id(self) -> Optional[str]:
        devices = self.sp.devices().get("devices", [])
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
        try:
            # Get current volume
            device_info = None
            devices = self.sp.devices().get("devices", [])
            for d in devices:
                if d.get("id") == device_id:
                    device_info = d
                    break
            current_vol = device_info.get("volume_percent") if device_info else None
            if current_vol is None:
                current_vol = 50

            step_sleep = max(0.05, duration / max(1, steps))
            for v in range(int(current_vol), -1, -max(1, int(current_vol / max(1, steps)))):
                self.sp.volume(v, device_id=device_id)
                time.sleep(step_sleep)
            # Try pause one last time
            if not self._try_pause(device_id):
                # Restore volume to a sane level if pause still not allowed
                self.sp.volume(min(20, current_vol), device_id=device_id)
            else:
                # Restore volume to previous level after pause
                self.sp.volume(current_vol, device_id=device_id)
            return True
        except spotipy.exceptions.SpotifyException:
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
                    self.sp.start_playback(device_id=device_id, uris=[track_uri], position_ms=int(max(0, start_ms)))
                except spotipy.exceptions.SpotifyException:
                    # Retry without position if restricted
                    self.sp.start_playback(device_id=device_id, uris=[track_uri])
            else:
                self.sp.start_playback(device_id=device_id, uris=[track_uri])
            time.sleep(max(0.1, seconds))
            if not self._try_pause(device_id):
                # Fallback: try to fade volume if pause is restricted
                self._try_fade_out(device_id)
        except spotipy.exceptions.SpotifyException as e:
            print(f"Playback error: {e}")

