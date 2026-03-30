"""SSH ControlMaster tunnel management."""

from __future__ import annotations

import subprocess
import time

_PERSIST_SECS = 600  # SSH ControlPersist duration in seconds
_RETRIES = 10  # attempts to verify socket after tunnel start
_RETRY_INTERVAL = 0.1  # seconds between verification attempts


def _socket(host: str) -> str:
    return f"/tmp/jl-ssh-{host}.sock"


def _is_alive(host: str) -> bool:
    r = subprocess.run(
        ["ssh", "-O", "check", "-S", _socket(host), host],
        capture_output=True,
    )
    return r.returncode == 0


def ensure(host: str, local_port: int, remote_port: int) -> None:
    """Open SSH tunnel if not already open."""
    if _is_alive(host):
        return
    subprocess.run(
        [
            "ssh",
            "-fNM",
            "-S",
            _socket(host),
            "-L",
            f"{local_port}:localhost:{remote_port}",
            "-o",
            f"ControlPersist={_PERSIST_SECS}",
            "-o",
            "StrictHostKeyChecking=no",
            host,
        ],
        check=True,
    )
    for _ in range(_RETRIES):
        if _is_alive(host):
            return
        time.sleep(_RETRY_INTERVAL)
    raise RuntimeError(f"SSH tunnel to {host} did not start")


def close(host: str) -> None:
    subprocess.run(
        ["ssh", "-O", "exit", "-S", _socket(host), host],
        capture_output=True,
    )
