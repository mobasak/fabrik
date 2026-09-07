# Scratch sweep — agents clean their OWN session scratch and agent worktrees, interruptions included, with nothing deleted blindly

Status: DRAFT
Profile: small
**Owner:** fleet
**Date:** 2026-09-08
**Operator dispatch (2026-09-08):** "i want agents delete their own scratchpads when they are done, but time to time their work can be interrupt by network issues, they can fill context, or account quota holds interrupts them. for the future scratchpad usage, and also for the existing scratchpads agents must clear them when they are done with them" → "ok but we should not cause data loss, agents must know what will this script do while using it."

## What we already agreed

- **Goal (operator, verbatim above):** every agent clears its OWN scratch when done; the interrupted cases heal; the existing residue is cleared by its owners; no data loss; the script is self-describing.
- **Two binding constraints (operator):** (1) *"we should not cause data loss"* — nothing is deleted blindly: the DEFAULT is a dry-run table, `--apply` is opt-in, every candidate carries its class + reason + evidence, and a refusal set is hard-coded; (2) *"agents must know what will this script do while using it"* — the help text, the close-out print, the per-prompt line and the § EXIT sentence all say what it does and what it never touches.
- **Chosen mechanism (D-184, reversible):** ONE hub script `scripts/scratch_sweep.py` (absolute-path callable from every repo, like `claude_rotate.py --status`) with three modes — session (own scratchpad), `--worktrees` (own agent worktrees), `--dead` (the janitor) — and THREE triggers: the run-record close prints its dry-run table; a user-level hook prints one advisory line per prompt and at SessionStart (the compaction/resume path); a daily cron line removes DEAD sessions' scratch. Rejected: auto-apply at close (constraint 2 — the agent applies knowingly); age-only deletion of the unowned root-level entries (no owner to ask — listed, never removed without an explicit flag); blind removal of the dormant worktrees (the operator's word 2026-09-07: *"i dont want to delete them blindly"*) — their owners get a mail and the classifier; editing `libs/subagents/` (D-137, the fanout scratch leak is fabrik-lib's, filed `01M1YRSN7F0GYVTBK7D40GW1P5`).
- **Why a mail alone cannot do it (settled in chat):** "when done" is a moment an interruption skips and a mail is read only when a session chooses to; the binding trigger is a check that fires at a moment the agent is still editable — the close-out and the per-prompt/SessionStart hook (the self-watch's own lesson, D-163).
- **Liveness key (measured this run):** every live CLI writes `<config-dir>/sessions/<pid>.json` (`pid`, `sessionId`, `cwd`, `procStart`); the config dir is `CLAUDE_CONFIG_DIR` (`~/.claude-fleet/active` → an account dir), so the janitor scans `~/.claude/sessions` + `~/.claude-fleet/*/sessions` and validates `pid` + `procStart` against `/proc/<pid>/stat` — 9 of 9 live claude processes matched, 0 pid-recycled (Evidence Phase A). Second signal: a HELD `<sid>.selfwatch.lock` (`scripts/sysadmin/selfwatch_check.py:65-87`). Third: any process holding a cwd/fd under the dir.
- **Scope OUT:** the pool module's `/tmp/subagents-fanout-*` (fabrik-lib's, filed); pytest basetemps (pinned, `c5d8e4fb`); `.tmp/subagents/` spools (NEVER swept — `docs/workstation/cleanup-automation.md` § D); docker volumes (HARD STOP); transcripts and `~/.claude/state`.

Branch: **RICH** — goal, constraints and mechanism are pinned by the operator's words and this run's measurements; no brainstorm.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "agents delete their own scratchpads when they are done" | IN | Phase A (session mode) + Phase B trigger 1 (close-out) |
| I2 | "their work can be interrupt by network issues, they can fill context, or account quota holds" | IN | Phase B trigger 2 (per-prompt + SessionStart line — fires on the next prompt/resume, whatever killed the turn) + Phase B trigger 3 (dead-session janitor) |
| I3 | "for the future scratchpad usage" | IN | Phase C (§ EXIT sentence in both CLAUDE.md files + the universal marker) |
| I4 | "also for the existing scratchpads agents must clear them" | IN | Phase A.7 (per-repo + broadcast mail naming each repo's residue; the hook line nags every live session; the janitor takes the dead ones) |
| I5 | "we should not cause data loss" | IN | Phase A (refusal set, dry-run default, holder/keep/fresh classes, git's own refusals as second guards) |
| I6 | "agents must know what will this script do while using it" | IN | Phase A (`--help` contract + every row's reason), Phase B (the close-out prints the table + the exact apply command), Phase C (§ EXIT names the never-touches) |
| I7 | "shold we send a mail to them?" (2026-09-07) | IN | Phase A.7 — yes, as the durable notice and audit trail; the hook is the enforcement |
| I8 | the dormant worktrees (seo 28 · trade-intelligence 24 · web-ecommerce-factory 18 · fabrik-lib 2) and the ai-model-catalog stale registration — "dont delete them blindly" | IN (classifier + mail) | Phase A.5 `--worktrees` lists them with reasons; A.7 mails their owners; cross-repo deletion stays refused |
| I9 | the pool module's fanout scratch leak | OUT-OF-SCOPE | fabrik-lib's module (D-137); filed `01M1YRSN7F0GYVTBK7D40GW1P5` |
| I10 | the 46 root-level unowned entries under `/tmp/claude-1000` (2.3 GB, e.g. `payments-c4`, `snap`, `c136copy` — plus LIVE system state `mcp-health-cache`, `bundled-skills`, `e2e-quota`, `*.hb`) | IN (listed, never auto-removed) | Phase A.4: `--unowned-older-than <days>` explicit flag, protected names hard-coded |

Intake: 10 items — 9 IN, 1 OUT-OF-SCOPE (I9, filed), 0 ASK.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED: the three `.py` surfaces) | typing (`list[str]`, `str \| None`), `datetime.now(UTC)`, stdout-only output, `.tmp` is disposable by contract | `:159-161`, `:219`, `:290-291`, `:150-153` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED: `tests/test_scratch_sweep.py`) | one test per behaviour, watched-fail-first, runner `uv run pytest` (the hub has `pyproject.toml` + `uv.lock`) | `:19-21`, `:47-49` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED: both `CLAUDE.md`) | DECISIONS row same change, CHANGELOG + INDEX, new-`.md` default-deny (only the plan + receipt are allowlisted) | `:23`, `:66`, `:183-197` |
| FLOOR packs (`35-security-auth`, `25-data-postgres`, `30-ops`, 12-Factor) | config via env vars with defaults (the test seams), no secrets, no docker mutation | `review_rubric.py` FLOOR block |
| `fabrik-lib` consult | the closest prior art is the pool module's `workspace.py::sweep_stale_worktrees` (`libs/subagents/workspace.py:176-236`: owner-sidecar + mtime + `worktree remove` → `rmtree` fallback). NOT vendored: it force-removes and rmtrees on refusal — the opposite of constraint 1 — and it targets `<repo>/.tmp/subagents/agent-*`, not session scratch. Its two sound ideas are kept: a liveness check before any removal, and `git worktree prune` for gone registrations. Fresh build, `🆕 fabrik-lib candidate: no` (box-local tooling, one consumer) | `fabrik-lib/README.md:65` (module RETIRED, D-132) |
| `agents-fabrik.md` § Planning Constraints | solo dev; no new top-level dirs; state conflicts surfaced not silently overwritten | `agents-fabrik.md:362-375` |
| `docs/workstation/cleanup-automation.md` | *this page is where a new cleanup rule gets written*; § D's DO-NOT-SWEEP list binds | `:9-10`, `:78-111` |
| `docs/workstation/hooks-index.md` | every user-level hook has a row; `install_user_hooks.py` is the only writer of the user-level registrations | `:102-104` |
| `CLAUDE.md` HARD STOPS | never offer docker volume deletion; never files outside the project tree except the sanctioned stores; a synced-surface edit is a fleet-wide change | HARD STOPS table |
| `scripts/command_run.py` (synced, `fabrik_synced_manifest.py:56`) | the close path `_close` (`:1679`), the persisted-then-print order (`:2129-2158`) | read this run |

## CONSTRAINTS DIGEST

| # | Pack `file:line` | Verbatim quote | Binds here |
|---|---|---|---|
| C1 | `10-python.md:150-151` | "`.tmp` contents are DISPOSABLE by contract" | a session scratchpad is temp by the same contract; the `.keep` list is the ONLY exception path, and it is the agent's explicit act |
| C2 | `10-python.md:160` | "Use `list[str]` not `List[str]`; use `str \| None` not `Optional[str]`" | the script's signatures |
| C3 | `10-python.md:219` | "`datetime.now(UTC)`, never `datetime.utcnow()`" | age arithmetic uses epoch seconds + `datetime.now(UTC)` for display only |
| C4 | `10-python.md:290` | "Structured JSON, **unbuffered**, to `stdout` — and nothing else" | the script writes its table to stdout and nothing to a logfile; the cron line's redirect is the platform's job |
| C5 | `45-testing-strategy.md:21` | "a non-trivial behavior's test proves something only if it has been SEEN RED" | every Behavior row below is seen red first |
| C6 | `45-testing-strategy.md:47` | "**Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`)" | the hub has `pyproject.toml` + `uv.lock`; gates below use `uv run pytest` |
| C7 | `40-documentation.md:23` | "`docs/DECISIONS.md` (the decision ledger — a decision made or received gets its row in the SAME change" | D-184 is minted in this plan's commit |
| C8 | `40-documentation.md:185` | "**Rule:** Edit existing docs instead of creating new ones." | the janitor is documented as § F of `cleanup-automation.md`, never a new page |
| C9 | `CLAUDE.md` HARD STOPS | "propose/offer ANY docker volume deletion … Volumes are DATA" | the script never invokes docker; the refusal set says so |
| C10 | `cleanup-automation.md:107-108` | "a future rule globbing `.tmp/**` or `*.jsonl` would take `pg_outbox.jsonl` with it" | the script's roots are `/tmp/claude-<uid>` and `git worktree list` paths ONLY — never `<repo>/.tmp` |
| C11 | `35-security-auth.md` (FLOOR) | "config via env vars only (`os.getenv("KEY","default")`)" | the test seams (`SCRATCH_SWEEP_ROOT`, `SCRATCH_SWEEP_SESSIONS_DIRS`, `FABRIK_PROC_ROOT`, `CLAUDE_SOUND_LOCKDIR`, `SCRATCH_SWEEP_NOW`, `FABRIK_SCRATCH_SWEEP`) are env vars with the real defaults |

Selections below cite a row or say `unconstrained`.

## Global Constraints

- **Refusal set (C1, C9, C10 — hard-coded, printed by `--help` and by every apply run):** the script never touches `/opt/<repo>` tracked or untracked files (except a `git worktree remove` of a worktree IT classified removable), `~/.claude*/projects` transcripts, `~/.claude*/state`, `<repo>/.tmp/**`, docker anything, another LIVE session's scratch, the caller's own `tasks/` dir, or a root-level entry of `/tmp/claude-<uid>` without `--unowned-older-than`. Held, kept, fresh, dirty, unmerged, locked and unclassifiable entries are LISTED with the reason and never removed.
- **Dry-run is the default; `--apply` is opt-in; every apply line prints `REMOVED <path> (<class>, <reason>)`.** Fail direction: any probe error on an entry ⇒ that entry is KEEP `probe-error` (never a candidate); the script exits 0 on its own errors in `--hook` mode (a hook must never block a prompt — the `selfwatch_check.py` contract) and non-zero only on a refusal (rc 2) or a bad invocation.
- **Never `--force` on a worktree removal, never `git branch -D`** — git's own refusals (a dirty tree → `worktree remove` rc 128; an unmerged branch → `branch -d` refuses) are the second guard behind the classifier (Evidence Phase A).
- **Scratch root:** `SCRATCH_SWEEP_ROOT` default `/tmp/claude-<uid>`; the session dir is `<root>/<slug(cwd)>/<sid>/` with `slug = cwd.replace("/", "-")` (`/opt/fabrik` → `-opt-fabrik`; the harness's own layout, `scratchpad/` + `tasks/`); the sid is `--session`, else `CLAUDE_SESSION_ID`, else `CLAUDE_CODE_SESSION_ID` (`scripts/command_run.py:91-108` — the Bash-tool shell carries the second, not the first); the cwd is `--cwd`, else the sessions file's `cwd` for that sid, else `os.getcwd()`.
- **Age threshold:** `--older-than` default `6h` (entries newer are `fresh` — a running review's copies survive); the janitor's transcript-idle threshold is 24 h; the unowned flag takes days. `SCRATCH_SWEEP_NOW` (epoch) is the test clock.
- **Cost:** `--hook` mode does a top-level `os.scandir` + mtimes only (no holder probe, no `du`) with a 1 s budget; `du -sk` runs only on candidates in dry-run/apply with a 10 s total budget (size `?` past it — a size is a courtesy, a class is the contract).
- **12-Factor non-negotiables (inherited, one line each):** logs = stdout only, never a logfile (XI) · no daemonizing / PID files (VIII) · config = granular env vars (III) · no docker/compose/`ports:` involvement (VII) · migrations, sticky sessions, backing services: not applicable (a box-local CLI, no service) — stated so no phase can quietly violate one.
- **Shared tree:** explicit pathspecs one per line with `--numstat` read in the same invocation; `CHANGELOG.md`/`DECISIONS.md` hot — hunk guard; siblings dirty in `libs/subagents/`, `INDEX.md`, `PORTS.md`, kaizen logs, plan-2 files — never staged (INDEX rows land by private-index plumbing). Synced surfaces touched (`scripts/command_run.py`, both `CLAUDE.md`) distribute fleet-wide on commit — correct for all ~46 repos because the close-out trigger is fail-open on a missing hub path and the § EXIT sentence uses the absolute hub path.
- **Pool OFF (D-181/D-182):** every reader seat is native; nothing records.

## Phases

### Phase A — the script: `scripts/scratch_sweep.py` + its graders + the owners' mail

**Interfaces — Produces:** `scripts/scratch_sweep.py` (hub-only; `# AFTER-EDIT: docs/workstation/cleanup-automation.md | docs/workstation/hooks-index.md | tests/test_scratch_sweep.py`): CLI `[--session SID] [--cwd DIR] [--older-than 6h] [--apply] [--worktrees [REPO]] [--dead] [--unowned-older-than DAYS] [--hook] [--brief] [--json]`; functions `classify_session(root, sid, cwd, now, older_than_s) -> list[Row]`, `classify_worktrees(repo, now) -> list[Row]`, `dead_sessions(root, sessions_dirs, lock_dir, proc_root, now) -> list[Row]`, `apply(rows) -> int`, `render(rows, brief=False) -> str`; `Row = (path, kind, cls, reason, evidence, size_kb | None)` with `cls ∈ {stale, fresh, held, kept, unclassified, probe-error, wt-removable, wt-dirty, wt-unmerged, wt-locked, wt-held, wt-prunable, dead, live, unowned, protected}`; only `stale`, `wt-removable`, `wt-prunable`, `dead` and (under the explicit flag) `unowned` are ever removed. Exit codes: 0 · 2 refusal · 1 bad invocation. Env seams per C11.

1. **Highest-risk test first (C5):** write `tests/test_scratch_sweep.py::test_dry_run_deletes_nothing_and_names_every_class` — a fixture scratchpad under `tmp_path` with a stale dir (mtime now−7h), a fresh dir (now−1h), a `.keep`-listed dir (stale by age), a dir held by a live process (the test opens an fd inside it — the same trick `tests/test_selfwatch_check.py::_hold_lock` uses), and `tasks/` beside it; run the script with `SCRATCH_SWEEP_ROOT=<tmp>`, `SCRATCH_SWEEP_NOW` fixed, `FABRIK_PROC_ROOT=/proc`; assert the table carries exactly `stale / fresh / kept / held` for the four, `tasks/` absent, and a byte hash of the tree before == after. Run → RED (module missing).
2. Implement session mode: derive sid/cwd/root (Global Constraints); `os.scandir(scratchpad)`; per entry, in order: `.keep` list (`scratchpad/.keep`, one relative name per line) or an entry-internal `.keep` file → `kept`; holder probe — walk `<proc_root>/<pid>/cwd` and `/fd/*` readlinks for a prefix match on the entry → `held` (`pid <n> <comm>`); `st_mtime` newer than threshold → `fresh`; a probe `OSError` → `probe-error`; else `stale` (candidate). Render a table `path · size · class · reason · evidence`, then the one-line `apply:` command when candidates exist. Run step 1 → GREEN.
3. Graders `test_apply_removes_only_stale` (the same fixture, `--apply`: the stale dir gone, the other three present, `REMOVED` line printed) and `test_apply_on_another_live_sid_is_refused` (a second sid whose sessions file names a live pid — the test writes `<sessions_dir>/<pid>.json` with its OWN pid + procStart from `/proc/self/stat`; `--session <that sid> --apply` → rc 2, nothing removed; the same without `--apply` → the table prints). Seen red → green.
4. `--dead` (janitor) + `--unowned-older-than`: grader `test_janitor_removes_only_dead_sids` — fixture root with `<slug>/<live-sid>/` (sessions file with the test's own pid + procStart) and `<slug>/<dead-sid>/` (no file, no lock, transcript absent), plus root-level `payments-c4/` (unowned, 10 d) and `mcp-health-cache/` (protected): `--dead` lists live as `live` and dead as `dead`, unowned as `unowned (needs --unowned-older-than)`, protected as `protected`; `--dead --apply` removes ONLY the dead dir; `--dead --unowned-older-than 7 --apply` removes `payments-c4` too, never `mcp-health-cache`. A held `<sid>.selfwatch.lock` (`CLAUDE_SOUND_LOCKDIR`) keeps a sid `live` even with no sessions file (grader `test_a_held_selfwatch_lock_is_liveness`). Seen red → green.
5. `--worktrees`: grader `test_worktree_classifier_three_verdicts` builds the fixture of this run's Evidence (a repo with a merged+clean, a never-merged and a dirty worktree, plus a squash-merged one whose merge commit carries `Merged-From: <branch>`): dry-run classes `wt-removable / wt-unmerged (ahead N) / wt-dirty (<paths>) / wt-removable`; `--apply` removes only the two removable, deletes their branches with `git branch -d`, prints the refusals verbatim for the rest; a `locked` entry (`git worktree lock`) is `wt-locked` with the unlock command as its reason; a registration whose path is gone is `wt-prunable` and `--apply` runs `git worktree prune`. Main checkout detection: `git worktree list --porcelain` line 1; the merge target is that checkout's current branch (the hub: `master`; fixtures: `main`). Seen red → green.
6. `--hook` mode (consumed in Phase B): payload on stdin (`session_id`, `cwd`, `hook_event_name`); gates identical to `selfwatch_check.py:92-101` (real sid · not `CLAUDE_MESH_HEADLESS=1` · not `CLAUDE_MESH_AUTONOMOUS=1` · an `/opt` cwd); prints ONE line `## 🧹 SCRATCH: <n> stale entries (<size or ?>, oldest <age>) in this session's scratchpad — dry-run: python3 /opt/fabrik/scripts/scratch_sweep.py · apply: … --apply · never touches: …` only when `n ≥ 1`; silent otherwise; exit 0 on every path (a stderr line on an exception, never silence — the B4 shape). Grader `test_hook_line_fires_only_with_candidates_and_never_blocks`. Seen red → green.
7. **The owners' mail — the first act after the script lands (the operator asked for the mail as a first act; a mail naming a script that does not exist yet would be wrong, so it follows A's commit by minutes):** (a) `python scripts/mail.py send --broadcast --ack no --kind finding` — D-035 body: WHAT (the script, its three modes, the refusal set, the dry-run default, the exact commands), WHEN (now; the close-out and per-prompt line arrive with Phase B), WHO (every repo's agents own their scratch; cross-repo deletion stays refused hub-side), WHY (87 GB of review copies across four hub sessions on 2026-09-07; 1,580 session dirs on the box, 9 live), HOW (dry-run → read → apply; `--worktrees` for agent worktrees), SYSTEMIC (no rule existed; the § EXIT sentence lands in Phase C); (b) four addressed mails — seo (28 worktrees, all merged; 2 with real uncommitted edits), trade-intelligence (24: 11 merged, 13 never-merged with 1-6 commits), web-ecommerce-factory (18: 10 merged, 8 never-merged; 3 with real uncommitted work), fabrik-lib (`feat/account-module` ×2, 57 d, dirty + unmerged) — each with its own dry-run command and the rule that never-merged/dirty stay theirs to merge or discard; (c) a native `SendMessage` to the live hub peers (`ListAgents` first) with the hub's own command. Record the mail ids in `## Evidence`.
8. Phase gate: `uv run pytest tests/test_scratch_sweep.py -q` → expected `N passed` (N = the graders above, ≥ 8); `uv run ruff check scripts/scratch_sweep.py tests/test_scratch_sweep.py` → clean; `python3 scripts/scratch_sweep.py --help` prints the refusal set (grader `test_help_names_the_refusal_set`); a live dry-run on THIS session's scratchpad (`python3 scripts/scratch_sweep.py`) → a table, nothing removed (`du -sk` before == after).
9. `python scripts/enforcement/check_doc_sync.py` + `python scripts/enforcement/check_script_headers.py` (the `# AFTER-EDIT:` header is a real comment in the first 25 lines — never inside the docstring).
10. `/fabrik-review-scoped` on Phase A's diff to a raised-zero no-op (Profile: small — the light round; classes: fail-open/closed on every probe, boundary (a sid with `/` or `..`, a symlinked entry — `os.scandir` + `readlink` on the entry itself: a symlink is `unclassified`, never followed), cost, behaviour-without-a-test).
11. Commit `scripts/scratch_sweep.py` + `tests/test_scratch_sweep.py` (explicit pathspecs, `Agent-Role: primary`, `Agent-Name: fleet`, `Agent-Phase: A`); `git reset -q HEAD -- <paths>`; push; then A.7.

### Phase B — the three triggers: close-out, per-prompt + SessionStart line, the janitor's cron line

**Interfaces — Consumes:** Phase A's `--brief` (the table + apply command, empty output on 0 candidates) and `--hook`. **Produces:** `scripts/command_run.py::_scratch_advisory(sid, repo_root) -> str` (fail-open shell-out, 5 s timeout, gated by `FABRIK_SCRATCH_SWEEP != "0"` and the hub path existing); `scripts/sysadmin/install_user_hooks.py::ENTRIES` gains `UserPromptSubmit` + `SessionStart` entries `python3 /opt/fabrik/scripts/scratch_sweep.py --hook`; a cron line for the operator.

1. **Highest-risk test first:** `tests/test_command_run.py::test_a_top_level_close_prints_the_scratch_table_and_a_nested_close_does_not` — `_cr("start", …)` then `done` with `FABRIK_SCRATCH_SWEEP_SCRIPT=<a stub that prints "STUB TABLE">` (a second seam so the test never runs the real sweep) → stdout carries `STUB TABLE` AFTER the `FEEDBACK:` line and BEFORE `run record closed`; a nested run (`start` inside `start`, `done` the inner) prints no table; `FABRIK_SCRATCH_SWEEP=0` → no table; a missing script path → no table, no stderr noise beyond one line. Run → RED.
2. Implement in `_close` (`scripts/command_run.py:2154-2158`): after the record persisted and the ledger row appended, `if parent is None and args.cmd in ("done", "blocked", "handoff"):` print `_scratch_advisory(sid, rec.get("repo_root"))`; the helper runs `[sys.executable, script, "--session", sid, "--cwd", repo_root, "--brief"]` with `timeout=5`, returns `""` on any exception (one stderr line). Docstring: why the print is after persistence (a close that did not happen prints no advice) and why never auto-apply (constraint 2). → GREEN.
3. `install_user_hooks.py`: add the two entries to `ENTRIES` (`:29-37`); grader in `tests/test_install_user_hooks.py`: a fresh settings file gains both entries with `timeout: 10`, and `--check` names a file lacking one. Seen red → green. Then `python3 scripts/sysadmin/install_user_hooks.py` (installs into the canonical `~/.claude/settings.json` and every account dir) → `--check` exit 0; `bash scripts/dr_claude_backup.sh` (the user settings are DR-mirrored, `scripts/dr_claude_backup.sh:89`; memory: run it after any Claude-config change). The hook fires in every window on the NEXT prompt — no reload needed (user-level hooks are read per event).
4. Fire-rate measurement BEFORE the row is written (FIX DIRECTIVE 5): run `--hook` against the 9 live sessions' payloads (`sid` + `cwd` from the sessions files) and record how many print a line and what they say; record the median wall time (budget: < 200 ms). A line that fires on a session with only fresh entries is a defect to fix here, not a threshold to tune later.
5. The janitor's cron line — handed to the operator in the handoff (crontab writes are classifier-blocked, memory `project_crontab_wipe_2026_08_19`): `20 4 * * * flock -n $HOME/.claude/state/scratch-sweep.lock python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply >> $HOME/.claude/scratch-sweep.log 2>&1`. Before handing it over, run `python3 scripts/scratch_sweep.py --dead` (dry-run) on the live box and paste the summary (`dead N · live 9 · unowned 46 · protected 3`) into Evidence — the first unattended run's log is the proof, read it the next day (memory `feedback_first_unattended_run_is_the_proof`).
6. Docs (Doc Sync Matrix floor + the box-local rows): `docs/workstation/hooks-index.md` — a new row after `:102` for the user-level `scratch_sweep.py --hook` (both events, gates, fail-open, tests) and the installer row `:104` "three" → the new count; `docs/workstation/cleanup-automation.md` — the table at `:12-17` gains the janitor row and a new **§ F — Session scratch and agent worktrees (`scratch_sweep.py`)** stating the three modes, the refusal set, the § D relation (never `<repo>/.tmp`), and the cron line; `docs/workstation/claude-configuration-inventory.md:132-136` — extend the user-level hook enumeration if it lists entries by name; `docs/workstation/wsl-startup-inventory.md` — only if it inventories cron lines (grep first).
7. Phase gate: `uv run pytest tests/test_command_run.py tests/test_install_user_hooks.py tests/test_scratch_sweep.py -q` → all green; `python3 scripts/sysadmin/install_user_hooks.py --check` → exit 0; `python scripts/enforcement/check_hooks_index.py` (every registered user-level hook has its row) → exit 0.
8. `python scripts/enforcement/check_doc_sync.py` + the doc steps above.
9. `/fabrik-review-scoped` on Phase B's diff to a raised-zero no-op (classes: the close-out print never changes a close's exit code or ledger row; the hook's 1 s budget; a payload with a non-dict body; the synced `command_run.py` in a repo where `/opt/fabrik` is absent → silent).
10. Commit (`scripts/command_run.py`, `scripts/sysadmin/install_user_hooks.py`, the three test files, the three docs — explicit pathspecs, `Agent-Phase: B`); realign; push.

### Phase C — the contract, the pointers, the ledger, the Finish

**Interfaces — Consumes:** Phase A's script path and refusal set (quoted verbatim in the § EXIT sentence). **Produces:** the § EXIT sentence in `CLAUDE.md:215` and `templates/governance/CLAUDE.md:187`; the universal marker bullet `clean-own-scratch` (anchor **CLEAN your own scratch**) in `CLAUDE.md` § UNIVERSAL governance markers; pointer clauses in `docs/reference/multi-agent-operating-model.md:126-127` and `commands/_sources/fabrik-execute-plan.md:1153`; the CHANGELOG entry; D-184's row (minted with this plan — Phase C verifies it stands).

1. Both `CLAUDE.md` § EXIT (READ BEFORE YOU EDIT — the subject lives inside item 5, after the push clause, never a new section): one sentence — "**Then CLEAN your own scratch** — `python3 /opt/fabrik/scripts/scratch_sweep.py` (dry-run: every stale entry in THIS session's scratchpad with size · class · reason; nothing is deleted), read the table, then `--apply`; `--worktrees` for agent worktrees you opened (removes only merged + clean + unlocked + unheld; never-merged, dirty and locked stay listed with the reason). It never touches `/opt/<repo>` files, transcripts, `~/.claude/state`, `<repo>/.tmp`, docker, another live session's scratch, or `tasks/`. The run-record close prints the table for you; the per-prompt line nags until clean; a DEAD session's scratch is swept by the daily janitor — an interrupted run heals on its next prompt, never by a sibling's hand." Same text in both files (the template's sentence names the absolute hub path — correct for every repo, fabrik-lib included, exactly as `claude_rotate.py --status` is cited).
2. The universal marker bullet: `- \`clean-own-scratch\` — anchor **CLEAN your own scratch** — a session's scratch is disposable by contract and nobody else may delete it blindly, so the owner sweeps it at task end and the janitor takes only DEAD sessions (operator directive 2026-09-08)`. fabrik-lib's `check_governance_drift.py` parses this list, so their next gate run warns them into adding the sentence — say so in A.7's fabrik-lib mail.
3. Pointers, not restatements: `docs/reference/multi-agent-operating-model.md:126-127` gains "(or `python3 /opt/fabrik/scripts/scratch_sweep.py --worktrees` — lists merged/dirty/unmerged/locked with reasons; `--apply` removes only the merged + clean)"; `commands/_sources/fabrik-execute-plan.md:1153` gains the same parenthetical after `git worktree prune`. Command source edited ⇒ render from the main master checkout: `python commands/assemble_commands.py` → `--check` → commit (the `command-corpus-check` pre-commit hook refuses sources ahead of the corpus — the order is render → `--check` → commit).
4. `CHANGELOG.md`: `### Added — agents sweep their own session scratch and agent worktrees; nothing is deleted blindly (2026-09-08)` atop `[Unreleased]` (hunk guard: expected numstat = this entry only).
5. `docs/DECISIONS.md`: verify D-184 (minted with this plan's commit) still reads true after Phases A-B; a changed shape is a NEW row superseding it, never an edit.
6. INDEX rows for `scripts/scratch_sweep.py`, `tests/test_scratch_sweep.py`, the plan, the lock and the receipt — `INDEX.md` is a sibling's dirty file: private-index plumbing (HEAD+mine blob), never a working-tree stage.
7. Whole-plan receipts: `python scripts/enforcement/check_doc_sync.py --range acffe9c1..HEAD` + `python scripts/enforcement/check_doc_stubs.py --range acffe9c1..HEAD`; `python scripts/final_gate.py --check --json` → `"status":"success"` (read `skipped_checks`); `python scripts/enforcement/check_convergence.py` → exit 0. A green gate is necessary, not sufficient — the Evidence is the proof.
8. `/fabrik-docs-review` over the docs this plan touched (both `CLAUDE.md`, hooks-index, cleanup-automation, the operating model, the rendered command) — every claim resolves to shipped `path:line`.
9. **The ONE heavy `/fabrik-review` over the whole-plan diff** (`acffe9c1..HEAD`; three native seats, ≥1 Opus; receipt `docs/development/reviews/2026-09-08-plan-1-scratch-sweep-review.md` via `review_receipt.py --init`, check-before-create) to a coverage-adjudicated no-op; fix in-run.
10. Status → `EXECUTED` with the Completion stamp; archive the plan per the executor's Finish; commit (explicit pathspecs, `Agent-Phase: C`); realign; push. Handoff line: the cron line (B.5) for the operator to place, and the mail ids.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor:** every phase runs `/fabrik-review-scoped` on its own diff to a raised-zero no-op BEFORE its commit; the whole-plan diff gets ONE full `/fabrik-review` at Finish (C.9). No phase commits on a first-pass green.
- **Dispatch policy:** Profile: small — the orchestrator codes each phase INLINE in the main checkout (D-169/D-170); every reader seat is NATIVE (pool OFF, D-181/D-182): the Finish review's three seats are ≥1 Opus authoritative + up to two Sonnet breadth seats briefed on disjoint classes (fail-open/closed + boundary · cost + behaviour-without-a-test); the plan-review's grounders are native `fabrik-researcher`/general-purpose seats on a PINNED copy (md5 in the brief).
- **Parallelism + merge:** Phases are sequential by data dependency (B consumes A's `--brief`/`--hook`; C quotes A's refusal set). Inside A, the graders for session/dead/worktree modes are independent and may be authored in parallel by native seats; the orchestrator merges + refutes. The Finish seats fan out in parallel; findings merge in the receipt with one verdict each.

## Behavior Contract

- **Given** a scratchpad with a stale, a fresh, a `.keep`-listed and a process-held entry (plus `tasks/`), **When** the script runs without `--apply`, **Then** the table names the four as `stale / fresh / kept / held` with reasons, `tasks/` is absent, and the tree is byte-identical afterwards (`scripts/scratch_sweep.py`, `tests/test_scratch_sweep.py`).
- **Given** the same scratchpad, **When** `--apply` runs, **Then** only the stale entry is removed, a `REMOVED <path> (stale, …)` line is printed, and the other three survive.
- **Given** a sid whose sessions file names a live `pid` + `procStart`, **When** `--session <that sid> --apply` runs from another session, **Then** rc 2 with the refusal reason and nothing removed; the dry-run of the same sid prints its table.
- **Given** `--dead`, **When** a sid has a live sessions file OR a held `selfwatch.lock` OR a process under its dir, **Then** it is `live`; a sid with none of the three and a transcript older than 24 h (or absent) is `dead`, and `--apply` removes its whole `<slug>/<sid>/` dir; root-level entries are `unowned` (never removed without `--unowned-older-than`) or `protected` (never removed).
- **Given** a repo with a merged-clean, a squash-merged (`Merged-From` trailer), a never-merged, a dirty and a locked worktree plus a gone registration, **When** `--worktrees` runs, **Then** the classes are `wt-removable / wt-removable / wt-unmerged (ahead N) / wt-dirty (<paths>) / wt-locked / wt-prunable`; `--apply` removes only the two removable (`git worktree remove`, then `git branch -d`) and prunes the gone one; never `--force`, never `-D`.
- **Given** a top-level run-record close (`done`/`blocked`/`handoff`), **When** the record has persisted, **Then** the sweep's `--brief` table prints after the `FEEDBACK:` line when candidates exist and nothing when there are none; a nested close, `FABRIK_SCRATCH_SWEEP=0`, or a missing hub script prints nothing and never changes the close's exit code or ledger row (`scripts/command_run.py:2154-2158`).
- **Given** a `UserPromptSubmit` or `SessionStart` payload for an `/opt` session, **When** its scratchpad holds ≥1 stale entry, **Then** exactly one `## 🧹 SCRATCH:` line naming the count, the dry-run and the apply commands prints; with none, headless, autonomous, or a non-`/opt` cwd it prints nothing; exit 0 on every path.
- **Given** `install_user_hooks.py` runs, **When** `--check` runs afterwards, **Then** both `scratch_sweep.py --hook` entries (`UserPromptSubmit`, `SessionStart`, `timeout: 10`) exist in the canonical settings and every account dir (`scripts/sysadmin/install_user_hooks.py:29-38`).
- **Given** `--help`, **When** it prints, **Then** the refusal set (Global Constraints) appears verbatim, so an agent reading the help knows what the script never touches.

## File Scope (owned paths)

- scripts/scratch_sweep.py
- tests/test_scratch_sweep.py
- scripts/command_run.py
- tests/test_command_run.py
- scripts/sysadmin/install_user_hooks.py
- tests/test_install_user_hooks.py
- CLAUDE.md
- templates/governance/CLAUDE.md
- docs/workstation/hooks-index.md
- docs/workstation/cleanup-automation.md
- docs/workstation/claude-configuration-inventory.md
- docs/workstation/wsl-startup-inventory.md
- docs/reference/multi-agent-operating-model.md
- commands/_sources/fabrik-execute-plan.md
- docs/development/reviews/2026-09-08-plan-1-scratch-sweep-review.md

(`INDEX.md`, `CHANGELOG.md`, `docs/DECISIONS.md` are governance files — orchestrator-applied shared-append surfaces outside the plan lock. Outside the repo, owned by this plan's execution: the user-level settings files written by `install_user_hooks.py` and mirrored by `dr_claude_backup.sh`; the cron line is the operator's.)

## Coverage Checklist

```text
$ python scripts/review_rubric.py --changed scripts/scratch_sweep.py scripts/command_run.py scripts/sysadmin/selfwatch_check.py .claude/hooks/session_orient.py CLAUDE.md templates/governance/CLAUDE.md tests/test_scratch_sweep.py
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md · ### core/25-data-postgres.md · ### core/30-ops.md · ### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: .claude/hooks/session_orient.py, scripts/command_run.py, scripts/scratch_sweep.py)
### core/40-documentation.md  (hit: CLAUDE.md, templates/governance/CLAUDE.md)
### core/45-testing-strategy.md  (hit: tests/test_scratch_sweep.py)
```

| Class / pack | Verdict | Disposition |
|---|---|---|
| `core/10-python.md` | UNCHECKED | |
| `core/40-documentation.md` | UNCHECKED | |
| `core/45-testing-strategy.md` | UNCHECKED | |
| FLOOR (`35-security-auth` · `25-data-postgres` · `30-ops` · 12-Factor) | UNCHECKED | |
| fail-open vs fail-closed on every gate/guard | UNCHECKED | |
| cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | UNCHECKED | |
| boundary/sentinel/prefix collisions | UNCHECKED | |
| behavior-without-a-test | UNCHECKED | |

(Filled by `/fabrik-plan-review`'s convergence round; every row CLEAN/FIXED/REFUTED before the CONVERGED flip.)

## Pass Ledger

| Pass | axes re-checked (claims · gates · interfaces · completeness) | method | raised | new: | edits made | plan md5 (start → end) |
|-----:|---|---|---:|---:|---:|---|

## Evidence

### Phase A

- The harness's scratch layout and the liveness key, measured 2026-09-08 (the scratch root `/tmp/claude-1000`, session dirs `<slug>/<sid>/{scratchpad,tasks}`; `~/.claude-fleet/can/sessions/<pid>.json` carrying `pid`/`sessionId`/`cwd`/`procStart`; `CLAUDE_CONFIG_DIR=/home/ozgur/.claude-fleet/active`):

```text
$ python3 - (sessions files across ~/.claude/sessions + ~/.claude-fleet/*/sessions, pid + procStart validated against /proc/<pid>/stat)
/home/ozgur/.claude-fleet/can/sessions live 9 dead 69 pid-recycled 0
/home/ozgur/.claude-fleet/mob/sessions live 0 dead 56 · ob 0/74 · ozgurbasak 0/3 · sarp 0/94 · ~/.claude/sessions 0/315
session dirs 1580: live 9 (4726 MB) · dead 1571 (952 MB)
root-level unowned entries 46 (2363 MB)
$ pgrep -x claude | wc -l
9
```

- The holder probe's real signal on this session's scratchpad (`/proc/<pid>/cwd` + `/fd/*` readlinks): `holders [('3129173','fd'), …] n 3` — the session's own harness holds fds under `tasks/`, which is why `tasks/` is excluded and the probe is per ENTRY, never per session dir.
- git's own refusals are the second guard (fixture under this session's scratchpad, 2026-09-08):

```text
$ git worktree remove ../wt-dirty
fatal: '../wt-dirty' contains modified or untracked files, use --force to delete it   (rc=128)
$ git branch -d unmerged
error: cannot delete branch 'unmerged' used by worktree at '…/wt-unmerged'
$ git worktree remove ../wt-merged && git branch -d merged && echo OK
Deleted branch merged (was 5701668).
OK
$ git commit --allow-empty -m "$(printf 'squash\n\nMerged-From: unmerged\n')" && git log --format='%(trailers:key=Merged-From,valueonly)' -1
unmerged
$ git merge-base --is-ancestor dirty main → y   (an ancestor branch with a dirty tree is still KEEP: the dirty rule wins)
```

- Prior art read, not vendored: `libs/subagents/workspace.py:176-236` (`sweep_stale_worktrees`: `worktree remove --force` then `rmtree` fallback — refused by constraint 1); `scripts/sysadmin/selfwatch_check.py:65-87` (`_armed`, the lock probe reused as liveness signal 2); `~/.local/bin/cache-prune.sh:1-3` ("never ~/.local, never source/data" — the same principle, size-capped caches only; it never touches `/tmp/claude-*`).
- The hub's own agent worktrees today (`git worktree list --porcelain`, 2026-09-08): 8 entries, every one `merged=n ahead=1-4 dirty=1-3 locked=False` — the classifier yields 0 removable here; the dirty paths are gate outputs (`duplicate-report.json`, `jscpd-report.json`, `.venv`), which is why `wt-dirty` lists its paths for the owner to judge.

### Phase B

- `scripts/command_run.py:1679` `_close`; the persisted-then-print order `:2129` (`fields["persisted"] = save(...)`), `:2154-2158` (the nested-resume print, then `run record closed`); the sid chain `:91-108`; the ledger row `:2095-2120`.
- `scripts/sysadmin/install_user_hooks.py:29-38` (`ENTRIES`, `TIMEOUT_S = 10`), `:41-58` (`_targets`: canonical + every account dir), `:61-69` (`_stale` iterates `ENTRIES.items()` — a new event key needs no loop change).
- The user-level registrations today (`~/.claude/settings.json` → `hooks.UserPromptSubmit`): `selfwatch_check.py` and `user_hook_gate.py mcp_watch.py`, both `timeout: 10`.

```text
$ python scripts/select_rules.py | head -3
Project type: (unknown)
ACTIVE — read these in full now (26):
$ python scripts/review_rubric.py --changed … | grep '^## \|^### ' | tail -4
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: .claude/hooks/session_orient.py, scripts/command_run.py, scripts/scratch_sweep.py)
### core/40-documentation.md  (hit: CLAUDE.md, templates/governance/CLAUDE.md)
### core/45-testing-strategy.md  (hit: tests/test_scratch_sweep.py)
```

### Phase C

- `CLAUDE.md:215` and `templates/governance/CLAUDE.md:187` — item 5 **EXIT**, identical text in both (grep `^5\. \*\*EXIT\*\*`); no `scratch`/`worktree` cleanup sentence exists in either today (`grep -n -i 'scratch\|worktree' CLAUDE.md templates/governance/CLAUDE.md` → 6 hits, none a cleanup rule).
- `docs/reference/multi-agent-operating-model.md:124-129` (§ Retirement: `ExitWorktree` … `remove`, then `git worktree prune`; "A dead session leaves its worktree locked"); `commands/_sources/fabrik-execute-plan.md:1153` (`git worktree remove <path>` + `git worktree prune`).
- `docs/workstation/cleanup-automation.md:9-10` ("this page is where a new cleanup rule gets written"), `:12-17` (the pieces table), `:78-111` (§ D DO-NOT-SWEEP).

```text
$ grep -n -i 'scratch\|worktree' scripts/command_run.py .claude/hooks/final_gate_stop.py scripts/sysadmin/selfwatch_check.py | grep -v 'git worktree list' | wc -l
3        (all three in final_gate_stop.py's docstring — "worktree is dirty"; no cleanup rule)
$ python3 scripts/decisions.py --next-id .
D-184
```

## Self-audit

- **Grounding passes run:** the close path (`command_run.py` `_close` head + tail), `selfwatch_check.py` whole, `session_orient.py:262-395`, `install_user_hooks.py:1-70`, `claude-reboot-sweep.sh` headers, `workspace.py:160-236`, `check_plan_lock_release.py` statuses, both `CLAUDE.md` EXIT lines, the three MATCHED packs in full, `cleanup-automation.md` whole, the live box (sessions files, scratch roots, holders, hub worktrees), the git fixture.
- **(a) Coverage of "What we already agreed":** own-scratch at done → A + B.1-2; interruptions → B.3-4 (the hook fires at the next prompt and at SessionStart, which is the compaction/resume path) + B.5 (dead sessions); future usage → C.1-2; existing residue → A.7 + the hook + the janitor; no data loss → A's classes + refusal set + git's refusals; self-describing → A.6/A.8 help + B.2 close print + C.1.
- **(b) Cross-phase signatures:** A produces `--brief`, `--hook`, `--dead`, `--worktrees`, `--unowned-older-than`, the env seams; B consumes `--brief` (close-out) and `--hook` (installer entries) by those exact spellings; C quotes A's refusal set verbatim. The sid chain in the script mirrors `command_run.py:91-108` (`CLAUDE_SESSION_ID` then `CLAUDE_CODE_SESSION_ID`).
- **Settled design questions (from the dispatch):** keep-list = a `.keep` file (survives interruption; a run-record field dies with a `nosession` record); age threshold 6 h (a review round's copies are hours old at most); the plan-lock condition on worktrees is DROPPED (locks do not name worktrees — merged + clean + unlocked + unheld is the real safety, and git refuses the rest); auto-apply at close is REJECTED (constraint 2); the janitor keeps nothing of a dead session (its transcript is the durable record; scratch is regenerable by contract, C1).
- **Mirror per change:** the close-out print adds stdout to every `done` in 46 repos — fail-open on a missing hub path, so a repo without `/opt/fabrik` sees nothing; the § EXIT sentence lengthens a fleet-synced contract — the fabrik-lib drift check will flag their copy (mailed); the user-level hook fires in EVERY window including non-fabrik cwds — gated to `/opt`.
- **Fixed point:** not yet claimed — this is the DRAFT; `/fabrik-plan-review` converges it.

## Residual unknowns

- **Resolved:** where liveness lives (`<config-dir>/sessions/<pid>.json` + `procStart`); whether the hub's worktrees are removable today (none: all unmerged + dirty); whether a new user-level event key needs installer changes (no — `ENTRIES.items()`).
- **Open, self-service:** the exact fire rate of the hook line across the 9 live sessions (B.4 measures it before the row is written); the wall time of the holder probe on this box (A.8 records it; the hook mode never runs it); whether `docs/workstation/wsl-startup-inventory.md` inventories cron lines (B.6 greps first).
- **Open, operator-owned:** placing the cron line (B.5) — handed over in the Finish handoff with the dry-run summary.
- **Accepted:** an entry a Read tool holds with no fd (not held by the probe) is protected only by the 6 h freshness window and the `.keep` list — the table shows it before any apply, which is the constraint-2 design; a worktree left DIRTY by synced-file noise or gate outputs stays listed until its owner judges it (infra's sync-provenance finding `01M1Y86PQF7R658QRNX52GGMX6` is the root fix for the noise half).
