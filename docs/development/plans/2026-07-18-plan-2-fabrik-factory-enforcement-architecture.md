# Fabrik Factory — Enforcement Architecture Rollout

**Status:** IN-PROGRESS
**Spec:** `docs/superpowers/specs/2026-07-18-fabrik-factory-architecture-design.md` (CONVERGED) — the source of truth.
**Nature:** docs + command-file change. **No deployed service, no scaffold, no `shape:` flags, no `fabrik apply`.**

Implements the reliability-ladder / compiled-from-sources model: mechanical gates (Tier 1) + self-sufficient
compiled commands (Tier 2) + armed adversarial review injected with the matched rule rubric (Tier 3), honoring the
spec's § Known limitations (L1 no-op≠compliance · L2 residual dependency · L3 pack-selection blind spot · L4
independently-shippable workstreams).

---

## What we already agreed (Phase 0 distillation — RICH, spec-fed)

- **Goal.** Rules enforced *as reliably as the mechanism allows* — mechanical certainty where a gate can check;
  maximally-enforced (injected-rubric, separate-reviewer, converge-to-no-op) but **probabilistic** where only a
  reviewer can judge (spec Goal §2 + § Known limitations L1).
- **Governing law.** *"Nothing is ambient. Every load-bearing constraint arrives via a gate, compiled context, or an
  armed review — never a doc an agent is told to read."* (spec § governing law).
- **Approved decisions (owner):** ONE tool-capable `-fabrik` command set (twins archived); **AGENTS.md option (b)** —
  collapse to one agents doc, strip rule-restatements, `@import` into a slimmed `CLAUDE.md`; governance docs are
  design-time sources, not runtime references.
- **Internal capabilities (VENDOR, exist):** `scripts/select_rules.py` (pack selection), `scripts/final_gate.py`
  (mechanical gate), `/opt/fabrik-lib/subagents/` (`fanout`/`set_quality`). The rule-injection wire is **ENHANCE**.
- **Rejected:** ambient-AGENTS.md, inline-everything, `Reads:`-header as the mechanism, generator self-attestation,
  single-pass review, unarmed reviewer (spec § Rejected alternatives).
- **Honest bounds (do not overclaim):** L1–L4 — the plan must not present the review loop as a compliance *guarantee*.

**Branch: RICH** — the CONVERGED spec pins goal + approach; no brainstorming. Straight to grounding + phasing.

**⚠️ Execution order = C → A → D → B** (phase *labels* are by workstream, not sequence). L4 says the four are
disjoint blast radii, so order by risk/value: **C first** (the core enforcement — `review_rubric.py` + arming the
reviews; highest value, isolated, no dependency on B), then **A** (cheap — the law) and **D** (cheap — the catalog
step), and **B LAST** (it rewrites `CLAUDE.md`, the shared auto-loaded bootstrap — the riskiest surgery, so it lands
only after everything else is proven). Nothing in C/A/D depends on B.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED) | goal, governing law, AGENTS.md option (b), L1–L4 bounds | `docs/superpowers/specs/2026-07-18-fabrik-factory-architecture-design.md` |
| `scripts/select_rules.py` | pack selection primitive; emits ACTIVE/AVAILABLE pack **paths + descriptions** (has `--json`) | `scripts/select_rules.py:104-133` — prints packs, not bodies → the injector must read pack bodies |
| `scripts/final_gate.py` | mechanical gate (Tier-1 showstoppers / Tier-3 repo health; static tools apply to any new `.py`) | `scripts/final_gate.py:11-28` |
| `/opt/fabrik-lib/subagents/` | `fanout` + `set_quality` (finder breadth + flywheel) — **vendor, don't build** | `fanout` at `subagents/agent.py:710`; `set_quality` at `subagents/pg_ledger.py:269`; both re-exported by `subagents/__init__.py` → `from libs.subagents import fanout, set_quality` |
| `/fabrik-review.md:72` | current review **reads** `.windsurf/rules` as binding context — the WS-C migration target | `~/.claude/commands/fabrik-review.md:72` |
| north-star | design-time intent doc — where the governing law is baked | `docs/orchestrator/00-autonomous-factory-north-star.md` |
| `CLAUDE.md` (161 lines, no `@import`) | the ONE auto-loaded file → the bootstrap; `@import` loads target **in full** (spec G2) | `CLAUDE.md` |
| `scripts/service_catalog.json` | secret-free owned-service inventory (90 svcs, 0 triage) for the 00-trigger procurement step | `scripts/service_catalog.json` |
| `EVALUATION_CHECKLIST_*` (×2) | the command-authoring QA rubrics C2/C8/D3 read + eval against | `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` · `docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` (both exist, verified) |
| `scripts/fabrik_synced_manifest.py` + `scripts/sync_enforcement_to_projects.py` | the project-side propagation path C2b drives (manifest entry + sync run) | both exist, verified; `select_rules.py`/`final_gate.py` already listed |

**fabrik-lib consult:** the only capability with a code artifact is the WS-C **rubric extractor** — checked
`fabrik-lib/README.md`: no module extracts "select_rules → pack mandates → review rubric"; it's factory-command-local
glue over the existing `select_rules.py`, not a generic reusable module → **project-local BUILD, no `🆕` candidate.**

## Global Constraints (inherited by every phase)

- **This is a docs + command-file + one-small-script change.** 12-Factor / `shape:` / deploy / GUI Build-Verification
  are **N/A** (no service, no compose, no screens) — do not emit those steps.
- **Command-file discipline:** every edited `-fabrik`/command file must still pass its `EVALUATION_CHECKLIST_*`
  (by path, never a hard-coded count) and the CC2 citation discipline (inline the decision, tag canonical).
- **Naming:** kebab-case; new script `scripts/review_rubric.py`.
- **No secret ever inlined** (service_catalog.json is secret-free; `all-envs.env` is never read at plan/review time).
- **Honesty (L1):** any text the plan adds about the review loop says "maximally-enforced / probabilistic," never
  "guaranteed compliant."
- **Reviews are the enforcement** (spec Tier 3): every phase ends with `/fabrik-review` to a no-op.

## Subagents & parallelism (enforced — baked into the phases)

- **Every phase's closing `/fabrik-review`** dispatches its finders **pool-default** (`fanout("review", …,
  mode="read_only")`, family-diverse, auto-recorded) **+ ≥1 native `fabrik-reviewer` on Opus** for the authoritative
  pass, with `set_quality` back-fill (`62-using-subagents.md` § Dispatch policy). Guard the import
  (`try: from libs.subagents import fanout, set_quality / except ImportError: fanout = None`).
- **Phase C parallelism:** the four review-command wirings (`/fabrik-review`, mega-`04`, ettw-`08`, ettw-`10`) are
  **independent** → apply + review them as a **parallel fan-out** (one unit per command file, disjoint `owned_paths`),
  merged before the phase gate. The `review_rubric.py` per-behavior tests are authored via **`/fabrik-generate-tests`**
  (cheap pool authors → you curate).
- **Sequential only on true data dependency:** the four phases are **L4-disjoint** → execution order is **C → A → D → B**
  (§ top: B last, riskiest bootstrap surgery); within a phase, fan out the independent units.

---

## Phase A — Bake the governing law into the north-star (WS-C)  — ✅ EXECUTED 2026-07-19 (review no-op R1:2/2 R2:1/1 R3:0/0)

**Responsibility:** make the reliability-ladder law the design-time source everything else is authored against.
**Files:** `docs/orchestrator/00-autonomous-factory-north-star.md` (edit).
**Interfaces — Produces:** a `## Enforcement Model (the governing law)` section that phases B–D reference by name.
**Consumes:** the CONVERGED spec.

1. Add a `## Enforcement Model` section to the north-star (near § Owner Working Model): the governing law verbatim +
   the three-tier ladder (gate / compiled / armed-review) + a one-line pointer to the spec's § Known limitations
   (L1–L4). Keep it lean (≤~30 lines) — it is intent, not the full spec.
2. Add one decision-log line under `## Decisions`: *"D-Enforce (2026-07-18): the reliability ladder is the factory's
   compliance model — see § Enforcement Model + spec 2026-07-18-fabrik-factory-architecture-design."*
3. **Fix the front-door self-contradiction (owner-directed fold-in, 2026-07-18).** North-star `:60` (§ two-workflow
   factory, step 1) claims `/fabrik-spec` is the universal front door; `:48` (§ Which workflow) already states the
   scale-routed model — they contradict. Rewrite step 1 of § two-workflow to the **three-tier front-door model**:
   **feature-scale** (one plan an operator session carries) → `/fabrik-spec` → data-contract → *(GUI)* ui-design →
   plan → execute · **epic** (needs a ticket store + dispatched agents) → `ettw-00` directly · **multi-epic vision**
   → `mega-00` (spec-grade intake — its Required sections carry everything `/fabrik-spec` produces; Scale Assessment
   down-routes). State the distinguishing test once: *does it need tickets and dispatched agents, or is it one plan
   an operator session can carry?* Routing is symmetric both ways (the `/fabrik-spec` up-route + ettw-00 mirror
   shipped 2026-07-18, outside this plan's scope). Align `:48` wording to the same three tiers.
4. **Gate:** `grep -c 'Enforcement Model' docs/orchestrator/00-autonomous-factory-north-star.md` → ≥1; the
   section states the law + L1 honesty bound (`grep -q 'probabilistic'`); and the three-tier front door is stated
   (`grep -q 'three-tier\|feature-scale' docs/orchestrator/00-autonomous-factory-north-star.md`). Expected: all present.
5. `python scripts/enforcement/check_doc_sync.py` (if it flags the north-star) → resolve; no other doc triggers (this
   is an intent doc, not a feature/API/env change → Doc Sync Matrix: none beyond CHANGELOG).
6. **`/fabrik-review`** on the north-star diff — looped to a no-op (zero CONFIRMED/PLAUSIBLE; each finding FIXED/REFUTED).
7. Commit (`docs/orchestrator/00-autonomous-factory-north-star.md`, provenance trailer).

---

## Phase B — Collapse the agents docs + slim CLAUDE.md + `@import` (WS-A)

**Responsibility:** one canonical agents doc (live platform facts only), compiled into the one auto-loaded file.
**Files:** `agents-fabrik.md` (becomes canonical, stripped), `AGENTS.md` (retire → stub pointer), `CLAUDE.md` (slim +
`@import`). **Interfaces — Consumes:** Phase A's Enforcement Model. **Produces:** a slim `CLAUDE.md` that `@import`s
the stripped agents doc.

1. **Reconcile the two agents docs → one.** Diff `AGENTS.md` vs `agents-fabrik.md` (42 differing lines, verified);
   keep `agents-fabrik.md` as canonical (the commands cite it). Fold any unique-to-`AGENTS.md` fact in.
2. **Strip rule-restatements** from `agents-fabrik.md`: every fact that restates a `.windsurf/rules` pack (auth=Pattern
   A, postgres-main, Stripe-ban, 12-Factor…) → a **tagged one-liner** (`[canonical: pack §X]`) or delete. Keep ONLY
   live platform facts rules don't carry (VPS hosts/IPs, ports, service topology, project list, fleet mesh). Target: a
   genuinely small doc (spec § AGENTS.md resolution — "small" is by content, not by the import mechanism).
2b. **While stripping, rewrite § Workflow to the three-tier front-door model + purge the archived-twin references
   (owner-directed fold-in, 2026-07-18).** The current § Workflow is stale a layer deeper than the rule-restatements:
   `AGENTS.md:47/:49/:93/:627-628` still describe the `-command` twins as live ("reference copies… keep in factual
   lockstep") and `:51` routes the EXISTING-mode user to `00-trigger-workflow-command` — the **retired tool-less
   twin**, which mega-00 itself forbids handing off to (its § routing: "never hand off to a `-command` twin") and
   which D2 archived. In the KEPT doc: (a) rewrite § Workflow to the same three-tier model Phase A puts in the
   north-star (feature → `/fabrik-spec` · epic → `ettw-00` · vision → `mega-00`, one distinguishing test, symmetric
   routing); (b) purge/correct **every** `-command` twin reference — EXISTING mode enters at
   `mega-epic-breakdown/00-trigger-fabrik` in EXISTING mode. **Gate:** `grep -cE 'workflow-command|command twins?'
   agents-fabrik.md` → 0 (and the AGENTS.md stub carries none). ⚠️ Deliberately NOT a bare `-command` grep — that
   would false-positive on legitimate text (e.g. `AGENTS.md:99` "Cascade slash-command workflows", which stays).
   Expected: 0.
3. **Retire `AGENTS.md`** → replace its body with a one-line stub: *"Canonical agents doc is `agents-fabrik.md`,
   `@import`-ed into `CLAUDE.md`. (AGENTS.md retained only for cross-tool discovery.)"* — OR `ln -s agents-fabrik.md
   AGENTS.md` if the sprawl gate allows a symlink (decide by whether `check_doc_sprawl.py` accepts it; default = stub).
4. **Slim `CLAUDE.md` to a bootstrap** + add `@agents-fabrik.md`: keep hard-stops + the gate contract + the Doc-Sync
   Matrix + pointers; move any long prose out to its canonical home; append the `@agents-fabrik.md` import line.
5. **Gate (mechanical):** `python scripts/select_rules.py >/dev/null` still runs (rules untouched);
   `python scripts/enforcement/check_doc_sprawl.py` exits 0 (no un-allowlisted file; the script has no argparse — no
   flag); `grep -q '@agents-fabrik' CLAUDE.md`. Expected: all pass.
6. **Gate (functional smoke — the U1 resolution step, DETERMINISTIC):** `claude` is present (`which claude` → OK,
   verified 2026-07-18). In a throwaway dir, plant a rare sentinel line (e.g. `SENTINEL-IMPORT-OK-7f3a`) into a copy of
   the stripped doc, write a scratch `CLAUDE.md` containing only `@<that-copy>`, then run
   `claude -p 'output only the exact SENTINEL token in your imported context' | grep -q SENTINEL-IMPORT-OK-7f3a` →
   exit 0. ⚠️ This is a **smoke test (spec U1), advisory — not a hard correctness gate**: if `claude -p` is flaky in the
   env, fall back to asserting the `@import` syntax against the cited memory-doc example and record it as a one-line
   owner check. Record the result either way.
7. Doc-sync: update `INDEX.md` (AGENTS.md retired/stubbed) + `CHANGELOG.md`.
8. **`/fabrik-review`** on the `CLAUDE.md` + `agents-fabrik.md` + `AGENTS.md` diff — no-op loop.
9. **Commit — ONE atomic commit, prepared ASIDE (mechanical guard, not just a quiet window).** `CLAUDE.md` is the
   bootstrap **every concurrent agent auto-loads**; a half-rewritten copy sitting in the working tree WHILE you edit
   is the hazard, so don't edit in place: author the new versions as `CLAUDE.md.new` / `agents-fabrik.md.new` /
   `AGENTS.md.new` (steps 1–4 write these), run B5/B6 gates against the `.new` files, then swap all three with
   consecutive `mv` commands (seconds of exposure instead of the whole authoring window) and commit immediately as a
   **single atomic commit**. Still prefer a quiet window — the `mv`+commit guard just stops a sibling turn from ever
   starting against a half-rewritten bootstrap even without one. (The C→A→D→B order already lands B last.)

---

## Phase C — Rubric extractor + arm the review commands (WS-B, the core enforcement)  — ✅ EXECUTED 2026-07-18 (review no-op R1:10/7 R2:3/3 R3:0/0; 11 tests; C2b fleet-sync at Finish post-merge)

**Responsibility:** turn Tier-3 reviews from "reviewer reads the packs" into "the matched rule rubric is injected."
**Files:** `scripts/review_rubric.py` (new), `~/.claude/commands/fabrik-review.md`,
`docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md`,
`docs/orchestrator/epic-to-ticket-workflow/{08-implementation-validation,10-cross-artifact-validation}-fabrik.md`.
**Interfaces — Consumes:** `select_rules.py --json` (relative pack paths). **Produces:**
`review_rubric.py --changed <paths> [--workflow {mega,ettw}]` → emits the injectable rubric: **matched rule-pack
mandates ALWAYS** (the code-review rubric — L3 core, never un-armed); `EVALUATION_CHECKLIST` items **only** when
`--workflow` names a command-chain review (the checklists are command-authoring QA, *not* a code rubric).

1. **Highest-risk behavior FIRST (TDD).** Write `tests/test_review_rubric.py` asserting: (a) a changed path under a
   pack's glob → that pack's mandate lines are emitted; (b) **the mandatory-core floor packs (`core/35-security-auth`,
   `core/25-data-postgres`, `core/30-ops` + the 12-Factor mandates) are ALWAYS emitted regardless of glob** — even for a
   path matching no pack (L3 — never un-armed on the high-blast-radius rules); (c) `--workflow ettw` *additionally* emits
   the ettw checklist items, and **without `--workflow` NO checklist is emitted** (packs only). Run it → RED.
2. **Build `scripts/review_rubric.py`** — **stdlib-only** (it will be synced project-side per step 2b, so no hub-only
   deps) + reuse `select_rules.py`'s frontmatter parser. Interface `--changed <paths> [--workflow {mega,ettw}]`: runs
   `select_rules.py --json`, **joins each returned *relative* pack path to `.windsurf/rules/`** (the `--json` `pack`
   field is `pack.relative_to(rules_dir)`) to read the pack **body**, extracts its mandate lines (`MUST` / `⚠️` /
   `never`). **L3 — mandatory-core floor:** the script **always injects the high-blast-radius packs**
   (`core/35-security-auth`, `core/25-data-postgres`, `core/30-ops`, 12-Factor) **regardless of glob**; glob-matched
   packs add on top. ("Independent selection" of the *same* glob function isn't independence — the floor is what
   guarantees a review is never un-armed.) The `EVALUATION_CHECKLIST_*` items are **command-authoring QA, not a code
   rubric** — unioned **only** with `--workflow`: `mega` reads
   `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`, `ettw` reads
   `docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` (both exist, verified);
   item extraction = the same mandate-line heuristic applied to the checklist's numbered/bulleted items (document
   the exact rule in the script docstring). As a **byproduct**, emit a
   `# promote-to-check_*:` line listing any injected mandate that is a deterministic grep (feeds the spec's Tier-1
   promotion direction). Run test → GREEN.
2b. **Sync `review_rubric.py` project-side (BLOCKING — else it FileNotFoundErrors in every project review).**
   `/fabrik-review` runs *inside each project*, and calls `review_rubric.py` there — exactly why `select_rules.py` +
   `final_gate.py` are already in the sync manifest. Add `scripts/review_rubric.py` to `scripts/fabrik_synced_manifest.py`
   (one line), then run **exactly** `python scripts/sync_enforcement_to_projects.py` (exists, verified; `--dry-run`
   first if cautious) so it propagates. **Gate (two-part):** `grep -q review_rubric scripts/fabrik_synced_manifest.py`
   AND a post-sync sentinel probe `test -f /opt/trade-intelligence/scripts/review_rubric.py && echo synced` →
   `synced` (any synced project works; a manifest entry without a completed sync run still FileNotFoundErrors —
   the sentinel is what proves propagation). This is why step 2 mandates stdlib-only.
3. **Back up the out-of-repo file FIRST (no git rollback — R2):** `cp ~/.claude/commands/fabrik-review.md
   ~/.claude/commands/fabrik-review.md.bak-$(date +%Y%m%d-%H%M%S)`. It lives outside the repo, so there is no
   `git checkout` to undo a bad edit — the timestamped backup is the rollback (the CLAUDE.md credentials-change
   backup pattern applied to the one un-versioned file in scope). Then **wire injection into `/fabrik-review`:**
   replace the *"READ `.windsurf/rules/**` as BINDING CONTEXT"* step
   (`:72`, the migration target) with *"run `python scripts/review_rubric.py --changed <diff paths>` and inject its
   output into every finder's prompt as the rubric they hunt against (G5/G6)."* Keep the static 12-Factor/test-quality
   hunt-lists (belt-and-suspenders).
4. **Wire the same injection step** into mega-`04` (`--workflow mega`) and ettw-`08`/`10` (`--workflow ettw`) — these
   review command-chain *files*, so they inject **both** the rule-pack mandates AND their workflow checklist. Generic
   `/fabrik-review` (step 3) passes **no** `--workflow` → rule-pack mandates only (a code diff has no command checklist).
5. **Honesty (L1/L2):** each edited review command states, once, that the loop is *maximally-enforced, probabilistic —
   not a compliance guarantee* (spec § Known limitations), and that the reviewer selects packs independently of the doer
   (L3). No overclaim.
6. **Gate (functional):** (a) `python scripts/review_rubric.py --changed scripts/final_gate.py` → non-empty, contains
   `.windsurf/rules/core/…` mandate lines and **no** checklist items (no `--workflow`); (b) `python scripts/review_rubric.py
   --changed docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md --workflow mega` → *also* contains
   items from `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`. Expected: both as stated.
7. **Gate (mechanical):** `python scripts/final_gate.py --check --json` on the new script → `"status":"success"`
   (ruff/mypy/bandit on `review_rubric.py`); `pytest tests/test_review_rubric.py -q` green.
8. **Checklist eval:** each edited command file re-evaluated against its `EVALUATION_CHECKLIST_*` (mega/ettw) → 0 FAIL.
9. Doc-sync: `docs/FEATURES.md` (armed-review capability) + `CHANGELOG.md` + `INDEX.md` (new script).
10. **`/fabrik-review`** on the full changed surface (script + 4 command files) — no-op loop.
11. Commit.

---

## Phase D — service_catalog.json mechanical step in 00-trigger (WS-D)  — ✅ EXECUTED 2026-07-19 (review no-op R1:1/1 R2:1/1 R3:0/0; owned-first + LEAD-not-guarantee)

**Responsibility:** make the procurement discipline checkable — consult owned services before proposing a paid one.
**Files:** `docs/orchestrator/mega-epic-breakdown/00-trigger-fabrik.md`. **Interfaces — Consumes:**
`scripts/service_catalog.json` (secret-free). **Produces:** the "consult catalog" step in 00's N3c 6-check + External-
Services grounding.

1. Add to 00-trigger's N3c 6-check ("build-where-consume-exists") + External-Services grounding a **mechanical step:**
   *"read `scripts/service_catalog.json`; if a `status=active` provider already covers the capability, use it — prefer
   `cost=free|freemium`; only live-research a NEW provider if nothing owned fits."* Add `scripts/service_catalog.json`
   to 00's `Reads:` header (so the read is forced, not assumed — Tier-2 compiled).
2. **Gate (functional):** `python -c "import json; d=json.load(open('scripts/service_catalog.json'));
   print(len([k for k in d if not k.startswith('_')]))"` → **== 90 provider entries, 0 triage** (⚠️ filter the
   `_README` meta-key — a bare `len(d)` is 91 and would fail on correct data; verified 2026-07-18). And
   `grep -q 'service_catalog.json' docs/orchestrator/mega-epic-breakdown/00-trigger-fabrik.md`.
3. **Checklist eval:** 00-trigger re-evaluated against `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` → 0 FAIL.
4. Doc-sync: `CHANGELOG.md`.
5. **`/fabrik-review`** on the 00-trigger diff — no-op loop.
6. Commit.

**Final phase doc convergence + FULL gate (runs after the TRUE last phase — B, per the C→A→D→B execution
order; this block sits after D only in file order):** run `/fabrik-docs-review` over the touched docs (north-star,
agents-fabrik.md, CLAUDE.md, FEATURES/INDEX/CHANGELOG) to a truthful fixed point, then the whole-change gate:
- `python scripts/final_gate.py --check --json` → `"status":"success"` (Tier-2 static checks on the one code artifact
  `scripts/review_rubric.py`; markdown-only changes are covered by Tier-1/Tier-3 sprawl/format);
- `python scripts/enforcement/check_convergence.py` → passes (this plan carries `## Evidence` + `## Self-audit` +
  `Status: CONVERGED` once `/fabrik-plan-review` flips it).
Green is necessary, not sufficient — it proves format/citations, not that the enforcement design *works*; the proof
is the Phase-C functional gate (`review_rubric.py` emits a real rubric) + the § Known-limitations honesty (L1).

---

## File Scope (owned paths)

```
docs/orchestrator/00-autonomous-factory-north-star.md
agents-fabrik.md
AGENTS.md
CLAUDE.md
scripts/review_rubric.py
tests/test_review_rubric.py
scripts/fabrik_synced_manifest.py   ⚠️ Phase C step 2b adds review_rubric.py here so it propagates project-side
docs/orchestrator/mega-epic-breakdown/00-trigger-fabrik.md
docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
docs/orchestrator/epic-to-ticket-workflow/08-implementation-validation-fabrik.md
docs/orchestrator/epic-to-ticket-workflow/10-cross-artifact-validation-fabrik.md
docs/FEATURES.md · docs/INDEX.md · CHANGELOG.md
~/.claude/commands/fabrik-review.md   ⚠️ NOT in the fabrik repo (user command dir) — serialization point, edit outside the repo lock
```

⚠️ **CLAUDE.md is a synced/bootstrap file** — confirm it is editable in the hub (`/opt/fabrik` owns it, not a
project) before Phase B; per its File-Ownership row it is the Claude bootstrap (hub-owned here).

## Evidence

- Phase A: north-star has `## Owner Working Model` + `## Decisions` (read this session) → the law section slots beside them.
- Phase B: `CLAUDE.md` = 161 lines, no `@import` (`grep` this session); `AGENTS.md`≈`agents-fabrik.md` = 42 diff lines.
- Phase C: `select_rules.py:104-133` prints packs+descriptions (has `--json`) → extractor reads bodies; `fabrik-review.md:72` = the "READ rules" migration target; `/opt/fabrik-lib/subagents/subagents/agent.py` defines `fanout`/`set_quality`.
- Phase D: `service_catalog.json` = 90 services, 0 triage (verified this session); 00-trigger has the N3c 6-check + External-Services grounding (read this session).
- External grounding inherited from the CONVERGED spec (G1–G7, re-verified 2026-07-18); not re-fetched here.

## Self-audit

- **Coverage:** every "What we agreed" item maps to a phase — governing law→A; AGENTS.md option (b)→B; armed review
  (Tier 3, L2/L3)→C; procurement/catalog→D; L1 honesty→enforced in A+C text; L4→the 4 independently-committable phases.
  **Owner fold-in (2026-07-18):** the front-door reconciliation rides A3 (north-star `:48`-vs-`:60` → three-tier
  model) + B2b (§ Workflow rewrite + archived-twin purge); the `/fabrik-spec` up-route + ettw-00 mirror shipped
  directly the same day (outside this plan's File Scope — no double-touch).
- **Cross-phase consistency:** Phase B consumes Phase A's `## Enforcement Model` by name (C and D carry no
  dependency on it — deliberately, per L4 disjointness); `review_rubric.py`'s
  interface (`--changed <paths>`) is consumed identically in C's four wirings.
- **Fresh-eyes gap check:** the only code artifact is `review_rubric.py` (tested, gated); everything else is
  doc/command prose gated by `/fabrik-review` + checklist-eval. Not yet a fixed point — that's `/fabrik-plan-review`'s job.

## Residual unknowns

- **Resolved:** `@import` loads-in-full + depth-capped (spec G2); catalog is secret-free (this session); all targets
  exist; **R1 — CLAUDE.md is hub-editable, and Phase B's rewrite is FLEET-WIDE** (corrected 2026-07-18: the earlier
  "not in any project `synced.lock`" claim was **wrong** — project locks DO list `CLAUDE.md`; the hub copy is
  editable precisely because the hub is the *source* projects sync FROM, which means B's rewrite **propagates to
  every project on the next sync** — B step 9's atomic-commit + quiet-window care applies doubly, and the stripped
  bootstrap must be correct for ALL projects, not just the hub); toolchain (`python3`/`pytest`/`ruff`/`git`/`claude`)
  all present; `select_rules.py` has `--json`; **catalog endorsed by use** (spec U3 resolved — owner used + corrected
  it to 90/0-triage this session); **select_rules hub-hang FIXED upstream 2026-07-18** (its per-glob `rglob`
  traversed the `.tmp/subagents/` worktree copies and hung at `/opt/fabrik` — rewritten to one pruned walk +
  in-memory matching, hub runtime now ~2s, so every Phase-B/C gate that shells it is runnable as written;
  propagates project-side via the same C2b sync run).
- **Still-open (both self-service — no execution stall):**
  - **R2 — `~/.claude/commands/fabrik-review.md` is outside the fabrik repo.** **Self-service:** Phase C edits it in
    place (a user-command-dir file, not a repo commit) and lists it in the handoff; it is NOT under the repo File-Scope
    lock. The mega/ettw review commands ARE in-repo. No decision owed — the executor just edits it.
  - **R3 — what to `@import` vs `Reads:`-fetch.** **Self-service, criterion = frequency-of-need, NOT size** (spec §
    Constraints): Phase B step 4 `@import`s only the **high-frequency** facts (needed most hub turns); rarely-needed
    platform detail (full VPS topology, the service list) → a `Reads:`-fetched Tier-2 reference — because `@import`
    taxes *every* turn at any size. A ~200-line doc needed 5% of turns still doesn't belong in the auto-load. The
    executor sorts by frequency, not line count.
  - **R4 — pack-count drift (nit, pre-existing, out of scope).** The real count is **55** `.md` packs (the
    chrome-ext launch checklist landed 2026-07-18; the spec already says 55). `fabrik-review.md:68` still says "50";
    this plan doesn't own that reconciliation. **Self-service:** if Phase B/C is already editing the file that
    carries a stale count, align it to 55 (re-run `find .windsurf/rules -name '*.md' | wc -l` first — it drifts);
    else leave it (not this plan's scope).
