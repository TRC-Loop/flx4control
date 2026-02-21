"""
Mic loopback — captures microphone input and plays it to the default output
at a configurable monitor volume.  Used for the crossfader "hear yourself" feature.
"""
from __future__ import annotations

import threading


class MicLoopback:
    """Software loopback: mic → speakers at a given volume (0.0 = silent, 1.0 = full)."""

    def __init__(self) -> None:
        self._volume: float = 0.0
        self._muted: bool = False
        self._stream = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_monitor_volume(self, volume: float) -> None:
        """Set the loopback level (crossfader position). 0.0 = off, 1.0 = full."""
        volume = max(0.0, min(1.0, volume))
        with self._lock:
            self._volume = volume
            self._sync_stream()

    def set_muted(self, muted: bool) -> None:
        """Hard mute/unmute (independent of volume level)."""
        with self._lock:
            self._muted = muted
            self._sync_stream()

    def stop(self) -> None:
        with self._lock:
            self._stop_stream()

    # ------------------------------------------------------------------
    # Internal helpers (call with _lock held)
    # ------------------------------------------------------------------

    def _sync_stream(self) -> None:
        should_run = self._volume > 0.001 and not self._muted
        if should_run and self._stream is None:
            self._start_stream()
        elif not should_run and self._stream is not None:
            self._stop_stream()

    def _start_stream(self) -> None:
        try:
            import sounddevice as sd

            def callback(indata, outdata, frames, time_info, status):  # noqa: ARG001
                vol = 0.0 if self._muted else self._volume
                outdata[:] = indata * vol

            self._stream = sd.Stream(
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
