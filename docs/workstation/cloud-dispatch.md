# Cloud dispatch — subagents that spend the cloud-session credit

Box-local subsystem (`scripts/cloud_dispatch.py`, registry `.fabrik/cloud-routines.json`), built
2026-10-14 on the operator's ask to use each account's $250 cloud-session credit (D-857). A local
subagent — the Agent tool, even with `isolation: "remote"` — runs on this box on the dispatching
account's subscription; the credit pays only for sessions on Anthropic's cloud. The only scriptable
way to start one is to fire a claude.ai **routine**, so every fleet account carries one,
`fabrik-cloud-worker`, and this script fires it. The three prepaid API credits are spent by a separate script,
[api-credit.md](api-credit.md) (D-1196).

## What a dispatch is

```
python3 scripts/cloud_dispatch.py list                      # accounts, fire path, weekly %, last ledger rows
python3 scripts/cloud_dispatch.py dispatch --slug fix-mail-tests --pick --task-file brief.md
python3 scripts/cloud_dispatch.py wait --slug fix-mail-tests --timeout 1800   # --since <sha> overrides the ledger's pre-fire sha
python3 scripts/cloud_dispatch.py log --account mob --session cse_01…
python3 scripts/cloud_dispatch.py settle --slug fix-mail-tests   # or --all: ledger the run's cost; pause on exhaustion
python3 scripts/cloud_dispatch.py pause can --reason "…" · unpause can · calibrate can --balance 212.40
python3 scripts/cloud_dispatch.py drain --batch batch.json [--max-open 10] [--dry-run] [--allow-plan-usage]   # § Draining a batch
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
refresh chain, 7 a paused or expired account (§ The credit guard). Shared flags `--registry`,
`--fleet-root`, `--ledger` go before or after the verb; `list` takes `--no-status` and
`--ledger-tail N`, `dispatch` takes `--task`/`--task-file`, `--force-new` and `--allow-plan-usage`,
`wait` takes `--since`, `--timeout` and `--interval` (floored at 1 s).

## Draining a batch

`drain` (W-b00d9d72, D-row in `docs/DECISIONS.md`) spends the credits through many runs. Each run's
lead writes a batch file, `[{"slug", "task" | "task_file", "files": [repo paths]}, …]`, choosing
items that are independent and cloud-sized; a `task_file` is read relative to the current
directory, not the batch file's. The script checks the whole batch before anything fires: every
task file is read and every payload rendered, and a pre-flight failure exits 8 (`drain_refused`)
with nothing fired and nothing ledgered:

- **one drain at a time** — `flock` on `<ledger dir>/cloud-drain.lock`, so two drains given
  ledgers in different directories do not exclude each other;
- **origin readable** — every git read checks its exit code, so a network failure refuses and is
  never read as "no open branches";
- **parity** — local `master` equals origin's (the cloud clones origin). The drain does not
  fast-forward anything: it refuses, and the main checkout's session fast-forwards master;
- **cloud-safe paths** — each a regular file at master (mode 100644 or 100755) or a new one,
  relative and in normal form (`.`, `..`, a directory, a symlink and a submodule refuse); not on the governance-sync filter (read from
  `command_run._sync_filter_source`, and an unreadable or uncompilable filter refuses); not in
  the deny set (`scripts/cloud_dispatch.py`, `.fabrik/cloud-routines.json`,
  `.pre-commit-config.yaml`, `commands/`, `scripts/sysadmin/`, any `conftest.py`); and no
  `tests/` file whose text at master names the home dir (`Path.home`, `expanduser`, `~/.claude`,
  `HOME`, `getpwuid`) — a substring screen, never a proof, which the merge rule below backs;
- **disjoint** — no path is listed twice, is in two entries, is in an unmerged `claude/*`
  branch's three-dot diff (renames split into both paths), or is held by a run in flight. A run
  is in flight when it fired within the last day and master does not yet carry its
  `Cloud-Dispatch: done <session>` trailer; it holds its `kind: drain` row's files, whether or
  not its branch is pushed yet. A plain `dispatch` run declares no files, so it holds a cap slot
  only;
- **cap** — open branches + in-flight runs + this batch ≤ `--max-open` (default 10, at least 1).

A slug with any ledger row that may have fired — `ok`, `unparsed`, `error` and every `http_<n>`
but 401 and 429 — is skipped as `already fired`, forever: re-running a stopped batch never fires
an entry twice, and a task whose run failed is re-run under a new slug. Each remaining entry is
re-checked against the ledger just before it fires (a sibling may have fired it since the
pre-flight), gets a `kind: drain` ledger row, and fires through `dispatch` by `--pick`, with
`Files you may change: …` appended to its task; `--allow-plan-usage` is passed to every fire. The
first failure stops the batch and exits with that fire's code, after the earlier entries have
fired and been ledgered. A pre-flight refusal prints only its reason; once the pre-flight passes,
stderr gets one line per entry, printed even when the batch stops: `fired`, `fired? (<status> —
read the ledger before retrying)`, `attempted (raised before a result — …)` (its drain row was
written, then the fire raised), `refused rcN`, `already fired`, `already fired (by another session,
after the pre-flight)`, `not reached` or (on `--dry-run`) `would fire`. A run has landed once
master carries its done trailer: the fire records the session as `cse_<id>` and the worker's
trailer names it `session_<id>`, so the two are compared by the part after the prefix.

**Merging a drained branch** (the lead's rule, from the panel's verdict): the branch's three-dot
diff must stay inside its declared files. A local spot-check is mandatory for more than 5 files,
any conftest or test-infrastructure change, or a receipt whose SHA is not the tip; other branches
are sampled, and every branch is checked for each account's first two runs. The merge deletes the
remote branch, because each drain fetches every listed `claude/*` branch and runs a merge-base
check on each.

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
be parked, paused or expired, and a CLI account's refresh chain must be neither expired nor expiring
within a day), then the **fewest ledger dispatches in the last 7 days**, then the highest weekly %
(the LOWEST under `--allow-plan-usage`: plan spend goes to the coolest account). A status row that
is a cached reading older than 6 h does not qualify its account, and when no account qualifies the
dispatch is REFUSED (exit 3, `no_account` — pass `--account`), never guessed. The weekly reading
comes from `claude_rotate.py --status --json` — a live probe; `list --no-status` skips it.

## The credit guard

Operator rulings 2026-10-14: *"we should not consume our account's quota"* · *"each has 250$
credits. when credits consumed, it must be paused"* · *"weekly usage is different than cloud 250$
credits"*. The guard counts DOLLARS against each account's declared credit; the weekly plan reading
is only an advisory.

- **Cost per run.** `settle --slug <s>` (run by `wait` on success; `settle --all` by every
  `dispatch` first) reads the run's raw events — `GET /v1/code/sessions/<cse>/events` (newest
  first) with the account's OAuth ACCESS token from `~/.claude-fleet/<slug>/.credentials.json`,
  read under the routine token's descriptor checks and never printed — and appends a `kind: settle`
  row: the newest `result` event's cumulative `total_cost_usd` (Claude Code's list-price estimate;
  measured $0.32 for the 4-minute probe), the token counts, `plan_5h`/`plan_7d` (0–1 fractions),
  `using_overage` and the last `rate_limit_info` verbatim. The routine token cannot read it (401
  `oauth_scope_insufficient`).
- **The standby token lapses in hours** and no script-side refresh exists (the grant is CLI-only),
  so when `expiresAt` has passed and a settle is owed, ONE in-place
  `claude -p ok --max-turns 1 --tools ""` from the scratch dir rolls that account's chain
  (sub-cent of plan, ledgered as `kind: token_refresh`, at most once per account per 8 h). A run
  that still cannot be read is ledgered `settle_pending` (`/login` in that account's dir is the
  remedy) and retried by the next `settle --all` — except a session whose token the API REFUSED
  (401/429) within the last 8 h, which the automatic sweep leaves alone (`settle --slug` always
  retries). A malformed `credit` block (claimed not a number ≥ 0, expires not `YYYY-MM-DD`) is a
  registry error naming the field, refused at load by every verb.
- **Spend** per account = the latest real-cost settle per fired session; every fired session with
  no real cost yet is PROVISIONED at the margin from the moment of dispatch (never a free window;
  settling twice never double-counts); `plan_usage` rows are excluded. `calibrate <slug> --balance
  <usd>` records the balance the web shows (claude.ai/settings/usage — the only place it is
  visible): spent = (claimed − balance) + the rows fired after it. Margin = `max($10, 10 % of
  claimed)` ($25 on $250; `credit_margin_usd` overrides) — the estimate is not Anthropic's ledger
  and parallel runs pass the check while in flight.
- **Pause** = ledger rows `kind: pause|unpause` (latest wins) under the ledger's flock — never the
  git-tracked registry, which a worktree, a checkout or a merge would silently un-pause. A settle
  reads the rows, computes the spend and writes its settle row AND the pause row under ONE exclusive
  lock (`LedgerTxn`), so two settles racing on the same account cannot each see only their own cost
  and both pass the threshold. Automatic
  when spent ≥ claimed − margin, or when the run drew on overage (`isUsingOverage` — recorded, not
  yet trusted: the captured probe shows overage DISABLED on these accounts, so the dollar counter is
  primary). A rise of the weekly plan reading on an IDLE account between two settles is printed as
  an advisory, never a pause (the browser, a CLI fire and `log` all move it; the active account is
  blind). `pause <slug> --reason` / `unpause <slug>` by hand.
- **Refusals** (exit 7): `dispatch`/`--pick` refuse a paused account and any account within 6 h of
  00:00 UTC on its `credit.expires` date (Anthropic's day, never this box's).
  `--allow-plan-usage` bypasses both, tags the row `plan_usage: true`, picks the coolest weekly
  reading and prints that it spends plan quota — the one sanctioned way to do so.
- `list` prints per account `credit: spent · left · N unsettled · expires (in d) · PAUSED since
  (reason)` and the ledger path it summed.

Cobra line (D-253): the cheapest way to read "never paused" is to never settle — which is why an
unsettled run is charged at the margin, not at zero; and the cheapest way to silence a pause is to
edit the registry — which is why the pause state is not there.

## Registry and routines

`.fabrik/cloud-routines.json` maps fleet slug → `trigger` (`trig_…`) + a `github` note + the static
`credit: {claimed_usd, expires}` (optional top-level `credit_margin_usd`). The four
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
- Billing: a run draws the account's PLAN usage (5-hour and weekly) first, like an interactive
  session; usage credits pay only as overage past the plan limit, and only where overage is turned
  on at claude.ai/settings/usage — without it a run at the wall is rejected
  (code.claude.com/docs/en/routines § Usage and limits, fetched 2026-10-25). Measured W-b00d9d72:
  each of the five fires so far opened a fresh 5-hour window on its account (reset ≈ fire + 5 h,
  idle accounts included), and every run's `rate_limit_info` reads `overageStatus: rejected`
  (`org_level_disabled` on can, ozgurbasak and mob, `out_of_credits` on ob). So the dollar guard
  above bounds the credit, not the plan draw: an account near its weekly wall cannot spend credit
  until overage is on. The credit balance is visible only at claude.ai/settings/usage (no endpoint
  exposes it) — the guard counts the per-run cost estimate against the declared credit and takes
  the web balance by `calibrate` whenever the operator reads it.

## Related scripts

- `scripts/cloud_dispatch.py`

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/cloud_dispatch.py`
<!-- END related-scripts -->
