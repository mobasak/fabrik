## DONE

A single reference for `droid exec` that combines:

1. **What the docs say `droid exec` supports** (capabilities, inputs/outputs, flags), and
2. A **cost-efficient operating model** (tool gating + evidence gating + escalation + multi-pass).

---

## 1) What `droid exec` is for (docs)

* **One-shot, non-interactive execution**: run a prompt, produce output to stdout/stderr, exit.
* **Automation-friendly**: supports structured output modes (JSON / streaming).
* **Safety/permissions model**: default is constrained; autonomy can be increased; unsafe skip exists (mutually exclusive with `--auto`).
* **Session continuity**: can continue runs via a session id.

(These map to the doc-derived items in the previous answer.)

---

## 2) Command shape (docs)

`droid exec [options] [prompt]`

Where `[prompt]` can come from:

* inline string prompt
* `--file` prompt file
* stdin (pipe)
* streaming stdin protocol when using `--input-format stream-jsonrpc`

---

## 3) Inputs (docs)

### Prompt input methods

* Inline prompt: `droid exec "…"`
* File: `-f, --file <path>`
* Piped stdin: `echo "…" | droid exec`
* Streaming multi-turn stdin: `--input-format stream-jsonrpc` (JSONL messages)

### Working directory

* `--cwd <path>`

### Session continuation

* `-s, --session-id <id>`

---

## 4) Outputs (docs)

### Output formats

* `-o, --output-format text` (default)
* `-o, --output-format json` (single structured object)
* `-o, --output-format stream-json` (JSONL event stream)
* `-o, --output-format stream-jsonrpc` (JSON-RPC style streaming for integrations)

### Exit codes

* success: `0`
* failure: non-zero

---

## 5) Options / parameters (docs)

### Safety / autonomy

* `--auto <low|medium|high>`
* `--skip-permissions-unsafe` (cannot be combined with `--auto`)
* `--use-spec`

### Model controls

* `-m, --model <id>`
* `-r, --reasoning-effort <off|none|low|medium|high>`
* `--spec-model <id>`
* `--spec-reasoning-effort <level>`

### Tool controls

* `--list-tools`
* `--enabled-tools <ids>`
* `--disabled-tools <ids>`

### I/O controls

* `--input-format <format>` (notably `stream-jsonrpc`)
* `-o, --output-format <format>` (see above)

### Misc

* `--delegation-url <url>`
* `-h, --help`
* `-v, --version`

---

## 6) Efficient operating model for `droid exec` (your text, merged with the above)

### Core principles

1. **Make expensive actions opt-in**

   * default: bounded tools, bounded context, bounded output
   * escalation: enable costly tools only for the subset that needs it

2. **Separate facts from writing**

   * Pass A: fact extraction/verification (minimal output)
   * Pass B: narrative/format expansion (no web/tools)

3. **Only produce precision you can justify**

   * default to coarse values unless explicitly supported; escalate for high specificity

---

## 7) Token-minimizing levers mapped to `droid exec` flags

### A) Tool gating (highest impact)

* Inspect what exists: `droid exec --list-tools`
* Default runs: restrict tools with `--disabled-tools` / `--enabled-tools`
* Pattern:

  * Pass A: allow only minimal tools needed (e.g., search), disable full-page ingestion tools
  * Pass A2: enable heavier tools (e.g., fetch/ingest) but only on flagged subset
  * Pass B: disable tools entirely (or restrict to none)

### B) Session reuse / multi-turn

* Use `--session-id` to avoid resending large shared context across runs.
* For app-like orchestration, prefer `--output-format stream-jsonrpc` + `--input-format stream-jsonrpc`.

### C) Reduce output size

* Prefer `--output-format json` or minimal JSONL content in Pass A.
* Avoid verbose text unless it’s the final deliverable.

### D) Dedup + cache outside `droid`

* Normalize keys, cache model results (JSON/SQLite), call `droid exec` only on cache misses.

### E) Prompt budgets

* Hard caps: “max 1 search”, “max 1 fetch”, “stop when confidence ≥ X”
* Enforce “no guessing” and “escalate only when needed”

---

## 8) Recommended generic execution architecture (best-efficiency)

### Pass A: Resolve facts cheaply

* Tools: restricted (search allowed ≤1; fetch disabled)
* Output: **small JSONL**: only research-dependent fields + `confidence` + `needs_escalation` + optional snippet-grounded `research_summary`

### Pass A2: Escalation subset only (optional)

* Input: only items with `needs_escalation=true`
* Tools: allow bounded fetch (≤1) + bounded search (≤1)
* Output: overlays only (`id` + updated fields + sources + confidence)

### Pass B: Final generation (no tools)

* Input: original items + merged overlays + verified facts
* Tools: disabled/restricted to none
* Output: full schema / final narrative

---

## 9) Minimal “best setup” checklist (operational)

* Tools: default disable heavy ingestion; only enable in escalation.
* Prompt: hard budgets + stop conditions + no-guessing contract.
* Output: minimal facts pass → final pass.
* Cache: dedupe keys + store results.
* Session: reuse `--session-id` or use `stream-jsonrpc`.
* Validation: strict JSONL parsing; repair-on-failure prompt.
* Escalation: only flagged subset.
* Audit: store sources/confidence; sample QA.

---

## 10) One optimal generic plan

1. Build Pass A with strict tool budgets and minimal JSONL output.
2. Add caching + dedupe keys.
3. Add Pass A2 escalation for flagged cases only (bounded fetch/search).
4. Build Pass B with tools disabled, consuming only verified facts/summaries.
5. Add validation + repair + QA sampling to stabilize runs.

Available built-in models:
  gpt-5.1-codex, gpt-5.1-codex-max, gpt-5.1, gpt-5.2, claude-sonnet-4-5-20250929, claude-o
pus-4-5-20251101, claude-opus-4-1-20250805, claude-haiku-4-5-20251001, gemini-3-pro-preview, glm-4.6