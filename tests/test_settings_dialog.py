"""Tests for FeedEditDialog validation in settings_dialog."""

from __future__ import annotations

from unittest.mock import patch

from src.settings_dialog import FeedEditDialog


class TestFeedEditDialogValidation:
    """Tests for FeedEditDialog._validate_and_accept input validation."""

    def test_blank_name_rejected(self, qtbot):
        """OK with an empty name must show a warning and not accept."""
        dialog = FeedEditDialog()
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("")
        dialog.url_edit.setText("https://example.com/feed")

        with patch.object(dialog, "accept") as mock_accept, \
             patch("src.settings_dialog.QMessageBox.warning") as mock_warn:
            dialog._validate_and_accept()

        mock_warn.assert_called_once()
        assert "name" in mock_warn.call_args[0][2].lower()
        mock_accept.assert_not_called()

    def test_whitespace_only_name_rejected(self, qtbot):
        """OK with a whitespace-only name must show a warning and not accept."""
        dialog = FeedEditDialog()
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("   ")
        dialog.url_edit.setText("https://example.com/feed")

        with patch.object(dialog, "accept") as mock_accept, \
             patch("src.settings_dialog.QMessageBox.warning") as mock_warn:
            dialog._validate_and_accept()

        mock_warn.assert_called_once()
        mock_accept.assert_not_called()

    def test_blank_url_rejected(self, qtbot):
        """OK with an empty URL must show a warning and not accept."""
        dialog = FeedEditDialog()
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("My Feed")
        dialog.url_edit.setText("")

        with patch.object(dialog, "accept") as mock_accept, \
             patch("src.settings_dialog.QMessageBox.warning") as mock_warn:
            dialog._validate_and_accept()

        mock_warn.assert_called_once()
        mock_accept.assert_not_called()

    def test_invalid_url_scheme_rejected(self, qtbot):
        """OK with a non-http(s) URL must show a warning and not accept."""
        dialog = FeedEditDialog()
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("My Feed")
        dialog.url_edit.setText("file:///etc/passwd")

        with patch.object(dialog, "accept") as mock_accept, \
             patch("src.settings_dialog.QMessageBox.warning") as mock_warn:
            dialog._validate_and_accept()

        mock_warn.assert_called_once()
        mock_accept.assert_not_called()

    def test_valid_name_and_url_accepted(self, qtbot):
        """OK with valid name and URL must call accept without warnings."""
        dialog = FeedEditDialog()
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("My Feed")
        dialog.url_edit.setText("https://example.com/feed")

        with patch.object(dialog, "accept") as mock_accept, \
             patch("src.settings_dialog.QMessageBox.warning") as mock_warn:
            dialog._validate_and_accept()

        mock_warn.assert_not_called()
        mock_accept.assert_called_once()
