"""Tests for scripts/kilo-benchmarks/audit_pipeline.py — Phase A helpers of
the Model-Discovery Pipeline Audit (docs/development/plans/2026-07-08-plan-3-model-pipeline-audit.md).

Highest-risk path: the phase-A findings-MD builder. If it silently drops a
subagent's row, the whole pipeline's audit coverage is under-reported.
"""

from __future__ import annotations

import sys
from pathlib import Path

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


def test_verify_tier_split_flags_out_price_gt_ceiling_in_code_section(tmp_path):
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
        {
            "script": "x",
            "ran": "yes",
            "dry-run": "yes",
            "writes-tagged": "yes",
            "fail-soft": "yes",
            "severity": "STYLE",
            "summary": "ok",
            "fix-commit": "—",
        },
    ]
    out = tmp_path / "phase-a-ingestor-findings.md"
    _render_findings_md("A", rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Phase A"), f"header missing; got: {text[:100]!r}"
    assert "| x |" in text, "row not rendered"


def test_render_findings_md_escapes_pipe_in_summary(tmp_path):
    """Pass-1 review Finding 10 regression: a `|` in a cell value must be
    escaped so it doesn't create a false extra column that the loader would
    then drop as len(cells) != len(header).
    """
    from audit_pipeline import _load_findings_generic, _render_findings_md

    rows = [
        {"script": "x", "severity": "CONFIRMED", "summary": "regex `a|b` broke", "fix-commit": "—"},
    ]
    out = tmp_path / "phase-x-findings.md"
    _render_findings_md("X", rows, out)
    # Round-trip: what we wrote must be readable back with the same row shape.
    loaded = _load_findings_generic(out)
    assert len(loaded) == 1, f"pipe-in-cell dropped the row; got {loaded}"
    assert "regex" in loaded[0]["summary"], f"summary lost: {loaded[0]}"


def test_render_findings_md_preserves_heterogeneous_row_columns(tmp_path):
    """Pass-1 review Finding 5 regression: rows with different key sets must
    all render fully. Using rows[0].keys() as headers silently drops columns
    that only later rows carry.
    """
    from audit_pipeline import _render_findings_md

    rows = [
        {"script": "a", "severity": "STYLE", "summary": "ok"},
        {"script": "b", "severity": "PLAUSIBLE", "summary": "note", "extra-field": "important"},
    ]
    out = tmp_path / "phase-x-findings.md"
    _render_findings_md("X", rows, out)
    text = out.read_text(encoding="utf-8")
    assert "extra-field" in text, "later-row column dropped from header"
    assert "important" in text, "later-row value dropped"


def test_dispatch_pool_audit_fails_soft_when_libs_subagents_missing(tmp_path, monkeypatch):
    """Pass-1 review Finding 13 regression: guarded import failure returns []
    instead of raising, so callers can fall back to the inline scan.
    """
    # Simulate the ImportError path by stashing sys.modules['libs.subagents']
    # and reloading audit_pipeline's inner import. Simpler: shadow the module
    # at import time by monkeypatching sys.modules to a broken shim.
    import sys as _sys

    import audit_pipeline

    monkeypatch.setitem(_sys.modules, "libs.subagents", None)
    # sys.modules[key]=None causes `from libs.subagents import X` to raise
    # ImportError — which the function's try/except should swallow.
    result = audit_pipeline._dispatch_pool_audit([tmp_path / "dummy.py"], task="x")
    assert result == [], f"expected [] on import failure, got {result}"


def test_render_consolidated_report_aggregates_two_phase_d_mds(tmp_path):
    """Pass-1 review Finding 14 regression: consolidator must aggregate BOTH
    phase-d-emitter-findings.md and phase-d-browser-findings.md into ONE
    counter row for phase D (not overwrite the first with the second).
    """
    from audit_pipeline import _render_consolidated_report, _render_findings_md

    _render_findings_md(
        "D",
        [{"artifact": "doc-1", "severity": "STYLE", "summary": "ok"}],
        tmp_path / "phase-d-emitter-findings.md",
    )
    _render_findings_md(
        "D",
        [
            {"tab": "tab-1", "severity": "STYLE", "summary": "ok"},
            {"tab": "tab-2", "severity": "PLAUSIBLE", "summary": "note"},
        ],
        tmp_path / "phase-d-browser-findings.md",
    )
    out = tmp_path / "consolidated.md"
    _render_consolidated_report(
        [tmp_path / "phase-d-emitter-findings.md", tmp_path / "phase-d-browser-findings.md"],
        out,
    )
    text = out.read_text(encoding="utf-8")
    # Phase D row must reflect BOTH files: 1 (emitter STYLE) + 1 (browser STYLE) = 2 STYLE,
    # plus 1 PLAUSIBLE from browser. If the pre-Finding-14 bug regressed, we'd see 2 STYLE + 1 PLAUSIBLE
    # from only the second file's read.
    assert "| D | 0 | 1 | 2 | 0 |" in text, (
        f"phase D aggregation wrong; expected 2 STYLE + 1 PLAUSIBLE, got:\n{text}"
    )
