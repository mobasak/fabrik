"""Local coding benchmark runner — EvalPlus + libs.subagents composition.

Spec: docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md
Plan: docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md

Runs HumanEval + MBPP via EvalPlus against configured target models, dispatched
in parallel via libs.subagents.run_agents (owned-paths + bwrap sandbox + cost caps).
Writes pass@1 * 100 to agents.humaneval_score + agents.coding_score.
Does NOT touch weighted_coding (BenchLM-reserved via scrape_benchlm.py:70).
Does NOT call record_agent_run (would misattribute pass@1 to orchestrator per pg_ledger.py:157-172).
"""
# AFTER-EDIT: docs/reference/kilo/CODING_SUBAGENT_SELECTION.md (regenerated after this runs)

from __future__ import annotations

import json
import pathlib
import re
import shlex
import subprocess  # noqa: F401  — kept for Phase C main()
import sys

SCRIPT_DIR = pathlib.Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
sys.path.insert(0, str((SCRIPT_DIR / "libs").resolve()))

from subagents import AgentSpec, run_agents  # noqa: E402, F401

# Injection-safety boundary — reject anything not in this whitelist BEFORE it
# reaches the shell task string. Model IDs from OR are always vendor/name-tag
# with limited chars; datasets are always a small enum. Fail-closed on anything
# with a shell metacharacter (`;`, `$`, `` ` ``, `|`, `&`, whitespace, quotes,
# a leading `-` that would be argparse-interpreted, or a `..` path segment).
_SAFE_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./_:-]*$")
_SAFE_DATASET_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def _validate_model_id(model_id: str) -> str:
    if not _SAFE_MODEL_ID_RE.match(model_id):
        raise ValueError(
            f"unsafe model id {model_id!r}: must match {_SAFE_MODEL_ID_RE.pattern} "
            f"(shell-injection guard). Reject at CLI boundary."
        )
    return model_id


def _validate_dataset(dataset: str) -> str:
    if not _SAFE_DATASET_RE.match(dataset):
        raise ValueError(
            f"unsafe dataset {dataset!r}: must match {_SAFE_DATASET_RE.pattern} "
            f"(path-traversal + shell-injection guard). Reject at CLI boundary."
        )
    return dataset


DEFAULT_MODELS = [
    "bytedance-seed/seed-1.6-flash",
    "bytedance-seed/seed-2.0-mini",
    "bytedance-seed/seed-1.6",
    "bytedance-seed/seed-2.0-lite",
]
DEFAULT_DATASETS = ["humaneval", "mbpp"]
ORCHESTRATOR_MODEL = "qwen/qwen3-coder-flash"  # verified live on OR in Phase A step 2c


def build_specs(
    target_models: list[str],
    datasets: list[str],
    work_dir: pathlib.Path,
    orchestrator: str = ORCHESTRATOR_MODEL,
    cost_cap: float = 5.0,
) -> list[AgentSpec]:
    """Build one AgentSpec per (target_model, dataset). Owned-paths disjoint.

    Each spec's `task` is the shell command that runs `evalplus.evaluate` against
    the target model on the given dataset. spec.model is the ORCHESTRATOR that
    executes the shell (any cheap Auto-tier coder), NOT the target being benched.
    """
    specs: list[AgentSpec] = []
    for target in target_models:
        _validate_model_id(target)  # fail-closed on shell metachars / leading -
        for ds in datasets:
            _validate_dataset(ds)  # fail-closed on shell metachars / path traversal
            unit_dir = work_dir / target.replace("/", "__") / ds
            unit_dir.mkdir(parents=True, exist_ok=True)
            # Shell-safe interpolation via shlex.quote — defense in depth atop the
            # regex guards above; the pool orchestrator runs `task` via bash.
            task = (
                f"cd {shlex.quote(str(unit_dir))} && "
                f"OPENAI_API_KEY=$OPENROUTER_API_KEY evalplus.evaluate "
                f"--backend openai "
                f"--base-url https://openrouter.ai/api/v1 "
                f"--model {shlex.quote(target)} "
                f"--dataset {shlex.quote(ds)} "
                f"--greedy --root ./results"
            )
            specs.append(
                AgentSpec(
                    task=task,
                    model=orchestrator,
                    task_type="code",
                    tools_enabled=True,
                    owned_paths=[str(unit_dir)],
                    max_cost_usd=cost_cap,
                    wall_clock_s=1800,  # 30 min per unit
                )
            )
    return specs


def parse_eval_results(results_json: pathlib.Path) -> dict[str, float]:
    """Read ONE EvalPlus dataset's eval_results.json → {base, plus} pass@1.

    Per-dataset scope: returns 2 keys, both raw 0.0-1.0 rates. Caller merges
    per-model humaneval + mbpp results via merge_dataset_results().

    Shape verified against evalplus/evaluate.py:245-290 + eval/__init__.py:87
    (PASS = "pass"). Note: EvalPlus does NOT save pass@1 to the JSON — it only
    prints it to stdout. We compute it from the per-task status records.

    For --greedy (n=1 sample per task), pass@1 = correct_count / total_count.
    """
    data = json.loads(results_json.read_text())
    eval_dict = data.get("eval", {})
    if not eval_dict:
        return {"base": 0.0, "plus": 0.0}

    total = 0
    base_correct = 0
    plus_correct = 0
    for _task_id, attempts in eval_dict.items():
        for attempt in attempts:
            total += 1
            base_pass = attempt.get("base_status") == "pass"
            plus_pass = attempt.get("plus_status") == "pass"
            if base_pass:
                base_correct += 1
            if base_pass and plus_pass:
                plus_correct += 1

    if total == 0:
        return {"base": 0.0, "plus": 0.0}
    return {"base": base_correct / total, "plus": plus_correct / total}


def merge_dataset_results(
    humaneval: dict[str, float], mbpp: dict[str, float]
) -> dict[str, float]:
    """Merge two per-dataset {base, plus} dicts into the 4-key dict write_scores consumes.

    Raises KeyError if either input dict is missing a required key.
    """
    return {
        "base": humaneval["base"],  # HumanEval pass@1
        "plus": humaneval["plus"],  # HumanEval+ pass@1
        "mbpp_base": mbpp["base"],  # MBPP pass@1
        "mbpp_plus": mbpp["plus"],  # MBPP+ pass@1
    }
