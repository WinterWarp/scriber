"""Optional delivery: type the text into the focused window via ydotool.

ydotool injects at the kernel uinput level, so it works on GNOME Wayland where
xdotool/wtype do not. It is DORMANT by default: it needs the ydotoold daemon
running with access to /dev/uinput. On NixOS enable it with:

    programs.ydotool.enable = true;

then `sudo nixos-rebuild switch` and re-log in. See the README.
"""

import os
import shutil
import subprocess

from .base import Injector, InjectionError


class YdotoolInjector(Injector):
    name = "ydotool"

    def __init__(self, binary: str = "ydotool"):
        self.binary = binary

    def available(self) -> tuple[bool, str]:
        if shutil.which(self.binary) is None:
            return False, "ydotool not found on PATH"
        socket = os.environ.get("YDOTOOL_SOCKET") or f"/run/user/{os.getuid()}/.ydotool_socket"
        if not os.path.exists(socket):
            return False, (
                "ydotoold daemon socket not found — enable programs.ydotool.enable "
                "(NixOS) and re-log in"
            )
        return True, ""

    def send(self, text: str) -> None:
        ok, msg = self.available()
        if not ok:
            raise InjectionError(msg)
        proc = subprocess.run(
            [self.binary, "type", "--", text],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise InjectionError(
                proc.stderr.strip() or "ydotool failed (is ydotoold running with uinput access?)"
            )
