"""Tests for src.notifier module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.notifier as notifier_module
from src.notifier import NotificationDialog, Notifier, clear_active_notifications


@pytest.fixture(autouse=True)
def reset_notification_registry():
    """Ensure the active-notification registry is empty before and after each test."""
    clear_active_notifications()
    yield
    clear_active_notifications()


class TestNotifier:
    def test_native_notifier_uses_tray(self, qtbot):
        tray = MagicMock()
        notifier = Notifier(tray_icon=tray, style="native")

        with patch("src.notifier.sys") as mock_sys:
            mock_sys.platform = "linux"
            # Re-init to pick up platform
            notifier = Notifier(tray_icon=tray, style="native")
            notifier._use_custom = False  # Force native for test
            notifier.notify("Title", "Body")
            tray.showMessage.assert_called_once()

    def test_custom_notifier_creates_dialog(self, qtbot):
        notifier = Notifier(style="custom")
        assert notifier._use_custom is True

    def test_no_tray_native_does_not_crash(self, qtbot):
        notifier = Notifier(tray_icon=None, style="native")
        notifier._use_custom = False
        # Should not raise
        notifier.notify("Title", "Body")


class TestNotificationRegistry:
    """Tests for the module-level _active_notifications registry."""

    def test_dialog_added_to_registry_on_creation(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg in notifier_module._active_notifications

    def test_dialog_removed_from_registry_on_dismiss(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg in notifier_module._active_notifications
        dlg._dismiss()
        assert dlg not in notifier_module._active_notifications

    def test_multiple_dialogs_stack_in_registry(self, qtbot):
        dlg1 = NotificationDialog("One", "First", timeout_ms=60000)
        dlg2 = NotificationDialog("Two", "Second", timeout_ms=60000)
        qtbot.addWidget(dlg1)
        qtbot.addWidget(dlg2)
        assert dlg1 in notifier_module._active_notifications
        assert dlg2 in notifier_module._active_notifications
        assert len(notifier_module._active_notifications) == 2

    def test_clear_active_notifications_empties_registry(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert len(notifier_module._active_notifications) == 1
        clear_active_notifications()
        assert notifier_module._active_notifications == []

    def test_registry_is_not_class_attribute(self):
        assert not hasattr(NotificationDialog, "_active_notifications")

    def test_registry_is_module_level(self):
        assert hasattr(notifier_module, "_active_notifications")
        assert isinstance(notifier_module._active_notifications, list)
