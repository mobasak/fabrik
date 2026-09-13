# AFTER-EDIT: scripts/enforcement/check_review_hygiene.py
"""Behavior contract for the advisory review-hygiene sweep (T08, review-convergence redesign).

The receipt fixtures are fetched with ``git show <sha>:<path>`` into ``tmp_path`` — never a
tracked-path grep, because the working tree's copy of the D-191 receipt moves under the plan and a
tracked read would grade a different artifact every round. Every object is skipped-with-a-reason
when absent (a shallow clone).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/enforcement/check_review_hygiene.py"
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_review_hygiene as crh  # noqa: E402

RECEIPT = "docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md"
SHA_741 = "741eebbf"  # round 12: F280's unescaped mid-cell pipe is live, F314 does not exist yet
SHA_69 = "69f01b92"  # round 16: F280 is escaped, F314's dual-verdict cell stands at :670
CORPUS_SHA = "8092e8a8"  # the plan's base — the 275 committed receipts the fire rate is measured on


def _show(sha: str, path: str) -> str | None:
    probe = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return subprocess.run(
        ["git", "-C", str(REPO), "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _fixture(tmp_path: Path, sha: str) -> Path:
    text = _show(sha, RECEIPT)
    if text is None:
        pytest.skip(
            f"object {sha}:{RECEIPT} absent from this clone (shallow) — fixture unfetchable"
        )
    p = tmp_path / f"{sha}-receipt.md"
    p.write_text(text, encoding="utf-8")
    return p


def _lines(sweep, cls: str) -> list[int]:
    return sorted(h.line for h in sweep.hits if h.cls == cls)


# ---------------------------------------------------------------- the receipt row-shape classes


def test_the_dual_verdict_class_counts_bare_verdict_words(tmp_path):
    """The seam with T02 (spine § Interfaces): the class counts BARE verdict WORDS per cell, not
    ``VERDICT`` matches — F314's cell (`RECORDED — the F250 shape …`) carries RECORDED twice and
    matches T02's widened ``VERDICT`` zero times, so a VERDICT-based detector is blind to it.

    ⚠️ The set is FIVE rows, not the six the ticket froze. Round 1 CONFIRMED the receipt's own
    remediation row (`:694` — `FIXED — one leading verdict per cell; … the round-14 tally reads
    FIXED 12 · RECORDED 2`) as a false positive: its only extra verdict words are TALLY references,
    and `_verdict_words` now drops a verdict word adjacent to a digit. F314 at `:670` — the row the
    § Interfaces seam names — is untouched by that rule and still fires.
    """
    receipt = _fixture(tmp_path, SHA_69)
    sweep = crh.scan(receipts=[receipt])
    lines = _lines(sweep, "dual-verdict")
    print(f"dual-verdict hits at {SHA_69}: {len(lines)} rows -> {lines}")
    assert lines == [419, 540, 649, 670, 683]
    # the F314 cell itself: two bare RECORDED, zero VERDICT matches
    cell = receipt.read_text(encoding="utf-8").splitlines()[669]
    from check_review_coverage import VERDICT  # noqa: PLC0415 — the T02 grammar, read not copied

    assert cell.count("RECORDED") == 2
    assert VERDICT.search(cell) is None


def test_a_tally_reference_is_not_a_second_disposition(tmp_path):
    """A TALLY is the verdict word FOLLOWED by a BOUNDED count — `reads FIXED 12 · RECORDED 2`.

    Structural (the word, then a short number that ends there), never a phrase list. ⚠️ A LEADING
    count fires BY DESIGN: the shipped code returns `['FIXED', 'REFUTED']` for `6 FIXED · 1
    REFUTED`, because nothing structural separates it from two dispositions written side by side —
    the stated cost, adjudicated `RECORDED — hygiene false positive (…)`. (This docstring carried
    round 1's superseded "a digit on either side" rule for two rounds, and claimed the opposite of
    what the code does — a comment stating a rule is a claim.)
    """
    assert crh._verdict_words("FIXED — moved; the spans REFUTED again") == ["FIXED", "REFUTED"]
    assert crh._verdict_words("FIXED — one per cell; the tally reads FIXED 12 · RECORDED 2") == [
        "FIXED"
    ]
    # A digit BEFORE the word is a finding id or a round number, NEVER a tally — a symmetric
    # adjacency rule dropped all three of these, two of them silently halving a real cell.
    assert crh._verdict_words("F280 FIXED — escaped the pipe") == ["FIXED"]
    assert crh._verdict_words("round 14 FIXED; round 15 REFUTED") == ["FIXED", "REFUTED"]
    assert crh._verdict_words("RECORDED — the 2 RECORDED rows above") == ["RECORDED", "RECORDED"]
    # A long token after the word is a DATE or an ID, not a count — an unbounded `\d` ate both,
    # and every hub mail id starts `01M`, so `ROUTED 01M…` lost its whole disposition.
    assert crh._verdict_words("FIXED 2026-09-09") == ["FIXED"]
    assert crh._verdict_words("ROUTED 01M1K6A15M to infra; the rest FIXED") == ["ROUTED", "FIXED"]
    assert crh._verdict_words("FIXED 2026-09-09 · REFUTED 2026-09-10") == ["FIXED", "REFUTED"]
    assert crh._verdict_words("RECORDED 2026-09-09; RECORDED 2026-09-08") == [
        "RECORDED",
        "RECORDED",
    ]
    # …and the bounded count still suppresses
    assert crh._verdict_words("the tally reads FIXED 12 and RECORDED 2") == []
    # STATED COST (b): PUNCTUATION between the word and the number is not a tally to this rule —
    # `<word> — <text>` is exactly how an honest single disposition is written, so the leading
    # `FIXED — 12 rows` survives while the trailing `FIXED 12` is dropped.
    assert crh._verdict_words("FIXED — 12 rows; the tally reads FIXED 12") == ["FIXED"]


def test_the_raw_pipe_class_fires_on_f280_before_it_was_escaped(tmp_path):
    receipt = _fixture(tmp_path, SHA_741)
    sweep = crh.scan(receipts=[receipt])
    assert _lines(sweep, "raw-pipe") == [596]
    # F280's row is not ALSO a dual-verdict hit — a row whose cells do not line up with its header
    # has no trustworthy disposition cell, so it is reported once and not graded twice.
    assert 596 not in _lines(sweep, "dual-verdict")


def test_the_raw_pipe_class_is_silent_once_the_pipe_is_escaped(tmp_path):
    receipt = _fixture(tmp_path, SHA_69)
    assert _lines(crh.scan(receipts=[receipt]), "raw-pipe") == []


def test_a_short_row_is_named_a_missing_cell_not_an_unescaped_pipe(tmp_path):
    """15 of the corpus raw-pipe hits are rows with FEWER cells than the header. Telling their
    author to escape a pipe they never wrote is a fabricated remedy."""
    receipt = tmp_path / "short-review.md"
    receipt.write_text(
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F1 | shape | a row missing its last cell |\n"
        "| F2 | shape | a row | with | one pipe too many |\n",
        encoding="utf-8",
    )
    whats = {h.line: h.what for h in crh.scan(receipts=[receipt]).hits if h.cls == "raw-pipe"}
    assert "MISSING cell" in whats[3]
    assert "unescaped `|`" in whats[4]


def test_a_row_quoted_inside_a_fence_is_not_graded(tmp_path):
    """A receipt quotes the very row it fixed. Grading the quotation fires the class on the fix."""
    receipt = tmp_path / "quoting-review.md"
    receipt.write_text(
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F1 | shape | fixed the row below | FIXED — escaped |\n"
        "\n"
        "```text\n"
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F0 | shape | the broken row | with | a stray pipe |\n"
        "```\n",
        encoding="utf-8",
    )
    sweep = crh.scan(receipts=[receipt])
    assert sweep.hits == []


def test_a_clean_synthetic_receipt_yields_no_hits(tmp_path):
    receipt = tmp_path / "clean-review.md"
    receipt.write_text(
        "# Review\n\n"
        "## Coverage Checklist\n\n"
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F1 | shape | a row | FIXED — the fix |\n"
        "| F2 | shape | another `a \\| b` row | REFUTED |\n",
        encoding="utf-8",
    )
    sweep = crh.scan(receipts=[receipt])
    assert sweep.hits == []
    assert sweep.files == 1
    assert sweep.ungraded == 0


def test_rows_in_a_headerless_table_are_counted_as_ungraded(tmp_path):
    """Neither class can grade a row whose table declares no header — no cell-count denominator and
    no named disposition column. A bounded search states its bound."""
    receipt = tmp_path / "headerless-review.md"
    receipt.write_text("| F1 | a row | FIXED — x |\n| F2 | a row | REFUTED |\n", encoding="utf-8")
    sweep = crh.scan(receipts=[receipt])
    assert sweep.hits == []
    assert sweep.ungraded == 2


# ---------------------------------------------------------------- the surface classes


def test_template_residue_is_reported_with_its_line(tmp_path):
    cmd = tmp_path / "fabrik-thing.md"
    cmd.write_text("# Thing\n\nrun the record: {{X}}\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[cmd]), "template-residue") == [3]


def test_template_residue_is_not_reported_in_a_command_source_tree(tmp_path):
    """`{{include:…}}` IS the authoring format under `commands/_sources` and `commands/_fragments`
    — 127 hits over 36 source files, 100 % false. Residue is a RENDERED-command defect."""
    for parent in ("_sources", "_fragments"):
        d = tmp_path / "commands" / parent
        d.mkdir(parents=True)
        src = d / "fabrik-thing.md"
        src.write_text("# Thing\n\n{{include:run-record}}\n", encoding="utf-8")
        assert _lines(crh.scan(surfaces=[src]), "template-residue") == [], parent


def test_only_the_renderers_own_tree_is_exempt_from_the_residue_class(tmp_path):
    """The exemption belongs to `commands/_sources` and `commands/_fragments` — the assembler's
    input tree. A BARE `_sources`/`_fragments` ancestor anywhere on the box silenced the whole
    class beneath it, with no NOTE: real `{{include:…}}` residue in an unrelated tree scored 0."""
    unrelated = [
        tmp_path / "fx" / "_sources" / "sub" / "rendered.md",
        tmp_path / "fx" / "_fragments" / "proj" / "docs" / "rendered.md",
    ]
    for f in unrelated:
        f.parent.mkdir(parents=True)
        f.write_text("{{include:run-record}}\n", encoding="utf-8")
        assert _lines(crh.scan(surfaces=[f]), "template-residue") == [1], f
    # the renderer's own pair stays exempt, at any depth
    exempt = tmp_path / "repo" / "commands" / "_sources" / "deep" / "fabrik-thing.md"
    exempt.parent.mkdir(parents=True)
    exempt.write_text("{{include:run-record}}\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[exempt]), "template-residue") == []


def test_a_symlink_loop_does_not_raise_out_of_the_source_tree_test(tmp_path):
    """Non-strict `Path.resolve()` raises RuntimeError — NOT OSError — on a symlink loop (3.12).
    Latent through the CLI (the existence gate fires first), but this script's contract is that no
    input reaches an uncaught raise, and a direct caller has no such gate."""
    a, b = tmp_path / "loopa", tmp_path / "loopb"
    a.symlink_to(b)
    b.symlink_to(a)
    assert crh._is_template_source(str(a / "rendered.md")) is False


def test_the_tally_rules_false_negative_shape_is_named(tmp_path):
    """STATED COST (c): the tally is DELETED before the words are counted, so a real disposition
    opening with a small count is erased with it. 0 of the 9 live tally fires at 8092e8a8 are of
    this shape, so the rule stands — the shape is PINNED so it is not rediscovered as a surprise."""
    assert crh._verdict_words("FIXED 12 of the rows and REFUTED 1") == []
    assert crh._verdict_words("RECORDED 2 as false positives; FIXED 1") == []


def test_the_source_tree_skip_survives_a_run_from_inside_the_directory(tmp_path):
    """`cd commands/_sources && … --surface .` hands over bare basenames, which carry no
    `_sources` ancestor: the same 36 files gave 127 hits from inside and 0 from the repo root."""
    d = tmp_path / "commands" / "_sources"
    d.mkdir(parents=True)
    (d / "fabrik-thing.md").write_text("{{include:run-record}}\n", encoding="utf-8")
    r = _run(["--surface", "."], d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "template-residue" not in r.stdout
    assert "hygiene: 0 hit(s) over 1 file(s), 0 rows ungraded" in r.stdout


def test_a_nonexistent_surface_path_is_noted_not_silently_dropped(tmp_path):
    """rc 0 + `0 hit(s) over 0 file(s)` for a path that never existed is byte-identical to a clean
    sweep — the same blindness the unreadable-file NOTE closes, one branch earlier."""
    sweep = crh.scan(surfaces=[tmp_path / "nope.md"], receipts=[tmp_path / "gone-review.md"])
    assert sweep.hits == []
    assert sweep.files == 0
    assert [n.split(": ", 1)[1] for n in sweep.notes] == [
        "no such path — NOT scanned, not in the denominator",
        "no such path — NOT scanned, not in the denominator",
    ]


def test_fence_parity_follows_the_commonmark_same_char_run_rule(tmp_path):
    unclosed = tmp_path / "unclosed.md"
    unclosed.write_text("intro\n\n```bash\necho hi\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[unclosed]), "fence-parity") == [3]

    nested = tmp_path / "nested.md"
    nested.write_text("intro\n\n````md\n```bash\necho hi\n```\n````\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[nested]), "fence-parity") == []


def test_a_dead_symbol_is_one_hit_and_a_live_one_is_none(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("def still_here():\n    return 1\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[src], symbols=["still_here"]), "dead-symbol") == []
    sweep = crh.scan(surfaces=[src], symbols=["long_gone"])
    assert [h.what for h in sweep.hits if h.cls == "dead-symbol"] == [
        "symbol `long_gone` is referenced 0 time(s) across 1 file(s) on the surface"
    ]


def test_a_symbol_with_no_surface_is_a_note_never_a_hit():
    """`referenced 0 time(s) across 0 file(s)` asserts a NEGATIVE with an empty denominator."""
    sweep = crh.scan(symbols=["anything"])
    assert sweep.hits == []
    assert sweep.notes == [
        "symbol `anything`: no readable file on the surface — nothing to count it in"
    ]


def test_an_unreadable_surface_file_is_noted_not_silently_dropped(tmp_path):
    """Vanishing from both the hits and the denominator makes an unreadable surface look clean."""
    gone = tmp_path / "vanished.md"
    gone.write_text("{{X}}\n", encoding="utf-8")
    sweep = crh.scan(surfaces=[gone])
    assert len(sweep.hits) == 1
    unreadable = tmp_path / "unreadable.md"
    unreadable.write_text("{{X}}\n", encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        sweep = crh.scan(surfaces=[unreadable])
    finally:
        unreadable.chmod(0o644)
    assert sweep.hits == []
    assert sweep.files == 0
    assert sweep.notes and "unreadable" in sweep.notes[0]


def test_a_stale_phrase_matches_across_a_line_wrap(tmp_path):
    doc = tmp_path / "rule.md"
    doc.write_text("a floor of three seats\nis never the answer\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[doc], phrases=["three seats is never"]), "stale-phrase") == [1]
    assert _lines(crh.scan(surfaces=[doc], phrases=["four seats is never"]), "stale-phrase") == []


def test_a_stale_phrase_matches_case_insensitively(tmp_path):
    """A brief names the phrase as prose; the surface may shout it in a heading."""
    doc = tmp_path / "rule.md"
    doc.write_text("# THE FLOOR IS THREE SEATS\n", encoding="utf-8")
    assert _lines(
        crh.scan(surfaces=[doc], phrases=["the floor is three seats"]), "stale-phrase"
    ) == [1]


def test_the_changelog_class_calls_check_changelog_quality(tmp_path):
    ch = tmp_path / "CHANGELOG.md"
    ch.write_text("# Changelog\n\n## [Unreleased]\n\nnothing structured here\n", encoding="utf-8")
    assert _lines(crh.scan(surfaces=[ch]), "changelog-entry") == [3]
    ch.write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added — a real entry (2026-09-09)\n- a thing\n",
        encoding="utf-8",
    )
    assert _lines(crh.scan(surfaces=[ch]), "changelog-entry") == []


def test_a_directory_surface_is_walked_for_md_and_py(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.md").write_text("{{RESIDUE}}\n", encoding="utf-8")
    (tmp_path / "sub" / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "sub" / "c.txt").write_text("{{IGNORED}}\n", encoding="utf-8")
    sweep = crh.scan(surfaces=[tmp_path / "sub"])
    assert _lines(sweep, "template-residue") == [1]
    assert sweep.files == 2


# ---------------------------------------------------------------- the adjudication vocabulary


def test_a_hygiene_false_positive_is_a_verdict_the_coverage_gate_accepts():
    """Behavior Contract row 4: a hit adjudicated false is RECORDED, never counted — and T02's
    widened ``VERDICT`` must accept that exact wording or the receipt row grades as `noverdict`."""
    from check_review_coverage import VERDICT  # noqa: PLC0415

    assert VERDICT.search("RECORDED — hygiene false positive (the tally, not a disposition)")
    assert VERDICT.search("| F9 | shape | x | RECORDED — hygiene false positive (quoted row) |")
    # the trailing `(` is what keeps a bare RECORDED a NON-verdict
    assert VERDICT.search("RECORDED — hygiene false positive") is None


# ---------------------------------------------------------------- the CLI contract


def _run(
    args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """PROJECT_ROOT is POPPED unless a test sets it: `final_gate.py` exports that variable to every
    check it runs, so a developer (or a gate) with it exported in the ambient shell made the CLI
    self-select against a DIFFERENT repo and these tests failed for a reason none of them named."""
    child = {k: v for k, v in os.environ.items() if k != "PROJECT_ROOT"}
    child.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=child,
    )


def test_the_cli_exits_zero_and_prints_advisory_lines_even_with_hits(tmp_path):
    doc = tmp_path / "residue.md"
    doc.write_text("{{X}}\n", encoding="utf-8")
    r = _run(["--surface", str(doc)], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[ADVISORY] template-residue" in r.stdout
    assert "hygiene: 1 hit(s) over 1 file(s), 0 rows ungraded" in r.stdout


def test_the_json_mode_emits_the_same_hits_as_a_list(tmp_path):
    doc = tmp_path / "residue.md"
    doc.write_text("{{X}}\n", encoding="utf-8")
    r = _run(["--surface", str(doc), "--json"], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    assert payload == {
        "hits": [
            {
                "class": "template-residue",
                "path": str(doc),
                "line": 1,
                "what": "unrendered template residue `{{X}}`",
                "occurrences": 1,
            }
        ],
        "files": 1,
        "notes": [],
        "ungraded_rows": 0,
    }


def _scratch_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/development/reviews").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    return root


def test_no_argument_mode_self_selects_a_changed_receipt(tmp_path, monkeypatch):
    # An ambient PROJECT_ROOT (exported by final_gate to every check) must not reach the child.
    monkeypatch.setenv("PROJECT_ROOT", str(REPO))
    root = _scratch_repo(tmp_path)
    (root / "docs/development/reviews/2026-09-09-x-review.md").write_text(
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F1 | shape | a row | FIXED — moved; the spans REFUTED again |\n",
        encoding="utf-8",
    )
    r = _run([], root)
    assert r.returncode == 0, r.stdout + r.stderr
    # REPO-RELATIVE, not the absolute path the self-selection builds: an advisory line that
    # names /tmp/… or /home/<user>/… is machine-specific and unclickable from the repo root.
    # The CLASS NAME must butt straight against `docs/` — a substring assertion on the relative
    # tail alone passes on the absolute path too (that mutant survived until this was tightened).
    assert "[ADVISORY] dual-verdict docs/development/reviews/2026-09-09-x-review.md:3 —" in r.stdout


def test_no_argument_mode_prefers_the_project_root_the_gate_exports(tmp_path):
    """`final_gate.py:268-270` exports PROJECT_ROOT to every check it runs; a git toplevel derived
    from cwd is the fallback, and the two differ whenever the gate runs from a subdirectory."""
    root = _scratch_repo(tmp_path)
    (root / "docs/development/reviews/2026-09-09-y-review.md").write_text(
        "| # | Class | Finding | Disposition |\n"
        "|---|---|---|---|\n"
        "| F1 | shape | a row | FIXED — moved; the spans REFUTED again |\n",
        encoding="utf-8",
    )
    # cwd OUTSIDE any repo: the git-toplevel fallback cannot answer from here, so a run that
    # finds the receipt can only have read PROJECT_ROOT. (Running from `root/docs` does NOT
    # discriminate — git walks UP to the same toplevel, and that mutant survived.)
    r = _run([], tmp_path, env={"PROJECT_ROOT": str(root)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2026-09-09-y-review.md:3" in r.stdout


def test_no_argument_mode_is_silent_with_no_changed_receipt(tmp_path):
    root = _scratch_repo(tmp_path)
    r = _run([], root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == ""


def test_json_mode_emits_its_envelope_even_when_the_self_selection_is_empty(tmp_path):
    """Silence is for the GATE registration's plain mode. A consumer that asked for `--json` and
    got an empty string cannot parse it — `json.loads("")` raises."""
    root = _scratch_repo(tmp_path)
    r = _run(["--json"], root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout) == {"hits": [], "files": 0, "notes": [], "ungraded_rows": 0}


def test_the_gate_registers_it_warn_only():
    gate = (REPO / "scripts/final_gate.py").read_text(encoding="utf-8")
    assert '"scripts/enforcement/check_review_hygiene.py"' in gate
    idx = gate.index('"scripts/enforcement/check_review_hygiene.py"')
    assert "warn_only=True" in gate[idx : idx + 400]


# ---------------------------------------------------------------- the measured fire rate

# Pinned from the run whose output is quoted in docs/workflows/FINAL_GATE_WORKFLOW.md. The doc's
# numbers are TRANSCRIBED FROM this test's printed output, never typed from memory — the doc adds
# `%`-spacing and thousands separators by hand, and says `TRANSCRIBED from` for exactly that
# reason. A prose-only fire rate is a claim nothing re-derives, and this class of check earns its
# place only while the rate holds.
CORPUS_RECEIPTS = 275
# Re-pinned 2026-09-10 (review-family adoption, Finish round 3): `_blank_quoted` read the comment
# markers on the RAW line, so a cell quoting `<!-- POOL OFF` opened a phantom comment and every later
# row went ungraded — 9 of 805 fleet receipts, a real raw-pipe defect lost behind "0 hits". Masking
# code spans first surfaced 75 rows, 2 raw-pipe hits in 2 more receipts; the recall rose, the rate
# barely moved (0.558 % → 0.584 %).
CORPUS_ROWS = 5992
CORPUS_DISPOSITION_ROWS = 1663
# D7 seam #3: 254 → 4241 (71.7 % of the corpus's rows; since re-pinned to 4,296 of 5,992 — the constants
# above are current, this paragraph is the history). The old number counted ONLY rows in a
# header-less table; a HEADED table that declares no disposition column was skipped silently and
# fell out of the denominator entirely, so the summary read "254 ungraded" over a corpus in which
# the dual-verdict class actually graded 1,645 of 5,917 rows. The rise IS the fix — a bounded
# search now states its real bound. ⚠️ docs/workflows/FINAL_GATE_WORKFLOW.md TRANSCRIBES this
# test's printed output and must be re-transcribed in the same change.
CORPUS_UNGRADED = 4296
CORPUS_RAW_PIPE = (35, 21)  # (hits, receipts)
CORPUS_DUAL_VERDICT = (27, 5)  # round 2: the four leading-count tally cells fire again


def test_the_fire_rate_over_the_committed_receipt_corpus():
    names = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "ls-tree",
            "-r",
            "--name-only",
            CORPUS_SHA,
            "--",
            "docs/development/reviews",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if names.returncode != 0 or not names.stdout.strip():
        pytest.skip(f"tree {CORPUS_SHA}:docs/development/reviews absent (shallow clone)")
    receipts = [
        n for n in names.stdout.split() if n.endswith(".md") and not n.endswith("-archive.md")
    ]
    rows = disposition = ungraded = 0
    hits: dict[str, int] = {"raw-pipe": 0, "dual-verdict": 0}
    files: dict[str, set[str]] = {"raw-pipe": set(), "dual-verdict": set()}
    for rel in receipts:
        text = _show(CORPUS_SHA, rel)
        assert text is not None, rel
        lines = crh._blank_quoted(text.splitlines())
        heads = crh._headers(lines)
        cursor = 0
        for row in crh._table_rows("\n".join(lines)):
            while cursor < len(lines) and lines[cursor] != row:
                cursor += 1
            if cursor >= len(lines):
                break
            idx, cursor = cursor, cursor + 1
            rows += 1
            if heads.get(idx, (None, None))[1] is not None:
                disposition += 1
        rhits, rungraded = crh._receipt_hits(rel, text)
        ungraded += rungraded
        for h in rhits:
            hits[h.cls] += 1
            files[h.cls].add(rel)
    print(
        f"corpus {CORPUS_SHA}: {len(receipts)} receipts · {rows} table data rows · "
        f"{disposition} disposition-bearing · {ungraded} ungraded ({ungraded / rows:.1%})\n"
        f"  raw-pipe     {hits['raw-pipe']} hits in {len(files['raw-pipe'])} receipts "
        f"({hits['raw-pipe'] / rows:.3%} of rows)\n"
        f"  dual-verdict {hits['dual-verdict']} hits in {len(files['dual-verdict'])} receipts "
        f"({hits['dual-verdict'] / disposition:.3%} of disposition-bearing rows)"
    )
    assert (len(receipts), rows, disposition, ungraded) == (
        CORPUS_RECEIPTS,
        CORPUS_ROWS,
        CORPUS_DISPOSITION_ROWS,
        CORPUS_UNGRADED,
    )
    assert (hits["raw-pipe"], len(files["raw-pipe"])) == CORPUS_RAW_PIPE
    assert (hits["dual-verdict"], len(files["dual-verdict"])) == CORPUS_DUAL_VERDICT


def test_every_repeatable_flag_says_so_in_its_help() -> None:
    """All four collectors are `action="append"`, but only two said "(repeatable)" — so `--surface`
    and `--receipt` read as single-valued and a caller passes one, silently sweeping a fraction of
    the surface (T10 review round 1). The help text IS the contract for a CLI nobody imports."""
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    ).stdout
    assert out.count("(repeatable)") == 4, out
    for flag in ("--surface", "--receipt", "--phrase", "--symbol"):
        i = out.index(
            f"  {flag} "
        )  # the options block, not the usage synopsis (two flags longer since T4.7)
        assert "(repeatable)" in out[i : i + 400], (flag, out[i : i + 400])


# ── D7 seam #3 (whole-plan validation, seat `opus`): a HEADED table that declares no disposition
# column was skipped SILENTLY and the summary still read `0 rows ungraded`. `review_receipt.py`'s
# generated grammar declares none (`| Class | Status |`, `| Pass | Finders | Counters | Method |`),
# so on a template-generated receipt the dual-verdict class graded nothing while claiming a full
# denominator. The denominator first; the coverage is a separate question. ────────────────────


def test_a_headed_table_with_no_disposition_column_is_ungraded_not_clean(tmp_path):
    receipt = tmp_path / "generated-review.md"
    receipt.write_text(
        "# Review\n\n"
        "## Coverage Checklist\n\n"
        "| Class | Status |\n"
        "|---|---|\n"
        "| shape | RECORDED — the F250 shape; RECORDED again by design |\n"
        "| races | CLEAN |\n",
        encoding="utf-8",
    )
    sweep = crh.scan(receipts=[receipt])
    # the class cannot grade these rows — but the denominator must SAY it swept nothing
    assert sweep.hits == []
    assert sweep.ungraded == 2, sweep


def test_the_declared_disposition_column_still_grades_and_counts_zero_ungraded(tmp_path):
    """The discriminating half: a table that DOES declare the column is graded as before, and its
    two-bare-verdict cell is still the one hit — the counter must not swallow the coverage."""
    receipt = tmp_path / "declared-review.md"
    receipt.write_text(
        "# Review\n\n"
        "| # | Class | Disposition |\n"
        "|---|---|---|\n"
        "| F1 | shape | RECORDED — the F250 shape; RECORDED again by design |\n"
        "| F2 | races | CLEAN |\n",
        encoding="utf-8",
    )
    sweep = crh.scan(receipts=[receipt])
    assert [(h.cls, h.line) for h in sweep.hits] == [("dual-verdict", 5)], sweep.hits
    assert sweep.ungraded == 0, sweep


def test_the_summary_line_reports_the_true_ungraded_denominator(tmp_path):
    """The user-observable half — the CLI summary and `--json` both carry it, so an operator
    reading `0 hit(s) … 0 rows ungraded` can tell "swept clean" from "swept nothing"."""
    receipt = tmp_path / "generated-review.md"
    receipt.write_text(
        "| Class | Status |\n|---|---|\n| shape | CLEAN |\n| races | CLEAN |\n| io | CLEAN |\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--receipt", str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "hygiene: 0 hit(s) over 1 file(s), 3 rows ungraded" in r.stdout, r.stdout
    j = subprocess.run(
        [sys.executable, str(SCRIPT), "--receipt", str(receipt), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert json.loads(j.stdout)["ungraded_rows"] == 3, j.stdout


# ------------------------------------------ the spec/plan classes (review-family adoption, Phase B)


def test_a_surface_table_row_with_more_cells_than_its_header_is_a_table_parity_hit(tmp_path):
    """`table-parity` on ANY `.md` surface, through the cell-count helper `raw-pipe` also uses
    (a shared helper, never a move — the receipt class is unchanged)."""
    p = tmp_path / "spec.md"
    p.write_text("# S\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n| 1 | 2 | 3 |\n")
    sweep = crh.scan(surfaces=[p])
    assert _lines(sweep, "table-parity") == [5]
    assert _lines(sweep, "raw-pipe") == []


def test_a_receipt_row_with_the_same_defect_still_fires_raw_pipe(tmp_path):
    p = tmp_path / "2026-09-10-x-review.md"
    p.write_text("# R\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n")
    sweep = crh.scan(receipts=[p])
    assert _lines(sweep, "raw-pipe") == [5]
    assert _lines(sweep, "table-parity") == []


def test_template_residue_is_the_fragment_parameter_shape_only(tmp_path):
    """The narrowing: `{{include:<name>}}` and `{{UPPER_CASE}}` fire; a Go template (`{{.Image}}`,
    the one standing false positive over the 36 rendered commands) and a literal `{{…}}` in a doc
    describing the class do not."""
    p = tmp_path / "doc.md"
    p.write_text(
        "go: `docker inspect --format '{{.Image}}' c`\n"
        "doc: the `{{…}}` residue class\n"
        "inc: {{include:run-record}}\n"
        "par: {{ARTIFACT}} and {{DONE_WORD}}\n"
        "low: {{artifact}}\n"
    )
    sweep = crh.scan(surfaces=[p])
    assert _lines(sweep, "template-residue") == [3, 4, 4]


def test_a_row_inside_a_fence_is_not_graded_for_table_parity(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text("# S\n\n```\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n```\n")
    sweep = crh.scan(surfaces=[p])
    assert _lines(sweep, "table-parity") == []


def test_a_headerless_table_on_a_surface_is_counted_as_ungraded(tmp_path):
    """The surface path keeps the helper's third value: rows no header pair claims are graded by
    nothing and the summary must say so (D7 seam #3, re-opened on the wider surface by Phase B's
    first cut — `--surface` printed `0 rows ungraded` over 313 headerless rows in docs/)."""
    p = tmp_path / "spec.md"
    p.write_text("# S\n\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n")
    sweep = crh.scan(surfaces=[p])
    assert sweep.ungraded == 2
    assert _lines(sweep, "table-parity") == []


def test_a_receipt_inside_the_surface_set_is_graded_by_the_receipt_class_only(tmp_path):
    """`--surface docs/ --receipt docs/…-review.md` — the documented shape — must not report one
    broken row twice (`table-parity` AND `raw-pipe` at the same `path:line`)."""
    d = tmp_path / "reviews"
    d.mkdir()
    r = d / "2026-09-10-x-review.md"
    r.write_text("# R\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n")
    sweep = crh.scan(surfaces=[d], receipts=[r])
    assert _lines(sweep, "raw-pipe") == [5]
    assert _lines(sweep, "table-parity") == []
    assert sweep.files == 1


def test_receipt_hits_are_emitted_in_line_order(tmp_path):
    """Lifting the parity pass out of the dual-verdict loop must not reorder the advisory lines —
    an orchestrator reads them top-down."""
    p = tmp_path / "2026-09-10-x-review.md"
    p.write_text(
        "# R\n\n| Id | Disposition |\n|---|---|\n"
        "| A | RECORDED — the F250 shape, RECORDED twice |\n"
        "| B | FIXED | extra |\n"
    )
    sweep = crh.scan(receipts=[p])
    lines = [h.line for h in sweep.hits]
    assert sorted(lines) == lines, lines
    assert _lines(sweep, "dual-verdict") == [5] and _lines(sweep, "raw-pipe") == [6]


@pytest.mark.parametrize(
    "spelling", ["absolute surface, relative receipt", "relative surface, absolute receipt"]
)
def test_one_file_under_two_spellings_is_one_file_and_one_class(tmp_path, monkeypatch, spelling):
    """`--surface <abs dir> --receipt <rel file>` is the gate's own shape (the no-argument mode
    self-selects ABSOLUTE receipt paths): one physical file is ONE entry in the denominator and is
    table-graded by the receipt class only, whichever way each side is spelled."""
    d = tmp_path / "reviews"
    d.mkdir()
    r = d / "2026-09-10-x-review.md"
    r.write_text("# R\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n")
    monkeypatch.chdir(tmp_path)
    if spelling.startswith("absolute surface"):
        sweep = crh.scan(surfaces=[d], receipts=[Path("reviews/2026-09-10-x-review.md")])
    else:
        sweep = crh.scan(surfaces=[Path("reviews")], receipts=[r])
    assert _lines(sweep, "raw-pipe") == [5]
    assert _lines(sweep, "table-parity") == []
    assert sweep.files == 1


def test_surface_hits_are_emitted_in_line_order(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text("# S\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n\ntext {{ARTIFACT}}\n")
    sweep = crh.scan(surfaces=[p])
    lines = [h.line for h in sweep.hits]
    assert sorted(lines) == lines, lines


def test_a_file_reached_through_its_directory_and_by_name_is_scanned_once(tmp_path, monkeypatch):
    """`--surface <dir> --surface <dir>/x.md` — one physical file, one entry, its hits emitted once
    (the expansion step dedupes on the RESOLVED path, whatever the spelling)."""
    d = tmp_path / "specs"
    d.mkdir()
    p = d / "spec.md"
    p.write_text("# S\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n")
    monkeypatch.chdir(tmp_path)
    sweep = crh.scan(surfaces=[Path("specs"), p])
    assert _lines(sweep, "table-parity") == [5]
    assert sweep.files == 1


def test_a_comment_opener_inside_a_code_span_does_not_blank_the_rows_after_it(tmp_path):
    """`` `<!--` `` in a cell is prose (a D-181 receipt quotes `<!-- POOL OFF` by convention); the
    blanking must read the line with code spans masked, or every later row goes ungraded and a real
    raw-pipe defect is lost (9 of 805 fleet receipts carried the shape on 2026-09-10)."""
    p = tmp_path / "2026-09-10-x-review.md"
    p.write_text(
        "# R\n\n| Id | Disposition |\n|---|---|\n"
        "| F1 | RECORDED — the cell quotes `<!-- POOL OFF` by convention |\n"
        "| F2 | FIXED | an unescaped pipe |\n"
    )
    sweep = crh.scan(receipts=[p])
    assert _lines(sweep, "raw-pipe") == [6]


def test_a_comment_opener_inside_a_fence_does_not_start_a_comment(tmp_path):
    """The fence state is decided first; markers inside a fenced example are quoted text (with the
    opener tested first, a fenced `<!--` blanked every later line of a probe copy; 0 live files differ)."""
    p = tmp_path / "pack.md"
    p.write_text(
        "# P\n\n```\n<!-- an example opener -->\n<!-- unclosed in the example\n```\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n"
    )
    sweep = crh.scan(surfaces=[p])
    assert _lines(sweep, "table-parity") == [10]


def test_a_parked_comment_closes_and_the_rows_after_it_are_graded(tmp_path):
    p = tmp_path / "2026-09-10-x-review.md"
    p.write_text(
        "# R\n\n<!-- parked:\n| old | rows |\n-->\n\n| Id | Disposition |\n|---|---|\n| F1 | FIXED | extra |\n"
    )
    sweep = crh.scan(receipts=[p])
    assert _lines(sweep, "raw-pipe") == [9]


def test_a_closer_inside_a_code_span_does_not_close_the_comment_early(tmp_path):
    p = tmp_path / "2026-09-10-x-review.md"
    # the span sits on a line INSIDE the comment: a raw read of the closer would end the comment
    # there and grade the parked F0 row as live
    p.write_text(
        "# R\n\n<!-- parked\n(mentions `-->` in prose)\n| Id | Disposition |\n|---|---|\n| F0 | FIXED | still parked |\n-->\n\n| Id | Disposition |\n|---|---|\n| F1 | FIXED | extra |\n"
    )
    sweep = crh.scan(receipts=[p])
    assert _lines(sweep, "raw-pipe") == [12]


def test_a_same_line_comment_is_left_raw(tmp_path):
    p = tmp_path / "2026-09-10-x-review.md"
    p.write_text(
        "# R\n\n<!-- a note on one line -->\n| Id | Disposition |\n|---|---|\n| F1 | FIXED | extra |\n"
    )
    sweep = crh.scan(receipts=[p])
    assert _lines(sweep, "raw-pipe") == [6]


def test_a_fence_opener_line_carrying_a_comment_opener_is_a_fence(tmp_path):
    """The opener line of a fence is itself fenced text: ```<!-- … opens a fence, not a comment, so
    the rows after the block stay live."""
    p = tmp_path / "pack.md"
    p.write_text(
        "# R\n\n```<!-- an example opener\nbody\n```\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 | 4 |\n"
    )
    sweep = crh.scan(surfaces=[p])
    assert _lines(sweep, "table-parity") == [9]


# ---------------------------------------------------------------- `--claim` (D10 rule 2)


def _claim_rows(stdout: str) -> list[int]:
    import re

    return [
        int(m.group(1))
        for m in re.finditer(r"^\[ADVISORY\] claim \S+:(\d+) — claim ", stdout, re.M)
    ]


def test_a_claim_term_lists_every_mirror_site_as_a_neutral_claim_row(tmp_path):
    """D10 rule (2): the pre-pin sweep is a COMMAND — `--surface <pin> --claim <term>` lists every
    line carrying the term (case-insensitively; a mirror inside a fence is still a mirror) so the
    orchestrator reads each site of a rewritten claim before the pin. The class is `claim`, never
    `stale-phrase`: a listing is neutral, not a verdict."""
    doc = tmp_path / "spec.md"
    doc.write_text(
        "The done window reaches back to the previous close.\n"
        "an unrelated line\n"
        "A DONE close REACHES BACK too.\n"
        "```\n"
        "$ probe: done reaches back inside a fence\n"
        "```\n",
        encoding="utf-8",
    )
    r = _run(["--surface", str(doc), "--claim", "reaches back"], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _claim_rows(r.stdout) == [1, 3, 5], r.stdout
    assert "hygiene: 3 hit(s) over 1 file(s)" in r.stdout, r.stdout
    assert "stale-phrase" not in r.stdout
    # a mirror WRAPPED across a line is listed too — the same whitespace-tolerant walk `--phrase`
    # uses (round-1 finding: a substring-per-line walk listed 1 of 2 and the pin went out with a
    # mirror unread)
    doc.write_text(
        "The done window reaches\nback to the close.\nA close reaches back.\n", encoding="utf-8"
    )
    r = _run(["--surface", str(doc), "--claim", "reaches back"], REPO)
    assert _claim_rows(r.stdout) == [1, 3], r.stdout
    # never across a BLANK line (a paragraph break is not a wrap), ONE row per line (a term
    # twice on one line is one site), and an empty term names no site — round-2 findings
    doc.write_text(
        "ends with fresh\n\nseat opens the next\nfresh seat here, FRESH SEAT twice\n",
        encoding="utf-8",
    )
    r = _run(["--surface", str(doc), "--claim", "fresh seat"], REPO)
    assert _claim_rows(r.stdout) == [4], r.stdout
    assert crh.scan(surfaces=[doc], claims=[""]).hits == []
    assert crh.scan(surfaces=[doc], phrases=[""]).hits == []  # the shared walk, same rule
    # a skipped blank-line match must not swallow a real site that starts inside its span
    # (round 3: a term whose first token repeats)
    assert crh._term_sites("para ends fresh\n\nfresh fresh seat\n", "fresh fresh") == [3]
    # an empty --phrase is refused aloud like an empty --claim (a `--phrase "$OLD"` whose
    # variable expanded empty must never read as a clean sweep)
    r = _run(["--surface", str(doc), "--phrase", ""], REPO)
    assert r.stdout.strip() == "REFUSED — --phrase needs a non-empty term", r.stdout
    r = _run(["--surface", str(doc), "--symbol", ""], REPO)  # `"".count` is len+1: always "live"
    assert r.stdout.strip() == "REFUSED — --symbol needs a non-empty term", r.stdout
    # the guard names the FIRST empty flag in (--claim, --phrase, --symbol) order (round 5)
    r = _run(["--surface", str(doc), "--symbol", "", "--phrase", ""], REPO)
    assert r.stdout.strip() == "REFUSED — --phrase needs a non-empty term", r.stdout
    r = _run(["--surface", str(doc), "--phrase", "", "--claim", ""], REPO)
    assert r.stdout.strip() == "REFUSED — --claim needs a non-empty term", r.stdout
    # line numbers are counted incrementally: the same answer, without the O(n·matches) walk
    assert crh._term_sites("a\nb a\n\na a\n", "a") == [1, 2, 4]


def test_a_claim_without_a_surface_is_refused_aloud_and_never_self_selects(tmp_path):
    """The spec's executed mutant: a dropped guard inherits the no-argument self-selection and
    prints `hygiene: 0 hit(s) over 1 file(s)` against the changed receipts — a green over nothing.
    PROJECT_ROOT is pinned to a fixture repo carrying one changed receipt so that path is live."""
    root = _scratch_repo(tmp_path)
    committed = root / "docs/development/reviews/2026-09-10-a-review.md"
    committed.write_text("| # | Class |\n|---|---|\n| F1 | x |\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "receipt"], check=True)
    (root / "docs/development/reviews/2026-09-11-b-review.md").write_text(
        "| # | Class | Finding | Disposition |\n|---|---|---|---|\n| F1 | shape | a row | FIXED |\n",
        encoding="utf-8",
    )
    r = _run(["--claim", "x"], root, env={"PROJECT_ROOT": str(root)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "REFUSED — --claim needs --surface", r.stdout
    assert "hygiene:" not in r.stdout
    # an empty term would list EVERY line of the surface (round-zero probe: 9 of 9) — refused too
    doc = tmp_path / "spec.md"
    doc.write_text("a\nb\n", encoding="utf-8")
    r = _run(["--surface", str(doc), "--claim", " "], root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "REFUSED — --claim needs a non-empty term", r.stdout
    # under --json the refusal rides the envelope's notes — a stdout consumer never gets prose
    r = _run(["--claim", "x", "--json"], root, env={"PROJECT_ROOT": str(root)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout) == {
        "hits": [],
        "files": 0,
        "notes": ["REFUSED — --claim needs --surface"],
        "ungraded_rows": 0,
    }


def test_claim_hits_carry_the_claim_class_in_json_and_beside_a_phrase(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text("the old wording stays here\nthe claim term sits here\n", encoding="utf-8")
    r = _run(["--surface", str(doc), "--claim", "claim term", "--json"], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    hits = json.loads(r.stdout)["hits"]
    assert [(h["class"], h["line"]) for h in hits] == [("claim", 2)], hits
    r = _run(["--surface", str(doc), "--claim", "claim term", "--phrase", "old wording"], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    kinds = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("[ADVISORY] ")]
    assert kinds == ["stale-phrase", "claim"], r.stdout


def test_hits_are_deduped_per_line_with_an_occurrences_field_and_a_stop_heading_and_a_label(
    tmp_path,
):
    """T4.7 (01M2AC95X, 01M285X4H): a phrase repeated on one line yielded one hit per occurrence
    (15 raw vs 13 unique every round); a surface carrying its own Pass Ledger reported every
    phrase the ledger retired; and the path echoed was the scratch copy, not the artifact."""
    s = tmp_path / "spec.pin.md"
    s.write_text(
        "# S\n\nnever issued, never issued, never issued\n\n## Pass Ledger\n\n"
        "| Pass 1 | retired 'never issued' |\n",
        encoding="utf-8",
    )
    sweep = crh.scan(surfaces=[s], phrases=["never issued"])
    stale = [h for h in sweep.hits if h.cls == "stale-phrase"]
    assert [h.line for h in stale] == [3, 7], [(h.line, h.what) for h in stale]
    assert stale[0].occurrences == 3 and stale[0].as_dict()["occurrences"] == 3
    sweep = crh.scan(surfaces=[s], phrases=["never issued"], stop_at_heading="## Pass Ledger")
    assert [h.line for h in sweep.hits if h.cls == "stale-phrase"] == [3]
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--surface",
            str(s),
            "--phrase",
            "never issued",
            "--stop-at-heading",
            "## Pass Ledger",
            "--label",
            "docs/superpowers/specs/spec.md",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
    )
    payload = json.loads(r.stdout)
    assert [h["path"] for h in payload["hits"]] == ["docs/superpowers/specs/spec.md"], payload
    assert payload["hits"][0]["occurrences"] == 3


def test_stop_at_heading_matches_a_real_heading_and_blanks_the_symbol_count_too(tmp_path):
    """Review round 1 (Phase B): `--stop-at-heading` matched any line STARTING with the text —
    a quoted heading inside a fence blanked the rest of the file, `#` swallowed everything, and
    the `--symbol` count still read the un-blanked text, so a symbol whose only mention sat in
    the retired ledger was reported live."""
    s = tmp_path / "spec.md"
    s.write_text(
        "# Doc\n\nthe widget lives here\n\n```\n## Pass Ledger\n```\n\n"
        "the widget is still live down here\n\n## Pass Ledger\n\nold_helper was removed; "
        "the widget was renamed\n",
        encoding="utf-8",
    )
    sweep = crh.scan(surfaces=[s], phrases=["the widget"], stop_at_heading="## Pass Ledger")
    assert [h.line for h in sweep.hits if h.cls == "stale-phrase"] == [3, 9], sweep.hits
    assert any("history — blanked" in n for n in sweep.notes), sweep.notes
    sweep = crh.scan(surfaces=[s], phrases=["the widget"], stop_at_heading="#")
    assert [h.line for h in sweep.hits if h.cls == "stale-phrase"] == [3, 9, 13], sweep.hits
    assert any("not found" in n for n in sweep.notes), sweep.notes
    sweep = crh.scan(surfaces=[s], symbols=["old_helper"], stop_at_heading="## Pass Ledger")
    assert [h.cls for h in sweep.hits] == ["dead-symbol"], sweep.hits
    sweep = crh.scan(surfaces=[s], symbols=["old_helper"])
    assert not sweep.hits, sweep.hits
    # review round 2: the RECEIPT path honours the flag too (it was a silent no-op there), and a
    # `~~~` line inside a ``` block is content, not a fence close
    sweep = crh.scan(receipts=[s], symbols=["old_helper"], stop_at_heading="## Pass Ledger")
    assert [h.cls for h in sweep.hits] == ["dead-symbol"], sweep.hits
    assert any("history — blanked" in n for n in sweep.notes), sweep.notes
    # and the receipt's OWN table classes read the blanked text: a dual-verdict row below the
    # heading is history, not a hit
    rec = tmp_path / "receipt.md"
    rec.write_text(
        "# R\n\n| # | Class | Disposition |\n|---|---|---|\n| 1 | x | CLEAN (a.py) |\n\n"
        "## Pass Ledger\n\n| # | Class | Disposition |\n|---|---|---|\n| 2 | y | FIXED r1 REFUTED |\n",
        encoding="utf-8",
    )
    assert [h.cls for h in crh.scan(receipts=[rec]).hits] == ["dual-verdict"]
    assert not crh.scan(receipts=[rec], stop_at_heading="## Pass Ledger").hits
    t = tmp_path / "tilde.md"
    t.write_text(
        "# Doc\n\n```\n~~~\n```\n\nthe widget lives here\n\n## Pass Ledger\n\nthe widget retired\n",
        encoding="utf-8",
    )
    sweep = crh.scan(surfaces=[t], phrases=["the widget"], stop_at_heading="## Pass Ledger")
    assert [h.line for h in sweep.hits if h.cls == "stale-phrase"] == [7], sweep.hits
    # round 3: a 3-backtick line inside a 4-backtick block is content — the quoted heading below
    # it is NOT the stop, and the live line after the block is graded
    q = tmp_path / "quad.md"
    q.write_text(
        "# Doc\n\n````md\n```\n## Pass Ledger\n```\n````\nthe widget lives here\n\n## Pass Ledger\n\nthe widget retired\n",
        encoding="utf-8",
    )
    sweep = crh.scan(surfaces=[q], phrases=["the widget"], stop_at_heading="## Pass Ledger")
    assert [h.line for h in sweep.hits if h.cls == "stale-phrase"] == [8], sweep.hits


def test_a_label_with_two_surfaces_is_refused_and_a_repeated_selector_dedupes(tmp_path):
    """Review round 1 (Phase B): `--label` was silently dropped with more than one surface, and
    `_dedupe` was never exercised — the same selector given twice is the producer that doubles
    a site, and the line output carries the count."""
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A\n\nThe Widget, the widget\n", encoding="utf-8")
    b.write_text("# B\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--surface", str(a), "--surface", str(b), "--label", "x.md"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
    )
    # review round 2: the CONTRACT is exit 0 — the refusal is printed, and under --json it rides
    # the envelope's notes
    assert r.returncode == 0 and "REFUSED" in r.stdout and "--label" in r.stdout, (
        r.stdout + r.stderr
    )
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--surface",
            str(a),
            "--surface",
            str(b),
            "--label",
            "x.md",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
    )
    assert r.returncode == 0 and "REFUSED" in json.loads(r.stdout)["notes"][0], r.stdout
    # the label does not leak into a second in-process run
    crh.main(["--surface", str(a), "--label", "first.md"])
    crh.main(["--surface", str(a)])
    assert not crh._LABEL, crh._LABEL
    assert crh._line_occurrences(["Foo foo"], 1, "foo") == 2
    sweep = crh.scan(surfaces=[a], phrases=["the widget", "the widget"])
    stale = [h for h in sweep.hits if h.cls == "stale-phrase"]
    # round 3: the same site twice is ONE site with the line's count, never a sum over producers
    assert len(stale) == 1 and stale[0].occurrences == 2, [(h.line, h.occurrences) for h in stale]
    assert "(×2)" in stale[0].line_out(), stale[0].line_out()
    assert crh._display.__doc__, "the early return demoted the docstring"


def test_the_docstring_names_the_md_only_classes():
    """T4.7 (01M285X4H): three of four classes run only on `.md` surfaces — the pin recipe copies
    to any name, so the docstring says which classes a non-.md surface silently loses."""
    assert 'path.endswith(".md")' in crh.__doc__, crh.__doc__[:600]
