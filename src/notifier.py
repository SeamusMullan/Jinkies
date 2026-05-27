"""Cross-platform desktop notification abstraction for Jinkies.

Uses native QSystemTrayIcon notifications on Linux/macOS,
and a custom animated dialog on Windows for reliable display.
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon

# Module-level registry of active notification dialogs.
# Using a module-level list (rather than a class attribute) avoids the
# shared-mutable-state problem: the registry is a single, explicit
# singleton that is not accidentally inherited by subclasses and can be
# cleared in tests without touching the class itself.
_active_notifications: list[NotificationDialog] = []

# Jenkins build result keywords \u2192 accent colour (RGB).
_JENKINS_STATUS_COLORS: dict[str, tuple[int, int, int]] = {
    "stable": (40, 167, 69),
    "success": (40, 167, 69),
    "fixed": (40, 167, 69),
    "broken": (220, 53, 69),
    "failed": (220, 53, 69),
    "failure": (220, 53, 69),
    "unstable": (255, 152, 0),
    "aborted": (108, 117, 125),
    "cancelled": (108, 117, 125),
}

_JENKINS_STATUS_RE = re.compile(
    r"\((" + "|".join(_JENKINS_STATUS_COLORS) + r")\)\s*$",
    re.IGNORECASE,
)


def _jenkins_accent(title: str) -> tuple[int, int, int] | None:
    """Return an RGB accent colour if the title contains a Jenkins status suffix."""
    m = _JENKINS_STATUS_RE.search(title)
    if m:
        return _JENKINS_STATUS_COLORS[m.group(1).lower()]
    return None


def jenkins_status(title: str) -> tuple[str, tuple[int, int, int]] | None:
    """Return (keyword, rgb) if title contains a Jenkins status suffix."""
    m = _JENKINS_STATUS_RE.search(title)
    if m:
        kw = m.group(1).lower()
        return kw, _JENKINS_STATUS_COLORS[kw]
    return None


class NotificationDialog(QDialog):
    """Custom notification popup for Windows.

    A frameless dialog that appears at the bottom-right of the screen
    and auto-dismisses after a timeout.  Clicking the body opens the
    optional URL in the default browser.

    Attributes:
        _dismiss_timer: Timer for auto-dismissal.
        _url: Optional URL to open on click.
    """

    def __init__(
        self,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        url: str | None = None,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(280)
        self.setMaximumWidth(520)
        self._setup_ui(title, body)
        self.adjustSize()
        self._position_on_screen()

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out)
        self._dismiss_timer.start(timeout_ms)

        self._fade_in()
        _active_notifications.append(self)

    def _setup_ui(self, title: str, body: str) -> None:
        accent = _jenkins_accent(title)
        accent_css = (
            f"rgb({accent[0]},{accent[1]},{accent[2]})" if accent else "#555555"
        )

        # Outer layout on QDialog \u2014 transparent, just holds the card frame.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Card frame \u2014 this is the visible, opaque surface.
        card = QFrame(self)
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        card.setStyleSheet(f"""
            QFrame#card {{
                background-color: rgb(40, 40, 40);
                border-radius: 8px;
                border-left: 4px solid {accent_css};
            }}
            QLabel#title {{
                color: white;
                font-weight: bold;
                font-size: 13px;
            }}
            QLabel#body {{
                color: #cccccc;
                font-size: 12px;
            }}
            QPushButton#close {{
                color: #888888;
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 2px 6px;
            }}
            QPushButton#close:hover {{
                color: white;
            }}
        """)
        outer.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 8, 10)
        card_layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("title")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(title_label)

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("close")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self._dismiss)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(header)

        body_label = QLabel(body)
        body_label.setObjectName("body")
        body_label.setWordWrap(True)
        card_layout.addWidget(body_label)

        if self._url:
            hint = QLabel("Click to open \u2197")
            hint.setStyleSheet("color: #666666; font-size: 10px;")
            card_layout.addWidget(hint)

    def _position_on_screen(self) -> None:
        """Position the dialog at the bottom-right of the primary screen."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        # Filter to only visible notifications to avoid stale entries
        # affecting the offset calculation.
        visible = [n for n in _active_notifications if n.isVisible()]
        offset = len(visible) * (self.height() + 8)
        x = geo.right() - self.width() - 16
        y = geo.bottom() - self.height() - 16 - offset
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
        if self in _active_notifications:
            _active_notifications.remove(self)
        self.close()
        self.deleteLater()

    def mousePressEvent(self, event: object) -> None:
        if self._url:
            QDesktopServices.openUrl(QUrl(self._url))
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
        self._tray_icon = tray_icon
        self._use_custom = style == "custom" or (style == "native" and sys.platform == "win32")

    def notify(self, title: str, body: str, url: str | None = None, icon: QIcon | None = None) -> None:
        """Show a desktop notification.

        Args:
            title: Notification title.
            body: Notification body text.
            url: Optional URL to open when the custom notification is clicked.
            icon: Optional icon (used for native notifications).
        """
        if self._use_custom:
            NotificationDialog(title, body, url=url)
        elif self._tray_icon:
            self._tray_icon.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
