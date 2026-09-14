"""The gate's tier composition, asserted by INSTRUMENTED EXECUTION against the doc's own numbers.

T12.8 (01M23CRZZ). `docs/workflows/FINAL_GATE_WORKFLOW.md` is hand-maintained beside a registry
that changes weekly, and the mail measured five drifts between them. Three were closed by the
2026-09-11 docs review; the counts drifted again within three days — by this very phase's own
additions — which is the argument for a check rather than another careful re-read.

The doc carries ONE machine-readable declaration (`<!-- GATE-COUNTS: … -->`) and its prose cites
those numbers. This test is the other half: it runs `run_consistency_checks` at each tier with the
check runners stubbed, counts the results list, and compares. Same one-declaration shape as
`# AFTER-EDIT:` → `## Related scripts`.

⚠️ It counts the RESULTS LIST, not `run_optional_check` CALLS — several rows are appended directly
and a call-counting probe answers lower (the doc says so too, and that gap is what made the earlier
hand counts disagree with each other).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "workflows" / "FINAL_GATE_WORKFLOW.md"
GATE = ROOT / "scripts" / "final_gate.py"

_DECL = re.compile(
    r"<!--\s*GATE-COUNTS:\s*tier1=(\d+)\s+tier2=(\d+)\s+tier3=(\d+)\s+every-tier=(\d+)\s*-->"
)


def _gate():
    spec = importlib.util.spec_from_file_location("fg_tier_counts", GATE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def _rows(mod, tier: int) -> list[str]:
    """Every row `run_consistency_checks` BUILDS at this tier, with the runners stubbed."""
    with (
        mock.patch.object(mod, "run_optional_check", lambda sp, cn, *a, **k: (cn, True, "")),
        mock.patch.object(mod, "run_cmd", lambda cmd, cwd=None, timeout=None: (0, "")),
    ):
        return [n for n, _ok, _out in mod.run_consistency_checks(tier=tier, changed_files=set())]


@pytest.fixture(scope="module")
def measured() -> dict[str, int]:
    mod = _gate()
    t1, t2, t3 = _rows(mod, 1), _rows(mod, 2), _rows(mod, 3)
    every = set(t1) & set(t2) & set(t3)
    return {"tier1": len(t1), "tier2": len(t2), "tier3": len(t3), "every-tier": len(every)}


def test_the_doc_declares_the_tier_counts_once_and_machine_readably() -> None:
    text = DOC.read_text(encoding="utf-8")
    found = _DECL.findall(text)
    assert len(found) == 1, (
        f"expected exactly one GATE-COUNTS declaration in {DOC.name}, found {len(found)} — "
        "two declarations are two things to drift, which is the defect this closes"
    )


def test_the_declared_tier_counts_match_instrumented_execution(measured: dict[str, int]) -> None:
    """The check the mail asked for. A new registration that does not update the declaration fails
    HERE, in the author's own gate run, instead of being measured by hand months later."""
    m = _DECL.search(DOC.read_text(encoding="utf-8"))
    assert m, "no GATE-COUNTS declaration"
    declared = {
        "tier1": int(m.group(1)),
        "tier2": int(m.group(2)),
        "tier3": int(m.group(3)),
        "every-tier": int(m.group(4)),
    }
    assert declared == measured, (
        f"{DOC.name} declares {declared} but the gate builds {measured}. Update the "
        "`<!-- GATE-COUNTS: … -->` line and any prose citing those numbers."
    )


def test_tier3_names_only_checks_that_are_actually_wired(measured: dict[str, int]) -> None:
    """Drift 2 of the mail, and the worse half of it: `check_ports`, `check_deps_sync` and
    `check_watchdog` are UNWIRED — `final_gate.py` says so in its own comments — yet the Tier-3
    description advertised ports, deps and watchdog as things `--systemic` checks. An agent reading
    it to answer "is X enforced?" got a wrong answer in the dangerous direction."""
    mod = _gate()
    tier3 = set(_rows(mod, 3))
    gate_src = GATE.read_text(encoding="utf-8")
    for script, advertised in (
        ("check_ports.py", "ports"),
        ("check_deps_sync.py", "deps"),
        ("check_watchdog.py", "watchdog"),
    ):
        assert f"# UNWIRED — {script}" in gate_src, (
            f"{script} is no longer marked UNWIRED — re-derive this test and the docs"
        )
        assert not any(advertised in row.lower() for row in tier3), (
            f"{script} is UNWIRED but a tier-3 row mentions {advertised!r}"
        )
    doc = DOC.read_text(encoding="utf-8")
    tier3_lines = [ln for ln in doc.splitlines() if "Tier 3" in ln or "--systemic" in ln]
    for ln in tier3_lines:
        for word in ("ports", "deps", "watchdog"):
            if re.search(rf"\b{word}\b", ln) and "UNWIRED" not in ln and "not wired" not in ln:
                pytest.fail(
                    f"a Tier-3 line advertises {word!r} while {word} is unwired:\n  {ln.strip()}"
                )


def test_the_sync_step_table_names_no_script_the_gate_never_runs() -> None:
    """Drift 1 of the mail, still live at the time of this fix: the § Phase 4 Sync Steps table
    named `sync_extensions.sh` and `sync_cascade_backup.sh`. `run_sync_steps` runs no `.sh` at
    all — it is the auto-stage step."""
    gate_src = GATE.read_text(encoding="utf-8")
    start = gate_src.index("def run_sync_steps")
    body = gate_src[start : start + 3000].split("\ndef ")[0]
    assert ".sh" not in body, "run_sync_steps now runs a shell script — re-derive the doc table"
    doc = DOC.read_text(encoding="utf-8")
    for script in ("sync_extensions.sh", "sync_cascade_backup.sh"):
        assert script not in doc, f"{DOC.name} still names {script}, which the gate never runs"


if __name__ == "__main__":  # pragma: no cover - convenience
    sys.exit(pytest.main([__file__, "-q"]))
