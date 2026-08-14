#!/bin/bash
# AFTER-EDIT: daily_refresh.sh, wsl_startup_hook.sh (both call this; keep the stage list here ONLY)
#
# Auto-commit the pipeline's OWN regenerated tracked docs.
#
# Extracted from daily_refresh.sh 2026-08-14 so BOTH pipeline entry points share one
# stage list. Two entry points regenerate these files:
#   * daily_refresh.sh      — emits "Refresh complete"
#   * wsl_startup_hook.sh   — emits "Pipeline complete", and had NO git step at all,
#                             which is why 14 regenerated files kept reappearing dirty
#                             for the next agent (the "poisoned before starting" friction).
# The block was NOT duplicated into wsl_startup_hook.sh: its whole pipeline body lives
# inside a double-quoted `nohup bash -c "…"` string (:88-173), so an inlined block with
# quotes, $(…) and || would need fragile escaping AND would fork the stage list in two —
# the exact drift that let 65-rag-search.md and embedding_shortlists.json go unstaged.
#
# Contract: stage EXPLICIT pipeline-owned paths ONLY — never `git add -A` on shared master
# — commit only when something changed, then a GUARDED fast-forward push (never force; if
# origin diverged, leave the commit local for the next agent to integrate). Never fails:
# a git hiccup must not abort or fail the refresh, so every path exits 0.
#
# Usage: bash autocommit_pipeline_outputs.sh [caller-label]
set -u

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
CALLER="${1:-pipeline}"

cd "$FABRIK_ROOT" || exit 0

git add -- \
  .windsurf/rules/ai/*.md \
  .windsurf/rules/core/65-rag-search.md \
  docs/reference/kilo/CODING_SUBAGENT_SELECTION.md \
  docs/reference/kilo/TASK_SUBAGENT_SELECTION.md \
  docs/reference/kilo/KILO_MODEL_CAPABILITIES.md \
  docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md \
  docs/reference/kilo/TTS_SELECTION.md \
  docs/reference/kilo/STT_SELECTION.md \
  docs/reference/kilo/TRANSLATION_SELECTION.md \
  docs/reference/kilo/IMAGE_GEN_SELECTION.md \
  docs/reference/kilo/CANDIDATE_SIGNUPS.md \
  docs/CAPABILITIES.md capabilities.json \
  docs/traycer/kilo_selected_agents.md \
  scripts/kilo-benchmarks/embedding_models_dump.json \
  scripts/kilo-benchmarks/embedding_shortlists.json \
  2>/dev/null || true

# ⚠️ EXCLUSIONS — do not "helpfully" add these:
# LOCAL_LLM_INFRASTRUCTURE.md is deliberately NOT staged: the pipeline rewrites only its
# auto-generated block, but the file is MIXED (hand-authored prose above) — `git add` stages
# the whole file, so a cron add would bundle an agent's uncommitted manual edit (review finding).
# NEVER add shared agent-edited files here (PORTS.md, plan-locks, enforcement code): a cron
# staging those would bundle a live agent's WIP into its commit. If the refresh churns such a
# file (format sweep), the churn is the defect — stop touching it, don't auto-commit it.

if git diff --cached --quiet; then
  echo "[auto-commit] nothing regenerated changed — tree already clean"
  exit 0
fi

git commit -q \
  -m "chore(kilo): ${CALLER} auto-commit of regenerated selection docs + catalog ($(date -u +%Y-%m-%d))" \
  -m "Agent-Role: primary" \
  -m "Agent-Context: the pipeline commits its own regenerated tracked outputs so the working tree stays clean for the next agent" \
  -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  && echo "[auto-commit] committed" || { echo "[auto-commit] commit failed (non-fatal)"; exit 0; }

git fetch -q origin master 2>/dev/null || true
if git merge-base --is-ancestor origin/master HEAD 2>/dev/null; then
  git push -q origin master 2>/dev/null \
    && echo "[auto-commit] pushed to origin/master" \
    || echo "[auto-commit] push failed — commit left local (non-fatal)"
else
  echo "[auto-commit] origin/master diverged — commit left local for the next agent to integrate"
fi
exit 0
