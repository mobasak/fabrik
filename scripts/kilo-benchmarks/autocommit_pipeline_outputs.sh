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
#
# Contract: stage EXPLICIT pipeline-owned paths ONLY — never `git add -A` on shared master
# — commit only when something changed, then a GUARDED fast-forward push (never force; if
# origin diverged, leave the commit local for the next agent to integrate). Never fails:
# a git hiccup must not abort or fail the refresh, so every path exits 0.
#
# Usage: bash autocommit_pipeline_outputs.sh [caller-label]
set -u

# Resolved BEFORE the cd below: `dirname "$0"` is relative, so after `cd "$FABRIK_ROOT"`
# an invocation like `bash autocommit_pipeline_outputs.sh` from this directory resolved
# the helper to /opt/fabrik/pipeline_alert.sh, which does not exist — and the alert was
# then lost to `|| true`.
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
CALLER="${1:-pipeline}"

cd "$FABRIK_ROOT" || exit 0

# ⚠️ BAIL if the repo is mid-operation. `git add` on a conflicted path marks it RESOLVED —
# staging the file WITH its <<<<<<< markers. The commit then correctly fails ("cannot do a
# partial commit during a merge"), but the index damage PERSISTS: `git diff --diff-filter=U`
# (the standard "am I done?" check) reports clean, and the sibling's next commit writes conflict
# markers into master. Three concurrent agents plus a boot-triggered pipeline on one shared tree
# makes this reachable. Nothing this script does is urgent enough to touch a mid-merge index.
# ⚠️ NOT REBASE_HEAD: git leaves that ref in place after a CONFLICTED rebase COMPLETES — it is
# only cleared when the next rebase starts. CLAUDE.md's push ladder mandates
# `git pull --rebase=merges`, so the first agent to resolve a rebase conflict (a CHANGELOG
# [Unreleased] collision is the likeliest on this 3-agent tree) would have disabled this script
# FOREVER, silently: exit 0, message only in a log nobody tails, oracle still green, heartbeat
# still stamped. The rebase-merge/rebase-apply DIRECTORIES are cleared correctly, so they are
# the honest in-progress signal. Verified against git 2.43.
for _state in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
  if git rev-parse -q --verify "$_state" >/dev/null 2>&1; then
    echo "[auto-commit] repo is mid-operation ($_state) — refusing to touch the index"
    exit 0
  fi
done
for _dir in rebase-merge rebase-apply; do
  if [ -d "$(git rev-parse --git-path "$_dir" 2>/dev/null)" ]; then
    echo "[auto-commit] repo is mid-rebase ($_dir) — refusing to touch the index"
    exit 0
  fi
done
if [ -e "$(git rev-parse --git-path BISECT_LOG 2>/dev/null)" ]; then
  echo "[auto-commit] repo is mid-bisect — refusing to touch the index"
  exit 0
fi
if [ -n "$(git ls-files --unmerged 2>/dev/null)" ]; then
  echo "[auto-commit] unmerged paths present — refusing to touch the index"
  exit 0
fi

# Resolve the destination BEFORE staging. The guard moved above the COMMIT in round 15 but not
# above the ADD, so the detached path still left pipeline files staged and exited 0 — breaking
# this file's own "refusing to touch the index" contract and leaving content that rides along in
# the next bare commit.
# `git rev-parse --abbrev-ref HEAD` prints "HEAD" on stdout AND exits 128 on an UNBORN branch,
# so `|| echo HEAD` appended rather than substituted and _BRANCH became $'HEAD\nHEAD' — which
# is not equal to "HEAD", so this guard was bypassed and the log record split across two lines.
# Phase B stands up the engine repo with `git init` and no commits, so that is on our own path.
# symbolic-ref is empty on a real detached HEAD and correct on an unborn branch.
_BRANCH="$(git symbolic-ref --short -q HEAD || true)"
if [ -z "$_BRANCH" ]; then
  echo "[auto-commit] DETACHED HEAD — refusing to stage or commit onto no branch"
  exit 0
fi

# THE stage list. Defined once as an array because it is used THREE times below — add,
# emptiness-test and commit. Earlier this was a single `git add --` followed by a BARE
# `git commit`, which commits the WHOLE INDEX: a peer's staged WIP rode along, defeating the
# exclusion list two comments down. (CLAUDE.md § HARD STOPS: commit with a pathspec, never the
# index. A bare `final_gate.py` run auto-stages, so a non-empty index is the NORMAL state here.)
PATHS=(
  # ⚠️ REMOVED at the Phase-D cutover 2026-08-15: fabrik no longer INJECTS these blocks
  # (category_export_markdown/update_gateway_counts moved to the ai-model-catalog engine).
  # Staging a fleet-synced rule pack that this pipeline does not produce means a SIBLING's
  # uncommitted edit gets auto-committed and PUSHED to ~46 repos by the boot hook. The file's
  # own residual note accepted that risk only because "the pipeline must publish that block";
  # it no longer does, so the justification is gone and the risk is not.
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
)

# Add PER PATH, not in one call: `git add` is all-or-nothing, so ONE renamed/retired path (or an
# empty rules/ai glob, or running inside the Phase-B engine repo where most of these do not
# exist) made it exit 128 with NOTHING staged — and the guard below then logged "tree already
# clean", reporting success for a total no-op. Per-path keeps the other 15 working.
# A peer's `git commit` holds .git/index.lock for SECONDS here — its pre-commit governance-sync
# fans out to ~46 repos. Every `git add` then fails, and because their stderr is discarded the
# script blamed the stage list, no-op'd, and the daily lockfile blocked any retry until tomorrow.
# Detect the real cause and say so.
if [ -e "$(git rev-parse --git-path index.lock 2>/dev/null)" ]; then
  # A TRANSIENT lock (a peer mid-commit) is fine to skip silently-ish. A STALE one (crashed or
  # OOM-killed git — plausible on a memory-constrained WSL box whose pre-commit fans out to ~46
  # repos) never clears, so every later run no-ops forever with the message only in a log the
  # file's own comment says nobody tails: the round-16 REBASE_HEAD class again. Age it.
  _lock="$(git rev-parse --git-path index.lock)"
  _age=$(( $(date +%s) - $(stat -c %Y "$_lock" 2>/dev/null || date +%s) ))
  if [ "$_age" -gt 900 ]; then
    echo "[auto-commit] index.lock is ${_age}s old — STALE, not a peer mid-commit; the auto-commit is disabled until it is removed"
    bash "$SELF_DIR/pipeline_alert.sh" \
      "auto-commit: stale .git/index.lock is disabling the pipeline auto-commit" \
      "A .git/index.lock in /opt/fabrik is ${_age}s old — far longer than a peer's commit. It is almost certainly from a crashed or OOM-killed git. While it exists EVERY pipeline auto-commit no-ops silently and the tree stays dirty for the next agent. Remove it once you have confirmed no git process is running: rm /opt/fabrik/.git/index.lock" \
      || true
  else
    echo "[auto-commit] another git process holds the index lock — skipping this run (not a stage-list problem)"
  fi
  exit 0
fi

STAGED=()
for _p in "${PATHS[@]}"; do
  if git add -- "$_p" 2>/dev/null; then
    STAGED+=("$_p")
  elif [ -e "$(git rev-parse --git-path index.lock 2>/dev/null)" ]; then
    # The pre-loop guard is a point sample; a peer can take the lock DURING these ~26 adds and
    # the run then reported "a pipeline output was renamed or retired" — a false cause, plus a
    # partial commit. Re-check on failure so the real reason is named.
    # ⚠️ Deliberately NOT attempting `git reset` here: writing the index needs the very lock
    # whose presence triggered this branch, so the unstage is guaranteed to fail. An earlier
    # version called it anyway and logged "aborting and unstaging" — a claim it could never
    # satisfy, while up to 25 paths stayed staged in shared master. Say what is true, and
    # alert, because unlike the pre-loop guard this one leaves the index dirty.
    echo "[auto-commit] index lock appeared mid-stage — aborting with ${#STAGED[@]} path(s) STILL STAGED (cannot unstage: that needs the same lock)"
    bash "$SELF_DIR/pipeline_alert.sh" \
      "auto-commit: aborted mid-stage, paths left staged" \
      "A peer took .git/index.lock while the pipeline auto-commit was staging. ${#STAGED[@]} regenerated path(s) are left STAGED in the shared index and could ride along in the next bare commit. Unstaging is impossible from here (it needs the same lock). Run: git reset -- <the pipeline paths>, or just let the next pipeline run re-stage and commit them." \
      || true
    exit 0
  fi
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
# ⚠️ STATED RESIDUAL: `.windsurf/rules/**` ARE mixed in the same sense — hand-authored rule
# prose plus an injected GATEWAY_COUNTS/OPENROUTER_ROUTES block — and they ARE staged, because
# the pipeline must publish that block and there is no way to stage only part of a file. So a
# sibling mid-edit on a rule pack when the boot pipeline fires gets that edit committed AND
# fleet-synced. Unlike LOCAL_LLM_INFRASTRUCTURE.md this is unavoidable, not an oversight —
# recorded here so the next reader does not mistake it for one.
# NEVER add shared agent-edited files here (PORTS.md, plan-locks, enforcement code): a cron
# staging those would bundle a live agent's WIP into its commit. If the refresh churns such a
# file (format sweep), the churn is the defect — stop touching it, don't auto-commit it.

# Resolve the destination BEFORE committing. The detached-HEAD guard used to sit AFTER the
# commit, so it announced "will be lost at the next checkout" about a commit it had just made —
# and the tree was then clean, hiding the loss from the next agent.
# Scoped to OUR paths: an unscoped test fires whenever ANY file is staged, so the script would
# commit even when zero pipeline outputs changed.
if git diff --cached --quiet -- "${STAGED[@]}"; then
  echo "[auto-commit] nothing regenerated changed — tree already clean"
  exit 0
fi

# ONE -m for the trailer block: git parses only the LAST paragraph as trailers, so a -m per
# line left `git log --format='%(trailers:key=Agent-Role)'` empty on every pipeline commit since
# July — the exact query CLAUDE.md § Agent Provenance Trailers says the trailers exist for.
git commit -q \
  -m "chore(kilo): ${CALLER} auto-commit of regenerated selection docs + catalog ($(date -u +%Y-%m-%d))" \
  -m "Agent-Role: primary
Agent-Context: the pipeline commits its own regenerated tracked outputs so the working tree stays clean for the next agent
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- "${STAGED[@]}" \
  && echo "[auto-commit] committed" || {
    # The ONLY bail-out that used to leave the index dirty. Every other path says "refusing to
    # touch the index" and means it. Here up to 26 pipeline paths stayed STAGED in the shared
    # master index, every day, and because the script exits 0 the caller's `|| echo ... errored`
    # can never fire — so a persistently failing pre-commit hook (this repo has two MODIFYING
    # hooks plus forbid-secrets and governance-sync) disables the auto-commit forever, silently.
    # That is the round-16 REBASE_HEAD class on a path with no ref to grep for.
    # ⚠️ `git reset -- <paths>` restores the index to HEAD, NOT to the pre-run index. If a peer
    # had one of OUR paths staged, this unstages it. Their content is already gone by then (the
    # `git add` above overwrote it) and is recoverable from the worktree, so this is the least
    # bad option — but it is not "leaving the index as we found it", and saying so would be the
    # kind of comment-drift that produced the round-17 bug.
    echo "[auto-commit] commit failed — unstaging our paths (note: git reset restores them to HEAD, not to whatever was staged before this run)"
    git reset -q -- "${STAGED[@]}" 2>/dev/null || true
    bash "$SELF_DIR/pipeline_alert.sh" \
      "auto-commit: git commit failed on $(hostname 2>/dev/null || echo this host)" \
      "The pipeline auto-commit could not commit its regenerated outputs (most likely a failing pre-commit hook). Our paths were unstaged so the shared index is unchanged, but the regenerated files remain UNCOMMITTED and the tree stays dirty for the next agent. If this repeats, the auto-commit is effectively disabled — check the pre-commit hooks first." \
      || true
    exit 0
  }

BRANCH="$_BRANCH"
# Detached HEAD returns the literal "HEAD": the commit lands on no branch and is dropped at the
# next checkout, so say that rather than the misleading "diverged" the generic path prints.
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
