"""/fabrik-command-improve feedback queue answered in one pass (D-735): execute what a new sentence says a script does.

The text pins live in the rule ledger `commands/_rules/fabrik-command-improve.yaml`; what stays here runs the recipes, scripts and files the source names.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-command-improve.md"


def _phase(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_five_runs_every_test_that_names_the_edited_source() -> None:
    """Row 1791830357 (D-790): fabrik-task.md's size cap and verbatim pins sit in a test the queue-pass test is not."""
    import subprocess

    found = subprocess.run(
        ["grep", "-rl", "--include=*.py", "fabrik-task.md", "tests/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "tests/test_fabrik_task_source.py" in found
    assert not [p for p in found if not p.endswith(".py")]


def test_a_fragment_edit_names_its_by_path_consumers_too() -> None:
    """Row 1791892288: the probe catalogue is never included, only named, so an include-only consumer list found none
    and missed the review commands that point at it. The rule lives in PHASE 3, and its recipe runs here: by-path
    pointers, a fragment that names another, and the includers too."""
    import subprocess

    def recipe(stem: str) -> set[str]:
        return set(
            subprocess.run(
                ["grep", "-rlw", stem, "commands/_sources", "commands/_fragments"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            ).stdout.split()
        )

    assert {
        "commands/_sources/fabrik-review.md",
        "commands/_sources/fabrik-review-scoped.md",
    } <= recipe("review-probe-catalogue")
    coverage = recipe("term-coverage")
    assert "commands/_fragments/subagents-core.md" in coverage  # a fragment that names it
    assert (
        "commands/_sources/fabrik-user-test.md" in coverage
    )  # an includer: {{include:term-coverage}}


def test_a_count_lives_at_its_list() -> None:
    """W-66f398a3: a paragraph that says how MANY ("wrong in FIVE ways") away from its list goes stale when the next
    edit adds an item, and Phase D's scoped review-fix rounds kept confirming that residue. The rule lives once, in
    the hub CLAUDE.md's § Behavior, beside READ BEFORE YOU EDIT, which every hub session loads, including the review-fix loops
    that never render /fabrik-command-improve's PHASE 3."""
    text = re.sub(r"\s+", " ", (ROOT / "CLAUDE.md").read_text())
    behavior = text[text.index("## Behavior") : text.index("## ⚠️ THE FIX DIRECTIVE")]
    assert (
        "- **A count lives at its list.** An enumeration states how many in the clause that opens the list, or not at"
        " all (`the ways below`, never `five ways` a sentence away), and an edit that adds an item to a list, or"
        " removes one, re-counts every place that list's count is stated. **A worked example is re-read** against"
        " every caveat in its own paragraph before it is pinned or committed." in behavior
    )


def test_a_reject_search_reads_the_render_and_a_seat_rule_lands_in_every_home() -> None:
    """Rows 1791941814 and 1791944106 (kaizen's own closes, 2026-10-14): a planned HELD reject said /fabrik-spec Phase 0
    dispatches no capped seat brief, but delegated-reads.md, which it includes, does; and a never-execute seat rule was
    first written into subagents-core alone. The reject search reads the rendered command; a seat rule goes to every
    home a grep names, and PHASE 2 admits the agent files those homes include."""
    for home in (
        "commands/_fragments/subagents-core.md",
        "commands/_sources/fabrik-review.md",
        "commands/_fragments/design-critique.md",
        "docs/reference/convergence-prompts.md",
        ".claude/workflows/fabrik-review-loop.js",
        ".claude/hooks/seat_guard.py",
        "commands/_agents/fabrik-reviewer.md",
    ):
        assert (ROOT / home).exists(), home
    assert "const SEAT_ISOLATION" in (ROOT / ".claude/workflows/fabrik-review-loop.js").read_text()


def test_the_mark_step_says_a_handle_is_the_whole_ts_with_its_fraction() -> None:
    """Row 1792084693, a second verdict on the mark-handle subject (held as mark-handles-from-take-output): a
    handle typed without its fractional part was refused as matching no row. The tool compares handles as exact
    strings, so the sentence names the whole `ts`. Mutants: drop the clause, or let the tool match by prefix."""
    # the sentence's example, executed: the row's key is its full ts, and mark_answered matches keys exactly —
    # read inside mark_answered, since --reject carries the same matching line (round-1 finding)
    import inspect
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_feedback_report as cfr

    assert cfr._ts_key(1792030670.5328414) == "1792030670.5328414"
    assert cfr._ts_key(1792030670.5328414) != "1792030670"
    assert "unknown = [t for t in wanted if t not in known]" in inspect.getsource(
        cfr.mark_answered
    ), "--mark-answered no longer matches handles exactly: the sentence's example is no longer true"


def test_a_fragment_pointed_at_by_path_is_a_write_and_lock_target() -> None:
    """W-5048181b: PHASE 2's write-target list and its lock check named the fragments a command renders but not one it
    points at by path (the probe catalogue, read live and never rendered), so a row whose fix belongs there had no
    listed target and no lock check. Both lists now name it; the lock check's printed grep is RUN here on a real command
    source and must print the catalogue repo-relative, the form `owned_paths` uses, since an absolute path matches no
    lock and fails open. The weight sentence and PHASE 5's test pick count a by-path reader too."""
    p2 = _phase("## PHASE 2", "## PHASE 3")
    lock = p2[p2.index("the file you would WRITE is lock-owned") : p2.index("STOP and mail")]
    assert lock.index("points at by path") < lock.index(".fabrik/plan-locks/")
    pattern = re.search(r"grep -no '([^']+)'", lock).group(1)
    scoped = ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
    out = subprocess.run(
        ["grep", "-no", pattern, str(scoped)], capture_output=True, text=True, check=True
    ).stdout.split()
    paths = {line.split(":", 1)[1] for line in out}
    assert "commands/_fragments/review-probe-catalogue.md" in paths, paths
    assert not any(p.startswith("/") for p in paths), paths
    included = set(re.findall(r"\{\{include:([a-z0-9-]+)\}\}", scoped.read_text()))
    assert "review-probe-catalogue" not in included, included


def test_the_lock_check_names_the_appended_fragment_and_how_an_entry_owns_a_path() -> None:
    """W-ddf1839c: the lock check's `include:` grep cannot see the two fragments the assembler appends with no include
    (close-feedback to every command, agent-feedback to every agent), and the bullet never said how an `owned_paths`
    entry matches a target while locks hold paths, directories and globs. Both sentences are pinned whole. Their facts
    are checked against the code: each append STATEMENT (deleting one fails here, the constant alone would not) and no
    source naming either fragment in an `include:`; and the three-shape ownership rule run through `_glob_matches` in
    scripts/epic_order.py, an epic `owned_paths` matcher, which implements all three; and the claim that no script
    testing a path against a lock's `owned_paths` is that rule — `_owned` matches globs since W-9fcb6ce4 but folds
    case, `_path_covers` matches none — run on both, each side of the "also" included."""
    import importlib.util
    import re as _re

    asm = (ROOT / "commands" / "assemble_commands.py").read_text()
    assert (
        '_CLOSE_FEEDBACK = "close-feedback"' in asm and '_AGENT_FEEDBACK = "agent-feedback"' in asm
    )
    assert 'text = text.rstrip("\\n") + "\\n\\n" + frags[_CLOSE_FEEDBACK] + "\\n"' in asm
    assert (
        "body = frags.get(_AGENT_FEEDBACK" in asm
        and 'text = text.rstrip("\\n") + "\\n\\n" + body + "\\n"' in asm
    )
    for name in ("close-feedback", "agent-feedback"):
        assert (ROOT / "commands" / "_fragments" / f"{name}.md").exists()
    for src in (ROOT / "commands" / "_sources").glob("*.md"):
        assert not _re.search(
            r"\{\{include:\s*(close-feedback|agent-feedback)\s*\}\}", src.read_text()
        ), src.name
    spec = importlib.util.spec_from_file_location("eo", ROOT / "scripts" / "epic_order.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    g = mod._glob_matches
    assert g(
        "commands/_fragments/term-edit.md", "commands/_fragments/term-edit.md"
    )  # the path it names
    assert g("commands/_fragments", "commands/_fragments/term-edit.md")  # a directory's subtree
    assert g("templates/chrome-extension/**", "templates/chrome-extension/src/a.ts")  # a glob
    assert not g("src/a/*", "src/a/b/deep.py")  # `*` stays inside one segment
    assert not g("commands/_fragments", "commands/_fragments_old/x.md")
    import sys as _sys

    readers = {}
    for name, rel in (("cpt_lock", "check_phase_tests.py"), ("cpk_lock", "check_plan_tickets.py")):
        sp = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "enforcement" / rel)
        m = importlib.util.module_from_spec(sp)
        _sys.modules[name] = m
        sp.loader.exec_module(m)
        readers[name] = m
    glob_entry, target = "templates/chrome-extension/**", "templates/chrome-extension/src/a.ts"
    # `_owned` matches all three shapes since W-9fcb6ce4 (a glob, `*` inside one segment); `_path_covers` none
    assert readers["cpt_lock"]._owned(target, [glob_entry])
    assert not readers["cpt_lock"]._owned("src/a/b/deep.py", ["src/a/*"])
    assert not readers["cpk_lock"]._path_covers(glob_entry, target)
    assert not readers["cpk_lock"]._path_covers("src/a/*", "src/a/b.py")  # nor a single-segment `*`
    assert readers["cpt_lock"]._owned("Commands/_Fragments/a.md", ["commands/_fragments"])
    assert not readers["cpk_lock"]._path_covers("commands/_fragments", "Commands/_Fragments/a.md")
    assert readers["cpk_lock"]._path_covers("commands/_fragments/a.md", "commands/_fragments")
    assert not readers["cpt_lock"]._owned("commands/_fragments", ["commands/_fragments/a.md"])


def test_the_lock_check_set_of_scripts_that_mention_owned_paths_is_pinned() -> None:
    """W-bcf6fc2f part 1: the PHASE 2 lock bullet says no script that tests a path against a lock's
    `owned_paths` is the ownership rule, and names `_owned` and `_path_covers`. A new script reading `owned_paths` could
    make that sentence false while every existing pin stayed green. This test lists every file under scripts/
    that names `owned_paths` by that literal spelling (keyed on the field, not on how the lock directory is
    spelled) and fails on one it has not met, so the bullet is re-read whenever that set changes. Its limit: it pins which files name
    the field, not what they do with it. What the two named matchers do with a glob is pinned by
    test_the_lock_check_names_the_appended_fragment_and_how_an_entry_owns_a_path, which runs them, and a new glob
    matcher added inside a known file escapes both. The role beside each entry is a note for the reader who adds
    the next one, not a checked fact. Cobra: the cheap way past it is to add a file without reading it."""
    known = {
        "scripts/enforcement/check_phase_tests.py": "lock reader: `_owned` matches a path (named in the bullet)",
        "scripts/enforcement/check_plan_tickets.py": "lock reader: `_path_covers` matches a path (named); epics too",
        "scripts/enforcement/check_plan_lock_release.py": "lock reader: compares owned_paths to ['**'] only",
        "scripts/epic_order.py": "epic frontmatter owned_paths, not plan locks",
        "scripts/doc_reconcile.py": "writes owned_paths for the docs it dispatches",
        "scripts/sysadmin/canary_grounding.py": "writes owned_paths for canary specs",
    }
    found = set()
    for path in sorted((ROOT / "scripts").rglob("*")):
        # every regular file, not only .py: a shell or extensionless runner can read a lock too; a dangling
        # symlink is not a file, and __pycache__ holds compiled copies of the .py files already scanned
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if b"owned_paths" in path.read_bytes():
            found.add(path.relative_to(ROOT).as_posix())
    assert found == set(known), sorted(found ^ set(known))


