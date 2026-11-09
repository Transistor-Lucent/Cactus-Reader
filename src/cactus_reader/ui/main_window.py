"""Main window: chrome, file loading, shortcuts, persistence and fullscreen."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon, QKeySequence, QShortcut
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
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..book import Book, BookError, DrmProtectedError, load_book
from ..paths import APP_NAME
from ..settings import Settings
from .help_dialog import HelpDialog
from .reader_view import ReaderView
from .settings_dialog import SettingsDialog
from .theme import COLORS, app_icon, icon
from .widgets import (
    DropOverlay,
    ElidedLabel,
    IconButton,
    Toast,
    logo_pixmap,
    vertical_divider,
)
from .welcome import WelcomePage

log = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".epub", ".mobi", ".prc", ".azw", ".azw3"}
_FILE_FILTER = (
    "漫画文件 (*.epub *.mobi *.prc *.azw *.azw3);;所有文件 (*.*)"
)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._book: Book | None = None
        self._fullscreen = False
        self._was_maximized = False
        self._windowed_geometry: QRect | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(880, 620)
        self.setAcceptDrops(True)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1200)
        self._save_timer.timeout.connect(self._save_settings)

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
        self._header.setFixedHeight(68)
        header_box = QHBoxLayout(self._header)
        header_box.setContentsMargins(20, 10, 18, 10)
        header_box.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(34))
        logo.setFixedSize(34, 34)
        header_box.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self._header_title = ElidedLabel("Cactus Reader")
        self._header_title.setObjectName("HeaderTitle")
        self._header_meta = ElidedLabel("EPUB / MOBI 漫画阅读器")
        self._header_meta.setObjectName("HeaderMeta")
        title_box.addWidget(self._header_title)
        title_box.addWidget(self._header_meta)
        header_box.addLayout(title_box, 1)

        self._open_button = QPushButton("打开漫画")
        self._open_button.setIcon(icon("open", COLORS["text"], 17))
        self._open_button.setIconSize(QSize(17, 17))
        self._open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_button.setFixedHeight(36)
        self._open_button.setToolTip("打开 EPUB / MOBI 漫画（Ctrl+O）")
        self._open_button.clicked.connect(self.open_dialog)
        header_box.addWidget(self._open_button)

        self._settings_button = IconButton("settings", "阅读设置（Ctrl+,）")
        self._settings_button.clicked.connect(self.open_settings)
        header_box.addWidget(self._settings_button)

        self._help_button = IconButton("help", "使用帮助（F1）")
        self._help_button.clicked.connect(self.show_help)
        header_box.addWidget(self._help_button)

        self._full_button = IconButton("fullscreen", "全屏（F11）")
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

        # Footer ---------------------------------------------------------
        self._footer = QFrame()
        self._footer.setObjectName("Footer")
        self._footer.setFixedHeight(62)
        footer_box = QHBoxLayout(self._footer)
        footer_box.setContentsMargins(16, 9, 16, 9)
        footer_box.setSpacing(8)

        self._left_button = IconButton("chevron-left", size=40, icon_size=17)
        self._left_button.clicked.connect(self._left_action)
        footer_box.addWidget(self._left_button)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(2)
        self._slider.setTracking(False)
        self._slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._slider.valueChanged.connect(self._on_slider)
        footer_box.addWidget(self._slider, 1)

        self._right_button = IconButton("chevron-right", size=40, icon_size=17)
        self._right_button.clicked.connect(self._right_action)
        footer_box.addWidget(self._right_button)

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

        root.addWidget(self._footer)
        self._footer.hide()

        self._overlay = DropOverlay(central)
        self._toast = Toast(central)

    def _build_shortcuts(self) -> None:
        bindings = [
            ("Ctrl+O", self.open_dialog),
            ("Ctrl+,", self.open_settings),
            ("F1", self.show_help),
            ("F11", self.toggle_fullscreen),
            ("Esc", self._on_escape),
            ("Ctrl+W", self.close_book),
            ("F", self.toggle_fit),
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

    # ---- book lifecycle --------------------------------------------------
    def open_dialog(self) -> None:
        start_dir = str(self.settings.data.get("last_dir") or "")
        if not start_dir or not Path(start_dir).is_dir():
            start_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "打开漫画", start_dir, _FILE_FILTER
        )
        if path:
            self.open_path(path)

    def open_path(self, path_value: str) -> None:
        path = Path(path_value).expanduser()
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            self._error("无法打开漫画", "仅支持 EPUB 与 MOBI 格式的漫画。")
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
        self._footer.setVisible(not self._fullscreen)
        self._reader.set_book(book, start_page)
        self._apply_reading_settings()
        self._update_header_for_book()
        self._sync_controls()
        self.setWindowTitle(f"{book.title} — Cactus Reader")
        self._reader.setFocus(Qt.FocusReason.OtherFocusReason)
        if book.used_fallback:
            self._toast.show_message("已使用兼容渲染模式显示此文件", 2400)

    def close_book(self) -> None:
        if self._book is None:
            return
        self._remember_position()
        self.settings.save()
        self._book.close()
        self._book = None
        self._reader.set_book(None)
        self._stack.setCurrentWidget(self._welcome)
        self._footer.hide()
        self._update_header_for_book()
        self._sync_controls()
        self._refresh_welcome()
        self.setWindowTitle(APP_NAME)
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
        self._left_button.setToolTip(
            "下一页（←）" if rtl else "上一页（←）"
        )
        self._right_button.setToolTip(
            "上一页（→）" if rtl else "下一页（→）"
        )

        if self.settings.fit_mode == "height":
            self._fit_button.setText("铺满高度")
            self._fit_button.setIcon(icon("fit-height", COLORS["text_muted"], 15))
            self._fit_button.setToolTip("页面高度铺满窗口，点击切换为铺满宽度（F）")
        else:
            self._fit_button.setText("铺满宽度")
            self._fit_button.setIcon(icon("fit-width", COLORS["text_muted"], 15))
            self._fit_button.setToolTip("页面宽度铺满窗口，点击切换为铺满高度（F）")

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
            self._direction_button.setToolTip("从右向左阅读：左键翻到后一页，点击切换为从左向右")
        else:
            self._direction_button.setText("左→右")
            self._direction_button.setIcon(QIcon())
            self._direction_button.setToolTip("从左向右阅读：右键翻到后一页，点击切换为从右向左")

    def _update_header_for_book(self) -> None:
        if self._book is None:
            self._header_title.setText("Cactus Reader")
            self._header_meta.setText("EPUB / MOBI 漫画阅读器")
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

    # ---- navigation actions ---------------------------------------------
    def _left_action(self) -> None:
        if self._book is None:
            return
        if self.settings.direction == "rtl":
            self._reader.forward()
        else:
            self._reader.back()

    def _right_action(self) -> None:
        if self._book is None:
            return
        if self.settings.direction == "rtl":
            self._reader.back()
        else:
            self._reader.forward()

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
        dialog = SettingsDialog(self.settings, self)
        dialog.settingsChanged.connect(self._apply_reading_settings)
        dialog.exec()
        self.settings.save()
        self._sync_controls()
        self._refresh_welcome()
        if self._book is not None:
            self._reader.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()
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
            self._footer.hide()
            self._sync_full_button()
            self._toast.show_message("按 F11 或 Esc 退出全屏", 2000)
        else:
            self._fullscreen = False
            if self._was_maximized:
                self.showMaximized()
            else:
                if self._windowed_geometry is not None:
                    self.setGeometry(self._windowed_geometry)
                self.showNormal()
            self._header.show()
            self._footer.setVisible(self._book is not None)
            self._sync_full_button()
            self._overlay.setGeometry(self._central.rect())
            if self._book is not None:
                self._reader.setFocus(Qt.FocusReason.OtherFocusReason)

    def _sync_full_button(self) -> None:
        self._full_button.set_icon(
            "fullscreen-exit" if self._fullscreen else "fullscreen"
        )
        self._full_button.setToolTip(
            "退出全屏（F11）" if self._fullscreen else "全屏（F11）"
        )

    def _on_escape(self) -> None:
        if self._fullscreen:
            self._set_fullscreen(False)

    # ---- keyboard --------------------------------------------------------
    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.KeyPress
            and self._book is not None
            and self.isActiveWindow()
            and QApplication.activeModalWidget() is None
            and QApplication.activePopupWidget() is None
            and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                          | Qt.KeyboardModifier.AltModifier))
        ):
            key = event.key()
            if key == Qt.Key.Key_Left:
                self._left_action()
                return True
            if key == Qt.Key.Key_Right:
                self._right_action()
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
