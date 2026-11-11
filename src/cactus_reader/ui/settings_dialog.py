"""The reading-settings dialog. Changes apply immediately."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QGuiApplication, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..settings import (
    DEFAULT_HIDE_CURSOR_DELAY,
    DEFAULT_PAGE_GAP,
    DEFAULTS,
    HIDE_CURSOR_MAX,
    HIDE_CURSOR_MIN,
    HIDE_CURSOR_PRESETS,
    PAGE_GAP_MAX,
    PAGE_GAP_MIN,
    PAGE_GAP_PRESETS,
    Settings,
    clamp_hide_cursor_delay,
    clamp_page_gap,
)
from .theme import enable_dark_titlebar, icon
from .widgets import SegmentedControl

_CUSTOM_GAP = "custom"
_CUSTOM_DELAY = "custom"


class GapPicker(QWidget):
    """Preset gap buttons plus a numeric custom input with hard limits."""

    changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = DEFAULT_PAGE_GAP

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        options = [
            (str(gap), str(gap), f"两页之间留 {gap} 像素")
            for gap in PAGE_GAP_PRESETS
        ]
        options.append((_CUSTOM_GAP, "自定义", "输入任意像素值"))
        self._segments = SegmentedControl(options)
        self._segments.changed.connect(self._on_segment)
        custom_button = self._segments.button(_CUSTOM_GAP)
        if custom_button is not None:
            custom_button.clicked.connect(self._focus_custom)
        layout.addWidget(self._segments)

        self._input = QLineEdit()
        self._input.setObjectName("GapInput")
        self._input.setFixedWidth(58)
        self._input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._input.setMaxLength(9)
        self._input.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"-?[0-9]{0,9}"), self._input)
        )
        self._input.setToolTip(
            f"输入 {PAGE_GAP_MIN}–{PAGE_GAP_MAX} 像素，按回车确认"
        )
        self._input.setAccessibleName("自定义双页间距")
        self._input.returnPressed.connect(self.commit)
        self._input.editingFinished.connect(self.commit)
        self._input.textEdited.connect(self._on_text_edited)
        layout.addWidget(self._input)

        unit = QLabel("px")
        unit.setObjectName("HintLabel")
        layout.addWidget(unit)
        self.set_value(DEFAULT_PAGE_GAP)

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._value = clamp_page_gap(value)
        self._sync_display()

    def commit(self) -> None:
        text = self._input.text().strip()
        if not text:
            self._sync_display()
            return
        try:
            raw = int(text)
        except ValueError:
            self._sync_display()
            return
        clamped = clamp_page_gap(raw)
        previous = self._value
        self._value = clamped
        self._sync_display()
        if clamped != previous:
            self.changed.emit(clamped)

    def _sync_display(self) -> None:
        if self._value in PAGE_GAP_PRESETS:
            self._segments.set_value(str(self._value))
        else:
            self._segments.set_value(_CUSTOM_GAP)
        text = str(self._value)
        if self._input.text() != text:
            self._input.setText(text)

    def _on_segment(self, value: str) -> None:
        if value == _CUSTOM_GAP:
            self._focus_custom()
            return
        self._value = clamp_page_gap(int(value))
        self._sync_display()
        self.changed.emit(self._value)

    def _focus_custom(self) -> None:
        self._input.setFocus(Qt.FocusReason.MouseFocusReason)
        self._input.selectAll()

    def _on_text_edited(self, text: str) -> None:
        if text.isdigit():
            number = int(text)
            if number in PAGE_GAP_PRESETS and str(number) == text:
                self._segments.set_value(text)
                return
        self._segments.set_value(_CUSTOM_GAP)


class IdleDelayPicker(QWidget):
    """Preset cursor-hide delays plus a numeric custom input with hard limits."""

    changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = DEFAULT_HIDE_CURSOR_DELAY

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        options = [
            (str(delay), f"{delay} 秒", f"鼠标静止 {delay} 秒后隐藏")
            for delay in HIDE_CURSOR_PRESETS
        ]
        options.append((_CUSTOM_DELAY, "自定义", "输入任意等待秒数"))
        self._segments = SegmentedControl(options)
        self._segments.changed.connect(self._on_segment)
        custom_button = self._segments.button(_CUSTOM_DELAY)
        if custom_button is not None:
            custom_button.clicked.connect(self._focus_custom)
        layout.addWidget(self._segments)

        self._input = QLineEdit()
        self._input.setObjectName("DelayInput")
        self._input.setFixedWidth(52)
        self._input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._input.setMaxLength(2)
        self._input.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r"[0-9]{0,2}"), self._input
            )
        )
        self._input.setToolTip(
            f"输入 {HIDE_CURSOR_MIN}–{HIDE_CURSOR_MAX} 秒，按回车确认"
        )
        self._input.setAccessibleName("自定义全屏时隐藏鼠标等待时间")
        self._input.returnPressed.connect(self.commit)
        self._input.editingFinished.connect(self.commit)
        self._input.textEdited.connect(self._on_text_edited)
        layout.addWidget(self._input)

        unit = QLabel("秒")
        unit.setObjectName("HintLabel")
        layout.addWidget(unit)
        self.set_value(DEFAULT_HIDE_CURSOR_DELAY)

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._value = clamp_hide_cursor_delay(value)
        self._sync_display()

    def commit(self) -> None:
        text = self._input.text().strip()
        if not text:
            self._sync_display()
            return
        try:
            raw = int(text)
        except ValueError:
            self._sync_display()
            return
        clamped = clamp_hide_cursor_delay(raw)
        previous = self._value
        self._value = clamped
        self._sync_display()
        if clamped != previous:
            self.changed.emit(clamped)

    def _sync_display(self) -> None:
        if self._value in HIDE_CURSOR_PRESETS:
            self._segments.set_value(str(self._value))
        else:
            self._segments.set_value(_CUSTOM_DELAY)
        text = str(self._value)
        if self._input.text() != text:
            self._input.setText(text)

    def _on_segment(self, value: str) -> None:
        if value == _CUSTOM_DELAY:
            self._focus_custom()
            return
        self._value = clamp_hide_cursor_delay(int(value))
        self._sync_display()
        self.changed.emit(self._value)

    def _focus_custom(self) -> None:
        self._input.setFocus(Qt.FocusReason.MouseFocusReason)
        self._input.selectAll()

    def _on_text_edited(self, text: str) -> None:
        if text.isdigit():
            number = int(text)
            if number in HIDE_CURSOR_PRESETS and str(number) == text:
                self._segments.set_value(text)
                return
        self._segments.set_value(_CUSTOM_DELAY)


class SettingsDialog(QDialog):
    settingsChanged = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("阅读设置")
        self.setWindowIcon(icon("settings"))
        self.setModal(True)
        self.setFixedWidth(640)
        screen = None
        if parent is not None and parent.window() is not None:
            screen = parent.window().screen()
        screen = screen or QGuiApplication.primaryScreen()
        if screen is not None:
            # Keep the buttons reachable on smaller laptop screens; the card
            # list scrolls instead of growing past the display.
            self.setMaximumHeight(max(520, screen.availableGeometry().height() - 80))
        enable_dark_titlebar(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)

        content = QWidget()
        content.setObjectName("SettingsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        # ---- layout and step --------------------------------------------
        layout_card = _card()
        layout_box = QVBoxLayout(layout_card)
        layout_box.setContentsMargins(20, 17, 20, 17)
        layout_box.setSpacing(13)

        self._view_seg = _row(
            layout_box,
            "页面布局",
            [("single", "单页", "每次显示一页漫画"),
             ("double", "双页", "并排显示两页漫画")],
        )
        layout_box.addWidget(_divider())

        self._step_seg = _row(
            layout_box,
            "双页显示翻页步长",
            [("1", "翻 1 页", "每次翻一页"),
             ("2", "翻 2 页", "每次翻两页，跳过下一个双页组合")],
        )

        layout_box.addWidget(_divider())
        gap_header = QHBoxLayout()
        gap_header.setSpacing(12)
        gap_name = QLabel("双页间距")
        gap_name.setObjectName("CardTitle")
        gap_header.addWidget(gap_name)
        gap_header.addStretch(1)
        self._gap_picker = GapPicker()
        gap_header.addWidget(self._gap_picker)
        layout_box.addLayout(gap_header)
        root.addWidget(layout_card)

        # ---- direction ---------------------------------------------------
        direction_card = _card()
        direction_box = QVBoxLayout(direction_card)
        direction_box.setContentsMargins(20, 17, 20, 17)
        direction_box.setSpacing(13)
        self._direction_seg = _row(
            direction_box,
            "阅读方向",
            [("ltr", "从左向右", "右方向键翻到后一页"),
             ("rtl", "从右向左", "左方向键翻到后一页")],
        )
        root.addWidget(direction_card)

        # ---- fit ---------------------------------------------------------
        fit_card = _card()
        fit_box = QVBoxLayout(fit_card)
        fit_box.setContentsMargins(20, 17, 20, 17)
        fit_box.setSpacing(13)
        self._fit_seg = _row(
            fit_box,
            "页面适配",
            [("height", "铺满高度", "按高度铺满窗口"),
             ("width", "铺满宽度", "按宽度铺满窗口")],
        )

        fit_box.addWidget(_divider())
        self._rotate_fit_seg = _row(
            fit_box,
            "旋转时切换铺满高度/宽度",
            [("on", "开启", "每次旋转后切换铺满高度与铺满宽度"),
             ("off", "关闭", "旋转时保持当前铺满方式")],
        )
        root.addWidget(fit_card)

        # ---- fullscreen cursor -------------------------------------------
        cursor_card = _card()
        cursor_box = QVBoxLayout(cursor_card)
        cursor_box.setContentsMargins(20, 16, 20, 16)
        cursor_box.setSpacing(9)
        cursor_title = QLabel("全屏时隐藏鼠标")
        cursor_title.setObjectName("CardTitle")
        cursor_box.addWidget(cursor_title)
        self._hide_cursor_picker = IdleDelayPicker()
        cursor_box.addWidget(
            self._hide_cursor_picker, 0, Qt.AlignmentFlag.AlignLeft
        )
        root.addWidget(cursor_card)

        shortcuts = QLabel(
            "方向键翻页  ·  Shift+←/→ 换步长  ·  滚轮翻页  ·  Ctrl+滚轮缩放"
            "  ·  Ctrl+鼠标中键恢复缩放  ·  Ctrl+←/→ 旋转"
        )
        shortcuts.setObjectName("HintLabel")
        shortcuts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts.setWordWrap(True)
        root.addSpacing(2)
        root.addWidget(shortcuts)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("SettingsFooter")
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(28, 8, 28, 18)
        bottom.setSpacing(10)
        reset = QPushButton("恢复默认")
        reset.setIcon(icon("reset", "#99A79A", 16))
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(self._reset)
        bottom.addWidget(reset)
        bottom.addStretch(1)
        done = QPushButton("完成")
        done.setObjectName("PrimaryButton")
        done.setCursor(Qt.CursorShape.PointingHandCursor)
        done.setDefault(True)
        done.clicked.connect(self.accept)
        bottom.addWidget(done)
        outer.addWidget(footer)

        self._view_seg.changed.connect(self._on_view_changed)
        self._step_seg.changed.connect(self._on_step_changed)
        self._direction_seg.changed.connect(self._on_direction_changed)
        self._fit_seg.changed.connect(self._on_fit_changed)
        self._gap_picker.changed.connect(self._on_gap_changed)
        self._hide_cursor_picker.changed.connect(self._on_hide_cursor_changed)
        self._rotate_fit_seg.changed.connect(self._on_rotate_fit_changed)
        self._sync_from_settings()

        # A scroll area reports a tiny hint of its own; size the dialog to the
        # cards plus the fixed footer, capped by the screen space computed above.
        target_height = content.sizeHint().height() + footer.sizeHint().height() + 2
        self.resize(self.width(), max(420, min(self.maximumHeight(), target_height)))

    # ---- initialisation --------------------------------------------------
    def _sync_from_settings(self) -> None:
        s = self._settings
        self._view_seg.set_value(s.view_mode)
        self._step_seg.set_value(str(s.double_step))
        self._direction_seg.set_value(s.direction)
        self._fit_seg.set_value(s.fit_mode)
        self._rotate_fit_seg.set_value("on" if s.rotate_switches_fit else "off")
        self._gap_picker.set_value(s.page_gap)
        self._hide_cursor_picker.set_value(s.hide_cursor_delay)
        self._step_seg.setEnabled(s.view_mode == "double")

    # ---- changes ---------------------------------------------------------
    def _on_view_changed(self, value: str) -> None:
        self._settings.view_mode = value
        self._step_seg.setEnabled(value == "double")
        self.settingsChanged.emit()

    def _on_step_changed(self, value: str) -> None:
        self._settings.double_step = int(value)
        self.settingsChanged.emit()

    def _on_direction_changed(self, value: str) -> None:
        self._settings.direction = value
        self.settingsChanged.emit()

    def _on_fit_changed(self, value: str) -> None:
        self._settings.fit_mode = value
        self.settingsChanged.emit()

    def _on_gap_changed(self, value: int) -> None:
        self._settings.page_gap = value
        self.settingsChanged.emit()

    def _on_hide_cursor_changed(self, value: int) -> None:
        self._settings.hide_cursor_delay = value
        self.settingsChanged.emit()

    def _on_rotate_fit_changed(self, value: str) -> None:
        self._settings.rotate_switches_fit = value == "on"
        self.settingsChanged.emit()

    def _reset(self) -> None:
        self._settings.view_mode = DEFAULTS["view_mode"]
        self._settings.double_step = DEFAULTS["double_step"]
        self._settings.direction = DEFAULTS["direction"]
        self._settings.fit_mode = DEFAULTS["fit_mode"]
        self._settings.rotate_switches_fit = DEFAULTS["rotate_switches_fit"]
        self._settings.page_gap = DEFAULTS["page_gap"]
        self._settings.hide_cursor_delay = DEFAULTS["hide_cursor_delay"]
        self._view_seg.set_value(self._settings.view_mode)
        self._step_seg.set_value(str(self._settings.double_step))
        self._direction_seg.set_value(self._settings.direction)
        self._fit_seg.set_value(self._settings.fit_mode)
        self._rotate_fit_seg.set_value(
            "on" if self._settings.rotate_switches_fit else "off"
        )
        self._gap_picker.set_value(self._settings.page_gap)
        self._hide_cursor_picker.set_value(self._settings.hide_cursor_delay)
        self._step_seg.setEnabled(self._settings.view_mode == "double")
        self.settingsChanged.emit()

    def accept(self) -> None:
        self._gap_picker.commit()
        self._hide_cursor_picker.commit()
        super().accept()


def _card() -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    return card


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def _row(parent_layout: QVBoxLayout, title: str,
         options: list[tuple[str, str, str]]) -> SegmentedControl:
    header = QHBoxLayout()
    header.setSpacing(16)
    name = QLabel(title)
    name.setObjectName("CardTitle")
    header.addWidget(name, 1)
    segment = SegmentedControl(options)
    header.addWidget(segment, 0, Qt.AlignmentFlag.AlignVCenter)
    parent_layout.addLayout(header)
    return segment
