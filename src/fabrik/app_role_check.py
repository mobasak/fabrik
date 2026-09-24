"""Pre-cutover check for the ``<db>_app`` DSN cutover — spec § 2 "pre-cutover check".

Before ``.env``'s ``DATABASE_URL`` is switched from the owner DSN to the ``<db>_app``
role DSN (T04), this module answers two questions: (1) is the app role's privilege
model already correct (delegated to T02's :func:`~fabrik.drivers.postgres.probe_app_role`),
and (2) does anything in the project's own repo still reach the database as an owner —
running DDL, a migration tool, or a bare ``psql`` invocation — over ``DATABASE_URL``
instead of ``DATABASE_URL_OWNER``. A cutover is safe only when both answers are clean.

Scan patterns settled in D-390, widened by this plan's review (spec § Derivations D1):

* ``*.sql`` files are never scanned for DDL text — they are schema data applied by
  someone (``db/schema.sql`` is owner-applied by design). The scan finds the
  INVOCATION that applies them (a ``psql`` call, a compose ``migrate`` service)
  instead of the SQL text itself.
* An alembic ``env.py``'s own connection source is checked separately from the
  general pattern set, because ordinary application code reading ``DATABASE_URL``
  is expected and harmless — it is meant to follow the cutover. Alembic does not:
  it opens its own connection and runs DDL directly, so an ``env.py`` that still
  resolves its URL from ``DATABASE_URL`` (rather than ``DATABASE_URL_OWNER``) is a
  real pre-cutover risk.
* **Suppression is cheap to defeat on purpose, and that is the point.** A finding
  is suppressed only when the line itself (once a trailing ``#``/``--``/``//``
  comment is stripped) or the containing compose service's ``environment``/
  ``command`` names ``DATABASE_URL_OWNER`` as the connection source. Moving the
  same text into a comment is the cheapest way to make the check pass without
  changing which variable the code actually connects with, so a comment token
  never suppresses a finding — this is deliberate, not an oversight.
* Fail closed, never pass on nothing: a missing repo, a repo with zero walkable
  files, a stale clone (HEAD behind its upstream after ``git fetch``), or no
  upstream at all are each their own failure — a scan that found nothing because
  it looked at nothing, or at old code, must never read as a clean pass.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from fabrik.drivers.postgres import POSTGRES_CONTAINER, AppRoleError, probe_app_role

# ── What the scan walks / skips (spec § Derivations D1) ───────────────────── #

_SKIP_DIRS = {
    "tests",
    "test",
    ".venv",
    "venv",
    "node_modules",
    "libs",
    "dist",
    "build",
    ".claude",
    ".git",
}

_CODE_EXTENSIONS = {".py", ".ts", ".js", ".mjs", ".sh"}
_COMPOSE_GLOBS = ("compose.yaml", "compose.*.yaml", "docker-compose*.yml")


def _is_compose_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name, glob) for glob in _COMPOSE_GLOBS)


def _is_alembic_env(rel: Path) -> bool:
    """``env.py`` under any ``alembic/`` ancestor directory (not just a direct parent)."""
    return rel.name == "env.py" and "alembic" in rel.parts[:-1]


def _is_walkable(rel: Path) -> bool:
    name = rel.name
    if rel.suffix in _CODE_EXTENSIONS:
        return True
    if name == "Makefile":
        return True
    if _is_compose_file(name):
        return True
    if name.startswith("Dockerfile"):
        return True
    if name.lower().startswith("entrypoint"):
        return True
    if name == "package.json":
        return True
    return bool(_is_alembic_env(rel))


# ── Patterns (case-insensitive; spec § 2) ──────────────────────────────────── #

_LINE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "runtime DDL",
        re.compile(
            r"\b(create|alter|drop)\s+(unique\s+)?"
            r"(table|index|extension|view|function|schema|type|sequence)\b",
            re.IGNORECASE,
        ),
    ),
    ("create_all", re.compile(r"\bcreate_all\b", re.IGNORECASE)),
    ("op.create_table", re.compile(r"op\.create_table", re.IGNORECASE)),
    (".sync(", re.compile(r"\.sync\(", re.IGNORECASE)),
    ("alembic upgrade/downgrade", re.compile(r"\balembic\s+(upgrade|downgrade)\b", re.IGNORECASE)),
    ("prisma migrate/db push", re.compile(r"\bprisma\s+(migrate|db\s+push)\b", re.IGNORECASE)),
    ("drizzle-kit push", re.compile(r"\bdrizzle-kit\s+push\b", re.IGNORECASE)),
    ("manage.py migrate", re.compile(r"\bmanage\.py\s+migrate\b", re.IGNORECASE)),
    ("psql invocation", re.compile(r"\bpsql\b", re.IGNORECASE)),
]

# A trailing #, -- or // comment, stripped before both the pattern check and the
# suppression check — the marker itself is never treated as part of the code.
_COMMENT_RE = re.compile(r"(#|--|//).*$")
# `_` continues a \b word run, so this never matches inside DATABASE_URL_OWNER.
_OWNER_RE = re.compile(r"\bDATABASE_URL_OWNER\b")
_DATABASE_URL_TOKEN_RE = re.compile(r"\bDATABASE_URL\b")


def _strip_comment(line: str) -> str:
    return _COMMENT_RE.sub("", line, count=1)


@dataclass
class Finding:
    path: str
    line: int
    pattern: str


@dataclass
class ScanResult:
    files_scanned: int
    findings: list[Finding]


@dataclass
class CheckResult:
    ok: bool
    failures: list[str]


def _scan_lines(rel: Path, lines: list[str]) -> list[Finding]:
    posix = rel.as_posix()
    findings: list[Finding] = []
    for lineno, raw in enumerate(lines, start=1):
        stripped = _strip_comment(raw)
        if _OWNER_RE.search(stripped):
            continue
        for label, regex in _LINE_PATTERNS:
            if regex.search(stripped):
                findings.append(Finding(path=posix, line=lineno, pattern=label))
                break
    return findings


def _scan_alembic_env(rel: Path, lines: list[str]) -> list[Finding]:
    posix = rel.as_posix()
    findings: list[Finding] = []
    for lineno, raw in enumerate(lines, start=1):
        stripped = _strip_comment(raw)
        if _OWNER_RE.search(stripped):
            continue
        if _DATABASE_URL_TOKEN_RE.search(stripped):
            findings.append(
                Finding(
                    path=posix, line=lineno, pattern="alembic env.py DATABASE_URL connection source"
                )
            )
    return findings


def _service_block_range(lines: list[str], service_name: str) -> tuple[int, int]:
    """The 0-indexed [start, end) line range of one compose service's mapping body."""
    key_re = re.compile(rf'^(\s+)["\']?{re.escape(service_name)}["\']?\s*:')
    start = None
    indent = 0
    for i, line in enumerate(lines):
        m = key_re.match(line)
        if m:
            start = i
            indent = len(m.group(1))
            break
    if start is None:
        return 0, len(lines)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        cur_indent = len(line) - len(line.lstrip(" "))
        if cur_indent <= indent:
            end = j
            break
    return start, end


def _database_url_env_line(
    lines: list[str], start: int, end: int, environment: object
) -> int | None:
    """The line inside [start, end) that sets ``DATABASE_URL`` under ``environment:``, if any."""
    sets_it = False
    if isinstance(environment, dict) and "DATABASE_URL" in environment:
        sets_it = True
    elif isinstance(environment, list):
        sets_it = any(
            isinstance(item, str) and item.split("=", 1)[0].strip() == "DATABASE_URL"
            for item in environment
        )
    if not sets_it:
        return None
    line_re = re.compile(r"\bDATABASE_URL\s*[:=]")
    for j in range(start, end):
        if line_re.search(lines[j]):
            return j + 1
    return start + 1


def _scan_compose_structure(rel: Path, text: str) -> list[Finding]:
    """Service-shaped findings a line-by-line scan cannot see: a service NAMED
    ``migrate``, and a service that overrides ``DATABASE_URL`` under ``environment:``
    (that value wins over ``.env``, so a cutover of ``.env`` never reaches the
    container). Suppression here spans the whole service block's environment/command,
    not just the reported line — the spec's own wording for this site."""
    findings: list[Finding] = []
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return findings
    if not isinstance(doc, dict):
        return findings
    services = doc.get("services")
    if not isinstance(services, dict):
        return findings

    posix = rel.as_posix()
    lines = text.splitlines()
    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, dict):
            continue
        start, end = _service_block_range(lines, str(service_name))
        stripped_block = "\n".join(_strip_comment(ln) for ln in lines[start:end])
        if _OWNER_RE.search(stripped_block):
            continue  # this service's own environment/command names the owner DSN

        if service_name == "migrate":
            findings.append(
                Finding(path=posix, line=start + 1, pattern="compose service named migrate")
            )

        env_line = _database_url_env_line(lines, start, end, service_cfg.get("environment"))
        if env_line is not None:
            findings.append(
                Finding(path=posix, line=env_line, pattern="compose environment sets DATABASE_URL")
            )
    return findings


def _scan_file(rel: Path, text: str) -> list[Finding]:
    lines = text.splitlines()
    findings = _scan_lines(rel, lines)
    if _is_alembic_env(rel):
        findings.extend(_scan_alembic_env(rel, lines))
    if _is_compose_file(rel.name):
        findings.extend(_scan_compose_structure(rel, text))
    return findings


def scan_repo(repo_dir: Path) -> ScanResult:
    """Walk ``repo_dir`` for connection-owning sites that would break a cutover.

    Returns ``ScanResult(files_scanned=0, findings=[])`` when ``repo_dir`` does not
    exist or holds no walkable file — callers (namely :func:`run_check`) turn a zero
    ``files_scanned`` into a failure rather than a silent clean pass.
    """
    if not repo_dir.is_dir():
        return ScanResult(files_scanned=0, findings=[])

    findings: list[Finding] = []
    files_scanned = 0
    for root, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            rel = file_path.relative_to(repo_dir)
            if not _is_walkable(rel):
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_scanned += 1
            findings.extend(_scan_file(rel, text))
    return ScanResult(files_scanned=files_scanned, findings=findings)


# ── Pre-cutover gate: probe + scan + clone freshness, fail-closed ──────────── #


def _stale_clone_failure(repo_dir: Path) -> str | None:
    """A failure string when ``repo_dir``'s HEAD is behind (or missing) its upstream.

    Deploys pull the remote (core/30-ops.md § redeploy), so a stale hub clone would
    scan code that is no longer what gets deployed. ``None`` means the clone is
    current and has an upstream to compare against.
    """
    fetch = subprocess.run(
        ["git", "-C", str(repo_dir), "fetch", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if fetch.returncode != 0:
        return f"could not fetch upstream for {repo_dir}: {(fetch.stderr or fetch.stdout).strip()}"

    upstream_ref = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if upstream_ref.returncode != 0:
        return f"no upstream configured for {repo_dir}"

    head = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    upstream_sha = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "@{u}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if head.returncode != 0 or upstream_sha.returncode != 0:
        return f"could not resolve HEAD/upstream sha for {repo_dir}"

    head_sha = head.stdout.strip()
    up_sha = upstream_sha.stdout.strip()
    if head_sha != up_sha:
        return f"stale clone: HEAD {head_sha} != upstream {up_sha}"
    return None


def run_check(db_name: str, repo_dir: Path, container: str = POSTGRES_CONTAINER) -> CheckResult:
    """The full pre-cutover gate: T02's privilege probe plus this module's repo scan.

    Every failure source below is additive — a passing probe does not short-circuit
    a repo problem and vice versa, since either one alone must block the cutover.
    """
    failures: list[str] = []

    try:
        failures.extend(probe_app_role(db_name, container=container))
    except AppRoleError as exc:
        failures.append(str(exc))

    if not repo_dir.is_dir():
        failures.append(f"no repo at {repo_dir} — cannot scan")
    else:
        stale = _stale_clone_failure(repo_dir)
        if stale:
            failures.append(stale)

        result = scan_repo(repo_dir)
        if result.files_scanned == 0:
            failures.append(f"scanned 0 files under {repo_dir}")
        for finding in result.findings:
            failures.append(f"{finding.path}:{finding.line} {finding.pattern} reaches DATABASE_URL")

    return CheckResult(ok=not failures, failures=failures)


def _db_name_for_spec(spec: dict) -> str:
    """The registrar's db_name rule (mirrors ``DeploymentOrchestrator._provision_postgres``,
    ``src/fabrik/orchestrator/infrastructure.py``): ``depends.postgres`` wins when set,
    else the spec's name (falling back to id), hyphens rewritten to underscores —
    PostgreSQL identifiers don't allow hyphens without quoting."""
    configured = (spec.get("depends") or {}).get("postgres")
    derived = str(spec.get("name") or spec.get("id", "unknown")).replace("-", "_")
    return configured or derived


def project_repo_dir(spec: dict) -> Path:
    """``/opt/<id>`` — the orchestrator's ``_load_secrets`` precedence (id before name,
    ``src/fabrik/orchestrator/__init__.py``). Shared by the CLI and T04's registrar step."""
    return Path("/opt") / str(spec.get("id") or spec.get("name"))
