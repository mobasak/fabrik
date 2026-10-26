"""W-f1191ec5 (mail 01M5MVZ2NF, infra-2): a seat runs a test only on a tree § Seat isolation stages.

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
    "conftest, none of the files a conftest loads by path (the hub's `tests/conftest.py` loads `tests/memguard.py`;"
    " its root `conftest.py` mutes live alerting and imports this tree's `src`). A seat runs a Python test only "
    "through pytest, and only on a tree this section stages, with the pins laid over it — the archive the recipe "
    "builds (the whole test tree, the root conftest, the pytest config and every root the tests import, read or "
    "run, never a subset that leaves one out), the lead's base copy, or, for a test that reads git history or the "
    "tracked set, the clone above — never on the pins dir, a copy of it or any hand-assembled tree, and never with "
    "a conftest or the pytest config dropped, skipped or pointed elsewhere by any flag, option or environment "
    "variable (`--noconftest`, `--confcutdir`, `--ignore` of a conftest, `-p no:` on a conftest's plugin, "
    "`PYTEST_ADDOPTS`, `-c` or `--rootdir` naming any file or tree other than the staged tree's own, or `-o` on "
    "`addopts`, `testpaths`, `python_files`, `pythonpath` or another key that changes what is collected or "
    "imported; an `-o` on a key that changes neither, such as `timeout`, stays legal); a test it cannot run that "
    "way is unverified, never run another way. A seat that runs pytest or imports pinned code "
    "needs the unmodified tree, so its brief's pin takes `--base` (the pin command of "
    "`/opt/fabrik/commands/_fragments/subagents-core.md`'s PIN paragraph), on each pass by the shape that pass's "
    "surface has then (a surface committed since the previous pass is pinned `--from`, as the bullet above says): "
    "`HEAD` for a working-tree pin (its basis is `HEAD` and its `base_sha` HEAD's commit either way; a repo with no"
    " commit has no base copy, and `--base` is refused there), `<c>^` for a fix pinned `--from <c>` (never `<c>`, "
    "which calls every file `UNCHANGED`), and the commit before the fix when it spans several. The brief's "
    "`base_sha` is then the one the pin records, and it gives `<pins_dir>.base` as the recipe's "
    "`${args.base_pin_dir}`, so each seat copies that tree in place of the archive steps of both `PIN_IMPORT` and "
    "`PYTEST_PINS`. A base copy is a whole commit (some 120 MB in the hub) beside the pins dir, so it sits in the "
    "durable `SCRATCH:` folder, which `start` keeps 14 days, whenever the including command pins there: once the "
    "pass is "
    "adjudicated, the lead removes it (`chmod -R u+w <pins_dir>.base`, then `rm -rf <pins_dir>.base`, each its own "
    "command), since every pass pins afresh and a delta brief reads the previous `pins_dir`, never its base copy."
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
    the unverified clause, `<c>^`, `never `<c>``, the clone, `PYTEST_ADDOPTS` or the base-copy removal each red it."""
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
