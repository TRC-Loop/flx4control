# FLX4 Control

Use a **Pioneer DDJ-FLX4** as a fully configurable Stream Deck for your PC.
Control apps, sounds, media playback, mic volume, scrolling, and more — all
from the hardware pads and knobs you already have.

---

## Install

### Windows

Run this in **PowerShell** (no admin needed for the AppData option):

```powershell
$f="$env:TEMP\flx4_$(Get-Random).ps1"; iwr https://raw.githubusercontent.com/TRC-Loop/flx4control/main/install.ps1 -OutFile $f; powershell -ExecutionPolicy Bypass -File $f
```

Or this for **Command Prompt**:

```cmd
curl -fsSL -o "%TEMP%\flx4_install.ps1" https://raw.githubusercontent.com/TRC-Loop/flx4control/main/install.ps1 && powershell -ExecutionPolicy Bypass -File "%TEMP%\flx4_install.ps1"
```

The installer will ask whether to install to **AppData** (no admin required) or
**Program Files** (admin required, runs automatically with elevation).

### macOS / Linux

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/TRC-Loop/flx4control/main/install.sh)
```
---

## Uninstall

### Windows

```powershell
iwr https://raw.githubusercontent.com/TRC-Loop/flx4control/main/uninstall.bat -OutFile "$env:TEMP\flx4_uninstall.bat"; Start-Process "$env:TEMP\flx4_uninstall.bat"
```

Or from **Command Prompt**:

```cmd
curl -fsSL -o "%TEMP%\flx4_uninstall.bat" https://raw.githubusercontent.com/TRC-Loop/flx4control/main/uninstall.bat && "%TEMP%\flx4_uninstall.bat"
```

### macOS / Linux

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/TRC-Loop/flx4control/main/uninstall.sh)
```

> User settings and sounds (`~/Library/Application Support/flx4control` on
> macOS, `%APPDATA%\flx4control` on Windows) are kept by default and only
> removed if you choose to during uninstall.

---

## Requirements

| | |
|---|---|
| Python | 3.10 or newer |
| OS | Windows 10/11 or macOS 11+ |
| Hardware | Pioneer DDJ-FLX4 connected via USB |

No special audio driver is needed — the DDJ-FLX4 is USB class-compliant.
If it works in Rekordbox, it will work here.

---

## Features

| Control | Function |
|---|---|
| **Performance pads** | 4 banks × 8 pads per deck — open apps, play sounds, media keys, mute mic |
| **Tab buttons** | Switch banks (HOT CUE / PAD FX / BEAT JUMP / SAMPLER) with LED feedback |
| **PLAY/PAUSE & CUE** | Configurable per deck — media play/pause, next/prev, or any pad action |
| **Channel faders** | Control system output volume and mic input volume |
| **Master Level knob** | Controls volume of the selected app in the program switcher |
| **Crossfader** | Mic loopback monitor (left = silent, right = full) |
| **Jog wheel** | One deck scrolls the mouse; the other seeks through media |
| **Browse encoder** | Opens an app switcher overlay; navigate with the encoder |
| **BROWSE LOAD** | Deck 1 selects the highlighted app; Deck 2 dismisses the switcher |

---

## Configuration

Everything is configured through the GUI — no config files to edit manually.
The app lives in the system tray and does not need a window open to work.

- **Pads**: right-click or double-click a pad to assign an action
- **Settings**: bottom panel for volume faders, scroll, mic/speaker devices
- **Deck Buttons**: configure PLAY/PAUSE and CUE per deck in the Settings panel
- **Sounds**: imported automatically into the app-data sounds folder so they
  persist even if the original file is deleted

---

## Updating

Re-run the same install command. The installer always recreates the virtual
environment and replaces all app files. Your settings and sounds are never
touched (they live in a separate app-data directory).

---

## Building from source

```bash
git clone https://github.com/TRC-Loop/flx4control.git
cd flx4control
./install.sh          # macOS / Linux
# or
install.bat           # Windows
```
