# Plan: Coding microbench completions shim + plan-2 unblock

**Status:** IN-PROGRESS (execution started 2026-07-10)
**Converged:** 2026-07-10 via `/fabrik-plan-review` — 2 passes to md5 fixed-point `0978a8e7a702f5da1761cad42a58caac`. Pass 1 dispatched 3 parallel independent grounders (G1 path:line + external deps + plan-2 commit hashes / G2 structural pillars + File Scope disjointness / G3 gates + Behavior Contracts + residuals) → 8 unique defects (0 from G1 — all 27 citations verified clean; 5 from G2 including 1 executor-blocking: Phase A missing lock-file-creation step 0; 3 from G3 including a systemic-break-passes-C1 lower-bound weakness). All 8 fixed. Pass 2 all-axes consistency sweep verified: log-path glob updated everywhere; Phase A step-0 doesn't collide with existing step-1 references; C1 floor references consistent across Behavior Contract + validation gate + recovery note; File Scope plan-2 paragraph landed cleanly; `run_agents` still only referenced in the review-dispatch template (never for bench dispatch). Zero edits + md5 identity → CONVERGED.
**Date:** 2026-07-10
**Author:** primary (this session)
**Spec:** `docs/superpowers/specs/2026-07-10-coding-microbench-completions-shim-design.md` (CONVERGED, md5 `40cb29797c1bca5d609cc1fcaccca790`)
**Unblocks:** `docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md` (Status BLOCKED — evalplus↔OR JSONDecodeError). Plan-3 lands the shim + refactor, runs the live bench, then closes plan-2 Phase F (docs + convergence + archive).

## What we already agreed

- **Design source of truth:** the `openrouter_complete.py` shim drafted by the fabrik-lib module owner (~90 LOC), reusing `libs.subagents._transport.run` + `_client.OpenRouterClient` + `_dotenv.load_env` — all already vendored via plan-2 Phase A.
- **User decision (relayed via ozgur):** module owner will drop the shim into `scripts/kilo-benchmarks/` when "plan-3 is drafted" — plan-3 must land + converge before shim arrives; plan-3 executor imports it from wherever it lands.
- **User decision (relayed):** fabrik-lib AI confirmed `Result.cost_usd` is single-attempt (never accumulates over retries) via 2-finder pool doc↔code review with cited `path:line` — original still-open residual #2 dissolved.
- **Approach:** two-step decomposition — completion via shim's `generate_samples(model, problems, out_path)` → offline eval via `evalplus.evaluate(dataset, samples=<path>)`. Zero changes to plan-2's Phase A/B/C/D (write_scores, tier ladder, FAMILIES, snapshot fixture, 43 pytest cases).
- **User goal:** unblock plan-2 Phase E (populate humaneval_score + coding_score for 4 ByteDance-Seed models), close plan-2 Phase F, archive both plans.
- **Explicitly rejected (from spec):** patch evalplus upstream, skip live-bench indefinitely, use LiveCodeBench (separate follow-up).
- **Explicitly out of scope:** UI-TARS GUI-agent bench (separate follow-up), LiveCodeBench contamination-resistant coverage (separate follow-up).

## Global Constraints

- **Python 3.12** (`pyproject.toml:6` — `requires-python = ">=3.12"`)
- **evalplus 0.3.1** already installed via plan-2 Phase A (`pyproject.toml:14 evalplus>=0.3.0`)
- **`libs.subagents` vendored at `scripts/kilo-benchmarks/libs/subagents/`** via plan-2 Phase A step 2b (byte-identical to `/opt/fabrik-lib/subagents/subagents/`)
- **OR API key:** `OPENROUTER_API_KEY` from `/opt/fabrik/.env` (already present). Bench sets `OPENAI_API_KEY=$OPENROUTER_API_KEY` for evalplus's local eval step (offline; no OR call).
- **Bwrap 0.9.0** installed at `/usr/bin/bwrap` — used by evalplus's OWN sandbox (multiprocessing + rlimit + read-only-root); bwrap wrap_command is available for defense-in-depth but not applied here (offline eval doesn't need network isolation).
- **DB path:** `scripts/kilo-benchmarks/kilo_agents.db` (unchanged from plan-2).
- **Shim's public API (drafted by module owner):**
  - `complete(model: str, prompt: str, *, client: OpenRouterClient, max_cost_usd: float = 0.50) → str`
  - `generate_samples(model: str, problems: dict[str, str], out_path: str | Path, *, max_concurrency: int = 8, solution_key: str = "solution", env_path: str | None = ".env") → tuple[Path, float]` — returns `(output_path, total_cost_usd)`
- **Result.cost_usd contract (verified single-attempt):** `sum(Result.cost_usd)` across successful completions is the exact spend metric — no double-counting on retries. Under-reports only on "partial tokens burned before retry failed" — safe direction for a spend guard.
- **Naming:** kebab-case files; snake_case Python modules; provenance trailers on every commit.
- **Review dispatch template:** every phase's closing `/fabrik-review` follows plan-2 Global Constraint's pool-default template (`run_agents(specs, tools_enabled=False, allow_ungrounded=True)`, `pick_models("review")`, each finder owes `record_agent_run(spec, result) + results_table`; reserve native `fabrik-reviewer` for high-risk auth/schema/migrations diffs — plan-3 has none, so all reviews go pool).
- **`# AFTER-EDIT:` header on every new `scripts/**/*.py`** (CLAUDE.md § Script coupling; `check_script_headers.py` WARN gate).
- **No `git push` unless the user says so this turn** — commits per phase, push deferred (per CLAUDE.md HARD STOPS).

## File Scope (owned paths)

**Created:**
- `scripts/kilo-benchmarks/openrouter_complete.py` — the shim, ~90 LOC. **Content authored by fabrik-lib module owner** (delivered as text in this session's handoff conversation); **plan-3 executor writes the file to `/opt/fabrik/scripts/kilo-benchmarks/`** using that authored content verbatim. **Cross-repo boundary correction (post-CONVERGED, mid-execution):** the original plan-3 Phase A step 1 was a `test -f` probe assuming the module owner would drop the file into `/opt/fabrik` themselves; this is a HARD STOP per CLAUDE.md (never-modify `/opt/fabrik` from a `/opt/fabrik-lib` agent; cross-repo write invites shared-tree collisions). The correct pattern: the owning repo's executor writes its own files. Plan-3 authors it in Phase A step 1 from the delivered content.
- `scripts/kilo-benchmarks/tests/test_openrouter_complete.py` — shim behavior tests (mock `_transport.run`).
- `scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py` — the 2-step refactor's integration test (2 files split because the shim tests are shim-local and don't need microbench_coding fixtures).

**Modified:**
- `scripts/kilo-benchmarks/microbench_coding.py` — `_run_one` refactored (2-step: `generate_samples` → `evalplus.evaluate --samples`); `main()` accumulates real cost from shim's returned tuple; outer `ThreadPoolExecutor` caps `max_workers=1` (resolves still-open residual #1 — outer serial + inner concurrent per unit).
- `scripts/kilo-benchmarks/tests/test_microbench_coding.py` — 3 tests updated: `test_main_writes_correct_model_id_end_to_end`, `test_main_emits_total_spend_regex_on_happy_path`, `test_main_emits_total_spend_on_unhandled_exception` — reshape mocks to match 2-step flow.
- `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` — regenerated post-live-bench (mechanical output).
- `CHANGELOG.md` — append atop `[Unreleased]` (2 entries: plan-3 EXECUTED + plan-2 unblocked/EXECUTED).
- `INDEX.md` — 3 new script rows (openrouter_complete.py + 2 test files).
- `docs/FEATURES.md` — "Coding microbench (Seed models)" entry under Internal tooling.
- `docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md` — Phase E marker: BLOCKED → EXECUTED (via plan-3); Phase F EXECUTED; Status: BLOCKED → EXECUTED.
- `docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md` — Status flips + phase EXECUTED markers.
- `.fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json` — blocked → released.
- `.fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json` — active → released.

**Sibling-plan disjointness (plan-1):** `2026-07-10-plan-1-mobile-app-factory.md` (ACTIVE) owns `templates/mobile-app/**` + `scaffold.py`. This plan owns `scripts/kilo-benchmarks/**` + top-level doc-sync (`CHANGELOG.md`, `INDEX.md`, `docs/FEATURES.md`) — code scope disjoint. Shared top-level doc-sync files: append-atop-`[Unreleased]`, explicit-path `git add`, `git diff --cached --name-only` before commit per CLAUDE.md HARD STOPS.

**Sibling-plan disjointness (plan-2, BLOCKED):** `2026-07-10-plan-2-coding-microbench-runner.md` holds a plan-lock at `.fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json` with `status: "blocked"` (verified this session). **A `blocked` lock signals plan-2 has YIELDED ownership per shared-master convention** — plan-3 is authorized to touch the following plan-2-owned paths as part of the unblock/finish path:
- `scripts/kilo-benchmarks/microbench_coding.py` — Phase B refactors `_run_one` + `main` outer loop
- `scripts/kilo-benchmarks/tests/test_microbench_coding.py` — Phase B reshapes 3 mocks for the 2-step flow
- `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` — Phase C regenerates
- `docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md` — Phase D flips `Status: BLOCKED → EXECUTED` + archives via `git mv`
- `.fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json` — Phase D flips `status: blocked → released` + updates `plan` field to archived path

Phase D closes both plans in the same commit sequence so their final states land together; no ownership-race window.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| **`.windsurf/rules/core/10-python.md`** (ACTIVE) | Python 3.12 typing, `os.getenv` for env, no hardcoded secrets | `pyproject.toml:6`; shim + integration both use `os.getenv("OPENROUTER_API_KEY")` never inline |
| **`.windsurf/rules/core/40-documentation.md`** (ACTIVE) | Doc Sync Matrix triggers: Code/deps → CHANGELOG; File added → INDEX; Feature → FEATURES | applied per phase; final `/fabrik-docs-review` in closing Phase E |
| **`.windsurf/rules/core/45-testing-strategy.md`** (ACTIVE) | Behavior Contract per phase; risk-ordered TDD | tests under `scripts/kilo-benchmarks/tests/test_*.py` |
| **`.windsurf/rules/core/58-resilience.md`** (ACTIVE) | Timeout/retry policies — `Liveness(hard_timeout_s=180, first_token_timeout_s=60)` in shim; per-problem `max_cost_usd=0.50` cap | shim design (spec §Chosen approach) + `_transport.py:41` Liveness class |
| **`.windsurf/rules/core/62-using-subagents.md`** (ACTIVE) | Pool-default for phase reviews; each finder owes `record_agent_run` | closing `/fabrik-review` at each phase boundary |
| **`.windsurf/rules/core/cost-budget.md`** (ACTIVE) | LLM cost caps required — bench uses shim's per-problem `max_cost_usd=0.50` + `AgentSpec.max_cost_usd=5.0` cap kept from plan-2 | shim + plan-2 build_units |
| **`libs/subagents/_transport.py:231`** | `run(model, messages, *, body, liveness, client, max_cost_usd, on_token, on_state) → Result` | vendored; verified this session |
| **`libs/subagents/_transport.py:41`** `Liveness` dataclass | fields `idle_timeout_s`, `hard_timeout_s`, `restart_max`, `connect_timeout_s`, `first_token_timeout_s` | vendored; verified |
| **`libs/subagents/_transport.py:55`** `Result` dataclass | fields `text: str`, `cost_usd: Optional[float]`, `finish_reason: Optional[str]` | vendored; verified |
| **`libs/subagents/_client.py:282-287`** `OpenRouterClient` | `(api_key, *, referer=None, title=None, base_url=..., transport=None, progress=True)` | vendored; verified |
| **`libs/subagents/_dotenv.py:141`** `load_env` | `load_env(repo: str, *, keys)` — takes DIRECTORY not file | vendored; caller passes `env_path="/opt/fabrik"` or relies on env already set |
| **`libs/subagents/_client.py:530` `_resolve_cost` retry contract** | Runs only after `_finalize(acc)` at :529 — single-attempt cost, never accumulates. `loop.py:441-442` accumulates only successful `Result.cost_usd`; `AgentResult.cost_usd = LoopOutcome.cost` (agent.py:337,365) | verified by fabrik-lib AI's 2-finder pool review + Pass-3 self-verification this session |
| **`scripts/kilo-benchmarks/microbench_coding.py:91,164,199,217,310,433`** | Function anchors: `build_units:91`, `parse_eval_results:164`, `merge_dataset_results:199`, `write_scores:217`, `main:310`, `_run_one` (nested):433 | verified this session |
| **evalplus 0.3.1 offline eval** | `evaluate(dataset, samples: Optional[str] = None, ...)` at `evalplus/evaluate.py:127-129` — with `samples=<jsonl>`, skips generation and runs sandboxed pass@1 evaluation only | verified this session |
| **evalplus problem-dict accessors** | `get_human_eval_plus() → Dict[str, Dict]` at `evalplus/data/humaneval.py:42` (164 problems); `get_mbpp_plus()` at `evalplus/data/mbpp.py:181` (378 problems). Each inner dict has a `"prompt"` key. | verified live this session |
| **`AGENTS.md`** infra (implicit) | Hub-side utility script; no VPS deploy, no `postgres-main`, no compose. Same as plan-2. | no shape change |
| **plan-2 preserved** | All Phase A/B/C/D output stays intact: write_scores column-scope, is_fresh UTC, argparse contract, tier ladder, FAMILIES, snapshot fixture, 43 pytest cases (3 mock-refactored in Phase B) | plan-2 commits: 135231a7, 9c33bb01, 64f4564d, eb43b4b9 |

## Phase A — Preflight: shim authored + integration surface probes — ✅ EXECUTED 2026-07-10

**Purpose:** Confirm the shim has landed at `scripts/kilo-benchmarks/openrouter_complete.py`, its imports resolve, and the integration surfaces (evalplus problem accessors, evalplus offline eval) work.

### Interfaces

**Consumes:** plan-2 Phase A output — `libs/subagents/*.py` vendored; evalplus installed.
**Produces:** confirmed environment; no code artifacts of this plan yet.

### Behavior Contract (this phase)

- **A1:** shim module importable from `scripts/kilo-benchmarks/openrouter_complete.py`; exports `complete`, `generate_samples`. (Given: shim dropped; When: import; Then: no ImportError.)
- **A2:** shim's internal transport reachable — `libs.subagents._transport.run` resolves (spec §Context Ledger cite `_transport.py:231`).
- **A3:** evalplus's `evaluate(dataset, samples=<jsonl>)` accepts the `samples` keyword arg (verified at `evalplus/evaluate.py:127-129`); a probe with a minimal shape-matching JSONL runs.
- **A4:** `get_human_eval_plus()` returns 164 problems each with a `"prompt"` key; `get_mbpp_plus()` returns 378 with same shape.

### Steps

0. **Create plan-3 lock file** (executor's own scope-lock — plan-2 is `blocked`, plan-1 is `active` and disjoint):
   ```bash
   cd /opt/fabrik && python3 <<'PYEOF'
   import json
   from pathlib import Path
   lock_path = Path(".fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json")
   assert not lock_path.exists(), f"lock already exists at {lock_path}"
   lock_path.write_text(json.dumps({
       "plan": "docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md",
       "owned_paths": [
           "scripts/kilo-benchmarks/openrouter_complete.py",
           "scripts/kilo-benchmarks/microbench_coding.py",
           "scripts/kilo-benchmarks/tests/test_openrouter_complete.py",
           "scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py",
           "scripts/kilo-benchmarks/tests/test_microbench_coding.py",
           "docs/reference/kilo/CODING_SUBAGENT_SELECTION.md",
           "CHANGELOG.md",
           "INDEX.md",
           "docs/FEATURES.md",
           "docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md",
           "docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md",
           ".fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json",
           ".fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json"
       ],
       "branch": "master",
       "started_at": "2026-07-10",
       "status": "active"
   }, indent=2))
   print(f"lock created at {lock_path}")
   PYEOF
   ```
   Expected: `lock created at .fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json`.

1. **Write the shim `scripts/kilo-benchmarks/openrouter_complete.py`** from the fabrik-lib module owner's authored content (delivered as text in the plan-3-drafted handoff — see below), then verify presence. **Cross-repo boundary rationale:** `/opt/fabrik-lib` agents are read-only wrt `/opt/fabrik` (CLAUDE.md HARD STOP); writes MUST originate from the owning repo's executor to keep each repo's gate visibility intact. The shim's imports use `from libs.subagents._client import ...` — these resolve because plan-2 Phase A step 2b vendored `libs/subagents/` (both `libs/__init__.py` and `libs/subagents/__init__.py` present at `scripts/kilo-benchmarks/libs/`).

   **Shim content (author verbatim; solution_key default `"solution"` matches evalplus 0.3.1's `utils.py:103` sample-key check):**
   ```python
   """openrouter_complete — HumanEval+/MBPP+ completion generator on the vendored subagents transport.

   Drop-in replacement for evalplus's `openai.OpenAI(base_url=OR)` completion step, which mis-parses
   OpenRouter's streaming SSE (the `json.decoder.JSONDecodeError`). This calls `libs.subagents._transport.run`
   instead — the SAME primitive every pool agent uses to talk to OpenRouter, so it is proven OR-compatible
   (streaming, provider reroute on content-stall, retry, cost accounting). The eval step (sandboxed
   execution + pass@1) stays evalplus's and runs offline against the produced samples `.jsonl`.
   """
   # ... (full 90 LOC per fabrik-lib module owner's authored delivery)
   ```

   After writing, verify presence:
   ```bash
   cd /opt/fabrik && test -f scripts/kilo-benchmarks/openrouter_complete.py && echo "shim written" || { echo "SHIM WRITE FAILED"; exit 1; }
   ```
   Expected: `shim written`.

2. **Shim import probe.**
   ```bash
   cd /opt/fabrik && .venv/bin/python -c "
   import sys, pathlib
   sys.path.insert(0, 'scripts/kilo-benchmarks/libs')
   sys.path.insert(0, 'scripts/kilo-benchmarks')
   from openrouter_complete import complete, generate_samples
   print('complete:', complete.__doc__.split(chr(10))[0] if complete.__doc__ else '(no doc)')
   print('generate_samples:', generate_samples.__doc__.split(chr(10))[0] if generate_samples.__doc__ else '(no doc)')
   "
   ```
   Expected: two doc-line prints, no ImportError.

3. **Transport reachability probe (A2).**
   ```bash
   cd /opt/fabrik && .venv/bin/python -c "
   import sys, pathlib
   sys.path.insert(0, 'scripts/kilo-benchmarks/libs')
   from subagents._transport import run, Liveness, Result
   from subagents._client import OpenRouterClient
   print('run:', callable(run))
   print('Liveness:', Liveness.__dataclass_fields__.keys())
   print('Result:', Result.__dataclass_fields__.keys())
   "
   ```
   Expected: `run: True`, Liveness fields include `hard_timeout_s`/`first_token_timeout_s`, Result fields include `text`/`cost_usd`/`finish_reason`.

4. **evalplus problem accessors probe (A4).**
   ```bash
   cd /opt/fabrik && .venv/bin/python -c "
   from evalplus.data.humaneval import get_human_eval_plus
   from evalplus.data.mbpp import get_mbpp_plus
   h = get_human_eval_plus()
   m = get_mbpp_plus()
   assert len(h) == 164, f'HumanEval+ count {len(h)} != 164'
   assert len(m) == 378, f'MBPP+ count {len(m)} != 378'
   assert 'prompt' in next(iter(h.values())), 'HumanEval+ missing prompt'
   assert 'prompt' in next(iter(m.values())), 'MBPP+ missing prompt'
   print('OK: 164 HumanEval+ + 378 MBPP+, both have prompt field')
   "
   ```
   Expected: `OK: 164 HumanEval+ + 378 MBPP+, both have prompt field`.

5. **evalplus offline eval probe (A3).** evalplus's `--samples` mode requires solutions for ALL 164 HumanEval+ problems (`evalplus/evaluate.py:230 assert len(completion_id) == len(problems)`), not a subset. Supply an empty solution for every task_id — evalplus scores them all as 0%, which is the correct output for empty solutions and proves the `--samples` pipeline works offline (no OR call, no cost):
   ```bash
   cd /opt/fabrik && .venv/bin/python -c "
   import json, tempfile, pathlib, subprocess, sys
   from evalplus.data.humaneval import get_human_eval_plus
   d = pathlib.Path(tempfile.mkdtemp(prefix='evalplus_offline_probe_'))
   samples_path = d / 'samples.jsonl'
   with samples_path.open('w') as f:
       for task_id in get_human_eval_plus():
           f.write(json.dumps({'task_id': task_id, 'solution': 'pass\n'}) + '\n')
   r = subprocess.run(
       [sys.executable, '-m', 'evalplus.evaluate', '--dataset', 'humaneval', '--samples', str(samples_path)],
       cwd=str(d), capture_output=True, timeout=120,
   )
   print('rc:', r.returncode)
   if r.returncode != 0:
       print('stderr:', r.stderr[-1000:].decode(errors='replace'))
       raise SystemExit(1)
   results = list(d.glob('**/*eval_results.json'))
   assert len(results) > 0, f'evalplus rc=0 but no eval_results.json under {d}'
   print('eval_results.json produced:', results[0])
   "
   ```
   Expected: `rc: 0`, `eval_results.json produced: <path>`, stdout ends with `pass@1: 0.000` on both `humaneval` (base) and `humaneval+` (extra tests) since all solutions are empty stubs. Exit non-zero on any failure.

### Phase A closing sequence

1. Run A1-A4 probes → all green.
2. `python scripts/enforcement/check_doc_sync.py` → expect no WARNING (Phase A adds no new files yet).
3. **`/fabrik-review` on this phase's changed surface** — Phase A adds ZERO code (just runs probes); NO-POOL declaration in commit: `NO-POOL: Phase A is preflight probes only, no authored code to review`.
4. **Commit Phase A** (probes-only phase; plan file staged for status flip):
   ```bash
   git add docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md .fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   chore(kilo-benchmarks): Phase A — preflight probes (shim reachability + evalplus offline)

   NO-POOL: Phase A is preflight probes only, no authored code to review

   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: verified shim landed + transport importable + evalplus problem accessors + offline eval probe green; plan-3 lock ACTIVE + status IN-PROGRESS

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase B — 2-step refactor: `_run_one` uses shim + updated tests — ✅ EXECUTED 2026-07-10

**Purpose:** Refactor `microbench_coding._run_one` from the broken 1-step `subprocess.run(evalplus.evaluate --backend openai ...)` to the 2-step `generate_samples → evalplus.evaluate --samples`. Update 3 mocks + add 2 new behavior tests. Cap outer concurrency (resolves plan-3 still-open residual #1).

### Interfaces

**Consumes:** Phase A's confirmed shim + evalplus availability.
**Produces:**
- `microbench_coding._run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str, float]` — 4-tuple (added `cost` float); previously `tuple[BenchUnit, bool, str]`.
- `microbench_coding.main` — outer `ThreadPoolExecutor(max_workers=1)` (serial across units to keep OR-concurrency budget bounded to shim's inner 8); accumulates `cost` from each `_run_one` return; emits `TOTAL_SPEND_USD: {total_spend:.2f}` as before.
- `test_microbench_coding.py` — 3 tests updated to match the 2-step flow: `test_main_writes_correct_model_id_end_to_end`, `test_main_emits_total_spend_regex_on_happy_path`, `test_main_emits_total_spend_on_unhandled_exception`.
- `test_openrouter_complete.py` — 6 new shim-behavior tests.
- `test_microbench_coding_two_step.py` — 4 new integration tests (2-step flow, cost aggregation).

### Behavior Contract (this phase — risk-ordered, TDD on B1)

- **B1 (highest risk — TDD)**: `_run_one` populates the correct `unit_dir/results/eval_results.json` after the 2-step sequence, and the returned `cost` matches the shim's returned `total_cost_usd`. (Given: mocked shim `generate_samples` returns `(<path>, 0.05)` after writing a real-shape JSONL; mocked `subprocess.run(evalplus.evaluate --samples)` writes a real-shape `eval_results.json`; When: `_run_one(unit)`; Then: returns `(unit, True, "", 0.05)` and `results/eval_results.json` exists.)
- **B2**: `main` accumulates real spend across units — `TOTAL_SPEND_USD` = `sum(cost per unit)`. (Given: 2 mocked units returning 0.11 each; When: main; Then: last stdout line matches `^TOTAL_SPEND_USD: 0\.22$`.)
- **B3**: outer `ThreadPoolExecutor` is capped at `max_workers=1` — units process serially (log lines appear in submission order). (Given: 4 units, mocked shim adds a 0.05s sleep per call; When: main; Then: units complete in submission order — `[1/8]`, `[2/8]`, …, `[8/8]`.)
- **B4**: shim's `generate_samples` returns `(Path, float)` with the float being sum of per-problem `Result.cost_usd` (single-attempt guarantee). (Given: mocked `_transport.run` returning 3 Results with `cost_usd=[0.01, 0.02, 0.03]`; When: `generate_samples`; Then: returned float = 0.06.)
- **B5**: shim's per-problem `[error]` on exception writes empty solution + stderr log, does NOT abort batch. (Given: mocked `_transport.run` raises on problem #2; When: `generate_samples` with 3 problems; Then: JSONL has 3 lines (2 real + 1 empty), stderr contains `[error] Task/2`.)
- **B6**: shim's `finish_reason="length"` truncation logs `[warn]` but writes the truncated text. (Given: mocked Result with `finish_reason="length"`; When: generate_samples; Then: stderr contains `[warn]`, JSONL row has the text.)
- **B7 (integration)**: end-to-end `main` writes correct `humaneval_score` for a mocked-happy-path Seed model. (Given: mocked shim + mocked evalplus subprocess dropping a real-shape `eval_results.json` with 2/3 base-pass; When: main; Then: DB row has `humaneval_score ≈ 66.67`.)
- **B8**: `--dry-run` output unchanged from plan-2 (backward compat). (Given: `--dry-run --models <M> --datasets humaneval`; When: main; Then: `DRY RUN` in stdout, no shim import triggered by dry path, `TOTAL_SPEND_USD: 0.00`.)

### Steps

1. **TDD B1 first — write test in `tests/test_microbench_coding_two_step.py` (mocks the whole 2-step flow); confirm it FAILS RED** because `_run_one` is still the old 1-step subprocess call.
   ```bash
   cd /opt/fabrik && .venv/bin/pytest scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py::test_run_one_writes_eval_results_and_returns_cost -xvs 2>&1 | tail -20
   ```
   Expected: FAIL — old `_run_one` doesn't return a 4-tuple, doesn't call shim, doesn't accumulate cost.

2. **Author test file `scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py`** (~120 LOC) with `# AFTER-EDIT: none` header. Includes B1, B2, B3, B7 tests. Mock strategy: `monkeypatch.setattr(microbench_coding, 'generate_samples', _fake_generate_samples)` + `monkeypatch.setattr(microbench_coding.subprocess, 'run', _fake_evalplus_evaluate)`.

3. **Author test file `scripts/kilo-benchmarks/tests/test_openrouter_complete.py`** (~140 LOC) with `# AFTER-EDIT: none` header. Includes B4, B5, B6 shim-behavior tests. Mock strategy: `monkeypatch.setattr(openrouter_complete, '_run', _fake_transport_run)` where `_fake_transport_run` returns a fake `Result(text=..., cost_usd=..., finish_reason=...)`.

4. **Refactor `microbench_coding._run_one`** — replace body:
   ```python
   def _run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str, float]:
       """Two-step: shim.generate_samples → evalplus.evaluate --samples (offline)."""
       # step 1 — completion via the vendored subagents transport (unblocks evalplus↔OR SSE bug)
       problems_dict = (
           get_human_eval_plus() if u.dataset == "humaneval" else get_mbpp_plus()
       )
       prompts = {task_id: p["prompt"] for task_id, p in problems_dict.items()}
       samples_path = u.unit_dir / "results" / f"{u.target.replace('/', '--')}_samples.jsonl"
       try:
           samples_path, cost = openrouter_complete.generate_samples(
               model=u.target,
               problems=prompts,
               out_path=samples_path,
               max_concurrency=8,
               env_path="/opt/fabrik",
           )
       except Exception as e:  # noqa: BLE001
           return u, False, f"generate_samples failed: {e!r}", 0.0
       # step 2 — offline eval (no OR call; evalplus's own sandbox)
       try:
           result = subprocess.run(
               [sys.executable, "-m", "evalplus.evaluate",
                "--dataset", u.dataset, "--samples", str(samples_path)],
               cwd=str(u.unit_dir),
               env=os.environ.copy(),
               capture_output=True,
               timeout=600,
               check=False,
           )
           if result.returncode != 0:
               return u, False, (result.stderr or b"").decode()[-2000:], cost
           return u, True, "", cost
       except subprocess.TimeoutExpired as e:
           return u, False, f"evalplus.evaluate --samples timeout after 600s: {e}", cost
       except Exception as e:  # noqa: BLE001
           return u, False, f"evalplus.evaluate --samples failed: {e!r}", cost
   ```
   Add `from evalplus.data.humaneval import get_human_eval_plus` + `from evalplus.data.mbpp import get_mbpp_plus` + `import openrouter_complete` at module top.

5. **Refactor `main()` cost aggregation.** Change the `ThreadPoolExecutor(max_workers=8)` for units to `max_workers=1` (B3 — serial outer). Change tuple unpack from 3-tuple to 4-tuple. Accumulate `cost` per unit; emit `TOTAL_SPEND_USD: {total_spend:.2f}` as before.
   Diff at `microbench_coding.py:main` — the outer loop over units becomes:
   ```python
   total_spend = 0.0
   with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
       futs = [pool.submit(_run_one, u) for u in units]
       for i, fut in enumerate(concurrent.futures.as_completed(futs)):
           u, ok, err, cost = fut.result()
           total_spend += cost
           status = "OK" if ok else "FAIL"
           print(f"[{i+1}/{len(units)}] {status} {u.target}/{u.dataset} cost=${cost:.4f}")
           if not ok:
               print(f"  err: {err[-500:]}", file=sys.stderr)
   ```

6. **Update 3 mocks in `tests/test_microbench_coding.py`:**
   - `test_main_writes_correct_model_id_end_to_end`: change mock target from `subprocess.run` (old 1-step) to BOTH `microbench_coding.openrouter_complete.generate_samples` (returns fake `(path, cost)`) AND `subprocess.run` (writes real-shape `eval_results.json` in `--samples` mode). Assert `humaneval_score` still ≈ 66.67.
   - `test_main_emits_total_spend_regex_on_happy_path`: same mock reshape; assert `TOTAL_SPEND_USD` regex matches non-zero (mocked cost = 0.05).
   - `test_main_emits_total_spend_on_unhandled_exception`: use env-var strip as before (F2 pattern from plan-2 Phase C), assert TOTAL_SPEND_USD emitted.

7. **Test-run all Phase B behaviors — concrete gate: zero failures + specific reshaped-test IDs must PASS:**
   ```bash
   cd /opt/fabrik && .venv/bin/pytest scripts/kilo-benchmarks/tests/test_openrouter_complete.py scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py scripts/kilo-benchmarks/tests/test_microbench_coding.py --tb=short 2>&1 | tee /tmp/phase_b_pytest.log
   grep -q ' failed' /tmp/phase_b_pytest.log && { echo "PHASE B FAIL: failures present"; exit 1; } || true
   grep -q ' error' /tmp/phase_b_pytest.log && { echo "PHASE B FAIL: errors present"; exit 1; } || true
   # The 3 reshaped test IDs (must appear as PASSED, not skipped/error/fail):
   for tid in test_main_writes_correct_model_id_end_to_end test_main_emits_total_spend_regex_on_happy_path test_main_emits_total_spend_on_unhandled_exception; do
       grep -qE "${tid} .*PASSED" /tmp/phase_b_pytest.log || { echo "PHASE B FAIL: reshaped test $tid did not PASS"; exit 1; }
   done
   echo "PHASE B PASS: zero failures/errors + all 3 reshaped mocks PASSED"
   ```
   Expected: `PHASE B PASS: zero failures/errors + all 3 reshaped mocks PASSED`. Actual test count may vary with parametrize expansion; only the concrete pass conditions above matter.

8. **Ruff check** — the refactored file + 2 new test files:
   ```bash
   cd /opt/fabrik && .venv/bin/ruff check scripts/kilo-benchmarks/microbench_coding.py scripts/kilo-benchmarks/tests/test_openrouter_complete.py scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py
   ```
   Expected: `All checks passed!`.

### Phase B closing sequence

1. Run step 7 test-suite → all green.
2. `python scripts/enforcement/check_doc_sync.py` → no WARNING scoped to Phase B files.
3. **`/fabrik-review` on Phase B's changed surface** — pool-dispatch template per Global Constraints. Highest-risk lens: (a) mocked-shim tests must actually assert on the DB write path (not just on the mock being called); (b) does removing outer concurrency correctly bound the OR call budget; (c) is the tuple-unpack change consistent everywhere `_run_one` is used.
4. **Commit Phase B** (explicit paths + trailers):
   ```bash
   git add scripts/kilo-benchmarks/microbench_coding.py scripts/kilo-benchmarks/tests/test_openrouter_complete.py scripts/kilo-benchmarks/tests/test_microbench_coding_two_step.py scripts/kilo-benchmarks/tests/test_microbench_coding.py docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase B — 2-step refactor (shim → evalplus offline) + tests

   _run_one refactored to 2-step:
     step 1: openrouter_complete.generate_samples(target, prompts, out) → (jsonl_path, cost)
     step 2: subprocess.run(evalplus.evaluate --samples <jsonl_path>) — offline, no OR call

   main outer ThreadPoolExecutor capped at max_workers=1 (serial units × inner-8 shim = 8 concurrent OR calls max, resolves plan-3 still-open residual #1).

   cost aggregation now real: total_spend += cost per unit; TOTAL_SPEND_USD reflects sum of shim's returned per-unit cost (single-attempt Result.cost_usd, verified by fabrik-lib AI).

   Tests:
   - test_openrouter_complete.py (6 shim-behavior tests: B4/B5/B6)
   - test_microbench_coding_two_step.py (4 integration tests: B1/B2/B3/B7)
   - test_microbench_coding.py (3 mocks reshape for 2-step flow)

   Agent-Role: orchestrator
   Agent-Phase: B
   Agent-Context: 2-step _run_one + outer serial + cost accumulation + 13 test cases (10 new + 3 reshape)

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase C — Live bench run + DB verification + selection MD regen

**Purpose:** Actually populate `humaneval_score` + `coding_score` for the 4 ByteDance-Seed models. This is the ~$2.66 live spend + ~30 min wall clock plan-2 Phase E BLOCKED at. Regen `CODING_SUBAGENT_SELECTION.md`.

### Interfaces

**Consumes:** Phase B (working 2-step `main`).
**Produces:** 4 rows in `agents` with non-NULL `humaneval_score` (0-100 scale), non-NULL `coding_score`, non-NULL `last_verified = UTC today`.

### Behavior Contract (this phase)

- **C1 (systemic-break floor):** all 4 Seed models have `humaneval_score IS NOT NULL AND humaneval_score >= 5 AND humaneval_score < 100`. **Floor = 5:** ByteDance-Seed models are frontier code LLMs (OR pricing $0.30-$2.00/Mtok output); a HumanEval+ pass@1 below 5% means the pipeline is systemically broken (empty completions, malformed JSONL, evalplus-can't-parse solutions) — NOT a legitimate low score. A pipeline-broken run must fail C1 rather than silently archive worthless data. **Ceiling = <100:** an exactly-100% score triggers Phase C's closing memorization-lens review but doesn't fail C1 (it's an anomaly to investigate, not a pipeline break).
- **C2:** all 4 have `coding_score` populated and ≥ 5 AND < 100 (same reasoning). Should be ≈ mean of 4 pass@1 sub-scores × 100.
- **C3:** `last_verified` = UTC today for all 4 rows (spec §Constraints — UTC-anchored write).
- **C4:** `TOTAL_SPEND_USD` emission matches `^TOTAL_SPEND_USD: [0-9]+\.[0-9]+$` regex AND value > 0.50 (a plausible floor: the 4-model × 2-dataset bench at real OR pricing on ~1.1K problems should cost at least ~$0.50; zero cost = shim never actually hit OR).
- **C5:** `CODING_SUBAGENT_SELECTION.md` after re-running `rank_coding_subagents.py` contains all 4 Seed model rows with humaneval_score displayed.

**Recovery from C1/C2 fail** (self-service, not a stall): the closing `/fabrik-review` on Phase C's diff is expected to inspect the per-unit stderr in `/tmp/microbench_coding_phase_C.log`; if a systemic break is diagnosed (all 4 models scoring 0-5), the fix path is a code-review-driven bug fix in `_run_one` or the shim call, NOT a threshold relaxation. Only if the operator confirms after inspection that "the bench really did work, Seed just happens to score <5" (unlikely for these tier-3 models) does the plan accept C1 fail as a legitimate outcome and proceed via `--force` in a review-fix commit. This is a REAL BLOCKED path if the pipeline is broken — the executor halts with `BLOCKED: Phase C C1 floor tripped — searched: /tmp/microbench_coding_phase_C.log — missing: sane pass@1 for Seed frontier models` and the user rules.

### Steps

1. **Silence noisy watchdogs / alerts if applicable** — no downtime alerts fire on this hub for `microbench_or_models`-class runs; skip.

2. **Confirm the setup one more time:**
   ```bash
   cd /opt/fabrik && OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' .env | cut -d= -f2) .venv/bin/python scripts/kilo-benchmarks/microbench_coding.py --dry-run --models bytedance-seed/seed-1.6-flash --datasets humaneval
   ```
   Expected: `DRY RUN — would dispatch 1 units:` + `TOTAL_SPEND_USD: 0.00`, exit 0.

3. **Live run — background via Bash `run_in_background=true` (per CLAUDE.md long-command monitoring rule; harness notifies on completion, no `nohup … &` polling):**
   ```bash
   cd /opt/fabrik && \
   OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' .env | cut -d= -f2) \
   .venv/bin/python scripts/kilo-benchmarks/microbench_coding.py \
       --models bytedance-seed/seed-1.6-flash,bytedance-seed/seed-2.0-mini,bytedance-seed/seed-1.6,bytedance-seed/seed-2.0-lite \
       --datasets humaneval,mbpp \
       --cost-cap 5 \
       --force \
       > /tmp/microbench_coding_phase_C.log 2>&1
   ```
   **Executor MUST launch this via the Bash tool's `run_in_background: true` parameter** (not shell `&` / `nohup`). The harness tracks the process + emits a completion notification. Expected wall clock: ~30-60 min for 8 units serialized outer + shim's inner-8 concurrent per unit against 164+378 problems.

4. **Wait for completion notification** — the harness fires a `<task-notification>` when the background command exits. Do NOT poll; the notification IS the wait signal.

5. **Validation gate C1+C2+C3 — DB inspection with systemic-break floor:**
   ```bash
   cd /opt/fabrik && .venv/bin/python -c "
   import sqlite3
   from datetime import datetime, UTC
   conn = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
   rows = conn.execute(
       'SELECT id, humaneval_score, coding_score, last_verified FROM agents '
       \"WHERE id LIKE 'bytedance-seed/seed-%' AND id NOT LIKE '%dola%' AND id NOT LIKE '%seedream%'\"
   ).fetchall()
   assert len(rows) == 4, f'expected 4 Seed rows, got {len(rows)}: {rows}'
   today_utc = datetime.now(UTC).date().isoformat()
   for id_, he, cs, lv in rows:
       print(f'{id_}: humaneval={he}, coding={cs}, verified={lv}')
       assert he is not None, (id_, 'humaneval_score is NULL')
       assert 5 <= he < 100, (id_, 'humaneval_score', he, 'outside 5-100 floor/ceiling — SYSTEMIC BREAK, not a low-scoring model')
       assert cs is not None, (id_, 'coding_score is NULL')
       assert 5 <= cs < 100, (id_, 'coding_score', cs, 'outside 5-100')
       assert lv == today_utc, (id_, lv, today_utc)
   print('C1+C2+C3 PASS')
   "
   ```
   Expected: 4 rows, all with valid scores, `C1+C2+C3 PASS`. If ANY row has `humaneval_score < 5`, the pipeline is systemically broken → executor halts with `BLOCKED: Phase C C1 floor tripped — see /tmp/microbench_coding_phase_C.log`.

6. **Regen selection MD (C5):**
   ```bash
   cd /opt/fabrik && .venv/bin/python scripts/kilo-benchmarks/rank_coding_subagents.py
   grep -c 'bytedance-seed/seed-' docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
   ```
   Expected: 4 matches.

7. **Cost audit (C4):**
   ```bash
   grep -oE '^TOTAL_SPEND_USD: [0-9]+\.[0-9]+$' /tmp/microbench_coding_phase_C.log | tail -1
   ```
   Expected: a line like `TOTAL_SPEND_USD: 2.5X` (near the spec's ~$2.66 estimate).

### Phase C closing sequence

1. Run C1-C5 → all green.
2. `python scripts/enforcement/check_doc_sync.py` → CODING_SUBAGENT_SELECTION.md regenerated, no new WARN.
3. **`/fabrik-review` on Phase C's diff** — pool-dispatch template. Highest-risk lens: (a) any Seed model scoring >0.95 on plain HumanEval is a memorization red flag; (b) any subprocess timeout / error swallowed silently; (c) does the actual observed pass@1 distribution match the Phase D tier threshold (60/40) or should thresholds recalibrate.
4. **Commit Phase C** (explicit paths + trailers):
   ```bash
   git add docs/reference/kilo/CODING_SUBAGENT_SELECTION.md docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase C — live bench populates 4 Seed models

   Real spend: $<n.nn> (fits the ~$2.66 spec estimate).
   Real scores in CODING_SUBAGENT_SELECTION.md for the 4 Seed models.

   Agent-Role: orchestrator
   Agent-Phase: C
   Agent-Context: 4 Seed models × 2 datasets × ~30 min via 2-step shim + evalplus offline eval; DB row updates verified against UTC-today

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase D — Docs sync + return-to-plan-2 Phase F

**Purpose:** Doc Sync Matrix triggers for BOTH plan-2 (which was BLOCKED at Phase F never-started) AND plan-3. `/fabrik-docs-review` convergence. Both plans move to EXECUTED + archive.

### Interfaces

**Consumes:** Phase C's populated DB + regenerated selection MD.
**Produces:** Updated docs, plan-2 EXECUTED, plan-3 EXECUTED, both archived.

### Behavior Contract (this phase)

- **D1:** `CHANGELOG.md` under `## [Unreleased]` gains 2 new entries at the top:
  - `### Added — Coding microbench completions shim + live bench (2026-07-10)` — describes plan-3's shim + refactor + live bench results.
  - `### Fixed — plan-2 Phase E unblocked (evalplus↔OR JSONDecodeError bypassed via completions shim) (2026-07-10)` — cross-links plan-2.
- **D2:** `INDEX.md` lists 3 new files: `openrouter_complete.py`, `test_openrouter_complete.py`, `test_microbench_coding_two_step.py`.
- **D3:** `docs/FEATURES.md` gains a "Coding microbench (Seed models)" entry under "Internal tooling" (create heading if absent).
- **D4:** plan-2 file: Status BLOCKED → EXECUTED; Phase E marker updated with plan-3 unblock reference; Phase F marker: EXECUTED via this Phase D.
- **D5:** plan-3 file: Status IN-PROGRESS → EXECUTED; all Phase markers final.
- **D6:** `/fabrik-docs-review` on the plan's changed surface converges to md5-identity no-op.

### Steps

1. Write CHANGELOG entries (append atop `[Unreleased]`, do NOT reset section).
2. Add INDEX rows for 3 new script files.
3. Add FEATURES.md entry (grep for `^## Internal tooling` first — if absent, create heading at end of file).
4. **Update plan-2 file — flip Status + convert Blocker paragraphs to a Resolved note + preserve historical text:**
   - Change line `**Status:** BLOCKED — evalplus↔OpenRouter incompatibility (Phase E) (2026-07-10)` to `**Status:** EXECUTED (2026-07-10 — Phase E unblocked via plan-3 shim, commit <phase-C-hash>; Phase F closed via plan-3 Phase D)`.
   - Replace the top-of-file `**Blocker:**` + `**Options for user resolution:**` block (7-8 lines describing 4 options) with a single line: `**Resolved:** 2026-07-10 via plan-3 shim (commit <phase-C-hash>) — evalplus↔OR JSONDecodeError bypassed by `openrouter_complete.py` completions shim; Phase E populated humaneval_score for 4 Seed models via plan-3 Phase C; Phase F (docs + convergence + archive) closed via plan-3 Phase D.`
   - Under `## Phase E — Live bench run against 4 Seed models — ⛔ BLOCKED 2026-07-10 (evalplus↔OR incompatibility)`: flip marker to `— ✅ EXECUTED 2026-07-10 via plan-3 (commit <phase-C-hash>)` and append a `### Blocker (historical)` subsection preserving the original blocker text verbatim (for postmortem visibility — a future reader tracing the plan-lifecycle sees the actual issue that was hit + how it was resolved).
   - Under `## Phase F — Docs + convergence`: append `— ✅ EXECUTED 2026-07-10 via plan-3 Phase D (commit <phase-D-hash>)`.
5. Update plan-3 file: Status IN-PROGRESS → EXECUTED; all Phase A/B/C/D markers `— ✅ EXECUTED 2026-07-10 (<phase-hash>)`.
6. Run `python scripts/enforcement/check_doc_sync.py` → expect success.
7. Invoke `/fabrik-docs-review scripts/kilo-benchmarks/openrouter_complete.py scripts/kilo-benchmarks/microbench_coding.py docs/reference/kilo/CODING_SUBAGENT_SELECTION.md CHANGELOG.md INDEX.md docs/FEATURES.md` via the Skill tool. **No-op signal:** the review reaches md5-identity no-op (per `/fabrik-docs-review`'s own termination contract).

### Phase D closing sequence

1. `check_doc_sync.py` → success.
2. `/fabrik-docs-review` → md5-identical no-op pass.
3. **Whole-plan `/fabrik-review` over cumulative diff** (per CLAUDE.md § Finish for plan-execution): `git diff <plan-3-baseline>..HEAD` scoped to this plan's owned paths — pool-dispatch template — loop to no-op. This is the cross-phase net catching what per-phase reviews missed.
4. **Full final gate:**
   ```bash
   cd /opt/fabrik && python scripts/final_gate.py --json | python -c "import sys, json; d=json.load(sys.stdin); print(d['status']); sys.exit(0 if d['status']=='success' else 1)"
   ```
   Expected: `success`.
5. Run `python scripts/enforcement/check_convergence.py` → success.
6. **Requirements coverage** — walk the plan-3 "What we already agreed" bullets, point to the phase + commit that delivered each. Verify zero gaps.
7. **Release BOTH plan locks + archive BOTH plans:**
   ```bash
   cd /opt/fabrik
   # release + archive plan-3
   python3 -c "
   import json
   from pathlib import Path
   p = Path('.fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json')
   d = json.loads(p.read_text())
   d['status'] = 'released'
   d['completed_at'] = '2026-07-10'
   d['plan'] = 'docs/development/plans/archived/2026-07-10-plan-3-coding-microbench-completions-shim.md'
   p.write_text(json.dumps(d, indent=2))
   "
   git mv docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md docs/development/plans/archived/2026-07-10-plan-3-coding-microbench-completions-shim.md
   # release + archive plan-2
   python3 -c "
   import json
   from pathlib import Path
   p = Path('.fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json')
   d = json.loads(p.read_text())
   d['status'] = 'released'
   d['completed_at'] = '2026-07-10'
   d['plan'] = 'docs/development/plans/archived/2026-07-10-plan-2-coding-microbench-runner.md'
   p.write_text(json.dumps(d, indent=2))
   "
   git mv docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md docs/development/plans/archived/2026-07-10-plan-2-coding-microbench-runner.md
   ```
8. **Commit Phase D** (explicit paths + trailers, including the plan mvs):
   ```bash
   git add CHANGELOG.md INDEX.md docs/FEATURES.md \
       docs/development/plans/archived/2026-07-10-plan-3-coding-microbench-completions-shim.md \
       docs/development/plans/archived/2026-07-10-plan-2-coding-microbench-runner.md \
       .fabrik/plan-locks/2026-07-10-plan-3-coding-microbench-completions-shim.json \
       .fabrik/plan-locks/2026-07-10-plan-2-coding-microbench-runner.json
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   docs(kilo-benchmarks): Phase D — docs sync + plan-2 + plan-3 archived (EXECUTED)

   - CHANGELOG: 2 entries (plan-3 shim + live bench; plan-2 unblocked)
   - INDEX: 3 new script rows
   - FEATURES: Coding microbench (Seed models) under Internal tooling
   - plan-2 status: BLOCKED → EXECUTED (Phase E unblocked via plan-3 shim; Phase F: this commit)
   - plan-3 status: IN-PROGRESS → EXECUTED
   - Both plans archived under docs/development/plans/archived/
   - Both plan-locks released

   Agent-Role: orchestrator
   Agent-Phase: D
   Agent-Context: whole-plan /fabrik-review no-op; final_gate --json success; /fabrik-docs-review md5-identity no-op; requirements coverage 100%

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Evidence

Per-phase real `path:line` reads + fenced command-output blocks:

**Phase A:**
- `evalplus/evaluate.py:127-129` — verified `samples: Optional[str] = None` param exists
- `_transport.py:41` — `Liveness` dataclass fields verified
- `_transport.py:55` — `Result` dataclass fields verified

```
$ .venv/bin/python -c "from evalplus.data.humaneval import get_human_eval_plus; from evalplus.data.mbpp import get_mbpp_plus; print(len(get_human_eval_plus()), len(get_mbpp_plus()))"
164 378
```

**Phase B:**
- `microbench_coding.py:433` — nested `def _run_one(u: BenchUnit)` currently returns 3-tuple; refactor to 4-tuple
- `microbench_coding.py:310` — `def main(argv)` — outer ThreadPoolExecutor to cap
- `microbench_coding.py:91` — `def build_units` — unchanged (BenchUnit + owned_paths intact)
- `microbench_coding.py:164` — `def parse_eval_results` — unchanged (still reads evalplus's `eval_results.json` shape)
- `microbench_coding.py:217` — `def write_scores` — unchanged (0-100 scale, weighted_coding untouched)

```
$ grep -n "def _run_one\|def main\|def build_units" scripts/kilo-benchmarks/microbench_coding.py
91:def build_units(
310:def main(argv: list[str] | None = None) -> int:
433:                def _run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str]:
```

**Phase C:**
- 4 Seed model pricing (verified in plan-2 Phase A + parent spec)
- `Result.cost_usd` single-attempt contract verified in plan-3 spec (10 cited path:lines)

```
$ curl -s https://openrouter.ai/api/v1/models | python3 -c "import sys, json; ids = {m['id'] for m in json.load(sys.stdin).get('data', [])}; print('all 4 present:', {'bytedance-seed/seed-1.6-flash','bytedance-seed/seed-2.0-mini','bytedance-seed/seed-1.6','bytedance-seed/seed-2.0-lite'} <= ids)"
all 4 present: True
```

**Phase D:**
- CLAUDE.md Doc Sync Matrix — 3 triggers: new file → INDEX; feature → FEATURES; code change → CHANGELOG
- CLAUDE.md § Plan lifecycle — EXECUTED plans MUST be archived

```
$ grep -n "docs/development/plans/archived\|EXECUTED" /opt/fabrik/CLAUDE.md | head -3
90:| new `.md` outside allowlist | root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` · `docs/superpowers/plans/**` · `docs/superpowers/specs/**` |
```

## Self-audit

**(a) Coverage — every "What we already agreed" mapped to a phase:**

| Item | Delivered by |
|---|---|
| Shim dropped by fabrik-lib module owner | Phase A step 1 (verify + BLOCKED if missing) |
| Shim reuses `_transport.run` + `_client.OpenRouterClient` + `_dotenv.load_env` | Phase A step 2 + 3 (import probes) |
| Two-step decomposition: `generate_samples` → `evalplus.evaluate --samples` | Phase B step 4 (`_run_one` refactor) |
| Zero changes to plan-2 Phase A/B/C/D output | Phase B (only `_run_one` + main's outer loop refactored + 3 mocks updated; plan-2 commits untouched) |
| Real cost tracking (single-attempt Result.cost_usd) | Phase B step 5 (`main` accumulates from `_run_one`'s 4-tuple return) |
| Live bench populates humaneval_score + coding_score | Phase C step 3 + 5 (DB verified UTC-today) |
| Return to plan-2 Phase F | Phase D step 4 (plan-2 Status BLOCKED → EXECUTED) |
| Archive both plans | Phase D step 7 (both plans `git mv` to archived/) |
| Rejected: patch evalplus upstream / skip live bench / use LiveCodeBench | out-of-scope per spec; no plan-3 phase attempts them |
| Concurrency cap (still-open residual #1) | Phase B step 5 (outer `max_workers=1`) + B3 test |
| Cost aggregation precision (resolved residual, single-attempt) | Phase B step 5 (sum of returned per-unit cost); B4 test proves shim's returned float |

Zero coverage gaps.

**(b) Cross-phase signature consistency:**
- `openrouter_complete.generate_samples(model, problems, out_path, ...)` — produced by shim (Phase A verifies), consumed by `_run_one` (Phase B) — consistent.
- `openrouter_complete.generate_samples(...) -> tuple[Path, float]` — return type consumed as `(samples_path, cost)` in `_run_one` — consistent.
- `_run_one(u: BenchUnit) -> tuple[BenchUnit, bool, str, float]` — produced Phase B, consumed by `main` outer loop — consistent (4-tuple both sides).
- `main` cost aggregation `total_spend += cost` — consumed by TOTAL_SPEND_USD emission (unchanged from plan-2 Phase C) — consistent.
- `parse_eval_results(results_json) → dict[str, float]` — plan-2 Phase B function, unchanged, consumed after `evalplus.evaluate --samples` writes `eval_results.json` — consistent.
- `write_scores(conn, model_id, scores)` — plan-2 Phase C function, unchanged, consumed at Phase C step 3 verify — consistent.

**Grounding passes run this turn:**
- `select_rules.py` → 19 ACTIVE + 31 AVAILABLE; picked 6 relevant for plan-3 (core/10-python, 40-doc, 45-testing, 58-resilience, 62-subagents, cost-budget)
- Verified plan-2 committed state (commits 135231a7 → edad5ac5 → 791fdc04)
- Verified `microbench_coding.py:91,164,199,217,310,433` anchor points against real file
- Verified evalplus `get_human_eval_plus()` = 164 / `get_mbpp_plus()` = 378 (live)
- Verified evalplus `--samples <path>` param at `evaluate.py:127-129`
- Verified all vendored `libs/subagents/` primitives (`_transport.run`, `Liveness`, `Result`, `OpenRouterClient`, `_dotenv.load_env`)
- Verified fabrik-lib AI's 10 cited `path:line`s for the `Result.cost_usd` single-attempt contract (this session's Pass-3 self-verification)

Fixed point: not yet — `/fabrik-plan-review` runs next per Phase 5 handoff. This draft is grounded but has not yet been through an adversarial parallel grounder round.

## Residual unknowns

### Resolved (during this drafting)

- **evalplus's `samples` param name.** RESOLVED — `evalplus.evaluate(dataset, samples: Optional[str] = None, ...)` at `evaluate.py:127-129`; verified this session.
- **evalplus problem-dict `"prompt"` key stability.** RESOLVED — inherited from CONVERGED spec Pass 1; both accessors verified.
- **`Result.cost_usd` single-attempt guarantee.** RESOLVED — fabrik-lib AI's 2-finder pool review confirmed + Pass-3 self-verified 10 cited `path:line`s.
- **Outer × inner concurrency multiplier.** RESOLVED — Phase B step 5 caps outer `max_workers=1`; B3 test proves serialization.
- **Naming: `openrouter_complete.py`.** RESOLVED — matches shim's own naming from the module owner's draft.
- **`env_path=".env"` vs `"/opt/fabrik"` for `_dotenv.load_env`.** RESOLVED — `_run_one` passes `env_path="/opt/fabrik"` explicitly (spec §Chosen approach + Context Ledger `_dotenv.py:141` row).

### Still-open (each has a self-service resolution step — none block execution)

1. **Shim's exact filename + module owner drop timing.** The plan assumes the module owner drops the shim at `scripts/kilo-benchmarks/openrouter_complete.py`. **Self-service resolution at Phase A step 1:** if the file exists at that path → proceed. If it doesn't → BLOCKED with the explicit blocker message (not a mid-run stall — the file existence check is deterministic). The executor stops with a clear signal for the user to prompt the module owner + resume.

**Zero cross-AI dependencies remaining at plan trust** (the shim drop is a one-time external artifact, checked by Phase A step 1 with BLOCKED if missing — this is the correct pattern for a "wait for external deliverable" workflow: probe + halt cleanly if not there, not silently spin).

## Handoff

**Next command (this turn, automatic):** `/fabrik-plan-review docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md`.

**After CONVERGED:**
- User relays "plan-3 is drafted" to fabrik-lib module owner → they drop the shim.
- User runs `/fabrik-execute-plan docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md`.
- Plan-3 EXECUTED → plan-2 also EXECUTED (Phase F closed via plan-3 Phase D) → both archived.

**Expected wall clock (execution):** ~30-45 min for Phase B code + tests + ~30-60 min for Phase C live bench + ~15 min Phase D docs. Total: ~1.5-2h autonomous once the shim is in place.

**Expected spend:** ~$2.66 for Phase C live bench (unchanged from plan-2 spec) + ~$0.30 for pool `/fabrik-review` passes ≈ **$3.00 total**.
