# Plan — review seats: write isolation in the seat guard (W-72dfd448)

Status: IN-PROGRESS
Profile: small
**Owner:** intel
**Surface:** `git rev-parse HEAD` = 4efc5d325 at authoring, re-grounded at 21744dd43 (2026-10-22; seat_guard.py and
its tests unchanged); `.claude/hooks/seat_guard.py` (651 lines), `tests/test_seat_guard.py` (33 tests), `commands/_agents/fabrik-reviewer.md:4` (read, not edited)

Spec: `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md` (DRAFT, `Size: small`, `Profile: delta`;
refined in this run by D-914). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source:
mail 01M4PHYNXJ → work item W-72dfd448; design rulings D-913, D-914. Estimated diff (after the plan review's rounds 1-3): ≈250 code lines in ONE code file, `.claude/hooks/seat_guard.py`
(redirect capture with the empty-list case and the stream-offset fd test in `_simple_commands` ≈45, the destination
rule `_write_reason` with its per-verb option tables, glob prefix and `/dev` exemption ≈130, its call before
`if not words` and every `continue` in `_scan` ≈10, the `env -C` scoping ≈10, the `_HEREDOC` fix ≈1, the unparseable
fallback ≈10, docstring ≈45); tests ≈220 lines in `tests/test_seat_guard.py`; one row in
`docs/workstation/hooks-index.md`.

## What this plan is

Two inline phases the orchestrator codes itself in the `worktree-intel` worktree; no coder is dispatched:

- **A — the guard**: the shell write rule, the unparseable fallback, the tool-list pin, the docstring and the
  hooks-index row and the two scanner fixes (spec § The delta items 1-5).
- **B — Finish**: the whole-plan `/fabrik-review` (the hook is a governance-sync path), CHANGELOG, the gate, commit,
  push, merge request.

Phase A ends with `/fabrik-review-scoped` on its surface; the Finish runs the ONE heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and writes one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I3 (2 IN delivered differently, 1 OUT-OF-SCOPE → W-f7bf9a54) | IN as dispositioned there | Phase A, per the spec rows |
| I2 | *"Plan as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"the matcher in .claude/settings.json:146 → Bash\|Write\|Edit\|NotebookEdit (reviewed commit only — the main checkout's settings are live)"* | OUT-OF-SCOPE — superseded by D-914: the seat holds no write tool (`commands/_agents/fabrik-reviewer.md:4`), so the matcher stays `Bash`; the destination is the tool-list pin, behaviour A1 | Phase A step 2 |
| I4 | *"_in_scratch :283-293 gains the session's own <main>/.tmp/runs/<sid>/"* | OUT-OF-SCOPE — D-914: no seat brief writes there (census in Evidence) and the payload names no main checkout to derive it from; the destination is spec § Contract deltas, which records the census | Evidence |
| I5 | *"graders in tests/test_seat_guard.py (33 today) per spec § Validation 1-6, each seen red first"* | IN | Phase A Behaviour Contract; Global Constraints |
| I6 | *"Sync paths (.claude/hooks/, .claude/settings.json) → full /fabrik-review at build"* | IN (the hook only) | Phase B step 1 |

Intake: 6 items — 4 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; today's code: `spec § What exists today`; external facts:
  `spec § External dependencies`.
- The delta 1-5 and the stated blind spots with the tripwire: `spec § The delta`; contract deltas and the MIRROR census:
  `spec § Contract deltas`; validation 1-7: `spec § Validation`; cost: `spec § Cost`; lifecycle: `spec § Lifecycle`.
- Approach B (judge panel 3/3, D-913), the tool-list pin replacing the tool-write hook (D-914) and the `perl -i` graft:
  `spec § Decisions taken`; rejected A, C, D and a per-seat cwd: `spec § Rejected alternatives`. The approval row is
  minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **Seats only.** Every new rule sits behind `decide()`'s existing early return (`.claude/hooks/seat_guard.py:566-567`):
  no `agent_id`, or an `agent_type` outside `SEAT_TYPES`, is allowed untouched — the lead, implementers and every other
  agent type keep writing as today.
- **Fail open on a guard bug, fail closed on an unknown destination.** `main()` keeps its `except Exception` → allow
  (`:620-627`, the charter); inside the rule, a `$`-bearing or substituted destination is NOT scratch (`_in_scratch`,
  `:284-285`), and neither is one starting with `~`.
- **Destinations only.** A read of the live tree (`cat`, `cp <live> <scratch>/`, `git -C <live> show`) stays allowed.
- **Relative destinations join the tracked cwd** (`os.path.join(ctx["cwd"], p)`) before `_in_scratch`, whose
  `realpath` (`:286`) would otherwise resolve against the hook process's own cwd. The tracked cwd is the shell's:
  `env -C` moves it for its own command only, and a command's redirects resolve against the cwd before it.
- **No settings change.** `.claude/settings.json` is untouched (D-914).
- **No new dependency**; `shlex`, `os.path` and `re` only (`core/10-python.md:38`).
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`), through the existing subprocess
  harness `_run()` (`tests/test_seat_guard.py:24-50`) and its `_denied()` (`:53`); red-on-revert runs in a throwaway
  worktree (`git worktree add --detach <scratch>/probe HEAD`), never the shared checkout.
- Seats never mutate git state; never read `~/.claude*`; seat scratch paths are absolute and each seat `cd`s to its own
  scratch first; a seat never executes a script it has not read.
- **Execution discipline (native seats only, D-181):** Phase A ends with `/fabrik-review-scoped` (the floor of three
  native seats on different angles, stamped with `command_run.py dispatch`) and does not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR — TOOLING surface; MATCHED — seat_guard.py, test_seat_guard.py) | no deps-file edit | `core/10-python.md:38` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — test_seat_guard.py) | one test per behaviour; watched-fail-first; no cosmetic assertions | `core/45-testing-strategy.md:20`, `:21`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, DECISIONS.md, this plan) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `docs/workstation/hooks-index.md` (the hooks authority) | the `seat_guard.py` row names what the hook refuses | `docs/workstation/hooks-index.md:104` |
| `commands/_agents/fabrik-reviewer.md` (the seat's definition, read only) | the tool list the pin asserts | `commands/_agents/fabrik-reviewer.md:4` |
| `fabrik-lib` | nothing parses shell destinations or keys a hook on a subagent type — BUILD in the hook | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | untouched — a hub hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |

## Phase A — the guard

**EXECUTED 2026-10-22** — commits af89164a5, 097ed32f0, fd6dc8083, dc904d604 on `worktree-intel`;
`/fabrik-review-scoped` closed at round 5 with confirmed 0 (series 11 → 10 → 9 → 1 → 0; the Evidence section
holds every round), residue W-9013addb.

Appetite: 120

**Interfaces — Produces** (all in `.claude/hooks/seat_guard.py`, consumed only inside it; the grammar is spec § The
delta 2, 3 and 5, cited rather than restated):
- `_simple_commands()` (`:214-234`) returns a list of `_Cmd(list)` — the words as today, plus a `.redirs` attribute
  holding `(op, target)` for every OUTPUT redirect of spec § The delta 2, kept also for an empty or keyword-only word
  list; an fd number leaves the words only by spec § The delta 2's stream test (`tell(op) - tell(digit) ==
  len(op)`, no quote before the digit). The `["("]`/`[")"]` scope markers (`:227`) stay plain
  equality-comparable lists. `_scan` reads `raw.redirs` BEFORE `_strip` (`:533`), which returns a plain slice.
- `_write_reason(words, redirs, ctx, cwd_before) -> str` — "" or the reason `a review seat writes only under its
  scratch dir — <dest> is outside it`; the destinations are spec § The delta 2's, redirects judged against
  `cwd_before`.
- `_scan()` (`:504-561`) — calls `_write_reason` inside its OWN `try` (panel condition, D-1116: an exception in the new
  rule is caught per command and treated as no write reason, so the existing kill and git rules still judge that
  command), for every simple command right after `_strip` and BEFORE the
  `if not words: continue` (`:534-535`), the `cd`/`pushd` (`:537-547`) and `bash -c` (`:548-557`) `continue`s; then
  `_kill_reason` and `_git_reason` as today (`:558`).
- `_strip()` (`:255-260`) — an `env -C <dir>` changes `ctx["cwd"]` for the stripped command only; the scan restores
  it after the command is judged (spec § The delta 5).
- `_HEREDOC` (`:116`) — `(?<!<)<<(?!<)`, so `<<<` is a here-string, not a heredoc opener (spec § The delta 5).
- the `_UnparseableError` fallback (`:510-517`) — spec § The delta 3; a bare unterminated `echo "x` stays allowed
  (`tests/test_seat_guard.py:231`).
- The module docstring and the reason text name the rule, the blind spots (spec § The delta) and the COBRA line.
- `docs/workstation/hooks-index.md:104` — the `seat_guard.py` row names the write rule and carries the blind-spot list
  of spec § The delta verbatim, as does the module docstring (panel condition, D-1116).

**Steps** (sequential):
1. Write the Phase A graders (Behaviour Contract below) in `tests/test_seat_guard.py`; run them and see each DENY row
   red against today's hook (`.venv/bin/python -m pytest tests/test_seat_guard.py -q`). The rows green today are
   proven by a named neuter in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), each watched
   red and restored: A1 — add `Write` to the `tools:` line; A2 — drop `decide()`'s early return (`:566-567`); A4 —
   drop the `/dev/` and fd exemptions; A5 — judge `cp` sources as destinations, and drop the `-M`/`-m`/`-I` exclusion
   for the `perl -Mstrict` case; A10's allow half — judge the `env -C` command's operands against the cwd from before
   it; A4's new cases — judge a glob by its whole path (`rm -f <scratch>/*.tmp`), drop the `gzip -c` exemption
   (`gzip -c f > <scratch>/f.gz`), and drop the quote check from the fd test (`echo "2>x"`); A8's allow half — match every `>`
   in the fallback; A9 — let the new path's exception escape `main()`.
2. The tool-list pin (A1): a test reading `commands/_agents/fabrik-reviewer.md`'s frontmatter `tools:` line.
3. `_Cmd` with `.redirs` and the fd-number drop in `_simple_commands`.
4. `_write_reason` and its call in `_scan`; the unparseable fallback.
5. Run the whole file green — the 33 existing tests unchanged — then `ruff check` and `ruff format --check` on both files.
6. The docstring and the hooks-index row.
7. False-refusal measure (panel condition, D-1116): replay every Bash command `fabrik-reviewer` seats ran in the
   subagent transcripts since 2026-10-01 (the `scrape_ledger.py --harvest` walk, reading `Bash` tool_use inputs) through
   the new `decide()` with each seat's own cwd and scratch, and paste refusals per N in Evidence. Each refusal of a
   command that wrote only under scratch is a defect fixed before step 8, or a stated cost in spec § The delta.
7b. One live probe: dispatch a `fabrik-reviewer` seat (Agent tool, its scratch absolute, `cd` there first) told to run
   `printf x > <its scratch>/ok` and then `printf x > /opt/fabrik/.claude/worktrees/intel/.seat-probe-<sid>`; paste both
   outcomes in Evidence (the second must be refused) and `git status --short` after the seat (no new file). The hook is
   read from `${CLAUDE_PROJECT_DIR}` at every call (`.claude/settings.json:150`), so the edited file is live in this
   worktree without a reload. The Workflow path is not probed live (hub agents never call it, D-961); its seats carry
   the same `agent_type`, which A3-A7 exercise through the payload.
8. `/fabrik-review-scoped` on Phase A's surface; fix what it finds. A shell-grammar edge case found here, or in
   the Finish review, gets its row in the Behaviour Contract and is decided by the running hook (spec § The delta,
   "Where the grammar is decided").

**Behavior Contract (Phase A):**

- **Given** `commands/_agents/fabrik-reviewer.md`, **When** its frontmatter `tools:` line is read, **Then** it names none of `Write`, `Edit`, `NotebookEdit`, `MultiEdit` (A1)
- **Given** the lead (no `agent_id`) and a `general-purpose` agent, cwd = the repo, **When** `echo x > Makefile` or `rm -rf src`, **Then** allowed (A2)
- **Given** a seat with cwd = the repo, **When** `echo x > Makefile`, `echo x >> docs/a.md`, `ls | tee Makefile`, `cmd &> out.log`, `cmd >& out.log`, `cmd &>2`, `cmd <> Makefile`, `> Makefile`, `{ echo x; } > Makefile`, `(true) > Makefile`, `for i in a; do echo; done > Makefile`, `exec 3> Makefile`, `cp <scratch>/a 2 >/dev/null`, **Then** denied, the reason naming the destination (A3)
- **Given** the same seat, **When** `cmd > /dev/null 2>&1`, `cmd 2>&1 | head`, `cmd >&2`, `echo x > <scratch>/a`, `cd <scratch> && echo x > a`, `mkdir -p <scratch>/d 2>/dev/null`, `truncate -s 0 <scratch>/f`, `rm -f <scratch>/*.tmp`, `dd if=f of=/dev/null`, `ls | tee /dev/stderr`, `cmd > /dev/stdout`, `curl -s -o /dev/null URL`, `gzip -c f > <scratch>/f.gz`, `echo "2>x"`, **Then** allowed (A4)
- **Given** the same seat, **When** `cp <live file> <scratch>/`, `cp -r src <scratch>/s`, `cat Makefile`, `perl -Mstrict -ne print Makefile`, **Then** allowed (A5)
- **Given** the same seat, **When** `cp <scratch>/x Makefile`, `mv a b`, `mv Makefile <scratch>/`, `rsync --remove-source-files Makefile <scratch>/`, `rm -rf src`, `unlink f`, `gzip Makefile`, `touch x`, `mkdir d`, `truncate -s 0 f`, `sed -i s/a/b/ f`, `sed -Ei s/a/b/ f`, `sed --in-place=.bak s/a/b/ f`, `perl -pi -e 1 f`, `perl -i -pe 1 f`, `dd if=/dev/zero of=f`, `install -t bin x`, `cp -rt src <scratch>/x`, `install -d live`, `ln -s <scratch>/x`, `sort -o f in`, `bash -c 'rm -rf src'`, `cd src > log`, `echo x > /dev/../opt/fabrik/Makefile`, **Then** denied (A6)
- **Given** the same seat, **When** `rm -rf "$D"`, `echo x > $(pwd)/x`, `touch ~/x`, `cd <scratch> && touch ~/x`, `rm -rf /tmp/*`, `rm -rf /tmp/claude-<uid>`, `rm -rf /tmp/claude-<uid>/<slug>`, `touch <scratch>/{x,/../../opt/f}`, `rm <scratch>/*/../../opt/f`, `rm -rf /tmp/cl*`, `rm -rf /tmp/claude-<uid>/<slug-prefix>*`, `cp /tmp/s/a "2">/dev/null`, **Then** denied (unknown, home, brace, glob-directory or ancestor-of-scratch destination; a quoted digit is a word) (A7)
- **Given** the same seat, **When** an untokenisable command naming a write (`echo "x > Makefile`), **Then** denied; `echo "unterminated` and `echo "unterminated 2>/dev/null` stay allowed (A8)
- **Given** raw non-JSON stdin, and a seat payload whose new write path raises (injected in-process with `monkeypatch`, the one grader outside `_run()`), **When** the hook runs, **Then** no deny from the write rule — no output for raw stdin, only the existing `updatedInput` envelope for the seat (fail open) — and on `touch x; git reset --hard` with the write path raising, the git rule still denies (A9)
- **Given** the same seat, **When** `env -C <scratch> true; rm -rf src` or `env -C <scratch> true; git reset --hard`, **Then** denied (the cwd move is scoped to its command); `env -C <scratch> touch x` is allowed (A10)
- **Given** the same seat, **When** `cat <<< hi` followed on later lines by `git reset --hard` and `hi`, **Then** denied (a here-string hides nothing) (A11)
- **Given** the same seat, **When** `mkdir -p /opt/fabrik/.tmp/runs/<its sid>/<run>/seat-x`, `mkdir -p <worktree>/.tmp/<run>/seat-x/tree`, `cd .tmp/w1/seat && echo x > out.txt`, **Then** allowed (a repo's gitignored run scratch); `rm -rf` of another sid's `.tmp/runs/<sid>/…`, of `.tmp/runs`, `.tmp`, `.tmp/*` or `.tmp/../src`, **Then** denied (A12 — added by the step-7 replay)
- **Given** the same seat, **When** a variable is assigned a literal earlier on the line (`S=<scratch>/run; mkdir -p $S/seat`, `export S=…; P=${S}/pins`), **Then** it is resolved and allowed; a reassignment to `$(pwd)`, a subshell's assignment, an env prefix (`S=… true`) and an unassigned `"$D"` stay unknown and denied (A13 — step-7 replay)
- **Given** the same seat, **When** an escaped backtick in double quotes, a `'` inside double quotes, `<( )` inside double quotes, `$(…)` inside single quotes, `rsync -an`/`--dry-run`, or `cd <scratch> && S=$PWD && touch $S/x`, **Then** allowed; `echo "$(touch x)"`, `` echo `touch x` ``, `rsync -a src/ /opt/elsewhere/` and `S=$PWD; touch $S/x` from the repo, **Then** denied (A14 — step-7 replay)
- **Given** the same seat, **When** `for m in a b; do … <scratch>/m$m; done` or the loop run inside scratch, **Then** allowed; a loop word with `/` or `..`, `for m in $(ls)`, `for m;` and a loop writing `mm_$m` in the repo, **Then** denied (A15 — step-7 replay)
- **Given** the same seat, **When** a kill or git target is a variable (`P=4242; kill -9 $P`, `S=<scratch>; git -C $S reset --hard`), **Then** denied, as before Phase A — variables are resolved for write destinations and `cd` only (A16 — review round 1)
- **Given** the same seat, **When** the line may have changed a variable since its literal assignment (`unset`, `read`, `printf -v`, `declare -g`, `eval`, `+=`, a `do`/`then` body, a pipeline or background assignment, one after `false &&`, a value with whitespace or a glob, a `bash -c` child, a loop variable mid-path over `tmp opt`), **Then** denied; an unbroken `&&` chain and `$PWD` after `cd <scratch> &&` stay allowed (A17 — round 1)
- **Given** the same seat, **When** `grep -n '>' Makefile`, `grep -c ";" Makefile`, a `#` inside a multi-line quoted script, or a trailing comment holding `>`, **Then** allowed; `touch '$S'`, `touch \$S`, a nested backtick, a `$'…'` hiding `$(…)` or a backtick, a heredoc opener inside quotes or after `#`, `bash -e -c "git status; git reset --hard"`, **Then** denied (A18 — round 1)
- **Given** the same seat, **When** `cd <existing scratch>; touch x` or `mkdir -p <scratch>/new/x; cd <scratch>/new/x; touch y`, **Then** allowed; `cd <scratch>/missing; touch x`, `cd <scratch> | cat; touch x`, an earlier `curl -o /etc/x`, `rsync` whose `-n` is an option's value or follows `--`, an untokenisable `curl -o`/`&>`, `/home/u/.tmp/x`, `kill ²; pkill -f mail`, **Then** denied; a repo inside another session's `/tmp` tree lends no `.tmp` scratch (A19, A19b — round 1)
- **Mocked:** only A9's crash injection (`monkeypatch` on the new write path, in-process); every other grader runs the real hook as a subprocess on a synthetic payload (`_run()`); A1 reads the real agent definition.

## Phase B — Finish

Appetite: 60

**Steps** (sequential):
1. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice as
   Agent-tool seats (D-961), the orchestrator executing every candidate), its receipt
   `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`.
2. `CHANGELOG.md` entry (`### Changed — review seats cannot write outside their scratch (<the commit date>)`); a
   `docs/DECISIONS.md` row only if the build takes a decision the spec did not (D-913, D-914 are the design rows; the
   approval row is `/fabrik-plan-review`'s).
3. After the merge, re-run step 7b's probe against the merged hook in the main checkout's session and paste it in
   the review receipt (panel condition, D-1116).
4. `python scripts/final_gate.py --check --json` green; commit by pathspec with trailers; push; `merge_request.py
   request --review <receipt> --item W-72dfd448`.

## File Scope (owned paths)

- `.claude/hooks/seat_guard.py`
- `tests/test_seat_guard.py`
- `docs/workstation/hooks-index.md` (only the `seat_guard.py` row, `:104`)
- `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md`
- `docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-plan-review.md` (this plan review's own
  receipt, when one is written)
- `CHANGELOG.md` (one entry)

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env added | CLEAN — no new env var or file sink; hunted: Phase A Interfaces |
| MATCHED core/40-documentation | one CHANGELOG entry; the hooks-index row; D-914 in the same change as the spec refinement | CLEAN — Phase B step 2, Phase A step 6, this plan's commit |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red | CLEAN — A1-A11 map spec § Validation 1-7 (Self-audit); A1's red is proven on revert |
| RECURRENCE fail-open vs fail-closed | guard crash → allow; unknown destination → deny | FIXED r1 — A7, A9 (A9 re-stated: a crash leaves the seat's `updatedInput` envelope, never a deny) |
| RECURRENCE cost/quota/limit accounting | none | CLEAN — no new hook invocation, no seat or quota change |
| RECURRENCE boundary/sentinel/prefix collisions | `/tmp` and its ancestors of other sessions' scratch, globs; `/dev/*` by the lexical `normpath`; glued vs spaced fd numbers; `>&` dup vs `&>` file; option values read as operands | FIXED r1 — spec § The delta 2 names each; A3, A4, A6, A7 grade them (round 1: ancestors and globs were scratch, `2 >` was an fd) |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A row; every row green today has a named red | FIXED r1 — Self-audit mapping; Phase A step 1 names each neuter |

Rubric invocation (verbatim output; the File Scope is the changed-path set):

```text
$ python scripts/review_rubric.py --changed .claude/hooks/seat_guard.py tests/test_seat_guard.py docs/workstation/hooks-index.md docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md CHANGELOG.md docs/DECISIONS.md
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
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

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

### core/40-documentation.md  (hit: CHANGELOG.md, docs/DECISIONS.md, docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_seat_guard.py)
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
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 36 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

## Evidence

Grounded at authoring (2026-10-15), executed. Three grounding seats ran (an Opus `fabrik-reviewer` on the hook's
anchors and callers, a Sonnet `fabrik-reviewer` census of every seat brief, a Sonnet `fabrik-researcher` on the hook
payload docs); their findings are folded into the spec and Phase A, each re-executed below.

- The seat's tools — `commands/_agents/fabrik-reviewer.md:4`:

```text
$ grep -n "^tools:" commands/_agents/fabrik-reviewer.md
4:tools: Read, Grep, Glob, Bash
```

- Today's tokeniser and scratch test (`.claude/hooks/seat_guard.py:214-234`, `:283-293`), imported from the file with
  `python3 -B`: the redirect target is dropped, an fd number and option values land among the words, `-pi` stays one
  token, `.tmp/runs` and a relative path are not scratch:

```text
$ python3 -B probe_tokens.py
'mkdir -p /tmp/s/x 2>/dev/null' -> [['mkdir', '-p', '/tmp/s/x', '2']]
'echo x > Makefile' -> [['echo', 'x']]
'truncate -s 0 /tmp/f' -> [['truncate', '-s', '0', '/tmp/f']]
'perl -pi -e s/a/b/ f' -> [['perl', '-pi', '-e', 's/a/b/', 'f']]
/tmp/foo True
/opt/fabrik/.tmp/runs/S/x False
relative/x False
```

- The brief census (spec § Contract deltas): 32 files searched at authoring; every seat write the briefs prescribe
  lands under `RUN-SCRATCH` (`.claude/workflows/fabrik-review-loop.js:258`, `:272`, `:230`;
  `commands/_fragments/subagents-core.md:5`); no brief names `.tmp/runs` for a seat. Re-checked 2026-10-22 for the
  Agent-tool path D-961 made the hub's only one: `commands/_fragments/no-workflow-hub.md` gives each seat its
  absolute scratch folder too. An adopted run folder is renamed INTO the adopting session's pad
  (`scripts/command_run.py::_adopt_run_scratch`, "move the wall seed's `resumable` folder into THIS session"), so it
  never sits under another session's `/tmp` dir.
- The `_HEREDOC` change (spec § The delta 5), run 2026-10-22 on a throwaway worktree of 21744dd43 with line 116
  patched to `r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1"`: the 33 existing tests stay green, a
  here-string hides nothing, and both heredoc forms still strip:

```text
$ pytest <probe>/tests/test_seat_guard.py -q
33 passed in 9.71s
$ _strip_heredocs('cat <<< hi\nrm -rf src\nhi\necho done') -> 'cat <<< hi\nrm -rf src\nhi\necho done'   (was 'cat <<< hi\necho done')
$ _strip_heredocs('cat <<EOF\nbody\nEOF\nls')               -> 'cat <<EOF\nls'
$ _strip_heredocs('cat <<-EOF\n\tbody\n\tEOF\nls')          -> 'cat <<-EOF\nls'
```

- The glued-fd test on the tokeniser's own stream (spec § The delta 2), run 2026-10-22 with `shlex.shlex(io.StringIO(s),
  posix=True, punctuation_chars=True)`, `whitespace_split=True`, recording `instream.tell()` after each token: the gap
  before the operator is zero exactly when `tell(op) - tell(digit) == len(op)` (round 3 also ran `>&`, `>>` and
  quoted `"2">x`, which is why the rule carries the operator length and the quote check):

```text
'cp /tmp/a 2 >/dev/null' -> [('cp', 3), ('/tmp/a', 10), ('2', 12), ('>', 14), ('/dev/null', 22)]
'cp /tmp/a 2>/dev/null'  -> [('cp', 3), ('/tmp/a', 10), ('2', 12), ('>', 13), ('/dev/null', 21)]
```

- **Executed 2026-10-22 — Phase A, steps 1-5.** A3 and A6-A11 were seen red against today's hook first. The rows
  green today were proven by a neuter in a throwaway worktree of `9fa2aef1f`
  (`git worktree add --detach <scratch>/rv/probe HEAD`, edited hook and tests copied in, each neuter applied alone,
  its rows run, the file restored). Two plan wordings did not hold. A4's glob neuter is "treat every glob as unknown":
  "judge a glob by its whole path" does not redden, because the whole path is still inside scratch. And `echo "2>x"`
  has no possible red, because shlex keeps quoted punctuation inside one token; the quote check's red is A7's
  `"2">x`.

```text
RED  A1 add Write to the tools line: 1 failed, 43 deselected
RED  A2 drop decide()'s early return: 1 failed, 43 deselected
RED  A4 drop the /dev exemption / the fd-dup exemption / treat every glob as unknown / drop the gzip -c exemption: 1 failed each
RED  A5 judge cp sources as destinations / drop the -M/-m/-I exclusion: 1 failed each
RED  A8 match every > in the fallback: 1 failed
RED  A9 let the write rule's exception escape: 1 failed
RED  A10 judge env -C operands against the cwd before it: 1 failed
all neuters red
```

- **Step 7, the false-refusal replay (D-1116 condition 2).** Population: every
  `~/.claude/projects/*/*/subagents/agent-*.meta.json` with `agentType: fabrik-reviewer` whose transcript holds a
  Bash `tool_use` dated 2026-10-01 or later. That covers every repo's seats, not only the hub's. Subagent transcripts
  are pruned after 3 days (CLAUDE.md § Pointers, D-736), so the window really covers about 2026-10-19 to 2026-10-22.
  Each command went through the new `decide()` and the old one (HEAD's hook), using the seat's own cwd, its lead's
  session id and that session's scratchpad.
  "New refusals" are commands the old hook allowed and the new one refuses.

```text
first replay (steps 1-6 hook):  seats=2005 commands=54727 old_refusals=92 new_refusals=2713 errors=0
  1992 /opt/fabrik-lib/.claude/worktrees/<wt>/.tmp/…   418 /opt/fabrik/.tmp/runs/<sid>/…   ~250 `S=<scratch>…; … $S/…`
final replay (fixed hook):       seats=2011 commands=54965 old_refusals=92 new_refusals=42 errors=0
```

  The 2,713 refusals were false refusals in four classes, each fixed with a grader: the repo run scratch
  `<repo>/.tmp/…` (A12), a literal variable assigned on the line (A13), the extractor's quote handling plus `$PWD` and
  `rsync -n` (A14), and a `for` loop over plain words (A15). This disproves the census above: seats were briefed
  into `.tmp/runs/<sid>/` (the D-836 RUN-SCRATCH) and into fabrik-lib's `<worktree>/.tmp/<run>/`. Nine of the 42
  remaining refusals are true positives, writes the rule exists to stop:

  - `rm` of `/opt/fabrik/.claude/worktrees/fleet/p.py`;
  - `mv` of `…/fleet/r2.tar` and of `…/fabrik-lib-sentinel/base.tar`;
  - `printf … > p4.py` and `> scratchp.py` written into a live worktree;
  - a double-quoted `$(touch pwned)` that bash ran in infra's worktree;
  - `touch`/`rm` under `~/.claude/bin/backups`.

  The other 33 refusals:

  - 9 are commands bash rejects too (`bash -n` errors), so no cost.
  - 9 are an unknown value inside the seat's own scratch: `$(…)`, a function's `$1`, a loop over words containing `/`,
    an unset `$R`. These fail closed, as spec § The delta requires.
  - The rest (8 + 7) are the stated cost. 8 are writes into `/tmp/claude-<uid>/` outside any session tree
    (`x133b`, `sb083-dummy-never.sql`), dirs those seats improvised. 7 are mis-parses: a single-quoted literal `$` in
    a path (4, one seat's injection probe), a quoted `{` in `HEAD^{tree}`, nested `bash -c` quoting, and one
    shlex/bash split on a double-quoted `\$b\$`.

  The cost is 15 refusals in 54,965 seat commands (0.027%), and each refusal names its fix (write under scratch).
  Fifteen old git refusals no longer fire. Every one is `git -C $S/…` or `$PWD/wt` resolving to the seat's own
  scratch, or a git word inside quoted printf data. Each was read and is correct.

```text
RED  A12 no repo .tmp scratch / any run sid is ours / .tmp itself is scratch: 1 failed each
RED  A13 no expansion / a computed value keeps the old literal / a subshell's vars survive / an env prefix sets a shell var: 1 failed each
all neuters red
```

- **Step 8, `/fabrik-review-scoped` round 1** (ROUTED-TO-FINISH: a hook path, `Profile: small`). Three
  author-blind `fabrik-reviewer` seats (Sonnet, Haiku, Opus) ran on pin `pins-1` of `40a2ac5d7` plus the work tree.
  They raised 33 candidates, which reduce to 11 confirmed root causes, all fixed:

  - **R1:** variable resolution reached the kill and git rules. `P=4242; read P <<< -1; kill -9 $P` and
    `S=<scratch>; unset S; git … reset --hard` were allowed where the old hook refused them.
  - **R2:** the variable table missed `unset`, `read`, `printf -v`, `declare`, `eval`, `+=`, conditional bodies,
    pipelines, background jobs, `&&`/`||`, and values with whitespace or a glob.
  - **R3:** `bash -c` inherited variables.
  - **R4:** a loop judged only its first value.
  - **R5:** `'$S'` was expanded, and a quoted `'>'` read as a redirect.
  - **R6:** `.tmp` counted anywhere, outside a repo and inside another session's `/tmp` tree.
  - **R7:** `$'…'` and nested backticks hid substitutions.
  - **R8:** a heredoc opener inside quotes or after `#` counted, and shlex's comment cut swallowed the next line.
  - **R9:** `kill ²` raised and the whole hook failed open.
  - **R10:** `rsync -n` was read from option values, only the last `curl -o` was judged, and the fallback missed
    `sort`/`curl`/`wget` and `&>`.
  - **R11:** a pipeline `cd`, or a `cd` into a missing directory, moved the cwd.

  Graders A16-A19b cover them. Every fix was undone alone in a throwaway worktree and its rows watched red (25
  neuters); the first ANSI-C row stayed green because `_protect` caught it too, so a backtick row only the
  extractor sees was added and went red. Recorded as blind spots rather than fixed: a symlink made earlier on the
  same line, and a `$(…)` body not seeing the outer line's variables (a false refusal).

```text
RED R1 kill/git words see expanded variables · RED R2 ×7 · RED R3 · RED R4 · RED R5 · RED R7 ×2 · RED R8 ×3
RED R9 · RED R10 ×4 · RED R11 ×2 · RED R6 ×2 — all neuters red
replay after round 1 (cd taken as succeeded): seats=2037 commands=55791 old_refusals=94 new_refusals=40 errors=0
```

  The six old refusals the new hook no longer makes were each read: three are quoted printf data the old hook
  misread, and three are `S=<scratch>; cd $S; git init`, where `cd` now resolves the literal into scratch. Of
  6,785 `cd X` lines not guarded by `&&`, 179 make X earlier on the same line; `mkdir -p x; cd x` is therefore
  counted as existing.

- **Step 8, rounds 2 and 3** (the round-1 seats re-verified their own claims on pins `pins-2` and `pins-3`, then
  hunted each round's fix diff plus one hop).

  Round 2 confirmed 10, 6 of them own-fix:
  - `for * in x` made `re.compile` raise and switched the write rule off for the line;
  - `$'…'` hid a heredoc from the line scanner;
  - an `&&`-guarded `cd` stayed certain after its chain;
  - wrapped `IFS= read`/`builtin`/`command`/`printf -vS` did not clear the table;
  - glob loop words were refused;
  - creators of a `cd` target were missing.

  The other 4 were the artifact's own:
  - `case` arms;
  - `$((a<<b))` as a heredoc opener;
  - the "gitignored" wording;
  - a glob through a link in scratch.

  Round 3 confirmed 9, 8 of them own-fix in round 2's code:
  - the new glob walk took 48 s against the hook's 5 s timeout (`.claude/settings.json:150-151`), so the hook could
    be killed undecided;
  - a `venv` word, a failing `cp`/`git clone`, or a `mkdir` without a parent "made" a directory;
  - `for d in *` through a link;
  - a variable `mkdir` operand;
  - `--depth` in a clone;
  - a subshell's unsure `cd`.

  The ninth was pre-existing: a multi-line quoted string faked a heredoc. Silence at round 3 left the verdict to the
  lead. Most defects were the review's own, so this is the scope-growth stop (D-355). Round 3 subtracted rather
  than patched:
  - no tree walk: a glob's own directory is listed once for a link out;
  - only `mkdir` makes a directory;
  - the quote state carries across lines.

  The rest are recorded costs:
  - `git worktree add x; cd x`, `tar -C`, `unzip -d` and `venv` need `&&`;
  - `rm -rf <scratch>/*` beside a link out is refused;
  - a link in a deeper glob directory is not seen.

  Graders A20, A21. Red on revert: 13 round-2 neuters and 7 round-3 neuters, all red. Replay after round 3:

```text
seats=2066 commands=56669 old_refusals=94 new_refusals=43 errors=0   (each cd taken as succeeded)
```

  Round 4 was the remainder round: the fixed set only. All of round 3's items were fixed, or are now stated costs;
  no input exceeded 0.01 s against the 5 s budget, and 15,000 fuzzed commands raised nothing. One own-fix loosening
  remained: the quote carry misread `x="$(echo "'")"` as leaving `'` open, so a heredoc opener on the next line hid
  a `git reset --hard`. It was fixed monotonically: a line that starts inside a carried quote never opens a
  heredoc, so the carry can only suppress one. The new A21 row went red on revert. `command_run.py` printed
  `⚠️ SCOPE GROWTH` (10/6 → 9/8 → 1/1).

- **Step 7b, the live probe (D-1116 condition 3, before merge).** One Haiku `fabrik-reviewer` Agent-tool seat ran
  against the edited hook in this worktree:

```text
1. cd <scratch>/rv/seat-probe && pwd                         ALLOWED  <scratch>/rv/seat-probe
2. printf x > <scratch>/rv/seat-probe/ok && cat …/ok           ALLOWED  x
3. printf x > /opt/fabrik/.claude/worktrees/intel/.seat-probe-5ce9d888
   REFUSED  PreToolUse:Bash hook error: seat guard (review seats run in the lead's shared tree): a review seat writes
   only under its scratch dir — /opt/fabrik/.claude/worktrees/intel/.seat-probe-5ce9d888 is outside it. run a git
   write only as `git -C <absolute repo under your scratch dir>` … never kill by pattern — kill a numeric pid you started.
$ ls /opt/fabrik/.claude/worktrees/intel/.seat-probe-5ce9d888
ls: cannot access '…/.seat-probe-5ce9d888': No such file or directory
$ git status --short    # only this phase's own edits; no file from the seat
```

- External: https://code.claude.com/docs/en/hooks (subagent `agent_id`/`agent_type`; exact-string matchers) and
  https://code.claude.com/docs/en/tools-reference (no MultiEdit row), fetched 2026-10-15 (exa, WebFetch).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: spec 1 → A1, 2 → A2, 3 → A3/A4, 4 → A5/A6/A7, 5 → A8, 6 → A9,
  7 → A10/A11.
- Every item in What we already agreed maps to Phase A (delta 1-5) or Phase B (review, CHANGELOG, merge request).
- Diff estimate ≈250 code lines in 1 code file (tests excluded) after rounds 1-3: inside `Profile: small` (≤ ~400, ≤ 5).
- Cross-phase names: `_Cmd`, `.redirs` and `_write_reason` are produced and consumed in Phase A only.
- Every touchpoint is a `path:line` in today's hook, re-read by the Opus grounding seat (its drift corrections are
  applied: `decide` `:564-582`, `_scan` `:504-561`, `main` `:611-647`).

## Residual unknowns

- **R1 — resolved.** The live tool-write payload no longer matters: the seat has no write tool (D-914).
- **R2 — resolved.** An adopted RUN-SCRATCH folder lies in the adopting session's pad (Evidence), so `_in_scratch`'s
  other-session test never refuses it.
- **R3 — open, by design.** The blind spots in spec § The delta (interpreters, `xargs`/`find` writes, depth > 3, a
  `$(…)` body judged against the cwd from before the line's `cd`, unlisted verbs and forms,
  side-effect writes such as `.pytest_cache`) stay; the tripwire there names the resolution.

## Pass Ledger

Written by `/fabrik-plan-review` (2026-10-22). Two author-blind section seats: an Opus seat on § Global Constraints,
§ Phase A and spec § The delta / Contract deltas / Validation, and a Sonnet seat on every other section of both files.
The orchestrator executed the refutations.

| Pass | Finders | Counters | Method |
|---|---|---|---|
| Pass 1 | native opus×1 + sonnet×1 (sections A, B) | found: 24, new: 24, confirmed: 15, fixed: 15, unexecuted: 0 | method: tokeniser, `_in_scratch` and hook-subprocess probes on a pinned copy; every cite opened |
| Pass 2 | same seats, own sections | found: 11, new: 11, confirmed: 6, fixed: 6, unexecuted: 0 | method: re-verification over the round-1 fold; the `_HEREDOC` change run on the 33 existing tests |
| Pass 3 | same seats, own sections | found: 7, new: 7, confirmed: 5, fixed: 5, unexecuted: 0 | method: re-verification; the scope-growth stop fired (own-fix 4 of 6, then 5 of 5) |
| Pass 4 | same seats, the fixed set only | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0 | method: the fixed hunks re-run as a path-rule model and a shlex-offset run; further grammar routed to Phase A |
| Pass 5 | same seats, the fixed set only | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation of every round-4 fix (model and shlex runs) and the routing paragraph |

Artifact hashes at the closing pass: plan `11a9471760f195df0a8e28c29424cf0d`, spec `1800d4ffef2c9344c42b7b11779a9a56`
(before this ledger and the Status flips).
