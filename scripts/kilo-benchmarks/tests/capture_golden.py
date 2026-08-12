# AFTER-EDIT: tests/test_golden_parity.py, docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Phase A.1 — freeze the consumer contract as a STRUCTURAL regression oracle.

The objective definition of "no functionality lost" for the catalog extraction, captured
before anything moves.

⚠️ MECHANISM CHANGED 2026-08-12 (operator-directed, after two review rounds).
The plan originally specified byte-identity (A.2 "assert sha256 == golden"; B.3 "byte-identical").
Measurement killed that: these artifacts are LIVE AGGREGATES over a flywheel that gains rows
daily. Across two consecutive daily auto-commits (8b1f077c -> 400ca5bb) the content genuinely
moved — ``n_total 274 -> 296``, ``glm-4.5-air 2.55/$0.0017/67 -> 2.57/$0.0019/75``. A
frozen-in-time byte-golden is therefore stale within 24 hours, permanently; and normalising
hard enough to survive that churn means blanking the very content the oracle protects (the
previous attempt collapsed ``gpt-4o-2024-05-13``, ``-08-06`` and ``-11-20`` into one string).

So this oracle freezes STRUCTURE, which is stable across regeneration:
  * artifact INVENTORY — every consumed path, and whether it is still produced;
  * marker INVENTORY — every ``(host, MARKER)`` pair that must keep being injected;
  * per-artifact SHAPE — markdown heading sequence + table header rows; JSON key schema.

That catches every "functionality lost" failure the extraction can cause — a doc that stops
being produced, a marker that stops being injected, a table that loses a column, a JSON that
loses a field — without false-REDing every night.

**Byte-equality still matters and still happens — in Phase C**, where the old and new engines
run against the SAME database at the SAME moment and their outputs are diffed. That is the
correct home for it, and the plan already specifies it there.

Gitignored artifacts: four consumed artifacts are git-ignored (``kilo_47_agents_final.json``,
``kilo_embeddings_final.json``, ``kilo_openrouter_routes_final.json``, ``models_browser.html``).
They are tracked for presence and shape when locally present; their absence in a fresh clone is
recorded as ``absent-by-gitignore`` rather than drift, or the oracle would be red everywhere
but one working copy.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
FABRIK_ROOT = SCRIPT_DIR.parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
MANIFEST = GOLDEN_DIR / "structure.json"
DB_QUERIES = GOLDEN_DIR / "db_queries.json"

# The 6 generated *_SELECTION.md docs + candidate signups. NOT a bare docs/reference/kilo/*.md
# glob: AGGREGATOR_ROADMAP.md and BENCHMARK_SOURCES.md are hand-authored (zero writers, absent
# from daily_refresh.sh), so including them would report a human's edit as extraction drift.
SELECTION_DOCS = [
    "docs/reference/kilo/CODING_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md",
    "docs/reference/kilo/IMAGE_GEN_SELECTION.md",
    "docs/reference/kilo/STT_SELECTION.md",
    "docs/reference/kilo/TRANSLATION_SELECTION.md",
    "docs/reference/kilo/TTS_SELECTION.md",
    "docs/reference/kilo/CANDIDATE_SIGNUPS.md",
]
CAPABILITIES_DOC = "docs/reference/kilo/KILO_MODEL_CAPABILITIES.md"
REGISTRY_JSONS = [
    "scripts/kilo_47_agents_final.json",
    "scripts/kilo_embeddings_final.json",
    "scripts/kilo_openrouter_routes_final.json",
]
OTHER_OUTPUTS = [
    "scripts/kilo-benchmarks/models_browser.html",
    "docs/traycer/kilo_selected_agents.md",
]
# 1:1 marker -> host. The non-`ai/` hosts are the ones an `ai/*`-only scope silently drops.
MARKER_HOSTS: list[tuple[str, str]] = [
    ("docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md", "ROSTER"),
    ("docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md", "EMBEDDING_ROSTER"),
    (CAPABILITIES_DOC, "EMBEDDING_CATALOG"),
    (".windsurf/rules/core/65-rag-search.md", "EMBEDDING_WINNERS"),
]
AI_PACK_MARKERS = ("GATEWAY_COUNTS", "OPENROUTER_ROUTES")

# Values churn daily; structure does not. Blank only what appears INSIDE a heading.
_VOLATILE_IN_HEADING = re.compile(r"\d{4}-\d{2}-\d{2}|n_total=\d+|\(\d+\)")


def _strip_volatile(s: str) -> str:
    return _VOLATILE_IN_HEADING.sub("<N>", s)


def _is_gitignored(rel: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(FABRIK_ROOT), "check-ignore", "-q", rel], capture_output=True
    )
    return r.returncode == 0


def md_shape(text: str) -> dict:
    """Structural fingerprint of a markdown doc: headings + table header rows.

    Deliberately excludes every value — scores, counts, prices and dates all churn daily.
    A lost section or a lost table column is what "functionality lost" actually looks like.
    """
    # SKELETON ONLY (# and ##). Deeper headings are INVENTORY, not structure: in
    # KILO_MODEL_CAPABILITIES.md there is one `###` per provider, and providers are ingested
    # daily (measured: 66 -> 68 headings across one day, DEEPGRAM and ASSEMBLYAI appearing).
    # Freezing that list would red the oracle on a normal catalog addition — which is growth,
    # not lost functionality.
    skeleton = re.findall(r"^(#{1,2})\s+(.+?)\s*$", text, re.M)
    headers = re.findall(r"^\|(.+?)\|[ \t]*\n\|[\s:|-]+\|[ \t]*$", text, re.M)
    # DISTINCT column tuples, not per-table rows: the NUMBER of tables tracks the provider
    # count (data), but the set of column contracts is the real interface. Losing a column is
    # exactly what "functionality lost" looks like.
    cols = sorted({tuple(c.strip().strip("*`") for c in row.split("|")) for row in headers})
    return {
        "skeleton": [f"{h} {_strip_volatile(s)}" for h, s in skeleton],
        "table_columns": [list(c) for c in cols],
    }


def json_shape(text: str) -> dict:
    """Key schema of a JSON artifact — keys and container types, never values."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        return {"parse_error": type(exc).__name__}

    def walk(o, depth=0):
        if depth > 3:
            return "..."
        if isinstance(o, dict):
            return {k: walk(v, depth + 1) for k, v in sorted(o.items())[:40]}
        if isinstance(o, list):
            return [walk(o[0], depth + 1)] if o else []
        return type(o).__name__

    return {"schema": walk(data)}


def html_shape(text: str) -> dict:
    """Coarse shape for the generated browser page."""
    return {
        "has_table": "<table" in text,
        "script_blocks": text.count("<script"),
        "id_attrs": sorted(set(re.findall(r'id="([a-zA-Z0-9_-]+)"', text)))[:40],
    }


def _shape_for(rel: str, text: str) -> dict:
    if rel.endswith(".json"):
        return json_shape(text)
    if rel.endswith(".html"):
        return html_shape(text)
    return md_shape(text)


def _read(rel: str) -> str | None:
    f = FABRIK_ROOT / rel
    if not f.exists():
        return None
    return f.read_text(encoding="utf-8", errors="replace")


def extract_block(text: str, marker: str) -> str | None:
    m = re.search(
        rf"<!--\s*{re.escape(marker)}:START.*?-->(.*?)<!--\s*{re.escape(marker)}:END\s*-->",
        text,
        re.S,
    )
    return m.group(1) if m else None


def strip_marker(text: str, marker: str) -> str:
    return re.sub(
        rf"<!--\s*{re.escape(marker)}:START.*?-->.*?<!--\s*{re.escape(marker)}:END\s*-->",
        "",
        text,
        flags=re.S,
    )


def ai_pack_hosts() -> list[Path]:
    return sorted((FABRIK_ROOT / ".windsurf" / "rules" / "ai").glob("*.md"))


def _db_queries() -> dict[str, str]:
    """The exact SQL live hub consumers issue — read from the MODULE, never hand-typed.

    Importing yields the f-string-INTERPOLATED query (real table, real 90-day window, real
    MIN_RUNS); a regex over source would capture the literal ``FROM {TABLE}``. Every read is
    guarded: Phase E deletes the engine scripts from fabrik while RETAINING tests/golden/**,
    so an unguarded read here would crash the oracle post-excise.
    """
    out: dict[str, str] = {}
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import rank_task_subagents as _rts

        out["rank_task_subagents.flywheel"] = _rts.QUERY
    except Exception as exc:  # noqa: BLE001 — the oracle must survive a missing engine
        out["rank_task_subagents.flywheel"] = f"<UNAVAILABLE: {type(exc).__name__}>"
    try:
        src = (SCRIPT_DIR / "rank_task_subagents.py").read_text(encoding="utf-8")
        m = re.search(r'"(SELECT id, quality_tier FROM agents[^"]*)"', src)
        if m:
            out["rank_task_subagents.quality_tier"] = m.group(1)
    except OSError as exc:
        out["rank_task_subagents.quality_tier"] = f"<UNAVAILABLE: {type(exc).__name__}>"
    try:
        ugc = (SCRIPT_DIR / "update_gateway_counts.py").read_text(encoding="utf-8")
        for i, q in enumerate(sorted(set(re.findall(r'"(SELECT count\(\*\) FROM [^"]+)"', ugc)))):
            out[f"update_gateway_counts.{i:02d}"] = q
    except OSError as exc:
        out["update_gateway_counts"] = f"<UNAVAILABLE: {type(exc).__name__}>"
    return out


def observe() -> dict:
    """Observe the live contract — inventory + shape. Writes nothing."""
    artifacts: dict[str, dict] = {}
    for rel in SELECTION_DOCS + REGISTRY_JSONS + OTHER_OUTPUTS:
        text = _read(rel)
        if text is None:
            artifacts[rel] = {
                "present": False,
                "reason": "absent-by-gitignore" if _is_gitignored(rel) else "MISSING",
            }
            continue
        artifacts[rel] = {"present": True, "shape": _shape_for(rel, text)}

    cap = _read(CAPABILITIES_DOC)
    artifacts[CAPABILITIES_DOC] = (
        {"present": False, "reason": "MISSING"}
        if cap is None
        else {"present": True, "shape": md_shape(strip_marker(cap, "EMBEDDING_CATALOG"))}
    )

    markers: dict[str, bool] = {}
    for rel, marker in MARKER_HOSTS:
        text = _read(rel)
        markers[f"{rel}::{marker}"] = bool(text and extract_block(text, marker) is not None)
    for host in ai_pack_hosts():
        text = host.read_text(encoding="utf-8")
        for marker in AI_PACK_MARKERS:
            if extract_block(text, marker) is not None:
                markers[f".windsurf/rules/ai/{host.name}::{marker}"] = True

    return {"artifacts": artifacts, "markers": markers, "db_queries": _db_queries()}


def snapshot() -> dict:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    obs = observe()
    MANIFEST.write_text(json.dumps(obs, indent=1, sort_keys=True), encoding="utf-8")
    DB_QUERIES.write_text(json.dumps(obs["db_queries"], indent=1), encoding="utf-8")
    return obs


def verify() -> int:
    if not MANIFEST.exists():
        print("[capture_golden] no structure.json — run --snapshot first", file=sys.stderr)
        return 2
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    got = observe()
    drift: list[str] = []

    for rel, w in want["artifacts"].items():
        g = got["artifacts"].get(rel)
        if g is None:
            drift.append(f"ARTIFACT DROPPED FROM THE CONTRACT: {rel}")
            continue
        if w.get("present") and not g.get("present") and g.get("reason") != "absent-by-gitignore":
            drift.append(f"NO LONGER PRODUCED: {rel}")
            continue
        if w.get("present") and g.get("present") and w.get("shape") != g.get("shape"):
            drift.append(f"SHAPE CHANGED: {rel}")

    for key, present in want["markers"].items():
        if present and not got["markers"].get(key):
            drift.append(f"MARKER NO LONGER INJECTED: {key}")
    for key in got["markers"]:
        if key not in want["markers"]:
            print(f"[capture_golden] NEW marker (addition, not drift): {key}", file=sys.stderr)

    if drift:
        print("[capture_golden] CONTRACT DRIFT:", file=sys.stderr)
        for d in drift:
            print("   " + d, file=sys.stderr)
        return 1
    n = len(want["artifacts"]) + len(want["markers"])
    print(f"[capture_golden] OK — {n} contract elements intact")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="capture_golden")
    ap.add_argument("--snapshot", action="store_true", help="freeze the contract (destructive)")
    ap.add_argument("--verify", action="store_true", help="check the live tree against it")
    args = ap.parse_args()
    if args.verify:
        return verify()
    if not args.snapshot:
        print(
            "[capture_golden] refusing to re-freeze without --snapshot.\n"
            "  --verify   check the live tree against the frozen contract\n"
            "  --snapshot OVERWRITE the frozen contract (destructive)",
            file=sys.stderr,
        )
        return 2
    obs = snapshot()
    print(
        f"[capture_golden] froze {len(obs['artifacts'])} artifacts + "
        f"{len(obs['markers'])} markers -> {MANIFEST}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
