"""Pluggable handwriting-recognition backends.

A backend takes PNG bytes (a rendered image of the strokes) and returns text.
Add a new engine by subclassing Recognizer and wiring it into make_recognizer().
"""

from .base import Recognizer, RecognitionError
from .tesseract import TesseractRecognizer
from .claude import ClaudeRecognizer
from .openai_compat import OpenAICompatRecognizer

__all__ = [
    "Recognizer",
    "RecognitionError",
    "TesseractRecognizer",
    "ClaudeRecognizer",
    "OpenAICompatRecognizer",
    "make_recognizer",
]


def make_recognizer(cfg: dict) -> Recognizer:
    engine = cfg.get("engine", "tesseract")
    if engine == "claude":
        return ClaudeRecognizer(model=cfg.get("claude_model"))
    if engine in ("openai", "openrouter"):
        return OpenAICompatRecognizer(
            base_url=cfg.get("openai_base_url"),
            model=cfg.get("openai_model"),
            api_key_env=cfg.get("openai_api_key_env"),
        )
    return TesseractRecognizer(
        lang=cfg.get("tesseract_lang", "eng"),
        psm=int(cfg.get("tesseract_psm", 7)),
    )
