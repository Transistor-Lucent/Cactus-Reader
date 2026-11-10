"""Fullscreen edge page-turn button tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cactus_reader.settings import Settings  # noqa: E402
from cactus_reader.ui.main_window import MainWindow  # noqa: E402

SAMPLE = ROOT / "tests" / "samples" / "cactus_sample.epub"


class FullscreenEdgeButtonTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.window.close()
        self.temp.cleanup()

    # ---- helpers ---------------------------------------------------------
    def _enter_fullscreen(self) -> None:
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window._fullscreen)
        # Tests drive the pointer position explicitly; stop the cursor poll so
        # it cannot overwrite the state under test.
        self.window._edge_timer.stop()

    def _move_to(self, point: QPoint) -> None:
        self.window._update_edge_buttons(point)
        self.app.processEvents()

    def _center(self, button) -> QPoint:
        return button.geometry().center()

    # ---- tests -----------------------------------------------------------
    def test_buttons_are_hidden_outside_fullscreen(self) -> None:
        self.assertFalse(self.left_button.isVisible())
        self.assertFalse(self.right_button.isVisible())
        self.assertFalse(self.window._edge_timer.isActive())

        self._move_to(self._center(self.left_button))
        self.assertFalse(self.left_button.isVisible())
        self.assertFalse(self.right_button.isVisible())

    def test_poll_timer_runs_only_in_fullscreen_with_a_book(self) -> None:
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window._edge_timer.isActive())

        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertFalse(self.window._edge_timer.isActive())

    def test_only_the_matching_button_is_revealed(self) -> None:
        self._enter_fullscreen()

        self._move_to(self._center(self.left_button))
        self.assertTrue(self.left_button.isVisible())
        self.assertFalse(self.right_button.isVisible())

        self._move_to(self.window._central.rect().center())
        self.assertFalse(self.left_button.isVisible())
        self.assertFalse(self.right_button.isVisible())

        self._move_to(self._center(self.right_button))
        self.assertFalse(self.left_button.isVisible())
        self.assertTrue(self.right_button.isVisible())

    def test_reveal_zone_surrounds_the_button(self) -> None:
        self._enter_fullscreen()
        pad = self.window._EDGE_HOVER_PAD

        left = self.left_button.geometry()
        y = left.center().y()
        # Just inside / outside the halo around the button.
        self._move_to(QPoint(left.right() + pad, y))
        self.assertTrue(self.left_button.isVisible())
        self._move_to(QPoint(left.right() + pad + 2, y))
        self.assertFalse(self.left_button.isVisible())

        x = left.center().x()
        self._move_to(QPoint(x, left.bottom() + pad))
        self.assertTrue(self.left_button.isVisible())
        self._move_to(QPoint(x, left.bottom() + pad + 2))
        self.assertFalse(self.left_button.isVisible())

        # The old screen-edge strip rule is gone: a far corner is not "near"
        # the button even though it is at the left edge.
        self._move_to(QPoint(20, 20))
        self.assertFalse(self.left_button.isVisible())

        right = self.right_button.geometry()
        y = right.center().y()
        self._move_to(QPoint(right.left() - pad, y))
        self.assertTrue(self.right_button.isVisible())
        self._move_to(QPoint(right.left() - pad - 2, y))
        self.assertFalse(self.right_button.isVisible())

    def test_clicks_follow_the_reading_direction(self) -> None:
        self.settings.direction = "rtl"
        self.settings.view_mode = "double"
        self.settings.double_step = 2
        self.window._apply_reading_settings()
        self._enter_fullscreen()

        self._move_to(self._center(self.left_button))
        # Right-to-left reading: the left button turns forward, the right one
        # backward (disabled on the first page).
        self.assertTrue(self.left_button.isEnabled())
        self.assertFalse(self.right_button.isEnabled())
        QTest.mouseClick(self.left_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.reader.current_page, 2)

        self.window._edge_timer.stop()
        self._move_to(self._center(self.right_button))
        self.assertTrue(self.right_button.isEnabled())
        QTest.mouseClick(self.right_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.reader.current_page, 0)

    def test_ltr_right_button_turns_forward(self) -> None:
        self.settings.direction = "ltr"
        self.window._apply_reading_settings()
        self._enter_fullscreen()

        self._move_to(self._center(self.right_button))
        QTest.mouseClick(self.right_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.reader.current_page, 2)

        self.window._edge_timer.stop()
        self._move_to(self._center(self.left_button))
        QTest.mouseClick(self.left_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.reader.current_page, 0)

    def test_wheel_over_an_edge_button_still_turns_pages(self) -> None:
        self._enter_fullscreen()
        self._move_to(self._center(self.right_button))
        event = QWheelEvent(
            QPointF(10.0, 10.0),
            QPointF(self.right_button.mapToGlobal(QPoint(10, 10))),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(self.right_button, event)
        self.app.processEvents()
        self.assertEqual(self.reader.current_page, 2)

    def test_leaving_fullscreen_hides_the_buttons(self) -> None:
        self._enter_fullscreen()
        self._move_to(self._center(self.left_button))
        self.assertTrue(self.left_button.isVisible())

        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertFalse(self.window._fullscreen)
        self.assertFalse(self.left_button.isVisible())
        self.assertFalse(self.right_button.isVisible())
        self.assertFalse(self.window._edge_timer.isActive())

    def test_opening_a_book_in_fullscreen_starts_the_edge_keys(self) -> None:
        self.window.close_book()
        self.app.processEvents()
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertFalse(self.window._edge_timer.isActive())

        self._move_to(self._center(self.left_button))
        self.assertFalse(self.left_button.isVisible())

        self.window.open_path(str(SAMPLE))
        self.app.processEvents()
        self.assertTrue(self.window._edge_timer.isActive())

        self.window._edge_timer.stop()
        self._move_to(self._center(self.left_button))
        self.assertTrue(self.left_button.isVisible())


if __name__ == "__main__":
    unittest.main()
