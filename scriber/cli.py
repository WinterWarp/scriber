"""Command-line entry point.

    scriber              launch the handwriting window
    scriber type-last    type the last recognized text into the focused window
                         (bind this to a GNOME shortcut for hands-free input;
                         requires ydotool — see the README)
"""

import sys


def _type_last() -> int:
    from . import config as cfg
    from .injectors.ydotool import YdotoolInjector

    text = cfg.read_last_text()
    if not text.strip():
        print("scriber: no saved text to type", file=sys.stderr)
        return 1
    injector = YdotoolInjector()
    ok, msg = injector.available()
    if not ok:
        print(f"scriber: {msg}", file=sys.stderr)
        return 1
    try:
        injector.send(text)
    except Exception as exc:  # noqa: BLE001
        print(f"scriber: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] == "type-last":
        return _type_last()
    from .app import run
    return run()
