# AFTER-EDIT: docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md (Phase A.0 gates)
"""Phase A.0 — the flywheel-safety invariant, made testable.

Guards the operator's binding constraint ("we should not break flywheel") across the
extraction. Three properties, all load-bearing:

1. A BROKEN read (subprocess/psql failure) is distinguishable from a genuinely EMPTY one —
   ``_query_rows`` returns ``("error", [])`` vs ``("ok", [])``. Without this, the daily stub
   advances its "Last refresh" date on a lie and broken looks identical to healthy-but-empty.
2. A broken read exits **1** from ``main()`` — the tripwire.
3. A genuinely-empty-but-reachable flywheel exits **0** — an empty table is not a failure.

These are simulated (monkeypatched subprocess), so the suite runs anywhere — it must NOT
depend on a live database or on passwordless sudo. The live positive-proof assertion is a
separate operational gate (A.0 gate 1 / B.4a), deliberately not a unit test.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rank_task_subagents as rts  # noqa: E402


class _Result:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_broken_read_is_distinguishable_from_empty(monkeypatch):
    """A psql/sudo failure yields state 'error' — never a bare empty list."""
    monkeypatch.setattr(
        rts.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(OSError("sudo: command not found")),
    )
    state, rows = rts._query_rows()
    assert state == "error", "a failed read MUST report state='error', not masquerade as empty"
    assert rows == []


def test_nonzero_psql_exit_is_error_state(monkeypatch):
    """psql exiting non-zero is a broken read, not an empty one."""
    monkeypatch.setattr(
        rts.subprocess, "run", lambda *a, **k: _Result(returncode=2, stderr="FATAL: no such db")
    )
    state, rows = rts._query_rows()
    assert state == "error"
    assert rows == []


def test_reachable_but_empty_is_ok_state(monkeypatch):
    """An empty-but-reachable flywheel is 'ok' — an empty table is not a failure."""
    monkeypatch.setattr(rts.subprocess, "run", lambda *a, **k: _Result(returncode=0, stdout=""))
    state, rows = rts._query_rows()
    assert state == "ok", "a clean query over an empty table must NOT report 'error'"
    assert rows == []


def test_broken_read_exits_nonzero(monkeypatch):
    """THE TRIPWIRE: main() returns 1 when the read is broken."""
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "stub")
    monkeypatch.setattr(rts, "_atomic_write", lambda *a, **k: None)
    rc = rts.main()
    assert rc == 1, "a BROKEN flywheel read must exit 1 — this is the only signal a caller gets"


def test_healthy_read_exits_zero(monkeypatch):
    """The mirror: a healthy read must not trip the wire."""
    monkeypatch.setattr(rts, "_query_rows", lambda: ("ok", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "stub")
    monkeypatch.setattr(rts, "_atomic_write", lambda *a, **k: None)
    assert rts.main() == 0


def test_daily_refresh_does_not_swallow_the_tripwire():
    """The un-mute: daily_refresh.sh must not discard the ranker's exit code.

    `_step` propagates rc correctly, but a bare `|| echo "... (non-fatal)"` at the call site
    turns exit 1 into a log line nobody reads — the file has no `set -e`, redirects to a
    logfile, and the crontab has no MAILTO, so propagation alone surfaces to no one.
    """
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    lines = [ln for ln in sh.splitlines() if "rank_task_subagents" in ln and "_step" not in ln]
    swallowed = [
        ln for ln in lines if "|| echo" in ln and "non-fatal" in ln and "alert" not in ln.lower()
    ]
    assert not swallowed, (
        "daily_refresh.sh swallows the rank_task_subagents tripwire into a log line: "
        f"{swallowed!r} — route the failure to send_alert instead (A.0 gate 3)"
    )


def test_the_alert_can_actually_fire_not_just_exist():
    """A grep for the absence of `|| echo` proves nothing about DELIVERY.

    `alerting/` does not load dotenv, and `_is_enabled()` reads TELEGRAM_BOT_TOKEN /
    ALERT_VPS_HOST from the process env. The token lives only in `.env`, so a
    `python -c "from alerting import send_alert; ..."` invocation that does NOT load dotenv
    first is a SILENT no-op — the exact failure this gate exists to prevent, reproduced
    inside the fix. The working idiom is `check_daily_refresh_freshness.py:39-43`:
    load_dotenv BEFORE importing alerting.
    """
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    alert_lines = [
        ln for ln in sh.splitlines() if "send_alert" in ln and "rank_task_subagents" in ln.lower()
    ]
    assert alert_lines, "the rank_task_subagents failure path must fire an alert"
    for ln in alert_lines:
        assert "load_dotenv" in ln, (
            "alert invocation does not load_dotenv before importing alerting, so "
            "alerting._is_enabled() is False and the alert silently never delivers: " + ln[:120]
        )


def test_alerting_is_enabled_once_dotenv_is_loaded():
    """End-to-end: with .env loaded the way the fixed invocation loads it, alerting is live."""
    from dotenv import load_dotenv

    load_dotenv(SCRIPT_DIR.parents[1] / ".env", override=False)
    import alerting

    assert alerting._is_enabled(), (
        "alerting reports itself DISABLED even with .env loaded — the un-mute would be a no-op"
    )
