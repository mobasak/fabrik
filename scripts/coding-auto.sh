#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# Kilo Agent — CODING-AUTO (auto-classifier)
# ════════════════════════════════════════════════════════════════════════════
#
# This wrapper is the Traycer entry point that uses the deterministic
# classifier instead of a hardcoded model. The ticket prompt comes in via
# $TRAYCER_PROMPT (or $TRAYCER_PROMPT_TMP_FILE), gets classified into
# coding_simple or coding_complex by classify_ticket.py, and is dispatched
# to the cheapest qualified model meeting the role's quality + speed floors.
#
# This file lives at /opt/fabrik/scripts/coding-auto.sh as the source of
# truth. It is auto-installed to ~/.traycer/cli-agents/coding-auto.sh by
# generate_kilo_agents.py (see STATIC_HELPER_SCRIPTS in that file), so it
# survives the atomic orphan-cleanup that wipes everything not in the list
# of role-priority agent scripts.
#
# Fabrik scaffold does NOT copy this to other /opt/* projects — the file
# stays in /opt/fabrik/scripts/ only, and the runtime path resolution
# below points back to /opt/fabrik regardless of the calling project.
#
# How Traycer picks this:
#     Either reference it by filename in your Traycer routing config, or add
#     an entry to scripts/kilo_47_agents_final.json. The script spans both
#     coding_simple and coding_complex by design — it doesn't fit the
#     per-role priority slot model.
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail

FABRIK_ROOT="/opt/fabrik"
DISPATCHER="$FABRIK_ROOT/scripts/kilo_auto_route.py"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
PYTHON="${VENV_PYTHON:-python3}"
[ -x "$VENV_PYTHON" ] || PYTHON="python3"

# Resolve prompt input — Traycer can pass via env var or temp file.
if [ -n "${TRAYCER_PROMPT_TMP_FILE:-}" ] && [ -f "$TRAYCER_PROMPT_TMP_FILE" ]; then
    PROMPT="$(cat "$TRAYCER_PROMPT_TMP_FILE")"
else
    PROMPT="${TRAYCER_PROMPT:-}"
fi

if [ -z "$PROMPT" ]; then
    echo "[coding-auto] ERROR: no prompt (set TRAYCER_PROMPT or TRAYCER_PROMPT_TMP_FILE)" >&2
    exit 2
fi

TICKET_ID="${TRAYCER_TASK_ID:-adhoc-$(date +%s)-$$}"

# Optional: caller may export TRAYCER_ESTIMATED_FILES / TRAYCER_ESTIMATED_LINES
# to give the classifier hard-rule inputs. Defaults handle missing values.
FILES="${TRAYCER_ESTIMATED_FILES:-1}"
LINES="${TRAYCER_ESTIMATED_LINES:-0}"

# Use first line of the prompt as the title for keyword matching.
TITLE="$(printf '%s' "$PROMPT" | head -n 1)"

# Dispatch — the auto-router classifies, picks the model, runs kilo, and
# writes the ticket_outcomes row. Prompt is piped on stdin so the dispatcher
# reads it cleanly without quoting issues.
exec "$PYTHON" "$DISPATCHER" \
    --ticket-id "$TICKET_ID" \
    --title "$TITLE" \
    --files "$FILES" \
    --lines "$LINES" \
    --auto-classify <<< "$PROMPT"
