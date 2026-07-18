#!/usr/bin/env python3
# AFTER-EDIT: scripts/gather_envs.py scripts/classify_services.py
"""Behavior-Contract regression tests for the env consolidator + classifier (Phase A).

Guards the two bugs that slipped this build: the empty-value false-merge and the
idempotency-compare defect. Loads the scripts by path (scripts/ is not a package).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ge = _load("gather_envs")
cs = _load("classify_services")


def _envs(tmp_path: Path, projects: dict[str, str]) -> list[Path]:
    """projects: {project_name: env_file_text} -> list of the .env Paths."""
    files = []
    for proj, text in projects.items():
        d = tmp_path / proj
        d.mkdir()
        f = d / ".env"
        f.write_text(text, encoding="utf-8")
        files.append(f)
    return files


def test_empty_values_never_merge(tmp_path):
    """Given two projects with empty *_API_KEY/*_PASSWORD, When consolidated,
    Then the empty values are skipped and never fused into one entry (the 22-way bug)."""
    files = _envs(
        tmp_path,
        {
            "proj_a": "ANTHROPIC_API_KEY=\nDB_PASSWORD=\n",
            "proj_b": "OPENAI_API_KEY=\nSMTP_PASSWORD=\n",
        },
    )
    body, stats = ge.consolidate(files)
    assert stats["skipped_empty"] == 4
    # No secret line should carry another key as an alias (the false-merge signature).
    assert "aliases:" not in body
    assert "ANTHROPIC_API_KEY" not in body  # empty -> skipped entirely


def test_idempotent_body(tmp_path):
    """Given unchanged input, When consolidate runs twice, Then the body is byte-identical."""
    files = _envs(tmp_path, {"proj_a": "FOO_API_KEY=sk-realvalue-1234567890\nPORT=8000\n"})
    body1, _ = ge.consolidate(files)
    body2, _ = ge.consolidate(files)
    assert body1 == body2


def test_read_existing_body_roundtrip_the_real_idempotency_guard(tmp_path):
    """Given a written all-envs.env, When read_existing_body reads it back, Then it equals the
    freshly-generated body — the ACTUAL guard for the read_existing_body split bug that dropped the
    leading '# ' and made every cron run rewrite the file (consolidate() determinism alone missed it)."""
    files = _envs(tmp_path, {"proj_a": "FOO_API_KEY=sk-realvalue-1234567890\nPORT=8000\n"})
    body, _ = ge.consolidate(files)
    out = tmp_path / "all-envs.env"
    out.write_text("# AUTO-GENERATED\n# Generated: 2026-01-01\n#\n" + body + "\n", encoding="utf-8")
    # If the bug returned (split mid-line at the first ═), the '# ' prefix is dropped → not equal.
    assert ge.read_existing_body(out).rstrip() == body.rstrip()


def test_alias_merge_same_value_different_name(tmp_path):
    """Given the same secret under two different names, When consolidated,
    Then it collapses to one entry with the other name as an alias."""
    val = "sk-shared-abcdef1234567890"
    files = _envs(
        tmp_path,
        {"proj_a": f"OPENROUTER_API_KEY={val}\n", "proj_b": f"WATCHDOG_OPENROUTER_KEY={val}\n"},
    )
    body, _ = ge.consolidate(files)
    assert "aliases:" in body
    assert body.count(val) == 1  # one line, not two


def test_distinct_values_kept_separate(tmp_path):
    """Given the same key with two different values, When consolidated, Then both are kept."""
    files = _envs(
        tmp_path,
        {
            "proj_a": "SONIOX_API_KEY=aaaa1111bbbb2222cccc\n",
            "proj_b": "SONIOX_API_KEY=zzzz9999yyyy8888xxxx\n",
        },
    )
    body, _ = ge.consolidate(files)
    assert "aaaa1111bbbb2222cccc" in body
    assert "zzzz9999yyyy8888xxxx" in body


def test_catalog_fail_soft(tmp_path, monkeypatch):
    """Given a malformed service_catalog.json, When loaded, Then it degrades to empty, no crash."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(ge, "CATALOG_PATH", bad)
    catalog, matchers = ge.load_catalog()
    assert catalog == {}
    assert matchers == []


def test_classify_input_has_no_secret_values(tmp_path):
    """Given a flagged provider block, When flagged_providers parses it, Then only var NAMES
    (and public URL values) are collected — never a secret value (no leak to the pool)."""
    all_envs = tmp_path / "all-envs.env"
    bar = "═" * 20  # PRODUCTION uses Unicode ═, not ASCII = — the boundary check keys on "# ═"
    all_envs.write_text(
        f"# {bar} NEEDS-TRIAGE (category=?) {bar}\n"
        '#svc name=zari category=? cost=? capability="?" url=? status=?\n'
        "ZARI_API_KEY=super-secret-value-xyz   # used by: trade-intelligence\n"
        "ZARI_API_URL=https://api.zari.example/v1/sometoken   # used by: trade-intelligence\n"
        f"# {bar} internal-config (NOT a service) {bar}\n"
        "PORT=8000\n",
        encoding="utf-8",
    )
    provs = cs.flagged_providers(all_envs)
    assert "zari" in provs
    assert "ZARI_API_KEY" in provs["zari"]["names"]
    # The section boundary MUST be honored — the internal-config PORT is NOT captured under zari.
    assert "PORT" not in provs["zari"]["names"]
    blob = repr(provs["zari"])
    assert "super-secret-value-xyz" not in blob  # secret value never captured
    assert "sometoken" not in blob  # only scheme+host sent — the URL path token must NOT leak
    assert provs["zari"]["urls"] == ["https://api.zari.example"]
