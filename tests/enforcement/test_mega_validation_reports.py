# AFTER-EDIT: scripts/enforcement/check_review_coverage.py
"""The mega validation-report grammar — every rule here was DEFEATED once before it was a test.

The first version of the grammar (commit e2bf0f6e) shipped with throwaway in-session fixtures and
no committed test; its own review (2026-08-18) then reproduced six distinct defeats: a quoted H1
routed ANY report away from the checklist gate, prose after the ledger table impersonated the
final round, a prose mention double-counted as round two, a fenced `Status: IN-PROGRESS` bought a
total exemption, `2026 -> 2026` (a year) passed as an "unmoved hash", and identical fabricated
strings satisfied an "anti-cheat" that never computed anything. Each test below pins one of those
defeats closed. Same subprocess harness as test_cert_dispositions.py: the REAL script against a
fixture git repo, so routing, the advisory scan and the live recompute are all exercised.
"""

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path("/opt/fabrik/scripts/enforcement/check_review_coverage.py")

sys.path.insert(0, str(CHECK.parent))
from check_review_coverage import epics_set_hash  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    epics = tmp_path / "docs/development/epics"
    epics.mkdir(parents=True)
    (epics / "2026-08-18-epic-1-alpha.md").write_text("# Epic 1\ncontent\n")
    (epics / "2026-08-18-epic-2-beta.md").write_text("# Epic 2\ncontent\n")
    return tmp_path


def _shell_hash(repo: Path) -> str:
    """The Step-3 anti-cheat pipeline VERBATIM — the value a real mega-04 run records."""
    out = subprocess.run(
        ["bash", "-c",
         "find docs/development/epics -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum"],
        cwd=repo, capture_output=True, text=True, timeout=15, check=True,
    ).stdout
    return out.split()[0]


def _gate(repo: Path, name: str, content: str, *, commit: bool = False) -> tuple[int, str]:
    (repo / "docs/development/reviews").mkdir(parents=True, exist_ok=True)
    (repo / f"docs/development/reviews/{name}").write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15, capture_output=True)
    if commit:
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
            cwd=repo, check=True, timeout=15, capture_output=True,
        )
    r = subprocess.run(
        [sys.executable, str(CHECK), "--root", str(repo)],
        capture_output=True, text=True, timeout=30,
    )
    return r.returncode, r.stdout + r.stderr


def _report(h: str, *, rounds: str | None = None, surface: str | None = None) -> str:
    rounds = rounds if rounds is not None else (
        f"| 1 | found: 7 | fixed: 6 | {'a' * 32} → {h} |\n"
        f"| 2 | found: 0 | fixed: 0 | {h} → {h} |\n"
    )
    return (
        "# Cross-Epic Validation Report\n"
        f"Surface: {surface if surface is not None else h}\n\n"
        "Rounds:\n"
        "| round | found: | fixed: | md5(start) → md5(end) |\n"
        "|---|---|---|---|\n"
        + rounds +
        "\n## Feature Coverage: PASS — 12 features across 2 epics\n"
        "## Overall: PASS · Fixups this run: 6 · Routed back: none\n"
    )


def test_python_hash_is_byte_identical_to_the_shell_pipeline(repo: Path) -> None:
    """If these ever diverge, every honest report fails the live recompute — the gate dies."""
    assert epics_set_hash(repo) == _shell_hash(repo)


def test_honest_report_with_real_hashes_passes(repo: Path) -> None:
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", _report(_shell_hash(repo)))
    assert rc == 0, out


def test_fabricated_identical_strings_no_longer_pass(repo: Path) -> None:
    """THE defeat: the v1 'anti-cheat' compared two typed strings. Now the live set must match."""
    fake = "d" * 32
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", _report(fake))
    assert rc == 1
    assert "epic set on disk hashes to" in out


def test_a_year_is_not_a_hash(repo: Path) -> None:
    h = _shell_hash(repo)
    rounds = f"| 1 | found: 1 | fixed: 1 | 2025 → 2026 |\n| 2 | found: 0 | fixed: 0 | 2026 → 2026 |\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md",
                    _report(h, rounds=rounds))
    assert rc == 1
    assert "no full `md5(start)" in out or "≥12 hex" in out


def test_prose_after_the_table_cannot_impersonate_the_final_round(repo: Path) -> None:
    """v1 took the LAST match in the file; a quoted contract sentence defeated both proofs."""
    h = _shell_hash(repo)
    bad_rounds = f"| 1 | found: 4 | fixed: 1 | {'b' * 32} → {'c' * 32} |\n"
    body = _report(h, rounds=bad_rounds) + (
        f"\nPolicy: the exit round is found: 0, fixed: 0 with {h} → {h}.\n"
    )
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", body)
    assert rc == 1
    assert "found: 4" in out


def test_a_prose_mention_is_not_a_second_round(repo: Path) -> None:
    h = _shell_hash(repo)
    one = f"| 1 | found: 0 | fixed: 0 | {h} → {h} |\n"
    body = _report(h, rounds=one) + f"\nSummary: round 1 closed found: 0, fixed: 0, {h} → {h}.\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", body)
    assert rc == 1
    assert "minimum two" in out


def test_final_round_must_be_quiet_in_BOTH_counters(repo: Path) -> None:
    h = _shell_hash(repo)
    rounds = f"| 1 | found: 3 | fixed: 2 | {'a' * 32} → {h} |\n| 2 | found: 0 | fixed: 3 | {h} → {h} |\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", _report(h, rounds=rounds))
    assert rc == 1
    assert "fixed: 3" in out


def test_broken_hash_chain_is_flagged(repo: Path) -> None:
    h = _shell_hash(repo)
    rounds = f"| 1 | found: 2 | fixed: 2 | {'a' * 32} → {'b' * 32} |\n| 2 | found: 0 | fixed: 0 | {h} → {h} |\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", _report(h, rounds=rounds))
    assert rc == 1
    assert "BETWEEN reviewed rounds" in out


def test_surface_must_equal_the_final_rounds_end_hash(repo: Path) -> None:
    h = _shell_hash(repo)
    other = "e" * 32
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md",
                    _report(h, surface=other))
    assert rc == 1
    assert "does not equal the final round" in out or "epic set on disk" in out


def test_quoting_the_template_does_not_reroute_a_normal_review(repo: Path) -> None:
    """v1's worst defeat: a fenced quote of the H1 skipped the checklist gate entirely."""
    body = (
        "# Review — some diff (/fabrik-review)\n"
        "Surface: abc123\n\n"
        "## Coverage Checklist\n"
        "| Class | Verdict | Evidence |\n|---|---|---|\n| fail-open | UNCHECKED | |\n\n"
        "```markdown\n# Cross-Epic Validation Report\n```\n"
    )
    rc, out = _gate(repo, "2026-08-18-quoting-review.md", body)
    assert rc == 1, "the checklist gate must still fire — the quote must not reroute"
    assert "UNCHECKED" in out


def test_fenced_in_progress_is_not_an_exemption_but_header_zone_is(repo: Path) -> None:
    h = _shell_hash(repo)
    fenced = _report("f" * 32) + "\n```\nStatus: IN-PROGRESS\n```\n"
    rc, _ = _gate(repo, "2026-08-18-mega-vision-validation-review.md", fenced)
    assert rc == 1, "a fenced quote of the escape hatch bought a total exemption in v1"
    header = "# Cross-Epic Validation Report\nStatus: IN-PROGRESS\n\n(partial run)\n"
    rc2, out2 = _gate(repo, "2026-08-18-mega-vision-validation-review.md", header)
    assert rc2 == 0, out2


def test_placeholders_flagged_outside_fences_only(repo: Path) -> None:
    h = _shell_hash(repo)
    with_fence = _report(h) + "\n```markdown\n## Coverage: [PASS] — [N] features\n```\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", with_fence)
    assert rc == 0, out
    naked = _report(h).replace("PASS — 12 features", "[PASS] — [N] features")
    rc2, out2 = _gate(repo, "2026-08-18-mega-vision-validation-review.md", naked)
    assert rc2 == 1
    assert "placeholder" in out2


def test_committed_unconverged_mega_report_surfaces_in_the_advisory_scan(repo: Path) -> None:
    """v1 reopened green-by-absence: committed mega reports were invisible to the scan."""
    h = _shell_hash(repo)
    bad = _report(h, rounds=f"| 1 | found: 4 | fixed: 1 | {'b' * 32} → {h} |\n")
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", bad, commit=True)
    assert "COMMITTED mega report" in out, "the advisory scan must name the committed report"
    assert rc == 0, "advisory, never blocking — retro-grading history is how a gate gets muted"
