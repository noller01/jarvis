#!/usr/bin/env python3
"""JARVIS — All-in-one AI personal assistant desktop app."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from jarvis.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
