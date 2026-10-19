#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/external-services-registry.md tests/test_external_services_chain.py docs/workstation/quota-dashboard.md
"""Render the external-services registry (fabrik_services) as a self-contained static HTML file.

The section is the SAME one the board's Services view shows: ``dashboard_ui.inventory.render`` with
``interactive=False`` (no filter bar, nothing that needs ``app.js``), wrapped here in a document of its
own: ``app.css`` inlined from ``dashboard_ui.STATIC_DIR``, no script, no external request, its own
``<!doctype>``, ``lang``, ``<title>``, viewport and ``<h1>``. ZERO secrets: metadata and a credential
COUNT only, never a raw key.

    python scripts/gen_dashboard.py [out.html]

Cobra check (D-253): the cheapest way to pass "the file is a snapshot of the registry" without the
outcome is a document whose section is empty or whose dates are the render's own; the section's
"Registry synced" line is ``max(api_keys.last_seen)`` and a registry with no row says "never synced".
"""

from __future__ import annotations

import argparse
import html
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _dir in (Path(__file__).resolve().parent, Path(__file__).resolve().parent / "sysadmin"):
    if (
        str(_dir) not in sys.path
    ):  # once - the chain suite loads this module many times (B65-7, FF1)
        sys.path.insert(0, str(_dir))

import dashboard_ui  # noqa: E402
import registry_db  # noqa: E402
from dashboard_ui import inventory  # noqa: E402
from dashboard_ui.strings import t  # noqa: E402

STALE_AFTER_H = inventory.STALE_AFTER_H


def credit_cell(bal, unit, fetched, now=None) -> str:
    """The balance, flagged with its age once the LAST successful fetch is older than two laps.
    Keeps the datetime signature the chain suite calls and delegates to ``inventory.credit_cell``, which
    owns every refusal (a bool, NaN, Infinity, a negative, a non-number balance): this wrapper only turns
    a ``now`` into epoch seconds through the inventory's own ``_epoch`` (a datetime, a finite
    non-negative number inside its edge) and anything it refuses into the wall clock, never raising. ``Decimal`` balances and datetime ``fetched``
    reach the inventory as they are; it reads both."""
    moment = inventory._epoch(now)  # the inventory's own time check: it refuses what it cannot age
    return inventory.credit_cell(bal, unit, fetched, time.time() if moment is None else moment)


def _read() -> tuple[list[dict], float | None]:
    """``(rows, synced_at)``; the registry connection is closed on every path."""
    conn = registry_db.connect()
    try:
        rows, synced_at = inventory.load(conn)
    finally:
        conn.close()
    return rows, synced_at


def load() -> list[dict]:
    return _read()[0]


def render(
    rows: list[dict],
    *,
    synced_at: float | None = None,
    now: float | None = None,
) -> str:
    """The whole document: the inventory section (``interactive=False``) inside a self-contained page."""
    when = time.time() if now is None else now
    section = inventory.render(rows, now=when, synced_at=synced_at, interactive=False)
    css = (dashboard_ui.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    if "</style" in css.lower():
        raise ValueError("app.css would close its own <style> element")
    title = html.escape(t("services.inv.title"))
    return (
        "<!doctype html>\n"
        f'<html lang="{html.escape(t("app.lang"))}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>\n<style>{css}</style></head>\n"
        f'<body><main class="view"><h1>{title}</h1>\n{section}\n</main></body></html>\n'
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "out",
        nargs="?",
        default="external-services-dashboard.html",
        help="output path (default: ./external-services-dashboard.html)",
    )
    out = Path(
        ap.parse_args(argv).out
    )  # `--help` exits here — it used to WRITE a file named --help
    try:
        rows, synced_at = _read()
        page = render(
            rows, synced_at=synced_at, now=time.time()
        )  # a row shape the section cannot render is the same typed line (EZ4)
    except Exception as exc:  # noqa: BLE001 - a dead registry is one typed line and exit 1, never a traceback (EY6)
        print(
            f"ERROR: registry unreadable ({exc.__class__.__name__}: {exc}) — nothing written; the previous dashboard stands"
        )
        return 1
    # atomic: a half-written dashboard is never served (the chain stamps its own heartbeat, CY1).
    # The tmp name carries the PID — a manual refresh overlapping the cron's step shared ONE tmp
    # name and the faster writer's pre-write unlink pulled it from under the slower one, whose
    # `os.replace` then crashed with a raw FileNotFoundError (EW4; the pattern
    # `gather_envs.write_secret_file` already uses, AW1). Every OSError on the way out is one
    # typed line and exit 1 — a directory or a missing parent at `out` was a traceback (EW4).
    tmp = out.with_name(f"{out.name}.tmp.{os.getpid()}")
    try:
        try:
            tmp.write_text(page, encoding="utf-8")
            os.replace(tmp, out)
        finally:
            tmp.unlink(missing_ok=True)  # a failed write leaves nothing behind (AC14)
    except OSError as exc:
        print(
            f"ERROR: {exc.__class__.__name__}: {exc} — nothing written; the previous dashboard stands"
        )
        return 1
    print(f"wrote {out} — {len(rows)} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
