"""W-6904b41e: the Behavior-Contract region parsers of check_phase_tests and check_test_proposal read each region once.

They used to slice the whole rest of the plan once per label or heading (`text[m.end():]`, then `.splitlines()`), which
made them quadratic: 8 000 bold labels took ~5 s, and 4x the input took 12-22x the time. The guard is deterministic:
the text is a str subclass that counts every character a slice copies out of it, so no clock is read. `_lines_from`
must also keep `str.splitlines`' line boundaries exactly, or a region's edges would move.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENF = ROOT / "scripts" / "enforcement"


def _load(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(f"_linear_{name}", ENF / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PHASE = _load("check_phase_tests")
PROPOSAL = _load("check_test_proposal")


class _Counting(str):
    """A str that adds the length of every slice taken from it to `copied`."""

    copied = 0

    def __getitem__(self, key):  # type: ignore[override]
        out = str.__getitem__(self, key)
        if isinstance(key, slice):
            _Counting.copied += len(out)
        return out


def _bold(n: int) -> str:
    return "".join(
        f"**Behavior Contract ({i}):**\n- **Given** a, **When** b, **Then** c\n\nprose {i}\n"
        for i in range(n)
    )


def _heads(n: int) -> str:
    return "".join(
        f"## Behavior Contract {i}\n- **Given** a, **When** b, **Then** c\n" for i in range(n)
    )


@pytest.fixture
def no_fence_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    """check_phase_tests strips fences first and would hand back a plain str; keep the counting one."""
    monkeypatch.setitem(
        sys.modules, "_fences", types.SimpleNamespace(strip_three_marker_fences=lambda t: t)
    )


@pytest.mark.parametrize(
    "parse, make",
    [
        pytest.param(lambda t: PROPOSAL._bold_contract_regions(t), _bold, id="test_proposal-bold"),
        pytest.param(lambda t: PHASE._contract_regions(t), _bold, id="phase_tests-bold"),
        pytest.param(lambda t: PHASE._contract_regions(t), _heads, id="phase_tests-heading"),
    ],
)
def test_each_region_is_copied_once_not_once_per_label(no_fence_strip: None, parse, make) -> None:
    text = _Counting(make(400))
    _Counting.copied = 0
    regions = parse(text)
    assert regions.count("**Given**") == 400
    # one pass over the text copies about len(text) characters; the quadratic form copied ~200x that here
    assert _Counting.copied <= 2 * len(text), (
        f"copied {_Counting.copied} chars from a {len(text)}-char text"
    )


@pytest.mark.parametrize("mod", [PHASE, PROPOSAL], ids=["check_phase_tests", "check_test_proposal"])
@pytest.mark.parametrize(
    "text",
    [
        "",
        "abc",
        "abc\n",
        "a\n\nb",
        "a\r\nb\rc\n",
        "**Behavior Contract:**\n- x\n\v- y\x85z w\x1cq\n",
        "label\n\n\n",
        "\n",
        "tail without newline",
    ],
)
def test_lines_from_matches_splitlines_from_every_offset(mod: types.ModuleType, text: str) -> None:
    for start in range(len(text) + 1):
        assert list(mod._lines_from(text, start)) == text[start:].splitlines(), (text, start)


def test_a_label_at_the_end_of_the_text_yields_an_empty_region() -> None:
    assert PROPOSAL._bold_contract_regions("**Behavior Contract:**") == ""


@pytest.mark.parametrize(
    "doc, givens",
    [
        # a label inside a heading region is already in that region: counted once, not twice
        ("## Behavior Contract\n**Behavior Contract (x):**\n- **Given** a\n", 1),
        # a label after the region ended (a later ## heading) is its own region
        (
            "## Behavior Contract\n- **Given** a\n## Other\n**Behavior Contract (y):**\n- **Given** b\n",
            2,
        ),
        # a label before any heading region, then a heading region
        ("**Behavior Contract (z):**\n- **Given** a\n\n## Behavior Contract\n- **Given** b\n", 2),
        # a label exactly at the start of the second of two heading regions' gap
        (
            "## Behavior Contract\n- **Given** a\n### Next\n**Behavior Contract:**\n- **Given** b\n"
            "## Behavior Contract\n**Behavior Contract:**\n- **Given** c\n",
            3,
        ),
    ],
)
def test_a_bold_label_is_skipped_only_inside_a_heading_region(
    no_fence_strip: None, doc: str, givens: int
) -> None:
    assert PHASE._contract_regions(doc).count("**Given**") == givens
