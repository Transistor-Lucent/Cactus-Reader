"""Visual language for Cactus Reader: a calm, dark, green-accented theme."""

from __future__ import annotations

import sys

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

COLORS = {
    "bg": "#0A0D0A",
    "surface": "#111611",
    "surface_raised": "#172017",
    "surface_hover": "#1D281D",
    "border": "#263126",
    "border_strong": "#334234",
    "text": "#EDF3EA",
    "text_muted": "#99A79A",
    "text_faint": "#6F7D70",
    "accent": "#8BD97A",
    "accent_bright": "#A9EB93",
    "accent_deep": "#4F8F4B",
    "accent_soft": "#243622",
    "page_bg": "#060806",
    "warning": "#E7A85C",
    "danger": "#E07A6D",
}

_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Segoe UI",
)

_ICON_PATHS: dict[str, str] = {
    "open": (
        '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v7'
        'A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z"/>'
    ),
    "settings": (
        '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/>'
        '<circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/>'
    ),
    "help": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M9.6 9.2a2.6 2.6 0 1 1 3.8 2.3c-.8.5-1.4 1.1-1.4 2.1v.4"/>'
        '<path d="M12 17h.01"/>'
    ),
    "fullscreen": (
        '<path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3'
        'M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/>'
    ),
    "fullscreen-exit": (
        '<path d="M8 3v3a2 2 0 0 1-2 2H3M16 3v3a2 2 0 0 0 2 2h3'
        'M8 21v-3a2 2 0 0 0-2-2H3M16 21v-3a2 2 0 0 1 2-2h3"/>'
    ),
    "chevron-left": '<path d="M15 4.5 7.5 12 15 19.5"/>',
    "chevron-right": '<path d="M9 4.5 16.5 12 9 19.5"/>',
    "fit-height": (
        '<path d="M12 3v18M8 7l4-4 4 4M8 17l4 4 4-4"/>'
    ),
    "fit-width": '<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
    "rotate-ccw": (
        '<path d="M1 4v6h6"/>'
        '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>'
    ),
    "rotate-cw": (
        '<path d="M23 4v6h-6"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>'
    ),
    "view-single": '<rect x="7" y="4" width="10" height="16" rx="1.6"/>',
    "view-double": (
        '<rect x="3" y="4" width="8" height="16" rx="1.4"/>'
        '<rect x="13" y="4" width="8" height="16" rx="1.4"/>'
    ),
    "direction-ltr": '<path d="M4 12h16M16 8l4 4-4 4"/>',
    "direction-rtl": '<path d="M20 12H4M8 8l-4 4 4 4"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "reset": (
        '<path d="M4 4v6h6"/>'
        '<path d="M4.6 10a8 8 0 1 1 1.9 8.4"/>'
    ),
    "book": (
        '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23z"/>'
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
    ),
    "keyboard": (
        '<rect x="2.5" y="6" width="19" height="12" rx="2"/>'
        '<path d="M6 10h.01M9.5 10h.01M13 10h.01M16.5 10h.01M8 14h8"/>'
    ),
}


def _font_family() -> str:
    available = set(QFontDatabase.families())
    for family in _FONT_CANDIDATES:
        if family in available:
            return family
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def apply_theme(app) -> None:
    family = _font_family()
    font = QFont(family, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet(family))


def enable_dark_titlebar(widget) -> None:
    """Ask Windows 10/11 to draw a dark native title bar."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new/old)
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
            if result == 0:
                break
    except Exception:
        pass


def icon(name: str, color: str | None = None, size: int = 20) -> QIcon:
    color = color or COLORS["text_muted"]
    path = _ICON_PATHS.get(name, "")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{path}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixel_size = max(24, size * 4)
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def app_icon() -> QIcon:
    from ..paths import asset_path

    for name in ("icon.ico", "icon.png"):
        path = asset_path(name)
        if path.exists():
            result = QIcon(str(path))
            if not result.isNull():
                return result
    from .widgets import logo_pixmap

    return QIcon(logo_pixmap(256))


def stylesheet(family: str) -> str:
    c = COLORS
    return f"""
* {{
    outline: none;
}}
QWidget {{
    background: transparent;
    color: {c['text']};
    font-family: "{family}";
    font-size: 13px;
}}
QMainWindow, QWidget#Root, QWidget#WelcomePage {{
    background: {c['bg']};
}}
QFrame#Header {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
}}
QFrame#Footer {{
    background: {c['surface']};
    border-top: 1px solid {c['border']};
}}
QLabel#HeaderTitle {{
    color: {c['text']};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#HeaderMeta {{
    color: {c['text_muted']};
    font-size: 12px;
}}
QLabel#Wordmark {{
    color: {c['text']};
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
QLabel#WelcomeTitle {{
    color: {c['text']};
    font-size: 34px;
    font-weight: 800;
}}
QLabel#WelcomeTagline {{
    color: {c['text_muted']};
    font-size: 14px;
}}
QLabel#WelcomeHint {{
    color: {c['text_faint']};
    font-size: 12px;
}}
QLabel#SectionLabel {{
    color: {c['text']};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#MutedLabel {{
    color: {c['text_muted']};
    font-size: 12px;
}}
QLabel#PageStatus {{
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#DialogTitle {{
    color: {c['text']};
    font-size: 23px;
    font-weight: 800;
}}
QLabel#DialogIntro {{
    color: {c['text_muted']};
    font-size: 13px;
}}
QLabel#HintLabel {{
    color: {c['text_muted']};
    font-size: 12px;
}}
QLabel#CardTitle {{
    color: {c['text']};
    font-size: 14px;
    font-weight: 700;
}}
QFrame#Card {{
    background: {c['surface_raised']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QFrame#Divider {{
    background: {c['border']};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QFrame#VerticalDivider {{
    background: {c['border']};
    max-width: 1px;
    min-width: 1px;
    border: none;
}}
QToolButton#IconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 6px;
}}
QToolButton#IconButton:hover {{
    background: {c['surface_hover']};
    border-color: {c['border']};
}}
QToolButton#IconButton:pressed {{
    background: {c['accent_soft']};
}}
QToolButton#IconButton:disabled {{
    background: transparent;
}}
QToolButton#EdgeTurnButton {{
    background: rgba(10, 13, 10, 176);
    border: 1px solid rgba(51, 66, 52, 216);
    border-radius: 20px;
}}
QToolButton#EdgeTurnButton:hover {{
    background: rgba(29, 40, 29, 224);
    border-color: {c['accent_deep']};
}}
QToolButton#EdgeTurnButton:pressed {{
    background: rgba(79, 143, 75, 230);
    border-color: {c['accent']};
}}
QToolButton#EdgeTurnButton:disabled {{
    background: rgba(10, 13, 10, 104);
    border-color: rgba(51, 66, 52, 120);
}}
QPushButton {{
    background: {c['surface_raised']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {c['surface_hover']};
    border-color: {c['border_strong']};
}}
QPushButton:pressed {{
    background: {c['accent_soft']};
}}
QPushButton:disabled {{
    color: {c['text_faint']};
    background: {c['surface']};
}}
QPushButton#PrimaryButton {{
    background: {c['accent']};
    color: #0B140B;
    border: none;
    border-radius: 10px;
    padding: 11px 22px;
    font-weight: 800;
}}
QPushButton#PrimaryButton:hover {{
    background: {c['accent_bright']};
}}
QPushButton#PrimaryButton:pressed {{
    background: {c['accent_deep']};
    color: #F2FFF0;
}}
QPushButton#ChipButton {{
    background: transparent;
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 6px 11px;
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#ChipButton:hover {{
    background: {c['surface_hover']};
    color: {c['text']};
    border-color: {c['border_strong']};
}}
QPushButton#LinkButton {{
    background: transparent;
    border: none;
    color: {c['text_muted']};
    padding: 4px 6px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#LinkButton:hover {{
    color: {c['accent']};
}}
QFrame#SegmentedWrap {{
    background: {c['bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QPushButton#SegmentButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 7px 15px;
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#SegmentButton:hover {{
    color: {c['text']};
    background: {c['surface_hover']};
}}
QPushButton#SegmentButton:checked {{
    background: {c['accent_soft']};
    border-color: {c['accent_deep']};
    color: {c['accent_bright']};
}}
QPushButton#SegmentButton:disabled {{
    color: {c['text_faint']};
    background: transparent;
}}
QLineEdit#GapInput, QLineEdit#DelayInput {{
    background: {c['bg']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 7px;
    padding: 5px 7px;
    font-size: 12px;
    font-weight: 700;
    selection-background-color: {c['accent_deep']};
}}
QLineEdit#GapInput:focus, QLineEdit#DelayInput:focus {{
    border-color: {c['accent_deep']};
    background: {c['surface']};
}}
QFrame#RecentRow {{
    background: {c['surface_raised']};
    border: 1px solid {c['border']};
    border-radius: 11px;
}}
QFrame#RecentRow:hover {{
    background: {c['surface_hover']};
    border-color: {c['border_strong']};
}}
QFrame#RecentRow:focus {{
    border-color: {c['accent_deep']};
}}
QLabel#RecentTitle {{
    color: {c['text']};
    font-size: 13px;
    font-weight: 700;
}}
QLabel#RecentMeta {{
    color: {c['text_faint']};
    font-size: 11px;
}}
QLabel#RecentPage {{
    color: {c['text_muted']};
    font-size: 11px;
    font-weight: 600;
}}
QFrame#EmptyRecent {{
    background: transparent;
    border: 1px dashed {c['border_strong']};
    border-radius: 11px;
}}
QLabel#EmptyRecentText {{
    color: {c['text_faint']};
    font-size: 12px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_faint']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']};
    min-width: 28px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QDialog#SettingsDialog, QDialog#HelpDialog {{
    background: {c['bg']};
}}
QFrame#SettingsFooter {{
    background: {c['bg']};
    border-top: 1px solid {c['border']};
}}
QToolTip {{
    background: {c['surface_hover']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}}
QMessageBox {{
    background: {c['surface']};
}}
QMessageBox QLabel {{
    color: {c['text']};
    font-size: 13px;
}}
QTextBrowser {{
    background: transparent;
    border: none;
    color: {c['text_muted']};
    selection-background-color: {c['accent_deep']};
    font-size: 13px;
}}
QSplitter::handle {{
    background: {c['border']};
}}
"""
