"""D7 / D-206: both ledger grammars learn `confirmed:` and `unexecuted:`, and the exit rule
grades the counter the CONTRACT now names.

The redesign re-cuts what a quiet round is: a candidate CONFIRMED by execution counts, while
RECORDED and REFUTED rows never reopen the loop (D-206, superseding D-048's `found:` rule). So a
final ledger row may legitimately read `found: 4` and still be the exit round — if it CONFIRMED
nothing, fixed nothing and left nothing unexecuted.

Backward compatibility is the CONTRACT here (DD4), not a nicety: this file is fleet-synced to ~46
repos, whose committed receipts are all written in the old grammar. Two tests below are therefore
INVARIANCE guards measured against the committed gate at the plan's base SHA — the corpus is the
denominator, and every count they print carries it.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
# The plan's base commit — the committed grammar every invariance guard compares against. The
# module imports only the standard library, so a `git show` copy runs standalone (no worktree:
# `git worktree add` writes the shared repo's registry).
BASE_SHA = "8092e8a8"
GATE_REL = "scripts/enforcement/check_review_coverage.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crc = _load("crc_confirmed", REPO / GATE_REL)


CORPUS_AT_BASE = 275  # receipts under docs/development/reviews at BASE_SHA — the DD4 denominator

_corpus_cache: list[Path] = []
# The root the pinned corpus is materialised under. READER 3 (`_committed_nonquiet`) takes a ROOT
# and rglobs it, so handing it `REPO` walked the LIVE filesystem and bypassed the pin entirely —
# one throwaway receipt with a D-206-quiet closing row committed anywhere under
# docs/development/reviews and the invariance test reds (`base=14, widened=13`). All three readers
# must see the SAME pinned corpus or the comparison is not one comparison.
_corpus_root: Path | None = None


def _corpus() -> list[Path]:
    """Every review receipt AS OF `BASE_SHA` — enumerated with `ls-tree` and read with `git show`,
    never `ls-files` over the working tree.

    ⚠️ This pin is the whole point. The invariance tests below compare the CURRENT gate against
    the gate at `BASE_SHA`, so the corpus must be the one that SHA graded. Reading live files made
    that a landmine: the moment this plan's own receipts land — their closing rows are
    `found: N, …, confirmed: 0, fixed: 0`, quiet under the new grammar and NOT under the old — the
    comparison reds the hub suite for every session, blaming the gate for a receipt written after
    it. The denominator drifts the same way, silently rebasing the "2 of N" counts.

    The content is materialized into a tmp mirror under the same relative path, because
    `check_file` takes a Path; nothing is ever read from the working tree.
    """
    global _corpus_root
    if _corpus_cache:
        return _corpus_cache
    rels = [
        f
        for f in subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "ls-tree",
                "-r",
                "--name-only",
                BASE_SHA,
                "--",
                "docs/development/reviews",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if f.endswith(".md")
    ]
    assert len(rels) == CORPUS_AT_BASE, (
        f"the pinned corpus is {len(rels)} receipts, not {CORPUS_AT_BASE} — a silent shrink of the "
        "DD4 denominator makes every 'N of 275' claim in this suite a different assertion"
    )
    root = Path(tempfile.mkdtemp(prefix="corpus-at-base-"))
    _corpus_root = root
    for rel in rels:
        blob = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{BASE_SHA}:{rel}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(blob, encoding="utf-8")
        _corpus_cache.append(p)
    return _corpus_cache


def _base_gate(tmp_path: Path) -> ModuleType:
    src = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{BASE_SHA}:{GATE_REL}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    p = tmp_path / "old_gate.py"
    p.write_text(src, encoding="utf-8")
    return _load("crc_base", p)


# A report the blocking reader accepts in full — so an assertion about the EXIT rule is never
# satisfied (or defeated) by an unrelated obligation. `Pass 2` is literal because the two-round
# minimum is a text match; the re-derivation row is the closing-pass mandate.
HEAD = (
    "# Review\n\nStatus: CLOSED\n\n**Surface:** `HEAD abc` · diff md5 `x`\n\n"
    "Rubric: `python scripts/review_rubric.py --changed a.py` (output fenced below)\n\n"
    "```\n# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)\n"
    "rubric body\n```\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open vs fail-closed | CLEAN | probed a.py guards + callers |\n"
    "| 2 | cost/quota accounting | CLEAN | hunted a.py cost paths |\n"
    "| 3 | boundary/sentinel/prefix | CLEAN | hunted a.py parsers |\n"
    "| 4 | behavior-without-a-test | CLEAN | hunted tests/test_a.py + a.py handlers |\n\n"
    "## Pass Ledger\n\n"
    "| Pass 1 | method: citation | found: 3 | new: 3 | fixed: 3 | finders: opus |\n"
    "| Pass 2 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: opus |\n"
)
# V1 — the canonical D7 closing row: `found:` is 4 and the round is still QUIET.
V1 = "| Pass 19 | opus×1 | found: 4, new: 2, confirmed: 0, fixed: 0, unexecuted: 0 | delta |\n"


def _graded(tmp_path: Path, tail: str) -> list[str]:
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "2026-09-09-confirmed-review.md"
    p.write_text(HEAD + tail, encoding="utf-8")
    return crc.check_file(p)


def _exit_errors(errs: list[str]) -> list[str]:
    return [e for e in errs if "final ledger round" in e]


def test_the_canonical_v1_row_exits_quiet_on_confirmed_zero_although_found_is_four(tmp_path):
    """D-206's whole point: `found: 4` with `confirmed: 0` is the exit round."""
    assert _graded(tmp_path, V1) == []


def test_a_confirmed_defect_in_the_final_round_fails_naming_confirmed(tmp_path):
    """The other half of D-206: `confirmed: 1` is a defect this round proved by EXECUTION, so
    the loop is not done however small `found:` is — and the message must name the counter it
    graded (an author who cannot see which counter failed edits the wrong one) and cite D-206,
    not the D-048 clause it replaces."""
    errs = _graded(
        tmp_path,
        "| Pass 19 | opus×1 | found: 4, new: 2, confirmed: 1, fixed: 1, unexecuted: 0 | delta |\n",
    )
    exits = _exit_errors(errs)
    assert exits and "confirmed: 1" in exits[0], errs
    assert "D-206" in exits[0] and "D-048" not in exits[0], exits


def test_an_unexecuted_candidate_in_the_final_round_fails_naming_unexecuted(tmp_path):
    """`unexecuted:` counts code candidates RECORDED but never executed (D1). A round that ends
    with one standing has left work the loop cannot see, so it is not the exit round even when
    `confirmed:` and `fixed:` are both 0 — the third conjunct of the quiet rule."""
    errs = _graded(
        tmp_path,
        "| Pass 19 | opus×1 | found: 4, new: 2, confirmed: 0, fixed: 0, unexecuted: 1 | delta |\n",
    )
    exits = _exit_errors(errs)
    assert exits and "unexecuted: 1" in exits[0], errs


def test_an_old_grammar_final_row_still_grades_on_found(tmp_path):
    """INVARIANCE guard (DD4): a receipt with no `confirmed:` token anywhere grades exactly as it
    did before D7 — `found: 3` fails, `found: 0` passes. Its red is a mutation on a copy (the
    legacy branch neutered), asserted in the ticket's red-first record."""
    errs = _graded(tmp_path, "| Pass 3 | opus | found: 3 | new: 0 | fixed: 0 |\n")
    exits = _exit_errors(errs)
    assert exits and "raised 3" in exits[0], errs
    assert _graded(tmp_path, "| Pass 3 | opus | found: 0 | new: 0 | fixed: 0 |\n") == []


def test_the_cell_anchored_row_resolves_mega_first_with_or_without_its_closing_pipe():
    """GFM lets the closing pipe go, and a `|`-only terminator would make a correct closing row
    INERT — matching neither grammar, so `founds[-1]` grades the PREVIOUS round (fail-open)."""
    row = "| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 0 |"
    for line in (row, row.rstrip("|").rstrip()):
        _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
        assert len(ordered) == 1, (line, ordered)
        assert ordered[0][:4] == (0, 0, 0, 0), (line, ordered)
        assert refusals == [], refusals


def test_corpus_the_widened_mega_row_matches_the_same_rows_and_the_new_slot_variant_far_more():
    """The `new:` slot D7 deliberately leaves OUT. Both counts are printed with their
    denominator: a count without one is indistinguishable from having looked at nothing."""
    files = _corpus()
    with_new_slot = re.compile(
        r"^\s*\|.*?\|\s*found:\s*(\d+)\s*(?:\||$)"
        r"(?:\s*new:\s*(\d+)\s*(?:\||$))?"
        r"(?:\s*confirmed:\s*(\d+)\s*(?:\||$))?"
        r"\s*fixed:\s*(\d+)\s*(?:\||$)"
        r"(?:\s*unexecuted:\s*(\d+)\s*(?:\||$))?"
    )
    shipped = slotted = lines = 0
    for p in files:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            lines += 1
            shipped += bool(crc._MEGA_ROW.match(ln))
            slotted += bool(with_new_slot.match(ln))
    print(
        f"_MEGA_ROW: shipped={shipped}, with-new-slot={slotted} "
        f"over {lines} lines in {len(files)} committed receipts"
    )
    assert len(files) > 200, f"corpus looks wrong: {len(files)} receipts"
    assert shipped == 2, f"the shipped regex must keep its 2 cell-anchored rows, got {shipped}"
    assert slotted > 10 * shipped, (
        f"an optional `new:` cell would flip {slotted} rows (of {lines} lines in {len(files)} "
        f"receipts) from the Pass grammar to MEGA-first, against {shipped} today"
    )


def test_pass_counters_ext_reads_the_counter_run_and_leaves_pass_counters_alone():
    """The extraction contract's two halves at once: the NEW reader reads `confirmed:` from the
    counter run on all three row shapes (prose, narrated, separate-cell), and the LEGACY pair
    keeps returning its two values unchanged — six narrow callers and the mega battery's 2-tuple
    expectations depend on that, and a widened return would break every one of them silently."""
    line = "Pass 19: found: 0, confirmed: 3, fixed: 0"
    assert crc._pass_counters_ext(line) == (0, 3, 0, None)
    assert crc._pass_counters(line) == (0, 0), "the legacy strict pair must not widen"
    # a narrated token AFTER the run is not a counter — the whole-line-is-one-cell reading would
    # flip this row from not-quiet to quiet
    assert crc._pass_counters_ext("Pass 19: found: 5, fixed: 0 — delta (confirmed: 0)") == (
        5,
        None,
        0,
        None,
    )
    # the separate-cell shape: the new tokens live INSIDE the `found:` cell, `fixed:` in its own
    assert crc._pass_counters_ext(
        "| Pass 19 | o | **found: 0, confirmed: 0, unexecuted: 0** | **fixed: 0** |"
    ) == (0, 0, 0, 0)


def test_a_misordered_counter_run_is_refused_by_name_and_the_row_stays_in_ordered(tmp_path):
    """A `None` return would leave the row INERT and hand the exit to the previous round — the
    fail-open direction. The row stays, its counters are `None`, and the reason is reported."""
    line = "Pass 19: found: 0, fixed: 0, confirmed: 0"
    reason = crc._pass_counters_ext(line)
    assert isinstance(reason, str) and "confirmed" in reason, reason
    _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
    assert [r[:4] for r in ordered] == [(0, None, 0, None)], ordered
    assert len(refusals) == 1 and "confirmed" in refusals[0], refusals
    errs = _graded(tmp_path, "- Pass 19: found: 0, fixed: 0, confirmed: 0\n")
    assert any(e.startswith("Pass row refused:") and "confirmed" in e for e in errs), errs
    assert crc._pass_counters_ext("Pass 19: found: 0, confirmed: 1, confirmed: 2, fixed: 0") == (
        "a second `confirmed:` counter in the run "
        "('found: 0, confirmed: 1, confirmed: 2, fixed: 0')"
    )


def test_corpus_every_committed_receipt_parses_and_grades_exactly_as_it_did_at_the_base_sha(
    tmp_path,
):
    """INVARIANCE guard, all three readers, 0 flips. Its red is a mutation on a copy (the `None`
    default for an absent `confirmed:`), asserted in the ticket's red-first record."""
    base = _base_gate(tmp_path)
    files = _corpus()
    assert len(files) > 200, f"corpus looks wrong: {len(files)} receipts"
    rows_old = rows_new = errs_old = errs_new = 0
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        o_tables, o_prose, o_ordered, *_ = base._ledger_shapes(text)
        n_tables, n_prose, n_ordered, refusals = crc._ledger_shapes(text)
        rows_old += len(o_ordered)
        rows_new += len(n_ordered)
        assert [r[-1] for r in n_ordered] == [r[-1] for r in o_ordered], p
        assert [(r[0], r[2]) for r in n_ordered] == [(r[0], r[1]) for r in o_ordered], p
        assert all(r[1] is None and r[3] is None for r in n_ordered), p
        assert refusals == [], (p, refusals)
        assert (len(n_tables), len(n_prose)) == (len(o_tables), len(o_prose)), p
        assert crc._unparsed_pass_lines(text) == base._unparsed_pass_lines(text), p
        # reader 1 — the blocking gate, verbatim errors modulo the D-048 -> D-206 rewording
        new_errs, old_errs = crc.check_file(p), base.check_file(p)
        errs_new += len(new_errs)
        errs_old += len(old_errs)
        assert _normalize(new_errs) == _normalize(old_errs), p
        # reader 2 — the mega grammar, for the reports routed to it
        if crc._is_mega_report(p, text):
            assert _normalize(crc.check_mega_validation(p, REPO, live=False)) == _normalize(
                base.check_mega_validation(p, REPO, live=False)
            ), p
    print(f"parsed Pass rows: base={rows_old}, widened={rows_new} over {len(files)} receipts")
    print(f"check_file errors: base={errs_old}, widened={errs_new} over {len(files)} receipts")
    assert rows_new == rows_old
    assert errs_new == errs_old
    # reader 3 — the committed advisory, one sweep per gate version, over the PINNED mirror.
    # It takes a ROOT and rglobs it, so `REPO` here walked the live tree and bypassed `_corpus()`.
    assert _corpus_root is not None, "_corpus() must have materialised the mirror"
    new_c = [e.split(": COMMITTED")[0] for e in crc._committed_nonquiet(_corpus_root, set())]
    old_c = [e.split(": COMMITTED")[0] for e in base._committed_nonquiet(_corpus_root, set())]
    print(f"committed advisories: base={len(old_c)}, widened={len(new_c)}")
    assert new_c == old_c


_D_CLAUSE = re.compile(r"\(a (?:FRESH|candidate) .*?D-\d+\)")


def _normalize(errs: list[str]) -> list[str]:
    """The one sanctioned text delta: the exit clause is re-keyed from D-048 to D-206."""
    return [_D_CLAUSE.sub("(CLAUSE)", e) for e in errs]


def test_the_line_normalisation_runs_before_the_readers_split_the_text():
    """GFM's notion of a line, imposed once: a zero-width character renders as nothing (so
    `confirmed<ZWSP>: 3` looks like a counter and parses as none) and a `U+2028` splits the row
    in Python but not in a renderer (so the counter fragment lands on a line no reader sees)."""
    zwsp = "| Pass 3 | m | found: 0, confirmed\u200b: 3, fixed: 0 |\n"
    _t, _p, ordered, _r = crc._ledger_shapes(zwsp)
    assert [r[:4] for r in ordered] == [(0, 3, 0, None)], ordered
    split = "| Pass 3 | m | found: 0, confirmed: 3,\u2028fixed: 0 |\n"
    body = crc._strip_fences(split)
    assert "\u2028" not in body and len(body.splitlines()) == 1, repr(body)
    _t, _p, ordered, _r = crc._ledger_shapes(split)
    assert [r[:4] for r in ordered] == [(0, 3, 0, None)], ordered
    # the set is REUSED from _LINE_BREAKS, never retyped
    assert set(crc._LINE_BREAKS) - set("\r\n") <= {chr(c) for c in crc._GFM_NORMALIZE}
    # the header window (built by splitting RAW text) is normalised too
    hidden = "# Review" + "\u2028filler" * 10 + "\n**Status:** IN-PROGRESS\n"
    assert len(hidden.splitlines()) > 10, "fixture must push Status out of the raw 10-line zone"
    assert crc._in_progress(hidden) is True


MEGA = (
    "# Cross-Epic Validation Report\nSurface: {h2}\n\n"
    "| round | found: | confirmed: | fixed: | md5(start) → md5(end) |\n"
    "|------:|-------:|---|---|---|\n"
    "| 1 | found: 0 | confirmed: 0 | fixed: 0 | {h1} → {h2} |\n"
    "| 2 | found: 0 | confirmed: {c} | fixed: 0 | {h2} → {h2} |\n"
)


def test_the_mega_grammar_unpacks_the_widened_row_and_reads_confirmed(tmp_path):
    """The THIRD reader. It unpacks the row tuple positionally (a 5-tuple into 3 names raises
    ValueError, which is why the widening enumerated every reader) and it must take the same
    D-206 branch as the other two — this file's founding enemy is a hardening that lands in one
    ledger reader and not its siblings. The hash-chain pairs still read the row's RAW line."""
    h1, h2 = "a" * 32, "b" * 32
    p = tmp_path / "2026-09-09-mega-x-validation-review.md"
    p.write_text(MEGA.format(h1=h1, h2=h2, c=0), encoding="utf-8")
    assert crc.check_mega_validation(p, tmp_path, live=False) == []
    p.write_text(MEGA.format(h1=h1, h2=h2, c=3), encoding="utf-8")
    errs = crc.check_mega_validation(p, tmp_path, live=False)
    assert any("final ledger round reads confirmed: 3" in e for e in errs), errs


# --- round-1 review fixes (F1-F7): each of these was RED on the pinned module at afb8243c ----


def test_an_unexecuted_counter_without_confirmed_is_never_quiet_in_any_reader(tmp_path):
    """F1 — the fail-open the two-branch rule left open. `unexecuted: 3` with no `confirmed:`
    fell to every reader's LEGACY rule, so `found: 0, fixed: 0` read QUIET with three unexecuted
    code candidates standing. D7 calls that row malformed (T02 refuses it by name); until then
    the exit must fail CLOSED on it, and say which counter it graded."""
    prose = "Pass 19: found: 0, fixed: 0, unexecuted: 3"
    row = crc._ledger_shapes(prose + "\n")[2][-1]
    assert row[:4] == (0, None, 0, 3), row
    assert crc._confirmed_quiet(row) is False, "a stated unexecuted: N is never quiet"
    # reader 1 — the blocking gate
    errs = _exit_errors(_graded(tmp_path, "| Pass 19 | o | found: 0, fixed: 0, unexecuted: 3 |\n"))
    assert errs and "unexecuted: 3" in errs[0], errs
    # the cell-anchored shape resolves MEGA-first and must fail the same way
    cell = "| 19 | found: 0 | fixed: 0 | unexecuted: 3 |"
    mrow = crc._ledger_shapes(cell + "\n")[2][-1]
    assert mrow[:4] == (0, None, 0, 3), mrow
    assert crc._confirmed_quiet(mrow) is False
    # a stated ZERO still falls to the legacy rule — absence and 0 are not the same statement
    assert crc._confirmed_quiet((0, None, 0, 0, "x")) is None
    assert crc._confirmed_quiet((0, None, 0, None, "x")) is None


def test_a_counter_token_trailed_by_a_word_is_not_a_counter_even_inside_the_run():
    """F2 — the stand-alone token guard was defeated by scanning the run's SLICE: the slice ends
    at the digit, so `(?!\\s*\\w)` never saw the word after it and `confirmed: 0 candidates
    reproduced` read as `confirmed: 0` — QUIET with 3 raised. `_FOUND_TOK` refuses the identical
    shape (`found: 0 clean`, the round-11 defence), so the grammars now agree."""
    forgery = "Pass 19: found: 3, confirmed: 0 candidates reproduced, fixed: 0"
    assert crc._pass_counters_ext(forgery) == (3, None, 0, None), "must degrade to no counter"
    row = crc._ledger_shapes(forgery + "\n")[2][-1]
    assert crc._confirmed_quiet(row) is None and row[0] == 3, row
    # and the shapes that legitimately end in a non-word must still parse
    for line, want in (
        ("| Pass 19 | o | **found: 0, confirmed: 0** | **fixed: 0** |", (0, 0, 0, None)),
        ("| Pass 19 | o | found: 0, confirmed: 0, unexecuted: 1** | fixed: 0 |", (0, 0, 0, 1)),
        ("| Pass 19 | o | found: 0, confirmed: 0, unexecuted: 0 | m | fixed: 0 |", (0, 0, 0, 0)),
        ("Pass 19: found: 0, confirmed: 0, fixed: 0.", (0, 0, 0, None)),
    ):
        assert crc._pass_counters_ext(line) == want, (line, crc._pass_counters_ext(line))


def test_a_non_counter_item_does_not_end_the_counter_run():
    """F3 — the run's boundary is the spec's: "the first character that is not part of a
    comma-joined `key: value` item". A numeric-only item value ended the run at
    `method: re-derivation`, dropping the `unexecuted: 3` behind it (quiet) and hiding a
    displaced counter from the order check. A value is a bare WORD, so a spaced narration
    (` — delta (confirmed: 0)`) still ends the run."""
    keeps = "Pass 19: found: 0, confirmed: 0, fixed: 0, method: re-derivation, unexecuted: 3"
    assert crc._pass_counters_ext(keeps) == (0, 0, 0, 3), crc._pass_counters_ext(keeps)
    displaced = "Pass 19: found: 0, fixed: 0, note: x, confirmed: 5"
    reason = crc._pass_counters_ext(displaced)
    assert isinstance(reason, str) and "`confirmed:`" in reason, reason
    # the narration boundary is unmoved
    assert crc._pass_counters_ext("Pass 19: found: 5, fixed: 0 — delta (confirmed: 0)") == (
        5,
        None,
        0,
        None,
    )


def test_the_legacy_pair_is_byte_identical_to_the_base_sha(tmp_path):
    """F4 — DD4's literal clause. `_pass_counters` has six narrow callers and five 2-tuple
    expectations in the mega battery, so its BODY may not move at all: an added docstring is an
    added statement in the AST. Compared as an AST body, not as text, so comments and formatting
    stay free."""
    import ast

    def body_of(src: str) -> str:
        tree = ast.parse(src)
        fn = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_pass_counters"
        )
        return ast.dump(ast.Module(body=fn.body, type_ignores=[]))

    base_src = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{BASE_SHA}:{GATE_REL}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    now_src = (REPO / GATE_REL).read_text(encoding="utf-8")
    assert body_of(now_src) == body_of(base_src), "_pass_counters' body moved — DD4 forbids it"


def _joined(a: str, b: str) -> str:
    """Two ledger rows on ONE physical line — a real `U+2028`, the way a paste produces it."""
    return a + "\u2028" + b + "\n"


MEGA_PAIR = ("| Pass 1 | f | found: 0 | fixed: 0 |", "| Pass 2 | f | found: 5 | fixed: 0 |")
COMMA_PAIR = ("| Pass 9 | o | found: 0, fixed: 0 |", "| Pass 10 | o | found: 5, fixed: 0 |")
PROSE_PAIR = ("Pass 9: found: 0, fixed: 0", "Pass 10: found: 5, fixed: 0")
CELL_PAIR = ("| 1 | found: 0 | fixed: 0 |", "| 2 | found: 5 | fixed: 0 |")


def test_every_joined_row_shape_is_refused_by_name_and_kept_in_the_ledger(tmp_path):
    """F5, redesigned (round-2 D1/D3). The first cut keyed on `_MEGA_ROW` + a `found:` count, so
    it saw ONLY the cell-anchored shape: the comma-run table form and the PROSE form still went
    silent, because `_pass_counters` refuses two `found:` tokens and `_unparsed_pass_lines` skips
    multi-strict lines. Detection is on the row HEADS now, which every shape has (or, for a
    head-less cell-anchored pair, on the `| found:` cell openings), and the row is KEPT as its
    FIRST run — dropping it hands the exit to the previous round, the fail-open the guard exists
    to close."""
    for label, (a, b) in (
        ("mega", MEGA_PAIR),
        ("comma-run", COMMA_PAIR),
        ("prose", PROSE_PAIR),
        ("cell-anchored, head-less", CELL_PAIR),
    ):
        line = _joined(a, b)
        assert len(line.splitlines()) == 2, f"{label}: fixture must split in Python"
        _t, _p, ordered, refusals = crc._ledger_shapes(line)
        assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), (
            label,
            refusals,
        )
        assert [r[:4] for r in ordered] == [(0, None, 0, None)], (label, ordered)


def test_a_row_that_merely_cites_another_round_is_not_a_joined_row(tmp_path):
    """F5's mirror (round-2 D2): counting `found:` tokens refused the honest
    `| … | found: 1 | fixed: 1 | the round-3 row said found: 3 |`, DROPPED it from the ledger
    (so the exit graded the previous round — fail-open on the refused row) and blamed a `U+2028`
    that was not there. One head plus a cited counter is one row."""
    citing = "| Pass 4 | o | found: 1 | fixed: 1 | the round-3 row said found: 3 |\n"
    _t, _p, ordered, refusals = crc._ledger_shapes(citing)
    assert refusals == [], refusals
    assert [r[:4] for r in ordered] == [(1, None, 1, None)], ordered
    # the CELL-OPENING twin (round-3 D1): `_CELL_FOUND` had neither `_FOUND_TOK`'s stand-alone
    # guard nor a head requirement, so any two cells merely BEGINNING `found: <digit>` tripped
    # the cell-anchored branch — this honest row was refused where the base gate saw 0 errors
    cell_citing = "| Pass 3 | o | found: 0 | fixed: 0 | found: 3 was the round-3 number |\n"
    _t, _p, ordered3, refusals3 = crc._ledger_shapes(cell_citing)
    assert refusals3 == [], refusals3
    assert [r[:4] for r in ordered3] == [(0, None, 0, None)], ordered3
    assert _graded(tmp_path, cell_citing) == [], _graded(tmp_path, cell_citing)
    prose_citing = "Pass 3: found: 0, fixed: 0 — same as Pass 2\n"
    _t, _p, ordered2, refusals2 = crc._ledger_shapes(prose_citing)
    assert refusals2 == [] and [r[:4] for r in ordered2] == [(0, None, 0, None)], (
        refusals2,
        ordered2,
    )
    errs = _graded(tmp_path, citing)
    assert not any(e.startswith("Pass row refused:") for e in errs), errs
    # ...and the same shape with a quiet first run passes the blocking gate outright
    quiet = "| Pass 4 | o | found: 0 | fixed: 0 | the round-3 row said found: 3 |\n"
    assert _graded(tmp_path, quiet) == [], _graded(tmp_path, quiet)


def test_a_joined_line_mid_ledger_leaves_the_table_as_one_group(tmp_path):
    """F5's second mirror (round-2 D4): the refusal used to fall through to the table-boundary
    flush, so ONE ledger became two groups and the multi-group guards accused the author of a
    decoy ledger — a second, wrong error on top of the right one."""
    ledger = (
        "| Pass 1 | f | found: 3 | fixed: 3 |\n"
        + _joined("| Pass 2 | f | found: 2 | fixed: 2 |", "| Pass 3 | f | found: 1 | fixed: 1 |")
        + "| Pass 4 | f | found: 0 | fixed: 0 |\n"
    )
    tables, prose, ordered, refusals = crc._ledger_shapes(ledger)
    assert [len(t) for t in tables] == [3], f"the ledger must stay ONE group: {tables}"
    assert prose == [] and len(ordered) == 3 and len(refusals) == 1, (prose, ordered, refusals)
    errs = _graded(tmp_path, ledger)
    assert any(e.startswith("Pass row refused:") for e in errs), errs
    assert not any("separate groups" in e for e in errs), errs


def test_a_line_with_no_first_run_is_not_joined_and_still_ends_its_table(tmp_path):
    """Round-3 D2. `| stage | found: 3 issues | found: 4 issues |` matched the unguarded cell
    opening twice, so it emitted a refusal while `_first_run` returned None — nothing was kept
    AND the `continue` skipped the table flush, so two adjacent ledgers merged into ONE group and
    the multi-group guard was disarmed, against this file's own "never silently dropped"
    contract. It carries no row STRUCTURE (no head cell, no empty cell, one strict opening), so
    it is not joined at all and takes the ordinary path."""
    stage = "| stage | found: 3 issues | found: 4 issues |\n"
    assert crc._joined_row(stage.rstrip("\n")) is False
    _t, _p, ordered, refusals = crc._ledger_shapes(stage)
    assert refusals == [] and ordered == [], (refusals, ordered)
    sandwich = (
        "| Pass 1 | f | found: 0 | fixed: 0 |\n" + stage + "| Pass 2 | f | found: 0 | fixed: 0 |\n"
    )
    tables, prose, ordered2, refusals2 = crc._ledger_shapes(sandwich)
    assert [len(t) for t in tables] == [1, 1], f"the table boundary must survive: {tables}"
    assert prose == [] and len(ordered2) == 2 and refusals2 == [], (prose, ordered2, refusals2)


def test_a_joined_line_with_no_readable_first_run_is_refused_and_ends_its_table(tmp_path):
    """Round-4 item 2: the no-first-run branch, DRIVEN. It was unreachable while every detector
    was a subset of `_FOUND_TOK` — reverting the branch left the old test green (2 mutants
    survived), which is a test asserting nothing. The structural arms reach past `_FOUND_TOK` on
    purpose, so a join whose counters are BOTH word-trailed lands here: refused by name, nothing
    kept (borrowing the second row's counters is the quiet-off-the-second-half fail-open), and
    the table ended exactly as any unparsed line ends it — never merged into the next ledger."""
    joined = _joined(
        "| Pass 5 | f | found: 3 issues | fixed: 1 |", "| Pass 6 | f | found: 0 items | fixed: 0 |"
    )
    line = joined.rstrip("\n")
    assert crc._joined_row(line) is True, "two head cells + two loose counters is a join"
    assert crc._first_run(line, crc._second_row_pos(line)) is None, "no READABLE first run"
    _t, _p, ordered, refusals = crc._ledger_shapes(joined)
    assert ordered == [], f"never borrow the second row's counters: {ordered}"
    assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), refusals
    ledger = (
        "| Pass 1 | f | found: 0 | fixed: 0 |\n" + joined + "| Pass 7 | f | found: 0 | fixed: 0 |\n"
    )
    tables, _p2, ordered2, refusals2 = crc._ledger_shapes(ledger)
    assert [len(t) for t in tables] == [1, 1], f"the table boundary must survive: {tables}"
    assert len(ordered2) == 2 and len(refusals2) == 1, (ordered2, refusals2)
    # Round-5 item 3: assert what the GATE SAYS, not only the shapes it derived. The boundary the
    # refusal creates DOES reach the multi-group guard, so a mid-ledger join is reported TWICE —
    # once truthfully, once as a decoy-group accusation the author did not earn. Fail-CLOSED but
    # wrong-reason, and pinned here so the comment above the branch can never drift from it again.
    errs = _graded(tmp_path, joined + "| Pass 5 | f | found: 0 | fixed: 0 |\n")
    assert any(e.startswith("Pass row refused:") for e in errs), errs
    assert any("separate groups" in e and "decoy" in e for e in errs), (
        f"the decoy-group accusation is the RECORDED wrong-reason second error: {errs}"
    )


def test_a_word_trailed_counter_never_hides_a_join(tmp_path):
    """Round-4 item 1 — the REGRESSION `(?!\\s*\\w)` on the cell opening introduced: one
    word-trailed counter made a genuinely joined line invisible, and the receipt then graded
    QUIET off its SECOND half. Detection is on the row STRUCTURE now (head cells, the empty cell
    a join leaves behind), so how READABLE a counter is cannot decide how many rows there are.

    The BULLETED case is the same fail-open on the OTHER call site: a `- | … |` row does not
    start with a pipe, so it is read by the PROSE branch — where an unbounded `_first_run` reaches
    across the join and keeps the second row's `found: 0`. Both sites must bound the read at
    `_second_row_pos`, so both are driven here."""
    for label, (a, b) in (
        (
            "headed",
            (
                "| Pass 3 | re-derivation | found: 5 issues | fixed: 0 | opus |",
                "| Pass 4 | delta | found: 0 | fixed: 0 | opus |",
            ),
        ),
        ("headless", ("| R1 | found: 3 issues | fixed: 1 |", "| R2 | found: 0 | fixed: 0 |")),
        (
            "both trailed",
            ("| Pass 1 | found: 3 issues | fixed: 1 |", "| Pass 2 | found: 0 items | fixed: 0 |"),
        ),
        (
            "bulleted — the PROSE call site",
            ("- | Pass 3 | found: 5 issues | fixed: 0 |", "- | Pass 4 | found: 0 | fixed: 0 |"),
        ),
    ):
        line = _joined(a, b).rstrip("\n")
        assert crc._joined_row(line) is True, label
        _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
        assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), label
        assert not any(crc._confirmed_quiet(r) or r[0] == 0 for r in ordered), (
            f"{label}: a join must never yield a quiet row off its second half: {ordered}"
        )


def test_the_two_committed_receipts_the_counter_only_detector_refused_stay_parsed():
    """The DD4 evidence, in the suite rather than in a report: the counter-only detector refused
    two rows of committed history — a row quoting its own verdict verbatim, and a method cell
    narrating another round's example line. Neither carries a row STRUCTURE, so the structural
    arms leave both alone; a future widening that reds either one reds here first."""
    for rel, lineno in (
        ("docs/development/reviews/2026-08-11-plan-2-stalled-midstream-resume-review.md", 35),
        ("docs/development/reviews/2026-08-18-mega-enforcement-e2bf0f6e-review.md", 304),
    ):
        p = REPO / rel
        line = p.read_text(encoding="utf-8").splitlines()[lineno - 1]
        assert "found:" in line, f"{rel}:{lineno} moved — re-derive the fixture"
        assert crc._joined_row(line) is False, f"{rel}:{lineno} refused as joined: {line[:120]}"


def test_all_three_readers_report_a_joined_row(tmp_path):
    """F5 (round-2 D3): the blocking gate, the committed advisory AND the mega grammar. The mega
    reader bound `refusals` to `_`, so on a mega report the row vanished with no message at all —
    this file's founding enemy (a hardening that lands in one ledger reader and not its siblings)."""
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    p = d / "2026-09-09-joined-review.md"
    body = HEAD.replace("| Pass 2 | method", "| Pass 8 | method") + _joined(*COMMA_PAIR)
    p.write_text(body, encoding="utf-8")
    assert any(e.startswith("Pass row refused:") for e in crc.check_file(p)), crc.check_file(p)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for args in (
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    advisory = crc._committed_nonquiet(tmp_path, set())
    assert any("refused Pass row" in a for a in advisory), advisory
    # reader 3 — a mega report carrying the same joined pair
    h1, h2 = "a" * 32, "b" * 32
    mega = tmp_path / "2026-09-09-mega-x-validation-review.md"
    mega.write_text(
        MEGA.format(h1=h1, h2=h2, c=0)
        + _joined(f"| 3 | found: 0 | fixed: 0 | {h2} → {h2} |", "| 4 | found: 5 | fixed: 0 | x |"),
        encoding="utf-8",
    )
    errs = crc.check_mega_validation(mega, tmp_path, live=False)
    assert any(e.startswith("Pass row refused:") for e in errs), errs


def test_both_readers_name_the_same_counter_for_a_row_without_confirmed(tmp_path):
    """F6 — consistency. The committed advisory named `(found: 3, fixed: 0)` where the blocking
    reader said `raised 3`: two readers describing ONE row with two different counter sets is
    how the reader-divergence class starts. The legacy branch names `found:` in both."""
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    p = d / "2026-09-09-legacy-review.md"
    p.write_text(HEAD + "| Pass 3 | o | found: 3 | fixed: 0 |\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for args in (
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    advisory = crc._committed_nonquiet(tmp_path, set())
    assert advisory and "(found: 3)" in advisory[0], advisory
    assert "fixed:" not in advisory[0].split(" — ")[0], advisory
    assert any("raised 3" in e for e in _exit_errors(crc.check_file(p))), crc.check_file(p)


def test_a_list_wrapped_table_row_is_cell_bounded_like_its_bare_twin():
    """F7 — `_PASS_HEAD` tolerates a leading list marker, so "is this written in cells?" must be
    asked of the marker-stripped text; asking it of the raw line made `- | Pass 19 | … |` the
    only Pass row whose run was bounded by the LINE. Defence in depth: under today's
    `_RUN_ITEM` no item can cross a `|`, so both bounds agree on every input — the guard is
    what keeps that true if the item grammar ever widens. The property tested is the
    EQUIVALENCE, plus the invariant it protects (a counter in a LATER cell is never this row's)."""
    bare = "| Pass 19 | found: 0, confirmed: 3 | fixed: 0 | unexecuted: 9 |"
    wrapped = "- " + bare
    b_start, b_stop, b_names = crc._counter_run(bare)
    w_start, w_stop, w_names = crc._counter_run(wrapped)
    assert bare[b_start:b_stop] == wrapped[w_start:w_stop] == "found: 0, confirmed: 3"
    assert b_names == w_names == ["found", "confirmed"]
    assert crc._pass_counters_ext(bare) == crc._pass_counters_ext(wrapped) == (0, 3, 0, None), (
        "the `unexecuted: 9` in a later cell belongs to no row's run"
    )


def test_a_prose_ledger_join_is_refused_even_when_a_counter_is_word_trailed(tmp_path):
    """Round-5 item 1 — a PRE-EXISTING fail-open this ticket's class closes, on the prose grammar.

    `Pass 3: … found: 5 issues, fixed: 0` joined to `Pass 4: … found: 0, fixed: 0` has no cells
    (so arms A and B cannot see it) and only ONE strict `_FOUND_TOK` (so the legacy head arm
    cannot either). Executed on b00a7755: `_joined_row` False, the row parsed as `(0, 0)`, and
    `check_file` returned `[]` — GREEN. A round that raised 5 was invisible and the exit was
    graded off the join's SECOND half. The prose arm keys on the COLON head form and only on
    pipe-less lines, so a cell row whose method cell narrates `Pass 3: found: 7 issues remain`
    is untouched."""
    line = (
        "Pass 3: method: re-derivation, found: 5 issues, fixed: 0 "
        "Pass 4: method: re-derivation, found: 0, fixed: 0"
    )
    assert crc._row_cells(line) == [], "the prose arm must only ever see pipe-less lines"
    assert len(crc._FOUND_TOK.findall(line)) == 1, "one STRICT token — why the legacy arm missed"
    assert crc._joined_row(line) is True
    _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
    assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), refusals
    assert not any(r[0] == 0 for r in ordered), f"never a quiet row off the second half: {ordered}"


def test_a_prose_pass_mention_is_not_a_second_prose_row(tmp_path):
    """The mirror of the arm above: `_PASS_HEAD_TOK` matches a bare MENTION, so keying the prose
    arm on it would refuse an honest prose row that merely NAMES another round. The colon is the
    row-start signal and a mention has none, so the new arm stays silent here.

    The citation is word-trailed on purpose (`found: 4 issues`), which keeps the LEGACY strict arm
    off too — that arm's own behaviour on a readable citation is the adjudicated fail-CLOSED
    choice recorded in `_joined_row`'s docstring and pinned by
    `test_a_row_that_merely_cites_another_round_is_not_a_joined_row`; this test is about the prose
    arm not WIDENING it."""
    line = "Pass 3: method: re-derivation, found: 0, fixed: 0 — same surface as Pass 2, found: 4 issues"
    assert crc._row_cells(line) == []
    assert len(crc._PASS_HEAD_TOK.findall(line)) == 2, "two MENTIONS"
    assert len(crc._PASS_HEAD_COLON.findall(line)) == 1, "one row START — why the arm stays off"
    assert len(crc._LOOSE_FOUND.findall(line)) == 2, "two LOOSE counters — the arm's other input"
    assert crc._joined_row(line) is False


def test_arm_b_needs_a_found_left_of_the_empty_cell(tmp_path):
    """Round-5 item 4, condition 1. An empty finders cell with nothing counting to its left is not
    a join, however many counters the row CITES to its right. Both rows here were refused
    fleet-wide by b00a7755's `any(empty) and >=2 loose fixed` arm (BASE green) — honest receipts
    told to unjoin a line they never joined."""
    for honest in (
        "| Pass 3 | | found: 0 | fixed: 0 | method: round 2 read found: 2, fixed: 2 |",
        '| Pass 3 | | found: 0, fixed: 0 — verdict "found: 0, fixed: 0" |',
    ):
        cells = crc._row_cells(honest)
        assert any(not c.strip() for c in cells), "the empty cell IS present — position decides"
        assert crc._joined_row(honest) is False, honest


def test_arm_b_needs_the_cell_right_of_the_empty_one_to_open_with_the_counter(tmp_path):
    """Round-5 item 4, condition 2. A `found:` left of the empty cell is not enough: some cell
    right of it must actually OPEN with the counter.

    ⚠️ Round-6 item 1 REPLACED this fixture. It used to be
    `| R1 | found: 3 issues | fixed: 1 | | R2 | notes, fixed: 0 | found: 0 |`, asserted NOT joined
    because the counter sat in the third cell right of the gap and the window was `[i+1:i+3]`.
    That was the fail-open itself, pinned as if it were the contract: the CANONICAL ledger row is
    `| Pass N | finders | found: … |`, so the third cell is exactly where a real second row keeps
    its counter. The window is unbounded now, and the honest shape is one where NO cell right of
    the gap opens with a counter at all."""
    honest = "| R1 | found: 3 issues | fixed: 1 | | R2 | notes, fixed: 0 | the prior found: 0 |"
    assert any(not c.strip() for c in crc._row_cells(honest)), "the gap IS there"
    assert crc._joined_row(honest) is False, honest
    canonical = (
        "| Pass 3 | o | found: 5 issues | fixed: 0 | | Pass 4 (delta) | o | found: 0 | fixed: 0 |"
    )
    assert crc._joined_row(canonical) is True, (
        "the canonical second row keeps its counter in the THIRD cell — the old window missed it"
    )


def test_arm_b_joins_when_both_conditions_hold_including_a_second_row_with_no_fixed(tmp_path):
    """Round-5 item 4, condition 3 — and the RECORDED F4 shape, which b00a7755 MISSED because its
    arm demanded two loose `fixed:` and F4's second row states none. Dropping that condition (it
    was the untested one — removing it survived all 25 tests) is what lets F4 be seen."""
    for joined_line in (
        "| R1 | found: 3 issues | fixed: 1 | | R2 | found: 0 | fixed: 0 |",
        "| R1 | found: 5 issues | fixed: 0 | | R2 | found: 0 |",
    ):
        assert crc._joined_row(joined_line) is True, joined_line
        _t, _p, ordered, refusals = crc._ledger_shapes(joined_line + "\n")
        assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), (
            joined_line
        )
        assert not any(r[0] == 0 for r in ordered), f"no quiet row off the second half: {ordered}"


def test_the_prose_arm_never_reaches_a_cell_row_that_narrates_two_pass_heads(tmp_path):
    """Round-5 item 4, the prose arm's own untested condition — dropping its `not cells` guard
    survived all 30 tests, so nothing held the arm to pipe-LESS lines.

    A cell row decides its join structure by CELLS (arms A and B); `Pass N:` text inside a cell is
    NARRATION. Measured over the 275 committed receipts (36,465 fence-stripped lines) the guard
    changes 0 verdicts today — the corpus row it was written for,
    `2026-08-18-mega-enforcement-e2bf0f6e-review.md:304`, carries only ONE colon head — so the
    guard is a near-miss, not a live save, and this fixture is the shape that realizes it: a
    receipt whose notes cell quotes TWO rounds' counters, which any review OF this grammar
    will eventually contain."""
    narrating = (
        "| Pass 5 | delta | found: 0 | fixed: 0 | note: the round-4 log read "
        "Pass 3: found: 7 issues remain and Pass 4: found: 2 issues |"
    )
    assert crc._row_cells(narrating), "it IS a cell row — which is the whole point"
    assert len(crc._PASS_HEAD_COLON.findall(narrating)) == 2, "two NARRATED colon heads"
    assert len(crc._LOOSE_FOUND.findall(narrating)) >= 2, "and two loose counters"
    assert crc._joined_row(narrating) is False, "cells decide a cell row, never narrated prose"
    _t, _p, ordered, refusals = crc._ledger_shapes(narrating + "\n")
    assert refusals == [] and len(ordered) == 1, (refusals, ordered)


def test_the_canonical_second_row_keeps_its_counter_in_the_third_cell(tmp_path):
    """Round-6 item 1 — a fail-OPEN regression that round 5 introduced with `cells[i + 1 : i + 3]`.

    A real ledger row is `| Pass N | finders | found: … |` (this file's own `HEAD` fixture is
    exactly that), so a join puts the second row's counter THREE cells right of the gap — outside
    the two-cell window. Executed on the pin: every one of the five arms missed it, the row was
    kept as `(0, None, 0, None)` and `check_file` returned GREEN, grading the exit quiet off the
    join's second half. Counting cells was guessing at a layout; the left-side condition is what
    keeps the arm from over-reaching."""
    line = (
        "| Pass 3 | o | found: 5 issues | fixed: 0 | | Pass 4 (delta) | o | found: 0 | fixed: 0 |"
    )
    cells = crc._row_cells(line)
    gap = next(i for i, c in enumerate(cells) if not c.strip())
    assert not any(crc._CELL_OPENS_FOUND.match(c) for c in cells[gap + 1 : gap + 3]), (
        "the counter is OUTSIDE the old two-cell window — that is the whole defect"
    )
    assert crc._joined_row(line) is True
    _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
    assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), refusals
    assert not any(r[0] == 0 for r in ordered), f"never quiet off the second half: {ordered}"
    errs = _graded(tmp_path, line + "\n")
    assert any(e.startswith("Pass row refused:") for e in errs), errs


def test_a_citing_cell_right_of_a_gap_is_refused_fail_closed(tmp_path):
    """Round 7 REVERSES round 6 item 2, which was wrong. `_CELL_OPENS_FOUND` was given
    `_CELL_FOUND`'s stand-alone guard so a word-trailed citing cell would stop reading as a row
    start — but a citing cell and a REAL word-trailed second row are the same string shape, so the
    guard only chose which way to be wrong, and it chose fail-OPEN (see the test below).

    This file's adjudicated policy on that exact tie is fail-CLOSED: fencing a citation is one
    keystroke; a missed join grades a receipt quiet off another round's numbers. Both halves of
    the residual are asserted here so the choice is visible rather than inferred, and 0 of the 275
    committed receipts pay it."""
    assert crc._CELL_OPENS_FOUND.match(" found: 3 was cited ") is not None, "unguarded ON PURPOSE"
    for citing in (
        "| Pass 3 | o | found: 0 | fixed: 0 | | see Pass 2 | found: 3 was cited |",
        "| R1 | found: 1 | fixed: 0 | | note | found: 2 |",
    ):
        assert crc._joined_row(citing) is True, citing
        _t, _p, _o, refusals = crc._ledger_shapes(citing + "\n")
        assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), citing
        # Round 8: a refusal an honest author cannot act on is half a gate. The message must name
        # the remedy, and the remedy must be the one that WORKS — measured, not assumed.
        assert "reword the cited counter" in refusals[0], refusals[0]
    # The repair matrix, executed. Rewording clears every shape; fencing clears only the bare
    # `_empty_cell_join` row (elsewhere a backtick satisfies `_FOUND_TOK`'s trailing guard rather
    # than defeating it); dropping the `Pass N` mention clears only the prose line. The message
    # above may only ever name the first.
    reworded = "| Pass 3 | o | found: 0 | fixed: 0 | | see Pass 2 | raised 3 as cited |"
    assert crc._joined_row(reworded) is False, "the named remedy must actually repair the row"
    assert _graded(tmp_path, reworded + "\n") == [], "and leave the receipt clean"
    fenced = "| Pass 3 | o | found: 0 | fixed: 0 | | see Pass 2 | `found: 3` was cited |"
    assert crc._joined_row(fenced) is True, "fencing does NOT repair this shape — never say it does"
    dropped = "| Pass 3 | o | found: 0 | fixed: 0 | | see earlier | found: 3 was cited |"
    assert crc._joined_row(dropped) is True, "nor does dropping the mention — the arm has no head"


def test_a_head_less_join_whose_second_row_is_word_trailed_is_still_seen(tmp_path):
    """Round-7 item 1, the fail-OPEN round 6's guard re-opened — the round-4 hole, one arm over.

    A HEAD-LESS second row states its counter and nothing else (`| found: 0 issues | fixed: 0 |`),
    so guarding `_CELL_OPENS_FOUND` against a trailing word made the row invisible: executed on
    3ddcb146, `_joined_row` was False, `_ledger_shapes` returned `ordered=[]` and `refusals=[]` —
    the line DROPPED WHOLE — and `check_file` came back GREEN off the previous quiet round. The
    `confirmed:` variant of the second row behaves identically, so both are pinned."""
    for second in ("| found: 0 issues | fixed: 0 |", "| found: 0 issues, confirmed: 0, fixed: 0 |"):
        line = "| Pass 3 (a) | found: 5 issues | fixed: 1 | " + second
        assert crc._joined_row(line) is True, line
        _t, _p, ordered, refusals = crc._ledger_shapes(line + "\n")
        assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), line
        assert not any(r[0] == 0 for r in ordered), f"never quiet off the second half: {ordered}"
        errs = _graded(tmp_path, line + "\n")
        assert any(e.startswith("Pass row refused:") for e in errs), (
            f"a dropped join is a GREEN receipt graded off the previous round: {errs}"
        )


def test_the_corpus_is_pinned_to_the_base_sha_not_the_working_tree(tmp_path):
    """Round-6 item 3 — the landmine under the first merge. The invariance tests grade the current
    gate against the gate at `BASE_SHA`, so the corpus must be the corpus that SHA saw. Reading
    live files meant this plan's own receipts (closing rows carrying `confirmed: 0`, quiet under
    the new grammar and not the old) would red the hub suite for every session the moment they
    landed, and would rebase the denominator silently besides."""
    files = _corpus()
    assert len(files) == CORPUS_AT_BASE, len(files)
    assert not any(str(p).startswith(str(REPO / "docs")) for p in files), (
        "a pinned receipt must never resolve into the live working tree"
    )
    live = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "docs/development/reviews/*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    # Equal TODAY; the pin is what keeps the tests correct on the day it stops being equal.
    assert len(live) >= CORPUS_AT_BASE, (len(live), CORPUS_AT_BASE)
