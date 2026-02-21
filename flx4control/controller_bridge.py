"""
ControllerBridge — runs the DDJ-FLX4 in a background thread and
exposes its events as Qt signals for thread-safe GUI integration.
"""
from __future__ import annotations

import platform
import subprocess
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .config import Config
from . import system_control, audio_player
from .mic_loopback import MicLoopback


class ControllerBridge(QObject):
    # --- Connection ---
    controller_connected = Signal()
    controller_disconnected = Signal()

    # --- Pad / tab events ---
    pad_triggered = Signal(int, int)    # deck, pad
    tab_changed = Signal(int, int)      # deck, bank index

    # --- Media / program switcher ---
    browse_turned = Signal(int)         # steps (positive = CW, negative = CCW)
    program_load_pressed = Signal(int)  # deck (1 or 2)
    master_level_changed = Signal(float)  # 0.0–1.0
    play_state_changed = Signal(bool)   # True = playing

    def __init__(self, config: Config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.config = config
        self._controller = None
        self._current_bank: dict[int, int] = {1: 0, 2: 0}
        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Playback / mic state
        self._is_playing: bool = False
        self._mic_muted: bool = False
        self._mic_volume: float = 1.0   # last volume set via fader

        # Mic loopback (crossfader → hear yourself)
        self._loopback = MicLoopback()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._connect_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._loopback.stop()
        ctrl = self._controller
        if ctrl:
            try:
                ctrl.leds.all_off()
                ctrl.stop()
            except Exception:
                pass
            self._controller = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def current_bank(self, deck: int) -> int:
        return self._current_bank.get(deck, 0)

    def is_mic_muted(self) -> bool:
        return self._mic_muted

    def refresh_leds(self) -> None:
        """Re-send all pad, tab, and button LEDs from current state."""
        if not self._controller:
            return
        for deck in (1, 2):
            bank = self._current_bank[deck]
            self._update_tab_leds(deck, bank)
            self._update_pad_leds(deck, bank)
        self._update_play_pause_led()

    # ------------------------------------------------------------------
    # Connection loop (runs in self._thread)
    # ------------------------------------------------------------------

    def _connect_loop(self) -> None:
        while self._running:
            was_connected = False
            try:
                import flx4py
                ctrl = flx4py.DDJFlx4()
                self._controller = ctrl
                self._setup_callbacks(ctrl)
                ctrl.start()
                self._connected = True
                was_connected = True
                self.controller_connected.emit()
                self._reset_leds()

                # Heartbeat loop: also updates VU meters
                while self._running:
                    time.sleep(2)
                    try:
                        ctrl.leds.set_button("BROWSE_PRESS", on=False)
                    except Exception:
                        break   # USB disconnected

                    # Update VU meters (best-effort)
                    try:
                        ctrl.leds.set_level_meter(1, system_control.get_output_volume())
                    except Exception:
                        pass
                    try:
                        ctrl.leds.set_level_meter(2, system_control.get_mic_volume())
                    except Exception:
                        pass

            except RuntimeError:
                pass   # device not found yet
            except Exception as exc:
                print(f"[controller] {exc}")
            finally:
                self._connected = False
                ctrl = self._controller
                if ctrl:
                    try:
                        ctrl.stop()
                    except Exception:
                        pass
                    self._controller = None
                if was_connected and self._running:
                    self.controller_disconnected.emit()

            if self._running:
                time.sleep(5)

    # ------------------------------------------------------------------
    # LED helpers
    # ------------------------------------------------------------------

    def _reset_leds(self) -> None:
        ctrl = self._controller
        if not ctrl:
            return
        ctrl.leds.all_off()
        for deck in (1, 2):
            bank = self._current_bank[deck]
            self._update_tab_leds(deck, bank)
            self._update_pad_leds(deck, bank)
        self._update_play_pause_led()

    def _update_tab_leds(self, deck: int, active_bank: int) -> None:
        ctrl = self._controller
        if not ctrl:
            return
        for tab in range(4):
            try:
                ctrl.leds.set_tab(deck, tab, tab == active_bank)
            except Exception:
                pass

    def _update_pad_leds(self, deck: int, bank: int) -> None:
        ctrl = self._controller
        if not ctrl:
            return
        for pad in range(8):
            action = self.config.get_pad_action(deck, bank, pad)
            lit = self._action_led_state(action)
            try:
                ctrl.leds.set_pad(deck, pad, lit)
            except Exception:
                pass

    def _action_led_state(self, action: dict) -> bool:
        atype = action.get("type", "none")
        if atype == "none":
            return False
        if atype == "mute_mic":
            return not self._mic_muted   # lit = mic active (not muted)
        return True

    def _update_play_pause_led(self) -> None:
        ctrl = self._controller
        if not ctrl:
            return
        for deck in (1, 2):
            try:
                ctrl.leds.set_button("PLAY_PAUSE", on=self._is_playing, deck=deck)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def _setup_callbacks(self, ctrl) -> None:
        import flx4py

        # ---- Performance pads ----
        @ctrl.on_pad(pressed=True)
        def on_pad_press(event: flx4py.PadEvent) -> None:
            deck = event.deck
            pad = event.pad
            bank = self._current_bank.get(deck, 0)
            action = self.config.get_pad_action(deck, bank, pad)
            self._execute_action(action)
            self.pad_triggered.emit(deck, pad)

        # ---- Tab / bank buttons ----
        @ctrl.on_tab(pressed=True)
        def on_tab_press(event: flx4py.TabEvent) -> None:
            deck = event.deck
            tab = event.tab
            self._current_bank[deck] = tab
            self._update_tab_leds(deck, tab)
            self._update_pad_leds(deck, tab)
            self.tab_changed.emit(deck, tab)

        # ---- PLAY/PAUSE button → media control ----
        @ctrl.on_button("PLAY_PAUSE", pressed=True)
        def on_play_pause(event: flx4py.ButtonEvent) -> None:
            self._toggle_play_pause()

        # ---- Channel faders → output / mic volume ----
        @ctrl.on_knob("CH_FADER")
        def on_ch_fader(event: flx4py.KnobEvent) -> None:
            vol_cfg = self.config.get_volume_fader()
            mic_cfg = self.config.get_mic_fader()
            if vol_cfg.get("control") == "CH_FADER" and event.deck == vol_cfg.get("deck"):
                system_control.set_output_volume(event.value)
            if mic_cfg.get("control") == "CH_FADER" and event.deck == mic_cfg.get("deck"):
                self._mic_volume = event.value
                if not self._mic_muted:
                    system_control.set_mic_volume(event.value)

        # ---- Master Level knob → output volume (if configured) + signal ----
        @ctrl.on_knob("MASTER_LEVEL")
        def on_master_level(event: flx4py.KnobEvent) -> None:
            vol_cfg = self.config.get_volume_fader()
            if vol_cfg.get("control") == "MASTER_LEVEL":
                system_control.set_output_volume(event.value)
            self.master_level_changed.emit(event.value)

        # ---- Crossfader → mic loopback (hear yourself) ----
        @ctrl.on_knob("CROSSFADER")
        def on_crossfader(event: flx4py.KnobEvent) -> None:
            self._loopback.set_monitor_volume(event.value)

        # ---- Jog wheels ----
        @ctrl.on_jog()
        def on_jog(event: flx4py.JogEvent) -> None:
            scroll_deck = self.config.get_scroll_deck()
            if scroll_deck != 0 and event.deck == scroll_deck:
                # Scroll
                sensitivity = self.config.get_scroll_sensitivity()
                direction = event.direction
                if self.config.get_scroll_reverse():
                    direction = -direction
                system_control.do_scroll(direction, sensitivity)
            else:
                # Media seek (the other jog wheel)
                system_control.seek_media(event.direction)

        # ---- Browse encoder → program switcher ----
        @ctrl.on_browse()
        def on_browse(event: flx4py.BrowseEvent) -> None:
            self.browse_turned.emit(event.steps)

        # ---- Browse LOAD buttons → program selection ----
        @ctrl.on_button("BROWSE_LOAD", pressed=True)
        def on_browse_load(event: flx4py.ButtonEvent) -> None:
            self.program_load_pressed.emit(event.deck)

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, action: dict) -> None:
        atype = action.get("type", "none")
        if atype == "app":
            self._launch_app(action.get("path", ""))
        elif atype == "sound":
            self._play_sound(action.get("file", ""))
        elif atype == "media_play_pause":
            self._toggle_play_pause()
        elif atype == "media_next":
            system_control.send_media_key("next")
        elif atype == "media_previous":
            system_control.send_media_key("previous")
        elif atype == "mute_mic":
            self._toggle_mic_mute()

    def _toggle_play_pause(self) -> None:
        system_control.send_media_key("play_pause")
        self._is_playing = not self._is_playing
        self._update_play_pause_led()
        self.play_state_changed.emit(self._is_playing)

    def _toggle_mic_mute(self) -> None:
        self._mic_muted = not self._mic_muted
        if self._mic_muted:
            system_control.set_mic_volume(0.0)
        else:
            system_control.set_mic_volume(self._mic_volume)
        self._loopback.set_muted(self._mic_muted)
        # Update mute-mic pad LEDs in active banks
        for deck in (1, 2):
            bank = self._current_bank[deck]
            self._update_pad_leds(deck, bank)

    def _launch_app(self, path: str) -> None:
        if not path:
            return
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen([path])
        except Exception as exc:
            print(f"[controller] launch '{path}': {exc}")

    def _play_sound(self, filename: str) -> None:
        if not filename:
            return
        path = self.config.resolve_sound_path(filename)
        if path:
            audio_player.play_sound(path)
        else:
            print(f"[controller] Sound not found: {filename}")
