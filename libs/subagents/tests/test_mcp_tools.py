"""Offline tests for the MCP provider (``mcp_tools``).

No real Node / `mcp` server is spawned — a **fake session** is injected via the
``build_mcp_provider(..., _connect=...)`` hook, so these run anywhere (SC1/SC2/SC3/SC4).
"""

from __future__ import annotations

import builtins
import json
import os
import re

import pytest

from subagents.mcp_tools import (
    SAFE_RESEARCH_SERVERS,
    build_mcp_provider,
    load_mcp_config,
    sanitize_fn_name,
)

_FN_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


# ---------------------------------------------------------------- sanitize (SC4)
def test_sanitize_hyphen_valid() -> None:
    out = sanitize_fn_name("brave-search", "web_search")
    assert out == "brave-search__web_search"
    assert _FN_RE.match(out)


def test_sanitize_dot_space_cleaned() -> None:
    out = sanitize_fn_name("my.server", "a b")
    assert _FN_RE.match(out)
    assert "." not in out and " " not in out


def test_sanitize_truncates_to_64() -> None:
    out = sanitize_fn_name("s" * 50, "t" * 50)
    assert len(out) <= 64
    assert _FN_RE.match(out)


# ------------------------------------------------------------- load_mcp_config
def test_load_config_dict_is_bare_map() -> None:
    cfg = {"exa": {"command": "npx", "args": ["-y", "exa-mcp-server"]}}
    assert load_mcp_config(cfg) == cfg


def test_load_config_path_unwraps_mcpservers(tmp_path) -> None:
    p = tmp_path / "mcp.json"
    p.write_text(json.dumps({"mcpServers": {"exa": {"command": "npx"}}}))
    assert load_mcp_config(str(p)) == {"exa": {"command": "npx"}}


def test_load_config_path_missing_wrapper_raises(tmp_path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"exa": {"command": "npx"}}))  # no mcpServers wrapper
    with pytest.raises(ValueError):
        load_mcp_config(str(p))


# ------------------------------------------------------ allowlist gate (SC2)
def test_unlisted_server_refused() -> None:
    with pytest.raises(PermissionError):
        build_mcp_provider(
            frozenset({"filesystem"}),
            {"filesystem": {"command": "npx", "args": ["-y", "@x/server-filesystem"]}},
            allow_unlisted=False,
        )


def test_unlisted_allowed_with_optout_does_not_raise() -> None:
    async def _fake_connect(name, server_def, stack):  # noqa: ANN001, ANN202
        raise RuntimeError("no server")  # forces skip → all-fail → None

    result = build_mcp_provider(
        frozenset({"filesystem"}),
        {"filesystem": {"command": "x"}},
        allow_unlisted=True,
        _connect=_fake_connect,
    )
    assert result is None  # connect failed → None, but NO PermissionError


def test_safe_servers_are_the_expected_four() -> None:
    assert SAFE_RESEARCH_SERVERS == frozenset(
        {"exa", "brave-search", "firecrawl", "context7"}
    )


def test_empty_servers_returns_none() -> None:
    assert build_mcp_provider(None, None) is None
    assert build_mcp_provider(frozenset(), {}) is None


# ----------------------------------------- fake session for the proxy tests
class _FakeTool:
    def __init__(self, name, description, input_schema):  # noqa: ANN001
        self.name = name
        self.description = description
        self.inputSchema = input_schema  # SDK attr is camelCase (grounded mcp 1.28.1)


class _FakeToolsResult:
    def __init__(self, tools):  # noqa: ANN001
        self.tools = tools


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):  # noqa: ANN001
        self.text = text


class _FakeCallResult:
    def __init__(self, text, is_error=False):  # noqa: ANN001
        self.content = [_FakeTextBlock(text)]
        self.isError = is_error


class _FakeSession:
    def __init__(self, tools, reply="hit"):  # noqa: ANN001
        self._tools = tools
        self._reply = reply
        self.calls: list = []

    async def list_tools(self):  # noqa: ANN202
        return _FakeToolsResult(self._tools)

    async def call_tool(self, name, args):  # noqa: ANN001, ANN202
        self.calls.append((name, args))
        return _FakeCallResult(self._reply)


# ------------------------------------------------------ provider proxy (SC1)
def test_provider_call_proxies_sc1() -> None:
    session = _FakeSession(
        [
            _FakeTool(
                "web_search",
                "search the web",
                {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            )
        ]
    )

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "npx"}}, _connect=_connect
    )
    assert provider is not None
    try:
        assert "exa__web_search" in provider.tool_names()
        # the input schema PAYLOAD propagates into the advertised function schema
        sch = next(
            s for s in provider.tool_schemas() if s["function"]["name"] == "exa__web_search"
        )
        assert sch["function"]["parameters"]["properties"] == {"query": {"type": "string"}}
        assert sch["function"]["parameters"]["required"] == ["query"]
        res = provider.call("exa__web_search", {"query": "x"})
        assert res.ok and "hit" in res.output
        # the REAL (un-prefixed) tool name is what reaches the server
        assert session.calls == [("web_search", {"query": "x"})]
        # an unknown fn name is a clean error, never a crash
        assert not provider.call("nope__nope", {}).ok
    finally:
        provider.close()


def test_provider_call_tool_error_flag() -> None:
    class _ErrSession(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            return _FakeCallResult("boom", is_error=True)

    session = _ErrSession([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "npx"}}, _connect=_connect
    )
    assert provider is not None
    try:
        res = provider.call("exa__t", {})
        assert not res.ok and "boom" in (res.error or "")
    finally:
        provider.close()


# --------------------------------------------------- absent-SDK fallback (SC3)
def test_absent_sdk_returns_none(monkeypatch) -> None:
    real_import = builtins.__import__

    def _no_mcp(name, *a, **k):  # noqa: ANN001, ANN202
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("no mcp")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_mcp)
    # no _connect → build hits the real `import mcp` guard → None (web_tools fallback)
    assert build_mcp_provider(frozenset({"exa"}), {"exa": {"command": "npx"}}) is None


# ---------------------------------------------- sanitize collision (keep both)
def test_sanitize_collision_keeps_both() -> None:
    session = _FakeSession(
        [_FakeTool("a.b", "d", {}), _FakeTool("a b", "d", {})]  # both → exa__a_b
    )

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "npx"}}, _connect=_connect
    )
    assert provider is not None
    try:
        names = provider.tool_names()
        assert len(names) == 2  # both kept, disambiguated — neither dropped
        reals = {provider._name_map[fn][1] for fn in names}
        assert reals == {"a.b", "a b"}  # each fn still routes to its REAL tool
    finally:
        provider.close()


def test_collision_disambiguation_stays_within_cap() -> None:
    """Many tools that all truncate to the SAME 64-char name must each get a distinct,
    still-≤64 fn name — including 2-digit suffixes (a 62-char base + `_10` = 65 would
    breach the OpenRouter function-name cap and 400 the whole tools array)."""
    prefix = "t" * 60  # 'exa__' + 60 chars > 64 → all truncate to the same name
    session = _FakeSession([_FakeTool(prefix + str(i), "d", {}) for i in range(12)])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        names = provider.tool_names()
        assert len(names) == 12  # all kept, none dropped
        assert all(len(n) <= 64 for n in names)  # cap honored even for 2-digit suffixes
        assert all(_FN_RE.match(n) for n in names)  # still valid charset
    finally:
        provider.close()


# ------------------------------------------------ call() TOTAL on a raise (SC)
def test_call_total_on_raise() -> None:
    class _RaiseSession(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            raise RuntimeError("network down")

    session = _RaiseSession([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "npx"}}, _connect=_connect
    )
    assert provider is not None
    try:
        res = provider.call("exa__t", {})  # must NOT raise into the loop
        assert not res.ok and "network down" in (res.error or "")
    finally:
        provider.close()


# -------------------------------------------------- _resolve_env expansion
def test_resolve_env_expands_and_none() -> None:
    from subagents.mcp_tools import _resolve_env

    os.environ["_MCP_TEST_KEY"] = "secret123"
    try:
        assert _resolve_env({"EXA_API_KEY": "${_MCP_TEST_KEY}"}) == {
            "EXA_API_KEY": "secret123"
        }
    finally:
        del os.environ["_MCP_TEST_KEY"]
    assert _resolve_env(None) is None
    assert _resolve_env({}) is None


# -------------------------------------------------- _extract_text labelling
def test_extract_text_labels_nontext() -> None:
    from subagents.mcp_tools import _extract_text

    class _Txt:
        type = "text"
        text = "hello"

    class _Img:
        type = "image"

    class _R:
        content = [_Txt(), _Img()]

    out = _extract_text(_R())
    assert "hello" in out and "non-text image" in out


# -------------------------------------------------- load_mcp_config errors
def test_load_config_non_object_file_raises(tmp_path) -> None:
    p = tmp_path / "arr.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError):
        load_mcp_config(str(p))


def test_load_config_bad_type_raises() -> None:
    with pytest.raises(ValueError):
        load_mcp_config(123)  # type: ignore[arg-type]


# ----------------------------------- _open_session real transport branches
class _FakeACM:
    def __init__(self, value):  # noqa: ANN001
        self._value = value

    async def __aenter__(self):  # noqa: ANN202
        return self._value

    async def __aexit__(self, *a):  # noqa: ANN002, ANN202
        return False


class _InitSession:
    def __init__(self):  # noqa: ANN204
        self.initialized = False

    async def initialize(self):  # noqa: ANN202
        self.initialized = True


def _run(coro):  # noqa: ANN001, ANN202
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_open_session_stdio_branch_expands_env() -> None:
    from contextlib import AsyncExitStack

    from subagents.mcp_tools import _open_session

    sess = _InitSession()
    seen: dict = {}

    def _stdio(params):  # noqa: ANN001, ANN202
        seen["params"] = params
        return _FakeACM(("R", "W"))

    def _params(**kw):  # noqa: ANN003, ANN202
        return kw

    def _client_session(read, write):  # noqa: ANN001, ANN202
        seen["rw"] = (read, write)
        return _FakeACM(sess)

    sdk = {
        "stdio_client": _stdio,
        "StdioServerParameters": _params,
        "ClientSession": _client_session,
        "streamablehttp_client": None,
    }
    os.environ["_MCP_ENV_T"] = "val9"

    async def go():  # noqa: ANN202
        async with AsyncExitStack() as stack:
            return await _open_session(
                {"command": "npx", "args": ["-y", "s"], "env": {"K": "${_MCP_ENV_T}"}},
                stack,
                sdk,
            )

    try:
        out = _run(go())
    finally:
        del os.environ["_MCP_ENV_T"]
    assert out is sess and sess.initialized
    assert seen["rw"] == ("R", "W")
    assert seen["params"]["env"] == {"K": "val9"}  # ${VAR} expanded, not inlined


def test_open_session_http_branch_ignores_third_tuple_item() -> None:
    from contextlib import AsyncExitStack

    from subagents.mcp_tools import _open_session

    sess = _InitSession()
    seen: dict = {}

    def _http(url):  # noqa: ANN001, ANN202
        seen["url"] = url
        return _FakeACM(("HR", "HW", "session-id"))  # 3-tuple

    def _client_session(read, write):  # noqa: ANN001, ANN202
        seen["rw"] = (read, write)
        return _FakeACM(sess)

    sdk = {
        "streamablehttp_client": _http,
        "ClientSession": _client_session,
        "stdio_client": None,
        "StdioServerParameters": None,
    }

    async def go():  # noqa: ANN202
        async with AsyncExitStack() as stack:
            return await _open_session({"url": "https://x/mcp"}, stack, sdk)

    out = _run(go())
    assert out is sess and sess.initialized
    assert seen["url"] == "https://x/mcp"
    assert seen["rw"] == ("HR", "HW")  # 3rd tuple item (session id) ignored


# ------------------------------- regression: one-task lifecycle (finding #1)
def test_all_session_ops_run_in_one_task() -> None:
    """The anyio cancel scopes require open, call_tool AND stack teardown to happen in
    the SAME task — else aclose() raises 'exit cancel scope in a different task' and the
    npx subprocess orphans (proven live vs mcp 1.28.1). This asserts the serve-task design
    keeps all three in one task; it FAILS on a run_until_complete-per-op design."""
    import asyncio

    seen_task: dict = {"list": None, "call": None, "aexit": None}

    class _TaskCM:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *a):  # noqa: ANN002, ANN204
            seen_task["aexit"] = id(asyncio.current_task())
            return False

    class _Tool:
        name, description, inputSchema = "t", "d", {}

    class _ToolsResult:
        tools = [_Tool()]

    class _Res:
        content: list = []
        isError = False

    class _TaskSession:
        async def list_tools(self):  # noqa: ANN202
            seen_task["list"] = id(asyncio.current_task())
            return _ToolsResult()

        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            seen_task["call"] = id(asyncio.current_task())
            return _Res()

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        await stack.enter_async_context(_TaskCM())  # entered in the serve task
        return _TaskSession()

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    provider.call("exa__t", {})
    provider.close()
    assert seen_task["list"] is not None
    assert seen_task["list"] == seen_task["call"] == seen_task["aexit"]


def test_hung_call_bounded_serve_task_recovers(monkeypatch) -> None:
    """A hung `call_tool` is cancelled IN the serve task (not just the caller), so it
    can't wedge the task — a later call still runs promptly. Regression for finding #1's
    'the 120s caller timeout leaves the serve task blocked forever' variant."""
    import asyncio
    import time

    monkeypatch.setattr("subagents.mcp_tools._CALL_TIMEOUT_S", 0.2)

    class _SlowSession(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            if args.get("slow"):
                await asyncio.sleep(5)  # >> the 0.2s in-task bound
            return _FakeCallResult("fast-ok")

    session = _SlowSession([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        slow = provider.call("exa__t", {"slow": True})
        assert not slow.ok  # bounded → error, not a hang
        t0 = time.monotonic()
        fast = provider.call("exa__t", {})  # serve task must be free already
        assert fast.ok and "fast-ok" in fast.output
        assert time.monotonic() - t0 < 2.0  # NOT blocked behind the 5s hung call
    finally:
        provider.close()


def test_mcp_schema_passes_inputschema_verbatim() -> None:
    """A tool's inputSchema (incl. $defs/$ref/additionalProperties) is advertised VERBATIM
    as function.parameters — NOT reprojected through _fn (which drops root keywords + forces
    additionalProperties:false, breaking $ref tools like firecrawl scrape/extract)."""
    rich = {
        "type": "object",
        "properties": {"q": {"$ref": "#/$defs/Q"}},
        "required": ["q"],
        "$defs": {"Q": {"type": "string"}},
        "additionalProperties": True,
    }
    session = _FakeSession([_FakeTool("t", "d", rich)])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        sch = next(
            s for s in provider.tool_schemas() if s["function"]["name"] == "exa__t"
        )
        assert sch["function"]["parameters"] == rich  # $defs/$ref/addlProps all preserved
    finally:
        provider.close()


def test_structured_content_fallback() -> None:
    """A structured-output tool that returns only ``structuredContent`` (empty ``content``)
    must not be delivered as "(no content)" — fall back to the JSON of the structured data."""

    class _StructResult:
        content: list = []
        isError = False
        structuredContent = {"answer": 42}

    class _StructSession(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            return _StructResult()

    session = _StructSession([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        res = provider.call("exa__t", {})
        assert res.ok and "answer" in res.output and "42" in res.output
    finally:
        provider.close()


def test_malformed_tool_skipped_not_fatal() -> None:
    """A tool with a bad (None) name is skipped, not fatal — the server's good tools (and
    every OTHER server) survive. Guards the per-tool isolation + name validation."""
    session = _FakeSession([_FakeTool(None, "d", {}), _FakeTool("good", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None  # build did NOT fail on the bad tool
    try:
        names = provider.tool_names()
        assert "exa__good" in names  # good tool kept
        assert not any("None" in n for n in names)  # bad tool skipped, not routed as None
    finally:
        provider.close()


def test_teardown_bounded_on_hung_aclose(monkeypatch) -> None:
    """close() must not block on a session that hangs during teardown — the stack unwind
    is time-bounded so the thread/loop are freed even if a pathological server ignores
    shutdown. Regression for the unbounded-aclose leak on the close edge."""
    import asyncio
    import time

    monkeypatch.setattr("subagents.mcp_tools._CLOSE_TIMEOUT_S", 0.3)

    class _HangCM:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *a):  # noqa: ANN002, ANN204
            await asyncio.sleep(10)  # hangs on teardown
            return False

    session = _FakeSession([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        await stack.enter_async_context(_HangCM())
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    t0 = time.monotonic()
    provider.close()  # must NOT wait the full 10s hung aclose
    assert time.monotonic() - t0 < 3.0  # bounded by _CLOSE_TIMEOUT_S (+ join)


def test_non_object_schema_falls_back() -> None:
    """A non-object-root inputSchema (spec-violating) falls back to a safe default so it
    can't 400 the whole tools array; a proper object schema is still passed verbatim."""
    session = _FakeSession(
        [
            _FakeTool("arr", "d", {"type": "array", "items": {"type": "string"}}),
            _FakeTool("obj", "d", {"type": "object", "properties": {"x": {"type": "string"}}}),
        ]
    )

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        params = {
            s["function"]["name"]: s["function"]["parameters"]
            for s in provider.tool_schemas()
        }
        assert params["exa__arr"] == {"type": "object", "properties": {}}  # fell back (safe)
        assert params["exa__obj"]["properties"] == {"x": {"type": "string"}}  # verbatim
    finally:
        provider.close()


def test_structured_content_unserializable_is_total() -> None:
    """A structuredContent whose json.dumps raises a non-(TypeError/ValueError) (e.g. a
    RuntimeError from default=str) must NOT escape call() — _extract_text is TOTAL."""

    class _Bad:
        def __str__(self):  # noqa: ANN204 — default=str raises → not TypeError/ValueError
            raise RuntimeError("boom")

    class _R:
        content: list = []
        isError = False
        structuredContent = {"x": _Bad()}

    class _S(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            return _R()

    session = _S([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        res = provider.call("exa__t", {})  # must NOT raise (was: RuntimeError escaped)
        assert res.ok  # total — returns a result even if the payload was undumpable
    finally:
        provider.close()


def test_call_total_on_nonlist_content() -> None:
    """A CallToolResult whose ``.content`` is a non-list (int) must not raise out of call()
    — the content iteration is guarded. Regression for the _extract_text totality gap."""

    class _WeirdResult:
        content = 42  # non-list, non-iterable
        isError = False
        structuredContent = None

    class _S(_FakeSession):
        async def call_tool(self, name, args):  # noqa: ANN001, ANN202
            return _WeirdResult()

    session = _S([_FakeTool("t", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is not None
    try:
        res = provider.call("exa__t", {})  # must NOT raise
        assert res.ok  # "(no content)" — total
    finally:
        provider.close()


def test_zero_usable_tools_returns_none() -> None:
    """A server that connects but exposes only bad-name (unusable) tools yields NO usable
    tool → build returns None (no idle provider/npx held), falling back to web_tools."""
    session = _FakeSession([_FakeTool(None, "d", {}), _FakeTool("", "d", {})])

    async def _connect(name, server_def, stack):  # noqa: ANN001, ANN202
        return session

    provider = build_mcp_provider(
        frozenset({"exa"}), {"exa": {"command": "x"}}, _connect=_connect
    )
    assert provider is None  # zero usable tools → None, not an idle provider
