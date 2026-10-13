"""check_data_contract_legend — a frozen data contract's Enum-registry `Backing` cells obey the
template's closed legend (fleet 01M4TGT7N4, kaizen 01M4F92G6V). WARN-only: 107 cells in 9 projects
were off the grammar on 2026-10-13, so the check names them until each project re-freezes."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_data_contract_legend as c  # noqa: E402

_HEAD = "# Data Contract\n\n**Status:** FROZEN · **Version:** v3\n\n"


def _contract(root: Path, registry: str, heading: str = "## Enum registry") -> Path:
    p = root / "docs" / "data-contract.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{_HEAD}{heading}\n\n{registry}\n## Next section\n\ntext\n", encoding="utf-8")
    return p


def _table(*rows: tuple[str, str]) -> str:
    body = "".join(f"| {e} | {b} | a, b |\n" for e, b in rows)
    return "| Enum | Backing | Allowed values |\n|---|---|---|\n" + body


def _run(root: Path, capsys) -> tuple[int, str]:
    rc = c.main([str(root)])
    return rc, capsys.readouterr().out


def test_off_grammar_cells_are_reported(tmp_path: Path, capsys) -> None:
    _contract(
        tmp_path,
        _table(
            ("`good`", "native"),
            ("`a`", "app-enforced"),
            ("`b`", "chk"),
            ("`c`", "<placeholder>"),
            ("`d`", "native ()"),
            ("`e`", "`native"),
        ),
    )
    rc, out = _run(tmp_path, capsys)
    assert rc == 0
    assert "5 of 6" in out, out
    for enum, cell in (("a", "app-enforced"), ("b", "chk"), ("c", "<placeholder>")):
        assert f"`{enum}`: '{cell}'" in out, out
    assert "`good`" not in out
    assert "chk:<x>" in out, "the fix text names the type-prefix confusion"


def test_grammar_shapes_and_escaped_pipes_pass(tmp_path: Path, capsys) -> None:
    _contract(
        tmp_path,
        _table(
            ("`a`", "native"),
            ("`b`", "**CHECK**"),
            ("`c`", "file (config/a.yaml / Zod)"),
            ("`d`", "app (no DB CHECK) / doc"),
            ("`e`", "CHECK *(SHIPPED mig 086/087)*"),
            ("`Tier` (`X`\\|`Y`), `Ref`", "native"),
        ),
    )
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and out == "", out


def test_registry_heading_variants_and_column_by_name(tmp_path: Path, capsys) -> None:
    moved = (
        "| Enum | Allowed values | Backing |\n|---|---|---|\n"
        "| `a` | x, y | invented |\n| `b` | x | CHECK |\n"
    )
    for heading in ("## Enum Registry", "### Enum registry", "## 5. Enum registry"):
        _contract(tmp_path, moved, heading)
        rc, out = _run(tmp_path, capsys)
        assert rc == 0 and "1 of 2" in out and "'invented'" in out, (heading, out)


def test_a_contract_legend_never_widens_the_set(tmp_path: Path, capsys) -> None:
    legend = (
        "> **Backing legend — a CLOSED list:**\n"
        "> `native` (a PG enum) · `CHECK` (a constraint) · `app` (code) · `doc` (docs) · "
        "`file` (a file) · `unconstrained` (free) · `app-enforced` (invented here)\n\n"
    )
    _contract(tmp_path, legend + _table(("`a`", "app-enforced")))
    rc, out = _run(tmp_path, capsys)
    assert rc == 0
    assert "'app-enforced'" in out, "a contract legend must not widen the accepted set"
    assert "legend" in out and "app-enforced" in out.split("legend", 1)[1], out


def test_absent_silent_and_unrecognised_table_warns(tmp_path: Path, capsys) -> None:
    assert _run(tmp_path, capsys) == (0, "")  # no contract
    _contract(tmp_path, "no table here\n", "## Other section")
    assert _run(tmp_path, capsys) == (0, "")  # no registry section
    _contract(tmp_path, "prose only, no table\n")
    assert _run(tmp_path, capsys) == (0, "")  # a section without a table
    _contract(tmp_path, "| Name | Kind |\n|---|---|\n| `a` | native |\n")
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "not recognised" in out, out


def test_exit_zero_on_every_path(tmp_path: Path, capsys) -> None:
    (tmp_path / "docs" / "data-contract.md").mkdir(parents=True)  # a directory, not a file
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "WARN check_data_contract_legend:" in out, out


def test_every_table_in_the_section_is_read_by_its_own_header(tmp_path: Path, capsys) -> None:
    """A registry split into `###` sub-tables (tojlo-mail) has one header row per table — the
    second header was read as a data row whose Backing cell was the word `Backing`."""
    second = "| Enum | Allowed values | Backing |\n|---|---|---|\n| `b` | x | invented |\n"
    _contract(tmp_path, "### Ours\n\n" + _table(("`a`", "native")) + "\n### Inherited\n\n" + second)
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "1 of 2" in out and "'invented'" in out, out
    assert "'Backing'" not in out, out


def test_a_gfm_table_is_found_by_its_delimiter_row_not_a_leading_pipe(
    tmp_path: Path, capsys
) -> None:
    """GFM tables need no outer pipes; detection is the header + delimiter row pair (review A-1)."""
    bare = "Enum | Backing | Allowed values\n---|---|---\n`a` | invented | x\n`b` | native | y\n"
    _contract(tmp_path, bare)
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "1 of 2" in out and "'invented'" in out, out


def test_a_fenced_table_is_an_example_not_a_row(tmp_path: Path, capsys) -> None:
    """A table inside a code fence in the section is an illustration, never registry rows (A-2)."""
    fenced = "```\n| Enum | Backing |\n|---|---|\n| fake | invented |\n```\n\n" + _table(
        ("`a`", "native")
    )
    _contract(tmp_path, fenced)
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and out == "", out


def test_an_escaped_backslash_before_a_pipe_still_splits(tmp_path: Path, capsys) -> None:
    """`\\\\|` is an escaped backslash then a real delimiter (GFM/cmark-gfm cell scanning) (A-3)."""
    row = "| Enum | Backing | Allowed values |\n|---|---|---|\n| a\\\\| invented | x |\n"
    _contract(tmp_path, row)
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "'invented'" in out, out


def test_a_table_without_backing_never_hides_the_registry_table(tmp_path: Path, capsys) -> None:
    """A second table in the section (or prose that parses as one) is skipped, never a reason to stop
    reading: the early return hid the real table's finding behind it (review pass 2, A-N1)."""
    prose = "Values are either Backing | legacy depending on the writer.\n-- | --\n\n"
    _contract(tmp_path, prose + _table(("`bad`", "app-enforced")))
    rc, out = _run(tmp_path, capsys)
    assert rc == 0 and "'app-enforced'" in out and "not recognised" not in out, out
