#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/DATA_SYNC_WORKFLOW.md
"""Sync db/schema.sql to all /opt projects that don't have it.

Creates the db/ directory and schema.sql file for projects that are missing it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
OPT_ROOT = Path("/opt")

SCHEMA_TEMPLATE = """-- Database Schema
-- Project: {name}
-- Last Updated: {today}
--
-- This file tracks all database schema changes.
-- Agents MUST update this file when making database changes.
--
-- Usage:
--   - Add new tables/columns with CREATE statements
--   - Document changes with comments including date
--   - Keep this file as the source of truth for DB structure

-- =============================================================================
-- TABLES
-- =============================================================================

-- Example:
-- CREATE TABLE IF NOT EXISTS users (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     email VARCHAR(255) UNIQUE NOT NULL,
--     created_at TIMESTAMPTZ DEFAULT NOW(),
--     updated_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Example:
-- CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- =============================================================================
-- CHANGE LOG
-- =============================================================================
-- {today}: Initial schema created
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync db/schema.sql to all /opt projects.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing anything",
    )
    return parser.parse_args()


def main() -> int:
    """Add db/schema.sql to all /opt projects that don't have it."""
    args = parse_args()
    today = date.today().isoformat()

    if args.dry_run:
        print("DRY-RUN MODE: No files will be written\n")

    # Folders to exclude (not real projects)
    exclude_folders = {
        ".factory",
        ".ssh",
        "web_scraper",  # Deprecated
    }

    # Discover projects
    projects = []
    for project_dir in OPT_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith("_"):
            continue
        if project_dir.name.startswith("."):
            continue
        if project_dir.name in exclude_folders:
            continue
        if project_dir == FABRIK_ROOT:
            continue
        projects.append(project_dir)

    print(f"Found {len(projects)} projects to check\n")

    created_count = 0
    skipped_count = 0
    exists_count = 0

    for project_dir in sorted(projects):
        db_dir = project_dir / "db"
        schema_file = db_dir / "schema.sql"

        # Check if schema.sql already exists
        if schema_file.exists():
            print(f"✓ {project_dir.name:40} EXISTS (db/schema.sql)")
            exists_count += 1
            continue

        # Check for alternative locations
        alt_locations = [
            project_dir / "schema.sql",
            project_dir / "docs" / "schema.sql",
            project_dir / "docs" / "db_schema.sql",
        ]
        alt_found = None
        for alt in alt_locations:
            if alt.exists():
                alt_found = alt
                break

        if alt_found:
            print(f"~ {project_dir.name:40} FOUND at {alt_found.relative_to(project_dir)}")
            skipped_count += 1
            continue

        # Create db/schema.sql
        if args.dry_run:
            print(f"→ {project_dir.name:40} WOULD CREATE db/schema.sql")
            created_count += 1
        else:
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                schema_file.write_text(SCHEMA_TEMPLATE.format(name=project_dir.name, today=today))
                print(f"+ {project_dir.name:40} CREATED db/schema.sql")
                created_count += 1
            except PermissionError:
                print(f"✗ {project_dir.name:40} SKIP (no write permission)")
                skipped_count += 1

    print()
    print(
        f"Results: {created_count} created, {exists_count} already exist, {skipped_count} skipped"
    )

    if args.dry_run:
        print("\nDRY-RUN: No files were modified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
