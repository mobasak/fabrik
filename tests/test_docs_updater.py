"""Tests for docs_updater.py documentation automation features."""

# Import the module functions
import re
import sys
from pathlib import Path

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
        assert "<!-- Phase:" in table and "phased_order" in table

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
            "git merge --no-ff",  # the merge protocol
        ):
            assert needle in text, f"doc does not name {needle!r}"
        # the pending half is labelled as pending, never stated as shipped
        assert text.count("on master (T01b, merged 2026-09-06)") >= 3
        assert "in acceptance, not yet merged" in text  # T13 (R2)
        assert len(text.splitlines()) <= 150
