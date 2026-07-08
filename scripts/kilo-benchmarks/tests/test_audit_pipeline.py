"""Tests for scripts/kilo-benchmarks/audit_pipeline.py — Phase A helpers of
the Model-Discovery Pipeline Audit (docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md).

Highest-risk path: the phase-A findings-MD builder. If it silently drops a
subagent's row, the whole pipeline's audit coverage is under-reported.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_load_ingestor_findings_preserves_every_row(tmp_path):
    md = tmp_path / "phase-a-ingestor-findings.md"
    md.write_text(
        "Generated: 2026-07-08\n\n"
        "| script | ran | dry-run | writes-tagged | fail-soft | severity | summary | fix-commit |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| verify_openrouter_catalog | yes | yes | yes | yes | STYLE | note-only | — |\n"
        "| scrape_groq_speeds | yes | partial | yes | yes | CONFIRMED | HTTP timeout unhandled | pending |\n"
        "| microbench_or_models | no | yes | n/a | yes | ESCALATE | needs its own plan | — |\n",
        encoding="utf-8",
    )
    from audit_pipeline import _load_ingestor_findings

    rows = _load_ingestor_findings(md)
    assert len(rows) == 3, f"expected 3 rows, got {len(rows)}"
    assert rows[0]["script"] == "verify_openrouter_catalog"
    assert rows[1]["severity"] == "CONFIRMED"
    assert rows[2]["severity"] == "ESCALATE"


def test_load_findings_generic_accepts_variable_columns(tmp_path):
    """Phase B/C/D/E findings MDs have different column sets;
    _load_findings_generic must handle each without loss."""
    md = tmp_path / "phase-c-aggregator-findings.md"
    md.write_text(
        "Generated: 2026-07-08\n\n"
        "| ranker | tier-contract | pareto-correct | header-contract | row-count-sane | severity | summary | fix-commit |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| rank_coding_subagents | ok | ok | ok | ok | STYLE | tier split clean | — |\n",
        encoding="utf-8",
    )
    from audit_pipeline import _load_findings_generic

    rows = _load_findings_generic(md)
    assert len(rows) == 1
    assert rows[0]["ranker"] == "rank_coding_subagents"
    assert rows[0]["severity"] == "STYLE"


def test_verify_tier_split_flags_out_M_gt_ceiling_in_code_section(tmp_path):
    md = tmp_path / "CODING.md"
    md.write_text(
        "# Coding subagent selection\n\n"
        "## Ranked table\n\n"
        "### code\n\n"
        "| # | Model | OR | OR_prov | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score |\n"
        "|---:|---|:-:|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|\n"
        "| 1 | `deepseek/deepseek-v4-flash` | ✅ | X | 100 | 0.100 | 0.180 | — | — | 40 | 1460 | 1000k | **A** | 0.500 |\n"
        "| 2 | `z-ai/glm-5` | ✅ | X | 68 | 0.600 | 1.920 | 72.8 | — | — | 1461 | 200k | **B+** | 0.571 |\n"
        "\n### code-onrequest\n\n"
        "| # | Model | OR | OR_prov | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score |\n"
        "|---:|---|:-:|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|\n"
        "| 1 | `moonshotai/kimi-k2.7-code` | ✅ | X | 51 | 0.740 | 3.500 | — | — | 42 | — | 262k | **B** | 0.278 |\n"
        "| 2 | `deepseek/deepseek-v3.2` | ✅ | X | 63 | 0.229 | 0.343 | 70.0 | 70.2 | — | 1431 | 128k | **B** | 0.551 |\n",
        encoding="utf-8",
    )
    from audit_pipeline import _verify_tier_split

    auto_violations, onreq_violations = _verify_tier_split(md)
    # glm-5 has Out $/M = 1.920 (> 1.5) but sits in `### code` → 1 violation.
    assert auto_violations == 1, f"expected 1 auto violation, got {auto_violations}"
    # deepseek-v3.2 has Out $/M = 0.343 (≤ 1.5) but sits in `### code-onrequest` → 1 violation.
    assert onreq_violations == 1, f"expected 1 on-request violation, got {onreq_violations}"


def test_render_findings_md_emits_phase_header(tmp_path):
    from audit_pipeline import _render_findings_md

    rows = [
        {"script": "x", "ran": "yes", "dry-run": "yes", "writes-tagged": "yes",
         "fail-soft": "yes", "severity": "STYLE", "summary": "ok", "fix-commit": "—"},
    ]
    out = tmp_path / "phase-a-ingestor-findings.md"
    _render_findings_md("A", rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Phase A"), f"header missing; got: {text[:100]!r}"
    assert "| x |" in text, "row not rendered"
