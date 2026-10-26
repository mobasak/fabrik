---
description: Converge the in-scope docs (the branch diff, or a given path/doc/range) to a fixed point — bidirectional doc↔code reconciliation → route each doc to its type → doc-sync gate, with cited evidence. TRIGGER — EN: "review all the docs", "are the docs still accurate"; TR: "tüm dokümanları gözden geçir", "dokümanlar kodla uyumlu mu" — fires for the MULTI-doc reconciliation sweep. SKIP: one doc's deep single-file converge (→ /fabrik-doc-converge). Stage: utility.
argument-hint: "[path, doc, or git range — omit to reconcile docs against the working-tree/branch diff]"
---

DOCS UPDATE CONVERGENCE

Converge the documentation to a fixed point — do not stop after one pass.

{{include:grounding-artifact}}
{{include:term-edit}}
## Run record — open it FIRST, close it only at the closing round

**5 phases (0–4)**; terminal condition: **the Termination contract's closing round (`confirmed: 0`, md5 unchanged) with the doc-sync gate green, or red only out-of-surface and declared (Phase 4 item 2).**

```bash
python3 scripts/command_run.py start --command fabrik-docs-review --phases 5 \
  --surface "<what this run is OVER — the spec | plan dir | ticket | diff range>" \
  --terminal "closing round confirmed 0 + the doc-sync gate green, or red only out-of-surface and declared"
```

{{include:orient}}

`step --phase <N> --title "<phase title>"` on entering each phase; one
`round --seats <seats dispatched this pass> --findings <discrepancies raised> --confirmed <discrepancies that held, executed>
--classes-swept <doc/claim classes swept clean> --classes-new <classes this pass opened>` per Phase-2/3 pass. The ledger is the doc set — re-sweep the
SAME docs each pass rather than re-scoping.
`done --command fabrik-docs-review --evidence "<the closing round + the verbatim gate line>" --feedback "<what you filed, to whom | none — surfaces exercised>"` at the
TERMINAL verdict; `blocked --command fabrik-docs-review --reason "…" --feedback "<…>"` otherwise. **Always name the run
you close** — a bare close would end the CALLER when nested. **Open the `RUN:` line on every reply until the run closes.**

## Phase 0 — Establish scope

### ⚠️ Synced docs — CONTEXT, never a TARGET (settle this FIRST)

**Am I in the HUB or a PROJECT?** → `git rev-parse --show-toplevel`.

**PROJECT** (repo root ≠ `/opt/fabrik`) — the centrally-distributed docs are **read-only** here (gate:
`check_synced_unmodified.py`). Get the list **mechanically; never hand-copy it**
(⚠️ `fabrik_synced_manifest.py` is NOT synced into projects — use the project's own lock):

> **⚠️ POOL OFF — D-181.** Run every fan-out NATIVELY (Claude Task subagents: `fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose); every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction is SUSPENDED; never write `NO-POOL:` for it.

```bash
# PORTS.md + docs/DECISIONS.md are SEEDED_NOT_ENFORCED (projects may edit them) → normal reconciliation targets.
python3 -c "import json;print('\n'.join(sorted(json.load(open('.fabrik/synced.lock')))))" | grep -vxF -e 'PORTS.md' -e 'docs/DECISIONS.md'
```

*(In the HUB, or from anywhere on this box, the canonical list is
`python /opt/fabrik/scripts/fabrik_synced_manifest.py --review-readonly`.)*

- **Never reconcile/rewrite a synced doc inside a project** — the next sync overwrites it. Read and cite it as **binding context**, outside Phase 1's claim-ledger denominator.
- **A synced doc in the diff is ITSELF the finding:** revert + propose upstream in `/opt/fabrik`; fix a stale claim in one **upstream**, never in the local copy.
- **`SEEDED_NOT_ENFORCED` is the exception** — reconcile it normally; NEVER revert a project's `docs/DECISIONS.md` (project-owned rows — reverting is data loss).

**HUB (`/opt/fabrik`)** — the synced docs ARE the product and are in-denominator. Reconcile
them **harder**: a wrong enumeration (counts, scaffold types, pack lists) is high-severity, copied into ~46 repos on the next sync.

The target is `$ARGUMENTS`; without one, use `git diff @{upstream}...HEAD` (fall back to `git diff main...HEAD`, then `git diff HEAD~1`; add `git diff HEAD` for uncommitted changes). Scope is
every doc the change touches PLUS any doc that references the changed code; obey `.windsurf/rules` throughout.

## Phase 1 — Claim extraction (zero skips)

Read every line of every in-scope doc. Build a **numbered claim ledger** — one row per
factual assertion (a path, a count, a command, an invariant, a flag, a port, an env var, a schema reference). Every non-prose line maps to ≥1 claim
or is marked N/A (heading/formatting); an unaccounted line was skipped — go back.

## Phase 2 — Bidirectional reconciliation (to a fixed point)

In this single turn, run reconciliation passes until the Termination contract's closing round
(the fragment above). Treat every claim as STALE until proven against the
real source, BOTH directions:

- **Doc → code:** OPEN the actual code/migration per claim. **A runnable example/command
  is verified by RUNNING it, not eyeballing** (an example that no longer runs is WRONG,
  not VERIFIED). A column name is not its values — read the values. The doc's own wording
  is never evidence for itself.
- **Code → doc:** scan what ACTUALLY changed (endpoints, fields, flags, env vars, files, migrations, features); a shipped change no doc mentions is a discrepancy.
- **Doc → live source (EXTERNAL claims):** a claim about a 3rd-party API / SDK / endpoint,
  **pricing**, a rate limit, a library **version**, or an ISO/RFC **standard** is NOT verifiable against local code — a `fabrik-researcher` seat (web, no shell) — a unit of its own, the workflow slice's `agent` — re-verifies it **LIVE** (`WebSearch` →
  `mcp__brave-search__brave_web_search` → on a miss `mcp__exa__web_search_exa` → official-docs `WebFetch` for library detail;
  a standard/RFC → fetch the primary doc and quote the clause).
  A live-checkable external claim is **VERIFIED-or-WRONG**, never parked as UNVERIFIABLE.

### Verdict taxonomy

Classify every claim with one of:

| Verdict | Meaning | Action |
|---|---|---|
| **VERIFIED** | True now — cite `path:line` proof | None |
| **STALE** | Was true, code moved/changed | Fix to reality, cite new `path:line` |
| **WRONG** | Never true or inverted | Fix to reality, cite `path:line` |
| **DEAD** | Documented but not actually used — audit by real usage, not mere code-match | Delete, don't polish |
| **UNVERIFIABLE** | Can't be checked mechanically | State why; list as residual |
| **INFERENCE** | A `fabrik-researcher` return: no source line states the external claim, but what the seat read implies it | Not VERIFIED: rewrite the claim to what a source line states and re-verify it, since a live-checkable claim is VERIFIED-or-WRONG |
| **NEEDS-RAW-FETCH** | A `fabrik-researcher` return: the source exists (or existed: the return names its archive URL) but the seat's tools cannot extract it | The orchestrator curls the named URL and section (a seat never curls), then classifies the claim by the rows above. If that curl cannot read it either, the orchestrator re-dispatches a `fabrik-researcher` seat for other live sources and classifies the claim by what they say, by the rows above, a source that seat cannot read either counting as none; when they conflict, the primary source decides (the vendor's own docs, the standard itself); only when none of them states or contradicts it, or they conflict with no single primary source to settle it (two primary surfaces that disagree settle nothing), is it UNVERIFIABLE, naming what a human should check and, for a conflict, every source on each side |

A seat's return cites every `path:line` with a short fragment of that line, unique in its
file, in a code span — path:line — `<fragment>` (for `path:a-b`, a fragment of line a; never a blank, rule or
fence line; the fragment carries no `|`, no backtick and no ledger counter such as `confirmed:`) — and a fix is
re-anchored by the fragment, never by the number: an earlier fix that adds or removes a line moves every later
number in the file, and only the fragment finds its line again. Every reconciler brief carries this form. Pass
Ledger rows, receipts (the claim ledger included) and the reviewed docs themselves keep a plain `path:line`: graders parse the first two, and
a quote written into a doc goes stale with the code.

Hunt the drift classes: changed signatures; renamed/removed symbols; config keys, env vars, ports, flags; outdated counts/tables; schema docs
vs the latest migration; dead links; stale versions/dates; documented-but-removed and shipped-but-undocumented features.

### Parallelism — the DEFAULT for a multi-doc scope

Dispatch one INDEPENDENT native seat per doc/subsystem, every run (recipe in
§ Subagents), in parallel, then merge + dedupe their findings, refuting any provably wrong
(quote the code/doc line that disproves it) before acting. Every seat brief, and the orchestrator's own doc edits, apply the lines of `/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE.
**Round 1 keeps the units-sized floor (D-208 — never solo, never two: a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles); every later round is sized by the fragment's D5 sentence (one seat per unit with an open claim, the round-1 `--units` count as the ceiling, D-335).**

**Verify subagents:** re-check a random sample (~20%) of each subagent's VERIFIED claims against the code; their summaries
are NOT proof. Each pass shows what you VERIFIED (the code/paths actually read), then fixes. **Dispatch the doc author-fixes through the Tier-1 reconcile loop** —
`scripts/doc_reconcile.py` (its author leg is a native `general-purpose` seat, or you) emitting a **minimal
structured patch, verified-before-applied**; the Opus adjudication stays yours.
**The loop ends ONLY at the Termination contract's closing round** (the round-1 seats over their own docs at `confirmed: 0`, the md5s unchanged). An empty pass with no coverage evidence does not count.

**Run the next pass UNPROMPTED the moment a pass makes any doc edit.** Three thoughts that
each mean **run the next pass now**: *"the docs were already in sync,"* *"the fix was trivial,"* *"it's
obviously clean."* Only the closing round is convergence.

**The Pass Ledger is the fragment's** (its counters and md5 pair — the discrepancies you raise are its `found:`, the ones you executed and that held its `confirmed:`, the doc edits its `edits:`); a ledger ending on a non-zero `confirmed:` row is an unfinished reconciliation — run the next pass.

```
Pass 1 — reconcilers: <doc types> | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0, edits: 4 | → not done (changed docs)
Pass 2 — sonnet×1 (round-1 owner) · the same seats over their own fixed docs | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | → CONVERGED (the closing round, md5 stable)
```

**⚠️ The WHOLE loop runs inside THIS ONE invocation — you do NOT yield control between passes.** **Context is never a reason to stop:** the harness AUTO-COMPACTS; "low context" filed as BLOCKED is a violation, and a heavy remainder goes to fresh subagents. After a doc edit go **straight into the next pass** in the SAME turn. **You return control EXACTLY ONCE: at the closing
round.**

## Phase 3 — Fix per pass, in one batch, routed to the right doc

Per pass: complete DISCOVERY first, then apply that pass's fixes in one batch. Route each fact to its document type (API reference, architecture, quickstart/README, runbook/ops,
CHANGELOG) without cross-contaminating them. Delete DEAD claims rather than
polishing them; when a DEAD sweep retires a whole documented subsystem or feature, that is a decision-shaped RETIREMENT: its
`docs/DECISIONS.md` row lands in the SAME change, classified at mint (normally a plain row; ONE-WAY — § Binding block — once dependents have dropped it)
(CLAUDE.md § the decision ledger); a routine dead-line deletion needs no row. Bump `Last Updated:` dates where present.

## Phase 4 — Gate + embedded proof

Run the doc-sync gate (`docs_updater.py --check`, plus
`python scripts/enforcement/check_doc_sync.py`) last; it is necessary, NOT sufficient — it verifies presence/format, not truth.

Your final message MUST embed structured proof, not a summary:

1. **Claim ledger** — the full claim → verdict → `path:line` table (or a representative
   subset if >100 claims, with totals).
2. **Gate output** — verbatim `docs_updater.py --check` + `check_doc_sync.py` green; a red none of whose findings the change under review caused (a finding naming a reviewed doc or a file the change touched, the reference doc of a module it added, or an index its added files feed — `PLANS.md`, `INDEX.md` — is in-surface) is embedded verbatim with the one-line `GATE-SCOPE: out-of-surface — <check>; findings naming this surface: 0 of <N>; measured by: <command>` declaration (`/fabrik-review` § Reporting's grammar), and its findings are listed as residuals.
3. **Self-audit** — total claims, counts per verdict (VERIFIED / STALE-fixed / WRONG-fixed
   / DEAD-removed / UNVERIFIABLE), and the line-coverage reconciliation showing zero
   skipped lines.

Do NOT say "reviewed" / "in-sync" / "converged"
without that embedded proof + the gate green (or its out-of-surface red embedded with the `GATE-SCOPE` line).

## Convergence & residuals

Never promise "zero discrepancies"; list the residual risks the tooling can't catch (hard-to-verify prose,
screenshots/diagrams, external-facing copy, examples needing a live service).
Convergence = the Termination contract's closing round, not your say-so, and not "I fixed what I found."


{{include:subagents-core}}

{{include:close-chain}}
