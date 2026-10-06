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
import functools
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

FABRIK_ROOT = Path(__file__).resolve().parents[1]
OPT = Path("/opt")
REPORT_DIR = FABRIK_ROOT / "docs" / "infrastructure" / "probe-reports"
TEMPLATE_DIR = FABRIK_ROOT / "templates" / "scaffold"


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
    # The TODO tokens a 2026-10-01 SERVICES seeding wrote into 15 repos (`[API — fill in]`,
    # `[purpose]`) — in no template, so the template rule cannot see them.
    re.compile(r"\[[^\]\n]*— fill in\]"),
    re.compile(r"\[purpose\]"),
)
# A doc left as its scaffold template (01M4664J): the template's OWN text is the sentinel, so the
# probe tracks whatever a template emits — a hand-picked token list missed an untouched OPERATIONS.md
# and every doc the scaffold seeds, because seeding substitutes `[Project Name]`/`YYYY-MM-DD`.
# A template line counts when it is >25 chars and carries none of the strings the scaffold
# substitutes at seed time (`SEED_SUBSTITUTED` is the union of src/fabrik/scaffold.py's seeding loops —
# a test reads those loops' AST and fails on drift). COBRA: a doc that rewords each template line
# trivially passes; the probe answers "was this template ever filled", never "is it true".
SEED_SUBSTITUTED: tuple[str, ...] = (
    "[Project Name]",
    "<project>",
    "project-name",
    "myproject",
    "[package_name]",
    "<package_name>",
    "<domain>",
    "YYYY-MM-DD",
    "[Brief description]",
    "[One-line description]",
    "Brief project description",
    "[PORT]",
)
# Registry docs whose template is a SHAPE the project keeps on purpose (append ledgers, indexes,
# the friction log) — measured 2026-10-05: every filled copy keeps 85-100% of its template's lines.
KEPT_SHAPE_DOCS = frozenset(
    {
        "CHANGELOG.md",
        "INDEX.md",
        "docs/README.md",
        "AFCL.md",
        "docs/DECISIONS.md",
        "docs/LESSONS_LEARNT.md",
        "docs/STRATEGIC_BACKLOG.md",
    }
)
# Measured 2026-10-05 over 44 repos: filled docs keep 0-48% of their template's lines, unfilled
# ones 49-98% (OPERATIONS 81-85, RESILIENCE 75-83, QUICKSTART 58-94, TROUBLESHOOTING 77-85).
TEMPLATE_LEFT_PCT = 50
# ...and the template must also be at least half of the DOC: measured 2026-10-05, the 16 docs that
# pass the first cut but are mostly their own text (e.g. a 664-line CONFIGURATION keeping the
# template's example blocks) carry 2-44% template lines; the 158 left as template carry 50-100%.
TEMPLATE_SHARE_PCT = 50
_HISTORY_NOTE = (
    "template history: unavailable (shallow or unreadable hub git) — only the current templates "
    "were compared, so a doc seeded from an older template version can read clean"
)
STALE_WARN_DAYS = 14  # a key doc this many days older than code = report row

# An inherited GIT_DIR/GIT_WORK_TREE (inside a git hook) would point `git -C <repo>` at the
# hook's repo instead — strip them so every git call reads the repo it names.
_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}


def _git_ts(repo: Path, *paths: str) -> int | None:
    """Unix timestamp of the last commit touching any of ``paths`` (0-arg = HEAD)."""
    cmd = ["git", "-C", str(repo), "log", "-1", "--format=%ct"]
    if paths:
        cmd += ["--", *paths]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20, check=False, env=_git_env()
        ).stdout
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


def _substantive_lines(text: str) -> set[str]:
    return {ln.strip() for ln in text.splitlines() if len(ln.strip()) > 25}


def _seed_lines(text: str) -> frozenset[str]:
    return frozenset(
        ln for ln in _substantive_lines(text) if not any(x in ln for x in SEED_SUBSTITUTED)
    )


def _git_out(*args: str) -> str:
    """stdout of ``git -C FABRIK_ROOT <args>``, '' on any failure (one call, one timeout)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(FABRIK_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_git_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


@functools.cache
def template_history_complete() -> bool:
    """True when the hub's full git history is readable — git present, FABRIK_ROOT is itself the
    work tree (a plain copy inside another repo would read THAT repo's history) and not shallow;
    else only the current templates are compared and the output says so."""
    top = _git_out("rev-parse", "--show-toplevel").strip()
    if not top or Path(top).resolve() != FABRIK_ROOT.resolve():
        return False
    return _git_out("rev-parse", "--is-shallow-repository").strip() == "false"


@functools.cache
def template_versions(template: str) -> tuple[frozenset[str], ...]:
    """The seed lines of templates/scaffold/<template> as it stands AND as every commit left it —
    a doc seeded from an older wording is still a template left unfilled (measured 2026-10-05:
    the current wording alone missed 5 DEPLOYMENT, 9 README and 16 CONFIGURATION docs that are
    95-100% an older version). Git unreadable → the current file alone."""
    rel = f"templates/scaffold/{template}"
    texts: list[str] = []
    try:
        texts.append((TEMPLATE_DIR / template).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        pass
    for sha in _git_out("log", "--format=%H", "--", rel).split():
        shown = _git_out("show", f"{sha}:{rel}")
        if shown:
            texts.append(shown)
    return tuple(dict.fromkeys(v for v in map(_seed_lines, texts) if v))


def templated_docs() -> list[tuple[str, str]]:
    """(project path, template) for every registry doc a project fills from a template."""
    try:
        sys.path.insert(0, str(FABRIK_ROOT / "scripts" / "enforcement"))
        import _doc_registry  # noqa: PLC0415

        rows = _doc_registry.PROJECT_DOCS
    except Exception:
        return []
    return [
        (r.name, r.template)
        for r in rows
        if r.template and r.fills in {"agent", "scaffold-stub"} and r.name not in KEPT_SHAPE_DOCS
    ]


def template_left_pct(text: str, template: str) -> int | None:
    """Highest percent of any template version's seed lines still verbatim in ``text``
    (None: the template has no such lines)."""
    versions = template_versions(template)
    if not versions:
        return None
    lines = _substantive_lines(text)
    return max(round(100 * len(v & lines) / len(v)) for v in versions)


def template_verdict(text: str, template: str) -> int | None:
    """``template_left_pct`` when the doc is left as its template — at least TEMPLATE_LEFT_PCT of
    a template version still in it AND template lines at least TEMPLATE_SHARE_PCT of the doc;
    else None. The second half keeps a long filled doc that kept a few template blocks (or a
    short old version's generic lines) from reading as a stub."""
    pct = template_left_pct(text, template)
    if pct is None or pct < TEMPLATE_LEFT_PCT:
        return None
    lines = _substantive_lines(text)
    every = frozenset().union(*template_versions(template))
    share = round(100 * len(lines & every) / len(lines)) if lines else 0
    return pct if share >= TEMPLATE_SHARE_PCT else None


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
    templates = dict(templated_docs())
    for rel in dict.fromkeys([*KEY_DOCS, *templates]):
        try:
            text = (project / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        pct = template_verdict(text, templates[rel]) if rel in templates else None
        n = stub_hits(text)
        if pct is not None:
            row.stubs.append(f"{Path(rel).name} (template text left: {pct}%)")
        elif n:
            row.stubs.append(f"{Path(rel).name} ({n})")
    return row


INDEX_PATH = FABRIK_ROOT / "INDEX.md"
# The anchor is matched by its LINK TARGET, never by link text or description — those are free to be
# edited by hand, and a prefix match on them fails into a cron log nobody reads (scoped review F2).
_LATEST_ANCHOR_RE = re.compile(
    r"^\|\s*\[[^\]]*\]\((?:\./)?docs/infrastructure/probe-reports/fleet-doc-audit-latest\.md\)"
)


def index_is_clean(root: Path) -> bool:
    """True iff INDEX.md matches HEAD — worktree AND index. `git diff --quiet -- INDEX.md` alone
    compares the worktree to the INDEX, so a sibling's STAGED-but-uncommitted edit read as clean
    and would have been swept into the cron's self-commit (scoped review F1, reproduced live)."""
    return (
        subprocess.run(
            ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", "INDEX.md"],
            check=False,
            timeout=30,
            env=_git_env(),
        ).returncode
        == 0
    )


def ensure_index_row(index_path: Path, dated_name: str, today: str) -> bool:
    """Index the dated report in INDEX.md — the generator owns its own INDEX row.

    THE CLASS THIS CLOSES (2026-09-02): every weekly run wrote a new dated report and
    never touched INDEX.md, so `check_doc_index` went red for whoever ran the next
    unrelated gate; three earlier reports had been indexed by hand after the fact.
    Inserts ONE row immediately before the `-latest` anchor row (the dated rows sit
    above it, as the hand-written ones already did). Idempotent: an existing row for
    `dated_name` → False, no write. No anchor → False, no write, loud stderr — never a
    silent partial edit of a shared file.
    """
    text = index_path.read_text(encoding="utf-8", errors="replace")
    if f"[{dated_name}](" in text:
        return False
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if _LATEST_ANCHOR_RE.match(ln):
            row = (
                f"| [{dated_name}](docs/infrastructure/probe-reports/{dated_name}) | "
                f"Dated fleet doc-freshness report ({today} cron run) |\n"
            )
            lines.insert(i, row)
            index_path.write_text("".join(lines), encoding="utf-8")
            return True
    print(
        f"WARN: INDEX.md has no fleet-doc-audit-latest anchor row — {dated_name} NOT indexed",
        file=sys.stderr,
    )
    return False


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
        *([_HISTORY_NOTE, ""] if not template_history_complete() else []),
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
        # INDEX.md is a SHARED file: only self-commit it if it was clean before we touched it —
        # otherwise a sibling's uncommitted INDEX edits would be swept into a cron commit.
        index_was_clean = index_is_clean(FABRIK_ROOT)
        indexed = ensure_index_row(INDEX_PATH, dated.name, today)
        commit_paths = [str(dated), str(latest)]
        if indexed and index_was_clean:
            commit_paths.append(str(INDEX_PATH))
        elif indexed:
            print(
                "WARN: INDEX.md row written but NOT self-committed — INDEX.md carried uncommitted "
                "changes before this run (a sibling's WIP); commit the row yourself",
                file=sys.stderr,
            )
        if commit:
            # Self-commit the report (daily_refresh precedent): a cron artifact
            # left untracked pollutes the shared tree for every next agent.
            # Pathspec-only — never touches anything else in the index.
            subprocess.run(
                ["git", "-C", str(FABRIK_ROOT), "add", "--", *commit_paths],
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
                    *commit_paths,
                ],
                check=False,
                timeout=30,
            )
    return 0  # advisory tool: the REPORT is the signal; non-zero = crash only


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stdout", action="store_true", help="print only — no report file")
    ap.add_argument("--commit", action="store_true", help="git-commit the report files (cron mode)")
    ap.add_argument(
        "--repo",
        type=Path,
        help="audit ONE project and print its row — no report (/fabrik-catchup)",
    )
    a = ap.parse_args()
    if a.repo:
        r = audit_project(a.repo.resolve())
        if r is None:
            print(f"{a.repo}: not a git repo with a docs/ directory — nothing audited")
            return 0
        print(f"project: {r.project}\nlag: {r.lag}d")
        for label, items in (("stale", r.stale), ("stubs", r.stubs), ("missing", r.missing)):
            print(f"{label}: {', '.join(items) or 'none'}")
        if not template_history_complete():
            print(_HISTORY_NOTE)
        return 0
    return run(write_report=not a.stdout, commit=a.commit)


if __name__ == "__main__":
    sys.exit(main())
