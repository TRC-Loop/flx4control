"""
Mic loopback — captures a chosen microphone input and plays it through a
chosen speaker output at a configurable monitor volume.
Used for the crossfader "hear yourself" feature.
"""
from __future__ import annotations

import threading
from typing import Optional


class MicLoopback:
    """Software loopback: mic → speakers at a given monitor volume."""

    def __init__(self) -> None:
        self._volume: float = 0.0
        self._muted: bool = False
        self._input_device: Optional[str] = None   # None = system default
        self._output_device: Optional[str] = None  # None = system default
        self._stream = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_monitor_volume(self, volume: float) -> None:
        """Crossfader position: 0.0 = silent, 1.0 = full monitor."""
        volume = max(0.0, min(1.0, volume))
        with self._lock:
            self._volume = volume
            self._sync_stream()

    def set_muted(self, muted: bool) -> None:
        with self._lock:
            self._muted = muted
            self._sync_stream()

    def set_devices(
        self,
        input_device: Optional[str],
        output_device: Optional[str],
    ) -> None:
        """Change the mic/speaker device. Restarts the stream if running."""
        with self._lock:
            changed = (self._input_device != input_device
                       or self._output_device != output_device)
            self._input_device = input_device
            self._output_device = output_device
            if changed and self._stream is not None:
                self._stop_stream()
                self._sync_stream()

    def stop(self) -> None:
        with self._lock:
            self._stop_stream()

    # ------------------------------------------------------------------
    # Internals (call with _lock held)
    # ------------------------------------------------------------------

    def _sync_stream(self) -> None:
        should_run = self._volume > 0.001 and not self._muted
        if should_run and self._stream is None:
            self._start_stream()
        elif not should_run and self._stream is not None:
            self._stop_stream()

    def _device_index(self, name: str, kind: str) -> Optional[int]:
        """Return sounddevice index for device name, or None to use default."""
        if not name:
            return None
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if name.lower() in d["name"].lower():
                    if kind == "input" and d["max_input_channels"] > 0:
                        return i
                    if kind == "output" and d["max_output_channels"] > 0:
                        return i
        except Exception:
            pass
        return None

    def _start_stream(self) -> None:
        try:
            import sounddevice as sd
            import numpy as np

            in_idx = self._device_index(self._input_device or "", "input")
            out_idx = self._device_index(self._output_device or "", "output")

            def callback(indata, outdata, frames, time_info, status):  # noqa: ARG001
                vol = 0.0 if self._muted else self._volume
                # Mix all input channels to mono, then broadcast to all output channels.
                # This handles mic (1ch) -> speakers (2ch) and any other combination.
                mono = indata.mean(axis=1, keepdims=True) * vol
                outdata[:] = np.broadcast_to(mono, outdata.shape)

            self._stream = sd.Stream(
                device=(in_idx, out_idx),
                samplerate=44100,
                callback=callback,
                dtype="float32",
                latency="low",
            )
            self._stream.start()
        except Exception as exc:
            print(f"[loopback] Failed to start: {exc}")
            self._stream = None

    def _stop_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
