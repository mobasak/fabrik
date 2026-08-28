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
