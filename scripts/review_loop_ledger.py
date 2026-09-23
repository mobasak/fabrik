#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/review-loop-workflow.md | tests/test_review_loop_ledger.py | commands/_sources/fabrik-review.md
"""review_loop_ledger — a review pass's ledger, read from its workflow run into a FILE (row 5b, D-357).

`fabrik-review-loop` returns its ledger as one tool result, escaped and often truncated; the lead used to
re-derive each pass from it with an ad-hoc script, and hand-typed the next pass's claim list (once as strings
the script rendered `undefined`). Finding 30 of `docs/reference/command-loop-performance.md`: the lead reads a
file, not its scrollback. So:

    review_loop_ledger.py read RUN_DIR [--out FILE] [--box MIN]
        RUN_DIR is the run's transcript dir (the Workflow launch prints it; it holds `journal.jsonl` and one
        `agent-<id>.jsonl` per seat). Writes {seats, candidates, verdicts, ledger_status} to FILE and prints a
        compact table. Every seat carries its MINUTES, from its transcript's first and last timestamp — the
        Workflow API has no per-agent timeout, so an overrun is only ever visible here (`OVER BOX`; one refuter
        ran 59 minutes against a 12-minute box on 2026-09-23). A seat with no result row is `NO RESULT`.
    review_loop_ledger.py next FILE --ids A-S1,B-S2
        The next pass's `slices[].ledger` for exactly those confirmed ids, as objects grouped by slice (the id
        prefix). An id the pass never raised is refused by name.

COBRA (D-253): the cheapest way to a clean-looking file is a pass whose seats returned nothing — a seat with
no result is printed `NO RESULT` and kept in `seats` with `returned: false`, never dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def _minutes(transcript: Path) -> float | None:
    stamps = []
    try:
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                t = json.loads(line).get("timestamp")
            except (ValueError, AttributeError):
                continue
            if t:
                stamps.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
    except OSError:
        return None
    # the span, not last-minus-first: an out-of-order line made a negative duration read as within box (A-H1)
    return round((max(stamps) - min(stamps)).total_seconds() / 60, 1) if len(stamps) > 1 else None


def read_run(run: Path, box: float | None) -> dict:
    journal = run / "journal.jsonl"
    if not journal.is_file():
        raise FileNotFoundError(
            f"{journal} is missing — pass the run's transcript dir (the Workflow launch prints it)"
        )
    # Nothing the journal carries is dropped (review of D-357, pass 1): a result row with no started row is a
    # seat of its own (A-S1), every result row of an agent is kept and counted (A-S7), and a row that cannot be
    # read is counted and printed, never raised as another subcommand's error (A-S3).
    labels: dict[str, str] = {}
    results: dict[str, list] = {}
    unreadable = 0
    for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        aid = row.get("agentId") if isinstance(row, dict) else None
        if not aid:
            unreadable += row.get("type") in ("started", "result") if isinstance(row, dict) else 1
            continue
        if row.get("type") == "started":
            labels[aid] = row.get("label", aid)
        elif row.get("type") == "result":
            results.setdefault(aid, []).append(row.get("result"))
    doc: dict = {
        "run": str(run),
        "unreadable_rows": unreadable,
        "seats": [],
        "candidates": [],
        "verdicts": [],
        "ledger_status": [],
    }
    for aid in list(labels) + [a for a in results if a not in labels]:
        # an orphan is labelled as one, so it can never read as a real seat's label (A-NEW2)
        label = labels.get(aid, f"orphan:{aid}")
        meta = run / f"agent-{aid}.meta.json"
        try:
            model = json.loads(meta.read_text()).get("model")
        except (OSError, ValueError):
            model = None
        minutes = _minutes(run / f"agent-{aid}.jsonl")
        got = [r for r in results.get(aid, []) if isinstance(r, dict)]
        doc["seats"].append(
            {
                "label": label,
                "model": model,
                "minutes": minutes,
                "over_box": bool(box is not None and minutes is not None and minutes > box),
                "untimed": minutes is None,
                "returned": bool(got),
                "duplicate_results": len(got),
            }
        )
        for result in got:
            for c in result.get("candidates") or []:
                doc["candidates"].append({**c, "seat": label})
            for st in result.get("ledger_status") or []:
                doc["ledger_status"].append({**st, "seat": label})
            for v in result.get("verdicts") or []:
                doc["verdicts"].append({**v, "seat": label})
    return doc


def _one(x: object, n: int) -> str:
    """One printed line per field: a seat's multi-line output is collapsed, then cut."""
    return " ".join(str(x).split())[:n]


def _print(doc: dict) -> None:
    for s in doc["seats"]:
        mins = "?" if s["minutes"] is None else f"{s['minutes']:.1f} min"
        flags = (
            ("  OVER BOX" if s["over_box"] else "")
            + ("  UNTIMED" if s.get("untimed") else "")
            + ("" if s["returned"] else "  NO RESULT")
            + (
                f"  DUPLICATE RESULT x{s['duplicate_results']}"
                if s.get("duplicate_results", 0) > 1
                else ""
            )
        )
        print(f"seat {s['label']:<18} {mins:>9}{flags}")
    for c in doc["candidates"]:
        print(
            f"candidate {c.get('id')} {c.get('file')}:{c.get('line')} [{c.get('failure_class')}] {_one(c.get('claim'), 240)}"
        )
    for v in doc["verdicts"]:
        print(f"verdict {v.get('id')} {v.get('verdict')} — {_one(v.get('mechanism'), 240)}")
    for s in doc["ledger_status"]:
        print(
            f"ledger {s.get('id')} {s.get('status')} ({s.get('seat')}) — {_one(s.get('output'), 160)}"
        )
    if doc.get("unreadable_rows"):
        print(
            f"{doc['unreadable_rows']} unreadable journal row(s) — a seat may be missing from this table"
        )
    print(
        f"{len(doc['seats'])} seats · {len(doc['candidates'])} candidates · {len(doc['verdicts'])} verdicts · "
        f"{sum(1 for s in doc['seats'] if s['over_box'])} over box · {sum(1 for s in doc['seats'] if not s['returned'])} no result"
    )


class LedgerError(Exception):
    """`next` cannot name one claim for an id: never raised, raised twice, or no `<slice>-` prefix."""


def next_ledger(doc: dict, ids: list[str]) -> list[dict]:
    # a byte-identical repeat (a result row delivered twice) is ONE claim; only distinct claims sharing an id
    # are ambiguous (A-NEW1)
    by_id: dict[str, list] = {}
    for c in doc["candidates"]:
        rows = by_id.setdefault(c.get("id"), [])
        key = (c.get("file"), c.get("line"), c.get("claim"))
        if all((r.get("file"), r.get("line"), r.get("claim")) != key for r in rows):
            rows.append(c)
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise LedgerError(f"id(s) this pass never raised: {', '.join(missing)}")
    twice = [i for i in ids if len(by_id[i]) > 1]
    if twice:
        raise LedgerError(
            f"id(s) raised more than once (by one seat or two), so they name no single claim: {', '.join(twice)} — "
            "pass the claim by hand as {id, file, line, claim}"
        )
    bare = [i for i in ids if "-" not in i or not i.split("-", 1)[0]]
    if bare:
        raise LedgerError(
            f"id(s) with no `<slice>-` prefix, so no slice owns them: {', '.join(bare)}"
        )
    slices: dict[str, list] = {}
    for i in ids:
        c = by_id[i][0]
        slices.setdefault(i.split("-", 1)[0], []).append(
            {"id": i, "file": c.get("file"), "line": c.get("line"), "claim": c.get("claim")}
        )
    return [{"name": n, "ledger": rows} for n, rows in slices.items()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("run", type=Path)
    r.add_argument("--out", type=Path)
    r.add_argument(
        "--box",
        type=float,
        help="the seats' time box in minutes; a longer seat is flagged OVER BOX",
    )
    n = sub.add_parser("next")
    n.add_argument("ledger", type=Path)
    n.add_argument("--ids", required=True, help="comma-separated confirmed candidate ids")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "read":
            doc = read_run(a.run, a.box)
            if a.out:
                a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
            _print(doc)
        else:
            doc = json.loads(a.ledger.read_text())
            print(
                json.dumps(
                    next_ledger(doc, [i.strip() for i in a.ids.split(",") if i.strip()]),
                    ensure_ascii=False,
                )
            )
    except FileNotFoundError as exc:
        print(f"review_loop_ledger: {exc}", file=sys.stderr)
        return 2
    except LedgerError as exc:
        print(f"review_loop_ledger: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
