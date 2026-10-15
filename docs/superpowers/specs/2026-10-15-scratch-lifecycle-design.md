# Scratch lifecycle — run-bound scratch that is deleted when its run is consumed

Status: CONVERGED
Size: small (≈350 lines, 2 files)
Profile: delta

Operator approval of the design: 2026-10-14, verbatim — *"ok approved but do not cause active scrathcpads to be removed but be sure the ones consumed will be done so. /fabrik-spec"* (design note: the run's scratch `scratch-lifecycle-design.md`, reproduced in § The delta). Recorded as D-864 in `docs/DECISIONS.md`. Review receipt: `docs/development/reviews/2026-10-15-scratch-lifecycle-spec-review.md`.

## Personas

- **Primary — the operator (ob)**, in their own words: *"do not cause active scrathcpads to be removed but be sure the ones consumed will be done so"*, after asking *"why arent agents clearing they scratchpads when they finish their work"*. Their loop is ZERO recurring steps: scratch takes care of itself, and an alarm is acted on by the agent that sees it, never by the operator. The one manual act left is signing the one-time legacy list (§ Lifecycle). **Step budget: 0 recurring steps, 1 one-time step.**
- **Lead agent session** (any hub or project window running a `/fabrik-*` command): owns a run; its duty is to put bulky work under the run's folder, close the run only after every seat has handed back, and route an alarm it sees (D6) to kaizen as a brief fix. 3 steps per run, all already mandatory: `start` (prints the folder) → work → `done|blocked|handoff`.
- **Seat (subagent)**: writes only under the `seat-<n>/` folder its brief names; holds nothing after hand-back.
- **`command_run.py`** (automated): mints the run folder and its `.owner` marker at `start`, refreshes the marker at every `step`/`round`/`dispatch` (the heartbeat), writes the run's terminal state into the marker at every close, moves a `resumable` folder into the adopting session on `start --resume-from`, removes the session's own CONSUMED run folders at every `start` (D3), measures seat folders at `round` (D5).
- **`scratch_sweep.py`** (automated): the nightly cron (`--dead --apply`, extended) removes CONSUMED marked run folders of EVERY session by marker, without a walk, keeps any dead session's directory that still holds an ACTIVE run folder (D4), and writes the size report (D6); the SessionStart-only hook prints the advisory alarm from that report and removes nothing; untagged entries keep today's path.
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

The fix resolves exactly that: ownership and state are recorded on the folder itself when it is created and at every close, and removal reads that record — neither age nor a walk is ever consulted for run-bound scratch.

## What exists today (grounded)

| Touchpoint | Today | Anchor |
|---|---|---|
| Sweep walk budget | 60 000 stats / 8 s total | `scripts/scratch_sweep.py:119`, `scripts/scratch_sweep.py:130` |
| Unwalked entry kept | `fresh`/`probe-error`, "never assumed stale" | `scripts/scratch_sweep.py:824-832` |
| Holder probe | same-uid fd / cwd under the entry; an unreadable same-uid `/fd` of a process that is not a zombie is returned in `gaps` while `probe_ok` stays true | `scripts/scratch_sweep.py::probe_holders`, `scripts/scratch_sweep.py::_is_zombie` |
| Live session test | `sessions/<pid>.json` pid + procStart match | `scripts/scratch_sweep.py:561` (`live_record`) |
| Dead-session janitor | cron `20 4 * * * … scratch_sweep.py --dead --apply`; three signals plus an idleness walk with a 30 s deadline, a cut-short walk is `unclassified`; a `dead` row is a WHOLE `<slug>/<sid>` directory, removed by `apply_rows` | `scripts/scratch_sweep.py:1287` (`dead_sessions`), `scripts/scratch_sweep.py:1369-1373`, `scripts/scratch_sweep.py:1458` (`apply_rows` call) |
| Hook | SessionStart only (UserPromptSubmit measured and rejected), advisory, removes nothing | `scripts/scratch_sweep.py:2477` (`run_hook_mode`) |
| Close-time advice | dry-run `--brief` table, deletes nothing | `scripts/command_run.py:6071-6109` (`_scratch_advisory`), call site `scripts/command_run.py:3609` |
| Run record | ONE file per session, overwritten by every `start` | `scripts/command_run.py:159` (`_record_path`) |
| Persistent run dir (D-836) | `<main>/.tmp/runs/<sid>/<command>-<key>/`, 14-day newest-mtime prune, dirs named by any `*.json` record or `seeds/*.json` kept | `scripts/command_run.py:1370-1376`, `scripts/command_run.py:1450` (`_prune_scratch`), `scripts/command_run.py:1484-1498` (`_scratch_referenced`), `scripts/command_run.py:1501-1549` (`_make_scratch`) |
| Resume seeds | `handoff` keeps a `.md` seed; a quota-wall `blocked` keeps a JSON seed; nothing prunes `seeds/` | `scripts/command_run.py:4996-5010` (`_keep_resume_seed`) |
| Session scratch resolver | `<root>/*/<sid>/` found by glob, never computed — the harness slug is `re.sub(r"[^A-Za-z0-9]", "-", cwd)` | `scripts/scratch_sweep.py:614-620` (`find_session_dirs`) |
| Size probe | `du -sk` (allocated blocks) with a 3 s timeout | `scripts/scratch_sweep.py:429` (`_du_kb`) |
| Seat copy rule | archive of the pinned SHA, `clone --shared --no-checkout`, never `git worktree add` in a seat | `commands/_fragments/review-probe-catalogue.md:160-185` |

Census of the stores this design governs (executed): (1) the harness session scratchpad `/tmp/claude-1000/<slug>/<sid>/scratchpad` — 73 G; (2) D-836 `.tmp/runs` — 1.5 M across 3 runs; only `commands/_sources/fabrik-task.md` names its `SCRATCH:` path, 8 other source/fragment files point seats at the session scratchpad.

## The delta

Design approved 2026-10-14 (Opus + Fable panel converged; three Sonnet judges ranked it first unanimously, 2026-10-15). Two tiers, one rule each:

- **Durable tier — unchanged:** D-836's `.tmp/runs/…` keeps small resume artifacts (seeds, measure notes) exactly as today.
- **Disposable tier — new:** bulky run work (pins, overlays, seat copies, probe trees, revert-test backups) lives in `<session scratchpad>/run-<record key>/`. Its contents are disposable by contract once the run is consumed; anything that must outlive the run is committed or moved out before the close.

### The marker — the single source of truth

Every run folder carries `.owner` (JSON): `{sid, key, command, repo, created, state, closed_at}`. `key` is the run record's key (command + start timestamp), unique per run; `repo` is the absolute common git directory of the checkout the run started in (`git rev-parse --path-format=absolute --git-common-dir`, the call `_scratch_main` makes, `scripts/command_run.py:1391-1400`), which outlives any one worktree. `state` ∈ `running` · `done` · `resumable`. Only a quota-wall `blocked --wall` writes `resumable`, because only its JSON seed can be adopted by `start --resume-from` (`scripts/command_run.py:5203-5208`); `handoff` and a plain `blocked` have no path that reuses the folder, so they write `done`; what a handoff's successor needs belongs in D-836's tier or a commit, and D2 refuses a handoff whose `--resume` text names a path under its own run folder. The folder's OWNER is the session directory it sits under; the marker's `sid` is informational. `command_run.py` writes it at `start`, refreshes its mtime at every `step`, `round` and `dispatch` (the HEARTBEAT — one `utime`, no walk), and rewrites `state` and `closed_at` at every close. The marker — not the per-session run record, which the next `start` overwrites (`scripts/command_run.py:159`) — is what every remover reads.

### Invariants (the operator's constraint, made checkable)

- **INV-1 — active is never removed.** A `run-*` folder is ACTIVE when ANY holds:
  - its marker reads `running` and its owning session is not DEAD — DEAD here = no live signal AND a death signal (`scratch_sweep.py`'s existing signals) AND a marker heartbeat older than 7 days; pid + start time is never the sole signal (a reader comment on LWN 1024448), and no tree walk is needed;
  - its marker reads `resumable` (a quota-wall resume may still come — never auto-removed; D6 names it after 72 h);
  - its marker reads `done` and `closed_at` is less than 30 minutes old (the grace for a seat finishing after its lead closed);
  - `probe_holders` (`scripts/scratch_sweep.py:318`) finds a same-uid fd or cwd inside it, OR returns a `gaps` entry whose process is still alive (`gap_starts` drops an exited pid; a zombie is never a gap) and either started at or after the marker's `created` less 300 s, has an unknown start time, or sits beside a missing, non-numeric or more-than-300-s-future `created` (D-878; `scripts/scratch_sweep.py::gap_keeps`), OR does not complete;
  - it contains a REGISTERED git worktree at any depth — any path in `git --git-dir=<repo> worktree list --porcelain` that lies under the folder (one call; a `repo` that no longer resolves leaves a run folder that held no worktree removable only after its `.git`-free top two levels are confirmed; a worktree is removed with `git worktree remove`, never rm -rf) — or a top-level `.keep`;
  - its marker is missing or unreadable.
  Any doubt ⇒ ACTIVE. In a dead session's directory, D4 keeps every ACTIVE run folder and removes the rest of that session's `scratchpad/` entry by entry (§ D4).
- **INV-2 — consumed is always removed.** A `run-*` folder is CONSUMED when INV-1 does not hold and its marker reads `done` (grace passed) or `running` for a DEAD session. Every CONSUMED folder is removed — whatever its size, with no tree walk — by the first of: the owning session's next `start` after the grace (D3), or the next nightly sweep (D4), so within 24 hours plus the grace. A `.trash-<key>` folder is CONSUMED by construction (it was renamed only after INV-1 was false) and needs only the holder probe; its gap test reads the marker's `created` and, when that is missing or not a number, the folder's rename time (`lstat().st_ctime`) instead, so a markerless trash folder is not kept for ever.
- **INV-3 — removal is by marker and name, never by inference.** A remover touches a `run-*` folder only through its readable `.owner`: D3 only folders under its OWN session directory; D4 any session's folders, by marker state alone. Ownership is the session directory a folder sits under, so two sessions sharing a cwd-slug (distinct `<sid>` directories) never touch each other's folders.

### Touchpoints

1. **D1 — mint (`command_run.py start`).** Beside `_make_scratch` (`scripts/command_run.py:1501`), resolve the session directory with `find_session_dirs(root, sid, cwd)` (`scripts/scratch_sweep.py:614`) — found by glob, never computed; create `<that>/scratchpad/run-<key>/` with its `.owner`; record it as `run_scratch`; print `RUN-SCRATCH: <path>` next to `SCRATCH:`. If no session directory is found, mint nothing and print why — the start is never refused (D-836's fail-open rule).
2. **D2 — mark at close.** `done`, `handoff` and a plain `blocked` write `state: done, closed_at`; only `blocked --wall` writes `state: resumable`. A `handoff` whose `--resume` text names a path under its own run folder is refused with the reason (a successor is a new run and the folder is removed after the grace — what it needs belongs in D-836's tier or a commit). Nothing is removed at close (a seat may still be finishing). The dry-run advisory stays for untagged entries.
3. **D3 — begin-and-end removal and adoption (`start`).** Every `start` removes its own session's CONSUMED run folders: `rename` the folder to `.trash-<key>` in the same directory (atomic; rename(2): for a directory "newpath must either not exist, or it must specify an empty directory" — keys are unique, so it does not), then remove it; a crash between the two leaves `.trash-<key>`, which the next `start` or nightly sweep removes after its holder probe. A `start --resume-from` whose seed names a `resumable` folder ADOPTS it with ONE step — `rename` it into the new session's `scratchpad/run-<new key>/` (same filesystem under the harness root); the state stays `resumable` (ACTIVE) until the adopting run's own close writes `done`, so a crash at any point leaves an ACTIVE folder, never a removed one. A folder holding a registered worktree is not adopted (a rename would break the worktree's link); then, or if the rename fails, the run mints a fresh folder and the old one stays `resumable`.
4. **D4 — marker-first nightly sweep (`scratch_sweep.py --dead --apply`).** Before any session-level classification, every marked `run-*` and `.trash-*` folder of every session is classified from its marker and INV-1 alone — no walk budget, no idleness walk — and CONSUMED ones are removed. Then a dead session's directory is removed whole only if it holds no ACTIVE run folder; otherwise D4 keeps the session directory and its `scratchpad/`, removes every other entry of that `scratchpad/` one by one, and the session directory's other top-level entries (`tasks/`, stamps) as today — never more than today's whole-directory removal would — keeping each ACTIVE run folder, its row reading `kept — holds an active run folder`. Untagged entries keep today's path unchanged. `scratch_sweep.py` reads `.owner` files and never the command-run state directory.
5. **D5 — seat-size check (`round`).** `round` measures each `seat-*` folder of the run by apparent size (`du -s --apparent-size`, its own deadline per folder) and prints the ones over the threshold as `copied a tree instead of archive/clone`; a measurement that times out prints `size unmeasured — over the deadline`. ADVISORY until the fire rate is measured on ≥ 20 rounds; the threshold (start: 2 GB) is then set by a D-row before it ever refuses.
6. **D6 — size report and alarm.** The nightly sweep (D4's holder) measures each session directory's apparent bytes outside its `running` run folders and lists run folders older than 72 h that are not `done`, writing `$HOME/.claude/state/scratch-size-report.json` (one file beside its lock — a refusal-set change, § Contract deltas). The SessionStart hook reads that report plus `statvfs` usage computed as `df` does (used ÷ (used + available), `f_bavail` for available) and prints one line when usage passes 85 %, its session holds more than 5 GB outside running run folders, or it owns a run folder older than 72 h that is not `done`. It never walks and never removes. A removed folder whose files are still open keeps its space until the last descriptor closes (unlink(2)), so the alarm can lag a removal.
7. **D7 — brief wording (kaizen).** `commands/_fragments/subagents-core.md` and `commands/_fragments/review-probe-catalogue.md` name `RUN-SCRATCH` as the root of every seat folder (`<run scratch>/seat-<n>/`) and restate the existing copy rule as the only way to stage a tree.

### Cobra check (D-253)

The cheapest way to satisfy "run folders are cleaned" without the outcome is to keep writing bulk work OUTSIDE the run folder (bare `scratchpad/`, `/tmp`), or to leave runs `resumable` or `running` for ever. Counter-measures shipped with it: D6 counts every byte outside open run folders and every run folder older than 72 h that is not `done`; D5 measures the outcome (apparent bytes), not a command shape (a `cp -r` ban is dodged with `rsync`/`tar`).

## Contract deltas

- **New cross-script file contract:** `.owner` JSON (`sid`, `key`, `command`, `repo`, `created`, `state` ∈ `running|done|resumable`, `closed_at`) — written by `command_run.py`, read by `scratch_sweep.py`.
- **Run-record JSON:** one optional key `run_scratch` (additive; readers ignore unknown keys).
- **`scratch_sweep.py` printed refusal set** (`scripts/scratch_sweep.py:60-61`, the `--help` text): gains the marker rule — it reads `.owner` files and removes a marked folder only when INV-2 holds — and one more file it writes under `~/.claude/state`: `scratch-size-report.json`.
- No data contract, UI contract or `shape:` field changes.

## Cost

≈ 350 code lines in 2 code files (`scripts/command_run.py` ~200: D1-D3 and D5; `scripts/scratch_sweep.py` ~150: D4, the nightly size report and the D6 hook line) plus tests (`tests/test_command_run_scratch.py`, a scratch-sweep test file); markdown edits in two fragments (D7) and four docs; a re-render from merged master. Disk: frees the bulk of 73 G after the one-time legacy pass.

## Validation

Graders (pytest), each proven red on the pre-change code:

- **V1 (INV-2, the root cause):** a 100 000-file marked folder of a `done` run past its grace is removed by the session's next `start` and by the nightly sweep with a constant number of `stat` calls (assert no walk budget is spent); a dead session's `running` folder with a stale heartbeat is removed without the idleness walk.
- **V2 (INV-1, the operator constraint):** each ACTIVE condition alone keeps the folder — `running` with a live session; `running` with a fresh heartbeat in a session with no live signal; `resumable`; `done` within the grace; a child process holding an fd inside; a child with cwd inside; a live `gaps` entry started at or after `created` less 300 s, or with an unknown start time, or beside a missing, non-numeric or more-than-300-s-future `created` (D-878); a probe that does not complete; a registered worktree two levels down; a `.keep`; a missing marker. One test per condition. A dead session's directory holding a `resumable` folder survives the nightly sweep.
- **V3 (INV-3):** `start` never touches another session's folders; a marker whose `sid` differs from its directory is kept.
- **V4 (D3 crash and adoption):** a crash after the rename leaves `.trash-<key>`, removed by the next `start`; `start --resume-from` moves a `resumable` folder into the new session and its later `done` makes it CONSUMED there; a crash right after the adoption rename leaves it `resumable` and kept; a folder holding a registered worktree is not adopted; `handoff` and plain `blocked` write `done`.
- **V5 (D5/D6):** a real 3 MB seat file with the threshold lowered to 1 MB is reported by `round`; a slow measurement reports `size unmeasured`; the hook prints the alarm from a synthetic report; neither refuses or removes anything.
- **V6:** untagged entries classify exactly as before (golden table from today's sweep output); the derivation of the session directory matches `find_session_dirs` for a cwd containing `_` and `.`.

## Decisions taken

- Run-bound disposable folder under the session scratchpad, not under D-836's main-checkout root — a worktree session cannot write the main checkout (executed 2026-10-15), and two judges required it.
- The `.owner` marker, not the per-session record, holds the run's state — the record is overwritten by the next `start`.
- Nothing is removed at close; removal waits for the 30-minute grace and then the session's next `start` or the nightly sweep — a seat may still be finishing.
- A dead `running` run is judged by its marker heartbeat (7 days), not by a tree walk — a gone pid is not a finished session (D-187).
- Adoption is one rename into the resuming session, so the new owner's own `start` finds it and no crash strands it as removable.
- Only a quota-wall `blocked` is `resumable`; `handoff` and plain `blocked` are `done`, since nothing can resume into their folder.
- `resumable` folders are never auto-removed; the alarm names them after 72 h.
- The seat-size check and the alarm ship ADVISORY; this narrows the approved note's "fails the round" until a fire rate is measured (FIX DIRECTIVE 5), and the operator may overrule it (Intake I12).
- Approach B over A (fix the remover only) and C (OS isolation) — § Rejected alternatives.
- A `/proc` gap keeps a folder only when its still-live process could be one of the run's writers — it started at or after the marker's `created` less 300 s — or a time is unknown (the start time, or a missing, non-numeric or more-than-300-s-future `created`): the box carries three same-uid daemons permanently, which kept every folder for ever under the original "a non-empty `gaps` list". The accepted residual, in D-878's words: "a daemon a run starts mid-run, or after a `.trash-*` rename, keeps that folder until the daemon exits or the next boot" (D-877, made the rule by D-878; re-frozen into INV-1, V2 and INV-2 on 2026-10-15).

## Rejected alternatives

- **A — fix the remover only** (top-level mtime/ctime + holders, `--apply` at close): still a heuristic; a top-level ctime is bumped by any write inside, so a long-lived session's big folder reads fresh forever; has no signal for a resumable run. Judges: 2nd, "stopgap only".
- **C — OS isolation** (per-session tmpfs / PrivateTmp namespace): needs root on WSL2; reclaims only at session end, which long-lived sessions never reach; tmpfs spends RAM. Disqualified by all three judges.
- **Bigger walk budget:** cost still scales with size and the hook's 4 s deadline bounds it anyway.
- **Remove at close:** a seat may still be finishing after its lead closes; the grace plus the next `start` covers it.
- **Delete each seat folder at hand-back:** the lead still adjudicates from it; tie removal to the run.
- **A `cp -r` ban:** dodged by `rsync`/`tar`; D5 measures bytes instead.
- **Age-only deletion inside live sessions:** tmpreaper's own README.security documents removing files a suspended process still needs — the opposite of INV-1.

## Lifecycle

- **Adoption:** D1-D4 ship together; from the first `start` after merge, new runs are bound. D7's wording reaches every repo with the next render + governance sync.
- **One-time legacy pass:** untagged leftovers (today's 73 G) are listed per session by `scratch_sweep.py` with holders and live-session status; the operator signs the list; only listed, unheld folders of sessions that agree (or dead sessions) are removed. Nothing untagged is removed without that list.
- **Growth:** D6 is the trigger — sustained alarms (> 3 sessions over 5 GB outside runs in a week) mean a command still writes outside its run folder; the agent seeing it routes the brief fix to kaizen.
- **Degradation:** every failure path keeps the folder (INV-1) and says why; a mint failure falls back to today's behaviour.
- **Retirement:** if the harness ever scopes scratch per task itself, D1-D3 retire and D4 stays as the legacy path.

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

Fetched 2026-10-14 and re-verified live 2026-10-15 by native `fabrik-researcher` seats (tools named per row):

- rename(2) — "Open file descriptors for oldpath are also unaffected"; for a directory, "newpath must either not exist, or it must specify an empty directory" — https://man7.org/linux/man-pages/man2/rename.2.html (exa fetch, firecrawl maxAge 0).
- open(2) — "this reference is unaffected if path is subsequently removed or modified" — https://man7.org/linux/man-pages/man2/open.2.html (exa fetch).
- unlink(2) — "the file will remain in existence until the last file descriptor referring to it is closed" — https://man7.org/linux/man-pages/man2/unlink.2.html (exa fetch).
- proc_pid_stat(5) field 22 starttime "expressed in clock ticks" — https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html (firecrawl, maxAge 0); pid + starttime not reuse-safe — a reader comment on https://lwn.net/Articles/1024448/ ("Process ids again", not an LWN editorial; exa search, firecrawl).
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

- `docs/workstation/cleanup-automation.md` § F (the scratch sweep's home) — the run-bound tier, the marker, INV-1..3, the alarm.
- `docs/workstation/hooks-index.md` — the hook's new alarm line.
- `commands/_fragments/subagents-core.md`, `commands/_fragments/review-probe-catalogue.md` — `RUN-SCRATCH` for seats (kaizen).
- `CHANGELOG.md`, `docs/DECISIONS.md` (D-864, the ruling row).

## Open / blocking unknowns

- **Resolved:** where the disposable tier lives (session scratchpad — judges); pid reuse (never the sole signal); rename atomicity (same directory, so same filesystem); the per-session record being overwritten (the marker carries state); hook removal (the hook never removes — D3 and D4 do); the session-directory path (found by `find_session_dirs`, never computed); a dead session's directory deleted whole (kept while it holds an active run folder).
- **Open — the D-836 worktree-write gap** (a worktree session cannot write its own durable `.tmp/runs` dir): infra's, OUT of this spec; destination mail `01M4Y3N9GW8N6HZ5D1QTFZPHWF` to infra.
- **Open — advisory thresholds** (2 GB seat, 5 GB session, 85 % disk, 72 h): resolution step = measure on ≥ 20 rounds after D1-D4 ship, then set by a D-row before D5/D6 can ever refuse.
- **Open — live thresholds** (30-minute done grace, 7-day dead-run heartbeat): these gate removal from the first day D3/D4 ship, so they start conservative; resolution step = the plan sets them in its first ticket's D-row from the measured gap between a lead's close and its seats' last write, and from today's longest-idle live session.
- **Accepted residual:** a background seat that holds no file open and writes nothing for 30 minutes after its lead closed the run, then writes again, finds its folder gone. The lead's duty to close only after every seat has handed back (§ Personas) is the guard; V2's grace test bounds it.

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
| I12 | the approved note's "a seat folder over 2 GB fails the round" | IN | § The delta — D5 ships advisory first (§ Decisions taken); the operator may overrule |
| I13 | "have you done spec review till reaching no ops convergence? if so proceed with next command" | IN | this review; receipt `docs/development/reviews/2026-10-15-scratch-lifecycle-spec-review.md` |
