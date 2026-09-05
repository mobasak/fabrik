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

import pytest

from fabrik.scaffold import FABRIK_ROOT, create_project

requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)


@requires_fabrik_env
def test_python_glitchtip_init_strips_locals_and_body(tmp_path):
    create_project(
        name="gt-py-sec",
        project_type="saas-skeleton",
        description="glitchtip security regression",
        base=tmp_path,
        generate_spec=False,
    )
    init = (tmp_path / "gt-py-sec" / "server" / "src" / "gt_py_sec" / "glitchtip_init.py").read_text()
    assert "include_local_variables=False" in init, "frame-locals channel not closed (JWT/DSN leak)"
    assert 'max_request_body_size="never"' in init, "request-body channel not closed (payload leak)"


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
    assert "LoggingIntegration(event_level=logging.ERROR, level=None)" in src, (
        "fleet logging default (D-126) missing — the reference uses event_level=None"
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
    assert top <= {"os", "re", "logging", "sentry_sdk", "structlog"}, f"unexpected top-level imports: {top}"

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
