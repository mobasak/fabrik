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


def test_stale_claims_window_and_supersede_semantics():
    from scripts.sysadmin.rules_currency_watch import stale_claims

    today = date(2027, 3, 1)
    rows = [
        {"id": "fresh", "last_verified": "2027-01-01", "window_days": 90},
        {"id": "stale", "last_verified": "2026-09-01", "window_days": 90},
        {"id": "superseded", "last_verified": "2026-01-01", "window_days": 90, "superseded": "2026-06-01"},
        {"id": "broken-row"},  # unparseable = stale by definition, must surface
        {"id": "default-window", "last_verified": "2026-08-01"},  # 180d default -> stale at 212d
    ]
    ids = [c["id"] for c in stale_claims(rows, today)]
    assert ids == ["stale", "broken-row", "default-window"]


def test_auto_update_preserves_versions_yaml_comments():
    # yaml.safe_load->safe_dump round-trips eat every comment — the file's whole
    # self-documentation (incl. the node_engines_floor POLICY note). The updater
    # must rewrite values at TEXT level, comments intact.
    from scripts.sysadmin.rules_currency_watch import _update_versions_text

    text = (
        "# MACHINE-OWNED header comment\n"
        "updated: 2026-09-01\n"
        "versions:\n"
        '  python_stable: "3.14"      # endoflife.date\n'
        '  node_lts: "24"             # api/nodejs.json\n'
        '  node_engines_floor: "22"   # POLICY, not auto-watched\n'
    )
    new = _update_versions_text(text, {"node": ("24", "26")}, date(2026, 10, 29))
    assert '  node_lts: "26"             # api/nodejs.json' in new
    assert "# MACHINE-OWNED header comment" in new
    assert "# POLICY, not auto-watched" in new
    assert 'python_stable: "3.14"' in new  # untouched key keeps value AND comment
    assert "updated: 2026-10-29" in new
    # shape drift (key missing) -> None; the caller falls back to the drift mail
    assert _update_versions_text("versions: {}\n", {"node": ("24", "26")}, date(2026, 10, 29)) is None


def test_register_parses_and_all_claims_fresh_at_seed():
    # The live register must load, and at seed time nothing is stale — the
    # first claims mail is owed at the first window expiry, not at landing.
    from scripts.sysadmin.rules_currency_watch import _load_claims, stale_claims

    claims = _load_claims()
    assert len(claims) >= 9
    assert all(c.get("verify") and c.get("pack") for c in claims)
    assert stale_claims(claims, date(2026, 9, 2)) == []
