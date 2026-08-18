# Command-corpus integrity check

**What it is:** the gate check that keeps the `/fabrik-*` command corpus honest — every
reference a command makes must point at something that exists. Tool:
`scripts/enforcement/check_command_corpus.py` · Gate row: *Command Corpus (references
resolve — BLOCKING)*, Tier 2 · Tests: `tests/test_check_command_corpus.py`.

## Why it exists

The corpus is the instruction set every agent on this box runs on. When a command names
something that no longer exists, **nothing fails loudly**: the agent follows the
instruction, gets a degraded result, and reports success. It is the same failure shape as
a gate check that asserts nothing — a green signal with no substance behind it.

The founding case, found by the 2026-08-16 corpus audit:

```
fanout("research", …, web_tools=["exa","brave","firecrawl","context7"])
```

Those are **provider** names. `libs/subagents/web_tools.py::WEB_TOOL_NAMES` accepts only
**tool** names, and `loop.py` filters advertised schemas by that set — an unknown name
yields an empty list, whereupon `merged.pop("tools")` runs the agent with **no tools at
all**. Four commands (`/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-after-chat`,
`/fabrik-plan-review`) dispatched their "live search" grounders that way. The grounders
returned confident prose, the results table looked normal, and every spec and plan
grounded that way was ungrounded. No gate, test, or review caught it while the text stood.

## What it proves

Five mechanically decidable facts — no judgement, no network:

| # | Check | Caught live |
|---|---|---|
| 1 | `web_tools=[...]` names only tools in `WEB_TOOL_NAMES` (imported live, never copied) | 4 commands, the founding case |
| 2 | Every `/fabrik-x` · `/design-review` chain reference resolves to a real source | — |
| 3 | Every `scripts/**.py` a command tells an agent to run exists | — |
| 4 | `Co-Authored-By:` in commit templates matches CLAUDE.md's canonical trailer | 6 templates naming a retired model |
| 5 | Every command opens a run record (shared fragment or a bespoke `start` block) | 24 of 27 opened none |

BLOCKING, because each is true/false with no tolerance band — and each was found violated
in a corpus that looked healthy.

## The orchestrator corpus (added 2026-08-16)

The Traycer workflow commands (`fab-mega-*`, `fab-ettw-*`) keep their canonical bodies under
`docs/orchestrator/**` — outside `commands/_sources/` — which is exactly how the whole set
escaped this audit: none of their docs was among the audited files, zero of the four mega
wrappers opened a run record, and a dead `scripts/` reference sat in three mega docs, all while
the check reported "all sound".

The audit now also walks `docs/orchestrator/_traycer-skills/*/SKILL.md` (hub-only; silently N/A
in projects) and, per wrapper:

- resolves the canonical doc the wrapper names and runs predicates 1–4 over it;
- requires a wrapper that **names no doc**, or names a **missing** one, to fail — a wrapper
  aiming agents at nothing is the founding failure shape;
- requires `command_run.py start` in every wrapper carrying the GENERATED banner (those went
  through `assemble_commands.py`'s `ORCH_SOURCES` table, which injects the record with a
  computed phase count). Hand-written wrappers (the ettw set, as of 2026-08-16) are exempt from
  the record requirement — the fix for those is extending `ORCH_SOURCES`, not hand-editing.

Scripts referenced by these docs resolve against the hub root **or** `templates/**` — the
orchestrator docs tell agents working *in a project* to run scripts the scaffold delivers
(e.g. `scripts/validate_i18n.py` from `templates/i18n-kit/`), and hub-rooting alone called
five live references dead.

**The important negative:** path-shaped look-alikes are *not* chain references.
`/opt/fabrik-lib`, `/run/fabrik-autoheal/pause` and `docs/reference/fabrik-mail.md` all
contain a `fabrik-<word>` token. A naive matcher reports four broken chains that were
never broken, and a check that cries wolf gets ignored — which is how a real break then
ships. The boundary lookarounds in `_CHAIN_RE` encode this, and
`test_path_lookalikes_are_not_chain_references` locks it.

### Predicate 5 in detail — why coverage was the whole problem

`CLAUDE.md` makes opening a run record the first act of any `/fabrik-*` invocation, and the Stop
hook's fifth cause refuses to end a turn while a record says `running`. That machinery existed and
was wired into **3 of 27** commands. For the other 24 the pinned `RUN:` line, the class ledger, the
non-convergence detector and the hook were all disarmed — which is precisely the "agents stop
without finishing the command" complaint the record was built to answer.

The fix is a shared `{{include:run-record}}` fragment whose two values — the command's name and its
phase count — are **computed at render time** by `assemble_commands.py::_phase_count`, never
hand-written per command. Hand-authored parameters for 24 commands would drift the moment a phase
was added, and a wrong phase count makes the pinned line lie about where the run is. `_phase_count`
trusts explicit `## Phase N` headings only once there are at least two of them: `/fabrik-release`
declares a lone `Phase 0` and then branches into VPS/MOBILE/STORE sections, so the literal count
would claim the run was finished with most of it still ahead.

## Anti-vacuity

`--selftest` feeds a known-bad corpus through the same predicates and requires **each** to
fire, then a known-good one and requires silence:

```console
$ python3 scripts/enforcement/check_command_corpus.py --selftest
✓ selftest: all 5 predicates fire on bad input and stay silent on good input
```

It was also proven **discriminating on the real defect**: reverting the `web_tools` fix in
a throwaway copy of the corpus turns the check red with the exact provider names named.

Both properties matter. A check that cannot fail is not a check, and a check that only
fails on synthetic fixtures has not been shown to catch the thing it was built for. See
`docs/workstation/liveness.md` for the general three-proof discipline this follows.

## Citation style it enforces by example

Two classes of citation rot were fixed alongside it and should not be reintroduced:

- **Never cite `CHANGELOG.md:<line>`.** The file is prepend-ordered, so a line number is
  wrong by the next entry. Eight citations in `/fabrik-decommission` had drifted ~2 700
  lines, pointing at unrelated text inside a *destructive* runbook. Cite the dated entry
  title instead.
- **Prefer a section anchor to a line range** when citing another command; two
  `/fabrik-deploy-verify` self-citations had slid three lines.

## Related

- `docs/reference/ticket-breadth.md` — the sibling advisory check on plan sets
- `docs/workstation/liveness.md` — heartbeat / vacuity-canary / doc-claim-binding proofs
- `.windsurf/rules/core/62-using-subagents.md` — the canonical `web_tools` recipe
