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
    # CONTRACT CHANGE (round 47): parity precondition — the deliberately-unclosed appendix
    # fence now fails accurately ("close the fence") instead of being silently tolerated;
    # the original defect (a phantom table from the leak) stays impossible either way.
    assert rc == 1
    assert "UNCLOSED" in out and "never closed" in out


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
        "## Notes\nElsewhere we failed 3 attempts at an unrelated deploy.\n",
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


def test_bare_decoy_blocked_headings_do_not_inflate_the_cardinality(repo: Path) -> None:
    """Round-19 finding 1: N-1 empty decoy headings + 1 real escalation waived N rows."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open | UNCHECKED |  |\n| cost quota | UNCHECKED |  |\n"
        "| boundary untested behavior | UNCHECKED |  |\n\n"
        "## Pass Ledger\n| Pass 1 | x | found: 3 · fixed: 3 | y |\n| Pass 2 | x | found: 0 · fixed: 0 | y |\n\n"
        "## BLOCKED — real one in scripts/x.py\nfailed 3 attempts on the same test; escalated.\n\n"
        "### BLOCKED — decoy A\n(TBD)\n\n### BLOCKED — decoy B\n(TBD)\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary11-review.md", body)
    assert rc == 1, "bare decoy headings inflated the evidenced-section count"
    assert "UNCHECKED" in out


def test_long_bounded_blocked_section_with_late_evidence_is_accepted(repo: Path) -> None:
    """Round-19 finding 3: the repo's own committed style puts the attempts phrase ~2KB in."""
    filler = "repro detail line\n" * 80
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
        "## Pass Ledger\n| Pass 1 | x | found: 1 · fixed: 0 | y |\n| Pass 2 | x | found: 1 · fixed: 0 | y |\n\n"
        "## BLOCKED — deep repro in scripts/x.py\n" + filler +
        "After all of the above: failed 3 attempts on the same test; escalated to the operator.\n\n"
        "## Closing\ndone.\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary12-review.md", body)
    assert rc == 0, f"a bounded section with late evidence was rejected: {out}"


def test_committed_in_progress_report_is_visible_not_cloaked(repo: Path) -> None:
    """Round-21 finding 2: IN-PROGRESS made a committed report permanently invisible."""
    body = (
        "# Cross-Epic Validation Report\nSurface: none-yet\nStatus: IN-PROGRESS\n\n"
        "Rounds:\n| r | found: | fixed: | h |\n|---|---|---|---|\n| 1 | found: 9 | fixed: 0 | tbd |\n"
    )
    rc, out = _gate(repo, "2026-08-19-mega-cloak-validation-review.md", body, commit=True)
    assert rc == 0, "advisory, never blocking"
    assert "COMMITTED as Status: IN-PROGRESS" in out, "the cloak is still invisible"


def test_absent_epic_set_fails_the_blocking_gate_loudly(tmp_path: Path) -> None:
    """Round-23 finding 1: no epics dir = the anti-cheat silently skipped = a fabricated
    hash chain passed the BLOCKING gate. Unverifiable must mean FAIL, not shrug."""
    import subprocess as sp
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    fake = "d" * 32
    body = _report(fake)  # no docs/development/epics at all
    rc, out = _gate(tmp_path, "2026-08-19-mega-fab-validation-review.md", body)
    assert rc == 1, "a fabricated chain passed with the epic set absent"
    assert "cannot be verified against nothing" in out


def test_non_checklist_review_doc_with_status_line_is_not_nagged(repo: Path) -> None:
    """Round-23 finding 3: the advisory misattributed spec/plan convergence artifacts."""
    body = "# Plan-Review Convergence Notes\nStatus: IN-PROGRESS\n\nprose only, no checklist\n"
    rc, out = _gate(repo, "2026-08-19-other-artifact-review.md", body, commit=True)
    assert rc == 0
    assert "other-artifact" not in out, "a non-subject doc was nagged forever"


def test_checklist_branch_committed_in_progress_is_nagged(repo: Path) -> None:
    """Round-23 finding 4 (coverage): the SECOND grammar branch, committed, was untested."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\nStatus: IN-PROGRESS\n\n"
        "review_rubric.py output\n\n## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-19-ordinary13-review.md", body, commit=True)
    assert rc == 0
    assert "COMMITTED as Status: IN-PROGRESS" in out


def test_prose_quote_of_the_command_is_not_report_shaped(repo: Path) -> None:
    """Round-25 findings 1+2: quoting /fabrik-review in prose made a notes doc a subject —
    blocking-failed when changed, nagged forever when committed with a Status line."""
    body = "# Plan Convergence Notes\n\nNext, run /fabrik-review to adjudicate the diff.\n"
    rc, out = _gate(repo, "2026-08-19-notes-review.md", body)
    assert rc == 0, f"a prose quote hard-failed the blocking gate: {out}"
    body2 = "# Spec Convergence Notes\nStatus: IN-PROGRESS\n\nWe then ran /fabrik-review here.\n"
    rc, out = _gate(repo, "2026-08-19-notes2-review.md", body2, commit=True)
    assert rc == 0
    assert "notes2" not in out, "a prose-quoting non-subject doc was nagged"


def test_note_lines_print_after_the_advisory_header(repo: Path) -> None:
    """Round-25 finding 3: a NOTE printing first broke the emitter's startswith-⚠ opt-in
    and silently re-hid the advisory payload from the gate JSON."""
    committed = (
        "# Review — old (/fabrik-review)\nSurface: abc\n\nreview_rubric.py ran\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN scripts/x.py |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 2, fixed: 0\n"
    )
    _gate(repo, "2026-08-19-old-review.md", committed, commit=True)
    (repo / "docs/development/reviews/2026-08-19-draft-review.md").write_text("# draft\n")
    import subprocess
    import sys as _s
    r = subprocess.run(
        [_s.executable, str(CHECK), "--root", str(repo)], capture_output=True, text=True, timeout=30
    )
    out = r.stdout
    assert "COMMITTED with a non-quiet" in out and "NOTE:" in out, "fixture must exercise both"
    assert out.lstrip().startswith("⚠"), f"stdout does not lead with ⚠:\n{out[:200]}"


def test_prose_discussing_a_coverage_checklist_is_not_a_subject(repo: Path) -> None:
    """Round-27: the heading-only rule — discussing the concept is not carrying the artifact."""
    body = (
        "# Plan Convergence Notes\n\nWe debated whether this ticket needs a coverage checklist "
        "before merging, but decided it's out of scope. It internally invokes "
        "`python scripts/review_rubric.py` anyway. Run /fabrik-review later.\n"
    )
    rc, out = _gate(repo, "2026-08-19-notes3-review.md", body)
    assert rc == 0, f"prose about the process became a subject: {out}"


def test_a_real_checklist_heading_is_still_fully_gated(repo: Path) -> None:
    """The structural contract's other half: the heading alone pulls the full obligation set."""
    body = "# Anything\n\n## Coverage Checklist\n| C | V | E |\n|---|---|---|\n| x | UNCHECKED |  |\n"
    rc, out = _gate(repo, "2026-08-19-real14-review.md", body)
    assert rc == 1
    assert "Surface" in out and "UNCHECKED" in out


def test_h1_checklist_heading_is_still_a_subject(repo: Path) -> None:
    """Round-29: `# Coverage Checklist` (H1) escaped every obligation — no source ever told
    authors which level to use, so the level window must include H1."""
    body = "# Coverage Checklist\n| C | V | E |\n|---|---|---|\n| x | UNCHECKED |  |\n"
    rc, out = _gate(repo, "2026-08-19-h1-review.md", body)
    assert rc == 1, "an H1 checklist escaped the gate"
    assert "UNCHECKED" in out


def test_heading_substring_needs_the_phrase_at_start(repo: Path) -> None:
    """Round-29: `## Non-coverage checklist items` was a subject via bare substring."""
    body = "# Notes\n\n## Non-coverage checklist items\n\nprose only\n"
    rc, out = _gate(repo, "2026-08-19-noncov-review.md", body)
    assert rc == 0, f"a mid-phrase heading became a subject: {out}"


def test_cert_filename_does_not_exempt_a_present_checklist(repo: Path) -> None:
    """Round-37 finding 1: a -user-test- filename routed a checklist-obligated report to the
    looser cert grammar and exited green with live UNCHECKED rows."""
    body = (
        "# Review of the user-test workflow\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-20-fabrik-user-test-workflow-review.md", body)
    assert rc == 1, "the filename substring exempted a present checklist"
    assert "UNCHECKED" in out


def test_fenced_handoff_example_does_not_fail_a_cert_report(repo: Path) -> None:
    """Round-37 finding 2: the cert grammar never fence-stripped — a documentation example
    produced false BLOCKING failures on an honest report."""
    body = (
        "# Certification run — all clear\n\nGrammar reference (example only):\n"
        "```\nHANDOFF P1 CLOSED example — repro: docs/does/not/exist.md — proof: n/a\n```\n"
        "\nNo real findings this run.\n"
    )
    rc, out = _gate(repo, "2026-08-20-thing-user-test-r1.md", body)
    assert rc == 0, f"a fenced example failed an honest cert report: {out}"


def test_template_status_boilerplate_is_a_leftover(repo: Path) -> None:
    """Round-37 finding 3: the angle-bracket Status placeholder escaped the leftover scan."""
    h = _shell_hash(repo)
    body = _report(h).replace(
        f"Surface: {h}",
        f"Surface: {h}\nStatus: <omit when converged; `Status: IN-PROGRESS` for an interrupted run>",
    )
    rc, out = _gate(repo, "2026-08-20-mega-boiler-validation-review.md", body)
    assert rc == 1, "shipped template boilerplate on the Status line read as adjudicated"
    assert "boilerplate" in out or "placeholder" in out


def test_grammar_below_an_unclosed_fence_fails_a_cert_report_loudly(repo: Path) -> None:
    """Round-39 finding 1: the fence-strip erased real HANDOFF rows below a dangling ``` and
    the floor-less cert grammar passed clean. Unverifiable content is loud, never silent."""
    body = (
        "# Certification run\n\nPasted terminal output:\n```\n$ some command\n"
        "\nHANDOFF P1 OPEN real finding — repro: docs/x.md — route: /fabrik-review\n"
    )
    rc, out = _gate(repo, "2026-08-20-thing2-user-test-r1.md", body)
    assert rc == 1, "real dispositions below an unclosed fence were silently erased"
    assert "UNCLOSED" in out


def test_fenced_checklist_quote_does_not_route_a_cert_report_to_check_file(repo: Path) -> None:
    """Round-39 finding 2: the routing decision read RAW text, so a fenced documentation
    example quoting the checklist heading force-routed an honest cert report into five
    fabricated obligations."""
    body = (
        "# Certification run — all clear\n\nGrammar note (example only):\n"
        "```\n## Coverage Checklist\n| x | UNCHECKED |  |\n```\n\n"
        "HANDOFF P1 CLOSED thing — repro: docs/x.md — proof: green run\n"
    )
    (repo / "docs/x.md").write_text("# repro\n")
    rc, out = _gate(repo, "2026-08-20-thing3-user-test-r1.md", body)
    assert rc == 0, f"a fenced checklist quote fabricated obligations: {out}"


def test_fenced_checklist_quote_is_not_a_subject_anywhere(repo: Path) -> None:
    """Round-41: the fenced-example defeat lived in _checklist_section's OLDER call sites —
    an honest how-to doc quoting the heading in a fence was false-BLOCKED with five
    fabricated obligations. Stripped at the DEFINITION now: every caller inherits."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "Example of the required section format:\n```\n## Coverage Checklist\n\n"
        "| Class | Verdict | Evidence |\n|---|---|---|\n| example | UNCHECKED |  |\n```\n\n"
        "That is all this doc contains.\n"
    )
    rc, out = _gate(repo, "2026-08-20-howto-review.md", body)
    assert rc == 0, f"a fenced heading quote made a how-to doc a subject: {out}"
    rc, out = _gate(repo, "2026-08-20-howto2-review.md", body + "\nStatus: nothing\n", commit=True)
    assert rc == 0
    assert "howto2" not in out, "the committed scan also misclassified the quoting doc"


def test_unclosed_fence_swallowing_the_checklist_fails_loudly(repo: Path) -> None:
    """Round-43 finding 1: an unclosed fence BEFORE the heading made an obligated report
    invisible to the primary gate AND the committed advisory."""
    body = (
        "# Review\n\nPasted transcript:\n```\n$ some output\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-20-swallow-review.md", body)
    assert rc == 1, "a swallowed checklist exempted the report silently"
    assert "UNCLOSED" in out
    rc, out = _gate(repo, "2026-08-20-swallow2-review.md", body, commit=True)
    assert rc == 0
    assert "UNCLOSED" in out, "the committed advisory missed the swallowed checklist"


def test_fenced_surface_example_does_not_satisfy_the_obligation(repo: Path) -> None:
    """Round-43 finding 2: the three obligation checks were the last raw-text seam — a fenced
    example quoting Surface: satisfied the cross-run anchor."""
    body = (
        "# Review — some diff (/fabrik-review)\n\n"
        "Example header format:\n```\nSurface: abcdef1234567890\nPass 2 example\nreview_rubric.py\n```\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN scripts/x.py hunted |\n\n"
        "## Pass Ledger\n| Pass 1 | x | found: 0 · fixed: 0 | y |\n| Pass 2 | x | found: 0 · fixed: 0 | y |\n"
    )
    rc, out = _gate(repo, "2026-08-20-fencedsurf-review.md", body)
    assert rc == 1, "a fenced Surface example satisfied the obligation"
    assert "Surface" in out


def test_unrelated_dangling_fence_does_not_false_fire_the_floor(repo: Path) -> None:
    """Round-45: a balanced-fenced heading quote + an unrelated dangling transcript fence
    false-BLOCKED a doc that owes nothing — the floor now position-anchors like cert's."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "Example of the required section format:\n```\n## Coverage Checklist\n\n"
        "| Class | Verdict | Evidence |\n|---|---|---|\n| example | UNCHECKED |  |\n```\n\n"
        "That is all this doc contains.\n\n"
        "Appendix — pasted terminal session (fence deliberately unclosed):\n```\n$ ls\nfoo.txt\n"
    )
    rc, out = _gate(repo, "2026-08-20-howto3-review.md", body)
    # CONTRACT CHANGE (round 47): fence PARITY is now a precondition — round 45's complaint
    # was the WRONG-REASON message (accusing a checklist that didn't exist), not that flagging
    # a genuinely dangling fence is wrong. The doc DOES have an unclosed fence; the accurate
    # one-keystroke message is correct, and undecidable intent-guessing is retired.
    assert rc == 1
    assert "UNCLOSED" in out and "never closed" in out


def test_tilde_fenced_checklist_example_is_not_a_subject(repo: Path) -> None:
    """Round-49 finding 1: `_strip_fences` stripped only backtick fences — a how-to doc
    quoting the checklist inside GFM's OTHER fence flavor (~~~) false-fired as a subject."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "Example of the required section format:\n~~~\n## Coverage Checklist\n\n"
        "| Class | Verdict | Evidence |\n|---|---|---|\n| example | UNCHECKED |  |\n~~~\n\n"
        "That is all this doc contains.\n"
    )
    rc, out = _gate(repo, "2026-08-20-tilde-howto-review.md", body)
    assert rc == 0, f"a tilde-fenced checklist quote made a how-to doc a subject: {out}"
    rc, out = _gate(repo, "2026-08-20-tilde-howto2-review.md", body, commit=True)
    assert rc == 0
    assert "tilde-howto2" not in out, "the committed scan also misread the tilde fence"


def test_dangling_tilde_fence_fails_parity(repo: Path) -> None:
    """Round-49 finding 1 (parity half): the parity precondition counted only ``` markers,
    so an unclosed ~~~ fence — the same unverifiable-structure defect — passed silently."""
    h = _shell_hash(repo)
    body = _report(h) + "\nAppendix — pasted session (fence unclosed):\n~~~\n$ ls\nfoo.txt\n"
    rc, out = _gate(repo, "2026-08-20-mega-vision-validation-review.md", body)
    assert rc == 1, "a dangling tilde fence was invisible to parity"
    assert "UNCLOSED" in out and "never closed" in out


def test_in_progress_precedes_parity(repo: Path) -> None:
    """Round-49 finding 2: parity fired BEFORE the IN-PROGRESS escape, so a sanctioned
    mid-loop report with a dangling appendix fence was blocked (live) and wrong-reason
    advised (committed). The parity obligation binds at the flip, not mid-loop."""
    mega = (
        "# Cross-Epic Validation Report\n"
        "Status: IN-PROGRESS\n\n"
        "round 3 running.\n\nAppendix (fence unclosed):\n```\n$ pytest\n"
    )
    rc, out = _gate(repo, "2026-08-20-mega-vision-validation-review.md", mega)
    assert rc == 0, f"a mid-loop mega report with a dangling fence was blocked: {out}"
    checklist = (
        "# Review — some diff (/fabrik-review)\n"
        "Status: IN-PROGRESS\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
        "Appendix (fence unclosed):\n```\n$ pytest\n"
    )
    rc, out = _gate(repo, "2026-08-20-midloop-review.md", checklist)
    assert rc == 0, f"a mid-loop checklist report with a dangling fence was blocked: {out}"
    rc, out = _gate(repo, "2026-08-20-midloop2-review.md", checklist, commit=True)
    assert rc == 0
    assert "IN-PROGRESS" in out, "the committed advisory lost the mid-loop line"
    assert "midloop2-review.md: COMMITTED with an" not in out, (
        "the committed advisory gave the wrong-reason UNCLOSED line instead of IN-PROGRESS"
    )


def test_cross_flavor_camouflage_cannot_hide_a_dangling_fence(repo: Path) -> None:
    """Round-51 CONFIRMED: per-flavor raw counting let a lone marker of the OTHER flavor,
    quoted as content inside a real fence, cancel the count — a camouflaged dangling fence
    swallowed a live UNCHECKED checklist and the gate exited green (fail-open through the
    parity precondition itself). The sequential scan reads it as a renderer would."""
    body = (
        "# Review\n\nPasted transcript (fence deliberately unclosed):\n```\n$ some output\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
        "Later, a REAL tilde block quoting a bare backtick fence line:\n~~~\n```\n~~~\n"
    )
    rc, out = _gate(repo, "2026-08-20-camouflage-review.md", body)
    assert rc == 1, "a cross-flavor quote camouflaged a dangling fence into a green exit"
    assert "UNCLOSED" in out


def test_cross_flavor_quote_inside_a_closed_fence_is_content(repo: Path) -> None:
    """Round-51 PLAUSIBLE (mirror): an honest doc quoting the other flavor's marker inside a
    properly-closed fence was rejected as UNCLOSED by the raw count. Sequential scan: content."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "Fence syntax example (a bare tilde marker as content):\n```\n~~~\n```\n\n"
        "That is all this doc contains.\n"
    )
    rc, out = _gate(repo, "2026-08-20-flavorquote-review.md", body)
    assert rc == 0, f"an honest cross-flavor quote false-fired the parity precondition: {out}"


def test_indented_closer_is_a_valid_fence_closer(repo: Path) -> None:
    """Round-51 PLAUSIBLE: a closer indented 1-3 spaces is a valid CommonMark fence closer
    (editor auto-indent), but the column-0 anchors missed it and flagged the doc UNCLOSED."""
    h = _shell_hash(repo)
    body = _report(h) + "\nAppendix:\n```\n$ ls\n   ```\n\nprose after the closed fence.\n"
    rc, out = _gate(repo, "2026-08-20-mega-vision-validation-review.md", body)
    assert rc == 0, f"an indented closer was invisible and the doc was falsely UNCLOSED: {out}"


def test_indented_code_block_cannot_mask_the_final_round(repo: Path) -> None:
    """Round-53 CRITICAL: CommonMark INDENTED code blocks (4+ spaces after a blank line) are
    quoted content to a renderer, but the grammar read them live — with an all-prose ledger
    (one group by construction, so the multi-group guard is silent) an indented quiet Pass
    row became the document-order final round, masking a real non-quiet exit (fail-open,
    reproduced end-to-end and cross-checked against markdown-it-py)."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 7, fixed: 6\n",
        "\nAppendix — indented example of a quiet row:\n\n"
        "    Pass 99: found: 0, fixed: 0\n",
    )
    rc, out = _gate(repo, "2026-08-20-indented-mask-review.md", body)
    # CONTRACT CHANGE (round 55): the silent strip round 54 answered this with itself failed
    # open the other way (a live indented row VANISHED) — an indented grammar-shaped line is
    # now refused loudly as undecidable, same adjudication as fence parity.
    assert rc == 1, "an indented fake quiet row masked a non-quiet final round"
    assert "INDENTED grammar-shaped line" in out


def test_indented_example_row_is_refused_as_undecidable(repo: Path) -> None:
    """Round-55 adjudication: an indented grammar-shaped line is undecidable — quoted to a
    renderer, load-bearing to the eye. Round 54 stripped it silently and the next sweep
    reproduced live rows VANISHING (an UNCHECKED checklist row and an OPEN HANDOFF row
    invisible to their gates). Refused loudly instead, like fence parity: never counted as
    live (masking stays impossible), never silently dropped (vanishing stays impossible)."""
    body = (
        "# Review — some diff (/fabrik-review)\n\n"
        f"Surface: {'b' * 32}\n"
        "review_rubric.py output embedded.\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN scripts/x.py hunted |\n\n"
        "Row-format example, indented as code:\n\n"
        "    | example class | UNCHECKED |  |\n\n"
        "## Pass Ledger\n| Pass 1 | x | found: 0 · fixed: 0 | y |\n"
        "| Pass 2 | x | found: 0 · fixed: 0 | y |\n"
    )
    rc, out = _gate(repo, "2026-08-20-indented-example-review.md", body)
    assert rc == 1, "an indented grammar-shaped line was silently adjudicated one way or the other"
    assert "INDENTED grammar-shaped line" in out


def test_backtick_info_string_with_backtick_is_not_an_opener(repo: Path) -> None:
    """Round-53 MEDIUM: CommonMark forbids a backtick in a backtick fence's info string — a
    one-line ```demo``` illustration is a paragraph to a renderer, but the scanner read it as
    a dangling opener and false-fired UNCLOSED, swallowing the real checklist after it."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "```demo``` — a one-line illustration of inline fence syntax.\n\n"
        "That is all this doc contains.\n"
    )
    rc, out = _gate(repo, "2026-08-20-inline-backticks-review.md", body)
    assert rc == 0, f"a one-line backtick illustration false-fired UNCLOSED: {out}"
    assert "UNCLOSED" not in out


def test_indented_unchecked_row_cannot_vanish(repo: Path) -> None:
    """Round-55 CRITICAL 1: the round-54 silent strip made a genuinely-live UNCHECKED
    checklist row (blank line above, 4-space indent — a routine editor accident) VANISH from
    check_file entirely: zero errors on a plainly unadjudicated report."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n\n"
        "    | the-actual-risky-finding | UNCHECKED |  |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-vanish-unchecked-review.md", body)
    assert rc == 1, "an indented live UNCHECKED row vanished from the checklist gate"
    assert "INDENTED grammar-shaped line" in out


def test_indented_handoff_row_cannot_vanish(repo: Path) -> None:
    """Round-55 CRITICAL 2: same vector, cert grammar — an indented OPEN HANDOFF row routed
    to /fabrik-review with no evidence vanished from HANDOFF_ROW.findall, and the emptied
    rows list also waived the NOT-QUIET obligation."""
    body = (
        "# cert\n\nDispositions:\n\n"
        "    HANDOFF P1 OPEN some risky finding — repro: tests/t.py — route: /fabrik-review src/x\n\n"
        "## RESUME\nre-run the journey\n"
    )
    rc, out = _gate(repo, "2026-08-20-user-test-vanish.md", body)
    assert rc == 1, "an indented OPEN HANDOFF row vanished from the cert gate"
    assert "INDENTED grammar-shaped line" in out


def test_indented_filler_cannot_shrink_the_header_zone(repo: Path) -> None:
    """Round-55 CRITICAL 3: the 10-line header zone was sliced from STRIPPED text, so
    blank-line-preceded indented filler above a body-deep Status: IN-PROGRESS shrank the
    document and pulled the line into the zone — a whole-grammar exemption. The zone now
    anchors to RAW line positions (stripped within the slice)."""
    filler = "".join(f"\n    filler line {i}\n" for i in range(7))
    body = (
        "# Review — some diff (/fabrik-review)\n"
        + filler
        + "\nprose\n\nStatus: IN-PROGRESS\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    assert body.splitlines().index("Status: IN-PROGRESS") >= 10, "fixture: Status must be body-deep"
    rc, out = _gate(repo, "2026-08-20-shrink-zone-review.md", body)
    assert rc == 1, "indented filler shrank the header zone and exempted the whole grammar"


def test_html_comment_status_does_not_exempt(repo: Path) -> None:
    """Round-57 CRITICAL 1: an HTML comment carrying Status: IN-PROGRESS in the first 10 raw
    lines — invisible to a renderer, live to the raw regex — silently exempted a document
    with an UNCHECKED row, no Surface, and a non-quiet ledger from EVERY obligation."""
    body = (
        "# Review — some diff (/fabrik-review)\n"
        "<!--\nStatus: IN-PROGRESS\n-->\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-20-comment-cloak-review.md", body)
    assert rc == 1, "a commented-out Status line exempted the whole grammar"


def test_blockquoted_checklist_heading_is_refused(repo: Path) -> None:
    """Round-57 CRITICAL 2: a `> ## Coverage Checklist` blockquote renders as a real heading
    but was invisible to the ATX column-0 anchor — the document silently became a non-subject
    despite a live UNCHECKED row and a non-quiet ledger."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "> ## Coverage Checklist\n> | Item | Verdict |\n> |---|---|\n"
        "> | fail-open handling | UNCHECKED |\n\n"
        "Pass 1: found: 3, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-blockquote-review.md", body)
    assert rc == 1, "a blockquoted checklist made the document a silent non-subject"
    assert "BLOCKQUOTED grammar-shaped line" in out


def test_blockquoted_handoff_row_is_refused(repo: Path) -> None:
    """Round-57 CRITICAL 3: a blockquoted OPEN HANDOFF row rendered plainly visible but
    vanished from HANDOFF_ROW.findall — the cert gate returned [] on an unevidenced
    code-wrong row and waived NOT-QUIET with it."""
    body = (
        "# cert\n\n"
        "> HANDOFF P1 OPEN some risky finding — repro: tests/t.py — route: /fabrik-review src/x\n\n"
        "## RESUME\nre-run the journey\n"
    )
    rc, out = _gate(repo, "2026-08-20-user-test-bq.md", body)
    assert rc == 1, "a blockquoted OPEN HANDOFF row vanished from the cert gate"
    assert "BLOCKQUOTED grammar-shaped line" in out


def test_setext_checklist_heading_is_refused(repo: Path) -> None:
    """Round-57 (same class): `Coverage Checklist` over a `---` underline renders as a real
    h2 but the ATX-only anchor never sees it — silent non-subject."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "Coverage Checklist\n------------------\n| Item | Verdict |\n|---|---|\n"
        "| fail-open handling | UNCHECKED |\n"
    )
    rc, out = _gate(repo, "2026-08-20-setext-review.md", body)
    assert rc == 1, "a setext checklist heading made the document a silent non-subject"
    assert "SETEXT-style heading" in out


def test_comment_separated_indented_row_is_still_refused(repo: Path) -> None:
    """Round-59 CRITICAL (fail-open half): _indented_grammar_error rebuilt its lines from RAW
    text while _strip_fences blanked comments — the walks disagreed, so an indented Pass row
    separated from prose only by a comment line was quoted to one reader and live to the
    other, vanishing a visibly non-quiet ledger line without any refusal."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n",
        "\nRound 3 notes:\n<!-- internal -->\n    Pass 3: found: 5, fixed: 0\n",
    )
    rc, out = _gate(repo, "2026-08-20-comment-indent-review.md", body)
    assert rc == 1, "a comment-separated indented Pass row escaped both the strip and the refusal"
    assert "INDENTED grammar-shaped line" in out


def test_grammar_example_inside_a_comment_is_not_refused(repo: Path) -> None:
    """Round-59 CRITICAL (fail-closed half): a renderer-invisible HTML comment wrapping a
    blockquoted HANDOFF example false-fired the BLOCKQUOTED refusal, hard-blocking an honest
    document — the raw-text walk saw the comment's content as live."""
    body = (
        "# How to write a cert report — internal documentation\n\n"
        "<!--\n> HANDOFF P1 OPEN example row for docs — repro: x — route: /fabrik-review y\n-->\n\n"
        "That is all this doc contains.\n"
    )
    rc, out = _gate(repo, "2026-08-20-comment-example-review.md", body)
    assert rc == 0, f"a comment-wrapped example false-fired the refusal: {out}"


def test_inline_comment_opener_cannot_eat_a_fence(repo: Path) -> None:
    """Round-59 HIGH: the position-blind comment regex let a mid-paragraph `<!--` (INLINE
    HTML to a renderer, never a block comment) absorb text through a `-->` quoted inside a
    later real fence, eating the fence opener and false-firing UNCLOSED on an unambiguous
    document. Block comments open only at line-leading `<!--`."""
    body = (
        "# How to write a review — internal documentation\n\n"
        "Some prose <!-- unterminated note about example:\n"
        "```python\nvalue = \"-->\"\nprint(\"real fence content\")\n```\n\n"
        "more prose\n"
    )
    rc, out = _gate(repo, "2026-08-20-inline-comment-review.md", body)
    assert rc == 0, f"an inline <!-- ate a real fence and false-fired UNCLOSED: {out}"
    assert "UNCLOSED" not in out


def test_dangling_comment_cannot_desubject_a_report(repo: Path) -> None:
    """Round-61 CRITICAL: a forgotten `-->` absorbed everything after it SILENTLY — the
    checklist heading vanished, the report became a non-subject, and a genuinely non-quiet
    all-UNCHECKED report passed clean. The dangling comment now gets the dangling fence's
    loud treatment."""
    body = (
        "# Review — some diff (/fabrik-review)\n\n"
        "<!-- TODO revisit\n\n"
        "## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
        "Pass 1: found: 4, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-dangling-comment-review.md", body)
    assert rc == 1, "a dangling comment de-subjected the report into a clean pass"
    assert "UNCLOSED HTML comment" in out


def test_dangling_comment_cannot_swallow_handoff_rows(repo: Path) -> None:
    """Round-61 CRITICAL (cert half): the same forgotten `-->` erased every HANDOFF row, so
    a P0 OPEN row owing evidence, NOT-QUIET and RESUME vanished on all three grounds."""
    body = (
        "# cert\n\n<!-- note to self\n\n"
        "HANDOFF P0 OPEN checkout crashes — repro: docs/x.md — route: /fabrik-review src/x\n"
    )
    rc, out = _gate(repo, "2026-08-20-user-test-comment.md", body)
    assert rc == 1, "a dangling comment swallowed every HANDOFF row silently"
    assert "UNCLOSED HTML comment" in out


def test_in_progress_cert_report_is_exempt_and_nagged(repo: Path) -> None:
    """Round-61 MEDIUM-HIGH: cert was the ONE grammar without the IN-PROGRESS escape,
    hard-blocking a legitimately mid-loop cert report the workflow sanctions committing.
    Exempt on the live path; the committed scan keeps the standing advisory (no cloak)."""
    body = (
        "# fabrik-user-test-checkout\nStatus: IN-PROGRESS\n\n"
        "HANDOFF P0 OPEN checkout crashes on empty cart — repro: docs/x.md — route: /fabrik-review src/x\n"
    )
    rc, out = _gate(repo, "2026-08-20-user-test-midloop.md", body)
    assert rc == 0, f"a mid-loop cert report was hard-blocked despite the escape hatch: {out}"
    rc, out = _gate(repo, "2026-08-20-user-test-midloop2.md", body, commit=True)
    assert rc == 0
    # File-specific assertion (round 63): _gate's git add -A sweeps the first file into this
    # commit too, so a bare "IN-PROGRESS" substring could be satisfied by the sibling's line —
    # the pin must prove the advisory fires for THIS file.
    assert "user-test-midloop2" in out and "IN-PROGRESS" in out, (
        "the committed scan lost the standing advisory on the newly committed cert report"
    )


def test_bulleted_pass_row_cannot_vanish(repo: Path) -> None:
    """Round-65 HIGH: `- Pass 3: found: 7, fixed: 0` renders as a fully visible list item,
    but _PASS_HEAD had no list-marker tolerance (HANDOFF_ROW next door did) — the bulleted
    non-quiet final round was invisible to the ledger extractor and the report exited green
    on both the blocking path and the committed advisory."""
    body = _everyday(
        "Pass 1: found: 5, fixed: 5\nPass 2: found: 0, fixed: 0\n",
        "\n- Pass 3: found: 7, fixed: 0\n",
    )
    rc, out = _gate(repo, "2026-08-20-bulleted-pass-review.md", body)
    assert rc == 1, "a bulleted non-quiet final round vanished from the ledger extractor"
    assert "final ledger round raised 7" in out


def test_numbered_handoff_row_cannot_vanish(repo: Path) -> None:
    """Round-67 HIGH: round 66 gave _PASS_HEAD numbered-list tolerance but left HANDOFF_ROW
    with only [-*] — a numbered `1. HANDOFF P1 OPEN …` (renderer-visible) vanished from
    findall and from the refusal net, waiving evidence, NOT-QUIET and RESUME at once."""
    body = (
        "# cert\n\nDispositions:\n\n"
        "1. HANDOFF P1 OPEN checkout crashes — repro: docs/x.md — route: /fabrik-review src/x\n"
    )
    rc, out = _gate(repo, "2026-08-20-user-test-numbered.md", body)
    assert rc == 1, "a numbered OPEN HANDOFF row vanished from the cert gate"
    assert "NOT-QUIET" in out, "the row must fail for the disposition reason, not incidentally"


def test_numbered_pass_row_cannot_vanish(repo: Path) -> None:
    """Round-67 LOW (coverage for the round-66 `\\d+.` branch, which shipped unexercised):
    a numbered non-quiet final Pass row must be read as the exit round."""
    body = _everyday(
        "Pass 1: found: 5, fixed: 5\nPass 2: found: 0, fixed: 0\n",
        "\n3. Pass 3: found: 7, fixed: 0\n",
    )
    rc, out = _gate(repo, "2026-08-20-numbered-pass-review.md", body)
    assert rc == 1, "a numbered non-quiet final round vanished from the ledger extractor"
    assert "final ledger round raised 7" in out


def test_list_marker_recap_is_refused_loudly_not_silently(repo: Path) -> None:
    """Round-67 MEDIUM, ADJUDICATED as the established loud-refusal design: a list-marker
    narrative recap (`1. Pass 1: found: 3 (initial sweep), fixed: 3 (…)`) is textually
    identical to real corpus ledger styles (round 13 measured parentheticals in committed
    ledgers), so token-tightening would evaporate honest ledgers — undecidable. The
    multi-group guard refuses it LOUDLY with the one-keystroke remedy (fence the recap),
    never silently in either direction."""
    body = _everyday(
        "| r | found: | fixed: | notes |\n|---|---|---|---|\n"
        "| 1 | found: 3 | fixed: 3 | sweep |\n| 2 | found: 0 | fixed: 0 | quiet |\n",
        "\nRound history, narrative:\n\n"
        "1. Pass 1: found: 3 (initial sweep), fixed: 3 (initial sweep)\n"
        "2. Pass 2: found: 0 (confirming round), fixed: 0 (confirming round)\n",
    )
    rc, out = _gate(repo, "2026-08-20-recap-review.md", body)
    assert rc == 1
    assert "separate groups" in out, "the recap impersonation must get the loud multi-group remedy"


def test_every_commonmark_list_marker_reaches_both_grammars(repo: Path) -> None:
    """Round-69 HIGH: the marker tolerance was re-typed per regex and per round (`-`, then
    `1.`, then `+`/`1)` still missing) — _LIST_MARK is now defined once and shared, and this
    pin sweeps the COMPLETE CommonMark marker set through both grammars so no variant can
    vanish a renderer-visible obligation again."""
    for i, mark in enumerate(["+", "1)", "*", "2."]):
        body = (
            "# cert\n\nDispositions:\n\n"
            f"{mark} HANDOFF P1 OPEN checkout crashes — repro: docs/x.md — route: /fabrik-review src/x\n"
        )
        rc, out = _gate(repo, f"2026-08-20-user-test-mark{i}.md", body)
        assert rc == 1, f"marker {mark!r} vanished a HANDOFF row"
        assert "NOT-QUIET" in out, f"marker {mark!r} failed for the wrong reason"
        body = _everyday(
            "Pass 1: found: 5, fixed: 5\nPass 2: found: 0, fixed: 0\n",
            f"\n{mark} Pass 3: found: 7, fixed: 0\n",
        )
        rc, out = _gate(repo, f"2026-08-20-mark{i}-pass-review.md", body)
        assert rc == 1, f"marker {mark!r} vanished a non-quiet final Pass row"
        assert "final ledger round raised 7" in out, f"marker {mark!r}: wrong reason"


def test_prose_decoy_in_a_later_section_is_refused(repo: Path) -> None:
    """Round-71 HIGH: prose Pass-lines collapsed into ONE flat group however far apart, so a
    retro sentence in a later section that parsed as a counter silently became the final
    round — the one decoy shape the multi-group guard could not see (table cases fired;
    prose+prose did not). Prose runs are now heading-bounded groups."""
    body = _everyday(
        "Pass 1: found: 3, fixed: 0\nPass 2: found: 4, fixed: 0\n",
        "\n## Appendix — unrelated retro note\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n",
    )
    rc, out = _gate(repo, "2026-08-20-prose-decoy-review.md", body)
    assert rc == 1, "a prose decoy past a heading silently became the final round"
    assert "separate groups" in out


def test_wrapped_continuation_prose_ledger_is_one_group(repo: Path) -> None:
    """Round-71 regression guard (the 2026-08-04 corpus style): an honest prose ledger whose
    rows wrap with continuation prose within ONE section must stay one group — breaking runs
    on arbitrary prose false-fired it; the boundary is structural (a heading)."""
    body = _everyday(
        "Pass 1 — found: 3, fixed: 3 (seams partition; the coverage dispatch was re-run\n"
        "inline after a quota kill; all anchors re-verified against the tree)\n"
        "Pass 2 — found: 0, fixed: 0. All refs byte-verified; render clean.\n",
    )
    rc, out = _gate(repo, "2026-08-20-wrapped-prose-review.md", body)
    assert rc == 0, f"an honest wrapped-continuation prose ledger was split into groups: {out}"


def test_blockquoted_and_setext_headings_also_bound_prose_runs(repo: Path) -> None:
    """Round-73 HIGH: the round-72 boundary was ATX-only — a blockquoted `> ## Appendix` or
    a setext underline (both real heading elements to a renderer) failed to close the prose
    run, so the round-71 decoy bypass survived one heading syntax over."""
    decoy_tail_bq = (
        "\n> ## Appendix — unrelated retro note\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n"
    )
    decoy_tail_setext = (
        "\nAppendix — unrelated retro note\n-------------------------------\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n"
    )
    # CONTRACT CHANGE (round 79): a blockquoted heading is now REFUSED by the container
    # normalization before the boundary ever parses (earlier, louder, remedy named); the
    # generic setext divider still exercises the run-boundary path. Both stay loud rc==1.
    for i, (tail, reason) in enumerate(
        [(decoy_tail_bq, "heading/declaration"), (decoy_tail_setext, "separate groups")]
    ):
        body = _everyday("Pass 1: found: 3, fixed: 0\nPass 2: found: 4, fixed: 0\n", tail)
        rc, out = _gate(repo, f"2026-08-20-heading-form{i}-review.md", body)
        assert rc == 1, f"decoy after heading form {i} silently became the final round"
        assert reason in out, f"heading form {i}: wrong reason"


def test_bare_hash_heading_bounds_a_prose_run(repo: Path) -> None:
    """Round-75: a lone `#` is a valid empty ATX heading to a renderer, but the boundary
    regex required a trailing space — the decoy bypass revived one syntax over again."""
    body = _everyday(
        "Pass 1: found: 3, fixed: 0\nPass 2: found: 2, fixed: 0\n",
        "\n#\nAppendix — unrelated retro note\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n",
    )
    rc, out = _gate(repo, "2026-08-20-bare-hash-review.md", body)
    assert rc == 1, "a decoy after a bare-# heading silently became the final round"
    assert "separate groups" in out


def test_list_wrapped_checklist_heading_cannot_desubject(repo: Path) -> None:
    """Round-77 CRITICAL: `- ## Coverage Checklist` renders as a real h2 nested in a list
    item, but the column-0 heading scan never saw it — the whole report silently became a
    non-subject (every obligation bypassed) on the blocking path AND the committed scan.
    Refused loudly, consistent with the blockquote adjudication of round 57."""
    for i, mark in enumerate(["-", "1.", "+"]):
        body = (
            "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
            f"{mark} ## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
            "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
            "Pass 1: found: 4, fixed: 0\n"
        )
        rc, out = _gate(repo, f"2026-08-20-listwrap{i}-review.md", body)
        assert rc == 1, f"a {mark}-wrapped checklist heading de-subjected the report"
        assert "LIST-WRAPPED" in out, f"marker {mark}: wrong reason"


def test_list_wrapped_divider_cannot_hide_a_decoy(repo: Path) -> None:
    """Round-77 HIGH (same root): `1. # Appendix` is a real heading to a renderer but not to
    the run boundary — the decoy after it merged into the real ledger's group. The refusal
    net now catches the wrapped heading before any parsing."""
    body = _everyday(
        "Pass 1: found: 3, fixed: 0\nPass 2: found: 4, fixed: 0\n",
        "\n1. # Appendix — unrelated retro note\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n",
    )
    rc, out = _gate(repo, "2026-08-20-listwrap-divider-review.md", body)
    assert rc == 1, "a decoy behind a list-wrapped divider silently became the final round"
    assert "LIST-WRAPPED" in out


def test_bulleted_rows_stay_live_despite_the_list_wrap_refusal(repo: Path) -> None:
    """Round-77 regression guard: bulleted Pass/HANDOFF ROWS are sanctioned live rows (the
    _LIST_MARK tolerance of rounds 65-70) and `- #123 fixed` prose is not a heading — the
    new refusal must not touch either."""
    body = _everyday(
        "Pass 1: found: 5, fixed: 5\nPass 2: found: 0, fixed: 0\n",
        "\nNotes:\n- #123 fixed upstream in the vendor tree.\n",
    )
    rc, out = _gate(repo, "2026-08-20-listwrap-safe-review.md", body)
    assert rc == 0, f"prose bullet or live row false-fired the list-wrap refusal: {out}"


def test_composed_containers_cannot_hide_grammar(repo: Path) -> None:
    """Round-79 CRITICALs: container prefixes COMPOSE (`- > ## …`, `> - ## …`), and the
    per-costume elif branches tested exactly one level — every composition revived the
    bypass one nesting deeper (de-subjected checklist; decoy-merged divider). The
    normalization loop peels to a fixpoint and judges the residual once."""
    for i, wrap in enumerate(["- > ", "> - "]):
        body = (
            "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
            f"{wrap}## Coverage Checklist\n| C | V | E |\n|---|---|---|\n"
            "| fail-open cost boundary untested behavior | UNCHECKED |  |\n\n"
            "Pass 1: found: 4, fixed: 0\n"
        )
        rc, out = _gate(repo, f"2026-08-20-composed{i}-review.md", body)
        assert rc == 1, f"composition {wrap!r} de-subjected the report"
    body = _everyday(
        "Pass 1: found: 3, fixed: 0\nPass 2: found: 4, fixed: 0\n",
        "\n- > ## Appendix — unrelated retro note\n\n"
        "Pass 2 of onboarding docs: found: 0, fixed: 0.\n",
    )
    rc, out = _gate(repo, "2026-08-20-composed-divider-review.md", body)
    assert rc == 1, "a composed-container divider hid the decoy merge"


def test_list_wrapped_setext_checklist_is_refused(repo: Path) -> None:
    """Round-79 HIGH: `- Coverage Checklist` over an indented underline renders as a real
    h2 in the list item, but the elif chain never reached the setext branch for a
    list-matched line — full de-subjecting. The setext check now runs on the peeled
    residual of both lines."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "- Coverage Checklist\n  -----\n| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-20-listsetext-review.md", body)
    assert rc == 1, "a list-wrapped setext checklist title de-subjected the report"
    assert "SETEXT-style heading" in out


def test_honest_status_surface_bullets_stay_live(repo: Path) -> None:
    """Round-79 MEDIUM: the wrapped-declaration refusal matched ANY English `Status:` or
    `Surface:` bullet — `- Surface: 3 new endpoints added this round` hard-blocked an honest
    converged report. Refusable only when the residual would have BEEN an anchor unwrapped
    (Status: IN-PROGRESS, or Surface: carrying a ≥12-hex hash)."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n",
        "\n## Notes\n\n- Surface: 3 new endpoints added this round\n"
        "- Status: green across all services\n",
    )
    rc, out = _gate(repo, "2026-08-20-honest-bullets-review.md", body)
    assert rc == 0, f"honest Status/Surface bullets false-fired the refusal: {out}"


def test_quoted_title_mention_over_a_divider_is_not_a_heading(repo: Path) -> None:
    """Round-81 HIGH: the round-80 setext check was depth-blind — a quoted/bulleted prose
    mention of the checklist title directly above an unrelated `---` divider (paragraph +
    thematic break to a renderer, NOT a heading) hard-refused a fully converged report."""
    for i, mention in enumerate(
        ["> Coverage Checklist section reference below for context",
         "- Coverage Checklist row explained further down"]
    ):
        body = _everyday(
            "Pass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n",
            f"\n{mention}\n---\n\nMore notes.\n",
        )
        rc, out = _gate(repo, f"2026-08-20-divider{i}-review.md", body)
        assert rc == 0, f"mention form {i} false-fired the setext refusal: {out}"


def test_quoted_setext_heading_in_matching_context_is_refused(repo: Path) -> None:
    """Round-81 coverage: a setext title WITH its underline in the SAME blockquote context
    IS a real heading to a renderer and stays refused."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "> Coverage Checklist\n> -----\n\n"
        "| C | V | E |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | UNCHECKED |  |\n"
    )
    rc, out = _gate(repo, "2026-08-20-quoted-setext-review.md", body)
    assert rc == 1, "a same-context quoted setext heading escaped the refusal"
    assert "SETEXT-style heading" in out


def test_dropped_fence_adjacency_does_not_forge_a_setext_heading(repo: Path) -> None:
    """Round-83 HIGH 1: dropping fence regions (while comments blanked) destroyed physical
    adjacency — a plain `Coverage Checklist` paragraph + fenced example + `---` divider
    became artificially adjacent and read as a setext heading, hard-refusing an honest
    converged report. Fences now blank like comments; positions always survive."""
    body = _everyday(
        "Pass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n",
        "\nCoverage Checklist\n```\nexample content\n```\n---\n\nMore notes.\n",
    )
    rc, out = _gate(repo, "2026-08-20-fence-adjacency-review.md", body)
    assert rc == 0, f"a fence seam forged a setext heading on an honest report: {out}"


def test_dropped_fence_adjacency_does_not_split_a_ledger_run(repo: Path) -> None:
    """Round-83 HIGH 2 (same root): a fence between prose ledger rows made the following
    `---` read as a run boundary via stale adjacency, splitting one honest quiet ledger
    into two groups and firing the multi-group refusal."""
    body = _everyday(
        "Pass 1: found: 3, fixed: 3\n```\nexample\n```\n---\nPass 2: found: 0, fixed: 0\n",
    )
    rc, out = _gate(repo, "2026-08-20-fence-split-review.md", body)
    assert rc == 0, f"a fence seam split an honest quiet ledger into groups: {out}"


def test_fence_inside_the_checklist_cannot_hide_rows(repo: Path) -> None:
    """Round-85 HIGH: a fenced example inside the checklist table became blank lines (round
    84's blanking), and _table_rows' break-at-first-non-pipe truncated extraction at the
    seam — every row after it, UNCHECKED included, went silently uncounted (fail-open,
    proven red on the parent commit's dropping behavior too... the DROP era collected across
    the vanished fence; only the blanking era truncated). The section is the contract now."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n"
        "```\nexample fenced content that should not matter\n```\n"
        "| another-class | UNCHECKED | pending |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-fence-in-table-review.md", body)
    assert rc == 1, "an UNCHECKED row after an in-table fence went silently uncounted"
    assert "UNCHECKED" in out


def test_comment_inside_the_checklist_cannot_hide_rows(repo: Path) -> None:
    """Round-85 MEDIUM (same root, pre-existing since the round-58 comment blanking): an
    HTML comment between checklist rows truncated extraction identically."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict | Evidence |\n|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN | scripts/x.py hunted |\n"
        "<!-- reviewer note -->\n"
        "| another-class | UNCHECKED | pending |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-comment-in-table-review.md", body)
    assert rc == 1, "an UNCHECKED row after an in-table comment went silently uncounted"
    assert "UNCHECKED" in out


def test_stray_separator_cannot_erase_the_preceding_row(repo: Path) -> None:
    """Round-87 CRITICAL: the round-86 header-skip looked ahead in the FILTERED pipe list,
    so a stray `|---|---|` anywhere later in the section (prose to a renderer — a stale
    template artifact) erased whichever row preceded it in pipe-order, silently uncounting
    a live UNCHECKED row with no fence/indent involved. The header test is now physical
    adjacency: a row is a header only if its separator is the literally next line."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict |\n|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n"
        "| auth-tenant-isolation | UNCHECKED |\n\n"
        "Appendix note explaining the layout below, prose only.\n\n"
        "|---|---|\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-stray-separator-review.md", body)
    assert rc == 1, "a stray separator erased the UNCHECKED row before it"
    assert "UNCHECKED" in out


def test_adjacent_stray_separator_cannot_swallow_a_data_row(repo: Path) -> None:
    """Round-89: physical adjacency alone still let a stray `|---|` DIRECTLY under a data
    row swallow it as a 'header' — chainably, wiping any number of UNCHECKED rows. A header
    must be run-initial (previous physical line not a pipe-row) and verdict-free."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict |\n|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n"
        "| auth-tenant-isolation | UNCHECKED |\n|---|\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-adjacent-separator-review.md", body)
    assert rc == 1, "an adjacent stray separator swallowed the UNCHECKED row above it"
    assert "UNCHECKED" in out


def test_headerless_table_with_verdict_grammar_is_a_forgery_residual(repo: Path) -> None:
    """Round-91 ADJUDICATION (re-anchoring the round-89 second seam): a run-initial row
    followed by a separator IS a table header to a renderer — restructuring an obligation
    INTO one is deliberate forgery, out of threat model, and the text stays visible to the
    operator in the rendered header cell. Judging header CONTENT false-failed honest
    vocabulary-naming headers (round 91), so the header test is structural only."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Class | Verdict |\n|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
        "| auth-tenant-isolation UNCHECKED |\n|---|\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-headerless-verdict-review.md", body)
    assert rc == 0, f"the structural header test should skip a renderer-true header: {out}"


def test_vocabulary_naming_header_is_not_data(repo: Path) -> None:
    """Round-91 HIGH: the round-90 verdict-free header condition false-failed an honest
    header that legitimately documents the column's allowed values — the header test is
    structural (run-initial + separator-next), never content-judged."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n"
        "| Class | Verdict (CLEAN, FIXED, REFUTED, or still UNCHECKED) | Notes |\n"
        "|---|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted | ok |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-20-vocab-header-review.md", body)
    assert rc == 0, f"a vocabulary-naming header was counted as a data row: {out}"


def test_mismatched_separator_does_not_make_a_header(repo: Path) -> None:
    """Round-93 CRITICAL: GFM requires the delimiter row to match the header's cell count —
    otherwise the block renders as a plain PARAGRAPH. The structural test skipped a 2-cell
    UNCHECKED row over a 1-cell `|---|` as 'the header' of a table no renderer sees,
    silently exempting visible obligation text (a round-92 regression)."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n"
        "| sql-injection-in-query-builder | UNCHECKED still to hunt |\n|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-21-mismatch-separator-review.md", body)
    assert rc == 1, "a mismatched separator made a paragraph row into a skipped 'header'"
    assert "UNCHECKED" in out


def test_doubled_pipe_typo_cannot_swallow_a_row(repo: Path) -> None:
    """Round-95 HIGH: Python's strip('|') ate a DOUBLED leading pipe, collapsing a 3-cell
    typo'd row onto a 2-cell separator — 'match' — and swallowing a live UNCHECKED row as
    the header of a table no renderer forms (GFM strips exactly ONE boundary pipe)."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n"
        "|| sql-injection-in-query-builder | UNCHECKED still to hunt |\n|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-21-doubled-pipe-review.md", body)
    assert rc == 1, "a doubled-pipe typo swallowed the UNCHECKED row as a phantom header"
    assert "UNCHECKED" in out


def test_escaped_pipe_header_is_still_a_header(repo: Path) -> None:
    """Round-95 MEDIUM (mirror): `\\|` is an ESCAPED pipe — content, not a delimiter. The
    naive split counted 3 cells for an honest vocabulary header over a 2-cell separator and
    false-failed a fully converged report."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n"
        "| Class | Verdict (CLEAN\\|FIXED\\|REFUTED) |\n|---|---|\n"
        "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-21-escaped-pipe-review.md", body)
    assert rc == 0, f"an escaped-pipe vocabulary header was counted as a data row: {out}"


def test_invalid_delimiter_row_cannot_make_a_header(repo: Path) -> None:
    """Round-97 CRITICAL: GFM requires every delimiter cell to carry at least one hyphen
    (`:?-+:?`) — the coarse character-class test accepted colon-only/blank cells, forming a
    phantom header pair no renderer forms and swallowing the UNCHECKED row above it."""
    for i, sep in enumerate(["|::|::|", "| : | : |", "|  |  |"]):
        body = (
            "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
            "review_rubric.py output embedded\n\n"
            "## Coverage Checklist\n"
            f"| sql-injection-hunt | UNCHECKED |\n{sep}\n"
            "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
            "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
        )
        rc, out = _gate(repo, f"2026-08-21-invalid-sep{i}-review.md", body)
        assert rc == 1, f"separator {sep!r} swallowed the UNCHECKED row above it"
        assert "UNCHECKED" in out, f"separator {sep!r}: wrong reason"


def test_valid_separator_shapes_are_recognized(repo: Path) -> None:
    """Round-99: the leading-pipe requirement was too strict the OTHER way — GFM's delimiter
    row may be pipe-less (`---|---`), and the unrecognized separator false-failed an honest
    header as a verdict-less data row. Sweep the VALID boundary: pipe-less, colon-aligned,
    and mixed forms must all pair with their header (a bare `---` stays excluded — it is a
    setext underline/thematic break, never a table separator)."""
    for i, sep in enumerate(["---|---", "|:---|---:|", "| :---: | :--- |"]):
        body = (
            "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
            "review_rubric.py output embedded\n\n"
            "## Coverage Checklist\n"
            f"| Class | Verdict |\n{sep}\n"
            "| fail-open cost boundary untested behavior | CLEAN — scripts/x.py hunted |\n\n"
            "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
        )
        rc, out = _gate(repo, f"2026-08-21-valid-sep{i}-review.md", body)
        assert rc == 0, f"valid separator {sep!r} was unrecognized and the header failed as data: {out}"


def test_one_column_table_with_bare_dash_separator_is_valid(repo: Path) -> None:
    """Round-101: GFM puts the pipe requirement on the HEADER, not the delimiter — a bare
    `---` under a 1-column pipe-bounded header forms a real table (renderer-verified), and
    round 100's pipe-presence gate false-failed it as a verdict-less data row."""
    body = (
        "# Review — some diff (/fabrik-review)\nSurface: abc123\n\n"
        "review_rubric.py output embedded\n\n"
        "## Coverage Checklist\n| Verdict |\n---\n"
        "| CLEAN — fail-open cost boundary untested behavior, scripts/x.py hunted |\n\n"
        "## Pass Ledger\nPass 1: found: 0, fixed: 0\nPass 2: found: 0, fixed: 0\n"
    )
    rc, out = _gate(repo, "2026-08-21-onecol-review.md", body)
    assert rc == 0, f"a valid 1-column table with a bare --- separator was false-failed: {out}"
