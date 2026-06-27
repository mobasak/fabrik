#!/usr/bin/env python3
"""Scrape three public coding leaderboards and join into kilo_agents.db.

No inference cost — we just read what other people already ran.

Sources:
  1. SWE-bench Verified (swebench.com)
       180 entries on the Verified board, default Agent: mini-SWE-agent v2.
       resolved% computed from per-instance details (count `resolved: true` /
       total instances). Lands in agents.swe_bench_verified_pct.
  2. Aider Polyglot leaderboard (aider.chat)
       69 entries, pass_rate_2 = % of 225 multi-language problems solved.
       Lands in agents.aider_polyglot_pct.
  3. OpenRouter design_arena coding categories (already in cache)
       Per-model mean ELO across {codecategories, fullstack, webapps,
       mobileapps, androidnative, godotgamedev, agenticgamedev,
       agentichtmlslides, htmlslides, svg, uicomponent, website, dataviz,
       gamedev, 3d}. Lands in agents.design_arena_coding_elo.

Each leaderboard names models differently from our `agents.id`. The
join uses a permissive canonical-name match: strip parens/reasoning
suffixes, normalize alphanum+hyphen, match against id + name +
canonical_slug. Unmatched models are reported but not an error.

Usage:
    python scrape_coding_benchmarks.py            # scrape + update DB
    python scrape_coding_benchmarks.py --dry-run  # show matches only
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "cache"
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
OR_CACHE = CACHE_DIR / "openrouter_live_catalog.json"

SWE_URL = "https://www.swebench.com/index.html"
AIDER_YAML = "https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml"

# SWE-bench leaderboard groups we mine. Each group runs the same 500-issue
# benchmark with different agent harnesses, so the same model appears
# across groups with slightly different scores — we take the max per
# model. Multilingual is a separate 300-issue board with newer-model
# coverage; tracked in its own column.
SWE_PRIMARY_GROUPS = ("Verified", "bash-only")  # combined for swe_bench_verified_pct
SWE_MULTILINGUAL_GROUP = "Multilingual"  # separate column

CODING_DESIGN_ARENA_CATS = {
    "codecategories",
    "fullstack",
    "webapps",
    "mobileapps",
    "androidnative",
    "godotgamedev",
    "agenticgamedev",
    "agentichtmlslides",
    "htmlslides",
    "svg",
    "uicomponent",
    "website",
    "dataviz",
    "gamedev",
    "3d",
}

UA = "fabrik-benchmark-scraper/1.0"


def _log(msg: str) -> None:
    print(f"[scrape_coding] {msg}")


# ---------------- canonical name helpers ----------------

# Strip leaderboard agent-harness prefixes that aren't in OpenRouter IDs.
# SWE-bench Verified entries are named like "mini-SWE-agent + Claude 4.5 Opus"
# or "Sonar Foundation Agent + Claude 4.5 Opus" etc. Need to strip the
# harness so we can canon the model name.
PREFIX_RE = re.compile(
    r"^(?:"
    r"mini-swe-agent\s*\+\s*|"
    r"live-swe-agent\s*\+\s*|"
    r"live-mini-swe-agent\s*\+\s*|"
    r"swe-agent\s*\+\s*|"
    r"swe-rex\s*\+\s*|"
    r"agentless\s*\+\s*|"
    r"moatless\s*\+\s*|"
    r"sonar\s+foundation\s+agent\s*\+\s*|"
    r"trae\s*\+\s*|"
    r"atlassian\s+rovo\s+dev[\s\(\d-]*\)?\s*\+?\s*|"
    r"epam\s+ai/run\s+developer\s+agent[\s\w\d-]*\+\s*|"
    r"joycode\s*\+\s*|"
    r"refact\.ai\s+agent\s*\+\s*|"
    r"prometheus-v[\d\.]+\s*\+\s*|"
    r"lingxi-v[\d\.]+_+|"
    r"harness\s+ai|"
    r"acoder|"
    r"warp"
    r")",
    re.IGNORECASE,
)
NOISE_SUFFIX_RE = re.compile(
    r"\s*\((?:high|medium|low|default[\s\w]*|with fallback|"
    r"\d+k[\s\w]*think[\s\w]*|non-reasoning|thinking|reasoning|"
    r"\d{8}|maverick|preview-\d{2}-\d{2}|\d{4}-\d{2}-\d{2})\)\s*",
    re.IGNORECASE,
)
# Trailing date stamps without parens: "claude-3-5-sonnet-20241022"
DATE_SUFFIX_RE = re.compile(r"-\d{8}(?:-[a-z]+)?$|-20\d{2}-\d{2}-\d{2}$|-202\d{5}$")


def canon_basic(s: str) -> str:
    """Lowercase, drop parens, drop noise tokens, alphanum-hyphen."""
    s = (s or "").strip()
    s = PREFIX_RE.sub("", s)
    s = NOISE_SUFFIX_RE.sub("", s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)  # drop any remaining parens
    s = re.sub(r"\b(preview|exp|alpha|beta|rc\d*|it|2025-\d{2}-\d{2})\b", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = DATE_SUFFIX_RE.sub("", s)
    return s


def canon_variants(s: str) -> list[str]:
    """Return multiple canonical forms to match word-order variants.
    "Claude 4.5 Opus" → {claude-4-5-opus, claude-opus-4-5, claude-opus-4.5}.
    """
    base = canon_basic(s)
    if not base:
        return []
    tokens = base.split("-")
    variants = {base}
    # Also try sorting tokens by length (model-family typically goes
    # word-then-version OR version-then-word — try both)
    if len(tokens) >= 3:
        # try reversing the model-version word order
        # e.g. claude-4-5-opus → claude-opus-4-5
        # heuristic: if there's a numeric token, move it after the next word
        for i, t in enumerate(tokens):
            if re.match(r"^\d", t) and i + 1 < len(tokens):
                swapped = tokens[:i] + [tokens[i + 1], t] + tokens[i + 2 :]
                variants.add("-".join(swapped))
                # also try moving all leading numbers to the end
                non_nums = [x for x in tokens if not re.match(r"^\d", x)]
                nums = [x for x in tokens if re.match(r"^\d", x)]
                variants.add("-".join(non_nums + nums))
                break
        # Try sorting non-numeric tokens alphabetically then appending numeric
        non_nums = [x for x in tokens if not re.match(r"^\d", x)]
        nums = [x for x in tokens if re.match(r"^\d", x)]
        variants.add("-".join(sorted(non_nums) + nums))
    # Also try without leading "claude-"/"gpt-" since DB has those as
    # provider prefixes only
    variants.add(base)
    return list(variants)


def _build_canon_index(rows: list[dict]) -> dict[str, str]:
    """Return canonical_variant → agent_id for matching."""
    index: dict[str, str] = {}
    for r in rows:
        aid = r["id"]
        for variant in (r.get("id"), r.get("name"), r.get("api_id")):
            if not variant:
                continue
            for c in canon_variants(variant):
                if c and c not in index:
                    index[c] = aid
            # Also strip provider prefix and try those variants
            stripped = variant.split("/", 1)[-1] if "/" in variant else variant
            for c in canon_variants(stripped):
                if c and c not in index:
                    index[c] = aid
    return index


def _match_id(canon_idx: dict[str, str], name: str) -> str | None:
    for c in canon_variants(name):
        if c in canon_idx:
            return canon_idx[c]
    return None


# ---------------- 1. SWE-bench Verified ----------------


def _resolve_pct(r: dict) -> float | None:
    """Extract a resolved % from a SWE-bench result row, preferring
    per_instance_details when available (more authoritative — same
    issue set across rows) and falling back to the top-level `resolved`
    field used by the 140 Verified rows without per-instance data."""
    details = r.get("per_instance_details") or {}
    if details:
        n_total = len(details)
        if not n_total:
            return None
        n_solved = sum(1 for d in details.values() if d.get("resolved"))
        return n_solved / n_total * 100
    # Aggregate field — already a percent in the API.
    agg = r.get("resolved")
    if isinstance(agg, (int, float)):
        return float(agg)
    return None


def _fetch_swe() -> tuple[list[dict], list[dict]]:
    """Return (primary_results, multilingual_results) tuple.

    primary = union of Verified + bash-only — both run the same 500-issue
              SWE-bench Verified problem set with different agent
              harnesses. Same model often appears in multiple rows;
              we keep them all and de-dupe per canonical name later.
    multilingual = the 300-issue SWE-bench Multilingual board, tracked
                   in its own column. Newer-model coverage is best here.
    """
    req = urllib.request.Request(SWE_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    m = re.search(
        r'<script[^>]*id=["\']leaderboard-data["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("SWE-bench leaderboard-data <script> not found — page layout changed?")
    data = json.loads(m.group(1))

    by_name = {g.get("name"): g for g in data}
    primary: list[dict] = []
    for group_name in SWE_PRIMARY_GROUPS:
        g = by_name.get(group_name)
        if not g:
            continue
        for r in g.get("results", []):
            pct = _resolve_pct(r)
            if pct is None:
                continue
            primary.append(
                {
                    "name": r.get("name") or "",
                    "resolved_pct": pct,
                    "group": group_name,
                    "date": r.get("date"),
                }
            )
    multilingual: list[dict] = []
    g = by_name.get(SWE_MULTILINGUAL_GROUP)
    if g:
        for r in g.get("results", []):
            pct = _resolve_pct(r)
            if pct is None:
                continue
            multilingual.append(
                {
                    "name": r.get("name") or "",
                    "resolved_pct": pct,
                    "date": r.get("date"),
                }
            )
    return primary, multilingual


# ---------------- 2. Aider Polyglot ----------------


def _fetch_aider() -> list[dict]:
    req = urllib.request.Request(AIDER_YAML, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    rows = yaml.safe_load(raw) or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pct = r.get("pass_rate_2")
        if not isinstance(pct, (int, float)):
            continue
        out.append(
            {
                "name": r.get("model") or "",
                "pass_rate_2": float(pct),
                "edit_format": r.get("edit_format"),
                "date": r.get("date"),
                "total_cost": r.get("total_cost"),
            }
        )
    return out


# ---------------- 3. design_arena coding extraction (zero new fetch) ----------------


def _extract_design_arena_coding() -> dict[str, float]:
    """Mean ELO across coding-only design_arena categories, per OR id.
    Reads the OpenRouter catalog cache that the verifier already wrote."""
    if not OR_CACHE.exists():
        _log(f"WARN: {OR_CACHE} missing — run verify_openrouter_catalog.py first")
        return {}
    cache = json.loads(OR_CACHE.read_text())
    out: dict[str, float] = {}
    for m in cache.get("data", []):
        elos = []
        for r in (m.get("benchmarks") or {}).get("design_arena") or []:
            if r.get("category") in CODING_DESIGN_ARENA_CATS:
                elo = r.get("elo")
                if isinstance(elo, (int, float)):
                    elos.append(elo)
        if elos:
            out[m["id"]] = sum(elos) / len(elos)
    return out


# ---------------- match + update ----------------


def _match_and_update(
    db_path: Path,
    swe_primary: list[dict],
    swe_multi: list[dict],
    aider: list[dict],
    da_coding: dict[str, float],
    dry_run: bool = False,
) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    agents = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]
    canon_idx = _build_canon_index(agents)

    counts = {
        "swe_matched": 0,
        "swe_unmatched": 0,
        "aider_matched": 0,
        "aider_unmatched": 0,
        "design_arena_coding_matched": 0,
    }
    swe_unmatched: list[str] = []
    aider_unmatched: list[str] = []

    # SWE-bench rows — primary groups, take MAX per matched id (same
    # model often appears in multiple agent harnesses).
    swe_by_id: dict[str, float] = {}
    for r in swe_primary:
        aid = _match_id(canon_idx, r["name"])
        if aid:
            cur = swe_by_id.get(aid, -1)
            if r["resolved_pct"] > cur:
                swe_by_id[aid] = r["resolved_pct"]
            counts["swe_matched"] += 1
        else:
            counts["swe_unmatched"] += 1
            if len(swe_unmatched) < 20:
                swe_unmatched.append(f"{r['name']:<55} ({r['resolved_pct']:.1f}%)")
    swe_updates: list[tuple[float, str]] = [(pct, aid) for aid, pct in swe_by_id.items()]

    # SWE-bench Multilingual — separate column
    swe_ml_by_id: dict[str, float] = {}
    for r in swe_multi:
        aid = _match_id(canon_idx, r["name"])
        if aid:
            cur = swe_ml_by_id.get(aid, -1)
            if r["resolved_pct"] > cur:
                swe_ml_by_id[aid] = r["resolved_pct"]
            counts["swe_multilingual_matched"] = counts.get("swe_multilingual_matched", 0) + 1
        else:
            counts["swe_multilingual_unmatched"] = counts.get("swe_multilingual_unmatched", 0) + 1
    swe_ml_updates: list[tuple[float, str]] = [(pct, aid) for aid, pct in swe_ml_by_id.items()]

    # Aider rows
    aider_updates: list[tuple[float, str]] = []
    for r in aider:
        aid = _match_id(canon_idx, r["name"])
        if aid:
            aider_updates.append((r["pass_rate_2"], aid))
            counts["aider_matched"] += 1
        else:
            counts["aider_unmatched"] += 1
            if len(aider_unmatched) < 20:
                aider_unmatched.append(f"{r['name']:<55} ({r['pass_rate_2']:.1f}%)")

    # design_arena coding scores (already keyed by id)
    da_updates = list(da_coding.items())
    counts["design_arena_coding_matched"] = len(da_updates)
    counts["swe_unique_models"] = len(swe_by_id)
    counts["swe_multilingual_unique"] = len(swe_ml_by_id)

    _log(
        f"SWE-bench primary: rows={counts['swe_matched']} unique={counts['swe_unique_models']} unmatched={counts['swe_unmatched']}"
    )
    _log(f"SWE-bench multilingual: unique={counts['swe_multilingual_unique']}")
    _log(
        f"Aider Polyglot:    matched={counts['aider_matched']} unmatched={counts['aider_unmatched']}"
    )
    _log(f"design_arena coding: matched={counts['design_arena_coding_matched']}")
    if swe_unmatched and dry_run:
        _log("  SWE unmatched sample:")
        for u in swe_unmatched[:10]:
            print(f"    {u}")
    if aider_unmatched and dry_run:
        _log("  Aider unmatched sample:")
        for u in aider_unmatched[:10]:
            print(f"    {u}")

    if dry_run:
        conn.close()
        return counts

    try:
        conn.execute("BEGIN")
        for pct, aid in swe_updates:
            conn.execute(
                "UPDATE agents SET swe_bench_verified_pct = ? WHERE id = ?",
                (pct, aid),
            )
        for pct, aid in swe_ml_updates:
            conn.execute(
                "UPDATE agents SET swe_bench_multilingual_pct = ? WHERE id = ?",
                (pct, aid),
            )
        for pct, aid in aider_updates:
            conn.execute(
                "UPDATE agents SET aider_polyglot_pct = ? WHERE id = ?",
                (pct, aid),
            )
        for aid, elo in da_updates:
            conn.execute(
                "UPDATE agents SET design_arena_coding_elo = ? WHERE id = ?",
                (elo, aid),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    _log(f"=== Coding benchmarks scrape @ {datetime.now(UTC).isoformat()} ===")
    try:
        swe_primary, swe_multi = _fetch_swe()
        _log(f"  SWE-bench primary: {len(swe_primary)} rows (Verified + bash-only)")
        _log(f"  SWE-bench Multilingual: {len(swe_multi)} rows")
    except Exception as e:
        _log(f"  SWE-bench fetch failed (non-fatal): {e}")
        swe_primary, swe_multi = [], []
    try:
        aider = _fetch_aider()
        _log(f"  Aider Polyglot:     {len(aider)} model entries")
    except Exception as e:
        _log(f"  Aider fetch failed (non-fatal): {e}")
        aider = []
    da_coding = _extract_design_arena_coding()
    _log(f"  design_arena coding: {len(da_coding)} model entries (from OR cache)")

    counts = _match_and_update(
        args.db, swe_primary, swe_multi, aider, da_coding, dry_run=args.dry_run
    )
    print()
    _log(
        f"Done. matched: SWE={counts['swe_matched']} · "
        f"Aider={counts['aider_matched']} · "
        f"design_arena_coding={counts['design_arena_coding_matched']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
