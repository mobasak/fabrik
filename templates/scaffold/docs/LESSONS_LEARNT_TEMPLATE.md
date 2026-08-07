<!-- markdownlint-disable MD032 MD031 MD040 MD022 MD024 -->
# Lessons Learnt

**Last Updated:** YYYY-MM-DD

**Purpose:** CAPTURE TECHNICAL HURDLES, AI-SPECIFIC QUIRKS, AND ARCHITECTURAL DECISIONS TO PREVENT REGRESSION AS CODEBASES AND AI AGENTS EVOLVE.

---

## Template

Copy this template for each lesson learnt. Name entries with a descriptive title and date.

````
# Lessons Learnt: [Feature/Bug Name]
**Date:** YYYY-MM-DD
**Status:** [Permanent Rule / Investigation / Deprecated]

**TL;DR:** One-sentence takeaway.

## 1. Context

- **Project/Module:** (e.g., Fabrik PaaS, FastAPI backend, Next.js frontend)
- **Environment:** (e.g., WSL Ubuntu, VPS, Docker)
- **AI Agent Used:** (e.g., Claude Code (Opus/Sonnet), an OpenRouter pool model — name model + harness)

## 2. The Problem

Describe the unexpected behavior or technical blocker. Was it a logic error, a model hallucination, or a stack-specific constraint?

**Impact:** [Low / Medium / High / Critical] — Distinguishes severity (e.g., 30-min debug vs production downtime).

## 3. Root Cause Analysis

- **Technical Trigger:** (e.g., PostgreSQL 16 connection pooling issue, Tailwind class conflict)
- **Model Behavior:** (Select one: Hallucination / Context Overflow / Stale Docs / Prompt Misinterpretation / N/A)
- **Why it happened:** (e.g., Context window overflow or stale documentation in the agent's memory)

## 4. The Solution & "Aha!" Moment

Provide the specific code snippet, prompt adjustment, or architectural change that fixed the issue.

```python
# Example of the corrected pattern
```

## 5. Integration: Rule Update

Which existing rule file needs to be updated to prevent this in the future?

- **Target File:** (e.g., `.windsurf/rules/core/10-python.md` or `.windsurf/rules/core/25-data-postgres.md`)
- **New Instruction:** "Always ensure [X] when [Y] to avoid [Z]."

## 6. Triggered By

What condition caused this to surface? (e.g., Alert storm, Deployment failure, Code review, User report)

- **Trigger:** (e.g., Production alert, Local testing, CI failure)
- **Detection Method:** (e.g., Monitoring alert, Manual inspection, User feedback)
````

---

## Why This Structure Works

1. **AI Compatibility:** By summarizing the "Lessons Learnt" into a specific "Rule Update," you can immediately feed that insight back into your AI agent's system instructions. This creates a closed-loop system where the AI learns from its own past mistakes.

2. **Stack Specificity:** Including sections for FastAPI, PostgreSQL, and Next.js allows you to track issues unique to your environment, such as WSL-specific networking or Ubuntu VPS hardening.

3. **Low-Ops Maintenance:** A single Markdown file is low-maintenance and standards-compliant, ensuring you can search and reference it even if you switch tools or orchestration layers later.

---

## When to Use This Template

- **After debugging a complex issue** that required multiple iterations
- **When an AI agent consistently makes the same mistake** across sessions
- **After architectural decisions** that have trade-offs worth documenting
- **When a stack-specific constraint** (e.g., WSL networking, VPS hardening) causes unexpected behavior
- **When upgrading dependencies** that introduce breaking changes or new patterns

---

## Integration with Fabrik Rules

When a lesson learnt graduates to a permanent rule:

1. Update the relevant `.windsurf/rules/**/*.md` file with the new instruction

2. Reference this file in the rule's rationale if needed

3. Update the lesson's "Status" field to "Permanent Rule" with the target rule file

---

## Example Entry

````markdown
# Lessons Learnt: Async LLM Client for ARO Brain
**Date:** 2026-04-14
**Status:** Permanent Rule

**TL;DR:** Never use sync HTTP clients in async FastAPI endpoints — use httpx.AsyncClient.

## 1. Context

- **Project/Module:** ARO Brain (alert reasoning webhook)
- **Environment:** Docker on VPS (Ubuntu 24.04)
- **AI Agent Used:** Claude Code (Sonnet)

## 2. The Problem

Initial implementation used synchronous `httpx.Client` for LLM calls, blocking the FastAPI event loop during 2-5 second API requests. Under alert storms, this caused request queuing and timeouts.

**Impact:** High — Production alert storms caused request queuing and timeouts.

## 3. Root Cause Analysis

- **Technical Trigger:** Synchronous HTTP client in async FastAPI endpoint
- **Model Behavior:** N/A
- **Why it happened:** Copied pattern from SEO module (synchronous CLI context) without considering async service context

## 4. The Solution & "Aha!" Moment

Switch to `httpx.AsyncClient` with async/await pattern:

```python
async with httpx.AsyncClient(timeout=120) as client:
    response = await client.post(...)
```

## 5. Integration: Rule Update

- **Target File:** `.windsurf/rules/core/10-python.md`
- **New Instruction:** "All HTTP calls in FastAPI endpoints MUST use async clients (httpx.AsyncClient, aiohttp). Never use synchronous clients in async contexts."

## 6. Triggered By

- **Trigger:** Production alert storm
- **Detection Method:** Monitoring alert (request timeout spike)
````
