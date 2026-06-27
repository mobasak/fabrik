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
DEFAULT_SWE_AGENT = "Verified"  # the most-populated leaderboard

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

# Strip leaderboard prefixes/suffixes that aren't in OpenRouter IDs.
PREFIX_RE = re.compile(
    r"^(?:mini-swe-agent\s*\+\s*|"
    r"|agentless\s*\+\s*|"
    r"|moatless\s*\+\s*|"
    r"|swe-rex\s*\+\s*|"
    r"|swe-agent\s*\+\s*)",
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


def _fetch_swe() -> list[dict]:
    """Return list of {name, resolved_pct, instance_cost, date} for the
    most-populated SWE-bench Verified agent."""
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
    # data is a list of leaderboard groups
    target = next((g for g in data if g.get("name") == DEFAULT_SWE_AGENT), None)
    if not target:
        raise RuntimeError(f"SWE-bench group {DEFAULT_SWE_AGENT!r} not found")
    out = []
    for r in target.get("results", []):
        details = r.get("per_instance_details") or {}
        if not details:
            continue
        n_total = len(details)
        n_solved = sum(1 for d in details.values() if d.get("resolved"))
        out.append(
            {
                "name": r.get("name") or "",
                "resolved_pct": n_solved / n_total * 100,
                "n_total": n_total,
                "instance_cost": r.get("instance_cost"),
                "date": r.get("date"),
            }
        )
    return out


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
    swe: list[dict],
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

    # SWE-bench rows
    swe_updates: list[tuple[float, str]] = []
    for r in swe:
        aid = _match_id(canon_idx, r["name"])
        if aid:
            swe_updates.append((r["resolved_pct"], aid))
            counts["swe_matched"] += 1
        else:
            counts["swe_unmatched"] += 1
            if len(swe_unmatched) < 20:
                swe_unmatched.append(f"{r['name']:<55} ({r['resolved_pct']:.1f}%)")

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

    _log(f"SWE-bench:        matched={counts['swe_matched']} unmatched={counts['swe_unmatched']}")
    _log(
        f"Aider Polyglot:   matched={counts['aider_matched']} unmatched={counts['aider_unmatched']}"
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
        swe = _fetch_swe()
        _log(f"  SWE-bench Verified: {len(swe)} model entries")
    except Exception as e:
        _log(f"  SWE-bench fetch failed (non-fatal): {e}")
        swe = []
    try:
        aider = _fetch_aider()
        _log(f"  Aider Polyglot:     {len(aider)} model entries")
    except Exception as e:
        _log(f"  Aider fetch failed (non-fatal): {e}")
        aider = []
    da_coding = _extract_design_arena_coding()
    _log(f"  design_arena coding: {len(da_coding)} model entries (from OR cache)")

    counts = _match_and_update(args.db, swe, aider, da_coding, dry_run=args.dry_run)
    print()
    _log(
        f"Done. matched: SWE={counts['swe_matched']} · "
        f"Aider={counts['aider_matched']} · "
        f"design_arena_coding={counts['design_arena_coding_matched']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
