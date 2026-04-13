import logging
import os
import signal
import subprocess
from typing import Optional

from .config import Config

log = logging.getLogger(__name__)


class DictationManager:
    """Manages the nerd-dictation subprocess lifecycle."""

    def __init__(self, config: Config):
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._active = False
        self._last_error: str = ""

    @property
    def is_running(self) -> bool:
        return self._active

    @property
    def last_error(self) -> str:
        return self._last_error

    def check_alive(self) -> bool:
        """Returns False if the process has unexpectedly exited."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def reset_after_crash(self):
        """Mark dictation as not running after an unexpected process exit."""
        self._active = False
        self._process = None

    def start(self) -> bool:
        if self._active:
            log.warning("Dictation already running")
            return False

        cmd = [self._config.nerd_dictation_path, "begin"]

        model_dir = self._config.vosk_model_dir
        if model_dir and os.path.isdir(model_dir):
            cmd.extend(["--vosk-model-dir", model_dir])

        if self._config.get_bool("continuous"):
            cmd.append("--continuous")

        if self._config.get_bool("full_sentence"):
            cmd.append("--full-sentence")

        if self._config.get_bool("numbers_as_digits"):
            cmd.append("--numbers-as-digits")

        timeout = self._config.get("timeout")
        if timeout and timeout != "0":
            cmd.extend(["--timeout", timeout])

        sample_rate = self._config.get("sample_rate")
        if sample_rate:
            cmd.extend(["--sample-rate", sample_rate])

        input_method = self._config.get("input_method")
        if input_method:
            cmd.extend(["--input", input_method])

        log.info("Starting dictation: %s", " ".join(cmd))

        # Run nerd-dictation through the venv Python so vosk is importable
        venv_python = os.path.expanduser(
            "~/.local/share/mint-dictation/venv/bin/python"
        )
        if os.path.exists(venv_python):
            cmd = [venv_python] + cmd

        env = None
        input_device = self._config.get("input_device")
        if input_device:
            env = os.environ.copy()
            env["PULSE_SOURCE"] = input_device

        self._last_error = ""
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                env=env,
            )
            self._active = True
            return True
        except FileNotFoundError:
            log.error(
                "nerd-dictation not found at %s", self._config.nerd_dictation_path
            )
            self._last_error = "nerd-dictation not found. Check the path in Settings."
            return False
        except Exception as exc:
            log.exception("Failed to start dictation")
            self._last_error = str(exc) or "Failed to start dictation."
            return False

    def stop(self) -> bool:
        if not self._active:
            log.warning("Dictation not running")
            return False

        cmd = [self._config.nerd_dictation_path, "end"]
        log.info("Stopping dictation")
        try:
            subprocess.run(cmd, timeout=5)
        except Exception:
            log.exception("Failed to send end command, killing process")
            self._kill()
        self._active = False
        self._process = None
        return True

    def cancel(self):
        if not self._active:
            return
        cmd = [self._config.nerd_dictation_path, "cancel"]
        log.info("Cancelling dictation")
        try:
            subprocess.run(cmd, timeout=5)
        except Exception:
            log.exception("Failed to send cancel command, killing process")
            self._kill()
        self._active = False
        self._process = None

    def _kill(self):
        if self._process is None:
            return
        try:
            pgid = os.getpgid(self._process.pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            log.exception("Failed to kill dictation process group")
        self._process = None

    def cleanup(self):
        """Kill any running dictation process. Call on app exit."""
        if self._active:
            self._kill()
            self._active = False
