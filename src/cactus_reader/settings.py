"""Small, dependency-free settings store with portable JSON persistence."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import choose_settings_path

VIEW_MODES = ("single", "double")
DIRECTIONS = ("ltr", "rtl")
FIT_MODES = ("height", "width")
MAX_RECENT = 10

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "view_mode": "double",
    "double_step": 2,
    "direction": "ltr",
    "fit_mode": "height",
    "window": {
        "x": None,
        "y": None,
        "width": 1240,
        "height": 820,
        "maximized": False,
    },
    "last_dir": "",
    "recent": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalise_path(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except OSError:
        return path


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or choose_settings_path()
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ---- persistence -----------------------------------------------------
    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}

        data = copy.deepcopy(DEFAULTS)
        for key in ("view_mode", "double_step", "direction", "fit_mode", "last_dir"):
            if key in raw:
                data[key] = raw[key]
        window = raw.get("window")
        if isinstance(window, dict):
            for key in ("x", "y", "width", "height"):
                value = window.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    data["window"][key] = int(value)
            data["window"]["maximized"] = bool(window.get("maximized", False))

        recent: list[dict[str, Any]] = []
        for item in raw.get("recent", []) if isinstance(raw.get("recent"), list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            entry = {
                "path": item["path"],
                "title": str(item.get("title") or Path(item["path"]).stem),
                "author": str(item.get("author") or ""),
                "format": str(item.get("format") or "").upper(),
                "page": _safe_int(item.get("page"), 0),
                "total": _safe_int(item.get("total"), 0),
                "opened_at": str(item.get("opened_at") or ""),
            }
            recent.append(entry)
        data["recent"] = recent[:MAX_RECENT]

        if data["view_mode"] not in VIEW_MODES:
            data["view_mode"] = DEFAULTS["view_mode"]
        if data["direction"] not in DIRECTIONS:
            data["direction"] = DEFAULTS["direction"]
        if data["fit_mode"] not in FIT_MODES:
            data["fit_mode"] = DEFAULTS["fit_mode"]
        data["double_step"] = 2 if _safe_int(data.get("double_step"), 2) == 2 else 1
        self.data = data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(
            prefix=".settings-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass

    # ---- typed accessors -------------------------------------------------
    @property
    def view_mode(self) -> str:
        return self.data["view_mode"]

    @view_mode.setter
    def view_mode(self, value: str) -> None:
        self.data["view_mode"] = value if value in VIEW_MODES else "double"

    @property
    def double_step(self) -> int:
        return 2 if _safe_int(self.data.get("double_step"), 2) == 2 else 1

    @double_step.setter
    def double_step(self, value: int) -> None:
        self.data["double_step"] = 2 if int(value) == 2 else 1

    @property
    def direction(self) -> str:
        return self.data["direction"]

    @direction.setter
    def direction(self, value: str) -> None:
        self.data["direction"] = value if value in DIRECTIONS else "ltr"

    @property
    def fit_mode(self) -> str:
        return self.data["fit_mode"]

    @fit_mode.setter
    def fit_mode(self, value: str) -> None:
        self.data["fit_mode"] = value if value in FIT_MODES else "height"

    @property
    def effective_step(self) -> int:
        return self.double_step if self.view_mode == "double" else 1

    def update_window(self, x: int, y: int, w: int, h: int, maximized: bool) -> None:
        self.data["window"] = {
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "maximized": bool(maximized),
        }

    # ---- recent files ----------------------------------------------------
    def find_recent(self, path: str | os.PathLike[str]) -> dict[str, Any] | None:
        target = _normalise_path(str(path))
        for entry in self.data["recent"]:
            if _normalise_path(entry["path"]) == target:
                return entry
        return None

    def touch_recent(self, path: str, title: str, author: str, fmt: str,
                     page: int, total: int) -> None:
        target = _normalise_path(path)
        existing = self.find_recent(path)
        if existing is not None:
            self.data["recent"].remove(existing)
            entry = existing
        else:
            entry = {"path": str(path)}
        entry.update(
            {
                "path": str(path),
                "title": title or Path(path).stem,
                "author": author or "",
                "format": (fmt or "").upper(),
                "page": max(0, int(page)),
                "total": max(0, int(total)),
                "opened_at": _now(),
            }
        )
        self.data["recent"].insert(0, entry)
        del self.data["recent"][MAX_RECENT:]
        # Keep only one path spelling if the same book was opened via a
        # different but equivalent path.
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in self.data["recent"]:
            key = _normalise_path(item["path"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self.data["recent"] = unique[:MAX_RECENT]

    def set_recent_page(self, path: str, page: int) -> None:
        entry = self.find_recent(path)
        if entry is not None:
            entry["page"] = max(0, int(page))

    def set_recent_total(self, path: str, total: int) -> None:
        entry = self.find_recent(path)
        if entry is not None:
            entry["total"] = max(0, int(total))

    def remove_recent(self, path: str) -> None:
        entry = self.find_recent(path)
        if entry is not None:
            self.data["recent"].remove(entry)

    def clear_recent(self) -> None:
        self.data["recent"] = []


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default
