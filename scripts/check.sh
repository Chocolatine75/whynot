#!/usr/bin/env bash
# Every check CI runs, in one command. Run before each commit:  ./scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== lint (ruff)";   uv run ruff check
echo "== types (mypy)";  uv run mypy
echo "== tests + coverage (pytest, no network)"
uv run pytest -q -n auto --cov --cov-report=term  # parallel: ~25 s instead of ~95 s
if [ -d web/node_modules ]; then
  echo "== web: types + tests"
  (cd web && npm run -s typecheck && npm test --silent)
fi
