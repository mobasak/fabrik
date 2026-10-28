# T06 — `agents_spawn.py add`, part 1: the lock, the preflight, the worktree, the binding, the registry, the item
Appetite: 165

## Scope
Creates `scripts/sysadmin/agents_spawn.py` (verified absent this run) and the `add` dispatch in `agents_up.sh`, implementing spec § The delta D1's helper (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:84-88`), D2 steps (1), (2), (4), (5) with its lock and idempotency (`:96-132`), D3's trust refusal (`:150-152`) and D6's memory floor and refusal record (`:206-215`), with W-14219e6f points 9 and 12 and plan-review pass 1, C4, C5, C9, C10. Steps (3), (6), (7) are T08's, which extends the same `add` function; T06's tests call its step functions directly (no env switch that skips the launch), and the set reaches master only through the one merge request after T10, so no master build carries a half `add`.

Invariants and touchpoints:
1. **Dispatch.** `agents_up.sh add <repo> <name> [--role <role>] [--item <W-id>]` dispatches before the grid's arguments as `rotate-session` does (`scripts/sysadmin/agents_up.sh:72-75`): `exec python3 "<script dir>/agents_spawn.py" add "$@"`.
2. **The root (C10).** `root = os.path.realpath(<repo>)` before any use — the trust key, the lock path, the session name — so a symlinked or trailing-slash path names the same repo.
3. **The lock.** `lock_path(root)` = `<git common dir>/fabrik-agents.lock` (`git -C <root> rev-parse --path-format=absolute --git-common-dir`, run with `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` removed, as `scripts/sysadmin/agents_up.sh:114`); `agents_lock(root)` takes `fcntl.flock(LOCK_EX)` on it. Both module-level (T07 imports them). Every later step runs under it.
4. **Preflight (D2 (1)), before any write**; each refusal exits 2 with the reason on stderr and appends one JSON line `{"at", "repo", "name", "step", "reason"}` to `~/.claude/state/agents-spawn.jsonl` (a state record beside `rotations.jsonl`, never a logfile): name matches `[a-z0-9][a-z0-9-]{0,31}`, is not a coordinator name, not the merge owner (read as `scripts/sysadmin/agents_up.sh:100-109`), and no LIVE pid-bearing identity-store row binds it in scope; `root` is trusted in the active account's config (`$HOME/.claude-fleet/active/.claude.json` → `projects[root].hasTrustDialogAccepted is true`; absent/unreadable → refuse with "open <root> once in Claude Code and accept the trust dialog"); the start is capped (`systemctl --user show-environment` answers) unless `FABRIK_AGENTS_UNCAPPED=1` (D4, `:172-174`); headroom ≥ 2 GB.
5. **Headroom (D6; W-14219e6f point 12; C4).** From the slice's cgroup (`systemctl --user show -p ControlGroup fabrik-agents.slice` → `/sys/fs/cgroup<path>`; seam `FABRIK_AGENTS_CGROUP_DIR`): headroom = limit − (`memory.current` − `memory.stat`'s `inactive_file`). **Decided:** limit = `memory.high`; when it reads `max` (the `FABRIK_AGENT_SLICE_MAX` override sets MemoryHigh to infinity, `scripts/sysadmin/agents_up.sh:404-407`), limit = `memory.max`; both `max`, or any value unreadable → refuse ("no measurable memory limit on fabrik-agents.slice"). Exposed as `headroom_bytes()` for T08's re-measure.
6. **Base branch (W-14219e6f point 9).** `resolve_base(root)` reads `<root>/.fabrik/work/config.json`'s `base_branch` FIRST (the hub's says `master`), and only when absent runs `git ls-remote --symref origin HEAD` (`merge_request.py`'s order, `scripts/merge_request.py:301-307`; its network call is `_remote_refs`, `:263-282`); that failing refuses: "no base_branch in <root>/.fabrik/work/config.json and origin's HEAD cannot be read (offline?) — set base_branch".
7. **Worktree (D2 (2); C5).** `git -C <root> worktree add -b worktree-<name> .claude/worktrees/<name> <base>`. A leftover branch `worktree-<name>`: `git merge-base --is-ancestor worktree-<name> <base>` true → `git branch -D worktree-<name>` (safe only AFTER that explicit check — plain `-d` tests merge into HEAD/upstream, not `<base>`) then add; false → refuse naming it. A worktree already in place for the name is kept.
8. **Binding (D2 (4)).** Mint `str(uuid.uuid4())`; run `python3 <hub>/scripts/whoami_agent.py --spawned <name> --session-id <uuid> --repo <root> --lock-fd <fd>` with `pass_fds=(fd,)` (T01); exit 1 → refuse "name held by a live session", 2 → refuse with its stderr, 3 or other → "whoami crashed: <stderr>" (T01's codes). `<hub>` = `Path(__file__).resolve().parents[2]` — no `/opt/fabrik` literal, so the write-root census (`tests/test_hub_write_root.py:478`) needs no row. Where `.fabrik/session-agents.json` exists, also write `{uuid: name}` by atomic replace; a repo with none gets NO file (`scripts/sysadmin/agents_up.sh:199-200`).
9. **Item (D2 (5); C9 — DECIDED: assign on the main checkout, the store of record).** `assign` is the distributor's verb (`scripts/work.py:3228-3232`), and the coordinator assigns on MAIN, the store of record (D-516, `scripts/work.py:5633-5637`); a worker's tree sees main's assignment only after it merges main, which the work store already prompts (`_merge_waiting`, `scripts/work.py:5656`, the merge rung at `:5930-5942`). So with `--item <W-id>`: run `python3 <root>/scripts/work.py assign <W-id> --owner <name>` in `root` with the caller's environment passed through unchanged (the coordinator's `CLAUDE_AGENT`/binding is the distributor identity; `add` never sets one), then `python3 <root>/scripts/work.py commit-items` (the store's own commit verb for item files, `scripts/work.py:4286-4313`, which refuses where it must not run — its refusal also stops `add`) so the assignment is on the base branch; both BEFORE any pane exists. The builder's first prompt (T02) tells it to merge the base branch when the item is not in its tree. A non-zero exit of either stops `add` at step 5 with that command's message.
10. **Idempotency (D2, `:129-132`).** Each step checks its artifact first (worktree, the name's binding in scope, registry row, item owner) and skips when present; a failing step leaves the earlier ones and prints `add stopped at step <n> (<name>) — re-run: agents_up.sh add <repo> <name> …`.

DO-NOT: start any tmux session or pane, or regenerate a launcher (T08); implement `remove` (T09); write a registry where none exists.

Depends: T01, T03
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py tests/test_hub_write_root.py -q
Docs: the new script's header — `# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_spawn.py` in its first lines (T09 refreshes the doc's rendered block)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH (new)
- tests/test_agents_spawn.py — new
- scripts/sysadmin/agents_up.sh — the `add` dispatch lines only

## Behavior Contract
- **Given** a trusted, capped repo with headroom, **When** `agents_up.sh add <R> b-1 --item W-x` runs through the new dispatch lines, **Then** under the repo's agents lock it creates `.claude/worktrees/b-1` on `worktree-b-1` from the base tip, writes the spawned binding, writes the registry row only where a registry exists, makes b-1 the owner of W-x on the main checkout and commits the item file, in that order (scripts/sysadmin/agents_up.sh:72-75; spec § The delta D2; plan-review pass 1, C4, C9)
- **Given** two `add` runs for one repo started together, **When** both finish, **Then** the second waited on the lock and no worktree, binding or registry row exists twice (spec § The delta D2)
- **Given** a bad name, a coordinator or merge-owner name, a live-bound name, an untrusted root, an uncapped start without the override, or under 2 GB headroom, **When** `add` runs, **Then** it exits 2 naming the reason, leaves no worktree or branch, and appends one line to `agents-spawn.jsonl`, while a symlinked or trailing-slash path to a trusted root passes (spec § The delta D2 step 1; spec § The delta D6; plan-review pass 1, C10)
- **Given** `memory.current` 20 GB with 8 GB `inactive_file` under a 31 GB `memory.high`, then `memory.high` reading `max`, **When** headroom is measured, **Then** the first reads 19 GB and the second is measured against `memory.max`, and with both `max` or a value unreadable `add` refuses (spec § The delta D6; W-14219e6f point 12; plan-review pass 1, C4)
- **Given** a leftover branch `worktree-b-1`, **When** `add` runs, **Then** one that is an ancestor of `<base>` is deleted and re-created and one that is not refuses naming it (spec § The delta D2 step 2; plan-review pass 1, C5)
- **Given** `base_branch` in `.fabrik/work/config.json` and no reachable remote, **When** `add` runs, **Then** it uses the configured base with no network call, and with no config and no remote it refuses naming the config key (scripts/merge_request.py:301-307; W-14219e6f point 9)
- **Given** a repo with no registry, **When** `add` runs, **Then** no `.fabrik/session-agents.json` is created and the binding alone records the builder (scripts/sysadmin/agents_up.sh:199-200)
- **Given** `assign` refused because the caller is not the distributor, **When** `add` runs, **Then** it stops at step 5 with that message, and a re-run by the distributor completes step 5 without creating the worktree or binding twice (scripts/work.py:3228-3232; spec § The delta D2; plan-review pass 1, C9)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- scripts/whoami_agent.py
- tests/test_agents_up.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
