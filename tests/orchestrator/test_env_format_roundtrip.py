"""`_format_env` / `_parse_env` round-trip + Compose-parseability.

THE DEFECT THIS GUARDS (measured live 2026-08-31, tryton-crm RUN 1):
`_format_env` quoted any value containing a space, `#`, `'`, `"` or newline and
wrapped it WITHOUT escaping the inner quotes. A JSON secret contains `"`, so it
shipped as `K="{"a":"b"}"` and Compose read the first inner quote as a NEW
VARIABLE NAME:

    failed to read /opt/tryton-crm/.env: line 6: unexpected character '"'
    in variable name "crm-bridge\\":{\\"token\\":...

That broke `docker compose build` for EVERY value carrying a quote — every
JSON-valued secret on the fleet, not one project's quirk. Two byte-identical
apply failures before the cause was found.

The pair must stay SYMMETRIC: whatever the writer escapes, the reader unescapes.
An asymmetric fix grows a backslash per apply, which is why idempotency is
asserted here and not just a single round-trip.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fabrik.orchestrator.deployer_ssh import _format_env, _parse_env

REPO_ROOT = Path(__file__).resolve().parents[2]

_CONSUMER_TOKENS = json.dumps(
    {"crm-bridge": {"token": "abc123", "orgs": ["bhd-group"], "scopes": ["read", "write"]}},
    separators=(",", ":"),
)

# One entry per shape that has to survive the file format.
CASES = {
    "CONSUMER_TOKENS": _CONSUMER_TOKENS,  # the live defect
    "PLAIN": "hello",
    "WITH_SPACE": "hello world",
    "WITH_HASH": "value#fragment",  # some dotenv parsers comment at ` #`
    "LEAD_TRAIL": "  padded  ",  # bare would be stripped
    "DSN": "postgresql://u:p@postgres-main:5432/db",
    "QUOTED_CONTENT": '"already quoted"',  # ambiguous: content IS quote-wrapped
    "BACKSLASH": r"a\b",
    "SINGLE_QUOTED_CONTENT": "'sq'",
}


def test_round_trip_preserves_every_value():
    assert _parse_env(_format_env(CASES)) == CASES


def test_round_trip_is_IDEMPOTENT_no_backslash_growth():
    """Asymmetric escape/unescape grows a backslash on every apply.

    A single round-trip cannot catch that — the corruption appears on the SECOND
    write. Deploys re-apply routinely, so this is the assertion that matters.
    """
    once = _parse_env(_format_env(CASES))
    twice = _parse_env(_format_env(once))
    assert twice == CASES


def test_json_value_is_emitted_UNQUOTED_so_compose_can_read_it():
    """The specific regression: a compose env_file takes the value raw to EOL."""
    line = next(
        line for line in _format_env(CASES).splitlines() if line.startswith("CONSUMER_TOKENS=")
    )
    assert line == f"CONSUMER_TOKENS={_CONSUMER_TOKENS}"
    assert not line.startswith('CONSUMER_TOKENS="'), (
        "a wrapped JSON value is exactly what Compose rejects"
    )


def _compose_config(tmp_path: Path, env_body: str) -> subprocess.CompletedProcess:
    (tmp_path / "probe.env").write_text(env_body)
    (tmp_path / "compose.yaml").write_text(
        "services:\n  t:\n    image: alpine:3\n    env_file: probe.env\n    command: [\"true\"]\n"
    )
    return subprocess.run(
        ["docker", "compose", "-f", "compose.yaml", "config"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.skipif(
    subprocess.run(["which", "docker"], capture_output=True, check=False).returncode != 0,
    reason="docker not available",
)
def test_REAL_compose_parses_our_output_and_rejects_the_old_form(tmp_path):
    """The executable check, not a proxy for it.

    The second half is what makes the first half mean anything: if Compose accepted
    the old broken form too, this test would prove nothing about the fix.
    """
    assert _compose_config(tmp_path, _format_env(CASES)).returncode == 0, "our output must parse"

    old_broken = f'CONSUMER_TOKENS="{_CONSUMER_TOKENS}"\n'
    assert _compose_config(tmp_path, old_broken).returncode != 0, (
        "the pre-fix form must still be REJECTED — otherwise this test does not discriminate"
    )
