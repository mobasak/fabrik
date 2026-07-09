"""Behavior Contract for Phase A rank_coding + rank_task reachability emit.

Plan-1 Phase A.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _make_agents_db(path: Path, rows: list[tuple[str, str, int, str]]) -> None:
    """rows: [(id, provider, reachable, service_type)]."""
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, provider TEXT, "
        "service_type TEXT, status TEXT, blocked INT DEFAULT 0, "
        "reachable_with_existing_keys INT DEFAULT 0)"
    )
    con.executemany(
        "INSERT INTO agents (id, provider, service_type, status, "
        "reachable_with_existing_keys) VALUES (?, ?, ?, 'active', ?)",
        [(rid, prov, st, reach) for (rid, prov, reach, st) in rows],
    )
    con.commit()
    con.close()


def test_rank_coding_reachable_stats_reads_only_reachable_llm_rows(tmp_path):
    """A.1: `_reachable_stats()` returns only reachable llm agents.

    Fixture: 2 reachable llm + 1 unreachable llm + 1 reachable tts (wrong service).
    Expected: n_reach=2, reachable_ids = {llm reachables}.
    """
    db = tmp_path / "agents.db"
    _make_agents_db(
        db,
        [
            ("reachable/llm-1", "openai", 1, "llm"),
            ("reachable/llm-2", "anthropic", 1, "llm"),
            ("unreach/llm-3", "unknown", 0, "llm"),
            ("reachable/tts-1", "elevenlabs", 1, "tts"),
        ],
    )

    import rank_coding_subagents as rc

    with patch.object(rc, "DB_PATH", db):
        stats = rc._reachable_stats()

    assert stats["n_reach"] == 2
    assert stats["n_total"] == 3, "unreachable llm counts in total; tts does NOT"
    assert stats["reachable_ids"] == {"reachable/llm-1", "reachable/llm-2"}


def test_rank_task_reachable_stats_includes_all_service_types(tmp_path):
    """A.2: rank_task's reachable-set covers ALL active service_types (task
    ranker serves review/docs/... not just LLM), unlike rank_coding which
    scopes to llm-only.
    """
    db = tmp_path / "agents.db"
    _make_agents_db(
        db,
        [
            ("reachable/llm", "openai", 1, "llm"),
            ("reachable/tts", "elevenlabs", 1, "tts"),
            ("unreach/llm", "unknown", 0, "llm"),
        ],
    )

    import rank_task_subagents as rt

    with patch.object(rt, "_AGENTS_DB", db):
        stats = rt._reachable_stats()

    assert stats["n_reach"] == 2, "both reachable rows across service types"
    assert stats["n_total"] == 3
    assert stats["reachable_ids"] == {"reachable/llm", "reachable/tts"}


def test_rank_task_reachable_stats_fail_soft_on_missing_db(tmp_path):
    """A.4: missing DB → zeros, no raise (fail-soft; consumer treats empty set
    as 'no filter available' and falls through to Phase C fallback)."""
    import rank_task_subagents as rt

    with patch.object(rt, "_AGENTS_DB", tmp_path / "does-not-exist.db"):
        # sqlite3.connect creates on write; use a directory to force ERROR.
        with patch("sqlite3.connect", side_effect=sqlite3.Error("nope")):
            stats = rt._reachable_stats()

    assert stats == {"n_reach": 0, "n_total": 0, "reachable_ids": set()}


def test_rank_task_render_includes_reachable_comments(tmp_path):
    """A.3: `render()` emits `<!-- reachable: N/M -->` and `<!-- reachable-set: ... -->`
    inside the header block."""
    db = tmp_path / "agents.db"
    _make_agents_db(
        db,
        [
            ("openai/gpt-5", "openai", 1, "llm"),
            ("some/tts", "elevenlabs", 1, "tts"),
        ],
    )

    import rank_task_subagents as rt

    with patch.object(rt, "_AGENTS_DB", db):
        out = rt.render([], state="ok")

    assert "<!-- reachable: 2/2 -->" in out
    assert "<!-- reachable-set: openai/gpt-5, some/tts -->" in out
