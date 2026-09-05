---
description: Force a workflow ARTIFACT to converge to a no-op — the shared paired review for the PRODUCER doers /fabrik-vision and /fabrik-epics (the `type` you pass — `vision-summary` · `epic-decomposition` · `expanded-epic-files` — names the ARTIFACT you hand it; Phase-0 table). Give it the artifact path + its type. (Not the cross-epic validation — that loop is /fabrik-epics-review's own.) Fan-outs finders, fixes, loops to a no-op; the doer produces, THIS forces convergence. TRIGGER — EN: "converge this workflow artifact", "review the epic or ticket breakdown"; TR: "bu workflow çıktısını sağlamlaştır", "epic/ticket taslağını incele" — fires on a workflow ARTIFACT, not source code. SKIP: source code review (→ /fabrik-review, /fabrik-repo-review). Stage: gate.
argument-hint: "<artifact path> <type — one of the Phase-0 table values>"
---

Converge one workflow artifact to a fixed point. This is to the `-fabrik` doer commands what `/fabrik-spec-review` is to `/fabrik-spec`: the separate, fresh-context pass that forces the no-op the doer's own blind-spot-sharing context won't reach. **One lean template** — the loop is artifact-neutral; only the `type` argument selects the yardstick (CC1: "thin files, not ten more heavy ones").

Reads (open NOTHING else to act): the artifact under review · its upstream (the Vision Summary for a decomposition or an expanded epic; the research or interview inputs for a vision) · the doer twin's own `## Acceptance Criteria` · **the checklist Phase 0 names** (see Phase 0 — reference it **by path, never by an item count**). Everything the artifact cites is provenance — do not open it to review; if the artifact's claim can't be acted on without opening a cited file, that IS a finding (the applicable checklist's **hollow-citation** item).

{{include:run-record}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:subagents-core}}
## Phase 0 — Scope (the `type` selects the folder + its yardstick)

Args name the **artifact path** + its **type**. If unset, infer from the path and state it.

| Folder | `type` values | Yardstick checklist (by path) |
|---|---|---|
| **`mega-epic-breakdown/`** (mega) | `vision-summary` · `epic-decomposition` · `expanded-epic-files` | `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` |

Load the matching doer twin's `## Acceptance Criteria` and the checklist items that twin's `[canonical: …]` provenance tags point at — those two ARE the yardstick. ⚠️ **Never hard-code an item count** — read the checklist; counts drift. Record the artifact's `md5sum`.

## Phase 1 — Finders (recall), pool + native Opus

Dispatch finders in parallel, each owning a different failure class, against the artifact + its acceptance criteria + the yardstick items. **Both layers, per `62-using-subagents.md`:** the **pool breadth** layer via `fanout("review", units, repo=…, project="mega-review" (the label the mega chain's twins share — it must MATCH Phase 3's back-fill, and omitting it records NOTHING, making that back-fill an orphan-writer), mode="read_only")` **AND ≥1 native `fabrik-reviewer` on Opus** (the authoritative pass — the pool never runs Opus). Cover, across finders, the classes THIS artifact can fail — locate each by NAME in the checklist (item numbers drift):

- **Field completeness / propagation** — every field the acceptance criteria require is present, valued, and consistent with the upstream artifact (Path A vs Path B; nothing silently dropped).
- **Trigger-vs-value** (the *feature-vs-scaffold / N-A-contradicts-its-trigger* item) — an `N/A` whose reason contradicts its trigger (e.g. `Responsive: N/A` on `shape.is_public: true` + HTML) is a violation, not a pass.
- **Flavor branch** (the *"Retrofit-epic special-case missing"* item) — Success-Criteria count, deploy-vs-gate criterion, closure applied correctly for the epic's flavour.
- **Hollow citation** (the *hollow-citation* item) — any claim the reader can't act on without opening a cited file → the artifact must inline the decision or tag `[canonical: …]`.
- **Dangling citation** — a cited path that is archived or no longer exists (verify with `ls`/`Read` before accepting it).
- **Grounding** — every external/vendor claim carries a fresh cited source (re-verify LIVE via exa/brave/firecrawl/official-docs WebFetch when the artifact touches a vendor); a memory-based external claim is a defect.
- **Cross-artifact seams** — the artifact contradicts nothing upstream produced. *(mega types: also the decomposition contract — `Owned paths:` disjoint across a `Parallel with:` set, `Produces`/`Consumes` matched, at most one epic owning migrations.)*

Each finder names a concrete failure scenario. YOU keep refute/merge/decide.

## Phase 2 — Verify / refute

Dedup; for each candidate try to REFUTE from the real source (quote the line/anchor that disproves it). Refute only when provably impossible or factually wrong — never merely for being rare. Log every candidate raised (including refuted ones) in the ledger; a fix is an edit → the md5 changes → the next pass is owed. A pass whose refutations leave the artifact unchanged still converges only via the md5-verified, edit-free round.

## Phase 3 — Fix + re-check

Fix every survivor in the artifact (route the fix to the artifact, not the doer command). **One
disposition fork the seams class needs stated: when a cross-artifact finding shows the ARTIFACT right
and its UPSTREAM stale, the fix routes one step up — re-run THIS review on the upstream artifact
(`/fabrik-workflow-review <vision path> vision-summary` for a stale Vision Summary behind a
decomposition or an expanded epic; `… epic-decomposition` for a stale cut behind an expanded epic),
or the upstream's own doer when it must change (`/fabrik-vision` for the vision, `/fabrik-epics` for
the cut) — and the downstream then re-derives from the changed upstream; routing is not
convergence. This loop never edits the upstream, and "fix the artifact into agreeing with a stale
upstream" is the wrong direction.** Re-run the yardstick. Back-fill the flywheel with the same label: `set_quality(r.agent_id, 0–5, project="mega-review", task_type="review", model=r.model)`. Then run the next full pass.

## Phase 4 — Gate + converge

`python scripts/final_gate.py --check --json` → `"status":"success"`. Reproduce the Pass Ledger with the md5 start==end proof on the final row. Do NOT say "converged" without it (CLAUDE.md convergence HARD STOP).

## After convergence — autonomous

The loop is **autonomous for every type this skill serves**: converge and return control to the orchestrator so the next stage runs without a human stop.

⚠️ This skill does **not** own either human gate, and neither gate is a `type` here `[canonical: north star § Human gates — R14: "Exactly two gates: plan approval in, deploy approval out"]`. **Plan-in** is the operator's approval of the spec/plan **upstream at the front door** — `/fabrik-spec-review` is the command that stops for it `[canonical: north star R25 — "/fabrik-spec-review stops for operator approval; /fabrik-plan-review runs to no-op autonomously"]`; by the time a mega artifact reaches this review, that gate has already passed. **Deploy-out** is Gate 2 before `/fabrik-deploy` — the operator's explicit go, with the deploy triad (`fabrik apply` underneath, never typed by hand) running after it. Likewise the doer whose paired review is a dedicated command is NOT a type here: the cross-epic validation of `/fabrik-epics`' output belongs to `/fabrik-epics-review`, which self-converges. This skill is the shared review for the **producer** doers only — `/fabrik-vision` (`vision-summary`) and `/fabrik-epics` (`epic-decomposition` · `expanded-epic-files`).

Never leave a non-no-op ledger row for the operator to re-invoke. Converge here.
