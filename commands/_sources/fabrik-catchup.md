---
description: Resume a neglected project fast: MEASURE plan-state vs locks, doc freshness, stub sentinels, spec `shape:` truth; QUEUE worst-first; EXECUTE via owning converge commands (never reimplements). Stage: utility. TRIGGER — EN: "catch this project up", "where did we leave off here", "is this project stale or behind", "resume work on this project"; TR: "bu projeyi güncelle", "kaldığımız yerden devam edelim", "proje güncel mi" — fires bare-prose, no slash command needed. SKIP: a whole-tree docs sweep on a HEALTHY project (→ /fabrik-docs-review) · one named doc's deep converge (→ /fabrik-doc-converge) · resuming an approved plan mid-flight (→ /fabrik-execute-plan — catchup measures and routes, it never executes plans).
argument-hint: "[optional: a doc, area, or finding class to prioritize this pass — omit for the full measure sweep]"
---

Get a neglected project back to a truthful, resumable state in one bounded run: **MEASURE**, **QUEUE**, **EXECUTE**. This command never reconciles a doc or contract itself — it routes to `/fabrik-doc-converge`, `/fabrik-features`, `/fabrik-data-contract` and `/fabrik-ui-design`.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
## ⚠️ Termination contract

You are done **only when a fresh re-run of Phase 0 MEASURE raises zero new queue items** — each prior finding is fixed, explicitly `BLOCKED`, or accounted for (named in the report: a candidate dead consumer reference or a genuinely undecidable reconcile downgraded per Phase 2, both report-only, un-committed by design; an item ROUTED to whoever owns it — mailed to its beat, or a gate red or work item reported to its owner (an open item or a live sibling) — with the mail id or owner named; and an item another session holds, named) — a genuine no-op re-measure and `python scripts/final_gate.py --check --json` reports `"status":"success"` in this same run — or reds only on checks a named owner holds (`GATE: failure (owned: <owner>)`).

The pass in which you executed any queue item is never the last MEASURE; run Phase 0 again, unprompted, before you stop. Three thoughts that each mean run the re-measure now: "the queue looked short," "that fix was trivial," "it's obviously caught up." Catchup owns only this outer loop — never the inner convergence loop of a routed command (that command's own termination contract governs its own no-op). Context is never a reason to stop: the harness auto-compacts and the run continues in the same invocation. The only legitimate early stop is a routed command coming back `BLOCKED` after 3 consecutive attempts on the same item — pause that item, name it in the report, and keep working the rest of the queue.

{{include:grounding-artifact}}

{{include:repo-identity}}

## Phase 0 — MEASURE (read-only; no fixes yet)

If `/opt/fabrik/docs/infrastructure/probe-reports/fleet-doc-audit-latest.md` (the hub's weekly `scripts/fleet_doc_audit.py` sweep) flags this project, read it as a head start — never as a substitute: the report can be up to a week stale, so every number in it still needs the fresh check below. If the path or file is unreadable, skip it.

A red found only at the termination gate costs a second loop, so run `python scripts/final_gate.py --check --json` FIRST and queue each red it reports as an item. Before fixing a red, look for its owner — an open item in `.fabrik/work/` that names the failing check, or a sibling; an owned red is reported to its owner (and, in a worktree, to the merge owner), never fixed here.

Run every probe against the CURRENT tree. Probes 2-4 mirror `scripts/fleet_doc_audit.py`'s probe set project-side; probes 1, 5, 6 and 7 EXTEND it (plan-lock reconcile, spec `shape:` truth, dead-reference detection, work-store hygiene), so scoping this run down to the audit's three probes would silently drop them:

1. Plan state vs lock. Enumerate BOTH plan shapes, excluding anything under `docs/development/plans/archived/`: single-file plans `docs/development/plans/*.md` and plan-set dirs `docs/development/plans/*/` (the dir's same-stem spine file). Read each `Status:` through `parse_plan_status` (`python3 -c "import sys; sys.path[:0] = ['/opt/fabrik/scripts', 'scripts']; from docs_updater import parse_plan_status; print(parse_plan_status(__import__('pathlib').Path(sys.argv[1]))[0])" <plan file or spine .md>`; the hub's copy first), the value the gate's tools act on, which a grep misreads. Look up `.fabrik/plan-locks/<file-or-dir-stem>.json` if it exists; reconcile against ALL `.fabrik/plan-locks/*` entries. Flag a contradiction: `IN-PROGRESS` with the lock missing or its `status` not `"active"`; `DRAFT`/`CONVERGED` with an `active` lock; `EXECUTED` with the plan still outside `docs/development/plans/archived/`; a lock whose `plan` path does not resolve on disk, or resolves under `docs/development/plans/` but outside `archived/` while its `status` is terminal (a plan kept elsewhere is not held to the `archived/` rule); a lock whose `plan` path resolves INTO `docs/development/plans/archived/` while its `status` is still `"active"`. Terminal allowlist {`released`, `executed`, `complete`, `completed`, `done`} per fabrik-lib `f8249ec3` (2026-08-29). Not a finding: a lock INTO `docs/development/plans/archived/` with a terminal `status`; don't flag it.
2. Key-doc freshness vs code. `git log -1 --format=%ct -- <code roots>` vs the same for every registry-obligated key doc (`docs/SERVICES.md`, `docs/RESILIENCE.md`, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`, `docs/FEATURES.md` — only the ones this `project.yaml::type` actually obligates). The code roots are the top-level directories `git ls-files -- '*.py' '*.ts' '*.tsx' '*.js' | grep / | cut -d/ -f1 | sort -u` prints, less `tests`, `docs`, `templates`, dot-directories and a `libs/` only when it is vendored (a first-party one stays) — never a hand list (`tryton_modules/` and `sao-overlay/` sit outside `src app web lib scripts`). ≥14 days behind = a CANDIDATE: it is queued only when a spot check finds a claim in the doc that the code contradicts; a date-stale doc with no drift is named in the report, not queued.
3. Stub sentinels. Run `python3 /opt/fabrik/scripts/fleet_doc_audit.py --repo .` and read its `stubs:` line — the hub audit's own probe, never a hand list. It reports `<DOC>.md (template text left: p%)` for a doc left as its scaffold template (at least half of some version of that template is still in it, and template text is at least half of the doc), else `<DOC>.md (<n>)` for the seed sentinels it still holds (`[Project Name]`, `[TBD…]`, a literal `**Last Updated:** YYYY-MM-DD`, `[… — fill in]`, `[purpose]`). No `/opt/fabrik` on this box: grep the docs for those five sentinels and say the template check was skipped.
4. Untracked key docs. An obligated doc that exists on disk but `git ls-files` doesn't know about is its own failure mode — never folded into the staleness day-count.
5. Spec `shape:` vs code truth. For every `specs/services/*.yaml`, check each `shape:` flag against the real code, per `CLAUDE.md` § Spec contract awareness (`needs_database` ⇒ a real DB call exists, `exposes_metrics` ⇒ `/metrics` is live, `needs_cache` ⇒ a real Redis call exists, …).
6. Candidate dead consumer references (DETECT only — never docker-probe, never auto-fix). Grep this project's own `.env`/`.env.example`/specs/code for a host/service name that looks retired: a name matching a known-retired service, a reference to an `/opt/archived/*` source, or an env row pointing at a service absent from the hub's `PORTS.md`/catalog. Report these as findings for the operator — do not act on them. A project-side DNS/container probe silently resolves against the wrong network and can return a false "dead" for a correct reference like `postgres-main:5432`. Liveness itself is hub-verified only: only a hub-side check settles it. Actual retirement (once the operator confirms) routes to `/fabrik-decommission`, the hub-side retirement runbook — never remove or repoint a reference from inside this command.
7. Work-store hygiene (a repo with `.fabrik/work/`). An open item whose title is a markdown heading or opens with a closed marker is a polluted queue entry a distributor would hand to another agent: `grep -lE '"title": "(#|✅|~~|\*\*CLOSED)' .fabrik/work/W-*.json | xargs -r grep -LE '"status": "(done|dropped)"'` lists them. An owned one goes to its owner (`work.py drop` for a finished one, a retitle for a live one); an unowned one is dropped or retitled here — never close another owner's item.

## Phase 1 — QUEUE (worst-first, routed)

Turn Phase 0's findings into one ordered list, worst first (a gate red first — it holds the termination gate; then a plan-state contradiction or a candidate dead consumer reference, which outrank a 15-day-stale doc, which outranks a stub sentinel or a polluted work item). Every item names the finding, its evidence (`path:line` or the command output that raised it), and its route:

| Finding class | Route |
|---|---|
| A scaffold doc stale/missing/stubbed (SERVICES, RESILIENCE, CONFIGURATION, OPERATIONS, QUICKSTART, DEPLOYMENT, TROUBLESHOOTING, INDEX.md, docs/README.md, README.md, BUSINESS_MODEL, STRATEGIC_BACKLOG) | `/fabrik-doc-converge <doc>` |
| `docs/FEATURES.md` incomplete or stale | `/fabrik-features` |
| `docs/data-contract.md` stale vs the live schema | `/fabrik-data-contract` |
| `docs/ui-design.md` stale vs the built screens (GUI project types only) | `/fabrik-ui-design` |
| Plan spine `Status:` vs lock contradiction | a named reconcile action — fix the spine header or the lock file to match reality (never both silently); state which was wrong and why; genuinely undecidable → report-only per Phase 2 |
| Spec `shape:` flag lying vs code | a named reconcile action — flip the flag in `specs/services/<id>.yaml` to match the code, or fix the code to match an intentionally-true flag; state which; genuinely undecidable → report-only per Phase 2 |
| Gate red (Phase 0) | the fix its check names; one an open item or a live sibling owns is reported to it, never fixed here |
| Work-store item polluted (probe 7) | its owner: a finished item is dropped by its owner or the distributor (`work.py drop`), a live one retitled; this command never closes another owner's item |
| Candidate dead consumer reference | report only, no auto-fix — name the reference + why it looks retired, and hand actual retirement to the operator via `/fabrik-decommission` (hub-side runbook); this command never docker-probes liveness or removes/repoints from a project |

## Phase 2 — EXECUTE (one item at a time)

Work the queue top to bottom. In a repo with `.fabrik/work/`, claim before executing: a queued item an open store item already names is claimed by its id (`python3 scripts/work.py claim W-xxxxxxxx`, the file stem), its commit names that id, and `work.py done W-xxxxxxxx --evidence <sha>` closes it; one another session holds is skipped and named. A finding with no store item is executed without minting one. In the hub, an item on another agent's beat is mailed to that beat (`docs/reference/agents/`) instead of executed, and the mail id goes in the report. Per item: run its routed command or reconcile action, verify the fix by re-running the exact probe that raised it, then commit — explicit pathspecs only, Agent Provenance Trailers, one commit per item (never batch unrelated items into one commit — a bisect needs the granularity).

Two manifesto laws bind the reconcile actions: a DECISION-SHAPED reconcile (a deliberate `shape:` flag flip, a Status re-ruling — anything beyond restoring a record to observed truth) carries its `docs/DECISIONS.md` row IN THE SAME commit, classified at mint (plain row normally — a reconcile is by construction reversible, and the undecidable case already downgrades to report-only; a truth-restoring correction needs no row); and a reconcile whose true side is genuinely undecidable from the tree downgrades to a REPORT-ONLY item naming both candidate truths — the most-reversible disposition (manifesto Invariant 3), never a silent guess.

A routed command owns its own termination contract (e.g. `/fabrik-doc-converge`) — catchup dispatches to it and moves to the next queue item once that command reports done; it never re-implements that command's convergence loop itself. Exception: a candidate dead consumer reference is never auto-executed — it stays a reported, un-committed item; move to the next queue item once it is named in the report (retirement is the operator's call, run hub-side via `/fabrik-decommission`).

## Output (always, last thing)

```
CATCHUP: <project> — measured 7 probe classes, queued <N> items, executed <N>, blocked <N>, reported <N>
RE-MEASURE: <clean (zero new items) | N new items found: <name them>>
GATE: python scripts/final_gate.py --check --json → success|failure|failure (owned: <owner>)
```

Next command: this run's fix queue IS the routing — each item already named its owning command (`/fabrik-doc-converge` · `/fabrik-features` · `/fabrik-data-contract` · `/fabrik-ui-design`); once the re-measure is clean, resume whichever pipeline stage the project was actually in before it went stale.

{{include:close-chain}}
