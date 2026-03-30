"""Config loading: CLI flags > env vars > ~/.config/jl/config.toml > defaults."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    url: str = "http://localhost:8888"
    token: str = ""
    ssh_host: str | None = None
    ssh_local_port: int = 8888
    ssh_remote_port: int = 8888
    image_dir: str | None = None
    timeout: int = 120
    profile: str = "default"


def _toml_path() -> Path:
    return Path.home() / ".config" / "jl" / "config.toml"


def _load_toml(profile: str) -> dict:
    p = _toml_path()
    if not p.exists():
        return {}
    with open(p, "rb") as f:
        data = tomllib.load(f)
    return data.get(profile, data.get("default", {}))


def load(
    profile: str = "default",
    url: str | None = None,
    token: str | None = None,
) -> Config:
    toml = _load_toml(profile)

    cfg = Config(profile=profile)

    # TOML layer
    cfg.url = toml.get("url", cfg.url)
    cfg.token = toml.get("token", cfg.token)
    cfg.ssh_host = toml.get("ssh_host", cfg.ssh_host)
    cfg.ssh_local_port = int(toml.get("ssh_local_port", cfg.ssh_local_port))
    cfg.ssh_remote_port = int(toml.get("ssh_remote_port", cfg.ssh_remote_port))
    cfg.image_dir = toml.get("image_dir", cfg.image_dir)
    cfg.timeout = int(toml.get("timeout", cfg.timeout))

    # Env layer
    cfg.url = os.environ.get("JUPYTER_URL", cfg.url)
    cfg.token = os.environ.get("JUPYTER_TOKEN", cfg.token)
    cfg.ssh_host = os.environ.get("JL_SSH_HOST", cfg.ssh_host)
    cfg.image_dir = os.environ.get("JL_IMAGE_DIR", cfg.image_dir)
    cfg.timeout = int(os.environ.get("JL_TIMEOUT", cfg.timeout))

    # CLI flag layer
    if url is not None:
        cfg.url = url
    if token is not None:
        cfg.token = token

    return cfg
