"""W-696d4d7e — the documentation pack's blank-line rule names TABLES.

WHY. `.windsurf/rules/core/40-documentation.md` asked for blank lines around headings, lists and code blocks, but not
tables. Under CommonMark with the table extension, a line flush against a table's last row is parsed as one more row,
so a paragraph written straight after a table vanishes into it. markdownlint's MD058 (`blanks-around-tables`) is the
lint for it. The pack is fleet-synced, and the cheatsheet and the prompt-templates doc state the same list, so all
three name tables.
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "core" / "40-documentation.md"
CHEATSHEET = ROOT / "docs" / "reference" / "MD" / "markdown-cheatsheet.md"
TEMPLATES = ROOT / "docs" / "reference" / "MD" / "ai-prompt-templates.md"


def test_a_paragraph_line_flush_against_a_table_renders_as_a_row() -> None:
    """The defect the rule prevents, executed: a flush paragraph line is a `<td>`, a blank-separated one a `<p>`; a
    flush heading or list item ends the table instead, which is why the rule says a PARAGRAPH line."""
    md = MarkdownIt("commonmark").enable("table")
    table = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    flush = md.render(table + "After the table.\n")
    spaced = md.render(table + "\nAfter the table.\n")
    assert "<td>After the table.</td>" in flush and "<p>After the table.</p>" not in flush
    assert "<p>After the table.</p>" in spaced
    assert "</table>\n<h1>H</h1>" in md.render(table + "# H\n")
    assert "</table>\n<ul>" in md.render(table + "- item\n")


def test_the_pack_and_both_docs_name_tables_in_the_blank_line_rule() -> None:
    pack = PACK.read_text(encoding="utf-8").splitlines()
    assert (
        "- **Blank lines around headings, lists, code blocks, tables** — parser boundary signals (a paragraph"
        " line flush against a table's last row renders as one more row)"
    ) in pack
    assert (
        "| Blank lines around headings, lists, code blocks, tables | Parser boundary signals |"
        in (CHEATSHEET.read_text(encoding="utf-8").splitlines())
    )
    templates = TEMPLATES.read_text(encoding="utf-8")
    tables = templates[templates.index("### Tables") : templates.index("### AI-specific")]
    assert (
        "| Blank lines around tables | MD058 | a blank line before and after every table — a paragraph line flush"
        " against the last row renders as one more row |" in tables
    )
