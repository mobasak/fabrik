#!/usr/bin/env python3
# AFTER-EDIT: none
"""Enforce database schema synchronization.

When model/entity files change, schema.sql or migrations must be updated.

Triggers on changes to:
- a filename in MODEL_FILE_PATTERNS (src/**/models.py, src/**/entities.py, src/**/db/*.py, models/*.py)
- any other non-test, non-migration .py whose staged content declares a table (`declares_table`) — W-62875be3,
  iterative_image_editor 01M3WW5PFN: db.py / main.py / tenant_registry.py declared tables the filenames never saw

A change is a change of the table STRUCTURE (`schema_signature`): the parsed DB classes' field statements and the
module-level Table(...) calls, compared between HEAD and the index. A regex over diff lines (the fallback for a file
that does not parse) fired on `class X(BaseModel)`, `class X(BaseHTTPMiddleware)` and re-wrapped columns — measured
2026-10-13: 12 false would-fails for 1 true in the 5 newly admitted files' history, 5 more in filename-matched files —
and a per-line rule loses a change on a wrapped call's continuation line or a column moved between adjacent classes.

Enforces:
- schema.sql updated, OR
- migrations/ directory has new migration, OR
- alembic/versions/ has new migration

Exit codes:
    0 - Pass (schema synced or no DB changes)
    1 - Fail (model changed without schema update)
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

DATA_CONTRACT_FILE = "docs/data-contract.md"

MODEL_FILE_PATTERNS = [
    r"src/.*/models\.py$",
    r"src/.*/entities\.py$",
    r"src/.*/db/.*\.py$",
    r"models/.*\.py$",
]

SCHEMA_FILES = [
    "schema.sql",
    "database/schema.sql",
    "db/schema.sql",
    "sql/schema.sql",
]

MIGRATION_DIRS = [
    "migrations/",
    "alembic/versions/",
    "db/migrations/",
]

DB_FIELD_PATTERNS = [
    r"Column\s*\(",
    r"relationship\s*\(",
    r"ForeignKey\s*\(",
    r"Table\s*\(",
    r"mapped_column\s*\(",
    r"class\s+\w+\s*\([^)]*Base[^)]*\)",
    r"class\s+\w+\s*\([^)]*Model[^)]*\)",
]


def get_staged_files() -> list[str]:
    """Get list of staged files — ``-z``, because plain output QUOTES a non-ASCII path and no later check
    could then resolve it (the whole gate passed silently)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "-z", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached", "-z"],
            capture_output=True,
            text=True,
        )
    return [f for f in result.stdout.split("\0") if f]


_ORM_IMPORT = re.compile(r"^\s*(?:from|import)\s+(?:sqlalchemy|sqlmodel|flask_sqlalchemy)\b", re.M)
_TABLE_DECL = re.compile(
    r"__tablename__\s*(?::[^=\n]+)?=|\bTable\s*\(\s*['\"]|\btable\s*=\s*True\b"
    r"|class\s+\w+\s*\([^)]*\b\w+\.Model\s*[,)]"
)
_COLUMN_CALLS = {"Column", "mapped_column", "relationship"}
_DB_BASES = {"Base", "DeclarativeBase", "SQLModel", "Model"}


def _git_text(*args: str) -> str | None:
    """stdout of a git command run at the repo root, or None when it fails (a path absent from that tree)."""
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=_repo_root())
    return r.stdout if r.returncode == 0 else None


def _is_test_or_migration(filepath: str) -> bool:
    name = os.path.basename(filepath)
    return (
        filepath.startswith("tests/")
        or "/tests/" in filepath
        or name.startswith("test_")
        or name in ("tests.py", "conftest.py")  # review round 1 A-S4: Django's per-app tests.py
        or any(filepath.startswith(d) or ("/" + d) in filepath for d in MIGRATION_DIRS)
    )


def declares_table(text: str) -> bool:
    """The source imports an ORM and declares a table: `__tablename__`, a `Table("…")` call, `table=True` or a class
    on `<x>.Model`."""
    return bool(_ORM_IMPORT.search(text) and _TABLE_DECL.search(text))


def is_model_file(filepath: str) -> bool:
    """A model file by name, or a non-test, non-migration .py whose staged content declares a table (the HEAD blob
    when the path is deleted in the index)."""
    if any(re.search(pattern, filepath) for pattern in MODEL_FILE_PATTERNS):
        return True
    if not filepath.endswith(".py") or _is_test_or_migration(filepath):
        return False
    text = _git_text("show", f":{filepath}")
    if text is None:
        text = _git_text("show", f"HEAD:{filepath}")
    return text is not None and declares_table(text)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        f = node.func
        return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
    return ""


def _base_name(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def _is_db_class(cls: ast.ClassDef) -> bool:
    if any(_base_name(b) in _DB_BASES for b in cls.bases):
        return True
    if any(
        k.arg == "table" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in cls.keywords
    ):
        return True
    for stmt in cls.body:
        targets = (
            stmt.targets
            if isinstance(stmt, ast.Assign)
            else [stmt.target]
            if isinstance(stmt, ast.AnnAssign)
            else []
        )
        if any(getattr(x, "id", "") == "__tablename__" for x in targets):
            return True
        if (
            isinstance(stmt, (ast.Assign, ast.AnnAssign))
            and stmt.value is not None
            and _call_name(stmt.value) in _COLUMN_CALLS
        ):
            return True
    return False


def schema_signature(text: str) -> list[str] | None:
    """The table STRUCTURE a source declares, position- and format-free: every DB class (a DB base, `table=True`,
    `__tablename__`, or a column call in its body — mixins included) as its name plus its body's assignments and
    annotated assignments (methods excluded), and every module-level assignment of a `Table(...)` call. None when the
    source does not parse.

    COBRA (D-253): a change routed around a recognised DB class (a helper returning columns, a custom base alias with
    no `__tablename__` and no column call) is invisible here — the cheapest dodge, and the regex never caught it either."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out: list[str] = []
    # every class and Table(...) assignment at any depth — a model under try/except or if/else counts (review round
    # 1, A-S2); ast.walk's breadth-first order is deterministic for one source
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_db_class(node):
            fields = [ast.dump(s) for s in node.body if isinstance(s, (ast.Assign, ast.AnnAssign))]
            out.append(node.name + ":" + "|".join(fields))
        elif (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and node.value is not None
            and _call_name(node.value) == "Table"
        ):
            out.append("table:" + ast.dump(node))
    return out


def _staged_renames() -> dict[str, str]:
    """Staged renames, new path -> old path (git's own rename detection over the index)."""
    out = _git_text("diff", "--cached", "-M", "--name-status", "-z", "HEAD") or ""
    parts = out.split("\0")
    renames: dict[str, str] = {}
    i = 0
    while i < len(parts):
        status = parts[i]
        if status.startswith(("R", "C")) and i + 2 < len(parts):
            renames[parts[i + 2]] = parts[i + 1]
            i += 3
        else:
            i += 2
    return renames


def has_db_changes(filepath: str) -> bool:
    """The table structure differs between HEAD and the index (a side absent from its tree is empty); a side that
    does not parse falls back to the DB_FIELD_PATTERNS regex over the staged diff. A rename compares the new path
    against its source, and the source's own deletion is no change (review round 1, A-S3: a `git mv` with no edit
    failed as a brand-new table)."""
    renames = _staged_renames()
    if filepath in renames.values():
        return False
    old = _git_text("show", f"HEAD:{filepath}")
    if old is None and filepath in renames:
        old = _git_text("show", f"HEAD:{renames[filepath]}")
    new = _git_text("show", f":{filepath}")
    old_sig = schema_signature(old) if old is not None else []
    new_sig = schema_signature(new) if new is not None else []
    if old_sig is not None and new_sig is not None:
        return old_sig != new_sig
    diff = _git_text("diff", "--cached", "--", filepath) or ""
    return any(re.search(pattern, diff) for pattern in DB_FIELD_PATTERNS)


def schema_file_updated(staged_files: list[str]) -> bool:
    """Check if any schema file was updated.

    Matches by path SUFFIX, not exact equality (transdoc upstream proposal
    2026-08-21): the saas-skeleton scaffold itself emits the schema at
    ``server/db/schema.sql`` (scaffold.py — the server/ layout), and ``api/`` /
    ``backend/`` / ``services/<x>/`` layouts are equally common. An equality
    test silently missed all of them, disarming this gate exactly where it is
    most needed. Anchored on the separator ("/" + known) so ``my_schema.sql``
    and ``not_a_db/schema.sql.bak`` stay non-matches — strictly widening,
    never a new false positive.
    """
    return any(
        staged == known or staged.endswith("/" + known)
        for staged in staged_files
        for known in SCHEMA_FILES
    )


def migration_added(staged_files: list[str]) -> bool:
    """Check if a new migration was added.

    Same suffix law as :func:`schema_file_updated` (the hub's own verification
    of the 2026-08-21 proposal found the twin bug here): ``startswith`` missed
    ``server/migrations/…`` — a migration dir at any depth counts, anchored on
    the separator.
    """
    for migration_dir in MIGRATION_DIRS:
        for f in staged_files:
            # .py OR .sql (youtube 01M180Z9): hardcoding one language's extension for a
            # check whose own MIGRATION_DIRS generalizes the directory let a plain-SQL
            # project stage 3 real migrations — 7 new columns — with EXIT=0, no WARN.
            if (f.startswith(migration_dir) or ("/" + migration_dir) in f) and f.endswith(
                (".py", ".sql")
            ):
                return True
    return False


def _repo_root() -> str:
    """Absolute repo root, so filesystem checks match git's root-relative staged paths
    regardless of the process CWD (the gate may run from a subdir)."""
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "."


# A landed DROP is the one direction with no innocent reading. A contract legitimately LEADS the
# schema mid-plan — that is the pipeline order Fabrik prescribes, and failing there would trap every
# freeze-before-build plan — but a table the contract still DECLARES while a migration in the same
# diff DROPS it is unambiguously stale. Any agent grounding on the frozen contract then plans against
# a dropped table and gets UndefinedTable: the exact failure class the contract exists to prevent,
# moved one artifact upstream. Filed by transdoc (2026-08-28) with the live case — commit a059c29
# dropped email_verify_tokens and password_reset_tokens while docs/data-contract.md v9 (Status:
# FROZEN) still declared both, and final_gate reported success across 53 checks.
_DROP_TABLE_RE = re.compile(
    r"""\bdrop_table\(\s*["']([A-Za-z_][\w]*)["']|\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?["`']?([A-Za-z_][\w]*)""",
    re.I,
)


def _dropped_tables(paths: list[str], root: str) -> set[str]:
    """Table names a staged migration drops (Alembic `drop_table(...)` or raw `DROP TABLE`)."""
    out: set[str] = set()
    for rel in paths:
        if "alembic/versions/" not in rel and "migrations/" not in rel:
            continue
        try:
            text = Path(root, rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for a, b in _DROP_TABLE_RE.findall(text):
            out.add((a or b).lower())
    return out


def _contract_declares(root: str, tables: set[str]) -> set[str]:
    """Of `tables`, those the frozen data contract still declares."""
    if not tables:
        return set()
    try:
        text = Path(root, DATA_CONTRACT_FILE).read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return set()
    return {t for t in tables if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", text)}


def warn_if_data_contract_stale(staged_files: list[str]) -> None:
    """WARN (never fail) if the schema changed but the frozen data contract wasn't updated too.

    docs/data-contract.md is the frozen GUI<->DB field dictionary. When db/schema.sql or a
    migration changes, the contract may be drifting from the schema. Advisory only — it nudges,
    it does not block (existing projects are grandfathered; a schema change may not touch fields).
    """
    schema_changed = schema_file_updated(staged_files) or migration_added(staged_files)
    if not schema_changed:
        return
    if not os.path.exists(os.path.join(_repo_root(), DATA_CONTRACT_FILE)):
        return
    if DATA_CONTRACT_FILE in staged_files:
        return
    root = _repo_root()
    stale = _contract_declares(root, _dropped_tables(staged_files, root))
    if stale:
        # HARD on the drop direction only (transdoc's ranked direction 1). No "the contract is
        # ahead" reading exists for a drop that already landed.
        names = ", ".join(sorted(stale))
        print(
            f"✗ FAIL: {DATA_CONTRACT_FILE} still declares {len(stale)} table(s) this diff DROPS: "
            f"{names}."
        )
        print("    A frozen contract that declares a dropped table sends the next agent to plan")
        print(
            "    against it — UndefinedTable at build time, from the artifact meant to prevent it."
        )
        print("    Run /fabrik-data-contract to re-freeze (bump Version), then re-stage.")
        raise SystemExit(1)
    print(f"⚠️  WARN: schema changed but {DATA_CONTRACT_FILE} was not updated.")
    print("    The frozen data contract may be drifting from the schema.")
    print("    Re-run /fabrik-data-contract (bump Version) if fields/enums changed; ignore if not.")


# intel 01M4TJJDC3: where a project applies its schema through migrations, schema.sql is documentation —
# only a NEW migration under that project's own migration dir changes the database (site-provisioner
# 7da4149 passed on schema.sql alone; 5ce52f2 later added 20 columns no migration had created).
_VENDORED_SEGMENTS = ("node_modules/", ".venv/", "site-packages/", "vendor/", "_vendor/")
_NOT_A_MIGRATION = ("env.py", "__init__.py", "script.py.mako")


def _migration_roots() -> dict[str, set[str]]:
    """``{root: {migration dirs}}`` for every migration dir in the INDEX (``git ls-files``, run at the repo
    root). A root is the prefix before a MIGRATION_DIRS match ("" or ending in "/"), taken over EVERY
    matching entry, so ``db/migrations/x.py`` yields both "" (``migrations/``) and "db/" (``db/migrations/``).
    A root inside a vendored tree (``node_modules/`` and the like) is not a project's. Git failing → {}
    (today's rule — unreachable in practice: an empty staged list returns before this runs)."""
    out = _git_text("ls-files", "-z") or ""
    roots: dict[str, set[str]] = {}
    for path in filter(None, out.split("\0")):
        anchored = "/" + path
        for d in MIGRATION_DIRS:
            at = anchored.find("/" + d)
            while at >= 0:
                root = anchored[1 : at + 1]
                if not any(("/" + v) in ("/" + root) for v in _VENDORED_SEGMENTS):
                    roots.setdefault(root, set()).add(root + d)
                at = anchored.find("/" + d, at + 1)
    return roots


def _governing(model: str, roots: dict[str, set[str]]) -> set[str]:
    """The migration dirs whose root is an ancestor of ``model`` (the repo root "" governs every path)."""
    return {d for root, dirs in roots.items() if model.startswith(root) for d in dirs}


def _added_migrations() -> list[str]:
    """Staged ADDED, MODIFIED or RENAMED-IN files (a rename lists its new path), minus migration plumbing
    (``env.py`` and the like). An edit counts: amending a not-yet-shipped migration in the same feature is
    common (seo 42d7000, site-provisioner 1a7de0f), and the gate cannot tell it from an edit to an applied
    one — that dodge is named in the D-row, not graded here."""
    out = _git_text("diff", "--cached", "--name-only", "--diff-filter=AMR", "-z") or ""
    return [
        f
        for f in filter(None, out.split("\0"))
        if f.endswith((".py", ".sql")) and os.path.basename(f) not in _NOT_A_MIGRATION
    ]


def main() -> int:
    """Check schema synchronization."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    warn_if_data_contract_stale(staged_files)

    model_files_changed = [f for f in staged_files if is_model_file(f)]

    if not model_files_changed:
        return 0

    model_files_with_db_changes = [f for f in model_files_changed if has_db_changes(f)]

    if not model_files_with_db_changes:
        return 0

    roots = _migration_roots()
    added = _added_migrations()
    governed = {f: _governing(f, roots) for f in model_files_with_db_changes}
    unmigrated = {
        f: dirs
        for f, dirs in governed.items()
        if dirs and not any(a.startswith(d) for a in added for d in dirs)
    }
    if unmigrated:
        print("ERROR: Database model changes detected without a new migration.")
        print("")
        print("These models live under a project that applies its schema through migrations, so")
        print(
            "schema.sql alone never reaches the database — add a migration that creates the change:"
        )
        for f, dirs in list(unmigrated.items())[:5]:
            print(f"  - {f}  (migrations: {', '.join(sorted(dirs))})")
        print("")
        print("A dead migration dir? Remove it in the same commit and schema.sql suffices again.")
        return 1
    ungoverned = [f for f, dirs in governed.items() if not dirs]
    if not ungoverned:
        return 0  # every changed model has a new migration under its own dir

    if schema_file_updated(staged_files) or migration_added(staged_files):
        # Schema kept in sync — pass silently (no benign chatter for advisory=True to forward),
        # unless the repo applies migrations elsewhere: no staged migration can be an ungoverned
        # model's own (any migration dir is a root), so schema.sql may be all that reached it.
        if roots:
            mig_dirs = sorted({d for ds in roots.values() for d in ds})
            print(
                "WARN: model change passed with no migration under its own project, but this repo "
                "tracks migrations in "
                f"{', '.join(mig_dirs[:5])} — if those apply this model's tables, add a migration: "
                + ", ".join(ungoverned[:5])
            )
        return 0

    print("ERROR: Database model changes detected without schema update.")
    print("")
    print("Model files with DB changes:")
    for f in model_files_with_db_changes[:5]:
        print(f"  - {f}")
    print("")
    print("Fix: Update one of these:")
    print("  - schema.sql (or database/schema.sql)")
    print("  - Add migration to migrations/ or alembic/versions/")
    print("")
    print("If this is a Pydantic schema (not DB model), rename file to avoid confusion.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
