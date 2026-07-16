# Plan — Traycer workflow `-fabrik` twins (both folders)

Status: IN PROGRESS
Date: 2026-07-16
Spec: `docs/superpowers/specs/2026-07-16-traycer-fabrik-twins-design.md`
Governs: `docs/traycer/mega-epic-breakdown/**` + `docs/traycer/epic-to-ticket-workflow/**`

## The per-twin pipeline (revised CC6 — applied to every item below)

1. **Ground** — read the real code + cited files for every claim (anchors, counts, triggers). The stale `-command` source is a map of what to verify, not truth.
2. **Write** the twin directly from that grounding — CC2 citations (provenance / inlined / zero hollow), a `Reads:` header, tool-capable, disk-reads. Accurate by construction.
3. **Converge to a no-op** via its paired review (CC1) — **pool `fanout("review")` (records the flywheel) + ≥1 native `fabrik-reviewer` on Opus**, loop inside one invocation until a full pass finds nothing AND changes nothing (Pass Ledger, `md5(start)==md5(end)`).
4. **Checklist-eval** against the folder's `EVALUATION_CHECKLIST_*` (0-FAIL) + the item-132 hollow-citation audit.
5. **Gate + commit** — `final_gate.py --check` green; stage explicit paths; `git commit -- <paths>` with provenance trailers.
6. **Stale source** — fix its load-bearing anchors in the same grounding pass (Traycer GUI intact); no convergence loop on the source.

Halt only on the **3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior]`. Shared-tree: never touch a sibling's file; a gate flagging one is a false-positive to report.

---

## Phase 0 — ettw `00`–`10` twins — ✅ DONE

Every ettw doer/review twin from `00-trigger-fabrik` through `10-cross-artifact-validation-fabrik` was built + converged to an md5-stable no-op via the pipeline above, and the shared review skill `~/.claude/commands/fabrik-ettw-review.md` exists.

**Evidence:** `docs/traycer/epic-to-ticket-workflow/{00..10}-*-fabrik.md` all present; recent commits `de0fb8f1` (08), `1fd8dfdb` (09), `f1c246d9` (10), `2472ddb3`/`ed1fe896` (07), `2be6cea7` (06), earlier for 00–05. Each commit records its Pass Ledger + the source anchor fixes.

## Phase A — ettw `11-deploy-fabrik` (the last ettw twin)

`11-deploy-command` is the **deploy-out human gate** (R14's 2nd human gate) — so its twin is **deliberately NOT autonomous**; its shape differs from `07`–`10`. It runs `fabrik apply` under operator control.

- **A1.** Ground `docs/traycer/epic-to-ticket-workflow/11-deploy-command.md` against the real deploy path: `fabrik apply` mechanics, the spec `shape:`→registrar mapping `[canonical: CLAUDE.md § Spec contract awareness]`, the deploy invariants (memory limits, `postgres-main`/`redis-main`, Traefik, container DNS, health-not-behind-auth), and the `git push`→redeploy rule for git-sourced apps.
- **A2.** Write `11-deploy-fabrik` — human-gated (operator runs `fabrik apply`; the driver only prepares + verifies), with the `Reads:` header + CC2 citations. It does NOT auto-deploy.
- **A3.** Converge via `/fabrik-ettw-review <path> deploy` (pool + native Opus) to a no-op.
- **A4.** Checklist (`EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`) + item-132.
- **A5.** Gate + commit; fix the `11-command` load-bearing anchors.
- **Gate:** `final_gate.py --check` → success; Pass Ledger ends `found:0, fixed:0`, md5 stable.

## Phase B — mega review infrastructure

**B1 — Build `/fabrik-mega-review <artifact-path> <type>`** (sibling of `/fabrik-ettw-review`, `type ∈ {trigger, decomposition, expanded-epic-files}`):
- Copy the lean template (termination contract + finder fan-out + checklist + gate) from `~/.claude/commands/fabrik-ettw-review.md`; retarget the yardstick to `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` and the mega artifact types.
- Converge the skill itself to a no-op (review its own prose), gate, commit.

**B2 — Rebuild `04-cross-epic-validation-fabrik` to the review discipline** (the biggest gap — currently a single-pass "quality auditor" with no pool+native, no loop):
- Ground the cross-epic dimensions against `04-cross-epic-validation-command.md` + `mega-epic-breakdown/03-expand-epic-files-fabrik` (epic-file structure) + `02-epic-decomposition-fabrik` (the compact-entry contract).
- Write it as the mega analog of ettw `10`: pool `fanout("review")` + native Opus finders across the cross-epic seams (owned-paths disjointness, Produces/Consumes contracts, parallel-set gates, Compliance-Report rows), surgical fixups vs route-to-re-decompose, loop-to-no-op, 3 BLOCKED halts.
- Converge (its paired review is itself a review — converge via `/fabrik-mega-review` or a native-Opus + pool pass on the twin's prose), checklist, gate, commit; fix the `04-command` anchors.

## Phase C — mega doer parity (`00`/`02`/`03`, light `05`)

Each re-converged to parity via the pipeline, reviewed with **`/fabrik-mega-review`**:

- **C1 — `00-trigger-fabrik`** (spec-role) — add the `/fabrik-spec` **BLOCKING live-research grounding gate** (external facts + best-practice, cited live) to its existing fabrik-lib verdict + rejected-alternatives; add `Reads:` + CC2; converge.
- **C2 — `02-epic-decomposition-fabrik`** (plan-role) — add `Reads:` + CC2, the decomposition-consistency checks (owned-paths disjoint, Produces/Consumes, parallel budget), converge.
- **C3 — `03-expand-epic-files-fabrik`** (spec/doc-role) — add `Reads:` + CC2, ground the epic-file field set against `01-epic-brief-fabrik`'s INFRA-CHECK canonical (Path A 13 / Path B 16), converge.
- **C4 — `05-dispatch-epic-tickets-fabrik`** — light touch: a `Reads:` header + verify it correctly hands each epic to the ettw chain; its real reviews live downstream. No heavy convergence.
- **Gate (per item):** `final_gate.py --check` → success; each Pass Ledger ends `found:0, fixed:0`, md5 stable; fix each `-command` anchor.

## Execution order + dependencies

`A` (independent) → `B1` (blocks C — the review tool) → `B2` → `C1` → `C2` → `C3` → `C4`. `A` may run before or in parallel with `B`. Each item runs to its own no-op before the next starts (no partial twins).

## Self-audit

- Every phase item names its real target file(s) and the pipeline step that proves completion (a converged Pass Ledger + gate green + commit SHA).
- GUI/coding are intentionally absent — the mega tier delegates them to the ettw per-epic chain (spec § Scope).
- No hard-coded roster or checklist count enters any twin (spec § Residuals).

## Residuals

- `B2` (rebuild `04`) is the largest single item — it goes from prose auditor to a converging pool+native review; budget the most rounds there (ettw `10` took 4).
- Shared-tree: sibling AIs edit both folders concurrently; commit explicit paths only, `git fetch` + fast-forward before push, never touch a sibling's file.
- Traycer retirement: if the owner retires Traycer mid-plan, the source-anchor-fix step (pipeline #6) is dropped and the `-command` sources are left as legacy.
