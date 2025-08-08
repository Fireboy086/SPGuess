import json
import difflib
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple


# Songs are now sourced from Spotify. Use the launcher to start the game.


def normalize_title(value: str) -> str:
    """Normalize text for lenient matching: lowercase, strip punctuation, collapse spaces."""
    lowered = value.lower()
    stripped = re.sub(r"[^a-z0-9\s]", "", lowered)
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed


def guess_contains_title(guess: str, correct_title: str) -> bool:
    """Return True if the normalized guess contains the canonical title as a distinct token span."""
    ng = normalize_title(guess)
    nt = normalize_title(canonicalize_title(correct_title))
    if not nt:
        return False
    if ng == nt:
        return True
    # Word-boundary style containment (spaces are single due to normalization)
    pattern = rf"(?:^| ){re.escape(nt)}(?:$| )"
    return re.search(pattern, ng) is not None


def is_correct_guess(guess: str, correct_title: str) -> bool:
    """Lenient match: equality/containment or fuzzy similarity (minor mistakes count)."""
    if guess_contains_title(guess, correct_title):
        return True
    ng = normalize_title(guess)
    nt = normalize_title(canonicalize_title(correct_title))
    if not ng or not nt:
        return False
    ratio = difflib.SequenceMatcher(None, ng, nt).ratio()
    return ratio >= 0.85


def canonicalize_title(raw_title: str) -> str:
    """Reduce track titles to their base form for fair matching/display.

    Rules:
    - Remove any parenthetical segments: (...)
    - Remove any suffix after " - " (dash with spaces)
    - Trim leading/trailing dashes, quotes, underscores, and extra spaces
    """
    # Remove parenthetical content (can occur multiple times)
    no_paren = re.sub(r"\s*\([^)]*\)", "", raw_title)
    # Split by ' - ' and take the first non-empty segment
    parts = [p.strip() for p in no_paren.split(" - ")]
    base = ""
    for p in parts:
        if p:
            base = p
            break
    if not base:
        base = no_paren
    # Clean leading/trailing punctuation/dashes and normalize spaces
    base = base.strip(" -–—_\"' ")
    base = re.sub(r"\s{2,}", " ", base).strip()
    return base


def normalize_artist(value: str) -> str:
    return normalize_title(value)


def guess_includes_artist(guess: str, artist: str) -> bool:
    """Check whether the user's guess mentions any of the artist names."""
    norm_guess = normalize_title(guess)
    # Split multiple artists by comma, ampersand, or 'feat'
    tokens = re.split(r",|&|feat\.?|with|x", artist, flags=re.IGNORECASE)
    for token in tokens:
        token_norm = normalize_artist(token).strip()
        if token_norm and token_norm in norm_guess:
            return True
    # Fallback: full artist string
    return normalize_artist(artist) in norm_guess


def play_round(
    songs: List[Dict[str, str]],
    seconds_base: float = 1.0,
    seconds_growth: float = 0.5,
    spotify_player=None,
    attempts_per_round: int = 3,
    randomize_offset: bool = True,
    per_round_seconds: int = 45,
) -> Tuple[bool, int]:
    """Run a single round.

    Returns (guessed_correctly, points_earned).
    Points: 3 if title correct and artist mentioned in guess, else 1 for title only.
    """
    song = random.choice(songs)
    title = song["title"]
    artist = song["artist"]

    attempts_remaining = attempts_per_round

    print("\n---===### GUESS THE SONG ###===---")
    print("You get a short audio snippet. Guess the title. Type 'skip' to forfeit the round or 'quit' to exit.")
    print(f"Round timer: {per_round_seconds}s")

    round_start = time.monotonic()
    while attempts_remaining > 0:
        # Play/replay snippet each attempt, slightly longer each time (cool bonus)
        if spotify_player and song.get("uri"):
            attempt_index = attempts_per_round - attempts_remaining  # 0-based
            seconds_this_attempt = max(0.5, seconds_base + seconds_growth * attempt_index)
            # Respect remaining round time
            elapsed = time.monotonic() - round_start
            remaining = max(0.0, per_round_seconds - elapsed)
            if remaining <= 0:
                print("Time's up for this round!")
                print(f"Out of time. The correct answer was '{title}' by {artist}.")
                return False, 0
            play_seconds = min(seconds_this_attempt, max(0.5, remaining))

            # Randomize start position within track duration minus snippet length (safe margin)
            duration_ms = int(song.get("duration_ms", 0))
            # Keep a 2s headroom to avoid ending right away, clamp to >= 0
            headroom_ms = int(max(0, (play_seconds + 0.5) * 1000))
            max_start = max(0, duration_ms - headroom_ms)
            start_ms = random.randint(0, max_start) if (randomize_offset and max_start > 0) else 0
            spotify_player.play_track_for(song["uri"], seconds=play_seconds, start_ms=start_ms)

        # Update remaining time display
        elapsed = time.monotonic() - round_start
        remaining = max(0.0, per_round_seconds - elapsed)
        approx_remaining = int(remaining)
        print(f"Attempts left: {attempts_remaining} | Time left: ~{approx_remaining}s. Your guess (or 'quit'): ")
        guess = input("> ")
        if guess.strip().lower() == "quit":
            raise KeyboardInterrupt  # Signal outer loop to end gracefully
        if guess.strip().lower() in {"skip", "s", "pass", "next"}:
            print("You skipped this round.")
            return False, 0

        if is_correct_guess(guess, title):
            print("-=# RESULT #=-")
            print(f"Correct! It was '{canonicalize_title(title)}' by {artist}.")
            points = 3 if guess_includes_artist(guess, artist) else 1
            if points == 3:
                print("Bonus: You included the artist!")
            return True, points

        attempts_remaining -= 1
        if attempts_remaining > 0:
            print("Not quite. Replaying the snippet...")

    print("-=# RESULT #=-")
    print(f"Out of attempts. The correct answer was '{canonicalize_title(title)}' by {artist}.")
    return False, 0


def run_game(
    songs: List[Dict[str, str]],
    spotify_player=None,
    attempts_per_round: int = 3,
    lives: int = 3,
    seconds_base: float = 1.0,
    seconds_growth: float = 0.75,
    randomize_offset: bool = True,
    per_round_seconds: int = 45,
) -> None:
    print("---===### SPGuess (CLI Prototype) ###===---")
    print("Guess the song title. Case and punctuation don't matter. Type 'quit' anytime.")
    print(f"You have {attempts_per_round} attempts per round and {lives} lives per game. Failing a round costs 1 life.")

    total_rounds = 0
    correct_count = 0
    score_points = 0
    current_streak = 0
    lives_remaining = lives

    # High score handling
    scores_path = Path(__file__).resolve().parent / "high_scores.json"
    best_score = 0
    try:
        if scores_path.exists():
            with scores_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                best_score = int(data.get("best_score", 0))
    except Exception:
        best_score = 0

    try:
        while lives_remaining > 0:
            try:
                was_correct, earned = play_round(
                    songs,
                    seconds_base=seconds_base,
                    seconds_growth=seconds_growth,
                    spotify_player=spotify_player,
                    attempts_per_round=attempts_per_round,
                    randomize_offset=randomize_offset,
                    per_round_seconds=per_round_seconds,
                )
            except KeyboardInterrupt:
                break

            total_rounds += 1
            if was_correct:
                correct_count += 1
                streak_bonus = 1 if current_streak >= 1 else 0
                round_points = earned + streak_bonus
                score_points += round_points
                current_streak += 1
                if streak_bonus:
                    print(f"Points this round: +{earned} (+{streak_bonus} streak) | Total: {score_points}")
                else:
                    print(f"Points this round: +{earned} | Total: {score_points}")
            else:
                lives_remaining -= 1
                print(f"Life lost! Lives remaining: {lives_remaining}")
                current_streak = 0
    finally:
        print("\n---===### SESSION SUMMARY ###===---")
        print(f"Rounds played: {total_rounds}")
        print(f"Correct guesses: {correct_count}")
        print(f"Total points: {score_points}")
        print(f"Lives remaining: {lives_remaining}")
        if total_rounds:
            accuracy = (correct_count / total_rounds) * 100
            print(f"Accuracy: {accuracy:.1f}%")
        # High score update
        try:
            if score_points > best_score:
                print("New high score! 🏆")
                with scores_path.open("w", encoding="utf-8") as f:
                    json.dump({"best_score": score_points}, f)
            else:
                print(f"Best score to beat: {best_score}")
        except Exception:
            pass
        print("Goodbye!")


def main() -> None:
    print("Please run the game via 'launch.py' after configuring Spotify credentials.")


if __name__ == "__main__":
    main()

