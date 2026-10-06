"""T03 — the DR chain restores `postgres18-data`, never the retired `postgres-data`.

Spec: docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md § The delta › D3
(the DR-chain hunk) + D1 step 8. `postgres-main`'s data volume moves from `postgres-data` to
`postgres18-data` on the PG18 upgrade; every DR script and doc that names the volume must follow,
or a disaster recovery run in the gap between the compose cutover and this merge restores the
WRONG (empty, pre-cutover) volume name and `postgres-main` never boots.

`postgres-data` is kept until release as the Backrest safety copy (D1 step 8), so this is a
whole-word check: `postgres18-data` must never be mistaken for a match.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP_CONFIG = REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-config.sh"

# The six files T03 owns — every live `postgres-data` mention here must now read `postgres18-data`.
OWNED_FILES = [
    REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-config.sh",
    REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-hub.sh",
    REPO_ROOT / "src" / "fabrik" / "orchestrator" / "vultr_drill.py",
    REPO_ROOT / "docs" / "operations" / "hub-restore-inventory.md",
    REPO_ROOT / "docs" / "operations" / "disaster-recovery.md",
    REPO_ROOT / "docs" / "infrastructure" / "vps-hub-rebuild.md",
]

# Whole-word: `postgres18-data` must never match (the digits sit right after `postgres`,
# so a plain substring search would false-positive on the new name).
_POSTGRES_DATA_WHOLE_WORD = re.compile(r"(?<![\w-])postgres-data(?![\w-])")

DISASTER_RECOVERY_MD = REPO_ROOT / "docs" / "operations" / "disaster-recovery.md"


def test_bootstrap_config_restores_postgres18_data_not_postgres_data() -> None:
    """Sourcing bootstrap-config.sh must populate FABRIK_HUB_VOLUMES_TO_RESTORE with
    `postgres18-data`, and must NOT still carry the retired `postgres-data` name."""
    assert BOOTSTRAP_CONFIG.is_file(), f"missing {BOOTSTRAP_CONFIG}"
    script = (
        f'source "{BOOTSTRAP_CONFIG}" && '
        'printf "%s\\n" "${FABRIK_HUB_VOLUMES_TO_RESTORE[@]}"'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"sourcing bootstrap-config.sh failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    volumes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert "postgres18-data" in volumes, (
        f"FABRIK_HUB_VOLUMES_TO_RESTORE is missing postgres18-data: {volumes}"
    )
    assert "postgres-data" not in volumes, (
        f"FABRIK_HUB_VOLUMES_TO_RESTORE still carries the retired postgres-data: {volumes}"
    )


def test_no_owned_file_names_the_retired_postgres_data_volume() -> None:
    """Whole-word scan (so `postgres18-data` never false-matches) over every file T03 owns —
    comments, log strings, and docs included. A surviving `postgres-data` mention means a DR run
    in the gap between the compose cutover and this merge would restore the wrong volume."""
    offenders: list[str] = []
    for path in OWNED_FILES:
        assert path.is_file(), f"missing owned file: {path}"
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _POSTGRES_DATA_WHOLE_WORD.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "retired `postgres-data` mention(s) survive:\n" + "\n".join(offenders)


def test_disaster_recovery_volume_count_comment_says_eleven() -> None:
    """The docker-volumes restore-loop comment must say 11 — the Backrest plan backs up both
    Postgres volumes until release (10 + 1), even though the restore loop itself only lists 10."""
    lines = DISASTER_RECOVERY_MD.read_text().splitlines()
    count_lines = [line for line in lines if "docker-volumes plan" in line and "backs up" in line]
    assert count_lines, (
        "could not find the docker-volumes plan count comment in "
        f"{DISASTER_RECOVERY_MD.relative_to(REPO_ROOT)}"
    )
    assert any("11" in line for line in count_lines), (
        f"volume-count comment does not say 11: {count_lines}"
    )
