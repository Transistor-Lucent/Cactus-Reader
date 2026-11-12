"""Keyboard and mouse reference for the reader."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS, enable_dark_titlebar, icon

_HELP_HTML = f"""
<style>
  body {{ color: {COLORS['text_muted']}; font-size: 13px; line-height: 1.45; }}
  h2 {{ color: {COLORS['text']}; font-size: 15px; margin: 14px 0 4px 0; }}
  h2:first-child {{ margin-top: 0; }}
  b {{ color: {COLORS['text']}; }}
  .key {{
    color: {COLORS['accent']}; background: {COLORS['surface_raised']};
    border: 1px solid {COLORS['border']}; border-radius: 4px;
    padding: 1px 6px; font-family: Consolas, monospace; font-size: 12px;
  }}
  ul {{ margin-top: 2px; margin-bottom: 2px; }}
  li {{ margin: 2px 0; }}
  a {{ color: {COLORS['accent']}; }}
</style>

<h2>打开与关闭</h2>
<ul>
  <li><span class="key">Ctrl+O</span> 打开 EPUB / MOBI / PDF 漫画，也可以直接把文件拖进窗口；
      <span class="key">Ctrl+W</span> 关闭当前漫画。</li>
  <li>受 DRM 或密码保护的文件无法打开。</li>
</ul>

<h2>翻页</h2>
<ul>
  <li><span class="key">←</span> <span class="key">→</span> 按阅读方向翻页；
      滚轮、<span class="key">PageUp</span> / <span class="key">PageDown</span>、
      <span class="key">Space</span>、<span class="key">Backspace</span> 也可翻页，
      <span class="key">Home</span> / <span class="key">End</span> 跳到开头 / 结尾。</li>
  <li><span class="key">Shift+←</span> / <span class="key">Shift+→</span> 在双页模式下使用相反的步长：
      设置为 2 页时翻 1 页，设置为 1 页时翻 2 页。</li>
  <li>把鼠标移到窗口底部即可显示进度条，点击或拖动可立即跳转；移开鼠标后自动收起。</li>
</ul>

<h2>画面</h2>
<ul>
  <li><span class="key">H</span> 切换铺满高度 / 铺满宽度；
      <span class="key">Ctrl</span> + 滚轮缩放，<span class="key">Ctrl</span> + 鼠标中键恢复 100%。</li>
  <li><span class="key">Ctrl+←</span> / <span class="key">Ctrl+→</span> 逆时针 / 顺时针旋转 90°。
      双页显示时两页各围绕自身旋转，左右位置保持不变；每次旋转默认切换铺满方式，
      可在阅读设置中关闭。</li>
  <li>画面超出窗口时，按住鼠标左键拖动即可平移。</li>
  <li><span class="key">F</span> 或双击画面进入 / 退出全屏，<span class="key">Esc</span> 退出全屏。
      全屏时鼠标移到画面左右边缘可显示翻页按钮，鼠标静止一段时间后自动隐藏。</li>
</ul>

<h2>设置</h2>
<ul>
  <li><span class="key">Ctrl+,</span> 打开阅读设置，<span class="key">F1</span> 随时查看本帮助；
      所有设置自动保存，复制整个 CactusReader 文件夹即可连同设置和阅读记录一起迁移。</li>
</ul>
"""


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HelpDialog")
        self.setWindowTitle("使用帮助")
        self.setWindowIcon(icon("help"))
        self.setModal(True)
        self.setFixedSize(640, 590)
        enable_dark_titlebar(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 18)
        layout.setSpacing(14)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(_HELP_HTML)
        browser.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(browser, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton("知道了")
        close.setObjectName("PrimaryButton")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)
