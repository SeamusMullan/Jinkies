"""Tests for FeedEditDialog validation in settings_dialog."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QMessageBox

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


class TestSettingsDialogLoadValues:
    """Tests for SettingsDialog._load_values populating UI from config."""

    def test_load_values_populates_poll_interval(self, qtbot):
        """Dialog spinner reflects poll_interval_secs from config."""
        config = AppConfig(poll_interval_secs=42, feeds=[], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        assert dialog._interval_spinner.value() == 42

    def test_load_values_populates_sound_paths(self, qtbot):
        """Dialog sound fields reflect sound_map paths from config."""
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[],
            sound_map={"new_entry": "/sounds/new.wav", "error": "/sounds/err.wav"},
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        assert dialog._new_entry_sound.text() == "/sounds/new.wav"
        assert dialog._error_sound.text() == "/sounds/err.wav"

    def test_load_values_populates_notification_style(self, qtbot):
        """Dialog combobox reflects notification_style from config."""
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[],
            sound_map={},
            notification_style="custom",
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        assert dialog._notif_style.currentText() == "custom"

    def test_load_values_populates_feeds(self, qtbot):
        """Dialog feed list reflects feeds from config."""
        feed = Feed(url="https://example.com/feed.atom", name="Test Feed")
        config = AppConfig(poll_interval_secs=60, feeds=[feed], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        assert dialog._feed_list.count() == 1
        item_text = dialog._feed_list.item(0).text()
        assert "Test Feed" in item_text
        assert "https://example.com/feed.atom" in item_text


class TestSettingsDialogBrowseSound:
    """Tests for SettingsDialog._browse_sound file selection."""

    def _make_dialog(self, qtbot):
        config = AppConfig(poll_interval_secs=60, feeds=[], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        return dialog

    def test_browse_new_entry_sound_sets_path(self, qtbot):
        """Selecting a file sets the new-entry sound path."""
        dialog = self._make_dialog(qtbot)

        with patch("src.settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("/sounds/new.wav", "WAV Files (*.wav)")):
            dialog._browse_sound("new_entry")

        assert dialog._new_entry_sound.text() == "/sounds/new.wav"

    def test_browse_error_sound_sets_path(self, qtbot):
        """Selecting a file sets the error sound path."""
        dialog = self._make_dialog(qtbot)

        with patch("src.settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("/sounds/err.wav", "WAV Files (*.wav)")):
            dialog._browse_sound("error")

        assert dialog._error_sound.text() == "/sounds/err.wav"

    def test_browse_cancelled_does_not_change_path(self, qtbot):
        """Cancelling the file dialog leaves the sound path unchanged."""
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[],
            sound_map={"new_entry": "/existing.wav"},
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        with patch("src.settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("", "")):
            dialog._browse_sound("new_entry")

        assert dialog._new_entry_sound.text() == "/existing.wav"


class TestSettingsDialogSaveAndAccept:
    """Tests for SettingsDialog._save_and_accept persisting UI values to config."""

    def _make_dialog(self, qtbot, **kwargs):
        config = AppConfig(poll_interval_secs=60, feeds=[], sound_map={}, **kwargs)
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        return dialog, config

    def test_save_and_accept_updates_poll_interval(self, qtbot):
        """Changed spinner value is written to config.poll_interval_secs."""
        dialog, config = self._make_dialog(qtbot)
        dialog._interval_spinner.setValue(120)

        with patch.object(dialog, "accept"):
            dialog._save_and_accept()

        assert config.poll_interval_secs == 120

    def test_save_and_accept_updates_notification_style(self, qtbot):
        """Changed combobox selection is written to config.notification_style."""
        dialog, config = self._make_dialog(qtbot)
        dialog._notif_style.setCurrentText("custom")

        with patch.object(dialog, "accept"):
            dialog._save_and_accept()

        assert config.notification_style == "custom"

    def test_save_and_accept_updates_sound_paths(self, qtbot):
        """Sound path fields are written to config.sound_map."""
        config = AppConfig(
            poll_interval_secs=60,
            feeds=[],
            sound_map={"new_entry": "/old_new.wav", "error": "/old_err.wav"},
        )
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        # Use _browse_sound mock to update the readonly fields
        with patch("src.settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("/sounds/new.wav", "")):
            dialog._browse_sound("new_entry")
        with patch("src.settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("/sounds/err.wav", "")):
            dialog._browse_sound("error")

        with patch.object(dialog, "accept"):
            dialog._save_and_accept()

        assert config.sound_map["new_entry"] == "/sounds/new.wav"
        assert config.sound_map["error"] == "/sounds/err.wav"

    def test_save_and_accept_preserves_feeds(self, qtbot):
        """Feeds in the list widget are written back to config.feeds."""
        feed = Feed(url="https://example.com/feed.atom", name="Keep Me")
        config = AppConfig(poll_interval_secs=60, feeds=[feed], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)

        with patch.object(dialog, "accept"):
            dialog._save_and_accept()

        assert len(config.feeds) == 1
        assert config.feeds[0].url == "https://example.com/feed.atom"

    def test_save_and_accept_calls_accept(self, qtbot):
        """_save_and_accept closes the dialog by calling accept()."""
        dialog, _ = self._make_dialog(qtbot)

        with patch.object(dialog, "accept") as mock_accept:
            dialog._save_and_accept()

        mock_accept.assert_called_once()


class TestSettingsDialogAddFeed:
    """Tests for SettingsDialog._add_feed feed creation flow."""

    def _make_dialog(self, qtbot):
        config = AppConfig(poll_interval_secs=60, feeds=[], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        return dialog

    def test_add_feed_accepted_appends_to_list(self, qtbot):
        """Accepting the add-feed dialog appends the new feed to the list."""
        dialog = self._make_dialog(qtbot)

        mock_feed_dialog = MagicMock()
        mock_feed_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_feed_dialog.url_edit.text.return_value = "https://example.com/feed.atom"
        mock_feed_dialog.name_edit.text.return_value = "Example Feed"
        mock_feed_dialog.auth_user_edit.text.return_value = ""
        mock_feed_dialog.auth_token_edit.text.return_value = ""

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_feed_dialog):
            dialog._add_feed()

        assert dialog._feed_list.count() == 1
        item_text = dialog._feed_list.item(0).text()
        assert "Example Feed" in item_text
        assert "https://example.com/feed.atom" in item_text

    def test_add_feed_cancelled_does_not_append(self, qtbot):
        """Cancelling the add-feed dialog leaves the list unchanged."""
        dialog = self._make_dialog(qtbot)

        mock_feed_dialog = MagicMock()
        mock_feed_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_feed_dialog):
            dialog._add_feed()

        assert dialog._feed_list.count() == 0

    def test_add_feed_with_credentials_stores_them(self, qtbot):
        """Providing auth credentials when adding a feed calls store_credentials."""
        dialog = self._make_dialog(qtbot)

        mock_feed_dialog = MagicMock()
        mock_feed_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_feed_dialog.url_edit.text.return_value = "https://secure.example.com/feed"
        mock_feed_dialog.name_edit.text.return_value = "Secure Feed"
        mock_feed_dialog.auth_user_edit.text.return_value = "user"
        mock_feed_dialog.auth_token_edit.text.return_value = "token123"

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_feed_dialog), \
             patch("src.settings_dialog.store_credentials") as mock_store:
            dialog._add_feed()

        mock_store.assert_called_once_with(
            "https://secure.example.com/feed", "user", "token123"
        )

    def test_add_feed_without_credentials_does_not_store(self, qtbot):
        """Omitting auth credentials when adding a feed does not call store_credentials."""
        dialog = self._make_dialog(qtbot)

        mock_feed_dialog = MagicMock()
        mock_feed_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_feed_dialog.url_edit.text.return_value = "https://example.com/feed.atom"
        mock_feed_dialog.name_edit.text.return_value = "Open Feed"
        mock_feed_dialog.auth_user_edit.text.return_value = ""
        mock_feed_dialog.auth_token_edit.text.return_value = ""

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_feed_dialog), \
             patch("src.settings_dialog.store_credentials") as mock_store:
            dialog._add_feed()

        mock_store.assert_not_called()


class TestSettingsDialogEditFeed:
    """Tests for SettingsDialog._edit_feed feed update flow."""

    def _make_dialog(self, qtbot):
        feed = Feed(url="https://example.com/feed.atom", name="Original Feed")
        config = AppConfig(poll_interval_secs=60, feeds=[feed], sound_map={})
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        return dialog, feed

    def test_edit_feed_no_selection_does_nothing(self, qtbot):
        """Calling _edit_feed with no item selected is a no-op."""
        dialog, _ = self._make_dialog(qtbot)
        # Ensure no current item is set
        dialog._feed_list.setCurrentItem(None)

        with patch("src.settings_dialog.FeedEditDialog") as mock_cls:
            dialog._edit_feed()

        mock_cls.assert_not_called()
        assert dialog._feed_list.count() == 1

    def test_edit_feed_accepted_updates_list_item(self, qtbot):
        """Accepting the edit dialog updates the feed's name and URL in the list."""
        dialog, _ = self._make_dialog(qtbot)
        dialog._feed_list.setCurrentRow(0)

        mock_edit_dialog = MagicMock()
        mock_edit_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_edit_dialog.name_edit.text.return_value = "Updated Feed"
        mock_edit_dialog.url_edit.text.return_value = "https://example.com/updated.atom"
        mock_edit_dialog.auth_user_edit.text.return_value = ""
        mock_edit_dialog.auth_token_edit.text.return_value = ""

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_edit_dialog), \
             patch("src.settings_dialog.delete_credentials"):
            dialog._edit_feed()

        item_text = dialog._feed_list.item(0).text()
        assert "Updated Feed" in item_text
        assert "https://example.com/updated.atom" in item_text

    def test_edit_feed_cancelled_keeps_original_text(self, qtbot):
        """Cancelling the edit dialog leaves the list item unchanged."""
        dialog, _ = self._make_dialog(qtbot)
        dialog._feed_list.setCurrentRow(0)

        mock_edit_dialog = MagicMock()
        mock_edit_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_edit_dialog):
            dialog._edit_feed()

        item_text = dialog._feed_list.item(0).text()
        assert "Original Feed" in item_text

    def test_edit_feed_url_change_deletes_old_credentials(self, qtbot):
        """Changing the URL during edit removes credentials for the old URL."""
        dialog, feed = self._make_dialog(qtbot)
        old_url = feed.url
        dialog._feed_list.setCurrentRow(0)

        mock_edit_dialog = MagicMock()
        mock_edit_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_edit_dialog.name_edit.text.return_value = "Moved Feed"
        mock_edit_dialog.url_edit.text.return_value = "https://newhost.example.com/feed"
        mock_edit_dialog.auth_user_edit.text.return_value = ""
        mock_edit_dialog.auth_token_edit.text.return_value = ""

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_edit_dialog), \
             patch("src.settings_dialog.delete_credentials") as mock_delete:
            dialog._edit_feed()

        deleted_urls = {call.args[0] for call in mock_delete.call_args_list}
        assert old_url in deleted_urls

    def test_edit_feed_with_new_credentials_stores_them(self, qtbot):
        """Providing auth credentials when editing a feed calls store_credentials."""
        dialog, _ = self._make_dialog(qtbot)
        dialog._feed_list.setCurrentRow(0)

        mock_edit_dialog = MagicMock()
        mock_edit_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_edit_dialog.name_edit.text.return_value = "Auth Feed"
        mock_edit_dialog.url_edit.text.return_value = "https://example.com/feed.atom"
        mock_edit_dialog.auth_user_edit.text.return_value = "newuser"
        mock_edit_dialog.auth_token_edit.text.return_value = "newtoken"

        with patch("src.settings_dialog.FeedEditDialog", return_value=mock_edit_dialog), \
             patch("src.settings_dialog.store_credentials") as mock_store:
            dialog._edit_feed()

        mock_store.assert_called_once_with(
            "https://example.com/feed.atom", "newuser", "newtoken"
        )
