# T09 — The run-record protocol doc and the event-stream doc carry `--confirmed` and the confirmed-based TERMINAL rule

## Scope
Document the run-record contract T10 implements (spec D7 third bullet, docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md:172; DD8 `:275`; V3 `:234`), so the two docs land BEFORE the code and T10's `/fabrik-docs-review` proves them against it (no gate reads a doc against its code — `check_doc_sync.py` is touch-on-change and keys on its five `SIGNIFICANT_DIRS` — `src/`, `scripts/`, `templates/`, `.factory/`, `.github/` — so a docs-only change grades nothing and a doc ahead of its code trips nothing): (1) `docs/reference/command-run-protocol.md` — the `round` row at `:55` gains `[--confirmed <N>]` and its meaning ("counts the candidates CONFIRMED by execution in that pass; when stated on the LAST round it is the exit counter — TERMINAL fires on `confirmed == 0` with every class swept; when no round states it the `--findings 0` rule stands; a pass with `--findings > 0` and no `--confirmed` under a command whose earlier rounds stated it draws a stderr warning"), the abbreviation note at `:62-65` names `--confirmed` (an abbreviated `--conf` now resolves to it), the TERMINAL sentence at `:113-114` states the confirmed rule and the old fallback, the example record's `rounds` entry at `:29` carries `"confirmed": 0`, the class-ledger bullets at `:110-115`, the exits line at `:316` and the test inventory at `:405` agree (the events line at `:152` is a verb→event mapping with no field list and stays as it is — the field list lives in the kaizen doc, one source of truth); the oscillation advisory reads the `confirmed` series when every round states it and the `findings` series otherwise (DD8); the `FEEDBACK:` trend shows the `confirmed` series when present. (2) `docs/workstation/kaizen-event-stream.md:115` — the `round` event's field list gains `confirmed` (int, absent when not stated). Every sentence describes the contract in the present tense as T10 ships it; nothing describes today's `findings`-only banner. DO-NOT: touch `scripts/command_run.py` or its tests (T10); describe a schema validator or a `--json` reader change (none exists, none is added); change any other row of the protocol doc; touch the doc's rendered `## Related scripts` block (`:413-422`, rendered from `command_run.py`'s header — every edit above sits at or before `:405`).

Depends: —
Parallel: ⚡
Complexity: simple
Gate: python3 -c 'import sys,re; p=open("docs/reference/command-run-protocol.md",encoding="utf-8").read(); k=open("docs/workstation/kaizen-event-stream.md",encoding="utf-8").read(); ok=("--confirmed" in p and "confirmed == 0" in p and re.search(r"\| `round` \|[^\n]*`confirmed`", k)); print("docs carry --confirmed:", bool(ok)); sys.exit(0 if ok else 1)'
Docs: `docs/reference/command-run-protocol.md` and `docs/workstation/kaizen-event-stream.md` (Touches); CHANGELOG entry (Deltas)

## Touches
- docs/reference/command-run-protocol.md — PRIMARY PATH
- docs/workstation/kaizen-event-stream.md

## Behavior Contract
- **Given** `docs/reference/command-run-protocol.md` after this ticket, **When** read, **Then** the `round` row carries `--confirmed` with its exit-counter meaning, the TERMINAL sentence at `:113` states the confirmed rule and the `--findings 0` fallback, and the example record's round at `:29`, the lines `:62-65`, `:110-115`, `:316`, `:405` agree with it (docs/reference/command-run-protocol.md:55, :113)
- **Given** `docs/workstation/kaizen-event-stream.md`, **When** read, **Then** the round event's field list at `:115` carries `confirmed` (docs/workstation/kaizen-event-stream.md:115)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/reference/command-run-protocol.md
- docs/workstation/kaizen-event-stream.md
- docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md

## Implementation notes
- The spec's rule is one bullet (`:172`); `sed -n '172p'` it. The `_loop_shaped` nudge, the ledger row and the banner wording are T10's code; this ticket documents their contract, T10's docs-review reconciles any drift.
- The Gate line is single-quoted for the shell so the backticks inside the regex reach Python untouched (a double-quoted form runs `` `round` `` as a command); it exits 1 today and 0 once both docs carry the contract.
- `command_run.py`'s `# AFTER-EDIT:` header names the protocol doc as coupled; the reverse coupling (`## Related scripts` block) is rendered by `render_doc_script_links.py` from the header — never hand-edit that block.
