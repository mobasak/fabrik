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

# ⚠️ BAIL if the repo is mid-operation. `git add` on a conflicted path marks it RESOLVED —
# staging the file WITH its <<<<<<< markers. The commit then correctly fails ("cannot do a
# partial commit during a merge"), but the index damage PERSISTS: `git diff --diff-filter=U`
# (the standard "am I done?" check) reports clean, and the sibling's next commit writes conflict
# markers into master. Three concurrent agents plus a boot-triggered pipeline on one shared tree
# makes this reachable. Nothing this script does is urgent enough to touch a mid-merge index.
for _state in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
  if git rev-parse -q --verify "$_state" >/dev/null 2>&1 || [ -e "$(git rev-parse --git-path "$_state" 2>/dev/null)" ]; then
    echo "[auto-commit] repo is mid-operation ($_state) — refusing to touch the index"
    exit 0
  fi
done
if [ -n "$(git ls-files --unmerged 2>/dev/null)" ]; then
  echo "[auto-commit] unmerged paths present — refusing to touch the index"
  exit 0
fi

# THE stage list. Defined once as an array because it is used THREE times below — add,
# emptiness-test and commit. Earlier this was a single `git add --` followed by a BARE
# `git commit`, which commits the WHOLE INDEX: a peer's staged WIP rode along, defeating the
# exclusion list two comments down. (CLAUDE.md § HARD STOPS: commit with a pathspec, never the
# index. A bare `final_gate.py` run auto-stages, so a non-empty index is the NORMAL state here.)
PATHS=(
  .windsurf/rules/ai/*.md
  .windsurf/rules/core/65-rag-search.md
  docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
  docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
  docs/reference/kilo/KILO_MODEL_CAPABILITIES.md
  docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md
  docs/reference/kilo/TTS_SELECTION.md
  docs/reference/kilo/STT_SELECTION.md
  docs/reference/kilo/TRANSLATION_SELECTION.md
  docs/reference/kilo/IMAGE_GEN_SELECTION.md
  docs/reference/kilo/CANDIDATE_SIGNUPS.md
  docs/CAPABILITIES.md
  capabilities.json
  docs/traycer/kilo_selected_agents.md
  scripts/kilo-benchmarks/embedding_models_dump.json
  scripts/kilo-benchmarks/embedding_shortlists.json
)

# Add PER PATH, not in one call: `git add` is all-or-nothing, so ONE renamed/retired path (or an
# empty rules/ai glob, or running inside the Phase-B engine repo where most of these do not
# exist) made it exit 128 with NOTHING staged — and the guard below then logged "tree already
# clean", reporting success for a total no-op. Per-path keeps the other 15 working.
STAGED=()
for _p in "${PATHS[@]}"; do
  if git add -- "$_p" 2>/dev/null; then STAGED+=("$_p"); fi
done
if [ ${#STAGED[@]} -eq 0 ]; then
  echo "[auto-commit] no pipeline paths matched — nothing to stage (check the stage list)"
  exit 0
fi
if [ ${#STAGED[@]} -ne ${#PATHS[@]} ]; then
  echo "[auto-commit] WARNING: ${#STAGED[@]}/${#PATHS[@]} stage paths matched — a pipeline output was renamed or retired"
fi

# ⚠️ EXCLUSIONS — do not "helpfully" add these:
# LOCAL_LLM_INFRASTRUCTURE.md is deliberately NOT staged: the pipeline rewrites only its
# auto-generated block, but the file is MIXED (hand-authored prose above) — `git add` stages
# the whole file, so a cron add would bundle an agent's uncommitted manual edit (review finding).
# NEVER add shared agent-edited files here (PORTS.md, plan-locks, enforcement code): a cron
# staging those would bundle a live agent's WIP into its commit. If the refresh churns such a
# file (format sweep), the churn is the defect — stop touching it, don't auto-commit it.

# Resolve the destination BEFORE committing. The detached-HEAD guard used to sit AFTER the
# commit, so it announced "will be lost at the next checkout" about a commit it had just made —
# and the tree was then clean, hiding the loss from the next agent.
_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
if [ "$_BRANCH" = "HEAD" ]; then
  echo "[auto-commit] DETACHED HEAD — refusing to commit onto no branch (it would be lost at the next checkout)"
  exit 0
fi

# Scoped to OUR paths: an unscoped test fires whenever ANY file is staged, so the script would
# commit even when zero pipeline outputs changed.
if git diff --cached --quiet -- "${STAGED[@]}"; then
  echo "[auto-commit] nothing regenerated changed — tree already clean"
  exit 0
fi

git commit -q \
  -m "chore(kilo): ${CALLER} auto-commit of regenerated selection docs + catalog ($(date -u +%Y-%m-%d))" \
  -m "Agent-Role: primary" \
  -m "Agent-Context: the pipeline commits its own regenerated tracked outputs so the working tree stays clean for the next agent" \
  -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- "${STAGED[@]}" \
  && echo "[auto-commit] committed" || { echo "[auto-commit] commit failed (non-fatal)"; exit 0; }

BRANCH="$_BRANCH"
# Detached HEAD returns the literal "HEAD": the commit lands on no branch and is dropped at the
# next checkout, so say that rather than the misleading "diverged" the generic path prints.
if [ "$BRANCH" = "HEAD" ]; then
  echo "[auto-commit] DETACHED HEAD — commit is on no branch and will be lost at the next checkout"
  exit 0
fi
if ! git rev-parse --verify -q "origin/$BRANCH" >/dev/null 2>&1; then
  echo "[auto-commit] no origin/$BRANCH — commit left local (not a divergence)"
  exit 0
fi
git fetch -q origin "$BRANCH" 2>/dev/null || true
if git merge-base --is-ancestor "origin/$BRANCH" HEAD 2>/dev/null; then
  git push -q origin "$BRANCH" 2>/dev/null \
    && echo "[auto-commit] pushed to origin/$BRANCH" \
    || echo "[auto-commit] push failed — commit left local (non-fatal)"
else
  echo "[auto-commit] origin/$BRANCH diverged — commit left local for the next agent to integrate"
fi
exit 0
