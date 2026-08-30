# Decisions

Append-at-top. One row per decision; rows are IMMUTABLE — a changed decision gets a NEW row whose
what-cell opens "supersedes D-NNN:"; the old row is never edited. WHY ≤ 2 lines; the full rationale
lives at the WHERE links (commit shas · paths · spec/plan/mail ids). What counts as a decision: an
operator ruling · a spec/plan approval or Status flip · a retirement/adoption (tool, vendor, pattern,
module) · an architecture/storage/scope choice · "we built X, it lives at Y" · a rejected option
worth not re-proposing. NOT a decision: routine fixes, refactors, doc edits — those are CHANGELOG's.
Subagents and the pipeline never hold the pen — the dispatching session appends. Query: grep this
file first; fleet-wide from the hub: `python3 /opt/fabrik/scripts/decisions.py <term>`.

| id | when | who | what (the decision) | why | where |
|---|---|---|---|---|---|
| D-000 | {{date}} | operator | decision ledger adopted in this repo (scaffolded) | every decision queryable with why/what/where/who/when — no more reconstruction hunts | /opt/fabrik docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md |
