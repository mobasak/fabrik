"""The saas-skeleton chat client speaks the backend chat route's contract (W-ab242b11 slice 2, Phase C).

Spec § Chosen approach, Client, names what ``components/chat/SSEStream.tsx`` owes the backend's
``POST /api/v1/chat``:
- the session cookie and the CSRF header, read from either cookie name;
- one refresh on a 401, whose retry re-reads the rotated CSRF cookie, and a second 401 shown as
  signed out;
- a frame cut across network chunks (a multi-byte character included) never dropped;
- one ``onComplete`` on every path;
- a 429's ``Retry-After`` and a refusal's ``detail`` shown.

These are proven by EXECUTING the hook, not by matching its source: the hook's logic (everything
above the first component) is run under node's type stripping with stubbed ``fetch``,
``document.cookie`` and React, against scripted backend replies. A regex grader of the same claims
was vacuous in review (a removed refresh call, a dropped buffer carry and a commented-out
``onComplete`` all passed it), so behaviour is what is asserted.

``ChatUI.tsx`` needs a React renderer to execute, so its wiring stays a source check, made
comment-blind and scoped to the hook call, with five plausible spellings it must accept and two
broken ones it must refuse (``45-testing-strategy.md`` § BANNED in tests). The rendered messages
themselves are the project's own front-end tests (spec § Validation, The template grader).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

CHAT = (
    Path(__file__).resolve().parent.parent / "templates" / "saas-skeleton" / "components" / "chat"
)

# React stand-ins: each useState slot records its last value, useCallback returns its function.
_STUBS = """const __state: unknown[] = [];
function useState<T>(init: T): [T, (v: unknown) => void] {
  const i = __state.length;
  __state.push(init);
  return [init, (v: unknown) => {
    __state[i] = typeof v === "function" ? (v as (p: unknown) => unknown)(__state[i]) : v;
  }];
}
function useCallback<F>(f: F, _deps: unknown[]): F { return f; }
"""

# The scenarios, run in order against `useSSEStream` from the extracted hook logic.
_DRIVER = r"""// Driver appended after the extracted hook logic. Scenarios run in order; each prints one result.
type Call = { url: string; init: RequestInit & { headers?: Record<string, string> } };

const enc = new TextEncoder();
function streamOf(chunks: Array<string | Uint8Array>): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(c) {
      for (const ch of chunks) c.enqueue(typeof ch === "string" ? enc.encode(ch) : ch);
      c.close();
    },
  });
}
function sse(chunks: Array<string | Uint8Array>): Response {
  return new Response(streamOf(chunks), { status: 200, headers: { "content-type": "text/event-stream" } });
}
let bodiesCancelled = 0;
function counted401(): Response {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(enc.encode('{"detail":"expired"}'));
    },
    cancel() {
      bodiesCancelled += 1;
    },
  });
  return new Response(body, { status: 401, headers: { "content-type": "application/problem+json" } });
}
// a normal answer: some text, then done
const reply = (): Response => sse(['data: {"type":"text_delta","text":"ok"}\n\ndata: {"type":"done"}\n\n']);
function problem(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/problem+json", ...headers } });
}

let cancelled = 0;
function openSse(chunks: string[]): Response {
  // a stream that stays open after its chunks, like a model still generating
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch));
      setTimeout(() => { try { c.close(); } catch { /* already cancelled */ } }, 200); // never hangs a client that fails to cancel
    },
    cancel() {
      cancelled += 1;
    },
  });
  return new Response(body, { status: 200 });
}

async function run(
  cookie: string,
  replies: Array<Response | Error | ((c: Call) => Response)>,
  onEvent?: () => void,
) {
  (globalThis as { document?: { cookie: string } }).document = { cookie };
  const calls: Call[] = [];
  const queue = [...replies];
  (globalThis as { fetch?: unknown }).fetch = async (url: string, init: Call["init"]) => {
    calls.push({ url, init });
    const next = queue.shift();
    if (next === undefined) throw new Error("no reply queued");
    if (next instanceof Error) throw next;
    return typeof next === "function" ? next({ url, init }) : next;
  };
  const completes: string[] = [];
  const errors: string[] = [];
  __state.length = 0;
  const { startStream } = useSSEStream({
    onComplete: (t: string) => completes.push(t),
    onError: (e: string) => errors.push(e),
    onEvent,
  });
  await startStream("/api/v1/chat", { message: "hi" });
  const [isStreaming, streamText, toolCalls] = __state;
  return {
    calls: calls.map((c) => ({
      url: c.url,
      credentials: c.init.credentials ?? null,
      csrf: (c.init.headers ?? {})["X-CSRF-Token"] ?? null,
      body: c.init.body ?? null,
    })),
    completes,
    errors,
    state: { isStreaming, streamText, toolCalls },
  };
}

const rotate = (c: Call): Response => {
  (globalThis as { document?: { cookie: string } }).document = { cookie: "__Host-csrf_token=rotated" };
  return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
};
const e = enc.encode("é"); // two bytes, split across chunks below
const results: Record<string, unknown> = {
  stream: await run("theme=dark; __Host-csrf_token=tok%3D1", [
    sse([
      'data: {"type":"text_delta","text":"H',
      new Uint8Array([...enc.encode('"}\n\ndata: {"type":"text_delta","text":"'), e[0]]),
      new Uint8Array([e[1], ...enc.encode('llo"}\n\ndata: {"type":"do')]),
      'ne"}\n\n',
    ]),
  ]),
  plain_cookie: await run("xcsrf_token=no; csrf_token=abc", [reply()]),
  refresh_then_ok: await run("__Host-csrf_token=old", [problem(401, { detail: "x" }), rotate, reply()]),
  refresh_refused: await run("__Host-csrf_token=old", [problem(401, { detail: "x" }), problem(401, { detail: "x" })]),
  retry_401: await run("__Host-csrf_token=old", [problem(401, { detail: "x" }), rotate, problem(401, { detail: "x" })]),
  limited: await run("csrf_token=a", [problem(429, { detail: "Rate limit reached (user)" }, { "Retry-After": "30" })]),
  csrf_403: await run("csrf_token=a", [new Response(JSON.stringify({ detail: "Missing or invalid CSRF token" }), { status: 403 })]),
  error_frame: await run("csrf_token=a", [sse(['data: {"type":"error","error":"The model took too long to respond"}\n\n'])]),
  network: await run("csrf_token=a", [new Error("connection reset")]),
  crlf: await run("csrf_token=a", [sse(['data: {"type":"text_delta","text":"ok"}\r\n\r\ndata: {"type":"done"}\r\n\r\n'])]),
  quoted_cookie: await run('csrf_token="abc"', [reply()]),
  both_cookies: await run("csrf_token=plain; __Host-csrf_token=host", [reply()]),
  unterminated: await run("csrf_token=a", [sse(['data: {"type":"text_delta","text":"last"}'])]),
  tools: await run("csrf_token=a", [
    sse([
      'data: {"type":"tool_call","tool":"search"}\n\ndata: {"type":"tool_call","tool":"grep"}\n\n',
      'data: {"type":"tool_result"}\n\ndata: {"type":"text_delta","text":"done"}\n\ndata: {"type":"done"}\n\n',
    ]),
  ]),
  empty_reply: await run("csrf_token=a", [sse(['data: {"type":"done"}\n\n'])]),
  refresh_bounded: await (async () => {
    let signalled = false;
    (globalThis as { document?: { cookie: string } }).document = { cookie: "csrf_token=a" };
    (globalThis as { fetch?: unknown }).fetch = async (url: string, init: RequestInit) => {
      if (url === "/auth/refresh") signalled = init.signal instanceof AbortSignal;
      return problem(401, { detail: "x" });
    };
    await useSSEStream({}).startStream("/api/v1/chat", { message: "hi" });
    return { signalled };
  })(),
  first_401_body: await (async () => {
    bodiesCancelled = 0;
    const r = await run("csrf_token=a", [counted401(), rotate, reply()]);
    return { ...r, bodiesCancelled };
  })(),
  refresh_throws: await run("csrf_token=a", [problem(401, { detail: "x" }), new Error("offline")]),
  bad_frame: await run("csrf_token=a", [
    sse(['data: {"type":"text_delta","text":5}\n\ndata: [1]\n\ndata: {"type":"text_delta","text":"ok"}\n\ndata: {"type":"done"}\n\n']),
  ]),
  handler_throws: await (async () => {
    cancelled = 0;
    const r = await run("csrf_token=a", [openSse(['data: {"type":"text_delta","text":"a"}\n\n'])], () => {
      throw new Error("handler bug");
    });
    return { ...r, cancelled };
  })(),
  concurrent_401: await (async () => {
    (globalThis as { document?: { cookie: string } }).document = { cookie: "csrf_token=old" };
    let refreshes = 0;
    (globalThis as { fetch?: unknown }).fetch = async (url: string) => {
      if (url === "/auth/refresh") {
        refreshes += 1;
        await new Promise((r) => setTimeout(r, 20));
        (globalThis as { document?: { cookie: string } }).document = { cookie: "csrf_token=new" };
        return new Response("{}", { status: 200 });
      }
      const cookie = (globalThis as { document?: { cookie: string } }).document?.cookie ?? "";
      return cookie.endsWith("new") ? reply() : problem(401, { detail: "x" });
    };
    const errors: string[] = [];
    const a = useSSEStream({ onError: (e: string) => errors.push(e) });
    const b = useSSEStream({ onError: (e: string) => errors.push(e) });
    await Promise.all([a.startStream("/api/v1/chat", { message: "a" }), b.startStream("/api/v1/chat", { message: "b" })]);
    return { refreshes, errors };
  })(),
};
console.log(JSON.stringify(results));
"""


def _node_strips_types() -> bool:
    # `--experimental-strip-types` arrived in node 22.6
    node = shutil.which("node")
    if node is None:
        return False
    out = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout
    match = re.match(r"v(\d+)\.(\d+)", out.strip())
    return bool(match) and (int(match.group(1)), int(match.group(2))) >= (22, 6)


def _hook_logic(source: str) -> str:
    # The hook ends where the first JSX component's icon table starts; imports become the stubs.
    logic = source[: source.index("const toolIcons")]
    logic = re.sub(r'^"use client";\n', "", logic)
    return re.sub(r"^import .*\n", "", logic, flags=re.MULTILINE)


def _run_hook(source: str, tmp_path: Path) -> dict:
    script = tmp_path / "hook.mts"
    script.write_text(_STUBS + _hook_logic(source) + _DRIVER)
    out = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def hook(tmp_path_factory: pytest.TempPathFactory) -> dict:
    if not _node_strips_types():
        pytest.skip(
            "node >= 22.6 (type stripping) is not installed; the hook is proven only by running it"
        )
    return _run_hook((CHAT / "SSEStream.tsx").read_text(), tmp_path_factory.mktemp("sse"))


def test_every_request_sends_the_session_cookie_and_the_csrf_header(hook):
    assert [c["credentials"] for c in hook["stream"]["calls"]] == ["same-origin"]
    # the raw value, as the server compares it (no URL-decoding), quotes stripped
    assert hook["stream"]["calls"][0]["csrf"] == "tok%3D1"
    assert hook["quoted_cookie"]["calls"][0]["csrf"] == "abc"
    assert hook["plain_cookie"]["calls"][0]["csrf"] == "abc"  # the plain name; xcsrf_token ignored


def test_a_401_refreshes_once_and_the_retry_reads_the_rotated_token(hook):
    calls = hook["refresh_then_ok"]["calls"]
    assert [c["url"] for c in calls] == ["/api/v1/chat", "/auth/refresh", "/api/v1/chat"]
    assert [c["csrf"] for c in calls] == ["old", "old", "rotated"]
    assert all(c["credentials"] == "same-origin" for c in calls)
    assert calls[2]["body"] == calls[0]["body"]
    assert hook["refresh_then_ok"]["errors"] == []


@pytest.mark.parametrize("case", ["refresh_refused", "retry_401", "refresh_throws"])
def test_a_second_401_is_shown_as_signed_out_and_never_loops(hook, case):
    result = hook[case]
    assert len(result["calls"]) <= 3
    assert len(result["errors"]) == 1 and "signed out" in result["errors"][0].lower()


def test_the_https_cookie_name_wins_when_both_are_set(hook):
    assert hook["both_cookies"]["calls"][0]["csrf"] == "host"


def test_a_last_frame_without_a_newline_is_still_delivered(hook):
    assert hook["unterminated"]["completes"] == ["last"]


def test_the_hook_state_tracks_the_stream(hook):
    # what ChatUI renders: the streamed text, the tool indicators, and streaming switched off
    state = hook["tools"]["state"]
    assert state["streamText"] == "done" and state["isStreaming"] is False
    assert state["toolCalls"] == [
        {"tool": "search", "status": "running"},
        {"tool": "grep", "status": "done"},
    ]
    for case in ("refresh_refused", "network", "handler_throws"):
        assert hook[case]["state"]["isStreaming"] is False, case


def test_a_reply_with_no_text_and_no_error_says_so(hook):
    # a reasoning model capped by CHAT_MAX_TOKENS can answer with nothing; the user is told
    result = hook["empty_reply"]
    assert result["completes"] == [""] and len(result["errors"]) == 1
    assert "empty" in result["errors"][0].lower()


def test_the_refresh_request_is_bounded(hook):
    # a hung /auth/refresh would hold the page-wide single flight, and every stream with it
    assert hook["refresh_bounded"] == {"signalled": True}


def test_the_refused_401_body_is_released_before_the_retry(hook):
    assert hook["first_401_body"]["bodiesCancelled"] == 1


def test_a_frame_cut_across_chunks_is_delivered_once(hook):
    # a frame split mid-JSON and mid-character ("é" across two chunks), and CRLF line endings
    assert hook["stream"]["completes"] == ["Héllo"] and hook["stream"]["errors"] == []
    assert hook["crlf"]["completes"] == ["ok"]


@pytest.mark.parametrize(
    "case",
    [
        "stream",
        "plain_cookie",
        "refresh_then_ok",
        "refresh_refused",
        "retry_401",
        "limited",
        "csrf_403",
        "error_frame",
        "network",
        "crlf",
        "quoted_cookie",
        "refresh_throws",
        "bad_frame",
        "both_cookies",
        "unterminated",
        "tools",
        "first_401_body",
        "empty_reply",
    ],
)
def test_on_complete_fires_exactly_once_on_every_path(hook, case):
    assert len(hook[case]["completes"]) == 1


def test_a_429_shows_its_retry_after_and_names_the_bucket(hook):
    assert len(hook["limited"]["errors"]) == 1
    assert "30" in hook["limited"]["errors"][0] and "(user)" in hook["limited"]["errors"][0]


def test_a_malformed_frame_is_never_appended(hook):
    assert hook["bad_frame"]["completes"] == ["ok"]


def test_a_throwing_handler_cancels_the_stream(hook):
    # an open response body would keep the backend relaying (and spending) to max_tokens
    result = hook["handler_throws"]
    assert result["cancelled"] == 1 and result["errors"] == ["handler bug"]
    assert len(result["completes"]) == 1


def test_two_streams_that_both_get_a_401_share_one_refresh(hook):
    # the backend rotates a refresh token once; a second concurrent refresh would lose and sign out
    assert hook["concurrent_401"] == {"refreshes": 1, "errors": []}


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("csrf_403", "Missing or invalid CSRF token"),
        ("error_frame", "The model took too long to respond"),
        ("network", "connection reset"),
    ],
)
def test_a_refusal_or_failure_reaches_on_error(hook, case, message):
    assert hook[case]["errors"] == [message]


def test_the_hook_harness_fails_on_the_pre_slice_2_client(tmp_path):
    # the client before this slice sent no credentials and no CSRF header: the harness must see it
    if not _node_strips_types():
        pytest.skip("node >= 22.6 (type stripping) is not installed")
    old = (
        "export function useSSEStream(options: { onComplete?: (t: string) => void; onError?: (e: string) => void } = {}) {\n"
        "  const startStream = async (url: string, body: Record<string, unknown>) => {\n"
        "    try {\n"
        '      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });\n'
        "      if (!r.ok) throw new Error(`HTTP ${r.status}`);\n"
        "      options.onComplete?.(await r.text());\n"
        "    } catch (e) { options.onError?.(String(e)); }\n"
        "  };\n"
        "  return { startStream };\n"
        "}\n"
        "const toolIcons = {};\n"
    )
    result = _run_hook(old, tmp_path)
    assert result["stream"]["calls"][0]["credentials"] is None
    assert result["stream"]["calls"][0]["csrf"] is None


_SETTLE_DRIVER = """
const user = { id: "u", role: "user" as const, content: "hi" };
const pending = { id: "a", role: "assistant" as const, content: "" };
const before = [user, pending];
const filled = settleReply(before, "Hello");
console.log(JSON.stringify({
  filled,
  emptied: settleReply(before, ""),
  untouched: settleReply([user], "x"),
  pendingKept: pending.content,
}));
"""


def test_a_finished_reply_fills_the_bubble_and_an_empty_one_is_dropped(tmp_path):
    """Plan § Phase C Behaviour Contract: a refusal or error shows its message, never an empty
    reply. Executed: everything above the component in ChatUI.tsx runs under node."""
    if not _node_strips_types():
        pytest.skip("node >= 22.6 (type stripping) is not installed")
    source = (CHAT / "ChatUI.tsx").read_text()
    head = source[: source.index("export function ChatUI")]
    head = re.sub(r'^"use client";\n', "", head)
    head = re.sub(r"^import .*\n", "", head, flags=re.MULTILINE)
    script = tmp_path / "settle.mts"
    script.write_text(head + _SETTLE_DRIVER)
    out = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert [m["content"] for m in result["filled"]] == ["hi", "Hello"]
    assert [m["role"] for m in result["emptied"]] == ["user"]
    assert [m["content"] for m in result["untouched"]] == ["hi"]
    assert result["pendingKept"] == "", "the previous state's message is never mutated"


# --- ChatUI: a source check, comment-blind and scoped to the hook call ------------------------

_COMMENTS = re.compile(r"/\*.*?\*/|(?<![:\"'`])//[^\n]*|\{/\*.*?\*/\}", re.DOTALL)
_STATE = re.compile(r"const\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState\b")
_NEXT_KEY = re.compile(r"\bon[A-Z]\w*\s*[:(]")


def _hook_options(text: str) -> str:
    # the object literal passed to useSSEStream({...}), by brace matching
    start = text.find("useSSEStream(")
    if start < 0:
        return ""
    open_at = text.find("{", start)
    depth = 0
    for i in range(open_at, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[open_at : i + 1]
    return ""


def _renders_the_error(text: str) -> bool:
    # onError stores its message in state and the JSX after the hook call renders that state
    code = _COMMENTS.sub("", text)
    options = _hook_options(code)
    at = options.find("onError")
    if at < 0:
        return False
    rest = options[at + len("onError") :]
    following = _NEXT_KEY.search(rest)
    handler = rest[: following.start()] if following else rest
    after_hook = code[code.find("useSSEStream(") :]
    for value, setter in _STATE.findall(code):
        if re.search(rf"\b{setter}\b", handler) and re.search(rf"\{{\s*{value}\b", after_hook):
            return True
    return False


RENDER_SPELLINGS = [
    "const [error, setError] = useState<string | null>(null);\n"
    "const s = useSSEStream({ onError: (m) => setError(m) });\nreturn (<p>{error}</p>);",
    'const [err, setErr] = useState("");\n'
    "const s = useSSEStream({ onComplete: done, onError: setErr });\nreturn (<div>{err && <p>{err}</p>}</div>);",
    "const [problem, setProblem] = useState<string>();\n"
    "const s = useSSEStream({ onError(message) { setProblem(message); } });\nreturn (<span>{ problem }</span>);",
    "const [notice, setNotice] = useState<string | null>(null);\n"
    "// onError shows a notice\n"
    "const s = useSSEStream({ onError: (e: string) => { setNotice(e); } });\n"
    "return (<>{notice ? <p>{notice}</p> : null}{items.map((i) => { return (<li>{i}</li>); })}</>);",
    'const [ failure , setFailure ] = useState("");\n'
    "const s = useSSEStream({\n  onError: (text) => setFailure(text),\n});\nreturn (\n  <p>{failure}</p>\n);",
]
RENDER_BROKEN = [
    "const [error, setError] = useState<string | null>(null);\n"
    "const s = useSSEStream({ onError: () => {}, onComplete: () => setError(null) });\nreturn (<p>{error}</p>);",
    "const [error, setError] = useState<string | null>(null);\n"
    "const s = useSSEStream({ onError: (m) => setError(m) });\nreturn (<p>{/* {error} */}</p>);",
]


def test_the_chat_ui_renders_what_the_stream_reports():
    assert _renders_the_error((CHAT / "ChatUI.tsx").read_text())


def test_the_render_check_accepts_five_spellings_and_refuses_two_broken_ones():
    caught = [s for s in RENDER_SPELLINGS if _renders_the_error(s)]
    assert len(RENDER_SPELLINGS) == 5 and caught == RENDER_SPELLINGS, f"caught {len(caught)} of 5"
    assert not [s for s in RENDER_BROKEN if _renders_the_error(s)]


@pytest.mark.parametrize("name", ["SSEStream.tsx", "ChatUI.tsx"])
def test_the_client_names_neither_the_model_service_nor_the_deleted_route(name):
    text = (CHAT / name).read_text()
    assert "openrouter" not in text.lower() and "api/chat" not in text
