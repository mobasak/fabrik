# Fleet AI-sysadmin Claude auth resilience — quota-triggered account rotation + monitoring honesty

**Status:** EXECUTED 2026-07-08 — all 6 phases (A–F) shipped + committed; whole-plan `/fabrik-review` converged (1 cross-phase finding fixed: keepalive regex parity); `final_gate.py --check --json` → `"status":"success"` (33/0) this turn; 66 sysadmin tests green. **Operator runbook remains** (trigger-not-execute): capture the `can@ocoron.com` snapshot, then run the Phase-F live-host rollout (push scripts → sync creds → shim cron → restart → forced-rotation verify) + the 2 live residuals (standby-token validity, per-container mem limit). Phase commits: A `ef82ba41` · B `b66fc8de` · C `572b6f41` · D `811455e2` · E `5d404dc5` · F `0cfa6daf` · whole-plan review-fix `ddffa96b`.
**Author:** Claude Opus 4.8 (hub) · from chat 2026-07-07
**Owner:** hub AI — sysadmin/watchdog stream (this session; created `f60f2bf4`). MINE, not a cross-stream sibling plan; a 2026-07-08 plan inventory misattributed it — corrected here. Not yet executed (`/fabrik-execute-plan` pending).

**Pass Ledger (`/fabrik-plan-review` — fixed point reached):**

| Pass | axes re-grounded | edits | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | claims · gates · interfaces · completeness (3 parallel grounders: A+B, C+D+E, structural+URLs) | ~14 | `2a51f063…` → `f89091c3…` |
| 2 | verify Pass-1 corrections (cron line, doc paths, alert lines, org names, proactive-check) | 1 (`:29`→`:32`) | `f89091c3…` → `22db642a…` |
| 3 | remaining citations (bot.py `:145/179/184/176/190`, aro-wake `:499/537/542`, daily-digest mtime) + structural pillars | **0** | `22db642a…` → `22db642a…` ✓ → **CONVERGED** |
| 4 (pre-execute re-review) | re-ground ALL citations vs current `master` (repo drifted since `f60f2bf4`) — every `path:line` still exact; found 2 residual consistency-drifts | 2 (Phase-B cron `:29`→`:32`; stale DRAFT self-audit line) | `a37d1b95…` → `83e27241…` |
| 5 (pre-execute re-review) | full re-scan: no other `:29`, no DRAFT/status contradiction, no banned `fabrik` gate, all 6 phases carry `/fabrik-review`, gate runnable | **0** | `8430b100…` → `8430b100…` ✓ → **CONVERGED (holds)** |

**Goal:** Make the fleet AI-sysadmin survive Claude subscription quota limits and stop failing silently. When a `claude -p` call hits a usage/quota limit, **auto-rotate** to the operator's second account and retry; keep both accounts' credentials **valid on every VPS**; make the health check **detect** an auth/quota break (it reports "fresh" through a month-long 401 outage); and **tune** the flapping alert that drives the wakes.

---

## What we already agreed (Phase 0 distillation)

- **Emergency already fixed (this chat):** valid creds copied to all 3 VPS; `claude -p` returns OK on vps1/2/3. This plan is the **durable** mechanism, not the un-break.
- **N accounts** (WSL `vishalguptax.claude-manager`, manual "Switch Account", 100% local) — the design supports **any number**, discovered by glob, account-name-agnostic. Currently on disk: `~/.claude/manager-accounts/mob-ocoron-com-s-organization/.credentials.json` (**Max 20x**) + `ob-ocoron-com-s-organization/.credentials.json` (**Pro**). **A 3rd login `can@ocoron.com` was added 2026-07-08 (user directive "n accounts should be supported"); its `manager-accounts/can-ocoron-com-s-organization/` snapshot must be captured via the claude-manager extension (switch to it once) — the rotation code + fleet-sync pick it up automatically by glob the moment it lands.** Active = `~/.claude/.credentials.json`. Rotation = **copy another snapshot over the active file** (extension does this on manual switch; it does NOT auto-rotate — we build that). On a usage-limit, `run_claude` walks through each *other* account at most once (bounded, no loop).
- **The quota signal (live-researched 2026-07-07, user directive "research and find out"):** Claude Code prints a **distinct** usage-limit message (NOT 401). Grounded verbatim renders (`claude-auto-retry` README) + Anthropic's own current docs (`code.claude.com/docs/en/errors`, "Usage limits") give these variants: `Claude usage limit reached. Resets at <t>` · `You've hit your weekly limit · resets <t>` · `You've hit your session limit · resets <t>` · `You've hit your Opus limit · resets <t>` · `<N>-hour limit reached - resets <t>` · `You're out of extra usage · resets <t>`. Detection is **output-string matching** — there is NO on-disk quota file to poll (confirmed; the extension reads Claude Code's live statusline).
- **401 ≠ quota:** `401 Invalid authentication credentials` = dead creds → **alert** (rotation won't help). Usage-limit → **rotate + retry once**.
- **Standby-cred staleness** is why the fleet died: only the *active* account self-refreshes; the inactive snapshot expires with no manager on the VPS. Fix: a **WSL→fleet sync** pushing both refreshed `manager-accounts/*/.credentials.json` to all 3 VPS.
- **Monitoring blind spot:** `daily-digest.sh:92` (+ the mtime freshness check in `proactive-check.sh:243-254`) reports "fresh" off the keepalive log **mtime**, never its content.
- **`ContainerHighMemory`** (`alerts.yml:32`, `expr … > 85`, `for: 5m`) fired ~38×/day — tune it.
- **Rejected:** `claude-auto-retry`'s "wait for reset" (we have a 2nd account → **rotate**); polling an on-disk quota file (none exists).

**Branch: RICH.** Goal + approach + the hard unknown (the quota signal) pinned/grounded in this chat.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | secret/credential handling — creds `chmod 600`, never logged/printed/committed; backup-before-overwrite of sensitive files | `35-security-auth.md:175-186` (read) |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | systemd/cron/rsync fleet-ops discipline | ACTIVE |
| `.windsurf/rules/core/60-watchdog.md` + `self-healing.md` + `cost-budget.md` (ACTIVE) | the sysadmin/self-heal + LLM-cost contract | ACTIVE |
| `fabrik-lib` — **no Claude-CLI account-rotation module** | `ai-consult/` = OpenRouter transport (wrong surface); `cost-budget/` = caps. **Build fresh, project-local.** 🆕 candidate (handoff). | `/opt/fabrik-lib/README.md` (read) |
| `AGENTS.md` — sysadmin + aro-wake topology | `vps-sysadmin-bot.service` (hub) + `aro-wake.service` (all hosts); host OAuth via `~/.claude/`; **two independent rsync trees + separate venvs** (`/opt/fabrik/.venv-aro-wake`) → no cross-dir import | `bootstrap-vps.sh:997-1125` (read) |
| `specs/services/*.yaml` `shape.*` | **no shape change** — host systemd/cron/scripts, not a deployed compose service | n/a |
| `scripts/bootstrap/templates/sysadmin-cron.template:32` | the **real** keepalive-cron source (`… /usr/bin/claude -p "ping" > /var/log/claude-keepalive.log 2>&1`), rendered by `bootstrap-vps.sh:985` → `/etc/cron.d/vps-sysadmin` | (read) |

**fabrik-lib consult (mandatory):** checked `/opt/fabrik-lib/README.md`; no Claude-Code-CLI credential-rotation module → fresh build, project-local. **🆕 fabrik-lib candidate:** `claude-account-rotate` (detect Claude-CLI usage-limit → swap `~/.claude/.credentials.json` between N accounts → retry; reusable by every subscription-billed operational agent). Propose in handoff; never write into `/opt/fabrik-lib`.

---

## Global Constraints (every phase inherits, verbatim)

- **Repo boundary:** edits in `/opt/fabrik` only. The WSL→fleet cred sync + live-host rollout write to the 3 VPS over SSH (operator's own fleet, authorized this chat); never another project repo or `/opt/fabrik-lib`.
- **Credential handling (`35-security-auth:175-186`):** `~/.claude/*.credentials.json` are `chmod 600`, **never logged/printed/committed**. Rotation swaps files; it never parses/emits token bytes.
- **Backup HARD-STOP carve-out:** the `manager-accounts/<org>/.credentials.json` snapshots ARE the durable copies — rotation **copies snapshot→active** and never mutates a snapshot, so the prior active value is always recoverable from a snapshot. To satisfy CLAUDE.md's "credentials change → backup" literally, `_rotate_active_account()` also writes the outgoing active to `~/.claude/.credentials.json.prev` (single rolling backup) before `os.replace`. This is the documented decision (backup-before-every-swap of a rotation is otherwise impractical).
- **Atomic + serialized swap:** rotation writes to a temp file then `os.replace` (atomic); wrap the read-active→decide→swap in an `flock` on `~/.claude/.claude-rotate.lock` so `bot.py` and `aro-wake/main.py` (independent processes on the same host) can't race the active file.
- **Quota-signal regex (verbatim, case-insensitive):** `usage limit reached | you've hit your (weekly|session|opus|[0-9]+-hour) limit | [0-9]+-hour limit reached | out of extra usage | limit\s*·\s*resets` — **pure alternation, no literal spaces around `|`**. `401` handled separately (`"401" in stderr` → alert, never rotate).
- **Rotation bounded:** at most **one** rotation + one retry per call; if the retry also limits/401s → give up, alert (both accounts exhausted/dead).
- **`run_claude` signature:** `run_claude(argv: list[str], timeout: int, cwd: str, env: dict[str,str]) -> subprocess.CompletedProcess` — `cwd`/`env` are REQUIRED (both callers pass `cwd=PROJECT_DIR` + `env` carrying `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`).
- **No cross-dir import:** `claude_rotate.py` is a **self-contained single file vendored byte-identical into both** `scripts/sysadmin/` and `scripts/aro-wake/` (they rsync + run under separate venvs; no shared import path exists).
- **Fleet SSH:** `vps` (172.93.160.197), `vps2`, `vps3`. Services `vps-sysadmin-bot.service`, `aro-wake.service`.
- **No `fabrik …` in gates.** Shared-master: explicit paths, provenance trailers, CHANGELOG atop `[Unreleased]`.

---

## One-Test Rule

**Why:** The single highest-risk behaviour in this plan is the quota-detection → rotate → retry decision in `run_claude` (Phase A). If it rotates on a 401 (dead creds, not quota) it burns the standby account for nothing; if it fails to rotate on a real usage-limit it never recovers; if it loops it can exhaust both accounts. One test pins that control flow before any wiring.

**Contract:**
- **Given:** two accounts exist under `~/.claude/manager-accounts/`, and `subprocess.run` is stubbed to return, on its first call, a usage-limit signal (e.g. `"You've hit your session limit · resets 3:45pm"`) then an OK result on the retry.
- **When:** `run_claude(argv, timeout, cwd, env)` is invoked.
- **Then:** it rotates the active account **exactly once** and retries, returning the retry's OK result; a stderr containing `401 Invalid authentication credentials` instead triggers **zero** rotations (alert path); two consecutive usage-limit results cause **≤1** rotation (no loop), returning the limit result.
- **Mocked:** `subprocess.run` (the `claude` invocation) and `_rotate_active_account` (the filesystem credential swap) are mocked; the **real** code under test is `is_usage_limit()`/`is_auth_401()` regex matching and the rotation-count / retry control flow. `cwd` and `env` pass-through to `subprocess.run` is asserted on the mock.

---

## Phase A — Rotation core (`scripts/sysadmin/claude_rotate.py`) — ✅ EXECUTED 2026-07-08

**Responsibility:** one tested module: run `claude`; on a usage-limit signal, atomically rotate the active account (serialized, with backup) and retry. Distinguish 401 (no rotate). **N-account** (user directive 2026-07-08 "n accounts should be supported"): walk through each *other* account at most once — bounded, never loops. **Also (user directive) a manual account CLI for WSL** — `claude_rotate.py --list | --switch <name|email|prefix> | --next` — so the operator switches the active account and reloads the VS Code workspace (no restart). Selection happens *under* the flock (race-safe); creds written `O_EXCL|O_NOFOLLOW` 0600 with a full-write loop; all FS steps fail-soft. Converged through 4 `/fabrik-review` rounds (27 tests, gate/ruff/mypy green).

**Files:**
- `scripts/sysadmin/claude_rotate.py` (**create**) — `run_claude(argv, timeout, cwd, env) -> CompletedProcess`; helpers `is_usage_limit(text)->bool`, `is_auth_401(text)->bool`, `_list_accounts()`, `_active_account()`, `_rotate_active_account()->str|None` (flock + write `.credentials.json.prev` + `os.replace` + `chmod 600`; returns new account name or None if <2 accounts). Never logs token bytes. First-25-lines `# AFTER-EDIT: scripts/sysadmin/bot.py, scripts/aro-wake/claude_rotate.py` (its co-located caller + the vendored twin).
- `scripts/sysadmin/test_claude_rotate.py` (**create**).

**Interfaces — Produces:** `run_claude(argv, timeout, cwd, env)->CompletedProcess`, `is_usage_limit(str)->bool`, `is_auth_401(str)->bool`, `_rotate_active_account()->str|None`. **Consumes:** nothing.

**Steps (highest-risk test FIRST):**
1. **Write failing test** `test_claude_rotate.py`: `is_usage_limit()` True for ALL grounded strings incl. `"You've hit your session limit · resets 3:45pm"` and `"You've hit your Opus limit · resets 3:45pm"`; False for `"401 Invalid authentication credentials"` + benign text. `is_auth_401()` True only for the 401 string. `run_claude` (mock `subprocess.run` → usage-limit then OK; mock `_rotate_active_account`) rotates exactly once → returns OK; two consecutive limits → ≤1 rotation, returns the limit result (no loop). `run_claude` **passes `cwd` and `env` through** to `subprocess.run` (assert the mock received them). Run → **RED**.
2. Implement to green: `_list_accounts` globs `~/.claude/manager-accounts/*/`; `_rotate_active_account` `flock`s `~/.claude/.claude-rotate.lock`, `cmp`s active vs each snapshot to find the *other*, writes active→`.credentials.json.prev`, `os.replace(other_snapshot_copy, active)`, `chmod 600`.
   - Gate: `python -m pytest scripts/sysadmin/test_claude_rotate.py -q` → all pass.
   - Gate: `python -c "import ast;ast.parse(open('scripts/sysadmin/claude_rotate.py').read());print('ok')"` → `ok`.
   - Gate: `python scripts/enforcement/check_script_headers.py scripts/sysadmin/claude_rotate.py 2>&1 | grep -c 'AFTER-EDIT'` → header present (WARN-only check; aro-wake twin created in Phase B).
3. **Doc-sync (explicit):** `CHANGELOG.md` entry; `INDEX.md` (2 new files); `docs/FEATURES.md` (rotation capability).
4. **Closing:** phase gate → `python scripts/enforcement/check_doc_sync.py` → **`/fabrik-review` on Phase-A surface via independent finder subagents, loop to a no-op pass** → commit (explicit paths, provenance trailers).

---

## Phase B — Vendor the twin + wire all three call sites + the cron template — ✅ EXECUTED 2026-07-08

**Responsibility:** every host claude invocation (bot, aro-wake, keepalive) routes through rotation.

**Files:**
- `scripts/aro-wake/claude_rotate.py` (**create** — byte-identical vendored copy of the Phase-A module; header `# AFTER-EDIT: scripts/aro-wake/main.py, scripts/sysadmin/claude_rotate.py`).
- `scripts/sysadmin/bot.py` (**modify**) — `_run_claude` (`bot.py:145`): replace `subprocess.run(["claude"…])` (`bot.py:179`, which passes `cwd=PROJECT_DIR`, `env=…`) with `claude_rotate.run_claude(argv, timeout, cwd=PROJECT_DIR, env=env)`; keep the `401` alert branch (`bot.py:190`).
- `scripts/aro-wake/main.py` (**modify**) — mirror `_run_claude` (`main.py:499`, subprocess at `:537` with `cwd=str(PROJECT_DIR)`): same swap, importing its co-located `claude_rotate`.
- `scripts/sysadmin/claude-keepalive-rotate.sh` (**create**) — the shim: `claude -p ping` via rotation; writes a **content token** (`KEEPALIVE_OK` / `KEEPALIVE_FAIL:<reason>`) to `/var/log/claude-keepalive.log` (single-run overwrite, matching the cron's `>`).
- `scripts/bootstrap/templates/sysadmin-cron.template` (**modify** `:32`) — swap the raw `/usr/bin/claude -p "ping" > …` for `/opt/fabrik/scripts/sysadmin/claude-keepalive-rotate.sh` (so new/re-provisioned hosts get the shim).
- `scripts/sysadmin/test_bot_rotation_wire.py` (**create**), + a byte-identity test: `cmp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py`.

**Interfaces — Consumes:** `claude_rotate.run_claude` (Phase A). **Produces:** all 3 sites rotation-enabled; keepalive log carries `KEEPALIVE_OK`/`KEEPALIVE_FAIL` (consumed by Phase D).

**Steps:** test-first (RED: bot calls bare subprocess; twin absent) → wire bot.py + aro-wake + vendor the twin + shim + cron template → GREEN → `bash -n scripts/sysadmin/claude-keepalive-rotate.sh`; `cmp` the twin is identical → **doc-sync (explicit): `CHANGELOG` + `INDEX.md` (new files)** → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase C — Standby-credential freshness sync (WSL → fleet) — ✅ EXECUTED 2026-07-08 (script + dry-run tests; live sync operator-run)

**Responsibility:** keep BOTH accounts valid on every VPS so a rotation lands on a usable account (the root cause).

**Files:**
- `scripts/sysadmin/sync-claude-accounts-to-fleet.sh` (**create**, runs on **WSL**) — for each VPS: `ssh <host> 'mkdir -p ~/.claude/manager-accounts/<org1> ~/.claude/manager-accounts/<org2>'` (the dirs do NOT exist on the VPS — bootstrap has zero `manager-accounts` refs), then `scp` both fresh `~/.claude/manager-accounts/*/.credentials.json`, `chmod 600`, and refresh active `~/.claude/.credentials.json` to the currently-active account. Idempotent; logs to `~/.cache/claude-fleet-sync.log` (no token bytes). Discovers org dirs by glob (account-name-agnostic).
- WSL cron (every 6h — conservative default; validated by the in-phase live test below).
- `scripts/sysadmin/test_sync_accounts.sh` (**create**) — `bash -n` + `DRY_RUN=1` asserting: 3 hosts, `mkdir -p` before scp, both account paths, never echoes token bytes.

**⚠️ Grounded dependency (residual #1):** whether an idle-synced snapshot's **refreshToken** still refreshes when swapped in. The creds JSON has only ONE `expiresAt` (the accessToken's — already stale for both idle accounts, which is normal); **there is no refreshToken-expiry field**, so `expiresAt` cannot answer this. **Resolution step (in-phase, the ONLY real test):** after first sync, on ONE VPS: rotate to the standby account → `claude -p ping` → expect OK. If it 401s, the standby refreshToken died between syncs → shorten the cron cadence and re-test; if still failing, escalate as a BLOCKING unknown (the manager may need to actively refresh standby tokens on WSL).

**Steps:** test-first (`bash -n` + dry-run) → implement (with `mkdir -p`) → **live single-host verify (sync → rotate → `claude -p ping` OK)** → cron → **doc-sync (explicit): `CHANGELOG` + `INDEX.md` + `docs/CONFIGURATION.md`** (the cron + the sync mechanism) → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase D — Monitoring honesty (page on a real break) — ✅ EXECUTED 2026-07-08

**Responsibility:** detect a 401/quota break instead of reporting "fresh" off mtime.

**Files:**
- `scripts/sysadmin/daily-digest.sh` (**modify** `:89-92`) — replace the mtime-only `KEEPALIVE_STATUS` with a **content** check of `/var/log/claude-keepalive.log` (single-run overwrite): if it contains `KEEPALIVE_FAIL` / `401` / matches the usage-limit regex → `KEEPALIVE_STATUS="⚠️ BROKEN (<reason>)"` and mark the digest unhealthy (pages via Apprise); only a real `KEEPALIVE_OK` within the freshness window is "healthy".
- `scripts/sysadmin/proactive-check.sh` (**modify** `:243-254`) — the same mtime-only freshness monitor; add the identical content check so BOTH health surfaces are honest.
- `scripts/sysadmin/test_daily_digest_keepalive.sh` (**create**) — fixture log with `401`/`KEEPALIVE_FAIL` → assert `BROKEN`; `KEEPALIVE_OK` → `healthy`.

**Interfaces — Consumes:** the keepalive content token (Phase B). **Produces:** honest health signal.

**Steps:** test-first (RED: current logic reports fresh on a 401 fixture) → fix `daily-digest.sh:89-92` + `proactive-check.sh:243-254` → GREEN → `bash -n` both → **doc-sync (explicit): `CHANGELOG`** → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase E — Tune `ContainerHighMemory` (stop the 38×/day flap) — ✅ EXECUTED 2026-07-08 (`for: 5m→15m`; per-container limit analysis operator-run)

**Responsibility:** only a *sustained* breach should fire.

**Files:**
- `configs/prometheus/rules/alerts.yml` (**modify** `:32-42`) — current: `expr: 100 * container_memory_usage_bytes{name!=""} / (container_spec_memory_limit_bytes{name!=""} > 0) > 85`, `for: 5m` (the `> 0` guard is in the expr at `:35`). Raise `for:` (e.g. `15m`) and/or the per-container limit; keep the `> 0` guard.
- `scripts/vps_apply_limits.sh` (**inspect / maybe modify**) — if a container's *limit* is simply too low, raise the limit here instead of desensitizing the alert.

**⚠️ Grounded dependency (residual #2):** which container flaps + raise-limit-vs-raise-threshold. **Resolution step:** on vps1, query Prometheus (`ALERTS{alertname="ContainerHighMemory"}` firing frequency per `name` over 7d — resolve the endpoint/auth in-phase) → decide per container.

**Steps:** ground firing history → edit rule/limit → validate `promtool check rules configs/prometheus/rules/alerts.yml` **if promtool present** (confirmed ABSENT on WSL) **ELSE** `python -c "import yaml;yaml.safe_load(open('configs/prometheus/rules/alerts.yml'));print('yaml ok')"` → **doc-sync (explicit): `CHANGELOG` + `docs/infrastructure/vps-status.md`** → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase F — Fleet rollout to LIVE hosts + provisioning + docs convergence + full gate — ✅ EXECUTED 2026-07-08 (provisioning + docs + gate; live rollout = operator runbook below)

**Responsibility:** land the mechanism on the 3 running VPS (not just future ones), bake into provisioning, converge docs.

**Steps:**
1. `scripts/bootstrap/bootstrap-vps.sh` (**modified** — added `sudo -u ozgur mkdir -p /home/ozgur/.claude/manager-accounts` in the step_14 sysadmin-pack install, after the script chmod). The rendered cron already uses `claude-keepalive-rotate.sh` via the Phase-B template edit; the `chmod 755 …/*.sh` glob already picks up the three new shims. `bootstrap-hub.sh` has **no** `.claude`/sysadmin block (nothing to edit); every host also gets `manager-accounts` created by the Phase-C sync's remote `mkdir -p`.
2. **Live-host rollout — OPERATOR RUNBOOK (trigger-not-execute; touches OAuth creds + restarts services on the 3 running VPS).** Run from WSL `/opt/fabrik`:
   ```bash
   # (0) capture the can@ocoron.com snapshot first (claude-manager → switch to it once),
   #     so all THREE accounts sync. Verify locally:
   python3 scripts/sysadmin/claude_rotate.py --list      # expect mob@ / ob@ / can@
   # (1) push scripts to each host's rsync tree (sysadmin + aro-wake twins):
   for h in vps vps2 vps3; do
     ssh ozgur@$h 'mkdir -p /opt/fabrik/scripts/sysadmin /opt/fabrik/scripts/aro-wake'
     scp -p scripts/sysadmin/{claude_rotate.py,claude-keepalive-rotate.sh,keepalive-status.sh,daily-digest.sh,proactive-check.sh,bot.py} ozgur@$h:/opt/fabrik/scripts/sysadmin/
     scp -p scripts/aro-wake/{claude_rotate.py,main.py} ozgur@$h:/opt/fabrik/scripts/aro-wake/
     ssh ozgur@$h 'chmod 755 /opt/fabrik/scripts/sysadmin/*.sh'
   done
   # (2) sync all account snapshots + active creds to the fleet:
   scripts/sysadmin/sync-claude-accounts-to-fleet.sh          # DRY_RUN=1 first to preview
   # (3) re-install the shim cron on each live host (or sudo sed the keepalive line):
   #     render vps-sysadmin-cron from the template (bootstrap step_14 does this) OR:
   for h in vps vps2 vps3; do
     ssh ozgur@$h "sudo sed -i 's#/usr/bin/claude -p \"ping\".*#/opt/fabrik/scripts/sysadmin/claude-keepalive-rotate.sh > /dev/null 2>\&1#' /etc/cron.d/vps-sysadmin"
   done
   # (4) restart services + verify:
   for h in vps vps2 vps3; do
     ssh ozgur@$h 'sudo systemctl restart vps-sysadmin-bot aro-wake; /opt/fabrik/scripts/sysadmin/claude-keepalive-rotate.sh; cat /var/log/claude-keepalive.log'  # expect KEEPALIVE_OK
   done
   # (5) residual #1 live check — force a rotation on ONE host, expect it lands + pings OK:
   ssh ozgur@vps 'python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --next && python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py /usr/bin/claude -p ping'
   ```
3. **`/fabrik-docs-review`** across touched docs: `docs/infrastructure/vps-ai-sysadmin.md`, `docs/infrastructure/vps-status.md`, `docs/CONFIGURATION.md`, `docs/FEATURES.md`, `CHANGELOG.md`.
4. **`/fabrik-review`** across the full changed surface — blocking, loop to no-op.
5. Full gate: `python scripts/final_gate.py --check --json` → `"status":"success"`; `python scripts/enforcement/check_convergence.py` → green. Green is necessary, not sufficient — the real proof is a live forced-rotation succeeding on a VPS (step 2).

---

## File Scope (owned paths)

```
scripts/sysadmin/claude_rotate.py                        (create)
scripts/aro-wake/claude_rotate.py                        (create — byte-identical vendored twin)
scripts/sysadmin/claude-keepalive-rotate.sh              (create)
scripts/sysadmin/sync-claude-accounts-to-fleet.sh        (create)
scripts/sysadmin/test_claude_rotate.py                   (create)
scripts/sysadmin/test_bot_rotation_wire.py               (create)
scripts/sysadmin/test_sync_accounts.py                   (create — pytest DRY_RUN dry-run, gate-covered; N-host via CLAUDE_FLEET_HOSTS)
scripts/sysadmin/test_daily_digest_keepalive.sh          (create)
scripts/sysadmin/bot.py                                  (modify)
scripts/sysadmin/daily-digest.sh                         (modify :89-92)
scripts/sysadmin/proactive-check.sh                      (modify :243-254 — content check, NOT the cron)
scripts/aro-wake/main.py                                 (modify :499/:537)
scripts/bootstrap/templates/sysadmin-cron.template       (modify :32 — cron → shim)
scripts/bootstrap/bootstrap-vps.sh, bootstrap-hub.sh     (modify)
configs/prometheus/rules/alerts.yml                      (modify :32-42)
scripts/vps_apply_limits.sh                              (inspect / maybe modify)
INDEX.md, CHANGELOG.md, docs/FEATURES.md, docs/CONFIGURATION.md, docs/infrastructure/vps-ai-sysadmin.md, docs/infrastructure/vps-status.md  (modify)
```
Disjoint from other in-flight plans (universal-watchdog owns different paths).

## Evidence

- **Signal (grounded live 2026-07-07):** `github.com/cheapestinference/claude-auto-retry` README "Messages Detected (verbatim)" confirms the 4 base strings; `code.claude.com/docs/en/errors` "Usage limits" (HTTP 200, fetched) adds the current `session limit` + `Opus limit` variants and separates quota-reached from auth-failure. No on-disk quota file (grep of `~/.claude` → none).
- **Accounts (read, keys only):** `~/.claude/manager-accounts/{mob,ob}-ocoron-com-s-organization/.credentials.json`, each `600`, `claudeAiOauth.{accessToken,refreshToken,expiresAt,scopes,subscriptionType,rateLimitTier}` + `organizationUuid`; Max 20x vs Pro.
- **Call sites (read):** `bot.py:145` `_run_claude`→`tuple[str,str|None]`, `subprocess.run` `:179` (`cwd=PROJECT_DIR`, `env` with `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `bot.py:175-176`), 401 `:190`, resume-retry `:194-197`; `aro-wake/main.py:499` mirror (`ARO_WAKE_PROJECT_DIR` vs `SYSADMIN_PROJECT_DIR`), subprocess `:537`. **Separate rsync trees + `.venv-aro-wake`** (`bootstrap-vps.sh:997-1125`) → no cross-import.
- **Cron (read):** `scripts/bootstrap/templates/sysadmin-cron.template:32` = the real keepalive line; rendered `bootstrap-vps.sh:985` → `/etc/cron.d/vps-sysadmin` `:1022`; `proactive-check.sh:238` is only a comment.
- **Blind spot (read):** `daily-digest.sh:89-92` mtime-only; `proactive-check.sh:243-254` same.
- **Alert (read):** `alerts.yml:32-42` `> 85` `for:5m`, guard `:35`. `promtool` ABSENT on WSL (`command not found`) → YAML-parse fallback.
- **Outage (captured):** vps1 last `claude_ok=true` ~Jun 29; vps2/3 ~Jun 6; `aro_wake_requests_total{status="failure"} 308`; live `claude -p` `401`→`OK` post-fix.
  ```
  vps1 sysadmin-actions.jsonl: "claude_ok": false ×271 / true ×29 (last 300); "claude exited 1"; cost 0.0
  ```

## Self-audit

- **Grounding:** 3 parallel grounder subagents (A+B, C+D+E, structural+URLs) + my reads. All findings applied; none refuted (all confirmed against real lines). Fixed vs the DRAFT: cwd/env interface, cross-dir vendor, cron-template target + live-host rollout, `docs/OPERATIONS.md`→`docs/CONFIGURATION.md`, `session`/`Opus` regex variants, `expiresAt` misread dropped, `mkdir -p`, atomic+flock swap, backup carve-out, `:45`→`:35`, per-phase CHANGELOG/INDEX, `vps-status.md` in scope, `proactive-check.sh` content-check.
- **Coverage of "What we agreed":** rotation trigger→A; 3 sites + cron→B; standby freshness→C; monitoring honesty→D; alert flap→E; live rollout+provisioning+docs→F. ✓
- **Cross-phase signatures:** `run_claude(argv,timeout,cwd,env)->CompletedProcess` produced in A, consumed identically in B (both callers pass cwd+env); keepalive token `KEEPALIVE_OK`/`KEEPALIVE_FAIL` produced in B, consumed in D. Reconciled.
- **Fixed point reached** — the Pass Ledger's final row (Pass 3) is `edits: 0` with `md5(start) == md5(end)` (`22db642a…`); a later `/fabrik-plan-review` re-ground (pre-execute) corrected two residual consistency-drifts (cron-template `:29`→`:32` in Phase B; this stale DRAFT sentence) and re-confirmed every `path:line` still holds against current `master`. **Status: CONVERGED.**

## Residual unknowns

**Resolved (this chat):** quota signal (grounded incl. session/Opus), rotation mechanism (atomic file swap + flock + backup), 3 call sites, cron source + live-rollout, blind-spot locations, root cause.

**Still open (each with an in-phase resolution step):**
1. **Standby refreshToken validity when swapped in** — no `expiresAt` for the refreshToken exists; the ONLY test is Phase C's live sync→rotate→`claude -p ping`. If it 401s, shorten cadence / escalate.
2. **`ContainerHighMemory` root cause** — Phase E queries Prometheus 7d firing-per-container to choose raise-limit vs raise-threshold.
3. **Live-host `/etc/cron.d/vps-sysadmin` update** — host-only state; Phase F step 2 re-renders/installs it explicitly (not just new-host provisioning).
4. **Concurrency** — resolved by the Phase-A `flock` on `~/.claude/.claude-rotate.lock` (bot + aro-wake can't race the active file).

---

**Next:** `/fabrik-plan-review` continues to a fixed point (this file). Then `/fabrik-execute-plan <file>` is **user-triggered** (mutates fleet scripts + touches OAuth creds).
