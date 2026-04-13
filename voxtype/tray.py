import logging
import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

    HAS_APPINDICATOR = True
except (ValueError, ImportError):
    HAS_APPINDICATOR = False

from gi.repository import Gtk

from .config import Config

log = logging.getLogger(__name__)

_TRANSCRIPT_LOG = Path.home() / ".local" / "share" / "voxtype" / "transcript.log"


class TrayIcon:
    """System tray icon using AppIndicator3 (native to Cinnamon)."""

    def __init__(self, config: Config, on_toggle=None, on_settings=None, on_quit=None):
        self._config = config
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._indicator = None
        self._status_item = None
        self._info_item = None

        if not HAS_APPINDICATOR:
            log.warning(
                "AppIndicator3 not available. Install gir1.2-appindicator3-0.1"
            )
            return

        icon_dir = str(config.icon_dir)
        self._icon_dir = icon_dir
        self._indicator = AppIndicator3.Indicator.new(
            "voxtype-tray",
            "vt-ready",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(icon_dir)
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()

        self._info_item = Gtk.MenuItem(label="○  Ready")
        self._info_item.set_sensitive(False)
        menu.append(self._info_item)

        menu.append(Gtk.SeparatorMenuItem())

        self._status_item = Gtk.MenuItem(label="Start Dictation")
        self._status_item.connect("activate", self._on_toggle_clicked)
        menu.append(self._status_item)

        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", self._on_settings_clicked)
        menu.append(settings_item)

        transcript_item = Gtk.MenuItem(label="View Transcript")
        transcript_item.connect("activate", self._on_transcript_clicked)
        menu.append(transcript_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        menu.append(quit_item)

        menu.show_all()
        self._indicator.set_menu(menu)

    def set_state(self, state: str):
        """Update tray icon to reflect state: 'ready', 'active', 'error'."""
        if not self._indicator:
            return

        icon_map = {
            "ready": "vt-ready",
            "active": "vt-active",
            "error": "vt-error",
        }
        icon_file = icon_map.get(state, "vt-ready")
        self._indicator.set_icon_full(
            icon_file, f"VoxType: {state}"
        )

        if self._status_item:
            if state == "active":
                self._status_item.set_label("Stop Dictation")
            else:
                self._status_item.set_label("Start Dictation")
        self._update_info_item(state)

    def _update_info_item(self, state: str):
        if self._info_item is None:
            return
        icons = {"active": "●", "error": "⚠", "ready": "○"}
        icon = icons.get(state, "○")
        summary = self._get_settings_summary()
        self._info_item.set_label(f"{icon}  {summary}")

    def _get_settings_summary(self) -> str:
        parts = []
        ptt_key = self._config.get("ptt_key").strip()
        if ptt_key:
            parts.append(f"PTT: {ptt_key}")
        else:
            parts.append("toggle")
        method = (self._config.get("input_method") or "PW-CAT").lower()
        parts.append(method)
        timeout = self._config.get("timeout")
        if timeout and timeout != "0":
            parts.append(f"{timeout}s timeout")
        return " · ".join(parts)

    def _on_transcript_clicked(self, widget):
        try:
            subprocess.Popen(
                ["xdg-open", str(_TRANSCRIPT_LOG)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("xdg-open not found; transcript is at %s", _TRANSCRIPT_LOG)

    def _on_toggle_clicked(self, widget):
        if self._on_toggle:
            self._on_toggle()

    def _on_settings_clicked(self, widget):
        if self._on_settings:
            self._on_settings()

    def _on_quit_clicked(self, widget):
        if self._on_quit:
            self._on_quit()
