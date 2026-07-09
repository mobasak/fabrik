"""Behavior Contract for seed_specialty_catalog.backfill_reachable_by_provider.

Phase 0 of plan-1 pick_models reachability gate. The pre-fix seeder only ran
`UPDATE ... WHERE id = ?` per specialty-seeded row, so 340+ pre-existing LLM
rows whose providers ARE in AI_VENDOR_ACCESS.md's OpenRouter route list never
had their reachable flag flipped. This function is the bulk backfill by
provider.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _fixture(tmp_path):
    p = tmp_path / "agents.db"
    con = sqlite3.connect(str(p))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, provider TEXT, status TEXT, "
        "blocked INT DEFAULT 0, reachable_with_existing_keys INT DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO agents (id, provider, status) VALUES (?, ?, 'active')",
        [
            ("openai/gpt-5", "openai"),
            ("openai/gpt-5-codex", "openai"),
            ("anthropic/claude-opus-4.5", "anthropic"),
            ("unknown/foo", "unknown_provider"),
        ],
    )
    con.commit()
    return p, con


def test_backfill_flips_only_matching_provider_rows(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    n = backfill_reachable_by_provider(con, {"openai", "anthropic"})
    assert n == 3, f"expected 3 flips, got {n}"
    reachable_by_provider = dict(
        con.execute(
            "SELECT provider, SUM(reachable_with_existing_keys) FROM agents GROUP BY provider"
        )
    )
    assert reachable_by_provider["openai"] == 2
    assert reachable_by_provider["anthropic"] == 1
    assert reachable_by_provider["unknown_provider"] == 0


def test_backfill_idempotent_second_run(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    assert backfill_reachable_by_provider(con, {"openai", "anthropic"}) == 3
    assert backfill_reachable_by_provider(con, {"openai", "anthropic"}) == 0


def test_backfill_empty_accessible_set(tmp_path):
    from seed_specialty_catalog import backfill_reachable_by_provider

    _p, con = _fixture(tmp_path)
    assert backfill_reachable_by_provider(con, set()) == 0


def test_backfill_null_provider_stays_unreachable_by_design(tmp_path):
    """PF1 regression / design attestation: a row with provider=NULL is
    intentionally left at reachable=0. `NULL IN ('openai', ...)` evaluates to
    NULL (falsy) in SQL, so the WHERE clause silently skips such rows.

    That is CORRECT semantics: an unknown-provider row can't be routed to any
    vendor, so it should stay unreachable — an OR fallback would silently flip
    misrouted rows to 'reachable' when in fact no route exists. This test
    locks the behavior in as intentional, not a bug.
    """
    import sqlite3

    from seed_specialty_catalog import backfill_reachable_by_provider

    p = tmp_path / "agents.db"
    con = sqlite3.connect(str(p))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, provider TEXT, status TEXT, "
        "blocked INT DEFAULT 0, reachable_with_existing_keys INT DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO agents (id, provider, status) VALUES (?, ?, 'active')",
        [
            ("openai/gpt-5", "openai"),
            ("unknown-vendor/mystery-model", None),  # NULL provider
        ],
    )
    con.commit()
    n = backfill_reachable_by_provider(con, {"openai"})
    assert n == 1, f"expected only the openai row to flip; got {n}"
    reach_by_id = dict(con.execute("SELECT id, reachable_with_existing_keys FROM agents"))
    assert reach_by_id["openai/gpt-5"] == 1
    assert reach_by_id["unknown-vendor/mystery-model"] == 0, (
        "NULL-provider row must stay unreachable — can't route to unknown vendor"
    )


def test_backfill_flips_shanghai_ai_lab(tmp_path):
    """Plan-2 Phase A regression — ModelScope adds Shanghai_AI_Laboratory
    (Intern-S line) as a new provider path. The seeder's coarse backfill
    must flip a `shanghai-ai-lab` row to reachable=1 once ModelScope's
    vendor row appears in AI_VENDOR_ACCESS.md (parse_vendor_catalog picks
    it up → passes it to backfill_reachable_by_provider).
    """
    import sqlite3

    from seed_specialty_catalog import backfill_reachable_by_provider

    p = tmp_path / "agents.db"
    con = sqlite3.connect(str(p))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, provider TEXT, status TEXT, "
        "blocked INT DEFAULT 0, reachable_with_existing_keys INT DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO agents (id, provider, status) VALUES (?, ?, 'active')",
        [
            ("shanghai-ai-lab/intern-s1", "shanghai-ai-lab"),
            ("shanghai-ai-lab/intern-s1-mini", "shanghai-ai-lab"),
            ("openai/gpt-5", "openai"),
        ],
    )
    con.commit()
    n = backfill_reachable_by_provider(con, {"shanghai-ai-lab"})
    assert n == 2, f"expected both shanghai-ai-lab rows to flip; got {n}"
    reach_by_provider = dict(
        con.execute(
            "SELECT provider, SUM(reachable_with_existing_keys) FROM agents GROUP BY provider"
        )
    )
    assert reach_by_provider["shanghai-ai-lab"] == 2
    assert reach_by_provider["openai"] == 0, (
        "openai stays unreachable — not in the accessible set for this test"
    )


def test_ai_vendor_access_modelscope_row_uses_canonical_db_providers():
    """Plan-2 Phase-E whole-plan review F1 regression guard.

    Bug fixed: the initial ModelScope row listed provider strings
    `paddlepaddle` / `xiaomimimo` / `tencent-hunyuan` (the HF-style names
    ModelScope publishes), but the DB's canonical provider values are
    `baidu` / `xiaomi` / `tencent`. Silent mismatch → zero flips + false
    coverage claims in every downstream doc.

    Grep the MS row's actual TEXT (not parse_vendor_catalog's union of
    all rows — several of these providers ARE listed by other rows like
    SF, so parse_vendor_catalog wouldn't discriminate). A regression that
    re-introduces `paddlepaddle` / `xiaomimimo` / `tencent-hunyuan` here
    would leave the correct string absent from the ModelScope row itself.
    """
    doc = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "docs/reference/kilo/AI_VENDOR_ACCESS.md"
    )
    assert doc.exists(), f"AI_VENDOR_ACCESS.md missing at {doc}"
    lines = [ln for ln in doc.read_text().splitlines() if ln.startswith("| ModelScope |")]
    assert len(lines) == 1, f"expected exactly 1 ModelScope row, got {len(lines)}"
    ms_row = lines[0]
    # Canonical DB provider names — these MUST appear in the ModelScope
    # row's provider column (2nd pipe-delimited field).
    ms_row_second_col = ms_row.split("|")[2]
    for canonical in ("baidu", "xiaomi", "tencent"):
        assert f" {canonical}" in ms_row_second_col or f",{canonical}" in ms_row_second_col or ms_row_second_col.strip().startswith(canonical), (
            f"ModelScope row's provider list missing canonical DB name {canonical!r}: {ms_row_second_col.strip()!r}"
        )
    # These wrong HF-style names must NOT appear (regression from Phase-E F1 fix).
    for wrong in ("paddlepaddle", "xiaomimimo", "tencent-hunyuan"):
        assert wrong not in ms_row_second_col, (
            f"ModelScope row's provider list contains pre-fix wrong name {wrong!r} — "
            f"was corrected 2026-07-09 to canonical DB provider name. Row: {ms_row_second_col.strip()!r}"
        )
