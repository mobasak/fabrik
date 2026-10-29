"""W-f1191ec5 (mail 01M5MVZ2NF, infra-2): a seat runs a test only on a tree § Seat isolation stages.

In infra-2's /fabrik-review of W-25f6b2a3, 3 of 4 finder seats skipped the `PIN_IMPORT`/`PYTEST_PINS` recipe and ran
pytest on a pins-only copy with `--noconftest`. A pins-only copy holds no conftest, so the hub's `tests/conftest.py`
(which loads `tests/memguard.py` by path) cannot collect there, and `--noconftest` drops every conftest's isolation
(the root `conftest.py` mutes live alerting and imports this tree's `src`). The probe catalogue now says so in its own
bullet, and has a pytest-running brief's pin take `--base`, whose read-only base copy replaces both recipes' archive
steps. The bullet's clauses are ledger entries (`commands/_rules/_shared/review-probe-catalogue.yaml`), ordered; this file keeps its place among its neighbours. The pin command and
the workflow arg it names are asserted by key, never by their prose, so this grader does not pin intel's wording.
"""

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
