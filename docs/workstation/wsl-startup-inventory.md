# WSL Startup Inventory — what runs when WSL starts

**Date:** 2026-08-03
**Status:** ✅ CURRENT
**Affects:** Local WSL2 dev box (`Ubuntu-24.04`). NOT the VPS fleet.

---

## A. On WSL boot → systemd (`systemd=true` in `/etc/wsl.conf`)

**Your custom / project services (auto-start every boot):**

| Service | What it is |
|---|---|
| `postgresql` · `redis-server` | Databases |
| `docker` · `containerd` | Containers |
| `openvpn.service` | VPN tunnel |
| `fabrik-mcp-http` · `fabrik-citation-verifier-mcp` · `fabrik-citation-verifier` · `citation-verifier` | Fabrik MCP + citation services |
| `fabrik-dr-watcher` · `env-watcher` | Fabrik watchers |
| `seo` | Project microservice |

**⚠️ DISABLED 2026-09-08 — five units were restart-looping against projects that no longer exist.**
`namecheap-api` · `image-broker` · `captcha` (all three archived to `/opt/archived/`), `webscraper-ui`
(`/opt/web_scraper` deleted outright) and `emailgateway` (repo survives but has NO source — `src/index.ts`
missing, 11 files and all of them governance docs). Measured before disabling: **~239,500 restarts**
across the five, every 5-10 s since the last boot, which is what grew `~/enforcement_watcher.log` to
3.2 GB and the journal to 505 MB. `fabrik-citation-verifier.service` was disabled in the same pass —
it is a STALE DUPLICATE that can never bind: pid 7347 already serves 8032 (`src.citation_verifier.main:app`
on 0.0.0.0) and the capability is healthy (HTTP 200, MCP CONNECTED). Re-enable any of these only after
its project is restored; a permanently-failed unit hides the next real failure.
| `spamd` | SpamAssassin daemon (Ubuntu package unit, enabled) |

**Does NOT auto-start (manual):**

- `ollama.service` — local LLM server (71 GB of models under `/usr/share/ollama/.ollama/models`; unit is
  `disabled` + `inactive`). Start when needed: `sudo systemctl start ollama`

**Stock Ubuntu (ignore):** `apparmor`, `landscape-client`, `ubuntu-advantage`, `snap.cups.*`, `ssl-cert`, `unbound-resolvconf`, etc.

---

## B. On boot → `@reboot` cron

- `/opt/youtube/scripts/start_all.sh` — starts the YouTube RAG pipeline
- `/opt/youtube/scripts/b2_socks_tunnel.sh` — B2 storage SOCKS tunnel
- `/opt/youtube/scripts/rag_backfill_supervisor.sh` — headless-Claude RAG backfill supervisor
- `sleep 60 && /opt/fabrik/scripts/dr_env_backup.sh` — catch-up DR credential mirror

---

## C. Scheduled (cron + systemd timers, while running)

- **cron:** youtube `recovery_sweep` + `start_all.sh ensure` (every 5 min), youtube RAG indexing
  (`rag_claim_index` hourly, `rag_claim_embed_index` hourly, `rag_daily_index` daily) + logrotate/job-prune
  (daily 04:00/04:05) + financials (weekly), fabrik audits (`audit_all_registrars` hourly,
  `audit_authelia_gates` weekly via the wake-proof `weekly_catchup.sh` hourly stamp-check at :07),
  `ci_fix_dispatcher` (hourly :40), `sync-claude-accounts-to-fleet`
  (every 6 h), `daily_refresh.sh` (06:00 — since 2026-09-02 it also runs `flush_subagent_outboxes` then `rank_task_subagents`; the ranking regen had NEVER been scheduled, so the doc that drives `pick_models` fleet-wide only refreshed when a human ran it — and since 2026-09-05 `claude_p_cost.py --refresh` runs BETWEEN them — after the outbox flush, before the ranker, in both this cron and the boot hook — because the ranker renders its rate and a rebuild wired after it would publish yesterday's figure for a full cycle; that sidecar had sat 26 days stale, at 0.006310 against the 0.007482 per Mtok a rebuild measured) + `kilo_model_sync` (11:59), the scratch janitor `scratch_sweep.py --dead --apply` (04:20 — ⚠️ NOT YET PLACED as of 2026-09-08, handed to the operator because a crontab write is classifier-blocked; deliberately with NO `flock -n` wrapper: the script takes that same lock itself and `flock(1)` holds it across the exec, so a wrapper makes the child's acquire fail and the sweep exits 0 having done nothing; see `cleanup-automation.md` § F), DR (`dr_env_backup` 03:30 + Sun 04:00
  recovery test), `cache-prune.sh` (Sun 03:00), calendar-orchestration (Sun 02:00), site-provisioner
  watchlist/drop-feed/dns-recheck, trade-intelligence GTIP refresh (05:30), headless-Claude session prune (05:17),
  Claude account rotation (`claude_rotate --tick` every 5 min; `--keepalive` Mon 06:20), quota dashboard
  (`quota_dashboard --ensure` @reboot + every 10 min, serves localhost:5051), kaizen measurement
  (DAILY since the M1 cutover 2026-08-20, three hourly stamp-checks that each fire once per day via
  `weekly_catchup.sh`: `kaizen_collect_v2.py` collector, `kaizen_outcomes.py` nightly fleet-health
  sweep, `kaizen_coroner.py` — the weekly `kaizen_metrics.py` is retired to
  `scripts/sysadmin/archived/`; `docs/workstation/kaizen.md`).
  **Post-wipe restore DONE 2026-08-22:** the 2026-08-19 whole-table wipe was reconciled + reinstalled
  to 41 jobs, now **46** (audited 2026-09-08: every referenced script path exists; backup `~/backups/crontab.backup.20260822-143018`); `--tick`/`--keepalive`/dashboard
  `--ensure` all live. Cron runs with a minimal `PATH` (no `~/.local/bin`), so the rotation pings
  resolve `claude` themselves (`claude-account-rotation.md` § Cron PATH) — no crontab `PATH=` line.
- **timers:** `proxy_sync`, `ip_authorization`, `phpsessionclean`, `logrotate`, `dpkg-db-backup`
  (+ stock `apt-daily*`, `man-db`, `motd-news`, `systemd-tmpfiles-clean`, `e2scrub_all`)

---

## D. Per-shell (every terminal you open — the `.bashrc` chain)

**Order:** `/etc/profile` → `/etc/profile.d/*` (locale-fix, apps-bin-path, bash_completion, byobu, cloudinit)
→ `~/.profile`; then interactive: `/etc/bash.bashrc` → `~/.bashrc` → `~/.bash_aliases`.

**`~/.bashrc` (91 active lines — was 115 until the 2026-09-08 audit) does:**

⚠️ **Audited and cleaned 2026-09-08** (backup `~/.bashrc.backup.20260908-015545`):
- **A plaintext `SEMGREP_APP_TOKEN` was removed.** It sat in a `0644` file AND was redundant —
  `~/.semgrep/settings.yml` (`0600`) holds the same token and `final_gate.py:470` reads it from
  there, never from the environment. Nothing consumed the export. It was never in reachable git
  history (0 commits); the only repo copy was a dangling object under `.git/lost-found`, pruned.
- **The enforcement-watcher guard was `pgrep -f`, which races.** `pgrep -f` matches any cmdline
  containing the string, so two shells opening in the same second both saw "not running" and both
  spawned — measured: 2 live watchers started at the identical second, each running full 45-project
  fleet syncs, 5,493 logged into a 3.2 GB unrotated file. Replaced with `flock -n 9`, which is
  atomic (proven: 10 simultaneous shells → exactly 1 start). `~/.bashrc` is not the only place this
  pattern appears — a `pgrep` guard on any per-shell daemon has the same defect.
- **~24 dead alias lines removed:** the whole `mmc-*`/`consult-*` family (they call
  `consult_list_models`, which is not a command, and name gpt5/codex/gemini routes retired here),
  plus the SHADOWED earlier definitions of `ll`/`mmc`/`mmc-list`/`mmc-auto` — each was defined twice
  and only the later one ever took effect.
- **NOT fixed, reported instead:** `PATH` reaches **121 entries of which 64 are unique**
  (`~/.local/bin` ×8, each Android SDK path ×7). Every `export PATH=` line prepends
  unconditionally, so a nested or re-sourced shell stacks them again. Harmless but it makes every
  command lookup scan duplicates; the fix is a guard or a dedup, and PATH is load-bearing enough to
  be worth a deliberate change rather than a drive-by one.
- `~/.bash_aliases` is sourced at `:104` but **does not exist** (harmless — the `-f` test guards it).

**It also does:**

- **fabrik startup hook** (line 212, interactive shells only): `source /opt/fabrik/scripts/wsl_startup_hook.sh`
  — env watcher + the lockfile-gated daily pipeline (detail: [../operations/wsl-environment.md](../operations/wsl-environment.md))
- **nvm load** (lines 214–216 → Node 24 in interactive shells; non-interactive shells return early before this)
- **ssh aliases:** `vps` / `vprod` → `ssh ozgur@172.93.160.197`
- **git aliases:** `g`, `gs`, `gp`, `gpu`, plus `opt`, `tools`, `ll`, `env-check`
- **`consult` / `mmc-*` aliases** — a multi-model consult tool (sonnet/gpt5/opus/haiku/gemini pairs)
- standard `ls`/`grep` color aliases, `lesspipe`, `dircolors`

> Node: interactive terminals resolve `node` → nvm **v24.18** (default). System `/usr/bin/node` is **v22.23**
> (the wsl-shell MCP's node-pty is built against it). See wsl-shell-mcp-setup.md.
