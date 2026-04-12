#!/usr/bin/env bash
set -euo pipefail

# ── Mint Dictation Uninstaller ───────────────────────────────────────
# Removes mint-dictation and all installed files.
# The VOSK model and nerd-dictation text-processing config are kept
# by default (they may be used by other tools).  Pass --purge to
# remove everything including configuration data.
# ────────────────────────────────────────────────────────────────────

PURGE=false
for arg in "$@"; do
    [[ "$arg" == "--purge" ]] && PURGE=true
done

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
removed() { echo -e "${RED}[REMOVED]${NC} $*"; }

# ── Stop running daemon ───────────────────────────────────────────────
if command -v mint-dictation &>/dev/null; then
    mint-dictation --quit 2>/dev/null && info "Daemon stopped" || true
fi

# ── Launcher ──────────────────────────────────────────────────────────
LAUNCHER="$HOME/.local/bin/mint-dictation"
if [ -f "$LAUNCHER" ]; then
    rm -f "$LAUNCHER"
    removed "Launcher: $LAUNCHER"
fi

# ── Autostart entry ───────────────────────────────────────────────────
AUTOSTART="$HOME/.config/autostart/mint-dictation.desktop"
if [ -f "$AUTOSTART" ]; then
    rm -f "$AUTOSTART"
    removed "Autostart entry: $AUTOSTART"
fi

# ── Application menu entry ────────────────────────────────────────────
APP_ENTRY="$HOME/.local/share/applications/mint-dictation.desktop"
if [ -f "$APP_ENTRY" ]; then
    rm -f "$APP_ENTRY"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    removed "App menu entry: $APP_ENTRY"
fi

# ── Python venv + nerd-dictation ──────────────────────────────────────
INSTALL_DIR="$HOME/.local/share/mint-dictation"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    removed "Install directory: $INSTALL_DIR"
fi

# ── Cache / runtime files ─────────────────────────────────────────────
CACHE_DIR="$HOME/.cache/mint-dictation"
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    removed "Cache: $CACHE_DIR"
fi

# ── Configuration (only with --purge) ────────────────────────────────
if $PURGE; then
    CONFIG_DIR="$HOME/.config/mint-dictation"
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        removed "Config: $CONFIG_DIR"
    fi

    ND_CONFIG="$HOME/.config/nerd-dictation/nerd-dictation.py"
    if [ -f "$ND_CONFIG" ]; then
        rm -f "$ND_CONFIG"
        removed "nerd-dictation text-processing config: $ND_CONFIG"
    fi

    VOSK_MODEL="$HOME/.config/nerd-dictation/model"
    if [ -d "$VOSK_MODEL" ]; then
        rm -rf "$VOSK_MODEL"
        removed "VOSK model: $VOSK_MODEL"
    fi
else
    warn "Config and VOSK model kept.  Run with --purge to remove them too."
fi

echo ""
info "Mint Dictation uninstalled."
