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


def test_redaction_still_applies_to_bridged_records():
    """A bridged uvicorn line must not bypass PII redaction on its way to stdout."""
    # split on the DEF, not the first mention — the call site precedes the body
    bridge = EMITTED.split("def _bridge_stdlib_logging")[1]
    assert "_redact_sensitive" in bridge, "third-party records skip redaction"
