"""Minimal output formatting for AI consumption."""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path


def text(s: str) -> None:
    if s:
        print(s, end="" if s.endswith("\n") else "\n")


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def image(data: str, image_dir: str | None, index: int = 0) -> None:
    """Output image as file path or IMAGE:<base64> sentinel."""
    if image_dir:
        p = Path(image_dir)
        p.mkdir(parents=True, exist_ok=True)
        fname = p / f"image-{int(time.time())}-{index}.png"
        fname.write_bytes(base64.b64decode(data))
        print(str(fname))
    else:
        print(f"IMAGE:{data}")
