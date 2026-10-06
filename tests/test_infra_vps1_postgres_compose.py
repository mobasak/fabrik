# AFTER-EDIT: none
"""T02 (PG18 fleet upgrade plan) — pins the hub's repo-mirror compose files to the PG18
cluster + exporter shape described in docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
§ The delta › D1 step 4 and § Compatibility checks.

These files are never applied by `fabrik apply` or synced to the hub — they are the repo's
record of the hand-edit the operator makes on the hub VPS during the D1 window (spec D1 step
4: "no sync or `fabrik apply` touches it until D3 merges"). The branch merges after that
window. This suite only parses the YAML and asserts shape; it never touches a live host, a
docker volume, or a database.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
POSTGRES_COMPOSE = REPO / "infra" / "vps1" / "postgres" / "compose.yaml"
MONITORING_COMPOSE = REPO / "infra" / "vps1" / "monitoring" / "compose.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_postgres_main_runs_pg18_on_the_new_external_volume() -> None:
    """Given infra/vps1/postgres/compose.yaml, when it is parsed, then postgres-main runs
    postgres:18.6-alpine, mounts the external volume postgres18-data at /var/lib/postgresql,
    keeps deploy.resources.limits.memory, container_name and the fabrik network, and no
    service mounts anything at /var/lib/postgresql/data (spec § The delta › D1 step 4)."""
    doc = _load(POSTGRES_COMPOSE)
    service = doc["services"]["postgres-main"]

    assert service["image"] == "postgres:18.6-alpine"
    assert service["container_name"] == "postgres-main"
    assert "fabrik" in service["networks"]
    assert service["deploy"]["resources"]["limits"]["memory"] == "2G"

    assert "postgres18-data:/var/lib/postgresql" in service["volumes"]
    assert doc["volumes"]["postgres18-data"]["external"] is True

    for svc in doc["services"].values():
        for mount in svc.get("volumes", []):
            assert not mount.endswith(":/var/lib/postgresql/data"), (
                f"a service still mounts the old PGDATA path: {mount!r}"
            )


def test_postgres_main_keeps_healthcheck_and_mesh_port_unchanged() -> None:
    """The ticket's DO-NOT / Scope invariants beyond the two Behavior Contract bullets:
    the healthcheck and the mesh-only port publication are untouched by the PG18 bump."""
    service = _load(POSTGRES_COMPOSE)["services"]["postgres-main"]

    assert service["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U postgres"]
    assert service["ports"] == ["10.99.0.1:5432:5432"]


def test_postgres_main_declares_platform_linux_amd64() -> None:
    """Review fixup A1: .windsurf/rules/core/30-ops.md:151 makes `platform: linux/amd64`
    mandatory for every VPS compose service; every monitoring service already carries it,
    but postgres-main predates that rule and was missed. The operator hand-applies this
    file in the D1 window, so the repo mirror must carry the pin too."""
    service = _load(POSTGRES_COMPOSE)["services"]["postgres-main"]

    assert service["platform"] == "linux/amd64"


def test_postgres_exporter_runs_v0_20_1_with_stat_checkpointer_collector() -> None:
    """Given infra/vps1/monitoring/compose.yaml, when it is parsed, then postgres-exporter
    runs prometheuscommunity/postgres-exporter:v0.20.1 with --collector.stat_checkpointer
    and keeps its memory limit (spec § Compatibility checks)."""
    doc = _load(MONITORING_COMPOSE)
    service = doc["services"]["postgres-exporter"]

    assert service["image"] == "prometheuscommunity/postgres-exporter:v0.20.1"
    assert "--collector.stat_checkpointer" in service["command"]
    assert service["deploy"]["resources"]["limits"]["memory"] == "64M"
