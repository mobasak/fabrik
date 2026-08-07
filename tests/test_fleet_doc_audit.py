# AFTER-EDIT: scripts/fleet_doc_audit.py | none
"""Behavior contract for the fleet doc-freshness audit's pure probes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fleet_doc_audit as fda  # noqa: E402


def test_lag_days_code_leads_docs():
    assert fda.lag_days(100 * 86400, 79 * 86400) == 21


def test_lag_days_docs_current_or_newer_is_zero():
    assert fda.lag_days(100 * 86400, 100 * 86400) == 0
    assert fda.lag_days(100 * 86400, 200 * 86400) == 0


def test_lag_days_no_code_commits_is_zero():
    assert fda.lag_days(None, 50 * 86400) == 0


def test_stub_hits_counts_template_sentinels():
    text = "# [Project Name]\n\n**Last Updated:** YYYY-MM-DD\n\n- goal: [TBD — fill]\n- ok line\n"
    assert fda.stub_hits(text) == 3


def test_stub_hits_filled_doc_is_clean():
    text = "# seo\n\n**Last Updated:** 2026-08-07\n\n- goal: rank tracking\n"
    assert fda.stub_hits(text) == 0
