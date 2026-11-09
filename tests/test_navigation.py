"""Navigation rules: page pairing, step and boundary behaviour."""

from __future__ import annotations

import unittest

from cactus_reader.navigation import (
    can_turn_back,
    can_turn_forward,
    page_status,
    turn_back,
    turn_forward,
    visible_pages,
)


class VisiblePagesTests(unittest.TestCase):
    def test_single_page(self) -> None:
        self.assertEqual(visible_pages(3, 10, False), [3])
        self.assertEqual(visible_pages(9, 10, False), [9])

    def test_double_spread(self) -> None:
        self.assertEqual(visible_pages(0, 10, True), [0, 1])
        self.assertEqual(visible_pages(4, 10, True), [4, 5])

    def test_final_odd_page_is_alone(self) -> None:
        self.assertEqual(visible_pages(8, 10, True), [8, 9])
        self.assertEqual(visible_pages(9, 11, True), [9, 10])
        self.assertEqual(visible_pages(9, 10, True), [9])

    def test_clamps_out_of_range(self) -> None:
        self.assertEqual(visible_pages(-4, 5, False), [0])
        self.assertEqual(visible_pages(99, 5, False), [4])


class TurnTests(unittest.TestCase):
    def test_double_step_two(self) -> None:
        self.assertEqual(turn_forward(0, 11, True, 2), 2)
        self.assertEqual(turn_forward(6, 11, True, 2), 8)
        self.assertEqual(turn_back(8, 11, True, 2), 6)

    def test_double_step_one(self) -> None:
        self.assertEqual(turn_forward(0, 11, True, 1), 1)
        self.assertEqual(turn_back(1, 11, True, 1), 0)

    def test_single_page_always_steps_one(self) -> None:
        self.assertEqual(turn_forward(2, 11, False, 2), 3)
        self.assertEqual(turn_back(2, 11, False, 2), 1)

    def test_cannot_move_past_final_spread(self) -> None:
        self.assertFalse(can_turn_forward(9, 11, True))
        self.assertFalse(can_turn_forward(8, 10, True))
        self.assertTrue(can_turn_forward(7, 10, True))
        self.assertEqual(turn_forward(9, 11, True, 2), 9)

    def test_back_boundary(self) -> None:
        self.assertFalse(can_turn_back(0))
        self.assertEqual(turn_back(0, 11, True, 2), 0)
        self.assertEqual(turn_back(1, 11, True, 2), 0)


class StatusTests(unittest.TestCase):
    def test_status(self) -> None:
        self.assertEqual(page_status(0, 11, False), "1 / 11")
        self.assertEqual(page_status(0, 11, True), "1–2 / 11")
        self.assertEqual(page_status(9, 11, True), "10–11 / 11")
        self.assertEqual(page_status(10, 11, True), "11 / 11")
        self.assertEqual(page_status(0, 0, True), "0 / 0")


if __name__ == "__main__":
    unittest.main()
