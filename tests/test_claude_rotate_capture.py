# AFTER-EDIT: scripts/sysadmin/claude_rotate.py
"""Behavior contract for claude_rotate's token RE-CAPTURE (plan 2026-08-10-plan-1, Phase C).

Why this exists (live incident 2026-08-10 12:05): the stored snapshot for the active account
was 1.5 days stale, so the credential chain ran on an old refresh token until it could not be
refreshed at all. Re-capture keeps the snapshot equal to the live token, so a later restore can
never resurrect a dead one.

Contract under test:
  --capture-current  snapshot the LIVE creds into the active account's dir — atomically
                     (tmp + os.replace, mirroring _activate_snapshot), 0600, MONOTONE (never
                     replace a newer snapshot with an older one), token bytes never emitted.
  --drift-check      read-only compare; capture only when the live token differs. Quiet, exit 0.
"""

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "sysadmin" / "claude_rotate.py"
_spec = importlib.util.spec_from_file_location("claude_rotate", _MOD)
rot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rot)


def _creds(token: str, org: str | None = None) -> str:
    d: dict = {"claudeAiOauth": {"accessToken": token, "refreshToken": f"rt-{token}"}}
    if org:
        d["organizationUuid"] = org
    return json.dumps(d)


@pytest.fixture
def box(tmp_path, monkeypatch):
    """An isolated ~/.claude with two account snapshots; acct-b is active."""
    claude = tmp_path / ".claude"
    accounts = claude / "manager-accounts"
    (accounts / "acct-a").mkdir(parents=True)
    (accounts / "acct-b").mkdir(parents=True)
    (accounts / "acct-a" / ".credentials.json").write_text(_creds("tok-A"))
    (accounts / "acct-b" / ".credentials.json").write_text(_creds("tok-B-OLD"))
    (claude / ".credentials.json").write_text(_creds("tok-B-LIVE"))
    (claude / ".active-account").write_text("acct-b")
    monkeypatch.setattr(rot, "CLAUDE_DIR", claude)
    monkeypatch.setattr(rot, "ACTIVE_CREDS", claude / ".credentials.json")
    monkeypatch.setattr(rot, "ACCOUNTS_DIR", accounts)
    monkeypatch.setattr(rot, "ACTIVE_MARKER", claude / ".active-account")
    return claude


def test_capture_writes_the_live_token_into_the_active_snapshot(box):
    assert rot._cmd_capture_current() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-LIVE"


def test_capture_is_0600(box):
    rot._cmd_capture_current()
    mode = stat.S_IMODE((box / "manager-accounts/acct-b/.credentials.json").stat().st_mode)
    assert mode == 0o600


def test_capture_leaves_no_tmp_litter(box):
    rot._cmd_capture_current()
    leftovers = [p.name for p in (box / "manager-accounts/acct-b").iterdir() if ".tmp" in p.name]
    assert leftovers == []


def test_capture_never_touches_a_sibling_snapshot(box):
    before = (box / "manager-accounts/acct-a/.credentials.json").read_text()
    rot._cmd_capture_current()
    assert (box / "manager-accounts/acct-a/.credentials.json").read_text() == before


def test_capture_is_monotone_identical_content_is_a_noop(box):
    """A capture that would write the SAME bytes must not churn the file (mtime stable)."""
    rot._cmd_capture_current()
    snap = box / "manager-accounts/acct-b/.credentials.json"
    os.utime(snap, (1_000_000, 1_000_000))
    rot._cmd_capture_current()
    assert snap.stat().st_mtime == 1_000_000


def test_capture_refuses_when_the_live_creds_have_no_token(box):
    (box / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {}}))
    assert rot._cmd_capture_current() != 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-OLD"  # untouched


def test_capture_refuses_when_no_active_account_resolves(box):
    (box / ".credentials.json").write_text(_creds("tok-UNKNOWN"))
    (box / ".active-account").unlink()
    assert rot._cmd_capture_current() != 0


def test_drift_check_captures_when_the_token_diverged(box):
    assert rot._cmd_drift_check() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-LIVE"


def test_drift_check_is_a_noop_when_in_sync(box):
    rot._cmd_capture_current()
    snap = box / "manager-accounts/acct-b/.credentials.json"
    os.utime(snap, (1_000_000, 1_000_000))
    assert rot._cmd_drift_check() == 0
    assert snap.stat().st_mtime == 1_000_000  # no rewrite when already equal


def test_neither_command_emits_token_bytes(box, capsys):
    rot._cmd_capture_current()
    rot._cmd_drift_check()
    out = capsys.readouterr()
    assert "tok-B-LIVE" not in out.out + out.err
    assert "rt-tok-B-LIVE" not in out.out + out.err


def test_cli_dispatches_both_subcommands(box, monkeypatch):
    seen = []
    monkeypatch.setattr(rot, "_cmd_capture_current", lambda: seen.append("capture") or 0)
    monkeypatch.setattr(rot, "_cmd_drift_check", lambda: seen.append("drift") or 0)
    assert rot.main(["--capture-current"]) == 0
    assert rot.main(["--drift-check"]) == 0
    assert seen == ["capture", "drift"]


def test_existing_switch_and_next_paths_are_untouched(box, monkeypatch):
    """The additive seam must not change the pre-existing CLI contract."""
    calls = []
    monkeypatch.setattr(rot, "_cmd_list", lambda: calls.append("list") or 0)
    monkeypatch.setattr(rot, "_cmd_switch", lambda n: calls.append(f"switch:{n}") or 0)
    monkeypatch.setattr(rot, "_cmd_next", lambda: calls.append("next") or 0)
    rot.main(["--list"])
    rot.main(["--switch", "acct-a"])
    rot.main(["--next"])
    assert calls == ["list", "switch:acct-a", "next"]


def test_drift_check_captures_when_only_the_refresh_token_rotated(box):
    """The live-incident shape: access token unchanged, refresh token rotated.

    An accessToken-only comparison reads "in sync" and leaves a DEAD refresh token in the
    snapshot — exactly what broke the operator's login on 2026-08-10.
    """
    snap = box / "manager-accounts/acct-b/.credentials.json"
    snap.write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": "tok-SAME", "refreshToken": "rt-OLD"}}))
    (box / ".credentials.json").write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": "tok-SAME", "refreshToken": "rt-NEW"}}))
    assert rot._cmd_drift_check() == 0
    assert json.loads(snap.read_text())["claudeAiOauth"]["refreshToken"] == "rt-NEW"


def test_capture_rolls_the_outgoing_snapshot_aside(box):
    """A capture must never be the operation that loses a usable credential."""
    rot._cmd_capture_current()
    prev = box / "manager-accounts/acct-b/.credentials.json.prev"
    assert prev.is_file()
    assert json.loads(prev.read_text())["claudeAiOauth"]["accessToken"] == "tok-B-OLD"
    assert stat.S_IMODE(prev.stat().st_mode) == 0o600


def test_drift_check_reports_a_failed_capture_without_failing_the_hook(box, monkeypatch, capsys):
    monkeypatch.setattr(rot, "_cmd_capture_current", lambda: 1)
    assert rot._cmd_drift_check() == 0          # a hook must never fail
    assert "capture FAILED" in capsys.readouterr().err  # but it must be visible


def _creds_gen(token: str, expires_at: int) -> str:
    return json.dumps({"claudeAiOauth": {
        "accessToken": token, "refreshToken": f"rt-{token}", "expiresAt": expires_at}})


def test_capture_refuses_to_regress_a_newer_snapshot(box):
    """MONOTONE, as the plan words it: an OLDER live file never stamps over a NEWER
    snapshot (the previous code only skipped byte-identical content — idempotency, not
    monotonicity)."""
    snap = box / "manager-accounts/acct-b/.credentials.json"
    snap.write_text(_creds_gen("tok-B", 2_000_000_000_000))          # newer generation
    (box / ".credentials.json").write_text(_creds_gen("tok-B", 1_000_000_000_000))  # older
    assert rot._cmd_capture_current() != 0
    assert json.loads(snap.read_text())["claudeAiOauth"]["expiresAt"] == 2_000_000_000_000


def test_capture_allows_a_newer_live_generation(box):
    snap = box / "manager-accounts/acct-b/.credentials.json"
    snap.write_text(_creds_gen("tok-B", 1_000_000_000_000))
    (box / ".credentials.json").write_text(_creds_gen("tok-B-NEW", 2_000_000_000_000))
    assert rot._cmd_capture_current() == 0
    assert json.loads(snap.read_text())["claudeAiOauth"]["accessToken"] == "tok-B-NEW"


def test_marker_resolved_capture_is_recoverable(box):
    """Accepted residual: a refreshed token no longer matches its snapshot, so identity
    falls back to the marker — indistinguishable from an out-of-band login as another
    account. Capture must therefore PROCEED (it is the primary use case) while leaving
    the prior credentials recoverable in `.prev`."""
    (box / ".credentials.json").write_text(_creds("tok-UNTRACKED"))  # matches no snapshot
    (box / ".active-account").write_text("acct-b")
    assert rot._cmd_capture_current() == 0
    snap = box / "manager-accounts/acct-b/.credentials.json"
    assert json.loads(snap.read_text())["claudeAiOauth"]["accessToken"] == "tok-UNTRACKED"
    prev = json.loads((snap.parent / (snap.name + ".prev")).read_text())
    assert prev["claudeAiOauth"]["accessToken"] == "tok-B-OLD"  # one-generation recovery


def test_capture_accepts_an_org_matched_identity(box):
    """An org-matched (old-format, marker-less) account resolves without the marker."""
    (box / "manager-accounts/acct-b/.credentials.json").write_text(_creds("tok-B-OLD", "org-42"))
    (box / ".credentials.json").write_text(_creds("tok-B-ROTATED", "org-42"))
    assert rot._cmd_capture_current() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-ROTATED"
