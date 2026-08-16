# Liveness layer — proving the machinery is actually RUNNING

**Date:** 2026-08-16
**Status:** ✅ CURRENT
**Code:** `scripts/sysadmin/liveness_audit.py` · registry `.fabrik/liveness-registry.json` · tests `tests/test_liveness_audit.py`
**Consumer:** `scripts/sysadmin/kaizen_metrics.py` (the `Missed crons` column + the hand-off mail's mechanism-health context)

---

## Why this exists

We verify correctness at **write-time** and never verify liveness at **run-time**. Every one of these
passed code review and had tests. None had proof it was running:

| Surface | Declared | Reality |
|---|---|---|
| Weekly kaizen pass | "binding — weekly" in two role charters | ran **0 times in 4 days**; no trigger existed |
| 6 Tier-3 gate checks | registered in `final_gate.py`, reported PASS | asserted **nothing** — no `__main__`, exit 0, empty output |
| Claude-config DR backup | a nightly cron line | had **never** run from cron: its `>> /var/log/…` target was uncreatable by this user, so the shell aborted before the script. Every backup on record was hand-run |
| Alerting | quota / keepalive / CI / watchdog alerts | dead fleet-wide; every alert reached nobody |
| fabrik-mail digest | documented "so nothing rots silently" | the cron did not exist |

Activating just two of those six checks immediately found 5 fleet repos shipping `platform: linux/arm64`
to an x86_64 VPS and 11 undocumented env vars in another. **A declaration is not a mechanism.**

---

## The three states, and why the third one exists

⚠️ **This is the load-bearing rule of the whole layer. Do not reduce it to two states.**

On 2026-08-16, three of the orchestrator's OWN probes lied, and each lie reached the operator as fact:

1. **`grep -c "arg=sweep" ~/.claude/sound-debug.log`** printed nothing, rc=1.
   Conclusion drawn: *"the reboot sweep has NEVER run."*
   **Truth:** the file holds one invalid UTF-8 byte (offset 1313, a truncated `\xe2\x80`). GNU grep
   classified the file BINARY and silently suppressed every match. `grep -a` shows **21** events,
   including that morning's boot. Measured again minutes later, after the Stop hook appended more lines,
   plain `grep` answered 21 — **the suppression is intermittent**, which is worse than a stable bug.
2. **`ls specs/services/ | grep apprise`** → nothing.
   Conclusion drawn: *"Apprise was never a fabrik-managed service."*
   **Truth:** the spec is at `specs/infrastructure/apprise.yaml`. One directory searched, generalised to
   "does not exist".
3. **`ssh vps docker ps`** → EMPTY output.
   Conclusion drawn: *"no apprise container, not even stopped."*
   **Truth:** the ssh user is not in the `docker` group. Every docker call failed with permission denied
   and printed **nothing to stdout**. With `sudo`: 31 containers running, apprise among them, healthy,
   HTTP 200 in-network.

In all three, **absence of evidence arrived as evidence of absence**. So:

> **Every probe validates its own INSTRUMENT against a positive control BEFORE it is allowed to report an
> absence, and the verdict space has three states — never two.**

| Verdict | Means | May be acted on as |
|---|---|---|
| **LIVE** | the instrument was proven, and it found evidence inside budget | healthy |
| **DEAD** | the instrument was proven, and the evidence is genuinely absent or overdue | a real defect |
| **UNKNOWN** | the instrument could **not** be proven; the fault is named | a gap in the *monitoring*, never in the monitored thing |

`finding()` in `liveness_audit.py` is the **only** constructor for a verdict, and any instrument fault
collapses the verdict to UNKNOWN — in **both** directions, because a broken instrument cannot prove
presence either. Neuter that one function and 6 tests go red, headline first
(`test_a_probe_whose_instrument_fails_reports_unknown_never_dead`).

**Corollaries, each traceable to a failure above:**

- Evidence is read as **bytes**, decoded `errors="replace"`. The module **never** shells out to `grep`
  for evidence (failure 1).
- A missing file whose parent directory is absent or unreadable is UNKNOWN, not DEAD (failure 2 in
  miniature — it may simply not be where we looked).
- A `/tmp` evidence path is declared `volatile` in the registry; its absence is UNKNOWN, because `/tmp`
  is cleared on boot and silence there proves nothing.
- A systemd unit that is `not-found` at the SYSTEM level is re-queried with `systemctl --user` before any
  absence is reported; an unreachable user bus is UNKNOWN (failure 3's shape exactly —
  `ai.traycer.host.service` is `not-found` system-wide and `enabled` under `--user`).
- Remote docker probes use `sudo docker`, and a permission failure is UNKNOWN, never absence (failure 3).

---

## The three proofs

### PROOF 1 — HEARTBEAT ("did it fire?")

`.fabrik/liveness-registry.json` declares each scheduled surface: `id`, `kind` (`cron`/`hook`/`service`/
`port`), how to detect its evidence, and its expected max age. The audit compares evidence to expectation.

The registry lives in `.fabrik/` because that is already the repo's **tracked** machine-state directory
(`lint-baseline.json`, `plan-locks/*.json`), so it is versioned and reviewable in a diff rather than a
box-local untracked file — which would itself be an unmonitored surface. JSON keeps the audit stdlib-only.

Evidence channels: `log` (mtime age) · `log_marker` (age of the last dated line carrying a marker —
this is the reboot-sweep probe, and the direct answer to failure 1) · `port` · `unit` · `hook` · `none`.

A `cron` surface is DEAD the moment its **schedule** is gone, whatever a stale log says — that is the
DR-backup class, where a fresh log was a hand-run. A surface with `"evidence": {"type": "none"}` is
UNKNOWN: scheduled but unobservable is unfalsifiable, which is not the same as healthy.

**A registry that misses surfaces is its own blind spot**, so the audit also diffs the box against the
registry and reports cron lines and hook commands present on the box but absent from it
(*unregistered = unmonitored*). `ownership.cron_owned_substrings` draws the boundary: everything else is
another repo's business, counted but not listed.

### PROOF 2 — VACUITY CANARY ("can it fail?")

Every check `final_gate.py` registers (parsed from its source — 39 today: 31 blocking, 8 declared
`warn_only=True`) is run against a **deliberately-bad fixture**. What the fixture must prove depends on
what the row CLAIMS:

- a **blocking** row must be able to go RED. A check that stays green on its own canary is **INERT**.
- a row declared `warn_only=True`, and an **unwired** hand-runnable diagnostic, must be able to SPEAK —
  it has no failing exit path, so its output IS its product. It reads LIVE when the bad tree produces
  output the clean tree did not, and DEAD when it is handed a real violation and says nothing.

Without that fork, honestly declaring a row advisory would keep reporting it INERT forever — the audit
would punish the fix. With it, DEAD keeps exactly one meaning: **a gate row that claims to block and
cannot**.

Control first: the same check on a **clean** tree must exit 0 without a traceback. If the invocation
itself is broken, we have measured our harness and not the check → UNKNOWN, never INERT.

The compose/env fixtures are reused from `tests/test_check_activation_anti_vacuity.py`, so the two agree
by construction. Where no fixture can REACH the check, it is reported **UNPROVEN** with the obstruction
named (`liveness_audit.UNREACHABLE`) — neither green nor red, the third state again.

The deliberately-**unwired** diagnostics (`check_ports`, `check_deps_sync`, `check_watchdog`,
`check_health`, and since 2026-08-16 `check_env_updates`, `check_test_coverage`,
`check_compose_services`, `check_reusable_modules`) are audited too: a hand-runnable check that
silently exits 0 is the same trap in a different hat.

**Invocation forms** (`CANARIES[<check>]["form"]`), because the corpus is not uniform: `root` /
`module` (the `_check_runner` `--root` contract), `cwd` and `gitcwd` (the many checks that read
`Path.cwd()` and the git diff), and `copy` — a copy of `scripts/enforcement/` staged INSIDE the
fixture, the only way to reach a check whose repo root is `Path(__file__).parents[2]`. A fixture is
split into `base` (both trees), `files` (the BAD tree — the violation), `clean` (the control only,
for rules whose violation is an ABSENCE) and `staged` (written after the `git commit` step).

**`warn_only` — the inverted canary.** Eight registered checks had **no non-zero exit path at all**
(`check_compose_services`, `check_doc_stubs`, `check_env_example`, `check_env_updates`,
`check_retired_terms`, `check_reusable_modules`, `check_script_headers`, `check_test_coverage`). Their
fixture is a real violation, the check REPORTS it, and it exits 0 — so each occupied a `final_gate.py`
row that no defect could ever turn red. Each was decided on measured fleet evidence (the reasoning lives
at its registration; the table is in `docs/workflows/FINAL_GATE_WORKFLOW.md` § Advisory rows): four are
now declared `warn_only=True` and print `[ADVISORY]`, four are unwired to hand-runnable diagnostics. The
`warn_only` key in `CANARIES` still records the source line that makes each toothless, and
`tests/test_gate_check_canaries.py` asserts they still print the finding — plus two ratchets: a
warn-only check may never be registered as an ordinary blocking row, and a `warn_only=True` declaration
must be backed by a written contract (a false declaration would be a silent downgrade of a real check).

The whole corpus is asserted as tests in `tests/test_gate_check_canaries.py`, including a `NEUTERS`
set that deletes one check's core rule and proves its canary then goes GREEN — a canary that survives
a broken check proves nothing about a working one.

### PROOF 3 — DOC-CLAIM BINDING ("is the doc true?")

**Every** `docs/workstation/*.md` is enumerated — 20 today, 19 before this file landed; a truncated
listing already produced a false n=12 — and scanned for machine-checkable claims:

| Claim | Extracted from | Verified against |
|---|---|---|
| `cron_line` | a real crontab entry inside a fenced block | `crontab -l`, verbatim; a matching command with a different schedule is reported as **schedule drift** |
| `scheduled_name` | `name (Sun 02:00)` — the token must carry a separator, so prose words never become claims | an active crontab line mentioning the token |
| `port` | `localhost:NNNN` / `127.0.0.1:NNNN` only — a VPS port in prose is not a claim about this box | `ss -ltn` |
| `unit` | a backticked `*.service` | `systemctl is-enabled`/`is-active`, system then `--user` |
| `hook_file` | a backticked script on a line mentioning "hook" | the settings.json hook commands |

Polarity is read from the doc's own words: a doc that names states (`enabled`, `failed`, `disabled`) is
TRUE if the box reports **any** of them. `MCP_HTTP_TRANSPORT.md` says two units are `enabled` and lose the
port race, ending `failed`/`inactive` — all three words are correct, and a naive "any negative word means
disabled" reading called both docs stale. The hook oracle reads only **one of four hook layers**, so a
file that exists but is not in `settings.json` is UNKNOWN with the limit named, not a stale doc.

---

## Running it

```bash
python scripts/sysadmin/liveness_audit.py                   # human table
python scripts/sysadmin/liveness_audit.py --json            # machine report
python scripts/sysadmin/liveness_audit.py --proof heartbeat # one proof (fast)
python scripts/sysadmin/liveness_audit.py --strict          # exit 1 on any DEAD or crashed proof
```

**It exits 0 by default and never raises.** This is a REPORT, not a gate: a monitoring layer that blocks
work gets disabled, and then it monitors nothing. `--strict` is the opt-in CI mode; UNKNOWN never fails
it (an instrument fault is not a defect), but a **crashed proof** does — a silently skipped proof is how
a monitor learns to say all-clear.

Read-only against the box: it never writes to `~/.claude-fleet`, the crontab, `claude-sound.sh`, or any
credential file. Its only writes are to its own temp fixtures.

### Proposed cron (NOT installed — print it, decide, install by hand)

```cron
40 6 * * 1 cd /opt/fabrik && .venv/bin/python scripts/sysadmin/liveness_audit.py --json >> $HOME/.claude/liveness.log 2>&1
```

06:40 Monday, five minutes before kaizen's 06:45 measurement, so kaizen consumes fresh liveness data.
The audit prints this line at the end of every human run.

---

## Feeding kaizen

`kaizen_metrics.py` shells out to `liveness_audit.py --json` (fail-soft, 900 s) and turns the heartbeat
proof into the **`Missed crons`** column — a metric the roles spec pinned and which had been an em-dash
since it was written, because the cron-miss LOG it named was never built and never will be (the per-job
logs are untimestamped appends, so run *counts* are not reconstructible). The answerable question is:
did each registered surface produce evidence inside its own budget?

The cell is `DEAD / (LIVE + DEAD)` over the heartbeat surfaces. ⚠️ **UNKNOWNs are excluded from BOTH
halves and named in the detail.** Folding them into the denominator reports a healthier box than we
measured; folding them into the numerator invents defects. Either breaks kaizen's honesty rule with a
number that looks fine. If *every* surface is UNKNOWN, the cell is an em-dash naming the instrument
faults. Guarded by `test_an_unknown_surface_is_never_rendered_as_a_number`.

Mechanism health — inert checks, unproven checks, stale doc claims, unregistered surfaces — rides the
hand-off mail as context, so the weekly kaizen row finally measures the machinery and not only outcomes.

---

## Watched fail (the red runs behind these tests)

Both are red-on-revert proofs; neither neutered state was staged or committed.

| Neutered | Red |
|---|---|
| `finding()`'s instrument check replaced with `if False:` | 6 failed, 30 passed — headline `test_a_probe_whose_instrument_fails_reports_unknown_never_dead`: `assert 'DEAD' == 'UNKNOWN'` |
| `measure_missed_crons` folding UNKNOWN back into the denominator | 2 failed — `Metric(value='0/1', …)` where an em-dash was owed |

---

## First real audit (2026-08-16)

`LIVE=52 DEAD=4 UNKNOWN=47` across the three proofs — heartbeat `22/3/3`, vacuity `7/0/40`, doc-claim
`23/1/4`; 41 crontab entries read (22 ours, 19 other repos'), 0 unregistered surfaces, 43 gate checks
parsed, 20 docs enumerated, 28 claims extracted. What it found on its first run:

- **DEAD ×3 (heartbeat)** — `claude-keepalive`, `kaizen-measurement`, `fabrik-mail-digest`: all three have
  a crontab line and have **never written evidence**. Their weekly/daily slots have not come round since
  the lines were installed; the audit says so precisely rather than guessing.
- **DEAD ×1 (doc-claim)** — `wsl-startup-inventory.md:48` schedules a calendar pipeline at Sun 02:00; the
  crontab holds only a **comment header**, no active line.
- **UNKNOWN ×3 (heartbeat)** — `fleet-doc-audit` and `mutation-sweep` write to `/tmp` (volatile: absence
  proves nothing); `ai-catalog-daily-refresh` has **no evidence channel at all** — a real monitoring gap,
  reported as one instead of hidden behind a green.
- **UNKNOWN ×4 (doc-claim)** — four `hook_file` claims naming files that exist but are wired outside the
  `settings.json` layer this oracle can read.
- **LIVE ×44 (vacuity)** — 36 canaried checks went red on their fixture; the other 8 are the decided
  `warn_only` set, each REPORTING its violation on an advisory or unwired row. Was 7 when this file
  landed; the corpus was completed the same day (see `tests/test_gate_check_canaries.py`).
- **DEAD ×0 (vacuity)** — was 8: the `warn_only` set, registered like ordinary checks and structurally
  unable to exit non-zero. Four are now declared `warn_only=True`, four are unwired; none occupies a
  blocking row it cannot lose. DEAD now counts only rows that claim to block and cannot.
- **UNKNOWN ×3 (vacuity)** — `check_vps_docs` (hardcoded absolute `/opt/fabrik` root), `check_phase_tests`
  and `check_mutation` (need an active plan lock / mutmut respectively — and all three return 0
  everywhere anyway, so all three are registered `warn_only=True`). Recorded in
  `liveness_audit.UNREACHABLE` with the obstruction named. 3 is the honest size of the remaining gap; it
  was 40.
- **`check_vps_docs` no longer reds the hub** — `vps-status.md` and `vps-urls.md` live in
  `docs/infrastructure/`; `check_vps_docs` + `vps-sync` now point there (they had been mis-referenced as
  `docs/operations/`, where the files never existed, and `fabrik vps-sync` refreshes them in place — the
  fleet agent's beat), and every finding the check
  can construct is `Severity.WARN` while its `__main__` exited 1 on ANY finding. Its exit now follows the
  severity — ERROR fails, `--strict` promotes WARN — matching `_check_runner.run_as_main`; pinned by
  `tests/test_check_vps_docs_severity.py`.
- **`reboot-sweep` LIVE** — last `arg=sweep` 4.4 h ago, 21 occurrences. The exact finding that was
  reported to the operator as "NEVER run".

---

## See also

- `docs/workstation/kaizen.md` — the weekly loop this feeds
- `docs/workstation/hooks-index.md` — every hook on the box, the registry's hook surfaces
- `docs/workstation/wsl-startup-inventory.md` — what runs on boot (and the one stale claim above)
- `tests/test_check_activation_anti_vacuity.py` — the canary fixtures PROOF 2 reuses
- `tests/test_gate_check_canaries.py` — the whole canary corpus as tests, plus the coverage ratchet
  (a new `run_optional_check(...)` with no canary and no `UNREACHABLE` reason fails the suite)
- `tests/test_final_gate_advisory_display.py` — the gate's output must distinguish an `[ADVISORY]` row
  from a passing blocking one, in both the human view and `--json`
- `tests/test_check_vps_docs_severity.py` — a WARN finding must not fail a gate row; an ERROR still must
- `docs/workflows/FINAL_GATE_WORKFLOW.md` § Advisory rows — the per-check decisions and their measurements
