#!/usr/bin/env bash
# run_all.sh — Run the full Astypalea iPOY data pipeline end to end.
#
# Usage:
#   cd ipoy/
#   bash scripts/run_all.sh
#
# Steps:
#   0. Create/activate virtualenv and install requirements
#   1. Download PDFs + RAAEY files (01_download.py)
#   2. Parse actual operations reports (03_parse_actual.py)
#   3. Parse forecast reports + RAAEY XLS (04_parse_forecast.py)
#   4. Parse monthly bulletins (05_parse_bulletins.py)
#   5. Run QA checks and generate figures (06_qa.py)
#
# Step 02_inspect.py is a development tool; run it manually.
# Re-running is safe: downloads are cached, CSVs are overwritten.

set -euo pipefail
cd "$(dirname "$0")/.."   # run from ipoy/ root

PYTHON="python3"
VENV=".venv"

# ── 0. Virtual environment ─────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"
echo "Installing/updating requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

PYTHON="$VENV/bin/python"

# ── 1. Download ────────────────────────────────────────────────────────────────
echo ""
echo "=== Step 1: Download ==="
$PYTHON scripts/01_download.py

# ── 2. Parse actuals ──────────────────────────────────────────────────────────
echo ""
echo "=== Step 2: Parse actual operations reports ==="
$PYTHON scripts/03_parse_actual.py

# ── 3. Parse forecasts ────────────────────────────────────────────────────────
echo ""
echo "=== Step 3: Parse forecast reports + RAAEY XLS ==="
$PYTHON scripts/04_parse_forecast.py

# ── 4. Parse bulletins ────────────────────────────────────────────────────────
echo ""
echo "=== Step 4: Parse monthly bulletins ==="
$PYTHON scripts/05_parse_bulletins.py

# ── 5. QA ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== Step 5: QA checks and figures ==="
$PYTHON scripts/06_qa.py

echo ""
echo "Pipeline complete."
echo "  Processed CSVs:  ipoy/data/processed/"
echo "  QA report:       ipoy/data/processed/QA_report.md"
echo "  Figures:         ipoy/data/processed/figures/"
echo ""
echo "Next: run 02_inspect.py on representative PDFs to verify"
echo "      parser assumptions match the actual layouts."
