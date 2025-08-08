VERBOSE: bool = False


def set_verbose(value: bool) -> None:
    global VERBOSE
    VERBOSE = bool(value)


def debug(msg: str) -> None:
    if VERBOSE:
        print(f"[DEBUG] {msg}")

