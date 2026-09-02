"""The scaffolded logger must make EVERY stdout line JSON — not just our own calls.

THE DEFECT THIS GUARDS (measured live 2026-09-01, filed by the infra session):
`_logger_py_content()` emitted a logger.py that called `structlog.configure(...)`
and nothing else. Configuring structlog configures STRUCTLOG — the stdlib loggers
that uvicorn/gunicorn/SQLAlchemy use keep their own handlers. So every scaffolded
FastAPI service shipped a MIX, visible on vps1 in adjacent lines:

    {"status": "ok", "event": "cloudflare_connectivity_check", ...}
    INFO:     127.0.0.1:54012 - "GET /health HTTP/1.1" 200 OK

Loki ingests both; it cannot label, filter or alert on the second.

THE BAR IS PER-PROCESS, NOT PER-CALL-SITE. "We log correctly" is not the property —
"every line this process writes is JSON" is. That distinction is why the gap was
invisible for so long: the JSON lines looked right and nobody diffed whole stdout.

These tests assert the emitted SOURCE, not a live process, because the scaffolder's
contract is the code it generates. The end-to-end proof (running the emitted module
and grepping for non-JSON) was done by hand at fix time and is recorded in the
commit; it needs structlog, which the hub venv does not carry.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fabrik.scaffold import _logger_py_content  # noqa: E402

EMITTED = _logger_py_content("demo-svc", "demo_svc")


def test_emitted_logger_compiles():
    """A generator that emits non-compiling code fails silently until deploy."""
    compile(EMITTED, "logger.py", "exec")


def test_bridges_the_stdlib_root_logger():
    """structlog.configure alone leaves uvicorn's handlers intact — the whole defect."""
    assert "_bridge_stdlib_logging" in EMITTED
    assert "ProcessorFormatter" in EMITTED
    assert "import logging" in EMITTED, "the bridge needs the stdlib logging module"


def test_neutralises_the_server_loggers_by_name():
    """uvicorn/gunicorn install their OWN handlers; clearing root is not enough.

    Named explicitly rather than by a wildcard so a future framework addition is a
    deliberate edit, not an accident of matching.
    """
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn"):
        assert f'"{name}"' in EMITTED, f"{name} not neutralised — its handler still writes raw text"


def test_remove_processors_meta_is_reachable_on_the_right_object():
    """Regression: the first fix used `structlog.stdlib.remove_processors_meta`.

    That COMPILES and raises AttributeError at import time — the emitted module was
    syntactically valid and dead on arrival. It is a ProcessorFormatter attribute.
    Caught only by running the emitted module, not by compiling it.
    """
    assert "structlog.stdlib.ProcessorFormatter.remove_processors_meta" in EMITTED
    assert "\n            structlog.stdlib.remove_processors_meta" not in EMITTED


def test_bridged_records_go_to_stdout_not_stderr():
    """One process must write one stream, or Loki labels the same service twice.

    Found only by running a REAL uvicorn server and capturing the two streams
    separately (2026-09-01): structlog's PrintLoggerFactory writes to stdout while a
    bare `logging.StreamHandler()` defaults to STDERR. Both halves were valid JSON —
    so every string assertion and the combined-output check passed — while the
    service was actually splitting its logs across two streams with two different
    `stream` label values. A test that greps merged output cannot see this.
    """
    assert "logging.StreamHandler(sys.stdout)" in EMITTED
    assert "import sys" in EMITTED, "explicit stdout needs the sys import"


def test_redaction_still_applies_to_bridged_records():
    """A bridged uvicorn line must not bypass PII redaction on its way to stdout."""
    # split on the DEF, not the first mention — the call site precedes the body
    bridge = EMITTED.split("def _bridge_stdlib_logging")[1]
    assert "_redact_sensitive" in bridge, "third-party records skip redaction"


def _redactor():
    """Exec ONLY the redactor slice — the emitted module imports structlog, which the
    hub venv does not carry, and the redactor itself does not need it."""
    start = EMITTED.index("_SECRET_PATTERNS = [")
    end = EMITTED.index("def _setup_logging")
    src = "import re\nfrom typing import Any\nfrom collections.abc import MutableMapping\n" + EMITTED[start:end]
    ns: dict = {}
    exec(compile(src, "redactor.py", "exec"), ns)  # noqa: S102
    return ns["_redact_sensitive"]


def test_message_level_secrets_are_redacted_by_execution():
    """A secret INSIDE a message string must not survive — proven by running it.

    THE DEFECT (measured 2026-09-02, found on the operator's fourth "are you sure?"):
    `_redact_sensitive` matched event-dict KEYS only. uvicorn logs the request line, so
    `GET /cb?api_key=sk-LIVE-SECRET` arrived as the `event` VALUE and no key matched.
    Once the stdlib bridge made those lines structured JSON they became Loki-INDEXED —
    so a key-only redactor shipped *searchable* secrets. Pre-existing on our own path
    too; the bridge widened the exposure rather than creating it.

    ⚠️ THIS TEST EXECUTES THE REDACTOR. The sibling test asserting `_redact_sensitive`
    appears in the bridge PASSED throughout the leak — the symbol was present and did
    not do what the test's name claimed. A string assertion cannot test behaviour.
    """
    redact = _redactor()

    leaky = {
        "event": '127.0.0.1 - "GET /cb?api_key=sk-LIVE-SECRET&token=abc123def456" 200',
        "h": "Bearer eyJhbGciOiJIUzI1NiJ9.PAYLOAD.SIG",
        "v": "vendor sk-proj-ABCDEFGHIJKLMNOP inline",
        "password": "hunter2",
    }
    out = redact(None, "info", dict(leaky))
    blob = repr(out)
    for secret in ("sk-LIVE-SECRET", "abc123def456", "PAYLOAD.SIG", "sk-proj-ABCDEFGHIJKLMNOP", "hunter2"):
        assert secret not in blob, f"{secret} survived redaction"


def test_redaction_does_not_mangle_benign_lines():
    """A redactor that eats legitimate output gets switched off — so bound the blast radius."""
    redact = _redactor()
    benign = {"event": "GET /health 200 in 12ms", "path": "/api/v1/users?page=2&limit=50"}
    out = redact(None, "info", dict(benign))
    assert out["event"] == benign["event"]
    assert out["path"] == benign["path"], "pagination params must not be redacted"
