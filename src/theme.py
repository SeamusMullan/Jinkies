"""Application theme support for Jinkies.

Provides QSS stylesheets for the PySide6 application.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Aero theme — Windows Vista/7 glass aesthetic
# Palette:
#   window chrome  : blue gradient  #4a90d9 → #1a5fa8
#   glass surface  : translucent white/blue tint (simulated via solid colour)
#   button         : gradient  #e8f4ff → #c0d8f0, border #7ab0d8
#   button hover   : gradient  #f0f8ff → #d0e8f8, border #4a90d9
#   button pressed : gradient  #a0c8e8 → #5090c8, border #1a5fa8
#   content bg     : #f5f9ff  (very light blue-white)
#   content alt    : #eaf3fc
#   text           : #1a1a2e
#   selection      : #3a80c8
#   border         : #8ab8d8
#   font           : Segoe UI 9pt
# ---------------------------------------------------------------------------

_AERO_QSS = """
/* ── Global font ──────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 9pt;
    color: #1a1a2e;
}

/* ── Window / Widget ──────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #dce9f5;
}
QWidget {
    background-color: transparent;
    color: #1a1a2e;
}
QMainWindow > QWidget,
QDialog > QWidget {
    background-color: #dce9f5;
}

/* ── GroupBox ─────────────────────────────────────────────────────── */
QGroupBox {
    background-color: rgba(255,255,255,160);
    color: #1a3a5c;
    border: 1px solid #8ab8d8;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #1a4a7a;
    font-weight: bold;
}

/* ── Label ────────────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #1a1a2e;
}

/* ── MenuBar ──────────────────────────────────────────────────────── */
QMenuBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c8dff5, stop:1 #a8c8e8);
    border-bottom: 1px solid #6aa0c8;
    padding: 1px;
    color: #1a1a2e;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8f4ff, stop:1 #b8d8f0);
    border: 1px solid #6aa0c8;
}
QMenuBar::item:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a0c8e8, stop:1 #6090b8);
    color: #ffffff;
}

/* ── Menu ─────────────────────────────────────────────────────────── */
QMenu {
    background-color: #eef5fc;
    border: 1px solid #8ab8d8;
    padding: 2px;
}
QMenu::item {
    padding: 5px 28px 5px 14px;
    border-radius: 2px;
}
QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c8e0f8, stop:1 #90b8e0);
    color: #0a0a1e;
    border: 1px solid #6aa0c8;
}
QMenu::separator {
    height: 1px;
    background: #b0cce0;
    margin: 3px 6px;
}

/* ── Toolbar ──────────────────────────────────────────────────────── */
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c8dff5, stop:1 #a0c4e0);
    border-bottom: 1px solid #6aa0c8;
    spacing: 2px;
    padding: 3px 4px;
}
QToolBar QToolButton {
    background: transparent;
    color: #1a1a2e;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 7px;
}
QToolBar QToolButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0f8ff, stop:1 #c8e0f8);
    border-color: #6aa0c8;
}
QToolBar QToolButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a0c8e8, stop:1 #5090c8);
    border-color: #3a70a8;
}
QToolBar QToolButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #b0d0f0, stop:1 #70a8d8);
    border-color: #4a80b8;
}
QToolBar::separator {
    width: 1px;
    background: #90b8d8;
    margin: 4px 3px;
}

/* ── StatusBar ────────────────────────────────────────────────────── */
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #b8d2ec, stop:1 #98bce0);
    border-top: 1px solid #6aa0c8;
    color: #1a3a5c;
}

/* ── Button ───────────────────────────────────────────────────────── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8f4ff, stop:1 #c0d8f0);
    color: #1a1a2e;
    border: 1px solid #7ab0d8;
    border-radius: 3px;
    padding: 4px 14px;
    min-height: 18px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f8fcff, stop:1 #d8ecff);
    border-color: #4a90d9;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #90b8d8, stop:1 #4878a8);
    border-color: #2a60a8;
    color: #ffffff;
}
QPushButton:disabled {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0e8f0, stop:1 #ccd8e8);
    color: #8090a0;
    border-color: #b0c4d4;
}
QPushButton:default {
    border: 2px solid #3a80c8;
}

/* ── Section-header buttons (dashboard unread/read headers) ────────── */
QPushButton[sectionHeader="true"] {
    text-align: left;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c0d8f0, stop:1 #a8c8e8);
    color: #1a3a5c;
    border: none;
    border-bottom: 1px solid #8ab8d8;
    border-top: 1px solid #8ab8d8;
    border-radius: 0;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 9pt;
}
QPushButton[sectionHeader="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8ecff, stop:1 #b8d8f8);
    color: #0a2a4a;
}

/* ── LineEdit ─────────────────────────────────────────────────────── */
QLineEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #8ab8d8;
    border-radius: 2px;
    padding: 3px 6px;
    selection-background-color: #3a80c8;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #3a80c8;
    background-color: #f8fbff;
}
QLineEdit:read-only {
    background-color: #eef4f8;
    color: #4a6070;
}

/* ── TextEdit ─────────────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #8ab8d8;
    border-radius: 2px;
    selection-background-color: #3a80c8;
    selection-color: #ffffff;
}
QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #3a80c8;
}

/* ── ComboBox ─────────────────────────────────────────────────────── */
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8f4ff, stop:1 #c8dcf0);
    color: #1a1a2e;
    border: 1px solid #7ab0d8;
    border-radius: 2px;
    padding: 3px 24px 3px 6px;
    min-width: 60px;
}
QComboBox:hover {
    border-color: #4a90d9;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0f8ff, stop:1 #d8ecff);
}
QComboBox:focus {
    border-color: #3a80c8;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #7ab0d8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8ecff, stop:1 #a8c8e8);
    border-radius: 0 2px 2px 0;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #3a6090;
    width: 0;
    height: 0;
}
QComboBox QAbstractItemView {
    background-color: #eef5fc;
    color: #1a1a2e;
    border: 1px solid #7ab0d8;
    selection-background-color: #3a80c8;
    selection-color: #ffffff;
    outline: none;
}

/* ── SpinBox ──────────────────────────────────────────────────────── */
QSpinBox {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #8ab8d8;
    border-radius: 2px;
    padding: 3px 6px;
}
QSpinBox:focus {
    border-color: #3a80c8;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8ecff, stop:1 #a8c8e8);
    border: none;
    width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8f4ff, stop:1 #b8d8f8);
}
QSpinBox::up-arrow {
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid #3a6090;
    width: 0; height: 0;
}
QSpinBox::down-arrow {
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid #3a6090;
    width: 0; height: 0;
}

/* ── CheckBox ─────────────────────────────────────────────────────── */
QCheckBox {
    color: #1a1a2e;
    spacing: 6px;
    background: transparent;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #7ab0d8;
    border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0f8ff, stop:1 #d0e4f8);
}
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #60a0d8, stop:1 #2868a8);
    border-color: #3a70a8;
    image: none;
}
QCheckBox::indicator:hover {
    border-color: #3a80c8;
}

/* ── ProgressBar ──────────────────────────────────────────────────── */
QProgressBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8ecff, stop:1 #b0ccec);
    color: #1a1a2e;
    border: 1px solid #8ab8d8;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5090d8, stop:1 #2060a8);
    border-radius: 2px;
}

/* ── ScrollBar ────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #d0e4f4;
    width: 14px;
    margin: 14px 0;
    border: 1px solid #a0c0dc;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c8dff5, stop:1 #90b8d8);
    min-height: 20px;
    border: 1px solid #7ab0d8;
    border-radius: 2px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #d8ecff, stop:1 #a8c8e8);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c8dff5, stop:1 #a0c4e0);
    border: 1px solid #90b8d8;
    subcontrol-origin: margin;
}
QScrollBar::sub-line:vertical { subcontrol-position: top; }
QScrollBar::add-line:vertical { subcontrol-position: bottom; }
QScrollBar::up-arrow:vertical {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #3a6090;
    width: 0; height: 0;
}
QScrollBar::down-arrow:vertical {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #3a6090;
    width: 0; height: 0;
}
QScrollBar:horizontal {
    background-color: #d0e4f4;
    height: 14px;
    margin: 0 14px;
    border: 1px solid #a0c0dc;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c8dff5, stop:1 #90b8d8);
    min-width: 20px;
    border: 1px solid #7ab0d8;
    border-radius: 2px;
    margin: 1px;
}
QScrollBar::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d8ecff, stop:1 #a8c8e8);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 14px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c8dff5, stop:1 #a0c4e0);
    border: 1px solid #90b8d8;
    subcontrol-origin: margin;
}
QScrollBar::sub-line:horizontal { subcontrol-position: left; }
QScrollBar::add-line:horizontal { subcontrol-position: right; }
QScrollBar::left-arrow:horizontal {
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    border-right: 5px solid #3a6090;
    width: 0; height: 0;
}
QScrollBar::right-arrow:horizontal {
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    border-left: 5px solid #3a6090;
    width: 0; height: 0;
}

/* ── TableWidget / TableView ──────────────────────────────────────── */
QTableWidget, QTableView {
    background-color: #f5f9ff;
    alternate-background-color: #eaf3fc;
    color: #1a1a2e;
    gridline-color: #c0d8ec;
    border: 1px solid #8ab8d8;
    selection-background-color: #3a80c8;
    selection-color: #ffffff;
}
QTableWidget::item, QTableView::item {
    padding: 2px 5px;
    border: none;
}
QTableWidget::item:selected, QTableView::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5898d8, stop:1 #2868a8);
    color: #ffffff;
}

/* ── HeaderView ───────────────────────────────────────────────────── */
QHeaderView {
    background: transparent;
    border: none;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d0e8f8, stop:1 #b0cce8);
    color: #1a3a5c;
    border: none;
    border-right: 1px solid #90b8d8;
    border-bottom: 1px solid #90b8d8;
    padding: 4px 6px;
    font-weight: bold;
}
QHeaderView::section:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0f0ff, stop:1 #c0dcf4);
}
QHeaderView::section:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a8c8e8, stop:1 #7098c0);
}
QHeaderView::section:first {
    border-left: none;
}

/* ── ListWidget ───────────────────────────────────────────────────── */
QListWidget {
    background-color: #f5f9ff;
    color: #1a1a2e;
    border: 1px solid #8ab8d8;
    alternate-background-color: #eaf3fc;
    outline: none;
}
QListWidget::item {
    padding: 3px 6px;
}
QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5898d8, stop:1 #2868a8);
    color: #ffffff;
    border: none;
}
QListWidget::item:hover:!selected {
    background-color: #daeaf8;
}

/* ── Splitter ─────────────────────────────────────────────────────── */
QSplitter::handle {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #b8d4ec, stop:1 #d8ecff);
}
QSplitter::handle:horizontal {
    width: 4px;
}
QSplitter::handle:vertical {
    height: 4px;
}
QSplitter::handle:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a90d9, stop:1 #2060a8);
}

/* ── TabWidget / TabBar ───────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #8ab8d8;
    background-color: #eef5fc;
}
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d0e4f8, stop:1 #b0c8e4);
    color: #1a3a5c;
    border: 1px solid #8ab8d8;
    border-bottom: none;
    padding: 4px 12px;
    border-radius: 3px 3px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0f8ff, stop:1 #ddeeff);
    border-color: #6aa0c8;
    color: #0a2a4a;
}
QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0f0ff, stop:1 #c0dcf4);
}

/* ── DialogButtonBox ──────────────────────────────────────────────── */
QDialogButtonBox QPushButton {
    min-width: 72px;
}

/* ── MessageBox ───────────────────────────────────────────────────── */
QMessageBox {
    background-color: #dce9f5;
}
QMessageBox QLabel {
    color: #1a1a2e;
    background: transparent;
}
"""

# ---------------------------------------------------------------------------
# Dark theme (retained as fallback)
# ---------------------------------------------------------------------------
_DARK_QSS = """
* { font-family: "Segoe UI", "Arial", sans-serif; font-size: 9pt; }
QMainWindow, QDialog, QWidget { background-color: #1e1e1e; color: #cccccc; }
QGroupBox { background-color: #1e1e1e; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 4px; margin-top: 8px; padding-top: 4px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; color: #aaaaaa; }
QLabel { background-color: transparent; color: #cccccc; }
QToolBar { background-color: #2a2a2a; border-bottom: 1px solid #3a3a3a; spacing: 4px; padding: 2px 4px; }
QToolBar QToolButton { background-color: transparent; color: #cccccc; border: 1px solid transparent; border-radius: 3px; padding: 3px 8px; }
QToolBar QToolButton:hover { background-color: #333333; border-color: #3a3a3a; }
QToolBar QToolButton:pressed { background-color: #0078d4; border-color: #005fa3; }
QToolBar::separator { width: 1px; background-color: #3a3a3a; margin: 4px 2px; }
QStatusBar { background-color: #2a2a2a; color: #aaaaaa; border-top: 1px solid #3a3a3a; }
QMenuBar { background-color: #2a2a2a; color: #cccccc; border-bottom: 1px solid #3a3a3a; }
QMenuBar::item { background-color: transparent; padding: 4px 8px; }
QMenuBar::item:selected { background-color: #333333; }
QMenuBar::item:pressed { background-color: #0078d4; }
QMenu { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; }
QMenu::item { padding: 4px 24px 4px 12px; }
QMenu::item:selected { background-color: #0078d4; color: #ffffff; }
QMenu::separator { height: 1px; background-color: #3a3a3a; margin: 2px 0; }
QPushButton { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; padding: 4px 12px; }
QPushButton:hover { background-color: #333333; border-color: #555555; }
QPushButton:pressed { background-color: #0078d4; border-color: #005fa3; color: #ffffff; }
QPushButton:disabled { background-color: #1e1e1e; color: #555555; border-color: #2a2a2a; }
QPushButton[sectionHeader="true"] { text-align: left; background-color: #2a2a2a; color: #999999; border: none; border-bottom: 1px solid #3a3a3a; border-top: 1px solid #3a3a3a; border-radius: 0; padding: 4px 8px; font-weight: bold; }
QPushButton[sectionHeader="true"]:hover { background-color: #333333; color: #cccccc; }
QLineEdit { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 6px; selection-background-color: #0078d4; selection-color: #ffffff; }
QLineEdit:focus { border-color: #0078d4; }
QLineEdit:read-only { background-color: #242424; color: #888888; }
QTextEdit, QPlainTextEdit { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; selection-background-color: #0078d4; selection-color: #ffffff; }
QTextEdit:focus, QPlainTextEdit:focus { border-color: #0078d4; }
QComboBox { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 24px 3px 6px; min-width: 60px; }
QComboBox:hover { border-color: #555555; }
QComboBox:focus { border-color: #0078d4; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border-left: 1px solid #3a3a3a; border-radius: 0 3px 3px 0; }
QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #cccccc; width: 0; height: 0; }
QComboBox QAbstractItemView { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; selection-background-color: #0078d4; selection-color: #ffffff; outline: none; }
QSpinBox { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 6px; }
QSpinBox:focus { border-color: #0078d4; }
QSpinBox::up-button, QSpinBox::down-button { background-color: #333333; border: none; width: 16px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #444444; }
QCheckBox { color: #cccccc; spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #3a3a3a; border-radius: 2px; background-color: #2a2a2a; }
QCheckBox::indicator:checked { background-color: #0078d4; border-color: #0078d4; }
QCheckBox::indicator:hover { border-color: #555555; }
QProgressBar { background-color: #2a2a2a; color: #cccccc; border: 1px solid #3a3a3a; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background-color: #0078d4; border-radius: 2px; }
QScrollBar:vertical { background-color: #1e1e1e; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background-color: #3a3a3a; min-height: 24px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background-color: #555555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; }
QScrollBar:horizontal { background-color: #1e1e1e; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background-color: #3a3a3a; min-width: 24px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background-color: #555555; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; }
QTableWidget, QTableView { background-color: #1e1e1e; alternate-background-color: #222222; color: #cccccc; gridline-color: #2e2e2e; border: 1px solid #3a3a3a; selection-background-color: #0078d4; selection-color: #ffffff; }
QTableWidget::item, QTableView::item { padding: 2px 4px; }
QHeaderView { background-color: #2a2a2a; color: #cccccc; border: none; }
QHeaderView::section { background-color: #2a2a2a; color: #cccccc; border: none; border-right: 1px solid #3a3a3a; border-bottom: 1px solid #3a3a3a; padding: 4px 6px; }
QHeaderView::section:hover { background-color: #333333; }
QHeaderView::section:checked { background-color: #0078d4; }
QListWidget { background-color: #1e1e1e; color: #cccccc; border: 1px solid #3a3a3a; alternate-background-color: #222222; outline: none; }
QListWidget::item { padding: 3px 6px; }
QListWidget::item:selected { background-color: #0078d4; color: #ffffff; }
QListWidget::item:hover:!selected { background-color: #2e2e2e; }
QSplitter::handle { background-color: #3a3a3a; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:vertical { height: 4px; }
QSplitter::handle:hover { background-color: #0078d4; }
QDialogButtonBox QPushButton { min-width: 72px; }
QMessageBox { background-color: #1e1e1e; color: #cccccc; }
QMessageBox QLabel { color: #cccccc; }
"""


def load_theme(name: str = "aero") -> str:
    """Return a QSS stylesheet string for the requested theme.

    Args:
        name: ``"aero"`` — Windows Aero/Vista/7 aesthetic (default).
              ``"dark"`` — dark flat theme.
              Any other value returns ``""`` (platform default).

    Returns:
        A QSS stylesheet string, or ``""`` for the system default.
    """
    if name == "aero":
        return _AERO_QSS
    if name == "dark":
        return _DARK_QSS
    return ""
