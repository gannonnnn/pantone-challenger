#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Pantone Challenger requires Python 3.11 or newer.")
print("Using Python", sys.version.split()[0])
PY

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
challenger doctor
pytest

cat <<'EOF'

Pantone Challenger is installed.

Activate it later with:
  source .venv/bin/activate

Run the real panel with:
  challenger run --date auto

The first production launch is documented in:
  docs/launch.md
EOF
