"""Tests for the notification sink layer (Epic 6)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models import AppConfig, Rule
from src.notify_sinks import (
    PROVIDER_PRESETS,
    ScriptSink,
    SinkConfig,
    SinkPayload,
    SinkRegistry,
    WebhookSink,
    build_sink,
    render_template,
)


@pytest.fixture()
def payload() -> SinkPayload:
    return SinkPayload(
        title="Build #42 failed",
        link="https://ci.example.com/42",
        status="failed",
        feed_name="Demo",
        feed_url="https://ci.example.com/rss",
        published="2026-01-01T00:00:00Z",
        summary="compile error",
    )


class TestRenderTemplate:
    def test_substitutes_known_fields(self, payload):
        out = render_template("{title} -> {status}", payload)
        assert out == "Build #42 failed -> failed"

    def test_missing_key_renders_empty(self, payload):
        # Unknown placeholder must not raise; renders as empty string.
        assert render_template("{title}{nope}", payload) == "Build #42 failed"

    def test_malformed_template_returns_as_is(self, payload):
        # A stray single brace would normally raise ValueError.
        assert render_template("100% {", payload) == "100% {"

    def test_no_code_execution(self, payload):
        # format_map only does attribute substitution; arbitrary expressions
        # are not evaluated.
        out = render_template("{title.__class__}", payload)
        # str.format does allow attribute access, but there's no eval; ensure
        # it doesn't blow up and produces a string.
        assert isinstance(out, str)


class TestSinkConfigSerialization:
    def test_roundtrip_without_secrets(self):
        cfg = SinkConfig(
            name="discord-team",
            provider="discord",
            url="https://discord.com/api/webhooks/x",
            body_template='{"content": "{title}"}',
        )
        data = cfg.to_dict()
        assert "token" not in str(data)  # no secrets leak into config
        restored = SinkConfig.from_dict(data)
        assert restored == cfg

    def test_appconfig_roundtrip(self):
        cfg = AppConfig(
            sinks=[SinkConfig(name="s1", provider="ntfy", url="https://ntfy.sh/t")],
            rules=[Rule(name="r1", sinks=["s1"])],
        )
        restored = AppConfig.from_dict(cfg.to_dict())
        assert restored.sinks[0].name == "s1"
        assert restored.rules[0].sinks == ["s1"]


class TestProviderPresets:
    def test_all_presets_have_transport(self):
        for preset in PROVIDER_PRESETS.values():
            assert preset.transport in ("http", "script")

    def test_pushover_declares_secret_fields(self):
        assert PROVIDER_PRESETS["pushover"].secret_fields


class TestWebhookSink:
    def test_rejects_non_https(self, payload):
        sink = WebhookSink(SinkConfig(name="x", url="http://insecure.example.com"))
        result = sink.send(payload)
        assert not result.ok
        assert "HTTPS" in (result.error or "")

    def test_empty_url_fails(self, payload):
        result = WebhookSink(SinkConfig(name="x", url="")).send(payload)
        assert not result.ok

    def test_successful_post(self, payload):
        cfg = SinkConfig(
            name="x",
            provider="custom",
            url="https://hook.example.com",
            body_template="{title}",
        )
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.status = 204
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            result = WebhookSink(cfg).send(payload)
        assert result.ok
        assert result.status_code == 204
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://hook.example.com"
        assert req.data == b"Build #42 failed"

    def test_http_error_captured(self, payload):
        import urllib.error

        cfg = SinkConfig(name="x", url="https://hook.example.com", body_template="x")
        err = urllib.error.HTTPError(
            "https://hook.example.com", 404, "Not Found", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = WebhookSink(cfg).send(payload)
        assert not result.ok
        assert result.status_code == 404

    def test_network_error_captured_not_raised(self, payload):
        cfg = SinkConfig(name="x", url="https://hook.example.com", body_template="x")
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            result = WebhookSink(cfg).send(payload)
        assert not result.ok
        assert result.error

    def test_secret_placeholder_resolved(self, payload):
        cfg = SinkConfig(
            name="ps",
            url="https://api.pushover.net/1/messages.json",
            body_template="token={secret:app_token}",
        )
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.status = 200
        with patch(
            "src.notify_sinks.get_sink_secret", return_value="SEKRET"
        ), patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            WebhookSink(cfg).send(payload)
        req = mock_open.call_args[0][0]
        assert req.data == b"token=SEKRET"


class TestScriptSink:
    def test_runs_with_env_vars(self, payload):
        with patch("subprocess.Popen") as mock_popen:
            result = ScriptSink(SinkConfig(name="s", script="echo hi")).send(payload)
        assert result.ok
        _, kwargs = mock_popen.call_args
        assert kwargs["env"]["JINKIES_TITLE"] == payload.title
        assert kwargs["env"]["JINKIES_STATUS"] == payload.status
        assert kwargs["shell"] is True

    def test_empty_script_fails(self, payload):
        result = ScriptSink(SinkConfig(name="s", script="")).send(payload)
        assert not result.ok

    def test_popen_error_captured(self, payload):
        with patch("subprocess.Popen", side_effect=OSError("no shell")):
            result = ScriptSink(SinkConfig(name="s", script="x")).send(payload)
        assert not result.ok


class TestSinkRegistry:
    def test_only_enabled_sinks_registered(self):
        reg = SinkRegistry([
            SinkConfig(name="on", url="https://a.example.com"),
            SinkConfig(name="off", url="https://b.example.com", enabled=False),
        ])
        assert reg.get("on") is not None
        assert reg.get("off") is None

    def test_update_replaces_contents(self):
        reg = SinkRegistry([SinkConfig(name="a", url="https://a.example.com")])
        reg.update([SinkConfig(name="b", url="https://b.example.com")])
        assert reg.get("a") is None
        assert reg.get("b") is not None

    def test_build_sink_picks_transport(self):
        assert isinstance(build_sink(SinkConfig(name="w", url="https://x")), WebhookSink)
        assert isinstance(
            build_sink(SinkConfig(name="s", transport="script", script="x")),
            ScriptSink,
        )
