# Prompt audit of the governance sources — 2026-10-05

**Requested by:** operator question 2026-09-30, routed as fabrik mail 01M3RQ7G6ZM8H1B66VJG93S32B (W-e44ab7d8), with the ordering rule in 01M3RQE2C4D3B81KRR2A5K94ND (W-a247f908).
**Method:** Anthropic's `/claude-api prompt-audit` skill (`shared/prompt-audit.md`, md5 `aebf35fc81d88fa26215a6c822b6ec5b`), Steps 3–5, run by 11 read-only seats over pinned copies at commit `52e1092fc`. Target model: Claude Opus 5.5 / Fable 5.1.
**House limits on every proposed cut:** D-330 (no rule lost, no byte-cut for its own sake) and D-331 (each cut names what the text did and shows the remaining text still does it). Lines that carry a D-id, a dated incident, a mail id or a measured count are incident guards and stay (the skill's keep-list item 5).
**Status:** PROPOSAL. Nothing in the corpus was edited by this audit. The skill is propose-only, and the style changes below wait for the operator's consent. The factual corrections are defects, tracked separately (see § What happens next).

## Scope — sources only

Per the ordering rule, only the SOURCES were audited, never a rendered or synced copy:

| Unit | Surface | Files | Lines | Seat |
|---|---|---|---|---|
| U1 | `CLAUDE.md` (hub contract) | 1 | 634 | Opus |
| U2 | `templates/governance/CLAUDE.md` (synced to ~46 repos) | 1 | 637 | Opus |
| U3 | `commands/_fragments/*.md` | 28 | 897 | Sonnet |
| C1–C4 | `commands/_sources/*.md` | 38 | 12,732 | Sonnet ×4 |
| R1–R4 | `.windsurf/rules/**/*.md` | 57 | 19,635 | Sonnet ×4 |

Coverage caveat, stated by the seats: the largest files were swept with the skill's signal greps and every hit read in context, not read line by line — `tojlo-design-system.md` (R1), `design-system-template.md`, `72-desktop.md`, `89-mobile-launch-checklist.md`, `60-saas-ui.md` (R2), `58-resilience.md`, `76-gpu-workers.md` (R4), and parts of `fabrik-vision.md`, `fabrik-spec.md`, `fabrik-deploy-verify.md` (C2).

## Result in one paragraph

The corpus is already in the register the skill asks for. Across 125 files and ~34,500 lines the seats found no API-replaceable scaffolds (no think-step-by-step, scratchpad tags, prefill, sampling parameters, word caps or tool-call cadences), no retired model names in instructions, no identity stubs substituting for context and no grader vocabulary. Almost every emphatic line carries its provenance. Six units came back clean. What the audit did find falls into two kinds: **factual errors** — text describing code that has since changed — and **volume or wording** changes on a handful of lines with no provenance.

## A — Factual errors (defects; fix through review)

Each was executed against the code at `52e1092fc` and re-verified on 2026-10-05.

| id | where | what is wrong | evidence |
|---|---|---|---|
| U2-1 | `templates/governance/CLAUDE.md:82` | The `setup-error` remedy says to install `ruff mypy bandit` or "run the gate with an interpreter that has them". The gate requires `ruff` (as a binary) and `pytest` (importable), and always uses `.venv/bin/python` when `.venv` exists, so the remedy omits pytest and its second option cannot work. It also contradicts the same file's line 228. | `scripts/final_gate.py:71,80,87` — `VENV_PYTHON`, `PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable`, `REQUIRED_TOOLS = ("ruff", "pytest")` |
| U1-1 | `CLAUDE.md` HARD STOPS, `git add -A` row; the same sentence at `templates/governance/CLAUDE.md:273` | "After the gate auto-stages on success, `git reset` then re-add only your files." The gate no longer blanket-stages: by default it re-stages only the paths already staged when it started; the blanket add survives only behind `--stage-all`. Following the rule runs a needless `git reset` that empties a carefully built index. | `scripts/final_gate.py:2525-2545` (`stage_changes`), `:3040-3048` |
| U1-6 / U2-2 | `CLAUDE.md` § Agent Provenance Trailers; `templates/governance/CLAUDE.md:349` | The only commit-trailer example pins `Co-Authored-By: Claude Opus 5`, a model the fleet no longer runs; examples are copied verbatim, into ~46 repos' history. | 39 of the last 40 hub commits carry the harness value `Claude Opus 5.5 (1M context)` |

## B — Style and volume proposals (await operator consent)

Each keeps every rule; the loss check is stated.

| id | where | current | proposed | loss check |
|---|---|---|---|---|
| U1-2 | `CLAUDE.md` § Behavior, "Check before create" | "Exists = STOP, ask." | "Exists = STOP — read it and extend it, or report the clash per § State conflict; a question to the operator only under a DECISION NEEDED ground." | STOP and the State-conflict report stay; only the escalation route changes, to the bar D-558 already sets. |
| U1-3 / U2-6 | `CLAUDE.md` and template, "Present before execute" | unscoped "plan → approval → execute" | scope it to work the operator has not already ordered; name the two exceptions the files already grant (the autonomy ruling D-558 / the DISPATCHED rule, and the plan-execution override) | The approval gate stays for new, unordered work. |
| U1-4 | `CLAUDE.md` § Behavior, "Shared repo" bullet | the peer-messaging and fabrik-mail handling contract (~3.6 KB) sits inside the git-commit bullet | MOVE it unchanged to its own § Behavior bullet after FEEDBACK-IS-RECIPROCAL | A move: no word, D-id or command changes. |
| U2-5 (U1 flagged the same line in the hub) | template `:142`; same wording in `CLAUDE.md` § Behavior, "Stay on task" | "no unsolicited advice or process commentary." | "…no unsolicited advice; process observations go in the `FEEDBACK:` line or an upstream filing, not mid-response." | The ban stays; the text no longer reads as forbidding the filing duty the same files mandate. |
| U2-4 | template `:157-169` | seventeen ⚠️ markers, seven on one paragraph | keep one ⚠️ at the head of the block, drop the inner glyphs; every word and bold stays | Volume only. |
| U2-7 | template `:48` | "on Claude Code 2.1.280" | "whether `EnterWorktree` copies that set has varied across Claude Code versions" | The check-and-copy instruction and its reason stay. |
| U1-7 | `CLAUDE.md` § Pointers, "Authoring a prompt" | "the agentic patterns you MUST enforce" | "the agentic patterns it binds" | Binding force stated in words. |
| U2-9 | template `:378` | "USE THEM when resuming work…" | "Use them when resuming work…" | Volume only; every trigger stays. |
| R2-1 | `.windsurf/rules/core/35-security-auth.md:143,259`; `45-testing-strategy.md:166` | "**CRITICAL: 12-Factor mandate.**" ×2; "(12-Factor X) (CRITICAL)" | "**12-Factor mandate.**"; drop "(CRITICAL)" | The 12-Factor quote and the Mandate/BANNED lines still carry the rule. |
| U3-1 | `commands/_fragments/autonomy-run.md:1`, `term-coverage.md:1`, `term-edit.md:1` | "(READ FIRST — the rule agents skip)" (autonomy-run, term-coverage); "READ FIRST (the rule agents skip)" (term-edit) | drop the parenthetical | The only emphatic claim in the fragments with no measurement behind it; ⚠️ and the bodies' dated obligations keep the signal. |
| C4-1 | `commands/_sources/design-review.md:8` | "You are an elite design review specialist… world-class… rigorous standards of top Silicon Valley companies like Stripe, Airbnb, and Linear." | "You are a design review specialist focused on user experience, visual design, accessibility, and front-end implementation." | The Stripe/Airbnb/Linear bar stays in the frontmatter description (`:3`). |
| U1-8, U1-9 | `CLAUDE.md` stash bullet; § Completion Contract 1a | a repeated "a pop takes whatever is on top"; "Don't ship first-draft code." | drop the repeat; drop the generic sentence | The bullet already says it once; the fixed-point loop that follows is the rule. |

## C — Flagged, no change proposed

- Refuted in review: two seats reported the `final_gate.py` line cites in both contracts as drifted or unchecked (`:1300` as stale). They hold: `:1300` is the `elif code == 5` branch that emits the `NO TESTS COLLECTED` row, and `tests/test_governance_template_split.py` (`test_the_gate_rows_line_citations_land_on_what_they_name`, pin at `:874`) checks every cite in both files.
- The `⚠️ POOL OFF — D-181` banner is copied into 23 of the 38 command sources and the copies DISAGREE in which seat types and flags they list (5 distinct variants across the 23 copies; 10 carry the `dispatch_headroom.py` sentence and 13 do not; `fabrik-command-improve.md:6` omits `fabrik-gui` and carries a shorter dispatch sentence). Keep-list item 8 treats disagreeing duplicates as a finding: a shared fragment would end the drift. A structural change, so recorded here rather than proposed.
- `term-coverage.md` and `term-edit.md` share long verbatim spans that currently agree (keep-list 8).
- `fabrik-vision.md:638,1089` "**CRITICAL: STOP GENERATION HERE.**" — no D-id, but it guards a live failure (the model writing the owner's reply); kept.
- Seven `(CRITICAL)` headers in `30-ops.md` and five across `10-python`, `55-observability`, `25-data-postgres` each sit over a reasoned mandate; kept.
- The `RULES ACTIVE` line, `Read fully before non-trivial work.`, the template's ⚠️ headings and the two 4–5 KB special-case paragraphs (template `:169`, `:291`) — flagged by the seats, no cut survives the loss check.
- Seat machinery: a single Bash read over ~30 KB is persisted by the harness to a path the seat briefs forbid reading; future briefs should cap one read near 25 KB.

## What happens next

1. Section A is filed as its own work item and goes through the full `/fabrik-review` (the template and the hub contract are governance-sync paths).
2. Section B waits for the operator's consent; nothing there is applied by this audit.
3. Only after the landed sources are distributed by the sync and the corpus render are the inheritors told to audit their own non-synced prompts: the project agents and fabrik-lib (ordering rule 01M3RQE2).

## Related

- Seat findings, per unit: the session scratch at audit time; this report carries every finding they raised at medium confidence or above.
- `docs/reference/operating-manifesto.md` (D-330, D-331); `docs/DECISIONS.md` D-558 (autonomy ruling).
