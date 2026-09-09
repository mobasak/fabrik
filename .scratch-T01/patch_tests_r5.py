import pathlib

P = pathlib.Path("tests/enforcement/test_review_confirmed_grammar.py")
s = P.read_text(encoding="utf-8")


def sub(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, f"{label}: {n} hits"
    s = s.replace(old, new)
    print(label, "applied")


# --- item 2: make the fall-through test DRIVE the branch it names -------------------------
old_test_start = s.index(
    "def test_a_line_with_no_first_run_is_not_joined_and_still_ends_its_table(tmp_path):"
)
old_test_end = s.index("def test_all_three_readers_report_a_joined_row(tmp_path):")
new_tests = '''def test_a_line_with_no_first_run_is_not_joined_and_still_ends_its_table(tmp_path):
    """Round-3 D2. `| stage | found: 3 issues | found: 4 issues |` matched the unguarded cell
    opening twice, so it emitted a refusal while `_first_run` returned None — nothing was kept
    AND the `continue` skipped the table flush, so two adjacent ledgers merged into ONE group and
    the multi-group guard was disarmed, against this file's own "never silently dropped"
    contract. It carries no row STRUCTURE (no head cell, no empty cell, one strict opening), so
    it is not joined at all and takes the ordinary path."""
    stage = "| stage | found: 3 issues | found: 4 issues |\\n"
    assert crc._joined_row(stage.rstrip("\\n")) is False
    _t, _p, ordered, refusals = crc._ledger_shapes(stage)
    assert refusals == [] and ordered == [], (refusals, ordered)
    sandwich = (
        "| Pass 1 | f | found: 0 | fixed: 0 |\\n" + stage + "| Pass 2 | f | found: 0 | fixed: 0 |\\n"
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
    line = joined.rstrip("\\n")
    assert crc._joined_row(line) is True, "two head cells + two loose counters is a join"
    assert crc._first_run(line, crc._second_row_pos(line)) is None, "no READABLE first run"
    _t, _p, ordered, refusals = crc._ledger_shapes(joined)
    assert ordered == [], f"never borrow the second row's counters: {ordered}"
    assert refusals and refusals[0].startswith("two ledger rows on ONE physical line"), refusals
    ledger = (
        "| Pass 1 | f | found: 0 | fixed: 0 |\\n" + joined + "| Pass 7 | f | found: 0 | fixed: 0 |\\n"
    )
    tables, _p2, ordered2, refusals2 = crc._ledger_shapes(ledger)
    assert [len(t) for t in tables] == [1, 1], f"the table boundary must survive: {tables}"
    assert len(ordered2) == 2 and len(refusals2) == 1, (ordered2, refusals2)


def test_a_word_trailed_counter_never_hides_a_join(tmp_path):
    """Round-4 item 1 — the REGRESSION `(?!\\\\s*\\\\w)` on the cell opening introduced: one
    word-trailed counter made a genuinely joined line invisible, and the receipt then graded
    QUIET off its SECOND half. Detection is on the row STRUCTURE now (head cells, the empty cell
    a join leaves behind), so how READABLE a counter is cannot decide how many rows there are."""
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
    ):
        line = _joined(a, b).rstrip("\\n")
        assert crc._joined_row(line) is True, label
        _t, _p, ordered, refusals = crc._ledger_shapes(line + "\\n")
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


'''
s = s[:old_test_start] + new_tests + s[old_test_end:]
print("tests rewritten")

P.write_text(s, encoding="utf-8")
