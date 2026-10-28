#!/usr/bin/env bash
# Every check CI runs, in one command. Run before each commit:  ./scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== lint (ruff)";   uv run ruff check
echo "== types (mypy)";  uv run mypy
echo "== tests + coverage (pytest, no network)"
uv run pytest -q --cov --cov-report=term
