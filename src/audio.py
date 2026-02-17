"""Audio playback for Jinkies feed monitor.

Wraps QSoundEffect for playing WAV audio cues on feed events.
Generates default sounds programmatically if WAV files are missing.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect


def get_sounds_dir() -> Path:
    """Get the path to the sounds directory.

    Handles both frozen (PyInstaller) and development environments.

    Returns:
        Path to the sounds directory.
    """
    import sys

    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "sounds"


def generate_wav(path: Path, frequency: float, duration: float, volume: float = 0.5) -> None:
    """Generate a simple sine wave WAV file.

    Args:
        path: Output file path.
        frequency: Tone frequency in Hz.
        duration: Duration in seconds.
        volume: Volume from 0.0 to 1.0.
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    max_amplitude = int(32767 * volume)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(n_samples):
            sample = max_amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)
            wav_file.writeframes(struct.pack("<h", int(sample)))


def ensure_default_sounds(sounds_dir: Path | None = None) -> None:
    """Generate default sound files if they don't exist.

    Args:
        sounds_dir: Override sounds directory path.
    """
    sounds_dir = sounds_dir or get_sounds_dir()
    defaults = {
        "new_entry.wav": (440.0, 0.3),
        "error.wav": (220.0, 0.5),
    }
    for filename, (freq, dur) in defaults.items():
        path = sounds_dir / filename
        if not path.exists():
            generate_wav(path, freq, dur)


class AudioPlayer:
    """Plays WAV audio cues for application events.

    Attributes:
        sound_map: Mapping of event type to WAV filename.
        sounds_dir: Directory containing WAV files.
    """

    def __init__(self, sound_map: dict[str, str], sounds_dir: Path | None = None) -> None:
        """Initialize the audio player.

        Args:
            sound_map: Mapping of event type to WAV filename.
            sounds_dir: Override sounds directory path.
        """
        self.sound_map = sound_map
        self.sounds_dir = sounds_dir or get_sounds_dir()
        self._effects: dict[str, QSoundEffect] = {}

    def play(self, event_type: str) -> None:
        """Play the sound associated with an event type.

        Args:
            event_type: The event type key (e.g. "new_entry", "error").
        """
        filename = self.sound_map.get(event_type)
        if not filename:
            return

        path = self.sounds_dir / filename
        if not path.exists():
            return

        if event_type not in self._effects:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(0.7)
            self._effects[event_type] = effect

        self._effects[event_type].play()
