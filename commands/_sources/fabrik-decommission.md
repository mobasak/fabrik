---
description: "Retire a project or service safely: hub-side liveness probe vs sibling domains and a fleet consumer sweep first (never a catalog/PORTS/env row as evidence), then one of three named outcomes, an operator confirmation gate, and only then the source move + hub bookkeeping. Runtime teardown is always a separate, operator-gated step. Stage: utility. TRIGGER — EN: \"retire this project\", \"decommission this service\", \"archive and shut down X\"; TR: \"bu projeyi emekliye ayır\", \"bu servisi kapat ve arşivle\" — fires bare-prose, no slash command needed. SKIP: proving a just-deployed service ALIVE (→ /fabrik-deploy-verify) · executing runtime teardown (→ the operator's own `fabrik destroy`, never any command's act)."
argument-hint: "<project or service name to retire — omit to be asked>"
---

Retire ONE named project/service. Run from the hub (`/opt/fabrik`), which has the fleet DNS/SSH reachability a project-side agent lacks. Runtime teardown is NEVER this command's own decision.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
## ⚠️ Termination contract

This is a bounded GROUND TRUTH → DECIDE → CONFIRM → EXECUTE run for ONE name: Phase 0 must finish in full (liveness probe AND consumer sweep) before Phase 1 states one of the three named outcomes explicitly, and Phase 1.5 must itself receive the operator's explicit go-ahead before Phase 2 touches a single file. You are done only when Phase 2's **receipts table** accounts for every bookkeeping surface (source location, file count, catalog, fleet audit, PORTS row, spec disposition, memory record, decision-ledger row, runtime-teardown disposition) with `path:line` or command-output evidence; a cell filled from memory instead of a fresh command is not a receipt. Runtime teardown (containers, Traefik route, registrar entries, DNS, Gatus probe) is NEVER one of this run's own actions, in any outcome; it is always NAMED as a separate, explicitly operator-gated follow-up, never executed inline. Two legitimate stops, both before Phase 2: (1) a live blocking consumer with no migration path: name it, stop, that is outcome C; (2) an unconfirmed Phase 1.5: present the Phase 0 evidence + the Phase 1 outcome and WAIT, since an outcome stated but not confirmed is not yet actionable.

{{include:grounding-artifact}}
## Phase 0 — GROUND TRUTH (read-only; no move yet)

1. **Consumer sweep.** Grep every fleet project's `.env`, `.env.example`, `specs/services/*.yaml` and code for the target's hostname, URL, API base or import path (`command grep -rn` across `/opt/*` excluding `/opt/archived/`). List every hit with `path:line`; a project referencing the target is a consumer whether or not it currently calls the reference.
2. **Liveness probe — DNS vs siblings, never registry rows.** Resolve the target's public domain (`dig +short <name>.vps1.ocoron.com` or `getent hosts`) in the SAME probe run as two KNOWN-LIVE sibling domains on the same VPS, and VERIFY they resolve before trusting them as controls (`status.vps1.ocoron.com` plus a live spec domain; `gatus.vps1`/`grafana.vps1` are NXDOMAIN). On vps2/vps3 wildcard DNS makes bare resolution non-evidentiary; use the HTTPS layer per `/fabrik-deploy-verify`'s control probe. Three outcomes only: target resolves → LIVE; target fails AND both siblings resolve → DEAD; target AND siblings all fail → inconclusive transient outage, re-probe later (not a verdict either way). Where the host is directly reachable, cross-check with a container/compose check on that VPS; never conclude dead from an unreachable host (that is an outage, not an absence). **Never** treat a catalog row, `PORTS.md` row, a `specs/services/*.yaml` file's mere existence, or a `.env` reference as evidence of liveness either way. Archived source proves nothing about liveness in EITHER direction: `mv /opt/<name> /opt/archived/<name>` only relocates the SOURCE tree and never touches the VPS runtime; the only thing that does is `fabrik destroy` (`_destroy_compose`'s `docker compose down` + remote `rm -rf`, `src/fabrik/orchestrator/destroyer.py:338-340`). The retracted captcha "service stays live" claim (`CHANGELOG.md` 2026-08-07) is cited only as that retracted claim, never as evidence that anything stayed live. Only a probe run THIS session counts.

## Phase 1 — DECIDE (state exactly one, before touching a file)

| Outcome | When | What happens |
|---|---|---|
| **archive-source-only** | Liveness probe = LIVE, and/or the consumer sweep found a live consumer with no migration need yet | Phase 2 moves the SOURCE project only; the deployed service is untouched |
| **full decommission** | Liveness probe = DEAD, and no live consumer remains | Phase 2 moves the source AND names runtime teardown as a separate operator-gated step (below) — never executes it |
| **migrate-consumers-first** | Consumer sweep found ≥1 live consumer with NO migration path named | STOP here. List each blocking consumer (`path:line`) + what it needs (e.g. an equivalent `fabrik-lib/<module>` capability, the captcha → `fabrik-lib/captcha-solve` precedent) — do not proceed to Phase 2 |

**Runtime teardown, named but never run here** (only reachable from *full decommission*): containers / compose app, the Traefik route, every registrar entry the spec's `shape:` block provisioned (GlitchTip project, Gatus endpoint, Meilisearch index, Authelia rule, Backrest plan, Postgres/Redis if `--drop-data`), the DNS A record and the Gatus probe itself. The tool is `fabrik destroy specs/services/<id>.yaml` (`src/fabrik/cli.py::destroy`, def at `:903`; docstring examples at `:924-926`); cite it for the operator to run themselves — this command never shells out to it and never decides to run it. Cite WITH it the ledger obligation: the hub session that executes the destroy mints the superseding ONE-WAY row (§ Binding field block) in that same change. `_destroy_compose` runs `docker compose down` then `sudo rm -rf /opt/<name>` ON THE VPS (`destroyer.py:338-340`) even though the hub archive is preserved; that VPS-side wipe is what makes a *full decommission* irreversible.

## Phase 1.5 — OPERATOR CONFIRMATION (mandatory stop, before any tree or bookkeeping mutation)

Present the Phase 0 evidence (consumer sweep hit count + files, the liveness verdict) and the Phase 1 outcome, then STOP. Do not proceed to Phase 2 on inference or silence; wait for the operator's explicit go-ahead. This gate applies to all three outcomes.

## Phase 2 — EXECUTE (source move + hub bookkeeping only — never runtime teardown)

1. **Count before.** Record `git -C /opt/<name> ls-files | wc -l` (tracked), `git -C /opt/<name> status --porcelain | wc -l` (uncommitted) and `find /opt/<name> -type f | wc -l` (raw total, catching gitignored files).
2. **Collision guard, then move.** Run `test ! -e /opt/archived/<name>` first. If it fails, STOP: do not overwrite; ask the operator whether to reuse it or append a `-<YYYYMMDD>` suffix (`/opt/archived/<name>-<YYYYMMDD>`) before proceeding. Once clear: `mv /opt/<name> /opt/archived/<name>`. The move is atomic only when `/opt` and `/opt/archived` share a filesystem; across a filesystem boundary `mv` silently falls back to copy-then-unlink and CAN drop a file mid-copy, so step 3's counts prove nothing was lost.
3. **Count after.** Re-run the same three counts at the new path. All three MUST match the "before" counts exactly (the wpf move preserved 8 uncommitted files, the captcha move 6; `CHANGELOG.md` 2026-08-07). A mismatch is a CRITICAL failure: stop, do not proceed to bookkeeping, report the discrepancy.
4. **Hub bookkeeping** (run the mechanism, never hand-edit):
   - `python scripts/sync_projects.py` regenerates `data/projects.yaml` + `docs/PROJECT_CATALOG.md`. The move does the exclusion: `scan_projects()` walks `root.iterdir()` over `/opt/*` top-level only, `DEFAULT_EXCLUDES` holds `"archived"` (`scripts/sync_projects.py:35-42`, checked at `:109-123`), so `/opt/archived/<name>` is never visited; never hand-edit the catalog.
   - `python scripts/fleet_doc_audit.py` regenerates the fleet audit report, excluded by LOCATION: `_excluded()` imports `sync_projects._is_excluded` (`scripts/fleet_doc_audit.py:43-60`), never a hardcoded name list (a hardcoded `RETIRED` set was removed as dead code and a silent revival trap). Do not add one back.
   - `PORTS.md`: annotate the project's row RETIRED + date + reason; never delete the row silently.
   - **Spec disposition.** *Full decommission* AND the operator has since confirmed the separately-gated runtime teardown actually ran → `git rm specs/services/<id>.yaml`. *Archive-source-only*, or teardown not yet run → annotate the spec's header comment (source archived, service still deployed); never delete a spec for a service still running. A spec left behind after a REAL teardown is an orphan trap: `fabrik apply` would resurrect the service and every fleet audit keeps counting it.
   - **Memory record**: one entry stating BOTH facts as separate, dated clauses even when they land in the same note; "source archived to `/opt/archived/<name>` on `<date>`" is NOT "the service is decommissioned".
   - CHANGELOG entry per the Doc Sync Matrix (`Changed` for archive-source-only, `Removed` once a real teardown lands).
   - The `docs/DECISIONS.md` retirement row (see the Receipts table), minted HERE in this bookkeeping change, never deferred to the run close.

## Receipts (Termination — every row filled with evidence, or the run isn't done)

A run that stops at Phase 1.5 owes none of these rows and emits the AWAITING form of the Output block, with FILES and RECEIPTS both marked `n/a (pre-execution)`. Only EXECUTED runs (operator confirmed, Phase 2 ran) owe the full Receipts-table reconciliation: every row below, count derived from the table itself.

| Surface | Before | After | Evidence |
|---|---|---|---|
| Source location | `/opt/<name>` | `/opt/archived/<name>` | `ls` / the move command's own output |
| File count | tracked N, uncommitted N, total N | same three, re-counted | exact match or CRITICAL stop |
| Catalog (`data/projects.yaml`) | listed | excluded | `sync_projects.py` run output |
| Fleet audit | scanned | excluded | `fleet_doc_audit.py` run output |
| `PORTS.md` row | live | RETIRED + date + reason | diff |
| Spec (`specs/services/<id>.yaml`) | present | `git rm`'d (real teardown) or annotated (source-only) | diff / `git rm` output |
| Memory record | — | written, archived-source vs dead-service stated separately | quoted entry |
| Decision ledger | — | the retirement ROW minted in the HUB's `/opt/fabrik/docs/DECISIONS.md` in Phase 2's own change (never the archived project's ledger; the ledger duty's "retirement/adoption" trigger), classified at mint as REVERSIBLE — the archive move is undoable and nothing irreversible has happened yet. The later `fabrik destroy` is a NEW decision: the hub session that runs it mints a superseding ONE-WAY row carrying the § Binding field block in THAT change (rows are immutable — never "grow" an existing one); this run only NAMES that obligation alongside the teardown command | the row, quoted |
| Runtime teardown | — | NAMED as the operator's own `fabrik destroy` call, or n/a | — never executed here |

## Output (always, last thing)

Two forms; which one you emit depends on whether Phase 2 ran.

**Paused at Phase 1.5**: close with `python3 scripts/command_run.py handoff --command fabrik-decommission --resume <a file holding this block under a ## RESUME heading> --reason "awaiting operator confirmation at Phase 1.5" --feedback …`, never `done`, since nothing has executed.

```
DECOMMISSION: AWAITING OPERATOR CONFIRMATION — outcome <A|B|C> proposed, evidence attached
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: n/a (pre-execution)
RECEIPTS: n/a (pre-execution)
RUNTIME TEARDOWN: n/a (pre-execution)
```

Where `<A|B|C>` is the Phase 1 outcome by name (`archive-source-only` | `full decommission` | `migrate-consumers-first`) and "evidence attached" means the Phase 0 consumer-sweep hits + liveness verdict were presented alongside this block, per Phase 1.5.

**Executed** (operator confirmed, Phase 2 ran to completion):

```
DECOMMISSION: <name> — outcome: archive-source-only | full decommission | migrate-consumers-first
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: tracked <before>→<after>, uncommitted <before>→<after>, total <before>→<after> — match | MISMATCH
RECEIPTS: all <N> surfaces reconciled (N = the Receipts-table row count — count the table, never restate a literal; counts drift) | outstanding: <name them>
RUNTIME TEARDOWN: named for the operator (`fabrik destroy specs/services/<id>.yaml`) | n/a — service stays live
```

Next command: none; after *full decommission* the operator's own `fabrik destroy specs/services/<id>.yaml` is next, never auto-chained; after *migrate-consumers-first*, the named blockers are the next work, owned by whichever project carries each consumer.

{{include:close-chain}}
