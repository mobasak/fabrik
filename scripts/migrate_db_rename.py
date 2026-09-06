#!/usr/bin/env python3
# AFTER-EDIT: none
# Atomic, idempotent, rollback-capable Postgres database rename for Coolify-managed
# apps. Reusable across vps1, vps2, ... — no hardcoded host names.
#
# T1-05 first use: --app fabrik-translator --from-db translator_service --to-db translator
#
# All VPS ops via SSH (--vps); all Coolify ops via REST (CoolifyClient honors
# COOLIFY_API_URL + COOLIFY_INTERNAL_URL). See docs/development/plans/
# fabrik workflow missing items/02-tier1-foundation.md § 6 (G-H8) for the
# user-facing migration procedure this script automates.

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Repo on PYTHONPATH so `from fabrik...` works without install
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from fabrik.drivers.coolify import CoolifyClient  # noqa: E402

# ────────────────────────────────────────────────────────────────────────────
# Exit codes (see module docstring for matrix)
# ────────────────────────────────────────────────────────────────────────────
EXIT_SUCCESS = 0
EXIT_PREFLIGHT_ABORT = 1
EXIT_SNAPSHOT_FAIL = 2
EXIT_ROLLED_BACK = 3
EXIT_ROLLBACK_FAILED = 4
EXIT_HEALTH_FAIL = 5


@dataclass
class EnvChange:
    uuid: str
    key: str
    is_preview: bool
    before: str
    after: str


@dataclass
class Receipt:
    app: str
    uuid: str
    from_db: str
    to_db: str
    started_at: str
    pg_container: str = ""
    vps: str = "vps"
    ended_at: str = ""
    outcome: str = "in_progress"
    baseline_metrics: dict[str, Any] = field(default_factory=dict)
    post_rename_metrics: dict[str, Any] = field(default_factory=dict)
    env_changes: list[EnvChange] = field(default_factory=list)
    snapshot_path: str = ""
    health_after: str = ""
    rollback_actions_taken: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def write(self, log_dir: Path) -> Path:
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = self.started_at.replace(":", "").replace("-", "")[:15]
        path = log_dir / f"{self.app}-{ts}.json"
        payload = asdict(self)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path


# ────────────────────────────────────────────────────────────────────────────
# Shell helpers
# ────────────────────────────────────────────────────────────────────────────
def ssh(vps: str, cmd: str, check: bool = True, timeout: int = 120) -> tuple[int, str, str]:
    # Wrap a remote command. We rely on the user's ~/.ssh/config alias.
    full = ["ssh", vps, cmd]
    result = subprocess.run(full, capture_output=True, text=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"ssh {vps} failed (rc={result.returncode}): {cmd}\nSTDERR: {result.stderr.strip()}"
        )
    return result.returncode, result.stdout, result.stderr


def psql(vps: str, container: str, db: str, sql: str, check: bool = True) -> tuple[int, str, str]:
    # Run a single psql command. -At for tuples-only + unaligned (parseable).
    inner = f"psql -U postgres -At -d {shlex.quote(db)} -c {shlex.quote(sql)}"
    cmd = f"sudo docker exec {shlex.quote(container)} {inner}"
    return ssh(vps, cmd, check=check)


def psql_admin(vps: str, container: str, sql: str, check: bool = True) -> tuple[int, str, str]:
    # Run a psql command against the postgres database (for DDL like ALTER DATABASE).
    return psql(vps, container, "postgres", sql, check=check)


# ────────────────────────────────────────────────────────────────────────────
# Phase 1 — Preflight
# ────────────────────────────────────────────────────────────────────────────
def resolve_app_uuid(coolify: CoolifyClient, app_name: str) -> tuple[str, dict[str, Any]]:
    for app in coolify.list_applications():
        if app.get("name") == app_name:
            return app["uuid"], app
    raise SystemExit(f"PREFLIGHT FAIL: Coolify app '{app_name}' not found")


def auto_detect_pg_container(vps: str) -> str:
    rc, out, _ = ssh(
        vps,
        "sudo docker ps --format '{{.Names}}' | grep '^postgres-main-' | head -1",
        check=False,
    )
    name = out.strip()
    if not name:
        raise SystemExit(
            "PREFLIGHT FAIL: could not auto-detect postgres-main container. "
            "Pass --pg-container explicitly."
        )
    return name


def db_exists(vps: str, container: str, db: str) -> bool:
    rc, out, _ = psql_admin(
        vps,
        container,
        f"SELECT 1 FROM pg_database WHERE datname={pg_str(db)}",
        check=False,
    )
    return out.strip() == "1"


def pg_str(s: str) -> str:
    # Safely embed a literal string in SQL. Single-quote escaped.
    return "'" + s.replace("'", "''") + "'"


def capture_metrics(vps: str, container: str, db: str) -> dict[str, Any]:
    _, size_out, _ = psql_admin(vps, container, f"SELECT pg_database_size({pg_str(db)})")
    size_bytes = int(size_out.strip() or "0")

    # Per-table tuple count via pg_stat_user_tables
    _, tbl_out, _ = psql(
        vps,
        container,
        db,
        "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname",
    )
    tables: dict[str, int] = {}
    for line in tbl_out.strip().splitlines():
        if "|" in line:
            name, tup = line.split("|", 1)
            tables[name.strip()] = int(tup.strip() or "0")
    return {
        "size_bytes": size_bytes,
        "size_kb": size_bytes // 1024,
        "tables": tables,
        "total_tuples": sum(tables.values()),
    }


def find_env_vars_to_patch(
    coolify: CoolifyClient, app_uuid: str, env_key: str, from_db: str
) -> list[dict[str, Any]]:
    needle = f"/{from_db}"
    matches: list[dict[str, Any]] = []
    for env in coolify.get_env_vars(app_uuid):
        if env.get("key") != env_key:
            continue
        value = env.get("value") or ""
        if value.endswith(needle) or needle in value:
            matches.append(env)
    return matches


def scan_cross_references(
    coolify: CoolifyClient, from_db: str, current_uuid: str
) -> tuple[list[str], list[str]]:
    # Walk all Coolify resources; return (conflict_refs, skipped_resources).
    # list_applications() returns a mixed bag — true applications, services,
    # databases, infrastructure containers. /applications/{uuid}/envs returns
    # 404 for non-application kinds; that's not a conflict, just the wrong
    # endpoint for that resource type. Silence 404s and only report real
    # cross-references (env_var fetch succeeded AND value contains needle).
    import logging

    needle = f"/{from_db}"
    refs: list[str] = []
    skipped: list[str] = []
    drv_logger = logging.getLogger("fabrik.drivers.coolify")
    prev_level = drv_logger.level
    drv_logger.setLevel(logging.CRITICAL)  # mute 404 ERROR spam during scan
    try:
        for app in coolify.list_applications():
            uuid = app.get("uuid")
            if uuid == current_uuid or not uuid:
                continue
            try:
                envs = coolify.get_env_vars(uuid)
            except Exception as e:  # noqa: BLE001
                # 404 = not-an-application (service/database/infra). Skip silently.
                if "404" in str(e):
                    skipped.append(f"{app.get('name')} (non-app, 404 on /envs)")
                    continue
                # Other errors get surfaced — we couldn't verify, fail closed.
                refs.append(f"  - {app.get('name')} <uuid={uuid}> env_var fetch failed: {e}")
                continue
            for env in envs:
                v = env.get("value") or ""
                if needle in v:
                    refs.append(f"  - {app.get('name')} :: {env.get('key')} contains '{needle}'")
    finally:
        drv_logger.setLevel(prev_level)
    return refs, skipped


# ────────────────────────────────────────────────────────────────────────────
# Phase 2 — Snapshot
# ────────────────────────────────────────────────────────────────────────────
def snapshot_db(vps: str, container: str, db: str, app: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = "/opt/backups/db-renames"
    fname = f"{app}-pre-rename-{ts}.dump"
    ssh(vps, f"sudo mkdir -p {backup_dir}")
    # pg_dump custom-format (-Fc) — compressed + restorable with pg_restore
    tmp_in = f"/tmp/{fname}"
    cmd = (
        f"sudo docker exec {shlex.quote(container)} "
        f"pg_dump -U postgres -Fc -d {shlex.quote(db)} -f {shlex.quote(tmp_in)}"
    )
    ssh(vps, cmd, timeout=600)
    ssh(vps, f"sudo docker cp {shlex.quote(container)}:{tmp_in} {backup_dir}/{fname}")
    ssh(vps, f"sudo docker exec {shlex.quote(container)} rm -f {shlex.quote(tmp_in)}")
    _, size_out, _ = ssh(vps, f"sudo ls -la {backup_dir}/{fname} | awk '{{print $5}}'")
    return f"{backup_dir}/{fname} ({int(size_out.strip() or 0)} bytes)"


# ────────────────────────────────────────────────────────────────────────────
# Phase 4 — Execute (with rollback stack)
# ────────────────────────────────────────────────────────────────────────────
class RollbackStack:
    def __init__(self) -> None:
        self.actions: list[tuple[str, Any]] = []

    def push(self, label: str, fn: Any) -> None:
        self.actions.append((label, fn))

    def unwind(self, receipt: Receipt) -> bool:
        ok = True
        while self.actions:
            label, fn = self.actions.pop()
            try:
                print(f"  ROLLBACK: {label}")
                fn()
                receipt.rollback_actions_taken.append(f"ok: {label}")
            except Exception as e:  # noqa: BLE001
                print(f"  ROLLBACK FAILED ({label}): {e}", file=sys.stderr)
                receipt.rollback_actions_taken.append(f"FAIL: {label} :: {e}")
                ok = False
        return ok


def terminate_connections(vps: str, container: str, db: str) -> None:
    sql = (
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname={pg_str(db)} AND pid<>pg_backend_pid()"
    )
    psql_admin(vps, container, sql, check=False)


def rename_db(vps: str, container: str, src: str, dst: str) -> None:
    psql_admin(vps, container, f"ALTER DATABASE {src} RENAME TO {dst}")


def patch_env_value(
    coolify: CoolifyClient,
    app_uuid: str,
    env_uuid: str,
    key: str,
    new_value: str,
    is_preview: bool,
) -> None:
    # Coolify v4: PATCH /applications/{uuid}/envs (no env_uuid in path).
    # Server matches by (key, is_preview) tuple in the body. The driver's
    # update_env_var() uses /envs/{env_uuid} which returns 404 — bypass it.
    # env_uuid kept in signature for receipt/audit trail only.
    del env_uuid
    coolify._request(  # noqa: SLF001
        "PATCH",
        f"/applications/{app_uuid}/envs",
        json={
            "key": key,
            "value": new_value,
            "is_preview": is_preview,
            "is_literal": True,
        },
    )


# ────────────────────────────────────────────────────────────────────────────
# Phase 5 — Verify (health poll)
# ────────────────────────────────────────────────────────────────────────────
def poll_health(url: str, timeout_s: int) -> str:
    import urllib.request

    deadline = time.monotonic() + timeout_s
    last = "no-attempt"
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "migrate_db_rename/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                if 200 <= resp.status < 300:
                    return str(resp.status)
                last = f"http-{resp.status}"
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__
        time.sleep(5)
    return f"timeout ({last})"


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Rename a Postgres database for a Coolify-managed app, "
        "atomically updating env vars and verifying health, with rollback.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--app", required=True, help="Coolify application name (slug)")
    p.add_argument("--from-db", required=True, dest="from_db", help="Source DB name")
    p.add_argument("--to-db", required=True, dest="to_db", help="Target DB name")
    p.add_argument("--env-key", default="DATABASE_URL", help="Env var key to update")
    p.add_argument("--pg-container", default="", help="Postgres container name (default: auto)")
    p.add_argument("--vps", default="vps", help="SSH host alias for the VPS")
    p.add_argument("--health-url", default="", help="Health URL (default: derived from app domain)")
    p.add_argument("--health-timeout", type=int, default=60, help="Health poll timeout (seconds)")
    p.add_argument("--dry-run", action="store_true", help="Read-only; exit before mutations")
    p.add_argument("--skip-snapshot", action="store_true", help="Skip pg_dump (testing only)")
    p.add_argument(
        "--skip-rollback",
        action="store_true",
        help="On health failure, do NOT auto-rollback (caller will decide)",
    )
    p.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    p.add_argument(
        "--log-dir",
        default=str(REPO_ROOT / "logs" / "migrations"),
        help="Where to write the JSON receipt",
    )
    return p.parse_args()


def derive_health_url(app: dict[str, Any]) -> str:
    import re

    # Try top-level fqdn first (set on single-domain applications)
    fqdn = app.get("fqdn") or ""
    if fqdn:
        host = fqdn.split(",")[0].strip()
        if host.startswith("http"):
            return host.rstrip("/") + "/health"
        return f"https://{host}/health"

    # Docker-compose apps don't have fqdn — extract from Traefik Host() labels
    for field_name in ("docker_compose", "docker_compose_raw"):
        compose = app.get(field_name) or ""
        match = re.search(r"Host\(`([^`]+)`\)", compose)
        if match:
            return f"https://{match.group(1)}/health"
    return ""


def main() -> int:
    args = parse_args()
    log_dir = Path(args.log_dir)

    if not os.getenv("COOLIFY_API_TOKEN"):
        print("PREFLIGHT FAIL: COOLIFY_API_TOKEN not set in environment", file=sys.stderr)
        return EXIT_PREFLIGHT_ABORT

    started_at = datetime.now(UTC).isoformat()
    receipt = Receipt(
        app=args.app,
        uuid="",
        from_db=args.from_db,
        to_db=args.to_db,
        started_at=started_at,
        vps=args.vps,
    )

    print(f"━━━ migrate_db_rename: {args.app} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   from_db={args.from_db}  →  to_db={args.to_db}")
    print(f"   vps={args.vps}  dry_run={args.dry_run}")
    print()

    coolify = CoolifyClient()

    # ── Phase 1 — PREFLIGHT ────────────────────────────────────────────────
    print("[1/6] PREFLIGHT")
    try:
        app_uuid, app_obj = resolve_app_uuid(coolify, args.app)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        receipt.outcome = "abort-preflight-app-not-found"
        receipt.ended_at = datetime.now(UTC).isoformat()
        receipt.write(log_dir)
        return EXIT_PREFLIGHT_ABORT
    receipt.uuid = app_uuid
    print(f"   ✓ app UUID resolved: {app_uuid}")

    pg_container = args.pg_container or auto_detect_pg_container(args.vps)
    receipt.pg_container = pg_container
    print(f"   ✓ postgres container: {pg_container}")

    if not db_exists(args.vps, pg_container, args.from_db):
        print(f"PREFLIGHT FAIL: source DB '{args.from_db}' does not exist", file=sys.stderr)
        receipt.outcome = "abort-preflight-source-missing"
        receipt.ended_at = datetime.now(UTC).isoformat()
        receipt.write(log_dir)
        return EXIT_PREFLIGHT_ABORT

    if db_exists(args.vps, pg_container, args.to_db):
        print(
            f"PREFLIGHT FAIL: target DB '{args.to_db}' already exists — rename would collide",
            file=sys.stderr,
        )
        receipt.outcome = "abort-preflight-target-exists"
        receipt.ended_at = datetime.now(UTC).isoformat()
        receipt.write(log_dir)
        return EXIT_PREFLIGHT_ABORT
    print(f"   ✓ DB existence: from={args.from_db} ✓  to={args.to_db} ✗ (free)")

    baseline = capture_metrics(args.vps, pg_container, args.from_db)
    receipt.baseline_metrics = baseline
    print(
        f"   ✓ baseline: size_kb={baseline['size_kb']}  "
        f"tables={len(baseline['tables'])}  total_tuples={baseline['total_tuples']}"
    )

    env_matches = find_env_vars_to_patch(coolify, app_uuid, args.env_key, args.from_db)
    if not env_matches:
        print(
            f"PREFLIGHT FAIL: no env var with key='{args.env_key}' references '/{args.from_db}'",
            file=sys.stderr,
        )
        receipt.outcome = "abort-preflight-no-env-match"
        receipt.ended_at = datetime.now(UTC).isoformat()
        receipt.write(log_dir)
        return EXIT_PREFLIGHT_ABORT
    print(f"   ✓ env vars to patch ({len(env_matches)}):")
    for env in env_matches:
        flag = "preview" if env.get("is_preview") else "prod"
        masked = (env.get("value") or "").rsplit("@", 1)[-1]  # hide creds
        print(f"     - [{flag}] {env['key']} uuid={env['uuid']} ...@{masked}")

    cross_refs, skipped_resources = scan_cross_references(coolify, args.from_db, app_uuid)
    if skipped_resources:
        receipt.notes.append(f"cross_ref_scan_skipped={len(skipped_resources)}")
    if cross_refs:
        print(
            "PREFLIGHT FAIL: other apps reference '/" + args.from_db + "':",
            file=sys.stderr,
        )
        for r in cross_refs:
            print(r, file=sys.stderr)
        receipt.outcome = "abort-preflight-cross-reference"
        receipt.notes.append(f"cross_refs={cross_refs}")
        receipt.ended_at = datetime.now(UTC).isoformat()
        receipt.write(log_dir)
        return EXIT_PREFLIGHT_ABORT
    print(
        f"   ✓ cross-reference scan: clean (scanned apps, skipped "
        f"{len(skipped_resources)} non-app resources)"
    )

    health_url = args.health_url or derive_health_url(app_obj)
    if not health_url:
        receipt.notes.append("no_health_url_derived")
        print("   ⚠  no health URL available — health-check phase will be skipped")
    else:
        print(f"   ✓ health URL: {health_url}")

    # ── Phase 2 — SNAPSHOT ─────────────────────────────────────────────────
    print()
    print("[2/6] SNAPSHOT")
    if args.dry_run or args.skip_snapshot:
        print(f"   ⏭  skipped (dry_run={args.dry_run} skip_snapshot={args.skip_snapshot})")
    else:
        try:
            receipt.snapshot_path = snapshot_db(args.vps, pg_container, args.from_db, args.app)
            print(f"   ✓ snapshot: {receipt.snapshot_path}")
        except Exception as e:  # noqa: BLE001
            print(f"SNAPSHOT FAIL: {e}", file=sys.stderr)
            receipt.outcome = "abort-snapshot"
            receipt.ended_at = datetime.now(UTC).isoformat()
            receipt.write(log_dir)
            return EXIT_SNAPSHOT_FAIL

    # ── Phase 3 — PLAN ─────────────────────────────────────────────────────
    print()
    print("[3/6] PLAN")
    print(f"   1. coolify.stop_application({app_uuid})")
    print(f"   2. SELECT pg_terminate_backend(pid) WHERE datname='{args.from_db}'")
    print(f"   3. ALTER DATABASE {args.from_db} RENAME TO {args.to_db}")
    print("   4. Re-capture metrics on new DB, verify match")
    for env in env_matches:
        new_value = (env.get("value") or "").replace(f"/{args.from_db}", f"/{args.to_db}")
        print(
            f"   5. PATCH env_var uuid={env['uuid']} "
            f"key={env['key']} (preview={env.get('is_preview')})"
        )
        print(f"        {env.get('value')!r}")
        print(f"      → {new_value!r}")
    print(f"   6. coolify.deploy({app_uuid})")
    print(f"   7. poll {health_url or '(skipped)'} for up to {args.health_timeout}s")

    if args.dry_run:
        print()
        print("━━━ DRY RUN — exiting before mutations ━━━")
        receipt.outcome = "dry-run"
        receipt.ended_at = datetime.now(UTC).isoformat()
        path = receipt.write(log_dir)
        print(f"Receipt: {path}")
        return EXIT_SUCCESS

    if not args.yes:
        print()
        try:
            ans = input("Proceed with mutations? [y/N]: ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("Aborted by user.")
            receipt.outcome = "aborted-by-user"
            receipt.ended_at = datetime.now(UTC).isoformat()
            receipt.write(log_dir)
            return EXIT_PREFLIGHT_ABORT

    # ── Phase 4 — EXECUTE ──────────────────────────────────────────────────
    print()
    print("[4/6] EXECUTE")
    rb = RollbackStack()
    try:
        print(f"   → stop_application({app_uuid})")
        coolify.stop_application(app_uuid)
        rb.push(
            f"restart_application({app_uuid})",
            lambda: coolify.restart_application(app_uuid),
        )

        # Give the container a moment to actually disconnect
        time.sleep(3)

        print(f"   → terminate_connections({args.from_db})")
        terminate_connections(args.vps, pg_container, args.from_db)

        print(f"   → ALTER DATABASE {args.from_db} RENAME TO {args.to_db}")
        rename_db(args.vps, pg_container, args.from_db, args.to_db)
        rb.push(
            f"ALTER DATABASE {args.to_db} RENAME TO {args.from_db}",
            lambda: rename_db(args.vps, pg_container, args.to_db, args.from_db),
        )

        # Verify metrics match baseline
        post = capture_metrics(args.vps, pg_container, args.to_db)
        receipt.post_rename_metrics = post
        if post["total_tuples"] != baseline["total_tuples"]:
            raise RuntimeError(
                f"metrics drift after rename: baseline_tuples={baseline['total_tuples']} "
                f"post_tuples={post['total_tuples']}"
            )
        print(f"   ✓ metrics match: size_kb={post['size_kb']} total_tuples={post['total_tuples']}")

        # Patch env vars
        for env in env_matches:
            old_value = env.get("value") or ""
            new_value = old_value.replace(f"/{args.from_db}", f"/{args.to_db}")
            env_uuid = env["uuid"]
            key = env["key"]
            is_preview = bool(env.get("is_preview"))
            print(f"   → PATCH env_var {env_uuid} ({key}, preview={is_preview})")
            patch_env_value(coolify, app_uuid, env_uuid, key, new_value, is_preview)
            receipt.env_changes.append(
                EnvChange(
                    uuid=env_uuid,
                    key=key,
                    is_preview=is_preview,
                    before=old_value,
                    after=new_value,
                )
            )
            # Capture for rollback (closure over loop var requires default arg)
            rb.push(
                f"PATCH env_var {env_uuid} → '{old_value}' (preview={is_preview})",
                lambda a=app_uuid, e=env_uuid, k=key, v=old_value, p=is_preview: patch_env_value(
                    coolify, a, e, k, v, p
                ),
            )

        print(f"   → deploy({app_uuid})")
        coolify.deploy(app_uuid)
        # No rollback push for deploy — we re-deploy in unwind if needed

    except Exception as e:  # noqa: BLE001
        print(f"EXECUTE FAIL: {e}", file=sys.stderr)
        ok = rb.unwind(receipt)
        try:
            coolify.deploy(app_uuid)
        except Exception as e2:  # noqa: BLE001
            receipt.rollback_actions_taken.append(f"FAIL: post-rollback deploy :: {e2}")
            ok = False
        receipt.outcome = "rolled-back" if ok else "rollback-failed"
        receipt.ended_at = datetime.now(UTC).isoformat()
        path = receipt.write(log_dir)
        print(f"Receipt: {path}")
        return EXIT_ROLLED_BACK if ok else EXIT_ROLLBACK_FAILED

    # ── Phase 5 — VERIFY ───────────────────────────────────────────────────
    print()
    print("[5/6] VERIFY")
    if not health_url:
        print("   ⏭  no health URL — skipped")
        receipt.health_after = "skipped"
    else:
        print(f"   → polling {health_url} for up to {args.health_timeout}s")
        result = poll_health(health_url, args.health_timeout)
        receipt.health_after = result
        if not result.startswith("2"):
            print(f"   ✗ health check failed: {result}", file=sys.stderr)
            if args.skip_rollback:
                receipt.outcome = "health-failed-no-rollback"
                receipt.ended_at = datetime.now(UTC).isoformat()
                receipt.write(log_dir)
                return EXIT_HEALTH_FAIL
            print("   → rolling back...")
            ok = rb.unwind(receipt)
            try:
                coolify.deploy(app_uuid)
            except Exception as e:  # noqa: BLE001
                receipt.rollback_actions_taken.append(f"FAIL: post-rollback deploy :: {e}")
                ok = False
            receipt.outcome = "rolled-back-on-health" if ok else "rollback-failed-on-health"
            receipt.ended_at = datetime.now(UTC).isoformat()
            path = receipt.write(log_dir)
            print(f"Receipt: {path}")
            return EXIT_ROLLED_BACK if ok else EXIT_ROLLBACK_FAILED
        print(f"   ✓ health: {result}")

    # ── Phase 6 — DOCUMENT ─────────────────────────────────────────────────
    print()
    print("[6/6] DOCUMENT")
    receipt.outcome = "success"
    receipt.ended_at = datetime.now(UTC).isoformat()
    path = receipt.write(log_dir)
    print(f"   ✓ receipt: {path}")
    print()
    print("Suggested CHANGELOG entry under [Unreleased] → ### Changed:")
    print(
        f"  - **DB rename — {args.app}**: `{args.from_db}` → `{args.to_db}` "
        f"({receipt.health_after}, snapshot: {receipt.snapshot_path or 'skipped'}) "
        f"({datetime.now(UTC).date().isoformat()})"
    )
    print()
    print(
        f"Next: edit specs/services/{args.app.replace('fabrik-', '')}.yaml "
        "to reflect the new shape/infra contract."
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
