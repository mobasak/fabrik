# Plan — Canonical type-aware project-doc registry (SSOT + derived surfaces)

Status: IN-PROGRESS
Spec: docs/superpowers/specs/2026-07-10-doc-registry-reconciliation-design.md (CONVERGED)
Date: 2026-07-10
Converged: 2026-07-10 (/fabrik-plan-review — 2 passes to an edit-free md5-verified no-op; every path:line re-grounded; the import crux fixed — registry imported same-dir (not the hub-only FABRIK_ROOT pattern) + stdlib-only so it resolves project-side; scaffold/manifest/check_doc_sync/final_gate citations verified; sync rglob confirmed to distribute the new enforcement scripts; no deferred questions)

Reconcile Fabrik's project-doc system into **one type-aware registry** that all surfaces derive from — killing the scaffold-seed ↔ check_structure-allowlist ↔ Doc-Sync-Matrix drift, dead templates, phantom allowlist entries, and empty-stub rot. **Build-by-extension** of the existing manifest/enforcement patterns; SSOT (derive, never a 2nd copy); grandfather the 45 existing projects (advisory only).

## Global Constraints (every phase inherits)
- **SSOT invariant:** the `docs/` allowlist + type-aware seed set are **derived** from `PROJECT_DOCS` — never a hand-maintained second copy.
- **Registry home = `scripts/enforcement/_doc_registry.py`** (grounded correction to the spec's "manifest" — the manifest is NOT synced to projects, but `scripts/enforcement/` IS, so `check_structure.py` running in a project can import it; scaffold imports it hub-side).
- **Grandfather:** existing projects are never retro-edited; drift is tolerated advisory (`LEGACY_TOLERATED` superset), never hard-failed. No fleet WARN storm.
- **Fleet-synced surfaces** (`scripts/enforcement/*`, `CLAUDE.md`, `final_gate.py`) re-distribute to ~45 projects on the manifest commit (governance-sync hook / `sync_enforcement_to_projects.py`) — Phase E re-syncs.
- Conventions: kebab-case; new scripts carry a `# AFTER-EDIT:` header; the force-fill check is **advisory** (never blocks a project gate); no `git add -A`.
- Real `SCAFFOLD_TYPES` (`src/fabrik/scaffold.py:137`): python-api, python-api-gpu, saas-skeleton, node-api, file-api, file-worker, wordpress, docusaurus, chrome-extension, mobile-app, desktop-app, static-site.

## Context Ledger
| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED) | goal, registry table, buckets, cleanup list, grandfather strategy | `docs/superpowers/specs/2026-07-10-doc-registry-reconciliation-design.md` |
| Manifest registry→derive pattern | the shape to mirror (constants → derive fn) | `scripts/fabrik_synced_manifest.py:57/66/81` (constants) → `:135 gitignore_dest_paths` → `:169 gitignore_block_text` |
| check_structure allowlist | the hard-coded set to replace with a derived import | `scripts/enforcement/check_structure.py:~202` (`if filename not in {…}`) |
| check_doc_sync trigger-detection | reuse for the force-fill "did a trigger fire?" | `scripts/enforcement/check_doc_sync.py` (`_staged`/`_is_significant_code`/`_has_route_change`/`_schema_doc_for`) |
| final_gate advisory registration | how to register the new advisory check | `scripts/final_gate.py:~674` (`run_optional_check(..., advisory=True)`, e.g. check_subagent_flywheel/check_mutation) |
| scaffold seed | the shared-all map to make type-aware | `src/fabrik/scaffold.py:194 SHARED_TEMPLATE_MAP`; types at `:137` |
| Doc Sync Matrix (authoritative, synced) | every registry doc needs a trigger row | `CLAUDE.md` § Doc Sync Matrix |
| best-practice (1c, inherited) | derive-don't-duplicate SSOT + grandfather-as-shared-contract | SRE Workbook configuration-design; designpatternsinaction.com/dry/ssot; Medium 2026-06-14 (cited in spec) |
| fabrik-lib verdict (inherited) | BUILD-by-extension; no module fits | spec fabrik-lib verdict table |

fabrik-lib checked — no module covers a scaffold-doc registry (the `doc-*` modules are content-processing); build in-fabrik by extension. No 🆕 candidate (hub-governance-specific).

## Behavior Contract
- **Given** a `python-api` project type, **When** `docs_allowlist("python-api")` is derived, **Then** it excludes `BUSINESS_MODEL.md`/`data-contract.md`/`ui-design.md` and includes `SERVICES.md`/`README.md`. *(Mocked: none — pure data.)*
- **Given** the 47-project fleet's existing doc names, **When** the derived allowlist ∪ `LEGACY_TOLERATED` is compared to the old hard-coded set, **Then** it is a superset (no currently-clean project newly WARNs). *(Mocked: none.)*
- **Given** the `_doc_registry` module is missing/unimportable, **When** `check_structure` derives its allowlist, **Then** it falls back to the old literal set and never crashes the gate. *(Mocked: sabotaged `sys.modules["_doc_registry"]`.)*
- **Given** a headless `python-api` scaffold, **When** `_scaffold_shared` seeds docs, **Then** `BUSINESS_MODEL.md`/`STRATEGIC_BACKLOG.md` are NOT seeded but `SERVICES.md`/`README.md` are. *(Mocked: `FABRIK_ROOT`/`TEMPLATE_DIR`, `subprocess.run`.)*
- **Given** a `saas-skeleton` scaffold, **When** docs are seeded, **Then** `BUSINESS_MODEL.md` + `data-contract.md` are present. *(Mocked: as above.)*
- **Given** a `docusaurus` scaffold, **When** docs are seeded, **Then** any `data`-bucket doc (incl. `data-contract.md`) is skipped (leak guard). *(Mocked: as above.)*
- **Given** a malformed registry that raises on use, **When** `_should_seed_doc` is called, **Then** it returns True (degrades to seeding) and never raises. *(Mocked: a registry stub whose `PROJECT_DOCS` raises.)*
- **Given** a staged `compose.yaml` change and a placeholder-bearing `docs/SERVICES.md`, **When** `check_doc_stubs` runs, **Then** it WARNs and exits 0. *(Mocked: `_staged()` return value, temp cwd.)*
- **Given** any git error inside `check_doc_stubs`, **When** it runs, **Then** it exits 0 (advisory never blocks). *(Mocked: `_staged()` raises.)*
- **Mocked:** scaffold integration tests mock the fabrik root + `subprocess.run`; registry/allowlist/stub-detector tests run against real data with the trigger inputs mocked.

## Phase A — The registry (SSOT) + `docs_allowlist()` derivation — ✅ EXECUTED 2026-07-11
**Files:** `scripts/enforcement/_doc_registry.py` (new), `tests/test_doc_registry.py` (new).
**Responsibility:** the single source of truth + the derivation. No consumers change yet.
**Produces:** `PROJECT_DOCS: list[DocRow]` (`name`, `template`, `applies_to: frozenset[str]` bucket-name(s), `trigger: str`, `fills: str`); `TYPE_BUCKETS: dict[str, frozenset[str]]` (bucket → SCAFFOLD_TYPES: `universal`=all 12; `deployed`={python-api,python-api-gpu,node-api,file-api,file-worker,saas-skeleton,wordpress}; `gui`={saas-skeleton,chrome-extension,mobile-app,desktop-app,static-site,docusaurus}; `saas`={saas-skeleton}; `data`= resolved per-project via `shape.needs_database`, not a fixed type set); `LEGACY_TOLERATED: frozenset[str]` (docs older projects carry that aren't in the registry — grounded in step A1); `docs_allowlist(project_type: str | None = None) -> frozenset[str]` (basenames of `docs/*.md` for the type, or the full union when `None`).

Steps:
1. **Ground `LEGACY_TOLERATED`** — grep the fleet for `docs/*.md` names not in the registry: `for d in /opt/*/docs/*.md; do basename "$d"; done | sort -u` → any not in `PROJECT_DOCS` (e.g. `DEPLOYMENT.md`, `FAQ.md`, `EXTERNAL_SYSTEMS.md`, `lessons-learnt.md`) goes in `LEGACY_TOLERATED`. **Gate:** the command prints the set; assert every current-project doc basename ∈ `docs_allowlist() | LEGACY_TOLERATED`.
2. **Write `_doc_registry.py`** from the spec's canonical registry table (the 23 rows). **Stdlib-only — no third-party or heavy fabrik imports** (it is imported by `check_structure`/`check_doc_stubs` running in a bare project with only stdlib guaranteed; pure data + `docs_allowlist()`). `# AFTER-EDIT: scripts/enforcement/check_structure.py, src/fabrik/scaffold.py, scripts/enforcement/check_doc_stubs.py` header.
3. **Behavior Contract (tests):** (a) `docs_allowlist("python-api")` excludes `BUSINESS_MODEL.md`/`data-contract.md`/`ui-design.md`, includes `README.md`/`SERVICES.md`; (b) `docs_allowlist("saas-skeleton")` includes `BUSINESS_MODEL.md`; (c) `docs_allowlist()` (None) == union of all buckets; (d) `docs_allowlist() | LEGACY_TOLERATED` is a superset of every existing-project doc basename (the grandfather guarantee); (e) every `PROJECT_DOCS` row's `applies_to` names a real bucket + its `template` (if not None) exists on disk.
**Gate:** `python -m pytest tests/test_doc_registry.py -q` → pass. `python -c "import sys; sys.path.insert(0,'scripts/enforcement'); from _doc_registry import docs_allowlist; print(sorted(docs_allowlist('python-api')))"` → prints the derived set.
**Close:** phase gate green → `check_doc_sync.py` (+ CHANGELOG entry) → `/fabrik-review` to a no-op → commit (explicit paths + trailers).

## Phase B — Derive the `check_structure` allowlist (drop the hard-coded copy) — ✅ EXECUTED 2026-07-11
**Files:** `scripts/enforcement/check_structure.py`, `tests/test_check_structure_docs_allowlist.py` (new).
**Consumes:** `_doc_registry.docs_allowlist`, `LEGACY_TOLERATED` (Phase A).
Steps:
1. Replace the literal `{…}` set (`:~202`) with an import of `_doc_registry` **from check_structure's OWN directory** — `sys.path.insert(0, str(Path(__file__).resolve().parent)); import _doc_registry` — then `if filename not in (_doc_registry.docs_allowlist() | _doc_registry.LEGACY_TOLERATED):`. **⚠️ Do NOT use the `sys.path.insert(0, FABRIK_ROOT/"scripts")` pattern some scripts use (e.g. `check_synced_unmodified.py:47`)** — `FABRIK_ROOT` is hardcoded `/opt/fabrik`, so a project would import the HUB's registry instead of its own synced copy. The registry is synced sibling-to-sibling in `scripts/enforcement/`, so same-dir import is correct in both hub and project. Fail-safe: wrap the import in `try/except`; on failure fall back to the previous literal set kept as `_FALLBACK_ALLOWLIST` (never crash the gate).
2. **Behavior Contract:** (a) a registry doc (`RESILIENCE.md`, `data-contract.md`) no longer WARNs (defect-1 class gone); (b) a legacy doc (`DEPLOYMENT.md`) is tolerated; (c) a genuinely-misplaced doc (`docs/random.md`) still WARNs; (d) import-failure → fallback set, no crash.
**Gate:** `python -m pytest tests/test_check_structure_docs_allowlist.py -q` → pass; `python scripts/enforcement/check_structure.py` on a fixture project with `docs/RESILIENCE.md` → no WARN for it.
**Close:** gate → doc-sync + CHANGELOG → `/fabrik-review` no-op → commit.

## Phase C — Type-aware scaffold seeding — ✅ EXECUTED 2026-07-11 (data-contract gating: grounded deviation — kept all-but-docusaurus, see below)
**Files:** `src/fabrik/scaffold.py`, `tests/test_scaffold_doc_seeding.py` (new).
**Consumes:** `PROJECT_DOCS`, `TYPE_BUCKETS` (Phase A).
Steps:
1. In `scaffold.py`, import the registry via the **same mechanism scaffold already uses for the manifest** — `_fabrik_synced_gitignore_block()` (`~scaffold.py:361`) does `sys.path.insert(0, str(FABRIK_ROOT / "scripts")); from fabrik_synced_manifest import …`; mirror it as `sys.path.insert(0, str(FABRIK_ROOT / "scripts" / "enforcement")); import _doc_registry` (hub-only — scaffold runs on the hub). Drive doc seeding from `PROJECT_DOCS`: seed a row's `template`→`name` **only when** `project_type` is in a bucket the row's `applies_to` covers (universal always; deployed/gui/saas per type; `data` when the scaffold's `shape.needs_database`). Keep `SHARED_TEMPLATE_MAP` for the truly-universal file→name mapping OR replace it with the registry rows (decide in-phase; keep behavior identical for universal docs). Do not seed rows with `template=None` (command-authored: ui-design/design-system) or `applies_to` the type lacks.
2. **Behavior Contract:** (a) scaffolding a `python-api` seeds README/INDEX/QUICKSTART/CONFIGURATION/…/SERVICES but **not** `BUSINESS_MODEL.md`/`data-contract.md`/`ui-design.md`; (b) a `saas-skeleton` seeds `BUSINESS_MODEL.md` + `data-contract.md`; (c) a `docusaurus` still skips `data-contract.md` (existing `_NO_DATA_CONTRACT_TYPES` honored); (d) no seeded doc is one that `docs_allowlist(type)` would reject.
**Gate:** `python -m pytest tests/test_scaffold_doc_seeding.py -q` → pass (use the scaffolder's existing test harness / a tmp dir).
**Close:** gate → doc-sync + CHANGELOG → `/fabrik-review` no-op → commit.

## Phase D — Force-fill: `check_doc_stubs.py` (advisory) — ✅ EXECUTED 2026-07-11
**Files:** `scripts/enforcement/check_doc_stubs.py` (new), `tests/test_check_doc_stubs.py` (new), `scripts/final_gate.py` (register advisory).
**Consumes:** `check_doc_sync` trigger-detection helpers; `PROJECT_DOCS` triggers (Phase A).
Steps:
1. Write `check_doc_stubs.py`: reuse `check_doc_sync`'s `_staged()`/`_is_significant_code()`/`_has_route_change()`/`_schema_doc_for()` (import or mirror) to decide **which registry docs' triggers fired in the staged change**; for each such doc that exists AND still contains a placeholder sentinel (`[Project Name]`, `[PROJECT_NAME]`, `{PROJECT_NAME}`, `YYYY-MM-DD`, `[DATE]`) → **WARN** (print, exit 0). Fail-safe: ANY exception/git-failure → exit 0. `# AFTER-EDIT: none` header.
2. Register in `final_gate.py` (`:~674`) via `run_optional_check("scripts/enforcement/check_doc_stubs.py", "Doc stub fill (advisory)", advisory=True)`.
3. **Behavior Contract:** (a) a doc whose trigger fired + has placeholders → WARN; (b) same doc, placeholders removed → no WARN; (c) trigger did NOT fire → no WARN even with placeholders (a stub is fine until relevant); (d) any git/parse error → exit 0 (advisory never blocks); (e) `final_gate` still reports `status:success` when only this WARNs.
**Gate:** `python -m pytest tests/test_check_doc_stubs.py -q` → pass; `python scripts/final_gate.py --check --json` → `status:success` (advisory doesn't fail it).
**Close:** gate → doc-sync + CHANGELOG → `/fabrik-review` no-op → commit.

## Phase E — Cleanup + Doc-Sync-Matrix alignment + fleet re-sync
**Files:** `templates/scaffold/docs/API_REFERENCE_TEMPLATE.md` + `DATABASE_SCHEMA_TEMPLATE.md` → `templates/.archive/` (git mv), `~/.claude/commands/fabrik-plan-after-chat.md`, `CLAUDE.md`, `INDEX.md`.
Steps:
1. `git mv` the 2 dead templates → `templates/.archive/` (verify no live seed/allowlist reference remains: `grep -rn "API_REFERENCE_TEMPLATE\|DATABASE_SCHEMA_TEMPLATE" src/ scripts/ templates/scaffold/` → only archive path).
2. Fix `~/.claude/commands/fabrik-plan-after-chat.md:240` — `schema → db/schema.sql + docs/DATABASE_SCHEMA.md` → `schema → db/schema.sql + docs/data-contract.md` (matches CLAUDE.md; the structure gate rejects DATABASE_SCHEMA.md).
3. Align `CLAUDE.md` Doc Sync Matrix — ensure every registry doc with an agent-fill has a trigger row (add rows for any registry doc missing one: e.g. LESSONS_LEARNT end-of-run, docs/README doc-added/removed). Canonicalize `LESSONS_LEARNT.md` (the registry name; note lowercase legacy is `LEGACY_TOLERATED`).
4. Update `INDEX.md` (new files: `_doc_registry.py`, `check_doc_stubs.py`, the 3 new tests; archived templates).
5. **Re-sync the fleet:** `python scripts/sync_enforcement_to_projects.py` (distributes `_doc_registry.py`, updated `check_structure.py`, `check_doc_stubs.py`, `final_gate.py`, `CLAUDE.md` to ~45 projects). Confirm a spot project: `ls /opt/captcha/scripts/enforcement/_doc_registry.py` present; `python /opt/captcha/scripts/enforcement/check_structure.py` → no new WARN storm.
**Gate:** `python scripts/final_gate.py --check --json` → `status:success`; the grep in step 1 clean; the fabrik-plan-after-chat line fixed (`grep -n DATABASE_SCHEMA ~/.claude/commands/fabrik-plan-after-chat.md` → empty).
**Close:** gate → **`/fabrik-docs-review`** (converge docs) → `/fabrik-review` over the cleanup surface no-op → commit.

## Phase 3 pillars (baked in above)
- **`/fabrik-review` at every phase boundary** — a written closing step in each phase (A–E), looped to a no-op.
- **Subagents — POOL-DEFAULT** (per `62 § Dispatch policy`): the per-phase implementer + finder fan-out uses the OpenRouter pool (`run_agents`/`pick_models`, records the flywheel); native `fabrik-reviewer` (Opus) added on top only for the highest-risk slice — here that's Phase B/D (enforcement-gate logic that runs fleet-wide). The plan-authored Behavior-Contract tests are authored by the pool (`/fabrik-generate-tests`).
- **Parallelism:** Phases A→B→C→D are largely **sequential** (B/C/D consume A's registry). Within a phase, test-authoring fans out (one pool author per Behavior-Contract test, disjoint owned_paths). Phase E is sequential (cleanup + sync). No inter-phase parallelism (shared registry dependency).

## File Scope (owned paths)
- `scripts/enforcement/_doc_registry.py` (new)
- `scripts/enforcement/check_structure.py`
- `scripts/enforcement/check_doc_stubs.py` (new)
- `scripts/final_gate.py`
- `src/fabrik/scaffold.py`
- `tests/test_doc_registry.py`, `tests/test_check_structure_docs_allowlist.py`, `tests/test_scaffold_doc_seeding.py`, `tests/test_check_doc_stubs.py` (new)
- `templates/scaffold/docs/API_REFERENCE_TEMPLATE.md`, `templates/scaffold/docs/DATABASE_SCHEMA_TEMPLATE.md` (→ `templates/.archive/`)
- `~/.claude/commands/fabrik-plan-after-chat.md` (user-level command — line 240)
- `CLAUDE.md`, `INDEX.md`, `CHANGELOG.md`

## Evidence
- **A/B (registry home correction):** `ls /opt/captcha/scripts/fabrik_synced_manifest.py` → *No such file* (manifest NOT synced to projects) ⟹ registry must live in synced `scripts/enforcement/`. `scripts/enforcement/` IS in the sync set (`fabrik_synced_manifest.py:74 ENFORCEMENT_DIR`).
- **A (types):** `scaffold.py:137` SCAFFOLD_TYPES = the 12 real types (read this session).
- **B (allowlist):** `check_structure.py:~202` `if filename not in {README.md, QUICKSTART.md, …}` (read this session).
- **D (reuse + registration):** `check_doc_sync.py` has `_staged`/`_is_significant_code`/`_has_route_change`/`_schema_doc_for`; `final_gate.py:~674` registers check_subagent_flywheel/check_mutation via `run_optional_check(..., advisory=True)`. Placeholder sentinels present: `[Project Name]`×27, `YYYY-MM-DD`×46, `{PROJECT_NAME}`×8, `[DATE]`×2, `[PROJECT_NAME]`×1.
- **E (stale ref):** `grep -n DATABASE_SCHEMA ~/.claude/commands/fabrik-plan-after-chat.md` → `:240 schema → db/schema.sql + docs/DATABASE_SCHEMA.md`.

## Self-audit
- **Coverage vs "what we agreed":** registry (A) · derive allowlist (B) · type-aware seed (C) · force-fill WARN (D) · cleanup + stale-ref fix + canonicalize + matrix align + re-sync (E). All 6 spec deliverables mapped to a phase. ✓
- **Cross-phase signatures:** `docs_allowlist()`/`PROJECT_DOCS`/`TYPE_BUCKETS`/`LEGACY_TOLERATED` produced in A, consumed by B (allowlist), C (seed), D (triggers) with identical names. ✓
- **Grounding correction recorded:** registry home = `scripts/enforcement/_doc_registry.py` (not the manifest) — the one design detail the spec left as "proposed" that Phase-1 grounding settled.

## Residual unknowns
- **RESOLVED:** registry home (enforcement/, synced); type buckets + membership (spec + `SCAFFOLD_TYPES`); grandfather via `LEGACY_TOLERATED` (Phase-A step 1 grounds the exact set from the live fleet).
- **Still-open (self-service, non-blocking):** whether Phase C keeps `SHARED_TEMPLATE_MAP` for universal file→name mapping or folds it fully into `PROJECT_DOCS` — decide in-phase to keep universal-doc behavior byte-identical (default: keep the map for universal, gate seeding by `applies_to`). The exact `data`-bucket resolution (`shape.needs_database`) at scaffold time — read the scaffold's shape input, same mechanism as `_NO_DATA_CONTRACT_TYPES`.
