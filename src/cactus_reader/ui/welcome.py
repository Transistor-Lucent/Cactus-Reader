"""The home screen shown before a comic is open."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS, icon
from .widgets import RecentRow, logo_pixmap


class WelcomePage(QWidget):
    openRequested = Signal()
    recentOpened = Signal(str)
    recentRemoved = Signal(str)
    clearRecentRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WelcomePage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 22, 32, 24)
        outer.setSpacing(0)
        outer.addStretch(1)

        column = QWidget()
        column.setFixedWidth(700)
        column.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        outer.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(88))
        logo.setFixedSize(88, 88)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(14)

        title = QLabel("Cactus Reader")
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(22)

        open_button = QPushButton("打开漫画")
        open_button.setObjectName("PrimaryButton")
        open_button.setIcon(icon("open", "#0B140B", 18))
        open_button.setIconSize(QSize(18, 18))
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        open_button.setFixedHeight(44)
        open_button.setMinimumWidth(170)
        open_button.clicked.connect(self.openRequested)
        layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)

        hint = QLabel("或将 EPUB / MOBI 文件拖放到窗口中")
        hint.setObjectName("WelcomeHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addSpacing(30)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(8)
        section = QLabel("最近阅读")
        section.setObjectName("SectionLabel")
        header.addWidget(section)
        header.addStretch(1)
        self._clear_button = QPushButton("清空")
        self._clear_button.setObjectName("LinkButton")
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_button.setToolTip("清空最近阅读记录")
        self._clear_button.clicked.connect(self.clearRecentRequested)
        header.addWidget(self._clear_button)
        layout.addLayout(header)
        layout.addSpacing(10)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setMaximumHeight(262)
        self._scroll.setMinimumHeight(64)
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 6, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_host)
        layout.addWidget(self._scroll)
        outer.addStretch(1)

        self._rows: list[QWidget] = []
        self._empty: QWidget | None = None

    def refresh(self, recent: list[dict]) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        self._empty = None

        if not recent:
            empty = QFrame()
            empty.setObjectName("EmptyRecent")
            empty.setFixedHeight(64)
            box = QVBoxLayout(empty)
            box.setContentsMargins(16, 0, 16, 0)
            text = QLabel("还没有阅读记录，打开一本漫画开始吧。")
            text.setObjectName("EmptyRecentText")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(text)
            self._list_layout.insertWidget(0, empty)
            self._rows.append(empty)
            self._empty = empty
            self._clear_button.setVisible(False)
            self._scroll.setFixedHeight(64)
            return

        self._clear_button.setVisible(True)
        for row_index, entry in enumerate(recent):
            row = RecentRow(entry)
            row.opened.connect(self.recentOpened)
            row.removed.connect(self.recentRemoved)
            self._list_layout.insertWidget(row_index, row)
            self._rows.append(row)

        visible = min(len(recent), 4)
        height = visible * 58 + max(0, visible - 1) * 8
        self._scroll.setFixedHeight(height)
