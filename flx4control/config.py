"""Configuration management — persists to JSON in the platform app-data directory."""
from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    app_dir = base / "flx4control"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_sounds_dir() -> Path:
    d = get_app_data_dir() / "sounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_BANKS: dict = {
    "deck1": {"0": {}, "1": {}, "2": {}, "3": {}},
    "deck2": {"0": {}, "1": {}, "2": {}, "3": {}},
}

DEFAULT_CONFIG: dict = {
    "version": 1,
    "banks": _DEFAULT_BANKS,
    # {"deck": 1, "control": "CH_FADER"} or {"deck": None, "control": "MASTER_LEVEL"}
    "volume_fader": {"deck": 1, "control": "CH_FADER"},
    "mic_fader": {"deck": 2, "control": "CH_FADER"},
    "scroll_deck": 1,         # 1, 2, or 0 = disabled
    "scroll_sensitivity": 3,
    "scroll_reverse": False,
    # Audio device names (None = system default)
    "audio_input_device": None,
    "audio_output_device": None,
    # One-time guides
    "windows_driver_guide_shown": False,
}


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------

class Config:
    """Thread-safe-ish JSON config (reads/writes protected by Python's GIL)."""

    def __init__(self) -> None:
        self._data: dict = {}
        self.load()

    # --- persistence ---

    def load(self) -> None:
        path = get_config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = {**DEFAULT_CONFIG, **loaded}
            except Exception:
                self._data = json.loads(json.dumps(DEFAULT_CONFIG))
        else:
            self._data = json.loads(json.dumps(DEFAULT_CONFIG))
            self.save()
        self._ensure_bank_structure()

    def save(self) -> None:
        path = get_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def _ensure_bank_structure(self) -> None:
        banks = self._data.setdefault("banks", {})
        for dk in ("deck1", "deck2"):
            deck_banks = banks.setdefault(dk, {})
            for i in range(4):
                deck_banks.setdefault(str(i), {})

    # --- pad actions ---

    def get_pad_action(self, deck: int, bank: int, pad: int) -> dict:
        return (
            self._data
            .get("banks", {})
            .get(f"deck{deck}", {})
            .get(str(bank), {})
            .get(str(pad), {"type": "none"})
        )

    def set_pad_action(self, deck: int, bank: int, pad: int, action: dict) -> None:
        banks = self._data.setdefault("banks", {})
        deck_banks = banks.setdefault(f"deck{deck}", {})
        bank_pads = deck_banks.setdefault(str(bank), {})
        if action.get("type", "none") == "none":
            bank_pads.pop(str(pad), None)
        else:
            bank_pads[str(pad)] = action
        self.save()

    # --- fader / volume ---

    def get_volume_fader(self) -> dict:
        return self._data.get("volume_fader", {"deck": 1, "control": "CH_FADER"})

    def set_volume_fader(self, deck: Optional[int], control: Optional[str]) -> None:
        self._data["volume_fader"] = {"deck": deck, "control": control}
        self.save()

    def get_mic_fader(self) -> dict:
        return self._data.get("mic_fader", {"deck": 2, "control": "CH_FADER"})

    def set_mic_fader(self, deck: Optional[int], control: Optional[str]) -> None:
        self._data["mic_fader"] = {"deck": deck, "control": control}
        self.save()

    # --- scroll ---

    def get_scroll_deck(self) -> int:
        return int(self._data.get("scroll_deck", 1))

    def set_scroll_deck(self, deck: int) -> None:
        self._data["scroll_deck"] = deck
        self.save()

    def get_scroll_sensitivity(self) -> int:
        return int(self._data.get("scroll_sensitivity", 3))

    def set_scroll_sensitivity(self, value: int) -> None:
        self._data["scroll_sensitivity"] = value
        self.save()

    def get_scroll_reverse(self) -> bool:
        return bool(self._data.get("scroll_reverse", False))

    def set_scroll_reverse(self, value: bool) -> None:
        self._data["scroll_reverse"] = value
        self.save()

    # --- audio devices ---

    def get_audio_input_device(self) -> Optional[str]:
        return self._data.get("audio_input_device")

    def set_audio_input_device(self, name: Optional[str]) -> None:
        self._data["audio_input_device"] = name
        self.save()

    def get_audio_output_device(self) -> Optional[str]:
        return self._data.get("audio_output_device")

    def set_audio_output_device(self, name: Optional[str]) -> None:
        self._data["audio_output_device"] = name
        self.save()

    # --- first-run flags ---

    def is_driver_guide_shown(self) -> bool:
        return bool(self._data.get("windows_driver_guide_shown", False))

    def mark_driver_guide_shown(self) -> None:
        self._data["windows_driver_guide_shown"] = True
        self.save()

    # --- sound file management ---

    def import_sound_file(self, source_path: str) -> str:
        """Copy a sound file into the app sounds dir and return the stored filename."""
        source = Path(source_path)
        dest = get_sounds_dir() / source.name
        counter = 1
        while dest.exists():
            dest = get_sounds_dir() / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        shutil.copy2(source, dest)
        return dest.name

    def resolve_sound_path(self, filename: str) -> Optional[Path]:
        """Return the full path to a stored sound file, or None if missing."""
        p = get_sounds_dir() / filename
        return p if p.exists() else None
