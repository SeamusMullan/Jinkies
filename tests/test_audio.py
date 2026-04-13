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

    def test_play_sound_file_override_missing(self, tmp_sounds_dir):
        """play() with a non-existent sound_file override should not raise."""
        player = AudioPlayer({}, sounds_dir=tmp_sounds_dir)
        # Should not raise even when the override path does not exist
        player.play("new_entry", sound_file="/nonexistent/custom.wav")

    def test_play_sound_file_override_used(self, tmp_sounds_dir):
        """play() uses sound_file override instead of sound_map when provided."""
        custom_wav = tmp_sounds_dir / "custom.wav"
        generate_wav(custom_wav, frequency=880.0, duration=0.1)

        # Empty sound_map – would normally produce no sound
        player = AudioPlayer({}, sounds_dir=tmp_sounds_dir)
        # Should not raise; the override file exists so it should be loaded
        player.play("new_entry", sound_file=str(custom_wav))
        assert str(custom_wav) in player._effects

    def test_play_sound_file_override_cached_separately(self, tmp_sounds_dir):
        """The override path and the event-type key use separate cache slots."""
        default_wav = tmp_sounds_dir / "new_entry.wav"
        custom_wav = tmp_sounds_dir / "custom.wav"
        generate_wav(default_wav, frequency=440.0, duration=0.1)
        generate_wav(custom_wav, frequency=880.0, duration=0.1)

        player = AudioPlayer({"new_entry": "new_entry.wav"}, sounds_dir=tmp_sounds_dir)
        player.play("new_entry")
        player.play("new_entry", sound_file=str(custom_wav))

        # Both cache slots must be populated independently
        assert "new_entry" in player._effects
        assert str(custom_wav) in player._effects
