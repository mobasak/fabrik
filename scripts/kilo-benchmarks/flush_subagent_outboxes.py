#!/usr/bin/env python3
# AFTER-EDIT: autocommit_pipeline_outputs.sh (none) | daily_refresh.sh (wires this) | tests/test_flush_subagent_outboxes.py
"""Fleet-wide outbox flusher — replay every repo's stranded subagent rows into the flywheel.

`libs/subagents/pg_ledger.flush_outbox` was DESIGNED for this and never wired: its own docstring says
*"run from a machine WITH the DSN (the hub, e.g. wired into ``daily_refresh.sh`` next to the ranking
regen)"* (`pg_ledger.py:855-858`). Nothing called it on any schedule — `crontab -l` and a grep over
`scripts/` both returned zero — so rows accumulated on disk in every repo that dispatches subagents.

⚠️ THE POPULATION IS ENUMERATED, NEVER ASSERTED. Three successive counts of the same backlog —
1,465 → 3,487 → 3,505 — were each a different glob presented as a total (a bare `pg_outbox.jsonl`
missing the crashed-flush residuals; then a `-maxdepth 4` missing two nested repos). This walker
therefore PRINTS what it walked. A future reader gets the list, not a number someone typed once.

Design constraints, each from a measured defect (plan 2026-09-02-plan-1-flywheel-recording, Phase A):

* **LOOP per directory.** `_flush_locked` processes the `.flushing` residual **or** the live outbox,
  never both — *"there is NO file-merging"* (`pg_ledger.py:864-869`). Four repos hold BOTH, so a
  one-shot call recovers the residual and silently leaves the live rows for tomorrow.
* **`receipt_dir` is REQUIRED.** With it unset, `ledger._receipts_path` falls back to `.tmp/subagents`
  relative to CWD — the hub — so flushing another repo's rows would append that repo's receipts to
  `/opt/fabrik/.tmp/subagents/receipts.jsonl` and give the owning repo none. Receipts are what
  `check_subagent_flywheel.py` reconciles against; a silent misroute, not an error.
* **NEVER assert `rows_after - rows_before == returned`.** `flush_outbox` returns `len(good)`, the
  parse-survivor count, and `_INSERT` ends `ON CONFLICT DO NOTHING` (`pg_ledger.py:85`) — so a batch
  containing an already-present `agent_id` legitimately lands fewer rows than it returns. An earlier
  draft of the plan mandated that equality; it is false by construction and would have redded the
  daily refresh every day.
* **Exit 0 ALWAYS.** This is a publisher's helper: a flusher that reds the daily refresh is worse
  than an unflushed row. The reasons are printed, never raised.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.subagents import pg_ledger  # noqa: E402

# Depth-unbounded on purpose: `/opt/trade-intelligence/web/` and `/opt/fabrik-lib/subagents/` each
# carry their own outbox and are invisible to a `/opt/*/` glob. The bound IS the defect this walker
# was written to stop repeating.
OUTBOX_GLOBS = ("*/.tmp/subagents", "*/*/.tmp/subagents", "*/*/*/.tmp/subagents")
OUTBOX_FILES = ("pg_outbox.jsonl", "pg_outbox.flushing.jsonl")
_MAX_ROUNDS = 20  # a pathological directory can never spin the daily refresh


def outbox_dirs(root: Path) -> list[Path]:
    """Every `.tmp/subagents` under `root` that currently holds outboxed rows, sorted."""
    seen: set[Path] = set()
    for pattern in OUTBOX_GLOBS:
        for d in root.glob(pattern):
            if d.is_dir() and any((d / f).is_file() for f in OUTBOX_FILES):
                seen.add(d)
    return sorted(seen)


def pending_rows(d: Path) -> int:
    """Rows waiting in this directory — live outbox plus any crashed-flush residual."""
    n = 0
    for f in OUTBOX_FILES:
        p = d / f
        if p.is_file():
            try:
                n += sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return n


def repo_of(d: Path, root: Path) -> str:
    """The owning repo name — the walker is the ONLY place that knows it.

    A stranded row's `project` field is a run label, not a repo (4,435 of 9,327 rows say
    `project='review'`), so the mapping this emits is the input the attribution phase needs.
    """
    try:
        return d.relative_to(root).parts[0]
    except ValueError:
        return d.name


def flush_dir(d: Path, *, dry_run: bool = False) -> tuple[int, list[str], int]:
    """Drain ONE directory to exhaustion. Returns (flushed, reasons, rounds)."""
    if dry_run:
        return 0, ["dry-run"], 0
    total = 0
    reasons: list[str] = []
    for rounds in range(1, _MAX_ROUNDS + 1):
        sink: list[str] = []
        n = pg_ledger.flush_outbox(outbox_dir=str(d), receipt_dir=str(d), reason_sink=sink)
        total += n
        reasons.extend(sink)
        # a round that moved nothing is the end of this directory — either it is drained
        # (`outbox-empty`) or something is stopping it, and the reason is already recorded.
        if n == 0:
            return total, reasons, rounds
    reasons.append(f"round-cap-{_MAX_ROUNDS}-reached")
    return total, reasons, _MAX_ROUNDS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/opt", help="tree to walk (default: /opt)")
    ap.add_argument("--dry-run", action="store_true", help="enumerate only; flush nothing")
    ap.add_argument("--manifest", help="write a repo→rows JSON manifest here")
    args = ap.parse_args(argv)

    root = Path(args.root)
    dirs = outbox_dirs(root)

    if not dirs:
        print("[flush-outboxes] no outboxes found — nothing stranded")
        return 0

    # ⚠️ The SINK is checked once, up front. Without a DSN every directory would report
    # `dsn-missing` and the walker would look like 20 separate failures instead of one
    # unreachable sink — and, worse, it must NEVER claim or delete an outbox it cannot deliver.
    if not (os.environ.get("SUBAGENT_RUNS_DSN") or "").strip():
        pending = sum(pending_rows(d) for d in dirs)
        print(
            f"[flush-outboxes] SINK UNREACHABLE — SUBAGENT_RUNS_DSN is unset. 0 flushed, "
            f"{pending} row(s) left in place across {len(dirs)} outbox dir(s). Nothing was claimed.",
            file=sys.stderr,
        )
        return 0

    manifest: list[dict[str, object]] = []
    total_flushed = 0
    total_pending = 0
    print(f"[flush-outboxes] walked {len(dirs)} outbox dir(s) under {root}:")
    for d in dirs:
        repo = repo_of(d, root)
        before = pending_rows(d)
        total_pending += before
        # ⚠️ PER-DIRECTORY, so ONE repo's fault cannot skip the others. `flush_outbox` documents
        # itself as never-raising, but this walk touches ~10 repos it does not own: a vanished
        # directory, a permission change mid-walk, or a future change to that contract would
        # otherwise abort every repo after the failing one — and the top-level guard would exit 0,
        # making a half-finished walk look like a completed one (phase-A review, finder unit 0).
        try:
            flushed, reasons, rounds = flush_dir(d, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001 — one repo's fault is not the fleet's
            flushed, reasons, rounds = 0, [f"walker-error: {exc!r}"], 0
        total_flushed += flushed
        after = pending_rows(d)
        uniq = sorted(set(reasons))
        print(
            f"  {repo:<26} {str(d.relative_to(root)):<52} pending {before:>5} · "
            f"flushed {flushed:>5} · left {after:>5} · rounds {rounds} · reasons {uniq or '[]'}"
        )
        manifest.append(
            {"repo": repo, "dir": str(d), "pending_before": before,
             "flushed": flushed, "left": after, "rounds": rounds, "reasons": uniq}
        )

    # NOT an equality assertion — see the module docstring. `flushed` counts parse survivors and
    # `ON CONFLICT DO NOTHING` legitimately absorbs duplicates, so flushed < pending is EXPECTED.
    print(
        f"[flush-outboxes] total: {total_flushed} flushed of {total_pending} pending "
        f"across {len(dirs)} dir(s){' (dry run — nothing flushed)' if args.dry_run else ''}"
    )
    if args.manifest:
        # ⚠️ A caller-supplied path is untrusted I/O, and this raised `FileNotFoundError` → exit 1
        # on an unwritable directory (found in this phase's own review). The flush ALREADY HAPPENED
        # by this point; killing the step here would red the daily refresh over a reporting artifact.
        try:
            Path(args.manifest).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
            print(f"[flush-outboxes] manifest written to {args.manifest}")
        except OSError as exc:
            print(f"[flush-outboxes] manifest NOT written ({exc}) — the flush itself succeeded",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    # ⚠️ THE LAST LINE OF THE FAIL-OPEN CONTRACT. This runs from the daily refresh; an unhandled
    # exception here would exit non-zero and mark the step failed for a fault that is, by design,
    # never worth stopping the pipeline for. Every deliberate outcome already returns 0 — this
    # catches the ones nobody thought of, LOUDLY.
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — fail-open is the contract
        print(f"[flush-outboxes] UNEXPECTED FAILURE ({exc!r}) — exiting 0 by contract; "
              "rows are left in place and the next run retries", file=sys.stderr)
        raise SystemExit(0) from None
