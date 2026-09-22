"""Graders for scripts/check_research_ledger.py — a research ledger with an undispositioned fact is refused."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_research_ledger",
    Path(__file__).resolve().parent.parent / "scripts" / "check_research_ledger.py",
)
crl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(crl)

HEAD = "| id | source | fact | url | disposition |\n|---|---|---|---|---|\n"


def _ledger(tmp_path: Path, rows: str) -> Path:
    p = tmp_path / "2026-09-23-x-ledger.md"
    p.write_text("# ledger\n\n" + HEAD + rows, encoding="utf-8")
    return p


def test_every_disposition_form_is_accepted(tmp_path: Path) -> None:
    p = _ledger(
        tmp_path,
        "| s-01 | seat | a fact | https://a | USED → § 4.9 finding 25 |\n"
        "| s-02 | seat | same fact | https://a | DUPLICATE of s-01 |\n"
        "| s-03 | seat | a fact | https://b | REJECTED — read whole: a survey of velocity, no review loop in it |\n"
        "| s-04 | seat | a fact | https://c | UNREACHABLE — 403 Forbidden; tried exa, WebFetch |\n",
    )
    assert crl.check(p) == []
    assert crl.main([str(p)]) == 0


def test_an_open_or_empty_row_is_refused(tmp_path: Path) -> None:
    p = _ledger(
        tmp_path,
        "| s-01 | seat | a fact | https://a | OPEN |\n| s-02 | seat | a fact | https://a |  |\n",
    )
    bad = crl.check(p)
    assert len(bad) == 2 and all("undispositioned" in b for b in bad)
    assert crl.main([str(p)]) == 1


def test_a_rejection_without_a_real_reason_or_a_dangling_duplicate_is_refused(
    tmp_path: Path,
) -> None:
    p = _ledger(
        tmp_path,
        "| s-01 | seat | a fact | https://a | REJECTED — read whole: not relevant |\n"
        "| s-02 | seat | a fact | https://a | DUPLICATE of s-99 |\n"
        "| s-03 | seat | a fact | https://a | DUPLICATE of s-03 |\n",
    )
    bad = crl.check(p)
    assert len(bad) == 3
    assert (
        "five words" in bad[0] and "not in this ledger" in bad[1] and "not in this ledger" in bad[2]
    )


def test_a_row_with_a_malformed_id_is_refused_never_skipped(tmp_path: Path) -> None:
    p = _ledger(
        tmp_path,
        "| S-01 | seat | uppercase | https://a | OPEN |\n| s-abc | seat | no number | https://b | |\n"
        "| s-1234 | seat | four digits | https://c | OPEN |\n| s-02 | seat | fine | https://d | USED → x |\n",
    )
    bad = crl.check(p)
    assert len(bad) == 3 and all("malformed id" in b for b in bad), bad
    assert crl.main([str(p)]) == 1


def test_an_escaped_pipe_inside_a_fact_keeps_the_row_in_its_five_cells(tmp_path: Path) -> None:
    p = _ledger(tmp_path, "| s-01 | seat | rate 5 \\| 10 req/s | https://a | OPEN |\n")
    assert crl._rows(p.read_text(encoding="utf-8"))[0][4] == "OPEN"
    assert len(crl.check(p)) == 1


def test_a_ledger_with_no_fact_rows_is_refused_and_a_missing_path_is_a_usage_error(
    tmp_path: Path,
) -> None:
    p = _ledger(tmp_path, "")
    assert crl.check(p) and "no fact rows" in crl.check(p)[0]
    assert crl.main([str(tmp_path / "absent-ledger.md")]) == 2
