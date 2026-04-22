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
import shlex

from fabrik.drivers.locks import run_locked

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
"""Skipped paths for every plan. Kept conservative to avoid backing up
ephemeral junk. Caller can pass ``excludes`` to override entirely."""


def _plan_json(
    plan_id: str,
    paths: list[str],
    repo: str,
    schedule_cron: str,
    excludes: tuple[str, ...],
) -> str:
    """Render the Backrest plan as a JSON string ready for jq --argjson."""
    plan = {
        "id": plan_id,
        "repo": repo,
        "paths": list(paths),
        "excludes": list(excludes),
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
sudo docker restart $(sudo docker ps --format '{{{{.Names}}}}' | grep '^backrest-')
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
sudo docker restart $(sudo docker ps --format '{{{{.Names}}}}' | grep '^backrest-')
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


__all__ = (
    "BACKREST_CONFIG",
    "DEFAULT_REPO",
    "DEFAULT_CRON",
    "DEFAULT_EXCLUDES",
    "add_backup_plan",
    "remove_backup_plan",
)
