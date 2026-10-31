# AFTER-EDIT: scripts/sysadmin/claude_broker.py, scripts/cloud_dispatch.py, scripts/rivals_run.py
"""Seat dispatchers skip while a hibernate pause is marked (T03b, seam P: `hibernate.py paused`).

Exit 0 starts nothing; exit 1, >=2, a timeout or a missing script proceeds (fail-open). The fake
`hibernate.py` is injected through FABRIK_HIBERNATE_PY; nothing touches a live marker. Every seat a
dispatcher spawns carries CLAUDE_CODE_RETRY_WATCHDOG=1 and starts at oom_score_adj 500.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


broker = _load("claude_broker", "scripts/sysadmin/claude_broker.py")
cd = _load("cloud_dispatch", "scripts/cloud_dispatch.py")
rr = _load("rivals_run", "scripts/rivals_run.py")

_PROBES = [
    (broker, "_hibernate_paused"),
    (cd, "hibernate_paused"),
    (rr, "hibernate_paused"),
]


def _fake_hibernate(tmp_path: Path, rc: int) -> Path:
    p = tmp_path / f"hibernate_rc{rc}.py"
    p.write_text(f"import sys\nsys.exit({rc})\n")
    return p


def _boom(*a, **k):
    raise AssertionError("must stop before this call")


def _preexec(mod):
    return getattr(mod, "_seat_preexec", None) or mod.seat_preexec


@pytest.mark.parametrize(("mod", "fn"), _PROBES)
@pytest.mark.parametrize(("rc", "paused"), [(0, True), (1, False), (2, False), (7, False)])
def test_the_probe_reads_the_exit_code(mod, fn, rc, paused, tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(_fake_hibernate(tmp_path, rc)))
    assert getattr(mod, fn)() is paused


@pytest.mark.parametrize(("mod", "fn"), _PROBES)
def test_a_repo_with_no_hub_hibernate_proceeds(mod, fn, tmp_path, monkeypatch, capsys):
    """Row 1: a synced launcher in a repo with no hub hibernate.py proceeds as if not paused."""
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(tmp_path / "absent.py"))
    assert getattr(mod, fn)() is False
    assert "proceeding" in capsys.readouterr().err


@pytest.mark.parametrize(("mod", "fn"), _PROBES)
def test_a_hung_probe_times_out_and_proceeds(mod, fn, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(_fake_hibernate(tmp_path, 0)))

    def _slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=10)

    monkeypatch.setattr(mod.subprocess, "run", _slow)
    assert getattr(mod, fn)() is False
    assert "TimeoutExpired" in capsys.readouterr().err


# -- claude_broker ----------------------------------------------------------------


def _broker(tmp_path, *, paused: bool, calls: list, audits: list):
    class _Gov:
        def route(self, kind, *, caller=None):
            calls.append(("route", kind))
            return "ob@"

    def _run(prompt, model):
        calls.append(("claude", prompt))
        return "hi"

    return broker.Broker(
        tokens={"tok": {"caller": "svc", "five_hour": 100, "seven_day": 100}},
        governor=_Gov(),
        budgets_path=tmp_path / "budgets.json",
        status_fn=lambda: {},
        now_fn=lambda: 1000.0,
        run_claude_fn=_run,
        audit_fn=audits.append,
        paused_fn=lambda: paused,
    )


def test_the_broker_starts_no_seat_while_paused_and_still_audits(tmp_path):
    calls: list = []
    audits: list = []
    b = _broker(tmp_path, paused=True, calls=calls, audits=audits)
    code, resp = b.handle({"prompt": "secret prompt"}, "tok")
    assert code == 503 and resp["via"] == "paused"
    assert calls == [], "no governor route and no claude seat while paused"
    assert len(audits) == 1 and audits[0]["via"] == "paused" and audits[0]["status"] == 503
    assert "secret prompt" not in str(audits[0])
    assert set(audits[0]) == {"caller", "prompt_hash", "out_len", "via", "status"}
    budgets = json.loads((tmp_path / "budgets.json").read_text())
    assert all(budgets["svc"][w]["count"] == 0 for w in ("five_hour", "seven_day"))


def test_the_broker_serves_when_not_paused(tmp_path):
    calls: list = []
    audits: list = []
    code, resp = _broker(tmp_path, paused=False, calls=calls, audits=audits).handle(
        {"prompt": "p"}, "tok"
    )
    assert code == 200 and resp["completion"] == "hi"
    assert ("claude", "p") in calls


def test_the_broker_seat_carries_the_watchdog_and_oom_adj(monkeypatch):
    """Row 2: the env and the preexec_fn the seat is spawned with."""
    seen: dict = {}

    def _run(argv, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(broker.subprocess, "run", _run)
    assert broker._default_run_claude(["x"]) == "ok"
    assert seen["env"]["CLAUDE_CODE_RETRY_WATCHDOG"] == "1"
    assert seen["preexec_fn"] is broker._seat_preexec


@pytest.mark.parametrize("mod", [broker, cd, rr])
def test_the_preexec_really_sets_oom_score_adj_500(mod):
    out = subprocess.run(
        [sys.executable, "-c", "print(open('/proc/self/oom_score_adj').read().strip())"],
        capture_output=True,
        text=True,
        preexec_fn=_preexec(mod),
        check=True,
    ).stdout.strip()
    assert out == "500"


@pytest.mark.parametrize("mod", [broker, cd, rr])
def test_the_preexec_is_fail_open(mod, monkeypatch):
    def _deny(*a, **k):
        raise PermissionError("no")

    monkeypatch.setattr("builtins.open", _deny)
    _preexec(mod)()  # must not raise


# -- cloud_dispatch ----------------------------------------------------------------


def test_cloud_dispatch_writes_nothing_while_paused(monkeypatch, capsys):
    monkeypatch.setattr(cd, "hibernate_paused", lambda: True)
    for name in ("load_registry", "_ls_remote", "_settle_all", "read_ledger", "_run_claude"):
        monkeypatch.setattr(cd, name, _boom)
    ns = argparse.Namespace(task="t", task_file=None, slug="s", registry=None)
    assert cd._cmd_dispatch(ns) == 0
    assert "hibernate pause marked" in capsys.readouterr().err


def test_cloud_dispatch_proceeds_when_not_paused(monkeypatch):
    def _reached(_p):
        raise RuntimeError("reached")

    monkeypatch.setattr(cd, "hibernate_paused", lambda: False)
    monkeypatch.setattr(cd, "load_registry", _reached)
    with pytest.raises(RuntimeError, match="reached"):
        cd._cmd_dispatch(argparse.Namespace(task="t", task_file=None, slug="s", registry=None))


def test_cloud_dispatch_account_env_carries_the_watchdog(tmp_path):
    assert cd._account_env(tmp_path)["CLAUDE_CODE_RETRY_WATCHDOG"] == "1"


def test_cloud_dispatch_run_claude_passes_the_preexec(monkeypatch, tmp_path):
    seen: dict = {}

    def _run(argv, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, stdout="o", stderr="e")

    monkeypatch.setattr(cd.subprocess, "run", _run)
    assert cd._run_claude(["x"], {}, tmp_path) == (0, "oe")
    assert seen["preexec_fn"] is cd.seat_preexec


# -- rivals_run --------------------------------------------------------------------


def test_rivals_main_checks_once_and_starts_nothing_while_paused(monkeypatch, capsys):
    monkeypatch.chdir(REPO_ROOT)  # _foreign_caller_repo() reads the cwd
    n = {"probe": 0}

    def _probe():
        n["probe"] += 1
        return True

    monkeypatch.setattr(rr, "hibernate_paused", _probe)
    monkeypatch.setattr(rr, "load_env", _boom)
    monkeypatch.setattr(rr.asyncio, "run", _boom)
    assert rr.main(["--market", "x", "--greenfield", "--preflight-only"]) == 0
    assert n["probe"] == 1
    assert "hibernate pause marked" in capsys.readouterr().out


def test_rivals_main_proceeds_when_not_paused(monkeypatch, capsys):
    monkeypatch.chdir(REPO_ROOT)  # _foreign_caller_repo() reads the cwd
    monkeypatch.setattr(rr, "hibernate_paused", lambda: False)
    monkeypatch.setattr(rr, "load_env", lambda repo: [])
    for key in ("EXA_API_KEY", "BRAVE_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    assert rr.main(["--market", "x", "--greenfield", "--preflight-only"]) == 0
    assert "wiring is sound" in capsys.readouterr().out


def test_rivals_llm_seat_carries_the_watchdog_and_preexec(monkeypatch):
    seen: dict = {}

    class _P:
        returncode = 0

        async def communicate(self):
            return b'{"result": "x", "is_error": false}', b""

    async def _exec(*a, **k):
        seen.update(k)
        return _P()

    monkeypatch.setattr(rr.asyncio, "create_subprocess_exec", _exec)
    llm = rr._make_llm("sonnet")
    try:
        asyncio.run(llm("p"))
    except Exception:  # noqa: BLE001 — only the spawn kwargs are asserted
        pass
    assert seen["env"]["CLAUDE_CODE_RETRY_WATCHDOG"] == "1"
    assert seen["preexec_fn"] is rr.seat_preexec
