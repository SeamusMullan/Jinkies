"""Application theme support for Jinkies.

Provides QSS stylesheets for the PySide6 application.
"""

from __future__ import annotations

_DARK_QSS = """
/* ── Base colours ─────────────────────────────────────────────────── */
/* background: #1e1e1e  surface: #2a2a2a  border: #3a3a3a            */
/* text: #cccccc  accent: #0078d4  hover: #333333                     */

/* ── Window / Widget ──────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
}

/* ── GroupBox ─────────────────────────────────────────────────────── */
QGroupBox {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: #aaaaaa;
}

/* ── Label ────────────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #cccccc;
}

/* ── Toolbar ──────────────────────────────────────────────────────── */
QToolBar {
    background-color: #2a2a2a;
    border-bottom: 1px solid #3a3a3a;
    spacing: 4px;
    padding: 2px 4px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #cccccc;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 8px;
}
QToolBar QToolButton:hover {
    background-color: #333333;
    border-color: #3a3a3a;
}
QToolBar QToolButton:pressed {
    background-color: #0078d4;
    border-color: #005fa3;
}
QToolBar::separator {
    width: 1px;
    background-color: #3a3a3a;
    margin: 4px 2px;
}

/* ── StatusBar ────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #2a2a2a;
    color: #aaaaaa;
    border-top: 1px solid #3a3a3a;
}

/* ── MenuBar ──────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #2a2a2a;
    color: #cccccc;
    border-bottom: 1px solid #3a3a3a;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 8px;
}
QMenuBar::item:selected {
    background-color: #333333;
}
QMenuBar::item:pressed {
    background-color: #0078d4;
}

/* ── Menu ─────────────────────────────────────────────────────────── */
QMenu {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
}
QMenu::item {
    padding: 4px 24px 4px 12px;
}
QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #3a3a3a;
    margin: 2px 0;
}

/* ── Button ───────────────────────────────────────────────────────── */
QPushButton {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 12px;
}
QPushButton:hover {
    background-color: #333333;
    border-color: #555555;
}
QPushButton:pressed {
    background-color: #0078d4;
    border-color: #005fa3;
    color: #ffffff;
}
QPushButton:disabled {
    background-color: #1e1e1e;
    color: #555555;
    border-color: #2a2a2a;
}

/* ── Section-header buttons (used in dashboard) ───────────────────── */
QPushButton[sectionHeader="true"] {
    text-align: left;
    background-color: #2a2a2a;
    color: #999999;
    border: none;
    border-bottom: 1px solid #3a3a3a;
    border-top: 1px solid #3a3a3a;
    border-radius: 0;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton[sectionHeader="true"]:hover {
    background-color: #333333;
    color: #cccccc;
}

/* ── LineEdit ─────────────────────────────────────────────────────── */
QLineEdit {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border-color: #0078d4;
}
QLineEdit:read-only {
    background-color: #242424;
    color: #888888;
}

/* ── TextEdit ─────────────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}
QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #0078d4;
}

/* ── ComboBox ─────────────────────────────────────────────────────── */
QComboBox {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 3px 24px 3px 6px;
    min-width: 60px;
}
QComboBox:hover {
    border-color: #555555;
}
QComboBox:focus {
    border-color: #0078d4;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #3a3a3a;
    border-radius: 0 3px 3px 0;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #cccccc;
    width: 0;
    height: 0;
}
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    outline: none;
}

/* ── SpinBox ──────────────────────────────────────────────────────── */
QSpinBox {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 3px 6px;
}
QSpinBox:focus {
    border-color: #0078d4;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #333333;
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #444444;
}

/* ── CheckBox ─────────────────────────────────────────────────────── */
QCheckBox {
    color: #cccccc;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a3a3a;
    border-radius: 2px;
    background-color: #2a2a2a;
}
QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}
QCheckBox::indicator:hover {
    border-color: #555555;
}

/* ── ProgressBar ──────────────────────────────────────────────────── */
QProgressBar {
    background-color: #2a2a2a;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 2px;
}

/* ── ScrollBar ────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #3a3a3a;
    min-height: 24px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}
QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #3a3a3a;
    min-width: 24px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #555555;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
}

/* ── TableWidget / TableView ──────────────────────────────────────── */
QTableWidget, QTableView {
    background-color: #1e1e1e;
    alternate-background-color: #222222;
    color: #cccccc;
    gridline-color: #2e2e2e;
    border: 1px solid #3a3a3a;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}
QTableWidget::item, QTableView::item {
    padding: 2px 4px;
}

/* ── HeaderView ───────────────────────────────────────────────────── */
QHeaderView {
    background-color: #2a2a2a;
    color: #cccccc;
    border: none;
}
QHeaderView::section {
    background-color: #2a2a2a;
    color: #cccccc;
    border: none;
    border-right: 1px solid #3a3a3a;
    border-bottom: 1px solid #3a3a3a;
    padding: 4px 6px;
}
QHeaderView::section:hover {
    background-color: #333333;
}
QHeaderView::section:checked {
    background-color: #0078d4;
}

/* ── ListWidget ───────────────────────────────────────────────────── */
QListWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #3a3a3a;
    alternate-background-color: #222222;
    outline: none;
}
QListWidget::item {
    padding: 3px 6px;
}
QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #2e2e2e;
}

/* ── Splitter ─────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #3a3a3a;
}
QSplitter::handle:horizontal {
    width: 4px;
}
QSplitter::handle:vertical {
    height: 4px;
}
QSplitter::handle:hover {
    background-color: #0078d4;
}

/* ── DialogButtonBox ──────────────────────────────────────────────── */
QDialogButtonBox QPushButton {
    min-width: 72px;
}

/* ── MessageBox ───────────────────────────────────────────────────── */
QMessageBox {
    background-color: #1e1e1e;
    color: #cccccc;
}
QMessageBox QLabel {
    color: #cccccc;
}
"""


def load_theme(name: str = "dark") -> str:
    """Return a QSS stylesheet string for the requested theme.

    Args:
        name: Theme name.  ``"dark"`` returns the built-in dark palette.
            Any other value (e.g. ``"light"``) returns an empty string so
            the platform default style is used.

    Returns:
        A QSS stylesheet string, or ``""`` for the system default.
    """
    if name == "dark":
        return _DARK_QSS
    return ""
