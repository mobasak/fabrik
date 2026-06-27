#!/bin/bash
# Daily refresh of the AI model catalog. Cron-safe (no PATH assumptions,
# no shell activity required). Runs the full chain:
#   1. verify_openrouter_catalog.py --apply --ingest-new
#        → cross-checks the DB against live OpenRouter + Kilo CLI,
#          fixes prices, marks delisted, ingests new
#   2. classify_ai_category.py
#        → re-classifies all models into the 7 LLM packs
#   3. category_route_mapper.py
#        → re-picks today's openrouter:* route winners + history
#   4. category_export_markdown.py
#        → injects route blocks into .windsurf/rules/ai/*.md
#   5. export_models_browser.py
#        → regenerates the single-file models_browser.html
#
# Each step is wrapped in `|| echo "[step] failed (non-fatal)"` so a
# downstream failure can't short-circuit subsequent steps. Output goes
# to scripts/kilo-benchmarks/cache/update.log.
#
# Install (run once):
#   ( crontab -l 2>/dev/null; echo "0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh" ) | crontab -
#
# Manual run:
#   bash /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh

set -u
FABRIK_ROOT="/opt/fabrik"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
VENV_PY="$FABRIK_ROOT/.venv/bin/python"
KB="$FABRIK_ROOT/scripts/kilo-benchmarks"

# Make `kilo` CLI visible to cron (cron PATH is minimal).
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

mkdir -p "$(dirname "$LOG_FILE")"
{
  echo ""
  echo "=== Fabrik AI catalog refresh — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="

  cd "$KB" || { echo "[daily_refresh] cd failed — aborting"; exit 0; }

  "$VENV_PY" "$KB/verify_openrouter_catalog.py" --apply --ingest-new \
    || echo "[daily_refresh] verifier failed (non-fatal)"

  # Re-derive quality_tier + is_ga for every row (including the newly-
  # ingested ones with NULL benchmarks) — otherwise the category
  # selector's `quality_tier >= ?` floor silently drops them AND the
  # browser's default tier filter hides them.
  "$VENV_PY" "$KB/migrate_selector_columns.py" \
    || echo "[daily_refresh] selector columns migration failed (non-fatal)"

  "$VENV_PY" "$KB/classify_ai_category.py" \
    || echo "[daily_refresh] classifier failed (non-fatal)"

  "$VENV_PY" "$KB/category_route_mapper.py" \
    || echo "[daily_refresh] route mapper failed (non-fatal)"

  "$VENV_PY" "$KB/category_export_markdown.py" \
    || echo "[daily_refresh] markdown export failed (non-fatal)"

  "$VENV_PY" "$KB/export_models_browser.py" \
    || echo "[daily_refresh] models_browser export failed (non-fatal)"

  echo "=== Refresh complete — $(date -u +'%Y-%m-%d %H:%M:%S UTC') ==="
} >> "$LOG_FILE" 2>&1
