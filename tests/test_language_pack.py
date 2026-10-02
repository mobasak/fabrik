"""Pins `ai/30-language.md` to its consumers, its licences and its cross-references.

The pack is glob-activated on every LLM, NLP, text, translation and embedding path. Seven things it states can go false
with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES) survive, and `Last content verification:` parses
   for `scripts/check_ai_pack_freshness.py`.
2. LLM work and translation go to Claude through `claude -p` first, as ai/00 says; the pack once pinned Claude models by
   version and defaulted translation to DeepL.
3. Embeddings point to core/65-rag-search.md, which owns pgvector on `postgres-main`; Supabase is never offered as a
   store, and dedicated vector databases stay banned.
4. The licence trap names Meta's non-commercial translation weights (NLLB, SeamlessM4T).
5. No retired route or model is offered: the Kilo gateway, Traycer, OpenAI's GPT-4, Cohere's legacy summarize endpoint.
6. No version number in any shape — the detector is the one `tests/test_vision_pack.py` defines, loaded here.
7. The vendor choice is recorded in project.yaml with ai/00's keys, and the cited packs and fabrik-lib modules exist.

Guards read structure (one bullet at a time, emphasis stripped, whole words) so a reworded or restyled line keeps its
meaning. The cheapest way past (2) is to rename the default in prose the bullet parser does not read; the review reads
the defaults. The cheapest way past (6) is a version in words; the detector catches the shapes agents copy.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "30-language.md"
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
    mod = _load("freshchk_language", FRESH)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_llm_and_translation_go_to_claude_first() -> None:
    index = _plain(INDEX.read_text(encoding="utf-8"))
    assert "Translation is text, so it is claude -p first" in index, (
        "ai/00 changed its translation rule: re-align"
    )
    llm = _bullet("Fabrik defaults", "LLM")
    assert "Claude through claude -p" in llm and "by alias" in llm, (
        "the LLM default is no longer Claude by alias"
    )
    translation = _bullet("Fabrik defaults", "Translation")
    # the default is what the bullet OPENS with: a later "Claude first rests on…" sentence must not stand in for it
    assert re.match(r"Translation\s*:?\s*→\s*Claude first", translation), (
        f"the translation default changed: {translation[:60]!r}"
    )
    assert "mt-router" in translation, "translation no longer goes through mt-router"
    # operator ruling (D-505): DeepL is not context-aware enough, so it comes last and the ruling stays stated
    assert "context-aware" in translation and "D-505" in translation, (
        "the DeepL ruling is gone from the default"
    )
    choice = _bullet("Subcategories", "Translation")
    order = [choice.find(n) for n in ("Azure", "Google", "DeepL")]
    assert -1 not in order and order[2] > max(order[:2]), (
        f"DeepL is no longer last among the managed engines: {order}"
    )
    # mt-router runs Claude only on the context path: the pack must say how a plain call reaches it
    assert "MT_CLAUDE_PLAIN=1" in translation and "context" in translation, (
        "the plain-path knob is gone"
    )
    assert "decision ledger" in translation and "project.yaml" in translation, (
        "the bake-off result no longer says where it is recorded"
    )
    assert "bake-off" in translation, (
        "the dedicated-MT boundary (a bake-off per language pair) is gone"
    )
    gateway = _plain(_section("Gateway coverage").split("<!-- GATEWAY_COUNTS:START", 1)[0])
    assert "not a metered gateway" in gateway, (
        "the gateway note no longer keeps Claude work off metered gateways"
    )


def test_embeddings_point_to_core65_and_pgvector() -> None:
    embeddings = _bullet("Fabrik defaults", "Embeddings")
    assert "pgvector on postgres-main" in embeddings, (
        "embeddings no longer go to pgvector on postgres-main"
    )
    assert "core/65-rag-search.md" in embeddings, (
        "embeddings no longer point to core/65, which owns them"
    )
    core65 = _plain((RULES / "core" / "65-rag-search.md").read_text(encoding="utf-8"))
    assert "pgvector" in core65 and "postgres-main" in core65, (
        "core/65 no longer owns pgvector on postgres-main"
    )
    for sentence in re.split(r"(?<=[.;])\s+", _plain(_prose())):
        if re.search(r"\bsupabase\b", sentence, re.I):
            assert "retired" in sentence.lower(), f"Supabase is offered as a store: {sentence!r}"
    choice = _bullet("Subcategories", "Embeddings")
    assert "core/65's roster is binding" in choice, (
        "the embedding candidates no longer defer to core/65's roster"
    )
    ban = _bullet("Fabrik defaults", "Dedicated vector")
    assert "BANNED" in ban and all(
        n in ban for n in ("Pinecone", "Qdrant", "Weaviate", "Milvus")
    ), "the dedicated vector database ban lost its teeth"


def test_licence_trap_names_meta_mt() -> None:
    defaults = _section("Fabrik defaults")
    trap = _plain(defaults.split("**Licence trap", 1)[1]) if "**Licence trap" in defaults else ""
    for needle in ("NLLB", "SeamlessM4T", "CC-BY-NC"):
        assert needle in trap, f"the licence trap no longer names {needle!r}"
    for bullet in _bullets("Fabrik defaults"):
        assert "NLLB" not in bullet and "Seamless" not in bullet, (
            f"a non-commercial model is a default: {bullet!r}"
        )


def test_no_retired_routes() -> None:
    body = _plain(_prose())
    lowered = body.replace("docs/reference/kilo/", "docs/reference/").lower()
    for gone in ("traycer", "kilo"):
        assert not re.search(rf"\b{gone}\b", lowered), f"{gone} is retired and still named"
    assert not re.search(r"\bGPT-?4\b", body), (
        "OpenAI's GPT-4 API models shut down; the pack still names them"
    )
    for sentence in re.split(r"(?<=[.;])\s+", body):
        if re.search(r"cohere\S* summari[sz]", sentence, re.I):
            assert re.search(r"legacy|unmaintained|deprecated", sentence, re.I), (
                f"Cohere Summarize offered: {sentence!r}"
            )


def test_no_version_literals() -> None:
    version_re = _load("vision_pack_test", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    body = re.sub(r"Apache-?2\.0|A?GPL-\d\.\d|CC-BY(?:-[A-Z]+)*-? ?\d\.\d", "", _prose())
    found = version_re.findall(body)
    assert not found, f"version literals in the pack: {found}"


def test_choice_recorded_and_cites_resolve() -> None:
    header = _plain(_pack().split("# 3. Language AI", 1)[0])
    assert "project.yaml (ai_category, ai_subcategory, ai_tools)" in header, (
        "the header no longer records the choice in project.yaml"
    )
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in INDEX.read_text(encoding="utf-8"), (
            f"ai/00 no longer names {key}: re-align this pack"
        )
    heads = [
        ln.lstrip("#").strip()
        for ln in INDEX.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]
    assert any(h.startswith("Claude subscription first") for h in heads), (
        "ai/00 lost § Claude subscription first"
    )
    for sibling in ("core/65-rag-search.md", "core/66-rag-chunking.md"):
        assert sibling in _pack() and (RULES / sibling).is_file(), f"{sibling} is cited but missing"


@pytest.mark.skipif(not (LIB / "README.md").is_file(), reason="needs /opt/fabrik-lib")
def test_fabrik_lib_modules_exist() -> None:
    for module in ("llm-dispatch", "mt-router", "rag"):
        assert f"`{module}`" in _pack(), f"the pack no longer names fabrik-lib's {module}"
        assert (LIB / module / "README.md").is_file(), f"fabrik-lib no longer has {module}/"
    assert "RAG_EMBEDDING_MODEL" in (LIB / "rag" / "README.md").read_text(encoding="utf-8")


def test_globs_reach_summarization_paths() -> None:
    """The matcher compares whole path segments, so a bare stem never matches summarization/ or summarizer/."""
    matcher = _load("rules_match", ROOT / "scripts" / "rules_match.py")
    globs = re.search(r"^globs: (\[.*\])$", _pack(), re.M).group(1)
    patterns = re.findall(r'"([^"]+)"', globs)
    for path in (
        "src/summarization/engine.py",
        "app/summarizer/run.py",
        "src/translation/x.py",
        "lib/embeddings/e.py",
    ):
        assert any(matcher.pack_matches_path(path, g, empty_matches_all=False) for g in patterns), (
            f"no glob of the pack reaches {path}"
        )
