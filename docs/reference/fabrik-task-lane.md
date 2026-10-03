# The /fabrik-task lane — operator guide

What it is, how agents choose it over the spec chain, and where each repo stands. The rules
themselves live in three places and are not restated here: the lane table in `CLAUDE.md` § Orient
step 0 (which lane a change takes), `commands/_sources/fabrik-task.md` (how a run goes) and
`docs/reference/command-run-protocol.md` (every flag and row field). Design:
`docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md`; ledger D-491, D-492, D-504, D-507.

## What the lane is

`/fabrik-task` is the path between a right-now fix and the spec chain (`/fabrik-spec` →
spec-review → plan → plan-review → execute). One decision, a six-field design note in the run
record, the build, a review sized by the surface, and a close that re-measures the commit. The
decision's row in `docs/DECISIONS.md` is the durable artifact; there is no spec or plan document.

## How an agent chooses — task or spec

The agent applies the lane table to the smallest change that discharges the ask, then runs
`command_run.py start --command fabrik-task …`. **The start IS the gate:** it either opens a record
or refuses, naming the lane the work belongs in. The agent does not argue with a refusal; it takes
the named lane. Every repo runs lane v2; a repo that commits `{"version": 1}` in its own
`.fabrik/lane.json` keeps the old gate. What decides, per version:

| | Lane v1 (pinned) | Lane v2 (default) |
|---|---|---|
| Goes to the spec chain | more than 3 declared files; a ONE-WAY decision; a trade-off to settle first | a contract path (`specs/services/`, `openapi*`, `*.schema.json`) or `consumers=external`; a ONE-WAY decision; a trade-off to settle first (with `--why`, ledgered); an appetite over 240 min |
| Sync path or heavy surface (auth, schema, migrations, gates) | refused to right-now + the full `/fabrik-review` | admitted (when there is a decision), and phase 4 runs the full `/fabrik-review` |
| More than 5 counted files (ledgers and Doc Sync destinations do not count) | spec chain (over 3) | admitted with the full review |
| No decision at all (`decision=no`) — a pure fix | refused to right-now + `/fabrik-review-scoped` (the full review on a sync or heavy surface) | the same |
| At close | undeclared paths recorded | undeclared paths refuse `done` until named (`--design-amend`); a close-time contract or 3+ new source files owe a full-review receipt |

An admitted `start` prints which version applied — `lane: v1`, or `lane: v2 (switch <commit>) · review: <scoped|full> · appetite: <n> min`; a refused start prints only its refusal.

## Where each repo stands (2026-10-02)

- **Every synced project and the hub run v2** (D-507): `scripts/task_lane.py` defaults to 2
  and the template's lane rows (`templates/governance/CLAUDE.md` § Orient step 0) describe v2;
  the governance sync carries both. The hub's own `.fabrik/lane.json` (3a803b44b) still pins 2.
- **A repo can stay on v1** by committing `{"version": 1}` as `.fabrik/lane.json`. The file is
  never synced, so the pin is that repo's own decision; an unreadable file falls back to the
  default with a warning on `start`.
- **fabrik-lib** is sync-excluded: its `scripts/command_run.py` predates the lane module and has
  no `task_lane.py`, so it runs the old gate until it adopts the files — requested by mail.

The hub-only week the spec planned (D12) was dropped by operator ruling on 2026-10-02: the lane
was built for every repo.

## What a running session sees

- **The command text and its router description** are rendered box-wide into `~/.claude/commands`
  and `~/.claude/skills`. A session reads a command's body when the command runs, so new runs get the
  new text, and the skill list a session shows (the descriptions the router selects on) refreshed
  in an open session after the render, observed 2026-10-02 — no reload needed for commands.
- **`CLAUDE.md`** is loaded at session start: a window opened before the governance sync rewrote
  its repo's `CLAUDE.md` keeps the old lane table until reloaded. The `start` gate itself reads the
  new rules at once, so an old window is refused or admitted by v2 even before its reload.
- **The quota dashboard's Commands tab** (`scripts/sysadmin/quota_dashboard.py`) reads the command
  sources live; it needs no restart.

## Measuring it

`python3 scripts/command_feedback_report.py --lane` (30 days by default; `--since <days>`, `--json`)
prints, per agent, the share of lane starts refused to the chain and the share downgraded back, the
task-to-spec ratio, the task median and UPGRADE share, the in-lane review median, small specs sent
back, the over-appetite share and which repos pin which version.
