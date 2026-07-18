#!/usr/bin/env python3
# AFTER-EDIT: scripts/refresh_service_inventory.py
"""Behavior-Contract tests for the refresh orchestrator (Phase D) — the re-bill guard.

No network / DB: the subprocess + flagged_providers are mocked; only the seen-set + new-provider
detection (the guard that stops re-billing stuck unknowns) is exercised.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

rsi = importlib.import_module("refresh_service_inventory")


def test_seen_set_roundtrip_is_a_union(tmp_path, monkeypatch):
    """Given previously-seen providers, When _mark_seen adds more, Then the set is the union
    (so an already-attempted provider is never dropped → never re-classified)."""
    seen = tmp_path / "seen.json"
    monkeypatch.setattr(rsi, "SEEN", seen)
    rsi._mark_seen(["x", "y"])
    assert rsi._seen() == {"x", "y"}
    rsi._mark_seen(["y", "z"])
    assert rsi._seen() == {"x", "y", "z"}


def test_only_new_providers_are_targeted(tmp_path, monkeypatch, capsys):
    """Given flagged {a,b,c} and seen {a,b}, When run(dry) computes the target set, Then only the
    NEW provider c is targeted (a,b are skipped — the re-bill guard)."""
    seen = tmp_path / "seen.json"
    seen.write_text('["a", "b"]', encoding="utf-8")
    monkeypatch.setattr(rsi, "SEEN", seen)
    monkeypatch.setattr(rsi, "flagged_providers", lambda _p: {"a": {}, "b": {}, "c": {}})
    monkeypatch.setattr(rsi.subprocess, "run", lambda *a, **k: None)  # no real gather
    rc = rsi.run(dry=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 new" in out
    assert "'c'" in out
    assert "'a'" not in out and "'b'" not in out
