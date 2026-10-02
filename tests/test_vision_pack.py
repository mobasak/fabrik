"""Pins `ai/20-vision.md` to its consumers, its licences and its cross-references.

The pack is glob-activated on every image/vision/OCR path. Seven things it states can go false with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES): `update_gateway_counts.py` and
   `category_export_markdown.py` rewrite the text between their markers, so both marker pairs must survive an edit.
2. `Last content verification:` — `scripts/check_ai_pack_freshness.py` reads it; the stamp must stay parseable.
3. Image understanding goes to Claude through `claude -p` first, as ai/00 says, through `llm-dispatch`'s Read-tool route;
   the pack once sent it to metered gateway models. The boundary where a dedicated model wins stays named.
4. The licence rule: no weights that are non-commercial or AGPL (Ultralytics YOLO, OpenPose, Surya, FLUX's Kontext and
   dev weights) may be named as a Fabrik default.
5. Its cites: ai/00 § Claude subscription first, ai/40-multimodal.md, 25-3d-generation.md, the reach map's § VIDEO,
   fabrik-lib's `llm-dispatch` and `ocr` READMEs.
6. No retired route (DALL·E, the Kilo gateway, FLUX-schnell as the bulk default, Detectron2, Traycer, Midjourney as an
   option), in any case, and no version number in any shape.
7. A vendor flagged as not set up in one lane is flagged in every lane, and the pointer to ai/40 says ai/00 overrides
   its pinned model.

The cheapest way past (4) is to rename a trap in the defaults; the review reads the licence. The cheapest way past (6) is a
version in words; the check catches the shapes agents copy (`v4.1`, `FLUX.2`, `4B`, `FLUX2`, `GPT Image 1`). Licence names (Apache-2.0, AGPL-3.0)
are stripped before the scan — the bound is that named set.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "20-vision.md"
INDEX = RULES / "ai" / "00-ai-model-selection.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"
REACH = ROOT / "docs" / "reference" / "ai-media-generation-provider-map.md"
LIB = Path(os.environ.get("FABRIK_LIB_DIR", "/opt/fabrik-lib"))
NOT_A_DEFAULT = ("YOLO", "OpenPose", "Surya", "Kontext", "dev weights")


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _defaults() -> str:
    """The Fabrik defaults bullets — up to the licence-trap paragraph, which names the traps on purpose."""
    return _section(_pack(), "Fabrik defaults").split("**Licence trap", 1)[0]


def _prose() -> str:
    """The pack below its frontmatter, with both machine-managed blocks cut out."""
    body = _pack().split("\n---\n", 1)[1]
    for marker in ("<!-- GATEWAY_COUNTS:START", "<!-- OPENROUTER_ROUTES:START"):
        head, _, rest = body.partition(marker)
        body = head + rest.split(":END -->", 1)[1]
    return body


@pytest.mark.parametrize("block", ["GATEWAY_COUNTS", "OPENROUTER_ROUTES"])
def test_machinery_blocks_survive(block: str) -> None:
    pack = _pack()
    start, end = pack.find(f"<!-- {block}:START"), pack.find(f"<!-- {block}:END -->")
    assert start != -1 and end > start, (
        f"the {block} markers are gone: its generator can no longer write the block"
    )


def test_freshness_check_reads_the_stamp() -> None:
    spec = importlib.util.spec_from_file_location("freshchk_vision", FRESH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_understanding_goes_to_claude_first() -> None:
    assert "image understanding" in INDEX.read_text(encoding="utf-8"), (
        "ai/00 no longer sends image understanding to claude -p: re-align this pack"
    )
    first = _defaults().split("\n- ", 2)[1]
    assert first.startswith("**Image understanding → Claude through `claude -p`**"), (
        "the first Fabrik default is no longer image understanding on Claude through claude -p"
    )
    assert "`llm-dispatch`" in first and 'tools=("Read",)' in first, (
        "the default no longer says how to hand Claude an image (llm-dispatch's Read tool)"
    )
    # run_agentic's max_turns is a required keyword with no default: a snippet without it raises TypeError
    assert "max_turns=" in first, "the run_agentic snippet lost max_turns, so it fails when copied"
    gateway = _section(_pack(), "Gateway coverage").split("<!-- GATEWAY_COUNTS:START", 1)[0]
    assert "not a metered gateway" in gateway, (
        "the gateway note no longer keeps image understanding off metered gateways"
    )


def test_dedicated_model_boundary_is_named() -> None:
    defaults = _defaults()
    for case in ("pixel-exact boxes", "counting", "real-time", "pose", "document OCR"):
        assert case in defaults, (
            f"the boundary where a dedicated model beats Claude no longer names {case!r}"
        )


@pytest.mark.parametrize("name", NOT_A_DEFAULT)
def test_no_restricted_licence_default(name: str) -> None:
    assert name not in _defaults(), (
        f"{name} carries a non-commercial or AGPL licence and is named as a default"
    )


def test_licence_trap_names_the_traps() -> None:
    sec = _section(_pack(), "Fabrik defaults")
    trap = sec.split("**Licence trap", 1)[1] if "**Licence trap" in sec else ""
    missing = [
        n for n in ("YOLO", "OpenPose", "Surya", "FLUX Non-Commercial", "AGPL") if n not in trap
    ]
    assert not missing, f"the licence trap no longer names {missing}"


def test_generation_stays_with_specialists() -> None:
    defaults = _defaults()
    assert "Claude does not generate images" in defaults
    assert "Recraft" in defaults and "FLUX" in defaults
    assert "through fal or Replicate" in defaults, (
        "Recraft's unfunded direct key is no longer routed around"
    )


def test_managed_and_sibling_caveats_hold() -> None:
    """A vendor flagged as not set up in one lane is flagged in every lane; ai/40's pinned model is overridden by ai/00."""
    ocr = _section(_pack(), "Subcategories").split("**Managed →", 1)[1].split("\n- ", 1)[0]
    caveat = re.sub(r"\s+", " ", ocr)
    assert "Neither is set up today" in caveat and "has no AWS row" in caveat, (
        "the managed OCR route lost its caveat that neither Google Cloud nor AWS is set up"
    )
    first = _defaults().split("\n- ", 2)[1]
    assert "ai/00 wins" in first, (
        "the pointer to ai/40 no longer says ai/00's ladder overrides ai/40's pinned model"
    )


def test_cites_resolve() -> None:
    pack = _pack()
    heads = [
        ln.lstrip("#").strip()
        for ln in INDEX.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]
    assert "§ Claude\n  subscription first" in pack or "§ Claude subscription first" in pack
    assert any(h.startswith("Claude subscription first") for h in heads), (
        "ai/00 lost § Claude subscription first"
    )
    for sibling in ("ai/40-multimodal.md", "25-3d-generation.md"):
        assert sibling in pack
        assert (RULES / "ai" / Path(sibling).name).is_file(), f"{sibling} is cited but missing"
    assert "§ VIDEO" in pack and "## VIDEO" in REACH.read_text(encoding="utf-8"), (
        "the reach map lost § VIDEO"
    )


@pytest.mark.skipif(not (LIB / "README.md").is_file(), reason="needs /opt/fabrik-lib")
def test_fabrik_lib_routes_exist() -> None:
    dispatch = (LIB / "llm-dispatch" / "README.md").read_text(encoding="utf-8")
    assert "Read tool" in dispatch and "add_dirs" in dispatch, (
        "llm-dispatch no longer documents image reading"
    )
    assert "vision_fn" in (LIB / "ocr" / "README.md").read_text(encoding="utf-8"), (
        "ocr/ lost its injectable vision_fn"
    )


def test_no_retired_routes() -> None:
    body = _prose()
    # the vendor-access catalog lives under docs/reference/kilo/ — that one directory names a file, not a route;
    # every other "kilo" (a route, a slash-joined pair, a module path) stays visible
    lowered = body.replace("docs/reference/kilo/", "docs/reference/").lower()
    # case-folded: "dall-e" and "Schnell" are the same retired names; Kilo is retired as a gateway and this pack names none
    for gone in ("dall", "detectron", "traycer", "schnell", "kilo"):
        assert gone not in lowered, f"{gone} is retired or unmaintained and still named"
    for sentence in re.split(r"(?<=[.;])\s+", body):
        if "midjourney" in sentence.lower():
            assert "no public API" in sentence, f"Midjourney is named as callable: {sentence!r}"


def test_no_version_literals() -> None:
    # a licence name carries a number but is not a version of anything the pack recommends
    body = re.sub(r"Apache-?2\.0|A?GPL-\d\.\d|CC-BY(?:-[A-Z]+)* \d\.\d", "", _prose())
    found = re.findall(
        r"\b[vV]\d+(?:\.\d+)?\b|\b\d+\.\d+\.\d+\b|[≥>]=?\s?\d+(?:\.\d+)?|@\d+\.\d+"
        r"|\b[A-Za-z][\w./-]*[A-Za-z] \d+\.\d+\b|\b[A-Za-z]+\.\d+\b|\b\d+B\b"
        # a digit glued to a product name (FLUX2, YOLO26) or a bare generation after any capitalised name (GPT Image 1, Textract 2)
        r"|\b[A-Z][A-Za-z]*[A-Z]\d+\b|\b[A-Z][A-Za-z]+ \d+\b",
        body,
    )
    assert not found, f"version literals in the pack: {found}"


def test_choice_is_recorded_where_ai00_says() -> None:
    """ai/00's selection workflow records the choice in project.yaml; this pack must not send agents elsewhere."""
    instruction = "project.yaml (`ai_category`,\n     `ai_subcategory`, `ai_tools`)"
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in INDEX.read_text(encoding="utf-8"), (
            f"ai/00 no longer names {key}: re-align this pack"
        )
    header = re.sub(r"\s+", " ", _pack().split("# 2. Vision AI", 1)[0])
    assert re.sub(r"\s+", " ", instruction) in header, (
        "the header no longer tells agents to record the choice in project.yaml"
    )
    assert "DECISIONS.md" not in header, (
        "the header sends the vendor choice somewhere other than project.yaml"
    )
