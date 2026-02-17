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
