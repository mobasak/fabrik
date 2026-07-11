# Design — Converging doc maintenance (registry-driven, pool-authored + verified, iterate-to-no-op)

Status: CONVERGED
Date: 2026-07-11
Converged: 2026-07-11 (/fabrik-spec-review — 2 passes to an edit-free md5-verified no-op; all 5 best-practice citations re-verified live this session [graphwiki/Cyberax/msiric/DeepDocs/patrickchugh, all 2026]; fabrik-lib pool VENDOR confirmed against the real README `subagents` row which lists a "docs" task; doc-* modules confirmed content-processing/inapplicable; path:line re-grounded — registry 22 rows, check_doc_sync `_staged():64`, 9 sync_projects AUTO-GEN blocks; decomposition verdict added; no BLOCKING unknown)
Scaffold type: fabrik hub itself (extends fabrik's own enforcement + commands + subagent pool; distributed fleet-wide)
Builds on: `docs/superpowers/specs/2026-07-10-doc-registry-reconciliation-design.md` (the type-aware doc registry SSOT — plan-4, EXECUTED)

## Goal

Keep **every** applicable project doc up to date **completely, leanly, fast, cheaply, and accurately** — by making doc-updating an **iterate-to-converge loop** (like `/fabrik-review`) driven by the registry SSOT, where **cheap OpenRouter pool agents author** the prose updates and **native Claude agents verify** them, deterministic docs are **generated with no model**, and a **whole-plan mechanical coverage gate** proves nothing was skipped — at the cheapest cost floor for each property.

Today the forcing is presence-only: `check_doc_sync` (touch-on-change) + `check_doc_stubs` (no-stub) prove a doc was *touched*, and correctness is assumed to come from an expensive coder hand-writing prose. That is neither "all docs current + correct" nor "cheapest." This design adds the missing **author** (cheap pool), the **verifier** (native), the **deterministic generator** (Tier-0), and the **end receipt** (whole-plan coverage) — each proving a different property at its own cost floor.

## Decomposition — single buildable spec (not split)

The four tiers are **one coherent subsystem**, not independent subprojects: they all key off the same registry SSOT (`_doc_registry.PROJECT_DOCS`), share the coverage gate, and are consumed by the same command wiring — delivering any one alone leaves the loop open (e.g. Tier-0 generators with no reconcile loop still lets prose rot; the loop with no coverage gate can't prove "done"). So it is one spec, executed as a phased plan (Tier-0 generators → `doc-reconcile` helper + loop → cumulative coverage gate → command wiring), each phase independently testable. No sub-spec is warranted.

## Chosen approach — a 4-tier ladder, two runtimes, registry-driven, converging (RECOMMENDED)

Cost tracks the diff, not the doc count; the correctness proof matches the doc's nature. Four tiers, all keyed off `_doc_registry.PROJECT_DOCS`:

- **Tier 0 — deterministic → generate, no model (free, exact).** For the computable parts: `PORTS.md` (from compose), the `docs/README.md` doc-index list, `INDEX.md`'s file enumeration, `db/schema.sql` freshness. Extends the existing `AUTO-GENERATED:*` block pattern (`sync_projects.py`, `docs_updater.py`). *The prose slots a generator can't compute (e.g. a new file's one-line INDEX description) are filled by Tier 1 — "deterministic structure, LLM fills slots."*
- **Tier 1 — prose → the doc-reconcile convergence loop (cheap, per fired trigger).** For each registry doc whose trigger fired in the diff:
  1. **Author (pool, cheap, parallel, records flywheel):** one `pick_models("docs")` agent per fired-trigger doc produces a **structured edit** (find/replace or section-scoped patch — never a blind rewrite) grounded in `{diff hunks} + {current doc} + {registry purpose}`. Disjoint `owned_paths` → all docs in parallel.
  2. **Verify (native Claude, cheap, no flywheel):** a native Haiku (Sonnet for a nuanced doc) checks "does the patched doc now match the code?" — cross-checks that referenced symbols/endpoints actually exist (the "model invents an endpoint; validation catches it" failure mode). Native produces no `AgentResult`, records nothing.
  3. **Converge:** verify finds drift → re-author. **Loop until a demonstrably-thorough pass makes zero doc edits** (md5-verified no-op — the exact termination contract `/fabrik-docs-review` already uses). One-shot is never trusted.
- **Tier 2 — whole-doc-set correctness → `/fabrik-docs-review` at the plan boundary.** The existing claim-by-claim convergence; its zero-edit no-op round **is** the correctness proof, produced once, cheaply (pool authors the fixes, Opus adjudicates).
- **Backstop — every commit (free, deterministic):** `check_doc_sync` (touch, 🔴 ERROR for CHANGELOG/CONFIGURATION/schema) + `check_doc_stubs` (no-stub).
- **End receipt — the whole-plan coverage gate (free, deterministic, ~sub-second):** at `/fabrik-execute-plan`'s Finish, run `check_doc_sync` + `check_doc_stubs` **scoped to the cumulative diff (baseline→HEAD)**, asserting every trigger that fired anywhere in the plan has its doc touched + no registry stub remains + no hub-owned doc locally edited. This is the cheap "definitely done" — it proves *nothing was skipped*; correctness was already proven by Tiers 1–2.

**Two runtimes, model-selection delegated:** the **pool** (fabrik-lib `subagents`) is the default author/reconciler — gradeable, cheap, feeds the flywheel via `pick_models("docs")`; **native Claude** (Haiku/Sonnet) is the verify + converge decision — reliable, no flywheel row. Commands declare the **task type** (`"docs"`) and name the native tier by **risk**, never by model name — so when the fabrik-lib model-selection AI retunes which cheap model wins for docs (the `*_SUBAGENT_SELECTION.md` mapping), the commands don't change.

**Command wiring (approved):**
- **`/fabrik-execute-plan`** — per phase: run the Tier-1 doc-reconcile convergence loop on the phase's fired-trigger docs (pool author → native verify → no-op) **before** the phase commit. Replaces "coder hand-writes the doc steps." Finish adds the whole-plan coverage gate.
- **`/fabrik-docs-review`** — Tier 2; make the author-fixes pool too, keep the Opus adjudication.
- **`/fabrik-plan-after-chat`** — annotates each trigger→doc step as "pool-reconciled + native-verified to no-op," not hand-authored.
- Tier-0 docs — mechanical, no model.

This is **build-by-extension**: reuse the vendored pool + the registry SSOT + the `/fabrik-review` convergence contract + the existing `AUTO-GENERATED`-block generators; add a thin `doc-reconcile` helper, the Tier-0 generators, and the cumulative-scope coverage mode. Minimal new code, maximal reuse.

## Rejected alternatives

- **B — All-native (Claude subagents author every doc).** Rejected: no flywheel (native records nothing), and it burns subscription Claude time on bulk prose the pool does for cents — the cited best-practice ("cheap-tier models are fine for drafting", Cyberax 2026) says the opposite. Native is the *verifier*, not the bulk author.
- **C — All-pool, one-shot, no verify / no converge.** Rejected: cheap models "invent an endpoint that almost matches a real one" (Cyberax) — without the native verify + the converge loop you ship confidently-wrong docs. The whole point of the two-runtime loop is catching that at cents.
- **D — Full LLM regeneration of the doc set at the boundary only (no per-diff, no deterministic tier).** Rejected: expensive (regenerates unchanged docs), and it fights the grounded best-practice ("a page changes only when its source subgraph changes"; "the foundation must be deterministic; LLMs fill gaps"). Per-diff + deterministic-first is both cheaper and more correct.

## External dependencies

**None** — this is fabrik-hub-internal tooling (enforcement scripts + command prompts + the vendored subagent pool over OpenRouter, which fabrik already uses). No new 3rd-party API/SDK/pricing/limits. The **1c best-practice/approach** grounding (live, cited this session, 2026-07-11):

- **graphwiki (PyPI, 2026)** — https://pypi.org/project/graphwiki/ (fetched 2026-07-11): "**Deterministic traversal decides what to document; the LLM only writes prose.** … a page changes only when its source subgraph changes" + `plan → deterministic context → writer (LLM) → gates → atomic emit` + `--since <git-ref>` incremental. Validates the deterministic-what + LLM-prose + gate + per-diff design.
- **Cyberax AI playbook (2026-05-11)** — https://cyberax.com/ai-playbook/auto-generate-docs-from-prs (fetched 2026-07-11): "**cheap-tier models are fine** for summarisation/drafting"; trigger-mapping (path + semantic) → candidate docs; "**structured edit-list beats free-form rewrites** because it preserves structure"; "run validation before the draft reaches a human … new code examples reference functions that actually exist … **the model occasionally invents an endpoint; validation catches it**." Validates cheap-author + structured-edit + verify.
- **msiric/autodocs (GitHub, 2026-03)** — https://github.com/msiric/autodocs (fetched 2026-07-11): "LLM-powered drift + suggestion, **everything else deterministic** … FIND/REPLACE with self-verification + deterministic REPLACE verification (code refs checked against source)." Validates deterministic-verify.
- **DeepDocs (2026-01)** — https://deepdocs.dev/automatic-document-generation/ (fetched 2026-07-11): "**intelligent updates, not blind regeneration** — carefully edits only the parts out of sync, preserving style." Validates edit-not-regenerate.
- **patrickchugh, "document like a boss"** — https://patrickchugh.github.io/blogposts/autodocs.html (fetched 2026-07-11): "the **foundation must be deterministic**; LLMs fill gaps … Jinja2 provides deterministic structure, the LLM fills slots … keep doc-gen on PRs to main, not every commit." Validates deterministic-first + cost-conscious boundary cadence.

These five (all 2026) independently converge on **exactly** this ladder: deterministic for structure/coverage, cheap LLM for the prose gaps as structured edits, a verify pass against real symbols, incremental per-diff, a coverage gate. (Inherits plan-4's SSOT citations — SRE config-design, "make derived state impossible to diverge" — for the registry-derives-everything invariant.)

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Parallel cheap-agent doc authoring (the pool) | **VENDOR as-is** | `fabrik-lib/subagents` is already vendored at `libs/subagents` — `run_agents([AgentSpec])→[AgentResult]`, `pick_models("docs")`, `record_agent_run`, disjoint-`owned_paths` parallelism, flywheel ledger. Composes `ai-consult`'s transport. Nothing to build. |
| `doc-reconcile(diff, doc)` helper (glue: registry trigger → dispatch → structured-edit prompt → apply patch) | **BUILD in fabrik** | Fabrik-governance-specific (registry doc set, fabrik trigger semantics, its `docs/` layout). Thin glue over `run_agents` + `_doc_registry`. Not generic → project-local, **no 🆕 candidate** (same call as plan-4's `check_doc_stubs`). |
| Tier-0 deterministic generators (`PORTS`/`docs/README` index / `INDEX` file-list) | **BUILD in fabrik (extend)** | Extend the existing `AUTO-GENERATED:*`-block pattern (`sync_projects.py`, `docs_updater.py`). Fabrik doc layout–specific. |
| Whole-plan coverage gate (cumulative-diff scope) | **BUILD in fabrik (extend)** | A `--cumulative`/`--range` mode on the existing `check_doc_sync`/`check_doc_stubs` (currently `_staged()` only). |
| The converge loop (author→verify→no-op) | **REUSE (pattern)** | The `/fabrik-review` + `/fabrik-docs-review` termination contract, applied to docs at the command level (execute-plan per phase, docs-review at boundary). No new module. |

The `doc-*` fabrik-lib modules (`doc-convert`/`doc-crawl`/`doc-translate`) are content-processing (docx/OCR/translate), **not** a scaffold-doc reconciler — confirmed inapplicable (same as plan-4).

## Shape / infra implications

- Scaffold type context: **the fabrik hub itself** (`/opt/fabrik`). No new `shape:` flags — this changes fabrik's enforcement + commands + a helper, not a deployed service.
- **Fleet-synced surfaces touched:** `scripts/enforcement/check_doc_sync.py` + `check_doc_stubs.py` (+ any new `scripts/doc_reconcile.py`/Tier-0 generators in `scripts/`), and `.windsurf/rules/` if the doc rule pack references the loop — all Fabrik-synced → re-distributed to ~47 projects. The command prompts (`~/.claude/commands/fabrik-*.md`) are operator-level, not fleet-synced.
- The pool dispatch runs **hub/dev-side** at plan-execution time (the coder's environment), reading the vendored `libs/subagents`; a project that hasn't vendored it degrades gracefully (guarded import → the mechanical gate still runs).

## Constraints

- **Registry is the SSOT** — the reconcile loop + Tier-0 + the coverage gate all derive which docs/triggers from `_doc_registry.PROJECT_DOCS`; never a second doc list.
- **Structured edits only** — the pool author emits find/replace or section-scoped patches, never a blind full-doc rewrite (preserve human style/structure; grounded best-practice).
- **Model-selection delegated** — commands pass `pick_models("docs")` + name native tier by risk; no hardcoded model IDs (the fabrik-lib AI owns the per-task/per-command assignment).
- **Cost floor per property** — deterministic where computable (free), cheap pool for prose (cents, only on changed docs), native only for verify + adjudication, LLM never re-verifies unchanged docs.
- **Never blocks on a doc-nuisance** — `check_doc_stubs` + the Tier-0 generators are advisory/fail-safe; only the existing `check_doc_sync` ERROR-tier (CHANGELOG/CONFIGURATION/schema) hard-blocks, unchanged.
- **Flywheel** — every pool `doc-reconcile` unit owes `record_agent_run` + `results_table` (`pick_models("docs")` learns which cheap model writes best); native verify records nothing by nature.

## Open / blocking unknowns

- **RESOLVED (user, this session):** the 4 command touchpoints + Tier-0 auto-gen + the whole-plan coverage gate are approved; model selection is delegated to `pick_models` + the fabrik-lib AI; the loop iterates-to-converge (not one-shot); the end check is a cheap mechanical receipt, not a re-run of the LLM.
- **RESOLVED (grounded, self-service):** VENDOR the pool (already at `libs/subagents`); BUILD the thin `doc-reconcile` helper + Tier-0 generators + the cumulative coverage mode by extension; the five 2026 sources confirm the deterministic-first + cheap-author + verify + per-diff approach.
- **Still-open (non-blocking, for the plan to ground):** (a) the exact **structured-edit contract** the pool author returns (find/replace block vs a section-scoped unified diff) — an implementation detail to ground against how `docs_updater`/existing patchers apply edits; (b) whether the per-phase reconcile is invoked as a **new `scripts/doc_reconcile.py`** or a **`/fabrik-docs-reconcile` skill** the commands call (default: a script helper, so both the plan pipeline and a direct coder can invoke it) — decide in the plan; (c) how much of `INDEX.md` is truly Tier-0 (file list) vs Tier-1 (per-file description prose) — the plan grounds the split against the current INDEX format.

## Success criteria (testable)

1. A `doc-reconcile(diff, doc)` dispatch produces a **structured** (non-blind-rewrite) patch, applies it, and records a flywheel row; a unit test asserts the patch touches only the target doc + a `record_agent_run` row lands.
2. The reconcile **loop converges** — given a doc already matching the diff, a pass makes zero edits (md5-verified no-op); given a stale doc, it patches then converges. Test both.
3. **Tier-0 generators** produce `PORTS.md` / the `docs/README.md` index deterministically from the repo state (no model), byte-stable on re-run.
4. The **whole-plan coverage gate** (cumulative baseline→HEAD) FAILS when a fired-trigger doc was never touched across the plan and PASSES when all were — a fixture test with a synthetic plan diff.
5. **Native verify** flags a doc that references a symbol/endpoint absent from the code (the "invented endpoint" case) and passes a doc that matches.
6. `/fabrik-execute-plan` per phase invokes the loop before the phase commit; `/fabrik-docs-review` author-fixes go through the pool — verified by the command-prompt text carrying the step (prompt-level, not a runtime test).
