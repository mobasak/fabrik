"""Unit tests for fabrik.orchestrator.vultr_drill (Phase 3a, `bare`).

VultrClient is a mock; SSH probe + state + drill-log are redirected to tmp.
The critical invariant under test: the instance is ALWAYS destroyed unless the
drill failed AND keep_on_failure is set.
"""

from unittest.mock import MagicMock

import pytest

from fabrik.drivers.vultr import VultrError
from fabrik.orchestrator import vultr_drill, vultr_state


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(vultr_state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(vultr_drill, "DRILL_LOG", tmp_path / "drills.jsonl")
    monkeypatch.setattr(vultr_drill, "_ssh_probe", lambda ip, **kw: True)
    yield


def _mock_client(monthly=10.0):
    c = MagicMock()
    c.list_plans.return_value = [
        {"id": "vc2-1c-0.5gb-v6", "monthly_cost": 2.5, "locations": ["lax"]},  # v6 — skipped
        {"id": "vc2-1c-2gb", "monthly_cost": monthly, "locations": ["lax"]},
        {"id": "vc2-2c-4gb", "monthly_cost": monthly + 10.0, "locations": ["lax"]},
        {"id": "vc2-1c-1gb", "monthly_cost": 6.0, "locations": ["ord"]},        # wrong region
    ]
    c.create_instance.return_value = ("instance", {"id": "i-123"})
    c.wait_for_active.return_value = {"main_ip": "1.2.3.4", "status": "active"}
    return c


def test_estimate_cost_rounds_up_to_hour():
    assert vultr_drill.estimate_cost(672.0, 60) == 1.0       # $1/hr, min 1h
    assert vultr_drill.estimate_cost(672.0, 3601) == 2.0     # 2h


def test_cheapest_ipv4_plan_skips_v6_and_wrong_region():
    plan, cost = vultr_drill.cheapest_ipv4_plan(_mock_client(), "lax")
    assert plan == "vc2-1c-2gb" and cost == 10.0  # cheapest non-v6 in lax


def test_dry_run_creates_nothing():
    c = _mock_client()
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], dry_run=True, client=c)
    assert rep["dry_run"] is True and rep["plan"] == "vc2-1c-2gb"
    c.create_instance.assert_not_called()


def test_happy_path_creates_then_destroys():
    c = _mock_client()
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], client=c)
    assert rep["success"] is True
    assert rep["checks"]["destroyed"] is True
    c.create_instance.assert_called_once()
    c.destroy.assert_called_once_with("instance", "i-123")
    # state record marked destroyed
    assert vultr_state.get_instance(rep["name"])["destroyed_at"] is not None


def test_failure_still_destroys_no_orphan():
    c = _mock_client()
    c.wait_for_active.side_effect = VultrError("never came up")
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], client=c)
    assert rep["success"] is False
    assert "never came up" in rep["error"]
    c.destroy.assert_called_once_with("instance", "i-123")   # destroyed despite failure
    assert rep["checks"]["destroyed"] is True


def test_keep_on_failure_leaves_instance():
    c = _mock_client()
    c.wait_for_active.side_effect = VultrError("boom")
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], keep_on_failure=True, client=c)
    assert rep["success"] is False
    c.destroy.assert_not_called()                            # left for operator
    assert rep["checks"]["kept_for_debug"] is True


def test_max_cost_guard_refuses_before_create():
    c = _mock_client(monthly=720.0)  # ~$1.07/hr * 4h ≈ $4.29 est
    with pytest.raises(VultrError, match="exceeds --max-cost"):
        vultr_drill.drill("bare", sshkey_ids=["k"], max_cost=0.50, client=c)
    c.create_instance.assert_not_called()


def test_unknown_kind_raises():
    with pytest.raises(NotImplementedError):
        vultr_drill.drill("wat", sshkey_ids=["k"], client=_mock_client())


def test_spoke_dispatch_runs_validate_then_destroys(monkeypatch):
    c = _mock_client()
    captured = {}

    def fake_validate(ip, name, *, g0_smoke=False):
        captured["ip"] = ip
        return {"ssh_ready": True, "bootstrap": True, "verify": True, "success": True}

    monkeypatch.setattr(vultr_drill, "_validate_spoke", fake_validate)
    rep = vultr_drill.drill("spoke", sshkey_ids=["k"], client=c)
    assert rep["success"] is True
    assert rep["plan"] == "vc2-1c-2gb"            # fixed spoke plan
    assert captured["ip"] == "1.2.3.4"
    c.destroy.assert_called_once_with("instance", "i-123")  # always destroyed


def test_validate_hub_passes_safety_flags(monkeypatch):
    """``_validate_hub`` MUST invoke ``bootstrap-hub.sh`` with both
    ``--skip-mesh`` and ``--skip-services``. Without ``--skip-mesh`` the
    drill droplet (restoring vps1's real wg keypair) would handshake with
    vps2/vps3 and overwrite their peer endpoints — breaking the live mesh.
    Without ``--skip-services`` step_13 starts the backrest container which
    writes to B2 with vps1's restic identity. Lock the contract here so a
    future refactor that drops either flag fails loudly.
    """
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(vultr_drill, "_wait_ssh", lambda *_a, **_k: True)
    monkeypatch.setattr(
        vultr_drill,
        "_run_script",
        lambda argv, *a, **k: captured.setdefault("argv", argv) and 0 or 0,
    )
    vultr_drill._validate_hub("9.9.9.9", "dr-drill-hub-fake")
    argv = captured["argv"]
    assert "--skip-mesh" in argv, "MUST pass --skip-mesh to bootstrap-hub.sh"
    assert "--skip-services" in argv, "MUST pass --skip-services to bootstrap-hub.sh"
    # Hub DR Drill #1 finding (2026-06-14): preflight check #6 is over-conservative
    # (tests B2 from operator, not target). Drill MUST skip it so a drill from a
    # B2-unreachable network doesn't burn ~10 min on retries.
    assert "--skip-local-b2-check" in argv, "MUST pass --skip-local-b2-check"
    # And the target must be root@<ip> as the last positional.
    assert argv[-1] == "root@9.9.9.9"


def test_spoke_failed_verify_still_destroys(monkeypatch):
    c = _mock_client()
    monkeypatch.setattr(
        vultr_drill, "_validate_spoke",
        lambda ip, name: {"bootstrap": True, "verify": False, "success": False},
    )
    rep = vultr_drill.drill("spoke", sshkey_ids=["k"], client=c)
    assert rep["success"] is False
    c.destroy.assert_called_once()                # no orphan even when verify fails


# ── PR3: partial-G0 creds-copy smoke (opt-in) ──────────────────────────────


def test_g0_smoke_pass_when_claude_p_exit0(monkeypatch):
    from fabrik.orchestrator import vultr_drill as d

    # local creds present
    monkeypatch.setattr(d.Path, "home", staticmethod(lambda: __import__("pathlib").Path("/tmp")))
    creds = d.Path("/tmp") / ".claude" / ".credentials.json"
    creds.parent.mkdir(parents=True, exist_ok=True)
    creds.write_text("{}")

    calls = []

    class _R:
        def __init__(self, stdout="", rc=0):
            self.stdout = stdout
            self.returncode = rc

    def fake_ssh(ip, cmd, *, timeout=60):
        calls.append(cmd)
        if "sha256sum" in cmd:
            return _R(stdout="abc123  /home/ozgur/.claude/.credentials.json")
        if cmd.startswith("claude -p"):
            return _R(stdout="RC=0")
        return _R()

    monkeypatch.setattr(d, "_ssh_ozgur_drill", fake_ssh)
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: _R(rc=0))  # scp ok

    res = d._g0_creds_smoke("1.2.3.4")
    assert res["attempted"] is True
    assert res["claude_p_rc"] == 0
    assert res["pass"] is True
    assert "refresh-token rotation race is NOT exercised" in res["note"]


def test_g0_smoke_fail_when_claude_p_nonzero(monkeypatch):
    from fabrik.orchestrator import vultr_drill as d

    monkeypatch.setattr(d.Path, "home", staticmethod(lambda: __import__("pathlib").Path("/tmp")))
    creds = d.Path("/tmp") / ".claude" / ".credentials.json"
    creds.parent.mkdir(parents=True, exist_ok=True)
    creds.write_text("{}")

    class _R:
        def __init__(self, stdout="", rc=0):
            self.stdout = stdout
            self.returncode = rc

    def fake_ssh(ip, cmd, *, timeout=60):
        if "sha256sum" in cmd:
            return _R(stdout="h  x")
        if cmd.startswith("claude -p"):
            return _R(stdout="RC=1")  # auth rejected
        return _R()

    monkeypatch.setattr(d, "_ssh_ozgur_drill", fake_ssh)
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: _R(rc=0))
    res = d._g0_creds_smoke("1.2.3.4")
    assert res["immediate_auth_ok"] is False and res["pass"] is False


def test_g0_smoke_skipped_when_no_local_creds(monkeypatch, tmp_path):
    from fabrik.orchestrator import vultr_drill as d

    monkeypatch.setattr(d.Path, "home", staticmethod(lambda: tmp_path))  # no .claude here
    res = d._g0_creds_smoke("1.2.3.4")
    assert res == {"attempted": False, "reason": "no local ~/.claude/.credentials.json to copy"}
