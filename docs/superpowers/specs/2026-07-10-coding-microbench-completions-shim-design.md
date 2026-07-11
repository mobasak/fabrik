# Coding microbench completions shim — design spec

**Status:** CONVERGED
**Converged:** 2026-07-10 via `/fabrik-spec-review` — 2 passes to md5 fixed-point `99350deb9f11fc381d699d6040ffded2`. Pass 1 made 3 edits: (a) enriched `get_human_eval_plus` / `get_mbpp_plus` grounding with live-verified problem-dict shape + counts (164 / 378) + accessor kwargs, (b) fixed a markdown pipe-in-code-cell collision in the `_transport.run` row (rewrote `float | None` → `Optional[float]` inside code fences to prevent MD056 table-column-count breakage), (c) resolved residual #1 (prompt-key stability) live and moved it from Still-open to Resolved. Pass 2 = zero edits + md5 identity.
**Post-CONVERGED external verification (Pass 3):** fabrik-lib AI (transport module owner) confirmed the `Result.cost_usd` retry-accounting contract via a 2-finder pool doc↔code review (both DOC ACCURATE) — single-attempt, never accumulates. This dissolves the original still-open residual #2 (cost aggregation under retries); the spec now carries it in the Resolved section with cited `path:line`. **A fresh Pass 3 `/fabrik-spec-review` verified the 10 newly-added cited `path:line`s against the real vendored `libs/subagents/*.py` code** (`_client.py:530` `_resolve_cost`; `:493/:516/:522/:526` raise paths; `loop.py:441-442` `total_cost +=`; `loop.py:360` `LoopOutcome.cost`; `agent.py:337,365` `AgentResult(outcome.cost_usd)`) — all 10 accurate. Pass 3 also swept axes A/B/C/D and found no other defects. Pass 4 = md5-identity no-op → convergence holds. Still-open list narrowed from 2 → 1.
**Date:** 2026-07-10
**Author:** primary (this session)
**Parent spec (inherited, CONVERGED):** `docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md`
**Blocks (this spec unblocks):** `docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md` (Phase E BLOCKED — 8/8 units failed with `json.decoder.JSONDecodeError` from evalplus's OpenAI-client wrapper mis-parsing OR's streaming SSE)

## Goal

Replace evalplus's default completion mechanism (`openai.OpenAI(base_url=…)` → `chat.completions.create(stream=True)`) — which mis-parses OpenRouter's streaming SSE — with a small completions shim (`openrouter_complete.py`) that reuses the **same** OR-compatible transport every pool subagent uses (`libs.subagents._transport.run` on top of `_client.OpenRouterClient`), then feed the produced samples JSONL back into evalplus's local eval step (`evalplus.evaluate(dataset, samples=<path>)` — offline, no OR call).

The result: the plan-2 Phase E live bench populates `agents.humaneval_score` + `agents.coding_score` for the 4 ByteDance-Seed target models, and `TOTAL_SPEND_USD` reflects real spend (sum of `Result.cost_usd` per completion) instead of the `0.00` placeholder.

**Zero changes** to plan-2's Phase A/B/C/D output: `write_scores`, `is_fresh`, `main()` argparse contract, tier ladder, FAMILIES prefix, snapshot fixture, and every test that isn't a mock of the old `subprocess.run(evalplus.evaluate ...)` path stays intact.

## Chosen approach

**Two-step decomposition of what evalplus does internally, at the caller boundary.** evalplus itself already supports this split — its `evaluate(dataset, samples=<path>)` param is a documented offline mode that skips generation and just runs the sandboxed pass@1 evaluation against a JSONL of pre-existing solutions (verified `evalplus/evaluate.py:127-129`). We just replace the completion generator.

### The shim (module-owner authored, delivered ready to drop in)

The completions shim was drafted by the fabrik-lib module owner ("them") who owns `libs/subagents/`. It sits at `scripts/kilo-benchmarks/openrouter_complete.py` (~90 LOC) and exposes three functions:

- **`complete(model, prompt, *, client, max_cost_usd=0.50) → str`** — one greedy OR call, returns raw completion text (empty string on a zero-token stall).
- **`generate_samples(model, problems: dict[str, str], out_path, *, max_concurrency=8, solution_key="solution", env_path=".env") → (Path, float)`** — batch-completes one problem per key, writes evalplus-shaped JSONL (`{"task_id", <solution_key>: <text>}` per line, in problems-dict order for determinism), returns `(output_path, total_cost_usd)`. Per-problem exceptions log `[error]` to stderr + write an empty solution (a SYSTEMATIC break is visible, not silently zero-scored). `finish_reason="length"` truncations log `[warn]`.
- **`_resolve_client(*, env_path)`** — internal; sources `OPENROUTER_API_KEY` from the process env, falling back to `libs.subagents._dotenv.load_env(env_path)`.

The shim uses:
- `libs.subagents._transport.run(model, messages, body={**_BODY}, liveness=_LIVENESS, client, max_cost_usd)` — verified at `libs/subagents/_transport.py:231` (already vendored).
- `libs.subagents._transport.Liveness(hard_timeout_s=180.0, first_token_timeout_s=60.0)` — verified at `_transport.py:41` (all fields real; other fields default per the dataclass).
- `libs.subagents._client.OpenRouterClient(api_key, referer, title)` — verified at `_client.py:282`.
- `libs.subagents._dotenv.load_env(repo, ...)` — verified at `_dotenv.py:141`. **Small quirk**: the module's `load_env` takes a REPO directory (not a `.env` file path), and the shim's default `env_path=".env"` would silently fall through the `try/except pass` if it doesn't resolve. Resolution: caller in `microbench_coding` passes `env_path="/opt/fabrik"` explicitly, OR relies on `OPENROUTER_API_KEY` already being in the env (which is how plan-2's Phase E launch already worked — `.env` grep upstream).

### Integration in `microbench_coding._run_one`

Current (plan-2 Phase E BLOCKED) `_run_one` runs:
```python
subprocess.run(
    [sys.executable, "-m", "evalplus.evaluate",
     "--backend", "openai", "--base-url", OR_URL,
     "--model", u.target, "--dataset", u.dataset,
     "--greedy", "--root", "./results"],
    cwd=u.unit_dir, env=env, ...
)
```

Refactor to two steps:
```python
def _run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str, float]:
    problems = get_human_eval_plus() if u.dataset == "humaneval" else get_mbpp_plus()
    # extract prompts — HumanEval+ uses "prompt", MBPP+ uses "prompt" too (per accessor return shape)
    prompts = {task_id: p["prompt"] for task_id, p in problems.items()}
    samples_path = u.unit_dir / "results" / f"{u.target.replace('/', '--')}_samples.jsonl"
    try:
        samples_path, cost = openrouter_complete.generate_samples(
            model=u.target,
            problems=prompts,
            out_path=samples_path,
            max_concurrency=8,
            env_path="/opt/fabrik",
        )
    except Exception as e:
        return u, False, f"generate_samples failed: {e!r}", 0.0
    # evalplus offline eval — reads samples_path, produces eval_results.json alongside
    try:
        result = subprocess.run(
            [sys.executable, "-m", "evalplus.evaluate",
             "--dataset", u.dataset,
             "--samples", str(samples_path)],
            cwd=str(u.unit_dir), env=env,
            capture_output=True, timeout=600, check=False,
        )
        if result.returncode != 0:
            return u, False, (result.stderr or b"").decode()[-2000:], cost
        return u, True, "", cost
    except Exception as e:
        return u, False, f"evalplus.evaluate failed: {e!r}", cost
```

`main()` accumulates `cost` per unit → `total_spend = sum(...)` → emits `TOTAL_SPEND_USD: {total_spend:.2f}`. plan-2's C8 test regex `^TOTAL_SPEND_USD: [0-9]+\.[0-9]+$` still matches; plan-2's E4 grep contract holds.

### Data flow

```
Phase-3 microbench_coding.main(--models=<4 Seed> --datasets=humaneval,mbpp --force)
    ↓ build_units  → 8 BenchUnit (target, dataset, spec, unit_dir)
    ↓ ThreadPoolExecutor(_run_one, units)  # max_workers=8
        ↓ for each unit:
        │  ├── problems = get_human_eval_plus() or get_mbpp_plus()
        │  ├── openrouter_complete.generate_samples(
        │  │       target, {task_id: prompt}, out_path=<samples.jsonl>,
        │  │       max_concurrency=8, env_path='/opt/fabrik')
        │  │       # ← libs.subagents._transport.run per problem, greedy temp=0
        │  │       # ← returns (path_to_jsonl, sum_of_cost_usd)
        │  └── subprocess.run(python -m evalplus.evaluate --dataset <ds> --samples <path>)
        │       # ← offline: reads samples.jsonl, sandboxes each solution,
        │       #   writes eval_results.json alongside
        ↓
    parse_eval_results per unit  → {base, plus} per (target, dataset)
    merge_dataset_results per target → 4-key composite
    write_scores per target → UPDATE agents SET humaneval_score, coding_score, last_verified
        ↓
    TOTAL_SPEND_USD: sum(per_unit_generate_samples_cost)
```

The eval step's sandbox is EvalPlus's own (multiprocessing.Process + rlimit), same as before. No shell metachar surface — arguments are passed as a Python list to `subprocess.run`, and the `--samples` path is built from `unit.unit_dir` (already regex-validated in build_units).

### Why this composition wins

- **No re-vendor needed** (module owner explicit): `_transport.run`, `_client.OpenRouterClient`, `_dotenv.load_env` are all in the current vendored copy at `scripts/kilo-benchmarks/libs/subagents/`.
- **No evalplus fork**: the OR-broken path (its OpenAI-client wrapper for `--backend openai`) is completely bypassed by the shim. The offline `evalplus.evaluate --samples <path>` path is well-tested and OR-agnostic.
- **Real cost tracking**: `generate_samples` returns actual `sum(Result.cost_usd)` per unit → `TOTAL_SPEND_USD` matches spec's ~$2.66 estimate ± the transport's cost calibration.
- **Proven OR-compat**: every pool subagent in this project (including Phase B/C reviews earlier in this session) runs on `_transport.run`. It handles OR's streaming SSE reliably.
- **Fail-visible per problem**: shim's per-problem exception → `[error]` on stderr + empty solution. Downstream pass@1 for that task = 0 (correct — the problem couldn't be attempted); overall pass@1 for the model reflects real capability with visible partial-failure attribution.

### Cost estimate

Same as parent plan-2: ~$2.66 for 4 Seed models × (HumanEval + MBPP) at real OR pricing. The shim's per-problem `max_cost_usd=0.50` cap prevents a single problem from consuming the whole budget on a runaway continuation; per-unit total is bounded by `AgentSpec.max_cost_usd=5.0` (plan-2 Phase C default).

## Rejected alternatives

- **Patch evalplus's OpenAI client upstream (Option A from plan-2 BLOCKED report)** — REJECTED: cross-project (evalplus is an external pip package), non-trivial (would need to identify the SSE-parsing bug in `evalplus/gen/util/api_request.py`, fix it, cut a release), and the module owner already offered the shim as a cleaner in-project solution.
- **Skip live-bench; wait for BenchLM to add Seed coverage (Option C)** — REJECTED: indefinite, defers plan-2's motivating gap (Seed models missing from `CODING_SUBAGENT_SELECTION.md`), and doesn't use the shim the module owner already drafted.
- **Follow-up plan using LiveCodeBench (Option D)** — REJECTED as the plan-3 approach (still a good follow-up plan-4 for contamination-resistant coverage): LCB adds different-benchmark scope creep. This spec's scope is narrowly "unblock plan-2 Phase E" — LCB coverage is a separate goal for a separate spec.
- **Use `evalplus.codegen` module + subclass its `OpenAI` decoder to fix SSE parsing** — REJECTED: still touches evalplus internals; brittle across evalplus releases. The shim decouples us from evalplus's completion-side code entirely.
- **Pool-dispatch each completion via `run_agents([AgentSpec], ...)` instead of a direct transport call** — REJECTED (design consideration): the pool's per-agent overhead (system prompt, tool-loop machinery, agent_id assignment, per-agent ledger write) is disproportionate to a single-shot temp=0 completion. The transport is the right abstraction level. The module owner's shim confirms this.

## External dependencies (all grounded live 2026-07-10)

| Dependency | Grounded fact | Source URL (fetched date) |
|---|---|---|
| **evalplus (already installed)** | `evaluate(dataset, samples: Optional[str] = None, ...)` supports offline eval mode when `samples` is a path to a JSONL — verified `evalplus/evaluate.py:127-129`. Reads the JSONL, sandboxes each solution, writes `eval_results.json`. No OR call in this mode. | `pip show evalplus` this session — v0.3.1 · `/opt/fabrik/.venv/lib/python3.12/site-packages/evalplus/evaluate.py:127` inspected this session |
| **evalplus.data.humaneval.get_human_eval_plus** | Signature `get_human_eval_plus(err_incomplete=True, mini=False, noextreme=False, version="default") -> Dict[str, Dict]`. Live-verified this session: returns **164 problems**; each `problem_dict` has keys `["task_id", "prompt", "entry_point", "canonical_solution", "test", "contract", "base_input", "atol", "plus_input"]` — the `"prompt"` field is the completion prompt. `evalplus/data/humaneval.py:42-52`. | file inspected + `python -c "from evalplus.data.humaneval import get_human_eval_plus; ...; print(list(next(iter(d.values())).keys()))"` this session |
| **evalplus.data.mbpp.get_mbpp_plus** | Signature `get_mbpp_plus(err_incomplete=True, mini=False, noextreme=False, version="default") -> Dict[str, Dict]`. Live-verified this session: returns **378 problems** (post-cleanup, matches spec's earlier MBPP+ = 378 claim); each `problem_dict` has keys `["task_id", "prompt", "entry_point", "canonical_solution", "base_input", "atol", "plus_input", "contract", "assertion"]` — same `"prompt"` field name as HumanEval. `evalplus/data/mbpp.py:181-193`. | file inspected + live count this session |
| **libs.subagents._transport.run** | Signature `run(model, messages: list[dict], *, body, liveness, client, max_cost_usd, on_token, on_state) → Result` at `_transport.py:231`. `Result` has `text: str`, `cost_usd: Optional[float]`, `finish_reason: Optional[str]` (raw source uses `float or None` union syntax; rewritten here to avoid a markdown-table pipe-collision). | vendored file inspected this session |
| **libs.subagents._transport.Liveness** | Dataclass at `_transport.py:41` with fields `idle_timeout_s`, `hard_timeout_s`, `restart_max`, `connect_timeout_s`, `first_token_timeout_s`. All shim-used field names real. | vendored file inspected this session |
| **libs.subagents._client.OpenRouterClient** | Constructor `(api_key, referer=None, title=None)` at `_client.py:282-287` (via `sed`'s `def __init__` scan). | vendored file inspected this session |
| **libs.subagents._dotenv.load_env** | `load_env(repo: str, *, keys)` at `_dotenv.py:141` — **takes a REPO directory, walks up to find `.env`**. Shim's default `env_path=".env"` fails to resolve; caller passes `env_path="/opt/fabrik"` or relies on env already being set. | vendored file inspected this session |
| **OpenRouter completion pricing (unchanged from parent)** | 4 Seed models: seed-1.6-flash $0.075/$0.30, seed-2.0-mini $0.10/$0.40, seed-1.6 $0.25/$2.00, seed-2.0-lite $0.25/$2.00. | parent spec §External deps + Pass-1 grounder (same session, still-fresh) |

## fabrik-lib verdict table (vendor→enhance→build)

| Capability | Verdict | Module + why | Upstream note |
|---|---|---|---|
| OR completion transport (SSE-robust, cost-tracking, liveness/idle timeouts, streaming) | **vendor as-is** | `libs.subagents._transport.run` — already vendored via plan-2 Phase A step 2b; used by every pool subagent in this session, proven OR-compat. This is the primary unblock. | none — no changes to the transport |
| OR HTTP client (referer/title/api-key config) | **vendor as-is** | `libs.subagents._client.OpenRouterClient` — same as above. | none |
| Env-var loading from `.env` | **vendor as-is** (with caller-side quirk noted) | `libs.subagents._dotenv.load_env(repo: str, ...)` — takes a directory, not a file. Caller in `microbench_coding` passes `env_path="/opt/fabrik"` or relies on env already set. | none — module's contract stands |
| Batch completion → JSONL for evalplus | **build** (~90 LOC, project-local) | `scripts/kilo-benchmarks/openrouter_complete.py` — the shim, authored by the fabrik-lib module owner as a usage example. **Not** a fabrik-lib candidate (module owner explicitly declined: it's project-glue that composes the module, not a new module). | none |
| evalplus offline eval (`--samples <path>` mode) | **external dep — already installed via plan-2 Phase A** | `evalplus >= 0.3.0` in `pyproject.toml`. Just call it with different args. | none |
| Integration into `microbench_coding._run_one` (2-step: shim → evalplus offline eval) | **build** (~40 LOC delta to `_run_one`, project-local) | Existing `microbench_coding.py` from plan-2. Replaces the single `subprocess.run(evalplus.evaluate --backend openai ...)` call with 2 steps: `generate_samples` then `evalplus.evaluate --samples`. | none |
| Everything else in `microbench_coding` (write_scores, is_fresh, main, argparse, BenchUnit, validation) | **unchanged from plan-2** | plan-2 Phase A/B/C/D committed already; only `_run_one` changes and the test that mocks `subprocess.run` needs a 2-mock update. | none |

**fabrik-lib consult performed:** re-grepped `/opt/fabrik-lib/README.md` for `completion|openrouter|OR client|transport|dotenv` after the module owner's shim landed. Only hit is `subagents/` (already adopted). The transport is not exposed as a separate module because it's the pool's private plumbing — using it directly from a project is the module owner's sanctioned "usage-example" pattern (their words).

## Shape/infra implications

- **Scaffold type:** hub-side utility script (`scripts/kilo-benchmarks/**`). Same as parent plan-2. NOT a deployed service.
- **`shape:` flags:** N/A — no `specs/services/*.yaml` touched.
- **New deps:** none (evalplus already pinned in `pyproject.toml`; shim uses only already-vendored `libs.subagents.*`).
- **New env vars:** none — `OPENROUTER_API_KEY` (already used by plan-2).
- **DB schema:** no ALTER TABLE — writes to existing `humaneval_score` + `coding_score` + `last_verified` columns via existing `write_scores`.
- **Sandbox provisioning:** unchanged — evalplus's offline eval step still uses its multiprocessing + rlimit sandbox (verified in parent spec Pass 1); bwrap outer layer is not applied (evalplus's local eval doesn't need it).

## Constraints

- **Backward-compat with plan-2 Phase A/B/C/D output.** No changes to `write_scores`, `is_fresh`, `main`'s argparse contract, `TOTAL_SPEND_USD` regex emission, `DEFAULT_MODELS`, `DEFAULT_DATASETS`, `ORCHESTRATOR_MODEL`, tier ladder, FAMILIES, snapshot fixture, or the 43 pytest cases from plan-2 (except the 3 that mocked the old dispatch — those need mock updates).
- **Fail-visible per problem.** A completion failure for one HumanEval problem MUST NOT silently zero-score the whole model. Shim writes `[error]` to stderr + empty solution; evalplus's local eval turns that into a legitimate pass@1 = 0 for that task. The model's aggregate pass@1 reflects the partial failure.
- **Real cost tracking.** `TOTAL_SPEND_USD` accumulates `sum(generate_samples returned cost)` across all units. No more `0.00` placeholder.
- **Deterministic output.** Shim's `generate_samples` iterates `problems.items()` and preserves order → `.jsonl` is byte-reproducible for the same model+problems input.
- **`--force` still needed for plan-2 Phase E retry.** The 4 Seed models are `is_fresh=True` from other benches — `--force` bypasses. Unchanged from plan-2.

## Open/blocking unknowns

### Resolved (during this drafting)

- **`_dotenv.load_env(repo)` vs shim's `env_path=".env"` default.** SELF-SERVICE: caller passes `env_path="/opt/fabrik"` (project root). Verified above.
- **Whether to use evalplus's `--samples` mode or reimplement pass@1 computation.** RESOLVED — evalplus's local eval mode is well-tested + supports both HumanEval+ (extra tests) and MBPP+ (v0.2.0 sanitized subset). Reimplementing would duplicate evalplus's sandbox + reference-solution execution.
- **Per-problem `max_cost_usd`.** RESOLVED — shim defaults to $0.50/problem; on 164 HumanEval + 378 MBPP+ problems the aggregate hard cap is well above the ~$2.66 expected total.
- **evalplus problem-dict prompt key stability.** RESOLVED — live-verified this session that both `get_human_eval_plus()` (164 problems) and `get_mbpp_plus()` (378 problems, post-cleanup) return `Dict[str, Dict]` where each inner dict has a `"prompt"` key. Integration snippet `problems[task_id]["prompt"]` is CORRECT. Was still-open in first draft.
- **Cost aggregation precision under retries.** RESOLVED — fabrik-lib AI (transport module owner) confirmed with a 2-finder pool doc↔code review (both DOC ACCURATE, scope caveats REFUTED with cited path:line): `Result.cost_usd` is **single-attempt** — it reflects only the successful attempt's OR-billed cost, never accumulates across retries. Verified in code: `_client.py:530` `_resolve_cost(acc, ...)` runs only after `_finalize(acc)` at `:529`, which is only reached if the stream loop completes without raising. Every retryable raise path (HardTimeoutError:493, ContentStallError:516, StuckError:522, TransientError:526, EmptyContentError) propagates before `_resolve_cost` is invoked → the failed attempt's `_Acc()` is discarded, cost never resolved. `loop.py:441-442` `total_cost += result.cost_usd` runs only after a successful call. `AgentResult.cost_usd = LoopOutcome.cost = sum(per-turn successful costs)` (agent.py:337,365; loop.py:360). Direction: never over-counts; slightly under-reports the "partial tokens burned before retry failed" case — the safe direction for a spend guard. **No caller-side reconciliation needed.** Also documented in `subagents/README.md` + `ai-consult/UPSTREAM_FEEDBACK.md` (upstream channel to the canonical run.py Result.cost_usd docstring on next sync — no vendored transport fork). Was still-open in first draft.

### Still-open (each has a self-service resolution step — none block execution)

1. **shim's ThreadPoolExecutor concurrency vs `max_concurrency=8`.** The shim uses its OWN `ThreadPoolExecutor(max_workers=max_concurrency=8)` per unit. `microbench_coding.main` ALSO uses its own `ThreadPoolExecutor(max_workers=8)` over units. Combined: 8 units × 8 shim-inner = up to 64 concurrent OR calls. **Self-service resolution at plan-3 Phase C:** cap the outer OR the inner (probably outer at `max_workers=1` when running the full 4-model bench so each unit's inner-8 doesn't blow up the OR concurrency budget). Verify by observing OR's `/generations` dashboard after a small dry-run. Not blocking — worst case is rate-limit responses that the transport already retries.

Zero cross-AI dependencies (shim already drafted by the fabrik-lib module owner). Zero unanswered execution-blocking questions.

## Handoff

- **Next step (this command, automatic):** `/fabrik-spec-review docs/superpowers/specs/2026-07-10-coding-microbench-completions-shim-design.md`.
- **After CONVERGED + user approval:**
  - Not a persistence-schema change (columns exist) → skip `/fabrik-data-contract`.
  - Not a GUI → skip `/fabrik-ui-design`.
  - `/fabrik-plan-after-chat docs/superpowers/specs/2026-07-10-coding-microbench-completions-shim-design.md`.
  - Then user relays "plan-3 is drafted" to the fabrik-lib module owner, who drops the shim into `scripts/kilo-benchmarks/openrouter_complete.py`.
  - Then `/fabrik-execute-plan` on plan-3.
  - Plan-3 EXECUTED → return to plan-2 Phase F (docs sync + `/fabrik-docs-review` + archive both plans).

**Expected wall clock (execution):** ~30-45 min for the code changes + tests + ~30 min live bench + ~15 min docs convergence + archival. Total: ~1.5h autonomous.

**Expected spend:** ~$2.66 for the live bench (unchanged from plan-2) + ~$0.30 for `/fabrik-review` pool passes ≈ **$3.00 total**.

**💡 No fabrik-lib candidate flagged.** The shim IS the fabrik-lib candidate topic — but the module owner explicitly framed it as "usage example of my module" rather than a new module. Their explicit judgment overrides the automatic candidate check.
