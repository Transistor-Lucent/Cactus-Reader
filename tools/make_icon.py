"""Render assets/cactus.svg into the Windows icon and a PNG preview."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PIL import Image  # noqa: E402


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(ROOT / "assets" / "cactus.svg"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return image


def main() -> int:
    app = QGuiApplication(sys.argv)
    del app
    assets = ROOT / "assets"
    png = assets / "icon.png"
    image = render(256)
    image.save(str(png))
    loaded = Image.open(png).convert("RGBA")
    loaded.save(
        assets / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(png)
    print(assets / "icon.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
