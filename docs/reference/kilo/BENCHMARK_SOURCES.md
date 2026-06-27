# Benchmark Sources — Catalogue + Decision Record

**Last Updated:** 2026-06-27
**Owner contract:** edits to this file are made by AI agents (Claude, other Code agents) as decisions evolve. The operator decides WITH the agent in chat; the agent persists the verdict here.
**Consumed by:** any agent extending or pruning the daily benchmark pipeline ([wsl_startup_hook.sh](../../../scripts/wsl_startup_hook.sh) → [KILO_BENCHMARK_WORKFLOW.md](../../workflows/KILO_BENCHMARK_WORKFLOW.md)).

---

## 1. Decision criteria — when does a benchmark belong in our pipeline?

When evaluating a new benchmark source (or re-evaluating a wired one), score it against these six axes. **All six must pass for WIRED status.** Failing two or more axes → REJECTED unless the agent class changes.

| # | Axis | Pass criterion | Notes |
|---|---|---|---|
| 1 | **Skill alignment** | Measures something our agents actually do: code editing, terminal use, doc fixing, code review, multi-step task completion | Agent class today = **production code agents** (Kilo/Traycer wrappers). Not ML researchers, not chatbots. |
| 2 | **Task duration** | Single task completes in seconds–minutes | Hours-long runs (e.g. mls-bench's 5h exploration budget) measure a different category of agent |
| 3 | **Refresh shape** | Continuous leaderboard updates as new models drop | Periodic research-paper drops (e.g. once-a-year benchmark releases) age too fast to be useful in a daily pipeline |
| 4 | **Public access** | Stable JSON API OR scrapable HTML with a parser that survives layout changes | If access requires login / API key with paid quota, fail |
| 5 | **Contamination resistance** | Either refreshes its problem set OR is held-out / private | Static benchmarks become contaminated as models train on the answers |
| 6 | **Cost to integrate** | ≤ ~200 LOC scraper + tractable maintenance | A 1000-LOC scraper that breaks every week is not worth a third-decimal score signal |

Two safety levers:

- **Annual re-verification**: every WIRED source gets re-checked once a year against axes 1–6. If any axis fails, demote to REJECTED.
- **On agent-class change**: if Fabrik ever ships ML research agents or hours-long agents, re-run all REJECTED entries against the new class.

---

## 2. WIRED sources (currently in pipeline)

These four sources are consumed daily by `wsl_startup_hook.sh` step 5. Each fills specific columns in `kilo_agents.db`.

### 2.1 Chatbot Arena (LMSys / openlm.ai)

- **URL:** `https://openlm.ai/chatbot-arena/`
- **Scraper:** [scripts/kilo-benchmarks/scrape_benchmarks.py](../../../scripts/kilo-benchmarks/scrape_benchmarks.py)
- **What it measures:** Pairwise blind preference voting → Elo rating. Captures *general output quality* across an open-domain conversation distribution.
- **Blind spot:** Strongly biased toward chat/instruction-following; says nothing about whether the model can run a 12-step terminal task without losing state.
- **Refresh cadence:** Daily-ish (new votes accumulate continuously; new models added on launch).
- **Lands in:** `kilo_agents.db.agents.elo_score` (114 models updated in last successful run).
- **Verdict:** **WIRED** — useful as a stylistic-floor signal (a model with Elo < 1100 will probably also fail at agent tasks). Not load-bearing for role assignment.
- **Last verified:** 2026-06-25

### 2.2 Terminal Bench 2.0 (tbench.ai)

- **URL:** `https://www.tbench.ai/leaderboard/terminal-bench/2.0`
- **Scraper:** [scripts/kilo-benchmarks/scrape_benchmarks.py](../../../scripts/kilo-benchmarks/scrape_benchmarks.py)
- **What it measures:** Success rate on 80+ terminal tasks (run commands, read files, debug, iterate) under a fixed time budget. Closest analog to what Kilo/Traycer agents actually do.
- **Blind spot:** Doesn't measure code-editing quality directly — only end-state success.
- **Refresh cadence:** Updated as new models are submitted; major version revisions occasionally (2.0 is current).
- **Lands in:** `kilo_agents.db.agents.tbench_score` (45 models updated in last successful run).
- **Verdict:** **WIRED** — strongest single signal for our use case. Highest weight in role assignment.
- **Last verified:** 2026-06-25

### 2.3 BenchLM coding leaderboard

- **URL:** `https://benchlm.ai/api/data/leaderboard?category=coding&format=json`
- **Scraper:** [scripts/kilo-benchmarks/scrape_benchlm.py](../../../scripts/kilo-benchmarks/scrape_benchlm.py)
- **What it measures:** Composite coding score across multiple sub-benchmarks (HumanEval, MBPP, code-fix tasks). Provides a *coding-specific* gradient that Terminal Bench doesn't capture.
- **Blind spot:** Composite hides which sub-benchmark drives the score; can lag on newest models (50 entries / 85 mapped in last run).
- **Refresh cadence:** Periodic — new models added on launch.
- **Lands in:** `kilo_agents.db.agents.benchlm_score` (28 models updated in last successful run).
- **Verdict:** **WIRED** — complements Terminal Bench. Coding-quality second signal.
- **Last verified:** 2026-06-25

### 2.4 Artificial Analysis (artificialanalysis.ai)

- **URL:** `https://artificialanalysis.ai/leaderboards/models`
- **Scraper:** [scripts/kilo-benchmarks/scrape_artificial_analysis.py](../../../scripts/kilo-benchmarks/scrape_artificial_analysis.py)
- **What it measures:** Throughput (tokens/sec) + TTFT (time-to-first-token) + cost per million tokens. Operational signals — not quality.
- **Blind spot:** A fast cheap model can be worse at the actual task; throughput says nothing about correctness.
- **Refresh cadence:** Daily (their own continuous-measurement infrastructure).
- **Lands in:** `kilo_agents.db.agents.output_tokens_per_sec`, `ttft_ms`.
- **Verdict:** **WIRED** — load-bearing for the role-mapper's cost/latency floor decisions.
- **Last verified:** 2026-06-25

### 2.5 Supporting (not benchmarks, but feeds the pipeline)

These three aren't benchmarks but provide the *substrate* the benchmarks score against. Listed here to keep the dependency map honest.

| Source | URL | Role |
|---|---|---|
| OpenRouter models catalog | `openrouter.ai/api/v1/models` | Master chat + embeddings catalog (which models exist, pricing, context window) |
| Kilo CLI | local CLI | Per-model role hints from the Kilo team's own selection |
| Ollama API | local | Local-model availability for the on-prem fleet |

---

## 3. CANDIDATE sources — all CONDITIONAL with explicit triggers

**Status as of 2026-06-27:** all four candidates are CONDITIONAL — not wired today, and not under active consideration. Each entry below names the **specific trigger condition** that would re-open the decision. **Do not re-evaluate these sources unless the trigger fires** — re-evaluation cycles are how shopping lists creep into pipelines without justified need.

### 3.1 mls-bench.com — ML methods invention benchmark

- **URL:** `https://mls-bench.com/`
- **What it is:** Research benchmark from UC Berkeley + Princeton + Tsinghua. 140 tasks × 12 ML domains. Tests whether an AI agent can invent novel ML methods (loss functions, attention variants, samplers) that transfer across models, datasets, and seeds. 5-hour exploration budget per agent.
- **Why not wired today:** Measures ML method *invention* (research). Today's Fabrik agent class is *production code agents* (Kilo/Traycer wrappers). Different skill, different task duration (5h vs seconds–minutes), no public API.
- **Trigger to re-evaluate:** Fabrik ships ML-research agents (training models, designing architectures, hyperparameter exploration). Operator expects this within ~12 months per the 2026-06-27 review.
- **Status:** CONDITIONAL — re-evaluate on ML-research-agent rollout
- **Confirmed:** 2026-06-27

### 3.2 SWE-bench Verified

- **URL:** `https://www.swebench.com/` · leaderboard at `https://www.swebench.com/index.html#verified`
- **What it is:** 500 hand-verified real GitHub issues from 12 Python repos. The agent must produce a patch that passes the project's actual tests.
- **Why not wired today:** Terminal Bench already covers code-editing-via-real-tasks, and BenchLM covers coding-quality composite. SWE-bench would be a third coding-quality signal without a documented gap it fills. Adding it = three signals where two suffice = noise.
- **Trigger to re-evaluate:**
  - The Terminal Bench scrape (`scrape_benchmarks.py` → `tbench.ai`) fails for **>3 consecutive days** with no recovery in sight, OR
  - We observe role-mapper assigning models to coding roles whose real-world Kilo/Traycer output is visibly worse than alternatives at the same score (signal: rank-inversion bug reports).
- **Status:** CONDITIONAL — re-evaluate on Terminal Bench failure or quality-rank inversion
- **Confirmed:** 2026-06-27

### 3.3 LiveCodeBench

- **URL:** `https://livecodebench.github.io/leaderboard.html`
- **What it is:** Code-generation benchmark that *refreshes its problem set monthly* from LeetCode/AtCoder/Codeforces contests held AFTER each model's training cutoff. Designed to defeat contamination.
- **Why not wired today:** Contamination is not an observed problem in our pipeline. Our four current sources' rankings have been stable and match Kilo/Traycer real-world quality. Solving a problem we don't have.
- **Trigger to re-evaluate:**
  - Two or more new model releases produce **leaderboard scores that don't match observed Kilo/Traycer output quality** within the same calendar quarter (contamination signal: a model scores top-tier but underperforms in production), OR
  - One of the WIRED sources is publicly accused of contamination by a vendor or independent researcher.
- **Status:** CONDITIONAL — re-evaluate on observed contamination
- **Confirmed:** 2026-06-27

### 3.4 Aider Polyglot Benchmark

- **URL:** `https://aider.chat/docs/leaderboards/`
- **What it is:** 225 hard exercism problems across 6 languages (C++, Go, Java, JavaScript, Python, Rust). Measures multi-language code-editing capability.
- **Why not wired today:** Fabrik's codebase is ~95% Python. Multi-language scoring would not change any current role-mapper decision because no role requires non-Python capability.
- **Trigger to re-evaluate:** **>30% of new Fabrik projects (rolling 90-day window) are non-Python** — measured from `data/projects.yaml` by `project.yaml::type` field. Source: `sync_projects.py` reports.
- **Status:** CONDITIONAL — re-evaluate on non-Python project share crossing 30%
- **Confirmed:** 2026-06-27

---

## 4. Sufficiency rationale — why we stopped at 4 sources

A reader (human or AI) will eventually ask: "Isn't there a single source we could use instead?" or "Are 4 sources enough?" — the answer goes here so the question doesn't get re-litigated.

### 4.1 Each WIRED source maps to one role-mapper decision axis

The four wired sources are not redundant; they each anchor a specific decision the role-mapper makes:

| Role-mapper decision | Source it anchors | What dies if removed |
|---|---|---|
| Can this model complete agent tasks? | Terminal Bench 2.0 | Role assignment loses its primary capability signal — fall back to coding-only data |
| Is the model's code quality acceptable? | BenchLM (composite coding) | Coding-quality fallback gone — Terminal Bench measures end-state, not edit quality |
| Will the model fit the cost/latency budget? | Artificial Analysis | Operational floor gone — role-mapper can no longer reject too-slow or too-expensive models |
| Stylistic floor (chat quality smell test) | Chatbot Arena (Elo) | Marginal — Arena is the weakest current signal; see §4.4 |

Take any one away and a decision becomes ungrounded. Add a 5th source for the *same* decision and we add scrape weight + maintenance + a tie-break problem without new signal.

### 4.2 There is no superior single-source aggregator for our use case

| Aggregator | Why it doesn't replace the 4 |
|---|---|
| Artificial Analysis | Already wired — aggregates *operational* metrics (cost, speed). Does not aggregate quality. |
| HuggingFace Open LLM Leaderboard | Aggregates academic benchmarks (MMLU, HellaSwag, GSM8k). Wrong skill class — measures test-taking, not agent capability. |
| Vellum AI / general "best model" rankings | Higher-level mixes; lag primary sources by days/weeks; methodology opaque; vendor-incentive-aligned. |
| Picking one primary (e.g. just Terminal Bench) | Single point of failure. One bad scrape day → role-mapper goes stale. One methodology bias → systemic bias with no cross-check. |

There is **no single quality aggregator that is better than the individual sources we have**. Adding more individual sources doesn't change that — it just adds maintenance.

### 4.3 The criteria in §1 are the gate

The "shopping list" temptation is real — every quarter a new benchmark drops that's "the new gold standard." §1 exists so that *any* candidate (current or future) must pass six concrete axes. **Aspirational reasons don't count.** A candidate must address either:

- A demonstrated **gap** in role-mapper decisions (rank-inversion bug, scrape failure), OR
- A demonstrated **change** in our agent class (ML research agents, multi-language fleet)

If neither has fired, we add nothing.

### 4.4 The one open question — should we retire Chatbot Arena?

Of the four wired sources, **Chatbot Arena is the weakest** — it measures chat preference, not agent capability, and the role-mapper barely consults it. It is also harmless: the scraper is stable, costs no quota, and provides a no-cost stylistic-floor signal.

**Not retiring it now**, but the trigger condition is:
- A 4-week observation window where we deliberately set `arena_elo` weight to zero in the role-mapper and confirm no decisions change. If decisions are unchanged, retire it.

### 4.5 The one observed gap — free-tier model coverage

Live query against `kilo_agents.db` on 2026-06-27:

```sql
SELECT count(*) FROM agents
  WHERE input_cost_per_m = 0 AND status = 'active';
-- → 38 free models

SELECT count(*) FROM agents
  WHERE input_cost_per_m = 0 AND status = 'active'
    AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL
         OR coding_score IS NOT NULL OR livecodebench IS NOT NULL);
-- → 0 free models with ANY quality score
```

**38 free models in the catalog. Zero have benchmark scores.** Probable cause: scrapers see (for example) `deepseek-v4-flash` on Terminal Bench but our DB stores it as `deepseek-v4-flash:free` — the `:free` OpenRouter suffix breaks the join.

This is a **real, observable gap** that meets the §1 criteria. The fix is small: normalize the `:free` suffix in `scrape_benchmarks.py` and `scrape_benchlm.py` before joining. Cost: ~15 LOC, no new source needed.

**Tracked as open issue** (not done in this commit per operator decision 2026-06-27 to keep this commit doc-only).

---

## 5. Periodic review checklist

| Cadence | Action | Owner |
|---|---|---|
| Annual | Re-verify every WIRED source's URL, scraper, and axis scores. Update "Last verified" dates. | Operator + agent during regular maintenance |
| On new-model launch | Check if any CANDIDATE now fits better than a WIRED one for the new model class | Agent during the launch turn |
| On agent-class change | Re-run all REJECTED sources against the new class | Agent during the change turn |
| On scraper failure 3 consecutive days | Open a CANDIDATE→WIRED swap evaluation | Daily-pipeline log review |

---

## 6. How to wire a new source (after a CONFIRMED ✅ verdict)

1. Add a scraper in `scripts/kilo-benchmarks/scrape_<name>.py` following the shape of [scrape_benchlm.py](../../../scripts/kilo-benchmarks/scrape_benchlm.py) (httpx + cache file + JSON output).
2. Add a column to `kilo_agents.db.agents` for the new score.
3. Wire the scraper into [update_kilo_benchmarks.py](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py) so it runs as part of step 5b in the daily pipeline.
4. Add the new score column to the [role_mapper.py](../../../scripts/kilo-benchmarks/role_mapper.py) sort-key in the right priority slot.
5. Move the entry from §3 to §2 here, fill in the "Lands in" + "Last verified" fields.
6. Update [KILO_BENCHMARK_WORKFLOW.md](../../workflows/KILO_BENCHMARK_WORKFLOW.md) step 5b's table cell to mention the new source.
7. Run the pipeline once manually; verify the column populates in the DB.

## 7. How to retire a WIRED source (after a CONFIRMED ❌ verdict)

1. Delete the scraper invocation from `update_kilo_benchmarks.py`.
2. Leave the DB column in place (don't drop — keeps historical snapshots intact); just stop writing to it.
3. Remove the source from `role_mapper.py` sort-key.
4. Move the entry from §2 to §4 here, fill in the failing axes + re-evaluate trigger.
5. Update [KILO_BENCHMARK_WORKFLOW.md](../../workflows/KILO_BENCHMARK_WORKFLOW.md) step 5b's table cell.
