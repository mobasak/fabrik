You are doing deep technical research for Fabrik, an internal solo-developer platform.

Context and constraints:
- Solo developer, ~50 focused hours/week
- Budget-conscious: prefer low-maintenance, durable, low-ops approaches
- Dev environment: WSL Ubuntu 24.04
- Deployment: x86_64 Ubuntu VPS via `fabrik apply` (SSH + Docker Compose) (Docker Compose)
- Defaults: Python + FastAPI + Uvicorn, Next.js 14 + TypeScript + Tailwind, PostgreSQL 16
- Mobile: React Native / TypeScript
- Chrome extensions: Manifest V3
- Base images: slim-bookworm only, never Alpine
- Prefer standards and practices that will still be good 2-3 years from now
- Avoid trendy/high-maintenance patterns unless clearly worth it
- Goal is to create a permanent rule file for agents, not just a general article

Research instructions:
- Prioritize official docs, standards, maintainers’ guidance, and broadly adopted current best practices
- Focus on fast, modern, durable, maintenance-light choices
- Separate “must enforce always” from “nice to have”
- Flag anything that is too opinionated, unstable, expensive, or high-maintenance
- Recommend what should be:
  1. enforced in execution handoffs,
  2. checked in final_gate.py,
  3. documented in AGENTS.md / AGENTS-compact.md,
  4. left as human guidance only

Output format:
1. Executive summary
2. Canonical rules for this rule file (10-20 bullets max)
3. Anti-patterns / banned patterns
4. What to enforce in execute handoffs
5. What to verify in final_gate.py
6. What belongs in AGENTS.md / AGENTS-compact.md
7. Minimal practical examples for Fabrik stack
8. “Recommended final content” for the rule file in a concise markdown format
