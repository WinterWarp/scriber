"""GTK4 application + main window."""

import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib  # noqa: E402

from . import config as cfg  # noqa: E402
from .canvas import Canvas  # noqa: E402
from .injectors import ClipboardInjector, YdotoolInjector  # noqa: E402
from .recognizers import make_recognizer  # noqa: E402

APP_ID = "org.scriber.Scriber"

NORMAL_SIZE = (760, 480)
COMPACT_SIZE = (420, 250)


class ScriberWindow(Gtk.ApplicationWindow):
    def __init__(self, app, conf):
        super().__init__(application=app, title="Scriber")
        self.app = app
        self.conf = conf
        self._auto_timer = None
        self._on_top = False
        self._sync_compact = False  # guards programmatic compact_toggle updates
        self.set_default_size(760, 480)
        self._build_ui()
        self._install_shortcuts()
        # Open straight into compact mode if that was the saved default. The
        # window isn't mapped yet, so size via set_default_size and skip the
        # runtime resize dance.
        if bool(self.conf.get("compact", False)):
            self.set_default_size(*COMPACT_SIZE)
            self._apply_compact(True, resize=False, apply_on_top=False)
            # The window has no surface yet; pin it once it's mapped.
            self.connect("map", self._on_map_pin)

    # ---- UI construction ------------------------------------------------
    def _build_ui(self):
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        recognize_btn = Gtk.Button(label="Recognize")
        recognize_btn.add_css_class("suggested-action")
        recognize_btn.set_tooltip_text("Recognize handwriting (Ctrl+Enter)")
        recognize_btn.connect("clicked", lambda _b: self.recognize())
        header.pack_start(recognize_btn)

        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_popover(self._build_settings_popover())
        header.pack_end(menu_btn)

        self.compact_toggle = Gtk.ToggleButton(icon_name="view-restore-symbolic")
        self.compact_toggle.set_tooltip_text("Compact mode — small window for writing alongside your app (Ctrl+M)")
        self.compact_toggle.connect("toggled", self._on_compact_toggled)
        header.pack_end(self.compact_toggle)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for setter in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(root, setter)(8)
        self.set_child(root)
        self._root = root

        # toolbar
        self.toolbar = toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", lambda _b: self.canvas.clear())
        undo_btn = Gtk.Button(label="Undo stroke")
        undo_btn.connect("clicked", lambda _b: self.canvas.undo())
        self.auto_toggle = Gtk.ToggleButton(label="Auto")
        self.auto_toggle.set_tooltip_text("Recognize automatically a moment after you stop writing")
        self.append_toggle = Gtk.ToggleButton(label="Append")
        self.append_toggle.set_tooltip_text("Add each recognition to the existing text")
        self.append_toggle.set_active(bool(self.conf.get("append")))
        for w in (clear_btn, undo_btn, self.auto_toggle, self.append_toggle):
            toolbar.append(w)
        root.append(toolbar)

        # canvas
        self.canvas = Canvas(
            stroke_width=float(self.conf.get("stroke_width", 3.0)),
            guide_lines=bool(self.conf.get("guide_lines", True)),
            on_stroke_finished=self._on_stroke_finished,
        )
        canvas_frame = Gtk.Frame()
        canvas_frame.set_vexpand(True)
        canvas_frame.set_child(self.canvas)
        root.append(canvas_frame)

        # recognized text (editable)
        self.buffer = Gtk.TextBuffer()
        textview = Gtk.TextView(buffer=self.buffer)
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        textview.set_top_margin(4)
        textview.set_left_margin(6)
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(72)
        scroller.set_max_content_height(140)
        scroller.set_child(textview)
        self.text_frame = text_frame = Gtk.Frame()
        text_frame.set_child(scroller)
        root.append(text_frame)

        # actions
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.status = Gtk.Label(label="Write above, then Recognize (Ctrl+Enter)")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        self.status.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self.status.add_css_class("dim-label")
        self.clear_text_btn = clear_text_btn = Gtk.Button(label="Clear text")
        clear_text_btn.connect("clicked", lambda _b: self.buffer.set_text("", -1))
        type_btn = Gtk.Button(label="Auto-type")
        type_btn.connect("clicked", lambda _b: self.do_autotype())
        copy_btn = Gtk.Button(label="Copy")
        copy_btn.add_css_class("suggested-action")
        copy_btn.connect("clicked", lambda _b: self.do_copy())
        actions.append(self.status)
        for w in (clear_text_btn, type_btn, copy_btn):
            actions.append(w)
        root.append(actions)

    def _build_settings_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for setter in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(box, setter)(12)

        def labelled(text, widget):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lab = Gtk.Label(label=text)
            lab.set_xalign(0)
            lab.set_hexpand(True)
            row.append(lab)
            row.append(widget)
            return row

        self.engine_dd = Gtk.DropDown.new_from_strings(
            ["Tesseract (offline)", "Claude (Anthropic)", "OpenRouter / OpenAI-compatible"]
        )
        self.engine_dd.set_selected({"claude": 1, "openai": 2}.get(self.conf.get("engine"), 0))
        self.engine_dd.connect("notify::selected", self._on_engine_changed)

        # Editable model slug — shown for the cloud engines, adapts to the selected one.
        self.model_label = Gtk.Label(xalign=0)
        self.model_entry = Gtk.Entry(hexpand=True)
        self.model_entry.set_width_chars(30)
        self.model_entry.connect("changed", self._on_model_changed)
        self.model_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.model_row.append(self.model_label)
        self.model_row.append(self.model_entry)

        self.input_dd = Gtk.DropDown.new_from_strings(["Clipboard (paste)", "Auto-type (ydotool)"])
        self.input_dd.set_selected(1 if self.conf.get("input_method") == "ydotool" else 0)
        self.input_dd.connect("notify::selected", self._on_input_changed)

        guide_chk = Gtk.CheckButton(label="Show guide lines")
        guide_chk.set_active(bool(self.conf.get("guide_lines", True)))
        guide_chk.connect("toggled", self._on_guide_toggled)

        space_chk = Gtk.CheckButton(label="Append a space when auto-typing")
        space_chk.set_active(bool(self.conf.get("append_space", True)))
        space_chk.connect("toggled", lambda c: self.conf.__setitem__("append_space", c.get_active()))

        ontop_chk = Gtk.CheckButton(label="Keep on top in compact mode")
        ontop_chk.set_active(bool(self.conf.get("always_on_top", True)))
        ontop_chk.connect("toggled", self._on_ontop_toggled)

        save_btn = Gtk.Button(label="Save as defaults")
        save_btn.connect("clicked", self._on_save_defaults)

        box.append(labelled("Engine", self.engine_dd))
        box.append(self.model_row)
        box.append(labelled("Send text via", self.input_dd))
        box.append(guide_chk)
        box.append(space_chk)
        box.append(ontop_chk)
        box.append(Gtk.Separator())
        box.append(save_btn)
        popover.set_child(box)
        self._sync_model_row()
        return popover

    def _install_shortcuts(self):
        def add(name, callback, accels):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a: callback())
            self.add_action(action)
            self.app.set_accels_for_action(f"win.{name}", accels)

        add("recognize", self.recognize, ["<Control>Return", "<Control>KP_Enter"])
        add("clear", lambda: self.canvas.clear(), ["<Control>l"])
        add("undo", lambda: self.canvas.undo(), ["<Control>z"])
        add("copy", self.do_copy, ["<Control><Shift>c"])
        add("compact", lambda: self.compact_toggle.set_active(not self.compact_toggle.get_active()), ["<Control>m"])

    # ---- settings handlers ---------------------------------------------
    def _on_engine_changed(self, dropdown, _param):
        self.conf["engine"] = {1: "claude", 2: "openai"}.get(dropdown.get_selected(), "tesseract")
        self._sync_model_row()

    def _sync_model_row(self):
        """Show the model field for the current engine, pre-filled from config."""
        engine = self.conf.get("engine", "tesseract")
        self._syncing = True
        if engine == "claude":
            self.model_label.set_text("Claude model")
            self.model_entry.set_placeholder_text("claude-haiku-4-5-20251001")
            self.model_entry.set_text(self.conf.get("claude_model", ""))
            self.model_row.set_visible(True)
        elif engine == "openai":
            self.model_label.set_text("OpenRouter / OpenAI model")
            self.model_entry.set_placeholder_text("anthropic/claude-sonnet-4.5")
            self.model_entry.set_text(self.conf.get("openai_model", ""))
            self.model_row.set_visible(True)
        else:
            self.model_row.set_visible(False)
        self._syncing = False

    def _on_model_changed(self, entry):
        if getattr(self, "_syncing", False):
            return  # programmatic update from _sync_model_row, not a user edit
        engine = self.conf.get("engine", "tesseract")
        text = entry.get_text().strip()
        if engine == "claude":
            self.conf["claude_model"] = text
        elif engine == "openai":
            self.conf["openai_model"] = text

    def _on_input_changed(self, dropdown, _param):
        self.conf["input_method"] = "ydotool" if dropdown.get_selected() == 1 else "clipboard"

    def _on_guide_toggled(self, check):
        self.conf["guide_lines"] = check.get_active()
        self.canvas.guide_lines = check.get_active()
        self.canvas.queue_draw()

    def _on_ontop_toggled(self, check):
        self.conf["always_on_top"] = check.get_active()
        # Re-apply if we're already compact so the change takes effect now.
        if self.conf.get("compact"):
            self._apply_always_on_top(True)

    # ---- compact / always-on-top ---------------------------------------
    def _on_compact_toggled(self, button):
        if self._sync_compact:
            return  # programmatic sync from _apply_compact, not a user click
        self._apply_compact(button.get_active())

    def _on_map_pin(self, *_a):
        self._apply_always_on_top(self.conf.get("compact", False))
        return False

    def _apply_compact(self, on, *, resize=True, apply_on_top=True):
        """Switch between the full window and a small, stripped-down one.

        Compact mode hides the toolbar and the recognized-text box, leaving the
        canvas plus Recognize / Auto-type / Copy — a palette you can keep beside
        your target app and feed with auto-type.
        """
        on = bool(on)
        self.conf["compact"] = on
        self.toolbar.set_visible(not on)
        self.text_frame.set_visible(not on)
        self.clear_text_btn.set_visible(not on)
        # A shorter canvas keeps the compact window small but still writable.
        self.canvas.set_content_height(120 if on else 260)
        if self.compact_toggle.get_active() != on:  # keep button + shortcut in sync
            self._sync_compact = True  # don't let set_active re-enter via "toggled"
            self.compact_toggle.set_active(on)
            self._sync_compact = False
        if resize:
            self._resize_to(*(COMPACT_SIZE if on else NORMAL_SIZE))
        if apply_on_top:
            self._apply_always_on_top(on)

    def _resize_to(self, width, height):
        """Force a mapped window to a new size.

        GTK4 dropped Gtk.Window.resize(); set_default_size alone won't shrink an
        already-shown window. Briefly making the window non-resizable snaps it to
        its natural size, which we pin to the target via the root's size request.
        """
        self.set_default_size(width, height)
        self._root.set_size_request(width, height)
        self.set_resizable(False)

        def release():
            self.set_resizable(True)
            self._root.set_size_request(-1, -1)
            return False

        GLib.idle_add(release)

    def _apply_always_on_top(self, compact_on):
        """Best-effort keep-above for compact mode.

        GTK4 exposes no portable "keep above", so we shell out to wmctrl when
        present (works on X11 sessions). On Wayland/GNOME, where only the
        compositor can pin a window, we fall back to a one-time hint pointing at
        the title-bar's "Always on Top" item.
        """
        import shutil
        import subprocess

        want = bool(compact_on) and bool(self.conf.get("always_on_top", True))
        if want == self._on_top:
            return False
        self._on_top = want

        if shutil.which("wmctrl"):
            action = "add" if want else "remove"
            try:
                subprocess.run(
                    ["wmctrl", "-r", self.get_title() or "Scriber", "-b", f"{action},above"],
                    check=False,
                    capture_output=True,
                )
                return False
            except Exception:  # noqa: BLE001 — fall through to the manual hint
                pass

        if want:
            self._set_status("Compact mode — to pin it, right-click the title bar → Always on Top")
        return False

    def _on_save_defaults(self, _btn):
        cfg.save(self.conf)
        self._set_status(f"Saved defaults to {cfg.CONFIG_PATH}")

    # ---- recognition ----------------------------------------------------
    def recognize(self):
        if self.canvas.is_empty():
            self._set_status("Nothing to recognize yet")
            return
        png = self.canvas.export_png()
        recognizer = make_recognizer(self.conf)
        ok, msg = recognizer.available()
        if not ok:
            self._set_status(f"{recognizer.name}: {msg}", error=True)
            return
        self._set_status(f"Recognizing with {recognizer.name}…")

        def worker():
            try:
                text = recognizer.recognize(png)
                GLib.idle_add(self._on_result, text)
            except Exception as exc:  # noqa: BLE001 — surface any backend failure
                GLib.idle_add(self._set_status, f"Error: {exc}", True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, text):
        text = text or ""
        if self.append_toggle.get_active() and self._text().strip():
            text = self._text().rstrip() + " " + text.lstrip()
        self.buffer.set_text(text, -1)
        cfg.write_last_text(text)
        if not text.strip():
            self._set_status("No text recognized — try writing larger / clearer")
        elif self.conf.get("input_method", "clipboard") == "clipboard":
            self._copy(text)
            self._set_status("Recognized & copied — switch to your app and press Ctrl+V")
        else:
            self._set_status("Recognized — press Auto-type, or Copy")
        return False

    # ---- delivery -------------------------------------------------------
    def _text(self) -> str:
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, False)

    def _copy(self, text) -> bool:
        try:
            ClipboardInjector(display=self.get_display()).send(text)
            return True
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Copy failed: {exc}", error=True)
            return False

    def do_copy(self):
        text = self._text()
        if not text.strip():
            self._set_status("Nothing to copy")
            return
        cfg.write_last_text(text)
        if self._copy(text):
            self._set_status("Copied — press Ctrl+V in your target app")

    def do_autotype(self):
        text = self._text()
        if not text.strip():
            self._set_status("Nothing to type")
            return
        cfg.write_last_text(text)
        self._copy(text)  # always leave a clipboard fallback
        injector = YdotoolInjector()
        ok, msg = injector.available()
        if not ok:
            self._set_status(
                f"Auto-type unavailable ({msg}). Text copied — paste with Ctrl+V. See README to enable ydotool.",
                error=True,
            )
            return
        seconds = max(1, round(float(self.conf.get("autotype_delay", 1.2))))
        self._countdown(seconds, text, injector)

    def _countdown(self, n, text, injector):
        if n > 0:
            self._set_status(f"Click your target window… typing in {n}")
            GLib.timeout_add(700, self._countdown, n - 1, text, injector)
            return False
        if self.conf.get("append_space", True):
            text = text + " "
        try:
            injector.send(text)
            self._set_status("Typed into the focused window")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Type failed: {exc} — text is on the clipboard (Ctrl+V)", error=True)
        return False

    # ---- misc -----------------------------------------------------------
    def _on_stroke_finished(self):
        if not self.auto_toggle.get_active():
            return
        if self._auto_timer:
            GLib.source_remove(self._auto_timer)
        self._auto_timer = GLib.timeout_add(900, self._auto_fire)

    def _auto_fire(self):
        self._auto_timer = None
        self.recognize()
        return False

    def _set_status(self, message, error=False):
        self.status.set_text(("⚠ " + message) if error else message)
        return False


def run() -> int:
    conf = cfg.load()
    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def on_activate(application):
        win = application.get_active_window() or ScriberWindow(application, conf)
        win.present()

    app.connect("activate", on_activate)
    return app.run(None)
