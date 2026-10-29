"""W-f1191ec5 (mail 01M5MVZ2NF, infra-2): a seat runs a test only on a tree § Seat isolation stages.

In infra-2's /fabrik-review of W-25f6b2a3, 3 of 4 finder seats skipped the `PIN_IMPORT`/`PYTEST_PINS` recipe and ran
pytest on a pins-only copy with `--noconftest`. A pins-only copy holds no conftest, so the hub's `tests/conftest.py`
(which loads `tests/memguard.py` by path) cannot collect there, and `--noconftest` drops every conftest's isolation
(the root `conftest.py` mutes live alerting and imports this tree's `src`). The probe catalogue now says so in its own
bullet, and has a pytest-running brief's pin take `--base`, whose read-only base copy replaces both recipes' archive
steps. The bullet's clauses are ledger entries (`commands/_rules/_shared/review-probe-catalogue.yaml`), ordered; this file keeps its place among its neighbours. The pin command and
the workflow arg it names are asserted by key, never by their prose, so this grader does not pin intel's wording.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"
LEDGER = ROOT / "scripts" / "review_loop_ledger.py"
LOOP = ROOT / ".claude" / "workflows" / "fabrik-review-loop.js"

HEAD = "- A pins-only copy is not a test tree:"


def test_the_bullet_sits_after_the_first_bullet_and_before_the_delta_brief() -> None:
    """The first § Seat isolation bullet is pinned whole by test_review_scoped_queue_pass.py; the new rule is its own
    bullet right after it, so neither span absorbs the other."""
    raw = CAT.read_text(encoding="utf-8").split("\n")
    first = next(
        k
        for k, line in enumerate(raw)
        if line.startswith("- The brief names the fix as `git show <sha>`")
    )
    mine = next(k for k, line in enumerate(raw) if line.startswith(HEAD))
    delta = next(k for k, line in enumerate(raw) if line.startswith("- A delta brief also names"))
    between = [line for line in raw[first + 1 : mine] if line.startswith("- ")]
    assert first < mine < delta and between == []


def test_named_base_copy_mechanism_exists() -> None:
    """Behaviour 3: the bullet points at `pin --base`, `<pins_dir>.base` and `${args.base_pin_dir}`; each exists,
    asserted by its key — the argparse flag, the fragment key the pin prints, the workflow arg — never by help or
    recipe prose, so a reworded help string or recipe sentence does not red it."""
    ledger = LEDGER.read_text(encoding="utf-8")
    assert '"--base", help=' in ledger
    assert 'frag["base_pin_dir"]' in ledger
    assert 'Path(f"{pins_dir}.base")' in ledger
    assert "for (const key of ['pins_dir', 'scratch_dir', 'base_pin_dir'])" in LOOP.read_text(
        encoding="utf-8"
    )


NODE_HARNESS = (
    "A test that needs a gitignored dependency tree (`node_modules/`) runs on no seat tree: an archive or a clone"
    " holds none, and a copy of the live one, a link to it or a variable pointing at it lets the run write inside it;"
    " so a seat reports that test unverifiable and never runs it, and the lead runs it in CLAUDE.md's throwaway"
    " worktree, after an install from that tree's own lockfile, when the change touches it or the code it tests."
)


def test_a_node_harness_test_is_the_leads_to_run() -> None:
    """Mail 01M640TVJY (intel, W-9ad5860f): a seat reports a `node_modules/` test unverifiable, so the lead's duty to
    run it is stated whole in § Seat isolation, right after the sentence that names the tests a seat runs."""
    text = re.sub(r"\s+", " ", CAT.read_text(encoding="utf-8"))
    seat = text[text.index("## Seat isolation") : text.index("## Loop bookkeeping")]
    before = "so a new import that breaks a stubbed loader reds in the pass. "
    assert before + NODE_HARNESS + " A script seat runs is run from its archive copy" in seat
