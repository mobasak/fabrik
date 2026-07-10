#!/usr/bin/env python3
# AFTER-EDIT: none
"""Force-fill advisory — WARN when a seeded doc still carries template placeholders AFTER its
Doc Sync Matrix trigger fired in the staged change.

A freshly-scaffolded doc stub (``[Project Name]``, ``YYYY-MM-DD`` …) is fine — until the change
that *should* have filled it ships. This catches the stub that silently rots past the moment it
became relevant: e.g. you add an API route (QUICKSTART's trigger) but ``docs/QUICKSTART.md`` is
still the pristine template.

Design:
- The docs checked are the intersection of (a) the SSOT registry (``_doc_registry.PROJECT_DOCS``)
  and (b) the docs for which we have a *mechanical* trigger detector below — so a doc renamed or
  removed from the registry automatically drops out (no drift), and fuzzy-trigger docs
  (BUSINESS_MODEL etc., no reliable code signal) are deliberately not nudged. ``_staged`` and the
  route detector are reused from ``check_doc_sync``; the compose/env/schema filename detectors are
  local (check_doc_sync does not expose them as helpers).
- ADVISORY ONLY — always exits 0 (never blocks a project's gate). Fail-safe: ANY git / parse /
  IO / import error → exit 0 (a doc-stub nudge must never break a commit).
- Registered advisory in ``final_gate.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # same-dir siblings: check_doc_sync + _doc_registry
    sys.path.insert(0, str(_HERE))

# Placeholder sentinels a scaffolded-but-unfilled doc still carries. Deliberately the NAME
# tokens only: scaffold seeding already substitutes ``[Project Name]``/``YYYY-MM-DD`` at seed
# time, and a date format like ``YYYY-MM-DD`` / ``[DATE]`` legitimately appears in a *filled*
# doc (e.g. data-contract documenting a DATE column), so treating dates as "unfilled" false-WARNs
# fleet-wide. The bracketed/braced NAME tokens survive seeding and never appear in filled prose.
PLACEHOLDERS: tuple[str, ...] = (
    "[Project Name]",
    "[PROJECT_NAME]",
    "{PROJECT_NAME}",
)


def _has_placeholder(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return any(ph in text for ph in PLACEHOLDERS)


def _trigger_detectors() -> dict[str, object]:
    """Map registry doc name → a predicate(staged: list[str]) that is True when the doc's
    Doc-Sync trigger fired. Only docs with a *mechanical* trigger are covered (fuzzy-trigger
    docs like BUSINESS_MODEL have no reliable code signal — nudging them would be noise)."""
    import check_doc_sync as ds  # same-dir sibling (the proven Doc-Sync detectors)

    def _compose(staged: list[str]) -> bool:
        return any(Path(f).name in {"compose.yaml", "compose.yml"} for f in staged)

    def _env(staged: list[str]) -> bool:
        return any(Path(f).name in {".env.example", ".env"} for f in staged)

    def _schema(staged: list[str]) -> bool:
        return any(
            f.endswith(".sql") or "migration" in f.lower() or "alembic" in f.lower() for f in staged
        )

    return {
        "docs/QUICKSTART.md": ds._has_route_change,
        "docs/CONFIGURATION.md": _env,
        "docs/data-contract.md": _schema,
        "docs/SERVICES.md": _compose,
        "docs/OPERATIONS.md": _compose,
    }


def main() -> int:
    try:
        import check_doc_sync as ds

        staged = ds._staged()
        if not staged:
            return 0
        root = Path.cwd()
        # Intersect the mechanically-detectable docs with the SSOT registry, so a doc renamed
        # or removed from _doc_registry automatically stops being checked (no drift). Fail-open:
        # if the registry can't be imported, check all detectors (an advisory must never vanish
        # for the wrong reason, but it also must never crash — see the outer except).
        try:
            import _doc_registry  # same-dir sibling

            registry_names = {r.name for r in _doc_registry.PROJECT_DOCS}
        except Exception:  # noqa: BLE001
            registry_names = None
        warns: list[str] = []
        for doc, fired in _trigger_detectors().items():
            if registry_names is not None and doc not in registry_names:
                continue  # doc left the registry SSOT → no longer checked
            try:
                if fired(staged):  # type: ignore[operator]
                    p = root / doc
                    if p.exists() and _has_placeholder(p):
                        warns.append(doc)
            except Exception:  # noqa: BLE001 — one detector failing must not sink the check
                continue
        for doc in warns:
            print(
                f"⚠️  {doc}: its Doc-Sync trigger fired but it still carries template "
                f"placeholders — fill the stub (advisory)."
            )
    except Exception:  # noqa: BLE001 — fail-safe: never block a gate on a doc-stub check
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
