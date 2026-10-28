# Agent identity — naming a session that is already running

**Box-local.** How an agent gets a name, why a window `/rename` is not one, and what to do with two
or three windows in one repo. Design: `docs/superpowers/specs/2026-09-16-multi-agent-self-naming-identity-design.md`
(D-267, D-268).

## The problem, in one measurement

Identity has always resolved from `CLAUDE_AGENT`, a **launch-time** environment variable. A window
`/rename` changes the label in the UI and reaches nothing else. Measured 2026-09-16 on three live
`trade-intelligence` windows the operator had named `agent-1`, `agent-2`, `agent-3`:

```
pid 48200 · CLAUDE_AGENT=<UNSET>
pid 49965 · CLAUDE_AGENT=<UNSET>
pid 49985 · CLAUDE_AGENT=<UNSET>
```

…and **0 of that repo's last 40 commits** carried an `Agent-Name` trailer, while 40 of 40 carried
`Agent-Role`. Three agents, one checkout, nothing able to say which of them did anything.

## Naming a session

**A window that is already running** — no relaunch, the chat history survives:

```bash
python3 /opt/fabrik/scripts/whoami_agent.py --as agent-2
python3 /opt/fabrik/scripts/whoami_agent.py --who      # prints the resolved name
```

**A window you are about to open** — still the better path when you have the choice:

```bash
CLAUDE_AGENT=agent-2 claude -n agent-2-<repo>
```

Both are valid; the env var always wins over a binding, so a named launch never needs the command.

**A session that does not exist yet — the spawner-only binding** (dynamic builders, W-b9ad80ae). The
spawner (`agents_spawn.py add`) mints a fresh session id for the builder it is about to launch and
records it before the pane exists:

```bash
python3 /opt/fabrik/scripts/whoami_agent.py --spawned b-1 --session-id <fresh uuid> --repo <repo> --lock-fd <n>
```

It is the one input that takes a session id as an argument, an exception to "the id comes from the
environment only", bounded by a caller proof checked in this order:

1. `--lock-fd <n>` is an open descriptor on exactly `<git common dir of --repo>/fabrik-agents.lock`;
2. a fresh open of that file cannot take its `flock` (`EWOULDBLOCK`): somebody holds it. If the probe
   gets the lock, nobody holds it; the probe releases it at once and the call refuses;
3. only then may the passed descriptor take the lock without blocking. That is a no-op for the open
   file description that already holds it, and it fails for a copy that is open but unlocked while
   another process holds the lock.

The spawner holds that lock across the whole `add` and passes the descriptor with
`subprocess.run(..., pass_fds=(fd,))`. The id must be a lowercase UUID that no row of the store has
ever carried, so the call can never re-name an existing session. `--session-id`, `--repo` and
`--lock-fd` are refused without `--spawned`, `--spawned` is refused without all three, and it takes
no `--force`. The scope is `--repo`'s common dir, read with `GIT_DIR`, `GIT_COMMON_DIR`,
`GIT_WORK_TREE` and `GIT_INDEX_FILE` removed, so an inherited value cannot redirect it.

Exit codes, for `--spawned` only: **0** written · **1** a live session holds the name in this repo ·
**2** refused (usage, caller proof, a malformed or already-known id) · **3** an unexpected exception,
so a spawner can tell a crash from a collision. `--as` and `--who` keep their codes.

The row carries `"spawned": true` with `pid` and `pid_start` null, and no `predecessor`, because
stamping the caller's process would make the spawner the holder of the builder's name. ⚠️ **The
null-pid gap:** a row with no pid is not a holder, so until the builder re-binds itself on its first
turn (`--as <name>`, which writes its own pid) nothing in the store reserves the name. The spawner's
own live-session preflight and the agents lock cover `add` itself. The cheapest bypass is a caller
that takes the agents lock itself. That is accepted, because only hub tooling (`agents_spawn.py`,
`rotate_session.py`) takes it, and the row it writes is marked `spawned` and reserves nothing.

## How it resolves

`CLAUDE_AGENT` (when well-formed) → this session's **binding** → `""`. A malformed env value falls
through to the binding, which changes nothing for anyone actually named — a malformed value already
resolved to `""` before this existed.

The binding is keyed on `CLAUDE_CODE_SESSION_ID`, which — unlike `CLAUDE_AGENT` — **is** exported
into every shell a live session runs, and **git hooks inherit it** (executed: a `commit-msg` hook
printed the sid while `CLAUDE_AGENT` was empty). ⚠️ The `claude` process itself does **not** carry
it, so the session's pid is found by walking `/proc` ancestry, never by matching the sid.

Store: `$AGENT_IDENTITY_FILE`, else `~/.claude/state/agent-identity.jsonl`. `$HOME`-keyed, not
`$CLAUDE_CONFIG_DIR`-keyed, so a session pinned to another account slug shares it. Append-only, last
row wins per session, rows trimmed at 30 days by the writer — nothing else prunes that directory — except each
(repo, name)'s newest binding, kept whatever its age, because a repo with no registry gets its launcher's builders
from these bindings and a quiet repo binds nothing for weeks (W-89474fc1; one row per name a repo ever bound).

## What it refuses, and why

- **A name outside `^[a-z0-9-]{1,32}$`.** `Agent-2`, `agent_2` and `agent.2` are accepted by
  `mail.py` but rejected by `command_run.py` and `agent_role.py`, so such a name would bind and then
  be silently dropped downstream — one session with two identities and no error anywhere.
- **A name a LIVE session already holds in this repo** (scoped to the git toplevel, not the cwd — a
  plain `cd` defeated a cwd-scoped check). `--force` overrides and records that it did. The one
  exception is this window's own earlier session: `/clear` mints a new session id in the SAME `claude`
  process, so a row carrying this process's exact `pid` and `pid_start` (and agreeing with
  `CLAUDE_PID` when it is set) is a predecessor, not a holder — the bind needs no `--force`, with or
  without it the new row records `predecessor` (the most recent such row of this name in this
  scope), and a live foreign holder later in the store still refuses (W-34cb1ef9). A row written
  before start times existed (`pid_start` absent) is never a predecessor and still needs `--force`.
  `predecessor` can cycle — a `/resume` into an older id in the same process points back — so a reader
  walking the chain must bound itself.
- **Re-binding one session id to a different name**, without `--force`. A Task subagent inherits its
  dispatcher's session id, so this would otherwise let a seat silently re-identify the session that
  dispatched it.

## What it does NOT do — read this before relying on it

- **It is not a lock against `--force`.** A bind is serialized (an `flock` around the whole
  read-modify-write, so a concurrent sibling can neither double-bind nor be erased by the 30-day
  trim), but `--force` deliberately overrides a live holder. Nothing downstream catches two
  sessions on one name: the hub's `check_commit_trailers.py` resolves `CLAUDE_AGENT`, else this
  session's binding (D-442), and warns only when the SIGNED `Agent-Name` differs from it — two
  sessions bound to one name both pass. No project repo installs that trailer check, so there the
  trailer is a claim (`docs/reference/multi-agent-operating-model.md` § The Agent-Name trailer is a
  claim).
- **A binding with no session pid reserves nothing.** If the `/proc` ancestry walk cannot find the
  `claude` ancestor, the row carries no pid and cannot hold the name against a sibling. The bind
  says so in its success message rather than implying protection it does not have.
- **The SessionStart hooks bind late.** `agent_role.py` (the role charter) and `session_orient.py`
  (the unnamed-session advisory) both run at session start, so naming yourself mid-flight takes
  effect for them at the NEXT start. Attribution in run records is immediate.
- **SessionStart prints a live-binding line naming who holds what.** `session_orient.py`'s
  multi-agent model output (`_model_line`, spec 2026-09-29-hub-worktree-cutover-design.md §
  D5(a)) lists every LIVE binding in the repo — `` `<name>` (pid <n>) `` per session, scoped to the
  git common dir, filtered to bindings whose pid is still alive at the row's recorded start — right
  alongside the move-to-worktree instruction for a non-owner main-checkout session. This is the
  COBRA counter to that instruction (D-253): binding yourself as the merge owner silences the
  instruction, but a second session bound to the same name is then VISIBLE in this line, not
  invisible the way the underlying store's own "not a lock against `--force`" gap otherwise leaves
  it. A session named at launch by `CLAUDE_AGENT` writes no binding, so it never appears here.
- **The mandated shared-append commit path fires no git hook.** `git commit-tree` + `git update-ref`
  — which `CLAUDE.md` requires for `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`
  and `INDEX.md` — runs none of the four commit hooks (executed). On that path you call
  `--who` yourself while composing the message, and write the `Agent-Name:` trailer by hand.

## Working with 2–3 agents in one repo today

1. Name each window once, with the command above.
2. Write `Agent-Name: <yours>` in every commit's trailer block — by hand; no hook injects it.
3. Never `git commit -- <paths>` on the four shared-append files; use the private-index recipe in
   `CLAUDE.md` § Behavior.
4. Take a plan-lock before touching a path a sibling might.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/whoami_agent.py`
<!-- END related-scripts -->
