#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_certification_coverage.py | scripts/final_gate.py | docs/reference/certification-denominator.md | commands/_sources/fabrik-user-test.md | commands/_sources/fabrik-service-test.md | CLAUDE.md
"""Certification coverage gate — the grader the certification contract never had.

`/fabrik-user-test` and `/fabrik-service-test` enumerate an inventory and terminate when a round adds
nothing new. The inventory was PROSE WITH COUNTS, authored by the agent later graded against it, and
**nothing read it**: `scripts/enforcement/` graded reviews and unit tests and had no certification
grader at all. So the agent chose its own denominator and marked its own homework. On a surface the
project authored, its enumeration and reality converge and this never bites; on an INHERITED surface
it under-counts silently and the run terminates HONESTLY AND WRONG — a true statement about the wrong
denominator, which neither command can self-detect. Measured on tryton-crm immediately after a
genuine md5-verified `/fabrik-features` no-op: ~12 of ~1,700 surfaces would be exercised and the
gauntlet would report converged.

This check reads the generated CERT BOARD and grades it. Two verdict classes, and the distinction is
load-bearing:

* **ADVISORY (`warn_only`) — coverage quality.** Missing ledger, UNVISITED IDs, a bad disposition,
  a short generator. These land advisory fleet-wide so every project SEES its real fraction on
  landing day without a release freezing. Promotion to blocking is a separate operator decision.
* **BLOCKING from day one — the anti-mix-up guard.** A cert board carrying `## Ticket Board`, or a
  cert lock written to `.fabrik/plan-locks/`, is NOT a coverage-quality problem: it is a board that
  `/fabrik-execute-plan` will dispatch to CODING agents (its detection triggers on the bare heading
  string, `fabrik-execute-plan.md:34-38`) holding a lock `final_gate_stop.py:785` believes in. The
  operator's advisory ruling covered coverage completeness, never a wrong-agent dispatch, and a
  warn-only safety guard is one nobody reads until after the damage.

⚠️ **Exit 0 on EVERY path**, including this module's own guard. `final_gate.py:198-208` converts a
non-zero exit from a `warn_only` check into a **blocking red fleet-wide** — `check_plan_lock_release`
hit that class five times during its build. The blocking verdict above is expressed by the gate row
being non-advisory, never by a non-zero exit from this file.

CLI: `--project-root PATH` (default cwd) · `--json`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ── the namespace separation, in one place ──────────────────────────────────────────────────────
# Each of these differs DELIBERATELY from its implementation-plan counterpart so a cert board is
# never mistaken for a plan-set. The heading is the load-bearing one: /fabrik-execute-plan's
# dispatcher detection triggers on the bare string `## Ticket Board` regardless of directory.
CERT_DIR = ("docs", "development", "certifications")
CERT_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-cert-[a-z0-9-]+$")
TICKET_FILE_RE = re.compile(r"^TC\d{2}[a-z]?-[a-z0-9-]+\.md$")
BOARD_HEADING = "## Test Board"
FORBIDDEN_HEADING = "## Ticket Board"
CERT_LOCK_DIR = (".fabrik", "cert-locks")
FORBIDDEN_LOCK_DIR = (".fabrik", "plan-locks")

# EXERCISED or OUT-OF-SCOPE(reason). `DEFERRED` is REJECTED (operator, 2026-08-27: "i dont accept
# deferred ... as like a real qc engineer all functionality must be tested"). A "later" disposition
# is the loophole that lets the whole contract be ignored: the tail that most needs generating is
# exactly the tail that gets deferred.
TERMINAL = frozenset({"EXERCISED", "OUT-OF-SCOPE"})
REJECTED_DISPOSITIONS = frozenset({"DEFERRED", "SKIPPED", "TODO", "PENDING", "WONTFIX"})
UNVISITED = "UNVISITED"

# Deleting DEFERRED moved the hole; it did not close it. OUT-OF-SCOPE was graded on one thing — a
# non-empty reason — so 1,688 OUT-OF-SCOPE(inherited vendor surface) + 12 EXERCISED would report
# CONVERGED: the tryton-crm scenario verbatim with a different word in the column. Every reason
# below describes how OUR surface came to exist, not whether a customer can click it; inherited
# surfaces are precisely what the T3 generated-smoke tier is for.
REJECTED_REASONS = (
    "inherited",
    "vendored",
    "vendor code",
    "third-party code",
    "third party code",
    "generated",
    "legacy",
    "low priority",
    "low-priority",
    "not ours",
    "out of time",
    "too many",
    "too hard",
    "later",
)

RUNNERS = frozenset({"gui", "service", "generated-smoke", "fix"})

# ── Phase B: where a project DECLARES its denominator source ────────────────────────────────────
# The hub must not INFER the registry. A project declares it in `project.yaml`, copying the shipped
# precedent `has_user_guide` — a project.yaml flag that arms `check_user_guide.py` (":7-8": pass when
# the flag is false/absent, fail when declared-but-missing). NOT `spec_loader.py::Shape`, which
# "declares what the project IS ... which infrastructure registrars are applicable" (:205-215) — a
# certification denominator is not an infrastructure registrar.
DECLARATION_KEY = "certification_registry"

# Per-scaffold-type DEFAULT when nothing is declared. Adopted from the tryton-crm proposal, which
# grounded it. An undeclared source falls back here AND the fallback is RECORDED — a
# declared-and-justified fallback is auditable, an inferred one is not.
# `wordpress` is absent on purpose: it is a dead legacy string in SCAFFOLD_TYPES (scaffold.py:146,
# with :5783 raising NotImplementedError) and we ship zero WordPress projects. It is a crash guard,
# never a product surface — and a sibling check that iterated SCAFFOLD_TYPES and let that
# NotImplementedError escape reddened ~46 repos.
REGISTRY_BY_TYPE: dict[str, str] = {
    "python-api": "live route table (FastAPI app.routes) or the emitted OpenAPI",
    "python-api-gpu": "live route table (FastAPI app.routes) or the emitted OpenAPI",
    "node-api": "live route table (Express _router.stack) or the emitted OpenAPI",
    "file-api": "live route table or the emitted OpenAPI",
    "saas-skeleton": "live route table; if it wraps a vendored platform, THAT platform's registry",
    "file-worker": "the task/beat registry — registered job names + schedules",
    "static-site": "sitemap.xml / the build manifest",
    "docusaurus": "sitemap.xml / the build manifest",
    "chrome-extension": "the MV3 manifest — popup, options, content-script matches, commands",
    "mobile-app": "the navigator route tree",
    "desktop-app": "the window + application-menu registry",
}
RETIRED_TYPES = frozenset({"wordpress"})
# A denominator that resolves to a DOC is the original defect: FEATURES.md documents what the
# project BUILT; certification must cover what the product SHIPS.
DOC_SOURCES = ("features.md", "docs/", "readme", "changelog", "prose", "doc:")
_ADVISORY_BUDGET = 500
_MAX_LINE = 220
_MAX_LINES = 10


class Finding:
    __slots__ = ("label", "detail", "blocking")

    def __init__(self, label: str, detail: str, *, blocking: bool = False) -> None:
        self.label, self.detail, self.blocking = label, detail, blocking


def _say(line: str) -> None:
    """The only print. ASCII by construction — a ledger carries LLM- and web-sourced text, and under
    an ASCII stdout an unguarded print raises mid-block, losing the finding while the census already
    printed (measured on a sibling check: indistinguishable from a clean run)."""
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


def _cell(v: Any) -> str:
    return str(v if v is not None else "").strip()


def parse_board(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse the `## Test Board` markdown table into rows. Returns (rows, problems)."""
    problems: list[str] = []
    if BOARD_HEADING not in text:
        problems.append(f"no `{BOARD_HEADING}` section")
        return [], problems
    body = text.split(BOARD_HEADING, 1)[1].split("\n## ", 1)[0]
    rows: list[dict[str, str]] = []
    header: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not header:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(dict(zip(header, cells, strict=False)))
    return rows, problems


def evaluate(root: Path) -> tuple[list[Finding], dict[str, int]]:
    """Grade every cert board under the project. Never raises for a data reason."""
    findings: list[Finding] = []
    counters = {
        "boards": 0,
        "ids": 0,
        "exercised": 0,
        "out_of_scope": 0,
        "unvisited": 0,
        "rejected": 0,
        "unrouted": 0,
        "mixup": 0,
    }

    # ── BLOCKING guard 1: a cert lock must never sit in the plan-lock dir ──────────────────────
    plan_locks = root.joinpath(*FORBIDDEN_LOCK_DIR)
    if plan_locks.is_dir():
        for lf in sorted(plan_locks.glob("*.json")):
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            # ⚠️ Precise, not a substring. `"cert" in plan` flagged this very plan's OWN lock
            # (`...-plan-1-certification-denominator.json`) on the first smoke run: an
            # implementation plan ABOUT certification is not a cert board. A cert lock is one whose
            # `plan` points INTO the certifications tree, or that says so explicitly.
            plan_val = str(data.get("plan", "")).replace("\\", "/")
            is_cert = "/".join(CERT_DIR) in plan_val or str(data.get("kind", "")).lower() == "cert"
            if is_cert:
                counters["mixup"] += 1
                findings.append(
                    Finding(
                        "MIXUP",
                        f"{lf.name} is a CERT lock in .fabrik/plan-locks/ — it must live in "
                        f".fabrik/cert-locks/; check_phase_tests.py:36 and final_gate_stop.py:785 read "
                        f"the plan-lock dir and would arm the Stop hook as if source were being written",
                        blocking=True,
                    )
                )

    cert_root = root.joinpath(*CERT_DIR)
    if not cert_root.is_dir():
        return findings, counters

    for board_dir in sorted(p for p in cert_root.iterdir() if p.is_dir()):
        if not CERT_DIR_NAME_RE.match(board_dir.name):
            findings.append(
                Finding("BAD DIR", f"{board_dir.name} is not YYYY-MM-DD-cert-<surface>")
            )
            continue
        counters["boards"] += 1
        spine = board_dir / f"{board_dir.name}.md"
        if not spine.is_file():
            findings.append(Finding("NO SPINE", f"{board_dir.name} has no same-stem spine"))
            continue
        try:
            text = spine.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            findings.append(Finding("UNREADABLE", f"{spine.name}: {type(exc).__name__}"))
            continue

        # ── BLOCKING guard 2: the heading is what stops the dispatcher claiming this board ─────
        if FORBIDDEN_HEADING in text:
            counters["mixup"] += 1
            findings.append(
                Finding(
                    "MIXUP",
                    f"{board_dir.name} carries `{FORBIDDEN_HEADING}` — /fabrik-execute-plan's "
                    f"dispatcher triggers on that bare string and would dispatch this TEST board to "
                    f"CODING agents. Use `{BOARD_HEADING}`.",
                    blocking=True,
                )
            )

        for tf in sorted(board_dir.glob("*.md")):
            if tf.name == spine.name or tf.name == "ledger.md":
                continue
            if not TICKET_FILE_RE.match(tf.name):
                findings.append(
                    Finding(
                        "BAD TICKET",
                        f"{tf.name} is not TC##[a-z]?-<slug>.md (T## is the "
                        f"IMPLEMENTATION namespace)",
                    )
                )

        rows, problems = parse_board(text)
        for p in problems:
            findings.append(Finding("BAD BOARD", f"{board_dir.name}: {p}"))

        for row in rows:
            tid = _cell(row.get("id") or row.get("ticket"))
            if not tid:
                continue
            counters["ids"] += 1
            disp_raw = _cell(row.get("disposition") or row.get("state"))
            runner = _cell(row.get("runner")).lower()
            disp = disp_raw.split("(", 1)[0].strip().upper()
            reason = disp_raw.split("(", 1)[1].rstrip(")").strip() if "(" in disp_raw else ""

            if runner not in RUNNERS:
                counters["unrouted"] += 1
                findings.append(
                    Finding(
                        "NO RUNNER",
                        f"{tid}: Runner={runner or '(none)'} not in "
                        f"{sorted(RUNNERS)} — the dispatcher's default unit is a CODER, so an unrouted "
                        f"test ticket puts a coding agent on a browser job",
                    )
                )

            if disp in REJECTED_DISPOSITIONS:
                counters["rejected"] += 1
                findings.append(
                    Finding(
                        "REJECTED DISPOSITION",
                        f"{tid}: {disp} is not a terminal disposition — "
                        f"every ID is EXERCISED or OUT-OF-SCOPE(reason). A 'later' state is the "
                        f"loophole that lets the contract be ignored.",
                    )
                )
            elif disp == UNVISITED or not disp:
                counters["unvisited"] += 1
                findings.append(Finding("UNVISITED", f"{tid}: not terminal — blocks the close"))
            elif disp == "EXERCISED":
                counters["exercised"] += 1
                ev = _cell(row.get("evidence"))
                if not ev or ev in {"-", "—"}:
                    findings.append(
                        Finding("NO EVIDENCE", f"{tid}: EXERCISED with no evidence path")
                    )
                elif not (board_dir / ev).exists() and not (root / ev).exists():
                    findings.append(
                        Finding(
                            "EVIDENCE MISSING",
                            f"{tid}: evidence {ev!r} does not exist on disk — the "
                            f"strongest mechanical proxy for 'the assertion was real'",
                        )
                    )
            elif disp == "OUT-OF-SCOPE":
                counters["out_of_scope"] += 1
                low = reason.lower()
                if not reason:
                    findings.append(
                        Finding(
                            "NO REASON",
                            f"{tid}: OUT-OF-SCOPE with no reason — a bare disposition is "
                            f"not a justification",
                        )
                    )
                elif any(r in low for r in REJECTED_REASONS):
                    findings.append(
                        Finding(
                            "BAD REASON",
                            f"{tid}: OUT-OF-SCOPE({reason[:60]}) describes how OUR "
                            f"surface came to exist, not whether a customer can click it — inherited "
                            f"surfaces are what the T3 generated-smoke tier is FOR",
                        )
                    )
            else:
                counters["unvisited"] += 1
                findings.append(Finding("UNKNOWN DISPOSITION", f"{tid}: {disp!r}"))

    # ── Phase B: the ledger's SOURCE must be a registry, and a short generator must be caught ──
    for board_dir in sorted(p for p in cert_root.iterdir() if p.is_dir()):
        ledger = board_dir / "ledger.md"
        if not ledger.is_file():
            findings.append(
                Finding(
                    "NO LEDGER",
                    f"{board_dir.name}: no ledger.md beside the board — the denominator "
                    f"must archive WITH the board it graded, or a later auditor has the verdict "
                    f"without the question",
                )
            )
            continue
        try:
            lt = ledger.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            findings.append(Finding("UNREADABLE", f"ledger.md: {type(exc).__name__}"))
            continue
        src = ""
        for line in lt.splitlines():
            if line.lower().startswith(("source:", "- source:", "**source:**")):
                src = line.split(":", 1)[1].strip().strip("*` ")
                break
        if not src:
            findings.append(
                Finding(
                    "NO SOURCE",
                    f"{board_dir.name}: ledger declares no `source:` — the denominator "
                    f"must name the registry it came from",
                )
            )
        elif any(d in src.lower() for d in DOC_SOURCES):
            findings.append(
                Finding(
                    "DOC DENOMINATOR",
                    f"{board_dir.name}: source {src!r} is a DOC. FEATURES.md "
                    f"documents what the project BUILT; certification must cover what it SHIPS. The "
                    f"doc inventory is a cross-check, never the denominator.",
                )
            )
        # A generator that under-enumerates CONSISTENTLY defeats the close-time diff, because both
        # enumerations come from the same generator and a short list agrees with itself.
        m_tot = re.search(r"registry_total:\s*(\d+)", lt)
        m_enum = re.search(r"ids_enumerated:\s*(\d+)", lt)
        if not m_tot or not m_enum:
            findings.append(
                Finding(
                    "NO RAW COUNT",
                    f"{board_dir.name}: ledger must record `registry_total:` (counted "
                    f"straight from the registry) AND `ids_enumerated:` — without both, a consistently "
                    f"short generator agrees with itself and the close-time diff is empty",
                )
            )
        elif int(m_tot.group(1)) != int(m_enum.group(1)):
            findings.append(
                Finding(
                    "SHORT GENERATOR",
                    f"{board_dir.name}: registry_total={m_tot.group(1)} but "
                    f"ids_enumerated={m_enum.group(1)} — the generator did not enumerate what it "
                    f"counted. Fail LOUD, never a silently short list.",
                )
            )

    # The 1,688/12 split must be impossible to hide behind a converged verdict.
    if counters["out_of_scope"] > counters["exercised"] and counters["ids"]:
        findings.append(
            Finding(
                "MOSTLY OUT-OF-SCOPE",
                f"{counters['out_of_scope']} out-of-scope vs {counters['exercised']} exercised — a "
                f"product that is mostly out of scope is a claim about the product; it needs an "
                f"explicit operator acknowledgement, not a silent CONVERGED",
            )
        )
    return findings, counters


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Advisory: certification coverage against the board.")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    # parse_KNOWN_args: argparse exits 2 on an unrecognised flag, and final_gate.py:198-208 turns
    # any non-zero exit from a warn_only check into a fleet-wide blocking red.
    args, _unknown = ap.parse_known_args(argv)
    try:
        sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - very old/exotic streams
        pass

    try:
        findings, counters = evaluate(Path(args.project_root))

        if args.json:
            _say(
                json.dumps(
                    {
                        "counters": counters,
                        "blocking": sum(1 for f in findings if f.blocking),
                        "findings": [
                            {"label": f.label, "detail": f.detail, "blocking": f.blocking}
                            for f in findings
                        ],
                    },
                    indent=2,
                )
            )
            return 0

        if not counters["boards"] and not findings:
            return 0  # no cert board here — silent, like every other advisory on a repo it does not apply to

        census = " | ".join(
            f"{counters[k]} {k.replace('_', '-')}"
            for k in (
                "boards",
                "ids",
                "exercised",
                "out-of-scope".replace("-", "_"),
                "unvisited",
                "rejected",
                "unrouted",
                "mixup",
            )
        )
        _say(census)
        blocking = [f for f in findings if f.blocking]
        if blocking:
            _say(
                "⚠ MIX-UP (BLOCKING, not advisory): a cert board that looks like an "
                "implementation plan gets dispatched to CODING agents"
            )
        budget = _ADVISORY_BUDGET - len(census) - 60
        shown = blocking + [f for f in findings if not f.blocking]
        # A LIST, not a counter — `emitted` tracks lines actually printed, not loop iterations, so
        # `enumerate` would be semantically wrong here (SIM113 is a false positive on that shape).
        # This mirrors check_plan_lock_release.py, which the plan named as the shape to copy.
        emitted: list[str] = []
        for f in shown:
            line = f"  {f.label}: {f.detail}"
            if len(line) > _MAX_LINE:
                line = line[: _MAX_LINE - 3] + "..."
            if (budget - len(line) < 0 or len(emitted) >= _MAX_LINES - 3) and emitted:
                _say(f"  ... {len(shown) - len(emitted)} more - run the check directly")
                break
            _say(line)
            budget -= len(line) + 1
            emitted.append(line)
        return 0
    except Exception as exc:  # never a traceback out of a warn_only check
        try:
            # type name only — repr(exc) can re-embed an unprintable payload and fail in turn.
            _say(f"could not evaluate certification coverage: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken; stay silent, stay 0
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
