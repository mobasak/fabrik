"""The design-critique step: two independent critiques before a design-approval gate.

Operator 2026-10-03: "after fabrik-spec or fabrik-spec-review and also inside fabrik-task
command's spec creation part, i want commands first get two independent design critiques in
parallel, one from Opus 5.5 and one from Fable 5.1 (latest fable and opus models)".

The step lives in ONE fragment and runs at the command that HOLDS the approval gate — once per
artifact version — so the rendered gate holders carry it exactly once, and `/fabrik-spec` (which
hands its spec to a gate holder) only points at them. Rendered into a temp dir, never the
installed corpus.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FRAGMENT = REPO / "commands" / "_fragments" / "design-critique.md"
# A sentence only the fragment carries — the marker the render must contain once per holder.
MARKER = "Two independent design critiques"
GATE_HOLDERS = (
    "fabrik-spec-review",
    "fabrik-plan-review",
    "fabrik-flows-review",
    "fabrik-ui-design-review",
    "fabrik-task",
)
# D-613: the commands whose design-approval gate the panel answers in the operator's place.
PANEL_HOLDERS = GATE_HOLDERS[:4]
PANEL_MARKER = "The panel answers the design-approval gate in the operator's place"


def _load(path: Path, name: str):
    """Import a repo script by path — `commands/` is not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    asm = _load(REPO / "commands" / "assemble_commands.py", "assemble_commands_design_critique")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        asm.render(tmp, tmp / "_skills", agents_dest=tmp / "_agents")
        return {
            name: (tmp / f"{name}.md").read_text(encoding="utf-8")
            for name in (*GATE_HOLDERS, "fabrik-spec")
        }


@pytest.mark.parametrize("command", GATE_HOLDERS)
def test_each_gate_holder_renders_the_step_exactly_once(rendered, command) -> None:
    """A gate holder carries the step once — zero is the gap, two would critique twice."""
    count = rendered[command].count(MARKER)
    assert count == 1, f"{command}.md carries the design-critique step {count} times, not once"


def test_plan_review_scopes_the_step_to_the_small_spec_gate(rendered) -> None:
    """A plan review without a `Size: small` spec has no gate — the step must say it is not owed there."""
    text = rendered["fabrik-plan-review"]
    lead = text[: text.index(MARKER)].rsplit("\n\n", 2)[-2]
    assert "Only a `Size: small` spec's gate owes the" in lead, (
        "the step follows no Size: small scoping sentence — every plan review would dispatch critiques"
    )


def test_fabrik_spec_points_at_the_gate_holders_and_never_runs_its_own(rendered) -> None:
    """`/fabrik-spec` hands its spec on; a second pair there would critique one spec twice."""
    text = rendered["fabrik-spec"]
    assert MARKER not in text, "fabrik-spec renders its own critique pair — the gate holder runs it"
    assert "design-critique" in text, "fabrik-spec never names the design-critique step"
    assert "/fabrik-spec-review" in text and "/fabrik-plan-review" in text


def test_fragment_names_both_models_the_fallback_and_no_version() -> None:
    """Both model tokens, the Fable-unavailable fallback, the counter — and no version literal."""
    text = FRAGMENT.read_text(encoding="utf-8")
    assert 'model: "opus"' in text and 'model: "fable"' in text, "a model token is missing"
    assert re.search(
        r"When Fable is unavailable[^.]*run a second\s+Opus\s+seat in its place", text
    ), "no Fable→Opus fallback sentence"
    assert "ONE message" in text, "the two critiques are not dispatched in parallel"
    assert "dispatch --seats 2" in text, "the two seats are not stamped"
    assert re.search(r"(?i)cobra", text), "no cheapest-way-past line (D-253)"
    assert not re.search(r"\b(Opus|Fable)\s+\d", text), "a model version literal in rule text"


@pytest.mark.parametrize("command", PANEL_HOLDERS)
def test_four_gate_commands_include_panel(rendered, command) -> None:
    """Behaviour 7 (D-613): each design-gate command renders the panel step once, AFTER the
    critique step it reads; `/fabrik-task` (no gate) carries none."""
    text = rendered[command]
    assert text.count(PANEL_MARKER) == 1, (
        f"{command}.md carries the panel step {text.count(PANEL_MARKER)} times"
    )
    assert text.index(MARKER) < text.index(PANEL_MARKER), f"{command}.md: panel before critique"


def test_fabrik_task_has_no_panel_step(rendered) -> None:
    assert PANEL_MARKER not in rendered["fabrik-task"]


@pytest.mark.parametrize("command", PANEL_HOLDERS)
def test_each_panel_holder_states_its_split_block(rendered, command) -> None:
    """B-S3: the panel step ends a split at "the command's DECISION block" — each of the four
    commands must state one, with the `Panel: … → split` line the Stop hook checks."""
    text = rendered[command]
    i = text.find("DECISION NEEDED (ground: gate)")
    assert i != -1, f"{command}.md states no DECISION block for the split path"
    window = text[i : i + 1200]
    assert re.search(r"^\s*- Panel: .*→ split\s*$", window, re.M), (
        f"{command}.md: no split Panel line"
    )
