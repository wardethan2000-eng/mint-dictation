import argparse
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .audio_monitor import AudioMonitor
from .config import Config
from .dictation import DictationManager
from .overlay import DictationOverlay
from .settings import SettingsWindow
from .tray import TrayIcon

log = logging.getLogger(__name__)

SOCKET_PATH = Path.home() / ".cache" / "mint-dictation" / "ipc.sock"
PID_PATH = Path.home() / ".cache" / "mint-dictation" / "daemon.pid"


class MintDictationApp:
    def __init__(self):
        self._config = Config()
        self._dictation = DictationManager(self._config)
        self._audio_monitor = AudioMonitor(on_level=self._on_audio_level)
        self._overlay = DictationOverlay(on_stop_clicked=self.toggle_dictation)
        self._settings = SettingsWindow(
            self._config,
            on_toggle=self.toggle_dictation,
            on_status=lambda: "active" if self._dictation.is_running else "ready",
            on_settings_changed=self._on_settings_saved,
        )
        self._tray = TrayIcon(
            self._config,
            on_toggle=self.toggle_dictation,
            on_settings=self._show_settings,
            on_quit=self.quit,
        )
        self._ipc_server = None
        self._running = True
        self._ptt_listener = None

    def toggle_dictation(self):
        if self._dictation.is_running:
            self._stop_dictation()
        else:
            self._start_dictation()

    def _start_dictation(self):
        if self._dictation.start():
            self._audio_monitor.start()
            self._overlay.show()
            self._tray.set_state("active")
            self._start_crash_monitor()
            log.info("Dictation started")
        else:
            self._tray.set_state("error")
            self._notify_error(self._dictation.last_error or "Failed to start dictation.")
            log.error("Failed to start dictation")

    def _stop_dictation(self):
        self._dictation.cancel()
        self._audio_monitor.stop()
        self._overlay.hide()
        self._tray.set_state("ready")
        log.info("Dictation stopped")

    def _on_audio_level(self, levels: list[float]):
        # Schedule UI update on the GTK main thread
        GLib.idle_add(self._overlay.update_levels, levels)

    def _notify_error(self, message: str):
        try:
            subprocess.Popen(
                ["notify-send", "-i", "dialog-error", "-t", "5000",
                 "Mint Dictation", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.warning("notify-send not available: %s", message)

    def _start_crash_monitor(self):
        GLib.timeout_add(2000, self._check_dictation_alive)

    def _check_dictation_alive(self) -> bool:
        if not self._dictation.is_running:
            return False
        if not self._dictation.check_alive():
            log.warning("nerd-dictation process crashed unexpectedly")
            self._dictation.reset_after_crash()
            self._audio_monitor.stop()
            self._overlay.hide()
            self._tray.set_state("error")
            self._notify_error("Dictation stopped unexpectedly. Please try again.")
            return False
        return True

    def _start_ptt_listener(self):
        ptt_key_name = self._config.get("ptt_key").strip().lower()
        if not ptt_key_name:
            return
        try:
            from pynput import keyboard as kb
        except ImportError:
            log.warning("pynput not installed; push-to-talk unavailable. Run: pip install pynput python-xlib")
            return
        try:
            ptt_key = kb.Key[ptt_key_name]
        except KeyError:
            if len(ptt_key_name) == 1:
                ptt_key = kb.KeyCode.from_char(ptt_key_name)
            else:
                log.warning("PTT: unrecognised key %r. Use names like 'f9', 'pause', 'scroll_lock'.", ptt_key_name)
                return

        def _keys_match(key, target):
            """Compare pynput key against target, handling KeyCode vs Key."""
            if key == target:
                return True
            if hasattr(key, 'vk') and hasattr(target, 'vk'):
                return key.vk == target.vk
            return False

        def on_press(key):
            if _keys_match(key, ptt_key) and not self._dictation.is_running:
                GLib.idle_add(self._start_dictation)

        def on_release(key):
            if _keys_match(key, ptt_key) and self._dictation.is_running:
                GLib.idle_add(self._stop_dictation)

        self._ptt_listener = kb.Listener(
            on_press=on_press, on_release=on_release, daemon=True
        )
        self._ptt_listener.start()
        log.info("PTT listener started for key: %r", ptt_key_name)

    def _restart_ptt_listener(self):
        self._stop_ptt_listener()
        self._start_ptt_listener()

    def _on_settings_saved(self):
        self._restart_ptt_listener()
        self._tray._update_info_item("active" if self._dictation.is_running else "ready")

    def _stop_ptt_listener(self):
        if self._ptt_listener is not None:
            try:
                self._ptt_listener.stop()
            except Exception:
                pass
            self._ptt_listener = None

    def quit(self):
        log.info("Shutting down")
        self._running = False
        self._stop_ptt_listener()
        self._dictation.cleanup()
        self._audio_monitor.stop()
        self._overlay.hide()
        self._cleanup_ipc()
        Gtk.main_quit()

    # ── IPC Server (Unix Domain Socket) ──────────────────────────────

    def _start_ipc_server(self):
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._ipc_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._ipc_server.bind(str(SOCKET_PATH))
        os.chmod(str(SOCKET_PATH), 0o600)
        self._ipc_server.listen(8)
        self._ipc_server.settimeout(1.0)

        thread = threading.Thread(target=self._ipc_loop, daemon=True)
        thread.start()

    def _ipc_loop(self):
        while self._running:
            try:
                conn, _ = self._ipc_server.accept()
                data = conn.recv(256).decode("utf-8").strip()
                response = self._handle_ipc_command(data)
                conn.sendall(response.encode("utf-8"))
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_ipc_command(self, command: str) -> str:
        if command == "toggle":
            GLib.idle_add(self.toggle_dictation)
            return "ok"
        elif command == "start":
            GLib.idle_add(self._start_dictation)
            return "ok"
        elif command == "stop":
            GLib.idle_add(self._stop_dictation)
            return "ok"
        elif command == "status":
            return "active" if self._dictation.is_running else "ready"
        elif command == "settings":
            GLib.idle_add(self._show_settings)
            return "ok"
        elif command == "quit":
            GLib.idle_add(self.quit)
            return "ok"
        return "unknown command"

    def _show_settings(self):
        self._settings.show()

    def _cleanup_ipc(self):
        if self._ipc_server:
            try:
                self._ipc_server.close()
            except Exception:
                pass
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink(missing_ok=True)
        if PID_PATH.exists():
            PID_PATH.unlink(missing_ok=True)

    def _write_pid(self):
        PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()))

    # ── Main Entry ───────────────────────────────────────────────────

    def run(self):
        self._write_pid()
        self._start_ipc_server()
        self._tray.set_state("ready")
        self._start_ptt_listener()
        log.info("Mint Dictation running (PID %d)", os.getpid())

        # Handle SIGTERM/SIGINT gracefully
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self.quit)

        Gtk.main()


def send_ipc_command(command: str) -> str:
    """Send a command to a running daemon via IPC socket."""
    if not SOCKET_PATH.exists():
        return ""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect(str(SOCKET_PATH))
        sock.sendall(command.encode("utf-8"))
        response = sock.recv(256).decode("utf-8")
        sock.close()
        return response
    except OSError:
        return ""


def is_daemon_running() -> bool:
    """Check if a mint-dictation daemon is already running."""
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        # Stale PID file
        PID_PATH.unlink(missing_ok=True)
        SOCKET_PATH.unlink(missing_ok=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Mint Dictation — voice dictation for Linux Mint"
    )
    parser.add_argument("--toggle", action="store_true", help="Toggle dictation on/off")
    parser.add_argument("--start", action="store_true", help="Start dictation")
    parser.add_argument("--stop", action="store_true", help="Stop dictation")
    parser.add_argument("--status", action="store_true", help="Print dictation status")
    parser.add_argument("--settings", action="store_true", help="Open the settings window")
    parser.add_argument("--app", action="store_true", help="Open the Mint Dictation app window")
    parser.add_argument("--quit", action="store_true", help="Quit the running daemon")
    parser.add_argument("--press", action="store_true", help="Start dictation (push-to-talk key down)")
    parser.add_argument("--release", action="store_true", help="Stop dictation (push-to-talk key up)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # If sending a command to an existing daemon
    if args.toggle or args.start or args.stop or args.status or args.quit or args.settings or args.app or args.press or args.release:
        if not is_daemon_running():
            if args.status:
                print("not running")
                return
            if args.quit:
                return  # nothing to quit
            if args.toggle or args.start or args.settings or args.app or args.press:
                # Auto-start the daemon, then send the command
                import subprocess as _sp
                import time as _time
                _sp.Popen(
                    [sys.executable, "-m", "mint_dictation.app"],
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    start_new_session=True,
                )
                # Wait up to 5 s for the IPC socket to appear
                deadline = _time.time() + 5.0
                while _time.time() < deadline:
                    if SOCKET_PATH.exists():
                        break
                    _time.sleep(0.1)
                else:
                    print("Daemon failed to start", file=sys.stderr)
                    sys.exit(1)
                _time.sleep(0.05)  # brief grace period
            else:
                print("Mint Dictation is not running.", file=sys.stderr)
                sys.exit(1)

        if args.toggle:
            resp = send_ipc_command("toggle")
        elif args.start:
            resp = send_ipc_command("start")
        elif args.stop:
            resp = send_ipc_command("stop")
        elif args.status:
            resp = send_ipc_command("status")
            print(resp)
            return
        elif args.quit:
            resp = send_ipc_command("quit")
        elif args.settings or args.app:
            resp = send_ipc_command("settings")
        elif args.press:
            resp = send_ipc_command("start")
        elif args.release:
            resp = send_ipc_command("stop")

        if resp != "ok" and not args.status:
            print(f"Command failed: {resp}", file=sys.stderr)
            sys.exit(1)
        return

    # Launch the daemon
    if is_daemon_running():
        print("Mint Dictation is already running.")
        sys.exit(0)

    app = MintDictationApp()
    app.run()


if __name__ == "__main__":
    main()
