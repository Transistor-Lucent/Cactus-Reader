"""Reusable UI pieces: icon buttons, segmented controls, recent rows, overlays."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..paths import asset_path
from .theme import COLORS, icon


class ElidedLabel(QLabel):
    """A single-line label that shortens itself with an ellipsis."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._full_text = text or ""
        self._apply_elision()

    def fullText(self) -> str:  # noqa: N802 - Qt naming
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        width = self.contentsRect().width()
        if width <= 0:
            super().setText(self._full_text)
            return
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, width
        )
        if super().text() != elided:
            super().setText(elided)
        self.setToolTip(self._full_text if elided != self._full_text else "")


class IconButton(QToolButton):
    def __init__(self, icon_name: str, tooltip: str = "",
                 parent: QWidget | None = None, *, size: int = 38,
                 icon_size: int = 19) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIcon(icon(icon_name))
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setToolTip(tooltip)

    def set_icon(self, icon_name: str, color: str | None = None) -> None:
        self.setIcon(icon(icon_name, color, self.iconSize().width()))


def logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    path = asset_path("cactus.svg")
    if path.exists():
        renderer = QSvgRenderer(str(path))
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter)
            painter.end()
            return pixmap
    # Fallback: a simple painted cactus mark.
    scale = size / 64.0
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#101810"))
    painter.drawRoundedRect(QRect(2, 2, 60, 60).adjusted(0, 0, 0, 0), 14, 14)
    painter.setPen(
        QPen(QColor(COLORS["accent"]), 7, Qt.PenStyle.SolidLine,
             Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    painter.drawLine(QPoint(32, 48), QPoint(32, 19))
    painter.drawLine(QPoint(21, 28), QPoint(21, 35))
    painter.drawLine(QPoint(21, 35), QPoint(27, 35))
    painter.drawLine(QPoint(43, 23), QPoint(43, 31))
    painter.drawLine(QPoint(43, 31), QPoint(37, 31))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#C97B52"))
    painter.drawRoundedRect(QRect(24, 49, 16, 9), 2, 2)
    painter.end()
    return pixmap


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str, str]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedWrap")
        self._buttons: list[tuple[str, QPushButton]] = []
        self._value = options[0][0]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for value, label, tooltip in options:
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            group.addButton(button)
            layout.addWidget(button)
            self._buttons.append((value, button))
            button.clicked.connect(
                lambda _checked=False, v=value: self._activate(v)
            )
        self.set_value(self._value)

    def _activate(self, value: str) -> None:
        if value == self._value:
            return
        self._value = value
        self.changed.emit(value)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        found = False
        for option, button in self._buttons:
            checked = option == value
            button.setChecked(checked)
            found = found or checked
        if found:
            self._value = value


class RecentRow(QFrame):
    opened = Signal(str)
    removed = Signal(str)

    def __init__(self, entry: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = str(entry.get("path") or "")
        self.setObjectName("RecentRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip(self._path)
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 9, 9, 9)
        layout.setSpacing(11)

        mark = QLabel()
        mark.setPixmap(icon("book", COLORS["accent_deep"], 18).pixmap(18, 18))
        mark.setFixedSize(20, 20)
        layout.addWidget(mark)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        title = ElidedLabel(str(entry.get("title") or "未命名漫画"))
        title.setObjectName("RecentTitle")
        meta = ElidedLabel(_entry_meta(entry))
        meta.setObjectName("RecentMeta")
        text_box.addWidget(title)
        text_box.addWidget(meta)
        layout.addLayout(text_box, 1)

        page = QLabel(_entry_page(entry))
        page.setObjectName("RecentPage")
        page.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(page)

        remove = IconButton("close", "从列表中移除", size=26, icon_size=13)
        remove.clicked.connect(lambda: self.removed.emit(self._path))
        layout.addWidget(remove)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.opened.emit(self._path)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.opened.emit(self._path)
            return
        super().keyPressEvent(event)


def _entry_meta(entry: dict) -> str:
    parts = []
    author = str(entry.get("author") or "").strip()
    fmt = str(entry.get("format") or "").strip().upper()
    if author:
        parts.append(author)
    if fmt:
        parts.append(fmt)
    return "  ·  ".join(parts) or "漫画文件"


def _entry_page(entry: dict) -> str:
    try:
        page = int(entry.get("page") or 0) + 1
        total = int(entry.get("total") or 0)
    except (TypeError, ValueError):
        return ""
    return f"{page} / {total}" if total > 0 else f"{page}"


class Toast(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            f"QLabel#Toast {{ background: {COLORS['surface_raised']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border_strong']};"
            " border-radius: 17px; padding: 8px 17px; font-size: 12px; }"
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, msec: int = 1800) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(msec)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(12, (parent.width() - self.width()) // 2)
        y = max(12, parent.height() - self.height() - 78)
        self.move(x, y)


class DropOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def show_over(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
            self.raise_()
            self.show()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(7, 11, 7, 232))
        inner = self.rect().adjusted(24, 24, -24, -24)
        pen = QPen(QColor(COLORS["accent_deep"]), 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 5])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, 18, 18)

        pixmap = logo_pixmap(84)
        painter.drawPixmap(
            (self.width() - 84) // 2, self.height() // 2 - 118, pixmap
        )
        font = QFont(self.font())
        font.setPointSizeF(17)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(
            QRect(0, self.height() // 2 - 12, self.width(), 40),
            Qt.AlignmentFlag.AlignCenter,
            "松开以打开漫画",
        )
        font.setPointSizeF(10.5)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text_muted"]))
        painter.drawText(
            QRect(0, self.height() // 2 + 30, self.width(), 28),
            Qt.AlignmentFlag.AlignCenter,
            "支持 EPUB 与 MOBI 格式",
        )


def vertical_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("VerticalDivider")
    line.setFixedWidth(1)
    line.setFixedHeight(24)
    return line
