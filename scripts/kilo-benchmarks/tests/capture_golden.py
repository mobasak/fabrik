# AFTER-EDIT: tests/test_golden_parity.py, docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Phase A.1 — freeze the consumer contract as an executable regression oracle.

This is the objective definition of "no functionality lost" for the catalog extraction: a
snapshot of every artifact a live consumer reads, plus the exact DB queries the hub consumers
issue, captured BEFORE anything moves. Phase B/C diff produced output against it.

Three artifact classes, and the split is load-bearing (get it wrong and B.3 parity
false-flags on every run):

1. **Whole-file goldens** — files a generator writes end to end: the 6
   ``docs/reference/kilo/*_SELECTION.md`` docs, the Traycer registry JSONs, and
   ``KILO_MODEL_CAPABILITIES.md`` **with its injected ``EMBEDDING_CATALOG`` block STRIPPED**
   (``generate_model_capabilities.py`` writes the base; ``embedding_export_markdown`` injects
   into the live file afterwards, so the base is what the decoupled engine will emit).
2. **Marker-body goldens** — only the text BETWEEN a marker pair, because the host file is
   not engine-owned (hand-authored prose surrounds it). Hosts are NOT confined to
   ``.windsurf/rules/ai/``.
3. **DB queries** — the SQL live hub consumers run, so the contract covers the query shape,
   not just its rendered output.

⚠️ Volatile fields are normalised before hashing. These artifacts are rewritten by cron EVERY
DAY and carry a date inside the frozen region (``Last refresh:`` in the selection docs,
``last-refreshed:`` in every marker opener). Without normalisation the first verify after
midnight reports drift on ~9 docs and 11 marker blocks for reasons that have nothing to do
with the extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
FABRIK_ROOT = SCRIPT_DIR.parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
BLOCKS_DIR = GOLDEN_DIR / "blocks"
MANIFEST = GOLDEN_DIR / "manifest.json"
DB_QUERIES = GOLDEN_DIR / "db_queries.json"

# ── class 1: whole-file goldens ───────────────────────────────────────────────
# The 6 *_SELECTION.md docs. NOT a bare docs/reference/kilo/*.md glob: AGGREGATOR_ROADMAP.md
# and BENCHMARK_SOURCES.md are hand-authored (zero writers, absent from daily_refresh.sh), so
# freezing them would report a human's edit as extraction drift.
SELECTION_DOCS = [
    "docs/reference/kilo/CODING_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/IMAGE_GEN_SELECTION.md",
    "docs/reference/kilo/STT_SELECTION.md",
    "docs/reference/kilo/TRANSLATION_SELECTION.md",
    "docs/reference/kilo/TTS_SELECTION.md",
]
REGISTRY_JSONS = [
    "scripts/kilo_47_agents_final.json",
    "scripts/kilo_all_models.json",
    "scripts/kilo_embeddings_final.json",
    "scripts/kilo_openrouter_routes_final.json",
]
# Hashed with EMBEDDING_CATALOG stripped — see module docstring.
CAPABILITIES_DOC = "docs/reference/kilo/KILO_MODEL_CAPABILITIES.md"

# ── class 2: marker-body goldens, keyed by (host, MARKER) ────────────────────
# 1:1 marker→host. The three non-`ai/` hosts are the ones an `ai/*`-only scope silently drops.
MARKER_HOSTS: list[tuple[str, str]] = [
    ("docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md", "ROSTER"),
    ("docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md", "EMBEDDING_ROSTER"),
    (CAPABILITIES_DOC, "EMBEDDING_CATALOG"),
    (".windsurf/rules/core/65-rag-search.md", "EMBEDDING_WINNERS"),
]
AI_PACK_MARKERS = ("GATEWAY_COUNTS", "OPENROUTER_ROUTES")

# ── volatile-field normalisation ─────────────────────────────────────────────
_VOLATILE = (
    re.compile(r"^(Last refresh:).*$", re.M),
    re.compile(r"(last-refreshed:\s*)\d{4}-\d{2}-\d{2}"),
    re.compile(r"^(_?Generated:).*$", re.M),
)


def normalize(text: str) -> str:
    """Strip fields that change daily but carry no contract meaning."""
    for pat in _VOLATILE:
        text = pat.sub(lambda m: m.group(1) + " <NORMALIZED>", text)
    return text


def sha(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def extract_block(text: str, marker: str) -> str | None:
    """Return the body BETWEEN ``<!-- MARKER:START ... -->`` and ``<!-- MARKER:END -->``."""
    m = re.search(
        rf"<!--\s*{re.escape(marker)}:START.*?-->(.*?)<!--\s*{re.escape(marker)}:END\s*-->",
        text,
        re.S,
    )
    return m.group(1) if m else None


def strip_marker(text: str, marker: str) -> str:
    """Remove an injected marker section so the whole-file golden is the generator's base."""
    return re.sub(
        rf"<!--\s*{re.escape(marker)}:START.*?-->.*?<!--\s*{re.escape(marker)}:END\s*-->",
        "",
        text,
        flags=re.S,
    )


def ai_pack_hosts() -> list[Path]:
    return sorted((FABRIK_ROOT / ".windsurf" / "rules" / "ai").glob("*.md"))


def snapshot() -> dict[str, str]:
    """Write the golden set; return a manifest of ``{relative_key: sha256}``."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}

    for rel in SELECTION_DOCS + REGISTRY_JSONS:
        f = FABRIK_ROOT / rel
        if not f.exists():
            print(f"[capture_golden] MISSING (recorded as absent): {rel}", file=sys.stderr)
            continue
        manifest[rel] = sha(f.read_text(encoding="utf-8"))

    cap = FABRIK_ROOT / CAPABILITIES_DOC
    if cap.exists():
        manifest[CAPABILITIES_DOC] = sha(
            strip_marker(cap.read_text(encoding="utf-8"), "EMBEDDING_CATALOG")
        )

    for rel, marker in MARKER_HOSTS:
        f = FABRIK_ROOT / rel
        if not f.exists():
            print(f"[capture_golden] marker host absent (skipped): {rel}", file=sys.stderr)
            continue
        body = extract_block(f.read_text(encoding="utf-8"), marker)
        if body is None:
            print(f"[capture_golden] marker {marker} not found in {rel}", file=sys.stderr)
            continue
        key = f"blocks/{Path(rel).name}.{marker}.txt"
        (GOLDEN_DIR / key).write_text(normalize(body), encoding="utf-8")
        manifest[key] = sha(body)

    for host in ai_pack_hosts():
        text = host.read_text(encoding="utf-8")
        for marker in AI_PACK_MARKERS:
            body = extract_block(text, marker)
            if body is None:
                continue
            key = f"blocks/{host.name}.{marker}.txt"
            (GOLDEN_DIR / key).write_text(normalize(body), encoding="utf-8")
            manifest[key] = sha(body)

    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    DB_QUERIES.write_text(json.dumps(_db_queries(), indent=1), encoding="utf-8")
    return manifest


def _db_queries() -> dict[str, str]:
    """The exact SQL live hub consumers issue (spec §2 grounding, Phase A.1 step 2)."""
    return {
        "rank_task_subagents.quality_tier": (
            "SELECT id, quality_tier FROM agents WHERE quality_tier IS NOT NULL"
        ),
        "rank_task_subagents.flywheel": (
            "SELECT task_type, model, count(*), avg(quality_score), avg(cost_usd), avg(latency_s) "
            "FROM subagent_runs GROUP BY task_type, model"
        ),
        "update_gateway_counts.counts": (
            "SELECT gateway, count(*) FROM agents GROUP BY gateway"
        ),
    }


def verify() -> int:
    """Diff live artifacts against the goldens. Returns a process exit code."""
    if not MANIFEST.exists():
        print("[capture_golden] no manifest — run --snapshot first", file=sys.stderr)
        return 2
    golden = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = snapshot_hashes()
    drift = []
    for key, want in golden.items():
        got = live.get(key)
        if got is None:
            drift.append(f"MISSING: {key}")
        elif got != want:
            drift.append(f"DRIFT:   {key}")
    for key in live:
        if key not in golden:
            drift.append(f"NEW:     {key}")
    if drift:
        print("[capture_golden] contract drift detected:", file=sys.stderr)
        for d in drift:
            print("   " + d, file=sys.stderr)
        return 1
    print(f"[capture_golden] OK — {len(golden)} artifacts match the frozen contract")
    return 0


def snapshot_hashes() -> dict[str, str]:
    """Hash live artifacts WITHOUT writing goldens (the verify side)."""
    live: dict[str, str] = {}
    for rel in SELECTION_DOCS + REGISTRY_JSONS:
        f = FABRIK_ROOT / rel
        if f.exists():
            live[rel] = sha(f.read_text(encoding="utf-8"))
    cap = FABRIK_ROOT / CAPABILITIES_DOC
    if cap.exists():
        live[CAPABILITIES_DOC] = sha(
            strip_marker(cap.read_text(encoding="utf-8"), "EMBEDDING_CATALOG")
        )
    for rel, marker in MARKER_HOSTS:
        f = FABRIK_ROOT / rel
        if not f.exists():
            continue
        body = extract_block(f.read_text(encoding="utf-8"), marker)
        if body is not None:
            live[f"blocks/{Path(rel).name}.{marker}.txt"] = sha(body)
    for host in ai_pack_hosts():
        text = host.read_text(encoding="utf-8")
        for marker in AI_PACK_MARKERS:
            body = extract_block(text, marker)
            if body is not None:
                live[f"blocks/{host.name}.{marker}.txt"] = sha(body)
    return live


def main() -> int:
    ap = argparse.ArgumentParser(prog="capture_golden")
    ap.add_argument("--snapshot", action="store_true", help="write the golden set")
    ap.add_argument("--verify", action="store_true", help="diff live output against goldens")
    args = ap.parse_args()
    if args.verify:
        return verify()
    m = snapshot()
    blocks = sum(1 for k in m if k.startswith("blocks/"))
    print(f"[capture_golden] snapshotted {len(m)} artifacts ({blocks} marker bodies) -> {GOLDEN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
