#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run.sh — One-command wrapper for the ctd-cast-processor pipeline.
#
# Usage:
#   ./run.sh                          # Process all CNV in sample_data/raw/
#   ./run.sh data/my_cruise/raw/      # Custom input directory
#   ./run.sh --no-plots               # Skip plot generation
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

INPUT_DIR="${1:-sample_data/raw}"
EXTRA_FLAGS="${@:2}"

echo "=============================================="
echo " ctd-cast-processor"
echo "=============================================="
echo " Input : ${INPUT_DIR}"
echo ""

# Verify package is installed
if ! command -v ctd-processor &>/dev/null; then
    echo "[ERROR] ctd-processor command not found."
    echo "        Run: pip install -e '.[dev]'"
    exit 1
fi

# Generate sample data if directory is empty or first CNV missing
if [ "${INPUT_DIR}" = "sample_data/raw" ] && [ ! -f "${INPUT_DIR}/cast_001.cnv" ]; then
    echo "[INFO] Generating synthetic sample CTD data..."
    python sample_data/generate_sample_cnv.py
fi

# Run batch processing
echo "[INFO] Processing all CNV files in ${INPUT_DIR}..."
ctd-processor batch "${INPUT_DIR}" \
    --output output/ \
    ${EXTRA_FLAGS}

echo ""
echo "=============================================="
echo " Pipeline complete. Results saved to output/"
echo "=============================================="
