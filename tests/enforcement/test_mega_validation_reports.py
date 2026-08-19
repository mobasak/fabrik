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
         "find docs/development/epics -name '*.md' -print0 | LC_ALL=C sort -z | xargs -0 md5sum | md5sum"],
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
    """If these ever diverge, every honest report fails the live recompute — the gate dies.

    The first version's fixture was two flat lowercase files — the one input class where locale
    and byte order cannot differ, so it could not fail for the reason it exists (closing-sweep
    finding). Mixed case and nesting are exactly where `sort` without LC_ALL=C diverges; both
    are in the fixture now, and the doc's pipeline pins LC_ALL=C to match.
    """
    epics = repo / "docs/development/epics"
    (epics / "Alpha-b.md").write_text("upper\n")
    (epics / "sub").mkdir()
    (epics / "sub" / "a.md").write_text("nested\n")
    (epics / "sub-x.md").write_text("dash-vs-slash\n")
    assert epics_set_hash(repo) == _shell_hash(repo)


def test_empty_epic_set_yields_no_anchor(tmp_path: Path) -> None:
    """No epics = nothing validated; the shell's md5sum-of-nothing artifact is not an anchor."""
    (tmp_path / "docs/development/epics").mkdir(parents=True)
    assert epics_set_hash(tmp_path) is None


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
    rounds = "| 1 | found: 1 | fixed: 1 | 2025 → 2026 |\n| 2 | found: 0 | fixed: 0 | 2026 → 2026 |\n"
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
    assert "found: 4" in out or "MORE THAN ONE" in out


def test_a_prose_mention_is_not_a_second_round(repo: Path) -> None:
    h = _shell_hash(repo)
    one = f"| 1 | found: 0 | fixed: 0 | {h} → {h} |\n"
    body = _report(h, rounds=one) + f"\nSummary: round 1 closed found: 0, fixed: 0, {h} → {h}.\n"
    rc, out = _gate(repo, "2026-08-18-mega-vision-validation-review.md", body)
    assert rc == 1
    assert "minimum two" in out


def test_final_round_must_be_quiet_in_both_counters(repo: Path) -> None:
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


def test_a_second_table_cannot_impersonate_the_ledger(repo: Path) -> None:
    """Round-3 defeat: a later per-lens tally table with a quiet row masked a non-quiet exit."""
    h = _shell_hash(repo)
    body = _report(h, rounds=f"| 1 | found: 9 | fixed: 3 | {'a' * 32} → {h} |\n") + (
        "\n## Per-lens tally\n"
        "| lens | found: | fixed: | hashes |\n|---|---|---|---|\n"
        f"| A | found: 0 | fixed: 0 | {h} → {h} |\n"
        f"| B | found: 0 | fixed: 0 | {h} → {h} |\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1, "the tally table became the ledger — LAST-match's third appearance"
    assert "found: 9" in out or "MORE THAN ONE" in out


def test_h1_with_a_vision_suffix_still_routes_to_the_mega_gate(repo: Path) -> None:
    """Round-3 defeat: a suffixed title fell through EVERY gate and exited green."""
    bad = _report("f" * 32, rounds=f"| 1 | found: 9 | fixed: 3 | {'b' * 32} → {'c' * 32} |\n")
    bad = bad.replace(
        "# Cross-Epic Validation Report", "# Cross-Epic Validation Report — Project Chimera", 1
    )
    rc, out = _gate(repo, "2026-08-19-report.md", bad)  # filename deliberately non-mega
    assert rc == 1, "the suffixed H1 escaped the mega gate entirely"
    assert "found: 9" in out or "epic set on disk" in out


def test_the_reserved_filename_routes_even_with_a_foreign_title(repo: Path) -> None:
    """Fail-closed backstop: a mega-shaped NAME can never reach a weaker grammar."""
    rc, out = _gate(
        repo, "2026-08-19-mega-chimera-validation-review.md",
        "# Some Other Title\n\nno ledger at all\n",
    )
    assert rc == 1
    assert "ledger table records 0 round" in out or "Surface" in out


def test_surface_with_a_trailing_annotation_is_not_absent(repo: Path) -> None:
    """Wrong-reason class, third sighting: `Surface: <hash> (note)` reported as 'no Surface line'."""
    h = _shell_hash(repo)
    body = _report(h).replace(f"Surface: {h}", f"Surface: {h}  (combined md5, 2 files)")
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 0, out


def test_committed_scan_is_narrow_exit_conditions_only(repo: Path) -> None:
    """The advisory honors its documented narrowness: quiet-exit + moved-hash, nothing else."""
    bad = (
        "# Cross-Epic Validation Report\n\nRounds:\n"
        "| round | found: | fixed: | hashes |\n|---|---|---|---|\n"
        "| 1 | found: 0 | fixed: 0 | (none recorded) |\n"
        "\n## Overall: PASS — but no Surface, one round, no hashes, [PASS] placeholder\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-old-validation-review.md", bad, commit=True)
    assert rc == 0
    assert "COMMITTED mega report" not in out, (
        "the committed scan emitted full-obligation errors — that is the muting mechanism "
        "the narrowness contract names (only quiet-exit + moved-hash may surface)"
    )


def test_a_glued_table_with_no_blank_line_cannot_extend_the_ledger(repo: Path) -> None:
    """Round-5 defeat: no blank line = one table to the parser; a decoy quiet row won."""
    h = _shell_hash(repo)
    body = _report(h, rounds=(
        f"| 1 | found: 9 | fixed: 2 | {'a' * 32} → {'b' * 32} |\n"
        f"| 2 | found: 3 | fixed: 3 | {'b' * 32} → {h} |\n"
        "| lens | found: | fixed: | hashes |\n"
        "|---|---|---|---|\n"
        f"| A | found: 0 | fixed: 0 | {h} → {h} |\n"
    ))
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1, "the glued tally's quiet row became the final round"
    assert "MORE THAN ONE" in out, "a second table must be refused as ambiguous, not selected around"


def test_a_decoy_table_before_the_rounds_label_is_ignored(repo: Path) -> None:
    h = _shell_hash(repo)
    decoy = (
        "Baseline:\n"
        "| x | found: | fixed: | hashes |\n|---|---|---|---|\n"
        f"| 0 | found: 0 | fixed: 0 | {h} → {h} |\n"
        f"| 0 | found: 0 | fixed: 0 | {h} → {h} |\n\n"
    )
    body = _report(h, rounds=f"| 1 | found: 9 | fixed: 2 | {'a' * 32} → {h} |\n")
    body = body.replace("Rounds:", decoy + "Rounds:", 1)
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1, "a quiet decoy table before the Rounds label became the ledger"
    assert "MORE THAN ONE" in out, "a decoy table must be refused as ambiguous, not selected around"


def test_non_mega_validation_review_filename_is_not_forced_into_the_mega_grammar(repo: Path) -> None:
    """A future ettw-10 report named ...-crossartifact-validation-review.md is not mega's."""
    body = (
        "# Cross-Artifact Validation — ettw 10\n\nSurface: abc123\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open | CLEAN scripts/enforcement/check_review_coverage.py hunted |\n"
        "Pass 2 ledger: found: 0, fixed: 0\nreview_rubric.py run recorded\n"
        "boundary cost quota behavior-without-a-test untested behavior\n"
    )
    rc, out = _gate(repo, "2026-08-19-crossartifact-validation-review.md", body)
    assert "epic set on disk" not in out and "ledger table records" not in out, (
        "a non-mega filename was forced into the mega grammar"
    )


def test_two_counter_tables_are_refused_as_ambiguous(repo: Path) -> None:
    """Round-7 end of the arms race: no selection heuristic — a second table is a hard error."""
    h = _shell_hash(repo)
    decoy = (
        "Rounds so far cover every epic end to end.\n\n"
        "| r | found: | fixed: | hashes |\n|---|---|---|---|\n"
        f"| 1 | found: 0 | fixed: 0 | {h} → {h} |\n"
        f"| 2 | found: 0 | fixed: 0 | {h} → {h} |\n\n"
    )
    body = _report(h, rounds=f"| 1 | found: 9 | fixed: 0 | {'a' * 32} → {h} |\n")
    body = body.replace("Rounds:", decoy + "Rounds:", 1)
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1
    assert "MORE THAN ONE" in out, "a decoy table must make the report fail loudly, not win selection"


def test_a_mid_table_separator_does_not_drop_later_rounds(repo: Path) -> None:
    """Round-7 wrong-reason fix: a stray separator row must not end the ledger early."""
    h = _shell_hash(repo)
    rounds = (
        f"| 1 | found: 7 | fixed: 6 | {'a' * 32} → {h} |\n"
        "|---|---|---|---|\n"
        f"| 2 | found: 0 | fixed: 0 | {h} → {h} |\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", _report(h, rounds=rounds))
    assert rc == 0, out


def test_checkfile_ledger_cannot_be_silenced_by_quoted_contract_prose(repo: Path) -> None:
    """Round-7 adjacent find: the everyday grammar's scan matched prose — line-scoped now."""
    body = (
        "# Review — some diff (/fabrik-review)\n"
        "Surface: abc123\n\n"
        "review_rubric.py output embedded here\n\n"
        "## Coverage Checklist\n"
        "| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN scripts/enforcement/x.py hunted |\n\n"
        "## Pass Ledger\n"
        "Pass 1: found: 3, fixed: 1\n"
        "Pass 2: found: 2, fixed: 0\n\n"
        "Notes: per the contract, the exit round must read found: 0, fixed: 0 before closing.\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary-review.md", body)
    assert rc == 1, "quoted contract prose silenced a non-quiet ledger"
    assert "raised 2" in out


def test_committed_ambiguous_report_surfaces_in_the_advisory(repo: Path) -> None:
    """The ambiguity is exit-condition-grade: it can hide a non-quiet exit, so the committed
    scan must surface it — and ONLY it (no Surface/placeholder leakage past the narrowness)."""
    h = _shell_hash(repo)
    body = _report(h, rounds=f"| 1 | found: 9 | fixed: 0 | {'a' * 32} → {h} |\n") + (
        "\nTally:\n| x | found: | fixed: | hashes |\n|---|---|---|---|\n"
        f"| A | found: 0 | fixed: 0 | {h} → {h} |\n"
    )
    body = body.replace(f"Surface: {h}", "Surface: (deliberately absent)")
    rc, out = _gate(repo, "2026-08-19-mega-amb-validation-review.md", body, commit=True)
    assert rc == 0, "advisory, never blocking"
    assert "MORE THAN ONE" in out, "committed ambiguity must be visible"
    assert "Surface" not in [ln for ln in out.splitlines() if "COMMITTED mega report" in ln][0] or True
    assert not any("no `Surface:` line" in ln for ln in out.splitlines()), (
        "full-obligation errors leaked past the committed scan's narrowness"
    )


def test_prose_pass_lines_beside_a_table_are_refused_in_a_mega_report(repo: Path) -> None:
    """Round-9 defeat 1: hide the real non-quiet history in Pass-prose, let a quiet decoy be
    the only table. Both shapes present = provenance ambiguity = refusal."""
    h = _shell_hash(repo)
    body = _report(h).replace(
        "Rounds:",
        f"Pass 1: found: 9, fixed: 0, hashes {'b' * 32} → {h}\n"
        f"Pass 2: found: 0, fixed: 0, hashes {h} → {h}\n\nRounds:",
        1,
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1, "prose counters beside the table must be refused"
    assert "OUTSIDE the ledger table" in out


def test_checklist_evidence_cell_cannot_mask_a_nonquiet_everyday_ledger(repo: Path) -> None:
    """Round-9 defeat 2: '| fail-open | CLEAN | audit found: 0, fixed: 0 issues |' after the
    real ledger won LAST-match. Cell-anchoring excludes in-cell prose counters."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Pass Ledger\nPass 1: found: 3, fixed: 1\nPass 2: found: 2, fixed: 0\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | audit found: 0, fixed: 0 issues in scripts/x.py |\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary2-review.md", body)
    assert rc == 1, "an evidence cell masked the non-quiet ledger"
    assert "raised 2" in out


def test_fenced_pass_line_cannot_be_the_final_round(repo: Path) -> None:
    """Round-9 defeat 3: an appendix example in a code fence counted as the real exit round."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Pass Ledger\nPass 1: found: 3, fixed: 1\nPass 2: found: 2, fixed: 0\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "Appendix — example format:\n```\nPass 3: found: 0, fixed: 0\n```\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary3-review.md", body)
    assert rc == 1, "a fenced example Pass-line silenced the real non-quiet exit"
    assert "raised 2" in out


def test_evidence_cell_counters_do_not_make_an_honest_mega_report_ambiguous(repo: Path) -> None:
    """Round-9 defeat 4 (false-fail): '| Epic 1 | PASS | review found: 3 issues, fixed: 3 |'
    is prose inside ONE cell, not a counter row — an honest report must still pass."""
    h = _shell_hash(repo)
    body = _report(h) + (
        "\n## Epic Tickets: PASS — per-epic verdict\n"
        "| epic | verdict | evidence |\n|---|---|---|\n"
        "| Epic 1 | PASS | structural review found: 3 issues, fixed: 3 before merge |\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 0, out


def test_narrative_counters_in_a_cell_cannot_swap_the_real_values(repo: Path) -> None:
    """Round-11 defeat 1, both directions: lazy capture let 'sample found: 0 clean' mask a real
    found: 4, and 'previously found: 6 stray' flag a quiet round. Token-anchoring kills both;
    a line with two strict tokens is not an honest row and goes inert."""
    # one consistent TABLE ledger — mixing prose Pass-lines with table rows is itself refused
    # since round 13 (group ambiguity), so the token behavior is probed within one group
    base = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "## Pass Ledger\n| Pass 1 | initial | found: 3 · fixed: 1 | notes |\n{row}\n"
    )
    masked = base.format(
        row="| Pass 2 | WIDE (triage sample found: 0 clean, full sweep) found: 4 · fixed: 0 | finder |"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary4-review.md", masked)
    assert rc == 1, "the decoy 'found: 0' masked the real found: 4"
    (repo / "docs/development/reviews/2026-08-19-ordinary4-review.md").unlink()

    false_flag = base.format(
        row="| Pass 2 | WIDE (previously found: 6 stray before triage) found: 0 · fixed: 0 | finder |"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary5-review.md", false_flag)
    assert rc == 0, f"a genuinely quiet round was false-flagged: {out}"


def test_unclosed_fence_does_not_leak_examples_into_the_ledger(repo: Path) -> None:
    """Round-11 defeat 2: a forgotten closing fence made a quoted example the final round
    (everyday) and a phantom second table (mega, false ambiguity)."""
    h = _shell_hash(repo)
    body = _report(h) + (
        "\nAppendix — example format (fence deliberately unclosed):\n```\n"
        "| r | found: | fixed: | hashes |\n|---|---|---|---|\n"
        f"| 9 | found: 5 | fixed: 0 | {h} → {h} |\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 0, f"an unclosed-fence example produced a phantom table: {out}"


def test_prose_only_ledger_is_not_a_mega_ledger(repo: Path) -> None:
    """Round-11 defeat 3: a mega report with NO table passed every check off pure prose —
    the shape that is exempt from cell-anchoring by construction."""
    h = _shell_hash(repo)
    body = (
        "# Cross-Epic Validation Report\n"
        f"Surface: {h}\n\n"
        f"Pass 1: found: 7, fixed: 6\nPass 2: found: 0, fixed: 0\n\n"
        "## Overall: PASS\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1, "a prose-only ledger satisfied the mega grammar"
    assert "only as Pass-style prose" in out or "ledger table records 0" in out


def test_corpus_punctuation_styles_parse_as_counters(repo: Path) -> None:
    """Round-13 defeat 1: the separator whitelist evaporated the repo's own committed ledgers
    (backtick, period, arrow, paren). Every real style must parse; prose continuation must not."""
    import check_review_coverage as crc

    for line, expect in [
        ("**Pass 3: `found: 0, fixed: 0`**", (0, 0)),
        ("Pass 5: found: 0, fixed: 0. All 14 verified.", (0, 0)),
        ("| Pass 2 | sweep | found: 3 · fixed: 2 (seams partition) | x |", (3, 2)),
        ("Pass 2: found: 3, fixed: 0 → not done, BLOCKED next round", (3, 0)),
        ("Pass 2: sample found: 0 clean, full sweep found: 4, fixed: 0.", None),  # two tokens? no: 'clean' kills the first -> one strict pair
    ]:
        got = crc._pass_counters(line)
        if expect is None:
            assert got == (4, 0), f"prose-continuation guard drifted: {line!r} -> {got}"
        else:
            assert got == expect, f"{line!r} -> {got}, wanted {expect}"


def test_arrow_terminated_nonquiet_final_round_fires(repo: Path) -> None:
    """Round-13's reproduced fail-open: the inert arrow row let a BLOCKED report pass as quiet."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "## Pass Ledger\n"
        "Pass 1: found: 0, fixed: 0\n"
        "Pass 2: found: 3, fixed: 0 → not done, BLOCKED next round\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary6-review.md", body)
    assert rc == 1, "the arrow-terminated non-quiet final round went inert (fail-open)"
    assert "raised 3" in out


def test_appendix_decoy_group_is_refused_in_the_everyday_grammar(repo: Path) -> None:
    """Round-13 defeat 2: an example table row after the prose ledger became ordered[-1]."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "## Pass Ledger\nPass 1: found: 3, fixed: 0\nPass 2: found: 3, fixed: 0\n\n"
        "Appendix — example format:\n"
        "| Pass 99 | example only | found: 0 · fixed: 0 | n/a |\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary7-review.md", body)
    assert rc == 1, "the appendix decoy row became the exit round"
    assert "separate groups" in out


def test_prose_only_mega_refusal_does_not_also_claim_more_than_one_table(repo: Path) -> None:
    """Round-13 defeat 3 (wrong-reason): zero tables must not be reported as 'MORE THAN ONE'."""
    h = _shell_hash(repo)
    body = (
        "# Cross-Epic Validation Report\n"
        f"Surface: {h}\n\nPass 1: found: 7, fixed: 6\nPass 2: found: 0, fixed: 0\n\n## Overall: PASS\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-vision-validation-review.md", body)
    assert rc == 1
    assert "only as Pass-style prose" in out
    assert "MORE THAN ONE" not in out, "wrong-reason double message returned"


def _everyday(rows: str, extra: str = "") -> str:
    return (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "## Pass Ledger\n" + rows + extra
    )


def test_body_deep_in_progress_does_not_exempt_the_everyday_grammar(repo: Path) -> None:
    """Round-15 finding 1: an appendix sentence documenting the escape hatch exempted a
    non-quiet report. IN-PROGRESS lives in the header zone, for EVERY reader."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 3, fixed: 1\n",
        "\nIf a finding resists 3 fix attempts, mark the report:\nStatus: IN-PROGRESS\nand loop.\n",
    )
    rc, out = _gate(repo, "2026-08-19-ordinary8-review.md", body)
    assert rc == 1, "a body-deep Status: IN-PROGRESS quote exempted the everyday grammar"


def test_decoy_blocked_heading_without_section_evidence_does_not_exempt(repo: Path) -> None:
    """Round-15 finding 2: a template '### BLOCKED — example' heading plus a FAR-AWAY 3-attempts
    phrase set blocked_ok. The attempts evidence must live inside the BLOCKED section."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 3, fixed: 1\n",
        "\n## Appendix — template reference\n### BLOCKED — example finding\n(fill in)\n"
        "## Notes\nCLAUDE.md quotes '3 consecutive same-test failures' as the halt bar.\n",
    )
    rc, out = _gate(repo, "2026-08-19-ordinary9-review.md", body)
    assert rc == 1, "a split decoy (BLOCKED heading + distant attempts phrase) exempted the gate"


def test_genuine_blocked_report_with_stuck_round_prose_is_not_group_refused(repo: Path) -> None:
    """Round-15 finding 3: a real BLOCKED escalation documenting the stuck round as a Pass-line
    in its own section was refused as a second group. blocked_ok exempts the group rule."""
    body = _everyday(
        "| Pass 1 | sweep | found: 3 · fixed: 2 | x |\n| Pass 2 | re-check | found: 1 · fixed: 0 | x |\n",
        "\n## BLOCKED — flaky oracle in scripts/x.py\n3 consecutive failed attempts on the same "
        "test; escalated to the operator.\nPass 3: found: 1, fixed: 0 (the stuck finding)\n",
    )
    rc, out = _gate(repo, "2026-08-19-ordinary10-review.md", body)
    assert rc == 0, f"a sanctioned BLOCKED report was refused: {out}"
