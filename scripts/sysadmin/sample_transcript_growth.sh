#!/usr/bin/env bash
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/superpowers/specs/2026-09-05-session-history-retention-design.md
# sample_transcript_growth.sh — Phase 0 of the session-history retention plan.
#
# WHY THIS EXISTS
#   The plan sets a 90-day window for MAIN transcripts but deliberately does NOT fix the
#   size cap, because the growth rate is genuinely unknown: MAIN was 0.61 GB across all of
#   August and 4.89 GB in the first five days of September. That is the difference between
#   a ~2 GB and a ~90 GB window, and a number invented today would have been the fifth
#   confident guess in this work's history — the previous four were all refuted by reading
#   code. So: measure for 14 days, THEN derive.
#
# WHAT IT RECORDS, one TSV row per day:
#   date · main_bytes · main_files · largest_bytes · largest_path
#
#   `largest_*` is not decoration. The aggregate bound cannot see a runaway session: the
#   largest transcript measured was 696.5 MB and 50% of all bytes live in the top 14 files,
#   so a single 10 GB session would sit comfortably under a 90 GB aggregate while filling
#   the disk on its own. The plan's cap is therefore TWO bounds, and this column is what
#   the per-file one is derived from.
#
# THE PREDICATE IS THE SPEC'S, NOT A NEW ONE
#   `! -path '*/subagents/*'` — subagent transcripts are a separate tier (7 days, no
#   archive) and must never be counted into the MAIN series. Changing this predicate
#   silently changes what every derived bound means.
#
# IDEMPOTENT BY DAY: a second run on the same date is a no-op, so a cron retry, a manual
# run, or an @reboot catch-up can never double-count a day into the series the cap is
# derived from.
#
# DELETES NOTHING. Reads only.
set -euo pipefail

PROJECTS="${CLAUDE_PROJECTS_DIR:-$HOME/.claude/projects}"
LOG="${TRANSCRIPT_GROWTH_LOG:-$HOME/.claude/state/transcript-growth.tsv}"

mkdir -p "$(dirname "$LOG")"
if [ ! -s "$LOG" ]; then
  printf 'date\tmain_bytes\tmain_files\tlargest_bytes\tlargest_path\n' > "$LOG"
fi

today=$(date +%F)
# Idempotence: exact field match on column 1, never a substring — a date is a prefix of
# nothing else here today, but `grep -q "$today"` would also match a path containing it.
if awk -F'\t' -v d="$today" 'NR>1 && $1==d {found=1} END{exit !found}' "$LOG"; then
  echo "sample_transcript_growth: $today already recorded — no-op"
  exit 0
fi

if [ ! -d "$PROJECTS" ]; then
  echo "sample_transcript_growth: projects dir not found: $PROJECTS" >&2
  exit 1
fi

# One find, two consumers: totals and the largest single file. Running find twice would
# sample two different instants of a store that grows while you read it.
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
find "$PROJECTS" -name '*.jsonl' ! -path '*/subagents/*' -printf '%s\t%p\n' > "$tmp"

read -r bytes files < <(awk -F'\t' '{t+=$1; n++} END{printf "%d %d\n", t+0, n+0}' "$tmp")
read -r lbytes lpath < <(sort -rn -k1,1 "$tmp" | head -1 | awk -F'\t' '{printf "%d %s\n", $1+0, $2}')

printf '%s\t%s\t%s\t%s\t%s\n' "$today" "$bytes" "$files" "${lbytes:-0}" "${lpath:--}" >> "$LOG"
printf 'sample_transcript_growth: %s  main=%s bytes / %s files  largest=%s bytes\n' \
  "$today" "$bytes" "$files" "${lbytes:-0}"
