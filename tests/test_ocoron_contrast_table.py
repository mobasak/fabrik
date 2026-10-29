"""Pins the ocoron pack's contrast table to its own colour tokens.

The pack once shipped 9 wrong ratios in 11 rows, and its two tables disagreed with each other.
This test recomputes every row of `ocoron-design-system.md` § Contrast table from the hex values
in its § Colour tokens table with the WCAG 2.2 relative-luminance formula, and fails when a stated
ratio drifts from the computed one or falls below the threshold the row states.

The cheap ways to satisfy it without the outcome, each closed here: delete a row
(`test_every_required_pair_has_a_row` holds the set to the pairs `design-system-template.md`
§ Contrast contract requires), weaken a row's own `Needs` (`test_needs_is_the_contract_threshold`
derives it from the contract instead of trusting it), or change a value only in the pack's CSS
block, which repeats every value (`test_css_block_matches_token_table`), point a retired alias or a
`--viz` slot at the wrong colour (`test_css_aliases_and_viz_point_where_the_pack_says`), or misquote
a forbidden pair's ratio (`test_forbidden_pair_ratios_are_computed`). The operator's brand fills and
their white-text override (W-79008127) close three more: re-colour a fill until white passes, or give
one a near-black foreground (`test_brand_values_are_the_operator_ruling` pins the ruled values), drop
or soften the override's wording on a sub-4.5 row (`test_brand_fill_override_ratios_are_computed`),
or misquote its lowest ratio (`test_brand_fill_forbidden_quote_is_computed`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_PACK = (
    Path(__file__).resolve().parents[1] / ".windsurf" / "rules" / "core" / "ocoron-design-system.md"
)
_STATES = ("accent", "success", "warning", "danger", "info", "ai")
_SURFACES = ("--surface-0", "--surface-1", "--surface-2")


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"section {heading!r} missing"
    return m.group(1)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(value: str) -> tuple[float, float, float]:
    h = value.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _over(rgba: str, bg: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b, a = (float(x) for x in re.findall(r"[\d.]+", rgba))
    # composite in 8-bit, as a browser paints it
    return tuple(round(a * f + (1 - a) * k * 255) / 255 for f, k in zip((r, g, b), bg, strict=True))  # type: ignore[return-value]


def _tokens() -> dict[str, dict[str, str]]:
    """slot -> {dark, light} raw values, from § Colour tokens."""
    out: dict[str, dict[str, str]] = {}
    for line in _section(_PACK.read_text(encoding="utf-8"), "Colour tokens").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[0].startswith("`--"):
            continue
        dark, light = (c.strip("`") for c in cells[1:3])
        slots = re.findall(r"`(--[a-z0-9-]+|-[a-z]+)`", cells[0])
        base = slots[0]
        for s in slots:
            name = base + s if s.startswith("-") and not s.startswith("--") else s
            out[name] = {"dark": dark, "light": light}
    return out


def _resolve(tok: dict[str, dict[str, str]], slot: str, mode: str) -> str:
    v = tok[slot][mode]
    m = re.fullmatch(r"var\((--[a-z0-9-]+)\)", v)
    return _resolve(tok, m.group(1), mode) if m else v


def _computed(tok: dict[str, dict[str, str]], fg: str, bg: str, mode: str) -> float:
    fg_slot = re.search(r"--[a-z0-9-]+", fg).group(0)  # type: ignore[union-attr]
    if fg_slot == "--focus-ring":
        fg_slot = "--color-accent"
    f = _rgb(_resolve(tok, fg_slot, mode))
    if bg.startswith("surface-0"):
        return min(_ratio(f, _rgb(_resolve(tok, s, mode))) for s in _SURFACES)
    if "tint over surface-1" in bg:
        state = re.fullmatch(r"--color-([a-z]+)-text", fg_slot).group(1)  # type: ignore[union-attr]
        tint = _over(
            _resolve(tok, f"--color-{state}-muted", mode), _rgb(_resolve(tok, "--surface-1", mode))
        )
        return _ratio(f, tint)
    bg_slot = re.search(r"--[a-z0-9-]+", bg).group(0)  # type: ignore[union-attr]
    return _ratio(f, _rgb(_resolve(tok, bg_slot, mode)))


def _rows() -> list[tuple[str, str, float, float, float]]:
    rows = []
    for line in _section(_PACK.read_text(encoding="utf-8"), "Contrast table").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[2].endswith(":1") and cells[0].startswith("`"):
            dark, light, need = (float(c.removesuffix(":1")) for c in cells[2:5])
            rows.append((cells[0], cells[1], dark, light, need))
    return rows


def test_table_parses() -> None:
    assert _rows()
    assert {"--surface-0", "--text-muted", "--color-danger-fg", "--border-control"} <= set(
        _tokens()
    )


@pytest.mark.parametrize("row", _rows(), ids=lambda r: f"{r[0]} on {r[1]}")
def test_stated_ratio_is_the_computed_one(row: tuple[str, str, float, float, float]) -> None:
    fg, bg, dark, light, need = row
    tok = _tokens()
    for mode, stated in (("dark", dark), ("light", light)):
        got = _computed(tok, fg, bg, mode)
        assert abs(got - stated) < 0.006, (
            f"{mode}: {fg} on {bg} states {stated}:1, computes {got:.2f}:1"
        )
        assert got >= need, f"{mode}: {fg} on {bg} computes {got:.2f}:1, below {need}:1"


def test_every_required_pair_has_a_row() -> None:
    have = {(re.sub(r"\s*\(.*", "", fg).strip("`"), bg) for fg, bg, *_ in _rows()}
    need = {(f"--{t}", "surface-0…2") for t in ("text-primary", "text-body", "text-muted")}
    for s in _STATES:
        need |= {
            (f"--color-{s}-text", "surface-0…2"),
            (f"--color-{s}-text", "its `-muted` tint over surface-1"),
            (f"--color-{s}-fg", f"`--color-{s}`"),
            (f"--color-{s}", "surface-0…2"),
        }
    need |= {
        ("--border-control", "surface-0…2"),
        ("--focus-ring", "surface-0…2"),
        ("--color-accent-fg", "`--color-accent-hover`"),
    }
    missing = {p for p in need if p not in have}
    assert not missing, f"contrast rows missing: {sorted(missing)}"


def _contract_need(fg: str, bg: str) -> float:
    """The threshold `design-system-template.md` § Contrast contract sets for a pair."""
    slot = re.search(r"--[a-z0-9-]+", fg).group(0)  # type: ignore[union-attr]
    is_text = slot.startswith("--text-") or slot.endswith(("-text", "-fg"))
    return 4.5 if is_text else 3.0


@pytest.mark.parametrize("row", _rows(), ids=lambda r: f"{r[0]} on {r[1]}")
def test_needs_is_the_contract_threshold(row: tuple[str, str, float, float, float]) -> None:
    fg, bg, _dark, _light, need = row
    assert need == _contract_need(fg, bg), f"{fg} on {bg} states Needs {need}:1"


def _css_blocks() -> dict[str, dict[str, str]]:
    text = _section(_PACK.read_text(encoding="utf-8"), "CSS custom properties")
    out = {}
    for mode, sel in (("dark", r":root"), ("light", r'\[data-theme="light"\]')):
        m = re.search(sel + r"\s*\{(.*?)\n\}", text, re.S)
        assert m, f"CSS block for {mode} missing"
        out[mode] = dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", m.group(1)))
    return out


def _norm(v: str) -> str:
    return re.sub(r"\s+", "", v).upper()


def test_css_block_matches_token_table() -> None:
    tok, css = _tokens(), _css_blocks()
    for slot, vals in tok.items():
        dark = css["dark"].get(slot)
        assert dark is not None, f"{slot} missing from the :root block"
        assert _norm(dark) == _norm(vals["dark"]), (
            f"{slot}: CSS dark {dark} vs table {vals['dark']}"
        )
        light = css["light"].get(slot, dark)
        assert _norm(light) == _norm(vals["light"]), (
            f"{slot}: CSS light {light} vs table {vals['light']}"
        )


def test_css_aliases_and_viz_point_where_the_pack_says() -> None:
    dark = _css_blocks()["dark"]
    expected = {
        "--color-secondary": "var(--color-warning)",
        "--color-purple": "var(--color-ai)",
        "--focus-ring": "var(--color-accent)",
    }
    viz = re.search(r"`--viz-1` … `--viz-6` \| ([a-z, ]+) —", _PACK.read_text(encoding="utf-8"))
    assert viz, "the --viz mapping sentence is missing"
    for n, name in enumerate((w.strip() for w in viz.group(1).split(",")), start=1):
        expected[f"--viz-{n}"] = f"var(--color-{name})"
    assert len(expected) == 9
    for slot, want in expected.items():
        assert _norm(dark.get(slot, "")) == _norm(want), (
            f"{slot} is {dark.get(slot)}, the pack says {want}"
        )


def test_forbidden_pair_ratios_are_computed() -> None:
    text = _section(_PACK.read_text(encoding="utf-8"), "Contrast table")
    para = text[text.index("**Forbidden pairs") :].split("\n\n")[0]
    tok = _tokens()

    def val(slot: str, mode: str = "dark") -> tuple[float, float, float]:
        return _rgb(_resolve(tok, slot, mode))

    cases = {
        r"`--text-muted` on `--surface-3` \(dark (\d+\.\d+):1": _ratio(
            val("--text-muted"), val("--surface-3")
        ),
        r"any surface \(dark (\d+\.\d+):1 on `--surface-1`": _ratio(
            val("--color-accent"), val("--surface-1")
        ),
        r"near-black text on `--color-accent` \((\d+\.\d+):1": _ratio(
            _rgb("#0A0A0A"), val("--color-accent")
        ),
        r"white\s+it is, (\d+\.\d+):1": _ratio(_rgb("#FFFFFF"), val("--color-accent")),
    }
    for pattern, got in cases.items():
        m = re.search(pattern, para)
        assert m, f"forbidden-pair quote {pattern!r} not found"
        assert abs(float(m.group(1)) - got) < 0.006, (
            f"{pattern!r} states {m.group(1)}:1, computes {got:.2f}:1"
        )


# ── The operator's four Ocoron brand fills (W-79008127, operator ruling 2026-10-24) ─────────────
# "blue 120AF1 / magenta A50FEA / green 08941F / orange EA880F", WHITE text on all four, "accepting
# 2.62:1 on orange and 3.99:1 on green as their call". Pinned here so the cheapest "fix" — re-colour a
# fill until white passes and restate its row, or give one fill a near-black fg — goes red.
_OPERATOR_BRAND = {
    "--color-brand-blue": "#120AF1",
    "--color-brand-magenta": "#A50FEA",
    "--color-brand-green": "#08941F",
    "--color-brand-orange": "#EA880F",
    "--color-brand-fg": "#FFFFFF",
}
_BRAND_FILLS = tuple(s for s in _OPERATOR_BRAND if s != "--color-brand-fg")
_BRAND_HEADING = "### Brand fills — the operator's white-text override"


def _brand_rows() -> list[tuple[str, str, float, str]]:
    """(fg, fill, stated ratio, ruling) from the override subsection's 4-column table. Four columns
    on purpose: `_rows()` floats every 5-cell row of § Contrast table against a threshold, which a
    sub-4.5 override row must never meet."""
    text = _section(_PACK.read_text(encoding="utf-8"), "Contrast table")
    assert _BRAND_HEADING in text, f"{_BRAND_HEADING!r} missing from § Contrast table"
    rows = []
    for line in text[text.index(_BRAND_HEADING) :].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].startswith("`--") and cells[2].endswith(":1"):
            rows.append((cells[0].strip("`"), cells[1].strip("`"), float(cells[2][:-2]), cells[3]))
    return rows


def test_brand_values_are_the_operator_ruling() -> None:
    tok, css = _tokens(), _css_blocks()
    for slot, want in _OPERATOR_BRAND.items():
        assert tok.get(slot) == {"dark": want, "light": want}, (
            f"{slot} is {tok.get(slot)}, the operator ruled {want} in both modes"
        )
        # the light block repeats every colour; test_css_block_matches_token_table falls back to
        # :root for a missing light entry, so the light block is graded here
        assert _norm(css["light"].get(slot, "")) == want, f"{slot} missing from the light block"
    fgs = {fg for fg, *_ in _brand_rows()}
    assert fgs == {"--color-brand-fg"}, f"an override row names another foreground: {fgs}"


def test_brand_fill_override_ratios_are_computed() -> None:
    tok = _tokens()
    rows = _brand_rows()
    assert sorted(fill for _, fill, *_ in rows) == sorted(_BRAND_FILLS), rows
    for fg, fill, stated, ruling in rows:
        for mode in ("dark", "light"):
            got = _ratio(_rgb(_resolve(tok, fg, mode)), _rgb(_resolve(tok, fill, mode)))
            assert abs(got - stated) < 0.006, (
                f"{mode}: {fg} on {fill} states {stated}:1, computes {got:.2f}:1"
            )
        # the wording follows the ratio: below 4.5 the row names the ruling and what WCAG still
        # grants (3:1 for large text), so a row cannot say less than the operator accepted
        # and never the phrase of another band, so a row cannot also claim what its ratio denies
        bands = {
            "pass": ["passes 4.5:1"],
            "large": ['operator override, do not "fix"', "meets WCAG AA only as large text"],
            "fail": ['operator override, do not "fix"', "fails WCAG AA at every text size"],
        }
        band = "pass" if stated >= 4.5 else "large" if stated >= 3.0 else "fail"
        for phrase in bands[band]:
            assert phrase in ruling, f"{fill} at {stated}:1 lacks {phrase!r}: {ruling!r}"
        for other in set(sum(bands.values(), [])) - set(bands[band]):
            assert other not in ruling, f"{fill} at {stated}:1 also says {other!r}: {ruling!r}"
    # the prose quotes the operator's two accepted ratios; they are the green and orange rows
    text = _section(_PACK.read_text(encoding="utf-8"), "Contrast table")
    m = re.search(r"accepting (\d+\.\d+):1 on orange and (\d+\.\d+):1 on green", text)
    assert m, "the operator's quoted ratios are missing from the override paragraph"
    by_fill = {fill: stated for _, fill, stated, _ in rows}
    assert float(m.group(1)) == by_fill["--color-brand-orange"], m.group(0)
    assert float(m.group(2)) == by_fill["--color-brand-green"], m.group(0)


def test_brand_fill_forbidden_quote_is_computed() -> None:
    """The quote names the LOWEST brand-fill-on-surface ratio over surface-0…2 in both modes (the
    table's population; `--surface-3` is a hover surface, template § Contrast contract) and the pair
    that reaches it."""
    text = _section(_PACK.read_text(encoding="utf-8"), "Contrast table")
    para = text[text.index("**Forbidden pairs") :].split("\n\n")[0]
    tok = _tokens()
    m = re.search(
        r"chart series \(as low as (\d+\.\d+):1 across surface-0…2 — "
        r"`(--color-brand-[a-z]+)` on (dark|light) `(--surface-[0-2])`",
        para,
    )
    assert m, "the brand-fill forbidden quote is missing"
    low = min(
        (_ratio(_rgb(_resolve(tok, f, mode)), _rgb(_resolve(tok, s, mode))), f, mode, s)
        for f in _BRAND_FILLS
        for mode in ("dark", "light")
        for s in _SURFACES
    )
    assert abs(float(m.group(1)) - low[0]) < 0.006, f"states {m.group(1)}:1, the lowest is {low}"
    assert m.groups()[1:] == low[1:], f"names {m.groups()[1:]}, the lowest is {low[1:]}"
