---
activation: glob
globs: ["scripts/bootstrap/**/*.sh", "scripts/bootstrap/**/*.template", "docs/infrastructure/vps-*-rebuild.md", "docs/infrastructure/vps-bootstrap-plan.md"]
description: Bootstrap script discipline — SSH user transition, fail2ban trap, idempotency, quote escaping
trigger: glob
---
<!-- CONSUMER: Coding agents (all) running drills, restores, or edits to bootstrap-vps.sh / bootstrap-hub.sh / bootstrap-spoke-restore.sh / sysadmin-cron.template / aro-wake.service.template
     GOAL: Encode the operator-discipline traps that live-bit us in real drills so any AI agent walking into the same situation gets caught by the rules, not by trial and error.
     AGENT USAGE: Before running ANY bootstrap script, read the "SSH user transition" rule. Before editing the remote-bash quoting in any step, read the "Quote escaping" rule. -->

# Bootstrap Script Discipline

Applies when running, editing, or debugging any script under `scripts/bootstrap/` or any operator-rebuild doc under `docs/infrastructure/vps-*-rebuild.md`. These rules encode operator-discipline traps that the project has hit in real drills. Walking past one of these will burn 10+ minutes of recovery time minimum.

## Rule 1 — SSH user transition (CRITICAL)

`step_01` of `bootstrap-vps.sh` and `bootstrap-hub.sh` **disables root SSH login** on the target VPS. This is correct security posture and unconditional. It means:

| When | Use this SSH user | Why |
|---|---|---|
| **First run on a fresh VPS** | `root@<new-ip>` | step_00 hasn't created the `ozgur` sudoer yet — root is the only login that exists |
| **Any re-run after step_01 succeeded** | **`ozgur@<new-ip>`** | step_01 has disabled root SSH; `ozgur` was created with NOPASSWD sudo by step_00 |

The bootstrap script handles either user as input — it maintains an `EFFECTIVE_REMOTE` variable that auto-switches to `ozgur@` after step_00 within a single run (see `bootstrap-vps.sh` comment at lines 139–142). The operator-side trap is that `REMOTE="$1"` is re-read fresh on every script invocation.

### Failure mode if you walk into this

1. First run as `root@<ip>` succeeds → step_01 disables root login
2. Step 14 (or any later step) crashes for any reason → script aborts
3. You re-run as `root@<ip>` (forgetting step_01 ran) → SSH preflight fails
4. You re-try → SSH preflight fails again
5. **fail2ban (default 3-failure threshold within 10 min) bans your dev WSL public IP**
6. You are locked out of the target VPS for 10 minutes
7. The only ways to recover: wait, reboot the VPS via provider web console, or SSH from a different source IP

### What the script does to defend you

The preflight in both `bootstrap-vps.sh` and `bootstrap-hub.sh` (since 2026-06-07) detects this trap automatically:

- If `REMOTE` is `root@<host>` and SSH fails
- AND `ozgur@<host>` succeeds with `sudo -n id`
- Then the script aborts BEFORE trying the failing SSH again, and prints:

```
SSH to root@<ip> failed BUT ssh ozgur@<ip> works.
step_01 has already run on this host (root login disabled).

Re-run as the sudoer:
  ./scripts/bootstrap/bootstrap-vps.sh [options] ozgur@<ip> <spoke-name>

Stopping now — additional root@<ip> retries WILL trip fail2ban (default 3 failures / 10 min) and lock you out.
```

**If you see this message, switch to `ozgur@<ip>` and re-run. Do not retry with `root@<ip>`.**

### What you should do BEFORE running any bootstrap script

1. Look at the script's `EFFECTIVE_REMOTE` comment (around line 139 in `bootstrap-vps.sh`) and verify the user-transition design hasn't changed.
2. If you're re-running after a partial failure: assume `step_01` has already disabled root login. Use `ozgur@<ip>`. Do not test root first.
3. If you've already triggered fail2ban: do not keep retrying. Reboot the droplet via the provider's web console (30 sec) or wait 10 min.

## Rule 2 — Remote-bash quote escaping (CRITICAL)

Inside `remote '...'` single-quoted strings, **do not nest `$(...)` inside `echo "..."`** if the inner command also uses double-quoted strings. The local bash parser accepts it; the remote bash (via ssh) does not — you get a syntax error at runtime.

### Bad — caught by first DR drill 2026-06-07

```bash
remote 'if python3 -c "import telegram" 2>/dev/null; then
    echo "already installed: $(python3 -c \"import telegram; print(telegram.__version__)\")"
fi'
# Remote bash: syntax error near unexpected token `telegram.__version__'
```

### Good — capture into a variable first

```bash
remote 'if python3 -c "import telegram" 2>/dev/null; then
    VER=$(python3 -c "import telegram; print(telegram.__version__)")
    echo "already installed: $VER"
fi'
```

### Even better — drop the version-print

```bash
remote 'if python3 -c "import telegram" 2>/dev/null; then
    echo "already installed"
fi'
```

Cosmetic version-strings are not worth the parser hazard. Knowing the package is installed is sufficient; the operator can query the version manually if needed.

### Test it before shipping

Whenever you edit a `remote '...'` block, run `bash -n scripts/bootstrap/bootstrap-vps.sh` (catches LOCAL parser errors only) AND do a `--verify` dry-run against any reachable VPS (catches REMOTE parser errors). The remote-bash syntax error WILL NOT be caught by `bash -n` of the local script — only by an actual ssh execution.

## Rule 3 — Idempotency by `command -v` / `which` / state probes

Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be wrapped in an idempotency check:

```bash
# Good
if ! command -v claude >/dev/null; then
    sudo npm install -g @anthropic-ai/claude-code
fi

# Good
if ! python3 -c "import telegram" 2>/dev/null; then
    sudo pip install --break-system-packages python-telegram-bot==22.7
fi

# Good
if ! systemctl cat aro-wake.service >/dev/null 2>&1; then
    sudo install -m 644 ...
fi
```

If the operator re-runs the script (which they will — bootstrap is allowed to fail partway and be restarted), every step must be a no-op when its outcome is already present. Live-verify by running the script against an already-bootstrapped VPS — every step should print `already installed` or `already configured`, never re-do work.

## Rule 4 — `--skip-mesh` + `--skip-dns` for DR drills against a throwaway VPS

When drilling bootstrap on a throwaway VPS (e.g. a $0.02 Vultr droplet), use both flags:

```bash
./scripts/bootstrap/bootstrap-vps.sh --skip-mesh --skip-dns root@<throwaway-ip> vps4
```

- `--skip-mesh` prevents the script from writing a new `[Peer]` block to vps1's `/etc/wireguard/wg0.conf`. Without it, drilling leaves a stale peer entry on production vps1 that needs manual cleanup.
- `--skip-dns` prevents calling site-provisioner to create `*.vps4.ocoron.com` DNS records. Without it, drilling pollutes the production DNS zone.

Both flags make the drill HERMETIC — destroying the throwaway droplet at the end leaves zero residue on production infrastructure.

## Rule 5 — Spoke name must match `^vps[0-9]+$`

Validation at `bootstrap-vps.sh` line 104. For DR drills against a throwaway, use `vps4` (or higher unused number). Do not use `vps-drill` or other free-form names — the script will reject at preflight.

`vps4` is conventionally reserved as "the next available drill identity" in this codebase. After drilling, no cleanup is needed on vps1 because `--skip-mesh` was used.

## Rule 6 — Never retry SSH more than twice without checking fail2ban

If your SSH preflight fails twice, the third attempt is what crosses fail2ban's threshold. Stop after the second failure. Diagnose first. Options:

```bash
# Confirm the public IP we're connecting from (will be the banned one)
curl -s https://api.ipify.org

# If you have a different-IP shell (e.g. via vps1), check fail2ban state on target
ssh vps "ssh ozgur@<target-ip> 'sudo fail2ban-client status sshd 2>&1 | head -15'"
```

If the fail2ban ban-list shows your dev WSL IP, your only options are: (a) wait 10 min, (b) reboot the target VPS via provider web console (clears state), or (c) get the target to remove your IP via console-login (Vultr, DO, Hetzner all support browser-based console).

## Rule 7 — A cron redirect the RUNNING USER cannot write aborts the job silently, forever

`* * * * * /path/script.sh >> /var/log/thing.log 2>&1` looks correct and is a **permanent silent
failure** whenever the cron's user cannot create that file. The shell opens the redirect **before**
exec'ing the script, so the job dies with no output, no log line, and no error anywhere — the script
never runs, and the absent log looks like "it ran and printed nothing".

Founding incident: `scripts/sysadmin/liveness_audit.py:10-11` — the Claude-config DR backup had never
once run from cron for exactly this reason. Reproduced again 2026-08-29 (`touch /var/log/x` →
`Permission denied` for the WSL user), when a plan copied an existing `>> /var/log/…` line verbatim from
a working precedent and shipped the same defect; only a native Opus reviewer caught it.

**Why the precedent misleads:** the `/var/log/…` redirects that DO work on the VPS work because those
files were **pre-created** (or the cron runs as root). Copying such a line into a user crontab, or onto
a box where the file does not exist, silently reproduces the bug. Root-on-VPS and user-on-WSL are
different worlds and the line looks identical in both.

**Before proposing ANY cron line, prove the redirect target:**

```
$ sudo -u <the cron's user> test -w "$(dirname /var/log/thing.log)" && echo writable || echo NOT
```

Prefer a path the user owns outright — `$HOME/.claude/state/<name>.log` or the project's own
`logs/` — over `/var/log/`. If `/var/log/` is genuinely required, the provisioning step that
**creates the file with the right owner** is part of the change, not an assumption.

⚠️ **Not mechanically gated, deliberately.** 32 `>> /var/log/` redirects exist across this repo's docs,
scripts and templates, and most are correct — VPS root cron writing pre-created files. A check flagging
all of them would fire mostly on legitimate lines, and a rule that is routinely waived teaches agents
that the gate's findings are advisory. Writability depends on the user and the host; only the author can
resolve it, which is why this is a rule you apply rather than a check that fires.

## Cross-references

- Worked example of these rules being applied / discovered: 2026-06-07 first DR drill (commit log entry `bootstrap: bake 4 spoke deps into bootstrap-vps.sh + ...`)
- Bootstrap script entry points: `scripts/bootstrap/bootstrap-vps.sh`, `scripts/bootstrap/bootstrap-hub.sh`, `scripts/bootstrap/bootstrap-spoke-restore.sh`
- Operator runbooks: `docs/infrastructure/vps-spoke-rebuild.md`, `docs/infrastructure/vps-hub-rebuild.md`, `docs/infrastructure/vps-bootstrap-plan.md`
