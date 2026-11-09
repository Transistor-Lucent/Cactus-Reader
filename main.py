"""Development entry point; the packaged app uses this file too."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if not getattr(sys, "frozen", False) and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cactus_reader.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
