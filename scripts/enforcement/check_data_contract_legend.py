#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_data_contract_legend.py | none
"""Data-contract Backing legend — every Enum-registry `Backing` cell names a legend token.

The data-contract template (``templates/scaffold/docs/data-contract-template.md``) states the
`Backing` column's legend as a CLOSED list — ``native · CHECK · app · doc · file ·
unconstrained`` — and says it grows "here in the template, never in one contract". Nothing
checked a frozen contract against it: on 2026-10-13, 107 of 288 registry cells in 9 projects
used words the legend never named (fleet 01M4TGT7N4, kaizen 01M4F92G6V).

WHAT IT CHECKS, in ``docs/data-contract.md`` under the root (argv[1], else the cwd):
- the registry section — a heading matching ``Enum registry`` at level 2 or 3, any case, an
  optional ``N.`` prefix — up to the next heading of the same or a higher level;
- every GFM table in it (a header row then a delimiter row, outer pipes optional; a table or a
  heading inside fenced code is an illustration and is skipped), each read by its own header —
  the ``Backing`` column found by name; cells split on unescaped pipes, so an Enum cell holding
  ``\\|`` keeps its columns;
- each cell, WHOLE, against the grammar: ``token``, ``token (note)``, parts joined by ``" / "``;
  a token may wear a balanced markdown wrapper (backticks, ``**``, ``*``); a note is a non-blank
  ``(...)`` with no parenthesis inside, optionally wrapped in a balanced ``*...*``.

It ALWAYS checks against the template's six tokens. A contract that carries its own
``> **Backing legend`` paragraph naming a different list is reported, never honoured.

FAIL DIRECTION — WARN, never ERROR: the 107 known cells would red 9 repos on the first sync,
and the FAIL flip waits for their re-freeze. Exit is 0 on EVERY path, an unexpected exception
included: ``final_gate.run_optional_check`` fails a ``warn_only`` row that exits non-zero, so a
crash here would red every synced repo's gate. Silent on no contract, no registry section, or a
section without a table. A table without a ``Backing`` header is skipped, so another table in the
section never hides the registry's; a section whose tables ALL lack one is reported.

COBRA (D-253): the cheapest way to silence a finding is to widen the contract's own legend with
the invented word — the check never reads a contract legend as the accepted set, and a differing
one is its own finding. The next cheapest is ``unconstrained (<what it is>)`` for every odd set,
which the template names as the honest word until the legend grows.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DATA_CONTRACT_FILE = "docs/data-contract.md"
LEGEND_TOKENS: tuple[str, ...] = ("native", "CHECK", "app", "doc", "file", "unconstrained")
_SHOWN = 20

_REGISTRY_HEADING = re.compile(r"^(#{2,3})\s+(?:\d+\.\s*)?enum registry\b", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^(#{1,6})\s")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_DELIM_CELL = re.compile(r"^:?-+:?$")
_LEGEND_ITEM = re.compile(r"^`([A-Za-z_]+)` \(")


def legend_tokens(text: str) -> list[str] | None:
    """The tokens a ``> **Backing legend`` quote paragraph defines, or None when the text has none.

    STRUCTURAL: the quote lines right after the bold header, each `` · ``-separated item shaped
    ``\\`token\\` (definition)``. Raises ValueError naming a malformed item, never reads a wrong span."""
    lines = text.splitlines()
    start = next((k for k, ln in enumerate(lines) if ln.startswith("> **Backing legend")), None)
    if start is None:
        return None
    block: list[str] = []
    for ln in lines[start + 1 :]:  # an item may wrap onto the next quote line
        if ln.strip() == ">" or not ln.startswith("> "):
            break
        block.append(ln[2:])
    if not block:
        raise ValueError("no legend definition lines after the bold Backing legend header")
    tokens: list[str] = []
    for item in " ".join(block).split(" · "):
        m = _LEGEND_ITEM.match(item.strip())
        if not m:
            raise ValueError(f"legend item is not `token` (definition): {item.strip()[:60]!r}")
        tokens.append(m.group(1))
    return tokens


def backing_cell_ok(cell: str, tokens: tuple[str, ...] | list[str] = LEGEND_TOKENS) -> bool:
    """The legend's whole-cell grammar: ``token``, ``token (note)``, ``a / b`` (``re.fullmatch``)."""
    alt = "|".join(re.escape(x) for x in tokens)
    tok = rf"(?:`(?:{alt})`|\*\*(?:{alt})\*\*|\*(?:{alt})\*|(?:{alt}))"
    body = r"[^()]*[^()\s][^()]*"  # at least one non-blank character, no parenthesis
    note = rf"(?:\*\({body}\)\*|\({body}\))"  # a balanced `*(...)*` or a bare `(...)`
    part = rf"{tok}(?:\s{note})?"
    return re.fullmatch(rf"{part}(?:\s/\s{part})*", cell) is not None


def _cells(line: str) -> list[str]:
    """A GFM table row's cells. A backslash escapes the next character, so ``\\|`` is an escaped
    pipe (restored to ``|``) and ``\\\\|`` an escaped backslash followed by a real delimiter
    (cmark-gfm's cell scanner); the outer pipes are optional."""
    s = line.strip()
    cells: list[str] = []
    cur: list[str] = []
    i = 0
    last_delim = False
    while i < len(s):
        ch = s[i]
        last_delim = False
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            cur.append("|" if nxt == "|" else ch + nxt)
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur))
            cur = []
            last_delim = True
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur))
    if s.startswith("|"):
        cells = cells[1:]
    if last_delim and cells:
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_row(line: str | None) -> bool:
    return (
        line is not None
        and bool(line.strip())
        and (line.strip().startswith("|") or len(_cells(line)) > 1)
    )


def _is_delimiter(line: str | None) -> bool:
    if line is None or "-" not in line or "|" not in line:
        return False
    cells = _cells(line)
    return bool(cells) and all(_DELIM_CELL.match(c) for c in cells)


def _unfenced(lines: list[str]) -> list[str | None]:
    """The lines with every fenced-code line (fences included) replaced by None — a heading or a
    table inside a fence is an illustration, never structure."""
    out: list[str | None] = []
    fence = ""
    for ln in lines:
        m = _FENCE.match(ln)
        if fence:
            out.append(None)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = ""
            continue
        if m:
            fence = m.group(1)
            out.append(None)
            continue
        out.append(ln)
    return out


def registry_rows(text: str) -> tuple[bool, list[tuple[str, str]] | None]:
    """``(has_section, rows)``: rows are ``(enum, backing)`` per data row of the registry tables.

    A table is a GFM table — a header row then a delimiter row (outer pipes optional); a registry
    split into ``###`` sub-tables (tojlo-mail) carries one header per table, each read on its own.
    A table whose header names no ``Backing`` column is skipped; ``rows`` is None only when the
    section holds tables and NONE of them has one, and ``[]`` when it holds no table at all."""
    level = 0
    body: list[str | None] = []
    for ln in _unfenced(text.splitlines()):
        if level:
            h = _ANY_HEADING.match(ln) if ln is not None else None
            if h and len(h.group(1)) <= level:
                break
            body.append(ln)
            continue
        m = _REGISTRY_HEADING.match(ln) if ln is not None else None
        if m:
            level = len(m.group(1))
    if not level:
        return False, []
    blocks: list[list[str]] = []
    i = 0
    while i < len(body) - 1:
        head, delim = body[i], body[i + 1]
        if head is not None and _is_row(head) and _is_delimiter(delim):
            block = [head]
            j = i + 2
            while j < len(body) and _is_row(body[j]):
                block.append(body[j])  # type: ignore[arg-type]  # _is_row excludes None
                j += 1
            blocks.append(block)
            i = j
        else:
            i += 1
    if not blocks:
        return True, []
    rows: list[tuple[str, str]] = []
    recognised = False
    for block in blocks:
        names = [c.strip("`*").lower() for c in _cells(block[0])]
        if "backing" not in names:
            continue  # another table (or prose that parses as one) never stops the read
        recognised = True
        col = names.index("backing")
        for ln in block[1:]:
            cells = _cells(ln)
            rows.append((cells[0] if cells else "", cells[col] if col < len(cells) else ""))
    return True, (rows if recognised else None)


def check(root: Path) -> list[str]:
    """The WARN lines for one repo root — empty when the contract is clean or absent."""
    path = root / DATA_CONTRACT_FILE
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    try:
        own = legend_tokens(text)
    except ValueError as exc:
        out.append(f"{DATA_CONTRACT_FILE}: Backing legend paragraph unreadable ({exc})")
    else:
        if own is not None and own != list(LEGEND_TOKENS):
            out.append(
                f"{DATA_CONTRACT_FILE}: its own Backing legend names {own}, not the template's "
                f"{list(LEGEND_TOKENS)} — the legend grows in the template, never in one contract; "
                "cells are checked against the template's list"
            )
    has_section, rows = registry_rows(text)
    if not has_section:
        return out
    if rows is None:
        out.append(
            f"{DATA_CONTRACT_FILE}: Enum registry table not recognised — no `Backing` column "
            "in its header, so its cells were not checked"
        )
        return out
    bad = [(enum, cell) for enum, cell in rows if not backing_cell_ok(cell)]
    if bad:
        out.append(
            f"{DATA_CONTRACT_FILE}: {len(bad)} of {len(rows)} Enum registry `Backing` cell(s) "
            "are not legend tokens:"
        )
        out.extend(f"  {enum}: {cell!r}" for enum, cell in bad[:_SHOWN])
        if len(bad) > _SHOWN:
            out.append(f"  … and {len(bad) - _SHOWN} more")
        out.append(
            "  fix: one of "
            + " · ".join(f"`{t}`" for t in LEGEND_TOKENS)
            + " — whole cell `token`, `token (note)` or `a / b`; `chk:<x>` is a TYPE, its "
            "Backing is `CHECK`; a set the list cannot name is `unconstrained (<what it is>)`; "
            "a retired enum leaves the registry. Re-freeze with /fabrik-data-contract."
        )
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        root = Path(args[0]) if args else Path.cwd()
        for line in check(root):
            print(line if line.startswith("  ") else f"WARN: {line}")
    except Exception as exc:  # noqa: BLE001 — warn_only: a crash must never red the gate
        print(f"WARN check_data_contract_legend: {type(exc).__name__}: {exc}")
    return 0  # warn_only contract: findings are the product, never a red exit


if __name__ == "__main__":
    sys.exit(main())
