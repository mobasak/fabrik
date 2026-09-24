"""Pre-cutover check for the ``<db>_app`` DSN cutover — spec § 2 "pre-cutover check".

Before ``.env``'s ``DATABASE_URL`` is switched from the owner DSN to the ``<db>_app``
role DSN (T04), this module answers two questions: (1) is the app role's privilege
model already correct (delegated to T02's :func:`~fabrik.drivers.postgres.probe_app_role`),
and (2) does anything in the project's own repo still reach the database as an owner —
running DDL, a migration tool, or a bare ``psql`` invocation — over ``DATABASE_URL``
instead of ``DATABASE_URL_OWNER``. A cutover is safe only when both answers are clean.

Scan patterns settled in D-390, widened by this plan's review and by acceptance-review
passes 1, 2 and 3 (spec § Derivations D1):

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
  is suppressed only when its comment-STRIPPED text names ``DATABASE_URL_OWNER``
  AND its RAW (un-stripped) text does not also name bare ``DATABASE_URL`` — the
  disqualifier reads the raw line ON PURPOSE, because checking it against the
  stripped text would let an earlier stray `#`/`--`/`//` hide a second, real
  ``DATABASE_URL`` use later on the same line and cause a false suppression.
  ``os.getenv("DATABASE_URL_OWNER") or os.environ["DATABASE_URL"]`` still reaches
  ``DATABASE_URL`` and stays a finding. The compose "environment sets
  DATABASE_URL" site follows an analogous but stricter rule, keyed on the VALUE
  assigned, not the whole line or block: a value that FULLMATCHES a pass-through
  form (``${DATABASE_URL}``/``$DATABASE_URL``, the value-less list/null-dict
  form, or the ``:?msg``/``?msg`` "error if unset" guard) is not an override —
  no finding at all; a value that fullmatches the owner variable reference
  (``${DATABASE_URL_OWNER}``/``$DATABASE_URL_OWNER``, same guard forms allowed)
  is an intentional hand-off (suppressed); anything else — a hardcoded DSN, a
  ``:-default`` fallback that can silently substitute a different value, or a
  value that merely CONTAINS the owner name as a substring — stays a finding.
  The ``DATABASE_URL:`` environment-mapping KEY itself is never counted as a
  bare-token use for the disqualifier — only what it is set TO matters. The
  cheapest way to defeat any of these rules is still a comment, and a comment
  still never suppresses.
* **Compose services are located STRUCTURALLY**, as a direct child key of the
  top-level ``services:`` mapping — never the first indented ``<name>:`` found
  anywhere in the file, which a `depends_on:` block or an unrelated top-level
  `secrets:` section can also spell. When a service's block cannot be located
  (flow-style YAML, a one-line file) suppression for that service's structural
  findings is skipped entirely — fail closed, never a silent fall-back to
  scanning the whole file as if it were one block. Compose's OWN YAML tags
  (``!reset``, ``!override`` — valid merge directives, not malformed input) are
  understood by a dedicated loader; a compose file that GENUINELY fails to parse
  is its own finding (``compose file unparseable``), never a quiet empty result.
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
# `(\.\w+)*` covers a submodule import (`from alembic.op import ...`,
# `from alembic.context import ...`) — acceptance review pass 2, O22.
_ALEMBIC_IMPORT_RE = re.compile(
    r"^\s*(from\s+alembic(\.\w+)*\s+import\b|import\s+alembic\b)", re.MULTILINE
)


def _strip_comment(line: str) -> str:
    return _COMMENT_RE.sub("", line, count=1)


def _suppressed_by_owner(stripped_text: str, raw_text: str) -> bool:
    """True when the comment-STRIPPED text names the owner connection source AND
    the RAW text does not also name a bare ``DATABASE_URL``.

    The disqualifier reads the RAW text on purpose (acceptance review pass 2,
    O17): checking it against the stripped text would let a `#`/`--`/`//`
    earlier on the same line hide a SECOND, real ``DATABASE_URL`` use and cause
    a false suppression — e.g. ``psql "$DATABASE_URL_OWNER" -c "select 1";
    x="a#b"; psql "$DATABASE_URL" -f schema.sql`` reads as owner-only once the
    stray ``#`` strips away the second invocation, which must never happen.

    ``os.getenv("DATABASE_URL_OWNER") or os.environ["DATABASE_URL"]`` still
    reaches ``DATABASE_URL`` on the fallback branch, so it must NOT read as
    suppressed either.
    """
    return bool(_OWNER_TOKEN_RE.search(stripped_text)) and not bool(_URL_TOKEN_RE.search(raw_text))


_ENV_KEY_RE = re.compile(r'^\s*(-\s*)?["\']?DATABASE_URL["\']?\s*[:=]\s*(.*)$')


def _strip_env_key(line: str) -> str:
    """The ``DATABASE_URL:`` (dict) or ``- DATABASE_URL=`` (list) environment key
    is never itself a bare-token use (acceptance review pass 2, O18; the list form
    added pass 3, O28) — only strip it when the line IS exactly that key, returning
    the value that follows; any other line (a command string, e.g.) is returned
    untouched. Without this, a canonical hand-off like
    ``DATABASE_URL: ${DATABASE_URL_OWNER}`` would disqualify its own suppression:
    the KEY text alone already contains a word-bounded bare ``DATABASE_URL``.

    A value-less key (``DATABASE_URL:`` with nothing after the colon, or the
    bare list form once matched) means "inherit the host value" — the SAME bare
    ``DATABASE_URL`` use as an explicit ``${DATABASE_URL}``, so it is represented
    as that token rather than an empty string (acceptance review pass 3, O27) —
    an empty string would erase the bare-token signal entirely and let a sibling
    ``DATABASE_URL_OWNER`` line falsely suppress a block that still reaches the
    owner-bypassing bare variable.
    """
    m = _ENV_KEY_RE.match(line)
    if not m:
        return line
    value = m.group(2).strip()
    return value if value else "$DATABASE_URL"


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
        if _suppressed_by_owner(_strip_comment(raw), raw):
            continue
        findings.append(Finding(path=posix, line=lineno, pattern=label))
    return findings


def _scan_alembic_env(rel: Path, lines: list[str]) -> list[Finding]:
    posix = rel.as_posix()
    findings: list[Finding] = []
    for lineno, raw in enumerate(lines, start=1):
        if not _URL_TOKEN_RE.search(raw):
            continue
        if _suppressed_by_owner(_strip_comment(raw), raw):
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
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
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
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        cur_indent = len(line) - len(line.lstrip(" "))
        if cur_indent <= child_indent:
            svc_end = j
            break
    return svc_start, svc_end


def _database_url_env_value(environment: object) -> str | None:
    """The raw value assigned to ``DATABASE_URL`` under ``environment:``, if any.

    A value-LESS entry — the list form ``- DATABASE_URL`` (no ``=value``) or a
    null dict value (``DATABASE_URL:`` with nothing after the colon) — means
    "inherit from the host/parent environment", i.e. exactly the same pass-through
    as ``${DATABASE_URL}`` (acceptance review pass 2, O19), so it is represented
    as that token rather than an empty string (which would misclassify as an
    override).
    """
    if isinstance(environment, dict) and "DATABASE_URL" in environment:
        value = environment["DATABASE_URL"]
        return "$DATABASE_URL" if value is None else str(value)
    if isinstance(environment, list):
        for item in environment:
            if isinstance(item, str) and item.split("=", 1)[0].strip() == "DATABASE_URL":
                return item.split("=", 1)[1] if "=" in item else "$DATABASE_URL"
    return None


# Full-match only (acceptance review pass 2, O24) — a query param or path segment
# that merely CONTAINS "DATABASE_URL_OWNER" as a substring must stay an override;
# only the value ACTUALLY BEING the owner variable reference is safe. Both accept
# the bash "error if unset" modifier (`:?msg` or `?msg`, item O19) since that is
# still the SAME value, just guarded — never `:-default`/`-default` (item O19),
# which can silently substitute a different value and so stays an override.
# Case-SENSITIVE (acceptance review pass 3, O29) — shell/Compose variable names
# are case-sensitive, so `${database_url}` is a DIFFERENT variable, not the same
# pass-through, and `${database_url_owner}` is not the owner hand-off either; a
# case-insensitive match here would silently clear a real override.
_PASSTHROUGH_FULLMATCH_RE = re.compile(r"\$DATABASE_URL|\$\{DATABASE_URL(:?\?[^}]*)?\}")
_OWNER_FULLMATCH_RE = re.compile(r"\$DATABASE_URL_OWNER|\$\{DATABASE_URL_OWNER(:?\?[^}]*)?\}")


def _classify_database_url_env(value: str) -> str:
    """One of ``passthrough`` (same ``.env`` value, not an override — no finding),
    ``owner`` (the value IS the owner variable reference — suppressed) or
    ``override`` (anything else, including a hardcoded owner DSN, a `:-default`
    fallback, or a value that merely CONTAINS the owner var's name as a
    substring — still a finding)."""
    text = value.strip()
    if _PASSTHROUGH_FULLMATCH_RE.fullmatch(text):
        return "passthrough"
    if _OWNER_FULLMATCH_RE.fullmatch(text):
        return "owner"
    return "override"


def _locate_env_url_line(lines: list[str], start: int, end: int) -> int:
    pattern = re.compile(r"\bDATABASE_URL\s*[:=]", re.IGNORECASE)
    for j in range(start, end):
        if pattern.search(lines[j]):
            return j + 1
    return start + 1


class _ComposeSafeLoader(yaml.SafeLoader):
    """A ``SafeLoader`` that also understands Compose's OWN YAML tags.

    ``!reset`` and ``!override`` are Compose-specific merge directives (used in
    override files to reset or replace a value rather than merge it) — valid,
    common Compose YAML, not malformed input. Plain ``yaml.safe_load`` has no
    constructor for either and raises ``ConstructorError`` (a ``YAMLError``),
    which used to read as an unparseable file (acceptance review pass 2, O20).
    Registering a constructor that returns the tagged node's plain underlying
    value lets these files parse normally so they still get scanned; a GENUINELY
    malformed file still raises ``yaml.YAMLError`` and is reported as such.
    """


def _construct_compose_tag(loader: yaml.SafeLoader, node: yaml.Node) -> object:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


_ComposeSafeLoader.add_constructor("!reset", _construct_compose_tag)
_ComposeSafeLoader.add_constructor("!override", _construct_compose_tag)


def _scan_compose_structure(rel: Path, text: str) -> list[Finding]:
    """Service-shaped findings a line-by-line scan cannot see: a service NAMED
    ``migrate``, and a service that overrides ``DATABASE_URL`` under ``environment:``
    (that value wins over ``.env``, so a cutover of ``.env`` never reaches the
    container)."""
    posix = rel.as_posix()
    try:
        # _ComposeSafeLoader is a yaml.SafeLoader subclass whose only two extra
        # constructors return a plain scalar/sequence/mapping (never an arbitrary
        # object) — bandit's static check does not recognise a SafeLoader
        # subclass, only the literal `yaml.safe_load` call, hence the marker below.
        doc = yaml.load(text, Loader=_ComposeSafeLoader) or {}  # nosec B506
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
        # Computed once, structurally, and shared by both checks below — PyYAML
        # already resolves EVERY null spelling (`~`, `null`, `Null`, `NULL`, an
        # empty scalar, any of those followed by a `# comment`) to Python `None`
        # at parse time, so this is the authoritative answer to "is DATABASE_URL
        # null/value-less here", never a spelling-by-spelling regex (acceptance
        # review D7, O30 — the text-based key-stripper below only recognised a
        # textually EMPTY value, not YAML's other null forms).
        env_value = _database_url_env_value(service_cfg.get("environment"))

        if service_name == "migrate":
            if block is not None:
                s, e = block
                stripped_block = "\n".join(_strip_comment(ln) for ln in lines[s:e])
                # The disqualifier reads the RAW lines (not comment-stripped, O17)
                # with the `DATABASE_URL:` env KEY itself excluded (O18) — only
                # what it's set TO can disqualify a suppression.
                disqualifier_block = "\n".join(_strip_env_key(ln) for ln in lines[s:e])
                if env_value == "$DATABASE_URL":
                    # Trust the structural parse over the regex (O30): whatever
                    # spelling of null this service's DATABASE_URL used, it IS a
                    # bare-token use and must disqualify an owner suppression.
                    disqualifier_block += "\n$DATABASE_URL"
                suppressed = _suppressed_by_owner(stripped_block, disqualifier_block)
                line = s + 1
            else:
                # Block unlocatable: fail closed — never suppress what we can't verify.
                suppressed = False
                line = 1
            if not suppressed:
                findings.append(
                    Finding(path=posix, line=line, pattern="compose service named migrate")
                )

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
        # Named and typed (acceptance review pass 2, O25) — an exception with an
        # empty `str()` (e.g. a bare `raise RuntimeError()`) must never become an
        # uninformative blank failure line.
        failures.append(f"privilege probe raised {type(exc).__name__}: {exc}")

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


def _require_mapping(spec: object) -> dict:
    """The spec itself must be a mapping — a YAML file whose top level is a list
    or scalar (acceptance review pass 2, O21) would otherwise reach `spec.get(...)`
    and raise a bare ``AttributeError`` instead of a resolvable failure string."""
    if not isinstance(spec, dict):
        raise SpecResolutionError(f"spec must be a mapping, got {type(spec).__name__}")
    return spec


def _db_name_for_spec(spec: dict) -> str:
    """The registrar's db_name rule (mirrors ``DeploymentOrchestrator._provision_postgres``,
    ``src/fabrik/orchestrator/infrastructure.py``): ``depends.postgres`` wins when set,
    else the spec's name (falling back to id), hyphens rewritten to underscores —
    PostgreSQL identifiers don't allow hyphens without quoting."""
    spec = _require_mapping(spec)
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
    spec = _require_mapping(spec)
    id_or_name = spec.get("id") or spec.get("name")
    if not id_or_name:
        raise SpecResolutionError("spec has neither 'id' nor 'name' — cannot derive repo_dir")
    return Path("/opt") / str(id_or_name)
