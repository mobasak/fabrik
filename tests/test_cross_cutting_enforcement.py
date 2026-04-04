"""Tests for cross-cutting enforcement scripts.

Covers:
- check_print_ban.py (Tier 1)
- check_user_guide.py (Tier 2)
- check_reusable_modules.py (Tier 2, warning-level)
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.enforcement.check_print_ban import main as print_ban_main  # noqa: E402, I001
from scripts.enforcement.check_print_ban import scan_file_for_pattern  # noqa: E402
from scripts.enforcement.check_print_ban import should_skip  # noqa: E402
from scripts.enforcement.check_reusable_modules import get_module_files  # noqa: E402
from scripts.enforcement.check_reusable_modules import main as reusable_main  # noqa: E402
from scripts.enforcement.check_user_guide import has_user_guide_enabled  # noqa: E402
from scripts.enforcement.check_user_guide import main as user_guide_main  # noqa: E402


class TestCheckPrintBan:
    """Tests for check_print_ban.py."""

    def test_py_file_with_print_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Staged .py production file with print() should fail."""
        monkeypatch.chdir(tmp_path)
        bad_file = tmp_path / "src" / "mymodule.py"
        bad_file.parent.mkdir(parents=True)
        bad_file.write_text('print("hello world")\n')

        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/mymodule.py"],
        ):
            assert print_ban_main() == 1

    def test_py_file_without_print_passes(self, tmp_path: Path, monkeypatch) -> None:
        """Staged .py file using logger instead of print() should pass."""
        monkeypatch.chdir(tmp_path)
        good_file = tmp_path / "src" / "mymodule.py"
        good_file.parent.mkdir(parents=True)
        good_file.write_text('logger.info("hello world")\n')

        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/mymodule.py"],
        ):
            assert print_ban_main() == 0

    def test_test_file_skipped(self, tmp_path: Path) -> None:
        """Files matching test patterns should be skipped even with print()."""
        test_file = tmp_path / "test_config.py"
        test_file.write_text('print("debug")\n')

        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=[str(test_file)],
        ):
            assert print_ban_main() == 0

    def test_scripts_dir_skipped(self, tmp_path: Path) -> None:
        """Files in scripts/ directory should be skipped."""
        script_file = tmp_path / "scripts" / "helper.py"
        script_file.parent.mkdir(parents=True)
        script_file.write_text('print("output")\n')

        # Use relative-like path with scripts/ prefix
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["scripts/helper.py"],
        ):
            assert print_ban_main() == 0

    def test_ts_file_with_console_log_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Staged .ts file with console.log() should fail."""
        monkeypatch.chdir(tmp_path)
        ts_file = tmp_path / "src" / "app.ts"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text('console.log("debug");\n')

        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/app.ts"],
        ):
            assert print_ban_main() == 1

    def test_comment_lines_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """print() in comments should not trigger a violation."""
        monkeypatch.chdir(tmp_path)
        py_file = tmp_path / "src" / "module.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text('# print("debug")\n')

        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/module.py"],
        ):
            assert print_ban_main() == 0

    def test_should_skip_patterns(self) -> None:
        """should_skip correctly identifies skip patterns."""
        assert should_skip("tests/test_foo.py") is True
        assert should_skip("scripts/helper.py") is True
        assert should_skip("src/utils/helper.py") is False

    def test_test_tsx_file_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """Regression: .test.tsx files must be skipped."""
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "src" / "Component.test.tsx"
        f.parent.mkdir(parents=True)
        f.write_text('console.log("test debug");\n')
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/Component.test.tsx"],
        ):
            assert print_ban_main() == 0

    def test_spec_js_file_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """Regression: .spec.js files must be skipped."""
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "src" / "api.spec.js"
        f.parent.mkdir(parents=True)
        f.write_text('console.log("spec debug");\n')
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/api.spec.js"],
        ):
            assert print_ban_main() == 0

    def test_test_jsx_file_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """Regression: .test.jsx files must be skipped."""
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "src" / "widget.test.jsx"
        f.parent.mkdir(parents=True)
        f.write_text('console.log("jsx debug");\n')
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/widget.test.jsx"],
        ):
            assert print_ban_main() == 0

    def test_spec_tsx_file_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """Regression: .spec.tsx files must be skipped."""
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "src" / "Form.spec.tsx"
        f.parent.mkdir(parents=True)
        f.write_text('console.log("spec tsx");\n')
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=["src/Form.spec.tsx"],
        ):
            assert print_ban_main() == 0

    def test_scan_file_for_pattern(self, tmp_path: Path) -> None:
        """scan_file_for_pattern returns correct line numbers."""
        f = tmp_path / "code.py"
        f.write_text("line1\nprint('hello')\nline3\nprint('bye')\n")
        lines = scan_file_for_pattern(str(f), "print(")
        assert lines == [2, 4]

    def test_no_staged_files_passes(self) -> None:
        """Empty staged file list should pass."""
        with patch(
            "scripts.enforcement.check_print_ban.get_staged_files",
            return_value=[],
        ):
            assert print_ban_main() == 0


class TestCheckUserGuide:
    """Tests for check_user_guide.py."""

    def test_no_project_yaml_passes(self, tmp_path: Path) -> None:
        """No project.yaml means no requirement — should pass."""
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 0

    def test_has_user_guide_false_passes(self, tmp_path: Path) -> None:
        """project.yaml with has_user_guide: false should pass."""
        (tmp_path / "project.yaml").write_text("has_user_guide: false\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 0

    def test_has_user_guide_true_missing_dir_fails(self, tmp_path: Path) -> None:
        """has_user_guide: true but no docs/user-guide/ should fail."""
        (tmp_path / "project.yaml").write_text("has_user_guide: true\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 1

    def test_has_user_guide_true_empty_dir_fails(self, tmp_path: Path) -> None:
        """has_user_guide: true with empty docs/user-guide/ should fail."""
        (tmp_path / "project.yaml").write_text("has_user_guide: true\n")
        guide_dir = tmp_path / "docs" / "user-guide"
        guide_dir.mkdir(parents=True)
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 1

    def test_has_user_guide_true_with_guide_passes(self, tmp_path: Path) -> None:
        """has_user_guide: true with docs/user-guide/index.md should pass."""
        (tmp_path / "project.yaml").write_text("has_user_guide: true\n")
        guide_dir = tmp_path / "docs" / "user-guide"
        guide_dir.mkdir(parents=True)
        (guide_dir / "index.md").write_text("# Getting Started\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 0

    def test_key_absent_passes(self, tmp_path: Path) -> None:
        """project.yaml without has_user_guide key should pass."""
        (tmp_path / "project.yaml").write_text("name: my-project\ntype: python-api\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert user_guide_main() == 0

    def test_stdlib_parser_no_pyyaml(self, tmp_path: Path) -> None:
        """Regression: has_user_guide_enabled works without PyYAML import."""
        (tmp_path / "project.yaml").write_text("has_user_guide: true\n")
        assert has_user_guide_enabled(tmp_path) is True

    def test_stdlib_parser_false_value(self, tmp_path: Path) -> None:
        """Regression: stdlib parser returns False for 'false' value."""
        (tmp_path / "project.yaml").write_text("has_user_guide: false\n")
        assert has_user_guide_enabled(tmp_path) is False

    def test_stdlib_parser_missing_file(self, tmp_path: Path) -> None:
        """Regression: stdlib parser returns False when file missing."""
        assert has_user_guide_enabled(tmp_path) is False

    def test_stdlib_parser_yes_value(self, tmp_path: Path) -> None:
        """Regression: stdlib parser accepts YAML 'yes' as truthy."""
        (tmp_path / "project.yaml").write_text("has_user_guide: yes\n")
        assert has_user_guide_enabled(tmp_path) is True


class TestCheckReusableModules:
    """Tests for check_reusable_modules.py."""

    def test_no_utils_dir_passes(self, tmp_path: Path) -> None:
        """No src/utils/ or src/lib/ should pass."""
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert reusable_main() == 0

    def test_module_tagged_passes(self, tmp_path: Path) -> None:
        """Module in src/utils/ tagged [reusable] in INDEX.md should pass."""
        utils_dir = tmp_path / "src" / "utils"
        utils_dir.mkdir(parents=True)
        (utils_dir / "helpers.py").write_text("def helper(): pass\n")
        (tmp_path / "INDEX.md").write_text("- `src/utils/helpers.py` — Utility helpers [reusable]\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert reusable_main() == 0

    def test_module_untagged_warns_but_passes(self, tmp_path: Path, capsys) -> None:
        """Untagged module should warn but still return 0 (non-blocking)."""
        utils_dir = tmp_path / "src" / "utils"
        utils_dir.mkdir(parents=True)
        (utils_dir / "helpers.py").write_text("def helper(): pass\n")
        (tmp_path / "INDEX.md").write_text("- `src/utils/helpers.py` — Utility helpers\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            result = reusable_main()
        assert result == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_init_py_excluded(self, tmp_path: Path) -> None:
        """__init__.py should not be checked."""
        utils_dir = tmp_path / "src" / "utils"
        utils_dir.mkdir(parents=True)
        (utils_dir / "__init__.py").write_text("")
        modules = get_module_files(tmp_path)
        assert len(modules) == 0

    def test_lib_dir_also_scanned(self, tmp_path: Path) -> None:
        """Modules in src/lib/ should also be detected."""
        lib_dir = tmp_path / "src" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "auth.py").write_text("def auth(): pass\n")
        (tmp_path / "INDEX.md").write_text("- `src/lib/auth.py` — Auth library [reusable]\n")
        with patch.dict(os.environ, {"FABRIK_ROOT": str(tmp_path)}):
            assert reusable_main() == 0


class TestFinalGateAdvisory:
    """Integration tests for advisory warning surfacing in final_gate."""

    def test_advisory_check_surfaces_warning(self, tmp_path: Path, capsys) -> None:
        """Regression: run_optional_check with advisory=True preserves stdout on exit 0."""
        # Create a minimal script that prints a WARNING and exits 0
        script = tmp_path / "warn_script.py"
        script.write_text('import sys\nprint("WARNING: something untagged")\nsys.exit(0)\n')

        # Import and call run_optional_check with advisory=True
        from scripts.final_gate import run_optional_check

        with patch("scripts.final_gate.FABRIK_ROOT", tmp_path):
            name, passed, msg = run_optional_check(
                str(script.name), "Test Advisory", advisory=True
            )
        assert passed is True
        assert "WARNING" in msg

    def test_non_advisory_check_drops_stdout(self, tmp_path: Path) -> None:
        """Non-advisory check should drop stdout on exit 0 (existing behavior)."""
        script = tmp_path / "ok_script.py"
        script.write_text('import sys\nprint("all good")\nsys.exit(0)\n')

        from scripts.final_gate import run_optional_check

        with patch("scripts.final_gate.FABRIK_ROOT", tmp_path):
            name, passed, msg = run_optional_check(
                str(script.name), "Test Non-Advisory"
            )
        assert passed is True
        assert msg == ""

    def test_print_step_shows_advisory_output(self, capsys) -> None:
        """Regression: print_step renders advisory output in yellow when passed."""
        from scripts.final_gate import print_step

        print_step("Reusable Module Tagging", True, "WARNING: 1 module(s) untagged")
        captured = capsys.readouterr()
        assert "WARNING: 1 module(s) untagged" in captured.out
        assert "PASS" in captured.out
