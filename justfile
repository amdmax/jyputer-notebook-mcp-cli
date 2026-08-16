python := ".venv/bin/python"

fmt:
    {{python}} -m black .

fmt-check:
    {{python}} -m black --check .

lint:
    {{python}} -m ruff check .

smoke:
    {{python}} -c "import jl.cli"

test: smoke
    {{python}} -m pytest

build:
    uv build

check: fmt lint
