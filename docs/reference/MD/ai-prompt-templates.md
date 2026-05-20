# AI Prompt Templates & Markdown Linting Rules

Reusable prompt structures and markdown rules for AI-friendly documents.

---

## Part A: Prompt Templates

### 1. Universal System Prompt

```md
# Role
You are {{ROLE}}.

## Objective
{{PRIMARY_GOAL}}

## Context
{{BACKGROUND_CONTEXT}}

## Constraints
- {{CONSTRAINT_1}}
- {{CONSTRAINT_2}}

## Input
{{USER_INPUT}}

## Output Requirements
- Format: {{FORMAT}}
- Tone: {{TONE}}
- Length: {{LENGTH}}

## Validation Rules
- Do not hallucinate
- Ask for missing information if required
- State uncertainty explicitly
```

**Use when:** defining a reusable system or agent prompt (AGENTS.md, skills, system-prompt.txt).

### 2. Task Execution (Single-Shot)

````md
# Task
{{TASK_DESCRIPTION}}

## Inputs
- {{INPUT_1}}
- {{INPUT_2}}

## Steps
1. Analyze inputs
2. Apply constraints
3. Produce result

## Constraints
- {{CONSTRAINT}}

## Output Format
```{{FORMAT}}
{{EXPECTED_STRUCTURE}}
```
````

**Use when:** deterministic tasks (analysis, conversion, extraction).

### 3. RAG Question Answering

```md
# Question
{{QUESTION}}

## Retrieved Context
{{RAG_CONTEXT}}

## Instructions
- Use only the provided context
- If context is insufficient, say so
- Do not use outside knowledge

## Output
- Answer
- Supporting excerpt (quote)
```

**Critical:** prevents hallucination. Works best when context chunks are Markdown-structured.

### 4. Extraction / Structuring

````md
# Source Text
{{RAW_TEXT}}

## Task
Extract the following fields:
- {{FIELD_1}}
- {{FIELD_2}}

## Rules
- Return valid JSON
- Use null if missing
- No commentary

## Output
```json
{
  "{{FIELD_1}}": "",
  "{{FIELD_2}}": ""
}
```
````

**Use when:** pipelines, automations, APIs (e.g., CV extraction in job-agent).

### 5. Multi-Step Reasoning

```md
# Problem
{{PROBLEM}}

## Reasoning Rules
- Think step by step
- Keep reasoning concise
- Do not assume missing data

## Final Answer
```

**Note:** keep reasoning bounded to avoid verbosity drift.

### 6. Agent Memory Entry

```md
# Memory Entry

## Type
{{FACT | DECISION | RULE}}

## Content
{{MEMORY_CONTENT}}

## Valid From
{{DATE}}

## Confidence
{{HIGH | MEDIUM | LOW}}
```

**Use when:** long-running agents, persistent context (shift notes, session memory).

---

## Part B: Markdown Linting Rules

These prevent human errors AND AI degradation.

### Structural Rules (Critical)

| Rule | Description |
|---|---|
| **MD001** | One H1 per document |
| **MD002** | No skipped heading levels (## → ### not ## → ####) |
| **MD003** | Blank lines around headings |

### List Rules

| Rule | Description |
|---|---|
| **MD004** | Consistent list markers — use `-` only (not `*` or `+`) |
| **MD005** | Blank line before lists |
| **MD006** | Proper indentation (2 spaces) |

### Code Rules (Critical for AI)

| Rule | Description |
|---|---|
| **MD010** | Fenced code blocks only — never indented code |
| **MD011** | Always specify language (`python`, `bash`, `json`) |
| **MD012** | Blank line before and after code blocks |

### Table Rules

| Rule | Description |
|---|---|
| **MD030** | Tables must have header separator |
| **MD031** | No multiline cells — keep tables atomic |

### AI-Specific Rules

| Rule | Description |
|---|---|
| **AI001** | Headings define semantic chunks — never use for styling |
| **AI002** | Lists imply constraints or steps — don't mix narrative |
| **AI003** | Code blocks are sacred — no commentary inside |
| **AI004** | Avoid decorative markdown — no ASCII art, emojis, visual hacks |

### Enforcement

If you want automated linting: `markdownlint`, `markdownlint-cli`, or `remark-lint` with a custom ruleset aligned to the rules above.
