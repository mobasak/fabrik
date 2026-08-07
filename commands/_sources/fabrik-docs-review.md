---
description: Converge the in-scope docs (the branch diff by default, or a given path/doc/range) to a fixed point — bidirectional doc↔code reconciliation (parallel reconcilers) → route each doc to its type → doc-sync gate, with cited evidence. TRIGGER — EN: "review all the docs", "are the docs still accurate"; TR: "tüm dokümanları gözden geçir", "dokümanlar kodla uyumlu mu" — fires for the MULTI-doc reconciliation sweep. SKIP: one doc's deep single-file converge (→ /fabrik-doc-converge). Stage: utility.
argument-hint: "[path, doc, or git range — omit to reconcile docs against the working-tree/branch diff]"
---

DOCS UPDATE CONVERGENCE

Converge the documentation to a fixed point — do not stop after one pass.

{{include:grounding-artifact}}
## Phase 0 — Establish scope

### ⚠️ Synced docs — CONTEXT, never a TARGET (settle this FIRST)

**Am I in the HUB or a PROJECT?** → `git rev-parse --show-toplevel`.

**PROJECT** (repo root ≠ `/opt/fabrik`) — the centrally-distributed docs are **read-only** here (gate:
`check_synced_unmodified.py`). Get the list **mechanically; never hand-copy it**
(⚠️ `fabrik_synced_manifest.py` is NOT synced into projects — use the project's own lock):

```bash
# The lock records exactly what was distributed to THIS project. PORTS.md is SEEDED_NOT_ENFORCED
# (projects may edit it) → it stays a normal reconciliation target.
python3 -c "import json;print('\n'.join(sorted(json.load(open('.fabrik/synced.lock')))))" | grep -vx 'PORTS.md'
# Covers: AGENTS.md · CLAUDE.md · AGENTS-compact.md · .windsurfrules · .windsurf/rules/**
#         docs/reference/MD/** · docs/reference/kilo/** · fabrik-lifecycle.md · tech-stack guide · …
```

*(In the HUB, or from anywhere on this box, the canonical list is
`python /opt/fabrik/scripts/fabrik_synced_manifest.py --review-readonly`.)*

- **Never reconcile/rewrite a synced doc inside a project** — the next sync overwrites it, and editing it is a
  Tier-1 violation. Its claims are still **binding context** for the project docs you ARE reconciling.
- **A synced doc in the diff is ITSELF the finding:** revert + propose upstream in `/opt/fabrik`.
- **`PORTS.md` is the exception** (`SEEDED_NOT_ENFORCED`) — projects may edit it → reconcile it normally.
- A stale claim in a synced doc → fix it **upstream in `/opt/fabrik`**, so every synced project gets the fix. Never
  patch the local copy.

**HUB (`/opt/fabrik`)** — the synced docs ARE the product; a stale claim propagates to every project. Reconcile
them **harder**, and treat a wrong enumeration (counts, scaffold types, pack lists) as high-severity: it will
be copied into 39 repos on the next sync.

If an argument was given, treat it as the target: `$ARGUMENTS` (a changed area, a
specific doc, or a git range). Otherwise get the change under review with
`git diff @{upstream}...HEAD` (fall back to `git diff main...HEAD`, then
`git diff HEAD~1`; include `git diff HEAD` if there are uncommitted changes). Scope is
every doc touched by the change PLUS any doc that references the changed code. Strictly
obey all guidelines in the `.windsurf/rules` folder throughout.

## Phase 1 — Claim extraction (zero skips)

Read every line of every in-scope doc. Build a **numbered claim ledger** — one row per
factual assertion (a path, a count, a command, an invariant, "X does Y", "N services",
a flag, a port, an env var, a schema reference). Every non-prose line maps to ≥1 claim
or is explicitly marked N/A (heading/formatting). At the end, reconcile line-count vs
claims-accounted: if any line is unaccounted for, you skipped it — go back.

## Phase 2 — Bidirectional reconciliation (to a fixed point)

In this single turn, run repeated reconciliation passes until one demonstrably-thorough
pass finds zero new discrepancies. Treat every claim as STALE until proven against the
real source, and check BOTH directions:

- **Doc → code:** for each claim in the ledger, OPEN the actual code/migration and
  confirm it holds — the symbol exists, the count matches. **A runnable example/command
  is verified by RUNNING it, not eyeballing** (an example that no longer runs is WRONG,
  not VERIFIED). A column name is not its values — read the values. The doc's own wording
  is never evidence for itself.
- **Code → doc:** scan what ACTUALLY changed (new/renamed/removed endpoints, fields,
  flags, env vars, files, migrations, features) and confirm each is reflected in the
  right doc. A shipped change no doc mentions is a discrepancy.
- **Doc → live source (EXTERNAL claims):** a claim about a 3rd-party API / SDK / endpoint,
  **pricing**, a rate limit, a library **version**, or an ISO/RFC **standard** is NOT
  verifiable against local code — re-verify it **LIVE** (`mcp__exa__web_search_exa` →
  `WebSearch` → `mcp__brave-search__brave_web_search` → `mcp__context7` for library docs;
  a standard/RFC → fetch the primary doc and quote the clause).
  A live-checkable external claim is **VERIFIED-or-WRONG**, never parked as UNVERIFIABLE —
  a stale price / dead endpoint / wrong version in a doc is exactly the drift this catches.

### Verdict taxonomy

Classify every claim with one of:

| Verdict | Meaning | Action |
|---|---|---|
| **VERIFIED** | True now — cite `path:line` proof | None |
| **STALE** | Was true, code moved/changed | Fix to reality, cite new `path:line` |
| **WRONG** | Never true or inverted | Fix to reality, cite `path:line` |
| **DEAD** | Documented but not actually used — audit by real usage, not mere code-match | Delete, don't polish |
| **UNVERIFIABLE** | Can't be checked mechanically | State why; list as residual |

Hunt the drift classes: changed signatures/return shapes; renamed/removed symbols;
added/removed config keys, env vars, ports, flags; outdated counts/tables; schema docs
vs the latest migration; dead links/cross-references; stale versions/dates/"as of"; and
features documented-but-removed or shipped-but-undocumented.

### Parallelism — the DEFAULT for a multi-doc scope

With **2+ docs or subsystems to reconcile**, `fanout` one INDEPENDENT reconciler per doc/subsystem (recipe in
§ Subagents), run them in parallel, then merge + dedupe their findings — refuting any that are provably wrong
(quote the code/doc line that disproves the discrepancy) before acting — before the next pass. Only a
single-doc scope loops solo.

**Verify subagents:** after merging subagent ledgers, independently re-check a random
sample (~20%) of each subagent's VERIFIED claims against the code. Subagent summaries
are NOT proof — a claim isn't verified until it's grounded in a `path:line` you could
re-run yourself.

After each pass, show what you VERIFIED (which code/paths you actually read) and what you
found, then fix. **Dispatch the doc author-fixes through the Tier-1 reconcile loop** —
`scripts/doc_reconcile.py` / a `pick_models("docs")` pool author emitting a **minimal
structured patch, verified-before-applied** (records the flywheel) — rather than hand-editing
each doc; keep the Opus adjudication (what's actually wrong + the routing decision) yours.
**The loop ends ONLY when a full, demonstrably-thorough pass finds zero
new discrepancies AND makes zero doc edits — a no-op pass.** The pass in which you *fixed*
docs is never the last: run one more, and if it changes anything (a correction, an
addition), keep going. A pass that finds nothing must still enumerate its coverage (what
you actually read); an empty pass with no evidence does not count.

**Run that next pass UNPROMPTED — the moment a pass makes any doc edit you owe it, automatically.** Never wait
to be asked *"did you reconcile to a no-op?"*; the obligation is yours and predates any challenge — reframing
your own skipped rule as a *"fair challenge"* you then conceded to is itself the dodge. Three thoughts that
each mean **run the next pass now**: *"the docs were already in sync,"* *"the fix was trivial,"* *"it's
obviously clean."* Only the zero-discrepancy, zero-edit round is convergence.

**Maintain a numbered Pass Ledger and reproduce it in the report — you are done ONLY when its last row
reads `discrepancies: 0, edits: 0`.** Record the md5 of each reconciled doc at the final pass's start and
end; identical hashes prove the no-op. A ledger ending on any non-zero row is an unfinished reconciliation
— run the next pass.

```
Pass 1 — reconcilers: <doc types> | discrepancies: 4 | edits: 4 | → not done (changed docs)
Pass 2 — reconcilers: <doc types> | discrepancies: 0 | edits: 0 | → CONVERGED (no-op, md5 stable)
```

**⚠️ The WHOLE loop runs inside THIS ONE invocation — you do NOT yield control between passes.** **Context is never a reason to stop:** the harness AUTO-COMPACTS long conversations and the run continues in the same invocation — keep durable artifacts current and keep going; "low context" filed as BLOCKED is still the named violation, and a heavy remainder is dispatched to fresh subagents, never deferred. When a pass
makes any doc edit, do **not** stop, do **not** print "Pass 1 done" and hand back, do **not** wait for the
caller to re-invoke `/fabrik-docs-review`. Go **straight into the next reconciliation pass** in the SAME turn
and keep chaining until the zero-discrepancy, zero-edit no-op. **You return control EXACTLY ONCE: at the no-op
round.** (Invoked as the final step of `/fabrik-execute-plan`, the whole loop completes before the run
finishes.) Ending the turn with an unresolved discrepancy so the operator has to re-invoke is THE failure this
kills — run the next pass instead.

## Phase 3 — Fix per pass, in one batch, routed to the right doc

Within each pass: complete the pass's DISCOVERY first, then apply that pass's fixes in one batch — do not interleave
discovery and editing. Route each fact to the document type it belongs to and respect
that type's contract — API reference, architecture, quickstart/README, runbook/ops,
CHANGELOG — and do not cross-contaminate (an ops detail does not belong in the API
reference, a changelog line is not architecture prose). Delete DEAD claims rather than
polishing them. Bump `Last Updated:` dates where present.

## Phase 4 — Gate + embedded proof

Run the doc-sync gate (`docs_updater.py --check`, plus the project's
Doc Sync Matrix via `python scripts/enforcement/check_doc_sync.py`) as the final step,
but treat it as necessary, NOT sufficient — it verifies presence/format, not truth.

Your final message MUST embed structured proof — not a summary, not "all looks good":

1. **Claim ledger** — the full claim → verdict → `path:line` table (or a representative
   subset if >100 claims, with totals).
2. **Gate output** — verbatim `docs_updater.py --check` + `check_doc_sync.py` green.
3. **Self-audit** — total claims, counts per verdict (VERIFIED / STALE-fixed / WRONG-fixed
   / DEAD-removed / UNVERIFIABLE), and the line-coverage reconciliation showing zero
   skipped lines.

Per CLAUDE.md's convergence HARD STOP, do NOT say "reviewed" / "in-sync" / "converged"
without that embedded proof + the gate green.

## Convergence & residuals

Do not promise "zero discrepancies" as a claim — iterate to a fixed point, then
explicitly list any residual risks the tooling can't catch (hard-to-verify prose,
screenshots/diagrams, external-facing copy, examples that need a live service to run).
Convergence = a full reconciliation round (all reconcilers + merge/refute + the subagent
verification sample) that produced **zero new discrepancies AND zero doc edits** — a no-op
round; not your say-so, and not "I fixed what I found."

{{include:subagents-core}}
