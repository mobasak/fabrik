"""Rules-pack version-pin tripwire (the "what happens in one year" mechanism).

Pins the pure logic: pin extraction across packs, the node LTS-date semantics
(a FUTURE lts date must not fire — node 26's lts field was a date string at
build time), and drift comparison. Network and mail stay out of tests.
"""

from datetime import date

from scripts.sysadmin.rules_currency_watch import (
    drifts,
    latest_node_lts,
    pinned_versions,
)


def test_pinned_versions_reads_all_packs(tmp_path):
    (tmp_path / "10-python.md").write_text("FROM python:3.14-slim-bookworm\n")
    (tmp_path / "30-ops.md").write_text("python:3.13-slim-bookworm and node:24-bookworm-slim\n")
    (tmp_path / "20-typescript.md").write_text("FROM node:24-bookworm-slim\n")
    assert pinned_versions(tmp_path) == {"python": "3.14", "node": "24"}


def test_future_lts_date_does_not_fire():
    rows = [
        {"cycle": "26", "lts": "2026-10-27"},
        {"cycle": "24", "lts": "2025-10-28"},
    ]
    assert latest_node_lts(rows, today=date(2026, 9, 1)) == "24"
    assert latest_node_lts(rows, today=date(2026, 11, 1)) == "26"


def test_drift_detection_both_directions():
    assert drifts({"python": "3.13", "node": "24"}, {"python": "3.14", "node": "24"}) == {
        "python": ("3.13", "3.14")
    }
    assert drifts({"python": "3.14", "node": "24"}, {"python": "3.14", "node": "26"}) == {
        "node": ("24", "26")
    }
    assert drifts({"python": "3.14"}, {"python": "3.14", "node": "26"}) == {}
    # a two-digit minor must compare numerically, not lexically
    assert drifts({"python": "3.9"}, {"python": "3.14"}) == {"python": ("3.9", "3.14")}
