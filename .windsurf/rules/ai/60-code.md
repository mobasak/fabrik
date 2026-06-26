---
activation: glob
globs: ["**/code-assist/**", "**/copilot/**", "**/codegen/**", "**/code-gen/**", "**/code-review-ai/**"]
description: Code & Developer AI (category 6) — generate or explain code (Claude Code, GitHub Copilot, Cursor, Windsurf Cascade, Amazon Q). Code completion, refactoring, debugging. Kilo: 148 code models.
trigger: glob
---
<!-- CONSUMER: Coding agents building code-generation features + Traycer (tech-plan)
     GOAL: Pick a code model/agent; Claude Code is the Fabrik in-house agent; this category is mostly meta (which agent runs the work).
     TRAYCER USAGE: Context File for code-assistant / codegen feature tickets.
     AGENT USAGE: For an embedded code-gen feature, default Claude. Don't confuse this with the dev tooling Fabrik already uses (Claude Code, Windsurf Cascade, Kilo). -->

# 6. Code & Developer AI

**Purpose:** Generate or explain code.

## Fabrik default
- **Claude / Claude Code** for code generation and review features. The Fabrik dev stack already uses Claude Code, Windsurf Cascade, and Kilo CLI — this category is about code AI *embedded in a product*, not the dev tooling.

## Examples
Claude Code, GitHub Copilot, Amazon Q Developer, Cursor IDE, Windsurf Cascade.

## Kilo coverage
✅ 148 code models. Free: `minimax/minimax-m2.5:free`. Full paid range. Check Kilo before a paid external code API.

**Use cases:** code completion, refactoring, debugging assistance.
