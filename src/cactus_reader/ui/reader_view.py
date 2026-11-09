"""The paper-free canvas: page layout, strict fit modes, panning and turns."""

from __future__ import annotations

import math
from collections import OrderedDict

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..book import Book
from ..navigation import (
    can_turn_back,
    can_turn_forward,
    page_status,
    turn_back,
    turn_forward,
    visible_pages,
)
from .theme import COLORS

_CACHE_ENTRIES = 8
_CACHE_BUCKET = 64
_MAX_TARGET_PIXELS = 16_000_000
_GAP = 6.0


class ReaderView(QWidget):
    positionChanged = Signal(int)
    fullscreenRequested = Signal()
    boundaryReached = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._book: Book | None = None
        self._current = 0
        self._two_page = True
        self._step = 2
        self._rtl = False
        self._fit = "height"

        self._pan = QPointF(0.0, 0.0)
        self._content_size = QSize(0, 0)
        self._entries: list[tuple[int, QRectF]] = []
        self._cache: OrderedDict[tuple[int, int, int], QPixmap] = OrderedDict()
        self._errors: dict[int, str] = {}

        self._dragging = False
        self._drag_start = QPoint()
        self._drag_pan = QPointF()
        self._wheel_accum = 0

    # ---- public API ------------------------------------------------------
    @property
    def book(self) -> Book | None:
        return self._book

    @property
    def current_page(self) -> int:
        return self._current

    @property
    def page_count(self) -> int:
        return self._book.page_count if self._book is not None else 0

    def set_book(self, book: Book | None, start_page: int = 0) -> None:
        self._book = book
        self._cache.clear()
        self._errors.clear()
        self._pan = QPointF(0.0, 0.0)
        if book is not None and book.page_count:
            self._current = max(0, min(int(start_page), book.page_count - 1))
        else:
            self._current = 0
        self._refresh_cursor()
        self.update()
        if book is not None and book.page_count:
            self.positionChanged.emit(self._current)

    def set_config(self, *, two_page: bool, step: int, rtl: bool) -> None:
        changed = (
            two_page != self._two_page
            or step != self._step
            or rtl != self._rtl
        )
        self._two_page = bool(two_page)
        self._step = 2 if int(step) == 2 else 1
        self._rtl = bool(rtl)
        if changed:
            self._pan = QPointF(0.0, 0.0)
            self._refresh_cursor()
            self.update()
            self.positionChanged.emit(self._current)

    def set_fit_mode(self, mode: str) -> None:
        mode = mode if mode in ("height", "width") else "height"
        if mode != self._fit:
            self._fit = mode
            self._pan = QPointF(0.0, 0.0)
            self._refresh_cursor()
            self.update()

    def go_to(self, index: int) -> None:
        if self._book is None or self._book.page_count <= 0:
            return
        target = max(0, min(int(index), self._book.page_count - 1))
        if target == self._current:
            return
        self._current = target
        self._pan = QPointF(0.0, 0.0)
        self._refresh_cursor()
        self.update()
        self.positionChanged.emit(target)

    def forward(self) -> None:
        if self._book is None or self._book.page_count <= 0:
            return
        step = self._step if self._two_page else 1
        if not can_turn_forward(self._current, self._book.page_count, self._two_page):
            self.boundaryReached.emit("end")
            return
        target = turn_forward(
            self._current, self._book.page_count, self._two_page, step
        )
        self._turn_to(target)

    def back(self) -> None:
        if self._book is None or self._book.page_count <= 0:
            return
        if not can_turn_back(self._current):
            self.boundaryReached.emit("start")
            return
        step = self._step if self._two_page else 1
        target = turn_back(self._current, self._book.page_count, self._two_page, step)
        self._turn_to(target)

    def first(self) -> None:
        self.go_to(0)

    def last(self) -> None:
        if self._book is None or self._book.page_count <= 0:
            return
        count = self._book.page_count
        target = max(0, count - 2) if self._two_page and count >= 2 else count - 1
        self.go_to(target)

    def can_forward(self) -> bool:
        return (
            self._book is not None
            and can_turn_forward(
                self._current, self._book.page_count, self._two_page
            )
        )

    def can_back(self) -> bool:
        return self._book is not None and can_turn_back(self._current)

    def status_text(self) -> str:
        if self._book is None:
            return "0 / 0"
        return page_status(self._current, self._book.page_count, self._two_page)

    def has_overflow(self) -> bool:
        self._rebuild_layout()
        return (
            self._content_size.width() > self.width() + 1
            or self._content_size.height() > self.height() + 1
        )

    def _turn_to(self, target: int) -> None:
        if target == self._current:
            return
        self.go_to(target)

    # ---- layout ----------------------------------------------------------
    def _visible_indices(self) -> list[int]:
        if self._book is None:
            return []
        return visible_pages(
            self._current, self._book.page_count, self._two_page
        )

    def _rebuild_layout(self) -> None:
        self._entries = []
        self._content_size = QSize(0, 0)
        if self._book is None:
            return
        indices = self._visible_indices()
        if not indices:
            return
        width = max(1, self.width())
        height = max(1, self.height())
        gap = _GAP if len(indices) > 1 else 0.0

        # In right-to-left spreads the earlier page sits on the right.
        visual = list(reversed(indices)) if self._two_page and self._rtl else list(indices)
        aspects = [
            max(0.02, min(50.0, self._book.pages[index].aspect))
            for index in visual
        ]

        if self._fit == "height":
            box_height = float(height)
            widths = [box_height * aspect for aspect in aspects]
            heights = [box_height for _ in aspects]
        else:
            available = max(1.0, width - gap * (len(visual) - 1))
            total_aspect = sum(aspects) or 1.0
            box_height = available / total_aspect
            widths = [box_height * aspect for aspect in aspects]
            heights = [box_height for _ in aspects]

        max_height = max(heights) if heights else 0.0
        total_width = sum(widths) + gap * (len(visual) - 1)
        x = 0.0
        for index, w, h in zip(visual, widths, heights):
            self._entries.append(
                (index, QRectF(x, (max_height - h) / 2.0, w, h))
            )
            x += w + gap
        self._content_size = QSize(
            max(1, int(round(total_width))), max(1, int(round(max_height)))
        )

    def _origin(self) -> QPointF:
        width = self.width()
        height = self.height()
        content_width = self._content_size.width()
        content_height = self._content_size.height()
        if content_width <= width:
            self._pan.setX(0.0)
            x = (width - content_width) / 2.0
        else:
            limit = (content_width - width) / 2.0
            self._pan.setX(max(-limit, min(limit, self._pan.x())))
            x = (width - content_width) / 2.0 + self._pan.x()
        if content_height <= height:
            self._pan.setY(0.0)
            y = (height - content_height) / 2.0
        else:
            limit = (content_height - height) / 2.0
            self._pan.setY(max(-limit, min(limit, self._pan.y())))
            y = (height - content_height) / 2.0 + self._pan.y()
        return QPointF(x, y)

    # ---- painting --------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS["page_bg"]))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._book is None or self._book.page_count <= 0:
            self._paint_message(painter, "没有可显示的页面")
            return

        self._rebuild_layout()
        if not self._entries:
            self._paint_message(painter, "没有可显示的页面")
            return

        origin = self._origin()
        border_pen = QPen(QColor("#1B251C"), 1.0)
        for index, rect in self._entries:
            target = rect.translated(origin)
            pixmap = self._pixmap_for(index, target)
            if pixmap is not None:
                painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
            else:
                self._paint_page_placeholder(painter, target, index)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(target.adjusted(0.5, 0.5, -0.5, -0.5))

    def _paint_message(self, painter: QPainter, text: str) -> None:
        font = QFont(self.font())
        font.setPointSizeF(12)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text_faint"]))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_page_placeholder(self, painter: QPainter, rect: QRectF,
                                index: int) -> None:
        painter.fillRect(rect, QColor("#0D120D"))
        message = self._errors.get(index, "正在载入…")
        font = QFont(self.font())
        font.setPointSizeF(max(9.0, min(13.0, rect.height() / 80.0)))
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text_faint"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, message)

    def _pixmap_for(self, index: int, rect: QRectF) -> QPixmap | None:
        if self._book is None:
            return None
        dpr = max(1.0, self.devicePixelRatioF())
        bucket = _CACHE_BUCKET
        target_w = max(bucket, int(math.ceil(rect.width() * dpr / bucket)) * bucket)
        target_h = max(bucket, int(math.ceil(rect.height() * dpr / bucket)) * bucket)
        target_w = min(target_w, 8192)
        target_h = min(target_h, 8192)
        pixels = target_w * target_h
        if pixels > _MAX_TARGET_PIXELS:
            factor = math.sqrt(_MAX_TARGET_PIXELS / pixels)
            target_w = max(64, int(target_w * factor))
            target_h = max(64, int(target_h * factor))

        key = (index, target_w, target_h)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        page = self._book.pages[index]
        try:
            image = page.source.load_image(QSize(target_w, target_h))
        except Exception as exc:  # a single bad page must not kill the reader
            self._errors[index] = "此页无法显示"
            from ..book import log

            log.warning("Cannot decode page %s: %s", index + 1, exc)
            return None
        if image.isNull():
            self._errors[index] = "此页无法显示"
            return None
        self._errors.pop(index, None)
        pixmap = QPixmap.fromImage(image)
        self._cache[key] = pixmap
        while len(self._cache) > _CACHE_ENTRIES:
            self._cache.popitem(last=False)
        return pixmap

    # ---- interaction -----------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._book is not None
            and self.has_overflow()
        ):
            self._dragging = True
            self._drag_start = event.position().toPoint()
            self._drag_pan = QPointF(self._pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            delta = event.position().toPoint() - self._drag_start
            self._pan = QPointF(
                self._drag_pan.x() + delta.x(), self._drag_pan.y() + delta.y()
            )
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._refresh_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.fullscreenRequested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        self._wheel_accum += delta
        threshold = 90 if event.angleDelta().y() else 36
        if self._wheel_accum <= -threshold:
            self._wheel_accum = 0
            self.forward()
            event.accept()
        elif self._wheel_accum >= threshold:
            self._wheel_accum = 0
            self.back()
            event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._pan = QPointF(0.0, 0.0)
        self._refresh_cursor()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._refresh_cursor()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if not self._dragging:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def _refresh_cursor(self) -> None:
        if self._dragging:
            return
        if self._book is not None and self.has_overflow():
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
