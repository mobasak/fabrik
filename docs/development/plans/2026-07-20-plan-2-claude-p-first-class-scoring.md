# Score claude -p (native Claude tiers) as first-class CODER + REVIEWER candidates

Status: IN-PROGRESS
Date: 2026-07-20
Author: primary (Claude Opus 4.8)
Spec: [docs/superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md](../../superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md) (CONVERGED — the grounded source of truth; this plan inherits its verdicts, does not re-derive them)

Score `claude-code/{opus,sonnet,haiku,fable}` on the **review** and **code** benchmarks the SAME way and next
to the 57 OpenRouter models, so one shared ranking shows value across cheap models AND Claude. Cost is
**three subscription-derived numbers** (§ Global Constraints). Hub-internal `scripts/kilo-benchmarks/` tooling;
no DB / cache / deploy / GUI.

---

## What we already agreed (from the CONVERGED spec + this conversation)

- **Goal:** rank `claude-code/*` beside the pool on **review (F1×5)** + **code (pass@1×5)**, identical graders,
  identical single-shot transport. Coder+reviewer FIRST; research/docs/plan/spec are a *separate* judged-spec
  extension (out of scope here).
- **Chosen approach (spec §Chosen approach):** (1) one single-shot dispatch shim `claude_p.py`; (2) a
  namespace-branch (`model.startswith("claude-code/")`) in the two harnesses; (3) a three-number cost model
  `derive_cost.py`; (4) a `claude-code/*` gate carve-out; (5) a doc-emit preamble.
- **Cost = three numbers (operator's Gemini research, spec §2):** ① API-equivalent cache-aware $ (the RANKING
  axis, computed from raw tokens at list prices — NOT ccusage's dollar, NOT the CLI `total_cost_usd`);
  ② amortized subscription $ (context, shown); ③ weekly-quota draw (the 3→1 decision axis). "Cost is not the
  binding constraint — the weekly quota is."
- **Transport parity (spec §Rejected):** `claude -p` runs single-shot, NO `--allowedTools`, NO `--add-dir`,
  single turn — identical protocol to the OpenRouter single completion.
- **Rejected:** OpenRouter `anthropic/*` per-token; quota-% as a cost rate; tools+multi-turn for Claude;
  amortized-as-ranking; the CLI `total_cost_usd` as the number; plan/spec generation-scoring here.
- **Grounded external facts (spec, live 2026-07-20):** prices Opus $5/$25 · Sonnet 4.6 $3/$15 · Haiku 4.5
  $1/$5 · Fable 5 $10/$50 (a REAL published API price); cache read ×0.1 / write-5m ×1.25 / write-1h ×2.0;
  Max 20x $200/mo; CLI `--output-format json` `usage` keys are snake_case
  `input_tokens`/`output_tokens`/`cache_read_input_tokens`/`cache_creation_input_tokens`.
- **Vendor verdict (spec):** `claude-evaluator` VENDOR+ENHANCE; graders/gates/ranker VENDOR as-is;
  `derive_cost.py` BUILD (~60 lines, no fabrik-lib module fits); no fabrik-lib candidate.

**Branch: RICH** — the spec pins goal + approach + all external facts. No brainstorming.

---

## Global Constraints (every phase inherits these verbatim)

- **Scope:** hub-internal `scripts/kilo-benchmarks/` tooling — `shape:` **none** (no DB call, cache, `/metrics`,
  search, admin). No `compose.yaml`, no deploy, no GUI. `fabrik apply` is not involved.
- **Transport parity (BINDING):** the shim adds **NO `--allowedTools`, NO `--add-dir`, keeps a single turn**,
  and passes **`--system-prompt ""` (empty)** — the methodology/task rides in the USER prompt exactly as the
  OpenRouter call sends it (`run_direct`:520 builds `task = methodology("review") + _TASK…` and `_direct_call`
  sends `messages:[{role:user, content:task}]` with NO system field; coding `_one`:239 is user-only too).
  Splitting the methodology into `--system-prompt` would rig the comparison — a defect. (`max_tokens` is N/A to
  `claude -p` — it takes no such flag; not a rigging axis, a cap only truncates and both sides get enough.)
- **Cost = three numbers:** ① `api_equiv` is the value stored as the result's `cost_usd` (→ `cost_per_1k` →
  gate + ranking); ② `amortized` and ③ `quota_draw` are computed for the doc preamble, NOT the ranking axis.
  ① is a raw-token list-price **valuation** (compute it ourselves; never ccusage's `$` output, never the CLI
  `total_cost_usd`).
- **CLI usage keys are snake_case:** `input_tokens` / `output_tokens` / `cache_read_input_tokens` /
  `cache_creation_input_tokens` (NOT the `usage-history.json` camelCase `input/output/cacheRead/cacheCreation`).
- **Cache-write TTL:** the single `cache_creation_input_tokens` count gives no 5m-vs-1h split → default the
  write multiplier to **×1.25** (Claude Code's 5-min default).
- **No real Claude call in the unit suite:** every test mocks the subprocess / `claude_p_call`; fixtures only.
- **12-Factor / ops:** stdout only, no logfiles (XI); config via a JSON ratios file + env, **no secrets in
  code** (III); no daemonizing (VIII); a shelled-out binary (`npx @anthropic-ai/claude-code`) is the operator's
  existing on-box CLI (`claude` 2.1.215), not a new Dockerfile dep — this is dev-box tooling, not a container.
- **⚠️ CROSS-REPO HARD STOP:** the spec's "upstream to `claude-evaluator/UPSTREAM_FEEDBACK.md`" is a
  **`/opt/fabrik-lib` write** — FORBIDDEN from this repo. It is an **operator handoff item** (§ Residual
  unknowns), never a plan step.
- **Naming:** kebab-case files; Python modules snake_case; new `.py` carry the `# AFTER-EDIT:` coupling header.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | Python/typing/env patterns for the new modules | `select_rules.py` → ACTIVE |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, smoke vs integration, no real-network in unit tests | `select_rules.py` → ACTIVE |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default `fanout`→`set_quality` for the test-author + review fan-out; native for the risky adapter/decide | `select_rules.py` → ACTIVE |
| `fabrik-lib/claude-evaluator` (VENDOR+ENHANCE) | subprocess `--print --model --system-prompt` dispatch, fail-closed | vendored at `scripts/kilo-benchmarks/vendor/claude_evaluator/core.py:184` (`_call_cli`); canonical `/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py:188` |
| `fabrik-lib` cost ladder (BUILD justified) | no module computes a subscription-token valuation | `cost-budget/` (caps+ledger), `api-quota/` (X-RateLimit) — neither fits → `derive_cost.py` BUILD |
| `microbench_review.py` (VENDOR as-is + branch) | `_DirectResult` result shape + `run_direct` dispatch | `_DirectResult`:388 (fields `agent_id/model/text/error/out_tokens/cost_usd/latency_s/out_price_mtok`); `_direct_call`:458; `run_direct`:514; persist `record_flywheel`:607 → `model_review_metrics`:679 (13 cols) |
| `microbench_coding_direct.py` (VENDOR as-is + branch) | `_Gen` result shape + `generate` dispatch | `_Gen`:197 (`code/cost_usd/latency_s/out_tokens/error`); `generate`:205; `_or_run` call:243; `_bill`:225; persist `model_coding_metrics`:360 |
| `build_task_baselines.py` (carve-out) | eligibility gates are set-comprehensions | `review_eligible`:150 (precision≥0.99 · `$/1k`≤0.70 · p50≤10s · `$/run`<0.007 · score5≥3.5); `code_eligible`:234 (n_err≤1 · pass@1≥0.90 · `$/1k`≤3.5 · p50≤10s); consts:93-214 |
| `rank_task_subagents.py` (preamble emit) | full tables auto-include by `score5`; shortlists gate via eligibility | `_full_review_results_table`:440 (reads `model_review_metrics`, leads with `model_id` → parser SKIPS); `_full_coding_results_table`:502; `_selected_shortlists`:709 (imports `review_eligible`/`code_eligible`) |
| `load_task_ranking` parser | rows are parse-safe: reads `cells[0].isdecimal()` (rank) + last (n); middle cells safe | `scripts/kilo-benchmarks/libs/subagents/select.py:209` |
| claude-manager on-disk (② / ③ sources) | ② denominator + ③ proxy exist | `~/.claude/.claude-manager/usage-history.json` (`days[date].byModel[tier]` camelCase); `statusline.json` (`rateLimits.sevenDay.usedPercent`); `~/.claude/manager-accounts/` (3: can/mob/ob) |
| `claude_price_ratios.json` (NEW) | ①'s list prices + cache multipliers, grounded 2026-07-20 | Anthropic pricing (`platform.claude.com/docs/en/about-claude/pricing`) + prompt-caching doc |

**🆕 fabrik-lib candidate:** none (hub-only benchmark tooling — no ≥2-project reuse). **Shape/infra:** none.

---

## Phase A — Dispatch shim + three-number cost model

Two pure-new modules + a ratios file. Foundation: everything downstream consumes them. Fully unit-testable
with mocked subprocess + fixture json — no real Claude call.

**Files:**
- `scripts/kilo-benchmarks/claude_p.py` — the single-shot dispatch shim (ONE responsibility: run `claude -p`
  once, return `(text, usage)`).
- `scripts/kilo-benchmarks/derive_cost.py` — the three-number cost model (ONE responsibility: tokens → ①②③).
- `scripts/kilo-benchmarks/claude_price_ratios.json` — grounded list prices + cache multipliers (data).
- `scripts/kilo-benchmarks/tests/test_claude_p.py`, `tests/test_derive_cost.py`.

**Interfaces — Produces:**
- `claude_p.py`: `ALIASES: dict[str,str]` = `{"claude-code/opus":"claude-opus-4-8", "claude-code/sonnet":"claude-sonnet-5", "claude-code/haiku":"claude-haiku-4-5-20251001", "claude-code/fable":"claude-fable-5"}`;
  `claude_p_call(model: str, prompt: str, *, system: str = "", timeout: float) -> tuple[str, dict]` — returns
  `(text, usage)` where `usage = {"input_tokens":int, "output_tokens":int, "cache_read_input_tokens":int, "cache_creation_input_tokens":int}`; **fail-closed** (raises `RuntimeError` on non-zero exit / unparseable json, mirroring `_call_cli`:212). `system` defaults `""` — the harnesses pass the methodology in `prompt` for parity (§ Global Constraints).
- `derive_cost.py`: `api_equiv(usage: dict, model: str, ratios_path: Path | None = None) -> float` (①);
  `amortized_rate(usage_history_path: Path | None = None, accounts_dir: Path | None = None) -> float` (② $/token);
  `quota_snapshot(statusline_path: Path | None = None) -> float` (③ raw `sevenDay.usedPercent`, for before/after delta).

**Steps:**

0. **Preflight — toolchain + live json-shape (run FIRST; self-service, no user question):**
   `npx @anthropic-ai/claude-code --version` (or on-box `claude --version`, grounded 2.1.215) confirms the CLI
   exists **and** `test -z "$ANTHROPIC_API_KEY"` (an env key silently bills the API instead of the
   subscription — spec § Traps). Absent/unauth → `BLOCKED: claude-code CLI — searched: npx/claude --version,
   $ANTHROPIC_API_KEY — missing: authenticated on-box CLI on the Max subscription`. Then ONE real shape probe:
   `npx @anthropic-ai/claude-code --print --output-format json --model claude-haiku-4-5-20251001 "reply OK"` →
   confirm the top-level JSON wraps `usage` with the snake_case keys (§ Global Constraints) and note where the
   result text sits; `claude_p.py` (step 4) parses THIS observed shape. Cheap one-call check, quota-negligible.
1. **Write `claude_price_ratios.json`** — `{"claude-code/opus":{"in":5.0,"out":25.0}, "...sonnet":{"in":3.0,"out":15.0}, "...haiku":{"in":1.0,"out":5.0}, "...fable":{"in":10.0,"out":50.0}, "_cache":{"read":0.1,"write_5m":1.25,"write_1h":2.0}}` (per-M USD; grounded spec § External dependencies).
   Gate: `python -c "import json; d=json.load(open('scripts/kilo-benchmarks/claude_price_ratios.json')); assert d['claude-code/fable']['out']==50.0 and d['_cache']['read']==0.1"` → exit 0.
2. **Write `derive_cost.py`** with the three functions + `# AFTER-EDIT:` header. ① formula:
   `in·P_in + out·P_out + cache_read·P_in·0.1 + cache_creation·P_in·1.25` (÷1e6; default write ×1.25 per Global
   Constraints). ② = `($200 × len(listdir(accounts_dir))) ÷ Σ raw tokens over usage-history` (fail-soft to the
   research anchor `9.3e-8 $/tok` if history is empty). ③ = `quota_snapshot` returns `usedPercent` (caller
   deltas before/after).
3. **TDD the risky path first (①'s cache-aware math)** — write `test_derive_cost.py::test_api_equiv_cache_aware`
   asserting `api_equiv({"input_tokens":1_000_000,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}, "claude-code/opus") == 5.0` and a cache-read case
   (`1M cache_read → 0.5`) and a cache-write case (`1M cache_creation → 6.25` at ×1.25). Run it RED first
   (module absent), then implement to green.
4. **Write `claude_p.py`** — mirror `_call_cli`'s subprocess (`npx @anthropic-ai/claude-code --print
   --output-format json --model <ALIASES[model]> --system-prompt <system>`, stdin=prompt, `timeout`), parse
   the json result, pull `.usage` (snake_case keys, default 0 each), return `(result_text, usage)`; raise
   `RuntimeError` on non-zero exit (fail-closed). `# AFTER-EDIT:` header.

**Behavior Contract (test per behavior — `tests/test_claude_p.py` + `tests/test_derive_cost.py`):**
- `claude_p_call` returns `(text, usage)` from a **mocked** `subprocess.run` whose stdout is a json blob with a
  `usage` block → asserts snake_case keys captured (never the camelCase names).
- `claude_p_call` **fail-closed**: mocked non-zero exit → `RuntimeError` (not an empty/garbage `usage`).
- `ALIASES` maps all four `claude-code/*` → the live model IDs.
- `api_equiv` cache-aware (TDD above) + rejects an unknown model (KeyError/explicit).
- `amortized_rate` from a fixture `usage-history.json` + a 3-entry `accounts_dir` → the expected `$/token`;
  fail-soft to the anchor on empty history.
- `quota_snapshot` reads `sevenDay.usedPercent` from a fixture `statusline.json`.

**Closing sequence (every phase):** (1) `python -m pytest scripts/kilo-benchmarks/tests/test_claude_p.py scripts/kilo-benchmarks/tests/test_derive_cost.py -q` → all green;
(2) `python scripts/enforcement/check_doc_sync.py` → resolve any trigger in this phase's diff (new files → INDEX.md; code → CHANGELOG.md);
(3) **`/fabrik-review`** on the changed surface (`claude_p.py`, `derive_cost.py`, the ratios file, the tests) + everything they call — pool `fanout("review", …, mode="read_only")` finders (→ `set_quality`) + native `fabrik-reviewer` Opus for the fail-closed/subprocess path, refute → prove-before-fix, looped to `found:0, fixed:0`;
(4) commit (`Agent-Role: subagent`, `Agent-Phase: A`, explicit paths).

---

## Phase B — Harness namespace-branch dispatch (review + code)

Wire `claude-code/*` into both harnesses as a `model.startswith("claude-code/")` branch that builds the SAME
result object the graders already consume — from `(text, usage)` via `claude_p_call` + `derive_cost.api_equiv`.

**Files:** `scripts/kilo-benchmarks/microbench_review.py`, `scripts/kilo-benchmarks/microbench_coding_direct.py`,
`scripts/kilo-benchmarks/tests/test_claude_p_dispatch.py`; ③/② sidecar `scripts/kilo-benchmarks/claude_p_cost.json`.

**Interfaces — Consumes:** `claude_p.claude_p_call`, `claude_p.ALIASES`, `derive_cost.api_equiv/amortized_rate/quota_snapshot` (Phase A).
**Produces:** `claude-code/*` rows in `model_review_metrics` + `model_coding_metrics` (via the existing persist
path, `cost_usd`=①); `claude_p_cost.json` = `{"amortized_per_mtok":float, "quota_draw_pct":float, "built_at":str}` for Phase C's preamble.

**Steps:**
1. **review branch** — replace the `ex.map` dispatch lambda (`run_direct`:529) so a `mt[0].startswith("claude-code/")`
   model routes to the shim (else `_direct_call(...)` unchanged). `mt[1]` is the `task` (methodology+code, the
   user content) — passed as the shim's **prompt** with `system=""` for parity, NOT `--system-prompt`:
   `text, usage = claude_p_call(mt[0], mt[1], system="", timeout=timeout); cost = derive_cost.api_equiv(usage, mt[0]);
   _DirectResult(mt[0], text=text, out_tokens=usage["output_tokens"], cost_usd=cost, latency_s=<measured t0→t1>, out_price_mtok=ratios[mt[0]]["out"])`
   (`out_price_mtok` is $/M — matches the OR path's `cp×1e6` at `:509`). The grader (`f1(recall,precision)×5`)
   and `record_flywheel` are unchanged (they read `_DirectResult`, which "duck-types the AgentResult fields", :389).
2. **code branch** — in `_one` (`generate`:238, beside `_or_run`:243), add:
   `if model.startswith("claude-code/"): text, usage = claude_p_call(model, prompt, system="", timeout=…)` — where
   `prompt` is the SAME user content `_or_run` gets (`prob.prompt + starter + _TASK_SUFFIX`, :239, user-only, no
   system) — then `cost = derive_cost.api_equiv(usage, model); _Gen(extract_code(text), cost, dt, usage["output_tokens"], None)`
   (error/empty → `_Gen(None, cost, None, 0, "empty")`). The branch bypasses `_bill`/`_or_run` (computes ①
   directly). Grader (`pass@1×5`) + persist (`model_coding_metrics`:360) unchanged.
3. **③/② capture** — the run driver reads `quota_snapshot()` before + after the full `claude-code/*` sweep,
   writes `claude_p_cost.json` = `{amortized_per_mtok: amortized_rate()*1e6, quota_draw_pct: after-before, built_at}`.
4. **Concurrency:** `claude-code/*` calls run at **low concurrency** (they share the rotation quota) — cap the
   `claude-code/*` slice to `max_concurrency=2`, distinct from the pool's setting.

**Behavior Contract (`tests/test_claude_p_dispatch.py`):**
- review branch: `claude_p_call` **mocked** to return `("<review text>", {snake_case usage})` → the branch
  builds a `_DirectResult` with `cost_usd == api_equiv(usage, model)`, `out_tokens == usage["output_tokens"]`,
  `model == "claude-code/opus"` — asserts the grader path accepts it (duck-types AgentResult).
- code branch: mocked `claude_p_call` → the branch builds a `_Gen` with `code == extract_code(text)` and
  `cost_usd == api_equiv(...)`; the error path → `_Gen(code=None, error=…)` counted as `n_err`.
- an `openrouter/*` model still routes to `_direct_call`/`_or_run` (the branch is additive, no regression).
- **transport parity (highest-risk):** assert the review branch calls `claude_p_call` with `mt[1]` (the full
  `methodology + code` task) as the **prompt** and `system=""` — the methodology is NOT split into a system
  prompt (spy on the mock's call args). Same for code: prompt is the user content, `system==""`.
- `claude_p_cost.json` is written with the three keys from a fixture quota snapshot pair.

**Closing sequence:** (1) `python -m pytest scripts/kilo-benchmarks/tests/test_claude_p_dispatch.py scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py -q` → green;
(2) `check_doc_sync.py` (CHANGELOG);
(3) **`/fabrik-review`** on both harnesses' branches + callers — pool finders + native Opus for the dispatch/branch logic (a wrong-shape result silently corrupts the grade), looped to no-op;
(4) commit (`Agent-Phase: B`).

---

## Phase C — Gate carve-out + doc-emit preamble

Keep `claude-code/*` shortlist-visible past the eligibility gates (an expensive Opus ① now trips `$/1k`), and
surface ② + ③ in the review/code section preambles. Full tables already auto-include `claude-code/*`
(`ORDER BY score5`, `model_id`-led → parser-skipped) — **no change there**.

**Files:** `scripts/kilo-benchmarks/build_task_baselines.py`, `scripts/kilo-benchmarks/rank_task_subagents.py`,
`scripts/kilo-benchmarks/tests/test_claude_p_carveout.py`.

**Interfaces — Consumes:** `review_eligible`/`code_eligible` (build_task_baselines); `claude_p_cost.json`,
`derive_cost.amortized_rate` (Phase B/A). **Produces:** carved shortlists + a preamble line per section.

**Steps:**
1. **Carve-out** — in `review_eligible`:150 add `or m.startswith("claude-code/")` to the set-comprehension
   condition, same in `code_eligible`:234. (Verified: both are single comprehensions; `_selected_shortlists`
   imports them → the carve-out propagates.) So a `claude-code/*` model with ① `$/1k` > 0.70 (review) / > 3.5
   (code), or `$/run` ≥ 0.007, or `p50` > 10s stays in the shortlist; the value sort still ranks it by ①.
2. **Preamble** — in `_full_review_results_table`:440 and `_full_coding_results_table`:502 (and the shortlist
   sections), emit ONE italic line under the section header, mirroring the existing `_gate: …_` pattern
   (`rank_task_subagents.py`:822): `_claude-code/* rows: $/1k = ① API-equivalent (list-price valuation of subscription tokens); amortized ≈$<amortized>/M, run quota-draw ≈<quota>% of weekly cap (③) — from claude_p_cost.json_`. Read `claude_p_cost.json` fail-soft (missing → omit the line, never raise).

**Behavior Contract (`tests/test_claude_p_carveout.py`):**
- with a seeded temp `kilo_agents.db` where `claude-code/opus` has ① `$/1k` **above** `REVIEW_MAX_COST_PER_1K`
  (0.70), `review_eligible` STILL includes it (carve-out), while a non-claude model above 0.70 is excluded
  (the gate still bites everyone else).
- same for `code_eligible` above `CODE_MAX_COST_PER_1K` (3.5).
- the preamble line renders ② + ③ from a fixture `claude_p_cost.json`, and **omits** cleanly (no raise) when
  the sidecar is absent.
- a rendered `claude-code/*` row is **parser-safe**: `load_task_ranking` on the emitted doc does not crash and
  does not mis-read the row (leads with `model_id`, not a decimal → skipped by the full-table parser).

**Closing sequence (final phase):** (1) `python -m pytest scripts/kilo-benchmarks/tests/test_claude_p_carveout.py -q` → green;
(2) **doc updates (Doc Sync Matrix):** `INDEX.md` (new files `claude_p.py`, `derive_cost.py`,
`claude_price_ratios.json`), `CHANGELOG.md` (`### Added — claude -p first-class review+code scoring`) — run
`check_doc_sync.py` green; (3) **`/fabrik-review`** on the carve-out + emit + callers, looped to no-op;
(4) **`/fabrik-docs-review`** — converge INDEX/CHANGELOG to a truthful fixed point;
(5) run the FULL gate `python scripts/final_gate.py --check --json` (Tier 2) + `python scripts/enforcement/check_convergence.py` → `"status":"success"`; (6) commit (`Agent-Phase: C`).

---

## Behavior Contract

One test per user-observable behavior (risk-ordered; the parity + ①-math behaviors are the risky ones,
TDD-first). **Mocked:** `subprocess.run` / `claude_p_call` are mocked (NO real Claude call in the unit suite);
`usage-history.json` / `statusline.json` / `kilo_agents.db` are temp fixtures; the live CLI shape is proven
once by Phase A step 0's probe. Per-phase test-file assignments are in each phase's block above.

- **Given** a mocked `subprocess.run` returning JSON with a snake_case `usage` block, **When** `claude_p_call`
  runs, **Then** it returns `(text, usage)` with `input_tokens/output_tokens/cache_read_input_tokens/cache_creation_input_tokens` captured (never camelCase). *(Phase A)*
- **Given** a mocked non-zero CLI exit, **When** `claude_p_call` runs, **Then** it raises `RuntimeError`
  (fail-closed — never an empty `usage`). *(Phase A)*
- **Given** `usage={input_tokens:1e6}` for `claude-code/opus`, **When** `api_equiv` runs, **Then** it returns
  `5.0`; **Given** `cache_read_input_tokens:1e6`, **Then** `0.5` (×0.1); **Given** `cache_creation_input_tokens:1e6`, **Then** `6.25` (×1.25 default). *(Phase A, TDD-first)*
- **Given** a fixture `usage-history.json` + a 3-entry `accounts_dir`, **When** `amortized_rate` runs, **Then**
  it returns the expected `$/token`; **Given** empty history, **Then** it fails soft to the research anchor. *(Phase A)*
- **Given** a fixture `statusline.json`, **When** `quota_snapshot` runs, **Then** it returns
  `rateLimits.sevenDay.usedPercent`. *(Phase A)*
- **Given** a `claude-code/opus` review task + mocked `claude_p_call`, **When** the `run_direct` branch
  dispatches, **Then** it builds a `_DirectResult` with `cost_usd == api_equiv(usage,model)` and
  `out_tokens == usage["output_tokens"]`, accepted by `grade()`. *(Phase B)*
- **Given** a `claude-code/*` code task + mocked `claude_p_call`, **When** the `_one` branch dispatches,
  **Then** it builds `_Gen(extract_code(text), api_equiv(...), dt, out_tokens, None)`; the empty path →
  `_Gen(None, …, "empty")` counted as `n_err`. *(Phase B)*
- **Given** a `claude-code/*` review dispatch, **When** the branch calls `claude_p_call`, **Then** the full
  `methodology+code` task is the **prompt** and `system==""` (transport parity — methodology NOT split into
  `--system-prompt`); same assertion for code. *(Phase B, highest-risk)*
- **Given** an `openrouter/*` model, **When** either harness dispatches, **Then** it still routes to
  `_direct_call`/`_or_run` (additive branch, no regression). *(Phase B)*
- **Given** a temp `kilo_agents.db` where `claude-code/opus` has ① `$/1k` above `REVIEW_MAX_COST_PER_1K`
  (0.70), **When** `review_eligible` runs, **Then** it STILL includes `claude-code/opus` (carve-out) while a
  non-claude model above 0.70 is excluded; same for `code_eligible` above 3.5. *(Phase C)*
- **Given** a fixture `claude_p_cost.json`, **When** the ranker renders the sections, **Then** the preamble
  line shows ② amort + ③ quota; **Given** the sidecar is absent, **Then** the line is omitted (no raise). *(Phase C)*
- **Given** the emitted doc with a `claude-code/*` row, **When** `load_task_ranking` parses it, **Then** it
  does not crash and skips the `model_id`-led full-table row. *(Phase C)*

---

## Subagent Mandates

| Phase | Parallel? | Dispatch |
|---|---|---|
| A | inline build; parallel test-author + review | impl inline (2 small modules, tight coupling); per-behavior tests via pool `fanout("code", mode="write", owned_paths=<disjoint test files>)`; `/fabrik-review` = pool `fanout("review")` finders + native Opus (fail-closed path) |
| B | inline build; parallel review | impl inline (branch edits into existing harnesses — shared files, serialize); `/fabrik-review` pool + **native Opus mandatory** (wrong result-shape silently corrupts grades) |
| C | inline build; parallel review | impl inline; `/fabrik-review` pool + native Opus (gate logic) |

Pool runs record to the flywheel (`fanout` auto-records UNSCORED → `set_quality` back-fill); native produces no
`AgentResult`. `check_subagent_flywheel.py` WARNs on an unrecorded pool run.

---

## File Scope (owned paths)

```
scripts/kilo-benchmarks/claude_p.py                       # NEW
scripts/kilo-benchmarks/derive_cost.py                    # NEW
scripts/kilo-benchmarks/claude_price_ratios.json          # NEW
scripts/kilo-benchmarks/claude_p_cost.json                # NEW (runtime sidecar)
scripts/kilo-benchmarks/microbench_review.py              # MODIFY (branch)
scripts/kilo-benchmarks/microbench_coding_direct.py       # MODIFY (branch)
scripts/kilo-benchmarks/build_task_baselines.py           # MODIFY (carve-out)
scripts/kilo-benchmarks/rank_task_subagents.py            # MODIFY (preamble)
scripts/kilo-benchmarks/tests/test_claude_p.py            # NEW
scripts/kilo-benchmarks/tests/test_derive_cost.py         # NEW
scripts/kilo-benchmarks/tests/test_claude_p_dispatch.py   # NEW
scripts/kilo-benchmarks/tests/test_claude_p_carveout.py   # NEW
CHANGELOG.md                                              # append atop [Unreleased] — SERIALIZATION POINT (shared)
INDEX.md                                                  # add the 3 new files — SERIALIZATION POINT (shared)
```

**Disjoint** from the active lock `2026-07-20-plan-1-docs-truth-convergence` (it owns `docs/**` +
`check_doc_*`; this plan owns `scripts/kilo-benchmarks/*`). `CHANGELOG.md` + `INDEX.md` are root shared-append
files (every plan touches them) → append atop `[Unreleased]` / add rows only, never rewrite; `git diff --cached
--name-only` before each commit.

---

## Evidence

**Phase A** — the shim's model is real: `vendor/claude_evaluator/core.py:184` `_call_cli` shells
`--print --output-format --model --system-prompt` (grounded this session); the canonical is
`/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py:188`, fail-closed at :212 (`raise RuntimeError` on
non-zero exit). Prices grounded 2026-07-20 (spec § External dependencies, `platform.claude.com/docs/en/about-claude/pricing`).
```
$ sed -n '388,405p' microbench_review.py  → _DirectResult(agent_id,model,text,error,out_tokens,cost_usd,latency_s,out_price_mtok)
$ grep _Gen microbench_coding_direct.py    → _Gen(code,cost_usd,latency_s,out_tokens,error)  @197
```
**Phase B** — result objects duck-type the graders: `_DirectResult` "Duck-types the AgentResult fields
grade()/record_flywheel read" (`microbench_review.py:389`); `generate` builds `_Gen(extract_code(r.text), _bill(r,toks), dt, toks, None)` (`:248`), so the branch mirrors that shape from `(text, usage)`.
```
$ grep -n "usage.get\|completion_tokens\|_bill" microbench_coding_direct.py  → coding reads r.usage; branch reads claude_p usage
```
**Phase C** — carve-out point verified single set-comprehensions:
```
$ sed -n '150,166p' build_task_baselines.py  → review_eligible: {m for m,d in load_review_metrics(...).items() if <5 conds>}
$ sed -n '234,247p' build_task_baselines.py  → code_eligible:   {m for m,d in load_coding_metrics(...).items() if <4 conds>}
$ sed -n '709,730p' rank_task_subagents.py   → _selected_shortlists imports review_eligible, code_eligible
```
Full table auto-includes: `_full_review_results_table:440` "Rows lead with the provider/model id … load_task_ranking SKIPS this table"; `ORDER BY m.score5 DESC`. Parser: `libs/subagents/select.py:209` `load_task_ranking` (decimal-rank + n).

---

## Self-audit

- **Grounding passes run:** read `_DirectResult`/`_Gen` shapes, `run_direct`/`generate` dispatch, `_bill`,
  the eligibility comprehensions + all gate constants (`REVIEW_MAX_*`/`CODE_MAX_*`), the ranker render
  functions + `load_task_ranking`, the vendored `_call_cli`, and the on-disk `usage-history.json` /
  `statusline.json` / `manager-accounts/` (3 accounts). External facts inherited from the CONVERGED spec
  (live-grounded 2026-07-20 — fresh, same day).
- **(a) Coverage** — every "What we agreed" maps to a phase: shim → A; three-number cost → A (`derive_cost`) +
  B (① into `cost_usd`, ②/③ sidecar); namespace branch → B; carve-out → C; doc-emit preamble → C;
  transport parity → A (no tools, single turn) + tested in A/B; research/docs/plan/spec excluded → not planned.
- **(b) Cross-phase signature consistency** — `claude_p_call(model, prompt, *, system, timeout) -> (text, usage)`
  and `api_equiv(usage, model)` produced in A are consumed with those exact signatures in B; `claude_p_cost.json`
  keys (`amortized_per_mtok`/`quota_draw_pct`/`built_at`) produced in B are consumed in C's preamble.
- Fixed-point claim: **not yet** — this is the DRAFT; `/fabrik-plan-review` converges it.

---

## Residual unknowns

**Resolved (in-plan or self-service):**
- The `--output-format json` `usage` key names — GROUNDED snake_case (spec); Phase A's first shim test asserts
  them, so a CLI-format drift fails a unit test, not execution.
- ②/③ persistence — self-service: `derive_cost.amortized_rate()` reads `usage-history.json` live; ③ is a
  before/after `quota_snapshot` delta written to `claude_p_cost.json` (no DB schema change — honours the spec's
  "zero module change").

**Still open (non-blocking, self-service at run):**
- **Sonnet 5 intro pricing** — if scoring `claude-sonnet-5`, its live rate is the intro **$2/$10 through
  2026-08-31** (standard $3/$15 after). Self-service: `claude_price_ratios.json` is a data file the operator
  edits at run time; the default carries $3/$15 with a comment. (Scales ① linearly; no mechanism break.)
- (RESOLVED — folded into **Phase A step 0**: the toolchain + live json-shape probe runs first, so
  `claude_p.py` parses the observed shape; the unit suite mocks it. No longer a run-time discovery.)

**Operator handoff (CROSS-REPO — this plan must NOT execute):**
- **Upstream note to `/opt/fabrik-lib/claude-evaluator/UPSTREAM_FEEDBACK.md`** (a json/usage capture mode for
  `_call_cli`) — a `/opt/fabrik-lib` write, forbidden from this repo. Surface to the operator to apply hub-side.

**💡 fabrik-lib candidates:** none.

---

## Next

After `/fabrik-plan-review` converges this DRAFT → **`/fabrik-execute-plan docs/development/plans/2026-07-20-plan-2-claude-p-first-class-scoring.md`** (user-triggered; it mutates code).
