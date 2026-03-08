#!/usr/bin/env python3
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

import re
import subprocess
import sys

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
    """Check if any schema file was updated."""
    return any(schema_file in staged_files for schema_file in SCHEMA_FILES)


def migration_added(staged_files: list[str]) -> bool:
    """Check if a new migration was added."""
    for migration_dir in MIGRATION_DIRS:
        for f in staged_files:
            if f.startswith(migration_dir) and f.endswith(".py"):
                return True
    return False


def main() -> int:
    """Check schema synchronization."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    model_files_changed = [f for f in staged_files if is_model_file(f)]

    if not model_files_changed:
        return 0

    model_files_with_db_changes = [f for f in model_files_changed if has_db_changes(f)]

    if not model_files_with_db_changes:
        return 0

    if schema_file_updated(staged_files):
        print("✅ Schema sync check PASSED (schema.sql updated)")
        return 0

    if migration_added(staged_files):
        print("✅ Schema sync check PASSED (migration added)")
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
