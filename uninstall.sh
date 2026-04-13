#!/usr/bin/env bash
set -euo pipefail

# ── VoxType Uninstaller ───────────────────────────────────────────────
# Removes VoxType and all installed files.
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
if command -v voxtype &>/dev/null; then
    voxtype --quit 2>/dev/null && info "Daemon stopped" || true
fi

# ── Launcher ──────────────────────────────────────────────────────────
LAUNCHER="$HOME/.local/bin/voxtype"
if [ -f "$LAUNCHER" ]; then
    rm -f "$LAUNCHER"
    removed "Launcher: $LAUNCHER"
fi

# ── Autostart entry ───────────────────────────────────────────────────
AUTOSTART="$HOME/.config/autostart/voxtype.desktop"
if [ -f "$AUTOSTART" ]; then
    rm -f "$AUTOSTART"
    removed "Autostart entry: $AUTOSTART"
fi

# ── Application menu entry ────────────────────────────────────────────
APP_ENTRY="$HOME/.local/share/applications/voxtype.desktop"
if [ -f "$APP_ENTRY" ]; then
    rm -f "$APP_ENTRY"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    removed "App menu entry: $APP_ENTRY"
fi

# ── Icons ─────────────────────────────────────────────────────────────
APP_ICON="$HOME/.local/share/icons/hicolor/scalable/apps/voxtype.svg"
if [ -f "$APP_ICON" ]; then
    rm -f "$APP_ICON"
    removed "App icon: $APP_ICON"
fi

STATUS_ICON_DIR="$HOME/.local/share/icons/hicolor/22x22/status"
for icon in "$STATUS_ICON_DIR"/vt-ready.png "$STATUS_ICON_DIR"/vt-active.png "$STATUS_ICON_DIR"/vt-error.png; do
    if [ -f "$icon" ]; then
        rm -f "$icon"
        removed "Tray icon: $icon"
    fi
done
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# ── Python venv + nerd-dictation ──────────────────────────────────────
INSTALL_DIR="$HOME/.local/share/voxtype"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    removed "Install directory: $INSTALL_DIR"
fi

# ── Cache / runtime files ─────────────────────────────────────────────
CACHE_DIR="$HOME/.cache/voxtype"
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    removed "Cache: $CACHE_DIR"
fi

# ── Configuration (only with --purge) ────────────────────────────────
if $PURGE; then
    CONFIG_DIR="$HOME/.config/voxtype"
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
info "VoxType uninstalled."
