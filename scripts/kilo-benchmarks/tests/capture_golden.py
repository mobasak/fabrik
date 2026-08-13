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
# `\(\d+[^)]*\)` covers BOTH `(12)` and `(87 models)`. The bare-`(\d+)` form was not enough:
# once headings became part of the magnitude key, `### OPENAI (87 models)` -> `(88 models)`
# changed the key overnight and reported "collection disappeared" — a false red on pure
# catalog growth, which is the fastest way to get an oracle ignored.
_VOLATILE_IN_HEADING = re.compile(r"\d{4}-\d{2}-\d{2}|n_total=\d+|\(\d+[^)]*\)")


def _strip_volatile(s: str) -> str:
    return _VOLATILE_IN_HEADING.sub("<N>", s)


# ⚠️ Bumped whenever the SHAPE FORMAT changes. A golden frozen by an older observer lacks
# the newer invariants, and `shapes_equal` would silently skip them while `verify()` printed
# OK — a strictly worse failure than no oracle, because it certifies what it never checked.
# verify() refuses to run against a mismatched version instead.
ORACLE_VERSION = 2

# How much a collection may shrink before we call it a collapse. Two regimes in one line:
#   min_allowed = min(wn - 1, wn * COLLAPSE_RATIO)
# Large collections get the ratio (measured daily churn on the big tables is ~8%; a real
# extraction failure was -87%). Small ones get an absolute allowance of exactly ONE item,
# because a ratio is meaningless at n=3 — but "meaningless" is not "disable it". A flat floor
# was tried and was strictly worse: at SMALL_N=10 it left 41 of 65 frozen collections (63%)
# and 7 of 13 artifacts protected against nothing but total emptying, which re-opened the very
# case json_shape exists to catch (kilo_47_agents_final.json's 13 role LISTS are all 1-5
# entries, so truncating all of them — 40 assignments -> 13, a 67% loss — read as green).
# Under the scaling rule: n=1 tolerates 1->0 (CANDIDATE_SIGNUPS.md is a queue whose natural
# end-state is empty, and it has already churned 2 -> 1 in-window), n=2 catches 2->0, and
# n>=3 catches a truncation-to-one. Growth stays cheap up to FANOUT_CEILING: Phase A freezes
# this contract for the whole B->E extraction and models_browser.html grew 1.41x in 26 days,
# so a tight ceiling would red on pure catalog growth.
COLLAPSE_RATIO = 0.5
FANOUT_CEILING = 10.0


# Artifacts whose tables may LEGITIMATELY empty. Exactly one: a signup-candidate queue whose
# natural end-state is zero (measured churning 2 -> 1 in-window). The n=1 tolerance was
# originally justified by this file alone and then applied to every 1-row collection — which
# silently exempted 25 collections, including the `plan` and `spec` routing shortlists and the
# ONLY data table in STT/TTS/TRANSLATION_SELECTION.md, from total-loss detection.
MAY_EMPTY = frozenset({"docs/reference/kilo/CANDIDATE_SIGNUPS.md"})

# Prefix marking a per-section row count in a magnitudes dict (see _rows_per_table).
SECTION_KEY = "\u00a7"


def _min_allowed(wn: int) -> float:
    """Smallest size that is still ordinary churn rather than a collapse.

    Never below 1: a collection emptying ENTIRELY is the husk this oracle exists to catch, at
    every size. (`min(wn - 1, ...)` alone evaluates to 0 at wn=1, which turned the check off
    for the 25 collections frozen at one row.)
    """
    return max(1.0, min(wn - 1, wn * COLLAPSE_RATIO))


def magnitudes_ok(want: dict, got: dict, may_empty: bool = False) -> tuple[bool, str]:
    """Compare per-collection sizes. Returns (ok, reason).

    PER-COLLECTION, not per-document, and keyed per SECTION — both distinctions were earned
    the hard way. A doc-wide row count was nearly useless: in TASK_SUBAGENT_SELECTION.md the
    routing tables `pick_models` consumes are 35 of 157 rows and the "display only" tables are
    122, so emptying every routing table left 78% of rows and passed green. Keying by column
    contract alone was not enough either: all six `### <task_type>` shortlists share one
    contract, so they summed into a single 21-row bucket and four of the six could be emptied
    while the total stayed above threshold. Only section-keyed sizes actually catch it.
    """
    for key, wn in want.items():
        if key.startswith(SECTION_KEY):
            # A per-SECTION count. Only total emptying counts here, because a section's size
            # is genuinely volatile: measured across 351 real commit pairs, `### X-AI` went
            # 15 -> 4 models in one day. Proportional loss is judged on the per-contract
            # `:: ROWS` aggregate instead, which is stable across that churn AND survives a
            # heading reformat (which changes every section key at once).
            gn = got.get(key)
            if gn is None or wn == 0:
                continue
            if gn == 0 and not may_empty:
                return False, f"EMPTIED {key}: {wn} -> 0"
            continue
        gn = got.get(key)
        if gn is None:
            # A section that vanished ENTIRELY is upstream catalog churn, not extraction
            # failure: measured over 24 consecutive daily commits of KILO_MODEL_CAPABILITIES.md
            # the only key losses were INFLECTION and UNKNOWN being delisted. The husk failure
            # this oracle exists to catch behaves differently — the renderer still runs, so the
            # section and its headers survive and the table EMPTIES, which trips COLLAPSE
            # below. Wholesale removal is covered instead by the `:: TABLES` count per column
            # contract, so losing 4 of 6 routing sections is still caught without false-reding
            # every delisted provider.
            continue
        if wn == 0:
            continue
        # A queue that drains is not a collapse — the exemption has to cover the aggregate
        # too, or the artifact it exists for still false-reds (measured: CANDIDATE_SIGNUPS.md
        # 6 -> 2 rows in one real commit pair). Growth is still checked.
        if not may_empty and gn < _min_allowed(wn):
            return False, f"COLLAPSE {key}: {wn} -> {gn}"
        if gn > wn * FANOUT_CEILING:
            return False, f"FAN-OUT {key}: {wn} -> {gn} (duplication?)"
    return True, ""


def shapes_equal(want: dict, got: dict) -> bool:
    """Structure must match exactly; collection SIZES only within a ratio band."""
    return not shape_drift(want, got)


def shape_drift(want: dict, got: dict, may_empty: bool = False) -> str:
    """The reason `want` and `got` differ, or "" when they agree."""
    w, g = dict(want), dict(got)
    wm, gm = w.pop("magnitudes", None), g.pop("magnitudes", None)
    if w != g:
        return "structure changed"
    # A golden frozen before magnitudes existed must not silently pass; verify() gates on
    # ORACLE_VERSION, so reaching here with a missing side means a hand-built shape in a test.
    if wm is None or gm is None:
        return ""
    ok, why = magnitudes_ok(wm, gm, may_empty=may_empty)
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
    """Row count PER TABLE, keyed by ENCLOSING SECTION + column contract.

    The section prefix is load-bearing, not decoration. Keyed by columns alone, the six
    `### <task_type>` shortlists in TASK_SUBAGENT_SELECTION.md share one column contract and
    were summed into a single 21-row bucket — so four of the six routing sections
    `pick_models` consumes (plan, spec, research, review) could be emptied entirely and the
    total, 11, stayed above the collapse threshold. The oracle printed OK while every vendored
    copy silently fell back to the baked-in `_TABLE`. That is the exact class this module
    claims to catch. Headings are volatile-stripped (`### OPENAI (87 models)`) so ordinary
    count churn does not change the key.
    """
    sizes: dict[str, int] = {}
    lines = text.splitlines()
    section = ""
    i = 0
    while i < len(lines) - 1:
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[i])
        if heading:
            section = _strip_volatile(heading.group(2))
        head = re.match(r"^\|(.+?)\|[ \t]*$", lines[i])
        if head and re.match(r"^\|[\s:|-]+\|[ \t]*$", lines[i + 1]):
            cols = "|".join(c.strip().strip("*`") for c in head.group(1).split("|"))
            # The `§ ` sentinel marks a PER-SECTION count, which is judged differently from
            # every other magnitude (emptying only, not proportionally). Inferring the kind
            # from the key text instead misclassified json paths and html payload_bytes as
            # section keys and silently turned their proportional checks off.
            key = f"{SECTION_KEY} {section} :: {cols}" if section else cols
            j = i + 2
            # Stop at the next table's header. Without this, a table not separated by a blank
            # line swallowed its neighbour's header + separator + rows: the count was inflated
            # by 2 + the neighbour's rows AND the neighbour was never keyed, so gutting it was
            # silently green. Live docs are clean today; one renderer change opens the hole.
            while j < len(lines) and lines[j].startswith("|"):
                # Require a REAL separator (>=3 dashes in a cell). `| - | - |` and a row of
                # blank cells both match the loose pattern, which would split a live table in
                # two and freeze the real one at 0 rows — and a collection frozen at 0 is
                # skipped forever by magnitudes_ok.
                if j + 1 < len(lines) and re.match(r"^\|[\s:|-]*-{3,}[\s:|-]*\|[ \t]*$", lines[j + 1]):
                    break
                j += 1
            sizes[key] = sizes.get(key, 0) + (j - i - 2)
            # How many tables share this column contract. Section keys alone tolerate a
            # vanished section (catalog churn); this catches the case where sections are
            # removed WHOLESALE — e.g. 4 of the 6 routing shortlists deleted outright rather
            # than emptied, which would otherwise slip through as 4 tolerated disappearances.
            sizes[f"{cols} :: TABLES"] = sizes.get(f"{cols} :: TABLES", 0) + 1
            # Total rows across every table sharing this contract. Section keys embed the
            # heading, so a cosmetic heading reformat moves all of them at once and — since a
            # vanished key is tolerated — would silently unguard everything beneath it
            # (measured: 57 of 70 keys, 401 rows). This aggregate is heading-independent.
            sizes[f"{cols} :: ROWS"] = sizes.get(f"{cols} :: ROWS", 0) + (j - i - 2)
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
        if isinstance(o, (dict, list)):
            # Size first: the depth cutoff below used to return before recording, so a
            # collection deeper than 3 was unmeasurable. Sizes are cheap; the schema is what
            # needs the depth bound.
            sizes[path] = len(o)
        if depth > 3:
            return "..."
        if isinstance(o, dict):
            return {k: walk(v, depth + 1, f"{path}.{k}") for k, v in sorted(o.items())[:40]}
        if isinstance(o, list):
            return [walk(o[0], depth + 1, f"{path}[]")] if o else []
        return type(o).__name__

    return {"schema": walk(data), "magnitudes": sizes}


def html_shape(text: str) -> dict:
    """Coarse shape for the generated browser page.

    Before `magnitudes` this function could not detect data loss AT ALL: measured, the payload
    blob contains zero `id="` substrings, so blanking all 3.7MB of it left `has_table`,
    `script_blocks`, `id_attrs` and even the literal `<tr` count byte-identical. It detected
    only a template rewrite. `payload_bytes` is the sole honest magnitude here, because the
    models are rendered client-side from that blob rather than from markup.
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
        block = extract_block(text, marker) if text else None
        # SIZE, not a boolean. `extract_block` returns "" for an emptied block, which is
        # `is not None`, so an injector that still writes its START/END fences with nothing
        # between them read as fully intact — 18 of the 46 contract elements (the ROSTER,
        # EMBEDDING_ROSTER, EMBEDDING_CATALOG, EMBEDDING_WINNERS and 14 ai-pack blocks) had
        # no husk protection at all.
        markers[f"{rel}::{marker}"] = -1 if block is None else len(block.strip())
    for host in ai_pack_hosts():
        # errors="replace" mirrors _read: a non-UTF-8 byte in any fleet-synced ai/*.md must
        # report drift, never crash the gate.
        text = host.read_text(encoding="utf-8", errors="replace")
        for marker in AI_PACK_MARKERS:
            block = extract_block(text, marker)
            if block is not None:
                markers[f".windsurf/rules/ai/{host.name}::{marker}"] = len(block.strip())

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
            # shape_drift already computes the PRECISE reason (which collection, what sizes).
            # Calling the boolean shapes_equal here threw that away and printed a generic
            # "SHAPE CHANGED", so an operator could not tell a data collapse from a renderer
            # edit — the single most useful thing the oracle knows.
            why = shape_drift(
                w.get("shape", {}), g.get("shape", {}), may_empty=rel in MAY_EMPTY
            )
            if why:
                drift.append(f"{rel}: {why}")

    # The SQL the live hub consumers issue. snapshot() froze these into both structure.json
    # and db_queries.json, but nothing ever compared them — so WINDOW_DAYS, MIN_RUNS, the
    # HAVING clause or the table name could all change and the oracle stayed green, defeating
    # the module's stated purpose ("read live, so it cannot drift into fiction").
    for key, wq in want.get("db_queries", {}).items():
        gq = got["db_queries"].get(key)
        if gq is None:
            # Phase-E tolerance, scoped to the OWNING MODULE. A global `any(...)` meant one
            # unavailable query suppressed GONE for all 15 — so a genuinely dropped consumer
            # query in a module that is still fully present became invisible whenever any
            # other module happened to be unreadable (including a sibling's mid-edit
            # SyntaxError, since the import guard is `except Exception`).
            family = key.split(".")[0]
            if any(
                "UNAVAILABLE" in str(v)
                for k, v in got["db_queries"].items()
                if k.split(".")[0] == family
            ):
                continue
            drift.append(f"QUERY GONE: {key}")
        elif gq != wq and "UNAVAILABLE" not in str(gq):
            # Test the OBSERVATION, not the golden. Reading `wq` meant the guard could never
            # fire in normal operation (the golden holds real SQL) and, when it did fire,
            # tolerated ANY observed value — baking in a dead check. Reading `gq` is what
            # `_db_queries`' stated Phase-E purpose requires: after the engine is excised the
            # observation degrades to <UNAVAILABLE> and the oracle stays quiet instead of
            # emitting 15 spurious QUERY CHANGED/GONE lines.
            drift.append(f"QUERY CHANGED: {key}")

    for key, want_size in want["markers"].items():
        got_size = got["markers"].get(key, -1)
        if want_size >= 0 and got_size < 0:
            drift.append(f"MARKER NO LONGER INJECTED: {key}")
        elif want_size > 0 and got_size == 0:
            drift.append(f"MARKER EMPTIED (fences still written, payload gone): {key}")
        elif want_size > 0 and got_size < _min_allowed(want_size):
            drift.append(f"MARKER COLLAPSED: {key} — {want_size} -> {got_size} chars")
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
    n = len(want["artifacts"]) + len(want["markers"]) + len(want.get("db_queries", {}))
    print(
        f"[capture_golden] OK — {n} contract elements intact "
        f"({len(want['artifacts'])} artifacts, {len(want['markers'])} markers, "
        f"{len(want.get('db_queries', {}))} queries)"
    )
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
