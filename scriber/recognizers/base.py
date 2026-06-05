class RecognitionError(Exception):
    """Raised when a backend cannot produce a result."""


class Recognizer:
    name = "base"

    def available(self) -> tuple[bool, str]:
        """Return (ok, message). message explains why it's unavailable when ok is False."""
        return True, ""

    def recognize(self, png_bytes: bytes) -> str:
        raise NotImplementedError
