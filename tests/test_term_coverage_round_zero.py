"""W-7c290366: round zero's input-space duty leads its list, bold.

Five /fabrik-review closes lost rounds because the author never enumerated the fix's input shapes before the pin,
and each reject cited term-coverage.md round zero, where that duty sat fourth of about ten duties in one paragraph.
The move puts it first and bold. Cheapest bypass: a reader who still skips it — W-1dc074b6 measures that.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "term-coverage.md"

HEADER_END = "not only before round one — D-335):** "
DUTY = (
    "**the fix's own INPUT space is enumerated and executed before the pin, so no seat is the first to meet it**"
    " — for example a matcher or replacer"
)
# the duty that led round zero before the move
BASE_FIRST_DUTY = "the fix's mutation battery (rule 4) runs only on a copy"


def _round_zero() -> str:
    lines = FRAG.read_text(encoding="utf-8").split("\n")
    hits = [
        line
        for line in lines
        if line.startswith("**Round zero — the orchestrator's OWN pre-pin probe")
    ]
    assert len(hits) == 1, len(hits)
    return hits[0]


def test_the_input_space_duty_leads_round_zero() -> None:
    zero = _round_zero()
    assert zero.count(HEADER_END) == 1
    after = zero[zero.index(HEADER_END) + len(HEADER_END) :]
    assert after.startswith(DUTY), after[:160]
    # the duty that led before the move now follows the input-space duty's last clause
    assert "listed before the probe runs; " + BASE_FIRST_DUTY in zero
