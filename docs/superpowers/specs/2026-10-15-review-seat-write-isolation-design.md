# Review seats — write isolation in the seat guard (design)

Status: DRAFT
Size: small (amendment 2026-10-22: ≈150 hook lines and ≈180 test lines over the converged build, across `.claude/hooks/seat_guard.py`, `tests/test_seat_guard.py` and `docs/workstation/hooks-index.md`)
Profile: delta
Work item: W-72dfd448 · seed: mail 01M4PHYNXJ (/fabrik-review verdict rows 1791209046, 1791049341, 1791225410) · upgraded from `/fabrik-task` on `tradeoffs` (design seed `/opt/fabrik/.tmp/runs/4e90716e-696b-4ddf-90ab-70e30f51f294/fabrik-task-2026-10-15T22-15-12-0300/design.md`)

## Personas

- **PRIMARY — the operator, whose live checkouts review seats have damaged.** The verdict rows, verbatim: *"the
  review-loop seat brief template could forbid writes under the repo root by construction (cwd = scratch, repo mounted
  read-only) instead of by prose"* (row 1791209046) and *"fabrik-review-loop.js should launch finder and refuter seats with
  cwd set to a fresh scratch directory (or isolation: worktree), never the caller's main checkout"* (row 1791049341). The
  house record behind them: a seat's `git checkout` destroyed a merge owner's uncommitted work, a seat's relative `cp`
  overwrote the hub `Makefile`, and a seat probe removed every session's `~/.claude/skills`.
- **Automated consumers:**
  - the **review seats** — `fabrik-reviewer` finders and refuters, dispatched by the review-loop Workflow
    (`.claude/workflows/fabrik-review-loop.js`) and directly by the Agent tool, which this change constrains: they read
    pins and write only their own scratch;
  - the **lead session / orchestrator** that dispatches them, which must NOT be constrained (it has no `agent_id`);
  - the **PreToolUse seat hook** (`.claude/hooks/seat_guard.py`), which holds the duty to refuse;
  - the **~46 synced repos**, which receive the hook and its registration through the governance sync.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "forbid writes under the repo root by construction (cwd = scratch, repo mounted read-only) instead of by prose" (01M4PHYNXJ row 1791209046) | IN, delivered differently | § The delta — no write tool (pinned, delta 1) and a shell-write rule (delta 2); defence-in-depth against accidental writes, not a mounted read-only tree (§ The delta, its blind-spot paragraph) |
| I2 | "launch finder and refuter seats with cwd set to a fresh scratch directory (or isolation: worktree), never the caller's main checkout" (01M4PHYNXJ row 1791049341) | IN, delivered differently | § Rejected alternatives — A (worktree) and the cwd option, which does not exist; the guard covers both dispatch paths instead, the seats' cwd unchanged |
| I3 | "hand seats a ready probe script" (01M4PHYNXJ row 1791225410) | OUT-OF-SCOPE | W-f7bf9a54 — a separate change with its own measure (seat turns spent building probes) |
| I4 | D-1129, the Opus + Fable panel (unanimous): "Review-seat write isolation becomes a filesystem fence, not a growing shell grammar" | IN | § Amendment 2026-10-22 — the fence |
| I5 | The whole-plan review round 1: 21 confirmed parser holes (receipt `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md` § Round 1 findings) | IN | § Amendment — what the fence closes, and the fallback that fails closed where it cannot run |
| I6 | W-9013addb, "a heredoc misread through a `"$(…)"` inside double quotes still hides later lines" | IN | § Amendment — under the fence the misread can hide no write; in the fallback the construct is unmodelled and refused |
| I7 | The panel's cobra: "bind too much writable space (`--bind /tmp`, or the whole repo `.tmp`) so that 'writes in scratch work' passes" | IN | § Amendment — Validation 9 asserts the bind set exactly |
| I8 | The panel's underivables: bwrap on other hosts; the harness's cwd tracking, background tasks and the worktree guard around a rewritten command | IN | § Amendment — Open unknowns, each resolved by a named build proof |

## Goal

A review seat cannot write outside its scratch directory by mistake — it holds no file-writing tool, and a shell command
whose destination is a literal path outside scratch is refused — on BOTH dispatch paths, without changing the seats'
working directory, their briefs, or the lead session.

## Amendment 2026-10-22 — the fence (D-1129)

**Why the design changes.** The parent's tripwire (§ The delta, its last paragraph) re-opens this design "with approach D
or a filesystem-level fence" on a confirmed interpreter write. The whole-plan review's round 1 confirmed 21 holes of the
same class against the converged parser, all executed (the receipt above, § Round 1 findings). Examples:
- `env -C /tmp bash -c "cd $PWD && git reset --hard"`;
- a conditional `cd`; `kill 1234 -1`; writes to `/dev/shm`;
- a heredoc body holding `$(…)`.

At the pin b0fa6d66d the panel's Opus seat replayed `decide()`. It allowed `touch /dev/shm/x`,
`true || cd /tmp; rm -rf src`, `kill 1234 -1` and an interpreter `shutil.rmtree`, and it refused `if (( n > 3 ))`. The
Opus + Fable panel ruled unanimously (D-1129): stop growing the grammar and fence the filesystem.

**The goal, restated.** A review seat's shell command CANNOT write outside its scratch: the operating system refuses
it, whatever the command's syntax, interpreter or nesting. The fence applies on both dispatch paths and leaves the
seats' working directory, their briefs and the lead session unchanged.

**The design.**
1. **The fence rides the existing rewrite.**
   - `seat_guard.py` already answers every allowed seat Bash call with `updatedInput`, which replaces the command
     before it runs and carries no `permissionDecision` (`rewrite()`, `:1419-1437`; `main()` `:1457-1460`). Today it
     prefixes `export PYTHON_DOTENV_DISABLED=1`.
   - The amendment makes that rewrite wrap the seat's whole command as `/usr/bin/bwrap <args> -- /bin/bash -c
     <shlex.quote(command)>`, keeping the dotenv prefix inside it.
   - The wrapper is keyed on the same `agent_id` + `agent_type in SEAT_TYPES` test as today (`:566-567`). So the lead
     and every non-seat agent are never wrapped, and no brief, cwd, Workflow script or settings file changes.
2. **The bind set is the policy.**
   - Bound in this order: `--ro-bind / /`, `--dev /dev`, `--proc /proc`, `--tmpfs /dev/shm`, then the writable binds.
   - Writable binds: `--bind <scratchpad_dir> <scratchpad_dir>` (the payload's session scratchpad, which holds the
     run's `RUN-SCRATCH` and its `seat-*` folders), and `--bind <repo>/.tmp/runs/<sid> …` when that run folder exists
     (D-836's durable SCRATCH, the 418 hub refusals of the parent's replay).
   - Then `--setenv TMPDIR <scratchpad_dir>`, `--unshare-pid`, `--die-with-parent`, and `--chdir <payload cwd>`.
   - Nothing else is writable: not the live tree, `$HOME`, `~/.claude`, `/tmp` outside the scratchpad, another
     session's scratch, or the repo's other `.tmp` folders. The parent's repo-wide `.tmp` rule is dropped: it exposed
     live coordinator state (round 1, W9).
   - The network is NOT unshared, because briefs allow local probes of `localhost` services.
3. **The fallback is the parser, failing closed.**
   - When `/usr/bin/bwrap` is absent or not executable, or a probe run (`bwrap --ro-bind / / true`) fails because user
     namespaces are refused (Ubuntu 24.04's AppArmor default, below), the hook keeps today's parser.
   - In that mode a seat command holding any construct the parser does not model is REFUSED, never allowed: heredoc
     to a shell, `eval`/`source`, `$'…'`, `((`/`[[`, an unknown wrapper, a conditional `cd`, or a `$(…)` in a write or
     cd position.
   - The refusal message says which mode the hook is in.
   - The probe result is cached per hook process, never written to disk.
4. **The kill and git rules stay**, as cheap early refusals with good messages. Under the fence they are
   defence-in-depth: `--unshare-pid` already makes a `kill` of an outside pid fail (ESRCH), and a git write to the live
   tree fails (EROFS).

**Executed on this box (2026-10-22, the lead session).**
- Ubuntu 24.04.3 LTS on WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`.
- `/usr/bin/bwrap` is bubblewrap 0.9.0, mode `-rwxr-xr-x`, not setuid.
- `/proc/sys/kernel/apparmor_restrict_unprivileged_userns` does not exist, so the AppArmor userns restriction is
  absent here.
- Inside `bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /dev/shm --bind <seat> <seat> --unshare-pid
  --die-with-parent --chdir <worktree> python3 -c …`:
  - the write into `<seat>` succeeded;
  - writes to `<worktree>/zz_fence_probe`, `~/zz_fence_probe` and `/tmp/zz_fence_probe` each raised
    `Read-only file system`, and none of the three files exists afterwards;
  - `os.getcwd()` was the worktree, and `os.getpid()` was 2 (its own pid namespace).
- With `--setenv TMPDIR <seat>`, `tempfile.NamedTemporaryFile` landed in the seat folder.
- The panel's seats (the reports in this run's panel folder) reproduced EROFS for `perl -pi` on a live README, for
  `touch $HOME/x`, and for an interpreter `open(…,'w')`. `.venv/bin/python` ran inside the fence.
- Per-call cost: 20 runs each of `bash -c true` gave 1.3 ms, and of the full wrapper 15.7 ms, so about 14 ms more per
  seat command.

**External facts (fetched 2026-10-22).**
- Claude Code's own Bash sandbox uses bubblewrap on Linux and WSL2: "the sandbox relies on `bubblewrap` and `socat`".
  Its check is "`touch ~/sandbox-probe` | … `Read-only file system` on Linux and WSL2". On Ubuntu 24.04 "the default
  AppArmor policy prevents bubblewrap from creating the user namespaces it needs", unless
  `kernel.apparmor_restrict_unprivileged_userns` is 0 or absent. That sandbox is session-wide: "subagents … use the
  same sandbox configuration" — https://code.claude.com/docs/en/sandboxing (WebFetch).
- bwrap's options, verbatim:
  - "bwrap is an unprivileged low-level sandboxing tool";
  - "the user namespace is required if bwrap is not run as root";
  - `--ro-bind` "Bind mount the host path SRC readonly on DEST"; `--bind` "Bind mount the host path SRC on DEST";
  - `--unshare-pid` "Create a new pid namespace";
  - `--die-with-parent` "Ensures child process (COMMAND) dies when bwrap's parent dies";
  - `--chdir` "Change directory to DIR"
  — https://manpages.debian.org/unstable/bubblewrap/bwrap.1.en.html (WebFetch).
- "`PreToolUse`: `updatedInput` directly under `hookSpecificOutput` replaces a tool's arguments before it runs", and a
  subagent's tool events "fire the same configured hooks as in the main conversation, and the input carries the
  `agent_id` and `agent_type`" — https://code.claude.com/docs/en/hooks (WebFetch).
- The parent's sources still stand: OS enforcement is the boundary and hooks are defence-in-depth (NVIDIA, cited in
  § External dependencies), and a Bash-string deny list was bypassed by `perl -i` (issue 40408).

**Approaches (D-1129).**
- **Chosen: the fence through the hook's rewrite, with the parser as a fail-closed fallback.**
- **Rejected: (a) the fail-closed parser alone.** Five Phase A rounds plus round 1 left 21 holes, and the parent's own
  blind spots (interpreters, scripts, `find`/`xargs`, deep nesting) cannot be parsed by construction.
- **Rejected: (c) Claude Code's built-in sandbox.** It is session-wide, so it would fence the lead too. The parent cut
  it on the same page, and it is still session-wide on 2026-10-22.
- **Rejected: a per-seat Unix user.** It needs root to create users and sudo per command.
- **Rejected: Landlock directly.** It is built in here (ABI 7, per the panel's syscall probe), but it needs a helper
  binary or Python ctypes in the hook path. bwrap already ships it on this box and is what Claude Code itself uses.

**Contract deltas (MIRROR — the shapes that now fail).**
- A seat command that writes anywhere outside its scratchpad or run folder now fails at the OS with EROFS. Before, the
  parser either missed the write or refused it.
- These now fail:
  - a probe that runs `pytest` in the live tree without `-p no:cacheprovider` (its `.pytest_cache` write);
  - a tool that writes a cache under `$HOME` (`~/.cache`) — the build measures which seat tools do;
  - `git` commands that need to write the live index;
  - a seat writing a fabrik-lib `<worktree>/.tmp/<run>/seat-…` folder. These were 1,863 replay commands, so the build
    must decide them: bind that folder when the payload cwd's repo holds it, or brief the fabrik-lib seats to use the
    scratchpad.
- The lead and non-seat agents: no change.
- A host without usable bwrap gets the parser in its stricter fail-closed form.

**Validation (each a test or an executed proof, red first).**
1. Each of the 21 round-1 commands, run for real through the rewritten command on a scratch copy, fails with
   EROFS/ESRCH and leaves the live tree unchanged.
2. An interpreter write (`python3 -c open(<live>,'w')`, `perl -pi`, `shutil.rmtree`) to a live path fails inside the
   fence, with the parser deleted from the path (wrapper-only run).
3. Writes into the seat folder, the run folder and `TMPDIR` succeed; `cwd` is the payload's.
4. The test file's allow cases, plus a fresh 3-day harvest of real seat commands, give the same exit code and stdout
   wrapped and unwrapped. False reds are reported per N.
5. The lead (no `agent_id`) and a non-seat agent get no wrapper.
6. The rewrite round-trips quoting: a command holding every quote, `$`, newline and heredoc form runs unchanged inside.
7. Fallback: with bwrap absent or the probe failing, the parser runs, refuses an unmodelled construct, and says it is
   in fallback mode. A grader neuters the wrapper and sees red.
8. `--die-with-parent`: a seat's backgrounded child dies when the call ends.
9. The bind set is asserted exactly ({scratchpad_dir, the run folder when it exists}). The cobra counter is that
   adding `/tmp` or the repo `.tmp` turns a test red.
10. One live `fabrik-reviewer` seat through the Agent tool, before the merge, writes its seat folder and gets EROFS on
    a live path. Its cwd tracking and a `run_in_background` call still work.

**Open unknowns, each closed by a build proof.**
- (U1) Whether Claude Code's own worktree isolation guard reads the original command or the rewritten one; Validation
  10 shows it.
- (U2) Whether read-only git commands (`git status`) fail when they cannot refresh the index under a read-only tree.
  The lead's session could not probe it (the worktree guard refuses git under a launcher), so the build runs it in a
  probe worktree.
- (U3) bwrap on other synced hosts. The fallback covers an absent or refused bwrap, and the refusal names the mode.
- (U4) Whether `$HOME` caches written by seat tools need a writable bind. The build's harvest replay (Validation 4)
  counts them.

**Lifecycle.**
- The fence is the boundary; the parser is the fallback.
- **Retirement:** the fence moves to Claude Code's sandbox if that ever gains a per-subagent configuration (the
  parent's retirement clause, unchanged).
- **Tripwire:** a confirmed seat write outside scratch through the fence re-opens this design.

## What exists today (grounded, read at 4efc5d325)

- `commands/_agents/fabrik-reviewer.md:4` — `tools: Read, Grep, Glob, Bash`: a review seat has NO Write, Edit or
  NotebookEdit tool, and `:15` tells it to write a probe file with a `printf … > <absolute path>` redirect. Every write a
  seat makes is therefore a Bash write.
- `.claude/hooks/seat_guard.py:62` — `SEAT_TYPES = frozenset({"fabrik-reviewer"})`; `decide()` (`:564-582`) returns ""
  at `:566-567` for any payload without `agent_id` or with another `agent_type`, so the lead and every other agent type
  are untouched.
- `.claude/hooks/seat_guard.py:283-293` — `_in_scratch()` already defines the scratch roots: the payload's
  `scratchpad_dir`, and `/tmp/` except another session's `/tmp/claude-<uid>/<slug>/<sid>/`; a `$`-bearing or substituted
  path is treated as NOT scratch (fail closed for a write).
- `.claude/hooks/seat_guard.py:504-561` — `_scan()` tokenises quote-aware, follows `cd`/`pushd`/subshell scope, recurses
  into `bash -c` and `$(…)`, and denies kills and git writes outside scratch; an untokenisable command is denied only when
  it names a git write or a kill (`:510-517`); recursion stops at depth 3 (`:518`, `:548`).
- `.claude/hooks/seat_guard.py:228-229` — `_simple_commands()` DROPS a redirect's target (`skip_next = True`): today a
  `> path` is invisible to every rule.
- `.claude/hooks/seat_guard.py:611-647` — `main()` returns at once unless `tool_name == "Bash"` (`:616-617`), and fails
  open on any exception (`:620-627`; the charter: a guard bug never blocks a seat).
- `.claude/hooks/seat_guard.py:286` — `_in_scratch()` calls `os.path.realpath`, which resolves a RELATIVE path against
  the hook process's cwd, not the seat's; `_git_reason` is correct only because `_git_parse` joins `ctx["cwd"]` first
  (`:339`, `:342`).
- `.claude/settings.json:145-155` — the hook is registered with `"matcher": "Bash"` only.
- `.claude/workflows/fabrik-review-loop.js:139` — Workflow slices default to `agentType: 'fabrik-reviewer'`, so Workflow
  seats already carry the agent type the guard keys on; `:252` and `:266` carry the prose rule this change backs
  ("never write, copy, mkdir or cd-and-create anything outside SCRATCH — your working directory is the LIVE repo").
- `tests/test_seat_guard.py` — 33 tests drive `decide()`/`main()` with synthetic payloads.

## External dependencies (fetched 2026-10-15)

- PreToolUse hooks "also run inside subagents … the input carries the `agent_id` and `agent_type` common input fields
  that identify the subagent"; `permissionDecision: "deny"` blocks the call and shows Claude the reason; a matcher of
  only letters and `|` is "Exact string, or list of exact strings" — https://code.claude.com/docs/en/hooks (WebFetch,
  exa, re-fetched 2026-10-15 by the plan's grounding seat). The built-in tool table lists Edit, Write and NotebookEdit and
  no MultiEdit — https://code.claude.com/docs/en/tools-reference (exa).
- There is no per-subagent cwd or write-path option; a hook keyed on `agent_type` is the documented way to scope a
  subagent — https://code.claude.com/docs/en/sub-agents and https://code.claude.com/docs/en/permissions (WebFetch);
  permissions "isn't a security boundary … Use both for defense-in-depth" (same page).
- Worktree isolation refuses Edit/Write and git aimed at the main checkout, but "a command that writes into the main
  checkout without running git there, such as `cp` or a shell redirect, isn't refused"; a changed worktree is kept until a
  sweep; it starts from committed state — https://code.claude.com/docs/en/worktrees (WebFetch).
- The built-in Bash sandbox is session-wide only ("subagents … use the same sandbox configuration") —
  https://code.claude.com/docs/en/sandboxing (WebFetch).
- Bash-string write detection catches literal paths, not interpreters: a 22-pattern deny list was bypassed by `perl -i` —
  https://github.com/anthropics/claude-code/issues/40408 (exa); OS enforcement is the boundary and hooks are
  defence-in-depth —
  https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/
  (exa).

## Constraints Digest

| Quote | Source |
|---|---|
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |

## The delta — B: widen the seat guard (judge panel 3/3)

1. **No file-writing tool — pinned, not hooked.** A seat already holds no Write, Edit or NotebookEdit tool
   (`commands/_agents/fabrik-reviewer.md:4`), so a tool-write deny would never fire. A test pins that tool list instead,
   so a future edit that grants a write tool fails the suite and has to bring its own guard. The hook's matcher stays
   `Bash` and `.claude/settings.json` is not touched.
2. **Shell writes with a literal destination.** `_simple_commands()` keeps each OUTPUT redirect's target (`>`, `>>`,
   `>|`, `<>`, `&>`, `&>>`, and `>& <file>`) with its command instead of dropping it — also when the command's word list
   is empty or ends on a keyword or closer (`> f`, `{ …; } > f`, `( … ) > f`, `done > f`, `exec 3> f`, `X=1 > f`) — and
   drops an fd number from the words only when it is glued to the operator (`2>`; `2 >` is a word `2` and a
   redirect), decided on the tokeniser's own stream: a digit token is an fd only when
   `tell(operator) - tell(digit) == len(operator)` (no gap, whatever the operator's length — `>`, `>>`, `>&`) and
   the digit token's last source character, at `tell(digit) - 2` (shlex's `tell` reads one character ahead), is not a
   quote (`"2">x` is the word `2`, as in bash). Only `>&` takes an all-digit or `-` target as an fd duplication; `&>` always writes a file. Any
   destination whose LEXICAL path — `os.path.normpath` of it joined to the cwd, no symlink resolved — lies under
   `/dev/` (`realpath` would send `/dev/stderr` to the hook's own stdio, never `/dev/`) (`> /dev/null`, `dd of=/dev/null`, `tee /dev/stderr`), a `-`
   value of `-o`/`-O` (stdout) and input redirects are never destinations. `_scan()` gains a
   write rule, judged on every simple command BEFORE its `if not words` and every `continue`, so a redirect on a `cd`,
   `bash -c` or keyword line is seen. Destinations: every redirect target; `tee` operands; `cp`/`install`/`ln` — the
   last operand, or the `-t` value (alone, in a flag cluster `-rt <dir>`, glued `-t<dir>`, or
   `--target-directory[= ]<dir>`), every operand of `install -d`, and the cwd for a one-operand `ln`; EVERY operand of
   `mv` and of `rsync --remove-source-files` (both delete their source), else `rsync`'s last operand;
   `rm`/`rmdir`/`unlink`/`shred`/`touch`/`mkdir`/`truncate`/`gzip`/`gunzip` (every operand, each verb's value-taking
   options skipped; `gzip`/`gunzip` with `-c`/`--stdout`/`-l`/`-t` write no file); `sort -o`, `curl -o`/`--output`, `wget -O`; `sed` with `i` anywhere in a short flag cluster (`-i`, `-Ei`, `-ni.bak`: the rest of the cluster after `i` is the
   suffix) or `--in-place[=SUF]` (its file
   operands, after the script, unless `-e`/`--expression`/`-f` gives it) and `perl` with `i` in a short cluster that
   is not `-M`/`-m`/`-I` (its file operands after the code from `-e` or a cluster ending in `e`); `dd of=`. Each
   joins the tracked `cwd`, a leading `~` is outside scratch, and a path naming `/tmp`, `/tmp/claude-<uid>` or
   `/tmp/claude-<uid>/<slug>` itself is outside scratch (an ancestor of other sessions' scratch is never this seat's).
   A path holding a brace (`{`), or a `..` segment after a glob character, is outside scratch, like a `$` (its
   expansions can leave the directory it starts in: `touch <scratch>/{x,/../../opt/f}`,
   `<scratch>/*/../../opt/f`); the cost, accepted, is that `mkdir -p <scratch>/{a,b}` is refused and a seat writes
   `mkdir -p <scratch>/a <scratch>/b`. A path holding a glob character (`*?[`) is judged by the DIRECTORY before it —
   the path cut back to the last `/` before the first such character — which must be inside scratch and not one of
   those ancestors, compared after `realpath` (`rm -f <scratch>/*.tmp` stays allowed; `rm -rf /tmp/*` and
   `rm -rf /tmp/cl*` do not). `_in_scratch()` decides the rest. A copy FROM the live tree INTO scratch
   stays allowed — `cp` and `install` sources are reads.
3. **Unparseable.** The existing fallback (`:510-517`) also denies an untokenisable command that names one of those write
   verbs as a word not preceded by `/`, `-` or `.`, or an output redirect to something other than `/dev/…` or an fd —
   never on a bare `echo` (an unterminated quote with no write stays allowed, `2>/dev/null` included).
4. **Docs.** The `docs/workstation/hooks-index.md` row for `seat_guard.py` names the write rule and states the blind
   spot.
5. **Two scanner defects the write rule rides on (pre-existing, found by the plan review).** `env -C <dir> cmd` moves
   the tracked cwd for that one command only (today `_strip` rewrites it for the rest of the line, so
   `env -C <scratch> true; git reset --hard` passes the git rule), and redirects on that command resolve against
   the cwd from before it. `_HEREDOC` no longer matches a here-string: `<<<` opened a phantom heredoc that hid every
   following line up to one equal to its word, `git reset` included.

**Where the grammar is decided.** This section states the rule's principle and the cases the plan review settled;
a further shell-grammar edge case is decided by Phase A's tests and its reviews, against the running hook, never
by another round of prose here (the plan review's scope-growth stop, 2026-10-22).

**The blind spot, stated (COBRA, D-253):** the cheapest way past the rule is a write the Bash string does not show — an
interpreter (`python -c "open(p,'w')"`, `shutil.rmtree`), a script file, a write whose destinations come from stdin or a
search (`xargs rm`, `find -delete`, `find -exec`), a write nested deeper than the scanner's three levels of `bash -c`/`$(…)`,
a side-effect write by a tool run in the live tree (`pytest`'s `.pytest_cache`), and a variable holding the path
(fail-closed only when the variable is the destination itself). The guard is defence-in-depth against ACCIDENTAL writes, not a boundary against an
adversarial seat; the brief's prose stays as the second layer. Write verbs and forms outside the list are blind spots too: `chmod`/`chown`,
`patch`, `split`, `tar -x`/`-C`, `unzip -d`, `bzip2`/`xz`, `curl -O` and a bare `wget URL` (both write into the cwd),
`sed`'s `w file` and `s///w file`, and any other verb or form until a refused-or-missed seat write names it
(§ Lifecycle, growth). A `$(…)`/backtick body is judged against the cwd from before the command line's own `cd`
(the scanner extracts substitutions before it tracks `cd`): `cd <scratch> && v=$(touch x)` is refused and
`cd <live> && v=$(touch x)` started in scratch is missed — accepted until a seat trips it, the tripwire below. **Tripwire:** a confirmed seat write to a live tree through
an interpreter re-opens this design with approach D (below) or a filesystem-level fence.

## Contract deltas

- A seat's Bash command with a literal write destination outside scratch, previously allowed, is now refused (the
  hook file is fleet-synced). **MIRROR — the shapes that now fail:** a seat that writes a report straight into the repo
  (`> docs/…`), a refuter that "fixes" a file in place, and a seat whose brief names a scratch path outside `/tmp` and its
  `scratchpad_dir` — such as the D-836 SCRATCH root `<main>/.tmp/runs/<sid>/`. A census of every seat brief on the hub
  (32 files: `commands/_sources/`, `commands/_fragments/`, the review-loop script, the agent definition, the two reference
  docs) found none: every brief names `RUN-SCRATCH` (`docs/reference/command-run-protocol.md:620`, under the session
  scratchpad), and SCRATCH is named for the orchestrator's own writes only. Re-checked 2026-10-22 after D-961 moved
  hub seats to the Agent tool: the Agent-tool briefs (`commands/_fragments/subagents-core.md`,
  `commands/_fragments/no-workflow-hub.md`, each review command's seat brief) name a `seat-` folder under
  `RUN-SCRATCH` too. So no scratch root is added.
  **As built (D-XXXX): the census was wrong, and a scratch root IS added.** The plan's step-7 replay of 54,727 real
  seat commands found 2,713 new refusals. 418 were hub seats writing their D-836 run folder `<repo>/.tmp/runs/<sid>/`,
  and 1,863 were fabrik-lib seats writing the `<worktree>/.tmp/<run>/seat-…` folders their briefs name. So a path
  inside a repo's `.tmp/` (one whose parent holds `.git`; gitignored by convention) is scratch, minus another session's `.tmp/runs/<sid>/` and the ancestors `.tmp`
  and `.tmp/runs`. The same replay added three more reads: a variable assigned a literal on the line, `$PWD`, and a
  `for` loop over plain words; it also fixed the extractor to honour escapes and double quotes. The residue is 42
  refusals (0.08%); the plan's Evidence carries each class. The Phase A review's round 1 then made the variable
  table conservative (and kept every variable away from the kill and git rules), read quoted operators as data, and
  bounded `.tmp` to a repo's; the replay after it leaves 40 new refusals in 55,791 commands (0.07%), measured with
  every `cd` taken as succeeded because the seats' scratch directories have been swept since they ran. After the
  review's round 3 (a glob judged by one listing of its directory, only `mkdir` making a `cd` target), 43 in 56,669.
- The tool list of `fabrik-reviewer` becomes a tested contract: granting it Write/Edit/NotebookEdit fails a test.
- Non-seat agents and the lead: no change.

## Lifecycle

- **Adoption:** ships with the next merge of `worktree-intel`; the post-merge sync distributes the hook to every
  synced repo.
- **Growth, with measured triggers:** a new seat agent type joins `SEAT_TYPES` only when it is read-only by contract; a new
  write verb joins the list when a refused-or-missed seat write names it.
- **Retirement:** the rule retires when Claude Code offers a per-subagent filesystem fence (a sandbox or write-path option
  scoped to a subagent) — then the fence replaces the string rule.

## Cost

One hook file (+≈250 lines), its tests (+≈220 lines), one doc row. No disk, no retention, no brief or settings change.
No new hook invocation: the Bash hook already runs on every seat command.

## Validation

Each behaviour gets a test in `tests/test_seat_guard.py`, seen red first:

1. The `fabrik-reviewer` agent definition grants no Write, Edit or NotebookEdit tool.
2. The lead (no `agent_id`) and a non-seat agent type writing anywhere are allowed.
3. A seat redirect to a live path (`echo x > Makefile` with cwd = the repo) is denied; `> /dev/null`, `2>&1` and a redirect
   into scratch are allowed.
4. A seat `cp <live> <scratch>/` is allowed; `cp <scratch>/x Makefile`, `rm -rf <live dir>`, `sed -i … <live file>`,
   `perl -pi … <live file>`, `tee <live file>`, `dd of=<live file>`, `touch ~/x` and a write on a `cd`/`bash -c` line are
   denied; `cd <scratch> && touch x`, `mkdir -p <scratch>/d 2>/dev/null` and `truncate -s 0 <scratch>/f` are allowed.
5. An untokenisable command naming a write verb is denied.
6. A crash inside the new path still fails open: no deny, only the existing `updatedInput` envelope for a seat
   (the crash is injected in-process, the one grader that cannot run through the subprocess harness).
7. The scanner fixes of delta 5: `env -C` scoped to its command; a here-string hides nothing.

## Decisions taken

- **The fence over the grammar** (D-1129, 2026-10-22). The Opus + Fable panel was unanimous after round 1 confirmed 21
  parser holes. It supersedes "B over A and D" below for the BOUNDARY: B's parser stays, but only as the fail-closed
  fallback (§ Amendment 2026-10-22).

- **B over A and D** (D-913) — the judge panel (three Sonnet seats, 2026-10-15) ranked B first unanimously: it covers both
  dispatch paths, builds on the existing hook, and needs no brief, cwd or retention change; each judge named the
  interpreter blind spot as the strongest point against it, which § The delta states with its tripwire.
- **`perl -i` joins the write list** (a judge's graft): an in-place flag is as literal as `sed -i`. A blanket deny of
  `python -c`/`perl -e` naming a live path is NOT taken — seats read live files that way for probes, and its fire rate on
  legitimate reads is unmeasured.

## Rejected alternatives

- **A — `isolation: 'worktree'` on the review-loop `agent()` calls.** Covers Workflow seats only (the Agent-tool fallback
  stays open); the documentation says `cp` and shell redirects into the main checkout are not refused, which is exactly
  the incident class; ≥7 cwd-relative brief instructions to rewrite; seats see committed state only; `.venv` is absent in
  synced projects; kept worktrees add to the 25 (≈3.5 GB) already on disk.
- **D — both.** All of A's cost for a marginal gain on one path; re-opened only by the tripwire above.
- **C — the built-in Bash sandbox.** Session-wide only, so it would fence the lead too; cut.
- **A per-seat cwd.** The Workflow `agent()` options and the Agent tool take no cwd; not an option.

## fabrik-lib verdict

Build. Nothing in fabrik-lib parses shell destinations or keys a hook on a subagent type; the existing hub hook is the
natural home.

## Documentation landing sites

- `docs/workstation/hooks-index.md` — the `seat_guard.py` row (write rule, blind spot).
- `CHANGELOG.md` — one `### Changed` entry.
- The module docstring of `.claude/hooks/seat_guard.py` — the rule, its limits and the COBRA line.

## Open / blocking unknowns

None. The guard keys on the Bash payload's `agent_type`, which the hook already reads for every seat today (the git and
kill rules); the build adds one live seat probe of the new rule.
