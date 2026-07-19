# Credential Recovery

**Created:** 2026-06-01 (W9 of fleet-hardening plan)
**Last Updated:** 2026-06-16 (W2 confirmed done — B2 restic repo initialized; weekly self-test now logs `OK: N snapshots readable`)
**Purpose:** Recover credentials after dev WSL loss, file corruption, or any other event that wipes the working copy. Six credential files are mirrored:

- `/opt/fabrik/.env` (~15 KB, dev-WSL canonical) — fleet credentials, encrypted-only-once master.
- `vps1:/opt/fabrik/.env.sysadmin` (~100 B, vps1-only) — Telegram bot token + owner ID for the AI sysadmin. Added 2026-06-01 after a deep-review pass found the original W9 omitted it, leaving the sysadmin bot's recovery dependent on user memory + a fresh BotFather token reissue.
- `vps2:/opt/backrest/.env` + `vps2:/opt/backrest/.restic-password` — spoke Backrest B2 creds + restic password (W11, 2026-06-01; Lesson 67 — without the password, vps2 backups are unreadable).
- `vps3:/opt/backrest/.env` + `vps3:/opt/backrest/.restic-password` — same for vps3 (per-spoke, independent).

**Companion to:** [`disaster-recovery.md`](disaster-recovery.md) — every DR path through that doc depends on `BACKREST_RESTIC_PASSWORD` being recoverable; this doc is how that works.

## What's at stake

`/opt/fabrik/.env` (~350 lines, ~15 KB) holds every credential the fabrik fleet needs:

| Key class | Examples | Recoverable from elsewhere? |
| :--- | :--- | :--- |
| **Irrecoverable** — encrypts the B2 restic repo; if lost, all B2 backups are permanently unreadable | `BACKREST_RESTIC_PASSWORD` | **NO** — restic itself stores no recovery mechanism |
| Third-party-issued (revoke + reissue is annoying but possible) | `CLOUDFLARE_API_TOKEN`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, `NAMECHEAP_API_KEY`, etc. | yes (revoke at provider, reissue) |
| Service-generated (regen at next deploy) | `API_KEY`, `SERVICE_INTERNAL_SECRET_KEY`, per-service tokens | yes |

The single key that **must** survive is `BACKREST_RESTIC_PASSWORD`. Everything else can be reissued at some operational cost. This doc's mechanism preserves the entire file, so all three classes are recoverable in one step.

## How the mirror works

```text
┌──────────────────────────────┐  push   ┌──────────────────────────────────────┐
│ dev WSL                      │ ──────▶ │ GitHub (private)                     │
│                              │         │   mobasak/fabrik-dr-store            │
│  /opt/fabrik/.env  ─────┐    │         │     env/latest                       │
│   (canonical, local)    │    │         │     env/fabrik-env-YYYYMM…Z          │
│                         │    │         │       (last 60 retained)             │
│  vps1:                  │    │         │                                      │
│  /opt/fabrik/           │    │         │     env/sysadmin-latest              │
│  .env.sysadmin   ┐ SSH  │    │         │     env/fabrik-env-sysadmin-YYYY…Z   │
│   (vps1-only)    └─pull─┤    │         │       (last 60 retained)             │
│                         ▼    │         │                                      │
│  scripts/dr_env_backup.sh   ─┼────────▶│                                      │
│                              │         │                                      │
│  cron:                       │         └──────────────────────────────────────┘
│   30 3 * * *  daily safety
│   @reboot     boot catchup
│   0 4 * * 0   weekly self-test
└──────────────────────────────┘
```

Three trigger paths for the **main `.env`**:

1. **Inotify** (`fabrik-dr-watcher.service`) — fires on every `close_write` or `moved_to` event on `/opt/fabrik/.env`. Covers append-style edits (`echo >>`, `cat >`) and save-via-tempfile editors (vim, sed `-i`, VSCode). Sub-second latency.
2. **Daily cron** (`30 3 * * *`) — safety net for any edit that somehow slipped past inotify (e.g., WSL was down when the change happened, then came back up without restarting the watcher).
3. **`@reboot` cron** (`sleep 60 && ...`) — catches up after WSL boots if env changed while WSL was down. The 60-second sleep lets network come up.

**`.env.sysadmin` is mirrored on the cron paths only** — the inotify watcher (`fabrik-dr-watcher.service`) watches only `/opt/fabrik/.env`; `.env.sysadmin` is SSH-pulled fresh from vps1 on each cron run (the local copy is not the source of truth). Latency is therefore up to ~24 h (daily 03:30 + `@reboot`). Acceptable because the sysadmin token changes <once per year (BotFather token rotation). The pull uses `ssh -o BatchMode=yes -o ConnectTimeout=8 vps 'sudo cat /opt/fabrik/.env.sysadmin'`; failure (vps1 briefly unreachable, NOPASSWD revoked, etc.) logs a warning and the main mirror still proceeds — the sysadmin file is **soft-required**, not blocking.

Plus a weekly recovery self-test:

- **`0 4 * * 0`** — `scripts/dr_env_recovery_test.sh` reads `/opt/fabrik-dr-store/env/latest`, extracts credentials, and confirms they can read the B2 restic repo by routing restic through `sudo docker exec backrest /bin/restic`. Logs to `/var/log/dr-env-recovery-test.log`. The B2 repo is now initialized (restic 0.18.1, snapshots present), so the script takes its healthy branch and logs `OK: N snapshots readable with recovered creds` (recent runs: 71 → 107 → 142 snapshots; the log rotates, older entries drop off). The `AWAITING-W2: …` branch remains in the script as an obsolete pre-init guard and no longer triggers. A one-off `FAIL` (2026-06-21, ssh timeout) self-recovered on the next run.

## Security model

The **private GitHub repo IS the security boundary** — same threat-model logic the operator already accepts for the main `mobasak/fabrik` code repo. Single-operator dev environment; no realistic attacker model named.

Hardening posture on `mobasak/fabrik-dr-store`:

- Visibility: **private**
- Collaborators: **none** (owner only)
- Actions: **none configured** (no `.github/workflows/`)
- Issues: **disabled**
- Projects: **disabled**
- Wiki: **disabled**
- Discussions: **disabled**

Never enable any of the above. Never make public. Never add collaborators. Never wire it to a GitHub Action that could exfiltrate. The privacy of the repo is load-bearing.

## Recovery — fresh WSL, env gone

One operator command:

```bash
gh auth login  # if needed
gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store
sudo mkdir -p /opt/fabrik
sudo cp /opt/fabrik-dr-store/env/latest /opt/fabrik/.env
sudo chown ozgur:ozgur /opt/fabrik/.env
sudo chmod 600 /opt/fabrik/.env
```

That's the full recovery for the main `.env`. The watcher + cron will resume from the next change.

## Recovery — sysadmin bot creds (vps1 wipe or fresh rebuild)

`env/sysadmin-latest` holds the Telegram bot token + owner ID **for vps1 only**. When standing up a fresh vps1 (after disk loss, full rebuild, or DR drill):

> **Spokes do NOT use `env/sysadmin-latest`.** PR3 (2026-06-13) auto-provisions each spoke's AI sysadmin during `fabrik vultr provision` by claiming a *per-host* token from the DR-store pool `env/sysadmin-bot-tokens.json` — a recovery operator must not assume the single `env/sysadmin-latest` covers vps2/vps3.

```bash
# Pull the sysadmin creds from the DR store (assumes you've already cloned it per above)
sudo install -m 600 -o ozgur -g ozgur /opt/fabrik-dr-store/env/sysadmin-latest \
  /tmp/.env.sysadmin.recovered

# Push to the rebuilt vps1
scp /tmp/.env.sysadmin.recovered vps:/tmp/.env.sysadmin.recovered
ssh vps 'sudo install -m 600 -o root -g root /tmp/.env.sysadmin.recovered /opt/fabrik/.env.sysadmin \
  && rm /tmp/.env.sysadmin.recovered \
  && sudo systemctl restart vps-sysadmin-bot.service \
  && sudo systemctl is-active vps-sysadmin-bot.service'

rm /tmp/.env.sysadmin.recovered
```

Verify the bot is talking again by messaging it on Telegram, or check the heartbeat via `curl http://127.0.0.1:8017/health` on vps1.

## Recovery — lost GitHub access

If the GitHub account is lost AND `/opt/fabrik/.env` is gone simultaneously:

1. **Reissue everything that can be reissued.** That covers Cloudflare token, B2 keys, Namecheap, every service-issued key.
2. **`BACKREST_RESTIC_PASSWORD` is unrecoverable.** B2 backups in the `vps1-ocoron-backups` bucket become permanently unreadable — they're encrypted with that password and restic stores no recovery mechanism.
3. **vps1 disk data is still intact** (assuming you haven't lost vps1 too). You can `pg_dump` glitchtip + site_provisioner directly, scp `/opt/<svc>/.env` files off vps1, rebuild the env from those primary sources. The B2 backup chain is broken until you re-init restic with a new password (treat as a full DR-key rotation event).

This is the worst-case scenario the W9 design accepts because it's already accepted for the main code repo.

## Recovery flow — DR self-test (no actual data loss)

Run this any time to validate the chain works without touching production state:

```bash
# Move the live env aside
sudo mv /opt/fabrik/.env /opt/fabrik/.env.bak

# Restore from the DR store
sudo cp /opt/fabrik-dr-store/env/latest /opt/fabrik/.env
sudo chown ozgur:ozgur /opt/fabrik/.env
sudo chmod 600 /opt/fabrik/.env

# Confirm the restored env is identical to what was live
diff /opt/fabrik/.env.bak /opt/fabrik/.env  # expect: empty output

# Confirm a fabrik op succeeds against restored creds (dry-run, no mutation)
cd /opt/fabrik && .venv/bin/fabrik apply specs/services/site-provisioner.yaml --dry-run --yes

# Restore the original
sudo mv /opt/fabrik/.env.bak /opt/fabrik/.env
```

The weekly cron at `0 4 * * 0` runs a more limited variant — it doesn't touch `/opt/fabrik/.env` at all, just reads `/opt/fabrik-dr-store/env/latest` and validates restic can connect to B2 with the credentials in it.

## Files involved

| Path | Role |
| :--- | :--- |
| [`/opt/fabrik/scripts/dr_env_backup.sh`](../../scripts/dr_env_backup.sh) | Single-shot backup: copy + commit + push if content changed |
| [`/opt/fabrik/scripts/dr_env_watcher_loop.sh`](../../scripts/dr_env_watcher_loop.sh) | Long-running inotify loop calling `dr_env_backup.sh` per event |
| [`/opt/fabrik/scripts/dr_env_recovery_test.sh`](../../scripts/dr_env_recovery_test.sh) | Weekly self-test: validates recovered creds against B2 |
| `/etc/systemd/system/fabrik-dr-watcher.service` | systemd unit running the watcher loop |
| `/var/log/dr-env-watcher.log` | Watcher event log |
| `/var/log/dr-env-backup.log` | Daily-cron and reboot-cron backup log |
| `/var/log/dr-env-recovery-test.log` | Weekly recovery self-test log |
| `/opt/fabrik-dr-store/` | Local clone of `mobasak/fabrik-dr-store` (the GitHub mirror) |
| `mobasak/fabrik-dr-store` | The GitHub private repo; `env/latest` is the recovery source |
| `crontab -l` on dev WSL | 3 entries: daily backup, reboot backup, weekly test |

## Known operational quirks

### `cmp -s` exit 2 when the file is unreadable to ozgur

`dr_env_backup.sh` does `if [ -f "$REPO/env/latest" ] && cmp -s "$ENV_PATH" "$REPO/env/latest"`. If the bash conditional sees `cmp -s` exit with code 2 (file unreadable — distinct from exit 1 "files differ"), it treats the result as falsy and falls through to push. In practice this happens only when `/opt/fabrik/.env` is momentarily owned by root (e.g., between a `sudo cp` and a `sudo chown`). The DR self-test in step 7 of W9 exercised this path and produced one extra "no-content-change" commit because the test used `sudo cp` to restore. In real-world use where edits happen as `ozgur`, this edge case never fires. Safe-default behavior: when uncertain, back up.

### Log files are not rotated

`/var/log/dr-env-{watcher,backup,recovery-test}.log` grow without bound. Current growth rate is a few hundred bytes per day (each backup adds one line; recovery test adds one line per week). Not urgent. When it becomes an issue, drop a `/etc/logrotate.d/fabrik-dr` file rotating these three weekly with `delaycompress` + 8 keep.

## Routine maintenance

None expected. The system is push-driven and self-validating. The weekly cron's log will show one of three states forever:

- `OK: N snapshots readable with recovered creds` — full chain healthy (post-W2)
- `AWAITING-W2: DR pipeline configured + creds valid` — pre-W2 state
- `FAIL: <reason>` — real DR-chain failure, investigate

If you ever see the `FAIL` state, that's a real DR incident. Check:

1. SSH to vps1 working (`ssh vps echo OK`)
2. Backrest container running (`ssh vps 'sudo docker ps --filter name=backrest'`)
3. B2 still reachable (`ssh vps 'sudo docker exec backrest /bin/restic -r s3:... cat config'`)
4. The `latest` file in `/opt/fabrik-dr-store/env/` actually has all 3 keys (`BACKREST_RESTIC_PASSWORD`, `B2_KEY_ID`, `B2_APPLICATION_KEY`)
