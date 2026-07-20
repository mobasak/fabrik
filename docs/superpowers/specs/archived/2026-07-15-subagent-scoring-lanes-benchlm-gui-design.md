# Subagent scoring lanes + BenchLM GUI catalog — design

**Status: CONVERGED**
**Date:** 2026-07-15
**Scope:** `/opt/fabrik` (hub-internal analysis tooling — `scripts/kilo-benchmarks/`). NOT a deployed service.

---

## Goal

Publish BenchLM's full **per-category** benchmark breakdown for every model in the model-browser GUI
(`models_browser.html`), auto-refreshed daily — and **structurally guarantee** those aggregate scores can
never enter the subagent-pool ranker.

This spec exists to draw a wall. The subagent pool already has a complete internal-scoring pipeline (below);
the risk is that a well-meaning future edit wires a broad public aggregate (BenchLM `agentic`, a paper
leaderboard topline) into that pipeline as a per-task prior — the exact "an aggregate that hides the profile"
error that this session repeatedly had to unwind. The deliverable is a *display-only* lane that has **no code
path** to `pick_models`.

---

## Context — the internal scoring pipeline (already built; documented here so the wall is explicit)

The two docs the subagents module reads are the **output** of our own evaluation, from three engines:

```
                          OUR OWN EVALUATION (3 engines)
  microbench_coding.py ──► agents.coding_score            ┐
   (EvalPlus HE+/MBPP+,      (+ scraped swe_bench_pct)     ├─► rank_coding_subagents.py
    we run it)                                             │        └─► CODING_SUBAGENT_SELECTION.md ┐
                                                           │                                         │
  microbench_terminal.py ─► tbench_task_results            │                                         ├─► libs/subagents/
   (Terminal-Bench/harbor,   └─► build_task_baselines.py   │                                         │   select.py
    we run it)                    └─► model_task_baseline  ├─► rank_task_subagents.py                 │   pick_models()
                                       (ops + code, TB2)   │        └─► TASK_SUBAGENT_SELECTION.md ───┘
  THE FLYWHEEL ───────────► subagent_runs (postgres)       │
   (set_quality on every     + quality_tier (derive_       │
    /fabrik-* dispatch)         quality_v2.py)             ┘
```

- **`CODING_SUBAGENT_SELECTION.md`** ← `rank_coding_subagents.py` (`OUT_PATH`, `rank_coding_subagents.py:51`).
  Sources: `agents.swe_bench_verified_pct` (scraped) + our own `agents.coding_score`
  (`microbench_coding.py`, EvalPlus). Auto price ceiling `$1.5/M out` (`rank_coding_subagents.py:105`).
- **`TASK_SUBAGENT_SELECTION.md`** ← `rank_task_subagents.py` (`OUTPUT_PATH`, `rank_task_subagents.py:146`).
  Ranking = `shrunk_q = (n·avg_q + K·tier_baseline)/(n+K)` blending:
  1. the **flywheel** (`subagent_runs`, `set_quality` verdicts — the primary per-task signal),
  2. **`model_task_baseline`** (per-task benchmark priors — ops+code from Terminal-Bench,
     `load_task_baselines`, `rank_task_subagents.py:71`),
  3. **`quality_tier`** (cold-start prior, `_load_quality_tiers`, `rank_task_subagents.py:321`).
- **Reader:** `libs/subagents/select.py::pick_models` parses both docs; `TASK_SUBAGENT_SELECTION.md` is read via
  env `SUBAGENT_SELECTION_DOC` (`select.py:222-235`) and its empirical order overrides the vendored `_TABLE`.

**Per-task honesty rule (already enforced):** a `model_task_baseline` row exists ONLY where a benchmark
genuinely measures that task on that model — today `ops` (TB2 system-administration+security) and `code` (TB2
software-engineering). Every other task type keeps the general `quality_tier` prior and is flywheel-primary. A
prior imported from a benchmark that never tested the model is a fabrication, and is prohibited.

**What this spec adds does NOT appear anywhere above.** That is the point.

---

## Chosen approach — enhance the existing scraper + a walled display table

1. **ENHANCE `scrape_benchlm.py` — extract all categories.** It already fetches the BenchLM API and reads
   `categoryScores`, but keeps only `coding` → `weighted_coding` (`scrape_benchlm.py:66-70`; that mapping is
   pre-existing and out of scope). Extend `parse_benchlm_entry` to retain **all** categories, and **union
   across per-category queries** — each `?category=<c>` returns its own set (grounded: `coding`=50 models,
   `math`=11 — the count varies by category, which is exactly why the union matters), and every row carries all
   8 `categoryScores` **keys** (values are often `null` — a model without a given eval), so querying each
   category and de-duping by model maximises coverage. **Scope note:** `scrape_benchlm.py` today writes a JSON
   cache (`benchlm_cache.json`, `save_cache`, `scrape_benchlm.py:122`); it has **no** DB write. The DB write is
   net-new plumbing (step 2), not a one-line addition.
2. **Land in a NEW table `benchlm_category_scores(model_id, category, score, scraped_at)`** — deliberately
   **not** columns on `agents`. `agents` is read by `derive_quality_v2.py` → `quality_tier` → the ranker's
   cold-start prior; a separate table the ranker never queries is the structural wall. Idempotent upsert on
   `(model_id, category)`. **The name→`agents.id` match already exists** in the consumer that writes
   `weighted_coding` today — `kilo_agents_db.py` imports `build_benchlm_map`/`fetch_benchlm_coding`
   (`kilo_agents_db.py:364`) and matches each agents row by normalized name against the benchlm map
   (`kilo_agents_db.py:482`). ⚠️ `build_benchlm_map` itself only builds a `{name → data}` dict and never touches
   `agents.id`; the actual join lives at `kilo_agents_db.py:482`. So the new per-category write extends **that**
   consumer (reuse its match, add a write to `benchlm_category_scores` keyed on the matched `agents.id`) — not a
   fresh matcher. An unmapped BenchLM name is skipped (display-only — a model not in our catalog has nothing to
   attach to).
3. **Join into `export_models_browser.py`** — a `LEFT JOIN benchlm_category_scores` on `model_id`, pivoted to
   one column per category, so the GUI shows the new fields. The export is `agents`-driven
   (`export_models_browser.py:44`, `SELECT * FROM agents`), so the join is added explicitly there.
4. **Wire into `daily_refresh.sh`** alongside the existing scrapers.

**Why lean / low-maintenance (best-practice, grounded 1c):** the leanest option is to extend a scraper that
already fetches this exact API rather than stand up a second fetch path — one HTTP source, one cron, no new
service. (Confirmed against CLAUDE.md § Pointers "Before new scripts: Grep scripts/ … Extend, don't
duplicate" and the existing `scrape_benchlm.py` — the API call already exists at `scrape_benchlm.py:32`.)

---

## Rejected alternatives

| approach | why rejected |
|---|---|
| **Columns on `agents`** (export's `SELECT *` picks them up free — simplest) | Breaches the wall: `agents` feeds `derive_quality_v2.py` → `quality_tier` → the ranker. Killed by the core requirement — these aggregates must be useless to internal scoring by construction. |
| **A new standalone BenchLM scraper** | Duplicates the fetch `scrape_benchlm.py` already does (CLAUDE.md: extend, don't duplicate). |
| **Scrape SWE-PRBench / SpecBench / CodeWiki per model** | Grounded impossible: SWE-PRBench publishes only a `leaderboard.png` (image; HF tree = `dataset/`, `README.md`, `leaderboard.png` — no results file); SpecBench/CodeWiki are arXiv paper tables. All list ~8 frontier models, **zero cheap-pool rows**. Nothing to scrape, and nothing that would inform a cheap-model decision. |
| **Feed BenchLM `agentic` into the ranker as a `research` prior** | It is a *blended* aggregate (BrowseComp is not broken out; `categoryScores` has one `agentic` number). Using it as a per-task score is the aggregate-hides-profile error. Display-only, never a prior. |

---

## External dependencies

| dependency | grounded fact | source + date |
|---|---|---|
| **BenchLM leaderboard API** | `GET https://benchlm.ai/api/data/leaderboard?category=<c>&format=json` — no auth, free. Returns `{lastUpdated, mode, methodologyVersion, approvedSnapshotId, models:[…]}`. **Model count varies by category** — `coding`=50, `math`=11 (fewer models have a math eval); the union across categories is what maximises coverage. Each model row: `{rank, model, creator, sourceType, overallScore, categoryScores:{agentic, coding, reasoning, multimodalGrounded, knowledge, multilingual, instructionFollowing, math}, inputPrice, outputPrice, evidenceStatus, methodologyVersion}`. Every row carries all **8 `categoryScores` keys**, but values are **often `null`** (a model without that eval). A model's scores are asserted stable across category queries (only ranking/membership changes) — non-load-bearing, since the upsert keys on `(model_id, category)` regardless. | Fetched live 2026-07-15 (this session): `?category=coding` and `?category=math` both re-verified. |
| Categories to surface | `agentic, coding, reasoning, math, instructionFollowing, knowledge, multilingual, multimodalGrounded` (frequently `null` per model — stored as NULL, shown blank). | same |

No BLOCKING external unknowns.

---

## fabrik-lib verdict

The ladder was run against the real `/opt/fabrik-lib/README.md` (read 2026-07-15). Three modules are adjacent
and were each adjudicated — not silently ignored:

| capability | verdict | why |
|---|---|---|
| Fetch a JSON leaderboard API | **BUILD (enhance existing `scrape_benchlm.py`)** — modules exist but don't fit | fabrik-lib has **`async-http-client/`** (singleton **async** httpx pool + circuit breaker, for a **deployed service** with sustained upstream traffic), **`web-scrape/`** and **`doc-crawl/`** (both for **HTML/JS page** scraping, not a JSON API). None fits: this is a **synchronous, one-shot daily-cron** scraper, and I am **enhancing an existing sync `httpx` call** (`scrape_benchlm.py:32`), not building an HTTP client. Vendoring `async-http-client` would mean rewriting a working sync cron to async to gain a connection pool + circuit breaker it does not need (8 requests, once a day) — a YAGNI service-grade dependency on a batch script. The resilience the scraper *does* need (timeout + fail-soft, below) is a few lines, not a module. |
| Model-name → `agents.id` matching | **VENDOR (in-repo)** | the join already runs in `kilo_agents_db.py:482` (matches each agents row by normalized name against `build_benchlm_map`'s dict, `kilo_agents_db.py:364`). Reuse that match; ⚠️ `build_benchlm_map` alone does NOT touch `agents.id` — it only builds the name-keyed dict. |

No fabrik-lib **core** enhancement (the change is a project-local enhancement to a hub-side script, not to a
fabrik-lib module) — so no `UPSTREAM_FEEDBACK.md` note is owed. Not a new-module candidate: bound to
`kilo_agents.db`'s schema and the BenchLM response shape (fails the "generic / ≥2 project types" bar).

---

## Shape / infra implications

**N/A — this is not a deployed service.** It is a script in the hub-side `kilo-benchmarks` analysis pipeline,
run by `daily_refresh.sh`. No scaffold type, no `specs/services/<id>.yaml`, no Docker, no `shape:` flags.

Store is the existing local **`kilo_agents.db` (SQLite)**. This is **not** a 12-Factor violation: the SQLite
ban (Factor X) applies to a *server-side backing service* for a deployed app; `kilo-benchmarks` is a local
analysis toolchain whose entire state is `kilo_agents.db`, exactly as every sibling script uses it. Flagging
this explicitly so `/fabrik-spec-review` does not mis-fire on it.

---

## Constraints

- **The wall (the core constraint):** `benchlm_category_scores` MUST have no reader among `rank_task_subagents.py`,
  `rank_coding_subagents.py`, `model_task_baseline`, or `derive_quality_v2.py`. Its only consumer is
  `export_models_browser.py`. A regression test asserts this (grep-level: no ranker/quality module imports or
  queries the table).
- **Fail-soft (resilience mandate):** a BenchLM outage MUST NOT wipe the display table. The scrape is
  timeout-bounded and **upserts, never truncates** — on a fetch failure it logs and leaves the prior rows
  intact (the GUI shows yesterday's scores rather than blanks). No circuit-breaker: a once-a-day 8-request
  batch script does not sustain the traffic a breaker exists to protect (this is why `async-http-client` is not
  vendored — see the fabrik-lib verdict). `scrape_benchlm.py` already fails soft this way for the coding scrape;
  the enhancement inherits it.
- **No fabricated priors:** unchanged from the existing rule — the GUI lane creates zero `model_task_baseline`
  rows.
- **Coverage reported, never faked:** an unmapped BenchLM model is skipped; the GUI shows blank for a category a
  model has no score in. No interpolation.
- **Extend, don't duplicate:** enhance `scrape_benchlm.py`; do not add a second BenchLM fetch.

---

## Testing approach

- **parse-all-categories:** from a real captured API row, all 8 categories are extracted (not just `coding`).
- **union-coverage:** querying N categories and de-duping yields the union of models, each with its full scores.
- **name mapping:** a BenchLM display name maps to the right `agents.id`; an unknown name is skipped, not guessed.
- **idempotent upsert:** re-running the scrape does not duplicate rows.
- **fail-soft:** a simulated BenchLM fetch failure leaves the prior `benchlm_category_scores` rows intact (no
  truncate, no wipe) and exits non-fatally.
- **the wall (regression):** a test asserting no ranker/quality-tier module reads `benchlm_category_scores`.
- **GUI join:** `export_models_browser.py` attaches the scores to the right model rows and shows blanks for gaps.

---

## Open / blocking unknowns

- **Resolved:** BenchLM API shape, coverage (11+ cheap-pool models), the non-scrapability of the paper
  benchmarks, the GUI data flow (`agents`-driven export), and the wall mechanism (separate table) — all
  grounded live this session.
- **Still open (non-blocking):** exact GUI column presentation (labels, ordering) — a display detail deferred to
  `/fabrik-plan-after-chat` / the export layer; does not change the design.
- **Out of scope (named for their own cycle):** the optional Phase-2 self-run of Terminal-Bench for the 16 cold
  models (ops/code, ~$7.80) and the optional SWE-PRBench self-run to audit flywheel `review` scores. Both are
  *internal-lane* work, unrelated to this GUI spec; each is its own spec→plan if pursued.
