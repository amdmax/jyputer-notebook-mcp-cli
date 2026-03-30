"""
Happy path integration tests for jl CLI.

Requires:
- JUPYTER_URL env var pointing to a running Jupyter server
- JUPYTER_TOKEN env var with the server token
- NOTEBOOK_LOCAL env var: local path to receipt_ocr.ipynb
- NOTEBOOK_REMOTE env var: remote path to upload to (default: invoices/notebooks/receipt_ocr.ipynb)
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

JUPYTER_URL = os.environ["JUPYTER_URL"]
JUPYTER_TOKEN = os.environ["JUPYTER_TOKEN"]
NOTEBOOK_LOCAL = Path(os.environ.get("NOTEBOOK_LOCAL", ""))
NOTEBOOK_REMOTE = os.environ.get("NOTEBOOK_REMOTE", "invoices/notebooks/receipt_ocr.ipynb")

BASE = ["jl", "--url", JUPYTER_URL, "--token", JUPYTER_TOKEN]


def jl(*args, timeout=30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*BASE, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def fresh_kernel():
    """One fresh kernel for the whole module."""
    r = jl("exec", "--fresh", "print('kernel ready')")
    assert r.returncode == 0
    assert "kernel ready" in r.stdout
    yield
    jl("kernel-reset")


@pytest.fixture(scope="module")
def uploaded_notebook(fresh_kernel):
    """Upload notebook once for the whole module."""
    r = jl("upload", str(NOTEBOOK_LOCAL), NOTEBOOK_REMOTE)
    assert r.returncode == 0
    assert "uploaded" in r.stdout
    return NOTEBOOK_REMOTE


def test_kernels_lists_running_kernels():
    r = jl("kernels")
    assert r.returncode == 0
    assert len(r.stdout.strip().splitlines()) >= 1


def test_ls_root():
    r = jl("ls")
    assert r.returncode == 0
    assert "invoices" in r.stdout


def test_ls_inbound():
    r = jl("ls", "invoices/inbound")
    assert r.returncode == 0
    lines = r.stdout.strip().splitlines()
    assert len(lines) >= 1
    assert all(".png" in l for l in lines)


def test_upload_sets_active_notebook(uploaded_notebook):
    r = jl("steps")
    assert r.returncode == 0
    assert "step   1" in r.stdout
    assert "step   2" in r.stdout


def test_steps_shows_code_cells_only(uploaded_notebook):
    r = jl("steps")
    assert r.returncode == 0
    lines = r.stdout.strip().splitlines()
    # all lines must start with "step"
    assert all(l.strip().startswith("step") for l in lines)
    # 1-based and sequential
    numbers = [int(l.split()[1]) for l in lines]
    assert numbers == list(range(1, len(numbers) + 1))


def test_step2_imports(fresh_kernel, uploaded_notebook):
    r = jl("step", "2", timeout=60)
    assert r.returncode == 0
    assert "ollama" in r.stdout
    assert "pydantic" in r.stdout


def test_step3_config(fresh_kernel, uploaded_notebook):
    # set cwd and model override first
    jl(
        "exec",
        "import os; os.chdir('/home/m/invoices/notebooks'); OLLAMA_MODEL='qwen2.5vl:32b'",
    )
    r = jl("step", "3", timeout=30)
    assert r.returncode == 0
    assert "Images:" in r.stdout
    count_line = next(l for l in r.stdout.splitlines() if "Images:" in l)
    count = int(count_line.split(":")[1].strip())
    assert count >= 1


def test_step4_ollama_ready(fresh_kernel, uploaded_notebook):
    r = jl("step", "4", timeout=30)
    assert r.returncode == 0
    assert "Ollama running" in r.stdout
    assert "ready" in r.stdout


def test_steps5_6_7_prompts_and_models(fresh_kernel, uploaded_notebook):
    r5 = jl("step", "5")
    assert r5.returncode == 0
    assert "Prompts set" in r5.stdout

    r6 = jl("step", "6")
    assert r6.returncode == 0

    r7 = jl("step", "7")
    assert r7.returncode == 0


def test_step8_single_image_ocr(fresh_kernel, uploaded_notebook):
    r = jl("step", "8", "--timeout", "180", timeout=190)
    assert r.returncode == 0
    assert "merchant_name" in r.stdout
    assert "total" in r.stdout


def test_step9_parse_and_validate(fresh_kernel, uploaded_notebook):
    r = jl("step", "9", timeout=30)
    assert r.returncode == 0
    assert "Parsed OK" in r.stdout
    # extract JSON block and validate it parses
    lines = r.stdout.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "{")
    raw = "\n".join(lines[start:])
    data = json.loads(raw)
    assert "merchant_name" in data
    assert "total" in data
    assert isinstance(data["total"], (int, float))
    assert data["currency"] == "UAH"


def test_exec_state_persists(fresh_kernel):
    jl("exec", "x = 42")
    r = jl("exec", "print(x)")
    assert r.returncode == 0
    assert "42" in r.stdout
