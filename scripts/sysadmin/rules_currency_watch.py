#!/usr/bin/env python3
# AFTER-EDIT: scripts/sysadmin/weekly_catchup.sh, docs/STRATEGIC_BACKLOG.md (rules-pass class ledger) | none
"""Rules-pack version-pin tripwire (operator question 2026-09-01: "what will happen
in one year later" — without this, the answer was "the pin drifts again").

The rules packs pin exact runtime versions by design (agents copy examples
verbatim; builds need pins; symbolic wording resolves nondeterministically per
agent). The measured failure mode: the literal outlives the release it tracked —
``python:3.13`` sat stale ~11 months past 3.14. The manifesto's answer is an
ARMED TRIPWIRE ("a closed loop without one is merely abandoned"): this watcher
rides the weekly kaizen cron (a rider in ``weekly_catchup.sh``, same pattern as
``feedback_relay.py`` — no new crontab line, that surface is operator-owned),
compares the packs' pinned python/node versions against the live
endoflife.date API, and MAILS fabrik/infra when a newer stable/LTS exists.
The mail lands under the handle-now law, so the drift becomes a forced
one-line fix instead of a dashboard nobody reads.

Watermarked per-version: one mail per NEW upstream release, never a weekly nag
(a tripwire that cries weekly is wallpaper). Network failure = silent exit 0 —
the cron log stays clean and next week retries; the gate is never involved
(offline-fast stays intact).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

RULES_DIR = Path("/opt/fabrik/.windsurf/rules/core")
WATERMARK = Path.home() / ".claude" / "state" / "rules-currency.watermark"
MAIL = Path("/opt/fabrik/scripts/mail.py")

_PY_PIN = re.compile(r"python:(\d+\.\d+)")
_NODE_PIN = re.compile(r"node:(\d+)")


def pinned_versions(rules_dir: Path) -> dict[str, str]:
    """Highest pinned python minor + node major across the core packs."""
    py: set[tuple[int, int]] = set()
    node: set[int] = set()
    for f in rules_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in _PY_PIN.finditer(text):
            major, minor = m.group(1).split(".")
            py.add((int(major), int(minor)))
        for m in _NODE_PIN.finditer(text):
            node.add(int(m.group(1)))
    out: dict[str, str] = {}
    if py:
        out["python"] = ".".join(map(str, max(py)))
    if node:
        out["node"] = str(max(node))
    return out


def latest_python(rows: list[dict]) -> str:
    return str(rows[0]["cycle"])


def latest_node_lts(rows: list[dict], today: date) -> str:
    """Newest cycle whose LTS date has PASSED — the ``lts`` field is False or a
    date string, and a future date (announced, not yet LTS) must not fire."""
    for r in rows:
        lts = r.get("lts")
        if lts is True:
            return str(r["cycle"])
        if isinstance(lts, str):
            try:
                if date.fromisoformat(lts) <= today:
                    return str(r["cycle"])
            except ValueError:
                continue
    return "0"


def drifts(pinned: dict[str, str], live: dict[str, str]) -> dict[str, tuple[str, str]]:
    """{runtime: (pinned, live)} where live is newer than pinned."""
    out: dict[str, tuple[str, str]] = {}
    if "python" in pinned and "python" in live:
        pv = tuple(map(int, pinned["python"].split(".")))
        lv = tuple(map(int, live["python"].split(".")))
        if lv > pv:
            out["python"] = (pinned["python"], live["python"])
    if "node" in pinned and "node" in live:
        if int(live["node"]) > int(pinned["node"]):
            out["node"] = (pinned["node"], live["node"])
    return out


def _fetch(product: str) -> list[dict]:
    with urllib.request.urlopen(f"https://endoflife.date/api/{product}.json", timeout=15) as r:
        return json.load(r)


def main() -> int:
    try:
        pinned = pinned_versions(RULES_DIR)
        live = {
            "python": latest_python(_fetch("python")),
            "node": latest_node_lts(_fetch("nodejs"), date.today()),
        }
    except Exception:
        return 0  # network/parse blip — next week retries; never noisy, never blocking
    found = drifts(pinned, live)
    if not found:
        return 0
    seen: dict[str, str] = {}
    try:
        seen = json.loads(WATERMARK.read_text())
    except Exception:
        pass
    fresh = {k: v for k, v in found.items() if seen.get(k) != v[1]}
    if not fresh:
        return 0
    lines = [
        "Subject: RULES-PIN DRIFT — a pack pins a runtime the world has moved past",
        "",
        "The rules-currency tripwire (rides the weekly cron) found the pinned version literal",
        "behind the live release line. The fix is ONE line in the owning pack (30-ops.md base-image",
        "table / the runtime pack), plus its dated 'as of' note — see the exact+dated+single-owner",
        "pinning policy (rules pass, 2026-09-01).",
        "",
    ]
    for runtime, (pin, cur) in sorted(fresh.items()):
        lines.append(f"- {runtime}: packs pin {pin}; current stable/LTS is {cur} (endoflife.date)")
    body = "\n".join(lines) + "\n"
    proc = subprocess.run(
        [sys.executable, str(MAIL), "send", "--to", "fabrik", "--to-agent", "infra", "--kind", "finding"],
        input=body,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(f"rules_currency_watch: mail send failed rc={proc.returncode}", file=sys.stderr)
        return 1  # watermark NOT advanced — retried next week
    seen.update({k: v[1] for k, v in fresh.items()})
    WATERMARK.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK.write_text(json.dumps(seen))
    print(f"rules_currency_watch: drift mailed -> fabrik/infra ({', '.join(sorted(fresh))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
