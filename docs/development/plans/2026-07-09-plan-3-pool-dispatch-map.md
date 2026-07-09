# Land the verified pool-dispatch map + parallelism rule into governance; propose subagents enhancements

Status: IN-PROGRESS
Date: 2026-07-09
Converged: 2026-07-09 (/fabrik-plan-review — 2 passes to an edit-free md5-verified no-op; all path:line citations re-verified stable, structural pillars completed — added /fabrik-docs-review + check_convergence to the final phase)
Spec (source of truth): `docs/superpowers/specs/2026-07-09-pool-dispatch-map-and-enhancements-design.md` (CONVERGED 2026-07-09)

Codify the session-verified pool dispatch rules into the fleet governance so the pool is dispatched **correctly**
(no silent serialization) and **generously** (parallel by default). Fix the one command that actively instructs a
serializing dispatch, hand the `subagents`-module enhancement list to the fabrik-lib AI (cross-repo propose), and
— optionally — re-vendor to activate the `[+github]` lanes (plan-2 is EXECUTED upstream).

## What we already agreed (from the CONVERGED spec + this session — RICH, no re-brainstorm)

- **Goal:** one source of truth for how each `/fabrik-*` command dispatches the pool — the **two-shape parallelism
  rule** + the per-command map — landed in `62 § Dispatch policy`, plus the fabrik-lib enhancement proposal.
- **The core fact the fleet is missing (verified this session):** a pool fan-out runs in parallel ONLY when
  either (a) **read-only** workers (`tools_enabled=False` + `allow_ungrounded=True`, content inlined — each is its
  own group), or (b) **tools-enabled** workers with **disjoint `owned_paths`**. `tools_enabled=True` + empty/
  overlapping `owned_paths` → one overlap group → **SERIAL** (`agent.py:430-435`, `workspace.py:321`). This rule
  exists in neither `62` nor any command today.
- **The one explicit defect:** `fabrik-data-contract.md:108` instructs "one grounder per surface,
  `tools_enabled=True`, run them **in parallel**" with no `owned_paths` → serializes. The other 7 grounding
  commands are *latent* (say "in parallel" without pinning the safe mode; footer offers `tools_enabled=True`
  with no owned_paths caveat). `/fabrik-review` + `/fabrik-repo-review` are the **correct reference pattern**
  (`tools_enabled=False` + `allow_ungrounded=True`).
- **fabrik-lib enhancements (propose, do NOT build here — cross-repo):** `fanout()` footgun-free helper +
  serialization guard/warning + quality-score back-fill. `record_run` loud-warn already landed upstream.
- **File-scope split (user, verbatim):** `62` + `CLAUDE.md` are **fabrik-synced** (edit in `/opt/fabrik`;
  the pre-commit hook auto-syncs fleet-wide on commit). The 12 `~/.claude/commands/fabrik-*.md` are
  **user-level** (live, NOT in the repo, no repo commit; pool workers can't read them → native edits).
- **github (arg 4):** plan-2 is `EXECUTED`/archived upstream (`final_commit b3dc97d`); the hub copy still lacks
  `github` → re-vendor activates `[+github]`. A **separate, optional** phase, gated on byte-identical + tests green.

## Global Constraints (every phase inherits — verbatim)

- **Fabrik-synced files are edited in `/opt/fabrik` ONLY** (`62-using-subagents.md`, `CLAUDE.md`) — a commit
  touching them **auto-triggers `sync_enforcement_to_projects.py --force`** fleet-wide (`.pre-commit-config.yaml:46`).
  That blast radius is intended (the rule must be fleet-wide) but means these are the last edits, verified first.
- **User-level command files are NOT committed to the repo** (`~/.claude/commands/*.md`) — they are live on
  edit; there is no repo commit or gate for them. Their "gate" is a grep assertion on the file.
- **Cross-repo HARD STOP:** the `subagents` module is canonical in `/opt/fabrik-lib` — this plan **proposes**
  enhancements (a hand-off note in `/opt/fabrik`), it **never writes** `/opt/fabrik-lib`.
- **Explicit-path commits only** (never `git add -A`); provenance trailers on every AI commit; append atop
  `CHANGELOG.md [Unreleased]`, never reset it.
- **All gates run from WSL** (`grep`, `python -c`, `pytest`, `final_gate.py`) — no `fabrik …` shell-out.
- Every governance claim traces to the spec's grounded `path:line` (spec § Grounding).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | THE dispatch-policy doc being extended — § Dispatch policy is the target | edited at its § Dispatch policy + § Report |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | doc-sync matrix + plan-file conventions the edits obey | `select_rules.py` ACTIVE |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract — a check per user-observable behavior (here: grep assertions on prose) | `select_rules.py` ACTIVE |
| `libs/subagents` (vendored module) | the runtime whose REAL behavior the map encodes — VENDOR (as-is); enhancements are fabrik-lib's to build | `agent.py:430-435`, `workspace.py:321`, `select.py:333`, `pg_ledger.py:97` (spec grounding table) |
| `/opt/fabrik-lib/subagents` (canonical) | the enhancement target — cross-repo PROPOSE only; github read-only already landed (`mcp_tools.py:98`) | plan-2 archived, `final_commit b3dc97d` |
| `scripts/fabrik_synced_manifest.py` + `.pre-commit-config.yaml:46` | why a `62`/`CLAUDE.md` commit fleet-syncs | manifest GOVERNANCE_FILES |
| `CLAUDE.md` | § Subagent fan-out gets a one-line pointer; shared-tree commit discipline | `CLAUDE.md:112` |

No new external API. No new fabrik-lib module (the enhancements are an ENHANCE of `subagents`, proposed upstream).
fabrik-lib consult: `subagents` is the module in question — already vendored; this plan changes governance + proposes
enhancements, it does not build them here.

## Behavior Contract (this plan's own checks — one per user-observable behavior; grep assertions, no code)

**Why:** the risk is a governance edit that says the rule but doesn't actually state the parallel-safe shapes, or a
command "fix" that still serializes. Each behavior is a runnable grep assertion.

- **Given** `62 § Dispatch policy`, **When** grepped, **Then** it contains the two-shape parallelism rule
  (`tools_enabled=False` → parallel; `tools_enabled=True` needs disjoint `owned_paths` else serial) AND the
  `pick_models` n-default AND `max_concurrency` default 4 AND the per-command dispatch map.
- **Given** `fabrik-data-contract.md`, **When** grepped around the grounder-dispatch block, **Then** it no longer
  pairs `tools_enabled=True` with "in parallel" **without** a disjoint-`owned_paths` (or RO-inline) instruction.
- **Given** `CLAUDE.md § Subagent fan-out`, **When** grepped, **Then** it points at the `62` parallelism rule.
- **Mocked:** none — real files, real greps.

---

## Phase A — Land the parallelism rule + per-command map into `62 § Dispatch policy` (+ `CLAUDE.md` pointer) — ✅ EXECUTED 2026-07-10

> Phase-A review: 2 pool RO finders (parallel, recorded, $0.0098) — correctness NO DEFECTS; consistency 10 raised, 9 refuted (Issue-3 table + Issue-8 model-map false positives; Issue-2 validator is Phase-C enhancement #2; rest formalization-not-defect), 1 fixed (Issue-7: scoped the worker-tools list to tools-enabled workers).

**Files:** `.windsurf/rules/core/62-using-subagents.md`, `CLAUDE.md` (both fabrik-synced — commit fleet-syncs).
**Responsibility:** make `62` the single source of truth for correct pool dispatch; `CLAUDE.md` points at it.

**Interfaces — Produces:** a `62 § Dispatch policy` subsection "Parallelism (the two shapes)" + a per-command
dispatch-map table; a `CLAUDE.md:112` clause pointing at it. Consumed by Phase B (the commands defer to this rule).

**Steps (highest-risk first — the rule text is the risk):**
1. **Write the parallel-safe rule** into `62 § Dispatch policy`, verbatim from the spec § "The verified parallelism
   rule": the two shapes (RO-inline all-parallel; TE needs disjoint `owned_paths`), the `pick_models(…, n=K)`
   default-1 note, `max_concurrency` default 4 (raise to widen), and every pool unit records
   (`record_agent_run` + `results_table`, never `record_run`).
2. **Add the per-command dispatch map** (spec § "The verified dispatch map") as a table in `62`, with the `[+github]`
   rows marked "pending hub re-vendor (plan-2 EXECUTED)".
3. **`CLAUDE.md:112`** — add one clause to § Subagent fan-out: "parallel pool fan-out follows `62 § Dispatch
   policy`'s two-shape rule (read-only → parallel; tools-enabled → disjoint `owned_paths` or it serializes)."
4. **Gate (grep assertions):**
   - `grep -c "disjoint" .windsurf/rules/core/62-using-subagents.md` → `≥1`; and the block names both
     `tools_enabled=False` (parallel) and the serial failure mode. `grep -c "max_concurrency" 62…` → `≥1`.
   - `grep -c "Dispatch policy" CLAUDE.md` → `≥1` (the pointer).
5. **Doc-sync:** `python scripts/enforcement/check_doc_sync.py` → resolve any WARN whose trigger is in this diff.
   `CHANGELOG.md` `[Unreleased]` entry (Changed — the dispatch rule).
6. **Phase gate:** `python scripts/final_gate.py --check --json` → `"status":"success"` (62 + CLAUDE.md are synced,
   gate-checked). Fix to green.
7. **`/fabrik-review`** on the Phase-A diff — pool finders (RO, `review`, `n=3`) over the prose + native decide/merge;
   loop to a no-op (zero CONFIRMED/PLAUSIBLE, all FIXED/REFUTED).
8. **Update the plan file:** mark Phase A `✅ EXECUTED <date> (<commit>)` + flip `Status: DRAFT → IN-PROGRESS`;
   **stage the plan file in this commit.**
9. **Commit** (explicit paths: `62-using-subagents.md`, `CLAUDE.md`, `CHANGELOG.md`, this plan) with provenance
   trailers (`Agent-Role: primary`, `Agent-Phase: A`).

## Phase B — Fix the commands: `data-contract:108` explicit trap + the shared footer caveat (user-level, no repo commit) — ✅ EXECUTED 2026-07-10

> Fixed `data-contract.md:108` (the one explicit trap → parallel-safe: RO-inline OR TE-disjoint `owned_paths` per surface) + added the `62 § Parallelism` caveat to 8 command footers (spec, spec-review, plan-review, plan-after-chat, docs-review, rules-review, data-contract, ui-design-review). `/fabrik-review` + `/fabrik-repo-review` left unchanged (already the correct `tools_enabled=False`+`allow_ungrounded` reference). No repo commit (user-level files, live); this plan-file update rides into the Phase-C commit. Review: native (pool can't read `~/.claude/commands`) — coherent, no-op.

**Files:** `~/.claude/commands/fabrik-data-contract.md` (explicit fix) + the shared § Subagents footer clause across
the grounding commands (`fabrik-spec`, `-spec-review`, `-plan-review`, `-plan-after-chat`, `-docs-review`,
`-rules-review`, `-ui-design-review`). **No repo commit — these are live user-level files.**

**Interfaces — Consumes:** the `62` parallelism rule from Phase A (the commands point at it).

**Steps:**
1. **`fabrik-data-contract.md:108`** — rewrite the grounder-dispatch instruction from "`tools_enabled=True` … run
   them in parallel" to the parallel-safe form: **either** RO-inline each surface's content
   (`tools_enabled=False`, `allow_ungrounded=True`) **or** `tools_enabled=True` with **disjoint `owned_paths` per
   surface** (schema / API models / frontend forms). One sentence; cite `62 § Dispatch policy`.
2. **Shared footer caveat** — in each grounding command's § Subagents "single-shot … or `tools_enabled=True` (real
   file reads)" clause, append: "— a `tools_enabled=True` **parallel** fan-out needs **disjoint `owned_paths`**, else
   it serializes; for a read-only parallel fan-out prefer `tools_enabled=False`." Apply the same one-line addition
   to each command that carries the clause (audit-confirmed set above; skip any that already state it).
3. **Verify `/fabrik-review` + `/fabrik-repo-review` are unchanged** (already correct — `tools_enabled=False` +
   `allow_ungrounded`); confirm by grep, do NOT edit them.
4. **Gate (grep assertions, user-level files):**
   - `grep -A2 "one INDEPENDENT grounder subagent per surface" ~/.claude/commands/fabrik-data-contract.md` shows the
     parallel-safe wording (no bare `tools_enabled=True` + "in parallel" without `owned_paths`).
   - each edited command's footer contains "disjoint `owned_paths`".
5. **`/fabrik-review`** on the Phase-B changed surface (the command files are readable natively; pool finders can't
   read user-level files → this review is **native**, per `62` — a legitimate all-native slice, no flywheel row owed).
   Loop to a no-op.
6. **No commit** (user-level files). **Update the plan file** to mark Phase B done + note "no repo commit
   (user-level)"; stage the plan-file update into the **next** repo commit (Phase C or the finish).

## Phase C — Propose the `subagents` enhancements to the fabrik-lib AI (cross-repo — hand-off, no write to fabrik-lib) — ✅ EXECUTED 2026-07-10

> Wrote `docs/reference/subagents-enhancement-proposal.md` (fanout helper + serialization guard + quality back-fill, each with the verified trap + `path:line`) + INDEX.md entry. Docs convergence: 1 pool RO reconciler (recorded, $0.0025) flagged `workspace.py:321` "empty→serial" as inverted — **REFUTED** (it misread `unrestricted=True`; that triggers `union()`→one group→serial per workspace.py:303,316-323, corroborated by Phase A's finder). Doc + 62 confirmed CORRECT; no fix. check_doc_sync + check_convergence + final_gate --check all green.

**Files:** `docs/reference/subagents-enhancement-proposal.md` (a NEW `/opt/fabrik` doc — the hand-off note the user
relays). **Never writes `/opt/fabrik-lib`.**

**Interfaces — Produces:** a grounded proposal doc listing the three enhancements (spec § "subagents-module
enhancements needed") with the trap each fixes + the `path:line` evidence.

**Steps:**
1. Write `docs/reference/subagents-enhancement-proposal.md`: (1) `fanout()` footgun-free helper (subsumes 4 traps),
   (2) serialization guard/warning in `arun_agents`, (3) quality-score back-fill (`set_quality` / serialize-reconstruct
   — INSERT-only role → NULL quality today). Each with the verified `path:line` + the failure it prevents. Note #4
   (`record_run` loud-warn) already landed.
2. `INDEX.md` — add the new doc (Doc Sync Matrix: file added → `INDEX.md`).
3. **Gate:** the doc exists + `check_doc_sync.py` green; `python scripts/final_gate.py --check --json` success.
4. **`/fabrik-review`** on the Phase-C diff (pool RO finders + native merge) → no-op.
5. **Docs convergence (this is the last committed phase — the doc-truth gate the per-phase gates don't give).**
   Run **`/fabrik-docs-review`** scoped to the doc surface this plan shipped (`62`'s dispatch map + parallelism
   rule, `CLAUDE.md` pointer, `docs/reference/subagents-enhancement-proposal.md`) — reconcile each claim against
   the real module `path:line` (the map must still match `agent.py`/`workspace.py`/`select.py`/`pg_ledger.py`) →
   iterate to a truthful zero-discrepancy no-op. Then `python scripts/enforcement/check_convergence.py` →
   validates this plan's `## Evidence` / `## Self-audit` convergence.
6. **Update the plan file** (Phase C done) + **commit** (explicit paths: the proposal doc, `INDEX.md`, this plan)
   with provenance (`Agent-Phase: C`). Surface the proposal to the user to relay to the fabrik-lib AI (handoff report).

## Phase D — (OPTIONAL) Re-vendor `libs/subagents` to activate `[+github]` — gated on byte-identical + tests green

**Files:** `libs/subagents/**` (re-vendor from canonical), `CHANGELOG.md`. **Optional** — run only if the user wants
`[+github]` live now. Same pattern as the plan-6 stall-fix pre-flight.

**Steps:**
1. **Pre-flight:** `diff -rq /opt/fabrik/libs/subagents /opt/fabrik-lib/subagents/subagents --exclude=__pycache__
   --exclude=requirements.txt` — note the delta (should include `mcp_tools.py` github + any drift).
2. **Re-vendor** the canonical inner package flat → `libs/subagents/` (keep `requirements.txt`, strip `__pycache__`),
   per `VENDORING.md`.
3. **Gate — byte-identical:** `diff -rq … --exclude=__pycache__ --exclude=requirements.txt` → **empty**;
   `grep -c '"github"' libs/subagents/mcp_tools.py` → `≥1` (github now in the hub allowlist).
4. **Gate — tests green:** `.venv/bin/python -m pytest tests/ -k "subagent or flywheel or synced" -q` → pass;
   `python -c "from libs.subagents import run_agents, record_agent_run"` → exit 0.
5. **Flip the `62` map's `[+github]` rows** from "pending re-vendor" to "active" (a one-line edit — the only governance
   change here). `CHANGELOG.md` entry.
6. **Phase gate:** `python scripts/final_gate.py --check --json` success (`extend-exclude=["libs/subagents"]` keeps
   ruff off the vendored files). **`/fabrik-review`** on the diff → no-op.
7. **Update the plan file** (Phase D done) + **commit** (explicit paths: `libs/subagents`, `62…`, `CHANGELOG.md`,
   this plan) with provenance (`Agent-Phase: D`).

---

## File Scope (owned paths)

Repo (fabrik-synced, committed — commit fleet-syncs):
- `.windsurf/rules/core/62-using-subagents.md`
- `CLAUDE.md` — **shared serialization point** (many plans touch it; do not run a phase editing it concurrently
  with a sibling plan that also edits `CLAUDE.md` — e.g. `2026-07-09-plan-2-modelscope`).

Repo (committed, this plan only):
- `docs/reference/subagents-enhancement-proposal.md` (new), `INDEX.md`, `CHANGELOG.md`
- `docs/development/plans/2026-07-09-plan-3-pool-dispatch-map.md` (this plan — status edits)
- `libs/subagents/**` (Phase D only, optional)

User-level (live, NOT committed): `~/.claude/commands/fabrik-data-contract.md` + the shared footer of
`fabrik-{spec,spec-review,plan-review,plan-after-chat,docs-review,rules-review,ui-design-review}.md`.

Cross-repo (NEVER written): `/opt/fabrik-lib/**` (enhancements proposed via the Phase-C doc, not written).

## Evidence

- **Phase A** — the parallelism rule is grounded at `agent.py:430-435` (read-only own-group / writer via
  `disjoint`) + `workspace.py:321` (`unrestricted = not owned[i] or not owned[j]`), re-read this session:
  ```
  groups += [{i} for i, s in enumerate(specs) if not s.tools_enabled]   # agent.py:435 — RO each own group
  unrestricted = not owned[i] or not owned[j]                            # workspace.py:321 — empty overlaps all
  ```
- **Phase B** — the explicit trap, re-read this session:
  ```
  fabrik-data-contract.md:108: … `tools_enabled=True` for repo Read/Grep … run them **in parallel** …   (no owned_paths → serial)
  fabrik-repo-review.md: `tools_enabled=False`, `allow_ungrounded=True`   (the CORRECT parallel pattern)
  ```
- **Phase C** — the enhancement targets grounded: `pg_ledger.py:97` (`record_run` no-op), `select.py:333`
  (`pick_models` default `n=1`), the serialization trap above.
- **Phase D** — `grep -c '"github"' /opt/fabrik/libs/subagents/mcp_tools.py` → `0` (hub lacks it);
  canonical `mcp_tools.py:98` has `_force_github_readonly`; plan-2 archived (`final_commit b3dc97d`).

## Self-audit

- **Grounding passes:** inherited the CONVERGED spec's grounding (all module facts re-verified during
  `/fabrik-spec-review` this session — the spec's Pass 3 was an edit-free md5 no-op); Phase-1 verification for this
  plan added the per-command trap audit (only `data-contract:108` is the explicit trap; the other 7 are latent →
  footer caveat).
- **Coverage (each "What we agreed" → a phase):** parallelism rule + map → **A**; command trap fix → **B**;
  fabrik-lib enhancement proposal → **C**; github activation → **D (optional)**. No agreed item unmapped.
- **Cross-phase signature consistency:** Phase A produces the `62` rule that Phase B/D consume (they point at it);
  no function/type names to reconcile (governance prose).
- **Fixed-point claim:** NOT yet — `/fabrik-plan-review` owes the convergence round.

## Residual unknowns

- **[RESOLVED]** Helper home → fabrik-lib enhance (operator's call); this plan proposes, does not build.
- **[RESOLVED]** github status → plan-2 EXECUTED/archived; Phase D (optional) activates it.
- **[SELF-SERVICE]** Whether to run Phase D this pass → the executor runs it only if the user opts in at hand-off;
  default is to stop after C and offer D (the map already documents `[+github]` as pending). No mid-run stall — the
  default (skip D, offer it) is baked in here.
- **[OPEN — none blocking]** No cross-AI/credential/infra unknown blocks A–C. Phase D depends only on canonical
  being byte-identical (a gate, self-service), not on the fabrik-lib AI.
