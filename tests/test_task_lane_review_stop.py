"""The in-lane review stops hunting at the first own-fix-only round (plan T04; spec § The delta D8,
§ Validation V8).

Two readers learn the nested case and nothing else moves:

- ``task_lane.scope_growth_rounds(stack)`` — ``(1, 1)`` when the record's IMMEDIATE parent (the
  last entry of the record stack, ``command_run.py``'s ``stack.append(parent)``) is a
  ``fabrik-task`` run, else today's ``(SCOPE_GROWTH_ROUNDS, SCOPE_GROWTH_QUALIFY)``.
- ``check_review_coverage.py`` — a receipt carrying the exact header line ``**Lane:** fabrik-task``
  (written by ``review_receipt.py --lane``, T03b) needs ONE trailing confirming round for the
  declared scope-growth stop instead of ``_OWN_FIX_ROUNDS_FOR_STOP`` (2).

Every receipt here is written by the real ``review_receipt.py --init [--lane]`` and graded by the
real ``check_file`` on disk.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_review_receipt import _complete

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCRIPT = ROOT / "scripts" / "review_receipt.py"
LANE_LINE = "**Lane:** fabrik-task"
QUIET_ERR = "the exit round must be quiet"
STOP_STATUS = "**Status:** CONVERGED on the D-252 scope-growth stop"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _tl():
    return _load("task_lane", ROOT / "scripts" / "task_lane.py")


def _crc():
    return _load("crc_t04", ROOT / "scripts" / "enforcement" / "check_review_coverage.py")


def _module_int(src: str, name: str) -> int:
    """A module-level integer literal, parsed (never `startswith` — a prefix sibling fooled that)."""
    rx = re.compile(rf"^{name}\s*(?::\s*[^=]+)?=\s*(\d+)\s*(?:#.*)?$")
    for line in src.splitlines():
        m = rx.match(line)
        if m:
            return int(m.group(1))
    raise AssertionError(f"{name} is no longer a plain integer literal")


# ── scope_growth_rounds ─────────────────────────────────────────────────────────────────────


def test_a_stack_whose_last_entry_is_fabrik_task_gets_the_one_round_stop():
    assert _tl().scope_growth_rounds([{"command": "fabrik-task"}]) == (1, 1)
    # deeper entries do not matter: only the IMMEDIATE parent decides
    stack = [{"command": "fabrik-execute-plan"}, {"command": "fabrik-task", "phase": 4}]
    assert _tl().scope_growth_rounds(stack) == (1, 1)


def test_an_empty_stack_keeps_todays_rule():
    assert _tl().scope_growth_rounds([]) == (3, 2)


def test_fabrik_task_deeper_than_the_last_entry_keeps_todays_rule():
    stack = [{"command": "fabrik-task"}, {"command": "fabrik-execute-plan"}]
    assert _tl().scope_growth_rounds(stack) == (3, 2)


@pytest.mark.parametrize(
    "last",
    [
        {"command": "fabrik-task-x"},
        {"command": "/fabrik-task"},  # the record stores the name stripped; a slash is not it
        {"command": "Fabrik-Task"},
        {"command": "fabrik-review"},
        {"command": None},
        {},
        "fabrik-task",  # not a record dict
    ],
)
def test_only_the_exact_fabrik_task_parent_selects_the_lane_stop(last):
    assert _tl().scope_growth_rounds([last]) == (3, 2)


def test_the_default_pair_is_command_runs_window_and_qualify():
    """Two hand-kept numbers drift; ``task_lane`` is pure (never imports ``command_run.py``), so
    the default is pinned to the twin by parsing the source."""
    src = (ROOT / "scripts" / "command_run.py").read_text(encoding="utf-8")
    assert _tl().scope_growth_rounds([]) == (
        _module_int(src, "SCOPE_GROWTH_ROUNDS"),
        _module_int(src, "SCOPE_GROWTH_QUALIFY"),
    )


# ── the lockstep ────────────────────────────────────────────────────────────────────────────


def test_the_lane_constant_is_in_lockstep_with_scope_growth_rounds():
    crc = _crc()
    assert (
        _tl().scope_growth_rounds([{"command": "fabrik-task"}])[1]
        == crc._LANE_OWN_FIX_ROUNDS_FOR_STOP
    )
    src = (ROOT / "scripts" / "command_run.py").read_text(encoding="utf-8")
    assert crc._OWN_FIX_ROUNDS_FOR_STOP == _module_int(src, "SCOPE_GROWTH_QUALIFY") == 2


# ── check_review_coverage: the **Lane:** marker ─────────────────────────────────────────────


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    return r


def _receipt(repo: Path, name: str, *, lane: bool) -> str:
    """A completed receipt written by the real ``review_receipt.py --init [--lane]``."""
    out = repo / "docs" / "development" / "reviews" / f"{name}-review.md"
    cmd = [sys.executable, str(RECEIPT_SCRIPT), "--init", "--project-root", str(repo)]
    cmd += ["--out", str(out), "--changed", "app.py"] + (["--lane"] if lane else [])
    made = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    text = _complete(out.read_text(encoding="utf-8"))
    out.unlink()
    assert (LANE_LINE + "\n" in text) is lane, "the writer's marker moved"
    return text


# The stop shape the lane window decides on: round 1 (the full pass) CONFIRMED nothing — D-278's
# natural "window round that does not qualify" — and round 2 confirmed only own-fix defects.
# Today's two-round rule refuses the declared stop (round 1 is in its qualifying tail); the
# lane's one-round rule counts round 2 alone. (An `unexecuted:` on round 1 is NOT this shape:
# the lane narrows only the qualifying count, never the unexecuted check — review ruling T04-O2.)
_STOP_ROWS = (
    "| Pass 1 | native opus×1 + sonnet×2 | found: 6, new: 6, confirmed: 0, fixed: 0, "
    "unexecuted: 0 | citation |\n"
    "| Pass 2 | native opus×1 + sonnet×2 | found: 2, new: 2, confirmed: 2, fixed: 2, "
    "unexecuted: 0 | method: re-derivation |\n"
)
_QUIET_ROW = (
    "| Pass 3 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, "
    "unexecuted: 0 | method: re-derivation |\n"
)


def _with_ledger(text: str, rows: str, status: str = STOP_STATUS) -> str:
    head = "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n"
    start = text.index(head) + len(head)
    end = text.index("\n\n", start) + 1
    out = text[:start] + rows + text[end:]
    out = out.replace("**Status:** CONVERGED", status, 1)
    # + the header row and the template's two fenced example rows
    assert out.count("| Pass ") == rows.count("| Pass ") + 3
    return out


def _grade(repo: Path, text: str, name: str = "graded") -> list[str]:
    p = repo / "docs" / "development" / "reviews" / f"{name}-review.md"
    p.write_text(text, encoding="utf-8")
    return _crc().check_file(p)


def test_a_lane_receipt_with_a_stop_at_round_two_then_a_quiet_close_passes(repo):
    """V8 as the ticket words it: round 2 confirms only own-fix defects, then a quiet closing
    row (D-355 still closes on a confirmed-zero pass)."""
    text = _with_ledger(
        _receipt(repo, "r", lane=True), _STOP_ROWS + _QUIET_ROW, "**Status:** CONVERGED"
    )
    assert _grade(repo, text) == []
    # The quiet closing row passes under EITHER rule, so this alone cannot tell them apart
    # (review T04-O1). What distinguishes them is the round the stop FIRED at: the same receipt's
    # ledger up to round 2, declaring the stop, is accepted with the marker and refused without.
    crc = _crc()
    at_stop = _with_ledger(_receipt(repo, "r", lane=True), _STOP_ROWS)
    rows = crc._ledger_shapes(at_stop)[2]
    assert crc._scope_growth_exit(at_stop, rows)
    plain = at_stop.replace(LANE_LINE + "\n", "", 1)
    assert not crc._scope_growth_exit(plain, crc._ledger_shapes(plain)[2])
    # D-355 (kaizen 01M4CPWDK0): the stop routes own-fix work; neither receipt may CLOSE at it
    assert any(QUIET_ERR in e for e in _grade(repo, at_stop))
    assert any(QUIET_ERR in e for e in _grade(repo, plain))


def test_a_lane_receipt_declaring_the_stop_at_round_two_does_not_close(repo):
    """The marker still makes the predicate fire at round 2 (D8), but since D-355 a receipt
    closes only on a confirmed-zero row — the stop is where hunting ends, not the close."""
    text = _with_ledger(_receipt(repo, "r", lane=True), _STOP_ROWS)
    crc = _crc()
    assert crc._scope_growth_exit(text, crc._ledger_shapes(text)[2])
    assert any(QUIET_ERR in e for e in _grade(repo, text))


def test_the_same_receipt_without_the_lane_line_keeps_the_two_round_rule(repo):
    text = _with_ledger(_receipt(repo, "r", lane=False), _STOP_ROWS)
    errs = _grade(repo, text)
    assert any(QUIET_ERR in e for e in errs), errs
    # ...and the ONLY difference between the two is the marker line
    lane = _with_ledger(_receipt(repo, "r", lane=True), _STOP_ROWS)
    assert lane.replace(LANE_LINE + "\n", "", 1) == text


@pytest.mark.parametrize(
    "variant",
    [
        "**Lane:** fabrik-task-x",  # a suffix
        "**Lane:** fabrik-task/v2",  # a slash after the keyword
        "**Lane:** **fabrik-task**",  # bold value
        "**Lane**: fabrik-task",  # colon outside the bold
        "**lane:** Fabrik-Task",  # case
        "Lane: fabrik-task",  # unbolded
        "> **Lane:** fabrik-task",  # blockquoted
        "**Lane:** fabrik-task (not really)",  # trailing prose
    ],
)
def test_only_the_exact_marker_line_selects_the_lane_window(repo, variant):
    """The marker exempts a gate, so it is read FAIL-CLOSED: the one spelling the writer emits
    (``review_receipt.LANE_LINE``) and nothing else. Every other spelling keeps the two-round
    rule."""
    lane = _with_ledger(_receipt(repo, "r", lane=True), _STOP_ROWS)
    text = lane.replace(LANE_LINE + "\n", variant + "\n", 1)
    assert text != lane
    errs = _grade(repo, text)
    assert any(QUIET_ERR in e for e in errs), (variant, errs)


def test_the_marker_is_header_zoned(repo):
    """A body-deep copy (an appendix QUOTING the marker) is not the marker — the same zone the
    Status declaration is read in (the first 10 lines)."""
    plain = _with_ledger(_receipt(repo, "r", lane=False), _STOP_ROWS)
    text = plain + "\n## Appendix\n\n" + LANE_LINE + "\n"
    errs = _grade(repo, text)
    assert any(QUIET_ERR in e for e in errs), errs


def test_a_fenced_marker_in_the_header_zone_is_not_the_marker(repo):
    plain = _with_ledger(_receipt(repo, "r", lane=False), _STOP_ROWS)
    lines = plain.split("\n")
    lines[2:2] = ["```text", LANE_LINE, "```"]
    text = "\n".join(lines)
    assert text.index(LANE_LINE) < sum(len(x) + 1 for x in lines[:10])
    errs = _grade(repo, text)
    assert any(QUIET_ERR in e for e in errs), errs


def test_the_lane_window_still_refuses_a_single_row_ledger():
    """Round 1 is the full pass; it holds no fixes of the review's own, so it can never be the
    own-fix round. The lane stop still needs at least one delta round."""
    crc = _crc()
    text = f"# R\n\n{STOP_STATUS}\n{LANE_LINE}\n"
    assert not crc._scope_growth_exit(text, [(6, 6, None, None)])
    assert crc._scope_growth_exit(text, [(6, 6, None, None), (2, 2, None, None)])


_UNEXECUTED_R1_ROWS = (
    "| Pass 1 | native opus×1 + sonnet×2 | found: 6, new: 6, confirmed: 6, fixed: 6, "
    "unexecuted: 5 | citation |\n"
    "| Pass 2 | native opus×1 + sonnet×2 | found: 2, new: 2, confirmed: 2, fixed: 2 "
    "| method: re-derivation |\n"
)


@pytest.mark.parametrize("lane", [True, False])
def test_an_unexecuted_round_one_refuses_the_stop_with_or_without_the_marker(repo, lane):
    """Review ruling T04-O2: the lane narrows ONLY how many own-fix rounds the stop needs. The
    `unexecuted:` check reads the same rows as without the marker (`_OWN_FIX_ROUNDS_FOR_STOP`),
    so a round-1 `unexecuted: 5` refuses the stop in both receipts."""
    crc = _crc()
    text = _with_ledger(_receipt(repo, "r", lane=lane), _UNEXECUTED_R1_ROWS)
    rows = crc._ledger_shapes(text)[2]
    assert [r[3] for r in rows] == [5, None], rows  # the fixture says what the ruling says
    assert not crc._scope_growth_exit(text, rows)
    assert any(QUIET_ERR in e for e in _grade(repo, text))
    # the tuple form the ruling names, through the predicate directly
    status = f"# R\n\n{STOP_STATUS}\n" + (f"{LANE_LINE}\n" if lane else "")
    assert not crc._scope_growth_exit(status, [(6, 6, None, 5), (2, 2, None, None)])


def test_the_lane_window_still_refuses_an_unexecuted_or_quiet_exit_row():
    crc = _crc()
    text = f"# R\n\n{STOP_STATUS}\n{LANE_LINE}\n"
    assert not crc._scope_growth_exit(text, [(6, 6, None, None), (2, 2, None, 1)])
    assert not crc._scope_growth_exit(text, [(6, 6, None, None), (0, 0, None, None)])
    assert not crc._scope_growth_exit(text, [(6, 6, None, None), (2, None, None, None)])


def test_the_lane_marker_alone_does_not_exempt_an_undeclared_stop():
    """The marker shortens the WINDOW; it is not a declaration. The Status line must still say
    the loop closed on the scope-growth stop."""
    crc = _crc()
    text = f"# R\n\n**Status:** CONVERGED\n{LANE_LINE}\n"
    assert not crc._scope_growth_exit(text, [(6, 6, None, None), (2, 2, None, None)])
