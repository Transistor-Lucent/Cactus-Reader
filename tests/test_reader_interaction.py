"""Interaction tests for page turning, direction and fit layout."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cactus_reader.settings import Settings  # noqa: E402
from cactus_reader.ui.main_window import MainWindow  # noqa: E402

SAMPLE = ROOT / "tests" / "samples" / "cactus_sample.epub"


class ReaderInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.temp.name) / "settings.json")
        self.window = MainWindow(settings)
        self.window.open_path(str(SAMPLE))
        self.reader = self.window._reader
        self.settings = settings
        self.assertEqual(self.reader.current_page, 0)

    def tearDown(self) -> None:
        self.window.close()
        self.temp.cleanup()

    def _apply(self) -> None:
        self.window._apply_reading_settings()

    def test_ltr_arrows_and_double_step_two(self) -> None:
        self.settings.direction = "ltr"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self._apply()
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 2)
        self.window._left_action()
        self.assertEqual(self.reader.current_page, 0)

    def test_rtl_arrows_reverse(self) -> None:
        self.settings.direction = "rtl"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self._apply()
        # Left arrow moves forward in right-to-left reading.
        self.window._left_action()
        self.assertEqual(self.reader.current_page, 2)
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 0)
        # At the very start, right arrow cannot go back further.
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 0)

    def test_double_step_one(self) -> None:
        self.settings.direction = "ltr"
        self.settings.view_mode = "double"
        self.settings.double_step = 1
        self._apply()
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 1)
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 2)
        self.window._left_action()
        self.assertEqual(self.reader.current_page, 1)

    def test_single_mode_ignores_double_step(self) -> None:
        self.settings.direction = "ltr"
        self.settings.view_mode = "single"
        self.settings.double_step = 2
        self._apply()
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 1)

    def test_cannot_turn_past_end(self) -> None:
        self.reader.go_to(10)
        self.assertFalse(self.reader.can_forward())
        self.window._right_action()
        self.assertEqual(self.reader.current_page, 10)

    def test_fit_height_and_width(self) -> None:
        self.reader.resize(1000, 600)
        self.reader.set_fit_mode("height")
        self.reader._rebuild_layout()
        self.assertEqual(self.reader._content_size.height(), 600)
        # Two 900x1300 pages at 600 px high are narrower than the viewport.
        self.assertAlmostEqual(self.reader._content_size.width(), 2 * 600 * 900 / 1300 + 6, delta=2)

        self.reader.set_fit_mode("width")
        self.reader._rebuild_layout()
        self.assertEqual(self.reader._content_size.width(), 1000)
        self.assertGreater(self.reader._content_size.height(), 600)

    def test_rtl_spread_puts_first_page_on_the_right(self) -> None:
        self.reader.resize(1000, 600)
        self.reader.set_config(two_page=True, step=2, rtl=True)
        self.reader._rebuild_layout()
        indices = [index for index, _ in self.reader._entries]
        self.assertEqual(indices, [1, 0])
        self.assertLess(self.reader._entries[0][1].x(), self.reader._entries[1][1].x())

    def test_page_status_uses_spread(self) -> None:
        self.reader.set_config(two_page=True, step=2, rtl=False)
        self.assertEqual(self.reader.status_text(), "1–2 / 11")

    def test_real_key_events_work_even_when_slider_has_focus(self) -> None:
        self.settings.direction = "rtl"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self._apply()
        self.window.show()
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1500))

        # The application-level filter must see arrows before the focused
        # widget consumes them.
        self.window._slider.setFocus()
        QTest.keyClick(self.window._slider, Qt.Key.Key_Left)
        self.assertEqual(self.reader.current_page, 2)
        QTest.keyClick(self.window._slider, Qt.Key.Key_Right)
        self.assertEqual(self.reader.current_page, 0)

        QTest.keyClick(self.window, Qt.Key.Key_F)
        self.assertEqual(self.settings.fit_mode, "width")

    def test_shift_arrows_use_the_alternate_double_page_step(self) -> None:
        self.settings.direction = "ltr"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self._apply()
        self.window.show()
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1500))

        # Configured step 2 -> Shift+arrow moves a single page.
        QTest.keyClick(
            self.window, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 1)
        QTest.keyClick(
            self.window, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 0)

        # Configured step 1 -> Shift+arrow moves two pages.
        self.settings.double_step = 1
        self._apply()
        QTest.keyClick(
            self.window, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 2)
        QTest.keyClick(
            self.window, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 0)

        # Single-page mode keeps its normal behaviour.
        self.settings.view_mode = "single"
        self.settings.double_step = 2
        self._apply()
        QTest.keyClick(
            self.window, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 1)

    def test_shift_arrows_follow_the_reading_direction(self) -> None:
        self.settings.direction = "rtl"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self._apply()
        self.window.show()
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1500))

        # A physical left arrow moves forward in right-to-left reading, but
        # still uses the alternate one-page step.
        QTest.keyClick(
            self.window, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 1)
        QTest.keyClick(
            self.window, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier
        )
        self.assertEqual(self.reader.current_page, 0)

    def test_ctrl_arrows_rotate_windowed_and_fullscreen(self) -> None:
        self.window.show()
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1500))

        # Counter-clockwise and clockwise keep their physical meaning even
        # while the slider owns the focus.
        self.window._slider.setFocus()
        QTest.keyClick(
            self.window._slider, Qt.Key.Key_Left,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(self.reader.rotation, 270)
        QTest.keyClick(
            self.window._slider, Qt.Key.Key_Right,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(self.reader.rotation, 0)

        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window._fullscreen)
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1500))
        QTest.keyClick(
            self.window._reader, Qt.Key.Key_Left,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(self.reader.rotation, 270)
        QTest.keyClick(
            self.window._reader, Qt.Key.Key_Right,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.assertEqual(self.reader.rotation, 0)
        self.window.toggle_fullscreen()


if __name__ == "__main__":
    unittest.main()
