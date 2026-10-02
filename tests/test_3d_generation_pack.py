"""Pins `ai/25-3d-generation.md` to its providers, its licences, its gate and its cross-references.

The pack is glob-activated on every 3D-asset path. Seven things it states can go false with no other gate red:

1. `Last content verification:` — `scripts/check_ai_pack_freshness.py` reads it; the pack once carried "Last reviewed:"
   and read as unstamped.
2. The routing table names no dead API (CSM, Luma Genie), no weights a licence restricts (Hunyuan3D, Stability's
   SF3D or SPAR3D) and no open model as a primary unless hosted (§ 0 and § 5 forbid self-hosting first); hosted routes are said to expose
   generate only. The pack once made Hunyuan3D the bulk fallback and TRELLIS self-host the primary.
3. The licence trap names TRELLIS's non-commercial nvdiffrast dependency, Hunyuan3D's territory exclusion and Stability's
   revenue cap; the exclusions say CSM and Luma Genie are gone.
4. The gate fails closed, trimesh (never a slicer) decides watertightness, its semantic checks go to Claude on renders
   the way `20-vision.md` says (run_agentic with Read, a control question), and the re-roll cap reads the same in the
   header and in § 4.
5. The CAD boundary routes simple parts to Claude-written CAD code through `claude -p` via a vendored `llm-dispatch`
   and complex ones to Zoo.
6. Its paths: the hub registry by its absolute path (a relative `data/projects.yaml` resolves to nothing in a project),
   the vendor-access catalog, the research brief, `core/76-gpu-workers.md`, `20-vision.md`, ai/00's project.yaml keys.
7. No retired route (Traycer, the Kilo gateway) and no version number in any shape — the version detector is the one
   `tests/test_vision_pack.py` defines, loaded here so the two packs share one definition.

The cheapest way past (2) is to rename a provider in the table; the review reads the licence. The cheapest way past (7)
is a version in words; the detector catches the shapes agents copy.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "25-3d-generation.md"
INDEX = RULES / "ai" / "00-ai-model-selection.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"
NOT_IN_ROUTING = ("CSM", "Luma", "Genie", "Hunyuan", "SF3D", "SPAR3D")
VENDOR_APIS = ("**Meshy**", "**Tripo**", "**Rodin**")  # the commercial APIs § 5 defaults to


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _section(text: str, number: str) -> str:
    start = text.index(f"\n## {number}. ")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_freshness_check_reads_the_stamp() -> None:
    mod = _load("freshchk_3d", FRESH)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_routing_names_no_dead_or_restricted_provider() -> None:
    table = [
        ln
        for ln in _section(_pack(), "1").splitlines()
        if ln.startswith("| ") and "Asset type" not in ln and not ln.startswith("| :--")
    ]
    assert len(table) >= 6, f"the routing table lost rows: {len(table)}"
    for row in table:
        for name in NOT_IN_ROUTING:
            assert name not in row, f"{name} is dead or licence-restricted and is routed to: {row}"
        primary = row.split("|")[2]
        # § 0 and § 5 forbid self-hosting as a starting move: a primary is a commercial vendor API or says it is
        # hosted — anything else (an open model however its self-host route is worded) fails closed
        if not any(v in primary for v in VENDOR_APIS):
            assert "hosted" in primary, (
                f"a primary is neither a vendor API nor hosted, against § 0 and § 5: {row}"
            )
    reach = _flat(_section(_pack(), "1"))
    assert "only the generate call" in reach, (
        "the reachability note no longer says hosted routes expose generate only"
    )


def test_licence_trap_and_exclusions_hold() -> None:
    routing = _flat(_section(_pack(), "1"))
    trap = routing.split("**Licence trap", 1)[1] if "**Licence trap" in routing else ""
    for needle in (
        "nvdiffrast",
        "non-commercial",
        "Hunyuan3D",
        "EU, UK or South Korea",
        "SF3D",
        "USD 1M",
    ):
        assert needle in trap, f"the licence trap no longer names {needle!r}"
    # each exclusion is one bullet; read the whole bullet, so a reworded or re-punctuated sentence still counts
    bullets = [_flat(b) for b in _section(_pack(), "2").split("\n- ")[1:]]
    heads = [(b.lstrip("*_ "), b) for b in bullets]
    csm = next((b for h, b in heads if h.startswith("CSM")), "")
    luma = next((b for h, b in heads if h.startswith("Luma Genie")), "")
    assert "shut down" in csm, "the exclusions no longer say CSM's API shut down"
    assert "sunset" in luma, "the exclusions no longer say Luma Genie was sunset"


def test_gate_fails_closed_and_claude_reads_the_renders() -> None:
    gate = _flat(_section(_pack(), "3"))
    # emphasis is not meaning: `Read`, *Read*, _Read_ and Read are one word; an underscore inside a word stays
    plain = re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", gate)
    assert "never a pass-by-default" in gate, (
        "the gate no longer fails closed on an unvalidatable generation"
    )
    for needle in ("run_agentic", "Read tool", "control question"):
        assert needle in plain, (
            f"the render check no longer says {needle!r}, as 20-vision's route requires"
        )
    assert "is_volume" in gate and "the slicer never decides" in gate, (
        "trimesh is no longer the watertight pass/fail over the slicers"
    )
    assert "`claude -p`" in gate and "`20-vision.md`" in gate, (
        "the semantic checks no longer go to Claude on renders, as 20-vision's image-understanding default says"
    )
    assert (
        "image understanding" in (RULES / "ai" / "20-vision.md").read_text(encoding="utf-8").lower()
    )


def test_reroll_cap_is_one_number() -> None:
    header = _pack().split("# 3D Generation Pipeline Rules", 1)[0]
    in_header = re.findall(r"cap re-rolls at (\d+)", header)
    in_body = re.findall(r"Re-roll cap: (\d+) attempts", _section(_pack(), "4"))
    # each side must state its number once; a side that drops it is a missing cap, not an agreement
    assert len(in_header) == 1 and len(in_body) == 1, (
        f"a re-roll cap is missing: header {in_header}, § 4 {in_body}"
    )
    assert in_header == in_body, f"the re-roll cap disagrees: {in_header} vs {in_body}"


def test_cad_boundary_routes_to_claude_or_zoo() -> None:
    boundary = _flat(_section(_pack(), "0"))
    assert "`llm-dispatch`" in boundary, (
        "the CAD route no longer goes through a vendored llm-dispatch, as ai/00 requires"
    )
    assert "`claude -p`" in boundary and "Zoo" in boundary, (
        "the CAD boundary lost its Claude or Zoo route"
    )
    assert "engineer" in boundary, (
        "the CAD boundary no longer keeps tolerance-critical parts with an engineer"
    )


def test_paths_resolve() -> None:
    pack = _pack()
    assert "`/opt/fabrik/data/projects.yaml`" in pack, (
        "the hub registry is no longer named by its absolute path"
    )
    assert "`data/projects.yaml`" not in pack, (
        "a relative data/projects.yaml resolves to nothing in a project repo"
    )
    for rel in (
        "docs/reference/kilo/AI_VENDOR_ACCESS.md",
        "docs/reference/research/Zero-Edit 3D API Evaluation.md",
    ):
        assert rel in pack and (ROOT / rel).is_file(), f"{rel} is cited but missing"
    for sibling in ("20-vision.md", "core/76-gpu-workers.md"):
        assert sibling in pack
    assert (RULES / "ai" / "20-vision.md").is_file() and (
        RULES / "core" / "76-gpu-workers.md"
    ).is_file()
    header = _flat(pack.split("# 3D Generation Pipeline Rules", 1)[0])
    assert "project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`)" in header
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in INDEX.read_text(encoding="utf-8"), (
            f"ai/00 no longer names {key}: re-align this pack"
        )


def test_no_retired_routes_or_versions() -> None:
    body = _pack().split("\n---\n", 1)[1]
    # retired names are refused in the frontmatter too: its description is what an agent browsing packs reads
    lowered = _pack().replace("docs/reference/kilo/", "docs/reference/").lower()
    for gone in ("traycer", "kilo"):
        # a whole word: "Kilo/OpenRouter" is the retired gateway, "kilobytes" is not
        assert not re.search(rf"\b{gone}\b", lowered), f"{gone} is retired and still named"
    version_re = _load("vision_pack_test", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    stripped = re.sub(r"Apache-?2\.0|A?GPL-\d\.\d|CC-BY(?:-[A-Z]+)* \d\.\d", "", body)
    found = version_re.findall(stripped)
    assert not found, f"version literals in the pack: {found}"
