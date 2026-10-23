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
| I1 | "forbid writes under the repo root by construction (cwd = scratch, repo mounted read-only) instead of by prose" (01M4PHYNXJ row 1791209046) | IN, delivered as the fence since D-1129 | § Amendment 2026-10-22 — the whole filesystem mounted read-only (`--ro-bind / /`), the payload cwd unchanged; in fallback mode, § The delta — no write tool (delta 1) and a shell-write rule (delta 2), defence-in-depth against accidental writes (its blind-spot paragraph) |
| I2 | "launch finder and refuter seats with cwd set to a fresh scratch directory (or isolation: worktree), never the caller's main checkout" (01M4PHYNXJ row 1791049341) | IN, delivered differently | § Rejected alternatives — A (worktree) and the cwd option, which does not exist; the guard covers both dispatch paths instead, the seats' cwd unchanged |
| I3 | "hand seats a ready probe script" (01M4PHYNXJ row 1791225410) | OUT-OF-SCOPE | W-f7bf9a54 — a separate change with its own measure (seat turns spent building probes) |
| I4 | D-1129, the Opus + Fable panel (unanimous): "Review-seat write isolation becomes a filesystem fence, not a growing shell grammar" | IN | § Amendment 2026-10-22 — the fence |
| I5 | The whole-plan review round 1: 21 confirmed code defects, about 15 of them let-throughs (receipt `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md` § Round 1 findings) | IN | § Amendment — what the fence closes, and the fallback that fails closed where it cannot run |
| I6 | W-9013addb, "a heredoc misread through a `"$(…)"` inside double quotes still hides later lines" | IN | § Amendment — under the fence the misread can hide no write; in the fallback the construct is unmodelled and refused |
| I7 | The panel's cobra: "bind too much writable space (`--bind /tmp`, or the whole repo `.tmp`) so that 'writes in scratch work' passes" | IN | § Amendment — Validation 9 asserts the bind set exactly |
| I8 | The panel's underivables: bwrap on other hosts; the harness's cwd tracking, background tasks and the worktree guard around a rewritten command | IN | § Amendment — Open unknowns, each resolved by a named build proof |

## Goal

(Fallback mode only since D-1129 — the fence's goal is § Amendment, The goal, restated.) A review seat cannot write outside its scratch directory by mistake — it holds no file-writing tool, and a shell command
whose destination is a literal path outside scratch is refused — on BOTH dispatch paths, without changing the seats'
working directory, their briefs, or the lead session.

## Amendment 2026-10-22 — the fence (D-1129)

**Why the design changes.** The parent's tripwire (§ The delta, its last paragraph) re-opens this design "with approach D
or a filesystem-level fence" on a confirmed interpreter write. The whole-plan review's round 1 confirmed 21 code defects
against the converged parser (receipt `docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md`,
§ Round 1 findings), all executed. About 15 of them are writes, kills or git writes the parser let through:
- `env -C /tmp bash -c "cd $PWD && git reset --hard"`;
- a conditional `cd`; `kill 1234 -1`; writes to `/dev/shm`;
- a heredoc body holding `$(…)`.

The rest are false refusals and robustness defects. At the pin b0fa6d66d the panel's Opus seat replayed `decide()`: it
allowed `touch /dev/shm/x`, `true || cd /tmp; rm -rf src`, `kill 1234 -1` and an interpreter `shutil.rmtree`, and it
refused `if (( n > 3 ))`. The Opus + Fable panel ruled unanimously (D-1129): stop growing the grammar and fence the
filesystem.

**The goal, restated (it replaces § Goal while the fence runs; § Goal stays the fallback mode's goal).** A review seat's
shell command cannot write outside its session's scratch, and cannot reach the masked host services that write for it
(the docker daemon, D-Bus and the user runtime sockets, tmux, and on WSL, where the masks hold, the Windows interop that
launches host processes outside every Linux namespace): the operating system refuses it whatever the command's
syntax, interpreter or nesting. The fence applies on both dispatch paths and leaves the lead session and the corpus seat
brief unchanged: that brief already assumes a `cd` does not carry, "The shell returns to the LIVE checkout before every
Bash call, so every path … is ABSOLUTE under SCRATCH" (`.claude/workflows/fabrik-review-loop.js:230`). A brief changes
only where it names a scratch path outside the session scratchpad (a repo `.tmp` folder, `/tmp`) or relies on a `cd`
carrying to the next call (Contract deltas).
- **Residuals, accepted.** Other sockets and every localhost TCP service stay reachable, because the network is not
  unshared (executed in round 2: a fenced python got `+PONG` from Redis on 127.0.0.1:6379). The hook's settings entry
  fails open (`[ -f "$f" ] || exit 0; python3 "$f"; exit 0`, `timeout: 5`), so a missing hook file, an import crash or
  a timeout runs the seat command unwrapped, as the seat guard's entry has done since it shipped.

**The design.**
1. **The fence rides the existing rewrite.**
   - `seat_guard.py` already answers every allowed seat Bash call with `updatedInput`, which replaces the command
     before it runs and carries no `permissionDecision` (`rewrite()`, `:1419-1436`; `main()` `:1456-1461`; the seat
     test at `decide()` `:1392-1394`). Anchors are read at worktree-intel 89143f4ba.
   - The rewrite wraps the seat's WHOLE command as `/usr/bin/bwrap <args> -- /bin/bash -c <shlex.quote(command)>`,
     with the dotenv prefix inside it. The wrap applies whether or not the command already starts with
     `export PYTHON_DOTENV_DISABLED=1`: the `_ALREADY_OFF` early return (`:1434-1435`) skips only the added prefix,
     never the wrap.
   - **Fail closed for a seat.** If building the wrapper raises (a `cwd` that is not a directory), the seat's call is
     DENIED with the reason, never run unwrapped. The non-seat path keeps today's
     fail-open.
   - `updatedInput` without a `permissionDecision` is not documented (the hooks page documents it combined with
     `allow` or `ask`). The hook has relied on it since D-801, and the hooks-index row records it working live on
     2.1.296. Validation 10 re-proves it on the build's Claude Code version.
2. **The bind set is the policy.**
   - The order: `--ro-bind / /`, `--dev /dev` (a private devtmpfs, so a `/dev/shm` write lands in the sandbox's own
     tmpfs), `--proc /proc`.
   - Then the service masks:
     - `--ro-bind /dev/null /run/docker.sock` (`/var/run` is a symlink to `/run`);
     - `--tmpfs /run/user/<uid>` (D-Bus and the user's runtime sockets);
     - `--tmpfs /tmp/tmux-<uid>`;
     - on WSL: `--tmpfs /run/WSL` (the interop sockets), `--tmpfs /mnt` (the drvfs mounts that hold every Windows
       executable), and `--unsetenv WSL_INTEROP`.
     - `--tmpfs /mnt` is skipped when the payload cwd or the scratchpad lies under `/mnt` (a repo on drvfs), since
       masking it would hide the seat's own cwd; that host keeps interop as its recorded residual.
     - Every mask is added only when its path exists: bwrap cannot create a mount point under the read-only root
       (executed in pass 5: a mask on a missing `/run/…sock` exits rc 1, "Can't create file … Read-only file
       system"). `--unsetenv` is not a path and always applies.
   - **WSL interop is a host service.** Executed at panel time: inside a fence with only `--ro-bind / /`, `--dev`,
     `--proc`, `--unshare-pid` and `--die-with-parent`, `/mnt/c/Windows/System32/cmd.exe /c ver` returned rc 0
     (`Microsoft Windows [Version 10.0.26200.9457]`), and a Windows process can write the live tree through
     `\\wsl.localhost\…`. The interop launcher is a kernel-wide binfmt registration, so a namespace cannot remove it;
     the masks above are expected to remove what it needs, which the mode probe and Validation 10 prove (the masked
     run was not executed at design time: the worktree guard refused the probe). On a WSL host the mode probe
     (Design 3) also binds a Windows executable read-only into its private folder (the shape of a seat that copies
     one into its scratch) and runs it inside the masked fence. If it launches, the fence still runs, because it
     still blocks every Linux-side write and fallback mode stops interop no better; the mode cache records
     `interop: open`, the hooks-index row names it, and interop is that host's accepted residual.
   - Then the writable binds:
     - `--bind <scratchpad_dir>` (the payload's session scratchpad);
     - `--bind <run folder>` when it exists. The run folder is `<toplevel of the payload cwd's main checkout>/.tmp/runs/<sid>/`
       (D-836 durable SCRATCH, resolved with `git rev-parse --git-common-dir` the way `command_run.py` resolves it);
     - `--bind <the session run record's scratch>` when that folder exists outside the run folder: a seeded or resumed
       run reuses the seed's folder, named after the seed's `session_id` (`command_run.py:1621-1623`). The hook reads
       the record at `command_run.py`'s `_record_path(sid)` (`~/.claude/state/command-runs/<sid>.json`, or under
       `COMMAND_RUN_DIR`), takes its `scratch` key, and binds it only when it resolves under `<main checkout>/.tmp/runs/`,
       the same root `command_run.py` checks before it reuses a seed's folder (`Path(prev).resolve().is_relative_to(root.resolve())`, `:1610`).
     - The lookups are one `git rev-parse` (2 ms measured) and one small JSON read per seat call, inside the hook's
       5-second timeout.
   - Then `--setenv TMPDIR <scratchpad_dir>`, `--unshare-pid`, `--die-with-parent`, and `--chdir <payload cwd>`.
   - **Width, stated (a residual, accepted).** The hook does not know a seat's own folder, so the fence is per SESSION.
     A seat can still write its siblings' folders and the lead's pins in the same scratchpad, never anything else.
   - The parent's repo-wide `.tmp` scratch rule is dropped (round 1, W9). The network is not unshared, because briefs
     allow local probes.
3. **Mode detection, and the fallback.**
   - The hook probes namespace creation once: the fixed flag set (masks and binds over a private temporary folder, never
     a per-call path) running `/bin/true`. It caches the result in `/tmp/claude-<uid>/seat-guard-bwrap.json`, keyed by
     the binary's path and mtime, the kernel release, the `kernel.apparmor_restrict_unprivileged_userns` value and a
     hash of the flag set, so a changed policy or flag set re-probes. A per-call failure is never cached. One the
     hook can see before it answers (a `cwd` that is not a directory) denies that call (Fail closed, above); a bind
     source that vanishes after the answer surfaces as bwrap's error exit, which writes nothing.
   - When that probe fails, or `/usr/bin/bwrap` is absent, the hook is in FALLBACK mode. The fallback triggers are:
     - user namespaces are refused (Ubuntu 24.04's AppArmor default when
       `kernel.apparmor_restrict_unprivileged_userns` is 1);
     - `scratchpad_dir` is absent or missing.
   - In fallback mode the parser runs. A seat command holding any construct the parser does not model is REFUSED:
     - a heredoc to a shell, `eval`/`source`;
     - `$'…'`, `((`/`[[`;
     - an unknown wrapper, a conditional `cd`;
     - a `$(…)` in a write or cd position.
   - The refusal says it is fallback mode.
   - In fallback mode an exception inside `decide()` on a seat payload DENIES the call and names fallback mode. Today
     `main()` turns it into an allow (`reason = ""`, seat_guard.py `:1452-1455`); that stays for non-seat payloads and
     in fence mode, where the fence is the boundary.
4. **Which rules run in fence mode.** The kill and git rules still run first, as cheap refusals with good messages. The
   parser's WRITE rule (parent delta 2) and its unparseable-write fallback (delta 3) do NOT run, because the fence is
   the boundary; their false refusals (R1-R4) end with them. Under the fence, `--unshare-pid` makes a `kill` of an
   outside pid fail with ESRCH, and a git write to the live tree fails with EROFS.

**Executed on this box (2026-10-22/23, the lead session).**
- Ubuntu 24.04.3 LTS on WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`.
- `/usr/bin/bwrap` is bubblewrap 0.9.0, mode `-rwxr-xr-x`, not setuid.
- `/proc/sys/kernel/apparmor_restrict_unprivileged_userns` does not exist.
- Inside `bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /dev/shm --bind <seat> <seat> --unshare-pid
  --die-with-parent --chdir <worktree> python3 -c …`:
  - the write into `<seat>` succeeded;
  - writes to `<worktree>/zz_fence_probe`, `~/zz_fence_probe` and `/tmp/zz_fence_probe` each raised
    `Read-only file system`, and none exists afterwards;
  - `os.getcwd()` was the worktree, and `os.getpid()` was 2.
- With `--setenv TMPDIR <seat>`, `tempfile.NamedTemporaryFile` landed in the seat folder.
- **The service escape, and its mask:**
  - Inside `bwrap --ro-bind / / --dev /dev --proc /proc --unshare-pid --die-with-parent`,
    `curl --unix-socket /var/run/docker.sock http://localhost/version` exited 0: the docker daemon answered, and a
    `docker run -v /:/h` would write anywhere.
  - With `--ro-bind /dev/null /run/docker.sock --tmpfs /run/user/1000` added, the same curl exited 7 (cannot
    connect).
- Per-call cost: 20 runs each of `bash -c true` gave 1.3 ms, and of the full wrapper 15.7 ms, so about 14 ms more per
  seat command. The mode probe runs once per binary, not per call.
- The spec-review seats (pass 1) reproduced the D-Bus socket as writable and `/tmp/tmux-1000` as reachable without the
  masks. They also showed `shlex.quote` round-tripping quotes, `$'…'`, heredocs and nested `$()` with the exit code
  kept, `--chdir` into the read-only tree working, and `--die-with-parent` killing a backgrounded child.

**External facts (fetched 2026-10-22, re-verified 2026-10-23).**
- Claude Code's own Bash sandbox uses bubblewrap on Linux and WSL2: "the sandbox relies on `bubblewrap` and `socat`".
  Its check row is `touch ~/sandbox-probe`, which "Fails with … `Read-only file system` on Linux and WSL2".
- On Ubuntu 24.04 "the default AppArmor policy prevents bubblewrap from creating the user namespaces it needs for
  isolation". The fix is needed only when `sysctl kernel.apparmor_restrict_unprivileged_userns` returns 1 (the page:
  "If the command returns `0`, skip this step … the key doesn't exist and you can skip this step").
- That sandbox is session-wide: "subagents run in the same process as the parent session and use the same sandbox
  configuration" — https://code.claude.com/docs/en/sandboxing (WebFetch; exa's 25,000-character fetch stops before it).
- bwrap, verbatim:
  - "bwrap is an unprivileged low-level sandboxing tool";
  - "the user namespace is required if bwrap is not run as root";
  - `--ro-bind` "Bind mount the host path SRC readonly on DEST"; `--bind` "Bind mount the host path SRC on DEST";
  - `--unshare-pid` "Create a new pid namespace";
  - `--die-with-parent` "Ensures child process (COMMAND) dies when bwrap's parent dies";
  - `--chdir` "Change directory to DIR"
  — https://manpages.debian.org/unstable/bubblewrap/bwrap.1.en.html (WebFetch; exa).
- "`PreToolUse`: `updatedInput` directly under `hookSpecificOutput` replaces a tool's arguments before it runs".
  "Claude Code evaluates permission rules and a Bash command's auto-background eligibility against the input your hook
  returns". A subagent's tool events "fire the same configured hooks as in the main conversation, and the input carries
  the `agent_id` and `agent_type` common input fields" — https://code.claude.com/docs/en/hooks (WebFetch).
- The parent's sources still stand: OS enforcement is the boundary and hooks are defence-in-depth (NVIDIA, § External
  dependencies), and a Bash-string deny list was bypassed by `perl -i` (issue 40408).

**Approaches (D-1129).**
- **Chosen: the fence through the hook's rewrite, with the parser as a fail-closed fallback.**
- **Rejected: (a) the fail-closed parser alone.** Five Phase A rounds plus round 1 left 21 confirmed defects, and the
  parent's own blind spots (interpreters, scripts, `find`/`xargs`, deep nesting) cannot be parsed by construction.
- **Rejected: (c) Claude Code's built-in sandbox.** It is session-wide, so it would fence the lead too. It is still
  session-wide on 2026-10-23.
- **Rejected: a per-seat Unix user.** It needs root to create users and sudo per command.
- **Rejected: Landlock directly.** It is built in here (ABI 7, per the panel's syscall probe), but it needs a helper or
  ctypes in the hook path. bwrap already ships it on this box and is what Claude Code itself uses.

**Contract deltas (MIRROR — the shapes that now fail).**
- A seat command that writes outside its session scratchpad and run folder fails at the OS with EROFS, whatever the
  parser would have said.
- These now fail:
  - a write to `/tmp` outside the scratchpad, such as `mktemp /tmp/x` (the parser counted all of `/tmp/` as scratch);
  - a `pytest` run in the live tree without `-p no:cacheprovider` (its `.pytest_cache` write);
  - a tool writing a cache under `$HOME`;
  - git commands that need to write the live index;
  - a call to the docker daemon, D-Bus or tmux, and on WSL any `/mnt` path and, where the masks hold, any Windows
    executable;
  - a `cd` that a later call relies on: the `cd` runs in the wrapped child, so it does not carry to the next call; a
    seat uses absolute paths or `cd` on the same line;
  - a backgrounded process outliving its Bash call (`--die-with-parent`; a seat that needs a long probe runs it in the
    foreground);
  - a seat that writes a `<worktree>/.tmp/<run>/seat-…` folder its brief names. That is the fabrik-lib brief shape the
    plan's replay counted (plan § Phase A Evidence; the plan and this spec give two counts for that class, 1,992 and
    1,863, so the number is not carried here).
- fabrik-lib is sync-excluded and does not receive this hook. A synced repo whose briefs name a repo `.tmp` folder must
  move them to the session scratchpad; the build's harvest replay (Validation 4) counts any.
- Inside the fence, `/bin/bash -c` does not load the harness's shell snapshot (its functions, such as the grep shim), so
  a seat command relying on one behaves as in a plain bash.
- `.claude/settings.json`'s `statusMessage` for the hook ("no pattern kills, git writes only in scratch") is updated to
  name the fence.
- Permission rules see the wrapped command (U6): a `Bash(<verb>:*)` allow or deny rule is not expected to match a seat
  call, so a deny a repo relies on for seats must live in the hook's kill or git rules. Validation 10 records what
  actually matches.
- The lead and non-seat agents: no change.
- A host without usable bwrap gets the parser in its stricter fail-closed form.

**Validation (each a test or an executed proof, red first).**
1. Each round-1 FALSE-GREEN command (the receipt's C1-C2, K1-K3, W1-W9), run for real through the rewritten command on
   a scratch copy, leaves the live tree byte-identical. A kill of an outside pid gets ESRCH. A `/dev/shm` write lands in
   the sandbox's private tmpfs, never the host's.
2. An interpreter write (`python3 -c open(<live>,'w')`, `perl -pi`, `shutil.rmtree`) to a live path fails inside the
   fence. The run uses the wrapper only, with the parser's write rule out of the path.
3. Writes into the scratchpad, the run folder and `TMPDIR` succeed; `pwd` inside is the payload cwd.
4. Equivalence: every allow case of `tests/test_seat_guard.py`, plus a fresh 3-day harvest of real seat commands, runs
   inside a throwaway worktree, never the live tree, wrapped and unwrapped. The unwrapped leg itself runs inside an
   outer fence, because harvested commands carry absolute paths: it binds writable the same scratchpad, run folder and
   `TMPDIR` the wrapped leg gets, the throwaway worktree, and a throwaway `$HOME`, so the only difference between the
   legs is the fence's own policy. A command whose destination is otherwise absolute compares on exit code only. The
   wrapped leg's EROFS lines under `$HOME` are U4's count. Exit code and stdout match, `$$`, `$PPID`
   and `ps` output excepted. False refusals are reported per N.
5. The lead (no `agent_id`) and a non-seat agent get no wrapper.
6. The rewrite round-trips quoting, including a command already starting with the dotenv export. It is wrapped too
   (the `_ALREADY_OFF` case).
7. Mode detection:
   - with bwrap absent, the mode probe failing, or `scratchpad_dir` missing, the hook is in fallback mode, refuses an
     unmodelled construct, and says so;
   - a grader that neuters the mode check, so fallback reads as fence, goes red;
   - a wrapper-build error on a seat payload denies the call, and so does an exception in `decide()` on a seat payload
     in fallback mode;
   - on WSL, a probe whose Windows executable launches inside the masked fence records `interop: open` and keeps
     fence mode; one that does not launch records `interop: masked`.
8. `--die-with-parent`: a backgrounded child is gone when the call ends.
9. The bind set is asserted exactly: {scratchpad_dir, the run folder when it exists, the run record's scratch when it
   exists outside the run folder and under `.tmp/runs/`}, writable; every service mask present for each path that
   exists; nothing else writable that persists outside the sandbox (the private `/dev` and the tmpfs masks excepted). The cobra counter is that adding `/tmp` or the repo `.tmp` turns a test red.
10. One live `fabrik-reviewer` seat through the Agent tool, before the merge:
    - it writes its seat folder;
    - it gets EROFS on a live path;
    - the docker curl fails; on WSL the run records whether a Windows executable launches, and it matches the mode
      cache's `interop:` value;
    - an allow-listed command (`git status`) is run, and the run records whether it prompted and which rule
      matched (U6, U2);
    - a later call in the same seat starts in the cwd the harness tracked, not the previous call's `cd` (U5);
    - a `run_in_background` call still delivers its output;
    - the `updatedInput` rewrite still applies on the build's Claude Code version.

**Open unknowns, each closed by a build proof.**
- (U1) Whether Claude Code's own worktree isolation guard reads the original command or the rewritten one
  (Validation 10).
- (U2) Whether read-only git commands (`git status`) fail when they cannot refresh the index under a read-only tree.
  The build probes it in a throwaway worktree.
- (U3) bwrap on other synced hosts. Mode detection falls back, and the refusal names the mode.
- (U4) Whether `$HOME` caches written by seat tools need a writable bind. The harvest replay (Validation 4) counts them.
- (U5) The cwd across calls. The `cd` runs in the wrapped child, so it cannot move the harness's shell: the expected
  behaviour is that the next call starts in the harness's tracked cwd, never the `cd` target (Contract deltas;
  Validation 10).
- (U6) Permission rules (and a Bash command's auto-background eligibility) are evaluated against the input the hook returns (External facts, the hooks
  page), so they see `/usr/bin/bwrap … -- /bin/bash -c '<quoted>'`, not the seat's command. Which allow rule a seat
  then needs, and whether a deny rule still bites, is proved by Validation 10's allow-listed call before the merge.

**Lifecycle.**
- **Adoption:** with the merge of `worktree-intel` after the live seat proof (Validation 10). The post-merge sync
  distributes it.
- **Growth, with measured triggers:**
  - a host service a seat reaches through a socket or an interop path joins the masks when a probe finds it;
  - a new writable bind joins only with a named brief that needs it and a test.
- **The parser:** it stays the fallback while any host may lack bwrap or allow it no user namespace. No retirement
  trigger is set: the mode cache is a local file and nothing collects it across hosts.
- **Retirement:** the fence moves to Claude Code's sandbox if that gains a per-subagent configuration (the parent's
  retirement clause).
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
(fail-closed only when the variable is the destination itself). The guard (fallback mode since D-1129) is defence-in-depth against ACCIDENTAL writes, not a boundary against an
adversarial seat; the brief's prose stays as the second layer. Write verbs and forms outside the list are blind spots too: `chmod`/`chown`,
`patch`, `split`, `tar -x`/`-C`, `unzip -d`, `bzip2`/`xz`, `curl -O` and a bare `wget URL` (both write into the cwd),
`sed`'s `w file` and `s///w file`, and any other verb or form until a refused-or-missed seat write names it
(§ Lifecycle, growth). A `$(…)`/backtick body is judged against the cwd from before the command line's own `cd`
(the scanner extracts substitutions before it tracks `cd`): `cd <scratch> && v=$(touch x)` is refused and
`cd <live> && v=$(touch x)` started in scratch is missed — accepted until a seat trips it, the tripwire below. **Tripwire:** a confirmed seat write to a live tree through
an interpreter re-opens this design with approach D (below) or a filesystem-level fence. (It fired: D-1129, § Amendment.)

## Contract deltas

- A seat's Bash command with a literal write destination outside scratch, previously allowed, is now refused (the
  hook file is fleet-synced). **MIRROR — the shapes that now fail:** a seat that writes a report straight into the repo
  (`> docs/…`), a refuter that "fixes" a file in place, and a seat whose brief names a scratch path outside `/tmp` and its
  `scratchpad_dir` — such as the D-836 SCRATCH root `<main>/.tmp/runs/<sid>/`. A census of every seat brief on the hub
  (32 files: `commands/_sources/`, `commands/_fragments/`, the review-loop script, the agent definition, the two reference
  docs) found none: every brief names `RUN-SCRATCH` (`docs/reference/command-run-protocol.md:616`, under the session
  scratchpad), and SCRATCH is named for the orchestrator's own writes only. Re-checked 2026-10-22 after D-961 moved
  hub seats to the Agent tool: the Agent-tool briefs (`commands/_fragments/subagents-core.md`,
  `commands/_fragments/no-workflow-hub.md`, each review command's seat brief) name a `seat-` folder under
  `RUN-SCRATCH` too. So no scratch root is added.
  **As built (superseded by D-1129, before its own row was minted): the census was wrong, and a scratch root IS added.** The plan's step-7 replay of 54,727 real
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

(The parser's lifecycle, for fallback mode; the fence's is § Amendment, Lifecycle.)

- **Adoption:** ships with the next merge of `worktree-intel`; the post-merge sync distributes the hook to every
  synced repo.
- **Growth, with measured triggers:** a new seat agent type joins `SEAT_TYPES` only when it is read-only by contract; a new
  write verb joins the list when a refused-or-missed seat write names it.
- **Retirement:** the rule retires when Claude Code offers a per-subagent filesystem fence (a sandbox or write-path option
  scoped to a subagent) — then the fence replaces the string rule.

## Cost

(Fallback mode. The fence adds about 14 ms per seat call, one `statusMessage` edit in `.claude/settings.json` and one
small mode-cache file under `/tmp/claude-<uid>/`: § Amendment.)

One hook file (+≈250 lines), its tests (+≈220 lines), one doc row. No retention, no corpus brief change.
No new hook invocation: the Bash hook already runs on every seat command.

## Validation

(The parser's behaviours, kept for fallback mode; the fence's are § Amendment, Validation.) Each behaviour gets a test in `tests/test_seat_guard.py`, seen red first:

1. The `fabrik-reviewer` agent definition grants no Write, Edit or NotebookEdit tool.
2. The lead (no `agent_id`) and a non-seat agent type writing anywhere are allowed.
3. A seat redirect to a live path (`echo x > Makefile` with cwd = the repo) is denied; `> /dev/null`, `2>&1` and a redirect
   into scratch are allowed.
4. A seat `cp <live> <scratch>/` is allowed; `cp <scratch>/x Makefile`, `rm -rf <live dir>`, `sed -i … <live file>`,
   `perl -pi … <live file>`, `tee <live file>`, `dd of=<live file>`, `touch ~/x` and a write on a `cd`/`bash -c` line are
   denied; `cd <scratch> && touch x`, `mkdir -p <scratch>/d 2>/dev/null` and `truncate -s 0 <scratch>/f` are allowed.
5. An untokenisable command naming a write verb is denied.
6. A crash inside the new path on a seat payload in fallback mode DENIES the call, naming fallback mode (D-1129 amendment, Design 3);
   on a non-seat payload it still fails open, with only the existing `updatedInput` envelope (the crash is injected
   in-process, the one grader that cannot run through the subprocess harness).
7. The scanner fixes of delta 5: `env -C` scoped to its command; a here-string hides nothing.

## Decisions taken

- **The fence over the grammar** (D-1129, 2026-10-22). The Opus + Fable panel was unanimous after round 1 confirmed 21
  code defects (about 15 of them let-throughs). It supersedes "B over A and D" below for the BOUNDARY: B's parser stays as the fail-closed
  fallback, and its kill and git rules also run in fence mode as early refusals (§ Amendment 2026-10-22).

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
- `.claude/settings.json` — the hook's `statusMessage` names the fence (§ Amendment, Contract deltas).
- `docs/workstation/hooks-index.md` — the row also names the fence, its masks, mode detection and the bwrap host prerequisite.
- The module docstring of `.claude/hooks/seat_guard.py` — the rule, its limits and the COBRA line.

## Open / blocking unknowns

The fence's open unknowns are U1-U5 in § Amendment; none blocks the design, and each is closed by a build proof.
