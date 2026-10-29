"""Coverage sweep for fabrik.drivers.preflight — gaps left by tests/drivers/test_preflight.py.

Hermetic: ``ssh`` and ``subprocess.run`` are mocked, ``time`` is not slept on, env is monkeypatched.
"""

from __future__ import annotations

import logging
import subprocess
from types import SimpleNamespace

import pytest

from fabrik.drivers import preflight as pf


def _run_result(rc=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def _no_jump_env(monkeypatch):
    for name in ("FABRIK_SSH_JUMP_VPS", "FABRIK_SSH_JUMP_VPS2", "FABRIK_VPS_SSH_HOST"):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------- #
# module surface                                                               #
# --------------------------------------------------------------------------- #


def test_all_names_resolve_and_constants_are_stable():
    for name in pf.__all__:
        assert hasattr(pf, name), name
    assert pf.PUBLIC_DNS_RESOLVER == "1.1.1.1"
    assert pf.TRAEFIK_API_LOCAL_URL.startswith("http://127.0.0.1:8080/")
    assert issubclass(pf.HostUnreachableError, RuntimeError)


# --------------------------------------------------------------------------- #
# _vps_resolves / _public_resolves                                             #
# --------------------------------------------------------------------------- #


def test_vps_resolves_dry_run_is_true_without_ssh(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ssh must not run")

    monkeypatch.setattr(pf, "ssh", boom)
    assert pf._vps_resolves("a.example.com", "1.2.3.4", dry_run=True) is True


def test_vps_resolves_matches_first_token_exactly(monkeypatch):
    calls = []

    def fake(cmd, timeout=None):
        calls.append((cmd, timeout))
        return "1.2.3.4  a.example.com\n"

    monkeypatch.setattr(pf, "ssh", fake)
    assert pf._vps_resolves("a.example.com", "1.2.3.4") is True
    assert calls == [("getent hosts a.example.com", 5)]
    assert pf._vps_resolves("a.example.com", "1.2.3.40") is False


def test_vps_resolves_ip_in_hostname_column_does_not_count(monkeypatch):
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: "9.9.9.9  1.2.3.4\n")
    assert pf._vps_resolves("x", "1.2.3.4") is False


def test_vps_resolves_empty_output_is_false(monkeypatch):
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: "")
    assert pf._vps_resolves("x", "1.2.3.4") is False


def test_vps_resolves_ssh_runtime_error_is_false(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("getent failed")

    monkeypatch.setattr(pf, "ssh", fail)
    assert pf._vps_resolves("x", "1.2.3.4") is False


@pytest.mark.xfail(
    strict=True,
    raises=IndexError,
    reason=(
        "whitespace-only output is truthy but split() is empty -> IndexError (preflight.py:148); "
        "latent: the real ssh() strips its answer (ssh.py:282)"
    ),
)
def test_vps_resolves_whitespace_only_output_is_false_not_a_crash(monkeypatch):
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: "  \n")
    assert pf._vps_resolves("x", "1.2.3.4") is False


def test_public_resolves_dry_run_is_true_without_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(pf.subprocess, "run", boom)
    assert pf._public_resolves("x", "1.2.3.4", dry_run=True) is True


def test_public_resolves_builds_dig_argv_and_finds_ip_in_cname_chain(monkeypatch):
    seen = {}

    def fake(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        return _run_result(0, "target.example.net.\n\n  1.2.3.4  \n")

    monkeypatch.setattr(pf.subprocess, "run", fake)
    assert pf._public_resolves("a.example.com", "1.2.3.4") is True
    assert seen["argv"] == ["dig", "+short", "a.example.com", "@1.1.1.1"]
    assert seen["kwargs"]["timeout"] == 5
    assert seen["kwargs"]["check"] is False


def test_public_resolves_missing_ip_or_empty_answer_is_false(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(0, "5.6.7.8\n"))
    assert pf._public_resolves("x", "1.2.3.4") is False
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(0, ""))
    assert pf._public_resolves("x", "1.2.3.4") is False


@pytest.mark.parametrize("answer", ["21.2.3.4", "1.2.3.45", "1.2.3.4.example.net."])
def test_public_resolves_needs_an_exact_answer_line(monkeypatch, answer):
    # A substring match would report a different public IP as propagated.
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(0, answer + "\n"))
    assert pf._public_resolves("x", "1.2.3.4") is False


def test_public_resolves_nonzero_rc_ignores_matching_stdout(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(9, "1.2.3.4\n"))
    assert pf._public_resolves("x", "1.2.3.4") is False


def test_public_resolves_timeout_is_false(monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("dig", 5)

    monkeypatch.setattr(pf.subprocess, "run", slow)
    assert pf._public_resolves("x", "1.2.3.4") is False


# --------------------------------------------------------------------------- #
# verify_dns_before_deployment                                                 #
# --------------------------------------------------------------------------- #


def test_dns_zero_timeout_names_both_failing_sides_without_polling(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no poll expected")

    monkeypatch.setattr(pf, "_vps_resolves", boom)
    monkeypatch.setattr(pf, "_public_resolves", boom)
    with pytest.raises(TimeoutError) as ei:
        pf.verify_dns_before_deployment("a.example.com", "1.2.3.4", timeout=0)
    msg = str(ei.value)
    assert "'a.example.com'" in msg and "'1.2.3.4'" in msg and "within 0s" in msg
    assert "VPS resolver" in msg and "public resolver (1.1.1.1)" in msg


def test_dns_sleeps_poll_interval_between_rounds_then_succeeds(monkeypatch):
    results = iter([(False, True), (True, True)])
    cur = {}

    def vps(fqdn, ip):
        cur["pair"] = next(results)
        return cur["pair"][0]

    sleeps = []
    monkeypatch.setattr(pf, "_vps_resolves", vps)
    monkeypatch.setattr(pf, "_public_resolves", lambda f, i: cur["pair"][1])
    monkeypatch.setattr(pf.time, "sleep", sleeps.append)
    pf.verify_dns_before_deployment("x", "1.2.3.4", timeout=60, poll_interval=0.25)
    assert sleeps == [0.25]


def test_dns_uses_default_ip_when_not_given(monkeypatch):
    seen = []
    monkeypatch.setattr(pf, "_vps_resolves", lambda f, ip: seen.append(ip) or True)
    monkeypatch.setattr(pf, "_public_resolves", lambda f, ip: seen.append(ip) or True)
    pf.verify_dns_before_deployment("x")
    assert seen == [pf.DEFAULT_VPS_IP, pf.DEFAULT_VPS_IP]


def test_dns_timeout_names_only_the_side_that_failed(monkeypatch):
    monkeypatch.setattr(pf, "_vps_resolves", lambda f, ip: True)
    monkeypatch.setattr(pf, "_public_resolves", lambda f, ip: False)
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    ticks = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr(pf.time, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError) as ei:
        pf.verify_dns_before_deployment("x", "1.2.3.4", timeout=5)
    assert "public resolver" in str(ei.value)
    assert "VPS resolver" not in str(ei.value)


# --------------------------------------------------------------------------- #
# Traefik                                                                      #
# --------------------------------------------------------------------------- #


def test_traefik_api_reachable_dry_run_skips_ssh(monkeypatch):
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: pytest.fail("ssh ran"))
    assert pf._traefik_api_reachable(dry_run=True) is True


def test_traefik_api_reachable_curl_command_and_failure(monkeypatch):
    seen = []
    monkeypatch.setattr(pf, "ssh", lambda cmd, timeout=None: seen.append((cmd, timeout)) or "")
    assert pf._traefik_api_reachable() is True
    cmd, timeout = seen[0]
    assert cmd.startswith("curl -fsS --max-time 3 ")
    assert pf.TRAEFIK_API_LOCAL_URL in cmd and timeout == 5

    def fail(*a, **k):
        raise RuntimeError("curl 22")

    monkeypatch.setattr(pf, "ssh", fail)
    assert pf._traefik_api_reachable() is False


def test_restart_traefik_issues_sudo_docker_restart_with_timeout(monkeypatch):
    seen = []
    monkeypatch.setattr(pf, "ssh", lambda cmd, timeout=None: seen.append((cmd, timeout)) or "")
    monkeypatch.setattr(pf, "_traefik_api_reachable", lambda: True)
    pf.restart_traefik_and_wait()
    assert seen == [("sudo docker restart traefik", 30)]


def test_restart_traefik_zero_timeout_raises_with_zero_attempts(monkeypatch):
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: "")
    monkeypatch.setattr(pf, "_traefik_api_reachable", lambda: pytest.fail("polled"))
    with pytest.raises(TimeoutError) as ei:
        pf.restart_traefik_and_wait(timeout=0)
    assert "attempts=0" in str(ei.value) and "within 0s" in str(ei.value)


def test_restart_traefik_sleeps_poll_interval_between_attempts(monkeypatch):
    answers = iter([False, False, True])
    sleeps = []
    monkeypatch.setattr(pf, "ssh", lambda *a, **k: "")
    monkeypatch.setattr(pf, "_traefik_api_reachable", lambda: next(answers))
    monkeypatch.setattr(pf.time, "sleep", sleeps.append)
    pf.restart_traefik_and_wait(timeout=60, poll_interval=0.5)
    assert sleeps == [0.5, 0.5]


# --------------------------------------------------------------------------- #
# _batch / _hop_destination                                                    #
# --------------------------------------------------------------------------- #


def test_batch_options():
    assert pf._batch(7) == ["-o", "BatchMode=yes", "-o", "ConnectTimeout=7"]


@pytest.mark.parametrize(
    ("hop", "dest"),
    [
        ("vps2", "vps2"),
        ("deploy@vps2", "deploy@vps2"),
        ("vps2:2222", "ssh://vps2:2222"),
        ("deploy@vps2:2222", "ssh://deploy@vps2:2222"),
    ],
)
def test_hop_destination_forms(hop, dest):
    assert pf._hop_destination(hop) == dest


def test_hop_destination_unparseable_hop_returned_verbatim():
    assert pf._hop_destination("none") == "none"


# --------------------------------------------------------------------------- #
# _probe                                                                       #
# --------------------------------------------------------------------------- #


def _probe_with(monkeypatch, **result):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(**result))
    return pf._probe(["ssh", "h", "true"], 10)


def test_probe_success_returns_ok_and_empty_reason(monkeypatch):
    assert _probe_with(monkeypatch, rc=0, stderr="noise") == (True, False, "")


def test_probe_timeout_is_network_shaped_with_outer_bound(monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("ssh", 15)

    monkeypatch.setattr(pf.subprocess, "run", slow)
    assert pf._probe(["ssh"], 10) == (False, True, "no answer in 15s")


def test_probe_oserror_is_not_network_shaped(monkeypatch):
    def missing(*a, **k):
        raise FileNotFoundError("ssh not found.")

    monkeypatch.setattr(pf.subprocess, "run", missing)
    ok, network, reason = pf._probe(["ssh"], 10)
    assert (ok, network) == (False, False)
    assert reason.startswith("FileNotFoundError: ssh not found") and not reason.endswith(".")


def test_probe_passes_outer_timeout_devnull_and_argv(monkeypatch):
    seen = {}

    def fake(argv, **kwargs):
        seen["argv"], seen["kw"] = argv, kwargs
        return _run_result(0)

    monkeypatch.setattr(pf.subprocess, "run", fake)
    pf._probe(["ssh", "h", "true"], 10)
    assert seen["argv"] == ["ssh", "h", "true"]
    assert seen["kw"]["timeout"] == 15
    assert seen["kw"]["stdin"] == subprocess.DEVNULL
    assert seen["kw"]["check"] is False


def test_probe_empty_stderr_falls_back_to_exit_code(monkeypatch):
    assert _probe_with(monkeypatch, rc=255, stderr="") == (False, False, "rc=255, no stderr")


def test_probe_stderr_of_only_frames_says_it_held_no_text(monkeypatch):
    ok, network, reason = _probe_with(monkeypatch, rc=255, stderr="@@@@\n.\n")
    assert (ok, network) == (False, False)
    assert reason == "rc=255, stderr held no text"


def test_probe_only_noise_reports_last_noise_line(monkeypatch):
    err = "Warning: Permanently added 'h' (ED25519) to the list of known hosts.\n"
    ok, network, reason = _probe_with(monkeypatch, rc=255, stderr=err)
    assert not ok and not network
    assert reason == "Warning: Permanently added 'h' (ED25519) to the list of known hosts"


def test_probe_joins_multiple_lines_in_order_and_flags_network(monkeypatch):
    err = "jump says no\nssh: connect to host h port 22: Connection refused\n"
    ok, network, reason = _probe_with(monkeypatch, rc=255, stderr=err)
    assert not ok and network
    assert reason == "jump says no; ssh: connect to host h port 22: Connection refused"


def test_probe_none_stderr_is_tolerated(monkeypatch):
    monkeypatch.setattr(
        pf.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=None)
    )
    assert pf._probe(["ssh"], 10) == (False, False, "rc=1, no stderr")


@pytest.mark.parametrize(
    "line",
    [
        "Connection timed out",
        "Connection reset by peer",
        "No route to host",
        "Network is unreachable",
        "ssh: Could not resolve hostname h: Name or service not known",
        "banner exchange: timeout",
    ],
)
def test_probe_network_shapes_detected(monkeypatch, line):
    assert _probe_with(monkeypatch, rc=255, stderr=line + "\n")[1] is True


def test_probe_permission_denied_is_not_network_shaped(monkeypatch):
    ok, network, reason = _probe_with(
        monkeypatch, rc=255, stderr="Permission denied (publickey).\n"
    )
    assert (ok, network, reason) == (False, False, "Permission denied (publickey)")


# --------------------------------------------------------------------------- #
# check_ssh_config                                                             #
# --------------------------------------------------------------------------- #


def test_check_ssh_config_returns_none_when_no_jump():
    assert pf.check_ssh_config("vps") is None


def test_check_ssh_config_returns_the_jump(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    assert pf.check_ssh_config("vps") == "vps2"


def test_check_ssh_config_user_qualified_alias_reads_unqualified_variable(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    assert pf.check_ssh_config("deploy@vps") == "vps2"


@pytest.mark.parametrize("host", ["", "-oProxyCommand=x", "a b", "h;rm"])
def test_check_ssh_config_rejects_non_alias(host):
    with pytest.raises(pf.HostUnreachableError, match="not an ssh alias.*nothing was changed"):
        pf.check_ssh_config(host)


def test_check_ssh_config_malformed_jump_becomes_host_unreachable(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "bad jump!")
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.check_ssh_config("vps")
    assert "FABRIK_SSH_JUMP_VPS" in str(ei.value)
    assert str(ei.value).endswith("(nothing was changed)")
    assert ei.value.__cause__ is None


# --------------------------------------------------------------------------- #
# verify_host_reachable                                                        #
# --------------------------------------------------------------------------- #


def _script_probes(monkeypatch, answers):
    calls = []

    def fake(argv, **kwargs):
        calls.append(argv)
        return answers.pop(0)

    monkeypatch.setattr(pf.subprocess, "run", fake)
    return calls


def test_default_host_comes_from_env(monkeypatch):
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "myvps")
    calls = _script_probes(monkeypatch, [_run_result(0)])
    pf.verify_host_reachable()
    assert calls == [["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "myvps", "true"]]


def test_default_host_is_vps_when_env_unset(monkeypatch):
    calls = _script_probes(monkeypatch, [_run_result(0)])
    pf.verify_host_reachable()
    assert calls[0][-2:] == ["vps", "true"]


def test_explicit_host_and_timeout_flow_into_argv(monkeypatch):
    calls = _script_probes(monkeypatch, [_run_result(0)])
    pf.verify_host_reachable("vps3", timeout=4)
    assert "ConnectTimeout=4" in calls[0] and calls[0][-2] == "vps3"


def test_jumped_success_probes_with_proxyjump_then_checks_direct_path(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    calls = _script_probes(monkeypatch, [_run_result(0), _run_result(255)])
    pf.verify_host_reachable("vps")
    assert calls[0][:3] == ["ssh", "-o", "ProxyJump=vps2"]
    assert calls[1][:3] == ["ssh", "-o", "ProxyJump=none"]
    assert "ConnectTimeout=3" in calls[1]


def test_empty_jump_value_means_direct_probe(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "")
    calls = _script_probes(monkeypatch, [_run_result(0)])
    pf.verify_host_reachable("vps")
    assert len(calls) == 1 and not any(a.startswith("ProxyJump") for a in calls[0])


def test_multi_hop_jump_is_passed_whole_and_blames_a_later_hop(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2,vps3")
    calls = _script_probes(
        monkeypatch,
        [
            _run_result(255, stderr="ssh: connect to host x port 22: Connection timed out\n"),
            _run_result(0),
        ],
    )
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.verify_host_reachable("vps")
    assert "ProxyJump=vps2,vps3" in calls[0]
    assert calls[1][-2:] == ["vps2", "true"]
    msg = str(ei.value)
    assert "a later hop or the leg to 'vps'" in msg
    assert "unset FABRIK_SSH_JUMP_VPS" in msg
    assert "via jump 'vps2,vps3'" in msg


def test_jump_answers_but_failure_not_network_shaped_says_run_by_hand(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    _script_probes(
        monkeypatch, [_run_result(255, stderr="Permission denied (publickey).\n"), _run_result(0)]
    )
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.verify_host_reachable("vps")
    assert "The jump host 'vps2' answers. Run `ssh vps true` by hand" in str(ei.value)


def test_jump_host_itself_unreachable_blames_the_jump(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    _script_probes(
        monkeypatch,
        [
            _run_result(255, stderr="Connection timed out\n"),
            _run_result(255, stderr="ssh: connect to host vps2: Connection refused\n"),
        ],
    )
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.verify_host_reachable("vps")
    msg = str(ei.value)
    assert "The jump host 'vps2' is unreachable too" in msg
    assert "Check `ssh vps2 true`" in msg


def test_jump_host_auth_failure_says_fails_not_unreachable(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    _script_probes(
        monkeypatch,
        [
            _run_result(255, stderr="Connection timed out\n"),
            _run_result(255, stderr="Permission denied (publickey)\n"),
        ],
    )
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.verify_host_reachable("vps")
    msg = str(ei.value)
    assert "The jump host 'vps2' fails: Permission denied (publickey)" in msg
    assert "unreachable too" not in msg


def test_direct_network_failure_suggests_setting_the_jump_variable(monkeypatch):
    calls = _script_probes(
        monkeypatch, [_run_result(255, stderr="Connection timed out during banner exchange\n")]
    )
    with pytest.raises(pf.HostUnreachableError) as ei:
        pf.verify_host_reachable("deploy@vps-1")
    assert len(calls) == 1
    msg = str(ei.value)
    assert "set FABRIK_SSH_JUMP_VPS_1=<that alias>" in msg
    assert "without a FABRIK jump" in msg
    assert msg.endswith("(nothing was changed)")


def test_probe_timeout_on_direct_path_reports_outer_bound(monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("ssh", 15)

    monkeypatch.setattr(pf.subprocess, "run", slow)
    with pytest.raises(pf.HostUnreachableError, match="no answer in 15s"):
        pf.verify_host_reachable("vps")


def test_bad_host_is_refused_before_any_subprocess(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: pytest.fail("probe ran"))
    with pytest.raises(pf.HostUnreachableError, match="not an ssh alias"):
        pf.verify_host_reachable("bad host")


# --------------------------------------------------------------------------- #
# _advise_if_direct_back                                                       #
# --------------------------------------------------------------------------- #


def test_advise_logs_warning_naming_host_and_variable_when_direct_answers(monkeypatch, caplog):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(0))
    with caplog.at_level(logging.WARNING, logger=pf.logger.name):
        pf._advise_if_direct_back("vps", "FABRIK_SSH_JUMP_VPS")
    assert "FABRIK_SSH_JUMP_VPS can be removed" in caplog.text
    assert "'vps'" in caplog.text


def test_advise_is_silent_when_direct_still_dead(monkeypatch, caplog):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: _run_result(255))
    with caplog.at_level(logging.WARNING, logger=pf.logger.name):
        pf._advise_if_direct_back("vps", "V")
    assert caplog.text == ""


@pytest.mark.parametrize(
    "exc", [subprocess.TimeoutExpired("ssh", 5), OSError("no ssh"), ValueError("x")]
)
def test_advise_swallows_any_probe_error(monkeypatch, exc):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(pf.subprocess, "run", boom)
    assert pf._advise_if_direct_back("vps", "V") is None


def test_jumped_pass_survives_a_crashing_advisory_probe(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    n = {"i": 0}

    def fake(argv, **kwargs):
        n["i"] += 1
        if n["i"] == 1:
            return _run_result(0)
        raise OSError("boom")

    monkeypatch.setattr(pf.subprocess, "run", fake)
    pf.verify_host_reachable("vps")
    assert n["i"] == 2
