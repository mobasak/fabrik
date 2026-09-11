# Final Gate Workflow

**Last Updated:** 2026-09-11
**Script:** `scripts/final_gate.py`

> Complete reference for `scripts/final_gate.py` — deterministic quality checks that validate code and documentation before Traycer commit.

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Commands Reference](#commands-reference)
4. [Execution Phases](#execution-phases)
5. [All Checks Reference](#all-checks-reference)
6. [Configuration](#configuration)
7. [Exit Codes](#exit-codes)
8. [Integration Examples](#integration-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

`final_gate.py` provides **deterministic quality checks** that catch formatting, syntax, and convention errors before expensive LLM review. It validates both code quality and documentation completeness.

**Change-set scope (shared-tree invariant, 2026-07-18):** the gate scopes fixers + static checks to *what
this session will push* — committed-but-unpushed + staged + unstaged modifications to tracked files.
**Untracked-unstaged files are excluded**: they cannot be pushed, and on a shared tree they are typically a
sibling agent's in-progress work (which the gate must neither red-flag against your session nor auto-fix /
auto-stage). Authorship = staging: `git add` your new file to bring it into gate scope. The lint-ratchet
(`check_lint_ratchet.py`) applies the same rule — its repo-wide count includes **tracked files only**, which
is also true CI-parity (CI's clean checkout has no untracked files).

### Key Features

1. **Auto-fix formatting** — Repairs whitespace, EOF newlines, Python formatting
2. **Static analysis** — Runs ruff, mypy, bandit, semgrep, yaml/json validation
3. **Repo consistency** — Validates Fabrik conventions, structure, and documentation
4. **Iterative convergence** — Re-runs up to 3 times when files change
5. **Best-effort tools** — Skips optional tools if not installed

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Final Gate System                           │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: AUTO-FIX     │  PHASE 2: STATIC      │  PHASE 3: REPO │
│  ├── whitespace        │  ├── ruff             │  ├── structure │
│  ├── EOF newlines      │  ├── mypy             │  ├── conventions│
│  ├── ruff format       │  ├── bandit           │  ├── doc sync  │
│  └── ruff --fix        │  ├── semgrep          │  └── symlinks  │
│                        │  ├── yaml/json        │                │
│                        │  ├── sqlfluff         │                │
│                        │  └── vulture          │                │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Use

| Context | Command | Purpose |
|---------|---------|---------|
| **Agent self-review (Tier 1)** | `python scripts/final_gate.py --lean` | Fast showstoppers only (syntax, secrets, schema sync) |
| **Phase handover (Tier 2)** | `python scripts/final_gate.py` | Full quality gate before Traycer commit |
| **Systemic maintenance (Tier 3)** | `python scripts/final_gate.py --systemic` | Repo health only (docker, ports, deps, docs sprawl, env contract, watchdog, health) |
| **CI read-only** | `python scripts/final_gate.py --check` | Read-only verification (no fixes, tier selected by flags) |

**Note:** Default mode auto-stages changes if all checks pass. Use `--no-stage` to disable.

---

## Commands Reference

### Basic Commands

```bash
# Tier 1 (LEAN): Showstoppers only (syntax, secrets, schema sync)
python scripts/final_gate.py --lean

# Tier 2 (FULL - default): Full quality gate
python scripts/final_gate.py

# Tier 3 (SYSTEMIC): Repo health only (no showstoppers)
python scripts/final_gate.py --systemic

# Check-only mode (CI - no fixes, respects tier flags)
python scripts/final_gate.py --check

# Don't auto-stage modified files
python scripts/final_gate.py --no-stage

# Log issues for post-Kilo analysis
python scripts/final_gate.py --post-kilo
```

### AI Fix Agent (Experimental)

```bash
# Enable AI-assisted fixes for mypy/ruff errors
FINAL_GATE_AI_FIX=1 python scripts/final_gate.py
```

---

## Execution Phases

### Phase 1: Auto-Fix Formatting

**Runs in:** Fix mode for Tier 1 and Tier 2 (skipped for Tier 3 and in `--check` mode)
**Skipped in:** `--check` mode

| Check | Action | Files Affected |
|-------|--------|----------------|
| **Trailing whitespace** | Strip trailing spaces | `*.py`, `*.md`, `*.yaml`, `*.yml`, `*.json`, `*.sh` |
| **EOF newlines** | Ensure files end with newline | Same as above |
| **ruff format** | Auto-format Python code | `src/`, `scripts/` |
| **ruff --fix** | Auto-fix lint issues | `src/`, `scripts/` |

### Phase 2: Static Analysis

**Runs in:** All modes for Tier 1 and Tier 2 (skipped for Tier 3)

| Check | Tool | Timeout | Required |
|-------|------|---------|----------|
| **ruff** | Lint check (no fix) | 120s | ✅ Yes |
| **mypy** | Type checking | 300s | ✅ Yes |
| **bandit** | Security scanner | 180s | ⚠️ Best-effort |
| **semgrep** | SAST rules | 30s | ⚠️ Best-effort |
| **yaml** | YAML syntax | — | ✅ Yes |
| **json** | JSON syntax | — | ✅ Yes |
| **sqlfluff** | SQL lint (PostgreSQL dialect) | 180s | ⚠️ If SQL files exist |
| **vulture** | Dead code | — | ⚠️ Best-effort |

**Best-effort checks:** Skip if tool not installed, don't fail build.

### Phase 3: Repo Consistency

**Runs in:** All tiers (1, 2, 3) and modes (except `--sync`), with tier-specific check sets:

- **Tier 1 (`--lean`)**: Showstoppers only (secrets, env vars, schema sync).
- **Tier 2 (default)**: Full consistency suite (structure, docs, changelog, schema, ports, docker, etc.).
- **Tier 3 (`--systemic`)**: Systemic repo health only (docker, ports, env contract, deps, docs completeness/drift, doc sprawl, watchdog, health, duplicates).

### Tier Matrix

| Tier | Flag | Primary Use |
|------|------|-------------|
| 1 | `--lean` | Agent self-review loop (fast showstoppers) |
| 2 | *(default)* | Phase handover / pre-commit quality gate |
| 3 | `--systemic` | On-demand repo/system hygiene |

### Tier 1 (LEAN) - `--lean` - Agent Self-Review

**Purpose:** Fast showstoppers only (syntax, secrets, schema sync, doc sync)

**Phase 3: Repo Consistency (34 checks)** — the results list of `run_consistency_checks(tier=1, changed_files=set())`, instrumented 2026-09-11 (stub `run_optional_check` and `run_cmd`, count the rows; at tier 1 the call count is the same 34); fourteen run unconditionally outside the `if tier in (1, 2):` block — among them `check_convergence.py`, `check_review_coverage.py`, `check_review_hygiene.py` and `check_plan_lock_release.py`. **The 20 CHECK ROWS bulleted below carry the Tier-1 notes (a 21st bullet, the flip-gate invocation matrix, documents a command-side gate battery, not a `run_consistency_checks` row); four of them (Convergence Evidence, Coverage Checklist, Plan-lock release, Review hygiene) are unconditional rows also bulleted under Tier 3, where the remaining ten are named.** Four Tier-1/2-only rows carry no note here and are listed only under § Enforcement Scripts: Frozen Chain (`check_frozen_chain.py`), Decision Ledger (`check_decisions_unique.py`), Doc-Script Links and Doc-Script Coverage (`render_doc_script_links.py`)
- **Convergence Evidence (plans + reviews)** - `check_convergence.py` — runs every tier, unconditionally; the CLOSING-ROW rule (D-206, 2026-09-09; landed by the review-family adoption plan on 2026-09-10): once a NON-ARCHIVED plan-set spine carries any `| Pass …` / `| Round …` table row with a `confirmed:` counter — anywhere in the file, no `## Pass Ledger` heading required — a CONVERGED or EXECUTED flip whose LAST such row does not read `confirmed: 0` is refused (`_check_spine_set` is reached from both claim paths; an `archived/` spine returns unchecked; `_PASS_ROW` — indented rows included, blockquoted excluded; fences stripped, code spans masked, HTML comments blanked, in that order; the row's last `confirmed:` token counts; `_closing_row_fail` is the single function the flip check calls and the one any fleet census must call — the census here is an ad-hoc measurement through that import, not a committed caller) — measured 2026-09-11 through that function over the 1,061 readable plan files under `/opt/*/docs/development/plans` in the 43 main checkouts (the registered worktrees excluded via `git worktree list`, not by path name — `/opt/fabrik-lib-account` is one and carries a byte-identical copy; 1,062 on disk, 1 a dangling symlink): 71 contain the substring `## Pass Ledger` (77 case-insensitively), 21 of them plan-set spines — 10 of those under `archived/`, which the rule never grades, leaving 11 (the heading is incidental: the GRADED population is every non-archived spine — 19 live of 47 fleet-wide, 28 archived) — 1 of the 1,061 carries a counter row (`2026-09-10-plan-1-review-family-adoption.md`, a bare dated plan that is NOT a plan-set spine, so the rule never reaches it) and 0 of the 19 live spines do, hence 0 refusals; separately, the last-token design's own cost is 0 of 47 spines and 0 of 805 fleet receipts carrying more than one `confirmed:` token on one Pass row when read through the rule's own masking (`check_convergence.py`'s `_PASS_ROW` comment states the convention)
- **Coverage Checklist (reviews)** - `check_review_coverage.py` — runs every tier, unconditionally
- **Plan-lock release** - `check_plan_lock_release.py` — runs every tier, unconditionally (advisory `warn_only=True`): reports a `.fabrik/plan-locks/<id>.json` left NON-TERMINAL (`active`/`paused`/`blocked`) after its plan finished. Every-tier ON PURPOSE — `--lean` is the mode agents run while a lock is live. Doc: [plan-lock-lifecycle.md](../reference/plan-lock-lifecycle.md)
- **Review hygiene (advisory)** - `check_review_hygiene.py` — runs every tier, unconditionally (advisory `warn_only=True`, no failing exit path): the grep-shaped classes a review round otherwise re-sweeps by hand — fragment residue (`template-residue`: the renderer's own shapes only, `{{include:<name>}}` or `{{UPPER_CASE}}` anchored at both braces — a Go template such as `{{.Image}}` is not residue), CommonMark fence parity, a table row whose cells do not line up with its header (`raw-pipe` on a receipt; `table-parity` on ANY `.md` surface — a spec, a plan, a rendered command — through one shared helper, fenced and commented lines blanked first), and a disposition cell carrying two or more bare verdict words (five of the script's eight classes — `changelog-entry`, `dead-symbol` and `stale-phrase` are the other three: the last two answer `--symbol` / `--phrase`, and `changelog-entry` runs `check_changelog.py`'s own quality rule whenever a `CHANGELOG.md` is on the surface). Registered with NO arguments on purpose: it self-selects the CHANGED receipts under `docs/development/reviews/` from `git status` and prints nothing when none changed, so it is inert on every unrelated commit. The orchestrator invokes it directly at each round's start and close (`--surface` · `--receipt` · `--phrase` · `--symbol` · `--json`). Fire rate over the 275 committed hub receipts at `8092e8a8` — the numbers are TRANSCRIBED from `tests/enforcement/test_check_review_hygiene.py::test_the_fire_rate_over_the_committed_receipt_corpus`'s printed output, which pins them, never typed by hand: raw-pipe 35 hits in 21 receipts (0.584 % of 5,992 table data rows), dual-verdict 27 hits in 5 receipts (1.624 % of 1,663 disposition-bearing rows) — re-pinned 2026-09-10 after the comment blanking learned to read code spans (a cell quoting `<!-- POOL OFF` had blanked every later row of 9 of the 805 fleet receipts (measured 2026-09-10; the population was 805 again on 2026-09-11, when the same-shaped probe found 11 receipts quoting the marker)); 4,296 rows (71.7 %) were graded by NO disposition class — which is not the same as carrying no verdict; a row with three verdict words in a header-less table lands here: a row in a table with no header pair is graded by neither class, and a row in a headed table that declares no disposition column (the header cell must be that one word, case-insensitively, bold tolerated — `Disposition (round)` is not recognised) is cell-count-checked by `raw-pipe` and never dual-verdict-graded — counted as ungraded when its cells line up, and reported as a `raw-pipe` hit when they do not (such a hit row is in neither bucket — 33 of the 35 raw-pipe hits, exactly the gap between 4,296 + 1,663 and the 5,992 denominator; the other 2 hits sit in disposition-declaring tables and are counted in the 1,663); never read as clean; every run that prints a summary states that bound (`--json` carries it as `ungraded_rows`; the no-argument gate run prints nothing at all when no receipt changed). Advisory until infra measures its false-positive rate below 5 % over 20 receipts, counted from the receipts' own `RECORDED — hygiene false positive (…)` rows.
- **The flip-gate invocation matrix** — the gates a `term-edit` review loop (`/fabrik-spec-review`, `/fabrik-plan-review` and the eleven other consumers of `commands/_fragments/term-edit.md`) runs on the artifact at pass 1 and again at the close (review-family adoption, 2026-09-10). A gate run COUNTS only when the runner can show the artifact was in the gate's examined set — four invocation shapes were measured to return green over NOTHING that day. The rows below are `tests/enforcement/test_flip_gate_matrix.py::MATRIX`, each pinned by a test that plants a fixture and asserts the gate's own examined marker names it (the watched-fail half is one mutant per row on a scratch copy of the gate, kept in the plan's receipt); one row per gate: invocation · tree · the examined marker · the fail-open shape it avoids.
  - `check_spec_convergence.py --root <scratch>` · a scratch root with the FLIPPED spec copy under `docs/superpowers/specs/` · marker `1 CONVERGED spec(s) examined` · avoids: an empty or mis-rooted scratch prints nothing and exits 0.
  - `check_rule_grounding.py --root <scratch>` · a scratch root with `scripts/` and `.windsurf/` linked in and the FLIPPED plan copy (dated on or after the floor cutoff) carrying a `## Constraints digest` · marker `1 CONVERGED in-window plan(s) examined` · avoids: a plan dated before the cutoff, or a root without the rubric script, examines nothing and exits 0.
  - `check_plan_tickets.py --plan-dir <set> --project-root <scratch>` · the set under `docs/development/plans/<YYYY-MM-DD-plan-slug>/` (a scratch copy elsewhere needs `--allow-external`) · marker `graded N ticket(s)` · avoids: a non-dated directory is REFUSED — `✗ … is not a dated plan directory`, exit 1 — so a green over such a dir is impossible, and the test asserts the marker AND the exit code.
  - `check_convergence.py --project-root <scratch>` · a scratch GIT root where the FLIPPED spine is TRACKED-AND-UNCOMMITTED (`git add -N`); the target list is `_converged_targets(root)` — it reads `git status --porcelain` and skips `??` · marker: the spine path in that list, then the gate's refusal text when its Evidence is removed · avoids: a committed-clean copy (settled at HEAD) and an untracked copy are both invisible, and the gate prints nothing and exits 0.
  - `check_plan_quality.py` · no CLI — reached through `python -m scripts.enforcement.validate_conventions --strict --git-diff` from the REAL tree; `PLAN_DIR` is bound to the cwd at import (a pin-time probe goes through `check_file()` with BOTH `PLAN_DIR` bindings patched to the flipped copy's directory — the matrix row's own method — and writes nothing into the real plans dir), the fixture inside it is FLIPPED (the gate reads Status — a DRAFT grades to WARN, a CONVERGED to ERROR) and `check_file()` returns `[]` for any path outside it (`check_plans.py` binds its OWN cwd-bound `PLAN_DIR` for the naming pre-check `check_file()` runs first — a scratch reproduction patches both, or the pre-check silently reads every scratch path as validly named) · marker: `check_file()` returns the missing-section finding for a plan inside `PLAN_DIR` · avoids: a fixture in a scratch root is silently out of scope; a DRAFT's WARN is `--strict`-exempt (advisory) while a CONVERGED's ERROR fails `validate_conventions`.
  - Not a flip gate: `check_citations_resolve.py --changed` runs at EVERY pin in the REAL tree (at a scratch root every repo path is missing and it ticks green over 0 examined anchors — the `--pin <dir>` root is a backlog EXTEND).
- **Secrets (Zero Hardcoding)** - `check_secrets.py`
  - Scans for hardcoded secrets (API keys, passwords, tokens)
- **Hardcoded localhost/127.0.0.1 Ban** - `check_env_vars.py`
  - Blocks a hardcoded `localhost` / `127.0.0.1` host or DSN outside a sanctioned env-var default
  - Renamed 2026-08-16: it shared the display name ".env Updates (Secrets)" with `check_env_updates.py`, which could not fail at all (now unwired — see § Advisory rows)
- **Imports Resolvable (clean checkout)** - `check_imports_resolvable.py` *(advisory)*
  - Catches shipped code importing a module not in the repo (gitignored/never `git add`ed) — green locally, `ModuleNotFoundError` in CI/deploy
  - **Three verdicts, not two.** `ERROR_AREAS` is `src`/`app`/`tests`; `WARN_AREAS` is `scripts`. A repo with a **library layout** (modules at `<name>/<pkg>/`, none of the three dirs) prints `NOT APPLICABLE: none of src/app/tests exist … NOT reporting a clean result` and exits 0 — it is not a defect, but it is not a pass either. Measured 2026-08-23: **7 of the 49 repos carrying this check** have none of the three, and the old output claimed `no phantom imports in src/app/tests — N imports checked` with a denominator built entirely from `scripts/`. The `OK:` line now names only the areas actually walked. `WARN_AREAS` are unaffected — a `scripts/` phantom still surfaces under NOT APPLICABLE.
- **Lint Ratchet (repo-wide, no new debt)** - `check_lint_ratchet.py` *(advisory)* — repo-wide ruff count may only go down
- **Schema Sync (DB Models)** - `check_schema_sync.py` *(advisory)*
  - Only runs if .py or .sql files changed
- **Doc Sync Matrix** - `check_doc_sync.py`
  - The single "update docs when code changes" gate — consolidates what `check_changelog.py` / `check_index_md.py` / `check_configuration_md.py` / `check_openapi_sync.py` used to check (those scripts still exist on disk with no gate row of their own — `check_changelog.py` is still imported by `check_review_hygiene.py`; the rest have no caller — see § All Checks Reference)
- **Subagent Flywheel (pool-or-declare — BLOCKING; STANDS DOWN under D-181)** - `check_subagent_flywheel.py` — the pool is OFF by ruling (D-181/D-182, 2026-09-07 — the committed constant `_POOL_POLICY_ON = False` in the script; `FABRIK_POOL_POLICY=on|off` is the test seam): Layer 1 never blocks and no `NO-POOL:` is owed, Layer 2 prints one line. With the constant flipped back on it fails the gate when a substantial code change ran zero pool subagent runs and carries no `NO-POOL:` declaration
- **Mutation (opt-in FABRIK_MUTMUT)** - `check_mutation.py` *(ADVISORY row)* — through the gate it ALWAYS prints the pointer and exits 0: `final_gate.py` deliberately strips `FABRIK_MUTMUT` for this one child (a set flag would start a session-detached mutmut the gate's 120s timeout then orphans). A real mutation run happens only by DIRECT invocation (`FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py`) or the Sunday 05:00 cron
- **Doc stub fill** - `check_doc_stubs.py` *(ADVISORY row)*
- **Script Coupling Header** - `check_script_headers.py` *(ADVISORY row)*
  - Each staged `scripts/**/*.py` declares, via a `# AFTER-EDIT:` header, the files to update when it changes (or `none`)
  - WARN-tier, touch-on-change (mirrors Doc Sync): warns on a missing header, or when a listed coupled file wasn't also staged; never blocks
  - Before 2026-08-16 it was registered with neither `advisory` nor `warn_only`, so `run_optional_check` discarded its stdout on exit 0 — the warnings it exists to emit reached nobody
- **Print/Console.log Ban** - `check_print_ban.py`
  - Bans `print()` in `.py` and `console.log()` in `.ts`/`.tsx`/`.js`/`.jsx` production code
- **No Host Ports on Traefik Services** - `check_no_host_ports.py`
- **Full Traefik Label Set (§7)** - `check_traefik_labels.py`
- **Spec <-> Project DB Name Match (Phase 1c)** - `check_spec_db_match.py`
- **Undeclared Imports (requirements.txt)** - `check_undeclared_imports.py`
- **Fabrik-Synced Files Unmodified** - `check_synced_unmodified.py`

**Phase 2: Static Analysis** — Tier 1 also runs `ruff` (only if changed `.py` files), `check json`, `check yaml`; mypy/bandit/semgrep/sqlfluff/vulture are Tier-2-only (`final_gate.py:561-562`).

### Tier 2 (FULL) - Default - Phase Handover

**Purpose:** Full quality gate before Traycer commit

**Pytest (CI parity)** — Tier 2 runs `pytest tests/ -x -q` (900s cap, blocking) **only when the repo's
own `.github/workflows/*` run pytest — OR the repo carries `.fabrik/run-pytest`**. ⚠️ The marker exists because the workflow-scan signal INVERTS during a CI cutover: deleting the workflows disarms local pytest instead of relocating it (measured 2026-08-29: 10 repos ran pytest locally for no reason other than that workflow text). A repo retiring its workflows MUST touch the marker. Rationale: the gate must be equivalent to what CI will reject —
an agent must not reach `status:success` and still push test-failing code (happened live on
trading-intelligence 2026-07-24). A repo whose CI doesn't run pytest is skipped (no CI red to prevent;
fabrik's own ~2,500-test suite takes ~3h — never run it inside a completion gate). Graceful skips:
no `tests/` dir, pytest not installed, no src/tests/scripts changes, or exit 5 (nothing collected).

**Phase 3: Repo Consistency** — inherits all **34** Tier-1 checks above (fourteen run unconditionally outside the `tier in (1, 2)` block — the earlier "TWO unconditional" was twelve short by 2026-09-11, every count here is by instrumented execution, never by eyeballing the call sites), **plus 18 Tier-2-only checks** — 14 with notes below plus the hub-conditional `epic_order --check` bullet the "19 where …" clause counts; four more run with no note: User-Level Hooks Registered (`scripts/sysadmin/install_user_hooks.py`), Rule-pack reachability (`check_pack_reachability.py`), Command Corpus [BLOCKING] (`check_command_corpus.py`), Ticket Breadth (`check_ticket_breadth.py`) — (the `if tier == 2:` block — incl. the 3 docs-truth durability gates: Doc Link Integrity, INDEX↔tree drift, Retired-Tech Tripwire [ADVISORY row] — plus the Plan-Set Contract, Hooks Index Fresh, Sync Trigger Coverage, and Phase Tests [ADVISORY row, plan-window]; 19 where `scripts/epic_order.py` exists — the hub-conditional `epic_order --check` row below), **plus the Kilo CLI Health Check** (shared with Tier 3, `tier >= 2`) — **54 checks total** on this hub with an empty changed set (instrumented 2026-09-11 — the results list of `run_consistency_checks(tier=2, changed_files=set())`). Two of the 54 are not `run_optional_check` rows — `epic_order --check` and the Kilo CLI Health Check — so a probe that counts CALLS rather than the results list answers 52; neither is changed-set-gated; only `epic_order --check` is gated on file existence at all (`_epic_order_row` returns no row where `scripts/epic_order.py` is absent, so a project's Tier-2 total is 53), while the Kilo row is appended on every `tier >= 2` run and degrades to an UNLABELLED green `(check not present, skipping)` row when its script is missing — it reaches neither `--json` warnings nor `skipped_checks`. A REAL changed set gives FEWER, not more (52 for a one-`.md` diff, 53 for a one-`.py` diff): every `if not changed or …` predicate is satisfied by an empty set. (The 2026-08-16 registration audit unwired four Tier-2 checks that could not fail — `check_env_updates`, `check_test_coverage`, `check_compose_services`, `check_reusable_modules`.) (Counts verified by INSTRUMENTED EXECUTION — stubbing `run_optional_check`/`run_cmd` and counting `run_consistency_checks(tier=…)`'s actual results list: tier 1 → 34, tier 2 → 54, tier 3 → 22, all from the results list with `changed_files=set()` (2026-09-11); by `run_optional_check` calls alone the same runs read 34 / 52 / 20 — never by eyeballing the call sites; the line-number ranges that used to be cited here are deliberately dropped — they drifted on every insertion and a wrong `path:line` is worse than none.)

**The Tier-2-only checks:**
- **Phase Tests (plan-window)** - `check_phase_tests.py` *(ADVISORY row)*
  - WARNs when an ACTIVE plan lock's window declares Behavior-Contract rows and ships lock-owned source with zero test changes
- **Doc Link Integrity (live tree)** - `check_doc_links.py` (2026-07-20: every repo-path reference in the live knowledge tree must resolve; archives/pipeline artifacts/LESSONS ledger/scaffold `*_TEMPLATE.md` + `scaffold-templates/` exempt — templates carry intentional placeholder refs; blocking)
- **INDEX.md ↔ docs tree drift** - `check_doc_index.py` (2026-07-20: INDEX targets exist + every live doc indexed by path/basename; blocking)
- **Retired-Tech Tripwire** - `check_retired_terms.py` *(ADVISORY row)* (2026-07-20: WARN-only — the script always exits 0; flags unmarked Kilo CLI / Windsurf Cascade / Coolify / Supabase live-framing. 73 open WARNs in the hub, which is why it advises rather than blocks)
- **Stage-Skip Artifact Gate** - `check_stage_artifacts.py`
  - Spec freshness + FROZEN header shape for a stage that was skipped
- **Hooks Index Fresh** - `check_hooks_index.py`
  - Hub-only; the hooks index matches the live hook set (self-skips off the hub)
- **Sync Trigger Coverage** - `check_sync_trigger_coverage.py`
  - Hub-only; every fleet-synced surface either fires the governance-sync or is a DECLARED
    non-trigger, so a fleet-wide file cannot be edited and silently ship nothing. Self-skips in
    projects; fails loudly if the hub's manifest goes missing; warns when run from a checkout the
    sync hook cannot fire from (a worktree)
- **Project Structure** - `check_structure.py`
  - Validates directory layout matches Fabrik conventions
- **opencode.json (Kilo-Safe Rules)** - `check_opencode_json.py`
  - Validates Kilo-safe rules configuration
- **Behavior Contract Proposal** - `check_test_proposal.py`
  - Verifies test justification is documented
- **Plan-Set Contract (Spine+Tickets)** - `check_plan_tickets.py` — the spine↔ticket contract for the spine+ticket plan shape (Board↔files, Depends DAG + Merge Order, exclusive Touches, never-route routing cross-check, READ budget, Board staleness; sibling/DRAFT findings are advisory)
- **README.md (Primary Entry Point)** - `check_readme_md.py`
  - Validates primary entry point documentation
- **.env.example Completeness** - `check_env_example.py` *(ADVISORY row)*
  - Warns when a staged diff reads an env var that `.env.example` does not declare
  - No other check covers code → `.env.example` (`check_doc_sync` only fires `.env.example` → `CONFIGURATION.md`), but 44 of 44 `/opt` repos already violate it (2223 undeclared vars, 240 in the hub), so it advises rather than blocks
- **User Guide Presence** - `check_user_guide.py`
  - Verifies `docs/user-guide/` exists with `.md` files when `project.yaml` has `has_user_guide: true`
  - Skips silently when `has_user_guide` is false or absent
- **epic_order --check** - `scripts/epic_order.py --check` *(hub-conditional row; `_epic_order_row()`)*
  - The epic-graph integrity proof over `docs/development/epics/*.md` frontmatter (numbering, `Epic N — …` title shape, parallel `owned_paths` disjointness, single migration owner — `EPIC-ARTIFACT-SCHEMA.md`); one finding reds the row, blocking
  - Row exists ONLY where `scripts/epic_order.py` exists — it is a hub tool in no synced manifest, so a project sees no row at all (never a failure pointing at a missing script)
  - Script present but no `docs/development/epics/` → the row is named `epic_order --check (N/A — no docs/development/epics/)`: green by contract, but the ⚠ text lands in `--json` `warnings` and the name is listed under `skipped_checks` — the same labelled-skip shape as `bandit (NOT INSTALLED — skipped)`, never a silent pass

**Kilo CLI Health Check** - `check_kilo_health.sh` — runs at `tier >= 2`, i.e. Tier 2 **and** Tier 3, not Tier-2-only.

**Not wired into the gate** (exist on disk, never invoked — see § All Checks Reference): `check_index_md.py`, `check_configuration_md.py`, `check_openapi_sync.py`, `check_changelog.py`, `check_docs.py`. Their intent is now covered by `check_doc_sync.py` (Doc Sync Matrix, Tier 1+2) and `docs_updater.py --check` (Tier 3).

**`--json` `warnings` array:** advisory checks that emit a `⚠`-prefixed line surface it under a top-level
`warnings` list in `--json` output (previously advisory output was human-mode-only). Benign passed-check
chatter and plain `WARNING:` output are excluded — a check opts in by prefixing with `⚠`.

### Tier 3 (SYSTEMIC) - `--systemic` - Repo Health

**Purpose:** On-demand repo/system hygiene (no showstoppers)

**Phase 3: Repo Consistency (22 checks)** — `run_consistency_checks` (the `tier >= 2` / Tier-3 selections; the results list under an empty changed set, instrumented 2026-09-11 — no Tier-3 row is changed-set-gated, and 20 is the `run_optional_check` call count; the old "13" and then "14" each dropped unconditional rows). **Twelve rows are bulleted below — seven Tier-3-specific, the Kilo CLI Health Check row shared with Tier 2, plus the four unconditional every-tier rows repeated from Tier 1 (Convergence Evidence, Coverage Checklist, Plan-lock release, Review hygiene). The remaining ten are the rest of the fourteen unconditional rows** (Vendored Drift, Routing Policy, Governance Tables, Certification Coverage, Rivals dossier, Spec convergence, Rule grounding, Citations resolve, Feedback duty, Trigger routing)
- **Convergence Evidence (plans + reviews)** - `check_convergence.py` — runs every tier, unconditionally; the CLOSING-ROW rule (D-206, 2026-09-09; landed by the review-family adoption plan on 2026-09-10): once a NON-ARCHIVED plan-set spine carries any `| Pass …` / `| Round …` table row with a `confirmed:` counter — anywhere in the file, no `## Pass Ledger` heading required — a CONVERGED or EXECUTED flip whose LAST such row does not read `confirmed: 0` is refused (`_check_spine_set` is reached from both claim paths; an `archived/` spine returns unchecked; `_PASS_ROW` — indented rows included, blockquoted excluded; fences stripped, code spans masked, HTML comments blanked, in that order; the row's last `confirmed:` token counts; `_closing_row_fail` is the single function the flip check calls and the one any fleet census must call — the census here is an ad-hoc measurement through that import, not a committed caller) — measured 2026-09-11 through that function over the 1,061 readable plan files under `/opt/*/docs/development/plans` in the 43 main checkouts (the registered worktrees excluded via `git worktree list`, not by path name — `/opt/fabrik-lib-account` is one and carries a byte-identical copy; 1,062 on disk, 1 a dangling symlink): 71 contain the substring `## Pass Ledger` (77 case-insensitively), 21 of them plan-set spines — 10 of those under `archived/`, which the rule never grades, leaving 11 (the heading is incidental: the GRADED population is every non-archived spine — 19 live of 47 fleet-wide, 28 archived) — 1 of the 1,061 carries a counter row (`2026-09-10-plan-1-review-family-adoption.md`, a bare dated plan that is NOT a plan-set spine, so the rule never reaches it) and 0 of the 19 live spines do, hence 0 refusals; separately, the last-token design's own cost is 0 of 47 spines and 0 of 805 fleet receipts carrying more than one `confirmed:` token on one Pass row when read through the rule's own masking (`check_convergence.py`'s `_PASS_ROW` comment states the convention)
- **Coverage Checklist (reviews)** - `check_review_coverage.py` — runs every tier, unconditionally
- **Plan-lock release** - `check_plan_lock_release.py` — runs every tier, unconditionally (advisory `warn_only=True`): reports a `.fabrik/plan-locks/<id>.json` left NON-TERMINAL (`active`/`paused`/`blocked`) after its plan finished. Every-tier ON PURPOSE — `--lean` is the mode agents run while a lock is live. Doc: [plan-lock-lifecycle.md](../reference/plan-lock-lifecycle.md)
- **Review hygiene (advisory)** - `check_review_hygiene.py` — runs every tier, unconditionally (advisory `warn_only=True`, no failing exit path): the grep-shaped classes a review round otherwise re-sweeps by hand — fragment residue (`template-residue`: the renderer's own shapes only, `{{include:<name>}}` or `{{UPPER_CASE}}` anchored at both braces — a Go template such as `{{.Image}}` is not residue), CommonMark fence parity, a table row whose cells do not line up with its header (`raw-pipe` on a receipt; `table-parity` on ANY `.md` surface — a spec, a plan, a rendered command — through one shared helper, fenced and commented lines blanked first), and a disposition cell carrying two or more bare verdict words (five of the script's eight classes — `changelog-entry`, `dead-symbol` and `stale-phrase` are the other three: the last two answer `--symbol` / `--phrase`, and `changelog-entry` runs `check_changelog.py`'s own quality rule whenever a `CHANGELOG.md` is on the surface). Registered with NO arguments on purpose: it self-selects the CHANGED receipts under `docs/development/reviews/` from `git status` and prints nothing when none changed, so it is inert on every unrelated commit. The orchestrator invokes it directly at each round's start and close (`--surface` · `--receipt` · `--phrase` · `--symbol` · `--json`). Fire rate over the 275 committed hub receipts at `8092e8a8` — the numbers are TRANSCRIBED from `tests/enforcement/test_check_review_hygiene.py::test_the_fire_rate_over_the_committed_receipt_corpus`'s printed output, which pins them, never typed by hand: raw-pipe 35 hits in 21 receipts (0.584 % of 5,992 table data rows), dual-verdict 27 hits in 5 receipts (1.624 % of 1,663 disposition-bearing rows) — re-pinned 2026-09-10 after the comment blanking learned to read code spans (a cell quoting `<!-- POOL OFF` had blanked every later row of 9 of the 805 fleet receipts (measured 2026-09-10; the population was 805 again on 2026-09-11, when the same-shaped probe found 11 receipts quoting the marker)); 4,296 rows (71.7 %) were graded by NO disposition class — which is not the same as carrying no verdict; a row with three verdict words in a header-less table lands here: a row in a table with no header pair is graded by neither class, and a row in a headed table that declares no disposition column (the header cell must be that one word, case-insensitively, bold tolerated — `Disposition (round)` is not recognised) is cell-count-checked by `raw-pipe` and never dual-verdict-graded — counted as ungraded when its cells line up, and reported as a `raw-pipe` hit when they do not (such a hit row is in neither bucket — 33 of the 35 raw-pipe hits, exactly the gap between 4,296 + 1,663 and the 5,992 denominator; the other 2 hits sit in disposition-declaring tables and are counted in the 1,663); never read as clean; every run that prints a summary states that bound (`--json` carries it as `ungraded_rows`; the no-argument gate run prints nothing at all when no receipt changed). Advisory until infra measures its false-positive rate below 5 % over 20 receipts, counted from the receipts' own `RECORDED — hygiene false positive (…)` rows.
- **Docker** - `check_docker.py`
  - Validates amd64 compatibility, No-Alpine base images, HEALTHCHECK presence
- **.env Contract Sync** - `check_env_contract.py`
  - Validates environment variable contracts are consistent
- **Documentation Sprawl** - `check_doc_sprawl.py` (2026-07-20: new-file detection is HEAD-or-staged-rename — a merely-staged new .md no longer bypasses the allowlist)
  - Detects documentation sprawl and duplication
  - (Doc Link Integrity, INDEX↔tree drift, and Retired-Tech Tripwire are registered in the `if tier == 2:` block — they are Tier-2-only, listed above, and do NOT run at Tier 3)
- **Duplicate Detection** - `check_duplicates.py`
  - Detects duplicate files and configurations
- **Documentation Drift** - `docs_updater.py --check`
  - Ensures documentation matches code implementation
- **VPS Docs Freshness** - `check_vps_docs.py` *(ADVISORY row)*
  - Checks VPS-facing docs haven't gone stale against the live fleet
  - Every finding it can construct is `Severity.WARN`; until 2026-08-16 its `__main__` exited 1 on ANY finding, so a `vps-status.md` the check couldn't find (it pointed at `docs/operations/`; the file is in `docs/infrastructure/`) redded a blocking row. Exit now follows severity (ERROR fails; `--strict` promotes WARN), matching `_check_runner.run_as_main`
- **Fabrik Convention Validator** - `validate_conventions.py --strict --git-diff` (the gate's display name; appended directly — a missing script yields an UNLABELLED green `(check not present, skipping)` row, the Kilo row's shape)
  - Validates naming conventions and structure
- **Kilo CLI Health Check** - `check_kilo_health.sh` (shared with Tier 2, `tier >= 2`)
  - Validates Kilo CLI installation and configuration

**Note:** `check_docs.py` ("Documentation") is NOT part of this list — it exists on disk but was removed
from the gate (per `final_gate.py`'s inline removal comment — hardcoded to `src/fabrik/`, dead in every scaffolded project; line numbers deliberately not cited, they drift). Its
intent is covered by the Doc Sync Matrix (`check_doc_sync.py`, Tier 1+2) and `docs_updater.py --check` above.

### Phase 4: Sync Steps

**Runs in:** `--sync` mode only

| Step | Script | Purpose |
|------|--------|---------|
| **Windsurf Extensions** | `sync_extensions.sh` | Sync to EXTENSIONS.md |
| **Cascade Backup** | `sync_cascade_backup.sh` | Check backup freshness |

---

## Advisory rows — the ones that can never go red

A check registered `run_optional_check(..., warn_only=True)` has **no failing exit path**. Its row prints
`[ADVISORY]` instead of `[PASS]`, the SUMMARY lists it by name under `Advisory:`, and `--json` reports it
under `advisory` alongside a `blocking` count. Read `blocking`, not `passed`: `passed` counts rows that
were never at risk.

**Why this exists.** On 2026-08-16 a canary sweep gave eight registered checks a real violation each. Each
PRINTED the violation and each exited 0 — and produced a row identical to a check that genuinely blocks.
Four of them (`check_compose_services`, `check_env_example`, `check_env_updates`, `check_test_coverage`)
were not even registered `advisory=True`, so `run_optional_check` discarded their stdout on exit 0: fully
silent green rows. Each was then decided on measured evidence — the reasoning is written at each
registration in `final_gate.py`:

| Check | Decision | Measured basis |
|---|---|---|
| `check_env_example` | ADVISORY | 2223 undeclared vars, 44/44 repos — a real uncovered Doc-Sync rule, unpromotable |
| `check_script_headers` | ADVISORY | 427 headerless scripts, 36/44 repos (107 in the hub); CLAUDE.md documents it as WARN |
| `check_retired_terms` | ADVISORY | 73 open WARNs in the hub; `return 0  # ALWAYS` is its written contract |
| `check_doc_stubs` | ADVISORY | 16/44 repos still ship a stub `docs/QUICKSTART.md` |
| `check_env_updates` | UNWIRED | asserts about `.env` — gitignored, machine-local, never part of the commit; 482 divergences, 17/44 repos |
| `check_test_coverage` | UNWIRED | 2063 findings, 20/44 repos; its rule is the 100%-coverage dogma the Behavior Contract rejects |
| `check_compose_services` | UNWIRED | blind to a service added to an EXISTING compose; `service_documented` is a substring match; covered by `check_doc_sync` |
| `check_reusable_modules` | UNWIRED | universe is empty — 0/44 repos had `src/utils/` or `src/lib/` on 2026-08-16; 3 of 43 main checkouts carry a `src/lib/` on 2026-09-11, none containing a single `.py` file |

`warn_only=` is **not** `advisory=`. `advisory=` only preserves stdout on exit 0; several checks carrying
it (`check_docker`, `check_env_contract`, `check_doc_sprawl --strict`, `check_lint_ratchet`,
`check_subagent_flywheel`) DO fail the gate on a real defect. A `warn_only` check that exits non-zero still
fails, and the gate names the broken contract.

**Enforcement of the enforcement.** `liveness_audit.py`'s vacuity proof judges a blocking row on whether it
can go RED and an advisory/unwired one on whether it can SPEAK, so declaring a row honestly is no longer
punished as INERT. Two ratchets in `tests/test_gate_check_canaries.py` hold the line: a warn-only check may
never be registered as an ordinary blocking row, and a `warn_only=True` declaration must be backed by a
written contract in `liveness_audit.CANARIES` / `UNREACHABLE`.

---

## All Checks Reference

### Static Analysis Checks (Phase 2)

#### ruff

```bash
# What it checks
python -m ruff check src/ scripts/

# Auto-fix (Phase 1)
python -m ruff check --fix src/ scripts/
python -m ruff format src/ scripts/
```

**Common issues:**
- Unused imports (F401)
- Undefined names (F821)
- Line too long (E501)
- Import sorting (I001)

#### mypy

```bash
# What it checks
python -m mypy --config-file=pyproject.toml src/package_name
```

**Recovery:** If mypy hangs (cache corruption), final_gate clears cache and retries with `--no-incremental`.

**Common issues:**
- Missing type annotations
- Type mismatches
- Incompatible return types

#### bandit

```bash
# What it checks
python -m bandit -ll -x tests/ -r src/
```

**Common issues:**
- Hardcoded passwords (B105)
- SQL injection (B608)
- Insecure pickle (B301)

#### semgrep

```bash
# What it checks
semgrep --config auto src/
```

**Note:** Requires `semgrep login` for authentication. Skipped if not authenticated.

#### sqlfluff

```bash
# What it checks
python -m sqlfluff lint --dialect postgres *.sql
```

**Dialect:** PostgreSQL (required for Fabrik projects)

**Common issues:**
- SQL syntax errors
- Missing semicolons
- Incorrect keywords
- Inconsistent capitalization

**Note:** Only runs if `.sql` files exist in the repository.

### Enforcement Scripts

All repo consistency checks are implemented by scripts in `scripts/enforcement/` — the bare rows below, `check_*.py` and `validate_conventions.py` — with five exceptions the list spells out in full: `scripts/docs_updater.py`, `scripts/render_doc_script_links.py` (two rows), `scripts/sysadmin/install_user_hooks.py`, `scripts/check_kilo_health.sh`, and the hub-conditional `scripts/epic_order.py --check`. Each script validates specific Fabrik conventions. The list is GENERATED from `run_consistency_checks`'s own call sites in `scripts/final_gate.py` (the generation note below); `run_static_checks` contributes no rows to it — the Phase-2 tools are documented under § Static Analysis Checks:

**Gate-wired (invoked by `final_gate.py`):** — this list is GENERATED from an instrumented run of `run_consistency_checks(tier=t, changed_files=set())` for t = 1, 2, 3 with `check_only=True`, `run_optional_check` stubbed to record `(script_path, check_name, warn_only, advisory)` and return `(check_name, True, "")`, and `run_cmd` stubbed to `(0, "")` (2026-09-11; 61 rows: 58 through `run_optional_check`, 3 appended directly). Regenerate it the same way — never by hand: three hand-kept versions drifted (2026-07-20, 2026-08-16, 2026-09-11). A row whose display name says BLOCKING but is registered `advisory=True` (Command Corpus, Subagent Flywheel) is printed as registered — the flag, not the name, is what the gate does.

- `scripts/docs_updater.py` — Documentation Drift (Tier 3; ADVISORY row)
- `check_certification_coverage.py` — Certification Coverage (advisory; board mix-up BLOCKS) (every tier; ADVISORY row)
- `check_citations_resolve.py` — Citations resolve (path:line lands) (every tier; advisory — `warn_only`, never blocks)
- `check_command_corpus.py` — Command Corpus (references resolve — BLOCKING) (Tier 2; ADVISORY row)
- `check_convergence.py` — Convergence Evidence (plans + reviews) (every tier; BLOCKING)
- `check_decisions_unique.py` — Decision Ledger (unique ids) (Tier 1/2; BLOCKING)
- `check_doc_index.py` — INDEX.md ↔ docs tree drift (Tier 2; BLOCKING)
- `check_doc_links.py` — Doc Link Integrity (live tree) (Tier 2; BLOCKING)
- `check_doc_sprawl.py` — Documentation Sprawl (Tier 3; ADVISORY row)
- `check_doc_stubs.py` — Doc stub fill (Tier 1/2; advisory — `warn_only`, never blocks)
- `check_doc_sync.py` — Doc Sync Matrix (Tier 1/2; BLOCKING)
- `check_docker.py` — Docker (amd64 platform, No-Alpine builds, HEALTHCHECK) (Tier 3; ADVISORY row)
- `check_duplicates.py` — Duplicate Detection (Tier 3; BLOCKING)
- `check_env_contract.py` — .env Contract Sync (Tier 3; ADVISORY row)
- `check_env_example.py` — .env.example Completeness (Tier 2; advisory — `warn_only`, never blocks)
- `check_env_vars.py` — Hardcoded localhost/127.0.0.1 Ban (Tier 1/2; BLOCKING)
- `check_feedback_duty.py` — Feedback duty (every tier; advisory — `warn_only`, never blocks)
- `check_frozen_chain.py` — Frozen Chain (contract pins) (Tier 1/2; advisory — `warn_only`, never blocks)
- `check_governance_tables.py` — Governance Tables (rules must render) (every tier; advisory — `warn_only`, never blocks)
- `check_hooks_index.py` — Hooks Index Fresh (Tier 2; BLOCKING)
- `check_imports_resolvable.py` — Imports Resolvable (clean checkout) (Tier 1/2; ADVISORY row)
- `check_lint_ratchet.py` — Lint Ratchet (repo-wide, no new debt) (Tier 1/2; ADVISORY row)
- `check_mutation.py` — Mutation (opt-in FABRIK_MUTMUT) (Tier 1/2; advisory — `warn_only`, never blocks)
- `check_no_host_ports.py` — No Host Ports on Traefik Services (Tier 1/2; BLOCKING)
- `check_opencode_json.py` — opencode.json (Kilo-Safe Rules) (Tier 2; BLOCKING)
- `check_pack_reachability.py` — Rule-pack reachability (Tier 2; advisory — `warn_only`, never blocks)
- `check_phase_tests.py` — Phase Tests (plan-window) (Tier 2; advisory — `warn_only`, never blocks)
- `check_plan_lock_release.py` — Plan-lock release (every tier; advisory — `warn_only`, never blocks)
- `check_plan_tickets.py` — Plan-Set Contract (Spine+Tickets) (Tier 2; BLOCKING)
- `check_print_ban.py` — Print/Console.log Ban (Tier 1/2; BLOCKING)
- `check_readme_md.py` — README.md (Primary Entry Point) (Tier 2; BLOCKING)
- `check_retired_terms.py` — Retired-Tech Tripwire (Tier 2; advisory — `warn_only`, never blocks)
- `check_review_coverage.py` — Coverage Checklist (reviews) (every tier; ADVISORY row)
- `check_review_hygiene.py` — Review hygiene (advisory) (every tier; advisory — `warn_only`, never blocks)
- `check_rivals_dossier.py` — Rivals dossier (every tier; advisory — `warn_only`, never blocks)
- `check_routing_policy.py` — Routing Policy (operator deny + allowlist) (every tier; advisory — `warn_only`, never blocks)
- `check_rule_grounding.py` — Rule grounding (plans) (every tier; advisory — `warn_only`, never blocks)
- `check_schema_sync.py` — Schema Sync (DB Models) (Tier 1/2; ADVISORY row)
- `check_script_headers.py` — Script Coupling Header (Tier 1/2; advisory — `warn_only`, never blocks)
- `check_secrets.py` — Secrets (Zero Hardcoding) (Tier 1/2; BLOCKING)
- `check_spec_convergence.py` — Spec convergence (every tier; advisory — `warn_only`, never blocks)
- `check_spec_db_match.py` — Spec <-> Project DB Name Match (Phase 1c) (Tier 1/2; BLOCKING)
- `check_stage_artifacts.py` — Stage-Skip Artifact Gate (spec freshness + FROZEN header shape) (Tier 2; BLOCKING)
- `check_structure.py` — Project Structure (Tier 2; BLOCKING)
- `check_subagent_flywheel.py` — Subagent Flywheel (pool-or-declare — BLOCKING) (Tier 1/2; ADVISORY row)
- `check_sync_trigger_coverage.py` — Sync Trigger Coverage (Tier 2; BLOCKING)
- `check_synced_unmodified.py` — Fabrik-Synced Files Unmodified (Tier 1/2; BLOCKING)
- `check_test_proposal.py` — Behavior Contract Proposal (Tier 2; BLOCKING)
- `check_ticket_breadth.py` — Ticket Breadth (plan sets) (Tier 2; advisory — `warn_only`, never blocks)
- `check_traefik_labels.py` — Full Traefik Label Set (§7) (Tier 1/2; BLOCKING)
- `check_trigger_routing.py` — Trigger routing (advertised phrase -> its own command) (every tier; advisory — `warn_only`, never blocks)
- `check_undeclared_imports.py` — Undeclared Imports (requirements.txt) (Tier 1/2; BLOCKING)
- `check_user_guide.py` — User Guide Presence (Tier 2; BLOCKING)
- `check_vendored_drift.py` — Vendored Drift (sync-excluded repos) (every tier; advisory — `warn_only`, never blocks)
- `check_vps_docs.py` — VPS Docs Freshness (Tier 3; advisory — `warn_only`, never blocks)
- `scripts/render_doc_script_links.py` — Doc-Script Coverage (ratchet) (Tier 1/2; BLOCKING)
- `scripts/render_doc_script_links.py` — Doc-Script Links (Tier 1/2; BLOCKING)
- `scripts/sysadmin/install_user_hooks.py` — User-Level Hooks Registered (Tier 2; advisory — `warn_only`, never blocks)
- `validate_conventions.py --strict --git-diff` — Fabrik Convention Validator (Tier 3; appended outside `run_optional_check` — appended directly; a missing script yields an UNLABELLED green `(check not present, skipping)` row that reaches neither `--json` warnings nor `skipped_checks`)
- `scripts/check_kilo_health.sh` — Kilo CLI Health Check (Tier 2/3; appended outside `run_optional_check` — appended directly; a missing script yields an UNLABELLED green `(check not present, skipping)` row that reaches neither `--json` warnings nor `skipped_checks`)
- `scripts/epic_order.py --check` — epic_order --check (Tier 2; appended outside `run_optional_check` — hub-conditional: no row where `scripts/epic_order.py` is absent)

**On disk but NOT gate-wired as their own row** (no `run_optional_check` call site in `final_gate.py`; NOT all dead — five are reached through another row's import and a sixth only through an explicit `--surface` run, see each bullet; re-verified 2026-09-11 against `final_gate.py`'s eight `# UNWIRED —` markers — the four retired from the Tier-2 block (`check_env_updates.py`, `check_test_coverage.py`, `check_compose_services.py`, `check_reusable_modules.py`) and the four from the Tier-3 block (`check_ports.py`, `check_deps_sync.py`, `check_watchdog.py`, `check_health.py`); all eight carry a 2026-08-16 measurement beside their marker). Their intent is now covered by `check_doc_sync.py` (Doc Sync Matrix) + `docs_updater.py --check`, not by these files:
- `check_changelog.py` — was: validates CHANGELOG.md updated (not gate-wired as a ROW; imported behind a `try/except ImportError` by `check_review_hygiene.py`'s `changelog-entry` class, reached only by a `--surface` run whose expansion contains a file named `CHANGELOG.md`)
- `check_index_md.py` — was: verifies INDEX.md reflects current structure
- `check_configuration_md.py` — was: ensures env vars documented in CONFIGURATION.md
- `check_openapi_sync.py` — was: validates API docs match routes
- `check_docs.py` — was: warns when a new `src/fabrik/` module's `__init__.py` has no mention in `INDEX.md` under `docs/` (the script's own path; the hub keeps `INDEX.md` at the root) and no dedicated doc file (removed as a ROW per `final_gate.py`'s inline removal comment — hardcoded to `src/fabrik/`; line numbers deliberately not cited, they drift); LIVE via `validate_conventions.py` on every changed `__init__.py`
- `check_ports.py` — was: PORTS.md registration (`# UNWIRED —` marker, 2026-08-16); LIVE via `validate_conventions.py` on every changed Dockerfile and `.py/.ts/.tsx/.js/.yaml/.yml` file
- `check_deps_sync.py` — was: dependencies documented (`# UNWIRED —` marker, 2026-08-16); LIVE via `validate_conventions.py` on a changed `requirements.txt`
- `check_watchdog.py` — was: watchdog scripts present (`# UNWIRED —` marker, 2026-08-16); LIVE via `validate_conventions.py` on every changed compose file it dispatches (`check_watchdog.py` itself silently skips `docker-compose.yml` and any case-variant — its guard matches the un-lowercased name while the dispatcher lowercases first)
- `check_health.py` — was: /health endpoint validation (`# UNWIRED —` marker, 2026-08-16); LIVE via `validate_conventions.py` on every changed `.py` file (the check itself skips any file with `test` in its name)
- `check_env_updates.py` — was: .env Updates (Secrets) (`# UNWIRED —` marker, 2026-08-16: could not fail)
- `check_test_coverage.py` — was: Test Coverage (New Code) (`# UNWIRED —` marker, 2026-08-16)
- `check_compose_services.py` — was: Compose Services Docs (`# UNWIRED —` marker, 2026-08-16)
- `check_reusable_modules.py` — was: Reusable Module Tagging (`# UNWIRED —` marker, 2026-08-16: 0 of 44 repos had `src/utils/` or `src/lib/` then; 3 of 43 main checkouts carry a `src/lib/` on 2026-09-11, none containing a single `.py` file)

Do not delete any of these 13 files yourself. Five are LIVE through an import — `check_health.py`, `check_ports.py`, `check_watchdog.py`, `check_deps_sync.py` and `check_docs.py` are imported by `validate_conventions.py` (`check_docs` inline in `run_all_checks`, the other four in the `run_check_*` wrappers it calls; the Tier-3 Fabrik Convention Validator row runs it with `--git-diff` over every changed file; the imports are unguarded and deferred, so deleting one reds the Tier-3 row with a `ModuleNotFoundError` the first time a file its dispatch matches appears in the diff — `__init__.py` for `check_docs`, any `.py` for `check_health`, a compose file for `check_watchdog`, `requirements.txt` for `check_deps_sync`, a Dockerfile or `.py/.ts/.tsx/.js/.yaml/.yml` for `check_ports`). `check_changelog.py` is imported — behind a `try/except ImportError` that degrades to an advisory hit — by `check_review_hygiene.py`'s `changelog-entry` class, which the gate's argument-less row never reaches: it fires on any `--surface` run whose expansion contains a file named `CHANGELOG.md` — a directory surface counts, since `--surface <dir>` rglobs every `.md` and `.py` beneath it — which is how `/fabrik-review` and the `term-edit` fragment reach it when the surface they name includes the CHANGELOG (no corpus invocation names the file itself). The other seven carry no gate row: four — `check_env_updates.py`, `check_test_coverage.py`, `check_compose_services.py`, `check_reusable_modules.py` — are still EXECUTED as vacuity canaries by `scripts/sysadmin/liveness_audit.py` (`CANARIES`), and `check_reusable_modules.py` is imported by `tests/test_cross_cutting_enforcement.py`, so deleting one breaks that audit (and that test), not the gate; only `check_index_md.py`, `check_configuration_md.py` and `check_openapi_sync.py` have no caller at all.

---

#### check_structure.py

**Purpose:** Validate project follows Fabrik directory structure.

**Required directories:**
- `src/` — Source code
- `docs/` — Documentation
- `scripts/` — Utility scripts
- `tests/` — Test suite
- `.droid/` — Kilo working directory

**Why this matters:**
- Consistent structure across projects
- Enables automation and tooling

#### check_opencode_json.py

**Purpose:** Ensures project's opencode.json contains only Kilo-safe instructions.

**Validates:**
- File exists and is valid JSON
- Contains `instructions` field that is a list
- Instructions exactly match Kilo-safe allowlist: `["AGENTS-compact.md"]`
- No forbidden patterns (e.g., `.windsurf/rules/*.md`)
- Instructions are in correct order

**Why this matters:**
- Prevents Cascade-only rules from being passed to Kilo CLI agents
- Ensures consistent behavior across all projects
- Enforces separation: Traycer uses AGENTS.md, Kilo uses AGENTS-compact.md

**Example valid configuration:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

#### check_index_md.py

**⚠️ NOT gate-wired** — exists on disk, no call site in `final_gate.py` (verified 2026-07-20). Covered instead by `check_doc_sync.py` (Doc Sync Matrix).

**Purpose (as written, dead):** Ensures INDEX.md reflects current file structure.

**Validates:**
- All important files are listed
- No stale entries for deleted files
- File descriptions are accurate
- Hierarchy is properly organized

**Why this matters:**
- Provides project navigation
- Helps new team members find files

#### check_test_proposal.py

**Purpose:** Enforce One-Test Rule from Solo-Dev Creed (Step 2.5 Decision-Grade Audit).

**When triggered:**
- After Step 2.5 Internal Audit
- During Step 5 Final Gate (this script)
- Validates that agents documented test justification BEFORE implementation

**Validates presence of:**
- `One-Test Rule` heading or section
- `Given` — Initial state
- `When` — Action taken
- `Then` — Expected result

**Location checked:** `docs/development/plans/` (latest plan file)

**Skipped when:** No plans directory or no plan files exist

**Why this matters:**
- **Forces High-Leverage Thinking:** Solo developers avoid low-value "coverage" tests
- **Prevents Forgotten Context:** Documents how to verify core logic for future maintenance
- **Ensures AI Discipline:** Stops agents from prioritizing "clean code" over correctness
- **Zero-Speculation:** Eliminates need to "guess" how to test during implementation

**Example format:**
```markdown
## One-Test Rule

**Why:** Database connection pooling is the highest risk area — if pool exhausts,
entire API becomes unresponsive. This test verifies graceful degradation.

**Contract:**
- **Given:** Connection pool at max capacity (10/10 connections)
- **When:** New API request arrives
- **Then:** Request waits up to 5s, then returns 503 with retry-after header
- **Mocked:** Database responses (simulate slow queries)
- **Real:** Connection pool manager, timeout logic
```

**Exit codes:**
- `0` — Proposal found or no plan exists
- `1` — Plan exists but missing required keywords

#### check_readme_md.py

**Purpose:** Ensures README.md is a valid primary entry point.

**Validates:**
- Required sections exist (Overview, Quick Start, etc.)
- Installation instructions work
- Links are valid
- Project description is clear

**Why this matters:**
- README is often the first thing people see
- Must provide accurate project introduction

#### check_configuration_md.py

**⚠️ NOT gate-wired** — exists on disk, no call site in `final_gate.py` (verified 2026-07-20). Covered instead by `check_doc_sync.py` (Doc Sync Matrix), which fires on new env vars per the Doc Sync Matrix.

**Purpose (as written, dead):** Ensures CONFIGURATION.md documents all env vars.

**Validates:**
- Every environment variable is documented
- Usage examples are provided
- Security implications are noted
- Default values are specified

**Why this matters:**
- Complete configuration reference
- Prevents configuration errors

#### check_env_updates.py — UNWIRED 2026-08-16

**⚠️ NOT gate-wired** — `final_gate.py`'s own `# UNWIRED — check_env_updates.py` marker retired the row on 2026-08-16 (the measurement sits beside it); still EXECUTED as a vacuity canary by `scripts/sysadmin/liveness_audit.py` (`CANARIES`), so it is not dead code.

**Purpose (actual):** compares `.env.example` against the local `.env` and reminds you which declared
variables have no local value. It never scanned code for secrets — that is `check_secrets.py`.

**Why it is no longer a gate row:** `.env` is gitignored, machine-local and secret-bearing, so it is not
part of the change under gate and legitimately omits every optional variable. 482 divergences across 17 of
44 `/opt` repos. It also shared the display name ".env Updates (Secrets)" with the blocking
`check_env_vars.py` row. Runnable by hand: `python scripts/enforcement/check_env_updates.py`.

**Skips:**
- Test files only
- Documentation only
- Config files only

#### check_changelog.py

**⚠️ NOT gate-wired as its own row — imported behind a guard** — no `run_optional_check` call site in `final_gate.py` (re-verified 2026-09-11); `check_review_hygiene.py`'s `changelog-entry` class imports and calls its `check_changelog_quality` behind a `try/except ImportError` (a missing file degrades to an advisory hit), and only a `--surface` run whose expansion contains a file named `CHANGELOG.md` (a directory surface counts) reaches that class — the gate's argument-less row never does. The CHANGELOG-on-change rule itself is `check_doc_sync.py`'s (Doc Sync Matrix).

**Purpose:** Ensures CHANGELOG.md is updated for significant code changes.

**Triggers when:**
- Changes in `src/`, `scripts/`, `templates/`
- More than 10 lines changed
- New files added

**Skips:**
- Test files only
- Documentation only
- Config files only

**Validates:**
- Entry exists for current changes
- Follows changelog format
- Includes version/date

**Why this matters:**
- Maintains project history
- Helps with release tracking

#### check_schema_sync.py

**Purpose:** Ensures database models match schema.sql.

**Validates:**
- All models have corresponding schema
- Schema includes all columns and indexes
- Migration history is consistent
- Data types match

**Why this matters:**
- Prevents database mismatches
- Ensures reproducible deployments

#### check_openapi_sync.py

**⚠️ NOT gate-wired** — exists on disk, no call site in `final_gate.py` (verified 2026-07-20). Covered instead by `check_doc_sync.py` (Doc Sync Matrix), which folds in API/SDK/CLI-change → `docs/QUICKSTART.md`.

**Purpose (as written, dead):** Ensures API documentation matches actual routes.

**Validates:**
- All endpoints are documented
- Request/response schemas match
- Authentication requirements are documented
- Example values are accurate

**Why this matters:**
- API docs must be trustworthy
- Prevents integration issues

#### check_test_coverage.py — UNWIRED 2026-08-16

**⚠️ NOT gate-wired** — `final_gate.py`'s own `# UNWIRED — check_test_coverage.py` marker retired the row on 2026-08-16 (the measurement sits beside it); still EXECUTED as a vacuity canary by `scripts/sysadmin/liveness_audit.py` (`CANARIES`), so it is not dead code.

**Purpose (actual):** greps `tests/` for the NAME of each new public `def`/`class` added under `src/`. It
cannot tell a meaningful test from a name collision, and it never sees `scripts/` or `libs/`.

**Why it is no longer a gate row:** 2063 findings across 20 of 44 `/opt` repos (295 in the hub), and its
rule — a test per public symbol — is the 100%-coverage dogma the Behavior Contract explicitly rejects.
Coverage is enforced by `check_test_proposal.py` plus the phase-boundary review. Runnable by hand:
`python scripts/enforcement/check_test_coverage.py`.

#### check_env_example.py — ADVISORY row

**Purpose:** warns when the staged diff reads an environment variable (`os.getenv`, `os.environ[...]`,
`os.environ.get`, `settings.X`) that `.env.example` does not declare.

**Why it advises rather than blocks:** it is the only check covering the Doc Sync Matrix rule "New env var
→ `.env.example`" (`check_doc_sync` only fires `.env.example` → `CONFIGURATION.md`), but all 44 `/opt`
repos already violate it — 2223 undeclared vars, 240 in the hub. Decomposed by pattern so the volume is not
mistaken for a loose regex: `os.getenv` 1720, `os.environ.get` 535, `os.environ[...]` 88, `settings.X` 1.

#### check_compose_services.py — UNWIRED 2026-08-16

**⚠️ NOT gate-wired** — `final_gate.py`'s own `# UNWIRED — check_compose_services.py` marker retired the row on 2026-08-16 (the measurement sits beside it); still EXECUTED as a vacuity canary by `scripts/sysadmin/liveness_audit.py` (`CANARIES`), so it is not dead code.

**Purpose (actual):** looks for each newly-added compose service NAME as a case-insensitive substring of
`docs/SERVICES.md` / `README.md`. It never inspected ports, env vars or volumes.

**Why it is no longer a gate row:** two structural faults, not volume. `get_new_services` only enters its
services block when `services:` is itself an ADDED diff line, so it sees a brand-new compose file and is
blind to a service added to an EXISTING one — the actual case. And a substring test passes trivially for
`app`/`api`/`db`/`web`. The surviving intent (compose changed → `SERVICES.md` + `OPERATIONS.md`) is carried
by `check_doc_sync.py`. Runnable by hand: `python scripts/enforcement/check_compose_services.py`.

#### check_docker.py

**Purpose:** Enforces Docker conventions for amd64 compatibility and security.

**Validates:**
- **No Alpine images**: Blocks `FROM alpine` and variants (use `-slim-bookworm` instead)
- **amd64 platform**: Custom builds must specify `platform: linux/amd64`
- **HEALTHCHECK**: All Dockerfiles must include health check
- **Approved base images**: Python 3.12/3.13-slim-bookworm, Node 22-bookworm-slim, debian:bookworm-slim, ubuntu:24.04
- **Port consistency**: EXPOSE ports match compose.yaml mappings

**Why this matters:**
- amd64 is required for VPS deployment (x86_64)
- Alpine images have glibc compatibility issues
- Health checks enable proper container monitoring

#### check_secrets.py

**Purpose:** No secrets committed to git.

**Scans for:**
- API keys
- Passwords
- Private keys
- AWS credentials

**Example detection:**
```python
# BAD
DB_HOST = 'localhost'
API_KEY = 'sk-abc123'  # noqa  (illustrative bad example)

# GOOD
DB_HOST = os.getenv('DB_HOST', 'localhost')
API_KEY = os.getenv('API_KEY')
```

#### check_env_contract.py

**Purpose:** Ensures environment variable contracts are consistent.

**Validates:**
- `.env.example` matches actual `.env` variables
- All required variables are documented
- No undocumented variables in use
- Variable descriptions are accurate

**Why this matters:**
- Prevents deployment failures due to missing env vars
- Ensures clear documentation for setup

#### check_reusable_modules.py

**⚠️ NOT gate-wired** — `final_gate.py`'s own `# UNWIRED — check_reusable_modules.py` marker retired it on 2026-08-16 (its universe was empty: 0 findings fleet-wide — 3 of 43 main checkouts now carry a `src/lib/`, none containing a single `.py` file, re-derived 2026-09-11; the marker's own 2026-08-16 figure was 0 of 44 repos with either directory); this section was added on 2026-09-11 — the doc had none for it before.

**Purpose (from the script's docstring):** Tier 2 enforcement (warning-level, non-blocking): verifies that every .py module in src/utils/ and src/lib/ is listed in INDEX.md with a [reusable] marker.

**Validates:**
- what the docstring states above — no gate row and no gate-side import reach it

**Why this matters:**
- still EXECUTED as a vacuity canary by `scripts/sysadmin/liveness_audit.py` (`CANARIES`) and imported by `tests/test_cross_cutting_enforcement.py` — deleting it breaks that audit and that test, not the gate
- the retirement measurement sits beside its marker in `final_gate.py`

#### check_ports.py

**⚠️ NOT gate-wired as its own row — LIVE via import** — `final_gate.py`'s `# UNWIRED — check_ports.py` marker retired the row with the measurement that did so (re-verified 2026-09-11); `validate_conventions.py` imports `check_file` from it and runs it on every changed Dockerfile and `.py/.ts/.tsx/.js/.yaml/.yml` file under the Tier-3 row, so the file is not dead.

**Purpose:** Ensures PORTS.md is updated with port allocations.

**Validates:**
- All used ports are registered
- No port conflicts documented
- Port purposes are explained
- Auto-generated section is current

**Why this matters:**
- Prevents port conflicts across projects
- Documents service endpoints

#### check_deps_sync.py

**⚠️ NOT gate-wired as its own row — LIVE via import** — `final_gate.py`'s `# UNWIRED — check_deps_sync.py` marker retired the row (re-verified 2026-09-11); `validate_conventions.py` imports `check_file` from it and runs it on a changed `requirements.txt` under the Tier-3 row, so the file is not dead.

**Purpose:** Ensures `requirements.txt` and `pyproject.toml` declare the same dependency set (its three message shapes: a package in one file and not the other, plus a `pyproject.toml` that fails to parse, which short-circuits the comparison).

**Validates:**
- on a changed `requirements.txt` with a sibling `pyproject.toml`: every package named in the file's `[project] dependencies` is named in the other and vice versa (two set differences over package names with version specifiers stripped) — `[project.optional-dependencies]`, PEP-735 `[dependency-groups]` and `[tool.poetry.dependencies]` are NOT read, so a dev dependency listed in both files is still reported as missing from `pyproject.toml`; a `pyproject.toml` that fails to parse is reported and ends the check — nothing about pins, conflicts or dev/prod separation

**Why this matters:**
- Catches an install-set divergence between the two files before it reaches a deployment (it does NOT pin, resolve or reconcile versions)
- Prevents import errors in deployment when a package is declared in one install file only

#### check_docs.py

**⚠️ NOT gate-wired as its own row — LIVE via import** — removed as a row per `final_gate.py`'s inline removal comment (it "was hardcoded to src/fabrik/ and dead in every scaffolded project"; line numbers deliberately not cited, they drift); `validate_conventions.py` still imports `check_file` from it and runs it on every changed `__init__.py` under the Tier-3 row. Covered instead by `check_doc_sync.py` (Doc Sync Matrix) + `docs_updater.py --check` (Tier 3).

**Purpose:** "Check that new src/ modules have corresponding documentation" (the docstring) — it warns when a new `src/fabrik/` module's `__init__.py` has no mention in `INDEX.md` under `docs/` (the script's own path; the hub keeps `INDEX.md` at the root) and no dedicated doc file; it never checks that a set of required doc FILES is present.

**Validates:**
- for each changed `__init__.py` of a `src/fabrik/` SUB-package (the package's own `src/fabrik/__init__.py` is dispatched and then silently skipped by the check's has-subdirectory gate), that the module's name appears in `INDEX.md` under `docs/` (the script's own path; the hub keeps `INDEX.md` at the root) or that one of `docs/<name>.md`, `docs/reference/<name>.md`, `docs/api/<name>.md` exists — a warning otherwise; nothing else

**Why this matters:**
- Ensures project is self-documenting
- Prevents missing critical documentation

#### check_watchdog.py

**⚠️ NOT gate-wired as its own row — LIVE via import** — `final_gate.py`'s `# UNWIRED — check_watchdog.py` marker retired the row (re-verified 2026-09-11); `validate_conventions.py` imports `check_file` from it and runs it on every changed compose file it dispatches under the Tier-3 row (the check itself silently skips `docker-compose.yml` and any case-variant — its own guard matches `file_path.name` un-lowercased against `compose.yaml`, `compose.yml`, `docker-compose.yaml`, while the dispatcher lowercases first), so the file is not dead. This section was added on 2026-09-11 — the doc had none for it before.

**Purpose (from the script's docstring):** Check that services have watchdog scripts.

**Validates:**
- what the docstring states above, per changed compose file `validate_conventions.py` dispatches (it dispatches all four names, lowercased); the check's own guard then drops `docker-compose.yml` and any case-variant, as the banner above says

**Why this matters:**
- the row is gone but the check still runs on every dispatched compose change — a deletion breaks the Tier-3 validator with an unguarded, deferred import: the raise lands the first time a compose file is in the diff

#### check_health.py

**⚠️ NOT gate-wired as its own row — LIVE via import** — `final_gate.py`'s `# UNWIRED — check_health.py` marker retired the row (re-verified 2026-09-11); `validate_conventions.py` imports `check_file` from it and runs it on every changed `.py` file under the Tier-3 Fabrik Convention Validator row (the check itself skips any file with `test` in its name), so the file is not dead.

**Purpose:** Ensures health endpoints test actual dependencies.

**Validates:**
- /health endpoint exists
- Returns proper JSON structure
- Tests database connection
- Checks external service dependencies

**Why this matters:**
- Health checks must reflect real system state
- Prevents false-positive monitoring

#### docs_updater.py

**Purpose:** Ensures documentation matches code (drift check).

**Validates:**
- API docs match actual implementation
- Class/function docs are current
- Parameter types are accurate
- Return values are documented

**Why this matters:**
- Prevents documentation drift
- Maintains trust in docs

#### update_agents_toc.py

**⚠️ ARCHIVED, NOT gate-wired** — the script lives at `scripts/archived/update_agents_toc.py`; no call site in `final_gate.py` (re-verified 2026-09-11).

**Purpose (as written, dead):** Ensures AGENTS.md table of contents is current.

**Validates:**
- All sections are listed in TOC
- Page numbers/links are accurate
- No stale TOC entries
- Formatting is consistent

**Why this matters:**
- Navigation aid for large document
- Helps find specific sections quickly

#### validate_conventions.py

**Purpose:** Fabrik naming and structure conventions.

**Validates:**
- Package names (lowercase, underscores)
- File naming patterns
- Import structure
- Docstring presence

**Why this matters:**
- Maintains consistency across projects
- Enables automated tooling

### Symlink Integrity Check

**Purpose:** Governance files must be local copies, not symlinks.

**Validates 8 governance paths** (`check_symlinks()` in `final_gate.py` — line numbers deliberately not cited, they drift):
- `AGENTS.md` — Local copy
- `agents-fabrik.md` — Local copy (canonical agents doc, synced 2026-07-19)
- `agents-fabrik-core.md` — Local copy (@import-ed platform core, synced 2026-07-19)
- `AGENTS-compact.md` — Local copy
- `opencode.json` — Local copy
- `.windsurfrules` — Local copy
- `.windsurf/rules/` — Local directory (not symlinked), recursive descendant check
- `.windsurf/workflows/` — Local directory (not symlinked), recursive descendant check

**Self-exemption:** Skipped when running inside `/opt/fabrik` (source repo).

---

## Configuration

### Timeouts

| Tool | Timeout (seconds) |
|------|-------------------|
| default | 120 |
| mypy | 300 |
| bandit | 180 |
| sqlfluff | 180 |
| ruff | 120 |
| semgrep | 30 (hardcoded at the call site, `final_gate.py:588`; the `TIMEOUTS["semgrep"]=300` dict entry at `:69` is dead — never read) |

### Max Iterations

Final gate runs up to **3 iterations** to achieve convergence (auto-fix → re-validate).

### Colors (Terminal Output)

- 🟢 **PASS** — Check succeeded
- 🔴 **FAIL** — Check failed
- 🟡 **SKIP** — Check skipped (tool not installed)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed |

---

## Integration Examples

### Example 1: Coder Agent Plan

```
5. Fix Issues
   - Run final_gate.py to validate implementation
   - If failures:
     * Fix formatting issues (auto-fixed by gate)
     * Fix semantic errors (mypy, bandit findings)
     * Fix convention violations
   - Re-run final_gate.py until PASS
   - Changes auto-staged
```

### Example 2: Fixer Agent Plan

```
3. Validate Fixes
   - Run final_gate.py to ensure no regressions
   - Address any new issues found
   - Re-run until all checks pass
```

### Example 3: CI/CD Pipeline

```yaml
- name: Final Gate Check
  run: python scripts/final_gate.py --check
```

---

## Troubleshooting

### "mypy hung (>30s) - clearing cache"

**Cause:** Incremental cache corrupted (common with large files).

**Auto-fix:** Script clears `.mypy_cache/` and retries with `--no-incremental`.

**Manual fix:**
```bash
rm -rf .mypy_cache/
python scripts/final_gate.py
```

### "semgrep not authenticated"

**Cause:** Semgrep requires login for rule updates.

**Fix:**
```bash
semgrep login
```

**Note:** Check is best-effort; build won't fail.

### "CHANGELOG.md not updated"

**Cause:** Significant code changes without changelog entry.

**Fix:** Add entry to `CHANGELOG.md`:
```markdown
## [Unreleased]

### Added
- New feature X

### Fixed
- Bug in Y
```

### "CHANGELOG.md was changed but its [Unreleased] section was not"

**Cause:** The change staged `CHANGELOG.md` while leaving `## [Unreleased]` byte-identical —
typically a cosmetic edit to an older release section. On a shared tree `[Unreleased]` almost
always holds a sibling's entry, so the older "does it have a real entry" question answered green
regardless of what your change did. Staging the file is not the same as having an entry.

**Fix:** Add your own entry under `## [Unreleased]`, or extend the entry this task already wrote
(a multi-commit task writes its entry once and extends it — that is accepted, no new `###`
heading needed). Fails **open** when the baseline revision cannot be read.

### "opencode.json contains incorrect Kilo-safe list"

**Cause:** Project's opencode.json has wrong instructions.

**Common issues:**
- Contains `.windsurf/rules/*.md` (Cascade-only)
- Contains `AGENTS.md` (Traycer-only)
- Missing `AGENTS-compact.md`
- Wrong order of instructions

**Fix:** Update project's opencode.json:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

**Note:** This check validates the PROJECT's opencode.json, not the global one at `~/.config/kilo/opencode.json`.

### "Symlink integrity failed"

**Cause:** Old project has symlinks to `/opt/fabrik` (pre-March 2026 scaffold).

**Fix:** Run `fabrik fix` to migrate symlinks to copies:
```bash
fabrik fix /opt/your-project
```

Or manually copy:
```bash
rm -f AGENTS.md AGENTS-compact.md opencode.json .windsurfrules  # Remove old symlinks
rm -rf .windsurf/rules .windsurf/workflows                      # Remove old symlinked dirs
mkdir -p .windsurf
cp /opt/fabrik/AGENTS.md ./AGENTS.md
cp /opt/fabrik/AGENTS-compact.md ./AGENTS-compact.md
cp /opt/fabrik/opencode.json ./opencode.json
cp /opt/fabrik/.windsurfrules ./.windsurfrules
cp -r /opt/fabrik/.windsurf/rules/ ./.windsurf/rules/
cp -r /opt/fabrik/.windsurf/workflows/ ./.windsurf/workflows/
```

**Note:** New scaffolds (March 2026+) copy files directly, no symlinks.

### "Command timed out after Xs"

**Cause:** Tool took too long (network issue, large codebase).

**Fix:** Check tool directly:
```bash
# Test specific tool
python -m mypy src/ --config-file=pyproject.toml
python -m bandit -r src/
```

### "No module named X"

**Cause:** Optional tool not installed.

**Fix:** Install missing tool:
```bash
/opt/<project>/.venv/bin/pip install bandit semgrep sqlfluff vulture
```

**Note:** These are best-effort; missing tools are skipped.

---

## Sources of Truth

- `.windsurfrules` — Cascade agent contract: behavior rules, invariants, and audit directives.
- `.windsurf/rules/core/50-code-review.md` — Tiered gate commands and usage for Cascade.
- `scripts/final_gate.py` — Executable tiered implementation (runtime truth).

## See Also

- [AGENTS.md](../../AGENTS.md) — Traycer orchestrator contract
- [KILO_REVIEW_WORKFLOW.md](../archive/KILO_REVIEW_WORKFLOW.md) — Kilo-CLI code review workflow (archived — Kilo CLI retired; reviews run via /fabrik-review)
- [KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md) — Agent discovery, benchmarking, role assignment
- [DOCUMENTATOR_WORKFLOW.md](../archive/DOCUMENTATOR_WORKFLOW.md) — Kilo-era documentation-generation workflow (archived; the live doc updater is `scripts/docs_updater.py`)
- [FABRIK_SCAFFOLD_WORKFLOW.md](FABRIK_SCAFFOLD_WORKFLOW.md) — Project scaffold reference

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/enforcement/check_changelog.py`
- `scripts/enforcement/check_compose_services.py`
- `scripts/enforcement/check_configuration_md.py`
- `scripts/enforcement/check_convergence.py`
- `scripts/enforcement/check_deps_sync.py`
- `scripts/enforcement/check_doc_index.py`
- `scripts/enforcement/check_doc_links.py`
- `scripts/enforcement/check_docker.py`
- `scripts/enforcement/check_docs.py`
- `scripts/enforcement/check_duplicates.py`
- `scripts/enforcement/check_env_contract.py`
- `scripts/enforcement/check_env_example.py`
- `scripts/enforcement/check_env_updates.py`
- `scripts/enforcement/check_health.py`
- `scripts/enforcement/check_index_md.py`
- `scripts/enforcement/check_no_host_ports.py`
- `scripts/enforcement/check_openapi_sync.py`
- `scripts/enforcement/check_opencode_json.py`
- `scripts/enforcement/check_ports.py`
- `scripts/enforcement/check_readme_md.py`
- `scripts/enforcement/check_retired_terms.py`
- `scripts/enforcement/check_review_hygiene.py`
- `scripts/enforcement/check_spec_db_match.py`
- `scripts/enforcement/check_test_coverage.py`
- `scripts/enforcement/check_traefik_labels.py`
- `scripts/enforcement/check_user_guide.py`
- `scripts/enforcement/check_vps_docs.py`
- `scripts/enforcement/check_watchdog.py`
- `scripts/enforcement/validate_conventions.py`
- `scripts/final_gate.py`
<!-- END related-scripts -->
