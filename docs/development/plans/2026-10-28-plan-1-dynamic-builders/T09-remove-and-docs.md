# T09 — `agents_spawn.py remove` (never loses work, resumable) and the verbs' documentation
Appetite: 135

## Scope
Implements spec § The delta D7 (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:217-237`), D4's `remove` half (`:175-177`) and the D9 guard for it (`:255-256`), with W-14219e6f point 5 and plan-review pass 1, C5, D2, D4, D5, D6; adds the `remove` dispatch to `agents_up.sh`; documents both verbs (spec § Documentation landing sites, `:397-404`).

Invariants and touchpoints:
1. **Dispatch.** `agents_up.sh remove <repo> <name>` dispatches beside `add` (T06's lines, the `scripts/sysadmin/agents_up.sh:72-75` pattern) to `agents_spawn.py remove`; the root is `realpath`'d as in T06.
2. **Resumable (D4).** A re-run that finds `.claude/worktrees/<name>` already gone skips the worktree checks and the `worktree remove`, and finishes what is left — the pane (if still tagged), the merged branch, the registry row, the launchers — so a `remove` interrupted after the worktree went completes. The `running` run-record check still applies on a resume, and a resume requires the name to have at least one of a registry row, an in-scope binding, or a tagged pane — a name with none is "no such builder <name> in <repo>", exit 2 (plan-review pass 2, D-N2).
3. **Under the repo's agents lock (T06), refuse (exit 2, every reason named, one `agents-spawn.jsonl` row) unless ALL hold**, every failing git call read as a refusal (D7):
   - no `~/.claude/state/command-runs/<sid>.json` with status `running` for ANY session id the name owns — its registry ids AND every id the identity store binds to it in scope;
   - `git -C <wt> status --porcelain` prints nothing;
   - `git -C <wt> symbolic-ref -q HEAD` names a branch (detached refuses; any branch name, so pre-spec builders retire the same way);
   - work is safe: `git rev-list <base>..HEAD` empty (`<base>` = T06's `resolve_base`) → retireable without a push; else the branch has an upstream and `git rev-list @{u}..HEAD` is empty; a never-pushed branch with commits (rc 128 on `@{u}`) refuses;
   - **ignored files, classified (panel PF1 — an executed listing of a hub worktree shows `.claude/scheduled_tasks.lock`, `.droid/`, `.fabrik/state/`, `.hypothesis/`, `logs/`, `scripts/.droid/`, `.tmp/`, none of which the pass-1 rule allowed):** (a) the regenerable set matches by path SEGMENT anywhere in the path (`scripts/__pycache__/`, `x/.pytest_cache/`); (b) a repo-configured list `remove_ignored_ok` in `<root>/.fabrik/work/config.json` (path prefixes; the hub's seed, added to the hub config by the coordinator's store edit at the post-merge proof: `.claude/scheduled_tasks.lock`, `.droid/`, `scripts/.droid/`, `.fabrik/state/`, `.hypothesis/`, `logs/`, `.tmp/`) lets those go; (c) `.tmp/` is split — `.tmp/runs/` is walked per the seed rule below and everything else under `.tmp/` is judged by (b); every path let go is printed `let go: <path>`, every other ignored path refuses, named. The list is a spec correction for the T10 receipt (spec D7 named only the cache trees).
   - ignored files (D2 — `--directory` collapses an ignored `.tmp/` to the single entry `.tmp/`, executed by the review): the dependency and cache trees are listed WITH `git -C <wt> ls-files --others --ignored --exclude-standard --directory` and let go when they are `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`; `.tmp/runs/` is walked DIRECTLY (`os.scandir` two levels: `.tmp/runs/<sid>/<run>`, the layout `scripts/command_run.py:1720-1722` writes) and each run folder refuses while ANY seed under `~/.claude/state/command-runs/seeds/` names a path inside it, whichever session wrote the seed (W-14219e6f point 5: a session that moved between worktrees leaves folders in two checkouts, so the scan is by PATH), else it is let go (`command_run.py` prunes `.tmp/runs/` after 14 days, `scripts/command_run.py:1522-1532`); every other ignored path refuses, each named.
   - **Point 5's other half (D6).** A run folder belongs to a session by its path segment — `.tmp/runs/<sid>/…` (`scripts/command_run.py:1720-1722`). Folders under another checkout's `.tmp/runs/<sid>/` whose `<sid>` is one of the name's ids are listed on stdout as `kept: <path>` and never touched.
4. **Then, in order (D7; C5):** the live read (T08a's `list-panes` read — an error or empty answer while the grid is up refuses and removes nothing); `tmux kill-pane -t <the pane id tagged @agent <name>>`; if the pane's window still exists, `select-layout -t <window id> even-horizontal`, else `kill-session -t "=<S>+<k>"` for that window's overflow session when one exists (T03 invariant 4's name) (tmux already removed the window, D4); `git -C <root> worktree remove .claude/worktrees/<name>` (never `--force`); the branch deleted with `git branch -D <branch>` ONLY AFTER `git merge-base --is-ancestor <branch> <base>` succeeds (plain `-d` tests merge into HEAD or its upstream, not `<base>`), kept otherwise; the name's rows dropped from `.fabrik/session-agents.json` (atomic replace, only where it exists); `heal_registry` (T08b) for the remaining builders' rows; the launchers regenerated (T08c's step-7 call). Charter and transcript stay (`scripts/sysadmin/archive_transcripts.py:101`, `:250-254` still archive a removed worktree's transcript).
5. **Docs.** `docs/reference/repo-coordinator-rollout.md` § Launching a repo's builders (`docs/reference/repo-coordinator-rollout.md:189`) and § The Windows side (`:308`): both verbs with arguments, exit codes and refusals, the named-window layout and grouped sessions, `--window`, the generated tabbed `.bat` and the remembered desktop, the coordinator's sizing rule (spec D6: spawn only when ready items it would assign outnumber idle builders AND the band is GREEN with no LANE; retire at the item boundary; read the refusals in `agents-spawn.jsonl`), the agents lock (shared with rotate_session.py, T07), the item hand-off on the main checkout (T06), the builder's `done — retire me` message as the usual trigger for `remove` (panel PO3), and the builder charter; then `python3 scripts/render_doc_script_links.py` refreshes its `## Related scripts` block (`:408`). `docs/reference/operator-agent-requirements.md` § 3 rows 3.1-3.8 (`docs/reference/operator-agent-requirements.md:42-49`) gain their record (this plan, D-1306).

DO-NOT: pass `--force` to `git worktree remove`; delete an unmerged branch; touch a transcript, a charter or another checkout's files.

Depends: T08c
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py -q
Docs: docs/reference/repo-coordinator-rollout.md, docs/reference/operator-agent-requirements.md (above); INDEX.md rows for `scripts/sysadmin/agents_spawn.py`, `tests/test_agents_spawn.py`, `docs/reference/agents/builder.md` ride the orchestrator's Deltas (governance file)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh — the `remove` dispatch lines only
- docs/reference/repo-coordinator-rollout.md
- docs/reference/operator-agent-requirements.md

## Behavior Contract
- **Given** a run record `running` under the id the store binds to the name after a re-bind, a dirty worktree, a detached HEAD, or a git call that fails, **When** `remove` runs for each, **Then** it exits 2 naming the cause and the worktree is still there (spec § The delta D7)
- **Given** commits beyond the base on a never-pushed branch, **When** `remove` runs, **Then** it refuses, and after the push it retires; a branch with no commits beyond the base and no upstream retires (spec § The delta D7; spec § Validation)
- **Given** an ignored `.tmp/` holding `.tmp/runs/<sid>/x/` that a seed written by another session names, plus `.venv` and `__pycache__`, **When** `remove` runs, **Then** it refuses naming the seed; with no seed naming it the worktree is removed; an unknown ignored file (a `.env` copy) refuses, named, while a worktree that ran pytest once and hosted one Claude session (`__pycache__` dirs, `.pytest_cache`, `.claude/scheduled_tasks.lock`, `logs/`) retires with each listed `let go:` (spec § The delta D7; W-14219e6f point 5; plan-review pass 1, D2; panel PF1)
- **Given** every check passing and the name the last pane of window `agents-2`, **When** `remove` runs, **Then** the pane is gone, `<S>+2` is killed, the worktree removed without `--force`, a branch that is an ancestor of `<base>` deleted and an unmerged one kept, the registry row dropped, the launchers regenerated, the transcript untouched (spec § The delta D4; spec § The delta D7; plan-review pass 1, C5)
- **Given** the name the last pane of window `agents` with `agents-2` live, **When** `remove` runs, **Then** `agents` ceases, `<S>`'s current window is a live window, and a following `add` places into the grid (spec § Validation; plan-review pass 1, D5)
- **Given** a tmux read that errors or returns nothing while the grid is up, **When** `remove` runs, **Then** it refuses and removes nothing (spec § The delta D9)
- **Given** a `remove` interrupted after the worktree was removed, **When** it is re-run, **Then** it skips the worktree checks, still refuses on a `running` record, and drops the registry row and regenerates the launchers, while a name with no registry row, binding or tagged pane exits 2 as no such builder (plan-review pass 1, D4; plan-review pass 2, D-N2)
- **Given** `.tmp/runs/<the name's sid>/r1/` under another checkout, **When** `remove` succeeds, **Then** stdout lists it as `kept:` and it still exists (W-14219e6f point 5; plan-review pass 1, D6)

## Context Files
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh
- docs/reference/repo-coordinator-rollout.md
- docs/reference/operator-agent-requirements.md
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
