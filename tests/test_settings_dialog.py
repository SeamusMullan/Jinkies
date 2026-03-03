"""Tests for FeedEditDialog validation in settings_dialog."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from src.models import AppConfig, Feed
from src.settings_dialog import FeedEditDialog, SettingsDialog


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


class TestSettingsDialogRemoveFeed:
    """Tests for SettingsDialog._remove_feed confirmation dialog."""

    def _make_dialog(self, qtbot):
        feed = Feed(url="https://example.com/feed.atom", name="Example Feed")
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[feed],
            sound_map={},
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        dialog._load_values()
        return dialog, feed

    def test_remove_feed_confirmed(self, qtbot):
        """Confirming removal deletes the feed from the list and clears credentials."""
        dialog, feed = self._make_dialog(qtbot)
        dialog._feed_list.setCurrentRow(0)

        with patch("src.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("src.settings_dialog.delete_credentials") as mock_delete:
            dialog._remove_feed()

        assert dialog._feed_list.count() == 0
        mock_delete.assert_called_once_with(feed.url)

    def test_remove_feed_cancelled(self, qtbot):
        """Cancelling the confirmation keeps the feed in the list."""
        dialog, _feed = self._make_dialog(qtbot)
        dialog._feed_list.setCurrentRow(0)

        with patch("src.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            dialog._remove_feed()

        assert dialog._feed_list.count() == 1
