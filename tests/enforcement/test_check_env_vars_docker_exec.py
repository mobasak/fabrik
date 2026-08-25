# AFTER-EDIT: scripts/enforcement/check_env_vars.py
"""Container-internal localhost inside docker-exec strings is correct, not a violation."""

import sys
from pathlib import Path

sys.path.insert(0, "/opt/fabrik/scripts/enforcement")
import check_env_vars as cev  # noqa: E402


def _results(tmp_path: Path, body: str):
    f = tmp_path / "probe.py"
    f.write_text(body)
    return cev.check_file(f)


def test_docker_exec_internal_localhost_is_sanctioned(tmp_path):
    """Fleet finding 01M05N9CVESBMTS7QX80NY8AYB: a meilisearch self-probe (`curl
    localhost` INSIDE `docker exec $CONT sh -c '…'`, marker on the line above the
    literal — a multi-line Python string) redded the gate on every unrelated touch."""
    body = (
        "cmd = (\n"
        "    \"sudo docker exec $CONT sh -c \"\n"
        "    \"'curl -s http://localhost:7700/indexes' 2>/dev/null\"\n"
        ")\n"
    )
    assert _results(tmp_path, body) == [], "container-internal localhost was flagged"


def test_bare_localhost_string_is_still_flagged(tmp_path):
    """The teeth stay: no docker-exec context above → still a violation."""
    body = 'url = "http://localhost:3000/api"\n'
    res = _results(tmp_path, body)
    assert res, "a bare hardcoded localhost URL must still be flagged"
