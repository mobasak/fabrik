---
description: Resume a neglected project fast: MEASURE plan-state vs locks, doc freshness, stub sentinels, spec `shape:` truth; QUEUE worst-first; EXECUTE via owning converge commands (never reimplements). Stage: utility. TRIGGER — EN: "catch this project up", "where did we leave off here", "is this project stale or behind", "resume work on this project"; TR: "bu projeyi güncelle", "kaldığımız yerden devam edelim", "proje güncel mi" — fires bare-prose. SKIP: a docs sweep on a HEALTHY project (→ /fabrik-docs-review) · one doc's deep converge (→ /fabrik-doc-converge) · resuming an approved plan (→ /fabrik-execute-plan — catchup never executes plans).
argument-hint: "[optional: a doc, area, or finding class to prioritize this pass — omit for the full measure sweep]"
---

Bounded run: **MEASURE** drift, **QUEUE** it worst-first, **EXECUTE** each item through the command that owns its fix. This command never reconciles a doc or contract itself — it routes to `/fabrik-doc-converge`, `/fabrik-features`, `/fabrik-data-contract` and `/fabrik-ui-design`.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
## ⚠️ Termination contract

You are done **only when a fresh re-run of Phase 0 MEASURE raises zero new queue items** — each prior finding is fixed, explicitly `BLOCKED`, or **accounted for** once this run's report names it: a candidate dead consumer reference or a genuinely undecidable reconcile downgraded per Phase 2 (both report-only, un-committed); an item ROUTED to whoever owns it — mailed to its beat, or a gate red or work item reported to its owner — with the mail id or owner named; an item another session holds, named. The re-measure must be a genuine no-op **and** `python scripts/final_gate.py --check --json` reports `"status":"success"` **in this same run** — or reds only on checks a named owner holds (`GATE: failure (owned: <owner>)`). Executing one item can surface another, so the pass in which you executed any queue item is never the last MEASURE: run Phase 0 again, unprompted. Catchup owns only this outer loop. **Context is never a reason to stop.** The only legitimate early stop is a routed command coming back `BLOCKED` after 3 consecutive attempts on the same item — pause that item, name it in the report, and work the rest.

{{include:grounding-artifact}}

{{include:repo-identity}}

## Phase 0 — MEASURE (read-only; no fixes yet)

If `/opt/fabrik/docs/infrastructure/probe-reports/fleet-doc-audit-latest.md` has a flagged row for this project, read it as a head start — **never as a substitute**: it can be a week stale, so recheck every number.

Run `python scripts/final_gate.py --check --json` FIRST and queue each red it reports as an item. A red an open `.fabrik/work/` item or a sibling mid-flight names is owned: it is reported to its owner (in a worktree, also the merge owner), never fixed here.

Run every probe against the CURRENT tree (probes 1, 5, 6, 7 extend `scripts/fleet_doc_audit.py`):

1. **Plan state vs lock.** Enumerate plans `docs/development/plans/*.md` and plan-set dirs `docs/development/plans/*/` (the same-stem spine file), excluding `archived/`. Read each `Status:` through `parse_plan_status` (`python3 -c "import sys; sys.path[:0] = ['/opt/fabrik/scripts', 'scripts']; from docs_updater import parse_plan_status; print(parse_plan_status(__import__('pathlib').Path(sys.argv[1]))[0])" <plan file or spine .md>`; the hub's copy first), never a grep, which misreads a bold header. Reconcile against ALL `.fabrik/plan-locks/*`. Flag: spine `IN-PROGRESS` with the lock missing or not `"active"`; spine `DRAFT`/`CONVERGED` with an `active` lock; spine `EXECUTED` while the plan sits outside `docs/development/plans/archived/`; a lock whose `plan` path does not resolve, or sits under `docs/development/plans/` outside `archived/` with a terminal `status` (a plan kept elsewhere, such as an epic's, is not held to the `archived/` rule), or sits INTO `archived/` while `"active"`. Terminal allowlist: {`released`, `executed`, `complete`, `completed`, `done`}. **Not a finding:** a lock INTO `archived/` with a terminal `status`.
2. **Key-doc freshness vs code.** `git log -1 --format=%ct -- <code roots>` vs the same for every key doc this `project.yaml::type` obligates (`docs/SERVICES.md`, `docs/RESILIENCE.md`, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`, `docs/FEATURES.md`). The code roots are the directories `git ls-files -- '*.py' '*.ts' '*.tsx' '*.js' | grep / | cut -d/ -f1 | sort -u` prints, less `tests`, `docs`, `templates`, dot-directories and a `libs/` only when it is vendored — never a hand list. ≥14 days behind = a CANDIDATE, queued only when a spot check finds a claim the code contradicts; a date-stale doc with no drift is named in the report, not queued.
3. **Stub sentinels.** Run `python3 /opt/fabrik/scripts/fleet_doc_audit.py --repo .` and read its `stubs:` line, never a hand list. With no `/opt/fabrik`, grep for `[Project Name]`, `[TBD…]`, `**Last Updated:** YYYY-MM-DD`, `[… — fill in]`, `[purpose]` and say the template check was skipped.
4. **Untracked key docs.** An obligated doc on disk that `git ls-files` doesn't know is its own failure mode, never folded into the staleness day-count.
5. **Spec `shape:` vs code.** For each `specs/services/*.yaml`, check every `shape:` flag against the code, per `CLAUDE.md` § Spec contract awareness (`needs_database` ⇒ a real DB call, `exposes_metrics` ⇒ live `/metrics`, `needs_cache` ⇒ a real Redis call, …).
6. **Candidate dead consumer references (DETECT only — never docker-probe, never auto-fix).** Grep `.env`/`.env.example`/specs/code for a retired-looking name: a known-retired service, an `/opt/archived/*` source, or an env row naming a service absent from the hub's `PORTS.md`/catalog. **Report these for the operator — do not act on them.** This box's **local** `fabrik` bridge is not the fleet's, so a project-side probe can falsely call `postgres-main:5432` dead: liveness is **hub-verified only**; never remove or repoint a reference from here.
7. **Work-store hygiene** (a repo with `.fabrik/work/`). An open item titled as a markdown heading or opening with a closed marker is a polluted queue entry: `grep -lE '"title": "(#|✅|~~|\*\*CLOSED)' .fabrik/work/W-*.json | xargs -r grep -LE '"status": "(done|dropped)"'` lists them. An owned one goes to its owner (`work.py drop` if finished, a retitle if live); an unowned one is dropped or retitled here — never close another owner's item.

## Phase 1 — QUEUE (worst-first, routed)

Worst first: a gate red, then a plan-state contradiction or dead consumer reference, then a stale doc, then a stub sentinel or polluted work item. Every item names the finding, its evidence (`path:line` or command output) and its **route**:

| Finding | Route |
|---|---|
| A scaffold doc stale/missing/stubbed (SERVICES, RESILIENCE, CONFIGURATION, OPERATIONS, QUICKSTART, DEPLOYMENT, TROUBLESHOOTING, INDEX.md, docs/README.md, README.md, BUSINESS_MODEL, STRATEGIC_BACKLOG) | `/fabrik-doc-converge <doc>` |
| `docs/FEATURES.md` incomplete or stale | `/fabrik-features` |
| `docs/data-contract.md` stale vs the live schema | `/fabrik-data-contract` |
| `docs/ui-design.md` stale vs the built screens (GUI types only) | `/fabrik-ui-design` |
| Plan `Status:` vs lock, or a `shape:` flag lying vs code | a named reconcile action: fix whichever side is wrong (the spine header or lock; the flag in `specs/services/<id>.yaml` or the code), never both silently, stating which and why; genuinely undecidable → report-only per Phase 2 |
| Gate red, or a polluted work item (probe 7) | the fix its check names; one an open item or a live sibling owns is reported to its owner, never fixed here — this command never closes another owner's item |
| Candidate dead consumer reference | **report only, no auto-fix**: name it and why it looks retired, hand retirement to the operator via `/fabrik-decommission`; never docker-probe liveness |

## Phase 2 — EXECUTE (one item at a time)

Work the queue top to bottom. **In a repo with `.fabrik/work/`, claim before executing:** a queued item an open store item already names is claimed by its id (`python3 scripts/work.py claim W-xxxxxxxx`), its commit names that id, and `work.py done W-xxxxxxxx --evidence <sha>` closes it; one another session holds is skipped and named. Mint no item for a finding without one. In the hub, an item on another agent's beat is mailed to that beat (`docs/reference/agents/`), and the mail id goes in the report. Per item: run its routed command or reconcile action, re-run the exact probe that raised it, then commit — explicit pathspecs only, Agent Provenance Trailers, **one commit per item** (never batch unrelated items). **A DECISION-SHAPED reconcile** (a deliberate `shape:` flag flip, a Status re-ruling — beyond restoring observed truth) **carries its `docs/DECISIONS.md` row IN THE SAME commit, classified at mint**. **A reconcile whose true side is undecidable from the tree downgrades to a REPORT-ONLY item naming both candidate truths**, never a silent guess. Move on once a routed command reports done. **Exception:** a candidate dead consumer reference is never auto-executed; retirement is the operator's call via `/fabrik-decommission`.

## Output (always, last thing)

```
CATCHUP: <project> — measured 7 probe classes, queued <N> items, executed <N>, blocked <N>, reported <N>
RE-MEASURE: <clean (zero new items) | N new items found: <name them>>
GATE: python scripts/final_gate.py --check --json → success|failure|failure (owned: <owner>)
```

Next command: once the re-measure is clean, resume the pipeline stage the project was in before it went stale.

{{include:close-chain}}
