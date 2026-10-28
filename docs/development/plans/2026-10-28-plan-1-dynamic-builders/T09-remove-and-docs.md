# T09 — `agents_spawn.py remove` (never loses work) and the verbs' documentation
Appetite: 120

## Scope
Implements spec § The delta D7 (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:217-237`), D4's `remove` half (`:175-177`) and the D9 guard for it (`:255-256`), with W-14219e6f point 5 decided below; adds the `remove` dispatch to `agents_up.sh`; documents both verbs (spec § Documentation landing sites, `:397-404`).

1. **Dispatch.** `agents_up.sh remove <repo> <name>` dispatches beside `add` (T06's lines, the `scripts/sysadmin/agents_up.sh:72-75` pattern) to `agents_spawn.py remove`.
2. **Under the repo's agents lock (T06), refuse (exit 2, every reason named, one `agents-spawn.jsonl` row) unless ALL hold**, every failing git call read as a refusal (D7):
   - no `~/.claude/state/command-runs/<sid>.json` with status `running` for ANY session id the name owns — the registry's ids for it AND every id the identity store binds to it in this repo's scope;
   - `git -C <wt> status --porcelain` prints nothing;
   - `git -C <wt> symbolic-ref -q HEAD` names a branch (detached refuses — any branch name, so pre-spec builders on branches like `infra-3-dynamic-builders` retire the same way);
   - work is safe: `git rev-list <base>..HEAD` empty (`<base>` from T06's `resolve_base`) → retireable without a push; else the branch has an upstream and `git rev-list @{u}..HEAD` is empty; a never-pushed branch with commits (rc 128 on `@{u}`) refuses;
   - ignored files (`git -C <wt> ls-files --others --ignored --exclude-standard --directory`): `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache` are let go; a `.tmp/runs/<x>` folder refuses while ANY seed under `~/.claude/state/command-runs/seeds/` names a path inside it, whichever session wrote the seed (**W-14219e6f point 5, decided:** a session that moved between worktrees can leave run folders in two checkouts and its seed may name either, so the seed scan is by PATH, never by the removed name's session ids), and is otherwise let go (`scripts/command_run.py:1522-1532`: `command_run.py` prunes `.tmp/runs/` after 14 days); any other ignored file refuses, each named.
   - **Point 5's other half:** run folders the name's session ids own in OTHER checkouts (a `.tmp/runs/` under another worktree or the main checkout whose run record names one of those ids) are listed on stdout as "kept: <path>" and never touched.
3. **Then, in order (D7):** read the live panes (T08's D9 read — an error or empty answer while the grid is up refuses and removes nothing); `tmux kill-pane -t <the pane tagged @agent <name>>`; `select-layout … even-horizontal` on its window if the window still exists, else `tmux kill-session -t =<S>-<k>` for the emptied window's grouped session (tmux already removed the window, D4); `git -C <root> worktree remove .claude/worktrees/<name>` (never `--force`); `git branch -d <branch>` only when `git merge-base --is-ancestor <branch> <base>`; drop the name's rows from `.fabrik/session-agents.json` (atomic replace, only where the file exists); regenerate the launchers (T08's step-7 call). The charter and the transcript stay (the nightly archive's `MAIN_GLOBS`, `scripts/sysadmin/archive_transcripts.py:101`, `:250-254`, still reaches a removed worktree's transcript).
4. **Docs.** `docs/reference/repo-coordinator-rollout.md` § Launching a repo's builders (`docs/reference/repo-coordinator-rollout.md:189`) and § The Windows side (`:308`): the two verbs with their arguments, exit codes and refusals, the four-pane named-window layout and grouped sessions, `--window`, the generated tabbed `.bat` and the remembered desktop, the sizing rule the coordinator applies (spec D6: spawn only when ready items it would assign outnumber idle builders AND the band is GREEN with no LANE; retire at the item boundary), the agents lock (shared with rotate_session.py, T07), and the builder charter; then `python3 scripts/render_doc_script_links.py` refreshes its `## Related scripts` block (`:408`) from T06's AFTER-EDIT header. `docs/reference/operator-agent-requirements.md` § 3 rows 3.1-3.8 (`docs/reference/operator-agent-requirements.md:42-49`) gain their record (this plan, D-1306) as spec § Documentation landing sites says.

DO-NOT: pass `--force` to any git call; delete a branch that is not merged; touch a transcript, a charter or another checkout's files.

Depends: T08
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py -q
Docs: docs/reference/repo-coordinator-rollout.md, docs/reference/operator-agent-requirements.md (both above); INDEX.md rows for `scripts/sysadmin/agents_spawn.py`, `tests/test_agents_spawn.py` and `docs/reference/agents/builder.md` ride the orchestrator's Deltas (INDEX.md is a governance file)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh — the `remove` dispatch lines only
- docs/reference/repo-coordinator-rollout.md
- docs/reference/operator-agent-requirements.md

## Behavior Contract
- **Given** a run record `running` under the session id the identity store binds to the name after a re-bind, **When** `remove` runs, **Then** it exits 2 naming that record (spec § The delta D7)
- **Given** a dirty worktree, a detached HEAD, or a git call that fails, **When** `remove` runs, **Then** it exits 2 naming each, and the worktree is still there (spec § The delta D7)
- **Given** commits beyond the base on a never-pushed branch, **When** `remove` runs, **Then** it refuses, and after the branch is pushed it retires; a branch with no commits beyond the base and no upstream retires (spec § The delta D7; spec § Validation)
- **Given** a `.tmp/runs/x/` folder that a seed under `seeds/` names, written by another session, **When** `remove` runs, **Then** it refuses naming the seed, and an unknown ignored file also refuses while `.venv` and `__pycache__` do not (spec § The delta D7; W-14219e6f point 5)
- **Given** every check passing and the name the last pane of window `agents-2`, **When** `remove` runs, **Then** the pane is gone, `<S>-2` is killed, the worktree is removed without `--force`, a merged branch is deleted, the registry row is dropped, the launchers regenerated, and the transcript file is untouched (spec § The delta D4; spec § The delta D7)
- **Given** a tmux read that errors or returns nothing while the grid is up, **When** `remove` runs, **Then** it refuses and removes nothing (spec § The delta D9)
- **Given** a run folder of the name's session in another checkout, **When** `remove` succeeds, **Then** stdout lists it as kept and it still exists (W-14219e6f point 5)

## Context Files
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh
- docs/reference/repo-coordinator-rollout.md
- docs/reference/operator-agent-requirements.md
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
