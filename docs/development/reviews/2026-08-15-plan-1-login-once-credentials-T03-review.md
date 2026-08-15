# T03 — Fleet-mode status/tick + keepalive: per-ticket review ledger

## Round 1 (2026-08-15)

Finders: pool deepseek-v3.2-exp + gemini-3-flash (production diff inline, read_only) +
native opus (worktree probes + 2 mutant tests) — round 1.
Surface: worktree commit d8d8ea96 on 713699eb: claude_rotate.py +437 (fleet status/tick/
keepalive), tests/test_claude_fleet.py +13 (78 total), v2 +7 hermeticity lines, twin.
Coder's claims re-verified first-hand: 179/179 across the 4 suites, twins md5 268a98c9;
coder's watched-fail-first log honest (13 red pre-change + a red-on-revert hermeticity
proof).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | Advisory-suppression stamp age unclamped — a FUTURE-dated stamp mtime (WSL suspend/NTP, the `_last_switch_ts` class T01 fixed with `_CLOCK_SKEW_TOLERANCE_S`) makes age negative → `age < 86400` true → the ≥85% advisory Telegram + drain-mail silenced INDEFINITELY; probe: stamp +5d, zero telegrams | opus CONFIRMED (probe) | **FIX (F54)**: clamp per the in-file `_CLOCK_SKEW_TOLERANCE_S` precedent — future-beyond-tolerance stamp = expired |
| 2 | Same class in `_cmd_keepalive`: unclamped `idle_s` — future-skewed credentials mtime reads "fresh", silently skips a due ping | opus CONFIRMED | **FIX (F55)**: negative-beyond-tolerance idle = due (spurious ping harmless; missed ping risks the 30d lapse) |
| 3 | Legacy `_tick_inner` drain stamp has the identical unclamped pattern (pre-existing, same file) | opus | **FIX (F58)**: adjacent same-file fix, declared — same clamp |
| 4 | Stale `default=str` + comment in `_cmd_fleet_status` JSON dump — shape it guards no longer reaches serialization | opus NIT | **FIX (F56)**: delete or make accurate |
| 5 | `_fleet_slug_repos` uses `OPT_DIR` but calls `_mailbox_repos()` which scans literal `/opt` — hermeticity seam split in two | opus NIT | **FIX (F57)**: `_mailbox_repos` scans `OPT_DIR` (same value in prod, one seam) |

Refuted: identity-pin lost-update/clobber (write-back re-reads under the flock and applies
only to rows STILL pending — compare-and-set; probe-confirmed, orchestrator code-read
concurred) · keepalive env leak (both vars unconditionally overridden atop os.environ;
150s timeout, TimeoutExpired counted as failure) · cache poisoning on failed probe
(cache write gated on `windows is not None`; probe-confirmed) · corrupt cache crash
(fails soft to `{}`) · duplicate concurrent probe (one wasted call, docstring-acknowledged)
· lock-fail pins-in-memory-only (documented fail-soft, costs one re-probe) · advisory
noise on stamp-touch failure (fail-open toward NOISE is the correct direction for an
advisory) · 85.0 boundary fires · pending rows excluded without crash · fleet-root
disappears mid-run (single-operator, fails with a readable error) · structural
no-successor + empty-root byte-identical guards both mutant-killed · credential-byte
census clean (token reads in-memory via the sanctioned reader; keepalive mtime-only,
trap-tested).

Round 1 verdict: NOT CLEAN — F54–F58 dispatched. Round 2 follows.
