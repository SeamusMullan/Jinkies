"""Tests for src.notifier module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import src.notifier as notifier_module
from src.notifier import NotificationDialog, Notifier


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


class TestActiveNotificationsRegistry:
    """Tests that _active_notifications is a proper module-level singleton."""

    def setup_method(self):
        """Ensure the registry is empty before each test."""
        notifier_module._active_notifications.clear()

    def teardown_method(self):
        """Clean up any lingering notifications after each test."""
        for n in list(notifier_module._active_notifications):
            n._dismiss_timer.stop()
            n.close()
        notifier_module._active_notifications.clear()

    def test_registry_is_module_level(self):
        """_active_notifications must live on the module, not the class."""
        assert hasattr(notifier_module, "_active_notifications")
        assert not hasattr(NotificationDialog, "_active_notifications")

    def test_dialog_registered_on_creation(self, qtbot):
        dlg = NotificationDialog("T", "B", timeout_ms=60_000)
        qtbot.addWidget(dlg)
        assert dlg in notifier_module._active_notifications

    def test_dialog_removed_on_dismiss(self, qtbot):
        dlg = NotificationDialog("T", "B", timeout_ms=60_000)
        qtbot.addWidget(dlg)
        assert dlg in notifier_module._active_notifications
        dlg._dismiss()
        assert dlg not in notifier_module._active_notifications

    def test_registry_isolated_between_contexts(self, qtbot):
        """Registry must start empty (setup_method cleared it)."""
        assert notifier_module._active_notifications == []
        dlg = NotificationDialog("T", "B", timeout_ms=60_000)
        qtbot.addWidget(dlg)
        assert len(notifier_module._active_notifications) == 1
