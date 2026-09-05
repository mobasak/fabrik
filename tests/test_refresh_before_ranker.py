"""Behavior contract for the Phase-C ordering gate.

`scripts/enforcement/_check_refresh_before_ranker.py` asserts that BOTH pipeline entry points rebuild
the cost sidecar before they regenerate the subagent ranking. Its first revision was demonstrably
bypassable in five ways, each found by an author-blind pass and each reproduced below as a test — a
gate that can be fooled is worse than none, because it reports a guarantee that is not there.

⚠️ The gate is only as good as its runner: it is wired into `.pre-commit-config.yaml` scoped to the
two shell files, and `test_the_gate_is_actually_wired_to_something` holds that. The first revision
was registered nowhere at all — it fired once, by hand, while the commit message claimed it "holds
that ordering".
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_GATE = _ROOT / "scripts" / "enforcement" / "_check_refresh_before_ranker.py"
_spec = importlib.util.spec_from_file_location("refresh_gate", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

_REFRESH = (
    '  _step "claude_p_cost_refresh" "$VENV_PY" "$FABRIK_ROOT/scripts/claude_p_cost.py" --refresh'
)
_RANKER = '  _step "rank_task_subagents" "$VENV_PY" "$KB/rank_task_subagents.py"'


def _run(tmp_path: Path, daily: str, boot: str | None = None) -> tuple[bool, str]:
    """Run the gate's per-file check against a synthetic entry point."""
    (tmp_path / "scripts" / "kilo-benchmarks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").write_text(
        daily, encoding="utf-8"
    )
    if boot is not None:
        (tmp_path / "scripts" / "wsl_startup_hook.sh").write_text(boot, encoding="utf-8")
    original = gate._REPO
    gate._REPO = tmp_path
    try:
        return gate._check("scripts/kilo-benchmarks/daily_refresh.sh")
    finally:
        gate._REPO = original


def test_correct_wiring_passes(tmp_path):
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{_REFRESH}\n{_RANKER}\n")
    assert ok, msg


def test_the_real_repo_is_correctly_ordered_in_every_entry_point():
    """The gate against the LIVE tree — the case that actually matters."""
    r = subprocess.run([sys.executable, str(_GATE)], capture_output=True, text=True, cwd=str(_ROOT))
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_step_that_only_reads_the_sidecar_does_not_count_as_a_rebuild(tmp_path):
    """A-1, CRITICAL. Matching the bare substring `claude_p_cost` let a READER satisfy the gate —
    a false green on the exact condition it exists to prevent, since without `--refresh` the module
    falls through to stdin and writes nothing at all."""
    # ⚠️ The FIRST version of this test used `"$KB/claude_p_cost.json"` as the reader's argument —
    # which contains no `.py`, so it was graded by the SCRIPT-PATH rule and said nothing at all about
    # `--refresh`. Mutation caught it: dropping the `--refresh` term from `_site` left this test
    # green. The line below invokes the module ITSELF without the flag, which is the real false-green
    # (`main()` then falls through to `sys.stdin.read()` and returns 2 having written nothing).
    reader = '  _step "cost_report" "$VENV_PY" "$FABRIK_ROOT/scripts/claude_p_cost.py" --model opus'
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{reader}\n{_RANKER}\n")
    assert not ok
    assert "never invokes" in msg


def test_a_line_continuation_does_not_hide_the_invocation(tmp_path):
    """A-4, FALSE RED. Anchoring on `startswith('_step')` per PHYSICAL line reddened a step wrapped
    exactly the way the rest of the file wraps its commands."""
    # ⚠️ The tokens must straddle the continuation, or the test proves nothing: the first version
    # put `claude_p_cost.py` and `--refresh` BOTH on the second physical line, so it matched with or
    # without joining and a mutation disabling the joiner survived. Here the script path is on line
    # one and the flag on line two — only a joined logical line carries both.
    wrapped = (
        '  _step "claude_p_cost_refresh" "$VENV_PY" "$FABRIK_ROOT/scripts/claude_p_cost.py" \\\n'
        "    --refresh"
    )
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{wrapped}\n{_RANKER}\n")
    assert ok, msg


def test_a_step_label_that_merely_mentions_the_ranker_is_not_the_ranker(tmp_path):
    """A-5, FALSE RED. `next()` took the first line CONTAINING the word, so a step LABEL
    (`verify_rank_task_subagents_inputs`) won and the gate reported a nonsense ordering."""
    decoy = '  _step "verify_rank_task_subagents_inputs" "$VENV_PY" "$KB/verify.py"'
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{decoy}\n{_REFRESH}\n{_RANKER}\n")
    assert ok, msg


def test_a_heredoc_body_is_not_executable_code(tmp_path):
    """A-2, FALSE GREEN. A line inside a here-doc is documentation, not a step."""
    doc = f"cat > /tmp/notes.md <<'EOF'\n{_REFRESH}\nEOF"
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{doc}\n{_RANKER}\n")
    assert not ok
    assert "never invokes" in msg


def test_a_comment_is_not_a_step(tmp_path):
    ok, msg = _run(tmp_path, f"#!/bin/bash\n#{_REFRESH}\n{_RANKER}\n")
    assert not ok


@pytest.mark.parametrize(
    ("body", "expect"),
    [
        (f"{_RANKER}\n{_REFRESH}", "must come FIRST"),
        (f"{_REFRESH}", "no invocation of rank_task_subagents.py"),
        (f"{_RANKER}", "never invokes"),
    ],
)
def test_every_broken_ordering_is_refused_with_a_message_that_says_which(tmp_path, body, expect):
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{body}\n")
    assert not ok
    assert expect in msg


def test_both_on_one_logical_line_is_refused_rather_than_mis_reported(tmp_path):
    """A-6. The old `>=` printed "refresh is at line 172, ranker at 172 — the rebuild must come
    FIRST", which is not a statement anyone can act on."""
    both = '  bash -c "$KB/../claude_p_cost.py --refresh && $KB/rank_task_subagents.py"'
    ok, msg = _run(tmp_path, f"#!/bin/bash\n{both}\n")
    assert not ok
    assert "cannot be read" in msg


def test_the_boot_entry_point_is_checked_too_not_just_the_cron(tmp_path, monkeypatch):
    """THE FINDING THAT MOTIVATED THE REWRITE. Both entry points take the same daily lock, so the
    one missing the rebuild becomes the whole day's pipeline whenever it wins the race. The first
    revision hardcoded a single target and was structurally unable to see this."""
    assert "scripts/wsl_startup_hook.sh" in gate._ENTRY_POINTS
    (tmp_path / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    (tmp_path / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").write_text(
        f"#!/bin/bash\n{_REFRESH}\n{_RANKER}\n", encoding="utf-8"
    )
    # the boot path ranks but never rebuilds — exactly the state shipped at 5fd58526
    (tmp_path / "scripts" / "wsl_startup_hook.sh").write_text(
        "#!/bin/bash\n$VENV_PYTHON $FABRIK_ROOT/scripts/kilo-benchmarks/rank_task_subagents.py\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "_REPO", tmp_path)
    assert gate.main() == 1


def test_the_gate_is_actually_wired_to_something():
    """A-7, the largest finding of the Phase-C review: the first revision was registered NOWHERE —
    not in final_gate.py, not in pre-commit, not in any test — while the commit message asserted it
    "holds that ordering". An unwired gate is a claimed guarantee that does not exist, and FIX
    DIRECTIVE #4 calls the thing it guards ungraded. This test is what keeps it wired."""
    config = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "_check_refresh_before_ranker.py" in config, (
        "the ordering gate is not referenced by .pre-commit-config.yaml — nothing runs it"
    )
