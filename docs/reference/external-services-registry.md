# External Services Registry — the daily chain that keeps the fleet's vendor inventory true

**Owner:** infra · **Definition:** `scripts/external_services_chain.sh` (ONE script) · **Schedule:** run by `scripts/kilo-benchmarks/daily_refresh.sh` (cron `0 6 * * *`) AND by `scripts/wsl_startup_hook.sh` at boot — the two share the daily lock, so both must carry it · **Heartbeat:** `external-services-chain` in `.fabrik/liveness-registry.json` (the dashboard file's mtime, ≤30 h — written ONLY when every DATA step succeeded; a failed classify alerts but never ages it) · **Human-readable output:** `docs/reference/apis/EXTERNAL_SYSTEMS.md` (the converged fleet index — hand-curated, sourced; this chain feeds its denominator, it does not write it)

## What it is

Four idempotent scripts run in order once a day by `scripts/external_services_chain.sh` (each under `timeout 900`), that answer "which external systems does the fleet use, from which repos, with which credentials, and are those accounts alive" — with **zero secrets** leaving `secrets/all-envs.env` (mode 600, gitignored):

| Step | Script | Reads | Writes | NO-OP when |
|---|---|---|---|---|
| 1 | `scripts/gather_envs.py --apply` (exit 1 and NO write if ripgrep cannot run — a complete yesterday beats a truncated today) | every `/opt/*/.env` (21 today) **and every git repo's source under `/opt` for `https://<host>` literals** (45 repos, one ripgrep, ~0.2 s) | `secrets/all-envs.env` — `#svc` blocks by category, `KEY=value` lines with `used by:`, `CODE_HOST_URL=https://<host>` lines for call sites, a NEEDS-TRIAGE block for unknown providers | body unchanged (volatile header excluded) |
| 2 | `scripts/classify_services.py --apply --tombstone-unresolved --max-per-run 10` | the NEEDS-TRIAGE block (names + public URLs only); the persisted cursor `.tmp/external-services/classify_cursor.json` | `scripts/service_catalog.json` — identified vendors merged, unidentifiable ones tombstoned (`category=unidentified`), a provider that transport-errors 3 runs in a row tombstoned too (`classify_errors.json`); `classify_last.json` + an info alert name today's new providers | nothing flagged |
| 2b | `scripts/gather_envs.py --apply` again | — | today's classifications leave NEEDS-TRIAGE before the sync reads the file | body unchanged |
| 3 | `scripts/registry_sync.py --fetch-credits` | `all-envs.env` | Postgres `fabrik_services` (`services`; `api_keys` as `value_sha256` only, with `kind` = `code-host` for the synthetic `CODE_HOST_URL` rows and `credential` for every real key (a proxy URL carrying a password is a credential) — the dashboard counts only credentials as keys; `credit_snapshots`, fetched with the first key whose NAME is a credential, else the first non-URL value — `GROQ_API_KEY_2`-style names still feed the fetcher) with a bounded prune (refuses to delete >20 % of the registry); `ensure_schema` probes for the `kind` column and adds it only when absent, in its own short transaction (an unconditional ALTER would wait behind any open reader); key rows that left a provider are pruned per service | upserts only bump `last_seen` |
| 4 | `scripts/gen_dashboard.py external-services-dashboard.html` | the registry (`kind`-tolerant: a registry never synced by the new sync counts every row as a credential) | the static HTML dashboard (repo root, gitignored), written atomically | SKIPPED when a DATA step (1, 2b, 3) failed — the heartbeat must age, not lie; a failed classify (paid, optional) alerts but does not age it |

`scripts/dashboard_server.py` (`http://127.0.0.1:8770`) is the live twin of step 4 — run it by hand when you want the registry queried on every load.

## The two inputs, and why the second exists

**Env keys are a proxy** for "the fleet uses vendor X", and the proxy leaks: a vendor reached without a key (a public API, a scrape target, an SDK whose token is named unusually, an OAuth flow) never appears in any `.env`. Measured 2026-09-02 before the second input: **239 of 495** hosts referenced from code across `/opt` were in neither the registry nor the fleet index — eight of them fleet-used systems with no key anywhere (PostHog, Axiom, Slack, Vercel, Cerebras, LinkedIn, BLS, Google APIs/Gmail).

The **code call-site scan** (`gather_envs.scan_code_hosts`) closes that class:

- source files only (`py ts js sh yaml` + Dockerfiles; `node_modules`, `.venv`, `dist`, `docs/`, `tests/`, fixtures, `*.md`, `*.lock` excluded);
- a host is attributed to the catalog provider whose `url` has the same HOSTNAME, else the one that ALONE owns its registrable domain (`api.resend.com` → `resend`); a label or hostname shared by several entries (`backrest`'s url is a github.com repo link; safe-browsing/youtube/gemini under google.com) is ambiguous and never resolved by JSON order — it falls through to the catalog key or the `match` prefix; the referencing repos join that provider's `used_by`;
- **multi-service platform domains** (`amazonaws`, `googleapis`, `azure`, `windows`, `cloudfront`) are never credited to one vendor — the service label is kept (`gmail.googleapis`, `truststore.amazonaws`) and goes to triage (an RDS truststore fetch was mis-credited to `aws-ses` before this rule); once the classifier names or tombstones that label it keeps its catalog entry and leaves triage;
- ignored: the fleet's own domains, local/test TLDs, placeholder labels (`example`, `evil`, `company`…), reference-only hosts (package registries, schema/standards hosts, CDNs, Q&A sites, front-end libraries — never a vendor's own domain), documentation subdomains by prefix (`docs.`, `learn.`, `developer.`, `help.`…), one-letter or over-long labels; `api.*` always survives;
- scanned: `py ts js sh yaml` and Dockerfiles; excluded: `node_modules`, `.venv`, `dist`, `docs/`, `tests/`, `__tests__/`, `__mocks__/`, `e2e/`, fixtures, `*.test.*`/`*.spec.*`, and `build/`/`cache/` at the repo ROOT only (a repo's own `src/build/` is source);
- a partial ripgrep run (exit 2 with matches — one unreadable directory) keeps its matches and prints rg's own error naming the path; a run with no matches and an error, or no `rg` at all, raises and nothing is written;
- a host that matches nothing lands in the same NEEDS-TRIAGE queue as an unknown key, as `#svc name=<label> category=? url=https://<host>` + `CODE_HOST_URL=…`, so step 2 grounds it exactly like an unknown key — and the catalog entry it earns carries `match: []` (no env key stands behind it, so a bare-word prefix must never claim one: `allowed` once swallowed `ALLOWED_ORIGINS`); an explicit internal-config name always wins over a catalog prefix; URL userinfo (`user:pw@`) is never taken as the host.

## Cost bound

Step 2 pays the OpenRouter pool (`max_cost_usd=0.20` per unit, measured ≈$0.002). `--max-per-run 10` walks the sorted queue from a PERSISTED CURSOR (the last name processed), wrapping at the end, so a burst of hundreds of new hosts drains over days at ≤$2/day worst case; a date-keyed offset was tried and refuted in review (with N changing daily it skipped and double-billed). A provider that only ever transport-errors is retried once per lap and tombstoned after 3 consecutive erroring runs — bounded spend by construction. A manual run may pass `--max-per-run 0`.

## Failure visibility

Every step is non-fatal to the caller but never silent: a non-zero exit (124 = the 900 s timeout) alerts via `alerting.send_alert` (the retired orchestrator's alert, kept) — a bounded-prune refusal, an exhausted pool or a dead registry DB reaches the operator, not just the log — and the dashboard is NOT rewritten, so the liveness heartbeat ages and reads DEAD. Newly classified providers raise an info alert. A manual run racing the cron is safe: `gather_envs` and `classify` write atomically (`os.replace`), `registry_sync` is one transaction, and `classify` holds a non-blocking lock (`.tmp/external-services/classify.lock`) so two runs never process the same slice or clobber the cursor — the loser prints a line and exits 0.

## Liveness

The chain is declared once in `.fabrik/liveness-registry.json` as `external-services-chain`: evidence = the dashboard file's mtime (step 4 runs last and writes only when steps 1, 2b and 3 succeeded — so a half-dead chain ages past 30 h and reads DEAD), `max_age_hours: 30`. `python3 scripts/sysadmin/liveness_audit.py` reports it LIVE/DEAD/UNKNOWN like every other scheduled surface.

## History — why it lives inside `daily_refresh.sh`

Built 2026-07-18 (plan `docs/development/plans/archived/2026-07-18-plan-1-external-services-registry.md`) with steps 3–4 behind a documented cron line for an orchestrator, `refresh_service_inventory.py`, that was "operator-installed — NOT auto-installed". It never was. Step 1 was later wired into `daily_refresh.sh` (2026-07-26, with step 2), so the scan ran every morning while the registry, the classifier's registry side, the dashboard and the new-provider alerting stayed frozen on build day — for 46 days, unnoticed, because no liveness surface named them. Found 2026-09-02 when the operator asked "is the auto scan working". Fix: steps 3–4 joined the one schedule that exists, the orchestrator (a second entry point whose seen-set design the tombstone flag had already superseded) was retired, the heartbeat was declared, and the code call-site input was added. Guards: `tests/test_external_services_chain.py` (the chain script's step order + gated heartbeat, both entry points run it and inline no step, the liveness surface, `gen_dashboard --help` writes no file), `scripts/tests/test_gather_envs.py` (attribution, ambiguity, triage, ignore rules, platform domains, partial/failed scans, 0600, cursor walk under churn, error budget), `scripts/tests/test_registry_sync.py` (credential by key role, `kind`, dashboard key count).

## Manual commands

```
.venv/bin/python scripts/gather_envs.py                # dry-run: counts only, nothing written
.venv/bin/python scripts/gather_envs.py --apply
.venv/bin/python scripts/classify_services.py          # dry-run proposals for every flagged provider
.venv/bin/python scripts/registry_sync.py --fetch-credits
.venv/bin/python scripts/gen_dashboard.py external-services-dashboard.html
bash scripts/external_services_chain.sh               # the whole chain, exactly as cron runs it
.venv/bin/python scripts/dashboard_server.py           # live, http://127.0.0.1:8770
REGISTRY_PRUNE_FORCE=1 .venv/bin/python scripts/registry_sync.py   # only for a legitimate mass recatalog
```

## Coupling

`gather_envs.py` ↔ `service_catalog.json` (`#svc` metadata) ↔ `classify_services.py` (writes the catalog) ↔ `registry_sync.py` (`SVC_RE`/`KV_RE` parse the exact line shapes — `CODE_HOST_URL` lines are ordinary `KEY=value` lines to it) ↔ `gen_dashboard.py` / `dashboard_server.py` (read the registry) ↔ `scripts/external_services_chain.sh` (the definition) ↔ `daily_refresh.sh` + `wsl_startup_hook.sh` (the two entry points) ↔ `.fabrik/liveness-registry.json` (the heartbeat) ↔ `db/services_registry_schema.sql` (`api_keys.kind`). Related packs: `core/57-external-data-sourcing` (the Capability Profile the fleet index carries per system), `core/58-resilience`.
