VERBOSITY: int = 0  # 0=quiet, 1=normal verbose, 2=extreme
COLOR_ENABLED: bool = True

_COLORS = {
    "reset": "\033[0m",
    "info": "\033[36m",      # cyan
    "event": "\033[35m",     # magenta
    "success": "\033[32m",   # green
    "warn": "\033[33m",      # yellow
    "error": "\033[31m",     # red
}


def set_verbose(value: bool) -> None:
    """Backward-compat: True -> level 1, False -> 0."""
    set_verbosity(1 if value else 0)


def set_verbosity(level: int) -> None:
    global VERBOSITY
    VERBOSITY = max(0, int(level))


def set_color_enabled(value: bool) -> None:
    global COLOR_ENABLED
    COLOR_ENABLED = bool(value)


def _colorize(level: str, text: str) -> str:
    if not COLOR_ENABLED:
        return text
    start = _COLORS.get(level, "")
    end = _COLORS.get("reset", "")
    return f"{start}{text}{end}"


def debug(msg: str, level: str = "info", noise: int = 1) -> None:
    """Print a colored debug message if current verbosity >= noise.

    - noise=1: shown with -v and -vv (normal informative events)
    - noise=2: shown only with -vv (extreme/detail, can be spammy)
    """
    if VERBOSITY >= noise:
        tag = level.upper()
        print(_colorize(level, f"[{tag}] {msg}"))

