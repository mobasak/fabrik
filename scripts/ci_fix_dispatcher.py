#!/usr/bin/env python3
# AFTER-EDIT: tests/test_ci_fix_dispatcher.py, INDEX.md, CHANGELOG.md
"""CI-fix dispatcher — GitHub Actions failure -> local coder-AI fix run.

The loop this automates: a project's CI fails on GitHub -> the operator gets a
failure email -> the operator manually tells a coder AI to fix it. This script
closes that loop headlessly: it polls `gh run list` for recent failures across
every /opt/<project> with a GitHub remote, and for each NEW failure launches
`claude -p` IN THAT PROJECT's working tree with a brief to reproduce the
failure locally, fix it, pass the local gate, and push.

Design decisions (deliberate, keep):
  * POLL, not webhook — no public endpoint on the dev box; failures are not
    latency-critical; `gh` is already authed.
  * REPRODUCE LOCALLY, not parse CI logs — the GitHub logs API 404s on renamed
    repos, and every repo already lives under /opt with its own gate/tests.
    The worker runs the failing checks itself; CI logs are a hint, not a need.
  * Fix agents work IN their own repo (never cross-repo), commit with
    provenance trailers, and push only after the local gate/tests pass.

Guards (the reason this is safe to run unattended):
  * dedup      — a run id is dispatched once; state in ~/.local/state/ci-fix/.
  * attempt cap— max 2 fix attempts per workflow+repo (no fix->fail->fix loop).
  * dirty skip — a repo with uncommitted changes is SKIPPED (a sibling agent
                 is mid-work there; never collide with their tree).
  * quota cap  — max dispatches per invocation (default 2; Claude Max quota
                 is the binding constraint, not dollars).
  * age gate   — only failures newer than --max-age-hours (default 48).
  * branch gate— only failures on master/main (feature branches are WIP).

Usage:
  python3 scripts/ci_fix_dispatcher.py --dry-run     # report, dispatch nothing
  python3 scripts/ci_fix_dispatcher.py               # dispatch (cron mode)
Cron: 40 * * * *  (hourly; a missed hour just means the next one catches up)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

OPT = Path("/opt")
STATE_DIR = Path.home() / ".local/state/ci-fix"
STATE_FILE = STATE_DIR / "state.json"
LOG_DIR = STATE_DIR / "logs"
MAX_ATTEMPTS = 2
WORKER_TIMEOUT_S = 30 * 60  # one fix run may include tests + gate

# Repos never auto-fixed (hub governance changes need a human-directed session).
SKIP_REPOS = {"fabrik-dr-store"}


def sh(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    """Run a command, return (exit_code, stdout+stderr)."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, str(e)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"runs": {}, "attempts": {}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def discover_repos() -> dict[str, Path]:
    """Map github owner/name -> local /opt working tree."""
    repos: dict[str, Path] = {}
    for d in sorted(OPT.iterdir()):
        if not (d / ".git").is_dir():
            continue
        rc, out = sh(["git", "-C", str(d), "remote", "get-url", "origin"])
        if rc != 0 or "github.com" not in out:
            continue
        slug = out.strip().split("github.com")[-1].lstrip(":/").removesuffix(".git")
        if slug and d.name not in SKIP_REPOS:
            repos[slug] = d
    return repos


def local_branch(repo_dir: Path) -> str:
    """The branch the local tree tracks — active dev branches aren't always
    master (e.g. a sibling agent pushing a work branch); failures there are
    still ours to fix."""
    rc, out = sh(["git", "-C", str(repo_dir), "branch", "--show-current"])
    return out.strip() if rc == 0 else ""


def recent_failures(slug: str, max_age_hours: int, extra_branch: str = "") -> list[dict]:
    """Failed runs on eligible branches within the age window."""
    allowed = {"master", "main"} | ({extra_branch} if extra_branch else set())
    rc, out = sh(
        ["gh", "run", "list", "-R", slug, "--status", "failure", "--limit", "10",
         "--json", "databaseId,workflowName,headBranch,createdAt"],
        timeout=45,
    )
    if rc != 0:
        return []
    try:
        runs = json.loads(out)
    except json.JSONDecodeError:
        return []
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    picked = []
    for r in runs:
        if r.get("headBranch") not in allowed:
            continue
        try:
            created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if created < cutoff:
            continue
        # NEVER-STARTED runs are not fixable code (2026-08-15 incident): a billing refusal,
        # an invalid workflow or a dispatch-time cancellation produces conclusion=failure with
        # ZERO steps and no logs. Dispatching `claude -p` at those burns the exact resource
        # whose exhaustion caused them. The CI-health probe reports them instead.
        rc2, out2 = sh(["gh", "api", f"repos/{slug}/actions/runs/{r['databaseId']}/jobs",
                        "--jq", ".jobs[0].steps | length"], timeout=30)
        if rc2 == 0 and out2.strip() == "0":
            print(f"    [skip] {slug} run {r['databaseId']}: job never started "
                  "(billing/workflow refusal) — not a code failure")
            continue
        picked.append(r)
    return picked


def worktree_dirty(repo_dir: Path) -> bool:
    rc, out = sh(["git", "-C", str(repo_dir), "status", "--porcelain"])
    return rc != 0 or bool(out.strip())


def failed_steps(slug: str, run_id: int) -> str:
    """Best-effort failing job/step names — a hint for the worker, not a need."""
    rc, out = sh(
        ["gh", "run", "view", "-R", slug, str(run_id), "--json", "jobs", "-q",
         '.jobs[] | select(.conclusion=="failure") | .name + ": " + '
         '([.steps[] | select(.conclusion=="failure") | .name] | join(", "))'],
        timeout=45,
    )
    return out.strip() if rc == 0 else ""


def fix_brief(slug: str, run: dict, steps: str) -> str:
    hint = f"Failing job/step(s): {steps}." if steps else \
        "Failing step names unavailable — discover by reproducing locally."
    return (
        f"CI auto-fix task. GitHub Actions run {run['databaseId']} of workflow "
        f"'{run['workflowName']}' FAILED on {slug} (branch {run['headBranch']}, "
        f"created {run['createdAt']}). {hint}\n"
        "Do the following, autonomously, in THIS repository only:\n"
        "1. git fetch and fast-forward the local tree so you are diagnosing the "
        "commit CI actually ran (do NOT discard any local uncommitted work — if "
        "fast-forward is impossible, STOP and report).\n"
        "2. Reproduce the failure locally: read .github/workflows/ to see what "
        "the failing workflow runs, then run those same checks/tests here.\n"
        "3. Fix the root cause in the code/tests. Never delete or weaken a "
        "check to make it pass; never `noqa`/skip a failing test to go green.\n"
        "4. Verify: re-run the failing check until it passes, then run the "
        "repo's gate (python scripts/final_gate.py --json) to status success "
        "if the repo has one.\n"
        "5. Commit ONLY the files you changed (explicit paths, never -A) with "
        "trailers: Agent-Role: ci-fix and Agent-Context: <run id + what was "
        "fixed>. Then git fetch + fast-forward + push.\n"
        "6. If the failure is in CI config itself (e.g. a stale or misconfigured "
        "workflow), fixing the workflow file is in scope.\n"
        "If you cannot fix it within these rules, stop and print "
        "BLOCKED: <reason> — do not push anything."
    )


def dispatch(repo_dir: Path, brief: str, log_path: Path, dry_run: bool) -> int:
    if dry_run:
        print(f"    [dry-run] would dispatch claude -p in {repo_dir}")
        return 0
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as lf:
        lf.write(f"=== dispatched {datetime.now(UTC).isoformat()} ===\n")
        lf.flush()
        try:
            p = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "-p", brief],
                cwd=repo_dir, stdout=lf, stderr=subprocess.STDOUT,
                timeout=WORKER_TIMEOUT_S,
                # resume-mesh: mark the worker AUTONOMOUS so session_orient.py drops the
                # persistent sweep marker — a VM cut mid-fix gets revived at next boot
                # (plan 2026-08-13-plan-1 Leg A; extend os.environ, never replace it)
                env={**os.environ, "CLAUDE_MESH_AUTONOMOUS": "1"},
            )
            lf.write(f"\n=== worker exit={p.returncode} ===\n")
            return p.returncode
        except subprocess.TimeoutExpired:
            lf.write(f"\n=== worker TIMEOUT after {WORKER_TIMEOUT_S}s ===\n")
            return 124


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="report; dispatch nothing")
    ap.add_argument("--max-dispatches", type=int, default=2,
                    help="quota guard: max fix runs per invocation (default 2)")
    ap.add_argument("--max-age-hours", type=int, default=48,
                    help="ignore failures older than this (default 48)")
    args = ap.parse_args()

    rc, _ = sh(["gh", "auth", "status"], timeout=30)
    if rc != 0:
        print("FAIL: gh CLI not authenticated", file=sys.stderr)
        return 1

    state = load_state()
    repos = discover_repos()
    print(f"{len(repos)} repos with GitHub remotes under /opt")

    dispatched = 0
    for slug, repo_dir in repos.items():
        if dispatched >= args.max_dispatches:
            print(f"quota guard: {args.max_dispatches} dispatches reached — rest wait for next run")
            break
        failures = recent_failures(slug, args.max_age_hours, local_branch(repo_dir))
        if not failures:
            continue
        if worktree_dirty(repo_dir):
            # NOT recorded: retried next cycle when the sibling's work is committed.
            print(f"  {slug}: {len(failures)} failure(s) but worktree dirty (sibling agent working) — skipped this cycle")
            continue
        for run in failures:
            run_id = str(run["databaseId"])
            attempt_key = f"{slug}:{run['workflowName']}"
            if run_id in state["runs"]:
                continue  # dedup: already handled
            if state["attempts"].get(attempt_key, 0) >= MAX_ATTEMPTS:
                print(f"  {slug}: attempt cap for '{run['workflowName']}' — needs a human")
                state["runs"][run_id] = {"outcome": "capped", "ts": time.time()}
                continue
            steps = failed_steps(slug, run["databaseId"])
            print(f"  {slug}: run {run_id} '{run['workflowName']}' -> dispatching fix agent")
            log_path = LOG_DIR / f"{repo_dir.name}-{run_id}.log"
            code = dispatch(repo_dir, fix_brief(slug, run, steps), log_path, args.dry_run)
            if not args.dry_run:
                state["runs"][run_id] = {
                    "repo": slug, "workflow": run["workflowName"],
                    "outcome": f"worker-exit-{code}", "ts": time.time(),
                    "log": str(log_path),
                }
                state["attempts"][attempt_key] = state["attempts"].get(attempt_key, 0) + 1
                save_state(state)
            dispatched += 1
            if dispatched >= args.max_dispatches:
                break

    if not args.dry_run:
        save_state(state)
    print(f"done: {dispatched} dispatched" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
