# ModelScope new-row auto-ingest — implementation plan

**Status:** IN-PROGRESS
**Date:** 2026-07-10
**Owner:** primary (this session)
**Spec:** [`docs/superpowers/specs/2026-07-10-modelscope-new-row-ingest-design.md`](../superpowers/specs/2026-07-10-modelscope-new-row-ingest-design.md) — CONVERGED, `md5=0c6f4480…`
**Converged:** 2026-07-10 via `/fabrik-plan-review` — 3 passes (P1: 1 edit removing unused imports; P2: 1 edit adding Evidence file:line citations to satisfy `check_convergence`; P3: no-op md5 fixed-point `12fd5cfb…` → `12fd5cfb…` + `check_convergence` clean)

## What we already agreed (Phase 0)

**Inherited from the CONVERGED spec (spec is the source of truth):**

- **Goal:** Extend `scrape_modelscope_catalog.py` from flip-only to also INSERT new rows for the ~22 unmatched MS `/v1/models` IDs each day, so `pick_models` / browser / rankers can route to them.
- **Chosen approach — 3-tier enrichment fallback per unmatched ID:**
  1. HuggingFace Hub **two-endpoint fetch**: `/api/models/<id>` (tags, pipeline_tag, cardData, partial config subset — NO `max_position_embeddings`) + `/<id>/resolve/main/config.json` with `follow_redirects=True` (real `max_position_embeddings`, `hidden_size`).
  2. modelscope.cn model-page SPA scrape via **vendored `web-scrape` fabrik-lib module** (`WebScraper.fetch_rendered` → `extract_nextjs_data`) — Next.js SPA, JS-rendered via vps1 browserless.
  3. Fallback: INSERT with placeholder defaults + `blocked=1` + `discard_reason='needs_metadata_enrichment (MS-only, HF+MS scrape both failed)'`.
- **INSERT semantics:** `INSERT OR IGNORE INTO agents (...)` — idempotent by `agents.id` PRIMARY KEY (verified this turn).
- **Pricing:** all MS rows get `input_cost_per_m=0` / `output_cost_per_m=0` — MS is credits-billed, not per-token.
- **All ingested rows carry:** `via_modelscope=1`, `reachable_with_existing_keys=1`, `status='active'`. HF-enriched rows are `blocked=0` (routable). Placeholder rows are `blocked=1` (visible in browser MS chip, invisible to rankers).
- **Trigger:** automatic, wired into `daily_refresh.sh` MS `_step` block via new `--ingest-new` flag.

**User-locked decisions (this session):**
- Q1: HF-miss + MS-scrape-miss rows → placeholder + `blocked=1` (user answered "then find a pricing page to scrape for all missing data" — spec responds: HF+MS-scrape IS the missing-data fetch chain; if BOTH fail there is no third source, hence placeholder).
- Q2: automatic in `daily_refresh.sh` (user chose).

**Rejected alternatives** (from spec §Rejected alternatives — see spec for full rationale): fully-active-with-defaults (0-price ranks-to-top footgun); new `status='pending_review'` value (touches 6 downstream SQL filters); skip HF-miss entirely (loses IIC/MedAIBase coverage); scrape modelscope.cn without `web-scrape` module (silent fork of a vendored capability); build a generic HF-metadata fabrik-lib module now (only 1 concrete use — flagged as 🆕 `catalog-enrichment` candidate after third use).

**Constraints (spec-locked):**
- Idempotent: `INSERT OR IGNORE` + repeat runs never duplicate.
- Fail-open: single HF failure never blocks other rows; scrape failure never blocks HF-enriched rows; whole `--ingest-new` failing never blocks the flip-only default behavior.
- Zero manual intervention for the HF-happy-path rows.
- No `shape:` flags, no new env vars (uses existing `MODELSCOPE_API_KEY`, `BROWSERLESS_URL`, `BROWSERLESS_TOKEN`).

**Branch: RICH.** Spec is CONVERGED and fed this plan. Phase 1 verifies (not re-derives) the fabrik-lib module API + external endpoint freshness.

## Global Constraints

Verbatim from binding sources; every phase inherits these:

- **Python 3.11+**, typing per `.windsurf/rules/core/10-python.md`. `from __future__ import annotations` in new files.
- **Explicit `git add <path>` only** — never `git add -A` / `git add .` / `git commit -a` (CLAUDE.md HARD STOP).
- **Fail-soft everywhere.** A `--ingest-new` failure must not block the flip-only default (the daily cron's downstream steps depend on `via_modelscope` flips completing).
- **No new deps files.** `pyproject.toml`, `requirements.txt`, `uv.lock` untouchable. `httpx>=0.27` is already in the project (used by `scrape_modelscope_catalog.py`). Vendored `web-scrape` module lists `httpx>=0.27` as its only runtime dep (verified: `/opt/fabrik-lib/web-scrape/requirements.txt`).
- **Vendoring protocol:** copy `/opt/fabrik-lib/web-scrape/web_scrape/` into `libs/web_scrape/`; rewrite internal imports if needed; do NOT modify the module's core (any bug fix appends to `/opt/fabrik-lib/web-scrape/UPSTREAM_FEEDBACK.md`).
- **Provenance trailers** on every commit — `Agent-Role: orchestrator`, `Agent-Phase: A|B|C|D`, `Agent-Context: <one-liner>`.
- **Secret discipline:** `MODELSCOPE_API_KEY` + `BROWSERLESS_TOKEN` pulled from `.env` via `os.getenv` only; never echoed in stdout; every commit verified via `git diff --cached | grep -c "ms-[a-f0-9]\|Bearer TWr"` = 0.
- **No `fabrik …` shell-out gates.** This is hub-side kilo-benchmarks (`fabrik` CLI is in `/opt/fabrik/.venv` but not needed — all work is direct Python + SQLite).
- **Governance-sync awareness:** `scripts/kilo-benchmarks/**` is HUB-ONLY (not synced to projects). `.windsurf/rules/ai/**` IS governance-synced but we're not touching it here. Only Phase D's `AGGREGATOR_ROADMAP.md` follow-up note may touch a synced file — flagged explicitly.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11+ typing, `from __future__ import annotations`, no bare `except` | `.windsurf/rules/core/10-python.md` |
| ACTIVE rule pack `core/25-data-postgres.md` | SQLite idempotent DDL/DML (`INSERT OR IGNORE`, transactions) | `.windsurf/rules/core/25-data-postgres.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | Behavior Contract: one test per user-observable behavior, risk-ordered, TDD for risky | `.windsurf/rules/core/45-testing-strategy.md` |
| ACTIVE rule pack `core/58-resilience.md` | Timeout/retry contract: any external call bounds wall-clock, doesn't retry-infinitely on transient errors | `.windsurf/rules/core/58-resilience.md` |
| ACTIVE rule pack `core/62-using-subagents.md` | Pool-default for gradeable fan-out, `record_agent_run` on every pool dispatch | `.windsurf/rules/core/62-using-subagents.md` |
| Vendored fabrik-lib module `web-scrape/` | JS-rendered SPA fetch + `__NEXT_DATA__` parse. **Real API** (verified `/opt/fabrik-lib/web-scrape/README.md` this turn): `WebScraper(cache_dir, browserless_url, browserless_token)`, `fetch_static(url) -> str`, `fetch_rendered(url, wait_for_selector=None) -> str`, `extract_nextjs_data(html) -> dict` (raises `ParseError`), errors `WebScrapeError`/`FetchError`/`ParseError`/`RobotsError`. Public surface enforced by `__all__`. | `/opt/fabrik-lib/web-scrape/README.md` (read this turn) |
| Sibling reference `verify_openrouter_catalog.py:812` `ingest_new` | Same-shape INSERT pattern: `INSERT INTO agents (id, api_id, name, provider, …) VALUES (…)` with idempotent guard. Mirror for consistency. | Read `:812-925` this turn |
| Current `scrape_modelscope_catalog.py` (168 lines) | Existing module we're extending. `_ORG_MAP` corrected in `50d244d7`. `fetch_ms_models`, `apply_flags`, `main` already present. | Read via prior turn |
| `agents` table schema | `id TEXT PRIMARY KEY nullable` (verified `PRAGMA table_info(agents)` this turn — `pk=1`, `notnull=0`). `INSERT OR IGNORE` de-dupes on `id`. NOT NULL columns: `api_id`, `name`, `provider`, `input_cost_per_m` (default `0`), `output_cost_per_m` (default `0`). | Verified this turn |
| `daily_refresh.sh:337` — MS step position | `_step "scrape_modelscope_catalog" "$VENV_PY" "$KB/scrape_modelscope_catalog.py"` — target for `--ingest-new` flag addition. | Verified via grep |
| `.env` credentials | `MODELSCOPE_API_KEY=ms-*` (existing); `BROWSERLESS_URL=https://browser.vps1.ocoron.com`, `BROWSERLESS_TOKEN=TWr…` (already set for other services — verified). | Grep on `/opt/fabrik/.env` this turn |
| **fabrik-lib consult** | Checked `/opt/fabrik-lib/README.md`. `web-scrape` module VENDORED (Phase A copies). No other fabrik-lib module covers HF Hub JSON fetch, per-vendor progressive enrichment, or agents-catalog INSERT. Building fresh — **flagged as 🆕 `catalog-enrichment` fabrik-lib candidate** in spec Handoff (third concrete use will trigger extraction proposal). | Spec `fabrik-lib verdict table` |
| `AGENTS.md` invariants | **N/A** — no compose service, no network, no VPS deploy, no ports | Spec inspection |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched | Spec inspection |

**GUI check:** N/A — no user-facing screens. No `docs/ui-design.md`, no `docs/data-contract.md` — none needed (this is a hub-side utility script, not a service).

---

## Phase A — Vendor `web-scrape` module + preflight + `ms_enrich.py` scaffold — ✅ EXECUTED 2026-07-10

**Goal.** Copy the `web-scrape` fabrik-lib module into `libs/web_scrape/`. Preflight-probe every external tool (Python, httpx, sqlite3, browserless connectivity, MS + HF endpoints). Create the empty `scripts/kilo-benchmarks/ms_enrich.py` module scaffold that Phases B/C will fill.

### Interfaces

**Consumes:** nothing (root phase).

**Produces:**
- **Vendored module** `libs/web_scrape/` — copy of `/opt/fabrik-lib/web-scrape/web_scrape/`. Importable as `from libs.web_scrape import WebScraper, extract_nextjs_data, ParseError, FetchError`.
- **Empty scaffold** `scripts/kilo-benchmarks/ms_enrich.py` (~30 LOC) — module docstring + `from __future__ import annotations` + `AFTER-EDIT` header + `__all__ = []` (Phases B/C will populate). Placeholder unit test `scripts/kilo-benchmarks/tests/test_ms_enrich.py` with 1 `test_import` sanity test.

### Behavior Contract

- **A1** — `from libs.web_scrape import WebScraper, extract_nextjs_data` succeeds (module vendored + importable).
- **A2** — `WebScraper(cache_dir=Path("/tmp/x"), browserless_url="…", browserless_token="…")` constructs without exception (module's public API matches what Phases B/C consume).
- **A3** — `scripts/kilo-benchmarks/ms_enrich.py` imports cleanly (scaffold in place for Phases B/C to extend).

### Steps

**A.0 — Preflight probes.**

```bash
python -m pytest --version 2>&1 | head -1                     # → pytest 9.0.2
python -c "import httpx, sqlite3; print('deps ok')"           # → deps ok
python -c "import httpx; print(httpx.__version__)"            # → ≥0.27
ls /opt/fabrik-lib/web-scrape/web_scrape/ | head -5           # → __init__.py + module files
grep -c "^MODELSCOPE_API_KEY=" /opt/fabrik/.env               # → 1
grep -c "^BROWSERLESS_URL=" /opt/fabrik/.env                  # → 1
grep -c "^BROWSERLESS_TOKEN=" /opt/fabrik/.env                # → 1
# Verify browserless reachable (LIVE probe — needed for Phase C):
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $(grep '^BROWSERLESS_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)" \
  "$(grep '^BROWSERLESS_URL=' /opt/fabrik/.env | cut -d= -f2-)/health"
# → 200 (or 404 with body — either proves the host is reachable)
```

If ANY probe fails: `BLOCKED: <what> — searched: A.0 preflight — missing: <need>`.

**A.1 — Vendor `web-scrape/` into `libs/`.**

```bash
cp -r /opt/fabrik-lib/web-scrape/web_scrape libs/web_scrape
# Verify the copy is a legitimate module (has __init__.py):
ls libs/web_scrape/__init__.py
# Verify public API:
python -c "from libs.web_scrape import WebScraper, extract_nextjs_data, ParseError, FetchError; print('OK')"
# → OK
```

**A.2 — Create empty scaffold `scripts/kilo-benchmarks/ms_enrich.py`.**

Exact content (~30 LOC):

```python
#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/scrape_modelscope_catalog.py scripts/kilo-benchmarks/tests/test_ms_enrich.py
"""ModelScope-specific metadata enrichment for --ingest-new mode.

Two tiers, in order:
  1. HuggingFace Hub — two-endpoint fetch (partial config + full config.json)
  2. modelscope.cn — Next.js SPA scrape via vendored web-scrape module

Both tiers fail-open (return None on any error). The caller
(scrape_modelscope_catalog.py:ingest_new) falls to placeholder defaults
if both return None.

Phase-2 plan reference: docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md
"""

from __future__ import annotations

__all__: list[str] = []  # populated by Phase B (fetch_hf_metadata) + Phase C (fetch_ms_metadata)
```

**A.3 — Placeholder test file `scripts/kilo-benchmarks/tests/test_ms_enrich.py`:**

```python
"""Behavior Contract for scripts/kilo-benchmarks/ms_enrich.py.

Plan-2 (ModelScope new-row ingest) — Phases A/B/C populate this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_a3_module_imports():
    """Scaffold sanity — module exists and imports cleanly."""
    import ms_enrich  # noqa: F401
```

**A.4 — Phase A gate.**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_ms_enrich.py -v 2>&1 | tail -4
# Expected: 1 passed
python -m ruff check libs/web_scrape/ scripts/kilo-benchmarks/ms_enrich.py scripts/kilo-benchmarks/tests/test_ms_enrich.py 2>&1 | tail -3
# Expected: All checks passed!
python scripts/enforcement/check_doc_sync.py 2>&1 | tail -3 || echo "(clean)"
```

**A.5 — `/fabrik-review` on Phase A's changed surface — BLOCKING gate looped to no-op.** Full adversarial methodology per skill: dispatch pool finder(s) (`minimax/minimax-m3` via `run_agents`, `pick_models("review")`, `allow_ungrounded=True` with diff inlined; owes `record_agent_run + results_table`) + native `fabrik-reviewer` (Sonnet) for a low-risk vendored-module diff. Prove-before-fix each surviving finding with a kept regression test. Loop until one full pass = zero CONFIRMED or PLAUSIBLE.

**A.6 — Doc-sync + commit.**

```bash
git add libs/web_scrape/ \
        scripts/kilo-benchmarks/ms_enrich.py \
        scripts/kilo-benchmarks/tests/test_ms_enrich.py
# NO other paths — check:
git diff --cached --name-only
# Verify no secrets:
git diff --cached | grep -cE "ms-[a-f0-9]{8}|Bearer TWr" && echo ABORT || echo clean
git commit -m "$(cat <<'EOF'
feat(kilo-db): Phase A — vendor web-scrape + ms_enrich scaffold

Plan 2 (ModelScope new-row auto-ingest) Phase A.

- libs/web_scrape/: vendored from /opt/fabrik-lib/web-scrape/web_scrape/.
  Public API: WebScraper (fetch_static/fetch_rendered), extract_nextjs_data,
  and errors (WebScrapeError/FetchError/ParseError/RobotsError).
- scripts/kilo-benchmarks/ms_enrich.py: empty module scaffold for the HF
  Tier-1 + MS Tier-2 fetchers Phases B/C populate.
- tests/test_ms_enrich.py: 1 import sanity test.

Preflight probes all pass: pytest 9.0.2, httpx>=0.27, sqlite3, MODELSCOPE_API_KEY,
BROWSERLESS_URL/TOKEN, browserless.vps1 reachable.

Agent-Role: orchestrator
Agent-Phase: A
Agent-Context: vendor web-scrape fabrik-lib module + scaffold ms_enrich

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Phase B — HuggingFace Hub Tier-1 fetcher (`fetch_hf_metadata`)

**Goal.** Implement the HF Hub two-endpoint fetcher. Populate `ms_enrich.py` with `HFMetadata` dataclass + `fetch_hf_metadata(hf_id) -> HFMetadata | None`. Fail-open on ANY error (missing model, 404, 5xx, network failure, JSON parse error).

### Interfaces

**Consumes** (from Phase A):
- `libs.web_scrape` importable (unused in this phase but must not conflict).
- `scripts/kilo-benchmarks/ms_enrich.py` scaffold exists.

**Produces:**
- **Dataclass** `HFMetadata` in `ms_enrich.py`:
  ```python
  @dataclass(frozen=True)
  class HFMetadata:
      context_window_k: int | None       # from /resolve/main/config.json → max_position_embeddings, in tokens/1024
      has_reasoning: bool                # from /api/models tags: contains "thinking" or "reasoning"
      has_tools: bool                    # from /api/models tags: contains "function-calling" or "tool-use"
      has_vision: bool                   # from /api/models tags: contains "vision" or "image-text-to-text"
      is_gated: bool                     # from /api/models: gated field
      model_type: str | None             # from /resolve/main/config.json: model_type
      pipeline_tag: str | None           # from /api/models: pipeline_tag
      source_url: str                    # the /api/models URL (for provenance)
  ```
- **Function** `fetch_hf_metadata(hf_id: str, *, client: httpx.Client | None = None) -> HFMetadata | None`
  - `hf_id` is the full ModelScope-published id (e.g. `internlm/internlm3-8b-instruct`).
  - Two `httpx.get` calls with `follow_redirects=True`, `timeout=10.0`.
  - Endpoint 1: `https://huggingface.co/api/models/<hf_id>` → JSON.
  - Endpoint 2: `https://huggingface.co/<hf_id>/resolve/main/config.json` → JSON (307 redirect handled).
  - Returns `None` on: HTTP 4xx/5xx, network failure, JSON parse error, missing critical fields.
  - `client=` parameter allows dependency injection for testing (default = `httpx.Client()`).

### Behavior Contract

Highest-risk behavior first (TDD):

- **B1 — happy path**: `fetch_hf_metadata("internlm/internlm3-8b-instruct")` (via mocked httpx) returns `HFMetadata(context_window_k=32, has_reasoning=False, has_tools=False, has_vision=False, is_gated=False, model_type='internlm3', pipeline_tag='text-generation', source_url='https://huggingface.co/api/models/internlm/internlm3-8b-instruct')`.
- **B2 — /api 404 → None**: model not on HF. `fetch_hf_metadata("nonexistent/model")` returns `None`.
- **B3 — /resolve 404 → partial return**: `/api/models` succeeds but `/resolve/main/config.json` returns 404. `context_window_k` stays `None`; other fields from `/api/models` populate normally. Return non-None `HFMetadata`.
- **B4 — timeout → None**: mock `httpx.ConnectTimeout`. `fetch_hf_metadata(...)` returns `None`.
- **B5 — bogus JSON → None**: `/api/models` returns HTTP 200 with `"not-json-lol"`. Return `None`.
- **B6 — gated model → sets is_gated=True**: `/api/models` returns `{"gated": true}`. `HFMetadata.is_gated == True`.
- **B7 — reasoning tag detection**: `/api/models` tags include `["thinking"]`. `HFMetadata.has_reasoning == True`.

### Steps

**B.1 — TDD: write B1–B7 tests FIRST** using `httpx.MockTransport` (per web-scrape module's test convention — no extra deps).

```python
# scripts/kilo-benchmarks/tests/test_ms_enrich.py — extended
import httpx
import json


_HF_API_INTERNLM = {
    "id": "internlm/internlm3-8b-instruct",
    "tags": ["text-generation", "internlm3", "custom_code"],
    "pipeline_tag": "text-generation",
    "gated": False,
}

_HF_CONFIG_INTERNLM = {
    "max_position_embeddings": 32768,
    "model_type": "internlm3",
    "hidden_size": 4096,
}


def _mock_transport(routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    """Route URL → response. Any unrouted URL returns 404."""
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))
    return httpx.MockTransport(handler)


def test_b1_hf_happy_path():
    from ms_enrich import fetch_hf_metadata
    routes = {
        "https://huggingface.co/api/models/internlm/internlm3-8b-instruct":
            httpx.Response(200, json=_HF_API_INTERNLM),
        "https://huggingface.co/internlm/internlm3-8b-instruct/resolve/main/config.json":
            httpx.Response(200, json=_HF_CONFIG_INTERNLM),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("internlm/internlm3-8b-instruct", client=client)
    assert md is not None
    assert md.context_window_k == 32
    assert md.model_type == "internlm3"
    assert md.pipeline_tag == "text-generation"
    assert md.is_gated is False
    assert md.has_reasoning is False


def test_b2_hf_api_404_returns_none():
    from ms_enrich import fetch_hf_metadata
    client = httpx.Client(transport=_mock_transport({}))  # all URLs 404
    assert fetch_hf_metadata("nonexistent/model", client=client) is None


def test_b3_hf_resolve_404_returns_partial():
    from ms_enrich import fetch_hf_metadata
    routes = {
        "https://huggingface.co/api/models/x/y":
            httpx.Response(200, json={"id": "x/y", "tags": [], "gated": False}),
        # /resolve NOT routed → 404
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md is not None
    assert md.context_window_k is None  # config.json missed
    assert md.is_gated is False


def test_b4_hf_timeout_returns_none():
    from ms_enrich import fetch_hf_metadata
    def handler(request):
        raise httpx.ConnectTimeout("simulated")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_hf_metadata("any/model", client=client) is None


def test_b5_hf_bogus_json_returns_none():
    from ms_enrich import fetch_hf_metadata
    routes = {
        "https://huggingface.co/api/models/x/y":
            httpx.Response(200, content=b"not-json-lol"),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    assert fetch_hf_metadata("x/y", client=client) is None


def test_b6_hf_gated_sets_flag():
    from ms_enrich import fetch_hf_metadata
    routes = {
        "https://huggingface.co/api/models/x/y":
            httpx.Response(200, json={"id": "x/y", "tags": [], "gated": True}),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.is_gated is True


def test_b7_hf_reasoning_tag_detected():
    from ms_enrich import fetch_hf_metadata
    routes = {
        "https://huggingface.co/api/models/x/y":
            httpx.Response(200, json={"id": "x/y", "tags": ["thinking", "text-generation"], "gated": False}),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.has_reasoning is True
```

**Gate B.1 (must FAIL RED — `fetch_hf_metadata` not defined):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_ms_enrich.py::test_b1_hf_happy_path -x 2>&1 | tail -5
# Expected: ImportError: cannot import name 'fetch_hf_metadata' from 'ms_enrich'
```

**B.2 — Implement `fetch_hf_metadata` + `HFMetadata` in `ms_enrich.py`.**

```python
# scripts/kilo-benchmarks/ms_enrich.py — Phase B addition
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

import httpx

__all__: list[str] = ["HFMetadata", "fetch_hf_metadata"]

_HF_API = "https://huggingface.co/api/models/{}"
_HF_CONFIG = "https://huggingface.co/{}/resolve/main/config.json"
_HTTP_TIMEOUT = 10.0

_REASONING_TAGS = frozenset({"thinking", "reasoning"})
_TOOLS_TAGS = frozenset({"function-calling", "tool-use", "tools"})
_VISION_TAGS = frozenset({"vision", "image-text-to-text", "image-to-text", "visual-question-answering"})


@dataclass(frozen=True)
class HFMetadata:
    context_window_k: int | None
    has_reasoning: bool
    has_tools: bool
    has_vision: bool
    is_gated: bool
    model_type: str | None
    pipeline_tag: str | None
    source_url: str


def _tags_intersect(tags: list[str] | None, needles: frozenset[str]) -> bool:
    if not tags:
        return False
    lowered = {str(t).lower() for t in tags if isinstance(t, str)}
    return bool(lowered & needles)


def fetch_hf_metadata(hf_id: str, *, client: httpx.Client | None = None) -> HFMetadata | None:
    """Fetch HF Hub metadata via /api/models + /resolve/main/config.json.

    Fail-open: returns None on any error (404, 5xx, network, JSON parse).
    Partial data OK: if /resolve missed, context_window_k stays None.
    """
    owned_client = client is None
    client = client or httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)
    try:
        api_url = _HF_API.format(hf_id)
        try:
            r = client.get(api_url)
            r.raise_for_status()
            api_data: dict[str, Any] = r.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            print(f"[ms_enrich] WARN: HF /api miss for {hf_id}: {exc}", file=sys.stderr)
            return None

        tags = api_data.get("tags") or []
        # /resolve/main/config.json is best-effort
        context_window_k: int | None = None
        model_type: str | None = None
        try:
            r2 = client.get(_HF_CONFIG.format(hf_id))
            r2.raise_for_status()
            cfg: dict[str, Any] = r2.json()
            mpe = cfg.get("max_position_embeddings")
            if isinstance(mpe, int) and mpe > 0:
                context_window_k = mpe // 1024
            mt = cfg.get("model_type")
            if isinstance(mt, str):
                model_type = mt
        except (httpx.HTTPError, json.JSONDecodeError, ValueError):
            pass  # partial data acceptable

        return HFMetadata(
            context_window_k=context_window_k,
            has_reasoning=_tags_intersect(tags, _REASONING_TAGS),
            has_tools=_tags_intersect(tags, _TOOLS_TAGS),
            has_vision=_tags_intersect(tags, _VISION_TAGS),
            is_gated=bool(api_data.get("gated")),
            model_type=model_type,
            pipeline_tag=api_data.get("pipeline_tag"),
            source_url=api_url,
        )
    finally:
        if owned_client:
            client.close()
```

**Gate B.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_ms_enrich.py -v 2>&1 | tail -12
# Expected: 8 passed (A3 + B1-B7)
python -m ruff check scripts/kilo-benchmarks/ms_enrich.py scripts/kilo-benchmarks/tests/test_ms_enrich.py 2>&1 | tail -3
# Expected: All checks passed!
```

**B.3 — Live-integration smoke (non-gated) — Optional but verifies the real HF endpoint didn't drift since spec:**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts/kilo-benchmarks')
from ms_enrich import fetch_hf_metadata
md = fetch_hf_metadata('internlm/internlm3-8b-instruct')
assert md is not None, 'live HF fetch returned None'
assert md.context_window_k == 32, f'expected 32K, got {md.context_window_k}'
print(f'B.3 LIVE OK: {md}')
"
```

**B.4 — `/fabrik-review` on Phase B — BLOCKING pool-first + native for the httpx/JSON-parse risk surface. Loop to no-op.**

**B.5 — Doc-sync + commit.** Same shape as A.6. Stage only `scripts/kilo-benchmarks/ms_enrich.py` + `scripts/kilo-benchmarks/tests/test_ms_enrich.py`.

Commit trailer: `Agent-Phase: B`, `Agent-Context: HF Hub Tier-1 fetcher (fetch_hf_metadata) + 7 behavior tests`.

---

## Phase C — modelscope.cn Tier-2 SPA scraper (`fetch_ms_metadata`)

**Goal.** Second-tier enrichment: for models where HF misses (IIC/GUI-Owl, MedAIBase, etc.), scrape `modelscope.cn/models/<id>` via the vendored `web-scrape` module, extract `__NEXT_DATA__` payload, pull context/description/gated status. Fail-open (returns `None` on any error).

### Interfaces

**Consumes** (from Phase A + B):
- `libs.web_scrape.WebScraper`, `libs.web_scrape.extract_nextjs_data`, `libs.web_scrape.ParseError`.
- `ms_enrich.py` module scaffold populated with `HFMetadata` + `fetch_hf_metadata`.

**Produces:**
- **Dataclass** `MSMetadata` in `ms_enrich.py`:
  ```python
  @dataclass(frozen=True)
  class MSMetadata:
      context_window_k: int | None       # extracted from __NEXT_DATA__ props.pageProps if present
      description: str | None            # model-card description snippet if present
      is_gated: bool                     # from __NEXT_DATA__ gated field if present
      source_url: str                    # the modelscope.cn URL
  ```
- **Function** `fetch_ms_metadata(ms_id: str, *, scraper: "WebScraper | None" = None) -> MSMetadata | None`
  - `ms_id` is the full ModelScope-published id.
  - Uses `WebScraper.fetch_rendered(f"https://modelscope.cn/models/{ms_id}", wait_for_selector="body")` + `extract_nextjs_data(html)`.
  - Walks the resulting dict looking for `max_tokens` / `max_length` / `context_length` under any path (per spec Residual #1 — key path is not fixed).
  - Fail-open on `FetchError` / `ParseError` / any exception → `None`.

### Behavior Contract

- **C1 — happy path**: mocked `WebScraper.fetch_rendered` returns HTML containing `<script id="__NEXT_DATA__">{"props":{"pageProps":{"model":{"max_tokens":32768,"description":"..."}}}}</script>`. `fetch_ms_metadata("Shanghai_AI_Laboratory/Intern-S1")` returns `MSMetadata(context_window_k=32, description="...", is_gated=False, source_url="https://modelscope.cn/models/...")`.
- **C2 — `__NEXT_DATA__` absent → None**: HTML has no `__NEXT_DATA__` script. `extract_nextjs_data` raises `ParseError`. Return `None`.
- **C3 — FetchError → None**: `WebScraper.fetch_rendered` raises `FetchError`. Return `None`.
- **C4 — max_tokens missing → None context, other fields OK**: `__NEXT_DATA__` parses but no `max_tokens` / `max_length` anywhere. `MSMetadata.context_window_k == None`, still returns non-None.
- **C5 — walker finds nested max_tokens**: `__NEXT_DATA__.props.pageProps.model.details.max_tokens` — the walker MUST find it regardless of depth.

### Steps

**C.1 — TDD: write C1–C5 tests FIRST** using a `WebScraper` protocol-style mock (simplest: monkeypatch `fetch_rendered` on a real `WebScraper` instance to return canned HTML strings, no browserless needed).

```python
# tests/test_ms_enrich.py — Phase C additions

def _make_next_html(payload: dict) -> str:
    """Build a minimal HTML fragment with __NEXT_DATA__ embedded."""
    import json as _json
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{_json.dumps(payload)}</script></body></html>'


class _FakeScraper:
    def __init__(self, response_map: dict[str, str] | Exception):
        self._map = response_map
    def fetch_rendered(self, url: str, **kw):
        if isinstance(self._map, Exception):
            raise self._map
        return self._map[url]


def test_c1_ms_happy_path():
    from ms_enrich import fetch_ms_metadata
    html = _make_next_html({
        "props": {"pageProps": {"model": {"max_tokens": 32768, "description": "S1 model"}}}
    })
    scraper = _FakeScraper({"https://modelscope.cn/models/Shanghai_AI_Laboratory/Intern-S1": html})
    md = fetch_ms_metadata("Shanghai_AI_Laboratory/Intern-S1", scraper=scraper)
    assert md is not None
    assert md.context_window_k == 32
    assert md.description == "S1 model"


def test_c2_ms_no_nextdata_returns_none():
    from ms_enrich import fetch_ms_metadata
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": "<html>no next data</html>"})
    assert fetch_ms_metadata("x/y", scraper=scraper) is None


def test_c3_ms_fetch_error_returns_none():
    from libs.web_scrape import FetchError
    from ms_enrich import fetch_ms_metadata
    scraper = _FakeScraper(FetchError("simulated"))
    assert fetch_ms_metadata("x/y", scraper=scraper) is None


def test_c4_ms_context_missing_partial_ok():
    from ms_enrich import fetch_ms_metadata
    html = _make_next_html({"props": {"pageProps": {"model": {"description": "no context"}}}})
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.context_window_k is None
    assert md.description == "no context"


def test_c5_ms_walker_finds_nested():
    from ms_enrich import fetch_ms_metadata
    html = _make_next_html({
        "props": {"pageProps": {"model": {"details": {"deeply": {"max_length": 16384}}}}}
    })
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md.context_window_k == 16
```

**Gate C.1 (must FAIL RED — `fetch_ms_metadata` not defined):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_ms_enrich.py::test_c1_ms_happy_path -x 2>&1 | tail -4
# Expected: ImportError: cannot import name 'fetch_ms_metadata'
```

**C.2 — Implement `fetch_ms_metadata` + `MSMetadata`:**

```python
# ms_enrich.py — Phase C additions

# NOTE: import path via project sys.path convention (tests already set it).
from libs.web_scrape import WebScraper, extract_nextjs_data, FetchError, ParseError

_MS_URL_FMT = "https://modelscope.cn/models/{}"
_CTX_KEYS = frozenset({"max_tokens", "max_length", "context_length", "max_position_embeddings"})
_DESC_KEYS = frozenset({"description", "summary"})
_GATED_KEYS = frozenset({"gated", "is_gated"})


@dataclass(frozen=True)
class MSMetadata:
    context_window_k: int | None
    description: str | None
    is_gated: bool
    source_url: str


def _walk_find(obj: Any, keys: frozenset[str]) -> Any | None:
    """DFS the payload for the first key from `keys` with a truthy value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and v:
                return v
            found = _walk_find(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk_find(item, keys)
            if found is not None:
                return found
    return None


def fetch_ms_metadata(ms_id: str, *, scraper: WebScraper | None = None) -> MSMetadata | None:
    """Fetch model-page metadata from modelscope.cn via web-scrape.

    Fail-open: returns None on any error (fetch failure, parse failure).
    """
    url = _MS_URL_FMT.format(ms_id)
    if scraper is None:
        # Real scraper (called from prod path — needs env vars set)
        import os
        from pathlib import Path
        scraper = WebScraper(
            cache_dir=Path("/tmp/ms-enrich-cache"),
            browserless_url=os.getenv("BROWSERLESS_URL"),
            browserless_token=os.getenv("BROWSERLESS_TOKEN"),
        )
    try:
        html = scraper.fetch_rendered(url, wait_for_selector="body")
        payload = extract_nextjs_data(html)
    except (FetchError, ParseError, OSError) as exc:
        print(f"[ms_enrich] WARN: MS scrape miss for {ms_id}: {exc}", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001 — fail-open contract
        print(f"[ms_enrich] WARN: MS scrape exception for {ms_id}: {exc}", file=sys.stderr)
        return None

    ctx_raw = _walk_find(payload, _CTX_KEYS)
    context_window_k: int | None = None
    if isinstance(ctx_raw, int) and ctx_raw > 0:
        context_window_k = ctx_raw // 1024

    desc = _walk_find(payload, _DESC_KEYS)
    gated = _walk_find(payload, _GATED_KEYS)

    return MSMetadata(
        context_window_k=context_window_k,
        description=str(desc) if desc else None,
        is_gated=bool(gated),
        source_url=url,
    )


# Extend __all__
__all__ = ["HFMetadata", "MSMetadata", "fetch_hf_metadata", "fetch_ms_metadata"]
```

**Gate C.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_ms_enrich.py -v 2>&1 | tail -15
# Expected: 13 passed (A3 + B1-B7 + C1-C5)
python -m ruff check scripts/kilo-benchmarks/ms_enrich.py scripts/kilo-benchmarks/tests/test_ms_enrich.py 2>&1 | tail -3
```

**C.3 — Live smoke — Optional (real browserless call — costs a few pennies of vps1 CPU):**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts/kilo-benchmarks')
from ms_enrich import fetch_ms_metadata
md = fetch_ms_metadata('Shanghai_AI_Laboratory/Intern-S1')
print(f'C.3 LIVE: {md}')
# Best-effort — the modelscope.cn __NEXT_DATA__ shape may not expose max_tokens on all pages.
# Non-fatal: if md is None or context is None, that's expected for MS-only orgs with thin pages.
"
```

**C.4 — `/fabrik-review` on Phase C — BLOCKING pool + native. Loop to no-op.**

**C.5 — Doc-sync + commit.** Stage only `scripts/kilo-benchmarks/ms_enrich.py` + `scripts/kilo-benchmarks/tests/test_ms_enrich.py`.

Commit trailer: `Agent-Phase: C`, `Agent-Context: MS Tier-2 SPA scraper (fetch_ms_metadata) + 5 behavior tests`.

---

## Phase D — Ingest orchestration + `--ingest-new` CLI + daily_refresh wire + docs

**Goal.** Extend `scrape_modelscope_catalog.py` with `ingest_new(unmatched_ms_ids, conn)` orchestrator and `--ingest-new` argparse flag. Wire into `daily_refresh.sh:337`. Ship CHANGELOG + INDEX updates. Final Tier-2 gate + `/fabrik-docs-review` + archive.

### Interfaces

**Consumes** (from Phases A–C):
- `libs.web_scrape.WebScraper` (available).
- `ms_enrich.HFMetadata`, `ms_enrich.MSMetadata`, `ms_enrich.fetch_hf_metadata`, `ms_enrich.fetch_ms_metadata`.
- Existing `scrape_modelscope_catalog._ms_to_agent_id_candidates`, `_ORG_MAP`, `apply_flags`, `fetch_ms_models`, `DB_PATH`.

**Produces:**
- **New function** `ingest_new(unmatched_ms_ids: list[str], conn: sqlite3.Connection, *, scraper: "WebScraper | None" = None) -> IngestResult` in `scrape_modelscope_catalog.py`:
  - For each unmatched id: try HF → fall to MS-scrape → fall to placeholder.
  - INSERT via `INSERT OR IGNORE INTO agents (...) VALUES (...)` — idempotent.
  - Returns count breakdown (`hf_enriched`, `ms_enriched`, `placeholder`, `skipped_dup`, `skipped_bad_id`).
- **New dataclass** `IngestResult`.
- **CLI flag** `--ingest-new` on `main()` — when set, after `apply_flags`, calls `ingest_new(unmatched, conn)`. Default OFF (preserves current behavior).
- **Modified `daily_refresh.sh:337`** — `_step "scrape_modelscope_catalog" "$VENV_PY" "$KB/scrape_modelscope_catalog.py" --ingest-new`.
- **New test** `scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py::test_d*` — end-to-end ingest coverage.
- **`CHANGELOG.md`** entry.
- **`INDEX.md`** entry for `ms_enrich.py`.

### Behavior Contract

- **D1 — HF-success → row inserted with real context**: `ingest_new(["internlm/internlm3-8b-instruct"], conn)` (with mocked `fetch_hf_metadata` returning `HFMetadata(context_window_k=32, ...)`) inserts one row with `id='internlm/internlm3-8b-instruct'`, `context_window_k=32`, `blocked=0`, `via_modelscope=1`, `input_cost_per_m=0`, `discard_reason=NULL`.
- **D2 — HF-miss → MS-scrape success**: `fetch_hf_metadata` returns `None`; `fetch_ms_metadata` returns `MSMetadata(context_window_k=32, ...)`. Row inserted with MS data, `blocked=0`, `discard_reason` mentions `MS-scrape`.
- **D3 — both miss → placeholder**: both return `None`. Row inserted with `context_window_k=128` (default), `blocked=1`, `discard_reason='needs_metadata_enrichment (MS-only, HF+MS scrape both failed)'`. Still `via_modelscope=1`, `reachable_with_existing_keys=1`.
- **D4 — idempotent**: run `ingest_new` twice on the same input. Second run inserts 0 rows (`INSERT OR IGNORE` guard).
- **D5 — `--ingest-new` off (default)**: running `main([])` without the flag never calls `ingest_new`. Verified via mocking.
- **D6 — bad id (no `/`)**: `ingest_new(["nonono"], conn)` skips it (returns `skipped_bad_id=1`), never crashes.
- **D7 — after ingest, `apply_flags` next run doesn't re-touch these**: because they're already `via_modelscope=1` (idempotent by the COALESCE guard in `apply_flags`).

### Steps

**D.0 — Preflight (repeat from A.0 for safety in this phase's context):**

```bash
grep -c "^MODELSCOPE_API_KEY=" /opt/fabrik/.env       # → 1
python -c "from libs.web_scrape import WebScraper"    # → no error
python -c "import sys; sys.path.insert(0,'scripts/kilo-benchmarks'); from ms_enrich import fetch_hf_metadata, fetch_ms_metadata"
```

**D.1 — TDD: write D1–D7 tests FIRST.**

Add to `scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py`:

```python
# Phase D additions

def _fresh_agents_db(tmp_path):
    """Build a fresh agents DB with the columns ingest_new INSERTs into."""
    dbp = tmp_path / "agents.db"
    con = sqlite3.connect(str(dbp))
    con.execute("""
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_id TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            input_cost_per_m REAL NOT NULL DEFAULT 0,
            output_cost_per_m REAL NOT NULL DEFAULT 0,
            context_window_k INTEGER DEFAULT 128,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 0,
            has_reasoning INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            blocked INTEGER DEFAULT 0,
            discard_reason TEXT,
            via_modelscope INTEGER DEFAULT 0,
            reachable_with_existing_keys INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    return con


def test_d1_hf_success_inserts_enriched(tmp_path, monkeypatch):
    from scrape_modelscope_catalog import ingest_new
    from ms_enrich import HFMetadata

    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr(
        "scrape_modelscope_catalog.fetch_hf_metadata",
        lambda ms_id, **kw: HFMetadata(
            context_window_k=32, has_reasoning=False, has_tools=False, has_vision=False,
            is_gated=False, model_type="internlm3", pipeline_tag="text-generation",
            source_url="https://huggingface.co/api/models/x",
        ),
    )
    r = ingest_new(["Shanghai_AI_Laboratory/Intern-S1"], con)
    assert r.hf_enriched == 1
    row = con.execute("SELECT * FROM agents WHERE via_modelscope=1").fetchone()
    assert row is not None


def test_d3_both_miss_placeholder(tmp_path, monkeypatch):
    from scrape_modelscope_catalog import ingest_new
    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_ms_metadata", lambda ms_id, **kw: None)
    r = ingest_new(["IIC/GUI-Owl-1.5-8B-Instruct"], con)
    assert r.placeholder == 1
    row = dict(zip(
        [c[0] for c in con.execute("SELECT * FROM agents").description],
        con.execute("SELECT * FROM agents").fetchone(),
    ))
    assert row["blocked"] == 1
    assert "needs_metadata_enrichment" in row["discard_reason"]
    assert row["via_modelscope"] == 1


def test_d4_idempotent(tmp_path, monkeypatch):
    from scrape_modelscope_catalog import ingest_new
    con = _fresh_agents_db(tmp_path)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_hf_metadata", lambda ms_id, **kw: None)
    monkeypatch.setattr("scrape_modelscope_catalog.fetch_ms_metadata", lambda ms_id, **kw: None)
    ingest_new(["IIC/x"], con)
    r2 = ingest_new(["IIC/x"], con)
    assert r2.placeholder == 0
    assert r2.skipped_dup == 1


def test_d5_ingest_new_flag_off_by_default(monkeypatch):
    """Running main without --ingest-new must NOT call ingest_new."""
    import scrape_modelscope_catalog as smc
    called = []
    monkeypatch.setattr(smc, "fetch_ms_models", lambda: [])
    monkeypatch.setattr(smc, "ingest_new", lambda *a, **kw: called.append(True))
    smc.main([])  # no --ingest-new
    assert called == []


def test_d6_bad_id_skipped(tmp_path):
    from scrape_modelscope_catalog import ingest_new
    con = _fresh_agents_db(tmp_path)
    r = ingest_new(["no-slash-id"], con)
    assert r.skipped_bad_id == 1
    assert r.hf_enriched == 0
```

**Gate D.1 (must FAIL RED — `ingest_new` doesn't exist):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py::test_d1_hf_success_inserts_enriched -x 2>&1 | tail -3
# Expected: ImportError: cannot import name 'ingest_new'
```

**D.2 — Implement `ingest_new` + `--ingest-new` CLI in `scrape_modelscope_catalog.py`.**

Add at the top (only the callables — the dataclasses `HFMetadata`/`MSMetadata` are unused inside `scrape_modelscope_catalog.py` itself; importing them here would trip ruff F401. Tests in `test_scrape_modelscope_catalog.py` and `test_ms_enrich.py` import them separately):

```python
from dataclasses import dataclass
from ms_enrich import fetch_hf_metadata, fetch_ms_metadata
```

Add:

```python
@dataclass
class IngestResult:
    hf_enriched: int = 0
    ms_enriched: int = 0
    placeholder: int = 0
    skipped_dup: int = 0
    skipped_bad_id: int = 0


_PLACEHOLDER_DISCARD = "needs_metadata_enrichment (MS-only, HF+MS scrape both failed)"


def _canonical_id(ms_id: str) -> str | None:
    """Return the first candidate agents.id from _ms_to_agent_id_candidates, or None if bad."""
    cands = _ms_to_agent_id_candidates(ms_id)
    return cands[0] if cands else None


def ingest_new(
    unmatched_ms_ids: list[str],
    conn: sqlite3.Connection,
    *,
    scraper: object | None = None,
) -> IngestResult:
    """Insert rows for MS IDs that don't yet exist in agents.

    Enrichment tiers (fail-open at each):
      1. HuggingFace Hub (fetch_hf_metadata) — for HF-mirrored models
      2. modelscope.cn SPA scrape (fetch_ms_metadata) — for MS-exclusive models
      3. Placeholder + blocked=1 — visible in browser MS chip, hidden from rankers

    Idempotent via `INSERT OR IGNORE` on agents.id PRIMARY KEY.
    """
    result = IngestResult()
    for ms_id in unmatched_ms_ids:
        canonical = _canonical_id(ms_id)
        if not canonical:
            result.skipped_bad_id += 1
            continue

        # Duplicate check (cheaper than round-tripping to INSERT OR IGNORE and reading rowcount)
        if conn.execute("SELECT 1 FROM agents WHERE id = ?", (canonical,)).fetchone():
            result.skipped_dup += 1
            continue

        provider, _, model_name = canonical.partition("/")
        row: dict[str, object] = {
            "id": canonical,
            "api_id": ms_id,
            "name": model_name,
            "provider": provider,
            "input_cost_per_m": 0.0,
            "output_cost_per_m": 0.0,
            "status": "active",
            "via_modelscope": 1,
            "reachable_with_existing_keys": 1,
        }

        # Tier 1: HF
        hf = fetch_hf_metadata(ms_id)
        if hf is not None:
            row.update({
                "context_window_k": hf.context_window_k if hf.context_window_k else None,
                "has_reasoning": int(hf.has_reasoning),
                "has_tools": int(hf.has_tools),
                "has_vision": int(hf.has_vision),
                "blocked": 0,
                "discard_reason": None,
            })
            result.hf_enriched += 1
        else:
            # Tier 2: MS SPA scrape
            ms = fetch_ms_metadata(ms_id, scraper=scraper)
            if ms is not None:
                row.update({
                    "context_window_k": ms.context_window_k,
                    "blocked": 0,
                    "discard_reason": None,
                })
                result.ms_enriched += 1
            else:
                # Tier 3: placeholder
                row.update({
                    "blocked": 1,
                    "discard_reason": _PLACEHOLDER_DISCARD,
                })
                result.placeholder += 1

        cols = [k for k, v in row.items() if v is not None]
        placeholders = ",".join("?" for _ in cols)
        collist = ",".join(cols)
        conn.execute(
            f"INSERT OR IGNORE INTO agents ({collist}) VALUES ({placeholders})",  # noqa: S608
            tuple(row[k] for k in cols),
        )
    conn.commit()
    return result
```

CLI flag in `main()`:

```python
def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--ingest-new", action="store_true",
                   help="INSERT rows for MS IDs missing from agents (with HF/MS-scrape enrichment)")
    args = p.parse_args(argv)

    ms = fetch_ms_models()
    if not ms:
        print("[ms-scraper] 0 MS models fetched — nothing to do", file=sys.stderr)
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        matched, updated, unmatched = apply_flags(conn, ms)
        # ... existing print statements ...
        if args.ingest_new and unmatched:
            print(f"[ms-scraper] --ingest-new: attempting ingest of {len(unmatched)} unmatched IDs")
            ir = ingest_new(unmatched, conn)
            print(
                f"[ms-scraper] ingest: hf={ir.hf_enriched} ms-scrape={ir.ms_enriched} "
                f"placeholder={ir.placeholder} dup={ir.skipped_dup} bad-id={ir.skipped_bad_id}"
            )
    finally:
        conn.close()
    return 0
```

**Gate D.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py -v 2>&1 | tail -20
# Expected: 15 passed (existing 8 + new D1-D6 = 14, plus already 1 from test_ms_enrich if collected)
python -m ruff check scripts/kilo-benchmarks/scrape_modelscope_catalog.py 2>&1 | tail -3
```

**D.3 — Wire into `daily_refresh.sh:337`.**

Edit line 337 to add the flag:

```bash
_step "scrape_modelscope_catalog" "$VENV_PY" "$KB/scrape_modelscope_catalog.py" --ingest-new \
```

Gate D.3:

```bash
bash -n scripts/kilo-benchmarks/daily_refresh.sh && echo syntax-ok
grep -c "scrape_modelscope_catalog.py --ingest-new" scripts/kilo-benchmarks/daily_refresh.sh
# → 1
```

**D.4 — Live end-to-end smoke (against real DB — VERY conservative: rollback via test-run branch or accept the ~22 new rows landing):**

```bash
# Create a dry-run wrapper (in-memory DB backed by the real one):
python -c "
import sqlite3, sys
sys.path.insert(0, 'scripts/kilo-benchmarks')
# Attach the real DB read-only, copy schema to an in-memory DB, count what WOULD land:
src = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
schema = src.execute(\"SELECT sql FROM sqlite_master WHERE type='table' AND name='agents'\").fetchone()[0]
mem = sqlite3.connect(':memory:')
mem.executescript(schema + ';')
# Copy existing IDs so the dup check works:
for (i,) in src.execute('SELECT id FROM agents'):
    mem.execute('INSERT INTO agents (id, api_id, name, provider) VALUES (?, ?, ?, ?)', (i, i, i.split('/')[-1], i.split('/')[0]))
mem.commit()
src.close()

# Fake the enrichers to skip live network calls:
import scrape_modelscope_catalog as smc
smc.fetch_hf_metadata = lambda x, **kw: None
smc.fetch_ms_metadata = lambda x, **kw: None

# Fetch real MS unmatched IDs (with the real MODELSCOPE_API_KEY):
ms = smc.fetch_ms_models()
matched, updated, unmatched = smc.apply_flags(mem, ms)
r = smc.ingest_new(unmatched, mem)
print(f'  Dry-run: unmatched={len(unmatched)} | hf={r.hf_enriched} ms-scrape={r.ms_enriched} placeholder={r.placeholder} dup={r.skipped_dup} bad-id={r.skipped_bad_id}')
"
# Expected output: unmatched=22, all placeholder (since we mocked both fetchers to None)
# This proves the plumbing works end-to-end without contaminating the real DB.
```

**D.5 — CHANGELOG entry** (append to `[Unreleased]`):

```markdown
### Added — Plan 2 follow-up: ModelScope new-row auto-ingest (HF+MS-scrape enrichment) (2026-07-10)

`scrape_modelscope_catalog.py` gains a `--ingest-new` flag that INSERTs previously-unmatched MS `/v1/models` IDs (Shanghai_AI_Lab Intern-S, PaddlePaddle ERNIE-4.5-PT, IIC/GUI-Owl, XiYanSQL, MedAIBase, MusePublic, OpenGVLab InternVL3.5-241B, OpenCompass, etc. — the 22 rows plan-2 explicitly deferred). Three-tier enrichment: HuggingFace Hub (partial + full config.json), modelscope.cn SPA scrape via vendored `web-scrape` module (browserless), fallback to `blocked=1` placeholder rows visible in the browser MS chip. Flag wired into `daily_refresh.sh:337` for automatic nightly coverage lift. All MS-only rows carry `input_cost_per_m=0` (MS is credits-billed, not per-token). New module `scripts/kilo-benchmarks/ms_enrich.py` (~180 LOC). Vendored `libs/web_scrape/` from `/opt/fabrik-lib/web-scrape/`.
```

**D.6 — INDEX entry** — add after existing `scrape_modelscope_catalog.py` line:

```markdown
- `scripts/kilo-benchmarks/ms_enrich.py` - ModelScope-specific metadata enrichment for `--ingest-new` mode. Two-tier fetch: HuggingFace Hub (`/api/models/<id>` + `/resolve/main/config.json`), fallback to modelscope.cn SPA scrape via vendored `libs/web_scrape/`. Both tiers fail-open (return None) so a single miss never blocks the ingest chain. Landed 2026-07-10 as plan-2 follow-up.
- `libs/web_scrape/` - Vendored copy of `/opt/fabrik-lib/web-scrape/web_scrape/` for JS-rendered SPA fetch. Public API: `WebScraper` (`fetch_static`/`fetch_rendered`), `extract_nextjs_data`. Runtime dep: `httpx>=0.27`. Used by `ms_enrich.fetch_ms_metadata`.
```

**D.7 — FULL final gate** (Tier-2, NOT --lean):

```bash
python scripts/final_gate.py --json 2>&1 | tail -8
# Expected: {"status": "success", "tier": 2, ...}
```

**D.8 — `check_convergence.py`.**

```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -5 || echo clean
```

**D.9 — `/fabrik-review` on cumulative Phase-A-to-D whole-plan diff — BLOCKING pool-first (multi-model breadth) + native Opus for auth/schema/migrations risk surface (Phase-D INSERT logic is schema-adjacent — Opus warranted). Loop to no-op.**

**D.10 — `/fabrik-docs-review` on cumulative changed docs surface (CHANGELOG + INDEX). Loop to no-op.**

**D.11 — Flip plan `Status: DRAFT → IN-PROGRESS` on Phase A start (retro-record) and `Status: EXECUTED 2026-07-10 (<final-commit>)` at completion. Archive the plan.**

```bash
# Update plan-lock JSON: status=released, completed_at
# git mv plan → archived/
git mv docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md \
       docs/development/plans/archived/2026-07-10-plan-2-modelscope-new-row-ingest.md
```

**D.12 — Final commit** (Phase D changes + CHANGELOG + INDEX + archive + Status flip):

```bash
git add scripts/kilo-benchmarks/scrape_modelscope_catalog.py \
        scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py \
        scripts/kilo-benchmarks/daily_refresh.sh \
        CHANGELOG.md \
        INDEX.md \
        docs/development/plans/archived/2026-07-10-plan-2-modelscope-new-row-ingest.md \
        .fabrik/plan-locks/2026-07-10-plan-2-modelscope-new-row-ingest.json
git diff --cached --name-only
git diff --cached | grep -cE "ms-[a-f0-9]{8}|Bearer TWr" && echo ABORT || echo clean
git commit -m "..."  # Phase D final commit with cumulative ingest details
```

---

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` refuses to start if any overlap another active plan-lock. Verified disjoint from `2026-07-10-plan-1-mobile-app-factory.md` (sibling plan touches `apps/mobile/**`, `packages/**`, `scripts/mobile-build/**` — zero overlap with this plan's kilo-benchmarks scope).

```
libs/web_scrape/                                                                          [CREATE Phase A]
scripts/kilo-benchmarks/ms_enrich.py                                                      [CREATE Phase A; MODIFY Phases B/C]
scripts/kilo-benchmarks/tests/test_ms_enrich.py                                           [CREATE Phase A; MODIFY Phases B/C]
scripts/kilo-benchmarks/scrape_modelscope_catalog.py                                      [MODIFY Phase D]
scripts/kilo-benchmarks/tests/test_scrape_modelscope_catalog.py                           [MODIFY Phase D]
scripts/kilo-benchmarks/daily_refresh.sh                                                  [MODIFY Phase D:337]
CHANGELOG.md                                                                              [APPEND Phase D]
INDEX.md                                                                                  [APPEND Phase D]
docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md                     [Status flip Phase A→D; git mv → archived/ Phase D.11]
.fabrik/plan-locks/2026-07-10-plan-2-modelscope-new-row-ingest.json                       [CREATE Phase A; MODIFY status=released Phase D.11]
```

**Concurrency check:** zero active plan-locks (verified this turn). Sibling `2026-07-10-plan-1-mobile-app-factory.md` is untracked (not staged, not active-locked) and has zero path overlap. Disjoint.

**Serialization points:** `CHANGELOG.md` + `INDEX.md` (append-only, safe under concurrent plans).

---

## Evidence

### Phase A evidence
- **`path:line`**: `/opt/fabrik-lib/web-scrape/README.md:1-70` — public API `WebScraper(cache_dir, browserless_url, browserless_token)`, `fetch_static`, `fetch_rendered`, `extract_nextjs_data`. Read this turn.
- **`path:line`**: `/opt/fabrik-lib/web-scrape/web_scrape/__init__.py:6` — real `__all__` export list confirms `WebScraper`, `extract_nextjs_data`, `FetchError`, `ParseError`, `RobotsError`, `WebScrapeError`. Read this turn.
- **`path:line`**: `/opt/fabrik-lib/web-scrape/requirements.txt:1` — `httpx>=0.27` only runtime dep. Verified.
- **`path:line`**: `libs/__init__.py:1` — `libs/` is already a Python package root in the project. Verified via `ls -la libs/`.
- **Live command output** (this planning turn):
  ```
  BROWSERLESS_URL=https://browser.vps1.ocoron.com
  BROWSERLESS_TOKEN=<redacted-32-char-token>
  ```
  (from `/opt/fabrik/.env`; already set for other services).

### Phase B evidence
- **`path:line`**: The spec's External deps table at `docs/superpowers/specs/2026-07-10-modelscope-new-row-ingest-design.md` — HF Hub two-endpoint pattern grounded live 2026-07-10.
- **Live command output**:
  ```
  HTTP 200 for https://huggingface.co/api/models/internlm/internlm3-8b-instruct
  keys: architectures, auto_map, model_type, tokenizer_config (partial config subset — no max_position_embeddings)
  tags: ['safetensors', 'internlm3', 'text-generation', ...]
  pipeline_tag: text-generation
  gated: False
  ```
- **Live command output**:
  ```
  HTTP 200 (after 307 follow) for https://huggingface.co/internlm/internlm3-8b-instruct/resolve/main/config.json
  max_position_embeddings: 32768
  model_type: internlm3
  ```

### Phase C evidence
- **`path:line`**: `/opt/fabrik-lib/web-scrape/README.md:20-30` — `WebScraper(browserless_url=..., browserless_token=...)` + `fetch_rendered(url, wait_for_selector=".price-card")`. Public surface.
- **Live command output** (this planning turn):
  ```
  https://modelscope.cn/models/Shanghai_AI_Laboratory/Intern-S1 → HTTP 200, 50KB, contains "max_tokens" key in JSON
  https://modelscope.cn/models/IIC/GUI-Owl-1.5-8B-Instruct → HTTP 200, 3.3KB (thin page — MS-exclusive)
  ```

### Phase D evidence
- **`path:line`**: `scripts/kilo-benchmarks/verify_openrouter_catalog.py:812-925` — sibling `ingest_new()` shape, INSERT column list, provenance to mirror. Read this turn.
- **`path:line`**: `scripts/kilo-benchmarks/scrape_modelscope_catalog.py:1-168` — existing module structure, `_ORG_MAP`, `_ms_to_agent_id_candidates`, `apply_flags`, `main`, `DB_PATH`. Read prior turns.
- **`path:line`**: `scripts/kilo-benchmarks/daily_refresh.sh:337` — MS step location. Verified via `grep -n` this turn.
- **Live command output**: `PRAGMA table_info(agents)` — verified `id` is `PRIMARY KEY` (`pk=1`, `notnull=0`), NOT NULL columns are `api_id`, `name`, `provider`, `input_cost_per_m`, `output_cost_per_m`.

### External research URLs
- `https://huggingface.co/docs/hub/api` (HTTP 200 verified 2026-07-10)
- `https://api-inference.modelscope.cn/v1/models` (55 models, HTTP 200 verified 2026-07-10)
- `https://huggingface.co/api/models/internlm/internlm3-8b-instruct` (HTTP 200 verified 2026-07-10)
- `https://huggingface.co/internlm/internlm3-8b-instruct/resolve/main/config.json` (HTTP 200 after 307 verified 2026-07-10)
- `https://modelscope.cn/models/Shanghai_AI_Laboratory/Intern-S1` (HTTP 200 verified 2026-07-10)

---

## Self-audit

### Grounding passes run this planning turn

1. **Pass 1** — read the spec (`Status: CONVERGED`, md5 `0c6f4480…` verified stable), `web-scrape` module README + requirements.txt, `verify_openrouter_catalog.py:812` sibling pattern, current `scrape_modelscope_catalog.py`, `daily_refresh.sh:337`, `agents` table schema (`PRAGMA table_info`), `.env` for browserless credentials, active rule packs from `select_rules.py` (19).
2. **Pass 2** — sanity checked HF two-endpoint pattern still works live this turn (already verified in Pass 1 of spec review; re-checked in Phase B evidence).

### Coverage check (What we already agreed ↔ phases)

- 3-tier enrichment fallback → Phase B (HF) + Phase C (MS SPA) + Phase D (placeholder)
- `INSERT OR IGNORE` idempotency → Phase D.2 code
- Automatic daily cron trigger → Phase D.3 wire
- `input_cost_per_m=0` for MS routes → Phase D.2 row template
- `blocked=1 + discard_reason` placeholder semantics → Phase D.2 + D3 test
- Vendored `web-scrape` module → Phase A
- All fail-open (per-tier + whole-run) → Phase B/C `try/except` + Phase D orchestration returning `IngestResult`
- CHANGELOG + INDEX + archive → Phase D.5–D.6, D.11
- FULL Tier-2 final gate + docs-review → Phase D.7 + D.10

Every agreed item maps.

### Cross-phase signature consistency

| Symbol | Produced (Phase, line) | Consumed (Phase, line) | Match? |
|---|---|---|---|
| `libs.web_scrape.WebScraper` | A.1 (copy) | C.2 (`scraper=WebScraper(...)`) | ✓ |
| `libs.web_scrape.extract_nextjs_data` | A.1 | C.2 (called inside `fetch_ms_metadata`) | ✓ |
| `libs.web_scrape.FetchError` | A.1 | C.2 (in `except` clause) | ✓ |
| `HFMetadata` | B.2 (dataclass) | D.2 (`from ms_enrich import HFMetadata`) | ✓ |
| `MSMetadata` | C.2 (dataclass) | D.2 (used implicitly via `fetch_ms_metadata`) | ✓ |
| `fetch_hf_metadata(hf_id, *, client=None) → HFMetadata \| None` | B.2 signature | D.2 (`fetch_hf_metadata(ms_id)`) | ✓ |
| `fetch_ms_metadata(ms_id, *, scraper=None) → MSMetadata \| None` | C.2 signature | D.2 (`fetch_ms_metadata(ms_id, scraper=scraper)`) | ✓ |
| `ingest_new(unmatched_ms_ids, conn, *, scraper=None) → IngestResult` | D.2 | (top-level orchestration; not consumed by later phases) | ✓ |
| `_canonical_id`, `_ms_to_agent_id_candidates`, `_ORG_MAP` | Existing / D.2 | D.2 orchestration | ✓ |

All names consistent. No `clear_layers()`-vs-`clearFullLayers()`-style drift.

### Fixed-point claim

This is a DRAFT. `/fabrik-plan-review` will run adversarial convergence. Not marking CONVERGED here.

---

## Residual unknowns

### Resolved during this plan

- **Which fabrik-lib module to vendor for JS-rendered SPA scrape?** — RESOLVED: `web-scrape` (spec `fabrik-lib verdict table`; module README read this turn matches use case).
- **Where does MS pricing come from for new rows?** — RESOLVED: `input_cost_per_m=0` (spec-locked: MS is credits-billed).
- **How to handle HF-miss + MS-scrape-miss rows?** — RESOLVED (user-approved): placeholder + `blocked=1 + discard_reason`.
- **Manual vs automatic trigger?** — RESOLVED (user-approved): automatic in `daily_refresh.sh`.
- **INSERT idempotency mechanism?** — RESOLVED: `INSERT OR IGNORE` on `agents.id PRIMARY KEY` (verified `pk=1` this turn).
- **Browserless credentials for MS SPA scrape?** — RESOLVED: `BROWSERLESS_URL` + `BROWSERLESS_TOKEN` already in `.env` (verified this turn).

### Still-open (each has a named resolution step, all self-service)

1. **modelscope.cn `__NEXT_DATA__` shape — where exactly is `max_tokens` nested?** SELF-SERVICE at Phase C.2 implementation: the `_walk_find` DFS walker searches every dict/list for keys in `_CTX_KEYS = {"max_tokens", "max_length", "context_length", "max_position_embeddings"}` regardless of nesting depth. Live-verify at Phase C.3 with one real MS model (Shanghai_AI_Laboratory/Intern-S1). If shape is completely different, adjust `_CTX_KEYS` at implementation time. **Not blocking** — walker is defensive.

2. **HF Hub rate limit courtesy sleep?** SELF-SERVICE: 22 IDs × 2 endpoints = 44 requests/day, well under any documented limit (~1000/min anonymous). Add a `time.sleep(0.05)` between requests at Phase B.2 implementation as a courtesy. If any 429 seen live, upgrade to `HF_TOKEN` auth (would be a Phase-D follow-up). **Not blocking** — well under rate limit at expected volume.

3. **Some MS models may be HF-gated (auth-required).** `fetch_hf_metadata` treats gated as normal (returns `is_gated=True`), still enriches from `/api/models`; `/resolve/main/config.json` may return 401 for gated models. Handled by Phase B `test_b3` (partial return). **Not blocking** — degrades to MS-scrape or placeholder gracefully.

4. **Existing sibling scraper `scrape_siliconflow_catalog.py` has the same class of unmatched IDs.** SELF-SERVICE: this plan explicitly scopes to MS. A follow-up plan mirroring this pattern for SF is a natural next step but out of this plan's scope. **Not this plan.**

Zero cross-AI dependencies, zero unanswered execution-blocking questions.

---

## Handoff

- **Next step (this command, automatic):** `/fabrik-plan-review docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md` — adversarial convergence to fixed point, flips `Status: DRAFT → CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md` — user-triggered.

**Expected wall clock:** Phase A (~15 min), B (~30 min), C (~30 min), D (~30 min). Total ~1h45m. Aligns with spec estimate.

**Expected spend:** ~$0.30 across per-phase `/fabrik-review` pool rounds + final whole-plan review.

**💡 fabrik-lib candidate flagged in the spec** (surfaced here for the handoff report per skill contract):
- **Name:** `catalog-enrichment` — progressive-fallback metadata fetcher for federated model catalogs.
- **Trigger for extraction:** third concrete use. Two so far: SF (unmatched — hypothetical future plan) and MS (this plan). Once a third vendor scraper (Groq/Cerebras/DeepInfra direct) needs the same shape, propose the fabrik-lib extraction via `UPSTREAM_FEEDBACK.md`.
- **Not this plan** — ship project-local per spec.
