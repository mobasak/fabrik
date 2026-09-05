# Fabrik — Features

**Last Updated:** 2026-09-02

## Scaffold error-reporting — a deny-by-default GlitchTip scrubber, not a flag list (2026-09-05)

Every Python scaffold now vendors `templates/scaffold/python/glitchtip_init.py`: a DENY-BY-DEFAULT event
scrubber where every event, request, header, span, context, frame and mechanism key is an explicit
ALLOWLIST, plus a LEAF-SHAPE rule that nulls an allowlisted key holding an unexpected container — the
part that closes a channel nobody enumerated. Registered as **both** `before_send` and
`before_send_transaction`, because sentry-sdk skips `before_send` entirely for transaction events
(`client.py`: `event.get("type") != "transaction"`), so a scrubber on one hook leaves every sampled
transaction unscrubbed. Alongside it: `include_local_variables=False`, `max_request_body_size="never"`,
`include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default
`LoggingIntegration(event_level=logging.ERROR, level=None)` (D-126).

**It replaces a two-flag mandate that measurably was not enough.** Pointing the guard at the init the
scaffold shipped under the old mandate produces
`secrets reached the wire through: ['apikey', 'header', 'otp', 'query']` — the two flags closed the DSN
in frame locals and the password in the request body and left four channels open: a breadcrumb carrying
an outbound URL's `apikey`, a custom request header (the SDK's own scrubber knows seven header names and
`X-Signing-Secret` is not one), a `logger.error` interpolation, and a URL query token. Reported by
site-provisioner and reproduced here rather than believed.

**Reaches three scaffold types** — `python-api`, `python-api-gpu`, `saas-skeleton` (census re-derived by
scaffolding each type and looking for the emitted file). `node-api` has the JS module; the other seven
types emit no Sentry init at all, and `chrome-extension` has its own isolated `BrowserClient`.

**The guard is the feature's proof, not its documentation.** `tests/test_scaffold_glitchtip_security.py`
swaps the transport's `capture_envelope`, raises inside a real FastAPI request with six secrets in play,
and substring-searches everything that would hit the wire — never a field list — asserting the
TRANSACTION event as well as the error. `GLITCHTIP_GUARD_MODULE` aims the same assertions at any module,
which is how the pre-fix leak above was measured. Vendored from site-provisioner at a revision recorded
in the module docstring, verified at execution time rather than read from the plan. Nothing back-fills an
existing project: vendor the template over your own copy and prove it with the guard.
Mandate: `.windsurf/rules/core/55-observability.md` § Error Reporting.

## Grounding-integrity canary — the refuses-ungrounded flywheel axis (2026-08-29)

Weekly missing-input canary probes (`scripts/sysadmin/canary_grounding.py`) measure, per pool
model, whether it fabricates when its grounding input is absent — the axis invisible in normal
scoring. Binary PREFIX judge (`CANNOT-GROUND: <path>` → 5, else 0; provider failures never
scored), ordinary `subagent_runs` rows under `project="canary-grounding"`, aggregated by the
selection-doc generator into a `grounding` column (`✓`/`✗(score)`/`—`, ≥2-probe floor, 30-day
decay) in `TASK_SUBAGENT_SELECTION.md`. The ×0.5 ranking multiplier for `review`/`docs`/`plan`
is filed to fabrik-lib (`select.py` doc-parser enhancement) and lands with a re-vendor. The same
change fixed the generator's organic aggregation to honor `set_quality`'s scored-delta contract
(latest-non-NULL wins; deltas no longer inflate `n`). Reference: `docs/reference/canary-grounding.md`.

## Review microbench — ground-truth code-review quality for the subagent pool (2026-07-18)

`/opt/ai-model-catalog/engine/microbench_review.py` scores a model's ability to **catch bugs in a review**,
against ground truth — not the circular flywheel self-score. The corpus is deterministic AST mutation
of 8 self-contained victim functions (the mutmut operator classes — comparison flip, arithmetic swap,
boolean and/or flip): 22 planted defects, each at a known line, plus 8 un-mutated controls. Every model
in the pool reviews every item (single-shot `read_only` via the existing `libs.subagents.run_agents` +
`pick_models`), returning JSON `{line, bug}`. Two numbers, both mandatory:

- **recall** — planted defects caught / total (accuracy),
- **precision** — 1 − (controls falsely flagged / controls) (noise; a "flag-everything" model has perfect
  recall and `F1 = 0`).

`score/5 = F1(recall, precision) × 5` writes to `model_task_baseline(task_type='review')`, which
`rank_task_subagents._tier_baseline` already prefers as the per-task prior → `TASK_SUBAGENT_SELECTION.md`
→ `pick_models`. **Cost + speed** are reported and persisted alongside in the `model_review_metrics`
table + a dated JSON artifact: **cost is OpenRouter's REAL billed charge** (`usage.cost`, requested via
`"usage": {"include": true}`) normalized to `$/1k` reviews — not a `tokens × list-price` estimate, so it
reflects caching/BYOK/rounding/provider rate; `out $/M` (the list output price) is kept beside it for
reference. Speed = p50 `latency_s` + `tok/s`. The gap between `out $/M` and `$/1k` is **verbosity** — a
model billed at $2/M that emits ~950 tokens/review costs ~10× one billed at $3/M that emits ~90
(measured: `seed-2.0-lite` vs `gemini-3-flash-preview`), so `$/1k` (real spend) is the number to rank on,
never the per-token sticker price.

**Two dispatch modes.** `--all` uses the pool (`run_agents`) for pool-eligible models. `--direct` calls
OpenRouter directly (`run_direct()`) and reaches **every** model — the pool attaches provider constraints
that 404 some models (`"no endpoints found that satisfy"`) even though they answer a plain request. A
benchmark must *reach a specific model*, not route around it, so `--direct` is the correct mode for
grading a candidate list; the pool remains correct for real review *work*. Errored/empty calls are
excluded from recall/precision (a 404 is never a "miss") and mostly-failed models are flagged UNMEASURED,
never persisted as a 0 prior. First full run (2026-07-18) graded 35 candidate models — `gemini-3-flash-preview`
led at A/4.21 (73% recall, 100% precision, $0.22/1k, 1.6s); the precision term correctly sank
`qwen3-coder-flash` (86% recall but 12% precision — a flag-everything model) to a D. `--smoke` /
`--all [--direct] [--models …]` / `--report`.

## Armed adversarial review — rubric injection (Tier 3 of the reliability ladder) (2026-07-18)

Every review boundary now ARMS its finders instead of hoping they read the rules: `scripts/review_rubric.py`
(fleet-synced, stdlib-only) emits an injectable rubric — the **mandatory-core floor** (`core/35-security-auth`
+ `core/25-data-postgres` + `core/30-ops` + all twelve 12-Factor axes, always injected regardless of glob, so
a review is never un-armed) plus every pack whose glob matches a changed path (mandate lines only), plus —
only for command-chain reviews (`--workflow mega|ettw`) — the authoring-QA checklist items. Wired into
`/fabrik-review`, mega-`04`, ettw-`08`/`10`. Byproduct: a `# promote-to-check_*` candidate list feeding the
drain-Tier-3-into-Tier-1 direction. Honest bound (spec L1): injection raises compliance probability — it is
maximally-enforced, not a guarantee. Design: `docs/superpowers/specs/archived/2026-07-18-fabrik-factory-architecture-design.md`.

## Coding microbench — live pass@1 for the coding-subagent ranking (2026-07-11)

`/opt/ai-model-catalog/engine/microbench_coding.py` runs a live 3-step pipeline per `(model, dataset)` unit — `openrouter_complete.generate_samples` (via the vendored `libs.subagents._transport` primitive) → `evalplus.sanitize` (tree-sitter extracts Python from prose + fenced code) → `evalplus.evaluate --samples` (sandboxed pass@1 grading) — and writes real `agents.humaneval_score` + `agents.coding_score` for OpenRouter LLMs. Samples + eval_results persist under `scripts/kilo-benchmarks/.microbench_cache/<UTC-stamp>-pid<pid>/` so a downstream sanitize/evaluate failure is $0-recoverable (the $-cost sits entirely in the shim step). Outer serial × shim inner-8 concurrent → 8 in-flight OR calls, not 64. `TOTAL_SPEND_USD: {n.nn}` on the last stdout line; typical run cost ~$1.20 per 4-model × 2-dataset unit set (HumanEval+ 164 + MBPP+ 378 = 542 problems per model).

**Initial coverage (2026-07-11):** the 4 `bytedance-seed/seed-*` coding models — `seed-1.6` and `seed-2.0-lite` tie at `coding_score = 91.96` (98.17 HumanEval+), `seed-2.0-mini` at 90.52, `seed-1.6-flash` at 87.16. Fed straight into `rank_coding_subagents.py` → `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md`.

---

## Coding microbench (direct) — contamination-free pass@1 via LiveCodeBench (2026-07-19)

`/opt/ai-model-catalog/engine/microbench_coding_direct.py` grades the **same 57 models as the review table** on ONE
fixed **LiveCodeBench** window (contamination-free by temporal filter — the fix for HumanEval+/MBPP+ saturation
+ contamination that the older `microbench_coding.py` inherits). Generation is **direct** through the vendored
ai-consult transport (`libs.subagents._transport.run`, real billed `cost_usd` via `{"usage":{"include":true}}`);
grading reuses LiveCodeBench's own sandboxed test execution (`lcb_runner.evaluation.codegen_metrics`) via a
sibling `.lcb-venv` installed **grading-only** (`--no-deps` + numpy/tqdm/datasets — no torch/vllm, since we
generate on OpenRouter, not locally). `pass@1 → grade` (same 0-5 letter scale as review) → `model_coding_metrics`
+ `model_task_baseline(code)` with a precedence guard, so **`pick_models("code")` ranks on measured ability**;
`rank_coding_subagents` surfaces the measured coding grade (`†`) + a `pass@1` column. Errored/cap-stopped calls
are `n_err` (never scored 0); `is_measured` gated at 3 graded. `--probe` sizes the real run first; `--cost-cap`
is a running-total dispatch gate. On-demand only (NOT in `daily_refresh.sh`) — the real ~$12-18 57-model run is
an operator action. Tests: `tests/test_lcb_smoke.py`, `test_microbench_coding_direct.py`, `test_coding_baselines.py`.

### Judged task-subagent benchmark — docs / research / plan / spec scoring

`/opt/ai-model-catalog/engine/microbench_judged.py` gives `pick_models()` a **measured, contamination-free
prior** for the four task types that previously had none. A task-agnostic spine (dispatch → grade →
persist → batched-resume) fed by a per-task GRADER, all on **fabrik-private / post-cutoff corpora** so a
model can't have memorized answers about our own repo:
- **research** (`research_grader.py`) — normalized EM / token-F1 (HotpotQA-vendored) on fabrik-private
  Q&A, with an injectable `claude-evaluator` near-miss tiebreak (subscription npx, $0 OpenRouter;
  abstention → F1 fallback, judge score clamped).
- **docs** (`docs_grader.py`) — **bidirectional** git-grounded recall/precision on a stale-doc→code-diff
  reconciliation, reusing `doc_reconcile` symbol plumbing (per-line tokenization; torch-free, $0).
- **plan / spec** (`structural_grader.py`) — a deterministic **structural filter** (phases,
  command-gates, resolving `path:line` citations, sections, `shape:` flags) + a **correlated cold-start
  prior** (`correlated_prior.py`: plan←code+review, spec←docs+plan; seeded free in `daily_refresh.sh`)
  + the **flywheel as the primary signal**; the PoLL LLM-judge is a documented deferred seam.

Each measured model gets BOTH a `model_task_baseline` prior AND one `subagent_runs` flywheel row per
dispatch (`quality_score=score5`) — the latter clears the ranker's `HAVING COUNT(*) >= 3` gate so a
cold model **surfaces**. Per-task **eligibility gates** (`build_task_baselines.judged_eligible`:
research/docs on score5+$/1k+p50, plan/spec on score5) filter the `### <task>` router sections and drive
the **✅ Selected subagents** headline + full leaderboards in `TASK_SUBAGENT_SELECTION.md` — mirroring
the review/code gates, fail-soft-inactive until the benchmark runs. **The paid `--task research|docs
--all` 57-model run is an OPERATOR action** (~$8–15, ~an hour; balance-guarded, per-call + running-total
cost caps, batched-resumable via `_measured_models`) — never run autonomously; a `--smoke` proves the
$0 persist+surfacing path. Tests: `tests/test_judged_harness.py`, `test_research_grader.py`,
`test_docs_grader.py`, `test_structural_grader.py`, `test_review_eligibility.py`.

---

## Fleet AI-sysadmin Claude quota-rotation (2026-07-08)

The fleet AI-sysadmin (`vps-sysadmin-bot` + `aro-wake`) survives Claude subscription **usage/quota limits** by auto-rotating between the operator's Claude accounts instead of failing silently. `scripts/sysadmin/claude_rotate.py` wraps every `claude -p` call: when the output carries a usage-limit signal (weekly / session / Opus / N-hour / "out of extra usage"), it atomically swaps the active `~/.claude/.credentials.json` to another `manager-accounts/<org>/` snapshot and retries. **N accounts** are supported (currently mob@ / ob@; can@ pending snapshot capture) — a limited call walks through each *other* account at most once, bounded so it can never loop. A `401` (dead credentials) is deliberately **not** a rotate trigger — that's an alert, since rotation can't fix expired creds. Swaps are atomic (`os.replace`) under an `flock` so the bot, aro-wake, and a manual switch can't race the active file (the target is chosen *under* the lock), the credential bytes are written `O_EXCL|O_NOFOLLOW` at mode 0600 (no world-readable window, no symlink follow) with a full-write loop, and every filesystem step fails soft (a transient error skips the rotation, never crashes the bot). There's a single rolling backup to `.credentials.json.prev`; accounts are told apart by their non-secret `organizationUuid`, and no token bytes are ever logged, printed, or committed.

**Manual account switch on WSL (no VS Code restart):** `python3 scripts/sysadmin/claude_rotate.py --list` shows the accounts (marking the active one), `--switch <name|email|prefix>` sets a chosen account active, and `--next` cycles to the next one. After a switch, just **reload the VS Code workspace** (Ctrl/Cmd+Shift+P → *Developer: Reload Window*) and the Claude Code extension picks up the new account. Empty or ambiguous names are rejected so you never silently switch to the wrong identity.

---

## AI Models Browser — Coding-subagent columns (2026-07-05)

The single-file `scripts/kilo-benchmarks/models_browser.html` now surfaces the coding-subagent ranking data alongside the existing Speed / Best Code / SWE / Aider columns:

- **`Code Fit` column** — composite score (0-1) shown on Overview / Reasoning / Coding / Translation tabs. 45% max(SWE-bench, Aider-Polyglot) + 20% AA intelligence + 15% Arena ELO + 10% output tok/s + 10% cost-inverse. Populated for the GLM / Kimi / Minimax / DeepSeek subagent pool (~38 rows); empty on all other rows.
- **`Doc↔Code` column** — letter grade (A+/A/B+/B/B-/C+/C) with a color-coded badge palette. Composite of context size + verified code-understanding + Arena/AA intelligence. Measures ability to compare documentation against implementation across a whole service. Sortable by grade rank (A+ > A > B+ > B > B- > C+ > C), not alphabetical.
- **`EXCL` / `PIN` inline badges** on the Code Fit cell — `EXCL` for reasoning-only models the ranker excludes (currently `moonshotai/kimi-k2-thinking`), `PIN` for models that need `provider.only=[…]` to avoid a broken OR sub-provider route (currently `minimax/minimax-m3` → exclude DeepInfra).
- **`Role suitability` filter chip** in the left sidebar — "coding-subagent" chip narrows the visible rows to the ranked pool. Registers in the "+N filters active" indicator alongside the other sidebar chips.
- **Detail-panel entries** on click: `Coding-subagent fit score` + `Doc↔Code` grade, `OR request body hint` (e.g. `{"reasoning":{"exclude":true},"max_tokens":30000}` for `minimax/minimax-m2.5`), `Provider pin` recipe, `⚠ Coding subagent status` (when excluded).

Data source: `/opt/ai-model-catalog/engine/rank_coding_subagents.py` (single source of truth for scoring/exclusion/pin/body-hint state; overlaid onto the browser payload by `/opt/ai-model-catalog/engine/export_models_browser.py` with the same `db_path` the chat rows come from). Full narrative + routing strategy lives in `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md`.

---


---

## fabrik-mail — durable hub↔project AI mail (2026-08-11)

A message channel between the fabrik hub and the `/opt/*` project repos (+ fabrik-lib), replacing the
operator-as-transport pattern with zero always-on infrastructure. A neutral-path file mailbox
(`/opt/fabrik-mail/<repo>/{inbox,archive}`) + `scripts/mail.py` (`send/list/read/ack/requeue/digest`) +
ONE fleet-synced surfacing hook (`.claude/hooks/mail_notify.py`, SessionStart + UserPromptSubmit). A hub
agent `send`s a message; the recipient repo's next agent session surfaces it automatically (bounded,
sanitized, delimited — messages are DATA, the receiver applies its own gates), `ack`s it, and the
operator sees unacked traffic via a daily Telegram digest. Publish is tmp-then-O_EXCL (never overwrites);
claim/ack is POSIX atomic-rename; ids are sortable hand-rolled Crockford ULIDs (no dependency). Star
topology (hub↔node); secret-refusal; 64 KB cap; malformed-quarantine. The hook is fail-open (a non-zero
UserPromptSubmit exit would block prompts fleet-wide). `/fabrik-upstream` PROJECT mode now routes its
proposals through mail. Conventions: `docs/reference/fabrik-mail.md`. Layer 2 (native cross-session
messaging ≥2.1.224) is adopted post-upgrade — deferred by fact.

**Addressing enforcement + escalation (2026-08-26, Layer 1.5):** the shared three-agent hub
mailbox refuses an unaddressed `send --to fabrik` (exit 2 + the three-beat guide) — `--to-agent
infra|fleet|intel`, explicit `--broadcast` (refuses `ack:required`: an obligation nobody owns
cannot be acked), or a `kind: reply` thread (exempt by kind; inherits the parent's owner). Typo'd
beats refused at `send` and `route`. Destination side: `scripts/sysadmin/mail_escalate.py` — a
6-hourly cron (≤1 Telegram/local-day via day-stamp) escalating `ack: required` obligations aged
≥3 days across ALL mailboxes, in three populations (inbox regardless of addressee · archive
strands · stranded resolve-windows). The dispatcher alternative (tier-0 regex + Haiku
classification, probe-measured 85.2%) was REJECTED at the operator's frame-break — enforcement
at the source beats routing at the destination (spec § Rejected alternative E).

---

## Quick Reference

| Feature | Status | Audience | Headline |
|---------|--------|----------|----------|
| [fabrik-mail](#fabrik-mail--durable-hubproject-ai-mail-2026-08-11) | ✅ Shipped | Developer | Durable hub↔project AI mail — file mailbox + surfacing hook; addressing ENFORCED at send (2026-08-26) + daily obligation escalation; replaces operator-as-transport |
| [Deployment Orchestration](#deployment-orchestration) | ✅ Shipped | Operator | `fabrik apply` — spec-driven deploy with 9 shape-gated registrars, saga rollback, state tracking |
| [Deploy Command Triad](#deploy-command-triad) | ✅ Shipped | Operator | `/fabrik-deploy-plan` → `/fabrik-deploy-plan-review` → Gate-2 `/fabrik-deploy` — plan-governed, evidence-bound deploys wrapping `fabrik apply` |
| [Deployment Verification](#deployment-verification--the-parity-contract) | ✅ Shipped | Operator | Per-project parity contract (`scripts/verify_prod_parity.py`) — `/fabrik-deploy-checklist` freezes it, `/fabrik-release` blocks on DRAFT, `/fabrik-deploy-verify` EXECUTES it as a blocking phase |
| [Preplan Handoff](#preplan-handoff) | ✅ Shipped | Developer | Capture intent before scaffold; every agent reads the same intent |
| [Project Scaffolding](#project-scaffolding) | ✅ Shipped | Developer | 12 scaffold types with `.droid/`, AI guardrails, and spec emission |
| [Documentation Enforcement](#documentation-enforcement) | ✅ Shipped | Developer | Never ship undocumented code again |
| [9-Step Workflow](#9-step-workflow) | ✅ Shipped | Developer | Systematic code quality from plan to commit |
| [AI Code Review](#ai-code-review) | ✅ Shipped | Developer | `/fabrik-review` — adversarial review gate: OpenRouter-pool finders + native Claude reviewers, converge to a no-op |
| [Development Workspace](#development-workspace) | ✅ Shipped | Developer | `.droid/` per-project workspace for review artifacts, transcripts, cost tracking, model sync |
| [Deploy State Store](#deploy-state-store) | ✅ Shipped | Operator | `.fabrik/state/` records what was deployed; feeds audit, destroy, export, verify |
| [Registrar Audit & Reconcile](#registrar-audit--reconcile) | ✅ Shipped | Operator | Spec ↔ live drift detection across the fleet |
| [Local Dev Loop](#local-dev-loop) | ✅ Shipped | Developer | `fabrik dev` / `fabrik logs --local` / `fabrik review` |
| [State-Driven Destroy](#state-driven-destroy) | ✅ Shipped | Operator | `fabrik destroy --use-state` reverses what was actually deployed |
| [Cross-VPS Portability](#cross-vps-portability) | ✅ Shipped (import untested) | Operator | `fabrik export` / `fabrik import` — bundle VPS state for rebuild |
| [i18n Kit](#i18n-kit) | ✅ Shipped | Developer | Multi-platform i18n: one JSON format, one validator, 5 platform loaders — auto-provisioned by scaffold |
| [VPS AI Sysadmin](#vps-ai-sysadmin) | ✅ Shipped | Operator | On-demand AI system administrator — Claude Code on VPS, triggered via Telegram, autonomous diagnostics and remediation |
| [VPS Audit System](#vps-audit-system) | ✅ Shipped | Operator | 7 audit prompts + 7 runner scripts for systematic VPS health checks: security, performance, containers, observability, backup |

**Status Legend:**
- ✅ **Shipped** — Production-ready
- 🚧 **Beta** — Available but may change
- 📋 **Planned** — On roadmap

---

## Deployment Orchestration

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.1

> **Headline:** `fabrik apply` takes a YAML spec with a `shape:` block and deploys it end-to-end — container (via SSH + Docker Compose), DNS, SSL, plus 9 registrars that fire automatically based on shape flags.

### What It Does

The core of Fabrik. A spec at `specs/services/<id>.yaml` declares what a service needs via its `shape:` block (needs_database, is_public, has_persistent_data, etc.). `fabrik apply` runs a state-machine orchestrator that:

1. **Validates** — spec schema, deploy readiness, compose linting
2. **Provisions secrets** — resolves from `-s` flag > project `.env` > fabrik `.env` > process env
3. **Deploys** — SSH to VPS, writes `/opt/<name>/compose.yaml` + `.env`, runs `docker compose up -d`
4. **Fires registrars** — 9 shape-gated registrars provision infrastructure automatically
5. **Verifies** — health checks, postcondition validation
6. **Rolls back** on failure — reverse-order cleanup of everything created

### The 9 Registrars

Each registrar fires only when the spec's `shape:` block activates it. `infra: <registrar>: false` overrides to disable.

| Registrar | Fires when | What it provisions |
|-----------|-----------|-------------------|
| **postgres** | `needs_database: true` | Database on postgres-main; credentials written into `/opt/<name>/.env` by the postgres registrar |
| **redis** | `needs_cache: true` | Cache index on redis-main via `assignments.json` |
| **gatus** | `is_public: true` + domain set | Health monitor endpoint on status.vps1.ocoron.com |
| **backrest** | `has_persistent_data: true` | Restic backup plan → Backblaze B2 |
| **glitchtip** | kind = service/worker/wordpress | Error tracking project + DSN |
| **grafana** | always | Dashboard annotation (decorative, not driftable) |
| **authelia** | `is_admin_dashboard: true` + domain | Forward-auth middleware rule |
| **meilisearch** | `has_search_feature: true` | Search index creation |
| **prometheus** | `exposes_metrics: true` + domain | Scrape target registration |

Order matters: postgres first (other registrars may need DB), prometheus last. Destroy reverses this order.

### How To Use

```bash
# Preview what will happen (registrar resolution, compose validation)
fabrik plan specs/services/my-api.yaml

# Deploy — orchestrator runs, registrars fire, state file written
fabrik apply specs/services/my-api.yaml

# Check post-deploy health
fabrik verify my-api.vps1.ocoron.com --spec registrars

# Redeploy (same spec, fresh container)
fabrik redeploy --spec specs/services/my-api.yaml

# Tail logs
fabrik logs my-api -f
```

### State Machine

```
PENDING → VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE
                ↓             ↓             ↓            ↓
              FAILED ← ROLLING_BACK ← ROLLING_BACK ← ROLLING_BACK → ROLLED_BACK
```

Every `fabrik apply` writes `.fabrik/state/<id>.json` — see [Deploy State Store](#deploy-state-store). Every registrar is isolated in try/except — one failure doesn't block others.

### Technical Details

- **Orchestrator:** `src/fabrik/orchestrator/` — `deployer.py` (state machine), `infrastructure.py` (registrar dispatch), `rollback.py` (reverse cleanup), `secrets.py`, `verifier.py`
- **Drivers:** `src/fabrik/drivers/` — 20+ integrations (postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus, cloudflare, dns, ssh, r2, supabase, etc.) plus archived legacy `coolify` driver for `fabrik status`/`logs` against pre-2026-05-30 services
- **Spec loader:** `src/fabrik/spec_loader.py` — YAML parsing, shape validation, template merging
- **State:** `src/fabrik/state.py` — 8-field manifest written after each successful apply

---

## Deploy Command Triad

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** 2026-08-11

> **Headline:** Every VPS deploy can now be plan-governed: `/fabrik-deploy-plan` authors a per-service
> deployment plan (surface resolution across all 12 scaffold types, spec↔code↔compose reconciliation,
> an ordered runbook with per-step verification + rollback, healing-window bracketing with stem-guarded
> autoheal-pause ownership, a verification battery, monitoring/DR truth), `/fabrik-deploy-plan-review`
> adversarially converges it to an md5-verified no-op (`Status: CONVERGED`), and the operator-dispatched
> `/fabrik-deploy` executes it step-by-step with a committed deploy ledger, halt protocol, and the
> battery as its exit gate — handing to `/fabrik-deploy-verify`.

### What It Does

- Closes the gap between `/fabrik-release`'s Gate-2 handoff and `/fabrik-deploy-verify`: the deploy
  itself becomes a reviewed, evidence-bound artifact instead of an ad-hoc `fabrik apply`.
- Gate-2 discipline preserved: `/fabrik-deploy` runs ONLY on the operator's explicit dispatch of a
  `Status: CONVERGED` plan (allowlist gate; every dispatch is a fresh run — no mid-runbook resume).
- Store surfaces (mobile/extension/desktop) get their surface's analogue of every class and stop at
  the operator's publish act.
- Seeded by the failure classes of `docs/development/reviews/2026-08-10-tryton-crm-deploy-readiness-review.md`.

### How To Use

```bash
/fabrik-deploy-plan specs/services/<id>.yaml     # author the plan (Status: DRAFT)
/fabrik-deploy-plan-review docs/development/plans/<plan>.md   # converge to CONVERGED
/fabrik-deploy docs/development/plans/<plan>.md  # operator-dispatched execution (Gate 2)
```

Sources: `commands/_sources/fabrik-deploy{,-plan,-plan-review}.md`; chained via the NEXT map in
`commands/assemble_commands.py` (`/fabrik-release` hands VPS surfaces to `/fabrik-deploy-plan`).

---

## Deployment Verification — the parity contract

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** 2026-09-02

> **Headline:** Every deploy is certified against what the product must CONTAIN, not only against liveness:
> each scaffolded project carries an executable parity contract (`scripts/verify_prod_parity.py`),
> `/fabrik-deploy-checklist` authors and FREEZES it from CODE + SPEC + DEV, `/fabrik-release` BLOCKS on a
> `DRAFT` contract, and `/fabrik-deploy-verify` EXECUTES it as a blocking phase — a service that once passed
> every check over a production database holding 0 of its 760 companies can no longer be `DEPLOY CONFIRMED`.

### What It Does

- **The contract stub is born with the project** — `templates/scaffold/scripts/verify_prod_parity.py` is
  seeded by `SCRIPT_FILES` (`src/fabrik/scaffold.py:494`) into every scaffoldable type; it carries a
  machine-readable `# Status: DRAFT | FROZEN · Version · Date` header and FAILS CLOSED: the contract
  run (`--json` / `--verdict`) exits 2 until the contract is frozen; `--header` inspects, `--self-check` refuses to
  bless a stub that carries only the precondition row. Project-owned and never synced: a project scaffolded before
  2026-09-02 receives it at its first `/fabrik-deploy-checklist` run (the command copies the template in).
- **Rows are produced by the vendored comparator** — fabrik-lib `health-probe` lives at `libs/health_probe/`
  (`VENDORED_DIRS`, `scripts/fabrik_synced_manifest.py:115`; byte-identical below a 3-line `VENDORED-FROM`
  header) and its `compare()` emits every parity row; the `_COMPARISON_KEYS` disjunction decides what a parity
  row is, so a `match: None` row fails closed instead of reading as "not checked".
- **`/fabrik-deploy-checklist`** (`commands/_sources/fabrik-deploy-checklist.md`) — one source, what the
  project ships (never a spec — specs reach it through `FEATURES.md`); derives every denominator (routes from the started
  app's `/openapi.json`, services from compose ∪ registrar sidecars, env keys from `os.getenv`, jobs from the
  live scheduler), cross-checks `FEATURES.md` both ways, SEES EVERY ROW RED against a broken DEV state, then
  freezes with its `docs/DECISIONS.md` row and refreshes the fleet-AI sections of `DEPLOYMENT.md` and
  `OPERATIONS.md` (`templates/scaffold/docs/{DEPLOYMENT,OPERATIONS}_TEMPLATE.md`).
- **`/fabrik-deploy-verify`** (`commands/_sources/fabrik-deploy-verify.md`) — an identity layer (deployed SHA
  = tested SHA, migration head, image digest), registrar rows DERIVED from `_REGISTRAR_ORDER` at run time,
  and **Phase 6 Parity (BLOCKING)**: one leg per row SITE (`hub` from the project's checkout · `container`
  via `docker exec` in the running app · `host` on the VPS), an unreachable leg kept in the denominator as
  UNVERIFIABLE, the legs merged with `--verdict --rows-from`, and the `PARITY:` / `VERDICT:` lines copied verbatim. No `FROZEN` header ⇒ `UNVERIFIED`, terminal — the signal to run
  `/fabrik-deploy-checklist`.
- **Release precondition** — `/fabrik-release`'s VPS path reads the header and stops with
  `BLOCKED: parity contract DRAFT → /fabrik-deploy-checklist` (`commands/_sources/fabrik-release.md:78-85`);
  a stale `Version` is a ⚠ WARN in the Gate-2 block.
- **Pipeline position** — `/fabrik-features` REFRESH → certification → `/fabrik-deploy-checklist` (on the
  certified build; moved after certification 2026-09-03, D-096) → `/fabrik-release` → the deploy triad → `/fabrik-deploy-verify` (`CLAUDE.md` § Orient `6-release` row + § Pipeline
  flow, mirrored in the fleet-synced `templates/governance/CLAUDE.md`).

### How To Use

```bash
/fabrik-deploy-checklist                 # in the project: author + FREEZE scripts/verify_prod_parity.py from what ships
python scripts/verify_prod_parity.py --header    # {"status": "FROZEN", "version": "v1", "date": ...} — the obligation gate
python scripts/verify_prod_parity.py --verdict   # PARITY: <agree> agree / <disagree> disagree / <unresolved> unresolved · VERDICT: <verdict> — <reasons> (exit 0 confirmed · 2 denied or DRAFT · 1 on a DOWN)
/fabrik-deploy-verify <service>          # hub-side: identity · DNS · health · derived registrars · Gatus · logs · Phase 6 parity
```

### Technical Details

- Exit precedence in the stub: a liveness `DOWN` → 1, any comparison row not `match: True` → 2, a non-`FROZEN`
  header → 2, else 0 (`templates/scaffold/scripts/verify_prod_parity.py:209-216`); the algebra is EXECUTED by
  `tests/test_deploy_verify_verdict.py` (9 tests on rows from the real `compare()`, the retired
  `expected AND actual` rule seen giving the false all-clear beside them).
- Scaffold contract: `tests/test_scaffold_deploy_contract.py` (31 tests — every type seeds the stub, vendoring
  byte-identity, the `{PROJECT_NAME}` doc sentinel, `wordpress` refused).
- Reference: `docs/reference/deployment-verification.md`; design `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md`
  (D-077); plan `docs/development/plans/archived/2026-09-01-plan-1-deployment-verification.md` (D-082, built as D-086).
- Deliberately deferred: no executable check grades the `FROZEN` header yet (`docs/STRATEGIC_BACKLOG.md`, owner infra).

---

## Preplan Handoff

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.2 (T3-01)

> **Headline:** Capture project intent BEFORE scaffold — every agent reads the same intent without re-deriving it.

### What It Does

The Fabrik lifecycle begins with **intent capture**. Before `fabrik scaffold` creates any files, run `fabrik preplan new <slug>` to author `docs/preplans/<YYYY-MM-DD>-<slug>.md` from a 9-section template (Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes-VPS1-inventory-reminders). Refine the markdown with Opus / Claude / ChatGPT until the intent is hardened. Then `fabrik scaffold <name> --from-preplan <path>` ingests it:

1. Pre-fills `--type` from the preplan's "Project type" section
2. Pre-fills the spec's `shape:` block from the preplan's "Shape preview" yaml
3. Adopts the preplan's "Idea" first line as the project description
4. Copies the preplan to `<project>/docs/preplan.md`
5. **Appends a `Preplan:` reference line to all 4 AI guardrail files** — `AGENTS.md` (Traycer), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo), `.windsurfrules` (Windsurf) — so every downstream agent that opens the project reads the same intent

### How To Use

```bash
fabrik preplan new citation-verifier
# Edit docs/preplans/<today>-citation-verifier.md — fill in the 9 sections
fabrik scaffold citation-verifier --from-preplan docs/preplans/<today>-citation-verifier.md
```

Traycer's `docs/traycer/fabrik-workflow.md` Step 2.5 is the planning-side companion: when Traycer detects a fresh project (no scaffold yet), it looks for a matching preplan in `docs/preplans/` BEFORE asking the operator to declare anything from scratch.

### Why This Matters

Without intent capture, every downstream agent (Claude Code writing code, Kilo reviewing, Windsurf editing, Traycer planning) has to **re-derive** what the project does from incomplete context. That re-derivation is where "wait, what was this project supposed to do?" drift comes from. The preplan is the single source of truth; the 4-guardrail injection makes sure every agent reads it.

The template's `## 9. Notes` section also embeds the VPS1-inventory reminders (postgres-main:5432, redis-main:6379, X-Internal-Token pattern, `*.vps1/health` Authelia bypass, /metrics scrape target, GlitchTip DSN convention) — so agents reading the preplan stay grounded in the same VPS1 reality the scaffold-emitted guardrails enforce.

---

## Project Scaffolding

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Create production-ready projects in seconds with built-in best practices

### What It Does

Fabrik scaffold generates a complete project structure with pre-configured tooling, documentation templates, and inherited quality rules. Every scaffolded project starts with the same conventions, reducing onboarding time and ensuring consistency.

### How To Use

```bash
fabrik scaffold my-project --type python-api
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Stop configuring, start building. Fabrik scaffolds production-ready projects with documentation, testing, and deployment ready to go." |
| **Email Subject** | "New project? Fabrik gets you to 'Hello World' in 30 seconds" |
| **Social Media** | "🏗️ fabrik scaffold my-app → Full project with docs, tests, CI/CD in seconds #DevTools" |
| **Sales One-liner** | "Fabrik scaffold eliminates boilerplate so teams ship features, not config." |

### Technical Details

<details>
<summary>Click to expand</summary>

**CLI Command:** `fabrik scaffold <name> [--type TYPE] [--github-create]`

**Generated Structure:**
- `src/` — Source code with `__init__.py`
- `tests/` — Test directory with sample test
- `docs/` — Documentation with FEATURES.md, INDEX.md
- `.env.example` — Environment template
- `AGENTS.md` — file copy of `/opt/fabrik/AGENTS.md` (Traycer)
- `AGENTS-compact.md` — file copy of `/opt/fabrik/AGENTS-compact.md` (Kilo CLI)
- `CLAUDE.md` — file copy of `/opt/fabrik/templates/governance/CLAUDE.md` (Claude Code; the hub's own `CLAUDE.md` is the hub contract, never seeded) — *added T1-02 G-B5*
- `.windsurfrules` — file copy of `/opt/fabrik/.windsurfrules` (compact synced contract file; consumed by non-Claude tooling — Windsurf Cascade itself is retired)
- `.windsurf/rules/` — file copy of `/opt/fabrik/.windsurf/rules/`

**Optional flags:**

- `--github-create` (T1-02 G-B2): also creates a private GitHub repo at `mobasak/<name>` via `gh repo create … --yes`. Best-effort — missing `gh` binary or unauthenticated state log a warning and continue.

**Output trailer:** Every successful scaffold ends with a `# Next: cd /opt/<name>; open Traycer …` hint pointing at the Traycer-managed workflow (T1-02 G-B4).

**Project Types:** `python-api`, `python-api-gpu`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`

</details>

---

## Documentation Enforcement

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Never ship undocumented code again

### What It Does

Automated checks ensure documentation stays in sync with code. When you add a feature, change a schema, or create an API endpoint, Fabrik reminds you to update the relevant docs.

### Enforcement Scripts

| Script | Trigger | Severity |
|--------|---------|----------|
| `check_changelog.py` | Code changes ≥10 lines | ERROR |
| `check_schema_sync.py` | DB model changes | ERROR |
| `check_readme_md.py` | Missing required sections | ERROR |
| `check_openapi_sync.py` | New API routes | WARNING |
| `check_test_coverage.py` | New public functions | WARNING |
| `check_env_example.py` | New env vars in code | WARNING |
| `check_compose_services.py` | New Docker services | WARNING |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Documentation that updates itself. Fabrik catches missing docs before they reach production." |
| **Email Subject** | "Your code review just got smarter: auto-doc enforcement" |
| **Social Media** | "📝 Fabrik now enforces schema.sql sync, API docs, and test coverage automatically #DevOps" |
| **Sales One-liner** | "Fabrik's enforcement scripts catch documentation drift at commit time." |

---

## 9-Step Workflow

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Systematic code quality from plan to commit

### What It Does

A structured workflow that ensures every code change goes through planning, implementation, review, and verification before commit. Token-optimized to run deterministic checks before expensive AI review.

### The Flow

```
PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → REVIEW → FINAL_GATE → VERIFY → SYNC → COMMIT
```

| Step | Action |
|------|--------|
| 1 | Traycer Plan (spec, edge cases, env vars) |
| 2 | Coder Implements |
| 2.5 | Self-Review (MANDATORY) |
| 3 | Final Gate (pre-review) |
| 4 | `/fabrik-review` Loop |
| 5 | Final Gate (post-review) |
| 6 | Traycer Verification |
| 7 | Sync Only |
| 8 | Commit |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "From idea to commit in 9 verified steps. No shortcuts, no surprises." |
| **Email Subject** | "The workflow that catches bugs before your users do" |
| **Social Media** | "🔄 9-step workflow: Plan → Code → Review → Gate → Ship. Every time. #QualityFirst" |
| **Sales One-liner** | "Fabrik's 9-step workflow embeds quality gates into every commit." |

---

## AI Code Review

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** `/fabrik-review` — adversarial code review: parallel OpenRouter-pool finders (recall) plus native Claude reviewers (authority) iterate to a fixed point.

### What It Does

`/fabrik-review` is the review gate (Kilo CLI, retired 2026-07-19, is no longer in this loop). Independent finders dispatched via the OpenRouter subagents pool (`libs.subagents.select.pick_models("review")` through `fanout()`) scan the diff in parallel for defects; native Claude reviewers cover the high-risk slices (auth, schema, migrations, concurrency); a refute/merge pass separates real defects from false positives, then fixes are applied with regression guards. The loop repeats until a fresh pass finds nothing and changes nothing.

### How To Use

```bash
/fabrik-review
```

### Technical Details

- Pool dispatch: `libs/subagents/agent.py::fanout("review", units, repo=..., mode="read_only")`
- Every pool dispatch records a `subagent_runs` flywheel row (`record_agent_run`) — never `record_run`, which silently no-ops on a raw result
- Rubric injection (mandatory-core floor + glob-matched packs) is layered in via `scripts/review_rubric.py`

---

## Development Workspace

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Every scaffolded project gets a `.droid/` directory — the runtime workspace for review artifacts, Traycer dispatch reports, multi-model consultations, and development cost tracking.

### What It Does

`.droid/` is created by `fabrik scaffold` (part of `SHARED_DIRS` in `scaffold.py`) for all 12 scaffold types. `fabrik fix` also creates/updates it on existing projects. Only `review-context/` and `traycer-reports/` are git-tracked; everything else is gitignored runtime state — `/fabrik-review` bundles, Traycer dispatch reports, per-session transcripts, multi-model consultation JSON, the doc-generation queue/log, and a SQLite dev-tracker (`dev_tracker.db`) recording gate results, review costs, and workflow events.

### How To Use

```bash
# Cost report across dev sessions
python scripts/kilo_cost_report.py

# Query the dev tracker
python scripts/dev_tracker.py report summary
```

---

## Deploy State Store

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-01)

> **Headline:** `.fabrik/state/<id>.json` records exactly what `fabrik apply` deployed — which registrars fired, which UUIDs were created, at what git SHA. Every downstream command (destroy, audit, export, verify) reads from this state.

### What It Does

Every successful `fabrik apply` writes an 8-field JSON manifest to `.fabrik/state/<id>.json`. This is the backbone of the deploy/destroy/audit pipeline:

```json
{
  "applied_at": "2026-05-16T14:03:04Z",
  "coolify_app_name": "my-api",
  "coolify_uuid": "lgg84cs8gkso0swk8g4cwo80",
  "domain": "my-api.vps1.ocoron.com",
  "git_sha": "ce9d1ed...",
  "registrars_applied": [
    {"type": "gatus", "id": "my-api", "status": "created", "data_bearing": false},
    {"type": "prometheus", "id": "my-api", "status": "created", "data_bearing": false}
  ],
  "spec_hash": "72f31d75097f4672",
  "spec_path": "/opt/fabrik/specs/services/my-api.yaml"
}
```

### Who Reads It

| Command | How it uses state |
|---------|------------------|
| `fabrik apply` | Writes state after successful deploy |
| `fabrik destroy --use-state` | Reads state to replay exact teardown (see [State-Driven Destroy](#state-driven-destroy)) |
| `fabrik audit-registrars` | Reads all state files for fleet-wide drift detection (see [Registrar Audit](#registrar-audit--reconcile)) |
| `fabrik verify --spec registrars` | Reads state for postcondition gate |
| `fabrik export` | Bundles state files into portability tarball (UUIDs stripped) |
| `fabrik review` | Writes `.fabrik/review/<ts>.md` — diff + spec + registrars bundled for review |

### Directory Structure

```
.fabrik/
├── state/
│   ├── <id>.json                  # Active deploy state (one per applied spec)
│   └── _destroyed/
│       └── <id>.json.<UTC-ts>     # Archived state from destroyed services
└── review/
    └── <YYYY-MM-DD-HHMMSS>.md     # Review bundles from `fabrik review` (gitignored)
```

Also related (outside `.fabrik/`): `data/projects.yaml` holds the project registry. Site provisioning (domain → DNS → initial deploy) is not saga state inside this repo — it's the standalone site-provisioner microservice (`provision.vps1.ocoron.com`); see `docs/reference/service-contracts/site-provisioner.md`.

### Data-Bearing Protection

Registrars that create persistent data (postgres, redis, meilisearch) are marked `data_bearing: true` in the state file. `fabrik destroy --use-state` refuses to tear these down without `--drop-data` — preventing accidental data loss when spec has drifted.

### Technical Details

- **Writer:** `src/fabrik/state.py` — `save()` writes atomically after each `fabrik apply`
- **Lock:** `src/fabrik/locks_local.py` — file-based lock prevents concurrent applies to the same spec
- **Archive:** `state.archive_destroyed()` moves to `_destroyed/` on successful destroy
- **Portability:** `src/fabrik/portability.py` — strips `coolify_uuid` from state files for export

---

## Registrar Audit & Reconcile

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-02)

> **Headline:** Spec ↔ live drift detection across the fleet, surgical destroy, fleet-wide reconcile

### What It Does

Every `fabrik apply` writes a per-spec state file (T2-01) capturing which registrars fired. T2-02 layers four operator commands on top of that foundation:

- **`fabrik audit-registrars`** — Compares each spec's shape-resolved registrars (what SHOULD be live) to the VPS's actual state (postgres `\l`, gatus `apps/<id>.yaml`, authelia config rules, backrest `config.json` plans, glitchtip project API, meilisearch index, prometheus scrape jobs, redis `assignments.json`). Outputs a pivot table or JSON. Exit 2 if any `missing`.
- **`fabrik reconcile-all`** — Walks every deployed spec, holds a per-spec file lock (T2-01 `locks_local.file_lock`), re-runs `DeploymentOrchestrator.refresh_infrastructure` per spec. Dry-run by default; `--yes` to apply. `--filter <substr>` to scope.
- **`fabrik verify <domain> --spec registrars`** — Single-domain postcondition check using the YAML-driven `PostconditionChecker`. Fails on any `missing` registrar.
- **`fabrik destroy --partial <reg>`** — Surgical un-registration without touching DNS, the running compose stack, or local files. Repeatable: `--partial gatus --partial backrest`. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py` (also consumed by T4-02).

### How To Use

```bash
# Audit the whole fleet
fabrik audit-registrars

# JSON for automation (alerts, dashboards)
fabrik audit-registrars --spec specs/services/translator.yaml --json | jq .

# Re-run registrars across the fleet (dry-run)
fabrik reconcile-all --filter translator

# Single-domain registrar coverage check
fabrik verify translator.vps1.ocoron.com --spec registrars

# Surgical removal of one or more registrars
fabrik destroy specs/services/translator.yaml --partial gatus --dry-run
fabrik destroy specs/services/translator.yaml --partial gatus --partial backrest -y
```

### Status Glyphs

| Glyph | Status  | Meaning                                                          |
|-------|---------|------------------------------------------------------------------|
| `✓`   | present | Shape says yes, live state agrees                                |
| `✗`   | missing | Shape says yes, live state says no                               |
| `·`   | n/a     | Shape says skip (includes `infra:` override case, reason in detail) |
| `?`   | unknown | Probe failed (e.g. SSH error, missing token, container not found)   |

A `drift` status (live exists but in a different shape than expected) is
not yet produced by any auditor — they currently check presence only.
Follow-up auditors will compare config bags.

### Excluded by design

`grafana` is intentionally excluded from destroy handlers and reports `n/a` for audit. Grafana annotations are point-in-time decorative markers, not driftable lifecycle state.

---

## Local Dev Loop

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.3 (T3-03)

> **Headline:** Code, watch, and bundle for review without leaving WSL. Three CLI commands close the inner-loop gap between scaffold and `fabrik apply`.

### What It Does

Stage 2 of the Fabrik lifecycle (Agentic Implementation) is where the developer iterates on code against the spec contract. T3-03 ships three commands that keep that loop tight without round-tripping to the VPS:

- **`fabrik dev`** — runs the project's `compose.dev.yaml` stack locally via `docker compose up`. Hot-reload + bind mounts, no VPS involvement.
- **`fabrik logs --local`** — tails `docker compose -f compose.dev.yaml logs` (sibling of the Loki-backed `fabrik logs <service>` for remote queries).
- **`fabrik review`** — bundles `git diff` + `specs/services/<id>.yaml` + `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md`. Hand the bundle to a human reviewer or dispatch it to the `/fabrik-review` pool.

### How To Use

```bash
cd /opt/<project>

# 1. Spin up the local dev stack (compose.dev.yaml from the scaffold)
fabrik dev -d

# 2. Tail logs in another terminal
fabrik logs --local -f
fabrik logs --local --service api -f   # one service only

# 3. When the diff looks good, bundle for review
fabrik review                          # uses HEAD by default
fabrik review --since HEAD~3           # last 3 commits
fabrik review --out /tmp/review.md     # custom output path

# 4. Dispatch (out-of-band) — pool review finders
python -c "
from libs.subagents import fanout
results, table = fanout('review', ['.fabrik/review/<ts>.md'], repo='/opt/fabrik')
print(table)
"
```

### Why This Matters

Pre-T3-03 the only feedback channel was `fabrik apply` → VPS deploy → Loki tail. That's a multi-minute loop for every iteration. `fabrik dev` keeps the loop in-WSL (sub-second), and `fabrik review` puts the spec contract + resolved-registrar surface in front of every reviewer so they catch shape contradictions before the deploy phase (consistent with the agent-rule snippet T3-02 propagated everywhere: "don't ship code that contradicts the spec").

### Technical Details

- **Scope of `--local`**: only `fabrik logs --local` branches to docker. The remote `fabrik logs <service>` path (Loki) is unchanged — `--local` is opt-in.
- **`.fabrik/review/` is gitignored**: bundles are local artefacts. The PR diff already captures the change set; the bundle is a reviewer prompt, not a tracked file.
- **Spec auto-detection**: `fabrik review` finds the first `specs/services/*.yaml` under cwd. Override with `--spec <path>`.
- **No spec required**: works on projects without a spec (the resolved-registrar section is omitted).
- **Helpers extracted** to [`src/fabrik/dev_tools.py`](../src/fabrik/dev_tools.py) so tests can exercise `build_review_bundle` / `run_dev_compose` / `run_local_logs` without invoking docker.

---

## State-Driven Destroy

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.3 (T4-02)

> **Headline:** `fabrik destroy --use-state` reverses what was actually applied, not what the spec says now. The spec is allowed to drift; the teardown isn't.

### What It Does

The default `fabrik destroy <spec>` walks the spec's current `shape:` block and runs only the destroyers the current shape declares applicable. That breaks when the spec drifted between apply and destroy:

```bash
# Day 1 — apply with search
echo "shape: { has_search_feature: true }" >> spec.yaml
fabrik apply spec.yaml         # meilisearch index created

# Day 7 — search no longer needed
sed -i 's/has_search_feature: true/has_search_feature: false/' spec.yaml

# Day 30 — destroy
fabrik destroy spec.yaml       # ❌ shape says no search → meilisearch destroyer SKIPPED → orphan index
fabrik destroy spec.yaml --use-state --drop-data -y   # ✅ replays Day-1 state, reaps the index
```

### How To Use

```bash
# Dry-run to see what state-driven destroy would tear down
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --dry-run

# Safe path (no data-bearing registrars in state, or operator OK with refusal)
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state -y

# State has postgres / redis / meilisearch → must explicitly drop data
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --drop-data -y
```

### Why This Matters

Two invariants the vision insists on (Stage 3 — Proper Registration) are now load-bearing on teardown too:

1. **Zero leaks.** Every registrar that `fabrik apply` ran ends up in the state file; `--use-state` guarantees every one of them runs its destroyer. No orphan auth rules, no orphan meilisearch indexes, no ghost gatus monitors.
2. **No silent data destruction.** State files mark `postgres / redis / meilisearch` entries with `data_bearing: true` (per [`state.DATA_BEARING_REGISTRARS`](../src/fabrik/state.py#L69)). `--use-state` refuses with an explicit error if any are present and `--drop-data` isn't set:

   ```text
   ❌ data-bearing-guard refused — state has data-bearing registrars (meilisearch, postgres);
      re-run with --drop-data to confirm destruction
   ```

   Operators have to type the data-destruction intent every single time.

### Technical Details

- **Phase 0** — data-bearing guard. Scans state's `registrars_applied` for `data_bearing: true` entries; refuses pre-flight if `--drop-data` not set.
- **Phase 1** — canonical reverse-order registrar teardown using `reversed(_REGISTRAR_ORDER)`: `prometheus → meilisearch → authelia → grafana → glitchtip → backrest → gatus → redis → postgres`. Order is enforced because postgres-last avoids FK violations against authelia session rows. Grafana is intentionally skipped (annotations are decorative). Dispatch uses T2-02's module-level `HANDLER_FUNCS` + `HANDLER_ARGS` maps.
- **Phase 2** — Compose stack teardown on the VPS (always: `docker compose down -v` + `rm -rf /opt/<name>`), DNS (gated by `--keep-dns` + spec domain), local files (gated by `--keep-files`).
- **On success** — `state.archive_destroyed(spec.id)` moves `<id>.json` → `_destroyed/<id>.json.<UTC-ts>`. State file is the deploy-state record; the archive preserves the audit trail without leaving the file in place to confuse future audits.
- **Mutually exclusive with `--partial`** — both flags exist for distinct surgical purposes (per-registrar vs. per-state-file). The combination errors out (exit 2).
- **Handler exception → bounded error.** A single failing destroyer doesn't abort the rest of the teardown; the failure goes into the report as an `error` ActionResult and `--use-state` exits 2 so CI can catch it.

### Acceptance Reference

Epic Brief Success Criterion 3. Live verification: `pytest tests/test_destroy_use_state.py -v` (16/16 pass), including the primary-path `TestPrimaryPathSpecDrift::test_a_resources_destroyed_even_after_shape_b`.

---

## Cross-VPS Portability

**Status:** ✅ Shipped (export verified; import path untested in this epic) | **Audience:** Operator | **Since:** v0.3 (T4-03)

> **Headline:** `fabrik export` produces a portable tarball that captures every resource `fabrik apply` registers on this VPS. `fabrik import` provides the rebuild scaffold on a fresh target. Zero secrets, zero UUIDs.

### What It Does

If vps1 dies — or you want to spin up vps2 as a base for a second customer / staging environment — the portability bundle lets you carry the registration story across machines without re-running every `fabrik apply` ticket by hand:

```bash
# On vps1 — produce the bundle
fabrik export --out /tmp/vps1-base.tar.gz

# Transfer to the new VPS (operator's choice: scp, rsync, etc.)
scp /tmp/vps1-base.tar.gz vps2:/tmp/

# On vps2 — see what would be restored (dry-run, default)
fabrik import /tmp/vps1-base.tar.gz

# Re-populate .env secrets per the bundle's secrets-redacted.json checklist
# (the ~0.5-day manual cost pack §28 'Secrets ergonomics' calls out)
nano /opt/fabrik/.env

# Execute the restore (stubbed in this epic; live roundtrip lands in vps2 stand-up)
fabrik import /tmp/vps1-base.tar.gz --apply
```

### What's Inside the Bundle

```text
fabrik-export-vps1-YYYY-MM-DD.tar.gz
├── manifest.json                  # version + section counts + untested_paths
├── README.md                      # restore steps + prerequisites
├── secrets-redacted.json          # .env KEY NAMES (never values)
├── specs/services/*.yaml          # every service spec
├── state/*.json                   # T2-01 state files, coolify_uuid stripped
├── coolify/{applications,services,projects}.json    # UUIDs recursively stripped
├── monitoring/{prometheus,alertmanager,redis-assignments,postgres-allocations}*
├── monitoring/grafana-dashboards/  # repo-local mirrors
├── authelia/configuration.yml      # SSH-pulled (best-effort)
└── backrest/config.json            # SSH-pulled (best-effort)
```

### Security Invariants (test-enforced)

1. **No plaintext secret values.** `_redact_env_keys` reads only up to the first `=` of each `.env` line. The test byte-scans the entire gzip stream for known values and asserts zero hits.
2. **No Coolify UUIDs.** `_strip_uuids` recurses both keys (14 known UUID-named fields including `private_key_uuid`, `server_uuid`, `deployment_uuid`) and bare 24-alphanum string values. The test scans 5 distinct UUID markers across all bundle entries.
3. **No Coolify private-key UUIDs** (a special case of the above) — guarantees the target can't accidentally inherit the source's git deploy-key references.

### Why Import Is Shipped Untested

The real roundtrip needs a fresh Ubuntu VM with bootstrapped Coolify + postgres-main + redis-main. Pack §28 explicitly defers this to the vps2 stand-up. Until then:

- The `import` pipeline parses the bundle, validates the manifest, and emits a restore plan.
- The `--apply` flag runs but ends at a documented stub (`phase: real_run / status: stub`).
- The bundle README enumerates manual follow-ups not automated by import: LetsEncrypt cert transfer, DNS provider re-binding, OAuth provider re-creation, postgres/meilisearch data restore (only if `--include-data` was used at export).

### Acceptance Reference

Pack v3.2 §EPIC SCOPE Tier 4 G-J2 (effort revised v2: +0.5 day for secrets ergonomics). Live verification: `pytest tests/test_portability.py -v` (23/23 pass). Sample run on `/opt/fabrik` produced a 44 KB tarball with 26 Coolify applications, 348 redacted secret keys, and zero UUID leaks.

---

## i18n Kit

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.4

> **Headline:** One JSON format, one validator, 5 platform loaders — auto-provisioned by `fabrik scaffold` for every GUI project type it covers (chrome-extension uses its own native i18n instead — see Platform Coverage).

### What It Does

Every GUI scaffold type ships with internationalization out of the box. `fabrik scaffold my-app --type saas-skeleton` places the right i18n loader, starter JSON, validation script, and reference docs into the project. Coding agents find these files on day one and use them — no manual setup, no third-party library installation.

### Platform Coverage

| Scaffold type | Strategy | What gets placed |
|---------------|----------|-----------------|
| **saas-skeleton** | React context | `lib/i18n/I18nProvider.tsx` + `server.ts` + `LanguageSwitcher.tsx`, `public/i18n/en.json` |
| **static-site** | Vanilla DOM | `static/js/i18n.js`, `static/i18n/en.json`, HTML snippets |
| **desktop-app** | Vanilla DOM | Same as static-site (Electron is Chromium) |
| **mobile-app** | RN adapter | `scripts/sync_rn_locales.py` (syncs to `src/locales/` for i18next) |
| **docusaurus** | Docusaurus adapter | `scripts/sync_docusaurus.py` (syncs custom strings to `i18n/<lang>/code.json`) |

**chrome-extension is not i18n-kit-provisioned.** Its i18n is owned natively by `@wxt-dev/i18n` (`src/locales/*.json` → build-time `_locales/`) — no `chrome_messages.py`/`i18n.js` provisioning (`I18N_ENABLED_TYPES` in `scaffold.py`, lines 186-193).

All types also receive: `scripts/validate_i18n.py` (3-level validator), `en.json` + example translations, `docs/reference/multilingual-plan.md` (1170-line architecture bible).

### Shared JSON Format

```json
{
  "_meta": { "language": "en", "nativeName": "English", "completeness": 1.0 },
  "nav": { "home": "Home", "settings": "Settings" },
  "common": { "save": "Save", "cancel": "Cancel" },
  "error": { "not_found": "Page not found" }
}
```

Nested dot-path keys (`nav.home`), `{variable}` interpolation, `_meta` block for completeness tracking. Same format consumed by all 5 i18n-kit loaders.

### Translation Workflow

```
1. Developer writes English UI using t('key') or data-i18n="key"
2. en.json is the source of truth — all keys present
3. AI translates en.json → tr.json (Claude/GPT first pass)
4. python scripts/validate_i18n.py --validate tr
   ├── Level 1: Structural (keys match, placeholders preserved) — free, instant
   ├── Level 2: Back-translation (semantic drift detection)
   └── Level 3: Native-speaker critique (tone/grammar + auto-fix)
5. Ship.
```

### Validation

Levels 2/3 route through the OpenRouter subagents pool rather than the retired Kilo CLI. Per-language model choice is driven by the translation-ranked leaderboard (`docs/reference/kilo/TRANSLATION_SELECTION.md`, seeded from `/opt/ai-model-catalog/engine/rank_translation.py` against `agents WHERE service_type='translation'`) rather than a hardcoded per-language table.

### Rule Pack Integration

- **60-saas-ui.md**: "Use scaffolded `lib/i18n/` — do not install next-intl or react-i18next"
- **70-chrome-ext.md**: use `@wxt-dev/i18n`'s `t()` — not the fabrik i18n-kit loader
- **80-mobile.md**: "Source-of-truth at `static/i18n/`, sync via `scripts/sync_rn_locales.py`"

These rules ensure coding agents use the scaffolded i18n system rather than installing their own.

### Technical Details

- **Source:** `templates/i18n-kit/` in the fabrik repo (20 files, ~1750 LoC)
- **Provisioner:** `_provision_i18n()` in `scaffold.py`, called from `create_project()` after type-specific scaffolder runs
- **Types map:** `I18N_ENABLED_TYPES` in `scaffold.py` — maps scaffold type → strategy (`react`, `vanilla` ×2, `rn`, `docusaurus`); chrome-extension is deliberately absent (owned by `@wxt-dev/i18n`)
- **Battle-tested:** Originally built for the Tojlo project (738 keys, 6 languages, 24 pages), generalized for all fabrik GUI types

---

## VPS AI Sysadmin

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.5 (2026-05-20)

> **Headline:** On-demand AI system administrator — Claude Code Opus running locally on VPS. Talks via Telegram. Queries 15 infrastructure APIs directly. Acts autonomously on safe operations. Proactive health checks every 15 min. Morning briefings. Weekly security patrols. Monthly backup verification. Shift notes for memory between sessions. Incident playbooks. Service criticality tiers. 1136 lines of code, zero cost when idle.

### Three Trigger Paths

1. **You message Telegram** → bot spawns Claude Opus → Claude runs commands locally (docker, curl, audit scripts) → responds → session lives until "done" or 10min silence → shift notes written
2. **Alert fires** → Alertmanager → Apprise → Telegram (existing flow) → you reply to investigate → Claude wakes with full context
3. **Proactive cron** (every 15min) → bash checks 11 Prometheus thresholds + TLS cert expiry + disk prediction (zero tokens) → only if anomaly detected → Claude wakes, diagnoses, acts autonomously, reports to Telegram

### Five Scheduled Routines

| Routine | Schedule | Uses Claude? | What it does |
|---|---|---|---|
| Proactive check | Every 15 min | Only on anomaly | 10+ PromQL thresholds + cert expiry + disk prediction. Bash prefilter = zero cost when healthy. Claude acts + reports when something is wrong. |
| Morning report | Daily 08:00 | Always | Collects: containers, disk, RAM, certs, alerts, shift notes, yesterday's actions. Claude formats concise Telegram briefing with trends. |
| Security patrol | Monday 08:30 | Always | Runs `03-security.sh`, Claude analyzes against `03-security-hardening.md` checklist. Reports GREEN/YELLOW/RED with findings. |
| Maintenance | Sunday 03:00 | Never | Pure bash: checks dangling images/volumes, journal size, backup freshness, restart counts, stale containers, cert expiry. |
| Backup verification | 1st of month 04:00 | Always | Runs `06-backup.sh`, Claude analyzes against `06-backup-disaster-recovery.md` checklist. Reports coverage gaps + recovery confidence. |

### Infrastructure APIs (15 services, queried locally)

| Service | What the sysadmin gets |
|---|---|
| Prometheus (`:9090`) | Container + host metrics, 13 alert rules, scrape target health |
| Loki (`:3100`) | All container logs — errors, stack traces, crash messages |
| Grafana (`:3000`) | Dashboard + datasource health (8 dashboards, 2 datasources) |
| Alertmanager (`:9093`) | Active firing alerts, silences |
| Gatus (`:8080`) | Uptime status for 30+ endpoints |
| GlitchTip (`:8000`) | Application errors, unhandled exceptions |
| cAdvisor (`:8080`) | Real-time per-container metrics (replaced Netdata, removed 2026-05-30) |
| Apprise (`:8000`) | Send notifications to Telegram |
| Pushgateway (`:9091`) | Drift audit metrics |
| Meilisearch (`:7700`) | Search index health |
| Docker CLI | Container lifecycle — ps, stats, logs, restart, update, inspect |
| Node exporter (via Prometheus) | Host CPU, RAM, disk, network |
| cAdvisor (via Prometheus) | Per-container resource metrics |
| Postgres exporter (via Prometheus) | Database connections, query rates |
| Redis exporter (via Prometheus) | Cache memory, hit rate |

### Safety Model

- **Autonomous:** restart application/platform containers, scale memory up (check host capacity first), all read operations, write shift notes
- **Ask first:** scale down, stop containers, anything destructive-adjacent, anything unsure about
- **Never:** delete anything, touch networking/firewall/boot config, modify critical-infra or monitoring, modify env vars

### Veteran Sysadmin Features

| Feature | How |
|---|---|
| **Incident playbooks** | 6 documented procedures in system prompt: OOM, restart loop, disk full, host memory, target down, cert expiry |
| **Service criticality tiers** | P0 (revenue: ocoron.com) → P1 (platform: traefik, postgres) → P2 (operations) → P3 (monitoring) → P4 (utility). Triage by tier when multiple issues. |
| **Shift notes** | `logs/sysadmin-shift-notes.md` — Claude reads at session start, writes at session end. Remembers context between conversations. |
| **Action log** | `logs/sysadmin-actions.jsonl` — every conversation logged with timestamp, session ID, message, response. Persistent audit trail. |
| **Audit prompt integration** | Weekly security + monthly backup routines reference the matching audit-prompt checklist. Claude doesn't improvise — it checks against documented criteria. |

### Components (1136 lines total)

| File | Lines | Purpose |
|---|---|---|
| `scripts/sysadmin/bot.py` | 332 | Telegram bot — spawns Claude Opus per message, JSON output parsing, session management, action logging, health endpoint `:8017`, daily heartbeat |
| `scripts/sysadmin/system-prompt.txt` | 232 | Sysadmin brain — role, 15 APIs, container classification, 6 incident playbooks, P0-P4 criticality, shift notes protocol, communication protocol, safety rules |
| `scripts/sysadmin/proactive-check.sh` | 202 | Two-stage cron — 11 checks (10 PromQL + Prometheus connectivity) + cert expiry. Bash prefilter (zero tokens). Claude acts on anomaly. Rate-limited 5/hr. |
| `scripts/sysadmin/morning-report.sh` | 124 | Daily briefing — containers, disk, RAM, certs, alerts, shift notes, yesterday's actions. Claude formats Telegram-friendly summary. |
| `scripts/sysadmin/weekly-maintenance.sh` | 115 | Sunday cleanup report — dangling resources, journal, backup freshness, restart counts, stale containers, cert expiry. Pure bash, no Claude. |
| `scripts/sysadmin/monthly-backup-verify.sh` | 70 | Backup audit vs DR checklist — coverage, freshness, retention, recovery confidence. |
| `scripts/sysadmin/weekly-security.sh` | 61 | Security audit vs hardening checklist — GREEN/YELLOW/RED with findings. |
| `ops/vps-sysadmin-bot.service` | 20 | Systemd unit — auto-start, `Restart=always`, `After=network.target docker.service` |

### Technical Details

- **Model:** Claude Opus (`--model opus`) — best reasoning for infrastructure diagnosis
- **Bot:** systemd service on VPS, `Restart=always`, health endpoint at `:8017/health`
- **Session:** `claude -p` per message, `--resume` for follow-ups, cleared on "done" / 10min timeout
- **System prompt:** injected via `--system-prompt` (NOT CLAUDE.md — that's for WSL development)
- **Auth:** Max subscription via `claude auth login` — no API key stored on VPS
- **Token economics:** $0 on quiet days (bash prefilter handles 95%), $5-15/month typical (included in Max)
- **Knowledge sync:** `scripts/sync-vps-sysadmin.sh` pushes docs, audit scripts, specs from WSL to VPS after any change

### Self-Observability — SLI metrics (since 2026-06-06)

`aro-wake` (the push-trigger entry point introduced in trio plan Phase 3) exposes 8 Prometheus metrics at `:8201/metrics` on every fleet host (vps1 hub + vps2/vps3 spokes), mapping to the `agent-sre` SLI framing from `docs/reference/research/AI for Autonomous System Administration.md`. Two alert rules ship pre-configured, evaluated per-host: `AroWakeLowSuccessRate` (warning at <90% success over 10m) and `AroWakeCostBurnHigh` (warning at >$5/h sustained — catches runaway-reasoning loops early). Prometheus scrapes the hub via docker bridge and the spokes via the wg0 mesh (cross-mesh container→host NAT verified live). See `CHANGELOG.md` 2026-06-06 entry for full metric list.

### Full Reference

- `docs/infrastructure/vps-ai-sysadmin.md` — 697-line canonical reference: architecture, firewall docs, session model, knowledge sync, notification templates, all scheduled routines, troubleshooting, 9-step replication recipe, files manifest

---

## VPS Audit System

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.5 (2026-05-20)

> **Headline:** 7 structured audit prompts + 7 runner scripts for systematic VPS health evaluation. Designed for parallel AI agent dispatch — each audit runs independently, returns a domain-specific report.

### What It Does

Each audit covers one domain of VPS health. The prompt defines what to check, the script collects the diagnostic data, and Claude Code (or any AI) analyzes it.

| Audit | Script | Prompt | Scope |
|---|---|---|---|
| Full system | `01-full-system.sh` | `01-full-system-audit.md` | CPU, memory, disk, network, services, security, Docker — all 8 domains |
| Container health | `02-container-health.sh` | `02-container-health.md` | Fleet stability, resource pressure, crash loops, compose-stack issues |
| Security | `03-security.sh` | `03-security-hardening.md` | Firewall, TLS, SSH, Authelia, container isolation, secrets |
| Performance | `04-performance.sh` | `04-performance-bottleneck.md` | CPU/memory/disk/network bottleneck identification |
| Observability | `05-observability.sh` | `05-observability-pipeline.md` | Prometheus, Loki, Grafana, GlitchTip, Gatus pipeline health |
| Backup/DR | `06-backup.sh` | `06-backup-disaster-recovery.md` | Backrest plans, B2 connectivity, coverage, recovery readiness |
| Hardening verify | `08-hardening-verify.sh` | `08-hardening-remediation.md` | Post-audit remediation verification with pass/fail score |
| Pre-production | — | `07-pre-production-checklist.md` | Go-live readiness across all layers |

### How To Run

```bash
# Single audit (run from WSL):
ssh vps 'sudo bash -s' < scripts/audit/01-full-system.sh | claude -p "analyze this"

# All audits in parallel (6 agents):
for i in 01 02 03 04 05 06; do
  ssh vps 'sudo bash -s' < scripts/audit/${i}-*.sh > /tmp/audit-${i}.txt &
done; wait

# Via the sysadmin bot (from Telegram):
"run a full security audit"
"check backup health"
"run performance analysis"
```

### Technical Details

- Scripts run with `sudo` (root access for Docker, iptables, journalctl)
- Each script takes 10-30 seconds, outputs structured text
- Prompts include analysis checklists, thresholds, and output format requirements
- First run (2026-05-19) identified: broken Promtail log pipeline, duplicate monitoring containers, empty backup retention, 28 containers without memory limits — all fixed

---

## WordPress Automation

**Status:** Extracted to `/opt/wpf/` | **Audience:** Operator | **Since:** v0.1 (fabrik), standalone since 2026-05

> **Headline:** WordPress site lifecycle was built inside fabrik (Phase 2), then extracted to a standalone project at `/opt/wpf/` — the WordPress Factory.

### History

The WordPress automation engine (13-stage deployer, planner, preset loader, WP-CLI driver, REST API client, theme/page/SEO/analytics/forms/menu modules — ~9,700 LoC) was originally built inside fabrik as Phase 2. It used fabrik's drivers (SSH+Compose, Backrest, Gatus, Cloudflare via site-provisioner; pre-2026-05-30 was Coolify) to deploy WordPress sites from YAML specs.

In May 2026, the engine was extracted to `/opt/wpf/` as a standalone project because:

1. WordPress sites use `kind: wordpress` specs consumed by `wpf wp apply` — they never flow through `fabrik apply` (which only validates `kind: service`)
2. wpf manages its own registrar dispatch (Backrest, Gatus, Cloudflare WAF) independently of fabrik's 9-registrar pipeline
3. wpf will become a SaaS product (GUI wizard, Watchdog AI, billing) — concerns that don't belong in the deployment platform

### Current State

- **fabrik:** WordPress scaffold type still exists (creates the project structure), but `deploy_router.py` raises `NotImplementedError` for WordPress deploys — use wpf instead
- **wpf (`/opt/wpf/`):** Has the full engine, golden-base Docker image system, 133 premium plugin zips, and site specs. Currently in Phase 1+2 (Foundation + Golden Base) — first deploy target is `ocoron.com`
- **Shared drivers:** wpf calls the same VPS infrastructure fabrik does (SSH+Compose deployer, site-provisioner at `:18014`, redis-main, Backrest; pre-2026-05-30 was Coolify API via `COOLIFY_API_TOKEN`) but manages WordPress site lifecycle independently

---

## See Also

- [README.md](../README.md) — Project overview
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [AGENTS.md](../AGENTS.md) — AI agent briefing
- [DEPLOYMENT_ARCHITECTURE.md](DEPLOYMENT_ARCHITECTURE.md) — Deploy flows, state machine, secrets
- [docs/operations/fabrik-lifecycle.md](operations/fabrik-lifecycle.md) — 4-stage lifecycle (Intent → Implementation → Registration → Verification)
