# Kilo Code Review Guide

**Last Updated:** 2026-05-20
**Script:** `scripts/kilo_code_review.py` (5600+ lines)
**Purpose:** Cost-aware, iterative AI code review with risk-based model routing, escalation, issue tracking, and token-lean defaults.

---

## Pipeline Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│ STEP 1: RISK ASSESSMENT                                           │
│   Path keywords: auth/, security/, payment/, secret/, crypt/      │
│   File content: password=, token=, api_key= patterns              │
│   Diff size: >400 lines = HIGH risk                               │
│   High-risk filenames: compose.yaml, Dockerfile, .env             │
│   Output: risk_level ∈ {low, medium, high, critical}             │
└───────────────────────────────────────────────────────────────────┘
                                ↓
┌───────────────────────────────────────────────────────────────────┐
│ STEP 2: TIER SELECTION                                             │
│   LOW      → free     → Free ($0)       [deepseek, minimax, qwen]│
│   MEDIUM   → economy  → Economy ($0.02) [gemini-flash, devstral] │
│   HIGH     → standard → Balanced ($0.50) [gpt-5.2-codex, glm-5]  │
│   CRITICAL → premium  → Strong ($3.00) [sonnet-4.6, gpt-5.3]     │
│   User overrides: --strategy, --model, --max-cost                 │
└───────────────────────────────────────────────────────────────────┘
                                ↓
┌───────────────────────────────────────────────────────────────────┐
│ STEP 3: REVIEW WITH RETRY LOOP                                     │
│   session_id preserved across all calls (cache hits ~30-50%)      │
│   On model error: track failed model → try next in tier → escalate│
│   Max 3 retry attempts per review                                 │
└───────────────────────────────────────────────────────────────────┘
                                ↓
┌───────────────────────────────────────────────────────────────────┐
│ STEP 4: FALSE NEGATIVE MITIGATION                                  │
│   IF verdict=PASS AND risk in {HIGH, CRITICAL}:                   │
│     Verify with stronger model (same session_id)                  │
│     IF issues found → log false negative, return verify result    │
│   Requires: KILO_ENABLE_PASS_VERIFY=1 (opt-in)                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Basic review (auto-selects model based on risk)
python scripts/kilo_code_review.py review src/myfile.py

# Review staged files
python scripts/kilo_code_review.py staged

# Free tier (development, iteration)
python scripts/kilo_code_review.py review src/ --strategy free

# Budget-constrained
python scripts/kilo_code_review.py review src/ --max-cost 0.50

# With plan for spec coverage validation
python scripts/kilo_code_review.py review src/ --plan "Add user authentication"

# Stats
python scripts/kilo_code_review.py stats --by-model --by-filetype --days 7
```

---

## Commands

| Command | Purpose |
|---|---|
| `review <files>` | Read-only review with model/strategy/plan options |
| `staged` | Review git staged files |
| `changed` | Review git changed files |
| `auto-fix <files>` | Review + fix loop (`--max-iterations 3`, `--min-severity MAJOR`) |
| `verify <files>` | Verify manual fixes (`--fixes "description"`) — lighter than full review |
| `stats` | Usage statistics (`--by-model`, `--by-filetype`, `--days N`) |

---

## Token-Lean Defaults

The script is optimized for solo dev token economy. Expensive features are opt-in:

| Feature | Default | Opt-in | Token impact |
|---|---|---|---|
| Review mode | `diff_only` | `--review-mode full` | diff_only saves ~60-75% |
| Multi-pass review | OFF | `KILO_ENABLE_MULTI_PASS=1` | Saves ~50% on PASS |
| PASS verification | OFF | `KILO_ENABLE_PASS_VERIFY=1` | Saves ~25% on PASS |
| Audit logging | OFF | `KILO_ENABLE_AUDIT=1` | Minimal overhead |

**Total PASS-case savings vs. all-on: ~75% fewer tokens.**

### When to use full mode

- Architectural changes spanning entire files
- Context from unmodified code is essential
- diff_only produces incomplete reviews

Oversized full prompts auto-degrade to diff_only before failing.

---

## Strategies

| Strategy | Starting tier | Escalation path | Max cost |
|---|---|---|---|
| `free` | Free ($0) | Free → Economy → Balanced → Strong | ~$3/review |
| `economy` | Economy (~$0.02/M) | Economy → Balanced → Strong → Prime | ~$5/review |
| `standard` | Balanced (~$0.5/M) | Balanced → Strong → Prime | ~$25/review |
| `premium` | Strong (~$3/M) | Strong → Prime | ~$50/review |
| `critical` | Prime (~$5/M) | Prime only | ~$50/review |

Without `--strategy`, auto-selected from file risk:

| Risk | Files | Auto strategy |
|---|---|---|
| LOW | `.md`, `.rst`, config | `free` |
| MEDIUM | Normal code | `economy` |
| HIGH | `src/`, `scripts/`, `.sh` | `standard` |
| CRITICAL | `auth/`, `security/`, payments | `premium` |

---

## Daily Workflow (Recommended)

```bash
# 1. Coder implements feature
# 2. Run final gate (deterministic checks)
python /opt/fabrik/scripts/final_gate.py

# 3. Stage intended files
git add <files>

# 4. Initial review with tracked ID
export REVIEW_ID="feat-auth-$(date +%Y%m%d)"
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Brief micro-spec" \
  --review-agent ask \
  --output json

# 5. Coder fixes issues

# 6. Verify fixes (lighter than full review)
python scripts/kilo_code_review.py verify <changed_files> \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --fixes "Fixed auth validation edge case"

# 7. Repeat verify until verdict=PASS (max 5 iterations)

# 8. Run final gate again
python /opt/fabrik/scripts/final_gate.py

# 9. Commit
```

### When to use verify vs full review

| Use verify | Use full review |
|---|---|
| After minor fixes (1-3 issues) | Auth/security/migrations changed |
| Fix is localized to one module | Fix touched multiple modules |
| Previous review was recent (<1 hour) | Previous findings were architectural |
| | >24 hours since last review |

---

## Micro-Spec Format (`--plan`)

Pass concise specs, not full plans. The script extracts numbered requirements for plan coverage validation.

```text
Objective:
<one sentence>

Non-goals:
- ...

Requirements:
REQ-1: ...
REQ-2: ...

Acceptance checks:
- ...

Touched modules:
- path/a
- path/b
```

**Do NOT pass:** brainstorm text, roadmap, rationale, alternatives considered, long architectural discussions. They inflate prompt size without adding review value.

---

## Session & Issue Tracking

### Scoped sessions

Sessions are scoped by project root + git branch + tracked review ID. Prevents cross-branch pollution.

```bash
--session continue --tracked-review-id "$REVIEW_ID"
```

### Issue-state persistence

Issues are fingerprinted by (tracked_review_id, file, lines, category, why) and tracked in:

```
.droid/reviews/<tracked_review_id>_issues.json
```

| Status | Meaning |
|---|---|
| `open` | Issue still present |
| `fixed` | Was open, now absent |
| `rejected` | Manually marked false positive |

No duplicate reporting across iterations.

```python
# Get open issues for coder feedback
from scripts.kilo_code_review import get_open_issues
issues = get_open_issues("feat-auth-20260520")
```

### Reviewer setting freeze

Keep settings constant within one `tracked_review_id`:

```bash
export REVIEW_AGENT="ask"
export STRATEGY="economy"
export VARIANT="high"
# Use same values for ALL reviews in this cycle
```

---

## Semantic Batching

Group files by subsystem before calling the script:

```bash
# Auth files together
python scripts/kilo_code_review.py staged \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Auth spec" \
  $(git diff --cached --name-only | grep -E 'auth|security')

# API files together
python scripts/kilo_code_review.py staged \
  --tracked-review-id "$REVIEW_ID" \
  --plan "API spec" \
  $(git diff --cached --name-only | grep -E 'api|routes')
```

**Rule:** If >5 staged files span unrelated areas, don't send as one mixed batch.

---

## Escalation Behavior

### When escalation happens

1. **Model error** — timeout, API failure, rate limit → retry next model in tier → escalate tier
2. **Zero findings on high-risk code** — false negative mitigation (if `KILO_ENABLE_PASS_VERIFY=1`)
3. **Budget allows** — respects `--max-cost` and `--no-escalate`

### Preventing escalation

```bash
--no-escalate        # Stay at initial tier
--max-cost 0.50      # Cap by cost
```

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `KILO_REVIEW_MODEL` | `kilo/auto` | Force specific model |
| `KILO_IDLE_TIMEOUT` | `120` | Kill if no output for N seconds |
| `KILO_HARD_TIMEOUT` | `1200` | Absolute max runtime |
| `KILO_POLL_INTERVAL` | `2` | Health check interval |
| `KILO_ENABLE_MULTI_PASS` | `0` | Multi-pass review (opt-in) |
| `KILO_ENABLE_PASS_VERIFY` | `0` | Verify PASS on high-risk (opt-in) |
| `KILO_ENABLE_AUDIT` | `0` | Audit logging (opt-in) |
| `KILO_DEFAULT_STRATEGY` | (auto) | Default cost strategy |
| `KILO_MAX_COST` | None | Max cost per review |
| `KILO_HIGH_RISK_PATHS` | (built-in) | Extra high-risk paths (`custom/,extra/`) |
| `KILO_TRACK_COST` | `0` | Per-agent cost tracking |
| `KILO_DEBUG` | `0` | Debug output |

---

## See Also

- [KILO_PERFORMANCE_TUNING.md](KILO_PERFORMANCE_TUNING.md) — Context management, token optimization, speed tuning
- [KILO_USAGE_GUIDE.md](KILO_USAGE_GUIDE.md) — Skills, MCP, workflows, autonomous mode
- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) — Automated model routing
- [KILO_TROUBLESHOOTING.md](KILO_TROUBLESHOOTING.md) — Common issues
- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) — Programmatic integration patterns (liveness monitoring, JSONL parsing, retry)
