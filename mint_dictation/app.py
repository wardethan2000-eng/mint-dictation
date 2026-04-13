import argparse
import logging
import os
import signal
import socket
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
        self._settings = SettingsWindow(self._config)
        self._tray = TrayIcon(
            self._config,
            on_toggle=self.toggle_dictation,
            on_settings=self._show_settings,
            on_quit=self.quit,
        )
        self._ipc_server = None
        self._running = True

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
            log.info("Dictation started")
        else:
            self._tray.set_state("error")
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

    def quit(self):
        log.info("Shutting down")
        self._running = False
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
        self._ipc_server.listen(1)
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
    except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
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
    parser.add_argument("--quit", action="store_true", help="Quit the running daemon")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # If sending a command to an existing daemon
    if args.toggle or args.start or args.stop or args.status or args.quit or args.settings:
        if not is_daemon_running():
            if args.status:
                print("not running")
                return
            if args.quit:
                return  # nothing to quit
            if args.toggle or args.start or args.settings:
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
        elif args.settings:
            resp = send_ipc_command("settings")

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
