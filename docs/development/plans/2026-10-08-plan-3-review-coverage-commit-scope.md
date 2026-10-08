# Plan — the review-coverage gate grades committed-but-unintegrated reviews (W-f847a317)

Status: EXECUTED 2026-10-09
Whole-plan review: docs/development/reviews/2026-10-08-plan-3-review-coverage-commit-scope-review.md
Profile: small
**Owner:** —
**Surface:** `git rev-parse HEAD` = d897964c0 at authoring; `scripts/enforcement/check_review_coverage.py` 3286 lines

Spec: `docs/superpowers/specs/2026-10-08-review-coverage-commit-scope-design.md` (DRAFT at f0e85a0bd, merged to master
as b8170e73a; `Size: small`, `Profile: delta` — `/fabrik-plan-review` grades its sections together with this plan and
flips both). Source: tryton-crm mail 01M3YD067C → W-23b86f9e's `/fabrik-task` UPGRADE (`tradeoffs`) → work item
W-f847a317. Estimated diff: ≈155 code lines in ONE code file, tests excluded — in `check_review_coverage.py`:
`integration_refs` ≈30, `_unintegrated_md` with its shallow guard, attribution and NOTE ≈55, the `-z` byte-safe rewrite
of `_changed_md` ≈22, `_grade`'s `live` parameter ≈3, `--base` and the `main()` wiring ≈35, docstring ≈10 (sum 155).
`scripts/final_gate.py` is untouched (I7). Tests ≈280 lines in one new file.

## What this plan is

Three inline phases the orchestrator codes itself in the worktree; no coder is dispatched:

- **A — the checker**: `--base`, the integration-base resolver, the unintegrated scan with its shallow guard and
  attribution, byte-safe `-z` porcelain, mega `live=False`, the joined blocking set and the two-source denominator
  (spec § The delta 1-6), with their graders.
- **B — the docs**: the gate workflow's two Coverage Checklist bullets and the INDEX rows.
- **C — blast radius and Finish**: the fleet measurement before merge, the whole-plan `/fabrik-review`, the gate.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (8 IN, 3 OUT-OF-SCOPE) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"(1) check_review_coverage.py gains --base … (2) _changed_md via porcelain -z … (3) final_gate.py passes --base"* (the brief's three pieces) | IN for (1) and (2); (3) REPLACED by I7 | A: (1), (2) |
| I4 | *"graders per the spec's Validation list"* | IN | Phase A steps 1 and 3 (G1–G9, G11–G15) |
| I5 | *"The plan-review flips spec+plan to CONVERGED and holds the approval gate (answered by the Opus + Fable panel, D-613)"* | IN | the `/fabrik-plan-review` run that `/fabrik-plan-after-chat` invokes as its final step; its design-gate panel |
| I6 | Grounding finding (this run, Evidence Phase A): in 5 of the 13 /opt repos that carry a reviews dir — tryton-crm, the reporter, among them — the main checkout's branch is `mobasak/<repo>` with no `origin/master` or `origin/main`, so the spec's first base order (linked-worktree base → origin/master → origin/main) resolves NOTHING in their main checkouts and the bypass stays open exactly where it was reported | IN — a LINKED worktree uses the main checkout's branch, else origin/master, else origin/main, never its own upstream (the push-first cobra stays closed); the MAIN checkout uses its branch's upstream, else origin/master, else origin/main (pushing the main checkout's branch IS integration) | Phase A `integration_refs`; spec § The delta 1, § Rejected alternatives, R3 (amended in this review) |
| I7 | Review finding (pass 1): sync-EXCLUDED repos pull the hub's files rather than receive pushes (`scripts/final_gate.py:1741-1744`), so a `final_gate.py` that passes `--base` can meet a checker that predates the flag and fail the row with `unrecognized arguments`; and a second resolver in `final_gate.py` is a second definition to keep in parity | IN — `final_gate.py` is unchanged; the checker resolves the base itself on every no-path run, `--base` is an explicit override only | Phase A `main()`; spec § The delta 1, § Validation, § Cost (amended in this review) |
| I8 | Design-approval panel (opus + fable, both `approve-with-changes`): a review hand-added inside a merge commit escapes `--no-merges`; the main-checkout push-then-gate window and the IN-PROGRESS exit are unnamed; the census sees one instant, not the accepted window; a linked worktree whose main checkout sits on a feature branch inherits master commits | IN — `--cc` replaces `--no-merges` (G13); the base becomes a SET of integration refs (G14); R4 and the IN-PROGRESS exit named in the spec; the NOTE names the right remedy; Phase C replays recent merges and asserts a resolved base | Phase A interfaces and G13/G14; Phase C step 1; spec § Goal, § The delta 1-3, § Decisions taken, § Lifecycle, R1, R4 |

## What we already agreed (citations, not restatement)

- Goal, personas, lifecycle: `spec § Goal`, `spec § Personas`, `spec § Lifecycle`; why: `spec § Why this exists`.
- Measured behaviour: `spec § What exists today`; external facts G1–G6: `spec § Grounding`.
- The delta 1-6: `spec § The delta`; cost: `spec § Cost`; validation: `spec § Validation`.
- Chosen approach (B), integration-ref range with merges read by combined diff (judge panel 3-0, amended by the
  approval panel): `spec § Decisions taken`;
  rejected alternatives: `spec § Rejected alternatives`. The approval row is minted by `/fabrik-plan-review` at its gate
  (a `Size: small` spec is approved there, not here).
- Residual unknowns R1–R3: `spec § Residual unknowns` — R3 is measured by this run (Evidence, Phase A) and changes the
  base order (I6).

## Global Constraints (every phase inherits these)

- **Fleet-synced surface**: `scripts/enforcement/` is under the governance-sync trigger; a merge distributes the checker
  to every project. `scripts/final_gate.py` keeps invoking it with no arguments (`:1730-1739`), so a project or a
  sync-excluded repo running either an old or a new copy of either file never passes an unknown flag (I7).
- **Stdlib only**, no new import (`subprocess`, `os`, `pathlib` are already imported,
  `scripts/enforcement/check_review_coverage.py:29-38`); no dependency file is touched (`core/10-python.md:30`).
- **Never a traceback from git**: every new `git` call is `subprocess.run(..., capture_output=True)` reading BYTES,
  decoded with `os.fsdecode` (a non-UTF-8 name that `-z` now passes through raw must never raise
  `UnicodeDecodeError`), and every path the checker PRINTS, on whatever line carries it (failure lines, the untracked, attribution and
  intent-to-add NOTEs, the advisory, the explicit-path branch), is rendered through one helper, `_shown(p) = os.fsencode(str(p)).decode("utf-8", "backslashreplace")`,
  so a surrogate-escaped name never raises `UnicodeEncodeError` at `print`; `FileNotFoundError`, a non-zero rc and a shallow repository all degrade to today's
  porcelain-only scope plus one NOTE printed AFTER the ⚠ block (`check_review_coverage.py:3247-3251` — the emitter
  protocol: the ⚠ header must speak first).
- **The explicit-path mode keeps its selection and grading**: `main()`'s `args.paths` branch (`:3201-3222`), which the
  hub's pre-commit hook `review-coverage-staged` uses (`.pre-commit-config.yaml:144`), never reads `--base` and never
  scans the range; only its printed lines change, through `_shown` (an argv path holding `\xff` raises at `print` today).
- **No double reporting**: a path in the blocking set is in the advisory scan's skip set unless it is
  `Status: IN-PROGRESS` (`_in_progress`, `:465`), so an unintegrated IN-PROGRESS receipt keeps its standing advisory and
  every other file is reported by exactly one of the two.
- **The base never reads a linked worktree's own upstream** — the push-first cobra (`spec § Rejected alternatives`):
  pushing a worktree branch to its own remote must not take its reviews out of scope before they are merged.
- **12-Factor on this surface**: a CLI check, not a service — III one new flag, no env knob; XI stdout only; the rest
  not engaged.
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:20`, `:22`); every grader builds a real git
  fixture in `tmp_path` (a bare `origin`, a main checkout, and where named a `git worktree add` linked worktree) and runs
  the checker as a subprocess with `--root`, the pattern of `tests/enforcement/test_review_coverage_catchup.py:49-60`;
  assertions on exit codes and the named paths in stdout, never on prose beyond the path and the NOTE token. Every
  grader is seen red — against today's code, or by the named mutant in Phase A step 5. Red-on-revert runs in a
  throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
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
| `.windsurf/rules/core/40-documentation.md` (MATCHED — FINAL_GATE_WORKFLOW.md) | Doc Sync in the same change; no skipped heading levels | `core/40-documentation.md:242` |
| `docs/DECISIONS.md` D-442 | a linked worktree's base is the main checkout's branch | `scripts/final_gate.py:3409-3431` (the precedent the resolver mirrors) |
| `fabrik-lib` | none covers git range scoping — BUILD in place | `spec § Grounding`, the fabrik-lib verdict |
| `scripts/sysadmin/liveness_audit.py` | asserts the check fires on a bad review in a no-remote fixture repo | `scripts/sysadmin/liveness_audit.py:1436-1442` |
| `specs/services/*.yaml` `shape:` | not engaged: no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | .windsurf/rules/core/10-python.md:30 | Deps |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | .windsurf/rules/core/40-documentation.md:242 | Docs |

## Phase A — the checker: the base, the unintegrated scan, byte-safe -z porcelain — ✅ EXECUTED 2026-10-09 (2abf019c5)

Appetite: 150

**Interfaces — Produces** (all in `scripts/enforcement/check_review_coverage.py`; `spec § The delta` 1-6, amended by I6
and I7):
- `integration_refs(root: Path) -> list[str]` — the REF NAMES the range excludes (never SHAs: each candidate is tested
  with `git rev-parse --verify --quiet <ref>` for its rc only, and the name itself is kept), deduplicated, in order; `[]`
  when none resolves. THE RULE: a member is admitted only by CONFIGURATION or by the one fallback — never because a
  remote name exists, since every member shrinks the range and `git push origin HEAD:<name>` creates any remote name
  (passes 6 and 7, A6-1 and A7-1, both executed). Linked worktree (the absolute `git rev-parse --git-dir` differs from
  `--git-common-dir`): (1) the main checkout's branch `B` (`git --git-dir <common> symbolic-ref --quiet --short HEAD`)
  when it differs from HEAD's branch; (2) `B`'s CONFIGURED upstream (`git rev-parse --abbrev-ref --symbolic-full-name
  B@{upstream}`) — which also excludes commits merged from a remote that is ahead of the local `B` (G3); (3) only when
  `B` has no configured upstream, the FIRST of `origin/master`, `origin/main` that resolves (a main checkout parked on a
  feature branch — G14). Never THIS branch's own upstream (the push-first cobra), and no `origin/<B>` twin by name.
  Main checkout: its CONFIGURED `@{upstream}`, else the first of `origin/master`, `origin/main` that resolves. Any git
  error drops that candidate. The residual, named in the spec: rewriting branch CONFIGURATION (`--set-upstream-to`),
  and, where the fallback is reached (no configured upstream), a push that creates the fallback ref itself —
  `origin/master` when the remote has only `main` or neither, `origin/main` when it has neither.
- `_unintegrated_md(root: Path, prefix: str, bases: list[str]) -> tuple[list[Path], dict[Path, str], list[str]]` —
  returns (paths, attribution, notes). `bases == []` → `([], {}, [])`. `git rev-parse --is-shallow-repository` printing `true` →
  `([], {}, ["NOTE: unintegrated review scan skipped — shallow clone (its grafted root lists already-integrated files); porcelain scope only"])`.
  Otherwise runs `git log -z --cc --name-only --format= --diff-filter=d HEAD --not <bases…> -- <prefix>`: `--cc`
  lists a merge commit's paths only where they differ from EVERY parent, so a clean catch-up merge adds nothing and a
  review hand-added inside a merge commit is listed (spec § The delta 2); the configured-upstream member excludes
  commits a worktree merged from a remote that is ahead of the local integration branch. Splits the bytes on NUL, `os.fsdecode`s each name,
  deduplicates, applies `_changed_md`'s filter (`.md`, not `-archive.md`, not under `archived/`, a file on disk).
  Attribution per path: `git log -1 --format=%h%x00%(trailers:key=Agent-Name,valueonly)%x00%an HEAD --not <same refs> --
  <path>`, each NUL field stripped of whitespace → `"<sha> (<Agent-Name, else author>)"`. rc ≠ 0 or
  `FileNotFoundError` → `([], {}, ["NOTE: unintegrated review scan skipped — git log rc <n> against <bases> (porcelain scope only)"])`.
- `_changed_md(root, prefix)` keeps its signature and return; it reads `git status --porcelain -z
  --untracked-files=all -- <prefix>` as bytes, splits on NUL, `os.fsdecode`s each entry, takes the path from
  `entry[3:]`, and for an `R` or `C` status in either column consumes the NEXT field as the rename source and discards it
  (under `-z` the destination comes first — Evidence, Phase A). No quote stripping remains. The docstring's stale
  "Returns (paths, notes)" becomes the three-tuple. `_intent_to_add(root, prefix)` (`:139-162`) reads the same
  bytes-and-`os.fsdecode` `-z` porcelain, so its set matches the paths the scan now grades and the intent-to-add NOTE
  still names a non-ASCII peer receipt.
- `_grade(p, root, live: bool = True)` — passes `live` to `check_mega_validation` (`:3163`); every existing caller is
  unchanged.
- `main()`: `ap.add_argument("--base", default=None, help=…)` — an explicit override; `final_gate.py` never passes it.
  No-path branch only: `bases = [args.base] if args.base is not None else integration_refs(root)`; `unint, who,
  unint_notes = _unintegrated_md(root, REVIEWS_DIR, bases)`. The blocking set is `changed` (plus the running-record
  receipts, `:3226-3228`) followed by every `unint` path not already in it, compared on `.resolve()`. The advisory skip
  set becomes `set(changed) | set(untracked) | {p for p in unint if not _in_progress(<its text>)}`. Grading: a path that
  came ONLY from `unint` is graded `_grade(p, root, live=False)`; on a failure from it, `NOTE: <rel> entered history in
  <who[p]> — mail its author or revert it; never push to clear it` is printed after the failure lines (pushing would
  integrate the unconverged review — spec § The delta 3). `unint_notes` print with `skip_notes`, after the ⚠ block. The OK line
  reads `check_review_coverage: OK — 0 unproven coverage claims across <N> changed + <M> unintegrated review
  artifact(s)` where M counts the unint-only paths.
- The module docstring's scope sentence (`:6-7`, "Inspects only changed/untracked files") names both sources, the base
  order and the shallow skip.

**Consumes:** nothing from later phases.

Steps:
1. **Test first (the highest-risk behaviour, G1)**: create `tests/enforcement/test_review_coverage_unintegrated.py`
   with a fixture builder `_repo(tmp_path)` → a bare `origin.git`, a clone `main` on branch `master` pushed with one
   commit, and `_FAILING_RECEIPT` (`tests/enforcement/test_review_coverage_catchup.py:42-46`, copied). G1: commit the
   failing receipt in `main` without pushing → the no-arg run exits 1 and names the path; push it → exits 0 and no
   failure line names it (it is integrated). Run `.venv/bin/python -m pytest
   tests/enforcement/test_review_coverage_unintegrated.py -q` → G1 red (exit 0 on the unpushed commit).
2. Implement `integration_refs`, `_unintegrated_md`, the byte-safe `_changed_md`, `_grade(live=…)` and the `main()`
   wiring. Re-run → G1 green.
3. Write G2–G15:
   - G2 (push-first cobra): a linked worktree (`git worktree add -b feat <wt>` from `main`) commits the failing receipt
     and pushes with `git push -u origin feat` (so the branch HAS an upstream the mutant could read) → its no-arg run
     still exits 1.
   - G3 (catch-up merge, remote ahead): a second clone pushes a commit adding a failing receipt to `origin/master`; the
     worktree runs `git fetch` and merges `origin/master` while the local `master` stays behind → the worktree's run
     does not name that receipt (the `origin/master` member excludes it, and `--cc` lists nothing for the clean merge).
   - G4 (sibling isolation): `main` commits a failing receipt WITHOUT pushing; THEN the worktree branch is created from
     `main`'s HEAD → the worktree's run exits 0 and does not name the path (its base is the local `master`, which holds
     the sibling's commit).
   - G5 (no base / git failure): a repo with no remote and HEAD on `master` (main checkout, no upstream) → exit 0
     with today's porcelain scope; `--base nosuchref` → exit 0 and the `NOTE: unintegrated review scan skipped` line,
     no `Traceback` in stderr.
   - G6 (IN-PROGRESS once): an unpushed committed receipt with `**Status:** IN-PROGRESS` → exit 0 and its path appears
     exactly once in stdout (the advisory line).
   - G7 (non-ASCII): a failing receipt named `2026-10-08-ü-review.md` reds BOTH as an uncommitted staged file and as an
     unpushed commit; a staged rename `a.md → b.md` grades `b.md` only; a staged failing receipt whose name holds the
     byte `\xff` → exit 1, its name printed with `\xff` backslash-escaped, no `Traceback` in stderr — in the no-path
     scan and when passed as an explicit path; a failing `git add -N` receipt named `…-ü-review.md` still prints the
     intent-to-add NOTE, and one named with `\xff` prints it escaped, with no `Traceback`.
   - G8 (mega live=False): an unpushed committed mega validation report whose recorded epic-set hash no longer matches
     the epics on disk → exit 0 (the textual contract passes; `live=True` would red it); the same report uncommitted →
     exit 1 (today's live grading, unchanged).
   - G9 (attribution + denominator): G1's failing run prints `NOTE: … entered history in <sha> (intel)` for a commit
     carrying `Agent-Name: intel`, and the author name for one without the trailer, with no stray newline inside the
     parentheses; a run whose only unintegrated artifact is an IN-PROGRESS receipt prints `0 changed + 1 unintegrated`.
   - G11 (I6, a non-master integration branch): a main checkout on branch `mobasak/x` tracking `origin/mobasak/x`, with
     no `master` or `main` anywhere, commits the failing receipt without pushing → exit 1 naming it; pushed → exit 0.
   - G13 (a review inside a merge commit): the worktree runs `git merge --no-ff --no-commit master`, `git add`s a failing
     receipt, and commits → exit 1 naming it; a clean `git merge master` of a branch carrying no review → the merge adds
     nothing to the range.
   - G14 (main checkout on a feature branch): the main checkout checks out a local branch `side` with no remote
     counterpart, cut before `origin/master` gained an integrated failing review; a linked worktree branched from
     `origin/master` → exit 0, that review not named (`origin/master` is in the set).
   - G15 (a push to a new remote name clears nothing): in a master repo, a linked worktree with a failing receipt runs
     `git push origin HEAD:main` → still exit 1; in the I6 shape, the main checkout on `mobasak/x` runs `git push origin
     HEAD:master` → still exit 1; and in the G14 shape (main checkout on an upstream-less `side`), the worktree runs
     `git push origin HEAD:side` → still exit 1.
   - G12 (shallow clone): a `--depth 1 --no-single-branch` clone on a DETACHED HEAD at a feature commit whose tree
     carries an already-integrated failing review (detached, so no upstream: the base falls back to `origin/master`,
     the CI shape) → exit 0 with the shallow NOTE (with the guard removed the grafted root lists the review and reds).
4. Re-run the file plus the sibling suites: `.venv/bin/python -m pytest tests/enforcement/test_review_coverage_unintegrated.py
   tests/enforcement/test_review_coverage_catchup.py tests/test_check_review_coverage_precommit.py
   tests/test_check_review_coverage_rederivation.py tests/test_check_review_coverage_blocked.py
   tests/test_check_review_coverage_scope_growth.py tests/enforcement/test_mega_validation_reports.py
   tests/enforcement/test_review_exit_contract.py tests/enforcement/test_review_confirmed_grammar.py
   tests/enforcement/test_review_refusals.py tests/test_task_lane_review_stop.py -q` → all pass (every test the
   AFTER-EDIT line names, `check_review_coverage.py:2`, plus the four sibling suites);
   `python3 scripts/sysadmin/liveness_audit.py --proof vacuity --json` → the `check_review_coverage` row is ALIVE (it
   still fires on its no-remote fixture, `scripts/sysadmin/liveness_audit.py:1436-1442`).
5. **Phase gate**: red-on-revert in a throwaway worktree, one mutant per grader that today's code does not already red —
   G2 (the linked branch reads `@{upstream}` first), G3 (member (2) omitted while (3) stays gated on `B`'s configuration), G13 (`--cc` replaced by `--no-merges`), G14 (`origin/master` dropped from the
   linked set), G15 (`origin/master` and `origin/main` added whenever they verify; an `origin/<B>` twin added by name), G4 (`--not` drops the
   base), G6 (the skip set takes IN-PROGRESS paths), G7 (bytes decoded strictly; `_shown` bypassed; `_intent_to_add` left on quoted porcelain), G8 (unint-only paths graded
   `live=True`), G9 (fields not stripped), G11 (the main-checkout `@{upstream}` leg removed), G12 (the shallow guard
   removed) → each named test red, then the worktree removed. (G1, G5 and G7's non-ASCII rows are red on today's code.)
   `.venv/bin/python -m mypy scripts/enforcement/check_review_coverage.py --ignore-missing-imports` → no new error
   against the pre-phase count.
6. **`/fabrik-review-scoped`** on Phase A's surface — BLOCKING, to its closing pass confirming zero defects.
7. Commit Phase A (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; trailers `Agent-Role: primary`,
   `Agent-Phase: A`), push.

**Behavior Contract (Phase A):**
- **Given** a failing review committed but not yet in the integration ref, **When** the gate's no-arg scan runs, **Then** it exits 1 naming the path; once integrated it is not a failure (spec § The delta 2-3)
- **Given** a linked worktree that pushed its branch to its own remote unmerged, **When** the scan runs there, **Then** the failing review still blocks (spec § The delta 1, the push-first cobra)
- **Given** a catch-up merge of a remote integration branch that is ahead of the local one, **When** the worktree scans, **Then** none of the merged commits' reviews enter its range (spec § The delta 2)
- **Given** a sibling's unpushed commit on the main checkout's branch that a linked worktree's branch contains, **When** the worktree scans, **Then** that commit's review is not in its range (spec § Validation)
- **Given** no resolvable base, **When** the scan runs, **Then** it is today's porcelain scope exactly, with no NOTE; **Given** a failing `git log` or a shallow clone, **Then** it keeps that scope with one NOTE and no traceback (spec § The delta 2 — row corrected in execution, Phase A review A-O3)
- **Given** an unintegrated `Status: IN-PROGRESS` receipt, **When** the scan runs, **Then** it exits 0 and the receipt is reported once (spec § The delta 3)
- **Given** a review whose name holds a non-ASCII byte, **When** either scan runs, **Then** it is graded, and a non-UTF-8 name never raises (spec § The delta 2, 5)
- **Given** an unintegrated mega report over epics that moved, **When** the scan runs, **Then** it is graded `live=False` (spec § The delta 4)
- **Given** a failing unintegrated review, **When** the gate reports it, **Then** a NOTE names the commit and its Agent-Name or author; a passing run's OK line counts both sources (spec § The delta 3, 6)
- **Given** the main checkout of a repo whose branch is `mobasak/<repo>` tracking `origin/mobasak/<repo>`, **When** the scan runs, **Then** its unpushed failing review blocks (I6)

## Phase B — the docs — ✅ EXECUTED 2026-10-09 (9b9cf5a28)

Appetite: 30

**Interfaces — Consumes** (Phase A): the scan's scope, the base order, the shallow skip, `--base`.

Steps:
1. `docs/workflows/FINAL_GATE_WORKFLOW.md` — the two Coverage Checklist bullets (`:168`, `:294`) gain "blocking scope:
   the working tree plus review artifacts in commits not yet in an integration ref, merges read by combined diff (the checker resolves them;
   `--base` overrides)"; the row at `:483` keeps "ADVISORY row" for the committed scan and names the new blocking leg.
   The checker's docstring (Phase A) is the `--help`. `INDEX.md`: the new test file's row, and the
   `check_review_coverage.py` row amended if it states the scope. `python3 scripts/render_doc_script_links.py --check`
   and `python3 scripts/enforcement/check_doc_sync.py` → green.
2. `/fabrik-review-scoped` on Phase B's surface — BLOCKING, to its closing pass confirming zero defects.
3. Commit Phase B (explicit pathspecs; `INDEX.md`, `CHANGELOG.md` via the private-index recipe; `Agent-Phase: B`), push.

**Behavior Contract (Phase B):**
- **Given** an agent reading the gate workflow after a red from the new leg, **When** it looks up the Coverage Checklist row, **Then** the doc names both scopes and how the base is chosen (spec § Documentation landing sites)

## Phase C — blast radius and Finish — ✅ EXECUTED 2026-10-09 (6054bf25c)

Appetite: 90

Steps:
1. **Fleet blast radius before merge** (spec § Cost), run in the background (`run_in_background`): a scratch script runs
   the Phase-A checker (`<worktree>/scripts/enforcement/check_review_coverage.py --root <tree>`) read-only over every
   `/opt` repo carrying `docs/development/reviews/` — its main checkout and every registered linked worktree whose
   directory exists and that `git worktree list --porcelain` does not mark `prunable` (13 repos, 246 registered trees,
   21 of them prunable and missing on disk, at authoring) — and tabulates per tree: the integration refs resolved, M
   unintegrated, exit code, and the paths a NEW red names, with the examined and skipped denominators. Every tree whose
   repo has a remote must resolve a non-empty set — an empty one there is a resolver defect (its "any git error drops
   the candidate" would otherwise turn a wrong `cwd` into a silent porcelain-only green), fixed before merge. Because a
   snapshot cannot see the window the spec accepts (R2 — the merge owner's merged-but-unpushed state reads 0 almost
   always), the script also replays, per main checkout, its last 20 first-parent merges into the integration branch,
   scanning each as HEAD=`<merge>` against base=`<merge>^1`, and counts how often a merge owner would have been
   reddened for a merged branch's review. Any new red is dispositioned before
   merge: a genuinely unconverged unintegrated review is mailed to that repo's agent (it is the bypass this plan closes,
   now visible); a false red is a defect fixed here. The table goes into the receipt.
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
So `-z` returns the raw name, a rename's destination comes FIRST and its source is the next NUL field, the range log
returns raw names, and a bad base is rc 128 (the NOTE path). Pass 1 of this review re-executed three edges in scratch
fixtures: a `\xff` name under `-z` with `text=True` raises `UnicodeDecodeError` (hence bytes + `os.fsdecode`); a
`mobasak/x` LOCAL base drops the remote-ahead term under a "no `/`" test and lists another session's merged review
(hence `refs/heads/<base>`); a shallow clone lists an already-integrated review through its grafted root:
```text
range per plan (no origin term, base has /): (0, b'…/2026-10-08-mine-review.md\x00…/2026-10-08-other-review.md\x00')
range with origin term: (0, b'…/2026-10-08-mine-review.md\x00')
shallow range feat --not origin/master: (0, b'docs/development/reviews/2026-01-01-old-review.md\x00')
text=True -z RAISES: UnicodeDecodeError 'utf-8' codec can't decode byte 0xff in position 154: invalid start byte
```
R3 measured across `/opt` (45 git repos; 13 with a reviews dir):
```text
repos=45 with origin/master|main=18 without=27: [...]
with a reviews dir=13; of those without a base: ['seo', 'session-recall', 'trade-intelligence', 'tryton-crm', 'web-ecommerce-factory']
tryton-crm   remotes='origin'  head=mobasak/tryton-crm  up=origin/mobasak/tryton-crm
seo          remotes='origin'  head=mobasak/seo         up=origin/mobasak/seo
```
All five have an upstream on their main branch, so the amended order (I6) resolves a base in 13 of 13; the spec's
first order resolved 8 of 13.
Pass 6 of this review showed that a set admitting any verifying `origin/main` is cleared by `git push origin HEAD:main`
(executed: range non-empty before, `b''` after, while `origin/master` still lacked the commit), so every member is now
anchored on configuration. Every reviews-bearing main checkout has a configured upstream, so the no-upstream fallback
is reached by none of them today:
```text
repos=13 risky(no upstream, origin/main only)=0 []
youtube                    head=spec/video-classification-pipeline upstream=origin/spec/video-classification-pipeline -> upstream
```

**Phase B.** The doc rows edited: `docs/workflows/FINAL_GATE_WORKFLOW.md:168`, `:294` (the two Coverage Checklist
bullets) and `:483` (the enforcement-scripts list row).

**Phase C.** The consumers outside the gate: `scripts/final_gate.py:1730-1739` (the row, called with no arguments and
unchanged — I7), `.pre-commit-config.yaml:144` (explicit-path mode, untouched) and
`scripts/sysadmin/liveness_audit.py:1436-1442` (a no-remote fixture: no base, so today's scope — its expectation holds).

## Self-audit

- Grounding passes: the spec's 32-row research ledger and three-judge panel; this run's reads of every cited function at
  d897964c0; two executed probes (the git shapes, the R3 census); pass 1 of this review (two author-blind seats, every
  confirmed finding re-executed by the orchestrator).
- Findings that changed the design: I6 — the main checkout reads its upstream, a linked worktree never does; I7 —
  `final_gate.py` is unchanged and the checker owns the one base definition; pass 1 — bytes + `os.fsdecode`, the
  `refs/heads/<base>` test, the shallow guard.
- (a) Coverage: the delta 1 → `integration_refs`, G2, G4, G5, G11, G14, G15; delta 2 → `_unintegrated_md`, G1, G3, G5, G12,
  G13; delta
  3 → the `main()` wiring, G1, G6, G9; delta 4 → `_grade(live=…)`, G8; delta 5 → the byte-safe `_changed_md`, G7; delta
  6 → the OK line, G9; every spec Validation row → G1–G9, G11–G15, and its final row (no unknown flag) → I7 and the
  Global Constraint; documentation landing sites → Phase A (docstring), Phase B (FINAL_GATE_WORKFLOW, INDEX), each
  phase's commit (CHANGELOG), the approval D-row at the plan review; the spec's blast-radius sentence → Phase C step 1.
  No gap.
- (b) Signatures: `integration_refs(root: Path) -> list[str]` returns ref names and is called only by `main()`, which
  passes the list (or `[args.base]`) to `_unintegrated_md(..., bases)`;
  `_unintegrated_md` returns the three-tuple `main()` unpacks; `_grade`'s new keyword defaults to today's `True`, so the
  explicit-path caller (`:3207`) and the pre-commit hook keep live grading.
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

## Pass Ledger

Joint loop over this plan and its `Size: small` spec (md5 pairs: plan · spec).

| Pass | seats · axes re-checked | counters | method | md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (plan § Global Constraints, Phase A, Phase B; spec § The delta, § Validation, § Constraints Digest) + sonnet×1 (every other section of both) · all axes | found: 17, new: 17, confirmed: 16, fixed: 16, unexecuted: 0, edits: 31 | method: citation — full pass over pins at 0422ddb26; every confirmed candidate re-executed by the orchestrator (the seat fixtures re-run: G1's integrated receipt is unnamed by the advisory, a `mobasak/x` local base drops the remote-ahead term, a branch made before the sibling commit never reaches it, a shallow clone lists an integrated review, a `\xff` name raises under `-z` `text=True`, trailer values carry a newline; `final_gate.py:71`/`:318` freeze the cwd, `rev-parse --verify` prints a SHA, `:1741-1744` sync-excluded repos pull); confirmed: G1 assertion, the `/` test, G4 unreachable, G10 cwd, shallow/orphan, G2 upstream, G3/G8 never red, `-z` decode, trailer strip, AFTER-EDIT list, four spans, the resolver's return, the G9 fixture, the I5 phase reference, the unbounded worktree census, the spec size; I7 drops the `final_gate.py` change; B-3 refuted | plan 7d7f53e5 · spec 3fcec7f8 → plan 2d219deb · spec a85622f0 |
| Pass 2 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-1 rewrite + one hop | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 5 | method: re-derivation — A 13/13 findings NOW_FALSE and 22/23 claims re-verified (A-C19 retired with G10), B 4/4 NOW_FALSE and 13/13 claims re-verified (census re-run: 13 repos, same 21 prunable missing; rubric diff 0 bytes; the Pass 1 end hash re-derived by deleting its row); confirmed by orchestrator execution, both inside round-1 hunks (own-fix: round 1): a surrogate-decoded name raises `UnicodeEncodeError` at `print` (A2-1, `_shown`), G12 on a checked-out branch gets an upstream and never reproduces the shallow false red (A2-2, detached HEAD); A2-3 recorded | plan aeb312b4 · spec a85622f0 → plan d42885c6 · spec a85622f0 |
| Pass 3 | opus×1 (slice A owner); slice B restated at its Pass 2 13/13 · remainder round — the round-2 fixed set only | found: 2, new: 2, confirmed: 1, fixed: 1, unexecuted: 0, edits: 4 | method: re-derivation — A2-1 and A2-2 NOW_FALSE, executed (`_shown` escapes `\xff`, round-trips `ü`, a piped child prints at rc 0; the detached shallow fixture falls back to origin/master and reds with the guard removed, passes with it); confirmed (own-fix: round 1, one hop from the `-z` hunk): `_intent_to_add` keeps quoted porcelain, so the intent-to-add NOTE misses a non-ASCII peer receipt (A3-1, read at `check_review_coverage.py:139-162`); A3-2 recorded and applied — the explicit-path branch's pre-existing `print` traceback on a `\xff` argv path; standing clean since Pass 2: slice B | plan 52cb3e78 · spec a85622f0 → plan 0eb94cbd · spec a85622f0 |
| Pass 4 | opus×1 (slice A owner); slice B restated at its Pass 2 13/13 · scope-growth stop remainder — the round-3 fixed set only | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 11 | method: re-derivation — A3-1 and A3-2 NOW_FALSE, executed (`-z --untracked-files=no` keeps ` A` for `add -N` entries, so the ü and `\xff` peer receipts match and a staged file does not); confirmed (own-fix: round 3, inside the A3-1 hunk): the intent-to-add NOTE becomes a new print site the enumerated `_shown` list missed (A4-1, a piped child raised `UnicodeEncodeError`) — the rule now covers every print site and G7 adds a `\xff` `add -N` row; residue before the next pin: the Coverage Checklist adjudicated (9 rows) | plan a7d6372b · spec a85622f0 → plan 67f93be1 · spec a85622f0 |
| Pass 5 | opus×1 + fable×1 (the D-613 design-approval panel, same brief, author-blind; pinned plan 23085818 · spec a85622f0) · approval axes: bypass closed, cross-session reds, cheapest dodge, blast radius | found: 13, new: 13, confirmed: 8, fixed: 6, unexecuted: 0, edits: 22 | method: citation — both seats `approve-with-changes`; confirmed by orchestrator execution or read: a review hand-added inside a merge commit escapes `--no-merges` (re-run: range empty, file tracked; `--cc` lists it) → `--cc` + G13; a linked worktree on a feature-branch main checkout inherits master commits → integration-ref SET + G14; the close chain pushes before it gates (`close-chain.md:7`, read) → spec R4, Goal narrowed, kaizen mail 01M4EJTSCY (recorded); IN-PROGRESS cheapest exit → named, backlog W-73f60b35 (recorded); the census sees one instant → merge replay + non-empty-set assertion; the NOTE invited pushing → remedy named; sweep commits and sibling-cut branches → Lifecycle and Validation sentences; refuted: the trailer newline (already stripped), the fleet-alloy reviews (0 errors, graded) | plan 0f3fac17 · spec a85622f0 → plan 1a1ab97a · spec 1c4f6993 |
| Pass 6 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the panel hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 14 | method: re-derivation — A: A4-1 NOW_FALSE and (a)-(e) executed true (`--cc` lists nothing for a clean catch-up merge, lists a receipt added inside a `--no-commit` merge, lists no review for a conflict resolved outside reviews/; G2/G4/G11 behave under the set; G13/G14 killable); B: Pass 5 end hash re-derived by deleting its row, the 10-of-13 split and `close-chain.md:7` re-run from primary sources; confirmed, all inside panel hunks (own-fix: round 5): a set admitting any verifying `origin/main` is cleared by `git push origin HEAD:main` (A6-1, executed in seat fixtures) → members anchored on configuration, G15, the config residual named and measured (13 of 13 main checkouts have a configured upstream); the plan's agreed-approach line still said non-merge commits (B6-1); the Self-audit Validation map omitted G13/G14 (B6-2); residue swept with the fix: two more "non-merge" sentences (spec persona, Phase B doc line) | plan a8a1441a · spec 1c4f6993 → plan 11fb5cc0 · spec 104b3aac |
| Pass 7 | opus×1 + sonnet×1 (round-1 slice owners) · remainder round — the round-6 fixed set | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 9 | method: re-derivation — A: A6-1 NOW_FALSE (`HEAD:main` and `HEAD:master` pushes no longer clear; the G15 mutants killed), G2/G4/G11/G13/G14 executed true; B: B6-1/B6-2 NOW_FALSE, the 13-of-13 configured-upstream census re-run from primary sources, the Pass 6 end hash re-derived by deleting its row, 13/13 Validation rows mapped; confirmed (own-fix: round 6, site: the `integration_refs` member list): the `origin/<B>` twin admitted by name is cleared by `git push origin HEAD:side` when B has no upstream (A7-1, executed) → the twin dropped, B's configured upstream covers G3, G15 extended; orchestrator probe before the pin: G3 excludes the remote-ahead review, `HEAD:side` and `HEAD:main` leave the range red; class rewrite — the `integration_refs` member paragraph and spec § The delta 1 (rounds 6, 7) | plan b0d52836 · spec 104b3aac → plan 36f206c9 · spec 0aa79bbd |
| Pass 8 | opus×1 + sonnet×1 (round-1 slice owners) · remainder round — the round-7 class rewrite only (scope-growth stop) | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — A: A7-1 NOW_FALSE (`HEAD:side` leaves the set `['side', 'origin/master']` and the range red), G2/G3/G4/G11/G13/G14 and both G15 pushes executed true, every member's admission named (B by the main checkout's HEAD, its upstream by configuration, the fallback only without one); B: residual (3) consistent with § The delta 1, the 13-of-13 census byte-identical on re-run, the Pass 7 end hash re-derived by deleting its row; confirmed, both wording inside the round-7 hunk (own-fix: round 7, site: the residual sentence and the G3 mutant): the named residual was narrower than the executed one — a remote with neither `master` nor `main` lets a push create the fallback (A8-1, executed) — and the G3 mutant read two ways, one of which survives (A8-2) | plan d209614e · spec 0aa79bbd → plan f753b2c4 · spec 64975615 |
| Pass 9 | opus×1 (slice A owner, closing); slice B restated at its Pass 8 3/3 · closing remainder round — the round-8 fixed set only | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — A 2/2 re-executed: the residual sentence covers all three fallback-creation cases (remote with neither branch → `HEAD:master` or `HEAD:main`; remote with only `main` → `HEAD:master`), each run in a fixture and each clearing the range as the sentence now says; the G3 mutant coded as written leaves the set `['master']` and goes red; standing clean since Pass 8: slice B and every class of the ledger | plan e1a83760 · spec 64975615 → plan e1a83760 · spec 64975615 ✓ |

## Residual

| Id | Verdict |
|---|---|
| B-3 | REFUTED (a plan's own Status flip is orchestrator bookkeeping outside File Scope — the precedent plan `docs/development/plans/2026-10-08-plan-2-payments-fulfilment-role.md` omits its own path the same way, and `/fabrik-execute-plan` mints its lock from File Scope for the code it guards) |
| A2-3 | RECORDED — measured (one hop out: `scripts/enforcement/check_review_hygiene.py:947-976` `_changed_receipts` hand-copies the old porcelain selection, so its parity docstring goes stale and it keeps both holes; outside File Scope — backlog W-1a3b3e85, sibling of W-699a271a) |
| A3-2 | RECORDED — measured (pre-existing, not introduced by any round's hunk: the explicit-path branch prints an argv path raw, so a `ÿ` name raises at `print` today while still failing closed; destination: applied in this plan — Phase A routes those lines through `_shown`) |
| P-R4 | RECORDED — measured (panel, both seats: the close chain pushes before it gates, `commands/_fragments/close-chain.md:7`, so a MAIN checkout's push-then-gate passes; spec R4; destination: kaizen, mail 01M4EJTSCY, command wording) |
| P-IP | RECORDED — measured (panel, both seats: `Status: IN-PROGRESS` stays the cheapest exit, pre-existing and advisory-nagged; spec § Decisions taken; destination: backlog W-73f60b35, refuse at merge-request time) |

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `scripts/enforcement/check_review_coverage.py` — every changed function, its callers | FIXED r1 (the `/`-keyed origin term became `refs/heads/<base>`; bytes + `os.fsdecode`; the shallow guard; the resolver returns a ref name — `_changed_md` :94, `main()` :3188, `_grade` :3145 re-read) · FIXED r2 (`_shown` on every print site, the advisory included) · FIXED r3 (`_intent_to_add` :139-162 on the same `-z` read; the explicit-path branch :3201-3222 prints through `_shown`) · FIXED panel (`--cc` replaces `--no-merges` so a review inside a merge commit is listed; the base is a SET of integration refs; the NOTE names the remedy) |
| Hunt: `tests/enforcement/test_review_coverage_unintegrated.py` — every grader can go red | FIXED r1 (G1's integrated assertion, G2 `push -u`, G3 remote-ahead, G4 branched after the sibling, G8 and G3 mutants named — each executed in seat fixtures) · FIXED r2 (G12 on a detached HEAD reds with the guard removed, executed) · FIXED r3 (G7's intent-to-add and explicit-path rows) · FIXED panel (G13 merge-commit receipt, G14 main checkout on a feature branch, each with a named mutant) |
| Hunt: `docs/workflows/FINAL_GATE_WORKFLOW.md` — every changed claim against the code | CLEAN (docs/workflows/FINAL_GATE_WORKFLOW.md:168, :294 and :483 re-read by both seats; Phase B names all three and keeps :483's ADVISORY wording for the committed scan) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r1 (a shallow clone and an unresolvable base degrade to porcelain scope with a NOTE, never a silent zero; `final_gate.py` unchanged so no unknown-flag red, I7) · FIXED r2 (a non-UTF-8 name can no longer crash the gate at `print`) |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | FIXED r1 (a slash in a branch name no longer decides local-vs-remote; four off-by-one spans corrected; trailer fields stripped) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r1 (G3 and G8 were green on today's code — each now has a named step-5 mutant; G4's mutant was unkillable until the branch order changed) · FIXED r2 (G12's mutant killed only through the NOTE text until the fixture went detached) |
| Recurrence: denominator on every count — bounded searches state their bound | FIXED r1 (Phase C's census bounded to existing non-prunable trees with 13 repos / 246 trees / 21 prunable stated; R3 13 of 13 re-derived by seat B twice) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (docs/development/plans/2026-10-08-plan-3-review-coverage-commit-scope.md § Phase C — the census runs in the background with Appetite 90; one `git log` per gate run, no new network call; seats stamped per round: 2, 2, 1, 1) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (docs/development/plans/2026-10-08-plan-3-review-coverage-commit-scope.md § Evidence — every confirmed candidate re-executed by the orchestrator in scratch git fixtures; the anti-cheat hash re-derived by seat B) |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python scripts/review_rubric.py --changed scripts/enforcement/check_review_coverage.py tests/enforcement/test_review_coverage_unintegrated.py docs/workflows/FINAL_GATE_WORKFLOW.md
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
