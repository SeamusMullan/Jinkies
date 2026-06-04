"""Settings dialog for Jinkies feed monitor.

Provides a UI for configuring poll interval, sound files,
feed management, and notification style.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.credential_store import delete_credentials, get_credentials, store_credentials
from src.feed_discover import discover_feeds
from src.feed_import import import_local_feed, import_opml
from src.models import Feed, Rule
from src.notify_sinks import PROVIDER_PRESETS, SinkConfig, build_sink
from src.sink_secret_store import store_sink_secret
from src.theme import resolve_theme
from src.url_validation import check_feed_connectivity, validate_feed_url

if TYPE_CHECKING:
    from src.audio import AudioPlayer
    from src.models import AppConfig, FeedEntry


class SettingsDialog(QDialog):
    """Dialog for editing application settings.

    Attributes:
        config: The current application config (modified in place on accept).
    """

    def __init__(
        self,
        config: AppConfig,
        parent: QDialog | None = None,
        audio: AudioPlayer | None = None,
        sample_entries: list[FeedEntry] | None = None,
    ) -> None:
        """Initialize the settings dialog.

        Args:
            config: The current AppConfig to edit.
            parent: Optional parent widget.
            audio: Optional audio player, used for sound-preview buttons.
            sample_entries: Current dashboard entries, used for rule dry-run.
        """
        super().__init__(parent)
        self.config = config
        self._audio = audio
        self._sample_entries = sample_entries or []
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

        # Entry table display
        display_group = QGroupBox("Display")
        display_layout = QFormLayout()
        self._page_size_spinner = QSpinBox()
        self._page_size_spinner.setRange(1, 10_000)
        self._page_size_spinner.setSuffix(" entries")
        display_layout.addRow("Page size:", self._page_size_spinner)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["aero", "dark", "light", "system"])
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        display_layout.addRow("Theme:", self._theme_combo)

        self._show_tray_badge_check = QCheckBox("Show unread badge on tray icon")
        display_layout.addRow("", self._show_tray_badge_check)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Sounds
        sound_group = QGroupBox("Sounds")
        sound_layout = QFormLayout()

        self._new_entry_sound = QLineEdit()
        self._new_entry_sound.setReadOnly(True)
        new_entry_browse = QPushButton("Browse...")
        new_entry_browse.clicked.connect(lambda: self._browse_sound("new_entry"))
        new_entry_preview = QPushButton("Preview")
        new_entry_preview.clicked.connect(
            lambda: self._preview_sound(self._new_entry_sound)
        )
        new_entry_row = QHBoxLayout()
        new_entry_row.addWidget(self._new_entry_sound)
        new_entry_row.addWidget(new_entry_browse)
        new_entry_row.addWidget(new_entry_preview)
        sound_layout.addRow("New entry sound:", new_entry_row)

        self._error_sound = QLineEdit()
        self._error_sound.setReadOnly(True)
        error_browse = QPushButton("Browse...")
        error_browse.clicked.connect(lambda: self._browse_sound("error"))
        error_preview = QPushButton("Preview")
        error_preview.clicked.connect(lambda: self._preview_sound(self._error_sound))
        error_row = QHBoxLayout()
        error_row.addWidget(self._error_sound)
        error_row.addWidget(error_browse)
        error_row.addWidget(error_preview)
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
        self._feed_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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

        # Rules
        rules_group = QGroupBox("Rules")
        rules_layout = QVBoxLayout()

        self._rules_table = QTableWidget(0, 6)
        self._rules_table.setHorizontalHeaderLabels(
            ["Name", "Feed", "Keyword", "Status", "Sound", "Notif/Color"]
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive,
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive,
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive,
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch,
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._rules_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._rules_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._rules_table.setMinimumHeight(120)
        rules_layout.addWidget(self._rules_table)

        rules_buttons = QHBoxLayout()
        self._add_rule_btn = QPushButton("Add")
        self._add_rule_btn.clicked.connect(self._add_rule)
        rules_buttons.addWidget(self._add_rule_btn)

        self._edit_rule_btn = QPushButton("Edit")
        self._edit_rule_btn.clicked.connect(self._edit_rule)
        rules_buttons.addWidget(self._edit_rule_btn)

        self._remove_rule_btn = QPushButton("Remove")
        self._remove_rule_btn.clicked.connect(self._remove_rule)
        rules_buttons.addWidget(self._remove_rule_btn)

        rules_layout.addLayout(rules_buttons)
        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)

        # Sinks (webhook / script notification destinations)
        sinks_group = QGroupBox("Sinks (Discord / Slack / ntfy / webhook / script)")
        sinks_layout = QVBoxLayout()

        self._sinks_table = QTableWidget(0, 4)
        self._sinks_table.setHorizontalHeaderLabels(
            ["Name", "Provider", "Target", "Enabled"]
        )
        self._sinks_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self._sinks_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._sinks_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._sinks_table.setMinimumHeight(100)
        sinks_layout.addWidget(self._sinks_table)

        sinks_buttons = QHBoxLayout()
        add_sink_btn = QPushButton("Add")
        add_sink_btn.clicked.connect(self._add_sink)
        sinks_buttons.addWidget(add_sink_btn)
        edit_sink_btn = QPushButton("Edit")
        edit_sink_btn.clicked.connect(self._edit_sink)
        sinks_buttons.addWidget(edit_sink_btn)
        remove_sink_btn = QPushButton("Remove")
        remove_sink_btn.clicked.connect(self._remove_sink)
        sinks_buttons.addWidget(remove_sink_btn)
        test_sink_btn = QPushButton("Send Test")
        test_sink_btn.clicked.connect(self._test_sink)
        sinks_buttons.addWidget(test_sink_btn)

        sinks_layout.addLayout(sinks_buttons)
        sinks_group.setLayout(sinks_layout)
        layout.addWidget(sinks_group)

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
        self._page_size_spinner.setValue(self.config.page_size)
        self._new_entry_sound.setText(self.config.sound_map.get("new_entry", ""))
        self._error_sound.setText(self.config.sound_map.get("error", ""))
        self._notif_style.setCurrentText(self.config.notification_style)
        self._theme_combo.setCurrentText(self.config.theme)
        self._show_tray_badge_check.setChecked(self.config.show_tray_badge)

        self._feed_list.clear()
        for feed in self.config.feeds:
            item = QListWidgetItem(f"{feed.name} — {feed.url}")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            self._feed_list.addItem(item)

        self._rules_table.setRowCount(0)
        for rule in self.config.rules:
            self._append_rule_row(rule)

        self._sinks_table.setRowCount(0)
        for sink in self.config.sinks:
            self._append_sink_row(sink)

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

    def _existing_groups(self) -> list[str]:
        """Return a sorted, deduplicated list of group names from the feed list."""
        groups: list[str] = []
        seen: set[str] = set()
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                g = getattr(feed, "group", None)
                if g and g not in seen:
                    groups.append(g)
                    seen.add(g)
        return sorted(groups)

    def _add_feed(self) -> None:
        """Show a dialog to add a new feed."""
        dialog = FeedEditDialog(existing_groups=self._existing_groups(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.url_edit.text()
            username = dialog.auth_user_edit.text() or None
            token = dialog.auth_token_edit.text() or None

            if username and token:
                store_credentials(url, username, token)

            raw_interval = dialog.poll_interval_spin.value()
            feed = Feed(
                url=url,
                name=dialog.name_edit.text(),
                poll_interval_secs=raw_interval if raw_interval > 0 else None,
                group=dialog.group_combo.currentText().strip() or None,
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
        dialog = FeedEditDialog(
            feed=feed,
            existing_groups=self._existing_groups(),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            feed.name = dialog.name_edit.text()
            feed.url = dialog.url_edit.text()
            raw_interval = dialog.poll_interval_spin.value()
            feed.poll_interval_secs = raw_interval if raw_interval > 0 else None
            feed.group = dialog.group_combo.currentText().strip() or None

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
        """Remove the selected feed(s) and their stored credentials."""
        selected_items = self._feed_list.selectedItems()
        if not selected_items:
            return

        # Sort by row so the confirmation list and removal order are predictable
        items_with_rows = sorted(
            [(self._feed_list.row(item), item) for item in selected_items]
        )
        rows = [row for row, _ in items_with_rows]
        feeds = [item.data(Qt.ItemDataRole.UserRole) for _, item in items_with_rows]

        if len(rows) == 1:
            title = "Remove Feed"
            msg = f"Remove feed \"{feeds[0].name}\"?"
        else:
            names = "\n".join(f"  \u2022 {f.name}" for f in feeds)
            title = "Remove Feeds"
            msg = f"Remove {len(rows)} feeds?\n\n{names}"

        reply = QMessageBox.question(
            self,
            title,
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for feed in feeds:
            delete_credentials(feed.url)
        for row in sorted(rows, reverse=True):
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

        try:
            if path.lower().endswith(".opml"):
                feeds = import_opml(path)
            else:
                feeds = import_local_feed(path)
        except ValueError as e:
            QMessageBox.warning(self, "Import Error", str(e))
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

    def _append_rule_row(self, rule: Rule) -> None:
        """Append *rule* as a new row in the rules table.

        Args:
            rule: The Rule to display.
        """
        row = self._rules_table.rowCount()
        self._rules_table.insertRow(row)

        name_item = QTableWidgetItem(rule.name if rule.enabled else f"[off] {rule.name}")
        name_item.setData(Qt.ItemDataRole.UserRole, rule)
        self._rules_table.setItem(row, 0, name_item)

        feed_text = rule.feed_url or "(all feeds)"
        # Shorten long URLs for display
        if rule.feed_url and len(rule.feed_url) > 30:
            feed_text = "…" + rule.feed_url[-28:]
        self._rules_table.setItem(row, 1, QTableWidgetItem(feed_text))
        self._rules_table.setItem(row, 2, QTableWidgetItem(rule.keyword or ""))
        self._rules_table.setItem(row, 3, QTableWidgetItem(rule.status or "any"))

        sound_text = rule.sound_file or ""
        if sound_text and len(sound_text) > 20:
            sound_text = "…" + sound_text[-18:]
        self._rules_table.setItem(row, 4, QTableWidgetItem(sound_text))

        actions: list[str] = []
        if rule.notification:
            actions.append("notif")
        if rule.highlight_color:
            actions.append(rule.highlight_color)
        self._rules_table.setItem(row, 5, QTableWidgetItem(", ".join(actions)))

    def _get_feed_urls(self) -> list[str]:
        """Return feed URLs currently listed in the feeds list widget.

        Returns:
            List of feed URL strings.
        """
        urls: list[str] = []
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                urls.append(feed.url)
        return urls

    def _add_rule(self) -> None:
        """Open the rule editor to create a new rule."""
        dialog = RuleEditDialog(
            feed_urls=self._get_feed_urls(),
            sink_names=self._sink_names(),
            sample_entries=self._sample_entries,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule = dialog.get_rule()
            self._append_rule_row(rule)

    def _edit_rule(self) -> None:
        """Open the rule editor for the currently selected rule row."""
        row = self._rules_table.currentRow()
        if row < 0:
            return
        item = self._rules_table.item(row, 0)
        if not item:
            return
        rule = item.data(Qt.ItemDataRole.UserRole)
        dialog = RuleEditDialog(
            rule=rule,
            feed_urls=self._get_feed_urls(),
            sink_names=self._sink_names(),
            sample_entries=self._sample_entries,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_rule()
            self._rules_table.removeRow(row)
            self._rules_table.insertRow(row)
            name_item = QTableWidgetItem(
                updated.name if updated.enabled else f"[off] {updated.name}"
            )
            name_item.setData(Qt.ItemDataRole.UserRole, updated)
            self._rules_table.setItem(row, 0, name_item)
            feed_text = updated.feed_url or "(all feeds)"
            if updated.feed_url and len(updated.feed_url) > 30:
                feed_text = "…" + updated.feed_url[-28:]
            self._rules_table.setItem(row, 1, QTableWidgetItem(feed_text))
            self._rules_table.setItem(row, 2, QTableWidgetItem(updated.keyword or ""))
            self._rules_table.setItem(row, 3, QTableWidgetItem(updated.status or "any"))
            sound_text = updated.sound_file or ""
            if sound_text and len(sound_text) > 20:
                sound_text = "…" + sound_text[-18:]
            self._rules_table.setItem(row, 4, QTableWidgetItem(sound_text))
            actions: list[str] = []
            if updated.notification:
                actions.append("notif")
            if updated.highlight_color:
                actions.append(updated.highlight_color)
            self._rules_table.setItem(row, 5, QTableWidgetItem(", ".join(actions)))
            self._rules_table.setCurrentCell(row, 0)

    def _remove_rule(self) -> None:
        """Remove the currently selected rule row."""
        row = self._rules_table.currentRow()
        if row >= 0:
            self._rules_table.removeRow(row)

    def _preview_sound(self, line_edit: QLineEdit) -> None:
        """Play the sound file named in *line_edit* for previewing.

        Args:
            line_edit: The widget holding the WAV file path.
        """
        path = line_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Preview", "No sound file selected.")
            return
        if self._audio is None:
            QMessageBox.information(
                self, "Preview", "Audio is unavailable in this context."
            )
            return
        self._audio.play("new_entry", sound_file=path)

    # --- Sink management ---

    def _sink_names(self) -> list[str]:
        """Return the names of sinks currently in the sinks table."""
        names: list[str] = []
        for row in range(self._sinks_table.rowCount()):
            item = self._sinks_table.item(row, 0)
            if item:
                cfg = item.data(Qt.ItemDataRole.UserRole)
                if cfg:
                    names.append(cfg.name)
        return names

    def _append_sink_row(self, cfg: SinkConfig) -> None:
        """Append *cfg* as a new row in the sinks table."""
        row = self._sinks_table.rowCount()
        self._sinks_table.insertRow(row)
        name_item = QTableWidgetItem(cfg.name)
        name_item.setData(Qt.ItemDataRole.UserRole, cfg)
        self._sinks_table.setItem(row, 0, name_item)
        preset = PROVIDER_PRESETS.get(cfg.provider)
        self._sinks_table.setItem(
            row, 1, QTableWidgetItem(preset.name if preset else cfg.provider)
        )
        target = cfg.script if cfg.transport == "script" else cfg.url
        if len(target) > 40:
            target = "…" + target[-38:]
        self._sinks_table.setItem(row, 2, QTableWidgetItem(target))
        self._sinks_table.setItem(
            row, 3, QTableWidgetItem("yes" if cfg.enabled else "no")
        )

    def _refresh_sink_row(self, row: int, cfg: SinkConfig) -> None:
        """Rewrite an existing sinks-table row with *cfg*."""
        self._sinks_table.removeRow(row)
        self._sinks_table.insertRow(row)
        name_item = QTableWidgetItem(cfg.name)
        name_item.setData(Qt.ItemDataRole.UserRole, cfg)
        self._sinks_table.setItem(row, 0, name_item)
        preset = PROVIDER_PRESETS.get(cfg.provider)
        self._sinks_table.setItem(
            row, 1, QTableWidgetItem(preset.name if preset else cfg.provider)
        )
        target = cfg.script if cfg.transport == "script" else cfg.url
        if len(target) > 40:
            target = "…" + target[-38:]
        self._sinks_table.setItem(row, 2, QTableWidgetItem(target))
        self._sinks_table.setItem(
            row, 3, QTableWidgetItem("yes" if cfg.enabled else "no")
        )
        self._sinks_table.setCurrentCell(row, 0)

    def _add_sink(self) -> None:
        """Open the sink editor to create a new sink."""
        dialog = SinkEditDialog(existing_names=self._sink_names(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._append_sink_row(dialog.get_sink())

    def _edit_sink(self) -> None:
        """Open the sink editor for the selected sink row."""
        row = self._sinks_table.currentRow()
        if row < 0:
            return
        item = self._sinks_table.item(row, 0)
        if not item:
            return
        cfg = item.data(Qt.ItemDataRole.UserRole)
        names = [n for n in self._sink_names() if n != cfg.name]
        dialog = SinkEditDialog(sink=cfg, existing_names=names, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_sink_row(row, dialog.get_sink())

    def _remove_sink(self) -> None:
        """Remove the selected sink row."""
        row = self._sinks_table.currentRow()
        if row >= 0:
            self._sinks_table.removeRow(row)

    def _test_sink(self) -> None:
        """Send a sample payload through the selected sink and show the result."""
        row = self._sinks_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Send Test", "Select a sink first.")
            return
        item = self._sinks_table.item(row, 0)
        cfg = item.data(Qt.ItemDataRole.UserRole)
        result = build_sink(cfg).test()
        if result.ok:
            code = f" (HTTP {result.status_code})" if result.status_code else ""
            QMessageBox.information(self, "Send Test", f"Sink '{cfg.name}' OK{code}.")
        else:
            QMessageBox.warning(
                self, "Send Test", f"Sink '{cfg.name}' failed: {result.error}"
            )

    def _on_theme_changed(self, name: str) -> None:
        """Apply theme immediately for live preview."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(resolve_theme(name))

    def _save_and_accept(self) -> None:
        """Save settings to config and close."""
        self.config.poll_interval_secs = self._interval_spinner.value()
        self.config.page_size = self._page_size_spinner.value()
        self.config.sound_map["new_entry"] = self._new_entry_sound.text()
        self.config.sound_map["error"] = self._error_sound.text()
        self.config.notification_style = self._notif_style.currentText()
        self.config.theme = self._theme_combo.currentText()
        self.config.show_tray_badge = self._show_tray_badge_check.isChecked()

        self.config.feeds = []
        for i in range(self._feed_list.count()):
            item = self._feed_list.item(i)
            if item:
                feed = item.data(Qt.ItemDataRole.UserRole)
                self.config.feeds.append(feed)

        self.config.rules = []
        for row in range(self._rules_table.rowCount()):
            item = self._rules_table.item(row, 0)
            if item:
                rule = item.data(Qt.ItemDataRole.UserRole)
                self.config.rules.append(rule)

        self.config.sinks = []
        for row in range(self._sinks_table.rowCount()):
            item = self._sinks_table.item(row, 0)
            if item:
                cfg = item.data(Qt.ItemDataRole.UserRole)
                self.config.sinks.append(cfg)

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
                auth_user=auth_user,
                auth_token=auth_token,
            ))
        self.accept()

    def get_feeds(self) -> list[Feed]:
        """Return the user-approved list of feeds.

        Returns:
            List of Feed objects the user chose to import.
        """
        return self.feeds


class _DiscoverWorker(QThread):
    """Background thread that runs feed discovery without blocking the UI.

    Signals:
        results_ready: Emitted with the list of discovered feed dicts when done.
    """

    results_ready: Signal = Signal(list)

    def __init__(self, url: str, parent: QThread | None = None) -> None:
        """Initialise with the URL to probe.

        Args:
            url: Website URL to discover feeds from.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        """Fetch and parse *url*, then emit results_ready."""
        results = discover_feeds(self._url)
        self.results_ready.emit(results)


class _DiscoverResultDialog(QDialog):
    """Show a list of discovered feeds and let the user pick one.

    Attributes:
        selected_url: The URL the user chose, or empty string if cancelled.
        selected_title: The title of the chosen feed, or empty string.
    """

    def __init__(
        self,
        feeds: list[dict[str, str]],
        parent: QDialog | None = None,
    ) -> None:
        """Initialise with the discovered feed list.

        Args:
            feeds: List of dicts with keys ``url``, ``title``, ``type``.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Discovered Feeds")
        self.setMinimumWidth(480)
        self.selected_url = ""
        self.selected_title = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a feed to add:"))

        self._list = QListWidget()
        for feed in feeds:
            label = feed["title"] or feed["url"]
            item = QListWidgetItem(f"{label}  [{feed['type'].upper()}]")
            item.setData(Qt.ItemDataRole.UserRole, feed)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(self._accept_selection)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_selection(self) -> None:
        """Store the selected feed's URL and title then accept."""
        item = self._list.currentItem()
        if not item:
            return
        feed = item.data(Qt.ItemDataRole.UserRole)
        self.selected_url = feed["url"]
        self.selected_title = feed["title"]
        self.accept()


class FeedEditDialog(QDialog):
    """Dialog for adding or editing a single feed.

    Attributes:
        name_edit: Text input for the feed name.
        url_edit: Text input for the feed URL.
        auth_user_edit: Text input for auth username.
        auth_token_edit: Text input for auth token/password.
        group_combo: Editable combo box for the feed group name.
    """

    def __init__(
        self,
        feed: Feed | None = None,
        existing_groups: list[str] | None = None,
        parent: QDialog | None = None,
    ) -> None:
        """Initialize the feed edit dialog.

        Args:
            feed: Existing feed to edit, or None for a new feed.
            existing_groups: List of group names already in use, for the combo
                box suggestions.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Feed" if feed else "Add Feed")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.addItem("")  # blank = no group
        for g in (existing_groups or []):
            if g:
                self.group_combo.addItem(g)
        self.url_edit = QLineEdit()
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(0, 86400)
        self.poll_interval_spin.setSuffix(" sec")
        self.poll_interval_spin.setSpecialValueText("Use global")
        self.auth_user_edit = QLineEdit()
        self.auth_user_edit.setPlaceholderText("Optional")
        self.auth_token_edit = QLineEdit()
        self.auth_token_edit.setPlaceholderText("Optional")
        self.auth_token_edit.setEchoMode(QLineEdit.EchoMode.Password)

        if feed:
            self.name_edit.setText(feed.name)
            self.url_edit.setText(feed.url)
            self.poll_interval_spin.setValue(feed.poll_interval_secs or 0)
            self.group_combo.setCurrentText(feed.group or "")
            creds = get_credentials(feed.url)
            if creds:
                self.auth_user_edit.setText(creds[0])
                self.auth_token_edit.setText(creds[1])

        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit)
        self._discover_btn = QPushButton("Discover…")
        self._discover_btn.setToolTip(
            "Auto-detect feeds from a website URL"
        )
        self._discover_btn.clicked.connect(self._discover_feeds)
        url_row.addWidget(self._discover_btn)

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Group:", self.group_combo)
        layout.addRow("Poll interval:", self.poll_interval_spin)
        layout.addRow("URL:", url_row)
        layout.addRow("Auth User:", self.auth_user_edit)
        layout.addRow("Auth Token:", self.auth_token_edit)

        check_btn = QPushButton("Check connectivity…")
        check_btn.clicked.connect(self._check_connectivity)
        layout.addRow("", check_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _discover_feeds(self) -> None:
        """Run feed discovery on the entered URL in a background thread.

        Populates ``url_edit`` (and optionally ``name_edit``) when the user
        selects a result, or shows an information dialog if nothing is found.
        """
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "Discover Feeds", "Enter a URL first.")
            return

        self._discover_btn.setEnabled(False)
        self._discover_btn.setText("Discovering…")

        self._worker = _DiscoverWorker(url, parent=self)
        self._worker.results_ready.connect(self._on_discover_results)
        self._worker.finished.connect(
            lambda: (
                self._discover_btn.setEnabled(True),
                self._discover_btn.setText("Discover…"),
            )
        )
        self._worker.start()

    def _on_discover_results(self, feeds: list[dict[str, str]]) -> None:
        """Handle results emitted by :class:`_DiscoverWorker`.

        Args:
            feeds: Discovered feed dicts, may be empty.
        """
        if not feeds:
            QMessageBox.information(
                self,
                "Discover Feeds",
                "No feeds found at that URL.",
            )
            return

        dialog = _DiscoverResultDialog(feeds, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.url_edit.setText(dialog.selected_url)
            if dialog.selected_title and not self.name_edit.text().strip():
                self.name_edit.setText(dialog.selected_title)

    def _check_connectivity(self) -> None:
        """Perform an optional HEAD-request connectivity check on the entered URL.

        Shows an information or warning dialog with the result.
        """
        url = self.url_edit.text().strip()
        error = validate_feed_url(url)
        if error:
            QMessageBox.warning(self, "Invalid Feed URL", error)
            return
        error = check_feed_connectivity(url)
        if error:
            QMessageBox.warning(self, "Connectivity Check Failed", error)
        else:
            QMessageBox.information(
                self, "Connectivity Check", "Successfully reached the feed URL."
            )

    def _validate_and_accept(self) -> None:
        """Validate the feed name and URL before accepting the dialog.

        Shows a warning and keeps the dialog open if the name is blank or
        the URL is empty / uses a disallowed scheme.
        """
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Invalid Feed Name", "Feed name must not be empty.")
            return
        url = self.url_edit.text().strip()
        error = validate_feed_url(url)
        if error:
            QMessageBox.warning(self, "Invalid Feed URL", error)
            return
        self.accept()


class RuleEditDialog(QDialog):
    """Dialog for creating or editing a single alert rule.

    Attributes:
        _rule: The Rule being edited (or ``None`` for a new rule).
        _feed_urls: Feed URLs to populate the feed dropdown.
    """

    def __init__(
        self,
        rule: Rule | None = None,
        feed_urls: list[str] | None = None,
        parent: QDialog | None = None,
        sink_names: list[str] | None = None,
        sample_entries: list[FeedEntry] | None = None,
    ) -> None:
        """Initialise the rule editor.

        Args:
            rule: Existing Rule to edit, or ``None`` to create a new one.
            feed_urls: Feed URLs for the feed condition dropdown.
            parent: Optional parent widget.
            sink_names: Names of configured sinks the rule may target.
            sample_entries: Current dashboard entries for dry-run preview.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Rule" if rule else "Add Rule")
        self.setMinimumWidth(480)
        self._rule = rule
        self._feed_urls = feed_urls or []
        self._sink_names = sink_names or []
        self._sample_entries = sample_entries or []
        self._highlight_color: str | None = rule.highlight_color if rule else None
        self._setup_ui()
        if rule:
            self._load_rule(rule)

    def _setup_ui(self) -> None:
        """Build the rule editor UI."""
        layout = QFormLayout(self)

        # Name + enabled
        name_row = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Rule name")
        name_row.addWidget(self._name_edit)
        self._enabled_check = QCheckBox("Enabled")
        self._enabled_check.setChecked(True)
        name_row.addWidget(self._enabled_check)
        layout.addRow("Name:", name_row)

        # --- Conditions ---
        layout.addRow(QLabel("<b>Conditions</b> (all must match; leave blank to skip)"))

        self._feed_combo = QComboBox()
        self._feed_combo.addItem("All feeds", None)
        for url in self._feed_urls:
            self._feed_combo.addItem(url, url)
        layout.addRow("Feed:", self._feed_combo)

        self._keyword_edit = QLineEdit()
        self._keyword_edit.setPlaceholderText("Substring in title (case-insensitive)")
        layout.addRow("Keyword:", self._keyword_edit)

        self._status_combo = QComboBox()
        self._status_combo.addItems(["Any", "stable", "back to normal", "broken", "failed", "unstable", "aborted"])
        layout.addRow("Jenkins status:", self._status_combo)

        # --- Actions ---
        layout.addRow(QLabel("<b>Actions</b>"))

        sound_row = QHBoxLayout()
        self._sound_edit = QLineEdit()
        self._sound_edit.setReadOnly(True)
        self._sound_edit.setPlaceholderText("No extra sound")
        sound_row.addWidget(self._sound_edit)
        sound_browse = QPushButton("Browse…")
        sound_browse.clicked.connect(self._browse_sound)
        sound_row.addWidget(sound_browse)
        sound_clear = QPushButton("Clear")
        sound_clear.clicked.connect(lambda: self._sound_edit.clear())
        sound_row.addWidget(sound_clear)
        layout.addRow("Sound file:", sound_row)

        self._notification_check = QCheckBox("Send desktop notification")
        layout.addRow("Notification:", self._notification_check)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton("Choose color…")
        self._color_btn.clicked.connect(self._choose_color)
        color_row.addWidget(self._color_btn)
        self._color_clear_btn = QPushButton("Clear")
        self._color_clear_btn.clicked.connect(self._clear_color)
        color_row.addWidget(self._color_clear_btn)
        color_row.addStretch()
        layout.addRow("Highlight color:", color_row)
        self._update_color_btn()

        self._webhook_edit = QLineEdit()
        self._webhook_edit.setPlaceholderText("https://...")
        layout.addRow("Webhook URL:", self._webhook_edit)

        self._script_edit = QLineEdit()
        self._script_edit.setPlaceholderText('echo "$JINKIES_TITLE"')
        layout.addRow("Script (legacy):", self._script_edit)

        # Named sinks the rule fires at.
        self._sinks_list = QListWidget()
        self._sinks_list.setMaximumHeight(96)
        for name in self._sink_names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._sinks_list.addItem(item)
        if self._sink_names:
            layout.addRow("Sinks:", self._sinks_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._test_btn = buttons.addButton(
            "Test…", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._test_btn.clicked.connect(self._dry_run)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_rule(self, rule: Rule) -> None:
        """Populate UI fields from an existing Rule.

        Args:
            rule: The Rule to load.
        """
        self._name_edit.setText(rule.name)
        self._enabled_check.setChecked(rule.enabled)

        # Feed dropdown
        if rule.feed_url:
            idx = self._feed_combo.findData(rule.feed_url)
            if idx >= 0:
                self._feed_combo.setCurrentIndex(idx)
            else:
                # Feed URL not in current list — add it
                self._feed_combo.addItem(rule.feed_url, rule.feed_url)
                self._feed_combo.setCurrentIndex(self._feed_combo.count() - 1)
        else:
            self._feed_combo.setCurrentIndex(0)  # "All feeds"

        self._keyword_edit.setText(rule.keyword or "")

        if rule.status:
            idx = self._status_combo.findText(rule.status, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self._status_combo.setCurrentIndex(idx)
        else:
            self._status_combo.setCurrentIndex(0)  # "Any"

        self._sound_edit.setText(rule.sound_file or "")
        self._notification_check.setChecked(rule.notification)
        self._highlight_color = rule.highlight_color
        self._update_color_btn()
        self._webhook_edit.setText(rule.webhook_url or "")
        self._script_edit.setText(rule.script or "")
        selected = set(rule.sinks)
        for i in range(self._sinks_list.count()):
            item = self._sinks_list.item(i)
            if item.text() in selected:
                item.setCheckState(Qt.CheckState.Checked)

    def _browse_sound(self) -> None:
        """Open a file dialog to pick a WAV file for this rule."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Sound File", "", "WAV Files (*.wav)"
        )
        if path:
            self._sound_edit.setText(path)

    def _choose_color(self) -> None:
        """Open a color dialog to pick the highlight color."""
        initial = QColor(self._highlight_color) if self._highlight_color else QColor()
        color = QColorDialog.getColor(initial, self, "Choose Highlight Color")
        if color.isValid():
            self._highlight_color = color.name()
            self._update_color_btn()

    def _clear_color(self) -> None:
        """Clear the highlight color selection."""
        self._highlight_color = None
        self._update_color_btn()

    def _update_color_btn(self) -> None:
        """Refresh the color button label and background to show the current color."""
        if self._highlight_color:
            self._color_btn.setText(self._highlight_color)
            self._color_btn.setStyleSheet(
                f"background-color: {self._highlight_color}; color: #000;"
            )
        else:
            self._color_btn.setText("Choose color…")
            self._color_btn.setStyleSheet("")

    def _checked_sinks(self) -> list[str]:
        """Return the names of sinks checked in the sinks list."""
        names: list[str] = []
        for i in range(self._sinks_list.count()):
            item = self._sinks_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                names.append(item.text())
        return names

    def _dry_run(self) -> None:
        """Preview which current entries this rule would match."""
        rule = self.get_rule()
        if not self._sample_entries:
            QMessageBox.information(
                self, "Rule Test", "No entries available to test against."
            )
            return
        matched = [e for e in self._sample_entries if rule.matches(e)]
        total = len(self._sample_entries)
        if not matched:
            QMessageBox.information(
                self, "Rule Test", f"0 of {total} entries match this rule."
            )
            return
        sample = "\n".join(f"  • {e.title}" for e in matched[:10])
        more = "" if len(matched) <= 10 else f"\n  …and {len(matched) - 10} more"
        QMessageBox.information(
            self,
            "Rule Test",
            f"{len(matched)} of {total} entries match this rule:\n\n{sample}{more}",
        )

    def _validate_and_accept(self) -> None:
        """Validate required fields then accept."""
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Invalid Rule", "Rule name must not be empty.")
            return
        self.accept()

    def get_rule(self) -> Rule:
        """Build and return a Rule from the current dialog state.

        Returns:
            A new Rule instance reflecting the user's input.
        """
        feed_url = self._feed_combo.currentData()
        keyword = self._keyword_edit.text().strip() or None
        status_text = self._status_combo.currentText()
        status = None if status_text == "Any" else status_text
        sound_file = self._sound_edit.text().strip() or None
        webhook_url = self._webhook_edit.text().strip() or None
        script = self._script_edit.text().strip() or None
        return Rule(
            name=self._name_edit.text().strip(),
            enabled=self._enabled_check.isChecked(),
            feed_url=feed_url,
            keyword=keyword,
            status=status,
            sound_file=sound_file,
            notification=self._notification_check.isChecked(),
            highlight_color=self._highlight_color,
            webhook_url=webhook_url,
            script=script,
            sinks=self._checked_sinks(),
        )


class SinkEditDialog(QDialog):
    """Dialog for creating or editing a single notification sink.

    Provider presets pre-fill the URL, headers, and body template; the user
    can override any of them.  Secrets (e.g. Pushover tokens) are written to
    the OS keyring on accept and never stored in config.
    """

    def __init__(
        self,
        sink: SinkConfig | None = None,
        existing_names: list[str] | None = None,
        parent: QDialog | None = None,
    ) -> None:
        """Initialise the sink editor.

        Args:
            sink: Existing :class:`SinkConfig` to edit, or ``None`` for new.
            existing_names: Names already in use (for uniqueness validation).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Sink" if sink else "Add Sink")
        self.setMinimumWidth(520)
        self._sink = sink
        self._existing_names = set(existing_names or [])
        self._secret_edits: dict[str, QLineEdit] = {}
        self._setup_ui()
        if sink:
            self._load_sink(sink)
        else:
            self._apply_preset(self._provider_combo.currentData())

    def _setup_ui(self) -> None:
        """Build the sink editor UI."""
        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Unique sink name (e.g. team-discord)")
        layout.addRow("Name:", self._name_edit)

        self._provider_combo = QComboBox()
        for key, preset in PROVIDER_PRESETS.items():
            self._provider_combo.addItem(preset.name, key)
        self._provider_combo.currentIndexChanged.connect(
            lambda: self._apply_preset(self._provider_combo.currentData())
        )
        layout.addRow("Provider:", self._provider_combo)

        self._enabled_check = QCheckBox("Enabled")
        self._enabled_check.setChecked(True)
        layout.addRow("", self._enabled_check)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://…")
        layout.addRow("URL:", self._url_edit)

        self._body_edit = QPlainTextEdit()
        self._body_edit.setPlaceholderText(
            "Body template — vars: {title} {link} {status} "
            "{feed_name} {published} {summary}"
        )
        self._body_edit.setMaximumHeight(110)
        self._body_row_label = QLabel("Body template:")
        layout.addRow(self._body_row_label, self._body_edit)

        self._script_edit = QLineEdit()
        self._script_edit.setPlaceholderText('echo "$JINKIES_TITLE"')
        self._script_row_label = QLabel("Script:")
        layout.addRow(self._script_row_label, self._script_edit)

        # Secret fields container (rebuilt per provider).
        self._secrets_group = QGroupBox("Secrets (stored in OS keyring)")
        self._secrets_form = QFormLayout()
        self._secrets_group.setLayout(self._secrets_form)
        layout.addRow(self._secrets_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        test_btn = buttons.addButton(
            "Send Test…", QDialogButtonBox.ButtonRole.ActionRole
        )
        test_btn.clicked.connect(self._send_test)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_preset(self, provider_key: str) -> None:
        """Fill URL/headers/body and secret fields from a provider preset."""
        preset = PROVIDER_PRESETS.get(provider_key)
        if preset is None:
            return
        is_script = preset.transport == "script"
        self._url_edit.setVisible(not is_script)
        self._body_edit.setVisible(not is_script)
        self._body_row_label.setVisible(not is_script)
        self._script_edit.setVisible(is_script)
        self._script_row_label.setVisible(is_script)
        if not self._url_edit.text().strip():
            self._url_edit.setText(preset.url_template)
        if not self._body_edit.toPlainText().strip():
            self._body_edit.setPlainText(preset.body_template)
        self._rebuild_secret_fields(preset.secret_fields)

    def _rebuild_secret_fields(self, keys: tuple[str, ...]) -> None:
        """Rebuild masked secret inputs for the given keys."""
        while self._secrets_form.rowCount():
            self._secrets_form.removeRow(0)
        self._secret_edits = {}
        for key in keys:
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("Leave blank to keep existing")
            self._secrets_form.addRow(f"{key}:", edit)
            self._secret_edits[key] = edit
        self._secrets_group.setVisible(bool(keys))

    def _load_sink(self, sink: SinkConfig) -> None:
        """Populate UI fields from an existing sink config."""
        self._name_edit.setText(sink.name)
        idx = self._provider_combo.findData(sink.provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        self._enabled_check.setChecked(sink.enabled)
        self._url_edit.setText(sink.url)
        self._body_edit.setPlainText(sink.body_template)
        self._script_edit.setText(sink.script)
        self._apply_preset(sink.provider)

    def _build_config(self) -> SinkConfig:
        """Construct a :class:`SinkConfig` from current fields."""
        provider = self._provider_combo.currentData()
        preset = PROVIDER_PRESETS.get(provider)
        transport = preset.transport if preset else "http"
        return SinkConfig(
            name=self._name_edit.text().strip(),
            provider=provider,
            transport=transport,
            url=self._url_edit.text().strip(),
            headers=dict(preset.headers) if preset else {},
            body_template=self._body_edit.toPlainText(),
            script=self._script_edit.text().strip(),
            enabled=self._enabled_check.isChecked(),
        )

    def _persist_secrets(self, sink_name: str) -> None:
        """Write any entered secrets to the keyring for *sink_name*."""
        for key, edit in self._secret_edits.items():
            value = edit.text()
            if value:
                store_sink_secret(sink_name, key, value)

    def _send_test(self) -> None:
        """Send a sample payload through the in-progress sink config."""
        cfg = self._build_config()
        if not cfg.name:
            QMessageBox.warning(self, "Send Test", "Give the sink a name first.")
            return
        # Persist secrets so {secret:KEY} placeholders resolve during the test.
        self._persist_secrets(cfg.name)
        result = build_sink(cfg).test()
        if result.ok:
            code = f" (HTTP {result.status_code})" if result.status_code else ""
            QMessageBox.information(self, "Send Test", f"Success{code}.")
        else:
            QMessageBox.warning(self, "Send Test", f"Failed: {result.error}")

    def _validate_and_accept(self) -> None:
        """Validate name uniqueness then accept, persisting secrets."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Sink", "Sink name must not be empty.")
            return
        if name in self._existing_names:
            QMessageBox.warning(
                self, "Invalid Sink", f"A sink named '{name}' already exists."
            )
            return
        self._persist_secrets(name)
        self.accept()

    def get_sink(self) -> SinkConfig:
        """Return the configured sink.

        Returns:
            A :class:`SinkConfig` reflecting the user's input.
        """
        return self._build_config()
