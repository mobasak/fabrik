"""Worker selection — pick the right OpenRouter model for a task type, cheaply.

The orchestrator (the dispatching agent) is the boss; these models are the workers.
This module encodes the "opt wise" rule ONCE so every project that vendors ``subagents``
selects workers the same disciplined way: **pick the cheapest model that clears the
quality bar for the task type**, honoring a cost ceiling and a caller-supplied exclude
list (e.g. a model that already failed this session).

Data provenance (two rails, both fleet-wide):
  1. **Ranking** — the canonical, daily-refreshed source is the fleet's
     ``CODING_SUBAGENT_SELECTION.md`` (generated from ``kilo-benchmarks/kilo_agents.db``
     in ``/opt/fabrik`` and synced to every project). The tables below are the *vendored
     default* seeded from it + empirical fabrik runs; they are the fallback when a project
     ships no fresher doc.
  2. **Refinement** — every ``run_agents`` run is recorded to the ledger with its
     ``task_type`` (see ``AgentSpec.task_type`` + ``ledger.agent_record``). Aggregating
     those real runs (cost × quality × reliability per task-type) is what sharpens this
     table over time — the flywheel: more fleet usage → cheaper, better selection.

Only models from the allowed ``CODING_SUBAGENT_SELECTION.md`` pool appear here.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Literal

TaskKind = Literal["spec", "plan", "code", "review", "docs", "research"]
TASK_KINDS: tuple[TaskKind, ...] = (
    "spec",
    "plan",
    "code",
    "review",
    "docs",
    "research",
)

# Model registry: approximate OpenRouter OUTPUT price ($/M tokens), from the fleet's
# CODING_SUBAGENT_SELECTION.md. Used to honor a cost ceiling + compute value. Prices
# drift — the synced doc is canonical; this is the vendored fallback.
_OUT_PRICE: dict[str, float] = {
    "minimax/minimax-m2.5": 0.48,
    "z-ai/glm-5": 1.92,
    "deepseek/deepseek-v3.2": 0.343,
    "moonshotai/kimi-k2.5": 2.025,
    "z-ai/glm-4.6": 1.74,
    "minimax/minimax-m3": 1.20,
    "deepseek/deepseek-v4-flash": 0.18,
    "deepseek/deepseek-v4-pro": 0.87,
    "z-ai/glm-5.2": 3.00,
    "moonshotai/kimi-k2": 2.30,
    # Registered on request 2026-07-08 — OUTPUT $/Mtok from openrouter.ai/api/v1/models
    # (also reachable via the live fallback below; listed here for offline determinism):
    "z-ai/glm-5.1": 3.04,
    "qwen/qwen3.7-max": 3.75,
    "x-ai/grok-4.20": 2.50,
    "x-ai/grok-4.20-multi-agent": 2.50,
}

# Fleet cost policy: the Auto-tier output-price cap. `pick_models` ALWAYS enforces this (so it is
# the sole gatekeeper — no rule/command file needs to name a roster or a price); a caller opts into
# the On-request tier for a pricier model with `allow_above_cap=True`. Changing the policy = change
# this one constant.
_MAX_POOL_PRICE_PER_MTOK = 1.5

# --- Live pricing fallback (opt-in) --------------------------------------------------
# The static table above is the offline default; it only covers the curated pool and can
# go stale. When live pricing is enabled (``model_price(..., live=True)`` or env
# ``SUBAGENT_LIVE_PRICING=1``), a table MISS fetches OpenRouter's live model list once
# (cached per process) so ANY model can be priced — cost-bounded selection then works for
# models beyond the vetted pool. Best-effort: a fetch failure ⇒ fall back to None (the
# caller fail-closes and excludes the model, never guesses).
_LIVE_PRICE: dict[str, float] = {}
_LIVE_FETCHED = False


def _fetch_openrouter_prices() -> dict[str, float]:
    """OpenRouter's live model list → ``{model_id: output $/Mtok}``; ``{}`` on any failure."""
    out: dict[str, float] = {}
    try:
        import httpx  # inside the try so a missing dep also fails closed (pricing NEVER crashes selection)

        resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=15.0)
        resp.raise_for_status()
        data = resp.json().get("data", []) if isinstance(resp.json(), dict) else []
    except Exception:  # noqa: BLE001 — pricing must NEVER crash selection
        return {}
    for m in data:
        # Guard PER ITEM so one odd row (a non-dict entry, `pricing` not a dict, a weird
        # `completion`) is skipped — not the whole 300-model list lost to a single bad row.
        try:
            if not isinstance(m, dict):
                continue
            pricing = m.get("pricing")
            mid = m.get("id")
            comp = pricing.get("completion") if isinstance(pricing, dict) else None
            if not mid or comp is None:
                continue
            out[mid] = float(comp) * 1_000_000  # per-token USD → per-Mtok
        except (TypeError, ValueError, AttributeError):
            continue
    return out


# task_type -> models ranked BEST-FIRST (highest quality first).
#   ALLOWED POOL — fleet policy (2026-07-08): a model is selectable only if its OUTPUT price is
#   <= $1.5/Mtok. The current members are these five benchmarked models (output $0.18-$1.20); a
#   future cheaper model can join once it clears a benchmark. glm-5/5.x ($3.00+), kimi ($2.03-3.50),
#   grok ($2.50), qwen ($3.75) all EXCEED $1.5 -> excluded from selection; they stay PRICED (for an
#   explicit opt-in test) but pick_models never returns them.
#   Rankings are EMPIRICAL from the fabrik api-quota benchmark (subagent_runs, 2026-07-06/07):
#     plan  — minimax-m3 4.8 > v4-pro 4.4 > v3.2 4.3 > v4-flash 3.9 > m2.5 3.3
#     review— minimax-m3 4.55 > v3.2 4.25 > v4-pro 4.05 > (m2.5 untested) > v4-flash 2.15 (weak)
#     code  — v4-flash 4.8 > minimax-m3 4.7 > v4-pro 4.1 > v3.2 3.4 > (m2.5 untested)
#     spec  — m2.5 4.3 > v3.2 3.8 (tested); m3/v4-pro/v4-flash by overall quality
#   docs/research have no A/B yet → seeded by overall quality (m3 best); the flywheel refines.
_TABLE: dict[str, list[str]] = {
    "spec": [
        "minimax/minimax-m2.5",
        "deepseek/deepseek-v3.2",
        "minimax/minimax-m3",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v4-flash",
    ],
    "plan": [
        "minimax/minimax-m3",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
    ],
    "code": [
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m3",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v3.2",
        "minimax/minimax-m2.5",
    ],
    "review": [
        "minimax/minimax-m3",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-pro",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-v4-flash",
    ],
    "docs": [
        "minimax/minimax-m3",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v3.2",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-v4-flash",
    ],
    "research": [
        "minimax/minimax-m3",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v3.2",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-v4-flash",
    ],
}

# Read-only public view of the seed table (a copy, so a caller can't mutate the default).
TASK_MODEL_TABLE: dict[str, list[str]] = {k: list(v) for k, v in _TABLE.items()}

# --- fresh synced ranking (the flywheel output the hub emits) ------------------------------
# The hub's kilo-benchmarks (rank_task_subagents.py) aggregates the shared subagent_runs table
# into a synced TASK_SUBAGENT_SELECTION.md: one `### <task_type>` section per TaskKind, each a
# rank-ordered markdown table (model in column 2, run-count `n` in the last column), ordered by
# success × avg_quality / avg_cost. When a project ships that doc (path via env
# SUBAGENT_SELECTION_DOC), pick_models prefers its EMPIRICAL rank order over the vendored _TABLE;
# a missing/empty/stub doc falls back to the vendored default (zero regression).
_RANK_CACHE: dict[str, tuple[float, dict[str, list[str]]]] = {}
_ROW_RE = re.compile(r"^\|(.+)\|$")


def load_task_ranking(
    path: str | None = None, *, min_n: int = 0, max_age_days: int | None = None
) -> dict[str, list[str]]:
    """Parse a synced TASK_SUBAGENT_SELECTION.md into ``{task_type: [models, rank-ordered]}``.

    ``path`` defaults to env ``SUBAGENT_SELECTION_DOC``. Returns ``{}`` for a missing/unreadable
    or empty (stub) doc — the caller then uses the vendored table. ``min_n`` drops rows whose
    run-count column is below the threshold (``0`` keeps every row the doc lists).
    ``max_age_days`` (if set) treats a doc whose ``Last refresh: YYYY-MM-DD`` stamp is older than
    that as untrustworthy → ``{}`` (a broken aggregator must not pin a stale ranking forever).
    Never raises.
    """
    path = path or os.getenv("SUBAGENT_SELECTION_DOC")
    if not path:
        return {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    # staleness gate (fabrik-AI parse contract): a doc older than max_age_days is not trusted.
    if max_age_days is not None:
        stamp = re.search(r"Last refresh:\s*(\d{4}-\d{2}-\d{2})", text)
        if stamp:
            try:
                refreshed: date | None = date.fromisoformat(stamp.group(1))
            except ValueError:
                refreshed = (
                    None  # unparseable date → ignore the gate, don't fail on a quirk
                )
            if refreshed is not None and (date.today() - refreshed).days > max_age_days:
                return {}
    valid = set(TASK_KINDS)
    out: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(
            "```"
        ):  # a ``` toggles a code fence — never parse fenced rows
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("###"):
            # ANY level-3 header ENDS the current section; a new one begins only if its name is
            # exactly a known TaskKind (case-insensitive). A garbled/typo/`code-review` header (or
            # one the regex rejects, e.g. no space after `###`) resets to None so its rows can't
            # leak into the previous valid kind. Matched on `stripped` so an indented header works.
            head = re.match(r"^###\s+([A-Za-z][\w-]*)", stripped)
            name = head.group(1).lower() if head else ""
            current = name if name in valid else None
            continue
        if current is None:
            continue
        row = _ROW_RE.match(stripped)
        if not row:
            continue
        cells = [c.strip() for c in row.group(1).split("|")]
        # a data row leads with a base-10 rank; header ("rank") + the "---" separator fail this.
        # `.isdecimal()` (not `.isdigit()`) rejects unicode digits (e.g. "²") so `int()` below
        # can never raise — the "never raises" contract is absolute.
        if len(cells) < 2 or not cells[0].isdecimal():
            continue
        # the hub renders the model as a backticked `provider/model`; strip the code ticks so
        # the id we hand to OpenRouter is clean (a `x` here would be an invalid model id).
        model = cells[1].strip("`")
        # the model cell must look like an OpenRouter id (provider/model) — a column-order drift
        # in the EXTERNAL doc must not silently inject a number/label as a "model".
        if "/" not in model:
            continue
        # strip backticks from the run-count too (symmetry with `model` — the hub renders `n`
        # plain today, but this keeps min_n robust if that column's rendering ever drifts).
        n_cell = cells[-1].strip("`")
        n = int(n_cell) if n_cell.isdecimal() else 0
        if min_n and n < min_n:
            continue
        bucket = out.setdefault(current, [])
        if model not in bucket:  # dedup, preserving first-seen (best) rank order
            bucket.append(model)
    return {k: v for k, v in out.items() if v}


def _synced_ranking() -> dict[str, list[str]]:
    """Env-driven, mtime-cached parse of the synced doc (re-reads when the daily refresh bumps it)."""
    path = os.getenv("SUBAGENT_SELECTION_DOC")
    if not path:
        return {}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = _RANK_CACHE.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    # a stale synced doc (>14 days — a stopped aggregator) is dropped so a project falls back to
    # the vendored table rather than pinning an old ranking forever (fabrik-AI parse contract).
    parsed = load_task_ranking(path, max_age_days=14)
    _RANK_CACHE[path] = (mtime, parsed)
    return parsed


def model_price(model: str, *, live: bool | None = None) -> float | None:
    """Approximate OpenRouter OUTPUT price ($/M tokens) for a model, or ``None`` if unknown.

    Static table first (offline, deterministic). If the model is not in the table AND live
    pricing is enabled, fetch OpenRouter's live prices so a vendored agent can price ANY model —
    not just the curated pool. ``live`` resolves as: ``True`` = force live, ``False`` = force
    offline (an explicit ``False`` wins over the env), ``None`` (default) = defer to env
    ``SUBAGENT_LIVE_PRICING=1``. Still ``None`` if unknown even live (fail-closed: the caller
    excludes it).

    The live list is fetched **once per process** — on success OR failure — so a persistent
    selection loop can't re-hit a slow/down endpoint per model; a failed first fetch therefore
    leaves live pricing off for the process (restart to retry; a TTL refresh is a non-goal)."""
    if model in _OUT_PRICE:
        return _OUT_PRICE[model]
    use_live = live if live is not None else os.getenv("SUBAGENT_LIVE_PRICING") == "1"
    if use_live:
        global _LIVE_FETCHED
        if not _LIVE_FETCHED:
            _LIVE_PRICE.update(_fetch_openrouter_prices())
            _LIVE_FETCHED = True
        return _LIVE_PRICE.get(model)
    return None


def _price_or_inf(model: str, live: bool | None) -> float:
    """The model's output $/Mtok, or ``inf`` when unknown (so a ceiling drops it / value ~0)."""
    price = model_price(model, live=live)
    return price if price is not None else float("inf")


def provider_max_price(model: str) -> dict | None:
    """The OpenRouter ``provider.max_price`` for this model — the native "same-price fallback"
    ceiling, so a provider (including an automatic fallback) is never routed to above the model's
    normal OUTPUT rate. Returns ``{"completion": <price $/Mtok>}`` or ``None`` when the price is
    unknown (fail-open: don't over-constrain a model we can't price). NEVER raises.

    Only the completion (output) dimension is capped — that is the metered "never pay more" axis and
    the one the pool's ≤$1.5 policy is expressed in; an unpriced prompt dimension is left unconstrained
    so a legitimately-cheap-output provider is not excluded on prompt price.

    Uses the STATIC price table only (``live=False``): this runs on the per-dispatch hot path, and a
    best-effort ceiling must never trigger a blocking live-pricing HTTP fetch there. An off-table model
    simply gets no ceiling (fail-open) — the same-price guard is best-effort and primarily matters for
    the curated in-table pool anyway."""
    try:
        p = model_price(model, live=False)
    except Exception:  # noqa: BLE001 — never raises; treat any pricing failure as "unknown"
        return None
    return {"completion": p} if p is not None else None


def pick_models(
    task_type: str,
    n: int = 1,
    *,
    max_cost_per_mtok: float | None = None,
    exclude: tuple[str, ...] = (),
    prefer: Literal["quality", "value"] = "quality",
    ranking: dict[str, list[str]] | None = None,
    live: bool | None = None,
    allow_above_cap: bool = False,
) -> list[str]:
    """Return up to ``n`` model ids for ``task_type``, best-first, under the fleet cost cap.

    This is the SOLE gatekeeper for the ≤$1.5/Mtok fleet policy: it ALWAYS enforces
    :data:`_MAX_POOL_PRICE_PER_MTOK` on the default (Auto) tier — a pricier model can never
    reach the default pool even if the synced ranking doc surfaces one or a caller passes a
    looser ``max_cost_per_mtok``. Rule/command packs therefore name no model rosters; they name
    only the invariant + this mechanism (see ``PROPOSED_RULE-using-subagents.md``).

    Args:
        task_type: one of :data:`TASK_KINDS`. Unknown → ``ValueError``.
        n: how many models to return (e.g. for a parallel A/B). May return fewer if the
           ceiling or ``exclude`` filters them out.
        max_cost_per_mtok: an ADDITIONAL, tighter ceiling on output $/M — the min-spend guard.
           It can only lower the effective cap (``min`` with the always-on fleet cap), never
           raise it above $1.5 on the Auto tier.
        allow_above_cap: the On-request tier. ``True`` drops the always-on ≤$1.5 fleet cap so a
           pricier benchmarked model (kept in the data, never in the default pool) can be
           selected — then only ``max_cost_per_mtok`` (if given) applies. Default ``False``.
        exclude: model ids to skip (e.g. one that failed this session — the reliability lever).
        prefer: ``"quality"`` = the source ranking (best output first); ``"value"`` = re-rank
                by rank-adjusted cheapness (``(rank_weight)/price``) so a nearly-as-good but
                much cheaper worker wins — the default for cost-sensitive, high-volume work.
        ranking: explicit ``{task_type: [models]}`` override (tests / a caller with fresher
                 data). ``None`` → the synced :func:`_synced_ranking` if present, else the
                 vendored :data:`TASK_MODEL_TABLE`.
        live: price models beyond the static table via OpenRouter's live prices (see
              :func:`model_price`) so a cost ceiling can admit a freshly-added model.
              ``True``/``False`` force live on/off; ``None`` (default) defers to env
              ``SUBAGENT_LIVE_PRICING=1``.

    Returns: the chosen model ids (possibly empty if every candidate was filtered out).
    """
    if task_type not in _TABLE:
        raise ValueError(
            f"unknown task_type {task_type!r}; expected one of {TASK_KINDS}"
        )
    if n <= 0:  # a non-positive count is empty — never a Python negative-slice surprise
        return []
    # Empirical synced order if it covers this task type, else the vendored seed.
    table = ranking if ranking is not None else _synced_ranking()
    excluded = set(exclude)
    ranked = [
        m for m in (table.get(task_type) or _TABLE[task_type]) if m not in excluded
    ]
    # AUTO-TIER PRICE CAP — pick_models is the SOLE gatekeeper. The fleet ≤$1.5/Mtok cap is ALWAYS
    # enforced: even if the synced CODING_SUBAGENT_SELECTION.md is refreshed with a pricier model, or
    # a caller passes a looser `max_cost_per_mtok`, a >$1.5 model can never reach the default pool.
    # `max_cost_per_mtok` can only make the ceiling TIGHTER (min of the two). A caller opts into the
    # On-request tier for a pricier model with `allow_above_cap=True` — then only its own ceiling (if
    # any) applies. FAIL-CLOSED: an unpriced model (unknown even to the live fetch) prices to +inf and
    # is DROPPED by any ceiling — a hard budget guard must not be bypassed by an unknown price.
    ceilings = [
        c
        for c in (
            None if allow_above_cap else _MAX_POOL_PRICE_PER_MTOK,
            max_cost_per_mtok,
        )
        if c is not None
    ]
    if ceilings:
        cap = min(ceilings)
        ranked = [m for m in ranked if _price_or_inf(m, live) <= cap]
    if prefer == "value":
        # value = rank_weight / price; rank_weight is higher for better-ranked models, so a
        # cheaper model only overtakes a better-ranked one when its price advantage outweighs
        # the rank gap — never drops to a much worse worker just because it is cheap. An UNPRICED
        # model uses `inf` (→ value ~0 → sorted LAST), consistent with the fail-closed ceiling
        # filter: in a cost-sensitive selection an unknown-cost worker is never preferred.
        span = len(ranked)
        ranked = sorted(
            ranked,
            key=lambda m: (span - ranked.index(m)) / max(_price_or_inf(m, live), 1e-9),
            reverse=True,
        )
    return ranked[:n]


__all__ = [
    "TaskKind",
    "TASK_KINDS",
    "TASK_MODEL_TABLE",
    "pick_models",
    "model_price",
    "load_task_ranking",
]
