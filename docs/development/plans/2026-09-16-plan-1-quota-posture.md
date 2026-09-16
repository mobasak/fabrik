# Quota posture — one writer, three readers: every session sees the account picture and its forecast, and acts on the band

Status: DRAFT
**Owner:** fleet
Date: 2026-09-16
Spec: none — the operator declined the spec stage this turn ("do you really need to run spec for this?"); the design was settled in chat (superpowers brainstorming, architectural path, operator chose option 2: advise at AMBER, bind at RED) and is restated under § What we already agreed
Ruling: **D-264** (the bands are a behaviour contract inside the D-175 quota bullet) · **D-265** (the band axis partitions: GREEN under 85 · AMBER 85 to under 90 · RED 90 and over · WALL) · **D-269** (minted with this plan — the received decisions below)

## What this plan is

Today the fleet's quota picture is a query (`claude_rotate.py --status`, D-175) and a prose contract
(the bands, D-264/D-265). Nothing between "working normally" and the WALL is surfaced to a running
session, nothing forecasts WHEN a window ends, and no hook reads a percentage (`quota_stop.py` fires
only on the `fleet-exhausted` stamp). Operator, this turn: *"all agents must see a dashboard, account
tracking. we need to measure active usage and consumption and foresee when will the active 5h quota
and weekly quota end. then all agents should keep an eye on it. and adjust their work properly.
slowdown, pause, finish fast etc."* — and *"fable 5 has its own usage limit weekly and if an agent is
fable 5 it should also know this."*

The system is ONE WRITER (the rotation tick, already probing all five accounts every 5 minutes)
producing ONE FILE (`~/.claude/state/quota-posture.json`: per-window utilization, burn, reset,
forecast, the band, the fleet queue) and THREE READERS that never probe: a box-level
`UserPromptSubmit` hook that injects one `QUOTA:` line per prompt, a box-level `PreToolUse` hook that
HOLDS new heavy dispatch at RED and says the band once at AMBER, and the existing `--status` /
dashboard / `dispatch_headroom.py` surfaces reading the same numbers. Every reader fails OPEN on an
absent, unreadable or stale file — the posture `quota_stop.py` already takes. It SURFACES and ENFORCES;
it never rotates (D-201 / D-111 own the thresholds and the flip).

## Intake Inventory

Every item is the operator's, this session, quoted or near-verbatim; the phase that delivers it is
named so § Self-audit can walk the list.

| # | Operator item | Delivered by |
|---|---|---|
| I1 | "all agents must see a dashboard, account tracking" — every agent, every repo, without running a command by hand | Phase C (the `QUOTA:` line on every prompt, box-level wiring reaches all `/opt` repos incl. fabrik-lib) |
| I2 | "measure active usage and consumption" — live burn, not only the current % | Phase B (`burn_per_min` per window from a 30-minute sample ring) |
| I3 | "foresee when will the active 5h quota and weekly quota end" | Phase B (`minutes_to_wall`, `minutes_to_reset`, `reset_first` / `wall_first`) |
| I4 | "all agents should keep an eye on it and adjust their work properly. slowdown, pause, finish fast" — a signal agents ACT on mechanically, graded before the wall | Phase A (the contract sentence per band) + Phase C (advise at AMBER, HOLD at RED — the operator's option 2) |
| I5 | "fable 5 has its own usage limit weekly and if an agent is fable 5 it should also know this" | Phase B (the Fable window in the file) + Phase C (the hook keys the band on it when the transcript says the model is Fable) + Phase A (the contract tells a Fable session which figure is theirs) |
| I6 | "do not forget we have 3 different claude.md file one in the fabrik, one is governance, last one is in the fabrik-lib folder" | Phase A (one byte-identical sentence set in all three; fabrik-lib repaired first — it is one version behind) |
| I7 | "do you really need to run spec for this?" · "do we really need a plan for it?" · "ok go" — a short plan, no spec | this plan (monolith, three phases + Finish) |
| I8 | Standing: never cause data loss on the shared tree; siblings are working here | § Global Constraints (pathspec commits, private-index recipe with the deletion assertion GATING, twins cp'd) |

## What we already agreed (citations, not restatement)

- **Bands and their actions are already live** in `CLAUDE.md:385` and `templates/governance/CLAUDE.md:393` (D-265 text: `under 85 — GREEN` · `85 to under 90 — AMBER` · `90 and over — RED: commit, push, close your run record, and start nothing new` · the WALL). `/opt/fabrik-lib/CLAUDE.md:208` still carries the D-264 text (`85-90 — AMBER`, `90+ with NO eligible successor — RED`) — measured this session, one version behind.
- **Architecture** (chat, this turn): one writer (the tick) → one atomic file → readers fail open at 3 ticks of staleness; hooks wired at USER level (box-local, never synced to the ~46 repos); the contract text is BEHAVIOUR only, the machinery lives in code comments (D-265's lesson: three review rounds each found a fresh wrong claim in machinery prose inside that bullet).
- **Option 2** (operator: "ok 2"): AMBER advises, RED binds. RED binds NEW HEAVY DISPATCH only — `Agent` (the grounded dispatch tool; `Workflow` held only defensively), a new `command_run.py start` — never edits, tests, git, `command_run.py done|blocked|round|handoff`, `mail.py`, `Monitor`, `TaskStop`. RED means finish-and-checkpoint, never freeze.
- **Measured fire rates** (re-derived at write time from `~/.claude/state/rotate-ledger.jsonl`, `event == "tick"` rows with a numeric `pct`, population 2,361): `>= 85` on 141 (6.0%), `>= 90` on 111 (4.7%), `>= 98` on 0; 48 rows carry `weekly_pct` (the field began mid-day 2026-09-16). AMBER and RED are signal, not wallpaper (FIX DIRECTIVE 5).
- **Cobra check (D-253)** for the RED hold: the cheapest way to satisfy "no new heavy dispatch at RED" is to finish the current work fast and dispatch after the flip — which IS the wanted behaviour. The one gaming path — spending RED on many small non-`Agent` calls, or opening a `/fabrik-review-scoped` record to unlock seats — burns quota visibly on the injected line and is still capped by `dispatch_headroom.py`'s band trim; no second gate is added. This paragraph goes into the hook's docstring verbatim (Phase C).
- **Fable's limit, grounded live** (fabrik-researcher seat, support.claude.com articles 15424964 + 9797557, fetched 2026-09-16): Fable draws from the account's shared weekly pool with its own ceiling ("up to 50% of your weekly usage limits on Fable models"), reported by the usage endpoint as its own `weekly_scoped` percentage — which the probe already captures as `model_windows.Fable` (`claude_rotate.py:3398-3418`). When that ceiling is reached "you can keep using Fable models with usage credits, or switch to another model". So a Fable session's binding number is the `Fable` figure, and the contract says so without claiming a separate reset clock (Opus has one; Fable does not).
- **The hook contract, grounded live** (Opus + Sonnet fabrik-researcher seats, https://code.claude.com/docs/en/hooks fetched complete at 189.8 KB on 2026-09-16): (1) the common input fields are `session_id · prompt_id · transcript_path · cwd · scratchpad_dir · permission_mode · effort · hook_event_name` — "Only `SessionStart` hooks can receive a `model` field, and it is not guaranteed to be present. There is no `$CLAUDE_MODEL` environment variable." — so a per-call hook learns the model from the transcript tail (`entry["message"]["model"]` on `type == "assistant"` lines, the path `command_run.py:1969-2003` already reads; in a 261,702-line transcript the last assistant entry sat 20 lines from EOF, inside the last 64 KiB); the transcript "is written asynchronously and may lag the in-memory conversation", so the first tool call after a `/model` switch may still read the previous model — accepted and stated in the hook's docstring. (2) `UserPromptSubmit`: "Plain text stdout: Claude Code adds stdout it treats as plain text to Claude's context" (default timeout there is 30 s, and a timed-out hook's output is DISCARDED — fail-open — the prompt still reaches Claude). (3) `PreToolUse` returns `hookSpecificOutput.permissionDecision` ∈ allow · deny · ask · defer with `permissionDecisionReason` ("For `deny`, shown to Claude") AND `additionalContext` — "String added to Claude's context alongside the tool result. Ignored when permissionDecision is `defer`" — so the AMBER notice and the RED hold are ONE hook. Hook output strings are capped at 10,000 characters. (4) Matchable tool names: "`Bash`, `PowerShell`, `Edit`, `Write`, `Read`, `Glob`, `Grep`, `Agent`, `WebFetch`, `WebSearch`, `AskUserQuestion`, `ExitPlanMode`, and any MCP tool names" — `Agent` IS the subagent-dispatch tool; **`Workflow` is not a tool name** (2 occurrences on the page, both background-task labels), so the contract holds `Agent`, and the hook's predicate keeps `Workflow` only defensively.
- **Received decisions to mint as D-269** (with this plan's commit — the ledger rule is same-change): the system is BUILT (operator: "no this is not enough…"); option 2; no spec; three contracts with fabrik-lib edited cross-repo on the operator's explicit instruction this turn; hooks at USER level, box-local; the writer is the tick and the file is `~/.claude/state/quota-posture.json`.

## Global Constraints (every phase inherits these)

- **Twelve-factor non-negotiables (FLOOR):** logs = unbuffered **stdout only, never a logfile** (XI — the hooks print to stdout/stderr and the tick's outputs already ride cron's redirect; the posture file is STATE beside the ledger, not a log) · no daemonizing / PID files (VIII — the hook is a per-event process, the writer is the existing cron tick) · config = granular env vars (III — `ROTATE_STATE_DIR`, `QUOTA_POSTURE_STALE_S`, never a grouped set; no secrets in code or output) · shelled-out binaries pinned (II — none added) · migrations/backing-services/sticky-sessions/SIGTERM/immutable-release axes do not apply to a box-local hook and are stated so a step cannot quietly violate one.
- **`uv run pytest`, never bare `pytest`** (`10-python.md:21`); `datetime.now(UTC)` never `utcnow()` (`10-python.md:219`) — the posture carries epoch floats, formatted for humans only at print time.
- **Fail-open is DECLARED per key** (`58-resilience.md:69`): absent file · unreadable JSON · `ts` older than `QUOTA_POSTURE_STALE_S` (default 900 s = 3 ticks, finite-guarded like `quota_stop._stale_after_s` at `.claude/hooks/quota_stop.py:495-506`) · unreadable transcript · malformed stdin ⇒ the hook ALLOWS and, on `UserPromptSubmit`, SAYS `posture unavailable (<why>)` — never silence (the `selfwatch_check.py:133-134` B4 rule). The WALL stays `quota_stop.py`'s: this hook never denies while the `fleet-exhausted` stamp stands (no double-deny, no second exit path to learn).
- **No hook blocks on a percentage without its fire rate in this plan** (§ What we already agreed). **Never change** `ROTATE_THRESHOLD` (98, `claude_rotate.py:2560`), `ROTATE_DRAIN_THRESHOLD` (85, `:3783`), `ROTATE_URGENT_DRAIN_PCT` (90, `:4576`), `ROTATE_DWELL_MIN`, the urgent-drain mail or the flip policy — this plan reads them, it does not set them.
- **Extend, never duplicate:** the probe (`_usage_windows` `:3378`), the picture (`_fleet_picture` `:3776`, printed by `_print_picture` `:3905`), `_tick_burn` (`:4142`, the flip leg's single-tick projection — left untouched; the posture's smoothed burn is a different question and is written beside it, its mirror stated in Phase B), `dispatch_headroom.quota()` (`:163`), `quota_dashboard.py`'s Fable column (`:794-800`), `quota_stop.py`'s state accessors (`:481-493`).
- **Both `claude_rotate.py` copies are byte-identical twins** — `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py` after EVERY edit; `tests/test_claude_fleet.py::test_twin_copies_are_byte_identical` (`:949`) grades it.
- **`scripts/sysadmin/` is NOT a synced path** (`command grep -c 'scripts/sysadmin' scripts/fabrik_synced_manifest.py` → 0) — the new hook lives there and reaches every window through the USER-level `settings.json`, never through governance sync. `.claude/hooks/` IS synced: nothing new goes there.
- **The user-level settings are SIX independent files** — `~/.claude-fleet/{can,mob,ob,ozgurbasak,sarp}/settings.json` plus the legacy `~/.claude/settings.json` (the `--sync-shared` SOURCE, `docs/workstation/hooks-index.md:86-95`). Measured: `mob` and `sarp` differ from the other three in exactly one top-level key, `model`. So the wiring is added PER FILE by an idempotent installer that edits only `hooks[<event>]`, writes a timestamped backup beside each file, and replaces atomically — **never `claude_rotate.py --sync-shared`** (it would clobber the `model` drift). Existing sessions load hooks at start; the new line appears in NEW windows.
- **Pool OFF (D-181/D-182):** native seats only, model by ROLE (`model: "opus"|"sonnet"|"haiku"`), `dispatch_headroom.py` before any fan-out wider than the floor, `command_run.py dispatch --seats <n>` stamped BEFORE sending; every seat brief carries the git-verb prohibition (read-only git only).
- **Shared tree, three sessions:** explicit pathspecs with `git diff HEAD -- <paths>` read before every pathspec commit; `CHANGELOG.md` / `docs/DECISIONS.md` / `INDEX.md` / `docs/STRATEGIC_BACKLOG.md` ONLY via the private-index recipe (`CLAUDE.md` § Shared repo, steps 1-7) **with the step-4 deletion assertion GATING the commit as a branch, never read afterwards** (2026-09-16: an insert that sliced to `len(s)` deleted 2,551 lines of the backlog because the assertion was read after `update-ref`); never `--amend`; never `git stash pop`; a plumbing commit fires no post-commit hook, so a governance-surface change committed that way is distributed by hand with `scripts/sync_enforcement_to_projects.py --force`.
- **Safe flags only:** `check_corpus_weight.py --check` / `--check --strict` / `--help` (a bare run, `--seed`, `--reseed` and bare `--strict` WRITE and `git add`); `final_gate.py --json --check` for read-only gates; never write `~/.claude/state/command-feedback.jsonl`; never a crontab write (hand any cron line to the operator); never touch the sound system; no credential bytes in any output.
- **Cross-repo:** `/opt/fabrik-lib/CLAUDE.md` is edited under the operator's explicit instruction this turn (I6) — the fabrik-lib commit is made in fabrik-lib's own tree with its own trailers and says so; nothing else outside `/opt/fabrik` is written.
- **Lock overlap, stated:** the ACTIVE lock `2026-09-09-plan-1-review-convergence-redesign` (plan `Status: IN-PROGRESS`, 34 owned paths, baseline `03bb9702`) owns five of this plan's paths — `CLAUDE.md`, `templates/governance/CLAUDE.md`, `scripts/sysadmin/dispatch_headroom.py`, `scripts/sysadmin/quota_dashboard.py`, `docs/workstation/claude-account-rotation.md`. The operator overrode that lock for the CLAUDE.md bullet today ("infra is busy, you are fleet. cant you figure it on your own?"); this plan reads that as covering the same work stream and SAYS SO here; `/fabrik-execute-plan` will refuse on the overlap unless the operator confirms at execute time or infra releases the lock — § Residual unknowns R-open-1. The `2026-09-05-plan-1-windowed-cost-sidecar` lock (active) overlaps nothing.

## Context Ledger

| Source | Why this plan needs it |
|---|---|
| `scripts/sysadmin/claude_rotate.py` — `_fleet_tick_inner` `:4904` (the tick; ledger row `:4966-4990`; advisory call `:4991`), `_fleet_picture` `:3776-3903` (keys `now/active/accounts/queue/next_relief/hold/last_flip/thresholds`), `_print_picture` `:3905`, `_usage_windows` `:3378-3418` (`five_hour`/`seven_day` → `{utilization, resets_at_epoch}`; `model_windows[<display_name>]` same shape from `limits[].kind == "weekly_scoped"`), `_tick_burn` `:4142`, `_rotate_state_dir` `:2129` (honours `ROTATE_STATE_DIR`), `_ledger_append` `:2162`, `_ledger_rotate` `:2706`, `_STATE_DIR_ERRORS` `:448`, `_account_caps` `:3431` (`caps.json`), `_urgent_drain_pct` `:4568`, `_rotate_threshold` `:2524`, `_fmt_when` `:3770`, `_active_account_walled` `:4391` | the writer's call site, the picture it composes, the window shapes, the accessors it reuses |
| `.claude/hooks/quota_stop.py` — `main` `:563` (stdin → `tool_name`, `tool_input.command`, `session_id`; fail-open on unreadable/non-object payload), `_state_dir/_stamp/_tick_log/_stale_after_s` `:481-506`, the deny shape `:594-600` (`hookSpecificOutput.permissionDecision`) | the reader's fail-open shape and the deny grammar; the WALL boundary this plan must not cross |
| `scripts/sysadmin/user_hook_gate.py:1-25` and `scripts/sysadmin/selfwatch_check.py:100-135` | the two existing box-level hook patterns (gate-deferred vs direct); the new hook is DIRECT like `selfwatch_check.py` because no project wires it |
| `~/.claude-fleet/<slug>/settings.json` × 5 + `~/.claude/settings.json` (`docs/workstation/hooks-index.md:86-104`) | the wiring targets; the drift measured (`model` key on mob/sarp) |
| `scripts/sysadmin/dispatch_headroom.py::quota` `:163-200` (subprocess `--status --json`, hottest window, `in_drain_band`, `thresholds.drain_band`) | the seat cap must read the same band the hook enforces |
| `scripts/sysadmin/quota_dashboard.py:670-672` (one `--status --json` run), `:794-806` (the Fable column) and `docs/workstation/quota-dashboard.md` § Reading the board (`:75`) | forecast columns from the same payload |
| `tests/test_claude_fleet.py` — `_fleet_two_accounts` `:1013`, `_fleet_creds` `:971`, `_fake_oauth` `:994`, `_usage_blob` `:1006`, the two tick graders `:4369-4432` (monkeypatch `_ledger_append`, `ROTATE_STATE_DIR` pinned at `:73`) | the fixture idiom every Phase B grader copies |
| `tests/test_quota_stop_hook.py::_run` `:58-80` | the subprocess-driven hook grader idiom Phase C copies (env `ROTATE_STATE_DIR`, `QUOTA_STOP_TICK_LOG`) |
| `tests/test_governance_template_split.py` — `T6_CLAIMS` `:112`, `test_the_shared_tree_commit_rules_are_identical_in_both_contracts` `:168`, `FABRIK`/`TEMPLATE_REL` `:16-17` | the twin-contract grader extended to a third file |
| `scripts/command_run.py` — `_state_dir` `:84-88` (`~/.claude/state/command-runs`), `_record_path` `:155`, `"state": "running"` `:2475`, the transcript `model` read `:2001` | how the hook tells a live run from none, and how a hook learns the session's model from `transcript_path` |
| `CLAUDE.md:385`, `templates/governance/CLAUDE.md:393`, `/opt/fabrik-lib/CLAUDE.md:208` | the D-175 bullet the new sentences join (READ BEFORE YOU EDIT — inside the bullet, never a new section) |
| `/opt/fabrik-lib/README.md` module table (grepped `quota|cost|budget|forecast|rate.?limit|usage`: `cost-budget/` is LLM-dollar caps, `concurrency-throttle/` a Redis semaphore, `api-auth/` per-tier rate limits) | the mandatory fabrik-lib consult: nothing vendorable answers "forecast a subscription window from utilization samples" — built here, box-local, ~150 lines |
| `docs/DECISIONS.md` D-175 · D-181/D-182 · D-201 · D-111 · D-253 · D-264 · D-265 | the rulings this plan inherits |

## Constraints Digest (verbatim rows from the MUST-READ packs)

MUST-READ set = FLOOR + `python3 scripts/review_rubric.py --changed <File Scope>` MATCHES: `core/10-python.md` + 12-FACTOR (FLOOR); `core/40-documentation.md`, `core/45-testing-strategy.md`, `core/58-resilience.md` (MATCHED). Each row quotes the pack; the implication is this plan's.

| Pack `file:line` | Verbatim | Implication here |
|---|---|---|
| `.windsurf/rules/core/10-python.md:21` | "is the mandated Python package manager" | every gate line in every phase is `uv run pytest …` |
| `.windsurf/rules/core/10-python.md:219` | "`datetime.now(UTC)`, never `datetime.utcnow()`" | the posture stores epoch floats from `time.time()`; human formatting only via `_fmt_when` |
| `scripts/review_rubric.py:140` (the FLOOR's 12-FACTOR block) | "XI logs: unbuffered stdout only; the app never writes/rotates a logfile" | the hook prints to stdout/stderr only; the writer's diagnostics ride the tick's stdout; the posture file is state, not a log |
| `.windsurf/rules/core/40-documentation.md:185` | "Edit existing docs instead of creating new ones." | no new reference doc: the rotation doc's § `--status`, `hooks-index.md` § 2, `quota-dashboard.md` § Reading the board are extended in place |
| `.windsurf/rules/core/40-documentation.md:129` | "Any change to code (`src/`, `scripts/`, `templates/`)" | every phase carries its CHANGELOG entry (private-index recipe) |
| `.windsurf/rules/core/40-documentation.md:157` | "`docs/development/plans/YYYY-MM-DD-plan-<name>.md`" | this file's location and name |
| `.windsurf/rules/core/45-testing-strategy.md:19` | "one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones" | one grader per Behavior Contract row; the RED hold and the fail-open rows come first |
| `.windsurf/rules/core/45-testing-strategy.md:21` | "a non-trivial behavior's test proves something only if it has been SEEN RED" | every new grader is run RED before the code lands (the steps say so literally) |
| `.windsurf/rules/core/58-resilience.md:69` | "a DECLARED fail-open/closed posture per key" | § Global Constraints declares the posture per failure key; each key has a grader |
| `.windsurf/rules/core/58-resilience.md:59` | "Dependency **refuses work** (429/402/quota)" | quota refusal is the class this plan pre-empts: the hold at RED is the "pause key" before the 429 |
| `.windsurf/rules/core/58-resilience.md:175` | "**Timeout is mandatory.**" | the hook makes NO network call; its one I/O beyond the posture file is a bounded 64 KiB tail read of the transcript; the readers' `--status --json` subprocess keeps its existing `timeout=60` |

## Phase A — the three contracts (repair fabrik-lib, then one identical sentence set in all three)

**Responsibility:** the BEHAVIOUR half — what an agent does with the `QUOTA:` line, what each band obliges, which figure a Fable session reads — as ONE sentence set present exactly once in `CLAUDE.md`, `templates/governance/CLAUDE.md` and `/opt/fabrik-lib/CLAUDE.md`, inside the existing D-175 quota bullet, graded by the twin-contract test extended to the third file. Machinery stays out of the contract (D-265).

**Interfaces — Produces:** `QUOTA_CLAIMS: tuple[str, ...]` in `tests/test_governance_template_split.py` (the sentences below, each present exactly once in all three files); `THIRD_CONTRACT = Path("/opt/fabrik-lib/CLAUDE.md")` (the grader skips the third file with a stated reason when the path is absent, so the suite stays portable). **Consumes:** nothing from later phases — the contract names the line FORMAT Phase C emits, so the format is fixed HERE and Phase C's grader asserts it byte for byte.

**The shared sentences** (appended inside the D-175 bullet directly after the WALL sentence; identical bytes in all three files; wrap-safe substrings of them become `QUOTA_CLAIMS`):

> **The `QUOTA:` line (D-269).** Every prompt opens with one injected line — `QUOTA: <account> · 5h <n>% (<forecast>) · weekly <n>% (<forecast>) · Fable <n>% · band <GREEN|AMBER|RED|WALL> · successor <account>` — where `<forecast>` is `reset in <h:mm>` or `wall in ~<m>m at <n>%/m` whichever comes FIRST, written by the rotation tick and read by a box-level hook. `posture unavailable` means the tick is dead or stale, not that quota is fine — run `python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status`. **The band names the action:** at AMBER the line is advice; at RED the hook HOLDS `Agent` and a new `command_run.py start` (a run record already live keeps its seats, and a `/fabrik-review-scoped` start stays allowed because it is the finish path) — everything a checkpoint needs stays allowed, so RED is finish-and-checkpoint, never freeze. **A session on a Fable model reads the `Fable` figure as its weekly** — Fable draws on the account's weekly pool under its own ceiling, reported as its own percentage, and the hook keys the band on it when the transcript says the model is Fable.

Steps:
1. **READ BEFORE YOU EDIT.** Open `CLAUDE.md:385` and read the whole D-175 bullet; open `templates/governance/CLAUDE.md:393` and `/opt/fabrik-lib/CLAUDE.md:208` the same way. Diff the three band sentences: hub and template are identical (D-265, graded by `T6_CLAIMS`); fabrik-lib carries `85-90 — AMBER` and `90+ with NO eligible successor — RED` (D-264 text) and lacks `85 to under 90` — confirm with `command grep -c 'under 90' /opt/fabrik-lib/CLAUDE.md` (expected 0) before touching it.
2. **Grader first — RED.** In `tests/test_governance_template_split.py` add `THIRD_CONTRACT` and `QUOTA_CLAIMS = (` `"**under 85 — GREEN:**"`, `"85 to under 90"`, `"RED: commit, push, close your run record"`, `"The `QUOTA:` line (D-269)"`, `"posture unavailable"`, `"at RED the hook HOLDS `Agent` and a new"`, `"reads the `Fable` figure as its weekly"` `)` and `test_the_quota_bands_and_the_quota_line_are_identical_in_all_three_contracts` — for each claim `count == 1` in hub, template and (when `THIRD_CONTRACT.exists()`, else `pytest.skip("fabrik-lib is not checked out on this box")`) fabrik-lib. Run `uv run pytest tests/test_governance_template_split.py -k quota_bands` → RED for the right reasons: fabrik-lib fails the `85 to under 90` claim, all three fail every D-269 claim. Paste the failure list into § Evidence.
3. **Repair fabrik-lib first.** In `/opt/fabrik-lib/CLAUDE.md:208` replace its AMBER and RED sentences with the hub's D-265 sentences byte for byte (copy them from `CLAUDE.md:385`, never retype). Commit in `/opt/fabrik-lib` with its own trailers (`Agent-Role: primary`, `Agent-Context: …operator-authorised cross-repo edit, D-269`) after `git -C /opt/fabrik-lib diff HEAD -- CLAUDE.md` shows exactly that hunk; fabrik-lib's `check_governance_drift.py` reads the hub file and must print no `missing:` anchor.
4. Write the shared sentences into all three files inside the D-175 bullet after the WALL sentence — one insert script that locates the WALL sentence's END anchor (`the only path through (every tool that path needs is allowed).`) and FAILS LOUDLY when the anchor is missing; never slice to `len(s)`. Wrap to the file's own width. `md5sum` the sentence set extracted from each file (`command grep -o 'The `QUOTA:` line.*Fable\.' <file> | md5sum`) — three identical hashes.
5. Grader → GREEN. Run `python3 scripts/enforcement/check_corpus_weight.py --check --strict` (safe flags only): the twins grow by the sentence set (~+900 B each); if the ratchet reds, read the check's docstring for the accepted justification and carry it in the D-269 row and the commit body — never `--seed`/`--reseed`.
6. **Highest-risk mirror, stated:** the template is a governance-sync trigger — a porcelain commit distributes the new sentences to ~46 repos on the post-commit sync; verify afterwards with `command grep -l 'The `QUOTA:` line (D-269)' /opt/*/CLAUDE.md | wc -l` against the synced-project count the sync printed. The hook that makes the sentences TRUE lands in Phase C; between A and C the sentences describe a line that does not yet appear — acceptable for one execution window because the sentence's own escape (`posture unavailable` ⇒ run `--status`) already holds; state this in the CHANGELOG entry.
7. Docs: CHANGELOG `### Changed — The QUOTA line joins the quota bullet in all three contracts (2026-09-16)` via the private-index recipe (step-4 assertion GATING).
8. **Closing sequence (literal):** (a) gate `uv run pytest tests/test_governance_template_split.py -x --tb=short` → green; (b) `python3 scripts/enforcement/check_doc_sync.py` + the doc steps above; (c) **`/fabrik-review-scoped` on this phase's diff — BLOCKING, run to its coverage-adjudicated exit** (surface: three contract files + one test; a 1-unit judgement surface ⇒ the floor, three native seats on different angles — contract truth vs the code that will emit the line · byte-identity across the three files · the sync blast radius — stamped `command_run.py dispatch --seats 3`; Opus on the contract-truth seat, Sonnet on the other two; every finding FIXED or REFUTED, a fresh non-authoring delta seat confirms 0); (d) commit — hub: `git commit -m … -- CLAUDE.md templates/governance/CLAUDE.md tests/test_governance_template_split.py` after `git diff HEAD -- <those paths>` reads as exactly this phase; CHANGELOG by the private-index recipe; trailers `Agent-Role: primary` · `Agent-Phase: A` · `Agent-Context: …`; push; realign `git reset -q HEAD -- <paths>`.

**Behavior Contract — Phase A**

| # | Given | When | Then | Grader |
|---|---|---|---|---|
| A1 | the three contracts | the grader runs | each `QUOTA_CLAIMS` sentence counts exactly 1 in hub, template and fabrik-lib | `test_the_quota_bands_and_the_quota_line_are_identical_in_all_three_contracts` (seen RED at step 2) |
| A2 | fabrik-lib not checked out | the grader runs | the third-file half SKIPS with a stated reason; the hub/template half still grades | same test, `pytest.skip` branch (run once with `THIRD_CONTRACT` monkeypatched to a missing path) |
| A3 | the D-175 bullet | the sentences are inserted | they sit after the WALL sentence INSIDE the bullet, no new heading; the insert refuses when the anchor is missing | the insert script's own assert + `command grep -c '^## .*QUOTA' <file>` = 0 |

## Phase B — the writer: the posture file from the tick, with forecast and the Fable window

**Responsibility:** `scripts/sysadmin/claude_rotate.py` (+ twin) computes and atomically writes `<state>/quota-posture.json` once per tick, exposes it on `--status` (text: one `posture:` line; `--json`: a top-level `posture` key), and never raises. One pure function computes, one I/O function writes, one reads.

**Interfaces — Produces:**
- `_quota_posture(accounts: list[dict], picture: dict, now: float, prev: dict | None, hold: bool) -> dict` — pure. Returns the schema below. `prev` is the previous file's content (or `None`); its `samples` ring is carried forward.
- `_write_quota_posture(posture: dict) -> None` — writes `_rotate_state_dir() / "quota-posture.json"` via `<path>.tmp` + `os.replace`; swallows `_STATE_DIR_ERRORS` (`:448`) exactly as `_ledger_append` does; never raises.
- `_read_quota_posture() -> dict | None` — `None` on absent/unreadable/non-dict; NO staleness judgement here (readers own it, each with its declared bound).
- Env: none new in the writer (the state dir is `ROTATE_STATE_DIR` as today).
- **Schema (`schema: 1`):**

```json
{"schema": 1, "ts": 1789660000.0, "tick_period_s": 300,
 "active": {"email": "ozgurbasak@ocoron.com", "slug": "ozgurbasak", "weekly_cap": null,
   "windows": {"five_hour": W, "seven_day": W, "fable": W | null, "models": {"<display_name>": W}},
   "hottest": "five_hour" | "seven_day", "band": "GREEN|AMBER|RED|WALL",
   "hottest_fable": "five_hour" | "seven_day" | "fable", "band_fable": "GREEN|AMBER|RED|WALL"},
 "fleet": {"queue": ["<email>", "..."], "successor": "<email>" | null, "next_relief": {"epoch": 0.0, "email": "", "window": ""} | null,
   "hold": {} | null, "last_flip": {} | null, "thresholds": {"trip": 98.0, "drain_band": 85.0, "urgent": 90.0}},
 "samples": {"<email>": [{"ts": 0.0, "five_hour": 0.0, "five_hour_reset": 0.0, "seven_day": 0.0, "seven_day_reset": 0.0, "fable": 0.0, "fable_reset": 0.0}]}}
```
  where `W = {"utilization": float | null, "resets_at": float | null, "wall_pct": 100.0 | <cap>, "burn_per_min": float | null, "minutes_to_wall": float | null, "minutes_to_reset": float | null, "verdict": "reset_first" | "wall_first" | "unknown"}`.
- **Burn:** per window, from `samples[<active email>]` — keep entries with `now - ts <= 35 * 60` whose `<window>_reset` equals the current reset epoch (a moved reset epoch restarts that window's history, the same "same window = same reset epoch" rule `_tick_burn` applies at `:4170`); with ≥ 2 kept samples spanning ≥ 240 s, `burn_per_min = max(0.0, (u_now - u_oldest) / ((now - ts_oldest) / 60))`; otherwise `null`. A flip changes the active email, so the ring is per email and a new active account starts empty (burn `null` for one tick — stated, graded).
- **Forecast:** `minutes_to_wall = (wall_pct - u) / burn_per_min` when `burn_per_min` is a positive finite number, else `null`; `minutes_to_reset = (resets_at - now) / 60` when `resets_at` is known, else `null`; `verdict = "reset_first"` when `minutes_to_reset` is known and (`minutes_to_wall` is `null` or `minutes_to_reset <= minutes_to_wall`), `"wall_first"` when `minutes_to_wall` is known and smaller, else `"unknown"`. `wall_pct` is the account's `caps.json` cap for `seven_day` when one exists (`_account_caps` `:3431`, surfaced as `weekly_cap` in the picture row), `100.0` otherwise and for the other windows.
- **Band:** `hot = max(five_hour.utilization, seven_day.utilization)` over the readings present; `band = "WALL"` when `hold` (the `fleet-exhausted` stamp stands — the tick knows it as `picture["hold"]`), else `"RED"` when `hot >= _urgent_drain_pct()`, else `"AMBER"` when `hot >= ROTATE_DRAIN_THRESHOLD`, else `"GREEN"`; NO reading at all ⇒ `band = null` (unknown, never GREEN — the `dispatch_headroom.quota()` lesson at `:176-186`). `band_fable`/`hottest_fable` repeat the computation with the Fable window included; when no Fable window is present they equal `band`/`hottest`.
- **Fable window:** `windows.models` carries EVERY `model_windows` entry the probe reported; `windows.fable` is the first key that starts with `"Fable"` (the dashboard reads `.get("Fable")` at `:798` today — a renamed display name would silently drop that column; the prefix match is the mirror, stated).
- **`--status`:** text adds one line after `last flip:` — `posture: <band> · 5h <n>% <forecast> · weekly <n>% <forecast> · Fable <n>% · burn 5h <x>%/m · written <age> ago` (or `posture: none written yet` / `posture: STALE <age>`); `--json` adds top-level `"posture": <file content or null>`.

**Interfaces — Consumes:** the picture from `_fleet_picture(accounts, <active slug>, now)` — the slug the tick resolves for its own flip leg (grep `_resolve_active` inside `_fleet_tick_inner` `:4904-4960`; `accounts, pending = _fleet_account_rows(dirs, allow_pings=True)` at `:4923`); the hold from `picture["hold"]`; `_account_caps()`.

Steps:
1. **Graders first — RED**, all in `tests/test_claude_fleet.py` beside the tick graders (`:4369-4432`), copying their fixture idiom (`_fleet_two_accounts` + `_fleet_creds` + `_fake_oauth` + `_usage_blob`; `ROTATE_STATE_DIR` is tmp-pinned by `_canonical`):
   - `test_the_fleet_tick_writes_the_quota_posture_file_atomically` — after `cr._cmd_tick() == 0`, `<state>/quota-posture.json` parses; `active.email` equals the tick row's `account`; `windows.five_hour.utilization == row["pct"]`, `windows.seven_day.utilization == row["weekly_pct"]`; `ts` within ±5 s of the fixture's `now`; no `quota-posture.json.tmp` remains; `fleet.thresholds == {"trip": 98.0, "drain_band": 85.0, "urgent": 90.0}` under default env.
   - `test_posture_burn_is_null_on_the_first_sample_and_positive_on_the_second` — tick once at `t0` (`_usage_blob(42.0, 50.0)`), then again at `t0 + 300` with `45.0` (monkeypatch the clock the tick reads); second file: `five_hour.burn_per_min == 0.6`, `minutes_to_wall == (100 - 45) / 0.6`, `verdict == "wall_first"` when the fixture's `resets_at` is far, and `seven_day.burn_per_min == 0.0` with `minutes_to_wall is None`.
   - `test_posture_burn_restarts_when_the_window_reset_epoch_moves` — second sample with a different `resets_at` → `burn_per_min is None`.
   - `test_posture_samples_ring_is_bounded_and_per_email` — 12 ticks → at most 7 kept samples for the active email; a flip (fixture swaps the active pointer) starts the new email with 1 sample and burn `null`.
   - `test_posture_band_follows_the_hottest_window_and_the_hold` — parametrised `(session, weekly, expect)`: `(84.9, 10, "GREEN")`, `(85.0, 10, "AMBER")`, `(10, 89.9, "AMBER")`, `(10, 90.0, "RED")`, `(0.0, 0.0, "GREEN")`; plus the stamp written → `"WALL"`; plus no reading (`_active_account_walled` monkeypatched to return a row without windows, the idiom the absent-window grader already uses) → `band is None` and the file is STILL written.
   - `test_posture_carries_the_fable_window_and_keys_band_fable_on_it` — extend `_usage_blob` with an optional `fable: float | None` that emits `limits=[{"kind": "weekly_scoped", "scope": {"model": {"display_name": "Fable"}}, "percent": <fable>, "resets_at": "..."}]` (the shape `_usage_windows` parses at `:3398-3418`); `fable=32.0` → `windows.fable.utilization == 32.0`, `band == "GREEN"`, `band_fable == "GREEN"`; `fable=91.0` with cool session/weekly → `band == "GREEN"`, `band_fable == "RED"`, `hottest_fable == "fable"`; no `limits` → `windows.fable is None` and `band_fable == band`.
   - `test_posture_weekly_wall_is_the_caps_json_cap` — `caps.json` with the active email at 95 → `seven_day.wall_pct == 95.0`.
   - `test_posture_write_never_raises_on_an_unwritable_state_dir` — `chmod 0o500` the state dir before the tick → tick returns 0, no traceback in `capsys`.
   - `test_status_json_carries_the_posture_and_status_text_prints_one_posture_line` — after a tick, `--status --json` has `posture["schema"] == 1`; `--status` text has exactly one line starting `posture:`; with no file, `posture: none written yet`.
   Run `uv run pytest tests/test_claude_fleet.py -k posture -x --tb=short` → every grader RED for its own reason (paste into § Evidence).
2. Implement `_quota_posture`, `_write_quota_posture`, `_read_quota_posture` in `scripts/sysadmin/claude_rotate.py` next to `_fleet_picture` (`:3776`); call from `_fleet_tick_inner` immediately after the ledger block (`:4990`, before `_fleet_active_wall_advisory` at `:4991`): `_write_quota_posture(_quota_posture(accounts, _fleet_picture(accounts, active_slug, now), now, _read_quota_posture(), hold=bool(picture["hold"])))`. The comment above it carries the burn rule and the mirror against `_tick_burn` in one paragraph (single-tick projection for the flip leg vs a 30-minute smoothed rate for humans and hooks — two questions, two functions, neither reads the other) and NO statistics (D-265's rule: numbers rot; the ledger is the source).
3. `_print_picture`: append the `posture:` line; the `--json` emitter adds `"posture"`. Age formatting via `_fmt_when`-style minutes, never a new formatter.
4. `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py`; `uv run pytest tests/test_claude_fleet.py scripts/sysadmin/test_claude_rotate.py tests/test_claude_rotate_v2.py -q --tb=short` — expected: the posture graders green, the twin grader green, and the SAME 13 pre-existing failures as at baseline (the snapshot-mode/ACTIVE_MARKER identity tests — compare the failing-test NAME SET against a throwaway-worktree run at the phase's base commit, never the count; a new name is this phase's defect).
5. Docs: `docs/workstation/claude-account-rotation.md` § `--status` (`:195`) gains one paragraph on the `posture:` line and the file (path, `schema`, the three windows, burn/forecast/verdict, band computed from the live thresholds, the fail-open bound readers apply) — inside that section, no new heading; `claude_rotate.py`'s `# AFTER-EDIT:` header already names that doc. CHANGELOG `### Added — The rotation tick writes the quota posture file; --status prints it (2026-09-16)`.
6. **Closing sequence (literal):** (a) the gate of step 4 → green (name-set unchanged); (b) `python3 scripts/enforcement/check_doc_sync.py` + step 5; (c) **`/fabrik-review-scoped` on this phase's diff — BLOCKING, run to its coverage-adjudicated exit**: pin the diff to `<scratch>/phaseB.diff` with its md5; units = 2 (the writer+forecast, the `--status` surface); `python3 scripts/sysadmin/dispatch_headroom.py --units 2 --risky 1 --mechanical 1`, stamp `command_run.py dispatch --seats <SEATS>`, dispatch exactly the printed mix in ONE message (Opus on the writer — atomicity, the sample ring, the band boundaries; Sonnet breadth on `--status`; Haiku on the grep-able class: every `None`/`bool` guard mirrors `_row_utils`); every finding FIXED with a grader or REFUTED; delta rounds over the fix diff (`--delta <n>`), closing on a fresh non-authoring seat confirming 0; (d) commit `-- scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_claude_fleet.py docs/workstation/claude-account-rotation.md` after `git diff HEAD -- <paths>`; CHANGELOG by the private-index recipe; `Agent-Phase: B`; push; realign.

**Behavior Contract — Phase B**

| # | Given | When | Then | Grader |
|---|---|---|---|---|
| B1 | a tick with a readable active account | the tick runs | the posture file exists, atomic, `ts` fresh, windows match the ledger row | `test_the_fleet_tick_writes_the_quota_posture_file_atomically` |
| B2 | one prior sample 300 s old, same reset epoch | the tick runs | `burn_per_min`, `minutes_to_wall`, `verdict` computed as specified | `test_posture_burn_is_null_on_the_first_sample_and_positive_on_the_second` |
| B3 | the reset epoch moved | the tick runs | burn `null` for that window | `test_posture_burn_restarts_when_the_window_reset_epoch_moves` |
| B4 | 12 ticks / a flip | the tick runs | ≤ 7 samples per email; a new active email starts empty | `test_posture_samples_ring_is_bounded_and_per_email` |
| B5 | readings at the band boundaries · the stamp · no reading | the tick runs | GREEN/AMBER/RED exactly at 85/90, WALL on the stamp, `null` on no reading | `test_posture_band_follows_the_hottest_window_and_the_hold` |
| B6 | the probe reports a Fable weekly_scoped limit / does not | the tick runs | `windows.fable` carried / `null`; `band_fable` keys on it / equals `band` | `test_posture_carries_the_fable_window_and_keys_band_fable_on_it` |
| B7 | a `caps.json` cap for the active email | the tick runs | `seven_day.wall_pct` is the cap | `test_posture_weekly_wall_is_the_caps_json_cap` |
| B8 | an unwritable state dir | the tick runs | rc 0, no traceback (the ledger's own tolerance) | `test_posture_write_never_raises_on_an_unwritable_state_dir` |
| B9 | a written file / none | `--status` / `--status --json` | one `posture:` line / the `posture` key; `none written yet` when absent | `test_status_json_carries_the_posture_and_status_text_prints_one_posture_line` |
| B10 | any edit to the hub copy | the suite runs | the aro-wake twin is byte-identical | `test_twin_copies_are_byte_identical` (`:949`) |

## Phase C — the readers: the prompt line, the RED hold, and the existing surfaces

**Responsibility:** `scripts/sysadmin/quota_posture_hook.py` (NEW, box-local, one file, both events, `--install`/`--check`), `dispatch_headroom.py::quota()` and `quota_dashboard.py` reading the same posture through the `--status --json` payload, the six settings files wired, the tick warning when wiring is missing.

**Interfaces — Consumes:** the Phase B schema (`posture["ts"]`, `active.windows.*`, `active.band`, `active.band_fable`, `fleet.successor`), the `posture` key in `--status --json`; the hook payload fields `hook_event_name`, `session_id`, `tool_name`, `tool_input.command`, `transcript_path` (the last one read by `mcp_watch.py:350` today); the run-record path `~/.claude/state/command-runs/<sid>.json` with `"state": "running"` (`command_run.py:84-88`, `:155`, `:2475`); the transcript's assistant entries' `message.model` (`command_run.py:2001`).

**Interfaces — Produces:**
- `scripts/sysadmin/quota_posture_hook.py` — stdin JSON → `main() -> int`, always exit 0. `_load_posture(now) -> tuple[dict | None, str]` (the dict or `None` + a reason: `absent` · `unreadable` · `stale <m>m`), staleness bound `QUOTA_POSTURE_STALE_S` default `900`, finite-guarded exactly like `quota_stop._stale_after_s`. `_session_model(transcript_path) -> str | None` — reads the LAST 64 KiB of the transcript, scans backwards for the last line whose `type == "assistant"` and returns `message.model`; `None` on any failure. `_is_fable(model) -> bool` = `model.startswith("claude-fable")`. `_live_run(sid) -> bool` — the run record exists and `state == "running"` (any error ⇒ `False`, i.e. the hold applies — stated: a corrupt record does not unlock seats). `_format_line(posture, is_fable) -> str` — byte-exact to Phase A's format: `QUOTA: <slug> · 5h <n>% (<forecast>) · weekly <n>% (<forecast>) · Fable <n>% · band <B> · successor <slug or none>`; `<forecast>` = `reset in <h:mm>` when `verdict == "reset_first"`, `wall in ~<m>m at <burn>%/m` when `"wall_first"`, `no burn` when `"unknown"`; `<B>` = `band_fable` when `is_fable` else `band`; a `null` band prints `band ?`. `--install [--check]`: over the six settings files, add under `UserPromptSubmit` and `PreToolUse` (matcher `.*`) an entry `{"type": "command", "command": "python3 /opt/fabrik/scripts/sysadmin/quota_posture_hook.py", "timeout": 10}` when no entry under that event names this basename; `--check` prints per file `wired` / `MISSING` and exits 1 on any missing, writes nothing; the writing mode backs up to `<file>.backup.<YYYYmmdd-HHMMSS>` beside the file, edits only `hooks[<event>]`, keeps every other key byte-for-byte (the `model` drift), writes tmp + `os.replace`, prints per-file verdict.
- Behaviour per event: **`UserPromptSubmit`** → print ONE line to stdout: the `QUOTA:` line, or `QUOTA: posture unavailable (<reason>) — run python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status`. **`PreToolUse`** → `band == "WALL"` or posture unavailable ⇒ print nothing, exit 0 (the WALL is `quota_stop.py`'s; fail-open); `band == "RED"` ⇒ DENY (`hookSpecificOutput.permissionDecision: "deny"`, `permissionDecisionReason` = the `QUOTA:` line + `RED: finish and checkpoint — commit, push, close your run record; new seats and new runs resume after the flip or the reset (<forecast>)`) when `tool_name in {"Agent", "Workflow"}` (`Agent` is the grounded dispatch tool; `Workflow` is not a tool name per the live docs and is kept in the set defensively, commented as such) and not `_live_run(sid)`, or when `tool_name == "Bash"` and `tool_input.command` matches `\bcommand_run\.py\s+start\b` without `--command fabrik-review-scoped` or `--command fabrik-review`; everything else ALLOW silently. `band == "AMBER"` ⇒ once per `(sid, band)` — marker `<state>/quota-posture-notified/<sid>.<band>` — emit `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "<the QUOTA: line> — AMBER: finish what you started, start nothing heavy"}}` with NO `permissionDecision` (the call proceeds; grounded: `PreToolUse` carries `additionalContext`, ignored only on `defer`); on RED the marker is written too so the hold's reason is not repeated on every allowed call. Markers older than 24 h are pruned by the tick (a two-line addition beside `_ledger_rotate`).
- The docstring carries the Cobra paragraph from § What we already agreed verbatim, the fire rates with their date and population, and the declared fail-open keys.
- `dispatch_headroom.quota()` — reads `payload.get("posture")` from the same `--status --json` run; when present and `now - posture["ts"] <= 900`, `band` comes from `posture["active"]["band"]` and the printed QUOTA line gains `wall in ~<m>m` / `reset in <h:mm>` from the hottest window; otherwise the existing computation stands unchanged (mirror: the two can disagree only while the posture is stale, and then the picture wins — stated in the function's docstring).
- `quota_dashboard.py` — two cells per window row from `posture` (`burn %/m`, `wall vs reset`) rendered by the existing `cell()` helper's neighbour; `no reading` when the window's burn is `null`; the Fable column gets the same two cells.
- `claude_rotate.py` — `_posture_hook_wiring_warnings() -> list[str]`: for each of the six settings files, `MISSING` when neither event names the hook basename; printed with `_fleet_row_warnings` output in the tick (`:4992-4993`): `⚠ quota-posture hook not wired in <n> of 6 settings files — run quota_posture_hook.py --install`.

Steps:
1. **Confirm delivery on this box (executable, cheap).** The live docs settle the mechanism (§ What we already agreed: `PreToolUse` carries `additionalContext`; `UserPromptSubmit` plain stdout lands as context; "To confirm delivery, check the debug log"). Prove it here once: wire the hook skeleton (emitting a marker string) into ONE settings file via `--install` on a COPY (`QUOTA_POSTURE_SETTINGS=<tmp list>` so the installer targets the copy), run a throwaway `claude -p 'reply with the word ok' --allowedTools ""` under a `CLAUDE_CONFIG_DIR` pointing at a tmp dir holding that copy, and read the resulting transcript for the marker; record the command and its output in § Evidence. A negative here is a BLOCKED finding against the docs, not a silent fallback.
2. **Graders first — RED**, NEW file `tests/test_quota_posture.py` driven like `tests/test_quota_stop_hook.py::_run` (`:58-80`): a `_posture(tmp_path, **overrides)` helper writes a schema-1 file into `tmp_path/state`; `_hook(payload, *, state, transcript=None, run_record=None, env=None)` runs the script with `ROTATE_STATE_DIR`, `QUOTA_POSTURE_STALE_S`, `COMMAND_RUN_DIR` pointed into `tmp_path`:
   - `test_prompt_line_says_unavailable_when_the_file_is_absent_or_stale` — absent → line contains `posture unavailable (absent)`; `ts = now - 901` → `(stale 15m)`; rc 0 both; `PreToolUse` prints nothing in both.
   - `test_prompt_line_matches_the_contract_format_byte_for_byte` — GREEN posture → the line equals the expected string built from the fixture (also asserts the same `QUOTA_CLAIMS` format tokens Phase A pinned: `· band `, `· successor `).
   - `test_red_holds_agent_and_workflow_only_without_a_live_run` — RED: `Agent` → deny JSON with reason containing `RED` and the forecast; `Workflow` → deny; `Agent` with a `running` record for the sid → allow; `Edit`, `Read`, `Bash git push`, `Bash python3 scripts/command_run.py done …`, `Monitor`, `TaskStop` → allow (exit 0, empty stdout).
   - `test_red_holds_a_new_command_start_but_not_the_review_that_finishes` — `Bash command_run.py start --command fabrik-spec` → deny; `… --command fabrik-review-scoped` → allow; `… --command fabrik-review` → allow.
   - `test_wall_is_left_to_quota_stop` — `band == "WALL"` → the hook prints nothing on `Agent` (no double deny).
   - `test_fable_sessions_key_the_band_on_the_fable_window` — posture `band GREEN`, `band_fable RED`; transcript tail whose last assistant entry has `"model": "claude-fable-5-1"` → `Agent` denied; `"claude-opus-5"` → allowed; no `transcript_path` → allowed (fail-open) and the prompt line still shows `Fable <n>%`.
   - `test_session_model_reads_only_the_transcript_tail` — a 2 MiB transcript whose last assistant entry is within the final 64 KiB → model found; wall time of one hook run `< 0.5 s`.
   - `test_amber_is_said_once_per_band_change` — AMBER: first `PreToolUse` emits the `additionalContext` JSON with NO `permissionDecision`; second emits nothing; band → RED then denies `Agent` and writes the RED marker; a fresh sid emits the AMBER context again.
   - `test_malformed_payloads_never_block` — non-JSON, a JSON list, an empty object → rc 0, empty stdout (the `quota_stop` pass-2 class).
   - `test_install_adds_both_entries_once_and_preserves_every_other_key` — six tmp settings copies (three identical, one with `"model": "opus"`) → after `--install`: each has exactly one entry per event naming the basename, `model` preserved byte-for-byte, a `.backup.<ts>` beside each; a second `--install` changes nothing (md5 equal); `--check` exits 1 before and 0 after.
   - `test_dispatch_headroom_prefers_a_fresh_posture_band` — monkeypatch the subprocess output with a payload carrying a fresh RED posture while the picture's hottest is 60 → `quota()["band"] == "RED"`; stale posture → the picture's own band.
   - in `tests/test_quota_dashboard.py`, `test_the_board_renders_burn_and_wall_vs_reset_from_the_posture` — `_payload()` (`:50`) extended with `posture` → the two cells appear; without → `no reading`.
   Run `uv run pytest tests/test_quota_posture.py tests/test_quota_dashboard.py -k 'posture' -x --tb=short` → every grader RED for its own reason (paste into § Evidence).
3. Implement `scripts/sysadmin/quota_posture_hook.py` (stdlib only: `json`, `os`, `sys`, `time`, `re`, `pathlib`, `math`; `# AFTER-EDIT: tests/test_quota_posture.py | docs/workstation/hooks-index.md | docs/workstation/claude-account-rotation.md`), then `dispatch_headroom.quota()`, then the dashboard cells, then `_posture_hook_wiring_warnings` + the marker prune in `claude_rotate.py` (cp the twin).
4. Graders → GREEN; `uv run pytest tests/test_quota_posture.py tests/test_quota_dashboard.py tests/test_user_hook_gate.py tests/test_selfwatch_check.py tests/test_quota_stop_hook.py tests/test_claude_fleet.py -q --tb=short` (the neighbouring hook suites prove nothing regressed).
5. **Wire this box:** `python3 scripts/sysadmin/quota_posture_hook.py --install --check` (expect 6 × `MISSING`), then `--install` (6 backups written, per-file verdict), then `--check` → 0. Run the Claude-config DR backup named in `docs/workstation/hooks-index.md:95` (`dr_claude_backup.sh` — locate it with `find /opt/fabrik/scripts ~/.claude/bin -name 'dr_claude_backup.sh' 2>/dev/null`; if absent on this box, say so in the receipt and mail infra — it is their beat). Then the executable check of the real thing: open ONE new window (any repo — `/opt/fabrik-lib` is the deliberate choice, the sync-excluded repo that motivated the user-level pattern) and paste the first prompt's `QUOTA:` line into § Evidence verbatim.
6. Docs: `docs/workstation/hooks-index.md` § 2 table (`:102-104`) — two new rows (`UserPromptSubmit (user-level, every window)` and `PreToolUse (user-level, every window)`) naming the hook, the line, the hold, the fail-open bound, the `--install`/`--check` commands, and the tick's wiring warning; `docs/workstation/quota-dashboard.md` § Reading the board (`:75`) — the two new cells; `docs/workstation/claude-account-rotation.md` § `--status` — one sentence pointing at the hook rows in hooks-index (never a second description of the hook); `docs/workstation/claude-account-rotation.md` § Runbook (`:431`) — the wiring warning's remedy; CHANGELOG `### Added — quota_posture_hook.py: the QUOTA line on every prompt, the RED hold, forecast on the dashboard and the seat budget (2026-09-16)`. INDEX.md rows for `scripts/sysadmin/quota_posture_hook.py` and `tests/test_quota_posture.py` (INDEX lists tests today) — by the private-index recipe, placed where `docs_updater.py --check` expects them.
7. **Closing sequence (literal):** (a) the gate of step 4 → green; `python3 scripts/final_gate.py --json --check` read for `status` AND `skipped_checks`; (b) `python3 scripts/enforcement/check_doc_sync.py` + step 6; (c) **`/fabrik-review-scoped` on this phase's diff — BLOCKING, run to its coverage-adjudicated exit**: pin the diff with its md5; units = 3 (the hook, `dispatch_headroom`+dashboard, the installer/wiring); `dispatch_headroom.py --units 3 --risky 1 --mechanical 1`, stamp, dispatch exactly the printed mix in ONE message (Opus on the hook — the deny predicate, the run-record check, the transcript tail read, the fail-open keys; Sonnet breadth on the two readers and on the installer; Haiku on the grep-able class: every env read finite-guarded, every path from the two accessors); every finding FIXED with a grader or REFUTED; delta rounds under `--delta`; a fresh non-authoring seat confirms 0; (d) commit `-- scripts/sysadmin/quota_posture_hook.py scripts/sysadmin/dispatch_headroom.py scripts/sysadmin/quota_dashboard.py scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_quota_posture.py tests/test_quota_dashboard.py docs/workstation/hooks-index.md docs/workstation/quota-dashboard.md docs/workstation/claude-account-rotation.md` after `git diff HEAD -- <paths>`; CHANGELOG + INDEX by the private-index recipe; `Agent-Phase: C`; push; realign.

**Behavior Contract — Phase C**

| # | Given | When | Then | Grader |
|---|---|---|---|---|
| C1 | no file / a stale file | any prompt | one `posture unavailable (<reason>)` line; no hold | `test_prompt_line_says_unavailable_when_the_file_is_absent_or_stale` |
| C2 | a fresh GREEN posture | any prompt | the contract's line, byte for byte | `test_prompt_line_matches_the_contract_format_byte_for_byte` |
| C3 | RED, no live run | `Agent` (and `Workflow`, defensively) | DENY with band + forecast; every checkpoint tool allowed | `test_red_holds_agent_and_workflow_only_without_a_live_run` |
| C4 | RED, a live run record | `Agent` | ALLOW (the run keeps its seats) | same test |
| C5 | RED | `command_run.py start` for anything but the review family | DENY; the review family ALLOW | `test_red_holds_a_new_command_start_but_not_the_review_that_finishes` |
| C6 | WALL | `Agent` | silent — `quota_stop.py` owns the WALL | `test_wall_is_left_to_quota_stop` |
| C7 | `band_fable RED`, `band GREEN` | a Fable transcript / an Opus transcript / none | DENY / ALLOW / ALLOW + the line still shows Fable | `test_fable_sessions_key_the_band_on_the_fable_window` |
| C8 | a 2 MiB transcript | the hook runs | the model is read from the tail; `< 0.5 s` | `test_session_model_reads_only_the_transcript_tail` |
| C9 | AMBER, then RED, same sid | successive tool calls | the notice once per band; a fresh sid again | `test_amber_is_said_once_per_band_change` |
| C10 | garbage on stdin | the hook runs | rc 0, silent | `test_malformed_payloads_never_block` |
| C11 | six settings files, one drifted | `--install` twice, `--check` before/after | wired once, drift preserved, backups beside, idempotent, `--check` 1→0 | `test_install_adds_both_entries_once_and_preserves_every_other_key` |
| C12 | a fresh posture in `--status --json` | `dispatch_headroom.quota()` | the posture's band; stale ⇒ the picture's | `test_dispatch_headroom_prefers_a_fresh_posture_band` |
| C13 | a payload with/without `posture` | the board renders | burn + wall-vs-reset cells / `no reading` | `test_the_board_renders_burn_and_wall_vs_reset_from_the_posture` |
| C14 | a settings file without the hook | the tick runs | one warning line naming `<n> of 6` and the remedy | `test_the_tick_warns_when_the_posture_hook_is_not_wired` (in `tests/test_claude_fleet.py`, six tmp files via `QUOTA_POSTURE_SETTINGS`) |

## Phase D — Finish

Steps:
1. **One heavy `/fabrik-review` over the WHOLE-plan diff** (base = the commit before Phase A; pin `<scratch>/whole-plan.diff` + md5). Partition BY FILE (D-207): `dispatch_headroom.py --slices opus=2,sonnet=3,haiku=1` — Opus on `quota_posture_hook.py` and the `claude_rotate.py` writer (record/file format + a hook that denies = the risky units), Sonnet on `dispatch_headroom.py`, `quota_dashboard.py`, the three contracts + docs, and the tests, Haiku on the inventory class (every `path:line` in the receipt re-derived). Brief the cross-phase net: (1) the contract sentence vs the line the hook actually prints (byte identity is graded, MEANING is this seat's); (2) the two band computations (`_quota_posture` vs `dispatch_headroom.quota()` fallback) agree on every boundary; (3) the WALL boundary — no state where both `quota_stop.py` and this hook deny, none where neither does while the stamp stands; (4) the fail-open table in § Global Constraints against the graders that exist now; (5) the sync blast radius — the template sentences reached every synced repo and NOTHING under `scripts/sysadmin/` did. Receipt at `docs/development/reviews/2026-09-16-plan-1-quota-posture-review.md` with the verbatim `final_gate.py --json --check` embed and a per-phase verdict; every finding FIXED (grader red→green) or REFUTED; closes on a fresh non-authoring delta seat confirming 0 (D-206) or the D-252 scope-growth stop with residue named in `docs/STRATEGIC_BACKLOG.md`.
2. Three-way identity: `uv run pytest tests/test_governance_template_split.py -q` green; `check_corpus_weight.py --check --strict`.
3. Distribution: for every governance-surface commit in this plan, check whether it was porcelain (post-commit sync fired — read its output) or plumbing (no hook) — a plumbing one is distributed NOW with `python3 scripts/sync_enforcement_to_projects.py --force`; verify with `command grep -l 'The `QUOTA:` line (D-269)' /opt/*/CLAUDE.md | wc -l` against the sync's own project count, and `command grep -L` for the stragglers.
4. Ledger + docs: D-269 (the received decisions) was minted with this plan's own commit; the Finish adds ONE new row (mint with `python3 scripts/decisions.py --next-id .` at write time — re-mint, never reuse a number read earlier) recording what was BUILT and WHERE (the file, the hook, the six wired settings files, the phase commits), `CLASS: REVERSIBLE` (each piece removable), with the Cobra line and the fire rates as measured at execution; CHANGELOG (Finish entry); `docs/development/PLANS.md` via `python3 scripts/docs_updater.py` (the AUTO-GENERATED block); `docs/LESSONS_LEARNT.md` only if the run produced one (else `none` in the block); all four by the private-index recipe with the gating assertion.
5. `/fabrik-docs-review` over the docs this plan touched (`hooks-index.md`, `claude-account-rotation.md`, `quota-dashboard.md`, the three contracts, CHANGELOG, the D-row, the receipt) — every claim resolves to shipped code at `path:line` or an executed output; fix in-run.
6. `python3 scripts/final_gate.py --json --check` → `status: success` (read `skipped_checks`); Status → EXECUTED with the phase commits named; the lock released and the plan archived per `/fabrik-execute-plan` § Finish; commit + push; the run record closed by name with its four-field `FEEDBACK:` line.

**Behavior Contract — Finish**

| # | Given | When | Then | Proof |
|---|---|---|---|---|
| D1 | the whole-plan diff | the heavy review runs | receipt with the verbatim gate embed + per-phase verdict; 0 confirmed on a fresh delta seat | the receipt file + `check_review_coverage.py` green |
| D2 | 45+ synced repos | the template commit landed | every `/opt/*/CLAUDE.md` synced carries the D-269 sentences | the `grep -l | wc -l` count equals the sync's count; `grep -L` names none |
| D3 | a new window in `/opt/fabrik-lib` | the first prompt | the `QUOTA:` line is the first injected line | pasted verbatim in the receipt |

## File Scope (owned paths)

- `docs/development/plans/2026-09-16-plan-1-quota-posture.md`
- `.fabrik/plan-locks/2026-09-16-plan-1-quota-posture.json`
- `docs/development/reviews/2026-09-16-plan-1-quota-posture-review.md`
- `scripts/sysadmin/claude_rotate.py`
- `scripts/aro-wake/claude_rotate.py`
- `scripts/sysadmin/quota_posture_hook.py`
- `scripts/sysadmin/dispatch_headroom.py`
- `scripts/sysadmin/quota_dashboard.py`
- `tests/test_claude_fleet.py`
- `tests/test_quota_posture.py`
- `tests/test_quota_dashboard.py`
- `tests/test_governance_template_split.py`
- `CLAUDE.md`
- `templates/governance/CLAUDE.md`
- `docs/workstation/claude-account-rotation.md`
- `docs/workstation/hooks-index.md`
- `docs/workstation/quota-dashboard.md`
- `docs/development/PLANS.md`

Excluded by the spine grammar (shared-append governance files, outside every plan lock — `check_plan_tickets.py::GOVERNANCE_FILES`): `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md`, `docs/FEATURES.md`, `docs/LESSONS_LEARNT.md`, `docs/README.md`, `docs/STRATEGIC_BACKLOG.md`. Outside this repo and therefore not ownable here, edited on the operator's explicit instruction (I6): `/opt/fabrik-lib/CLAUDE.md`. Outside any repo: the six user-level `settings.json` files (backed up beside themselves by the installer), `~/.claude/state/quota-posture.json`, `~/.claude/state/quota-posture-notified/`. Serialization points with the active `2026-09-09-plan-1-review-convergence-redesign` lock: `CLAUDE.md`, `templates/governance/CLAUDE.md`, `scripts/sysadmin/dispatch_headroom.py`, `scripts/sysadmin/quota_dashboard.py`, `docs/workstation/claude-account-rotation.md` — see R-open-1.

## Evidence

Every block below was executed in this session on 2026-09-16 (the box's live tree at `b0e513bc`); line anchors drift — grep the symbol.

**E1 — the tick row site and what is in scope for the writer** (`scripts/sysadmin/claude_rotate.py:4966-4993`, read):
```
    _active_walled, _active_row = _active_account_walled(accounts, threshold)
    if _active_row is not None and isinstance(_active_row.get("five_hour"), dict):
        ...
            _wk_window = _active_row.get("seven_day")
            _wk = _wk_window.get("utilization") if isinstance(_wk_window, dict) else None
            if isinstance(_wk, (int, float)) and not isinstance(_wk, bool):
                _row["weekly_pct"] = float(_wk)
            _ledger_append(_row)
    _fleet_active_wall_advisory(accounts, now, threshold)
    for warn in _fleet_row_warnings(accounts):
        print(warn)
```

**E2 — the picture's keys** (`:3891-3902`): `now · active · accounts · queue · next_relief{epoch,email,window} · hold · last_flip · thresholds{trip, drain_band}`; `_fleet_picture` reads `thr = _rotate_threshold()` and `band = _env_float("ROTATE_DRAIN_THRESHOLD", 85.0)` (`:3782-3783`); `_urgent_drain_pct()` returns `_env_float("ROTATE_URGENT_DRAIN_PCT", 90.0)` (`:4576`).

**E3 — the Fable window is already captured** (`:3398-3418`):
```
            if not isinstance(lim, dict) or lim.get("kind") != "weekly_scoped":
                continue
            scope = lim.get("scope")
            model = scope.get("model") if isinstance(scope, dict) else None
            name = model.get("display_name") if isinstance(model, dict) else None
            pct = lim.get("percent")
            if isinstance(name, str) and name and isinstance(pct, (int, float)):
                models[name] = {"utilization": float(pct), "resets_at_epoch": _iso_to_epoch(lim.get("resets_at"))}
```
and the dashboard reads it as `(acct.get("model_windows") or {}).get("Fable")` (`quota_dashboard.py:798`).

**E4 — fire rates, from the producing tool's own totals:**
```
tick rows with numeric pct: 2361 · >=85: 141 (6.0%) · >=90: 111 (4.7%) · >=98: 0 · rows carrying weekly_pct: 48
```

**E5 — the fleet at write time** (`claude_rotate.py --status`):
```
fleet: 5 dir(s) · 5 account(s) · active: ozgurbasak
picture: hold none
queue:   #1 ozgurbasak@ocoron.com (active 38%/65%) · #2 can@ocoron.com (eligible 0%/82%) · #3 ob@ocoron.com (eligible 11%/2%) · #4 sarp@ocoron.com (cap-walled 0%/97% returns Thu 10:59) · #5 mob@oc…
next relief: sarp@ocoron.com at Thu 10:59 (weekly window)
last flip: Wed 15:40 can -> ozgurbasak (relief)
```

**E6 — the six settings files and their drift:**
```
can: /home/ozgur/.claude-fleet/can/settings.json 23144624
mob: /home/ozgur/.claude-fleet/mob/settings.json f025e232
ob: /home/ozgur/.claude-fleet/ob/settings.json 23144624
ozgurbasak: /home/ozgur/.claude-fleet/ozgurbasak/settings.json 23144624
sarp: /home/ozgur/.claude-fleet/sarp/settings.json 75f1466f
mob differs from can in keys: ['model']
sarp differs from can in keys: ['model']
```
and every one of them wires `selfwatch_check.py` (UserPromptSubmit, timeout 10) and `user_hook_gate.py … quota_stop.py` (PreToolUse `.*`, timeout 10) — the shape the installer copies.

**E7 — lock overlap** (`.fabrik/plan-locks/*.json` parsed): `2026-09-09-plan-1-review-convergence-redesign` status `active`, 34 owned, overlap `['CLAUDE.md', 'docs/workstation/claude-account-rotation.md', 'scripts/sysadmin/dispatch_headroom.py', 'scripts/sysadmin/quota_dashboard.py', 'templates/governance/CLAUDE.md']`; its plan reads `Status: IN-PROGRESS`. `2026-09-05-plan-1-windowed-cost-sidecar` active, overlap `[]`.

**E8 — the three contracts today:** `CLAUDE.md:385` and `templates/governance/CLAUDE.md:393` both read `**under 85 — GREEN:** work normally. **85 to under 90 —` …; `/opt/fabrik-lib/CLAUDE.md:208` reads `**85-90 — AMBER: …** **90+ with NO eligible successor — RED:** …` — the D-264 text.

**E9 — hook payload shape and the model path:** `tests/test_quota_stop_hook.py:85-100` drive the hook with `{"tool_name": …, "tool_input": {…}}` and `quota_stop.py:563-590` reads `tool_name`, `tool_input.command`, `session_id`; `mcp_watch.py:350` reads `payload.get("transcript_path")`; `command_run.py:2001` reads `m = msg.get("model")` from the transcript's assistant entries. No hook fixture on the box carries a `model` field (grepped `"model"` across `tests/test_quota_stop_hook.py tests/test_final_gate_stop_hook.py tests/test_user_hook_gate.py` → none). Fable's limit semantics: support.claude.com articles 15424964 and 9797557, fetched 2026-09-16 by the grounding seat (quoted in § What we already agreed).

**E10 — the MUST-READ set** (`review_rubric.py --changed <File Scope>`): FLOOR `core/10-python.md` + 12-FACTOR; MATCHED `core/40-documentation.md` (hit: `CLAUDE.md`, the two workstation docs), `core/45-testing-strategy.md` (hit: the three test files), `core/58-resilience.md` (hit: `dispatch_headroom.py`).

## Self-audit

- **Grounding passes:** every symbol in § Context Ledger was opened this session (`sed -n` / `grep -n` on the live tree); the archived kaizen plan (`docs/development/plans/archived/2026-09-14-plan-1-kaizen-observe-and-act.md`) was read as the shape template; the methodology (`~/.claude/commands/fabrik-plan-after-chat.md`, 1,038 lines) read in full; 26 ACTIVE packs listed by `select_rules.py`, the MUST-READ subset read and quoted; three native `fabrik-researcher` seats dispatched (stamped 3: Opus on the hook I/O contract, Sonnet on the transcript model path, Sonnet on the Fable limit) — all three returned before this draft closed; their verdicts are quoted in § What we already agreed and resolved R4, R6, R7, R8; one refuted my own draft (`Workflow` as a tool name) and the contract sentence was corrected before any file carried it.
- **(a) Coverage walk of § Intake Inventory:** I1 → C (line on every prompt, box-level) · I2 → B (burn) · I3 → B (forecast) · I4 → A (contract) + C (advise/hold) · I5 → B (window) + C (transcript model) + A (sentence) · I6 → A (three files, fabrik-lib first) · I7 → this plan's shape · I8 → § Global Constraints. No gap found.
- **(b) Cross-phase signature consistency:** `_quota_posture` / `_write_quota_posture` / `_read_quota_posture` (B) are consumed by `--status` (B) and, through the `posture` key, by `dispatch_headroom.quota()` and the dashboard (C); the hook (C) reads the schema keys `ts`, `active.windows.{five_hour,seven_day,fable}.{utilization,verdict,minutes_to_wall,minutes_to_reset,burn_per_min}`, `active.band`, `active.band_fable`, `active.slug`, `fleet.successor` — every one is produced in B's schema; the line format is fixed in A's sentences and asserted byte-for-byte by C2; `QUOTA_POSTURE_STALE_S` is read only by C; `QUOTA_POSTURE_SETTINGS` (the installer's test override) is named in C14 and in the installer; the marker directory name `quota-posture-notified` appears in C's hook and in B's tick prune — same string.
- **Fixed point:** not claimed — this is a DRAFT; `/fabrik-plan-review` runs the first convergence round.

## Residual unknowns

**Resolved this session**
- R1 — "does the tick already capture Fable?" → yes, `model_windows.<display_name>` (E3); today's readings can 16 / mob 100 / ob 0 / ozgurbasak 32 / sarp 58.
- R2 — "is `scripts/sysadmin/` synced?" → no (E10's manifest grep → 0); the hook is box-local by placement.
- R3 — "one settings file or many?" → six independent files, drifting in `model` (E6); per-file idempotent install, never `--sync-shared`.
- R4 — "is Fable's weekly a separate reset clock?" → no: a ceiling inside the shared weekly pool, reported as its own percentage (grounding seat, live sources); the contract sentence avoids claiming a separate clock.
- R5 — "which lock owns what?" → E7; the operator's override covers the CLAUDE.md bullet explicitly and the work stream by their words; stated, not assumed silently.
- R6 — "can `PreToolUse` inject context without denying?" → yes, `additionalContext` (live docs, verbatim in § What we already agreed); one hook carries both the AMBER notice and the RED hold; no `PostToolUse` wiring.
- R7 — "does the hook payload carry the model?" → no, except optionally on `SessionStart` (and stale after `/model`); the transcript tail read is the path, grounded on a real 261,702-line transcript (last assistant entry 20 lines from EOF).
- R8 — "is `Workflow` a matchable tool?" → no (2 occurrences on the full docs page, both task-type labels); the contract promises `Agent` only.

**Still open — each with its named resolution step**
- R-open-1 — **the five lock-owned paths.** Resolution: at `/fabrik-execute-plan` start, the operator either confirms the override for this plan's five paths in one line, or infra releases `2026-09-09-plan-1-review-convergence-redesign`'s lock (its plan is IN-PROGRESS); until one happens the executor's overlap refusal is CORRECT and the phases that touch those files (A, C) wait. Ground (3) of the operator-decision bar: the operator already owns this decision this turn.
- R-open-2 — **the transcript lags the in-memory conversation** (docs: "written asynchronously"), so the first tool call after a `/model` switch may read the previous model. Resolution: accepted and written in the hook's docstring; if a live case bites, the backlog item is a `PostModelSwitch` hook writing `<state>/session-model/<sid>` that the hook reads first — recorded in `docs/STRATEGIC_BACKLOG.md` at Finish, not built here.
- R-open-3 — **a live CLI may rewrite its `settings.json` from memory and drop the entry** (hooks-index `:93`: "the CLI writes config back"). Resolution: the tick's wiring warning (C14) makes a dropped entry visible within 5 minutes and names the remedy; `--check` is the executable probe; if it fires in practice, the receipt records it and the daily-cron re-assert becomes a line handed to the operator.
- R-open-4 — **`check_corpus_weight.py --check --strict` on the twins' growth.** Resolution: Phase A step 5 reads the check's own docstring for the justification grammar; D-265 grew the twins by +507 B under the same check and passed with its D-row justification.

## Pass Ledger

| Pass | Reader | Pinned md5 | Candidates | Confirmed | Fixed | Refuted | Notes |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | filled by `/fabrik-plan-review` |

## Coverage Checklist

| Class | Verdict |
|---|---|
| Declared fail-open per key (absent · unreadable · stale · transcript · stdin) with a grader each | OPEN — Phase C C1/C7/C10, Phase B B8 |
| The WALL boundary: never a double deny, never a gap while the stamp stands | OPEN — Phase C C6, Finish D1 brief (3) |
| Band boundaries identical in the writer and in `dispatch_headroom.quota()`'s fallback | OPEN — Phase B B5, Phase C C12, Finish D1 brief (2) |
| Record/file format: atomic write, schema versioned, `.tmp` never left behind | OPEN — Phase B B1 |
| Timeouts: no network in the hook; the transcript read bounded to 64 KiB; the subprocess keeps `timeout=60` | OPEN — Phase C C8 |
| Fleet-synced paths untouched (`.claude/hooks/`, `scripts/enforcement/`); the template sentences distributed and verified by count | OPEN — Phase A step 6, Finish D2 |
| Twin byte-identity after every `claude_rotate.py` edit | OPEN — Phase B B10 |
| UTC/epoch discipline (`10-python.md:219`) | OPEN — Phase B schema (epoch floats only) |
| Doc truth across the three contracts, hooks-index, the rotation doc, the dashboard doc, CHANGELOG, the D-row | OPEN — Finish step 5 (`/fabrik-docs-review`) |
| fail-open on a malformed row | OPEN — Phase C C10 (stdin), Phase B (a corrupt previous posture file ⇒ `prev = None`, ring restarts) |
| cost/quota accounting | OPEN — the hook costs no API call; seats per phase bounded by `dispatch_headroom.py`; fire rates stated (E4) |
| boundary/sentinel | OPEN — Phase B B5 (84.9/85/89.9/90), Phase C C9 (once per band) |
| behavior-without-a-test | OPEN — every Behavior Contract row names its grader; the review confirms none is orphaned |

The rubric this plan's reviews inject into every seat brief, run on the plan's own File Scope:

```bash
python3 scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py scripts/sysadmin/quota_posture_hook.py scripts/sysadmin/dispatch_headroom.py scripts/sysadmin/quota_dashboard.py tests/test_claude_fleet.py tests/test_quota_posture.py tests/test_governance_template_split.py tests/test_quota_dashboard.py CLAUDE.md templates/governance/CLAUDE.md docs/workstation/claude-account-rotation.md docs/workstation/hooks-index.md docs/workstation/quota-dashboard.md
```

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)
### core/10-python.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/40-documentation.md  (hit: CLAUDE.md, docs/workstation/claude-account-rotation.md, docs/workstation/hooks-index.md)
### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py, tests/test_governance_template_split.py, tests/test_quota_dashboard.py)
### core/58-resilience.md  (hit: scripts/sysadmin/dispatch_headroom.py)
```
