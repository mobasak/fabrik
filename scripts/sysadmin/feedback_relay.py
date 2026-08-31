#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md, scripts/sysadmin/weekly_catchup.sh | none
"""FEEDBACK relay — closes the loop the operator asked for five times (D-055, then the 6th ask:
"i dont read anything, you read").

Every command close persists its FEEDBACK verdict text (D-055). Nobody was the READER: the digest
was operator-facing, and the operator does not read dashboards. This relay makes an AGENT the
reader — it rides the daily kaizen cron slot (a rider in ``weekly_catchup.sh``'s
``kaizen_collect_v2.py`` case, so no new crontab line), gathers every not-yet-relayed close whose
verdict carries substance, and mails ONE digest to the shared ``fabrik`` inbox addressed to
``infra``. The hub session that opens it is bound by the handle-now law: read -> validate -> fix or
route -> ack. That is the report-back loop: agents write feedback at close, the machinery delivers
it to the machinery's owner, a session acts on it.

Idempotent by WATERMARK: a run-record is relayed at most once (its ``updated_ts`` must exceed the
stored watermark, which advances only after a successful send). Quiet when there is nothing new.
``none — surfaces`` verdicts are counted in the digest header but not expanded — the reader's time
goes to the filings.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RUNS_DIR = Path.home() / ".claude" / "state" / "command-runs"
WATERMARK = Path.home() / ".claude" / "state" / "feedback-relay.watermark"
MAIL = Path("/opt/fabrik/scripts/mail.py")
CLOSED = {"done", "blocked"}


def _gather(runs: Path, since: float) -> tuple[list[tuple[float, str, str, str, str]], int]:
    """Return ([(ts, date, repo, command, text)] for substantive verdicts, count of plain nones)."""
    rows: list[tuple[float, str, str, str, str]] = []
    nones = 0
    for f in runs.glob("*.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or r.get("state") not in CLOSED:
            continue
        ts = float(r.get("updated_ts") or 0)
        if ts <= since:
            continue
        text = str(r.get("feedback_text") or "").strip()
        if not text:
            continue  # pre-D-055 close — nothing to relay
        if str(r.get("feedback") or "") == "none":
            nones += 1
            continue
        rows.append(
            (
                ts,
                str(r.get("updated_at") or "")[:10],
                str(r.get("repo_root") or "?"),
                str(r.get("command") or "?"),
                text,
            )
        )
    rows.sort()
    return rows, nones


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", default="", help=f"run-record dir (default {RUNS_DIR})")
    ap.add_argument("--watermark", default="", help=f"watermark file (default {WATERMARK})")
    ap.add_argument("--dry-run", action="store_true", help="print the digest, send nothing, keep the watermark")
    args = ap.parse_args(argv)
    runs = Path(args.runs) if args.runs else RUNS_DIR
    wm_path = Path(args.watermark) if args.watermark else WATERMARK

    since = 0.0
    try:
        since = float(wm_path.read_text().strip())
    except (OSError, ValueError):
        pass  # first run relays everything persisted so far — bounded by D-055's landing date

    rows, nones = _gather(runs, since)
    if not rows:
        return 0  # quiet when fresh — the cron log stays at the job's own cadence

    lines = [
        "Subject: FEEDBACK relay — "
        f"{len(rows)} filed verdict(s) from command closes (+{nones} none-verdicts, not expanded)",
        "",
        "Agents reported the following about the machinery at their run closes (D-055 persisted",
        "text; relayed once each). HANDLE-NOW applies: validate each, fix in-beat or route by beat,",
        "then ack. The none-verdicts are countable via check_feedback_duty.py --digest.",
        "",
    ]
    for _ts, date, repo, cmd, text in rows:
        lines.append(f"--- {date} · {repo} · /{cmd}")
        lines.append(text)
        lines.append("")
    body = "\n".join(lines)

    if args.dry_run:
        print(body)
        return 0

    proc = subprocess.run(
        [sys.executable, str(MAIL), "send", "--to", "fabrik", "--to-agent", "infra", "--kind", "finding"],
        input=body,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(f"feedback_relay: mail send failed rc={proc.returncode}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return 1  # watermark NOT advanced — the batch retries on the next cadence
    wm_path.parent.mkdir(parents=True, exist_ok=True)
    wm_path.write_text(str(rows[-1][0]))
    print(f"feedback_relay: relayed {len(rows)} verdict(s) -> fabrik/infra ({proc.stdout.strip()[-60:]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
