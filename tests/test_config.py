"""Tests for src.config persistence functions."""

from __future__ import annotations

import json

from src.config import load_config, load_state, save_config, save_state
from src.models import AppConfig


class TestConfig:
    def test_load_config_missing_file(self, tmp_config_dir):
        config = load_config(tmp_config_dir)
        assert isinstance(config, AppConfig)
        assert config.poll_interval_secs == 60
        assert config.feeds == []

    def test_save_and_load_config(self, tmp_config_dir, sample_config):
        save_config(sample_config, tmp_config_dir)
        loaded = load_config(tmp_config_dir)
        assert loaded.poll_interval_secs == sample_config.poll_interval_secs
        assert len(loaded.feeds) == 1
        assert loaded.feeds[0].url == "https://example.com/feed.atom"

    def test_config_json_readable(self, tmp_config_dir, sample_config):
        save_config(sample_config, tmp_config_dir)
        with open(tmp_config_dir / "config.json") as f:
            data = json.load(f)
        assert data["poll_interval_secs"] == 120

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        config = AppConfig()
        save_config(config, nested)
        assert (nested / "config.json").exists()


class TestState:
    def test_load_state_missing_file(self, tmp_config_dir):
        state = load_state(tmp_config_dir)
        assert "seen_ids" in state
        assert state["seen_ids"] == []

    def test_save_and_load_state(self, tmp_config_dir):
        state = {"seen_ids": ["id1", "id2", "id3"]}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert loaded["seen_ids"] == ["id1", "id2", "id3"]

    def test_state_preserves_extra_fields(self, tmp_config_dir):
        state = {"seen_ids": ["id1"], "errors_today": 5}
        save_state(state, tmp_config_dir)
        loaded = load_state(tmp_config_dir)
        assert loaded["errors_today"] == 5
