---
description: Resume a neglected project fast: MEASURE plan-state vs locks, doc freshness, stub sentinels, spec `shape:` truth; QUEUE worst-first; EXECUTE via owning converge commands (never reimplements). Stage: utility. Hub weekly `/opt/fabrik/docs/infrastructure/probe-reports/fleet-doc-audit-latest.md` is a re-verified head start if present. TRIGGER — EN: "catch this project up", "where did we leave off here", "is this project stale or behind", "resume work on this project"; TR: "bu projeyi güncelle", "kaldığımız yerden devam edelim", "proje güncel mi" — fires bare-prose, no slash command needed.
argument-hint: "[optional: a doc, area, or finding class to prioritize this pass — omit for the full measure sweep]"
---

Get a neglected project back to a truthful, resumable state in one bounded run: **MEASURE** what has
drifted, **QUEUE** it worst-first, **EXECUTE** the queue by dispatching each item to the command that
already owns that fix. This command never reconciles a doc or contract itself — it routes to
`/fabrik-doc-converge`, `/fabrik-features`, `/fabrik-data-contract`, and `/fabrik-ui-design`, each of
which owns its own convergence loop.

## ⚠️ Termination contract

This is a bounded MEASURE → QUEUE → EXECUTE run, not an open-ended loop. You are done **only when a
fresh re-run of Phase 0 MEASURE raises zero new queue items** — every prior finding is now fixed,
explicitly `BLOCKED`, or **report-only** (a candidate dead consumer reference that is already named in
this run's report counts as accounted-for on re-measure, not a new item — it stays un-committed by design;
see Phase 2's Exception) — a genuine no-op re-measure **and** `python scripts/final_gate.py --check
--json` reports `"status":"success"` **in this same run**. Executing one item can surface another (a doc
converge can expose a fresher staleness elsewhere) — **the pass in which you executed any queue item is
never the last MEASURE**; run Phase 0 again, unprompted, before you stop. Three thoughts that each mean
*run the re-measure now*: "the queue looked short," "that fix was trivial," "it's obviously caught up."
Catchup owns only this outer loop — never the inner convergence loop of a routed command (that command's
own termination contract governs its own no-op). **Context is never a reason to stop**: the harness
auto-compacts and the run continues in the same invocation. The only legitimate early stop is a routed
command coming back `BLOCKED` after 3 consecutive attempts on the same item — pause that item, name it in
the report, and keep working the rest of the queue.

{{include:grounding-artifact}}

{{include:repo-identity}}

## Phase 0 — MEASURE (read-only; no fixes yet)

If `/opt/fabrik/docs/infrastructure/probe-reports/fleet-doc-audit-latest.md` exists (the hub's weekly
`scripts/fleet_doc_audit.py` sweep, readable from any project on this box) and this project has a flagged
row, read it as a head start — **never as a substitute**: the report can be up to a week stale, so every
number in it still needs the fresh check below. If the path is unreadable (a non-hub box, or the file
hasn't run yet), skip it — it is a head start, not a dependency.

Run every probe against the CURRENT tree. Probes 2-4 mirror `scripts/fleet_doc_audit.py`'s probe set
project-side; probes 1, 5, and 6 EXTEND it — plan-lock reconcile, spec `shape:` truth, and dead-reference
detection have no counterpart in the fleet audit, so scoping this run down to the audit's three probes
would silently drop them:

1. **Plan state vs lock.** Enumerate BOTH plan shapes, excluding anything under
   `docs/development/plans/archived/`: single-file plans `docs/development/plans/*.md`, and plan-set
   dirs `docs/development/plans/*/` (read the dir's same-stem spine file). For each, read its `Status:`
   header and look up `.fabrik/plan-locks/<file-or-dir-stem>.json` if it exists — reconcile against ALL
   `.fabrik/plan-locks/*` entries so no lock is left unmatched to a live plan. Flag a contradiction:
   spine says `IN-PROGRESS` but the lock is missing or its `status` is not `"active"` (a released lock
   while the spine still claims work is running); spine says `DRAFT`/`CONVERGED` but an `active` lock
   exists; spine says `EXECUTED` but the plan (file or dir) still sits outside
   `docs/development/plans/archived/`; a lock whose `plan` path does not resolve on disk, or resolves
   outside `archived/` while its `status` is terminal (`released`/`complete`); a lock whose `plan` path
   resolves INTO `docs/development/plans/archived/` while its `status` is still `"active"` (an abandoned
   run archived by hand without releasing the lock). **Not a finding:** a lock pointing INTO
   `docs/development/plans/archived/` with a terminal `status` is the normal end state for a finished plan
   — don't flag it.
2. **Key-doc freshness vs code.** `git log -1 --format=%ct -- src app web lib scripts` vs the same for
   every registry-obligated key doc (`docs/SERVICES.md`, `docs/RESILIENCE.md`,
   `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`, `docs/FEATURES.md` — only the ones this
   `project.yaml::type` actually obligates). ≥14 days behind = flagged stale.
3. **Stub sentinels.** Grep those same key docs for unfilled seed placeholders: `[Project Name]`,
   `[TBD…]`, a literal `**Last Updated:** YYYY-MM-DD`.
4. **Untracked key docs.** An obligated doc that exists on disk but `git ls-files` doesn't know about is
   its own failure mode — never folded into the staleness day-count.
5. **Spec `shape:` vs code truth.** For every `specs/services/*.yaml`, check each `shape:` flag against
   the real code, per `CLAUDE.md` § Spec contract awareness (`needs_database` ⇒ a real DB call exists,
   `exposes_metrics` ⇒ `/metrics` is live, `needs_cache` ⇒ a real Redis call exists, …).
6. **Candidate dead consumer references (DETECT only — never docker-probe, never auto-fix).** Grep this
   project's own `.env`/`.env.example`/specs/code for a host/service name that looks retired: a name
   matching a known-retired service, a reference to an `/opt/archived/*` source, or an env row pointing at
   a service absent from the hub's `PORTS.md`/catalog. **Report these as findings for the operator —
   do not act on them.** A project has no fleet creds (deploy is trigger-not-execute) and this WSL box
   runs a **local** Docker bridge also named `fabrik`, distinct from the fleet's `fabrik` network — a
   project-side DNS/container probe silently resolves against the wrong network and can return a false
   "dead" for a correct reference like `postgres-main:5432`. Liveness itself is **hub-verified only**.
   The captcha retirement (`docs/SERVICES.md` § Service-status drift warning) is the cautionary case: a
   catalog row can outlive the service it describes, so neither "the row says it's live" nor a
   project-side probe saying "unreachable" is proof — only a hub-side check settles it. Actual retirement
   (once the operator confirms) routes to `/fabrik-decommission`, the hub-side retirement runbook — never
   remove or repoint a reference from inside this command.

## Phase 1 — QUEUE (worst-first, routed)

Turn Phase 0's findings into one ordered list, worst first (a plan-state contradiction or a candidate dead
consumer reference outranks a 15-day-stale doc, which outranks a stub sentinel). Every item names: the finding,
its evidence (`path:line` or the command output that raised it), and its **route**:

| Finding class | Route |
|---|---|
| A scaffold doc stale/missing/stubbed (SERVICES, RESILIENCE, CONFIGURATION, OPERATIONS, QUICKSTART, DEPLOYMENT, TROUBLESHOOTING, INDEX.md, docs/README.md, README.md, BUSINESS_MODEL, STRATEGIC_BACKLOG) | `/fabrik-doc-converge <doc>` |
| `docs/FEATURES.md` incomplete or stale | `/fabrik-features` |
| `docs/data-contract.md` stale vs the live schema | `/fabrik-data-contract` |
| `docs/ui-design.md` stale vs the built screens (GUI project types only) | `/fabrik-ui-design` |
| Plan spine `Status:` vs lock contradiction | a named reconcile action — fix the spine header or the lock file to match reality (never both silently); state which was wrong and why |
| Spec `shape:` flag lying vs code | a named reconcile action — flip the flag in `specs/services/<id>.yaml` to match the code, or fix the code to match an intentionally-true flag; state which |
| Candidate dead consumer reference | **report only, no auto-fix** — name the reference + why it looks retired, and hand actual retirement to the operator via `/fabrik-decommission` (hub-side runbook); this command never docker-probes liveness or removes/repoints from a project |

## Phase 2 — EXECUTE (one item at a time)

Work the queue top to bottom. Per item: run its routed command or reconcile action, verify the fix by
re-running the exact probe that raised it, then commit — explicit pathspecs only, Agent Provenance
Trailers, **one commit per item** (never batch unrelated items into one commit — a bisect needs the
granularity). A routed command owns its own termination contract (e.g. `/fabrik-doc-converge` converges
to its own edit-free no-op) — catchup dispatches to it and moves to the next queue item once that command
reports done; it never re-implements that command's convergence loop itself. **Exception:** a candidate
dead consumer reference is never auto-executed — it stays a reported, un-committed item; move to the next
queue item once it is named in the report (retirement is the operator's call, run hub-side via
`/fabrik-decommission`, outside this run).

## Output (always, last thing)

```
CATCHUP: <project> — measured 6 probe classes, queued <N> items, executed <N>, blocked <N>, reported <N>
RE-MEASURE: <clean (zero new items) | N new items found: <name them>>
GATE: python scripts/final_gate.py --check --json → success|failure
```

Next command: this run's fix queue IS the routing — each item already named its owning command
(`/fabrik-doc-converge` · `/fabrik-features` · `/fabrik-data-contract` · `/fabrik-ui-design`); once the
re-measure is clean, resume whichever pipeline stage the project was actually in before it went stale.
