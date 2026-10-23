# Plan — review seats: write isolation in the seat guard (W-72dfd448)

Status: DRAFT
Profile: small
**Owner:** intel
**Surface:** `git rev-parse HEAD` = 4efc5d325 at authoring; Phase B first re-planned at 3dd31656e (the fence), and
re-planned again at d0a3ece02 for P2 (§ Phase B), where
`.claude/hooks/seat_guard.py` is 1479 lines and `tests/test_seat_guard.py` holds 55 tests (Evidence, "P2 re-plan
grounding"); `commands/_agents/fabrik-reviewer.md:4` (read, not edited)

Spec: `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md` (CONVERGED 2026-10-23, D-1160:
§ Amendment 2026-10-23, P2 — review seats in a dedicated reviewer session under Claude Code's own Bash sandbox, the
parser kept as the per-seat layer; it supersedes D-1158, which had reopened D-1145's fence approval after Validation
10 failed). Phases B-D re-planned 2026-10-23 at d0a3ece02 from that amendment; Phase A stays as built; the fence code
stays reverted (6dc45645f). The spec was approved by `/fabrik-spec-review`'s panel, so this plan review runs alone (no
joint loop). Source: mail 01M4PHYNXJ → work item W-72dfd448; design rulings D-913, D-914, D-1129, D-1145. Phase A as
BUILT measured 874 hook lines added and 46 removed, and 404 test lines (`git diff --numstat 95d14ca0f HEAD`, Evidence) —
far past its estimate and past the `Profile: small` line; the profile is kept for the work still to run (Phase B no
code; Phase C ≈210 code lines in 2 code files, an estimate, Self-audit), where it holds (≤ ~400, ≤ 5 files), and Phase
A's overrun is recorded here, measured. Phase A's original estimate, kept for the record: ≈250 code lines in ONE code file, `.claude/hooks/seat_guard.py`
(redirect capture with the empty-list case and the stream-offset fd test in `_simple_commands` ≈45, the destination
rule `_write_reason` with its per-verb option tables, glob prefix and `/dev` exemption ≈130, its call before
`if not words` and every `continue` in `_scan` ≈10, the `env -C` scoping ≈10, the `_HEREDOC` fix ≈1, the unparseable
fallback ≈10, docstring ≈45); tests ≈220 lines in `tests/test_seat_guard.py`; one row in
`docs/workstation/hooks-index.md`.

## What this plan is

Four inline phases (A executed; B, C and D re-planned, so three still to run — `Profile: small`'s ≤3) the orchestrator codes itself in the `worktree-intel` worktree; no coder is dispatched:

- **A — the guard**: the shell write rule, the unparseable fallback, the tool-list pin, the docstring and the
  hooks-index row and the two scanner fixes (spec § The delta items 1-5).
- **B — the first live proof** (P2, D-1160): a prototype launcher in the run scratch starts one reviewer session, one
  seat inside it runs the checks of spec item 4; no repository code; a failed MUST check stops the plan.
- **C — the launcher and the per-seat refusals**: `scripts/review_session.py`, the hook's refusal table (measured,
  anchored, matched on the unquoted skeleton) and its seat crash-denies, the docs, and the mail to kaizen.
- **D — Finish**: the whole-plan `/fabrik-review` (the hook is a governance-sync path), CHANGELOG, the gate, commit,
  push, merge request, and the post-merge re-run of the proof.

Phases A, B and C each end with `/fabrik-review-scoped` on their surface; the Finish runs the ONE heavy
`/fabrik-review` (the `/fabrik-execute-plan` D7 floor) and writes one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I3 (2 IN delivered differently, 1 OUT-OF-SCOPE → W-f7bf9a54) | IN as dispositioned there | Phase A, per the spec rows |
| I2 | *"Plan as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"the matcher in .claude/settings.json:146 → Bash\|Write\|Edit\|NotebookEdit (reviewed commit only — the main checkout's settings are live)"* | OUT-OF-SCOPE — superseded by D-914: the seat holds no write tool (`commands/_agents/fabrik-reviewer.md:4`), so the matcher stays `Bash`; the destination is the tool-list pin, behaviour A1 | Phase A step 2 |
| I4 | *"_in_scratch :283-293 gains the session's own <main>/.tmp/runs/<sid>/"* | OUT-OF-SCOPE — D-914: no seat brief writes there (census in Evidence) and the payload names no main checkout to derive it from; the destination is spec § Contract deltas, which records the census | Evidence |
| I5 | *"graders in tests/test_seat_guard.py (33 today) per spec § Validation 1-6, each seen red first"* | IN | Phase A Behaviour Contract; Global Constraints |
| I6 | *"Sync paths (.claude/hooks/, .claude/settings.json) → full /fabrik-review at build"* | IN for the hook; `.claude/settings.json` is no longer touched (P2 registers the hook in the launcher's `--settings`) | Phase D step 1 |
| I7 | the coordinator, 2026-10-23: *"resume W-72dfd448 — /fabrik-spec-review on … the D-1129 amendment, then the plan-2 Phase B re-plan"* | IN, delivered as the fence attempt, which BLOCKED at Validation 10 | § Evidence, "Phase B fence attempt (superseded by D-1160)" |
| I8 | D-1129 / D-1145: the fence replaces the parser as the boundary; the parser stays as the fail-closed fallback | OUT-OF-SCOPE — superseded by D-1160 (the harness refuses the wrapped command); the destination is spec § Amendment 2026-10-23 | — |
| I9 | the coordinator, 2026-10-23: *"let /fabrik-spec-review's Opus + Fable panel decide among (a) … (b) … (c)"*; the panel chose P2 (D-1160) | IN | Phases B-D |
| I10 | spec item 4: *"The review briefs that rely on a localhost probe are listed and each is accepted as `unverified` or rerouted"* | IN | Phase B step 6, Phase C step 6 |

Intake: 10 items — 7 IN, 3 OUT-OF-SCOPE (each named above), 0 ASK.

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; today's code: `spec § What exists today`; external facts:
  `spec § External dependencies`.
- The delta 1-5 and the stated blind spots with the tripwire: `spec § The delta`; contract deltas and the MIRROR census:
  `spec § Contract deltas`; validation 1-7: `spec § Validation`; cost: `spec § Cost`; lifecycle: `spec § Lifecycle`.
- Approach B (judge panel 3/3, D-913), the tool-list pin replacing the tool-write hook (D-914) and the `perl -i` graft:
  `spec § Decisions taken`; rejected A, C, D and a per-seat cwd: `spec § Rejected alternatives`. The approval row is
  minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).
- P2 and its five binding changes: `spec § Amendment 2026-10-23`, Panel decision (`spec:380-418`), approved by D-1160 —
  the approval row exists, so this plan mints none for the spec.

## Global Constraints (every phase inherits these)

- **Seats only.** Every new rule sits behind `decide()`'s existing early return (`.claude/hooks/seat_guard.py:1394-1395`):
  no `agent_id`, or an `agent_type` outside `SEAT_TYPES`, is allowed untouched — the lead, implementers and every other
  agent type keep writing as today.
- **Fail open on a guard bug, fail closed on an unknown destination** (Phase A). Phase C narrows it for SEAT payloads:
  a `decide()` exception denies (`spec:147-149`, applied always since there is no fence), and so does a write-rule
  exception, a new Phase C decision recorded in its commit's D-row (it supersedes, for seat payloads, D-1116's
  per-command catch that reads a crash as "no reason");
  `main()`'s `except Exception` → allow stays for the non-seat path (`:1452-1455`); inside the rule, a `$`-bearing or
  substituted destination is NOT scratch (`_in_scratch`, `:581-582`), and neither is one starting with `~`.
- **Destinations only.** A read of the live tree (`cat`, `cp <live> <scratch>/`, `git -C <live> show`) stays allowed.
- **Relative destinations join the tracked cwd** (`os.path.join(ctx["cwd"], p)`) before `_in_scratch`, whose
  `realpath` (`:583`) would otherwise resolve against the hook process's own cwd. The tracked cwd is the shell's:
  `env -C` moves it for its own command only, and a command's redirects resolve against the cwd before it.
- **No settings change.** `.claude/settings.json` is not touched (the matcher stays `Bash`, D-914); the reviewer
  session registers the hook through the launcher's `--settings` (`spec:398-401`); no agent edits permission settings.
- **No new dependency**; the standard library only (`core/10-python.md:38`): `json`, `os`, `re`, `shlex` and
  `subprocess` are already imported (`:105-111`). The `claude` CLI is a HOST prerequisite, not a package: Phase B's
  preflight probes it and its flags, and `scripts/review_session.py` fails loudly when it is absent.
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`), through the existing subprocess
  harness `_run()` (`tests/test_seat_guard.py:24-50`) and its `_denied()` (`:53`); red-on-revert runs in a throwaway
  worktree, never the shared checkout. A reviewer session's directory is fresh under `/tmp/claude-<uid>/`, never under
  `/opt` and never a git work tree (`spec:386-387`).
- Seats never mutate git state; never read `~/.claude*`; seat scratch paths are absolute, and a seat `cd`s only on the same line as the command
  that needs it; a seat never executes a script it has not read.
- **Execution discipline (native seats only, D-181):** Phases A, B and C each end with `/fabrik-review-scoped` (the floor of three
  native seats on different angles, stamped with `command_run.py dispatch`) and do not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR — TOOLING surface; MATCHED — seat_guard.py, test_seat_guard.py) | no deps-file edit | `core/10-python.md:38` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — test_seat_guard.py) | one test per behaviour; watched-fail-first; no cosmetic assertions | `core/45-testing-strategy.md:20`, `:21`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, DECISIONS.md, this plan) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `docs/workstation/hooks-index.md` (the hooks authority) | the `seat_guard.py` row names what the hook refuses | `docs/workstation/hooks-index.md:107` |
| `commands/_agents/fabrik-reviewer.md` (the seat's definition, read only) | the tool list the pin asserts | `commands/_agents/fabrik-reviewer.md:4` |
| `fabrik-lib` | nothing parses shell destinations or keys a hook on a subagent type — BUILD in the hook | `spec § fabrik-lib verdict` |
| § Amendment 2026-10-23 (CONVERGED, D-1160) | P2: the reviewer session, the launcher, the per-seat layer, the first proof — Phases B and C build against it verbatim | `spec:380-418` |
| § Amendment 2026-10-22 Design 3 (the refusal list) | the constructs the parser does not model, refused for a seat | `spec:141-149` |
| `.windsurf/rules/core/30-ops.md` (judgment read; the surface is TOOLING) | a shelled-out binary is never assumed — `claude` is probed with its flags | `core/30-ops.md:464` |
| `scripts/cloud_dispatch.py` (read, not edited) | the headless `claude -p` shape to reuse: the prompt on stdin, a scratch cwd, timeouts as errors | `scripts/cloud_dispatch.py:402-418` |
| `scripts/rivals_run.py` (read, not edited) | a parsed `claude -p` run sets `FABRIK_HEADLESS=1` and `CLAUDE_MESH_HEADLESS=1` so no hook banner reaches its output | `scripts/rivals_run.py:536` |
| Claude Code docs (fetched 2026-10-23) | `--settings` inline JSON overrides per key; hooks merge across levels; subagents share the session's sandbox and hooks; `--permission-mode auto`; `localhost` private and `docker` incompatible in the sandbox | § Evidence, "P2 re-plan grounding" |
| `specs/services/*.yaml` `shape:` | untouched — a hub hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| A twelve-factor app never relies on implicit existence of system-wide packages | `.windsurf/rules/core/30-ops.md:464` |

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

## Phase B — the first live proof (re-planned 2026-10-23 for P2, D-1160; no repository code)

Appetite: 60

Implements `spec § Amendment 2026-10-23`, Panel decision items 1, 2 and 4
(`docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md:385-415`), cited, never restated. The fence
attempt this phase replaces (D-1129, BLOCKED at Validation 10) is kept in § Evidence, "Phase B fence attempt
(superseded by D-1160)"; its code stays reverted (6dc45645f). Item 4 binds the order: this proof runs before any build,
and nothing in Phase C starts until it is green.

**Interfaces — Produces** (scratch only, never a repository file):
- `<run scratch>/proof_launch.py` — builds the reviewer session's `--settings` JSON (item 1's sandbox block plus a
  `hooks.PreToolUse` entry, matcher `Bash`, whose command is `python3 <hook path>` with an absolute path), mints a
  session id (`uuid4`) and makes the session directory `/tmp/claude-<uid>/review-session/<that id>/` (never under `/opt`,
  never a git worktree; the `<slug>/<sid>` shape is the one the hook's `_TMP_SESSION` (`.claude/hooks/seat_guard.py:147`)
  reads as THIS session's scratch, since the seats' payload carries the session's id — a bare `/tmp/claude-<uid>/<dir>/`
  reads its second segment as another session's id and is refused), and runs
  `claude -p --session-id <that id> --permission-mode auto --permission-prompts none --output-format json --max-turns 40 --settings <json>`
  with the brief on stdin and that directory as cwd, the env adding `FABRIK_HEADLESS=1` and `CLAUDE_MESH_HEADLESS=1`
  (`scripts/rivals_run.py:536`). The stdin-prompt, scratch-cwd shape is `scripts/cloud_dispatch.py:402-412`'s.
  The hook path is the WORKTREE's `.claude/hooks/seat_guard.py` (absolute), because the main checkout's copy predates
  Phase A until the merge (Evidence, "P2 re-plan grounding"). Phase C's launcher is this prototype made permanent.
- `<run scratch>/proof-brief.md` — the reviewer session's brief: dispatch ONE `fabrik-reviewer` seat (`model: "haiku"`)
  that runs checks P1-P7 below, one plain command per Bash call, and writes its report to `<session dir>/seat-1/`;
  then write `<session dir>/receipt.md` with each check's command, rc and stderr.

**Steps** (sequential; the orchestrator runs them inline in `worktree-intel`):
1. Preflight: `claude --version` (2.1.309 at authoring), and `claude --help` lists `--permission-mode` with `auto`
   among its choices, `--permission-prompts`, `--settings`, `--session-id` and `--output-format` (Evidence). Missing ⇒
   BLOCKED, missing infra. `--max-turns` is absent from `--help` on 2.1.309 but documented
   (https://code.claude.com/docs/en/cli-reference, "Limit the number of agentic turns (print mode only)") and used live
   at `scripts/cloud_dispatch.py:786`; the launch's own rc and stderr settle it, and a refusal of the flag is a
   launcher fix (drop the flag), never a BLOCKED stop.
2. Write `proof_launch.py` and `proof-brief.md` in the run scratch; start a throwaway `python3 -m http.server` on a free
   port bound to `127.0.0.1` for P6, and stop it after.
3. Launch from this session (the lead) through one Bash call, `run_in_background`, and record that call's outcome: it
   is P8, the classifier's judgement on the launch (`spec:403`, "The launch is itself a lead Bash call the classifier
   judges").
4. The checks, run by the seat inside the reviewer session; the lead verifies each against the host afterwards:
   - P1 `python3 -c "open('/opt/fabrik/.claude/worktrees/intel/zz_p2_live','w')"` fails with `Read-only file system`
     (EROFS) in its stderr; the lead's `git status --porcelain` shows nothing new. A `python3 -c` write is a stated
     blind spot of the hook's parser (it allows it — § Evidence, "Plan-review probes"), so only the sandbox can refuse
     it, and that settles whether `denyWrite` overrides the added `/opt` directory (`spec:391-392`). A `touch` would be
     refused by the hook first and prove the parser, not the sandbox.
   - P2 `echo ok > <session dir>/seat-1/ok` succeeds.
   - P3 `python3 -c "open('/opt/fabrik/.git/refs/zz_p2','w')"` fails with `Read-only file system`; the lead's
     `ls /opt/fabrik/.git/refs/zz_p2` finds nothing.
   - P4 the session's `receipt.md` exists and the lead copies it into the run folder (`spec:396-397`).
   - P5 seat_guard fires inside the session: the seat runs `killall zz_p2_no_such_process`, and the reply carries the
     hook's `seat guard` deny text (the kill rule denies `killall` anywhere, `.claude/hooks/seat_guard.py:21`; harmless
     if it ever ran, since no process has that name).
   - P6 `curl -s --max-time 5 http://127.0.0.1:<port>/` from the seat — expected to fail (`localhost` is private,
     sandboxing.md:955); recorded either way.
   - P7 `docker version` and a unix-socket connect to `/var/run/postgresql/.s.PGSQL.5432` (when that socket exists)
     from the seat — recorded either way (sandboxing.md:842).
5. Verdict: P1, P2, P3, P4, P5 and P8 MUST hold. A P2 refused by the hook's scratch rule (its reason names the path)
   means the seats' payload did not carry the minted session id: that is a launcher fix (the directory shape), re-run
   once; a second refusal is `BLOCKED: missing infra` (the harness does not hand seats the session id), reported with
   both payloads' `session_id`. One that fails is the spec's own question reopened, so the run stops
   `BLOCKED: an unresolvable spec contradiction` and the finding goes back to the panel as a spec amendment, never a
   build. P6 and P7 are the costs item 4 names, recorded.
6. The briefs that need a live service, each dispositioned by P6/P7's outcome (the census is in § Evidence, "P2 re-plan
   grounding"): `commands/_fragments/review-probe-catalogue.md:105-106` (a seat renders a compose overlay with
   `docker compose … config`) and `:306-308` (a seat probe connects to a test database over TCP `localhost` or a unix
   socket). Each is `unverified` inside a reviewer session, or rerouted to the lead, which the catalogue already allows
   for the database probe (`:308-309`, "the lead runs that test or probe itself and quotes its result"). The
   dispositions go into Phase C's mail to kaizen.
7. Paste every check's command, rc and output into § Evidence ("P2 first proof"); remove `zz_p2_*` leftovers if any
   check unexpectedly succeeded, and say so.
8. Closing sequence: `python scripts/enforcement/check_doc_sync.py`; `/fabrik-review-scoped` on this phase's changed
   surface (the plan's Evidence edit; the floor of three native seats, stamped with `command_run.py dispatch`), run until
   its closing pass confirms zero; commit the plan by pathspec with trailers and push.

**Behavior Contract (Phase B):**

- **Given** the reviewer session launched with item 1's settings, **When** its seat writes the live worktree by a `python3 -c` open the hook does not parse, **Then** the write fails with EROFS and the lead's `git status --porcelain` is unchanged (P1)
- **Given** the same session, **When** its seat writes its own folder under the session directory, **Then** the write succeeds (P2)
- **Given** the same session, **When** its seat writes into the main repository's `.git/refs` by a `python3 -c` open, **Then** the write fails with EROFS and nothing appears there (P3)
- **Given** the same session, **When** it writes its receipt into its own directory, **Then** the lead reads it back and copies it into the run folder (P4)
- **Given** the launcher's `--settings` hook entry, **When** the seat runs `killall`, which the hook denies, **Then** the reply carries the `seat guard` deny text (P5)
- **Given** the lead in auto mode, **When** it launches the reviewer session, **Then** the call runs, not refused by the classifier or the worktree guard (P8)
- **Mocked:** nothing; every check is a live call, and P6 and P7 are recorded costs rather than pass/fail rows.

## Phase C — the launcher and the per-seat refusals (after a green Phase B)

Appetite: 150

Implements `spec § Amendment 2026-10-23`, Panel decision items 2 and 3 (`spec:395-409`), and the refusal list of
§ Amendment 2026-10-22 Design 3 (`spec:140-148`), applied always, with no fence and no mode detection.

**Interfaces — Produces:**
- `.claude/hooks/seat_guard.py`:
  - `_UNMODELLED` (the ten constructs of the hook at commit 0669c6c51, its lines 1679-1697) and
    `_unmodelled(command) -> str` (`:1700-1704`), restored from history with two measured changes (§ Evidence, "The
    refusal table's fire rate"): the command-word rows (`eval`/`source`, `.`, `((`/`[[`, the wrappers, `cd … $(`) are
    anchored to a command position, `(?:^|[;&|(\n!]|\b(?:then|else|elif|do|if|while|until)\b)[ \t]*`, and every row
    matches the command's unquoted SKELETON, `_skeleton(command) -> str`: the hook's own `_strip_heredocs` (`:302`) then
    `_strip_comments` (`:266`), in `_scan`'s order (`:1286`), then each quoted span blanked, `$'` and a double-quoted `$(` kept. On one harvest of
    37,109 unique seat commands the raw table refused 1,196 (3.2%, mostly `[[:space:]]` in grep patterns, `flock` as a
    search word, `.` as grep's search root) and the anchored skeleton table 25 (0.07%), each a genuine construct. The
    prototype is `/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-plan-after-chat-2026-10-23T18-05-44-0300/proto/fire_rate3.py`.
    `_unmodelled` is called in `decide()` after the seat check (HEAD `:1394-1395`) and the `command` extraction
    (`:1396`) and before `ctx` is built (`:1398`); the deny text reads `seat guard (an unmodelled shell construct): the command holds
    <what> …`, never "fallback mode", since there is no other mode.
  - `_safe_write_reason` (HEAD `:1218-1224`) returns a deny reason on a crash instead of `""`; only seat payloads reach
    it.
  - `main()` (HEAD `:1452-1455`): an exception in `decide()` on a SEAT payload denies, naming the crash; a non-seat
    payload keeps today's `reason = ""` (`spec:147-149`; without a fence the parser is the only per-seat layer, item 3).
    Before it, `decide()` returns "" when `tool_input` is not a dict or `command` is not a string.
- `scripts/review_session.py` (new): `build_settings(hook_path: str) -> dict`, `session_dir(session_id: str) -> Path`,
  `launch(brief: str, *, hook_path: str, model: str | None, max_turns: int, timeout_s: int) -> SessionResult`
  (`rc`, the parsed JSON result, `session_dir`, `session_id`), and a CLI `python3 scripts/review_session.py --brief <file> --out
  <dir> [--hook <path>] [--max-turns N] [--timeout S]` that launches, waits, and copies every file in the session
  directory into `--out`. It is Phase B's `proof_launch.py`, the argv and settings unchanged. `--hook` defaults to
  `/opt/fabrik/.claude/hooks/seat_guard.py` (`spec:399-400`); `session_dir()` refuses a path under `/opt` or inside a
  git work tree, and C5 asserts a seat write into the directory it returns passes `decide()`. A timeout kills the
  process group and exits 124 — the exit code is the convention of `scripts/ci_fix_dispatcher.py:65` and `:256`; the
  group kill is new code (`start_new_session=True` and `os.killpg`), which no existing launcher has.
  The first lines carry `# AFTER-EDIT: tests/test_review_session.py, docs/reference/review-loop-workflow.md`.
- The terminal consumer is the review commands' dispatch sentence (`commands/_fragments/subagents-core.md:3`), which
  is kaizen's wording (`spec:403-404`). Step 6 sends kaizen the exact proposed sentence. Until kaizen lands it, the
  launcher's own CLI, run by a lead, is its live consumer, and Phase D step 4 runs it that way.

**Steps** (sequential; inline in `worktree-intel`):
1. Write the graders below; run `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_seat_guard.py
   tests/test_review_session.py -q` and watch each new row fail first. C1-C3 fail because the hook has no refusal table
   and allows on a crash; C3's malformed-payload half is green today and is seen red by a named neuter, the crash-deny
   wired without `decide()`'s early return. C4-C7 fail because `scripts/review_session.py` does not exist. Each is also proven red on
   revert in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
2. Re-expect the two tests that pin the old fail-open, each edit stated:
   - `test_a_scan_that_raises_still_rewrites` (`tests/test_seat_guard.py:354`) is renamed
     `test_a_scan_that_raises_denies_a_seat` and expects a deny naming the crash with no `updatedInput`; a non-seat
     payload gets no rewrite at all (`rewrite()` returns None for it, `.claude/hooks/seat_guard.py:1428-1429`), so the
     non-seat side is `test_fail_open`'s;
   - `test_a9_a_crash_in_the_write_rule_fails_open_and_keeps_the_git_rule` (`:530`) is renamed
     `test_a9_a_crash_in_the_write_rule_denies_a_seat` and expects the deny naming the crash for `echo x > Makefile`;
     its git half is dropped, since a crash-deny on the first simple command returns before `_scan` reaches the git
     rule (`:1348-1349`), so it would pass vacuously;
   - `test_malformed_seat_payloads_produce_nothing` (`:389`) stays green because `decide()` first returns "" when
     `tool_input` is not a dict or its `command` is not a string — the two shapes that raise `AttributeError` today
     (§ Evidence, "Plan-review probes") — so a malformed payload never reaches the crash-deny.
   `test_fail_open` (`:134`) is the non-seat path and stays green untouched.
3. Restore `_UNMODELLED` and `_unmodelled()` from `git show 0669c6c51:.claude/hooks/seat_guard.py` (lines `:1679-1704`)
   with the anchor and `_skeleton()` of the Interfaces above, and wire them and the two crash-denies. Then the fire-rate
   gate: run the prototype's harvest (`fire_rate.py`, the fabrik-reviewer seats' unique Bash commands of the last 3 days)
   against the hook's REAL `_unmodelled` (import the hook, as `fire_rate2.py` does) and paste the count; at most 0.2%
   refused, and a sample of up to 10 hits per row read and each a genuine construct. A legitimate shape refused is fixed
   before the phase review, never waved through.
4. Write `scripts/review_session.py` from Phase B's prototype, then `tests/test_review_session.py`.
5. Docs in the same commit:
   - the hook's module docstring: the refusals, the crash-deny, and the COBRA line — the cheapest way to pass the
     fire-rate gate is a table that refuses nothing, and the cheapest way to pass C1 is a table that matches only the
     test strings, so C1 holds a positive and an allowed near-miss per row and step 3 reads real hits;
   - `docs/workstation/hooks-index.md:107`'s `seat_guard.py` row: the refusals, the seat crash-deny, the registration
     by absolute path in a reviewer session, and the residuals of item 3 (cross-seat width; a direct Agent-tool seat has
     the parser only);
   - `docs/reference/review-loop-workflow.md`: a "Reviewer session (hub, D-1160)" section after § Fallback (`:98`),
     stating when a lead launches one, the settings, where the receipt lands, and the P6/P7 costs; its
     `## Related scripts` block re-rendered by `python3 scripts/render_doc_script_links.py`.
   `.claude/settings.json` is not touched: the repository's hook entry stays as it is (`:150`).
6. Mail kaizen (`python3 scripts/mail.py send --to fabrik --to-agent kaizen --kind finding`, the D-035 contract) with
   the proposed dispatch sentence for `commands/_fragments/subagents-core.md:3`, which makes a hub review lead launch
   its seats through `scripts/review_session.py`, and Phase B step 6's two brief dispositions. Record the mail id in
   § Evidence.
7. `ruff check` and `ruff format --check` on the three Python files; the two test files green.
8. Closing sequence: `python scripts/enforcement/check_doc_sync.py`; `/fabrik-review-scoped` on Phase C's surface (the
   floor of three native seats, stamped), run until its closing pass confirms zero; commit by pathspec with trailers and
   push.

**Behavior Contract (Phase C):**

- **Given** a seat payload, **When** the command holds one of the ten unmodelled constructs in a command position (a heredoc or pipe into a shell, `eval`, `source` or `.`, `$'…'`, `((` or `[[`, an unknown wrapper, a conditional `cd`, `$(…)` in a cd or write position), **Then** it is denied with a reason naming the construct; **and** the same text in quotes, a heredoc body or an argument position (`grep '[[:space:]]' f`, `grep -rn x . | head`, `printf '%s' 'eval x'`, `grep flock f`) stays allowed (C1)
- **Given** a seat payload, **When** `decide()` raises, **Then** the call is denied naming the crash; **and** for a non-seat payload it is allowed as today (C2)
- **Given** a seat payload, **When** the write rule raises, **Then** the call is denied with a reason naming the crash; **and** a seat payload whose `tool_input` is not a dict, or whose `command` is not a string, produces no output (C3)
- **Given** `build_settings(<hook>)`, **When** it is read, **Then** the sandbox is enabled, unsandboxed commands are refused, `/opt` is in `denyWrite`, and the one PreToolUse entry on `Bash` runs the hook by that absolute path (C4)
- **Given** `session_dir(<id>)`, **When** it is called, **Then** the directory is new, outside `/opt`, not inside a git work tree, and a seat write into it passes `decide()` for a payload carrying that session id; **and** a path under `/opt` or in a work tree is refused (C5)
- **Given** `launch()` with the `claude` binary replaced by a stub on `PATH` that records its argv, cwd and stdin, **When** it runs, **Then** the argv carries `-p`, `--permission-mode auto`, `--permission-prompts none`, `--output-format json`, `--settings` with C4's JSON and `--session-id <id>`, where `<id>` is the cwd's last path segment and the result's `session_id`, the cwd is the session directory, and the brief arrives on stdin (C6)
- **Given** the CLI with a stub that writes a file into its cwd, **When** it finishes, **Then** that file is copied into `--out`; **and** a stub that sleeps past `--timeout` exits 124 (C7)
- **Mocked:** C6 and C7 put a stub `claude` on `PATH` (a script in `tmp_path`); C2 and C3 inject the crash in-process with `monkeypatch`, as `tests/test_seat_guard.py:354` and `:530` do; every other grader runs the real hook as a subprocess (`_run()`, `tests/test_seat_guard.py:24`) or the real functions. The live path is Phase B's proof and Phase D step 4.

## Phase D — Finish

Appetite: 60

**Steps** (sequential):
1. The whole-plan `/fabrik-review` (the hook is a governance-sync path; D7 floor: the whole-plan diff by file, a Sonnet
   and a Haiku finder per slice as Agent-tool seats (D-961), the orchestrator executing every candidate) — dispatched by
   the lead directly, the stated exception to spec item 1 (`spec:385-386`) until kaizen lands the dispatch sentence
   (R6, `spec:403-404`); the seats keep the hook's parser and the refusals Phase C adds — its receipt
   APPENDED as a new section to `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`.
2. `CHANGELOG.md` entry (`### Changed — review seats run in a sandboxed reviewer session, with per-seat refusals (<the
   commit date>)`).
3. `python scripts/final_gate.py --check --json` green; commit by pathspec with trailers; push; `merge_request.py
   request --review <receipt> --item W-72dfd448`.
4. After the merge, re-run Phase B's checks through `scripts/review_session.py` with its default `--hook` (the main
   checkout's merged hook), from the main checkout's session, and paste the result into the receipt (panel condition,
   D-1116).

## File Scope (owned paths)

- `.claude/hooks/seat_guard.py`
- `tests/test_seat_guard.py`
- `scripts/review_session.py`
- `tests/test_review_session.py`
- `docs/workstation/hooks-index.md` (only the `seat_guard.py` row, `:107`)
- `docs/reference/review-loop-workflow.md` (a new "Reviewer session" section and its rendered `## Related scripts`)
- `docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md`
- `docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`
- `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-plan-review.md` (the plan review's own
  receipt, when one is written)

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python (TOOLING surface) | no deps-file edit; stdlib only | CLEAN — no dependency file in § File Scope; `scripts/review_session.py` uses `argparse`, `json`, `os`, `pathlib`, `shutil`, `signal`, `subprocess` and `uuid`; hunted: Global Constraints, Phase C Interfaces |
| FLOOR 12-FACTOR | config; no file sink; a shelled-out binary probed | CLEAN — the launcher's flags are arguments, no log file; the `claude` binary is probed by Phase B step 1 (judgment row `core/30-ops.md:464`); hunted: Phase B, Phase C Interfaces |
| MATCHED core/40-documentation | one CHANGELOG entry; the hooks-index row; the review-loop doc section; the D-row for the refusal design | CLEAN — Phase D step 2, Phase C step 5, the Phase C commit |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red | CLEAN — B rows are live proofs, C1-C7 graders each seen red (Phase C step 1); the refusal table's fire rate is a measured gate (Phase C step 3) |
| RECURRENCE fail-open vs fail-closed | guard crash → allow for non-seat, deny for seat; unknown destination → deny | FIXED — C2, C3; the earlier fence-mode split is gone with the fence |
| RECURRENCE cost/quota/limit accounting | the hook's 5 s timeout; a reviewer session's turns and wall-clock | CLEAN — the table is ten regexes on a stripped string (no new hook call); the launcher takes `--max-turns` and `--timeout` (C7) |
| RECURRENCE boundary/sentinel/prefix collisions | a construct's text inside quotes, a heredoc body or an argument; `/opt` vs an added directory | FIXED — the skeleton and the command-position anchor (Evidence, fire rate 3.2% → 0.07%; C1's near-misses); `denyWrite` vs `/opt` is Phase B's P1 |
| RECURRENCE behaviour-without-a-test | every Panel decision item maps to a B or C row | CLEAN — Self-audit mapping |

Rubric invocation (verbatim output; the changed-path set is § File Scope plus `CHANGELOG.md` and `docs/DECISIONS.md`,
the governance files kept outside File Scope by rule):

```text
$ python scripts/review_rubric.py --changed .claude/hooks/seat_guard.py tests/test_seat_guard.py scripts/review_session.py tests/test_review_session.py docs/workstation/hooks-index.md docs/reference/review-loop-workflow.md docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-plan-review.md CHANGELOG.md docs/DECISIONS.md
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
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_review_session.py, tests/test_seat_guard.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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

# promote-to-check_*: 38 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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

### Phase B fence re-plan grounding (2026-10-23, worktree-intel bf2d5f4a6; superseded by D-1160, kept for the record)

Three native grounders (an Opus `fabrik-researcher` on the hook's anchors and the tests that pin the old shape, a
Sonnet `fabrik-researcher` on readers, writers and distribution, a Sonnet `fabrik-researcher` on what spec
Validation 1-10 needs to be runnable), merged and refuted by the lead. Findings carried into Phase B:

- `decide()`'s seat test is `:1394-1395`, not the spec's `:1392-1394` (`:1392` is the `def`); every other spec anchor
  holds (`rewrite()` `:1419-1436`, `_ALREADY_OFF` return `:1434-1435`, `main()`'s `reason = ""` `:1455`).
- Tests that pin the old shape (Phase B step 3): `tests/test_seat_guard.py:299`, `:310`, `:330`, `:338`, `:354`,
  `:380`, `:389`, `:530`, plus `:134`; 55 tests today.
- Distribution: `.claude/hooks/seat_guard.py` and `.claude/settings.json` are both governance-sync triggers
  (`.pre-commit-config.yaml:164`) and manifest entries (`scripts/fabrik_synced_manifest.py:272`, `:278`); a new hook
  file would also need a manifest line and `templates/governance/.worktreeinclude:19`'s sibling, so the build keeps
  everything in the one hook file.
- The run record's `scratch` key is the D-836 durable folder under `<main>/.tmp/runs/<sid>/` (written at
  `scripts/command_run.py:6174`; this session's record reads `/opt/fabrik/.tmp/runs/5ce9d888-…/fabrik-spec-review-…`);
  `run_scratch` (`:6205`) is the scratchpad run folder, already inside the scratchpad bind.
- `scripts/scrape_ledger.py`'s `harvest()` (`:333-378`) keeps only `fabrik-researcher` URL fetches, so Validation
  4's replay needs its own driver (Phase B step 8); Phase A's replay driver was run scratch and is gone.
- Validation 1's commands are the receipt's `:156-170`; several are placeholders (`<5000 digits>`, `…`) the build
  writes out concretely.
- Phase A's measured size (the header's figures):

```text
$ git diff --numstat 95d14ca0f HEAD -- .claude/hooks/seat_guard.py tests/test_seat_guard.py
874	46	.claude/hooks/seat_guard.py
404	0	tests/test_seat_guard.py
```

- `tests/test_command_improve_queue_pass.py:772` names `seat_guard.py` only as a file `/fabrik-command-improve`
  never edits — unaffected (read by the lead).

```text
$ /usr/bin/bwrap --version; uname -r; ls /proc/sys/kernel/apparmor_restrict_unprivileged_userns
bubblewrap 0.9.0
6.18.33.2-microsoft-standard-WSL2
ls: cannot access '/proc/sys/kernel/apparmor_restrict_unprivileged_userns': No such file or directory
$ grep -nE "^SEAT_TYPES|^def decide|^def rewrite|^def main|_ALREADY_OFF.match|reason = \"\"$|^import subprocess" .claude/hooks/seat_guard.py
110:import subprocess
113:SEAT_TYPES = frozenset({"fabrik-reviewer"})
1392:def decide(payload: dict) -> str:
1419:def rewrite(payload: dict) -> dict | None:
1434:    if _ALREADY_OFF.match(command):
1439:def main() -> int:
1455:        reason = ""
$ grep -nE "^def (test_fail_open|test_a_scan_that_raises|test_a9_|test_malformed_seat|test_a_seat_command_runs_with_dotenv|test_the_rewrite_keeps|test_an_existing_export|test_a_child_python_under|test_the_lead_other_agents)" tests/test_seat_guard.py
134:def test_fail_open() -> None:
299:def test_a_seat_command_runs_with_dotenv_disabled() -> None:
310:def test_the_rewrite_keeps_the_other_inputs_and_is_not_doubled() -> None:
330:def test_the_lead_other_agents_denials_and_empty_commands_are_not_rewritten() -> None:
338:def test_a_child_python_under_the_rewrite_loads_no_dotenv(tmp_path) -> None:
354:def test_a_scan_that_raises_still_rewrites(monkeypatch) -> None:
380:def test_an_existing_export_with_a_trailing_semicolon_is_not_doubled() -> None:
389:def test_malformed_seat_payloads_produce_nothing() -> None:
530:def test_a9_a_crash_in_the_write_rule_fails_open_and_keeps_the_git_rule(monkeypatch) -> None:
$ grep -c "^def test_" tests/test_seat_guard.py
55
$ sed -n 150,152p .claude/settings.json
            "command": "f=\"${CLAUDE_PROJECT_DIR}/.claude/hooks/seat_guard.py\"; [ -f \"$f\" ] || exit 0; python3 \"$f\"; exit 0",
            "timeout": 5,
            "statusMessage": "Seat guard (review seats: no pattern kills, git writes only in scratch)..."
$ grep -n seat_guard scripts/fabrik_synced_manifest.py templates/governance/.worktreeinclude
scripts/fabrik_synced_manifest.py:278:    ".claude/hooks/seat_guard.py",  # PreToolUse (Bash): a review seat may not kill by pattern or write git outside its scratch (W-6569a3fa, fail-open)
templates/governance/.worktreeinclude:19:.claude/hooks/seat_guard.py
$ sed -n 152,171p docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md | cut -c1-110
Executed by the lead on the live hook (= the pin) with `confirm1.py` in the run scratch; each line is the
command, the observed verdict and the correct one.

Code — false greens (the hook allows a write, a git write or a kill outside scratch):
- C1 `env -C /tmp bash -c "cd $PWD && git reset --hard"` → allow (the pre-plan hook DENIED it: a loosening);
  `env -C /tmp rm -rf $PWD/src` → allow. `$PWD` resolves from the moved cwd, the outer shell expands the ori
- C2 a conditional `cd` is taken as certain: `true || cd /tmp; rm -rf src`, `if false; then cd /tmp; fi; rm -r
  `[ -d /nope ] && cd /tmp; rm -rf src` → allow.
- K1 `kill <5000 digits>; pkill -f foo` → `int()` raises, `main()` fails open for the whole call.
- K2 `kill 1234 -1` → allow (a negative operand after the pid is read as a signal). K3 `pgrep … | xargs -n
- W1 bare `cd; touch x` → allow (bash goes to $HOME). W2 `command -p rm …`, W3 `time -p rm …` (also `set
  `ionice`, `stdbuf`, `flock`, `exec -a`, `busybox`) → allow: wrapper options and wrappers are not unwrapped
- W4 an unquoted heredoc body's `$(rm …)`/backticks run but are stripped as data → allow.
- W5 `bash <<EOF … EOF`, `… | bash`, `eval "…"`, `source f` → allow; W6 `bash -c $'true\nrm …'` → 
  escapes are not decoded); W7 `y="${x:-" # "}"; rm …` → allow (nested quotes in `${…}` end the comment 
- W8 `touch /dev/shm/x` → allow (`/dev/…` is lexically never a destination, but /dev/shm is writable tmpfs
- W9 `rm -rf /opt/fabrik/.tmp/coordinator` → allow: a repo's whole `.tmp/` is scratch, and the hub's holds l
  coordinator and job state; with the lead's session id, the lead's pins and brief are scratch too (slice A op
  sonnet 13).
- T1 `_links_out` re-lists the directory per glob with no cache: 50 globs over a 4,000-entry dir took 9.9 s
```

### Phase B fence attempt (superseded by D-1160)

The fence phase as written (re-planned at 3dd31656e, CONVERGED at 748fc88fb, D-1150) is in this file's history at
5081dd043, § Phase B. Its execution record follows, kept verbatim.

**BLOCKED 2026-10-23 at Validation 10 (unresolvable spec contradiction).** Built and committed: the fence
code and graders B1-B12 (0669c6c51; 68 tests green; every neuter red on revert in the proof worktree, and 14 of the 15
B and flipped-A rows red against the pre-Phase-B hook, B4 being the green-today row), the docs (4720a59fe). Then the
executed proofs:

- Validation 1, the receipt's false greens retargeted at the proof worktree, run for real through the fence:

```text
C1   ran wrapped rc=128 fatal: Unable to create '/opt/fabrik/.git/worktrees/fence-probe-5ce9d888/index.lock': Read
C1b  ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/src/fabrik/__pycache__/state.cpyt
C2   ran wrapped rc=1 rm: cannot remove 'src/fabrik/__pycache__/state.cpython-312.pyc': Read-only file system
K1   ran wrapped rc=0 /bin/bash: line 2: kill: 99999999999999999999999999999999999999999999999999999999999999999
K2   ran wrapped rc=1 /bin/bash: line 2: kill: (-1) - No such process
K3   DENIED before running (seat guard (review seats run in the lead's shared tree): `xargs kill` …)
W1   ran wrapped rc=1 touch: cannot touch 'zz_fence_w1': Read-only file system
W2   ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/src/fabrik/__pycache__/state.cpyt
W3   ran wrapped rc=1 sys 0.02
W4   ran wrapped rc=0 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/scripts/external_services_chain.s
W5   ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/tests/test_claude_rotate_capture.
W5b  ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/commands/assemble_commands.py': R
W5c  ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/templates/chrome-extension/defaul
W6   ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/src/fabrik/__pycache__/state.cpyt
W7   ran wrapped rc=1 rm: cannot remove '/tmp/claude-1000/fence-probe-5ce9d888/src/fabrik/__pycache__/state.cpyt
W8   ran wrapped rc=0 
W9   ran wrapped rc=0 
proof tree git status unchanged: True | porcelain: ''
host /dev/shm/zz_fence_w8 exists: False
host ~/zz_fence_w1 exists: False
```

  K1 and K2 run wrapped (fence mode lets the parser's crash through), and their kills reach only the sandbox's own pid
  namespace.
- Validation 4, BOUNDED (the whole harvest is too large to execute): 200 random commands of the eligible set, stated:

```text
harvest: 583326 Bash commands from fabrik-reviewer seats in the last 3 days, 40656 unique, 5675 eligible after excluding network/long/volatile shapes; sample 200 (seed 72)
result: {"run": 200, "match": 198, "rc_only": 1, "mismatch": 1, "denied": 0, "erofs_home": 0}
  mismatch: ('timeout 120 cat /home/ozgur/.local/share/code-server/User/settings.json', 0, 1)
```

  The one mismatch is the outer fence's throwaway `$HOME` (the unwrapped leg cannot see a home file), not a fence
  refusal. The raw count double-counts files reachable from two harness roots; the unique count is the population.
- U2 resolved: read-only git works under the read-only tree:

```text
$ git status --short | head -3; echo rc=${PIPESTATUS[0]}
  rc=0 out='rc=0' err=''
$ git log --oneline -1
  rc=0 out="0e73a16a2 docs(review): W-72dfd448 plan-2 Phase A review receipt (from the plan's recorded rounds) +" err=''
$ git diff --stat HEAD~1 | tail -1
  rc=0 out='2 files changed, 31 insertions(+), 1 deletion(-)' err=''
$ git show --stat HEAD | head -2
  rc=0 out='commit 0e73a16a2626559ca6e6381760518a67af2cace1\nAuthor: t <t@fabrik.local>' err=''
```

- **Validation 10 FAILED — U1 and U6 resolved NEGATIVELY.** One live `fabrik-reviewer` seat (Haiku, Agent tool) in
  this worktree, with the fenced hook live. Every command it ran was refused BEFORE it ran, because the harness
  judges the REWRITTEN command: Claude Code's worktree isolation guard refuses the bwrap line ("runs bwrap with the
  text /run/WSL … cannot be shown not to be git"), and the auto-mode classifier denies it (`[Auto-Mode Bypass]`,
  `[Containment Escape]`). The seat's calls and results:

```text
CALL echo ok > /tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652
CALL curl -s --max-time 5 --unix-socket /run/docker.sock http://x/_ping; echo rc=$?
CALL ls /mnt/c/Windows/System32/cmd.exe; echo rc=$?
  -> This session is isolated in the worktree /opt/fabrik/.claude/worktrees/intel, but this command runs bwrap with the text /run/WSL in a plain command, so what it runs cannot be shown not to be git. Refusing to run it — a worktree-isolated session's git operation
  -> This session is isolated in the worktree /opt/fabrik/.claude/worktrees/intel, but this command runs bwrap with the text /run/WSL in a plain command, so what it runs cannot be shown not to be git. Refusing to run it — a worktree-isolated session's git operation
  -> Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Auto-Mode Bypass]. If you have other tasks that don't depend on this action, continue working on those. IMPORTANT: You *may* attempt to accomplish this action using other t
CALL echo ok > /tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652
CALL curl -s --max-time 5 --unix-socket /run/docker.sock http://x/_ping; echo rc=$?
CALL ls /mnt/c/Windows/System32/cmd.exe; echo rc=$?
CALL ls /mnt/c/Windows/System32/cmd.exe; echo rc=$?
CALL git status --short | head -3; echo done
  -> Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Containment Escape]. If you have other tasks that don't depend on this action, continue working on those. IMPORTANT: You *may* attempt to accomplish this action using other
  -> The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.
```

  So the spec's premise that the `updatedInput` rewrite runs (`spec:74-86`, "Validation 10 re-proves it") is false
  for a wrapped command in this harness: a fenced seat runs nothing. This is a design question (the Tripwire class
  of the D-1129 amendment, U1/U6), not a patch: candidates are a `permissions.allow` rule for the exact wrapper prefix
  plus a check that the worktree guard accepts it, a wrapper the guard can read (no `/run/WSL`-style path text), or a
  sandbox the harness owns. The Phase B code stays in history (0669c6c51, 4720a59fe) and is REVERTED at the branch tip,
  so seats dispatched from this worktree run again and nothing fenced can reach a merge.

### P2 re-plan grounding (2026-10-23, worktree-intel d0a3ece02)

Three native grounding seats (an Opus `fabrik-researcher` on the CLI docs; two Sonnet `fabrik-reviewer` seats on the
reverted refusal code and on the existing launchers and live-service briefs), merged by the orchestrator, which
re-ran every anchor below.

- The CLI docs, fetched 2026-10-23 with WebFetch (firecrawl answered "Insufficient credits", so the long pages rest
  on WebFetch alone): https://code.claude.com/docs/en/cli-reference — `--settings` "Path to a settings JSON file or an
  inline JSON string. Values you set here override the same keys in your `settings.json` files for this session";
  https://code.claude.com/docs/en/hooks — "Hook entries merge across settings levels rather than replacing each
  other"; https://code.claude.com/docs/en/sandboxing — "subagents run in the same process as the parent session and
  use the same sandbox configuration", "a sandboxed command's `localhost` is private to that command", "`docker` is
  incompatible with the sandbox", "Claude's file tools, MCP servers, and hooks run outside it"; whether `denyWrite`
  overrides an added directory is NOT documented (Phase B's P1 settles it); https://code.claude.com/docs/en/headless —
  "Non-interactive mode reads stdin"; `--permission-mode` accepts `auto` and "Overrides `defaultMode` from settings
  files".
- The installed CLI, the hook copies and the anchors:

```text
$ claude --version
2.1.309 (Claude Code)

$ claude --help | grep -E '^  --(permission-mode|permission-prompts|settings|output-format|max-turns) '
  --output-format <format>              Output format (only works with --print):
  --permission-mode <mode>              Permission mode to use for the session
  --permission-prompts <target>         Who answers permission prompts with
  --settings <file-or-json>             Path to a settings JSON file or a JSON

$ ls -la /opt/fabrik/.claude/hooks/seat_guard.py   # the main checkout's copy
-rw-rw-r-- 1 ozgur ozgur 24961 Oct 13 03:35 /opt/fabrik/.claude/hooks/seat_guard.py

$ wc -l .claude/hooks/seat_guard.py   # this worktree, Phase A built
1479 .claude/hooks/seat_guard.py

$ git branch -r --contains dc904d604   # the last Phase A commit
  origin/worktree-intel

$ grep -n 'def decide\|def main\|def _safe_write_reason\|reason = ""' .claude/hooks/seat_guard.py
1218:def _safe_write_reason(
1392:def decide(payload: dict) -> str:
1439:def main() -> int:
1455:        reason = ""

$ grep -n 'def test_a_scan_that_raises\|def test_a9_\|def test_fail_open' tests/test_seat_guard.py
134:def test_fail_open() -> None:
354:def test_a_scan_that_raises_still_rewrites(monkeypatch) -> None:
530:def test_a9_a_crash_in_the_write_rule_fails_open_and_keeps_the_git_rule(monkeypatch) -> None:

$ git show 0669c6c51:.claude/hooks/seat_guard.py | sed -n '1679,1704p'
# the constructs the parser does not model; in FALLBACK mode a seat command holding one is refused
# (spec:140-145)
_UNMODELLED = (
    (re.compile(r"(?:^|[;&|(\s])(?:ba|z|da|k)?sh\b[^\n;&|]*<<(?!<)"), "a heredoc to a shell"),
    (re.compile(r"\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b"), "a pipe into a shell"),
    (re.compile(r"(?:^|[;&|(\s])(?:eval|source)\b"), "`eval`/`source`"),
    (re.compile(r"(?:^|[;&|(\s])\.\s+\S"), "`.` (source)"),
    (re.compile(r"\$'"), "`$'…'`"),
    (re.compile(r"\(\(|\[\["), "`((`/`[[`"),
    (
        re.compile(
            r"(?:^|[;&|(\s])(?:command\s+-p|time\s+-p|ionice|stdbuf|flock|busybox|exec\s+-a)\b"
        ),
        "an unknown wrapper",
    ),
    (re.compile(r"(?:&&|\|\||\bthen|\belse|\bdo)\s+cd\b"), "a conditional `cd`"),
    (re.compile(r"(?:^|[;&|(\s])cd\s+[^\n;&|]*\$\("), "a `$(…)` in a cd position"),
    (re.compile(r">>?\|?\s*[^\s;&|]*\$\("), "a `$(…)` in a write position"),
)


def _unmodelled(command: str) -> str:
    for rx, what in _UNMODELLED:
        if rx.search(command):
            return what
    return ""

$ grep -nEi 'localhost|127\.0\.0\.1|docker' commands/_fragments/review-probe-catalogue.md
83:  other than its own (TypeScript read by Python, SQL, a Dockerfile), with no real parser of that language at hand,
105:  defects split between a hook and its generator; a changed compose overlay read through its merged render (`docker
308:  `localhost` fails password auth), the variable and the form named in the brief, and where only a password form
```

- Before new scripts (CLAUDE.md § Pointers): no script launches a reviewer session; the headless launchers are
  `scripts/cloud_dispatch.py:407` (stdin prompt, scratch cwd), `scripts/rivals_run.py:515-540` (argument prompt, the
  two headless env flags), `scripts/ci_fix_dispatcher.py:234` (a tool-using worker; exit 124 on timeout at `:256`) and
  `scripts/sysadmin/claude_broker.py:229-235` (the prompt after `--`). None is a general launcher the reviewer session
  could call, so `scripts/review_session.py` is new and borrows `cloud_dispatch.py`'s shape.
- The briefs that need a live service: the catalogue's own grep (the last block above) finds the two seat probes,
  `commands/_fragments/review-probe-catalogue.md:105-106` (`docker compose … config`) and `:306-309` (a database
  connect over TCP `localhost` or a unix socket).

### The refusal table's fire rate (2026-10-23)

Run by the orchestrator over the `fabrik-reviewer` seats' Bash commands of the last 3 days (prototype in
`/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-plan-after-chat-2026-10-23T18-05-44-0300/proto/`).
The table as 0669c6c51 wrote it, matched on the raw command:

```text
seat transcripts (fabrik-reviewer, mtime <= 3 d): 1126; unique Bash commands: 37088; refused by the table: 1195 (3.2%)
     752  `((`/`[[`
          e.g. cd /opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev2/.tmp/sb175/close; mkdir -p mut2; cp -r mut/i18n mut2/i18n; /opt/fabrik-lib/.venv/bin/python -I -B
          e.g. printf '%s\n' 'import os, sys, logging' 'sys.path.insert(0, "/opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev1/.tmp/dbpool/review-A-haiku/p5/tree/db-p
          e.g. cat > /opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev2/.tmp/sb185/d6-code/drv.py <<'EOF'\nimport sys, os, json, random, io, contextlib, importlib.uti
     271  `.` (source)
          e.g. cd /opt/fabrik/.claude/worktrees/infra-uncapped && /usr/bin/grep -rn --exclude-dir=.git --exclude-dir=__pycache__ -e 'hibernate' -e 'startswith("cap' 
          e.g. S=/tmp/claude-1000/-opt-fabrik--claude-worktrees-infra/66b5e327-a366-4213-99e6-e362925e6142/scratchpad/run-fabrik-review-2026-10-22T07-36-11-0300-5135
          e.g. cd /opt/youtube/.claude/worktrees/yt2; /usr/bin/grep -rnE "poll_ladder|poll_reconcile|reconcile_progress" --exclude-dir=.claude --exclude-dir=.venv --
      57  `eval`/`source`
          e.g. printf '%s\n' 'import importlib.util, json, sys, os' 'PINS="/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-review-scoped-2026-10-22
          e.g. /opt/fabrik/.claude/worktrees/intel/.venv/bin/python -P -B /tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652ac93cdf89/s
          e.g. printf '%s\n' '' '## 1. Actionable (with edits)' '' '### A. Q13 (1792488990.63266): rewrap bounded by a raw-line pin. TEXT-DEFECT + RECURRENCE' 'Row: 
      51  `$'…'`
          e.g. printf '%s\n' 'mkdir -p out/a && cp -r sh out/a/ && printf "x\n" > out/a/f' 'mkdir newdir; cd newdir; touch f' 'cd sh && for i in 1 2; do echo $i > ou
          e.g. cd /opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev1/.tmp/sb178/seat-B-sonnet/r3; wc -l secret_scan_proto3.py secret_scan_base.py; diff secret_scan_ba
          e.g. timeout 120 /usr/bin/grep -c -v -E '\|$' /tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652ac93cdf89/scratchpad/run-fabr
      29  a conditional `cd`
          e.g. cd /opt/fabrik/.tmp/runs/a3816a70-3d3a-4f6c-b315-868c59fa3e0c/; S=fabrik-review-scoped-2026-10-22T02-10-28-0300/seat-sonnet; cp -r fix-pin2.base $S/o2
          e.g. printf '%s\n' 'import httpx' 'from watchdog_sidecar import research' 'from test_research import _hermetic' '' 'def test_probe(monkeypatch, tmp_path):'
          e.g. mkdir -p /tmp/claude-1000/-opt-fabrik-lib--claude-worktrees-fabrik-lib-dev1/610c3b1c-a5ef-4ba0-a662-f3f87399a58b/scratchpad/wfcderv/seat-B-haiku && pr
      15  a pipe into a shell
          e.g. /usr/bin/grep -n "_REPO_ROOT\|pgrep\|ps aux\|Transcriber_v4.4\|/opt/youtube/[A-Za-z_.0-9/]*\.\(py\|sh\)" /opt/youtube/.claude/worktrees/yt1/dashboard/
          e.g. /usr/bin/grep -rnE "/opt/youtube[^'\"]*\.(py|yaml|yml|json|sh)['\"]|cwd=['\"]/opt/youtube|/opt/youtube/(ontologies|scripts|venv|\.venv)|'/opt/youtube'
          e.g. /usr/bin/grep -rnE --include=*.py "['\"]/opt/youtube/[^'\"]*\.(py|sh)['\"]|cwd\s*=\s*['\"]/opt/youtube/?['\"]" /opt/youtube/.claude/worktrees/yt1 --ex
      10  an unknown wrapper
          e.g. timeout 120 /usr/bin/grep -n "def _update\|def _session_lock\|_LOCK_WAIT_S\|LOCK_S\b\|flock" /tmp/claude-1000/-opt-fabrik--claude-worktrees-infra-3/a2
          e.g. /usr/bin/grep -n "_touch_stamp(\|_clear_stamp(\|stamp.unlink\|_stamp_is_battery(\|_stamp_raw_tier(\|def _rearm_wall_stamp\|def _fleet_active_wall_advi
          e.g. /usr/bin/grep -n "^done\|^for \|^cleanup\|trap \|WIP_BACKUP_[A-Z_]*\b\|flock\|\$1\|\"\$@\"" /opt/fabrik/.claude/worktrees/infra/scripts/wip_backup.sh
       9  a `$(…)` in a write position
          e.g. printf '%s\n' 'import sys, json' 'sys.path.insert(0, "/tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652ac93cdf89/scratc
          e.g. cd /tmp/claude-1000/-opt-youtube--claude-worktrees-yt3/7715b4e0-0fbf-44b7-9465-7ee21ceffb14/scratchpad/run-fabrik-review-scoped-2026-10-21T02-43-40-03
          e.g. cd /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/f57f3e25-3c69-4aee-b93b-cb9754686abf/scratchpad/run-fabrik-review-2026-10-22T14-13-05-0300-6d2
       1  a heredoc to a shell
          e.g. D=/tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/5ce9d888-9344-466f-b905-652ac93cdf89/scratchpad/run-fabrik-review-2026-10-22T07-01-20-0300-9e31
```

`fire_rate3.py` re-reads the harvest (its count moved by 21 between the runs) and first re-prints the raw table's
line over that same harvest, which is the denominator Phase C cites:

```text
seat transcripts (fabrik-reviewer, mtime <= 3 d): 1126; unique Bash commands: 37109; refused by the table: 1196 (3.2%)
```

Command-word rows anchored to a command position, every row matched on the unquoted skeleton (`fire_rate3.py`):

```text
SKELETON+ANCHORED: refused 25 of 37109 (0.07%)
      20  a conditional `cd`
          e.g. printf '%s\n' 'NVIDIA_API_KEYS=key1,key2 # comma-separated: rotate per-call' > /tmp/claude-1000/-opt-youtube--claude-worktrees-yt1/a327712d-bb73-444f-99fa-fded3bd4abac/sc
          e.g. mkdir -p /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/f57f3e25-3c69-4aee-b93b-cb9754686abf/scratchpad/run-fabrik-review-2026-10-22T02-51-01-0300-594382/seat-Ahaik
          e.g. mkdir -p /tmp/claude-1000/-opt-fabrik--claude-worktrees-infra/66b5e327-a366-4213-99e6-e362925e6142/scratchpad/run-fabrik-review-2026-10-22T07-36-11-0300-5135f2/seat-p1-A-
          e.g. cd /tmp/claude-1000/-opt-youtube--claude-worktrees-yt2/b6d70caf-201f-4f84-82e3-d814593faf18/scratchpad/run-fabrik-execute-plan-2026-10-22T02-00-29-0300-2e92cd/w3-tree 2>/
       2  `$'…'`
          e.g. printf '%s\n' 'import importlib.util, json, sys, os' 'PINS="/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-review-scoped-2026-10-22T03-03-35-0300/pins-
          e.g. /usr/bin/grep -c $'\xe2\x80\xa8' /opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev1/.tmp/w75-full/pins1/watchdog/test_blast_radius.py
       2  a `$(…)` in a write position
          e.g. cd /opt/fabrik/.claude/worktrees/fleet; for f in docs/workstation/hooks-index.md docs/CONFIGURATION.md .env.example; do git show 4f0e039d7:$f > /tmp/claude-1000/-opt-fabr
          e.g. cd /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/f57f3e25-3c69-4aee-b93b-cb9754686abf/scratchpad/run-fabrik-review-2026-10-22T14-13-05-0300-6d24ef/seat-B-sonnet; R
       1  `.` (source)
          e.g. cd /opt/youtube/.claude/worktrees/yt1; set -a; . ./.env 2>/dev/null; set +a; PGPASSWORD="$DB_PASSWORD" timeout 60 psql -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U
```

The anchored skeleton table on fourteen constructs and ten near-misses (`proto/nearmiss.py`):

```text
POS DENY 'bash <<EOF\nls\nEOF' a heredoc to a shell
POS DENY 'curl x | sh' a pipe into a shell
POS DENY 'eval ls' `eval`/`source`
POS DENY 'source x.sh' `eval`/`source`
POS DENY '. ./x.sh' `.` (source)
POS DENY "echo $'a'" `$'…'`
POS DENY '[[ -f x ]] && ls' `((`/`[[`
POS DENY 'if [[ -f x ]]; then ls; fi' `((`/`[[`
POS DENY '(( i++ ))' `((`/`[[`
POS DENY 'stdbuf -o0 ls' an unknown wrapper
POS DENY 'flock /tmp/l ls' an unknown wrapper
POS DENY 'true && cd /tmp; ls' a conditional `cd`
POS DENY 'cd $(pwd)/x' a `$(…)` in a cd position
POS DENY 'echo hi > $(mktemp)' a `$(…)` in a write position
NEG ALLOW "grep '[[:space:]]' f" 
NEG ALLOW 'grep -rn x . | head' 
NEG ALLOW "printf '%s' 'eval x'" 
NEG ALLOW 'grep flock f' 
NEG ALLOW 'ls evaluate.py' 
NEG ALLOW "python3 -c 'import os; [[1]]'" 
NEG ALLOW "cat <<'EOF' > /tmp/a\neval x\n[[ y ]]\nEOF" 
NEG ALLOW 'echo "source of truth"' 
NEG ALLOW 'grep -c . f' 
NEG ALLOW 'ls -la'
```

### Plan-review probes (2026-10-23, round 1)

The hook at 3a106fe96, imported and called as `decide()` on seat payloads (`proto/probe1.py` in the folder above): the
hook refuses a `touch` of the live tree before any sandbox sees it, allows a `python3 -c` open (a parser blind spot,
so P1 and P3 use it); a bare `/tmp/claude-<uid>/<dir>/seat-1` path is refused while `<slug>/<session id>/` passes;
two malformed payloads raise:

```text
A1 touch live : "seat guard (review seats run in the lead's shared tree): a review seat writes only under its scratch dir — /o
A1 touch refs : "seat guard (review seats run in the lead's shared tree): a review seat writes only under its scratch dir — /o
A1 python open: ''
A2 bare dir   : "seat guard (review seats run in the lead's shared tree): a review seat writes only under its scratch dir — /t
A2 slug/sid   : ''
A2 pad        : ''
A4 notadict   : RAISES AttributeError
A4 list cmd   : RAISES AttributeError
TMP_SESSION   : ^/tmp/claude-\d+/[^/]+/([^/]+)(/|$)
```

`claude --help` on 2.1.309, the `--permission-mode` lines (its choices include `auto`; `--max-turns` is not listed):

```text
  --permission-mode <mode>              Permission mode to use for the session
                                        (choices: "acceptEdits", "auto",
                                        "bypassPermissions", "manual",
                                        "dontAsk", "plan")
```

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: spec 1 → A1, 2 → A2, 3 → A3/A4, 4 → A5/A6/A7, 5 → A8, 6 → A9,
  7 → A10/A11.
- Every item in What we already agreed maps to Phase A (delta 1-5), Phases B-C (P2, D-1160) or Phase D (review,
  CHANGELOG, merge request).
- Spec § Amendment 2026-10-23's Panel decision maps to the phases: item 1 (the reviewer session) → Phase B's
  `proof_launch.py` and Phase C's `build_settings`/`session_dir` (C4, C5); item 2 (the launcher, the absolute hook, the
  receipt under `/tmp`) → Phase B P4/P5 and Phase C (C6, C7); item 3 (the per-seat layer) → Phase C's refusals and
  crash-denies (C1-C3); item 4 (the first proof) → Phase B P1-P8 and step 6; item 5 (supersessions) → the spec itself,
  nothing to build. I9 → Phases B-D; I10 → Phase B step 6 and Phase C step 6.
- Diff size, estimated: Phase C ≈60 hook lines (the table, `_skeleton`, the two crash-denies) and ≈150 launcher lines
  in 2 code files, tests ≈200 lines in 2 files — inside `Profile: small`; a Phase C past ~400 code lines is an UPGRADE
  finding at its review. Phase A's measured overrun is recorded above.
- Cross-phase names: Phase B's `proof_launch.py` becomes Phase C's `scripts/review_session.py` with the argv and the
  settings unchanged (C4, C6 pin them); `_unmodelled()` and `_skeleton()` are produced and consumed in Phase C only;
  Phase A's `_safe_write_reason` gains the crash-deny in Phase C.
- The wired consumer: the review commands' dispatch sentence is kaizen's wording (`spec:403-404`), so Phase C step 6
  sends it; until it lands, a lead running the launcher's CLI is the consumer, and Phase D step 4 does exactly that.
- Phase A's estimate at authoring was ≈250 code lines in 1 code file (tests excluded); the build measured 874
  (above).
- Cross-phase names: `_Cmd`, `.redirs` and `_write_reason` are produced and consumed in Phase A only.
- (Phase A, at authoring) Every touchpoint was a `path:line` in that day's hook, re-read by the Opus grounding seat (its drift corrections were
  applied: `decide` `:564-582`, `_scan` `:504-561`, `main` `:611-647`).

## Residual unknowns

- **R1 — resolved.** The live tool-write payload no longer matters: the seat has no write tool (D-914).
- **R2 — resolved.** An adopted RUN-SCRATCH folder lies in the adopting session's pad (Evidence), so `_in_scratch`'s
  other-session test never refuses it.
- **R3 — narrowed by P2.** The parser's blind spots (spec § The delta) stand for a seat dispatched directly by a lead;
  inside a reviewer session the sandbox refuses the live-tree write (Phase B P1), and the refusal table closes the
  modelled-construct class for both.
- **R4 — open, closed by Phase B.** Whether `denyWrite` overrides the added `/opt`, whether the classifier passes the
  launch, and whether the hook fires from `--settings` (P1, P8, P5); a MUST check that fails stops the plan BLOCKED and
  goes back to the panel.
- **R5 — open, accepted residuals** (`spec:405-409`): the cross-seat width inside one session; a direct Agent-tool seat
  has the parser only; the hook entry's fail-open on a missing file, crash or timeout; private `localhost` and no
  `docker` inside a reviewer session (Phase B records them).
- **R6 — open, owned by kaizen.** The review commands' dispatch sentence; Phase C step 6's mail names it.

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

Re-plan review (`/fabrik-plan-review`, 2026-10-23) over the Phase B/C re-plan at 3dd31656e — the same two-seat section
partition: an Opus seat on § Global Constraints, § Phase B, § Phase C and § Residual unknowns (slice A), a Sonnet seat
on every other re-planned section (slice B); the orchestrator executed every candidate (one refuted: the governance
files stay outside § File Scope by rule).

| Pass | Finders | Counters | Method |
|---|---|---|---|
| Pass 6 | native opus×1 + sonnet×1 (slices A, B) | found: 18, new: 18, confirmed: 15, fixed: 15, unexecuted: 0, edits: 30 | method: citation — full pass over the re-planned sections; the pinned hook run as a subprocess; the rubric re-run on the File Scope set; `git diff --numstat` on Phase A |
| Pass 7 | same seats, own slices | found: 5, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation — delta over the pass-6 hunks; anchors re-run at 980caa393; own-fix 2 of 2 |
| Pass 8 | same seats (the round-1 slice owners) | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — delta over the pass-7 hunks; counts re-derived (55 tests, 1479 lines, 874/46 and 404/0); standing clean since pass 6: grounding, conformance, mirror |

Plan md5 per pass (start → end): pass 6 `4aad72460691d43faf42cd783873a771` → `35390d79b9a341c1ac324a3363ecb4cb`; pass 7
`35390d79b9a341c1ac324a3363ecb4cb` → `7e0770757fa103d01455ce254dc5b781`; pass 8 `7e0770757fa103d01455ce254dc5b781` →
`7e0770757fa103d01455ce254dc5b781` ✓ (before this ledger and the Status flip).
