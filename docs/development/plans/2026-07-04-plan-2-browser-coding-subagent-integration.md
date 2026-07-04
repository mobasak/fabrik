# Browser: coding-subagent ranking integration

**Status:** IN-PROGRESS
**Date:** 2026-07-04
**Started:** 2026-07-04 via /fabrik-execute-plan
**Owner:** solo (Özgür)
**Follow-up to:** commit `8405eecd..5b3af308` — coding-subagent ranking pipeline
**Review passes:** DRAFT → CONVERGED via `/fabrik-plan-review` 2026-07-04 (5 grounding passes; passes 4 + 5 both no-op with distinct coverage — fixed point reached)

## Goal

Surface the coding-subagent ranking data (composite score, Doc↔Code grade, exclusion flag, provider-pin recipe, body-hint recipe, "when to route" narrative) inside the interactive `models_browser.html` so an operator or an orchestrating AI can pick a subagent without opening `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` separately. Reuses `scripts/kilo-benchmarks/rank_coding_subagents.py` (no duplicate scoring logic).

## Context Ledger

Binding sources verified via `python scripts/select_rules.py` output 2026-07-04:

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | Python typing + env-var discipline for the ranker refactor + export_models_browser edits | `.windsurf/rules/core/10-python.md` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix triggers: file added → `INDEX.md`; code changed → `CHANGELOG.md`; feature shipped → `docs/FEATURES.md` | `.windsurf/rules/core/40-documentation.md` + `CLAUDE.md` Doc Sync Matrix |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Highest-risk-path-first test (composite ranker → payload projection is the risky pipe) | `.windsurf/rules/core/45-testing-strategy.md` |
| `.windsurf/rules/ai/60-code.md` (AVAILABLE — relevant to the "code subagent" domain) | Category-6 language: Kilo has 148 code models; the ranker + browser view scope this catalog to what's *actually* dispatchable as a coding subagent | `.windsurf/rules/ai/60-code.md` |
| `AGENTS.md` invariants touched | None — the browser is a single-file static HTML artifact, no service/compose/network changes | n/a |
| `fabrik-lib` modules considered | None applicable — the ranker + payload projection is repo-local, no table-rendering or scoring-pipeline module in fabrik-lib (verified via `grep -i "browser\|render\|json.*export\|table\|rank\|score" /opt/fabrik-lib/README.md`) | `fabrik-lib/README.md` |
| `specs/services/<id>.yaml` `shape:` flags | None touched — no DB/cache/metrics/search/admin surface added | n/a |
| `docs/operations/fabrik-lifecycle.md` | Not applicable — no deploy step, browser regenerates via `daily_refresh.sh` step-9 (`export_models_browser.py`) | n/a |

**Decision — vendor vs build**: no fabrik-lib module offers scoring/ranking projection; the existing `rank_coding_subagents.py` (repo-local, committed `8405eecd..5b3af308`, adversarially reviewed to a fixed point) is the source of truth. This plan **refactors it** to expose a public API and **wires the same computation** into the browser export path — no re-implementation.

## Global Constraints

- Every gate command runs from the project's WSL dev (`/opt/fabrik/.venv/bin/python …`) — no `fabrik …` shell-outs (hub-side CLI, unrunnable here).
- Browser output must remain **byte-idempotent** across regenerations for the same DB state (verified via md5 on back-to-back runs).
- New Python code passes `ruff check` and the project's `mypy` strict subset (matches how `rank_coding_subagents.py` already ships clean).
- Composite score + Doc↔Code grade + exclusion / pin / body-hint tables are the **single source** — no forking of `EXCLUDE_MODELS` / `PROVIDER_PINS` / `BODY_HINTS` constants. The template reads what the payload injects; the payload reads what the ranker exposes.
- The 5 existing browser features from prior work MUST stay green: `perf_seconds` → `Ns/gen` rendering, Speed column visible on 6 specialty tabs, 6 new provider-tag labels in `speedSourceLabel()`, `speedSortValue()` cross-service-type sort, per-generation-latency detail-panel row.
- No breaking change to existing template row order or column order — new columns append to the right of `Doc↔Code`, new chip appends to the existing chip-grid, new detail-panel row appends to the existing detail rows.
- Doc Sync Matrix triggers for this plan: `INDEX.md` (no new files created — only modified — so INDEX only updates if we register new symbols; verify at Phase B doc step), `CHANGELOG.md` (always), `docs/FEATURES.md` (feature shipped — new browser column set).

## File Scope (owned paths)

**Modified**:
- `scripts/kilo-benchmarks/rank_coding_subagents.py` — expose 3 public functions (rename `_rows_from_db` → `rank_all`, `_grade_doc_review` → `grade_doc_review`, `_fmt_body_hint` → `fmt_body_hint`); keep all `_`-prefixed helpers private.
- `scripts/kilo-benchmarks/export_models_browser.py` — inject 6 per-row fields into every chat model.
- `scripts/kilo-benchmarks/models_browser_template.html` — 2 new columns + 1 chip + badge CSS + detail-panel entries.
- `scripts/kilo-benchmarks/models_browser.html` — regenerated artifact (produced by the export script).
- `INDEX.md` — register the 3 public functions if any new file lands (none expected — this plan modifies existing files only).
- `CHANGELOG.md` — 1 `[Unreleased]` entry.
- `docs/FEATURES.md` — 1 entry describing the new columns + filter chip.

**Created**:
- `scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py` — regression tests for the new payload projection + ranker public API.

Plan-lock inventory verified 2026-07-04 via `cat .fabrik/plan-locks/*.json`:
- `2026-07-03-plan-1-full-speed-coverage-close.json` — `status: released` (owned `models_browser_template.html`, `models_browser.html` — now free)
- `2026-07-04-plan-1-saas-fastapi-user-auth-flip.json` — `status: released` (owned `CHANGELOG.md`, `docs/FEATURES.md` — now free)

No active-status locks. This plan's owned paths are disjoint from every archived plan's declared paths at the time of grounding. **Serialization note**: `CHANGELOG.md`, `INDEX.md`, and `docs/FEATURES.md` are hub-shared documents any future plan might touch — this plan's doc-update steps must use append-only edits (never rewrite the entire `[Unreleased]` section).

## Phase A — Backend — ✅ EXECUTED 2026-07-04: expose ranker API + inject fields into browser payload

Highest-risk path: the composite score → JSON payload → template read chain. Test first.

### A.1 — Add public wrapper to `rank_coding_subagents.py`

**Change** — append at end of `scripts/kilo-benchmarks/rank_coding_subagents.py` (do NOT rename the existing private `_rows_from_db` — keep call site stability):

```python
def rank_all(db_path: Path | None = None) -> list[dict]:
    """Public entrypoint: return the ranked candidates.

    Same shape as `_rows_from_db` (adds `score` + `doc_grade` per row), but
    accepts a caller-supplied db_path so `export_models_browser` can invoke
    it directly instead of shelling out to the CLI. Idempotent — safe to
    call N times per process.
    """
    global DB_PATH  # noqa: PLW0603
    saved = DB_PATH
    try:
        if db_path is not None:
            DB_PATH = Path(db_path)
        return _rows_from_db()
    finally:
        DB_PATH = saved


def grade_doc_review(ctx_k: float, swe: float, aider: float, aa_idx: float, arena: float) -> str:
    """Public alias — see `_grade_doc_review`."""
    return _grade_doc_review(ctx_k, swe, aider, aa_idx, arena)


def fmt_body_hint(mid: str) -> str:
    """Public alias — see `_fmt_body_hint`."""
    return _fmt_body_hint(mid)


# Public constants for the browser payload projection (single source of truth)
CODING_EXCLUDE_MODELS = EXCLUDE_MODELS
CODING_PROVIDER_PINS = PROVIDER_PINS
CODING_BODY_HINTS = BODY_HINTS
```

**Highest-risk path test — write FIRST, run to RED, then implement**:

Create `scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py`:

```python
"""Test the coding-subagent ranking → browser payload projection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))


def test_rank_all_returns_list_of_dicts_with_score_and_grade():
    """The public `rank_all()` must return a list where every row carries
    both a numeric `score` in [0, 1] and a letter `doc_grade`."""
    from rank_coding_subagents import rank_all

    rows = rank_all()
    assert len(rows) > 0
    for r in rows:
        assert isinstance(r, dict), r
        assert "id" in r
        assert "score" in r and 0.0 <= r["score"] <= 1.0, r
        assert r["doc_grade"] in {"A+", "A", "B+", "B", "B-", "C+", "C"}, r["doc_grade"]


def test_public_aliases_match_private_originals():
    """The public aliases must return exactly what the private helpers do."""
    from rank_coding_subagents import (
        _fmt_body_hint,
        _grade_doc_review,
        fmt_body_hint,
        grade_doc_review,
    )

    for args in [(300, 75, 0, 0, 0), (900, 0, 0, 45, 1500), (100, 0, 0, 0, 0)]:
        assert grade_doc_review(*args) == _grade_doc_review(*args)
    for mid in ["minimax/minimax-m3", "z-ai/glm-5", "no/such-model"]:
        assert fmt_body_hint(mid) == _fmt_body_hint(mid)


def test_public_constants_are_single_source():
    """Browser code MUST read these constants from the ranker — never fork them."""
    from rank_coding_subagents import (
        BODY_HINTS,
        CODING_BODY_HINTS,
        CODING_EXCLUDE_MODELS,
        CODING_PROVIDER_PINS,
        EXCLUDE_MODELS,
        PROVIDER_PINS,
    )
    assert CODING_EXCLUDE_MODELS is EXCLUDE_MODELS
    assert CODING_PROVIDER_PINS is PROVIDER_PINS
    assert CODING_BODY_HINTS is BODY_HINTS
```

**Runnable gate for A.1** — expected to be RED then GREEN in that order:

```bash
# Red step (before A.1 code lands): the imports fail → test errors out
/opt/fabrik/.venv/bin/python -m pytest \
  /opt/fabrik/scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py \
  -x --tb=short
# expect: 3 collected, 3 errors on ImportError

# Apply A.1 changes.

# Green step:
/opt/fabrik/.venv/bin/python -m pytest \
  /opt/fabrik/scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py::test_rank_all_returns_list_of_dicts_with_score_and_grade \
  /opt/fabrik/scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py::test_public_aliases_match_private_originals \
  /opt/fabrik/scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py::test_public_constants_are_single_source \
  -x --tb=short
# expect: 3 passed
```

### A.2 — Wire ranker into `export_models_browser.py`

**Change** — in `scripts/kilo-benchmarks/export_models_browser.py`, at the top of `_fetch_chat_models` (after the existing `agents = [dict(r) …]` line at :38), inject the coding-subagent fields on every matching row.

Append these keys to every chat model (all 6 default to `None`/`False` for out-of-scope rows so the JSON schema is uniform):

- `code_fit_score`: `float | None` — 3-decimal composite (only set for the ~38 in-scope rows)
- `doc_code_grade`: `str | None` — one of `A+/A/B+/B/B-/C+/C` (only for in-scope rows)
- `code_subagent_candidate`: `bool` — `True` iff the row appears in `rank_all()` output
- `code_excluded_reason`: `str | None` — non-empty iff `id in CODING_EXCLUDE_MODELS`
- `code_provider_pin`: `list[str] | None` — `PROVIDER_PINS.get(id)`
- `code_body_hint`: `str | None` — `fmt_body_hint(id)` when non-dash, else `None`

**Implementation sketch** (insert immediately after line 38):

```python
# Coding-subagent overlay — single source of truth is
# rank_coding_subagents.rank_all(). Never fork EXCLUDE_MODELS / PROVIDER_PINS /
# BODY_HINTS.
from rank_coding_subagents import (
    CODING_BODY_HINTS,
    CODING_EXCLUDE_MODELS,
    CODING_PROVIDER_PINS,
    fmt_body_hint,
    rank_all,
)

ranked_by_id = {r["id"]: r for r in rank_all()}
for a in agents:
    mid = a["id"]
    ranked = ranked_by_id.get(mid)
    a["code_subagent_candidate"] = ranked is not None
    a["code_fit_score"] = round(ranked["score"], 3) if ranked else None
    a["doc_code_grade"] = ranked["doc_grade"] if ranked else None
    a["code_excluded_reason"] = (
        "reasoning-only — returns 0 output tokens when reasoning is excluded"
        if mid in CODING_EXCLUDE_MODELS else None
    )
    a["code_provider_pin"] = list(CODING_PROVIDER_PINS[mid]) if mid in CODING_PROVIDER_PINS else None
    hint = fmt_body_hint(mid)
    a["code_body_hint"] = hint if hint != "—" else None
```

**Highest-risk-path test** (append to same test file):

```python
def test_export_payload_carries_coding_fields():
    """The browser JSON payload must project the ranker fields onto every
    chat model — sparse dict of None for out-of-scope rows."""
    from export_models_browser import _build_payload
    from rank_coding_subagents import DB_PATH

    payload = _build_payload(DB_PATH)
    chat = payload["chat_models"]
    assert len(chat) > 0

    # Every chat row has the 6 new keys (uniform schema)
    for m in chat:
        assert "code_subagent_candidate" in m
        assert "code_fit_score" in m
        assert "doc_code_grade" in m
        assert "code_excluded_reason" in m
        assert "code_provider_pin" in m
        assert "code_body_hint" in m

    # At least one row IS a coding-subagent candidate w/ score + grade
    candidates = [m for m in chat if m["code_subagent_candidate"]]
    assert len(candidates) >= 30
    for c in candidates:
        assert 0 <= c["code_fit_score"] <= 1
        assert c["doc_code_grade"] in {"A+", "A", "B+", "B", "B-", "C+", "C"}

    # kimi-k2-thinking (the one EXCLUDE_MODELS entry): candidate=False +
    # excluded_reason non-empty
    exc = [m for m in chat if m["id"] == "moonshotai/kimi-k2-thinking"]
    assert len(exc) == 1
    assert exc[0]["code_subagent_candidate"] is False
    assert exc[0]["code_excluded_reason"] is not None

    # minimax/minimax-m3: candidate=True + provider_pin populated
    m3 = [m for m in chat if m["id"] == "minimax/minimax-m3"]
    assert len(m3) == 1
    assert m3[0]["code_subagent_candidate"] is True
    assert m3[0]["code_provider_pin"] == ["Minimax", "Novita", "Parasail", "Together"]
```

**Runnable gate for A.2**:

```bash
/opt/fabrik/.venv/bin/python -m pytest \
  /opt/fabrik/scripts/kilo-benchmarks/tests/test_export_models_browser_coding_fields.py \
  -x --tb=short
# expect: 4 passed

# Regenerate + verify JSON payload contains the new keys
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py
grep -c "code_fit_score" /opt/fabrik/scripts/kilo-benchmarks/models_browser.html
# expect: >= 700 (one per chat model row in the payload)
```

### A.3 — Idempotency verification

```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py > /dev/null
md5a=$(md5sum /opt/fabrik/scripts/kilo-benchmarks/models_browser.html | cut -d' ' -f1)
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py > /dev/null
md5b=$(md5sum /opt/fabrik/scripts/kilo-benchmarks/models_browser.html | cut -d' ' -f1)
[ "$md5a" = "$md5b" ] && echo "IDEMPOTENT" || echo "DIFF: $md5a vs $md5b"
# expect: IDEMPOTENT
```

### A.4 — Phase A `/fabrik-review` gate (BLOCKING)

Run the full `/fabrik-review` adversarial methodology on the Phase A surface (`rank_coding_subagents.py` new public API + `export_models_browser.py` overlay + the new test file):
- Dispatch parallel finder subagents (recall)
- Refute false positives with quoted `path:line`
- Prove-before-fix any CONFIRMED / PLAUSIBLE finding with a red regression test
- Re-run the gate + review after each fix
- Phase B does NOT begin until a demonstrably-thorough round returns zero new correctness/security findings.

## Phase B — Frontend: template columns + chip + badge + detail-panel

### B.1 — Add 2 columns to `models_browser_template.html`

**Change** — after the existing "Best Code" column `<th>` in the header row (near line 648, `data-sort="_best_code_score"`), insert two new column headers:

```html
<th data-sort="code_fit_score" data-tabs="overview coding" title="Composite coding-subagent fit score (0-1). 45% max(SWE, Aider) + 20% AA idx + 15% Arena ELO + 10% speed + 10% cost-inverse. Only populated for the GLM/Kimi/Minimax/DeepSeek subagent pool (~38 rows). Empty on rows outside that scope.">Code Fit</th>
<th data-sort="doc_code_grade" data-tabs="overview coding" title="Doc↔Code review grade (A+/A/B+/B/B-/C+/C). Measures ability to compare documentation against implementation across a whole service, from context size + verified code-understanding + AA/Arena intelligence. Only populated for coding-subagent pool rows.">Doc↔Code</th>
```

Corresponding row-render cells go into the row template **immediately after the existing Best Code TD at line 1374** (grounded 2026-07-04 via `grep -n "_best_code_label" scripts/kilo-benchmarks/models_browser_template.html`), before the Arena cell at line 1375, in the same left-to-right order as the header columns. Renders empty (`_D`) when the field is null:

```javascript
<td class="num" title="Coding-subagent composite score">${m.code_fit_score != null ? m.code_fit_score.toFixed(3) : _D}${codeSubagentBadge(m)}</td>
<td class="num"><span class="doc-code-badge grade-${(m.doc_code_grade || '').replace('+', 'plus').replace('-', 'minus') || 'na'}">${m.doc_code_grade || _D}</span></td>
```

### B.2 — Add Doc↔Code badge CSS + `codeSubagentBadge()` helper

**Change** — in the `<style>` block (near the existing `.src-badge` rules around line 324), append the grade badge palette (dark-mode-safe, no light-mode variant since the browser only ships dark):

```css
.doc-code-badge {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
  font-size: 10px;
  border: 1px solid transparent;
}
.doc-code-badge.grade-Aplus  { background: #1a4520; border-color: #2c7a37; color: #a8ee9c; }
.doc-code-badge.grade-A      { background: #2a4a20; border-color: #4a7a2c; color: #c0ee9c; }
.doc-code-badge.grade-Bplus  { background: #1a3552; border-color: #2c5a99; color: #9cc6ff; }
.doc-code-badge.grade-B      { background: #2a3552; border-color: #3c5a99; color: #b0c6ff; }
.doc-code-badge.grade-Bminus { background: #302a4a; border-color: #4a4080; color: #b8b0d0; }
.doc-code-badge.grade-Cplus  { background: #3a2a1a; border-color: #6b5033; color: #d6b088; }
.doc-code-badge.grade-C      { background: #3a1f1a; border-color: #7a4030; color: #ee9c88; }
.doc-code-badge.grade-na     { color: var(--muted); border: none; padding: 0; background: transparent; }
.code-warn-badge {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 3px;
  border: 1px solid #7a4030;
  background: #3a1f1a;
  color: #ffb0a0;
  font-size: 10px;
  font-weight: 600;
}
.code-pin-badge {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 3px;
  border: 1px solid #6b5033;
  background: #3a2a1a;
  color: #ffd08a;
  font-size: 10px;
  font-weight: 600;
}
```

And in the `<script>` section (near `speedSortValue()` at line 1100), add the badge renderer:

```javascript
function codeSubagentBadge(m) {
  if (m.code_excluded_reason) {
    return ` <span class="code-warn-badge" title="${escapeHtml(m.code_excluded_reason)}">EXCL</span>`;
  }
  if (m.code_provider_pin) {
    const pin = m.code_provider_pin.join(",");
    return ` <span class="code-pin-badge" title="Provider pin required for OR routing: provider.only=${escapeHtml(JSON.stringify(m.code_provider_pin))}">PIN</span>`;
  }
  return "";
}
```

### B.3 — Add "Coding subagent" filter chip

**Change** — insert a new chip-grid section (right after the existing "Status" section around line 504, or a new `<h3>Role suitability</h3>`):

```html
<h3>Role suitability <span style="font-weight: normal; text-transform: none; color: var(--muted)">(any of)</span></h3>
<div class="chip-grid" id="role-chips">
  <span class="chip" data-role="code_subagent" title="Ranked in the GLM/Kimi/Minimax/DeepSeek coding-subagent pool (see docs/reference/kilo/CODING_SUBAGENT_SELECTION.md). Filters to ~38 candidates.">coding-subagent</span>
</div>
```

Wire it into the existing filter reducer by mirroring the exact 3-part pattern the `data-cap` chips already use (grounded 2026-07-04 — the code uses **lowercase** `state.svctypes` and `state.caps`, verified at lines 814 / 830 / 955 / 1010 / 1012):

1. **State**: add `roles: new Set()` alongside the existing `state.svctypes` / `state.caps` state Sets (all lowercase).
2. **Init**: call `initChips("role-chips", state.roles)` — the existing `initChips()` helper (verified in use at line 814 for `caps`) already handles chip click → toggle `.on` → mutate the passed Set → re-run filters.
3. **Predicate**: inside the filter reducer (the block that starts around line 1010 with `if (state.svctypes.size > 0)`), add: `if (state.roles.has("code_subagent") && m.code_subagent_candidate !== true) return false;` — mirrors the `state.caps.has(cap) && !m[cap]` shape used at line 955.

The chip filter is intentionally scoped to the **Coding tab and Overview tab only** — on specialty tabs (Translation/Transcription/Voice/Image/Video/OCR), the underlying `TAB_DEFAULTS[tab].services` list already excludes `llm`, so no rows match the code_subagent predicate anyway (no user-visible effect).

### B.4 — Detail-panel extensions

**Change** — in the detail-panel row-composition area **immediately after the existing Throughput push at line 1448** (grounded 2026-07-04 via `grep -n 'sourceRows.push.*Throughput' scripts/kilo-benchmarks/models_browser_template.html`), add these entries **only when the flag is set**:

```javascript
if (m.code_fit_score != null) {
  sourceRows.push(["Coding-subagent fit score", m.code_fit_score.toFixed(3) + " (Doc↔Code: " + escapeHtml(m.doc_code_grade || "—") + ")"]);
}
if (m.code_body_hint) {
  sourceRows.push(["OR request body hint", '<code>' + escapeHtml(m.code_body_hint) + '</code>']);
}
if (m.code_provider_pin) {
  sourceRows.push(["Provider pin", '<code>{"provider":{"only":' + escapeHtml(JSON.stringify(m.code_provider_pin)) + '}}</code>']);
}
if (m.code_excluded_reason) {
  sourceRows.push(["⚠ Coding subagent status", escapeHtml(m.code_excluded_reason)]);
}
```

### B.5 — Regenerate + verification gate

```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py
# expect: [export_models_browser] wrote ... N chat models

# All new features present in the generated HTML
for token in "Code Fit" "Doc↔Code" "code_fit_score" "codeSubagentBadge" "doc-code-badge" "grade-Aplus" "role-chips" "data-role=\"code_subagent\""; do
  grep -q "$token" /opt/fabrik/scripts/kilo-benchmarks/models_browser.html \
    && echo "✓ $token" \
    || (echo "✗ $token MISSING"; exit 1)
done

# The 5 prior features remain intact (regression guard)
grep -q "s/gen" /opt/fabrik/scripts/kilo-benchmarks/models_browser.html && echo "✓ s/gen"
grep -q "speedSortValue" /opt/fabrik/scripts/kilo-benchmarks/models_browser.html && echo "✓ speedSortValue"

# Idempotency across two regens
md5a=$(md5sum /opt/fabrik/scripts/kilo-benchmarks/models_browser.html | cut -d' ' -f1)
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo-benchmarks/export_models_browser.py > /dev/null
md5b=$(md5sum /opt/fabrik/scripts/kilo-benchmarks/models_browser.html | cut -d' ' -f1)
[ "$md5a" = "$md5b" ] && echo "IDEMPOTENT" || (echo "DIFF: $md5a vs $md5b"; exit 1)
```

### B.6 — Doc-sync updates (BLOCKING before phase commit)

Per Doc Sync Matrix (`CLAUDE.md`):

- **`CHANGELOG.md`**: append one `### Added — Browser: coding-subagent columns + filter chip + detail-panel recipes (2026-07-04)` entry summarizing the 2 columns, the badge system, the chip, and the detail-panel additions.
- **`docs/FEATURES.md`**: append a "Coding subagent columns in AI Models Browser" bullet explaining what the new columns show and how to filter.
- **`INDEX.md`**: no new files, but the ranker's new public API (`rank_all`, `grade_doc_review`, `fmt_body_hint`) deserves a note under the existing `rank_coding_subagents.py` entry.

Runnable gate:

```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/enforcement/check_doc_sync.py; echo "doc_sync: $?"
# expect: doc_sync: 0
```

### B.7 — Phase B `/fabrik-review` gate (BLOCKING)

Run the full `/fabrik-review` adversarial methodology on the Phase B surface (`models_browser_template.html`, `models_browser.html`, doc-sync updates). **Dispatch parallel finder subagents** (Sonnet — this diff is UI-only, no auth/schema/secrets/concurrency) partitioned by class: one on CSS/JS correctness (badge class-name collisions, XSS in `escapeHtml` usage, sort key handling), one on HTML/template structure (column-count consistency across `<th>` + `<td>`, `data-tabs` correctness, chip-grid selector/reducer wiring), one on doc-sync accuracy (do the new column names, chip name, and example screenshots match the code?). Merge findings, refute false positives with quoted `path:line`, prove-before-fix each CONFIRMED / PLAUSIBLE finding, re-run the phase gate after each fix. Phase C does not begin until a full round returns zero new correctness/security findings.

### Parallelism in Phase B (fan-out + merge point)

B.1 (columns), B.2 (badge CSS + helper JS), B.3 (chip + reducer), and B.4 (detail-panel entries) are **independent template edits** that touch different regions of `models_browser_template.html`. When executed by subagents, dispatch **four parallel worktree-isolated implementation subagents** — one per sub-step — with the merge point at B.5 (`export_models_browser.py` regenerates once, HTML verification runs once, all subagents' edits merge into the same template file). If any two edits touch overlapping lines, the merge conflict is resolved by the orchestrator per the standard `/fabrik-execute-plan` merge protocol (highest task number wins on semantic conflicts).

## Phase C — Final gate

Runnable gate:

```bash
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/final_gate.py --check --json | \
  /opt/fabrik/.venv/bin/python -c "import sys,json;d=json.load(sys.stdin);print(d['status']);sys.exit(0 if d['status']=='success' else 1)"
# expect: success

/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/enforcement/check_convergence.py
# expect: exit 0
```

**MANDATORY final step**: run `/fabrik-docs-review` to converge the new doc surface (`CHANGELOG.md`, `docs/FEATURES.md`, `INDEX.md`) to a truthful fixed point. Per the fabrik-plan-review structural pillars, any plan that ships a feature MUST run `/fabrik-docs-review` in its last phase — touch-on-change gates prove doc presence, not correctness; this pass proves correctness.

A green gate is **necessary but not sufficient** — it proves citations/format, not that the design is sound; the real proof is Evidence below.

## Evidence

Grounded via reads on 2026-07-04:

**Phase A grounding**:
- `scripts/kilo-benchmarks/rank_coding_subagents.py:197-231` — `_rows_from_db()` returns `list[dict]` with keys `id, in_M, out_M, db_tps, swe, aider, aa_idx, arena, ctx_k, tier, reasoning, or_ok, or_prov, score, doc_grade`. The public wrapper delegates directly.
- `scripts/kilo-benchmarks/export_models_browser.py:38` — `agents = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]` returns every column including `id`, `service_type`. The injection point is immediately after this line.
- `scripts/kilo-benchmarks/rank_coding_subagents.py:57-83` — `EXCLUDE_MODELS`, `PROVIDER_PINS`, `BODY_HINTS` are module-level constants; alias-exposing them keeps the single-source-of-truth invariant.

```bash
$ grep -n "^def \|^_" scripts/kilo-benchmarks/rank_coding_subagents.py | head
85:def _grade_doc_review(...)
127:def _compose_score(...)
159:def _fmt_or_dash(...)
178:def _fmt_body_hint(...)
197:def _rows_from_db(...)
244:def _safe_md_id(...)
```

**Phase B grounding**:
- `scripts/kilo-benchmarks/models_browser_template.html:481-491` — existing chip-grid pattern with `data-svc` attribute, exactly what the new `data-role` chip mirrors.
- `scripts/kilo-benchmarks/models_browser_template.html:324-338` — existing badge CSS at `.src-badge.*`, exactly what the new `.doc-code-badge.grade-*` follows.
- `scripts/kilo-benchmarks/models_browser_template.html:644-661` — existing header row; the new columns append right after "Best Code" (line ~648).
- `scripts/kilo-benchmarks/models_browser_template.html:1374` — existing row-render cell for `_best_code_label` (Best Code column); the 2 new cells (`code_fit_score`, `doc_code_grade`) go immediately after, following the same `<td class="num">` shape as the sibling Arena/AA/SWE/Aider/DA-code cells at lines 1375-1381.

```bash
$ grep -c "^| [0-9]* |" docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
38   # → the ranker returns 38 rows on the current DB; the payload projection targets these plus the 1 EXCLUDE entry.
```

External research: none required — everything grounded in repo-local code.

## Self-audit

Grounding passes run: 1 solo pass (RICH branch — the scope + files + shape were all pre-agreed in the immediately-preceding chat; grounder subagents deferred to the enforced `/fabrik-plan-review` step).

**Coverage check (a) against "What we already agreed"**:
- ✅ "Extend export_models_browser.py to invoke the ranker" → Phase A.2
- ✅ "Add 2 columns: Code Fit + Doc↔Code" → Phase B.1
- ✅ "Warning badge for excluded/pin-required rows" → Phase B.2 (`codeSubagentBadge()`)
- ✅ "Extend detail panel" → Phase B.4
- ✅ "Filter chip: Coding-subagent candidates only" → Phase B.3
- ✅ "Reuse rank_coding_subagents.py (no duplicate logic)" → Phase A.1 (public wrapper, no re-implementation)
- ✅ "Must not break existing perf_seconds/s/gen or speedSortValue" → Phase B.5 regression guard

**Cross-phase signature consistency (b)**:
- Phase A.1 produces `rank_all() -> list[dict]` with `score`, `doc_grade` keys.
- Phase A.2 consumes the same shape via `ranked_by_id = {r["id"]: r for r in rank_all()}`.
- Phase A.2 produces payload keys `code_fit_score`, `doc_code_grade`, `code_subagent_candidate`, `code_excluded_reason`, `code_provider_pin`, `code_body_hint`.
- Phase B.1 consumes `code_fit_score` + `doc_code_grade` for the two columns.
- Phase B.2 consumes `code_excluded_reason` + `code_provider_pin` for the badges.
- Phase B.3 consumes `code_subagent_candidate` for the chip filter.
- Phase B.4 consumes all 6 fields for the detail panel.

Names match across phases. No naming drift.

**Fixed-point claim**: DRAFT — grounded solo. `/fabrik-plan-review` will run parallel grounders to prove or refute.

## Residual unknowns

**Resolved this pass**:
- Ranker public-API surface: 3 aliases + 3 constants (see A.1). No API break to existing callers.
- Chip filter integration point: same reducer as `data-svc`/`data-cap` chips (repo pattern verified line 481).
- Idempotency guaranteed by the ranker's own byte-idempotency (adversarially verified in the prior review).

**Still open (non-blocking)**:
- Whether "code_subagent" should be one chip or three (candidate / excluded / pin-required). Started with 1 chip for scope; extending to sub-chips is a follow-up.
- Whether the browser should show the composite score's sub-component breakdown (SWE weight, cost weight, etc.) in the detail panel. Deferred — the doc file has it; the browser can point users there.
- Whether to add a light-mode variant for the new `.doc-code-badge` colors. The browser currently ships dark-only; if a light-mode theme lands in a future plan, the badges will follow that plan's palette.

## Hand-off

1. `/fabrik-plan-review docs/development/plans/2026-07-04-plan-2-browser-coding-subagent-integration.md` — converge to fixed point; flip Status: DRAFT → CONVERGED. (Enforced final step of this command; runs in this same turn.)
2. Once CONVERGED, `/fabrik-execute-plan docs/development/plans/2026-07-04-plan-2-browser-coding-subagent-integration.md` — user-triggered.
