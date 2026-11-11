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
  <li><span class="key">Ctrl+O</span> 打开 EPUB / MOBI 漫画，也可以直接把文件拖进窗口。</li>
  <li>支持常见结构的 EPUB 与 MOBI；DRM 加密文件无法打开，特殊排版会尝试兼容渲染。</li>
  <li><span class="key">Ctrl+W</span> 关闭当前漫画，回到首页。</li>
</ul>

<h2>翻页</h2>
<ul>
  <li><span class="key">←</span> <span class="key">→</span> 按阅读方向翻页。从左向右时，→ 是后一页；
      从右向左时，← 是后一页。顶栏「打开漫画」左侧的两个翻页按钮遵循同样的规则。</li>
  <li><span class="key">Shift</span> + <span class="key">←</span> /
      <span class="key">→</span> 双页浏览时按相反的步长翻页：设置为 2 页时翻 1 页，
      设置为 1 页时翻 2 页。</li>
  <li><span class="key">PageDown</span> / <span class="key">Space</span> 后一页，
      <span class="key">PageUp</span> / <span class="key">Backspace</span> 前一页。</li>
  <li><span class="key">Home</span> 回到开头，<span class="key">End</span> 跳到结尾。</li>
  <li>底栏会自动隐藏；把鼠标移到窗口底部即可显示进度条和显示按钮，移开后再收起。
      铺满高度会随底栏的显示和隐藏自动调整页面大小。</li>
  <li>点击或拖动底栏进度条，画面会立即跳到对应页；拖动时也持续跟随。</li>
  <li>进度条方向会跟随阅读方向：从右向左阅读时，右侧是已读部分。</li>
  <li>鼠标滚轮向下翻到后一页，向上翻到前一页。</li>
  <li>双页浏览时，一次翻 1 页或 2 页由「阅读设置 → 双页显示翻页步长」决定。</li>
</ul>

<h2>画面</h2>
<ul>
  <li><span class="key">H</span> 在「铺满高度」和「铺满宽度」之间切换。</li>
  <li><span class="key">Ctrl</span> + 鼠标滚轮向上放大、向下缩小；
      <span class="key">Ctrl</span> + 鼠标中键恢复到当前铺满模式的 100% 大小。</li>
  <li><span class="key">Ctrl+←</span> 逆时针旋转 90°，<span class="key">Ctrl+→</span>
      顺时针旋转 90°；把鼠标移到窗口底部显示底栏后，右侧也有对应的旋转按钮。双页浏览时两页各围绕自身旋转，
      左右两页的相对位置保持不变。默认每次旋转还会自动在铺满高度与铺满宽度之间
      切换，可在阅读设置中关闭。</li>
  <li>画面超出窗口时，按住鼠标左键拖动即可平移。</li>
  <li>全屏时，把鼠标移到画面左侧或右侧边缘中部的翻页按钮附近，按钮才会浮现；
      点击即可按当前阅读方向向左或向右翻一页。鼠标离开按钮周围后按钮自动隐藏。</li>
  <li>全屏时鼠标静止达到设定的等待时间后会自动隐藏，移动鼠标立即恢复；
      等待时间可在「阅读设置 → 全屏时隐藏鼠标」中调整。</li>
  <li><span class="key">F</span> 或双击画面进入 / 退出全屏，<span class="key">Esc</span> 退出全屏。</li>
</ul>

<h2>设置</h2>
<ul>
  <li><span class="key">Ctrl+,</span> 打开阅读设置：单页 / 双页、翻页步长、双页间距、阅读方向、页面适配、
      旋转时是否切换铺满高度/宽度，以及全屏时隐藏鼠标的等待时间。</li>
  <li>双页间距可选择预设，也可输入 0–200 像素的自定义值；按回车确认。
      全屏时隐藏鼠标的等待时间同样支持预设和 1–60 秒的自定义输入。</li>
  <li>所有设置自动保存。复制整个 CactusReader 文件夹，即可连同设置和阅读记录一起迁移；
      如果程序目录不可写，则保存到当前用户的本地配置目录。</li>
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
