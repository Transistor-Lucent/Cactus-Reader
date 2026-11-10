"""Settings validation, round-tripping and recent-file bookkeeping."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cactus_reader.settings import (
    DEFAULT_HIDE_CURSOR_DELAY,
    DEFAULT_PAGE_GAP,
    DEFAULTS,
    HIDE_CURSOR_MAX,
    HIDE_CURSOR_MIN,
    PAGE_GAP_MAX,
    Settings,
    clamp_hide_cursor_delay,
    clamp_page_gap,
)


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "settings.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_defaults(self) -> None:
        settings = Settings(self.path)
        self.assertEqual(settings.view_mode, "double")
        self.assertEqual(settings.double_step, 2)
        self.assertEqual(settings.direction, "ltr")
        self.assertEqual(settings.fit_mode, "height")
        self.assertTrue(settings.rotate_switches_fit)
        self.assertEqual(settings.page_gap, DEFAULT_PAGE_GAP)
        self.assertEqual(settings.hide_cursor_delay, DEFAULT_HIDE_CURSOR_DELAY)
        self.assertEqual(settings.effective_step, 2)

    def test_effective_step_in_single_mode(self) -> None:
        settings = Settings(self.path)
        settings.view_mode = "single"
        self.assertEqual(settings.effective_step, 1)

    def test_invalid_values_are_rejected(self) -> None:
        settings = Settings(self.path)
        settings.view_mode = "triple"
        settings.direction = "up"
        settings.fit_mode = "stretch"
        settings.double_step = 7
        settings.page_gap = 999
        settings.hide_cursor_delay = 999
        self.assertEqual(settings.view_mode, "double")
        self.assertEqual(settings.direction, "ltr")
        self.assertEqual(settings.fit_mode, "height")
        self.assertEqual(settings.double_step, 1)
        self.assertEqual(settings.page_gap, PAGE_GAP_MAX)
        self.assertEqual(settings.hide_cursor_delay, HIDE_CURSOR_MAX)
        settings.page_gap = -4
        settings.hide_cursor_delay = -4
        self.assertEqual(settings.page_gap, 0)
        self.assertEqual(settings.hide_cursor_delay, HIDE_CURSOR_MIN)
        self.assertEqual(clamp_page_gap("bad"), DEFAULT_PAGE_GAP)
        self.assertEqual(
            clamp_hide_cursor_delay("bad"), DEFAULT_HIDE_CURSOR_DELAY
        )

    def test_round_trip_with_unicode(self) -> None:
        settings = Settings(self.path)
        settings.view_mode = "single"
        settings.direction = "rtl"
        settings.fit_mode = "width"
        settings.double_step = 1
        settings.page_gap = 18
        settings.hide_cursor_delay = 7
        settings.touch_recent(
            r"C:\漫画\仙人掌.epub", "仙人掌漫画", "某作者", "epub", 4, 20
        )
        settings.save()

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw["recent"][0]["title"], "仙人掌漫画")

        loaded = Settings(self.path)
        self.assertEqual(loaded.view_mode, "single")
        self.assertEqual(loaded.direction, "rtl")
        self.assertEqual(loaded.fit_mode, "width")
        self.assertEqual(loaded.double_step, 1)
        self.assertEqual(loaded.page_gap, 18)
        self.assertEqual(loaded.hide_cursor_delay, 7)
        self.assertEqual(loaded.data["recent"][0]["page"], 4)
        self.assertEqual(loaded.data["recent"][0]["total"], 20)

    def test_rotate_fit_switch_round_trips_and_validates(self) -> None:
        settings = Settings(self.path)
        settings.rotate_switches_fit = False
        settings.save()
        self.assertFalse(Settings(self.path).rotate_switches_fit)

        self.path.write_text(
            json.dumps({"rotate_switches_fit": "off"}), encoding="utf-8"
        )
        self.assertTrue(Settings(self.path).rotate_switches_fit)

    def test_recent_is_deduplicated_and_capped(self) -> None:
        settings = Settings(self.path)
        for index in range(14):
            settings.touch_recent(
                self.temp.name + f"/book{index}.epub",
                f"Book {index}", "", "EPUB", index, 30,
            )
        settings.touch_recent(
            self.temp.name + "/book3.epub", "Book 3", "A", "EPUB", 9, 30
        )
        titles = [entry["title"] for entry in settings.data["recent"]]
        self.assertEqual(titles[0], "Book 3")
        self.assertEqual(len(titles), 10)
        self.assertEqual(titles.count("Book 3"), 1)
        self.assertEqual(settings.data["recent"][0]["page"], 9)

    def test_recent_page_update_and_removal(self) -> None:
        settings = Settings(self.path)
        path = self.temp.name + "/comic.mobi"
        settings.touch_recent(path, "Comic", "", "MOBI", 0, 50)
        settings.set_recent_page(path, 12)
        settings.set_recent_total(path, 50)
        entry = settings.find_recent(path)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["page"], 12)
        self.assertEqual(entry["total"], 50)
        settings.remove_recent(path)
        self.assertIsNone(settings.find_recent(path))

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")
        settings = Settings(self.path)
        self.assertEqual(settings.view_mode, DEFAULTS["view_mode"])
        settings.save()
        json.loads(self.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
