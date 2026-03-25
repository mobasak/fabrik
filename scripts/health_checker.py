#!/usr/bin/env python3

"""Run HTTP `/health` probe and DB TCP reachability checks for cron/CI use.
Validates service health responses and database host:port connectivity.
Exit codes: 0 OK, 1 unexpected error, 2 config error,
3 HTTP unhealthy, 4 DB unreachable.

Workflow Doc: docs/workflows/HEALTH_CHECKER_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_CONFIG = 2
EXIT_HTTP_UNHEALTHY = 3
EXIT_DB_UNREACHABLE = 4


@dataclass(frozen=True)
class DbTarget:
    host: str
    port: int


def _load_env() -> None:
    """Load FABRIK_ROOT/.env if present.

    This keeps local runs convenient while still working in Docker/CI where
    env vars are typically injected directly.
    """

    fabrik_root = os.getenv("FABRIK_ROOT")
    if not fabrik_root:
        return
    load_dotenv(os.path.join(fabrik_root, ".env"))


def _db_target_from_env() -> DbTarget | None:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        if not parsed.hostname:
            return None
        if parsed.port is None:
            return None
        return DbTarget(host=parsed.hostname, port=int(parsed.port))

    host = os.getenv("DB_HOST")
    port_raw = os.getenv("DB_PORT")
    if not host or not port_raw:
        return None

    try:
        port = int(port_raw)
    except ValueError:
        return None

    return DbTarget(host=host, port=port)


def _check_db_reachability(target: DbTarget, timeout_s: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((target.host, target.port), timeout=timeout_s):
            return True, f"reachable: {target.host}:{target.port}"
    except OSError as exc:
        return False, f"unreachable: {target.host}:{target.port} ({exc})"


def _check_http_health(url: str, timeout_s: float) -> tuple[bool, str]:
    try:
        resp = httpx.get(url, timeout=timeout_s)
    except Exception as exc:  # noqa: BLE001 - surface network problems
        return False, f"request_failed: {exc}"

    if resp.status_code != 200:
        return False, f"status_code={resp.status_code} body={resp.text[:200]}"

    try:
        payload: Any = resp.json()
    except ValueError:
        return False, "invalid_json"

    if isinstance(payload, dict):
        status_value = str(payload.get("status", "")).lower()
        if status_value != "ok":
            return False, f"status={status_value}"
        return True, "ok"

    return False, "unexpected_json_shape"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Fabrik health endpoints and DB reachability"
    )
    parser.add_argument(
        "--health-url",
        default=None,
        help="Optional full URL to /health endpoint (e.g. http://localhost:8000/health)",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Check DB host/port reachability using DATABASE_URL or DB_HOST/DB_PORT",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Timeout seconds for each check (default: 5.0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    _load_env()
    args = parse_args(argv)

    # If nothing requested, fail fast with a helpful exit code.
    if not args.health_url and not args.check_db:
        print("No checks requested. Use --health-url and/or --check-db.")
        return EXIT_CONFIG

    if args.health_url:
        ok, detail = _check_http_health(args.health_url, timeout_s=args.timeout)
        print(f"http: {detail}")
        if not ok:
            return EXIT_HTTP_UNHEALTHY

    if args.check_db:
        target = _db_target_from_env()
        if not target:
            print("db: missing/invalid DATABASE_URL or DB_HOST/DB_PORT")
            return EXIT_CONFIG

        ok, detail = _check_db_reachability(target, timeout_s=args.timeout)
        print(f"db: {detail}")
        if not ok:
            return EXIT_DB_UNREACHABLE

    return EXIT_OK


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - last-resort CLI safety net
        print(f"unexpected_error: {exc}")
        raise SystemExit(EXIT_UNEXPECTED)
