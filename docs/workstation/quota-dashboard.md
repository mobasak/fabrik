# Command centre — the quota dashboard (box-local, `localhost:5051`)

**What it is:** the operator's command-and-control page for the box, in a browser tab you leave open.
Six views behind one navigation — **Overview** (what needs you now), **Work**, **Accounts**, **Usage**,
**Commands**, **Services** — over the same collectors the old five-tab board read: every Claude
account's session (5h) and weekly headroom from `claude_rotate.py --status --json`, every repo's work
store, every agent's run records, the box budget, the spend sidecar, the command corpus, the pool and
search-API balances. It decides nothing and never touches a credential file; its only writes are the
operator's own clicks, relayed to `work.py` and the rotation CLI (§ Boundaries).

**Open it:** <http://localhost:5051/> (works from Windows too — WSL forwards loopback). Each view has
its own URL — `/#overview` (the default), `/#work`, `/#accounts`, `/#usage`, `/#commands`,
`/#services` — so a link or a reload lands where it was; `/#work/<repo>` opens one repo's pane.

Tool: `scripts/sysadmin/quota_dashboard.py` (the server, the collectors, the probe loop) and its page
layer `scripts/sysadmin/dashboard_ui/` · Output: `~/.claude/quota-dashboard/quota.json` (and the
pool/search-API caches beside it) · Log: `~/.claude/quota-dashboard.log`. The redesign is plan
`docs/development/plans/archived/2026-10-17-plan-1-command-centre-dashboard/` over spec
`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` (D-925).

## The page layer

```text
scripts/sysadmin/dashboard_ui/
  components.py   every HTML builder — the ONLY code that writes markup; every value escaped
  strings.py      the string catalogue: every word the page shows (D-926); `t(key)`, `use(mapping)`
  fmt.py          the shared formatters (ages, resets, the posture sub-line) — words from the catalogue
  snapshot.py     the decision card's snapshot token
  merges.py       the fleet-wide blocked-merge reader
  views/          one module per view: render(data, ctx) -> ViewResult, optional collect(ctx)
    overview.py work.py accounts.py usage.py commands.py services.py
  static/app.css  one stylesheet: one palette, light / dark / system, computed contrast
  static/app.js   every client behaviour, declared by markup attributes (posts, dialogs, filters, refresh)
```

The package never imports `quota_dashboard` (that module runs as `__main__`; a second import would
split its registries): the server hands each view its data (`_view_data`) and wraps the markup the view
returns. Three invariants are graded, not hoped for: no string holding an HTML tag is built anywhere but
`components.py` and no view hands a component a literal word (INV-4 —
`tests/test_quota_dashboard_page_layer.py`, an AST scan); every view rendered under a stand-in
catalogue shows no catalogue-owned English (the same file); and every datum and control the old five
tabs showed renders in some view (INV-2 — the same file's inventory). The old page builders (31 of them,
`_repos_page`, `render`, `_agents_block`, the panels and cells) were deleted with the redesign (T07).

**Render-time baseline** (the spec's growth trigger: a view whose render exceeds 500 ms moves its
collector onto the probe loop's cache): measured at T01 on the live box, the old page's `generate()`
took 1,619 ms and `_repos_page(fresh=True)` 1,505 ms — the costs the Overview and Work views now carry
per refresh through the 20 s collector cache.

## The views

### Overview — what needs you now (the default)

One summary strip (decisions waiting per repo with the oldest age, blocked merges, agents not working,
the quota band and the active account, any health fault — each a link to its section), then, by
urgency: **Decisions waiting** (every `awaiting-operator` item across `/opt/*/.fabrik/work`, grouped by
repo with the hub's group first and expanded, the others collapsed to their count; a card per item with
its ground, the question clamped to three lines with *Show all*, the asking agent, the wait; *Accept* and
*Reject* on a decision, *Comment* on every card), **Blocked merges** (read-only; the card names the merge
owner who must act), **Agents** (one table per repo — state, NOW, Holds, NEXT with its queued count,
last merge or "merge owner", paused by / at / why and a partial pause, "not honoured here" until a repo's
work.py syncs, windows, named-from, the dormant count per repo, and Pause / Resume), the **Quota** strip
(band, active account, successor, the three windows with resets, the hold tier, the next relief) and the
**Health** strip (stale views, failed collectors and probes, and the box-budget line). On a RED or WALL
band, or a failed probe, the Quota and Health strips move above the decisions.

The **box-budget line** is `dispatch_headroom.py --json` reduced to what the box AND the quota allow
right now — read-only and heavy seats allowed, the box cap and the sibling reservation, the CLI cap, the
quota line (or the fleet hold at 0 seats) — with the script's own degraded-state reasons as caveats
(`_budget_reading`, `_budget_caveat_lines`; a heavy-only cause is labelled "heavy half —"). It is served
from a 60 s cache that one background probe refreshes (`_budget_cached`); it never runs on a request
thread, and an account switch bumps the cache's generation so a probe already in flight cannot land the
old account's reading. `QUOTA_DASH_BUDGET=0` disables it (the tests).

**Agents** are `scripts/agent_status.py`'s `collect_box`, loaded by path: a repo's agents are its open
windows (interactive `claude` processes, named by `CLAUDE_AGENT`, else their worktree, else the newest
run record's agent), plus the agents with a run record of that repo in the last 7 days and those holding
a claim; older agents are counted as dormant, not listed. **Pause / Resume** (W-7159f8e2) appears on a
row whose repo's store has `config.json`; Pause asks for an optional reason in its confirm dialog, Resume
names every marker it lifts and who set the first. Both post `/agent-pause`; the board runs the HUB's
`work.py --repo <repo> pause|resume` as the OPERATOR (the child gets only PATH, HOME, LANG, LC_* and
TZ) and every rule about who may pause stays `work.py`'s (D-910).

### Work — every repo's remaining work

The repo picker (`fabrik` first, then by how much remains), the **Tag** filter, and per repo: a summary,
owner chips with counts (**All**, the hub agents at 0 too, `operator` and other owners by name,
**(unassigned)** last; an unowned awaiting decision counts under `operator`), the skipped-file list, and
one closed section per owner — a table of id, kind, status, priority, title, next step (capped at 160
characters, the rest behind a disclosure up to 600), tags, live claim and the **Operator** cell:
*Accept* and *Reject* (each with its confirm dialog; Reject needs a reason) on every open item except an
awaiting non-decision, and a comment box (Enter saves). Rows run awaiting-operator first, then priority,
then id. "Remaining" is `work.py`'s own rule, imported by path. The chip, the tag and the picked repo are
kept by `app.js` (the hash and `localStorage`), and the 20 s refresh keeps them.

Every verdict posts `/item-verdict` with the card's **snapshot token** — a hash of what the card showed
(question, status, ground, comment count, merged duplicates). The server re-derives it from the item as
it stands and answers **409 `changed`** when they differ, or **409 `diverged`** when the board's tree and
the repo's main checkout disagree about the item; the page then says so in its live region and reloads
the view. A verdict with NO token — a page loaded before the redesign — is accepted only through
`_LEGACY_TOKEN_UNTIL` (**2026-10-31**, the redesign's coding date plus 14 days, inclusive), then refused
with the same 409. What accept and reject do to an item is `work.py verdict`'s
(`docs/reference/work-tracking.md`).

### Accounts — which account serves, which comes next

The banners (live probe failed, auto-rotation paused by the operator marker, pause state unreadable, no
accounts reporting), the fleet **Warnings**, the **quota governor**'s verdict, and the accounts in
**rotation order** with a rank badge each — `#1 ACTIVE`, `#2 NEXT`, `#N in line`, `#N — returns <time>` —
then the active account's own return slot (a ghost row when it will be flipped away and come back at its
reset) and the scaffolded-but-unlogged `pending-login` dirs ("One /login in this directory pins it").
Each row: session (5h), weekly and Fable meters, and an **Edit** disclosure holding Switch, Disable /
Enable, the weekly cap and the rotate-at line, each behind a confirm dialog. Below the table, the rotation
rule with the flip threshold and the probe interval.

| Element | Meaning |
|---|---|
| `N% left` | **remaining** headroom (the CLI prints *used*); green >25%, amber 6–25%, red ≤5% — red is where the fleet abandons the account |
| `cap N%` · `RESERVED — fleet excluded` · `WALLED` · `PARKED — out of service` | a `caps.json` reserve · weekly at its cap (automated flips skip it; `--switch` may still target it) · weekly ≥ 100% · taken out of service (`--park`) |
| `cached Nh ago` | the account is idle, so its token is stale; the reading is the last known one with its age |
| `idle` in a window cell | the account is NOT the active pointer and its cached reading is older than the window (or the reading's own reset has passed): its window is empty by construction. On a capped account it adds "browser use is not visible here" |
| `unknown` in a window cell | the ACTIVE account with a reading older than its window — it CAN be burning quota, so no number is shown |
| Fable column | Fable-5's separate weekly limit, read from the usage payload's `limits` array (`scope.model.display_name == "Fable"`); `no reading` until the tick re-probes an idle account |
| `0.60%/m, wall in ~48m` on the active row | the rotation tick's smoothed burn and whichever of the wall or the reset comes first, RELAYED from the `posture` key of `claude_rotate.py --status --json` (the tick's own reading, the one the `QUOTA:` prompt line shows — D-273); the board re-derives nothing. A standby row carries none, deliberately |

**Row order = rotation order** (`_queue`, the read-only mirror of the tick's `_pick_flip_target`):
eligible standbys perishable-first (soonest weekly reset, then lower weekly, then lower session), then
the ineligible tail by WHEN each returns — a session-spent account back in two hours precedes a
cap-walled one back next week. A parked account is never shown returning.

### Usage — what did we spend

The cost sidecar `claude_p_cost.json` (rebuilt by the 06:00 cron): tier-weighted subscription spend over
its rolling window with `built_at`, the fee breakdown when the window's months carry fees, a reconcile
line, and a daily calendar per month. Tokens no tier claimed are named in a warning that survives the
no-tiers path; a missing or unreadable sidecar is said in words, never a zeroed table.

### Commands — what each `/fabrik-*` command does

A searchable catalogue in pipeline order — `#`, command, stage, purpose, when to use, skip when, next,
native subagents, model tiers — parsed live from each command's own `description:` under
`commands/_sources/` (the successor from the assembler's `NEXT` map; the order from `PIPELINE_ORDER`),
with per-command detail, and the **service matrix** as its own tab: which outside-the-box service each
command actually reaches, a dot meaning the command names that service's own invocation token
(`fanout(`, `WebSearch`, `mcp__firecrawl`, `fabrik apply`), never a prose mention.

⚠️ **The matrix reads `~/.claude/commands/`, the RENDERED corpus** (`QUOTA_DASH_RENDERED_COMMANDS`):
the assembler appends the shared pool and mail fragments, so the sources under-report. A command with
no rendered file falls back to its source and the caveat names which rows did. HTML comments (the
corpus keeps the pool contract inside POOL OFF comments for re-enable, D-181/D-182) and the shared
boilerplate are blanked before any detector runs; the `pool` and `flywheel` columns are tombstones whose
expected count is 0. The intro states the method's limits: a literal match reads no negations, and a
rewrite that keeps a file's mtime and size is invisible to the cache. **Adding an external service to
the fleet means adding a row to `_EXT_SERVICES` in `quota_dashboard.py`** — the page says so too. The
native-subagents cell leads with the command's own dispatch RULE (an Opus floor, the unit it fans over,
or a fixed floor), then the seat types and their tiers.

### Services — are the external services healthy and funded

The **OpenRouter pool** balance (shown once, here; a level, not a projection — HTTP 402 is issued on
balance; amber at or under `POOL_CREDITS_WARN_USD`, red at zero with what you will see, "endpoint
unreachable" with its age when served past its TTL, "not configured" when there is no key), the
**search-API quotas** (Brave, Firecrawl, Exa — plan, remaining, renewal; every value that cannot be
obtained says why), and the **external-services inventory** — the registry's providers rendered in place
by `dashboard_ui/inventory.py` (the same function writes `external-services-dashboard.html` for the 06:00
chain's `scripts/gen_dashboard.py`): a summary, the Needs-attention list, the categories as collapsed groups
with a filter (a name, Cost, Status) and the untriaged queue.

**The registry read** runs in a CHILD PROCESS, `scripts/sysadmin/inventory_read.py` — the one place psycopg2
is imported, so the board stays stdlib and a missing driver is only this section's error state. The
collector (`_inventory`) spawns it under `sys.executable` with a deadline 4.5 s after the arrival of the
request that spawns it and kills it at that deadline (a request that joins the read shares that deadline
and waits up to its own 5 s), so the section answers inside the request's 5 s whatever Postgres does; the
child also bounds itself with a SIGALRM a moment past that deadline, should the board be gone, and reads
the registry in ONE read-only REPEATABLE READ snapshot, so a read that straddles `registry_sync`'s commit
never shows pre-sync rows under the post-sync `synced_at` (W-a4bc74a6); one
lock guards the last good read and the read in flight (never held across a read), concurrent requests
share one child, and the last good read is served for 60 s from its start. A failed or killed read is
the section's error state, `<ExceptionClass>: <first line>` and nothing more, with Retry; the pool and API
cards render beside it. No connection is ever cancelled. The Services view has no timed refresh: it loads
on navigation, on `visibilitychange` and on a forced refresh.

**The pool drain advisory.** When the balance falls to `POOL_CREDITS_WARN_USD` or below, the board sends
ONE mesh-notify (the rotation tick's notify path) for the drain episode, latched by
`<OUT_DIR>/pool-credits-drained`; the latch is cleared — re-armed — the moment the balance recovers
above the line. An unknown balance (no key, an unreachable endpoint with nothing cached) is silence,
never a false alarm.

Both balances are fetched OFF the render path, on the probe loop's cadence behind their TTLs, and cached
beside `quota.json`; a view reads the cache only (`fetch=False`), so a third-party endpoint is never on a
page load's critical path. Keys come from the MCP configs and the pool's key file and are never
rendered, logged or cached.

| Service | Endpoint | Gives us |
|---|---|---|
| **Firecrawl** | `GET https://api.firecrawl.dev/v1/team/credit-usage` | `remaining_credits`, `plan_credits`, `billing_period_end` — one call, no credits spent |
| **Brave** | none — the quota IS the rate-limit header on a search response | `X-RateLimit-Limit/Remaining/Reset`, `"<per-second>, <monthly>"`. ⚠️ probing costs one search query |
| **Exa** | none reachable | usage needs a team-management SERVICE key (ours gets 403) and returns spend, never a balance or a renewal |

⚠️ **Brave's monthly `0` means UNLIMITED** ("15,000 requests per month (0 for unlimited)",
[rate limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting)), and
`X-RateLimit-Reset` is **seconds remaining**, not an epoch. Both are pinned by graders.

## How it stays current

**The server probes every `QUOTA_DASH_PROBE_INTERVAL_S` (20 s) whether or not a page is open**
(`_start_probe_loop`), writes `quota.json` and the in-memory reading (`_LAST_STATUS`), and hands the
payload to the rotation trigger. `generate()` is that probe pass and nothing else — no page is written;
it is serialized, so the loop, a view and a switch never run two probes at once. A failed probe keeps
the last good payload (marked `probe_failed`, which lowers the trigger's bar) and records the failure's
class; a pass that raises for any other reason records its class the same way (W-6a0f3c65).

**Each view refreshes its own region** by fetching `GET /v/<view>` at its cadence — Overview, Work and
Accounts every 20 s (`data-refresh-s` on the fragment), the others on open and on demand — and swaps it
only when its `data-stamp` changed. The refresh never clobbers the operator (INV-5): it is skipped while
a field has focus, a dialog is open or text is selected; typed text, open disclosures, scroll and focus
are carried across a swap; the refresh after the operator's own write is forced past the skips but
waits for an open dialog. The work stores and the agents are read through one cache of
`QUOTA_DASH_REPOS_TTL_S` (20 s) shared by every view and tab, dropped by every board write.

**The quota views (Overview, Accounts) carry the stale banner** when the reading is old: the probe
failed after the last good reading (it names when and the error class — never the message, which can
carry paths), or no probe has finished for one interval plus one timeout plus a minute (140 s by
default — what a hung probe or a restarted process looks like). That one bound (`_stale_after_s`) is
also when the Overview's Health strip lists the reading as stale, so the strip and the banner never
disagree. **No request ever waits on a probe:** a moved fleet pointer starts ONE background
regeneration (at most once per `QUOTA_DASH_PROBE_TIMEOUT_S`, none while one is already running) and the
NEXT refresh shows the new account; a reading older than `QUOTA_DASH_MAX_AGE_S` starts one too. A
regeneration that raises records its error class (the banner names it) and its thread ends cleanly.

**The rotation trigger — the fast path to a flip.** After each probe, if the ACTIVE account's 5h window
is at/over its flip line (`thresholds.json`'s entry, else `ROTATE_THRESHOLD`, default 99 — pinned equal
to the tick's own default) or it is cap-walled; or, on the urgent-drain tier, at/over
`ROTATE_URGENT_DRAIN_PCT` (90); or, while the probe is blind, at/over the drain line
(`ROTATE_DRAIN_THRESHOLD`, 85); or, on the relief tier, the active's hottest window at/over the drain
line with another account eligible and cool (`_relief_candidate`) — the server runs
`claude_rotate.py --tick` at once, on its own thread, under the cron's own lock, once per
`QUOTA_DASH_TRIGGER_COOLDOWN_S` (120 s) per tier. The tick keeps every safety it has; this only shortens
the latency from the `*/5` cron (the backstop) to the probe interval.

**Idle accounts show `cached Nh ago` by design** — `--status` is a ping-free read; only the active dir's
fresh token is probed live. Idle-cache freshness is the `*/5` rotation tick's job
(`claude-account-rotation.md` § Cron PATH if idle ages climb without bound).

## Routes and the request guard

Every request first passes the **Host allowlist** (INV-6): the server answers only `127.0.0.1:<port>`,
`localhost:<port>`, `[::1]:<port>` and the configured `QUOTA_DASH_HOST` at the bound port; anything else
(a DNS-rebinding page reaching the socket under its own name) is `421` before anything runs. A POST — or
a `GET /v/<view>`, which re-reads the stores and republishes targets — whose `Sec-Fetch-Site` is
`cross-site` is `403` before its body is read — and so is a cross-site `GET /quota.json`, which can start a
regeneration too. Every POST also needs the custom `X-Quota-Dash` header
(a cross-origin page cannot add one without a preflight this server never answers), a body of at most
4,096 bytes, and a target the board itself rendered.

| Path | Serves |
|---|---|
| `GET /`, `/index.html` | the app shell — skip link, top bar, the six-view navigation, one `<main>` that `app.js` fills with the view the URL names (Overview by default). It carries no data, so it answers at once whatever the probe is doing |
| `GET /v/<view>` | one view's fragment (`overview`, `work`, `accounts`, `usage`, `commands`, `services`; anything else 404). A view that fails renders its error state in words; every other view is unaffected |
| `GET /static/app.css`, `/static/app.js` | the two static files, `Cache-Control: no-cache` with an ETag (an edit shows at once) |
| `GET /quota.json` | the last `--status --json` payload on disk, served at once; a payload older than `QUOTA_DASH_MAX_AGE_S`, or a fleet pointer that has moved since it was written, starts ONE background regeneration. A first call with nothing on disk returns `{}` and starts one background probe — a deliberate delta from the old page, which probed inline and made that caller wait |
| `GET /health` | `ok` — liveness for the keepalive |
| `GET /external-services.html` | `303` to `/#services`, empty body, on no removal date — the old static page's bookmark now lands on the inventory section (not tied to `_LEGACY_TOKEN_UNTIL`) |
| `GET /repos.html` | the old Repos page's bookmark: `303` to `/#work` through `_LEGACY_TOKEN_UNTIL` (2026-10-31), `404` after it. A work item removes the redirect and the token's legacy branch on that date |
| `POST /item-verdict` | `{repo, item, action: accept\|reject\|comment, text, token}` → `work.py verdict` as the operator against the repo's main checkout — 200, 400 (unknown pair or action, or no words), 409 (`changed` / `diverged`, nothing run) or 502 (work.py's refusal or a timeout) |
| `POST /agent-pause` | `{repo, agent, action: pause\|resume, why}` → `work.py pause\|resume` as the operator — 200, 400 or 502 |
| `POST /switch` | `{account: <slug>}` → `claude_rotate.py --switch <slug>`, then a fresh probe — 200, 400 (a slug the last payload does not list), 502 (the CLI's stderr) |
| `POST /park` | `{account: <email>, park: true\|false}` → `--park\|--unpark <email>` — the same contract |
| `POST /cap`, `POST /threshold` | `{account, cap}` (0–100, null clears, 0 parks) · `{account, threshold}` (50–100, null = the fleet default) → `~/.claude-fleet/caps.json` · `thresholds.json`, read-modify-write under a `<file>.lock` flock with an atomic replace; a file that does not parse is never rewritten (502) |

**Refusals, before anything runs:** `421` a foreign `Host`; `403` a cross-site request, or a POST without
the `X-Quota-Dash` header; `404` an unknown path; `400` a `Content-Length` outside 0–4,096 or a body that
is not JSON. `GET /static/<file>` answers `304` to an `If-None-Match` that carries its current ETag.

A POST for a target the board does not hold — a restarted server, or a frame older than the last render
— rebuilds once through the view that shows it (`_rebuild_targets`: the Overview for a pause, the Work
view for an item, then the Overview when the item's Work pane faulted and published nothing), so "not on
the board" is never the answer for something the operator can see. Every
POST outcome is one line in the log.

## Lifecycle

Self-healing, no systemd (WSL has no user bus). Two crontab lines:

```cron
@reboot sleep 20 && /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
*/10 * * * * /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
```

`--ensure` demands a real HTTP `ok` from `/health` (`QUOTA_DASH_ENSURE_TIMEOUT_S`, 5 s): a healthy server
makes the line a no-op, a dead port respawns, and a WEDGED server (accepts, never answers) is killed —
only the PID holding our port, only after the probe fails — and respawned.

Modes: `--serve` (the foreground server) · `--ensure` (start it if it is down) · `--once` (probe the
fleet once, write `quota.json`, print its path and exit — a scripted refresh without a server).

## Configuration (all env, all defaulted)

The board's own knobs, and the box and rotation knobs it reads; nothing is set in a file.

| Variable | Default | Purpose |
|---|---|---|
| `QUOTA_DASH_PORT` | `5051` | listen port (PORTS.md: WSL Python range) |
| `QUOTA_DASH_HOST` | `127.0.0.1` | bind address — loopback by design; a configured name joins the Host allowlist, a wildcard bind never does |
| `QUOTA_DASH_URL` | `http://<QUOTA_DASH_HOST>:<QUOTA_DASH_PORT>/` | the board's URL as `claude_rotate.py`'s no-successor drain mail names it — set it only when the board is reached at another address |
| `QUOTA_DASH_PROBE_INTERVAL_S` | `20` | the server's own probe cadence, viewer or not — a PERIOD, not a pause after each probe |
| `QUOTA_DASH_MAX_AGE_S` | `20` | a reading older than this starts a background regeneration on the next quota view or `/quota.json` |
| `QUOTA_DASH_REFRESH_S` | `20` | the Overview's and the Accounts view's refresh cadence |
| `QUOTA_DASH_REPOS_TTL_S` | `20` | how long the work-store and agents reads are cached (the Work view's cadence too) |
| `QUOTA_DASH_PROBE_TIMEOUT_S` | `60` | per-probe subprocess timeout |
| `QUOTA_DASH_TICK_TIMEOUT_S` | `180` | the board-invoked `--tick`'s timeout |
| `QUOTA_DASH_TRIGGER_COOLDOWN_S` | `120` | the rotation trigger's per-tier cooldown |
| `QUOTA_DASH_ROTATE_LOCK` | `~/.claude/state/rotate.lock` | the cron tick's lock the board's tick takes too |
| `QUOTA_DASH_SWITCH_TIMEOUT_S` | `90` | the account controls' subprocess timeout |
| `QUOTA_DASH_SOCKET_TIMEOUT_S` | `15` | per-connection socket timeout — a client that under-sends its declared body is dropped, never parked |
| `QUOTA_DASH_ENSURE_TIMEOUT_S` | `5` | `--ensure`'s `/health` timeout |
| `QUOTA_DASH_LOG` | `~/.claude/quota-dashboard.log` | where `--ensure` points the respawned server's output |
| `QUOTA_DASH_OUT_DIR` | `~/.claude/quota-dashboard` | `quota.json` and the balance caches |
| `QUOTA_DASH_ROTATE_CLI` | `/opt/fabrik/scripts/sysadmin/claude_rotate.py` | the CLI it shells |
| `QUOTA_DASH_POINTER` | `~/.claude-fleet/active` | the fleet pointer compared against the reading — a flip regenerates on the next quota view |
| `QUOTA_DASH_CAPS_FILE`, `QUOTA_DASH_THRESHOLDS_FILE` | `~/.claude-fleet/caps.json`, `thresholds.json` | the files the cap and rotate-at controls write |
| `QUOTA_DASH_BUDGET` | `1` | `0` disables the box-budget line (it shells out to `dispatch_headroom.py`, which probes the fleet) — set in the tests, never on the served board |
| `QUOTA_DASH_CREDITS_KEY_FILE` | `~/.config/fabrik/subagents.env` | the OpenRouter key (`OPENROUTER_API_KEY` in the environment wins) |
| `QUOTA_DASH_CREDITS_URL` | `https://openrouter.ai/api/v1/credits` | the balance endpoint |
| `QUOTA_DASH_CREDITS_TTL_S` · `QUOTA_DASH_CREDITS_TIMEOUT_S` | `300` · `10` | the balance's reuse window and GET timeout (off the render path) |
| `POOL_CREDITS_WARN_USD` | `5` | the pool's drain line — an absolute floor, not a percentage |
| `QUOTA_DASH_API_QUOTAS_TTL_S` · `QUOTA_DASH_API_QUOTAS_TIMEOUT_S` | `1800` · `12` | the search-API readings' reuse window (long on purpose: a Brave probe spends a query) and per-provider timeout |
| `QUOTA_DASH_RENDERED_COMMANDS` | `~/.claude/commands` | the RENDERED corpus the service matrix reads |
| `CLAUDE_P_COST` | `scripts/kilo-benchmarks/claude_p_cost.json` | the spend sidecar the Usage view reads |
| `FABRIK_OPT_DIR` | `/opt` | the root the Overview and Work views scan for `*/.fabrik/work` stores and merge records |
| `CLAUDE_FLEET_ROOT` | `~/.claude-fleet` | where `caps.json` and `thresholds.json` live (unless their own `QUOTA_DASH_*_FILE` is set) |
| `QUOTA_RESERVE_PCT` | `80` | the quota governor's reserve: routine work sheds to the pool at or over it |
| `ROTATE_THRESHOLD` | `99` | the flip line the rotation trigger keys on (an account's `thresholds.json` entry wins) — the tick's own knob |
| `ROTATE_URGENT_DRAIN_PCT` | `90` | the urgent-drain tier of the trigger |
| `ROTATE_DRAIN_THRESHOLD` | `85` | the drain line: the blind-probe tier and the relief tier |
| `ROTATE_TARGET_SESSION_MAX_PCT` | the drain line | the picker's session bar, which the queue's eligibility mirrors |
| `BRAVE_API_KEY`, `FIRECRAWL_API_KEY`, `EXA_API_KEY` | — | a provider key in the environment wins over the MCP configs (`~/.claude.json`, the repo's `.mcp.json`); never rendered, logged or cached |

## Testing

Thirteen test files, none of which reaches the network, the fleet or the real home. They share one
isolation module, `tests/quota_dashboard_isolation.py`: every loader points HOME at an empty directory and
drops the provider keys, every proxy variable and the MCP configs, and an autouse guard each file imports
cuts every non-loopback connect and lookup and fails the test that tried one. The Services view's registry
read is guarded on both sides, because libpq connects in C and the socket guard cannot see it: the loader
replaces the collector's spawn with a stub that answers the census fixture
(`tests/external_services_fixture.py`), empties the 60 s slot, and sets `SERVICES_REGISTRY_DSN` to a socket
directory that does not exist, so no board test reads the real registry:

```bash
.venv/bin/python -m pytest tests/test_quota_dashboard.py tests/test_quota_dashboard_render_failure.py \
  tests/test_quota_dashboard_posture.py tests/test_quota_dashboard_banner.py tests/test_quota_dashboard_page_layer.py \
  tests/test_quota_dashboard_browser.py tests/test_quota_dashboard_ui_kit.py tests/test_quota_dashboard_app_js.py \
  tests/test_quota_dashboard_server.py tests/test_quota_dashboard_overview.py tests/test_quota_dashboard_work.py \
  tests/test_quota_dashboard_accounts.py tests/test_quota_dashboard_views_misc.py -q
```

The two browser files launch chromium through playwright (in the `.venv`; skipped where it is missing); the
inventory's axe cases also need `axe-core` (`AXE_CORE_JS`, else any `/opt/*/node_modules/axe-core/axe.min.js`;
skipped where absent).

## Boundaries

- **The writes are relays.** It reads by shelling `--status --json`, and — only on the operator's
  click — relays `--switch`, `--park`/`--unpark`, the cap and rotate-at edits, `work.py pause|resume`
  and `work.py verdict`. It never decides a rotation and never reads or writes a credential file; the
  CLI and `work.py` own those contracts (`docs/workstation/claude-account-rotation.md`,
  `docs/reference/work-tracking.md`). The written item files sit in each repo's main checkout until its
  coordinator's `work.py commit-items`; the board never commits.
- **Loopback only.** No auth, because nothing off-box can reach it; remote access is W-7def1b78, never a
  rebind to `0.0.0.0` without auth in front.
- **Stdlib only, no build step.** No dependencies to keep current — the board process imports neither
  `registry_db` nor psycopg2 (the named exception, D9, lives in the `inventory_read.py` child); playwright is
  in the `.venv` for the browser tests only (`tests/test_quota_dashboard_browser.py`, `tests/test_quota_dashboard_app_js.py`).

## Related

- `docs/workstation/claude-account-rotation.md` — the rotation system the Accounts view displays
- `docs/reference/work-tracking.md` — the work stores the Overview and Work views read and write
- `PORTS.md` — port 5051 allocation

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/gen_dashboard.py`
- `scripts/sysadmin/dashboard_ui/__init__.py`
- `scripts/sysadmin/dashboard_ui/components.py`
- `scripts/sysadmin/dashboard_ui/fmt.py`
- `scripts/sysadmin/dashboard_ui/inventory.py`
- `scripts/sysadmin/dashboard_ui/merges.py`
- `scripts/sysadmin/dashboard_ui/snapshot.py`
- `scripts/sysadmin/dashboard_ui/strings.py`
- `scripts/sysadmin/dashboard_ui/views/__init__.py`
- `scripts/sysadmin/dashboard_ui/views/accounts.py`
- `scripts/sysadmin/dashboard_ui/views/commands.py`
- `scripts/sysadmin/dashboard_ui/views/overview.py`
- `scripts/sysadmin/dashboard_ui/views/services.py`
- `scripts/sysadmin/dashboard_ui/views/usage.py`
- `scripts/sysadmin/dashboard_ui/views/work.py`
- `scripts/sysadmin/inventory_read.py`
- `scripts/sysadmin/quota_dashboard.py`
<!-- END related-scripts -->
