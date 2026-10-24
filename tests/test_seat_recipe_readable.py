"""W-f1191ec5 (mail 01M5MVZ2NF, infra-2): a seat runs pytest only on the tree § Seat isolation stages.

In infra-2's /fabrik-review of W-25f6b2a3, 3 of 4 finder seats skipped the `PIN_IMPORT`/`PYTEST_PINS` recipe and ran
pytest on a pins-only copy with `--noconftest`. A pins-only copy holds no conftest, so the hub's `tests/conftest.py`
(which loads `tests/memguard.py` by path) cannot collect there, and `--noconftest` drops every conftest's isolation
(the root `conftest.py` mutes live alerting and imports this tree's `src`). The probe catalogue now says so in its own
bullet, and has a pytest-running brief's pin take `--base`, whose read-only base copy replaces both recipes' archive
steps. The bullet is pinned whole, cut on raw lines, so a dropped or contradicting clause reds it. The pin command and
the workflow arg it names are asserted by key, never by their prose, so this grader does not pin intel's wording.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"
LEDGER = ROOT / "scripts" / "review_loop_ledger.py"
LOOP = ROOT / ".claude" / "workflows" / "fabrik-review-loop.js"

HEAD = "- A pins-only copy is not a test tree:"

BULLET = (
    "- A pins-only copy is not a test tree: it holds the pins and nothing else — no package, no pytest config, no "
    "conftest, none of the files a conftest loads by path (the hub's `tests/conftest.py` loads `tests/memguard.py`; "
    "its root `conftest.py` mutes live alerting and imports this tree's `src`). A seat runs pytest only on the tree "
    "this section stages — the archive, or the lead's base copy, with the pins laid over it — never on the pins dir, "
    "a copy of it or any hand-assembled subset, and never with a conftest or the pytest config dropped or moved "
    "(`--noconftest`, `--confcutdir`, `-c`, `-o`, `--rootdir`, a test file run outside its tree); a test it cannot "
    "run that way is unverified, never run another way. A seat that runs pytest needs the unmodified tree, so its "
    "brief's pin takes `--base` (the pin command of `/opt/fabrik/commands/_fragments/subagents-core.md`'s PIN "
    "paragraph), the same way on every pass of the review: `HEAD` for a working-tree pin (its basis and `base_sha` "
    "are `HEAD` either way; a repo with no commit has no base copy, and `--base` is refused there), `<c>^` for a fix "
    "pinned `--from <c>` (never `<c>`, which calls every file `UNCHANGED`), and the commit before the fix when it "
    "spans several. The brief's `base_sha` is then the one the pin records, and it gives `<pins_dir>.base` as the "
    "recipe's `${args.base_pin_dir}`, so each seat copies that tree in place of the archive steps of both "
    "`PIN_IMPORT` and `PYTEST_PINS`."
)


def _seat_isolation_bullet(head: str) -> str:
    raw = CAT.read_text(encoding="utf-8").split("\n")
    top = raw.index("## Seat isolation")
    stop = next(k for k in range(top + 1, len(raw)) if raw[k].startswith("#"))
    starts = [k for k in range(top + 1, stop) if raw[k].startswith(head)]
    assert len(starts) == 1, (
        f"expected one bullet starting {head!r} in § Seat isolation, found {len(starts)}"
    )
    start = starts[0]
    end = next(k for k in range(start + 1, stop + 1) if raw[k].startswith(("- ", "#")))
    return " ".join(" ".join(raw[start:end]).split())


def test_pins_only_copy_is_not_a_test_tree() -> None:
    """Behaviour 1+2: the bullet bars pytest on any tree but the staged one and every conftest-dropping flag, and has
    a pytest brief take `--base` with the right commit per pin shape. Pinned whole: mutants dropping `--confcutdir`,
    the unverified clause, `<c>^`, or `never `<c>`` each red it."""
    assert _seat_isolation_bullet(HEAD) == BULLET


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
    """Behaviour 3: the bullet points at `pin --base` and `${args.base_pin_dir}`; both exist, asserted by key."""
    assert (
        '"--base", help="also extract this commit, whole and read-only, into <pins-dir>.base"'
        in (LEDGER.read_text(encoding="utf-8"))
    )
    assert "for (const key of ['pins_dir', 'scratch_dir', 'base_pin_dir'])" in LOOP.read_text(
        encoding="utf-8"
    )
