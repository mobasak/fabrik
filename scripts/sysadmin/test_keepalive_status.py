# AFTER-EDIT: none
"""Tests for keepalive-status.sh::keepalive_reason — the shared CONTENT classifier that
daily-digest.sh + proactive-check.sh use so a fresh mtime with a 401/usage-limit token is
reported BROKEN, not "fresh" (the month-long-401-reads-as-fresh bug). Also asserts both
monitors actually source the helper + still parse."""
import pathlib
import subprocess

import claude_rotate  # cross-check the classifier against the rotation core's regex
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/sysadmin/keepalive-status.sh"
DIGEST = ROOT / "scripts/sysadmin/daily-digest.sh"
PROACTIVE = ROOT / "scripts/sysadmin/proactive-check.sh"

# Every render the Python rotation core treats as a usage-limit — INCLUDING a branch-5-only
# "limit · resets" render (no "hit your…limit"). The monitors' classifier must match all of
# them (the shim/classifier regex must not be a subset of the core's rotation trigger).
GROUNDED_LIMIT_RENDERS = [
    "Claude usage limit reached. Resets at 3pm",
    "You've hit your weekly limit · resets 3pm",
    "You've hit your session limit · resets 3:45pm",
    "You've hit your Opus limit · resets 3:45pm",
    "5-hour limit reached - resets 3pm",
    "You're out of extra usage · resets 3pm",
    "You've reached your limit · resets 3pm",  # branch-5 ONLY
]


def _reason(tmp_path, content, *, write=True):
    log = tmp_path / "ka.log"
    if write:
        log.write_text(content)
    script = f'. "{HELPER}"; keepalive_reason "{log}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_helper_syntax_valid():
    r = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_keepalive_ok_token_is_healthy(tmp_path):
    assert _reason(tmp_path, "KEEPALIVE_OK 2026-07-08T10:00:00+00:00") == "", "OK token → healthy (empty)"


def test_keepalive_fail_401_token_is_broken(tmp_path):
    out = _reason(tmp_path, "KEEPALIVE_FAIL:401_auth 2026-07-08T10:00:00+00:00")
    assert "401_auth" in out, f"FAIL:401_auth token → broken reason, got {out!r}"


def test_keepalive_fail_usage_limit_token_is_broken(tmp_path):
    out = _reason(tmp_path, "KEEPALIVE_FAIL:usage_limit 2026-07-08T10:00:00+00:00")
    assert "usage_limit" in out


def test_old_format_raw_401_is_broken(tmp_path):
    # pre-shim log (raw claude output, no token) with a real 401 → detected as 401_auth
    assert _reason(tmp_path, "401 Invalid authentication credentials") == "401_auth"


def test_old_format_raw_usage_limit_is_broken(tmp_path):
    assert _reason(tmp_path, "You've hit your session limit · resets 3pm") == "usage_limit"


def test_old_format_healthy_ping_is_fresh(tmp_path):
    # a successful pre-shim ping wrote the JSON result — no 401/limit → healthy
    assert _reason(tmp_path, '{"result":"pong"}') == ""


def test_benign_401_substring_is_not_broken(tmp_path):
    # RC=0 old-format output mentioning "401" but no auth wording → NOT a break
    assert _reason(tmp_path, "checked port 401 and it is closed") == ""


def test_missing_log_is_empty(tmp_path):
    assert _reason(tmp_path, "", write=False) == "", "absent log → no reason (mtime check handles cron-dead)"


@pytest.mark.parametrize("render", GROUNDED_LIMIT_RENDERS)
def test_classifier_matches_every_rotation_trigger(tmp_path, render):
    # Invariant: whatever the Python rotation core rotates on, the monitors must also classify
    # as usage_limit (old-format log path) — same 5 regex branches, no subset drift.
    assert claude_rotate.is_usage_limit(render), f"rotation core should match {render!r}"
    assert _reason(tmp_path, render) == "usage_limit", f"classifier must match {render!r} too"


def test_both_tokens_present_fails_closed(tmp_path):
    # a partially-overwritten log carrying BOTH tokens must read BROKEN — FAIL wins over OK
    out = _reason(
        tmp_path,
        "KEEPALIVE_FAIL:401_auth 2026-07-08T09:00:00+00:00\nKEEPALIVE_OK 2026-07-08T10:00:00+00:00",
    )
    assert "401_auth" in out, "FAIL must take precedence over OK (fail-closed)"


def test_both_monitors_source_the_helper_and_stay_valid():
    for mon in (DIGEST, PROACTIVE):
        src = mon.read_text()
        assert "keepalive-status.sh" in src, f"{mon.name} must source the shared classifier"
        assert "keepalive_reason" in src, f"{mon.name} must call keepalive_reason"
        r = subprocess.run(["bash", "-n", str(mon)], capture_output=True, text=True)
        assert r.returncode == 0, f"{mon.name}: {r.stderr}"
