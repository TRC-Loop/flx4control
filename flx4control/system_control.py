"""System control — volume, mic, mouse scroll, media keys, app management."""
from __future__ import annotations

import platform
import subprocess
from typing import Optional

_PLATFORM = platform.system()


# ===========================================================================
# Volume control (output)
# ===========================================================================

def set_output_volume(value: float) -> None:
    """Set system output volume. value: 0.0–1.0."""
    value = max(0.0, min(1.0, value))
    if _PLATFORM == "Darwin":
        subprocess.Popen(
            ["osascript", "-e", f"set volume output volume {int(value * 100)}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    elif _PLATFORM == "Windows":
        _win_set_output_volume(value)


def get_output_volume() -> float:
    """Return current system output volume as 0.0–1.0, or 0.0 on failure."""
    try:
        if _PLATFORM == "Darwin":
            r = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=2,
            )
            return int(r.stdout.strip()) / 100.0
        elif _PLATFORM == "Windows":
            return _win_get_output_volume()
    except Exception:
        pass
    return 0.0


# ===========================================================================
# Volume control (mic input)
# ===========================================================================

def set_mic_volume(value: float) -> None:
    """Set system microphone volume. value: 0.0–1.0."""
    value = max(0.0, min(1.0, value))
    if _PLATFORM == "Darwin":
        subprocess.Popen(
            ["osascript", "-e", f"set volume input volume {int(value * 100)}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    elif _PLATFORM == "Windows":
        _win_set_mic_volume(value)


def get_mic_volume() -> float:
    """Return current system mic/input volume as 0.0–1.0, or 0.0 on failure."""
    try:
        if _PLATFORM == "Darwin":
            r = subprocess.run(
                ["osascript", "-e", "input volume of (get volume settings)"],
                capture_output=True, text=True, timeout=2,
            )
            return int(r.stdout.strip()) / 100.0
        elif _PLATFORM == "Windows":
            return _win_get_mic_volume()
    except Exception:
        pass
    return 0.0


# ===========================================================================
# Mouse scroll
# ===========================================================================

def do_scroll(direction: int, amount: int = 3) -> None:
    """Scroll at the current mouse position. direction: +1=up, -1=down."""
    try:
        import pyautogui
        pyautogui.scroll(direction * amount)
    except Exception as exc:
        print(f"[scroll] {exc}")


# ===========================================================================
# Audio device enumeration
# ===========================================================================

def list_audio_inputs() -> list[tuple[int, str]]:
    """Return [(device_index, device_name)] for all available input devices."""
    try:
        import sounddevice as sd
        result = []
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                result.append((i, d.get("name", f"Device {i}")))
        return result
    except Exception:
        return []


def list_audio_outputs() -> list[tuple[int, str]]:
    """Return [(device_index, device_name)] for all available output devices."""
    try:
        import sounddevice as sd
        result = []
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_output_channels", 0) > 0:
                result.append((i, d.get("name", f"Device {i}")))
        return result
    except Exception:
        return []


# ===========================================================================
# Media keys
# ===========================================================================

def send_media_key(action: str) -> None:
    """
    Send a system media key.
    action: 'play_pause' | 'next' | 'previous'
    """
    try:
        from pynput.keyboard import Key, Controller
        key_map = {
            "play_pause": Key.media_play_pause,
            "next":       Key.media_next,
            "previous":   Key.media_previous,
        }
        key = key_map.get(action)
        if key:
            Controller().tap(key)
    except Exception as exc:
        print(f"[media] send_media_key({action}): {exc}")


def seek_media(direction: int) -> None:
    """Seek forward (direction > 0) or backward (direction < 0) with arrow keys."""
    try:
        from pynput.keyboard import Key, Controller
        Controller().tap(Key.right if direction > 0 else Key.left)
    except Exception as exc:
        print(f"[media] seek: {exc}")


# ===========================================================================
# Open applications
# ===========================================================================

def get_open_apps() -> list[str]:
    """Return sorted list of visible, user-facing application names."""
    try:
        if _PLATFORM == "Darwin":
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process '
                 'whose background only is false'],
                capture_output=True, text=True, timeout=5,
            )
            apps = [a.strip() for a in r.stdout.strip().split(",") if a.strip()]
            return sorted(set(apps))
        elif _PLATFORM == "Windows":
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 'Get-Process | Where-Object {$_.MainWindowTitle -ne ""} '
                 '| Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=5,
            )
            apps = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
            return sorted(set(apps))
    except Exception as exc:
        print(f"[apps] get_open_apps: {exc}")
    return []


def focus_app(app_name: str) -> None:
    """Bring an application window to the foreground."""
    try:
        if _PLATFORM == "Darwin":
            subprocess.Popen(
                ["osascript", "-e", f'tell application "{app_name}" to activate'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif _PLATFORM == "Windows":
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command",
                 f'(New-Object -ComObject WScript.Shell).AppActivate("{app_name}")'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception as exc:
        print(f"[apps] focus_app({app_name}): {exc}")


def get_app_volume(app_name: str) -> float:
    """Get per-application audio volume (Windows only). Returns 0.0–1.0."""
    if _PLATFORM != "Windows":
        return get_output_volume()
    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and _proc_matches(session.Process.name(), app_name):
                iface = session._ctl.QueryInterface(ISimpleAudioVolume)
                return float(iface.GetMasterVolume())
    except Exception as exc:
        print(f"[apps] get_app_volume: {exc}")
    return 0.0


def set_app_volume(app_name: str, volume: float) -> None:
    """Set per-application audio volume (Windows only). value: 0.0–1.0."""
    volume = max(0.0, min(1.0, volume))
    if _PLATFORM != "Windows":
        set_output_volume(volume)
        return
    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and _proc_matches(session.Process.name(), app_name):
                iface = session._ctl.QueryInterface(ISimpleAudioVolume)
                iface.SetMasterVolume(volume, None)
    except Exception as exc:
        print(f"[apps] set_app_volume: {exc}")


def _proc_matches(proc_name: str, app_name: str) -> bool:
    p = proc_name.lower().removesuffix(".exe")
    a = app_name.lower().removesuffix(".exe")
    return p == a or p.startswith(a) or a.startswith(p)


# ===========================================================================
# Windows helpers
# ===========================================================================

def _win_set_output_volume(value: float) -> None:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        cast(iface, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(value, None)
    except Exception as exc:
        print(f"[volume] Windows output: {exc}")


def _win_get_output_volume() -> float:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return float(cast(iface, POINTER(IAudioEndpointVolume)).GetMasterVolumeLevelScalar())
    except Exception:
        return 0.0


def _win_set_mic_volume(value: float) -> None:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        for dev in AudioUtilities.GetAllDevices():
            if getattr(dev, "flow", -1) == 1:
                try:
                    iface = dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    cast(iface, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(value, None)
                    return
                except Exception:
                    continue
    except Exception as exc:
        print(f"[volume] Windows mic: {exc}")


def _win_get_mic_volume() -> float:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        for dev in AudioUtilities.GetAllDevices():
            if getattr(dev, "flow", -1) == 1:
                try:
                    iface = dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    return float(cast(iface, POINTER(IAudioEndpointVolume)).GetMasterVolumeLevelScalar())
                except Exception:
                    continue
    except Exception:
        pass
    return 0.0
