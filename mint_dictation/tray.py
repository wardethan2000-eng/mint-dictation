import logging
import os

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


class TrayIcon:
    """System tray icon using AppIndicator3 (native to Cinnamon)."""

    def __init__(self, config: Config, on_toggle=None, on_settings=None, on_quit=None):
        self._config = config
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._indicator = None
        self._status_item = None

        if not HAS_APPINDICATOR:
            log.warning(
                "AppIndicator3 not available. Install gir1.2-appindicator3-0.1"
            )
            return

        icon_dir = str(config.icon_dir)
        self._indicator = AppIndicator3.Indicator.new(
            "mint-dictation",
            os.path.join(icon_dir, "mic-ready"),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(icon_dir)
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()

        self._status_item = Gtk.MenuItem(label="Start Dictation")
        self._status_item.connect("activate", self._on_toggle_clicked)
        menu.append(self._status_item)

        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", self._on_settings_clicked)
        menu.append(settings_item)

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

        icon_dir = str(self._config.icon_dir)
        icon_map = {
            "ready": "mic-ready",
            "active": "mic-active",
            "error": "mic-error",
        }
        icon_name = icon_map.get(state, "mic-ready")
        self._indicator.set_icon_full(
            os.path.join(icon_dir, icon_name), f"Dictation: {state}"
        )

        if self._status_item:
            if state == "active":
                self._status_item.set_label("Stop Dictation")
            else:
                self._status_item.set_label("Start Dictation")

    def _on_toggle_clicked(self, widget):
        if self._on_toggle:
            self._on_toggle()

    def _on_settings_clicked(self, widget):
        if self._on_settings:
            self._on_settings()

    def _on_quit_clicked(self, widget):
        if self._on_quit:
            self._on_quit()
