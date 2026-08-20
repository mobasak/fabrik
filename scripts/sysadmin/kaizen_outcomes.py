#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_outcomes.py | none
"""Kaizen M1 outcome tier — rework miner, fleet-health sweep, premature-stop reader.

The spec's outcome tier is "the numbers ceremony cannot move"
(docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:139-148): three
metrics computed from ground truth no governance prose can shift —

- **rework_rate** — commits whose files are re-touched within ``KAIZEN_REWORK_DAYS``
  (default 7) by a LATER fix-shaped commit (``fix(`` / ``revert`` / ``hotfix`` subject),
  mined from ``git log`` (READ-ONLY subprocess git, never a mutation) across every
  ``/opt/*`` git repo. The denominator is always printed with the rate; a repo whose
  mined window carries no provenance trailers reports ``—`` with that reason (its
  history cannot be attributed to agents, so a rate would be a lie about the loop).
- **fleet_health** (``--sweep``) — for each CONFIGURED pilot project
  (``KAIZEN_SWEEP_PROJECTS``, comma list, DEFAULT ``fabrik`` — the set is config,
  never heuristic discovery), create a CLEAN worktree from HEAD in a temp dir (a
  ``git clone --shared`` — the live tree is never executed in and never written; a
  dirty live tree is irrelevant because HEAD is what ships) and run INSTALL-LESS
  checks only: ``compileall``, pytest via the project's OWN existing ``.venv`` (see
  the deviation note below), ``final_gate.py --check`` where synced — all under a
  per-project ``KAIZEN_SWEEP_TIMEOUT_S`` (default 300) budget. Timeout / no venv /
  no tests / node project → honest ``—`` with the reason. Each project emits one
  ``fleet_health`` event via kaizen_events. The report says ``swept n/N — the rest —``.
- **premature_stop** — the Stop-hook oracle finally read, SESSION-level: the share of
  stop-verdict-carrying sessions with a premature-cause ``stop_block`` (T06's
  ``PREMATURE_CAUSES``, imported), served from T06's derived-facts rows
  (``kaizen_collect_v2.read_rows``); cf. T06's event-level ``premature_stop_rate``.

All three register in T06's paired-counter registry (a schema constraint — an
unpaired metric refuses to load): rework_rate ⟂ review_rounds, fleet_health ⟂
sweep_coverage, premature_stop ⟂ stop_block_causes.

POPULATION NOTE — the store-reading metrics (``premature_stop``,
``stop_block_causes``, ``review_rounds``) compute over EVENT-era rows only
(``kc._event_era``): T08's transcript-era backfill rows carry ``—`` in every
event-only field and are excluded, not coerced. The registered formula strings
predate this narrowing and stay verbatim (a formula edit is a def-hash version
bump); this note is the in-band record.

THE HONESTY RULE (inherited, binding)
-------------------------------------
An unmeasurable metric renders ``—`` with its reason — never a fabricated 0. A
missing events store, an unreadable repo, a git failure, a timed-out check: all
fail OPEN into a dashed cell, never a crash.

DEVIATION NOTE (pytest runner)
------------------------------
The ticket sketch says ``uv run pytest`` when ``.venv`` exists — but ``uv run``
inside the clean CLONE (which has no venv, ever) would create and sync an
environment, i.e. install. The install-less mandate is the binding rule, so the
sweep runs the LIVE project's existing ``.venv/bin/python -m pytest`` with the
clone as cwd: same interpreter + deps, zero installs, live tree untouched.

NIGHTLY CRON ENTRY (a job key in weekly_catchup.sh's table since T09; the crontab LINE
itself rides the operator's crontab install — this module never writes a crontab)
-----------------------------------------------------------------------------------------
The sweep is a job key in scripts/sysadmin/weekly_catchup.sh (T09 cutover): the runner owns
the wake-proof stamp-check — hourly cron tick, fires only when the daily success stamp is
>= ~1 day old (86400 - 1800 s slack), stamp touched ONLY on success so a failing sweep
retries hourly with every attempt in the log. The crontab line:

41 * * * * flock -n $HOME/.claude/state/daily-kaizen-sweep.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh kaizen_outcomes.py >> $HOME/.claude/kaizen-sweep.log 2>&1

Config via env: ``KAIZEN_REWORK_DAYS`` (7), ``KAIZEN_SWEEP_PROJECTS`` (``fabrik``),
``KAIZEN_SWEEP_TIMEOUT_S`` (300), plus T06's ``KAIZEN_STATE_DIR`` / T01's
``KAIZEN_EVENTS_DIR`` through the modules that own them. Box-local, stdlib only.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import kaizen_collect_v2 as kc  # noqa: E402 - same directory (T06's registry + read_rows)
from kaizen_collect_v2 import DASH, MetricResult  # noqa: E402 - the shared result shape

try:
    # T06's cause vocabulary — guarded: an older collector (a box mid-sync) must cost
    # ONLY the stops pair its measurement, never the rework/sweep tiers or the module.
    from kaizen_collect_v2 import PREMATURE_CAUSES  # noqa: E402
except ImportError:  # pragma: no cover - simulated in tests via monkeypatch
    PREMATURE_CAUSES = None  # type: ignore[assignment]

try:
    import kaizen_events  # T01 emitter — same directory; fleet_health events
except Exception:  # pragma: no cover - a box mid-sync
    kaizen_events = None  # type: ignore[assignment]

OPT_ROOT = Path("/opt")
#: Mined lookback = 4 windows: enough later history that every denominator commit's
#: observation window is complete, without walking whole repo histories nightly.
LOOKBACK_WINDOWS = 4
GIT_TIMEOUT_S = 60.0

# Anchored AND word-bounded: the SUBJECT is fix-shaped, not any subject that mentions
# or merely starts with the word — "docs: describe the hotfix procedure" is prose,
# "hotfixture:" is another word. Accepted under-count: "hotfixed ..." no longer counts
# — the honest direction (a missed rework, never a fabricated one).
_FIX_RE = re.compile(r"^\s*(?:fix\(|revert\b|hotfix\b)", re.I)


def _warn(msg: str) -> None:
    """stderr only — reports go to stdout, event files belong to kaizen_events."""
    try:
        print(f"kaizen_outcomes: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover - stderr itself is gone
        pass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        val = int(raw)
        return val if val > 0 else default
    except ValueError:
        if raw:
            _warn(f"unparseable {name}={raw!r} — using default {default}")
        return default


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.0f}% ({num}/{den})"


# ── rework_rate — read-only git mining across /opt/* repos ────────────────────────────


@dataclasses.dataclass
class RepoRework:
    """One repo's rework verdict. ``cell`` is ``—`` (with ``reason``) when unmeasured."""

    repo: str
    cell: str
    reason: str = ""
    numerator: int | None = None
    denominator: int | None = None
    measurable: bool = False


@dataclasses.dataclass
class _Commit:
    sha: str
    ts: int
    subject: str
    #: Every path the commit involved (renames contribute BOTH sides) — the broad set
    #: a candidate commit is matched BY.
    files: frozenset[str]
    #: Paths the commit actually MODIFIED (rename-status R* pairs excluded) — the set
    #: used when this commit is the later FIX: a pure rename reworks nothing.
    fix_files: frozenset[str]


def _fix_shaped(subject: str) -> bool:
    return bool(_FIX_RE.search(subject))


def _git_out(repo: Path, args: list[str], timeout: float = GIT_TIMEOUT_S) -> str | None:
    """One READ-ONLY git probe. ``None`` means "not measurable", never a guess."""
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, read-only subcommand
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return proc.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _mine_commits(repo: Path, lookback_days: int) -> list[_Commit] | None:
    # --name-status with explicit -M: rename detection is pinned ON (not left to the
    # host's diff.renames config) so an R* pair is deterministically visible and can be
    # excluded from the fix-side intersection — a pure rename is not rework.
    out = _git_out(
        repo,
        [
            "log",
            "--no-merges",
            "-M",
            f"--since={lookback_days} days ago",
            "--format=%x1e%H%x1f%ct%x1f%s",
            "--name-status",
        ],
    )
    if out is None:
        return None
    commits: list[_Commit] = []
    for record in out.split("\x1e"):
        if not record.strip():
            continue
        lines = record.splitlines()
        head = lines[0].split("\x1f")
        if len(head) != 3:
            continue  # a malformed record is skipped, never guessed at
        sha, raw_ts, subject = head
        try:
            ts = int(raw_ts)
        except ValueError:
            continue
        files: set[str] = set()
        fix_files: set[str] = set()
        for ln in lines[1:]:
            parts = ln.rstrip("\n").split("\t")
            if len(parts) < 2 or not parts[0].strip():
                continue
            status = parts[0].strip()
            if status.startswith(("R", "C")) and len(parts) >= 3:
                files.update((parts[1], parts[2]))  # both sides are matchable...
                continue  # ...but a rename/copy pair modifies nothing — never fix-side
            files.add(parts[1])
            fix_files.add(parts[1])
        commits.append(
            _Commit(
                sha=sha,
                ts=ts,
                subject=subject,
                files=frozenset(files),
                fix_files=frozenset(fix_files),
            )
        )
    return commits


def _has_trailers(repo: Path, lookback_days: int) -> bool | None:
    out = _git_out(
        repo,
        [
            "log",
            f"--since={lookback_days} days ago",
            "--format=%(trailers:key=Agent-Role,valueonly)",
        ],
    )
    if out is None:
        return None
    return any(ln.strip() for ln in out.splitlines())


def mine_repo(repo: Path, days: int, now: float | None = None) -> RepoRework:
    """One repo's rework rate over the mined window. Read-only; fails open to ``—``."""
    now_s = time.time() if now is None else now
    lookback = days * LOOKBACK_WINDOWS
    commits = _mine_commits(repo, lookback)
    if commits is None:
        return RepoRework(repo.name, DASH, reason="git unreadable (log failed)")
    if not commits:
        return RepoRework(repo.name, DASH, reason=f"no commits in the {lookback}d mined window")
    trailers = _has_trailers(repo, lookback)
    if trailers is None:
        return RepoRework(repo.name, DASH, reason="git unreadable (trailer probe failed)")
    if not trailers:
        return RepoRework(
            repo.name,
            DASH,
            reason=(
                "no Agent-Role trailers parsed in the mined window "
                "(present-but-malformed trailer blocks count as unparsed)"
            ),
        )
    window_s = days * 86400
    denom = [c for c in commits if c.ts + window_s <= now_s]
    if not denom:
        return RepoRework(repo.name, DASH, reason=f"no commits with a complete {days}d window")
    reworked = sum(
        1
        for c in denom
        if any(
            d.ts > c.ts
            and d.ts - c.ts <= window_s
            and _fix_shaped(d.subject)
            and (c.files & d.fix_files)
            for d in commits
        )
    )
    return RepoRework(
        repo.name,
        _pct(reworked, len(denom)),
        numerator=reworked,
        denominator=len(denom),
        measurable=True,
    )


def rework_rate(
    root: Path = OPT_ROOT, days: int | None = None, now: float | None = None
) -> tuple[MetricResult, list[RepoRework]]:
    """Rework across every git repo under ``root``. Denominator always printed."""
    days = days if days is not None else _env_int("KAIZEN_REWORK_DAYS", 7)
    try:
        repos = sorted(
            (p for p in root.iterdir() if p.is_dir() and (p / ".git").exists()),
            key=lambda p: p.name,
        )
    except OSError as exc:
        return (
            MetricResult.unavailable("rework_rate", f"repo root {root} unreadable: {exc!r}"),
            [],
        )
    if not repos:
        return MetricResult.unavailable("rework_rate", f"no git repos under {root}"), []
    per = [mine_repo(repo, days, now) for repo in repos]
    measured = [r for r in per if r.measurable]
    if not measured:
        return (
            MetricResult.unavailable(
                "rework_rate", f"0/{len(per)} repo(s) measurable — see per-repo reasons"
            ),
            per,
        )
    num = sum(r.numerator or 0 for r in measured)
    den = sum(r.denominator or 0 for r in measured)
    overall = MetricResult(
        id="rework_rate",
        cell=_pct(num, den),
        detail=(
            f"commits re-touched by a fix-shaped commit within {days}d; "
            f"{len(measured)}/{len(per)} repo(s) measured"
        ),
        value=num / den if den else None,
        numerator=num,
        denominator=den,
    )
    return overall, per


# ── fleet_health sweep — clean temp worktrees, install-less checks ────────────────────


@dataclasses.dataclass
class SweepResult:
    """One project's sweep verdict. ``swept`` = every attempted check COMPLETED."""

    project: str
    cell: str
    reason: str = ""
    swept: bool = False
    checks: dict[str, str] = dataclasses.field(default_factory=dict)
    duration_s: float = 0.0


@dataclasses.dataclass
class SweepReport:
    results: list[SweepResult]
    health: MetricResult
    coverage: MetricResult
    lines: list[str]


def sweep_project_names(only: list[str] | None = None) -> list[str]:
    """The CONFIGURED pilot set — env list only, never heuristic discovery.

    ``only`` distinguishes None (no override — read the env) from ``[]`` (an explicit
    empty override — sweep NOTHING); an empty list must never fall through to the env.
    """
    if only is not None:
        return [p.strip() for p in only if p.strip()]
    raw = os.getenv("KAIZEN_SWEEP_PROJECTS", "") or "fabrik"
    return [p.strip() for p in raw.split(",") if p.strip()]


def _node_test_project(src: Path) -> bool:
    pkg = src / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
        scripts = data.get("scripts") if isinstance(data, dict) else None
        return bool(isinstance(scripts, dict) and scripts.get("test"))
    except (OSError, ValueError):
        return False


#: _run_check's non-rc outcomes — flow into check cells and project reasons verbatim.
CHECK_TIMEOUT = "timeout"
CHECK_UNREAPABLE = "timeout (unreapable)"
#: Bound on the post-SIGKILL reap: a D-state child must cost seconds, not the budget.
REAP_TIMEOUT_S = 5.0


def _run_check(cmd: list[str], timeout: float, cwd: Path | None = None) -> int | str:
    """Run one install-less check in its OWN process group. Returns the rc, or a
    timeout marker string on budget overrun — in which case the WHOLE group
    (pytest/final_gate grandchildren included) is SIGKILLed before returning, so
    nothing outlives the budget or the temp worktree it was running in (the kill
    happens before the TemporaryDirectory cleanup). The post-kill reap is itself
    BOUNDED (``REAP_TIMEOUT_S``): a D-state child that survives SIGKILL yields
    ``CHECK_UNREAPABLE`` and the sweep moves on — fail open, never a hang."""
    try:
        proc = subprocess.Popen(  # noqa: S603 - fixed argv assembled from vetted paths
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,  # new session => pgid == pid, killpg reaches the tree
        )
    except OSError as exc:
        _warn(f"check {cmd[0]} failed to start ({exc!r}) — counted as a failure")
        return 127
    try:
        return proc.wait(timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass  # the group died between the timeout and the kill — already gone
        try:
            proc.wait(timeout=REAP_TIMEOUT_S)  # reap the direct child, BOUNDED
        except subprocess.TimeoutExpired:
            _warn(f"check {cmd[0]}: child unreapable after SIGKILL — giving up, fail open")
            return CHECK_UNREAPABLE
        return CHECK_TIMEOUT


def sweep_one(name: str, root: Path, timeout_s: int) -> SweepResult:
    """Sweep ONE project in a clean temp worktree from HEAD — NEVER the live tree.

    The worktree is a ``git clone --shared`` into a temp dir: a pure READ of the live
    repo (objects borrowed, nothing in the source mutated or executed). If the clean
    worktree cannot be created the project is ``—`` — there is no live-tree fallback.
    """
    t0 = time.monotonic()
    deadline = t0 + timeout_s

    def finish(res: SweepResult) -> SweepResult:
        res.duration_s = round(time.monotonic() - t0, 1)
        if kaizen_events is None:
            _warn("kaizen_events unavailable — fleet_health event not emitted")
        else:
            kaizen_events.emit(
                "fleet_health",
                project=res.project,
                swept=res.swept,
                cell=res.cell,
                reason=res.reason,
                checks=res.checks,
                duration_s=res.duration_s,
            )
        return res

    src = root / name
    if not src.is_dir():
        return finish(SweepResult(name, DASH, reason=f"missing project dir {src}"))
    if not (src / ".git").exists():
        return finish(SweepResult(name, DASH, reason="not a git repo"))
    if _node_test_project(src):
        return finish(SweepResult(name, DASH, reason="node project — pilot skips node runtimes"))

    checks: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix=f"kaizen-sweep-{name}-") as tmp:
        clone = Path(tmp) / name
        rc = _run_check(
            ["git", "clone", "--quiet", "--shared", str(src), str(clone)],
            deadline - time.monotonic(),
        )
        if isinstance(rc, str):
            return finish(
                SweepResult(name, DASH, reason=f"{rc} (worktree creation)", checks=checks)
            )
        if rc != 0:
            return finish(
                SweepResult(name, DASH, reason="clean worktree creation failed", checks=checks)
            )

        # compileall — install-less, runs everywhere.
        rc = _run_check(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "-x",
                r"(\.venv|node_modules|\.git)",
                str(clone),
            ],
            deadline - time.monotonic(),
        )
        if isinstance(rc, str):
            checks["compile"] = f"{DASH} ({rc})"
            return finish(SweepResult(name, DASH, reason=f"{rc} (compile)", checks=checks))
        checks["compile"] = "pass" if rc == 0 else f"fail (rc={rc})"

        # pytest — only via the project's OWN existing venv (install-less; see module
        # docstring deviation note), against the CLONE.
        venv_py = src / ".venv" / "bin" / "python"
        has_cfg = (clone / "pyproject.toml").is_file() or (clone / "pytest.ini").is_file()
        if not has_cfg:
            checks["pytest"] = f"{DASH} (no tests config)"
        elif not venv_py.is_file():
            checks["pytest"] = f"{DASH} (no venv)"
        else:
            rc = _run_check(
                [str(venv_py), "-m", "pytest", "-q"], deadline - time.monotonic(), cwd=clone
            )
            if isinstance(rc, str):
                checks["pytest"] = f"{DASH} ({rc})"
                return finish(SweepResult(name, DASH, reason=f"{rc} (pytest)", checks=checks))
            checks["pytest"] = "pass" if rc == 0 else f"fail (rc={rc})"

        # final_gate --check — read-only, where synced.
        gate = clone / "scripts" / "final_gate.py"
        if not gate.is_file():
            checks["final_gate"] = f"{DASH} (not synced)"
        else:
            gate_py = str(venv_py) if venv_py.is_file() else sys.executable
            rc = _run_check(
                [gate_py, "scripts/final_gate.py", "--check", "--json"],
                deadline - time.monotonic(),
                cwd=clone,
            )
            if isinstance(rc, str):
                checks["final_gate"] = f"{DASH} ({rc})"
                return finish(SweepResult(name, DASH, reason=f"{rc} (final_gate)", checks=checks))
            checks["final_gate"] = "pass" if rc == 0 else f"fail (rc={rc})"

    failing = sorted(k for k, v in checks.items() if v.startswith("fail"))
    executed = [k for k, v in checks.items() if not v.startswith(DASH)]
    if not executed:
        return finish(SweepResult(name, DASH, reason="no runnable checks", checks=checks))
    cell = "ok" if not failing else f"red ({', '.join(failing)})"
    return finish(SweepResult(name, cell, swept=True, checks=checks))


def run_sweep(
    root: Path = OPT_ROOT, only: list[str] | None = None, timeout_s: int | None = None
) -> SweepReport:
    """Sweep the configured pilot set; report ``swept n/N — the rest —``."""
    budget = timeout_s if timeout_s is not None else _env_int("KAIZEN_SWEEP_TIMEOUT_S", 300)
    names = sweep_project_names(only)
    results = [sweep_one(name, root, budget) for name in names]
    swept = [r for r in results if r.swept]
    unswept = [r for r in results if not r.swept]

    lines = [f"{r.project}: {r.cell}" + (f" — {r.reason}" if r.reason else "") for r in results]
    summary = f"swept {len(swept)}/{len(names)}"
    if unswept:
        detail = "; ".join(f"{r.project}: {r.reason or DASH}" for r in unswept)
        summary += f" — the rest {DASH} ({detail})"
    lines.append(summary)

    coverage = MetricResult(
        id="sweep_coverage",
        cell=_pct(len(swept), len(names)) if names else DASH,
        detail="projects fully swept over the configured pilot set",
        value=(len(swept) / len(names)) if names else None,
        numerator=len(swept),
        denominator=len(names) or None,
        measurable=bool(names),
    )
    if swept:
        green = sum(1 for r in swept if r.cell == "ok")
        health = MetricResult(
            id="fleet_health",
            cell=_pct(green, len(swept)),
            detail="swept projects with every executed check green",
            value=green / len(swept),
            numerator=green,
            denominator=len(swept),
        )
    else:
        health = MetricResult.unavailable("fleet_health", "nothing swept — see per-project reasons")
    return SweepReport(results=results, health=health, coverage=coverage, lines=lines)


# ── premature_stop + the counter pairs read from T06's rows ──────────────────────────


def _stop_verdicts(row: dict) -> int:
    events = row.get("events") or {}
    return int(events.get("stop_pass", 0)) + int(events.get("stop_block", 0))


def premature_stop(state: Path | None = None) -> tuple[MetricResult, MetricResult]:
    """(premature_stop, stop_block_causes) from derived-facts rows — T02's oracle read.

    SESSION-level by design: the share of stop-verdict-carrying sessions that hit a
    stop_block whose cause is premature (:data:`PREMATURE_CAUSES` — T06's set,
    imported, never copied). T06's ``premature_stop_rate`` beside it in the registry
    is EVENT-level (share of stop VERDICTS premature); the two formulas cross-reference
    each other. A stop_block with a non-premature cause (a gate-red or uncommitted-work
    hold) is a legitimate hold, not a premature stop — it stays out of the numerator
    and in the ``stop_block_causes`` histogram.

    Fail-open, PAIRED: a missing/empty events store — or zero stop verdicts — yields
    two honest ``—`` results with ONE shared reason. A paired counter must never
    fabricate "clean" while its metric is unmeasurable.
    """
    vocab: frozenset[str] | None = PREMATURE_CAUSES
    if vocab is None:
        reason = "premature-cause vocabulary unavailable (kaizen_collect_v2 import failed)"
        return (
            MetricResult.unavailable("premature_stop", reason),
            MetricResult.unavailable("stop_block_causes", reason),
        )
    # Event-era only (T09 era filter): T08's transcript-era rows carry DASH strings
    # in events/stop_causes — unfiltered they crash _stop_verdicts, and their lines
    # are prose, not stop verdicts.
    rows = [r for r in kc.read_rows(state=state) if kc._event_era(r)]
    if not rows:
        reason = "no derived-facts rows (events store empty or missing)"
        return (
            MetricResult.unavailable("premature_stop", reason),
            MetricResult.unavailable("stop_block_causes", reason),
        )
    verdict_rows = [r for r in rows if _stop_verdicts(r) > 0]
    if not verdict_rows:
        reason = "no stop verdicts in the rows"
        return (
            MetricResult.unavailable("premature_stop", reason),
            MetricResult.unavailable("stop_block_causes", reason),
        )
    total_stops = sum(_stop_verdicts(r) for r in verdict_rows)
    causes: collections.Counter[str] = collections.Counter()
    for r in verdict_rows:
        for cause, count in (r.get("stop_causes") or {}).items():
            causes[str(cause)] += int(count)
    # ONE unit throughout — EVENTS: the numerator (caused stop_block events), the
    # denominator (stop-verdict events) and the cell text all count the same thing.
    if causes:
        causes_cell = ", ".join(f"{c}={n}" for c, n in causes.most_common())
    else:
        causes_cell = f"clean (0 stop_block events over {total_stops} stop verdicts)"
    causes_metric = MetricResult(
        id="stop_block_causes",
        cell=causes_cell,
        detail=(
            "full stop_block cause histogram in EVENT units — premature and legitimate causes alike"
        ),
        value=dict(causes),
        numerator=sum(causes.values()),
        denominator=total_stops,
    )
    premature_sessions = sum(
        1
        for r in verdict_rows
        if any(
            int(count) > 0 and cause in vocab
            for cause, count in (r.get("stop_causes") or {}).items()
        )
    )
    prem = MetricResult(
        id="premature_stop",
        cell=_pct(premature_sessions, len(verdict_rows)),
        detail=(
            "sessions with a premature-cause stop_block over sessions with any stop "
            "verdict; cf. premature_stop_rate (T06) = share of stop VERDICTS premature"
        ),
        value=premature_sessions / len(verdict_rows),
        numerator=premature_sessions,
        denominator=len(verdict_rows),
    )
    return prem, causes_metric


def review_rounds(state: Path | None = None) -> MetricResult:
    """Mean max-round per round-carrying session (rework_rate's counter pair)."""
    # Event-era only — transcript rows' `runs` is a DASH string (see premature_stop).
    rows = [r for r in kc.read_rows(state=state) if kc._event_era(r)]
    vals = [
        int((r.get("runs") or {}).get("rounds_max", 0))
        for r in rows
        if int((r.get("runs") or {}).get("rounds_max", 0)) > 0
    ]
    if not vals:
        return MetricResult.unavailable("review_rounds", "no session carries a round event")
    return MetricResult(
        id="review_rounds",
        cell=f"{sum(vals) / len(vals):.1f} (n={len(vals)})",
        detail="mean rounds_max across round-carrying sessions",
        value=sum(vals) / len(vals),
        numerator=sum(vals),
        denominator=len(vals),
    )


# ── registry — the three pairs join T06's set (unpaired definitions refuse) ──────────

OUTCOME_METRIC_DEFS: tuple[dict, ...] = (
    {
        "id": "rework_rate",
        "version": 1,
        "counter_metric": "review_rounds",
        "formula": (
            "commits whose files are re-touched within KAIZEN_REWORK_DAYS by a later "
            "fix-shaped commit (subject anchored + word-bounded: fix(/revert/hotfix; "
            "'hotfixed'/'hotfixture' deliberately not counted — the honest under-count "
            "direction), mined read-only from git log across /opt/* repos; denominator "
            "= commits with a complete window; repos without provenance trailers "
            "report — with the reason."
        ),
    },
    {
        "id": "review_rounds",
        "version": 1,
        "counter_metric": "rework_rate",
        "formula": (
            "mean rounds_max across round-carrying sessions (derived-facts rows) — "
            "rounds down must never buy rework up."
        ),
    },
    {
        "id": "fleet_health",
        "version": 1,
        "counter_metric": "sweep_coverage",
        "formula": (
            "swept projects whose install-less checks (compileall / venv pytest / "
            "final_gate --check) are all green, over projects fully swept in clean "
            "HEAD worktrees."
        ),
    },
    {
        "id": "sweep_coverage",
        "version": 1,
        "counter_metric": "fleet_health",
        "formula": (
            "projects fully swept over the configured KAIZEN_SWEEP_PROJECTS set — "
            "health up must never buy coverage down (skipping red projects)."
        ),
    },
    {
        "id": "premature_stop",
        "version": 1,
        "counter_metric": "stop_block_causes",
        "formula": (
            "SESSION-level: sessions with a stop_block whose cause is premature "
            "(PREMATURE_CAUSES: run-record / promise-stall) over sessions with any "
            "stop verdict, from derived-facts rows — the Stop-hook oracle, read. "
            "Cross-reference: premature_stop_rate (T06) is the EVENT-level share of "
            "stop VERDICTS premature; non-premature causes (gate-red, uncommitted "
            "holds) never count here."
        ),
    },
    {
        "id": "stop_block_causes",
        "version": 1,
        "counter_metric": "premature_stop",
        "formula": (
            "the FULL {cause: count} distribution of stop_block events — premature "
            "and legitimate causes alike — the rate's shape, so a falling rate cannot "
            "hide a cause-mix shift. EVENT units throughout (numerator, denominator "
            "and cell). Dashes WITH premature_stop when no stop verdict exists (a "
            "pair never fabricates clean)."
        ),
    },
)


def registry() -> dict[str, dict]:
    """T06's registry plus the outcome tier — one validated, fully-paired set."""
    return kc.validate_registry((*kc.METRIC_DEFS, *OUTCOME_METRIC_DEFS))


# ── cli ───────────────────────────────────────────────────────────────────────────────


def _print_metric(m: MetricResult) -> None:
    mark = "" if m.measurable else "  [NOT MEASURED]"
    print(f"{m.id}: {m.cell}{mark}")
    if m.detail:
        print(f"  - {m.detail}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rework", action="store_true", help="mine rework across /opt repos")
    mode.add_argument("--sweep", action="store_true", help="fleet-health sweep (pilot set)")
    mode.add_argument("--stops", action="store_true", help="premature-stop rate from events")
    ap.add_argument("--only", help="sweep: comma list overriding KAIZEN_SWEEP_PROJECTS")
    ap.add_argument("--root", type=Path, default=OPT_ROOT, help="projects root (default /opt)")
    args = ap.parse_args(argv)

    registry()  # the pairs load (and refuse if unpaired) before anything is reported
    if args.rework:
        overall, per = rework_rate(root=args.root)
        for r in per:
            print(f"{r.repo}: {r.cell}" + (f" — {r.reason}" if r.reason else ""))
        _print_metric(overall)
        return 0
    if args.sweep:
        only = [p.strip() for p in args.only.split(",")] if args.only else None
        report = run_sweep(root=args.root, only=only)
        for line in report.lines:
            print(line)
        _print_metric(report.health)
        _print_metric(report.coverage)
        return 0
    prem, causes = premature_stop()
    _print_metric(prem)
    _print_metric(causes)
    _print_metric(review_rounds())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
