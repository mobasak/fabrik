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
    "minimax/minimax-m2.5": 0.90,  # corrected 2026-07-10 from a stale $0.48 (live OR = $0.90)
    "z-ai/glm-5": 1.92,
    "deepseek/deepseek-v3.2": 0.343,
    "moonshotai/kimi-k2.5": 2.025,
    "z-ai/glm-4.6": 1.74,
    "minimax/minimax-m3": 1.20,
    "deepseek/deepseek-v4-flash": 0.18,
    "deepseek/deepseek-v4-pro": 0.87,
    # Registered 2026-07-10 (plan-1 pool-utilization) — live OR OUTPUT $/Mtok, all validated callable;
    # roles web-live-researched (spec 2026-07-10-pool-cost-utilization-design.md):
    "z-ai/glm-4.7-flash": 0.40,  # cheap coder — SWE-bench 59.2%
    "z-ai/glm-4.5-air": 0.85,  # moderate reasoning/agentic — MMLU-Pro 71.9%
    "qwen/qwen3-coder-flash": 0.975,  # fast/long-ctx code — 123 tps, 1M ctx
    "deepseek/deepseek-r1-distill-llama-70b": 0.80,  # niche reasoning/math (verbose, slow)
    # Registered 2026-07-09 (operator request) — OUTPUT $/Mtok from openrouter.ai/api/v1/models;
    # $0.80 ≤ $1.5 → Auto-tier eligible (a coder model, added to _TABLE["code"] below):
    "qwen/qwen3-coder-next": 0.80,
    "z-ai/glm-5.2": 3.00,
    "moonshotai/kimi-k2": 2.30,
    # Registered on request 2026-07-08 — OUTPUT $/Mtok from openrouter.ai/api/v1/models
    # (also reachable via the live fallback below; listed here for offline determinism):
    "z-ai/glm-5.1": 3.04,
    "qwen/qwen3.7-max": 3.75,
    "x-ai/grok-4.20": 2.50,
    "x-ai/grok-4.20-multi-agent": 2.50,
    # Priced 2026-07-20 — the hub's gate-selected review/code shortlist models (from
    # TASK_SUBAGENT_SELECTION.md "✅ Selected subagents", $/M-out column). Needed so pick_models'
    # cost logic + provider_max_price can price them; most are >$1.5 (the always-on cap is gone, so
    # they are selected on quality, not price). deepseek-v4-flash is already priced above.
    "qwen/qwen3-max": 3.90,
    "google/gemini-3-flash-preview": 3.00,
    "deepseek/deepseek-v3.2-exp": 0.41,
    "openai/gpt-5.4-mini": 4.50,
    "openai/gpt-5.6-luna": 6.00,
    "writer/palmyra-x5": 6.00,
}

# Reference output-price ($/Mtok) — the OLD Auto-tier cap. NO LONGER auto-enforced by `pick_models`
# (removed 2026-07-19 per operator: the pool is curated, and per-run task cost is pennies regardless
# of $/Mtok — a blanket cap wrongly excluded the hub's top reviewers). Kept as a named reference a
# caller can still pass to `max_cost_per_mtok` if they deliberately want the old ≤$1.5 budget.
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
#   NO PRICE CAP (2026-07-19): `pick_models` no longer filters by output price — the fresh hub
#   ranking (auto-read from `_HUB_SELECTION_DOC` when co-located, else `SUBAGENT_SELECTION_DOC`)
#   drives selection and it deliberately ranks pricier high-quality reviewers (gemini-3-flash-preview,
#   gpt-5.1-codex-mini, glm-5.2, …) in-band because per-run task cost is pennies. This vendored `_TABLE`
#   is only the LAST-RESORT FALLBACK for an environment with neither the hub doc nor the env var; it can
#   drift from the daily-refreshed doc, so treat it as a floor, not the truth.
#   (The earlier 2026-07-06/07 api-quota empirical seed — m3-first for review, m2.5-first for spec — was
#    SUPERSEDED by the 2026-07-10 research-backed reorder below; the flywheel still refines from real runs.)
# Reordered 2026-07-10 (plan-1 pool-utilization) to a RESEARCH-BACKED, best-first (quality) order with a
# FAMILY-DIVERSE top-K — the first 3 of each list are DISTINCT vendor families so a K-way fan-out gets
# distinct-family recall (a same-family top-K defeats the diversity the design is built on). This IS the
# source (quality) order `pick_models` returns for prefer="quality" (the default); prefer="value" re-ranks
# it toward cheaper at call time — the table itself is NOT value-ordered. Roles from the web-live research in
# spec 2026-07-10-pool-cost-utilization-design.md: `deepseek-v4-pro` leads judgment tasks (frontier — ties
# Claude Opus 4.6 on SWE-bench @ $0.87, cheaper than m3); `deepseek-v4-flash` leads code (TOP empirical code
# score AND cheapest — both agree, not a value compromise). EVERY Auto-tier model (≤$1.5) appears in ≥1 list
# so pick_models can reach all of them (the `r1-distill` reasoning tail lives in the judgment lists). This is
# the vendored FALLBACK seed; the flywheel (CODING_SUBAGENT_SELECTION.md) refines it. `pick_models` best-first.
#   2026-07-20 REFRESH: `review` + `code` were re-seeded to the hub's GATE-SELECTED shortlists
#   (TASK_SUBAGENT_SELECTION.md "✅ Selected subagents"). The prior "v4-flash leads code / v4-pro leads
#   judgment" rationale still describes the OTHER task_types (spec/plan/docs/research), which are unchanged.
#   Consumers now AUTO-DISCOVER their synced copy of that doc (`_project_selection_doc`), so this vendored
#   table is only the last-resort OFFLINE floor.
_TABLE: dict[str, list[str]] = {
    # judgment/generalist task_types → v4-pro (deepseek) → m3 (minimax) → glm-4.5-air (zai) = 3 families
    "spec": [
        "deepseek/deepseek-v4-pro",
        "minimax/minimax-m3",
        "z-ai/glm-4.5-air",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-r1-distill-llama-70b",  # reasoning tail (verbose/slow) — reachable at n>=7
    ],
    "plan": [
        "deepseek/deepseek-v4-pro",
        "minimax/minimax-m3",
        "z-ai/glm-4.5-air",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-r1-distill-llama-70b",  # reasoning tail (verbose/slow) — reachable at n>=7
    ],
    # code → the hub's GATE-SELECTED coder shortlist (2026-07-20 refresh; TASK_SUBAGENT_SELECTION.md
    # "Coders — 6 selected", daily-driver then premium). Top-3 = google/deepseek/qwen = 3 distinct
    # families for fan-out recall diversity. glm-4.7-flash + qwen3-coder-flash stay at the TAIL: NOT
    # gate-selected (the hub dropped them from the doc's `### code` routing), but retained so a priced
    # ≤$1.5 coder is never stranded unreachable in the OFFLINE fallback. The synced doc wins when present.
    "code": [
        "google/gemini-3-flash-preview",
        "deepseek/deepseek-v3.2-exp",
        "qwen/qwen3-coder-next",
        "openai/gpt-5.4-mini",
        "openai/gpt-5.6-luna",
        "writer/palmyra-x5",
        "z-ai/glm-4.7-flash",
        "qwen/qwen3-coder-flash",
    ],
    # review → the hub's GATE-SELECTED reviewer shortlist (2026-07-20 refresh; TASK_SUBAGENT_SELECTION.md
    # "Reviewers — 4 selected", score5-desc). Top-3 = qwen/google/deepseek = 3 distinct families. The old
    # judgment-seed models (v4-pro, m3, glm-4.5-air, m2.5, r1-distill) remain reachable via spec/plan/docs/
    # research; the synced doc (auto-discovered) wins over this offline floor when present.
    "review": [
        "qwen/qwen3-max",
        "google/gemini-3-flash-preview",
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v3.2-exp",
    ],
    "docs": [
        "deepseek/deepseek-v4-pro",
        "minimax/minimax-m3",
        "z-ai/glm-4.5-air",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-r1-distill-llama-70b",  # reasoning tail (verbose/slow) — reachable at n>=7
    ],
    "research": [
        "deepseek/deepseek-v4-pro",
        "minimax/minimax-m3",
        "z-ai/glm-4.5-air",
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
        "deepseek/deepseek-r1-distill-llama-70b",  # reasoning tail (verbose/slow) — reachable at n>=7
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


# Canonical hub location of the daily-refreshed ranking. When ``SUBAGENT_SELECTION_DOC`` is unset but
# the hub is CO-LOCATED (fabrik-lib dev, or the hub itself), the module auto-reads this fresh doc so
# selection stays synced with no env wiring — that is the "why aren't the updated docs synced" fix.
# A vendored copy in a deployed project (no ``/opt/fabrik``) simply misses it and falls back to the
# env var or the vendored ``_TABLE`` (portable, zero-regression).
_HUB_SELECTION_DOC = "/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"

# The fabrik sync delivers `docs/reference/kilo/` (incl. this doc) into EVERY project tree, but a deployed
# project has no `/opt/fabrik` path and usually no `SUBAGENT_SELECTION_DOC` env — so without this a vendored
# copy silently fell back to the (drifting) `_TABLE`. A vendored `subagents` lives UNDER that same project
# tree (e.g. `<proj>/libs/subagents/subagents/`), so walking UP from this file finds the project's OWN fresh
# synced copy — closing the flywheel loop with zero env/deploy wiring.
_SYNCED_DOC_RELPATH = ("docs", "reference", "kilo", "TASK_SUBAGENT_SELECTION.md")


def _project_selection_doc(start: Path | None = None) -> str | None:
    """Ascend from ``start`` (default: this module's own location) to find the project's synced
    ``docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`` — NEAREST ancestor first.

    Returns the first (closest) existing match, or ``None`` when no copy sits above this module. The
    walk runs to the filesystem root — bounded naturally by the path depth, with NO arbitrary depth cap
    — so a module vendored at any depth still finds its project's doc; nearest-first guarantees the
    project's OWN copy wins over any farther ancestor. Never raises."""
    try:
        anchor = (start or Path(__file__)).resolve()
    except OSError:
        return None
    for parent in anchor.parents:
        candidate = parent.joinpath(*_SYNCED_DOC_RELPATH)
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:  # a permission/again error on one ancestor must not abort the walk
            continue
    return None


def _synced_ranking() -> dict[str, list[str]]:
    """mtime-cached parse of the synced ranking doc (re-reads when the daily refresh bumps it).

    Resolution order: ``SUBAGENT_SELECTION_DOC`` env → the co-located hub doc
    (:data:`_HUB_SELECTION_DOC`, if it exists) → the project-relative synced copy
    (:func:`_project_selection_doc`, discovered by walking up from this module) → ``{}`` (caller uses
    the vendored ``_TABLE``)."""
    path = os.getenv("SUBAGENT_SELECTION_DOC")
    if not path and os.path.exists(_HUB_SELECTION_DOC):
        path = _HUB_SELECTION_DOC
    if not path:
        path = _project_selection_doc()
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


def provider_max_price(model: str) -> dict[str, float] | None:
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
    """Return up to ``n`` model ids for ``task_type``, best-first (rank order of the synced doc /
    vendored table), with NO default price cap.

    The always-on ≤$1.5/Mtok fleet cap was REMOVED (operator decision 2026-07-19): the pool is
    curated cheap+high-quality and per-run task cost is pennies regardless of $/Mtok, so the blanket
    cap wrongly excluded the hub's top-ranked (unpriced or >$1.5) reviewers. Price filtering is now
    OPT-IN only, via ``max_cost_per_mtok``.

    Args:
        task_type: one of :data:`TASK_KINDS`. Unknown → ``ValueError``.
        n: how many models to return (e.g. for a parallel A/B). May return fewer if
           ``max_cost_per_mtok`` or ``exclude`` filters them out.
        max_cost_per_mtok: an OPT-IN output $/M ceiling — the only price filter left (the min-spend
           budget guard). ``None`` (default) = no price filtering at all. An unpriced model prices
           to +inf and is dropped ONLY when this ceiling is set (fail-closed under a budget).
        allow_above_cap: retained for backward compatibility; a NO-OP now (there is no always-on cap
           left to bypass).
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
    # PRICE CAP REMOVED (operator decision 2026-07-19). The former always-on ≤$1.5/Mtok fleet cap is
    # gone: the pool is curated cheap+high-quality, and per-run task cost — especially for review/spec
    # fan-outs — is pennies regardless of $/Mtok (the hub's TASK_SUBAGENT_SELECTION.md ranks all models
    # together, WITHOUT a $1.5 split, for exactly this reason). The blanket cap wrongly excluded the
    # hub's top-ranked reviewers (e.g. gemini-3-flash-preview, gpt-5.1-codex-mini, glm-5.2) and every
    # UNPRICED model. Now: only an OPT-IN `max_cost_per_mtok` (the min-spend budget guard) filters —
    # an unpriced model prices to +inf and is dropped ONLY when that ceiling is set. `allow_above_cap`
    # is retained for backward compatibility but is a NO-OP (there is no default cap left to bypass).
    if max_cost_per_mtok is not None:
        ranked = [m for m in ranked if _price_or_inf(m, live) <= max_cost_per_mtok]
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
