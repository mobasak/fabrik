"""Backrest backup-plan provisioning — atomic under flock + jq on the VPS.

Adds / removes a plan in ``/opt/backrest/config/config.json`` with three
guarantees the earlier Python-chain design could not provide:

1. **Concurrency-safe** — the entire read-modify-validate-write cycle
   runs as one bash script under :func:`fabrik.drivers.locks.run_locked`.
   Two concurrent ``fabrik apply`` invocations serialize on the shared
   ``/tmp/fabrik-backrest-config.lock`` file instead of racing to write
   the same JSON document.
2. **Atomic** — ``jq`` writes to a ``.tmp`` sibling, ``python3 -m json.tool``
   validates the result, and only then is ``mv`` used to replace the
   live file. On validation failure the ``.tmp`` is deleted and the
   previous ``.bak.{ts}`` is restored; the script exits non-zero so the
   caller sees the failure.
3. **Escape-free** — the new-plan JSON is handed to the VPS as base64,
   decoded inline, and piped into ``jq --argjson``. No shell quoting
   hazards (embedded single quotes, unicode, newlines) reach the script.

Design notes
------------
* Backrest's config embeds live B2 credentials, so the directory is
  explicitly **excluded** from :data:`fabrik.drivers.locks.GIT_VERSIONED_DIRS`.
  Rollback relies on timestamped ``.bak.{ts}`` files, never git.
* The last 10 ``.bak.{ts}`` files are retained; older ones are pruned
  inside the same locked script. This keeps disk usage bounded without
  losing the recent-history safety net.
* The Backrest container has a Coolify UUID suffix; it is resolved by
  prefix match (``^backrest-``) at script runtime, not baked into a
  constant, so a container re-create does not break the driver.
* ``jq`` is a Phase 4d dependency — verified present at ``/usr/bin/jq``
  on the VPS 2026-04-18 and re-verified 2026-04-19. The plan upgrade
  path assumes Debian's ``jq`` package remains installed.
* **No direct secret transmission.** The B2 repository (``b2-vps1``) is
  already registered in Backrest with its credentials; we only add a
  plan that references it by name. No AWS/B2 keys are touched by this
  driver.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import shlex

from fabrik.drivers.locks import run_locked
from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

BACKREST_CONFIG = "/opt/backrest/config/config.json"
"""Live Backrest config path on the VPS. Secret-bearing (B2 credentials) —
do NOT add this to ``GIT_VERSIONED_DIRS``."""

DEFAULT_REPO = "b2-vps1"
"""Default Backrest repository name. Matches the repo registered in the
config 2026-04-13 at initial Backrest deploy."""

DEFAULT_CRON = "0 3 * * *"
"""Daily at 03:00 UTC+3 (default VPS timezone). Avoids peak hours and
aligns with the existing Backrest baseline audit (2026-04-17)."""

DEFAULT_EXCLUDES: tuple[str, ...] = ("**/cache", "**/*.log", "**/tmp")

# Default retention policy — prevents unbounded snapshot accumulation.
# Backrest uses a protobuf oneof: policyKeepLastN | policyTimeBucketed | policyKeepAll.
# We use policyTimeBucketed with daily/weekly/monthly counts.
# Source: github.com/garethgeorge/backrest/proto/v1/config.proto → RetentionPolicy
DEFAULT_RETENTION: dict = {"policyTimeBucketed": {"daily": 7, "weekly": 4, "monthly": 6}}
"""Skipped paths for every plan. Kept conservative to avoid backing up
ephemeral junk. Caller can pass ``excludes`` to override entirely."""


def _plan_json(
    plan_id: str,
    paths: list[str],
    repo: str,
    schedule_cron: str,
    excludes: tuple[str, ...],
    retention: dict | None = None,
) -> str:
    """Render the Backrest plan as a JSON string ready for jq --argjson."""
    plan = {
        "id": plan_id,
        "repo": repo,
        "paths": list(paths),
        "excludes": list(excludes),
        "retention": retention or DEFAULT_RETENTION,
        "schedule": {"cron": schedule_cron},
        "hooks": [
            {
                "conditions": ["CONDITION_ANY_ERROR"],
                "actionCommand": {
                    "command": (
                        "curl -s -X POST http://apprise:8000/notify/alerts "
                        "-H 'Content-Type: application/json' "
                        '-d \'{"title":"Backup failed: ' + plan_id + '",'
                        '"type":"failure"}\''
                    )
                },
            }
        ],
    }
    return json.dumps(plan)


def _build_add_script(payload_b64: str, plan_id: str) -> str:
    """Compose the locked bash script for atomic plan insertion.

    The script is one continuous bash block so ``flock`` holds the lock
    for every step. The plan JSON is passed as base64 to sidestep all
    shell-quoting hazards; it is decoded into an environment variable
    inside the script and consumed by ``jq --argjson``.
    """
    # Docker format tokens ``{{.Names}}`` must survive both the f-string
    # ({{{{ → {{) and the later ``shlex.quote`` inside run_locked.
    return f"""set -euo pipefail
CFG={BACKREST_CONFIG}

# 1. Idempotency
if sudo jq -e '.plans[]? | select(.id=={json.dumps(plan_id)})' "$CFG" >/dev/null 2>&1; then
    echo EXISTS
    exit 0
fi

# 2. Timestamped backup
BAK="$CFG.bak.$(date +%Y%m%d-%H%M%S)"
sudo cp "$CFG" "$BAK"

# 3. Mutate via jq -> tmp (new plan decoded from base64 to bypass shell quoting)
NEW_PLAN=$(echo {shlex.quote(payload_b64)} | base64 -d)
sudo jq --argjson p "$NEW_PLAN" '.plans = ((.plans // []) + [$p])' "$CFG" \\
    | sudo tee "$CFG.tmp" >/dev/null

# 4. Validate — if json.tool rejects, restore from .bak and exit non-zero
if ! sudo python3 -m json.tool "$CFG.tmp" >/dev/null; then
    sudo rm -f "$CFG.tmp"
    sudo cp "$BAK" "$CFG"
    echo CORRUPT_RESTORED >&2
    exit 1
fi

# 5. Atomic replace
sudo mv "$CFG.tmp" "$CFG"

# 6. Prune — keep last 10 timestamped backups
sudo bash -c 'ls -t '"$CFG"'.bak.* 2>/dev/null | tail -n +11 | xargs -r rm -f' || true

# 7. Restart Backrest (UUID-suffixed, prefix-matched at runtime)
sudo docker restart $(sudo docker ps --format '{{{{.Names}}}}' | grep -E '^backrest(-|$)')
echo CREATED
"""


def _build_remove_script(plan_id: str) -> str:
    """Compose the locked bash script for idempotent plan removal."""
    return f"""set -euo pipefail
CFG={BACKREST_CONFIG}

# Idempotency — if no plan with this id, do nothing
if ! sudo jq -e '.plans[]? | select(.id=={json.dumps(plan_id)})' "$CFG" >/dev/null 2>&1; then
    echo NOT_FOUND
    exit 0
fi

BAK="$CFG.bak.$(date +%Y%m%d-%H%M%S)"
sudo cp "$CFG" "$BAK"
sudo jq 'del(.plans[] | select(.id=={json.dumps(plan_id)}))' "$CFG" \\
    | sudo tee "$CFG.tmp" >/dev/null
if ! sudo python3 -m json.tool "$CFG.tmp" >/dev/null; then
    sudo rm -f "$CFG.tmp"
    sudo cp "$BAK" "$CFG"
    echo CORRUPT_RESTORED >&2
    exit 1
fi
sudo mv "$CFG.tmp" "$CFG"
sudo bash -c 'ls -t '"$CFG"'.bak.* 2>/dev/null | tail -n +11 | xargs -r rm -f' || true
sudo docker restart $(sudo docker ps --format '{{{{.Names}}}}' | grep -E '^backrest(-|$)')
echo REMOVED
"""


def add_backup_plan(
    plan_id: str,
    paths: list[str],
    repo: str = DEFAULT_REPO,
    schedule_cron: str = DEFAULT_CRON,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
    dry_run: bool = False,
) -> dict:
    """Add a Backrest plan atomically under a VPS-side ``flock``.

    See module docstring for the full safety chain. Idempotent on ``plan_id``:
    a repeat call with the same ID returns ``status=exists``.

    Args:
        plan_id: Unique plan identifier (e.g. ``"my-project-data"``).
        paths: Absolute paths on the VPS to back up.
        repo: Backrest repository name (registered at Backrest deploy).
            Default ``b2-vps1``.
        schedule_cron: Five-field cron expression. Default daily at 03:00.
        excludes: Exclude globs. Default ``("**/cache", "**/*.log", "**/tmp")``.
        dry_run: Skip VPS mutation and return a dry-run marker.

    Returns:
        ``{"status": "created" | "exists" | "dry_run", "plan": plan_id}``.

    Raises:
        ValueError: ``plan_id`` is empty / non-string, or ``paths`` empty.
        RuntimeError: Lock acquisition timed out, script exited non-zero,
            or ``python3 -m json.tool`` rejected the rendered config
            (``CORRUPT_RESTORED`` stderr marker surfaces in the message).
    """
    if not isinstance(plan_id, str) or not plan_id:
        raise ValueError(f"plan_id must be a non-empty string, got {plan_id!r}")
    if not paths or not all(isinstance(p, str) and p for p in paths):
        raise ValueError(f"paths must be a non-empty list of strings, got {paths!r}")

    if dry_run:
        logger.info("[DRY RUN] Would add Backrest plan: %s (paths=%s)", plan_id, paths)
        return {"status": "dry_run", "plan": plan_id}

    payload = _plan_json(
        plan_id=plan_id,
        paths=paths,
        repo=repo,
        schedule_cron=schedule_cron,
        excludes=excludes,
    )
    payload_b64 = base64.b64encode(payload.encode()).decode()

    script = _build_add_script(payload_b64, plan_id)
    out = run_locked("backrest-config", script, timeout=120)

    status = "exists" if "EXISTS" in out else "created"
    logger.info("Backrest plan %s: status=%s", plan_id, status)
    return {"status": status, "plan": plan_id}


def remove_backup_plan(plan_id: str, dry_run: bool = False) -> bool:
    """Rollback handler — remove a plan by ID under the same lock.

    Best-effort: catches ``RuntimeError`` from the underlying
    :func:`run_locked` call, logs a warning, and returns ``False`` so
    the rollback orchestrator can continue unwinding other registrars.

    Args:
        plan_id: Plan identifier to delete.
        dry_run: Log intent and return True.

    Returns:
        True on success or no-op removal, False on lock / script failure.
    """
    if not isinstance(plan_id, str) or not plan_id:
        raise ValueError(f"plan_id must be a non-empty string, got {plan_id!r}")

    if dry_run:
        logger.info("[DRY RUN] Would remove Backrest plan: %s", plan_id)
        return True

    script = _build_remove_script(plan_id)
    try:
        out = run_locked("backrest-config", script, timeout=120)
        if "NOT_FOUND" in out:
            logger.info("Backrest plan not present (no-op): %s", plan_id)
        else:
            logger.info("Removed Backrest plan: %s", plan_id)
        return True
    except RuntimeError as e:
        logger.warning("Backrest rollback failed (non-fatal): %s", e)
        return False


# ---------------------------------------------------------------------------
# Phase 6 of deploy-readiness-gaps plan (2026-06-30): per-DB Backrest plans.
#
# Layered ON TOP of the existing whole-cluster postgres-dumps plan. Each
# fabrik-created database gets its own plan at /opt/backups/postgres/<db>/.
# pre-backup.sh (operator one-time edit per the plan) writes the per-DB
# pg_dump file there; Backrest snapshots the directory daily.
# ---------------------------------------------------------------------------

_DB_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
"""Conservative shell-safe DB-name pattern.

Tighter than postgres._IDENT_RE (lower-case only, no leading underscore)
so the name is also safe inside the `for db in $(cat …)` loop in
pre-backup.sh — no shell metacharacters, no glob risk.
"""

POSTGRES_TRACKED_DBS = "/opt/backups/fabrik-tracked-dbs.txt"
"""Append-only registry of DB names fabrik-managed for per-DB backup.

pre-backup.sh reads this file each night and dumps each listed DB to
``/opt/backups/postgres/<db>/latest.dump``. register_postgres_plan()
appends; unregister_postgres_plan() removes.
"""

POSTGRES_PER_DB_CRON = "0 2 * * *"
"""Per-DB plan schedule — matches the existing whole-cluster
postgres-dumps plan (verified 2026-06-30 via SSH inventory of vps1).
"""


def _validate_db_name(db_name: str) -> None:
    """Pass-2 adversarial: a shell-special char would break the
    pre-backup.sh for-loop. Reject anything outside `[a-z][a-z0-9_]*`.
    """
    if not isinstance(db_name, str) or not _DB_NAME_RE.match(db_name):
        raise ValueError(
            f"Invalid db_name for backrest plan {db_name!r}: must match "
            "[a-z][a-z0-9_]{0,62} — shell-safe + matches pre-backup.sh loop"
        )


def _append_tracked_db(db_name: str) -> None:
    """Append db_name to /opt/backups/fabrik-tracked-dbs.txt via SSH,
    idempotently. `grep -qxF + echo` pattern avoids double-append on
    repeat calls. The db_name is pre-validated, so no shell injection."""
    _validate_db_name(db_name)
    cmd = (
        f"sudo touch {POSTGRES_TRACKED_DBS} && "
        f"sudo grep -qxF {db_name} {POSTGRES_TRACKED_DBS} || "
        f"echo {db_name} | sudo tee -a {POSTGRES_TRACKED_DBS} >/dev/null"
    )
    ssh(cmd, timeout=15)


def _remove_tracked_db(db_name: str) -> None:
    """Strip db_name's line from the tracked-DBs file. No-op if absent."""
    _validate_db_name(db_name)
    # -i with explicit pattern; db_name is pre-validated to alnum+underscore
    # so no sed-special characters to escape.
    cmd = (
        f"sudo touch {POSTGRES_TRACKED_DBS} && sudo sed -i '/^{db_name}$/d' {POSTGRES_TRACKED_DBS}"
    )
    ssh(cmd, timeout=15)


def register_postgres_plan(db_name: str) -> dict:
    """Register a per-DB Backrest plan + append db_name to the tracked-DBs file.

    Plan ID convention: ``postgres-<db_name>``. Path:
    ``/opt/backups/postgres/<db_name>/`` (created on-demand by pre-backup.sh).
    Schedule + retention inherit from the existing whole-cluster
    ``postgres-dumps`` plan so backup cadence stays consistent.

    Returns add_backup_plan's status dict (``{"status": "created"|"exists",
    "plan": "postgres-<db>"}``).

    Idempotent: a repeat call returns ``status: exists`` from the underlying
    add_backup_plan, and the tracked-DBs append is idempotent on its own
    via `grep -qxF`.
    """
    _validate_db_name(db_name)
    plan_id = f"postgres-{db_name}"
    path = f"/opt/backups/postgres/{db_name}/"
    result = add_backup_plan(
        plan_id=plan_id,
        paths=[path],
        repo=DEFAULT_REPO,
        schedule_cron=POSTGRES_PER_DB_CRON,
        # Per-DB plans hold only the dump file; the default cache/log/tmp
        # excludes don't apply. Empty tuple keeps the entire directory.
        excludes=(),
    )
    _append_tracked_db(db_name)
    return result


def unregister_postgres_plan(db_name: str) -> bool:
    """Mirror of register_postgres_plan, called from drop_database.

    Removes the per-DB plan AND scrubs the tracked-DBs file. The
    tracked-file scrub runs unconditionally — even if remove_backup_plan
    returned False (lock/script failure), the next register attempt for
    the same name must not double-append.
    """
    _validate_db_name(db_name)
    plan_id = f"postgres-{db_name}"
    plan_removed = remove_backup_plan(plan_id, dry_run=False)
    # Always scrub the tracked file, regardless of plan removal result.
    try:
        _remove_tracked_db(db_name)
    except Exception as exc:  # noqa: BLE001 — best-effort scrub
        logger.warning(
            "backrest: tracked-DBs scrub failed for %s (%s); next register may double-append",
            db_name,
            exc,
        )
    return plan_removed


__all__ = (
    "BACKREST_CONFIG",
    "DEFAULT_REPO",
    "DEFAULT_CRON",
    "DEFAULT_EXCLUDES",
    "DEFAULT_RETENTION",
    "POSTGRES_TRACKED_DBS",
    "POSTGRES_PER_DB_CRON",
    "add_backup_plan",
    "remove_backup_plan",
    "register_postgres_plan",
    "unregister_postgres_plan",
)
