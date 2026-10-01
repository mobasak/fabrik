"""Pins `ai/10-speech-audio.md` to its consumers, its licences and its cross-references.

The pack is glob-activated on every speech/audio/voice path. Five things it states can go false with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES): `update_gateway_counts.py` and
   `category_export_markdown.py` rewrite the text between their markers, so both marker pairs must survive an edit.
2. `Last content verification:` — `scripts/check_ai_pack_freshness.py` reads it; the pack must stay parseable and fresh.
3. The licence rule: no model whose weights are non-commercial (Coqui XTTS, F5-TTS, MusicGen) may be named as a Fabrik default;
   the pack once made XTTS the self-hosted TTS fallback and called it Apache 2.0.
4. Its cites: `ai/00-ai-model-selection.md` § Selection MDs, and fabrik-lib's `speech-detect/` module.
5. No retired route (the Kilo gateway, Play.ht) and no version number in any shape.

The cheapest way past (3) is to rename a non-commercial model in the defaults; the review reads the licence. The cheapest way
past (5) is a version in words; the check catches the shapes agents copy. Licence names (Apache 2.0, CC-BY-NC 4.0,
GPL-3.0) are stripped before the scan — the bound is that named set.
"""

from __future__ import annotations

import importlib.util
import os
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "ai" / "10-speech-audio.md"
INDEX = ROOT / ".windsurf" / "rules" / "ai" / "00-ai-model-selection.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"
LIB_README = Path(os.environ.get("FABRIK_LIB_DIR", "/opt/fabrik-lib")) / "README.md"
NON_COMMERCIAL = ("XTTS", "F5-TTS", "MusicGen")


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _defaults() -> str:
    """The Fabrik defaults bullets — up to the licence-trap paragraph, which names the traps on purpose."""
    sec = _section(_pack(), "Fabrik defaults")
    return sec.split("**Licence trap", 1)[0]


@pytest.mark.parametrize("block", ["GATEWAY_COUNTS", "OPENROUTER_ROUTES"])
def test_machinery_blocks_survive(block: str) -> None:
    pack = _pack()
    start, end = pack.find(f"<!-- {block}:START"), pack.find(f"<!-- {block}:END -->")
    assert start != -1 and end > start, (
        f"the {block} markers are gone: its generator can no longer write the block"
    )


def test_freshness_check_reads_the_stamp() -> None:
    spec = importlib.util.spec_from_file_location("freshchk_speech", FRESH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    status, age, _msg = mod.check_pack(PACK, date.today())
    assert status == "fresh", f"check_ai_pack_freshness.py reads the pack as {status!r}: {_msg}"


@pytest.mark.parametrize("model", NON_COMMERCIAL)
def test_no_non_commercial_default(model: str) -> None:
    assert model not in _defaults(), (
        f"{model} has non-commercial weights and is named as a Fabrik default"
    )


def test_licence_trap_names_the_traps() -> None:
    sec = _section(_pack(), "Fabrik defaults")
    trap = sec.split("**Licence trap", 1)[1] if "**Licence trap" in sec else ""
    missing = [m for m in NON_COMMERCIAL if m not in trap]
    assert not missing, f"the licence trap no longer names {missing}"


def test_self_hosted_fallback_is_permissive() -> None:
    defaults = _defaults()
    assert "Chatterbox" in defaults and "MIT" in defaults


def test_cites_resolve() -> None:
    pack = _pack()
    assert "`ai/00-ai-model-selection.md`" in pack and "§ Selection MDs" in pack
    heads = [
        ln.lstrip("#").strip()
        for ln in INDEX.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]
    assert any(h.startswith("Selection MDs") for h in heads), "ai/00 no longer has § Selection MDs"


@pytest.mark.skipif(not LIB_README.is_file(), reason="needs /opt/fabrik-lib")
def test_speech_detect_module_exists() -> None:
    assert "`speech-detect/`" in _pack()
    assert "speech-detect/" in LIB_README.read_text(encoding="utf-8"), (
        "fabrik-lib no longer lists speech-detect/"
    )


def test_no_retired_routes() -> None:
    body = _pack()
    for marker in ("<!-- GATEWAY_COUNTS:START", "<!-- OPENROUTER_ROUTES:START"):
        body = body.split(marker, 1)[0] + body.split(marker, 1)[1].split(":END -->", 1)[1]
    assert "Play.ht" not in body, "Play.ht's API was shut down"
    assert not re.search(r"Kilo\s*/|cheaper of Kilo", body), "the Kilo gateway is retired"


def test_no_version_literals() -> None:
    body = _pack().split("\n---\n", 1)[1]
    for marker in ("<!-- GATEWAY_COUNTS:START", "<!-- OPENROUTER_ROUTES:START"):
        head, _, rest = body.partition(marker)
        body = head + rest.split(":END -->", 1)[1]
    # a licence name carries a number but is not a version of anything the pack recommends
    body = re.sub(r"Apache 2\.0|CC-BY(?:-[A-Z]+)* \d\.\d|[AL]?GPL-\d\.\d", "", body)
    found = re.findall(
        r"\bv\d+(?:\.\d+)?\b|\b\d+\.\d+\.\d+\b|\bChrome v?\d{2,3}\b|[≥>]=?\s?\d+(?:\.\d+)?|@\d+\.\d+"
        r"|\b[A-Za-z][\w./-]*[A-Za-z] \d+\.\d+\b",
        body,
    )
    assert not found, f"version literals in the pack: {found}"
