"""Coverage sweep for fabrik.orchestrator.vultr_drill (hermetic: no network/ssh/home)."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from fabrik.drivers.vultr import VultrError
from fabrik.orchestrator import vultr_drill as d
from fabrik.orchestrator import vultr_state


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(vultr_state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(d, "DRILL_LOG", tmp_path / "logs" / "drills.jsonl")
    monkeypatch.setattr(d, "FABRIK_ROOT", tmp_path)
    monkeypatch.setattr(d.time, "sleep", lambda s: None)


def _client(monthly=10.0):
    c = MagicMock()
    c.list_plans.return_value = [
        {"id": "vc2-1c-2gb", "monthly_cost": monthly, "locations": ["lax"]},
        {"id": "vc2-4c-8gb", "monthly_cost": monthly * 4, "locations": ["lax"]},
    ]
    c.create_instance.return_value = ("instance", {"id": "i-1"})
    c.wait_for_active.return_value = {"main_ip": "1.2.3.4"}
    return c


# ── estimate_cost / plans ──
def test_estimate_cost_min_one_hour_and_exact_boundary():
    assert d.estimate_cost(672.0, 0) == 1.0
    assert d.estimate_cost(672.0, 3600) == 1.0
    assert d.estimate_cost(672.0, 3601) == 2.0


def test_estimate_cost_rounds_to_four_places():
    assert d.estimate_cost(10.0, 3600) == round(10.0 / 672, 4)


def test_cheapest_plan_none_available_raises():
    c = MagicMock()
    c.list_plans.return_value = [{"id": "a-v6", "monthly_cost": 1, "locations": ["lax"]}]
    with pytest.raises(VultrError, match="no vc2 IPv4 plan"):
        d.cheapest_ipv4_plan(c, "lax")


def test_cheapest_plan_missing_locations_key_is_skipped():
    c = MagicMock()
    c.list_plans.return_value = [{"id": "x", "monthly_cost": 1}]
    with pytest.raises(VultrError):
        d.cheapest_ipv4_plan(c, "lax")


def test_cheapest_plan_passes_plan_type():
    c = MagicMock()
    c.list_plans.return_value = [{"id": "p", "monthly_cost": 3, "locations": ["lax"]}]
    assert d.cheapest_ipv4_plan(c, "lax", "vhf") == ("p", 3)
    c.list_plans.assert_called_once_with("vhf")


@pytest.mark.parametrize(
    "kind,plan",
    [
        ("spoke", d.SPOKE_DRILL_PLAN),
        ("hub", d.HUB_DRILL_PLAN),
        ("spoke-restore", d.SPOKE_DRILL_PLAN),
    ],
)
def test_resolve_plan_fixed_kinds(kind, plan):
    got, cost = d._resolve_plan(_client(), kind, "lax")
    assert got == plan and cost > 0


def test_resolve_plan_bare_uses_cheapest():
    assert d._resolve_plan(_client(), "bare", "lax") == ("vc2-1c-2gb", 10.0)


def test_resolve_plan_unknown_kind():
    with pytest.raises(NotImplementedError):
        d._resolve_plan(_client(), "nope", "lax")


def test_plan_monthly_cost_missing_plan():
    with pytest.raises(VultrError, match="not found"):
        d._plan_monthly_cost(_client(), "ghost")


# ── _ssh_probe ──
def test_ssh_probe_success_first_try(monkeypatch):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="ok\n")

    monkeypatch.setattr(d.subprocess, "run", run)
    assert d._ssh_probe("1.1.1.1") is True
    assert len(calls) == 1 and "root@1.1.1.1" in calls[0] and "BatchMode=yes" in calls[0]


def test_ssh_probe_retries_then_succeeds(monkeypatch):
    results = iter(
        [
            SimpleNamespace(returncode=255, stdout=""),
            SimpleNamespace(returncode=0, stdout="nothing"),  # rc 0 but no "ok"
            SimpleNamespace(returncode=0, stdout="ok"),
        ]
    )
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: next(results))
    assert d._ssh_probe("1.1.1.1", attempts=5) is True


def test_ssh_probe_exhausts_attempts_and_swallows_errors(monkeypatch):
    n = {"c": 0}

    def run(*a, **k):
        n["c"] += 1
        raise subprocess.TimeoutExpired("ssh", 15) if n["c"] % 2 else OSError("x")

    monkeypatch.setattr(d.subprocess, "run", run)
    assert d._ssh_probe("1.1.1.1", attempts=4, interval=0) is False
    assert n["c"] == 4


def test_ssh_probe_zero_attempts_false():
    assert d._ssh_probe("1.1.1.1", attempts=0) is False


def test_wait_ssh_delegates_with_defaults(monkeypatch):
    seen = {}
    monkeypatch.setattr(d, "_ssh_probe", lambda ip, **kw: seen.update(ip=ip, **kw) or True)
    assert d._wait_ssh("2.2.2.2") is True
    assert seen == {"ip": "2.2.2.2", "attempts": 20, "interval": 6}


# ── _run_script ──
def test_run_script_returns_rc_and_writes_log(tmp_path, monkeypatch):
    def run(argv, stdout, stderr, timeout, check):
        stdout.write("hello")
        assert stderr == subprocess.STDOUT and timeout == 7 and check is False
        return SimpleNamespace(returncode=3)

    monkeypatch.setattr(d.subprocess, "run", run)
    log = tmp_path / "l.log"
    assert d._run_script(["x"], 7, log) == 3
    assert log.read_text() == "hello"


def test_run_script_timeout_is_124(tmp_path, monkeypatch):
    def run(*a, **k):
        raise subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(d.subprocess, "run", run)
    assert d._run_script(["x"], 1, tmp_path / "l") == 124


def test_run_script_oserror_is_127(tmp_path, monkeypatch):
    def run(*a, **k):
        raise OSError("no exec")

    monkeypatch.setattr(d.subprocess, "run", run)
    assert d._run_script(["x"], 1, tmp_path / "l") == 127


def test_run_script_unwritable_log_is_127(tmp_path):
    assert d._run_script(["x"], 1, tmp_path / "missing-dir" / "l") == 127


# ── _ssh_ozgur_drill ──
def test_ssh_ozgur_drill_argv_and_timeout(monkeypatch):
    seen = {}

    def run(argv, **kw):
        seen.update(argv=argv, **kw)
        return "r"

    monkeypatch.setattr(d.subprocess, "run", run)
    assert d._ssh_ozgur_drill("3.3.3.3", "ls", timeout=10) == "r"
    assert seen["argv"][-2:] == ["ozgur@3.3.3.3", "ls"]
    assert seen["timeout"] == 15 and seen["check"] is False


# ── _g0_creds_smoke (home redirected to tmp via a Path subclass) ──
def _home_at(monkeypatch, home):
    class _P(type(home)):
        @classmethod
        def home(cls):
            return home

    monkeypatch.setattr(d, "Path", _P)


def _with_creds(monkeypatch, tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    _home_at(monkeypatch, tmp_path)


def _R(stdout="", rc=0):
    return SimpleNamespace(stdout=stdout, returncode=rc)


def test_g0_scp_failure_reports_rc(tmp_path, monkeypatch):
    _with_creds(monkeypatch, tmp_path)
    monkeypatch.setattr(d, "_ssh_ozgur_drill", lambda *a, **k: _R())
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: _R(rc=5))
    assert d._g0_creds_smoke("1.1.1.1") == {
        "attempted": True,
        "pass": False,
        "reason": "scp failed (rc=5)",
    }


def test_g0_timeout_is_reported_not_raised(tmp_path, monkeypatch):
    _with_creds(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("ssh", 1)

    monkeypatch.setattr(d, "_ssh_ozgur_drill", boom)
    res = d._g0_creds_smoke("1.1.1.1")
    assert res["attempted"] is True and res["pass"] is False
    assert res["reason"].startswith("smoke error")


def test_g0_detects_rotation_and_missing_rc_marker(tmp_path, monkeypatch):
    _with_creds(monkeypatch, tmp_path)
    hashes = iter(["aaa  f", "bbb  f"])

    def ssh(ip, cmd, *, timeout=60):
        if "sha256sum" in cmd:
            return _R(next(hashes))
        if cmd.startswith("claude -p"):
            return _R("garbage")  # no RC= token -> 127
        return _R()

    monkeypatch.setattr(d, "_ssh_ozgur_drill", ssh)
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: _R())
    res = d._g0_creds_smoke("1.1.1.1")
    assert res["claude_p_rc"] == 127 and res["pass"] is False
    assert res["spoke_creds_rotated_on_first_use"] is True


def test_g0_unrotated_creds(tmp_path, monkeypatch):
    _with_creds(monkeypatch, tmp_path)

    def ssh(ip, cmd, *, timeout=60):
        if "sha256sum" in cmd:
            return _R("same  f")
        return _R("RC=0") if cmd.startswith("claude -p") else _R()

    monkeypatch.setattr(d, "_ssh_ozgur_drill", ssh)
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: _R())
    res = d._g0_creds_smoke("1.1.1.1")
    assert res["spoke_creds_rotated_on_first_use"] is False and res["pass"] is True


# ── _validate_spoke ──
def test_validate_spoke_full_success(monkeypatch):
    runs = []
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: True)
    monkeypatch.setattr(d, "_run_script", lambda argv, t, log: runs.append((argv, t, log)) or 0)
    out = d._validate_spoke("9.9.9.9", "n1")
    assert out["success"] is True and out["bootstrap"] and out["verify"]
    boot, verify = runs
    assert "--skip-mesh" in boot[0] and "--skip-dns" in boot[0]
    assert boot[0][-2:] == ["root@9.9.9.9", d.DRILL_SPOKE_NAME]
    assert verify[0][1:] == ["--verify", "ozgur@9.9.9.9", d.DRILL_SPOKE_NAME]
    assert verify[1] == d._VERIFY_TIMEOUT and boot[1] == d._BOOTSTRAP_TIMEOUT
    assert boot[2].name == "drill-n1.bootstrap.log" and verify[2].name == "drill-n1.verify.log"


def test_validate_spoke_bootstrap_fail_skips_verify(monkeypatch):
    runs = []
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: False)
    monkeypatch.setattr(d, "_run_script", lambda *a: runs.append(a) or 2)
    out = d._validate_spoke("9.9.9.9", "n")
    assert len(runs) == 1
    assert out["success"] is False and out["bootstrap_rc"] == 2 and "verify" not in out
    assert out["ssh_ready"] is False


def test_validate_spoke_verify_fail(monkeypatch):
    rcs = iter([0, 1])
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: True)
    monkeypatch.setattr(d, "_run_script", lambda *a: next(rcs))
    out = d._validate_spoke("9.9.9.9", "n", g0_smoke=True)
    assert out["success"] is False and out["verify_rc"] == 1
    assert "g0_smoke" not in out  # only runs after a passing verify


@pytest.mark.parametrize("flag,present", [(True, True), (False, False)])
def test_validate_spoke_g0_smoke_opt_in(monkeypatch, flag, present):
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: True)
    monkeypatch.setattr(d, "_run_script", lambda *a: 0)
    monkeypatch.setattr(d, "_g0_creds_smoke", lambda ip: {"pass": False})
    out = d._validate_spoke("9.9.9.9", "n", g0_smoke=flag)
    assert ("g0_smoke" in out) is present
    assert out["success"] is True  # a failing smoke never flips success


# ── _validate_hub / _validate_spoke_restore result shape ──
def test_validate_hub_result_fields(monkeypatch):
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: False)
    seen = {}
    monkeypatch.setattr(d, "_run_script", lambda argv, t, log: seen.update(t=t, log=log) or 4)
    out = d._validate_hub("8.8.8.8", "hubn")
    assert out["success"] is False and out["bootstrap_rc"] == 4 and out["ssh_ready"] is False
    assert out["cf_drill_zone"] == d.CF_DRILL_ZONE_NAME
    assert out["le_staging_test_host"] == d.LE_STAGING_TEST_HOSTNAME
    assert seen["t"] == d._HUB_BOOTSTRAP_TIMEOUT
    assert seen["log"].name == "drill-hubn.bootstrap.log"


def test_validate_hub_zone_args_are_paired(monkeypatch):
    seen = {}
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: True)
    monkeypatch.setattr(d, "_run_script", lambda argv, t, log: seen.update(a=argv) or 0)
    d._validate_hub("8.8.8.8", "h")
    a = seen["a"]
    assert a[a.index("--cf-zone-id") + 1] == d.CF_DRILL_ZONE_ID
    assert a[a.index("--cf-zone-name") + 1] == d.CF_DRILL_ZONE_NAME
    assert a[a.index("--drill-test-le-staging") + 1] == d.LE_STAGING_TEST_HOSTNAME


def test_validate_spoke_restore_result_fields(monkeypatch):
    seen = {}
    monkeypatch.setattr(d, "_wait_ssh", lambda ip: True)
    monkeypatch.setattr(d, "_run_script", lambda argv, t, log: seen.update(t=t) or 0)
    out = d._validate_spoke_restore("8.8.8.8", "sr")
    assert out["success"] is True and out["restored_spoke"] == d.SPOKE_RESTORE_DRILL_SPOKE
    assert seen["t"] == d._SPOKE_RESTORE_BOOTSTRAP_TIMEOUT


# ── write_report ──
def test_write_report_appends_sorted_json_lines_and_creates_dir():
    d.write_report({"b": 1, "a": 2})
    d.write_report({"c": 3})
    lines = d.DRILL_LOG.read_text().splitlines()
    assert lines[0] == '{"a": 2, "b": 1}' and json.loads(lines[1]) == {"c": 3}


def test_write_report_swallows_oserror(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(d, "DRILL_LOG", blocker / "sub" / "l.jsonl")
    d.write_report({"a": 1})  # must not raise


# ── drill() ──
def test_drill_dry_run_fields_and_no_state():
    c = _client()
    rep = d.drill("spoke", sshkey_ids=["k"], dry_run=True, client=c, region="ord")
    assert rep["dry_run"] is True and rep["region"] == "ord" and rep["plan"] == d.SPOKE_DRILL_PLAN
    assert rep["cost_estimate_usd"] == d.estimate_cost(10.0, 3600)
    assert rep["name"].startswith("dr-drill-spoke-")
    assert not d.DRILL_LOG.exists()
    c.create_instance.assert_not_called()


@pytest.mark.parametrize(
    "kind,secs", [("bare", 4 * 3600), ("spoke", 3600), ("hub", 7200), ("spoke-restore", 3600)]
)
def test_drill_cost_horizon_per_kind(kind, secs):
    rep = d.drill(kind, sshkey_ids=[], dry_run=True, client=_client())
    assert rep["cost_estimate_usd"] == d.estimate_cost(rep["monthly_cost"], secs)


def test_drill_max_cost_boundary_equal_is_allowed():
    est = d.estimate_cost(10.0, 3600)
    rep = d.drill("spoke", sshkey_ids=[], dry_run=True, max_cost=est, client=_client())
    assert rep["dry_run"] is True


def test_drill_unknown_kind_before_client_created(monkeypatch):
    monkeypatch.setattr(d, "VultrClient", MagicMock(side_effect=AssertionError("client built")))
    with pytest.raises(NotImplementedError):
        d.drill("zzz", sshkey_ids=[])


def test_drill_default_client_constructed(monkeypatch):
    c = _client()
    monkeypatch.setattr(d, "VultrClient", lambda: c)
    rep = d.drill("bare", sshkey_ids=[], dry_run=True)
    assert rep["plan"] == "vc2-1c-2gb"


def test_drill_bare_records_state_and_report_log(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda ip, **kw: True)
    c = _client()
    rep = d.drill("bare", sshkey_ids=["k1"], client=c)
    kw = c.create_instance.call_args.kwargs
    assert kw["sshkey_ids"] == ["k1"] and kw["tags"] == ["fabrik-drill", "disposable"]
    assert kw["hostname"] == kw["label"] == rep["name"] and kw["region"] == "lax"
    c.wait_for_active.assert_called_once_with("instance", "i-1", timeout=180)
    rec = vultr_state.get_instance(rep["name"])
    assert rec["mode"] == "disposable" and rec["drill_kind"] == "bare"
    assert rec["vultr_id"] == "i-1" and rec["destroyed_at"]
    logged = json.loads(d.DRILL_LOG.read_text().splitlines()[-1])
    assert logged["name"] == rep["name"] and logged["success"] is True
    assert set(rep["step_durations"]) == {"provision_to_ready", "validate"}


def test_drill_bare_no_ip_is_unreachable_but_destroyed(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda *a, **k: pytest.fail("probe without ip"))
    c = _client()
    c.wait_for_active.return_value = {"main_ip": ""}
    rep = d.drill("bare", sshkey_ids=[], client=c)
    assert rep["success"] is False and rep["checks"]["ssh_reachable"] is False
    c.destroy.assert_called_once()


def test_drill_bare_ssh_unreachable_fails_without_error(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda *a, **k: False)
    rep = d.drill("bare", sshkey_ids=[], client=_client())
    assert rep["success"] is False and rep["error"] is None


def test_drill_hub_and_spoke_restore_dispatch(monkeypatch):
    monkeypatch.setattr(d, "_validate_hub", lambda ip, n: {"success": True, "h": ip})
    monkeypatch.setattr(d, "_validate_spoke_restore", lambda ip, n: {"success": False, "s": ip})
    hub = d.drill("hub", sshkey_ids=[], client=_client())
    sr = d.drill("spoke-restore", sshkey_ids=[], client=_client())
    assert hub["success"] is True and hub["checks"]["h"] == "1.2.3.4"
    assert sr["success"] is False and sr["checks"]["s"] == "1.2.3.4"


def test_drill_spoke_passes_g0_flag(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        d, "_validate_spoke", lambda ip, n, *, g0_smoke=False: seen.update(g=g0_smoke) or {}
    )
    rep = d.drill("spoke", sshkey_ids=[], g0_smoke=True, client=_client())
    assert seen["g"] is True and rep["success"] is False  # no "success" key -> False


def test_drill_keep_on_failure_but_success_still_destroys(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda *a, **k: True)
    c = _client()
    rep = d.drill("bare", sshkey_ids=[], keep_on_failure=True, client=c)
    c.destroy.assert_called_once()
    assert "kept_for_debug" not in rep["checks"]


def test_drill_keep_on_unsuccessful_validation_keeps(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda *a, **k: False)
    c = _client()
    rep = d.drill("bare", sshkey_ids=[], keep_on_failure=True, client=c)
    c.destroy.assert_not_called()
    assert rep["checks"]["kept_for_debug"] is True


def test_drill_destroy_failure_is_recorded(monkeypatch):
    monkeypatch.setattr(d, "_ssh_probe", lambda *a, **k: True)
    c = _client()
    c.destroy.side_effect = VultrError("api down")
    rep = d.drill("bare", sshkey_ids=[], client=c)
    assert rep["checks"]["destroyed"] is False
    assert rep["error"] == " | destroy failed: api down"
    assert vultr_state.get_instance(rep["name"])["destroyed_at"] is None


def test_drill_destroy_failure_appends_to_existing_error():
    c = _client()
    c.wait_for_active.side_effect = VultrError("slow")
    c.destroy.side_effect = VultrError("api down")
    rep = d.drill("bare", sshkey_ids=[], client=c)
    assert rep["error"] == "slow | destroy failed: api down"


def test_drill_create_failure_leaves_no_destroy_and_logs():
    c = _client()
    c.create_instance.side_effect = VultrError("quota")
    rep = d.drill("bare", sshkey_ids=[], client=c)
    assert rep["success"] is False and rep["error"] == "quota" and rep["vultr_id"] is None
    c.destroy.assert_not_called()
    assert json.loads(d.DRILL_LOG.read_text())["error"] == "quota"


@pytest.mark.xfail(
    strict=True,
    reason="vultr_drill.py:541 reports kept_for_debug when create failed and nothing exists to keep",
)
def test_drill_create_failure_with_keep_flag_keeps_nothing():
    c = _client()
    c.create_instance.side_effect = VultrError("quota")
    rep = d.drill("bare", sshkey_ids=[], keep_on_failure=True, client=c)
    assert "kept_for_debug" not in rep["checks"]


def test_drill_plan_resolution_error_propagates_without_create():
    c = MagicMock()
    c.list_plans.return_value = []
    with pytest.raises(VultrError):
        d.drill("spoke", sshkey_ids=[], client=c)
    c.create_instance.assert_not_called()
