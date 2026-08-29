"""The kaizen daily digest — the reader half the measurement pipeline never had.

Operator, 2026-08-30: "without me telling, nothing is measured and improved — why did we
spend time on it?" The collector had been publishing real series for days (37k events,
144/177 closes with verdicts) into a log nobody is shown. The digest is the delivery
surface: latest point + delta per published series, one short Telegram message a day.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "kaizen_digest", REPO / "scripts" / "sysadmin" / "kaizen_digest.py"
)
kd = importlib.util.module_from_spec(_spec)
sys.modules["kaizen_digest"] = kd
_spec.loader.exec_module(kd)


def _series(dirp: Path, name: str, version: int, points: list[dict]) -> None:
    (dirp / "series").mkdir(parents=True, exist_ok=True)
    f = dirp / "series" / f"{name}@v{version}.jsonl"
    f.write_text("\n".join(json.dumps(p) for p in points) + "\n", encoding="utf-8")


def test_digest_composes_latest_point_with_delta(tmp_path):
    _series(tmp_path, "review_rounds", 10, [
        {"day": "2026-08-27", "metric": "review_rounds", "value": 11.0, "cell": "11.0 (n=10)"},
        {"day": "2026-08-28", "metric": "review_rounds", "value": 8.9, "cell": "8.9 (n=15)"},
    ])
    out = kd.compose(tmp_path)
    assert "review_rounds" in out and "8.9 (n=15)" in out
    assert "↓" in out or "-2.1" in out, f"delta missing: {out}"


def test_digest_picks_the_highest_series_version(tmp_path):
    _series(tmp_path, "hole_count", 1, [{"day": "2026-08-20", "metric": "hole_count", "value": 9, "cell": "9"}])
    _series(tmp_path, "hole_count", 3, [{"day": "2026-08-28", "metric": "hole_count", "value": 2, "cell": "2"}])
    out = kd.compose(tmp_path)
    assert "2" in out and "2026-08-20" not in out, "a retired series version leaked into the digest"


def test_empty_store_is_loud_not_silent(tmp_path):
    out = kd.compose(tmp_path)
    assert "NO PUBLISHED SERIES" in out, "an empty store must say so — silence reads as health"
