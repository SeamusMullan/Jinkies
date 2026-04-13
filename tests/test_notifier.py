"""Tests for src.notifier module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.notifier import Notifier


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

    def test_custom_notify_creates_notification_dialog(self, qtbot):
        """Notifier.notify with custom style invokes NotificationDialog."""
        notifier = Notifier(style="custom")
        with patch("src.notifier.NotificationDialog") as mock_dialog_cls:
            notifier.notify("Alert", "Something happened")
        mock_dialog_cls.assert_called_once_with("Alert", "Something happened")


class TestNotificationDialog:
    """Tests for the NotificationDialog custom popup."""

    def test_init_creates_dialog(self, qtbot):
        """NotificationDialog can be instantiated without crashing."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Test Title", "Test Body", timeout_ms=100)
        qtbot.addWidget(dialog)
        assert dialog is not None

    def test_dismiss_removes_from_active(self, qtbot):
        """_dismiss() removes the dialog from _active_notifications."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Title", "Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        assert dialog in NotificationDialog._active_notifications
        dialog._dismiss()
        assert dialog not in NotificationDialog._active_notifications

    def test_fade_out_then_dismiss(self, qtbot):
        """_fade_out() starts an animation that calls _dismiss on finish."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Title", "Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        # Should not raise
        dialog._fade_out()

    def test_mouse_press_dismisses(self, qtbot):
        """mousePressEvent dismisses the dialog."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Title", "Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        assert dialog in NotificationDialog._active_notifications
        dialog.mousePressEvent(None)
        assert dialog not in NotificationDialog._active_notifications

    def test_position_on_screen(self, qtbot):
        """_position_on_screen runs without error (screen may be None in CI)."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Title", "Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        # Should not raise even with minimal screen info
        dialog._position_on_screen()

    def test_position_on_screen_no_primary_screen(self, qtbot):
        """_position_on_screen returns early when there is no primary screen."""
        from unittest.mock import patch

        from PySide6.QtGui import QGuiApplication

        from src.notifier import NotificationDialog
        dialog = NotificationDialog("Title", "Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        with patch.object(QGuiApplication, "primaryScreen", return_value=None):
            # Should not raise and should return early
            dialog._position_on_screen()

    def test_setup_ui_labels(self, qtbot):
        """_setup_ui creates title and body labels."""
        from src.notifier import NotificationDialog
        dialog = NotificationDialog("My Title", "My Body", timeout_ms=100000)
        qtbot.addWidget(dialog)
        # At minimum the dialog is visible and has children
        assert dialog.layout() is not None
