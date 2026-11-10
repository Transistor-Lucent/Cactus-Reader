"""Progress slider, double-page gap and zoom interaction tests."""

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
from PySide6.QtGui import QColor, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cactus_reader.settings import (  # noqa: E402
    DEFAULT_HIDE_CURSOR_DELAY,
    HIDE_CURSOR_MAX,
    HIDE_CURSOR_MIN,
    PAGE_GAP_MAX,
    Settings,
)
from cactus_reader.ui.main_window import MainWindow  # noqa: E402
from cactus_reader.ui.settings_dialog import SettingsDialog  # noqa: E402
from cactus_reader.ui.widgets import PageSlider  # noqa: E402

SAMPLE = ROOT / "tests" / "samples" / "cactus_sample.epub"


class ReaderFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name) / "settings.json")
        self.window = MainWindow(self.settings)
        self.window.open_path(str(SAMPLE))
        self.reader = self.window._reader
        self.slider = self.window._slider
        self.window.resize(1240, 820)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.temp.cleanup()

    def _slider_click(self, fraction: float) -> None:
        y = self.slider.height() // 2
        x = int(round(10 + fraction * (self.slider.width() - 20)))
        QTest.mouseClick(
            self.slider, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, QPoint(x, y),
        )
        self.app.processEvents()

    def test_slider_pages_follow_while_dragging(self) -> None:
        y = self.slider.height() // 2
        QTest.mousePress(
            self.slider, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier, QPoint(14, y),
        )
        self.assertTrue(self.slider.isSliderDown())

        QTest.mouseMove(self.slider, QPoint(int(self.slider.width() * 0.30), y))
        self.app.processEvents()
        first_page = self.reader.current_page
        self.assertGreater(first_page, 0)
        self.assertEqual(first_page, self.slider.value())

        QTest.mouseMove(self.slider, QPoint(int(self.slider.width() * 0.72), y))
        self.app.processEvents()
        second_page = self.reader.current_page
        self.assertGreater(second_page, first_page)
        self.assertEqual(second_page, self.slider.value())
        self.assertTrue(self.slider.isSliderDown())

        QTest.mouseRelease(
            self.slider, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(int(self.slider.width() * 0.72), y),
        )
        self.assertFalse(self.slider.isSliderDown())
        self.assertEqual(self.reader.current_page, second_page)

    def test_slider_click_jumps_and_direction_mirrors_progress(self) -> None:
        self.settings.direction = "ltr"
        self.window._apply_reading_settings()
        self._slider_click(1.0)
        self.assertEqual(self.reader.current_page, 10)

        self.settings.direction = "rtl"
        self.window._apply_reading_settings()
        self.assertTrue(self.slider.rtl)
        # In right-to-left mode the right edge is the beginning.
        self._slider_click(1.0)
        self.assertEqual(self.reader.current_page, 0)
        self._slider_click(0.0)
        self.assertEqual(self.reader.current_page, 10)

    def test_slider_fill_matches_reading_direction(self) -> None:
        slider = PageSlider()
        slider.setRange(0, 10)
        slider.setValue(5)
        slider.resize(240, 24)
        slider.show()
        self.app.processEvents()
        y = slider.height() // 2

        image = slider.grab().toImage()
        self._assert_color(image.pixelColor(48, y), "#4F8F4B")              # read
        self._assert_color(image.pixelColor(192, y), ("#263126", "#334234"))  # unread

        slider.set_rtl(True)
        slider.update()
        self.app.processEvents()
        image = slider.grab().toImage()
        self._assert_color(image.pixelColor(48, y), ("#263126", "#334234"))  # unread
        self._assert_color(image.pixelColor(192, y), "#4F8F4B")             # read
        slider.close()

    def _assert_color(
        self, color: QColor, expected: str | tuple[str, ...]
    ) -> None:
        candidates = (expected,) if isinstance(expected, str) else expected
        distances = []
        for candidate in candidates:
            target = QColor(candidate)
            distances.append(
                abs(color.red() - target.red())
                + abs(color.green() - target.green())
                + abs(color.blue() - target.blue())
            )
        self.assertLessEqual(
            min(distances),
            12,
            f"{color.name()} is not close to {expected}",
        )

    def test_double_page_gap_changes_spacing(self) -> None:
        self.reader.resize(1000, 600)
        self.reader.set_config(two_page=True, step=2, rtl=False)
        self.reader.set_page_gap(0)
        self.reader._rebuild_layout()
        self.assertEqual(len(self.reader._entries), 2)
        right_page = self.reader._entries[1][1]
        left_page = self.reader._entries[0][1]
        self.assertAlmostEqual(right_page.left() - left_page.right(), 0.0, delta=0.01)

        self.reader.set_page_gap(48)
        self.reader._rebuild_layout()
        right_page = self.reader._entries[1][1]
        left_page = self.reader._entries[0][1]
        self.assertAlmostEqual(right_page.left() - left_page.right(), 48.0, delta=0.01)

    def test_rotation_swaps_page_orientation(self) -> None:
        self.reader.resize(800, 600)
        self.reader.set_config(two_page=False, step=1, rtl=False)
        self.reader.set_fit_mode("height")
        self.reader._rebuild_layout()
        upright = self.reader._entries[0][1]
        self.assertLess(upright.width(), upright.height())

        self.assertTrue(self.reader.rotate_cw())
        self.assertEqual(self.reader.rotation, 90)
        self.reader._rebuild_layout()
        turned = self.reader._entries[0][1]
        self.assertGreater(turned.width(), turned.height())
        self.assertAlmostEqual(turned.height(), self.reader.height(), delta=1)

        pixmap = self.reader._pixmap_for(0, turned)
        self.assertIsNotNone(pixmap)
        assert pixmap is not None
        self.assertGreater(pixmap.width(), pixmap.height())

        self.reader.rotate_cw()
        self.assertEqual(self.reader.rotation, 180)
        self.reader.rotate_ccw()
        self.assertEqual(self.reader.rotation, 90)
        self.reader.rotate_ccw()
        self.assertEqual(self.reader.rotation, 0)

    def test_rotation_keeps_spread_left_right_order(self) -> None:
        self.reader.resize(1000, 600)
        self.reader.set_fit_mode("height")
        self.reader.set_config(two_page=True, step=2, rtl=False)
        self.reader._rebuild_layout()
        self.assertEqual([index for index, _ in self.reader._entries], [0, 1])

        self.reader.rotate_cw()
        self.reader._rebuild_layout()
        self.assertEqual([index for index, _ in self.reader._entries], [0, 1])
        left, right = self.reader._entries
        self.assertEqual(left[0], 0)
        self.assertEqual(right[0], 1)
        self.assertLess(left[1].center().x(), right[1].center().x())

        self.reader.set_config(two_page=True, step=2, rtl=True)
        self.reader._rebuild_layout()
        self.assertEqual([index for index, _ in self.reader._entries], [1, 0])
        self.reader.rotate_ccw()
        self.reader._rebuild_layout()
        self.assertEqual([index for index, _ in self.reader._entries], [1, 0])
        left, right = self.reader._entries
        self.assertEqual(left[0], 1)
        self.assertEqual(right[0], 0)
        self.assertLess(left[1].center().x(), right[1].center().x())

    def test_rotation_switches_fit_mode_unless_disabled(self) -> None:
        self.settings.fit_mode = "height"
        self.settings.rotate_switches_fit = True
        self.window._apply_reading_settings()

        self.window.rotate_cw()
        self.assertEqual(self.reader.rotation, 90)
        self.assertEqual(self.settings.fit_mode, "width")
        self.assertEqual(self.reader._fit, "width")

        self.window.rotate_ccw()
        self.assertEqual(self.reader.rotation, 0)
        self.assertEqual(self.settings.fit_mode, "height")
        self.assertEqual(self.reader._fit, "height")

        self.settings.rotate_switches_fit = False
        self.window.rotate_cw()
        self.assertEqual(self.reader.rotation, 90)
        self.assertEqual(self.settings.fit_mode, "height")
        self.assertEqual(self.reader._fit, "height")

        self.window.rotate_ccw()
        self.assertEqual(self.reader.rotation, 0)
        self.assertEqual(self.settings.fit_mode, "height")

    def test_rotate_fit_switch_control_updates_settings(self) -> None:
        dialog = SettingsDialog(self.settings)
        self.assertEqual(dialog._rotate_fit_seg.value(), "on")
        off_button = dialog._rotate_fit_seg.button("off")
        self.assertIsNotNone(off_button)
        assert off_button is not None
        off_button.click()
        self.assertFalse(self.settings.rotate_switches_fit)

        dialog._reset()
        self.assertTrue(self.settings.rotate_switches_fit)
        self.assertEqual(dialog._rotate_fit_seg.value(), "on")
        dialog.close()

    def test_progress_slider_has_no_hover_tooltip(self) -> None:
        self.assertEqual(self.slider.toolTip(), "")

    def test_hide_cursor_delay_picker_clamps_and_resets(self) -> None:
        dialog = SettingsDialog(self.settings)
        picker = dialog._hide_cursor_picker
        picker._input.setText("99")
        picker.commit()
        self.assertEqual(self.settings.hide_cursor_delay, HIDE_CURSOR_MAX)
        self.assertEqual(picker.value(), HIDE_CURSOR_MAX)
        self.assertEqual(picker._input.text(), str(HIDE_CURSOR_MAX))

        picker._input.setText("0")
        picker.commit()
        self.assertEqual(self.settings.hide_cursor_delay, HIDE_CURSOR_MIN)
        self.assertEqual(picker._input.text(), str(HIDE_CURSOR_MIN))

        picker._input.setText("7")
        picker.commit()
        self.assertEqual(self.settings.hide_cursor_delay, 7)
        self.assertEqual(picker.value(), 7)

        dialog._reset()
        self.assertEqual(
            self.settings.hide_cursor_delay, DEFAULT_HIDE_CURSOR_DELAY
        )
        self.assertEqual(picker.value(), DEFAULT_HIDE_CURSOR_DELAY)
        dialog.close()

    def test_gap_input_is_numeric_and_clamps_on_enter(self) -> None:
        dialog = SettingsDialog(self.settings)
        dialog.show()
        self.app.processEvents()
        picker = dialog._gap_picker
        line = picker._input
        line.setFocus()
        self.app.processEvents()

        line.selectAll()
        QTest.keyClicks(line, "999")
        self.assertEqual(line.text(), "999")
        QTest.keyClick(line, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(picker.value(), PAGE_GAP_MAX)
        self.assertEqual(self.settings.page_gap, PAGE_GAP_MAX)
        self.assertEqual(line.text(), str(PAGE_GAP_MAX))

        line.selectAll()
        QTest.keyClicks(line, "-5")
        QTest.keyClick(line, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(picker.value(), 0)
        self.assertEqual(self.settings.page_gap, 0)
        self.assertEqual(line.text(), "0")

        line.selectAll()
        QTest.keyClicks(line, "31")
        QTest.keyClick(line, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(self.settings.page_gap, 31)
        self.assertEqual(line.text(), "31")

        line.selectAll()
        QTest.keyClicks(line, "4444")
        self.assertEqual(line.text(), "4444")
        dialog.accept()
        self.app.processEvents()
        self.assertEqual(self.settings.page_gap, PAGE_GAP_MAX)
        self.assertEqual(line.text(), str(PAGE_GAP_MAX))
        dialog.close()

    def test_ctrl_wheel_zooms_and_ctrl_middle_resets_to_fit(self) -> None:
        self.settings.fit_mode = "width"
        self.window._apply_reading_settings()
        self.reader._rebuild_layout()
        base_width = self.reader._content_size.width()
        self.assertEqual(base_width, self.reader.width())

        self._send_ctrl_wheel(120)
        self.assertGreater(self.reader.zoom_factor, 1.0)
        self.reader._rebuild_layout()
        self.assertGreater(self.reader._content_size.width(), base_width)

        QTest.mouseClick(
            self.reader, Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.ControlModifier, QPoint(80, 80),
        )
        self.app.processEvents()
        self.assertEqual(self.reader.zoom_factor, 1.0)
        self.reader._rebuild_layout()
        self.assertEqual(self.reader._content_size.width(), base_width)

        self._send_ctrl_wheel(-120)
        self.assertLess(self.reader.zoom_factor, 1.0)
        self.reader._rebuild_layout()
        self.assertLess(self.reader._content_size.width(), base_width)

    def _send_ctrl_wheel(self, delta: int) -> None:
        local = QPointF(120.0, 120.0)
        global_pos = QPointF(self.reader.mapToGlobal(QPoint(120, 120)))
        event = QWheelEvent(
            local,
            global_pos,
            QPoint(0, 0),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(self.reader, event)
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
