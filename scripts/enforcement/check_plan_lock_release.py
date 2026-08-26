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
action — the plan's OWNER releases it per Finish step 5; if a run is confirmed dead the
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

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # bare-script invocation: final_gate.py:261 runs [PYTHON, path]
    sys.path.insert(0, str(_HERE))

try:
    from check_convergence import EXECUTED as _CANONICAL_EXECUTED
except Exception:  # pragma: no cover - fail soft; the legacy alternation still covers EXECUTED
    _CANONICAL_EXECUTED = None

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
_FENCE = re.compile(r"^[ \t]*(?:```|~~~).*?^[ \t]*(?:```|~~~)", re.M | re.S)
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
    ]
    ref = PlanRef(tried=[str(p.relative_to(root)) for _, p in branches])
    for loc, cand in branches:
        if cand.is_file():
            ref.location, ref.spine = loc, cand
            ref.status_value = status_value(_read(cand) or "")
            break
    else:
        # A plan-set DIRECTORY with no same-stem spine still tells us where the plan lives.
        for loc, d in (("live", plans / stem), ("archived", plans / "archived" / stem)):
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
    """Quote a plan's Status value, bounded. `final_gate.py:2092` ships advisory output as
    `output[:500]` and `:387` prints 10 lines — one real fleet status value is ~900 chars, so an
    unbounded quote silently truncates every finding after it."""
    v = " ".join((value or "").split())
    return v if len(v) <= limit else v[: limit - 1] + "…"


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
                f"not a plan lock (holder={data.get('holder')!r}) — not judged",
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
        findings.append(
            Finding(
                "ORPHAN LOCK",
                name,
                f"no plan resolves for stem {looked!r} (tried: {', '.join(ref.tried)})",
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
    ts = next((k for k in COMPLETION_TS if data.get(k)), None)
    if ts and not data.get("final_commit"):
        findings.append(
            Finding(
                "HALF-APPLIED FINISH",
                name,
                f"{ts}={data.get(ts)!r} with final_commit absent — "
                "Finish step 5 landed one field of three",
            )
        )

    # 6. A missed Finish step-6 repoint — reported only for non-terminal locks (35 of the
    #    fleet's 37 stale paths sit on terminal locks: dead history, and re-pointing a released
    #    lock destroys provenance).
    if not ref.field_resolved and ref.location != "missing":
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory: a finished plan must not hold its lock.")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    # parse_KNOWN_args: argparse exits 2 on an unrecognised flag, and `final_gate.py:265-269`
    # turns any non-zero exit from a warn_only check into a fleet-wide blocking red.
    args, _unknown = ap.parse_known_args(argv)
    root = Path(args.project_root)

    try:
        counters, findings, examined, evaluable, foreign = _collect(root)
    except Exception as exc:  # never a traceback out of a warn_only check
        print(f"could not evaluate plan locks: {exc!r}")
        return 0

    # 30 of ~46 synced repos carry no lock dir at all. `warn_only` implies `advisory`, so
    # stdout prints on every pass — a block there would be permanent noise.
    if examined == 0:
        return 0

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

    census = " · ".join(f"{counters[k]} {k.replace('_', '-')}" for k in LABELS)
    print(census)  # FIRST, always all eight: final_gate truncates advisory output at 500 chars
    if verdict == "NOTHING VERIFIED":
        print(
            f"NOTHING VERIFIED — 0 of {examined} lock(s) were in an evaluable (non-terminal) "
            "state; this is an unasked question, not a pass"
        )
    elif verdict == "OK":
        # The three buckets must SUM to `examined`; an earlier form computed "terminal" as
        # examined - evaluable, which silently folded the 7 foreign repo-locks into it.
        print(
            f"OK — 0 stale of {examined} plan lock(s) examined "
            f"({evaluable} non-terminal evaluated · "
            f"{examined - evaluable - foreign} terminal/unevaluable · {foreign} foreign)"
        )
    # Every finding prints, in EVERY verdict — including the self-reports under NOTHING VERIFIED.
    # EXCEPT `FOREIGN LOCK`: it is out of jurisdiction by construction, so a per-lock line would
    # print forever in the one repo that owns seven of them. It stays in the census, where the
    # count is the honest signal, and out of the line list, where it would be pure noise.
    for f in findings:
        if f.label == "FOREIGN LOCK":
            continue
        line = f"{f.label}: {f.lock} {f.detail}".rstrip()
        print(f"  {line}" + (f" — {f.remedy}" if f.remedy else ""))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
