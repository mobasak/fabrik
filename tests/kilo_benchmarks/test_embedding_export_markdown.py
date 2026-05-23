"""Tests for `embedding_export_markdown.py`.

Runs the generator against the live DB and asserts that both files
exist with the expected sections, today's winners table, and per-row
metadata. No mocks — relies on the daily pipeline having populated
`embedding_models` + `embedding_roles`.
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
SELECTION_GUIDE_PATH = DOCS_DIR / "KILO_EMBEDDING_SELECTION_GUIDE.md"
CAPABILITIES_PATH = DOCS_DIR / "KILO_EMBEDDING_CAPABILITIES.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


embedding_export_markdown = _load("embedding_export_markdown")
embedding_role_mapper = _load("embedding_role_mapper")


@pytest.fixture(scope="module", autouse=True)
def _seed():
    """Make sure embedding_roles is populated before generating markdown."""
    if not DB_PATH.exists():
        pytest.skip("kilo_agents.db missing — run embedding_models_db.py first")
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_roles'"
        )
        if cur.fetchone() is None:
            pytest.skip("embedding_roles table missing — run embedding_role_mapper.py first")
    finally:
        conn.close()
    embedding_role_mapper.run()
    embedding_export_markdown.run()


def test_selection_guide_file_exists():
    assert SELECTION_GUIDE_PATH.exists(), (
        f"selection guide not generated at {SELECTION_GUIDE_PATH}"
    )
    body = SELECTION_GUIDE_PATH.read_text()
    assert body.startswith("# Kilo Embedding Selection Guide")
    assert "## Today's Winners" in body
    assert "## Selection Philosophy" in body
    assert "## How to override" in body


def test_capabilities_file_exists():
    assert CAPABILITIES_PATH.exists(), (
        f"capabilities file not generated at {CAPABILITIES_PATH}"
    )
    body = CAPABILITIES_PATH.read_text()
    assert body.startswith("# Kilo Embedding Model Capabilities")
    assert "## All embedding models" in body
    assert "## Legend" in body


def test_selection_guide_lists_every_role():
    """Every role from embedding_role_configs.yaml must appear as an `### ` section."""
    body = SELECTION_GUIDE_PATH.read_text()
    import yaml as _yaml

    cfg = _yaml.safe_load(
        (SCRIPT_DIR / "embedding_role_configs.yaml").read_text()
    )["roles"]
    for role in cfg.keys():
        assert f"### {role}" in body, f"missing role section for {role!r}"


def test_selection_guide_contains_db_winners():
    """Every `embedding_roles.model_id` appears in the rendered markdown."""
    conn = sqlite3.connect(DB_PATH)
    try:
        winners = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT model_id FROM embedding_roles"
            ).fetchall()
        ]
    finally:
        conn.close()
    assert winners, "embedding_roles must be populated for this test"
    body = SELECTION_GUIDE_PATH.read_text()
    for model_id in winners:
        assert model_id in body, f"winner {model_id!r} not found in selection guide"


def test_capabilities_lists_every_catalog_row():
    """Every row in embedding_models appears in the capabilities table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM embedding_models ORDER BY id"
            ).fetchall()
        ]
    finally:
        conn.close()
    body = CAPABILITIES_PATH.read_text()
    missing = [i for i in ids if i not in body]
    assert not missing, f"missing model ids in capabilities file: {missing[:5]}..."


def test_capabilities_renders_total_count():
    """`Total models:` line matches the actual row count."""
    conn = sqlite3.connect(DB_PATH)
    try:
        n = conn.execute("SELECT COUNT(*) FROM embedding_models").fetchone()[0]
    finally:
        conn.close()
    body = CAPABILITIES_PATH.read_text()
    assert f"**Total models:** {n}" in body


def test_run_returns_paths_and_overwrites_idempotently():
    """Calling run() twice must not append/duplicate content."""
    paths1 = embedding_export_markdown.run()
    body1 = SELECTION_GUIDE_PATH.read_text()
    paths2 = embedding_export_markdown.run()
    body2 = SELECTION_GUIDE_PATH.read_text()
    assert paths1 == paths2
    assert body1 == body2, "second run produced different output (non-deterministic?)"


def test_qwen3_embedding_8b_p1_visible_in_guide():
    """Acceptance: the multilingual_primary P1 winner is rendered in the guide."""
    body = SELECTION_GUIDE_PATH.read_text()
    assert "qwen/qwen3-embedding-8b" in body
    # Must be in the multilingual_primary section, not just the philosophy text.
    multi_start = body.index("### multilingual_primary")
    next_section = body.find("\n### ", multi_start + 1)
    if next_section == -1:
        next_section = len(body)
    multi_section = body[multi_start:next_section]
    assert "| P1 |" in multi_section
    assert "qwen/qwen3-embedding-8b" in multi_section
