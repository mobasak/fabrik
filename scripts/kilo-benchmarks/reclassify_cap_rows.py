#!/usr/bin/env python3
# AFTER-EDIT: tests/test_reclassify_cap_rows.py | rank_task_subagents.py (reads the status it writes)
"""One-off: reclassify the default-price-cap rejections that are recorded as model FAILURES.

The pool once carried an always-on `≤$1.5/Mtok` cap. It was removed **2026-07-19** — `select.py:83`
says so in its own body, *"(removed 2026-07-19 per operator: the pool is curated, and per-run task
cost is pennies regardless"*. ⚠️ An earlier draft dated it 2026-07-21 from
`git log -S"always-on cap is gone"`, which finds the commit that added the PHRASE, not the one that
removed the CODE. The commit message is not the diff.

While that cap was live it produced HTTP 404 *"No endpoints found that satisfy the max price for this
request"* — recorded as `status='error'`. Three models were priced out **before ever running**, and
their success rates read 0–20% as a result. They are UNSCORED, not bad.

⚠️ THE CAUSE IS NOT IN THE DATABASE. `subagent_runs` has no error-text column, so this cannot select
on the reason. The "240" figure quoted elsewhere is a **JSONL-ledger** count; the DB holds **90**
matching rows. Selection is therefore by the enumerated `(model, ts::date)` pairs below — never by a
text match that cannot exist. Keeping the two populations distinct is the point.

⚠️ AND NOT BY DATE ALONE. `max_cost_per_mtok` survives as an OPT-IN caller filter (`select.py:526`),
so a `max price` rejection can also be a caller's deliberate ceiling — erasing those would destroy a
real signal. The dry-run prints every candidate for confirmation before anything is written.

Terminal status is `skipped`: not a failure, not a success. The aggregation counts runs from
`status <> 'scored'` and success from `status='done'`, so a `skipped` row leaves `n` intact while no
longer counting against the model — which is exactly the truth about a run that never happened.
"""

from __future__ import annotations

import argparse
import os
import sys

# The enumerated candidate set — three models, one date, the day before the cap came off.
CANDIDATES = (
    ("moonshotai/kimi-k2.5", "2026-07-18"),
    ("qwen/qwen3.7-max", "2026-07-18"),
    ("z-ai/glm-5", "2026-07-18"),
)
CAP_REMOVED = "2026-07-19"
NEW_STATUS = "skipped"

# ⚠️ `unnest`, not `IN %s`. psycopg3 does not adapt a tuple-of-tuples into a row-list the way
# psycopg2 did — `IN %s` renders as `IN $1` and Postgres rejects it. Passing two parallel arrays and
# zipping them server-side is the portable form, and it keeps the candidate set a DATA parameter
# rather than interpolated SQL.
_MATCH = """(model, ts::date) IN (SELECT * FROM unnest(%s::text[], %s::date[]))"""
_SELECT = f"""
SELECT model, ts::date AS d, project, count(*) AS n
FROM subagent_runs
WHERE status = 'error' AND {_MATCH}
GROUP BY 1, 2, 3 ORDER BY 1, 3
"""
_UPDATE = f"""
UPDATE subagent_runs SET status = %s
WHERE status = 'error' AND {_MATCH}
"""


def _pairs() -> tuple[list[str], list[object]]:
    import datetime

    models = [m for m, _ in CANDIDATES]
    dates = [datetime.date.fromisoformat(d) for _, d in CANDIDATES]
    return models, dates


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=os.environ.get("SUBAGENT_RUNS_DSN", ""))
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = ap.parse_args(argv)
    if not args.dsn:
        print("no DSN (--dsn or SUBAGENT_RUNS_DSN)", file=sys.stderr)
        return 2

    import psycopg

    pairs = _pairs()
    with psycopg.connect(args.dsn) as conn:
        models, dates = pairs
        rows = conn.execute(_SELECT, (models, dates)).fetchall()
        total = sum(r[3] for r in rows)
        print(f"candidates: {total} row(s) across {len(rows)} (model, date, project) group(s)")
        for model, d, project, n in rows:
            print(f"  {model:<24} {d}  project={project:<28} n={n}")
        print(
            f"\nEvery candidate predates the cap removal on {CAP_REMOVED}. Confirm the population is "
            "the DEFAULT-cap sweep and not a caller's deliberate `max_cost_per_mtok` ceiling before "
            "applying — the DB cannot tell them apart."
        )
        if not args.apply:
            print("\nDRY RUN — nothing written. Re-run with --apply.")
            return 0
        n = conn.execute(_UPDATE, (NEW_STATUS, models, dates)).rowcount
        conn.commit()
        print(f"\nAPPLIED: {n} row(s) → status='{NEW_STATUS}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
