"""Cactus Reader application bootstrap."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .paths import APP_VERSION
from .settings import Settings
from .ui.main_window import MainWindow
from .ui.theme import app_icon, apply_theme, enable_dark_titlebar


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "CactusStudio.CactusReader"
            )
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName("Cactus Reader")
    app.setApplicationDisplayName("Cactus Reader")
    app.setOrganizationName("Cactus Studio")
    app.setApplicationVersion(APP_VERSION)
    apply_theme(app)
    app.setWindowIcon(app_icon())

    settings = Settings()
    window = MainWindow(settings)
    window.show()
    enable_dark_titlebar(window)
    if bool(settings.data.get("window", {}).get("maximized")):
        window.showMaximized()

    files = [arg for arg in argv[1:] if not arg.startswith("-")]
    if files:
        QTimer.singleShot(80, lambda: window.open_path(files[0]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
