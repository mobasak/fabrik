---
description: Force a workflow ARTIFACT to converge to a no-op — the shared paired review for the PRODUCER doers /fabrik-vision and /fabrik-epics (the `type` you pass — `vision-summary` · `epic-decomposition` · `expanded-epic-files` — names the ARTIFACT you hand it; Phase-0 table). Give it the artifact path + its type. (Not the cross-epic validation — that loop is /fabrik-epics-review's own.) Fan-outs finders, fixes, loops to a no-op; the doer produces, THIS forces convergence. TRIGGER — EN: "converge this workflow artifact", "review the epic or ticket breakdown"; TR: "bu workflow çıktısını sağlamlaştır", "epic/ticket taslağını incele" — fires on a workflow ARTIFACT, not source code. SKIP: source code review (→ /fabrik-review, /fabrik-repo-review). Stage: gate.
argument-hint: "<artifact path> <type — one of the Phase-0 table values>"
---

> **⚠️ POOL OFF — D-181.** Run every fan-out natively with Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose), skip every flywheel back-fill, and never write `NO-POOL:`. Canonical: `62-using-subagents.md` § Dispatch policy.

Reads (open NOTHING else to act): the artifact · its upstream (Vision Summary, or the research inputs for a vision) · the doer twin's `## Acceptance Criteria` · the Phase 0 checklist. Everything the artifact cites is provenance, not to be opened to review; a claim that can't be acted on without opening a cited file IS a finding (**hollow-citation**).

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}
{{include:grounding-artifact}}

{{include:subagents-core}}
## Phase 0 — Scope (the `type` selects the folder + its yardstick)

Args: artifact path + type; if unset, infer from the path and state it.

| Folder | `type` values | Yardstick checklist (by path) |
|---|---|---|
| **`mega-epic-breakdown/`** (mega) | `vision-summary` · `epic-decomposition` · `expanded-epic-files` | `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` |

The doer twin's `## Acceptance Criteria` plus the checklist items its `[canonical: …]` tags point at ARE the yardstick. Never hard-code an item count — read the checklist. Record the artifact's `md5sum`.

## Phase 1 — Finders (recall), native seats

Dispatch finders in parallel, one failure-class GROUP each, in one message: a Sonnet `fabrik-reviewer` per group plus the Haiku seats `dispatch_headroom.py --units <groups>` prints (D-191), AND at least one Opus `fabrik-reviewer`. Collapse classes so no finding is claimed by two groups; the group count is `--units`, never a token 1–2. Classes, each located by NAME in the checklist:

- **Field completeness / propagation** — every required field is present, valued and consistent with upstream.
- **Trigger-vs-value** — an `N/A` whose reason contradicts its trigger (e.g. `Responsive: N/A` on `shape.is_public: true` + HTML) is a violation.
- **Flavor branch** (*"Retrofit-epic special-case missing"*) — Success-Criteria count, deploy-vs-gate criterion and closure fit the epic's flavour.
- **Hollow / dangling citation** — inline the decision or tag `[canonical: …]`; verify a cited path exists with `ls`/`Read`.
- **Grounding** — every external/vendor claim carries a fresh cited source, re-verified LIVE via exa/brave/firecrawl/official-docs WebFetch; a memory-based external claim is a defect.
- **Cross-artifact seams** — nothing contradicts upstream. *(Mega types: also `Owned paths:` disjoint across a `Parallel with:` set, `Produces`/`Consumes` matched, at most one epic owning migrations.)*

Each finder names a concrete failure scenario. YOU keep refute/merge/decide.

## Phase 2 — Verify / refute

For each deduped candidate try to REFUTE from the real source (quote the line that disproves it). Refute only when provably impossible or factually wrong — never merely for being rare. Log every candidate, refuted ones too; a fix changes the md5, so the next pass is owed. Convergence comes only from the md5-verified closing round at `confirmed: 0`.

## Phase 3 — Fix + re-check

Fix every survivor in the artifact, not the doer command. When the ARTIFACT is right and its UPSTREAM stale, re-run THIS review on the upstream (`/fabrik-workflow-review <vision path> vision-summary`, or `… epic-decomposition` for a stale cut) or its doer (`/fabrik-vision`, `/fabrik-epics`), then re-derive the downstream. This loop never edits the upstream, and "fix the artifact into agreeing with a stale upstream" is the wrong direction. Re-run the yardstick, then the next full pass.

## Phase 4 — Gate + converge

`python scripts/final_gate.py --check --json` → `"status":"success"`. Reproduce the Pass Ledger with the md5 start==end proof on the final row. Do NOT say "converged" without it (CLAUDE.md convergence HARD STOP).

## After convergence — autonomous

Return control to the orchestrator so the next stage runs without a human stop. This skill owns neither human gate `[canonical: north star § Human gates — R14: "Exactly two gates: plan approval in, deploy approval out"]`: plan-in is approved upstream (`/fabrik-spec-review` stops for it), deploy-out is Gate 2 before `/fabrik-deploy`, the deploy triad (`fabrik apply` underneath, never typed by hand) running after it. The cross-epic validation belongs to `/fabrik-epics-review`, which self-converges. This skill is the shared review for the producer doers only: `/fabrik-vision` (`vision-summary`) and `/fabrik-epics` (`epic-decomposition` · `expanded-epic-files`). Never leave a ledger row whose `confirmed:` is non-zero for the operator to re-invoke.

{{include:close-chain}}
