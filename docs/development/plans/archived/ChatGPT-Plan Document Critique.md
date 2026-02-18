# Plan Document Critique

**User:** Anonymous (ob@ocoron.com)  
**Created:** 2/16/2026 19:42:03  
**Updated:** 2/17/2026 12:22:39  
**Exported:** 2/17/2026 13:36:17  
**Link:** [https://chatgpt.com/c/699348b9-38fc-8333-a781-1d4e3bcc6275](https://chatgpt.com/c/699348b9-38fc-8333-a781-1d4e3bcc6275)  

## Prompt:
2026-02-16-plan-gap01-duplicate-detection.md

File

2026-02-16-plan-gap08-property-testing.md

File

2026-02-16-plan-gap07-traycer-integration.md

File

2026-02-16-plan-gap06-custom-droids.md

File

2026-02-16-plan-gap04-kpi-dashboard.md

File

2026-02-16-plan-gap03-mcp-server-config.md

File

2026-02-16-plan-gap09-pipeline-orchestrator.md

File

2026-02-16-plan-gap02-windsurf-workflows.md

File

these are plan documents opus, chatgpt and gemini agreed upon, opus 4.5 will implement them but looking at them i see these plans are very shallow, what do you think?

## Response:
Yes: these plans are “execution checklists,” not implementable specs. They are strong on _process control_ (stages, gates, verifier separation) but shallow on _technical specificity_ and _risk closure_. You’ll likely get inconsistent implementations because too much is left to the builder’s interpretation.

Below is a grounded critique based on the documents you shared.

2026-02-16-plan-gap01-duplicate…

2026-02-16-plan-gap09-pipeline-…

2026-02-16-plan-gap04-kpi-dashb…

2026-02-16-plan-gap03-mcp-serve…

What’s good (but not the issue)
-------------------------------

*   Clear “DONE WHEN,” scope boundaries, and stop conditions appear consistently.
    2026-02-16-plan-gap01-duplicate…
*   Gate-driven workflow + verifier independence is well-defined.
    2026-02-16-plan-gap09-pipeline-…

Why they feel shallow: the missing “spec layer”
-----------------------------------------------

Across the plans, the steps say “create X” and “integrate Y,” but they rarely define:

1.  **Interfaces and data contracts**
    *   Example: KPI plan defines event types conceptually, but not a strict JSON schema (required fields, types, versioning, backward compatibility, idempotency keys, timestamp format).
    2026-02-16-plan-gap04-kpi-dashb…
*   Pipeline runner plan lists functions to call but not the exact input/output structures (StageResult schema, how outputs are persisted, how retries are recorded).
    2026-02-16-plan-gap09-pipeline-…
    2.  **Repository truth / integration points**  
    Many steps assume files and patterns exist (“see check\_secrets.py”, “existing patterns in .pre-commit-config.yaml”, “ci.yml exists”) but don’t anchor with exact paths, snippets, or acceptance diffs.
    *   Duplicate detection plan references existing infra but doesn’t include the actual intended pre-commit hook stanza or workflow step as canonical expected text.
    2026-02-16-plan-gap01-duplicate…
    3.  **Failure modes & rollback**  
    Stop conditions exist, but mitigation/playbooks are often vague:
    *   GAP-01: “stop if npm not available” but no fallback path (e.g., vendored binary, dockerized runner, or CI-only mode).
    2026-02-16-plan-gap01-duplicate…
*   GAP-03 MCP: security constraints are stated, but no explicit threat model (what MCP can read/write, how secrets are prevented from leaking into logs, minimum env var checks, least-privilege scopes).
    2026-02-16-plan-gap03-mcp-serve…
    4.  **Test strategy tied to invariants**  
    Property testing plan is closer to concrete, but still leaves target selection open (“any pure utilities”), which guarantees drift.
    2026-02-16-plan-gap08-property-…
    A real spec would name exact functions/modules and the invariant per function.
5.  **Non-functional requirements**  
    Latency/timeouts, CI runtime budgets, developer ergonomics, log formats, and determinism are mostly absent.
    *   Pipeline orchestrator claims token/cycle metrics in outputs but does not specify how tokens are computed/collected (it references droid\_core token logging indirectly but lacks contract).
    2026-02-16-plan-gap09-pipeline-…

Plan-by-plan “depth gaps” (most important)
------------------------------------------

### GAP-09 Pipeline Orchestrator (P0)

Main risk: it’s a _system_ but described as a _script_. Missing:

*   exact CLI surface (commands, flags, exit codes),
*   persisted state (where pipeline state lives; resumability),
*   deterministic stage transitions (what constitutes success/failure),
*   concrete risk router heuristics and test cases.  
    It lists what functions exist and what to call, but not the orchestration contract.
    2026-02-16-plan-gap09-pipeline-…

### GAP-04 KPI Dashboard (P1)

Main risk: analytics become garbage without strict schema + idempotency.

*   Need schema versioning and stable task identifiers.
*   Need reconciliation rules between `.droid_token_usage.jsonl` and KPI events (duplicate ingestion, partial sessions, missing end events).
    2026-02-16-plan-gap04-kpi-dashb…

### GAP-03 MCP Server Config (P1)

Main risk: security + operational drift.

*   “Credentials in env vars” is not enough—need: how env vars are loaded (shell profile? direnv?), how redaction is enforced, what the MCP servers are allowed to do, and how you audit.
    2026-02-16-plan-gap03-mcp-serve…

### GAP-01 Duplicate Detection (P0)

Main risk: tool friction and false positives.

*   Need baseline strategy (how you avoid blocking initial adoption), exclusion patterns that match repo reality, and a precise policy for “templates are allowed duplicates.”
    2026-02-16-plan-gap01-duplicate…

One optimal fix: add a “Spec Patch” section to every GAP
--------------------------------------------------------

DONE for planning quality = every plan gets an additional _one-page spec patch_ before execution:

**Spec Patch template (must be present)**

1.  **Artifacts list**: exact files to create/modify + expected ownership.
2.  **Contracts**: data schemas / function signatures / CLI flags / exit codes.
3.  **Golden paths**: 2–3 end-to-end examples (commands + expected outputs).
4.  **Edge/failure paths**: at least 5 named failure modes + handling/rollback.
5.  **Tests**: minimal tests required and where they live.
6.  **Operational constraints**: runtime budgets, CI constraints, logging format, determinism.

This keeps your existing gate/verifier structure intact, but removes ambiguity.

DONE (for your question)
------------------------

*   DONE = you can point to 3–5 concrete missing spec elements per plan; the fix is a repeatable “Spec Patch” layer that makes the builder’s job deterministic and verifiable.

If you want, I can rewrite **one** of the GAPs (start with GAP-09) into a “Spec Patch + Execution Steps” version using only the content already present in these docs, so Opus 4.5 has much less room to improvise.

## Prompt:
Optimizing Workflows Across AI Coding Platforms for Fast, Low-Cost, Near-Flawless Code.md

File

these plans for modifying my existing fabrik structure according to attached principles. now what should i tell my coder ai so that it can plan it perfectly.

## Response:
Tell your coder AI to produce a **“Spec Patch”** for _your existing Fabrik repo_, not a generic plan. Your current GAP plans already enforce staged execution + verifier separation, but they lack the “repo-grounded spec layer” (exact files, contracts, failure modes). The instruction below forces the missing depth while staying consistent with your principles (planner→implementer→verifier; gates; spec-freeze).

Optimizing Workflows Across AI …

2026-02-16-plan-gap03-mcp-serve…

What to tell the coder AI (copy/paste prompt)
---------------------------------------------

**ROLE:** You are the _Planner_. You must output a repo-specific implementation plan for modifying an existing Fabrik structure according to the attached principles and GAP docs. Do **not** implement anything.

### 1) Required repo reconnaissance (must be first)

Before planning, scan the repo and produce an “As-Is Map”:

*   Repo tree summary (top 3 levels)
*   Existing related files/infra per GAP:
    *   `.pre-commit-config.yaml`, `.github/workflows/*`, `scripts/droid_core.py`, `scripts/enforcement/*`, `AGENTS.md`, `.windsurf/*`, `config/models.yaml`, `.droid_token_usage.jsonl` (if present)
*   For each GAP, list **exact existing hooks/scripts** that will be extended (not duplicated). This is a core constraint in the GAPs.
    2026-02-16-plan-gap03-mcp-serve…
    2026-02-16-plan-gap04-kpi-dashb…

If any of these do not exist, report it explicitly and propose a minimal compatible placement.

### 2) Produce a “Spec Patch” per GAP (mandatory)

For each GAP you intend to modify (GAP-01/02/03/04/06/07/08/09), output the following sections:

**A. Files-to-change (exact)**

*   Create/modify list with paths + brief reason
*   Expected diff size (S/M/L)

**B. Contracts (machine-readable)**

*   If the GAP introduces data/events (e.g., KPI JSONL), define:
    *   JSON schema (required fields, types, version, idempotency key, timestamp format)
    *   Example events (2–3)
*   If the GAP introduces a CLI (e.g., pipeline\_runner), define:
    *   Commands, flags, exit codes, stdout/stderr format  
        This is the biggest depth gap today, especially in KPI + orchestrator.
        2026-02-16-plan-gap04-kpi-dashb…
        2026-02-16-plan-gap03-mcp-serve…

**C. Golden paths**

*   2–3 concrete end-to-end runs with commands and expected outputs (copyable)

**D. Failure modes + rollback**

*   At least 5 named failure modes per GAP + handling
*   Rollback procedure (git revert / disable flag / CI bypass strategy)  
    Examples: “npm missing” in GAP-01 stop condition must have a fallback path.
    2026-02-16-plan-gap01-duplicate…

**E. Verification plan**

*   Exact gates to run, in order (local + CI)
*   What the verifier must check and how (JSON output shape)  
    Your GAP templates already demand post-step evidence + Mode 4 verification; keep that structure.
    2026-02-16-plan-gap01-duplicate…

### 3) Build an integrated execution order (dependency graph)

Output a dependency graph and an execution order across GAPs:

*   Example dependencies:
    *   GAP-09 pipeline orchestrator depends on existing `droid_core.py` orchestration functions (explicitly required).
        2026-02-16-plan-gap03-mcp-serve…
    *   KPI capture depends on token log ingestion and hook wiring (must not modify core session logging).
        2026-02-16-plan-gap04-kpi-dashb…
    *   Duplicate detection should be early because it prevents rework.
        2026-02-16-plan-gap01-duplicate…

### 4) “Definition of DONE” must be testable

For each GAP, rewrite DONE into commands that return PASS/FAIL. Reuse the existing “canonical gate” pattern from the plans.

2026-02-16-plan-gap03-mcp-serve…

### 5) Output format (strict)

Return:

1.  As-Is Map
2.  Dependency graph + recommended order
3.  Spec Patch per GAP
4.  Risk register (top 10 risks + mitigation)
5.  A single “Next command to run” to start Stage 1.

Why this works (in one line)
----------------------------

It forces the AI to replace vague “create X” steps with **repo-grounded interfaces, exact file diffs, testable gates, and failure-mode closure**, while preserving your existing staged pipeline discipline.

Optimizing Workflows Across AI …

2026-02-16-plan-gap03-mcp-serve…

If you want, I can compress this into a shorter “Planner System Prompt” for your coder AI, but the above version is the one that reliably produces non-shallow plans.

## Prompt:
so does it need to create new files or convert these files? i do not want to waste too much token for recreating what we already have. so give me exact prompt to achieve want we want

## Response:
Thought for 25s

Copy/paste this prompt to your coder AI (Opus 4.5 / Cascade / etc.). It is designed to minimize tokens by **reusing existing files first** and only creating **missing** files when unavoidable.

* * *

**PROMPT (paste as-is)**

You are my “Integrator Planner” for an existing repo (“fabrik”). Your job is to produce a **precise, non-shallow implementation plan** that modifies the existing structure according to the attached GAP plans and workflow principles.

Inputs you must treat as binding specs
--------------------------------------

*   GAP-09 Pipeline Orchestrator plan
*   GAP-01 Duplicate Detection plan
*   “Optimizing Workflows Across AI Coding Platforms…” principles

Key constraints you must obey:

*   **Extend, don’t duplicate** existing infrastructure (reuse functions and existing patterns).
    2026-02-16-plan-gap09-pipeline-…
*   For duplicate detection, integrate with existing repo enforcement/CI patterns rather than inventing new ones.
    2026-02-16-plan-gap01-duplicate…
*   This is a pipeline/guardrails problem: make state explicit, split roles, enforce via hooks/CI, and make verification automatic-first.
    Optimizing Workflows Across AI …

Primary objective
-----------------

Produce an **implementation plan that avoids recreating what already exists**. I want the smallest necessary delta: modify existing files wherever possible; only add new files if there is no suitable existing home.

Hard rules (token + change minimization)
----------------------------------------

1.  **Inventory first, then plan.** Before proposing any new file, you must locate existing equivalents (scripts, configs, enforcement checks, workflows).
2.  **No large rewrites.** Prefer small diffs over refactors unless the GAP “DONE WHEN” explicitly requires a new artifact.
3.  **New files are allowed only when a plan explicitly requires them AND no equivalent exists.**
    *   Example: if GAP-09 requires `scripts/pipeline_runner.py`, you may create it, but still reuse `scripts/droid_core.py` functions and patterns.
        2026-02-16-plan-gap09-pipeline-…
4.  **Every proposed change must include:**
    *   exact file path
    *   whether it is **MODIFY** or **CREATE**
    *   reason (1–2 lines) tied to a specific “DONE WHEN” item or plan step
    *   smallest-diff approach (what you will _not_ change)

What you must deliver (single response)
---------------------------------------

### A) Repo mapping (evidence-based)

*   List the existing files you found that correspond to each GAP area (pipeline orchestration, enforcement scripts, pre-commit config, CI workflows, model config, etc.).
*   If you cannot find something, say “NOT FOUND” and propose the minimal new file.

### B) File change plan (minimal-delta)

Create a table:

*   GAP ID
*   Path
*   Action (MODIFY/CREATE)
*   Minimal change summary (bullets)
*   Acceptance gate command(s) to prove it works

### C) Step-by-step execution plan (gated)

*   Break into steps that each end with a **gate command** and required evidence output.
*   Include verifier handoff points (builder vs verifier separation) and re-verify cap where specified.
    2026-02-16-plan-gap09-pipeline-…

### D) Decision rule for “create vs modify”

At the end, give a strict rule-set answering:

*   “Do we need to create new files or convert existing ones?”  
    Your answer must be grounded in the repo mapping + the GAP “DONE WHEN” requirements (not guesswork).

Stop conditions
---------------

If any GAP prerequisite is missing (tools not installed, referenced functions absent, etc.), STOP and report the exact blocker + at most 2 fixes (as the GAPs require).

2026-02-16-plan-gap09-pipeline-…

2026-02-16-plan-gap01-duplicate…

Important
---------

Do NOT write code yet. Do NOT propose broad architecture changes. Do NOT regenerate existing content. Produce only the precise minimal-delta plan.

* * *

If you want, I can adapt that prompt to mention **all** your GAP files explicitly (GAP-02..GAP-08) once you upload them or confirm they’re in the same batch—right now I only have grounded excerpts for GAP-01 and GAP-09 plus the principles doc.

## Prompt:
i have not only updated GAP-09 Pipeline Orchestrator plan

GAP-01 Duplicate Detection plan to you, i have uploaded 9 files.

## Response:
Thought for 29s

Use this exact prompt. It explicitly references **all 9 uploaded GAP plans + the principles doc** and forces the coder AI to decide **CREATE vs MODIFY** only when the GAP “DONE WHEN” requires it, otherwise reuse/extend existing infra (pre-commit, enforcement scripts, CI, droid\_core, hooks, templates).

2026-02-16-plan-gap01-duplicate…

2026-02-16-plan-gap09-pipeline-…

2026-02-16-plan-gap04-kpi-dashb…

* * *

Exact prompt to give your coder AI (copy/paste)
-----------------------------------------------

You are my **Integrator Planner** for an existing repo (“fabrik”). Your task is to produce a **repo-grounded, minimal-delta implementation plan** that applies ALL attached plans:

*   GAP-01 Duplicate Detection (jscpd)
*   GAP-02 Windsurf Workflows
*   GAP-03 MCP Server Config
*   GAP-04 KPI Dashboard
*   GAP-06 Custom Droids
*   GAP-07 Traycer Integration
*   GAP-08 Property-Based Testing
*   GAP-09 Pipeline Orchestrator
*   “Optimizing Workflows Across AI Coding Platforms…” principles

### Hard constraints you must obey (binding)

1.  **Extend, don’t duplicate** existing infrastructure. GAP docs repeatedly require reuse of existing configs/scripts/templates and avoiding duplicated logic.
    2026-02-16-plan-gap01-duplicate…
    2026-02-16-plan-gap02-windsurf-…
    2026-02-16-plan-gap09-pipeline-…
2.  **Minimal tokens + minimal diffs**: do not rewrite or restate the GAP documents. Only produce the delta plan.
3.  **No new external deps where prohibited** (e.g., GAP-09: “No new external deps”, use existing `droid_core.py` functions only).
    2026-02-16-plan-gap09-pipeline-…
4.  Follow the workflow discipline: staged execution, gates, builder vs verifier separation, and verifier does not implement fixes.
    2026-02-16-plan-gap06-custom-dr…
    2026-02-16-plan-gap09-pipeline-…
5.  If a plan calls for new artifacts explicitly (e.g., GAP-09 says `scripts/pipeline_runner.py` must exist; GAP-02 says `.windsurf/workflows/` must exist), you may create them. Otherwise, default to MODIFY.
    2026-02-16-plan-gap09-pipeline-…
    2026-02-16-plan-gap02-windsurf-…

* * *

Step 0: Repo inventory (must be first; keep it short)
-----------------------------------------------------

Scan the repo and output an “As-Is Map”:

*   Tree summary (top 3 levels)
*   Confirm presence/paths of these expected integration points (or say NOT FOUND):
    *   `.pre-commit-config.yaml` (GAP-01, GAP-08)
    *   `scripts/enforcement/` (GAP-01, GAP-02)
    *   `.github/workflows/` (GAP-01, GAP-08)
    *   `scripts/droid_core.py` (GAP-09)
    *   `scripts/droid-review.sh` (GAP-04)
    *   `.droid_token_usage.jsonl` (GAP-04 data source)
    *   `templates/traycer/` (GAP-07)
    *   `config/models.yaml` (models referenced in multiple GAPs)
    *   `tests/` and `pyproject.toml` (GAP-08)  
        If anything is missing, list it as a blocker and propose **at most 2** minimal fixes (STOP CONDITIONS pattern).
        2026-02-16-plan-gap04-kpi-dashb…

* * *

Deliverable: Minimal-Delta “Spec Patch Plan” (single response)
--------------------------------------------------------------

Output ONLY the following sections:

### 1) CREATE vs MODIFY decision (global)

Answer: “Do we need to create new files or convert existing ones?”  
Rule-set must be strict:

*   CREATE only if required by a GAP DONE WHEN (e.g., pipeline\_runner must exist; workflows dir must exist; KPI tracker CLI must exist; new droids must exist; some docs/test files are explicitly required).
    2026-02-16-plan-gap09-pipeline-…
    2026-02-16-plan-gap02-windsurf-…
    2026-02-16-plan-gap04-kpi-dashb…
    2026-02-16-plan-gap06-custom-dr…
    2026-02-16-plan-gap08-property-…
*   Otherwise MODIFY an existing equivalent.

### 2) File-level change table (the core output)

A table with columns:

*   GAP
*   Path
*   Action (CREATE/MODIFY)
*   Minimal change summary (3–6 bullets; explicitly say what you will NOT change)
*   Gate command(s) proving DONE WHEN

### 3) Dependency order (short)

Give the recommended order across GAPs with 1-line justification each (e.g., run duplicate detection early to prevent rework; orchestrator depends on `droid_core`; KPI depends on token log ingestion; etc.).

Optimizing Workflows Across AI …

2026-02-16-plan-gap09-pipeline-…

2026-02-16-plan-gap04-kpi-dashb…

### 4) Spec contracts only where data/interfaces exist

Only for components that emit/consume structured data/CLI outputs:

*   KPI event schema + JSONL required fields (GAP-04)
    2026-02-16-plan-gap04-kpi-dashb…
*   pipeline\_runner CLI commands/exit codes (GAP-09)
    2026-02-16-plan-gap09-pipeline-…
    Keep this section concise.

### 5) Stop conditions checklist

Aggregate STOP IF items (tool missing, incompatible token log format, missing hook capability, etc.) and the “at most 2 fixes” rule.

2026-02-16-plan-gap04-kpi-dashb…

2026-02-16-plan-gap09-pipeline-…

* * *

Important prohibitions
----------------------

*   Do NOT implement code.
*   Do NOT regenerate the GAP docs.
*   Do NOT propose broad refactors.
*   Do NOT add deps where prohibited (especially GAP-09).
    2026-02-16-plan-gap09-pipeline-…

* * *

First command you should run
----------------------------

At the end, output exactly one “Next command” that I can run to start with Step 0 inventory (e.g., `ls`, `rg`, or repo tree command).

* * *

If you paste that, your coder AI will be forced to (a) inventory first, (b) map each GAP to existing repo artifacts, and (c) choose CREATE only where the GAPs explicitly demand new artifacts (like `scripts/pipeline_runner.py`, `.windsurf/workflows/*.md`, KPI schema/doc + `kpi_tracker.py`, property tests, Traycer evaluation doc, and new droid markdowns).

## Prompt:
so what will the ai create when i send this prompt?

## Response:
Thought for 50s

If you send the “planner-only / no code” prompt (the one that forces a **file-impact plan**), the AI should **not create or convert anything immediately**. It should output a **deterministic plan** that lists:

*   **CREATE (new files)**
*   **MODIFY (existing files)**
*   **NO-CHANGE (verify exists, leave as-is)**
*   plus **commands/gates** to prove each change is correct.

So the “artifact” it creates is a **plan + file-diff manifest**, not code.

What the plan should say will be created/modified (based on your 9 GAP specs)
-----------------------------------------------------------------------------

### GAP-09 Pipeline Orchestrator

*   **CREATE:** `scripts/pipeline_runner.py` (explicit DONE WHEN).
    2026-02-16-plan-gap09-pipeline-…
*   Likely **MODIFY:** nothing else is mandated by DONE WHEN, but it must reuse existing `scripts/droid_core.py` functions (so the plan should confirm what exists and avoid duplication).
    2026-02-16-plan-gap09-pipeline-…

### GAP-01 Duplicate Detection

*   **CREATE:** `.jscpd.json`
    2026-02-16-plan-gap01-duplicate…
*   **MODIFY:** `.pre-commit-config.yaml` to add the hook
    2026-02-16-plan-gap01-duplicate…
*   **CREATE:** `scripts/enforcement/check_duplicates.py`
    2026-02-16-plan-gap01-duplicate…
*   **MODIFY:** `scripts/enforcement/validate_conventions.py` to call it
    2026-02-16-plan-gap01-duplicate…
*   **CREATE:** `docs/reference/duplicate-baseline.md`
    2026-02-16-plan-gap01-duplicate…
*   **MODIFY:** `.github/workflows/ci.yml` (or create if absent)
    2026-02-16-plan-gap01-duplicate…
*   **MODIFY:** `docs/TESTING.md`, `CHANGELOG.md`, maybe `AGENTS.md`
    2026-02-16-plan-gap01-duplicate…

### GAP-06 Custom Droids

These are not repo files; they’re on your machine:

*   **CREATE (outside repo):** 4 new droids in `/home/ozgur/.factory/droids/` (planner, security-auditor, test-generator, documentation-writer).
    2026-02-16-plan-gap06-custom-dr…
*   **CREATE:** `docs/reference/custom-droids.md`
    2026-02-16-plan-gap06-custom-dr…
*   **MODIFY:** `AGENTS.md` and `CHANGELOG.md`
    2026-02-16-plan-gap06-custom-dr…

### GAP-03 MCP Server Config

Also outside repo:

*   **MODIFY:** `~/.factory/mcp.json` to include at least 2 MCP servers
    2026-02-16-plan-gap03-mcp-serve…
*   (Plan must explicitly keep credentials out of the file.)
    2026-02-16-plan-gap03-mcp-serve…

### GAP-04 KPI Dashboard (CLI-only)

*   **CREATE:** `scripts/kpi_tracker.py` (implied by gate/CLI commands)
    2026-02-16-plan-gap04-kpi-dashb…
*   **Runtime data file:** `.droid/kpis.jsonl` (stored as data; plan should treat it as generated, not “source code”).
    2026-02-16-plan-gap04-kpi-dashb…
*   **MODIFY:** `scripts/droid-review.sh` to log KPI events
    2026-02-16-plan-gap04-kpi-dashb…
*   **CREATE/MODIFY docs:** `docs/reference/kpi-schema.md`, `docs/CONFIGURATION.md`, `AGENTS.md`, `CHANGELOG.md`
    2026-02-16-plan-gap04-kpi-dashb…

### GAP-07 Traycer Integration (evaluation only)

*   **CREATE:** `docs/reference/traycer-evaluation.md` with a “Decision:” line (gate)
    2026-02-16-plan-gap07-traycer-i…
*   **MODIFY:** “templates updated for Traycer compatibility” (the plan should enumerate exactly which templates change, but it’s explicitly required).
    2026-02-16-plan-gap07-traycer-i…

### GAP-08 Property Testing

*   **MODIFY:** `pyproject.toml` to add `hypothesis` under dev optional deps
    2026-02-16-plan-gap08-property-…
    2026-02-16-plan-gap08-property-…
*   **MODIFY/CREATE:** at least 3 property-based tests under `tests/`
    2026-02-16-plan-gap08-property-…
*   **MODIFY:** documentation (not named here, but “Documentation updated” is in DONE WHEN)
    2026-02-16-plan-gap08-property-…

Direct answer to your question (“new files or convert these files?”)
--------------------------------------------------------------------

*   It should **not convert** your 9 plan documents.
*   It should **not recreate** anything that already exists.
*   It should produce a plan that **minimizes token waste** by first deciding, per required artifact: **exists? then modify; missing? then create**.

If your prompt instructs it to output a **File Impact Manifest**, the AI’s output should look like:

*   `CREATE:` \[list\]
*   `MODIFY:` \[list\]
*   `VERIFY EXISTS (no change):` \[list\]
*   `GATES TO RUN:` \[commands from each GAP\]

That’s what it “creates” when you send the prompt: a precise manifest + gates, not the code itself.

## Prompt:
at the beginning i told you "these are plan documents opus, chatgpt and gemini agreed upon, opus 4.5 will implement them but looking at them i see these plans are very shallow, what do you think?
 now i am lost, what should i tell him to create better plans?

## Response:
You are lost because you are asking the AI to “plan better” without changing the **planning interface**.

Your current GAP docs are **execution checklists**.  
What you need is a **Spec-Level Plan Generator**.

Below is the exact instruction you should give Opus 4.5 so it produces deep, non-shallow plans.

* * *

Copy-Paste This To Opus 4.5
===========================

You are not implementing anything.

You are generating a **Spec-Level Implementation Plan** for modifying an existing repo according to the attached GAP documents.

The previous plans were too shallow because they described tasks, not specifications.

Your job is to convert each GAP into a **Deterministic Spec Plan**.

* * *

1\. Before Planning: Repo Grounding (Mandatory)
-----------------------------------------------

Scan the repository and produce:

*   Top-level structure (3 levels deep)
*   Existing files related to:
    *   enforcement
    *   CI workflows
    *   droid\_core
    *   pre-commit
    *   tests
    *   model config
    *   token logs
    *   scripts/

For every GAP requirement, state:

*   FOUND (path)
*   NOT FOUND (will need CREATE)
*   EXISTS BUT INCOMPLETE (MODIFY)

Do not assume anything.

* * *

2\. For Each GAP, Produce a “Spec Patch”
----------------------------------------

For each GAP, output exactly these sections:

### A. Problem Definition

What system-level behavior must change?

### B. Required Artifacts (CREATE vs MODIFY)

Table:

*   Path
*   Action (CREATE / MODIFY / VERIFY)
*   Why required (tie to DONE WHEN)
*   What will NOT be changed

### C. Interfaces and Contracts (Mandatory)

If the GAP introduces:

*   CLI → define commands, flags, exit codes, stdout/stderr format
*   JSON data → define schema (fields, types, required, versioning)
*   Hook integration → define invocation order + failure semantics
*   Pipeline orchestration → define state transitions and retry rules

No vague language allowed.  
Everything must be machine-testable.

### D. Golden Path (End-to-End)

2 concrete examples:

*   command
*   expected output
*   expected side effects

### E. Failure Modes

At least 5:

*   failure condition
*   detection mechanism
*   mitigation
*   rollback

### F. Gate Definition

Define:

*   exact command to run
*   what constitutes PASS
*   what constitutes FAIL

* * *

3\. Cross-GAP Integration Map
-----------------------------

Produce:

*   Dependency graph
*   Execution order
*   Shared artifacts (avoid duplication)
*   Conflicts between GAPs (if any)

* * *

4\. Minimal-Delta Rule
----------------------

You must default to MODIFY over CREATE unless the GAP explicitly requires a new artifact.

If creating a new file, justify why no existing file can host the functionality.

* * *

5\. Output Constraints
----------------------

Do NOT:

*   Implement code
*   Rewrite GAP documents
*   Add new architectural concepts
*   Suggest refactors beyond minimal-delta
*   Add new external dependencies where prohibited

Produce a structured, deterministic plan only.

* * *

Why This Works
==============

Your earlier plans were shallow because they:

*   Said “create X”
*   Said “integrate Y”
*   Did not define contracts
*   Did not define failure semantics
*   Did not define deterministic gates
*   Did not ground against existing repo state

This prompt forces:

*   Repo awareness
*   Explicit interfaces
*   State machine definition
*   Testability
*   Failure handling
*   Minimal diffs

That transforms “checklist planning” into “implementation-spec planning”.

* * *

What You Should Expect Back
===========================

A response that:

*   Lists CREATE vs MODIFY clearly
*   Defines schemas and CLI contracts
*   Defines retry logic and state transitions
*   Provides deterministic gate commands
*   Shows integration across all 9 GAPs
*   Removes ambiguity

If the response does not contain:

*   Schemas
*   CLI definitions
*   State transitions
*   Failure matrix
*   Gate commands

Then it is still shallow.

* * *

If you want, I can now:

*   Rewrite one of your GAPs (GAP-09 is the most critical) into a proper Spec-Level Plan so you can see the difference immediately.

## Prompt:
ok so i can use this prompt for only gap-0 to test or what do you suggest? i will copy it back to you so you can evaluate your prompts efficiency?

## Response:
Do **not** start with all 9 GAPs.

Start with **GAP-09 (Pipeline Orchestrator)** only.

Reason:

*   It is the highest structural complexity.
*   It touches orchestration, state, retries, risk routing.
*   If the AI produces a deep spec here, it will likely handle the others well.
*   If it fails here, the prompt is still insufficient.

GAP-01 is too mechanical (tool + hook + CI). It won’t stress the planner.

* * *

How to Test Properly
--------------------

### Step 1 — Send the spec-level prompt

Limit scope explicitly:

> “Apply this process ONLY to GAP-09. Do not analyze other GAPs.”

This reduces token sprawl and keeps evaluation focused.

* * *

### Step 2 — What a Good Output Must Contain

When you paste the response back, I will evaluate it against these criteria:

A good plan for GAP-09 must include:

1.  Explicit CLI definition
    *   commands
    *   flags
    *   exit codes
2.  State machine definition
    *   stage transitions
    *   retry logic
    *   failure routing
3.  Data contract
    *   what a StageResult object contains
    *   JSON shape
4.  Integration mapping
    *   exact functions reused from `droid_core.py`
    *   what is not modified
5.  Failure matrix (at least 5 cases)
6.  Deterministic gate command

If any of those are missing, it is still shallow.

* * *

Important Adjustment to the Prompt (small but critical)
-------------------------------------------------------

Add this one line before sending it:

> “If your output contains vague language like ‘integrate’, ‘ensure’, ‘handle appropriately’, or ‘follow existing patterns’ without defining exact behavior, the plan is invalid.”

This forces precision.

* * *

Why This Controlled Test Matters
--------------------------------

If you test all 9 at once:

*   You won’t know if the prompt works.
*   Token waste increases.
*   Debugging becomes unclear.

Testing GAP-09 isolates the planning intelligence.

* * *

Yes — Paste It Back
-------------------

When you get the output:

*   Paste the full response here.
*   I will evaluate:
    *   depth
    *   determinism
    *   ambiguity
    *   hidden architectural risk
    *   token efficiency
    *   whether the prompt needs tightening

We will iterate once or twice until it produces spec-grade plans reliably.

That is the correct way to debug a planning meta-prompt.

## Prompt:
now give me the final prompt to send

## Response:
Below is the **final, tightened prompt**.  
Use it **only for GAP-09 (Pipeline Orchestrator)** as a controlled test.

Copy-paste exactly.

* * *

FINAL PROMPT — GAP-09 Spec-Level Plan
=====================================

You are generating a **Spec-Level Implementation Plan**.

Scope: **GAP-09 Pipeline Orchestrator only.**  
Do not analyze or mention any other GAP.

You are not implementing code.

Your task is to transform GAP-09 into a **deterministic, repo-grounded specification plan** that removes ambiguity and prevents shallow execution.

* * *

0\. Hard Constraints
--------------------

*   Extend existing infrastructure. Do not duplicate logic.
*   No new external dependencies.
*   Reuse `scripts/droid_core.py` functions.
*   Minimal-delta rule: MODIFY over CREATE unless explicitly required.
*   If vague wording appears (e.g., “integrate”, “handle”, “ensure”), your output is invalid unless exact behavior is defined.
*   Do not restate the GAP document. Convert it into a spec.

* * *

1\. Repo Grounding (Mandatory First Section)
--------------------------------------------

Scan the repository and output:

### A. Structure Map (top 3 levels)

### B. GAP-09 Integration Points

For each required component, mark:

*   FOUND (path)
*   NOT FOUND
*   EXISTS BUT INCOMPLETE

Specifically check:

*   `scripts/droid_core.py`
*   `scripts/`
*   enforcement scripts
*   CLI entry patterns
*   logging/token tracking utilities
*   CI workflow triggers

If something required by GAP-09 does not exist, explicitly state the blocker and propose at most 2 minimal fixes.

* * *

2\. Required Artifacts (CREATE vs MODIFY)
-----------------------------------------

Produce a table:

*   Path
*   Action (CREATE / MODIFY / VERIFY)
*   Justification (tie directly to GAP-09 DONE WHEN)
*   What will NOT be changed
*   Estimated diff size (S/M/L)

Do not create new files unless strictly required.

* * *

3\. Interface & Contract Specification (Mandatory Precision)
------------------------------------------------------------

### A. CLI Contract

Define:

*   Command syntax
*   Subcommands
*   Flags
*   Exit codes (numeric)
*   stdout format
*   stderr format

Example format required:

```
fabrik pipeline run --stage PLAN --task-id T123
Exit codes:
0 = success
1 = stage failure
2 = retry exhausted
3 = configuration error
...
```

No vague language.

* * *

### B. State Machine Definition

Define:

*   Valid stages
*   Stage transition rules
*   Retry logic (max attempts, backoff strategy)
*   Failure routing rules
*   Risk routing behavior (if applicable)
*   Deterministic stage completion criteria

Provide a transition table.

* * *

### C. Data Contract

Define exact JSON schema for:

*   StageResult object
*   Pipeline state persistence
*   Any log/event emission

Include:

*   Required fields
*   Types
*   Optional fields
*   Version field
*   Idempotency mechanism (if applicable)

Provide 1 concrete JSON example.

* * *

4\. Golden Paths (2 Required)
-----------------------------

Provide two full end-to-end examples:

Example must include:

*   command run
*   expected stdout
*   expected exit code
*   expected file/log side effect

* * *

5\. Failure Matrix (Minimum 5 Cases)
------------------------------------

For each:

*   Failure condition
*   Detection mechanism
*   System response
*   Retry behavior
*   Exit code
*   Rollback behavior (if any)

No generic wording allowed.

* * *

6\. Deterministic Gate Definition
---------------------------------

Define exactly:

*   Command to verify DONE WHEN
*   Expected PASS output
*   Expected FAIL output
*   CI validation hook (if applicable)

* * *

7\. Cross-System Impact
-----------------------

Briefly describe:

*   What other components are touched indirectly
*   What is explicitly NOT changed
*   How this avoids duplication of `droid_core.py`

Keep concise.

* * *

8\. Output Rules
----------------

Do NOT:

*   Implement code
*   Rewrite GAP text
*   Add architectural refactors
*   Add new dependencies
*   Generalize beyond GAP-09

If any required section is incomplete or ambiguous, explicitly state why and stop.

* * *

End of Prompt
=============

* * *

When Opus responds, paste the result here.  
I will evaluate:

*   Determinism
*   Precision
*   Missing contracts
*   Architectural risk
*   Token efficiency
*   Whether the prompt needs tightening further.

## Prompt:
do you think using traycer.ai will help me a lot ?
ai coders does not forget context, skip or overlook written rules, creates different ui module even in the same page/module, creates duplicate codes and database fields, make mistakes and require continuous reviews by other ais or human, i think traycer.ai might help me a lot. 

opus replied see below

---

# GAP-09 Pipeline Orchestrator — Spec-Level Implementation Plan

**Version:** 1.0.0  
**Date:** 2026-02-16  
**Status:** SPEC (not implementation)

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

/opt/fabrik/
├── scripts/
│   ├── droid_core.py          # Core execution functions
│   ├── droid_models.py        # Model resolution
│   ├── droid_session.py       # Session management
│   ├── process_monitor.py     # Process tracking
│   ├── enforcement/           # Validation scripts
│   │   └── validate_conventions.py
│   └── droid/                  # Batch scripts
├── config/
│   └── models.yaml            # Model configuration
├── tests/
│   ├── test_droid_core.py     # Existing droid tests
│   └── orchestrator/          # Orchestrator tests exist
├── .github/workflows/
│   ├── daily-maintenance.yml
│   └── droid-review.yml
└── docs/development/plans/
    └── 2026-02-16-plan-gap09-pipeline-orchestrator.md

### B. GAP-09 Integration Points

| Component | Status | Path | Notes |
|-----------|--------|------|-------|
| [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1224 | Returns [MultiModelResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:1152:0-1159:43) |
| [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1298 | max_review_iterations param |
| [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1488 | Returns tuple[bool, str] |
| [run_parallel_models()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1162:0-1220:18) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1163 | Returns dict[str, TaskResult] |
| [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Core execution |
| [TaskType](cci:2://file:///opt/fabrik/scripts/droid_core.py:126:0-144:61) enum | **FOUND** | @/opt/fabrik/scripts/droid_core.py | 11 task types |
| [TaskResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:147:0-157:33) dataclass | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Standard result |
| [MultiModelResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:1152:0-1159:43) dataclass | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1155 | Multi-model result |
| TOOL_CONFIGS dict | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Model assignments |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **FOUND** | @/opt/fabrik/config/models.yaml | Stage model config |
| scripts/pipeline_runner.py | **NOT FOUND** | — | **CREATE required** |
| tests/test_pipeline_runner.py | **NOT FOUND** | — | **CREATE required** |
| Token tracking utility | **FOUND** | @/opt/fabrik/scripts/.droid_token_usage.jsonl | Append-only log |
| CI workflow trigger | **FOUND** | @/opt/fabrik/.github/workflows/droid-review.yml | Existing pattern |

### C. Blockers & Minimal Fixes

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|-------------|--------------|
| scripts/pipeline_runner.py does not exist | **CREATE** new file (GAP-09 scope) | N/A — required |
| tests/test_pipeline_runner.py does not exist | **CREATE** minimal unit tests | Skip tests (not recommended) |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| scripts/pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN: "scripts/pipeline_runner.py exists" | — | **L** (~400 lines) |
| tests/test_pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN: "Integration test passes" | — | **M** (~150 lines) |
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **VERIFY** | Confirm multi-model functions exist and callable | All existing code | **0** |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **VERIFY** | Confirm stage model configs present | All existing config | **0** |
| [docs/development/plans/2026-02-16-plan-gap09-pipeline-orchestrator.md](cci:7://file:///opt/fabrik/docs/development/plans/2026-02-16-plan-gap09-pipeline-orchestrator.md:0:0-0:0) | **MODIFY** | Update status to COMPLETE on success | Content except status | **S** (~2 lines) |

---

## 3. Interface & Contract Specification

### A. CLI Contract

**Command syntax:**

bash
python scripts/pipeline_runner.py <command> [options]

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| run | Execute full pipeline |
| stage | Execute single stage |
| --help | Show help |
| --version | Show version |

**Flags for run subcommand:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| TASK | positional | yes | — | Task description string |
| --dry-run | flag | no | false | Simulate without execution |
| --stage | choice | no | auto | Start at specific stage: discovery, planning, execution, verification, ship |
| --risk | choice | no | auto | Override risk level: low, medium, high |
| --session-id | string | no | — | Resume existing session |
| --cwd | path | no | . | Working directory |
| --json | flag | no | false | Output JSON instead of text |
| --verbose | flag | no | false | Verbose logging to stderr |

**Flags for stage subcommand:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| STAGE | positional | yes | — | Stage name: discovery, planning, execution, verification, ship |
| PROMPT | positional | yes | — | Stage prompt |
| --session-id | string | no | — | Session ID for continuity |
| --cwd | path | no | . | Working directory |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success — all stages passed |
| 1 | Stage failure — one stage failed after retries |
| 2 | Retry exhausted — MAX 2 re-verify iterations exceeded |
| 3 | Configuration error — missing model config, invalid flags |
| 4 | Pre-flight gate failure — ruff/mypy/pytest failed |
| 5 | Risk assessment failure — cannot assess task risk |
| 10 | Dry-run success — simulation completed |

**stdout format (default):**

PIPELINE: <task_summary>
RISK: <LOW|MEDIUM|HIGH>
STARTING: Stage <N>

STAGE 1 DISCOVERY: <PASS|SKIP>
STAGE 2 PLANNING: <PASS|SKIP>
STAGE 3 EXECUTION: <PASS|FAIL>
STAGE 4 VERIFICATION: <PASS|FAIL> (iteration <N>/2)
STAGE 5 SHIP: <PASS|SKIP>

RESULT: <SUCCESS|FAILURE>
TIME: <seconds>s
TOKENS: <estimated>

**stderr format:**

[PIPELINE] <timestamp> <level>: <message>

### B. State Machine Definition

**Valid stages:**

| Stage | ID | Entry Condition | Exit Condition |
|-------|----|-----------------|----------------|
| INIT | 0 | Pipeline started | Risk assessed |
| DISCOVERY | 1 | Risk == HIGH | MultiModelResult.merged_result not empty |
| PLANNING | 2 | Risk >= MEDIUM OR Stage 1 passed | Plan JSON valid |
| EXECUTION | 3 | Pre-flight gates pass | Code changes applied, no errors |
| VERIFICATION | 4 | Stage 3 passed | {"approved": true} OR iteration == 2 |
| SHIP | 5 | Stage 4 passed, docs affected | CHANGELOG updated |
| DONE | 6 | Final stage passed | — |
| FAILED | -1 | Any stage fails after retries | — |

**Stage transition rules:**

| From | To | Condition |
|------|----|-----------|
| INIT | DISCOVERY | risk == HIGH |
| INIT | PLANNING | risk == MEDIUM |
| INIT | EXECUTION | risk == LOW |
| DISCOVERY | PLANNING | Stage 1 success |
| PLANNING | EXECUTION | Stage 2 success |
| EXECUTION | VERIFICATION | Pre-flight pass AND Stage 3 success |
| VERIFICATION | SHIP | Stage 4 approved |
| VERIFICATION | EXECUTION | Stage 4 rejected AND iteration < 2 |
| VERIFICATION | FAILED | Stage 4 rejected AND iteration == 2 |
| SHIP | DONE | Stage 5 success OR no docs affected |
| Any | FAILED | Unrecoverable error |

**Retry logic:**

| Stage | Max Attempts | Backoff | Escalation |
|-------|--------------|---------|------------|
| VERIFICATION | 2 | None | Exit code 2, human escalation |
| All others | 1 | None | Immediate failure |

**Risk routing behavior:**

| Risk Level | Starting Stage | Stages Executed |
|------------|----------------|-----------------|
| LOW | 3 (Execution) | 3 → 4 → 5 |
| MEDIUM | 2 (Planning) | 2 → 3 → 4 → 5 |
| HIGH | 1 (Discovery) | 1 → 2 → 3 → 4 → 5 |

**Transition table:**

┌────────────────┬─────────────┬─────────────┬────────────────┐
│ Current State  │ Event       │ Next State  │ Action         │
├────────────────┼─────────────┼─────────────┼────────────────┤
│ INIT           │ risk=HIGH   │ DISCOVERY   │ run_stage_1    │
│ INIT           │ risk=MEDIUM │ PLANNING    │ run_stage_2    │
│ INIT           │ risk=LOW    │ EXECUTION   │ run_stage_3    │
│ DISCOVERY      │ success     │ PLANNING    │ run_stage_2    │
│ DISCOVERY      │ failure     │ FAILED      │ report_error   │
│ PLANNING       │ success     │ EXECUTION   │ run_stage_3    │
│ PLANNING       │ failure     │ FAILED      │ report_error   │
│ EXECUTION      │ preflight_fail │ FAILED   │ exit(4)        │
│ EXECUTION      │ success     │ VERIFICATION│ run_stage_4    │
│ EXECUTION      │ failure     │ FAILED      │ report_error   │
│ VERIFICATION   │ approved    │ SHIP        │ run_stage_5    │
│ VERIFICATION   │ rejected,n<2│ EXECUTION   │ run_stage_3    │
│ VERIFICATION   │ rejected,n=2│ FAILED      │ exit(2)        │
│ SHIP           │ success     │ DONE        │ report_success │
│ SHIP           │ skip        │ DONE        │ report_success │
│ SHIP           │ failure     │ FAILED      │ report_error   │
└────────────────┴─────────────┴─────────────┴────────────────┘

### C. Data Contract

**StageResult schema:**

json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["stage", "status", "started_at", "ended_at"],
  "properties": {
    "stage": {
      "type": "string",
      "enum": ["discovery", "planning", "execution", "verification", "ship"]
    },
    "status": {
      "type": "string",
      "enum": ["pass", "fail", "skip"]
    },
    "started_at": {
      "type": "string",
      "format": "date-time"
    },
    "ended_at": {
      "type": "string",
      "format": "date-time"
    },
    "session_id": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "output": {
      "type": "string"
    },
    "error": {
      "type": "string"
    },
    "iteration": {
      "type": "integer",
      "minimum": 0,
      "maximum": 2
    },
    "tokens_estimated": {
      "type": "integer"
    }
  }
}

**PipelineResult schema:**

json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["version", "task", "risk", "status", "stages", "metrics"],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0.0"
    },
    "task": {
      "type": "string"
    },
    "risk": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "stages": {
      "type": "array",
      "items": { "$ref": "#/$defs/StageResult" }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "total_time_seconds": { "type": "number" },
        "total_tokens_estimated": { "type": "integer" },
        "verification_iterations": { "type": "integer" },
        "stages_executed": { "type": "integer" },
        "stages_skipped": { "type": "integer" }
      }
    }
  }
}

**Concrete JSON example:**

json
{
  "version": "1.0.0",
  "task": "Add health endpoint to user-service",
  "risk": "low",
  "status": "success",
  "stages": [
    {
      "stage": "execution",
      "status": "pass",
      "started_at": "2026-02-16T18:00:00Z",
      "ended_at": "2026-02-16T18:02:30Z",
      "session_id": "abc123",
      "model": "swe-1-5",
      "output": "Added /health endpoint...",
      "iteration": 0,
      "tokens_estimated": 1200
    },
    {
      "stage": "verification",
      "status": "pass",
      "started_at": "2026-02-16T18:02:31Z",
      "ended_at": "2026-02-16T18:03:45Z",
      "session_id": "def456",
      "model": "gpt-5.3-codex",
      "output": "{\"approved\": true, \"issues\": []}",
      "iteration": 1,
      "tokens_estimated": 800
    },
    {
      "stage": "ship",
      "status": "skip",
      "started_at": "2026-02-16T18:03:46Z",
      "ended_at": "2026-02-16T18:03:46Z"
    }
  ],
  "metrics": {
    "total_time_seconds": 226,
    "total_tokens_estimated": 2000,
    "verification_iterations": 1,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

**Idempotency mechanism:**

- Each pipeline run generates a unique run_id (UUID v4)
- State persisted to .droid/pipeline_state_{run_id}.json
- Resume via --session-id reloads state and continues from last successful stage

---

## 4. Golden Paths (2 Required)

### Golden Path 1: LOW Risk Task (Typo Fix)

**Command:**
bash
python scripts/pipeline_runner.py run "Fix typo in README.md: change 'teh' to 'the'" --json

**Expected stdout:**
json
{
  "version": "1.0.0",
  "task": "Fix typo in README.md: change 'teh' to 'the'",
  "risk": "low",
  "status": "success",
  "stages": [
    {"stage": "execution", "status": "pass", "model": "swe-1-5"},
    {"stage": "verification", "status": "pass", "model": "gpt-5.3-codex", "iteration": 1},
    {"stage": "ship", "status": "skip"}
  ],
  "metrics": {
    "total_time_seconds": 45,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

**Expected exit code:** 0

**Expected file side effect:**
- [README.md](cci:7://file:///opt/fabrik/README.md:0:0-0:0) modified (typo corrected)
- .droid/pipeline_state_<uuid>.json created

---

### Golden Path 2: HIGH Risk Task (New API Endpoint)

**Command:**
bash
python scripts/pipeline_runner.py run "Add authentication endpoint with JWT tokens" --verbose

**Expected stderr:**
[PIPELINE] 2026-02-16T18:00:00Z INFO: Assessing risk...
[PIPELINE] 2026-02-16T18:00:01Z INFO: Risk: HIGH (keywords: authentication, JWT)
[PIPELINE] 2026-02-16T18:00:01Z INFO: Starting Stage 1 DISCOVERY
[PIPELINE] 2026-02-16T18:01:30Z INFO: Stage 1 PASS (dual-model: gpt-5.3-codex + gemini-3-pro-preview)
[PIPELINE] 2026-02-16T18:01:31Z INFO: Starting Stage 2 PLANNING
[PIPELINE] 2026-02-16T18:03:00Z INFO: Stage 2 PASS (tri-model review complete)
[PIPELINE] 2026-02-16T18:03:01Z INFO: Running pre-flight gates...
[PIPELINE] 2026-02-16T18:03:05Z INFO: Pre-flight: ruff PASS, mypy PASS
[PIPELINE] 2026-02-16T18:03:06Z INFO: Starting Stage 3 EXECUTION
[PIPELINE] 2026-02-16T18:05:30Z INFO: Stage 3 PASS
[PIPELINE] 2026-02-16T18:05:31Z INFO: Starting Stage 4 VERIFICATION (iteration 1/2)
[PIPELINE] 2026-02-16T18:06:45Z INFO: Stage 4 PASS (approved)
[PIPELINE] 2026-02-16T18:06:46Z INFO: Starting Stage 5 SHIP
[PIPELINE] 2026-02-16T18:07:30Z INFO: Stage 5 PASS (CHANGELOG updated)

**Expected stdout:**
PIPELINE: Add authentication endpoint with JWT tokens
RISK: HIGH
STARTING: Stage 1

STAGE 1 DISCOVERY: PASS
STAGE 2 PLANNING: PASS
STAGE 3 EXECUTION: PASS
STAGE 4 VERIFICATION: PASS (iteration 1/2)
STAGE 5 SHIP: PASS

RESULT: SUCCESS
TIME: 450s
TOKENS: ~8500

**Expected exit code:** 0

**Expected file side effects:**
- src/api/auth.py created
- [CHANGELOG.md](cci:7://file:///opt/fabrik/CHANGELOG.md:0:0-0:0) updated
- .droid/pipeline_state_<uuid>.json created

---

## 5. Failure Matrix (Minimum 5 Cases)

| # | Failure Condition | Detection Mechanism | System Response | Retry Behavior | Exit Code | Rollback |
|---|-------------------|---------------------|-----------------|----------------|-----------|----------|
| 1 | **Pre-flight gate fails (ruff error)** | [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) returns (False, report) | Print report to stderr, abort pipeline | No retry | 4 | None |
| 2 | **Verification rejected twice** | iteration == 2 AND "approved": false | Print "Retry exhausted, escalate to human" | No further retry | 2 | Code reverted to pre-Stage-3 state via git |
| 3 | **Model not available** | droid exec returns error containing "model not found" | Print available models, suggest alternative | No retry | 3 | None |
| 4 | **Session ID invalid** | droid exec --session-id X returns "session not found" | Start new session, log warning | Auto-recover with new session | Continue | None |
| 5 | **Stage 1 dual-model timeout** | [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) hangs >300s | Kill subprocess, return partial result | No retry | 1 | None |
| 6 | **Risk assessment fails (empty task)** | assess_risk("") raises ValueError | Print "Task description required" | No retry | 5 | None |
| 7 | **mypy not installed** | FileNotFoundError in [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | Print "mypy not installed - required tool missing" | No retry | 4 | None |

---

## 6. Deterministic Gate Definition

**DONE WHEN verification command:**

bash
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py run "Test task" --dry-run && \
python -c "from scripts.pipeline_runner import assess_risk, RiskLevel; assert assess_risk('Fix typo') == RiskLevel.LOW" && \
python -c "from scripts.pipeline_runner import run_stage_1_discovery; help(run_stage_1_discovery)" && \
pytest tests/test_pipeline_runner.py -x && \
echo "GATE PASS"

**Expected PASS output:**

usage: pipeline_runner.py [-h] [--version] {run,stage} ...
...
PIPELINE: Test task
RISK: low
DRY-RUN: Would execute stages 3, 4, 5
RESULT: DRY-RUN SUCCESS
...
GATE PASS

**Expected FAIL output (any of):**

Error: No module named 'scripts.pipeline_runner'
AssertionError: assess_risk('Fix typo') != RiskLevel.LOW
pytest: FAILED tests/test_pipeline_runner.py

**CI validation hook:**

Add to [.github/workflows/droid-review.yml](cci:7://file:///opt/fabrik/.github/workflows/droid-review.yml:0:0-0:0):

yaml
- name: Verify GAP-09 Pipeline Runner
  run: |
    python scripts/pipeline_runner.py --help
    python scripts/pipeline_runner.py run "CI test" --dry-run

---

## 7. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **READ-ONLY** — imports run_* functions |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **READ-ONLY** — reads stage model configs |
| [.droid/](cci:9://file:///opt/fabrik/.droid:0:0-0:0) directory | **WRITE** — creates pipeline_state_*.json |
| [.droid_token_usage.jsonl](cci:7://file:///opt/fabrik/scripts/.droid_token_usage.jsonl:0:0-0:0) | **APPEND** — logs token estimates |

### Explicitly NOT Changed

| Component | Reason |
|-----------|--------|
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | All required functions already exist and wired |
| [scripts/droid_models.py](cci:7://file:///opt/fabrik/scripts/droid_models.py:0:0-0:0) | Model resolution unchanged |
| [scripts/droid_session.py](cci:7://file:///opt/fabrik/scripts/droid_session.py:0:0-0:0) | Session management unchanged |
| [.github/workflows/](cci:9://file:///opt/fabrik/.github/workflows:0:0-0:0) | CI changes deferred (separate GAP) |
| [src/](cci:9://file:///opt/fabrik/src:0:0-0:0) | No source code changes |

### Duplication Avoidance

| Function | Source | Reuse Strategy |
|----------|--------|----------------|
| [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) | droid_core.py:1224 | Import and call directly |
| [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5) | droid_core.py:1298 | Import and call directly |
| [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | droid_core.py:1488 | Import and call directly |
| [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import and call directly |
| [TaskType](cci:2://file:///opt/fabrik/scripts/droid_core.py:126:0-144:61) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import enum |
| [TaskResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:147:0-157:33) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import dataclass |
| TOOL_CONFIGS | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import dict |

**No logic duplication.** pipeline_runner.py is a pure orchestrator that chains existing validated functions.

---

## 8. Summary

This spec transforms GAP-09 into a deterministic implementation plan with:

- **2 files to CREATE**: scripts/pipeline_runner.py, tests/test_pipeline_runner.py
- **0 files to MODIFY** (except GAP-09 status)
- **5 exit codes** defined with exact meanings
- **6-stage state machine** with explicit transition rules
- **JSON schemas** for StageResult and PipelineResult
- **2 golden paths** with exact expected outputs
- **7 failure cases** with detection and response

**All required sections are complete.** The spec is ready for Mode 3 (Build) execution.

## Response:
Thought for 13s

Traycer.ai is plausibly aligned with the specific failure modes you listed, but only for the parts it explicitly targets: **spec anchoring + codebase-aware planning + post-implementation verification against the plan**.

What Traycer claims to do that matches your pain points
-------------------------------------------------------

### 1) “AI coder forgets context / overlooks written rules”

Traycer’s core pitch is **spec-driven development**: you turn intent into structured “Artifacts” (specs), then hand off to coding agents, reducing drift. [Traycer+1](https://docs.traycer.ai/?utm_source=chatgpt.com)  
It also advertises **Phases Mode** to maintain context across multi-step work. [Traycer+1](https://docs.traycer.ai/?utm_source=chatgpt.com)

**Implication (grounded):** If your rules are embedded in the Artifact/spec and reused across phases, you get a stronger “anchor” than a freeform chat prompt. That should reduce rule-skipping _when the coding agent follows the handed-off plan_.

### 2) “Creates different UI modules even in the same page/module”

Traycer says it generates **file-level plans with symbol references** and codebase analysis. [Traycer+1](https://docs.traycer.ai/tasks/plan?utm_source=chatgpt.com)  
**Implication:** When the plan explicitly references existing components/symbols, it can steer the agent toward reusing existing UI modules instead of inventing new ones—_if you enforce “modify existing component X” in the plan_.

### 3) “Creates duplicate code / duplicate DB fields”

Traycer claims it **scans your codebase to verify AI-generated changes and apply course corrections** before they reach production. [Traycer+1](https://traycer.ai/?utm_source=chatgpt.com)  
It also has a “Verification” step that compares implementation vs plan and produces review comments categorized by severity. [Traycer+1](https://docs.traycer.ai/tasks/plan?utm_source=chatgpt.com)  
**Implication:** This can catch some duplication if the plan says “extend existing model/table/field” and verification checks deviations. (It’s not a guarantee against duplicates unless the verification heuristics explicitly detect them; Traycer doesn’t publicly specify exact duplicate-detection rules.)

### 4) “Requires continuous reviews by other AIs/humans”

Traycer’s workflow is explicitly “Plan → Execute in agent → Verify,” intended to reduce that back-and-forth. [Traycer+1](https://traycer.ai/?utm_source=chatgpt.com)

What Traycer will not automatically fix (based on public info)
--------------------------------------------------------------

*   It does not claim to replace **repo-level enforcement** (pre-commit, CI, schema migration checks, duplicate detection tools). Traycer verification helps, but hard guarantees come from your existing GAP-01/GAP-08 style gates (jscpd, tests, linters) and CI rules.
*   If your “rules” are vague, Traycer won’t magically make them precise. You still need spec-level constraints (like your GAP-09 spec you generated).

Security / privacy considerations you should validate
-----------------------------------------------------

Traycer docs state organizations have “privacy mode” and claim code is “streamed, never uploaded.” [Traycer+1](https://docs.traycer.ai/account/organizations?utm_source=chatgpt.com)  
Treat this as a vendor claim until you confirm it fits your risk requirements (especially for proprietary repos).

Cost / friction reality check
-----------------------------

Traycer uses “artifact slots” with tiered limits and recharge rates (Free/Lite/Pro/Pro+). [Traycer+1](https://docs.traycer.ai/account/pricing?utm_source=chatgpt.com)  
This matters if you plan to run many small tasks per day.

Recommendation: run a controlled A/B test in 60–90 minutes
----------------------------------------------------------

Do this on a task that reliably triggers your pain points (UI consistency + duplicate risk):

1.  Pick a medium task that normally causes drift (e.g., “add a settings panel using existing components; no new UI module; no new DB fields; reuse X model”).
2.  Run it **without Traycer** (your current best prompt + gates).
3.  Run it **with Traycer Plan + Verify**:
    *   Put your constraints in the Artifact as **non-negotiables** (“MODIFY existing component `<path>`; do not create new `<component>`; DB: reuse field `<name>`; fail if new field added”).
    *   After agent execution, use Traycer verification and compare the number/type of issues caught. [Traycer+1](https://docs.traycer.ai/tasks/plan?utm_source=chatgpt.com)
4.  Score both runs on:
    *   of duplicated components/files introduced
        =========================================
    *   of rule violations
        ==================
    *   of review cycles to reach merge-ready
        =====================================
    *   final diff size

If Traycer reduces review cycles and prevents drift materially on this test, it’s likely worth integrating into your GAP-09 pipeline as the “verification lens” (alongside CI gates).

Quick evaluation of Opus’s GAP-09 spec you pasted
-------------------------------------------------

That plan is **not shallow**: it includes CLI contract, state machine, JSON schemas, gates, failure matrix, and a minimal CREATE/MODIFY set. That is exactly the kind of structure Traycer claims to produce and verify against. [Traycer+1](https://docs.traycer.ai/?utm_source=chatgpt.com)

If you want to decide “Traycer yes/no” quickly: run the A/B test above and paste both diffs + review notes; I’ll score them against the rubric.

## Prompt:
reevaluate opus answer do you think your prompt worked fine

---

# GAP-09 Pipeline Orchestrator — Spec-Level Implementation Plan

**Version:** 1.0.0  
**Date:** 2026-02-16  
**Status:** SPEC (not implementation)

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

/opt/fabrik/
├── scripts/
│   ├── droid_core.py          # Core execution functions
│   ├── droid_models.py        # Model resolution
│   ├── droid_session.py       # Session management
│   ├── process_monitor.py     # Process tracking
│   ├── enforcement/           # Validation scripts
│   │   └── validate_conventions.py
│   └── droid/                  # Batch scripts
├── config/
│   └── models.yaml            # Model configuration
├── tests/
│   ├── test_droid_core.py     # Existing droid tests
│   └── orchestrator/          # Orchestrator tests exist
├── .github/workflows/
│   ├── daily-maintenance.yml
│   └── droid-review.yml
└── docs/development/plans/
    └── 2026-02-16-plan-gap09-pipeline-orchestrator.md

### B. GAP-09 Integration Points

| Component | Status | Path | Notes |
|-----------|--------|------|-------|
| [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1224 | Returns [MultiModelResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:1152:0-1159:43) |
| [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1298 | max_review_iterations param |
| [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1488 | Returns tuple[bool, str] |
| [run_parallel_models()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1162:0-1220:18) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1163 | Returns dict[str, TaskResult] |
| [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Core execution |
| [TaskType](cci:2://file:///opt/fabrik/scripts/droid_core.py:126:0-144:61) enum | **FOUND** | @/opt/fabrik/scripts/droid_core.py | 11 task types |
| [TaskResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:147:0-157:33) dataclass | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Standard result |
| [MultiModelResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:1152:0-1159:43) dataclass | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1155 | Multi-model result |
| TOOL_CONFIGS dict | **FOUND** | @/opt/fabrik/scripts/droid_core.py | Model assignments |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **FOUND** | @/opt/fabrik/config/models.yaml | Stage model config |
| scripts/pipeline_runner.py | **NOT FOUND** | — | **CREATE required** |
| tests/test_pipeline_runner.py | **NOT FOUND** | — | **CREATE required** |
| Token tracking utility | **FOUND** | @/opt/fabrik/scripts/.droid_token_usage.jsonl | Append-only log |
| CI workflow trigger | **FOUND** | @/opt/fabrik/.github/workflows/droid-review.yml | Existing pattern |

### C. Blockers & Minimal Fixes

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|-------------|--------------|
| scripts/pipeline_runner.py does not exist | **CREATE** new file (GAP-09 scope) | N/A — required |
| tests/test_pipeline_runner.py does not exist | **CREATE** minimal unit tests | Skip tests (not recommended) |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| scripts/pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN: "scripts/pipeline_runner.py exists" | — | **L** (~400 lines) |
| tests/test_pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN: "Integration test passes" | — | **M** (~150 lines) |
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **VERIFY** | Confirm multi-model functions exist and callable | All existing code | **0** |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **VERIFY** | Confirm stage model configs present | All existing config | **0** |
| [docs/development/plans/2026-02-16-plan-gap09-pipeline-orchestrator.md](cci:7://file:///opt/fabrik/docs/development/plans/2026-02-16-plan-gap09-pipeline-orchestrator.md:0:0-0:0) | **MODIFY** | Update status to COMPLETE on success | Content except status | **S** (~2 lines) |

---

## 3. Interface & Contract Specification

### A. CLI Contract

**Command syntax:**

bash
python scripts/pipeline_runner.py <command> [options]

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| run | Execute full pipeline |
| stage | Execute single stage |
| --help | Show help |
| --version | Show version |

**Flags for run subcommand:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| TASK | positional | yes | — | Task description string |
| --dry-run | flag | no | false | Simulate without execution |
| --stage | choice | no | auto | Start at specific stage: discovery, planning, execution, verification, ship |
| --risk | choice | no | auto | Override risk level: low, medium, high |
| --session-id | string | no | — | Resume existing session |
| --cwd | path | no | . | Working directory |
| --json | flag | no | false | Output JSON instead of text |
| --verbose | flag | no | false | Verbose logging to stderr |

**Flags for stage subcommand:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| STAGE | positional | yes | — | Stage name: discovery, planning, execution, verification, ship |
| PROMPT | positional | yes | — | Stage prompt |
| --session-id | string | no | — | Session ID for continuity |
| --cwd | path | no | . | Working directory |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success — all stages passed |
| 1 | Stage failure — one stage failed after retries |
| 2 | Retry exhausted — MAX 2 re-verify iterations exceeded |
| 3 | Configuration error — missing model config, invalid flags |
| 4 | Pre-flight gate failure — ruff/mypy/pytest failed |
| 5 | Risk assessment failure — cannot assess task risk |
| 10 | Dry-run success — simulation completed |

**stdout format (default):**

PIPELINE: <task_summary>
RISK: <LOW|MEDIUM|HIGH>
STARTING: Stage <N>

STAGE 1 DISCOVERY: <PASS|SKIP>
STAGE 2 PLANNING: <PASS|SKIP>
STAGE 3 EXECUTION: <PASS|FAIL>
STAGE 4 VERIFICATION: <PASS|FAIL> (iteration <N>/2)
STAGE 5 SHIP: <PASS|SKIP>

RESULT: <SUCCESS|FAILURE>
TIME: <seconds>s
TOKENS: <estimated>

**stderr format:**

[PIPELINE] <timestamp> <level>: <message>

### B. State Machine Definition

**Valid stages:**

| Stage | ID | Entry Condition | Exit Condition |
|-------|----|-----------------|----------------|
| INIT | 0 | Pipeline started | Risk assessed |
| DISCOVERY | 1 | Risk == HIGH | MultiModelResult.merged_result not empty |
| PLANNING | 2 | Risk >= MEDIUM OR Stage 1 passed | Plan JSON valid |
| EXECUTION | 3 | Pre-flight gates pass | Code changes applied, no errors |
| VERIFICATION | 4 | Stage 3 passed | {"approved": true} OR iteration == 2 |
| SHIP | 5 | Stage 4 passed, docs affected | CHANGELOG updated |
| DONE | 6 | Final stage passed | — |
| FAILED | -1 | Any stage fails after retries | — |

**Stage transition rules:**

| From | To | Condition |
|------|----|-----------|
| INIT | DISCOVERY | risk == HIGH |
| INIT | PLANNING | risk == MEDIUM |
| INIT | EXECUTION | risk == LOW |
| DISCOVERY | PLANNING | Stage 1 success |
| PLANNING | EXECUTION | Stage 2 success |
| EXECUTION | VERIFICATION | Pre-flight pass AND Stage 3 success |
| VERIFICATION | SHIP | Stage 4 approved |
| VERIFICATION | EXECUTION | Stage 4 rejected AND iteration < 2 |
| VERIFICATION | FAILED | Stage 4 rejected AND iteration == 2 |
| SHIP | DONE | Stage 5 success OR no docs affected |
| Any | FAILED | Unrecoverable error |

**Retry logic:**

| Stage | Max Attempts | Backoff | Escalation |
|-------|--------------|---------|------------|
| VERIFICATION | 2 | None | Exit code 2, human escalation |
| All others | 1 | None | Immediate failure |

**Risk routing behavior:**

| Risk Level | Starting Stage | Stages Executed |
|------------|----------------|-----------------|
| LOW | 3 (Execution) | 3 → 4 → 5 |
| MEDIUM | 2 (Planning) | 2 → 3 → 4 → 5 |
| HIGH | 1 (Discovery) | 1 → 2 → 3 → 4 → 5 |

**Transition table:**

┌────────────────┬─────────────┬─────────────┬────────────────┐
│ Current State  │ Event       │ Next State  │ Action         │
├────────────────┼─────────────┼─────────────┼────────────────┤
│ INIT           │ risk=HIGH   │ DISCOVERY   │ run_stage_1    │
│ INIT           │ risk=MEDIUM │ PLANNING    │ run_stage_2    │
│ INIT           │ risk=LOW    │ EXECUTION   │ run_stage_3    │
│ DISCOVERY      │ success     │ PLANNING    │ run_stage_2    │
│ DISCOVERY      │ failure     │ FAILED      │ report_error   │
│ PLANNING       │ success     │ EXECUTION   │ run_stage_3    │
│ PLANNING       │ failure     │ FAILED      │ report_error   │
│ EXECUTION      │ preflight_fail │ FAILED   │ exit(4)        │
│ EXECUTION      │ success     │ VERIFICATION│ run_stage_4    │
│ EXECUTION      │ failure     │ FAILED      │ report_error   │
│ VERIFICATION   │ approved    │ SHIP        │ run_stage_5    │
│ VERIFICATION   │ rejected,n<2│ EXECUTION   │ run_stage_3    │
│ VERIFICATION   │ rejected,n=2│ FAILED      │ exit(2)        │
│ SHIP           │ success     │ DONE        │ report_success │
│ SHIP           │ skip        │ DONE        │ report_success │
│ SHIP           │ failure     │ FAILED      │ report_error   │
└────────────────┴─────────────┴─────────────┴────────────────┘

### C. Data Contract

**StageResult schema:**

json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["stage", "status", "started_at", "ended_at"],
  "properties": {
    "stage": {
      "type": "string",
      "enum": ["discovery", "planning", "execution", "verification", "ship"]
    },
    "status": {
      "type": "string",
      "enum": ["pass", "fail", "skip"]
    },
    "started_at": {
      "type": "string",
      "format": "date-time"
    },
    "ended_at": {
      "type": "string",
      "format": "date-time"
    },
    "session_id": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "output": {
      "type": "string"
    },
    "error": {
      "type": "string"
    },
    "iteration": {
      "type": "integer",
      "minimum": 0,
      "maximum": 2
    },
    "tokens_estimated": {
      "type": "integer"
    }
  }
}

**PipelineResult schema:**

json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["version", "task", "risk", "status", "stages", "metrics"],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0.0"
    },
    "task": {
      "type": "string"
    },
    "risk": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "stages": {
      "type": "array",
      "items": { "$ref": "#/$defs/StageResult" }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "total_time_seconds": { "type": "number" },
        "total_tokens_estimated": { "type": "integer" },
        "verification_iterations": { "type": "integer" },
        "stages_executed": { "type": "integer" },
        "stages_skipped": { "type": "integer" }
      }
    }
  }
}

**Concrete JSON example:**

json
{
  "version": "1.0.0",
  "task": "Add health endpoint to user-service",
  "risk": "low",
  "status": "success",
  "stages": [
    {
      "stage": "execution",
      "status": "pass",
      "started_at": "2026-02-16T18:00:00Z",
      "ended_at": "2026-02-16T18:02:30Z",
      "session_id": "abc123",
      "model": "swe-1-5",
      "output": "Added /health endpoint...",
      "iteration": 0,
      "tokens_estimated": 1200
    },
    {
      "stage": "verification",
      "status": "pass",
      "started_at": "2026-02-16T18:02:31Z",
      "ended_at": "2026-02-16T18:03:45Z",
      "session_id": "def456",
      "model": "gpt-5.3-codex",
      "output": "{\"approved\": true, \"issues\": []}",
      "iteration": 1,
      "tokens_estimated": 800
    },
    {
      "stage": "ship",
      "status": "skip",
      "started_at": "2026-02-16T18:03:46Z",
      "ended_at": "2026-02-16T18:03:46Z"
    }
  ],
  "metrics": {
    "total_time_seconds": 226,
    "total_tokens_estimated": 2000,
    "verification_iterations": 1,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

**Idempotency mechanism:**

- Each pipeline run generates a unique run_id (UUID v4)
- State persisted to .droid/pipeline_state_{run_id}.json
- Resume via --session-id reloads state and continues from last successful stage

---

## 4. Golden Paths (2 Required)

### Golden Path 1: LOW Risk Task (Typo Fix)

**Command:**
bash
python scripts/pipeline_runner.py run "Fix typo in README.md: change 'teh' to 'the'" --json

**Expected stdout:**
json
{
  "version": "1.0.0",
  "task": "Fix typo in README.md: change 'teh' to 'the'",
  "risk": "low",
  "status": "success",
  "stages": [
    {"stage": "execution", "status": "pass", "model": "swe-1-5"},
    {"stage": "verification", "status": "pass", "model": "gpt-5.3-codex", "iteration": 1},
    {"stage": "ship", "status": "skip"}
  ],
  "metrics": {
    "total_time_seconds": 45,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

**Expected exit code:** 0

**Expected file side effect:**
- [README.md](cci:7://file:///opt/fabrik/README.md:0:0-0:0) modified (typo corrected)
- .droid/pipeline_state_<uuid>.json created

---

### Golden Path 2: HIGH Risk Task (New API Endpoint)

**Command:**
bash
python scripts/pipeline_runner.py run "Add authentication endpoint with JWT tokens" --verbose

**Expected stderr:**
[PIPELINE] 2026-02-16T18:00:00Z INFO: Assessing risk...
[PIPELINE] 2026-02-16T18:00:01Z INFO: Risk: HIGH (keywords: authentication, JWT)
[PIPELINE] 2026-02-16T18:00:01Z INFO: Starting Stage 1 DISCOVERY
[PIPELINE] 2026-02-16T18:01:30Z INFO: Stage 1 PASS (dual-model: gpt-5.3-codex + gemini-3-pro-preview)
[PIPELINE] 2026-02-16T18:01:31Z INFO: Starting Stage 2 PLANNING
[PIPELINE] 2026-02-16T18:03:00Z INFO: Stage 2 PASS (tri-model review complete)
[PIPELINE] 2026-02-16T18:03:01Z INFO: Running pre-flight gates...
[PIPELINE] 2026-02-16T18:03:05Z INFO: Pre-flight: ruff PASS, mypy PASS
[PIPELINE] 2026-02-16T18:03:06Z INFO: Starting Stage 3 EXECUTION
[PIPELINE] 2026-02-16T18:05:30Z INFO: Stage 3 PASS
[PIPELINE] 2026-02-16T18:05:31Z INFO: Starting Stage 4 VERIFICATION (iteration 1/2)
[PIPELINE] 2026-02-16T18:06:45Z INFO: Stage 4 PASS (approved)
[PIPELINE] 2026-02-16T18:06:46Z INFO: Starting Stage 5 SHIP
[PIPELINE] 2026-02-16T18:07:30Z INFO: Stage 5 PASS (CHANGELOG updated)

**Expected stdout:**
PIPELINE: Add authentication endpoint with JWT tokens
RISK: HIGH
STARTING: Stage 1

STAGE 1 DISCOVERY: PASS
STAGE 2 PLANNING: PASS
STAGE 3 EXECUTION: PASS
STAGE 4 VERIFICATION: PASS (iteration 1/2)
STAGE 5 SHIP: PASS

RESULT: SUCCESS
TIME: 450s
TOKENS: ~8500

**Expected exit code:** 0

**Expected file side effects:**
- src/api/auth.py created
- [CHANGELOG.md](cci:7://file:///opt/fabrik/CHANGELOG.md:0:0-0:0) updated
- .droid/pipeline_state_<uuid>.json created

---

## 5. Failure Matrix (Minimum 5 Cases)

| # | Failure Condition | Detection Mechanism | System Response | Retry Behavior | Exit Code | Rollback |
|---|-------------------|---------------------|-----------------|----------------|-----------|----------|
| 1 | **Pre-flight gate fails (ruff error)** | [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) returns (False, report) | Print report to stderr, abort pipeline | No retry | 4 | None |
| 2 | **Verification rejected twice** | iteration == 2 AND "approved": false | Print "Retry exhausted, escalate to human" | No further retry | 2 | Code reverted to pre-Stage-3 state via git |
| 3 | **Model not available** | droid exec returns error containing "model not found" | Print available models, suggest alternative | No retry | 3 | None |
| 4 | **Session ID invalid** | droid exec --session-id X returns "session not found" | Start new session, log warning | Auto-recover with new session | Continue | None |
| 5 | **Stage 1 dual-model timeout** | [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) hangs >300s | Kill subprocess, return partial result | No retry | 1 | None |
| 6 | **Risk assessment fails (empty task)** | assess_risk("") raises ValueError | Print "Task description required" | No retry | 5 | None |
| 7 | **mypy not installed** | FileNotFoundError in [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | Print "mypy not installed - required tool missing" | No retry | 4 | None |

---

## 6. Deterministic Gate Definition

**DONE WHEN verification command:**

bash
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py run "Test task" --dry-run && \
python -c "from scripts.pipeline_runner import assess_risk, RiskLevel; assert assess_risk('Fix typo') == RiskLevel.LOW" && \
python -c "from scripts.pipeline_runner import run_stage_1_discovery; help(run_stage_1_discovery)" && \
pytest tests/test_pipeline_runner.py -x && \
echo "GATE PASS"

**Expected PASS output:**

usage: pipeline_runner.py [-h] [--version] {run,stage} ...
...
PIPELINE: Test task
RISK: low
DRY-RUN: Would execute stages 3, 4, 5
RESULT: DRY-RUN SUCCESS
...
GATE PASS

**Expected FAIL output (any of):**

Error: No module named 'scripts.pipeline_runner'
AssertionError: assess_risk('Fix typo') != RiskLevel.LOW
pytest: FAILED tests/test_pipeline_runner.py

**CI validation hook:**

Add to [.github/workflows/droid-review.yml](cci:7://file:///opt/fabrik/.github/workflows/droid-review.yml:0:0-0:0):

yaml
- name: Verify GAP-09 Pipeline Runner
  run: |
    python scripts/pipeline_runner.py --help
    python scripts/pipeline_runner.py run "CI test" --dry-run

---

## 7. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **READ-ONLY** — imports run_* functions |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **READ-ONLY** — reads stage model configs |
| [.droid/](cci:9://file:///opt/fabrik/.droid:0:0-0:0) directory | **WRITE** — creates pipeline_state_*.json |
| [.droid_token_usage.jsonl](cci:7://file:///opt/fabrik/scripts/.droid_token_usage.jsonl:0:0-0:0) | **APPEND** — logs token estimates |

### Explicitly NOT Changed

| Component | Reason |
|-----------|--------|
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | All required functions already exist and wired |
| [scripts/droid_models.py](cci:7://file:///opt/fabrik/scripts/droid_models.py:0:0-0:0) | Model resolution unchanged |
| [scripts/droid_session.py](cci:7://file:///opt/fabrik/scripts/droid_session.py:0:0-0:0) | Session management unchanged |
| [.github/workflows/](cci:9://file:///opt/fabrik/.github/workflows:0:0-0:0) | CI changes deferred (separate GAP) |
| [src/](cci:9://file:///opt/fabrik/src:0:0-0:0) | No source code changes |

### Duplication Avoidance

| Function | Source | Reuse Strategy |
|----------|--------|----------------|
| [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) | droid_core.py:1224 | Import and call directly |
| [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5) | droid_core.py:1298 | Import and call directly |
| [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | droid_core.py:1488 | Import and call directly |
| [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import and call directly |
| [TaskType](cci:2://file:///opt/fabrik/scripts/droid_core.py:126:0-144:61) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import enum |
| [TaskResult](cci:2://file:///opt/fabrik/scripts/droid_core.py:147:0-157:33) | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import dataclass |
| TOOL_CONFIGS | [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | Import dict |

**No logic duplication.** pipeline_runner.py is a pure orchestrator that chains existing validated functions.

---

## 8. Summary

This spec transforms GAP-09 into a deterministic implementation plan with:

- **2 files to CREATE**: scripts/pipeline_runner.py, tests/test_pipeline_runner.py
- **0 files to MODIFY** (except GAP-09 status)
- **5 exit codes** defined with exact meanings
- **6-stage state machine** with explicit transition rules
- **JSON schemas** for StageResult and PipelineResult
- **2 golden paths** with exact expected outputs
- **7 failure cases** with detection and response

**All required sections are complete.** The spec is ready for Mode 3 (Build) execution.

## Response:
Thought for 39s

Partly. Your prompt succeeded at forcing a **spec-shaped output**, but Opus’s answer has several **drifts and unverifiable insertions** relative to the actual GAP-09 document.

What worked (prompt effectiveness)
----------------------------------

Opus produced the key “spec-level” sections your prompt demanded: CLI contract, state machine, JSON contracts, golden paths, failure matrix, and a gate. That aligns with GAP-09’s intent to turn the pipeline into an explicit orchestrator that reuses `droid_core.py` functions and enforces the re-verify cap.

2026-02-16-plan-gap09-pipeline-…

It also matched core routing logic (LOW skips stages 1/2; MEDIUM starts at stage 2; HIGH starts at stage 1).

2026-02-16-plan-gap09-pipeline-…

Where the answer is weak / incorrect (relative to GAP-09)
---------------------------------------------------------

### 1) Canonical gate drift (important)

GAP-09 defines a very specific **canonical gate**:

*   `python scripts/pipeline_runner.py --help && python scripts/pipeline_runner.py --dry-run "Test task" && echo "PASS"`
    2026-02-16-plan-gap09-pipeline-…

Opus replaced it with a much larger gate (imports, pytest, asserts). That may be useful, but it no longer matches the plan’s canonical gate and can create extra friction.

2026-02-16-plan-gap09-pipeline-…

### 2) Out-of-scope violation: CI integration suggestion

GAP-09 explicitly states CI/CD integration is out of scope.

2026-02-16-plan-gap09-pipeline-…

Opus proposed adding steps to a GitHub workflow anyway. That’s a spec violation.

### 3) Pre-flight placement ambiguity

DONE WHEN requires: “Pre-flight gates run before each verification.”

2026-02-16-plan-gap09-pipeline-…

In the GAP steps, pre-flight gates are emphasized as part of the execution flow and “must pass before AI verification proceeds” (i.e., right before Stage 4).

2026-02-16-plan-gap09-pipeline-…

Opus places pre-flight gating as an entry condition into EXECUTION and in the transition table, but does not clearly specify it runs immediately before Stage 4 for every run.

### 4) Session management incomplete vs the plan’s dataflow

GAP-09’s dataflow specifies multiple session IDs (stage1/2 share, stage3 new, stage4 separate, stage5 docs-only).

2026-02-16-plan-gap09-pipeline-…

Opus mentions `--session-id` and “separate for verification,” but doesn’t lock the explicit multi-session structure.

### 5) “Repo grounding” may be fabricated (cannot verify from GAP-09)

The repo tree and exact function line numbers are not in GAP-09; they could be true if Opus actually scanned your repo, but from what you provided here, there’s no way to verify. Treat that section as untrusted unless you confirm those paths exist.

Verdict
-------

*   **Prompt worked** at forcing a deeper plan format.
*   **Opus output is not fully compliant** with GAP-09 due to (1) canonical gate drift, (2) CI out-of-scope violation, and (3) incomplete enforcement of the plan’s session/dataflow + pre-flight-before-verification rule.
    2026-02-16-plan-gap09-pipeline-…
    2026-02-16-plan-gap09-pipeline-…
    2026-02-16-plan-gap09-pipeline-…

What to tell Opus next (minimal fix prompt)
-------------------------------------------

Send this to Opus:

1.  “Revise the spec to be **GAP-09 compliant**:
    *   Use the **canonical gate exactly as written** in GAP-09 (no expansion).
    2026-02-16-plan-gap09-pipeline-…
*   Remove all CI/workflow changes (explicitly out of scope).
    2026-02-16-plan-gap09-pipeline-…
*   Make pre-flight gates run **immediately before Stage 4 Verification** on every run (fail-closed).
    2026-02-16-plan-gap09-pipeline-…
*   Make session IDs match the dataflow: session\_id\_1 for stages 1–2, session\_id\_2 for stage 3, session\_id\_3 separate for stage 4, session\_id\_4 for docs stage 5.
    2026-02-16-plan-gap09-pipeline-…
*   Add the required step-reporting format as a compliance requirement for builders/verifiers.”
    2026-02-16-plan-gap09-pipeline-…

That will tighten the plan without increasing scope.

## Prompt:
Stage	Purpose	Models	Pattern
1 - Discovery	Spec creation	GPT-5.3-Codex + Gemini Pro	Dual discussion
2 - Planning	Phased plan	Sonnet + Flash (or Traycer) → Codex review	Plan + review
3 - Execution	Build	SWE-1.5	Single model
4 - Verification	Audit	GPT-5.3-Codex	Independent
5 - Ship	Docs	Haiku 4.5	Cheap/fast

i am planning to use this approach but looks like my planning specs are not enough, what should i add?

## Response:
Thought for 18s

Add **spec “anchors” that force repo-awareness + prevent divergence**. Right now your stage model lineup is fine; the missing piece is _what the Stage-2 output must contain so Stage-3 cannot improvise._ Your own principles doc explicitly frames the fix as a **pipeline problem** (explicit state + roles + automated gates), not “better prompting.”

Optimizing Workflows Across AI …

What to add to your planning specs (Stage-2 deliverable upgrades)
-----------------------------------------------------------------

### 1) “Repo-awareness” section (mandatory)

Require the planner to prove it searched the existing code before proposing anything (to prevent new UI modules / duplicate helpers). Your principles doc calls this out: indexing gaps + insufficient introspection → duplicates; mitigation is an explicit search/snapshot step before writing.

Optimizing Workflows Across AI …

**Add addition:** “Existing implementation(s) found” with file paths + symbol names + why they will be reused.

### 2) File-impact manifest (CREATE/MODIFY/DELETE) + “do not touch” list

A single table that locks down where changes are allowed. This is the “single canonical plan artifact” idea.

Optimizing Workflows Across AI …

### 3) Contracts: UI + API + DB schemas (machine-checkable)

For each touched interface:

*   API routes (method/path/request/response)
*   DB fields (name/type/nullability/index/migration rule)
*   UI components (existing component to reuse, props, state ownership)  
    This turns “don’t create a different UI module” into a spec requirement, not a hope. (Same logic as “make state explicit and machine-readable.”)
    Optimizing Workflows Across AI …

### 4) Invariants (hard rules) + duplication prevention gates

Two layers:

*   **Invariants:** “Must reuse `<ComponentX>`; no new table/field; no new module under `/ui/*`” etc.
*   **Automated gates:** duplication detection + static analysis + tests. Your doc recommends exactly that gate stack.
    Optimizing Workflows Across AI …
    Optimizing Workflows Across AI …

### 5) “Semantic presence checks” for reuse (not just text search)

Require LSP “find references/definitions” or Semgrep patterns to verify reuse (“do not re-implement X”).

Optimizing Workflows Across AI …

### 6) Acceptance tests as commands (golden path)

Planner must define:

*   commands to run
*   expected outputs
*   pass/fail criteria  
    This aligns with your existing GAP style: gates + evidence required.
    2026-02-16-plan-gap01-duplicate…

### 7) Failure modes + rollback plan

At least 5 predictable failures and what to do (including “how to revert”). This reduces endless review loops.

### 8) Strict step reporting format + session discipline

Make every phase output a structured report: changed files + gate output + verifier result; and enforce separate verifier session for independence.

2026-02-16-plan-gap01-duplicate…

2026-02-16-plan-gap01-duplicate…

* * *

Drop-in “Stage-2 Plan Output Contract” (paste into your planning workflow)
--------------------------------------------------------------------------

Use this as the required format for the Stage-2 model:

1.  **Repo-awareness proof:** searches performed + existing files/symbols found + reuse decision.
2.  **File-impact manifest:** CREATE / MODIFY / DELETE + “do-not-touch” list.
3.  **Contracts:** API, DB, UI component reuse mapping (explicit).
4.  **Invariants:** hard “must/must-not” rules.
5.  **Gates:** commands (lint/tests/static/dup-detect) + pass criteria.
6.  **Golden path:** 1–2 end-to-end examples with expected outputs.
7.  **Failure matrix + rollback:** triggers, mitigations, revert steps.
8.  **Step report template:** changed files + gate output + verifier JSON + re-verify count.

* * *

Practical note on your model table
----------------------------------

Your model staging is consistent with the “roles + automated gates + verifier layer” pattern shown in your principles doc.

Optimizing Workflows Across AI …

The improvement is not swapping models—it’s enforcing the Stage-2 “output contract” above so Stage-3 cannot drift.

If you want, I can turn the contract into a **single copy/paste prompt** specifically for your Stage-2 planner (Sonnet/Flash/Traycer) that forces all eight sections with minimal tokens.

## Prompt:
ok turn the contract into a single copy/paste prompt specifically for your Stage-2 planner (Sonnet/Flash/Traycer) that forces all eight sections with minimal tokens.

## Response:
Below is the **minimal, strict, copy-paste prompt** for your **Stage-2 Planner (Sonnet / Flash / Traycer)**.

It enforces all 8 required sections, prevents drift, and keeps tokens tight.

* * *

STAGE-2 PLANNER SPEC CONTRACT (COPY/PASTE)
==========================================

You are Stage-2 (Planning).

You are NOT implementing code.  
You must produce a **deterministic, repo-grounded implementation spec** for the given task.

If any section is missing, incomplete, or vague, the plan is invalid.

No generic language (“integrate”, “handle”, “ensure”) without precise definition.

Keep output compact but complete.

* * *

INPUT
-----

Task:

```
<PASTE TASK HERE>
```

* * *

OUTPUT FORMAT (ALL SECTIONS REQUIRED)
=====================================

1\. Repo-Awareness Proof
------------------------

List:

*   Searches performed (exact patterns)
*   Existing files found (paths)
*   Existing symbols/components found
*   Reuse decision per item

If nothing found, write: `NOT FOUND` and justify why CREATE is required.

* * *

2\. File Impact Manifest
------------------------

Table:

Path | Action (CREATE/MODIFY/DELETE) | Reason | What will NOT change

Rules:

*   Default = MODIFY
*   CREATE only if no suitable existing location
*   Explicit “DO NOT TOUCH” list required

* * *

3\. Contracts (Machine-Checkable)
---------------------------------

Only define what is touched.

### A. API (if applicable)

*   Method
*   Path
*   Request schema
*   Response schema
*   Error codes

### B. DB (if applicable)

*   Table
*   Field
*   Type
*   Nullability
*   Index
*   Migration rule

Explicitly state:

*   “No new table”
*   or “New field allowed”

### C. UI (if applicable)

*   Existing component to reuse
*   Props added/changed
*   State owner
*   No new module under `<path>` (if enforced)

* * *

4\. Invariants (Hard Rules)
---------------------------

Bullet list:

*   Must reuse: <component/file>
*   Must NOT create: <module/table/field>
*   Must NOT duplicate: <logic name>
*   Must pass: <gate list>

These are non-negotiable.

* * *

5\. Gates (Deterministic Commands)
----------------------------------

List exact commands:

*   lint
*   type check
*   tests
*   duplicate detection
*   any task-specific checks

For each:  
PASS condition  
FAIL condition

* * *

6\. Golden Path (1–2 Only)
--------------------------

For each:

Command:  
Expected changed files:  
Expected output:  
Exit code:

* * *

7\. Failure Matrix (Minimum 5)
------------------------------

Failure | Detection | System Response | Rollback

Be specific.

* * *

8\. Step Report Template (For Stage-3 + Stage-4)
------------------------------------------------

Provide this exact reporting format:

```
STEP REPORT
Task:
Files changed:
Gates run:
Gate results:
Verifier result:
Re-verify count:
```

Verification must run in a separate session.

Max 2 re-verify cycles.

* * *

Additional Rules
================

*   No architecture redesign.
*   No new dependencies unless explicitly required.
*   No expanding scope.
*   No code samples.
*   Keep under 900 lines.

If any ambiguity exists, state it and stop.

* * *

END OF PROMPT
=============

* * *

This forces:

*   repo scanning
*   explicit reuse
*   file-level locking
*   contract definition
*   hard invariants
*   deterministic gates
*   structured reporting
*   verifier independence

If you want, I can now optimize this further for **token efficiency for Flash vs Sonnet vs Traycer**, since each behaves slightly differently under constraint-heavy prompts.

## Prompt:
---

# GAP-09 Pipeline Orchestrator — Spec-Level Implementation Plan (REVISED)

**Version:** 1.1.0  
**Date:** 2026-02-16  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-09 v1.0

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

/opt/fabrik/
├── scripts/
│   ├── droid_core.py          # Core execution functions
│   ├── droid_models.py        # Model resolution
│   ├── droid_session.py       # Session management
│   ├── process_monitor.py     # Process tracking
│   └── enforcement/           # Validation scripts
├── config/
│   └── models.yaml            # Model configuration
├── tests/
│   ├── test_droid_core.py     # Existing droid tests
│   └── orchestrator/          # Orchestrator tests exist
└── docs/development/plans/
    └── 2026-02-16-plan-gap09-pipeline-orchestrator.md

### B. GAP-09 Integration Points

| Component | Status | Path |
|-----------|--------|------|
| [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1224 |
| [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1298 |
| [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1488 |
| [run_parallel_models()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1162:0-1220:18) | **FOUND** | @/opt/fabrik/scripts/droid_core.py:1163 |
| [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) | **FOUND** | @/opt/fabrik/scripts/droid_core.py |
| scripts/pipeline_runner.py | **NOT FOUND** | **CREATE required** |
| tests/test_pipeline_runner.py | **NOT FOUND** | **CREATE required** |

### C. Blockers

| Blocker | Fix |
|---------|-----|
| scripts/pipeline_runner.py does not exist | **CREATE** (GAP-09 scope) |
| tests/test_pipeline_runner.py does not exist | **CREATE** (GAP-09 scope) |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| scripts/pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN | — | **L** |
| tests/test_pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN | — | **M** |
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **VERIFY** | Confirm functions exist | All code | **0** |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **VERIFY** | Confirm stage configs | All config | **0** |

**Explicitly NOT created/modified:**
- .github/workflows/* — OUT OF SCOPE per GAP-09
- Any CI/CD integration — OUT OF SCOPE per GAP-09

---

## 3. Interface & Contract Specification

### A. CLI Contract

**Command syntax:**

bash
python scripts/pipeline_runner.py <command> [options]

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| run | Execute full pipeline |
| stage | Execute single stage |
| --help | Show help |

**Flags for run:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| TASK | positional | yes | — | Task description |
| --dry-run | flag | no | false | Simulate without execution |
| --stage | choice | no | auto | Start stage: discovery, planning, execution, verification, ship |
| --risk | choice | no | auto | Override: low, medium, high |
| --cwd | path | no | . | Working directory |
| --json | flag | no | false | JSON output |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Stage failure |
| 2 | Retry exhausted (MAX 2 verification iterations) |
| 3 | Configuration error |
| 4 | Pre-flight gate failure |
| 5 | Risk assessment failure |

### B. State Machine Definition

**Session ID Allocation (per GAP-09 DATA FLOW):**

| Session | Stages | Purpose |
|---------|--------|---------|
| session_id_1 | Stage 1 + Stage 2 | Discovery → Planning continuity |
| session_id_2 | Stage 3 | Execution (new session for build) |
| session_id_3 | Stage 4 | Verification (SEPARATE for Verifier independence) |
| session_id_4 | Stage 5 | Documentation (docs only) |

**Stage transition table:**

┌────────────────┬─────────────────┬─────────────┬────────────────┬─────────────┐
│ Current State  │ Event           │ Next State  │ Action         │ Session     │
├────────────────┼─────────────────┼─────────────┼────────────────┼─────────────┤
│ INIT           │ risk=HIGH       │ DISCOVERY   │ run_stage_1    │ session_1   │
│ INIT           │ risk=MEDIUM     │ PLANNING    │ run_stage_2    │ session_1   │
│ INIT           │ risk=LOW        │ EXECUTION   │ run_stage_3    │ session_2   │
│ DISCOVERY      │ success         │ PLANNING    │ run_stage_2    │ session_1   │
│ DISCOVERY      │ failure         │ FAILED      │ report_error   │ —           │
│ PLANNING       │ success         │ EXECUTION   │ run_stage_3    │ session_2   │
│ PLANNING       │ failure         │ FAILED      │ report_error   │ —           │
│ EXECUTION      │ success         │ PRE_VERIFY  │ run_preflight  │ session_2   │
│ EXECUTION      │ failure         │ FAILED      │ report_error   │ —           │
│ PRE_VERIFY     │ gates_pass      │ VERIFICATION│ run_stage_4    │ session_3   │
│ PRE_VERIFY     │ gates_fail      │ FAILED      │ exit(4)        │ —           │
│ VERIFICATION   │ approved        │ SHIP        │ run_stage_5    │ session_4   │
│ VERIFICATION   │ rejected, n<2   │ EXECUTION   │ run_stage_3    │ session_2   │
│ VERIFICATION   │ rejected, n=2   │ FAILED      │ exit(2)        │ —           │
│ SHIP           │ success/skip    │ DONE        │ report_success │ session_4   │
│ SHIP           │ failure         │ FAILED      │ report_error   │ —           │
└────────────────┴─────────────────┴─────────────┴────────────────┴─────────────┘

**Pre-flight gates position (REVISED per GAP-09):**

Pre-flight gates run **immediately before Stage 4 Verification** on every pipeline run:

Stage 3 EXECUTION
       │
       ▼
┌─────────────────┐
│ PRE-FLIGHT      │  ◀── Run BEFORE verification, NOT before execution
│ GATES           │
│ ruff, mypy      │
│ FAIL-CLOSED     │
└────────┬────────┘
         │ gates_pass
         ▼
Stage 4 VERIFICATION

**Risk routing:**

| Risk Level | Starting Stage | Stages Executed |
|------------|----------------|-----------------|
| LOW | 3 (Execution) | 3 → preflight → 4 → 5 |
| MEDIUM | 2 (Planning) | 2 → 3 → preflight → 4 → 5 |
| HIGH | 1 (Discovery) | 1 → 2 → 3 → preflight → 4 → 5 |

### C. Data Contract

**StageResult schema:**

json
{
  "stage": "verification",
  "status": "pass",
  "started_at": "2026-02-16T18:02:31Z",
  "ended_at": "2026-02-16T18:03:45Z",
  "session_id": "session_id_3",
  "model": "gpt-5.3-codex",
  "output": "{\"approved\": true}",
  "iteration": 1,
  "tokens_estimated": 800
}

**PipelineResult schema:**

json
{
  "version": "1.0.0",
  "task": "Add health endpoint",
  "risk": "low",
  "status": "success",
  "stages": [ ... ],
  "metrics": {
    "total_time_seconds": 226,
    "total_tokens_estimated": 2000,
    "verification_iterations": 1,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

---

## 4. Golden Paths (2 Required)

### Golden Path 1: LOW Risk Task

**Command:**
bash
python scripts/pipeline_runner.py run "Fix typo in README.md" --json

**Expected flow:**
INIT → risk=LOW → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE

**Expected exit code:** 0

---

### Golden Path 2: HIGH Risk Task

**Command:**
bash
python scripts/pipeline_runner.py run "Add JWT authentication endpoint"

**Expected flow:**
INIT → risk=HIGH → DISCOVERY(session_1) → PLANNING(session_1) → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE

**Expected exit code:** 0

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Exit Code |
|---|-------------------|-----------|----------|-----------|
| 1 | Pre-flight gate fails | [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29) returns (False, _) | Abort before Stage 4 | 4 |
| 2 | Verification rejected twice | iteration == 2 AND rejected | Escalate to human | 2 |
| 3 | Model not available | droid exec error | Print available models | 3 |
| 4 | Risk assessment fails | Empty task | Print error | 5 |
| 5 | Stage 3 execution fails | TaskResult.success == False | Abort pipeline | 1 |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE (exactly as written in GAP-09):**

bash
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py --dry-run "Test task" && \
echo "PASS"

**Expected PASS output:**
usage: pipeline_runner.py ...
...
PASS

**Expected FAIL output:**
Error: No module named 'scripts.pipeline_runner'

**CI validation:** OUT OF SCOPE per GAP-09.

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

**Per GAP-09 REPORTING FORMAT, after every step the builder/verifier MUST output:**

text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [x] Check 1 passed
- [x] Check 2 passed

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)

**Compliance rules:**
1. Builders MUST include this report after each step
2. Verifiers MUST include this report after each audit
3. Session ID MUST be documented in each report
4. Pre-Flight Gates section MUST appear before Mode 4 Verification
5. Re-verify count MUST show current iteration out of MAX 2

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | **READ-ONLY** — imports functions |
| [config/models.yaml](cci:7://file:///opt/fabrik/config/models.yaml:0:0-0:0) | **READ-ONLY** — reads stage configs |
| [.droid/](cci:9://file:///opt/fabrik/.droid:0:0-0:0) directory | **WRITE** — state persistence |

### Explicitly NOT Changed (OUT OF SCOPE)

| Component | Reason |
|-----------|--------|
| .github/workflows/* | OUT OF SCOPE per GAP-09 |
| CI/CD integration | OUT OF SCOPE per GAP-09 |
| [scripts/droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) | All functions exist |
| [src/](cci:9://file:///opt/fabrik/src:0:0-0:0) | No source changes |

### Duplication Avoidance

All stage execution uses existing [droid_core.py](cci:7://file:///opt/fabrik/scripts/droid_core.py:0:0-0:0) functions:
- Stage 1: [run_discovery_dual_model()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1223:0-1294:5)
- Stage 2: [run_planning_with_review()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1297:0-1417:5)
- Stage 3: [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43)
- Pre-verify: [run_with_preflight_gates()](cci:1://file:///opt/fabrik/scripts/droid_core.py:1487:0-1579:29)
- Stage 4: [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) with verification model
- Stage 5: [run_droid_exec()](cci:1://file:///opt/fabrik/scripts/droid_core.py:927:0-1144:43) with docs model

---

## 9. Summary of Revisions (v1.0 → v1.1)

| Change | Before | After |
|--------|--------|-------|
| Canonical gate | Expanded with pytest | Exact GAP-09 text |
| CI validation hook | Included | **REMOVED** (out of scope) |
| Pre-flight gates position | Before Stage 3 | Before Stage 4 |
| Session ID allocation | Generic | Matches GAP-09 dataflow exactly |
| Step-reporting format | Not included | **ADDED** as compliance requirement |

**All sections are GAP-09 compliant.** Ready for Mode 3 (Build) execution.

## Response:
Thought for 25s

Your revised v1.1 plan is **much closer to GAP-09** than the earlier Opus version, and your “Stage-2 spec contract” prompt clearly helped—because the output now explicitly aligns to the **canonical gate**, **out-of-scope**, **session separation**, and **step reporting** patterns that exist across your GAP docs.

Where v1.1 is clearly improved (and why this indicates the prompt worked)
-------------------------------------------------------------------------

1.  **Canonical gate is now exact**  
    GAP-09 defines the canonical gate exactly as: `--help` + `--dry-run "Test task"` + `echo "PASS"`.
    2026-02-16-plan-gap09-pipeline-…
    Your v1.1 repeats it verbatim.
2.  **CI/CD integration removed (correctly out of scope)**  
    GAP-09 explicitly lists CI/CD integration as out of scope.
    2026-02-16-plan-gap09-pipeline-…
    Your v1.1 keeps it out.
3.  **Session separation is now explicit and matches the documented “verifier independence” rule**  
    GAP plans repeatedly require a **separate verifier session**.
    2026-02-16-plan-gap09-pipeline-…
    GAP-09 also shows a multi-session dataflow (stage continuity then separate verify).
    2026-02-16-plan-gap09-pipeline-…
    Your v1.1 now encodes this in a session allocation table and the transition table.
4.  **Pre-flight is now explicitly fail-closed and positioned relative to verification**  
    GAP-09’s pre-flight gate function is described as fail-closed and “must pass before AI verification proceeds.”
    2026-02-16-plan-gap09-pipeline-…
    Your v1.1 makes “PRE\_VERIFY → VERIFICATION” explicit.
5.  **Step reporting is now treated as a compliance artifact**  
    GAP plans consistently require evidence + gate output + Mode-4 verification after each step.
    2026-02-16-plan-gap09-pipeline-…
    Your v1.1 adds a structured reporting format, which is consistent with that pattern.

**Conclusion:** yes—your prompt worked, because it forced the missing “hard spec anchors” (gates, scope boundaries, session/roles, reporting) that are explicitly present in the GAP documents.

Remaining issue: a real ambiguity between “pre-flight before verification” vs “pre-flight before execution”
-----------------------------------------------------------------------------------------------------------

GAP-09’s DONE WHEN states: “Pre-flight gates run before each verification.”

2026-02-16-plan-gap09-pipeline-…

But the step instructions for Stage 3 explicitly say: “FIRST runs run\_with\_preflight\_gates() … ONLY IF gates pass: calls run\_droid\_exec()” (i.e., pre-flight before execution).

2026-02-16-plan-gap09-pipeline-…

So your v1.1 positioning “pre-flight immediately before Stage 4” is consistent with the DONE WHEN wording and the function note “before AI verification proceeds.”

2026-02-16-plan-gap09-pipeline-…

…but it conflicts with the Stage-3 step text.

2026-02-16-plan-gap09-pipeline-…

### Minimal fix (recommended)

Define it as:

*   **Pre-flight is required before verification (hard requirement).**
    2026-02-16-plan-gap09-pipeline-…
    2026-02-16-plan-gap09-pipeline-…
*   **Optionally also run pre-flight before execution** when execution writes code, to fail earlier (but do not contradict the “before verification” rule).
    2026-02-16-plan-gap09-pipeline-…

That resolves the internal contradiction without expanding scope.

One more caution: “Repo grounding” claims
-----------------------------------------

Your v1.1 “Repo grounding” section lists specific paths/line refs. GAP-09 itself does not contain those repo paths/lines; the plan file only defines reuse strategy and function names.

2026-02-16-plan-gap09-pipeline-…

So treat the repo grounding table as **valid only if confirmed by actual repo scan** (otherwise it can mislead).

What to tell Opus next (one sentence)
-------------------------------------

“Update v1.1 to resolve the pre-flight ambiguity by specifying: pre-flight MUST run immediately before Stage-4 verification (per DONE WHEN), and MAY also run before Stage-3 execution (per Step-5), but never instead of the pre-verify gate.”

If you want, I can give an exact patch text for the “Pre-flight gates position” section so you can paste it into the spec.

## Prompt:
this is very overwhelming, and i am lost already, you cant create a single prompt to make it happen. i dont know what to do now.

## Response:
Good. Stop.

You are overwhelmed because you are trying to design a **perfect meta-system** before you’ve validated a **minimal working control loop**.

You do NOT need:

*   more spec refinement
*   more prompt engineering
*   traycer yet
*   more GAP rewriting

You need one thing:

A Stable Control Loop
=====================

Right now your real problem is not model choice.  
It is **drift between plan → execution → verification.**

So simplify.

* * *

What To Do Now (Do This Exactly)
================================

Step 1 — Freeze Everything
--------------------------

Ignore all other GAPs.  
Ignore traycer.  
Ignore spec perfection.

Only focus on:

**GAP-09 Pipeline Orchestrator.**

Nothing else.

* * *

Step 2 — Stop Improving The Spec
--------------------------------

Your v1.1 spec is already 80–85% good enough.

Perfection now is diminishing returns.

The real test is:

> Can Stage-3 build it without improvising?

That is the only question that matters.

* * *

Step 3 — Run One Real Execution Cycle
-------------------------------------

Use this instruction:

* * *

SIMPLE EXECUTION PROMPT (Use This Now)
======================================

You are Stage-3 (Execution).

You must implement `scripts/pipeline_runner.py`  
strictly according to GAP-09 Spec v1.1.

Rules:

*   Do not modify any other files.
*   Reuse existing `droid_core.py` functions.
*   Follow the defined CLI contract exactly.
*   Implement only what is required to pass the canonical gate.
*   Do not expand scope.
*   After implementation, output the required STEP REPORT.

Stop after first verification pass.

* * *

That’s it.

No more meta prompts.

No more refinement.

Just build.

* * *

Why You’re Feeling Lost
=======================

You moved from:

“AI makes mistakes”

to

“I will engineer a perfect multi-model orchestration system with formal spec contracts and verification layers.”

That’s a systems jump.

Your brain is trying to manage:

*   orchestration logic
*   model specialization
*   repo enforcement
*   spec determinism
*   verification loops
*   session isolation
*   drift control
*   duplicate detection
*   UI consistency

That’s too many dimensions at once.

* * *

Correct Path Forward
====================

1.  Build pipeline\_runner.
2.  Run it.
3.  See what breaks.
4.  Fix one concrete failure.
5.  Repeat.

Not theory.  
Not architecture.  
Not traycer.  
Execution.

* * *

Important: Traycer Decision
===========================

Do NOT evaluate Traycer yet.

If your internal pipeline cannot reliably enforce:

*   reuse rules
*   gates
*   verifier independence

then Traycer will just add another layer of complexity.

First make your own loop stable.

Then compare.

* * *

Your Immediate Action
=====================

Right now, send the simple execution prompt above to Opus.

When it replies, paste the output here.

We will debug the _actual behavior_ instead of designing hypothetical perfection.

You don’t need a better plan.

You need one working loop.

That’s the move.

## Prompt:
now our prompt became this 
# GAP-09 Pipeline Orchestrator — Spec-Level Implementation Plan

**Version:** 1.2.0  
**Date:** 2026-02-16  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-09 v1.0  
**Source:** @/opt/fabrik/docs/development/plans/2026-02-16-plan-gap09-pipeline-orchestrator.md

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

/opt/fabrik/
├── scripts/
│   ├── droid_core.py          # Core execution functions
│   ├── droid_models.py        # Model resolution
│   ├── droid_session.py       # Session management
│   ├── process_monitor.py     # Process tracking
│   └── enforcement/           # Validation scripts
├── config/
│   └── models.yaml            # Model configuration
├── tests/
│   ├── test_droid_core.py     # Existing droid tests
│   └── orchestrator/          # Orchestrator tests exist
└── docs/development/plans/
    └── 2026-02-16-plan-gap09-pipeline-orchestrator.md

### B. GAP-09 Integration Points

| Component | Status | Path |
|-----------|--------|------|
| run_discovery_dual_model() | **FOUND** | scripts/droid_core.py:1224 |
| run_planning_with_review() | **FOUND** | scripts/droid_core.py:1298 |
| run_with_preflight_gates() | **FOUND** | scripts/droid_core.py:1488 |
| run_parallel_models() | **FOUND** | scripts/droid_core.py:1163 |
| run_droid_exec() | **FOUND** | scripts/droid_core.py |
| scripts/pipeline_runner.py | **NOT FOUND** | **CREATE required** |
| tests/test_pipeline_runner.py | **NOT FOUND** | **CREATE required** |

### C. Blockers

| Blocker | Fix |
|---------|-----|
| scripts/pipeline_runner.py does not exist | **CREATE** (GAP-09 scope) |
| tests/test_pipeline_runner.py does not exist | **CREATE** (GAP-09 scope) |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| scripts/pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN | — | **L** |
| tests/test_pipeline_runner.py | **CREATE** | GAP-09 DONE WHEN | — | **M** |
| scripts/droid_core.py | **VERIFY** | Confirm functions exist | All code | **0** |
| config/models.yaml | **VERIFY** | Confirm stage configs | All config | **0** |

**Explicitly NOT created/modified (OUT OF SCOPE per GAP-09):**
- .github/workflows/*
- Any CI/CD integration
- Web UI for pipeline monitoring
- Real-time streaming dashboard
- Traycer integration (GAP-07)

---

## 3. Interface & Contract Specification

### A. CLI Contract

**Command syntax:**

bash
python scripts/pipeline_runner.py <command> [options]

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| run | Execute full pipeline |
| stage | Execute single stage |
| --help | Show help |

**Flags for run:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| TASK | positional | yes | — | Task description |
| --dry-run | flag | no | false | Simulate without execution |
| --stage | choice | no | auto | Start stage: discovery, planning, execution, verification, ship |
| --risk | choice | no | auto | Override: low, medium, high |
| --cwd | path | no | . | Working directory |
| --json | flag | no | false | JSON output |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Stage failure |
| 2 | Retry exhausted (MAX 2 verification iterations) |
| 3 | Configuration error |
| 4 | Pre-flight gate failure |
| 5 | Risk assessment failure |

### B. State Machine Definition

**Session ID Allocation (per GAP-09 DATA FLOW):**

| Session | Stages | Purpose |
|---------|--------|---------|
| session_id_1 | Stage 1 + Stage 2 | Discovery → Planning continuity |
| session_id_2 | Stage 3 | Execution (new session for build) |
| session_id_3 | Stage 4 | Verification (SEPARATE for Verifier independence) |
| session_id_4 | Stage 5 | Documentation (docs only) |

**Stage transition table:**

┌────────────────┬─────────────────┬─────────────┬────────────────┬─────────────┐
│ Current State  │ Event           │ Next State  │ Action         │ Session     │
├────────────────┼─────────────────┼─────────────┼────────────────┼─────────────┤
│ INIT           │ risk=HIGH       │ DISCOVERY   │ run_stage_1    │ session_1   │
│ INIT           │ risk=MEDIUM     │ PLANNING    │ run_stage_2    │ session_1   │
│ INIT           │ risk=LOW        │ EXECUTION   │ run_stage_3    │ session_2   │
│ DISCOVERY      │ success         │ PLANNING    │ run_stage_2    │ session_1   │
│ DISCOVERY      │ failure         │ FAILED      │ report_error   │ —           │
│ PLANNING       │ success         │ EXECUTION   │ run_stage_3    │ session_2   │
│ PLANNING       │ failure         │ FAILED      │ report_error   │ —           │
│ EXECUTION      │ success         │ PRE_VERIFY  │ run_preflight  │ session_2   │
│ EXECUTION      │ failure         │ FAILED      │ report_error   │ —           │
│ PRE_VERIFY     │ gates_pass      │ VERIFICATION│ run_stage_4    │ session_3   │
│ PRE_VERIFY     │ gates_fail      │ FAILED      │ exit(4)        │ —           │
│ VERIFICATION   │ approved        │ SHIP        │ run_stage_5    │ session_4   │
│ VERIFICATION   │ rejected, n<2   │ EXECUTION   │ run_stage_3    │ session_2   │
│ VERIFICATION   │ rejected, n=2   │ FAILED      │ exit(2)        │ —           │
│ SHIP           │ success/skip    │ DONE        │ report_success │ session_4   │
│ SHIP           │ failure         │ FAILED      │ report_error   │ —           │
└────────────────┴─────────────────┴─────────────┴────────────────┴─────────────┘

**Pre-flight gates position (per GAP-09):**

| Gate Point | Requirement | Source |
|------------|-------------|--------|
| Before Stage 4 Verification | **MUST** run (fail-closed) | GAP-09 DONE WHEN: "Pre-flight gates run before each verification" |
| Before Stage 3 Execution | **MAY** run (optional) | GAP-09 Step-5: "FIRST runs run_with_preflight_gates()" |

**Rule:** The pre-verify gate (before Stage 4) is mandatory and cannot be skipped. The pre-execution gate (before Stage 3) is optional but recommended. Running pre-execution does NOT satisfy the pre-verify requirement.

┌─────────────────┐
                    │ PRE-FLIGHT      │  ◀── MAY run (optional, per Step-5)
                    │ (optional)      │
                    └────────┬────────┘
                             │
                             ▼
                    Stage 3 EXECUTION
                             │
                             ▼
                    ┌─────────────────┐
                    │ PRE-FLIGHT      │  ◀── MUST run (mandatory, per DONE WHEN)
                    │ GATES           │
                    │ ruff, mypy      │
                    │ FAIL-CLOSED     │
                    └────────┬────────┘
                             │ gates_pass
                             ▼
                    Stage 4 VERIFICATION

**Risk routing:**

| Risk Level | Starting Stage | Stages Executed |
|------------|----------------|-----------------|
| LOW | 3 (Execution) | 3 → preflight → 4 → 5 |
| MEDIUM | 2 (Planning) | 2 → 3 → preflight → 4 → 5 |
| HIGH | 1 (Discovery) | 1 → 2 → 3 → preflight → 4 → 5 |

### C. Data Contract

**StageResult schema:**

json
{
  "stage": "verification",
  "status": "pass",
  "started_at": "2026-02-16T18:02:31Z",
  "ended_at": "2026-02-16T18:03:45Z",
  "session_id": "session_id_3",
  "model": "gpt-5.3-codex",
  "output": "{\"approved\": true}",
  "iteration": 1,
  "tokens_estimated": 800
}

**PipelineResult schema:**

json
{
  "version": "1.0.0",
  "task": "Add health endpoint",
  "risk": "low",
  "status": "success",
  "stages": [ ... ],
  "metrics": {
    "total_time_seconds": 226,
    "total_tokens_estimated": 2000,
    "verification_iterations": 1,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}

---

## 4. Golden Paths (2 Required)

### Golden Path 1: LOW Risk Task

**Command:**
bash
python scripts/pipeline_runner.py run "Fix typo in README.md" --json

**Expected flow:**
INIT → risk=LOW → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE

**Expected exit code:** 0

**Expected file side effects:**
- README.md modified
- .droid/pipeline_state_<uuid>.json created

---

### Golden Path 2: HIGH Risk Task

**Command:**
bash
python scripts/pipeline_runner.py run "Add JWT authentication endpoint"

**Expected flow:**
INIT → risk=HIGH → DISCOVERY(session_1) → PLANNING(session_1) → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE

**Expected exit code:** 0

**Expected file side effects:**
- src/api/auth.py created
- CHANGELOG.md updated
- .droid/pipeline_state_<uuid>.json created

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Exit Code |
|---|-------------------|-----------|----------|-----------|
| 1 | Pre-flight gate fails | run_with_preflight_gates() returns (False, _) | Abort before Stage 4 | 4 |
| 2 | Verification rejected twice | iteration == 2 AND rejected | Escalate to human | 2 |
| 3 | Model not available | droid exec error | Print available models | 3 |
| 4 | Risk assessment fails | Empty task | Print error | 5 |
| 5 | Stage 3 execution fails | TaskResult.success == False | Abort pipeline | 1 |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE (exactly as written in GAP-09):**

bash
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py --dry-run "Test task" && \
echo "PASS"

**Expected PASS output:**
usage: pipeline_runner.py ...
...
PASS

**Expected FAIL output:**
Error: No module named 'scripts.pipeline_runner'

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

**Per GAP-09 REPORTING FORMAT, after every step the builder/verifier MUST output:**

text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [x] Check 1 passed
- [x] Check 2 passed

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)

**Compliance rules:**

1. Builders MUST include this report after each step
2. Verifiers MUST include this report after each audit
3. Session ID MUST be documented in each report
4. Pre-Flight Gates section MUST appear before Mode 4 Verification
5. Re-verify count MUST show current iteration out of MAX 2

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| scripts/droid_core.py | **READ-ONLY** — imports functions |
| config/models.yaml | **READ-ONLY** — reads stage configs |
| .droid/ directory | **WRITE** — state persistence |

### Explicitly NOT Changed (OUT OF SCOPE per GAP-09)

| Component | Reason |
|-----------|--------|
| .github/workflows/* | OUT OF SCOPE |
| CI/CD integration | OUT OF SCOPE |
| Web UI for pipeline monitoring | OUT OF SCOPE |
| Real-time streaming dashboard | OUT OF SCOPE |
| Traycer integration | GAP-07 scope |
| scripts/droid_core.py | All functions exist |
| src/ | No source changes |

### Duplication Avoidance

All stage execution uses existing droid_core.py functions:

| Stage | Function |
|-------|----------|
| Stage 1 | run_discovery_dual_model() |
| Stage 2 | run_planning_with_review() |
| Stage 3 | run_droid_exec() |
| Pre-verify | run_with_preflight_gates() |
| Stage 4 | run_droid_exec() with verification model |
| Stage 5 | run_droid_exec() with docs model |

---

## 9. Summary of GAP-09 Compliance

| Requirement | Status |
|-------------|--------|
| Canonical gate matches GAP-09 exactly | ✅ |
| CI/workflow changes removed | ✅ |
| Pre-flight gates before Stage 4 (fail-closed) | ✅ |
| Session IDs match GAP-09 dataflow | ✅ |
| Step-reporting format included | ✅ |

**All sections are GAP-09 compliant.** Ready for Mode 3 (Build) execution.

## Response:
Your v1.2.0 spec is now “good enough to build.” Stop iterating on planning. Next step is execution with tight scope.

Single prompt to send to Opus for Mode 3 (Build)
------------------------------------------------

Copy/paste exactly:

```text
You are Mode 3 (Build) implementing GAP-09 using the provided Spec v1.2.0.

Objective: create ONLY these files:
- scripts/pipeline_runner.py
- tests/test_pipeline_runner.py

Hard rules:
1) Do NOT modify any other files.
2) Do NOT add external dependencies.
3) Reuse existing functions from scripts/droid_core.py (no duplicated logic).
4) Implement the CLI exactly:
   python scripts/pipeline_runner.py <command> [options]
   subcommands: run, stage, --help
   support flags: TASK, --dry-run, --stage, --risk, --cwd, --json
5) Session separation must follow the spec (session_id_1..4) and Stage-4 verification must be a separate session.
6) Pre-flight MUST run fail-closed before Stage 4 Verification, and MAY also run before Stage 3 Execution (optional). Running it before Stage 3 does NOT satisfy the mandatory pre-verify gate.
7) Implement ONLY what is needed to pass the CANONICAL GATE:
   python scripts/pipeline_runner.py --help &&
   python scripts/pipeline_runner.py --dry-run "Test task" &&
   echo "PASS"
8) After you finish, run the canonical gate and paste the full console output.

Deliverables:
A) The full contents of scripts/pipeline_runner.py
B) The full contents of tests/test_pipeline_runner.py
C) STEP REPORT in this exact format:

STEP 1 STATUS: PASS/FAIL
SESSION ID: <...>
MODE: Build

Changed files:
- scripts/pipeline_runner.py
- tests/test_pipeline_runner.py

Gate output:
<paste output>

Self-Review (Builder):
- [ ] CLI matches spec
- [ ] No other files changed
- [ ] No new deps
- [ ] Pre-verify gate implemented
- [ ] Session separation respected

STOP after STEP 1. Do not start verification; that will be a separate run.
```

Optional (recommended) separate prompt for Mode 4 (Verifier)
------------------------------------------------------------

Use only after Mode 3 produces code + gate output:

```text
You are Mode 4 (Verifier). You must NOT implement fixes.

Verify GAP-09 implementation against Spec v1.2.0.

Tasks:
1) Run the canonical gate exactly and report output.
2) Verify no files other than scripts/pipeline_runner.py and tests/test_pipeline_runner.py were modified.
3) Verify CLI flags and exit codes match spec.
4) Verify mandatory pre-verify pre-flight gate exists and is fail-closed.
5) Verify verifier session is separate (session_id_3).

Output STEP REPORT in the required format.
If FAIL: list exact issues and STOP. No patches.
```

If you run Mode 3 with the first prompt and paste the result here, the next move is straightforward: check whether it passes the canonical gate and whether it violated “only two files changed.”



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)