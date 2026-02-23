"""Tests for src.credential_store."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.credential_store import (
    _service_name,
    delete_credentials,
    get_credentials,
    store_credentials,
)


class TestServiceName:
    def test_service_name_format(self):
        assert _service_name("https://example.com/feed") == "jinkies:https://example.com/feed"


class TestStoreCredentials:
    @patch("src.credential_store.keyring")
    def test_store_credentials_https(self, mock_keyring):
        store_credentials("https://example.com/feed", "user", "token123")

        assert mock_keyring.set_password.call_count == 2
        mock_keyring.set_password.assert_any_call(
            "jinkies:https://example.com/feed", "username", "user",
        )
        mock_keyring.set_password.assert_any_call(
            "jinkies:https://example.com/feed", "token", "token123",
        )

    def test_store_credentials_http_rejected(self):
        with pytest.raises(ValueError, match="non-HTTPS"):
            store_credentials("http://example.com/feed", "user", "token123")

    def test_store_credentials_no_scheme_rejected(self):
        with pytest.raises(ValueError, match="non-HTTPS"):
            store_credentials("example.com/feed", "user", "token123")


class TestGetCredentials:
    @patch("src.credential_store.keyring")
    def test_get_existing_credentials(self, mock_keyring):
        mock_keyring.get_password.side_effect = lambda svc, key: {
            ("jinkies:https://example.com/feed", "username"): "user",
            ("jinkies:https://example.com/feed", "token"): "token123",
        }.get((svc, key))

        result = get_credentials("https://example.com/feed")
        assert result == ("user", "token123")

    @patch("src.credential_store.keyring")
    def test_get_missing_credentials(self, mock_keyring):
        mock_keyring.get_password.return_value = None

        result = get_credentials("https://example.com/feed")
        assert result is None

    @patch("src.credential_store.keyring")
    def test_get_partial_credentials_returns_none(self, mock_keyring):
        mock_keyring.get_password.side_effect = lambda svc, key: {
            ("jinkies:https://example.com/feed", "username"): "user",
            ("jinkies:https://example.com/feed", "token"): None,
        }.get((svc, key))

        result = get_credentials("https://example.com/feed")
        assert result is None


class TestDeleteCredentials:
    @patch("src.credential_store.keyring")
    def test_delete_existing_credentials(self, mock_keyring):
        delete_credentials("https://example.com/feed")

        assert mock_keyring.delete_password.call_count == 2
        mock_keyring.delete_password.assert_any_call(
            "jinkies:https://example.com/feed", "username",
        )
        mock_keyring.delete_password.assert_any_call(
            "jinkies:https://example.com/feed", "token",
        )

    @patch("src.credential_store.keyring")
    def test_delete_nonexistent_credentials(self, mock_keyring):
        import keyring.errors

        mock_keyring.delete_password.side_effect = keyring.errors.PasswordDeleteError
        mock_keyring.errors = keyring.errors

        # Should not raise
        delete_credentials("https://example.com/feed")
