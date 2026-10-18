"""The saas-skeleton chat client speaks the backend chat route's contract (W-ab242b11 slice 2, Phase C).

A source grader over ``components/chat/SSEStream.tsx`` and ``ChatUI.tsx``: it proves the wiring is
present, not the rendered text, which is the project's own front-end tests' job (spec § Validation,
The template grader). Spec § Chosen approach, Client, names what the client owes the backend's
``POST /api/v1/chat``: the session cookie and the CSRF header, one refresh on a 401, a frame cut
across network chunks never dropped, one ``onComplete``, and a 429's ``Retry-After`` shown.

Each check is a predicate, not one fixed string, and ``SPELLINGS`` carries five ways a different
author would plausibly write the same wiring (``.windsurf/rules/core/45-testing-strategy.md`` §
BANNED in tests); ``test_each_check_catches_its_five_spellings`` reports how many each one catches.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

CHAT = (
    Path(__file__).resolve().parent.parent / "templates" / "saas-skeleton" / "components" / "chat"
)

_I = re.IGNORECASE


def _has(pattern: str, flags: int = 0) -> Callable[[str], bool]:
    return lambda text: re.search(pattern, text, flags) is not None


def _sends_credentials(text: str) -> bool:
    return _has(r"credentials\s*:\s*[\"'`]same-origin[\"'`]")(text)


def _sends_csrf_header(text: str) -> bool:
    # the header's value is a call, so every attempt (the retry included) reads the cookie afresh
    return _has(r"x-csrf-token[\"'`]\s*[:,]\s*[\w.]+\(", _I)(text)


def _reads_both_cookie_names(text: str) -> bool:
    return "__Host-" in text and "csrf_token" in text


def _refreshes_once_on_401(text: str) -> bool:
    return text.count("/auth/refresh") == 1 and _has(r"[!=]==?\s*401\b")(text)


def _shows_signed_out(text: str) -> bool:
    return _has(r"sign(?:ed)?[\s-]?(?:in|out)", _I)(text)


def _decodes_as_a_stream(text: str) -> bool:
    return _has(r"stream\s*:\s*true")(text)


def _carries_a_partial_line(text: str) -> bool:
    return _has(r"\.pop\(\)|\.lastIndexOf\(|\.splice\(\s*-1")(text)


_ON_COMPLETE_CALL = re.compile(r"\bonComplete\s*(?:\?\.)?\s*\(")


def _calls_on_complete_once(text: str) -> bool:
    return len(_ON_COMPLETE_CALL.findall(text)) == 1


def _shows_retry_after(text: str) -> bool:
    return "429" in text and _has(r"\.get\(\s*[\"'`]retry-after[\"'`]\s*\)", _I)(text)


def _reads_the_error_detail(text: str) -> bool:
    return _has(r"\.detail\b|\[\s*[\"'`]detail[\"'`]\s*\]")(text)


_STATE = re.compile(r"const\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState\b")


def _renders_the_error(text: str) -> bool:
    """``onError`` stores its message in state and the JSX renders that state: a no-op handler fails."""
    at = text.find("onError")
    jsx = text.rfind("return (")
    if at < 0 or jsx < 0:
        return False
    handler = text[at : at + 240]
    for value, setter in _STATE.findall(text):
        if re.search(rf"\b{setter}\b", handler) and re.search(rf"\{{\s*{value}\b", text[jsx:]):
            return True
    return False


SSE_CHECKS: dict[str, Callable[[str], bool]] = {
    "credentials": _sends_credentials,
    "csrf header": _sends_csrf_header,
    "both cookie names": _reads_both_cookie_names,
    "one refresh on 401": _refreshes_once_on_401,
    "streaming decode": _decodes_as_a_stream,
    "partial line": _carries_a_partial_line,
    "one onComplete": _calls_on_complete_once,
    "retry-after": _shows_retry_after,
    "error detail": _reads_the_error_detail,
    "signed out": _shows_signed_out,
}
UI_CHECKS: dict[str, Callable[[str], bool]] = {
    "renders onError": _renders_the_error,
}

SPELLINGS: dict[str, list[str]] = {
    "credentials": [
        'fetch(url, { credentials: "same-origin" })',
        "fetch(url, {credentials:'same-origin'})",
        "init = { credentials : `same-origin` }",
        '{\n  credentials: "same-origin",\n}',
        'const opts: RequestInit = { method: "POST", credentials: "same-origin" };',
    ],
    "csrf header": [
        '"X-CSRF-Token": csrfToken()',
        "'x-csrf-token': readCsrfCookie()",
        'headers.set("X-CSRF-Token", getCsrf())',
        '"X-Csrf-Token": cookies.csrf()',
        "`X-CSRF-Token`: csrf()",
    ],
    "both cookie names": [
        'const NAMES = ["__Host-csrf_token", "csrf_token"];',
        "read('__Host-csrf_token') ?? read('csrf_token')",
        'const base = "csrf_token"; [`__Host-${base}`, base]',
        'cookie("__Host-csrf_token") || cookie("csrf_token")',
        'for (const n of ["csrf_token", "__Host-csrf_token"]) {}',
    ],
    "one refresh on 401": [
        'if (res.status === 401) await fetch("/auth/refresh", init);',
        "if (r.status == 401) { await fetch('/auth/refresh', o) }",
        "const REFRESH = `/auth/refresh`; if (response.status === 401) refresh();",
        'if (status !== 401) return res; await fetch("/auth/refresh")',
        'response.status === 401 && (await fetch("/auth/refresh", { method: "POST" }))',
    ],
    "signed out": [
        'setError("You are signed out.")',
        'onError("Please sign in again")',
        "'Signed out — sign in to chat'",
        '"Sign-in required"',
        '"You have been signed out"',
    ],
    "streaming decode": [
        "decoder.decode(value, { stream: true })",
        "decoder.decode(value,{stream:true})",
        "td.decode(chunk, { stream : true })",
        "decoder.decode(value, {\n  stream: true,\n})",
        "new TextDecoder().decode(v, { stream: true })",
    ],
    "partial line": [
        'buffer = lines.pop() ?? "";',
        'buf = parts.pop() || "";',
        'const cut = buffer.lastIndexOf("\\n");',
        "const rest = lines.splice(-1)[0];",
        "pending = chunks.pop()!;",
    ],
    "one onComplete": [
        "options.onComplete?.(fullText);",
        "onComplete?.(text)",
        "onComplete(fullText)",
        "options.onComplete ?.(t)",
        "opts.onComplete?.( full )",
    ],
    "retry-after": [
        'if (res.status === 429) wait = res.headers.get("Retry-After");',
        "status === 429 && r.headers.get('retry-after')",
        "case 429: s = response.headers.get(`Retry-After`);",
        'if (code == 429) { h = resp.headers.get( "Retry-After" ) }',
        'if (r.status === 429) after = r.headers.get("RETRY-AFTER")',
    ],
    "error detail": [
        "message = body.detail",
        "const { detail } = problem; use(problem.detail)",
        'msg = json["detail"]',
        "err?.detail ?? fallback",
        "data['detail']",
    ],
    "renders onError": [
        "const [error, setError] = useState<string | null>(null);\n"
        "useSSEStream({ onError: (m) => setError(m) });\nreturn (<p>{error}</p>);",
        'const [err, setErr] = useState("");\n'
        "useSSEStream({ onError: setErr });\nreturn (<div>{err && <p>{err}</p>}</div>);",
        "const [problem, setProblem] = useState<string>();\n"
        "useSSEStream({ onError(message) { setProblem(message); } });\nreturn (<span>{ problem }</span>);",
        "const [notice, setNotice] = useState<string | null>(null);\n"
        "const s = useSSEStream({ onComplete: done, onError: (e: string) => { setNotice(e); } });\n"
        "return (<>{notice ? <p>{notice}</p> : null}</>);",
        'const [ failure , setFailure ] = useState("");\n'
        "useSSEStream({\n  onError: (text) => setFailure(text),\n});\nreturn (\n  <p>{failure}</p>\n);",
    ],
}


def _text(name: str) -> str:
    return (CHAT / name).read_text()


@pytest.mark.parametrize("check", sorted(SSE_CHECKS))
def test_the_stream_hook_meets_the_backend_contract(check):
    assert SSE_CHECKS[check](_text("SSEStream.tsx")), check


@pytest.mark.parametrize("check", sorted(UI_CHECKS))
def test_the_chat_ui_shows_what_the_stream_reports(check):
    assert UI_CHECKS[check](_text("ChatUI.tsx")), check


@pytest.mark.parametrize("name", ["SSEStream.tsx", "ChatUI.tsx"])
def test_the_client_names_neither_the_model_service_nor_the_deleted_route(name):
    text = _text(name)
    assert "openrouter" not in text.lower() and "api/chat" not in text


@pytest.mark.parametrize("check", sorted(SPELLINGS))
def test_each_check_catches_its_five_spellings(check):
    predicate = {**SSE_CHECKS, **UI_CHECKS}[check]
    caught = [s for s in SPELLINGS[check] if predicate(s)]
    print(f"{check}: caught {len(caught)} of {len(SPELLINGS[check])}")
    assert len(SPELLINGS[check]) == 5
    assert caught == SPELLINGS[check]


def test_a_no_op_error_handler_fails_the_render_check():
    noop = (
        "const [error, setError] = useState<string | null>(null);\n"
        "useSSEStream({ onError: () => {} });\nreturn (<p>{error}</p>);"
    )
    assert not _renders_the_error(noop)


def test_two_on_complete_call_sites_fail():
    assert not _calls_on_complete_once("onComplete?.(a);\n onComplete?.(b);")
