"""Offline backend: shell out to the `tesseract` binary.

Tesseract is image-based OCR built for printed text. It does best on tidy,
well-separated block letters; cursive is hard for it. For higher accuracy
switch to the Claude backend.
"""

import os
import shutil
import subprocess
import tempfile

from .base import Recognizer, RecognitionError


class TesseractRecognizer(Recognizer):
    name = "tesseract"

    def __init__(self, lang: str = "eng", psm: int = 7, oem: int = 1, binary: str = "tesseract"):
        self.lang = lang
        self.psm = psm
        self.oem = oem
        self.binary = binary

    def available(self) -> tuple[bool, str]:
        if shutil.which(self.binary) is None:
            return False, "tesseract not found on PATH"
        return True, ""

    def recognize(self, png_bytes: bytes) -> str:
        ok, msg = self.available()
        if not ok:
            raise RecognitionError(msg)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_bytes)
            path = tmp.name
        try:
            cmd = [
                self.binary, path, "stdout",
                "--oem", str(self.oem),
                "--psm", str(self.psm),
                "-l", self.lang,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RecognitionError(proc.stderr.strip() or "tesseract failed")
            return proc.stdout.strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
