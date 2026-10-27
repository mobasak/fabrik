"""Tests for docs_updater.py documentation automation features."""

# Import the module functions
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from docs_updater import (
    PLANS_BLOCK_RE,
    STRUCTURE_BLOCK_RE,
    extract_block_body,
    generate_plans_table,
    is_public_module,
    replace_block,
)


class TestBoundedBlockReplacement:
    """Tests for bounded block replacement (idempotency)."""

    def test_replace_block_changes_when_body_differs(self):
        """Block should be replaced when body content changes."""
        text = """# Header

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-01-01T00:00Z -->
old content
<!-- AUTO-GENERATED:STRUCTURE:END -->

# Footer
"""
        new_body = "new content"
        result, changed = replace_block(text, new_body, STRUCTURE_BLOCK_RE, "STRUCTURE")

        assert changed is True
        assert "new content" in result
        assert "old content" not in result

    def test_replace_block_idempotent_when_body_same(self):
        """Block should NOT be replaced when body content is identical."""
        text = """# Header

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-01-01T00:00Z -->
same content
<!-- AUTO-GENERATED:STRUCTURE:END -->

# Footer
"""
        new_body = "same content"
        result, changed = replace_block(text, new_body, STRUCTURE_BLOCK_RE, "STRUCTURE")

        assert changed is False
        assert result == text  # Unchanged

    def test_extract_block_body_excludes_markers(self):
        """Extracted body should not include HTML comment markers."""
        text = """<!-- AUTO-GENERATED:PLANS:START -->
<!-- AUTO-GENERATED:PLANS v1 | 2026-01-01T00:00Z -->
| Plan | Date |
|------|------|
<!-- AUTO-GENERATED:PLANS:END -->"""

        body = extract_block_body(text, PLANS_BLOCK_RE)

        assert body is not None
        assert "<!--" not in body
        assert "| Plan | Date |" in body


class TestPublicModuleDetection:
    """Tests for public module detection."""

    def test_is_public_module_with_all(self, tmp_path):
        """Module with __all__ should be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("__all__ = ['foo', 'bar']")

        assert is_public_module(mod) is True

    def test_is_public_module_with_readme(self, tmp_path):
        """Module with README.md should be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("# empty")
        (mod / "README.md").write_text("# My Module")

        assert is_public_module(mod) is True

    def test_is_public_module_without_markers(self, tmp_path):
        """Module without __all__ or README should NOT be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("# internal module")

        assert is_public_module(mod) is False

    def test_is_public_module_without_init(self, tmp_path):
        """Directory without __init__.py should NOT be detected as module."""
        mod = tmp_path / "notamodule"
        mod.mkdir()

        assert is_public_module(mod) is False


class TestPlansTableGeneration:
    """Tests for plans table generation."""

    def test_generate_plans_table_empty(self, tmp_path, monkeypatch):
        """Empty plans directory should generate placeholder table."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()

        # Monkeypatch PLANS_DIR
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans_dir)

        table = generate_plans_table()

        assert "(none)" in table
        assert "| Epic/Plan | Owner | Status | Phase |" in table

    def test_generate_plans_table_with_files(self, tmp_path, monkeypatch):
        """Plans directory with files should generate proper table."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "2026-01-07-test-plan.md").write_text("# Test Plan")

        # Monkeypatch PLANS_DIR
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans_dir)

        table = generate_plans_table()

        assert "2026-01-07-test-plan.md" in table
        assert "2026-01-07" in table
        assert "Active" in table


class TestStubCreation:
    """Tests for module stub creation."""

    def test_stub_creation_skips_existing(self, tmp_path, monkeypatch):
        """Existing docs should NOT be overwritten."""
        import docs_updater

        # Setup
        ref_dir = tmp_path / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        existing = ref_dir / "mymodule.md"
        existing.write_text("# Existing content - DO NOT OVERWRITE")

        mod = tmp_path / "src" / "fabrik" / "mymodule"
        mod.mkdir(parents=True)
        (mod / "__init__.py").write_text("__all__ = ['foo']")

        monkeypatch.setattr(docs_updater, "PROJECT_ROOT", tmp_path)

        # Try to create stub
        from docs_updater import create_module_stub

        result = create_module_stub(mod)

        assert result is False
        assert "DO NOT OVERWRITE" in existing.read_text()


class TestSyncedDocsAreNotLinkChecked:
    """Fabrik-synced governance/reference copies are gitignored in consuming projects and their
    links resolve only in the repo that OWNS them (`scripts/kilo-benchmarks/*`,
    `docs/workflows/*`). Checking them against a consuming project reported broken links no
    project could fix and blocked /fabrik-release, whose preconditions require this check green.
    Reported from tryton-crm 2026-08-10 with 4 such rows.
    """

    @staticmethod
    def _repo(tmp_path, *, ignore_line: str) -> Path:
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".gitignore").write_text(ignore_line + "\n")
        synced = tmp_path / "docs" / "reference" / "kilo"
        synced.mkdir(parents=True)
        (synced / "BENCHMARK_SOURCES.md").write_text(
            "# Sources\n\n[tool](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py)\n"
        )
        owned = tmp_path / "docs"
        (owned / "OWNED.md").write_text("# Owned\n\n[gone](../scripts/does_not_exist.py)\n")
        return tmp_path

    def test_a_gitignored_synced_doc_is_skipped(self, tmp_path, monkeypatch):
        root = self._repo(tmp_path, ignore_line="docs/reference/kilo/")
        monkeypatch.chdir(root)
        import docs_updater as du

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert not any("BENCHMARK_SOURCES" in i for i in issues), issues

    def test_a_tracked_doc_with_a_broken_link_is_still_reported(self, tmp_path, monkeypatch):
        """Non-vacuity: the skip must be the gitignore predicate, not 'stop checking links'."""
        root = self._repo(tmp_path, ignore_line="docs/reference/kilo/")
        monkeypatch.chdir(root)
        import docs_updater as du

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert any("OWNED.md" in i for i in issues), (
            f"a repo-owned broken link must still fail: {issues}"
        )

    def test_when_nothing_is_ignored_the_synced_doc_is_checked(self, tmp_path, monkeypatch):
        """The hub owns these files (tracked there), so it must keep checking them — that is
        where a genuinely broken link can actually be fixed."""
        root = self._repo(tmp_path, ignore_line="# nothing ignored")
        monkeypatch.chdir(root)
        import docs_updater as du

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert any("BENCHMARK_SOURCES" in i for i in issues), issues

    def test_git_failure_falls_back_to_checking_everything(self, tmp_path, monkeypatch):
        """A visible false positive beats silently skipping a doc the project really owns."""
        import docs_updater as du

        monkeypatch.setattr(
            du.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no git"))
        )
        assert du._gitignored([tmp_path / "docs" / "x.md"]) == set()


class TestPlansTableOwnerColumn:
    """T15 (multi-agent-per-repo): the PLANS.md block gains an Owner column, drops Date,
    renames Progress to Phase, and lists epics beside plans."""

    @staticmethod
    def _tree(tmp_path: Path) -> Path:
        plans = tmp_path / "docs" / "development" / "plans"
        epics = tmp_path / "docs" / "development" / "epics"
        plans.mkdir(parents=True)
        epics.mkdir(parents=True)
        (plans / "2026-01-01-plan-1-alpha-work.md").write_text(
            "# Plan A\n\n**Owner:** alpha\n\nStatus: DRAFT\n\n- [x] one\n- [ ] two\n",
            encoding="utf-8",
        )
        (plans / "2026-01-02-plan-2-unowned.md").write_text(
            "# Plan B\n\nStatus: DRAFT\n", encoding="utf-8"
        )
        # a live hub shape: the Owner line carries a prose tail — the cell is the NAME only
        (plans / "2026-01-03-plan-3-prose-owner.md").write_text(
            "# Plan C\n\n**Owner:** infra (build) — spec by fleet, execution on the go-word\n\n"
            "Status: CONVERGED\n",
            encoding="utf-8",
        )
        (epics / "2026-01-01-epic-1-thing.md").write_text(
            '---\nkind: story\ntitle: "Epic 1"\nstatus: 1\nepic_n: 1\nslug: thing\n'
            "depends_on: []\nparallel_with: []\nowned_paths: []\nowner: beta\n---\n# Epic 1\n",
            encoding="utf-8",
        )
        return plans

    def test_bc1_owner_column_from_plan_line_and_epic_frontmatter(self, tmp_path, monkeypatch):
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        table = generate_plans_table()
        lines = [ln for ln in table.splitlines() if ln.startswith("|")]
        assert lines[0] == "| Epic/Plan | Owner | Status | Phase |"
        assert "| Plan | Date |" not in table
        by_name = {ln.split("](")[0].lstrip("| ["): ln for ln in lines[2:]}
        # plan with **Owner:** alpha → alpha; Phase = Board progress
        assert "| alpha | DRAFT | 1/2 |" in by_name["2026-01-01-plan-1-alpha-work.md"]
        # plan with no owner line → the em dash (the tail sweep fills it)
        assert "| — | DRAFT | - |" in by_name["2026-01-02-plan-2-unowned.md"]
        # prose-tailed Owner line → the leading name token only
        assert "| infra | CONVERGED | - |" in by_name["2026-01-03-plan-3-prose-owner.md"]
        # epic: owner from frontmatter, status 1 = IN_PROGRESS, Phase = phased_order position
        assert "| beta | IN_PROGRESS | 1 |" in by_name["2026-01-01-epic-1-thing.md"]
        assert "(epics/2026-01-01-epic-1-thing.md)" in table
        # the Phase source is DEFINED in the block's own header comment
        assert "<!-- Phase:" in table and "depends_on" in table

    @staticmethod
    def _stale_index(tmp_path: Path) -> Path:
        idx = tmp_path / "docs" / "development" / "PLANS.md"
        idx.write_text(
            "# Plans\n\n<!-- AUTO-GENERATED:PLANS:START -->\n"
            "<!-- AUTO-GENERATED:PLANS v1 | 2026-01-01T00:00 -->\n"
            "| Plan | Date | Status | Progress |\n|---|---|---|---|\n| stale | - | - | - |\n"
            "<!-- AUTO-GENERATED:PLANS:END -->\n\n## Tail\n",
            encoding="utf-8",
        )
        return idx

    def test_bc2_stale_block_is_regenerated_in_place_then_check_is_clean(
        self, tmp_path, monkeypatch
    ):
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        idx = self._stale_index(tmp_path)
        monkeypatch.setattr(docs_updater, "PLANS_INDEX", idx)
        assert docs_updater.validate_plans_indexed(), "precondition: the block must read stale"
        changed, _msg = docs_updater.sync_plans_index()
        assert changed is True
        text = idx.read_text(encoding="utf-8")
        assert "| Epic/Plan | Owner | Status | Phase |" in text
        assert "| stale |" not in text
        assert text.startswith("# Plans\n") and text.endswith("## Tail\n")  # only the block moved
        assert docs_updater.validate_plans_indexed() == []
        # idempotent: a second sync is a no-op (the header comment must not defeat the compare)
        assert docs_updater.sync_plans_index()[0] is False

    def test_bc3_untouched_stale_block_is_a_check_finding(self, tmp_path, monkeypatch):
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        idx = self._stale_index(tmp_path)
        monkeypatch.setattr(docs_updater, "PLANS_INDEX", idx)
        before = idx.read_text(encoding="utf-8")
        findings = docs_updater.validate_plans_indexed()
        assert findings and all("PLANS" in f for f in findings)
        assert idx.read_text(encoding="utf-8") == before  # --check never mutates

    def test_epics_without_epic_order_render_a_visible_placeholder_row(self, tmp_path, monkeypatch):
        # docs_updater.py is fleet-synced; scripts/epic_order.py is NOT. A project with an
        # epics dir must not crash --sync/--check, and must not silently drop its epics either.
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        monkeypatch.setitem(sys.modules, "epic_order", None)
        monkeypatch.setitem(sys.modules, "scripts.epic_order", None)
        table = generate_plans_table()
        assert "| beta |" not in table  # the parser was genuinely unavailable
        assert "1 epic file(s) not listed" in table and "epic_order.py" in table
        assert "2026-01-01-plan-1-alpha-work.md" in table  # plans still render

    def test_pipes_in_owner_and_status_are_escaped_to_keep_four_cells(self, tmp_path, monkeypatch):
        # acceptance round 1 [M]: an unescaped `|` in an epic `owner:` or a plan `Status:` split a
        # row into 5 cells (executed: 0 of 25 live rows today; 1 of 291 plan-shaped .md under
        # plans/ carries a pipe in its 20-char status, under archived/).
        import docs_updater

        plans = self._tree(tmp_path)
        (plans.parent / "epics" / "2026-01-02-epic-2-piped.md").write_text(
            '---\nkind: story\ntitle: "Epic 2"\nstatus: 0\nepic_n: 2\nslug: piped\n'
            'depends_on: []\nparallel_with: []\nowned_paths: []\nowner: "a | b"\n---\n# E2\n',
            encoding="utf-8",
        )
        (plans / "2026-01-04-plan-4-piped-status.md").write_text(
            "# Plan D\n\nStatus: A | B pipes\n", encoding="utf-8"
        )
        # round 2 [L]: an ALREADY-escaped pipe (a hand-edited owner) must not be escaped again —
        # `a \\| b` is a literal backslash followed by a live delimiter, the 5-cell split again.
        (plans.parent / "epics" / "2026-01-03-epic-3-pre-escaped.md").write_text(
            '---\nkind: story\ntitle: "Epic 3"\nstatus: 0\nepic_n: 3\nslug: pre\n'
            'depends_on: []\nparallel_with: []\nowned_paths: []\nowner: "a \\| b"\n---\n# E3\n',
            encoding="utf-8",
        )
        # round 3 [L]: escaping is by PARITY — `a\\|b` (two backslashes in the FILE) is an escaped
        # backslash followed by a LIVE pipe; epic_order's flat parser hands the raw `a\\|b` back
        # (verified: loaded owner repr 'a\\\\|b'), so the cell must become `a\\\|b`.
        (plans.parent / "epics" / "2026-01-04-epic-4-two-backslashes.md").write_text(
            '---\nkind: story\ntitle: "Epic 4"\nstatus: 0\nepic_n: 4\nslug: two\n'
            'depends_on: []\nparallel_with: []\nowned_paths: []\nowner: "a\\\\|b"\n---\n# E4\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans)
        table = generate_plans_table()
        rows = [ln for ln in table.splitlines() if ln.startswith("| [")]
        assert len(rows) == 8, table  # 4 epics + 4 plans
        for row in rows:
            # a pipe is a delimiter when preceded by an EVEN number of backslashes (zero incl.)
            cells = re.split(r"(?<!\\)(?:\\\\)*\|", row.strip())[1:-1]
            assert len(cells) == 4, row
        assert r"| a \| b |" in table
        assert r"| A \| B pipes |" in table
        assert "| a\\\\\\|b |" in table  # the cell text is a\\\|b
        assert "| a\\\\|b |" not in table  # never left as a live delimiter
        assert "| a \\\\| b |" not in table  # never double-escaped

    def test_a_reworded_phase_note_is_a_stale_finding(self, tmp_path, monkeypatch):
        # acceptance round 1 [L]: the note DEFINES the Owner/Phase columns; if the compare dropped
        # every comment line, rewording it would leave every repo's stale definition in place with
        # no signal. Only the writer's stamp line is excluded from the compare.
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        idx = self._stale_index(tmp_path)
        monkeypatch.setattr(docs_updater, "PLANS_INDEX", idx)
        assert docs_updater.sync_plans_index()[0] is True
        assert docs_updater.validate_plans_indexed() == []
        monkeypatch.setattr(
            docs_updater, "_PLANS_PHASE_NOTE", "<!-- Phase: a REWORDED definition -->"
        )
        assert docs_updater.validate_plans_indexed(), "a reworded note must read stale"
        assert docs_updater.sync_plans_index()[0] is True
        assert "<!-- Phase: a REWORDED definition -->" in idx.read_text(encoding="utf-8")
        assert docs_updater.validate_plans_indexed() == []

    def test_an_undecodable_epic_file_renders_the_placeholder_row(self, tmp_path, monkeypatch):
        # acceptance round 1 [L]: load_epics() opens every *.md as UTF-8; one undecodable file
        # aborted --check/--sync with UnicodeDecodeError. Same placeholder row as the missing-parser
        # branch beside it — never a crash, never silence.
        import docs_updater

        plans = self._tree(tmp_path)
        (plans.parent / "epics" / "2026-01-03-epic-3-binary.md").write_bytes(
            b"---\n\xff\xfe\n---\n"
        )
        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans)
        table = generate_plans_table()
        assert "2 epic file(s) not listed" in table and "not decodable" in table
        assert "| beta |" not in table
        assert "2026-01-01-plan-1-alpha-work.md" in table

    def test_no_plans_index_or_no_block_is_not_a_finding(self, tmp_path, monkeypatch):
        # Mirror of BC3: docs_updater.py is fleet-synced — a project with no PLANS.md, or one
        # without the markers, has opted out of the table and must not red its gate.
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", self._tree(tmp_path))
        missing = tmp_path / "docs" / "development" / "PLANS.md"
        monkeypatch.setattr(docs_updater, "PLANS_INDEX", missing)
        assert docs_updater.validate_plans_indexed() == []
        assert docs_updater.sync_plans_index()[0] is False
        missing.write_text("# Plans\n\nno markers here\n", encoding="utf-8")
        assert docs_updater.validate_plans_indexed() == []
        assert docs_updater.sync_plans_index()[0] is False


class TestMultiAgentOperatingModelDoc:
    """T15 BC4: the dedicated reference doc names the four emitted artifacts, the launch form
    and the lock path exactly as T01a/T01b and T04a/T04b implement them — T01a/T04a/T04b are on
    master; T01b's emission (rows 2, 4, the mid-epic loop) is PLANNED text until T01b merges, and
    the doc says so on each of those rows."""

    DOC = Path(__file__).parent.parent / "docs" / "reference" / "multi-agent-operating-model.md"

    def test_doc_exists_and_names_the_planned_surfaces(self):
        assert self.DOC.is_file(), f"missing: {self.DOC}"
        text = self.DOC.read_text(encoding="utf-8")
        for needle in (
            "claude --worktree <name> -n <name>-<repo>",  # the launch form (one per window)
            ".worktreeinclude",  # artifact 1 (T01a declares, T01b emits)
            '"symlinkDirectories": [".venv"]',  # artifact 2: the settings.json worktree block
            '"baseRef": "head"',
            ".claude/worktrees/",  # artifact 3: the .gitignore line
            "rerere.enabled",  # artifact 4: the two git config keys
            "push.autoSetupRemote",
            ".fabrik/plan-locks/",  # the lock location (T04b: unchanged, per working tree)
            "scripts/merge_request.py merge",  # the merge protocol (`merge_request.py` runs `git merge --no-ff` itself)
        ):
            assert needle in text, f"doc does not name {needle!r}"
        # the pending half is labelled as pending, never stated as shipped
        assert text.count("on master (T01b, merged 2026-09-06)") >= 3
        assert "On master (T13, merged 2026-09-06)" in text  # T13 (R2)
        # No line cap: T15's 150-line ceiling (last enforced at aedcf64c6) was a plan-era snapshot; the
        # doc became the canonical operating model and passed it at f4fac0204 (2026-09-16), growing
        # through every reviewed change since. Its contract is the named surfaces above, not a length.


# W-961bede1: --sync must keep a project's own STRUCTURE rows (trade-intelligence 01M3RTNQ).
_SCRIPT = Path(__file__).parent.parent / "scripts" / "docs_updater.py"
_FILES = (
    "docs/a/README.md",
    "docs/b/README.md",
    "docs/design-system.md",
    "docs/saved.md",
    "docs/plans/set1/a.md",
    "docs/plans/set1/b.md",
    "docs/reference/x.md",
    "docs/QUICKSTART.md",
    "docs/windsurf/w.md",
)
# The reporter's literal shapes: `name/   # text` (a hand-collapsed dir) and `name# text`.
_HAND_BLOCK = (
    "docs/\n"
    "├── QUICKSTART.md                   # Get Fabrik running in 5 minutes\n"
    "├── a\n"
    "│   └── README.md                   # Readme of a\n"
    "├── b\n"
    "│   └── README.md                   # Readme of b\n"
    "├── design-system.md                # Design-system declaration (house identity)\n"
    "├── plans\n"
    "│   └── set1/   # Plan set (spine + T01-T12): enrich persona\n"
    "├── reference\n"
    "├── saved.md# Saved search config\n"
    "└── windsurf                        # Windsurf IDE optimization\n"
)


def _structure_project(root: Path, block: str, files=_FILES) -> Path:
    for rel in files:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n")
    (root / "INDEX.md").write_text(
        "# Index\n<!-- AUTO-GENERATED:STRUCTURE:START -->\n```text\n"
        + block
        + "```\n<!-- AUTO-GENERATED:STRUCTURE:END -->\n"
    )
    return root


def _sync(root: Path) -> str:
    import subprocess

    subprocess.run(
        [sys.executable, str(_SCRIPT), "--sync"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return extract_block_body((root / "INDEX.md").read_text(), STRUCTURE_BLOCK_RE)


def _row(body: str, name: str) -> str:
    for line in body.splitlines():
        text = line.lstrip("│ ├└─")
        if text == name or text.startswith((name + " ", name + "/")):
            return line
    raise AssertionError(f"no row {name!r} in:\n{body}")


def test_sync_keeps_hand_written_row_comments_by_path(tmp_path):
    body = _sync(_structure_project(tmp_path, _HAND_BLOCK))
    assert _row(body, "design-system.md").endswith("# Design-system declaration (house identity)")
    assert _row(body, "saved.md").endswith("# Saved search config")
    lines = body.splitlines()
    a = next(i for i, ln in enumerate(lines) if ln.endswith("── a"))
    b = next(i for i, ln in enumerate(lines) if ln.endswith("── b"))
    assert lines[a + 1].endswith("# Readme of a") and lines[b + 1].endswith("# Readme of b"), body


def test_sync_keeps_a_hand_collapsed_directory_collapsed(tmp_path):
    body = _sync(_structure_project(tmp_path, _HAND_BLOCK))
    row = _row(body, "set1")
    assert "set1/" in row and row.endswith("# Plan set (spine + T01-T12): enrich persona"), body
    assert "a.md" not in body.split("set1", 1)[1].split("├──", 1)[0], body


def test_a_hub_commented_directory_expands_when_populated(tmp_path):
    lines = _sync(_structure_project(tmp_path, _HAND_BLOCK)).splitlines()
    ref = next(i for i, ln in enumerate(lines) if ln.lstrip("│ ├└─").startswith("reference"))
    assert lines[ref + 1].endswith("── x.md"), (
        lines
    )  # the empty `reference` row expands, x.md under it


def test_hub_text_follows_the_hub_dict(tmp_path):
    body = _sync(_structure_project(tmp_path, _HAND_BLOCK))
    assert "Get Fabrik running in 5 minutes" in _row(body, "QUICKSTART.md")  # current hub text
    assert _row(body, "windsurf").endswith("# Windsurf IDE reference (retired 2026-07-19)"), body


def test_sync_is_idempotent_over_carried_comments(tmp_path):
    root = _structure_project(tmp_path, _HAND_BLOCK)
    _sync(root)
    first = (root / "INDEX.md").read_text()
    _sync(root)
    assert (root / "INDEX.md").read_text() == first


def test_a_deleted_rows_comment_is_dropped(tmp_path):
    root = _structure_project(tmp_path, _HAND_BLOCK)
    (root / "docs/design-system.md").unlink()
    (root / "docs/new.md").write_text("x\n")
    (root / "docs/FAQ.md").write_text("x\n")
    body = _sync(root)
    assert "design-system.md" not in body and "house identity" not in body
    assert " # " not in _row(body, "new.md")
    assert _row(body, "FAQ.md").endswith("# Frequently asked questions")  # a new hub-known file


def test_an_orphan_row_never_lands_on_another_file(tmp_path):
    block = "docs/\n├─ broken\n│   └── README.md                   # Orphan text\n├── a\n"
    body = _sync(_structure_project(tmp_path, block, files=("docs/README.md", "docs/a/README.md")))
    assert "Orphan text" not in body, body


# ── W-ab678eb9 (tryton-crm 01M3T9H8): --sync in a linked worktree must not drop the main checkout's
# gitignored STRUCTURE rows. A worktree lacks the main checkout's ignored files, so a walk of its own
# disk rewrote the committed block without them.

_DU = Path(__file__).parent.parent / "scripts" / "docs_updater.py"


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _run_sync(cwd: Path) -> str:
    import subprocess

    subprocess.run(
        [sys.executable, str(_DU), "--sync"], cwd=cwd, check=True, capture_output=True, text=True
    )
    return extract_block_body((cwd / "INDEX.md").read_text(), STRUCTURE_BLOCK_RE) or ""


def _main_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout with ignored docs (a file and a collapsed dir with a hand comment) synced
    into a committed block, plus a linked worktree of it."""
    main = tmp_path / "main"
    (main / "docs" / "guide").mkdir(parents=True)
    (main / "docs" / "guide" / "a.md").write_text("a\n")
    (main / "docs" / "old.md").write_text("old\n")
    (main / "docs" / "private" / "deep").mkdir(parents=True)
    (main / "docs" / "private" / "deep" / "d.md").write_text("d\n")
    (main / "docs" / "notes.md").write_text("n\n")
    (main / ".gitignore").write_text("docs/private/\ndocs/notes.md\n")
    (main / "INDEX.md").write_text(
        "# Index\n<!-- AUTO-GENERATED:STRUCTURE:START -->\n<!-- AUTO-GENERATED:STRUCTURE:END -->\n"
    )
    _git(main, "init", "-q")
    _run_sync(main)
    block = (main / "INDEX.md").read_text()
    collapsed = "└── private/                         # hand note on private\n"
    assert "└── private\n    └── deep\n        └── d.md\n" in block, block
    block = block.replace("└── private\n    └── deep\n        └── d.md\n", collapsed)
    (main / "INDEX.md").write_text(block)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt))
    return main, wt


def test_worktree_sync_carries_ignored_rows(tmp_path):
    _main, wt = _main_with_worktree(tmp_path)
    body = _run_sync(wt)
    assert "notes.md" in body, body
    assert "private/" in body and "hand note on private" in body, body


def test_worktree_sync_lists_its_own_new_doc(tmp_path):
    _main, wt = _main_with_worktree(tmp_path)
    (wt / "docs" / "fresh.md").write_text("f\n")
    assert "fresh.md" in _run_sync(wt)


def test_worktree_sync_drops_deleted_tracked_row(tmp_path):
    """Non-vacuity: only IGNORED absent rows are carried; a deleted tracked doc is not resurrected."""
    _main, wt = _main_with_worktree(tmp_path)
    (wt / "docs" / "old.md").unlink()
    assert "old.md" not in _run_sync(wt)


def test_disk_wins_a_name_clash_with_a_carried_row(tmp_path):
    """A carried child `x/y.md` forces its parent `x` to a directory; when `docs/x` is a plain
    FILE on the worktree's disk, the disk wins: `x` is listed as a file and `y.md` is not."""
    _main, wt = _main_with_worktree(tmp_path)
    (wt / ".gitignore").write_text((wt / ".gitignore").read_text() + "docs/x/\n")
    (wt / "docs" / "x").write_text("now a file\n")
    index = (wt / "INDEX.md").read_text()
    (wt / "INDEX.md").write_text(index.replace("docs/\n", "docs/\n├── x\n│   └── y.md\n", 1))
    body = _run_sync(wt)
    assert "x" in body.split() and "y.md" not in body, body


def test_main_checkout_subdir_is_not_a_worktree(tmp_path):
    """A main checkout run from a subdirectory reads `--git-dir` absolute and `--git-common-dir`
    relative; compared raw they differ, so the subdirectory project would carry stale rows."""
    main, _wt = _main_with_worktree(tmp_path)
    sub = main / "sub"
    (sub / "docs").mkdir(parents=True)
    (sub / "docs" / "x.md").write_text("x\n")
    (sub / ".gitignore").write_text("docs/gone.md\n")
    (sub / "INDEX.md").write_text(
        "# Sub\n<!-- AUTO-GENERATED:STRUCTURE:START -->\n```text\ndocs/\n└── gone.md\n```\n"
        "<!-- AUTO-GENERATED:STRUCTURE:END -->\n"
    )
    assert "gone.md" not in _run_sync(sub)


def test_structure_outside_git_is_plain_walk(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("x\n")
    (tmp_path / "INDEX.md").write_text(
        "# I\n<!-- AUTO-GENERATED:STRUCTURE:START -->\n```text\ndocs/\n└── gone.md\n```\n"
        "<!-- AUTO-GENERATED:STRUCTURE:END -->\n"
    )
    body = _run_sync(tmp_path)
    assert "x.md" in body and "gone.md" not in body, body


# site-provisioner 01M4DBKECA: a status VALUE outside the exact-first tuple was graded by whatever
# word came later in its own line — `BUILT … Earlier: CONVERGED` read CONVERGED.
def _plan_with_status(tmp_path, line: str):
    p = tmp_path / "2026-10-08-plan-x.md"
    p.write_text(f"# Plan\n\n**Status:** {line}\n\n## Tasks\n", encoding="utf-8")
    return p


def test_a_status_value_is_never_overridden_by_later_history_text(tmp_path):
    import docs_updater as du

    p = _plan_with_status(tmp_path, "BUILT 2026-09-05 — shipped in 0074c60. Earlier: CONVERGED")
    assert du.parse_plan_status(p)[0] == "BUILT"
    # real status lines from plans on the box (design critiques, Opus + Fable)
    for line, want in (
        ("✅ EXECUTED 2026-08-13 — whole-plan review converged", "EXECUTED"),
        ("⛔ PINNED — DO NOT EXECUTE AS-WRITTEN (was CONVERGED 2026-07-07)", "PINNED"),
        ("✅ **CLOSED 2026-06-02**", "CLOSED"),
        ("BUILT IN PART, not EXECUTED (relabelled 2026-10-02)", "PARTIAL"),
        ("DONE IN PART, remaining items pending", "PARTIAL"),
        ("✓ EXECUTED — superseded by X (converged)", "EXECUTED"),
        ("✓ EXECUTED, converged with baseline", "EXECUTED"),
        ("BUILT; converged earlier", "BUILT"),
        ("BUILT, IN PART, not EXECUTED", "PARTIAL"),
        ("In-Progress — phase 2", "IN_PROGRESS"),
        ("DONE (2026-07-01) — converged earlier", "COMPLETE"),
        ("RESOLVED — see Resolution", "RESOLVED"),
    ):
        p = _plan_with_status(tmp_path, line)
        assert du.parse_plan_status(p)[0] == want, line
    for word in sorted(du._PLAN_STATUS_WORDS):
        p = _plan_with_status(tmp_path, f"{word.upper()} — earlier: converged, then executed")
        assert du.parse_plan_status(p)[0] == word.upper(), word


def test_the_done_sets_agree_and_a_built_plan_is_done():
    """docs_updater's PLAN_DONE and work.py's _PLAN_DONE grade the same plans as finished; a BUILT
    plan is finished in both (it is never handed an owner nor listed as active)."""
    import docs_updater as du
    import work

    assert du.PLAN_DONE == work._PLAN_DONE
    assert {"BUILT", "IMPLEMENTED", "SHIPPED", "CLOSED", "FIXED"} <= du.PLAN_DONE
    # RESOLVED labels a resolved issue inside an unfinished plan (check_plan_lock_release)
    assert "RESOLVED" not in du.PLAN_DONE and "PARTIAL" not in du.PLAN_DONE


def test_the_phase_note_names_no_hub_only_path():
    """The note is written into every repo's PLANS.md; a project has no scripts/epic_order.py."""
    import docs_updater as du

    assert "epic_order.py" not in du._PLANS_PHASE_NOTE
    assert "depends_on" in du._PLANS_PHASE_NOTE


def test_work_open_plans_reads_the_shared_done_set(tmp_path):
    """work.py's open-plan view lists a not-finished plan and hides a BUILT one, through the
    docs_updater it imports (review B-S2: the agreement test never ran the consumer)."""
    import work

    plans = tmp_path / "docs" / "development" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-10-01-plan-a.md").write_text(
        "# A\n\n**Status:** BUILT 2026-10-01 — Earlier: CONVERGED\n"
    )
    (plans / "2026-10-02-plan-b.md").write_text("# B\n\n**Status:** APPROVED — phases pending\n")
    out = work._open_plans(tmp_path)
    assert any("plan-b" in line for line in out), out
    assert not any("plan-a" in line for line in out), out


class TestLinkCheckReadsCommonMarkLinks:
    """W-f11e740e: check_link_integrity read links with its own `\\[..\\]\\(([^)]+)\\)` regex, so a
    titled or <angle> link to a live doc was reported broken and an escaped or paren name was
    skipped unexamined; it now reads destinations through check_doc_links.link_targets."""

    @staticmethod
    def _issues(tmp_path, monkeypatch, body: str, files=("live.md", "a_b.md", "a(b).md", "a#b.md")):
        import docs_updater as du

        docs = tmp_path / "docs"
        docs.mkdir()
        for name in files:
            (docs / name).write_text("# x\n")
        (docs / "src.md").write_text(body)
        monkeypatch.setattr(du, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(du, "_gitignored", lambda paths: set())
        return [i for i in du.check_link_integrity() if "src.md" in i]

    def test_a_commonmark_link_to_a_live_doc_is_not_broken(self, tmp_path, monkeypatch):
        body = '[t](live.md "a title")\n[a](<live.md>)\n[e](a\\_b.md)\n[p](a(b).md)\n[plain](live.md)\n'
        assert self._issues(tmp_path, monkeypatch, body) == []

    def test_a_commonmark_link_to_a_missing_doc_names_its_real_path(self, tmp_path, monkeypatch):
        body = '[t](gone.md "a title")\n[a](<gone2.md>)\n[p](g(o)ne.md)\n'
        issues = self._issues(tmp_path, monkeypatch, body)
        assert any(i.endswith(": gone.md") for i in issues), issues
        assert any(i.endswith(": gone2.md") for i in issues), issues
        assert any(i.endswith(": g(o)ne.md") for i in issues), issues

    def test_an_escaped_hash_in_a_name_is_not_cut(self, tmp_path, monkeypatch):
        """link_targets already dropped the fragment and undid `\\#`; a second cut checked `a`."""
        assert self._issues(tmp_path, monkeypatch, "[h](a\\#b.md)\n") == []

    def test_the_link_check_falls_back_to_the_regex_and_says_so(
        self, tmp_path, monkeypatch, capsys
    ):
        """With both import names gone the advisory row still runs, on today's regex."""
        monkeypatch.setitem(sys.modules, "enforcement.check_doc_links", None)
        monkeypatch.setitem(sys.modules, "scripts.enforcement.check_doc_links", None)
        issues = self._issues(tmp_path, monkeypatch, "[g](gone.md)\n")
        assert any("gone.md" in i for i in issues), issues
        captured = capsys.readouterr()
        assert "link_targets unavailable" in captured.err  # stdout carries only the report
        assert "link_targets unavailable" not in captured.out

    def test_a_uri_scheme_link_is_not_a_file(self, tmp_path, monkeypatch):
        """A paren is now a path character, so `javascript:alert(1)` stopped being skipped as
        regex-ish and was checked as a file (4 fleet docs, the after-diff): any URI scheme is
        external, not only http(s)/mailto/file."""
        body = (
            "[x](javascript:alert(1))\n[t](tel:+15550100)\n[d](data:text/plain,hi)\n"
            "[m](MAILTO:a@b.c)\n[u](urn:ietf:rfc:2119)\n[g](geo:37.7,-122.4)\n[s](ms-settings:display)\n"
        )
        assert self._issues(tmp_path, monkeypatch, body) == []

    def test_a_colon_in_a_relative_name_is_still_graded(self, tmp_path, monkeypatch):
        """Review passes 1-2: a dot or slash before the colon makes it a path, so `notes.md:12` and
        `src/gone.py:1` are graded; a dot-free 2+ character prefix (`ab:c.md`) reads as a scheme."""
        issues = self._issues(tmp_path, monkeypatch, "[a](src/gone.py:1)\n[b](notes.md:12)\n")
        assert any(i.endswith(": src/gone.py:1") for i in issues), issues
        assert any(i.endswith(": notes.md:12") for i in issues), issues

    def test_a_protocol_relative_link_is_not_a_repo_file(self, tmp_path, monkeypatch):
        assert self._issues(tmp_path, monkeypatch, "[c](//cdn.example.com/x.js)\n") == []

    def test_two_links_to_one_missing_target_report_it_once(self, tmp_path, monkeypatch):
        """The shared reader's line holds no link text, so duplicates would print identically."""
        issues = self._issues(tmp_path, monkeypatch, "[a](gone.md)\nand [b](gone.md)\n")
        assert issues == [i for i in issues if i.endswith(": gone.md")]
        assert len(issues) == 1, issues


class TestLinkCheckSkipsCodeExamples:
    """W-69f51003: `_strip_quoted` removed ``` fences and blockquotes only, so a link inside an
    inline code span or a `~~~` fence — a code EXAMPLE — was graded, and a `~~~` fence showing a
    ``` line paired that line with the next real fence. The link check now blanks both fence kinds
    in one pass before `_strip_quoted` and blanks inline spans after it."""

    @staticmethod
    def _issues(tmp_path, monkeypatch, body: str) -> list[str]:
        import docs_updater as du

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "live.md").write_text("# x\n")
        (docs / "src.md").write_bytes(body.encode())
        monkeypatch.setattr(du, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(du, "_gitignored", lambda paths: set())
        return [i.rsplit(": ", 1)[1] for i in du.check_link_integrity() if "src.md" in i]

    def test_link_integrity_skips_links_in_code_spans_and_tilde_fences(self, tmp_path, monkeypatch):
        body = (
            "Use `[a](a.md)` and ``[b](`b`.md)`` and `![](img.png)` here.\n"
            "A span `crossing\n[c](c.md)` lines.\n"
            "A CRLF span `crossing\r\n[d](d.md)` lines.\r\n\n"
            "A span `opening\n[h](h.md)\n` closing at a line start.\n\n"
            "~~~\n[e](e.md)\n~~~\n\n"
            "~~~md\n[f](f.md)\n~~~~\n\n"
            "~~~\r\n[g](g.md)\r\n~~~\r\n\n"
            "```js\n[i](i.md)\n`````\n\n"
            "[a]`(x)`(glue.md) is blanked, never deleted into a link.\n"
            "a](`see [x](stray.md)`) — a stray `](` shields no span.\n"
            "[live](live.md) stays.\n"
        )
        assert self._issues(tmp_path, monkeypatch, body) == []

    def test_link_integrity_fence_kinds_do_not_pair_across_each_other(self, tmp_path, monkeypatch):
        body = (
            "~~~\n```python\n[ex1](ex1.md)\n~~~\n[real](real.md)\n\n"
            "```\n[ex2](ex2.md)\n```\n[real2](real2.md)\n"
        )
        assert sorted(self._issues(tmp_path, monkeypatch, body)) == ["real.md", "real2.md"]

    @pytest.mark.parametrize(
        "body",
        [
            "``[s](s.md)` tail\n",  # an opener is a whole run: `` never pairs with `
            "\\`[s](s.md)` tail\n",  # an escaped backtick opens nothing
            "- item `open\n- [s](s.md) y` z\n",  # a span never crosses into a list item
            "# Title `open\n[s](s.md) x` y\n",  # nor out of a heading
            "| a `x | [s](s.md) |\n| b | c` |\n",  # nor out of a table row
            "para `open\n\n[s](s.md) x` y\n",  # nor across a blank line
            "para `open\r\n\r\n[s](s.md) x` y\r\n",  # a CRLF blank line too
            '[s](s.md "a `quote")\n',  # a backtick in a title
            '[s](s.md "a `quote") and `x`\n',  # opens no span with a later backtick
            "~~~\n[s](s.md)\n",  # an unclosed fence grades its links (the safe direction)
            "```a`b\n[s](s.md)\n",  # a ``` opener's info string holds no backtick
            "```x [y](y.md) ```\n[s](s.md)\n\n```\n[e](e.md)\n```\n",  # nor this one
            "`open\n---\n[s](s.md) x`\n",  # a setext underline ends the paragraph
            "`open\n===\n[s](s.md) x`\n",
            "`open\n***\n[s](s.md) x`\n",  # so does a thematic break
        ],
    )
    def test_link_integrity_still_reports_links_beside_stray_backticks(
        self, tmp_path, monkeypatch, body
    ):
        assert self._issues(tmp_path, monkeypatch, body) == ["s.md"]

    def test_a_backtick_in_a_link_destination_opens_no_span(self, tmp_path, monkeypatch):
        assert self._issues(tmp_path, monkeypatch, "[s](`s`.md)\n") == ["`s`.md"]

    def test_the_fence_walk_is_linear_on_unclosed_openers(self):
        """The first build's fence regex searched to end of file from every unclosed opener
        (100 KB took 24 s); the walk reads each line once."""
        import time

        import docs_updater as du

        text = "```x\n" * 200_000
        start = time.perf_counter()
        assert du._blank_code_fences(text) == text
        assert time.perf_counter() - start < 5


# W-8f9a7d2c: a code span that crosses a line break, with a header key opening its second line, won first-match
# over the real header. The scans skip a header whose KEY a code span holds and read every value from the original
# text, so a value in code font (a live hub form) keeps it.
def _plan(tmp_path, body: str):
    p = tmp_path / "2026-10-20-plan-span.md"
    p.write_text(f"# Plan\n\n{body}\n## Tasks\n", encoding="utf-8")
    return p


def test_a_status_line_inside_a_code_span_never_wins(tmp_path):
    import docs_updater as du

    p = _plan(
        tmp_path,
        "The header grammar is `one line,\nStatus: DRAFT` in an example.\n\n**Status:** COMPLETE\n",
    )
    assert du.parse_plan_status(p)[0] == "COMPLETE"
    p = _plan(tmp_path, "See ``a\n**Status:** DRAFT`` here.\n\n**Status:** EXECUTED\n")
    assert du.parse_plan_status(p)[0] == "EXECUTED"


def test_an_owner_line_inside_a_code_span_never_wins(tmp_path):
    import docs_updater as du

    p = _plan(tmp_path, "Write it as `a\nOwner: someone` here.\n\n**Owner:** intel\n")
    assert du.parse_plan_owner(p) == "intel"


def test_a_backticked_header_value_is_kept(tmp_path):
    import docs_updater as du

    p = _plan(
        tmp_path, "**Status:** `COMPLETE`\n**Owner:** `[infra]` · **Shape:** monolith (2 phases)\n"
    )
    assert du.parse_plan_status(p)[0] == "COMPLETE"
    assert du.parse_plan_owner(p) == "infra"


def test_a_span_opened_line_and_an_unclosed_backtick_read_as_today(tmp_path):
    import docs_updater as du

    p = _plan(
        tmp_path,
        "`check_x` Status: DRAFT example\n`run_y` Owner: nobody\n**Status:** EXECUTED\n**Owner:** intel\n",
    )
    assert (du.parse_plan_status(p)[0], du.parse_plan_owner(p)) == ("EXECUTED", "intel")
    p = _plan(tmp_path, "Type the ` key.\n**Status:** DRAFT\n**Owner:** intel\n")
    assert (du.parse_plan_status(p)[0], du.parse_plan_owner(p)) == ("DRAFT", "intel")


def test_two_stray_backticks_around_the_only_header_still_read_it(tmp_path):
    """Review pass 1 (S-s1, S-h1): two stray backticks pair into a span around the plan's only header; with no
    header outside a span the scan falls back to the first match, as before, rather than read Active / no owner
    (and `--adopt` would then write a second Owner line)."""
    import docs_updater as du

    p = _plan(tmp_path, "Use ` here\n**Status:** COMPLETE\n**Owner:** intel\nthen ` there\n")
    assert (du.parse_plan_status(p)[0], du.parse_plan_owner(p)) == ("COMPLETE", "intel")
    p = _plan(
        tmp_path, "**Status:** EXECUTED — see `scripts/x.py\n**Owner:** intel — also `y` here\n"
    )
    assert (du.parse_plan_status(p)[0], du.parse_plan_owner(p)) == ("EXECUTED", "intel")


# ── W-16c00597: _blank_code_spans is linear, with the quadratic original as its oracle ─────────────────────────────
# The function below is `_blank_code_spans` VERBATIM as it stood at commit ed16ac2a7 (the last change before
# W-16c00597), renamed and pointed at the module's own regex constants. It scanned forward from every unmatched
# opener to its paragraph's end and found each opener's line start by an rfind — quadratic on one long line.
import bisect  # noqa: E402

import docs_updater as du  # noqa: E402

_FX = du._fences_module()  # the regexes moved to _fences with the function (W-b9af1d47)


def _old_blank_code_spans(content: str) -> str:
    runs = list(_FX._BACKTICK_RUN_RE.finditer(content))
    tails = [(m.start(1), m.end(1)) for m in _FX._LINK_TAIL_RE.finditer(content)]
    tail_starts = [start for start, _ in tails]
    out, kept, i = [], 0, 0
    while i < len(runs):
        opener = runs[i]
        i += 1
        # W-753040b8: the opener rule moved to CommonMark's backslash parity in the linear function, and this oracle
        # takes the SAME rule — its job is linear-vs-quadratic equivalence; the escape rule is graded in test_fences.py
        o_start, o_len = opener.start(), len(opener.group())
        b = o_start
        while b and content[b - 1] == "\\":
            b -= 1
        if (o_start - b) % 2:
            o_start, o_len = o_start + 1, o_len - 1
            if not o_len:
                continue
        t = bisect.bisect_right(tail_starts, o_start) - 1
        if t >= 0 and o_start < tails[t][1]:
            continue
        line_start = content.rfind("\n", 0, opener.start()) + 1
        one_line = _FX._ONE_LINE_BLOCK_RE.match(content, line_start) is not None
        seen = opener.end()
        for j in range(i, len(runs)):
            # only the text since the last run is new; each line it starts is checked whole
            starts = [m.end() for m in re.finditer("\n", content[seen : runs[j].start()])]
            if starts and (
                one_line or any(_FX._BLOCK_START_RE.match(content, seen + s) for s in starts)
            ):
                break
            seen = runs[j].end()
            if len(runs[j].group()) == o_len:
                out += [
                    content[kept:o_start],
                    du._blank(content[o_start : runs[j].end()]),
                ]
                kept, i = runs[j].end(), j + 1
                break
    return "".join(out) + content[kept:]


_FUZZ_TOKENS = [
    "`",
    "``",
    "```",
    "````",
    "`````",
    "x",
    " ",
    "\t",
    "\n",
    "\n\n",
    "\r",
    "\r\n",
    "# h\n",
    "#h",
    "- ",
    "+ ",
    "1. ",
    "2) ",
    "> ",
    ">",
    "| a |",
    "\\`",
    "\\\\",
    "[a](b`c)",
    "[t]",
    "](x)",
    "[a [b] c](d `e (f`) g)",
    "[",
    "]",
    "(",
    ")",
    "===\n",
    "---\n",
    "***\n",
    "* * *\n",
    "___\n",
    "~~~",
    "```x\n",
    "    ",
    "é",
]

_FIXTURES = [
    "",
    "`a`",
    "`a\n- `x",
    "`a\n```b` c",
    "`` a ` b ``",
    "\\`a` `b`",
    "[a](x `y) z` w",
    "a `b\n\nc` d",
    "a `b\r\n\r\nc` d",
    "# h `a\nb` c",
    "| `a | b` |\n| c |",
    "a `b\n    c` d",
    "a `b\n===\nc` d",
    "`" * 5 + "a" + "`" * 3 + "b" + "`" * 5,
    "`a\n" * 50 + "`",
]


@pytest.mark.parametrize("text", _FIXTURES)
def test_blank_code_spans_equals_the_quadratic_original_on_fixtures(text: str) -> None:
    assert du._blank_code_spans(text) == _old_blank_code_spans(text)


def test_blank_code_spans_equals_the_quadratic_original_on_fuzz() -> None:
    import random

    rng = random.Random(0x16C00597)
    for _ in range(5000):
        text = "".join(rng.choice(_FUZZ_TOKENS) for _ in range(rng.randint(0, 40)))
        assert du._blank_code_spans(text) == _old_blank_code_spans(text), repr(text)


def _best_of_3(text: str) -> float:
    import time

    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        du._blank_code_spans(text)
        best = min(best, time.perf_counter() - start)
    return best


def test_blank_code_spans_beats_the_quadratic_original_on_unmatched_runs() -> None:
    """1 500 unmatched distinct-length runs on one line: the original scans to the paragraph's end per opener (about
    a second here), the linear walk takes milliseconds. Measured against the oracle on the same box, so a slow or busy
    box slows both and the ~300x gap stays far above the 20x asserted. The original's other cost, a line-start rfind
    per opener (26 s on 4 MB of dense pairs), separates from the forward walk only past ~2 MB, too slow for the suite —
    the equality tests above guard that path's answer, not its speed."""
    import time

    text = " x ".join("`" * (k + 1) + " y" for k in range(1500))
    start = time.perf_counter()
    _old_blank_code_spans(text)
    old = time.perf_counter() - start
    assert _best_of_3(text) * 20 < old, (old, _best_of_3(text))


# --- W-da101088: what the staleness gate may watch -------------------------------------------
# A watched doc must be one the project can edit and may keep where it is: a stale-header row on a
# hub-synced file or on a path check_structure calls misplaced is a row nobody can clear (D-1272).

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "enforcement"))
import check_structure  # noqa: E402
import fabrik_synced_manifest  # noqa: E402


def _not_the_projects_to_edit(entries: list[str]) -> list[str]:
    # This tree's own synced set, never the main checkout's (the function's default root).
    readonly = set(fabrik_synced_manifest.review_readonly_paths(Path(__file__).resolve().parents[1]))
    return [e for e in entries if e in readonly]


def _misplaced(entries: list[str]) -> list[str]:
    # The fallback allowlist lacks API_REFERENCE.md, so a failed registry import would be red
    # for a reason that has nothing to do with the list.
    assert check_structure._doc_registry is not None, "doc registry import failed"
    # Ask the structure gate itself, path by path: any violation it reports means misplaced.
    root = Path(__file__).resolve().parents[1]
    return [e for e in entries if check_structure.check_structure(root, files=[e])]


def test_no_watched_doc_is_a_file_the_project_cannot_edit() -> None:
    assert _not_the_projects_to_edit(du.MANUAL_DOCS) == []


@pytest.mark.parametrize(
    "synced",
    [
        "AGENTS.md",
        "agents-fabrik.md",
        "agents-fabrik-core.md",
        "CLAUDE.md",
        "docs/reference/convergence-prompts.md",
    ],
)
def test_the_readonly_guard_catches_every_synced_doc(synced: str) -> None:
    assert _not_the_projects_to_edit(["docs/QUICKSTART.md", synced]) == [synced]


def test_no_watched_doc_is_one_governance_misplaces() -> None:
    assert _misplaced(du.MANUAL_DOCS) == []


@pytest.mark.parametrize(
    "misplaced",
    [
        "docs/INDEX.md",
        "docs/NOTES.md",
        "docs/notes/setup.md",
        "notes.md",
        "docs/index.md",
        "scripts/notes.md",
        "src/x.md",
        "proposals/x.md",
    ],
)
def test_the_misplaced_guard_catches_every_spelling(misplaced: str) -> None:
    assert _misplaced(["docs/QUICKSTART.md", misplaced]) == [misplaced]


@pytest.mark.parametrize(
    "placed",
    ["README.md", "docs/QUICKSTART.md", "docs/guides/setup.md", "docs/foo/README.md", ".github/x.md"],
)
def test_the_misplaced_guard_passes_a_doc_governance_allows(placed: str) -> None:
    assert placed not in _misplaced([placed])


def test_staleness_skips_the_dropped_docs_and_still_runs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    for rel in ("AGENTS.md", "docs/INDEX.md", "docs/FUNNEL.md", "docs/AUTOMATION.md", "docs/QUICKSTART.md"):
        (tmp_path / rel).write_text("# no marker\n")
    (tmp_path / "docs/CONFIGURATION.md").write_text("**Last Updated:** 2000-01-01\n")
    monkeypatch.setattr(du, "PROJECT_ROOT", tmp_path)
    issues = du.check_staleness()
    assert issues[0] == "Missing 'Last Updated' date: docs/QUICKSTART.md"
    assert re.fullmatch(r"Stale doc \(\d+ days old\): docs/CONFIGURATION\.md", issues[1])
    assert len(issues) == 2
