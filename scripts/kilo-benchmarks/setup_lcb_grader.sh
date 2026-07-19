#!/bin/bash
# AFTER-EDIT: scripts/kilo-benchmarks/microbench_coding_direct.py | none
# Provision the LiveCodeBench GRADING-ONLY sibling venv for microbench_coding_direct.py.
# Idempotent — safe to re-run. Both .lcb-src and .lcb-venv are gitignored (rebuilt, never committed).
#
# WHY grading-only: LiveCodeBench declares torch>=2.3 + vllm (multi-GB, GPU) for its GENERATION path,
# which we don't use (we generate via OpenRouter). We need only lcb_runner.evaluation.codegen_metrics,
# which imports just numpy/tqdm/datasets. So: install the package --no-deps + that light subset.
# ⚠️ datasets<3.0 is REQUIRED: code_generation_lite is a script dataset loaded with trust_remote_code=True,
# and datasets>=3.0 dropped BOTH — despite lcb's own pyproject pinning datasets>=3.2.0 (a lcb inconsistency).
set -u
KB="$(cd "$(dirname "$0")" && pwd)"
SRC="$KB/.lcb-src"
VENV="$KB/.lcb-venv"

echo "[lcb-setup] target: $VENV"
if [ ! -d "$SRC/lcb_runner" ]; then
  echo "[lcb-setup] cloning LiveCodeBench (code only, ~8MB)..."
  rm -rf "$SRC"
  git clone --depth 1 https://github.com/LiveCodeBench/LiveCodeBench "$SRC" || { echo "[lcb-setup] clone FAILED"; exit 1; }
else
  echo "[lcb-setup] .lcb-src present — skipping clone"
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "[lcb-setup] creating venv..."
  python3 -m venv "$VENV" || { echo "[lcb-setup] venv FAILED"; exit 1; }
fi

echo "[lcb-setup] installing lcb_runner --no-deps + grading subset (numpy tqdm 'datasets<3.0')..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e "$SRC" --no-deps
"$VENV/bin/pip" install -q numpy tqdm 'datasets<3.0'

echo "[lcb-setup] verifying the grader imports torch/vllm-free..."
if "$VENV/bin/python" -c "from lcb_runner.evaluation import codegen_metrics, extract_instance_results" 2>/dev/null; then
  echo "[lcb-setup] OK — grader ready. datasets=$("$VENV/bin/python" -c 'import datasets;print(datasets.__version__)')"
  echo "[lcb-setup] next: python microbench_coding_direct.py --probe   # size cost, then --all"
else
  echo "[lcb-setup] FAILED — grader import errored (check datasets<3.0 + the clone)"; exit 1
fi
