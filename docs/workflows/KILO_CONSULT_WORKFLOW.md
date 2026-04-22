# Kilo Consultation Workflow

**Purpose:** Provide Cascade with a Q&A consultation tool when stuck on implementation, architecture, debugging, or best practices questions.

**Script:** `/opt/fabrik/scripts/kilo_consult.py`

**Workflow Doc:** `docs/workflows/KILO_CONSULT_WORKFLOW.md`

---

## Overview

`kilo_consult.py` is a focused consultation script for Cascade to query Kilo AI agents when stuck. It uses proven patterns from `kilo_code_review.py` but simplified for Q&A use case (no code changes, no iteration loops).

**Key Features:**
- Risk-based routing (high-risk paths → expensive models)
- Direct risk-to-model mapping (no escalation, no DB)
- Session management with Q&A history (session_id for related questions)
- Optional git diff context for stuck-on-changes scenarios
- Configurable models via environment variables
- All three models supported (Gemini Flash, GPT-5.4, Opus 4.6)

---

## When to Use

**Consult Kilo when:**
- Stuck on implementation details
- Architecture decision needed
- Debugging root cause unclear
- Best practices question
- API/library usage unknown
- Need design guidance

**Do NOT use for:**
- Code review (use `kilo_code_review.py` instead)
- Auto-fixing (this is Q&A only, Cascade applies fixes manually)
- Structured output validation (simple text responses)

---

## Question Formulation Best Practices

**Consulting Agent (Cascade) Guidelines:**

- **Do not trust the answer 100%** — The replying agent (Kilo) can make mistakes. Always verify critical suggestions before applying.
- **Be context-aware** — Include relevant file context, error messages, stack traces, and current state.
- **Be definitive** — Ask specific questions with clear scope. Avoid vague "what do you think?" queries.
- **Be result-oriented** — Focus on the desired outcome, not the process. "How do I fix X?" not "What's wrong with my code?"
- **Be lean** — Keep questions concise. Provide only necessary context. Long prompts waste tokens and dilute focus.
- **Seek long-term permanent solutions** — Ask for architectural patterns, not quick hacks. "How should I structure this?" not "How do I make this work now?"

**Consulted Agent (Kilo) Guidelines:**

- **Give crystal clear step-by-step walkthrough answers** — Break down solutions into numbered steps with explicit actions.
- **Be specific** — Cite line numbers, function names, and exact code locations.
- **Explain the why** — Include rationale so the consulting agent can verify and adapt the solution.
- **Handle edge cases** — Mention potential failure modes and how to detect them.
- **Reference existing patterns** — Point to similar code in the codebase when applicable.

**For comprehensive prompt directives**, see: `docs/reference/ai_agent_prompt_directives.md`

---

## Risk Assessment

The script automatically assesses risk based on file path to select appropriate model.

### High-Risk Paths (Escalate to Opus 4.6)

**Directory prefixes:**
- `backend/`, `server/`, `api/`
- `auth/`, `security/`, `session/`, `crypto/`, `middleware/`, `permissions/`
- `migrations/`, `alembic/`, `prisma/`, `db/`, `database/`, `models/`
- `docker/`, `infra/`, `infrastructure/`, `.github/`, `ci/`
- `wp-content/plugins/`, `wp-content/themes/`

**Filenames (exact match, case-insensitive):**
- `compose.yaml`, `Dockerfile`, `.env`, `.env.production`, `.env.local`
- `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`
- `requirements.txt`, `poetry.lock`, `pyproject.toml`
- `go.mod`, `go.sum`, `cargo.toml`, `cargo.lock`
- `manifest.json`, `background.js`, `service_worker.js`

### Risk Levels

| Risk Level | Trigger | Starting Model |
|------------|---------|----------------|
| **Critical** | compose.yaml, Dockerfile, .env, package.json | Opus 4.6 max |
| **High** | backend/, auth/, docker/, migrations/ | GPT-5.4 high |
| **Medium** | Default | Gemini Flash high |
| **Low** | Documentation, config files | Gemini Flash low |

---

## Model Selection

### Supported Models

| Model | Cost | Thinking | Use When |
|-------|------|----------|----------|
| **Gemini 3 Flash** | ~$0.75/1M out | Low | Quick questions, cost-sensitive |
| **GPT-5.4** | ~$15/1M out | Maximum | Code generation, refactoring, implementation |
| **Opus 4.6** | ~$25/1M out | Maximum | Architecture, critical reasoning, security |

### Model Selection Logic

```python
if risk_level == "critical":
    model = KILO_MODEL_EXPENSIVE  # Opus 4.6 (default: kilo/anthropic/claude-opus-4.6)
elif risk_level == "high":
    model = KILO_MODEL_MID  # GPT-5.4 (default: kilo/openai/gpt-5.4)
elif risk_level == "medium":
    model = KILO_MODEL_CHEAP  # Gemini Flash (default: kilo/google/gemini-3-flash-preview)
else:  # low
    model = KILO_MODEL_CHEAP  # Gemini Flash (default: kilo/google/gemini-3-flash-preview)
```

**Override with `--model` flag:**
```bash
python scripts/kilo_consult.py --model kilo/anthropic/claude-opus-4.6 --file file.py "Question"
```

---

## Variant Selection

Variants control thinking depth (reasoning mode).

| Variant | Use When | Duration | Cost |
|---------|----------|----------|------|
| **low** | Quick lint checks | ~10s | Lowest |
| **high** | Standard reviews (default) | ~20s | Best quality/cost |
| **max** | Complex/security reviews | ~40s | Highest quality |

### Variant by Risk Level

```python
if risk_level == "critical":
    variant = "max"
elif risk_level in ("high", "medium"):
    variant = "high"
else:  # low
    variant = "low"
```

**Override with `--variant` flag:**
```bash
python scripts/kilo_consult.py --variant max --file file.py "Question"
```

---

## Session Management

Sessions enable context continuity for related questions.

### Session ID Format

```
consult-<filename>-<hash>-<YYYYMMDD>
```

Example: `consult-coolify-a1b2c3-20260415`

The 6-character hash suffix prevents collisions for files with the same name in different directories.

### Session State

**Stored in:** `.droid/consultations/<session_id>.json`

**Tracked:**
- session_id, created_at, last_used_at
- model, variant, file_path
- risk_level
- iteration count
- history (last 10 Q&A pairs)

### Usage

**First consultation:**
```bash
python scripts/kilo_consult.py --file src/fabrik/drivers/coolify.py "How do I fix the API endpoint?"
# Session ID: consult-coolify-20260415
```

**Follow-up question (same session):**
```bash
python scripts/kilo_consult.py --session consult-coolify-20260415 "Now apply that fix to the deploy method"
```

**Benefits:**
- Context carries forward
- Kilo remembers previous answers
- Better for multi-step problem solving

---

---

### Command-Line Options

### Full Usage

```bash
python scripts/kilo_consult.py [-h] [--file FILE] [--model MODEL] [--variant VARIANT]
                              [--session SESSION] [--timeout TIMEOUT] [--diff]
                              question
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--file FILE` | File to consult about | `--file src/fabrik/drivers/coolify.py` |
| `--model MODEL` | Override model selection | `--model kilo/anthropic/claude-opus-4.6` |
| `--variant VARIANT` | Override variant selection | `--variant max` |
| `--session SESSION` | Continue existing session | `--session consult-coolify-a1b2c3-20260415` |
| `--timeout TIMEOUT` | Timeout in seconds (default: 120) | `--timeout 300` |
| `--diff` | Include git diff in consultation context | `--diff` |
| `question` | Your question (required) | `"What is the purpose of this method?"` |

### Help

```bash
python scripts/kilo_consult.py --help
```

---

## Usage Examples

### Simple Consultation

```bash
python scripts/kilo_consult.py \
    --file src/fabrik/drivers/coolify.py \
    "What is the purpose of the deploy method in this file?"
```

**Output:**
```
[Consult] Session: consult-coolify-a1b2c3-20260415
[Consult] Risk: high
[Consult] Model: kilo/openai/gpt-5.4
[Consult] Variant: high
[Consult] File: src/fabrik/drivers/coolify.py
[Consult] Question: What is the purpose of the deploy method in this file?

[Kilo response...]
```

### Override Model for Critical Questions

```bash
python scripts/kilo_consult.py \
    --model kilo/anthropic/claude-opus-4.6 \
    --variant max \
    --file src/fabrik/drivers/coolify.py \
    "Design a better API client for Coolify"
```

### Follow-Up Question

```bash
python scripts/kilo_consult.py \
    --session consult-coolify-20260415 \
    "Now apply that fix to the deploy method"
```

### No File (General Question)

```bash
python scripts/kilo_consult.py \
    "What is the best way to handle async database connections in FastAPI?"
```

### With Git Diff (Stuck on Changes)

```bash
python scripts/kilo_consult.py \
    --diff \
    --file src/fabrik/drivers/coolify.py \
    "I'm getting a 404 error on the deploy method. What's wrong?"
```

---

---

## Technical Implementation

### Script Location

```
/opt/fabrik/scripts/kilo_consult.py
```

### Key Components

1. **Risk Assessment** (`assess_risk()`)
   - File path pattern matching
   - Returns: low, medium, high, critical

2. **Model Selection** (`get_model_for_risk()`)
   - Direct risk → model mapping
   - User override support

3. **Variant Selection** (`get_variant_for_risk()`)
   - Risk → variant mapping
   - User override support

4. **Session Management** (`create_session_id()`, `load_session_state()`, `save_session_state()`)
   - Session ID generation with hash suffix
   - State persistence to JSON
   - Q&A history (last 10 entries)
   - Iteration tracking

5. **Kilo Execution** (`run_kilo()`)
   - Subprocess with stdin input
   - Timeout protection
   - Stderr debugging
   - History context injection for session continuity
   - FileNotFoundError handling

### Dependencies

- Python 3.10+
- Kilo CLI 7.0.33+

### Environment Variables

- `KILO_SESSION_DIR`: Session directory (default: `.droid/consultations`)
- `KILO_TIMEOUT`: Default timeout in seconds (default: 600)
- `KILO_MODEL_CHEAP`: Cheap model (default: `kilo/google/gemini-3-flash-preview`)
- `KILO_MODEL_MID`: Mid-tier model (default: `kilo/openai/gpt-5.4`)
- `KILO_MODEL_EXPENSIVE`: Expensive model (default: `kilo/anthropic/claude-opus-4.6`)

---

## Constraints and Limitations

### No Autonomous Code Changes
- Pure Q&A only
- Kilo provides answers, Cascade applies fixes
- No auto-edit capabilities
- No autonomous code changes
- Requires Kilo CLI installed and accessible
- Model IDs must use `kilo/` prefix
- Uses stdin for question (not command-line argument)

### File Path Limitations
- Risk assessment based on path patterns only
- No content inspection
- High-risk paths hardcoded

### Session Scope
- Session state is per-file
- No cross-file session continuity
- Session files not automatically cleaned up

---

## Troubleshooting

### Model Not Found Error

**Error:** `Model not found: kilo/auto`

**Solution:** The script now uses actual model IDs instead of `kilo/auto`. If you see this error, update the script or use explicit `--model` flag.

### File Not Found Error

**Error:** `Error: File not found: <your question>`

**Solution:** This was fixed by using stdin for the question. Ensure you're using the latest version of the script.

### Kilo CLI Not Found

**Error:** `kilo: command not found`

**Solution:** Install Kilo CLI:
```bash
npm install -g @kilopk/cli
```

### Session Not Found

**Error:** Session state not found

**Solution:** Check the session ID or start a new consultation without `--session`.

### Timeout

**Error:** Command timed out after 120 seconds

**Solution:** Increase timeout with `--timeout` flag:
```bash
python scripts/kilo_consult.py --timeout 300 --file file.py "Question"
```

---

## Best Practices

1. **Use sessions for related questions** - Context carries forward via Q&A history
2. **Override model for critical questions** - Use `--model kilo/anthropic/claude-opus-4.6`
3. **Use risk assessment** - Let the script auto-select models based on file path
4. **Review session state** - Check `.droid/consultations/` for history
5. **Use --diff for stuck-on-changes** - Include git diff for context
6. **Configure models via env vars** - Set KILO_MODEL_* for custom model selection
7. **Follow question formulation best practices** - See "Question Formulation Best Practices" section for guidelines on asking effective questions and interpreting answers
8. **Verify critical suggestions** - Do not trust the answer 100%; always verify before applying changes

---

## Related Documentation

- **Kilo CLI Reference:** `docs/reference/kilo/KILO_CLI_REFERENCE.md`
- **Kilo Review Workflow:** `docs/workflows/KILO_REVIEW_WORKFLOW.md`
- **Kilo Dispatch Workflow:** `docs/workflows/KILO_DISPATCH_WORKFLOW.md`
- **Traycer-Kilo Agents Guide:** `docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md`

---

## Changelog

### 2026-04-15
- Initial implementation of `kilo_consult.py`
- Risk-based routing (direct risk-to-model mapping, no escalation)
- Session management with Q&A history (last 10 entries)
- Optional git diff context via --diff flag
- Configurable models via environment variables
- Fixed stdin input for Kilo CLI
- Fixed model selection (removed kilo/auto, use actual model IDs)
- Added session ID hash suffix to prevent collisions
- Added FileNotFoundError handling for kilo binary
- Added encoding='utf-8' to file I/O
- Capped history growth to 10 entries
- Don't save session state on failure (exit_code != 0)
