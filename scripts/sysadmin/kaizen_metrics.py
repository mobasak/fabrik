#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_metrics.py | docs/workstation/kaizen.md | docs/reference/agents/infra.md | docs/reference/agents/fleet.md | docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md
"""KAIZEN MEASUREMENT TRIGGER — the mechanical half of the weekly kaizen loop.

The charters (`docs/reference/agents/{infra,fleet}.md` § Kaizen) declare a weekly pass
BINDING for infra and fleet, and the roles spec pins five metrics. Between 2026-08-12 and
2026-08-16 the pass ran exactly zero times, because the spec left the cadence trigger as an
open item: a binding rule with no mechanism is documentation, not enforcement.

This script is the mechanism, and it is deliberately only HALF of the loop:

  MEASUREMENT (here)          cheap, stdlib-only, cron-able, no agent, no Claude quota.
  ANALYSIS    (the agent)     expensive, quota-scarce, timeboxed <=90 min.

Never spend Claude quota to produce a number a script can compute. The cron measures and
records the row; the mail it then sends hands the measured row (plus deltas vs the previous
row) to the analysis half, so the agent's pass starts with its input already gathered.

HONESTY RULE (load-bearing, see `_UNAVAILABLE`)
----------------------------------------------
A metric is written ONLY when a real source supports it. Everything else is written as an
em-dash with a one-line reason emitted to stderr and carried in the hand-off mail. A wrong
metric is worse than an absent one: it silently ends the investigation it should have
started. There are no estimates, no proxies wearing another metric's name, and no
plausible-looking placeholders in this file.

Today's verdicts (each re-derived at run time, never hardcoded):

  Gate first-pass rate     -- UNAVAILABLE. Nothing records gate runs. `final_gate.py`'s
                              `--post-kilo` writes `.droid/gate_issues.jsonl`, which has
                              never existed, and no hook keeps a pass/fail history.
  Death-classes /wk        -- REAL. `~/.claude/sound-debug.log` `event=StopFailure` lines
                              carry `error=<class>`; the decider's death classes.
  Lesson-class recurrence  -- UNAVAILABLE. `docs/LESSONS_LEARNT.md` headings are free prose
                              with no class tag, so recurrence needs semantic clustering --
                              that IS the analysis half's job. The countable context
                              (totals, new-in-window) rides the mail instead of the column.
  Review rounds /plan      -- REAL. `docs/development/reviews/*.md`, both ledger dialects.
  Missed crons             -- REAL since 2026-08-16, via `liveness_audit.py --json`. The
                              spec's cron-miss LOG still does not exist and never will (the
                              per-job logs are untimestamped appends, so run COUNTS are not
                              reconstructible) -- but the question behind the metric is
                              answerable a different way: did each registered surface
                              produce evidence inside its own budget? The cell is
                              DEAD/(LIVE+DEAD) over the heartbeat proof's surfaces.

                              ⚠️ The audit has THREE states, and an UNKNOWN is an instrument
                              failure, not a miss. UNKNOWNs are excluded from BOTH halves of
                              the fraction and named in the detail. Folding them into the
                              denominator would report a healthier box than we measured;
                              folding them into the numerator would invent defects. Either
                              is the honesty rule broken by a number that looks fine.
                              Mechanism health (inert checks, stale doc claims, unregistered
                              surfaces) rides the hand-off mail as context.

Modes:
  --once      measure, upsert one row per role, then mail the analysis half (fail-soft)
  --dry-run   print the rows that WOULD be written; touch nothing
  --report    print the current tables

Idempotence: the row is keyed by ISO week. A second run in the same ISO week UPDATES that
week's row instead of appending a second one, and it never overwrites a cell the analyst
filled -- a mechanically-unavailable metric yields to whatever a human/agent put there.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The em-dash the existing kaizen tables already use for "not measured".
DASH = "—"

# The liveness audit runs three proofs, one of which spawns a subprocess per gate-check
# canary. Generous, and fail-soft: a slow audit must never cost the measurement.
LIVENESS_TIMEOUT = 900

# Columns, in the order the shipped tables declare them. The script owns the five metric
# cells; the last two are the analyst's and are only ever written as DASH here.
COLUMNS = (
    "Date",
    "Gate first-pass rate",
    "Death-classes /wk",
    "Lesson-class recurrence",
    "Review rounds /plan",
    "Missed crons",
    "Top friction fixed",
    "Filed (spec/mail)",
)

ROLES = ("infra", "fleet")
WINDOW_DAYS = 7

# A numbered round heading: "## Round 3", "### Round-2 REFUTED", "## Round 7 (2026-08-15)".
_ROUND_HEADING = re.compile(r"^#{2,4}[ \t]+Round[\s-]*(\d+)\b", re.MULTILINE)
# The other shipped ledger dialect: a table whose first column is Round/Pass, one row each.
_ROUND_TABLE_HEADER = re.compile(r"^\**\s*(?:round|pass)e?s?\s*\**$", re.IGNORECASE)
_LEADING_INT = re.compile(r"^(\d+)")
_DATED_FILE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
_LESSON_HEADING = re.compile(r"^#{1,2} +Lesson\b", re.MULTILINE)
# "2026-08-16 14:19:06  arg=done  event=StopFailure  ...  error=rate_limit  ..."
_LOG_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\b")


@dataclass
class Metric:
    """One measured cell. Exactly one of `value` / `reason` is set."""

    value: str | None = None
    reason: str | None = None
    # Free-text grounding for the hand-off mail; never shortens into the cell.
    detail: str = ""

    @property
    def cell(self) -> str:
        return self.value if self.value is not None else DASH

    @property
    def measured(self) -> bool:
        return self.value is not None


def _unavailable(reason: str) -> Metric:
    """The honesty rule's only constructor for an unmeasured metric."""
    return Metric(value=None, reason=reason)


@dataclass
class Measurement:
    date: dt.date
    window_start: dt.date
    metrics: dict[str, Metric]
    context: list[str] = field(default_factory=list)

    def row(self) -> list[str]:
        cells = [self.date.isoformat()]
        cells += [self.metrics[c].cell for c in COLUMNS[1:6]]
        cells += [DASH, DASH]  # analyst-owned; preserved on re-run, never authored here
        return cells

    def reasons(self) -> list[tuple[str, str]]:
        return [(name, m.reason) for name, m in self.metrics.items() if not m.measured and m.reason]


# --------------------------------------------------------------------------- measurement


def measure_review_rounds(reviews_dir: Path, start: dt.date, end: dt.date) -> Metric:
    """Mean review rounds per in-window review ledger.

    Two ledger dialects ship in `docs/development/reviews/`: numbered `## Round N` headings,
    and a `| Round | ... |` (or `| Pass | ... |`) table. Counting only headings silently
    undercounts -- the 16-round stalled-midstream ledger uses the table form and would have
    scored 0 -- so both are read and the MAX round number wins per ledger.

    Ledgers using neither marker are NOT scored as zero rounds (they had rounds; they just
    did not machine-mark them). They are excluded and surface in the denominator, so the
    coverage of the mean is visible in the cell itself.
    """
    if not reviews_dir.is_dir():
        return _unavailable(f"no review ledger directory at {reviews_dir}")

    scored: list[int] = []
    unmarked = 0
    for path in sorted(reviews_dir.glob("*.md")):
        m = _DATED_FILE.match(path.name)
        if not m:
            continue  # undated ledger: cannot be placed in the window
        try:
            when = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if not (start <= when <= end):
            continue
        rounds = ledger_rounds(_read(path))
        if rounds:
            scored.append(max(rounds))
        else:
            unmarked += 1

    total = len(scored) + unmarked
    if not scored:
        return _unavailable(
            f"no in-window review ledger ({start}..{end}) carries a machine-readable round "
            f"marker ({total} ledger(s) seen)"
        )
    mean = statistics.mean(scored)
    return Metric(
        value=f"{mean:.1f} (n={len(scored)}/{total})",
        detail=(
            f"max round per ledger: {sorted(scored, reverse=True)}; "
            f"{unmarked} in-window ledger(s) carry no machine-readable round marker and are "
            f"excluded from the mean (they are NOT counted as zero rounds)"
        ),
    )


def ledger_rounds(text: str) -> list[int]:
    """Every round number a review ledger declares, in either shipped dialect."""
    found = [int(n) for n in _ROUND_HEADING.findall(text)]
    found.extend(_table_rounds(text))
    return found


def _table_rounds(text: str) -> list[int]:
    """Round numbers from a markdown table whose FIRST column is Round/Pass."""
    out: list[int] = []
    in_body = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_body = False
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            in_body = False
            continue
        first = cells[0]
        if first and set(first) <= set(":- "):
            continue  # the header separator row
        if not in_body:
            if _ROUND_TABLE_HEADER.match(first):
                in_body = True
            continue
        hit = _LEADING_INT.match(first)
        if hit:
            out.append(int(hit.group(1)))
    return out


def measure_death_classes(sound_log: Path, start: dt.date, end: dt.date) -> Metric:
    """Turn-death occurrences and distinct death classes in the window.

    Source: the Stop-hook sound log. `event=StopFailure` lines are the decider's deaths and
    carry the class as `error=<class>` (rate_limit, authentication_failed, server_error...).
    Older lines predate the `error=` field; they are counted as occurrences but contribute
    no class, and that split is reported so the number is never read as more precise than it
    is.
    """
    if not sound_log.is_file():
        return _unavailable(f"no Stop-hook sound log at {sound_log} (nothing records deaths)")

    lo, hi = start.isoformat(), end.isoformat()
    classes: dict[str, int] = {}
    occurrences = 0
    unclassified = 0
    for line in _read(sound_log).splitlines():
        if "event=StopFailure" not in line:
            continue
        stamp = _LOG_DATE.match(line)
        if not stamp or not (lo <= stamp.group(1) <= hi):
            continue  # undated legacy line, or out of window
        occurrences += 1
        err = next((tok[len("error=") :] for tok in line.split() if tok.startswith("error=")), "")
        if err and err != "-":
            classes[err] = classes.get(err, 0) + 1
        else:
            unclassified += 1

    ranked = sorted(classes.items(), key=lambda kv: (-kv[1], kv[0]))
    detail = (
        ", ".join(f"{name}={count}" for name, count in ranked) if ranked else "no classed death"
    )
    if unclassified:
        detail += f"; {unclassified} death(s) on log lines predating the error= field"
    return Metric(
        value=f"{occurrences} occ / {len(classes)} cls",
        detail=detail,
    )


def measure_gate_first_pass(repo_root: Path) -> Metric:
    """UNAVAILABLE by construction -- see the module docstring's honesty rule."""
    ledger = repo_root / ".droid" / "gate_issues.jsonl"
    where = "`.droid/gate_issues.jsonl` (final_gate.py --post-kilo)"
    if ledger.is_file():
        # Deliberately still unavailable: the file logs ISSUES, never a per-run pass/fail
        # verdict, so a first-pass RATE cannot be derived from it without inventing the
        # denominator. Recording that here keeps a future reader from "fixing" this by
        # counting lines.
        return _unavailable(
            f"{where} exists but records issues, not per-run verdicts -- a first-pass RATE "
            "needs a denominator of gate RUNS, which nothing records"
        )
    return _unavailable(
        f"no gate-run history exists: {where} was never written and no hook keeps a "
        "pass/fail record, so neither numerator nor denominator is observable"
    )


def measure_lesson_recurrence(lessons: Path, start: dt.date, end: dt.date) -> Metric:
    """UNAVAILABLE by construction -- recurrence needs a class taxonomy that does not exist."""
    if not lessons.is_file():
        return _unavailable(f"no lessons file at {lessons}")
    return _unavailable(
        "docs/LESSONS_LEARNT.md carries no class tag on its entries -- recurrence requires "
        "semantic clustering of free-prose headings, which is the analysis half's job, not "
        "a script's; the countable context rides the hand-off mail instead"
    )


def lesson_context(lessons: Path, start: dt.date, end: dt.date) -> str:
    """Countable lesson facts for the ANALYSIS half. Never a metric cell."""
    if not lessons.is_file():
        return ""
    text = _read(lessons)
    total = len(_LESSON_HEADING.findall(text))
    dated = len(
        [
            d
            for d in re.findall(r"\((\d{4}-\d{2}-\d{2})\)", text)
            if start.isoformat() <= d <= end.isoformat()
        ]
    )
    return (
        f"lessons: {total} numbered entries in docs/LESSONS_LEARNT.md; "
        f"{dated} in-window date stamp(s) -- clustering them into recurring CLASSES is your pass"
    )


def liveness_report(repo_root: Path, timeout: int = LIVENESS_TIMEOUT) -> tuple[dict | None, str]:
    """Run the liveness audit and parse its JSON. Returns (report, fault) -- never raises.

    A cron-miss log was never built and never will be: the per-job logs are untimestamped
    appends, so expected-vs-actual RUN COUNTS are not reconstructible. What IS observable is
    whether each declared surface produced evidence inside its own budget, which is the
    question the metric was always asking. `liveness_audit.py` answers it.
    """
    script = repo_root / "scripts" / "sysadmin" / "liveness_audit.py"
    if not script.is_file():
        return None, f"no liveness audit at {script}"
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(script), "--json", "--proof", "heartbeat,vacuity,doc_claim"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"the liveness audit could not be run: {type(exc).__name__}: {exc}"
    try:
        return json.loads(proc.stdout), ""
    except json.JSONDecodeError:
        tail = (proc.stderr or proc.stdout).strip()[-200:]
        return None, f"the liveness audit emitted no parseable JSON: {tail}"


def _findings(report: dict, proof: str) -> list[dict]:
    return list(((report.get("proofs") or {}).get(proof) or {}).get("findings") or [])


def measure_missed_crons(repo_root: Path, report: dict | None = None, fault: str = "") -> Metric:
    """Registered scheduled surfaces that produced NO evidence inside their budget.

    THE HONESTY RULE, sharpened: the liveness audit has three states, and an UNKNOWN is an
    instrument failure, not a miss. UNKNOWNs are excluded from BOTH the numerator and the
    denominator and reported by name -- rendering one as a number would be the same lie the
    three-state rule exists to prevent, wearing a metric's clothes.
    """
    if report is None:
        return _unavailable(fault or "the liveness audit produced no report")
    cron_like = [f for f in _findings(report, "heartbeat") if f.get("kind") in ("cron", "service", "hook")]
    if not cron_like:
        return _unavailable("the liveness registry declares no scheduled surfaces to measure")

    unknown = [f for f in cron_like if f["verdict"] == "UNKNOWN"]
    proven = [f for f in cron_like if f["verdict"] in ("LIVE", "DEAD")]
    if not proven:
        return _unavailable(
            f"all {len(unknown)} scheduled surface(s) reported UNKNOWN (instrument faults: "
            + "; ".join(sorted({f['instrument_fault'] for f in unknown}))[:300]
            + ") -- an instrument failure is not a miss and must not be counted as one"
        )
    missed = [f for f in proven if f["verdict"] == "DEAD"]
    return Metric(
        value=f"{len(missed)}/{len(proven)}",
        detail=(
            "missed: "
            + (", ".join(f"{f['id']} ({f['reason_class']})" for f in missed) or "none")
            + f"; {len(unknown)} surface(s) UNKNOWN and excluded from both numerator and "
            "denominator: "
            + (", ".join(f["id"] for f in unknown) or "none")
        ),
    )


def liveness_context(report: dict | None, fault: str) -> list[str]:
    """Mechanism health for the hand-off mail. Counts only; never a verdict."""
    if report is None:
        return [f"liveness audit: NOT RUN -- {fault}"]
    out: list[str] = []
    summary = report.get("summary") or {}
    out.append(
        f"liveness overall: LIVE={summary.get('LIVE', 0)} DEAD={summary.get('DEAD', 0)} "
        f"UNKNOWN={summary.get('UNKNOWN', 0)} (UNKNOWN = the probe's instrument could not be "
        "proven -- never read it as DEAD)"
    )
    vac = _findings(report, "vacuity")
    inert = [f["id"] for f in vac if f["verdict"] == "DEAD"]
    unproven = [f["id"] for f in vac if f["verdict"] == "UNKNOWN"]
    # LIVE is not one thing. A BLOCKING row is LIVE when it can go red; a row declared
    # warn_only in final_gate.py (kind "check(advisory)") or unwired from it is LIVE when it
    # can SPEAK -- it has no failing exit path at all. Reporting one total as "proven able to
    # fail" would overstate enforcement by exactly the number of rows that can never fail,
    # which is the whole finding this proof exists to surface.
    live = [f for f in vac if f["verdict"] == "LIVE"]
    can_fail = [f for f in live if f.get("kind") == "check"]
    out.append(
        f"gate checks: {len(can_fail)} blocking rows proven able to FAIL, "
        f"{len(live) - len(can_fail)} advisory/unwired proven to REPORT (no failing exit path), "
        f"{len(inert)} INERT ({', '.join(inert) or 'none'}), {len(unproven)} UNPROVEN (no canary)"
    )
    stale = [f["id"] for f in _findings(report, "doc_claim") if f["verdict"] == "DEAD"]
    docs = ((report.get("proofs") or {}).get("doc_claim") or {}).get("docs")
    out.append(
        f"doc claims: {len(stale)} STALE across {docs} workstation doc(s)"
        + (f" -- {', '.join(stale)}" if stale else "")
    )
    unreg = ((report.get("proofs") or {}).get("heartbeat") or {}).get("unregistered") or {}
    cron = unreg.get("cron") or {}
    if cron.get("instrument_fault"):
        out.append(f"unregistered surfaces: UNKNOWN -- {cron['instrument_fault']}")
    else:
        out.append(
            f"unregistered owned cron lines: {len(cron.get('owned', []))} (unregistered = unmonitored)"
        )
    return out


def measure(
    repo_root: Path, sound_log: Path, when: dt.date, liveness: tuple[dict | None, str] | None = None
) -> Measurement:
    start = when - dt.timedelta(days=WINDOW_DAYS - 1)
    lessons = repo_root / "docs" / "LESSONS_LEARNT.md"
    report, fault = liveness if liveness is not None else liveness_report(repo_root)
    metrics = {
        "Gate first-pass rate": measure_gate_first_pass(repo_root),
        "Death-classes /wk": measure_death_classes(sound_log, start, when),
        "Lesson-class recurrence": measure_lesson_recurrence(lessons, start, when),
        "Review rounds /plan": measure_review_rounds(
            repo_root / "docs" / "development" / "reviews", start, when
        ),
        "Missed crons": measure_missed_crons(repo_root, report, fault),
    }
    context = [c for c in (lesson_context(lessons, start, when),) if c]
    context += liveness_context(report, fault)
    return Measurement(date=when, window_start=start, metrics=metrics, context=context)


# ------------------------------------------------------------------------------- table io


@dataclass
class Table:
    head: list[str]
    header: str
    separator: str
    rows: list[str]
    tail: list[str]

    def render(self) -> str:
        parts = [*self.head, self.header, self.separator, *self.rows, *self.tail]
        return "\n".join(parts) + "\n"


def parse_table(text: str) -> Table:
    """Split a kaizen log into prose / header / separator / rows / prose.

    Preserving the exact header and separator lines is the point: the append must not
    reshape the table, so neither line is ever regenerated.
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("|")), None)
    if start is None or start + 1 >= len(lines):
        raise ValueError("no markdown table found")
    end = start + 2
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    return Table(
        head=lines[:start],
        header=lines[start],
        separator=lines[start + 1],
        rows=lines[start + 2 : end],
        tail=lines[end:],
    )


def split_row(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def render_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _iso_week(value: str) -> tuple[int, int] | None:
    try:
        parsed = dt.date.fromisoformat(value.strip())
    except ValueError:
        return None
    year, week, _ = parsed.isocalendar()
    return year, week


def merge_cells(new: list[str], old: list[str]) -> list[str]:
    """Same-week update: mechanical cells win, analyst-filled cells survive.

    A cell this script writes as DASH means "no real source supports it". If a human or the
    analysis agent has since put something there, the script must not stamp it back to DASH
    -- that would make the mechanical half destroy the analytical half's output every week.
    """
    merged = list(new)
    for i, cell in enumerate(new):
        if i == 0:
            continue  # the Date cell always advances to this run
        if cell == DASH and i < len(old) and old[i] not in ("", DASH):
            merged[i] = old[i]
    return merged


def upsert(path: Path, cells: list[str]) -> tuple[str, list[str] | None]:
    """Append the row, or update this ISO week's existing row. Returns (action, previous)."""
    table = parse_table(_read(path))
    key = _iso_week(cells[0])
    previous: list[str] | None = None
    target: int | None = None
    for i, row in enumerate(table.rows):
        row_cells = split_row(row)
        if not row_cells:
            continue
        if key is not None and _iso_week(row_cells[0]) == key:
            target = i
        else:
            previous = row_cells

    if target is None:
        table.rows.append(render_row(cells))
        action = "appended"
    else:
        existing = split_row(table.rows[target])
        table.rows[target] = render_row(merge_cells(cells, existing))
        action = "updated"
    path.write_text(table.render(), encoding="utf-8")
    return action, previous


# ------------------------------------------------------------------------------- hand-off


def deltas(new: list[str], old: list[str] | None) -> list[str]:
    if not old:
        return ["(no previous row -- this is the first measured pass)"]
    out = []
    for i, name in enumerate(COLUMNS[1:6], start=1):
        was = old[i] if i < len(old) else DASH
        now = new[i]
        out.append(f"- {name}: {was} -> {now}" + ("  (unchanged)" if was == now else ""))
    return out


def compose_mail(role: str, m: Measurement, cells: list[str], previous: list[str] | None) -> str:
    lines = [
        f"# Kaizen measurement -- {role}, week of {m.window_start} .. {m.date}",
        "",
        "The MECHANICAL half ran (cron, no agent, no quota). This is your input; the",
        f"ANALYSIS half is yours: <=90 min, per `docs/reference/agents/{role}.md` § Kaizen.",
        "",
        "## This week's row",
        "",
        render_row(list(COLUMNS)),
        render_row(["---"] * len(COLUMNS)),
        render_row(cells),
        "",
        "## Deltas vs the previous row",
        "",
        *deltas(cells, previous),
        "",
        "## Grounding for the measured cells",
        "",
    ]
    for name, metric in m.metrics.items():
        if metric.measured and metric.detail:
            lines.append(f"- {name}: {metric.detail}")
    reasons = m.reasons()
    if reasons:
        lines += [
            "",
            "## Not measured (and why -- these are findings, not gaps to paper over)",
            "",
        ]
        lines += [f"- {name}: {reason}" for name, reason in reasons]
    if m.context:
        lines += ["", "## Context for the analysis (countable, not a metric)", ""]
        lines += [f"- {c}" for c in m.context]
    lines += [
        "",
        "## What to do with it",
        "",
        "Analyze (recurrence x blast radius, evidence-cited) -> improve (<=30 min fixes land",
        "in-pass; larger become a spec or a mailed handoff) -> control (every fix ships a",
        "regression guard). Then fill `Top friction fixed` + `Filed` in the row; a re-run of",
        "`kaizen_metrics.py` will NOT overwrite what you put there.",
        "",
    ]
    return "\n".join(lines)


def send_mail(repo_root: Path, role: str, body: str) -> bool:
    """Hand the measured row to the analysis half. FAIL-SOFT: the row is already on disk."""
    mail = repo_root / "scripts" / "mail.py"
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(mail), "send", "--to", "fabrik", "--kind", "request"],
            input=body,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive; any failure is non-fatal
        print(
            f"kaizen: mail hand-off failed for {role} ({exc}) -- ROW IS RECORDED", file=sys.stderr
        )
        return False
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {proc.returncode}"
        print(
            f"kaizen: mail hand-off failed for {role} ({tail}) -- ROW IS RECORDED",
            file=sys.stderr,
        )
        return False
    return True


# ----------------------------------------------------------------------------------- cli


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def log_path(repo_root: Path, role: str) -> Path:
    return repo_root / "docs" / "reference" / "agents" / f"kaizen-log-{role}.md"


def _emit_reasons(m: Measurement) -> None:
    for name, reason in m.reasons():
        print(f"kaizen: {name} = {DASH} -- {reason}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    when = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    m = measure(repo_root, args.sound_log, when)
    cells = m.row()

    if args.report:
        for role in ROLES:
            path = log_path(repo_root, role)
            print(f"=== {path} ===")
            print(_read(path).rstrip() if path.is_file() else "(missing)")
            print()
        return 0

    _emit_reasons(m)

    if args.dry_run:
        print(f"# window {m.window_start} .. {m.date}  (nothing written)")
        print(render_row(list(COLUMNS)))
        print(render_row(cells))
        for role in ROLES:
            print(f"# -> {log_path(repo_root, role)}")
        return 0

    failures = 0
    for role in ROLES:
        path = log_path(repo_root, role)
        if not path.is_file():
            print(f"kaizen: no kaizen log at {path} -- skipped", file=sys.stderr)
            failures += 1
            continue
        # ORDER IS THE CONTRACT: record first, mail second. A mail failure must never
        # cost the measurement.
        action, previous = upsert(path, cells)
        print(f"kaizen: {action} row in {path}")
        if not args.no_mail:
            send_mail(repo_root, role, compose_mail(role, m, cells, previous))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Measure the five pinned kaizen metrics and record one row per role."
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="measure, upsert rows, mail the analyst")
    mode.add_argument("--dry-run", action="store_true", help="print the rows; write nothing")
    mode.add_argument("--report", action="store_true", help="print the current tables")
    p.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument(
        "--sound-log",
        type=Path,
        default=Path.home() / ".claude" / "sound-debug.log",
        help="Stop-hook log carrying event=StopFailure death classes",
    )
    p.add_argument("--date", help="ISO date to measure as (default: today)")
    p.add_argument("--no-mail", action="store_true", help="skip the analysis hand-off mail")
    return p


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
