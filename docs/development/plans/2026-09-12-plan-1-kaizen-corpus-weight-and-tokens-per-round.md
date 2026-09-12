# Kaizen feedback loop — pieces 3 + 4: the corpus-weight ratchet and tokens-per-round

Status: DRAFT
Profile: small
**Owner:** —
Date: 2026-09-12
Spec: `docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md` § D4 (the four-piece table, rows 3 and 4), § Q4, § Q5 canary 4, § Q6, § Constraints 2 and 4, § Reproduce R3/R9
Ruling: **D-224** (the loop is approved) · **D-234** (four pieces; pieces 3 + 4 build now, 1 + 2 after infra's review-family lock releases)
Supersedes: `docs/development/plans/2026-09-11-plan-2-kaizen-tier1-report.md` — a DRAFT never executed, REMOVED in this plan's commit (the convergence gate forbids archiving a DRAFT; its text lives at `git show ad612bc6:docs/development/plans/2026-09-11-plan-2-kaizen-tier1-report.md`); its piece-4 content is Phase B here, verbatim where it was right

⚠️ **CITATION CONVENTION — by SYMBOL, not by line**, except where a line is quoted verbatim in the Constraints Digest (those are pinned to the pack's text, which the grounding gate re-checks). Three sessions and a daily pipeline commit to this tree; every code reference names the function or constant.

---

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"commands, rules, claude.mds and similar governance files kept optimum to have fast, lean, accurate, permanent, resilient commands/skills/rulepacks"* (2026-09-09) | IN | Phase A — the byte ratchet is the "lean" instrument; § D4 row 3 |
| I2 | *"record these into kaizen/feedback … make our commands better and better after each usage"* (2026-09-11) | IN (the proof half) / OUT-OF-SCOPE (the act half) | Phase B is piece 4, the thermometer; pieces 1 + 2 wait on infra's lock — spec § D4 sequencing, named destination |
| I3 | *"/fabrik-plan-after-chat for pieces 3 + 4"* (2026-09-12, the dispatch) | IN | this plan |
| I4 | *"we should not cause data loss"* | IN | Phase A: the check writes ONE file (`.fabrik/corpus-weight-baseline.json`) and only on `--seed`/`--reseed`/a shrink; `--check` never writes; nothing is deleted anywhere — Behavior rows A6, A7 |
| I5 | *"agents must know what will this script do while using it"* | IN | Phase A: `--help` names every path that writes and the exit-code contract; every verdict line says what it measured and against what — row A9 |
| I6 | *"beware siblings are working in the repo do not collide"* | IN | § File Scope: disjoint from all three active locks (verified below); `docs/reference/command-run-protocol.md` deliberately excluded |
| I7 | the spec's own machinery findings for piece 4: `command_feedback_report.py`'s `_TOK` includes cache tokens with no flag; a `test_cmd` fixture row sits in the ledger | IN | Phase B rows B7, B8 |
| I8 | *"should we continue this with fable 5.1 or opus 5?"* | OUT-OF-SCOPE | a session-model question, answered in chat; not a plan item |

Intake: 8 items — 6 IN, 1 split IN/OUT (I2, destination named), 1 OUT-OF-SCOPE (I8), 0 ASK.

## What we already agreed (citations)

- Piece 3 is a BYTE ratchet on governance surfaces, WARN never red, on the proven baseline pattern — spec § D4 four-piece table row 3; § Q4 ("bytes only as the free, CI-native trend signal, never as the enforced ceiling").
- Piece 3 must be correct in every synced repo and budget only what a repo owns — spec § Constraints 2. **CHANGED by grounding (below):** a synced project owns NONE of the surfaces (its `CLAUDE.md` and `.windsurf/rules/` are byte-identical sync copies, overwritten on every hub governance commit), so in a project the check measures nothing and says so; the hub measures five surfaces.
- Q4's re-baselining mode binds: compare against the BASE branch, not only the committed baseline — spec § D4 row 3, § Q4.
- Fire rate before shipping — spec § Q6. **Measured (§ Evidence A2):** rises on 16–21 of the last 30 days per surface. So the WARN fires on the DELTA the committing change adds, and the baseline is the trend record; a warn-on-every-rise-since-baseline would be wallpaper (FIX DIRECTIVE 5).
- Piece 4 is a REPORT, not a kaizen series; `cost_usd` derives nothing; the mass rule's two ordered clauses; the divisor is the TOTAL row count; every figure carries its row count — spec § D4 row 4, § Q2, § Q5 canary 4, § Reproduce R3.
- Tokens per round are over `tok_in`+`tok_out` only — spec § Q2 (`command_tokens_per_round@v1`); the shipped reader's `median_tok` is cache-inclusive (spec § Reproduce R9).
- Pieces 1 + 2 are out of scope (infra's lock owns `assemble_commands.py` and both `CLAUDE.md` files) — spec § D4 sequencing.
- Chat-born rulings minted as **D-240** in this plan's commit: (a) hub-only measurement, (b) WARN on the change's own delta with the baseline as trend, (c) plan-2 superseded by this plan and removed from the tree (its last text at ad612bc6).

## Global Constraints

- Both scripts are stdlib-only and run under the repo's own interpreter (`final_gate` runs `sys.executable`); no new dependency (CLAUDE.md § HARD STOPS: deps files untouched).
- 12-Factor non-negotiables inherited by every phase: logs to **stdout only** (XI) — the check prints, never writes a logfile; config by env vars only, none needed here (III); no daemon, no PID file (VIII); no backing service substituted in tests (X); nothing else applies (no container, no DB, no worker).
- `scripts/enforcement/` and `scripts/final_gate.py` are FLEET-SYNCED: every line must be correct for ~46 repos (CLAUDE.md § HARD STOPS, synced surfaces). Enforcement scripts resolve their root from `__file__`, never the cwd (`check_governance_tables.py::_root`).
- A `warn_only=True` check returns 0 on EVERY path; a non-zero exit hard-fails the gate fleet-wide (`final_gate.py::run_optional_check` docstring; `check_governance_tables.py` module docstring).
- `--check` must reach the new check: only `ratchet_args = ("--check",) if check_only else ()` threads it today (`final_gate.py`, the lint-ratchet registration); a read-only gate run must never write a baseline.
- Shared tree: explicit pathspecs one per line, `--numstat` read in the same invocation, `git reset -q HEAD -- <paths>` after every scoped commit; `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md` are dirty or hot — private-index plumbing for the governance rows; never amend, never stash, never `--force`.
- `Path.rglob`, never git, enumerates surfaces: `scripts/enforcement/` and `.windsurf/` are gitignored in projects (`fabrik_synced_manifest.py::gitignore_block_text`), so `git ls-files` reads as empty there.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | one test per user-observable behaviour, seen RED first | `45-testing-strategy.md:19,21,198` (quoted in the digest) |
| `.windsurf/rules/core/10-python.md` (ACTIVE) | type hints on every signature; `list[str]`/`str \| None` forms; `uv run pytest` | `10-python.md:159-160,230` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | CHANGELOG under `[Unreleased]`; TROUBLESHOOTING on a recurring symptom; trailer block shape | `40-documentation.md:66,81,111` |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | native seats only (pool OFF, D-181); Opus authoritative + Sonnet breadth; never-route set | `62-using-subagents.md:63,65,98` |
| fabrik-lib (`/opt/fabrik-lib/README.md`) | nothing to vendor: no module budgets bytes or ratchets a count (grep `ratchet\|weight\|budget\|byte` → `cost-budget/` is USD caps, `file-cache/` is eviction — neither fits); BUILD fresh. Not a 🆕 candidate: projects own no surface to budget, so it is single-repo by construction | `README.md:28,46` |
| `agents-fabrik.md` § Planning Constraints | solo dev; existing services first; scaffold immutability — no new top-level dirs | `agents-fabrik.md:362-380` |
| `scripts/enforcement/check_lint_ratchet.py` | the ratchet pattern: `ROOT`/`BASELINE` constants, `_read_baseline`, `_write_baseline` (+ `git add`), seed/rise/drop/equal branches, `--check`, `_baseline_is_gitignored`, the version re-seed | `check_lint_ratchet.py:41-42,108-128,153-179,182-244` |
| `scripts/render_doc_script_links.py::ratchet` | the same contract as a `(rc, message)` function | `render_doc_script_links.py:269-296` |
| `scripts/final_gate.py` | `run_optional_check(script, name, *args, module, advisory, warn_only)`; `_diff_base()` resolves `@{upstream}` → `origin/master` → `origin/main`; `ratchet_args` threads `--check` | `final_gate.py:347-354, 1393-1401, 1542-1548, 2204-2222` |
| `scripts/enforcement/check_convergence.py::_head_text` | `git show <ref>:<path>` read shape to generalise for the base-branch sizes | `check_convergence.py:686-696` |
| `scripts/select_rules.py` · `pack_layout_audit.py` | the canonical `.windsurf/rules` walk: `rules_dir = root / ".windsurf" / "rules"` + `sorted(rules_dir.rglob("*.md"))` | `select_rules.py:75-80`, `pack_layout_audit.py:180-185` |
| `scripts/fabrik_synced_manifest.py` | `scripts/enforcement/` synced recursively; `final_gate.py` in `CORE_SCRIPTS`; `.fabrik/*` baselines NOT synced (project-local); `templates/governance/CLAUDE.md` → a project's `CLAUDE.md` byte-identical, overwritten on sync | `fabrik_synced_manifest.py:37-38, 99-105, 125-126, 262, 320-324, 341-362, 474-486` |
| `scripts/command_feedback_report.py` | `build`/`render`/`main` signatures; `_TOK` (cache-inclusive), `_tok_total`, `_num`, `_median`, `_k`; `rounds`/`toks` accessors; the 11-column table | `command_feedback_report.py:103,108,132,151,170,187-189,195,205-206,265-274,281,294-313,340` |
| `tests/test_command_feedback_report.py` · `tests/enforcement/test_check_lint_ratchet.py` | the grader shapes: `_row`/`_write`/`_run` over a tmp ledger; a git-init `repo` fixture running the check as a SUBPROCESS | `test_command_feedback_report.py:16-46,194-214`, `test_check_lint_ratchet.py:22-43,60-97` |
| `specs/services/*.yaml` `shape.*` | none — no service, no DB, no cache, no metrics endpoint | n/a |
| `docs/data-contract.md` · `docs/ui-design.md` | absent in the hub — not a GUI, no fields | n/a |

## Constraints Digest

| # | Rule (verbatim) | Source | Binds |
|---|---|---|---|
| C1 | "**Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:19` | every Behavior row below has a named grader |
| C2 | "**Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:21` | each grader written before its implementation or proven red-on-revert on a copy |
| C3 | "A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) \| Watch it fail first, or neuter the change → prove red → restore → re-run green" | `.windsurf/rules/core/45-testing-strategy.md:198` | the red-on-revert recipe for the exit-code and no-write graders |
| C4 | "Use type hints for all function signatures" | `.windsurf/rules/core/10-python.md:159` | both scripts |
| C5 | "Use `list[str]` not `List[str]`; use `str \| None` not `Optional[str]`" | `.windsurf/rules/core/10-python.md:160` | both scripts |
| C6 | "Source, config, or Docker file changed \| `CHANGELOG.md` entry under `## [Unreleased]`; `INDEX.md` reflects change" | `.windsurf/rules/core/40-documentation.md:66` | Phase C |
| C7 | "Recurring symptom hit \| `docs/TROUBLESHOOTING.md` updated" | `.windsurf/rules/core/40-documentation.md:81` | the WARN line gets a row in § Common Error Messages (Phase A) |
| C8 | "an advisory check that returns 1 on a finding does not warn, it HARD-FAILS every gate in ~46 synced repos the first time it fires" | `scripts/enforcement/check_governance_tables.py:35-36` | `main()` returns 0 on every path; `--strict` alone returns 1 |
| C9 | "Dispatch policy — NATIVE for every fan-out while the pool is OFF (D-181, 2026-09-07); BINDING" | `.windsurf/rules/core/62-using-subagents.md:63` | every review seat in this plan is native |

Selections that cite no row: the baseline file name and JSON shape (`unconstrained` — mirrors `lint-baseline.json`); the five hub surfaces (`unconstrained` — the spec's list plus `templates/governance/CLAUDE.md` and `commands/_fragments/`, which the fleet reads and the assembler renders).

---

## Phase A — piece 3: `check_corpus_weight.py`, its graders, and its gate registration

**Interfaces — Produces.** `scripts/enforcement/check_corpus_weight.py` with: `SURFACES: tuple[str, ...] = ("CLAUDE.md", "templates/governance/CLAUDE.md", "commands/_sources", "commands/_fragments", ".windsurf/rules")`; `BASELINE = ROOT / ".fabrik" / "corpus-weight-baseline.json"`; `owned_surfaces(root: Path) -> list[str]` (empty when `root/.fabrik/synced.lock` exists — a synced project; otherwise every SURFACES entry that exists); `measure(root: Path, surface: str) -> int` (a file's bytes, or Σ bytes of `*.md` under a directory via `Path.rglob`); `base_sizes(root: Path, ref: str) -> dict[str, int] | None` (per-surface Σ blob sizes from `git ls-tree -r -l <ref> -- <surface>`, `.md` only under directories; `None` when the ref does not resolve); `diff_base(root: Path) -> str | None` (the `_diff_base` ladder: `@{upstream}` → `origin/master` → `origin/main`); `read_baseline() -> dict[str, int] | None`; `write_baseline(sizes: dict[str, int], ref: str | None) -> None` (JSON `{"surfaces": {...}, "ref": ..., "seeded_at": ...}` + best-effort `git add`); `verdict(...)` returning `(rc_strict: int, lines: list[str])`; `main(argv) -> int` with flags `--check` (never writes), `--seed` (write the baseline only when none exists), `--reseed` (overwrite the baseline at today's sizes — the D-row-citing commit's tool), `--strict` (exit 1 on any rise — tests and a future promotion; never passed by the gate), `--json`. **Exit code is 0 on every path without `--strict`.** **Gate registration is NOT this plan's edit:** `scripts/final_gate.py` and `docs/workflows/FINAL_GATE_WORKFLOW.md` are owned by the active lock `2026-09-09-plan-1-review-convergence-redesign` (34 paths; the second also by `2026-09-11-plan-1-review-family-pass3`). The exact block — `cw_args = ("--check",) if check_only else ()` → `run_optional_check("scripts/enforcement/check_corpus_weight.py", "Corpus Weight (byte ratchet — advisory)", *cw_args, warn_only=True)` beside the lint ratchet, its workflow-doc bullet, and its grader — is REQUESTED from infra (the lock-holder and the `scripts/enforcement/` beat) by mail `01M2AJKKVGH8Q2PK51CM2GJ5FC` (sent 2026-09-12, ack required); until it lands the check runs standalone (`python3 scripts/enforcement/check_corpus_weight.py`) and the receipt records the mail id.

**Consumes.** The git remote (`origin/master` on the hub); `--check` from the gate once registered; nothing else.

**What the check prints (the contract agents read, I5).** One line per owned surface — `corpus-weight: <surface> <bytes> B · baseline <b> (<±delta>) · base <ref> <±delta>` — then ONE of: `corpus-weight: OK — no owned surface grew` · `⚠ corpus-weight: this change ADDS <n> B to <surface> (base <ref> → tree); the baseline is <b> B — a governance surface grew; the review that accepts it cites the D-row naming what the growth retires` (per grown surface) · `corpus-weight: no baseline — run --seed at a corpus state you accept` · `corpus-weight: synced project — every governance surface here is a hub copy; nothing to budget` · `⚠ corpus-weight: .fabrik/corpus-weight-baseline.json is gitignored here — the ratchet is local-only` (the lint ratchet's CI-parity degradation, restated). A shrink on a plain run tightens the baseline and says `ratcheted DOWN <b> → <bytes>` for that surface.

Steps, in order:
1. Toolchain preflight (WSL dev): `.venv/bin/python -m ruff --version` (0.14.10) and `.venv/bin/python -m pytest --version` (9.0.2) — both present today; the phase gate uses them.
2. Write `tests/enforcement/test_check_corpus_weight.py` FIRST, copying the `repo` fixture shape of `test_check_lint_ratchet.py` (git init + user config + the check copied under `scripts/enforcement/`), adding: a `CLAUDE.md` and `.windsurf/rules/a.md` in the fixture, a bare remote (`git init --bare` + `git remote add origin` + a first commit pushed) for the base-branch rows, and a `synced.lock` variant. Run the file: every grader RED (module absent) — record the collected count and the red in the run record.
3. Write `scripts/enforcement/check_corpus_weight.py` with the header `# AFTER-EDIT: scripts/final_gate.py, docs/TROUBLESHOOTING.md, tests/enforcement/test_check_corpus_weight.py` and a module docstring stating: what it measures, the five surfaces, the ownership rule, the exit-code contract (0 always; `--strict` 1 on a rise), the three writes (`--seed`, `--reseed`, a shrink on a plain run) and that `--check` writes nothing. Reuse the `.windsurf/rules` walk (`rules_dir.rglob("*.md")`), the `ROOT = Path(__file__).resolve().parents[2]` resolution and the `_baseline_is_gitignored` probe from the lint ratchet; the `git ls-tree -r -l` read for base sizes.
4. Run the graders GREEN; then the red-on-revert proof for A5 (exit code) and A6 (`--check` never writes): copy the script to scratch, neuter the branch, run, watch red, restore from the copy (the copy is written BEFORE the mutation), re-run green.
5. Run the check standalone on the hub — `python3 scripts/enforcement/check_corpus_weight.py --check` — and confirm the five surface lines, the no-baseline line, exit 0, and that `.fabrik/corpus-weight-baseline.json` does NOT exist afterwards (the `--check` no-write contract on the real repo). The gate registration is infra's (Interfaces above): the mail sent at plan time carries the block; if it has landed by now, also run `python3 scripts/final_gate.py --json --check` and confirm the row sits under `advisory`, not `blocking`.
6. `docs/TROUBLESHOOTING.md` § Common Error Messages: one row — `⚠ corpus-weight: this change ADDS N B to <surface>` · cause: the commit grows a governance surface the hub owns · solution: cut what the growth retires, or raise the baseline with `--reseed` in a commit citing the D-row that names the retirement. (The `docs/workflows/FINAL_GATE_WORKFLOW.md` check bullet rides infra's registration mail — that doc is lock-owned.)
7. Do NOT seed the hub baseline in this phase: `.fabrik/plan-locks/2026-09-11-plan-1-review-family-pass3.json` is `status: active` and owns the corpus mid-edit; a baseline seeded now freezes numbers infra is changing (spec § D4 sequencing). The seed is Phase C step 6, conditioned on that lock's status, with the fallback named there.
8. Closing sequence: (1) `uv run pytest tests/enforcement/test_check_corpus_weight.py tests/enforcement/test_check_lint_ratchet.py -q` green; (2) `python scripts/enforcement/check_doc_sync.py` + the TROUBLESHOOTING row above; (3) **`/fabrik-review-scoped`** on this phase's diff (Profile: small — the ONE heavy `/fabrik-review` runs at Finish over the whole-plan diff), run to a delta round that confirms zero; fix what it finds in-run; (4) commit `scripts/enforcement/check_corpus_weight.py`, `tests/enforcement/test_check_corpus_weight.py`, `docs/TROUBLESHOOTING.md` by explicit pathspec with trailers (`Agent-Phase: A`), then `git reset -q HEAD -- <those paths>`.

### Behavior Contract (Phase A)

- **Given** a repo with no baseline, **When** the check runs without flags, **Then** it prints the no-baseline line, exits 0 and writes nothing (`test_no_baseline_is_a_zero_exit_and_writes_nothing`).
- **Given** `--seed` on a repo with no baseline, **When** run, **Then** `.fabrik/corpus-weight-baseline.json` holds one integer per owned surface, a `ref` and `seeded_at`, and is staged (`test_seed_writes_one_number_per_owned_surface_and_stages_it`).
- **Given** a baseline and a surface that grew, **When** run without flags, **Then** the ⚠ line names the surface, the bytes added and the baseline, the exit code is 0, and the baseline is unchanged (`test_a_rise_warns_names_the_surface_and_never_reds`).
- **Given** the same rise, **When** run with `--strict`, **Then** exit 1 (`test_strict_reds_on_a_rise`) — the future-promotion and regression hook, never passed by the gate.
- **Given** any state (no baseline · rise · shrink · equal · synced project · gitignored baseline), **When** run without `--strict`, **Then** exit is 0 — one grader loops every state (`test_exit_is_zero_on_every_path_without_strict`; red-on-revert proven).
- **Given** `--check`, **When** run over a shrink or with no baseline, **Then** no file under `.fabrik/` is created or modified (`test_check_never_writes`; red-on-revert proven).
- **Given** a baseline and a surface that shrank, **When** run without flags, **Then** the baseline tightens to the new size and says so; with `--check` it only reports (`test_a_shrink_tightens_the_baseline_except_under_check`).
- **Given** a repo carrying `.fabrik/synced.lock`, **When** run, **Then** it prints the synced-project line, exits 0, and no baseline is written even with `--seed` (`test_a_synced_project_owns_nothing_and_seeds_nothing`).
- **Given** `--help`, **When** run, **Then** the text names every writing path (`--seed`, `--reseed`, a shrink on a plain run), that `--check` writes nothing, and the exit-code contract (`test_help_states_what_it_writes_and_when_it_exits_nonzero`).
- **Given** a remote base exists and the tree grew a surface past the base, **When** run, **Then** the ⚠ line carries the base ref and the delta vs base; with no resolvable base the base cell reads `—` (`test_base_branch_delta_is_reported_and_absent_base_is_a_dash`).
- **Given** a directory surface holding a `.md` and a `.yaml`, **When** measured on the tree AND at the base ref, **Then** only the `.md` bytes count on both sides (`test_directory_surfaces_count_md_bytes_only_on_both_sides`).

### Evidence (Phase A)

`scripts/enforcement/check_lint_ratchet.py::main` — seed (`return 0`), rise (`return 1`, the only non-zero path), drop (writes unless `--check`), equal; `_write_baseline` stages the file; `_baseline_is_gitignored` degrades loudly. `scripts/final_gate.py::run_optional_check` — `warn_only` "has no failing exit path by contract"; `:1393` `ratchet_args = ("--check",) if check_only else ()`.

```
$ replay — one commit per day, last 30 days, five hub surfaces (bytes at that commit; + = rose vs the previous day)
day         CLAUDE.md  templates/governance/CLAUDE.md  commands/_sources  commands/_fragments  .windsurf/rules
2026-08-13     36,535      33,536                        542,066             28,688           1,077,977
2026-08-28     49,029+     46,390+                       659,714+            40,945+          1,109,932+
2026-09-05     73,114+     68,138+                       967,261+            83,826+          1,228,239+
2026-09-12     89,856+     82,476+                     1,047,779+           115,798+          1,251,876
days=30 rises per surface (would-WARN days): CLAUDE.md=19, templates/governance/CLAUDE.md=21, commands/_sources=21, commands/_fragments=16, .windsurf/rules=19
```
(the full 30-row table is in the run's scratchpad and reproduces from `git log --since='30 days ago' --first-parent master` + `git ls-tree -r -l <sha> -- <surface>`). A ratchet that WARNs whenever a surface sits above its baseline would have spoken on two days in three; the WARN is therefore on the change's own delta (tree vs base) and the baseline is the trend line — Q6's narrowing, recorded as D-240.

```
$ base-branch sizes at origin/master 2234c830 vs the working tree (the second gate's inputs)
CLAUDE.md                        base=     89856  tree=     89856
templates/governance/CLAUDE.md   base=     82476  tree=     82476
commands/_sources                base=   1047779  tree=   1047899   ← sibling WIP in the tree: +120 B is a live example of the delta the WARN names
commands/_fragments              base=    115798  tree=    115798
.windsurf/rules                  base=   1319036  tree=   1251876   ← base counts every blob, tree counts .md only: the measurement must apply the same .md filter to both sides (row A11)
```

Fleet: 49 repos under `/opt` carry a root `CLAUDE.md`; the three sampled (`youtube`, `transdoc`, `web-ecommerce-factory`) hold a 433-line `CLAUDE.md` identical to `templates/governance/CLAUDE.md` and the same 56 rule packs; `commands/_sources/` exists only under `/opt/fabrik` (36 files, 0 elsewhere); `scripts/enforcement/` is gitignored in projects (`/opt/youtube/.gitignore:180`); `.fabrik/` is ignored wholesale in none of the three (`wpf` is the known exception, retired).

## Phase B — piece 4: tokens-per-round behind the mass rule

**Interfaces — Produces.** In `scripts/command_feedback_report.py`: `_io_total(r: dict) -> int | None` (Σ `tok_in`+`tok_out` only — the divergence from `_tok_total`'s cache-inclusive sum is stated in its docstring); per-command keys `tok_per_round: float | None`, `tok_per_round_reason: str | None` (`"zero token mass"` · `"mass ratio 0.3038 < 2/3"` · `None` when published), `mass_ratio: float | None`, `rows_with_numerator: int`, `rows_with_denominator: int`, `rows_total: int`; a top-level `conventions` dict in `--json` (`{"mean_divisor": "total rows of the command", "tok_per_round": "tok_in+tok_out over rounds-carrying rows only; cache excluded", "median_tok": "cache-inclusive"}`); in `render`: a 12th column `tok/round (q/T · num/den)` and one population sentence stating the two conventions. **Consumes.** `build`'s existing `rounds`/`toks` accessors and `_num`; nothing new from Phase A.

Steps, in order:
1. Re-read `build` whole before writing (the old plan's own self-audit: the delta framing rests on two greps returning 0 — `per_round`/`mass` — re-run them: still 0 at 358 lines).
2. Write the graders FIRST in `tests/test_command_feedback_report.py` using `_row`/`_write`/`_run` over a tmp ledger; a CONSTRUCTED zero-mass fixture (never the live `test_cmd` row — a fixture in a production ledger passes for the wrong reason). Run: every new grader RED; record the count.
3. Implement clause 1 (T == 0 → `—` + reason, BEFORE any division), clause 2 (q/T < ⅔ → `—` + the measured ratio), then the quantity Σ(tok_in+tok_out) ÷ Σ rounds over rows carrying BOTH (a `rounds == 0` row contributes to neither side); emit the six keys; add the column, the conventions sentence and the `--json` `conventions` dict.
4. Graders GREEN; red-on-revert for B1 (clause order) and B6 (`cost_usd` absent from every derivation — re-introducing it must fail the suite).
5. `docs/reference/command-run-protocol.md` is coupled by the script's `# AFTER-EDIT:` header but owned by two active sibling locks (`2026-09-09-plan-1-review-convergence-redesign`, `2026-09-11-plan-1-review-family-pass3`): do NOT edit it. Accept `check_script_headers.py`'s WARN with a named owner: mail the lock-holder (infra) the two sentences the doc's report paragraph needs (`tok/round`, the mass rule, the conventions) — the mail id goes in the commit body.
6. Closing sequence: (1) `uv run pytest tests/test_command_feedback_report.py -q` green; (2) `check_doc_sync.py` + the mail above; (3) **`/fabrik-review-scoped`** on this phase's diff to a zero-confirmed delta round, fixes in-run; (4) commit the script and its tests by pathspec (`Agent-Phase: B`), reset the index for those paths.

### Behavior Contract (Phase B)

- **Given** a command whose total token mass `T` is 0, **When** the report builds, **Then** `tok_per_round` renders `—` with the reason "zero token mass" and no ratio is evaluated — clause 1 runs BEFORE clause 2 (`test_mass_rule_clause1_precedes_the_ratio`; red-on-revert proven).
- **Given** a command whose rounds-carrying, token-carrying rows hold < ⅔ of its token mass, **When** the report builds, **Then** `tok_per_round` renders `—` with its reason and the measured ratio, never a number (`test_mass_rule_silences_below_two_thirds`).
- **Given** a command at or above ⅔, **When** the report builds, **Then** it emits Σ(tok_in+tok_out) ÷ Σ rounds over rounds-carrying rows only, plus `rows_with_numerator` and `rows_with_denominator` (`test_tok_per_round_excludes_zero_round_rows_from_both_sides`).
- **Given** any per-command mean the report emits, **When** rendered or dumped, **Then** the divisor is the command's TOTAL row count and both outputs say so (`test_mean_divisor_is_total_rows_and_is_stated`).
- **Given** any figure in the rendered report or its `--json`, **When** emitted, **Then** it carries the row count it was computed at (`test_every_figure_carries_its_row_count`).
- **Given** `cost_usd`, **When** any axis is derived, **Then** it is absent from the derivation (`test_cost_usd_is_absent_from_every_derivation`; proven by mutation).
- **Given** a row with cache tokens, **When** tokens-per-round is computed, **Then** only `tok_in`+`tok_out` enter it while `median_tok` stays cache-inclusive, and the population line states both conventions (`test_tok_per_round_excludes_cache_and_the_report_says_so`).
- **Given** exactly ⅔, **When** the report builds, **Then** it publishes (`≥`, not `>`) (`test_two_thirds_exactly_publishes`).

### Evidence (Phase B)

`scripts/command_feedback_report.py:103` `_TOK = ("tok_in", "tok_out", "tok_cache_read", "tok_cache_create")`; `:132` `_tok_total` sums all four; `:170` `rounds = [...]`, `:195` `toks = [...]`; `:294-297` the 11-column header; `:265-274` the eight top-level keys. `grep -n 'tok_in' scripts/command_feedback_report.py` → only `:103` and `:197`: no cache-excluding helper exists.

```
$ mass-rule subjects at 126 ledger rows (Σ tok_in+tok_out; q = the mass on rows carrying both sides)
  fabrik-execute-plan        n= 12 T=   5,981,250  — (q/T=0.3038)
  fabrik-plan-after-chat     n=  7 T=   1,297,118  — (q/T=0.1127)
  fabrik-spec                n=  7 T=   1,265,204  — (q/T=0.5250)
  fabrik-plan-review         n=  9 T=   2,029,212  29,690 tok/round (q/T=0.9364, num rows=8, den rows=7)
  fabrik-review              n= 29 T=   9,366,501  38,633 tok/round (q/T=0.9982, num rows=25, den rows=24)
  test_cmd                   n=  1 T=           0  — (T=0)
rows=126 commands=14 publish=10 silenced=3 undefined=1
```
The gap the spec relies on still holds at 126 rows: every command is ≤ 0.5250 or ≥ 0.9364; ⅔ sits in an empty band.

## Phase C — Finish

1. Full suites: `uv run pytest tests/test_command_feedback_report.py tests/enforcement/test_check_corpus_weight.py tests/enforcement/test_check_lint_ratchet.py -q` green; `uv run ruff check scripts/enforcement/check_corpus_weight.py scripts/command_feedback_report.py tests/enforcement/test_check_corpus_weight.py tests/test_command_feedback_report.py` clean.
2. `python3 scripts/final_gate.py --json --check` → `"status": "success"`, read `skipped_checks` and the `advisory` list (the new row is there only once infra's registration has landed — record which); `python3 scripts/enforcement/check_convergence.py` — green is necessary, not sufficient; the Evidence above is the proof.
3. The ONE heavy `/fabrik-review` over the whole-plan diff (D7 floor: `dispatch_headroom.py --units 3 --risky 1` — units: the check, the report, the gate registration; Opus on the fleet-synced units, Sonnet breadth, one Haiku mechanical seat on the exit-code/no-write class; stamped with `dispatch --seats <n>` first), its receipt at `docs/development/reviews/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round-review.md` with the verbatim gate embed and a per-phase verdict; fixes in-run.
4. `/fabrik-docs-review` over the docs this plan touched (`docs/TROUBLESHOOTING.md`, the CHANGELOG entries) — `command-run-protocol.md` stays with its lock-holders (Phase B step 5).
5. Governance rows by private-index plumbing (HEAD + mine): `CHANGELOG.md` one `### Added — Corpus-weight ratchet + tokens-per-round (2026-09-12)` entry; `INDEX.md` rows for the new script and test; `docs/DECISIONS.md` D-240 (minted at the plan's own commit, not here); `docs/development/PLANS.md` regenerated by `python scripts/docs_updater.py --sync`.
6. The hub baseline: read `.fabrik/plan-locks/2026-09-11-plan-1-review-family-pass3.json`. If `status` is not `active`: `python3 scripts/enforcement/check_corpus_weight.py --seed`, commit `.fabrik/corpus-weight-baseline.json` with the receipt. If still `active`: leave the hub unseeded — the check prints its no-baseline line at every gate (exit 0) until the first session after the lock releases runs `--seed`; write that sentence into the receipt's residuals and into `docs/STRATEGIC_BACKLOG.md` as the named destination. Either branch is self-service; neither asks.
7. The cron line for `command_feedback_report.py` is NOT installed (crontab writes are classifier-blocked); the receipt hands the operator the line and records that the report is unscheduled until they run it.
8. Status → EXECUTED; the plan moves to `docs/development/plans/archived/`; the lock releases; commit + push by pathspec; scratch sweep.

---

## Behavior Contract

The roll-up is the union of the Phase A and Phase B rows above (11 + 8 = 19 graders), each named, each seen RED first. Test lines budgeted ≤ ~1.5× the code diff (~290 code lines → ≤ ~435 test lines).

## File Scope (owned paths)

- scripts/enforcement/check_corpus_weight.py
- tests/enforcement/test_check_corpus_weight.py
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
- docs/TROUBLESHOOTING.md
- .fabrik/corpus-weight-baseline.json
- docs/development/reviews/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round-review.md
- .fabrik/plan-locks/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.json

Governance files (`CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/FEATURES.md`, `docs/LESSONS_LEARNT.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`) stay OUT by the spine grammar. **Collision check, executed 2026-09-12 over the three active locks** (`2026-09-05-plan-1-windowed-cost-sidecar`, `2026-09-09-plan-1-review-convergence-redesign`, `2026-09-11-plan-1-review-family-pass3`): each of the eight paths above matched 0 active locks (a script over every lock's `owned_paths`, exact or directory-prefix). Two paths this plan WOULD have wanted are owned and therefore excluded: `scripts/final_gate.py` + `docs/workflows/FINAL_GATE_WORKFLOW.md` (the 2026-09-09 lock; the registration is infra's by mail — Phase A Interfaces) and `docs/reference/command-run-protocol.md` (two locks; Phase B step 5).

## Coverage Checklist

```
$ python scripts/review_rubric.py --changed scripts/enforcement/check_corpus_weight.py scripts/command_feedback_report.py tests/test_command_feedback_report.py tests/enforcement/test_check_corpus_weight.py
```

| Class | How this plan covers it |
|---|---|
| Fail direction | The check exits 0 on every path (one grader loops the states); `--strict` is the only red and the gate never passes it; every absence in the report renders `—` with its reason. |
| Boundary | `T = 0` (a constructed fixture); exactly ⅔ publishes; `rounds == 0` rows excluded from both sides; a directory surface counts `.md` only on BOTH the tree and the base side; no resolvable base → `—`. |
| Bounded search / denominator | Every report figure carries its row count; the conventions are stated in text and `--json`; the 30-day replay states its bound (one commit per day, first-parent). |
| Fleet blast radius | `scripts/enforcement/` ships to ~46 repos: a synced project owns nothing and the check says so; `Path.rglob`, never git, enumerates; always-0 exit, and the registration infra lands is `warn_only=True` (the mailed block). |
| Behaviour without a test | 20 named graders, each seen RED first; two red-on-revert proofs per phase named in the steps. |
| Cost | Two stdlib reads (a byte walk over five paths; a 126-row JSONL); no network, no LLM, no new I/O beyond one JSON file written on `--seed`/`--reseed`/a shrink. |
| Recurrence: stale figures | The ledger grew 102 → 126 during the design; stamps are the mitigation and a grader enforces them. |
| Recurrence: fix residue | If the review's confirmed count stops falling and its findings sit inside the previous round's fix diff, change WHO writes the fixes (`docs/LESSONS_LEARNT.md` § "The finder and the fixer must not be the same agent"). |

## Self-audit — where this plan could be wrong

- **The ownership rule is stricter than the spec's Constraint 2 wording** ("budgets the surfaces a repo HAS"). Grounding showed a project HAS the surfaces but does not OWN them — sync overwrites them on every hub governance commit. The plan follows the grounding; the spec sentence is owed a correction on its next non-delta pass (recorded in the spec's own § BLOCKED residue by this plan's commit message, and D-240).
- **The WARN-on-delta narrowing rests on the 30-day replay's bound**: one commit per day, first-parent. A per-commit replay could show a different rate; the shape (16–21 of 30 days) makes the conclusion robust to that bound, and Q6 makes the narrowing a recorded outcome either way.
- **Coverage (a):** I1 → Phase A; I2 (proof half) → Phase B; I3 → this file; I4 → rows A5–A7 and the `--check` gate run; I5 → row A9; I6 → File Scope; I7 → rows B7 and the `test_cmd` fixture rule. No gap found.
- **Cross-phase signature consistency (b):** Phase B consumes nothing from Phase A; Phase C consumes `check_corpus_weight.py --seed` (Phase A's flag) and the receipt path named in File Scope. Names match.
- **The `.windsurf/rules` base-vs-tree asymmetry (67,160 B)** is the `.yaml` files the tree walk excludes and `ls-tree` includes — row A11 pins the same filter on both sides; a reviewer who reads the raw numbers without that row will see a phantom shrink.
- **Fixed point?** Not claimed here. `/fabrik-plan-review` converges it; the review's own failure mode is named in the Coverage Checklist.

## Residual unknowns

- **Resolved:** whether projects should measure anything (no — grounded); whether the WARN must be delta-based (yes — measured); the base ref (the gate's own ladder); the `--check` threading (mirrors `ratchet_args`).
- **Still open, with its step:** when the hub baseline is seeded — Phase C step 6 (conditioned on infra's lock, both branches self-service). The gate registration + its grader + the workflow-doc bullet — infra's, requested by mail at plan time (id in § What we already agreed once sent); the check runs standalone until then. The `command-run-protocol.md` paragraph — Phase B step 5 (mailed to the lock-holder). The cron line — Phase C step 7 (the operator installs it).
