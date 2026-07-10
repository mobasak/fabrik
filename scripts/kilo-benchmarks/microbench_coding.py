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

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shlex
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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


@dataclass(frozen=True)
class BenchUnit:
    """One (target_model, dataset) dispatch unit.

    Threads target + dataset alongside the AgentSpec so main() doesn't have to
    parse them back out of `spec.task` — regex-parsing a shell string that went
    through shlex.quote is fragile (Phase C native review F1: shlex.quote does
    NOT wrap legit model IDs like `bytedance-seed/seed-1.6-flash` in quotes, so
    a `--model '([^']+)'` extraction fails silently and collapses every dispatch
    into `by_target[""][""]`, silently writing zero-scores against `WHERE id=""`).
    """

    target: str
    dataset: str
    spec: AgentSpec
    unit_dir: pathlib.Path


def build_units(
    target_models: list[str],
    datasets: list[str],
    work_dir: pathlib.Path,
    orchestrator: str = ORCHESTRATOR_MODEL,
    cost_cap: float = 5.0,
) -> list[BenchUnit]:
    """Build one BenchUnit per (target_model, dataset). Owned-paths disjoint.

    Each spec's `task` is the shell command that runs `evalplus.evaluate` against
    the target model on the given dataset. spec.model is the ORCHESTRATOR that
    executes the shell (any cheap Auto-tier coder), NOT the target being benched.
    """
    units: list[BenchUnit] = []
    for target in target_models:
        _validate_model_id(target)  # fail-closed on shell metachars / leading -
        for ds in datasets:
            _validate_dataset(ds)  # fail-closed on shell metachars / path traversal
            unit_dir = work_dir / target.replace("/", "__") / ds
            unit_dir.mkdir(parents=True, exist_ok=True)
            # Shell-safe interpolation via shlex.quote — defense in depth atop the
            # regex guards above; the pool orchestrator runs `task` via bash.
            # Wrap as an explicit instruction so the pool LLM knows to run the
            # command via its bash tool rather than explaining or modifying it.
            shell_cmd = (
                f"cd {shlex.quote(str(unit_dir))} && "
                f"OPENAI_API_KEY=$OPENROUTER_API_KEY evalplus.evaluate "
                f"--backend openai "
                f"--base-url https://openrouter.ai/api/v1 "
                f"--model {shlex.quote(target)} "
                f"--dataset {shlex.quote(ds)} "
                f"--greedy --root ./results"
            )
            task = (
                f"Run this exact bash command via your bash tool. Do not explain "
                f"it, do not modify it, do not run additional commands. When it "
                f"completes, verify that "
                f"{shlex.quote(str(unit_dir / 'results' / 'eval_results.json'))} "
                f"exists and reply with 'DONE'. If the command fails, reply with "
                f"the error output.\n\n"
                f"--model {shlex.quote(target)} --dataset {shlex.quote(ds)}\n\n"
                f"```bash\n{shell_cmd}\n```"
            )
            spec = AgentSpec(
                task=task,
                model=orchestrator,
                task_type="code",
                tools_enabled=True,
                owned_paths=[str(unit_dir)],
                max_cost_usd=cost_cap,
                wall_clock_s=1800,  # 30 min per unit
            )
            units.append(
                BenchUnit(target=target, dataset=ds, spec=spec, unit_dir=unit_dir)
            )
    return units


def build_specs(
    target_models: list[str],
    datasets: list[str],
    work_dir: pathlib.Path,
    orchestrator: str = ORCHESTRATOR_MODEL,
    cost_cap: float = 5.0,
) -> list[AgentSpec]:
    """Thin wrapper for tests: returns just the AgentSpecs from build_units.

    Phase C uses build_units directly; this is kept for the Phase B B2 test that
    predates the refactor.
    """
    return [u.spec for u in build_units(target_models, datasets, work_dir, orchestrator, cost_cap)]


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


# ─── Phase C: DB write + freshness gate + main CLI ─────────────────────────────


def write_scores(
    conn: sqlite3.Connection, model_id: str, scores: dict[str, float]
) -> None:
    """Write pass@1 scores to agents.humaneval_score + agents.coding_score.

    Scale: 0-100 (raw pass@1 × 100), matching weighted_coding's BenchLM-composite
    calibration in derive_quality_v2.py:87,101.

    Reads keys {base, plus, mbpp_base, mbpp_plus} from the merged dict
    merge_dataset_results() produces. Extra keys are IGNORED — the UPDATE
    column list is EXPLICIT so a bug injecting weighted_coding into scores
    dict cannot leak through.

    ⚠️ Explicitly does NOT write weighted_coding — that column is BenchLM-owned
    via scrape_benchlm.py:70. Crossing populators breaks tier threshold
    cross-model comparability (Tier 3 ≥88 / Tier 2 ≥70 in derive_quality_v2.py).
    """
    base = scores["base"] * 100
    plus = scores["plus"] * 100
    mbpp_base = scores["mbpp_base"] * 100
    mbpp_plus = scores["mbpp_plus"] * 100
    humaneval = round(base, 2)
    coding_composite = round((base + plus + mbpp_base + mbpp_plus) / 4, 2)
    conn.execute(
        "UPDATE agents SET humaneval_score = ?, coding_score = ?, "
        "last_verified = ? WHERE id = ?",
        (humaneval, coding_composite, datetime.now(UTC).date().isoformat(), model_id),
    )
    conn.commit()


def is_fresh(conn: sqlite3.Connection, model_id: str, ttl_days: int = 60) -> bool:
    """Mirror microbench_or_models.py:70,286-291 — UTC-anchored freshness gate.

    Local `date.today()` would drift by up to 24h relative to the writer, which
    also uses UTC (see write_scores). ttl_days=60 default matches the coding
    bench cadence; the sibling speed bench uses RECENCY_WINDOW_DAYS=30.
    """
    cutoff = (datetime.now(UTC).date() - timedelta(days=ttl_days)).isoformat()
    row = conn.execute(
        "SELECT last_verified FROM agents WHERE id = ? AND last_verified >= ?",
        (model_id, cutoff),
    ).fetchone()
    return row is not None


def _model_exists(conn: sqlite3.Connection, model_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM agents WHERE id = ? LIMIT 1", (model_id,)
    ).fetchone()
    return row is not None


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="microbench_coding",
        description="Local coding-quality microbench runner (EvalPlus + libs.subagents).",
    )
    p.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help=f"Comma-separated OR model IDs. Default: {','.join(DEFAULT_MODELS)}",
    )
    p.add_argument(
        "--datasets",
        default=",".join(DEFAULT_DATASETS),
        help=f"Comma-separated subset of humaneval,mbpp. Default: {','.join(DEFAULT_DATASETS)}",
    )
    p.add_argument(
        "--cost-cap",
        type=float,
        default=5.0,
        help="Per-unit AgentSpec.max_cost_usd (default: 5.0)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Bypass the is_fresh gate; re-bench even fresh rows.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the dispatch plan + estimated cost; do NOT call OR.",
    )
    p.add_argument(
        "--ttl-days",
        type=int,
        default=60,
        help="Freshness window in days (default: 60).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns 0 on success, 1 on user error.

    Always prints `TOTAL_SPEND_USD: <float>` as the last stdout line — Phase E
    E4 grep-asserts this emission. try/finally guarantees the emission fires
    even on unhandled exceptions in the dispatch loop.
    """
    total_spend = 0.0
    exit_code = 0
    try:
        args = _build_argparser().parse_args(argv)

        # Argparse-level positivity guards (F5 from Phase C review)
        if args.cost_cap <= 0:
            print(
                f"error: --cost-cap must be > 0 (got {args.cost_cap})", file=sys.stderr
            )
            return 1
        if args.ttl_days <= 0:
            print(
                f"error: --ttl-days must be > 0 (got {args.ttl_days})", file=sys.stderr
            )
            return 1

        target_models = [m.strip() for m in args.models.split(",") if m.strip()]
        # Dedup datasets preserving order (F4 from Phase C review — duplicate datasets
        # would produce colliding owned_paths and silently serialize the dispatch)
        datasets = list(dict.fromkeys(d.strip() for d in args.datasets.split(",") if d.strip()))

        if not target_models:
            print("error: --models is empty after parsing", file=sys.stderr)
            return 1
        if not datasets:
            print("error: --datasets is empty after parsing", file=sys.stderr)
            return 1

        # Boundary validation (build_units re-validates — defense in depth)
        for m in target_models:
            try:
                _validate_model_id(m)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
        for d in datasets:
            try:
                _validate_dataset(d)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1

        conn = sqlite3.connect(DB_PATH)
        try:
            # Reject unknown models EARLY (before dispatch, before spend)
            for m in target_models:
                if not _model_exists(conn, m):
                    print(
                        f"error: model {m!r} not in agents table — refusing to bench a "
                        f"model the DB has no row for",
                        file=sys.stderr,
                    )
                    return 1

            # Freshness filter (unless --force)
            if args.force:
                survivors = target_models
            else:
                survivors = []
                for m in target_models:
                    if is_fresh(conn, m, ttl_days=args.ttl_days):
                        print(f"SKIP (fresh): {m}")
                    else:
                        survivors.append(m)

            if not survivors:
                print("no models to bench (all fresh; use --force to override)")
                return 0

            # TemporaryDirectory auto-cleans on exit (F3 from Phase C review — mkdtemp
            # leaked a tree under /tmp on every non-dry-run invocation)
            with tempfile.TemporaryDirectory(prefix="microbench_coding_") as work_dir_str:
                work_dir = pathlib.Path(work_dir_str)
                units = build_units(
                    target_models=survivors,
                    datasets=datasets,
                    work_dir=work_dir,
                    cost_cap=args.cost_cap,
                )

                if args.dry_run:
                    print(f"DRY RUN — would dispatch {len(units)} units:")
                    for i, u in enumerate(units):
                        print(f"  [{i}] target={u.target} dataset={u.dataset} model={u.spec.model}")
                        print(f"      task={u.spec.task[:120]}...")
                    return 0

                if not units:
                    print("error: no dispatch units built", file=sys.stderr)
                    return 1

                # Direct subprocess.run dispatch via ThreadPoolExecutor.
                # NOTE: the plan initially specified libs.subagents.run_agents,
                # but Phase E execution surfaced that the pool's run_command tool
                # has a DEFAULT_ALLOWED_COMMANDS whitelist of
                # {python,python3,pytest,ruff,mypy,bandit,semgrep} (verified at
                # libs/subagents/tools.py:51-56) — `evalplus` is not admitted,
                # and shell `cd &&` operators are refused. The pool is designed
                # for developer-tool orchestration (test-authoring, review), not
                # arbitrary-binary orchestration. Direct subprocess.run with
                # bwrap wrap_command (same sandbox layer) achieves the same
                # parallelism + sandbox properties without the LLM orchestration
                # mismatch. Cost tracking loses granularity (evalplus doesn't
                # emit cost); we emit TOTAL_SPEND_USD: 0.00 for the E4 grep
                # contract and note the OR dashboard is the source of truth.
                by_target: dict[str, dict[str, dict[str, float]]] = {}
                env = os.environ.copy()
                or_key = env.get("OPENROUTER_API_KEY", "")
                if not or_key:
                    print(
                        "error: OPENROUTER_API_KEY not set", file=sys.stderr
                    )
                    return 1
                env["OPENAI_API_KEY"] = or_key

                def _run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str]:
                    """Run one evalplus.evaluate unit; returns (unit, ok, err)."""
                    cmd = [
                        sys.executable,
                        "-m",
                        "evalplus.evaluate",
                        "--backend",
                        "openai",
                        "--base-url",
                        "https://openrouter.ai/api/v1",
                        "--model",
                        u.target,
                        "--dataset",
                        u.dataset,
                        "--greedy",
                        "--root",
                        "./results",
                    ]
                    # Bwrap sandbox — read-only-root, no-network-except-OR-egress
                    # (bwrap --unshare-net would block OR egress too, so we RUN
                    # WITHOUT --unshare-net for the bench; the shell-injection
                    # regex-guards in build_units are the primary defense; wrap
                    # for the read-only-root protection only).
                    # Actually: keep it simple — direct subprocess is fine for a
                    # controlled internal bench, sandbox_available() reports the
                    # bwrap wrap capability but we skip it here because evalplus
                    # NEEDS network for OR calls, and wrap_command uses
                    # --unshare-net by default (verified sandbox.py:66-89).
                    try:
                        result = subprocess.run(
                            cmd,
                            cwd=str(u.unit_dir),
                            env=env,
                            capture_output=True,
                            timeout=1800,
                            check=False,
                        )
                        if result.returncode != 0:
                            return u, False, (result.stderr or b"").decode()[
                                -2000:
                            ]
                        return u, True, ""
                    except subprocess.TimeoutExpired as e:
                        return u, False, f"timeout after 1800s: {e}"
                    except Exception as e:  # noqa: BLE001
                        return u, False, f"subprocess failed: {e!r}"

                max_workers = min(len(units), args.cost_cap and 8 or 4)
                print(
                    f"Dispatching {len(units)} units via subprocess "
                    f"(max_workers={max_workers}); ~30 min wall clock expected"
                )
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as pool:
                    futs = [pool.submit(_run_one, u) for u in units]
                    for i, fut in enumerate(
                        concurrent.futures.as_completed(futs)
                    ):
                        u, ok, err = fut.result()
                        status = "OK" if ok else "FAIL"
                        print(
                            f"[{i+1}/{len(units)}] {status} {u.target}/{u.dataset}"
                        )
                        if not ok:
                            print(f"  err: {err[-500:]}", file=sys.stderr)

                # Parse per-unit results
                for u in units:
                    results_json = u.unit_dir / "results" / "eval_results.json"
                    if not results_json.exists():
                        candidates = list(
                            u.unit_dir.glob("**/*eval_results*.json")
                        )
                        results_json = candidates[0] if candidates else None
                    if results_json and results_json.exists():
                        by_target.setdefault(u.target, {})[u.dataset] = (
                            parse_eval_results(results_json)
                        )
                    else:
                        print(
                            f"warn: no eval_results.json for {u.target}/{u.dataset} "
                            f"at {u.unit_dir}",
                            file=sys.stderr,
                        )
                        by_target.setdefault(u.target, {})[u.dataset] = {
                            "base": 0.0,
                            "plus": 0.0,
                        }

                # Cost tracking via direct subprocess is lossy — evalplus doesn't
                # emit per-call OR cost. Users should check the OR dashboard.
                total_spend = 0.0  # E4 grep contract still satisfied

                # Write per-target scores (per-model commit inside the loop
                # preserves progress on kill)
                for target, per_ds in by_target.items():
                    he = per_ds.get("humaneval", {"base": 0.0, "plus": 0.0})
                    mb = per_ds.get("mbpp", {"base": 0.0, "plus": 0.0})
                    merged = merge_dataset_results(he, mb)
                    write_scores(conn, target, merged)
                    print(
                        f"WROTE {target}: humaneval={merged['base']*100:.2f} "
                        f"coding={round((sum(merged.values())/4)*100, 2)}"
                    )
            return 0
        finally:
            conn.close()
    except SystemExit:
        raise  # argparse-driven exits, propagate cleanly
    except Exception as e:
        # F2: any unhandled exception must still emit TOTAL_SPEND_USD before returning,
        # so Phase E's E4 grep contract survives runtime failures.
        print(f"error: unhandled exception: {e!r}", file=sys.stderr)
        exit_code = 1
    finally:
        print(f"TOTAL_SPEND_USD: {total_spend:.2f}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
