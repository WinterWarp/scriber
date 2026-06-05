"""Pluggable text-delivery backends (how recognized text reaches the target app)."""

from .base import Injector, InjectionError
from .clipboard import ClipboardInjector
from .ydotool import YdotoolInjector

__all__ = [
    "Injector",
    "InjectionError",
    "ClipboardInjector",
    "YdotoolInjector",
    "make_injector",
]


def make_injector(cfg: dict, display=None) -> Injector:
    if cfg.get("input_method") == "ydotool":
        return YdotoolInjector()
    return ClipboardInjector(display=display)
