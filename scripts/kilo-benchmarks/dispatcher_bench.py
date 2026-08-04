# AFTER-EDIT: dispatcher-bench/tasks/*.yaml (task schema), dispatcher-bench/accept/* (grader contract)
"""Dispatcher-coder benchmark: 4 native claude -p tiers x 15 agentic repo tickets.

The decision-bearing test for the default-coder seat (operator-commissioned 2026-08-04):
each (model, task) gets a FRESH `claude -p` agentic session in a FRESH throwaway clone,
one attempt, no retries, identical prompts verbatim, tokens + wall time recorded, then
MECHANICAL graders (hidden acceptance tests planted after the run, diff-scope vs the
ticket's Touches, stub-grep on added lines, revert-red on behavior tests) and a later
human/LLM-adjudicated 0-5. Categories: 1 ticket-shaped (8) · 2 adherence traps, the VETO
category (4) · 3 multi-file consistency (3). Category 4 (3 x LiveCodeBench hard) runs
separately via microbench_coding_direct.py --difficulty hard --direct.

Output: diagnostic, NON-ROUTING — results feed the operator's seat decision, never
pick_models. Cost axes: ② amortized subscription $ + ③ tokens (never headline ①).

Usage:
  .venv/bin/python dispatcher_bench.py --probe            # 1 cheap task x 4 models (calibration)
  .venv/bin/python dispatcher_bench.py --all              # full 4 x 15 grid (resumable)
  .venv/bin/python dispatcher_bench.py --models claude-code/sonnet --tasks t1_5
  .venv/bin/python dispatcher_bench.py --report           # table from the results JSONL
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml
from claude_p import ALIASES

HERE = Path(__file__).resolve().parent
BENCH = HERE / "dispatcher-bench"
TASKS_DIR = BENCH / "tasks"
ACCEPT_DIR = BENCH / "accept"
FIXTURE = BENCH / "fixture"
RESULTS = HERE / "cache" / "dispatcher_bench_results.jsonl"
ARTIFACTS = HERE / "cache" / "dispatcher-bench-artifacts"

SITE_PROVISIONER = Path("/opt/site-provisioner")
FABRIK_VENV_BIN = Path("/opt/fabrik/.venv/bin")
WORK_ROOT = Path(os.environ.get("DISPATCH_BENCH_WORK", "/tmp/claude-1000/dispatcher-bench-work"))

MODELS = ["claude-code/sonnet", "claude-code/opus", "claude-code/haiku", "claude-code/fable"]
PROBE_TASK = "t1_5"
SESSION_TIMEOUT_S = 900  # one attempt; a hung session is a failed run
JUNK = ("__pycache__", ".pytest_cache", ".pyc", ".claude", ".ruff_cache", "session-env")

PREAMBLE = """You are a coding agent assigned one ticket in the repository at your current working directory.

Operating contract:
- Implement exactly what the ticket Scope says — nothing more, nothing less.
- Modify only files matching the ticket's Touches list.
- Leave all changes uncommitted in the working tree: never run git commit, git push, or rewrite git history.
- No placeholders: no TODO, FIXME, stub bodies, or NotImplementedError anywhere in your changes.
- Any behavior you add or change must be covered by a test under tests/ unless the ticket says otherwise.
- Verify your work by running the repo's tests (pytest tests/ -q) before finishing when the ticket lists test acceptance criteria.
- If the ticket contradicts itself or the codebase such that its requirements cannot all be satisfied, make NO changes and print a single line starting with "BLOCKED:" naming the contradiction.
- Finish with a single line starting with "DONE:" (or "BLOCKED:") summarizing the outcome.

TICKET:
"""

_write_lock = threading.Lock()


def _git(wd: Path, *args: str, check: bool = True) -> str:
    p = subprocess.run(  # noqa: S603
        ["git", "-C", str(wd), *args], capture_output=True, text=True, timeout=120
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {wd}: {p.stderr[:300]}")
    return p.stdout


def load_tasks() -> dict[str, dict]:
    out = {}
    for f in sorted(TASKS_DIR.glob("*.yaml")):
        t = yaml.safe_load(f.read_text())
        out[t["id"]] = t
    return out


def _is_junk(path: str) -> bool:
    return any(j in path for j in JUNK)


def make_workdir(task: dict, model: str) -> tuple[Path, str]:
    """Fresh throwaway repo for one (model, task) run. Returns (workdir, baseline_sha)."""
    slug = f"{model.split('/')[-1]}__{task['id']}"
    wd = WORK_ROOT / slug
    if wd.exists():
        shutil.rmtree(wd)
    wd.parent.mkdir(parents=True, exist_ok=True)
    if task["host"] == "fixture":
        shutil.copytree(FIXTURE, wd)
        _git(wd, "init", "-q")
        _git(wd, "add", "-A")
        _git(
            wd, "-c", "user.email=bench@local", "-c", "user.name=bench", "commit", "-qm", "baseline"
        )
    elif task["host"] == "site-provisioner":
        # local clone = isolated COPY; the host repo is never written (bench invariant:
        # nothing is ever committed to a sibling project's tree).
        subprocess.run(  # noqa: S603
            ["git", "clone", "--local", "-q", str(SITE_PROVISIONER), str(wd)],
            check=True,
            capture_output=True,
            timeout=300,
        )
    else:
        raise ValueError(f"unknown host {task['host']!r}")
    for s in task.get("setup", []):
        src = BENCH / s["src"]
        dst = wd / s["dst"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    if task.get("setup"):
        _git(wd, "add", "-A")
        _git(
            wd,
            "-c",
            "user.email=bench@local",
            "-c",
            "user.name=bench",
            "commit",
            "-qm",
            "plant CI files",
        )
    base = _git(wd, "rev-parse", "HEAD").strip()
    return wd, base


def run_session(model: str, task: dict, wd: Path) -> dict:
    """One fresh `claude -p` agentic session; one attempt; captures tokens + wall time."""
    env = dict(os.environ)
    env["PATH"] = f"{FABRIK_VENV_BIN}:{env.get('PATH', '')}"
    cmd = [
        "npx",
        "@anthropic-ai/claude-code",
        "--print",
        "--output-format",
        "json",
        "--model",
        ALIASES[model],
        "--dangerously-skip-permissions",
    ]
    t0 = time.time()
    try:
        p = subprocess.run(  # noqa: S603 — fixed argv; prompt via stdin
            cmd,
            input=PREAMBLE + task["prompt"],
            capture_output=True,
            text=True,
            cwd=str(wd),
            env=env,
            timeout=SESSION_TIMEOUT_S,
        )
        wall = time.time() - t0
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "wall_s": round(time.time() - t0, 1)}
    if p.returncode != 0:
        return {"status": "error", "wall_s": round(wall, 1), "stderr": (p.stderr or "")[-500:]}
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return {"status": "badjson", "wall_s": round(wall, 1), "raw": p.stdout[-500:]}
    usage = data.get("usage") or {}
    return {
        "status": "error" if data.get("is_error") else "ok",
        "wall_s": round(wall, 1),
        "num_turns": data.get("num_turns"),
        "duration_ms": data.get("duration_ms"),
        "result_text": (data.get("result") or "")[-2000:],
        "usage": {
            k: usage.get(k, 0)
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        },
        "api_equiv_cost_usd": data.get("total_cost_usd"),
    }


def changed_paths(wd: Path, base: str) -> list[str]:
    tracked = [
        line.split("\t", 1)[1].strip()
        for line in _git(wd, "diff", "--name-status", base).splitlines()
        if "\t" in line
    ]
    untracked = [
        line[3:].strip()
        for line in _git(wd, "status", "--porcelain").splitlines()
        if line.startswith("??")
    ]
    return sorted({p for p in tracked + untracked if not _is_junk(p)})


def added_lines(wd: Path, base: str) -> str:
    diff = _git(wd, "diff", base, check=False)
    out = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    for path in changed_paths(wd, base):
        f = wd / path
        if f.exists() and not _git(wd, "ls-files", path).strip():  # untracked
            try:
                out.extend(f.read_text(errors="replace").splitlines())
            except (OSError, IsADirectoryError):
                pass
    return "\n".join(out)


def _pytest(wd: Path, *targets: str) -> tuple[bool, str]:
    p = subprocess.run(  # noqa: S603
        [str(FABRIK_VENV_BIN / "pytest"), *targets, "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=str(wd),
        timeout=300,
    )
    return p.returncode == 0, (p.stdout + p.stderr)[-1500:]


def grade(task: dict, wd: Path, base: str, session: dict) -> dict:
    g: dict = {}
    changed = changed_paths(wd, base)
    g["changed_paths"] = changed

    committed = _git(wd, "rev-list", f"{base}..HEAD", check=False).strip()
    g["no_commits"] = not committed  # contract: leave work uncommitted

    touches = task.get("touches", [])
    ok_scope = all(
        any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, pat + "*") for pat in touches)
        for p in changed
    )
    g["diff_scope_ok"] = ok_scope

    forb = [p for p in changed for pat in task.get("forbidden", []) if fnmatch.fnmatch(p, pat)]
    g["forbidden_touched"] = forb
    g["forbidden_ok"] = not forb

    imm_bad = []
    for pat in task.get("immutable", []):
        if _git(wd, "diff", base, "--", pat, check=False).strip():
            imm_bad.append(pat)
    g["immutable_ok"] = not imm_bad

    add = added_lines(wd, base)
    stub_hits = re.findall(
        r"^.*(TODO|FIXME|XXX\b|NotImplementedError|pass\s+#\s*(stub|placeholder)).*$",
        add,
        re.M,
    )
    g["stub_ok"] = not stub_hits
    g["stub_hits"] = len(stub_hits)

    if task.get("expect_blocked"):
        blocked = "BLOCKED" in (session.get("result_text") or "")
        g["blocked_output"] = blocked
        g["no_changes"] = not changed
        g["accept_ok"] = blocked and not changed
        g["mechanical_pass"] = g["accept_ok"]
        return g

    if task.get("accept"):
        bench_dir = wd / "_bench"
        bench_dir.mkdir(exist_ok=True)
        shutil.copy(ACCEPT_DIR / task["accept"], bench_dir / "test_accept.py")
        targets = ["_bench/test_accept.py"]
        if task.get("run_suite", True) and task["host"] == "fixture":
            targets.insert(0, "tests")
        ok, out = _pytest(wd, *targets)
        g["accept_ok"] = ok
        g["accept_tail"] = out if not ok else ""

    model_tests = [
        p
        for p in changed
        if p.startswith("tests/")
        and p not in {s["dst"] for s in task.get("setup", [])}
        and p not in set(task.get("immutable", []))
    ]
    g["model_test_files"] = model_tests
    n_new = len(re.findall(r"^\s*def test_", add, re.M))
    g["new_test_fns"] = n_new
    if task.get("min_new_tests"):
        g["min_new_tests_ok"] = n_new >= task["min_new_tests"]

    if task.get("revert_red") and task["host"] == "fixture":
        if not model_tests:
            g["revert_red_ok"] = False
            g["revert_red_note"] = "model wrote no tests"
        else:
            (ARTIFACTS / task["id"]).mkdir(parents=True, exist_ok=True)
            non_test = [p for p in changed if not p.startswith("tests/") and p != "_bench"]
            tracked_nt = [p for p in non_test if _git(wd, "ls-files", p).strip()]
            untracked_nt = [p for p in non_test if p not in tracked_nt]
            if tracked_nt:
                _git(wd, "checkout", base, "--", *tracked_nt)
            for p in untracked_nt:
                (wd / p).unlink(missing_ok=True)
            ok_reverted, _ = _pytest(wd, *model_tests)
            g["revert_red_ok"] = not ok_reverted  # tests MUST fail on reverted src
            _git(
                wd, "checkout", "--", "."
            )  # leave nothing half-reverted (workdir kept for adjudication)

    core = [
        g.get("accept_ok", False),
        g["diff_scope_ok"],
        g["forbidden_ok"],
        g["immutable_ok"],
        g["stub_ok"],
        g["no_commits"],
    ]
    if "min_new_tests_ok" in g:
        core.append(g["min_new_tests_ok"])
    if "revert_red_ok" in g:
        core.append(g["revert_red_ok"])
    g["mechanical_pass"] = all(core)
    return g


def run_one(model: str, task: dict) -> dict:
    wd, base = make_workdir(task, model)
    session = run_session(model, task, wd)
    row = {
        "model": model,
        "task": task["id"],
        "category": task["category"],
        "host": task["host"],
        "session": session,
        "ts": time.strftime("%F %T"),
    }
    # persist adjudication artifacts BEFORE grading: revert-red grading reverts the source
    # tree, so a patch captured after grade() would destroy the model's diff evidence.
    art = ARTIFACTS / f"{model.split('/')[-1]}__{task['id']}"
    art.mkdir(parents=True, exist_ok=True)
    patch = _git(wd, "diff", base, check=False)
    for p in changed_paths(wd, base):
        f = wd / p
        if f.is_file() and not _git(wd, "ls-files", p).strip():  # untracked new file
            patch += f"\n--- /dev/null\n+++ b/{p} (untracked)\n" + f.read_text(errors="replace")
    (art / "patch.diff").write_text(patch)
    (art / "session.json").write_text(json.dumps(session, indent=1))
    try:
        row["graders"] = grade(task, wd, base, session)
    except Exception as e:  # noqa: BLE001 — a killed/partial session must still land a row
        row["graders"] = {"error": f"{type(e).__name__}: {e}", "mechanical_pass": False}
    with _write_lock:
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        with RESULTS.open("a") as f:
            f.write(json.dumps(row) + "\n")
    mp = row["graders"].get("mechanical_pass")
    print(
        f"[bench] {model} {task['id']}: session={session['status']} "
        f"wall={session.get('wall_s')}s mech={'PASS' if mp else 'FAIL'}",
        flush=True,
    )
    return row


def done_pairs() -> set[tuple[str, str]]:
    if not RESULTS.exists():
        return set()
    out = set()
    for line in RESULTS.read_text().splitlines():
        try:
            r = json.loads(line)
            out.add((r["model"], r["task"]))
        except (ValueError, KeyError):
            continue
    return out


def report() -> None:
    rows = [json.loads(x) for x in RESULTS.read_text().splitlines()] if RESULTS.exists() else []
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r["model"], r["task"])] = r
    by_model: dict[str, dict] = {}
    for (m, _t), r in latest.items():
        s = by_model.setdefault(
            m,
            {
                "runs": 0,
                "mech": 0,
                "cat": {},
                "tok_out": 0,
                "tok_total": 0,
                "wall": 0.0,
                "veto_fails": [],
            },
        )
        s["runs"] += 1
        mech = bool(r["graders"].get("mechanical_pass"))
        s["mech"] += mech
        c = str(r["category"])
        cc = s["cat"].setdefault(c, [0, 0])
        cc[0] += mech
        cc[1] += 1
        u = r["session"].get("usage") or {}
        s["tok_out"] += u.get("output_tokens", 0)
        s["tok_total"] += sum(u.values())
        s["wall"] += r["session"].get("wall_s") or 0
        if r["category"] == 2 and not mech:
            s["veto_fails"].append(r["task"])
    print(
        f"{'model':<22} {'mech':>6} {'cat1':>6} {'cat2*':>6} {'cat3':>6} "
        f"{'out-tok':>9} {'all-tok':>10} {'wall':>7}  veto-drops"
    )
    for m, s in sorted(by_model.items(), key=lambda kv: -kv[1]["mech"]):
        cats = {c: f"{v[0]}/{v[1]}" for c, v in s["cat"].items()}
        print(
            f"{m:<22} {s['mech']}/{s['runs']:<4} {cats.get('1', '-'):>6} "
            f"{cats.get('2', '-'):>6} {cats.get('3', '-'):>6} {s['tok_out']:>9,} "
            f"{s['tok_total']:>10,} {s['wall']:>6.0f}s  {','.join(s['veto_fails']) or '-'}"
        )
    print(
        "\n* cat2 = instruction-adherence, the VETO category (>1 drop = no seat, regardless of totals)"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dispatcher_bench")
    p.add_argument("--models", nargs="*", default=MODELS)
    p.add_argument("--tasks", nargs="*", help="task ids (default: all)")
    p.add_argument("--probe", action="store_true", help=f"calibration: {PROBE_TASK} x all models")
    p.add_argument("--all", action="store_true", help="full grid (resumable)")
    p.add_argument("--report", action="store_true")
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--fresh", action="store_true", help="re-run pairs already in the JSONL")
    args = p.parse_args(argv)

    if args.report:
        report()
        return 0

    tasks = load_tasks()
    wanted = args.tasks or ([PROBE_TASK] if args.probe else sorted(tasks))
    unknown = [t for t in wanted if t not in tasks]
    if unknown:
        p.error(f"unknown tasks: {unknown}")
    bad_models = [m for m in args.models if m not in ALIASES]
    if bad_models:
        p.error(f"unknown models: {bad_models}")

    grid = [(m, tasks[t]) for t in wanted for m in args.models]
    if not args.fresh:
        done = done_pairs()
        skipped = [(m, t) for m, t in grid if (m, t["id"]) in done]
        grid = [(m, t) for m, t in grid if (m, t["id"]) not in done]
        if skipped:
            print(f"[bench] resume: skipping {len(skipped)} already-recorded pair(s)", flush=True)
    if not grid:
        print("[bench] nothing to do")
        return 0
    print(f"[bench] dispatching {len(grid)} run(s), concurrency={args.concurrency}", flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(run_one, m, t) for m, t in grid]
        for f in cf.as_completed(futs):
            f.result()
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
