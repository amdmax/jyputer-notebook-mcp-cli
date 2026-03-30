# jl — Jupyter Lab CLI

## Problem

When Claude Code interacts with a remote Jupyter server via `jupyter-mcp-server`, every context window carries the full MCP tool schema (16 tools) plus round-trip overhead per operation. On long sessions this wastes thousands of tokens and adds latency.

`jl` replaces the MCP entirely with a thin CLI. Claude calls `jl exec "..."` via Bash — one tool call, no schema, no protocol overhead.

## MCP replaced

[`jupyter-mcp-server`](https://github.com/datalayer/jupyter-mcp-server) — the Datalayer MCP server for Jupyter Lab. `jl` communicates directly with the Jupyter REST API and kernel WebSocket, bypassing MCP completely.

## Dependencies

**Runtime** (installed automatically via `uv tool install .`):
- Python ≥ 3.11
- [`httpx`](https://www.python-httpx.org/) — Jupyter REST API calls
- [`websockets`](https://websockets.readthedocs.io/) — kernel execution via Jupyter messaging protocol

**System:**
- `uv` — for installation (`brew install uv`)
- `ssh` — for ControlMaster tunnel to remote Jupyter servers

**Jupyter server** (remote or local):
- Jupyter Lab running and reachable
- A valid server token

## Install

```bash
uv tool install .
```

## Quickstart

```bash
# configure
cat > ~/.config/jl/config.toml <<EOF
[default]
url = "http://localhost:8888"
token = "your_token_here"
EOF

# or via env vars
export JUPYTER_URL=http://localhost:8888
export JUPYTER_TOKEN=your_token_here

# use
jl exec "import torch; print(torch.cuda.is_available())"
jl upload my_notebook.ipynb
jl steps
jl step 2
jl step 3 --timeout 300
```

## Commands

| Command | Description |
|---------|-------------|
| `exec "<code>"` | Run code in stateful kernel (variables persist) |
| `upload <local> [remote]` | Upload `.ipynb`, set as active notebook |
| `steps` | List notebook code cells as 1-based steps |
| `step <N>` | Run step N |
| `run <notebook> [cell]` | Run all cells or one by absolute index |
| `read <notebook>` | Print cell sources |
| `ls [path]` | List remote files |
| `kernels` | List running kernels |
| `kernel-reset` | Delete current kernel, clear state |
| `sessions` | List sessions |

## Remote server (SSH tunnel)

```toml
# ~/.config/jl/config.toml
[default]
url = "http://localhost:18888"
token = "your_token_here"
ssh_host = "my-gpu-server"
ssh_local_port = 18888
ssh_remote_port = 8888
```

`jl` manages the ControlMaster socket automatically — the tunnel is opened once and reused across calls.
