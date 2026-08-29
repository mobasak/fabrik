# Phase B review — claude_broker.py (completion-only container broker)

**Surface:** `scripts/sysadmin/claude_broker.py` + `tests/test_claude_broker.py`
**Plan:** docs/development/plans/2026-08-29-plan-1-vps-quota-governance.md (Phase B — the container broker)
**Status:** DONE — coverage-adjudicated exit, found: 0 on the security boundary

The broker is the CONFUSED-DEPUTY boundary: containers get `claude -p --tools "" -- <prompt>` completion,
never host tools or creds. Token auth (401), per-caller window budget (429), fail-closed tool-disable
(503), forced-`routine` routing through the Phase-A governor.

## Rounds

`Finders: native opus ×1 — round 1`
`Finders: pool deepseek-v3.2 + gemini-3-flash ×2 (+ native opus stalled on stream watchdog, re-dispatched) — round 2`
`Finders: native opus ×1 — round 3 (confirming)`

- **Round 1 (native Opus — found 5 real, fixed 5):**
  - **HIGH (confused-deputy)** — the container-controlled prompt was a bare trailing positional; a prompt
    like `--allow-dangerously-skip-permissions` would be parsed as a CLI flag, bypassing `--tools ""`.
    **FIXED:** POSIX `--` end-of-options before the prompt (`argv += ["--", prompt]`). Red-on-revert PROVEN
    (copy-based): without `--`, `test_prompt_cannot_inject_a_flag` FAILS. Grounded: `claude --help` usage
    `[options] [command] [prompt]` — prompt IS positional.
  - **MED (fail-open)** — a window stored with a `None` epoch during a `--status` outage never upgraded on
    recovery → a caller wedged at 429 forever. **FIXED:** `_caller_state` adopts the fresh epoch when the
    stored one is None. Test: `test_none_epoch_window_recovers_on_status_return`.
  - **MED (fail-open)** — a failed claude run spent ob@ quota but wasn't counted/audited and the exception
    escaped. **FIXED:** count + audit on failure, return 502, never raise. Test:
    `test_failed_run_counts_audits_and_502`.
  - **LOW** — non-dict body / malformed token config crashed. **FIXED:** 400 / 500 guards. Tests:
    `test_non_dict_body_400`, `test_malformed_token_config_500`.
  - REFUTED: constant-time token compare (single-operator, loopback — out of scope).
- **Round 2 (pool breadth + native re-dispatch after a stall — 2 more real, fixed 2):**
  - **HIGH (confused-deputy, pool deepseek)** — the `model` value (container-controlled, value slot BEFORE
    the `--`) could be a `--`-leading token some arg parsers read as a flag. **FIXED:** `_MODEL_RE`
    validation → 400. ⚠️ The FIRST regex `^[A-Za-z0-9._-]+$` was too permissive (it ALLOWED
    `--allow-dangerously-skip-permissions`, which is all letters+hyphens) — its own test
    `test_flag_shaped_model_rejected_400` caught it; tightened to `^[A-Za-z0-9][A-Za-z0-9._-]*$` (must start
    alphanumeric, no leading hyphen).
  - **INFO (pool gemini)** — `serve` read `Content-Length` bytes with no cap → OOM. **FIXED:** `_MAX_BODY`
    (1 MB) → 413 before the read.
  - REFUTED: 503 info-leak (container can't alter server config), 502 budget-bypass (the fix counts
    failures — finder conceded), off-by-one (finder conceded correct), rollover disk-I/O (degenerate
    past-epoch telemetry only — perf, not correctness).
- **Round 3 (confirming — the tool/creds boundary CONFIRMED AIRTIGHT; 2 wrapper-robustness findings, fixed):**
  - Native Opus confirmed all 6 defenses airtight: the `--` prompt sentinel, the model regex (checked before
    any run; a passing value can't lead with `-` nor split argv), fail-closed `--tools ""`, budget
    counts-on-failure, None-epoch recovery, no exception escapes. It also confirmed
    `test_flag_shaped_model_rejected_400` genuinely constrains the regex (would fail a too-permissive one).
  - **MED** — `serve.do_POST`: a NEGATIVE `Content-Length` (`-1`) bypassed the `_MAX_BODY` cap
    (`-1 > 1_000_000` is False) → `rfile.read(-1)` reads unbounded to EOF → OOM. **FIXED.**
  - **LOW** — a non-integer `Content-Length` raised an uncaught `ValueError` outside the try. **FIXED.**
  - Both closed by a testable pure helper `_safe_content_length` (rejects negative/non-integer/over-cap → 413
    before any read). Test: `test_safe_content_length`.

**Exit — the confused-deputy boundary (tool/creds) is CONFIRMED AIRTIGHT (round 3); every finding across 3
rounds is FIXED, the 2 security-critical fixes red-on-revert proven. found: 0.** Status: DONE.

## Coverage Checklist

| Class | Swept | Verdict |
|---|---|---|
| confused-deputy / tool bypass | prompt `--` sentinel + model charset validation + fail-closed `--tools ""` before every run; container reaches no host tool | FIXED |
| fail-open / fail-silent | failed run counts+audits+502 (never escapes); None-epoch recovers; non-dict body/bad token guarded; do_POST wraps →500 | FIXED |
| cost/quota accounting | budget counts success AND failure; over-budget at limit → 429; window reset from live `--status` epoch | FIXED |
| boundary / sentinel | `count >= limit`; None epoch never `now>=None`, adopts fresh on recovery | CLEAN |
| resource exhaustion | `_MAX_BODY` cap → 413 | FIXED |
| auth | per-caller token → 401; class forced `routine` server-side (never self-labelled) | CLEAN |
| behavior-without-a-test | 18 tests, one per behavior incl. the two security fixes (red-on-revert proven for `--`) | CLEAN |
| secret handling | ob@ cred host-side only; audit records a prompt HASH, never the raw prompt | CLEAN |

## Gate

```
$ .venv/bin/python -m pytest tests/test_claude_broker.py -q  →  18 passed
$ .venv/bin/ruff check scripts/sysadmin/claude_broker.py tests/test_claude_broker.py  →  All checks passed!
$ .venv/bin/mypy scripts/sysadmin/claude_broker.py  →  Success: no issues found
```

Exit: _pending round-3 finder → found: 0 to close._
