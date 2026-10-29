"""Unit tests for check_print_ban.is_template_generator.

The print-ban exempts a whole file that carries a top-of-file `# noqa-file: template-generator`
COMMENT directive (its apparent print()s are emitted-project code). The match must be a comment
that BEGINS with the marker — never a bare substring, a string literal, or a prose mention.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
from check_print_ban import is_template_generator, should_skip  # noqa: E402


def _write(tmp_path: Path, text: str) -> str:
    f = tmp_path / "f.py"
    f.write_text(text)
    return str(f)


def test_directive_comment_matches(tmp_path: Path) -> None:
    src = "#!/usr/bin/env python3\n# noqa-file: template-generator\nprint('emitted')\n"
    assert is_template_generator(_write(tmp_path, src))


def test_string_literal_mention_does_not_match(tmp_path: Path) -> None:
    # e.g. another check comparing against the marker string — must NOT disable the ban.
    src = 'marker = "noqa-file: template-generator"\nprint("real")\n'
    assert not is_template_generator(_write(tmp_path, src))


def test_prose_comment_mention_does_not_match(tmp_path: Path) -> None:
    src = "# see noqa-file: template-generator for details\nprint('real')\n"
    assert not is_template_generator(_write(tmp_path, src))


def test_no_marker_does_not_match(tmp_path: Path) -> None:
    assert not is_template_generator(_write(tmp_path, "# ordinary module\nprint('real')\n"))


def test_marker_past_first_lines_does_not_match(tmp_path: Path) -> None:
    body = "\n".join(f"# line {i}" for i in range(25))
    assert not is_template_generator(_write(tmp_path, body + "\n# noqa-file: template-generator\n"))


def test_missing_file_returns_false(tmp_path: Path) -> None:
    assert not is_template_generator(str(tmp_path / "does-not-exist.py"))


def test_docs_files_are_skipped() -> None:
    # docs/ holds documentation + archived examples, never production code.
    assert should_skip("docs/archive/examples/health_check_usage.py")
    assert not should_skip("src/fabrik/cli.py")


# --- the ban matches a CALL of the builtin, never an identifier ending in "print" (mail 01M3ZHT9HB,
# W-5ee4557e: web-ecommerce-factory's `def _fingerprint(html, hosts)` was reported as print()).


def test_identifiers_ending_in_print_are_not_the_builtin(tmp_path: Path) -> None:
    from check_print_ban import scan_file_for_pattern

    f = tmp_path / "m.py"
    f.write_text(
        "def _fingerprint(html, hosts):\n"
        "    x = blueprint(1)\n"
        "    self.print(2)\n"
        "    footprint (3)\n"
        "print(4)\n"
        "    builtins.print(5)\n"
        "y = [print(6)]\n"
        "__builtins__.print(7)\n"
        "    def print(self, x):\n"
        "    the lines to print (the count, the NOTEs)\n"
    )
    assert scan_file_for_pattern(str(f), "print(") == [5, 6, 7, 8]


def test_console_log_needs_the_bare_object(tmp_path: Path) -> None:
    from check_print_ban import scan_file_for_pattern

    f = tmp_path / "m.ts"
    f.write_text(
        "myconsole.log(1);\nwindow.console.log(2);\nconsole.log(3);\n$console.log(4);\nconsole?.log(5);\n"
    )
    assert scan_file_for_pattern(str(f), "console.log(") == [2, 3, 5]


def test_definitions_and_attribute_chains_are_not_the_builtin(tmp_path: Path) -> None:
    from check_print_ban import scan_file_for_pattern

    f = tmp_path / "m.py"
    f.write_text(
        "    def  print(self):\n"
        "\tdef\tprint(self):\n"
        "obj.builtins.print(1)\n"
        "mybuiltins.print(2)\n"
        "x = 1; print(3)\n"
        "undef_print(4)\n"
    )
    assert scan_file_for_pattern(str(f), "print(") == [5]
