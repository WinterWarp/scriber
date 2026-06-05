"""Headless smoke test — run inside the dev shell:

    nix develop -c python tests/smoke.py

Validates: GTK4 bindings import, Cairo PNG export, the Tesseract backend end to
end (renders real text and OCRs it back), and that the full widget tree builds.
Does NOT open a visible window.
"""

import io
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
import cairo  # noqa: E402

from scriber.canvas import Canvas  # noqa: E402
from scriber.recognizers.tesseract import TesseractRecognizer  # noqa: E402


def _render_text_png(text: str) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 480, 140)
    cr = cairo.Context(surface)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.set_source_rgb(0, 0, 0)
    cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(64)
    cr.move_to(20, 95)
    cr.show_text(text)
    surface.flush()
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def test_export_png():
    canvas = Canvas()
    canvas.strokes = [[(10, 10), (40, 40), (80, 10)], [(100, 20), (120, 60)]]
    png = canvas.export_png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "export_png did not produce a PNG"
    print("ok  export_png ->", len(png), "bytes")


def test_tesseract_pipeline():
    rec = TesseractRecognizer(psm=7)
    ok, msg = rec.available()
    assert ok, f"tesseract unavailable: {msg}"
    result = rec.recognize(_render_text_png("Hello"))
    print(f"ok  tesseract recognized: {result!r}")
    assert "Hello" in result or "hello" in result.lower(), f"unexpected OCR result: {result!r}"


_app_counter = 0


def _make_window():
    global _app_counter
    from scriber import config as cfg
    from scriber.app import ScriberWindow

    Gtk.init()
    _app_counter += 1
    app = Gtk.Application(application_id=f"org.scriber.SmokeTest{_app_counter}")
    app.register(None)
    return ScriberWindow(app, dict(cfg.DEFAULTS))  # build full tree; do not present


def test_window_builds():
    win = _make_window()
    assert win.canvas is not None
    print("ok  window/widget tree builds")


def test_model_field_ui():
    win = _make_window()
    # Tesseract (default): model field hidden
    assert win.model_row.get_visible() is False, "model field should hide for Tesseract"

    # Switch to OpenRouter/OpenAI (index 2): field shows, pre-filled from config
    win.engine_dd.set_selected(2)
    assert win.conf["engine"] == "openai"
    assert win.model_row.get_visible() is True
    assert win.model_entry.get_text() == win.conf["openai_model"]

    # Edit the slug in the UI -> config updates
    win.model_entry.set_text("anthropic/claude-opus-4.8")
    assert win.conf["openai_model"] == "anthropic/claude-opus-4.8"

    # Switch to Claude: field rebinds to the Claude model
    win.engine_dd.set_selected(1)
    assert win.conf["engine"] == "claude"
    assert win.model_entry.get_text() == win.conf["claude_model"]
    win.model_entry.set_text("claude-sonnet-4-6")
    assert win.conf["claude_model"] == "claude-sonnet-4-6"
    # ...and the OpenRouter slug we set earlier is preserved
    assert win.conf["openai_model"] == "anthropic/claude-opus-4.8"

    # Back to Tesseract: hidden again
    win.engine_dd.set_selected(0)
    assert win.model_row.get_visible() is False
    print("ok  model field shows/edits/rebinds per engine")


if __name__ == "__main__":
    failures = 0
    for test in (test_export_png, test_tesseract_pipeline, test_window_builds, test_model_field_ui):
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print("---")
    print("all passed" if failures == 0 else f"{failures} test(s) failed")
    sys.exit(1 if failures else 0)
