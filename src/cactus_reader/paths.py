"""Filesystem helpers that keep the application fully portable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "CactusReader"
APP_VERSION = "1.0.0"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Directory containing CactusReader.exe (the folder the user copies)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """Directory holding bundled read-only resources."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return app_dir()


def asset_path(*parts: str) -> Path:
    return bundle_dir().joinpath("assets", *parts)


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def choose_settings_path() -> Path:
    """Prefer a settings file beside the exe, so copying the folder migrates it.

    If that folder is read-only (for example a protected Program Files install),
    fall back to the standard per-user location instead of failing to start.
    """
    portable = app_dir() / "settings.json"
    try:
        if portable.exists():
            with portable.open("a", encoding="utf-8"):
                pass
        else:
            probe = app_dir() / ".cactusreader-write-test"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
        return portable
    except OSError:
        return user_data_dir() / "settings.json"
