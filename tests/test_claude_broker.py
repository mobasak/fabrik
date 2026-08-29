"""Behavior-Contract tests for scripts/sysadmin/claude_broker.py (TDD — written FIRST).

The broker gives Docker containers subscription-billed LLM completion on the single-key ob@ host
Claude with NO host tools and NO creds: it runs `claude -p --tools ""` (the documented "disable all
tools" form — `claude --help`, v2.1.238) via the host entrypoint, gated by per-caller token auth +
per-caller window budgets, forcing every job to `routine` through the QuotaGovernor (so a job sheds
to the pool under the reserve, never dropped). It FAILS CLOSED if the tool-disable form is unverified.

`Broker.handle(body, token)` is the pure request handler (status_code, response) — the HTTP server
is a thin wrapper. All I/O (claude subprocess, pool, governor) is injected, so nothing touches live
state or burns quota.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / "scripts" / "sysadmin" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


claude_broker = _load("claude_broker")
quota_governor = _load("quota_governor")
Broker = claude_broker.Broker
QuotaGovernor = quota_governor.QuotaGovernor


class _FakeGovernor:
    """Records the (kind, caller) it was routed with; returns a canned destination."""

    def __init__(self, dest="ob@"):
        self.dest = dest
        self.calls: list[tuple[str, str | None]] = []

    def route(self, kind, *, caller=None):
        self.calls.append((kind, caller))
        return self.dest


def _broker(tmp_path, *, governor=None, dest="ob@", now=1000.0, run_claude=None, pool=None,
            tool_disable_args=("--tools", ""), tokens=None):
    gov = governor or _FakeGovernor(dest)
    audit: list[dict] = []
    b = Broker(
        tokens=tokens if tokens is not None else {"tok-alpha": {"caller": "alpha", "five_hour_limit": 3, "seven_day_limit": 10}},
        governor=gov,
        budgets_path=tmp_path / "broker-budgets.json",
        status_fn=lambda: {"active": "ob", "accounts": [{"slugs": ["ob"],
                           "five_hour": {"resets_at_epoch": 5000.0}, "seven_day": {"resets_at_epoch": 9000.0}}]},
        now_fn=lambda: now,
        run_claude_fn=run_claude or (lambda prompt, model: f"ob-completion:{prompt}"),
        pool_fn=pool or (lambda prompt, model: f"pool-completion:{prompt}"),
        tool_disable_args=tool_disable_args,
        audit_fn=audit.append,
    )
    b._audit_log = audit  # test handle to the captured audit lines
    return b


# (a) a valid token returns a completion; no/invalid token → 401
def test_valid_token_completion(tmp_path):
    b = _broker(tmp_path)
    code, resp = b.handle({"prompt": "hello"}, "tok-alpha")
    assert code == 200
    assert resp["completion"] == "ob-completion:hello"


def test_missing_token_401(tmp_path):
    b = _broker(tmp_path)
    assert b.handle({"prompt": "hi"}, None)[0] == 401


def test_invalid_token_401(tmp_path):
    b = _broker(tmp_path)
    assert b.handle({"prompt": "hi"}, "tok-WRONG")[0] == 401


# (b) the claude invocation argv carries the grounded tool-disable flag (no host tools)
def test_claude_argv_carries_tool_disable(tmp_path):
    b = _broker(tmp_path)
    argv = b._claude_argv("do a thing", None)
    assert "--tools" in argv
    # the token AFTER --tools is the empty string — "disable all tools"
    assert argv[argv.index("--tools") + 1] == ""
    assert "-p" in argv


def test_claude_argv_carries_tool_disable_with_model(tmp_path):
    b = _broker(tmp_path)
    argv = b._claude_argv("do a thing", "claude-opus-4-8")
    assert "--tools" in argv and argv[argv.index("--tools") + 1] == ""


# (b2) if the tool-disable form is unverifiable, the broker refuses to serve (fail-CLOSED)
def test_fail_closed_when_tool_disable_unverified(tmp_path):
    called = {"ran": False}

    def _run(prompt, model):
        called["ran"] = True
        return "SHOULD NEVER RUN"

    b = _broker(tmp_path, tool_disable_args=(), run_claude=_run)  # empty → not the pinned deny form
    code, resp = b.handle({"prompt": "hi"}, "tok-alpha")
    assert code == 503
    assert called["ran"] is False  # never invoked an unrestricted claude


# (c) an over-budget caller → 429 (seed the counter file at the limit)
def test_over_budget_429(tmp_path):
    b = _broker(tmp_path)  # five_hour_limit = 3
    for _ in range(3):
        assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 200
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 429  # 4th over the 5h limit


# (d) the counter resets when now >= resets_at_epoch; a None epoch neither resets nor raises
def test_budget_resets_after_epoch(tmp_path):
    b = _broker(tmp_path, now=1000.0)  # window reset epochs 5000/9000
    for _ in range(3):
        b.handle({"prompt": "x"}, "tok-alpha")
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 429
    # a later request past the 5h reset epoch (5000) starts a fresh count
    b2 = _broker(tmp_path, now=6000.0)
    assert b2.handle({"prompt": "x"}, "tok-alpha")[0] == 200


def test_budget_none_epoch_never_resets_nor_raises(tmp_path):
    # status_fn yields a None reset epoch → the window count must not reset and must not crash
    gov = _FakeGovernor("ob@")
    audit: list[dict] = []
    b = Broker(
        tokens={"tok-alpha": {"caller": "alpha", "five_hour_limit": 2, "seven_day_limit": 10}},
        governor=gov, budgets_path=tmp_path / "b.json",
        status_fn=lambda: {"active": "ob", "accounts": [{"slugs": ["ob"],
                           "five_hour": {"resets_at_epoch": None}, "seven_day": {"resets_at_epoch": None}}]},
        now_fn=lambda: 1000.0,
        run_claude_fn=lambda p, m: "ok", pool_fn=lambda p, m: "pool",
        tool_disable_args=("--tools", ""), audit_fn=audit.append,
    )
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 200
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 200
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 429  # still counts; None epoch never reset it


# (e) the broker forces `routine` + calls the governor; a job under the reserve routes to the pool
def test_forces_routine_and_sheds_to_pool(tmp_path):
    gov = _FakeGovernor("pool")
    b = _broker(tmp_path, governor=gov)
    code, resp = b.handle({"prompt": "hello"}, "tok-alpha")
    assert code == 200
    assert resp["completion"] == "pool-completion:hello"   # shed to pool, not ob@
    assert gov.calls == [("routine", "alpha")]             # class forced to routine, caller passed


def test_audit_line_per_job(tmp_path):
    b = _broker(tmp_path)
    b.handle({"prompt": "secret prompt"}, "tok-alpha")
    assert len(b._audit_log) == 1
    line = b._audit_log[0]
    assert line["caller"] == "alpha"
    assert "prompt_hash" in line            # hash, not the raw prompt
    assert "secret prompt" not in str(line)  # the raw prompt is never audited verbatim


# SECURITY: the container-controlled prompt must never be parsed as a CLI flag — a `--` sentinel
# separates it from the options (red-on-revert: without `--`, a `--allow-…` prompt becomes a flag).
def test_prompt_cannot_inject_a_flag(tmp_path):
    b = _broker(tmp_path)
    argv = b._claude_argv("--allow-dangerously-skip-permissions", None)
    assert argv[-1] == "--allow-dangerously-skip-permissions"  # the prompt is the LAST arg
    assert argv[-2] == "--"                                    # immediately preceded by the sentinel
    # and the pinned tool-disable is still present + before the sentinel
    assert argv.index("--tools") < argv.index("--")


def test_prompt_flag_injection_with_model(tmp_path):
    b = _broker(tmp_path)
    argv = b._claude_argv("--help", "claude-opus-4-8")
    assert argv[-2] == "--" and argv[-1] == "--help"
    assert argv[argv.index("--model") + 1] == "claude-opus-4-8"


# a FAILED completion still spends ob@ quota → it must be counted + audited + returned 502, never
# an uncaught exception (else a caller burns quota under-budget with zero audit trail).
def test_failed_run_counts_audits_and_502(tmp_path):
    def _boom(prompt, model):
        raise RuntimeError("claude timed out")

    b = _broker(tmp_path, run_claude=_boom)  # five_hour_limit = 3
    code, resp = b.handle({"prompt": "x"}, "tok-alpha")
    assert code == 502
    assert "completion failed" in resp["error"]
    assert any(line.get("status") == 502 for line in b._audit_log)  # the failure is audited
    # the failed attempt consumed budget: two more (limit 3) then the 4th is 429
    b.handle({"prompt": "x"}, "tok-alpha")
    b.handle({"prompt": "x"}, "tok-alpha")
    assert b.handle({"prompt": "x"}, "tok-alpha")[0] == 429


# a window created with a None epoch (during a --status outage) must RECOVER once status returns a
# real (past) epoch — not stay wedged at 429 forever.
def test_none_epoch_window_recovers_on_status_return(tmp_path):
    gov = _FakeGovernor("ob@")
    audit: list[dict] = []
    budgets = tmp_path / "b.json"
    # phase 1: --status is down (None epochs); caller hits the limit
    down = Broker(
        tokens={"tok-alpha": {"caller": "alpha", "five_hour_limit": 2, "seven_day_limit": 10}},
        governor=gov, budgets_path=budgets,
        status_fn=lambda: {"active": "ob", "accounts": [{"slugs": ["ob"],
                           "five_hour": {"resets_at_epoch": None}, "seven_day": {"resets_at_epoch": None}}]},
        now_fn=lambda: 1000.0, run_claude_fn=lambda p, m: "ok", pool_fn=lambda p, m: "pool",
        tool_disable_args=("--tools", ""), audit_fn=audit.append,
    )
    down.handle({"prompt": "x"}, "tok-alpha")
    down.handle({"prompt": "x"}, "tok-alpha")
    assert down.handle({"prompt": "x"}, "tok-alpha")[0] == 429  # wedged while down
    # phase 2: --status returns a PAST epoch (2000 < now 3000) → the window must roll over
    up = Broker(
        tokens={"tok-alpha": {"caller": "alpha", "five_hour_limit": 2, "seven_day_limit": 10}},
        governor=gov, budgets_path=budgets,
        status_fn=lambda: {"active": "ob", "accounts": [{"slugs": ["ob"],
                           "five_hour": {"resets_at_epoch": 2000.0}, "seven_day": {"resets_at_epoch": 2000.0}}]},
        now_fn=lambda: 3000.0, run_claude_fn=lambda p, m: "ok", pool_fn=lambda p, m: "pool",
        tool_disable_args=("--tools", ""), audit_fn=audit.append,
    )
    assert up.handle({"prompt": "x"}, "tok-alpha")[0] == 200  # recovered, not stuck at 429


def test_non_dict_body_400(tmp_path):
    b = _broker(tmp_path)
    assert b.handle(["not", "a", "dict"], "tok-alpha")[0] == 400


# a container-controlled `model` value must be a strict model name — a `--`-leading value that some
# arg parsers could read as a flag is refused 400 (defence-in-depth on top of the `--` sentinel).
def test_flag_shaped_model_rejected_400(tmp_path):
    called = {"ran": False}

    def _run(prompt, model):
        called["ran"] = True
        return "x"

    b = _broker(tmp_path, run_claude=_run)
    assert b.handle({"prompt": "hi", "model": "--allow-dangerously-skip-permissions"}, "tok-alpha")[0] == 400
    assert b.handle({"prompt": "hi", "model": "sonnet --tools default"}, "tok-alpha")[0] == 400
    assert called["ran"] is False  # never invoked claude with a flag-shaped model
    # a legitimate model name still works
    assert b.handle({"prompt": "hi", "model": "claude-opus-4-8"}, "tok-alpha")[0] == 200


def test_malformed_token_config_500(tmp_path):
    # a token whose config lacks "caller" must not KeyError — 500 misconfig, never a crash
    b = _broker(tmp_path, tokens={"tok-bad": {"five_hour_limit": 3}})
    assert b.handle({"prompt": "x"}, "tok-bad")[0] == 500


# the Content-Length guard: a negative length (would make rfile.read(-1) OOM the host) or a
# non-integer must be REJECTED, not read; a normal length passes.
def test_safe_content_length():
    assert claude_broker._safe_content_length("-1") is None          # negative → no unbounded read
    assert claude_broker._safe_content_length("abc") is None         # non-integer → no ValueError escape
    assert claude_broker._safe_content_length(str(10 ** 9)) is None  # over _MAX_BODY (1 MB)
    assert claude_broker._safe_content_length(None) == 0             # missing → empty body
    assert claude_broker._safe_content_length("100") == 100          # normal
