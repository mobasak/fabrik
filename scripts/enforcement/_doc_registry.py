#!/usr/bin/env python3
# AFTER-EDIT: scripts/enforcement/check_structure.py, src/fabrik/scaffold.py, scripts/enforcement/check_doc_stubs.py
"""Canonical, type-aware project-doc registry — the single source of truth (SSOT).

Every surface that lists "which docs a project has / allows / must update" DERIVES
from ``PROJECT_DOCS`` here, so they can never drift again:

  - ``src/fabrik/scaffold.py`` seeds a doc only when the project's type is in a bucket
    the row's ``applies_to`` covers (type-aware seeding).
  - ``scripts/enforcement/check_structure.py`` derives its ``docs/`` allowlist from
    :func:`docs_allowlist` instead of hard-coding a second copy.
  - ``scripts/enforcement/check_doc_stubs.py`` reads each row's ``trigger`` to decide
    force-fill WARNs.
  - ``CLAUDE.md``'s Doc Sync Matrix is the human-readable rendering of the rows' triggers.

STDLIB-ONLY by contract: this module is synced fleet-wide into ``scripts/enforcement/``
and imported by ``check_structure``/``check_doc_stubs`` running inside a *bare* project
(only the standard library is guaranteed there). It must stay pure data + stdlib helpers
— no third-party or heavy ``fabrik`` imports, and nothing here may touch the filesystem
at import time (the template-existence check lives in the tests, hub-side only).
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------------------
# Type buckets over the real SCAFFOLD_TYPES (src/fabrik/scaffold.py:137 — keep in sync).
# --------------------------------------------------------------------------------------
ALL_TYPES: frozenset[str] = frozenset(
    {
        "python-api",
        "python-api-gpu",
        "saas-skeleton",
        "node-api",
        "file-api",
        "file-worker",
        "wordpress",
        "docusaurus",
        "chrome-extension",
        "mobile-app",
        "desktop-app",
        "static-site",
    }
)

# deployed = runs a backend service → gets SERVICES/OPERATIONS/RESILIENCE/PORTS.
# Excludes the client-app types (chrome-extension/mobile-app/desktop-app) and the
# static-site types (docusaurus/static-site) — they ship no backend service.
_DEPLOYED: frozenset[str] = frozenset(
    {
        "python-api",
        "python-api-gpu",
        "node-api",
        "file-api",
        "file-worker",
        "saas-skeleton",
        "wordpress",
    }
)

# gui = has a user-facing UI surface (design-system + ui-design contracts apply).
_GUI: frozenset[str] = frozenset(
    {
        "saas-skeleton",
        "chrome-extension",
        "mobile-app",
        "desktop-app",
        "static-site",
        "docusaurus",
    }
)

# saas = the product/SaaS scaffold (BUSINESS_MODEL / STRATEGIC_BACKLOG).
_SAAS: frozenset[str] = frozenset({"saas-skeleton"})

# Bucket name → the set of SCAFFOLD_TYPES it covers. The ``data`` bucket is intentionally
# EMPTY: "is this project data-shaped?" is not a type property — it's the per-project
# ``shape.needs_database`` flag. So a data doc contributes to NO specific-type allowlist
# (a no-DB python-api is guaranteed none) and surfaces only in the permissive None-union
# that ``check_structure`` uses; seeding resolves it via ``seed_rows(..., needs_database=)``.
TYPE_BUCKETS: dict[str, frozenset[str]] = {
    "universal": ALL_TYPES,
    "deployed": _DEPLOYED,
    "gui": _GUI,
    "saas": _SAAS,
    "data": frozenset(),
}


def _bucket_types(bucket: str) -> frozenset[str]:
    """Types a bucket covers, for per-type allowlist derivation (``data`` → empty; it is
    db-driven, not type-driven, so it never enters a specific type's allowlist)."""
    return TYPE_BUCKETS.get(bucket, frozenset())


def _require_known_type(project_type: str) -> None:
    """Fail LOUD on an unknown/typo'd type instead of silently returning an empty set.
    A silent empty allowlist would make ``check_structure`` false-WARN every doc; a silent
    empty seed set would scaffold no docs — both are worse than a clear error."""
    if project_type not in ALL_TYPES:
        raise ValueError(
            f"unknown project_type {project_type!r} — expected one of {sorted(ALL_TYPES)}"
        )


@dataclass(frozen=True)
class DocRow:
    """One canonical project doc.

    name       project-relative path (e.g. ``docs/SERVICES.md`` or ``README.md``).
    template   source template, relative to ``templates/scaffold/`` (mirrors the
               ``SHARED_TEMPLATE_MAP`` key convention), or ``None`` for docs that are
               command-authored / inline / special (ui-design, PORTS, AGENTS, schema).
    applies_to bucket name(s) this doc belongs to (``universal``/``deployed``/``gui``/
               ``saas``/``data``).
    trigger    the Doc Sync Matrix "when to update" rule (human-readable).
    fills      who fills it: ``scaffold-stub`` | ``scaffold`` | ``agent`` |
               ``/fabrik-data-contract`` | ``/fabrik-ui-design`` | ``static``.
    """

    name: str
    template: str | None
    applies_to: frozenset[str]
    trigger: str
    fills: str


# --------------------------------------------------------------------------------------
# THE REGISTRY — the single source of truth (spec canonical table, grounded to real
# template paths under templates/scaffold/{,docs/,workflows/}).
# --------------------------------------------------------------------------------------
PROJECT_DOCS: tuple[DocRow, ...] = (
    # --- universal (all 12 types) ---
    DocRow(
        "README.md",
        "docs/PROJECT_README_TEMPLATE.md",
        frozenset({"universal"}),
        "project identity change",
        "scaffold-stub",
    ),
    DocRow(
        "INDEX.md",
        "docs/PROJECT_INDEX_TEMPLATE.md",
        frozenset({"universal"}),
        "file added/removed/renamed",
        "agent",
    ),
    DocRow(
        "docs/README.md",
        "docs/DOCS_INDEX_TEMPLATE.md",
        frozenset({"universal"}),
        "a doc added/removed",
        "agent",
    ),
    DocRow(
        "CHANGELOG.md",
        "docs/CHANGELOG_TEMPLATE.md",
        frozenset({"universal"}),
        "any code/Docker/deps change",
        "agent",
    ),
    DocRow("AGENTS.md", None, frozenset({"universal"}), "infra/topology change", "scaffold"),
    DocRow("AFCL.md", "AFCL_TEMPLATE.md", frozenset({"universal"}), "friction hit", "agent"),
    DocRow(
        "docs/QUICKSTART.md",
        "docs/QUICKSTART_TEMPLATE.md",
        frozenset({"universal"}),
        "API/SDK/CLI changed",
        "agent",
    ),
    DocRow(
        "docs/CONFIGURATION.md",
        "docs/CONFIGURATION_TEMPLATE.md",
        frozenset({"universal"}),
        "new env var (+ .env.example)",
        "agent",
    ),
    DocRow(
        "docs/TROUBLESHOOTING.md",
        "docs/TROUBLESHOOTING_TEMPLATE.md",
        frozenset({"universal"}),
        "recurring symptom",
        "agent",
    ),
    DocRow(
        "docs/FEATURES.md",
        "docs/FEATURES_TEMPLATE.md",
        frozenset({"universal"}),
        "feature shipped",
        "agent",
    ),
    DocRow(
        "docs/LESSONS_LEARNT.md",
        "docs/LESSONS_LEARNT_TEMPLATE.md",
        frozenset({"universal"}),
        "end of ticket/run",
        "agent",
    ),
    # (removed 2026-07-11: docs/workflows/kilo-consult-workflow.md — the `kilo consult`
    #  feature is superseded by the OpenRouter fabrik-lib consult module (run_agents), so its
    #  how-to is no longer seeded/synced to projects. Template archived in templates/.archive/;
    #  kilo_consult.py stays as a dormant tool.)
    # --- deployed (runs a backend service) ---
    DocRow(
        "docs/SERVICES.md",
        "docs/SERVICES_TEMPLATE.md",
        frozenset({"deployed"}),
        "compose service added/removed",
        "agent",
    ),
    DocRow(
        "docs/OPERATIONS.md",
        "docs/OPERATIONS_TEMPLATE.md",
        frozenset({"deployed"}),
        "compose service added/removed",
        "agent",
    ),
    DocRow(
        "docs/RESILIENCE.md",
        "docs/RESILIENCE_TEMPLATE.md",
        frozenset({"deployed"}),
        "resilience pattern changed",
        "agent",
    ),
    DocRow(
        "docs/DEPLOYMENT.md",
        "docs/DEPLOYMENT_TEMPLATE.md",
        frozenset({"deployed"}),
        "deploy config changed",
        "agent",
    ),
    DocRow("PORTS.md", None, frozenset({"deployed"}), "new port allocated", "agent"),
    # --- data (shape.needs_database) ---
    DocRow("db/schema.sql", None, frozenset({"data"}), "schema migration", "agent"),
    DocRow(
        "docs/data-contract.md",
        "docs/data-contract-template.md",
        frozenset({"data"}),
        "DB field/enum/model change",
        "/fabrik-data-contract",
    ),
    # --- gui (user-facing UI) ---
    DocRow(
        "docs/ui-design.md", None, frozenset({"gui"}), "screen/flow/UI change", "/fabrik-ui-design"
    ),
    DocRow(
        "docs/flows.md",
        None,
        frozenset({"universal"}),
        "journey/persona/flow change",
        "/fabrik-flows",
    ),
    DocRow(
        "docs/design-system.md", None, frozenset({"gui"}), "brand/token change", "/fabrik-ui-design"
    ),
    # --- saas (product) ---
    DocRow(
        "docs/BUSINESS_MODEL.md",
        "docs/BUSINESS_MODEL_TEMPLATE.md",
        frozenset({"saas"}),
        "pricing/positioning change",
        "agent",
    ),
    DocRow(
        "docs/STRATEGIC_BACKLOG.md",
        "docs/STRATEGIC_BACKLOG_TEMPLATE.md",
        frozenset({"saas"}),
        "deferred-work / session findings",
        "agent",
    ),
)

# Recognized-standard legacy doc basenames that older fleet projects already carry but
# that are NOT in the derived registry allowlist. Grounded against the live fleet
# (`for d in /opt/*/docs/*.md; do basename "$d"; done | sort -u`, 2026-07-11). These are
# TOLERATED (advisory, never a hard fail) so a registry change does not start WARNing on
# projects that are clean today — the grandfather / no-regression guarantee. This is a
# SMALL explicit set of once-standard names, NOT "every doc any project happens to carry"
# (genuinely-misplaced one-offs like notes.md/tickets.md correctly keep WARNing).
LEGACY_TOLERATED: frozenset[str] = frozenset(
    {
        "lessons-learnt.md",  # naming drift → canonical LESSONS_LEARNT.md
        "lessons_learnt.md",  # naming drift
        "API_REFERENCE.md",  # retired template (→ QUICKSTART + live /docs)
        "HANDOVER.md",  # legacy handover doc
        "FINANCIALS.md",  # Traycer-workflow doc, out of scaffold scope
        "FAQ.md",  # phantom-allowlist legacy (was in check_structure allowlist)
        "EXTERNAL_SYSTEMS.md",  # phantom-allowlist legacy
        "TESTING.md",  # phantom-allowlist legacy
        "owner_ozgur_basak.md",  # operator marker, in today's allowlist
    }
)


def docs_allowlist(project_type: str | None = None, needs_database: bool = False) -> frozenset[str]:
    """Basenames of docs that legitimately live *directly* in ``docs/`` for a project
    of ``project_type`` (or the full union across all types when ``project_type`` is
    ``None``).

    ``check_structure.py`` calls this with **no argument** (the permissive None-union) so
    it never false-WARNs a recognized doc regardless of the project's exact shape — that is
    where the grandfather / no-regression guarantee lives. A caller that DOES know the
    project's type may pass it for a stricter set; ``needs_database`` then symmetrically
    (with :func:`seed_rows`) includes the ``data`` docs a DB-backed project legitimately
    carries — without it, ``data`` docs never enter a per-type allowlist (a no-DB
    python-api is guaranteed none).

    Root-level docs (README/INDEX/CHANGELOG/PORTS/AGENTS/AFCL) and ``docs/<subdir>/*`` files
    are handled by ``check_structure``'s ``ALLOWED_ROOT_MD`` / ``VALID_DOCS_SUBDIRS``
    respectively — this returns only the flat ``docs/*.md`` set. Callers typically union the
    result with :data:`LEGACY_TOLERATED`.
    """
    if project_type is not None:
        _require_known_type(project_type)  # fail loud on a typo'd type, never silent-empty
    out: set[str] = set()
    for row in PROJECT_DOCS:
        parts = row.name.split("/")
        if len(parts) != 2 or parts[0] != "docs":
            continue  # only flat docs/*.md — root + subdir docs handled elsewhere
        if project_type is None:
            out.add(parts[1])  # permissive full union (needs_database is a no-op here)
            continue
        matched = False
        for bucket in row.applies_to:
            if bucket == "data":
                if needs_database:
                    matched = True
            elif project_type in _bucket_types(bucket):
                matched = True
        if matched:
            out.add(parts[1])
    return frozenset(out)


def seed_rows(project_type: str, needs_database: bool = False) -> tuple[DocRow, ...]:
    """Registry rows a scaffolder should SEED for ``project_type`` — i.e. rows with a real
    ``template`` whose bucket the type belongs to. The ``data`` bucket is honored only when
    ``needs_database`` is true (matching ``shape.needs_database``). Rows with ``template is
    None`` (command-authored / inline / special) are never seeded here.

    Note: ``scaffold.py`` may apply additional overrides on top (e.g. the
    ``_NO_DATA_CONTRACT_TYPES`` leak guard for docusaurus) — this returns the type-matched
    template set; the scaffolder owns final leak/override policy.
    """
    _require_known_type(project_type)  # fail loud on a typo'd type, never silent-empty
    out: list[DocRow] = []
    for row in PROJECT_DOCS:
        if row.template is None:
            continue
        matched = False
        for bucket in row.applies_to:
            if bucket == "data":
                if needs_database:
                    matched = True
            elif project_type in _bucket_types(bucket):
                matched = True
        if matched:
            out.append(row)
    return tuple(out)
