# AFTER-EDIT: scripts/enforcement/check_review_hygiene.py
"""Behavior contract for the advisory review-hygiene sweep (T08, review-convergence redesign).

The two receipt fixtures are fetched with ``git show <sha>:<path>`` into ``tmp_path`` — never a
tracked-path grep, because the working tree's copy of the D-191 receipt moves under the plan and a
tracked read would grade a different artifact every round. Both objects are skipped-with-a-reason
when absent (a shallow clone).
"""

from __future__ import annotations

import json
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
SHA_69 = "69f01b92"  # round 16: F280 is escaped, six dual-verdict cells stand (F314 at :670)


def _obj(sha: str) -> str | None:
    """The receipt blob at ``sha``, or None when the object is absent (shallow clone)."""
    probe = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", f"{sha}:{RECEIPT}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return subprocess.run(
        ["git", "-C", str(REPO), "show", f"{sha}:{RECEIPT}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _fixture(tmp_path: Path, sha: str) -> Path:
    text = _obj(sha)
    if text is None:
        pytest.skip(
            f"object {sha}:{RECEIPT} absent from this clone (shallow) — fixture unfetchable"
        )
    p = tmp_path / f"{sha}-receipt.md"
    p.write_text(text, encoding="utf-8")
    return p


def _classes(hits, cls: str) -> list[int]:
    return sorted(h.line for h in hits if h.cls == cls)


# ---------------------------------------------------------------- the receipt row-shape classes


def test_the_dual_verdict_class_counts_bare_verdict_words(tmp_path):
    """The seam with T02 (spine § Interfaces): the class counts BARE verdict WORDS per cell, not
    ``VERDICT`` matches — F314's cell (`RECORDED — the F250 shape …`) carries RECORDED twice and
    matches T02's widened ``VERDICT`` zero times, so a VERDICT-based detector is blind to it."""
    receipt = _fixture(tmp_path, SHA_69)
    hits, _ = crh.scan(receipts=[receipt])
    lines = _classes(hits, "dual-verdict")
    print(f"dual-verdict hits at {SHA_69}: {len(lines)} rows -> {lines}")
    assert lines == [419, 540, 649, 670, 683, 694]
    # the F314 cell itself: two bare RECORDED, zero VERDICT matches
    cell = receipt.read_text(encoding="utf-8").splitlines()[669]
    from check_review_coverage import VERDICT  # noqa: PLC0415 — the T02 grammar, read not copied

    assert cell.count("RECORDED") == 2
    assert VERDICT.search(cell) is None


def test_the_raw_pipe_class_fires_on_f280_before_it_was_escaped(tmp_path):
    receipt = _fixture(tmp_path, SHA_741)
    hits, _ = crh.scan(receipts=[receipt])
    assert _classes(hits, "raw-pipe") == [596]
    # F280's row is not ALSO a dual-verdict hit at 741eebbf — the two classes are independent
    assert 596 not in _classes(hits, "dual-verdict")


def test_the_raw_pipe_class_is_silent_once_the_pipe_is_escaped(tmp_path):
    receipt = _fixture(tmp_path, SHA_69)
    hits, _ = crh.scan(receipts=[receipt])
    assert _classes(hits, "raw-pipe") == []


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
    hits, files = crh.scan(receipts=[receipt])
    assert hits == []
    assert files == 1


# ---------------------------------------------------------------- the surface classes


def test_template_residue_is_reported_with_its_line(tmp_path):
    cmd = tmp_path / "fabrik-thing.md"
    cmd.write_text("# Thing\n\nrun the record: {{X}}\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[cmd])
    assert _classes(hits, "template-residue") == [3]


def test_fence_parity_follows_the_commonmark_same_char_run_rule(tmp_path):
    unclosed = tmp_path / "unclosed.md"
    unclosed.write_text("intro\n\n```bash\necho hi\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[unclosed])
    assert _classes(hits, "fence-parity") == [3]

    nested = tmp_path / "nested.md"
    nested.write_text("intro\n\n````md\n```bash\necho hi\n```\n````\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[nested])
    assert _classes(hits, "fence-parity") == []


def test_a_dead_symbol_is_one_hit_and_a_live_one_is_none(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("def still_here():\n    return 1\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[src], symbols=["still_here"])
    assert _classes(hits, "dead-symbol") == []
    hits, _ = crh.scan(surfaces=[src], symbols=["long_gone"])
    assert [h.what for h in hits if h.cls == "dead-symbol"] == [
        "symbol `long_gone` is referenced 0 time(s) across 1 file(s) on the surface"
    ]


def test_a_stale_phrase_matches_across_a_line_wrap(tmp_path):
    doc = tmp_path / "rule.md"
    doc.write_text("a floor of three seats\nis never the answer\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[doc], phrases=["three seats is never"])
    assert _classes(hits, "stale-phrase") == [1]
    hits, _ = crh.scan(surfaces=[doc], phrases=["four seats is never"])
    assert _classes(hits, "stale-phrase") == []


def test_the_changelog_class_calls_check_changelog_quality(tmp_path):
    ch = tmp_path / "CHANGELOG.md"
    ch.write_text("# Changelog\n\n## [Unreleased]\n\nnothing structured here\n", encoding="utf-8")
    hits, _ = crh.scan(surfaces=[ch])
    assert _classes(hits, "changelog-entry") == [3]
    ch.write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added — a real entry (2026-09-09)\n- a thing\n",
        encoding="utf-8",
    )
    hits, _ = crh.scan(surfaces=[ch])
    assert _classes(hits, "changelog-entry") == []


def test_a_directory_surface_is_walked_for_md_and_py(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.md").write_text("{{RESIDUE}}\n", encoding="utf-8")
    (tmp_path / "sub" / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "sub" / "c.txt").write_text("{{IGNORED}}\n", encoding="utf-8")
    hits, files = crh.scan(surfaces=[tmp_path / "sub"])
    assert _classes(hits, "template-residue") == [1]
    assert files == 2


# ---------------------------------------------------------------- the CLI contract


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_cli_exits_zero_and_prints_advisory_lines_even_with_hits(tmp_path):
    doc = tmp_path / "residue.md"
    doc.write_text("{{X}}\n", encoding="utf-8")
    r = _run(["--surface", str(doc)], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[ADVISORY] template-residue" in r.stdout
    assert "hygiene: 1 hit(s) over 1 file(s)" in r.stdout


def test_the_json_mode_emits_the_same_hits_as_a_list(tmp_path):
    doc = tmp_path / "residue.md"
    doc.write_text("{{X}}\n", encoding="utf-8")
    r = _run(["--surface", str(doc), "--json"], REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    assert payload["hits"] == [
        {
            "class": "template-residue",
            "path": str(doc),
            "line": 1,
            "what": "unrendered template residue `{{X}}`",
        }
    ]
    assert payload["files"] == 1


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


def test_no_argument_mode_self_selects_a_changed_receipt(tmp_path):
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
    assert json.loads(r.stdout) == {"hits": [], "files": 0}


def test_the_gate_registers_it_warn_only():
    gate = (REPO / "scripts/final_gate.py").read_text(encoding="utf-8")
    assert '"scripts/enforcement/check_review_hygiene.py"' in gate
    idx = gate.index('"scripts/enforcement/check_review_hygiene.py"')
    assert "warn_only=True" in gate[idx : idx + 400]
