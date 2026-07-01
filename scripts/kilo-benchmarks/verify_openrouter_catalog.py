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
    supported_parameters. has_reasoning is derived from OR's `reasoning`
    block when present (more accurate than inference)."""
    arch = record.get("architecture", {}) or {}
    mods = arch.get("input_modalities", []) or []
    has_vision = 1 if "image" in mods else 0
    params = record.get("supported_parameters", []) or []
    has_tools = 1 if ("tools" in params or "tool_choice" in params) else 0
    # has_reasoning: OR-authoritative when the `reasoning` block exists
    # (mandatory OR supports configurable efforts). Pre-fix the verifier
    # heuristically inferred from family / weighted_coding / etc.
    reasoning = record.get("reasoning") or {}
    has_reasoning = 1 if (reasoning.get("mandatory") or reasoning.get("supported_efforts")) else 0
    return {"has_vision": has_vision, "has_tools": has_tools, "has_reasoning": has_reasoning}


def _live_caching(record: dict) -> tuple[float | None, float | None]:
    """Extract prompt-caching pricing from OR's `pricing.input_cache_read` /
    `pricing.input_cache_write`. Same scale as `prompt` / `completion`
    (per-token USD strings). Returns (read_per_m, write_per_m) as floats,
    or (None, None) if the field is absent.

    Production cost impact: caching cuts real cost 5-10x for repeat
    prompts; surfacing it lets operators reason about per-call vs
    sustained-load economics.
    """
    p = record.get("pricing", {}) or {}

    def _parse(field: str) -> float | None:
        raw = p.get(field)
        if raw is None:
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return None
        if val < 0:
            return None
        return val * 1_000_000

    return _parse("input_cache_read"), _parse("input_cache_write")


def _live_reasoning_efforts(record: dict) -> tuple[int, str | None]:
    """Extract OR's reasoning metadata: (mandatory, supported_efforts_json).

    `mandatory` = 1 if the model REQUIRES reasoning (cannot disable
    thinking — affects first-token latency expectations).
    `supported_efforts` = JSON list of effort levels (e.g. "low", "medium",
    "high"), or None if the model doesn't expose configurable efforts.
    """
    r = record.get("reasoning") or {}
    mandatory = 1 if r.get("mandatory") else 0
    efforts = r.get("supported_efforts")
    efforts_json = json.dumps(efforts) if efforts else None
    return mandatory, efforts_json


def _live_top_provider(record: dict) -> tuple[int | None, int | None, int]:
    """Pull (context_length, max_completion_tokens, is_moderated) from
    `top_provider`. The provider-side context_length is often LOWER than
    the model's stated max — surface both so the operator picks the right
    one for their use case.
    """
    tp = record.get("top_provider") or {}
    ctx = tp.get("context_length")
    if ctx is not None:
        try:
            ctx = int(ctx)
        except (TypeError, ValueError):
            ctx = None
    max_out = tp.get("max_completion_tokens")
    if max_out is not None:
        try:
            max_out = int(max_out)
        except (TypeError, ValueError):
            max_out = None
    is_moderated = 1 if tp.get("is_moderated") else 0
    return ctx, max_out, is_moderated


def _live_canonical_slug(record: dict) -> str | None:
    """OR's `canonical_slug` (e.g. anthropic/claude-sonnet-5-20260630).
    Often longer than the route id and carries a date suffix. None when
    OR doesn't provide one."""
    return (record.get("canonical_slug") or "").strip() or None


def _live_knowledge_cutoff(record: dict) -> str | None:
    """OR's `knowledge_cutoff` (ISO date string). None when absent."""
    return (record.get("knowledge_cutoff") or "").strip() or None


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


def _kilo_caching(record: dict) -> tuple[float | None, float | None]:
    """Kilo's `cost.cache` block — same scale as `cost.input` (already
    USD per million). Returns (read, write) as floats, or (None, None)
    if the block is absent.

    Kilo-cli parity with OR's `pricing.input_cache_read`/`input_cache_write`
    extraction added 2026-07-01.
    """
    cost = record.get("cost", {}) or {}
    cache = cost.get("cache") or {}
    if not isinstance(cache, dict):
        return None, None

    def _f(key: str) -> float | None:
        v = cache.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return _f("read"), _f("write")


def _kilo_caps(record: dict) -> dict[str, int]:
    """Pull capability flags from Kilo CLI's `capabilities` block.

    Map keys to the DB schema's column names: has_vision (image input),
    has_tools (toolcall), has_reasoning (reasoning bool). This is the
    Kilo-CLI parallel to _live_caps() — for Kilo-only rows it's our only
    source for these flags.
    """
    caps = record.get("capabilities") or {}
    inp = caps.get("input") or {}
    has_vision = 1 if (inp.get("image") if isinstance(inp, dict) else False) else 0
    has_tools = 1 if caps.get("toolcall") else 0
    has_reasoning = 1 if caps.get("reasoning") else 0
    return {
        "has_vision": has_vision,
        "has_tools": has_tools,
        "has_reasoning": has_reasoning,
    }


def _kilo_limits(record: dict) -> tuple[int | None, int | None]:
    """Pull (context_length_in_tokens, max_completion_tokens) from Kilo's
    `limit` block. Numeric, no division — Kilo gives raw token counts."""
    lim = record.get("limit") or {}
    ctx = lim.get("context")
    out = lim.get("output")
    try:
        ctx = int(ctx) if ctx is not None else None
    except (TypeError, ValueError):
        ctx = None
    try:
        out = int(out) if out is not None else None
    except (TypeError, ValueError):
        out = None
    return ctx, out


def _kilo_reasoning_efforts(record: dict) -> str | None:
    """Kilo's `variants` block is a dict of effort-level keys → variant info.
    The KEYS are the reasoning effort levels (e.g. ["none", "minimal",
    "low", "medium", "high", "xhigh"]). Returns a JSON array string or None
    if the block is empty / not present.
    """
    v = record.get("variants")
    if not isinstance(v, dict) or not v:
        return None
    keys = sorted(v.keys())
    if not keys:
        return None
    return json.dumps(keys)


def _kilo_provider_id(record: dict) -> str | None:
    """Kilo CLI's `providerID` ('kilo' for the native gateway, 'openrouter'
    when Kilo is just proxying OR). For models that appear twice in
    `kilo models --verbose` (one per providerID), the parser keeps one;
    this helper lets the caller see which provider variant won."""
    return (record.get("providerID") or "").strip() or None


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
        # has_reasoning drift detection (2026-07-01): pre-fix this field was
        # set at ingest time and never re-verified — the daily catalog audit
        # found 3 rows drifted. Now covered by the same discrepancy path as
        # has_vision/has_tools so future drift gets auto-corrected nightly.
        if (row.get("has_reasoning") or 0) != live_caps["has_reasoning"]:
            row_disc.append(
                {
                    "field": "has_reasoning",
                    "db": row.get("has_reasoning"),
                    "live": live_caps["has_reasoning"],
                }
            )
        # knowledge_cutoff drift (Phase 1 field). Empty→empty stays clean.
        live_cutoff = _live_knowledge_cutoff(live_rec)
        db_cutoff = row.get("knowledge_cutoff") or None
        if live_cutoff and db_cutoff != live_cutoff:
            row_disc.append(
                {
                    "field": "knowledge_cutoff",
                    "db": db_cutoff,
                    "live": live_cutoff,
                }
            )
        # max_completion_tokens drift (Phase 1 field).
        _, live_max_out, live_moderated = _live_top_provider(live_rec)
        if live_max_out is not None and row.get("max_completion_tokens") != live_max_out:
            row_disc.append(
                {
                    "field": "max_completion_tokens",
                    "db": row.get("max_completion_tokens"),
                    "live": live_max_out,
                }
            )
        if (row.get("is_moderated") or 0) != live_moderated:
            row_disc.append(
                {
                    "field": "is_moderated",
                    "db": row.get("is_moderated"),
                    "live": live_moderated,
                }
            )
        # reasoning_mandatory + reasoning_supported_efforts drift (Phase 1 fields).
        live_rmandatory, live_refforts = _live_reasoning_efforts(live_rec)
        if (row.get("reasoning_mandatory") or 0) != live_rmandatory:
            row_disc.append(
                {
                    "field": "reasoning_mandatory",
                    "db": row.get("reasoning_mandatory"),
                    "live": live_rmandatory,
                }
            )
        # supported_efforts is a JSON string; compare as-is (both sides serialize
        # the same way via json.dumps ordering).
        if (row.get("reasoning_supported_efforts") or None) != live_refforts:
            row_disc.append(
                {
                    "field": "reasoning_supported_efforts",
                    "db": row.get("reasoning_supported_efforts"),
                    "live": live_refforts,
                }
            )
        # canonical_slug drift (Phase 1 field) — OR occasionally re-slugs.
        live_slug = _live_canonical_slug(live_rec)
        if live_slug and (row.get("canonical_slug") or None) != live_slug:
            row_disc.append(
                {
                    "field": "canonical_slug",
                    "db": row.get("canonical_slug"),
                    "live": live_slug,
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
    #
    # Priority for canonical collisions (up to 3 Kilo records share a
    # canonical: `<provider>/<name>`, `stealth/<name>`, bare `<name>`).
    # Bug caught 2026-07-01: naive last-write-wins overwrote the real
    # $5/$25 price for anthropic/claude-opus-4.8 with the bare-form
    # `claude-opus-4-8` record which Kilo emits as $0/$0 (placeholder).
    # Score records so the properly-prefixed, priced record wins:
    #   +100  provider-prefixed id (contains "/")
    #   +50   priced (input > 0 or output > 0)   — placeholders are $0/$0
    #   -20   stealth/* prefix (beta discount preview, not the real price)
    def _rec_priority(kid: str, k_in: float, k_out: float) -> int:
        score = 0
        if "/" in kid:
            score += 100
        if k_in > 0 or k_out > 0:
            score += 50
        if kid.startswith("stealth/"):
            score -= 20
        return score

    # Also expose the priority-selected raw record per canonical so the
    # richer-field capabilities pass in apply_fixes (family, provider_id,
    # cache pricing) writes to the correct canonical DB row too. Without
    # this, bare-form Kilo records like `claude-fable-5` UPDATE
    # non-existent rows while the real `anthropic/claude-fable-5` DB row
    # gets no update at all (kilo_family stays NULL).
    kilo_sourced: dict[str, dict] = {}
    kilo_scores: dict[str, int] = {}
    kilo_best_record: dict[str, dict] = {}
    for mid, rec in kilo.items():
        k_in, k_out = _kilo_pricing(rec)
        canonical_id = or_canonical_to_full.get(_canonicalize_id(mid), mid)
        score = _rec_priority(mid, k_in, k_out)
        if canonical_id in kilo_scores and kilo_scores[canonical_id] >= score:
            continue
        kilo_sourced[canonical_id] = {"input": k_in, "output": k_out}
        kilo_best_record[canonical_id] = rec
        kilo_scores[canonical_id] = score

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
    # `openrouter/*` rows are OR-managed meta-routers / alpha-tier routes
    # (auto, fusion, owl-alpha, elephant-alpha, pareto-code, bodybuilder).
    # OR hides their alpha/preview routes from /api/v1/models but the
    # routes remain USABLE — model page openrouter.ai/openrouter/owl-alpha
    # loads with live pricing, and the route serves requests. Pre-fix the
    # verifier flagged any openrouter/* row not in /api/v1/models as
    # truly_delisted → status='deprecated', breaking the OR-only chip on
    # the browser. Exempt the prefix here: OR controls these routes'
    # lifecycle and absence from the listings endpoint is OR's curation
    # choice, NOT a delisting signal.
    or_meta_prefix = "openrouter/"
    truly_delisted = [
        mid
        for mid in delisted
        if mid not in kilo and mid not in direct_routed and not mid.startswith(or_meta_prefix)
    ]
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
        "kilo_best_record": kilo_best_record,
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
            # Richer-extraction fields (2026-07-01 migration)
            slug = _live_canonical_slug(rec)
            cutoff = _live_knowledge_cutoff(rec)
            cache_r, cache_w = _live_caching(rec)
            r_mandatory, r_efforts = _live_reasoning_efforts(rec)
            _, max_out, is_mod = _live_top_provider(rec)
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "has_vision, has_tools, has_reasoning, status, last_verified, "
                "via_openrouter, via_kilo, kilo_input_cost_per_m, kilo_output_cost_per_m, "
                "is_variable_pricing, description, "
                "canonical_slug, knowledge_cutoff, "
                "cache_read_cost_per_m, cache_write_cost_per_m, "
                "reasoning_mandatory, reasoning_supported_efforts, "
                "max_completion_tokens, is_moderated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 1, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?)",
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
                    caps["has_reasoning"],
                    today_iso,
                    also_kilo,
                    k_in,
                    k_out,
                    1 if is_var else 0,
                    desc,
                    slug,
                    cutoff,
                    cache_r,
                    cache_w,
                    r_mandatory,
                    r_efforts,
                    max_out,
                    is_mod,
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
            # And reset any rows OpenRouter no longer returns.
            # EXCEPTION: `openrouter/*` meta-routes (auto, fusion, owl-alpha,
            # elephant-alpha, pareto-code, bodybuilder) are OR-managed alpha
            # / preview routes that OR hides from /api/v1/models but keeps
            # routable. Don't flip via_openrouter=0 on these — same rationale
            # as the truly_delisted exemption above.
            conn.execute(
                f"UPDATE agents SET via_openrouter = 0 "
                f"WHERE id NOT IN ({placeholders}) "
                f"AND id NOT LIKE 'openrouter/%'",
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

        # Kilo CLI richer extraction (Phase 3, 2026-07-01): per-row pull
        # of the same column set we extract from OR. For ROWS REACHABLE
        # VIA OR (via_openrouter=1), the OR-side data wrote first and
        # we DON'T overwrite it (OR is authoritative for dual-routed).
        # For KILO-ONLY rows, this pass is the only source for these
        # fields. Plus Kilo-specific columns (kilo_provider_id,
        # kilo_release_date, kilo_family, kilo_cache_read/write) that
        # OR doesn't expose.
        kilo_descs_written = 0
        kilo_richer_rows = 0
        # Use the priority-selected best record per canonical DB id
        # (built in verify()). Iterating raw kilo_raw would attempt
        # UPDATE agents WHERE id='claude-fable-5' — a bare-form Kilo id
        # that has no DB row — while the real `anthropic/claude-fable-5`
        # row would get no update because it's not a raw Kilo key.
        # Bug caught 2026-07-01 by audit_ui_values.py Phase C.
        kilo_best = report.get("kilo_best_record") or {}
        for mid, rec in kilo_best.items():
            # Description: only fill if OR didn't.
            desc = _kilo_description(rec)
            if desc:
                cur = conn.execute(
                    "UPDATE agents SET description = ? "
                    "WHERE id = ? AND (description IS NULL OR description = '')",
                    (desc, mid),
                )
                if cur.rowcount:
                    kilo_descs_written += cur.rowcount

            # Kilo-side richer fields
            k_caps = _kilo_caps(rec)
            k_ctx, k_max_out = _kilo_limits(rec)
            k_efforts = _kilo_reasoning_efforts(rec)
            k_cache_r, k_cache_w = _kilo_caching(rec)
            k_provider = _kilo_provider_id(rec)
            k_release = (rec.get("release_date") or "").strip() or None
            k_family = (rec.get("family") or "").strip() or None

            # Kilo-only columns: always write (Kilo is authoritative for them)
            conn.execute(
                "UPDATE agents SET "
                "kilo_cache_read_cost_per_m = ?, "
                "kilo_cache_write_cost_per_m = ?, "
                "kilo_provider_id = ?, "
                "kilo_release_date = ?, "
                "kilo_family = ? "
                "WHERE id = ?",
                (k_cache_r, k_cache_w, k_provider, k_release, k_family, mid),
            )

            # Shared columns: write ONLY for Kilo-ONLY rows (via_openrouter=0).
            # OR-routed rows have OR as authority for these fields — writing
            # Kilo's values here silently reverts the discrepancy loop's
            # nightly correction. Bug caught 2026-07-01: perplexity/sonar-
            # reasoning-pro et al. had OR-say has_reasoning=0 written by the
            # discrepancy pass, then this Kilo pass immediately reverted to 1
            # because Kilo's capabilities.reasoning=1 for those routes.
            # `AND via_openrouter = 0` is the fix: Kilo authority applies
            # only where OR isn't in the picture.
            cur = conn.execute(
                "UPDATE agents SET "
                "has_vision      = COALESCE(NULLIF(has_vision, 0),      ?), "
                "has_tools       = COALESCE(NULLIF(has_tools, 0),       ?), "
                "has_reasoning   = COALESCE(NULLIF(has_reasoning, 0),   ?), "
                "context_window_k = COALESCE(NULLIF(context_window_k, 0), ?), "
                "max_completion_tokens = COALESCE(max_completion_tokens, ?), "
                "cache_read_cost_per_m = COALESCE(cache_read_cost_per_m, ?), "
                "cache_write_cost_per_m = COALESCE(cache_write_cost_per_m, ?), "
                "reasoning_supported_efforts = COALESCE(reasoning_supported_efforts, ?) "
                "WHERE id = ? AND (via_openrouter = 0 OR via_openrouter IS NULL)",
                (
                    k_caps["has_vision"],
                    k_caps["has_tools"],
                    k_caps["has_reasoning"],
                    (k_ctx // 1000) if k_ctx else None,
                    k_max_out,
                    k_cache_r,
                    k_cache_w,
                    k_efforts,
                    mid,
                ),
            )
            if cur.rowcount:
                kilo_richer_rows += cur.rowcount
        counts["kilo_descriptions_written"] = kilo_descs_written
        counts["kilo_richer_rows"] = kilo_richer_rows

        # Richer OR extraction (2026-07-01): for every live OR row, refresh
        # the 8 new columns the migration added — canonical_slug,
        # knowledge_cutoff, cache_read/write costs, reasoning_mandatory,
        # reasoning_supported_efforts, max_completion_tokens, is_moderated.
        # Operator-flagged: "are you sure we can extract all models with all
        # their columns?" — answer was no, only 6 of 18 fields. This pass
        # closes the gap for OR-routed rows. Direct-vendor + Kilo-only rows
        # don't get these fields populated here (no OR data to pull from).
        richer_rows_updated = 0
        live_raw = _fetch_live()
        for mid, rec in live_raw.items():
            slug = _live_canonical_slug(rec)
            cutoff = _live_knowledge_cutoff(rec)
            cache_r, cache_w = _live_caching(rec)
            r_mandatory, r_efforts = _live_reasoning_efforts(rec)
            tp_ctx, max_out, is_mod = _live_top_provider(rec)
            cur = conn.execute(
                "UPDATE agents SET "
                "canonical_slug = ?, "
                "knowledge_cutoff = ?, "
                "cache_read_cost_per_m = ?, "
                "cache_write_cost_per_m = ?, "
                "reasoning_mandatory = ?, "
                "reasoning_supported_efforts = ?, "
                "max_completion_tokens = ?, "
                "is_moderated = ? "
                "WHERE id = ?",
                (slug, cutoff, cache_r, cache_w, r_mandatory, r_efforts, max_out, is_mod, mid),
            )
            if cur.rowcount:
                richer_rows_updated += cur.rowcount
        counts["richer_fields_refreshed"] = richer_rows_updated

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
