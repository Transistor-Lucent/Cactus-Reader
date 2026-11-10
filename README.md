# Cactus Reader

一个轻量、深色风格的 Windows EPUB / MOBI 漫画阅读器。支持单页与双页浏览、左右阅读方向、铺满高度与铺满宽度，并且整个程序可以随文件夹一起迁移。

## 快速开始

双击本目录下的 **`CactusReader.exe`** 即可启动。

- 点「打开漫画」或按 `Ctrl+O` 选择文件。
- 也可以直接把 `.epub` / `.mobi` 文件拖进窗口。
- 最近阅读的漫画会显示在首页，下次打开可以接着上次的页数继续读。

## 阅读设置

按 `Ctrl+,` 或点右上角设置按钮：

| 设置项 | 可选值 | 说明 |
| --- | --- | --- |
| 页面布局 | 单页 / 双页 | 双页时按书本跨页显示 |
| 双页翻页步长 | 1 页 / 2 页 | 仅双页布局生效，一个设置项控制一次翻页的页数，没有额外的步长按钮 |
| 双页间距 | 0 / 6 / 12 / 24 px，或自定义 | 双页中间留白。自定义输入框只接受数字，范围 0–200 px；按回车或离开输入框后，超出范围的值会立即调整到边界 |
| 阅读方向 | 从左向右 / 从右向左 | 同时决定画面顺序、左右方向键的含义和进度条方向 |
| 页面适配 | 铺满高度 / 铺满宽度 | 严格按所选方向铺满，超出部分可拖动查看 |

设置会立即生效并自动保存。双页步长为 1 时，相邻跨页会保留一页重叠；步长为 2 时，每次翻两页。

## 快捷键

| 按键 | 作用 |
| --- | --- |
| `←` / `→` | 按阅读方向翻页。从左向右时，`→` 下一页、`←` 上一页；从右向左时，`←` 下一页、`→` 上一页 |
| `PageDown` / `Space` | 下一页 |
| `PageUp` / `Backspace` | 上一页 |
| `Home` / `End` | 回到开头 / 跳到结尾 |
| 点击或拖动进度条 | 立即跳到对应页；拖动过程中画面持续跟随进度条 |
| 鼠标滚轮 | 向下翻下一页，向上翻上一页 |
| `Ctrl` + 鼠标滚轮 | 向上放大，向下缩小 |
| `Ctrl` + 鼠标中键 | 恢复到当前铺满模式（铺满高度或铺满宽度）的 100% 大小 |
| 鼠标拖动 | 画面超出窗口时平移画面 |
| 双击画面 / `F11` | 进入或退出全屏 |
| 全屏边缘按钮 | 鼠标移到画面左右边缘中部的翻页按钮附近时出现，点击按阅读方向向左 / 向右翻页 |
| `Esc` | 退出全屏 |
| `F` | 切换铺满高度 / 铺满宽度 |
| `Ctrl+O` | 打开漫画 |
| `Ctrl+,` | 阅读设置 |
| `F1` | 使用帮助 |
| `Ctrl+W` | 关闭当前漫画 |

底栏两侧的翻页按钮与方向键遵循同一套阅读方向规则。进度条也会跟随阅读方向：从左向右阅读时左侧是已读部分，从右向左阅读时右侧是已读部分。

全屏阅读时，画面左右两侧各有一个边缘翻页按钮：只有把鼠标移到对应按钮附近，按钮才会浮现，离开按钮周围后自动隐藏。点击按钮等同于按一次对应方向的翻页键，遵循当前的阅读方向与双页翻页步长。

## 支持的文件

- **EPUB**：按 OPF spine 顺序提取图片，支持 `<img>`、SVG `<image>`、`<object>` 图片页面，自动补上不在正文中的封面。
- **MOBI / PRC / AZW / AZW3**：读取 Palm 数据库、PalmDOC 压缩文本和图片资源，支持 KF8 的 `kindle:flow` / `kindle:embed` 引用，按漫画页顺序显示，并跳过缩略图与间隔图。
- 遇到不常见的排版或损坏的文件时，会尝试用内置 MuPDF 兼容渲染器打开。
- **不支持 DRM 加密文件**。受密码或 DRM 保护的漫画会提示无法打开。

## 便携使用

程序所需的运行时文件都在 `CactusReader.exe` 和 `_internal` 文件夹中：

```text
CactusReader\
├─ CactusReader.exe
├─ _internal\          # Qt、PyMuPDF 等运行时和图标资源
├─ assets\             # 源文件中的图标资源（打包后也复制了一份在 _internal）
├─ settings.json       # 首次运行后生成：设置、最近阅读、窗口位置
├─ src\                # Python 源码
├─ tests\              # 测试与示例漫画
├─ tools\              # 图标生成脚本
├─ CactusReader.spec
├─ version_info.txt
├─ build.ps1
└─ README.md
```

- 设置文件默认写在 `CactusReader.exe` 所在目录，所以复制整个 `CactusReader` 文件夹到任何用户目录或 U 盘后，设置和阅读记录会一起迁移。
- 如果程序目录不可写（例如安装在受保护的系统目录），会自动改用 `%LOCALAPPDATA%\CactusReader\settings.json`，程序仍可正常启动。
- 迁移时只需保证 `CactusReader.exe` 与 `_internal` 在同一目录；复制整个文件夹最省心。

## 从源码运行

需要 Python 3.13：

```powershell
python -m pip install -r requirements.txt
python main.py
```

## 构建可执行文件

安装构建依赖后，在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

脚本会使用 PyInstaller 的单文件夹模式构建，并把 `dist\CactusReader` 中的 `CactusReader.exe` 和 `_internal` 复制回项目根目录。构建完成后直接双击根目录的 `CactusReader.exe` 即可。

`build.ps1 -NoClean` 可以复用上一次的构建缓存。

## 运行测试

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -v
```

测试覆盖翻页规则、左右方向、双页步长、铺满高度/宽度布局、设置持久化、EPUB/MOBI/KF8 解析和真实方向键事件。示例漫画在 `tests/samples/`，可用 `tests/make_samples.py` 重新生成 EPUB（需要 Pillow）。

## 已知限制

- DRM 加密的 Kindle 或 EPUB 文件无法打开。
- 极少数使用特殊排版、纯 CSS 背景图或异常容器的漫画可能无法提取页面，此时程序会尝试兼容渲染；若两种方式都失败，会给出错误提示。
- 双页步长为 1 时允许跨页重叠，这是为了在“每次只前进一页”和双页显示之间保持一致。
