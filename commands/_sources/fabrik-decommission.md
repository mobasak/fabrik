---
description: Retire a project or service safely: ground truth first (hub-side liveness probe vs sibling domains, fleet consumer sweep — never a catalog/PORTS/env row as evidence), then one of three named outcomes (archive-source-only, full decommission, migrate-consumers-first), an operator confirmation gate, and only then the source move + hub bookkeeping. Runtime teardown is always a separate, operator-gated step. Stage: utility. TRIGGER — EN: "retire this project", "decommission this service", "archive and shut down X"; TR: "bu projeyi emekliye ayır", "bu servisi kapat ve arşivle" — fires bare-prose, no slash command needed.
argument-hint: "<project or service name to retire — omit to be asked>"
---

Retire ONE named project/service the way the wpf + captcha retirements (2026-08-07) should have gone
from the start: ground truth before any move, three explicit outcomes instead of one silent guess, and
runtime teardown that is NEVER this command's own decision. Run this from the hub (`/opt/fabrik`) — it
needs fleet DNS/SSH reachability a project-side agent does not have (deploy is trigger-not-execute for
projects; the hub is the execution side).

## ⚠️ Termination contract

This is a bounded GROUND TRUTH → DECIDE → CONFIRM → EXECUTE run for ONE name, not an open loop. Phase 0
must finish in full — both the liveness probe AND the consumer sweep — before Phase 1 states an outcome,
and Phase 1 must state one of the three named outcomes explicitly before the Phase 1.5 operator
confirmation gate, which must itself receive the operator's explicit go-ahead before Phase 2 touches a
single file. You are done only when Phase 2's **receipts table** accounts for every bookkeeping surface
(source location, file count, catalog, fleet audit, PORTS row, spec disposition, memory record,
runtime-teardown disposition) with `path:line` or command-output evidence — a cell filled from memory
instead of a fresh command is not a receipt. Runtime teardown (containers, Traefik route, registrar
entries, DNS, Gatus probe) is NEVER one of this run's own actions, in any outcome — it is always NAMED as
a separate, explicitly operator-gated follow-up, never executed inline. Two legitimate stops, both before
Phase 2: (1) the consumer sweep finds a live blocking consumer with no migration path — name it, stop,
that is outcome C; (2) Phase 1.5's confirmation has not yet been given — present the Phase 0 evidence +
the Phase 1 outcome and WAIT; an outcome stated but not confirmed is not yet actionable.

{{include:grounding-artifact}}
## Phase 0 — GROUND TRUTH (read-only; no move yet)

1. **Consumer sweep.** Grep every fleet project's `.env`, `.env.example`, `specs/services/*.yaml`, and
   code for the target's hostname, URL, API base, or import path (`grep -rn` across `/opt/*` excluding
   `/opt/archived/`). Enumerate every hit with `path:line` — a project referencing the target is a
   consumer whether or not it currently calls the reference.
2. **Liveness probe — DNS vs siblings, never registry rows.** Resolve the target's public domain
   (e.g. `dig +short <name>.vps1.ocoron.com` or `getent hosts`) in the SAME probe run as two KNOWN-LIVE
   sibling domains on the same VPS — VERIFY they resolve before trusting them as controls (e.g.
   `status.vps1.ocoron.com` plus a live spec domain; `gatus.vps1`/`grafana.vps1` are NXDOMAIN — the
   dead-sibling trap; on vps2/vps3 wildcard DNS makes bare resolution non-evidentiary, so the
   discriminating evidence moves to the HTTPS layer, per `/fabrik-deploy-verify`'s control probe). Three
   outcomes only: target resolves → LIVE. Target fails AND both siblings resolve → DEAD (absence proven —
   this is the discriminator: a real retirement looks like THIS, not "everything timed out"). Target AND
   siblings ALL fail → inconclusive transient outage — re-probe later, this is not a verdict either way.
   Where the host is directly reachable, cross-check with a container/compose check on that VPS — never
   conclude dead from an unreachable host (that is an outage, not an absence). **Never** treat a catalog
   row, `PORTS.md` row, a `specs/services/*.yaml` file's mere existence, or a `.env` reference as evidence
   of liveness either way — the captcha case is the cautionary tale: the catalog/env rows still read
   "live" after the service's DNS record was already gone (`CHANGELOG.md` § "Removed — captcha.vps1.ocoron.com torn down…" (2026-08-07) — the corrected finding).
   The archived-source ≠ dead-service principle itself rests on the MECHANISM, not on any changelog
   anecdote: a hub-side `mv /opt/<name> /opt/archived/<name>` only relocates the SOURCE tree — it never
   touches the VPS runtime. The only thing that does is `fabrik destroy` (`_destroy_compose`'s `docker
   compose down` + remote `rm -rf`, `src/fabrik/orchestrator/destroyer.py:338-340`). So source location
   proves nothing about liveness in EITHER direction — archived source implies neither a live service nor
   a dead one. (One retirement entry briefly asserted "the deployed service stays live" and was corrected
   the SAME DAY by a fresh DNS probe — `CHANGELOG.md` § "Changed — captcha project retired and archived; the deployed service stays live" (2026-08-07, the RETRACTED claim) is cited here only as the retracted claim
   itself, a cautionary tale about probe-vs-registry-row, never as evidence that anything stayed live.)
   Only a probe run THIS session counts.

## Phase 1 — DECIDE (state exactly one, before touching a file)

| Outcome | When | What happens |
|---|---|---|
| **archive-source-only** | Liveness probe = LIVE, and/or the consumer sweep found a live consumer with no migration need yet | Phase 2 moves the SOURCE project only; the deployed service is untouched — `CHANGELOG.md` § "Changed — wpf retired and archived" (2026-08-07)'s wpf precedent (8 uncommitted files preserved exactly across the move) is the clean archive-source-only case. Captcha's move preserved 6 files the same way, but its "service stays live" claim was ITSELF RETRACTED the SAME DAY after a fresh DNS probe (`CHANGELOG.md` § "Removed — captcha.vps1.ocoron.com torn down…" (2026-08-07)) — the file-preservation figure still stands, the liveness claim doesn't; that gap is the cautionary tale behind Phase 0 step 2's only-a-probe-run-THIS-session rule |
| **full decommission** | Liveness probe = DEAD, and no live consumer remains | Phase 2 moves the source AND names runtime teardown as a separate operator-gated step (below) — never executes it |
| **migrate-consumers-first** | Consumer sweep found ≥1 live consumer with NO migration path named | STOP here. List each blocking consumer (`path:line`) + what it needs (e.g. an equivalent `fabrik-lib/<module>` capability, the captcha → `fabrik-lib/captcha-solve` precedent) — do not proceed to Phase 2 |

**Runtime teardown, named but never run here** (only reachable from *full decommission*): containers /
compose app, the Traefik route, every registrar entry the spec's `shape:` block provisioned (GlitchTip
project, Gatus endpoint, Meilisearch index, Authelia rule, Backrest plan, Postgres/Redis if
`--drop-data`), the DNS A record, and the Gatus probe itself. The hub-side tool that reverses these is
`fabrik destroy specs/services/<id>.yaml` (`src/fabrik/cli.py:976` — reverses MeiliSearch, Authelia,
GlitchTip, Backrest, Gatus, and Postgres/Redis registrars, then the compose app and DNS record; examples
at `src/fabrik/cli.py:997-999`). Cite it here for the operator to run themselves — this command never
shells out to it and never decides to run it. That compose-destroy step is itself irreversible on the
remote side: `_destroy_compose` runs `docker compose down` then `sudo rm -rf /opt/<name>` ON THE VPS
(`src/fabrik/orchestrator/destroyer.py:338-340`) — the remote tree is wiped even though this command's own
hub-side move to `/opt/archived/<name>` is preserved untouched; that VPS-side wipe, not the hub-side
archive, is what makes a *full decommission* irreversible.

## Phase 1.5 — OPERATOR CONFIRMATION (mandatory stop, before any tree or bookkeeping mutation)

Present the Phase 0 evidence (consumer sweep hit count + files, the liveness verdict) and the Phase 1
outcome chosen, then STOP. Do not proceed to Phase 2 on inference or silence — wait for the operator's
explicit go-ahead. This gate applies to all three outcomes, not just *full decommission*: even
*archive-source-only* moves a tree and edits hub bookkeeping, which is exactly the class of action this
command exists to gate rather than silently execute.

## Phase 2 — EXECUTE (source move + hub bookkeeping only — never runtime teardown)

1. **Count before.** `git -C /opt/<name> ls-files | wc -l` (tracked), `git -C /opt/<name> status
   --porcelain | wc -l` (uncommitted), and `find /opt/<name> -type f | wc -l` (raw total — catches
   gitignored files the other two counts blind-spot). Record all three.
2. **Collision guard, then move.** `test ! -e /opt/archived/<name>` first — if that fails (the
   destination already exists, e.g. a prior partial retirement), STOP: do not overwrite, ask the operator
   whether to reuse it or append a `-<YYYYMMDD>` suffix (`/opt/archived/<name>-<YYYYMMDD>`) before
   proceeding. Once clear: `mv /opt/<name> /opt/archived/<name>` — atomic only when `/opt` and
   `/opt/archived` share a filesystem (the fabrik convention); across a filesystem boundary `mv` silently
   falls back to copy-then-unlink, which CAN drop a file mid-copy — the before/after count in step 3 is
   what actually proves nothing was lost, and matters most in that cross-device case.
3. **Count after.** Re-run the same three counts at the new path. All three MUST match the "before"
   counts exactly — the wpf move preserved 8 uncommitted files, the captcha move preserved 6
   (`CHANGELOG.md` § "Changed — captcha project retired and archived; the deployed service stays live" (2026-08-07, the RETRACTED claim), `CHANGELOG.md` § "Changed — wpf retired and archived" (2026-08-07)) precisely because this was verified, not assumed. A mismatch is a
   CRITICAL failure: stop, do not proceed to bookkeeping, report the discrepancy.
4. **Hub bookkeeping** (each step is the mechanism, not a hand-edit):
   - `python scripts/sync_projects.py` — regenerates `data/projects.yaml` + `docs/PROJECT_CATALOG.md`.
     The move itself does the exclusion work: `scan_projects()` walks `root.iterdir()` over `/opt/*`
     top-level only and checks each name against `DEFAULT_EXCLUDES`, which already contains the literal
     `"archived"` (`scripts/sync_projects.py:35-42`, checked at `:109-123`) — so `/opt/archived/<name>`
     is never visited once the move lands. Never hand-edit the catalog.
   - `python scripts/fleet_doc_audit.py` — regenerates the fleet audit report. Same location-based
     mechanism: `_excluded()` imports `sync_projects._is_excluded` (`scripts/fleet_doc_audit.py:43-60`) —
     by LOCATION, never a hardcoded name list (a hardcoded `RETIRED` set was tried and removed as dead
     code + a silent revival trap, `CHANGELOG.md` § "Removed — captcha.vps1.ocoron.com torn down…" (2026-08-07)). Do not add one back.
   - `PORTS.md` — annotate the project's row RETIRED + date + reason (never delete the row silently).
   - **Spec disposition.** If outcome was *full decommission* AND the operator has since confirmed the
     separately-gated runtime teardown actually ran: `git rm specs/services/<id>.yaml`. If outcome was
     *archive-source-only*, or teardown hasn't run yet: annotate the spec's header comment
     (source archived, service still deployed) — never delete a spec for a service still running. A spec
     left behind after a REAL teardown is an orphan trap: `fabrik apply` would resurrect the service and
     every fleet audit keeps counting it — exactly how `captcha.yaml` sat orphaned for weeks
     (`CHANGELOG.md` § "Removed — captcha.vps1.ocoron.com torn down…" (2026-08-07)).
   - **Memory record** — one entry that states BOTH facts as separate, dated clauses even when they land
     in the same note: "source archived to `/opt/archived/<name>` on `<date>`" is NOT "the service is
     decommissioned" — conflating them is the exact defect this command exists to prevent (a real entry
     briefly claimed "the deployed service stays live" after the service was in fact already dead;
     corrected only by a fresh DNS probe, `CHANGELOG.md` § "Removed — captcha.vps1.ocoron.com torn down…" (2026-08-07)).
   - CHANGELOG entry per the Doc Sync Matrix (`Changed` for archive-source-only, `Removed` once a real
     teardown lands).

## Receipts (Termination — every row filled with evidence, or the run isn't done)

A run that stops at Phase 1.5 (the mandatory operator-confirmation gate) has not reached Phase 2 and owes
none of these rows yet — it emits the AWAITING form of the Output block instead, with FILES and RECEIPTS
both marked `n/a (pre-execution)`. Paused runs emit the AWAITING form; only EXECUTED runs (operator
confirmed, Phase 2 ran) owe this 8-surface reconciliation.

| Surface | Before | After | Evidence |
|---|---|---|---|
| Source location | `/opt/<name>` | `/opt/archived/<name>` | `ls` / the move command's own output |
| File count | tracked N, uncommitted N, total N | same three, re-counted | exact match or CRITICAL stop |
| Catalog (`data/projects.yaml`) | listed | excluded | `sync_projects.py` run output |
| Fleet audit | scanned | excluded | `fleet_doc_audit.py` run output |
| `PORTS.md` row | live | RETIRED + date + reason | diff |
| Spec (`specs/services/<id>.yaml`) | present | `git rm`'d (real teardown) or annotated (source-only) | diff / `git rm` output |
| Memory record | — | written, archived-source vs dead-service stated separately | quoted entry |
| Runtime teardown | — | NAMED as the operator's own `fabrik destroy` call, or n/a | — never executed here |

## Output (always, last thing)

Two forms — which one you emit depends on whether Phase 2 ran.

**Paused at Phase 1.5** (the mandatory stop — outcome stated, operator go-ahead not yet given):

```
DECOMMISSION: AWAITING OPERATOR CONFIRMATION — outcome <A|B|C> proposed, evidence attached
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: n/a (pre-execution)
RECEIPTS: n/a (pre-execution)
RUNTIME TEARDOWN: n/a (pre-execution)
```

Where `<A|B|C>` is the Phase 1 outcome by name (`archive-source-only` | `full decommission` |
`migrate-consumers-first`) and "evidence attached" means the Phase 0 consumer-sweep hits + liveness verdict
were presented alongside this block, per Phase 1.5.

**Executed** (operator confirmed, Phase 2 ran to completion):

```
DECOMMISSION: <name> — outcome: archive-source-only | full decommission | migrate-consumers-first
CONSUMER SWEEP: <N refs across <M> files | none>
LIVENESS: live | dead (siblings resolved, target didn't) | inconclusive (re-probe — siblings also failed)
FILES: tracked <before>→<after>, uncommitted <before>→<after>, total <before>→<after> — match | MISMATCH
RECEIPTS: all 8 surfaces reconciled | outstanding: <name them>
RUNTIME TEARDOWN: named for the operator (`fabrik destroy specs/services/<id>.yaml`) | n/a — service stays live
```

Next command: none in the pipeline — this is a standalone hub-side runbook. If the outcome was *full
decommission*, the operator's own `fabrik destroy specs/services/<id>.yaml` run is the next action (never
auto-chained from here); if it was *migrate-consumers-first*, the named blockers are the next work, owned
by whichever project carries each consumer.
