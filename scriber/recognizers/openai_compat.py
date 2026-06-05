"""OpenAI-compatible backend — works with OpenRouter, OpenAI, Groq, Together,
or a local llama.cpp / LM Studio server.

Uses the Chat Completions API with vision (`image_url`) content, which is what
OpenRouter speaks (unlike Anthropic's native Messages API used by claude.py).
Standard library only — no extra Python deps.

Defaults target OpenRouter. The API key is read from the environment variable
named by `api_key_env` (default OPENROUTER_API_KEY) so secrets stay out of the
config file. For a local server, point `base_url` at it; a key is then optional.
"""

import base64
import json
import os
import urllib.error
import urllib.request

from .base import Recognizer, RecognitionError

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
DEFAULT_KEY_ENV = "OPENROUTER_API_KEY"

SYSTEM_PROMPT = (
    "You transcribe handwriting from images. Output only the transcribed text, "
    "verbatim, preserving the original line breaks. Do not add commentary, quotes, "
    "or markdown. If nothing is legible, output nothing."
)


def _is_local(url: str) -> bool:
    return any(host in url for host in ("localhost", "127.0.0.1", "0.0.0.0"))


class OpenAICompatRecognizer(Recognizer):
    name = "openai"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        max_tokens: int = 1024,
        title: str = "Scriber",
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.api_key_env = api_key_env or DEFAULT_KEY_ENV
        self.api_key = api_key or os.environ.get(self.api_key_env)
        self.max_tokens = max_tokens
        self.title = title

    def available(self) -> tuple[bool, str]:
        if not self.api_key and not _is_local(self.base_url):
            return False, f"{self.api_key_env} is not set"
        return True, ""

    def recognize(self, png_bytes: bytes) -> str:
        ok, msg = self.available()
        if not ok:
            raise RecognitionError(msg)

        image_b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe the handwriting."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        # Optional OpenRouter attribution headers (harmless to other servers).
        headers["X-Title"] = self.title

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RecognitionError(f"API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RecognitionError(f"Network error reaching {self.base_url}: {exc.reason}") from exc

        return _extract_text(payload)


def _extract_text(payload: dict) -> str:
    """Pull the assistant text out of an OpenAI-style chat completion response."""
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        err = payload.get("error") if isinstance(payload, dict) else None
        if err:
            raise RecognitionError(str(err.get("message", err) if isinstance(err, dict) else err))
        raise RecognitionError("unexpected response shape (no choices)")
    content = message.get("content", "")
    if isinstance(content, list):  # some providers return content as parts
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return (content or "").strip()
