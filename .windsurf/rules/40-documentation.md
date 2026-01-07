# Documentation Rules

activation: glob
globs: ["*.md", "docs/**/*", "specs/**/*"]

---

## Plan Document Structure (MANDATORY)

All plan documents (`phaseX.md`, `*_PLAN.md`) MUST follow this structure:

```markdown
# Phase X: [Feature Name]

**What is this?** One sentence.

---

## The Problem
Why things are broken. Plain language, bullet points.

## The Solution
One paragraph + user flow showing what happens automatically.

## What We're Building
Table: File/Component | What it does

## How It Works (Step by Step)
Step 1, Step 2, Step 3... in plain words.

## What This Fixes
Table: Before | After

## Timeline
Table: Phase | Days | What happens

## What We're NOT Building (Yet)
Deferred features list.

## Success = When This Works
Code block showing happy path.
```

**Template:** `templates/docs/PLAN_TEMPLATE.md`

## Writing Style

- **Plain language** — No jargon unless necessary
- **Show don't tell** — Use examples and code blocks
- **Before/After tables** — Make improvements obvious
- **Step-by-step** — Break complex flows into numbered steps
