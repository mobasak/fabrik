"""Mail 01M65ZP80Q (wef2): a review seat's tests run under capped_run.sh, never under the Bash tool's timeout alone.

On 2026-10-26 a seat ran a mutant under plain pytest; the mutant blocked on a FIFO and the Bash tool's `timeout` only
moved it to the background, where it ran 2 days 13 hours. D-935 puts every test run under capped_run.sh, but a seat
reads its brief, not CLAUDE.md, and no seat-facing text said so. The rule now sits in the two places seats read: the
probe catalogue's § Seat isolation (pasted whole by /fabrik-review and /fabrik-review-scoped) and the fabrik-reviewer
House rules (every such seat, every command). The new sentences are pinned whole, compared with whitespace collapsed
because the catalogue and fabrik-review.md wrap their lines.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"
AGENT = ROOT / "commands" / "_agents" / "fabrik-reviewer.md"
SCOPED = ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
REVIEW = ROOT / "commands" / "_sources" / "fabrik-review.md"

BULLET = (
    "- A test run, and a probe that executes pinned code, follows the fabrik-reviewer House rules' `capped_run.sh` "
    "clause (D-935; the recipe's pytest launch is its `<command>`), since the Bash tool's `timeout` only backgrounds a "
    "command (a seat's FIFO-blocked mutant ran 2 days 13 hours, mail 01M65ZP80Q); a brief to a seat of another type "
    "quotes it whole."
)

CLAUSE = (
    "a background probe lives inside a python program, stopped by its handle; run every test, and every probe that "
    "executes the pinned code, as one plain `/opt/fabrik/scripts/capped_run.sh --timeout <s> -- <command>` (D-935; "
    "`<s>` your brief's number, else 120, at most 540; its `systemctl --user` call is that cap, not a barred write), "
    "the Bash `timeout` set to (`<s>` + 60) × 1000 ms and no outer `timeout 120`: the Bash timeout only backgrounds a "
    "command, which runs on unseen; exit 124 or 137, or 2 with a `capped_run:` line, is no result (the test "
    "`unverified`, its mutant not caught), that line going in MACHINERY;"
)

SUMMARY_CAP = (
    "never a hand-listed path set — each test run goes under `capped_run.sh --timeout <s>`, the brief naming `<s>` "
    "(3× the lead's own run, at most 540) when that run took over 40 s — the recipe is the seat prompt's"
)


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _seat_isolation(text: str) -> str:
    start = text.index("\n## Seat isolation\n")
    return text[start : text.index("\n## ", start + 1)]


def _summary_unit(path: Path) -> str:
    flat = _flat(path)
    start = flat.index("Its § Seat isolation applies whole, whatever the shape")
    tail = "the pytest config with the roots)."
    end = flat.find(tail, start)
    assert end != -1, f"{path.name}: the § Seat isolation summary has lost its end"
    return flat[start : end + len(tail)]


def test_the_catalogue_seat_isolation_section_ends_with_the_capped_run_bullet() -> None:
    section = _seat_isolation(CAT.read_text(encoding="utf-8"))
    bullets = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n(?=- )", section)]
    assert bullets[-1] == BULLET


def test_the_mutation_bullet_names_the_capped_run_timeout_not_a_bare_timeout() -> None:
    assert (
        "under the explicit `timeout` its brief names (`/fabrik-review`'s D8 mutation-seat lesson), that `timeout` "
        "being § Seat isolation's `capped_run.sh --timeout`;"
    ) in _flat(CAT)


def test_the_reviewer_house_rules_carry_the_capped_run_clause_whole() -> None:
    house = next(
        line
        for line in AGENT.read_text(encoding="utf-8").splitlines()
        if line.startswith("**House rules")
    )
    assert CLAUSE in house


def test_both_review_commands_summarise_the_cap_in_one_identical_unit() -> None:
    scoped, review = _summary_unit(SCOPED), _summary_unit(REVIEW)
    assert SUMMARY_CAP in scoped
    assert scoped == review
