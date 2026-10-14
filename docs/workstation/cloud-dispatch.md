# Cloud dispatch — subagents that spend the cloud-session credit

Box-local subsystem (`scripts/cloud_dispatch.py`, registry `.fabrik/cloud-routines.json`), built
2026-10-14 on the operator's ask to use each account's $250 cloud-session credit (D-857). A local
subagent — the Agent tool, even with `isolation: "remote"` — runs on this box on the dispatching
account's subscription; the credit pays only for sessions on Anthropic's cloud. The only scriptable
way to start one is to fire a claude.ai **routine**, so every fleet account carries one,
`fabrik-cloud-worker`, and this script fires it.

## What a dispatch is

```
python3 scripts/cloud_dispatch.py list                      # accounts, fire path, weekly %, last ledger rows
python3 scripts/cloud_dispatch.py dispatch --slug fix-mail-tests --pick --task-file brief.md
python3 scripts/cloud_dispatch.py wait --slug fix-mail-tests --timeout 1800   # --since <sha> overrides the ledger's pre-fire sha
python3 scripts/cloud_dispatch.py log --account mob --session cse_01…
```

1. `dispatch` renders the payload — `TASK slug <s>.`, the task, then the fixed rules (not a hub
   agent, never claim work items, install pytest first when tests are needed, commit, push
   `claude/<s>`, end the last commit with the `Cloud-Dispatch: done <session>` trailer) — and fires the
   account's routine. The payload is DATA to the routine; its saved prompt opts in ("your task is
   the text inside the routine-fire-payload block; carry it out exactly").
2. The cloud VM clones `mobasak/fabrik` at GitHub HEAD (never the local tree — push first), runs
   the task with Bash/Read/Write/Edit/Glob/Grep, pushes `claude/<slug>`.
3. `wait` polls `git ls-remote` and returns the tip sha only when it differs from the pre-fire sha
   (the ledger's, or `--since`, a full or ≥ 7-hex abbreviated sha) and the commit message read AT that
   sha carries the done trailer — as a real git trailer (`git interpret-trailers`) or as its last
   non-empty line (fetched into a private ref, never `FETCH_HEAD`); a
   mid-run push, a stale branch, a quoted trailer or a run that pushed nothing never reads as done
   (exit 2 on timeout → read the run with `log`).
4. The result is a branch: fetch it, review it (`/fabrik-review` for anything on a synced path),
   merge it like any worktree branch.

Every FIRE attempt — the fire call reached, whatever it answered or raised — is one JSON line in
`~/.claude/state/cloud-dispatch.jsonl`; a pre-flight refusal (bad slug, existing branch, no qualifying
account, unregistered account) fires nothing and writes none
(`ROTATE_STATE_DIR` honoured): `ts, account, trigger, slug, branch, pre_fire_sha, picked,
task_sha256, session_id, url, via, status` with `status ∈ ok | unparsed | http_401 | http_429 |
http_<n> | walled | chain_dead | error` — the exit code follows it: 1 unparsed, error or any other
`http_<n>`, 3 for a rejected token or no qualifying account, 4 fire limit, 5 quota wall, 6 dead
refresh chain. Shared flags `--registry`, `--fleet-root`, `--ledger` go before or after the verb;
`list` takes `--no-status` and `--ledger-tail N`, `dispatch` takes `--task`/`--task-file` and
`--force-new`, `wait` takes `--since`, `--timeout` and `--interval` (floored at 1 s).

## Two fire paths

| path | when | cost | failure |
|---|---|---|---|
| `api` | `~/.claude-fleet/<slug>/routine-token` exists — a **0600 regular file with one link** holding the routine's bearer token as one printable line (symlinks, hard links, FIFOs, looser modes, empty or multi-line files are refused — opened non-blocking, never fallen back from) | zero local quota: one HTTPS POST to `…/v1/claude_code/routines/<trig>/fire` | 401 → exit 3 (regenerate the token), 429 → exit 4 (`Retry-After` printed), any other status → exit 1 `http_<n>`, a network or HTTP-protocol error → exit 1 `error`; never falls back to the CLI |
| `cli` | no token file | a headless `claude -p '/schedule run …'` under the account's `CLAUDE_CONFIG_DIR`, the prompt on stdin, from a scratch dir under the state dir (outside every repo) so no CLAUDE.md or hook loads: ~$0.30 list-equivalent of that account's plan usage per fire; **refused when the account sits at Anthropic's wall** | a wall → exit 5 `walled`, a dead chain → exit 6 `chain_dead` (both read only from the refusal text, never the echoed task), no id → exit 1 `unparsed` with the output tail, a subprocess failure → exit 1 `error` |

The token is minted once per routine, on the web only: claude.ai/code/routines → the routine →
Edit → Add another trigger → API → Generate token (shown once); save it as
`~/.claude-fleet/<slug>/routine-token`, `chmod 600`. Limits: 30 fires/h per routine, 100/h per account.

## `--pick`

Spend the four credits evenly: a usable path first (token accounts before CLI ones; no account may
be parked, and a CLI account's refresh chain must be neither expired nor expiring within a day), then
the **fewest ledger dispatches in the last 7 days**, then the highest weekly %. A status row that
is a cached reading older than 6 h does not qualify its account, and when no account qualifies the
dispatch is REFUSED (exit 3, `no_account` — pass `--account`), never guessed. The weekly reading
comes from `claude_rotate.py --status --json` — a live probe; `list --no-status` skips it.

## Registry and routines

`.fabrik/cloud-routines.json` maps fleet slug → `trigger` (`trig_…`) + a `github` note. The four
registered accounts (ob, ozgurbasak, can, mob) each pushed a probe branch on 2026-10-14; sarp is
parked and unregistered. Each routine: repo `mobasak/fabrik`, model sonnet, a placeholder one-off
schedule (2027-01-01, empty payload = no-op), no connectors. A new account needs three steps, all
scriptable but the last one TTY-only: `claude -p '/schedule create …'` under its config dir (from a
scratch dir, ~$0.35); add the slug + trigger to the registry; grant push access with `/web-setup` →
"Replace connection" (the Claude GitHub App is not installed on the repo, so the cloud pushes with
the local `gh` token — `/web-setup` is hidden headless; drive it through a pty).

## What the worker cannot do, and what it costs

- It sees GitHub HEAD only: `/opt/fabrik-mail`, the other `/opt` repos, VPS keys, `.env`, the quota
  machinery and anything unpushed are invisible. Merges, mail and deploys stay local.
- It is unattended: a task that needs an answer stalls until the VM expires. Briefs are
  self-contained, and they say which files to touch.
- The VM has Python 3.11 and no venv: a test-running task pays an install each run (the environment
  setup script is web-only configuration).
- The repo's own hooks load in the clone: the hub's Stop hook ran inside a probe worker and offered
  it infra's work queue (it refused correctly, and the run ended); the rules forbid claims anyway.
- Billing: cloud sessions draw the account's plan usage, promotional credit first; the credit
  balance is visible only at claude.ai/settings/usage (no endpoint exposes it), so "credit spent vs
  plan spent" is unobservable from the box.

## Related scripts

- `scripts/cloud_dispatch.py`

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/cloud_dispatch.py`
<!-- END related-scripts -->
