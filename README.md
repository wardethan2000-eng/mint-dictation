# Mint Dictation

Offline voice dictation for Linux Mint. Toggle with a hotkey — text is typed live into whatever app has focus (VSCode, browser, terminal, etc.). A small floating overlay with a mic icon and waveform animation appears while recording.

Built on [nerd-dictation](https://github.com/ideasman42/nerd-dictation) + [VOSK](https://alphacephei.com/vosk/) for fully offline, privacy-respecting speech recognition.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Desktop](https://img.shields.io/badge/desktop-Cinnamon%20%2F%20X11-orange)

## Features

- **Hotkey toggle** — bind any key to start/stop dictation
- **Live typing** — text appears in the focused app as you speak (via `xdotool`)
- **Punctuation by voice** — say "period", "comma", "question mark", etc.
- **Overlay indicator** — floating window with pulsing mic icon + real-time waveform
- **System tray** — AppIndicator3 icon shows dictation state (ready / active / error)
- **Fully offline** — all speech recognition runs locally via VOSK, no data leaves your machine
- **Configurable** — sample rate, model path, input method, and text processing rules

## Requirements

- **Linux Mint** (Cinnamon desktop, X11)
- **PipeWire** or **PulseAudio** audio system
- A working microphone
- ~200 MB disk space (medium VOSK model)

## Installation

```bash
git clone https://github.com/wardethan2000-eng/mint-dictation.git ~/mint-dictation
cd ~/mint-dictation
chmod +x install.sh
./install.sh
```

The installer will:

1. Install system packages (`python3-gi`, `xdotool`, `libportaudio2`, etc.)
2. Create a Python virtual environment with VOSK, sounddevice, numpy, PyGObject
3. Clone [nerd-dictation](https://github.com/ideasman42/nerd-dictation)
4. Download the VOSK English model (~128 MB)
5. Install the `mint-dictation` launcher to `~/.local/bin/`
6. Create a default config at `~/.config/mint-dictation/config.ini`
7. Add an autostart entry for login

### Set Up a Hotkey

After installation, assign a keyboard shortcut to toggle dictation:

1. Open **System Settings → Keyboard → Shortcuts → Custom Shortcuts**
2. Click **Add custom shortcut**
3. Set **Name** to `Mint Dictation Toggle`
4. Set **Command** to:
   ```
   /home/YOUR_USERNAME/.local/bin/mint-dictation --toggle
   ```
5. Click **Add** and press your desired key combination (e.g. `Ctrl+Shift+D`)

## Usage

### Launch the Daemon

```bash
mint-dictation          # Start (tray icon appears)
mint-dictation -v       # Start with verbose logging
```

The daemon runs in the background with a system tray icon. It must be running before toggling dictation.

### CLI Commands

| Command | Description |
|---------|-------------|
| `mint-dictation --toggle` | Toggle dictation on/off (bind to hotkey) |
| `mint-dictation --start` | Start dictation |
| `mint-dictation --stop` | Stop dictation |
| `mint-dictation --status` | Print current status (`ready`, `active`, `not running`) |
| `mint-dictation --quit` | Quit the daemon |

### Overlay

When dictation is active, a small floating overlay appears at the top center of your screen:

- **Pulsing mic icon** — click to stop dictation
- **Waveform bars** — real-time audio level visualization

### Voice Commands

Say these words to insert punctuation:

| Say | Inserts |
|-----|---------|
| "period" / "full stop" | `.` |
| "comma" | `,` |
| "question mark" | `?` |
| "exclamation mark" | `!` |
| "colon" | `:` |
| "semicolon" | `;` |
| "open quote" / "close quote" | `"` |
| "open paren" / "close paren" | `(` / `)` |
| "new line" | newline character |
| "new paragraph" | double newline |
| "dash" | ` —` |
| "hyphen" | `-` |
| "ellipsis" | `...` |

Filler words (um, uh, hmm) are automatically removed.

## Configuration

### Main Config

Edit `~/.config/mint-dictation/config.ini`:

```ini
[dictation]
nerd_dictation_path = ~/.local/share/mint-dictation/nerd-dictation/nerd-dictation
vosk_model_dir = ~/.config/nerd-dictation/model
timeout = 0
continuous = true
full_sentence = true
sample_rate = 44100
input_method = PW-CAT
```

| Key | Description | Default |
|-----|-------------|---------|
| `nerd_dictation_path` | Path to nerd-dictation script | `~/.local/share/mint-dictation/nerd-dictation/nerd-dictation` |
| `vosk_model_dir` | Path to VOSK language model | `~/.config/nerd-dictation/model` |
| `timeout` | Auto-stop after N seconds of silence (0 = disabled) | `0` |
| `continuous` | Keep listening between sentences | `true` |
| `full_sentence` | Capitalize first word of each sentence | `true` |
| `sample_rate` | Audio sample rate in Hz | `44100` |
| `input_method` | Audio capture: `PW-CAT`, `PAREC`, or `SOX` | (auto) |

### Text Processing

Edit `~/.config/nerd-dictation/nerd-dictation.py` to customize:

- **Punctuation commands** — map spoken words to punctuation characters
- **Word replacements** — fix capitalization (e.g. "linux" → "Linux", "api" → "API")
- **Filler removal** — strip "um", "uh", etc.
- **Regex replacements** — multi-word pattern matching

See [`examples/nerd-dictation.py`](examples/nerd-dictation.py) for a full example config.

### Choosing a VOSK Model

| Model | Size | RAM | Accuracy |
|-------|------|-----|----------|
| [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models) | ~40 MB | ~300 MB | Basic |
| [vosk-model-en-us-0.22-lgraph](https://alphacephei.com/vosk/models) | ~128 MB | ~1 GB | **Good (recommended)** |
| [vosk-model-en-us-0.22](https://alphacephei.com/vosk/models) | ~1.8 GB | ~8 GB | Best (needs 16 GB+ RAM) |

To switch models, download and extract to `~/.config/nerd-dictation/model/` (replacing existing contents).

## Architecture

```
┌────────────────────────────────────────────────┐
│            mint-dictation (GTK3 app)           │
│                                                │
│  ┌──────────┐  ┌─────────┐  ┌──────────────┐  │
│  │Tray Icon │  │ Overlay │  │Audio Monitor │  │
│  │(AppInd3) │  │ (Cairo) │  │(sounddevice) │  │
│  └────┬─────┘  └────┬────┘  └──────┬───────┘  │
│       └──────┬───────┘       waveform only     │
│              │                      │          │
│     ┌────────┴────────┐             │          │
│     │DictationManager │             │          │
│     └────────┬────────┘             │          │
│              │ subprocess           │          │
│     ┌────────┴────────┐             │          │
│     │   IPC Server    │             │          │
│     │ (Unix socket)   │             │          │
│     └─────────────────┘             │          │
└──────────────┬──────────────────────┘          │
               │                                  │
    ┌──────────┴──────────┐                       │
    │   nerd-dictation    │                       │
    │  ┌──────┐ ┌───────┐ │                       │
    │  │ VOSK │ │xdotool│ │                       │
    │  └──┬───┘ └───────┘ │                       │
    │     │ audio          │                       │
    │  ┌──┴────┐           │                       │
    │  │pw-cat │           │                       │
    │  └───────┘           │                       │
    └──────────────────────┘                       │
```

**Communication flow:**

1. CLI (`--toggle`, `--status`) → Unix domain socket → daemon
2. Daemon → spawns `nerd-dictation begin` subprocess
3. `nerd-dictation` → spawns `pw-cat` for mic capture → pipes audio to VOSK
4. VOSK recognizes speech → nerd-dictation processes text → `xdotool` types into focused app
5. Audio monitor (separate read-only stream) feeds waveform levels to overlay

## Troubleshooting

### No text appears when speaking

- Verify mic works: `pw-record --format=s16 --channels=1 --rate=44100 /tmp/test.wav`
- Check `xdotool`: `which xdotool`
- Test nerd-dictation directly:
  ```bash
  ~/.local/share/mint-dictation/venv/bin/python \
    ~/.local/share/mint-dictation/nerd-dictation/nerd-dictation begin \
    --vosk-model-dir ~/.config/nerd-dictation/model \
    --input PW-CAT --output STDOUT --continuous --full-sentence
  ```

### PulseAudio / PipeWire

- **PipeWire** (default on newer Linux Mint): set `input_method = PW-CAT`
- **PulseAudio**: set `input_method = PAREC`
- Check which you have: `pactl info | grep "Server Name"`

### Overlay doesn't appear

- Run with verbose logging: `mint-dictation -v`
- Verify GTK3: `dpkg -l | grep gir1.2-gtk-3.0`

### Tray icon missing

```bash
sudo apt install gir1.2-appindicator3-0.1
```

### High memory usage

- Use the medium model (recommended): `vosk-model-en-us-0.22-lgraph` (~1 GB RAM)
- The large model needs ~8 GB+ free RAM and may freeze systems with ≤8 GB total

## Development

```bash
git clone https://github.com/wardethan2000-eng/mint-dictation.git
cd mint-dictation
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
python -m mint_dictation.app -v
```

## License

[GPL-3.0](LICENSE)
