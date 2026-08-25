"""check_vps_docs' exit code must follow its findings' SEVERITY.

WHY. Every `CheckResult` this module can construct is `Severity.WARN` — a missing doc, an
absent `Last Updated:` header, a stale date. Its entry point nevertheless exited 1 on ANY
finding, so a warning-level condition failed a BLOCKING Tier-3 gate row: the hub was red
because this check pointed at `docs/operations/` where `vps-status.md` / `vps-urls.md` never
lived — they are in `docs/infrastructure/`. A stale VPS doc is a refresh chore (`fabrik vps-sync`),
not a defect in the change under gate, and it is the
mirror image of the vacuous-green class — a row that reds on nothing rather than one that
greens on everything. Both teach an operator to stop reading the gate.

The contract asserted here is `_check_runner.run_as_main`'s, so the whole enforcement
corpus answers the same way: ERROR fails, WARN reports, `--strict` promotes.

The check reads the absolute literal `FABRIK_ROOT = Path("/opt/fabrik")` and so cannot be
pointed at a fixture (that is its `UNREACHABLE` entry in `liveness_audit.CANARIES`). These
tests therefore drive `main()` with the finding list substituted — which is exactly the
seam the bug lived in: the findings were always right, the exit code was not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "enforcement"))

import check_vps_docs as cvd  # noqa: E402 — the path insert must precede the import
from validate_conventions import CheckResult, Severity  # noqa: E402


def _finding(severity: Severity) -> CheckResult:
    return CheckResult(
        check_name="vps_doc_freshness",
        severity=severity,
        message=f"a {severity.name} condition",
        file_path="/opt/fabrik/docs/infrastructure/vps-status.md",
        fix_hint="Run `fabrik vps-sync` to regenerate VPS docs.",
    )


@pytest.fixture
def findings(monkeypatch: pytest.MonkeyPatch):
    """Substitute the finding list; the freshness logic itself is not under test here."""

    def _set(*severities: Severity) -> None:
        monkeypatch.setattr(
            cvd, "check_vps_doc_freshness", lambda *a, **k: [_finding(s) for s in severities]
        )

    return _set


def test_warn_findings_are_reported_and_do_not_fail(
    findings, capsys: pytest.CaptureFixture[str]
) -> None:
    """The live hub case: two missing ops docs must not red a blocking gate row."""
    findings(Severity.WARN, Severity.WARN)
    assert cvd.main([]) == 0
    out = capsys.readouterr().out
    assert "[WARN] a WARN condition" in out, "reporting is the entire product of a WARN"
    assert "0 error(s), 2 warning(s)" in out
    assert out.startswith("[WARN]") and "PASS: check_vps_docs" in out


def test_an_error_finding_still_fails(findings) -> None:
    """The teeth, kept. Softening WARN must not soften ERROR — that would be a downgrade
    wearing a bug-fix label, and this check's next real rule will be an ERROR."""
    findings(Severity.ERROR)
    assert cvd.main([]) == 1


def test_an_error_fails_even_beside_warns(findings) -> None:
    findings(Severity.WARN, Severity.ERROR, Severity.WARN)
    assert cvd.main([]) == 1


def test_strict_promotes_warns_to_failing(findings) -> None:
    """`--strict` is the documented activation switch, same as `_check_runner`'s."""
    findings(Severity.WARN)
    assert cvd.main(["--strict"]) == 1


def test_a_clean_run_passes_in_both_modes(findings, capsys: pytest.CaptureFixture[str]) -> None:
    findings()
    assert cvd.main([]) == 0
    assert cvd.main(["--strict"]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out, (
        "a green run must still print a verdict — silence is how a check that stopped "
        "running passes for one that found nothing"
    )


# --- the verdict must state its DENOMINATOR (enforcement-battery audit, 2026-08-25) -------------
# The clean-run test above already reasons that "silence is how a check that stopped running passes
# for one that found nothing" — but `0 error(s), 0 warning(s)` has the same defect one level up: it
# cannot distinguish "walked the tree and found nothing" from "walked nothing". Measured across all
# 59 checks in a subject-free repo: 17 emitted an affirmative success claim, 1 stated a denominator.
# This runner backs SEVEN checks (docker/health/ports/watchdog/vps_docs/env_contract/deps_sync), so
# the count lands in all of them at once. See docs/reference/enforcement-battery-audit.md.


def test_verdict_states_its_own_denominator(
    findings, capsys: pytest.CaptureFixture[str]
) -> None:
    """check_vps_docs does NOT walk the repo — its unit is the fixed VPS_DOCS list.

    Asserting the runner's "files walked" here would be a borrowed unit: this check never calls
    iter_repo_files, so a file count would be a number it did not earn. The rule is that a success
    line names ITS OWN denominator, not that every check reports the same one.
    """
    findings()
    assert cvd.main([]) == 0
    out = capsys.readouterr().out
    m = re.search(r"across (\d+) VPS doc\(s\)", out)
    assert m is not None, f"verdict carries no denominator: {out!r}"
    assert int(m.group(1)) == len(cvd.VPS_DOCS), "the count must be the real subject list, not a literal"
