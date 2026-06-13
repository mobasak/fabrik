"""Unit tests for the PR3 _provision_sysadmin helper functions, exercising the
REAL implementations (no autouse network-stubbing fixture here).

Covers gaps surfaced in deep review: the new aro-wake health retry loop, the
.env.sysadmin parser, and the Telegram getMe token check — all previously
stubbed away in test_vultr_provision.py and therefore uncovered.
"""

import time
from unittest.mock import MagicMock

from fabrik.orchestrator import vultr_provision as prov


def _cp(stdout="", returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


# ── _check_aro_wake_health (new retry loop) ────────────────────────────────


def test_health_200_first_try_no_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: calls.append(1) or _cp("200"))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    assert prov._check_aro_wake_health("10.99.0.4") == "200"
    assert len(calls) == 1  # success short-circuits — no wasted retries


def test_health_retries_then_succeeds(monkeypatch):
    seq = [_cp("000"), _cp(""), _cp("200")]  # refused, no-response, then up
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    assert prov._check_aro_wake_health("10.99.0.4") == "200"
    assert seq == []  # consumed all three — proves it retried


def test_health_all_fail_reports_after_n_tries(monkeypatch):
    calls = []
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: calls.append(1) or _cp("503"))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    out = prov._check_aro_wake_health("10.99.0.4", attempts=3)
    assert "after 3 tries" in out and "503" in out
    assert "verify from a mesh host" in out  # actionable annotation
    assert len(calls) == 3  # exhausted the retries, not more


# ── _local_env_sysadmin (parser) ───────────────────────────────────────────


def test_local_env_sysadmin_parses_and_skips_comments(monkeypatch, tmp_path):
    monkeypatch.setattr(prov, "FABRIK_ROOT", tmp_path)
    (tmp_path / ".env.sysadmin").write_text(
        "# comment\n\nTELEGRAM_OWNER_ID=6999\nWATCHDOG_OPENROUTER_KEY=sk-or-x\n# trailing\n"
    )
    env = prov._local_env_sysadmin()
    assert env["TELEGRAM_OWNER_ID"] == "6999"
    assert env["WATCHDOG_OPENROUTER_KEY"] == "sk-or-x"
    assert "# comment" not in env


def test_local_env_sysadmin_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(prov, "FABRIK_ROOT", tmp_path)  # no .env.sysadmin written
    assert prov._local_env_sysadmin() == {}


# ── _check_bot_token (getMe, never logs the token) ─────────────────────────


def test_bot_token_valid(monkeypatch):
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: _cp('{"ok": true}'))
    assert prov._check_bot_token("123:abc") == "valid"


def test_bot_token_invalid(monkeypatch):
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: _cp('{"ok": false}'))
    assert prov._check_bot_token("123:abc").startswith("invalid")


def test_bot_token_unverified_on_garbage(monkeypatch):
    monkeypatch.setattr(prov.subprocess, "run", lambda *a, **k: _cp("not json"))
    assert prov._check_bot_token("123:abc") == "unverified (getMe call failed)"
