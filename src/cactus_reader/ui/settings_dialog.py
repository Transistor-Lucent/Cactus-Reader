"""The reading-settings dialog. Changes apply immediately."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..settings import (
    DEFAULT_PAGE_GAP,
    DEFAULTS,
    PAGE_GAP_MAX,
    PAGE_GAP_MIN,
    PAGE_GAP_PRESETS,
    Settings,
    clamp_page_gap,
)
from .theme import enable_dark_titlebar, icon
from .widgets import SegmentedControl

_CUSTOM_GAP = "custom"


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
        enable_dark_titlebar(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel("阅读设置")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        intro = QLabel("按你的习惯排版漫画。所有更改会即时生效并自动保存。")
        intro.setObjectName("DialogIntro")
        intro.setWordWrap(True)
        root.addWidget(intro)
        root.addSpacing(2)

        # ---- layout and step --------------------------------------------
        layout_card = _card()
        layout_box = QVBoxLayout(layout_card)
        layout_box.setContentsMargins(20, 17, 20, 17)
        layout_box.setSpacing(13)

        self._view_seg = _row(
            layout_box,
            "页面布局",
            "单页浏览，或左右并排显示两页。",
            [("single", "单页", "每次显示一页漫画"),
             ("double", "双页", "并排显示两页漫画")],
        )
        layout_box.addWidget(_divider())

        self._step_seg = _row(
            layout_box,
            "双页翻页步长",
            "双页浏览时，一次翻页前进或后退的页数。",
            [("1", "翻 1 页", "每次翻一页"),
             ("2", "翻 2 页", "每次翻两页，跳过下一个双页组合")],
        )
        self._step_hint = QLabel()
        self._step_hint.setObjectName("HintLabel")
        self._step_hint.setWordWrap(True)
        layout_box.addWidget(self._step_hint)

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
        self._gap_hint = QLabel()
        self._gap_hint.setObjectName("HintLabel")
        self._gap_hint.setWordWrap(True)
        layout_box.addWidget(self._gap_hint)
        root.addWidget(layout_card)

        # ---- direction ---------------------------------------------------
        direction_card = _card()
        direction_box = QVBoxLayout(direction_card)
        direction_box.setContentsMargins(20, 17, 20, 17)
        direction_box.setSpacing(13)
        self._direction_seg = _row(
            direction_box,
            "阅读方向",
            "决定翻页方向和方向键的含义。",
            [("ltr", "从左向右", "右方向键翻到后一页"),
             ("rtl", "从右向左", "左方向键翻到后一页")],
        )
        self._direction_hint = QLabel()
        self._direction_hint.setObjectName("HintLabel")
        self._direction_hint.setWordWrap(True)
        direction_box.addWidget(self._direction_hint)
        root.addWidget(direction_card)

        # ---- fit ---------------------------------------------------------
        fit_card = _card()
        fit_box = QVBoxLayout(fit_card)
        fit_box.setContentsMargins(20, 17, 20, 17)
        fit_box.setSpacing(13)
        self._fit_seg = _row(
            fit_box,
            "页面适配",
            "铺满窗口的某一侧，多出的部分可以拖动查看。",
            [("height", "铺满高度", "页面高度贴合窗口"),
             ("width", "铺满宽度", "页面宽度贴合窗口")],
        )
        self._fit_hint = QLabel()
        self._fit_hint.setObjectName("HintLabel")
        self._fit_hint.setWordWrap(True)
        fit_box.addWidget(self._fit_hint)
        root.addWidget(fit_card)

        shortcuts = QLabel(
            "方向键翻页  ·  滚轮翻页  ·  Ctrl+滚轮缩放  ·  Ctrl+中键恢复适配  ·  拖动平移"
        )
        shortcuts.setObjectName("HintLabel")
        shortcuts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts.setWordWrap(True)
        root.addSpacing(2)
        root.addWidget(shortcuts)

        root.addSpacing(4)
        bottom = QHBoxLayout()
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
        root.addLayout(bottom)

        self._view_seg.changed.connect(self._on_view_changed)
        self._step_seg.changed.connect(self._on_step_changed)
        self._direction_seg.changed.connect(self._on_direction_changed)
        self._fit_seg.changed.connect(self._on_fit_changed)
        self._gap_picker.changed.connect(self._on_gap_changed)
        self._sync_from_settings()

    # ---- initialisation --------------------------------------------------
    def _sync_from_settings(self) -> None:
        s = self._settings
        self._view_seg.set_value(s.view_mode)
        self._step_seg.set_value(str(s.double_step))
        self._direction_seg.set_value(s.direction)
        self._fit_seg.set_value(s.fit_mode)
        self._gap_picker.set_value(s.page_gap)
        self._update_hints()
        self._step_seg.setEnabled(s.view_mode == "double")
        self._step_hint.setEnabled(s.view_mode == "double")

    def _update_hints(self) -> None:
        if self._settings.view_mode == "double":
            self._step_hint.setText(
                "双页浏览时，每次翻页前进或后退 1 或 2 页。"
            )
            self._gap_hint.setText(
                f"双页并排时两页之间的留白。可点选预设，或输入 "
                f"{PAGE_GAP_MIN}–{PAGE_GAP_MAX} 像素后按回车；超出范围会自动调整到边界。"
            )
        else:
            self._step_hint.setText(
                "单页浏览固定每次翻 1 页；切换到双页后可以调整步长。"
            )
            self._gap_hint.setText(
                f"当前为单页浏览，间距仅在双页模式下显示。可先设置 "
                f"{PAGE_GAP_MIN}–{PAGE_GAP_MAX} 像素，输入后按回车确认。"
            )
        if self._settings.direction == "rtl":
            self._direction_hint.setText(
                "从右向左：左方向键翻到后一页，右方向键翻到前一页。"
            )
        else:
            self._direction_hint.setText(
                "从左向右：右方向键翻到后一页，左方向键翻到前一页。"
            )
        if self._settings.fit_mode == "height":
            self._fit_hint.setText(
                "页面高度贴合窗口；超出的宽度可以按住鼠标左右拖动查看。"
            )
        else:
            self._fit_hint.setText(
                "页面宽度贴合窗口；超出的高度可以按住鼠标上下拖动查看。"
            )

    # ---- changes ---------------------------------------------------------
    def _on_view_changed(self, value: str) -> None:
        self._settings.view_mode = value
        enabled = value == "double"
        self._step_seg.setEnabled(enabled)
        self._step_hint.setEnabled(enabled)
        self._update_hints()
        self.settingsChanged.emit()

    def _on_step_changed(self, value: str) -> None:
        self._settings.double_step = int(value)
        self._update_hints()
        self.settingsChanged.emit()

    def _on_direction_changed(self, value: str) -> None:
        self._settings.direction = value
        self._update_hints()
        self.settingsChanged.emit()

    def _on_fit_changed(self, value: str) -> None:
        self._settings.fit_mode = value
        self._update_hints()
        self.settingsChanged.emit()

    def _on_gap_changed(self, value: int) -> None:
        self._settings.page_gap = value
        self._update_hints()
        self.settingsChanged.emit()

    def _reset(self) -> None:
        self._settings.view_mode = DEFAULTS["view_mode"]
        self._settings.double_step = DEFAULTS["double_step"]
        self._settings.direction = DEFAULTS["direction"]
        self._settings.fit_mode = DEFAULTS["fit_mode"]
        self._settings.page_gap = DEFAULTS["page_gap"]
        self._view_seg.set_value(self._settings.view_mode)
        self._step_seg.set_value(str(self._settings.double_step))
        self._direction_seg.set_value(self._settings.direction)
        self._fit_seg.set_value(self._settings.fit_mode)
        self._gap_picker.set_value(self._settings.page_gap)
        self._step_seg.setEnabled(self._settings.view_mode == "double")
        self._step_hint.setEnabled(self._settings.view_mode == "double")
        self._update_hints()
        self.settingsChanged.emit()

    def accept(self) -> None:
        self._gap_picker.commit()
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


def _row(parent_layout: QVBoxLayout, title: str, description: str,
         options: list[tuple[str, str, str]]) -> SegmentedControl:
    header = QHBoxLayout()
    header.setSpacing(16)
    text_box = QVBoxLayout()
    text_box.setSpacing(2)
    name = QLabel(title)
    name.setObjectName("CardTitle")
    desc = QLabel(description)
    desc.setObjectName("HintLabel")
    desc.setWordWrap(True)
    text_box.addWidget(name)
    text_box.addWidget(desc)
    header.addLayout(text_box, 1)
    segment = SegmentedControl(options)
    header.addWidget(segment, 0, Qt.AlignmentFlag.AlignVCenter)
    parent_layout.addLayout(header)
    return segment
