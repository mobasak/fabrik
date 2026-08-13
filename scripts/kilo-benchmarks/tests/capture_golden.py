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
import importlib.util
import json
import os
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


# ⚠️ Bumped whenever the SHAPE FORMAT changes. A golden frozen by an older observer lacks
# the newer invariants, and `shapes_equal` would silently skip them while `verify()` printed
# OK — a strictly worse failure than no oracle, because it certifies what it never checked.
# verify() refuses to run against a mismatched version instead.
ORACLE_VERSION = 2

# A collection may lose this fraction before we call it a collapse, or multiply by this
# factor before we call it a fan-out. Measured daily churn is ~8% (n_total 274 -> 296) and
# per-table churn was 0 and +6 rows; a real extraction failure emptied 181 rows to 24 (-87%).
# Both bounds sit an order of magnitude away from normal churn.
COLLAPSE_RATIO = 0.5
FANOUT_CEILING = 4.0


def magnitudes_ok(want: dict, got: dict) -> tuple[bool, str]:
    """Compare per-collection sizes by RATIO. Returns (ok, reason).

    PER-COLLECTION, not per-document — that distinction is the whole point. A single
    doc-wide row count is nearly useless: in TASK_SUBAGENT_SELECTION.md the routing tables
    `pick_models` actually consumes are 35 of 157 rows, and the two tables labelled
    "display only; not parsed for routing" are 122. Emptying EVERY routing table leaves
    122/157 = 78% of rows — comfortably inside any doc-wide tolerance — so the husk that
    breaks routing passed green. Keyed sizes catch it; a scalar cannot.
    """
    for key, wn in want.items():
        gn = got.get(key)
        if gn is None:
            return False, f"collection disappeared: {key}"
        if wn == 0:
            continue
        if gn < wn * COLLAPSE_RATIO:
            return False, f"COLLAPSE {key}: {wn} -> {gn}"
        if gn > wn * FANOUT_CEILING:
            return False, f"FAN-OUT {key}: {wn} -> {gn} (duplication?)"
    return True, ""


def shapes_equal(want: dict, got: dict) -> bool:
    """Structure must match exactly; collection SIZES only within a ratio band."""
    return not shape_drift(want, got)


def shape_drift(want: dict, got: dict) -> str:
    """The reason `want` and `got` differ, or "" when they agree."""
    w, g = dict(want), dict(got)
    wm, gm = w.pop("magnitudes", None), g.pop("magnitudes", None)
    if w != g:
        return "structure changed"
    # A golden frozen before magnitudes existed must not silently pass; verify() gates on
    # ORACLE_VERSION, so reaching here with a missing side means a hand-built shape in a test.
    if wm is None or gm is None:
        return ""
    ok, why = magnitudes_ok(wm, gm)
    return "" if ok else why


def _is_gitignored(rel: str) -> bool:
    # Phase B copies tests/ into the engine repo; `git` may be absent or the tree not yet a
    # repo. Crashing the gate is strictly worse than reporting drift, so fail to "not ignored"
    # (fail-CLOSED: the artifact reads as MISSING and reds loudly).
    try:
        r = subprocess.run(
            ["git", "-C", str(FABRIK_ROOT), "check-ignore", "-q", rel], capture_output=True
        )
    except OSError:
        return False
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
    # ⚠️ MAGNITUDE, not just shape (added 2026-08-12 after self-testing the redesign).
    # Structure alone is TOO WEAK: deleting every data row from TASK_SUBAGENT_SELECTION.md
    # (181 rows -> 24) left skeleton and columns byte-identical, so the oracle would have
    # certified "no functionality lost" for an extraction that emitted a correct-looking
    # husk with zero data — the single most likely extraction failure (engine copied, DB
    # wiring wrong). Row count is recorded in coarse BUCKETS so ordinary churn cannot move
    # it: measured daily drift is ~8% (n_total 274 -> 296), while a collapse is -87%.
    # Bucketing by powers of ~1.5 tolerates a 50% swing and still catches an order of
    # magnitude. A doc that legitimately grows past a bucket edge is a one-line re-freeze;
    # a doc that silently empties is caught the first time.
    return {
        "skeleton": [f"{h} {_strip_volatile(s)}" for h, s in skeleton],
        "table_columns": [list(c) for c in cols],
        "magnitudes": _rows_per_table(text),
    }


def _rows_per_table(text: str) -> dict[str, int]:
    """Row count PER TABLE, keyed by the table's column contract.

    Keyed by columns rather than by the enclosing heading because headings carry volatile
    counts (`### OPENAI (87 models)`) and get renamed; the column contract is the stable
    identity. Tables sharing a column contract are summed.
    """
    sizes: dict[str, int] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        head = re.match(r"^\|(.+?)\|[ \t]*$", lines[i])
        if head and re.match(r"^\|[\s:|-]+\|[ \t]*$", lines[i + 1]):
            key = "|".join(c.strip().strip("*`") for c in head.group(1).split("|"))
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            sizes[key] = sizes.get(key, 0) + (j - i - 2)
            i = j
            continue
        i += 1
    return sizes


def json_shape(text: str) -> dict:
    """Key schema of a JSON artifact — keys and container types, never values.

    `magnitudes` carries container LENGTHS because the schema alone cannot see them: `walk`
    renders a list as `[walk(o[0])]`, one element regardless of length, so truncating every
    list to a single entry (a registry going 40 assignments -> 13) produced a byte-identical
    schema. Dropping a whole key was caught; shrinking every collection was not.
    """
    try:
        data = json.loads(text)
    except ValueError as exc:
        return {"parse_error": type(exc).__name__}

    sizes: dict[str, int] = {}

    def walk(o, depth=0, path="$"):
        if depth > 3:
            return "..."
        if isinstance(o, dict):
            sizes[path] = len(o)
            return {k: walk(v, depth + 1, f"{path}.{k}") for k, v in sorted(o.items())[:40]}
        if isinstance(o, list):
            sizes[path] = len(o)
            return [walk(o[0], depth + 1, f"{path}[]")] if o else []
        return type(o).__name__

    return {"schema": walk(data), "magnitudes": sizes}


def html_shape(text: str) -> dict:
    """Coarse shape for the generated browser page.

    `data_rows` deliberately reuses md_shape's field name so shapes_equal applies the SAME
    collapse ratio here. Measured: blanking the 3.7MB embedded JS payload does change
    `id_attrs` — but only because the blob happens to contain `id="` substrings. That is
    luck, not a contract. The row count makes the catch intentional.
    """
    payload = re.search(r'<script[^>]*id="payload"[^>]*>(.*?)</script>', text, re.S)
    return {
        "has_table": "<table" in text,
        "script_blocks": text.count("<script"),
        "id_attrs": sorted(set(re.findall(r'id="([a-zA-Z0-9_-]+)"', text)))[:40],
        "magnitudes": {
            "tr": text.count("<tr"),
            # The models are rendered client-side from this blob, NOT from markup: the page
            # is 3.86 MB but holds only 157 literal `<tr`. Emptying the blob is a total data
            # loss that leaves every markup-derived field identical, so the blob's own size
            # is the only honest magnitude here.
            "payload_bytes": len(payload.group(1)) if payload else 0,
        },
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
    # Load from the FILE under SCRIPT_DIR, not by module name. A bare `import
    # rank_task_subagents` resolves through whatever is already on sys.path — sibling test
    # modules put the real engine dir there — so the engine looked present even when
    # SCRIPT_DIR pointed nowhere, and the missing-engine guard could not be tested (nor could
    # it catch its own revert). sys.path is restored so a bogus dir never leaks into the
    # rest of the session.
    _saved_path = list(sys.path)
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        spec = importlib.util.spec_from_file_location(
            "_oracle_rts", SCRIPT_DIR / "rank_task_subagents.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("no engine module")
        _rts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_rts)
        out["rank_task_subagents.flywheel"] = _rts.QUERY
    except Exception as exc:  # noqa: BLE001 — the oracle must survive a missing engine
        out["rank_task_subagents.flywheel"] = f"<UNAVAILABLE: {type(exc).__name__}>"
    finally:
        sys.path[:] = _saved_path
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
        # errors="replace" mirrors _read: a non-UTF-8 byte in any fleet-synced ai/*.md must
        # report drift, never crash the gate.
        text = host.read_text(encoding="utf-8", errors="replace")
        for marker in AI_PACK_MARKERS:
            if extract_block(text, marker) is not None:
                markers[f".windsurf/rules/ai/{host.name}::{marker}"] = True

    return {
        "oracle_version": ORACLE_VERSION,
        "artifacts": artifacts,
        "markers": markers,
        "db_queries": _db_queries(),
    }


def snapshot() -> dict:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    obs = observe()
    # A collection frozen at 0 can never be ratio-compared again (0 * anything == 0), so
    # re-freezing while the pipeline is broken silently bakes in a dead check. --snapshot is
    # the only writer and nothing else validates the observed state, so say it out loud.
    for rel, a in sorted(obs["artifacts"].items()):
        empties = [k for k, n in (a.get("shape", {}).get("magnitudes") or {}).items() if n == 0]
        if empties:
            print(
                f"[capture_golden] ⚠️  freezing EMPTY collections in {rel}: {empties} — "
                "if the pipeline is broken, fix it before freezing; these can never red again",
                file=sys.stderr,
            )
    MANIFEST.write_text(json.dumps(obs, indent=1, sort_keys=True), encoding="utf-8")
    DB_QUERIES.write_text(json.dumps(obs["db_queries"], indent=1), encoding="utf-8")
    return obs


def verify() -> int:
    if not MANIFEST.exists():
        print("[capture_golden] no structure.json — run --snapshot first", file=sys.stderr)
        return 2
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if want.get("oracle_version") != ORACLE_VERSION:
        print(
            f"[capture_golden] golden was frozen by oracle v{want.get('oracle_version')}, "
            f"this is v{ORACLE_VERSION} — its invariants would be SKIPPED, not checked. "
            "Re-freeze with --snapshot.",
            file=sys.stderr,
        )
        return 2
    got = observe()
    drift: list[str] = []

    # On the box that RUNS the pipeline, a gitignored artifact that stopped being produced is
    # the headline failure — not an absent checkout. 4 of 13 artifacts are gitignored, so the
    # fresh-clone tolerance below silently exempts 31% of the inventory from "NO LONGER
    # PRODUCED". daily_refresh.sh sets this; a laptop/CI clone does not.
    require_local = os.environ.get("ORACLE_REQUIRE_LOCAL_ARTIFACTS") == "1"

    for rel, w in want["artifacts"].items():
        g = got["artifacts"].get(rel)
        if g is None:
            drift.append(f"ARTIFACT DROPPED FROM THE CONTRACT: {rel}")
            continue
        if w.get("present") and not g.get("present"):
            if g.get("reason") == "absent-by-gitignore" and not require_local:
                continue
            drift.append(f"NO LONGER PRODUCED: {rel}")
            continue
        if w.get("present") and g.get("present"):
            ws, gs = w.get("shape", {}), g.get("shape", {})
            if not shapes_equal(ws, gs):
                if (
                    ws.get("data_rows")
                    and gs.get("data_rows", 0) < ws["data_rows"] * COLLAPSE_RATIO
                ):
                    drift.append(
                        f"DATA COLLAPSE: {rel} — {ws['data_rows']} rows -> {gs.get('data_rows', 0)}"
                    )
                else:
                    drift.append(f"SHAPE CHANGED: {rel}")

    # The SQL the live hub consumers issue. snapshot() froze these into both structure.json
    # and db_queries.json, but nothing ever compared them — so WINDOW_DAYS, MIN_RUNS, the
    # HAVING clause or the table name could all change and the oracle stayed green, defeating
    # the module's stated purpose ("read live, so it cannot drift into fiction").
    for key, wq in want.get("db_queries", {}).items():
        gq = got["db_queries"].get(key)
        if gq is None:
            drift.append(f"QUERY GONE: {key}")
        elif gq != wq and "UNAVAILABLE" not in str(wq):
            drift.append(f"QUERY CHANGED: {key}")

    for key, present in want["markers"].items():
        if present and not got["markers"].get(key):
            drift.append(f"MARKER NO LONGER INJECTED: {key}")
    for key in got["markers"]:
        if key not in want["markers"]:
            print(f"[capture_golden] NEW marker (addition, not drift): {key}", file=sys.stderr)
    # Symmetry with markers: an artifact added to SELECTION_DOCS/REGISTRY_JSONS/OTHER_OUTPUTS
    # without re-snapshotting is simply absent from `want` and was therefore unprotected with
    # no signal at all. Not drift — but it must not be silent.
    for rel in got["artifacts"]:
        if rel not in want["artifacts"]:
            print(
                f"[capture_golden] NEW artifact NOT YET FROZEN (unprotected): {rel} "
                "— re-run --snapshot to bring it under the contract",
                file=sys.stderr,
            )

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
