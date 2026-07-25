# WSL Startup Inventory — what runs when WSL starts

**Date:** 2026-07-25
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
| `emailgateway` · `namecheap-api` · `image-broker` · `captcha` · `seo` | Project microservices |

**Does NOT auto-start (manual):**

- `ollama.service` — local LLM server (the 72 GB models). Start when needed: `sudo systemctl start ollama`

**Stock Ubuntu (ignore):** `apparmor`, `landscape-client`, `ubuntu-advantage`, `snap.cups.*`, `ssl-cert`, `unbound-resolvconf`, etc.

---

## B. On boot → `@reboot` cron

- `/opt/youtube/scripts/start_all.sh` — starts the YouTube RAG pipeline
- `/opt/youtube/scripts/b2_socks_tunnel.sh` — B2 storage SOCKS tunnel

---

## C. Scheduled (cron + systemd timers, while running)

- **cron:** youtube `recovery_sweep` (every 5 min), fabrik audits (hourly + weekly), `kilo_model_sync` (daily),
  calendar-orchestration (weekly), site-provisioner watchlist/drop-feed (daily), youtube financials (weekly)
- **timers:** `proxy_sync`, `ip_authorization`, `episodic-index`, `phpsessionclean`, `logrotate`, `dpkg-db-backup`

---

## D. Per-shell (every terminal you open — the `.bashrc` chain)

**Order:** `/etc/profile` → `/etc/profile.d/*` (locale-fix, apps-bin-path, bash_completion, byobu, cloudinit)
→ `~/.profile`; then interactive: `/etc/bash.bashrc` → `~/.bashrc` → `~/.bash_aliases`.

**`~/.bashrc` (113 active lines) does:**

- **nvm load** (lines 214–216 → Node 24 in interactive shells; non-interactive shells return early before this)
- **ssh aliases:** `vps` / `vprod` → `ssh ozgur@172.93.160.197`
- **git aliases:** `g`, `gs`, `gp`, `gpu`, plus `opt`, `tools`, `ll`, `env-check`
- **`consult` / `mmc-*` aliases** — a multi-model consult tool (sonnet/gpt5/opus/haiku/gemini pairs)
- standard `ls`/`grep` color aliases, `lesspipe`, `dircolors`

> Node: interactive terminals resolve `node` → nvm **v24.18** (default). System `/usr/bin/node` is **v22.23**
> (the wsl-shell MCP's node-pty is built against it). See wsl-shell-mcp-setup.md.
