"""Main window: chrome, file loading, shortcuts, persistence and fullscreen."""

from __future__ import annotations

import logging
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..book import Book, BookError, DrmProtectedError, load_book
from ..settings import Settings
from .help_dialog import HelpDialog
from .reader_view import ReaderView
from .settings_dialog import SettingsDialog
from .theme import COLORS, app_icon, icon
from .widgets import (
    DropOverlay,
    EdgeTurnButton,
    ElidedLabel,
    IconButton,
    PageSlider,
    Toast,
    logo_pixmap,
    vertical_divider,
)
from .welcome import WelcomePage

log = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".epub", ".mobi", ".prc", ".azw", ".azw3", ".pdf"}
_FILE_FILTER = (
    "漫画文件 (*.epub *.mobi *.prc *.azw *.azw3 *.pdf);;所有文件 (*.*)"
)


class MainWindow(QMainWindow):
    # How far around a fullscreen edge button the pointer can be and still
    # reveal it.
    _EDGE_HOVER_PAD = 56

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._book: Book | None = None
        self._fullscreen = False
        self._was_maximized = False
        self._windowed_geometry: QRect | None = None

        self.setWindowTitle("Cactus Reader")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(880, 620)
        self.setAcceptDrops(True)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1200)
        self._save_timer.timeout.connect(self._save_settings)

        # The footer stays out of the reading area until the pointer reaches
        # the bottom edge of the window.
        self._footer_timer = QTimer(self)
        self._footer_timer.setInterval(80)
        self._footer_timer.timeout.connect(self._update_footer_visibility)

        # Polls the pointer while fullscreen so the edge buttons appear as
        # soon as the mouse approaches them, even while it rests over another
        # widget.
        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(50)
        self._edge_timer.timeout.connect(self._update_edge_buttons)
        self._edge_timer.timeout.connect(self._poll_cursor_hide)

        # Pointer idle tracking for fullscreen cursor hiding.  Timestamps use
        # a monotonic clock so sleep/suspend cannot make the pointer vanish.
        self._cursor_hidden = False
        self._cursor_last_pos = QCursor.pos()
        self._cursor_idle_since = monotonic()

        self._build_ui()
        self._build_shortcuts()
        self._restore_geometry()
        self._refresh_welcome()
        self._apply_reading_settings()
        self._update_header_for_book()
        self._sync_controls()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # ---- construction ----------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        self._central = central
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header ---------------------------------------------------------
        self._header = QFrame()
        self._header.setObjectName("Header")
        self._header.setFixedHeight(56)
        header_box = QHBoxLayout(self._header)
        header_box.setContentsMargins(18, 8, 16, 8)
        header_box.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(34))
        logo.setFixedSize(34, 34)
        header_box.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._header_title = ElidedLabel("Cactus Reader")
        self._header_title.setObjectName("HeaderTitle")
        self._header_meta = ElidedLabel("EPUB / MOBI / PDF 漫画阅读器")
        self._header_meta.setObjectName("HeaderMeta")
        title_box.addWidget(self._header_title)
        title_box.addWidget(self._header_meta)
        header_box.addLayout(title_box, 1)

        # Page-turn arrows live in the header, just before the open button.
        self._left_button = IconButton("chevron-left", size=40, icon_size=17)
        self._left_button.clicked.connect(self._left_action)
        header_box.addWidget(self._left_button)

        self._right_button = IconButton("chevron-right", size=40, icon_size=17)
        self._right_button.clicked.connect(self._right_action)
        header_box.addWidget(self._right_button)

        self._turn_divider = vertical_divider()
        header_box.addWidget(self._turn_divider)
        header_box.addSpacing(16)

        self._open_button = QPushButton("打开漫画")
        self._open_button.setIcon(icon("open", COLORS["text"], 17))
        self._open_button.setIconSize(QSize(17, 17))
        self._open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_button.setFixedHeight(36)
        self._open_button.setToolTip("打开 EPUB / MOBI / PDF 漫画（Ctrl+O）")
        self._open_button.clicked.connect(self.open_dialog)
        header_box.addWidget(self._open_button)

        self._settings_button = IconButton("settings", "阅读设置（Ctrl+,）")
        self._settings_button.clicked.connect(self.open_settings)
        header_box.addWidget(self._settings_button)

        self._help_button = IconButton("help", "使用帮助（F1）")
        self._help_button.clicked.connect(self.show_help)
        header_box.addWidget(self._help_button)

        self._full_button = IconButton("fullscreen", "全屏（F）")
        self._full_button.clicked.connect(self.toggle_fullscreen)
        header_box.addWidget(self._full_button)
        root.addWidget(self._header)

        # Pages ----------------------------------------------------------
        self._stack = QStackedWidget()
        self._welcome = WelcomePage()
        self._reader = ReaderView()
        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._reader)
        self._stack.setCurrentWidget(self._welcome)
        root.addWidget(self._stack, 1)

        self._welcome.openRequested.connect(self.open_dialog)
        self._welcome.recentOpened.connect(self._open_recent)
        self._welcome.recentRemoved.connect(self._remove_recent)
        self._welcome.clearRecentRequested.connect(self._clear_recent)
        self._reader.positionChanged.connect(self._on_position_changed)
        self._reader.fullscreenRequested.connect(self.toggle_fullscreen)
        self._reader.boundaryReached.connect(self._on_boundary)
        self._reader.zoomChanged.connect(self._on_zoom_changed)

        # Footer ---------------------------------------------------------
        self._footer = QFrame()
        self._footer.setObjectName("Footer")
        self._footer.setFixedHeight(50)
        footer_box = QHBoxLayout(self._footer)
        footer_box.setContentsMargins(16, 8, 16, 8)
        footer_box.setSpacing(8)

        self._slider = PageSlider()
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._on_slider)
        footer_box.addWidget(self._slider, 1)

        self._status = QLabel("0 / 0")
        self._status.setObjectName("PageStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setFixedWidth(92)
        footer_box.addWidget(self._status)

        footer_box.addWidget(vertical_divider())

        self._fit_button = QPushButton("铺满高度")
        self._fit_button.setObjectName("ChipButton")
        self._fit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_button.setFixedHeight(32)
        self._fit_button.setIconSize(QSize(15, 15))
        self._fit_button.clicked.connect(self.toggle_fit)
        footer_box.addWidget(self._fit_button)

        self._view_button = QPushButton("双页")
        self._view_button.setObjectName("ChipButton")
        self._view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_button.setFixedHeight(32)
        self._view_button.setIconSize(QSize(15, 15))
        self._view_button.clicked.connect(self.toggle_view_mode)
        footer_box.addWidget(self._view_button)

        self._direction_button = QPushButton("左→右")
        self._direction_button.setObjectName("ChipButton")
        self._direction_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._direction_button.setFixedHeight(32)
        self._direction_button.setIconSize(QSize(15, 15))
        self._direction_button.clicked.connect(self.toggle_direction)
        footer_box.addWidget(self._direction_button)

        footer_box.addWidget(vertical_divider())

        self._rotate_ccw_button = IconButton(
            "rotate-ccw", "逆时针旋转 90°（Ctrl+←）", size=34, icon_size=17
        )
        self._rotate_ccw_button.clicked.connect(self.rotate_ccw)
        footer_box.addWidget(self._rotate_ccw_button)

        self._rotate_cw_button = IconButton(
            "rotate-cw", "顺时针旋转 90°（Ctrl+→）", size=34, icon_size=17
        )
        self._rotate_cw_button.clicked.connect(self.rotate_cw)
        footer_box.addWidget(self._rotate_cw_button)

        root.addWidget(self._footer)
        self._footer.hide()

        self._overlay = DropOverlay(central)
        self._toast = Toast(central)

        # Fullscreen edge page-turn keys.  They live above the reader and are
        # shown one at a time while the pointer is around that button.
        self._edge_left_button = EdgeTurnButton(
            "chevron-left", "上一页（←）", central
        )
        self._edge_left_button.clicked.connect(self._left_action)
        self._edge_left_button.hide()
        self._edge_right_button = EdgeTurnButton(
            "chevron-right", "下一页（→）", central
        )
        self._edge_right_button.clicked.connect(self._right_action)
        self._edge_right_button.hide()
        self._position_edge_buttons()

    def _build_shortcuts(self) -> None:
        bindings = [
            ("Ctrl+O", self.open_dialog),
            ("Ctrl+,", self.open_settings),
            ("F1", self.show_help),
            ("F", self.toggle_fullscreen),
            ("Esc", self._on_escape),
            ("Ctrl+W", self.close_book),
            ("H", self.toggle_fit),
        ]
        self._shortcuts: list[QShortcut] = []
        for sequence, handler in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    # ---- window state ----------------------------------------------------
    def _restore_geometry(self) -> None:
        data = self.settings.data.get("window", {})
        width = max(880, int(data.get("width") or 1240))
        height = max(620, int(data.get("height") or 820))
        x = data.get("x")
        y = data.get("y")
        rect = QRect(int(x), int(y), width, height) if x is not None and y is not None else None
        screen = QGuiApplication.primaryScreen()
        placed = False
        if rect is not None:
            for candidate in QGuiApplication.screens():
                if rect.intersects(candidate.availableGeometry()) and candidate.availableGeometry().contains(
                    rect.center()
                ):
                    self.setGeometry(rect)
                    placed = True
                    break
        if not placed:
            available = screen.availableGeometry() if screen is not None else QRect(0, 0, 1240, 820)
            w = min(width, available.width())
            h = min(height, available.height())
            self.setGeometry(
                available.x() + (available.width() - w) // 2,
                available.y() + (available.height() - h) // 2,
                w,
                h,
            )
        if bool(data.get("maximized")):
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _save_geometry(self) -> None:
        if self._fullscreen and self._windowed_geometry is not None:
            rect = self._windowed_geometry
            maximized = self._was_maximized
        elif self.isMaximized():
            rect = self.normalGeometry()
            maximized = True
        else:
            rect = self.geometry()
            maximized = False
        if rect.isValid() and rect.width() > 100 and rect.height() > 100:
            self.settings.update_window(
                rect.x(), rect.y(), rect.width(), rect.height(), maximized
            )

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange and not self._fullscreen:
            if self.isMaximized() and self._header.isVisible():
                self._sync_full_button()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._overlay.setGeometry(self._central.rect())
        self._toast.reposition()
        if hasattr(self, "_edge_left_button"):
            self._position_edge_buttons()
            self._update_edge_buttons()

    # ---- book lifecycle --------------------------------------------------
    def open_dialog(self) -> None:
        self._reset_cursor_activity()
        start_dir = str(self.settings.data.get("last_dir") or "")
        if not start_dir or not Path(start_dir).is_dir():
            start_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "打开漫画", start_dir, _FILE_FILTER
        )
        self._reset_cursor_activity()
        if path:
            self.open_path(path)

    def open_path(self, path_value: str) -> None:
        path = Path(path_value).expanduser()
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            self._error("无法打开漫画", "仅支持 EPUB、MOBI 与 PDF 格式的漫画。")
            return
        if not path.exists():
            self._error("无法打开漫画", f"找不到文件：\n{path}")
            return
        if not path.is_file():
            self._error("无法打开漫画", f"这不是一个文件：\n{path}")
            return

        error: Exception | None = None
        book: Book | None = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            book = load_book(path)
        except DrmProtectedError as exc:
            error = exc
        except BookError as exc:
            error = exc
        except Exception as exc:  # defensive: never lose the reader to one file
            log.exception("Unexpected failure opening %s", path)
            error = exc
        finally:
            QApplication.restoreOverrideCursor()

        if book is None:
            if error is None:
                return
            if isinstance(error, DrmProtectedError):
                self._error("无法打开漫画", str(error) or "这个文件受 DRM 保护。")
            elif isinstance(error, BookError):
                self._error("无法打开漫画", str(error))
            else:
                self._error(
                    "无法打开漫画",
                    f"读取时发生意外错误，文件可能已损坏。\n\n{error}",
                )
            return

        existing = self.settings.find_recent(str(path))
        start_page = 0
        if existing is not None:
            try:
                start_page = int(existing.get("page") or 0)
            except (TypeError, ValueError):
                start_page = 0
        start_page = max(0, min(start_page, book.page_count - 1))

        self._remember_position()
        if self._book is not None:
            self._book.close()
        self._book = book

        self.settings.touch_recent(
            str(path), book.title, book.author, book.fmt,
            start_page, book.page_count,
        )
        self.settings.data["last_dir"] = str(path.parent)
        self.settings.save()

        self._stack.setCurrentWidget(self._reader)
        self._reader.set_book(book, start_page)
        self._start_footer_watch()
        self._apply_reading_settings()
        self._update_header_for_book()
        self._sync_controls()
        self.setWindowTitle("Cactus Reader")
        self._reader.setFocus(Qt.FocusReason.OtherFocusReason)
        if book.used_fallback:
            self._toast.show_message("已使用兼容渲染模式显示此文件", 2400)
        if self._fullscreen:
            self._reset_cursor_activity()

    def close_book(self) -> None:
        if self._book is None:
            return
        self._remember_position()
        self.settings.save()
        self._book.close()
        self._book = None
        self._reader.set_book(None)
        self._stack.setCurrentWidget(self._welcome)
        self._stop_footer_watch()
        self._update_header_for_book()
        self._sync_controls()
        self._refresh_welcome()
        self.setWindowTitle("Cactus Reader")
        self._reader.clearFocus()
        self._welcome.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_recent(self, path: str) -> None:
        if not Path(path).exists():
            self._error("无法打开漫画", f"找不到文件：\n{path}")
            self.settings.remove_recent(path)
            self.settings.save()
            self._refresh_welcome()
            return
        self.open_path(path)

    def _remove_recent(self, path: str) -> None:
        self.settings.remove_recent(path)
        self.settings.save()
        self._refresh_welcome()

    def _clear_recent(self) -> None:
        if not self.settings.data["recent"]:
            return
        answer = QMessageBox.question(
            self,
            "清空最近阅读",
            "确定要清空最近阅读记录吗？\n漫画文件本身不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.settings.clear_recent()
            self.settings.save()
            self._refresh_welcome()

    def _refresh_welcome(self) -> None:
        self._welcome.refresh(list(self.settings.data.get("recent", [])))

    # ---- reading state ---------------------------------------------------
    def _apply_reading_settings(self) -> None:
        self._reader.set_config(
            two_page=self.settings.view_mode == "double",
            step=self.settings.effective_step,
            rtl=self.settings.direction == "rtl",
        )
        self._reader.set_page_gap(self.settings.page_gap)
        self._reader.set_fit_mode(self.settings.fit_mode)
        self._sync_controls()
        self._save_timer.start()

    def _on_position_changed(self, index: int) -> None:
        self._remember_position()
        self._sync_controls()
        self._save_timer.start()

    def _remember_position(self) -> None:
        if self._book is None:
            return
        self.settings.set_recent_page(str(self._book.path), self._reader.current_page)
        self.settings.set_recent_total(str(self._book.path), self._book.page_count)

    def _sync_controls(self) -> None:
        has_book = self._book is not None
        count = self._reader.page_count
        self._slider.set_rtl(self.settings.direction == "rtl")
        self._slider.blockSignals(True)
        self._slider.setRange(0, max(0, count - 1))
        self._slider.setValue(self._reader.current_page)
        self._slider.setEnabled(count > 1)
        self._slider.blockSignals(False)
        self._status.setText(self._reader.status_text())

        rtl = self.settings.direction == "rtl"
        left_enabled = self._reader.can_forward() if rtl else self._reader.can_back()
        right_enabled = self._reader.can_back() if rtl else self._reader.can_forward()
        self._left_button.setEnabled(has_book and left_enabled)
        self._right_button.setEnabled(has_book and right_enabled)

        if self.settings.fit_mode == "height":
            self._fit_button.setText("铺满高度")
            self._fit_button.setIcon(icon("fit-height", COLORS["text_muted"], 15))
            self._fit_button.setToolTip("页面高度铺满窗口，点击切换为铺满宽度（H）")
        else:
            self._fit_button.setText("铺满宽度")
            self._fit_button.setIcon(icon("fit-width", COLORS["text_muted"], 15))
            self._fit_button.setToolTip("页面宽度铺满窗口，点击切换为铺满高度（H）")

        if self.settings.view_mode == "double":
            self._view_button.setText("双页")
            self._view_button.setIcon(icon("view-double", COLORS["text_muted"], 15))
            self._view_button.setToolTip("当前双页浏览，点击切换为单页")
        else:
            self._view_button.setText("单页")
            self._view_button.setIcon(icon("view-single", COLORS["text_muted"], 15))
            self._view_button.setToolTip("当前单页浏览，点击切换为双页")

        if rtl:
            self._direction_button.setText("右←左")
            self._direction_button.setIcon(QIcon())
            self._direction_button.setToolTip("点击切换阅读方向")
        else:
            self._direction_button.setText("左→右")
            self._direction_button.setIcon(QIcon())
            self._direction_button.setToolTip("点击切换阅读方向")

        # The fullscreen edge buttons mirror the footer arrows.
        self._edge_left_button.setEnabled(has_book and left_enabled)
        self._edge_right_button.setEnabled(has_book and right_enabled)
        self._edge_left_button.setToolTip(
            "下一页（←）" if rtl else "上一页（←）"
        )
        self._edge_right_button.setToolTip(
            "上一页（→）" if rtl else "下一页（→）"
        )
        self._position_edge_buttons()
        self._update_edge_buttons()
        if self._fullscreen and has_book:
            if not self._edge_timer.isActive():
                self._reset_cursor_activity()
                self._edge_timer.start()
        elif self._edge_timer.isActive():
            self._edge_timer.stop()
            self._apply_cursor_hidden(False)

    # ---- auto-hiding footer ---------------------------------------------
    def _start_footer_watch(self) -> None:
        if self._book is None or self._fullscreen:
            self._stop_footer_watch()
            return
        self._set_footer_visible(False)
        if not self._footer_timer.isActive():
            self._footer_timer.start()

    def _stop_footer_watch(self) -> None:
        self._footer_timer.stop()
        self._set_footer_visible(False)

    def _footer_reveal_rect(self) -> QRect:
        """The footer-shaped strip that brings the hidden bar back."""
        central = self._central
        height = min(
            max(1, self._footer.height()), max(1, central.height())
        )
        top_left = central.mapToGlobal(QPoint(0, central.height() - height))
        return QRect(top_left, QSize(central.width(), height))

    def _update_footer_visibility(
        self, global_pos: QPoint | None = None
    ) -> None:
        if (
            self._book is None
            or self._fullscreen
            or not self.isVisible()
            or self.isMinimized()
        ):
            self._set_footer_visible(False)
            return
        if global_pos is None:
            global_pos = QCursor.pos()
        if self._footer.isVisible():
            # Do not yank the slider away while it is being dragged.
            if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
                return
            if self._footer.rect().contains(
                self._footer.mapFromGlobal(global_pos)
            ):
                return
            self._set_footer_visible(False)
            return
        if self._footer_reveal_rect().contains(global_pos):
            self._set_footer_visible(True)

    def _set_footer_visible(self, visible: bool) -> None:
        if visible == self._footer.isVisible():
            return
        self._footer.setVisible(visible)
        # The footer takes height from the reader.  Repaint immediately so a
        # height-fit page grows or shrinks with the available viewport.
        self._reader.update()

    # ---- fullscreen edge page-turn keys ---------------------------------
    def _position_edge_buttons(self) -> None:
        if not hasattr(self, "_edge_left_button"):
            return
        area = self._central.rect()
        tenth = max(1.0, area.width() / 10.0)
        margin = 16
        # Keep the whole button inside its trigger tenth on narrow screens.
        if tenth < margin + self._edge_left_button.width() + 4:
            margin = max(4, int(tenth - self._edge_left_button.width() - 4))
        y = max(
            area.y(),
            area.y() + (area.height() - self._edge_left_button.height()) // 2,
        )
        self._edge_left_button.move(area.x() + margin, y)
        self._edge_right_button.move(
            area.x() + area.width() - margin - self._edge_right_button.width(), y
        )

    def _update_edge_buttons(self, local_pos: QPoint | None = None) -> None:
        """Reveal a button only while the pointer is around that button.

        ``local_pos`` uses the central widget's coordinates; when omitted the
        live cursor position is used, which is what the polling timer needs.
        """
        if not self._fullscreen or self._book is None:
            self._hide_edge_buttons()
            return
        if self._overlay.isVisible() or QApplication.activeModalWidget() is not None:
            self._hide_edge_buttons()
            return
        if local_pos is None:
            local_pos = self._central.mapFromGlobal(QCursor.pos())
        if not self._central.rect().contains(local_pos):
            self._hide_edge_buttons()
            return
        self._set_edge_button_visible(
            self._edge_left_button,
            self._edge_hover_zone(self._edge_left_button).contains(local_pos),
        )
        self._set_edge_button_visible(
            self._edge_right_button,
            self._edge_hover_zone(self._edge_right_button).contains(local_pos),
        )

    def _edge_hover_zone(self, button) -> QRect:
        pad = self._EDGE_HOVER_PAD
        return button.geometry().adjusted(-pad, -pad, pad, pad)

    @staticmethod
    def _set_edge_button_visible(button, visible: bool) -> None:
        if visible:
            if not button.isVisible():
                button.show()
                button.raise_()
        elif button.isVisible():
            button.hide()

    def _hide_edge_buttons(self) -> None:
        self._edge_left_button.hide()
        self._edge_right_button.hide()

    # ---- fullscreen cursor auto-hide ------------------------------------
    def _reset_cursor_activity(self) -> None:
        """Show the pointer and restart the fullscreen idle countdown."""
        self._note_cursor_activity(QCursor.pos())

    def _note_cursor_activity(self, global_pos: QPoint) -> None:
        self._cursor_last_pos = QPoint(global_pos)
        self._cursor_idle_since = monotonic()
        self._apply_cursor_hidden(False)

    def _poll_cursor_hide(self, global_pos: QPoint | None = None) -> None:
        """Hide the pointer once it has rested over a fullscreen book.

        ``global_pos`` is injectable for deterministic tests; the polling
        timer calls this without arguments.
        """
        if not self._fullscreen or self._book is None:
            self._apply_cursor_hidden(False)
            return
        if (
            QApplication.activeModalWidget() is not None
            or QApplication.activePopupWidget() is not None
        ):
            # Menus and dialogs need a visible pointer.
            self._apply_cursor_hidden(False)
            return
        if global_pos is None:
            global_pos = QCursor.pos()
        if global_pos != self._cursor_last_pos:
            self._note_cursor_activity(global_pos)
            return
        if self._cursor_hidden:
            return
        if not self._central.rect().contains(
            self._central.mapFromGlobal(global_pos)
        ):
            # The pointer is over another screen or outside the reading
            # area; its normal cursor should stay visible there.
            self._cursor_idle_since = monotonic()
            return
        if monotonic() - self._cursor_idle_since >= self.settings.hide_cursor_delay:
            self._apply_cursor_hidden(True)

    def _apply_cursor_hidden(self, hidden: bool) -> None:
        hidden = bool(hidden)
        if hidden == self._cursor_hidden:
            return
        self._cursor_hidden = hidden
        self._reader.set_cursor_hidden(hidden)
        shape = (
            Qt.CursorShape.BlankCursor
            if hidden
            else Qt.CursorShape.PointingHandCursor
        )
        self._edge_left_button.setCursor(shape)
        self._edge_right_button.setCursor(shape)

    def _update_header_for_book(self) -> None:
        if self._book is None:
            self._header_title.setText("Cactus Reader")
            self._header_meta.setText("EPUB / MOBI / PDF 漫画阅读器")
            return
        self._header_title.setText(self._book.title)
        parts = []
        if self._book.author:
            parts.append(self._book.author)
        parts.append(self._book.fmt)
        parts.append(f"{self._book.page_count} 页")
        self._header_meta.setText("  ·  ".join(parts))

    def _on_slider(self, value: int) -> None:
        if self._book is not None:
            self._reader.go_to(value)

    def _on_boundary(self, where: str) -> None:
        self._toast.show_message(
            "已经是最后一页" if where == "end" else "已经是第一页", 1200
        )

    def _on_zoom_changed(self, factor: float) -> None:
        if abs(factor - 1.0) < 1e-6:
            mode = "铺满高度" if self.settings.fit_mode == "height" else "铺满宽度"
            self._toast.show_message(f"已恢复{mode}（100%）", 1400)
        else:
            self._toast.show_message(
                f"缩放 {int(round(factor * 100))}%  ·  Ctrl+中键恢复", 1400
            )

    # ---- navigation actions ---------------------------------------------
    def _left_action(self) -> None:
        self._turn_side(left=True)

    def _right_action(self) -> None:
        self._turn_side(left=False)

    def _turn_side(self, *, left: bool, step: int | None = None) -> None:
        if self._book is None:
            return
        forward = self.settings.direction == "rtl"
        if not left:
            forward = not forward
        if forward:
            self._reader.forward(step)
        else:
            self._reader.back(step)

    def _alternate_step(self) -> int:
        """The other double-page step, so Shift+arrow flips 1 <-> 2."""
        return 3 - self.settings.double_step

    def _forward_page(self) -> None:
        if self._book is not None:
            self._reader.forward()

    def _back_page(self) -> None:
        if self._book is not None:
            self._reader.back()

    def _go_first(self) -> None:
        if self._book is not None:
            self._reader.first()

    def _go_last(self) -> None:
        if self._book is not None:
            self._reader.last()

    # ---- rotation --------------------------------------------------------
    def rotate_cw(self) -> None:
        self._rotate(clockwise=True)

    def rotate_ccw(self) -> None:
        self._rotate(clockwise=False)

    def _rotate(self, *, clockwise: bool) -> None:
        if self._book is None:
            return
        rotated = (
            self._reader.rotate_cw() if clockwise else self._reader.rotate_ccw()
        )
        if rotated and self.settings.rotate_switches_fit:
            # A page that was too tall/large for the viewport when upright can
            # become wider than the viewport once turned.  Switching the fit
            # side keeps the rotated page filling the reading area.
            self.toggle_fit()

    # ---- view toggles ----------------------------------------------------
    def toggle_view_mode(self) -> None:
        self.settings.view_mode = (
            "single" if self.settings.view_mode == "double" else "double"
        )
        self._apply_reading_settings()

    def toggle_direction(self) -> None:
        self.settings.direction = (
            "rtl" if self.settings.direction == "ltr" else "ltr"
        )
        self._apply_reading_settings()

    def toggle_fit(self) -> None:
        self.settings.fit_mode = (
            "width" if self.settings.fit_mode == "height" else "height"
        )
        self._apply_reading_settings()

    # ---- dialogs ---------------------------------------------------------
    def open_settings(self) -> None:
        self._reset_cursor_activity()
        dialog = SettingsDialog(self.settings, self)
        dialog.settingsChanged.connect(self._apply_reading_settings)
        dialog.exec()
        self._reset_cursor_activity()
        self.settings.save()
        self._sync_controls()
        self._refresh_welcome()
        if self._book is not None:
            self._reader.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_help(self) -> None:
        self._reset_cursor_activity()
        dialog = HelpDialog(self)
        dialog.exec()
        self._reset_cursor_activity()
        if self._book is not None:
            self._reader.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---- fullscreen ------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        self._set_fullscreen(not self._fullscreen)

    def _set_fullscreen(self, enabled: bool) -> None:
        if enabled == self._fullscreen:
            return
        if enabled:
            self._was_maximized = self.isMaximized()
            self._windowed_geometry = (
                self.normalGeometry() if self.isMaximized() else self.geometry()
            )
            self._fullscreen = True
            self.showFullScreen()
            self._header.hide()
            self._footer_timer.stop()
            self._set_footer_visible(False)
            self._sync_full_button()
            self._position_edge_buttons()
            self._reset_cursor_activity()
            if self._book is not None and not self._edge_timer.isActive():
                self._edge_timer.start()
            self._update_edge_buttons()
            self._toast.show_message("按 F 或 Esc 退出全屏", 2000)
        else:
            self._fullscreen = False
            self._edge_timer.stop()
            self._hide_edge_buttons()
            self._apply_cursor_hidden(False)
            if self._was_maximized:
                self.showMaximized()
            else:
                if self._windowed_geometry is not None:
                    self.setGeometry(self._windowed_geometry)
                self.showNormal()
            self._header.show()
            self._start_footer_watch()
            self._sync_full_button()
            self._overlay.setGeometry(self._central.rect())
            if self._book is not None:
                self._reader.setFocus(Qt.FocusReason.OtherFocusReason)

    def _sync_full_button(self) -> None:
        self._full_button.set_icon(
            "fullscreen-exit" if self._fullscreen else "fullscreen"
        )
        self._full_button.setToolTip(
            "退出全屏（F）" if self._fullscreen else "全屏（F）"
        )

    def _on_escape(self) -> None:
        if self._fullscreen:
            self._set_fullscreen(False)

    # ---- keyboard --------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.Wheel
            and watched in (self._edge_left_button, self._edge_right_button)
            and self._book is not None
        ):
            # Scrolling while hovering an edge button still turns pages.
            QApplication.sendEvent(self._reader, event)
            return True
        if (
            event.type() == QEvent.Type.KeyPress
            and self._book is not None
            and self.isActiveWindow()
            and QApplication.activeModalWidget() is None
            and QApplication.activePopupWidget() is None
            and not (event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            key = event.key()
            modifiers = event.modifiers()
            # Rotation is physical, so the shortcuts do not follow the
            # reading direction.  They work windowed and fullscreen alike.
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_Left:
                    self.rotate_ccw()
                    return True
                if key == Qt.Key.Key_Right:
                    self.rotate_cw()
                    return True
            if not (modifiers & Qt.KeyboardModifier.ControlModifier):
                if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    # Shift+arrow turns by the other double-page step, so
                    # either step size is always one keystroke away.
                    step = None
                    if (
                        modifiers & Qt.KeyboardModifier.ShiftModifier
                        and self.settings.view_mode == "double"
                    ):
                        step = self._alternate_step()
                    self._turn_side(left=key == Qt.Key.Key_Left, step=step)
                    return True
                if key == Qt.Key.Key_PageDown:
                    self._forward_page()
                    return True
                if key == Qt.Key.Key_PageUp or key == Qt.Key.Key_Backspace:
                    self._back_page()
                    return True
                if key == Qt.Key.Key_Space:
                    focus = QApplication.focusWidget()
                    if not isinstance(focus, QAbstractButton):
                        self._forward_page()
                        return True
                if key == Qt.Key.Key_Home:
                    self._go_first()
                    return True
                if key == Qt.Key.Key_End:
                    self._go_last()
                    return True
        return super().eventFilter(watched, event)

    # ---- drag and drop ---------------------------------------------------
    def _supported_drop(self, mime) -> str | None:
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_SUFFIXES and path.is_file():
                return str(path)
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._supported_drop(event.mimeData()) is not None:
            event.acceptProposedAction()
            self._overlay.show_over()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._supported_drop(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._overlay.hide()
        path = self._supported_drop(event.mimeData())
        if path is not None:
            event.acceptProposedAction()
            self.open_path(path)
        else:
            event.ignore()

    # ---- persistence and shutdown ---------------------------------------
    def _save_settings(self) -> None:
        self._remember_position()
        self.settings.save()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_timer.stop()
        self._edge_timer.stop()
        self._apply_cursor_hidden(False)
        self._remember_position()
        self._save_geometry()
        self.settings.save()
        if self._book is not None:
            self._book.close()
            self._book = None
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().closeEvent(event)

    def _error(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setWindowIcon(self.windowIcon())
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
