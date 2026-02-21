#!/usr/bin/env bash
# =============================================================================
# FLX4 Control — Installer / Updater for macOS and Linux
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LAUNCHER="$SCRIPT_DIR/run.sh"

echo "╔══════════════════════════════════════════╗"
echo "║      FLX4 Control — Installer            ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Directory : $SCRIPT_DIR"

# --- Check Python -----------------------------------------------------------
find_python() {
    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || {
    echo ""
    echo "ERROR: Python 3.10 or newer is required."
    echo "  Download from: https://www.python.org/downloads/"
    exit 1
}

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "  Python    : $PY_VERSION ($PYTHON)"
echo ""

# --- Virtual environment ----------------------------------------------------
if [ -d "$VENV_DIR" ]; then
    echo "→ Updating existing virtual environment…"
else
    echo "→ Creating virtual environment…"
    "$PYTHON" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

echo "→ Upgrading pip…"
"$PIP" install --upgrade pip --quiet

# --- Dependencies -----------------------------------------------------------
echo "→ Installing / updating dependencies…"
"$PIP" install \
    "flx4py" \
    "PySide6>=6.5" \
    "pygame>=2.0" \
    "pyautogui" \
    "pynput" \
    "sounddevice" \
    --quiet

echo "  Done."
echo ""

# --- Launcher script --------------------------------------------------------
cat > "$LAUNCHER" << 'LAUNCH_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py" "$@"
LAUNCH_EOF
chmod +x "$LAUNCHER"
echo "→ Launcher created: run.sh"

# --- macOS: .app bundle -----------------------------------------------------
if [[ "$OSTYPE" == "darwin"* ]]; then
    APP_BUNDLE="$SCRIPT_DIR/FLX4 Control.app"
    MACOS_DIR="$APP_BUNDLE/Contents/MacOS"
    RESOURCES_DIR="$APP_BUNDLE/Contents/Resources"

    mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

    cat > "$MACOS_DIR/FLX4Control" << APPEOF
#!/usr/bin/env bash
BUNDLE_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/../.." && pwd)"
# The actual project is one level up (the .app is inside the project folder)
PROJECT_DIR="\$(dirname "\$BUNDLE_DIR")"
exec "\$PROJECT_DIR/.venv/bin/python" "\$PROJECT_DIR/main.py"
APPEOF
    chmod +x "$MACOS_DIR/FLX4Control"

    cat > "$APP_BUNDLE/Contents/Info.plist" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>FLX4 Control</string>
    <key>CFBundleDisplayName</key><string>FLX4 Control</string>
    <key>CFBundleIdentifier</key><string>com.flx4control.app</string>
    <key>CFBundleVersion</key><string>1.0.0</string>
    <key>CFBundleShortVersionString</key><string>1.0.0</string>
    <key>CFBundleExecutable</key><string>FLX4Control</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSAppleEventsUsageDescription</key><string>FLX4 Control uses AppleScript to adjust system volume.</string>
</dict>
</plist>
PLISTEOF

    echo "→ macOS app bundle created: FLX4 Control.app"
    echo ""
    echo "┌─────────────────────────────────────────────┐"
    echo "│  macOS Permissions Required                 │"
    echo "│                                             │"
    echo "│  For SCROLLING to work, grant Accessibility │"
    echo "│  access to Terminal (or the .app):          │"
    echo "│                                             │"
    echo "│  System Settings → Privacy & Security       │"
    echo "│  → Accessibility → add Terminal or the app  │"
    echo "└─────────────────────────────────────────────┘"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Installation complete!                  ║"
echo "║                                          ║"
echo "║  To start: ./run.sh                      ║"
if [[ "$OSTYPE" == "darwin"* ]]; then
echo "║  Or: double-click 'FLX4 Control.app'     ║"
fi
echo "╚══════════════════════════════════════════╝"
