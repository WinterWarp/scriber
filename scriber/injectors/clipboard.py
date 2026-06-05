"""Default delivery: put text on the clipboard; the user pastes with Ctrl+V.

Prefers the in-process GTK clipboard (no external binary). Because the app keeps
running, that content stays available for pasting. Falls back to wl-copy (Wayland)
or xclip (X11) so the text survives even after the app closes.
"""

import shutil
import subprocess

from .base import Injector, InjectionError


class ClipboardInjector(Injector):
    name = "clipboard"

    def __init__(self, display=None):
        self.display = display  # a Gdk.Display, when called from the GUI

    def send(self, text: str) -> None:
        if self.display is not None:
            try:
                self.display.get_clipboard().set(text)
                return
            except Exception:
                pass  # fall through to an external tool

        if shutil.which("wl-copy"):
            subprocess.run(["wl-copy", "--"], input=text.encode("utf-8"), check=False)
            return
        if shutil.which("xclip"):
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=False,
            )
            return
        raise InjectionError("no clipboard mechanism available (need GTK display, wl-copy, or xclip)")
