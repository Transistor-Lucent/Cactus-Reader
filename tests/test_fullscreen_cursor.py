"""Fullscreen idle cursor hiding tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from time import monotonic

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cactus_reader.settings import Settings  # noqa: E402
from cactus_reader.ui.main_window import MainWindow  # noqa: E402

SAMPLE = ROOT / "tests" / "samples" / "cactus_sample.epub"


class FullscreenCursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name) / "settings.json")
        self.window = MainWindow(self.settings)
        self.window.open_path(str(SAMPLE))
        self.window.resize(1200, 800)
        self.window.show()
        self.app.processEvents()
        self.reader = self.window._reader
        self.left_button = self.window._edge_left_button
        self.right_button = self.window._edge_right_button

        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window._fullscreen)
        # The poll otherwise re-reads the real system cursor and would
        # overwrite the deterministic positions used below.
        self.window._edge_timer.stop()
        central = self.window._central
        self.inside = central.mapToGlobal(central.rect().center())

    def tearDown(self) -> None:
        self.window.close()
        self.temp.cleanup()

    def _force_idle(self, seconds: float) -> None:
        self.window._cursor_last_pos = QPoint(self.inside)
        self.window._cursor_idle_since = monotonic() - seconds

    def test_idle_hides_cursor_and_movement_restores_it(self) -> None:
        self.settings.hide_cursor_delay = 3
        self._force_idle(2.9)
        self.window._poll_cursor_hide(self.inside)
        self.assertFalse(self.window._cursor_hidden)

        self._force_idle(3.1)
        self.window._poll_cursor_hide(self.inside)
        self.assertTrue(self.window._cursor_hidden)
        self.assertEqual(
            self.reader.cursor().shape(), Qt.CursorShape.BlankCursor
        )
        self.assertEqual(
            self.left_button.cursor().shape(), Qt.CursorShape.BlankCursor
        )
        self.assertEqual(
            self.right_button.cursor().shape(), Qt.CursorShape.BlankCursor
        )

        moved = self.inside + QPoint(2, 0)
        self.window._poll_cursor_hide(moved)
        self.assertFalse(self.window._cursor_hidden)
        self.assertNotEqual(
            self.reader.cursor().shape(), Qt.CursorShape.BlankCursor
        )
        self.assertEqual(
            self.left_button.cursor().shape(),
            Qt.CursorShape.PointingHandCursor,
        )

    def test_delay_setting_controls_the_threshold(self) -> None:
        self.settings.hide_cursor_delay = 10
        self._force_idle(9.5)
        self.window._poll_cursor_hide(self.inside)
        self.assertFalse(self.window._cursor_hidden)

        self._force_idle(10.5)
        self.window._poll_cursor_hide(self.inside)
        self.assertTrue(self.window._cursor_hidden)

    def test_leaving_fullscreen_restores_the_cursor(self) -> None:
        self._force_idle(99)
        self.window._poll_cursor_hide(self.inside)
        self.assertTrue(self.window._cursor_hidden)

        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertFalse(self.window._fullscreen)
        self.assertFalse(self.window._cursor_hidden)
        self.assertFalse(self.window._edge_timer.isActive())
        self.assertNotEqual(
            self.reader.cursor().shape(), Qt.CursorShape.BlankCursor
        )
        self.assertNotEqual(
            self.left_button.cursor().shape(),
            Qt.CursorShape.BlankCursor,
        )

    def test_pointer_outside_the_reading_area_keeps_a_cursor(self) -> None:
        self.settings.hide_cursor_delay = 1
        outside = self.inside + QPoint(self.window.width() + 400, 0)
        self.window._cursor_last_pos = QPoint(outside)
        self.window._cursor_idle_since = monotonic() - 99
        self.window._poll_cursor_hide(outside)
        self.assertFalse(self.window._cursor_hidden)

    def test_cursor_is_not_hidden_outside_fullscreen(self) -> None:
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertFalse(self.window._fullscreen)

        self.settings.hide_cursor_delay = 1
        self._force_idle(99)
        self.window._poll_cursor_hide(self.inside)
        self.assertFalse(self.window._cursor_hidden)


if __name__ == "__main__":
    unittest.main()
