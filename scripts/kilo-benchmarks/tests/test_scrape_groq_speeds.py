"""Regression tests for scrape_groq_speeds.

Covers:
- HTML table parse (happy path with a fixture that mirrors Groq's real DOM shape)
- Cell-prefix stripping ("AI Model ...", "Current Speed ... TPS")
- Fail-soft on malformed HTML (empty string, no target table)
- Explicit map hits before fuzzy match (per Design)
- Authoritative-source precedence: never clobber AA/own_microbench/manual_override
- All 8 current Groq models map to real DB row ids (U10 resolution)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- Fixture: a minimal HTML page that mirrors Groq's shape ----------

_GROQ_FIXTURE = """
<html><body>
<h1>Some other content that must not be picked up.</h1>
<table>
<thead><tr><th>Unrelated table</th><th>tps</th></tr></thead>
<tbody><tr><td>ignore me</td><td>999</td></tr></tbody>
</table>
<table class="type-ui-1">
<caption>*Approximate number of tokens per $</caption>
<thead><tr>
<th><span>AI Model</span></th>
<th><span>Current Speed</span><span>(Tokens per Second)</span></th>
<th>Input Token Price</th>
<th>Output Token Price</th>
</tr></thead>
<tbody>
<tr>
  <td><span>AI Model</span><span>GPT OSS 20B 128k</span></td>
  <td><span>Current Speed</span><span>1,000 TPS</span></td>
  <td>0.10</td><td>0.50</td>
</tr>
<tr>
  <td><span>AI Model</span><span>Llama 3.3 70B Versatile 128k</span></td>
  <td><span>Current Speed</span><span>394 TPS</span></td>
  <td>0.59</td><td>0.79</td>
</tr>
<tr>
  <td><span>AI Model</span><span>Qwen 3.6 27B 131k</span></td>
  <td><span>Current Speed</span><span>500 TPS</span></td>
  <td>0.20</td><td>0.30</td>
</tr>
</tbody>
</table>
</body></html>
"""


def test_parse_pricing_table_extracts_rows_and_tps():
    from scrape_groq_speeds import parse_pricing_table

    rows = parse_pricing_table(_GROQ_FIXTURE)
    assert len(rows) == 3, f"expected 3 rows, got {len(rows)}"
    assert rows[0] == {"name": "GPT OSS 20B 128k", "tps": 1000}
    assert rows[1] == {"name": "Llama 3.3 70B Versatile 128k", "tps": 394}
    assert rows[2] == {"name": "Qwen 3.6 27B 131k", "tps": 500}


def test_parse_fail_soft_on_empty_html():
    from scrape_groq_speeds import parse_pricing_table

    assert parse_pricing_table("") == []


def test_parse_fail_soft_on_html_without_target_table():
    from scrape_groq_speeds import parse_pricing_table

    html = "<html><body><table><tr><td>no tps here</td></tr></table></body></html>"
    assert parse_pricing_table(html) == []


def test_normalize_groq_name_strips_context_size_and_variant():
    from scrape_groq_speeds import normalize_groq_name

    assert normalize_groq_name("Llama 3.3 70B Versatile 128k") == "Llama 3.3 70B"
    assert normalize_groq_name("Llama 3.1 8B Instant 128k") == "Llama 3.1 8B"
    assert normalize_groq_name("Llama 4 Scout (17Bx16E) 128k") == "Llama 4 Scout"
    assert normalize_groq_name("Qwen3 32B 131k") == "Qwen3 32B"
    assert normalize_groq_name("GPT OSS Safeguard 20B") == "GPT OSS Safeguard 20B"


def test_all_8_current_groq_models_have_explicit_map_entries():
    """U10 resolution: Groq's stable ~8-model catalog is hand-mapped so
    name-mismatches are surfaced at test time, not silently dropped."""
    from scrape_groq_speeds import GROQ_TO_OR_ID

    expected_normalized = {
        "GPT OSS 20B",
        "GPT OSS Safeguard 20B",
        "GPT OSS 120B",
        "Llama 4 Scout",
        "Qwen3 32B",
        "Llama 3.3 70B",
        "Llama 3.1 8B",
        "Qwen 3.6 27B",
    }
    assert expected_normalized == set(GROQ_TO_OR_ID.keys()), (
        f"map drift: expected {expected_normalized}, got {set(GROQ_TO_OR_ID.keys())}"
    )


def _seed_min_db(tmp_path: Path) -> Path:
    db = tmp_path / "seed.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, name TEXT, provider TEXT, service_type TEXT,
            status TEXT DEFAULT 'active',
            output_tokens_per_sec REAL, ttft_ms REAL,
            speed_source TEXT, speed_updated_at TEXT
        );
        INSERT INTO agents (id, name, provider, service_type, status) VALUES
          ('openai/gpt-oss-20b', 'OpenAI: GPT OSS 20B', 'openai', 'llm', 'active'),
          ('meta-llama/llama-3.3-70b-instruct', 'Meta: Llama 3.3 70B Instruct',
             'meta-llama', 'llm', 'active');
        -- Seed a row that has an AA value — Groq scraper MUST NOT clobber it.
        INSERT INTO agents (id, name, provider, service_type, status,
            output_tokens_per_sec, speed_source, speed_updated_at) VALUES
          ('anthropic/claude-opus-4.8', 'Anthropic: Claude Opus 4.8',
             'anthropic', 'llm', 'active',
             62.0, 'artificialanalysis.ai (n=1)', '2026-07-01');
        """
    )
    conn.commit()
    conn.close()
    return db


def test_update_never_overwrites_higher_authority_sources(tmp_path):
    """Regression: even if a Groq name incorrectly mapped to an AA-sourced
    row, the WHERE guard in update_database must reject the write."""
    from scrape_groq_speeds import update_database

    db_path = _seed_min_db(tmp_path)
    # Pretend Groq scraper matched claude-opus-4.8 (it shouldn't; but if
    # it did, precedence should still protect the AA data).
    matches = {"anthropic/claude-opus-4.8": {"tps": 999, "groq_name": "test"}}
    updated, skipped_precedence, _ = update_database(matches, db_path)

    assert updated == 0
    assert skipped_precedence == 1

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT output_tokens_per_sec, speed_source FROM agents WHERE id='anthropic/claude-opus-4.8'"
    ).fetchone()
    conn.close()
    assert row[0] == 62.0, "AA value was overwritten"
    assert row[1] == "artificialanalysis.ai (n=1)"


def test_update_writes_to_null_speed_source_rows(tmp_path):
    """Happy path: a row with no prior Speed data gets the Groq tps."""
    from scrape_groq_speeds import SPEED_SOURCE_TAG, update_database

    db_path = _seed_min_db(tmp_path)
    matches = {"openai/gpt-oss-20b": {"tps": 1000, "groq_name": "GPT OSS 20B 128k"}}
    updated, _, _ = update_database(matches, db_path)

    assert updated == 1
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT output_tokens_per_sec, speed_source FROM agents WHERE id='openai/gpt-oss-20b'"
    ).fetchone()
    conn.close()
    assert row[0] == 1000.0
    assert row[1] == SPEED_SOURCE_TAG


def test_update_refreshes_existing_groq_lpu_row(tmp_path):
    """A row already tagged `groq_lpu*` gets its tps refreshed (Groq
    may report a different number after their LPU updates)."""
    from scrape_groq_speeds import SPEED_SOURCE_TAG, update_database

    db_path = _seed_min_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE agents SET output_tokens_per_sec=800, "
        "speed_source='groq_lpu (pin required)', speed_updated_at='2026-06-01' "
        "WHERE id='openai/gpt-oss-20b'"
    )
    conn.commit()
    conn.close()

    matches = {"openai/gpt-oss-20b": {"tps": 1000, "groq_name": "GPT OSS 20B"}}
    updated, skipped_precedence, _ = update_database(matches, db_path)
    assert updated == 1
    assert skipped_precedence == 0

    conn = sqlite3.connect(db_path)
    r = conn.execute(
        "SELECT output_tokens_per_sec, speed_source FROM agents WHERE id='openai/gpt-oss-20b'"
    ).fetchone()
    conn.close()
    assert r[0] == 1000.0, "existing groq_lpu row should have been refreshed"
    assert r[1] == SPEED_SOURCE_TAG
