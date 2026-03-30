"""jl — minimal Jupyter Lab CLI for AI-driven remote execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

_PREVIEW_WIDTH = 80  # chars of cell source shown in brief/steps output
_ID_PREFIX_LEN = 8  # chars of kernel/session UUID shown in listings

import jl.config as config_mod
import jl.output as out
import jl.state as state_mod
import jl.tunnel as tunnel_mod
from jl.http_client import JupyterClient, JupyterError
from jl.kernel import execute
from jl.notebook import code_steps, read_cells, run_all, run_cell, run_step


def _emit_result(result, cfg) -> int:
    for txt in result.outputs:
        out.text(txt)
    for i, img in enumerate(result.images):
        out.image(img, cfg.image_dir, i)
    if result.error:
        out.error(result.error)
        return 1
    return 0


def _delete_kernel_state(cfg, client: JupyterClient) -> None:
    st = state_mod.load(cfg.profile)
    if st:
        try:
            client.delete_kernel(st["kernel_id"])
        except JupyterError:
            pass
        state_mod.clear(cfg.profile)


def _get_or_create_kernel(cfg, client: JupyterClient) -> str:
    st = state_mod.load(cfg.profile)
    if st and st.get("url") == cfg.url:
        k = client.get_kernel(st["kernel_id"])
        if k:
            return st["kernel_id"]
    k = client.create_kernel("python3")
    state_mod.save(cfg.profile, k["id"], cfg.url)
    return k["id"]


def _active_notebook(args, cfg) -> str:
    nb = getattr(args, "notebook", None)
    if nb:
        return nb
    st = state_mod.load(cfg.profile)
    nb = st and st.get("notebook")
    if not nb:
        out.error("no active notebook — pass a path or run 'jl upload' first")
        raise SystemExit(1)
    return nb


def cmd_exec(args, cfg, client: JupyterClient) -> int:
    if args.fresh:
        _delete_kernel_state(cfg, client)

    kernel_id = args.kernel_id or _get_or_create_kernel(cfg, client)
    result = execute(kernel_id, args.code, cfg.url, cfg.token, args.timeout)
    return _emit_result(result, cfg)


def cmd_run(args, cfg, client: JupyterClient) -> int:
    kernel_id = _get_or_create_kernel(cfg, client)

    if args.cell is not None:
        result = run_cell(
            client,
            args.notebook,
            args.cell,
            kernel_id,
            cfg.url,
            cfg.token,
            args.timeout,
        )
        return _emit_result(result, cfg)

    results = run_all(
        client, args.notebook, kernel_id, cfg.url, cfg.token, args.timeout
    )
    for cell_idx, result in results:
        rc = _emit_result(result, cfg)
        if rc:
            out.error(f"stopped at cell {cell_idx}")
            return rc
    return 0


def cmd_read(args, cfg, client: JupyterClient) -> int:
    cells = read_cells(client, args.notebook)
    for c in cells[: args.cells]:
        src = c["source"]
        line = src.split("\n")[0][:_PREVIEW_WIDTH] if args.format == "brief" else src
        print(f"{c['index']:3}  {c['type']:<8}  {line}")
    return 0


def cmd_ls(args, cfg, client: JupyterClient) -> int:
    items = client.list_contents(args.path or "")
    for item in items:
        t = item.get("type", "")
        if args.type and t != args.type:
            continue
        name = item.get("name", item.get("path", ""))
        size = item.get("size") or ""
        print(f"{name:<40}  {t:<10}  {size}")
    return 0


def cmd_upload(args, cfg, client: JupyterClient) -> int:
    local = Path(args.local)
    if not local.exists():
        out.error(f"file not found: {local}")
        return 1
    content = json.loads(local.read_text())
    remote = args.remote or local.name
    result = client.upload_notebook(remote, content)
    state_mod.set_notebook(cfg.profile, remote)
    print(f"uploaded → {result.get('path', remote)}")
    print(f"active notebook set to: {remote}")
    return 0


def cmd_steps(args, cfg, client: JupyterClient) -> int:
    nb = _active_notebook(args, cfg)
    for s in code_steps(client, nb):
        first_line = s["source"].split("\n")[0][:_PREVIEW_WIDTH]
        print(f"step {s['step']:3}  (cell {s['index']:3})  {first_line}")
    return 0


def cmd_step(args, cfg, client: JupyterClient) -> int:
    nb = _active_notebook(args, cfg)
    kernel_id = _get_or_create_kernel(cfg, client)
    result = run_step(client, nb, args.n, kernel_id, cfg.url, cfg.token, args.timeout)
    return _emit_result(result, cfg)


def cmd_kernels(args, cfg, client: JupyterClient) -> int:
    for k in client.list_kernels():
        print(
            f"{k.get('id', '')[:_ID_PREFIX_LEN]}  {k.get('name', ''):<10}  {k.get('execution_state', ''):<10}  {k.get('last_activity', '')}"
        )
    return 0


def cmd_kernel_id(args, cfg, client: JupyterClient) -> int:
    st = state_mod.load(cfg.profile)
    if not st:
        out.error("no kernel state")
        return 1
    print(st["kernel_id"])
    return 0


def cmd_kernel_reset(args, cfg, client: JupyterClient) -> int:
    st = state_mod.load(cfg.profile)
    if st:
        _delete_kernel_state(cfg, client)
        print(f"deleted {st['kernel_id']}")
    else:
        print("no state")
    return 0


def cmd_sessions(args, cfg, client: JupyterClient) -> int:
    for s in client.list_sessions():
        sid = s.get("id", "")[:_ID_PREFIX_LEN]
        path = s.get("notebook", {}).get("path", s.get("path", ""))
        kid = s.get("kernel", {}).get("id", "")[:_ID_PREFIX_LEN]
        kname = s.get("kernel", {}).get("name", "")
        print(f"{sid}  {path:<40}  kernel:{kid}  {kname}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jl", description="Jupyter Lab CLI")
    p.add_argument("--profile", default="default")
    p.add_argument("--url")
    p.add_argument("--token")

    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("exec", help="Execute code in stateful kernel")
    e.add_argument("code")
    e.add_argument("--timeout", type=int, default=None)
    e.add_argument("--kernel-id", dest="kernel_id", default=None)
    e.add_argument("--fresh", action="store_true")

    r = sub.add_parser("run", help="Run notebook cell(s)")
    r.add_argument("notebook")
    r.add_argument("cell", type=int, nargs="?", default=None)
    r.add_argument("--timeout", type=int, default=None)

    rd = sub.add_parser("read", help="Read notebook cells")
    rd.add_argument("notebook")
    rd.add_argument("--format", choices=["brief", "full"], default="brief")
    rd.add_argument("--cells", type=int, default=100)

    ls = sub.add_parser("ls", help="List files")
    ls.add_argument("path", nargs="?", default="")
    ls.add_argument("--type", choices=["file", "directory", "notebook"], default=None)

    ul = sub.add_parser("upload", help="Upload local .ipynb and set as active notebook")
    ul.add_argument("local")
    ul.add_argument("remote", nargs="?", default=None)

    sts = sub.add_parser("steps", help="List steps (code cells, 1-based)")
    sts.add_argument("notebook", nargs="?", default=None)

    st = sub.add_parser("step", help="Run step N (1-based code cell)")
    st.add_argument("n", type=int)
    st.add_argument("notebook", nargs="?", default=None)
    st.add_argument("--timeout", type=int, default=None)

    sub.add_parser("kernels", help="List kernels")
    sub.add_parser("kernel-id", help="Print current kernel ID")
    sub.add_parser("kernel-reset", help="Delete current kernel and clear state")
    sub.add_parser("sessions", help="List sessions")

    return p


COMMANDS = {
    "exec": cmd_exec,
    "run": cmd_run,
    "read": cmd_read,
    "ls": cmd_ls,
    "upload": cmd_upload,
    "steps": cmd_steps,
    "step": cmd_step,
    "kernels": cmd_kernels,
    "kernel-id": cmd_kernel_id,
    "kernel-reset": cmd_kernel_reset,
    "sessions": cmd_sessions,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = config_mod.load(profile=args.profile, url=args.url, token=args.token)

    if hasattr(args, "timeout") and args.timeout is None:
        args.timeout = cfg.timeout

    if cfg.ssh_host:
        try:
            tunnel_mod.ensure(cfg.ssh_host, cfg.ssh_local_port, cfg.ssh_remote_port)
        except Exception as e:
            out.error(f"tunnel: {e}")
            sys.exit(2)

    client = JupyterClient(cfg.url, cfg.token)
    try:
        rc = COMMANDS[args.command](args, cfg, client)
        sys.exit(rc or 0)
    except JupyterError as e:
        out.error(str(e))
        sys.exit(2)
    except httpx.ConnectError as e:
        out.error(f"connection refused — is the tunnel up? ({e})")
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
    finally:
        client.close()
