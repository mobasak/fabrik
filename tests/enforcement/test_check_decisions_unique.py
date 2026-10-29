"""Decision-ledger duplicate-id guard (D-057 sequencing; upstream 01M1CBJWQS).

Concurrent lanes minting max+1 from their own trees collided 4x/day at wef; the check
detects the collision at the gate. The load-bearing property, learned from wef's hand
repair (01M1CW4S): it keys on the ID CELL of a table row and NEVER counts prose
mentions — repos carry 20+ legitimate prose references to ids, including narrative
about past collisions, and a naive matcher reds on all of them.
"""

from pathlib import Path

import pytest
import scripts.enforcement.check_decisions_unique as _mod
from scripts.enforcement.check_decisions_unique import (
    _DELIMITER,
    find_duplicates,
    find_rows_outside_the_table,
    main,
)


@pytest.fixture(autouse=True)
def _isolated_shape_baseline(tmp_path, monkeypatch):
    # main() reads TWO globals: LEDGER (relative, so a test redirects it or chdirs) and the advisory
    # shape leg's _SHAPE_BASELINE (absolute, parents[2] of the module), which neither move reaches.
    # Left alone, every main() call grades its fixture ledger against the hub's real baseline and
    # prints ⚠ ABSENT for ids that exist in the real ledger but not in the fixture — red since
    # ed461e243 added the leg (W-62281917). An empty baseline keeps the leg quiet in every test.
    base = tmp_path / "shape-baseline.json"
    base.write_text('{"malformed_ids": []}')
    monkeypatch.setattr(_mod, "_SHAPE_BASELINE", base)


def test_duplicate_id_cells_detected():
    text = (
        "| id | when |\n"
        "|---|---|\n"
        "| D-023 | 2026-08-31 | operator | approve |\n"
        "| D-023 | 2026-08-31 | agent | identity |\n"
        "| D-024 | 2026-08-31 | agent | briefs |\n"
    )
    assert find_duplicates(text) == {"D-023": 2}


def test_prose_mentions_never_count():
    # The collision narrative itself mentions ids — the wef repair kept those
    # lines verbatim on purpose; the matcher must not see them.
    text = (
        "| D-023 | 2026-08-31 | operator | approve |\n"
        "The collision (D-023 · D-023 · D-023) was repaired; supersedes D-023's half.\n"
        "  | D-023 | indented, not a row start |\n"
    )
    assert find_duplicates(text) == {}


def test_clean_ledger_is_silent():
    text = "| D-001 | x |\n| D-002 | y |\n"
    assert find_duplicates(text) == {}


def test_padded_and_bold_id_cells_still_match():
    # Nothing enforces the ledger's cell spacing; a table formatter's padding
    # or a bold id must not become a silent false negative (review finding).
    text = "|  D-003  | padded |\n| **D-003** | bold |\n"
    assert find_duplicates(text) == {"D-003": 2}


def test_failure_lines_carry_the_gate_prefix(tmp_path, monkeypatch, capsys):
    # The visibility contract, now at the BLOCKING tier (promoted 2026-09-04, the second half of
    # the D-057 sequencing): failure lines carry ✗ so they reach --json's failures. The original
    # defect this pins is unchanged in shape — a bare "WARN:"/unprefixed line is JSON-invisible.
    import scripts.enforcement.check_decisions_unique as mod

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text("| D-001 | a |\n| D-001 | b |\n")
    monkeypatch.setattr(mod, "LEDGER", tmp_path / "docs" / "DECISIONS.md")
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert out.count("✗") >= 2
    # the line that NAMES the id is the actionable one; a count of ✗ lines cannot see it lose its prefix
    assert any(ln.startswith("✗") and "D-001 appears 2x" in ln for ln in out.splitlines())
    assert "WARN:" not in out and "⚠" not in out


def test_gate_registers_the_check_as_blocking():
    # Promoted from warn_only on 2026-09-04 after wef's repair reply landed and the fleet was
    # re-measured (0 duplicates in 49 ledgers, so blocking reds no repo). A regression to
    # warn_only reopens the hole the finding named: a duplicate id survives every gate.
    gate = (Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py").read_text(
        encoding="utf-8"
    )
    block = gate[gate.index("check_decisions_unique.py") :]
    assert "warn_only" not in block[:300], "the duplicate-id check blocks; it does not advise"


def test_a_duplicate_id_now_reds_the_gate_not_just_warns(tmp_path, monkeypatch):
    """This landed WARN-first per the D-057 sequencing, explicitly "after wef's repair reply". That
    reply arrived (01M1MDXY6N6DD0CEAZ9M3778AH) and the promotion was re-measured before flipping:
    0 duplicate ids across 49 fleet ledgers, so blocking reds no repo at landing. A duplicate id
    breaks every citation of it, and while this was advisory it survived every gate."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    led = tmp_path / "docs" / "DECISIONS.md"

    led.write_text("| D-001 | a |\n| D-002 | b |\n", encoding="utf-8")
    assert main() == 0, "unique ids stay green"

    led.write_text("| D-001 | a |\n| D-002 | b |\n| D-002 | c |\n", encoding="utf-8")
    assert main() == 1, "a duplicate id must RED the gate, not merely warn"

    led.write_text(
        "| D-001 | a |\n\nSee D-001 and D-001 again in this narrative about D-001.\n",
        encoding="utf-8",
    )
    assert main() == 0, "prose occurrences are not id cells — the wef repair report's own lesson"

    led.unlink()
    assert main() == 0, "no ledger is not a failure"


# --------------------------------------------------------------------------------------
# T12.12 (01M295S5G, 01M1T1134) — a row ABOVE the delimiter is outside the table.
# --------------------------------------------------------------------------------------

_ABOVE = (
    "# Decisions\n"
    "\n"
    "| D-999 | x | y | a row ABOVE the delimiter | z | w |\n"
    "\n"
    "| id | when | who | what | why | where |\n"
    "|---|---|---|---|---|---|\n"
    "| D-001 | a | b | c | d | e |\n"
)


def test_a_row_above_the_delimiter_is_reported_with_its_line():
    """This check is a LINE regex by design — it must not red on the dozens of legitimate prose
    mentions a repo carries — and the cost of that design is that it had no idea where the table
    IS. A row placed above the `|---|` delimiter is outside the table: no renderer shows it and no
    reader finds it, and the duplicate check blessed it (brand-identity-creator's reported shape).
    Uniqueness is not all addressability needs."""
    stray = find_rows_outside_the_table(_ABOVE)
    assert stray == [(3, "D-999")], stray
    assert find_duplicates(_ABOVE) == {}, "it is not a duplicate — that is the whole point"


def test_rows_inside_the_table_are_never_reported():
    inside = "# Decisions\n\n| id | when |\n|---|---|\n| D-001 | a |\n| D-002 | b |\n"
    assert find_rows_outside_the_table(inside) == []


def test_a_ledger_with_no_delimiter_is_not_this_checks_verdict():
    """No delimiter means no table to be outside of. That is a different defect and this check
    does not claim to own it — silence here, rather than reporting every row as stray."""
    assert find_rows_outside_the_table("# Decisions\n\n| D-001 | a |\n") == []


def test_a_stray_row_reds_the_gate(tmp_path, monkeypatch, capsys):
    """It has to change the EXIT CODE or it is a comment. Measured before making it blocking:
    0 of 49 fleet ledgers carry a stray row today, so this reds no repo on landing day — the same
    denominator that justified promoting the duplicate half."""
    import scripts.enforcement.check_decisions_unique as mod

    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(_ABOVE, encoding="utf-8")
    monkeypatch.setattr(mod, "LEDGER", ledger)
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "ABOVE the table delimiter" in out and "D-999" in out
    assert "placement fix, not a content edit" in out, (
        "the message must say the cells stay immutable, or the repair edits history"
    )


def test_the_live_hub_ledger_has_no_stray_rows():
    """The live assertion, not a fixture's."""
    text = Path("/opt/fabrik/docs/DECISIONS.md").read_text(encoding="utf-8")
    assert find_rows_outside_the_table(text) == []


def test_a_fake_delimiter_above_a_stray_row_no_longer_hides_it():
    """Phase E review: `_DELIMITER` took the FIRST dash-ish line anywhere, so a two-character
    `| |` — an empty data row — was read as the delimiter and silenced the check for every row
    below it. Executed: with `| |` above a stray row the check reported nothing; moved below it,
    the stray was found. The pattern is now anchored to a real header row above it, which makes
    the cheapest fake cost as much as the real fix."""
    # ⚠️ THE FIXTURE MUST MATCH `_DELIMITER`, or this grader tests the OTHER half of the fix.
    # The first cut used `| |`, which the repaired pattern rejects outright on the dash
    # requirement — so the anchor was never reached and the test passed with the anchor DELETED
    # (executed both arms, round 3 of the Phase E review: `[(4, 'D-001')]` either way). `| - |` is
    # a legal delimiter cell and is NOT preceded by a header row, so the anchor is what decides.
    fake = "# Decisions\n\n| - |\n| D-001 | a |\n\n| id | when |\n|---|---|\n| D-002 | b |\n"
    assert _DELIMITER.match("| - |"), "the fixture must be a real delimiter or the anchor is idle"
    assert find_rows_outside_the_table(fake) == [(4, "D-001")], find_rows_outside_the_table(fake)

    # the other half of the same fix, graded separately: a cell with no dashes is not a delimiter
    assert not _DELIMITER.match("| |")
    two_char = "# Decisions\n\n| |\n| D-001 | a |\n\n| id | when |\n|---|---|\n| D-002 | b |\n"
    assert find_rows_outside_the_table(two_char) == [(4, "D-001")]


def test_the_anchored_delimiter_still_finds_a_real_stray_and_stays_quiet_when_clean():
    real = "# Decisions\n\n| D-999 | x |\n\n| id | when |\n|---|---|\n| D-001 | a |\n"
    assert find_rows_outside_the_table(real) == [(3, "D-999")]
    clean = "# Decisions\n\n| id | when |\n|---|---|\n| D-001 | a |\n"
    assert find_rows_outside_the_table(clean) == []


def test_the_cobra_path_is_written_down_where_the_next_reader_finds_it():
    """FIX DIRECTIVE 5: for every gate introduced, the cheapest way to satisfy it WITHOUT the
    outcome is recorded in the same change. The measured-fire-rate half was done when this landed;
    this half was skipped and the review caught it."""
    from pathlib import Path as _Path

    src = _Path("/opt/fabrik/scripts/enforcement/check_decisions_unique.py").read_text(
        encoding="utf-8"
    )
    body = src.split("def find_rows_outside_the_table")[1].split('"""')[1]
    assert "cobra-effect" in body and "cheapest" in body.lower(), body[-400:]


_SHAPE_HEAD = "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"


def test_a_pipe_inside_a_code_span_is_not_a_cell_boundary():
    """intel 01M4405E: D-285, D-303, D-305, D-372, D-423 and D-558 carry `a|b` inside code spans and
    were reported malformed though each has six cells — the counter must agree with
    tests/test_decisions_table_shape.py, which strips code spans and `\\|` before counting."""
    from scripts.enforcement.check_decisions_unique import malformed_ids

    ok = (
        _SHAPE_HEAD + "| D-900 | 2026-10-04 | infra | ran `a|b|c` and a\\|b | a reason | `x.py` |\n"
    )
    short = _SHAPE_HEAD + "| D-901 | 2026-10-04 | infra | what | why |\n"
    assert malformed_ids(ok) == {}
    assert "D-901" in malformed_ids(short)


def test_a_cell_of_only_punctuation_reads_as_empty():
    """intel's addendum: `—` in why/where is the one-character padding the docstring warns about."""
    from scripts.enforcement.check_decisions_unique import malformed_ids

    for filler in ("—", "-", " — ", "…", "n/a"):
        row = f"| D-902 | 2026-10-04 | infra | what | {filler} | `x.py` |\n"
        got = malformed_ids(_SHAPE_HEAD + row)
        if filler == "n/a":
            assert got == {}, (
                "a word, however thin, is content — the line is drawn at no word at all"
            )
        else:
            assert "D-902" in got, filler


# W-27db8c35: the mask read code spans with a one-backtick regex, so a run of two or more backticks
# paired with the wrong partner. D-1159 (a quoted triple-backtick closer) read 4 cells against 6.
_LONG_RUN_ROWS = {
    "triple run (D-1159)": (
        '| D-903 | 2026-10-24 | infra | the "``` info" closer and `x` | a reason | `y.py` |'
    ),
    "double span holding a pipe": (
        "| D-904 | 2026-10-24 | infra | ran ``a|b`` here | a reason | `y.py` |"
    ),
    "double span holding a backtick": (
        "| D-905 | 2026-10-24 | infra | the ``a`b`` span | a reason | `y.py` |"
    ),
}


@pytest.mark.parametrize("row", _LONG_RUN_ROWS.values(), ids=_LONG_RUN_ROWS.keys())
def test_a_backtick_run_pairs_only_with_a_run_of_its_own_length(row):
    from scripts.enforcement.check_decisions_unique import malformed_ids

    assert malformed_ids(_SHAPE_HEAD + row + "\n") == {}


def test_an_escaped_backtick_opens_no_span():
    """A backslash before a backtick makes it literal (GFM, and decisions.py's _rows split), so the
    pipe after it is a real separator: this row has SEVEN cells and must not read as six."""
    from scripts.enforcement.check_decisions_unique import _cells

    row = "| D-906 | 2026-10-24 | infra | \\`a | b\\` | a reason | `y.py` |"
    assert len(_cells(row)) == 7


def test_a_short_row_with_a_long_backtick_run_is_still_malformed():
    from scripts.enforcement.check_decisions_unique import malformed_ids

    short = _SHAPE_HEAD + "| D-907 | 2026-10-24 | infra | the ``` x and `y` | a reason |\n"
    assert malformed_ids(short) == {"D-907": "5 cells, header has 6"}


def test_a_long_run_pairs_across_cells_by_design():
    """The STATED COST of pairing over the whole row (intel 01M4405E keeps a pipe inside a span as
    text, so spans are found before the split): a lone double run in one cell pairs with a double
    span two cells later and hides both separators between them. 0 of 2896 D-rows across the 51
    /opt/*/docs/DECISIONS.md ledgers changed cell count on 2026-10-24; pinned so a change to it is
    a decision, not an accident."""
    from scripts.enforcement.check_decisions_unique import _cells

    assert len(_cells("| D-908 | 2026-10-24 | infra | use `` here | why | ``x`` where |")) == 4


def test_the_shape_test_counts_through_the_checkers_mask():
    """tests/test_decisions_table_shape.py counts bare pipes with the checker's own mask, so a pipe
    inside a code span and an escaped pipe are text to both; a row missing its trailing pipe, or
    carrying a doubled one, still counts every bare pipe it has."""
    import tests.test_decisions_table_shape as shape

    assert shape._bare_pipes("| D-1 | d | w | ran `a|b` and a\\|b | why | where |") == 7
    assert shape._bare_pipes("| D-1 | d | w | what | why | where") == 6
    assert shape._bare_pipes("| D-1 | d | w | what | why | where ||") == 8
    assert shape._bare_pipes(_LONG_RUN_ROWS["triple run (D-1159)"]) == 7


def test_the_live_hub_ledger_masks_what_decisions_py_masks():
    """On every row of the hub ledger the checker hides exactly the pipes that decisions.py's own
    code-span reader (the ledger writer's) puts inside a span, plus every escaped pipe."""
    import scripts.decisions as dec
    from scripts.enforcement.check_decisions_unique import _masked

    text = (Path(__file__).resolve().parents[2] / "docs" / "DECISIONS.md").read_text(
        encoding="utf-8"
    )
    rows = [ln for ln in text.splitlines() if ln.startswith("| D-")]
    assert len(rows) > 1000
    for ln in rows:
        spans = dec._code_span_ranges(ln)
        out, i = [], 0
        while i < len(ln):
            if ln[i] == "\\" and ln[i + 1 : i + 2] == "|":
                out.append("\0")
                i += 2
                continue
            inside = any(a <= i < b for a, b in spans)
            out.append("\0" if ln[i] == "|" and inside else ln[i])
            i += 1
        assert _masked(ln) == "".join(out), ln[:40]


# --------------------------------------------------------------------------------------
# W-c25fd20f — the seven gaps the W-27db8c35 review found in the other legs.
# --------------------------------------------------------------------------------------


def _row(did: str, what: str = "what") -> str:
    return f"| {did} | 2026-10-29 | infra | {what} | why | `x.py` |\n"


def test_the_shape_ratchet_reports_each_state(tmp_path, monkeypatch, capsys):
    """Gap 1: the advisory ratchet had no test — `gone = []`, `regressed = []` and an early return
    all survived the file. Each state is graded by the line it prints."""
    base = tmp_path / "baseline.json"
    monkeypatch.setattr(_mod, "_SHAPE_BASELINE", base)
    short = "| D-002 | 2026-10-29 | infra | what | why |\n"

    _mod.check_row_shape(_SHAPE_HEAD + _row("D-001") + short)  # no baseline: seeds, blocks nothing
    out = capsys.readouterr().out
    assert "seeding baseline with 1 malformed row(s)" in out
    # review pass 1, A-haiku-8: the line it tells the operator to write must parse — a Python list
    # repr (`['D-002']`) is no JSON, so the copied baseline never armed the ratchet
    import json
    import re

    seed = re.search(r"(\{\"malformed_ids\": .*\}) to arm", out).group(1)
    assert json.loads(seed) == {"malformed_ids": ["D-002"]}

    base.write_text('{"malformed_ids": ["D-002"]}')
    _mod.check_row_shape(_SHAPE_HEAD + _row("D-001") + short)
    assert "D-002 still malformed — 5 cells, header has 6" in capsys.readouterr().out

    _mod.check_row_shape(_SHAPE_HEAD + _row("D-001") + short + "| D-003 | a |\n")
    assert "1 row(s) became malformed since the baseline: D-003" in capsys.readouterr().out

    _mod.check_row_shape(_SHAPE_HEAD + _row("D-001"))  # D-002 deleted, not repaired
    assert "ABSENT rather than repaired (D-002)" in capsys.readouterr().out

    _mod.check_row_shape(_SHAPE_HEAD + _row("D-001") + _row("D-002"))  # repaired
    out = capsys.readouterr().out
    assert "decision-shape: OK — 1 baseline row(s)" in out and "ABSENT" not in out


def test_a_stray_row_in_a_fake_table_above_the_ledger_is_reported():
    """Gap 2: a header plus delimiter typed above a stray row made the stray part of "the table"
    (the FIRST confirmed delimiter). The ledger table is the one holding the most D-rows."""
    fake = (
        "| a | b |\n|---|---|\n"
        + _row("D-999")
        + "\n"
        + _SHAPE_HEAD
        + _row("D-001")
        + _row("D-002")
    )
    assert find_rows_outside_the_table(fake) == [(3, "D-999")]
    # a tie goes to the LAST table — the ledger table closes its file (293 of 293 ledgers)
    tie = "| a | b |\n|---|---|\n" + _row("D-999") + "\n" + _SHAPE_HEAD + _row("D-001")
    assert find_rows_outside_the_table(tie) == [(3, "D-999")]
    # a row after the table, past a blank line, renders as a paragraph: it is outside too
    after = _SHAPE_HEAD + _row("D-001") + "\n" + _row("D-002")
    assert find_rows_outside_the_table(after) == [(5, "D-002")]


def test_an_indented_row_inside_the_table_counts():
    """Gap 3: up to 3 spaces of indent is still a table row (CommonMark), so a duplicate there was
    a silent miss. An indented line OUTSIDE any table stays prose (test_prose_mentions_never_count)."""
    text = _SHAPE_HEAD + _row("D-001") + "  " + _row("D-001")
    assert find_duplicates(text) == {"D-001": 2}
    assert "D-001" in _mod.malformed_ids(_SHAPE_HEAD + _row("D-002") + "   | D-001 | x |\n")


def test_a_fenced_row_is_not_a_row():
    """Gap 4: a ledger quoting a row inside a code fence (an example, a repair note) red as a
    duplicate of the row it quotes."""
    text = _SHAPE_HEAD + _row("D-001") + "\n```\n" + _row("D-001") + "```\n"
    assert find_duplicates(text) == {}
    assert find_rows_outside_the_table(text) == []


def test_main_from_a_subdirectory_grades_the_repo_ledger(tmp_path):
    """Gap 5: LEDGER was cwd-relative, so a run from docs/ found no ledger and passed."""
    import subprocess
    import sys

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text(_SHAPE_HEAD + _row("D-001") + _row("D-001"))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=60)
    script = Path(_mod.__file__).resolve()
    run = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path / "docs",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "D-001 appears 2x" in run.stdout


def test_a_short_header_still_reports_the_duplicate(tmp_path, monkeypatch, capsys):
    """Gap 6: a header under 6 cells raised IndexError in the advisory leg, so the run crashed
    before the blocking legs printed what was wrong."""
    short = "| id | what |\n|---|---|\n| D-001 | x |\n| D-001 | y |\n"
    assert _mod.malformed_ids(short) == {}
    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(short)
    monkeypatch.setattr(_mod, "LEDGER", ledger)
    assert _mod.main() == 1
    assert "D-001 appears 2x" in capsys.readouterr().out


def test_annotated_and_padded_ids_share_one_key():
    """Gap 7: an id cell with text after the id was not a row at all, and D-1 / D-001 were two
    keys. The first spelling seen names the duplicate."""
    annotated = (
        _SHAPE_HEAD
        + _row("D-001")
        + "| D-001 (amended) | 2026-10-29 | infra | w | why | `x.py` |\n"
    )
    assert find_duplicates(annotated) == {"D-001": 2}
    assert find_duplicates(_SHAPE_HEAD + _row("D-001") + _row("D-1")) == {"D-001": 2}
    # a cell that only STARTS with the id's letters is no id: `D-1x`, `D-1.5`, `D-1-2` are not D-1
    for other in ("D-1x", "D-1.5", "D-1.1", "D-1-2", "D-1/2"):
        assert find_duplicates(_SHAPE_HEAD + _row("D-1") + f"| {other} | a |\n") == {}, other


def test_an_indented_duplicate_in_another_table_reds_twice():
    """Design critique C2: counting indented rows only inside the LEDGER table moved gap 3's miss
    into a second table. Any table body's rows count; outside the ledger they are also stray."""
    text = _SHAPE_HEAD + _row("D-5") + _row("D-6") + "\n| a | b |\n|---|---|\n  " + _row("D-5")
    assert find_duplicates(text) == {"D-5": 2}
    assert find_rows_outside_the_table(text) == [(8, "D-5")]


def test_the_table_body_ends_where_the_renderer_ends_it():
    """Design critiques C3 (Opus) and 1 (Fable), settled by rendering with markdown-it (GFM tables,
    2026-10-29): a tab or a 4-space indent ENDS the table — that line is an indented code block and
    the rows after it render outside the table — while a row with no leading pipe continues it."""
    for indent in ("\t", "    "):
        text = _SHAPE_HEAD + _row("D-1") + indent + _row("D-2") + _row("D-3")
        assert find_rows_outside_the_table(text) == [(5, "D-3")], repr(indent)
        assert find_duplicates(text + _row("D-2")) == {}, "the code-block copy is an example"
    no_pipe = _SHAPE_HEAD + _row("D-1") + "D-2 | d | w | what | why | where\n" + _row("D-3")
    assert find_rows_outside_the_table(no_pipe) == []


def test_a_slightly_indented_stray_is_still_a_stray():
    """Fable critique 3: an indented row outside the table is prose to the duplicate leg, so a one-
    space indent would have hidden a stray — yet no renderer shows it as a row."""
    text = " " + _row("D-9") + "\n" + _SHAPE_HEAD + _row("D-1")
    assert find_rows_outside_the_table(text) == [(1, "D-9")]


def test_a_fence_that_swallows_the_table_does_not_silence_it():
    """Fable critique 3: an unclosed fence above the ledger pairs with any later fence line, and
    blanking that block would hide every duplicate — a block holding a header and delimiter is kept."""
    text = "```\n" + _SHAPE_HEAD + _row("D-1") + _row("D-1") + "```\n"
    assert find_duplicates(text) == {"D-1": 2}


def test_a_duplicate_written_two_ways_names_both(tmp_path, monkeypatch, capsys):
    """Fable critique 7: `D-1` beside `D-001` is one id; the line must name both spellings, or the
    repairer greps one row."""
    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(_SHAPE_HEAD + _row("D-001") + _row("D-1"))
    monkeypatch.setattr(_mod, "LEDGER", ledger)
    assert _mod.main() == 1
    assert "id D-001 appears 2x (written D-001 and D-1)" in capsys.readouterr().out


def test_a_crlf_ledger_reads_as_lf():
    """Design critique C4: `_fences` admits no `\\r` in a closer, so a CRLF fence was never blanked —
    the fenced copy red as a duplicate AND as a stray."""
    text = (_SHAPE_HEAD + _row("D-1") + "\n```\n" + _row("D-1") + "```\n").replace("\n", "\r\n")
    assert find_duplicates(text) == {}
    assert find_rows_outside_the_table(text) == []


def test_a_delimiter_line_inside_the_body_opens_no_table():
    """Design critique C10: a `| - |`-shaped row inside the ledger body is a row of that table, not
    the delimiter of a second one a tie could prefer."""
    text = _SHAPE_HEAD + _row("D-1") + "| --- | --- |\n" + _row("D-2")
    assert find_rows_outside_the_table(text) == []
    assert [i for _, i in _mod._all_row_ids(text)] == ["D-1", "D-2"]
    # where it would decide: a non-D row then a delimiter-shaped row makes an inner "table" that
    # TIES the ledger on D-rows, and the tie-to-last rule would read its 2-cell header as the ledger's
    tie = _SHAPE_HEAD + "| x | y |\n|---|---|\n" + _row("D-1")
    assert _mod.malformed_ids(tie) == {}


def test_a_table_with_no_d_row_is_not_the_ledger():
    """Design critiques C5 (Opus) and 4 (Fable): a status legend must not become "the ledger table"
    of a ledger whose rows sit under an unconfirmed header (fabrik-lib's shape plus one legend) —
    every real row would red as stray. Stated cost: a stray above a zero-row table goes quiet."""
    legend = "| status | meaning |\n|---|---|\n| open | live |\n\n| id | when |\n" + _row("D-1")
    assert find_rows_outside_the_table(legend + _row("D-2")) == []


def test_the_stray_message_names_where_the_row_is(tmp_path, monkeypatch, capsys):
    """Design critique C6: a row AFTER the table was told to move "below the |---| line" — where
    it already was."""
    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(_row("D-9") + "\n" + _SHAPE_HEAD + _row("D-1") + "\n" + _row("D-2"))
    monkeypatch.setattr(_mod, "LEDGER", ledger)
    assert _mod.main() == 1
    out = capsys.readouterr().out.splitlines()
    assert any("D-9 sits ABOVE the table delimiter" in ln for ln in out), out
    assert any("D-2 sits outside the ledger table (after it" in ln for ln in out), out
    assert all(
        "placement fix, not a content edit" in ln for ln in out if ":" in ln and "row D-" in ln
    )


def test_main_from_a_subdirectory_under_a_hook_environment(tmp_path):
    """Design critique C1: a git hook exports GIT_DIR, under which `--show-toplevel` answers the cwd
    itself — the docs/ run found no ledger and passed again."""
    import os
    import subprocess
    import sys

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text(_SHAPE_HEAD + _row("D-001") + _row("D-001"))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=60)
    env = {**os.environ, "GIT_DIR": str(tmp_path / ".git")}
    run = subprocess.run(
        [sys.executable, str(Path(_mod.__file__).resolve())],
        cwd=tmp_path / "docs",
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert run.returncode == 1, run.stdout + run.stderr


def test_a_ledger_in_the_cwd_wins_over_the_enclosing_repo(tmp_path, monkeypatch):
    """The cwd is asked first, so a fixture nested inside another repo keeps grading its own ledger
    (the liveness canary's copy form runs that way when TMPDIR sits inside a work tree)."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=60)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text(_SHAPE_HEAD + _row("D-1") + _row("D-1"))
    fixture = tmp_path / "fixture"
    (fixture / "docs").mkdir(parents=True)
    (fixture / "docs" / "DECISIONS.md").write_text(_SHAPE_HEAD + _row("D-1"))
    monkeypatch.chdir(fixture)
    assert main() == 0


# What markdown-it (GFM tables) does with each line placed between a ledger row and the next row:
# True = the next row is still in the table (review pass 1, A-sonnet-1; executed 2026-10-29).
_RENDER_CONTINUES = {
    "# h | x": False,
    "#h | x": True,
    "> q | x": False,
    "  > q | x": False,
    "- li | x": False,
    "* * * | x": False,
    "1. a | x": False,
    "1) a | x": False,
    "```| x": False,
    "~~~ | x": False,
    "<div> | x": False,
    "<DIV> | x": False,
    "</p> | x": False,
    "<!-- c --> | x": False,
    "<?php | x": False,
    "---|x": True,
    "-x | y": True,
    "12a | b": True,
    "<span> | x": True,
    "<a | b": True,
    "D-9 | no lead pipe |": True,
}


@pytest.mark.parametrize("line", sorted(_RENDER_CONTINUES))
def test_a_line_that_starts_another_block_ends_the_table(line):
    """Review pass 1, A-sonnet-1: any piped line continued the body, so a row after a heading, a
    quote, a list item, a fence or an HTML block — outside the rendered table — passed as a row."""
    text = _SHAPE_HEAD + _row("D-1") + line + "\n" + _row("D-2")
    expected = [] if _RENDER_CONTINUES[line] else [(5, "D-2")]
    assert find_rows_outside_the_table(text) == expected


def test_the_render_table_matches_markdown_it():
    """The expectations above are the renderer's, not the checker's — re-read where it is installed."""
    markdown_it = pytest.importorskip("markdown_it")
    md = markdown_it.MarkdownIt("commonmark").enable("table")
    for line, continues in _RENDER_CONTINUES.items():
        html = md.render(_SHAPE_HEAD + _row("D-1") + line + "\n" + _row("D-2"))
        assert ("<td>D-2</td>" in html) is continues, line


def test_the_blocking_lines_print_before_the_advisory_leg(tmp_path, monkeypatch, capsys):
    """Review pass 1, B-sonnet-1: gap 6's fix moved the advisory ratchet AFTER the ✗ lines, so a
    failure in it can no longer hide them — nothing graded that order."""
    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(_SHAPE_HEAD + _row("D-1") + _row("D-1"))
    monkeypatch.setattr(_mod, "LEDGER", ledger)

    def boom(text):
        raise RuntimeError("advisory leg failed")

    monkeypatch.setattr(_mod, "check_row_shape", boom)
    with pytest.raises(RuntimeError):
        _mod.main()
    assert "D-1 appears 2x" in capsys.readouterr().out


def test_the_table_reading_legs_read_the_ledger_rows_only():
    """Review pass 1, B-sonnet-2/3: a stray row is the stray leg's — the shape ratchet neither
    grades it as malformed nor counts it as present (a deleted ledger row must still read ABSENT)."""
    text = "| D-9 | short |\n\n" + _SHAPE_HEAD + _row("D-1")
    assert _mod.malformed_ids(text) == {}
    assert _mod._all_row_ids(text) == [(5, "D-1")]


def test_a_header_and_delimiter_of_different_widths_are_no_table():
    """Review pass 1, A-haiku-2: GFM renders no table when the counts differ (markdown-it renders
    none for 6/7, 6/3 and 3/6), so the rows under such a pair are no ledger table's."""
    for head in (
        "| a | b | c | d | e | f |\n|---|---|---|\n",
        "| a | b | c |\n|---|---|---|---|\n",
    ):
        text = head + _row("D-1") + "\n" + _row("D-2")
        assert _mod._parse(text).header is None, head
        assert find_rows_outside_the_table(text) == []
    assert _mod._parse(_SHAPE_HEAD + _row("D-1")).header is not None


def test_a_triple_is_not_called_two_rows(tmp_path, monkeypatch, capsys):
    """Review pass 1, A-haiku-7: the summary said "two rows each" beside "appears 3x"."""
    ledger = tmp_path / "docs" / "DECISIONS.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(_SHAPE_HEAD + _row("D-1") + _row("D-1") + _row("D-1"))
    monkeypatch.setattr(_mod, "LEDGER", ledger)
    assert _mod.main() == 1
    out = capsys.readouterr().out
    assert "appears 3x" in out and "two rows" not in out


def test_an_id_of_any_length_is_keyed_without_int():
    """Review pass 1, A-sonnet-2: `int()` refuses over 4,300 digits, so one such cell crashed the run
    before any line printed. Pass 1's first fix capped ids at 9 digits, which made a 10-digit id
    invisible (C-haiku-1: the old checker caught its duplicate) — the key needs no `int()` at all.
    A non-ASCII digit is no id digit."""
    huge = "D-" + "9" * 5000
    assert find_duplicates(_SHAPE_HEAD + _row(huge) + _row(huge)) == {huge: 2}
    ten = "D-1234567890"
    assert find_duplicates(_SHAPE_HEAD + _row(ten) + _row(ten)) == {ten: 2}
    assert find_duplicates(_SHAPE_HEAD + _row("D-0") + _row("D-000")) == {"D-0": 2}
    assert find_duplicates(_SHAPE_HEAD + "| D-١ | a |\n| D-١ | b |\n") == {}
