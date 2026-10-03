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
import contextlib
import fnmatch
import json
import logging
import os
import re
import shlex
from collections.abc import Iterator
from dataclasses import dataclass

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
    if not isinstance(db_name, str) or not _DB_NAME_RE.fullmatch(db_name):
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


# ---------------------------------------------------------------------------
# Coverage — read-only (W-5c4ad6a6, D-518). The registrar warns and the audit
# reports; nothing below writes, edits or deletes a plan. A plan is trusted only
# when Backrest can actually run it over a path; a doubt reads "uncovered", which
# costs a warning, never a false "present".
# ---------------------------------------------------------------------------

_SERVICE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
"""The deployer's service-name pattern (``orchestrator/deployer_ssh.py:31``)."""

_ANON_VOLUME_RE = re.compile(r"^[0-9a-f]{64}$")
_UNSAFE_EXCLUDE_CHARS = frozenset("[\\$!")
"""Brackets, escapes, env expansion and negation read differently in Python and restic."""

_PLANS_JQ = (
    "[.plans[]? | {id, paths: (.paths // []), excludes: (.excludes // []), "
    "iexcludes: (.iexcludes // []), backup_flags: (.backup_flags // []), "
    "scheduled: ((.schedule // {}) | length > 0), disabled: (.schedule.disabled // false)}]"
)
"""Plan fields only — the repo section of config.json (B2 credentials) never leaves the VPS."""


@dataclass(frozen=True)
class Persistence:
    """What a service persists on its host: container count, data paths, skipped anonymous volumes."""

    containers: int
    paths: list[str]
    anonymous: int


def _norm(path: str) -> str:
    return path.rstrip("/") or "/"


def _discovery_script(name: str) -> str:
    q = shlex.quote
    return (
        "set -eo pipefail\n"
        f"ids=$(sudo docker ps -aq --filter {q('label=com.docker.compose.project=' + name)})\n"
        f'if [ -z "$ids" ]; then ids=$(sudo docker ps -aq --filter {q("name=^" + name + "$")}); fi\n'
        'if [ -z "$ids" ]; then echo NOCONTAINERS; exit 0; fi\n'
        'echo "containers|$(echo $ids | wc -w)"\n'
        "sudo docker inspect --format "
        "'{{range .Mounts}}{{.Type}}|{{.Name}}|{{.RW}}|{{.Source}}{{\"\\n\"}}{{end}}' $ids"
        " | while IFS='|' read -r t n rw src; do\n"
        '  case "$t" in\n'
        '    volume) printf \'volume|%s|%s\\n\' "$n" "$src" ;;\n'
        '    bind) src=$(sudo readlink -f -- "$src" || printf \'%s\' "$src")\n'
        '      if [ "$rw" = true ] && { sudo test -d "$src" || sudo test -f "$src"; }; then\n'
        "        printf 'bind|-|%s\\n' \"$src\"\n"
        "      fi ;;\n"
        "  esac\n"
        "done\n"
    )


def discover_persistence(name: str) -> Persistence | None:
    """Ask Docker what service ``name`` persists: named volumes and writable bind directories and files.

    A bind source is resolved (``readlink -f``) first: restic stores a symlink as a link, not its target's data. A source
    ``readlink`` cannot resolve (a missing parent) keeps its literal path and then fails ``test -d``/``-f``: skipped, never fatal.

    One SSH call; ``None`` when it fails (never a guess). Zero containers is its own answer.
    """
    if not isinstance(name, str) or not _SERVICE_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid service name {name!r}")
    try:
        out = ssh(f"bash -o pipefail -c {shlex.quote(_discovery_script(name))}", timeout=60)
    except Exception as exc:  # noqa: BLE001 — a failed probe is "unknown", never a guess
        logger.warning("backrest: discovery for %s failed: %s", name, exc)
        return None
    if out.strip() == "NOCONTAINERS":
        return Persistence(0, [], 0)
    paths: set[str] = set()
    anonymous = 0
    containers = 0
    for line in out.splitlines():
        if line.startswith("containers|"):
            containers = int(line.split("|", 1)[1].strip() or 0)
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        kind, vol_name, src = parts
        if kind == "volume" and _ANON_VOLUME_RE.fullmatch(vol_name):
            anonymous += 1
        elif src:
            paths.add(_norm(src))
    return Persistence(containers, sorted(paths), anonymous)


def read_plans() -> list[dict] | None:
    """The host's Backrest plans, plan fields only; ``None`` when the read fails."""
    try:
        out = ssh(f"sudo jq -c {shlex.quote(_PLANS_JQ)} {shlex.quote(BACKREST_CONFIG)}", timeout=30)
        plans = json.loads(out)
    except Exception as exc:  # noqa: BLE001
        logger.warning("backrest: reading plans failed: %s", exc)
        return None
    return plans if isinstance(plans, list) else None


def visible(paths: list[str]) -> set[str] | None:
    """The subset of ``paths`` Backrest itself can stat (``test -e`` inside its container); ``None`` on failure."""
    if not paths:
        return set()
    script = (
        "set -o pipefail\n"
        "c=$(sudo docker ps --format '{{.Names}}' | grep -E '^backrest(-|$)' | head -1) || true\n"
        '[ -n "$c" ] || { echo "no running backrest container" >&2; exit 1; }\n'
        'sudo docker exec "$c" sh -c \'for p in "$@"; do [ -e "$p" ] && printf "%s\\n" "$p"; done; exit 0\' _ '
        + " ".join(shlex.quote(p) for p in paths)
        + "\n"
    )
    try:
        out = ssh(f"bash -c {shlex.quote(script)}", timeout=60)
    except Exception as exc:  # noqa: BLE001
        logger.warning("backrest: visibility probe failed: %s", exc)
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def trusted(plan: dict, vis: set[str]) -> bool:
    """A plan Backrest can actually run: every path visible, scheduled, no iexcludes, no backup_flags."""
    plan_paths = [_norm(p) for p in plan.get("paths") or []]
    seen = {_norm(v) for v in vis}
    return bool(
        plan_paths
        and all(p in seen for p in plan_paths)
        and plan.get("scheduled")
        and not plan.get("disabled")
        and not plan.get("iexcludes")
        and not plan.get("backup_flags")
    )


def _excluded(path: str, patterns: list[str]) -> bool:
    # Conservative over-read of restic: a pattern's last real component against ANY component of the whole path.
    # Pure-wildcard components (`**`, `*`) are dropped first: restic reads `dir/**` as dir and everything under it,
    # and fnmatch of `**` would otherwise match every component, excluding the whole plan.
    components = [c for c in path.split("/") if c]
    for pattern in patterns:
        if any(ch in pattern for ch in _UNSAFE_EXCLUDE_CHARS):
            return True
        parts = [c for c in pattern.rstrip("/").split("/") if c and c.strip("*")]
        if not parts:
            return True
        if any(fnmatch.fnmatchcase(c, parts[-1]) for c in components):
            return True
    return False


_DUMP_DIR = "/opt/backups"
_CLUSTER_DUMP_MAX_MIN = 36 * 60
"""The hub's pre-backup.sh writes a nightly pg_dumpall here as pg_dump_YYYYMMDD_HHMM.sql (01:30); 36 h lets one
missed run alarm by the next afternoon."""


def _cluster_dump_for(db_name: str) -> str | None:
    """The newest fresh, COMPLETE cluster dump that contains ``db_name`` on this host, ``""`` when there is none.

    Only the newest file is tested — a partial newest dump is the alarm, never a fall back to yesterday's. ``None``
    when the probe fails. ``db_name`` is validated by the caller.
    """
    q = shlex.quote
    script = (
        "set -o pipefail\n"
        f"f=$(sudo find {q(_DUMP_DIR)} -maxdepth 1 -type f -name 'pg_dump_*.sql' -size +0c "
        f"-mmin -{_CLUSTER_DUMP_MAX_MIN} -printf '%T@ %p\\n' | sort -rn | head -1 | cut -d' ' -f2-)\n"
        '[ -n "$f" ] || exit 0\n'
        "sudo tail -c 512 \"$f\" | grep -q 'database cluster dump complete' || exit 0\n"
        f'sudo grep -q -m1 {q("^CREATE DATABASE " + db_name + " ")} "$f" || exit 0\n'
        "printf '%s\\n' \"$f\"\n"
    )
    try:
        out = ssh(f"bash -c {q(script)}", timeout=120)
    except Exception as exc:  # noqa: BLE001 — a failed probe is "unknown", never a guess
        logger.warning("backrest: cluster dump probe failed: %s", exc)
        return None
    return out.strip()


def coverage(paths: list[str], plans: list[dict], vis: set[str]) -> dict[str, str | None]:
    """Map each path to the trusted plan whose root covers it most specifically (ties by id), or ``None``.

    A path Backrest cannot itself stat is never covered: a plan root such as ``/opt`` exists inside the
    Backrest image even when its host bind is missing, so a visible root alone proves nothing about the data.
    """
    result: dict[str, str | None] = {}
    seen = {_norm(v) for v in vis}
    candidates = sorted((p for p in plans if trusted(p, vis)), key=lambda p: str(p.get("id")))
    for raw in paths:
        path = _norm(raw)
        result[raw] = None
        if path not in seen:
            continue
        best = -1
        for plan in candidates:
            roots = [_norm(r) for r in plan.get("paths") or []]
            depth = max(
                (len(r) for r in roots if path == r or r == "/" or path.startswith(r + "/")),
                default=-1,
            )
            if depth > best and not _excluded(path, list(plan.get("excludes") or [])):
                result[raw], best = str(plan.get("id")), depth
    return result


@contextlib.contextmanager
def _on_host(host: str) -> Iterator[None]:
    prev = os.environ.get("FABRIK_VPS_SSH_HOST")
    os.environ["FABRIK_VPS_SSH_HOST"] = host
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        else:
            os.environ["FABRIK_VPS_SSH_HOST"] = prev


def _paper(plans: list[dict], plan_id: str, vis: set[str]) -> bool:
    seen = {_norm(v) for v in vis}
    return any(
        p.get("id") == plan_id and any(_norm(x) not in seen for x in p.get("paths") or [])
        for p in plans
    )


def coverage_findings(
    name: str, db_name: str | None, *, target_host: str, hub_host: str
) -> tuple[str, list[str], dict]:
    """The coverage table for one service: ``(status, findings, actual)``.

    Paths are checked on ``target_host``; the database on ``hub_host``, where postgres-main and /opt/backups live — a
    per-database dump directory that exists and is covered, or else the newest fresh, complete cluster dump that
    contains it and is covered. A service not running on the host is ``missing`` and its database is not checked. ``FABRIK_VPS_SSH_HOST`` is set for each and restored.
    Status: ``unknown`` (a probe failed) · ``missing`` (not running on the host) · ``drift`` · ``present``.
    """
    findings: list[str] = []
    if db_name is not None:
        try:
            _validate_db_name(db_name)
        except ValueError:
            findings.append(f"invalid database name {db_name!r}: database not checked")
            db_name = None

    with _on_host(target_host):
        found = discover_persistence(name)
        plans = read_plans()
        if found is None or plans is None:
            return "unknown", ["a coverage probe failed"], {}
        plan_paths = [x for p in plans for x in p.get("paths") or []]
        vis = visible(sorted(set(found.paths) | set(plan_paths)))
        if vis is None:
            return "unknown", ["the Backrest visibility probe failed"], {}

    paper = _paper(plans, f"{name}-data", vis)
    if paper:
        findings.append(f"paper plan {name}-data: remove it")

    actual: dict = {"anonymous_volumes": found.anonymous}
    if found.containers == 0:
        # not running on the host: an undeployed spec is not drift and its database is not checked for a dump, but a
        # paper plan tied to it — `<name>-data` above, or a `postgres-<db>` plan on the hub — still is (spec table)
        if db_name is not None:
            with _on_host(hub_host):
                hub_plans = plans if hub_host == target_host else read_plans()
                if hub_plans is None:
                    return "unknown", ["the hub plan read failed"], {}
                pg = [p for p in hub_plans if p.get("id") == f"postgres-{db_name}"]
                pg_vis: set[str] | None = vis
                if pg and hub_host != target_host:
                    pg_vis = visible(sorted({x for p in pg for x in p.get("paths") or []}))
                    if pg_vis is None:
                        return "unknown", ["the hub visibility probe failed"], {}
            if pg and pg_vis is not None and _paper(pg, f"postgres-{db_name}", pg_vis):
                findings.append(f"paper plan postgres-{db_name}: remove it")
                paper = True
        return (
            ("drift" if paper else "missing"),
            findings or [f"not running on {target_host}"],
            actual,
        )

    if db_name is not None:
        with _on_host(hub_host):
            hub_plans = plans if hub_host == target_host else read_plans()
            if hub_plans is None:
                return "unknown", ["the hub plan read failed"], {}
            dump = f"/opt/backups/postgres/{db_name}"
            hub_paths = [x for p in hub_plans for x in p.get("paths") or []]
            hub_vis = visible(sorted({dump, *hub_paths}))
            if hub_vis is None:
                return "unknown", ["the hub visibility probe failed"], {}
            db_covered = dump in hub_vis and coverage([dump], hub_plans, hub_vis)[dump] is not None
            if not db_covered:
                # every database on postgres-main is in the nightly pg_dumpall; a per-db dir exists only for a few
                cluster = _cluster_dump_for(db_name)
                if cluster is None:
                    return "unknown", ["the cluster dump probe failed"], {}
                if cluster:
                    cluster_vis = visible([cluster])
                    if cluster_vis is None:
                        return "unknown", ["the hub visibility probe failed"], {}
                    # coverage() itself refuses a path Backrest cannot stat
                    db_covered = (
                        coverage([cluster], hub_plans, hub_vis | cluster_vis)[cluster] is not None
                    )
        if _paper(hub_plans, f"postgres-{db_name}", hub_vis):
            findings.append(f"paper plan postgres-{db_name}: remove it")
        if not db_covered:
            findings.append(f"database {db_name}: no dump covered")

    if not found.paths and db_name is None:
        findings.append("has_persistent_data set but no persistence found")
    covered = coverage(found.paths, plans, vis)
    findings.extend(f"unprotected: {p}" for p, q in covered.items() if q is None)
    actual["covered_by"] = {p: q for p, q in covered.items() if q is not None}
    return ("drift" if findings else "present"), findings, actual


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
    "Persistence",
    "discover_persistence",
    "read_plans",
    "visible",
    "trusted",
    "coverage",
    "coverage_findings",
)
