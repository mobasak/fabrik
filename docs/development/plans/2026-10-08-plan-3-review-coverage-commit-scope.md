# Plan — the review-coverage gate grades committed-but-unintegrated reviews (W-f847a317)

Status: DRAFT
Profile: small
**Owner:** —
**Surface:** `git rev-parse HEAD` = d897964c0 at authoring; `scripts/enforcement/check_review_coverage.py` 3286 lines, `scripts/final_gate.py` 3504 lines

Spec: `docs/superpowers/specs/2026-10-08-review-coverage-commit-scope-design.md` (DRAFT at f0e85a0bd, merged to master
as b8170e73a; `Size: small`, `Profile: delta` — `/fabrik-plan-review` grades its sections together with this plan and
flips both). Source: tryton-crm mail 01M3YD067C → W-23b86f9e's `/fabrik-task` UPGRADE (`tradeoffs`) → work item
W-f847a317. Estimated diff: ≈170 code lines in 2 code files, tests excluded — in `check_review_coverage.py`:
`integration_base` ≈30, `_unintegrated_md` with its attribution and NOTE ≈45, the `-z` rewrite of `_changed_md` ≈20,
`_grade`'s `live` parameter ≈3, `--base` and the `main()` wiring ≈35, docstring ≈10 (sum 143); in `final_gate.py`:
`_integration_base` ≈20 and the call site ≈5 (sum 25). Tests ≈260 lines in one new file.

## What this plan is

Three inline phases the orchestrator codes itself in the worktree; no coder is dispatched:

- **A — the checker**: `--base`, the integration-base resolver, the unintegrated scan with its attribution, `-z`
  porcelain, mega `live=False`, the joined blocking set and the two-source denominator (spec § The delta 1-6), with
  their graders.
- **B — the gate**: `final_gate.py` resolves the same base and passes `--base`; a parity grader pins the two resolvers
  together; the docs.
- **C — blast radius and Finish**: the fleet measurement before merge, the whole-plan `/fabrik-review`, the gate.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (8 IN, 3 OUT-OF-SCOPE) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"(1) check_review_coverage.py gains --base … (2) _changed_md via porcelain -z … (3) final_gate.py passes --base"* (the brief's three pieces) | IN | A: (1), (2) · B: (3) |
| I4 | *"graders per the spec's Validation list"* | IN | A step 1 and 3 (G1–G9), B step 1 (G10) |
| I5 | *"The plan-review flips spec+plan to CONVERGED and holds the approval gate (answered by the Opus + Fable panel, D-613)"* | IN | `/fabrik-plan-review` at Phase 5 of this command |
| I6 | Grounding finding (this run, Evidence Phase A): in 5 of the 13 /opt repos that carry a reviews dir — tryton-crm, the reporter, among them — the main checkout's branch is `mobasak/<repo>` with no `origin/master` or `origin/main`, so the spec's base order (linked-worktree base → origin/master → origin/main) resolves NOTHING in their main checkouts and the bypass stays open exactly where it was reported | IN — the base order is amended: a LINKED worktree uses the main checkout's branch, else origin/master, else origin/main, and never its own upstream (the push-first cobra stays closed); the MAIN checkout uses its branch's upstream, else origin/master, else origin/main (pushing the main checkout's branch IS integration, so its upstream is the integration ref) | Phase A `integration_base`; the spec's § The delta 1, § Rejected alternatives (upstream row) and R3 amended in this plan's `/fabrik-plan-review` |

## What we already agreed (citations, not restatement)

- Goal, personas, lifecycle: `spec § Goal`, `spec § Personas`, `spec § Lifecycle`; why: `spec § Why this exists`.
- Measured behaviour: `spec § What exists today`; external facts G1–G6: `spec § Grounding`.
- The delta 1-6: `spec § The delta`; cost: `spec § Cost`; validation: `spec § Validation`.
- Chosen approach (B), integration-base range over non-merge commits (judge panel 3-0): `spec § Decisions taken`;
  rejected seven: `spec § Rejected alternatives`. The approval row is minted by `/fabrik-plan-review` at its gate (a
  `Size: small` spec is approved there, not here).
- Residual unknowns R1–R3: `spec § Residual unknowns` — R3 is measured by this run (Evidence, Phase A) and changes the
  base order (I6).

## Global Constraints (every phase inherits these)

- **Fleet-synced surface**: both files are under the governance-sync trigger (`scripts/enforcement/`,
  `scripts/final_gate.py`); a merge distributes them to every project. They ship together, so a project never runs a
  `final_gate.py` that passes `--base` against a checker that refuses it.
- **Stdlib only**, no new import (`subprocess`, `os`, `pathlib` are already imported,
  `scripts/enforcement/check_review_coverage.py:29-37`); no dependency file is touched (`core/10-python.md:30`).
- **Never a traceback from git**: every new `git` call is `subprocess.run(..., capture_output=True)` with its rc read;
  `FileNotFoundError` and a non-zero rc both degrade to today's porcelain-only scope plus one NOTE printed AFTER the ⚠
  block (`check_review_coverage.py:3247-3251` — the emitter protocol: the ⚠ header must speak first).
- **The explicit-path mode is untouched**: `main()`'s `args.paths` branch (`:3201-3222`), which the hub's pre-commit hook
  `review-coverage-staged` uses (`.pre-commit-config.yaml:144`), never reads `--base` and never scans the range.
- **No double reporting**: a path in the blocking set is in the advisory scan's skip set unless it is
  `Status: IN-PROGRESS` (`_in_progress`, `:465`), so an unintegrated IN-PROGRESS receipt keeps its standing advisory and
  every other file is reported by exactly one of the two.
- **The base never reads a linked worktree's own upstream** — the push-first cobra (`spec § Rejected alternatives`):
  pushing a worktree branch to its own remote must not take its reviews out of scope before they are merged.
- **12-Factor on this surface**: a CLI check, not a service — III one new flag, no env knob; XI stdout only; the rest
  not engaged.
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:20`, `:22`); every grader builds a real git
  fixture in `tmp_path` (a bare `origin`, a main checkout, and where named a `git worktree add` linked worktree) and runs
  the checker as a subprocess with `--root`, the pattern of `tests/enforcement/test_review_coverage_catchup.py:47-60`;
  assertions on exit codes and the named paths in stdout, never on prose beyond the path and the NOTE token. Red-on-
  revert runs in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never run `uv` or `pip`; a seat runs
  Python as `.venv/bin/python …` with `PYTHONPATH=<worktree>/src`; seat scratch paths are absolute.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats, stamped with `command_run.py dispatch`), not handing on until its closing pass confirms
  zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku finder per
  slice (D-344), the orchestrator executing every refutation. Within a phase the steps are sequential.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | no deps-file edit | `core/10-python.md:30` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — the new test file) | one test per behaviour; watched-fail-first | `core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — FINAL_GATE_WORKFLOW.md) | Doc Sync in the same change; no skipped heading levels | `core/40-documentation.md:240` |
| `docs/DECISIONS.md` D-442 | a linked worktree's base is the main checkout's branch | `scripts/final_gate.py:3409-3431` |
| `fabrik-lib` | none covers git range scoping — BUILD in place | `spec § Grounding`, the fabrik-lib verdict |
| `scripts/sysadmin/liveness_audit.py` | asserts the check fires on a bad review in a no-remote fixture repo | `scripts/sysadmin/liveness_audit.py:1436-1442` |
| `specs/services/*.yaml` `shape:` | not engaged: no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | .windsurf/rules/core/10-python.md:30 | Deps |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | .windsurf/rules/core/40-documentation.md:240 | Docs |

## Phase A — the checker: --base, the unintegrated scan, -z porcelain

Appetite: 120

**Interfaces — Produces** (all in `scripts/enforcement/check_review_coverage.py`; `spec § The delta` 1-6, amended by I6):
- `integration_base(root: Path) -> str` — the ref the range excludes, "" when none resolves. Linked worktree (the
  absolute `git rev-parse --git-dir` differs from `--git-common-dir`): the main checkout's branch
  (`git --git-dir <common> symbolic-ref --quiet --short HEAD`) when it differs from HEAD's branch, else
  `origin/master`, else `origin/main` — never this branch's own upstream. Main checkout: `@{upstream}`
  (`git rev-parse --abbrev-ref --symbolic-full-name @{upstream}`), else `origin/master`, else `origin/main`. Each
  candidate is accepted only when `git rev-parse --verify --quiet <ref>` exits 0. Any git error answers "".
- `_unintegrated_md(root: Path, prefix: str, base: str) -> tuple[list[Path], dict[Path, str], list[str]]` — returns
  (paths, attribution, notes). `base == ""` → `([], {}, [])`. Runs `git log -z --no-merges --name-only --format=
  --diff-filter=d HEAD --not <base> [origin/<base>] -- <prefix>`, the `origin/<base>` term added only when `<base>` has
  no `/` and `origin/<base>` verifies (it excludes commits a worktree merged from a remote ahead of the local
  integration branch). Splits on NUL, deduplicates, applies `_changed_md`'s filter (`.md`, not `-archive.md`, not under
  `archived/`, a file on disk). Attribution per path: `git log -1 --format=%h%x00%(trailers:key=Agent-Name,valueonly)%x00%an
  HEAD --not <same refs> -- <path>` → `"<sha> (<Agent-Name or author>)"`. rc ≠ 0 or `FileNotFoundError` →
  `([], {}, ["NOTE: unintegrated review scan skipped — git log rc <n> against <base> (porcelain scope only)"])`.
- `_changed_md(root, prefix)` keeps its signature and return; it reads `git status --porcelain -z
  --untracked-files=all -- <prefix>`, splits on NUL, takes the path from `entry[3:]`, and for an `R` or `C` status in
  either column consumes the NEXT field as the rename source and discards it (under `-z` the destination comes first —
  Evidence, Phase A). No quote stripping remains. The docstring's stale "Returns (paths, notes)" becomes the three-tuple.
- `_grade(p, root, live: bool = True)` — passes `live` to `check_mega_validation` (`:3163`); every existing caller is
  unchanged.
- `main()`: `ap.add_argument("--base", default=None, help=…)`. No-path branch only: `base = args.base if args.base is
  not None else integration_base(root)`; `unint, who, unint_notes = _unintegrated_md(root, REVIEWS_DIR, base)`. The
  blocking set is `changed` (plus the running-record receipts, `:3226-3229`) followed by every `unint` path not already
  in it, compared on `.resolve()`. The advisory skip set becomes `set(changed) | set(untracked) | {p for p in unint if
  not _in_progress(<its text>)}`. Grading: a path that came ONLY from `unint` is graded `_grade(p, root, live=False)`;
  on a failure from it, `NOTE: <rel> entered history in <who[p]>` is printed after the failure lines. `unint_notes`
  print with `skip_notes`, after the ⚠ block. The OK line reads `check_review_coverage: OK — 0 unproven coverage claims
  across <N> changed + <M> unintegrated review artifact(s)` where M counts the unint-only paths.
- The module docstring's scope sentence (`:6-7`, "Inspects only changed/untracked files") names both sources and the
  base order.

**Consumes:** nothing from later phases.

Steps:
1. **Test first (the highest-risk behaviour, G1)**: create `tests/enforcement/test_review_coverage_unintegrated.py`
   with a fixture builder `_repo(tmp_path)` → a bare `origin.git`, a clone `main` on branch `master` pushed with one
   commit, and `_FAILING_RECEIPT` (`tests/enforcement/test_review_coverage_catchup.py:41-45`, copied). G1: commit the
   failing receipt in `main` without pushing → the no-arg run exits 1 and names the path; push it → exits 0 and the ⚠
   advisory still names it (the integrated file is advisory only). Run `.venv/bin/python -m pytest
   tests/enforcement/test_review_coverage_unintegrated.py -q` → G1 red (exit 0 on the unpushed commit).
2. Implement `integration_base`, `_unintegrated_md`, `_grade(live=…)` and the `main()` wiring. Re-run → G1 green.
3. Write G2–G9 (each seen red against the step-2 code or by a named mutant in step 5):
   - G2 (push-first cobra): a linked worktree (`git worktree add -b feat <wt>` from `main`) commits the failing receipt
     and pushes `feat` to `origin` → its no-arg run still exits 1.
   - G3 (catch-up merge): `main` gains a commit adding a failing receipt, is pushed; the worktree branch merges
     `master` → the worktree's run does not name that receipt (non-merge range; it is on `master`).
   - G4 (sibling isolation): `main` commits a failing receipt WITHOUT pushing; the worktree (branch created before it)
     runs → exit 0, the path not named (its base is local `master`, which holds the sibling's commit).
   - G5 (no base / git failure): a repo with no remote and HEAD on `master` (main checkout, no upstream) → exit 0
     with today's porcelain scope; `--base nosuchref` → exit 0 and the `NOTE: unintegrated review scan skipped` line,
     no `Traceback` in stderr.
   - G6 (IN-PROGRESS once): an unpushed committed receipt with `**Status:** IN-PROGRESS` → exit 0 and its path appears
     exactly once in stdout (the advisory line).
   - G7 (non-ASCII): a failing receipt named `2026-10-08-ü-review.md` reds BOTH as an uncommitted staged file and as an
     unpushed commit; a staged rename `a.md → b.md` grades `b.md` only.
   - G8 (mega live=False): an unpushed committed mega validation report whose recorded epic-set hash no longer matches
     the epics on disk → exit 0 (the textual contract passes; `live=True` would red it); the same report uncommitted →
     exit 1 (today's live grading, unchanged).
   - G9 (attribution + denominator): G1's failing run prints `NOTE: … entered history in <sha> (intel)` for a commit
     carrying `Agent-Name: intel`, and the author name for one without the trailer; a passing run with one converged
     unpushed receipt prints `0 changed + 1 unintegrated`.
4. Re-run the file plus the sibling suites: `.venv/bin/python -m pytest tests/enforcement/test_review_coverage_unintegrated.py
   tests/enforcement/test_review_coverage_catchup.py tests/test_check_review_coverage_precommit.py
   tests/test_check_review_coverage_rederivation.py tests/test_check_review_coverage_blocked.py
   tests/test_check_review_coverage_scope_growth.py tests/enforcement/test_mega_validation_reports.py
   tests/enforcement/test_review_confirmed_grammar.py tests/enforcement/test_review_refusals.py
   tests/test_task_lane_review_stop.py -q` → all pass (the AFTER-EDIT list, `check_review_coverage.py:2`);
   `python3 scripts/sysadmin/liveness_audit.py --proof vacuity --json` → the `check_review_coverage` row is ALIVE (it
   still fires on its no-remote fixture, `scripts/sysadmin/liveness_audit.py:1436-1442`).
5. **Phase gate**: red-on-revert in a throwaway worktree for G1 (`main()` ignores `unint`), G2 (the linked branch reads
   `@{upstream}` first), G4 (`--not` drops the base), G6 (the skip set takes IN-PROGRESS paths), G7 (`-z` removed) →
   each named test red, then the worktree removed. `.venv/bin/python -m mypy
   scripts/enforcement/check_review_coverage.py --ignore-missing-imports` → no new error against the pre-phase count.
6. **`/fabrik-review-scoped`** on Phase A's surface — BLOCKING, to its closing pass confirming zero defects.
7. Commit Phase A (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; trailers `Agent-Role: primary`,
   `Agent-Phase: A`), push.

**Behavior Contract (Phase A):**
- **Given** a failing review committed but not yet in the integration ref, **When** the gate's no-arg scan runs, **Then** it exits 1 naming the path; once integrated it is advisory only (spec § The delta 2-3)
- **Given** a linked worktree that pushed its branch to its own remote unmerged, **When** the scan runs there, **Then** the failing review still blocks (spec § The delta 1, the push-first cobra)
- **Given** a catch-up merge of the integration branch, **When** the worktree scans, **Then** none of the merged commits' reviews enter its range (spec § The delta 2)
- **Given** a sibling's unpushed commit on the main checkout's branch, **When** a linked worktree scans, **Then** that commit's review is not in its range (spec § Validation)
- **Given** no resolvable base or a failing `git log`, **When** the scan runs, **Then** it exits on today's porcelain scope with one NOTE and no traceback (spec § The delta 2)
- **Given** an unintegrated `Status: IN-PROGRESS` receipt, **When** the scan runs, **Then** it exits 0 and the receipt is reported once (spec § The delta 3)
- **Given** a review whose name holds a non-ASCII byte, **When** either scan runs, **Then** it is graded (spec § The delta 2, 5)
- **Given** an unintegrated mega report over epics that moved, **When** the scan runs, **Then** it is graded `live=False` (spec § The delta 4)
- **Given** a failing unintegrated review, **When** the gate reports it, **Then** a NOTE names the commit and its Agent-Name or author; a passing run's OK line counts both sources (spec § The delta 3, 6)
- **Given** the main checkout of a repo whose branch is `mobasak/<repo>` tracking `origin/mobasak/<repo>`, **When** the scan runs, **Then** its unpushed failing review blocks (I6)

## Phase B — the gate passes --base; the docs

Appetite: 45

**Interfaces — Consumes** (Phase A): `--base <ref>` on the checker; `integration_base(root)`'s order.

**Interfaces — Produces** (`scripts/final_gate.py`):
- `_integration_base() -> str` — the same order as `integration_base` through `run_cmd`, reusing
  `_linked_worktree_base()` (`:3409-3431`) for the linked-worktree leg; defined beside it at the file's end so the
  gate's cited line numbers above do not move (the convention `:3419-3420` states). `_diff_base()` (`:2829-2846`) is
  untouched — ruff and mypy keep their upstream-first base.
- The Coverage Checklist row (`:1729-1738`) passes `"--base", _integration_base()` only when it is non-empty; an empty
  base passes nothing and the checker resolves its own, which answers "" in the same states.

Steps:
1. **Test first (G10, parity)**: in the new test file, for three fixtures — a main checkout with an upstream, a linked
   worktree, a no-remote repo — assert `final_gate._integration_base()` (imported as `import final_gate as fg` after a
   `sys.path` insert, the pattern of `tests/test_final_gate_uninvoked_dirs.py:11-17`, with `monkeypatch.chdir` to the
   fixture — `run_cmd` runs in the cwd) equals
   the checker's `integration_base(root)`, and that the gate's argv for the row carries `--base <that ref>`
   (monkeypatched `run_optional_check` capturing its args). Run → red (no `_integration_base`).
2. Implement `_integration_base` and the call-site change. Re-run → green; a mutant swapping the main-checkout order
   (origin/master before `@{upstream}`) → G10 red.
3. Docs: `docs/workflows/FINAL_GATE_WORKFLOW.md` — the two Coverage Checklist bullets (`:168`, `:294`) gain "blocking
   scope: the working tree plus review artifacts in non-merge commits not yet in the integration ref (`--base`)"; the
   checker's docstring (Phase A) is the `--help`. `INDEX.md`: the new test file's row, and the
   `check_review_coverage.py` row amended if it states the scope. `python3 scripts/render_doc_script_links.py --check`
   and `python3 scripts/enforcement/check_doc_sync.py` → green.
4. `/fabrik-review-scoped` on Phase B's surface — BLOCKING, to its closing pass confirming zero defects.
5. Commit Phase B (explicit pathspecs; `INDEX.md`, `CHANGELOG.md` via the private-index recipe; `Agent-Phase: B`), push.

**Behavior Contract (Phase B):**
- **Given** any of the three repo shapes, **When** `final_gate.py` runs the coverage row, **Then** it passes the same base the checker would resolve, and nothing when there is none (spec § The delta 1)

## Phase C — blast radius and Finish

Appetite: 60

Steps:
1. **Fleet blast radius before merge** (spec § Cost): a scratch script runs the Phase-B checker
   (`<worktree>/scripts/enforcement/check_review_coverage.py --root <repo>`) in the main checkout of every `/opt` repo
   carrying `docs/development/reviews/` (13 at authoring) and in every registered linked worktree of those repos,
   read-only, and tabulates per tree: base resolved, M unintegrated, exit code, and the paths a NEW red names. Any new
   red is dispositioned before merge: a genuinely unconverged unintegrated review is mailed to that repo's agent (it
   is the bypass this plan closes, now visible); a false red is a defect fixed here. The table goes into the receipt.
2. **Finish — the heavy `/fabrik-review`** over the whole-plan diff: the D7 floor — file partition, a Sonnet and a Haiku
   finder per slice (D-344), the orchestrator executing every refutation, stamped with `command_run.py dispatch`
   first — to its closing pass confirming zero defects; receipt
   `docs/development/reviews/2026-10-08-plan-3-review-coverage-commit-scope-review.md` embedding the verbatim
   `final_gate.py --json` success.
3. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"`, checked with an exit-coded
   reader before any embedding; `python scripts/enforcement/check_convergence.py` → exit 0.
4. Commit Phase C (explicit pathspecs; `Agent-Phase: C`), push; plan `Status: EXECUTED`; `merge_request.py request
   --review <receipt> --item W-f847a317` and the `SendMessage` lines it prints.

**Behavior Contract (Phase C):**
- **Given** the merged change reaches every synced repo, **When** each repo's next gate runs, **Then** every new red was measured and dispositioned before merge (spec § Cost)

## File Scope (owned paths)

- scripts/enforcement/check_review_coverage.py
- scripts/final_gate.py
- tests/enforcement/test_review_coverage_unintegrated.py
- docs/workflows/FINAL_GATE_WORKFLOW.md
- docs/superpowers/specs/2026-10-08-review-coverage-commit-scope-design.md
- docs/development/reviews/2026-10-08-plan-3-review-coverage-commit-scope-review.md

## Evidence

**Phase A.** The scan today reads porcelain only, strips quotes and never unescapes; `main()`'s no-path branch builds
the blocking set from it and the running-record receipts alone:
```text
scripts/enforcement/check_review_coverage.py:94:def _changed_md(root: Path, prefix: str) -> tuple[list[Path], list[str], list[Path]]:
scripts/enforcement/check_review_coverage.py:2792:def _committed_nonquiet(root: Path, skip: set[Path]) -> list[str]:
scripts/enforcement/check_review_coverage.py:2830:            for e in check_mega_validation(p, root, live=False, scope="exit"):
scripts/enforcement/check_review_coverage.py:3145:def _grade(p: Path, root: Path) -> list[str]:
scripts/enforcement/check_review_coverage.py:3163:        return [f"{rel}: {e}" for e in check_mega_validation(p, root, live=True)]
scripts/enforcement/check_review_coverage.py:3188:def main() -> int:
```
The git shapes the delta relies on, probed this run in a scratch repo (a staged non-ASCII name, a staged rename, the
range log, a missing base):
```text
porcelain: b'R  docs/development/reviews/a.md -> "docs/development/reviews/2026-10-08-\\303\\274-review.md"\nA  docs/development/reviews/b.md\n'
porcelain -z: b'R  docs/development/reviews/2026-10-08-\xc3\xbc-review.md\x00docs/development/reviews/a.md\x00A  docs/development/reviews/b.md\x00'
log -z range: (0, b'docs/development/reviews/2026-10-08-\xc3\xbc-review.md\x00docs/development/reviews/b.md\x00')
orphan/no-base rc: 128
```
So `-z` returns the raw UTF-8 name, a rename's destination comes FIRST and its source is the next NUL field, the range
log returns raw names, and a bad base is rc 128 (the NOTE path). R3 measured across `/opt` (45 git repos; 13 with a
reviews dir):
```text
repos=45 with origin/master|main=18 without=27: [...]
with a reviews dir=13; of those without a base: ['seo', 'session-recall', 'trade-intelligence', 'tryton-crm', 'web-ecommerce-factory']
tryton-crm   remotes='origin'  head=mobasak/tryton-crm  up=origin/mobasak/tryton-crm
seo          remotes='origin'  head=mobasak/seo         up=origin/mobasak/seo
```
All five have an upstream on their main branch, so the amended order (I6) resolves a base in 13 of 13; the spec's
order resolves 8 of 13.

**Phase B.** The gate's seams:
```text
scripts/final_gate.py:1732:            "scripts/enforcement/check_review_coverage.py",
scripts/final_gate.py:2829:def _diff_base() -> str | None:
scripts/final_gate.py:3409:def _linked_worktree_base() -> str:
```
`_linked_worktree_base` answers "" in the main checkout and on a detached main checkout (`:3419-3423`), which is why the
new resolver adds its own main-checkout leg rather than reusing `_diff_base`'s upstream-first order for a worktree.

**Phase C.** The consumers outside the gate: `.pre-commit-config.yaml:144` (explicit-path mode, untouched) and
`scripts/sysadmin/liveness_audit.py:1436-1442` (a no-remote fixture: no base, so today's scope — its expectation holds).

## Self-audit

- Grounding passes: the spec's 32-row research ledger and three-judge panel; this run's reads of every cited function at
  d897964c0; two executed probes (the git shapes, the R3 census) whose output is above.
- Finding that changed the design: I6 — the spec's base order resolves nothing in the main checkout of 5 of the 13
  repos that carry reviews, the reporter included; the main checkout now reads its upstream, a linked worktree never does.
- (a) Coverage: the delta 1 → `integration_base` (A) and `_integration_base` (B), G2, G4, G5, G10; delta 2 →
  `_unintegrated_md`, G1, G3, G5; delta 3 → the `main()` wiring, G1, G6, G9; delta 4 → `_grade(live=…)`, G8; delta 5 →
  the `-z` `_changed_md`, G7; delta 6 → the OK line, G9; Validation's nine rows → G1–G10 (its last row, the old-checker
  pairing, is a Global Constraint: the two files sync together); documentation landing sites → Phase A (docstring),
  Phase B step 3 (FINAL_GATE_WORKFLOW, INDEX), each phase's commit (CHANGELOG), the approval D-row at the plan review;
  the spec's blast-radius sentence → Phase C step 1. No gap.
- (b) Signatures: Phase B consumes `--base <ref>` and `integration_base(root: Path) -> str` exactly as Phase A produces
  them; `_unintegrated_md` returns the three-tuple `main()` unpacks; `_grade`'s new keyword defaults to today's `True`,
  so the explicit-path caller (`:3207`) and the pre-commit hook keep live grading.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Resolved — R3** (repos with no master/main integration branch): measured, 5 of 13 reviews-bearing repos; the base
  order is amended so all 13 resolve (I6, Evidence Phase A).
- **Resolved — the `-z` rename order**: destination first, source second (probe above).
- **Open — R2** (the main checkout grades merged-but-unpushed reviews against the merge owner): accepted by the spec;
  resolution: Phase C step 1 tabulates every new red per tree before merge, with its attribution NOTE.
- **Open — repos with no remote at all** (16 of 45 /opt repos; none carries a reviews dir today): the scan stays
  porcelain-only there, as today; resolution: the census in Phase C step 1 re-counts, and a reviews dir appearing in a
  remote-less repo is the trigger to revisit.

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `scripts/enforcement/check_review_coverage.py` — every changed function, its callers | UNCHECKED |
| Hunt: `scripts/final_gate.py` — the new resolver and the coverage row | UNCHECKED |
| Hunt: `tests/enforcement/test_review_coverage_unintegrated.py` — every grader can go red | UNCHECKED |
| Hunt: `docs/workflows/FINAL_GATE_WORKFLOW.md` — every changed claim against the code | UNCHECKED |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | UNCHECKED |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | UNCHECKED |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | UNCHECKED |
| Recurrence: denominator on every count — bounded searches state their bound | UNCHECKED |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | UNCHECKED |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | UNCHECKED |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python scripts/review_rubric.py --changed scripts/enforcement/check_review_coverage.py scripts/final_gate.py tests/enforcement/test_review_coverage_unintegrated.py docs/workflows/FINAL_GATE_WORKFLOW.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: docs/workflows/FINAL_GATE_WORKFLOW.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/enforcement/test_review_coverage_unintegrated.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 35 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `30-ops.md`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
- `scripts/enforcement/_doc_registry.py::PROJECT_DOCS` `/fabrik-plan-after-chat` `Docs:`
```
