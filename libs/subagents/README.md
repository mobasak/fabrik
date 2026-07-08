# subagents — vendorable parallel-subagent runtime (OpenRouter-direct)

Recruit and run **N subagents in parallel** over the **OpenRouter API** for
coding / research / docs / review / text tasks. One uniform Python API —
`run_agents([AgentSpec, …]) → [AgentResult]` — composes the OpenRouter transport
vendored from [`ai-consult`](../ai-consult) with a tool-loop, per-agent git
worktrees, an owned-paths scope check, caps, and a durable provenance ledger.

`run_command` is confined by an **OS sandbox** (bubblewrap) — read-only filesystem
except the worktree, no network, **fail-closed** — on top of the software layers (see
[Containment](#containment)).

## Quickstart

```python
from subagents import run_agents, AgentSpec

results = run_agents(
    [
        AgentSpec(
            task="Add a unit test for the retry path in http_client.py",
            model="anthropic/claude-sonnet-5",
            owned_paths=["tests/*.py"],          # globs this agent may touch
            max_turns=8,
            max_cost_usd=0.50,
        ),
        AgentSpec(
            task="Draft a CHANGELOG entry for the 1.4 release",
            model="anthropic/claude-haiku-4-5",
            owned_paths=["CHANGELOG.md"],
            tools_enabled=False,                 # single-shot (no tool loop)
        ),
    ],
    repo="/path/to/your/repo",
)

for r in results:
    print(r.agent_id, r.status, r.cost_usd)
    if r.status == "done":
        print(r.diff)          # the agent's change — YOU review + apply it; nothing auto-applies
```

`run_agents` is synchronous; `arun_agents(...)` is the async core (use it from
inside an event loop). Set `OPENROUTER_API_KEY` in the environment.

Agents with **disjoint** `owned_paths` run in parallel (bounded by
`max_concurrency`, default 4); agents whose globs could **overlap** are
serialized so two agents never race on the same file.

## Containment

Defence in depth — an OS sandbox under the workflow layers:

| Layer | Guarantee |
|---|---|
| **OS sandbox (bubblewrap)** | `run_command` runs under `bwrap --ro-bind / / --bind <worktree> --unshare-{user,pid,ipc,uts,net} --die-with-parent --new-session`: the **whole filesystem is read-only except the worktree**, **no network**, isolated namespaces. An allow-listed `python`/`pytest` (arbitrary execution) that tries to write an absolute path outside the worktree hits `EROFS` at the kernel. **Fail-closed:** if `bwrap`/user-namespaces are unavailable, `run_command` is *refused*, never run unsandboxed (`AgentSpec.sandbox=False` is the trusted opt-out). Same primitive OpenAI Codex uses on Linux/WSL2. |
| **worktree-per-agent** | each agent works in its own detached `git worktree` under `<repo>/.tmp/subagents/` — never the caller's working tree |
| **diff-captured, never applied** | the agent's changes are returned as a unified `diff`; **nothing is applied to your repo** — you review and apply |
| **scope check** | the authoritative `git diff --cached --name-status` path list is checked against `owned_paths`; a change that left its bounds flips the result to `status="out_of_scope"` (renames / quoted / mode-only changes can't slip past) |
| **caps** | per agent: `max_turns`, `max_cost_usd`, `wall_clock_s` (the last is enforced *mid-call*, not just between turns) |
| **provenance ledger** | every run is appended (JSONL) with task/model/status/cost/diff — secret-free (a strict whitelist; API keys and system prompts never land on disk) |

**Residual (know the boundary — it's write-confinement, not read-confinement):** the sandbox is read-only-root, so a command can still *read* any host file the user can (another project's `.env`, `~/.ssh`, a sibling worktree). `--unshare-net` stops it phoning out, but **the model's own output is an exfiltration channel** (it flows back to the orchestrator/OpenRouter), so no-network does NOT make reads safe — keep secrets OUT of readable paths. `_stripped_env` keeps orchestrator secrets out of the child's env. To also block *reading* specific secrets, mask them (`--tmpfs` over their parent) — a documented follow-up, as is a `--seccomp` syscall filter. Always add `.tmp/` to your `.gitignore` (that's where the worktrees live). Requires `bubblewrap` on any host running tool-enabled agents.

## API

- `AgentSpec(task, model, system="", owned_paths=[], tools_enabled=True, allowed_commands=None, sandbox=True, web_tools=None, body=None, max_turns=8, max_cost_usd=None, wall_clock_s=1800.0, task_type="code", mcp_servers=None, mcp_config=None, mcp_allow_unlisted=False)`
  - `allowed_commands`: overrides the `run_command` binary allow-list — `None` = the minimal default toolchain, `frozenset()` = **forbid all execution** (file tools still work). This is the "let it edit files but not run code" knob.
  - `sandbox` (default `True`): OS-sandbox `run_command` in the worktree via bubblewrap, **fail-closed** (refuse if `bwrap`/userns absent). Set `False` only for a trusted agent on a host without `bwrap`.
  - `body`: per-agent OpenRouter request-body passthrough, merged **under** the loop's tool schemas — carries a model's REQUIRED hints, e.g. `{"max_tokens": 20000}` (glm-5), `{"provider": {"only": ["Minimax"]}}` (minimax pin), `{"reasoning": {"exclude": True}}` (deepseek). See `CODING_SUBAGENT_SELECTION.md` for the per-model hints; the caller sets it (`pick_models` does not).
  - `web_tools`: web tools to enable for this agent (see below) — `None`/empty = **none** (they cost money + reach the internet).
  - `mcp_servers`: MCP research servers to enable (see "MCP research tools" below) — `None`/empty = **none**. Scoped per task type like `web_tools`.
  - `mcp_config`: the MCP server definitions — a **path** to the standard `{"mcpServers": {…}}` file (the fleet's `/opt/fabrik/mcp.json`, **non-dot**) OR the **bare** `{name: def}` dict. `None` ⇒ MCP disabled.
  - `mcp_allow_unlisted` (default `False`): conscious opt-out to enable a server **not** in `SAFE_RESEARCH_SERVERS`. MCP tools run **outside** the sandbox, so an FS/shell/exec server would bypass containment — the default **refuses** it (like `sandbox=False` for the OS sandbox).
  - `task_type`: a provenance/selection tag (`spec`/`plan`/`code`/`review`/`docs`/`research`) — it does not change how the loop runs, but it is recorded to the ledger so aggregating real runs by task type sharpens `pick_models` over time. Pair it with `pick_models(task_type, …)` to choose the model.
  - Caps: `max_turns` + `wall_clock_s` are **hard**; `max_cost_usd` is **best-effort** (only enforceable when the provider reports cost — `max_turns` is the real spend backstop). Note `max_cost_usd` covers only **model** spend, not the paid web-tool APIs.
- `AgentResult(agent_id, text, diff, status, provider, cost_usd, turns, error=None, tool_calls={}, latency_s=None)`
  where `status ∈ {"done", "capped", "error", "out_of_scope"}`, `tool_calls` is a name→count map of the tools the agent actually ran (provenance, also recorded in the ledger), and `latency_s` is the run's wall-clock seconds (a value metric).
  (An `error` run may still carry a partial `diff` — always review it before applying; `out_of_scope` is computed for `done`/`capped` only.)
- `run_agents(specs, *, repo, ledger_path=None, max_concurrency=4, on_progress=None) -> list[AgentResult]`
- `arun_agents(specs, *, repo, ledger_path=None, max_concurrency=4, on_progress=None) -> list[AgentResult]` (async)
  - `on_progress(event)`: opt-in **live** callback fired once per **successful** transport turn, per agent, with `{"agent_id", "turns", "cost_usd", "provider", "tools"}` — for a babysitting view of cost/progress mid-run. A turn that ends in a transport **error/exception**, or a wall-clock cap hit *before* the first call, emits **no** event — the terminal status/cost comes from the returned `AgentResult` (and the ledger), not `on_progress`. It is called from a worker **thread**, and with parallel agents from **multiple threads concurrently** — keep it cheap + thread-safe (a bare file append can interleave; use a lock, a queue, or per-`agent_id` files). A raising callback is swallowed, never crashing a run.
- `methodology(kind) -> str` — a distilled `/fabrik-*` discipline prompt (`kind ∈ {research, spec, plan, review, code, docs}`) the assigning agent passes as `AgentSpec.system` per task type. (An OpenRouter model can't invoke Claude Code skills — this delivers the methodology as a prompt.)

## Selecting workers (`pick_models`) — cheapest that clears the bar

The orchestrator is the boss; these models are the workers. `pick_models` encodes the
"opt wise" rule once so **every project that vendors this module selects workers the same
disciplined way** — pick the cheapest model that clears the quality bar for the task type,
honoring a cost ceiling and a reliability exclude-list.

```python
from subagents import pick_models, AgentSpec, run_agents

# one worker for a plan, under a $1/M output ceiling, cheapest-that-ranks:
model = pick_models("plan", n=1, max_cost_per_mtok=1.0, prefer="value")[0]
# a 3-model A/B for a spec, skipping one that failed earlier this session:
models = pick_models("spec", n=3, exclude=("deepseek/deepseek-v4-flash",))
specs = [AgentSpec(task=brief, model=m, task_type="spec", tools_enabled=False) for m in models]
results = run_agents(specs, repo=repo)
```

- `pick_models(task_type, n=1, *, max_cost_per_mtok=None, exclude=(), prefer="quality"|"value", live=None, allow_above_cap=False)`
  — `prefer="value"` re-ranks toward a nearly-as-good-but-cheaper worker (rank-weight ÷ price);
  `max_cost_per_mtok` is an *additional, tighter* ceiling (it can only lower the always-on fleet cap,
  never raise it); `exclude` is the reliability lever; `live` prices models beyond the static table
  (see below); `allow_above_cap=True` is the **On-request tier** — it drops the always-on ≤$1.5 cap so
  a pricier benchmarked model can be selected (see the allowed-pool bullet).
- `TASK_KINDS`, `TASK_MODEL_TABLE` (read-only view), `model_price(model, *, live=None)` are also exported.
- **Pricing — static table + live fallback.** `model_price` reads a vendored static table (the
  curated pool, seeded from `CODING_SUBAGENT_SELECTION.md`) offline. For a model **not** in that
  table, `live` fetches OpenRouter's live prices — `live=True` forces it, `live=False` forces
  offline, `live=None` (default) defers to env **`SUBAGENT_LIVE_PRICING=1`**. The live list is
  fetched **once per process** (best-effort — a fetch failure ⇒ `None`, and a cost ceiling then
  **fail-closes** and excludes the model rather than guessing). So a vendored agent can cost-bound
  *any* OpenRouter model, not just the benchmarked ones.
- **Data provenance (two fleet-wide rails):** the ranking is seeded from the fleet's
  daily-refreshed `CODING_SUBAGENT_SELECTION.md` (`kilo-benchmarks`, synced from `/opt/fabrik`)
  plus empirical fabrik runs; every run's `task_type` is recorded to the ledger so aggregating
  real cost×quality×reliability per task type refines the table over time (the flywheel).
  Only models from the allowed `CODING_SUBAGENT_SELECTION.md` pool appear.
- **Allowed pool — cost policy (2026-07-08), enforced IN `pick_models`:** a model is selectable only
  if its **output price is ≤ $1.5/Mtok**. This cap (`_MAX_POOL_PRICE_PER_MTOK`) is enforced **inside
  `pick_models` itself** — it is the SOLE gatekeeper. Even if the synced `CODING_SUBAGENT_SELECTION.md`
  is refreshed with a pricier model, or a caller passes a looser `max_cost_per_mtok=`, a >$1.5 model can
  never reach the default (Auto) pool. The current members are five benchmarked models —
  `deepseek-v4-flash`, `deepseek-v3.2`, `minimax-m2.5`, `deepseek-v4-pro`, `minimax-m3` (output
  $0.18–$1.20). Models over $1.5 (glm-5/5.x $3.00+, kimi $2.03–3.50, grok $2.50, qwen $3.75) stay
  *priced and rankable* but are never returned by default.
- **On-request tier — `allow_above_cap=True`:** because `pick_models` is the single enforcement point,
  packs and callers name no roster and set no cap of their own — they just call `pick_models`. To
  deliberately reach a pricier model for an explicit opt-in benchmark, pass `allow_above_cap=True`
  (then only your own `max_cost_per_mtok`, if any, applies). Treat it like `sandbox=False` in review:
  justified at the call site or it's a bug.
- **Fresh empirical ranking (opt-in):** when the hub ships the aggregated
  `TASK_SUBAGENT_SELECTION.md` (from `kilo-benchmarks`, synced fleet-wide — one `### <task_type>`
  section per kind, ranked by success × quality / cost), point env **`SUBAGENT_SELECTION_DOC`** at
  it and `pick_models` uses its per-task **empirical** rank order over the vendored default —
  mtime-cached, fail-soft (a missing/empty/stub doc ⇒ the vendored `TASK_MODEL_TABLE`, zero
  regression). `load_task_ranking(path=None, *, min_n=0, max_age_days=None)` is exported for
  direct use (`path` defaults to env `SUBAGENT_SELECTION_DOC`).

## Centralized run-metrics (opt-in) — one shared `subagent_runs` on `postgres-main`

Every run's metrics can be aggregated fleet-wide into **one shared Postgres table**, so the
selection flywheel learns from *all* projects — without any agent writing another project's
repo (they all write to the shared DB *service* over the network, exactly like `cost-budget`'s
cross-project `cost_ledger`). Turn it on by setting **one env var**; it is otherwise a no-op.

- **Where:** the `subagent_runs` table on the shared **`postgres-main`** (never `localhost`).
  DSN from env **`SUBAGENT_RUNS_DSN`** (`record_run`'s default `dsn`). Owning project from env
  **`SUBAGENT_PROJECT`** (unset ⇒ `"unknown"`).
- **What:** one row per run — `ts, project, agent_id, task_type, model, provider, status,
  cost_usd, turns, latency_s, quality_score, tool_calls`. The schema is `SUBAGENT_RUNS_DDL`
  (exported); apply it with `python -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)" | psql "$SUBAGENT_RUNS_DSN"`.
- **How — the orchestrator writes it, once, after judging.** The centralized row is written by
  **`record_run(record, quality_score=…)`** — NOT automatically by the run. The local JSONL
  `ledger` (`ledger_path`) is written on every run and is the durable audit copy, but it does
  **NOT** auto-write to Postgres: a runtime auto-write could only carry a NULL `quality_score`
  and would then **duplicate** the orchestrator's quality-bearing row (the table is INSERT-only,
  so two rows can't be merged). So: **one run → one flywheel row, via `record_run`.** It is
  **fail-open** (a Postgres outage never breaks a run), least-privilege (`INSERT`-only; the table
  is provisioned centrally by the hub, no auto-DDL), and `psycopg` is lazy-imported.
- **`quality_score`** is the one field only the **orchestrator** can supply — a verdict from your
  gate/tests/review, not a measurement. After you judge a run, call
  `record_run(result, quality_score=<0–5>, project=…)` (WSL dev: pass a peer-auth `connect=`;
  VPS: the injected `SUBAGENT_RUNS_DSN` connects directly). Skipping it means the ranking never
  improves.

## Web research tools (opt-in, paid)

Subagents can research the web, scrape/browse pages, and look up library docs via
five **opt-in, env-keyed** tools that call hosted APIs. They are **off by default**
(they cost money + reach the internet); the assigning agent enables them per task
type via `AgentSpec.web_tools`, and each needs its API key in the environment:

| Tool | Service | Env key |
|---|---|---|
| `web_search` | Exa (`/search`) | `EXA_API_KEY` |
| `web_search_brave` | Brave (`/res/v1/web/search`) — an alternative search engine to Exa | `BRAVE_API_KEY` |
| `web_scrape` | Firecrawl (`/v2/scrape`; `actions` drive click/fill/screenshot — no puppeteer needed) | `FIRECRAWL_API_KEY` |
| `web_crawl` | Firecrawl (`/v2/crawl`, async) | `FIRECRAWL_API_KEY` |
| `docs_lookup` | Context7 (`/api/v2/context`) | `CONTEXT7_API_KEY` |

```python
from subagents import AgentSpec, methodology

spec = AgentSpec(
    task="research the current OpenRouter rate limits and summarize",
    model="anthropic/claude-sonnet-5",
    system=methodology("research"),
    owned_paths=["notes/*.md"],
    web_tools=frozenset({"web_search", "docs_lookup"}),  # opt-in, per task type
)
```

Enforcement is two-way: a disabled web tool is neither advertised to the model nor
executed if the model asks for it. A tool whose key is unset returns an error
result (never crashes). Web-tool usage is recorded in `AgentResult.tool_calls` +
the ledger. `max_cost_usd` does **not** bound web-API spend — set `max_turns`
conservatively and enable web tools only where the task needs them.

## MCP research tools (opt-in, outside the sandbox)

Instead of (or alongside) the per-provider `web_tools`, an agent can reach the fleet's
**Model Context Protocol** servers — the *same* servers Claude Code uses — via one
integration that auto-syncs with whatever MCP servers are wired into the fleet. Each MCP
tool is advertised to the model as `{server}__{tool}` and proxied to its server. Enable
per agent with `mcp_servers` + `mcp_config`:

```python
from subagents import AgentSpec, methodology

spec = AgentSpec(
    task="research the current OpenRouter rate limits and summarize",
    model="anthropic/claude-sonnet-5",
    system=methodology("research"),
    tools_enabled=False,                       # research config — no file/command tools
    mcp_servers=frozenset({"exa", "context7"}),  # opt-in, per task type
    mcp_config="/opt/fabrik/mcp.json",         # the fleet source-of-truth (non-dot)
)
```

⚠️ **Security — the load-bearing constraint.** MCP tool calls run in the loop **process,
OUTSIDE the bubblewrap `run_command` sandbox** (they need the network + an `npx`
subprocess). So a filesystem / shell / exec MCP server would hand an untrusted model
**unsandboxed I/O — a full bypass** of the sandbox. Therefore the module ships a fail-safe
allowlist `SAFE_RESEARCH_SERVERS = {exa, brave-search, firecrawl, context7}`: a server not
in it is **refused** unless you pass `mcp_allow_unlisted=True` (a conscious opt-out). Keep
browser/FS/exec MCPs off the untrusted pool.

- **Config shapes:** `mcp_config` as a **path** reads the standard `{"mcpServers": {…}}`
  wrapper (the hub's **`/opt/fabrik/mcp.json`** — *non-dot*, so Claude Code doesn't
  auto-load and double-register it); as a **dict** it's the bare `{name: def}` map. Server
  `env` values like `${EXA_API_KEY}` are expanded from the process env (keys never inlined).
- **Optional dependency:** the `mcp` SDK + **Node/`npx`** are lazy-imported — a host without
  them (or an unreadable config) makes MCP **quietly unavailable**: the agent runs with
  whatever `web_tools` you enabled (or **no** tools if you set none), never crashing. Enable
  `web_tools` alongside `mcp_servers` if you want a guaranteed fallback on such a host.
- **Enforcement is two-way** (advertised + routed only if enabled) and **TOTAL** (a failing
  MCP call returns an error to the model, never crashes the run). `max_cost_usd` does **not**
  bound MCP spend — cap `max_turns`.
- **See EVERY tool work end-to-end** — `tests/test_all_tools_e2e.py` drives all three families
  through the real `run_loop` with no mocks: every tool a real `npx` MCP server advertises, all
  six file/command tools (`run_command` bubblewrap-sandboxed), and all five web tools against
  their real hosted APIs. Opt-in so the fast unit gate stays deterministic:
  `RUN_MCP_INTEGRATION=1 python -m pytest tests/test_all_tools_e2e.py -v -s`
  (needs Node/`npx` + the `mcp` SDK; the web tools additionally need their `*_API_KEY` in the env,
  else they skip — e.g. `set -a; . /opt/fabrik/.env; set +a`).

## Reviewing code with the pool (incl. a repo-wide review) + benchmarking reviewers

`run_agents` isn't only for *writing* code — a common use is **fanning a review out to N models**,
either to review real code you'll act on, or to **benchmark models as reviewers** and score them.

- **Native vs pool.** `/fabrik-review` and `/fabrik-repo-review` dispatch **Claude**
  `fabrik-reviewer` finders. To use **OpenRouter models** as the reviewers (or to score them), run
  them through *this* pool with `task_type="review"`.
- **Reviewers are single-shot** — they read code and **report** findings, they don't write. So use
  `tools_enabled=False` (no worktree, **no bwrap needed**), `system=methodology("review")`, and put
  the code/diff to review in `task`. Cheap + fast (~1 turn).

```python
from subagents import run_agents, AgentSpec, methodology, record_run

MODELS = ["minimax/minimax-m3", "qwen/qwen3.7-max", "x-ai/grok-4.20"]   # proven + on-trial
specs = [AgentSpec(
    task=review_brief,                 # the unit's code + "find bugs, cite path:line"
    model=m, system=methodology("review"), task_type="review",
    tools_enabled=False,               # report-only — nothing to write
    max_turns=2, max_cost_usd=0.25, wall_clock_s=600,   # tight (glm has runaway history)
) for m in MODELS]
results = run_agents(specs, repo="/path/to/repo")
for r in results:
    record_run(r, quality_score=<0-5>, project="my-project")   # YOUR verdict → the flywheel
```

- **Repo-wide (a big review).** Don't hand one agent the whole tree — **partition into units**
  (files / packages / the changed surface) and fan out: one review per **(unit × model)**, run in
  parallel bounded by `max_concurrency`, then aggregate the findings. Disjoint `owned_paths` per unit
  keep them parallel; keep each unit's brief small enough that a reviewer holds it in context. For
  the *authoritative* whole-repo pass prefer the native `/fabrik-repo-review` (Claude finders) — use
  the pool for the **model benchmark** over the same surface.
- **Which reviewer to trust.** Act on findings from a **proven** reviewer — native Claude finders,
  or (from the fleet benchmark) **`minimax/minimax-m3`** (best-tested at review). Run **unproven**
  models (e.g. `qwen3.7-max`, `glm-5.x`, `grok-4.20`) as a **scored benchmark alongside**, never as
  the sole reviewer of code you'll ship — then promote only what the flywheel numbers earn. Set
  `SUBAGENT_LIVE_PRICING=1` so any model's cost is tracked even beyond the curated pool.
- **Guardrails** (see `PROPOSED_RULE-using-subagents.md`): keep `max_turns`/`max_cost_usd`/
  `wall_clock_s` **tight**; do **not** set a high `body={"max_tokens": …}` for glm models (that
  caused a runaway); babysit the first run; never route **secrets/auth/migrations** to the pool.

## Install (vendor, don't import)

Per the fabrik-lib rule, **copy this folder** into your project and install its deps:

```bash
cp -r subagents/ your-project/libs/subagents/
pip install -r your-project/libs/subagents/requirements.txt   # httpx==0.28.1
```

Requires the system `git` (worktrees + diffs are driven via `subprocess`). No
Python git dependency; everything else is the standard library.

**For tool-enabled agents** (`tools_enabled=True`), install **bubblewrap** —
`run_command` is sandboxed through it and fails closed without it:
`apt install bubblewrap` (Debian/Ubuntu/WSL2) · `dnf install bubblewrap` (Fedora).
Needs unprivileged user namespaces (default-on modern kernels; WSL2 yes, WSL1 no).
Single-shot pools (`tools_enabled=False`) don't need it.

## Vendored from

- **`ai-consult`** — the OpenRouter transport (`_client.py` = `OpenRouterClient`
  httpx/SSE; `_transport.py` = `run`/`arun`, the store/persist coupling stripped)
  and the consult-loop / `ConsultStore` patterns (adapted into `loop.py` /
  `ledger.py`). A bug found in the vendored transport belongs upstream in
  [`ai-consult/UPSTREAM_FEEDBACK.md`](../ai-consult/UPSTREAM_FEEDBACK.md).

## Files

| File | Responsibility |
|---|---|
| `agent.py` | public `run_agents` / `arun_agents` + `AgentSpec` / `AgentResult`; the concurrency orchestration |
| `loop.py` | one subagent's executor — single-shot or tool-loop, with caps |
| `tools.py` | the tool registry + workdir-scoped executors (read/list/grep/write/apply_patch/run_command) |
| `sandbox.py` | bubblewrap OS sandbox for `run_command` — read-only-root + writable-worktree + no-net, fail-closed |
| `web_tools.py` | opt-in hosted web-research tools (Exa/Brave/Firecrawl/Context7) — the no-dep HTTP fallback |
| `mcp_tools.py` | opt-in MCP-client provider — connects the fleet's MCP servers, `SAFE_RESEARCH_SERVERS` allowlist, dedicated-thread async→sync bridge (lazy-imports `mcp`) |
| `workspace.py` | git worktree lifecycle + owned_paths disjointness + authoritative diff-scope |
| `ledger.py` | durable append-only JSONL provenance (secret-free record whitelist) |
| `methodology.py` | `methodology(kind)` — the distilled `/fabrik-*` discipline prompts + `METHODOLOGY_KINDS` |
| `select.py` | `pick_models` worker selection + `TASK_KINDS` / `TASK_MODEL_TABLE` / `model_price` / `load_task_ranking` |
| `pg_ledger.py` | opt-in centralized run-metrics — `record_run` (INSERT-only, fail-open) + `SUBAGENT_RUNS_DDL` (lazy-imports `psycopg`) |
| `_client.py` / `_transport.py` | vendored OpenRouter transport (do not edit — sync from ai-consult) |
