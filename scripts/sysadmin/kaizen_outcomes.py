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
  (``kaizen_collect_v2.window_delta_rows``); cf. T06's event-level ``premature_stop_rate``.

All three register in T06's paired-counter registry (a schema constraint — an
unpaired metric refuses to load): rework_rate ⟂ review_rounds, fleet_health ⟂
sweep_coverage, premature_stop ⟂ stop_block_causes.

POPULATION NOTE (W5-1, tightened W6, day-scoped publish W7-1) — the store-reading
metrics (``premature_stop``, ``stop_block_causes``, ``review_rounds``) compute
over DAY-SCOPED DELTA ROWS (``kc.window_delta_rows``) for a caller-chosen set of
day stamps: the CLI's on-demand view is the trailing window — the last
``KAIZEN_OUTCOMES_WINDOW_DAYS`` LOCAL calendar days including today (default 7;
the store's day stamps are local, W6-5, and under the daily cron the newest
derivable stamp is yesterday) — while the DAILY PUBLISH passes ``days=[the
published day]`` so every PUBLISHED day point is DAY-scoped (a trailing-window
value published as a day point made the weekly cell sum overlapping windows).
Each sid's in-window store rows are delta'd against its nearest earlier row, so
a lifetime session contributes only its in-window growth (never all-time
cumulative; the event-era filter and the root law live in the delta seam).
Attributed-side bootstrap symmetry (W6-2): a
first-ever delta row carrying family mass from before the window is
bootstrap-unmeasurable — excluded and counted. Value and attribution guard
measure the SAME rows with the SAME semantics; a window with no derived delta
rows at all is a derivation gap — unmeasurable with its measured cause (W6-4),
never a knowable 0. The window is stated in the formulas (a formula edit is a
def-hash version bump).

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
``KAIZEN_SWEEP_TIMEOUT_S`` (300), ``KAIZEN_OUTCOMES_WINDOW_DAYS`` (7 — the
store-reading metrics' day window: the last N LOCAL calendar days including today),
plus T06's ``KAIZEN_STATE_DIR`` / T01's ``KAIZEN_EVENTS_DIR`` through the modules
that own them. Box-local, stdlib only.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import kaizen_collect_v2 as kc  # noqa: E402 - same directory (registry + delta seams)
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


def _window_days() -> int:
    """The store-reading metrics' window (L7): ``KAIZEN_OUTCOMES_WINDOW_DAYS``,
    default 7 — an all-time cumulative read would let ancient history swamp the
    current week's signal."""
    return _env_int("KAIZEN_OUTCOMES_WINDOW_DAYS", 7)


def _window_day_stamps() -> list[str]:
    """THE window — ONE definition for value and guard alike (W5-1): the last
    ``KAIZEN_OUTCOMES_WINDOW_DAYS`` LOCAL calendar days INCLUDING today, as day
    stamps. LOCAL (W6-5): the store's day stamps are local dates (the daily pass
    stamps ``dt.date.today()``), so UTC arithmetic here silently dropped the
    boundary day whenever the two calendars disagreed. Under the daily cron the
    newest derivable stamp is YESTERDAY — today's stamp usually holds no row yet.
    The day window IS the value window: both guard operands and every metric
    population are computed over the same day-scoped delta rows
    (:func:`kaizen_collect_v2.window_delta_rows`)."""
    today = dt.date.today()
    return [(today - dt.timedelta(days=k)).isoformat() for k in range(_window_days())]


def _window_deltas(state: Path | None, days: list[str]) -> tuple[list[dict], list[dict]]:
    """``(all delta rows, attributed delta rows)`` over ``days`` (W5-1; the days
    are parameterized since W7-1 — the publish seam passes the single published
    day) — the unknown accumulator's rows stay in the first list (they are the
    guard's subject), out of the second (they are nobody's session)."""
    deltas = kc.window_delta_rows(days, state)
    return deltas, [r for r in deltas if r.get("sid") != kc.UNKNOWN]


def _no_derivation_reason(state: Path | None = None, days: list[str] | None = None) -> str:
    """W5-1 (#5) + W6-4 + W7-4: a window holding NO derived delta rows is
    unmeasurable, never a knowable 0 — and the dash names WHICH measured cause
    applies (empty store · transcript-era-only store · event-era rows exist but
    none dated in-window · in-window rows exist but every delta was
    shrink-suppressed), never a guessed "the daily derivation did not run"."""
    day_stamps = days if days is not None else _window_day_stamps()
    window = set(day_stamps)
    prefix = (
        f"no derivation in window — the {len(day_stamps)}d local day window holds "
        "no derived delta rows: "
    )
    suffix = "; never a knowable 0"
    by_sid = kc._rows_by_sid_day(state)
    if by_sid:
        # W7-4: the fourth measured branch — checked via delta_row's None returns
        # (the caller reaches here only when window_delta_rows came back empty, so
        # any in-window store row must have delta'd to None), never guessed.
        suppressed = 0
        for by_day in by_sid.values():
            days_sorted = sorted(by_day)
            for i, day in enumerate(days_sorted):
                if day not in window:
                    continue
                prev = by_day[days_sorted[i - 1]] if i > 0 else None
                if kc.delta_row(by_day[day], prev) is None:
                    suppressed += 1
        if suppressed:
            return (
                prefix + "in-window rows exist but every delta was suppressed "
                f"(accumulator/file shrink — {suppressed} row(s) delta'd to None)" + suffix
            )
        newest = max(d for days_ in by_sid.values() for d in days_)
        return (
            prefix
            + f"event-era rows exist but none dated in-window (newest derived day {newest})"
            + suffix
        )
    if any(True for _ in kc._iter_facts(state or kc.state_dir())):
        return prefix + "the store holds rows but none event-era (transcript-era only)" + suffix
    return prefix + "the derived-facts store is empty (nothing has ever been derived)" + suffix


def _smear_note(rows: list[dict], mass: Callable[[dict], int]) -> str:
    """W7-5 + W8-2 + W9-1 — the derivation-gap smear made VISIBLE, not
    structural: the delta seam attributes gap growth to the derivation day on the
    attributed side exactly as the unknown side documents it (design-consistent,
    deliberate). The predicate is PER ROW (W9-1): a kept row whose baseline
    (``delta_of``) SKIPS at least one calendar day before the ROW'S OWN day
    smears the skipped days' growth into it — whatever the window's edges (a
    window-edge threshold silenced real in-window gaps and flagged normal
    edge-day baselines). The immediately-preceding day is the normal consecutive
    baseline — never a smear. Annotated in the detail, never silently folded —
    including on the unavailable paths (W10-6). Only rows carrying the caller's
    family ``mass`` count (W10-7 — a zero-mass row smeared nothing), and BOTH
    date operands are validated (W10-5 — a malformed baseline string sorts
    before every real ISO date and would otherwise fabricate the count)."""
    k = 0
    for r in rows:
        day, base = r.get("day"), r.get("delta_of")
        if not (isinstance(day, str) and isinstance(base, str)):
            continue
        try:
            prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
            dt.date.fromisoformat(base)
        except ValueError:
            continue
        if base < prev and mass(r) > 0:
            k += 1
    if not k:
        return ""
    return f"; includes {k} row(s) whose baseline skips at least one day (derivation-gap smear)"


def _gapped(row: dict, *fields: str) -> bool:
    """Root law: a delta-row field measured with no same-field baseline is
    ``None`` — such a row is unmeasurable for consumers of that field and leaves
    numerator AND denominator."""
    return any(f in row and row[f] is None for f in fields)


def _bootstrap_split(
    rows: list[dict], mass: Callable[[dict], int], window_days: list[str]
) -> tuple[list[dict], int]:
    """W6-2 — attributed-side bootstrap symmetry (mirrors the unknown
    accumulator's W5-3 rule): a FIRST-EVER attributed delta row (``delta_of``
    None) carrying family mass whose session PREDATES the window (the 60-day
    session first derived today) dumped lifetime backlog as its "delta" — the
    in-window split is unknowable, so the row is bootstrap-unmeasurable for that
    family: excluded from value population AND guard operand, and counted. A
    first-ever row whose ``first_ts`` proves the session was BORN in-window
    carries no pre-window backlog and stays (its lifetime IS in-window growth);
    an absent/unparseable ``first_ts`` with mass cannot prove it — excluded. A
    zero-mass row dumped nothing for the family: a knowable 0, kept."""
    oldest = min(window_days)
    kept: list[dict] = []
    excluded = 0
    for r in rows:
        if r.get("delta_of") is not None or mass(r) <= 0:
            kept.append(r)
            continue
        born = kc._parse_ts(r.get("first_ts"))
        if born is not None and born.astimezone().date().isoformat() >= oldest:
            kept.append(r)  # born in-window — lifetime IS in-window growth
            continue
        excluded += 1
    return kept, excluded


def _bootstrap_reason(n: int, what: str) -> str:
    """The dash reason when bootstrap exclusion empties a metric's population."""
    return (
        f"bootstrap-unmeasurable — {n} attributed session(s') first-ever "
        f"derivation lands in-window carrying {what} from before the window "
        "(delta_of None: the 'delta' is lifetime backlog, not in-window growth — "
        "the attributed mirror of the unknown accumulator's bootstrap window; "
        "expected unmeasurable until a later re-derivation yields a real delta)"
    )


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
    #
    # NUL-delimited (M4): \x1e/\x1f CAN legally appear inside a commit subject, and an
    # injected one used to split the record mid-subject — the commit lost its file
    # list and the metric silently deflated. NUL cannot appear in a subject (git
    # rejects it), so the format's four %x00 delimiters are injection-proof: each
    # record contributes exactly (sha, ts, subject, name-status tail) — four tokens.
    out = _git_out(
        repo,
        [
            "log",
            "--no-merges",
            "-M",
            f"--since={lookback_days} days ago",
            "--format=%x00%H%x00%ct%x00%s%x00",
            "--name-status",
        ],
    )
    if out is None:
        return None
    commits: list[_Commit] = []
    parts = out.split("\x00")
    # parts[0] is the (empty) prefix before the first record; then groups of four.
    for idx in range(1, len(parts) - 2, 4):
        sha, raw_ts, subject = parts[idx], parts[idx + 1], parts[idx + 2]
        tail = parts[idx + 3] if idx + 3 < len(parts) else ""
        try:
            ts = int(raw_ts)
        except ValueError:
            continue  # a malformed record is skipped, never guessed at
        files: set[str] = set()
        fix_files: set[str] = set()
        for ln in tail.splitlines():
            parts_ln = ln.rstrip("\n").split("\t")
            if len(parts_ln) < 2 or not parts_ln[0].strip():
                continue
            status = parts_ln[0].strip()
            if status.startswith(("R", "C")) and len(parts_ln) >= 3:
                files.update((parts_ln[1], parts_ln[2]))  # both sides are matchable...
                continue  # ...but a rename/copy pair modifies nothing — never fix-side
            files.add(parts_ln[1])
            fix_files.add(parts_ln[1])
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
    # ignore_cleanup_errors (L2): a CHECK_UNREAPABLE child (D-state, survived
    # SIGKILL) can hold the temp worktree busy — cleanup then raises out of the
    # sweep. The unreapable path already warned; losing a temp dir is the fail-open
    # cost, crashing the sweep is not.
    with tempfile.TemporaryDirectory(
        prefix=f"kaizen-sweep-{name}-", ignore_cleanup_errors=True
    ) as tmp:
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


def _window_attribution_guard(
    names: tuple[str, ...], what: str, state: Path | None, attributed: int, days: list[str]
) -> tuple[str | None, str]:
    """W4-1/W5-1 — ``(dash_reason, publish_note)`` for a WINDOWED store metric,
    over the caller's ``days`` (parameterized since W7-1).

    LIKE WITH LIKE (W5-1): both operands are window-scoped per-day DELTAS from the
    same store — ``attributed`` is the caller's family sum over the window's
    attributed delta rows (a lifetime session contributes only its in-window
    growth), and the unattributed operand is the unknown accumulator's per-day
    delta mass over the SAME day stamps (``kc._windowed_unattributed``, reusing
    ``delta_row``). Guarded by the same 20% attribution floor as the unwindowed
    metrics: publishes (share stated) when healthy, dashes when the unknown stream
    holds the window's mass, and HEALS when attribution improves. An unknowable
    unknown mass dashes with its TRUE cause (W5-2/W5-3): accumulator shrank ·
    pre-v3 rows in window (absent ≠ 0, root law) · bump-day gap · bootstrap window
    (the accumulator's first derivation carries pre-window backlog — the first
    window after store bootstrap is expected unmeasurable)."""
    rows_by_day = kc._unknown_rows_by_day(state)
    unattributed, cause = kc._windowed_unattributed(rows_by_day, names, days)
    if unattributed is None:
        return kc.unattributed_unknowable_reason(cause, what), ""
    if unattributed > 0:
        total = attributed + unattributed
        if attributed / total < kc.ATTRIBUTED_MIN_SHARE:
            return (
                f"{what} unattributable in the window — {attributed} attributed vs "
                f"{unattributed} in the unknown stream (below the "
                f"{kc.ATTRIBUTED_MIN_SHARE:.0%} attribution floor)",
                "",
            )
        return (
            None,
            f"; window attribution share: {100 * attributed / total:.0f}% attributed "
            f"({attributed} attributed vs {unattributed} unknown-stream {what})",
        )
    return (
        None,
        f"; window attribution share: 100% attributed (0 unknown-stream {what} in the window)",
    )


def _stop_verdicts(row: dict) -> int:
    events = row.get("events")
    if not isinstance(events, dict):
        return 0
    return int(events.get("stop_pass", 0) or 0) + int(events.get("stop_block", 0) or 0)


def _stops_mass(row: dict) -> int:
    """The stops FAMILY mass of a row (W6-2's bootstrap gate): stop verdicts plus
    cause counts — a first-ever row carrying either dumped pre-window backlog."""
    causes = row.get("stop_causes")
    cause_mass = sum(int(v or 0) for v in causes.values()) if isinstance(causes, dict) else 0
    return _stop_verdicts(row) + cause_mass


def premature_stop(
    state: Path | None = None, days: list[str] | None = None
) -> tuple[MetricResult, MetricResult]:
    """(premature_stop, stop_block_causes) from derived-facts rows — T02's oracle read.

    SESSION-level by design: the share of stop-verdict-carrying sessions that hit a
    stop_block whose cause is premature (:data:`PREMATURE_CAUSES` — T06's set,
    imported, never copied). T06's ``premature_stop_rate`` beside it in the registry
    is EVENT-level (share of stop VERDICTS premature); the two formulas cross-reference
    each other. A stop_block with a non-premature cause (a gate-red or uncommitted-work
    hold) is a legitimate hold, not a premature stop — it stays out of the numerator
    and in the ``stop_block_causes`` histogram.

    ``days`` (W7-1): the day stamps the pair computes over. ``None`` — the CLI's
    on-demand trailing window (:func:`_window_day_stamps`). The daily publish
    passes ``days=[published day]`` so each PUBLISHED day point is DAY-scoped —
    a trailing-window value published as a day point made the weekly cell sum
    seven overlapping windows.

    Fail-open, PAIRED: a missing/empty events store — or zero stop verdicts — yields
    two honest ``—`` results with ONE shared reason. A paired counter must never
    fabricate "clean" while its metric is unmeasurable.
    """
    day_stamps = days if days is not None else _window_day_stamps()
    vocab: frozenset[str] | None = PREMATURE_CAUSES
    if vocab is None:
        reason = "premature-cause vocabulary unavailable (kaizen_collect_v2 import failed)"
        return (
            MetricResult.unavailable("premature_stop", reason),
            MetricResult.unavailable("stop_block_causes", reason),
        )
    # W5-1: ONE population — the window's day-scoped delta rows (event-era only,
    # each in-window store row minus its nearest earlier same-sid row; the T09 era
    # filter and the root law both live in the delta seam). Value and guard are
    # computed over the SAME rows with the SAME semantics — a lifetime session
    # contributes only its in-window growth.
    deltas, attributed = _window_deltas(state, day_stamps)
    if not deltas:
        reason = _no_derivation_reason(state, day_stamps)
        return (
            MetricResult.unavailable("premature_stop", reason),
            MetricResult.unavailable("stop_block_causes", reason),
        )
    # Root law: a delta row whose events/stop_causes map gapped (measured with no
    # same-field baseline) is unmeasurable for the stops family — out of BOTH
    # guard operand and value population.
    rows = [r for r in attributed if not _gapped(r, "events", "stop_causes")]
    # W6-2: attributed-side bootstrap symmetry — a first-ever row carrying
    # pre-window stops mass is excluded from BOTH operands and counted.
    rows, boot = _bootstrap_split(rows, _stops_mass, day_stamps)
    guard, note = _window_attribution_guard(
        ("stop_pass", "stop_block"),
        "stop-verdict events",
        state,
        sum(_stop_verdicts(r) for r in rows),
        day_stamps,
    )
    if guard is not None:
        return (
            MetricResult.unavailable("premature_stop", guard),
            MetricResult.unavailable("stop_block_causes", guard),
        )
    if boot:
        note += f"; {boot} bootstrap row(s) excluded — first-ever derivation predates the window"
    note += _smear_note(rows, _stops_mass)  # W7-5/W9-1/W10: the mass-bearing per-row smear
    # Per-SESSION grouping: a sid may carry several in-window delta rows (one per
    # derivation day); its window verdicts/causes are their sums.
    verdicts_by_sid: collections.Counter[str] = collections.Counter()
    causes: collections.Counter[str] = collections.Counter()
    premature_sids: set[str] = set()
    for r in rows:
        sid = str(r.get("sid"))
        verdicts = _stop_verdicts(r)
        verdicts_by_sid[sid] += verdicts
        if verdicts <= 0:
            # W6-3: causes ride verdict-bearing rows ONLY — a causes-without-
            # verdicts row must not leak into the histogram (numerator ⊆
            # denominator structurally, the pre-wave invariant restored).
            continue
        for cause, count in (r.get("stop_causes") or {}).items():
            n = int(count)
            causes[str(cause)] += n
            if n > 0 and cause in vocab:
                premature_sids.add(sid)
    sessions = {sid for sid, n in verdicts_by_sid.items() if n > 0}
    if not sessions:
        reason = (
            _bootstrap_reason(boot, "stop-verdict mass")
            if boot
            else "no stop verdicts in the window's delta rows"
        )
        # W10-6: never silently folded — the measured annotations (smear,
        # bootstrap count) ride the unavailable verdict too.
        return (
            MetricResult.unavailable("premature_stop", reason + note),
            MetricResult.unavailable("stop_block_causes", reason + note),
        )
    total_stops = sum(verdicts_by_sid.values())
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
            "full stop_block cause histogram in EVENT units — premature and legitimate "
            "causes alike, over the window's delta rows" + note
        ),
        value=dict(causes),
        numerator=sum(causes.values()),
        denominator=total_stops,
    )
    premature_sessions = len(premature_sids & sessions)
    prem = MetricResult(
        id="premature_stop",
        cell=_pct(premature_sessions, len(sessions)),
        detail=(
            "sessions with a premature-cause stop_block over sessions with any stop "
            "verdict, in-window growth only; cf. premature_stop_rate (T06) = share "
            "of stop VERDICTS premature" + note
        ),
        value=premature_sessions / len(sessions),
        numerator=premature_sessions,
        denominator=len(sessions),
    )
    return prem, causes_metric


def _round_growth(row: dict) -> int:
    events = row.get("events")
    if not isinstance(events, dict):
        return 0
    return int(events.get("round", 0) or 0)


def review_rounds(state: Path | None = None, days: list[str] | None = None) -> MetricResult:
    """Mean max-round per round-carrying session (rework_rate's counter pair).

    W5-1 (supersedes W4-1's mixed operands): value AND guard are computed over the
    SAME window-scoped day-scoped delta rows — a session is round-carrying only if
    its ROUND FAMILY GREW in the window (a 60-day session's lifetime rounds are
    not this window's rounds), and the guard's attributed operand is that same
    in-window growth against the unknown accumulator's per-day delta mass on the
    20% attribution floor; see :func:`_window_attribution_guard`. The session's
    VALUE stays ``rounds_max`` (point-in-time, carried by its latest in-window
    delta row). Publishes (share stated) when healthy, dashes when swamped or
    when the unknown mass is unknowable (with the true cause), and heals when
    attribution improves. A window with no derived delta rows at all is a
    derivation gap — unmeasurable, never a knowable 0.

    ``days`` (W7-1): the day stamps the metric computes over. ``None`` — the
    CLI's on-demand trailing window. The daily publish passes ``days=[published
    day]`` so the PUBLISHED day point is DAY-scoped: numerator = the day's summed
    ``rounds_max`` over its round-growth sids, denominator = their count — the
    weekly cell's n-weighted mean then weights each session once, never once per
    derivation-day residency."""
    day_stamps = days if days is not None else _window_day_stamps()
    deltas, attributed = _window_deltas(state, day_stamps)
    if not deltas:
        return MetricResult.unavailable("review_rounds", _no_derivation_reason(state, day_stamps))
    # Root law: an events-map gap row cannot say whether rounds happened — out of
    # both operands.
    rows = [r for r in attributed if not _gapped(r, "events")]
    # W6-2: attributed-side bootstrap symmetry — a first-ever row carrying
    # pre-window round mass is excluded from BOTH operands and counted.
    rows, boot = _bootstrap_split(rows, _round_growth, day_stamps)
    guard, note = _window_attribution_guard(
        ("round",),
        "round events",
        state,
        sum(_round_growth(r) for r in rows),
        day_stamps,
    )
    if guard is not None:
        return MetricResult.unavailable("review_rounds", guard)
    if boot:
        note += f"; {boot} bootstrap row(s) excluded — first-ever derivation predates the window"
    note += _smear_note(rows, _round_growth)  # W7-5/W9-1/W10: the mass-bearing per-row smear
    growth: collections.Counter[str] = collections.Counter()
    latest: dict[str, dict] = {}
    for r in rows:  # sorted (sid, day) — the last row per sid is its latest day
        sid = str(r.get("sid"))
        growth[sid] += _round_growth(r)
        latest[sid] = r
    vals = []
    for sid, grown in growth.items():
        if grown <= 0:
            continue
        runs = latest[sid].get("runs")
        rounds_max = int(runs.get("rounds_max", 0) or 0) if isinstance(runs, dict) else 0
        if rounds_max > 0:
            vals.append(rounds_max)
    if not vals:
        # W10-6: never silently folded — the measured annotations ride the
        # unavailable verdict too.
        return MetricResult.unavailable(
            "review_rounds",
            (
                _bootstrap_reason(boot, "round mass")
                if boot
                else "no session carries a round event in the window"
            )
            + note,
        )
    return MetricResult(
        id="review_rounds",
        cell=f"{sum(vals) / len(vals):.1f} (n={len(vals)})",
        detail=("mean rounds_max across sessions whose round family grew in the window" + note),
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
        # v4 (fix-wave 3, S3): window-knowability guard. v5 (fix-wave 4, W4-1):
        # windowed unattributed count on the 20% floor. v6 (fix-wave 5, W5-1):
        # BOTH operands and the value population come from the same day-scoped
        # delta rows — one window definition, in-window growth only. v7 (fix-wave
        # 6, W6-2 + W6-5): LOCAL day window + attributed-side bootstrap symmetry.
        # v8 (fix-wave 7, W7-1 + W7-5): the PUBLISHED day point is DAY-scoped +
        # the pre-window-baseline smear is annotated. v9 (fix-wave 8, W8-1 +
        # W8-2): the weekly cell is EXEMPT from series aggregation (latest-per-sid
        # over the week's delta rows) + the smear needs a SKIPPED day. v10
        # (fix-wave 9, W9-1 + W9-7): the smear predicate is PER ROW (the row's
        # own day, not the window edge) + the week-scope bootstrap divergence is
        # stated.
        "version": 10,
        "counter_metric": "rework_rate",
        "formula": (
            "mean rounds_max across sessions whose ROUND FAMILY GREW in the window, "
            "computed over the window's day-scoped delta rows. THE PUBLISHED DAY "
            "POINT IS DAY-scoped (W7-1): the daily publish computes over "
            "days=[the published day] only — numerator = that day's summed "
            "rounds_max over its round-growth sids, denominator = their count — "
            "an honest day view of that day's round growth. THE WEEKLY CELL IS "
            "EXEMPT from series aggregation (W8-1, the single-source law's one "
            "carve-out): rounds_max is a point-in-time per-session quantity, and "
            "anonymous day points cannot be per-session-deduplicated — a session "
            "growing across three week days would be counted once per residency "
            "day with its partial values summed (the 6.0-for-9.0 dilution). The "
            "weekly cell instead recomputes over the ISO week's day-scoped delta "
            "rows, latest-per-sid, under the same attribution-guard FUNCTION the "
            "day publish uses, scoped to the week's days. Bootstrap divergence "
            "stated (W9-7): the in-window-birth predicate is window-scoped, so a "
            "session born on a week day but first derived the next day is "
            "bootstrap-excluded from that day's single-day point yet KEPT by the "
            "week recompute — the wider window knows the birth was in-week; the "
            "weekly n may therefore exceed the sum of the week's day-point n's. "
            "The "
            "trailing window is ONLY the on-demand CLI view: ONE window "
            "definition for value and guard alike — the last "
            "KAIZEN_OUTCOMES_WINDOW_DAYS LOCAL calendar days including today "
            "(default 7; the store's day stamps are local dates, and under the "
            "daily cron the newest derivable stamp is yesterday), each sid's "
            "in-window store rows delta'd against its nearest earlier row (root "
            "law: absent-field baselines are None per field; gap rows leave "
            "numerator AND denominator), so a lifetime session contributes only "
            "its in-window growth — rounds down must never buy rework up. "
            "Baseline-smear symmetry (W7-5, per-row since W9-1 — visible not "
            "structural): the delta seam attributes derivation-gap growth to the "
            "derivation day on the attributed side exactly as on the unknown side "
            "— a kept row whose baseline (delta_of) SKIPS at least one calendar "
            "day before the ROW'S OWN day smears the skipped days' growth into "
            "it, annotated in the detail whatever the window's edges (a "
            "window-edge threshold silenced real in-window gaps); the "
            "immediately-preceding day is the normal consecutive baseline, never "
            "a smear. "
            "Attributed-side bootstrap symmetry: a first-ever attributed delta row "
            "(delta_of None) carrying round mass whose first_ts predates the "
            "window is bootstrap-unmeasurable — excluded from value AND guard "
            "operands and counted; the metric dashes with the bootstrap reason "
            "when the exclusion empties the population (a first_ts-proven "
            "in-window birth stays: its lifetime IS in-window growth). The "
            "session's value is rounds_max (point-in-time, latest in-window delta "
            "row). Window-scoped attribution guard over the SAME delta rows: "
            "attributed in-window round growth vs the unknown accumulator's "
            "per-day delta mass on the 20% attribution floor — publishes with the "
            "share stated, dashes below the floor, and dashes with the TRUE cause "
            "when the unknown mass is unknowable (accumulator shrank; pre-v3 rows "
            "in window — absent ≠ 0; bump-day gap; bootstrap window: the unknown "
            "accumulator's first derivation carries pre-window backlog, so the "
            "first window after store bootstrap is expected unmeasurable). A "
            "window with NO derived delta rows at all is 'no derivation in "
            "window' with the measured cause stated (empty store / transcript-era "
            "only / rows out of window), never a knowable 0. Never a lifetime "
            "ratio and never a lifetime ratchet: the guard heals when attribution "
            "improves."
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
        # v3 (fix-wave 3, S3): window-knowability guard. v4 (fix-wave 4, W4-1):
        # windowed unattributed count on the 20% floor. v5 (fix-wave 5, W5-1):
        # BOTH operands and the value population come from the same day-scoped
        # delta rows — one window definition, in-window growth only. v6 (fix-wave
        # 6, W6-2 + W6-5): LOCAL day window + attributed-side bootstrap symmetry.
        # v7 (fix-wave 7, W7-1 + W7-5): DAY-scoped published day point + the
        # annotated pre-window-baseline smear. v8 (fix-wave 8, W8-2): the smear
        # needs a SKIPPED day — a consecutive-day baseline is normal. v9
        # (fix-wave 9, W9-1): the smear predicate is PER ROW.
        "version": 9,
        "counter_metric": "stop_block_causes",
        "formula": (
            "SESSION-level: sessions with a premature-cause stop_block "
            "(PREMATURE_CAUSES: run-record / promise-stall) over sessions with any "
            "stop verdict, computed over the window's day-scoped delta rows. THE "
            "PUBLISHED DAY POINT IS DAY-scoped (W7-1): the daily publish computes "
            "over days=[the published day] only — that day's verdict-bearing "
            "sessions — the trailing window is ONLY the on-demand CLI view, never "
            "a published day point. ONE window definition for value and guard "
            "alike (smear rule shared, per-row since W9-1: only a baseline that "
            "SKIPS at least one calendar day before the ROW'S OWN day is a smear "
            "— the immediately-preceding day is the normal consecutive "
            "baseline): the last "
            "KAIZEN_OUTCOMES_WINDOW_DAYS LOCAL calendar days including today "
            "(default 7; the store's day stamps are local dates, and under the "
            "daily cron the newest derivable stamp is yesterday), each sid's "
            "in-window store rows delta'd against its nearest earlier row (root "
            "law: gap rows leave numerator AND denominator), so a lifetime "
            "session contributes only its in-window growth — the Stop-hook "
            "oracle, read. Baseline-smear symmetry (W7-5, visible not "
            "structural): a kept row whose baseline (delta_of) predates the "
            "window smears derivation-gap growth into it — annotated in the "
            "detail, exactly as the unknown side documents the same smear. "
            "Attributed-side bootstrap symmetry: a first-ever "
            "attributed delta row (delta_of None) carrying stops mass whose "
            "first_ts predates the window is bootstrap-unmeasurable — excluded "
            "from value AND guard operands and counted; the pair dashes with the "
            "bootstrap reason when the exclusion empties the population. "
            "Cross-reference: premature_stop_rate (T06) is the EVENT-level share "
            "of stop VERDICTS premature; non-premature causes (gate-red, "
            "uncommitted holds) never count here. Window-scoped attribution guard "
            "over the SAME delta rows: windowed attributed stop verdicts vs the "
            "unknown accumulator's per-day delta mass on the 20% attribution "
            "floor — publishes with the share stated, dashes below the floor, and "
            "dashes with the TRUE cause when the unknown mass is unknowable "
            "(accumulator shrank; pre-v3 rows in window — absent ≠ 0; bump-day "
            "gap; bootstrap window: the unknown accumulator's first derivation "
            "carries pre-window backlog, so the first window after store "
            "bootstrap is expected unmeasurable). A window with NO derived delta "
            "rows at all is 'no derivation in window' with the measured cause "
            "stated (empty store / transcript-era only / rows out of window), "
            "never a knowable 0. The guard heals when attribution improves."
        ),
    },
    {
        "id": "stop_block_causes",
        # v3 (fix-wave 3, S3): window-knowability guard. v4 (fix-wave 4, W4-1):
        # the windowed-delta guard. v5 (fix-wave 5, W5-1): the pair rides the
        # day-scoped delta-row population together — like with like everywhere.
        # v6 (fix-wave 6, W6-2/W6-3/W6-5): LOCAL day window, bootstrap symmetry,
        # and the numerator scoped to verdict-bearing rows. v7 (fix-wave 7,
        # W7-1 + W7-5): DAY-scoped published day point + the annotated smear.
        # v8 (fix-wave 8, W8-2): the smear needs a SKIPPED day. v9 (fix-wave 9,
        # W9-1): the smear predicate is PER ROW.
        "version": 9,
        "counter_metric": "premature_stop",
        "formula": (
            "the FULL {cause: count} distribution of stop_block events — premature "
            "and legitimate causes alike — the rate's shape, so a falling rate cannot "
            "hide a cause-mix shift. EVENT units throughout (numerator, denominator "
            "and cell), computed over the SAME day-scoped delta rows and window as "
            "its pair. THE PUBLISHED DAY POINT IS DAY-scoped (W7-1): the daily "
            "publish computes over days=[the published day] only; the trailing "
            "window (the last KAIZEN_OUTCOMES_WINDOW_DAYS LOCAL calendar days "
            "including today, default 7; the store's day stamps are local dates, "
            "and under the daily cron the newest derivable stamp is yesterday — "
            "in-window growth only) is ONLY the on-demand CLI view. "
            "Baseline-smear symmetry (W7-5, per-row since W9-1): a kept row "
            "whose baseline (delta_of) skips at least one calendar day before "
            "the ROW'S OWN day smears the skipped days' growth into it — "
            "annotated in the detail with its pair; the immediately-preceding "
            "day is the normal consecutive baseline, never a smear. Causes are "
            "summed over "
            "VERDICT-BEARING rows "
            "only (numerator ⊆ denominator structurally — a causes-without-"
            "verdicts row never leaks into the histogram), and the pair shares "
            "the attributed-side bootstrap exclusion (a first-ever delta row "
            "carrying pre-window stops mass is out of both operands, counted). "
            "Dashes WITH premature_stop when no stop verdict exists (a pair never "
            "fabricates clean), on 'no derivation in window' with the measured "
            "cause stated (a derivation gap is never a knowable 0), and under the "
            "same window-scoped attribution guard (windowed delta operands on the "
            "20% floor; an unknowable unknown mass dashes with its true cause — "
            "shrank / pre-v3 / bump-day gap / bootstrap window)."
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
