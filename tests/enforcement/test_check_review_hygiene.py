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
    """`6 FIXED · 1 REFUTED` and `reads FIXED 12 · RECORDED 2` are COUNTS of verdicts, not two
    verdicts. Structural (a digit on either side), never a phrase list."""
    assert crh._verdict_words("FIXED — moved; the spans REFUTED again") == ["FIXED", "REFUTED"]
    assert crh._verdict_words("FIXED — one per cell; the tally reads FIXED 12 · RECORDED 2") == [
        "FIXED"
    ]
    # A digit BEFORE the word is a finding id or a round number, NEVER a tally — a symmetric
    # adjacency rule dropped all three of these, two of them silently halving a real cell.
    assert crh._verdict_words("F280 FIXED — escaped the pipe") == ["FIXED"]
    assert crh._verdict_words("round 14 FIXED; round 15 REFUTED") == ["FIXED", "REFUTED"]
    assert crh._verdict_words("RECORDED — the 2 RECORDED rows above") == ["RECORDED", "RECORDED"]


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
# numbers are copied FROM this test's printed output, never typed by hand — a prose-only fire rate
# is a claim nothing re-derives, and this class of check earns its place only while the rate holds.
CORPUS_RECEIPTS = 275
CORPUS_ROWS = 5917
CORPUS_DISPOSITION_ROWS = 1645
CORPUS_UNGRADED = 254
CORPUS_RAW_PIPE = (33, 19)  # (hits, receipts)
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
