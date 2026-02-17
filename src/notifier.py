"""Cross-platform desktop notification abstraction for Jinkies.

Uses native QSystemTrayIcon notifications on Linux/macOS,
and a custom animated dialog on Windows for reliable display.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon


class NotificationDialog(QDialog):
    """Custom notification popup for Windows.

    A frameless, semi-transparent dialog that appears at the bottom-right
    of the screen and auto-dismisses after a timeout.

    Attributes:
        _dismiss_timer: Timer for auto-dismissal.
    """

    _active_notifications: list[NotificationDialog] = []

    def __init__(
        self,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        parent: QDialog | None = None,
    ) -> None:
        """Initialize the notification dialog.

        Args:
            title: Notification title text.
            body: Notification body text.
            timeout_ms: Auto-dismiss timeout in milliseconds.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self._setup_ui(title, body)
        self._position_on_screen()

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out)
        self._dismiss_timer.start(timeout_ms)

        self._fade_in()
        NotificationDialog._active_notifications.append(self)

    def _setup_ui(self, title: str, body: str) -> None:
        """Build the notification UI.

        Args:
            title: Notification title.
            body: Notification body text.
        """
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(50, 50, 50, 230);
                border-radius: 8px;
            }
            QLabel#title {
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QLabel#body {
                color: #cccccc;
                font-size: 12px;
            }
            QPushButton#close {
                color: #999999;
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 2px 6px;
            }
            QPushButton#close:hover {
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("title")
        header.addWidget(title_label)

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("close")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self._dismiss)
        header.addWidget(close_btn)
        layout.addLayout(header)

        body_label = QLabel(body)
        body_label.setObjectName("body")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)

    def _position_on_screen(self) -> None:
        """Position the dialog at the bottom-right of the primary screen."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        offset = len(NotificationDialog._active_notifications) * (self.sizeHint().height() + 8)
        x = geo.right() - self.sizeHint().width() - 16
        y = geo.bottom() - self.sizeHint().height() - 16 - offset
        self.move(x, y)

    def _fade_in(self) -> None:
        """Animate the dialog fading in."""
        self.setWindowOpacity(0.0)
        self.show()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _fade_out(self) -> None:
        """Animate the dialog fading out, then close."""
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._dismiss)
        self._anim.start()

    def _dismiss(self) -> None:
        """Close and clean up the notification."""
        self._dismiss_timer.stop()
        if self in NotificationDialog._active_notifications:
            NotificationDialog._active_notifications.remove(self)
        self.close()
        self.deleteLater()

    def mousePressEvent(self, event: object) -> None:
        """Dismiss on click.

        Args:
            event: The mouse press event.
        """
        self._dismiss()


class Notifier:
    """Cross-platform notification dispatcher.

    Uses QSystemTrayIcon.showMessage on Linux/macOS and
    NotificationDialog on Windows.

    Attributes:
        _tray_icon: Reference to the system tray icon.
        _use_custom: Whether to use custom dialog notifications.
    """

    def __init__(
        self,
        tray_icon: QSystemTrayIcon | None = None,
        style: str = "native",
    ) -> None:
        """Initialize the notifier.

        Args:
            tray_icon: The system tray icon (needed for native notifications).
            style: "native" or "custom" notification style.
        """
        self._tray_icon = tray_icon
        self._use_custom = style == "custom" or (style == "native" and sys.platform == "win32")

    def notify(self, title: str, body: str, icon: QIcon | None = None) -> None:
        """Show a desktop notification.

        Args:
            title: Notification title.
            body: Notification body text.
            icon: Optional icon (used for native notifications).
        """
        if self._use_custom:
            NotificationDialog(title, body)
        elif self._tray_icon:
            self._tray_icon.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
