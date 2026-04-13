import logging
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from .config import Config

log = logging.getLogger(__name__)

_RATES = ["16000", "22050", "44100", "48000"]
_METHODS = ["PW-CAT", "PAREC", "SOX"]


class SettingsWindow:
    """GTK settings dialog for Mint Dictation."""

    def __init__(self, config: Config, on_settings_changed=None):
        self._config = config
        self._on_settings_changed = on_settings_changed
        self._window = None

    def show(self):
        if self._window and self._window.get_visible():
            self._window.present()
            return
        self._build()
        self._window.show_all()

    def hide(self):
        if self._window:
            self._window.hide()

    # ── Build ────────────────────────────────────────────────────────

    def _build(self):
        self._window = Gtk.Dialog(
            title="Mint Dictation — Settings",
            modal=False,
            destroy_with_parent=False,
        )
        self._window.set_default_size(460, 460)
        self._window.set_resizable(False)

        btn_cancel = self._window.add_button("Cancel", Gtk.ResponseType.CANCEL)
        btn_save = self._window.add_button("Save", Gtk.ResponseType.OK)
        btn_save.get_style_context().add_class("suggested-action")
        self._window.set_default_response(Gtk.ResponseType.OK)
        self._window.connect("response", self._on_response)
        self._window.connect("delete-event", lambda w, e: w.hide() or True)

        notebook = Gtk.Notebook()
        notebook.set_border_width(8)
        self._window.get_content_area().pack_start(notebook, True, True, 0)

        # Save confirmation info bar
        self._info_bar = Gtk.InfoBar()
        self._info_bar.set_message_type(Gtk.MessageType.INFO)
        self._info_bar.set_no_show_all(True)
        self._info_bar.get_content_area().add(
            Gtk.Label(label="Changes take effect on the next recording session.")
        )
        self._window.get_content_area().pack_start(self._info_bar, False, False, 0)

        notebook.append_page(self._build_audio_tab(),       Gtk.Label(label="  Audio  "))
        notebook.append_page(self._build_recognition_tab(), Gtk.Label(label="  Recognition  "))
        notebook.append_page(self._build_hotkey_tab(),      Gtk.Label(label="  Hotkey  "))

    def _grid(self):
        g = Gtk.Grid()
        g.set_row_spacing(12)
        g.set_column_spacing(14)
        g.set_border_width(18)
        return g

    def _label(self, text):
        lbl = Gtk.Label(label=text, xalign=1.0)
        lbl.get_style_context().add_class("dim-label")
        return lbl

    # ── Audio tab ────────────────────────────────────────────────────

    def _build_audio_tab(self):
        g = self._grid()

        # Input method
        g.attach(self._label("Input method:"), 0, 0, 1, 1)
        self._input_combo = Gtk.ComboBoxText()
        for m in _METHODS:
            self._input_combo.append_text(m)
        cur = self._config.get("input_method") or "PW-CAT"
        self._input_combo.set_active(_METHODS.index(cur) if cur in _METHODS else 0)
        g.attach(self._input_combo, 1, 0, 1, 1)

        hint = Gtk.Label(xalign=0)
        hint.set_markup('<small><span foreground="#888">PW-CAT = PipeWire  ·  PAREC = PulseAudio  ·  SOX = SoX</span></small>')
        g.attach(hint, 1, 1, 1, 1)

        # Sample rate
        g.attach(self._label("Sample rate:"), 0, 2, 1, 1)
        self._rate_combo = Gtk.ComboBoxText()
        for r in _RATES:
            self._rate_combo.append_text(r + " Hz")
        cur_rate = self._config.get("sample_rate") or "44100"
        self._rate_combo.set_active(_RATES.index(cur_rate) if cur_rate in _RATES else 2)
        g.attach(self._rate_combo, 1, 2, 1, 1)

        # VOSK model directory
        g.attach(self._label("VOSK model:"), 0, 3, 1, 1)
        browse_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._model_entry = Gtk.Entry()
        self._model_entry.set_width_chars(30)
        self._model_entry.set_text(self._config.vosk_model_dir)
        browse_btn = Gtk.Button(label="Browse…")
        browse_btn.connect("clicked", self._on_browse_model)
        browse_box.pack_start(self._model_entry, True, True, 0)
        browse_box.pack_start(browse_btn, False, False, 0)
        g.attach(browse_box, 1, 3, 1, 1)

        model_hint = Gtk.Label(xalign=0)
        model_hint.set_markup(
            '<small><span foreground="#888">Download models at alphacephei.com/vosk/models</span></small>'
        )
        g.attach(model_hint, 1, 4, 1, 1)

        # Microphone device
        g.attach(self._label("Microphone:"), 0, 5, 1, 1)
        self._mic_sources = self._get_audio_sources()
        self._mic_combo = Gtk.ComboBoxText()
        self._mic_combo.append_text("System default")
        for _name, desc in self._mic_sources:
            self._mic_combo.append_text(desc)
        saved_device = self._config.get("input_device")
        mic_idx = 0
        if saved_device:
            for i, (name, _desc) in enumerate(self._mic_sources):
                if name == saved_device:
                    mic_idx = i + 1
                    break
        self._mic_combo.set_active(mic_idx)
        g.attach(self._mic_combo, 1, 5, 1, 1)
        mic_hint = Gtk.Label(xalign=0)
        mic_hint.set_markup(
            '<small><span foreground="#888">Applies when using PipeWire or PulseAudio input</span></small>'
        )
        g.attach(mic_hint, 1, 6, 1, 1)

        return g

    # ── Recognition tab ──────────────────────────────────────────────

    def _build_recognition_tab(self):
        g = self._grid()

        self._continuous_check = Gtk.CheckButton(
            label="Continuous listening (keep recording between sentences)"
        )
        self._continuous_check.set_active(self._config.get_bool("continuous"))
        g.attach(self._continuous_check, 0, 0, 2, 1)

        self._full_sentence_check = Gtk.CheckButton(
            label="Capitalize first word of each sentence"
        )
        self._full_sentence_check.set_active(self._config.get_bool("full_sentence"))
        g.attach(self._full_sentence_check, 0, 1, 2, 1)

        self._numbers_check = Gtk.CheckButton(
            label='Convert number words to digits  (e.g. "five" → 5)'
        )
        self._numbers_check.set_active(self._config.get_bool("numbers_as_digits"))
        g.attach(self._numbers_check, 0, 2, 2, 1)

        # Silence timeout
        g.attach(self._label("Silence timeout:"), 0, 3, 1, 1)
        timeout_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._timeout_spin = Gtk.SpinButton.new_with_range(0, 60, 1)
        try:
            self._timeout_spin.set_value(float(self._config.get("timeout") or "0"))
        except (ValueError, TypeError):
            self._timeout_spin.set_value(0)
        timeout_box.pack_start(self._timeout_spin, False, False, 0)
        timeout_box.pack_start(Gtk.Label(label="seconds  (0 = no auto-stop)"), False, False, 0)
        g.attach(timeout_box, 1, 3, 1, 1)

        return g

    # ── Hotkey tab ───────────────────────────────────────────────────

    def _build_hotkey_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_border_width(18)

        info = Gtk.Label(xalign=0)
        info.set_line_wrap(True)
        info.set_markup(
            "Hotkeys are managed by your desktop environment.\n\n"
            "To toggle dictation on/off with a key combination, add a "
            "<b>Custom Shortcut</b> in:\n"
            "<i>System Settings → Keyboard → Shortcuts → Custom Shortcuts</i>"
        )
        box.pack_start(info, False, False, 0)

        # Command display
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        cmd_lbl = Gtk.Label()
        cmd_lbl.set_markup("<tt><b>~/.local/bin/mint-dictation --toggle</b></tt>")
        cmd_lbl.set_selectable(True)
        cmd_lbl.set_margin_top(10)
        cmd_lbl.set_margin_bottom(10)
        cmd_lbl.set_margin_start(14)
        cmd_lbl.set_margin_end(14)
        frame.add(cmd_lbl)
        box.pack_start(frame, False, False, 0)

        note = Gtk.Label(xalign=0)
        note.set_markup(
            '<small><span foreground="#888">'
            "The daemon starts automatically when the hotkey is pressed — "
            "no need to launch it separately."
            "</span></small>"
        )
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 0)

        open_btn = Gtk.Button(label="Open Keyboard Settings")
        open_btn.set_halign(Gtk.Align.START)
        open_btn.connect("clicked", self._on_open_keyboard_settings)
        box.pack_start(open_btn, False, False, 0)

        return box

    # ── Callbacks ────────────────────────────────────────────────────

    @staticmethod
    def _get_audio_sources() -> list[tuple[str, str]]:
        """Returns list of (device_name, description) for non-monitor input sources."""
        sources = []
        try:
            result = subprocess.run(
                ["pactl", "list", "sources"],
                capture_output=True, text=True, timeout=3,
            )
            current_name = None
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Name:"):
                    current_name = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Description:") and current_name is not None:
                    desc = stripped.split(":", 1)[1].strip()
                    if not current_name.endswith(".monitor"):
                        sources.append((current_name, desc))
                    current_name = None
        except Exception:
            pass
        return sources

    def _on_browse_model(self, _button):
        dialog = Gtk.FileChooserDialog(
            title="Select VOSK Model Directory",
            parent=self._window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Select", Gtk.ResponseType.OK)
        dialog.set_filename(self._model_entry.get_text())
        if dialog.run() == Gtk.ResponseType.OK:
            self._model_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _on_open_keyboard_settings(self, _button):
        for cmd in (["cinnamon-settings", "keyboard"], ["gnome-control-center", "keyboard"]):
            try:
                subprocess.Popen(cmd)
                return
            except FileNotFoundError:
                continue
        log.warning("Could not open keyboard settings")

    def _on_response(self, _dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            self._save()
        self._window.hide()

    def _save(self):
        self._config.set("input_method", _METHODS[self._input_combo.get_active()])
        self._config.set("sample_rate", _RATES[self._rate_combo.get_active()])
        self._config.set("vosk_model_dir", self._model_entry.get_text().strip())
        self._config.set("continuous", str(self._continuous_check.get_active()).lower())
        self._config.set("full_sentence", str(self._full_sentence_check.get_active()).lower())
        self._config.set("numbers_as_digits", str(self._numbers_check.get_active()).lower())
        self._config.set("timeout", str(int(self._timeout_spin.get_value())))
        active = self._mic_combo.get_active()
        self._config.set(
            "input_device",
            self._mic_sources[active - 1][0] if active > 0 else ""
        )
        self._config.save()
        log.info("Settings saved")
        self._info_bar.show_all()
        GLib.timeout_add(4000, self._hide_info_bar)
        if self._on_settings_changed:
            self._on_settings_changed()

    def _hide_info_bar(self) -> bool:
        self._info_bar.hide()
        return False
