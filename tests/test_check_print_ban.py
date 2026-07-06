"""Unit tests for check_print_ban.is_template_generator.

The print-ban exempts a whole file that carries a top-of-file `# noqa-file: template-generator`
COMMENT directive (its apparent print()s are emitted-project code). The match must be a comment
that BEGINS with the marker — never a bare substring, a string literal, or a prose mention.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
from check_print_ban import is_template_generator  # noqa: E402


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
