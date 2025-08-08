VERBOSE: bool = False
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
    global VERBOSE
    VERBOSE = bool(value)


def set_color_enabled(value: bool) -> None:
    global COLOR_ENABLED
    COLOR_ENABLED = bool(value)


def _colorize(level: str, text: str) -> str:
    if not COLOR_ENABLED:
        return text
    start = _COLORS.get(level, "")
    end = _COLORS.get("reset", "")
    return f"{start}{text}{end}"


def debug(msg: str, level: str = "info") -> None:
    if VERBOSE:
        tag = level.upper()
        print(_colorize(level, f"[{tag}] {msg}"))

