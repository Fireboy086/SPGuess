import threading
import time
import random
from typing import Dict, List, Optional

import customtkinter as ctk

from guess_cli import is_correct_guess, evaluate_guess, guess_includes_artist, canonicalize_title
import difflib
from debug import debug


class SPGuessApp(ctk.CTk):
    def __init__(
        self,
        songs: List[Dict[str, str]],
        spotify_player,
        attempts_per_round: int = 3,
        lives: int = 3,
        seconds_base: float = 1.0,
        seconds_growth: float = 0.75,
        randomize_offset: bool = True,
        per_round_seconds: int = 60,
    ) -> None:
        super().__init__()
        self.title("SPGuess")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Game config
        self.songs = songs
        self.spotify_player = spotify_player
        self.attempts_per_round = attempts_per_round
        self.lives_total = lives
        self.seconds_base = seconds_base
        self.seconds_growth = seconds_growth
        self.randomize_offset = randomize_offset
        self.per_round_seconds = per_round_seconds
        self.time_limit_enabled = True
        self.inter_round_delay_ms = 1500

        # Game state
        self.lives_remaining = lives
        self.score_points = 0
        self.correct_count = 0
        self.total_rounds = 0
        self.current_song: Optional[Dict[str, str]] = None
        self.attempts_remaining = attempts_per_round
        self.round_start_monotonic: float = 0.0
        self.snippet_thread: Optional[threading.Thread] = None
        self.round_active = False
        # Suggestions state
        self.current_suggestions: List[str] = []
        self.suggestion_index: int = 0

        # High score
        self.best_score = 0
        self._scores_path = None

        # UI elements
        self._build_ui()
        self._show_start_screen()
        # Keep window on top at launch
        try:
            self.attributes("-topmost", True)
            self.after(1500, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _build_ui(self) -> None:
        pad = 10
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.status_label = ctk.CTkLabel(
            self,
            text="Welcome to SPGuess!",
            justify="center",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.status_label.grid(row=0, column=0, padx=pad, pady=(pad, 0))

        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.grid(row=1, column=0, sticky="ew", padx=pad, pady=pad)
        self.info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lives_var = ctk.StringVar(value="Lives: 3")
        self.lives_label = ctk.CTkLabel(self.info_frame, textvariable=self.lives_var)
        self.lives_label.grid(row=0, column=0, padx=pad, pady=pad)

        self.attempts_var = ctk.StringVar(value="Attempts: 3")
        self.attempts_label = ctk.CTkLabel(self.info_frame, textvariable=self.attempts_var)
        self.attempts_label.grid(row=0, column=1, padx=pad, pady=pad)

        self.timer_var = ctk.StringVar(value="Time: 60s")
        self.timer_label = ctk.CTkLabel(self.info_frame, textvariable=self.timer_var)
        self.timer_label.grid(row=0, column=2, padx=pad, pady=pad)

        self.score_var = ctk.StringVar(value="Points: 0")
        self.score_label = ctk.CTkLabel(self.info_frame, textvariable=self.score_var)
        self.score_label.grid(row=0, column=3, padx=pad, pady=pad)

        # Timer progress bar for visual polish
        self.timer_progress = ctk.CTkProgressBar(self.info_frame)
        self.timer_progress.grid(row=1, column=0, columnspan=4, padx=pad, pady=(0, pad), sticky="ew")
        self.timer_progress.set(1.0)

        self.entry = ctk.CTkEntry(self, placeholder_text="Type your guess (title, optionally artist)")
        self.entry.grid(row=2, column=0, sticky="ew", padx=pad)
        self.entry.bind("<Return>", lambda _: self._on_guess())
        self.entry.bind("<KeyRelease>", lambda _: self._update_suggestions())
        self.entry.bind("<Tab>", self._on_tab_complete)

        # Suggestion zone: scrollable, filtered list
        self.suggest_frame = ctk.CTkScrollableFrame(self, height=120)
        self.suggest_frame.grid(row=3, column=0, sticky="nsew", padx=pad, pady=(6, 0))
        self.suggest_header = ctk.CTkLabel(self.suggest_frame, text="Suggestions", anchor="w")
        self.suggest_header.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 6))
        self.suggest_items_container = ctk.CTkFrame(self.suggest_frame)
        self.suggest_items_container.grid(row=1, column=0, sticky="nsew")
        self.suggest_frame.grid_columnconfigure(0, weight=1)
        self.suggest_frame.grid_rowconfigure(1, weight=1)

        helper_text = (
            "Ways to answer: \n"
            "- Just title (e.g., Hellfire)\n"
            "- Title by Artist (e.g., Hellfire by Imagine Dragons)\n"
            "- Title - Artist (e.g., Hellfire - Imagine Dragons)\n"
            "Formatting inside (...) or after ' - ' is ignored."
        )
        self.helper = ctk.CTkLabel(self, text=helper_text, justify="left")
        self.helper.grid(row=5, column=0, padx=pad, pady=(0, pad), sticky="w")

        self.buttons_frame = ctk.CTkFrame(self)
        self.buttons_frame.grid(row=4, column=0, sticky="ew", padx=pad, pady=pad)
        self.buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.play_button = ctk.CTkButton(self.buttons_frame, text="Replay Snippet", command=self._on_replay)
        self.play_button.grid(row=0, column=0, padx=pad, pady=pad)

        self.guess_button = ctk.CTkButton(self.buttons_frame, text="Guess", command=self._on_guess)
        self.guess_button.grid(row=0, column=1, padx=pad, pady=pad)

        self.skip_button = ctk.CTkButton(self.buttons_frame, text="Skip", command=self._on_skip)
        self.skip_button.grid(row=0, column=2, padx=pad, pady=pad)

        self.quit_button = ctk.CTkButton(self, text="Quit", command=self._on_quit)
        self.quit_button.grid(row=6, column=0, padx=pad, pady=(0, pad))

    def _flash_result(self, success: bool) -> None:
        try:
            prev_fg = self.status_label.cget("fg_color")
        except Exception:
            prev_fg = "transparent"
        try:
            prev_text = self.status_label.cget("text_color")
        except Exception:
            prev_text = None
        color = "#2e7d32" if success else "#c62828"  # green / red
        self.status_label.configure(fg_color=color, text_color="white")
        self.after(450, lambda: self.status_label.configure(fg_color=prev_fg, text_color=prev_text))

    def _update_info_labels(self) -> None:
        self.lives_var.set(f"Lives: {self.lives_remaining}")
        self.attempts_var.set(f"Attempts: {self.attempts_remaining}")
        if self.time_limit_enabled and self.round_active:
            remaining = max(0, int(self.per_round_seconds - (time.monotonic() - self.round_start_monotonic)))
            self.timer_var.set(f"Time: {remaining}s")
            # Update progress bar
            if self.per_round_seconds > 0:
                frac = max(0.0, min(1.0, remaining / float(self.per_round_seconds)))
                self.timer_progress.set(frac)
        else:
            self.timer_var.set("Time: OFF")
            self.timer_progress.set(0.0)
        self.score_var.set(f"Points: {self.score_points}")

    def _start_new_round(self) -> None:
        if self.lives_remaining <= 0:
            self._end_game()
            return
        self.round_active = True
        self.current_song = random.choice(self.songs)
        self.attempts_remaining = self.attempts_per_round
        self.round_start_monotonic = time.monotonic()
        title = canonicalize_title(self.current_song.get("title", "")) if self.current_song else ""
        artist = (self.current_song or {}).get("artist", "")
        self.status_label.configure(text="Guess the song title!")
        debug(f"Round start → Selected: '{title}' by {artist}", level="event")
        self.entry.delete(0, "end")
        self.entry.configure(state="normal")
        self._update_info_labels()
        self.after(150, self._play_snippet_async)
        self.after(200, self._tick_timer)
        self._update_suggestions()
        debug("Started new round", noise=1)

    def _show_start_screen(self) -> None:
        top = ctk.CTkToplevel(self)
        top.title("Start Game")
        top.geometry("460x420")
        top.grab_set()
        try:
            top.attributes("-topmost", True)
        except Exception:
            pass

        ctk.CTkLabel(top, text="SPGuess – Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=12)

        # Random start checkbox
        self._rand_var = ctk.BooleanVar(value=self.randomize_offset)
        ctk.CTkCheckBox(top, text="Start at random position", variable=self._rand_var).pack(anchor="w", padx=16, pady=6)

        # Basic: attempts & lives
        basic_row = ctk.CTkFrame(top)
        basic_row.pack(fill="x", padx=12, pady=(6, 0))
        ctk.CTkLabel(basic_row, text="Attempts:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self._attempts_entry = ctk.CTkEntry(basic_row, width=80)
        self._attempts_entry.grid(row=0, column=1, padx=6, pady=6)
        self._attempts_entry.insert(0, str(int(self.attempts_per_round)))
        ctk.CTkLabel(basic_row, text="Lives:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self._lives_entry = ctk.CTkEntry(basic_row, width=80)
        self._lives_entry.grid(row=0, column=3, padx=6, pady=6)
        self._lives_entry.insert(0, str(int(self.lives_total)))

        # Time limit toggle and entry
        self._time_limit_enabled_var = ctk.BooleanVar(value=True)
        self._time_chk = ctk.CTkCheckBox(top, text="Enable per-round time limit", variable=self._time_limit_enabled_var)
        self._time_chk.pack(anchor="w", padx=16, pady=(12, 6))

        time_row = ctk.CTkFrame(top)
        time_row.pack(fill="x", padx=12)
        ctk.CTkLabel(time_row, text="Seconds:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self._time_entry = ctk.CTkEntry(time_row)
        self._time_entry.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        time_row.grid_columnconfigure(1, weight=1)
        self._time_entry.insert(0, str(int(self.per_round_seconds)))

        # Advanced settings toggle
        self._adv_var = ctk.BooleanVar(value=False)
        adv_toggle = ctk.CTkCheckBox(top, text="Show advanced settings", variable=self._adv_var, command=lambda: self._toggle_advanced(top))
        adv_toggle.pack(anchor="w", padx=16, pady=(12, 6))

        # Advanced frame (hidden by default)
        self._adv_frame = ctk.CTkFrame(top)
        # child widgets created in toggle handler on first show

        btn = ctk.CTkButton(top, text="Start", command=lambda: self._apply_start_settings(top))
        btn.pack(pady=16)

        # Prepare high score path and load
        from pathlib import Path as _Path
        self._scores_path = _Path(__file__).resolve().parent / "high_scores.json"
        self._load_high_score()

    def _apply_start_settings(self, top: ctk.CTkToplevel) -> None:
        self.randomize_offset = bool(self._rand_var.get())
        self.time_limit_enabled = bool(self._time_limit_enabled_var.get())
        try:
            secs = int(self._time_entry.get().strip())
            self.per_round_seconds = max(5, min(600, secs))
        except Exception:
            pass
        try:
            self.attempts_per_round = max(1, int(self._attempts_entry.get().strip()))
            self.lives_total = max(1, int(self._lives_entry.get().strip()))
            self.lives_remaining = self.lives_total
        except Exception:
            pass
        # Advanced
        try:
            if hasattr(self, "_base_entry"):
                self.seconds_base = max(0.2, float(self._base_entry.get().strip()))
            if hasattr(self, "_growth_entry"):
                self.seconds_growth = max(0.0, float(self._growth_entry.get().strip()))
            if hasattr(self, "_delay_entry"):
                self.inter_round_delay_ms = max(300, int(self._delay_entry.get().strip()))
        except Exception:
            pass
        top.destroy()
        # Init status labels based on settings
        self._update_info_labels()
        self._start_new_round()
        # Focus entry for quick typing
        self.after(50, lambda: self.entry.focus_set())

    def _toggle_advanced(self, top: ctk.CTkToplevel) -> None:
        show = bool(self._adv_var.get())
        if show:
            # populate if empty
            if not getattr(self, "_adv_built", False):
                row = ctk.CTkFrame(self._adv_frame)
                row.pack(fill="x", padx=12, pady=(0, 6))
                ctk.CTkLabel(row, text="Snippet base (s):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
                self._base_entry = ctk.CTkEntry(row, width=80)
                self._base_entry.grid(row=0, column=1, padx=6, pady=6)
                self._base_entry.insert(0, str(self.seconds_base))
                ctk.CTkLabel(row, text="Growth per attempt (s):").grid(row=0, column=2, padx=6, pady=6, sticky="w")
                self._growth_entry = ctk.CTkEntry(row, width=80)
                self._growth_entry.grid(row=0, column=3, padx=6, pady=6)
                self._growth_entry.insert(0, str(self.seconds_growth))

                row2 = ctk.CTkFrame(self._adv_frame)
                row2.pack(fill="x", padx=12, pady=(0, 6))
                ctk.CTkLabel(row2, text="Inter-round delay (ms):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
                self._delay_entry = ctk.CTkEntry(row2, width=100)
                self._delay_entry.grid(row=0, column=1, padx=6, pady=6)
                self._delay_entry.insert(0, str(self.inter_round_delay_ms))
                self._adv_built = True
            self._adv_frame.pack(fill="x", padx=12, pady=(0, 6))
        else:
            try:
                self._adv_frame.pack_forget()
            except Exception:
                pass

    def _load_high_score(self) -> None:
        try:
            if self._scores_path and self._scores_path.exists():
                import json as _json
                with self._scores_path.open("r", encoding="utf-8") as f:
                    data = _json.load(f)
                    self.best_score = int(data.get("best_score", 0))
        except Exception:
            self.best_score = 0

    def _save_high_score(self) -> None:
        try:
            if not self._scores_path:
                return
            import json as _json
            with self._scores_path.open("w", encoding="utf-8") as f:
                _json.dump({"best_score": self.best_score}, f)
        except Exception:
            pass

    def _end_game(self) -> None:
        self.round_active = False
        # Disable inputs
        self.entry.configure(state="disabled")
        self.play_button.configure(state="disabled")
        self.guess_button.configure(state="disabled")
        self.skip_button.configure(state="disabled")

        # Update high score BEFORE showing summary
        if self.score_points > self.best_score:
            self.best_score = self.score_points
            self._save_high_score()

        # End screen modal
        top = ctk.CTkToplevel(self)
        top.title("Session Summary")
        top.geometry("420x260")
        top.grab_set()

        acc = (self.correct_count / self.total_rounds * 100.0) if self.total_rounds else 0.0
        summary = (
            f"Rounds: {self.total_rounds}\n"
            f"Correct: {self.correct_count}\n"
            f"Points: {self.score_points}\n"
            f"Accuracy: {acc:.1f}%\n"
            f"Best: {self.best_score}"
        )
        ctk.CTkLabel(top, text="Game Over", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        ctk.CTkLabel(top, text=summary, justify="left").pack(pady=10)

        btn_frame = ctk.CTkFrame(top)
        btn_frame.pack(fill="x", pady=10, padx=10)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        def close_and_quit() -> None:
            top.destroy()
            self.destroy()

        def play_again() -> None:
            top.destroy()
            # Reset state
            self.lives_remaining = self.lives_total
            self.correct_count = 0
            self.total_rounds = 0
            self.score_points = 0
            self._start_new_round()

        ctk.CTkButton(btn_frame, text="Play Again", command=play_again).grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkButton(btn_frame, text="Quit", command=close_and_quit).grid(row=0, column=1, padx=8, pady=8)

    def _tick_timer(self) -> None:
        if not self.round_active:
            return
        if self.time_limit_enabled:
            remaining = self.per_round_seconds - (time.monotonic() - self.round_start_monotonic)
            if remaining <= 0:
                # Time's up -> fail round (not a skip)
                self.status_label.configure(text="Time's up for this round!")
                self._flash_result(False)
                self._finalize_round(success=False)
                return
        self._update_info_labels()
        # no timer-tick spam
        self.after(200, self._tick_timer)
        self._update_suggestions()

    def _on_replay(self) -> None:
        if self.round_active and self.attempts_remaining > 1:
            self.attempts_remaining -= 1
            self._update_info_labels()
            self._play_snippet_async()

    def _play_snippet_async(self) -> None:
        # Prevent overlapping snippets
        if self.snippet_thread and self.snippet_thread.is_alive():
            return

        def target() -> None:
            try:
                if not self.current_song:
                    return
                attempt_index = self.attempts_per_round - self.attempts_remaining
                seconds_this_attempt = max(0.5, self.seconds_base + self.seconds_growth * attempt_index)
                if self.time_limit_enabled:
                    # Respect remaining time
                    remaining = max(0.0, self.per_round_seconds - (time.monotonic() - self.round_start_monotonic))
                    if remaining <= 0:
                        return
                    play_seconds = min(seconds_this_attempt, max(0.5, remaining))
                else:
                    play_seconds = seconds_this_attempt
                duration_ms = int(self.current_song.get("duration_ms", 0))
                headroom_ms = int(max(0, (play_seconds + 0.5) * 1000))
                max_start = max(0, duration_ms - headroom_ms)
                start_ms = random.randint(0, max_start) if (self.randomize_offset and max_start > 0) else 0
                debug(f"Snippet → len={play_seconds:.2f}s start_ms={start_ms}", noise=2)
                self.spotify_player.play_track_for(self.current_song["uri"], seconds=play_seconds, start_ms=start_ms)
            except Exception:
                pass

        self.snippet_thread = threading.Thread(target=target, daemon=True)
        self.snippet_thread.start()
        debug("Snippet playback thread started", noise=2)

    def _on_guess(self) -> None:
        if not self.round_active or not self.current_song:
            return
        guess = self.entry.get().strip()
        self.entry.delete(0,"end")
        if guess.lower() in {"/quit", "/exit"}:
            self.destroy()
            return
        if guess.lower() in {"/skip", "/s", "/pass", "/next"}:
            self.status_label.configure(text="Round skipped.")
            self._flash_result(False)
            self._finalize_round(success=False)
            return

        ok, sim = evaluate_guess(guess, self.current_song["title"])
        if ok:
            base = 3 if guess_includes_artist(guess, self.current_song["artist"]) else 1
            self.score_points += base
            self.correct_count += 1
            ct = canonicalize_title(self.current_song['title'])
            self.status_label.configure(text=f"Correct! +{base} point(s). It was '{ct}' by {self.current_song['artist']}.")
            debug(f"Guess OK → input='{guess}' vs title='{ct}', sim={sim:.2f}, artist_included={'yes' if base==3 else 'no'}", level="success")
            self._flash_result(True)
            self._finalize_round(success=True)
            return

        # Wrong
        # Compute similarity for storytelling
        debug(f"Guess MISS → input='{guess}', sim={sim:.2f}", level="warn")
        self.attempts_remaining -= 1
        self._update_info_labels()
        if self.attempts_remaining > 0:
            self.status_label.configure(text="Not quite. Replaying snippet...")
            self._flash_result(False)
            self._play_snippet_async()
        else:
            self.status_label.configure(text=f"Out of attempts. It was '{canonicalize_title(self.current_song['title'])}' by {self.current_song['artist']}.")
            self._flash_result(False)
            self._finalize_round(success=False)

    def _on_skip(self) -> None:
        if self.round_active:
            self.status_label.configure(text="Round skipped.")
            self._finalize_round(success=False)

    def _on_quit(self) -> None:
        # Open summary then quit
        self._end_game()

    def _finalize_round(self, success: bool) -> None:
        if not self.round_active:
            return
        self.round_active = False
        self.total_rounds += 1
        if not success:
            self.lives_remaining -= 1
        self._update_info_labels()
        if self.lives_remaining <= 0:
            self._end_game()
            return
        # Next round after short pause
        self.after(self.inter_round_delay_ms, self._start_new_round)

    def _update_suggestions(self) -> None:
        try:
            text = self.entry.get().strip()
            debug(f"Typing → '{text}'", noise=2)
        except Exception:
            return
        # Clear items
        for w in getattr(self, "_suggest_item_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self._suggest_item_widgets = []
        if not text:
            self.current_suggestions = []
            self.suggestion_index = 0
            return
        # Build candidate list from songs (title and title - artist)
        candidates = []
        for s in self.songs:
            t = canonicalize_title(s.get("title", ""))
            a = s.get("artist", "")
            candidates.append(f"{t}")
            if a:
                candidates.append(f"{t} - {a}")
        # Fuzzy match
        matches = difflib.get_close_matches(text, candidates, n=50, cutoff=0.5)
        debug(f"Suggestions computed → {len(matches)} matches", noise=2)
        self.current_suggestions = matches
        self.suggestion_index = 0
        # Render buttons
        for idx, m in enumerate(matches):
            btn = ctk.CTkButton(self.suggest_items_container, text=m, anchor="w", command=lambda val=m: self._accept_suggestion(val))
            btn.grid(row=idx, column=0, sticky="ew", padx=6, pady=2)
            self._suggest_item_widgets.append(btn)

    def _accept_suggestion(self, value: str) -> None:
        try:
            self.entry.delete(0, "end")
            self.entry.insert(0, value)
            self.entry.icursor("end")
            self.entry.focus_set()
        except Exception:
            pass

    def _on_tab_complete(self, event) -> str:
        if not self.current_suggestions:
            return "break"
        try:
            value = self.current_suggestions[self.suggestion_index % len(self.current_suggestions)]
            self.suggestion_index += 1
            self.entry.delete(0, "end")
            self.entry.insert(0, value)
            self.entry.icursor("end")
        except Exception:
            return "break"
        return "break"


def run_ui(
    songs: List[Dict[str, str]],
    spotify_player,
    attempts_per_round: int = 3,
    lives: int = 3,
    seconds_base: float = 1.0,
    seconds_growth: float = 0.75,
    randomize_offset: bool = True,
    per_round_seconds: int = 60,
) -> None:
    app = SPGuessApp(
        songs=songs,
        spotify_player=spotify_player,
        attempts_per_round=attempts_per_round,
        lives=lives,
        seconds_base=seconds_base,
        seconds_growth=seconds_growth,
        randomize_offset=randomize_offset,
        per_round_seconds=per_round_seconds,
    )
    app.geometry("600x450") #4x3 * 150
    app.mainloop()

