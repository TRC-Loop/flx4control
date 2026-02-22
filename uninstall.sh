#!/usr/bin/env bash
# =============================================================================
# FLX4 Control — Uninstaller for macOS and Linux
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║      FLX4 Control — Uninstaller          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Project directory : $SCRIPT_DIR"
echo ""

# Detect config directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    CFG_DIR="$HOME/Library/Application Support/flx4control"
else
    CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/flx4control"
fi

echo "  The following will be removed:"
[ -d "$SCRIPT_DIR/.venv" ]           && echo "    - .venv (virtual environment)"
[[ "$OSTYPE" == "darwin"* ]] && \
    [ -d "$SCRIPT_DIR/FLX4 Control.app" ] && echo "    - FLX4 Control.app"
[ -f "$SCRIPT_DIR/run.sh" ]          && echo "    - run.sh"
echo ""
echo "  User settings/sounds ($CFG_DIR)"
echo "  will be kept unless you choose to remove them below."
echo ""

read -r -p "Proceed with uninstall? (y/N): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Cancelled."
    exit 0
fi
echo ""

# ---------------------------------------------------------------------------
# Remove virtual environment
# ---------------------------------------------------------------------------
if [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "→ Removing virtual environment…"
    rm -rf "$SCRIPT_DIR/.venv"
    echo "  Done."
fi

# ---------------------------------------------------------------------------
# Remove macOS app bundle
# ---------------------------------------------------------------------------
if [[ "$OSTYPE" == "darwin"* ]]; then
    APP="$SCRIPT_DIR/FLX4 Control.app"
    if [ -d "$APP" ]; then
        echo "→ Removing FLX4 Control.app…"
        rm -rf "$APP"
        echo "  Done."
    fi
fi

# ---------------------------------------------------------------------------
# Remove launcher
# ---------------------------------------------------------------------------
if [ -f "$SCRIPT_DIR/run.sh" ]; then
    rm "$SCRIPT_DIR/run.sh"
    echo "→ Removed run.sh"
fi

# Remove generated icon files
rm -f "$SCRIPT_DIR/flx4control.ico" "$SCRIPT_DIR/flx4control.png"

# ---------------------------------------------------------------------------
# Optionally remove user config and sounds
# ---------------------------------------------------------------------------
echo ""
if [ -d "$CFG_DIR" ]; then
    echo "  User settings and sounds are at:"
    echo "    $CFG_DIR"
    echo ""
    read -r -p "Remove settings and sounds as well? (y/N): " RMCFG
    if [[ "$RMCFG" == "y" || "$RMCFG" == "Y" ]]; then
        rm -rf "$CFG_DIR"
        echo "  Settings and sounds removed."
    else
        echo "  Settings and sounds kept."
    fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  FLX4 Control has been uninstalled.      ║"
echo "║                                          ║"
echo "║  You can delete this project folder      ║"
echo "║  manually if you no longer need it.      ║"
echo "╚══════════════════════════════════════════╝"
