"""Configuration: load/save a flat TOML at ~/.config/scriber/config.toml,
plus a tiny cache file holding the last recognized text (for `scriber type-last`)."""

import os
import tomllib

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
_CACHE_HOME = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")

CONFIG_DIR = os.path.join(_CONFIG_HOME, "scriber")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")
CACHE_DIR = os.path.join(_CACHE_HOME, "scriber")
LAST_TEXT_PATH = os.path.join(CACHE_DIR, "last.txt")

DEFAULTS = {
    # recognition
    "engine": "tesseract",            # "tesseract" | "claude" | "openai"
    "tesseract_lang": "eng",
    "tesseract_psm": 7,               # 7 = single text line; 6 = uniform block
    "claude_model": "claude-haiku-4-5-20251001",
    # "openai" engine: OpenAI-compatible (OpenRouter by default, also OpenAI / local)
    "openai_base_url": "https://openrouter.ai/api/v1",
    "openai_model": "anthropic/claude-sonnet-4.5",
    "openai_api_key_env": "OPENROUTER_API_KEY",
    # text delivery
    "input_method": "clipboard",      # "clipboard" | "ydotool"
    "append_space": True,             # add a trailing space when auto-typing
    "autotype_delay": 1.2,            # seconds of countdown before auto-typing
    # canvas / behaviour
    "guide_lines": True,
    "stroke_width": 3.0,
    "append": False,                  # accumulate successive recognitions
    # compact mode: a small, stripped-down window for writing alongside your
    # target app (handy with auto-type). always_on_top is best-effort (see app.py).
    "compact": False,
    "always_on_top": True,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        return cfg
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"scriber: ignoring bad config {CONFIG_PATH}: {exc}")
        return cfg
    for key in DEFAULTS:
        if key in data:
            cfg[key] = data[key]
    return cfg


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def save(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lines = ["# Scriber configuration (flat key = value)", ""]
    for key in DEFAULTS:
        lines.append(f"{key} = {_toml_value(cfg.get(key, DEFAULTS[key]))}")
    with open(CONFIG_PATH, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_last_text(text: str) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(LAST_TEXT_PATH, "w") as fh:
            fh.write(text)
    except OSError:
        pass


def read_last_text() -> str:
    try:
        with open(LAST_TEXT_PATH) as fh:
            return fh.read()
    except OSError:
        return ""
