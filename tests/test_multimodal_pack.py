"""Pins `ai/40-multimodal.md` to the modalities each engine actually reads, and to its cross-references.

The pack is read by citation from ai/00 and ai/20 (no fleet directory matches its globs today). Seven things it states
can go false with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES) survive, and `Last content verification:` parses
   for `scripts/check_ai_pack_freshness.py`.
2. Images and documents go to Claude through `claude -p` on ai/20's ladder, with the subject's context passed; the pack
   once pinned an Opus model by version.
3. Claude reads no audio and no video, and the pack says so: spoken content is transcribed per ai/10, and video and
   non-speech audio go to Gemini through OpenRouter in the content shapes OpenRouter accepts.
4. PDFs are read text-first through fabrik-lib's `pdf-extract` and `ocr`, within the Read tool's page limits.
5. The open-weights route goes hosted first, as core/76's API-versus-self-host framework does, and the licence
   trap says checkpoint licences differ from the family's.
6. No retired route or model is offered (Kilo, Traycer, OpenAI's GPT-4 line, Kosmos-2), and no version number in any
   shape — the detector is the one `tests/test_vision_pack.py` defines, loaded here.
7. The cited packs and fabrik-lib modules exist, and the choice is recorded in project.yaml with ai/00's keys.

Guards read structure (one bullet at a time, emphasis stripped, whole words) so a restyled line keeps its meaning. The
cheapest way past (3) is to keep the words while routing audio to Claude in a sentence the bullet parser does not read;
the defaults and the Subcategories audio lane are pinned bullet by bullet, and the review reads the rest. The cheapest way past (6) is a version in words; the detector catches the shapes agents
copy.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "40-multimodal.md"
INDEX = RULES / "ai" / "00-ai-model-selection.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"
LIB = Path(os.environ.get("FABRIK_LIB_DIR", "/opt/fabrik-lib"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _plain(text: str) -> str:
    """Whitespace collapsed and emphasis stripped; an underscore inside a word stays."""
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _section(heading: str) -> str:
    text = _pack()
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _bullets(heading: str) -> list[str]:
    body = _section(heading).split("**Licence trap", 1)[0]
    return [_plain(b) for b in body.split("\n- ")[1:]]


def _bullet(heading: str, label: str) -> str:
    """The first bullet whose opening words contain the label (a restyled label still matches)."""
    return next((b for b in _bullets(heading) if label.lower() in b[:60].lower()), "")


def _prose() -> str:
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
    mod = _load("freshchk_multimodal", FRESH)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_images_and_documents_go_to_claude() -> None:
    images = _bullet("Fabrik defaults", "Images")
    # the default is what the bullet OPENS with, not a later mention
    assert re.match(r"Images and documents\s*:?\s*→\s*Claude through claude -p", images), (
        f"the image and document default changed: {images[:70]!r}"
    )
    for needle in ("ai/20-vision.md", "run_agentic", "haiku"):
        assert needle in images, f"the image default no longer names {needle!r}"
    assert "product name" in images, (
        "the image default lost its measured lesson: pass what the caller knows about the subject"
    )


def test_claude_reads_no_audio_or_video() -> None:
    intro = _plain(_section("Fabrik defaults").split("\n- ", 1)[0])
    assert re.search(r"Claude reads text, images and PDFs and nothing else", intro), (
        "the defaults no longer say which inputs Claude reads"
    )
    assert re.search(r"drops an audio part silently", intro), (
        "the defaults no longer warn that Claude drops audio without an error"
    )
    speech = _bullet("Fabrik defaults", "Speech")
    assert re.match(r"Speech\s*:?\s*→\s*transcribe", speech) and "ai/10-speech-audio.md" in speech, (
        "spoken content no longer goes through ai/10's transcription first"
    )
    video = _bullet("Fabrik defaults", "Video")
    assert re.match(r"Video\b[^→]{0,40}→\s*Gemini through OpenRouter", video), (
        f"video no longer goes to Gemini through OpenRouter: {video[:70]!r}"
    )
    for needle in ("Flash-Lite", "video_url", "input_audio", "base64", "YouTube"):
        assert needle in video, f"the video route no longer names {needle!r}"
    # OpenRouter's only video control is `processing`; a frame-rate or resolution knob the route lacks must not return
    assert re.search(r'processing on the video part', video) and "no frame-rate or resolution setting" in video, (
        "the video route no longer names the one control OpenRouter exposes"
    )
    assert "how it was said" in speech, "speech whose tone matters no longer goes to Gemini"
    # cost a clip before sending it, and the dated price change stays visible
    assert re.search(r"100 tokens a second", video) and "2027-01-01" in video, (
        "the video route lost its cost rule or the Flash price change date"
    )
    for bullet in _bullets("Fabrik defaults"):
        if re.match(r"[^→]{0,60}→\s*Claude", bullet):
            assert not re.search(r"\b(?:audio|video|speech)\b", bullet[:40], re.I) or bullet.startswith("Only the"), (
                f"a Claude default takes audio or video: {bullet[:70]!r}"
            )


def test_pdfs_are_read_text_first() -> None:
    pdfs = _bullet("Fabrik defaults", "PDFs")
    for needle in ("pdf-extract", "ocr", "make_claude_vision_fn", "20 pages", "100 pages or 20 MB", "encrypted"):
        assert needle in pdfs, f"the PDF route no longer names {needle!r}"
    # the Read tool's page-range reads need poppler on the host; ocr's Claude fallback is inert at its default threshold
    assert "pdftoppm" in pdfs and re.search(r"min_conf above 0", pdfs), (
        "the PDF route lost its host dependency or ocr's escalation threshold"
    )
    assert "uses_claude_cli" in pdfs, "the PDF route no longer says a deployed service declares the CLI"


def test_self_host_defers_to_core76_and_the_trap_holds() -> None:
    selfhost = _bullet("Fabrik defaults", "Open weights")
    assert "Qwen" in selfhost and "core/76-gpu-workers.md" in selfhost, (
        "the open-weights route no longer names Qwen's open models under core/76"
    )
    # core/76 starts with managed APIs: hosted first, a GPU pod only past its break-even
    assert re.search(r"hosted first", selfhost) and "break-even" in selfhost, (
        "the open-weights route no longer puts hosted before a GPU pod, as core/76 does"
    )
    assert "Apache-licensed" in selfhost, "the self-hosted route no longer states its weights' licence"
    defaults = _section("Fabrik defaults")
    trap = _plain(defaults.split("**Licence trap", 1)[1]) if "**Licence trap" in defaults else ""
    assert "LLaVA" in trap and "checkpoint" in trap, "the licence trap no longer warns about checkpoint licences"
    for bullet in _bullets("Fabrik defaults") + _bullets("Subcategories"):
        assert not re.search(r"\b(?:LLaVA|Kosmos)\b", bullet), f"an unmaintained model is offered: {bullet[:70]!r}"


def test_subcategories_route_each_modality() -> None:
    video = _bullet("Subcategories", "Video")
    assert re.search(r"OpenAI's models take no video", video), "the video lane no longer says OpenAI takes no video"
    # every audio lane opens on Gemini, and no clause in it hands audio to Claude
    audio = _bullet("Subcategories", "Audio")
    assert re.search(r"^Audio understanding[^:]*:\s*Gemini \(default\)", audio), (
        f"the audio lane no longer defaults to Gemini: {audio[:70]!r}"
    )
    assert not re.search(r"\bClaude\b", audio), f"the audio lane routes audio to Claude: {audio!r}"
    docs = _bullet("Subcategories", "Document")
    for needle in ("Mistral OCR", "LlamaParse", "Docling", "file-parser", "signup", "mistral-ocr"):
        assert needle in docs, f"the document lane no longer names {needle!r}"
    # OpenRouter's file-parser defaults to the model's native file input; Mistral OCR is the engine you set or the fallback
    assert not re.search(r"Mistral OCR[^.;]{0,80}\bdefault engine", docs), (
        "the document lane calls Mistral OCR the file-parser's default again"
    )
    gateway = _plain(_section("Gateway coverage").split("<!-- GATEWAY_COUNTS:START", 1)[0])
    assert "architecture.input_modalities" in gateway and "no video-input flag" in gateway, (
        "the gateway note no longer points at a video-input check that exists"
    )
    compare = _bullet("Subcategories", "Compare")
    for needle in ("arena.ai", "MMMU", "OpenCompass"):
        assert needle in compare, f"the comparison list no longer names {needle!r}"
    assert re.search(r"mirror is stale", compare), "the comparison list no longer flags the stale mirror"


def test_no_retired_routes() -> None:
    body = _plain(_prose())
    lowered = body.replace("docs/reference/kilo/", "docs/reference/").lower()
    for gone in ("traycer", "kilo", "kosmos"):
        assert not re.search(rf"\b{gone}\b", lowered), f"{gone} is retired and still named"
    assert not re.search(r"\bGPT-?4", body), (
        "OpenAI's GPT-4 line is shut down or scheduled; the pack still names it"
    )


def test_no_version_literals() -> None:
    version_re = _load("vision_pack_test", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    found = version_re.findall(_prose())
    assert not found, f"version literals in the pack: {found}"


def test_choice_recorded_and_cites_resolve() -> None:
    header = _plain(_pack().split("# 4. Vision-Language", 1)[0])
    assert "project.yaml (ai_category, ai_subcategory, ai_tools)" in header, (
        "the header no longer records the choice in project.yaml"
    )
    index = INDEX.read_text(encoding="utf-8")
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in index, f"ai/00 no longer names {key}: re-align this pack"
    heads = [ln.lstrip("#").strip() for ln in index.splitlines() if ln.startswith("#")]
    assert any(h.startswith("Claude subscription first") for h in heads), "ai/00 lost § Claude subscription first"
    assert "§ Claude subscription first" in _plain(_pack()), "the pack no longer cites ai/00 § Claude subscription first"
    for sibling in ("ai/20-vision.md", "ai/10-speech-audio.md", "core/76-gpu-workers.md"):
        assert sibling in _pack() and (RULES / sibling).is_file(), f"{sibling} is cited but missing"
    assert "AI_VENDOR_ACCESS.md" in _pack() and (ROOT / "docs/reference/kilo/AI_VENDOR_ACCESS.md").is_file(), (
        "the vendor-access catalog is cited but missing"
    )


@pytest.mark.skipif(not (LIB / "README.md").is_file(), reason="needs /opt/fabrik-lib")
def test_fabrik_lib_modules_exist() -> None:
    for module in ("pdf-extract", "ocr"):
        assert f"`{module}`" in _pack(), f"the pack no longer names fabrik-lib's {module}"
        assert (LIB / module / "README.md").is_file(), f"fabrik-lib no longer has {module}/"
    assert "def make_claude_vision_fn" in (LIB / "ocr" / "ocr" / "vision_claude.py").read_text(encoding="utf-8"), (
        "fabrik-lib's ocr no longer has make_claude_vision_fn"
    )
    assert "run_agentic" in (LIB / "llm-dispatch" / "README.md").read_text(encoding="utf-8")
