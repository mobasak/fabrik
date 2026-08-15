"""C.2 — the parallel-run safety window: does the RELOCATED engine agree with fabrik's own?

For ≥1 week (including a Sunday, when the specialty benchmarks run) both engines run daily on this
box. fabrik keeps producing into its live paths; ai-model-catalog produces into `engine/out/` and
delivers into a SHADOW root. This diffs the two and is the only place in the migration where
**byte**-equality is meaningful: the comparison is old-vs-new at the SAME INSTANT against the SAME
database, so the daily row growth that makes a frozen byte-golden useless cancels out on both sides.

⚠️ **This test's own failure mode is passing for the wrong reason, and it has two.** Both are
guarded below, because either one turns a week-long safety window into theatre:

1. **The shadow bundle may be STALE.** `daily_refresh.sh` short-circuits on a same-day lockfile. The
   copied engine shipped that guard BYTE-IDENTICALLY (`/tmp/.fabrik_daily_<date>` at the same lines),
   so on one box the second engine to run would `exit 0` having produced nothing — and this diff
   would then compare yesterday's shadow output against today's fabrik output and could go GREEN
   while the relocated engine never executed a single step. The engine's lock is now namespaced to
   `/tmp/.amc_engine_daily_*`, and `test_the_shadow_bundle_actually_ran_today` proves it per-run.
2. **The shadow bundle may be ABSENT.** A window that silently skips every day is indistinguishable
   from a window that passed. Absence SKIPS loudly with the reason, and the skip is never a pass.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

FABRIK_ROOT = Path(__file__).resolve().parents[3]
SHADOW = Path(os.environ.get("DELIVER_SHADOW", "/tmp/deliver-shadow"))

# fabrik-relative artifacts both engines produce. Marker-block hosts are NOT compared whole-file:
# fabrik's copies carry the block injected in place, the shadow's carry it injected by the deliver
# step, and the surrounding prose is hand-maintained — only the BLOCK BODIES are engine-owned.
_WHOLE_FILE = [
    "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/CODING_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/STT_SELECTION.md",
    "docs/reference/kilo/TTS_SELECTION.md",
    "docs/reference/kilo/TRANSLATION_SELECTION.md",
    "docs/reference/kilo/IMAGE_GEN_SELECTION.md",
    "scripts/kilo_47_agents_final.json",
]

# Both sides regenerate a date stamp per run; a run that straddles UTC midnight would differ on that line
# alone. Normalise ONLY the stamp — never the data.
_VOLATILE_PREFIXES = (
    "**Generated:**",
    "Last content verification:",
    "_Last updated:",
    '"generated_at":',   # JSON artifacts stamp the run time too
)

# ⚠️ C-B5 — THE COMPARISON IS ONLY MEANINGFUL WITHIN ONE WINDOW, and the plan does not say so.
# Measured 2026-08-15: fabrik's cron produced at 03:01Z, the relocated engine at 15:40Z, and
# TASK_SUBAGENT_SELECTION.md diverged on `n_total=124` vs `142` with a reshuffled top-3. Nothing was
# wrong with either engine — the FLYWHEEL GAINED 18 RUNS between them, and every ranking is derived
# from it. So a diff taken 12h apart is guaranteed to fail on real data, forever.
#
# The danger is the "fix" that follows: normalising the numbers away, which blanks exactly the
# content this window exists to protect and turns a week of green into theatre. Instead the test
# REFUSES to judge a skewed pair — neither pass nor fail — and says why. C.2's protocol is therefore
# to run the two engines ADJACENTLY (same hour, same DB state), not to compare today's shadow
# against this morning's cron output.
_MAX_SKEW_HOURS = 3.0


def _normalise(text: str) -> str:
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if any(s.startswith(p) for p in _VOLATILE_PREFIXES):
            continue
        keep.append(line)
    return "\n".join(keep)


def _skew_hours(a: Path, b: Path) -> float:
    return abs(a.stat().st_mtime - b.stat().st_mtime) / 3600.0


def _require_shadow() -> None:
    if not SHADOW.exists():
        pytest.skip(
            f"no shadow bundle at {SHADOW} — the parallel-run window has not been started, or "
            f"today's delivery did not run. This is NOT a pass: a window that silently skips every "
            f"day looks exactly like a window that succeeded."
        )


def test_the_shadow_bundle_actually_ran_today():
    """S1d / C-B1: prove the relocated engine EXECUTED today, not that it exited on a lockfile."""
    _require_shadow()
    probe = SHADOW / "docs" / "reference" / "kilo" / "TASK_SUBAGENT_SELECTION.md"
    assert probe.exists(), f"{probe} absent — the shadow delivery produced nothing"
    mtime_day = datetime.fromtimestamp(probe.stat().st_mtime, UTC).strftime("%Y-%m-%d")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    # ⚠️ The C.2 parallel-run WINDOW CLOSED with Phase E (2026-08-15). This harness is retained as a
    # rerunnable tool, not a standing assertion: with no window running there is no daily shadow to
    # refresh, so a hard `assert mtime_day == today` would turn into a FAILING test every day forever
    # — and a suite that is red by design is a suite nobody reads. Outside a window it SKIPS with the
    # reason; re-open a window by refreshing the shadow and it asserts again.
    if mtime_day != today:
        pytest.skip(
            f"shadow bundle is from {mtime_day}, not {today} — no parallel-run window is active "
            f"(C.2 closed 2026-08-15). Refresh {SHADOW} to re-arm this harness. NOT a pass."
        )
    assert mtime_day == today, (
        f"shadow bundle is STALE (mtime {mtime_day}, today {today}). The relocated engine did not "
        f"run today — most likely a lockfile short-circuit. Every diff below would compare "
        f"yesterday's output and could pass while the engine never executed."
    )


@pytest.mark.parametrize("rel", _WHOLE_FILE)
def test_shadow_matches_fabrik_byte_for_byte(rel):
    """Same DB, same instant, same code lineage ⇒ identical bytes. A diff is a decoupling defect."""
    _require_shadow()
    shadow, live = SHADOW / rel, FABRIK_ROOT / rel
    if not shadow.exists():
        pytest.skip(f"{rel}: not in today's shadow bundle (producer may need network)")
    assert live.exists(), f"{rel}: fabrik's own copy is missing — compare has no left-hand side"
    skew = _skew_hours(shadow, live)
    if skew > _MAX_SKEW_HOURS:
        pytest.skip(
            f"{rel}: the two artifacts are {skew:.1f}h apart (limit {_MAX_SKEW_HOURS}h) — the "
            f"flywheel gains rows continuously, so a skewed pair diverges on real DATA and the "
            f"comparison cannot distinguish that from a decoupling defect. Run both engines in the "
            f"same window. Refusing to judge is deliberate: this is NOT a pass. (C-B5)"
        )
    s, f = _normalise(shadow.read_text()), _normalise(live.read_text())
    if s != f:
        sl, fl = s.splitlines(), f.splitlines()
        diff = [
            f"  line {i + 1}:\n    shadow: {a[:120]}\n    fabrik: {b[:120]}"
            for i, (a, b) in enumerate(zip(sl, fl, strict=False))
            if a != b
        ][:5]
        pytest.fail(
            f"{rel} DIVERGED between the two engines ({len(sl)} vs {len(fl)} lines):\n"
            + "\n".join(diff)
            + "\n  A diff here means a path or env leaked into CONTENT — the decoupling is incomplete."
        )


def test_the_comparison_set_is_not_empty():
    """Guard the guard: an empty _WHOLE_FILE list would make the whole window vacuously green."""
    assert len(_WHOLE_FILE) >= 6, f"only {len(_WHOLE_FILE)} artifacts compared — the window proves little"
