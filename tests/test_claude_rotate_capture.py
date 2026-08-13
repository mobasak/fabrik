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
import time
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


def _verified_as_active(monkeypatch):
    """Identity-gate seams (shipped 2026-08-13): the live token verifies as the account the
    marker names — the pre-gate tests' implicit assumption, now explicit."""
    monkeypatch.setattr(rot, "_live_email", lambda **kw: "acct@example.com")
    monkeypatch.setattr(rot, "_store_for_email",
                        lambda email, accounts: next(
                            (a for a in accounts if a.name == "acct-b"), None))


def test_drift_check_captures_when_the_token_diverged(box, monkeypatch):
    _verified_as_active(monkeypatch)
    assert rot._cmd_drift_check() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-LIVE"


def test_drift_check_is_a_noop_when_in_sync(box, monkeypatch):
    _verified_as_active(monkeypatch)
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


def test_drift_check_captures_when_only_the_refresh_token_rotated(box, monkeypatch):
    _verified_as_active(monkeypatch)
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
    _verified_as_active(monkeypatch)
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


# --- Stale-snapshot rotation guard (live incident 2026-08-10 14:37) ------------------------


def _oauth_blob(access_h: float, refresh_h: float) -> bytes:
    """A credentials payload whose access/refresh tokens expire in N hours (negative = past)."""
    now = time.time()
    return json.dumps(
        {
            "claudeAiOauth": {
                "accessToken": "redacted",
                "refreshToken": "redacted",
                "expiresAt": int((now + access_h * 3600) * 1000),
                "refreshTokenExpiresAt": int((now + refresh_h * 3600) * 1000),
            }
        }
    ).encode()


def test_a_month_old_snapshot_is_refused_as_a_rotation_target():
    """THE incident: mob@ hit its weekly wall, the picker chose can@ (never walled), and can@'s
    snapshot was a month old. The switch installed a dead credential and logged the operator out
    mid-session with 'OAuth session expired and could not be refreshed'."""
    reason = rot._stale_snapshot_reason(_oauth_blob(-720, -10))
    assert reason is not None and "refresh token expired" in reason


def test_a_lapsed_access_token_is_not_disqualifying():
    """REVERSED after review. I first refused any snapshot whose access token had expired, on the
    single-use-refresh-token argument. That made rotation structurally impossible exactly when it
    is needed: only the ACTIVE account self-refreshes, so every standby's 8-12h token has lapsed
    long before a weekly wall arrives ~2.x days later — `healthy_sibling()` would return None
    permanently. It is a ranking preference now, not a filter. The live incident is still caught
    by the refresh-token clause alone: can@'s month-old snapshot had an EXPIRED refresh token,
    which is precisely what "could not be refreshed" means."""
    assert rot._stale_snapshot_reason(_oauth_blob(-50, 600)) is None  # ob@'s real shape


def test_a_fresh_snapshot_is_allowed():
    assert rot._stale_snapshot_reason(_oauth_blob(8, 700)) is None


def test_a_token_expiring_inside_the_margin_is_still_a_valid_target():
    """Same reversal: it will simply refresh on first use, which is the standby's normal path."""
    assert rot._stale_snapshot_reason(_oauth_blob(0.03, 700)) is None


def test_an_expired_refresh_token_is_the_real_disqualifier():
    """The clause that actually caught the incident, kept and pinned on its own."""
    reason = rot._stale_snapshot_reason(_oauth_blob(-720, -10))
    assert reason is not None and "refresh token expired" in reason


def test_the_operator_can_override_a_stale_target(monkeypatch):
    monkeypatch.setenv("CLAUDE_ROTATE_ALLOW_STALE", "1")
    assert rot._stale_snapshot_reason(_oauth_blob(-720, -10)) is None


def test_a_snapshot_with_no_expiry_metadata_is_refused_not_assumed_good():
    """Cross-layer divergence: the picker treated a missing expiry field as unusable while the
    installer treated it as allowed. Two layers disagreeing about the same credential is the exact
    class that logged the operator out, and 'we cannot prove it authenticates' must fail CLOSED —
    refusing costs a wait, allowing costs a re-login."""
    blob = json.dumps({"claudeAiOauth": {"accessToken": "x", "refreshToken": "y"}}).encode()
    reason = rot._stale_snapshot_reason(blob)
    assert reason is not None and "no expiry metadata" in reason


def test_the_override_still_admits_a_metadata_less_snapshot(monkeypatch):
    monkeypatch.setenv("CLAUDE_ROTATE_ALLOW_STALE", "1")
    blob = json.dumps({"claudeAiOauth": {"accessToken": "x", "refreshToken": "y"}}).encode()
    assert rot._stale_snapshot_reason(blob) is None


# --- The guard's WIRING, not just its helper (review finding F2) ----------------------------
# Every earlier test called `_stale_snapshot_reason` directly, so deleting the call from
# `_activate_snapshot` left the suite green — i.e. the entire fix could be removed without a
# single failure, while the commit claimed "ANY caller is covered".


def _rotation_sandbox(tmp_path, accounts):
    """A real snapshot tree; `accounts` is {name: hours-until-access-expiry or None-for-dead}."""
    import time as _t
    now = _t.time()
    (tmp_path / "manager-accounts").mkdir()
    for name, (access_h, refresh_h) in accounts.items():
        d = tmp_path / "manager-accounts" / name
        d.mkdir()
        d.joinpath(".credentials.json").write_bytes(json.dumps({"claudeAiOauth": {
            "accessToken": f"tok-{name}", "refreshToken": f"r-{name}",
            "expiresAt": int((now + access_h * 3600) * 1000),
            "refreshTokenExpiresAt": int((now + refresh_h * 3600) * 1000)}}).encode())
    (tmp_path / ".credentials.json").write_bytes(json.dumps({"claudeAiOauth": {
        "accessToken": "tok-live", "refreshToken": "r-live",
        "expiresAt": int((now + 5 * 3600) * 1000),
        "refreshTokenExpiresAt": int((now + 700 * 3600) * 1000)}}).encode())
    rot.CLAUDE_DIR = tmp_path
    rot.ACTIVE_CREDS = tmp_path / ".credentials.json"
    rot.ACCOUNTS_DIR = tmp_path / "manager-accounts"
    rot.ACTIVE_MARKER = tmp_path / ".active-account"
    rot.BACKUP_CREDS = tmp_path / ".credentials.json.prev"
    rot.ROTATE_LOCK = tmp_path / ".rotate.lock"
    return tmp_path / ".credentials.json"


def test_activate_snapshot_itself_refuses_a_dead_target(tmp_path):
    """Pins the CALL SITE: deleting the guard from `_activate_snapshot` must red this."""
    live = _rotation_sandbox(tmp_path, {"dead": (-720, -10)})
    before = live.read_bytes()
    assert rot._activate_snapshot(target=tmp_path / "manager-accounts" / "dead") is None
    assert live.read_bytes() == before, "a refused activation must not touch the live credentials"


def test_activate_snapshot_still_installs_a_good_target(tmp_path):
    """Non-vacuity: proves the refusal is selective, not a blanket 'refuse everything' that would
    silently disable rotation — the mirror failure of the bug this guard exists to fix."""
    live = _rotation_sandbox(tmp_path, {"good": (8, 700)})
    before = live.read_bytes()
    assert rot._activate_snapshot(target=tmp_path / "manager-accounts" / "good") == "good"
    assert live.read_bytes() != before


def test_a_dead_first_candidate_does_not_block_a_healthy_later_one(tmp_path):
    """Review finding F1: the selector returned the FIRST tokened snapshot without consulting the
    guard, the installer refused it, and the caller broke out — so a fresh standby one index later
    was never tried. Pre-fix that logged the operator out; post-fix it rotated NOWHERE."""
    live = _rotation_sandbox(tmp_path, {"a-dead": (-720, -10), "b-good": (8, 700)})
    assert rot._rotate_active_account() == "b-good"
    assert b"tok-b-good" in live.read_bytes()


def test_a_snapshot_with_no_refresh_token_is_refused_by_both_layers():
    """Cross-layer divergence (F6): the picker refused it, the installer allowed it. Once the
    access token lapses there is no way back, and every non-picker path — --switch, --next,
    run_claude's rotation, and the VPS fleet where no picker exists — takes the installer."""
    blob = json.dumps({"claudeAiOauth": {"accessToken": "x", "expiresAt": 9_999_999_999_000}}).encode()
    reason = rot._stale_snapshot_reason(blob)
    assert reason is not None and "no refresh token" in reason


# ── identity gate (shipped 2026-08-13 after the mis-filing incident) ───────────


def test_gate_retargets_capture_to_the_verified_store(box, monkeypatch, capsys):
    """Marker says acct-b but the LIVE token verifies as acct-a's owner → the capture must
    land in acct-a (the mis-filing class, inverted)."""
    monkeypatch.setattr(rot, "_live_email", lambda **kw: "owner-a@example.com")
    monkeypatch.setattr(rot, "_store_for_email",
                        lambda email, accounts: next(
                            (a for a in accounts if a.name == "acct-a"), None))
    assert rot._cmd_drift_check() == 0
    snap = json.loads((box / "manager-accounts/acct-a/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-LIVE"
    assert "RETARGETED" in capsys.readouterr().err


def test_gate_skips_when_identity_unverifiable(box, monkeypatch, capsys):
    monkeypatch.setattr(rot, "_live_email", lambda **kw: None)
    assert rot._cmd_drift_check() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-OLD", "no write on unverifiable"
    assert "skipped" in capsys.readouterr().err


def test_gate_skips_when_no_store_matches(box, monkeypatch, capsys):
    monkeypatch.setattr(rot, "_live_email", lambda **kw: "stranger@example.com")
    monkeypatch.setattr(rot, "_store_for_email", lambda email, accounts: None)
    assert rot._cmd_drift_check() == 0
    snap = json.loads((box / "manager-accounts/acct-b/.credentials.json").read_text())
    assert snap["claudeAiOauth"]["accessToken"] == "tok-B-OLD"
    assert "no store for live account" in capsys.readouterr().err


def test_store_for_email_prefix_mapping(tmp_path):
    a = tmp_path / "ob-ocoron-com-s-organization"
    a.mkdir()
    b = tmp_path / "sarp-ocoron-com-s-organization"
    b.mkdir()
    assert rot._store_for_email("ob@ocoron.com", [a, b]) == a
    assert rot._store_for_email("sarp@ocoron.com", [a, b]) == b
    assert rot._store_for_email("zz@ocoron.com", [a, b]) is None
    c = tmp_path / "ob-other-org"
    c.mkdir()
    assert rot._store_for_email("ob@ocoron.com", [a, b, c]) is None, "ambiguity never guessed"
