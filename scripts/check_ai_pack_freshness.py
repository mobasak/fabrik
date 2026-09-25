#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/KILO_BENCHMARK_WORKFLOW.md
"""Warn when AI rule packs in .windsurf/rules/ai/*.md are >90 days unverified.

Reads each pack's `Last content verification: YYYY-MM-DD` line and prints a
warning to stdout when (today - date) > AI_PACK_STALE_DAYS. Packs without the
line are reported as "unstamped" (warning, not error). Exit 0 always — this
is a freshness signal in the daily log, not a gate.

Invoked from wsl_startup_hook.sh after the embedding pipeline, before
sync_extensions.sh.

`--delivered-max-age N` is the second, daily mode (D-415): it reads every auto-managed
`last-refreshed: YYYY-MM-DD` block marker (the GATEWAY_COUNTS and OPENROUTER_ROUTES blocks the
ai-model-catalog engine delivers) and EXITS 1 when any is older than N days, so daily_refresh.sh can
page. The blocks call themselves "live"; on 2026-09-23 all 14 still read 2026-09-07 because the engine
crashed after emitting and before delivering, and nothing noticed for 16 days. The cheapest way to
satisfy this without the outcome is to bump the marker date without new counts — the marker is
written only by the engine's own export step, so a hand-bumped date is a visible diff in a
generated block, never a silent pass.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
AI_PACKS_DIR = FABRIK_ROOT / ".windsurf" / "rules" / "ai"


def _stale_days() -> int:
    """Parse the threshold defensively — a bad env value must not crash the run."""
    raw = os.environ.get("AI_PACK_STALE_DAYS", "90")
    try:
        days = int(raw)
    except ValueError:
        print(f"[ai-pack-freshness] invalid AI_PACK_STALE_DAYS={raw!r}; using 90", file=sys.stderr)
        return 90
    if days < 0:
        print(f"[ai-pack-freshness] negative AI_PACK_STALE_DAYS={raw!r}; using 90", file=sys.stderr)
        return 90
    return days


STALE_DAYS = _stale_days()

VERIFICATION_RE = re.compile(
    r"Last content verification:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


DELIVERED_RE = re.compile(r"last-refreshed:\s*(\d{4}-\d{2}-\d{2})")


def _today() -> date:
    # UTC date. Stamps are date-only, so one written in the operator's local
    # evening can read ±1 day vs UTC near midnight — immaterial at a 90-day
    # threshold, and future-dated stamps are handled as fresh in check_pack.
    return datetime.now(UTC).date()


def check_pack(pack_path: Path, today: date) -> tuple[str, int | None, str]:
    """Return (status, age_days, message). Status: 'fresh' | 'stale' | 'unstamped'."""
    try:
        text = pack_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return ("unstamped", None, f"{pack_path.name}: unreadable ({e.__class__.__name__}: {e})")
    raw_dates = VERIFICATION_RE.findall(text)
    if not raw_dates:
        return (
            "unstamped",
            None,
            f"{pack_path.name}: no `Last content verification:` line — "
            "consider stamping to track refresh cadence",
        )
    parsed: list[date] = []
    for raw in raw_dates:
        try:
            parsed.append(date.fromisoformat(raw))
        except ValueError:
            continue
    if not parsed:
        return ("unstamped", None, f"{pack_path.name}: malformed date(s) {raw_dates!r}")
    # If a pack carries more than one stamp (e.g. a manual one + an
    # auto-injected one), the NEWEST verification is the truthful one.
    verified = max(parsed)
    age = (today - verified).days
    if age < 0:
        return (
            "fresh",
            age,
            f"{pack_path.name}: stamped in the future ({verified.isoformat()}) — clock/typo?",
        )
    if age > STALE_DAYS:
        return (
            "stale",
            age,
            f"{pack_path.name}: verified {age} days ago "
            f"(>{STALE_DAYS}d threshold) — re-verify model lineup / vendor picks",
        )
    return ("fresh", age, f"{pack_path.name}: verified {age}d ago")


def stale_delivered_blocks(packs: list[Path], today: date, max_age: int) -> list[str]:
    """Every `last-refreshed:` block marker older than `max_age` days, as `<pack>: <date> (<n>d)`."""
    stale = []
    for pack in packs:
        try:
            text = pack.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            stale.append(
                f"{pack.name}: unreadable ({e.__class__.__name__}) — cannot prove it fresh"
            )
            continue
        for raw in DELIVERED_RE.findall(text):
            try:
                age = (today - date.fromisoformat(raw)).days
            except ValueError:
                stale.append(f"{pack.name}: malformed last-refreshed {raw!r}")
                continue
            if age > max_age:
                stale.append(f"{pack.name}: last-refreshed {raw} ({age}d old)")
    return stale


def delivered_main(max_age: int) -> int:
    today = _today()
    packs = sorted(AI_PACKS_DIR.glob("*.md")) if AI_PACKS_DIR.is_dir() else []
    markers = 0
    for pack in packs:
        try:
            markers += len(DELIVERED_RE.findall(pack.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            pass  # counted as stale by stale_delivered_blocks
    if markers == 0:
        # Fail CLOSED: no delivered block to measure is the total-loss case this mode exists for.
        print(f"[ai-pack-freshness] ⚠️  no `last-refreshed:` block found under {AI_PACKS_DIR}")
        return 1
    stale = stale_delivered_blocks(packs, today, max_age)
    if not stale:
        print(f"[ai-pack-freshness] delivered blocks fresh (<= {max_age}d) in {len(packs)} packs")
        return 0
    print(f"[ai-pack-freshness] ⚠️  {len(stale)} delivered block(s) older than {max_age}d:")
    for m in stale:
        print(f"  - {m}")
    return 1


def main() -> int:
    if "--delivered-max-age" in sys.argv[1:]:
        # Any malformed use of the paging flag is exit 2, never a fall-through to the warn-only scan:
        # a cron line that lost its value would otherwise turn the page into a silent exit 0.
        if len(sys.argv) != 3 or sys.argv[1] != "--delivered-max-age":
            print("[ai-pack-freshness] usage: --delivered-max-age N", file=sys.stderr)
            return 2
        try:
            return delivered_main(int(sys.argv[2]))
        except ValueError:
            print(
                f"[ai-pack-freshness] invalid --delivered-max-age {sys.argv[2]!r}", file=sys.stderr
            )
            return 2
    today = _today()
    if not AI_PACKS_DIR.is_dir():
        print(f"[ai-pack-freshness] {AI_PACKS_DIR} does not exist — skipping")
        return 0

    packs = sorted(AI_PACKS_DIR.glob("*.md"))
    if not packs:
        print(f"[ai-pack-freshness] no .md files in {AI_PACKS_DIR}")
        return 0

    fresh, stale, unstamped = [], [], []
    for pack in packs:
        try:
            status, _age, msg = check_pack(pack, today)
        except Exception as e:  # noqa: BLE001 — warn-only: one bad pack must not abort the scan
            status, msg = "unstamped", f"{pack.name}: check failed ({e.__class__.__name__}: {e})"
        {"fresh": fresh, "stale": stale, "unstamped": unstamped}[status].append(msg)

    print(
        f"[ai-pack-freshness] {len(packs)} packs scanned "
        f"(threshold: {STALE_DAYS}d) on {today.isoformat()}"
    )
    if stale:
        print(f"[ai-pack-freshness] ⚠️  {len(stale)} STALE pack(s):")
        for m in stale:
            print(f"  - {m}")
    if unstamped:
        print(f"[ai-pack-freshness] ℹ️  {len(unstamped)} unstamped pack(s):")
        for m in unstamped:
            print(f"  - {m}")
    if not stale and not unstamped:
        print(f"[ai-pack-freshness] ✅ all {len(packs)} packs fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
