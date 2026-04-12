import configparser
import os
from pathlib import Path


_DEFAULTS = {
    "nerd_dictation_path": os.path.expanduser(
        "~/.local/share/mint-dictation/nerd-dictation/nerd-dictation"
    ),
    "vosk_model_dir": os.path.expanduser("~/.config/nerd-dictation/model"),
    "timeout": "0",
    "continuous": "true",
    "numbers_as_digits": "false",
    "full_sentence": "true",
    "overlay_position": "top-center",
    "sample_rate": "44100",
}

_CONFIG_DIR = Path.home() / ".config" / "mint-dictation"
_CONFIG_FILE = _CONFIG_DIR / "config.ini"


class Config:
    def __init__(self):
        self._parser = configparser.ConfigParser()
        self._parser["dictation"] = dict(_DEFAULTS)
        self._load()

    def _load(self):
        if _CONFIG_FILE.exists():
            self._parser.read(_CONFIG_FILE)

    def save(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_FILE, "w") as f:
            self._parser.write(f)

    def get(self, key: str) -> str:
        return self._parser.get("dictation", key, fallback=_DEFAULTS.get(key, ""))

    def get_bool(self, key: str) -> bool:
        return self._parser.getboolean(
            "dictation", key, fallback=_DEFAULTS.get(key, "false").lower() == "true"
        )

    def set(self, key: str, value: str):
        self._parser.set("dictation", key, value)

    @property
    def nerd_dictation_path(self) -> str:
        return self.get("nerd_dictation_path")

    @property
    def vosk_model_dir(self) -> str:
        return self.get("vosk_model_dir")

    @property
    def icon_dir(self) -> Path:
        # Installed location or dev location
        pkg_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
        if pkg_dir.exists():
            return pkg_dir
        return Path("/usr/share/mint-dictation/icons")
