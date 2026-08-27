#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_trigger_routing.py, scripts/final_gate.py | none
"""Every command's ADVERTISED trigger phrase must not route to a DIFFERENT command.

WHY THIS EXISTS
---------------
Each `/fabrik-*` command declares `TRIGGER — EN: "..."` in its description: the phrases an
operator can type to reach it. Nothing checked that the router agrees. Measured 2026-08-28 by
running all 71 advertised EN phrases through the live `skill_router.py`:

    21 resolved to the RIGHT command · 45 resolved NOWHERE · 5 resolved to a DIFFERENT command

The five mis-routes are the defect this check polices, and they were not random. Every one landed
on a command whose OWN description disclaims the phrase — "review this UI" and "review the epic or
ticket breakdown" both fell through to `fabrik-review`, whose SKIP clause literally reads
"Traycer artifact convergence (→ /fabrik-workflow-review), rendered-UI review (→ /design-review)".
The operator types a command's advertised phrase and is pointed at a gate that says it is not the
one. That is strictly worse than routing nowhere, and it is the same shape found auditing
`/fabrik-spec-review` (command 3 of 31) — which is why this is now a check and not a third audit.

WHAT IT IS NOT
--------------
It does **not** flag a phrase that routes NOWHERE. Routing nowhere is SAFE: the router's standing
failure mode is over-firing, not under-firing (its own KEYWORD_STEMS comments say so repeatedly),
and a stem added to chase recall is how a router starts hijacking unrelated prompts. The
nowhere-count is reported as a DENOMINATOR — a measured statistic, never a finding — so the gap
stays visible without pressuring anyone to close it with a loose pattern.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — a non-zero exit from a
`warn_only` check is a BLOCKING red across ~46 governance-synced repos.

HUB-ONLY. `commands/_sources/` does not exist in a project, so the check is silent there.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = REPO / "commands" / "_sources"
ROUTER = REPO / ".claude" / "hooks" / "skill_router.py"
SKILLS = Path.home() / ".claude" / "skills"

# The description line, then the EN trigger clause inside it, then each quoted phrase.
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.M)
_EN_RE = re.compile(r"TRIGGER\s*—\s*EN:\s*(.+?)(?:;\s*TR:|—|\bStage:)", re.S)
_PHRASE_RE = re.compile(r'"([^"]+)"')

# `fabrik-service-test` is the one command whose stem resolves DYNAMICALLY by project type, so it
# must be graded against a type it actually serves — grading it as `saas-skeleton` reports a
# mis-route that does not exist (reproduced while writing this check).
_HEADLESS_GRADE = {"fabrik-service-test": "python-api"}
_DEFAULT_GRADE = "saas-skeleton"

ADVISORY_BUDGET = 500
MAX_LINE = 200
MAX_LINES = 8
SCOPE_NOTE = (
    "sees whether an advertised phrase reaches its own command; cannot tell whether the phrase "
    "is one an operator would ever type, and deliberately does not grade phrases that route nowhere"
)
REMEDY = (
    "add a NARROW stem above the broad one in skill_router.py KEYWORD_STEMS (a noun from the "
    "target's own domain in the same clause as the verb), or change the advertised phrase"
)


def _load_router():
    """Import the live router, or return None. Never raises — a missing/broken router must not
    take a warn_only check to a non-zero exit in ~46 repos."""
    if not ROUTER.exists():
        return None
    try:
        import importlib.util  # noqa: PLC0415

        spec = importlib.util.spec_from_file_location("_sr_probe", ROUTER)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def advertised(sources: Path) -> list[tuple[str, str]]:
    """(command, phrase) for every advertised EN trigger."""
    out: list[tuple[str, str]] = []
    for path in sorted(sources.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        desc = _DESC_RE.search(text)
        if not desc:
            continue
        en = _EN_RE.search(desc.group(1))
        if not en:
            continue
        out.extend((path.stem, ph) for ph in _PHRASE_RE.findall(en.group(1)))
    return out


def grade(sources: Path, router, roster: set[str]) -> tuple[list[tuple[str, str, str]], int, int]:
    """(mis-routes, correct_count, nowhere_count)."""
    misrouted: list[tuple[str, str, str]] = []
    correct = nowhere = 0
    for cmd, phrase in advertised(sources):
        try:
            stem = router.first_regex_match(phrase)
            target = (
                router.resolve_target(stem, roster, _HEADLESS_GRADE.get(cmd, _DEFAULT_GRADE), True)
                if stem
                else None
            )
        except Exception:
            continue
        if target is None:
            nowhere += 1
        elif target == cmd:
            correct += 1
        else:
            misrouted.append((cmd, phrase, target))
    return misrouted, correct, nowhere


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--sources", default=str(SOURCES))
    parser.add_argument("--skills", default=str(SKILLS))
    # parse_known_args + the SystemExit guard: argparse exits 2 on a bad flag, and SystemExit
    # derives from BaseException, so `except Exception` would NOT catch it. That exact hole took a
    # warn_only check to a fleet-wide blocking red five times before it was named.
    try:
        args, _ = parser.parse_known_args(argv)
    except SystemExit:
        return 0

    sources = Path(args.sources)
    if not sources.is_dir():
        return 0  # a project: no command sources, nothing to grade
    router = _load_router()
    if router is None:
        return 0
    skills_dir = Path(args.skills)
    roster = {p.name for p in skills_dir.iterdir() if p.is_dir()} if skills_dir.is_dir() else set()
    if not roster:
        return 0  # no installed roster to resolve against; silent rather than wrong

    misrouted, correct, nowhere = grade(sources, router, roster)
    total = correct + nowhere + len(misrouted)
    if not total:
        return 0
    if not misrouted:
        print(
            _ascii(
                f"trigger routing: {total} advertised phrase(s) - {correct} reach their own "
                f"command, {nowhere} route nowhere, 0 mis-routed ({SCOPE_NOTE})"
            )
        )
        return 0

    head = (
        f"WARN trigger routing: {len(misrouted)} advertised phrase(s) reach a DIFFERENT command "
        f"(of {total}; {correct} correct, {nowhere} nowhere - not graded)"
    )
    marker_cost = len(f"\n  ... {len(misrouted)} more") if len(misrouted) > MAX_LINES else 0
    remedy = f"\n  -> {REMEDY}"
    budget = ADVISORY_BUDGET - len(head) - len(remedy) - marker_cost
    lines: list[str] = []
    for cmd, phrase, target in misrouted[:MAX_LINES]:
        row = f'  {cmd}: "{phrase}" -> {target}'
        if len(row) > MAX_LINE:
            row = row[: MAX_LINE - 3] + "..."
        if budget - len(row) - 1 < 0:
            break
        budget -= len(row) + 1
        lines.append(row)
    out = head + "".join("\n" + ln for ln in lines)
    if len(misrouted) > len(lines):
        out += f"\n  ... {len(misrouted) - len(lines)} more"
    print(_ascii(out + remedy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
