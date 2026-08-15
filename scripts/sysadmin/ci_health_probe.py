#!/usr/bin/env python3
# AFTER-EDIT: scripts/ci_fix_dispatcher.py (shares the never-started classification), docs/workstation/ci-health-probe.md
"""Fleet CI-health probe — catch CI that NEVER RAN, and the quota curve that kills it.

Spec: docs/superpowers/specs/2026-08-15-ci-health-probe-design.md

The incident that produced it (2026-08-15): GitHub refused to start Actions jobs on every
PRIVATE repo (Free-plan allowance crossed in July, $0 spending limit → refusal instead of
billing). Jobs "failed" in 1 second with ZERO steps and no logs. Every local gate stayed green
because `final_gate` runs ruff/pytest on the box, and `ci_fix_dispatcher` would have dispatched
`claude -p` workers to fix code that was never broken. The operator found it by noticing red
checks repo by repo.

Two legs, deliberately:
  * REACTIVE  — a run whose job has ZERO steps did not run at all (billing refusal, workflow
                syntax error, cancellation). Classified, never confused with a test failure.
  * PREDICTIVE— current-month Actions minutes vs the plan's included allowance. This is the
                half that would have PREVENTED the outage: the curve was 529 → 1478 → 2074 →
                2409 over four months, public in the billing API, and unwatched.

Costs nothing: API reads only (no Actions minutes), ≤2 gh calls per repo + 1 account call.
Always exits 0 — a cron-hosted probe must never look like a broken cron.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

OPT = Path(os.environ.get("CI_PROBE_OPT_ROOT", "/opt"))
STATE_DIR = Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")
SOUND = Path.home() / ".claude" / "bin" / "claude-sound.sh"
SUPPRESS_S = float(os.environ.get("CI_PROBE_SUPPRESS_S", 24 * 3600))
WARN_PCT = float(os.environ.get("CI_PROBE_WARN_PCT", 80))

# Included Actions minutes per month for PRIVATE repos, by plan (docs.github.com, fetched
# 2026-08-15). Public repos are unmetered; self-hosted runners are free.
PLAN_MINUTES = {"free": 2000, "pro": 3000, "team": 3000}


def sh(cmd: list[str], timeout: int = 45) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def classify_run(job: dict) -> str:
    """`never-started` | `test-failure` | `ok`.

    A job that failed with ZERO steps never reached a runner — the signature of a billing
    refusal, an invalid workflow, or a cancellation at dispatch. Calling that a test failure is
    what makes an auto-fixer burn quota on code that was never the problem.
    """
    if (job.get("conclusion") or "") != "failure":
        return "ok"
    return "never-started" if not (job.get("steps") or []) else "test-failure"


def repo_slug(repo_dir: Path) -> str | None:
    rc, out = sh(["git", "-C", str(repo_dir), "remote", "get-url", "origin"], timeout=15)
    if rc != 0 or "github.com" not in out:
        return None
    tail = out.strip().split("github.com")[-1].lstrip(":/")
    return tail[:-4] if tail.endswith(".git") else tail


def probe_repo(slug: str) -> dict | None:
    """The newest run's health for one repo, or None when there is nothing to say."""
    rc, out = sh(["gh", "run", "list", "-R", slug, "--limit", "1",
                  "--json", "databaseId,conclusion,workflowName,createdAt"])
    if rc != 0:
        return None
    try:
        runs = json.loads(out)
    except ValueError:
        return None
    if not runs or (runs[0].get("conclusion") or "") != "failure":
        return None
    run = runs[0]
    rc, out = sh(["gh", "api", f"repos/{slug}/actions/runs/{run['databaseId']}/jobs",
                  "--jq", ".jobs[0]"])
    if rc != 0:
        return None
    try:
        job = json.loads(out) if out.strip() else {}
    except ValueError:
        return None
    verdict = classify_run(job)
    if verdict != "never-started":
        return None
    return {"repo": slug, "run_id": run["databaseId"], "workflow": run.get("workflowName"),
            "verdict": verdict, "created": run.get("createdAt", "?"),
            "reason": annotation_reason(slug, job)}


def annotation_reason(slug: str, job: dict) -> str:
    """GitHub's own words for WHY, when cheap to get — never our guess."""
    cid = job.get("check_run_url", "").rstrip("/").split("/")[-1]
    if not cid.isdigit():
        return "job never started (no steps executed)"
    rc, out = sh(["gh", "api", f"repos/{slug}/check-runs/{cid}/annotations",
                  "--jq", ".[0].message // empty"], timeout=25)
    msg = out.strip()
    return msg[:200] if rc == 0 and msg else "job never started (no steps executed)"


def _repo_is_private(owner: str, repo: str) -> bool | None:
    """True/False from the live API; None when unknowable (counted, fail-loud)."""
    rc, out = sh(["gh", "api", f"repos/{owner}/{repo}", "--jq", ".private"], timeout=20)
    s = out.strip().lower()
    return True if (rc == 0 and s == "true") else False if (rc == 0 and s == "false") else None


def actions_quota() -> dict | None:
    """Current-month METERED Actions minutes vs the plan's included allowance.

    Only PRIVATE repos consume the allowance — public-repo minutes appear in usageItems with
    quantity but are fully discounted (net $0, unmetered). Summing raw quantity produced the
    2026-08-15 false alarm: fabrik (public) alone read as 82% of the Pro allowance while real
    metered usage was ~0. Unknown visibility counts (fail-loud beats a silent wall).

    A non-200 (the per-user billing endpoint already moved once — the old path 410s) must read
    as UNKNOWN, never as zero: a fail-open zero would silence the alert exactly when the API
    changes again.
    """
    rc, out = sh(["gh", "api", "/user", "--jq", ".login + \" \" + .plan.name"], timeout=25)
    if rc != 0 or not out.strip():
        return None
    login, _, plan = out.strip().partition(" ")
    rc, out = sh(["gh", "api", f"/users/{login}/settings/billing/usage"], timeout=30)
    if rc != 0:
        return None
    try:
        items = json.loads(out).get("usageItems", [])
    except ValueError:
        return None
    month = datetime.now(UTC).strftime("%Y-%m")
    rows = [i for i in items
            if i.get("sku") == "Actions Linux" and str(i.get("date", "")).startswith(month)]
    visibility: dict[str, bool | None] = {}
    used = 0.0
    for i in rows:
        repo = i.get("repositoryName")
        if repo:
            if repo not in visibility:
                visibility[repo] = _repo_is_private(login, repo)
            if visibility[repo] is False:
                continue  # public = unmetered
        used += i.get("quantity", 0)
    included = PLAN_MINUTES.get(plan.lower(), 2000)
    return {"plan": plan, "used": round(used), "included": included,
            "pct": (used / included * 100) if included else 0.0}


def notify(title: str, body: str) -> None:
    if not SOUND.is_file():
        print(f"[no notifier] {title}: {body}")
        return
    subprocess.run(["bash", str(SOUND), "mesh-notify", "ci-health", "/opt/fabrik",
                    f"{title} — {body}"], stdin=subprocess.DEVNULL,
                   capture_output=True, check=False)


def suppressed(key: str) -> bool:
    stamp = STATE_DIR / f"ci-probe-{key}.stamp"
    try:
        if (time.time() - stamp.stat().st_mtime) < SUPPRESS_S:
            return True
    except OSError:
        pass
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp.touch()
    except OSError:
        pass
    return False


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in args
    blocked: list[dict] = []
    try:
        repos = sorted(d for d in OPT.iterdir() if (d / ".git").is_dir())
    except OSError:
        repos = []
    for d in repos:
        slug = repo_slug(d)
        if not slug:
            continue
        hit = probe_repo(slug)
        if hit:
            blocked.append(hit)
            # the timestamp is load-bearing: after a billing fix the NEWEST run can still be
            # a pre-fix failure, so "blocked" without an age misleads. Age lets the operator
            # tell a live block from a stale one (re-run to confirm).
            print(f"NEVER-STARTED {hit['repo']} (run {hit['created']}): {hit['reason'][:90]}")
    # ONE alert for the whole event — a fleet-wide stop is one message naming every repo,
    # not one discovery per repo (which is how the 2026-08-15 outage was actually found).
    if blocked and not suppressed("blocked"):
        names = ", ".join(f"{h['repo'].split('/')[-1]} ({h['created'][:10]})" for h in blocked)
        notify("CI NOT RUNNING", f"{len(blocked)} repo(s) — {names}. {blocked[0]['reason'][:120]}")
    quota = actions_quota()
    if quota is None:
        print("quota: UNKNOWN (billing API unreachable — not treated as 0)")
    else:
        print(f"quota: {quota['used']}/{quota['included']} min ({quota['pct']:.0f}%) "
              f"plan={quota['plan']}")
        if quota["pct"] >= 100 and not suppressed("quota-over"):
            notify("ACTIONS QUOTA EXCEEDED",
                   f"{quota['used']}/{quota['included']} min on {quota['plan']} — jobs will be "
                   "refused until the spending limit or plan is raised")
        elif quota["pct"] >= WARN_PCT and not suppressed("quota-warn"):
            notify("ACTIONS QUOTA WARNING",
                   f"{quota['used']}/{quota['included']} min ({quota['pct']:.0f}%) on "
                   f"{quota['plan']} — CI stops when it hits 100%")
    if not blocked and not quiet:
        print("ci-health: every repo's newest run executed (or passed)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — cron-hosted: never a traceback, never a false red
        print(f"ci-health: INTERNAL ERROR {type(e).__name__}: {e}")
        sys.exit(0)
