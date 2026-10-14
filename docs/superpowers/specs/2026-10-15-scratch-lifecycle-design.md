# Scratch lifecycle — run-bound scratch that is deleted when its run is consumed

Status: DRAFT
Size: small (≈300 lines, 3 files)
Profile: delta

Operator approval of the design: 2026-10-14, verbatim — *"ok approved but do not cause active scrathcpads to be removed but be sure the ones consumed will be done so. /fabrik-spec"* (design note: the run's scratch `scratch-lifecycle-design.md`, reproduced in § The delta). Recorded as a `docs/DECISIONS.md` row in the same commit as this spec.

## Personas

- **Primary — the operator (ob)**, in their own words: *"do not cause active scrathcpads to be removed but be sure the ones consumed will be done so"*, after asking *"why arent agents clearing they scratchpads when they finish their work"*. Their loop is ZERO steps: scratch takes care of itself; the one manual act left is signing the one-time legacy list (§ Lifecycle). **Step budget: 0 recurring steps, 1 one-time step.**
- **Lead agent session** (any hub or project window running a `/fabrik-*` command): owns a run; its duty is to put bulky work under the run's folder and close the run. 3 steps per run, all already mandatory: `start` (prints the folder) → work → `done|blocked|handoff`.
- **Seat (subagent)**: writes only under the `seat-<n>/` folder its brief names; holds nothing after hand-back.
- **`command_run.py`** (automated): mints the run folder at `start`, deletes it at `done` when consumed, sweeps the session's other consumed run folders at every `start`, measures seat folders at `round`.
- **`scratch_sweep.py`** (automated: SessionStart/UserPromptSubmit hook, nightly `--dead` cron): classifies marked run folders by their marker and record, never by a tree walk; keeps today's path for untagged entries; prints the size alarm.
- **Infra** (owner of `command_run.py`, `scratch_sweep.py`, hooks) builds it; **kaizen** owns the brief wording in `commands/_fragments/`.

Every mechanism below names its holder; nothing is left to "the agent remembers".

## Goal

A scratch folder created for a run is removed when — and only when — that run is consumed, so agent scratch stops accumulating in long-lived sessions, with zero risk to scratch still in use.

## Why this exists

Measured 2026-10-14 (executed this session):

- `du -xh -d2 /tmp/claude-1000` → **73 G** total; `-opt-fabrik-lib/67ccc993…` **27 G**, `…wef3/a3d02ca4…` **17 G**, `-opt-fabrik/dd3c06d1…` **16 G**, intel 5.1 G, fleet 4.0 G, kaizen 2.0 G — all OPEN sessions.
- Inside them: `scratchpad/revC/B-sonnet/{head,before,after}` at **7.5 G each** (each copy carries the repo's `.claude/` 2.1 G, `.venv` 0.58 G, `node_modules` 0.25 G); `scratchpad/exec/` = **550** seat folders holding `repo-good`, `repo-revert1..3` copies ≈ 0.7 G each; infra's `pw39` 6.9 G, `pr-mr` 4.2 G.
- `python3 /opt/fabrik/scripts/scratch_sweep.py --session <sid>` (dry run) on the three: `revC · fresh · not walked — the shared freshness budget was exhausted`; `exec · probe-error · the freshness walk was cut short — never assumed stale`; `pw39`, `pr-mr` · `fresh · not walked`.

**Root cause (falsifiable):** scratch has no declared owner or lifetime, so the only remover infers liveness afterwards by walking every file's mtime under a fixed budget and KEEPS what it cannot finish — the larger the residue, the more certainly it survives. Falsify: give `scratch_sweep.py` a 20 GB entry whose files are all > 6 h old — today it returns `fresh`/`probe-error`, never `stale`.

Contributing causes: the close step only prints a dry-run table; seats copy whole live trees instead of the archive/clone recipe the catalogue prescribes; the nightly cron clears only DEAD sessions, and these sessions live for days.

The fix resolves exactly that: ownership is recorded when the folder is created, and the run's own close — an event that already happens every run — removes it, so neither age nor a walk is ever consulted for run-bound scratch.

## What exists today (grounded)

| Touchpoint | Today | Anchor |
|---|---|---|
| Sweep walk budget | 60 000 stats / 8 s total | `scripts/scratch_sweep.py:119`, `scripts/scratch_sweep.py:130` |
| Unwalked entry kept | `fresh`/`probe-error`, "never assumed stale" | `scripts/scratch_sweep.py:824-832` |
| Holder probe | same-uid fd / cwd under the entry | `scripts/scratch_sweep.py:292` (`probe_holders`) |
| Live session test | `sessions/<pid>.json` pid + procStart match | `scripts/scratch_sweep.py:561` (`live_record`) |
| Dead-session janitor | cron `20 4 * * * … scratch_sweep.py --dead --apply` | `scripts/scratch_sweep.py:1287` (`dead_sessions`) |
| Close-time advice | dry-run `--brief` table, deletes nothing | `scripts/command_run.py:6071-6109` (`_scratch_advisory`), call site `scripts/command_run.py:3609` |
| Persistent run dir (D-836) | `<main>/.tmp/runs/<sid>/<command>-<key>/`, 14-day newest-mtime prune, referenced dirs kept | `scripts/command_run.py:1370-1376`, `scripts/command_run.py:1450` (`_prune_scratch`), `scripts/command_run.py:1484` (`_scratch_referenced`), `scripts/command_run.py:1501-1549` (`_make_scratch`) |
| Session scratch resolver | `<root>/<cwd-slug>/<sid>/` | `scripts/scratch_sweep.py:614` (`find_session_dirs`) |
| Seat copy rule | archive of the pinned SHA, `clone --shared --no-checkout`, never `git worktree add` in a seat | `commands/_fragments/review-probe-catalogue.md:160-185` |

Census of the stores this design governs (executed): (1) the harness session scratchpad `/tmp/claude-1000/<slug>/<sid>/scratchpad` — 73 G; (2) D-836 `.tmp/runs` — 1.5 M across 3 runs; only `commands/_sources/fabrik-task.md` names its `SCRATCH:` path, 8 other source/fragment files point seats at the session scratchpad.

## The delta

Design approved 2026-10-14 (Opus + Fable panel converged; three Sonnet judges ranked it first unanimously, 2026-10-15). Two tiers, one rule each:

- **Durable tier — unchanged:** D-836's `.tmp/runs/…` keeps small resume artifacts (seeds, measure notes) exactly as today.
- **Disposable tier — new:** bulky run work (pins, overlays, seat copies, probe trees) lives in `<session scratchpad>/run-<record key>/`, removed when the run is consumed.

### Invariants (the operator's constraint, made checkable)

- **INV-1 — active is never removed.** A run folder is ACTIVE when ANY holds: its run record is `running` and the owning session is live (`live_record`, `scripts/scratch_sweep.py:561`); a resume seed or record references it (`_scratch_referenced`, `scripts/command_run.py:1484`); `probe_holders` (`scripts/scratch_sweep.py:292`) finds any same-uid fd or cwd inside it; `probe_holders` itself could not complete (`probe_ok` false). Any doubt ⇒ ACTIVE. pid + start time is never the sole signal (LWN 1024448 — not reuse-safe).
- **INV-2 — consumed is always removed.** A run folder is CONSUMED when its record is closed `done` (or its owning session is no longer live and no seed references it) AND INV-1 does not hold. Every CONSUMED folder is removed by the first of: that run's own `done`; the session's next `start`; the next hook or nightly sweep — whatever its size, with no tree walk.
- **INV-3 — removal is by name, never by inference.** Only a folder carrying a `.owner` marker whose `sid` equals the remover's sid (or a dead sid, in `--dead`) is touched; a marker naming another live session is kept.

### Touchpoints

1. **D1 — mint (`command_run.py start`).** Beside `_make_scratch` (`scripts/command_run.py:1501`), create `<session scratchpad>/run-<key>/` (resolver: `find_session_dirs`, `scripts/scratch_sweep.py:614`) with `.owner` = `{sid, key, command, created}`; record it as `run_scratch`; print `RUN-SCRATCH: <path>` next to `SCRATCH:`. A failure to mint never refuses the start (D-836's fail-open rule).
2. **D2 — consume at close (`done`).** After the record lock drops (the `_scratch_advisory` slot, `scripts/command_run.py:3609`): if INV-1 is false, `rename run-<key>` → `.trash-<key>` (atomic, rename(2)), then remove it; if INV-1 holds, keep it and print why. `blocked` and `handoff` never remove (their seed references the folder — INV-1). The dry-run advisory stays for untagged entries.
3. **D3 — begin-and-end sweep (`start`).** Every `start` removes its own session's CONSUMED `run-*` and `.trash-*` folders (marker + record + INV-1 only — no walk), so a crashed close is cleared at the session's next run, as job runners do at each job boundary.
4. **D4 — marker-first classification (`scratch_sweep.py`).** In the session/hook/`--dead` modes, an entry with `.owner` is classified from its marker and record alone (`consumed` → removable, `active` → kept with its reason) BEFORE the walk budget is consulted; untagged entries keep today's path unchanged. `--dead` removes a dead session's marked folders without walking them.
5. **D5 — seat-size check (`round`).** `round` measures each `seat-*` folder of the run (`du` with a deadline, `scripts/scratch_sweep.py:429` `_du_kb`) and prints the ones over the threshold as `copied a tree instead of archive/clone`. ADVISORY until the fire rate is measured on ≥ 20 rounds; the threshold (start: 2 GB) is set from that measurement before it ever refuses.
6. **D6 — size alarm (hook).** The SessionStart/UserPromptSubmit hook prints one line when a session's bytes OUTSIDE its open run folders exceed 5 GB, or the filesystem passes 85 % (`statvfs` `f_bavail`·`f_frsize` vs `f_blocks`·`f_frsize`), naming the top three folders; and any run folder older than 72 h whose record is still `running`. Advisory only.
7. **D7 — brief wording (kaizen).** `commands/_fragments/subagents-core.md` and `commands/_fragments/review-probe-catalogue.md` name `RUN-SCRATCH` as the root of every seat folder (`<run scratch>/seat-<n>/`) and restate the existing copy rule as the only way to stage a tree.

### Cobra check (D-253)

The cheapest way to satisfy "run folders are cleaned" without the outcome is to keep writing bulk work OUTSIDE the run folder (bare `scratchpad/`, `/tmp`), or to keep a dead run `running`. Counter-measures shipped with it: D6 counts every byte outside open run folders and every run `running` > 72 h; D5 measures the outcome (bytes), not a command shape (a `cp -r` ban is dodged with `rsync`/`tar`).

## Contract deltas

None — no data contract, UI contract or `shape:` field changes. Run-record JSON gains one optional key `run_scratch` (additive; readers ignore unknown keys).

## Cost

≈ 300 code lines in 3 files (`scripts/command_run.py` ~170, `scripts/scratch_sweep.py` ~90, the hook path inside `scratch_sweep.py --hook` ~40) plus tests; markdown edits in two fragments and a re-render from merged master. Disk: frees the bulk of 73 G within one run of each owning session after the legacy pass.

## Validation

Graders (pytest, in `tests/test_command_run*.py` and `tests/test_scratch_sweep*.py`), each proven red on the pre-change code:

- **V1 (INV-2, the root cause):** a 100 000-file marked folder of a closed run is removed by `done` with a constant number of `stat` calls (assert the walk budget is never spent), and by `--dead` for a dead sid.
- **V2 (INV-1, the operator constraint):** each ACTIVE condition alone keeps the folder — `running` + live session; seed reference; a child process holding an fd inside; a child with cwd inside; `probe_ok` false. One test per condition.
- **V3 (INV-3):** a marker naming another live sid is never removed, even when its record is closed.
- **V4 (D3):** a run whose close crashed after the rename leaves `.trash-<key>`; the next `start` removes it; a `blocked` run's folder survives a later `start`.
- **V5 (D5/D6):** a sparse 3 GB seat file is reported by `round` and the alarm fires on a synthetic 6 GB outside-run total; neither refuses anything.
- **V6:** untagged entries classify exactly as before (golden table from today's sweep output).

## Decisions taken

- Run-bound disposable folder under the session scratchpad, not under D-836's main-checkout root — a worktree session cannot write the main checkout (executed 2026-10-15), and two judges required it.
- `done` removes; `blocked`/`handoff` keep (resume) — matches D-836's referenced-dir rule.
- Size check and alarm ship advisory; promotion to a gate waits on a measured fire rate.
- Approach B over A (fix the remover only) and C (OS isolation) — § Rejected alternatives.

## Rejected alternatives

- **A — fix the remover only** (top-level mtime/ctime + holders, `--apply` at close): still a heuristic; a top-level ctime is bumped by any write inside, so a long-lived session's big folder reads fresh forever; has no signal for a resumable run. Judges: 2nd, "stopgap only".
- **C — OS isolation** (per-session tmpfs / PrivateTmp namespace): needs root on WSL2; reclaims only at session end, which long-lived sessions never reach; tmpfs spends RAM. Disqualified by all three judges.
- **Bigger walk budget:** cost still scales with size and the 10 s hook cap bounds it anyway.
- **Delete each seat folder at hand-back:** the lead still adjudicates from it; a late writer may be running. Tie removal to the run.
- **A `cp -r` ban:** dodged by `rsync`/`tar`; D5 measures bytes instead.
- **Age-only deletion inside live sessions:** tmpreaper's own README.security documents removing files a suspended process still needs — the opposite of INV-1.

## Lifecycle

- **Adoption:** ships with D1–D4 together; from the first `start` after merge, new runs are bound. D7's wording reaches every repo with the next render + governance sync.
- **One-time legacy pass:** untagged leftovers (today's 73 G) are listed per session by `scratch_sweep.py` with holders and live-session status; the operator signs the list; only listed, unheld folders of sessions that agree (or dead sessions) are removed. Nothing untagged is removed without that list.
- **Growth:** D6 is the trigger — sustained alarms (> 3 sessions over 5 GB outside runs in a week) mean a command still writes outside its run folder; fix that command's brief.
- **Degradation:** every failure path keeps the folder (INV-1) and says why; a mint failure falls back to today's behaviour.
- **Retirement:** if the harness ever scopes scratch per task itself, D1–D3 retire and D4 stays as the legacy path.

## Constraints Digest

| Quote | Source |
|---|---|
| contents are DISPOSABLE by contract | `.windsurf/rules/core/10-python.md:151` |
| Anything that must SURVIVE a restart is not temp | `.windsurf/rules/core/10-python.md:153` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |
| Registered in final_gate.py at correct tier | `.windsurf/rules/core/40-documentation.md:91` |
| row in the SAME change (rows immutable; supersede-by-new-row) | `.windsurf/rules/core/40-documentation.md:76` |
| Scheduled job (Beat/cron/systemd timer) added or changed | `.windsurf/rules/core/40-documentation.md:75` |

## Constraints

Shared same-uid box, several live sessions per repo; no root; deleting a live session's in-use files is a critical failure (CLAUDE.md § Behavior); seats run read-only git and never `git worktree add` on the live repo.

## fabrik-lib verdict

BUILD (box tooling inside the hub's own `command_run.py`/`scratch_sweep.py`; no fabrik-lib module covers session scratch; not a candidate — hub-specific).

## External dependencies

All fetched 2026-10-14 by native `fabrik-researcher` seats (tools named per row):

- rename(2) — "If newpath already exists, it will be atomically replaced" and "Open file descriptors for oldpath are also unaffected" — https://man7.org/linux/man-pages/man2/rename.2.html (exa fetch).
- open(2) — "this reference is unaffected if path is subsequently removed or modified" — https://man7.org/linux/man-pages/man2/open.2.html (exa fetch).
- unlink(2) — "the file will remain in existence until the last file descriptor referring to it is closed" — https://man7.org/linux/man-pages/man2/unlink.2.html (exa fetch).
- proc_pid_stat(5) field 22 starttime "expressed in clock ticks" — https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html (firecrawl, maxAge 0); pid + starttime not reuse-safe — https://lwn.net/Articles/1024448/ (exa search).
- statvfs(3) — "f_bavail; /* Number of free blocks for unprivileged users */" — https://man7.org/linux/man-pages/man3/statvfs.3.html (exa fetch).
- shutil.rmtree — "rmtree() now ignores FileNotFoundError exceptions for all but the top-level path" (3.13) — https://docs.python.org/3/library/shutil.html (exa fetch).

## Approach grounding (1c)

- systemd.exec(5) RuntimeDirectory=: "the lifetime of the directories is tied directly to the lifetime of the unit" — https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html (firecrawl directQuote).
- tmpfiles.d(5): a directory holding a BSD flock "(and everything below it) is skipped" by age cleanup — https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html (exa search + fetch).
- GitHub Actions RUNNER_TEMP: "This directory is emptied at the beginning and end of each job" — https://docs.github.com/en/actions/reference/workflows-and-actions/variables (exa search).
- GitLab job execution: cleanup "regardless of whether previous steps failed" — https://docs.gitlab.com/ci/jobs/job_execution/ (exa search).
- Nix GC: "all paths in the Nix store not reachable via file system references from a set of 'roots', are deleted" — https://nix.dev/manual/nix/latest/command-ref/nix-store/gc.html (exa search).
- tmpreaper README.security: suspended processes' temp files "are likely to be removed" by age cleaners — https://fossies.org/linux/tmpreaper/debian/README.security (firecrawl directQuote).

## Shape / infra implications

None — box-local tooling; no service, no `specs/services/` change, no port.

## Documentation landing sites

- `docs/workstation/cleanup-automation.md` § F (the scratch sweep's home) — the run-bound tier, INV-1..3, the alarm.
- `docs/workstation/hooks-index.md` — the hook's new alarm line.
- `commands/_fragments/subagents-core.md`, `commands/_fragments/review-probe-catalogue.md` — `RUN-SCRATCH` for seats (kaizen).
- `CHANGELOG.md`, `docs/DECISIONS.md` (the ruling row, this commit).

## Open / blocking unknowns

- **Resolved:** where the disposable tier lives (session scratchpad — judges); pid reuse (never the sole signal); rename atomicity (same filesystem — the folder is renamed in place).
- **Open — the D-836 worktree-write gap** (a worktree session cannot write its own durable `.tmp/runs` dir): infra's, OUT of this spec; destination mail `01M4Y3N9GW8N6HZ5D1QTFZPHWF` to infra.
- **Open — thresholds** (2 GB seat, 5 GB session, 85 % disk, 72 h): resolution step = measure on ≥ 20 rounds after D1–D4 ship, then set by a D-row before D5/D6 can ever refuse.

## Intake Inventory

Scope: the scratch thread of the 2026-10-14 session, from "now look at claude session scratch" onward.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "now look at claude session scratch, why does it occupy 72gb" | IN | § Why this exists |
| I2 | "why arent agents clearing they scratchpads when they finish their work" | IN | § Why this exists — root cause |
| I3 | "didnt like your solution approaches rethink" | IN | § Rejected alternatives |
| I4 | "are we addressing the root cause … ask to subagent and use brainstorming skill" | IN | § Why this exists; § Decisions taken |
| I5 | "do not cause active scrathcpads to be removed" | IN | § The delta — INV-1 |
| I6 | "be sure the ones consumed will be done so" | IN | § The delta — INV-2 |
| I7 | "/fabrik-spec" | IN | this artifact |
| I8 | one-time cleanup of today's 72 GB with an operator-signed list (approved design note) | IN | § Lifecycle — one-time legacy pass |
| I9 | seats copy whole live trees (surfaced) | IN | § The delta — D5, D7 |
| I10 | D-836 run scratch unwritable from a worktree session (surfaced) | OUT-OF-SCOPE | mail 01M4Y3N9GW8N6HZ5D1QTFZPHWF to infra |
| I11 | "do not bypass the guard" (subagent transcripts) | OUT-OF-SCOPE | transcript pruner, answered on W-1afe3956 |
