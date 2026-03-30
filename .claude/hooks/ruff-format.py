#!/usr/bin/env python3
import json
import subprocess
import sys

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

if file_path.endswith(".py"):
    subprocess.run(["uvx", "ruff", "format", "--quiet", file_path])
