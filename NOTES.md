## Next Gamemode: Karaoke Match

Goal: A random song plays from your liked tracks. You must sing the current lyric line. We transcribe your mic audio with Whisper and match it to the lyric line at the current timestamp.

Flow
- Start: pick a random liked track, choose a random offset, start playback.
- Capture mic during snippet window (e.g., 3–6s) while audio plays.
- Transcribe mic audio with Whisper/faster-whisper (local). Alternative: Vosk (offline) for lower resource use.
- Fetch time-synced lyrics from LRCLIB and pick the target line based on Spotify progress_ms.
- Compare transcript vs target lyric using fuzzy metrics (normalized Levenshtein, word error rate). Accept above threshold.
- Scoring: base points for match, bonus for higher similarity and on-beat timing; streak multipliers.

Tech/Implementation
- Mic capture: sounddevice or pyaudio; save to WAV; basic VAD (webrtcvad) to trim silence.
- Transcription: faster-whisper (GPU if available) or tiny/base Whisper model for speed.
- Lyrics: LRCLIB wrapper (already prototyped in test_snippet) returning [(ms, text)].
- Alignment: pick line where line_ms ≤ progress_ms < next_line_ms; allow ±500–1000ms slack.
- Similarity: use rapidfuzz (token_set_ratio) + word error rate; configurable thresholds.
- UI: new mode screen with mic level meter, live countdown, and result banner (Matched/Missed + score).

Settings
- Toggle random start vs from-beginning.
- Snippet length per attempt and number of attempts.
- Time limit on round; mic record window.
- Model selection (whisper-tiny/base vs faster-whisper) and language.

Risks/Notes
- Ensure playback doesn’t leak into mic (use headphones / echo cancellation if possible).
- Latency: keep total round latency < 1–2s; preload Whisper model.
- Lyrics availability varies; fallback to unsynced lyrics -> line-level match may be approximate.
- Respect API ToS; LRCLIB is community-driven.

Stretch Ideas
- Duet/party mode with multiple mics.
- Pitch detection (librosa/crepe) for bonus accuracy on melody.
- Leaderboards and weekly challenges using fixed song seeds.

