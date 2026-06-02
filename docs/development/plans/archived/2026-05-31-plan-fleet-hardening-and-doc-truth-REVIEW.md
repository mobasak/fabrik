# Veteran Review — Fleet Hardening + Doc Truth Pass (v3.2)

**Reviewed:** 2026-05-31 evening
**Reviewer lens:** veteran sysadmin, signing off as if for an SRE team
**Plan under review:** [`2026-05-31-plan-fleet-hardening-and-doc-truth.md`](2026-05-31-plan-fleet-hardening-and-doc-truth.md) (v3.2, 1073 lines, 9 workstreams)
**Verdict:** **REJECT for full-batch execution. APPROVE for staged execution, W9 first only.**

## 1. The one-line verdict

The plan is well-structured but operationally too big to ship as one batch on production infrastructure with a single-operator team. Ship it as 4 stages, gated by results, not by checklist completion.

## 2. What this review is NOT

- Not another iteration of the plan
- Not a list of polish items
- Not a list of "v4 candidate" changes
- Not advocacy for any specific tool or path

## 3. What this review IS

A signed verdict on whether the plan as written can be safely executed, with concrete blockers that prevent shipping and a recommended staging path.

---

## 4. BLOCKERS — must fix before shipping the relevant workstream

These will cause execution to fail or produce false-positive results. They are concrete, not stylistic.

### B1 — W2 plan-creation JSON schema is undocumented

The plan says "edit `config.json` directly" but does not specify the JSON object structure for a plan entry. Backrest 1.12.1's schema is **not** what the README shows (the README usually documents the latest version's UI fields, which don't 1:1 map to the on-disk JSON).

**Required before W2:** capture the live schema from an existing Backrest instance (any tenant has one with plans) OR read the proto definitions from the Backrest repo (`internal/api/v1alpha1/*.proto`) and translate to JSON. Document the exact field set in the plan.

**Risk if shipped as-is:** first plan-creation edit produces malformed JSON, Backrest fails to restart, plan execution stalls on Day 2.

### B2 — W2 hook-event name not verified for this Backrest version

Plan assumes `CONDITION_SNAPSHOT_SUCCESS` exists. Pre-flight noted Backrest 1.12.1 but did not run `grep -r CONDITION /opt/backrest` or open the API schema to confirm.

**Required before W2:** `docker exec backrest /backrest --help 2>&1 | grep -iE "condition|hook"` OR fetch the gRPC reflection schema. If the hook name differs, update the plan.

**Risk if shipped as-is:** failure-hook test does nothing, you think it failed silently, you spend 20 minutes debugging an apprise/Telegram path that's not actually being called.

### B3 — W3 `_persist_state` function name asserted but not verified

```bash
grep -n "_persist_state\|persist_state" src/fabrik/orchestrator/__init__.py
```

was never run. The plan patches a function by that name. If the actual name is `_save_state` or `_write_state_file`, the patch instructions are wrong.

**Required before W3:** grep the codebase. Use the actual function name in the plan.

**Risk if shipped as-is:** code change touches the wrong function, tests pass for wrong reasons, target_vps not actually written to state file.

### B4 — W4 template field validation never confirmed

Plan chose `template: python-api` on the assumption that `templates/python-api/` exists. Was never `ls templates/`'d.

**Required before W4:** `ls /opt/fabrik/templates/` and pick a value that exists on disk. If `python-api` does exist, fine. If only `saas-skeleton` or `node-api` exists, use one of those.

**Risk if shipped as-is:** `fabrik apply` fails at validation step with `template not found`. Recovery is trivial but it's a wasted cycle that erodes trust.

### B5 — W8 induced-anomaly mechanism is non-deterministic

```bash
ssh vps2 'timeout 60 yes > /dev/null &'
```

The `&` is interpreted by the **remote** shell. SSH exits when the foreground command exits. The backgrounded `yes` becomes a zombie tied to a dead SSH session — Linux's behavior here depends on `nohup` state, controlling-tty state, and kernel version. May survive 60s. May die in 1s when SSH cleans up.

**Required before W8:** use `nohup ... </dev/null >/dev/null 2>&1 &` form, or run via `systemd-run --quiet`, or use `stress-ng --cpu 1 --timeout 60` if installed. Choose one and write it down.

**Risk if shipped as-is:** test "passes" because no anomaly was ever induced. The bot's safety behavior is not actually validated. False confidence.

### B6 — W9 cron commits noise on every tick

```bash
cp "$ENV_PATH" "$REPO/env/fabrik-env-${TS}"
```

This **always** writes a new file (timestamped name). Then:

```bash
if git diff --cached --quiet; then exit 0; fi
```

`git diff --cached` will see the new file every run → always commits. The "no changes since last backup" branch never fires.

**Required before W9:** check if `env/latest` content actually changed. Only write the timestamped copy when it did.

```bash
if ! cmp -s "$ENV_PATH" "$REPO/env/latest"; then
  cp "$ENV_PATH" "$REPO/env/latest"
  cp "$ENV_PATH" "$REPO/env/fabrik-env-${TS}"
fi
```

**Risk if shipped as-is:** 365 commits/year, mostly noise. After a year the GitHub repo has 365 commits and you can't tell when the env actually changed.

### B7 — W10 cooldown files in tmpfs

`/var/run/sysadmin/` is `/run/sysadmin/` on Ubuntu 24.04, which is **tmpfs**. Wiped on reboot.

**Required before W10:** use `/var/lib/sysadmin/cooldowns/` (persistent) or `/opt/fabrik/state/cooldowns/`.

**Risk if shipped as-is:** every reboot resets cooldowns. If the watcher decides to restart Traefik on boot due to a transient anomaly, the cooldown that's supposed to stop a second attempt has already been wiped.

### B8 — W10 `action_restart_wg_hub` can disconnect the operator

Plan describes this action but doesn't gate it behind "is the operator currently SSH'd in over mesh." If the bot decides to restart `wg-quick@wg0` while you're SSH'd in via `ssh vps` (which on a single-NIC VPS uses the public IP, but if it ever moved to mesh: boom), you lose your session mid-debug.

**Required before W10:** before `systemctl restart wg-quick@wg0`, verify `ss -tnp | grep :22.*ESTAB` is empty (no active SSH sessions) OR add an explicit `SYSADMIN_AUTONOMOUS_WG_RESTART=false` default that requires opt-in.

**Risk if shipped as-is:** rare but high-impact. Bot kills the mesh while you're using it.

## 5. NON-BLOCKERS — fix after first stage ships, not before

These won't cause failures but are concerns a veteran would file as follow-ups.

| # | Concern | Fix later |
| :--- | :--- | :--- |
| N1 | W1 default-deny before SSH rule briefly blocks SSH (window of seconds) | Document the order rigidly; the current order is correct |
| N2 | W5 27 sequential `nc` probes could trigger `recidive` jail (not sshd jail) | Pace them 5s apart or run from a non-allowlisted IP |
| N3 | W6 probe script makes 51 sequential SSH calls (80s runtime) | Batch into 3 SSH calls (one per host), parse on stdout |
| N4 | No plan-execution telemetry / checkpoint mechanism | Add `state/plan-execution.log` to record where you stopped |
| N5 | Rollback paths are listed but never tested | Test one rollback before going live |
| N6 | W4 nginx canary serves `/` not `/health` | Use a real `/health` endpoint when this is a production check |
| N7 | W10 GitHub-token sourcing for DR-store watcher undocumented | Add a `GH_DR_STORE_RO_TOKEN` env var with explicit scope |

## 6. STRUCTURAL ISSUE — the real blocker

The 8 blockers above are fixable inline in 30 minutes. But there is a deeper issue: **the plan is too large to ship in a single batch on a single-operator production fleet**.

A 10.5-hour active execution across 9 workstreams with 50 checkboxes is a project, not an ops change. Project-sized changes need either: (a) a team of 2+ engineers with one driving and one reviewing live, or (b) staged execution with go/no-go gates between stages.

This plan has neither. Single operator + AI driver + no gates = the failure mode is silent partial completion. Step 3 of W2 fails, you don't notice, you proceed to W3, and 90 minutes later you discover backups have been silently broken since Day 2.

## 7. RECOMMENDED EXECUTION SHAPE

Replace the 3-day batch with 4 stages:

| Stage | Contents | Effort | Decision after |
| :--- | :--- | :--- | :--- |
| **Stage 1** | W9 only (DR env mirror) + B6 fix inline | 50 min | "Does W9 ship clean? If yes → Stage 2. If no → root-cause before anything else." |
| **Stage 2** | W1 + W5 + W6 (safe hardening pass) + N3 batch-probe fix | 3.5 h | "Are the spoke firewalls live and the probe-audit script useful? Decision: do W2 alone next, or pause and observe?" |
| **Stage 3** | W2 only (Backrest reactivation), with B1+B2 fixed inline first | 90 min | "Are backups actually running and alerting? 7-day soak before deciding on Stage 4." |
| **Stage 4** | W3 + W4 + W8 + W10 (M5 + spoke deploy + watchers) | 5 h | Decide ticket-by-ticket. None is urgent. |

The signal: after Stage 1, you know whether the AI-driven execution model works for this fleet at all. That signal is worth 50 minutes of investment before any of the higher-risk workstreams.

## 8. WHY PRIOR REVIEWS DIDN'T CATCH B1–B8

Honest accounting: I wrote and reviewed v1 → v2 → v3 → v3.2 in a single afternoon. Each pass added rigor inside individual workstreams (better commands, more acceptance criteria, more lessons) but never read the plan as a single ops artifact would be read by a fresh reviewer. The pre-flight probe pass found 6 things — but it was scoped to *probe what the plan claims is the current state*, not to *probe what the plan asserts it can do*. B1, B2, B3, B4 are all in the latter category.

A veteran would have run a single grep before approving:

```bash
grep -nE "_persist_state|template: python-api|CONDITION_SNAPSHOT_SUCCESS" \
  docs/development/plans/2026-05-31-plan-fleet-hardening-and-doc-truth.md
# For each match, verify the asserted thing exists. None of these
# were verified in the plan or in pre-flight.
```

That single grep would have caught half the blockers. It wasn't run because each review pass was trying to improve the plan, not validate it.

## 9. WHAT I'D SIGN OFF ON RIGHT NOW

I would sign off on this exact change:

> Execute Stage 1 only: W9 (DR env mirror) with B6 fix inline. Estimated 50 minutes. Report results — including any surprises — before proposing Stage 2.

I would NOT sign off on any larger batch without (a) blockers B1–B8 fixed in writing and (b) explicit operator approval of the staged shape in §7.

## 10. Signed

Reviewer: Claude (acting in the veteran-sysadmin lens)
Date: 2026-05-31 evening
Plan version reviewed: v3.2 (1073 lines, 9 active workstreams)
Verdict: APPROVE Stage 1 only. REJECT full-batch execution.
Next action: operator decision on staged shape (§7).
