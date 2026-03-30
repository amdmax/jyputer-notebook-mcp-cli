"""Read and run .ipynb notebook helpers."""

from __future__ import annotations

from jl.http_client import JupyterClient
from jl.kernel import execute, ExecutionResult


def read_cells(client: JupyterClient, path: str) -> list[dict]:
    """Return list of cells with index, type, source."""
    nb = client.get_notebook(path)
    cells = nb.get("content", {}).get("cells", [])
    return [
        {
            "index": i,
            "type": c.get("cell_type", "code"),
            "source": "".join(c.get("source", [])),
        }
        for i, c in enumerate(cells)
    ]


def code_steps(client: JupyterClient, path: str) -> list[dict]:
    """Return only code cells with 1-based step numbers."""
    cells = read_cells(client, path)
    return [
        {**c, "step": i + 1}
        for i, c in enumerate(c for c in cells if c["type"] == "code")
    ]


def run_step(
    client: JupyterClient,
    path: str,
    step: int,
    kernel_id: str,
    url: str,
    token: str,
    timeout: int,
) -> ExecutionResult:
    steps = code_steps(client, path)
    target = next((s for s in steps if s["step"] == step), None)
    if target is None:
        raise ValueError(f"Step {step} not found (notebook has {len(steps)} steps)")
    return execute(kernel_id, target["source"], url, token, timeout)


def run_cell(
    client: JupyterClient,
    path: str,
    cell_index: int,
    kernel_id: str,
    url: str,
    token: str,
    timeout: int,
) -> ExecutionResult:
    cells = read_cells(client, path)
    target = next((c for c in cells if c["index"] == cell_index), None)
    if target is None:
        raise ValueError(f"Cell {cell_index} not found in {path}")
    if target["type"] != "code":
        raise ValueError(f"Cell {cell_index} is {target['type']}, not code")
    return execute(kernel_id, target["source"], url, token, timeout)


def run_all(
    client: JupyterClient,
    path: str,
    kernel_id: str,
    url: str,
    token: str,
    timeout: int,
) -> list[tuple[int, ExecutionResult]]:
    cells = read_cells(client, path)
    results = []
    for c in cells:
        if c["type"] != "code" or not c["source"].strip():
            continue
        r = execute(kernel_id, c["source"], url, token, timeout)
        results.append((c["index"], r))
        if r.error:
            break  # stop on first error
    return results
