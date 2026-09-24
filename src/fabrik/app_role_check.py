"""Pre-cutover check for the ``<db>_app`` DSN cutover — spec § 2 "pre-cutover check".

Before ``.env``'s ``DATABASE_URL`` is switched from the owner DSN to the ``<db>_app``
role DSN (T04), this module answers two questions: (1) is the app role's privilege
model already correct (delegated to T02's :func:`~fabrik.drivers.postgres.probe_app_role`),
and (2) does anything in the project's own repo still reach the database as an owner —
running DDL, a migration tool, or a bare ``psql`` invocation — over ``DATABASE_URL``
instead of ``DATABASE_URL_OWNER``. A cutover is safe only when both answers are clean.

Scan patterns settled in D-390, widened by this plan's review and by acceptance-review
pass 1 (spec § Derivations D1):

* ``*.sql`` files are never scanned for DDL text — they are schema data applied by
  someone (``db/schema.sql`` is owner-applied by design). The scan finds the
  INVOCATION that applies them (a ``psql`` call, a compose ``migrate`` service)
  instead of the SQL text itself.
* An alembic ``env.py``'s own connection source is checked separately from the
  general pattern set, because ordinary application code reading ``DATABASE_URL``
  is expected and harmless — it is meant to follow the cutover. Alembic does not:
  it opens its own connection and runs DDL directly, so an ``env.py`` that still
  resolves its connection from ``DATABASE_URL`` (rather than ``DATABASE_URL_OWNER``)
  is a real pre-cutover risk. An alembic env is recognised by CONTENT (it imports
  ``alembic``), not by living under an ``alembic/`` directory — the standard
  ``migrations/env.py`` layout is exactly as real a risk.
* **Patterns match the RAW line; comment-stripping is used ONLY to decide
  suppression, and only in the direction of reporting more, never less.** A
  same-line `#`/`--`/`//` is common inside ordinary code that has nothing to do
  with comments — a quoted string (`"id#1"`), a `postgresql://` URL, a bash
  parameter expansion (`${VAR#pattern}`), a decrement (`i--`) — and truncating
  the line there before pattern-matching would hide a real finding sitting after
  it. Matching the raw line first and only consulting the stripped line for the
  suppression decision means an over-eager strip can only fail to suppress
  (fail closed), never fail to detect.
* **Suppression follows the CONNECTION SOURCE, not mere token presence.** A line
  is suppressed only when its comment-stripped text names ``DATABASE_URL_OWNER``
  AND does not also name bare ``DATABASE_URL`` — ``os.getenv("DATABASE_URL_OWNER")
  or os.environ["DATABASE_URL"]`` still reaches ``DATABASE_URL`` and stays a
  finding. The compose "environment sets DATABASE_URL" site follows the same rule
  but reads the VALUE assigned to ``DATABASE_URL``, not the whole line: a value of
  exactly ``${DATABASE_URL}``/``$DATABASE_URL`` is a pass-through of the same
  ``.env`` entry (not an override — no finding at all), a value naming
  ``DATABASE_URL_OWNER`` is an intentional owner hand-off (suppressed), and
  anything else — including a hardcoded owner DSN that merely LOOKS safe — stays
  a finding. The cheapest way to defeat either rule is still a comment, and a
  comment still never suppresses.
* **Compose services are located STRUCTURALLY**, as a direct child key of the
  top-level ``services:`` mapping — never the first indented ``<name>:`` found
  anywhere in the file, which a `depends_on:` block or an unrelated top-level
  `secrets:` section can also spell. When a service's block cannot be located
  (flow-style YAML, a one-line file) suppression for that service's structural
  findings is skipped entirely — fail closed, never a silent fall-back to
  scanning the whole file as if it were one block. A compose file that fails to
  parse at all is its own finding (``compose file unparseable``), never a quiet
  empty result.
* Fail closed, never pass on nothing: a missing repo, a repo with zero walkable
  files, a stale clone (HEAD behind its upstream after ``git fetch``), no
  upstream at all, a non-git repo, or ANY exception the privilege probe or a git
  call raises are each their own failure — a scan that found nothing because it
  looked at nothing, at old code, or crashed silently must never read as a clean
  pass. A spec with neither ``id`` nor ``name``, or a non-mapping ``depends``,
  fails the same way — a resolvable error string, never ``/opt/None`` and never
  an uncaught ``AttributeError``.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from fabrik.drivers.postgres import POSTGRES_CONTAINER, probe_app_role

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

_CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh"}
_COMPOSE_GLOBS = (
    "compose.yaml",
    "compose.yml",
    "compose.*.yaml",
    "compose.*.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
    "docker-compose*.yml",
    "docker-compose*.yaml",
)
_NAMED_WALKABLE = {"Makefile", "Procfile", "justfile", "Justfile", "package.json", "env.py"}


def _is_compose_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name, glob) for glob in _COMPOSE_GLOBS)


def _is_walkable(rel: Path) -> bool:
    name = rel.name
    if rel.suffix in _CODE_EXTENSIONS:
        return True
    if name in _NAMED_WALKABLE:
        return True
    if _is_compose_file(name):
        return True
    if name.startswith("Dockerfile"):
        return True
    return bool(name.lower().startswith("entrypoint"))


# ── Patterns (case-insensitive; spec § 2, widened by acceptance review) ────── #

_LINE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "runtime DDL",
        re.compile(
            r"\b(create|alter|drop)\s+"
            r"(or\s+replace\s+)?"
            r"(unique\s+)?"
            r"(temp(orary)?\s+|unlogged\s+|materialized\s+)?"
            r"(table|index|extension|view|function|schema|type|sequence|trigger)\b",
            re.IGNORECASE,
        ),
    ),
    ("create_all", re.compile(r"\bcreate_all\b", re.IGNORECASE)),
    ("op.create_table", re.compile(r"op\.create_table", re.IGNORECASE)),
    (".sync(", re.compile(r"\.sync\(", re.IGNORECASE)),
    (
        "alembic upgrade/downgrade",
        re.compile(
            r"\balembic\b.{0,40}?\b(upgrade|downgrade)\b|\bcommand\.(upgrade|downgrade)\s*\(",
            re.IGNORECASE,
        ),
    ),
    ("prisma migrate/db push", re.compile(r"\bprisma\s+(migrate|db\s+push)\b", re.IGNORECASE)),
    ("drizzle-kit push", re.compile(r"\bdrizzle-kit\s+push\b", re.IGNORECASE)),
    ("manage.py migrate", re.compile(r"\bmanage\.py\s+migrate\b", re.IGNORECASE)),
    ("psql invocation", re.compile(r"\bpsql\b", re.IGNORECASE)),
]

# A trailing #, -- or // comment, stripped ONLY for the suppression decision —
# patterns above are matched against the RAW line (module docstring).
_COMMENT_RE = re.compile(r"(#|--|//).*$")
# Case-insensitive: alembic env.py connections can read a lowercase attribute
# (`settings.database_url`) as readily as the uppercase env var. `_` continues a
# \b word run, so neither token ever matches inside the other's OWNER/bare form.
_OWNER_TOKEN_RE = re.compile(r"\bDATABASE_URL_OWNER\b", re.IGNORECASE)
_URL_TOKEN_RE = re.compile(r"\bDATABASE_URL\b", re.IGNORECASE)
_ALEMBIC_IMPORT_RE = re.compile(r"^\s*(from\s+alembic\s+import\b|import\s+alembic\b)", re.MULTILINE)


def _strip_comment(line: str) -> str:
    return _COMMENT_RE.sub("", line, count=1)


def _suppressed_by_owner(text: str) -> bool:
    """True when ``text`` names the owner connection source AND not the bare one.

    ``os.getenv("DATABASE_URL_OWNER") or os.environ["DATABASE_URL"]`` still reaches
    ``DATABASE_URL`` on the fallback branch, so it must NOT read as suppressed.
    """
    return bool(_OWNER_TOKEN_RE.search(text)) and not bool(_URL_TOKEN_RE.search(text))


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
        label = None
        for pattern_label, regex in _LINE_PATTERNS:
            if regex.search(raw):
                label = pattern_label
                break
        if label is None:
            continue
        if _suppressed_by_owner(_strip_comment(raw)):
            continue
        findings.append(Finding(path=posix, line=lineno, pattern=label))
    return findings


def _scan_alembic_env(rel: Path, lines: list[str]) -> list[Finding]:
    posix = rel.as_posix()
    findings: list[Finding] = []
    for lineno, raw in enumerate(lines, start=1):
        if not _URL_TOKEN_RE.search(raw):
            continue
        if _suppressed_by_owner(_strip_comment(raw)):
            continue
        findings.append(
            Finding(
                path=posix, line=lineno, pattern="alembic env.py DATABASE_URL connection source"
            )
        )
    return findings


# ── Compose structure: services located as children of the top-level mapping ── #

_SERVICES_KEY_RE = re.compile(r"^services\s*:\s*(#.*)?$")


def _services_block_range(lines: list[str]) -> tuple[int, int] | None:
    """The [start, end) line range of the top-level ``services:`` mapping body."""
    start = None
    for i, line in enumerate(lines):
        if _SERVICES_KEY_RE.match(line):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        if len(line) - len(line.lstrip(" ")) == 0:
            end = j
            break
    return start, end


def _service_block_range(
    lines: list[str], services_range: tuple[int, int], service_name: str
) -> tuple[int, int] | None:
    """The [start, end) range of ONE service, as a direct child of ``services:``.

    Returns ``None`` when the child indent level can't be determined or the named
    key never appears at exactly that indent — never a guess, and never the first
    same-named key found anywhere (a `depends_on:` block or a top-level `secrets:`
    section can spell the same key at a different, deeper or unrelated, level).
    """
    start, end = services_range
    child_indent = None
    for j in range(start + 1, end):
        stripped_line = lines[j].strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        child_indent = len(lines[j]) - len(lines[j].lstrip(" "))
        break
    if child_indent is None:
        return None

    key_re = re.compile(rf'^ {{{child_indent}}}["\']?{re.escape(service_name)}["\']?\s*:')
    svc_start = None
    for j in range(start + 1, end):
        if key_re.match(lines[j]):
            svc_start = j
            break
    if svc_start is None:
        return None

    svc_end = end
    for j in range(svc_start + 1, end):
        line = lines[j]
        if not line.strip():
            continue
        cur_indent = len(line) - len(line.lstrip(" "))
        if cur_indent <= child_indent:
            svc_end = j
            break
    return svc_start, svc_end


def _database_url_env_value(environment: object) -> str | None:
    """The raw value assigned to ``DATABASE_URL`` under ``environment:``, if any."""
    if isinstance(environment, dict) and "DATABASE_URL" in environment:
        value = environment["DATABASE_URL"]
        return "" if value is None else str(value)
    if isinstance(environment, list):
        for item in environment:
            if isinstance(item, str) and item.split("=", 1)[0].strip() == "DATABASE_URL":
                return item.split("=", 1)[1] if "=" in item else ""
    return None


def _classify_database_url_env(value: str) -> str:
    """One of ``passthrough`` (same ``.env`` value, not an override — no finding),
    ``owner`` (names the owner DSN as its source — suppressed) or ``override``
    (anything else, including a hardcoded owner DSN — still a finding: merely
    passing the owner value through a different-looking expression is not the
    same as naming ``DATABASE_URL_OWNER`` as the source)."""
    text = value.strip()
    if text in ("${DATABASE_URL}", "$DATABASE_URL"):
        return "passthrough"
    if _suppressed_by_owner(text):
        return "owner"
    return "override"


def _locate_env_url_line(lines: list[str], start: int, end: int) -> int:
    pattern = re.compile(r"\bDATABASE_URL\s*[:=]", re.IGNORECASE)
    for j in range(start, end):
        if pattern.search(lines[j]):
            return j + 1
    return start + 1


def _scan_compose_structure(rel: Path, text: str) -> list[Finding]:
    """Service-shaped findings a line-by-line scan cannot see: a service NAMED
    ``migrate``, and a service that overrides ``DATABASE_URL`` under ``environment:``
    (that value wins over ``.env``, so a cutover of ``.env`` never reaches the
    container)."""
    posix = rel.as_posix()
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return [Finding(path=posix, line=1, pattern="compose file unparseable")]
    if not isinstance(doc, dict):
        return []
    services = doc.get("services")
    if not isinstance(services, dict):
        return []

    lines = text.splitlines()
    services_range = _services_block_range(lines)

    findings: list[Finding] = []
    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, dict):
            continue

        block = (
            _service_block_range(lines, services_range, str(service_name))
            if services_range is not None
            else None
        )

        if service_name == "migrate":
            if block is not None:
                s, e = block
                stripped_block = "\n".join(_strip_comment(ln) for ln in lines[s:e])
                suppressed = _suppressed_by_owner(stripped_block)
                line = s + 1
            else:
                # Block unlocatable: fail closed — never suppress what we can't verify.
                suppressed = False
                line = 1
            if not suppressed:
                findings.append(
                    Finding(path=posix, line=line, pattern="compose service named migrate")
                )

        env_value = _database_url_env_value(service_cfg.get("environment"))
        if env_value is not None and _classify_database_url_env(env_value) == "override":
            if block is not None:
                s, e = block
                line = _locate_env_url_line(lines, s, e)
            else:
                line = 1
            findings.append(
                Finding(path=posix, line=line, pattern="compose environment sets DATABASE_URL")
            )
    return findings


def _scan_file(rel: Path, text: str) -> list[Finding]:
    lines = text.splitlines()
    findings = _scan_lines(rel, lines)
    if rel.name == "env.py" and _ALEMBIC_IMPORT_RE.search(text):
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


def _git_env() -> dict[str, str]:
    """The environment every git call in this module runs with: no credential
    prompt can block a check that must complete unattended."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _stale_clone_failure(repo_dir: Path) -> str | None:
    """A failure string when ``repo_dir``'s HEAD is behind (or missing) its upstream.

    Deploys pull the remote (core/30-ops.md § redeploy), so a stale hub clone would
    scan code that is no longer what gets deployed. ``None`` means the clone is
    current and has an upstream to compare against. Every git call is wrapped: a
    timeout, a missing git binary or a non-git directory is a failure string, never
    an uncaught exception that would crash the whole check.
    """
    try:
        fetch = subprocess.run(
            ["git", "-C", str(repo_dir), "fetch", "-q"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=_git_env(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"git fetch failed for {repo_dir}: {exc}"
    if fetch.returncode != 0:
        return f"could not fetch upstream for {repo_dir}: {(fetch.stderr or fetch.stdout).strip()}"

    try:
        upstream_ref = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{u}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_git_env(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"could not resolve upstream for {repo_dir}: {exc}"
    if upstream_ref.returncode != 0:
        return f"no upstream configured for {repo_dir}"

    try:
        head = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_git_env(),
        )
        upstream_sha = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "@{u}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=_git_env(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"could not resolve HEAD/upstream sha for {repo_dir}: {exc}"
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
    ANY exception the probe raises (``AppRoleError``, a driver ``RuntimeError``, a
    connectivity ``OSError``/``TimeoutExpired``, ...) becomes a failure string; the
    repo scan still runs regardless.
    """
    failures: list[str] = []

    try:
        failures.extend(probe_app_role(db_name, container=container))
    except Exception as exc:  # noqa: BLE001 - deliberately blanket, see docstring
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


class SpecResolutionError(ValueError):
    """The spec lacks what ``_db_name_for_spec``/``project_repo_dir`` need to
    resolve safely — the CLI catches this and prints+exits 1 rather than crashing
    on ``/opt/None`` or an ``AttributeError`` from a malformed ``depends:``."""


def _db_name_for_spec(spec: dict) -> str:
    """The registrar's db_name rule (mirrors ``DeploymentOrchestrator._provision_postgres``,
    ``src/fabrik/orchestrator/infrastructure.py``): ``depends.postgres`` wins when set,
    else the spec's name (falling back to id), hyphens rewritten to underscores —
    PostgreSQL identifiers don't allow hyphens without quoting."""
    depends = spec.get("depends")
    if depends is not None and not isinstance(depends, dict):
        raise SpecResolutionError(f"spec 'depends' must be a mapping, got {type(depends).__name__}")
    configured = (depends or {}).get("postgres")
    if configured:
        return str(configured)
    name_or_id = spec.get("name") or spec.get("id")
    if not name_or_id:
        raise SpecResolutionError("spec has neither 'name' nor 'id' — cannot derive db_name")
    return str(name_or_id).replace("-", "_")


def project_repo_dir(spec: dict) -> Path:
    """``/opt/<id>`` — the orchestrator's ``_load_secrets`` precedence (id before name,
    ``src/fabrik/orchestrator/__init__.py``). Shared by the CLI and T04's registrar step."""
    id_or_name = spec.get("id") or spec.get("name")
    if not id_or_name:
        raise SpecResolutionError("spec has neither 'id' nor 'name' — cannot derive repo_dir")
    return Path("/opt") / str(id_or_name)
