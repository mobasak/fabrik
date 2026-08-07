#!/usr/bin/env python3
# AFTER-EDIT: tests/test_fleet_doc_audit.py | none
"""Fleet-wide doc-freshness audit — the MECHANICAL rot detector for /opt projects.

Why this exists: every doc gate (check_doc_sync, check_doc_index, stubs) fires only
inside a working session's gate run — a project nobody commits to has ZERO doc
enforcement, and touch-on-change proves presence, never truth. This audit closes the
untouched-project gap with cheap mechanical probes (no LLM):

  1. LAG   — last code commit newer than last docs/CHANGELOG commit (days).
  2. STALE — a key doc's last commit older than the last code commit (per-doc days).
  3. STUBS — unfilled template sentinels ([Project Name], [TBD], literal YYYY-MM-DD)
             still present in seeded docs.
  4. MISSING — a doc the registry's type bucket obligates that does not exist.

Output: a dated markdown report under docs/infrastructure/probe-reports/ (plus a
-latest copy) and a one-screen stdout summary. Read-only over every project tree.
Truth-level auditing stays with /fabrik-docs-review + /fabrik-doc-converge — this
script tells the operator WHERE to point them.

Usage:
    python scripts/fleet_doc_audit.py            # full fleet, write report
    python scripts/fleet_doc_audit.py --stdout   # no report file (cron log mode)

Cron: weekly (see crontab — Monday 06:30).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

FABRIK_ROOT = Path(__file__).resolve().parents[1]
OPT = Path("/opt")
REPORT_DIR = FABRIK_ROOT / "docs" / "infrastructure" / "probe-reports"


# Exclusions come from sync_projects.py ITSELF (imported, never hand-copied — a
# hand-copied set drifted within hours of shipping and silently hid the real
# project Reference_Creator from the first audit). The hub repo is added here:
# its docs are governed by its own gates, not this fleet probe.
# Retirement mechanism: a retired project is MOVED to /opt/archived/<name>
# (wpf + captcha, 2026-08-07) — the location itself excludes it from this scan,
# so there is deliberately NO name-list here: a hardcoded set would be dead
# code today and a silent-exclusion trap if a project were ever un-archived.


def _excluded(name: str) -> bool:
    sys.path.insert(0, str(FABRIK_ROOT / "scripts"))
    try:
        import sync_projects  # noqa: PLC0415

        return name == "fabrik" or sync_projects._is_excluded(name)
    except Exception:
        return name in {"fabrik", "fabrik-lib", "archived", "google", "containerd"}


CODE_PATHS = ("src", "app", "web", "lib", "scripts")
KEY_DOCS = (
    "docs/SERVICES.md",
    "docs/RESILIENCE.md",
    "docs/CONFIGURATION.md",
    "docs/DEPLOYMENT.md",
    "docs/FEATURES.md",
)
# Sentinels a filled doc must not carry (template placeholders).
_STUB_RES = (
    re.compile(r"\[Project Name\]"),
    re.compile(r"\[TBD[^\]]*\]"),
    re.compile(r"^\*\*Last Updated:\*\* YYYY-MM-DD", re.M),
)
STALE_WARN_DAYS = 14  # a key doc this many days older than code = report row


def _git_ts(repo: Path, *paths: str) -> int | None:
    """Unix timestamp of the last commit touching any of ``paths`` (0-arg = HEAD)."""
    cmd = ["git", "-C", str(repo), "log", "-1", "--format=%ct"]
    if paths:
        cmd += ["--", *paths]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False).stdout
    except Exception:
        return None
    out = out.strip()
    return int(out) if out.isdigit() else None


def lag_days(code_ts: int | None, docs_ts: int | None) -> int:
    """Whole days the code commit leads the docs commit (0 when docs keep up)."""
    if code_ts is None:
        return 0
    return max(0, (code_ts - (docs_ts or 0)) // 86400)


def stub_hits(text: str) -> int:
    """Count of unfilled template sentinels in one doc's text."""
    return sum(len(r.findall(text)) for r in _STUB_RES)


@dataclass
class Row:
    project: str
    lag: int = 0
    stale: list[str] = field(default_factory=list)  # "SERVICES.md (21d)"
    stubs: list[str] = field(default_factory=list)  # "FEATURES.md (3)"
    missing: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.lag or self.stale or self.stubs or self.missing)


def _required_docs(project: Path) -> list[str]:
    """Registry-obligated key docs for this project's type (best-effort; [] on any gap)."""
    try:
        sys.path.insert(0, str(FABRIK_ROOT / "scripts" / "enforcement"))
        import _doc_registry  # noqa: PLC0415

        ptype = ""
        py = project / "project.yaml"
        if py.is_file():
            m = re.search(r"^type:\s*([a-z0-9-]+)", py.read_text(encoding="utf-8"), re.M)
            ptype = m.group(1) if m else ""
        if not ptype:
            return []
        allow = _doc_registry.docs_allowlist(ptype)
        # The allowlist carries BARE basenames; KEY_DOCS are docs/-prefixed paths —
        # compare basenames or this probe is dead code (live defect, first ship).
        return [d for d in KEY_DOCS if Path(d).name in allow]
    except Exception:
        return []


def audit_project(project: Path) -> Row | None:
    if not (project / ".git").exists() or not (project / "docs").is_dir():
        return None
    row = Row(project=project.name)
    code_ts = _git_ts(project, *CODE_PATHS)
    if code_ts is None:
        # Code outside the standard dirs (or none): fall back to HEAD so an
        # active repo can never read as vacuously clean (fail-visible).
        code_ts = _git_ts(project)
    docs_ts = _git_ts(project, "docs", "CHANGELOG.md")
    if docs_ts is None and code_ts is not None:
        # docs/ never committed at all — its own failure mode, not an
        # epoch-sized lag number (mirrors the per-doc "(untracked)" branch).
        row.stale.append("docs+CHANGELOG (never committed)")
        row.lag = 0
    else:
        row.lag = lag_days(code_ts, docs_ts)
    required = _required_docs(project)
    for rel in KEY_DOCS:
        f = project / rel
        if not f.is_file():
            if rel in required:
                row.missing.append(rel)
            continue
        doc_ts = _git_ts(project, rel)
        if doc_ts is None:
            # On disk but zero git history — never committed is its own failure mode,
            # not an epoch-sized staleness number.
            row.stale.append(f"{Path(rel).name} (untracked)")
        else:
            d = lag_days(code_ts, doc_ts)
            if d >= STALE_WARN_DAYS:
                row.stale.append(f"{Path(rel).name} ({d}d)")
        try:
            n = stub_hits(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            n = 0
        if n:
            row.stubs.append(f"{Path(rel).name} ({n})")
    return row


def run(write_report: bool = True, commit: bool = False) -> int:
    rows: list[Row] = []
    for p in sorted(OPT.iterdir()):
        if not p.is_dir() or p.name.startswith((".", "_")) or _excluded(p.name):
            continue
        r = audit_project(p)
        if r is not None:
            rows.append(r)
    dirty = [r for r in rows if not r.clean]
    dirty.sort(key=lambda r: (-(r.lag), -len(r.stale) - len(r.missing)))

    today = _dt.date.today().isoformat()
    lines = [
        f"# Fleet doc-freshness audit — {today}",
        "",
        f"Projects scanned: {len(rows)} · flagged: {len(dirty)} · clean: {len(rows) - len(dirty)}",
        "",
        "Mechanical probes only (lag/stale/stubs/missing) — truth-level fixes are",
        "`/fabrik-docs-review` or `/fabrik-doc-converge <doc>` run IN the flagged project.",
        "",
        "| Project | Code-vs-docs lag | Stale key docs (≥14d behind code) | Stub sentinels | Missing obligated |",
        "|---|---|---|---|---|",
    ]
    for r in dirty:
        lines.append(
            f"| {r.project} | {r.lag}d | {', '.join(r.stale) or '—'} | "
            f"{', '.join(r.stubs) or '—'} | {', '.join(r.missing) or '—'} |"
        )
    if not dirty:
        lines.append("| _fleet clean_ | — | — | — | — |")
    report = "\n".join(lines) + "\n"

    print(report)
    if write_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        dated = REPORT_DIR / f"fleet-doc-audit-{today}.md"
        latest = REPORT_DIR / "fleet-doc-audit-latest.md"
        dated.write_text(report, encoding="utf-8")
        latest.write_text(report, encoding="utf-8")
        print(f"report: docs/infrastructure/probe-reports/fleet-doc-audit-{today}.md")
        if commit:
            # Self-commit the report (daily_refresh precedent): a cron artifact
            # left untracked pollutes the shared tree for every next agent.
            # Pathspec-only — never touches anything else in the index.
            subprocess.run(
                ["git", "-C", str(FABRIK_ROOT), "add", "--", str(dated), str(latest)],
                check=False,
                timeout=30,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(FABRIK_ROOT),
                    "commit",
                    "-m",
                    f"chore(fleet): weekly doc-freshness audit report ({today})\n\n"
                    "Agent-Role: primary\n"
                    "Agent-Context: fleet_doc_audit.py cron self-commit (mechanical report only)",
                    "--",
                    str(dated),
                    str(latest),
                ],
                check=False,
                timeout=30,
            )
    return 0  # advisory tool: the REPORT is the signal; non-zero = crash only


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stdout", action="store_true", help="print only — no report file")
    ap.add_argument("--commit", action="store_true", help="git-commit the report files (cron mode)")
    a = ap.parse_args()
    return run(write_report=not a.stdout, commit=a.commit)


if __name__ == "__main__":
    sys.exit(main())
