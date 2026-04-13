#!/usr/bin/env bash
set -euo pipefail

# ── VoxType Installer ───────────────────────────────────────────────────
# Installs nerd-dictation, VOSK model, system dependencies, and sets
# up VoxType for use on Linux (Cinnamon / X11).
# ────────────────────────────────────────────────────────────────────

INSTALL_DIR="$HOME/.local/share/voxtype"
NERD_DICT_DIR="$INSTALL_DIR/nerd-dictation"
MODEL_DIR="$HOME/.config/nerd-dictation/model"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/venv"

MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip"
MODEL_ZIP_NAME="vosk-model-en-us-0.22-lgraph"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. System packages ──────────────────────────────────────────────
info "Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    gir1.2-appindicator3-0.1 \
    xdotool \
    libportaudio2 \
    python3-venv \
    git \
    wget \
    unzip

# Detect audio system
if command -v pw-cat &>/dev/null; then
    INPUT_METHOD="PW-CAT"
    info "Detected PipeWire — will use pw-cat for audio capture"
elif command -v parec &>/dev/null; then
    INPUT_METHOD="PAREC"
    info "Detected PulseAudio — will use parec for audio capture"
    sudo apt-get install -y -qq pulseaudio-utils
else
    INPUT_METHOD="PAREC"
    warn "No audio capture tool found; installing pulseaudio-utils"
    sudo apt-get install -y -qq pulseaudio-utils
fi

# ── 2. Create virtual environment ───────────────────────────────────
info "Setting up Python virtual environment..."
mkdir -p "$INSTALL_DIR"

python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet vosk sounddevice numpy pycairo PyGObject pynput python-xlib

# ── 3. Clone nerd-dictation ─────────────────────────────────────────
if [ -d "$NERD_DICT_DIR" ]; then
    info "nerd-dictation already cloned, pulling latest..."
    cd "$NERD_DICT_DIR" && git pull --quiet && cd -
else
    info "Cloning nerd-dictation..."
    git clone --quiet https://github.com/ideasman42/nerd-dictation.git "$NERD_DICT_DIR"
fi

# ── 4. Download VOSK model ──────────────────────────────────────────
if [ -d "$MODEL_DIR" ] && [ -f "$MODEL_DIR/conf/model.conf" ]; then
    info "VOSK model already installed at $MODEL_DIR"
else
    info "Downloading VOSK model ($MODEL_ZIP_NAME, ~128 MB)..."
    TMP_DIR=$(mktemp -d)
    wget -q --show-progress -O "$TMP_DIR/model.zip" "$MODEL_URL"
    unzip -q "$TMP_DIR/model.zip" -d "$TMP_DIR"
    mkdir -p "$(dirname "$MODEL_DIR")"
    rm -rf "$MODEL_DIR"
    mv "$TMP_DIR/$MODEL_ZIP_NAME" "$MODEL_DIR"
    rm -rf "$TMP_DIR"
    info "Model installed to $MODEL_DIR"
fi

# ── 5. Install VoxType package ──────────────────────────────────────
info "Installing VoxType..."
pip install --quiet -e "$SCRIPT_DIR"

# ── 6. Create launcher script ───────────────────────────────────────
LAUNCHER="$HOME/.local/bin/voxtype"
mkdir -p "$HOME/.local/bin"

cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
VENV_DIR="$HOME/.local/share/voxtype/venv"
source "$VENV_DIR/bin/activate"
exec python -m voxtype.app "$@"
LAUNCHER_EOF
chmod +x "$LAUNCHER"
info "Launcher installed to $LAUNCHER"

# ── 7. Desktop autostart entry ──────────────────────────────────────
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/voxtype.desktop" << EOF
[Desktop Entry]
Type=Application
Name=VoxType
Comment=Voice dictation with system tray and overlay
Exec=$LAUNCHER
Icon=voxtype
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
info "Autostart entry created"

# ── 7b. Application menu entry ──────────────────────────────────────
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/voxtype.desktop" << EOF
[Desktop Entry]
Type=Application
Name=VoxType
Comment=Voice-to-text dictation tool
Exec=$LAUNCHER --app
Icon=voxtype
Categories=Utility;Accessibility;
Keywords=voice;dictation;speech;microphone;
Terminal=false
StartupNotify=false
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true
info "Application menu entry installed"

# ── 7c. Install icon into hicolor theme ─────────────────────────────
ICON_THEME_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_THEME_DIR"
cp "$SCRIPT_DIR/assets/icons/voxtype.svg" "$ICON_THEME_DIR/voxtype.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
info "Application icon installed to icon theme"

# ── 8. Create default config ────────────────────────────────────────
CONFIG_DIR="$HOME/.config/voxtype"
CONFIG_FILE="$CONFIG_DIR/config.ini"
if [ ! -f "$CONFIG_FILE" ]; then
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" << EOF
[dictation]
nerd_dictation_path = $NERD_DICT_DIR/nerd-dictation
vosk_model_dir = $MODEL_DIR
timeout = 0
continuous = true
numbers_as_digits = false
full_sentence = true
sample_rate = 44100
input_method = $INPUT_METHOD
EOF
    info "Default config written to $CONFIG_FILE"
fi

# ── 9. Install example text-processing config ───────────────────────
ND_CONFIG_DIR="$HOME/.config/nerd-dictation"
ND_CONFIG_FILE="$ND_CONFIG_DIR/nerd-dictation.py"
mkdir -p "$ND_CONFIG_DIR"
if [ -f "$SCRIPT_DIR/examples/nerd-dictation.py" ]; then
    if [ -f "$ND_CONFIG_FILE" ]; then
        cp "$ND_CONFIG_FILE" "${ND_CONFIG_FILE}.bak"
        info "Backed up existing text processor config to ${ND_CONFIG_FILE}.bak"
    fi
    cp "$SCRIPT_DIR/examples/nerd-dictation.py" "$ND_CONFIG_FILE"
    info "Text processing config installed to $ND_CONFIG_FILE"
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
info "============================================"
info " VoxType installed successfully!"
info "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Start the daemon:"
echo "       voxtype"
echo ""
echo "  2. Open VoxType from your app menu (or run: voxtype --app)"
echo "     Go to the Hotkey tab, click \"Set...\" to capture a key combo,"
echo "     then click \"Apply to Cinnamon\" to register it automatically."
echo ""
echo "  3. Press your hotkey and start talking!"
echo ""
