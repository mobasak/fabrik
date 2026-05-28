# Prompt Repository Folder Structure

Production-ready structure for organizing AI prompts at scale. One prompt = one file, composable, diffable, testable.

> **Fabrik current state:** Prompts are scattered across `.windsurf/rules/`, `AGENTS.md`, `CLAUDE.md`, `system-prompt.txt`, and inline in Python scripts. This doc is a reference architecture for when centralization becomes needed.

---

## Structure

```text
prompts/
├─ README.md                    # Purpose + usage
├─ _meta/
│  ├─ conventions.md            # Naming, structure, tone rules
│  ├─ linting.md                # Markdown + AI lint rules
│  └─ variables.md              # Allowed {{PLACEHOLDERS}}
│
├─ system/
│  ├─ base-system.md            # Default role, behavior, limits
│  ├─ safety.md                 # Refusals, uncertainty handling
│  └─ domain/
│     ├─ finance.md
│     ├─ legal.md
│     └─ medical.md
│
├─ tasks/
│  ├─ analysis/                 # summarize, compare, classify
│  ├─ generation/               # write-article, create-outline
│  ├─ transformation/           # translate, rewrite, format-convert
│  └─ extraction/               # entities, tables, json-schema
│
├─ rag/
│  ├─ qa.md                     # Context-only answering
│  ├─ citation.md               # Evidence enforcement
│  └─ refusal.md                # Insufficient-context handling
│
├─ knowledge/
│  ├─ core.md                   # Universal domain principles (always injected)
│  ├─ {domain-a}.md             # Domain-specific fragment
│  ├─ {domain-b}.md             # Domain-specific fragment
│  └─ routing.md                # Task → fragment(s) mapping
│
├─ agents/
│  ├─ planner.md                # Role + output contract
│  ├─ executor.md
│  ├─ reviewer.md
│  └─ memory.md
│
├─ workflows/
│  ├─ research.md               # Multi-prompt sequences
│  ├─ content-pipeline.md
│  └─ decision-support.md
│
├─ tests/
│  ├─ inputs/                   # Test inputs
│  ├─ expected/                 # Expected outputs
│  └─ regression.md             # Known failure cases
│
└─ versions/
   ├─ v1/
   ├─ v2/
   └─ changelog.md
```

---

## Design Principles

- **Everything is Markdown** — version-controlled, diffable, human + AI readable
- **One prompt = one responsibility** — no monolithic system prompts
- **Composable** — workflows combine task prompts, not duplicate them
- **Knowledge-routed** — domain expertise lives in `knowledge/`, injected selectively per task via a static routing map (not monolithically)
- **Testable** — tests/ catches regressions after prompt edits
- **Versioned** — never overwrite production prompts, version explicitly

---

## Standard Prompt File Template

Every `.md` prompt file:

````md
# Prompt Name

## Purpose
{{WHAT_THIS_PROMPT_DOES}}

## Inputs
- {{INPUT_1}}
- {{INPUT_2}}

## Constraints
- {{CONSTRAINT_1}}
- {{CONSTRAINT_2}}

## Output Format
```{{FORMAT}}
{{STRUCTURE}}
```

## Failure Mode
If inputs are insufficient, respond with:
"Insufficient information to complete task."
````

---

## Variable Rules

Defined centrally in `_meta/variables.md`:

- `{{TEXT}}`, `{{CONTEXT}}`, `{{LANGUAGE}}`, `{{FORMAT}}`, `{{SCHEMA}}`
- No free-form variables — undefined variable = error
- Variables are replaced programmatically

---

## How Fabrik Maps to This (if adopted)

| This structure | Current fabrik equivalent |
| --- | --- |
| `system/` | `AGENTS.md`, `CLAUDE.md`, `.windsurfrules`, `system-prompt.txt` |
| `tasks/` | Inline in `kilo_code_review.py`, `kilo_dispatch.py` |
| `knowledge/` | `prompts/bible/` (brand-identity-creator) |
| `agents/` | `~/.traycer/cli-agents/*.sh`, `.windsurf/workflows/*.md` |
| `workflows/` | `.windsurf/workflows/*.md` |
| `tests/` | No prompt testing exists yet |
| `versions/` | No prompt versioning exists yet |

---

## When to Adopt This

- When prompt count exceeds ~30 and drift becomes a problem
- When multiple people edit prompts and need governance
- When prompt quality regressions start causing production issues
- When you build a product that sells prompt-driven features
