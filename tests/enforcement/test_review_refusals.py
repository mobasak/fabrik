"""T02 — the REFUSAL half of D7: the token, counter and header rules, the RECORDED verdicts, the
residual licences (V5) and the finders cell (V11).

RED-FIRST IS EXECUTED, NOT CLAIMED. Every refused fixture is graded twice in the same test: once
against the gate as it stood BEFORE this ticket (`git show <PRE_T02_SHA>:` — T01's committed
grammar, materialised into a tmp file; the module is stdlib-only, so a bare copy runs) and once
against the working tree's gate. The pre-state each fixture is asserted to have had is written in
its own row — `silent` (the old grammar read it inert or QUIET, the fail-open being closed) or
`t01` (T01's counter-run reader already refused it by name, so this ticket adds no second
message). A revert of any rule turns the corresponding row red here, permanently.

The corpus tests are pinned to the plan's base SHA with `git ls-tree`/`git show`, never the
working tree, so the orchestrator's Delta repair of the ONE refused committed row cannot flip
the measurement afterwards. That row's refusal reaches NO gate output: the T20 receipt carries no
Coverage Checklist, so it is not `check_file`'s subject and `_committed_nonquiet` skips it — the
refusal exists at `_ledger_shapes` level only (executed: `check_file` and the advisory are
byte-identical to the pre-T02 gate on all 275). The repair is hygiene, not a red being cleared.
"""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
GATE_REL = "scripts/enforcement/check_review_coverage.py"
BASE_SHA = "8092e8a8"  # the plan's base — the corpus the DD4 measurements are made over
PRE_T02_SHA = "0fcafed5"  # T01's commit: the gate immediately before these rules
CORPUS_AT_BASE = 275


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout


crc = _load("crc_refusals", REPO / GATE_REL)


def _pre_gate() -> ModuleType:
    global _PRE
    if _PRE is None:
        p = Path(tempfile.mkdtemp(prefix="pre-t02-")) / "pre_gate.py"
        p.write_text(_git("show", f"{PRE_T02_SHA}:{GATE_REL}"), encoding="utf-8")
        _PRE = _load("crc_pre_t02", p)
    return _PRE


_PRE: ModuleType | None = None

# --- fixtures -----------------------------------------------------------------
# Every SINGLE-ROW fixture is embedded under a REAL vocabulary header with one prior parsing data
# row, so the run grades the ROW and not the header rule (the spec's own instruction). The block
# fixtures below are blocks by design and build their own text.
HEADER = "| Pass | Finders | found: F, confirmed: C, fixed: X | Method |"
SEP = "|---|---|---|---|"
PRIOR = "| Pass 1 | opus×1 | found: 1 | fixed: 1 |"


def _embed(row: str) -> str:
    return "\n".join(["## Pass Ledger", "", HEADER, SEP, PRIOR, row, ""])


def _refusals(text: str, mod: ModuleType | None = None) -> list[str]:
    return (mod or crc)._ledger_shapes(text)[3]


def _last(text: str, mod: ModuleType | None = None):
    return (mod or crc)._ledger_shapes(text)[2][-1]


def _quiet(row) -> bool:
    """`check_file`'s own exit verdict for a row: the D-206 rule, else the legacy `found:` one."""
    verdict = crc._confirmed_quiet(row)
    return row[0] == 0 if verdict is None else verdict


# (row, the pre-T02 state: "silent" = read inert or quiet, "t01" = already refused by name)
REFUSED_BY_TOKEN = [
    ("| 19 | found: 0 | fixed: 0 | confirmed: 3 |", "silent"),
    ("| 19 | found: 0 | fixed: 0 | confirmed: 0 |", "silent"),
    ("| 19 | found: 3 | fixed: 3 | delta (confirmed: 0) |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | method: delta | unexecuted: 2 |", "silent"),
    ("| 19 | confirmed: 3 | found: 0 | fixed: 0 |", "silent"),
    ("| 19 | unexecuted: 2 | found: 0 | fixed: 0 |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | unexecuted: 0 | fixed: 0 |", "silent"),
    ("| 19 | found: 0 | fixed: 0 | confirmed: 3", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | **unexecuted: 2** |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 2. |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted : 2 |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, Confirmed: 3, fixed: 0 | m |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, fixed: 0 — narrated CONFIRMED: 3 still stand | m |", "silent"),
    ("| 19 | found: 0 | Confirmed: 3 | fixed: 0 |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | Unexecuted: 2 |", "silent"),
    ("| 19 | found: 0 | Confirmed: three | fixed: 0 |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | Unexecuted: n/a |", "silent"),
    ("| 19 | found: 0 | fixed: 0 | Confirmed: 3 defects stand |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | Unexecuted: 2 standing |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | Unexecuted: two standing |", "silent"),
    ("| 19 | found: 0 | fixed: 0 | CONFIRMED: |", "silent"),
    ("| 19 | found: 0 | confirmed: three | fixed: 0 |", "silent"),
    ("| 19 | found: 5 | confirmed: | fixed: 0 |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: |", "silent"),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 0 | unexecuted: 2 |", "silent"),
    ("| 18 | found: 11, new: 9, confirmed: 3, fixed: 3, unexecuted: 0 |", "silent"),
    ("| Pass 19 | opus×1 | found: 0 | fixed: 0 | confirmed: 3 |", "silent"),
    ("| 19 | found: 0 | new: 2 | confirmed: 0 | fixed: 0 |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, fixed: 0 | delta (confirmed: 3) |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, confirmed: , fixed: 0 | m |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, confirmed: three, fixed: 0 | m |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, confirmed: 0, fixed: 0 | unexecuted: 2 |", "silent"),
    ("| Pass 19 | opus×1 | found: 0, confirmed: 0, fixed: 0 | m | confirmed: 3 |", "silent"),
    ("| Pass 19 | opus×1 | **found: 0** | **confirmed: 0** | **fixed: 0** |", "silent"),
    # a literal U+2028 — GFM's line normalisation folds it to a space BEFORE any reader splits
    # the text, so this is ONE row and the fragment cannot escape the scan
    ("| Pass 19 | opus×1 | found: 0, fixed: 0 | delta confirmed: 3 |", "silent"),
    # the counter run's own order, already named by T01's reader — no second message is added
    ("| Pass 19 | opus×1 | found: 0, confirmed: 0, fixed: 0, confirmed: 3 | m |", "t01"),
    ("| Pass 19 | opus×1 | found: 0, fixed: 0, confirmed: 0 | m |", "t01"),
    # the spec's `| 1 |`-numbered forms, verbatim (the same rules, a different first cell)
    ("| 1 | found: 0 | fixed: 0 | confirmed: 3 |", "silent"),
    ("| 1 | found: 0 | fixed: 0 | confirmed: 0 |", "silent"),
    ("| 1 | found: 3 | fixed: 3 | delta (confirmed: 0) |", "silent"),
    ("| 1 | confirmed: 3 | found: 0 | fixed: 0 |", "silent"),
    ("| 1 | unexecuted: 2 | found: 0 | fixed: 0 |", "silent"),
    # the placeholder-lettered row of the spec's three-row all-token block: `confirmed: C` is a
    # bare-colon token on a row whose `found: 0` makes it DATA, so it is refused like any other
    ("| N | found: 0 | confirmed: C | unexecuted: U | fixed: 0 |", "silent"),
    # ROUND 1 — a WRAPPED or punctuated value after an ALL-CAPS label is a counter wearing
    # markdown, not a prose label. `^\\d` alone exempted every one of these as a label and the
    # closing row then graded QUIET with defects standing; the spec puts the same wrapper in the
    # threat model for the lowercase form (`**unexecuted: 2**` is REFUSED).
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: **3** |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: (3) |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: -3 |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: +3 |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: `3` |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: _3_ |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | CONFIRMED: <3> |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | UNEXECUTED: **2** |", "silent"),
    ("| Pass 7 | native verifier | found: 0 | fixed: 0 | UNEXECUTED: [2] |", "silent"),
]

# The PROSE path: a Pass-headed line the prose arm reads, `_PASS_HEAD` the scope test.
REFUSED_PROSE = [
    ("Pass 19: found: 0, fixed: 0 — confirmed: three defects still stand", "silent"),
    ("Pass 19: found: 5, fixed: 0 — delta (confirmed: 0)", "silent"),
    ("- Pass 2 (SCOPED) — F1's hunk: found: 0, new: 0, fixed: 0 (confirmed: 0)", "silent"),
    ("- | Pass 19 | sonnet×2 | found: 5, fixed: 0 | delta (confirmed: 0) |", "silent"),
    ("Pass 19: confirmed: 0, found: 5, fixed: 0", "silent"),
    ("Pass 19: found: 0, fixed: 0, confirmed: 0", "t01"),
    ("Pass 19: found: 0, unexecuted: 0, confirmed: 0, fixed: 0", "t01"),
]

REFUSED_BY_COUNTER = [
    "| u | x | found: 0 | fixed: 0 | unexecuted: 2 |",
    "| x | found: 9 | fixed: 0 | unexecuted: 0 |",
    "| Pass 19 | opus×1 | found: 0, fixed: 0, unexecuted: 2 | m |",
]

# (row, quiet?) — resolved by a grammar, no occurrence left unread
PARSED_AND_NOT_REFUSED = [
    ("| Pass 19 | opus×1 | **found: 0, confirmed: 0** | **fixed: 0** |", True),
    ("Pass 19: found: 0, confirmed: 3, fixed: 0", False),
    ("| Pass 9 (C round 4) | native verifier | **found: 0** | **fixed: 0** | ALL CLOSED |", True),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 0 | delta re-derivation |", True),
    ("| 19 | found: 4 | confirmed: 0 | fixed: 0 |", True),
    ("| 19 | found: 4 | confirmed: 1 | fixed: 1 |", False),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 0", True),
    ("| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 2", False),
    ("| Pass 18 | opus×1 | found: 11, new: 9, confirmed: 3, fixed: 3, unexecuted: 0 | m |", False),
]

# The prose LIE: an ALL-CAPS verdict label beside an honest old-grammar row. Named out of the
# threat model by the spec — the operator's eye's job, not the parser's.
OUT_OF_THREAT_MODEL = [
    "| 19 | found: 0 | fixed: 0 | CONFIRMED: thirteen defects stand |",
    "| 19 | found: 0 | fixed: 0 | delta — CONFIRMED: see residual |",
    "| Pass 19 | opus×1 | found: 0, fixed: 0 | delta — CONFIRMED: thirteen defects stand |",
]


def test_the_refusal_rules_read_t01s_tuple() -> None:
    """The SEAM: this ticket consumes T01's extraction contract and never re-parses it."""
    text = _embed("| Pass 19 | opus×1 | found: 4, new: 0, confirmed: 0, fixed: 0 | delta |")
    shapes = crc._ledger_shapes(text)
    assert len(shapes) == 4
    tables, prose_runs, ordered, refusals = shapes
    assert refusals == [], refusals
    assert prose_runs == []
    assert len(tables) == 1
    assert all(len(r) == 5 for r in ordered), ordered
    assert ordered[-1][:4] == (4, 0, 0, None), ordered[-1]


@pytest.mark.parametrize("row,pre", REFUSED_BY_TOKEN)
def test_a_token_no_grammar_read_refuses_the_row_by_name(row: str, pre: str) -> None:
    text = _embed(row)
    before = _refusals(text, _pre_gate())
    if pre == "silent":
        assert before == [], (row, before)
    else:
        assert before, row
    now = _refusals(text)
    assert now, row
    if pre == "silent":
        assert any("no grammar read as a counter" in r for r in now), now
        assert any("write `confirmed:" in r or "write `| confirmed: C |`" in r for r in now), now


@pytest.mark.parametrize("row,pre", REFUSED_PROSE)
def test_a_token_outside_the_counter_run_refuses_the_prose_row(row: str, pre: str) -> None:
    text = "\n".join(["## Pass Ledger", "", "Pass 1: found: 1, fixed: 1", "", row, ""])
    before = _refusals(text, _pre_gate())
    assert (before == []) is (pre == "silent"), (row, before)
    now = _refusals(text)
    assert now, row
    if pre == "silent":
        assert any("inside the counter cell" in r for r in now), now


@pytest.mark.parametrize("row", REFUSED_BY_COUNTER)
def test_unexecuted_without_confirmed_is_refused_never_old_grammar_quiet(row: str) -> None:
    text = _embed(row)
    pre = _pre_gate()
    assert _refusals(text, pre) == [], row
    now = _refusals(text)
    assert any("`unexecuted:` with no `confirmed:` counter" in r for r in now), now
    # and the refusal PREEMPTS the quiet computation — the row is never read as an honest exit
    assert not _quiet(_last(text)), _last(text)


@pytest.mark.parametrize("row,quiet", PARSED_AND_NOT_REFUSED)
def test_a_row_both_grammars_resolve_is_not_refused_and_keeps_its_verdict(
    row: str, quiet: bool
) -> None:
    text = _embed(row)
    assert _refusals(text) == [], row
    last = _last(text)
    verdict = crc._confirmed_quiet(last)
    if verdict is None:  # no `confirmed:` — the legacy rule stands
        verdict = last[0] == 0
    assert verdict is quiet, (row, last)


@pytest.mark.parametrize("row", OUT_OF_THREAT_MODEL)
def test_an_all_caps_prose_label_on_an_old_grammar_row_is_exempt(row: str) -> None:
    """The five-conjunct carve-out. Without it the rule would refuse 27 honest committed cells."""
    assert _refusals(_embed(row)) == [], row


def test_the_carve_out_conjuncts_are_each_load_bearing() -> None:
    base = "| 19 | found: 0 | fixed: 0 | CONFIRMED: thirteen defects stand |"
    assert _refusals(_embed(base)) == []
    # 1 — a mis-cased literal is a counter attempt, not a label
    assert _refusals(_embed(base.replace("CONFIRMED", "Confirmed")))
    # 3 — what follows the colon is a VALUE
    assert _refusals(_embed(base.replace("thirteen defects stand", "13 defects stand")))
    assert _refusals(_embed(base.replace("thirteen defects stand", "n/a")))
    # 4 — the row states a numeric new-grammar counter of its own
    assert _refusals(
        _embed("| 19 | found: 0 | confirmed: 0 | fixed: 0 | CONFIRMED: see residual |")
    )
    # 2 — the label sits INSIDE the counter run
    assert _refusals(_embed("| Pass 19 | o×1 | found: 0, CONFIRMED: three, fixed: 0 | m |"))


def test_the_header_is_exempt_and_a_second_header_shaped_row_is_a_refused_data_row() -> None:
    good = "\n".join([HEADER, SEP, "| Pass 2 | opus×1 | found: 0, confirmed: 0, fixed: 0 | m |"])
    assert _refusals(good) == []
    twice = "\n".join(
        [HEADER, SEP, "| Pass 2 | opus×1 | found: 0, confirmed: 0, fixed: 0 | m |", HEADER]
    )
    assert _refusals(twice), "a second header-shaped row is a data row carrying the colon token"


def test_a_block_that_is_not_yet_a_ledger_is_never_refused() -> None:
    """`review_receipt.py --init` writes a header and a separator and nothing else."""
    init_shape = "| Pass | Finders | Counters | Method |\n|---|---|---|---|"
    assert _refusals(init_shape) == []
    assert _refusals(f"{HEADER}\n{SEP}") == [], (
        "the counter-vocabulary header alone is not a ledger"
    )
    # a disposition block: parenthesised verdicts, no colon token — out of scope
    disposition = "\n".join(
        [
            "| Finding | Seat | Disposition |",
            "|---|---|---|",
            "| F212 | grader | RECORDED — unexecuted (3 attempts timed out) |",
        ]
    )
    assert _refusals(disposition) == []


def test_a_token_bearing_block_in_which_nothing_parses_is_refused_by_name() -> None:
    block = "\n".join(
        [
            "| Pass | Finders | Counters | Method |",
            "|---|---|---|---|",
            "| 17 | found: 0 | confirmed: 1 | unexecuted: 0 | fixed: 1 |",
            "| 18 | found: 0 | confirmed: 0 | unexecuted: 0 | fixed: 0 |",
            "| 19 | found: 0 | confirmed: 0 | unexecuted: 0 | fixed: 0 |",
        ]
    )
    assert crc._ledger_shapes(block)[2] == [], "no row parses — the block must not go inert"
    assert len(_refusals(block)) == 3, _refusals(block)


def test_a_headerless_two_row_block_grades_its_first_row_as_data() -> None:
    block = "| 19 | found: 0 | Confirmed: 3 | fixed: 0 |\n| 20 | found: 0 | fixed: 0 |"
    assert _refusals(block), "the first row carries a numeric counter — it is data, not a header"


def test_a_stray_separator_never_splits_a_block_or_hides_a_row() -> None:
    rows = [
        HEADER,
        SEP,
        PRIOR,
        SEP,
        "| Pass 19 | opus×1 | found: 0, fixed: 0 | delta (confirmed: 3) |",
    ]
    assert _refusals("\n".join(rows)), "the row after a stray separator is still a data row"
    # and standalone as the block's FIRST row — a counter-bearing row is never a header
    assert _refusals("| Pass 19 | opus×1 | found: 0, fixed: 0 | delta (confirmed: 3) |")


def test_the_recorded_dispositions_are_verdicts_not_missing_ones() -> None:
    for kind in ("unexecuted (3 attempts timed out)", "by design (F4, round 3)", "measured (why)"):
        row = f"| F1 | RECORDED — {kind} |"
        assert crc.VERDICT.search(row), row
        assert not _pre_gate().VERDICT.search(row), f"pre-T02 read this as a noverdict row: {row}"
    assert crc.VERDICT.search("| F2 | RECORDED — hygiene false positive (fenced example) |")
    assert not crc.VERDICT.search("| F3 | RECORDED |"), "a bare RECORDED states no reason"
    assert not crc.VERDICT.search("| F4 | RECORDED — unexecuted: 3 |"), "a colon form is refused"
    for legacy in (
        "| a | CLEAN (x.py:1) |",
        "| b | FIXED (2) |",
        "| c | REFUTED |",
        "| d | ROUTED |",
    ):
        assert crc.VERDICT.search(legacy), legacy


# --- V5: the residual licences ------------------------------------------------
CLOSING = "| Pass 18 | opus×1 | found: 0, confirmed: 0, fixed: 0 | method: re-derivation |"


def _residual(
    verdict: str,
    *,
    closing: str = CLOSING,
    ids: str = "| F342 |\n| F358 |",
    prior: str = PRIOR,
) -> list[str]:
    ledger = [HEADER, SEP] + ([prior] if prior else []) + [closing]
    text = "\n".join(
        [
            "## Findings",
            "",
            "| id | note |",
            "|---|---|",
            ids,
            "",
            "## Residual",
            "",
            f"| F1 | RECORDED — {verdict} |",
            "",
            "## Pass Ledger",
            "",
            *ledger,
            "",
        ]
    )
    text_s = crc._strip_fences(text)
    return crc._residual_errors(text_s, crc._ledger_shapes(text)[2])


def test_a_by_design_licence_names_an_existing_owner_and_an_earlier_round() -> None:
    assert _residual("by design (F342, round 15; F358, round 17)") == []
    assert _residual("by design (D-203)") == []
    assert _residual("measured (a prevalence figure, no code claim)") == []
    assert _residual("unexecuted (3 probe attempts timed out)") == []


@pytest.mark.parametrize(
    "verdict,marker",
    [
        ("by design (F999, round 18)", "owning row is absent"),
        ("by design (the F250 shape, round 3)", "owning row is absent"),
        ("by design (D-203, round 3)", "takes NO round token"),
        ("by design (F342, round 18)", "not EARLIER than the closing"),
        ("by design (F342, round 19)", "not EARLIER than the closing"),
        ("by design (F342)", "needs its adjudicating"),
    ],
)
def test_a_malformed_by_design_licence_is_refused_by_name(verdict: str, marker: str) -> None:
    errs = _residual(verdict)
    assert errs and any(marker in e for e in errs), (verdict, errs)


def test_a_prefixed_owner_matches_whole_and_a_range_cell_expands() -> None:
    assert _residual("by design (AF9, round 3)", ids="| AF9 |") == []
    assert _residual("by design (F9, round 3)", ids="| AF9 |"), "F9 must not be lifted out of AF9"
    assert _residual("by design (F12, round 3)", ids="| F9, F12–F16 |") == []
    assert _residual("by design (F16, round 3)", ids="| F9, F12-F16 |") == []


def test_a_receipt_with_no_closing_pass_row_fails_closed_on_a_round_bound() -> None:
    mega_only = "| 19 | found: 0 | confirmed: 0 | fixed: 0 |"
    errs = _residual("by design (F342, round 1)", closing=mega_only, prior="")
    assert errs and any("no closing `Pass N` row" in e for e in errs), errs
    # a round-less D-row has no N to bound and stays exempt
    assert _residual("by design (D-203)", closing=mega_only, prior="") == []


def test_the_round_bound_reads_the_closing_row_never_an_earlier_pass_row() -> None:
    """ROUND 1 — the LAST-match class, again. A cell-anchored closing row appended after a Pass
    row let V5 bound a licence against the EARLIER round and pass it: `(F342, round 5)` under a
    trailing `| 99 | … |` was graded against `Pass 7` and accepted. The bound now reads
    `ordered[-1]` — the row the exit rule itself grades — and refuses when it has no Pass head."""
    cell_anchored = "| 99 | found: 0 | confirmed: 0 | fixed: 0 |"
    pass_seven = "| Pass 7 | opus×1 | found: 0, confirmed: 0, fixed: 0 | m |"
    errs = _residual("by design (F342, round 5)", closing=cell_anchored, prior=pass_seven)
    assert errs and any("no closing `Pass N` row" in e for e in errs), errs
    # the same licence under a real Pass-headed closing row is fine
    assert _residual("by design (F342, round 5)", closing=CLOSING, prior=pass_seven) == []


def test_the_closing_pass_row_is_ordered_minus_one_and_nothing_else() -> None:
    rows = "\n".join(
        [
            HEADER,
            SEP,
            "| Pass 7 | opus×1 | found: 0, confirmed: 0, fixed: 0 | m |",
            "| 99 | found: 0 | confirmed: 0 | fixed: 0 |",
        ]
    )
    ordered = crc._ledger_shapes(rows)[2]
    assert len(ordered) == 2, ordered
    assert crc._closing_pass_row(ordered) is None, "a cell-anchored last row carries no Pass N"
    assert crc._closing_pass_row(ordered[:1]) == (7, ordered[0][4])
    assert crc._closing_pass_row([]) is None


def test_the_residual_scan_never_reads_a_fenced_example() -> None:
    fenced = "\n".join(
        [
            "## Residual",
            "",
            "```text",
            "| F1 | RECORDED — by design (F999, round 9) |",
            "```",
            "",
            HEADER,
            SEP,
            PRIOR,
            CLOSING,
            "",
        ]
    )
    assert crc._residual_errors(crc._strip_fences(fenced), crc._ledger_shapes(fenced)[2]) == []


# --- V11: the finders cell ----------------------------------------------------
def test_the_closing_row_must_name_a_finder_seat_by_model_token() -> None:
    assert crc._MODEL_TOK.search("native sonnet×2")
    assert crc._MODEL_TOK.search("native opus×1 + sonnet×3")
    assert not crc._MODEL_TOK.search("the orchestrator's own re-read")
    assert crc._closing_pass_row(crc._ledger_shapes(_embed(CLOSING))[2])[0] == 18


def test_corpus_the_finders_rule_is_scoped_to_the_new_grammar_by_measurement() -> None:
    """FIRE RATE, measured before it blocks: over the receipts at the base SHA the rule would
    refuse 66 of the 70 closing rows if applied to every ledger — receipts whose finders cell
    honestly reads `native verifier` under the contract binding that day. Scoped to rows written
    under D-206 (`confirmed:` stated) it fires on 0 of them, and the redesigned loop's own rows
    are all inside that scope (the plan's Execution Discipline: from T02's merge on, every receipt
    closes on a row carrying `confirmed: 0`)."""
    unscoped = scoped = graded = 0
    for p in _corpus():
        ordered = crc._ledger_shapes(p.read_text(encoding="utf-8", errors="replace"))[2]
        closing = crc._closing_pass_row(ordered)
        if closing is None:
            continue
        graded += 1
        cells = crc._row_cells(closing[1])
        if len(cells) < 2 or not crc._MODEL_TOK.search(cells[1]):
            unscoped += 1
            row = next(r for r in reversed(ordered) if r[4] == closing[1])
            scoped += row[1] is not None
    print(f"V11 over {graded} closing rows at {BASE_SHA}: unscoped={unscoped} scoped={scoped}")
    assert (graded, unscoped, scoped) == (70, 66, 0)


# --- the pinned corpus --------------------------------------------------------
_corpus_cache: list[Path] = []


def _corpus() -> list[Path]:
    if _corpus_cache:
        return _corpus_cache
    rels = [
        f
        for f in _git(
            "ls-tree", "-r", "--name-only", BASE_SHA, "--", "docs/development/reviews"
        ).split()
        if f.endswith(".md")
    ]
    assert len(rels) == CORPUS_AT_BASE, len(rels)
    root = Path(tempfile.mkdtemp(prefix="corpus-refusals-"))
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_git("show", f"{BASE_SHA}:{rel}"), encoding="utf-8")
        _corpus_cache.append(p)
    return _corpus_cache


def test_corpus_the_token_rule_refuses_exactly_one_committed_row() -> None:
    """FIRE RATE of the token rule over the ledger-block path (the header exempt), pinned at the
    base SHA: 28 in-scope rows / 30 occurrences, of which 27 cells / 29 occurrences are exempt
    under the carve-out and ONE row is refused — the T20 receipt's verdict cell. That refusal
    surfaces in NO gate output (the receipt has no Coverage Checklist, so neither `check_file` nor
    the committed advisory reads it); the orchestrator's Delta repair is hygiene on the live file.
    A rule that refused the other 27 would be wallpaper; one that refused none would not close the
    fail-open."""
    files = _corpus()
    print(f"receipts examined: {len(files)}")
    rows = occ = exempt_rows = exempt_occ = 0
    refused: list[tuple[str, str]] = []
    for p in files:
        block: list[str] = []
        blocks: list[list[str]] = []
        for line in crc._strip_fences(p.read_text(encoding="utf-8", errors="replace")).splitlines():
            if line.strip().startswith("|"):
                block.append(line)
            elif block:
                blocks.append(block)
                block = []
        if block:
            blocks.append(block)
        for b in blocks:
            for ln in crc._ledger_block_rows(b):
                hits = list(crc._TOKEN_LIT.finditer(ln))
                if not hits:
                    continue
                rows += 1
                occ += len(hits)
                if any("no grammar read as a counter" in r for r in crc._row_refusals(ln)):
                    refused.append((p.name, ln.strip()[:60]))
                else:
                    exempt_rows += 1
                    exempt_occ += len(hits)
    print(f"in-scope rows={rows} occurrences={occ} exempt={exempt_rows}/{exempt_occ}")
    assert (rows, occ, exempt_rows, exempt_occ) == (28, 30, 27, 29)
    assert [n for n, _ in refused] == [
        "2026-08-31-plan-1-manifesto-command-pass-T20-fabrik-release-review.md"
    ], refused


def test_corpus_the_new_rules_change_no_other_committed_verdict() -> None:
    """DD4 backward compatibility, all three readers, over the same pinned corpus: the ONE row
    above is the only delta the refusal half introduces — `check_file` and the committed advisory
    are byte-identical to the pre-T02 gate on all 275 receipts."""
    pre = _pre_gate()
    files = _corpus()
    deltas = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        if crc.check_file(p) != pre.check_file(p):
            deltas.append(p.name)
        assert crc._ledger_shapes(text)[2] == pre._ledger_shapes(text)[2], p
    print(f"check_file deltas over {len(files)} receipts: {deltas}")
    assert deltas == []
    root = files[0].parents[3]
    assert (root / "docs/development/reviews").is_dir(), root
    assert crc._committed_nonquiet(root, set()) == pre._committed_nonquiet(root, set())
