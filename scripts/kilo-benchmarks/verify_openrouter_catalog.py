#!/usr/bin/env python3
"""Verify every row in kilo_agents.db.agents against the live OpenRouter
catalog. Produce a per-row diff for pricing, context window, capability
flags, and name; flag delisted rows; optionally apply fixes.

Usage:
    python verify_openrouter_catalog.py                # report only
    python verify_openrouter_catalog.py --apply        # write fixes to DB
    python verify_openrouter_catalog.py --json out.json # machine-readable

Live source: https://openrouter.ai/api/v1/models
Fields cross-checked: input_cost_per_m, output_cost_per_m,
context_window_k, has_vision, has_tools, name. Delisted rows (in DB
but absent from live catalog) get status='deprecated' under --apply.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_DATE_SUFFIX_RE = re.compile(r"-20\d{6}$")  # -YYYYMMDD (e.g. -20250805)
_HYPHEN_DIGITS_RE = re.compile(r"(\d)-(\d)")
_DISCOUNTED_SUFFIX = ":discounted"
_STEALTH_PREFIX = "stealth/"

# Provider re-spelling pairs the upstream catalogs use inconsistently.
# Key = canonical (kept), Value = alias that folds onto it. Bidirectional —
# the re-write happens after provider-prefix strip, so 'reka/' and 'rekaai/'
# both reduce to the same bare form via the second-pass alias map.
_PROVIDER_ALIASES = {
    "rekaai": "reka",
}


def _canonicalize_id(model_id: str) -> str:
    """Reduce a model id to a dedup identity key.

    Treated as the SAME model (fold onto the canonical row):
      anthropic/claude-opus-4.6      -> claude-opus-4.6
      claude-opus-4-6                -> claude-opus-4.6   (Kilo bare, hyphen→dot)
      claude-opus-4-1-20250805       -> claude-opus-4.1   (date snapshot)
      claude-opus-4-5-20251101       -> claude-opus-4.5
      stealth/claude-opus-4.6        -> claude-opus-4.6   (pre-launch alpha)
      deepseek-v4-flash:discounted   -> deepseek-v4-flash (only folds when
                                                           parent also in DB)
      reka/reka-edge ↔ rekaai/reka-edge -> reka/reka-edge (provider alias)

    Treated as DIFFERENT models (intentional non-fold):
      anthropic/claude-opus-4.6 vs anthropic/claude-opus-4.6-fast
        (Fast is a 2x pricing tier — separate route)
      kilo-auto/* meta-routers
        (no specific underlying model to fold to)
      openrouter/auto, openrouter/fusion, openrouter/owl-alpha
        (meta-routers — keep separate)
    """
    s = (model_id or "").strip().lower()
    # 1. Strip stealth/ prefix (pre-launch alpha routes)
    if s.startswith(_STEALTH_PREFIX):
        s = s[len(_STEALTH_PREFIX) :]
    # 2. Strip provider prefix + apply provider-alias normalization
    if "/" in s:
        provider, rest = s.split("/", 1)
        provider = _PROVIDER_ALIASES.get(provider, provider)
        s = rest  # discard provider — we only need the model identity
    # 3. Strip :discounted suffix
    if s.endswith(_DISCOUNTED_SUFFIX):
        s = s[: -len(_DISCOUNTED_SUFFIX)]
    # 4. Strip date suffix (-YYYYMMDD)
    s = _DATE_SUFFIX_RE.sub("", s)
    # 5. Normalize hyphen-between-digits → dot ("4-6" → "4.6"). Applies
    #    across the whole string but only between digits, so identifiers
    #    like "gpt-4" stay as "gpt-4" (hyphen between letter+digit).
    s = _HYPHEN_DIGITS_RE.sub(r"\1.\2", s)
    # 6. Strip trailing ".0" — Kilo CLI's "initial release" version suffix
    #    that OR drops. So `claude-opus-4-0` (Kilo) → `claude-opus-4.0`
    #    (step 5) → `claude-opus-4` (this step), matching OR's
    #    `anthropic/claude-opus-4`. No legit model name ends in ".0" today;
    #    revisit if one ever does.
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _today_utc_iso() -> str:
    """UTC date so the verifier never drifts vs export_models_browser
    (which uses datetime.now(UTC) for generated_at). Mixing local-tz
    `date.today()` here with UTC there produced negative day counts
    around midnight UTC, displayed as "-1d" in the browser."""
    return datetime.now(UTC).date().isoformat()


SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
OR_URL = "https://openrouter.ai/api/v1/models"
CACHE_PATH = SCRIPT_DIR / "cache" / "openrouter_live_catalog.json"


def _fetch_live() -> dict[str, dict]:
    """Hit OpenRouter, return id → full record map. Also persists the
    response to cache for inspection."""
    req = urllib.request.Request(OR_URL, headers={"User-Agent": "fabrik-verifier/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, indent=2))
    return {m["id"]: m for m in payload.get("data", [])}


def _live_pricing(record: dict) -> tuple[float, float, bool]:
    """OpenRouter encodes pricing as dollars-per-token strings (e.g.
    '0.000003' = $3 per million). Returns (input_per_m, output_per_m,
    is_variable).

    Sentinel handling: OpenRouter uses `"-1"` (or any negative string)
    to mean "variable / dynamic — depends on which underlying model
    this meta-router selects per request." Applies to openrouter/auto,
    openrouter/fusion, openrouter/pareto-code, openrouter/bodybuilder.
    For these we return (0.0, 0.0, True) — keep the cost columns at 0
    (the `agents.input_cost_per_m` column is NOT NULL) and set the
    is_variable flag so the browser renders "variable" rather than $0
    or a nonsense -$1,000,000."""
    p = record.get("pricing", {}) or {}

    def _parse(field: str) -> tuple[float, bool]:
        raw = p.get(field, 0) or 0
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return 0.0, False
        if val < 0:
            return 0.0, True
        return val * 1_000_000, False

    inp, var_inp = _parse("prompt")
    outp, var_outp = _parse("completion")
    return inp, outp, var_inp or var_outp


def _live_description(record: dict) -> str:
    """OpenRouter's `description` field — full explainer text for the
    model. Already markdown-flavored. Trimmed/cleaned but otherwise
    passed through verbatim."""
    d = record.get("description") or ""
    return d.strip()


def _kilo_description(record: dict) -> str:
    """Kilo CLI nests its description under `options.description`."""
    opts = record.get("options", {}) or {}
    return (opts.get("description") or "").strip()


def _live_caps(record: dict) -> dict[str, int]:
    """Vision flag from architecture.input_modalities; tools from
    supported_parameters."""
    arch = record.get("architecture", {}) or {}
    mods = arch.get("input_modalities", []) or []
    has_vision = 1 if "image" in mods else 0
    params = record.get("supported_parameters", []) or []
    has_tools = 1 if ("tools" in params or "tool_choice" in params) else 0
    return {"has_vision": has_vision, "has_tools": has_tools}


def _fetch_kilo() -> dict[str, dict]:
    """Run `kilo models --verbose` and parse the JSON-per-model output
    that the CLI emits. Returns id → full record map (same shape that
    `kilo_agents_db.py:fetch_kilo_models` extracts)."""
    try:
        result = subprocess.run(
            ["kilo", "models", "--verbose"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[verifier] kilo CLI unavailable ({e}); skipping Kilo cross-check", file=sys.stderr)
        return {}
    lines = result.stdout.split("\n")
    models: dict[str, dict] = {}
    i = 0
    while i < len(lines):
        if lines[i].strip() == "{":
            buf = ["{"]
            depth = 1
            i += 1
            while i < len(lines) and depth > 0:
                buf.append(lines[i])
                depth += lines[i].count("{") - lines[i].count("}")
                i += 1
            try:
                m = json.loads("\n".join(buf))
                if "id" in m:
                    models[m["id"]] = m
            except json.JSONDecodeError:
                pass
        else:
            i += 1
    return models


def _kilo_pricing(record: dict) -> tuple[float, float]:
    """Kilo CLI's `cost` block stores `input`/`output` directly as USD
    per million tokens (already scaled)."""
    cost = record.get("cost", {}) or {}
    try:
        inp = float(cost.get("input", 0) or 0)
    except (TypeError, ValueError):
        inp = 0.0
    try:
        outp = float(cost.get("output", 0) or 0)
    except (TypeError, ValueError):
        outp = 0.0
    return inp, outp


def _approx_eq(a, b, tol=0.005) -> bool:
    """Compare floats with small tolerance — OpenRouter occasionally
    returns prices like '5.999999...e-06' so exact equality is fragile."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def verify(db_path: Path = DB_PATH) -> dict:
    """Cross-check every active row against BOTH the live OpenRouter
    catalog and the Kilo CLI's `kilo models --verbose` output.
    Returns:
    {
      "summary": {...counts...},
      "discrepancies": [...],
      "delisted": [...],             # in DB but absent from BOTH sources
      "live_only": [...],            # missing-from-DB OpenRouter rows
      "kilo_only": [...],            # missing-from-DB Kilo Gateway rows
      "matched_clean": [...],
      "kilo_sourced": {id: {"input": X, "output": Y}},  # via_kilo + prices
      "openrouter_sourced": [id, ...],  # via_openrouter flag set
    }
    """
    live = _fetch_live()
    kilo = _fetch_kilo()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Filter to OpenRouter-routed rows only. Without `via_openrouter=1`, this
    # verifier silently deprecates direct-vendor rows (Soniox, ElevenLabs,
    # AssemblyAI, Coqui, etc.) on every run — they're not in OpenRouter's
    # /api/v1/models response, so they get swept into `delisted[]` below and
    # flipped to status='deprecated' by apply_fixes(). Convergence Pass 6
    # caught this; live measurement showed 186 wrongly-deprecated direct-vendor
    # rows at that time. See docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md.
    db_rows = {
        r["id"]: dict(r)
        for r in conn.execute(
            "SELECT * FROM agents WHERE status='active' AND via_openrouter=1"
        ).fetchall()
    }
    # All-rows set for INSERT-exclusion at line 323-324: live_only/kilo_only
    # must NOT include IDs that already exist in any state (active, deprecated,
    # via_openrouter=0, etc.) or ingest_new() will hit a UNIQUE constraint
    # failure. Pre-2026-06-30 bug: live_only was computed against db_rows
    # (filtered to active+via_openrouter=1), so any DB row that was deprecated
    # OR direct-vendor-flagged but still in OpenRouter's catalog got falsely
    # flagged as "missing" → INSERT failure logged in every daily run.
    all_db_ids = {r[0] for r in conn.execute("SELECT id FROM agents").fetchall()}
    conn.close()

    delisted: list[str] = []
    matched_clean: list[str] = []
    discrepancies: list[dict] = []

    for mid, row in db_rows.items():
        live_rec = live.get(mid)
        if not live_rec:
            delisted.append(mid)
            continue

        live_inp, live_out, live_var = _live_pricing(live_rec)
        live_ctx = (live_rec.get("context_length") or 0) // 1000
        live_caps = _live_caps(live_rec)
        live_name = live_rec.get("name") or ""
        live_desc = _live_description(live_rec)
        # Fall back to Kilo's description when OpenRouter's is empty —
        # some rows have only the Kilo-side text.
        if not live_desc and mid in kilo:
            live_desc = _kilo_description(kilo[mid])

        row_disc: list[dict] = []
        # Skip price discrepancy detection when OpenRouter says the
        # pricing is variable — the DB stores 0 + is_variable_pricing=1,
        # which "differs" from the live 0 but doesn't need a fix.
        if not live_var:
            if not _approx_eq(row.get("input_cost_per_m"), live_inp, tol=0.01):
                row_disc.append(
                    {
                        "field": "input_cost_per_m",
                        "db": row.get("input_cost_per_m"),
                        "live": live_inp,
                    }
                )
            if not _approx_eq(row.get("output_cost_per_m"), live_out, tol=0.01):
                row_disc.append(
                    {
                        "field": "output_cost_per_m",
                        "db": row.get("output_cost_per_m"),
                        "live": live_out,
                    }
                )
        # Detect is_variable_pricing flag drift.
        db_var = bool(row.get("is_variable_pricing") or 0)
        if db_var != live_var:
            row_disc.append(
                {
                    "field": "is_variable_pricing",
                    "db": int(db_var),
                    "live": int(live_var),
                }
            )
        # If pricing IS variable, reset the cost columns to 0 (clear
        # any prior -1,000,000 garbage we wrote).
        if live_var:
            if (row.get("input_cost_per_m") or 0) != 0:
                row_disc.append(
                    {
                        "field": "input_cost_per_m",
                        "db": row.get("input_cost_per_m"),
                        "live": 0.0,
                    }
                )
            if (row.get("output_cost_per_m") or 0) != 0:
                row_disc.append(
                    {
                        "field": "output_cost_per_m",
                        "db": row.get("output_cost_per_m"),
                        "live": 0.0,
                    }
                )
        if row.get("context_window_k") != live_ctx and live_ctx > 0:
            row_disc.append(
                {
                    "field": "context_window_k",
                    "db": row.get("context_window_k"),
                    "live": live_ctx,
                }
            )
        if (row.get("has_vision") or 0) != live_caps["has_vision"]:
            row_disc.append(
                {
                    "field": "has_vision",
                    "db": row.get("has_vision"),
                    "live": live_caps["has_vision"],
                }
            )
        if (row.get("has_tools") or 0) != live_caps["has_tools"]:
            row_disc.append(
                {
                    "field": "has_tools",
                    "db": row.get("has_tools"),
                    "live": live_caps["has_tools"],
                }
            )
        if live_name and row.get("name") != live_name:
            row_disc.append(
                {
                    "field": "name",
                    "db": row.get("name"),
                    "live": live_name,
                }
            )
        # Description is a free-text field — push the live value down
        # whenever it changes (operator never edits these locally).
        if live_desc and (row.get("description") or "") != live_desc:
            row_disc.append(
                {
                    "field": "description",
                    "db": row.get("description"),
                    "live": live_desc,
                }
            )

        if row_disc:
            discrepancies.append({"id": mid, "diffs": row_disc})
        else:
            matched_clean.append(mid)

    # Use all_db_ids (every row regardless of status/flags) — see comment at
    # the db_rows / all_db_ids block above. Using db_rows here would re-fail
    # with UNIQUE constraint in ingest_new() for any row that exists in DB
    # with status='deprecated' or via_openrouter=0 but is still listed live.
    # Full canonical-ID dedup (2026-07-01 generalization of the 2026-06-30
    # bare-vs-prefixed fix). The earlier fix only collapsed exact bare↔prefixed
    # matches: `claude-fable-5` ↔ `anthropic/claude-fable-5`. Live audit found
    # the same model surfacing under SIX patterns that string-equality misses:
    #
    #   1. Provider prefix:     anthropic/claude-opus-4.6
    #   2. Bare ID (Kilo):      claude-opus-4-6              (dot → hyphen)
    #   3. Date snapshot:       claude-opus-4-1-20250805     (-YYYYMMDD)
    #   4. Stealth alpha route: stealth/claude-opus-4.6
    #   5. Discounted suffix:   deepseek-v4-flash:discounted
    #   6. Provider re-spelling: reka/reka-edge ↔ rekaai/reka-edge
    #
    # Patterns 1-4 + 6 are "same model, different listing" and should fold
    # onto the canonical (OR-prefixed) row. Pattern 5 (:discounted) is a
    # tier-pricing variant the UI already handles via the show_discounted
    # toggle — _canonicalize_id strips the suffix so :discounted folds onto
    # its parent only when the parent ALSO exists in DB.
    #
    # NOT canonicalized (intentional):
    #   - `-fast` variants ("claude-opus-4.8-fast") — Anthropic charges 2x
    #     for them; treat as separate routing tiers, not the same row.
    #   - `kilo-auto/*` meta-routers — no specific underlying model to fold to.
    or_canonical_to_full = {_canonicalize_id(mid): mid for mid in live}

    live_only = [mid for mid in live if mid not in all_db_ids]
    # kilo_only after dedup: Kilo CLI ID is "really" Kilo-only only if its
    # canonical key doesn't match any OR row.
    kilo_only = [
        mid
        for mid in kilo
        if mid not in all_db_ids
        and mid not in live
        and _canonicalize_id(mid) not in or_canonical_to_full
    ]

    # Build per-id Kilo Gateway pricing so apply_fixes can populate
    # `kilo_input_cost_per_m` / `kilo_output_cost_per_m` / `via_kilo`.
    # When a Kilo ID's canonical matches an OR canonical, route the Kilo
    # pricing onto the CANONICAL (prefixed) row so the UI sees one
    # dual-routed model, not two split-only rows.
    kilo_sourced: dict[str, dict] = {}
    for mid, rec in kilo.items():
        k_in, k_out = _kilo_pricing(rec)
        canonical_id = or_canonical_to_full.get(_canonicalize_id(mid), mid)
        kilo_sourced[canonical_id] = {"input": k_in, "output": k_out}

    # Recompute delisted: a row is truly delisted only if NEITHER the
    # OpenRouter nor the Kilo CLI catalog returns it AND the DB row is
    # not flagged as reachable via a direct-API gateway (DashScope /
    # SiliconFlow). Without the gateway-flag carve-out we'd nuke
    # operator-seeded specialist routes like qwen-mt-turbo on every run.
    direct_routed = {
        mid
        for mid, row in db_rows.items()
        if (row.get("via_dashscope") or 0) or (row.get("via_siliconflow") or 0)
    }
    truly_delisted = [mid for mid in delisted if mid not in kilo and mid not in direct_routed]
    delisted_or_only = [mid for mid in delisted if mid in kilo]

    # Catalog-dedup duplicates: bucket every DB ID by its canonical key,
    # then for any bucket with 2+ IDs, mark the non-canonical members as
    # `status='deprecated'`. The canonical choice priority:
    #   1. The OR-prefixed live ID for that canonical key (if any)
    #   2. The longest non-stealth/ DB ID (Anthropic's dotted form beats
    #      Kilo's hyphenated form when neither is in OR's live catalog)
    #   3. The longest ID overall (last-resort tiebreaker)
    # The earlier (2026-06-30) version of this only detected bare↔prefixed
    # 1:1 dupes via dict lookup; now we group across every canonicalization
    # rule (hyphen-vs-dot, date suffix, stealth/, discounted, provider
    # re-spelling like reka/ ↔ rekaai/).
    canonical_groups: dict[str, list[str]] = {}
    for mid in all_db_ids:
        canonical_groups.setdefault(_canonicalize_id(mid), []).append(mid)

    catalog_dupes: list[str] = []
    for canonical_key, ids in canonical_groups.items():
        if len(ids) < 2:
            continue
        # Preferred canonical row for this bucket
        canonical_id = or_canonical_to_full.get(canonical_key)
        if not canonical_id:
            non_stealth = [i for i in ids if not i.startswith("stealth/")]
            canonical_id = max(non_stealth or ids, key=len)
        # Everything else in the bucket is a dup to deprecate
        for mid in ids:
            if mid != canonical_id:
                catalog_dupes.append(mid)

    return {
        "summary": {
            "db_active": len(db_rows),
            "live_total": len(live),
            "kilo_total": len(kilo),
            "in_both_sources": len(set(live) & set(kilo)),
            "matched_clean": len(matched_clean),
            "matched_with_discrepancy": len(discrepancies),
            "delisted_in_db_only": len(truly_delisted),
            "or_delisted_but_kilo_has": len(delisted_or_only),
            "missing_from_db_or": len(live_only),
            "missing_from_db_kilo_only": len(kilo_only),
        },
        "discrepancies": discrepancies,
        "delisted": truly_delisted,
        "or_delisted_kilo_only": delisted_or_only,
        "live_only": live_only,
        "kilo_only": kilo_only,
        "matched_clean": matched_clean,
        "kilo_sourced": kilo_sourced,
        "openrouter_sourced": list(live.keys()),
        "catalog_dupes": catalog_dupes,
    }


def ingest_new(report: dict, db_path: Path = DB_PATH) -> dict:
    """Pull rows that are in OpenRouter or Kilo CLI but missing from
    our DB. Tags each new row with via_openrouter / via_kilo + the
    Kilo Gateway price if it differs from OpenRouter."""
    live = json.loads(CACHE_PATH.read_text())
    live_by_id = {m["id"]: m for m in live.get("data", [])}
    kilo_by_id = _fetch_kilo()
    today_iso = _today_utc_iso()
    inserted_or = 0
    inserted_kilo = 0

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        for mid in report["live_only"]:
            rec = live_by_id.get(mid)
            if not rec:
                continue
            provider = mid.split("/")[0] if "/" in mid else mid
            inp, outp, is_var = _live_pricing(rec)
            ctx = (rec.get("context_length") or 0) // 1000
            caps = _live_caps(rec)
            also_kilo = 1 if mid in kilo_by_id else 0
            k_in, k_out = (None, None)
            if also_kilo:
                k_in, k_out = _kilo_pricing(kilo_by_id[mid])
            desc = _live_description(rec)
            if not desc and also_kilo:
                desc = _kilo_description(kilo_by_id[mid])
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "has_vision, has_tools, status, last_verified, "
                "via_openrouter, via_kilo, kilo_input_cost_per_m, kilo_output_cost_per_m, "
                "is_variable_pricing, description) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 1, ?, ?, ?, ?, ?)",
                (
                    mid,
                    mid,
                    rec.get("name") or mid,
                    provider,
                    inp,
                    outp,
                    ctx,
                    caps["has_vision"],
                    caps["has_tools"],
                    today_iso,
                    also_kilo,
                    k_in,
                    k_out,
                    1 if is_var else 0,
                    desc,
                ),
            )
            inserted_or += 1

        # Kilo-only rows: ID exists in Kilo CLI but NOT in OpenRouter.
        # Kilo Gateway aliases like kilo-auto/*, stealth/*, :discounted.
        for mid in report.get("kilo_only", []):
            rec = kilo_by_id.get(mid)
            if not rec:
                continue
            provider = mid.split("/")[0] if "/" in mid else mid
            k_in, k_out = _kilo_pricing(rec)
            ctx_raw = (rec.get("limit", {}) or {}).get("context") or 0
            ctx = int(ctx_raw) // 1000 if isinstance(ctx_raw, (int, float)) else 0
            caps = rec.get("capabilities", {}) or {}
            has_vision = 1 if (caps.get("input", {}) or {}).get("image") else 0
            has_tools = 1 if caps.get("toolcall") else 0
            has_reasoning = 1 if caps.get("reasoning") else 0
            desc = _kilo_description(rec)
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "has_vision, has_tools, has_reasoning, status, last_verified, "
                "via_openrouter, via_kilo, kilo_input_cost_per_m, kilo_output_cost_per_m, "
                "description) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0, 1, ?, ?, ?)",
                (
                    mid,
                    mid,
                    rec.get("name") or mid,
                    provider,
                    k_in,
                    k_out,
                    ctx,
                    has_vision,
                    has_tools,
                    has_reasoning,
                    today_iso,
                    k_in,
                    k_out,
                    desc,
                ),
            )
            inserted_kilo += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"inserted_openrouter": inserted_or, "inserted_kilo_only": inserted_kilo}


def apply_fixes(report: dict, db_path: Path = DB_PATH) -> dict:
    """For each discrepancy, UPDATE the DB column to live value.
    Delisted rows get status='deprecated'. Returns counts."""
    conn = sqlite3.connect(db_path)
    today_iso = _today_utc_iso()
    counts = {"rows_updated": 0, "rows_deprecated": 0, "fields_updated": 0}

    try:
        conn.execute("BEGIN")
        for entry in report["discrepancies"]:
            mid = entry["id"]
            for diff in entry["diffs"]:
                conn.execute(
                    f"UPDATE agents SET {diff['field']} = ?, last_verified = ? WHERE id = ?",
                    (diff["live"], today_iso, mid),
                )
                counts["fields_updated"] += 1
            counts["rows_updated"] += 1

        for mid in report["delisted"]:
            conn.execute(
                "UPDATE agents SET status = 'deprecated', "
                "discard_reason = COALESCE(discard_reason, 'delisted by OpenRouter (verifier)'), "
                "last_verified = ? WHERE id = ?",
                (today_iso, mid),
            )
            counts["rows_deprecated"] += 1
        # Bump last_verified for cleanly-matching rows too — we DID verify
        # them against the live catalog today, the columns just didn't
        # need to change. Without this, downstream consumers might still
        # mark them stale.
        if report.get("matched_clean"):
            placeholders = ",".join("?" * len(report["matched_clean"]))
            conn.execute(
                f"UPDATE agents SET last_verified = ? WHERE id IN ({placeholders})",
                (today_iso, *report["matched_clean"]),
            )
            counts["rows_clean_touched"] = len(report["matched_clean"])

        # Source attribution: stamp via_openrouter on every DB row that
        # OpenRouter currently returns, via_kilo on every row Kilo CLI
        # returns. Both can be true for dual-routed models. Also store
        # the Kilo Gateway price so the browser can show both rates
        # side-by-side when they differ.
        or_ids = report.get("openrouter_sourced", [])
        if or_ids:
            placeholders = ",".join("?" * len(or_ids))
            conn.execute(
                f"UPDATE agents SET via_openrouter = 1 WHERE id IN ({placeholders})",
                or_ids,
            )
            # And reset any rows OpenRouter no longer returns
            conn.execute(
                f"UPDATE agents SET via_openrouter = 0 WHERE id NOT IN ({placeholders})",
                or_ids,
            )

        kilo_sourced = report.get("kilo_sourced", {}) or {}
        if kilo_sourced:
            for mid, prices in kilo_sourced.items():
                conn.execute(
                    "UPDATE agents SET via_kilo = 1, "
                    "kilo_input_cost_per_m = ?, "
                    "kilo_output_cost_per_m = ? "
                    "WHERE id = ?",
                    (prices["input"], prices["output"], mid),
                )
            # Rows Kilo CLI no longer returns: clear via_kilo
            placeholders = ",".join("?" * len(kilo_sourced))
            conn.execute(
                f"UPDATE agents SET via_kilo = 0, kilo_input_cost_per_m = NULL, "
                f"kilo_output_cost_per_m = NULL WHERE id NOT IN ({placeholders})",
                list(kilo_sourced.keys()),
            )
            counts["kilo_sourced_tagged"] = len(kilo_sourced)

        # Push Kilo CLI descriptions onto Kilo-only rows whose
        # description column is empty (OpenRouter never describes
        # them so they'd otherwise stay NULL forever).
        kilo_descs_written = 0
        kilo_raw = _fetch_kilo()
        for mid, rec in kilo_raw.items():
            desc = _kilo_description(rec)
            if not desc:
                continue
            cur = conn.execute(
                "UPDATE agents SET description = ? "
                "WHERE id = ? AND (description IS NULL OR description = '')",
                (desc, mid),
            )
            if cur.rowcount:
                kilo_descs_written += cur.rowcount
        counts["kilo_descriptions_written"] = kilo_descs_written

        # Catalog-dedup cleanup: mark Kilo-bare duplicate rows as deprecated
        # so the UI's Kilo-only chip stops showing them as exclusive routes.
        # Their canonical (provider-prefixed) sibling already carries
        # via_kilo=1 via the kilo_sourced normalization above. Status='deprecated'
        # rather than DELETE so historical rows persist for audit.
        catalog_dupes = report.get("catalog_dupes", []) or []
        if catalog_dupes:
            placeholders = ",".join("?" * len(catalog_dupes))
            cur = conn.execute(
                f"UPDATE agents SET status = 'deprecated' "
                f"WHERE id IN ({placeholders}) AND status != 'deprecated'",
                catalog_dupes,
            )
            counts["catalog_dupes_deprecated"] = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def _print_report(report: dict, verbose: bool = False) -> None:
    s = report["summary"]
    print("=" * 70)
    print(f"  Source coverage @ {_today_utc_iso()}")
    print("=" * 70)
    print(f"  OpenRouter total:              {s['live_total']:>4}")
    print(f"  Kilo CLI total:                {s['kilo_total']:>4}")
    print(f"  In BOTH sources (same id):     {s['in_both_sources']:>4}")
    print(f"  Kilo-only (Gateway aliases):   {s['missing_from_db_kilo_only']:>4}")
    print(f"  OpenRouter-only:               {s['missing_from_db_or']:>4}")
    print()
    print("=" * 70)
    print(f"  OpenRouter catalog verification @ {_today_utc_iso()}")
    print("=" * 70)
    print(f"  DB active rows:                {s['db_active']:>4}")
    print(f"  Live OpenRouter rows:          {s['live_total']:>4}")
    print(f"  ✓  matched cleanly:            {s['matched_clean']:>4}")
    print(f"  ~  matched w/ discrepancy:     {s['matched_with_discrepancy']:>4}")
    print(f"  ⚠  delisted in DB only:        {s['delisted_in_db_only']:>4}")
    print(f"  +  in OpenRouter, not in DB:   {s['missing_from_db_or']:>4}")
    print(f"  +  in Kilo only, not in DB:    {s['missing_from_db_kilo_only']:>4}")
    print()
    if report["discrepancies"]:
        print(f"=== Discrepancies (top {min(40, len(report['discrepancies']))}) ===")
        for entry in report["discrepancies"][:40]:
            print(f"\n  {entry['id']}")
            for d in entry["diffs"]:
                f = d["field"]
                db, live = d["db"], d["live"]
                if isinstance(db, float) or isinstance(live, float):
                    print(f"    {f:<25} DB={db}  LIVE={live}")
                else:
                    print(f"    {f:<25} DB={db!r}  LIVE={live!r}")
    if report["delisted"]:
        print()
        print(f"=== Delisted (top 20 of {len(report['delisted'])}) ===")
        for mid in report["delisted"][:20]:
            print(f"  - {mid}")
    if verbose and report["live_only"]:
        print()
        print(f"=== Missing from DB (top 20 of {len(report['live_only'])}) ===")
        for mid in report["live_only"][:20]:
            print(f"  + {mid}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--apply", action="store_true", help="apply fixes to DB")
    p.add_argument(
        "--ingest-new",
        action="store_true",
        help="INSERT rows present in OpenRouter but missing from DB",
    )
    p.add_argument("--json", type=Path, help="write full report as JSON")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} does not exist.", file=sys.stderr)
        sys.exit(1)

    report = verify(args.db)
    _print_report(report, verbose=args.verbose)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nFull report written to {args.json}")

    if args.apply:
        print()
        print("Applying fixes...")
        counts = apply_fixes(report, args.db)
        print(f"  fields updated:  {counts['fields_updated']}")
        print(f"  rows updated:    {counts['rows_updated']}")
        print(f"  rows deprecated: {counts['rows_deprecated']}")
        if counts.get("catalog_dupes_deprecated"):
            print(f"  catalog dupes deprecated: {counts['catalog_dupes_deprecated']}")

    if args.ingest_new:
        print()
        print("Ingesting new rows from OpenRouter...")
        c = ingest_new(report, args.db)
        # ingest_new() returns {'inserted_openrouter': N, 'inserted_kilo_only': M}
        # (see line 473). The previous code referenced c['inserted'] which never
        # existed — was masked by the UNIQUE constraint error that fired BEFORE
        # this print line could execute (pre-2026-06-30 fix at db_rows/all_db_ids).
        print(f"  rows inserted (OpenRouter):  {c['inserted_openrouter']}")
        print(f"  rows inserted (Kilo-only):   {c['inserted_kilo_only']}")


if __name__ == "__main__":
    main()
