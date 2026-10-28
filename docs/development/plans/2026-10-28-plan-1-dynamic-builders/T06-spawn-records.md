# T06 — `agents_spawn.py add`, part 1: the lock, the preflight, the worktree, the binding, the registry, the item
Appetite: 150

## Scope
Creates `scripts/sysadmin/agents_spawn.py` (verified absent this run) and the `add` dispatch in `agents_up.sh`, implementing spec § The delta D1's helper (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:84-88`), D2 steps (1), (2), (4), (5) and its lock and idempotency (`:96-132`), D3's trust refusal (`:150-152`) and D6's memory floor and refusal record (`:206-215`), with W-14219e6f points 9 and 12 decided below. Steps (3), (6), (7) — cold start, placement and launch, launcher regeneration — are T08's, which extends the same `add` function; T06's tests call its step functions directly (no env switch that skips the launch is added), and the set reaches master only through the one merge request after T10, so no master build ever carries a half `add`.

1. **Dispatch.** `agents_up.sh add <repo> <name> [--role <role>] [--item <W-id>]` dispatches before the grid's arguments exactly as `rotate-session` does (`scripts/sysadmin/agents_up.sh:72-75`): `exec python3 "<script dir>/agents_spawn.py" add "$@"`.
2. **The lock.** `agents_lock(root)` — a context manager taking `fcntl.flock(LOCK_EX)` on `lock_path(root)` = `<git common dir>/fabrik-agents.lock` (`git -C <root> rev-parse --path-format=absolute --git-common-dir`, run with the git location variables unset as `scripts/sysadmin/agents_up.sh:114` does). Both are module-level functions T07 imports. Every later step runs under it.
3. **Preflight (D2 (1)), before any write**, each refusal exit 2 with the reason on stderr and one JSON line appended to `~/.claude/state/agents-spawn.jsonl` (`{"at", "repo", "name", "step", "reason"}` — a state record beside `rotations.jsonl`, never an app logfile): the name matches `[a-z0-9][a-z0-9-]{0,31}`, is not a coordinator name, not the repo's merge owner (read as `scripts/sysadmin/agents_up.sh:100-109` reads it), and no LIVE pid-bearing identity-store row binds it in this repo's scope; the repo root is trusted in the active account's config (`$HOME/.claude-fleet/active/.claude.json`, `projects[<root>].hasTrustDialogAccepted is true`; unreadable or absent → refuse with the one-line remedy "open <root> once in Claude Code and accept the trust dialog"); the start is capped (`systemctl --user show-environment` answers) unless `FABRIK_AGENTS_UNCAPPED=1` (D4, `:172-174`); and slice headroom is at least 2 GB.
4. **Headroom (D6; W-14219e6f point 12).** Read the slice's cgroup (`systemctl --user show -p ControlGroup fabrik-agents.slice` → `/sys/fs/cgroup<that path>`; seam `FABRIK_AGENTS_CGROUP_DIR` for tests): headroom = limit − (`memory.current` − `memory.stat`'s `inactive_file`). **Decided:** the limit is `memory.high`; when it reads `max` (the `FABRIK_AGENT_SLICE_MAX` override sets MemoryHigh to infinity, `scripts/sysadmin/agents_up.sh:404-407`), the limit is `memory.max`; both `max`, or any value unreadable, refuses ("no measurable memory limit on fabrik-agents.slice"). Exposed as `headroom_bytes()` so T08 re-measures with the same code (point 7).
5. **The base branch (W-14219e6f point 9).** `resolve_base(root)` reads `<root>/.fabrik/work/config.json`'s `base_branch` FIRST (the hub's says `master`, read this run), and only when it is absent runs `git ls-remote --symref origin HEAD` (the same order as `merge_request.py`'s `_resolve_base`, `scripts/merge_request.py:301-307`; the network call is its `_remote_refs`, `:263-282`); that call failing refuses: "no base_branch in <root>/.fabrik/work/config.json and origin's HEAD cannot be read (offline?) — set base_branch". So an offline `add` in a configured repo never touches the network.
6. **The worktree (D2 (2)).** `git -C <root> worktree add -b worktree-<name> .claude/worktrees/<name> <base>` from the base tip. A leftover branch `worktree-<name>`: re-created (deleted with `git branch -d`, then added) only when `git merge-base --is-ancestor worktree-<name> <base>` says it is merged; otherwise refuse naming it. A worktree already in place for the name is kept (idempotency).
7. **The binding (D2 (4)).** Mint `str(uuid.uuid4())` and run `python3 <hub>/scripts/whoami_agent.py --spawned <name> --session-id <uuid> --repo <root> --lock-fd <fd>` with `pass_fds=(fd,)` (T01's CLI) — `<hub>` derived from `Path(__file__).resolve().parents[2]`, never a `/opt/fabrik` literal, so the write-root census (`tests/test_hub_write_root.py:478`) needs no row. In a repo that HAS `.fabrik/session-agents.json`, also write `{uuid: name}` by atomic replace (temp in the same folder + `os.replace`); a repo with no registry gets NO file (`scripts/sysadmin/agents_up.sh:199-200` would otherwise drop every bindings-only builder).
8. **The item (D2 (5)).** With `--item <W-id>`: `python3 <root>/scripts/work.py assign <W-id> --owner <name>` (`scripts/work.py:6660-6662`) run in `<root>`, BEFORE any pane exists; its failure stops `add` at this step.
9. **Idempotency (D2, `:129-132`).** Each step first reads whether its artifact exists (worktree, the name's binding in scope, registry row, item owner) and skips it when it does; a failing step leaves the earlier ones in place and prints `add stopped at step <n> (<name>) — re-run: agents_up.sh add <repo> <name> …`.

DO-NOT: start any tmux session or pane, or regenerate a launcher (T08); implement `remove` (T09); write a registry where none exists.

Depends: T01, T03
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py tests/test_hub_write_root.py -q
Docs: the new script's header — `# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_spawn.py` in its first lines (the doc's rendered `## Related scripts` block is refreshed by T09)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH (new)
- tests/test_agents_spawn.py — new
- scripts/sysadmin/agents_up.sh — the `add` dispatch lines only

## Behavior Contract
- **Given** a trusted, capped repo with headroom, **When** `agents_up.sh add <R> b-1 --item W-x` runs, **Then** under the repo's agents lock it creates `.claude/worktrees/b-1` on `worktree-b-1` from the base tip, writes the spawned binding, writes the registry row only where a registry exists, and makes b-1 the owner of W-x, in that order (spec § The delta D2)
- **Given** two `add` runs for one repo started together, **When** both finish, **Then** the second waited on the lock and no worktree, binding or registry row exists twice (spec § The delta D2)
- **Given** a bad name, a coordinator or merge-owner name, a live-bound name, an untrusted root, an uncapped start without the override, or under 2 GB headroom, **When** `add` runs, **Then** it exits 2 naming the reason, leaves no worktree or branch, and appends one line to `agents-spawn.jsonl` (spec § The delta D2 step 1; spec § The delta D6)
- **Given** `memory.high` reading `max`, **When** headroom is measured, **Then** it is measured against `memory.max`, and with both `max` or a value unreadable `add` refuses (spec § The delta D6; W-14219e6f point 12)
- **Given** a leftover branch `worktree-b-1`, **When** `add` runs, **Then** a merged one is re-created and an unmerged one refuses naming it (spec § The delta D2 step 2)
- **Given** `base_branch` in `.fabrik/work/config.json` and no reachable remote, **When** `add` runs, **Then** it uses the configured base with no network call, and with no config and no remote it refuses naming the config key (scripts/merge_request.py:301-307; W-14219e6f point 9)
- **Given** a repo with no registry, **When** `add` runs, **Then** no `.fabrik/session-agents.json` is created and the binding alone records the builder (scripts/sysadmin/agents_up.sh:199-200)
- **Given** an `add` that stopped at the item step, **When** it is re-run, **Then** the worktree and binding are not created twice and the run completes the item step (spec § The delta D2)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- scripts/whoami_agent.py
- tests/test_agents_up.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
