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
| `emailgateway` · `namecheap-api` · `image-broker` · `captcha` · `seo` · `webscraper-ui` | Project microservices |
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
  `audit_authelia_gates` Mon 06:00), `ci_fix_dispatcher` (hourly :40), `sync-claude-accounts-to-fleet`
  (every 6 h), `daily_refresh.sh` (06:00) + `kilo_model_sync` (11:59), DR (`dr_env_backup` 03:30 + Sun 04:00
  recovery test), `cache-prune.sh` (Sun 03:00), calendar-orchestration (Sun 02:00), site-provisioner
  watchlist/drop-feed/dns-recheck, trade-intelligence GTIP refresh (05:30), headless-Claude session prune (05:17),
  Claude account rotation (`claude_rotate --tick` every 5 min; `--keepalive` Mon 06:20), quota dashboard
  (`quota_dashboard --ensure` @reboot + every 10 min, serves localhost:5051), kaizen measurement
  (`kaizen_metrics --once` Mon 06:45 — after the keepalive + fleet doc audit; `docs/workstation/kaizen.md`)
- **timers:** `proxy_sync`, `ip_authorization`, `phpsessionclean`, `logrotate`, `dpkg-db-backup`
  (+ stock `apt-daily*`, `man-db`, `motd-news`, `systemd-tmpfiles-clean`, `e2scrub_all`)

---

## D. Per-shell (every terminal you open — the `.bashrc` chain)

**Order:** `/etc/profile` → `/etc/profile.d/*` (locale-fix, apps-bin-path, bash_completion, byobu, cloudinit)
→ `~/.profile`; then interactive: `/etc/bash.bashrc` → `~/.bashrc` → `~/.bash_aliases`.

**`~/.bashrc` (113 active lines) does:**

- **fabrik startup hook** (line 212, interactive shells only): `source /opt/fabrik/scripts/wsl_startup_hook.sh`
  — env watcher + the lockfile-gated daily pipeline (detail: [../operations/wsl-environment.md](../operations/wsl-environment.md))
- **nvm load** (lines 214–216 → Node 24 in interactive shells; non-interactive shells return early before this)
- **ssh aliases:** `vps` / `vprod` → `ssh ozgur@172.93.160.197`
- **git aliases:** `g`, `gs`, `gp`, `gpu`, plus `opt`, `tools`, `ll`, `env-check`
- **`consult` / `mmc-*` aliases** — a multi-model consult tool (sonnet/gpt5/opus/haiku/gemini pairs)
- standard `ls`/`grep` color aliases, `lesspipe`, `dircolors`

> Node: interactive terminals resolve `node` → nvm **v24.18** (default). System `/usr/bin/node` is **v22.23**
> (the wsl-shell MCP's node-pty is built against it). See wsl-shell-mcp-setup.md.
