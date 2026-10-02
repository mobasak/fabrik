# The /fabrik-task lane — operator guide

What it is, how agents choose it over the spec chain, and where each repo stands. The rules
themselves live in three places and are not restated here: the lane table in `CLAUDE.md` § Orient
step 0 (which lane a change takes), `commands/_sources/fabrik-task.md` (how a run goes) and
`docs/reference/command-run-protocol.md` (every flag and row field). Design:
`docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md`; ledger D-491, D-492, D-504.

## What the lane is

`/fabrik-task` is the path between a right-now fix and the spec chain (`/fabrik-spec` →
spec-review → plan → plan-review → execute). One decision, a six-field design note in the run
record, the build, a review sized by the surface, and a close that re-measures the commit. The
decision's row in `docs/DECISIONS.md` is the durable artifact; there is no spec or plan document.

## How an agent chooses — task or spec

The agent applies the lane table to the smallest change that discharges the ask, then runs
`command_run.py start --command fabrik-task …`. **The start IS the gate:** it either opens a record
or refuses, naming the lane the work belongs in. The agent does not argue with a refusal; it takes
the named lane. What decides depends on the repo's lane version:

| | Lane v1 (default) | Lane v2 (opted in) |
|---|---|---|
| Goes to the spec chain | more than 3 declared files; a ONE-WAY decision; a trade-off to settle first | a contract path (`specs/services/`, `openapi*`, `*.schema.json`) or `consumers=external`; a ONE-WAY decision; a trade-off to settle first (with `--why`, ledgered); an appetite over 240 min |
| Sync path or heavy surface (auth, schema, migrations, gates) | refused to right-now + the full `/fabrik-review` | admitted (when there is a decision), and phase 4 runs the full `/fabrik-review` |
| More than 5 counted files (ledgers and Doc Sync destinations do not count) | spec chain (over 3) | admitted with the full review |
| No decision at all (`decision=no`) — a pure fix | refused to right-now + `/fabrik-review-scoped` (the full review on a sync or heavy surface) | the same |
| At close | undeclared paths recorded | undeclared paths refuse `done` until named (`--design-amend`); a close-time contract or 3+ new source files owe a full-review receipt |

An admitted `start` prints which version applied — `lane: v1`, or `lane: v2 (switch <commit>) · review: <scoped|full> · appetite: <n> min`; a refused start prints only its refusal.

## Where each repo stands (2026-10-02)

- **The hub (`/opt/fabrik`)** runs **v2** since 3a803b44b (`.fabrik/lane.json` = `{"version": 2}`).
  Its `CLAUDE.md` lane table describes v2.
- **Every synced project** has the new code (`scripts/task_lane.py` ships with
  `scripts/command_run.py`) but no switch, so it runs **v1** — exactly as before. Its `CLAUDE.md`
  lane rows (from `templates/governance/CLAUDE.md`) still describe v1.
- **fabrik-lib** is sync-excluded: its `scripts/command_run.py` predates the lane module, so it
  runs v1 until it adopts the new files (a mail at the flip).

## Rollout

The hub runs v2 for seven days first (spec D12). On or after 2026-10-09 work item W-6b257bdd reads
`python3 scripts/command_feedback_report.py --lane --since 7` and the refusal ledger
(`~/.claude/state/lane-refusals.jsonl`). If the week shows no refusal the replay fixture did not
predict, ONE commit flips `task_lane._LANE_DEFAULT` to 2 and rewrites the template's lane rows, so
every project moves to v2 on the next sync; fabrik-lib and Volkan's port are mailed the rule text.
A project can stay on v1 by committing `{"version": 1}`.

Opting a single repo in before the flip is possible (commit `.fabrik/lane.json` `{"version": 2}`
ALONE), but not advised: its `CLAUDE.md` rows would still describe v1, so its agents would read one
rule while the gate enforces another.

## What a running session sees

- **The command text and its router description** are rendered box-wide into `~/.claude/commands`
  and `~/.claude/skills`. A session reads a command's body when the command runs, so new runs get the
  new text, and the skill list a session shows (the descriptions the router selects on) refreshed
  in an open session after the render, observed 2026-10-02 — no reload needed for commands.
- **`CLAUDE.md`** is loaded at session start: hub windows opened before the change keep the old lane
  table until reloaded.
- **The quota dashboard's Commands tab** (`scripts/sysadmin/quota_dashboard.py`) reads the command
  sources live; it needs no restart.

## Measuring it

`python3 scripts/command_feedback_report.py --lane` (30 days by default; `--since <days>`, `--json`)
prints, per agent, the share of lane starts refused to the chain and the share downgraded back, the
task-to-spec ratio, the task median and UPGRADE share, the in-lane review median, small specs sent
back, the over-appetite share and which repos pin which version.
