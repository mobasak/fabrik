"""Behavior-Contract tests — the fleet CI-health probe.

Spec: docs/superpowers/specs/2026-08-15-ci-health-probe-design.md. Written against the live
2026-08-15 incident: GitHub refused to START jobs (1-second failures, ZERO steps, no logs) while
every local gate stayed green and ci_fix_dispatcher would have dispatched Claude workers to
"fix" code that was never broken.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "scripts" / "sysadmin" / "ci_health_probe.py"

spec = importlib.util.spec_from_file_location("ci_health_probe", PROBE)
cp = importlib.util.module_from_spec(spec)
sys.modules["ci_health_probe"] = cp
spec.loader.exec_module(cp)


# ── 1. the classification that the whole design rests on ───────────────────────


def test_zero_step_failure_is_never_started_not_a_test_failure():
    """The live signature: conclusion=failure with an EMPTY steps list. Treating it as a test
    failure is what would make an auto-fixer burn quota during a quota outage."""
    assert cp.classify_run({"conclusion": "failure", "steps": []}) == "never-started"


def test_real_failure_with_steps_is_a_test_failure():
    job = {"conclusion": "failure",
           "steps": [{"name": "ruff", "conclusion": "failure"},
                     {"name": "checkout", "conclusion": "success"}]}
    assert cp.classify_run(job) == "test-failure"


def test_success_is_ok():
    assert cp.classify_run({"conclusion": "success", "steps": [{"name": "x"}]}) == "ok"


# ── 2. quota foresight — the half that PREVENTS rather than reports ────────────


def _quota(monkeypatch, plan: str, minutes: float, month="2026-08"):
    import json as _json

    def fake_sh(cmd, timeout=45):
        if "/user" in cmd and "--jq" in cmd:
            return 0, f"tester {plan}\n"
        if "settings/billing/usage" in " ".join(cmd):
            return 0, _json.dumps({"usageItems": [
                {"date": f"{month}-01T00:00:00Z", "sku": "Actions Linux", "quantity": minutes},
                {"date": f"{month}-01T00:00:00Z", "sku": "Actions storage", "quantity": 99},
                {"date": "2026-01-01T00:00:00Z", "sku": "Actions Linux", "quantity": 5000},
            ]})
        return 1, ""

    monkeypatch.setattr(cp, "sh", fake_sh)
    monkeypatch.setattr(cp, "datetime", _FrozenNow(month))
    return cp.actions_quota()


class _FrozenNow:
    def __init__(self, month):
        self._month = month

    def now(self, tz=None):  # noqa: ARG002
        return _Stamp(self._month)


class _Stamp:
    def __init__(self, month):
        self._month = month

    def strftime(self, fmt):  # noqa: ARG002
        return self._month


def test_quota_counts_only_this_month_and_only_actions_minutes(monkeypatch):
    q = _quota(monkeypatch, "pro", 2411)
    assert q["used"] == 2411, "storage rows and other months must not be counted"
    assert q["included"] == 3000 and q["plan"] == "pro"
    assert 80 <= q["pct"] < 81


def test_free_plan_allowance_is_2000(monkeypatch):
    q = _quota(monkeypatch, "free", 2074)   # the real July figure that caused the outage
    assert q["included"] == 2000 and q["pct"] > 100


def test_unreachable_billing_api_is_unknown_never_zero(monkeypatch):
    """A fail-open zero would silence the alert exactly when the endpoint moves again — which
    it already did once (the old per-user endpoint 410s)."""
    monkeypatch.setattr(cp, "sh", lambda cmd, timeout=45: (1, ""))
    assert cp.actions_quota() is None


# ── 3. alerting: one event, one message; suppression survives restarts ─────────


def test_one_alert_for_many_blocked_repos(tmp_path, monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(cp, "STATE_DIR", tmp_path)
    monkeypatch.setattr(cp, "notify", lambda t, b: sent.append((t, b)))
    monkeypatch.setattr(cp, "actions_quota", lambda: None)
    monkeypatch.setattr(cp, "OPT", tmp_path / "opt")
    (tmp_path / "opt").mkdir()
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / "opt" / name / ".git").mkdir(parents=True)
    monkeypatch.setattr(cp, "repo_slug", lambda d: f"acme/{d.name}")
    monkeypatch.setattr(cp, "probe_repo", lambda slug: {
        "repo": slug, "run_id": 1, "workflow": "CI", "verdict": "never-started",
        "created": "2026-08-14T20:20:19Z",
        "reason": "The job was not started because recent account payments have failed"})
    assert cp.main([]) == 0
    assert len(sent) == 1, f"a fleet stop is ONE message, got {len(sent)}"
    assert "3 repo(s)" in sent[0][1] and "alpha" in sent[0][1] and "gamma" in sent[0][1]
    assert "2026-08-14" in sent[0][1], "the alert must date the run — a stale block reads as live otherwise"


def test_suppression_blocks_the_second_tick(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "STATE_DIR", tmp_path)
    assert cp.suppressed("blocked") is False, "first call arms the stamp and does not suppress"
    assert cp.suppressed("blocked") is True, "second call within the window suppresses"


def test_suppression_expires(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "STATE_DIR", tmp_path)
    monkeypatch.setattr(cp, "SUPPRESS_S", 0.01)
    cp.suppressed("k")
    time.sleep(0.02)
    assert cp.suppressed("k") is False


# ── 4. cron safety: never a traceback, never a false red ───────────────────────


def test_probe_exits_zero_when_everything_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cp, "OPT", tmp_path / "nonexistent")
    monkeypatch.setattr(cp, "STATE_DIR", tmp_path)
    monkeypatch.setattr(cp, "sh", lambda cmd, timeout=45: (1, ""))
    assert cp.main([]) == 0
    assert "UNKNOWN" in capsys.readouterr().out


def test_no_actions_minutes_are_consumed_by_the_probe():
    """Contract: the probe only READS (gh api / gh run list). A `gh workflow run` or a push
    would consume the very quota it exists to protect."""
    src = PROBE.read_text()
    assert "workflow run" not in src and "gh run rerun" not in src


def test_public_repo_minutes_are_not_counted(monkeypatch):
    """2026-08-15 false alarm: PUBLIC-repo minutes are unmetered (gross fully discounted,
    net $0) but the probe summed raw quantity — fabrik's 2559 public minutes read as 82% of
    the Pro allowance. Only private (and unknown-visibility, fail-loud) repos count."""
    import json as _json

    def fake_sh(cmd, timeout=45):
        joined = " ".join(cmd)
        if "/user" in cmd and "--jq" in cmd:
            return 0, "tester pro\n"
        if "settings/billing/usage" in joined:
            return 0, _json.dumps({"usageItems": [
                {"date": "2026-08-01T00:00:00Z", "sku": "Actions Linux", "quantity": 2559,
                 "repositoryName": "fabrik"},
                {"date": "2026-08-01T00:00:00Z", "sku": "Actions Linux", "quantity": 40,
                 "repositoryName": "tryton-crm"},
                {"date": "2026-08-01T00:00:00Z", "sku": "Actions Linux", "quantity": 7,
                 "repositoryName": "mystery"},
            ]})
        return 1, ""

    monkeypatch.setattr(cp, "sh", fake_sh)
    monkeypatch.setattr(cp, "datetime", _FrozenNow("2026-08"))
    monkeypatch.setattr(cp, "_repo_is_private", lambda owner, repo: {
        "fabrik": False, "tryton-crm": True}.get(repo))  # mystery -> None (unknown)
    q = cp.actions_quota()
    assert q["used"] == 47, "public fabrik excluded; private + unknown counted (fail-loud)"
