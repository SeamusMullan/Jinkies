"""Tests for FeedEditDialog validation in settings_dialog."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

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

    def _make_dialog_multi(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed.atom", name="Feed A"),
            Feed(url="https://b.com/feed.atom", name="Feed B"),
            Feed(url="https://c.com/feed.atom", name="Feed C"),
        ]
        config = AppConfig(
            poll_interval_secs=60,
            feeds=feeds,
            sound_map={},
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        dialog._load_values()
        return dialog, feeds

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

    def test_remove_multiple_feeds_confirmed(self, qtbot):
        """Confirming bulk removal deletes all selected feeds and their credentials."""
        from PySide6.QtCore import Qt as _Qt
        dialog, feeds = self._make_dialog_multi(qtbot)
        # Select feeds at row 0 and row 2
        dialog._feed_list.item(0).setSelected(True)
        dialog._feed_list.item(2).setSelected(True)

        with patch("src.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes) as mock_question, \
             patch("src.settings_dialog.delete_credentials") as mock_delete:
            dialog._remove_feed()

        # Only the two selected feeds should remain removed; one stays
        assert dialog._feed_list.count() == 1
        # Remaining item should be Feed B (row 1)
        remaining = dialog._feed_list.item(0).data(_Qt.ItemDataRole.UserRole)
        assert remaining.name == "Feed B"
        # Credentials must be cleared for both removed feeds
        assert mock_delete.call_count == 2
        deleted_urls = {call.args[0] for call in mock_delete.call_args_list}
        assert deleted_urls == {feeds[0].url, feeds[2].url}
        # The confirmation dialog should mention bulk removal
        title_arg = mock_question.call_args[0][1]
        msg_arg = mock_question.call_args[0][2]
        assert title_arg == "Remove Feeds"
        assert "2" in msg_arg

    def test_remove_multiple_feeds_cancelled(self, qtbot):
        """Cancelling bulk removal keeps all feeds in the list."""
        dialog, feeds = self._make_dialog_multi(qtbot)
        dialog._feed_list.item(0).setSelected(True)
        dialog._feed_list.item(2).setSelected(True)

        with patch("src.settings_dialog.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            dialog._remove_feed()

        assert dialog._feed_list.count() == 3
