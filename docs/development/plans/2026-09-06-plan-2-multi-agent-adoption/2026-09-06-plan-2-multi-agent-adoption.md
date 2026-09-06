# Multi-agent adoption for existing projects — merge owner, work-item ownership, `--adopt`, two advisories

Status: IN-PROGRESS (2026-09-06 — /fabrik-execute-plan dispatcher; was CONVERGED at 231757fb)
**Owner:** infra
Spec: docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md (CONVERGED 7d8b3dbe, approved D-155; ruling D-154; profile D-153)

## Goal

An existing repo with several windows gets, in one operator-worded run, a declared merge owner and an owner on every open work item — and stays that way because the surfaces that show ownership are regenerated and checked, never hand-kept; a single-window repo sees nothing new.

## What we already agreed (from the spec + this conversation)

- One master per repo: *"existing agents must assign one agent as master"* — the merge owner, declared by ONE ledger row (`MERGE OWNER: <name>`) and printed by the PLANS block header (D1 → T01, T02a).
- Responsibility by WORK ITEM, never code area — the operator's accepted correction, D-154 (D2 → T02a/T02b).
- The adoption step is a script flag, not a new command (D2 → T02a/T02b); it refuses on a single-session repo without `--single-window`.
- Two advisories, never blocks, that fire only at ≥2 live sessions per checkout — the `/proc` scan, NOT `git worktree list` (28 of 29 seo worktrees are subagent residue) (D3 → T03, D5 → T04).
- `/fabrik-vision` EXISTING reads PLANS.md + STRATEGIC_BACKLOG.md; the epic path mints the same merge-owner row (D4 → T05).
- The scaffolder seeds the PLANS markers so new repos are born with the surface (T06); today the block is present in 0 of 41 projects.
- The hub is outside the worktree model — its three sessions never see the SessionStart line (T04's hub suppression).
- No new dependency; all BUILD (fabrik-lib verdict in the spec); no data contract, no UI; the real repos are adopted on the operator's word per repo, never by this plan.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "approved the design … on approval, /fabrik-plan-after-chat" — the spec's five deltas D1–D5 | IN | T01–T05 (one delta each, T02 split a/b) |
| I2 | spec I15 / § What exists today: the PLANS block in 0 of 41 projects; the scaffold seeds no markers | IN | T02a (a), T06 (1) |
| I3 | spec V4: the fire-rate proof over the 45 sync targets before the sync distributes | IN | T06 (2) |
| I4 | spec § Documentation landing sites: operating-model doc, hooks-index, governance template, CHANGELOG, D-row | IN | T04 (hooks-index), T06 (3), Deltas |
| I5 | spec § Lifecycle: real repos adopted on the operator's word per repo | OUT-OF-SCOPE — not a build step; the operator runs `--adopt` per repo after T06 merges (named in § Residual unknowns as the hand-off) | § Residual unknowns |
| I6 | the D-153 machinery report (spec § Machinery report) | OUT-OF-SCOPE — delivered in the spec; this plan adds its own numbers to the receipt (T06) | T06 receipt |
| I7 | "headless: no data contract, no UI" | IN | § Context Ledger (no `docs/data-contract.md`, no `docs/ui-design.md`) |

Intake: 7 items — 5 IN, 2 OUT-OF-SCOPE (I5, I6 — each named), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | `decisions.py --merge-owner` read | — | ⚡ | ✅ | branch head b7ffb88a; merged 2026-09-06 |
| T02a | `--adopt` core: markers, owners, ledger row, header | — | ⚡ | ✅ | branch head 9607384f; merged 2026-09-06 |
| T02b | `--adopt` backlog tagging, three shapes | T02a | ⛓️ | ✅ | branch head 7a4526e0; merged 2026-09-06 |
| T03 | `--check` advisory at ≥2 sessions (+ `advisory=True` at the gate call) | T02b | ⛓️ | ✅ | branch head 34ed7a86; merged 2026-09-06 |
| T04 | SessionStart advisory (hook) | — | ⚡ | ✅ | branch head d92888e8; merged 2026-09-06 |
| T05 | vision reads the work stores; epics-review mints the row | — | ⚡ | ✅ | branch head 4e6c3435; merged 2026-09-06 |
| T06 | Integration: scaffold markers, fire-rate proof, docs, whole-plan gate | T01, T03, T04, T05 | ⛓️ | ✅ | branch head 56b2d231; merged 2026-09-06 |

## Merge Order

1. T01
2. T02a
3. T02b
4. T03
5. T04
6. T05
7. T06

Serialized: scripts/docs_updater.py — T02a, T02b, T03 (Depends chain; one file, three tickets, in this order)
Serialized: tests/test_docs_updater_adopt.py — T02a, T02b, T03

## Interfaces

- **T01 → T02a (shared grammar, no import):** `MERGE_OWNER_RE = re.compile(r"^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*)", re.I)` applied to the stripped `what` cell (cells[3]); LAST match wins. Seam test: T02a's `read_merge_owner()` test and T01's `--merge-owner` test share one fixture ledger text (copied verbatim into both test files) and must agree on `beta`. Consumer: T02a (`tests/test_docs_updater_adopt.py`).
- **T02a → T02b:** `--adopt` runs T02b's backlog step after (b) and before (d); T02b's classifier `classify_backlog_row(line, header_cells) -> "table-tag"|"table-item"|"bullet"|"skip"` is also T03's untagged-row source. Consumer: T02b, T03.
- **T02a → T03:** `count_sessions_sharing(cwd) -> int` and `read_merge_owner() -> tuple[str,str] | None`. Consumer: T03 (`validate_ownership_advisory`).
- **T02a → T04 (copy, not import):** the `/proc` scan semantics — `<proc_root>/<pid>/comm == "claude"`, `cwd` symlink resolved, unreadable/vanished skipped — duplicated in the hook by design (hooks are self-contained; the hook reads `proc_root` from `FABRIK_PROC_ROOT`, the script takes it as a parameter). Seam: both tests build the SAME fake proc tree shape (a shared helper is not possible across the two test files without a conftest — T04 copies T02a's 12-line builder verbatim) and assert the same count.
- **T02a → T05:** the row grammar `MERGE OWNER: <name>` and `decisions.py --merge-owner`'s `UNDECLARED` exit 3 (T01). Consumer: the epics-review text (T05).
- **T02a → T06:** the marker pair + `## Ownership (auto-generated)` heading the scaffold literal must reproduce byte-for-byte. Consumer: T06 (`tests/test_scaffold_doc_seeding.py`).

## Behavior Contract

- **Given** a ledger whose last matching row's `what` cell is `**MERGE OWNER: beta** — …` and an earlier row `MERGE OWNER: alpha`, **When** `decisions.py --merge-owner <repo>` runs, **Then** it prints `beta` and exits 0 — the last row wins and leading `**` is stripped (scripts/decisions.py:82)
- **Given** a ledger with rows but none opening with `MERGE OWNER:` (a `what` cell that merely CONTAINS the phrase mid-sentence does not match), **When** `--merge-owner` runs, **Then** it prints `UNDECLARED` and exits 3 (scripts/decisions.py:140)
- **Given** a repo path whose `docs/DECISIONS.md` cannot be read, **When** `--merge-owner` runs, **Then** it writes the same `decisions: cannot read …` stderr line `_next_id` writes and exits 1 (scripts/decisions.py:159)
- **Given** a scratch repo (PROJECT_ROOT monkeypatched) with a marker-less PLANS.md, two open plans with no Owner line, one EXECUTED plan, and a ledger with no `MERGE OWNER:` row, **When** `--adopt alpha,beta --single-window` runs, **Then** PLANS.md gains the markers and a v2 block whose second header line reads `<!-- Merge owner: alpha | source: D-NNN -->`, the two open plans carry `**Owner:** alpha` and `**Owner:** beta` on the line after their H1, the EXECUTED plan is untouched, exactly one `MERGE OWNER: alpha` row was appended with id max+1, and the printed table has one row per change (scripts/docs_updater.py:1046)
- **Given** the state after that run, **When** `--adopt alpha,beta --single-window` runs again, **Then** every touched file is byte-identical and the output is `(nothing to adopt)` (scripts/docs_updater.py:1015)
- **Given** a ledger already carrying `MERGE OWNER: alpha`, **When** `--adopt gamma --single-window` runs, **Then** NO new ledger row is written, the existing row is untouched, and the header comment still names `alpha` — a change of merge owner is a hand-minted superseding row, never `--adopt`'s write (scripts/decisions.py:82)
- **Given** a fake proc tree with ONE `claude` process whose cwd is the repo and no `--single-window`, **When** `--adopt alpha` runs with `proc_root` pointed at it, **Then** it exits 2 with one stderr line naming the count and the override, and no file changes; with two such processes it proceeds (scripts/docs_updater.py:1550)
- **Given** a ledger row whose `what` opens with `**MERGE OWNER: alpha**`, **When** `read_merge_owner()` runs, **Then** it returns `("alpha", "D-NNN")` (scripts/docs_updater.py:834)
- **Given** an epics dir with two frontmatter epics lacking `owner:`, **When** `--adopt alpha,beta --single-window` runs, **Then** `epic_order.py --assign alpha,beta` was invoked once and the table carries an `epic_order` row (scripts/epic_order.py:668)
- **Given** the live hub tree, **When** `generate_plans_table()` runs, **Then** its second line starts with `<!-- Merge owner:` and `validate_plans_indexed()` against the pre-change block reports the stale finding once, and `--sync` clears it (scripts/docs_updater.py:1066)
- **Given** a backlog with a hub-shaped table (`Tag` column, one empty tag cell), a project-shaped table (no `Tag` column, one untagged row), and three bullet rows (`- `, `- [ ] `, `- [x] `), **When** `--adopt alpha,beta --single-window` runs, **Then** the empty tag cell reads `` `[alpha]` ``, the project row's second cell starts with `[beta] `, and the bullets read `- [alpha] …`, `- [ ] [beta] …`, `- [x] [alpha] …` — round-robin across all five in file order (docs/STRATEGIC_BACKLOG.md:19)
- **Given** a row already carrying `[infra]`, the legend table, a header row, and a fenced block containing `- item`, **When** `--adopt` runs, **Then** none of them changes (scripts/docs_updater.py:946)
- **Given** the state after one run, **When** it runs again, **Then** STRATEGIC_BACKLOG.md is byte-identical (scripts/docs_updater.py:1046)
- **Given** no STRATEGIC_BACKLOG.md, **When** `--adopt` runs, **Then** it succeeds with no backlog rows in the report (scripts/docs_updater.py:1550)
- **Given** a fake proc tree with two `claude` processes in the repo (`proc_root`) and a repo with no `MERGE OWNER:` row, **When** `docs_updater.py --check` runs, **Then** stdout carries exactly one `ADVISORY:` line naming `2 sessions` and `--adopt`, and the exit code equals the run's exit code with the advisory removed (scripts/docs_updater.py:1357)
- **Given** one process in the fake proc tree, or two processes but `scripts/fabrik_synced_manifest.py` present (hub identity), **When** `--check` runs, **Then** no `ADVISORY:` line is printed (scripts/docs_updater.py:1357)
- **Given** 2 sessions, a declared merge owner, every open plan owned and every backlog row tagged, **When** `--check` runs, **Then** no `ADVISORY:` line is printed — parametrized over the four combinations of (sessions ∈ {1,2}) × (ownership complete/incomplete), only (2, incomplete) prints (scripts/docs_updater.py:1066)
- **Given** `run_optional_check` driven against a stub script that prints an `ADVISORY:` line and exits 0, **When** it is called with `advisory=True`, **Then** the returned message carries the line and without the keyword it does not — and the `Documentation Drift` call carries `advisory=True` (scripts/final_gate.py:1884)
- **Given** the hook run through the existing `_run` harness with `FABRIK_PROC_ROOT` pointing at a fake tree holding three `claude` entries whose `cwd` symlinks resolve to a non-hub scratch cwd (plus one `bash` entry and one entry with no `cwd`), **When** it runs, **Then** the ORIENT block carries exactly one line starting `- ⚠️ **3 sessions share this main checkout.**` placed after the identity line (.claude/hooks/session_orient.py:294)
- **Given** a fake tree with one `claude` entry in that cwd, **When** it runs, **Then** the block carries no `sessions share` line and is byte-identical to today's output for that cwd (.claude/hooks/session_orient.py:287)
- **Given** three entries and a cwd whose path contains `/.claude/worktrees/`, or a cwd carrying `scripts/fabrik_synced_manifest.py` (hub identity), **When** it runs, **Then** no `sessions share` line is printed (.claude/hooks/session_orient.py:139)
- **Given** no `FABRIK_PROC_ROOT` and the live `/proc`, **When** `_sessions_line` runs on this box, **Then** it returns within 200 ms and never raises even when an entry disappears mid-scan (a fake tree entry whose `cwd` symlink dangles) (.claude/hooks/session_orient.py:211)
- **Given** the vision source, **When** `tests/test_vision_reads_work_stores.py` greps its EXISTING read list, **Then** `docs/development/PLANS.md` and `docs/STRATEGIC_BACKLOG.md` both appear between the `EXISTING mode only` bullet and the fabrik-lib bullet, and the epic-seed paragraph names `owner:` inheritance from a `[name]` tag (commands/_sources/fabrik-vision.md:63)
- **Given** the epics-review source, **When** the test greps § Step 1.5, **Then** it names `decisions.py --merge-owner` and the `MERGE OWNER:` row mint (commands/_sources/fabrik-epics-review.md:138)
- **Given** both sources edited, **When** `assemble_commands.py --check` and `check_command_corpus.py` run from the main checkout, **Then** both exit 0 and every composed skill description stays ≤ 1024 chars (commands/assemble_commands.py:1)
- **Given** a fresh `_scaffold_shared` into a scratch dir, **When** it finishes, **Then** `docs/development/PLANS.md` carries the `AUTO-GENERATED:PLANS` markers below its hand table and `docs_updater.py --sync` (PROJECT_ROOT pointed at it) regenerates the block in place (src/fabrik/scaffold.py:1437)
- **Given** the 45 sync targets read-only, **When** the fire-rate proof runs, **Then** every repo the advisory would fire in has ≥2 live sessions and no single-session repo fires — recorded as a table in the receipt with its denominator (scripts/docs_updater.py:1357)
- **Given** the operating-model doc and the governance template after this ticket, **When** grepped, **Then** neither carries "tail sweep" and both name `--adopt` (docs/reference/multi-agent-operating-model.md:70)

## Global Constraints

- Shared tree, three hub sessions: every commit is a private-index commit of explicitly named paths; never `git add -A`, `--amend`, stash; fetch + fast-forward before push; never `--force`.
- `scripts/docs_updater.py` (RUN_SCRIPT) and `.claude/hooks/session_orient.py` (AGENT_HOOK_FILES) are FLEET-SYNCED: correct for a project with no PLANS.md, no backlog, no epics, one session; stdlib only; a commit-tree commit skips the post-commit sync — run `python3 scripts/sync_enforcement_to_projects.py --force` after T06 merges.
- Commands render from the MAIN checkout only, order render → `--check` → commit (the renderer prunes when run from a worktree).
- Advisory, never block: no new file under `scripts/enforcement/`; `--check`'s exit code is unchanged by the advisory; `final_gate.py:1884` is `run_optional_check`, whose stdout is DROPPED on exit 0 unless `advisory=True` (`final_gate.py:347-365`) — T03 adds that one keyword and nothing else there; the hub never gets either advisory.
- Hub identity = `scripts/fabrik_synced_manifest.py` present; the hub never gets the SessionStart line.
- Never-Route: scripts/enforcement/
- Never-Route: scripts/final_gate.py
- 12-Factor non-negotiables (binding on every ticket): logs = unbuffered to **stdout only, never a logfile** (XI) · migrations = a one-off process against the deployed release, never from `lifespan`/startup (XII) · same backing services in dev/test/prod — no SQLite-for-Postgres, no `fakeredis` (X) · no sticky sessions (VI) · no daemonizing / PID files (VIII) · workers requeue in-flight jobs on SIGTERM, jobs idempotent (IX) · releases immutable, never hot-patch a container (V) · config = granular env vars, no grouped env sets, no secrets in code (III) · shelled-out binaries installed + pinned in the Dockerfile (II). None of the tickets ships a service; the rows that bind here are XI (the hook and the script print to stdout/stderr only) and III (no constants beyond the regex).
- `datetime.now(UTC)`, never `utcnow()` (core/10-python.md:219) for the ledger row's date and the block stamp.
- Every test watched RED first; a mutation asserted on disk before it is trusted.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED: scripts/, hooks) | `uv` only, no new dependency (:21); `datetime.now(UTC)` (:219); no logfile writes (:291); ruff rule-sets ASYNC/B/S (:245) | the four rows in § Constraints digest |
| `.windsurf/rules/core/40-documentation.md` (MATCHED: commands/_sources) | `Agent-Role: primary` trailers (:458); one CHANGELOG entry per code-shipping ticket (:480) | § Constraints digest |
| `.windsurf/rules/core/45-testing-strategy.md` | one test per user-observable behaviour, red-first | T02a/T04 Behavior Contracts |
| FLOOR packs 35 / 25 / 30 | no auth, no DB, no service in this plan — unconstrained except "ZERO secrets/constants in code" (35) | § Constraints digest |
| fabrik-lib (README module table) | nothing to vendor: no module covers a decision ledger, markdown ownership stamps, or a `/proc` scan (spec § fabrik-lib verdict) — BUILD, not a candidate (Fabrik-specific grammar) | /opt/fabrik-lib/README.md |
| `agents-fabrik.md` | no infra invariant touched (no compose, no port, no DB) | — |
| `specs/services/*.yaml` `shape:` | none — the hub has no project.yaml; nothing deploys | — |
| `docs/data-contract.md` / `docs/ui-design.md` | absent by design (headless, no persistence) | — |
| `scripts/docs_updater.py` | `_OWNER_LINE_RE`/`NO_OWNER`/`parse_plan_owner` (:832-853); `parse_plan_status` (:856); `_PLANS_PHASE_NOTE` (:924); `_cell` (:946); `generate_plans_table` (:1015); `sync_plans_index` (:1046, markers opt-in :1055); `validate_plans_indexed` (:1066); `validate_docs` (:1357); argparse (:1562) | read this run |
| `scripts/decisions.py` | `ROW_RE` (:32); `_rows` cell split (:82); `_next_id` (:140-166, exit 1 on unreadable :159) | read this run |
| `scripts/epic_order.py` | `--assign` round-robin `_write_owner` (:668), idempotent (:693); `main` (:761) | read this run |
| `.claude/hooks/session_orient.py` | `_identity_line` + `is_hub` (:133-142); `main` reads `cwd` from the payload (:226); the block assembly (:287-295) | read this run |
| `src/fabrik/scaffold.py` | the inline PLANS.md literal (:1436-1452) — 280 KB file, over the per-ticket budget → Integration hatch | read this run |
| `commands/_sources/fabrik-vision.md` / `fabrik-epics-review.md` | EXISTING read list (:63-66); Step 1.5 (:138) | read this run |
| `docs/STRATEGIC_BACKLOG.md` | the hub tag legend + `Tag` column (:19-24); project shape `| Effort | Item | Why | Ready when |` (transdoc, seo, youtube) | read this run |
| `scripts/final_gate.py` | `run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check")` (:1884); `advisory` keeps stdout on exit 0, `warn_only` marks non-blocking (:347-365) | read this run |

## Constraints digest

| Pack | Row (verbatim) | Applies to |
|---|---|---|
| .windsurf/rules/core/10-python.md:21 | "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | no dependency added by any ticket |
| .windsurf/rules/core/10-python.md:219 | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | T02a (ledger row date, block stamp) |
| .windsurf/rules/core/10-python.md:291 | "**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rot" | T03/T04 print to stdout/stderr only |
| .windsurf/rules/core/10-python.md:245 | "Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces" | every Python ticket runs `ruff check` |
| .windsurf/rules/core/40-documentation.md:458 | "Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`." | every commit (subagent tickets: `Agent-Role: subagent` + `Agent-Task`) |
| .windsurf/rules/core/40-documentation.md:480 | "**Enforced:** Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry." | one CHANGELOG entry per ticket (Deltas) |
| .windsurf/rules/core/35-security-auth.md (FLOOR) | "**ZERO secrets/constants in code**" | the `/proc` scan reads `comm` and `cwd` only, never `environ` |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green.
- **Dispatch policy** — pool-default (`fanout(task_type, …)`, auto-records to the flywheel, wants the `set_quality` back-fill) for the gradeable tickets T01, T02a, T02b; native for T03 (`never-route` — it touches `scripts/final_gate.py`), T04, T05, T06 (`Complexity: native` — a synced hook, command prose, the Integration receipt), and native added on top as the authoritative pass on T02a (the fleet-synced script). Naming neither would let the executor go all-native.
- **Parallelism + merge** — T01, T02a, T04, T05 fan out concurrently at Phase 1 (disjoint Touches); T02b then T03 follow T02a serially on `scripts/docs_updater.py`; T06 runs last. Results merge in the main checkout by the merge owner in Merge Order, one `--no-ff` merge per ticket after its review exit; the D4 acceptance round is the pool trio + a native finder on T02a/T04.

## File Scope (owned paths)

- scripts/decisions.py
- tests/test_decisions_helper.py
- scripts/docs_updater.py
- tests/test_docs_updater_adopt.py
- .claude/hooks/session_orient.py
- tests/test_session_orient_hook.py
- docs/workstation/hooks-index.md
- commands/_sources/fabrik-vision.md
- commands/_sources/fabrik-epics-review.md
- tests/test_vision_reads_work_stores.py
- src/fabrik/scaffold.py
- tests/test_scaffold_doc_seeding.py
- docs/reference/multi-agent-operating-model.md
- templates/governance/CLAUDE.md
- docs/development/reviews/2026-09-06-plan-2-multi-agent-adoption-review.md
- scripts/final_gate.py

## Evidence

- `scripts/docs_updater.py:1055` — `return False, "docs/development/PLANS.md has no AUTO-GENERATED:PLANS markers — skipped"` (why 0 of 41 projects carry the block); `:924` `_PLANS_PHASE_NOTE` carries "agent-1's tail sweep fills it" (the sentence T02a retires); `:946` `_cell` escapes pipes; `:1562` `--sync` argparse line.
- `scripts/decisions.py:82` — `cells = [c.strip() for c in line.strip().strip("|").split("|")]`; `:162` the id scan; `:159` exit 1 on an unreadable ledger.
- `.claude/hooks/session_orient.py:139-142` — `is_hub = (Path(cwd) / "scripts" / "fabrik_synced_manifest.py").is_file()` + the UNNAMED warning; `:287-295` the block assembly where the new line slots after `_identity_line`.
- `src/fabrik/scaffold.py:1437-1455` — the PLANS.md literal ending in `| (none) | - | - |`.
- `commands/_sources/fabrik-vision.md:63-66` — the EXISTING read list; `fabrik-epics-review.md:138` — "Step 1.5: ticket-set integrity + owner assignment, in CODE".
- `scripts/final_gate.py:1884` — `run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check")`.
- SIZING DEFECT signals (execution window, logged per D6): the emit gate re-run mid-execution reports T02a at 275,503 B and T03 at 309,875 B against the 262,144 B READ budget — `scripts/docs_updater.py` grew 59→85 KB and `tests/test_docs_updater_adopt.py` 0→53 KB through the plan's own tickets, and T03 carries the 128 KB `scripts/final_gate.py`; T02a was merged before the growth, T03's coder read the file it was born into — no re-split; the ten missing-trailer WARNs are sibling commits on shared master (aca5b038, f44e002b, 17b172bf, 43bccf95) plus the Serialized T02a→T02b→T03 chain touching one file by design. Re-dispatches: T01 ×2 (pool units dead/blind), T02a ×1 (pool unit dead), T02b ×1 (native coder died on a 429 mid-round-2, its edits salvaged).
- Execution finding (T03 review r1): that call is under `if tier == 3` (`final_gate.py:1783`) and a passing advisory row's stdout is unreachable in `--check --json` — T03's Behavior Contract row 4 re-cut to the behavioural `run_optional_check(advisory=True)` test; the JSON surfacing is a backlog row (T06 Deltas). Plan-text defects recorded this run: T02b's Scope named a `Tag` column the hub table does not have (it is `Owner`); the T02b round-2 brief's own regex widening was a regression caught by the round-2 native finder (54 false skips fleet-wide) and fixed at the mechanism in round 3.

```text
$ for p in $(pgrep -x claude); do readlink /proc/$p/cwd; done | sort | uniq -c | sort -rn | awk '$1>=2'
      3 /opt/web-ecommerce-factory
      3 /opt/site-provisioner
      3 /opt/iterative_image_editor
      3 /opt/fabrik-lib
      3 /opt/fabrik
      2 /opt/youtube
      2 /opt/trade-intelligence
      2 /opt/brand-identiy-creator
total=21
$ (sync targets) git repos=41 plans_md=35 with_block=0
$ git -C /opt/seo worktree list --porcelain | grep -c '^branch refs/heads/worktree-agent-'   → 28   (of 29)
$ project backlogs: table rows=619 bullet rows=764 tagged table rows=6
$ grep -c '^| D-[0-9]* | [^|]* | [^|]* | \*\*' docs/DECISIONS.md → 58   (of 155 rows)
$ wc -c scripts/docs_updater.py src/fabrik/scaffold.py → 59363, 279834  (READ_BUDGET_BYTES = 262144 → scaffold.py is the Integration hatch)
```

## Self-audit

- Grounding passes: every `path:line` above was opened this run (the same anchors the spec's review re-derived, plus `docs_updater.py` main/argparse, `decisions.py` `_next_id`, `epic_order.py` `_write_owner`, the hook's `main`); the four measurements re-run this session; the four 1c sources probed 200 with quotes matched (spec § Chosen approach — inherited, not repeated).
- (a) Coverage — one master → T01/T02a; work-item split → T02a/T02b; make-sure mechanism → T03/T04; vision inputs → T05; markers at birth → T06; fire-rate proof → T06; docs → T04/T06/Deltas. No agreement without a ticket.
- (b) Cross-ticket signatures — `MERGE_OWNER_RE` identical in T01 and T02a (seam test on one fixture); `count_sessions_sharing(cwd)`/`read_merge_owner()` produced by T02a, consumed by T03; `classify_backlog_row` produced by T02b, consumed by T03; the marker pair + heading produced by T02a, reproduced by T06's scaffold literal; the hook's scan is a stated copy, seam-tested on the same synthetic pid list.
- Sizing: the emit gate summary line is recorded in § Residual unknowns once run; `scaffold.py` (280 KB) sits in the Integration ticket by the READ-budget hatch.
- Fixed point: reached at review r2 — r1 (pool ×3 + own re-derivation): 6 fixes (terminal-status set, no `v2` arg, hub suppression in T03, `advisory=True` at the gate call → T03 never-route, the fake proc tree instead of a count override in T04/T02a, the comm value resolved); r2: edit-free full re-read, emit gate 0 findings over 7 tickets / 20 Touches / 35 Context-Files entries.

## Coverage Checklist

Rubric over the touched surfaces (`python scripts/review_rubric.py --changed scripts/docs_updater.py scripts/decisions.py .claude/hooks/session_orient.py commands/_sources/fabrik-vision.md`):

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: .claude/hooks/session_orient.py, scripts/docs_updater.py)
### core/40-documentation.md  (hit: commands/_sources/fabrik-vision.md)
```

| Class | Status |
|---|---|
| core/10-python.md rows (uv, datetime, no logfile, ruff sets) | CLEAN — no dependency, `datetime.now(UTC)` named in T02a, stdout/stderr only (T03/T04), ruff in every Python ticket's gate path |
| core/40-documentation.md rows (trailers, CHANGELOG) | CLEAN — trailers in § Global Constraints; one CHANGELOG entry per ticket in every `Docs:` |
| FLOOR 35/25/30 (unconstrained here except secrets) | CLEAN — the scan reads `comm` + `cwd`, never `environ` (T02a, T04 DO-NOT) |
| Recurrence: bounded-count claims without denominators | FIXED r1 — "21 sessions / 8 checkouts / 6 synced", "0 of 41", "28 of 29", "619 + 764 / 6", "58 of 155", "27 → 28 rows" all carry their denominators |
| Recurrence: proxy-as-evidence (a grep standing in for a run) | FIXED r1 — the emit gate's own summary line (`graded 7 ticket(s), 20 Touches path(s), 35 Context-Files entry(ies) … 0 finding(s)`) is the sizing evidence; the comm value was RUN, not assumed |
| Recurrence: fleet blast radius of a synced surface | FIXED r1 — the hub excluded from BOTH advisories (T03 gained the `is_hub` return; T04 had it); single-session repos traced to zero output in T02a/T03/T04; `advisory=True` at `final_gate.py:1884` so the line is not silently dropped |
| Recurrence: idempotency claimed, not asserted on disk | FIXED r1 — T02a/T02b assert byte-identity on the second run; the terminal-status set corrected to the normaliser's real values (`EXECUTED`, `COMPLETE`); the "v2 version arg" claim removed (`replace_block` hard-codes `v1`) |

## Pass Ledger

| Pass | Layer | Method | Findings → fixed | What was re-derived |
|---|---|---|---|---|
| Pass r1 | pool ×3 (deepseek-v4-flash 0/5 — raw tool markup; gemini-3-flash 3/5; qwen3-max 1/5 — graded unexecuted deltas as missing code) + own re-derivation | method: re-derivation | 6 → 6 | `parse_plan_status` vocabulary re-read at `docs_updater.py:889-905` (terminal = EXECUTED, COMPLETE); `replace_block` re-read (:703-717, stamp hard-coded `v1`, no version arg); `run_check` (:1423) and `run_optional_check` (:347-365, stdout dropped on exit 0 unless `advisory=True`); the hook's block assembly (:287-295) and the harness's env seam (`tests/test_session_orient_hook.py:18-40`); the hub clause (operating-model § Hub vs project); `/proc/<pid>/comm` walked: 21 `claude` of 21 `pgrep -x claude`; `docs/reference/decision-ledger.md` exists; `check_script_headers.py` touch-on-change (:11-14); emit gate re-run: 7 tickets / 20 Touches / 35 Context-Files entries, 0 findings |
| Pass r2 | own closing read (full set) | method: re-derivation | 0 → 0 | roll-up recounted from the ticket files (28 = 3+7+4+4+4+3+3, spine equal); every ticket's eight fields present, no `Status:` line; stale-token sweep over the set (override / CONVERGED-EXECUTED / version-arg / to-adjudicate = 0 after the two legitimate mentions were read); emit gate 0 findings; `check_plan_quality.py` prints nothing on this set AND on a deliberately broken fixture (missing Complexity/Gate/Docs) — it grades nothing here, so field presence is self-verified above (filed as a finding, § Residual unknowns) |

## Residual unknowns

- **Resolved:** the advisory trigger (live sessions, not worktrees); the ledger grammar vs bold-leading cells; the three backlog row shapes; the socket cannot identify a worktree session (cwd can).
- **Resolved (review r1):** the `/proc/<pid>/comm` value of every live Claude Code session on this box is `claude` — `for p in $(pgrep -x claude); do cat /proc/$p/comm; done | sort | uniq -c` → `21 claude`, and a full `/proc` walk on `comm == claude` counts the same 21 as `pgrep -x claude`.
- **Open (self-service, T06):** the fire-rate proof reads 45 repos read-only; a repo whose PLANS.md is unreadable is reported as a row, never skipped silently.
- **Filed (infra, own beat):** `scripts/enforcement/check_plan_quality.py` reads `PLAN_DIR = Path.cwd()/docs/development/plans` (:44), takes no `--plan-dir`, and printed nothing on a fixture ticket missing `Complexity:`/`Gate:`/`Docs:` — the vacuous-check class; a backlog row is written at T06's Deltas and the check is measured before it is trusted.
- **Hand-off after execution (operator's word, per repo):** the six shared-checkout project repos measured today are the adoption candidates; agent-1 in each runs `python scripts/docs_updater.py --adopt <names>` — not this plan's step.
