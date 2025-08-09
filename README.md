## SPGuess

### Spotify-powered song guessing game

Type the title (and optionally the artist) to guess what’s playing from your own Spotify library. Short snippets play, getting a little longer each attempt. Fast, fuzzy matching, slick dark UI, keyboard-first controls, and a simple scoring system keep it engaging.

### Highlights
- **Your music**: Pulls up to 500 of your Liked Songs via Spotify.
- **Snippet gameplay**: Each wrong attempt replays a slightly longer snippet. Optional per‑round timer.
- **Fuzzy matching**: Case/punctuation-insensitive; partials work well. Include the artist for bonus points.
- **Smart start**: Start snippets from random positions to avoid always hearing the intro.
- **Suggestions & tab-complete**: Live fuzzy suggestions and tab cycling.
- **Scoring & highscores**: Points, accuracy, lives, and a local `high_scores.json`.
- **UI**: Built with `customtkinter` (dark theme). Simple controls, fast feedback.

### Quickstart
1. **Requirements**
   - Python 3.10+ (3.11 recommended)
   - A Spotify account (Premium recommended for playback control)
   - Spotify app open on a device you control (desktop/mobile)
2. **Install**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Spotify auth (pick one)**
   - Env vars:
     - `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET` (optional if using PKCE), `SPOTIPY_REDIRECT_URI`
   - Or place a `.Creds.ini` file in project root (or alongside `spotify_client.py`):
     ```ini
     [Spotify]
     ClientID=YOUR_CLIENT_ID
     ClientSecret=YOUR_CLIENT_SECRET
     RedirectURI=http://127.0.0.1:8888/callback
     ```
   - Notes:
     - PKCE is supported; if you provide only `ClientID` and `RedirectURI`, no secret is required.
     - The code includes safe public defaults for PKCE; you can use your own app credentials instead.
     - Tokens are cached at `~/.spguess_token_cache` to avoid re-consent.
4. **Run**
   ```bash
   python launch.py
   ```
   - Optional flags: `-v` (verbose), `-vv` (extreme), `--no-color`.

### Gameplay cheat sheet
- **Goal**: Guess the song title (optionally include artist for +2 bonus).
- **Attempts**: Default 3 per round; each replay gets a bit longer.
- **Timer**: Optional per‑round time limit (default 60s).
- **Lives**: Lose one for each failed round. Game ends at 0.
- **Inputs**:
  - Press Enter to submit
  - Press Tab to cycle suggestions
  - Buttons: Replay Snippet, Guess, Skip, Quit
  - Commands in the input: `/skip`, `/s`, `/pass`, `/next`, `/quit`, `/exit`
- **Scoring**: +1 for correct title, +3 if your input includes the artist.
- **High score**: Stored locally next to `ui_app.py` as `high_scores.json`.

### Settings you can tweak (from the start screen)
- Attempts per round
- Lives per game
- Enable/disable time limit and set seconds per round
- Randomize start position for snippets
- Advanced: base snippet seconds, growth per attempt, inter‑round delay

### Troubleshooting
- “No active Spotify device found”: Open the Spotify app on your computer/phone and start any playback once so the device registers, then try again.
- Playback errors or 403: Spotify playback control generally requires Premium and can be restricted on some devices.
- Nothing plays / silence: Some tracks have restricted `position_ms` seeking; the player falls back to starting at 0 when needed.

### Dev utilities
- `scripts/update_test_song.py`: Refreshes `test_data/sample_song.json` from Spotify search (includes offsets and metadata). Example:
  ```bash
  python scripts/update_test_song.py --title "Believer" --artist "Imagine Dragons"
  ```
- `test_snippet.py`: Demonstrates lyric lookup (LRCLIB) and short snippet playback for the sample song. Example:
  ```bash
  python test_snippet.py --time-ms 60000
  ```

### Architecture overview
- `launch.py`: Authenticates, loads Liked Songs (normalized `title/artist/uri/duration_ms`), verifies a device, launches the UI.
- `ui_app.py`: The game UI and logic: timer, suggestions, guesses, scoring, highscores.
- `spotify_client.py`: Auth and data. Supports OAuth with PKCE or Client Secret; caches tokens.
- `spotify_player.py`: Minimal playback helper for short snippet playback with optional `position_ms`.
- `guess_cli.py`: CLI prototype and matching/evaluation helpers.

### Roadmap (near → far)
- Daily challenge / seedable round of the day
- Party mode (shared device, pass‑and‑play), playlist‑scoped modes
- Hints: lyric lines near the snippet (LRCLIB), year/album/artist hints
- Leaderboards, achievements, and streaks
- Adaptive difficulty (learn “good snippet windows” per track)
- Web client (Spotify Web Playback SDK) and cross‑platform packaging
- Other services: Apple Music / YouTube Music adapters
- Streamer mode / overlay for Twitch/OBS

### Privacy & data
- OAuth tokens cached locally at `~/.spguess_token_cache`.
- High scores stored locally in `high_scores.json`.
- No analytics or external data collection.

### Contributing
Issues and PRs welcome. Ideas, UX tweaks, or bug reports are appreciated.

### License
TBD. If you plan to fork/distribute, choose a license and update this section.
