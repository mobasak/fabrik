---
activation: glob
globs: ["scripts/bootstrap/**/*.sh", "scripts/bootstrap/**/*.template", "scripts/aro-wake/templates/*.template", "docs/infrastructure/vps-*-rebuild.md", "docs/infrastructure/vps-bootstrap-plan.md"]
description: Bootstrap script discipline — SSH user transition, effective sshd config, fail2ban lockout, idempotency, quote escaping, cron redirects
trigger: glob
currency_pass: 2026-10-04
---
<!-- CONSUMER: Coding agents (all) running drills, restores, or edits to scripts/bootstrap/bootstrap-vps.sh,
     scripts/bootstrap/bootstrap-hub.sh, scripts/bootstrap/bootstrap-spoke-restore.sh,
     scripts/bootstrap/templates/sysadmin-cron.template or
     scripts/aro-wake/templates/aro-wake.service.template.
     GOAL: Encode the operator-discipline traps that live-bit us in real drills so any AI agent walking into the same
     situation gets caught by the rules, not by trial and error.
     AGENT USAGE: Before running ANY bootstrap script, read Rule 1. Before editing the remote-bash quoting in any step,
     read Rule 2. Research basis: docs/reference/research/2026-10-04-bootstrap-scripts-currency-ledger.md. -->

# Bootstrap Script Discipline

Applies when running, editing, or debugging any script under `scripts/bootstrap/` or any operator-rebuild doc under
`docs/infrastructure/vps-*-rebuild.md`. These rules encode operator-discipline traps that the project has hit in real
drills. Walking past one of these will burn 10+ minutes of recovery time minimum. Only the hub carries these scripts;
no project repo has a `scripts/bootstrap/`. `scripts/bootstrap/bootstrap-config.sh` holds the settings the three
scripts source (users, mesh, ports): an edit there changes every script at once, so re-run each script's `--verify`
after it.

## Rule 1 — SSH user transition (CRITICAL)

`step_01` of `bootstrap-vps.sh`, `bootstrap-hub.sh` and `bootstrap-spoke-restore.sh` **disables root SSH login**
(`PermitRootLogin no`) on the target VPS. This is correct security posture and unconditional. It means:

| When | Use this SSH user | Why |
|---|---|---|
| **First run on a fresh VPS** | `root@<new-ip>` | step_00 hasn't created the `ozgur` sudoer yet — root is the only login that exists |
| **Any re-run after step_01 succeeded** | **`ozgur@<new-ip>`** | step_01 has disabled root SSH; `ozgur` was created with NOPASSWD sudo by step_00 |

The bootstrap scripts handle either user as input — each keeps an `EFFECTIVE_REMOTE` variable that switches to
`ozgur@` after step_00 within a single run (`bootstrap-vps.sh`: the comment at lines 139–142, the switch at the end
of step_00). The operator-side trap is that `REMOTE="$1"` is re-read fresh on every script invocation.

### Failure mode if you walk into this

1. First run as `root@<ip>` succeeds → step_01 disables root login
2. Step 14 (or any later step) crashes for any reason → script aborts
3. You re-run as `root@<ip>` (forgetting step_01 ran) → SSH preflight fails
4. You keep re-trying → each attempt is another authentication failure
5. **fail2ban bans your dev WSL public IP.** No bootstrap script writes a jail config, so the Ubuntu package's
   defaults apply: the package enables the `sshd` jail, and upstream's defaults ban after **5 failures within 10
   minutes, for 10 minutes**. A refused root login counts once per key the client offers that root's
   `authorized_keys` accepts, so a client with several such keys burns several failures per attempt.
6. You are locked out of the target VPS for 10 minutes
7. The only ways to recover: wait, use the provider's web console (Rule 6), or SSH from a different source IP

### What the scripts do to defend you

The preflight in `bootstrap-vps.sh` and `bootstrap-hub.sh` (since 2026-06-07) detects this trap automatically:

- If `REMOTE` is `root@<host>` and SSH fails
- AND `ozgur@<host>` succeeds with `sudo -n id`
- Then the script aborts BEFORE trying the failing SSH again. Its message begins:

```
SSH to root@<ip> failed BUT ssh ozgur@<ip> works.
step_01 has already run on this host (root login disabled).
```

and tells you to re-run with `ozgur@<ip>`. It goes on to warn that more root retries will trip fail2ban, citing a
three-failure threshold that is out of date — the defaults are above.

**If you see this message, switch to `ozgur@<ip>` and re-run. Do not retry with `root@<ip>`.**

### What you should do BEFORE running any bootstrap script

1. Look at the script's `EFFECTIVE_REMOTE` comment (around line 139 in `bootstrap-vps.sh`) and verify the
   user-transition design hasn't changed.
2. If you're re-running after a partial failure: assume `step_01` has already disabled root login. Use
   `ozgur@<ip>`. Do not test root first.
3. If you've already triggered fail2ban: do not keep retrying (Rule 6).

### Verify the EFFECTIVE sshd config, not the file you edited

sshd uses the **first** value it reads for each keyword, and Ubuntu's `sshd_config` includes
`/etc/ssh/sshd_config.d/*.conf` at the top, in lexical order. Ubuntu images ship their own drop-ins:
cloud-init's `50-cloud-init.conf` may say `PasswordAuthentication yes` (it carries whatever the image or installer
chose), while `60-cloudimg-settings.conf` says `no`. Either way, any drop-in that sorts before yours wins over a later
`99-…` drop-in and over any edit to the main `sshd_config`. So:

- Put hardening in a **low-numbered** drop-in (e.g. `01-fabrik-hardening.conf`), not a `99-…` one and not a `sed` on
  the main file.
- Before reloading, **assert the effective value** with
  `sudo sshd -T | grep -Ei '^(permitrootlogin|passwordauthentication) '` — `-T` runs every check `-t` does and then
  prints the configuration sshd will actually use; it needs root because the host keys are root-only. A clean
  `sshd -t` passes while a cloud drop-in silently overrides you.
- When cloud-init's `disable_root` is on (its default), it also prefixes root's `authorized_keys` so a root key
  login prints a "log in as the user …" message and exits — a different mechanism from `PermitRootLogin`. The
  providers this fleet uses ship images that allow the first root login (the table above), so it is off there.

## Rule 2 — Remote-bash quote escaping (CRITICAL)

Inside `remote '...'` single-quoted strings, **do not nest `$(...)` inside `echo "..."`** if the inner command also
uses double-quoted strings. Inside single quotes a backslash escapes nothing, so `\"` reaches the remote shell as
two literal characters, and the remote bash — the only shell that parses this program — hits a syntax error at
runtime.

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

Cosmetic version-strings are not worth the parser hazard. Knowing the package is installed is sufficient; the
operator can query the version manually if needed.

### Test it before shipping

Whenever you edit a `remote '...'` block, run `bash -n scripts/bootstrap/bootstrap-vps.sh` (catches LOCAL parser
errors only) AND do a `--verify` dry-run against any reachable VPS (catches REMOTE parser errors). `bash -n` reads
the single-quoted remote program as one string literal and never parses it, so the remote-bash syntax error WILL NOT
be caught by `bash -n` of the local script — only by an actual ssh execution.

## Rule 3 — Idempotency by `command -v` / state probes

Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already
present. Probe with `command -v` (the POSIX builtin, which looks a name up the way the shell will) — not `which`,
which is non-standard:

```bash
# Good — Claude Code's recommended route is the native installer, which also keeps itself updated
if ! command -v claude >/dev/null; then
    curl -fsSL https://claude.ai/install.sh | bash
fi

# Good — a step that overwrites is idempotent by construction; verify afterwards
sudo install -m 644 scripts/aro-wake/templates/aro-wake.service.template /etc/systemd/system/aro-wake.service
systemctl cat aro-wake.service >/dev/null 2>&1 && echo "unit installed OK"
```

- **Claude Code:** the docs recommend the native installer; the npm package is an alternative that needs Node.js
  only while npm installs it (the binary it fetches does not use Node) and must **not** be installed with
  `sudo npm install -g`. The installer needs about 512 MB of free memory: on a small VPS, an install that dies with
  `Killed` (exit 137) was the OOM killer — add swap and re-run. Running it needs the documented 4 GB of RAM, so a box
  that installs fine can still run out of memory when a bot starts `claude`. Headless boxes authenticate with a
  long-lived token from `claude setup-token` in `CLAUDE_CODE_OAUTH_TOKEN`.
- **Python packages:** Ubuntu marks its system Python externally managed (PEP 668), so a plain `pip install` fails.
  `--break-system-packages` overrides that at the risk of breaking the OS's own Python; prefer an apt `python3-…`
  package, a venv, or `pipx`. The `python-telegram-bot` install in `bootstrap-vps.sh` still uses the override,
  because the bot's unit runs the system `python3` and the two must move together (W-eccfcc2a); new dependencies go
  into a venv.

If the operator re-runs the script (which they will — bootstrap is allowed to fail partway and be restarted), every
step must be a no-op when its outcome is already present. Live-verify by running the script against an
already-bootstrapped VPS — every step should print `already installed` or `already configured`, never re-do work.

## Rule 4 — `--skip-mesh` + `--skip-dns` for DR drills against a throwaway VPS

When drilling `bootstrap-vps.sh` on a throwaway VPS, use both flags:

```bash
./scripts/bootstrap/bootstrap-vps.sh --skip-mesh --skip-dns root@<throwaway-ip> vps4
```

- `--skip-mesh` skips the WireGuard steps, including the one that writes a new `[Peer]` block to vps1's
  `/etc/wireguard/wg0.conf`. Without it, drilling leaves a stale peer entry on production vps1 that needs manual
  cleanup.
- `--skip-dns` skips the step that calls site-provisioner to create `*.vps4.ocoron.com` DNS records. Without it,
  drilling pollutes the production DNS zone.

Both flags make the drill write nothing to production — destroying the throwaway droplet at the end leaves zero
residue. The preflight still reads vps1 (it checks the hub's WireGuard state), so the hub must be reachable. `bootstrap-hub.sh` and `bootstrap-spoke-restore.sh` accept `--skip-mesh` and `--verify` but have no
`--skip-dns`.

## Rule 5 — Spoke name must match `^vps[0-9]+$`

Validation at `bootstrap-vps.sh` line 104, during argument parsing. For DR drills against a throwaway, use `vps4` (or
higher unused number). Do not use `vps-drill` or other free-form names — the script will reject them.

`vps4` is conventionally reserved as "the next available drill identity" in this codebase. After drilling, no cleanup
is needed on vps1 because `--skip-mesh` was used.

## Rule 6 — Never retry SSH more than twice without checking fail2ban

The ban threshold is five failures in ten minutes by default (Rule 1), but one attempt can count more than once
and the preflight's own probes count too. Stop after the second failure and diagnose first:

```bash
# Confirm the public IP we're connecting from (will be the banned one)
curl -s https://api.ipify.org

# If you have a different-IP shell (e.g. via vps1), check fail2ban state on target
ssh vps "ssh ozgur@<target-ip> 'sudo fail2ban-client status sshd 2>&1 | head -15'"

# From any shell on the target (console or another IP), lift the ban
sudo fail2ban-client set sshd unbanip <your-ip>
```

On Ubuntu the `sshd` jail reads the systemd journal, so there may be no `auth.log` to grep — use
`journalctl -u ssh` beside `fail2ban-client status sshd`.

**Prevention:** fail2ban never bans an address in `ignoreip`. Adding the operator's IP and the mesh range in a
`/etc/fail2ban/jail.d/*.local` drop-in (or at runtime with `sudo fail2ban-client set sshd addignoreip <ip>`) retires
this whole lockout class; the bootstrap scripts do not do it yet.

If the ban-list shows your dev WSL IP, your options are: (a) wait 10 min, (b) log in through the provider's browser
console and unban, or (c) SSH from another IP. The consoles work without network SSH but need a **password** login:
DigitalOcean's **Recovery Console** (its Droplet Console needs a working sshd; reset the root password from the
control panel), Vultr's noVNC **View Console**, and Hetzner's VNC console (reset the root password from Rescue). A
key-only box has no password until you reset one.

## Rule 7 — A cron redirect the RUNNING USER cannot write aborts the job silently, forever

`* * * * * /path/script.sh >> /var/log/thing.log 2>&1` looks correct and is a **permanent silent
failure** whenever the cron's user cannot create that file. The shell opens the redirect **before**
exec'ing the script, and a redirect that cannot open the file fails the command — so the job dies with no output in
the log, the script never runs, and the absent log looks like "it ran and printed nothing". Cron runs the line with
`/bin/sh`; the shell's error goes to cron's mail (the crontab owner, or `MAILTO`), and on a box with no mail agent
cron discards it. The journal (`journalctl -t CRON`) then shows only that the job ran and that its output was
discarded — never the shell's error — so the writability probe below is the diagnostic, not the log.

Founding incident: `scripts/sysadmin/liveness_audit.py:10-11` — the Claude-config DR backup had never
once run from cron for exactly this reason. Reproduced again 2026-08-29 (`touch /var/log/x` →
`Permission denied` for the WSL user), when a plan copied an existing `>> /var/log/…` line verbatim from
a working precedent and shipped the same defect; only a native Opus reviewer caught it.

**Why the precedent misleads:** the `/var/log/…` redirects that DO work on the VPS work because those files were
**pre-created** (`bootstrap-vps.sh` installs `/etc/cron.d/vps-sysadmin` and, in the same step, touches the sysadmin
logs and hands `claude-keepalive.log` to `ozgur`) or because the cron runs as root. Copying such a line into a user crontab, or
onto a box where the file does not exist, silently reproduces the bug. Root-on-VPS and user-on-WSL are different
worlds and the line looks identical in both.

**Before proposing ANY cron line, prove the redirect target:**

```
$ f=/var/log/thing.log; sudo -u <the cron's user> sh -c "test -w '$f' || { test ! -e '$f' && test -w \"\$(dirname '$f')\"; }" && echo writable || echo NOT
```

The sibling silent failure: cron ignores a file in `/etc/cron.d` whose name contains a dot (it follows run-parts'
naming — letters, digits, underscores and hyphens only), so a template installed as `vps-sysadmin.cron` never runs.

Prefer a path the user owns outright — `$HOME/.claude/state/<name>.log` or the project's own
`logs/` — over `/var/log/`. If `/var/log/` is genuinely required, the provisioning step that
**creates the file with the right owner** is part of the change, not an assumption.

⚠️ **Not mechanically gated, deliberately.** Dozens of `>> /var/log/` redirects exist across this repo's docs, scripts
and templates, and most are correct — VPS root cron writing pre-created files. A check flagging all of them would fire mostly on legitimate lines, and a rule
that is routinely waived teaches agents that the gate's findings are advisory. Writability depends on the user and
the host; only the author can resolve it, which is why this is a rule you apply rather than a check that fires.

## Cross-references

- Worked example of these rules being applied / discovered: 2026-06-07 first DR drill (commit `175ea6926`,
  `bootstrap: bake 4 spoke deps into bootstrap-vps.sh + ...`)
- Bootstrap script entry points: `scripts/bootstrap/bootstrap-vps.sh`, `scripts/bootstrap/bootstrap-hub.sh`,
  `scripts/bootstrap/bootstrap-spoke-restore.sh`; templates under `scripts/bootstrap/templates/`
- Operator runbooks: `docs/infrastructure/vps-spoke-rebuild.md`, `docs/infrastructure/vps-hub-rebuild.md`,
  `docs/infrastructure/vps-bootstrap-plan.md`
