"""Kernel ID persistence across CLI invocations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _state_path(profile: str) -> Path:
    p = Path.home() / ".local" / "state" / "jl"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{profile}.json"


def load(profile: str) -> dict | None:
    p = _state_path(profile)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save(profile: str, kernel_id: str, url: str, notebook: str | None = None) -> None:
    p = _state_path(profile)
    existing = load(profile) or {}
    data = {
        "kernel_id": kernel_id,
        "url": url,
        "created_at": existing.get(
            "created_at", datetime.now(timezone.utc).isoformat()
        ),
        "notebook": notebook if notebook is not None else existing.get("notebook"),
    }
    p.write_text(json.dumps(data))


def set_notebook(profile: str, notebook: str) -> None:
    st = load(profile) or {}
    st["notebook"] = notebook
    _state_path(profile).write_text(json.dumps(st))


def clear(profile: str) -> None:
    p = _state_path(profile)
    if p.exists():
        p.unlink()
