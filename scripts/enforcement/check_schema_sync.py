#!/usr/bin/env python3
# AFTER-EDIT: none
"""Enforce database schema synchronization.

When model/entity files change, schema.sql or migrations must be updated.

Triggers on changes to:
- src/**/models.py
- src/**/entities.py
- src/**/schemas.py (Pydantic models with DB fields)

Enforces:
- schema.sql updated, OR
- migrations/ directory has new migration, OR
- alembic/versions/ has new migration

Exit codes:
    0 - Pass (schema synced or no DB changes)
    1 - Fail (model changed without schema update)
"""

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
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
        )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def is_model_file(filepath: str) -> bool:
    """Check if file is a model/entity file."""
    return any(re.search(pattern, filepath) for pattern in MODEL_FILE_PATTERNS)


def has_db_changes(filepath: str) -> bool:
    """Check if file contains actual DB model changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        for pattern in DB_FIELD_PATTERNS:
            if re.search(pattern, diff_content):
                return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


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
        print("    against it — UndefinedTable at build time, from the artifact meant to prevent it.")
        print("    Run /fabrik-data-contract to re-freeze (bump Version), then re-stage.")
        raise SystemExit(1)
    print(f"⚠️  WARN: schema changed but {DATA_CONTRACT_FILE} was not updated.")
    print("    The frozen data contract may be drifting from the schema.")
    print("    Re-run /fabrik-data-contract (bump Version) if fields/enums changed; ignore if not.")


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

    if schema_file_updated(staged_files) or migration_added(staged_files):
        # Schema kept in sync — pass silently (no benign chatter for advisory=True to forward).
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
