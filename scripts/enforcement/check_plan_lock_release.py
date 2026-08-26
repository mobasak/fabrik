#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_plan_lock_release.py
"""Plan-lock release gate — ADVISORY. A finished plan must not hold its scope lock.

THE MEASURED CLASS. `.fabrik/plan-locks/<plan-id>.json` is created by prose
(`/fabrik-execute-plan` Before-You-Start step 7) and released by prose (Finish step 5).
Three consumers READ locks; **nothing writes one but the agent**. Two live instances were
measured 2026-08-25: `kaizen-m1-event-stream` sat `active` with `completed_at` set and
`final_commit` null — one field of a three-field write landing — and BLOCKED an unrelated
plan at step 7 on three high-traffic hub paths until the operator ruled; `ai-model-catalog`
held ten paths for thirteen days. This check is the executable backing for
`commands/_sources/fabrik-catchup.md:47-60` probe 1, which already specified the rule in prose.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — findings included.
`final_gate.py:262-270` turns any non-zero exit from a `warn_only` check into a BLOCKING red
("its contract changed"), which on a governance-synced check means ~46 repos. Every failure
path returns 0 with an honest line; the exception guard catches the CLASS, never a list of types.

NEVER AUTO-RECLAIMS. It reports. Freeing another plan's lock is an operator action
(`fabrik-execute-plan.md:73-78`), and the remediation text names the owner and the sanctioned
action - the plan's OWNER releases it per Finish step 5; if a run is confirmed dead the
OPERATOR deletes the lock file. Locks are git-tracked, so telling an arbitrary reader to
"release it" would instruct a never-commit-what-you-did-not-author violation from this check's
own output.

TWO NAMED EXITS — this check is not meant to live forever:
  * PROMOTE to blocking once it has run with zero findings across the fleet for two
    consecutive weekly syncs. Operator decision.
  * DELETE it, and build the mechanical acquire/release writer instead, if it catches more
    than two NEW instances after landing (day-one inherited debt does not count). A third
    instance means detection is not changing behaviour and only removing the prose write will.

Full subsystem reference: docs/reference/plan-lock-lifecycle.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# NO cross-module import, deliberately. An earlier revision imported `check_convergence.EXECUTED`
# and bound it to a name it never read. That dead import cost three real things: (1) `except
# Exception` does NOT catch `SystemExit` (a BaseException), so a sibling that exits at import time
# turned this advisory row into a BLOCKING RED across ~46 repos — measured rc=3 — which is the exact
# `check_pack_reachability` failure mode this module exists to avoid; (2) a sibling printing at
# import prepended its stdout BEFORE the census, breaking the census-prints-first invariant;
# (3) it made `docs/reference/plan-lock-lifecycle.md`'s "stdlib only" contract false, and
# stdlib-only is precisely what makes a synced check safe to drop into 48 repos whose sibling
# copies may be mid-sync. `_STATUS_LINE` below mirrors check_convergence's anchor by SHAPE; the
# test suite pins the shapes rather than the coupling.
# ── the status partition — derived from the WRITER's contract, not from the corpus ──────
# `/fabrik-execute-plan` prescribes `active` (step 7), `paused` (:459, quota pause) and
# `blocked` (:563, halt). All three are MID-FLIGHT. Reading the corpus alone yields only the
# values that happen to exist and silently counts a paused run as finished.
NON_TERMINAL = frozenset({"active", "paused", "blocked"})
TERMINAL = frozenset({"released", "executed", "complete", "completed"})

# Finished-plan vocabulary. `RESOLVED` is deliberately absent — it is how this repo labels a
# resolved issue INSIDE an unfinished plan, and it was the first measured false positive.
# `CONVERGED` is absent too: a converged plan is ready to execute, not executed.
FINISHED_TOKENS = (
    "IMPLEMENTATION-CONVERGED",
    "EXECUTED",
    # COMPLETED must precede COMPLETE — the shorter one is a prefix of the longer, so an
    # alphabetised tuple would make "COMPLETED 2026-08-01" report as "COMPLETE".
    "COMPLETED",
    "COMPLETE",
    "CLOSED",
    "DONE",
    "SHIPPED",
    "FIXED",
    "SUPERSEDED",
)

# The completion-timestamp FAMILY, enumerated — never inferred as `endswith("_at")`.
# `started_at` is on 212 of ~213 fleet locks, so the inferred form fires HALF-APPLIED FINISH
# on every non-terminal lock in the fleet.
COMPLETION_TS = ("completed_at", "finished_at", "released_at")

# Both fence syntaxes, and indented fences inside list items — a `~~~` or two-space-indented
# block carrying a `status:` line would otherwise still parse as the plan's status.
# The closing marker must MATCH the opener (`\1`), as CommonMark requires. Accepting either marker
# on both ends let the non-greedy `.*?` pair an opening ``` with an unrelated ~~~ (or pair the FIRST
# of two same-marker fences with the SECOND's opener), stripping the wrong span and LEAVING a
# `Status:` line that lives inside a code block exposed to the anchor. Measured: a plan whose real
# status is IN-PROGRESS but which quotes `Status: EXECUTED` inside a fence read as EXECUTED — a
# LIKELY STALE LOCK finding against a perfectly healthy lock, which is the one outcome worse than
# not running at all. An UNTERMINATED fence now swallows to EOF for the same reason.
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(?:.*?^[ \t]*\1[ \t]*$|.*\Z)", re.M | re.S)
# Mirrors `check_convergence.EXECUTED`'s anchor (:122-126) so both accept the same shapes —
# notably `**Status:**` with the colon INSIDE the bold, which needs the post-colon `\*{0,2}`.
_STATUS_LINE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(.*)$", re.M | re.I
)
_DECORATION = re.compile(r"^[\s*✅🚧✔️—–\-]+")

LABELS = (
    "stale",
    "likely_stale",
    "half_applied",
    "plan_field_stale",
    "orphan",
    "foreign",
    "unknown_status",
    "unevaluable",
)
_LABEL_TEXT = {
    "stale": "STALE LOCK",
    "likely_stale": "LIKELY STALE LOCK",
    "half_applied": "HALF-APPLIED FINISH",
    "plan_field_stale": "PLAN FIELD STALE",
    "orphan": "ORPHAN LOCK",
    "foreign": "FOREIGN LOCK",
    "unknown_status": "UNKNOWN STATUS",
    "unevaluable": "UNEVALUABLE",
}
_KEY = {v: k for k, v in _LABEL_TEXT.items()}

# `final_gate.py:2114` ships each advisory row as `output[:500]`.
_ADVISORY_BUDGET = 500
# No single finding line may consume the whole budget.
_MAX_LINE = 220
_MAX_LINES = 10  # `final_gate.py:387` prints ten lines of advisory output, with NO ellipsis

_REMEDY = (
    "the plan's OWNER releases it (Finish step 5); if that run is confirmed dead the OPERATOR "
    "deletes the lock (fabrik-execute-plan.md:77). Never edit another session's lock."
)


@dataclass
class Finding:
    label: str
    lock: str
    detail: str = ""
    remedy: str = ""


@dataclass
class PlanRef:
    location: str = "missing"  # "live" | "archived" | "missing"
    status_value: str | None = None
    spine: Path | None = None
    field_resolved: bool = True
    tried: list[str] = field(default_factory=list)


def normalise_status(raw: object) -> str:
    """Case-fold before EVERY partition test — a live upper-case `RELEASED` lock exists."""
    return str(raw or "").strip().lower()


def strip_decoration(value: str) -> str:
    return _DECORATION.sub("", value or "").strip()


def status_value(spine_text: str) -> str | None:
    """The VALUE off a plan's `Status:` line — fence-stripped, FIRST match wins.

    Fence-stripping is load-bearing: a fenced `status: Mapped[str] = mapped_column(` would
    otherwise parse as a plan's status and read as "not finished" (fail-silent-green).
    First-not-last is load-bearing too: five live fleet plans carry more than one
    `Status:`-shaped line and two flip verdict between the first and the last.
    """
    if not spine_text:
        return None
    m = _STATUS_LINE.search(_FENCE.sub("", spine_text))
    if not m:
        return None
    return m.group(1).strip() or None


def finished_token(value: str) -> str | None:
    """The finished token a status VALUE begins with, or None. ANCHORED, never a substring.

    A substring search returns `COMPLETE` for
    `Issue 1 RESOLVED (§2.8). **Phase B complete + live-validated.** …` — a real, unfinished
    fleet plan. Anchoring on the decoration-stripped value is what makes the token list safe.
    """
    up = strip_decoration(value or "").upper()
    return next((w for w in FINISHED_TOKENS if up.startswith(w)), None)


def _read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def resolve_plan(root: Path, lock_path: Path, plan_field: str | None) -> PlanRef:
    """Four-way stem resolution. NOT an inherited convention — `check_plan_tickets.py:1481`
    resolves ONE location gated on `is_dir()`, which misses every single-file `.md` plan."""
    stem = Path(str(plan_field or lock_path.stem)).stem
    plans = root / "docs" / "development" / "plans"
    branches = [
        ("live", plans / f"{stem}.md"),
        ("live", plans / stem / f"{stem}.md"),
        ("archived", plans / "archived" / f"{stem}.md"),
        ("archived", plans / "archived" / stem / f"{stem}.md"),
        # `archive` without the 'd' is a REAL fleet layout, not a typo to ignore:
        # /opt/youtube/docs/development/plans/archive/ holds 33 plans. Hard-coding only
        # "archived" downgraded a genuinely stale lock there from STALE LOCK to ORPHAN LOCK,
        # and the verdict from FINDINGS to NOTHING VERIFIED.
        ("archived", plans / "archive" / f"{stem}.md"),
        ("archived", plans / "archive" / stem / f"{stem}.md"),
    ]
    ref = PlanRef(tried=[str(p.relative_to(root)) for _, p in branches])
    for loc, cand in branches:
        if cand.is_file():
            ref.location, ref.spine = loc, cand
            ref.status_value = status_value(_read(cand) or "")
            break
    else:
        # A plan-set DIRECTORY with no same-stem spine still tells us where the plan lives.
        for loc, d in (
            ("live", plans / stem),
            ("archived", plans / "archived" / stem),
            ("archived", plans / "archive" / stem),
        ):
            if d.is_dir():
                ref.location = loc
                break

    # Is the stored `plan` value itself still correct? 11 fleet locks store a bare stem
    # rather than a path — those are resolved by the stem, never "stale".
    pf = str(plan_field or "")
    if ref.location != "missing":
        if "/" not in pf:
            ref.field_resolved = True  # a bare stem is resolved BY the stem — never "stale"
        else:
            # `Path("/a") / "/b"` == `/b` — an absolute value discards `root` entirely, so a
            # lock pointing at ANOTHER repo would be declared healthy on a cross-repo stat().
            cand = (root / pf).resolve()
            inside = cand == root.resolve() or root.resolve() in cand.parents
            ref.field_resolved = inside and cand.exists()
    return ref


def _truncate(value: str, limit: int = 90) -> str:
    """Quote a plan's Status value, bounded. `final_gate.py:2114` ships advisory output as
    `output[:500]` and `:387` prints 10 lines — one real fleet status value is ~900 chars, so an
    unbounded quote silently truncates every finding after it."""
    v = " ".join((value or "").split())
    return v if len(v) <= limit else v[: limit - 3] + "..."


def evaluate(root: Path, lock_path: Path) -> tuple[list[Finding], bool]:
    """(findings, evaluable). EVALUABLE means: we read this lock, it is in a non-terminal state,
    and we could read its plan's state — i.e. the question was actually asked. Terminal locks are
    correctly skipped (not evaluable); unreadable ones are an unasked question (not evaluable).
    Deriving this from the emitted LABELS instead was wrong: a terminal-but-unparseable lock
    inflated the count and turned `NOTHING VERIFIED` into `OK — 1 non-terminal evaluated`."""
    name = lock_path.name
    raw = _read(lock_path)
    if raw is None:
        return [Finding("UNEVALUABLE", name, "lock file could not be read")], False
    try:
        data = json.loads(raw)
    except Exception:
        return [Finding("UNEVALUABLE", name, "lock file is not valid JSON")], False
    if not isinstance(data, dict):
        return [Finding("UNEVALUABLE", name, "lock file is valid JSON but not an object")], False

    # 1. JURISDICTION FIRST, and it short-circuits. A repo-wide advisory mutex is a different
    #    protocol; judging it would be this check's own version of the over-reach it catches.
    #    Keyed on shape, NEVER on the `plan` value's prose (one fleet repo-lock contains a "/").
    if "holder" in data and data.get("owned_paths") == ["**"]:
        return [
            Finding(
                "FOREIGN LOCK",
                name,
                f"not a plan lock (holder={data.get('holder')!r}) - not judged",
            )
        ], False

    findings: list[Finding] = []
    status = normalise_status(data.get("status"))

    # 2. Status partition. UNKNOWN ACCUMULATES — it never returns — so a typo cannot suppress
    #    a real finding behind it.
    if status in TERMINAL:
        return [], False
    if "status" not in data:
        # A MISSING field is an unasked question, not an unrecognised VALUE.
        return [Finding("UNEVALUABLE", name, "lock carries no status field")], False
    if status not in NON_TERMINAL:
        findings.append(
            Finding(
                "UNKNOWN STATUS",
                name,
                f"status {data.get('status')!r} is outside the writer's contract",
            )
        )

    ref = resolve_plan(root, lock_path, data.get("plan"))

    # 3. Rule 1 — is the plan finished?
    if ref.location == "missing":
        looked = Path(str(data.get("plan") or lock_path.stem)).stem
        # Name the stem and the COUNT, not every candidate path. Listing all of them was ~800
        # chars on a real repo — and it got worse when the `archive` (no 'd') branches took the
        # list from four candidates to six, so a fix widened a line past the advisory budget.
        # The stem is what the operator needs; the search order lives in the doc.
        findings.append(
            Finding(
                "ORPHAN LOCK",
                name,
                f"no plan resolves for stem {looked!r} "
                f"({len(ref.tried)} file locations under docs/development/plans/)",
            )
        )
    elif ref.location == "archived":
        if ref.status_value:
            detail = f'its plan is ARCHIVED (Status: "{_truncate(ref.status_value)}")'
        else:
            detail = "its plan is ARCHIVED (status line unreadable)"
        findings.append(Finding("STALE LOCK", name, detail, _REMEDY))
    else:
        tok = finished_token(ref.status_value or "")
        if tok:
            findings.append(
                Finding(
                    "LIKELY STALE LOCK",
                    name,
                    f'its plan reads Status: "{_truncate(ref.status_value)}" (matched {tok})',
                    _REMEDY,
                )
            )

    # 4. The plan resolved but its state could not be read — an unasked question, never a pass.
    if ref.location != "missing" and ref.status_value is None:
        findings.append(
            Finding("UNEVALUABLE", name, "plan resolved but carries no readable Status: line")
        )

    # 5. Rule 2 — a half-applied Finish step 5.
    # Finish step 5 writes THREE things: status:"released", a completion timestamp, and
    # final_commit. A non-terminal lock carrying ANY completion timestamp is a half-apply
    # regardless of final_commit — an earlier revision keyed only on `final_commit` being absent
    # and so reported plain `OK` for {active + completed_at + final_commit}, the two-of-three case
    # where the STATUS FLIP is the missing field. That lock still hard-BLOCKs an unrelated plan at
    # step 7, which is the whole motivating class.
    ts = next((k for k in COMPLETION_TS if data.get(k)), None)
    if ts:
        missing = (
            "the status flip"
            if data.get("final_commit")
            else "final_commit or the status flip (neither landed)"
        )
        findings.append(
            Finding(
                "HALF-APPLIED FINISH",
                name,
                f"{ts}={data.get(ts)!r} but status is still {data.get('status')!r} - "
                f"Finish step 5 did not land {missing}",
                _REMEDY,
            )
        )

    # 6. A missed Finish step-6 repoint — reported only for non-terminal locks (35 of the
    #    fleet's 37 stale paths sit on terminal locks: dead history, and re-pointing a released
    #    lock destroys provenance).
    # NOT on an archived plan: STALE LOCK already owns that lock, and advising a repoint there
    # contradicts the provenance rule (fabrik-execute-plan.md:69-71) the doc cites. Emitting both
    # gave one lock two counters and two contradictory instructions.
    if not ref.field_resolved and ref.location == "live":
        findings.append(
            Finding(
                "PLAN FIELD STALE",
                name,
                f"plan field {data.get('plan')!r} does not resolve — Finish step 6 repoint missing",
            )
        )
    # EVALUABLE = a RECOGNISED non-terminal status AND a readable plan state. An unrecognised
    # status is of unknown terminality, so counting it as "non-terminal evaluated" overstates
    # what the run actually asked.
    return findings, (
        status in NON_TERMINAL and ref.location != "missing" and ref.status_value is not None
    )


def classify(root: Path, lock_path: Path) -> list[Finding]:
    """0, 1 or MORE findings per lock — one lock can carry several labels at once."""
    return evaluate(root, lock_path)[0]


def _collect(root: Path) -> tuple[dict[str, int], list[Finding], int, int, int]:
    """(counters, findings, examined, evaluable, foreign). `evaluable` comes from `evaluate()`,
    never from the emitted labels — inferring it from labels counted a terminal-but-unparseable
    lock as "1 non-terminal evaluated" and turned NOTHING VERIFIED into OK."""
    lockdir = root / ".fabrik" / "plan-locks"
    counters = dict.fromkeys(LABELS, 0)
    findings: list[Finding] = []
    examined = evaluable = foreign = 0
    if not lockdir.is_dir():
        return counters, findings, examined, evaluable, foreign
    for lock in sorted(lockdir.glob("*.json")):
        examined += 1
        # The WHOLE per-lock body is guarded, accumulation included: an exception escaping the
        # loop is caught by main's outer guard, which discards EVERY lock's findings and still
        # exits 0 — fail-silent for the entire corpus instead of for one lock.
        try:
            got, ok = evaluate(root, lock)
            evaluable += 1 if ok else 0
            foreign += 1 if any(f.label == "FOREIGN LOCK" for f in got) else 0
            for f in got:
                counters[_KEY.get(f.label, "unevaluable")] += 1
            findings.extend(got)
        except Exception as exc:  # the CLASS, never an enumerated list of types
            counters["unevaluable"] += 1
            findings.append(Finding("UNEVALUABLE", lock.name, f"could not evaluate: {exc!r}"))
    return counters, findings, examined, evaluable, foreign


def _ascii_safe_stdout() -> None:
    """Never lose output to the terminal's encoding.

    Round 2 fixed only the census separator; every OTHER line still carried non-ASCII — the em
    dashes in the verdict lines, and the plan's own Status value, which routinely contains `✅` and
    `—` across the fleet. Under an ASCII stdout the census printed, the next line raised, main's
    guard caught it, and the guard's own message re-embedded the offending payload via `repr(exc)`
    so IT failed too and was swallowed. Net: `1 stale` in the census, no lock name, no remedy, no
    error, rc 0 — an operator could not distinguish a truncated run from a clean one. That is the
    fail-silent-green class, inside the check written to prevent it. Reconfiguring once at entry
    makes every subsequent print survive, whatever the payload.
    """
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:  # pragma: no cover - very old/exotic streams
        pass


def _say(line: str) -> None:
    """The ONLY print in this module, and the ASCII guarantee's real home.

    `_ascii_safe_stdout` is a belt, not the brace: `reconfigure` exists only on a real
    `TextIOWrapper`, so under a wrapped/captured/exotic stdout it silently does nothing (its
    `except` is a `pass`) and the very next `\u2705` in a quoted plan status raises again. Round 4
    raised that: the fix depended on the environment cooperating. Coercing here makes every emitted
    byte ASCII **by construction**, provable without a subprocess, and independent of the stream.
    """
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory: a finished plan must not hold its lock.")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    # parse_KNOWN_args: argparse exits 2 on an unrecognised flag, and `final_gate.py:265-269`
    # turns any non-zero exit from a warn_only check into a fleet-wide blocking red.
    args, _unknown = ap.parse_known_args(argv)
    _ascii_safe_stdout()
    root = Path(args.project_root)

    try:
        counters, findings, examined, evaluable, foreign = _collect(root)
        return _emit(args, counters, findings, examined, evaluable, foreign)
    except Exception as exc:  # never a traceback out of a warn_only check
        # The OUTPUT path is inside the guard too. An earlier revision guarded only `_collect`,
        # so a UnicodeEncodeError from the census separator escaped as rc=1 — which
        # `final_gate.py:262-270` converts into a blocking red across ~46 repos.
        try:
            # type name only — `repr(exc)` re-embeds the payload that may itself be unprintable.
            _say(f"could not evaluate plan locks: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken; stay silent, stay 0
            pass
        return 0


def _emit(args, counters, findings, examined, evaluable, foreign) -> int:
    # 30 of ~46 synced repos carry no lock dir at all. `warn_only` implies `advisory`, so
    # stdout prints on every pass — a block there would be permanent noise.

    real = [
        f
        for f in findings
        if f.label in ("STALE LOCK", "LIKELY STALE LOCK", "HALF-APPLIED FINISH", "PLAN FIELD STALE")
    ]
    # ⚠️ FINDINGS outranks NOTHING VERIFIED. The earlier ordering let `evaluable == 0` win, and
    # STALE LOCK / HALF-APPLIED FINISH / ORPHAN LOCK are all emitted on paths where evaluable is
    # False — so a run could print "1 stale" in the census and "nothing was verified, this is an
    # unasked question" on the very next line, with the finding, its detail and the remedy never
    # printed at all. The check found the exact defect it exists to find and swallowed it.
    verdict = "FINDINGS" if real else ("NOTHING VERIFIED" if evaluable == 0 else "OK")

    # `--json` is NEVER silenced: a machine consumer asked a question and is owed a parseable
    # payload. An earlier revision returned before this branch when `examined == 0`, so
    # `json.loads(stdout)` raised on ~30 lock-less repos and could not distinguish "no locks"
    # from "the check crashed" — while the code's own comment claimed the opposite.
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": verdict,
                    "examined": examined,
                    "evaluable": evaluable,
                    "counters": counters,
                    "findings": [
                        {"label": f.label, "lock": f.lock, "detail": f.detail} for f in findings
                    ],
                },
                indent=2,
            )
        )
        return 0

    # Nothing found AND nothing to say: stay silent on the HUMAN path. 11 of 16 lock-carrying
    # repos hold only terminal locks, so an all-zero census + "NOTHING VERIFIED" would print on
    # EVERY gate run there, forever — the fires-everywhere-so-gets-noqa'd failure this check's own
    # doc argues against for the no-lock-dir case. `--json` is NEVER silenced: a machine consumer
    # asked a question and is owed the payload. The distinction that matters is "nothing to
    # report" (silent) vs "something I could not evaluate" (loud), so any non-zero counter —
    # `unevaluable` included — still speaks.
    # FOREIGN is out of jurisdiction by construction, so a foreign-only corpus has nothing to
    # say: fabrik-lib holds 48 locks (7 foreign, 41 terminal) and printed two content-free lines
    # on every gate run because the earlier predicate counted `foreign` as content.
    #
    # ⚠️ BOTH clauses are load-bearing, and `evaluable == 0` is the one that keeps this honest.
    # An all-zero-counter run where `evaluable >= 1` is NOT "nothing to say" — it is the check
    # asking its question and getting a clean answer, and the spec's whole success contract is
    # that such a run STATES ITS DENOMINATOR. Silencing on the counters alone deleted the `OK -
    # 0 stale of N examined` line entirely; `test_ok_line_buckets_sum_to_examined` caught it.
    # `examined == 0` needs no separate guard: it implies both clauses.
    actionable = {k: v for k, v in counters.items() if k != "foreign"}
    if not any(actionable.values()) and evaluable == 0:
        return 0

    census = " | ".join(f"{counters[k]} {k.replace('_', '-')}" for k in LABELS)
    _say(census)  # FIRST, always all eight: final_gate truncates advisory output at 500 chars

    # ASCII throughout, and computed BEFORE printing so its length can be charged to the budget.
    if verdict == "NOTHING VERIFIED":
        verdict_line = (
            f"NOTHING VERIFIED - 0 of {examined} lock(s) were in an evaluable (non-terminal) "
            "state; this is an unasked question, not a pass"
        )
    elif verdict == "OK":
        # The three buckets must SUM to `examined`; an earlier form computed "terminal" as
        # examined - evaluable, which silently folded the 7 foreign repo-locks into it.
        verdict_line = (
            f"OK - 0 stale of {examined} plan lock(s) examined "
            f"({evaluable} non-terminal evaluated | "
            f"{examined - evaluable - foreign} terminal/unevaluable | {foreign} foreign)"
        )
        # ⚠️ `OK` is scoped to the FOUR findings, but the SELF-REPORTS print underneath it. A run
        # with a healthy active lock and one ORPHAN emitted `OK - 0 stale of 2 ...` immediately
        # above `ORPHAN LOCK: ghost.json`, and an operator scanning an advisory row stops reading at
        # `OK`. That is fail-silent-green — the exact class this check exists to close — occurring
        # inside the check. The word stays (nothing STALE was found, which is true), but it may
        # never stand alone when the check is also reporting something it could not resolve.
        n_self = sum(counters[k] for k in ("orphan", "unknown_status", "unevaluable"))
        if n_self:
            verdict_line += f" - but {n_self} lock(s) could NOT be resolved; see below"
    else:
        verdict_line = ""
    if verdict_line:
        _say(verdict_line)
    # Every finding prints, in EVERY verdict — including the self-reports under NOTHING VERIFIED.
    # EXCEPT `FOREIGN LOCK`: it is out of jurisdiction by construction, so a per-lock line would
    # print forever in the one repo that owns seven of them. It stays in the census, where the
    # count is the honest signal, and out of the line list, where it would be pure noise.
    shown = [f for f in findings if f.label != "FOREIGN LOCK"]
    # BOUND THE WHOLE BLOCK, not just each line. `final_gate.py:2114` ships advisory output as
    # `output[:500]` and `:387` prints 10 lines with NO ellipsis — so an unbounded list is silently
    # truncated mid-token and every finding after the cut simply vanishes. Measured before this:
    # the fleet's one finding-bearing repo emitted 662 chars and lost its second finding. Dropping
    # detail is acceptable; dropping the EXISTENCE of a finding is not, so the overflow is counted
    # and named.
    # Charge EVERY line that will be printed — the verdict line above, the overflow marker, and
    # the remedy trailer only if some finding actually carries one. The earlier arithmetic
    # reserved 169 chars for a remedy that often never printed (only STALE and LIKELY STALE set
    # one), so orphan- or half-apply-heavy repos collapsed findings into `... N more` with ~190
    # chars sitting unused; and it charged neither the marker nor the verdict line, measuring
    # 526 against the 500 cap.
    # `+ 1` per unconditional line: `print` appends a newline and `output[:500]` counts it. The
    # per-finding arithmetic below already charges its own (`len(line) + 1`); the census, the
    # verdict line and the remedy trailer did not, under-charging the block by 3 chars against a
    # cap the worst case already sits 9 chars beneath.
    # Computed, not guessed. A literal 52 was measured correct for n up to ~5 digits (48/49/50 at
    # n=5/95/950) but is an unstated bound: a magic number that silently under-charges once the
    # count grows a digit is exactly the class this budget keeps hitting.
    marker_cost = len(f"  ... {len(shown)} more finding(s) - run the check directly") + 1
    remedy_cost = len(_REMEDY) + 7 if any(f.remedy for f in shown) else 0
    budget = (
        _ADVISORY_BUDGET - (len(census) + 1) - (len(verdict_line) + 1) - remedy_cost - marker_cost
    )
    # `final_gate.py:387` prints TEN lines with no ellipsis — a SECOND cap, independent of chars.
    # Today the char budget makes it unreachable (measured: 40 findings still collapse to 5 lines,
    # because census + verdict eat ~260 of 500 and no finding line is shorter than ~90 chars), so
    # this is not a live defect. It is stated anyway because that safety is EMERGENT: raising
    # `_ADVISORY_BUDGET` alone would silently start dropping findings past line 10, with no ellipsis
    # and no marker, which is precisely the invisible-truncation failure the budget exists to stop.
    # Reserve THREE: the census, the verdict line, and the overflow marker — which is itself a
    # printed line. Charging only the first two emitted 11 lines against a 10-line cap, and the
    # line the gate drops with no ellipsis would have been the marker: the run would have looked
    # complete while silently withholding 22 findings. Caught by the cap's own test.
    line_budget = _MAX_LINES - 3 - (1 if remedy_cost else 0)
    emitted: list[str] = []
    emitted_findings: list[Finding] = []
    for f in shown:
        line = f"  {f.label}: {f.lock} {f.detail}".rstrip()
        if len(line) > _MAX_LINE:  # never let ONE finding eat the whole budget
            line = line[: _MAX_LINE - 1] + "..."
        if (budget - len(line) < 0 or len(emitted) >= line_budget) and emitted:
            _say(f"  ... {len(shown) - len(emitted)} more finding(s) - run the check directly")
            break
        _say(line)
        budget -= len(line) + 1
        emitted.append(line)
        emitted_findings.append(f)
    # The remedy prints ONCE, as a trailer. Repeating it per finding cost 140 chars each and blew
    # `final_gate.py:2114`'s `output[:500]` budget on the fleet's only finding-bearing repo today
    # (measured 662 chars, cut mid-token, second finding lost).
    #
    # ⚠️ Keyed on what was actually EMITTED, not on `shown`. Keyed on `shown`, a corpus of 9 ORPHANs
    # plus 1 STALE printed `-> the plan's OWNER releases it (Finish step 5)` under a visible list
    # containing no stale lock at all — the STALE line had been truncated away. The reader is then
    # told to take the wrong action on the findings they CAN see (an orphan is not released; its
    # plan cannot be found). Measured. The BUDGET still charges off `shown`, which over-reserves in
    # exactly this case — deliberate, like `marker_cost`: over-charging can only drop a finding we
    # already name in the marker, while under-charging silently truncates one mid-token.
    if any(f.remedy for f in emitted_findings):
        _say(f"  -> {_REMEDY}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
