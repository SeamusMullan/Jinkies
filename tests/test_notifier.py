"""Tests for src.notifier module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QGuiApplication

from src.notifier import NotificationDialog, Notifier


class TestNotificationDialog:
    @pytest.fixture(autouse=True)
    def clear_active_notifications(self):
        """Isolate _active_notifications between tests to prevent pollution."""
        NotificationDialog._active_notifications.clear()
        yield
        NotificationDialog._active_notifications.clear()

    def test_active_notifications_tracks_instance(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg in NotificationDialog._active_notifications

    def test_multiple_dialogs_all_tracked(self, qtbot):
        dlg1 = NotificationDialog("T1", "B1", timeout_ms=60000)
        dlg2 = NotificationDialog("T2", "B2", timeout_ms=60000)
        qtbot.addWidget(dlg1)
        qtbot.addWidget(dlg2)
        assert dlg1 in NotificationDialog._active_notifications
        assert dlg2 in NotificationDialog._active_notifications
        assert len(NotificationDialog._active_notifications) == 2

    def test_position_within_screen_bounds(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            pytest.skip("No primary screen available to validate dialog geometry")
        geo = screen.availableGeometry()
        assert geo.contains(dlg.geometry())

    def test_position_stacked_above_previous(self, qtbot):
        dlg1 = NotificationDialog("T1", "B1", timeout_ms=60000)
        dlg2 = NotificationDialog("T2", "B2", timeout_ms=60000)
        qtbot.addWidget(dlg1)
        qtbot.addWidget(dlg2)
        # Second dialog should be stacked higher (smaller y) than the first
        assert dlg2.pos().y() < dlg1.pos().y()

    def test_fade_in_shows_widget(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg.isVisible()

    def test_fade_in_animation_properties(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_anim")
        assert dlg._anim.startValue() == 0.0
        assert dlg._anim.endValue() == 1.0
        assert dlg._anim.duration() == 200

    def test_fade_out_animation_properties(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        dlg._fade_out()
        assert dlg._anim.startValue() == 1.0
        assert dlg._anim.endValue() == 0.0
        assert dlg._anim.duration() == 300

    def test_fade_out_connects_finished_to_dismiss(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        called = []
        dlg._dismiss = lambda: called.append(True)
        dlg._fade_out()
        # Directly emit finished to verify the connection without relying on
        # animation timing (offscreen platform may not support opacity changes)
        dlg._anim.finished.emit()
        assert called

    def test_dismiss_removes_from_active_notifications(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg in NotificationDialog._active_notifications
        dlg._dismiss()
        assert dlg not in NotificationDialog._active_notifications

    def test_dismiss_stops_timer(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg._dismiss_timer.isActive()
        dlg._dismiss()
        assert not dlg._dismiss_timer.isActive()

    def test_dismiss_closes_dialog(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        assert dlg.isVisible()
        dlg._dismiss()
        assert not dlg.isVisible()

    def test_dismiss_is_idempotent(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        dlg._dismiss()
        dlg._dismiss()  # second call must not raise

    def test_mouse_press_event_dismisses(self, qtbot):
        dlg = NotificationDialog("Title", "Body", timeout_ms=60000)
        qtbot.addWidget(dlg)
        called = []
        dlg._dismiss = lambda: called.append(True)
        dlg.mousePressEvent(MagicMock())
        assert called


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
