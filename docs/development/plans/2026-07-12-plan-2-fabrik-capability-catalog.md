# Plan — Fabrik Capability Catalog + Tool-Doc Audit

**Status:** CONVERGED (2026-07-12) — `/fabrik-plan-review` fixed point, independently verified (pool `fanout` + native Opus `fabrik-researcher`, per the mandated floor). Pass 1 found **4 real defects** — the load-bearing one: `doc_reconcile.reconcile_doc` is diff-driven + edit-only (no delete path), so it CANNOT drive the doc-audit → Phase B rebuilt as a BUILD (corrects the spec's inherited "VENDOR+ENHANCE doc_reconcile" verdict); plus the CLI probe (`sys.executable` + whole-surface-broken guard), the flat `.commands` walk (→ recurse the 7 nested groups, 54 vs 23), and the untestable `manual` status (→ marker/no-safe-probe rule); dry-run-by-default added for the dead-doc delete. Pass 2 confirmed all + fixed a wrong `path:line` citation. Pass 3 = a genuine independent no-op (0 defects) on md5 `43bdf092`.

**Spec (source of truth):** `docs/superpowers/specs/2026-07-12-fabrik-capability-catalog-design.md` (CONVERGED r4,
independently verified). This plan INHERITS its grounding — the vendor verdict (BUILD the generator, VENDOR+ENHANCE
the doc-reconcile scripts, VENDOR the llms.txt format), the external facts (llms.txt/agents.md), and the surface
counts — and does not re-derive them.

**Goal.** A generated, self-verifying catalog of every invokable capability in the fabrik repo, so any AI
planner/orchestrator agent discovers + correctly invokes every tool with zero onboarding — plus a doc-audit that
surfaces broken/retired/incomplete tools. Two artifacts: `capabilities.json` (machine-readable) + `docs/CAPABILITIES.md`
(llms.txt-style).

---

## Global Constraints (every phase inherits these — copied verbatim from the binding sources)

- **Hub-side only.** All work is in `/opt/fabrik` (a new `scripts/`, generated artifacts, doc updates). **No** DB,
  cache, metrics, search, auth, admin → **no `shape:` flags, no scaffold, no deploy, no `compose.yaml`.** Do NOT emit
  any `fabrik …` command as a gate (hub-side CLI; but this plan runs IN the hub, so `python -c`/`pytest`/`ruff` gates are correct).
- **Naming:** kebab-case files; Python modules snake_case (`generate_capability_index.py`) — `CLAUDE.md` § Naming.
- **Script coupling header** (`core/90-bootstrap-scripts.md` + `CLAUDE.md`): every `scripts/**/*.py` carries a
  `# AFTER-EDIT: <coupled files | none>` line in its first ~25 lines. Gate-enforced (WARN) by `check_script_headers.py`.
- **No hardcoded secrets/localhost; no silent failures** — read-only introspection; a probe that errors is recorded as
  `broken`, never crashes the run (fail-soft per `core/58-resilience.md`).
- **Generated-not-hand-curated:** the catalog is a build artifact, re-derived; never hand-edit `capabilities.json`/
  `CAPABILITIES.md` (they're regenerated).
- **Testing** (`core/45-testing-strategy.md`): one test per distinct user-observable behavior, risk-ordered, TDD for the
  risky path. Lean-but-complete, not 100%-coverage.

## Context Ledger (binding sources — a cold executor inherits full awareness here)

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | how the Python generator is written (stdlib-first, typed) | pack |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | doc-audit reconciliation discipline + Doc Sync Matrix | pack |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, TDD risky path | pack |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default fan-out + `record`/`set_quality` flywheel | pack |
| `.windsurf/rules/core/90-bootstrap-scripts.md` (ACTIVE) | `scripts/**` conventions + the `# AFTER-EDIT:` coupling header | pack |
| `.windsurf/rules/core/58-resilience.md` (ACTIVE) | fail-soft: a probe error → `broken`, never crash the generator | pack |
| **BUILD** — repo introspection + liveness verify | no fabrik-lib module fits (spec §verdict) → build `scripts/generate_capability_index.py`, following the precedent | `scripts/kilo-benchmarks/generate_model_capabilities.py` (source→MD generator) + `verify_openrouter_catalog.py` (catalog+verify) |
| **BUILD** — doc-audit mechanical fixes | `doc_reconcile.py` does NOT fit (grounded 2026-07-12: `reconcile_doc` `:288` is **diff-driven** + **edit-only** via `git apply` `:235`, no delete path) → Phase B builds the audit's file ops directly. *Corrects the spec's over-optimistic "VENDOR+ENHANCE doc_reconcile."* | `scripts/doc_reconcile.py:288` (read — proves the API mismatch); Phase B builds `scripts/audit_capability_docs.py` |
| **VENDOR (validate)** — doc gates | validate the audit result | `scripts/enforcement/check_docs.py` + `check_doc_sync.py` (used to check, not to reconcile) |
| **VENDOR (existing)** — daily regeneration | wire the generator into the daily pipeline | `scripts/kilo-benchmarks/daily_refresh.sh` (lockfile `/tmp/.fabrik_daily_$(date -u +%Y%m%d)`, `:85`) + `scripts/wsl_startup_hook.sh` |
| **VENDOR (format)** — llms.txt | `docs/CAPABILITIES.md` structure: H1 + blockquote + H2 link-lists | `https://llmstxt.org/` (spec §External deps, fetched 2026-07-12) |
| Enumeration points (introspection targets) | the 7 surfaces the generator reads | CLI `@cli.command(` `src/fabrik/cli.py`; drivers `src/fabrik/drivers/*.py`; `_REGISTRAR_ORDER` `src/fabrik/orchestrator/infrastructure.py:90`; `SCAFFOLD_TYPES` `src/fabrik/scaffold.py:138`; `templates/*/`; `/opt/fabrik-lib/README.md`+dirs; `.windsurf/rules/**/*.md` |
| Doc Sync Matrix (`CLAUDE.md`) | file added → `INDEX.md`; new script → `INDEX.md`; always `CHANGELOG.md`; new doc → `docs/README.md` | `CLAUDE.md` § Doc Sync Matrix |

**🆕 fabrik-lib candidate:** none — repo-introspection is fabrik-hub-specific (fails the generic + ≥2-project-type bar; spec §verdict).

---

## Phase A — Catalog generator + manifest (C1)

**Deliverable:** `scripts/generate_capability_index.py` that enumerates all 7 surfaces, liveness-verifies each, and
emits `capabilities.json` + `docs/CAPABILITIES.md` (+ root `/llms.txt`) — wired into the daily pipeline. Ships
standalone value (the catalog exists + self-verifies).

**Files:**
- **Create** `scripts/generate_capability_index.py` — the generator (single responsibility: introspect → verify → emit).
- **Create** `tests/test_generate_capability_index.py` — the Behavior-Contract tests.
- **Generate** `capabilities.json` (repo root), `docs/CAPABILITIES.md`, `/llms.txt` (committed as the first snapshot).
- **Modify** `scripts/kilo-benchmarks/daily_refresh.sh` — add a step calling the generator (inside the existing lockfile block).
- **Modify** `INDEX.md` (rows for the new script + artifacts), `CHANGELOG.md`, `docs/README.md` (new `docs/CAPABILITIES.md`).

**Interfaces — Produces (Phase B consumes):**
- `capabilities.json` schema: `{ "generated_at": ISO8601, "capabilities": [ { "name": str, "kind": "cli"|"driver"|"registrar"|"script"|"lib-module"|"scaffold"|"rules-pack", "summary": str, "invoke": str, "status": "ok"|"broken"|"retired"|"manual", "defects": [ "broken"|"retired"|"doc_drift"|"incomplete"|"undocumented"|"dead_doc" ], "doc_link": str|null, "verified_at": ISO8601 } ] }`
- `scripts/generate_capability_index.py::build_catalog(root: Path) -> list[dict]` (the records) and `main()` (writes the files). **Consumes:** nothing (reads the live repo).

**Behavior Contract (risk-ordered; TDD the security/correctness-critical ones):**
1. **[RISK, TDD] A probe that errors → `status:"broken"` + excluded from the usable set, and the generator does NOT crash** (fail-soft). *Test first: seed a fake CLI verb whose `--help` exits non-zero → assert its record is `broken` and the run completes.*
2. **[RISK, TDD] A tool with a `# DEPRECATED`/`RETIRED` marker (or a doc saying so) → `status:"retired"`** (retire-candidate, not auto-removed).
3. **[TDD] A tool the generator cannot safely auto-probe → `status:"manual"`** (offered with a caution flag), by a defined **detection rule** (so it's testable): a script/tool is `manual` iff it carries an explicit `# CATALOG-MANUAL` (or `# DESTRUCTIVE`) header marker **OR** it exposes no safe probe (no `--help`/`--check` flag detected in its arg-parser/help, not importable, and not a header-parseable script) — i.e. running it to verify would have side effects, so it's deferred to the operator rather than auto-run. *Test: seed a script with a `# CATALOG-MANUAL` marker + no `--help` → assert `status:"manual"`, not `broken`.*
4. **The catalog covers all 7 surfaces** — `len(capabilities) ≥ 250`; every `kind` present.
5. **`docs/CAPABILITIES.md` is valid llms.txt** — first line is a single `# H1`; a `>` blockquote follows; each `## H2` section is a markdown link-list `[name](url): summary`.
6. **`capabilities.json` is valid** against the Interfaces schema (every record has the 8 keys; `status` in the enum).
7. **[RISK] Whole-surface-broken guard** — if every entry of a `kind` probes `broken` (e.g. a bad interpreter path), the generator RAISES rather than emitting a silently-all-broken catalog. *Test: point the CLI probe at a non-existent interpreter → assert it raises, not that it writes 23+ `broken` CLI records.*

**Steps:**
1. **[TDD-red]** Write `tests/test_generate_capability_index.py::test_broken_probe_is_flagged_not_crashing` — build the catalog over a tmp repo fixture containing one deliberately-broken CLI stub; assert the record is `status:"broken"`, excluded from `[c for c in caps if c["status"]=="ok"]`, and `build_catalog` returned (no exception). Run → **confirm RED** (no generator yet). Gate: `.venv/bin/python -m pytest tests/test_generate_capability_index.py -k broken -x` → fails for the right reason (ImportError/AttributeError on the missing module).
2. Implement `scripts/generate_capability_index.py` (carry the `# AFTER-EDIT: INDEX.md, docs/README.md, scripts/kilo-benchmarks/daily_refresh.sh` header):
   - **Enumerate** per surface: CLI = import `src.fabrik.cli` + **recursively** walk the click group — for each entry, if it is a `click.Group` (the 7 `@cli.group()` groups in `cli.py`: `preplan`/`ai`/`domain`/`content`/`seo`/`vultr`/`gpu`), descend into its `.commands` and record each leaf as `<group> <subcommand>` (a flat `.commands` walk misses the ~31 nested subcommands and defeats the "invoke every tool" goal — there are **54** `@*.command(` decorators vs 23 top-level `@cli.command`). Probe each leaf via `subprocess.run([sys.executable,"-m","fabrik.cli",*verb_path,"--help"])` exit 0 — **`sys.executable`, NOT bare `python`** (a PATH `python` without fabrik installed would ModuleNotFound → fail-soft would silently mark the *entire* CLI surface `broken`); drivers = `src/fabrik/drivers/*.py` minus `__init__.py`, probe = `importlib` import; registrars = import `_REGISTRAR_ORDER`; scripts = top-level `scripts/*.{py,sh}` + the named subdirs (`enforcement`,`sysadmin`,`utils`,`probes`,`aro-wake`) minus `.archive/`, probe = `--help`/`--check` or header parse; lib-modules = dir-backed rows of `/opt/fabrik-lib/README.md` (62 non-hidden dirs − 4 non-module), probe = import/README-row-present; scaffolds = `templates/*/` tagged `scaffold` (∈ `SCAFFOLD_TYPES`) vs `helper`; rules = `.windsurf/rules/**/*.md`, probe = file parses.
   - **Classify** `status` (ok/broken/retired/manual) + build `defects[]`. **Whole-surface sanity guard:** if ALL entries of a `kind` come back `broken`, that is an environment/generator error (not N broken tools) — raise, don't emit a silently-all-broken catalog (Behavior 7).
   - **Emit** `capabilities.json` (root) + `docs/CAPABILITIES.md` (llms.txt: H1 + blockquote + one `## H2` per kind, link-list rows) + `/llms.txt` (pointer to CAPABILITIES.md). Fail-soft per probe.
3. Run the Behavior-Contract tests to green: `.venv/bin/python -m pytest tests/test_generate_capability_index.py -x` → all pass.
4. Generate the first snapshot: `.venv/bin/python scripts/generate_capability_index.py`; assert artifacts written: `test -f capabilities.json && test -f docs/CAPABILITIES.md && test -f llms.txt`. Gate (**stdlib `python`, not `jq` — jq is present today but the gate must not depend on it**): `.venv/bin/python -c "import json; d=json.load(open('capabilities.json')); assert len(d['capabilities'])>=250, len(d['capabilities']); assert all(c['invoke'] for c in d['capabilities'] if c['status']=='ok')"` → exit 0; `head -1 docs/CAPABILITIES.md | grep -qE '^# '` (valid llms.txt H1).
5. Wire into the daily pipeline: add to `scripts/kilo-benchmarks/daily_refresh.sh` (inside the lockfile block) a line running the generator. Gate: `grep -q generate_capability_index scripts/kilo-benchmarks/daily_refresh.sh`.
6. **Docs (Doc Sync Matrix — pool-reconciled + native-verified via `scripts/doc_reconcile.py`, not hand-drafted):** `INDEX.md` rows for `scripts/generate_capability_index.py` + `capabilities.json` + `docs/CAPABILITIES.md` + `llms.txt`; `docs/README.md` row for `docs/CAPABILITIES.md`; `CHANGELOG.md` `### Added — Fabrik capability catalog generator (2026-07-12)`. Gate: `python scripts/enforcement/check_doc_sync.py` → any WARNING whose trigger is in THIS phase's diff is BLOCKING.
7. **Phase-A closing sequence (literal steps):** (a) phase gate green (steps 3–6); (b) `python scripts/enforcement/check_doc_sync.py` + the doc steps above; (c) **`/fabrik-review` on Phase A's changed surface** (`scripts/generate_capability_index.py` + tests + `daily_refresh.sh`) — full adversarial methodology (pool `minimax/minimax-m3` finders `fanout("review")` + native `fabrik-reviewer` for the introspection/subprocess-safety slices → refute → prove-before-fix with a kept regression test), **looped to a no-op pass** (0 CONFIRMED/PLAUSIBLE); re-run the gate after each fix; (d) `python scripts/final_gate.py --check --json` → `"status":"success"` + `python scripts/enforcement/check_convergence.py`; (e) commit (explicit paths + `Agent-Role: primary`/`Agent-Phase: A` trailers). **Non-GUI phase → no Build Verification Loop.**

---

## Phase B — Doc-audit + defect ledger (C2)

**Deliverable:** the doc-audit that consumes Phase A's `capabilities.json` `defects[]`, **mechanically resolves**
the fixable set (`dead_doc` → delete the orphan doc; `undocumented` → write a stub + link; `doc_drift` → flag in
the report), and rolls `broken`/`retired`/`incomplete` into an operator-facing defect ledger. Never auto-removes a tool.

**⚠️ Vendor-verdict correction (grounded 2026-07-12, overrides the spec's inherited "VENDOR+ENHANCE doc_reconcile"):**
`scripts/doc_reconcile.py::reconcile_doc(doc, diff_text, root, verify_fn)` is **diff-driven** (it embeds a code-change
unified diff in its pool prompt, `:257-271`) and **edit-only** (sole write path `_apply_patch` = `git apply`,
`:235-243`) — it has **no deletion path** and requires a `diff_text` the catalog audit does not have. So it does NOT
fit a defect-list-driven audit that must delete dead docs → **this phase BUILDs the audit's mechanical actions
directly** (plain `pathlib` file ops), and does **not** modify or drive `doc_reconcile.py`. (`check_docs.py` /
`check_doc_sync.py` are still used to *validate* the result.)

**Files:**
- **Create** `scripts/audit_capability_docs.py` — consumes `capabilities.json`, applies the mechanical fixes (unlink dead docs / write undocumented stubs / flag drift), emits `docs/development/capability-defects.md` (the operator report). (`# AFTER-EDIT: INDEX.md`.)
- **Create** `tests/test_audit_capability_docs.py`.
- **Modify** `INDEX.md`, `CHANGELOG.md`.
- *(No `scripts/doc_reconcile.py` edit — the shared-file serialization point is removed.)*

**Interfaces — Consumes:** Phase A's `capabilities.json` (the 8-key schema above). **Produces:** `docs/development/capability-defects.md` (the operator ledger); `scripts/audit_capability_docs.py::run(catalog_path: Path) -> AuditReport` (`AuditReport = {fixed: list[str], operator_action: list[dict]}`).

**Behavior Contract (risk-ordered; TDD the destructive path):**
1. **[RISK, TDD] Dry-run by default; under `--apply` a `dead_doc` orphan is deleted; `broken`/`retired`/`incomplete` → surfaced in the report and NO tool file is ever touched** (operator-authority + shared-tree). *Test first: seed a catalog json with one `dead_doc` (real tmp doc) + one `retired` tool; assert (a) default run does NOT delete (dry-run) but lists it, (b) `--apply` unlinks the dead doc, (c) the retired tool is in `operator_action` and its own file is untouched in both modes.*
2. **`undocumented` → a stub doc is written + linked; `doc_drift` → flagged in the report (not silently rewritten).**
3. **Idempotent:** re-running over an already-clean catalog (no defects) produces an empty operator ledger + zero file changes.

**Steps:**
1. **[TDD-red]** `tests/test_audit_capability_docs.py::test_dead_doc_deleted_and_tool_never_removed` — seed the catalog json + a real tmp orphan doc; assert unlink + retired-in-report + tool-file untouched. Run → **RED**. Gate: `.venv/bin/python -m pytest tests/test_audit_capability_docs.py -k dead_doc -x` → fails for the right reason (no module yet).
2. Implement `scripts/audit_capability_docs.py` (**dry-run by default — CLAUDE.md HARD STOP "destructive script w/o dry-run"; `--apply` to execute the unlinks/stubs**): load `capabilities.json`; partition `defects[]`; **mechanical set** — `dead_doc` → `pathlib.Path(doc_link).unlink(missing_ok=True)` (only under `--apply`; dry-run lists what it *would* delete), `undocumented` → write a stub `.md` + set `doc_link` (under `--apply`), `doc_drift` → append to the report; **operator set** (`broken`/`retired`/`incomplete`) → `docs/development/capability-defects.md` with the recommended action (fix / retire-decision / revise). Never unlink a *tool* file. The report always lists the full dry-run plan.
3. Tests green: `.venv/bin/python -m pytest tests/test_audit_capability_docs.py -x`.
4. Run it: `.venv/bin/python scripts/audit_capability_docs.py capabilities.json`; Gate: `test -f docs/development/capability-defects.md`; `.venv/bin/python -m scripts.enforcement.check_docs` → exit 0.
5. **Docs:** `INDEX.md` rows (new script + `capability-defects.md`); `CHANGELOG.md` `### Added — capability doc-audit + defect ledger`. Gate: `python scripts/enforcement/check_doc_sync.py`.
6. **`/fabrik-docs-review`** on the changed docs surface (the catalog + defect ledger + any reconciled docs) — converge to a truthful fixed point.
7. **Phase-B closing sequence (literal):** (a) phase gate green; (b) `check_doc_sync.py` + doc steps; (c) **`/fabrik-review` on Phase B's changed surface** — full adversarial methodology (pool `fanout("review")` `minimax/minimax-m3` finders + native `fabrik-reviewer` for the destructive-unlink + operator-authority slices → refute → prove-before-fix with a kept regression test), **looped to a no-op pass**; re-run the gate after each fix; (d) `python scripts/final_gate.py --check --json` success + `check_convergence.py`; (e) commit (`Agent-Phase: B`). Non-GUI → no Build Verification Loop.

---

## File Scope (owned paths)
- `scripts/generate_capability_index.py` (new), `scripts/audit_capability_docs.py` (new)
- `scripts/kilo-benchmarks/daily_refresh.sh`
- `capabilities.json`, `docs/CAPABILITIES.md`, `llms.txt`, `docs/development/capability-defects.md` (generated artifacts)
- `tests/test_generate_capability_index.py`, `tests/test_audit_capability_docs.py`
- `INDEX.md`, `CHANGELOG.md`, `docs/README.md` (append-only atop `[Unreleased]` / add rows — shared, never reset)
- this plan file.

## Evidence
- **Phase A:** `src/fabrik/cli.py` — `@cli.command(` at `:147`(hidden)/`:247`/`:369` (CLI enumeration surface, read); `src/fabrik/orchestrator/infrastructure.py:90` `_REGISTRAR_ORDER` (10 entries, read); `src/fabrik/scaffold.py:138` `SCAFFOLD_TYPES` (12, incl `wordpress` deploy-only); precedent `scripts/kilo-benchmarks/generate_model_capabilities.py:1-15` (source→MD generator docstring, read).
  ```text
  $ ls -d /opt/fabrik-lib/*/ | wc -l → 62   (− 4 non-module docs/docs-site/node_modules/scripts = 58 modules)
  $ grep -c '@cli.command(' src/fabrik/cli.py → 23   $ ls src/fabrik/drivers/*.py|grep -v __init__|wc -l → 27
  $ find .windsurf/rules -name '*.md'|wc -l → 50   $ ls -d templates/*/|wc -l → 19 (11 scaffold-type + 8 helper)
  ```
- **Phase B:** `scripts/doc_reconcile.py` — `fired_docs()` `:91`, `reconcile_doc()` `:288`, `class ReconcileResult` `:82`, `_quality` `:283` (the reconcile API C2 drives, read); `scripts/kilo-benchmarks/daily_refresh.sh:85` lockfile pattern (read).
- **External:** llms.txt format `https://llmstxt.org/` + agents.md `https://agents.md/` — inherited from the spec (both fetched + re-verified live 2026-07-12, spec §External deps / r4 independent verify).

## Self-audit
- **Grounding passes:** read the enumeration points (cli.py/@cli.command, infrastructure.py:90, scaffold.py:138, templates/, fabrik-lib dirs, .windsurf/rules), the precedent generator, the `doc_reconcile.py` public API, and the daily-pipeline wire-in — all cited in Evidence. The vendor verdict + external facts are inherited from the CONVERGED spec (not re-derived). **`/fabrik-plan-review` Pass 1 (pool `fanout` + native Opus `fabrik-researcher`) caught 4 real defects, all fixed:** (1) MAJOR — `reconcile_doc` is diff-driven + edit-only (no delete), so it can't drive the audit → Phase B rebuilt as a BUILD (corrects the spec's inherited vendor verdict); (2) CLI probe used bare `python` → `sys.executable` + whole-surface-broken guard (Behavior 7); (3) flat `.commands` walk missed ~31 nested subcommands (54 `@*.command(` vs 23 top-level) → recurse subgroups; (4) Behavior 3 `manual` had no detection rule → defined (marker OR no-safe-probe). The `jq` gate → stdlib `python` (no external-tool dependency).
- **Coverage (each "agreed" item → phase):** verified inventory of 7 surfaces → Phase A steps 2; liveness-verify each → Phase A Behavior 1–3; `capabilities.json` + `docs/CAPABILITIES.md` → Phase A steps 2/4; broken/retired/incomplete defect ledger → Phase A Behavior 1–3 + Phase B Behavior 2; doc audit (fix stale, delete dead) → Phase B Behavior 1; daily regeneration → Phase A step 5.
- **Cross-phase signature consistency:** Phase A `Produces` `capabilities.json` (8-key schema) = Phase B `Consumes` (same schema); `build_catalog`/`run` names consistent.
- **Pillars present:** `/fabrik-review` is a literal step (7/c, B-7/c) in **both** phases; pool-default subagents named (Phase A-7/c review finders via `fanout`); the final `/fabrik-docs-review` is Phase B step 6. Not yet a fixed point — `/fabrik-plan-review` converges it.

## Residual unknowns
- **Resolved (self-service, defaults applied):** (1) `capabilities.json` at repo root next to `/llms.txt` (spec residual); (2) in-scope scripts = top-level + the 5 named subdirs minus `.archive/` (spec residual, Phase A step 2); (3) verify depth = `--help`/import/dir-check (no side-effect execution), destructive → `manual` (spec residual, Phase A Behavior 3).
- **Still-open (named resolution):** none blocking. The File Scope is now fully disjoint (Phase B builds `audit_capability_docs.py` and does NOT touch the shared `doc_reconcile.py`, so the earlier serialization point is removed). Two self-service defaults (both settled, no execution stop): the `manual` detection rule (Behavior 3 — explicit `# CATALOG-MANUAL` marker OR no-safe-probe) and the in-scope script set (top-level + 5 named subdirs minus `.archive/`).

## Validation
Final: `python scripts/final_gate.py --check --json` → `{"status":"success"}` + `check_convergence.py` green. Green
proves citations/format, not design soundness — the real proof is the Evidence + the per-phase `/fabrik-review` no-ops.
