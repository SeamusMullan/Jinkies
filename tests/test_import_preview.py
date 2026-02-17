"""Tests for ImportPreviewDialog."""

from __future__ import annotations

from src.models import Feed
from src.settings_dialog import ImportPreviewDialog


class TestImportPreviewDialog:
    def test_shows_all_feeds(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)
        assert dialog._table.rowCount() == 2

    def test_duplicates_unchecked(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        existing = {"https://a.com/feed"}
        dialog = ImportPreviewDialog(feeds, existing)
        qtbot.addWidget(dialog)

        # Row 0 (duplicate) should be unchecked
        cb0 = dialog._table.cellWidget(0, 0)
        assert not cb0.isChecked()
        # Row 1 (new) should be checked
        cb1 = dialog._table.cellWidget(1, 0)
        assert cb1.isChecked()

    def test_accept_collects_checked_feeds(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/feed", name="Feed B"),
        ]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)

        # Uncheck the first feed
        dialog._table.cellWidget(0, 0).setChecked(False)
        dialog._accept_import()

        result = dialog.get_feeds()
        assert len(result) == 1
        assert result[0].url == "https://b.com/feed"

    def test_edited_values_are_used(self, qtbot):
        feeds = [Feed(url="https://old.com/feed", name="Old Name")]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)

        # Edit the name and URL in the table
        dialog._table.item(0, 1).setText("New Name")
        dialog._table.item(0, 2).setText("https://new.com:8080/feed")
        dialog._accept_import()

        result = dialog.get_feeds()
        assert len(result) == 1
        assert result[0].name == "New Name"
        assert result[0].url == "https://new.com:8080/feed"

    def test_empty_url_skipped(self, qtbot):
        feeds = [Feed(url="https://a.com/feed", name="Feed A")]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)

        dialog._table.item(0, 2).setText("")
        dialog._accept_import()

        assert dialog.get_feeds() == []

    def test_dup_label_shown(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="A"),
            Feed(url="https://b.com/feed", name="B"),
        ]
        existing = {"https://a.com/feed", "https://b.com/feed"}
        dialog = ImportPreviewDialog(feeds, existing)
        qtbot.addWidget(dialog)
        assert "2 feed(s) already exist" in dialog._dup_label.text()

    def test_no_dup_label_when_none(self, qtbot):
        feeds = [Feed(url="https://a.com/feed", name="A")]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)
        assert dialog._dup_label.text() == ""

    def test_auth_applied_to_all_feeds(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="A"),
            Feed(url="https://b.com/feed", name="B"),
        ]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)

        dialog._auth_user.setText("admin")
        dialog._auth_token.setText("secret123")
        dialog._accept_import()

        result = dialog.get_feeds()
        assert len(result) == 2
        for f in result:
            assert f.auth_user == "admin"
            assert f.auth_token == "secret123"

    def test_no_auth_when_fields_empty(self, qtbot):
        feeds = [Feed(url="https://a.com/feed", name="A")]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)
        dialog._accept_import()

        result = dialog.get_feeds()
        assert result[0].auth_user is None
        assert result[0].auth_token is None

    def test_select_all(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="A"),
            Feed(url="https://b.com/feed", name="B"),
        ]
        existing = {"https://a.com/feed", "https://b.com/feed"}
        dialog = ImportPreviewDialog(feeds, existing)
        qtbot.addWidget(dialog)

        # Both should start unchecked (duplicates)
        assert not dialog._table.cellWidget(0, 0).isChecked()
        assert not dialog._table.cellWidget(1, 0).isChecked()

        dialog._set_all_checked(True)
        assert dialog._table.cellWidget(0, 0).isChecked()
        assert dialog._table.cellWidget(1, 0).isChecked()

    def test_select_none(self, qtbot):
        feeds = [
            Feed(url="https://a.com/feed", name="A"),
            Feed(url="https://b.com/feed", name="B"),
        ]
        dialog = ImportPreviewDialog(feeds)
        qtbot.addWidget(dialog)

        dialog._set_all_checked(False)
        dialog._accept_import()
        assert dialog.get_feeds() == []
