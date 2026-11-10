"""Render the UI offscreen to catch layout and styling mistakes quickly."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cactus_reader.settings import Settings  # noqa: E402
from cactus_reader.ui.help_dialog import HelpDialog  # noqa: E402
from cactus_reader.ui.main_window import MainWindow  # noqa: E402
from cactus_reader.ui.settings_dialog import SettingsDialog  # noqa: E402
from cactus_reader.ui.theme import apply_theme  # noqa: E402


def main() -> int:
    out = ROOT / "tests" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    settings = Settings(Path(tempfile.mkdtemp()) / "settings.json")
    window = MainWindow(settings)
    window.resize(1240, 820)
    window.show()
    QTest.qWait(300)
    window.grab().save(str(out / "01_welcome.png"))

    window.open_path(str(ROOT / "tests" / "samples" / "cactus_sample.epub"))
    QTest.qWait(500)
    window.grab().save(str(out / "02_reader_double.png"))

    settings.direction = "rtl"
    settings.fit_mode = "width"
    window._apply_reading_settings()
    QTest.qWait(300)
    window.grab().save(str(out / "03_reader_rtl_width.png"))

    settings.view_mode = "single"
    window._apply_reading_settings()
    QTest.qWait(300)
    window.grab().save(str(out / "04_reader_single.png"))

    settings.view_mode = "double"
    settings.direction = "ltr"
    settings.fit_mode = "height"
    window._apply_reading_settings()

    window._set_fullscreen(True)
    window._edge_timer.stop()
    QTest.qWait(300)
    area = window._central.rect()
    window._update_edge_buttons(QPoint(int(area.width() * 0.05), area.height() // 2))
    QTest.qWait(150)
    window.grab().save(str(out / "05_fullscreen_left.png"))
    window._update_edge_buttons(QPoint(int(area.width() * 0.95), area.height() // 2))
    QTest.qWait(150)
    window.grab().save(str(out / "06_fullscreen_right.png"))
    window._set_fullscreen(False)
    QTest.qWait(200)

    dialog = SettingsDialog(settings, window)
    dialog.show()
    QTest.qWait(250)
    dialog.grab().save(str(out / "07_settings.png"))
    dialog.close()

    help_dialog = HelpDialog(window)
    help_dialog.show()
    QTest.qWait(250)
    help_dialog.grab().save(str(out / "08_help.png"))
    help_dialog.close()

    window.close_book()
    QTest.qWait(250)
    window.grab().save(str(out / "09_welcome_recent.png"))

    window.close()
    QTest.qWait(100)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
