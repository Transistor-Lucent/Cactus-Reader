"""Pure page-navigation rules, kept separate for deterministic testing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadingConfig:
    two_page: bool
    step: int
    rtl: bool


def visible_pages(current: int, page_count: int, two_page: bool) -> list[int]:
    if page_count <= 0:
        return []
    current = max(0, min(int(current), page_count - 1))
    if two_page and current + 1 < page_count:
        return [current, current + 1]
    return [current]


def can_turn_forward(current: int, page_count: int, two_page: bool) -> bool:
    if page_count <= 1 or current >= page_count - 1:
        return False
    if two_page and current + 1 >= page_count - 1:
        # Both of the final pages are already on screen.
        return False
    return True


def turn_forward(current: int, page_count: int, two_page: bool, step: int) -> int:
    if page_count <= 0:
        return 0
    step = max(1, min(int(step), 2))
    if not two_page:
        step = 1
    if not can_turn_forward(current, page_count, two_page):
        return max(0, min(current, page_count - 1))
    return min(page_count - 1, current + step)


def can_turn_back(current: int) -> bool:
    return current > 0


def turn_back(current: int, page_count: int, two_page: bool, step: int) -> int:
    if page_count <= 0:
        return 0
    step = max(1, min(int(step), 2))
    if not two_page:
        step = 1
    return max(0, min(int(current), page_count - 1) - step)


def page_status(current: int, page_count: int, two_page: bool) -> str:
    pages = visible_pages(current, page_count, two_page)
    if not pages:
        return "0 / 0"
    if len(pages) == 1:
        return f"{pages[0] + 1} / {page_count}"
    return f"{pages[0] + 1}–{pages[-1] + 1} / {page_count}"
