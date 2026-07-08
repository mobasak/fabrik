"""END-TO-END: prove a pool subagent can use EVERY tool it's given — for real, no mocks.

Three families, each exercised through the real code paths (the ``run_loop`` a subagent runs):

1. **MCP tools** — every tool a real ``npx`` MCP server (keyless ``server-everything``)
   advertises is called via the provider.
2. **File / command tools** — all six (``write_file`` / ``read_file`` / ``list_dir`` /
   ``grep`` / ``apply_patch`` / ``run_command``) driven through ``run_loop`` in a real
   worktree (``run_command`` is bubblewrap-sandboxed).
3. **Web research tools** — all five (Exa ``web_search``, Brave ``web_search_brave``,
   Firecrawl ``web_scrape`` / ``web_crawl``, Context7 ``docs_lookup``) hit the real hosted
   APIs — only when their ``*_API_KEY`` is in the env, else skipped.

The "model" is always a scripted fake (no paid OpenRouter call); everything the fake drives
is real. Opt-in via ``RUN_MCP_INTEGRATION=1`` so the fast unit gate stays deterministic::

    RUN_MCP_INTEGRATION=1 python -m pytest tests/test_all_tools_e2e.py -v -s
    # to include the paid web tools, also export the keys, e.g.:
    #   set -a; . /opt/fabrik/.env; set +a
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from typing import Any

import pytest

from subagents._transport import Result
from subagents.loop import run_loop
from subagents.tools import ToolResult


def _mcp_importable() -> bool:
    try:
        import mcp  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MCP_INTEGRATION") != "1"
    or shutil.which("npx") is None
    or not _mcp_importable(),
    reason="set RUN_MCP_INTEGRATION=1 with Node/npx + the mcp SDK to run the live E2E tests",
)

_EVERYTHING = {
    "everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}
}


def _result(*, text: str = "", tool_calls: list[dict] | None = None, finish: str = "stop") -> Result:
    return Result(
        text=text, tool_calls=tool_calls, model="fake/model", provider="fake", usage={},
        cost_usd=0.0, cost_unknown=False, finish_reason=finish, reasoning="", consult_id="",
    )


def _scripted_model(script: list[tuple[str, str]]):
    """A fake model that emits the scripted ``(tool_name, args_json)`` calls one per turn
    (keyed off how many tool results are already in the transcript), then finishes."""

    def model(model_name, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        done = sum(1 for m in messages if m.get("role") == "tool")
        if done < len(script):
            name, args = script[done]
            return _result(
                tool_calls=[{"id": f"c{done}", "function": {"name": name, "arguments": args}}],
                finish="tool_calls",
            )
        return _result(text="done", finish="stop")

    return model


# A `data:` URI carrying real content, valid for a `format: uri` string field.
_DATA_URI = "data:text/plain;base64," + base64.b64encode(b"hello from the pool").decode()

# Per-tool argument overrides where a generic value can't satisfy a specific constraint
# (keyed by the sanitized fn-name). The synthesizer can't know that gzip-file's `data` is a
# `format: uri` string that must be a real URL / data URI, not arbitrary text.
_ARG_OVERRIDES: dict[str, dict] = {
    "everything__gzip-file-as-resource": {"data": _DATA_URI, "outputType": "resource"},
}

# Tools that require an MCP client CAPABILITY this research-focused client does not negotiate
# (the "tasks"/task-augmentation lifecycle). They are correctly REACHABLE — the server reports
# the requirement and the provider surfaces it cleanly — but they are not plain synchronous
# calls, so we assert that graceful-capability-error rather than a result. Implementing MCP
# tasks for a demo-only tool would be YAGNI (no research server — exa/firecrawl/context7 —
# needs it).
_CAPABILITY_GATED: frozenset[str] = frozenset({"everything__simulate-research-query"})


def _synth_args(schema: dict) -> dict:
    """Synthesize a complete, valid argument dict from a tool's JSON-Schema parameters
    (enum → first value; ``format: uri`` string → a data URI; number → 2; bool → False;
    string → "test"; …)."""
    out: dict[str, Any] = {}
    for key, spec in schema.get("properties", {}).items():
        if not isinstance(spec, dict):
            out[key] = "test"
            continue
        if spec.get("enum"):
            out[key] = spec["enum"][0]
        elif spec.get("format") == "uri":
            out[key] = _DATA_URI
        elif spec.get("type") in ("number", "integer"):
            out[key] = 2
        elif spec.get("type") == "boolean":
            out[key] = False
        elif spec.get("type") == "array":
            out[key] = []
        elif spec.get("type") == "object":
            out[key] = {}
        else:
            out[key] = "test"
    return out


# ----------------------------------------------------------- 1. ALL MCP tools
def test_every_mcp_tool_is_callable() -> None:
    """Call EVERY tool the real MCP server advertises — each returns a proper ToolResult."""
    from subagents.mcp_tools import build_mcp_provider

    provider = build_mcp_provider(frozenset({"everything"}), _EVERYTHING, allow_unlisted=True)
    assert provider is not None, "server-everything failed to start (network / npx?)"
    try:
        schemas = {s["function"]["name"]: s["function"]["parameters"] for s in provider.tool_schemas()}
        assert len(schemas) >= 10, f"expected the full toolset, got {len(schemas)}"
        print(f"\n  driving all {len(schemas)} MCP tools:")
        results: dict[str, ToolResult] = {}
        for name in sorted(schemas):
            args = {**_synth_args(schemas[name]), **_ARG_OVERRIDES.get(name, {})}
            res = provider.call(name, args)
            results[name] = res
            snippet = (res.output or res.error or "").replace("\n", " ")[:60]
            print(f"    {'OK ' if res.ok else 'ERR'} {name} -> {snippet!r}")
        # EVERY tool is callable + TOTAL (returns a ToolResult, never crashes).
        assert all(isinstance(r, ToolResult) for r in results.values())
        # Every tool SUCCEEDS except the capability-gated ones — and those must fail for the
        # RIGHT reason (the server reporting the missing "tasks" capability), never a crash
        # or a bad-args error. This is the honest "all tools used properly": 12 return real
        # results; the 13th is correctly told it needs a client capability we don't provide.
        for name, r in results.items():
            if not r.ok:
                assert name in _CAPABILITY_GATED, f"{name} unexpectedly failed: {r.error}"
                assert "task" in (r.error or "").lower(), f"{name}: unexpected error {r.error}"
        ok = sum(r.ok for r in results.values())
        assert ok >= len(schemas) - len(_CAPABILITY_GATED), f"only {ok}/{len(schemas)} ok"
        # representative coverage across every result shape (text / numeric / structured /
        # image-as-non-text-block / no-arg / gzipped-resource) — each must genuinely succeed:
        for must in ("echo", "get-sum", "get-structured-content", "get-env",
                     "get-tiny-image", "gzip-file-as-resource"):
            fn = next(n for n in results if n.endswith("__" + must))
            assert results[fn].ok, f"{fn} should succeed"
    finally:
        provider.close()


def test_mcp_tool_through_run_loop() -> None:
    """The exact ``AgentSpec`` path: ``run_loop`` advertises the REAL MCP schemas and routes
    a call to the REAL server, with the result in the transcript (research config)."""
    def model(model_name, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        adv = {t["function"]["name"] for t in (body or {}).get("tools", [])}
        assert any(n.endswith("__echo") for n in adv), adv
        if not any(m.get("role") == "tool" for m in messages):
            echo = next(n for n in adv if n.endswith("__echo"))
            return _result(tool_calls=[{"id": "c1", "function": {"name": echo, "arguments": '{"message":"via the loop"}'}}], finish="tool_calls")
        return _result(text="done", finish="stop")

    with tempfile.TemporaryDirectory() as workdir:
        out = run_loop(
            model="fake/model", system="", task="echo", workdir=workdir, tools_enabled=False,
            max_turns=4, max_cost_usd=None, wall_clock_s=120.0, run_fn=model,
            mcp_servers=frozenset({"everything"}), mcp_config=_EVERYTHING, mcp_allow_unlisted=True,
        )
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert out.status == "done" and tool_msgs and "via the loop" in tool_msgs[0]["content"]
    assert any(k.endswith("__echo") for k in out.tool_calls)


# ------------------------------------------------- 2. ALL file/command tools
def test_every_file_and_command_tool_via_loop() -> None:
    """Drive all six file/command tools through run_loop in a real worktree — the exact
    path a coding subagent takes. run_command is bubblewrap-sandboxed."""
    if shutil.which("bwrap") is None:
        pytest.skip("bwrap absent — run_command would be refused (fail-closed)")

    patch = (
        "--- /dev/null\n"
        "+++ b/created_by_patch.txt\n"
        "@@ -0,0 +1 @@\n"
        "+made by apply_patch\n"
    )
    script = [
        ("write_file", '{"path": "greet.py", "content": "print(\'hello from run_command\')\\n"}'),
        ("read_file", '{"path": "greet.py"}'),
        ("list_dir", '{"path": "."}'),
        ("grep", '{"pattern": "hello", "path": "."}'),
        ("apply_patch", '{"patch": ' + _json_str(patch) + "}"),
        ("run_command", '{"cmd": "python greet.py"}'),
    ]
    with tempfile.TemporaryDirectory() as workdir:
        out = run_loop(
            model="fake/model", system="", task="exercise every file/command tool",
            workdir=workdir, tools_enabled=True, max_turns=10, max_cost_usd=None,
            wall_clock_s=120.0, run_fn=_scripted_model(script), sandbox=True,
        )
        tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
        used = out.tool_calls
        print("\n  file/command tools exercised:")
        for m in tool_msgs:
            print(f"    -> {m['content'].replace(chr(10), ' ')[:70]!r}")
        # every one of the six tools ran to SUCCESS (counted only on ok=True)
        for name, _ in script:
            assert used.get(name) == 1, f"{name} did not succeed (counts={used})"
        # and the chain really executed: run_command ran the file it wrote+patched
        assert any("hello from run_command" in m["content"] for m in tool_msgs)
        assert os.path.exists(os.path.join(workdir, "created_by_patch.txt"))


# --------------------------------------------------- 3. ALL web research tools
_WEB = [
    ("web_search", '{"query": "OpenRouter API pricing", "num_results": 3}', "EXA_API_KEY"),
    ("web_search_brave", '{"query": "Model Context Protocol", "num_results": 3}', "BRAVE_API_KEY"),
    ("web_scrape", '{"url": "https://example.com"}', "FIRECRAWL_API_KEY"),
    ("web_crawl", '{"url": "https://example.com", "limit": 1}', "FIRECRAWL_API_KEY"),
    ("docs_lookup", '{"library": "react", "query": "useEffect cleanup"}', "CONTEXT7_API_KEY"),
]


@pytest.mark.parametrize("tool,args,key", _WEB, ids=[w[0] for w in _WEB])
def test_each_web_tool_live(tool: str, args: str, key: str) -> None:
    """Each web research tool hits its REAL hosted API through run_loop — skipped unless
    its key is in the env (e.g. sourced from /opt/fabrik/.env)."""
    if not os.getenv(key):
        pytest.skip(f"{key} not set — export it to run the live {tool} call")

    captured: dict = {}

    def model(model_name, messages, *, body=None, liveness=None, **kw):  # noqa: ANN001, ANN002, ANN003
        captured["advertised"] = {t["function"]["name"] for t in (body or {}).get("tools", [])}
        if not any(m.get("role") == "tool" for m in messages):
            return _result(tool_calls=[{"id": "w1", "function": {"name": tool, "arguments": args}}], finish="tool_calls")
        return _result(text="done", finish="stop")

    with tempfile.TemporaryDirectory() as workdir:
        out = run_loop(
            model="fake/model", system="", task=f"use {tool}", workdir=workdir,
            tools_enabled=False, max_turns=4, max_cost_usd=None, wall_clock_s=90.0,
            run_fn=model, web_tools=frozenset({tool}),
        )
    assert tool in captured["advertised"]  # advertised to the model
    tool_msgs = [m for m in out.transcript if m.get("role") == "tool"]
    assert tool_msgs, "the web tool produced no result message"
    content = tool_msgs[0]["content"]
    print(f"\n  {tool} (live) -> {content.replace(chr(10), ' ')[:90]!r}")
    # a live call returns real content, not an error/'not enabled'
    assert not content.startswith("error:"), f"{tool} errored: {content[:120]}"
    assert out.tool_calls.get(tool) == 1  # counted as a real successful call


def _json_str(s: str) -> str:
    import json

    return json.dumps(s)
