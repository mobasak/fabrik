"""dispatch_headroom refuses while CLAUDE_CODE_SUBAGENT_MODEL_FORCE is set (row 5b, D-357).

code.claude.com/docs/en/model-config: the `_FORCE` variable puts every subagent on one model, a
per-invocation `model` included — so a partitioned loop's Sonnet + Haiku pair would be one model twice and
a units fan-out's mix would collapse, with every count still printing as if it held (§ 4.9 findings 37, 43).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "dispatch_headroom.py"


def _run(env_extra: dict, *args: str) -> subprocess.CompletedProcess:
    import os

    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SRC), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )


def test_a_forced_subagent_model_refuses_every_fan_out() -> None:
    for args in (("--slices", "sonnet=2,haiku=2"), ("--units", "2")):
        r = _run({"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "haiku"}, *args)
        assert r.returncode == 2 and "CLAUDE_CODE_SUBAGENT_MODEL_FORCE" in r.stderr, (
            args,
            r.stdout,
            r.stderr,
        )
        assert "SEATS:" not in r.stdout


def test_an_empty_force_variable_is_unset() -> None:
    r = _run({"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": ""}, "--slices", "sonnet=1,haiku=1")
    assert r.returncode == 0 and "SEATS:" in r.stdout, r.stderr


def test_a_whitespace_force_value_still_refuses() -> None:
    """Review of D-357, A-S6/B-S5: a value that is set but only whitespace is still set — fail closed."""
    r = _run({"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "  "}, "--slices", "sonnet=1,haiku=1")
    assert r.returncode == 2 and "CLAUDE_CODE_SUBAGENT_MODEL_FORCE" in r.stderr, r.stdout
