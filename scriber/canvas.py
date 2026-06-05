"""The writing surface: a GtkDrawingArea that captures pen/mouse strokes,
renders them with smoothing, and exports a clean PNG for recognition.

Strokes are captured with a GestureDrag, which fires for stylus, touch, and
mouse alike — so it works with or without a tablet.
"""

import io

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
import cairo  # noqa: E402


class Canvas(Gtk.DrawingArea):
    def __init__(self, stroke_width: float = 3.0, guide_lines: bool = True, on_stroke_finished=None):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_height(260)

        self.strokes: list[list[tuple[float, float]]] = []
        self._current: list[tuple[float, float]] | None = None
        self._start = (0.0, 0.0)

        self.stroke_width = stroke_width
        self.guide_lines = guide_lines
        self.on_stroke_finished = on_stroke_finished

        self.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.set_button(1)  # primary: pen tip / left mouse / touch
        drag.connect("drag-begin", self._on_begin)
        drag.connect("drag-update", self._on_update)
        drag.connect("drag-end", self._on_end)
        self.add_controller(drag)

    # ---- stroke capture -------------------------------------------------
    def _on_begin(self, _gesture, x, y):
        self._start = (x, y)
        self._current = [(x, y)]
        self.strokes.append(self._current)
        self.queue_draw()

    def _on_update(self, _gesture, off_x, off_y):
        if self._current is None:
            return
        self._current.append((self._start[0] + off_x, self._start[1] + off_y))
        self.queue_draw()

    def _on_end(self, gesture, off_x, off_y):
        self._on_update(gesture, off_x, off_y)
        self._current = None
        if self.on_stroke_finished:
            self.on_stroke_finished()

    # ---- editing --------------------------------------------------------
    def clear(self):
        self.strokes = []
        self._current = None
        self.queue_draw()

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.queue_draw()

    def is_empty(self) -> bool:
        return not any(self.strokes)

    # ---- rendering ------------------------------------------------------
    @staticmethod
    def _trace(cr, points):
        """Trace a smoothed path through points using midpoint quadratics."""
        if not points:
            return
        if len(points) == 1:
            x, y = points[0]
            cr.move_to(x, y)
            cr.line_to(x + 0.01, y)  # a dot
            return
        cr.move_to(*points[0])
        for i in range(1, len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            mid = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
            # quadratic (control = point i) expressed as a cubic
            cr.curve_to(x0, y0, x0, y0, *mid)
        cr.line_to(*points[-1])

    def _draw(self, _area, cr, width, height):
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

        if self.guide_lines:
            cr.set_source_rgb(0.85, 0.88, 0.95)
            cr.set_line_width(1)
            step = height / 4.0
            for i in range(1, 4):
                y = step * i
                cr.move_to(0, y)
                cr.line_to(width, y)
                cr.stroke()

        cr.set_source_rgb(0.05, 0.05, 0.08)
        cr.set_line_width(self.stroke_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for stroke in self.strokes:
            self._trace(cr, stroke)
            cr.stroke()

    # ---- export ---------------------------------------------------------
    def export_png(self, scale: float = 2.0, pad: int = 24) -> bytes:
        """Render just the written content (cropped + padded) to PNG bytes:
        black strokes on white, upscaled, which is what the recognizers want."""
        points = [p for stroke in self.strokes for p in stroke]
        if not points:
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 8, 8)
            cr = cairo.Context(surface)
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            return _surface_png(surface)

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max(int((max_x - min_x + 2 * pad) * scale), 8)
        height = max(int((max_y - min_y + 2 * pad) * scale), 8)

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

        cr.scale(scale, scale)
        cr.translate(-min_x + pad, -min_y + pad)
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(self.stroke_width * 1.3)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for stroke in self.strokes:
            self._trace(cr, stroke)
            cr.stroke()

        return _surface_png(surface)


def _surface_png(surface) -> bytes:
    surface.flush()
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()
