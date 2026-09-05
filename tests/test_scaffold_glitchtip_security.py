"""Security regression: the scaffold-emitted GlitchTip/Sentry init must not leak secrets.

transdoc filed (01M13279RB + correction 01M133NZWN) that the scaffolded `glitchtip_init` shipped
the JWT signing secret, the DB DSN, and live request-body values to GlitchTip on any handled ERROR
log — because `send_default_pii=False` closes NEITHER the frame-locals channel NOR (in Python) the
request-body channel. These tests assert the emitted init carries the STRUCTURAL fixes, per
`.windsurf/rules/core/55-observability.md` § Error Reporting.

Grounded API note (Sentry docs, verified 2026-08-28):
- Python (`sentry-sdk`): frame locals default ON and the request body is attached regardless of
  `send_default_pii` → BOTH `include_local_variables=False` and `max_request_body_size="never"`.
- Node (`@sentry/node`): frame locals default ON for Node runtimes → `includeLocalVariables: false`.
  There is NO `maxRequestBodySize` init option in @sentry/node (that is Python-only); with
  `sendDefaultPii: false` the body is reported as SIZE only, not content. Emitting the Python-style
  flag in Node would be a silently-ignored no-op (false security) — so it must NOT appear.
"""

import os
from pathlib import Path

import pytest

from fabrik.scaffold import FABRIK_ROOT, create_project

requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)


SECRETS = {
    "dsn": "postgres://svc:PGPASSWORD_LEAK@postgres-main:5432/db",
    # An absent "@" is not an absent credential. Every other DSN in this corpus carries one,
    # so the whole corpus was blind BY CONSTRUCTION to a truncated or mistyped DSN — the
    # redactors keyed on a literal "@" and `rsplit("@", 1)[-1]` is a NO-OP without one, so
    # the credential arrives as the "host" and is re-emitted verbatim. site-provisioner
    # measured 240 of 480 probes leaking on this shape and 0 of 240 on the "@"-bearing one
    # (01M1RQF0SV7SRQJSG6NFEZG8NE); their own 26,880-case fuzz corpus could not see it for
    # exactly this reason. Carried here because a guard whose inputs all share one shape
    # proves only that the shape it never tries is untested.
    "dsn_no_at": "postgres://svc:NOATPASSWORD_LEAK",
    "jwt": "JWTSECRET_LEAK",
    "password": "BODYPASSWORD_LEAK",
    "header": "SIGNINGSECRET_LEAK",
    "query": "URLTOKEN_LEAK",
    "otp": "OTPINTERPOLATED_LEAK",
    "apikey": "BREADCRUMBAPIKEY_LEAK",
}


def _load_guard_module(tmp_path):
    """Load the module under guard: the substituted TEMPLATE by default, or whatever
    GLITCHTIP_GUARD_MODULE points at — which is how the watched-fail is aimed at the OLD
    inline literal without editing the test. T02 (the emitter) merges LAST, so this guard
    must not wait for it: it substitutes the template's two tokens itself."""
    import importlib.util

    override = os.environ.get("GLITCHTIP_GUARD_MODULE")
    if override:
        path = Path(override)
    else:
        template = Path(__file__).resolve().parents[1] / "templates" / "scaffold" / "python" / "glitchtip_init.py"
        src = template.read_text().replace("{pkg}", "guarded_pkg").replace("{name}", "guarded-svc")
        path = tmp_path / "glitchtip_init_under_guard.py"
        path.write_text(src)

    spec = importlib.util.spec_from_file_location("glitchtip_init_under_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _serialize(envelopes):
    """What would actually hit the wire. The reference tests' own method: capture_envelope
    receives an Envelope, so walk its items and dump each payload. Substring-search THAT —
    never a field list, because a field list is the denylist this whole plan replaces."""
    import json

    return "\n".join(
        json.dumps(item.payload.json, default=repr)
        for envelope in envelopes
        for item in envelope.items
        if getattr(item.payload, "json", None) is not None
    )


def test_python_glitchtip_captured_event_and_transaction_carry_no_secret(tmp_path, monkeypatch):
    """Rule 55: verify on the CAPTURED EVENT, never the init kwarg.

    The test this replaces asserted two flag STRINGS were present in emitted text. That is a
    denylist assertion about source code, and site-provisioner measured ~10 channels still open
    behind exactly those two flags. This one raises inside a real request with six secrets in
    play and searches everything the transport would ship.

    The TRANSACTION half is not decoration: sentry-sdk skips `before_send` entirely for
    transaction events (`client.py`, `event.get("type") != "transaction"`), so a scrubber
    registered only there leaves every sampled transaction unscrubbed.
    """
    import logging

    import httpx
    import sentry_sdk
    from fastapi import FastAPI, Request
    from starlette.testclient import TestClient

    monkeypatch.setenv("SENTRY_DSN", "https://publickey@glitchtip.invalid/42")
    # Without this, transactions sample at 0.05 and the transaction assertions are vacuous.
    monkeypatch.setenv("GLITCHTIP_TRACES_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("SERVICE_NAME", "guarded-svc")

    module = _load_guard_module(tmp_path)
    assert module.init_glitchtip() is True, (
        "init_glitchtip() returned False — the module took its ImportError/no-DSN path, so "
        "nothing below is actually being scrubbed. A missing SDK must FAIL this guard, never pass it."
    )
    print(f"sentry_sdk.VERSION = {sentry_sdk.VERSION}")

    envelopes = []
    monkeypatch.setattr(sentry_sdk.get_client().transport, "capture_envelope", envelopes.append)

    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):  # noqa: ANN201
        settings_repr = f"Settings(database_url='{SECRETS['dsn']}', jwt_secret='{SECRETS['jwt']}')"  # noqa: F841
        body = await request.json()  # noqa: F841
        signing = request.headers.get("X-Signing-Secret")  # noqa: F841
        logging.getLogger("guard").error("otp=%s", SECRETS["otp"])
        # The @-less credential travels in the TEMPLATE, which is the one logentry field the
        # allowlist deliberately KEEPS — so it is reachable only through the free-text
        # redactor, which is precisely where the "@"-keyed regex used to miss it.
        logging.getLogger("guard").error("connecting to " + SECRETS["dsn_no_at"])
        try:  # a breadcrumb carrying an outbound URL with a live-looking key
            httpx.get(f"http://127.0.0.1:1/probe?apikey={SECRETS['apikey']}", timeout=0.05)
        except Exception:  # noqa: BLE001  (connection refused is the point; the breadcrumb is recorded first)
            pass
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(
            f"/boom?token={SECRETS['query']}",
            json={"password": SECRETS["password"]},
            headers={"X-Signing-Secret": SECRETS["header"]},
        )
    sentry_sdk.get_client().flush(timeout=2)

    wire = _serialize(envelopes)
    assert wire, "nothing was captured — the transport swap or the raise did not work"

    leaked = sorted(name for name, value in SECRETS.items() if value in wire)
    assert not leaked, f"secrets reached the wire through: {leaked}"

    payloads = []
    for envelope in envelopes:
        for item in envelope.items:
            data = getattr(item.payload, "json", None)
            if isinstance(data, dict):
                payloads.append(data)

    errors = [d for d in payloads if d.get("type") != "transaction" and "exception" in d]
    transactions = [d for d in payloads if d.get("type") == "transaction"]
    assert errors, "no ERROR event captured"
    assert transactions, (
        "no TRANSACTION event captured — with traces_sample_rate=1.0 one is expected, and it is "
        "the event before_send never sees"
    )

    for event in errors:
        logentry = event.get("logentry")
        if logentry is not None:
            assert set(logentry) <= {"message"}, (
                f"logentry carries more than the template: {sorted(logentry)} — params/formatted "
                "hold the INTERPOLATED text"
            )
        crumbs = event.get("breadcrumbs") or {}
        values = crumbs.get("values", crumbs) if isinstance(crumbs, dict) else crumbs
        assert not values, f"breadcrumbs survived: {values!r}"


def test_node_glitchtip_init_strips_locals_without_bogus_body_flag(tmp_path):
    create_project(
        name="gt-node-sec", project_type="node-api", description="glitchtip security regression", base=tmp_path
    )
    init = (tmp_path / "gt-node-sec" / "src" / "glitchtip_init.js").read_text()
    assert "includeLocalVariables: false" in init, "Node frame-locals channel not closed (default ON in Node)"
    # The Python-only flag must NOT be emitted in Node: @sentry/node has no such option, so it would be
    # a silently-ignored no-op that reads like a fix. sendDefaultPii:false already restricts the body to
    # size-only in Node.
    assert "maxRequestBodySize" not in init, "invalid @sentry/node option emitted — false security"


# ── T01: the vendored deny-by-default scrubber lives in the template tree ──────────────────────
# The two tests above assert a FLAG LIST, and that framing is what this module replaces. Measured
# by site-provisioner (01M1R0XZMZT43BDG20Y2PXV0EA) and confirmed here against sentry-sdk 2.68.1:
# those two flags close two channels and roughly ten others stayed open, because a flag list is a
# denylist and a denylist cannot see a channel nobody enumerated. The load-bearing one:
#
#     client.py — before_send = self.options["before_send"]
#                 if (before_send is not None and event is not None
#                         and event.get("type") != "transaction"):
#
# `before_send` is SKIPPED ENTIRELY for transaction events, so a scrubber registered only there
# never runs on a transaction. Hence both hooks below, asserted rather than assumed.


def test_vendored_module_is_deny_by_default_and_registers_both_hooks():
    """The vendored template must parse, import, expose the scrubber, register BOTH hooks, and
    carry the three scaffold adaptations. The leaf-shape rule is EXECUTED, not grepped — it is the
    part that catches a channel nobody enumerated, so reading it would prove nothing."""
    import ast
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "templates" / "scaffold" / "python" / "glitchtip_init.py"
    assert path.exists(), "the vendored scrubber is missing from the template tree"
    src = path.read_text()

    tree = ast.parse(src)  # Gate: it must parse as Python before anything else is worth asserting
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {"init_glitchtip", "_scrub_event"} <= funcs, f"missing entry points; has {sorted(funcs)[:8]}"

    # BOTH hooks. The second is the whole point — see the client.py quote above.
    assert src.count("before_send=_scrub_event") == 1, "before_send hook not registered exactly once"
    assert src.count("before_send_transaction=_scrub_event") == 1, (
        "before_send_transaction NOT registered — every sampled transaction would ship unscrubbed, "
        "because the SDK skips before_send for transaction events"
    )

    # The scaffold adaptations, each deliberate (see the module docstring).
    # Assert the CALL, not a literal spelling. This assertion used to pin the exact
    # single-line string and went red the moment upstream reflowed it across three lines to
    # add `sentry_logs_level` — a real change, but the test named the formatting rather than
    # the contract. Read the keywords off the AST instead.
    logging_calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", None)) == "LoggingIntegration"
    ]
    assert len(logging_calls) == 1, f"expected one LoggingIntegration call, found {len(logging_calls)}"
    kwargs = {k.arg: ast.unparse(k.value) for k in logging_calls[0].keywords}
    assert kwargs.get("event_level") == "logging.ERROR", (
        f"fleet logging default (D-126) missing — upstream uses event_level=None; got {kwargs.get('event_level')!r}"
    )
    assert kwargs.get("level") == "None", f"level must stay None (no breadcrumbs); got {kwargs.get('level')!r}"
    # The THIRD handler. `_sentry_logs_handler` defaults to INFO and emits `log` envelope
    # items carrying `sentry.message.parameter.0` — the interpolated log parameter — through
    # `before_send_log`, a hook this module does not register. `_scrub_event` therefore has
    # ZERO reach into that channel, so it is disabled outright rather than left resting on
    # the `enable_logs` client default.
    assert kwargs.get("sentry_logs_level") == "None", (
        "sentry_logs_level must be None — that channel bypasses _scrub_event entirely; "
        f"got {kwargs.get('sentry_logs_level')!r}"
    )
    for integration in ("FastApiIntegration", "StarletteIntegration"):
        assert f'{integration}(transaction_style="endpoint")' in src, (
            f"{integration} lost transaction_style=endpoint — this silently RENAMES every "
            "transaction in GlitchTip"
        )
    # Exactly two substitution tokens, once each: T02 substitutes by str.replace, never .format(),
    # because the module contains ~40 other braces that are dict/set literals, regexes and f-strings.
    assert src.count("{pkg}") == 1, f"{{pkg}} token appears {src.count('{pkg}')}x, expected once"
    assert src.count("{name}") == 1, f"{{name}} token appears {src.count('{name}')}x, expected once"

    # Imports stay stdlib + sentry_sdk + structlog, or a scaffolded project cannot run it.
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top.add(node.module.split(".")[0])
    # `ipaddress` arrived with the @-less credential fix: the authority is accepted only if it
    # provably PARSES, and a ":" survives solely as a numeric port or inside a bracketed IPv6
    # literal — which is what `ipaddress.IPv6Address` adjudicates. Widened deliberately, with
    # the reason recorded, rather than relaxed to make a red guard green.
    assert top <= {"ipaddress", "os", "re", "logging", "sentry_sdk", "structlog"}, (
        f"unexpected top-level imports: {top}"
    )

    # EXECUTE it.
    spec = importlib.util.spec_from_file_location("vendored_glitchtip_init_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert set(module._ALLOWED_LOGENTRY_KEYS) == {"message"}, (
        "logentry allowlist must be exactly {'message'} — params/formatted carry the INTERPOLATED "
        f"text and are the log-interpolation leak; got {set(module._ALLOWED_LOGENTRY_KEYS)}"
    )

    # Leaf shape: an allowlisted key holding an unexpected CONTAINER is nulled. This is the rule
    # that closes channels nobody enumerated, so it is exercised against the real function.
    scrubbed = module._scrub_event({"event_id": {"secret": "leaked-via-container"}, "level": "error"}, {})
    assert scrubbed.get("event_id") is None, (
        f"leaf-shape rule did not null a container in a scalar-valued key: {scrubbed.get('event_id')!r}"
    )

    # METRICS. `enable_metrics` is a documented NO-OP in sentry-sdk 2.68.1 — the client logs
    # "has no effect" and then builds the MetricsBatcher unconditionally — so the ONLY lever is
    # the hook, which drops a metric by returning None. Asserting the kwarg was passed is the
    # exact shape that let this channel sit open upstream for a full round while its guard was
    # green ("the test asserted the kwarg had been handed to init and never that anything
    # happened"), so CALL the function instead.
    assert module._drop_metric(object(), {}) is None, (
        "_drop_metric must return None for every metric — anything else re-opens the channel"
    )

    # SESSIONS have no before_send hook of any kind, so a hook-shaped inventory is structurally
    # blind to them and the flag IS the whole lever. This is the one place an option assertion is
    # the strongest available check rather than the weakest — recorded so it is not later
    # "upgraded" into a behavioural one that does not exist.
    init_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "init"
    ]
    assert len(init_calls) == 1, f"expected one sentry_sdk.init call, found {len(init_calls)}"
    init_kwargs = {k.arg: ast.unparse(k.value) for k in init_calls[0].keywords}
    assert init_kwargs.get("auto_session_tracking") == "False", (
        "auto_session_tracking must be False — session envelopes bypass every before_send hook; "
        f"got {init_kwargs.get('auto_session_tracking')!r}"
    )
    assert init_kwargs.get("before_send_metric") == "_drop_metric", (
        f"before_send_metric must be wired to _drop_metric; got {init_kwargs.get('before_send_metric')!r}"
    )
    assert "enable_metrics" not in init_kwargs, (
        "enable_metrics is a documented no-op (client.py logs 'has no effect' and builds the "
        "MetricsBatcher regardless) — passing it reads as a closed channel to the next reader"
    )


# ── T02: the emitter COPIES the vendored module instead of carrying an inline literal ──────────


@requires_fabrik_env
# FIVE types, not three. The first census scaffolded only SIX of the twelve and called it "each
# type" — office-extension and static-site each scaffold a `server/` FastAPI backend and get the
# module too, so leaving them out left two emitting types ungraded.
@pytest.mark.parametrize(
    "project_type",
    ["python-api", "python-api-gpu", "saas-skeleton", "office-extension", "static-site"],
)
def test_scaffold_emits_the_vendored_module_byte_for_byte(tmp_path, project_type):
    """All three reaching types must get the TEMPLATE, not a copy that drifted from it.

    The census was re-derived by scaffolding each of the 12 types and looking for the emitted
    file: python-api, python-api-gpu and saas-skeleton reach this emitter; node-api has the JS
    module; the other seven emit no Sentry init at all.

    Byte-equality is the assertion because the failure this guards is DRIFT — an inline literal
    that stops matching the reviewed module is exactly what T02 removed.
    """
    from fabrik.scaffold import TEMPLATE_DIR

    name = f"gt-emit-{project_type}"
    create_project(
        name=name,
        project_type=project_type,
        description="vendored glitchtip emitter",
        base=tmp_path,
        generate_spec=False,
    )
    emitted = next(
        p for p in (tmp_path / name).rglob("glitchtip_init.py") if ".venv" not in str(p)
    )
    package_name = emitted.parent.name

    expected = (
        (TEMPLATE_DIR / "python" / "glitchtip_init.py")
        .read_text()
        .replace("{pkg}", package_name)
        .replace("{name}", name)
    )
    assert emitted.read_text() == expected, (
        f"{project_type}: emitted glitchtip_init.py is not the substituted template — it has drifted"
    )
    body = emitted.read_text()
    assert "{pkg}" not in body and "{name}" not in body, "a substitution token survived into the project"
    # The other ~40 braces are the module's own dict/set literals, regexes and f-strings; they must
    # survive untouched, which is why the emitter uses str.replace and never .format().
    assert "_ALLOWED_EVENT_KEYS" in body and "before_send_transaction=_scrub_event" in body


@requires_fabrik_env
def test_scaffold_raises_when_the_vendored_template_is_missing(tmp_path, monkeypatch):
    """No silent skip. A missing template must FAIL the scaffold, because a project that quietly
    comes out without its scrubber is precisely the bug this plan exists to prevent — and it is
    the failure mode the neighbouring `pause_state.py` `.exists()` guard hides."""
    import fabrik.scaffold as scaffold_mod

    monkeypatch.setattr(scaffold_mod, "TEMPLATE_DIR", tmp_path / "no-such-template-dir")

    with pytest.raises(Exception) as excinfo:
        create_project(
            name="gt-missing-template",
            project_type="python-api",
            description="missing template",
            base=tmp_path,
            generate_spec=False,
        )
    assert "glitchtip_init.py" in str(excinfo.value) or isinstance(excinfo.value, (FileNotFoundError, OSError)), (
        f"scaffold failed for an unrelated reason: {excinfo.value!r}"
    )
