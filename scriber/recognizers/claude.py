"""Cloud backend: send the rendered handwriting image to the Anthropic
Messages API and ask for a verbatim transcription.

Uses only the standard library (urllib) so it needs no extra Python deps.
Requires ANTHROPIC_API_KEY in the environment (or passed explicitly).
"""

import base64
import json
import os
import urllib.error
import urllib.request

from .base import Recognizer, RecognitionError

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You transcribe handwriting from images. Output only the transcribed text, "
    "verbatim, preserving the original line breaks. Do not add commentary, quotes, "
    "or markdown. If nothing is legible, output nothing."
)


class ClaudeRecognizer(Recognizer):
    name = "claude"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = 1024):
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens

    def available(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY is not set"
        return True, ""

    def recognize(self, png_bytes: bytes) -> str:
        ok, msg = self.available()
        if not ok:
            raise RecognitionError(msg)

        image_b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # Static instruction is cache-friendly; mark it for prompt caching.
            "system": [
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": "Transcribe the handwriting."},
                    ],
                }
            ],
        }

        req = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RecognitionError(f"Anthropic API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RecognitionError(f"Network error reaching Anthropic: {exc.reason}") from exc

        parts = [
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        ]
        return "".join(parts).strip()
