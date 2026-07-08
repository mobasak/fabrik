"""Phase C — loop.py: the per-subagent executor (single-shot or tool-loop).

Highest-risk behavior: the tool-loop must EXECUTE tool calls in the workdir and
TERMINATE (on stop, or on a cap). Transport is dependency-injected so these run
offline with a fake model — no network, no API key.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from subagents._transport import Result
from subagents.loop import LoopOutcome, run_loop


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_web_tools_disabled_not_advertised_or_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """web_tools=None → the web schema is NOT advertised, and a web_search call the
    model emits anyway is rejected ('not enabled') without hitting the network."""
    # set the key so `net == []` proves the GATE blocks (not a missing-key early return)
    monkeypatch.setenv("EXA_API_KEY", "k")
    seen: dict = {}
    net: list = []
    web_client = _mock_client(lambda r: net.append(r) or httpx.Response(200, json={}))

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[_tool_call("web_search", '{"query":"x"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        web_client=web_client,
    )
    names = {t["function"]["name"] for t in (seen["body"] or {}).get("tools", [])}
    assert "web_search" not in names
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "not enabled" in tool_msgs[0]["content"]
    assert net == [], "gate did not block the web call (network hit while disabled)"
    assert "web_search" not in out.tool_calls  # a blocked call is NOT counted


def test_web_tools_partial_enable_rejects_other_web_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """web_tools={web_search} on, model emits web_scrape (disabled) → rejected +
    not counted, even though ANOTHER web tool is enabled."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")
    net: list = []
    web_client = _mock_client(lambda r: net.append(r) or httpx.Response(200, json={}))

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[_tool_call("web_scrape", '{"url":"http://x"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        web_tools=frozenset({"web_search"}),
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        web_client=web_client,
    )
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "not enabled" in tool_msgs[0]["content"]
    assert net == [] and "web_scrape" not in out.tool_calls


def test_web_tools_enabled_routes_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """web_tools={'web_search'} → advertised, routed to execute_web_tool, counted."""
    monkeypatch.setenv("EXA_API_KEY", "k")
    seen: dict = {}
    web_client = _mock_client(
        lambda r: httpx.Response(
            200, json={"results": [{"title": "HIT", "url": "u", "text": "s"}]}
        )
    )

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[_tool_call("web_search", '{"query":"x"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        web_tools=frozenset({"web_search"}),
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        web_client=web_client,
    )
    names = {t["function"]["name"] for t in (seen["body"] or {}).get("tools", [])}
    assert names == {"web_search"}  # only the enabled web tool (file tools off)
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "HIT" in tool_msgs[0]["content"]
    assert out.tool_calls.get("web_search") == 1


def test_failed_enabled_web_call_is_not_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ENABLED web tool that fails (unset key → ok=False, no paid work) must NOT
    be counted — tool_calls records successful usage, not attempts."""
    monkeypatch.delenv("EXA_API_KEY", raising=False)  # web_search will fail ok=False

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[_tool_call("web_search", '{"query":"x"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        web_tools=frozenset({"web_search"}),
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "EXA_API_KEY" in tool_msgs[0]["content"]  # it ran + failed
    assert "web_search" not in out.tool_calls  # but a FAILED call is not counted


def test_file_tools_disabled_are_refused_not_run(tmp_path: Path) -> None:
    """tools_enabled=False → a file/command tool the model emits is refused (two-way
    gate, matching web tools), not executed. Matters for the research config where
    file tools are off but web tools are on."""

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[
                    _tool_call("write_file", '{"path":"x.txt","content":"hi"}')
                ],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "disabled" in tool_msgs[0]["content"]
    assert not (tmp_path / "x.txt").exists()  # refused, NOT executed
    assert "write_file" not in out.tool_calls


def _result(
    *,
    text: str = "",
    tool_calls: list[dict] | None = None,
    finish_reason: str | None = "stop",
    cost_usd: float | None = 0.001,
    error: str | None = None,
) -> Result:
    return Result(
        text=text,
        tool_calls=tool_calls,
        model="fake/model",
        provider="fake",
        usage={},
        cost_usd=cost_usd,
        cost_unknown=cost_usd is None,
        finish_reason=finish_reason,
        reasoning="",
        consult_id="cid",
        error=error,
    )


def _tool_call(name: str, arguments: str, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_tool_loop_executes_and_terminates(tmp_path: Path) -> None:
    """Turn 1 asks to write a file; turn 2 stops. The file must exist, the tool
    result must be in the transcript, and the loop must end done in 2 turns."""
    calls: list[list[dict]] = []

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls.append(list(messages))
        if len(calls) == 1:
            return _result(
                tool_calls=[
                    _tool_call("write_file", '{"path": "x.txt", "content": "hi"}')
                ],
                finish_reason="tool_calls",
            )
        return _result(text="all done", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="you are a coder",
        task="write x.txt",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )

    assert isinstance(outcome, LoopOutcome)
    assert outcome.status == "done"
    assert outcome.turns == 2
    assert outcome.text == "all done"
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "hi"
    # the tool result was fed back into the conversation
    assert any(m.get("role") == "tool" for m in outcome.transcript)
    # the served provider is surfaced for downstream provenance
    assert outcome.provider == "fake"


def test_loop_respects_max_turns(tmp_path: Path) -> None:
    """A model that never stops is capped at max_turns."""

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(
            tool_calls=[_tool_call("list_dir", "{}")], finish_reason="tool_calls"
        )

    outcome = run_loop(
        model="fake/model",
        system="",
        task="loop forever",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=3,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "capped"
    assert outcome.turns == 3


def test_single_shot_no_tools(tmp_path: Path) -> None:
    """With tools disabled, one call returns and the loop is done."""
    n = {"count": 0}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        n["count"] += 1
        assert body is None, "no tools body should be sent when tools_enabled=False"
        return _result(text="prose answer", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="explain X",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "done"
    assert outcome.turns == 1
    assert outcome.text == "prose answer"
    assert n["count"] == 1


def test_transport_error_returns_error_status(tmp_path: Path) -> None:
    """A transport error (Result.error set) surfaces as status=error, not a crash."""

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(error="429 rate limited", finish_reason=None)

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "error"
    assert outcome.error is not None


def test_loop_raising_transport_returns_error(tmp_path: Path) -> None:
    """If the transport itself raises, the loop returns error rather than propagating."""

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("boom")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "error"
    assert "boom" in (outcome.error or "")


def test_cost_cap_caps_the_loop(tmp_path: Path) -> None:
    """Accumulated cost over the cap ends the loop as capped."""

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(
            tool_calls=[_tool_call("list_dir", "{}")],
            finish_reason="tool_calls",
            cost_usd=1.0,
        )

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=100,
        max_cost_usd=1.5,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "capped"
    assert outcome.cost_usd is not None and outcome.cost_usd >= 1.5


def test_loop_bounds_call_to_remaining_wall_clock(tmp_path: Path) -> None:
    """The loop passes the transport a liveness bounded by the wall-clock budget,
    so a single call can't exceed it (wall_clock enforced mid-call, not just between)."""
    seen: dict[str, object] = {}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["liveness"] = liveness
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=30.0,
        run_fn=fake_run,
    )
    lv = seen["liveness"]
    assert lv is not None
    assert lv.hard_timeout_s <= 30.0  # bounded by wall_clock_s
    assert lv.idle_timeout_s <= 30.0
    assert lv.connect_timeout_s <= 30.0  # connect bounded too
    assert (
        lv.restart_max == 0
    )  # transport retry disabled → wall_clock is a hard ceiling


def test_allowed_commands_threaded_to_tools(tmp_path: Path) -> None:
    """AgentSpec.allowed_commands must reach execute_tool — an empty set forbids
    all command execution while file tools still work (the F1 fix)."""
    calls = {"n": 0}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls["n"] += 1
        if calls["n"] == 1:
            return _result(
                tool_calls=[
                    _tool_call("run_command", '{"cmd": "python -c \\"print(1)\\""}')
                ],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        allowed_commands=frozenset(),  # forbid ALL execution
        run_fn=fake_run,
    )
    tool_msgs = [m for m in outcome.transcript if m.get("role") == "tool"]
    assert tool_msgs and "not in the allow-list" in tool_msgs[0]["content"]


def test_non_dict_tool_arguments_do_not_crash(tmp_path: Path) -> None:
    """A valid-JSON but NON-object arguments payload (list/str/int) must feed an
    error back, not crash the run and discard its paid diff (the F3#1 HIGH fix)."""
    calls = {"n": 0}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls["n"] += 1
        if calls["n"] == 1:
            return _result(
                tool_calls=[
                    _tool_call("read_file", "[1, 2, 3]")
                ],  # valid JSON, not an object
                finish_reason="tool_calls",
            )
        return _result(text="recovered", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "done"  # did NOT crash into error
    tool_msgs = [m for m in outcome.transcript if m.get("role") == "tool"]
    assert tool_msgs and "must be a JSON object" in tool_msgs[0]["content"]


def test_synthetic_ids_do_not_collide_with_real_ids(tmp_path: Path) -> None:
    """A call missing an id must get a UNIQUE synthetic id, never colliding with a
    sibling's real ordinal id (F1#2)."""

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_dir", "arguments": "{}"},
                    },
                    {
                        "type": "function",
                        "function": {"name": "list_dir", "arguments": "{}"},
                    },  # no id
                ],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    asst = next(
        m
        for m in outcome.transcript
        if m.get("role") == "assistant" and m.get("tool_calls")
    )
    ids = [tc["id"] for tc in asst["tool_calls"]]
    assert len(ids) == len(set(ids)), f"duplicate tool_call ids: {ids}"
    tool_ids = [
        m["tool_call_id"] for m in outcome.transcript if m.get("role") == "tool"
    ]
    assert sorted(tool_ids) == sorted(ids)  # every tool result pairs to a unique call


def test_tool_call_without_id_gets_synthetic_id(tmp_path: Path) -> None:
    """A tool call missing an id is given a synthetic one so the resent message +
    tool result have matching ids (F6/F9)."""

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        if not any(m.get("role") == "tool" for m in messages):
            tc = {
                "type": "function",
                "function": {"name": "list_dir", "arguments": "{}"},
            }
            return _result(tool_calls=[tc], finish_reason="tool_calls")
        return _result(text="done", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "done"
    asst = [
        m
        for m in outcome.transcript
        if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    tool = [m for m in outcome.transcript if m.get("role") == "tool"]
    assert asst[0]["tool_calls"][0]["id"], "assistant tool_call missing id"
    assert tool[0]["tool_call_id"] == asst[0]["tool_calls"][0]["id"], "id mismatch"


def test_capped_preserves_last_text(tmp_path: Path) -> None:
    """A cost-capped run keeps the model's last text instead of blanking it (F5)."""

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(
            text="partial progress here",
            tool_calls=[_tool_call("list_dir", "{}")],
            finish_reason="tool_calls",
            cost_usd=1.0,
        )

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=100,
        max_cost_usd=0.5,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "capped"
    assert outcome.text == "partial progress here"


def test_malformed_tool_arguments_do_not_crash(tmp_path: Path) -> None:
    """Invalid JSON in tool arguments is handled: the loop feeds an error back."""
    calls = {"n": 0}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls["n"] += 1
        if calls["n"] == 1:
            return _result(
                tool_calls=[_tool_call("write_file", "{not valid json")],
                finish_reason="tool_calls",
            )
        return _result(text="recovered", finish_reason="stop")

    outcome = run_loop(
        model="fake/model",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert outcome.status == "done"
    tool_msgs = [m for m in outcome.transcript if m.get("role") == "tool"]
    assert tool_msgs and (
        "error" in tool_msgs[0]["content"].lower()
        or "json" in tool_msgs[0]["content"].lower()
    )


# ── extra_body passthrough + on_progress observability (2026-07-07) ──────────────

def test_extra_body_merges_under_tools(tmp_path: Path) -> None:
    """A per-agent extra_body (provider pin / max_tokens / reasoning) reaches the
    transport MERGED with the loop's tool schemas."""
    seen: dict = {}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run,
        extra_body={"provider": {"only": ["Minimax"]}, "max_tokens": 20000},
    )
    assert seen["body"]["provider"] == {"only": ["Minimax"]}
    assert seen["body"]["max_tokens"] == 20000
    assert isinstance(seen["body"]["tools"], list)  # loop still controls tools


def test_extra_body_cannot_clobber_tools(tmp_path: Path) -> None:
    """extra_body is merged UNDER tools — a caller-supplied `tools` can't win."""
    seen: dict = {}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run, extra_body={"tools": "HACKED"},
    )
    assert seen["body"]["tools"] != "HACKED"
    assert isinstance(seen["body"]["tools"], list)


def test_no_extra_body_single_shot_is_none(tmp_path: Path) -> None:
    """No extra_body + no advertised tools ⇒ body stays None (unchanged behavior)."""
    seen: dict = {"body": "unset"}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=False, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert seen["body"] is None


def test_on_progress_fires_once_per_turn(tmp_path: Path) -> None:
    """on_progress fires per completed turn with turns/cost/provider/tools; the last
    turn (finishing) reports an empty tools list."""
    events: list[dict] = []
    calls: list[int] = []

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls.append(1)
        if len(calls) == 1:
            return _result(
                tool_calls=[_tool_call("write_file", '{"path": "x.txt", "content": "hi"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=8, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run, on_progress=events.append,
    )
    assert len(events) == 2
    assert events[0]["turns"] == 1 and events[0]["tools"] == ["write_file"]
    assert events[1]["turns"] == 2 and events[1]["tools"] == []
    # values, not just keys: cost accumulates (each _result defaults cost_usd=0.001);
    # provider is the served id — proves running cost/provider are actually reported.
    assert events[0]["cost_usd"] == pytest.approx(0.001)
    assert events[1]["cost_usd"] == pytest.approx(0.002)
    assert all(e["provider"] == "fake" for e in events)


def test_on_progress_raising_never_crashes_the_loop(tmp_path: Path) -> None:
    """A buggy progress callback is swallowed — observability must not break a run.
    Also proves the callback WAS reached (a counter), so this can't pass trivially by
    the callback never firing."""
    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(text="done", finish_reason="stop")

    calls: list[int] = []

    def boom(_ev: dict) -> None:
        calls.append(1)
        raise ValueError("bad callback")

    outcome = run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run, on_progress=boom,
    )
    assert outcome.status == "done"
    assert calls == [1]  # invoked once (and its raise swallowed) — not silently skipped


def test_on_progress_fires_on_capped_path(tmp_path: Path) -> None:
    """A run that exhausts max_turns (status='capped') still emits a progress event on
    each turn — the babysitting case that matters most (a run about to be capped)."""
    events: list[dict] = []

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        # always request a tool → never terminates on its own → hits max_turns
        return _result(
            tool_calls=[_tool_call("write_file", '{"path": "x.txt", "content": "hi"}')],
            finish_reason="tool_calls",
        )

    outcome = run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=3, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run, on_progress=events.append,
    )
    assert outcome.status == "capped"
    assert len(events) == 3  # one per turn, right up to the cap
    assert events[-1]["turns"] == 3


def test_extra_body_nested_cannot_clobber_tools(tmp_path: Path) -> None:
    """The loop is authoritative over `tools` EVEN against a nested OpenAI-SDK-style
    `extra_body` (the transport flattens it — the loop must flatten + re-own tools first)."""
    seen: dict = {}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=True, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run,
        # DOUBLE-nested: one-level flatten isn't enough (the transport flattens one level
        # too), so a leftover nested tools would survive — the fixed-point flatten must win.
        extra_body={"extra_body": {"extra_body": {"tools": "HACKED", "provider": {"only": ["X"]}}}},
    )
    assert seen["body"]["tools"] != "HACKED"
    assert isinstance(seen["body"]["tools"], list)      # loop's schemas win
    assert seen["body"]["provider"] == {"only": ["X"]}  # legit nested key still flattened
    assert "extra_body" not in seen["body"]             # ALL nesting flattened out


def test_extra_body_single_shot_cannot_leak_tools(tmp_path: Path) -> None:
    """tools_enabled=False (no advertised tools): a caller `tools` must be STRIPPED, not
    leaked to the API (the loop advertises none)."""
    seen: dict = {}

    def fake_run(model, messages, *, body=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="ok", finish_reason="stop")

    run_loop(
        model="fake/model", system="", task="t", workdir=str(tmp_path),
        tools_enabled=False, max_turns=2, max_cost_usd=None, wall_clock_s=60.0,
        run_fn=fake_run, extra_body={"tools": [{"x": 1}], "max_tokens": 500},
    )
    assert "tools" not in (seen["body"] or {})           # stripped
    assert seen["body"]["max_tokens"] == 500             # other keys survive


def test_invoke_loop_threads_body_and_progress() -> None:
    """AgentSpec.body → run_loop extra_body, and on_progress is forwarded."""
    from subagents.agent import AgentSpec, _invoke_loop

    captured: dict = {}

    def fake_loop(**kw):  # noqa: ANN003
        captured.update(kw)
        return LoopOutcome("", "done", 0, None, [])

    spec = AgentSpec(task="t", model="m", body={"max_tokens": 20000})
    cb = lambda e: None  # noqa: E731
    _invoke_loop(fake_loop, spec, "/wd", on_progress=cb)
    assert captured["extra_body"] == {"max_tokens": 20000}
    assert captured["on_progress"] is cb


# ---------------------------------------------------------------- MCP wiring
class _FakeMcpProvider:
    """Stand-in for mcp_tools.McpProvider (built in Phase A) — no real sessions."""

    def __init__(self) -> None:
        self.calls: list = []
        self.closed = False

    def tool_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "exa__web_search",
                    "description": "search",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    def tool_names(self) -> frozenset[str]:
        return frozenset({"exa__web_search"})

    def call(self, name, arguments):  # noqa: ANN001, ANN202
        from subagents.tools import ToolResult

        self.calls.append((name, arguments))
        return ToolResult(ok=True, output="hit")

    def close(self) -> None:
        self.closed = True


def test_mcp_tool_advertised_and_routed(tmp_path: Path) -> None:
    """SC1: an injected provider's tool is advertised + routed even with
    tools_enabled=False (the research config) — proving the MCP branch precedes the
    'file/command tools disabled' refusal. Provider is closed at loop end."""
    seen: dict = {}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        if not any(m.get("role") == "tool" for m in messages):
            return _result(
                tool_calls=[_tool_call("exa__web_search", '{"query":"x"}')],
                finish_reason="tool_calls",
            )
        return _result(text="done", finish_reason="stop")

    provider = _FakeMcpProvider()
    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,  # research config — file/command tools OFF
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        mcp_provider=provider,
    )
    names = {t["function"]["name"] for t in (seen["body"] or {}).get("tools", [])}
    assert "exa__web_search" in names  # advertised
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs and "hit" in tool_msgs[0]["content"]  # routed + result appended
    assert provider.calls == [("exa__web_search", {"query": "x"})]
    assert out.tool_calls.get("exa__web_search") == 1  # counted (successful call)
    assert provider.closed  # torn down on loop exit


def test_mcp_absent_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC3: build returns None (SDK/Node absent) → no mcp tools advertised, no crash."""
    monkeypatch.setattr("subagents.loop.build_mcp_provider", lambda *a, **k: None)
    seen: dict = {}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        seen["body"] = body
        return _result(text="done", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        mcp_servers=frozenset({"exa"}),
        mcp_config={"exa": {"command": "npx"}},
    )
    assert out.status == "done"
    names = {t["function"]["name"] for t in (seen["body"] or {}).get("tools", [])}
    assert not any(n.startswith("exa__") for n in names)


def test_mcp_unlisted_server_errors_money_safe(tmp_path: Path) -> None:
    """SC5-analogue: an unlisted server without mcp_allow_unlisted → run_loop returns
    status='error' (PermissionError caught) and NO transport call is made (money-safe)."""
    called = {"n": 0}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        called["n"] += 1
        return _result(text="x", finish_reason="stop")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=False,
        max_turns=8,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
        mcp_servers=frozenset({"filesystem"}),
        mcp_config={"filesystem": {"command": "npx"}},
        mcp_allow_unlisted=False,
    )
    assert out.status == "error"
    assert "unlisted" in (out.error or "").lower()
    assert called["n"] == 0  # refused before any paid transport call


def test_invoke_loop_forwards_mcp_fields() -> None:
    """AgentSpec's mcp_* knobs reach run_loop verbatim (the agent.py→loop.py contract)."""
    from subagents.agent import AgentSpec, _invoke_loop

    captured: dict = {}

    def fake_loop(**kw):  # noqa: ANN003, ANN202
        captured.update(kw)
        return LoopOutcome("", "done", 0, None, [])

    spec = AgentSpec(
        task="t",
        model="m",
        mcp_servers=frozenset({"exa"}),
        mcp_config={"exa": {"command": "npx"}},
        mcp_allow_unlisted=True,
    )
    _invoke_loop(fake_loop, spec, "/wd")
    assert captured["mcp_servers"] == frozenset({"exa"})
    assert captured["mcp_config"] == {"exa": {"command": "npx"}}
    assert captured["mcp_allow_unlisted"] is True


def test_run_loop_total_on_nondict_tool_call(tmp_path: Path) -> None:
    """A malformed non-dict entry in the transport's tool_calls must be skipped, not crash
    run_loop (regression: _normalize_tool_calls used to raise AttributeError on `.get`)."""

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        return _result(tool_calls=["not-a-dict"], finish_reason="tool_calls")

    out = run_loop(
        model="m",
        system="",
        task="x",
        workdir=str(tmp_path),
        tools_enabled=True,
        max_turns=2,
        max_cost_usd=None,
        wall_clock_s=60.0,
        run_fn=fake_run,
    )
    assert out.status == "done"  # malformed entry skipped → no tool calls → finishes cleanly


def test_out_tokens_summed_across_turns(tmp_path: Path) -> None:
    """output (completion) tokens accumulate across turns onto LoopOutcome.out_tokens."""
    calls = {"n": 0}

    def fake_run(model, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        calls["n"] += 1
        if calls["n"] == 1:
            r = _result(tool_calls=[_tool_call("list_dir", "{}")], finish_reason="tool_calls")
            r.usage = {"completion_tokens": 30}
            return r
        r = _result(text="done", finish_reason="stop")
        r.usage = {"completion_tokens": 12}
        return r

    out = run_loop(
        model="m", system="", task="x", workdir=str(tmp_path), tools_enabled=True,
        max_turns=4, max_cost_usd=None, wall_clock_s=60.0, run_fn=fake_run,
    )
    assert out.out_tokens == 42  # 30 + 12, summed across the two turns
