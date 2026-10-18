#!/usr/bin/env python3
"""The registry read the Services view runs, as a CHILD PROCESS the board spawns and kills at the read's deadline.

``inventory_read.py --deadline <epoch seconds>`` connects with ``registry_db.connect(connect_timeout=2,
options="-c statement_timeout=2000")``, calls ``dashboard_ui.inventory.load`` with a ``before_query`` hook that
re-arms ``SET LOCAL statement_timeout`` to the deadline left (never below 1 ms: 0 disables the bound), and
reports EVERY outcome as one JSON object written once to stdout:

- success, exit 0: ``{"rows": [...], "synced_at": <float> | null}`` (strings, ints, floats, null, lists of strings);
- any failure, exit 1: ``{"error": "<ExceptionClass>: <first line of the message>"}``.

psycopg2 is imported HERE and nowhere in the board (spec D9): a missing psycopg2 is this process's failure and
the section's error state, never the board's. Only ``json`` and ``sys`` are imported at module top; everything
else, ``--deadline`` parsing included, runs inside one ``try`` whose ``except BaseException`` builds the error
object, so a bad argv, an import failure or an interrupt is reported the same way. No argparse (it prints and
exits on its own). The board kills a read that outlives its deadline; nothing here ever cancels a connection.

Cobra check (D-253): the cheapest way to pass "the read is bounded" without the outcome is a statement timeout
alone, which a server that accepts and never answers never reaches; the bound that holds is the board killing
this process at the deadline (tests/test_quota_dashboard.py drives it against such a server).
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md scripts/sysadmin/quota_dashboard.py

import json
import sys


def _plain(value):
    """``value`` as JSON-safe data: Decimal to float, a set or tuple to a sorted list of strings."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return float(value)  # a Decimal from psycopg2; anything else is a defect the error object names


def _deadline(argv):
    if len(argv) != 3 or argv[1] != "--deadline":
        raise ValueError("usage: inventory_read.py --deadline <epoch seconds>")
    return float(argv[2])


def _read(argv):
    import os
    import time

    deadline = _deadline(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.dirname(here), here):  # scripts/, then scripts/sysadmin/ first on the path
        if path not in sys.path:
            sys.path.insert(0, path)
    import registry_db
    from dashboard_ui import inventory

    def rearm(cur):
        left_ms = max(1, int((deadline - time.time()) * 1000))
        cur.execute(f"SET LOCAL statement_timeout = {left_ms}")

    conn = registry_db.connect(connect_timeout=2, options="-c statement_timeout=2000")
    try:
        rows, synced_at = inventory.load(conn, before_query=rearm)
    finally:
        conn.close()
    return json.dumps({"rows": _plain(rows), "synced_at": _plain(synced_at)})


def main(argv):
    try:
        out, code = _read(argv), 0
    except BaseException as exc:  # noqa: BLE001 — every outcome is one JSON object, an interrupt included
        line = (str(exc).splitlines() or [""])[0]
        out, code = json.dumps({"error": f"{type(exc).__name__}: {line}".rstrip(": ")}), 1
    sys.stdout.write(out)
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
