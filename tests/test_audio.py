"""Tests for src.audio module."""

from __future__ import annotations

import wave

from src.audio import AudioPlayer, ensure_default_sounds, generate_wav


class TestGenerateWav:
    def test_generates_valid_wav(self, tmp_path):
        path = tmp_path / "test.wav"
        generate_wav(path, frequency=440.0, duration=0.1)
        assert path.exists()

        with wave.open(str(path), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44100
            assert wf.getnframes() > 0

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "test.wav"
        generate_wav(path, frequency=220.0, duration=0.05)
        assert path.exists()


class TestEnsureDefaultSounds:
    def test_creates_default_sounds(self, tmp_sounds_dir):
        ensure_default_sounds(tmp_sounds_dir)
        assert (tmp_sounds_dir / "new_entry.wav").exists()
        assert (tmp_sounds_dir / "error.wav").exists()

    def test_does_not_overwrite_existing(self, tmp_sounds_dir):
        existing = tmp_sounds_dir / "new_entry.wav"
        existing.write_text("existing content")
        ensure_default_sounds(tmp_sounds_dir)
        assert existing.read_text() == "existing content"


class TestAudioPlayer:
    def test_init(self, tmp_sounds_dir):
        sound_map = {"new_entry": "new_entry.wav"}
        player = AudioPlayer(sound_map, sounds_dir=tmp_sounds_dir)
        assert player.sound_map == sound_map
        assert player.sounds_dir == tmp_sounds_dir

    def test_play_missing_event_type(self, tmp_sounds_dir):
        player = AudioPlayer({}, sounds_dir=tmp_sounds_dir)
        # Should not raise
        player.play("nonexistent")

    def test_play_missing_file(self, tmp_sounds_dir):
        player = AudioPlayer({"test": "missing.wav"}, sounds_dir=tmp_sounds_dir)
        # Should not raise
        player.play("test")
