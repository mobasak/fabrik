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
import os
import shutil
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
    # W-05004b41: compose interpolates env_file values, so a `$` must survive it.
    "BCRYPT": "$2b$12$abcdefghijklmnopqrstuv",
    "DOLLAR_MID": "pa$$word",
    "DOLLAR_BRACE": "${NOT_A_VAR}",
    "DOLLAR_END": "cost$",
    "DOLLAR_WITH_QUOTES": 'it\'s "$5"',
    "BACKSLASH_DOLLAR": r"a\$b",
}

# The `$`-bearing subset, read back from a real container (W-05004b41).
DOLLAR_CASES = {k: v for k, v in CASES.items() if "$" in v}


def test_round_trip_preserves_every_value():
    assert _parse_env(_format_env(CASES)) == CASES


def test_round_trip_is_idempotent_no_backslash_growth():
    """Asymmetric escape/unescape grows a backslash on every apply.

    A single round-trip cannot catch that — the corruption appears on the SECOND
    write. Deploys re-apply routinely, so this is the assertion that matters.
    """
    once = _parse_env(_format_env(CASES))
    twice = _parse_env(_format_env(once))
    assert twice == CASES


def test_json_value_is_escaped_not_bare_wrapped():
    """The invariant is that Compose can READ it — not that it is unquoted.

    My first version of this test asserted "emitted unquoted", which is an
    implementation choice, not the requirement. Bending the fix to satisfy it broke
    `TestFormatEnv::test_quotes_spaces`, whose contract is real: the file must stay
    safe for a shell `source`, where a bare `K=a b` word-splits. The fix therefore
    keeps the quote trigger and fixes only the ESCAPING.
    """
    line = next(
        line for line in _format_env(CASES).splitlines() if line.startswith("CONSUMER_TOKENS=")
    )
    assert line.startswith('CONSUMER_TOKENS="') and line.endswith('"')
    assert '\\"' in line, "inner quotes MUST be escaped — bare-wrapped is the defect"
    # and it must survive the round trip back to the exact original JSON
    assert _parse_env(line)["CONSUMER_TOKENS"] == _CONSUMER_TOKENS


def _compose_config(tmp_path: Path, env_body: str) -> subprocess.CompletedProcess:
    (tmp_path / "probe.env").write_text(env_body)
    (tmp_path / "compose.yaml").write_text(
        'services:\n  t:\n    image: alpine:3\n    env_file: probe.env\n    command: ["true"]\n'
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
def test_real_compose_parses_our_output_and_rejects_the_old_form(tmp_path):
    """The executable check, not a proxy for it.

    The second half is what makes the first half mean anything: if Compose accepted
    the old broken form too, this test would prove nothing about the fix.
    """
    assert _compose_config(tmp_path, _format_env(CASES)).returncode == 0, "our output must parse"

    old_broken = f'CONSUMER_TOKENS="{_CONSUMER_TOKENS}"\n'
    assert _compose_config(tmp_path, old_broken).returncode != 0, (
        "the pre-fix form must still be REJECTED — otherwise this test does not discriminate"
    )


def test_dollar_is_escaped_and_shell_literal(tmp_path):
    """Each `$` is written `\\$` inside double quotes, which a POSIX shell `.` also reads literally
    (`$$` would read as the shell's PID) — the file stays safe to `source`."""
    body = _format_env(DOLLAR_CASES)
    for line in body.splitlines():
        assert line.split("=", 1)[1].startswith('"'), line
    env_file = tmp_path / "probe.env"
    env_file.write_text(body)
    names = sorted(DOLLAR_CASES)
    script = f"set -a; . {env_file}; " + "; ".join(f'printf "%s\\0" "${n}"' for n in names)
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=True).stdout
    assert dict(zip(names, out.split("\0")[:-1], strict=True)) == DOLLAR_CASES


def _local_image(name: str) -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(["docker", "image", "inspect", name], capture_output=True, check=False)
    return probe.returncode == 0


@pytest.mark.skipif(
    not _local_image("alpine:3"), reason="docker or the local alpine:3 image is absent"
)
def test_dollar_values_reach_the_container_verbatim(tmp_path):
    """The real consumer: compose interpolates env_file values before the container starts, so the
    grader reads the CONTAINER's environment, not the parser (`a$b` used to arrive as `a`)."""
    (tmp_path / ".env").write_text(_format_env(DOLLAR_CASES))
    (tmp_path / "compose.yaml").write_text(
        "services:\n  t:\n    image: alpine:3\n    env_file:\n      - path: .env\n"
    )
    keep = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(tmp_path),
            "run",
            "--rm",
            "--pull",
            "never",
            "t",
            "env",
            "-0",
        ],
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k in keep},
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    seen = dict(item.split("=", 1) for item in result.stdout.split("\0") if "=" in item)
    assert {k: seen.get(k) for k in DOLLAR_CASES} == DOLLAR_CASES
