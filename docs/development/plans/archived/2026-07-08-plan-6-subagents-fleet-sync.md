# Promote `subagents` from vendor-copy to a Fabrik-synced module

Status: EXECUTED (2026-07-10, lean per operator). Shipped the essence — `VENDORED_DIRS=["libs/subagents"]` in the synced manifest (`iter_synced_pairs` + `gitignore_dest_paths` + the `.fabrik/synced.lock` so `check_synced_unmodified` protects it); a `VENDORED_DIRS` copy+orphan-prune loop in `sync_enforcement_to_projects.py` (distributes to existing projects on every sync); a `libs/subagents` copytree in `scaffold.py` driven by the same `VENDORED_DIRS` constant (new projects, all types); pre-flight re-vendored the hub copy byte-identical to canonical. +3 manifest tests. Reviewed via the pool (2 passes, 4 defects fixed: orphan-prune, scaffold source-of-truth, is_dir guard). The detailed Phase-B docs/guardrail steps below were folded in leanly rather than executed verbatim.
Date: 2026-07-08
Converged: 2026-07-08 (/fabrik-plan-review — 3 passes to an edit-free md5-verified no-op; every path:line re-grounded live, the step-4c verify block + the namespace-package import PROVEN by running them, all residuals forced to RESOLVED/SELF-SERVICE)

Make the vendored `libs/subagents` pool module a **Fabrik-synced** file set (like `.windsurf/rules`,
`scripts/enforcement`, `CLAUDE.md`): one hub source (`/opt/fabrik/libs/subagents`) synced fleet-wide via
`fabrik_synced_manifest.py`, **gitignored + gate-unmodifiable** in every project. This replaces the lossy
per-project re-vendor (a fix reaches a project only when it re-vendors) with automatic fleet-wide
propagation, so the `pick_models` flywheel and the whole `/fabrik-*` command pipeline run on **one** version.

## What we already agreed (from this conversation — RICH, no spec needed)

- **Goal:** `subagents` becomes a synced module, not a per-project vendor copy. (Skip `/fabrik-spec`: no
  external facts, no vendor-ladder call — it's already vendored; the design is settled with the fabrik-lib AI.)
- **Why it fits the synced mold (not the vendor mold):** zero project-specific surface — every project calls
  `run_agents`/`pick_models`/`record_agent_run` **identically**, nothing to adapt. The flywheel compounds only
  on one fleet version; the `/fabrik-*` review pipeline now runs on it → divergent copies are a liability.
- **Chosen approach — re-vendor-once → sync-fleet:** the hub stays the single re-vendor point (pull
  `/opt/fabrik-lib` canonical → `/opt/fabrik/libs/subagents`, flat, as today); the manifest propagates *that*
  to all projects. Inbound `UPSTREAM_FEEDBACK.md` stays (bug reports); outbound fixes go fleet-wide with no
  re-vendor.
- **Rejected:** full `/fabrik-spec` (ceremony — design grounded here); raw direct execution (fleet-wide +
  gitignore + deploy blast radius needs the verify-on-one-project gate); keeping the vendor model (loses the
  fleet flywheel, lets copies diverge). User (verbatim): *"plan or direct execution"* → **lean plan**, and the
  plan MUST *"verify-on-ONE-project before flipping the fleet."*
- **Mode-B deploy risk (grounded, currently absent):** if a project called `run_agents` from **app-runtime**
  code, gitignore + git-sourced `fabrik apply` would drop the module from that container. Fleet grep
  (2026-07-08): **zero** app-runtime callers — only dev/review tooling. Safe today; carry a permanent guardrail.
- **Fleet `.env` (`~/.config/fabrik/subagents.env`) stays user-level** — the sync carries code only; the
  credential never enters the manifest or any project tree.

## Global Constraints (verbatim — every phase inherits)

- **The manifest-change commit AUTO-TRIGGERS a `--force` fleet sync.** `.pre-commit-config.yaml:46` runs
  `sync_enforcement_to_projects.py --force` on every `/opt/fabrik` commit. Therefore **ALL verification
  (unit tests + `--dry-run` + one-project check) happens BEFORE the Phase-A commit** — that commit is what
  ships `libs/subagents` to the fleet, so it is the last step, only after the dry-run proves it safe.
- **Hub is the SOURCE, not a synced target:** `/opt/fabrik/libs/subagents` is committed + tracked; the hub's
  own `.gitignore` does NOT ignore it. Only *projects* gitignore + sync it.
- **Never sync `__pycache__`/`.pyc`** — `iter_synced_pairs` already excludes them (`fabrik_synced_manifest.py:222`); the new dir inherits this.
- **Fabrik-synced files are edited in `/opt/fabrik` only** (they overwrite project copies on sync). Once synced,
  a project's `libs/subagents` copy is gate-unmodifiable (`check_synced_unmodified.py`).
- **Cross-repo HARD STOP:** `/opt/fabrik-lib/subagents/VENDORING.md` (the "how to vendor" doc) is the
  fabrik-lib AI's to update to the sync model — I flag it, I do NOT edit it.
- **Explicit-path commits only** (never `git add -A`); provenance trailers on every AI commit.
- **Gates run from WSL dev** (`python scripts/…`, `pytest`) — never a `fabrik …` shell-out.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `scripts/fabrik_synced_manifest.py` | the single manifest that declares the synced set; a new synced dir is a constant + 2 wiring points | `:66 GOVERNANCE_DIRS`, `:74 ENFORCEMENT_DIR`, `:144 gitignore_dest_paths`, `:161 gitignore_block_text`, `:213 iter_synced_pairs` loop `[*GOVERNANCE_DIRS, ENFORCEMENT_DIR]`, `:222` `__pycache__`/`.pyc` exclusion |
| `scripts/enforcement/check_synced_unmodified.py` | enforcement — compares each project's synced files to the per-project **lock** the sync writes (NOT live HEAD), so a new synced dir auto-enforces once the sync distributes it | `:10` "Compares against `.fabrik/synced.lock`", `:49` reads `SEEDED_NOT_ENFORCED` from the manifest |
| `scripts/sync_enforcement_to_projects.py` | the sync — imports `iter_synced_pairs` + `gitignore_block_text`; supports `--dry-run` (verify without writing) + `--force` | `:14 --dry-run`, `:46-47` imports |
| `.pre-commit-config.yaml` | auto-runs the sync `--force` fleet-wide on every hub commit (why verification precedes the commit) | `:46` `if pwd==/opt/fabrik: sync_enforcement_to_projects.py --force` |
| `libs/subagents/` (the payload — hub-tracked source) | 15 `.py` (`run_agents`/`pick_models`/`record_agent_run` etc.) + `requirements.txt` (`httpx`) — vendor, don't build | `git ls-files libs/subagents/*.py` (tracked); `libs/subagents/requirements.txt` |
| `tests/test_synced_manifest.py` (EXISTS) | the manifest's test file — extend it, don't create | `ls tests/test_synced_manifest.py` |
| `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` | the "What Gets Synced" table the manifest header points at | `fabrik_synced_manifest.py:13` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract + Testing Trophy — a test per user-observable behavior | `select_rules.py` ACTIVE |

No new external API; no new fabrik-lib module (this distributes an already-vendored one). fabrik-lib consult:
`subagents` is the module in question — already vendored; this plan changes only its DISTRIBUTION (vendor→sync).

## Behavior Contract (this plan's own tests — one per distinct behavior)

**Why:** the risk is the manifest change silently syncing the wrong thing fleet-wide (a `__pycache__`, a
non-flat path, or nothing) — a `--force` fleet push amplifies any error to ~35 projects. Each behavior is tested.

- **Given** the manifest with `libs/subagents` added, **When** `iter_synced_pairs(<project_root>)` runs,
  **Then** it yields every `libs/subagents/*.py` + `requirements.txt` mapped **flat** to
  `<project_root>/libs/subagents/*` (same relative path), and yields **no** `__pycache__`/`.pyc` entry.
- **Given** the manifest, **When** `gitignore_block_text()` runs, **Then** the output contains `libs/subagents/`.
- **Given** the manifest, **When** `sync_enforcement_to_projects.py --dry-run` runs, **Then** it reports
  `libs/subagents/*.py` as would-copy for a project and reports zero `__pycache__` entries (integration proof).
- **Mocked:** none — real manifest functions + a real `--dry-run` against a real (throwaway) project dir.

---

## Pre-flight — re-vendor the canonical stall-fix into the hub copy FIRST (BLOCKING, before Phase A)

> Added 2026-07-08 post-convergence, per the fabrik-lib AI's ask (the manifest design is unchanged — this is a
> guard on WHAT gets synced, not a re-review of the wiring). The Phase-A design remains CONVERGED.

**Why (grounded):** Phase A makes `/opt/fabrik/libs/subagents` the **single fleet source** — whatever bytes it
holds are `--force`-pushed to ~35 projects on the Phase-A commit (`.pre-commit-config.yaml:46`). If the hub copy
predates fabrik-lib's **stall-fix** — the `max_price` cap on model selection + content-stall runs excluded from
retry + `quality_score` set `NULL` on a stalled run — then the fleet inherits the provider **stall fleet-wide**.
The pre-vendor MUST land in the hub copy and be proven byte-identical to canonical BEFORE Phase A's manifest
change, or the sync amplifies a stale module to every project.

**Steps (self-service — a hub re-vendor, NOT a cross-repo write): read `/opt/fabrik-lib`, write only the hub's
`/opt/fabrik/libs/subagents` copy (the standard, allowed re-vendor point); never edit `/opt/fabrik-lib`.**
1. **Detect drift (read-only):** `diff -rq /opt/fabrik/libs/subagents <canonical-subagents-dir>` — resolve
   `<canonical-subagents-dir>` from `/opt/fabrik-lib/subagents/VENDORING.md` (the vendoring doc this plan
   already cites at Global Constraints). If **identical** → the stall-fix is already vendored; record the diff
   output as evidence and skip to Phase A. If it **differs** → step 2.
2. **Re-vendor:** copy the canonical `.py` files (flat, as today) into `/opt/fabrik/libs/subagents/` per
   `VENDORING.md`. Editing the **hub source** is allowed; this is the re-vendor point, not a fabrik-lib edit.
3. **Confirm the three stall-fix behaviors are present** in the re-vendored hub copy (grep the module):
   a `max_price`/max-cost cap in the selection path; the content-stall run **excluded from retry**; and
   `quality_score` written as `NULL`/`None` on a stalled run. All three present, or the vendor is incomplete.
4. **Prove byte-identical to canonical:** `diff -rq /opt/fabrik/libs/subagents <canonical-subagents-dir>` →
   **zero differences** (record the verbatim output as evidence).
5. **Prove the re-vendor didn't break the module:** `.venv/bin/python -m pytest tests/ -k subagent -q` → green.

**BLOCKING:** do not begin Phase A until step 4 shows zero diff and step 5 is green. Syncing a stale copy
fleet-wide is the exact failure this pre-flight exists to prevent.

---

## Phase A — Add `libs/subagents` to the sync manifest (+ full pre-commit verification)

**Files:** `scripts/fabrik_synced_manifest.py`, `tests/test_synced_manifest.py`.
**Responsibility:** declare `libs/subagents` a synced dir; **prove** (unit + dry-run + one-project) it syncs
flat and pycache-free BEFORE the commit that fleet-pushes it.

**Interfaces — Produces:** `VENDORED_DIRS = ["libs/subagents"]`; `iter_synced_pairs` yields the pairs;
`gitignore_dest_paths` gains a "Vendored fabrik-lib modules" group with `libs/subagents/`.

**Steps (highest-risk test FIRST):**
1. **Write the failing tests** in `tests/test_synced_manifest.py`: (a) `iter_synced_pairs(tmp_project)` includes
   `(<fabrik>/libs/subagents/agent.py, <tmp_project>/libs/subagents/agent.py)` and `requirements.txt`, and
   includes **no** path with `__pycache__` or suffix `.pyc`; (b) `gitignore_block_text()` contains
   `"libs/subagents/"`. **Run red** (`pytest tests/test_synced_manifest.py -q` → fail).
2. Edit `fabrik_synced_manifest.py`: add `VENDORED_DIRS = ["libs/subagents"]` near the other dir constants
   (after `ENFORCEMENT_DIR`, `:74`); wire into `iter_synced_pairs` (`:213` → `for rel_dir in [*GOVERNANCE_DIRS, ENFORCEMENT_DIR, *VENDORED_DIRS]:`)
   and `gitignore_dest_paths` (`:144` return dict → add `"Vendored fabrik-lib modules (synced fleet-wide)": [f"{d}/" for d in VENDORED_DIRS]`).
3. **Run tests green.**
4. **VERIFY BEFORE THE FLEET-SYNCING COMMIT** (this commit triggers `--force` fleet sync — prove safe first):
   - `python -c "from scripts.fabrik_synced_manifest import iter_synced_pairs, gitignore_block_text; from pathlib import Path; ps=list(iter_synced_pairs(Path('/tmp/xp'))); assert any('libs/subagents/agent.py' in str(d) for _s,d in ps); assert not any('__pycache__' in str(s) for s,_d in ps); assert 'libs/subagents/' in gitignore_block_text(); print('manifest OK')"` → `manifest OK`.
   - **Dry-run the fleet sync:** `python scripts/sync_enforcement_to_projects.py --dry-run 2>&1 | grep -c "libs/subagents"` → `≥1` (the payload appears in the would-copy set; step-1's unit test already proves all 15 files map flat); `python scripts/sync_enforcement_to_projects.py --dry-run 2>&1 | grep "libs/subagents" | grep -c "__pycache__"` → `0`.
   - **One-project verify (throwaway install path — proves the FLAT layout works anywhere):**
     ```bash
     T=$(mktemp -d)
     python - "$T" <<'PY'
     import shutil, sys; from pathlib import Path
     from scripts.fabrik_synced_manifest import iter_synced_pairs
     T = Path(sys.argv[1])
     for src, dest in iter_synced_pairs(T):
         if "libs/subagents" in str(dest):
             dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
     assert (T / "libs/subagents/agent.py").is_file(), "flat copy failed"
     print("copied flat OK")
     PY
     ( cd "$T" && python -c "from libs.subagents import run_agents, pick_models, record_agent_run; print('import from synced copy OK')" )
     rm -rf "$T"
     ```
     Expected: `copied flat OK` then `import from synced copy OK`. **The import test MUST run from `$T`
     (`cd "$T"`), NOT `PYTHONPATH=$T` from `/opt/fabrik` — the latter false-positives by importing the hub's
     own `libs/subagents` via CWD instead of the synced copy.**
5. Doc-sync: `CHANGELOG.md`.
6. **Gate:** `pytest tests/test_synced_manifest.py -q` green; `python scripts/final_gate.py --check --json` → `"status":"success"`.

**Phase A closing sequence:** (1) gates green + step-4 verification all pass; (2) `python scripts/enforcement/check_doc_sync.py` + CHANGELOG;
(3) **`/fabrik-review`** on the manifest + tests diff (pool-default finders per `62` § Dispatch policy;
`record_agent_run` each) → loop to a no-op; (4) commit `scripts/fabrik_synced_manifest.py` +
`tests/test_synced_manifest.py` + `CHANGELOG.md` (explicit paths, provenance). **This commit's pre-commit hook
performs the intended `--force` fleet sync of `libs/subagents` — step-4 already proved it correct.** Confirm
post-commit: `git -C /opt/<a-project> status` shows `libs/subagents/` present + gitignored (spot-check one project).

---

## Phase B — Vendor→sync docs + `httpx` dev-dep note + the mode-B deploy guardrail

**Files:** `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`, `AGENTS.md` (guardrail note), `INDEX.md`,
`CHANGELOG.md`. **Cross-repo (flag only):** `/opt/fabrik-lib/subagents/VENDORING.md`.
**Responsibility:** document the new distribution model + bake in the permanent mode-B guardrail so a future
app-runtime user of `run_agents` doesn't silently ship a broken container.

**Interfaces — Consumes:** Phase A's synced-manifest change (the "What Gets Synced" surface).

**Steps:**
1. `SYNC_ENFORCEMENT_WORKFLOW.md` "What Gets Synced" table: add a row — `libs/subagents/` → *"vendored
   fabrik-lib pool module; synced fleet-wide, gitignored + gate-unmodifiable in projects; hub is the single
   re-vendor point."*
2. **Mode-B guardrail** (a subsection in `SYNC_ENFORCEMENT_WORKFLOW.md`, cross-referenced from `AGENTS.md`
   where the pool is described): *"`libs/subagents` is dev/review tooling (mode A) — gitignored, not in the
   deploy image. A project that calls `run_agents` from **app-runtime** code (mode B) MUST vendor-not-sync it
   or add it to the deploy artifact — git-sourced `fabrik apply` excludes gitignored files. Re-grep the fleet
   (`grep -rl 'run_agents(' /opt/*/src /opt/*/app`) before any change to the fleet gitignore. Baseline
   2026-07-08: 0 app-runtime callers."*
3. **`httpx` dev-dep note** (in `SYNC_ENFORCEMENT_WORKFLOW.md` + the scaffolded project QUICKSTART pointer):
   *"the pool's one runtime dep is `httpx` — a project running the `/fabrik-*` pool tooling installs it via
   `pip install -r libs/subagents/requirements.txt` (dev/CI only)."*
4. **Behavior Contract:** **Given** the docs, **When** a reader checks "What Gets Synced", **Then**
   `libs/subagents` is listed; **Given** a project considering app-runtime `run_agents`, **When** it reads the
   guardrail, **Then** the deploy-image requirement is explicit. (Doc behaviors — verified by grep in the gate,
   no unit test.)
5. Doc-sync: `INDEX.md`, `CHANGELOG.md`. **Cross-repo flag (not an edit):** append a note to
   `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` requesting the fabrik-lib AI update `VENDORING.md` § "Keeping
   the copy current" from re-vendor to the synced model (this is the one sanctioned cross-repo write).
6. **Gate:** `grep -c "libs/subagents" docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` → `≥1`;
   `python scripts/final_gate.py --check --json` → success.

**Phase B closing sequence:** (1) gate green; (2) `check_doc_sync.py` + INDEX + CHANGELOG; (3)
**`/fabrik-review`** on the docs diff → no-op; (4) commit `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` +
`AGENTS.md` + `INDEX.md` + `CHANGELOG.md` (explicit paths).

## Final phase gate (after B)

- `python scripts/final_gate.py --json` → `"status":"success"`; `python scripts/enforcement/check_convergence.py` → pass.
- **`/fabrik-docs-review`** — converge the sync/vendoring docs to the new reality to a no-op.

## File Scope (owned paths)

- `scripts/fabrik_synced_manifest.py`
- `tests/test_synced_manifest.py`
- `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`
- `AGENTS.md`, `INDEX.md`, `CHANGELOG.md`
- **cross-repo (append-only flag, not owned):** `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md`
- **NOT edited (hub is source, projects are targets):** `libs/subagents/**` (unchanged — this plan distributes
  the existing copy), every project's `libs/subagents/**` (written by the sync, never by this plan)

## Evidence

- **Manifest wiring** — a synced dir is one constant + two call-sites: `fabrik_synced_manifest.py:213`
  (`for rel_dir in [*GOVERNANCE_DIRS, ENFORCEMENT_DIR]`) + `:144` (`gitignore_dest_paths` return dict); pycache
  already excluded at `:222`. gitignore auto-flows via `gitignore_block_text` (`:161→:179` iterates
  `gitignore_dest_paths`).
- **Enforcement auto-flows** — `check_synced_unmodified.py:10` compares to the per-project lock the sync
  writes; no edit needed there.
- **Sync + auto-fleet-push** — `sync_enforcement_to_projects.py:14` `--dry-run` (the safe verify);
  `.pre-commit-config.yaml:46` runs it `--force` on every hub commit (why verify precedes commit).
- **Mode-B baseline** — fleet grep 2026-07-08: `grep -rln "run_agents(" /opt/*/src /opt/*/app` → **0** spoke
  app-runtime callers (only `/opt/fabrik` hub driver + doc/workflow files). Sync+gitignore safe today.
- **Payload tracked** — `git ls-files libs/subagents/*.py` → 15 files; `libs/subagents/requirements.txt` present.
- **Sync `libs/subagents/` ONLY — not `libs/__init__.py` (namespace package, PROVEN):** `libs/__init__.py`
  exists + is tracked at the hub, but `from libs.subagents import …` works WITHOUT it — `libs/` resolves as a
  Python-3 implicit namespace package. Verified: `cp libs/subagents/*.py $T/libs/subagents/` (no
  `libs/__init__.py`), `cd $T && python -c "from libs.subagents import run_agents, pick_models, record_agent_run"`
  → OK. So `VENDORED_DIRS=["libs/subagents"]` (which rglobs only that dir, never the parent `libs/__init__.py`)
  is correct + sufficient — and NOT syncing `libs/__init__.py` avoids clobbering a project's own `libs/` package.

## Self-audit

- Coverage: "synced module" → Phase A (manifest + verify); "verify-on-one-project before fleet" → Phase A
  step 4c (throwaway-project import check) + post-commit spot-check; "mode-B guardrail" → Phase B step 2;
  "httpx" → Phase B step 3; "vendor→sync model doc" → Phase B step 1 + the cross-repo VENDORING.md flag.
- Cross-phase signatures: `VENDORED_DIRS` (A.Produces) is internal to the manifest; Phase B consumes only the
  synced-surface fact (docs). No shared symbol to drift.
- Grounding: every `path:line` above read live this session.

## Residual unknowns

- **[RESOLVED — grounded]** mode-B deploy risk: 0 fleet app-runtime callers (grep 2026-07-08) → sync+gitignore
  safe now; the guardrail (Phase B) keeps it safe.
- **[SELF-SERVICE — Phase B step 5, non-blocking]** the executor appends the flag to
  `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` (a concrete, non-stalling action) requesting the fabrik-lib AI
  update `VENDORING.md` § "Keeping the copy current" (re-vendor → synced). The fabrik-lib AI's actual
  `VENDORING.md` edit is their async follow-up in their own repo — it does **not** block this plan's completion,
  and the executor never waits on it.
- **[RESOLVED — decided]** `httpx` is surfaced via the doc note (Phase B step 3) — the chosen approach for
  mode-A dev/CI usage. Auto-installing it into a scaffolded project's dev-requirements is an **out-of-scope**
  future scaffolder enhancement (revisit only if a project ever automates the pool in CI); not needed now.
- **[RESOLVED — decided]** `libs/subagents/` carries **no** `README.md` — the package is self-documenting
  (module docstrings) and the canonical README lives one level up (`/opt/fabrik-lib/subagents/README.md`,
  outside the package). Not load-bearing; the sync ships whatever is in the dir. (A 3-line pointer README is a
  trivial future add, never an execution-time decision.)
