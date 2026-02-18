# GAP-04 KPI Dashboard — Spec-Level Implementation Plan

**Version:** 1.1.0  
**Revision Date:** 2026-02-17  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-04 v1.0  
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap04-kpi-dashboard.md`

---

## Implementation Readiness Checklist

> **Pre-implementation step:** Before starting, verify repo paths exist and run the canonical gate on a clean checkout. Check boxes as verified.

- [ ] **Spec-Level Implementation Plan (implementable specs) attached**
- [ ] Repo grounding paths verified (all referenced files/dirs either exist or are explicitly CREATE)
- [ ] Required Artifacts list complete (CREATE/MODIFY + exact paths)
- [ ] Deterministic Gate is **one exact command** (copy/paste) and passes on a clean checkout
- [ ] DONE WHEN criteria are measurable and mapped to artifacts + gate output
- [ ] Failure modes/rollback defined (even if minimal)

---

## Artifacts Table

| Path | Action | Purpose | Gate Coverage |
|------|--------|---------|---------------|
| `scripts/kpi_tracker.py` | CREATE | KPI CLI tool | `python scripts/kpi_tracker.py --help` |
| `docs/reference/kpi-schema.md` | CREATE | Schema documentation | `test -f docs/reference/kpi-schema.md` |
| `tests/test_kpi_tracker.py` | CREATE | Unit tests | `pytest tests/test_kpi_tracker.py -v` |
| `scripts/droid-review.sh` | MODIFY | Add KPI emission | `grep "kpis.jsonl" scripts/droid-review.sh` |
| `.droid/kpis.jsonl` | CREATE (runtime) | KPI event storage | Schema validation |
| `CHANGELOG.md` | MODIFY | Document GAP-04 | Manual verify |

---

## KPI Data Contract

### Metric Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `<action>_<object>_<unit>` | `tokens_used_total` | Counter |
| `<object>_<property>` | `task_duration_seconds` | Measurement |
| `<object>_<status>_count` | `review_pass_count` | Status counter |

**Rules:**
- All names: `snake_case`
- No abbreviations (except `id`, `uuid`)
- Units always explicit (seconds, count, total)

### Schema Validation Command

```bash
# Validate KPI event schema
python -c "
import json, sys
from pathlib import Path

kpi_file = Path('.droid/kpis.jsonl')
if not kpi_file.exists():
    print('No KPI file yet (OK for new setup)')
    sys.exit(0)

required = ['event_id', 'event_type', 'timestamp', 'task_id']
valid_types = ['task_start', 'task_end', 'review_start', 'review_end', 'error']

errors = []
for i, line in enumerate(kpi_file.read_text().strip().split('\n'), 1):
    if not line: continue
    try:
        event = json.loads(line)
        missing = [f for f in required if f not in event]
        if missing:
            errors.append(f'Line {i}: Missing {missing}')
        if event.get('event_type') not in valid_types:
            errors.append(f'Line {i}: Invalid event_type')
    except json.JSONDecodeError as e:
        errors.append(f'Line {i}: Invalid JSON: {e}')

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('✓ KPI schema valid')
"
```

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── scripts/
│   ├── .droid_token_usage.jsonl   # Token log (EXISTS)
│   ├── droid_core.py              # Core execution
│   └── droid-review.sh            # Review wrapper
├── .droid/
│   └── (runtime data)             # Session data
└── docs/
    └── reference/                  # For KPI schema doc
```

### B. GAP-04 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `.droid_token_usage.jsonl` | **FOUND** | `scripts/` | **READ** — data source |
| `scripts/droid-review.sh` | **FOUND** | `scripts/` | **MODIFY** — emit KPI events |
| `scripts/kpi_tracker.py` | **NOT FOUND** | `scripts/` | **CREATE** required |
| `.droid/kpis.jsonl` | **NOT FOUND** | `.droid/` | **CREATE** (runtime data) |
| `docs/reference/kpi-schema.md` | **NOT FOUND** | `docs/reference/` | **CREATE** required |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| Token log format incompatible | Adapt parser | Document format requirements |
| No .droid directory | Create directory | Use scripts/ instead |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `scripts/kpi_tracker.py` | **CREATE** | GAP-04 DONE WHEN: CLI exists | — | **L** (~200 lines) |
| `scripts/droid-review.sh` | **MODIFY** | Emit KPI events | Core review logic | **S** (~10 lines) |
| `.droid/kpis.jsonl` | **CREATE** (runtime) | Data storage | — | N/A |
| `docs/reference/kpi-schema.md` | **CREATE** | Documentation | — | **M** (~60 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |
| `tests/test_kpi_tracker.py` | **CREATE** | Unit tests required | — | **M** (~80 lines) |
| `.github/workflows/ci.yml` | **MODIFY** | CI integration | Other steps | **S** (~10 lines) |

**Explicitly NOT created/modified:**
- `scripts/droid_core.py` — Token logging unchanged
- Web dashboard — OUT OF SCOPE (CLI only)
- Real-time streaming — OUT OF SCOPE

---

## 3. Interface & Contract Specification

### A. KPI Event Schema (JSONL)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["event_id", "event_type", "timestamp", "task_id"],
  "properties": {
    "event_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique event identifier for idempotency"
    },
    "event_type": {
      "type": "string",
      "enum": ["task_start", "task_end", "review_start", "review_end", "error"]
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "task_id": {
      "type": "string",
      "description": "Unique task identifier"
    },
    "session_id": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "tokens_input": {
      "type": "integer"
    },
    "tokens_output": {
      "type": "integer"
    },
    "duration_seconds": {
      "type": "number"
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure", "timeout"]
    },
    "error_message": {
      "type": "string"
    }
  }
}
```

### B. Example KPI Events

```jsonl
{"event_id": "550e8400-e29b-41d4-a716-446655440001", "event_type": "task_start", "timestamp": "2026-02-16T14:30:00Z", "task_id": "task_abc123", "session_id": "sess_xyz", "model": "gpt-5.3-codex"}
{"event_id": "550e8400-e29b-41d4-a716-446655440002", "event_type": "task_end", "timestamp": "2026-02-16T14:32:30Z", "task_id": "task_abc123", "tokens_input": 1500, "tokens_output": 800, "duration_seconds": 150, "status": "success"}
{"event_id": "550e8400-e29b-41d4-a716-446655440003", "event_type": "review_start", "timestamp": "2026-02-16T14:32:31Z", "task_id": "task_abc123", "model": "gpt-5.3-codex"}
```

### C. CLI Contract

**Command syntax:**
```bash
python scripts/kpi_tracker.py <command> [options]
```

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `summary` | Show KPI summary for time range |
| `export` | Export KPIs to CSV/JSON |
| `ingest` | Ingest from token log |
| `--help` | Show help |

**Flags for `summary`:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--since` | date | no | 7d ago | Start date |
| `--until` | date | no | now | End date |
| `--model` | string | no | all | Filter by model |
| `--format` | choice | no | table | Output: `table`, `json`, `csv` |

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | No data found |
| `2` | Parse error |
| `3` | File not found |

### D. Summary Output Format

```
KPI Summary (2026-02-10 to 2026-02-16)
======================================
Total tasks:        47
Success rate:       91.5%
Avg duration:       2.3 min
Total tokens:       125,430
  - Input:          89,200
  - Output:         36,230
Cost estimate:      $4.52

By Model:
  gpt-5.3-codex:    28 tasks, 94% success
  swe-1-5:          12 tasks, 83% success
  gemini-3-flash:   7 tasks, 100% success
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: View KPI Summary

**Command:**
```bash
python scripts/kpi_tracker.py summary --since 2026-02-10
```

**Expected output:**
```
KPI Summary (2026-02-10 to 2026-02-16)
======================================
Total tasks:        47
Success rate:       91.5%
...
```

**Expected exit code:** `0`

---

### Golden Path 2: Export to JSON

**Command:**
```bash
python scripts/kpi_tracker.py export --format json --since 2026-02-15 > kpis.json
```

**Expected output file:**
```json
{
  "period": {"start": "2026-02-15", "end": "2026-02-16"},
  "summary": {
    "total_tasks": 12,
    "success_rate": 0.917,
    "total_tokens": 28450
  },
  "events": [...]
}
```

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **KPI file not found** | FileNotFoundError | Create empty `.droid/kpis.jsonl`, return code 0 with warning | None |
| 2 | **Malformed JSONL line** | JSONDecodeError | Skip line, log to stderr with line number, continue processing | None |
| 3 | **Duplicate event_id** | Hash set collision | Skip duplicate, log info level, continue | None |
| 4 | **Token log format change** | KeyError on required field | Print specific missing field, return code 2 | None |
| 5 | **No events in range** | Empty result | Print "No data for period", return code 1 | None |
| 6 | **File permission denied** | PermissionError | Print path and required permissions, return code 3 | None |
| 7 | **Disk full on write** | OSError | Print error, do NOT corrupt existing file, return code 3 | Keep original file |
| 8 | **Schema validation failure** | jsonschema.ValidationError | Log invalid event, skip, increment error counter | None |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
python scripts/kpi_tracker.py --help && \
python scripts/kpi_tracker.py summary --format json 2>/dev/null | jq '.summary' && \
echo "PASS"
```

**Expected PASS output:**
```
usage: kpi_tracker.py [-h] {summary,export,ingest} ...
...
{
  "total_tasks": ...,
  "success_rate": ...
}
PASS
```

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

After **every step**, builder/verifier MUST output:

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [ ] Schema matches spec
- [ ] Idempotency via event_id
- [ ] Type hints complete

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| `droid-review.sh` | Emits KPI events |
| `.droid_token_usage.jsonl` | Read for ingestion |
| `.droid/` directory | Stores KPI data |

### Invariants (Hard Rules)

- **MUST use:** UUID v4 for event_id (idempotency)
- **MUST use:** ISO 8601 timestamps
- **MUST NOT modify:** Token logging in droid_core.py
- **MUST handle:** Partial/incomplete sessions gracefully
- **MUST validate:** Schema on ingest (reject invalid events)
- **MUST have:** Unit tests with >80% coverage

### PII & Data Retention Policy (MANDATORY)

| Data Type | PII Risk | Retention | Handling |
|-----------|----------|-----------|----------|
| `task_id` | Low | 90 days | Auto-rotate via `kpi_tracker.py prune` |
| `session_id` | Low | 90 days | Auto-rotate |
| `model` | None | Indefinite | Keep |
| `tokens_*` | None | Indefinite | Keep |
| `error_message` | **Medium** | 30 days | May contain stack traces, sanitize |
| `prompt_text` | **High** | **NEVER STORE** | Excluded from schema |

**Retention Commands:**
```bash
# Prune events older than 90 days
python scripts/kpi_tracker.py prune --older-than 90d

# Sanitize error messages (remove potential secrets)
python scripts/kpi_tracker.py sanitize --field error_message
```

**Hard Rules:**
- **NEVER log:** Full prompts, API keys, user content
- **MUST sanitize:** Error messages containing paths or stack traces
- **MUST support:** `prune` command for GDPR compliance

### Idempotency Mechanism

```
┌─────────────────────────────────────────┐
│ Idempotency Rules                       │
├─────────────────────────────────────────┤
│ 1. event_id = UUID v4 (unique per emit) │
│ 2. task_id = stable across retries      │
│ 3. Duplicate event_id = skip silently   │
│ 4. Missing end event = mark incomplete  │
└─────────────────────────────────────────┘
```

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Create KPI Schema Documentation

```text
DO:
- Create docs/reference/kpi-schema.md
- Document JSON schema from Section 3.A
- Include example events from Section 3.B
- Document required vs optional fields
- Add PII handling section from Section 8

GATE:
test -f docs/reference/kpi-schema.md && grep "event_id" docs/reference/kpi-schema.md

EVIDENCE REQUIRED:
- kpi-schema.md file exists
- Contains JSON schema definition
- Contains example events

SELF-REVIEW (Builder):
- [ ] Schema matches Section 3.A exactly
- [ ] Examples are valid JSON
- [ ] PII handling documented

MODE 4 VERIFICATION:
- Verifier audits: Schema complete? Examples valid? PII documented?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create kpi_tracker.py Skeleton

```text
DO:
- Create scripts/kpi_tracker.py
- Implement CLI with argparse:
  - summary subcommand
  - export subcommand
  - ingest subcommand
  - prune subcommand
  - sanitize subcommand
- Add type annotations on all functions
- Define KPIEvent dataclass matching schema

GATE:
python scripts/kpi_tracker.py --help

EVIDENCE REQUIRED:
- --help output shows all subcommands
- No import errors

SELF-REVIEW (Builder):
- [ ] Type annotations on all functions
- [ ] KPIEvent dataclass matches schema
- [ ] All subcommands listed in --help

PRE-FLIGHT GATES:
ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Types? CLI structure? Schema compliance?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Implement Summary Command

```text
DO:
- Implement summary subcommand in kpi_tracker.py
- Read from .droid/kpis.jsonl
- Calculate: total tasks, success rate, avg duration, total tokens, cost estimate
- Group by model
- Support --since, --until, --model, --format flags

GATE:
python scripts/kpi_tracker.py summary --format json 2>/dev/null | jq '.summary'

EVIDENCE REQUIRED:
- Summary output matches format in Section 3.D
- JSON output is valid

SELF-REVIEW (Builder):
- [ ] Handles missing file gracefully (creates empty)
- [ ] Handles malformed lines (skips, logs warning)
- [ ] Output format matches spec

PRE-FLIGHT GATES:
ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Output format? Error handling? Calculations correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Implement Export Command

```text
DO:
- Add export subcommand to kpi_tracker.py
- Support --format json and --format csv
- Support --since, --until filters
- Output to stdout or file

GATE:
python scripts/kpi_tracker.py export --format json --since 2026-02-01 | head -5

EVIDENCE REQUIRED:
- Export produces valid JSON/CSV
- Filters work correctly

SELF-REVIEW (Builder):
- [ ] JSON output is valid JSON
- [ ] CSV has proper headers
- [ ] Date filters work correctly

PRE-FLIGHT GATES:
ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Output formats valid? Filters work?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Implement Ingest from Token Log

```text
DO:
- Add ingest subcommand
- Parse scripts/.droid_token_usage.jsonl
- Convert to KPI event format
- Handle duplicate event_id (skip, log)
- Handle malformed lines (skip, log warning with line number)

GATE:
python scripts/kpi_tracker.py ingest && echo "INGEST OK"

EVIDENCE REQUIRED:
- Ingest runs without error
- Events appear in .droid/kpis.jsonl

SELF-REVIEW (Builder):
- [ ] Idempotency via event_id (duplicates skipped)
- [ ] Malformed lines handled gracefully
- [ ] Line number included in warnings

PRE-FLIGHT GATES:
ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Idempotency? Error handling? Data integrity?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Implement Prune and Sanitize Commands

```text
DO:
- Add prune subcommand: python scripts/kpi_tracker.py prune --older-than 90d
- Add sanitize subcommand: python scripts/kpi_tracker.py sanitize --field error_message
- Prune removes events older than threshold
- Sanitize removes potential secrets from specified fields

GATE:
python scripts/kpi_tracker.py prune --help && python scripts/kpi_tracker.py sanitize --help

EVIDENCE REQUIRED:
- Both commands show help
- No errors

SELF-REVIEW (Builder):
- [ ] Prune respects retention policy (90 days default)
- [ ] Sanitize removes paths, stack traces, potential secrets
- [ ] Both commands are non-destructive (backup or dry-run option)

PRE-FLIGHT GATES:
ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Retention correct? Sanitization thorough?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Create Unit Tests

```text
DO:
- Create tests/test_kpi_tracker.py
- Test cases:
  - test_schema_validation_valid_event()
  - test_schema_validation_invalid_event()
  - test_idempotency_duplicate_event_id()
  - test_file_corruption_malformed_jsonl()
  - test_empty_file_handling()
  - test_summary_calculation()
  - test_prune_retention()

GATE:
pytest tests/test_kpi_tracker.py -v --cov=scripts.kpi_tracker --cov-fail-under=80

EVIDENCE REQUIRED:
- All tests pass
- Coverage >= 80%

SELF-REVIEW (Builder):
- [ ] Schema validation tested (valid/invalid)
- [ ] Idempotency tested
- [ ] Error handling tested
- [ ] Coverage > 80%

PRE-FLIGHT GATES:
ruff check tests/test_kpi_tracker.py && mypy tests/test_kpi_tracker.py

MODE 4 VERIFICATION:
- Verifier audits: Tests comprehensive? Coverage sufficient?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 8 — Modify droid-review.sh for KPI Emission

```text
DO:
- Add KPI event emission to scripts/droid-review.sh
- Emit task_start event at beginning
- Emit task_end event at end with status
- Use UUID for event_id
- Write to .droid/kpis.jsonl

GATE:
grep "kpis.jsonl" scripts/droid-review.sh

EVIDENCE REQUIRED:
- droid-review.sh emits events
- Events match schema

SELF-REVIEW (Builder):
- [ ] UUID generation for event_id
- [ ] ISO 8601 timestamps
- [ ] Both start and end events emitted
- [ ] Status captured (success/failure)

MODE 4 VERIFICATION:
- Verifier audits: Event format? Schema compliance? Integration correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 9 — Final Verification

```text
DO:
- Run full test suite: pytest tests/test_kpi_tracker.py -v
- Run a test review to generate KPI events
- Run summary to verify data appears
- Update CHANGELOG.md

GATE (CANONICAL):
python scripts/kpi_tracker.py --help && \
python scripts/kpi_tracker.py summary --format json 2>/dev/null | jq '.summary' && \
echo "PASS"

EVIDENCE REQUIRED:
- All tests pass
- Summary shows data
- CHANGELOG updated

SELF-REVIEW (Builder):
- [ ] CLI works end-to-end
- [ ] Tests pass with >80% coverage
- [ ] PII handling verified

MODE 4 VERIFICATION (FINAL):
- Verifier audits: All features work? Tests pass? Ready to use?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- .droid_token_usage.jsonl format incompatible
- .droid/ directory cannot be created
- jsonschema library not available

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `kpi_tracker.py`, `kpi-schema.md`, `test_kpi_tracker.py` |
| Files to MODIFY | `droid-review.sh`, `CHANGELOG.md`, `ci.yml` |
| Runtime data | `.droid/kpis.jsonl` |
| Canonical Gate | CLI works, summary returns data |
| Schema | JSONL with UUID event_id for idempotency |
| Tests | Unit tests with >80% coverage |
| Retention | 90 days default, `prune` command for cleanup |

**All sections complete.** Ready for Mode 3 (Build) execution.
