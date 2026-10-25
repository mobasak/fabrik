---
description: "Retire a project or service safely: hub-side liveness probe vs sibling domains and a fleet consumer sweep first (never a catalog/PORTS/env row as evidence), then one of three named outcomes, an operator confirmation gate, and only then the source move + hub bookkeeping. Runtime teardown is always a separate, operator-gated step. Stage: utility. TRIGGER — EN: \"retire this project\", \"decommission this service\", \"archive and shut down X\"; TR: \"bu projeyi emekliye ayır\", \"bu servisi kapat ve arşivle\" — fires bare-prose. SKIP: proving a just-deployed service ALIVE (→ /fabrik-deploy-verify) · executing runtime teardown (→ the operator's own `fabrik destroy`, never any command's act)."
argument-hint: "<project or service name to retire — omit to be asked>"
---

Retire ONE named project/service. Run from the hub (`/opt/fabrik`), which has the fleet DNS/SSH reachability a project-side agent lacks.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
## ⚠️ Termination contract

This is a bounded GROUND TRUTH → DECIDE → CONFIRM → EXECUTE run for ONE name: finish Phase 0 (liveness probe AND consumer sweep) before Phase 1 states one outcome, and get the operator's explicit go-ahead at Phase 1.5 before Phase 2 touches a file. You are done only when Phase 2's **receipts table** accounts for every surface with `path:line` or command-output evidence; a cell filled from memory is not a receipt. Runtime teardown (containers, Traefik route, registrar entries, DNS, Gatus probe) is NEVER one of this run's own actions, in any outcome; it is NAMED as a separate operator-gated follow-up. Two legitimate stops, both before Phase 2: a live blocking consumer with no migration path (outcome C), and an unconfirmed Phase 1.5, where you WAIT.

{{include:grounding-artifact}}
## Phase 0 — GROUND TRUTH (read-only; no move yet)

1. **Consumer sweep.** Grep every fleet project's `.env`, `.env.example`, `specs/services/*.yaml` and code for the target's hostname, URL, API base or import path (`command grep -rn` across `/opt/*` excluding `/opt/archived/`). List every hit with `path:line`; any project referencing the target is a consumer.
2. **Liveness probe — DNS vs siblings, never registry rows.** Resolve the target's public domain (`dig +short <name>.vps1.ocoron.com` or `getent hosts`) in the SAME probe run as two KNOWN-LIVE sibling domains on the same VPS, and VERIFY the siblings resolve (`status.vps1.ocoron.com`; `gatus.vps1`/`grafana.vps1` are NXDOMAIN). On vps2/vps3 wildcard DNS makes bare resolution non-evidentiary; use the HTTPS layer per `/fabrik-deploy-verify`'s control probe. Target resolves → LIVE; target fails AND both siblings resolve → DEAD; target AND siblings all fail → inconclusive outage, re-probe later. Never conclude dead from an unreachable host. **Never** treat a catalog row, `PORTS.md` row, a `specs/services/*.yaml` file's mere existence, or a `.env` reference as evidence of liveness either way. Archived source says nothing about liveness: `mv /opt/<name> /opt/archived/<name>` only relocates the SOURCE tree; only `fabrik destroy` (`src/fabrik/orchestrator/destroyer.py:338-340`) touches the VPS runtime. Only a probe run THIS session counts.

## Phase 1 — DECIDE (state exactly one, before touching a file)

| Outcome | When | What happens |
|---|---|---|
| **archive-source-only** | Liveness = LIVE, and/or a live consumer with no migration need yet | Phase 2 moves the SOURCE project only; the deployed service is untouched |
| **full decommission** | Liveness = DEAD, and no live consumer remains | Phase 2 moves the source AND names runtime teardown as a separate operator-gated step; never executes it |
| **migrate-consumers-first** | Consumer sweep found ≥1 live consumer with NO migration path named | STOP. List each blocking consumer (`path:line`) and what it needs (e.g. an equivalent `fabrik-lib/<module>` capability); do not proceed to Phase 2 |

**Runtime teardown, named but never run here** (only from *full decommission*): containers, the Traefik route, every registrar entry the spec's `shape:` block provisioned, the DNS A record and the Gatus probe. The tool is `fabrik destroy specs/services/<id>.yaml` (`src/fabrik/cli.py::destroy`); cite it for the operator to run, since this command never shells out to it. Cite WITH it the ledger obligation: the hub session that executes the destroy mints the superseding ONE-WAY row (§ Binding field block) in that same change. Its VPS-side `sudo rm -rf /opt/<name>` is what makes a *full decommission* irreversible.

## Phase 1.5 — OPERATOR CONFIRMATION (mandatory stop, before any tree or bookkeeping mutation)

Present the Phase 0 evidence (consumer sweep hit count + files, the liveness verdict) and the Phase 1 outcome, then STOP. Do not proceed to Phase 2 on inference or silence; wait for the operator's explicit go-ahead. This gate applies to all three outcomes.

## Phase 2 — EXECUTE (source move + hub bookkeeping only — never runtime teardown)

1. **Count before.** Record `git -C /opt/<name> ls-files | wc -l` (tracked), `git -C /opt/<name> status --porcelain | wc -l` (uncommitted) and `find /opt/<name> -type f | wc -l` (raw total, catching gitignored files).
2. **Collision guard, then move.** Run `test ! -e /opt/archived/<name>` first. If it fails, STOP: do not overwrite; ask the operator whether to reuse it or append a `-<YYYYMMDD>` suffix. Once clear: `mv /opt/<name> /opt/archived/<name>`. Across a filesystem boundary `mv` copies then unlinks and CAN drop a file, so step 3's counts prove nothing was lost.
3. **Count after.** Re-run the same three counts at the new path. All three MUST match "before" exactly. A mismatch is a CRITICAL failure: stop, do not proceed to bookkeeping, report the discrepancy.
4. **Hub bookkeeping** (run the mechanism, never hand-edit):
   - `python scripts/sync_projects.py` regenerates `data/projects.yaml` + `docs/PROJECT_CATALOG.md`. The move does the exclusion (`DEFAULT_EXCLUDES` holds `"archived"`, `scripts/sync_projects.py:35-42`); never hand-edit the catalog.
   - `python scripts/fleet_doc_audit.py` regenerates the fleet audit report, excluded by LOCATION (`scripts/fleet_doc_audit.py:43-60`). Never add a hardcoded retired-name list.
   - `PORTS.md`: annotate the project's row RETIRED + date + reason; never delete the row silently.
   - **Spec disposition.** *Full decommission* AND the separately-gated teardown has actually run → `git rm specs/services/<id>.yaml`. *Archive-source-only*, or teardown not yet run → annotate the spec's header comment (source archived, service still deployed); never delete a spec for a service still running.
   - **Memory record**: one entry stating BOTH facts as separate, dated clauses; "source archived to `/opt/archived/<name>` on `<date>`" is NOT "the service is decommissioned".
   - CHANGELOG entry (`Changed` for archive-source-only, `Removed` once a real teardown lands).
   - The `docs/DECISIONS.md` retirement row (see the Receipts table), minted HERE in this bookkeeping change, never deferred to the run close.

## Receipts (Termination — every row filled with evidence, or the run isn't done)

A run that stops at Phase 1.5 owes none of these rows and emits the AWAITING form of the Output block. Only EXECUTED runs owe every row below.

| Surface | Before | After | Evidence |
|---|---|---|---|
| Source location | `/opt/<name>` | `/opt/archived/<name>` | `ls` / the move command's own output |
| File count | tracked N, uncommitted N, total N | same three, re-counted | exact match or CRITICAL stop |
| Catalog (`data/projects.yaml`) | listed | excluded | `sync_projects.py` run output |
| Fleet audit | scanned | excluded | `fleet_doc_audit.py` run output |
| `PORTS.md` row | live | RETIRED + date + reason | diff |
| Spec (`specs/services/<id>.yaml`) | present | `git rm`'d (real teardown) or annotated (source-only) | diff / `git rm` output |
| Memory record | — | written, archived-source vs dead-service stated separately | quoted entry |
| Decision ledger | — | the retirement ROW minted in the HUB's `/opt/fabrik/docs/DECISIONS.md` in Phase 2's own change (never the archived project's ledger), classified REVERSIBLE; the later `fabrik destroy` is a NEW decision, and this run only NAMES that obligation | the row, quoted |
| Runtime teardown | — | NAMED as the operator's own `fabrik destroy` call, or n/a | — never executed here |

## Output (always, last thing)

**Paused at Phase 1.5**: close with `python3 scripts/command_run.py handoff --command fabrik-decommission --resume <a file holding this block under a ## RESUME heading> --reason "awaiting operator confirmation at Phase 1.5" --feedback …`, never `done`, since nothing has executed.

```
DECOMMISSION: AWAITING OPERATOR CONFIRMATION — outcome <A|B|C> proposed, evidence attached
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: n/a (pre-execution)
RECEIPTS: n/a (pre-execution)
RUNTIME TEARDOWN: n/a (pre-execution)
```

**Executed** (operator confirmed, Phase 2 ran to completion):

```
DECOMMISSION: <name> — outcome: archive-source-only | full decommission | migrate-consumers-first
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: tracked <before>→<after>, uncommitted <before>→<after>, total <before>→<after> — match | MISMATCH
RECEIPTS: all <N> surfaces reconciled (N = the Receipts-table row count — count the table, never restate a literal; counts drift) | outstanding: <name them>
RUNTIME TEARDOWN: named for the operator (`fabrik destroy specs/services/<id>.yaml`) | n/a — service stays live
```

Next command: none; after *full decommission* the operator's own `fabrik destroy specs/services/<id>.yaml` is next, never auto-chained; after *migrate-consumers-first*, the named blockers.

{{include:close-chain}}
