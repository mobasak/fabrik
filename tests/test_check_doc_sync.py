"""Tests for the unified Doc Sync Matrix gate (scripts/enforcement/check_doc_sync.py).

Drives the real script over a throwaway git repo with staged changes — it reads
`git diff --cached`, so staging is how we exercise each rule. ERROR rows must fail
(exit 1); WARN rows must pass (exit 0) while printing a warning.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_doc_sync.py"
CHANGELOG_OK = "# Changelog\n\n## [Unreleased]\n\n### Added\n- a real entry\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


def _write(repo: Path, rel: str, content: str = "x\n") -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _stage(repo: Path, *rels: str) -> None:
    subprocess.run(["git", "add", "--", *rels], cwd=repo, check=True, timeout=15)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=30
    )


def test_significant_code_without_changelog_fails(repo: Path) -> None:
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 1 and "CHANGELOG.md not updated" in r.stdout


def test_significant_code_with_changelog_passes(repo: Path) -> None:
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_tests_only_change_needs_no_changelog(repo: Path) -> None:
    _write(repo, "tests/test_x.py", "def test_x():\n    assert True\n")
    _stage(repo, "tests/test_x.py")
    assert _run(repo).returncode == 0


def test_env_example_without_configuration_fails(repo: Path) -> None:
    _write(repo, ".env.example", "FOO=bar\n")
    _stage(repo, ".env.example")
    r = _run(repo)
    assert r.returncode == 1 and "CONFIGURATION.md" in r.stdout


def test_new_file_without_index_warns_not_blocks(repo: Path) -> None:
    # A brand-new doc file with no INDEX update → WARN (not block): exit 0 + warning.
    _write(repo, "docs/guides/new-guide.md", "# guide\n")
    _stage(repo, "docs/guides/new-guide.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout
    assert "INDEX.md not updated" in r.stdout


def test_compose_change_is_warn_only(repo: Path) -> None:
    # PORTS is a fuzzy row → WARN, never blocks. (Also touches INDEX+CHANGELOG to
    # isolate the PORTS rule: stage them so only the PORTS warning can surface.)
    _write(repo, "compose.yaml", "services: {}\n")
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _write(repo, "INDEX.md", "# idx\n")
    _stage(repo, "compose.yaml", "CHANGELOG.md", "INDEX.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout
    assert "PORTS.md" in r.stdout  # warning surfaced, but not blocking


def test_docs_only_change_passes(repo: Path) -> None:
    _write(repo, "docs/QUICKSTART.md", "# qs\n")
    _stage(repo, "docs/QUICKSTART.md")
    assert _run(repo).returncode == 0


def test_changelog_bare_todo_flagged(repo: Path) -> None:
    """bare `todo` in an [Unreleased] entry body IS an unfinished-work marker."""
    changelog = "# Changelog\n\n## [Unreleased]\n\n### Added\n- something bare todo needed\n"
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 1, r.stdout
    assert "placeholder" in r.stdout.lower()


def test_changelog_dated_todo_prose_reference_passes(repo: Path) -> None:
    """`dated-todo` as prose (naming the TODO-format convention) is NOT a placeholder."""
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "### Changed\n- documented the dated-todo format convention\n"
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_changelog_dated_todos_plural_prose_passes(repo: Path) -> None:
    """P6F1 regression: `dated-todos` (plural of the prose reference) is also
    a legitimate documentation naming — must NOT be flagged, symmetric with
    the singular `dated-todo`.
    """
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "### Changed\n- documented the dated-todos format convention\n"
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_changelog_plural_placeholders_flagged(repo: Path) -> None:
    """P5F1 regression: plural `TODOS` / `FIXMEs` are placeholder markers too.
    A letter-only boundary regex without `s?` would silently waive them
    (verified: `re.search(r"(?<![a-zA-Z])todo(?![a-zA-Z])", "todos")` = None).
    """
    changelog = "# Changelog\n\n## [Unreleased]\n\n### Fixed\n- see TODOS list before shipping\n"
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 1, r.stdout
    assert "placeholder" in r.stdout.lower()


def test_changelog_autodoc_not_flagged(repo: Path) -> None:
    """P4F1 regression: `autodoc` / `photodocumentation` / `fixmeup` contain
    the substring `todo`/`fixme` but are unrelated words — must NOT be flagged.
    A regex based on plain substring matching wrongly rejects them.
    """
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "### Added\n- autodoc generation and photodocumentation support\n"
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_changelog_compound_todo_still_flagged(repo: Path) -> None:
    """`updated-todo-list` is NOT the safe `dated-todo` prose reference —
    it's a genuine bare `todo` inside a hyphen chain. Substring bug in the
    regex would silently strip `dated-todo` and let this pass. Regression
    guard for the `\\bdated-todo\\b` fix.
    """
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "### Fixed\n- resolved the updated-todo-list before merge\n"
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", changelog)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 1, r.stdout
    assert "placeholder" in r.stdout.lower()


def test_backticked_placeholder_word_in_prose_is_not_unfinished_work(repo: Path) -> None:
    """A changelog entry DOCUMENTING placeholder tokens is not itself a placeholder.

    Live shared-tree false positive (2026-08-10): a sibling's entry described a
    credential-scanner change — "placeholder family narrowed (`example`/`sample`/`dummy`/
    `todo`/`tbd`)" — and the bare-token scan read the inline-code `todo` as unfinished work,
    reddening the gate for every agent in the repo.
    """
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Fixed — scanner tuned (2026-08-10)\n"
        "- placeholder family narrowed (`example`/`sample`/`dummy`/`todo`/`tbd`).\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 0, f"documented token must not read as a placeholder: {r.stdout}"


def test_bare_todo_in_the_changelog_still_fails(repo: Path) -> None:
    """The guard must keep catching a REAL unfinished-work marker outside code ticks."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Added — thing (2026-08-10)\n"
        "- shipped the thing. TODO: write the docs.\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    assert _run(repo).returncode == 1


def test_an_unbalanced_backtick_cannot_swallow_a_real_todo(repo: Path) -> None:
    """Inline-span stripping pairs backticks left-to-right, so ONE stray tick earlier on the line
    swallows everything up to the next tick — including a plainly-written unfinished-work marker.
    A typo elsewhere must not disable the guard (native review finding, reproduced)."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Fixed — thing (2026-08-10)\n"
        "- The `run flag is gone; TODO: document the `--force` path\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 1, f"a stray tick must not disable the TODO guard: {r.stdout}"


def test_a_quoted_task_marker_is_documentation_not_unfinished_work(repo: Path) -> None:
    """REVERSED after review. I first asserted that `TODO: wire the alert` inside ticks was
    unfinished work. That rule was wrong, and it made the gate RED on the hub for every agent —
    because the CHANGELOG paragraph describing the detector necessarily QUOTES the tokens it
    detects. A gate that cannot describe its own behaviour is broken. Inside balanced ticks is a
    quotation; the question this gate asks is only "is the entry itself a stub?"."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Fixed — thing (2026-08-10)\n"
        "- left a `TODO: wire the OOM alert` in poll_worker\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    assert _run(repo).returncode == 0


def test_the_gate_accepts_an_entry_describing_its_own_detector(repo: Path) -> None:
    """The self-inflicted hub-RED (review finding): this exact prose blocked every agent in the
    repo, with a message claiming [Unreleased] was 'empty or has a placeholder' while it held
    thousands of real entries."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Fixed — doc-sync guard (2026-08-10)\n"
        "- a stray tick swallowed `TODO: document the --force path`; the template tokens\n"
        "  `<brief title>` / `<description>` were also read from the wrong body.\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 0, f"the gate must not reject prose that documents it: {r.stdout}"


def test_plural_and_comment_forms_inside_ticks_are_quotations(repo: Path) -> None:
    """Strip/detect asymmetry (review finding): the detector had `s?`, the strip did not, so
    `todos` was rejected — a plausible real entry in any of ~48 repos."""
    for line in (
        "- scanner lists the `todos` it found",
        "- the linter now understands `# TODO` comments",
    ):
        _write(
            repo,
            "CHANGELOG.md",
            f"# Changelog\n\n## [Unreleased]\n\n### Fixed — x (2026-08-10)\n{line}\n",
        )
        _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
        _stage(repo, "CHANGELOG.md", "src/app/handler.py")
        assert _run(repo).returncode == 0, line


def test_an_actually_pasted_template_placeholder_is_still_rejected(repo: Path) -> None:
    """The real template is pasted WITHOUT ticks — that is the stub this gate exists to catch."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Added — <brief title> (2026-08-10)\n"
        "- <description>\n",
    )
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "CHANGELOG.md", "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 1, f"a ticked template placeholder must still fail: {r.stdout}"


def test_prose_fallback_does_not_fire_the_resilience_warning(repo):
    """2026-08-26 (web-ecommerce-factory upstream, measured 4/4 prose false-positives):
    the word "fallback" in a comment or operator-facing string is not a resilience
    pattern — a WARN whose only correct response is to ignore it trains scroll-past."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Added — classifier default (2026-08-26)\n- x\n",
    )
    _write(
        repo,
        "src/app/classify.py",
        "def classify(x):\n    # the fallback class shown to a human in the scan report\n"
        "    return 'fallback: unknown'\n",
    )
    _stage(repo, "CHANGELOG.md", "src/app/classify.py")
    r = _run(repo)
    assert "RESILIENCE" not in r.stdout, r.stdout


def test_retry_still_fires_the_resilience_warning(repo):
    """The counter-direction: dropping \\bfallback\\b must not have taken retry with it."""
    _write(
        repo,
        "CHANGELOG.md",
        "# Changelog\n\n## [Unreleased]\n\n### Added — retrying client (2026-08-26)\n- x\n",
    )
    _write(
        repo,
        "src/app/client.py",
        "def get(x):\n    for attempt in range(3):  # retry with backoff\n        pass\n",
    )
    _stage(repo, "CHANGELOG.md", "src/app/client.py")
    r = _run(repo)
    assert "RESILIENCE" in r.stdout, r.stdout


# ── the [Unreleased]-was-actually-touched rule ────────────────────────────────
# The quality check asks "does [Unreleased] hold a real entry" — a question about the
# FILE, not about YOUR change. On a shared tree [Unreleased] almost always holds a
# sibling's entry, so staging any cosmetic CHANGELOG edit answered it green. These
# three pin the corrected question: "did this change touch [Unreleased]".

_PRIOR = (
    "# Changelog\n\n## [Unreleased]\n\n"
    "### Added — a sibling's entry from another task (2026-08-27)\n- their work\n\n"
    "## [1.0.0] - 2026-01-01\n\n### Added\n- the old relase note\n"
)


def _commit(repo: Path, msg: str = "base") -> None:
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True, timeout=15)


def test_a_cosmetic_changelog_edit_does_not_satisfy_the_entry_requirement(repo: Path) -> None:
    """THE GAP: fixing a typo in an OLD release section stages CHANGELOG.md and leaves
    [Unreleased] byte-identical — yet the check passed on the strength of the sibling's
    entry. Staging the file is not the same as having an entry."""
    _write(repo, "CHANGELOG.md", _PRIOR)
    _write(repo, "README.md", "# r\n")
    _stage(repo, "CHANGELOG.md", "README.md")
    _commit(repo)

    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", _PRIOR.replace("old relase note", "old release note"))
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 1, r.stdout
    assert "[Unreleased] section was not" in r.stdout, r.stdout


def test_extending_an_existing_unreleased_entry_is_accepted(repo: Path) -> None:
    """The counter-direction, and the reason the rule is NOT "added a new ### heading":
    a task that spans commits writes its entry once and extends that prose afterwards.
    Measured over 223 significant-code commits in 5 repos — every compliant commit
    touches the section, but many add no new heading."""
    _write(repo, "CHANGELOG.md", _PRIOR)
    _write(repo, "README.md", "# r\n")
    _stage(repo, "CHANGELOG.md", "README.md")
    _commit(repo)

    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", _PRIOR.replace("- their work", "- their work\n- and my phase B"))
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_the_rule_fires_in_range_mode_too(repo: Path) -> None:
    """Positive control for --range, the whole-plan coverage receipt. Ran the real check over
    200 real hub commits in range mode and it fired 0 times; that number only means "no
    migration cost" if the range path is capable of firing at all."""
    _write(repo, "CHANGELOG.md", _PRIOR)
    _write(repo, "README.md", "# r\n")
    _stage(repo, "CHANGELOG.md", "README.md")
    _commit(repo)

    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", _PRIOR.replace("old relase note", "old release note"))
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    _commit(repo, "phase")
    r = subprocess.run(
        [sys.executable, str(CHECK), "--range", "HEAD~1..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 1, r.stdout
    assert "[Unreleased] section was not" in r.stdout, r.stdout


def test_range_mode_accepts_a_touched_section(repo: Path) -> None:
    """The counter-direction for --range: a range that DID extend the section stays green."""
    _write(repo, "CHANGELOG.md", _PRIOR)
    _write(repo, "README.md", "# r\n")
    _stage(repo, "CHANGELOG.md", "README.md")
    _commit(repo)

    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", _PRIOR.replace("- their work", "- their work\n- my entry"))
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    _commit(repo, "phase")
    r = subprocess.run(
        [sys.executable, str(CHECK), "--range", "HEAD~1..HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "[Unreleased] section was not" not in r.stdout, r.stdout


def test_an_unreadable_baseline_fails_open(repo: Path) -> None:
    """No HEAD yet (or no CHANGELOG at HEAD) means the question cannot be asked. This is
    an ERROR row on a governance-sync surface reaching ~46 repos: a check that cannot ask
    its question must not answer it. Never invent a red from an absent baseline."""
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_a_pydantic_only_models_py_does_not_demand_the_schema_dump(repo: Path) -> None:
    """The trigger matched the FILENAME: one `min_length` change in a Pydantic-only `models.py`
    was blocked for a missing `db/schema.sql` (site-provisioner 01M1QS9527Y8K0P9VPE9XF5MYB,
    2026-09-05). A `models.py` is a schema trigger only when its content defines an ORM model."""
    _write(
        repo, "db/schema.sql", "-- schema\n"
    )  # TRACKED: the old trigger exempted repos without a dump
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _write(
        repo,
        "api/models.py",
        "from pydantic import BaseModel\n\nclass Site(BaseModel):\n    name: str\n",
    )
    _stage(repo, "CHANGELOG.md", "api/models.py")
    r = _run(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "schema.sql" not in (r.stdout + r.stderr)


def test_an_orm_models_py_still_demands_the_schema_dump(repo: Path) -> None:
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _write(repo, "db/schema.sql", "-- schema\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    _write(
        repo,
        "app/models.py",
        "from sqlalchemy import Column, Integer\n\nclass Site(Base):\n    __tablename__ = 'site'\n    id = Column(Integer, primary_key=True)\n",
    )
    _stage(repo, "app/models.py")
    r = _run(repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "schema.sql" in (r.stdout + r.stderr)
