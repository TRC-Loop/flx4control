"""Sound playback via pygame.mixer — thread-safe, non-blocking."""
from __future__ import annotations

import threading
from pathlib import Path

_mixer_ready = False
_init_lock = threading.Lock()


def _ensure_mixer() -> bool:
    global _mixer_ready
    with _init_lock:
        if _mixer_ready:
            return True
        try:
            import pygame
            import pygame.mixer
            if not pygame.get_init():
                pygame.init()
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            _mixer_ready = True
            return True
        except Exception as exc:
            print(f"[audio] pygame mixer init failed: {exc}")
            return False


def play_sound(path: str | Path) -> None:
    """Play a sound file asynchronously (fire and forget)."""
    if not _ensure_mixer():
        return
    try:
        import pygame.mixer
        sound = pygame.mixer.Sound(str(path))
        sound.play()
    except Exception as exc:
        print(f"[audio] Failed to play {path}: {exc}")


def stop_all() -> None:
    """Stop all currently playing sounds."""
    global _mixer_ready
    if not _mixer_ready:
        return
    try:
        import pygame.mixer
        pygame.mixer.stop()
    except Exception:
        pass
