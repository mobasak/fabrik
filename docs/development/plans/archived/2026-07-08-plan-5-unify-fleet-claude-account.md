# Unify all fleet Claude callers onto one account + guarantee auto-rotation on all 3 VPS

**Status:** EXECUTED 2026-07-08 — Phases A+B+C shipped; final gate `success` (34/0); whole-plan `/fabrik-review` converged (caught + fixed a stdin-lost-on-retry data-loss bug + a proactive-check fail-open + a root-cwd crash). Code + operator rollout runbook complete; the live 3-VPS rollout is operator-run (trigger-not-execute). Commits: A `2d51c448`, B `e99621f8`, C `d683204e`, review-fixes `b875f066`/`7d914e70`.
**Author:** Claude Opus 4.8 (hub) · from chat 2026-07-08
**Owner:** hub AI — sysadmin/watchdog stream. Extends the EXECUTED `docs/development/plans/archived/2026-07-07-plan-1-sysadmin-claude-rotation.md` (which wired only bot.py + aro-wake + keepalive). Not yet executed (`/fabrik-execute-plan` pending, user-triggered).

**Pass Ledger (`/fabrik-plan-review` — fixed point reached):**

| Pass | axes re-grounded | edits | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | claims (4 call sites `:420/:94/:25/:33`, `claude_rotate.py::main:342` passthrough, rsync mechanism) · structural pillars | 4 (rsync grounded dir-level → residual #1 resolved + File-Scope + Phase-C step 1; residual renumber) | `2d44fcfb…` → (edited) |
| 2 | all pillars: `/fabrik-review`×3, no banned `fabrik` gate, final+convergence gate, Behavior-Contract×3, no deferred question, non-GUI | 0 (grounding) | (verify scan, no content change) |
| 3 | md5-anchored no-op | **0** | see report ✓ → **CONVERGED** |

**Goal:** Make **every** Claude Code caller on the fleet use **one** credential mechanism (the operator account `/home/ozgur/.claude`) and go through **auto-rotation**, on **all 3 VPS** — closing the gap that four sysadmin cron scripts run as `root` (whose `/root/.claude` has no credentials at all) and never rotate.

---

## What we already agreed (Phase 0 distillation)

- **The problem (live-verified this chat on vps/vps2/vps3):** the `claude` *binary* is system-wide, but the *account* is per-`$HOME`. The cron runs `proactive-check.sh`, `morning-report.sh`, `weekly-security.sh`, `monthly-backup-verify.sh` as **root**, and **`/root/.claude/.credentials.json` is ABSENT on all 3 hosts** → their `claude -p` is not just un-rotated, it's **broken (no auth)**. Only ozgur's path (bot, aro-wake, keepalive) has creds — and ozgur is on **mob@ (`767e428b…`)** with **zero `manager-accounts` snapshots on any VPS**, so even ozgur's rotation currently has nothing to rotate to.
- **Chosen approach (user directive: "all claude code systems in vps should use same account credential mechanism and all 3 servers should have account auto rotation. Be sure."):** a single wrapper `scripts/sysadmin/claude-run.sh` that routes **every** sysadmin `claude` invocation through `claude_rotate.py` **as the operator** — direct when already `ozgur`, `sudo -u ozgur -H python3 claude_rotate.py claude "$@"` when the caller is root (root→ozgur sudo needs no password). Wire the 4 root scripts' `claude -p …` calls to it. Then roll out to all 3 VPS + run the fleet-sync so each host has ≥2 snapshots to rotate between.
- **Rejected:** (a) flipping the 4 scripts' cron user root→ozgur — riskier (they run 22/10/2/2 `sudo` calls + implicit-root commands; a surgical claude-only reroute is safer). (b) symlinking `/root/.claude → /home/ozgur/.claude` — a root-run `claude` token refresh would chown the files to root and break ozgur's rotation writes.
- **Keep as-is:** the 3 already-wired callers (`bot.py:189`, `aro-wake/main.py:546`, `claude-keepalive-rotate.sh`).
- **Out of scope (tracked in memory):** capturing the **can@** snapshot (operator, pending — `[[project_can_account_capture_pending]]`) and the `_active_account()` `.claude.json` org fallback (`[[project_rotation_coverage_gap]]`). This plan works with the 2 captured accounts (mob@ + ob@); can@ joins automatically by glob once captured.

**Branch: RICH.** Goal + approach + the live-verified findings all pinned in this chat.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/90-bootstrap-scripts.md` (ACTIVE) | SSH-user-transition + quote-escaping + sudo discipline for fleet ops; nested `$()`/quote traps (AFCL) | pack + `AFCL.md:12-13` |
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | creds `chmod 600`, never logged/printed/committed; the wrapper passes creds by file only, never parses token bytes | `35-security-auth:175-186` |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | systemd/cron/rsync fleet-ops; trigger-not-execute deploy | ACTIVE |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract — test each user-observable behavior, risk-ordered | ACTIVE |
| `fabrik-lib` — **no applicable module** | no fabrik-lib module does "run-as-operator claude wrapper"; `claude_rotate.py` (built in the prior plan, project-local) IS the rotation primitive this wraps. Fresh 15-line shell wrapper. | `/opt/fabrik-lib/README.md` (checked); prior plan's `scripts/sysadmin/claude_rotate.py` |
| `claude_rotate.py` CLI (prior plan) | `python3 claude_rotate.py <claude-bin> -p …` runs claude through usage-limit rotation; also `--list/--switch/--next` | `scripts/sysadmin/claude_rotate.py::main` (read) |
| `sync-claude-accounts-to-fleet.sh` (prior plan) | pushes all `manager-accounts/*` snapshots + active creds to `CLAUDE_FLEET_HOSTS`; prerequisite so rotation has ≥2 targets | `scripts/sysadmin/sync-claude-accounts-to-fleet.sh` (read) |
| `specs/services/*.yaml` `shape.*` | **no shape change** — host scripts/cron, not a deployed compose service | n/a |
| `AGENTS.md` — sysadmin topology | `vps-sysadmin-bot.service` + `aro-wake.service` run as `User=ozgur`; scripts rsynced to `/opt/fabrik/scripts/sysadmin` on each VPS | `vps-sysadmin-bot.service.template:10`; `bootstrap-vps.sh` step_14 |

**fabrik-lib consult (mandatory):** checked `/opt/fabrik-lib/README.md` — no run-as-user/claude-invocation module; the rotation primitive (`claude_rotate.py`) already exists project-local. The wrapper is a trivial shell adapter → **build fresh, project-local** (too small + fabrik-specific to be a 🆕 candidate).

---

## Global Constraints (every phase inherits, verbatim)

- **Repo boundary:** edits in `/opt/fabrik` only. The live rollout writes to the 3 VPS over SSH (operator's own fleet, authorized this chat) — never another repo.
- **Credential handling (`35-security-auth:175-186`):** `~/.claude/*.credentials.json` are `chmod 600`, never logged/printed/committed. The wrapper swaps NO files itself — it delegates to `claude_rotate.py` (which does the atomic swap) and only ever passes the `claude` binary + args.
- **One operator account:** the single credential home is `/home/ozgur/.claude`; `CLAUDE_OPERATOR_USER` (default `ozgur`) names the operator. Every claude call resolves to that home.
- **sudo:** `sudo -u ozgur -H` from a root cron needs no password (root→any-user is unconditional; bootstrap also grants ozgur `NOPASSWD`, `bootstrap-vps.sh:255-297`). `-H` sets `HOME=/home/ozgur` so `claude` reads the right creds.
- **Deploy = trigger-not-execute:** the plan produces the code + the exact runbook; the live 3-VPS rollout (scp + sync + restart) is **operator-run**. No `fabrik …` in gates (hub-side only).
- **Shared-master:** explicit-path commits, provenance trailers, CHANGELOG appended atop `[Unreleased]`.

---

## Phase A — The unified wrapper `scripts/sysadmin/claude-run.sh` + test — ✅ EXECUTED 2026-07-08

**Responsibility:** one shell entrypoint that runs `claude` through `claude_rotate.py` **as the operator account**, regardless of the calling user — so root cron scripts and ozgur services share one rotating account.

**Files:**
- `scripts/sysadmin/claude-run.sh` (**create**) — resolves `claude_rotate.py` co-located; `OPERATOR="${CLAUDE_OPERATOR_USER:-ozgur}"`; `CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || echo /usr/bin/claude)}"`; if `id -un == $OPERATOR` → `exec python3 "$DIR/claude_rotate.py" "$CLAUDE_BIN" "$@"`, else `exec sudo -u "$OPERATOR" -H python3 "$DIR/claude_rotate.py" "$CLAUDE_BIN" "$@"`. Header `# AFTER-EDIT: scripts/sysadmin/proactive-check.sh, scripts/sysadmin/morning-report.sh, scripts/sysadmin/weekly-security.sh, scripts/sysadmin/monthly-backup-verify.sh`.
- `scripts/sysadmin/test_claude_run.py` (**create**).

**Interfaces — Produces:** `claude-run.sh [claude-args…]` — a drop-in for `claude` that rotates + runs as `$OPERATOR`. **Consumes:** `claude_rotate.py::main` (prior plan).

**Behavior Contract (risk-ordered):**
1. *(highest-risk, TDD-first)* **Args pass through verbatim** incl. a multi-line `--system-prompt "$SYS_PROMPT"` → the underlying `claude` receives them unchanged (the sysadmin scripts pass a large multi-line system prompt).
2. **Routes through rotation** — the wrapper invokes `claude_rotate.py`, not bare `claude` (so a usage-limit rotates).
3. **Operator-direct path** — when the caller *is* the operator, it runs directly (no sudo) and uses the operator's `~/.claude`.
4. **Root path routes via `sudo -u ozgur -H`** — asserted structurally (the sudo branch exists) + documented (only reachable as root on the VPS; the E2E arg/rotation behavior is proven via the direct path with a fake claude).

**Steps (highest-risk test FIRST):**
1. **Write failing test** `test_claude_run.py`: with `CLAUDE_OPERATOR_USER=$(current user)`, `CLAUDE_BIN=<fake claude that echoes its argv + a chosen output/rc>`, `HOME=<tmp with a fake ~/.claude, <2 accounts → no rotation>`: run `claude-run.sh -p --model opus "PROMPT" --system-prompt $'multi\nline'` → assert the fake claude received exactly `-p --model opus PROMPT --system-prompt multi\nline` (args verbatim) and the wrapper exit == the fake's rc. Assert the source contains the `sudo -u "$OPERATOR" -H` branch for the non-operator case. Run → **RED** (wrapper absent).
2. Implement `claude-run.sh` to green. Gate: `bash -n scripts/sysadmin/claude-run.sh` → ok; `python -m pytest scripts/sysadmin/test_claude_run.py -q` → pass; `python scripts/enforcement/check_script_headers.py scripts/sysadmin/claude-run.sh 2>&1 | grep -c AFTER-EDIT` → header present.
3. **Doc-sync (explicit):** `CHANGELOG.md`; `docs/CONFIGURATION.md` (the `claude-run.sh` unified entrypoint + `CLAUDE_OPERATOR_USER`).
4. **Closing:** phase gate → `python scripts/enforcement/check_doc_sync.py` → **`/fabrik-review` on the Phase-A surface via independent finder subagents, loop to a no-op pass** → commit (explicit paths, provenance trailers).

---

## Phase B — Wire the 4 root sysadmin scripts to the wrapper + test — ✅ EXECUTED 2026-07-08

**Responsibility:** every root-run sysadmin claude call goes through `claude-run.sh` (→ operator account + rotation) instead of the broken bare `claude`.

**Files (each **modify** the one `RESULT=$(claude -p …)` invocation):**
- `scripts/sysadmin/proactive-check.sh` (`:420`) — `claude -p --model opus … --system-prompt "$SYS_PROMPT"` → `"$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model opus … --system-prompt "$SYS_PROMPT"`.
- `scripts/sysadmin/morning-report.sh` (`:94`) — same swap.
- `scripts/sysadmin/weekly-security.sh` (`:25`) — same swap.
- `scripts/sysadmin/monthly-backup-verify.sh` (`:33`) — same swap.
- `scripts/sysadmin/test_claude_run.py` (**extend** — a wiring assertion per script).

**Interfaces — Consumes:** `claude-run.sh` (Phase A). **Produces:** all 4 root scripts route claude through the operator account.

**Behavior Contract:**
1. Each of the 4 scripts invokes claude via `claude-run.sh` (not bare `claude -p`) — asserted per script.
2. The surrounding capture + failure-handling logic (`RESULT=$(…)`, the `⚠️ … Claude failed` fallback in 3 of them) is unchanged — asserted via `bash -n` + a grep that the fallback line still exists.

**Steps:** test-first (RED: scripts still call bare `claude -p`) → swap the 4 invocations → GREEN → `bash -n` all 4 → **doc-sync (explicit): `CHANGELOG` + `docs/infrastructure/vps-ai-sysadmin.md`** (all sysadmin claude now via the operator account) → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase C — Provisioning check + rollout runbook + docs convergence + full gate — ✅ EXECUTED 2026-07-08

**Responsibility:** guarantee the wrapper + `claude_rotate.py` reach all 3 VPS, each host has ≥2 snapshots to rotate between, and the docs tell the true story. The live rollout is operator-run (trigger-not-execute).

**Steps:**
1. **Provisioning inspection (grounded: no bootstrap edit needed):** step_14's rsync is **dir-level** — `bootstrap-vps.sh:999-1001` runs `rsync -a --exclude __pycache__ --exclude '*.pyc' "${SYSADMIN_SOURCE:-/opt/fabrik/scripts/sysadmin/}" "${tmpdir}/sysadmin/"` → every `.sh`/`.py` in the dir ships, so `claude-run.sh` is included automatically. Gate: `grep -nE "rsync -a.*sysadmin" scripts/bootstrap/bootstrap-vps.sh` → shows the dir-level `rsync -a … /scripts/sysadmin/ … /sysadmin/` at `:999-1001` (confirms new files ship; no allowlist to extend).
2. **Rollout runbook (documented, operator-run — the 3 live VPS):** in `docs/infrastructure/vps-ai-sysadmin.md`, the exact commands: (a) `scp` updated `scripts/sysadmin/*` + `scripts/aro-wake/*` to each host; (b) run **`sync-claude-accounts-to-fleet.sh`** from WSL so each VPS gets mob@ + ob@ snapshots (rotation targets — currently zero); (c) re-render/install `/etc/cron.d/vps-sysadmin` from the template (picks up the prior plan's keepalive→shim); (d) `systemctl restart vps-sysadmin-bot aro-wake`; (e) verify: on one VPS, `claude-run.sh -p ping` returns OK AND (as root) `sudo /opt/fabrik/scripts/sysadmin/proactive-check.sh`-path claude no longer 401s; force a rotation and confirm it lands on the other account.
3. **`/fabrik-docs-review`** across touched docs: `docs/CONFIGURATION.md`, `docs/infrastructure/vps-ai-sysadmin.md`, `CHANGELOG.md`.
4. **`/fabrik-review`** across the full changed surface — blocking, loop to no-op.
5. **Full gate:** `python scripts/final_gate.py --check --json` → `"status":"success"`; `python scripts/enforcement/check_convergence.py` → green. Green is necessary, not sufficient — the real proof is step 2's live verify on a VPS (operator-run).

---

## File Scope (owned paths)

```
scripts/sysadmin/claude-run.sh                    (create)
scripts/sysadmin/test_claude_run.py               (create)
scripts/sysadmin/proactive-check.sh               (modify :420 — claude call → wrapper)
scripts/sysadmin/morning-report.sh                (modify :94)
scripts/sysadmin/weekly-security.sh               (modify :25)
scripts/sysadmin/monthly-backup-verify.sh         (modify :33)
scripts/bootstrap/bootstrap-vps.sh                (inspect only — rsync is dir-level (:999-1001), ships new files automatically; no edit expected)
scripts/sysadmin/claude_rotate.py, scripts/aro-wake/claude_rotate.py, scripts/sysadmin/test_claude_rotate.py  (whole-plan-review fix — added buffer_stdin so a rotation retry re-supplies the piped stdin that the wired stdin-based scripts feed; prior-plan file, but plan-5's wiring exposed the bug)
docs/CONFIGURATION.md, docs/infrastructure/vps-ai-sysadmin.md, CHANGELOG.md, INDEX.md  (modify)
```
Disjoint from the sibling `2026-07-08-plan-*` (flywheel/behavior-contract/pipeline) — those own `scripts/enforcement/**`, `scripts/kilo-benchmarks/**`, `libs/**`, not `scripts/sysadmin/**`. **Serialization note:** `proactive-check.sh` was last touched by the archived rotation plan (Phase D) — now committed, no in-flight conflict.

## Evidence

- **Broken root path (live, all 3 VPS):** `sudo -n test -f /root/.claude/.credentials.json` → `absent`; `/root/.claude` is a root-owned dir, not a symlink. ozgur active org `767e428b…` (mob@); `ls ~/.claude/manager-accounts` → empty on every host.
  ```
  [/root/.claude] ls: drwxr-xr-x 3 root root … /root/.claude ; root creds file: absent-or-denied
  [live cron] root proactive-check.sh / morning-report.sh / weekly-security.sh / monthly-backup-verify.sh ; ozgur keepalive
  ```
- **The 4 claude call sites (read):** `proactive-check.sh:420`, `morning-report.sh:94`, `weekly-security.sh:25`, `monthly-backup-verify.sh:33` — all `RESULT=$(claude -p --model opus … --system-prompt "$SYS_PROMPT")`.
- **The rotation primitive (read):** `claude_rotate.py::main` accepts `<claude-bin> args…` passthrough → runs via `run_claude` (usage-limit rotate). `sync-claude-accounts-to-fleet.sh` pushes snapshots to `CLAUDE_FLEET_HOSTS`.
- **sudo (read):** `bootstrap-vps.sh:255-297` grants ozgur NOPASSWD; root→ozgur sudo is unconditional.

## Self-audit

- **Grounding:** solo (small, 6-file surface, all internal). Read: the 4 scripts' claude lines, `claude_rotate.py::main`, `sync-claude-accounts-to-fleet.sh`, bootstrap sudoers + rsync, live VPS probe (all 3). No external deps to research (all internal shell/creds).
- **Coverage of "What we already agreed":** one-account wrapper→A; wire 4 root scripts→B; ship + sync-so-rotation-has-targets + rollout runbook→C; keep 3 wired callers→untouched; can@/`_active_account` fallback→explicit out-of-scope. ✓
- **Cross-phase signatures:** `claude-run.sh [args]` produced in A, consumed identically in B (4 call sites) + the runbook in C. Reconciled.
- **Fixed point reached** — `/fabrik-plan-review` re-grounded the 4 call sites (`:420/:94/:25/:33` — exact), `claude_rotate.py::main` passthrough (`:342`), and the rsync (dir-level `:999-1001` → resolved residual #1); Pass 2 verified all structural pillars (`/fabrik-review`×3, runnable non-`fabrik` gates, Behavior-Contract×3, zero deferred questions, non-GUI). Pass 3 no-op → **Status: CONVERGED.**

## Residual unknowns

**Resolved (this chat, live-verified):** root-vs-ozgur split, /root/.claude no creds (all 3), fleet on mob@, zero snapshots, sudo root→ozgur passwordless, the 4 call sites + the rotation primitive API.

**Resolved additionally (this review):** step_14 rsync is **dir-level** (`bootstrap-vps.sh:999-1001`, `rsync -a … /opt/fabrik/scripts/sysadmin/ → …/sysadmin/`, excludes only `__pycache__`/`*.pyc`) → `claude-run.sh` ships automatically; no bootstrap edit.

**Still open (each with a resolution step — none block execution / none is a deferred question):**
1. **Live rollout is operator-run** (trigger-not-execute) — Phase C step 2 documents the exact commands; the plan does not mutate the 3 VPS (not a stall — the executor writes the runbook, the operator runs it).
2. **Rotation needs ≥2 valid snapshots per host** — the fleet-sync pushes mob@ + ob@ (both captured on WSL); **can@ still pending** (`[[project_can_account_capture_pending]]`) but 2 accounts already give real rotation.
3. **Standby-token validity when swapped in** — inherited from the prior plan's residual; Phase C step 2's live verify (rotate → `claude-run.sh -p ping`) is the test.

---

**Next:** `/fabrik-plan-review` converges this to a fixed point. Then `/fabrik-execute-plan <file>` is **user-triggered** (mutates sysadmin scripts; live rollout operator-run).
