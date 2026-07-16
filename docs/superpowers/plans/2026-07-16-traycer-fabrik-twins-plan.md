# Plan — Traycer workflow `-fabrik` twins (both folders)

Status: CONVERGED (via /fabrik-plan-review; re-converged after inheriting the spec's Capability-delta dimension — pool + native Opus to an md5-stable no-op; Phase 0 done, Phase A/B/C ready to execute)
Date: 2026-07-16
Spec: `docs/superpowers/specs/2026-07-16-traycer-fabrik-twins-design.md`
Governs: `docs/traycer/mega-epic-breakdown/**` + `docs/traycer/epic-to-ticket-workflow/**`

## The per-twin pipeline (revised CC6 — applied per twin, step 3's depth scaled to the twin's role)

1. **Ground** — read the real code + cited files for every claim (anchors, counts, triggers). The stale `-command` source is a map of what to verify, not truth.
2. **Write** the twin directly from that grounding — CC2 citations (provenance / inlined / zero hollow), a `Reads:` header, tool-capable, disk-reads. Accurate by construction. **Close the capability delta** (spec § Capability-delta litmus): the twin must actually USE every Fabrik capability its role needs — disk-reads (all); shell/gate (all); **live research** (`fanout("research")`) where it touches external facts; **subagent dispatch where the role needs it** — the coders/finders that produce for ettw `06`/`07` and the review twins; for the **mega doers, the grounding/research legs only** (the synthesis stays the driving Opus's, per the spec's decision); convergence. A re-format with no dispatch/research where the role needs it is NOT done.
3. **Converge to a no-op — depth scaled by role** (per the spec's role-parity matrix): a **doer** via its **paired review** (CC1: **pool `fanout("review")`** recording the flywheel **+ ≥1 native `fabrik-reviewer` on Opus**); a **review twin** (`08`/`10`/mega `04`) via its **own** finder loop-to-no-op (it has no downstream paired review); the human-gated `11` and thin dispatcher `05` via a **grounding+consistency pass** (pool + native Opus verifying accuracy/consistency, not the full doer loop). Every variant loops inside one invocation until a full pass changes nothing (Pass Ledger, `md5(start)==md5(end)`).
4. **Checklist-eval** (0-FAIL) against the folder's checklist: **ettw** → `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` (132 items, incl. the item-132 hollow-citation audit); **mega** → `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` (101 items, 102 after B1) — which currently has **no** hollow-citation item, so apply the CC2 hollow-citation discipline directly, and Phase B1 **adds** an equivalent item to the mega checklist (a parity gap) before the mega twins run their checklist-eval.
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
- **A3.** **Grounding+consistency pass** on the twin (pool + native Opus verifying accuracy + consistency to a no-op) — `11` is a human-gate doc, not an autonomous doer, so this is the grounding+consistency depth (step 3's `11` variant), **not** the full doer paired-review loop.
- **A4.** Checklist (`EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`, incl. item-132 hollow-citation).
- **A5.** Gate + commit; fix the `11-command` load-bearing anchors.
- **Gate:** `final_gate.py --check` → success; Pass Ledger ends `found:0, fixed:0`, md5 stable.

## Phase B — mega review infrastructure

**B1 — Build `/fabrik-mega-review <artifact-path> <type>`** (sibling of `/fabrik-ettw-review`, `type ∈ {trigger, decomposition, expanded-epic-files}`):
- Copy the lean template (termination contract + finder fan-out + checklist + gate) from `~/.claude/commands/fabrik-ettw-review.md`; retarget the yardstick to `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` and the mega artifact types.
- **Add a hollow-citation item to the mega checklist** (the ettw item-132 equivalent — the mega checklist lacks one) so the mega twins have the CC2 audit as an explicit yardstick item.
- Converge the skill itself to a no-op (review its own prose), gate, commit.

**B2 — Rebuild `04-cross-epic-validation-fabrik` to the review discipline** (the biggest gap — currently a single-pass "quality auditor" with no pool+native, no loop):
- Ground the cross-epic dimensions against `04-cross-epic-validation-command.md` + `mega-epic-breakdown/03-expand-epic-files-fabrik` (epic-file structure) + `02-epic-decomposition-fabrik` (the compact-entry contract).
- Write it as the mega analog of ettw `10`: pool `fanout("review")` + native Opus finders across the cross-epic seams (owned-paths disjointness, Produces/Consumes contracts, parallel-set gates, Compliance-Report rows), surgical fixups vs route-to-re-decompose, loop-to-no-op, 3 BLOCKED halts.
- Converge via its **own** finder loop-to-no-op (native Opus + pool on the twin's prose) — `04` is a review twin, so it self-converges (step 3's review-twin variant); it has no downstream paired review, and `/fabrik-mega-review`'s type enum (`trigger`/`decomposition`/`expanded-epic-files`) has no review-artifact slot. Checklist, gate, commit; fix the `04-command` anchors.

## Phase C — mega doer parity (`00`/`02`/`03`, light `05`)

Each brought to parity via the pipeline. The mega **doers** `00`/`02`/`03` converge via **`/fabrik-mega-review`**; `05` (thin dispatcher, C4) gets only a grounding+consistency pass (not a paired review):

- **C1 — `00-trigger-fabrik`** (spec-role) — add the `/fabrik-spec` **BLOCKING live-research grounding gate** to its existing fabrik-lib verdict + rejected-alternatives; add `Reads:` + CC2; converge. **Capability:** the live-research gate runs through **`fanout("research")`** grounders (parallel — one per external fact / best-practice, exa/brave/firecrawl/context7); the **vision synthesis stays the driving Opus's** (the Traycer twin can run neither).
- **C2 — `02-epic-decomposition-fabrik`** (plan-role) — add `Reads:` + CC2, the decomposition-consistency checks (owned-paths disjoint, Produces/Consumes, parallel budget), converge. **Capability:** disk-reads the real vision/codebase for grounding; the **decomposition itself is single-agent Opus judgment** (like `/fabrik-plan-after-chat`), MAY fan out grounders for the consistency checks — no producing fan-out.
- **C3 — `03-expand-epic-files-fabrik`** (spec/doc-role) — add `Reads:` + CC2, ground the epic-file field set against `01-epic-brief-fabrik`'s INFRA-CHECK canonical (Path A = 10 required + 3 SaaS-conditional; Path B = 16 — 13 required incl. Registrars/Universal-categories/Epic-Flavor + 3 SaaS-conditional; `01` line 90 states this consistently), converge. **Capability:** the epic files are independent units → **dispatch one grounder per epic file** (a genuine per-unit fan-out — like `/fabrik-spec`'s per-dep `fanout("research")`, not a single batched agent) for the per-epic field grounding; Opus synthesizes each file.
- **C4 — `05-dispatch-epic-tickets-fabrik`** — the lightest grounding+consistency pass (step 3's `05` variant): a `Reads:` header + verify it correctly hands each epic to the ettw chain + a pool+native consistency check to a no-op — thin (no deep grounding), since its real reviews live downstream in ettw.
- **Gate (per item):** `final_gate.py --check` → success; each Pass Ledger ends `found:0, fixed:0`, md5 stable; fix each `-command` anchor.

## Execution order + dependencies

`A` (independent) → `B1` (blocks C — the review tool) → `B2` → `C1` → `C2` → `C3` → `C4`. `A` may run before or in parallel with `B`. Each item runs to its own no-op before the next starts (no partial twins).

## Self-audit

- Every phase item names its real target file(s) and the pipeline step that proves completion (a converged Pass Ledger + gate green + commit SHA).
- Every phase item passes the **capability-delta litmus** (spec § Capability-delta): it USES the Fabrik capabilities its role needs — the mega-doer subagent-dispatch decision is baked into C1 (research fan-out) / C2 (single-agent + optional grounder fan-out) / C3 (per-epic grounders).
- GUI/coding are intentionally absent — the mega tier delegates them to the ettw per-epic chain (spec § Scope).
- No hard-coded roster or checklist count enters any twin (spec § Residuals).

## Residuals

- `B2` (rebuild `04`) is the largest single item — it goes from prose auditor to a converging pool+native review; budget the most rounds there (ettw `10` took 4).
- Shared-tree: sibling AIs edit both folders concurrently; commit explicit paths only, `git fetch` + fast-forward before push, never touch a sibling's file.
- Traycer retirement: if the owner retires Traycer mid-plan, the source-anchor-fix step (pipeline #6) is dropped and the `-command` sources are left as legacy.
