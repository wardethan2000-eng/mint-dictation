import logging
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

# Number of RMS history samples to keep for the waveform display
HISTORY_SIZE = 40


class AudioMonitor:
    """Captures real-time audio levels from the default input device for waveform display."""

    def __init__(self, on_level: Optional[Callable[[list[float]], None]] = None):
        self._on_level = on_level
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._levels: list[float] = [0.0] * HISTORY_SIZE

    @property
    def levels(self) -> list[float]:
        with self._lock:
            return list(self._levels)

    def start(self):
        if self._stream is not None:
            return
        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=44100,
                blocksize=1470,  # ~30 callbacks/sec at 44100 Hz
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            log.info("Audio monitor started")
        except Exception:
            log.exception("Failed to start audio monitor")
            self._stream = None

    def stop(self):
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            log.exception("Error stopping audio monitor")
        self._stream = None
        with self._lock:
            self._levels = [0.0] * HISTORY_SIZE
        log.info("Audio monitor stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            log.debug("Audio status: %s", status)
        rms = float(np.sqrt(np.mean(indata ** 2)))
        # Clamp and normalize to 0-1 range (typical speech RMS is 0.01-0.3)
        level = min(1.0, rms / 0.25)
        with self._lock:
            self._levels.pop(0)
            self._levels.append(level)
        if self._on_level:
            try:
                self._on_level(self.levels)
            except Exception:
                pass
