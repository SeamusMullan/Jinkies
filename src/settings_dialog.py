"""Settings dialog for Jinkies feed monitor.

Provides a UI for configuring poll interval, sound files,
feed management, and notification style.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.credential_store import delete_credentials, get_credentials, store_credentials
from src.url_validation import validate_feed_url

if TYPE_CHECKING:
    from src.models import AppConfig, Feed


class SettingsDialog(QDialog):
    """Dialog for editing application settings.

    Attributes:
        config: The current application config (modified in place on accept).
    """

    def __init__(self, config: AppConfig, parent: QDialog | None = None) -> None:
        """Initialize the settings dialog.

        Args:
            config: The current AppConfig to edit.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Jinkies — Settings")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        """Build the settings dialog UI."""
        layout = QVBoxLayout(self)

        # Poll interval
        poll_group = QGroupBox("Polling")
        poll_layout = QFormLayout()
        self._interval_spinner = QSpinBox()
        self._interval_spinner.setRange(1, 300)
        self._interval_spinner.setSuffix(" seconds")
        poll_layout.addRow("Poll interval:", self._interval_spinner)
        poll_group.setLayout(poll_layout)
        layout.addWidget(poll_group)

        # Sounds
        sound_group = QGroupBox("Sounds")
        sound_layout = QFormLayout()

        self._new_entry_sound = QLineEdit()
        self._new_entry_sound.setReadOnly(True)
        new_entry_browse = QPushButton("Browse...")
        new_entry_browse.clicked.connect(lambda: self._browse_sound("new_entry"))
        new_entry_row = QHBoxLayout()
        new_entry_row.addWidget(self._new_entry_sound)
        new_entry_row.addWidget(new_entry_browse)
        sound_layout.addRow("New entry sound:", new_entry_row)

        self._error_sound = QLineEdit()
        self._error_sound.setReadOnly(True)
        error_browse = QPushButton("Browse...")
        error_browse.clicked.connect(lambda: self._browse_sound("error"))
        error_row = QHBoxLayout()
        error_row.addWidget(self._error_sound)
        error_row.addWidget(error_browse)
        sound_layout.addRow("Error sound:", error_row)

        sound_group.setLayout(sound_layout)
        layout.addWidget(sound_group)

        # Notification style
        notif_group = QGroupBox("Notifications")
        notif_layout = QFormLayout()
        self._notif_style = QComboBox()
        self._notif_style.addItems(["native", "custom"])
        notif_layout.addRow("Style:", self._notif_style)
        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)

        # Feed management
        feed_group = QGroupBox("Feeds")
        feed_layout = QVBoxLayout()

        self._feed_list = QListWidget()
        feed_layout.addWidget(self._feed_list)

        feed_buttons = QHBoxLayout()
        self._add_feed_btn = QPushButton("Add")
        self._add_feed_btn.clicked.connect(self._add_feed)
        feed_buttons.addWidget(self._add_feed_btn)

        self._edit_feed_btn = QPushButton("Edit")
        self._edit_feed_btn.clicked.connect(self._edit_feed)
        feed_buttons.addWidget(self._edit_feed_btn)

        self._remove_feed_btn = QPushButton("Remove")
        self._remove_feed_btn.clicked.connect(self._remove_feed)
        feed_buttons.addWidget(self._remove_feed_btn)

        self._import_feed_btn = QPushButton("Import...")
        self._import_feed_btn.clicked.connect(self._import_feeds)
        feed_buttons.addWidget(self._import_feed_btn)

        feed_layout.addLayout(feed_buttons)
        feed_group.setLayout(feed_layout)
        layout.addWidget(feed_group)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self) -> None:
        """Populate UI fields from the current config."""
        self._interval_spinner.setValue(self.config.poll_interval_secs)
        self._new_entry_sound.setText(self.config.sound_map.get("new_entry", ""))
        self._error_sound.setText(self.config.sound_map.get("error", ""))
        self._notif_style.setCurrentText(self.config.notification_style)

        self._feed_list.clear()
        for feed in self.config.feeds:
            item = QListWidgetItem(f"{feed.name} — {feed.url}")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            self._feed_list.addItem(item)

    def _browse_sound(self, event_type: str) -> None:
        """Open a file dialog to select a WAV sound file.

        Args:
            event_type: The event type key ("new_entry" or "error").
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Sound File", "", "WAV Files (*.wav)"
        )
        if path:
            if event_type == "new_entry":
                self._new_entry_sound.setText(path)
            elif event_type == "error":
                self._error_sound.setText(path)

    def _add_feed(self) -> None:
        """Show a dialog to add a new feed."""
        dialog = FeedEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from src.models import Feed

            url = dialog.url_edit.text()
            username = dialog.auth_user_edit.text() or None
            token = dialog.auth_token_edit.text() or None

            if username and token:
                store_credentials(url, username, token)

            feed = Feed(
                url=url,
                name=dialog.name_edit.text(),
            )
            item = QListWidgetItem(f"{feed.name} — {feed.url}")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            self._feed_list.addItem(item)

    def _edit_feed(self) -> None:
        """Edit the selected feed."""
        current = self._feed_list.currentItem()
        if not current:
            return
        feed = current.data(Qt.ItemDataRole.UserRole)
        old_url = feed.url
        dialog = FeedEditDialog(feed=feed, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            feed.name = dialog.name_edit.text()
            feed.url = dialog.url_edit.text()

            username = dialog.auth_user_edit.text() or None
            token = dialog.auth_token_edit.text() or None

            # If the URL changed, remove credentials for the old URL
            if feed.url != old_url:
                delete_credentials(old_url)

            if username and token:
                store_credentials(feed.url, username, token)
            elif not username and not token:
                # Credentials cleared by user
                delete_credentials(feed.url)

            current.setText(f"{feed.name} — {feed.url}")

    def _remove_feed(self) -> None:
        """Remove the selected feed and its stored credentials."""
        row = self._feed_list.currentRow()
        if row >= 0:
            item = self._feed_list.item(row)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                delete_credentials(feed.url)
            self._feed_list.takeItem(row)

    def _import_feeds(self) -> None:
        """Import feeds from an OPML or Atom/XML file with preview."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Feeds",
            "",
            "Feed Files (*.opml *.xml *.atom *.rss);;OPML Files (*.opml);;All Files (*)",
        )
        if not path:
            return

        from src.feed_import import import_local_feed, import_opml

        try:
            if path.lower().endswith(".opml"):
                feeds = import_opml(path)
            else:
                feeds = import_local_feed(path)
        except ValueError:
            return

        if not feeds:
            return

        existing_urls = set()
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                existing_urls.add(feed.url)

        preview = ImportPreviewDialog(feeds, existing_urls, parent=self)
        if preview.exec() != QDialog.DialogCode.Accepted:
            return

        for feed in preview.get_feeds():
            item = QListWidgetItem(f"{feed.name} — {feed.url}")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            self._feed_list.addItem(item)

    def _save_and_accept(self) -> None:
        """Save settings to config and close."""
        self.config.poll_interval_secs = self._interval_spinner.value()
        self.config.sound_map["new_entry"] = self._new_entry_sound.text()
        self.config.sound_map["error"] = self._error_sound.text()
        self.config.notification_style = self._notif_style.currentText()

        self.config.feeds = []
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                self.config.feeds.append(feed)

        self.accept()

    def get_config(self) -> AppConfig:
        """Return the modified config.

        Returns:
            The AppConfig with user's changes applied.
        """
        return self.config


class ImportPreviewDialog(QDialog):
    """Preview and edit imported feeds before adding them.

    Shows an editable table of feeds parsed from an OPML or Atom file,
    allowing the user to modify names/URLs and select which to import.

    Attributes:
        feeds: The list of Feed objects after user edits.
    """

    def __init__(
        self,
        feeds: list[Feed],
        existing_urls: set[str] | None = None,
        parent: QDialog | None = None,
    ) -> None:
        """Initialize the import preview dialog.

        Args:
            feeds: Parsed feeds to preview.
            existing_urls: URLs already in the config (shown as duplicates).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Import Preview — Edit Feeds")
        self.setMinimumSize(650, 400)
        self._existing_urls = existing_urls or set()
        self._source_feeds = feeds
        self.feeds: list[Feed] = []
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self) -> None:
        """Build the preview dialog UI."""
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Review and edit the imported feeds below. "
            "Uncheck any you don't want to import."
        ))

        # Auth section — applied to all imported feeds
        auth_group = QGroupBox("Authentication (applied to all imported feeds)")
        auth_layout = QFormLayout()
        self._auth_user = QLineEdit()
        self._auth_user.setPlaceholderText("Leave blank for no auth")
        auth_layout.addRow("Username:", self._auth_user)
        self._auth_token = QLineEdit()
        self._auth_token.setPlaceholderText("API token or password")
        self._auth_token.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addRow("Token:", self._auth_token)
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)

        # Select all/none controls
        select_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_row.addWidget(select_all_btn)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        select_row.addWidget(select_none_btn)
        select_row.addStretch()
        layout.addLayout(select_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Import", "Name", "URL"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive,
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.setColumnWidth(1, 180)
        layout.addWidget(self._table)

        self._dup_label = QLabel("")
        layout.addWidget(self._dup_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_import)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_table(self) -> None:
        """Fill the table with parsed feed data."""
        self._table.setRowCount(len(self._source_feeds))
        dup_count = 0

        for row, feed in enumerate(self._source_feeds):
            # Checkbox column
            checkbox = QCheckBox()
            is_dup = feed.url in self._existing_urls
            checkbox.setChecked(not is_dup)
            if is_dup:
                dup_count += 1
            self._table.setCellWidget(row, 0, checkbox)

            # Editable name
            name_item = QTableWidgetItem(feed.name)
            self._table.setItem(row, 1, name_item)

            # Editable URL
            url_item = QTableWidgetItem(feed.url)
            self._table.setItem(row, 2, url_item)

        if dup_count:
            self._dup_label.setText(
                f"{dup_count} feed(s) already exist and are unchecked."
            )

    def _set_all_checked(self, checked: bool) -> None:
        """Set all feed checkboxes to the given state.

        Args:
            checked: Whether to check or uncheck all.
        """
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.setChecked(checked)

    def _accept_import(self) -> None:
        """Collect checked feeds with user edits and auth, then accept."""
        auth_user = self._auth_user.text().strip() or None
        auth_token = self._auth_token.text().strip() or None

        self.feeds = []
        for row in range(self._table.rowCount()):
            checkbox = self._table.cellWidget(row, 0)
            if not checkbox or not checkbox.isChecked():
                continue

            name = self._table.item(row, 1).text().strip()
            url = self._table.item(row, 2).text().strip()
            if not url or validate_feed_url(url) is not None:
                continue

            if auth_user and auth_token:
                store_credentials(url, auth_user, auth_token)

            from src.models import Feed as FeedModel

            self.feeds.append(FeedModel(
                url=url,
                name=name or url,
            ))
        self.accept()

    def get_feeds(self) -> list[Feed]:
        """Return the user-approved list of feeds.

        Returns:
            List of Feed objects the user chose to import.
        """
        return self.feeds


class FeedEditDialog(QDialog):
    """Dialog for adding or editing a single feed.

    Attributes:
        name_edit: Text input for the feed name.
        url_edit: Text input for the feed URL.
        auth_user_edit: Text input for auth username.
        auth_token_edit: Text input for auth token/password.
    """

    def __init__(
        self,
        feed: Feed | None = None,
        parent: QDialog | None = None,
    ) -> None:
        """Initialize the feed edit dialog.

        Args:
            feed: Existing feed to edit, or None for a new feed.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Feed" if feed else "Add Feed")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.auth_user_edit = QLineEdit()
        self.auth_user_edit.setPlaceholderText("Optional")
        self.auth_token_edit = QLineEdit()
        self.auth_token_edit.setPlaceholderText("Optional")
        self.auth_token_edit.setEchoMode(QLineEdit.EchoMode.Password)

        if feed:
            self.name_edit.setText(feed.name)
            self.url_edit.setText(feed.url)
            creds = get_credentials(feed.url)
            if creds:
                self.auth_user_edit.setText(creds[0])
                self.auth_token_edit.setText(creds[1])

        layout.addRow("Name:", self.name_edit)
        layout.addRow("URL:", self.url_edit)
        layout.addRow("Auth User:", self.auth_user_edit)
        layout.addRow("Auth Token:", self.auth_token_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        """Validate the feed URL before accepting the dialog."""
        url = self.url_edit.text().strip()
        error = validate_feed_url(url)
        if error:
            QMessageBox.warning(self, "Invalid Feed URL", error)
            return
        self.accept()
