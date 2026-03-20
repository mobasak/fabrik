# AI Agent Prompt Directives

Quick-reference phrases to steer AI agents toward thorough, correct, production-ready output.

---

## Completeness & Thoroughness

| Phrase | Purpose |
|--------|---------|
| **Be thorough.** | Don't stop at the happy path — cover edge cases |
| **Follow verbatim.** | Implement exactly what is specified, nothing less |
| **Complete the full implementation — do not stub, skip, or leave TODOs.** | Forces full delivery, not skeleton code |
| **Handle all cases listed — not just the first.** | Prevents partial loop execution |
| **Do not truncate output.** | Show the full result, not "…and so on" |

---

## Self-Review & Verification

| Phrase | Purpose |
|--------|---------|
| **Before returning, review your own output for correctness, completeness, and consistency.** | Triggers self-audit before delivery |
| **Verify that every requirement from the spec is addressed.** | Prevents silent requirement omissions |
| **Check your work: trace through the logic step by step before finalizing.** | Forces deliberate reasoning, not pattern matching |
| **Do a final pass: look for off-by-one errors, null paths, and missing imports.** | Targets the most common coding mistakes |
| **Confirm the output compiles / runs without modification.** | Holds agent accountable for runnable code |

---

## No Assumptions or Hallucinations

| Phrase | Purpose |
|--------|---------|
| **Do not assume — if something is ambiguous, state your assumption explicitly before proceeding.** | Surfaces hidden guesses before they cause bugs |
| **Do not hallucinate APIs, methods, or library features. If you are unsure whether something exists, say so.** | Prevents confident fabrication of non-existent functions |
| **Only use functions and imports you can confirm exist in this codebase or the specified library version.** | Version-anchors the implementation |
| **Do not invent variable names or field names — derive them strictly from what is visible in context.** | Prevents schema drift |

---

## Best Practices & Quality

| Phrase | Purpose |
|--------|---------|
| **Apply best practices for the language and framework in use.** | Activates idiomatic, production-grade patterns |
| **Follow SOLID principles and maintain separation of concerns.** | Architecture guidance for larger outputs |
| **Write production-ready code — not prototype or demo quality.** | Raises the quality bar explicitly |
| **Include meaningful error handling — do not swallow exceptions silently.** | Prevents bare try/catch or pass blocks |
| **Keep functions small and single-purpose.** | Enforces decomposition |

---

## Code Review Directives

| Phrase | Purpose |
|--------|---------|
| **Review this code thoroughly: identify bugs, security issues, performance problems, and violations of best practices. Be specific — cite line numbers or function names.** | Full-spectrum review with specificity requirement |
| **Do not just describe what the code does — evaluate whether it does it correctly and safely.** | Shifts review from description to judgment |
| **Flag any silent failure modes — paths where the code proceeds without error but produces wrong results.** | Catches the hardest class of bugs |
| **Prioritize findings: Critical / High / Medium / Low.** | Forces triage so fixable issues surface first |

---

## Execution Speed & Focus

| Phrase | Purpose |
|--------|---------|
| **Do not ask for clarification — make the best reasonable interpretation and state it, then proceed.** | Eliminates back-and-forth on unblocking tasks |
| **Deliver the solution directly — skip the preamble and commentary.** | Cuts agent verbosity, gets to output faster |
| **Focus exclusively on the task. Do not refactor unrelated code.** | Prevents scope creep in agentic edits |

---

## Usage

Copy any phrase directly into your prompt to activate that behavior in AI agents (Claude, GPT, Gemini, etc.).
