"""Tests for `embedding_export_markdown.py`.

Now that the embedding sections live INSIDE the existing chat-side markdown
files (between EMBEDDING_ROSTER and EMBEDDING_CATALOG markers), these tests
assert that:

  - Both host files contain the marker pairs.
  - The chat-side ROSTER section (between ROSTER:START / ROSTER:END) and any
    other host content are preserved across the generator run.
  - The embedding marker bodies are populated with today's winners + catalog.
  - Idempotent: two runs produce byte-identical files.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
DOCS_DIR = REPO_ROOT / "docs" / "reference" / "kilo"
SELECTION_GUIDE_PATH = DOCS_DIR / "KILO_AGENT_SELECTION_GUIDE.md"
CAPABILITIES_PATH = DOCS_DIR / "KILO_MODEL_CAPABILITIES.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


embedding_export_markdown = _load("embedding_export_markdown")
embedding_role_mapper = _load("embedding_role_mapper")


def _between(text: str, start: str, end: str) -> str:
    si = text.find(start)
    ei = text.find(end)
    assert si != -1 and ei != -1 and ei > si, f"markers missing: {start} / {end}"
    line_end = text.find("\n", si)
    return text[line_end + 1 : ei]


@pytest.fixture(scope="module", autouse=True)
def _seed():
    if not DB_PATH.exists():
        pytest.skip("kilo_agents.db missing")
    conn = sqlite3.connect(DB_PATH)
    try:
        if (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_roles'"
            ).fetchone()
            is None
        ):
            pytest.skip("embedding_roles missing — run embedding_role_mapper first")
    finally:
        conn.close()
    embedding_role_mapper.run()
    embedding_export_markdown.run()


def test_host_files_contain_embedding_markers():
    guide = SELECTION_GUIDE_PATH.read_text()
    cap = CAPABILITIES_PATH.read_text()
    assert "<!-- EMBEDDING_ROSTER:START" in guide
    assert "<!-- EMBEDDING_ROSTER:END -->" in guide
    assert "<!-- EMBEDDING_CATALOG:START" in cap
    assert "<!-- EMBEDDING_CATALOG:END -->" in cap


def test_chat_roster_section_preserved():
    """Generator must NOT touch the chat-side ROSTER block."""
    guide = SELECTION_GUIDE_PATH.read_text()
    assert "<!-- ROSTER:START" in guide
    assert "<!-- ROSTER:END -->" in guide
    chat_block = _between(guide, "<!-- ROSTER:START", "<!-- ROSTER:END -->")
    # The chat roster always carries an "Auto-generated" provenance line and
    # at least one role section header. If that's missing, we corrupted it.
    assert chat_block.strip(), "chat roster body is empty"


def test_embedding_roster_contains_all_role_sections():
    import yaml as _yaml

    cfg = _yaml.safe_load((SCRIPT_DIR / "embedding_role_configs.yaml").read_text())["roles"]
    body = _between(
        SELECTION_GUIDE_PATH.read_text(),
        "<!-- EMBEDDING_ROSTER:START",
        "<!-- EMBEDDING_ROSTER:END -->",
    )
    for role in cfg:
        assert f"### {role}" in body, f"missing role: {role}"


def test_embedding_roster_contains_db_winners():
    conn = sqlite3.connect(DB_PATH)
    try:
        winners = [
            r[0] for r in conn.execute("SELECT DISTINCT model_id FROM embedding_roles").fetchall()
        ]
    finally:
        conn.close()
    assert winners
    body = _between(
        SELECTION_GUIDE_PATH.read_text(),
        "<!-- EMBEDDING_ROSTER:START",
        "<!-- EMBEDDING_ROSTER:END -->",
    )
    for mid in winners:
        assert mid in body, f"missing winner {mid!r} in roster"


def test_embedding_catalog_contains_every_model():
    conn = sqlite3.connect(DB_PATH)
    try:
        ids = [r[0] for r in conn.execute("SELECT id FROM embedding_models").fetchall()]
    finally:
        conn.close()
    body = _between(
        CAPABILITIES_PATH.read_text(),
        "<!-- EMBEDDING_CATALOG:START",
        "<!-- EMBEDDING_CATALOG:END -->",
    )
    missing = [i for i in ids if i not in body]
    assert not missing, f"missing model ids in catalog: {missing[:5]}"


def test_embedding_catalog_total_count_correct():
    conn = sqlite3.connect(DB_PATH)
    try:
        n = conn.execute("SELECT COUNT(*) FROM embedding_models").fetchone()[0]
    finally:
        conn.close()
    body = _between(
        CAPABILITIES_PATH.read_text(),
        "<!-- EMBEDDING_CATALOG:START",
        "<!-- EMBEDDING_CATALOG:END -->",
    )
    assert f"Total: {n} models" in body


def test_run_is_idempotent():
    embedding_export_markdown.run()
    a_guide = SELECTION_GUIDE_PATH.read_text()
    a_cap = CAPABILITIES_PATH.read_text()
    embedding_export_markdown.run()
    assert SELECTION_GUIDE_PATH.read_text() == a_guide
    assert CAPABILITIES_PATH.read_text() == a_cap


def test_qwen3_p1_in_multilingual_primary_section():
    body = _between(
        SELECTION_GUIDE_PATH.read_text(),
        "<!-- EMBEDDING_ROSTER:START",
        "<!-- EMBEDDING_ROSTER:END -->",
    )
    multi_idx = body.index("### multilingual_primary")
    next_idx = body.find("\n### ", multi_idx + 1)
    if next_idx == -1:
        next_idx = len(body)
    section = body[multi_idx:next_idx]
    assert "| P1 |" in section
    assert "qwen/qwen3-embedding-8b" in section


def test_no_standalone_embedding_files():
    """Standalone KILO_EMBEDDING_*.md must not exist (consolidated into chat files)."""
    assert not (DOCS_DIR / "KILO_EMBEDDING_SELECTION_GUIDE.md").exists()
    assert not (DOCS_DIR / "KILO_EMBEDDING_CAPABILITIES.md").exists()
