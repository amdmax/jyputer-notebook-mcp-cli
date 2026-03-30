#!/usr/bin/env python3
"""Block direct git push to main/master — use a branch + PR instead."""
import json
import re
import sys

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

command = data.get("tool_input", {}).get("command", "")

if re.search(r"git\s+push\b.*\b(main|master)\b", command) or re.search(
    r"git\s+push\s+(?!.*--delete).*\b(origin|upstream)\b\s+(main|master)\b", command
):
    print("ERROR: direct push to main/master is not allowed. use a branch + pull request.", file=sys.stderr)
    sys.exit(2)
