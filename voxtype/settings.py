import logging
import subprocess
from pathlib import Path

import ast
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk, Gtk

from .config import Config

_TRANSCRIPT_LOG = Path.home() / ".local" / "share" / "voxtype" / "transcript.log"

_VOICE_COMMANDS = [
    ("stop recording",    "Stop recording and close overlay"),
    ("stop dictation",    "Same as above"),
    ("period",            "Inserts  ."),
    ("comma",             "Inserts  ,"),
    ("question mark",     "Inserts  ?"),
    ("exclamation mark",  "Inserts  !"),
    ("colon",             "Inserts  :"),
    ("semicolon",         "Inserts  ;"),
    ("dash",              "Inserts  —"),
    ("new line",          "Inserts a line break"),
    ("new paragraph",     "Inserts two line breaks"),
    ("tab key",           "Inserts a tab character"),
    ("open quote",        'Inserts  "'),
    ("close quote",       'Inserts  "'),
    ("open paren",        "Inserts  ("),
    ("close paren",       "Inserts  )"),
]

log = logging.getLogger(__name__)

_RATES = ["16000", "22050", "44100", "48000"]
_METHODS = ["PW-CAT", "PAREC", "SOX"]


class SettingsWindow:
    """Main application window — Getting Started, Settings, and Transcript."""

    def __init__(self, config: Config, on_settings_changed=None,
                 on_toggle=None, on_status=None):
        self._config = config
        self._on_settings_changed = on_settings_changed
        self._on_toggle = on_toggle       # callable()
        self._on_status = on_status       # callable() -> "active"/"ready"/"error"
        self._window = None
        self._status_label = None
        self._toggle_btn = None
        self._transcript_view = None
        self._info_bar = None
        self._status_timer_id = None
        self._current_hotkey = self._config.get("toggle_hotkey", "")
        self._hotkey_display_lbl = None

    def show(self):
        if self._window and self._window.get_visible():
            self._window.present()
            return
        self._build()
        self._window.show_all()
        self._info_bar.hide()
        self._start_status_updates()
        self._refresh_status()

    def hide(self):
        self._stop_status_updates()
        if self._window:
            self._window.hide()

    # ── Build ────────────────────────────────────────────────────────

    def _build(self):
        self._window = Gtk.Window(title="VoxType")
        self._window.set_default_size(560, 640)
        self._window.set_resizable(False)
        self._window.set_icon_name("microphone")
        self._window.connect("delete-event", lambda w, e: w.hide() or True)
        self._window.connect("hide", lambda w: self._stop_status_updates())

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._window.add(outer)

        outer.pack_start(self._build_status_header(), False, False, 0)
        outer.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        notebook = Gtk.Notebook()
        notebook.set_border_width(4)
        outer.pack_start(notebook, True, True, 0)

        # Save confirmation info bar
        self._info_bar = Gtk.InfoBar()
        self._info_bar.set_message_type(Gtk.MessageType.INFO)
        self._info_bar.set_no_show_all(True)
        self._info_bar.get_content_area().add(
            Gtk.Label(label="Settings saved. Changes take effect on the next recording session.")
        )
        outer.pack_start(self._info_bar, False, False, 0)

        notebook.append_page(self._build_getting_started_tab(), Gtk.Label(label="  Getting Started  "))
        notebook.append_page(self._build_audio_tab(),           Gtk.Label(label="  Audio  "))
        notebook.append_page(self._build_recognition_tab(),     Gtk.Label(label="  Recognition  "))
        notebook.append_page(self._build_hotkey_tab(),          Gtk.Label(label="  Hotkey  "))
        notebook.append_page(self._build_transcript_tab(),      Gtk.Label(label="  Transcript  "))

        outer.pack_start(self._build_button_bar(), False, False, 0)

    def _build_status_header(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_border_width(14)

        self._status_label = Gtk.Label(label="○  Ready")
        self._status_label.set_xalign(0.0)
        self._status_label.get_style_context().add_class("dim-label")
        box.pack_start(self._status_label, True, True, 0)

        self._toggle_btn = Gtk.Button(label="Start Dictation")
        self._toggle_btn.get_style_context().add_class("suggested-action")
        self._toggle_btn.connect("clicked", self._on_toggle_clicked)
        self._toggle_btn.set_sensitive(self._on_toggle is not None)
        box.pack_end(self._toggle_btn, False, False, 0)

        return box

    def _build_button_bar(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_border_width(10)
        outer.pack_start(bar, False, False, 0)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda _: self.hide())
        bar.pack_start(btn_cancel, False, False, 0)

        btn_save = Gtk.Button(label="Save Settings")
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", lambda _: self._save())
        bar.pack_end(btn_save, False, False, 0)

        return outer

    # ── Getting Started tab ──────────────────────────────────────────

    def _build_getting_started_tab(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_border_width(20)
        scroll.add(box)

        intro = Gtk.Label()
        intro.set_markup(
            "<b>VoxType</b> listens to your microphone and types what you say "
            "into any focused application — a browser, text editor, chat window, or anything else."
        )
        intro.set_line_wrap(True)
        intro.set_xalign(0.0)
        box.pack_start(intro, False, False, 0)

        box.pack_start(self._section_label("Quick Start"), False, False, 0)

        steps = [
            ("1", "Set up a hotkey",
             "Open <i>System Settings → Keyboard → Shortcuts → Custom Shortcuts</i>\n"
             "and add a new shortcut with this command:\n"
             "<tt>~/.local/bin/voxtype --toggle</tt>"),
            ("2", "Press your hotkey",
             "The floating overlay appears at the top of your screen. Dictation starts immediately."),
            ("3", "Speak normally",
             "Text is typed into the focused window. Use voice commands below to insert punctuation."),
            ("4", "Press your hotkey again",
             "Or click the overlay to stop. The overlay disappears and dictation ends."),
        ]
        for num, title, desc in steps:
            box.pack_start(self._step_row(num, title, desc), False, False, 0)

        hk_btn = Gtk.Button(label="Open Keyboard Settings…")
        hk_btn.set_halign(Gtk.Align.START)
        hk_btn.connect("clicked", self._on_open_keyboard_settings)
        box.pack_start(hk_btn, False, False, 0)

        box.pack_start(self._section_label("Voice Commands"), False, False, 0)

        vc_note = Gtk.Label(label="Say any of these words while recording to trigger the action:")
        vc_note.set_xalign(0.0)
        vc_note.set_line_wrap(True)
        box.pack_start(vc_note, False, False, 0)

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(20)
        for i, (cmd, desc) in enumerate(_VOICE_COMMANDS):
            cmd_lbl = Gtk.Label()
            cmd_lbl.set_markup(f'<tt><b>"{cmd}"</b></tt>')
            cmd_lbl.set_xalign(0.0)
            desc_lbl = Gtk.Label(label=desc)
            desc_lbl.set_xalign(0.0)
            desc_lbl.get_style_context().add_class("dim-label")
            grid.attach(cmd_lbl,  0, i, 1, 1)
            grid.attach(desc_lbl, 1, i, 1, 1)
        box.pack_start(grid, False, False, 0)

        box.pack_start(self._section_label("Push-to-Talk Mode"), False, False, 0)
        ptt_note = Gtk.Label()
        ptt_note.set_markup(
            "Instead of toggling, hold a key to record and release to stop.\n"
            "Set a <b>Push-to-talk key</b> in the <i>Recognition</i> tab (e.g. <tt>f9</tt>),\n"
            "then add <tt>--press</tt> on key-down and <tt>--release</tt> on key-up shortcuts."
        )
        ptt_note.set_line_wrap(True)
        ptt_note.set_xalign(0.0)
        box.pack_start(ptt_note, False, False, 0)

        return scroll

    def _section_label(self, text: str) -> Gtk.Label:
        lbl = Gtk.Label()
        lbl.set_markup(f"<b>{text}</b>")
        lbl.set_xalign(0.0)
        return lbl

    def _step_row(self, num: str, title: str, desc: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_valign(Gtk.Align.START)

        badge = Gtk.Label()
        badge.set_markup(f"<b>{num}</b>")
        badge.set_size_request(24, 24)
        badge.get_style_context().add_class("dim-label")
        row.pack_start(badge, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_lbl = Gtk.Label()
        title_lbl.set_markup(f"<b>{title}</b>")
        title_lbl.set_xalign(0.0)
        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(desc)
        desc_lbl.set_xalign(0.0)
        desc_lbl.set_line_wrap(True)
        desc_lbl.get_style_context().add_class("dim-label")
        text_box.pack_start(title_lbl, False, False, 0)
        text_box.pack_start(desc_lbl, False, False, 0)
        row.pack_start(text_box, True, True, 0)

        return row

    # ── Transcript tab ───────────────────────────────────────────────

    def _build_transcript_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(10)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._transcript_view = Gtk.TextView()
        self._transcript_view.set_editable(False)
        self._transcript_view.set_cursor_visible(False)
        self._transcript_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._transcript_view.set_monospace(True)
        self._transcript_view.set_left_margin(8)
        self._transcript_view.set_right_margin(8)
        self._transcript_view.set_top_margin(6)
        scroll.add(self._transcript_view)
        box.pack_start(scroll, True, True, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda _: self._load_transcript())
        btn_row.pack_start(refresh_btn, False, False, 0)

        open_btn = Gtk.Button(label="Open in Text Editor")
        open_btn.connect("clicked", self._on_open_transcript)
        btn_row.pack_start(open_btn, False, False, 0)

        path_lbl = Gtk.Label()
        path_lbl.set_markup(f'<small><span foreground="#888">{_TRANSCRIPT_LOG}</span></small>')
        path_lbl.set_xalign(0.0)
        btn_row.pack_end(path_lbl, False, False, 0)

        box.pack_start(btn_row, False, False, 0)

        GLib.idle_add(self._load_transcript)
        return box

    def _load_transcript(self, *_):
        if self._transcript_view is None:
            return
        buf = self._transcript_view.get_buffer()
        if not _TRANSCRIPT_LOG.exists():
            buf.set_text("No transcript yet. Start recording and speak to generate one.")
            return
        try:
            lines = _TRANSCRIPT_LOG.read_text(encoding="utf-8").splitlines()
            buf.set_text("\n".join(lines[-200:]))
            end = buf.get_end_iter()
            self._transcript_view.scroll_to_iter(end, 0.0, False, 0.0, 1.0)
        except Exception as e:
            buf.set_text(f"Could not load transcript: {e}")

    # ── Status updates ────────────────────────────────────────────────

    def _start_status_updates(self):
        self._status_timer_id = GLib.timeout_add(1000, self._refresh_status)

    def _stop_status_updates(self):
        if self._status_timer_id is not None:
            GLib.source_remove(self._status_timer_id)
            self._status_timer_id = None

    def _refresh_status(self, *_) -> bool:
        if self._status_label is None:
            return False
        state = self._on_status() if self._on_status else "ready"
        icons  = {"active": "●", "error": "⚠", "ready": "○"}
        labels = {"active": "Recording…", "error": "Error — click to retry", "ready": "Ready"}
        color  = "#e05050" if state == "active" else "#888888"
        self._status_label.set_markup(
            f'<span foreground="{color}">{icons.get(state, "○")}  {labels.get(state, "Ready")}</span>'
        )
        if self._toggle_btn:
            self._toggle_btn.set_label(
                "Stop Dictation" if state == "active" else "Start Dictation"
            )
            ctx = self._toggle_btn.get_style_context()
            if state == "active":
                ctx.remove_class("suggested-action")
                ctx.add_class("destructive-action")
            else:
                ctx.remove_class("destructive-action")
                ctx.add_class("suggested-action")
        return True

    def _grid(self):
        g = Gtk.Grid()
        g.set_row_spacing(12)
        g.set_column_spacing(14)
        g.set_border_width(18)
        return g

    def _flabel(self, text):
        lbl = Gtk.Label(label=text, xalign=1.0)
        lbl.get_style_context().add_class("dim-label")
        return lbl

    # ── Audio tab ────────────────────────────────────────────────────

    def _build_audio_tab(self):
        g = self._grid()

        # Input method
        g.attach(self._flabel("Input method:"), 0, 0, 1, 1)
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
        g.attach(self._flabel("Sample rate:"), 0, 2, 1, 1)
        self._rate_combo = Gtk.ComboBoxText()
        for r in _RATES:
            self._rate_combo.append_text(r + " Hz")
        cur_rate = self._config.get("sample_rate") or "44100"
        self._rate_combo.set_active(_RATES.index(cur_rate) if cur_rate in _RATES else 2)
        g.attach(self._rate_combo, 1, 2, 1, 1)

        # VOSK model directory
        g.attach(self._flabel("VOSK model:"), 0, 3, 1, 1)
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
        g.attach(self._flabel("Microphone:"), 0, 5, 1, 1)
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
        g.attach(self._flabel("Silence timeout:"), 0, 3, 1, 1)
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
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_border_width(18)

        # ── Toggle hotkey capture row ────────────────────────────────
        g = self._grid()
        g.set_border_width(0)

        g.attach(self._flabel("Toggle hotkey:"), 0, 0, 1, 1)

        hk_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        current = self._current_hotkey or "Not set"
        self._hotkey_display_lbl = Gtk.Label(label=current)
        self._hotkey_display_lbl.get_style_context().add_class("dim-label")
        self._hotkey_display_lbl.set_xalign(0.0)
        self._hotkey_display_lbl.set_width_chars(18)
        hk_row.pack_start(self._hotkey_display_lbl, False, False, 0)

        set_btn = Gtk.Button(label="Set…")
        set_btn.connect("clicked", self._on_set_hotkey_clicked)
        hk_row.pack_start(set_btn, False, False, 0)

        g.attach(hk_row, 1, 0, 1, 1)

        apply_btn = Gtk.Button(label="Apply to Cinnamon")
        apply_btn.set_tooltip_text("Registers the hotkey as a Cinnamon custom keyboard shortcut")
        apply_btn.connect("clicked", self._on_apply_cinnamon_clicked)
        g.attach(apply_btn, 1, 1, 1, 1)

        de_note = Gtk.Label(xalign=0)
        de_note.set_markup(
            '<small><span foreground="#888">'
            "Works on Linux Mint / Cinnamon DE. For other desktops, add the shortcut manually."
            "</span></small>"
        )
        de_note.set_line_wrap(True)
        g.attach(de_note, 0, 2, 2, 1)

        box.pack_start(g, False, False, 0)

        # ── Push-to-talk key row ──────────────────────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 0)

        ptt_g = self._grid()
        ptt_g.set_border_width(0)

        ptt_g.attach(self._flabel("Push-to-talk key:"), 0, 0, 1, 1)
        self._ptt_entry = Gtk.Entry()
        self._ptt_entry.set_text(self._config.get("ptt_key", ""))
        self._ptt_entry.set_tooltip_text("e.g.  ctrl  or  f9  (pynput key name)")
        ptt_g.attach(self._ptt_entry, 1, 0, 1, 1)

        ptt_hint = Gtk.Label(xalign=0)
        ptt_hint.set_markup(
            '<small><span foreground="#888">'
            "Hold to record, release to stop. Leave blank to disable push-to-talk."
            "</span></small>"
        )
        ptt_g.attach(ptt_hint, 0, 1, 2, 1)

        box.pack_start(ptt_g, False, False, 0)

        return box

    def _on_set_hotkey_clicked(self, _button):
        """Open a key-capture dialog and update the displayed binding."""
        binding = self._capture_hotkey_dialog()
        if binding:
            self._current_hotkey = binding
            self._hotkey_display_lbl.set_text(binding)

    def _capture_hotkey_dialog(self) -> str:
        """Show a modal dialog, capture one key+modifier combo, return binding string."""
        dialog = Gtk.Dialog(title="Set Toggle Hotkey", parent=self._window, modal=True)
        dialog.set_default_size(340, 0)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)

        lbl = Gtk.Label()
        lbl.set_markup("<b>Press your desired hotkey combination…</b>")
        lbl.set_margin_top(20)
        lbl.set_margin_bottom(20)
        lbl.set_margin_start(16)
        lbl.set_margin_end(16)
        dialog.get_content_area().pack_start(lbl, True, True, 0)
        dialog.show_all()

        captured = []

        # Mask that Gtk uses to check meaningful modifier keys
        _MOD_MASK = (
            Gdk.ModifierType.SUPER_MASK
            | Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.MOD1_MASK
            | Gdk.ModifierType.SHIFT_MASK
        )

        _LONE_MODS = {
            Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
            Gdk.KEY_Control_L, Gdk.KEY_Control_R,
            Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
            Gdk.KEY_Super_L, Gdk.KEY_Super_R,
            Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
            Gdk.KEY_Hyper_L, Gdk.KEY_Hyper_R,
        }

        def on_key_press(widget, event):
            if event.keyval in _LONE_MODS:
                return True
            parts = []
            mods = event.state & _MOD_MASK
            if mods & Gdk.ModifierType.SUPER_MASK:
                parts.append("Super")
            if mods & Gdk.ModifierType.CONTROL_MASK:
                parts.append("Control")
            if mods & Gdk.ModifierType.MOD1_MASK:
                parts.append("Alt")
            if mods & Gdk.ModifierType.SHIFT_MASK:
                parts.append("Shift")
            keyname = Gdk.keyval_name(event.keyval)
            binding = "".join(f"<{p}>" for p in parts) + keyname
            captured.append(binding)
            lbl.set_markup(f"<b>{binding}</b>")
            dialog.response(Gtk.ResponseType.OK)
            return True

        dialog.connect("key-press-event", on_key_press)
        result = dialog.run()
        dialog.destroy()

        return captured[0] if (result == Gtk.ResponseType.OK and captured) else ""

    def _on_apply_cinnamon_clicked(self, _button):
        """Write the current hotkey into Cinnamon custom keyboard shortcuts via dconf."""
        binding = self._current_hotkey.strip()
        if not binding:
            self._show_message("No hotkey set", "Press \"Set…\" first to capture a key combination.")
            return
        launcher = Path.home() / ".local" / "bin" / "voxtype"
        command = f"{launcher} --toggle"
        short_name = "VoxType Toggle"
        try:
            self._write_cinnamon_shortcut(binding, command, short_name)
            self._show_message(
                "Hotkey applied",
                f"{binding} → {short_name}\n\nLog out and back in if it doesn't take effect immediately.",
            )
        except Exception as exc:
            log.error("Failed to apply Cinnamon hotkey: %s", exc)
            self._show_message("Failed to apply hotkey", str(exc))

    @staticmethod
    def _write_cinnamon_shortcut(binding: str, command: str, name: str) -> None:
        """Create or update a Cinnamon custom keyboard shortcut via dconf."""
        _BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings"
        _LIST_KEY = "/org/cinnamon/desktop/keybindings/custom-list"

        def dconf_read(path: str) -> str:
            r = subprocess.run(["dconf", "read", path], capture_output=True, text=True, timeout=5)
            return r.stdout.strip()

        def dconf_write(path: str, value: str) -> None:
            subprocess.run(["dconf", "write", path, value], check=True, timeout=5)

        # Parse current custom-list
        raw = dconf_read(_LIST_KEY)
        if not raw or raw in ("@as []", "[]"):
            existing: list[str] = []
        else:
            try:
                existing = ast.literal_eval(raw.replace("'", '"'))
            except Exception:
                existing = []

        # Find slot already pointing at voxtype
        target_id = None
        for cid in existing:
            cmd_raw = dconf_read(f"{_BASE}/{cid}/command")
            if "voxtype" in cmd_raw:
                target_id = cid
                break

        if target_id is None:
            target_id = f"custom{len(existing)}"
            existing.append(target_id)
            list_val = "[" + ", ".join(f"'{x}'" for x in existing) + "]"
            dconf_write(_LIST_KEY, list_val)

        base = f"{_BASE}/{target_id}"
        dconf_write(f"{base}/name",    f"'{name}'")
        dconf_write(f"{base}/command", f"'{command}'")
        dconf_write(f"{base}/binding", f"['{binding}']")

    @staticmethod
    def _show_message(title: str, body: str) -> None:
        dlg = Gtk.MessageDialog(
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dlg.format_secondary_text(body)
        dlg.run()
        dlg.destroy()

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

    def _on_toggle_clicked(self, _button):
        if self._on_toggle:
            self._on_toggle()
        GLib.timeout_add(200, self._refresh_status)

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

    def _on_open_transcript(self, _button):
        try:
            subprocess.Popen(
                ["xdg-open", str(_TRANSCRIPT_LOG)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("xdg-open not available")

    def _save(self):
        self._config.set("input_method", _METHODS[self._input_combo.get_active()])
        self._config.set("sample_rate", _RATES[self._rate_combo.get_active()])
        self._config.set("vosk_model_dir", self._model_entry.get_text().strip())
        self._config.set("continuous", str(self._continuous_check.get_active()).lower())
        self._config.set("full_sentence", str(self._full_sentence_check.get_active()).lower())
        self._config.set("numbers_as_digits", str(self._numbers_check.get_active()).lower())
        self._config.set("timeout", str(int(self._timeout_spin.get_value())))
        if hasattr(self, "_ptt_entry"):
            self._config.set("ptt_key", self._ptt_entry.get_text().strip().lower())
        self._config.set("toggle_hotkey", self._current_hotkey)
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
