#!/usr/bin/env python3
"""Phase 1c (deploy-readiness-gaps): spec <-> project DB-name consistency.

For each hub spec with ``shape.needs_database``, the orchestrator now provisions
the database named ``(spec.depends.postgres or spec_id.replace("-","_"))``
(see ``orchestrator/infrastructure.py`` ``_provision_postgres``). This check
verifies that resolved name matches the project's OWN runtime DB name — the
``PG_DATABASE`` / ``POSTGRES_DB`` key, or the ``DATABASE_URL`` path, in the
project's ``.env.example``.

That mismatch is exactly the class of bug that left calendar pointed at an
empty/wrong DB: ``fabrik apply`` provisioned + injected one name while the app's
runtime config expected another, so ``/api/health`` passed (``SELECT 1``) but
every real endpoint 500'd.

Runs from ``final_gate.py`` at ``/opt/fabrik``. Skips cleanly (exit 0) where
there's no ``specs/services/`` directory (every non-fabrik project the
enforcement set is synced to), and skips any spec whose project ``.env`` doesn't
declare a DB name (nothing to compare).
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — PyYAML is a fabrik dep; skip if absent
    print("[skip] PyYAML not available — cannot parse specs")
    raise SystemExit(0) from None

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SPECS_DIR = REPO_ROOT / "specs" / "services"
OPT_ROOT = Path("/opt")
DB_ENV_KEYS = ("PG_DATABASE", "POSTGRES_DB")


def _project_db_name(project_dir: Path) -> str | None:
    """Best-effort extract the project's runtime DB name from its .env(.example)."""
    for env_file in (project_dir / ".env.example", project_dir / ".env"):
        if not env_file.is_file():
            continue
        text = env_file.read_text(encoding="utf-8", errors="replace")
        for key in DB_ENV_KEYS:
            m = re.search(rf"(?m)^[ \t]*{key}=([A-Za-z0-9_]+)", text)
            if m:
                return m.group(1)
        # Pull the dbname path segment out of a DATABASE_URL (creds/host elided).
        m = re.search(r"(?m)^[ \t]*DATABASE_URL=\S*@[^/]+/([A-Za-z0-9_]+)", text)
        if m:
            return m.group(1)
    return None


def main() -> int:
    if not SPECS_DIR.is_dir():
        print(f"[skip] no specs/services/ dir at {SPECS_DIR} — nothing to check")
        return 0

    specs = sorted(SPECS_DIR.glob("*.yaml"))
    mismatches: list[tuple[str, str, str]] = []
    compared = 0
    for spec_file in specs:
        try:
            spec = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        shape = spec.get("shape") or {}
        if not shape.get("needs_database"):
            continue
        spec_id = spec.get("id") or spec_file.stem
        expected = (spec.get("depends", {}) or {}).get("postgres") or spec_id.replace("-", "_")
        actual = _project_db_name(OPT_ROOT / spec_id)
        if actual is None:
            continue  # no project-side DB name to compare against
        compared += 1
        if actual != expected:
            mismatches.append((spec_id, expected, actual))

    if mismatches:
        print(
            "spec <-> project DB-name DRIFT — the orchestrator will provision the "
            "spec-resolved name while the app connects to the project name:"
        )
        for sid, exp, act in mismatches:
            print(f"  ✗ {sid}: spec resolves to '{exp}' but project .env uses '{act}'")
        print(
            "Fix: set spec.depends.postgres to the project's DB name (or align the "
            "project's PG_DATABASE/DATABASE_URL), then re-apply."
        )
        return 1

    print(f"spec <-> project DB names consistent ({compared} compared, {len(specs)} specs scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
