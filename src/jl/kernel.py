"""Jupyter kernel execution via WebSocket (Jupyter messaging protocol)."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field

import websockets

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class ExecutionResult:
    outputs: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    error: str | None = None


def _build_request(msg_id: str, code: str) -> str:
    return json.dumps(
        {
            "header": {
                "msg_id": msg_id,
                "msg_type": "execute_request",
                "username": "jl",
                "session": msg_id,
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False,
            },
            "channel": "shell",
        }
    )


async def _execute_async(
    kernel_id: str,
    code: str,
    url: str,
    token: str,
    timeout: int,
) -> ExecutionResult:
    ws_url = f"{url.replace('http', 'ws')}/api/kernels/{kernel_id}/channels"
    if token:
        ws_url += f"?token={token}"

    msg_id = str(uuid.uuid4())
    result = ExecutionResult()

    async with websockets.connect(ws_url) as ws:
        await ws.send(_build_request(msg_id, code))

        async with asyncio.timeout(timeout):
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue

                msg_type = msg.get("msg_type", "")
                content = msg.get("content", {})

                if msg_type == "stream":
                    result.outputs.append(content.get("text", ""))

                elif msg_type == "execute_result":
                    txt = content.get("data", {}).get("text/plain", "")
                    if txt:
                        result.outputs.append(txt)

                elif msg_type == "display_data":
                    data = content.get("data", {})
                    if png := data.get("image/png"):
                        result.images.append(png)
                    elif txt := data.get("text/plain"):
                        result.outputs.append(txt)

                elif msg_type == "error":
                    tb = content.get("traceback", [])
                    result.error = "\n".join(_ANSI.sub("", line) for line in tb)

                elif msg_type == "status":
                    if content.get("execution_state") == "idle":
                        break

    return result


def execute(
    kernel_id: str,
    code: str,
    url: str,
    token: str,
    timeout: int = 120,
) -> ExecutionResult:
    return asyncio.run(_execute_async(kernel_id, code, url, token, timeout))
