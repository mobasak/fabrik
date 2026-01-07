# PHASE B — EXECUTION PLAN TEMPLATE

Use this **only after exploration is finished and the plan is locked**.

---

## EXECUTION MODE HEADER (mandatory)

```text
MODE: EXECUTION (PLAN LOCKED)

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope
- One step at a time
- After each step: show Evidence + Gate result
- If a Gate fails or is unclear → STOP and report
```

---

## TASK METADATA

```text
TASK:
<short name>

GOAL:
<1 sentence: what must work when finished>

DONE WHEN (all true):
- <primary observable behavior>
- <secondary safety/edge behavior if relevant>
- Gate command passes: <single canonical command>

OUT OF SCOPE:
- <explicit exclusions>
```

---

## GLOBAL CONSTRAINTS (optional but useful)

```text
CONSTRAINTS:
- Language / framework: <…>
- No new deps unless stated
- Follow patterns in: <paths>
- Backward compatibility: <yes/no>
```

---

## CANONICAL GATE (recommended)

If possible, define **one command** reused across steps.

```text
CANONICAL GATE:
<e.g. pytest -q | make test | npm test | fabrik apply --dry-run fixtures/x.yml>
```

Steps may add a *local* gate only if necessary.

---

## EXECUTION STEPS (5–7 MAX)

### Step 1 — Skeleton / wiring

```text
DO:
- Create files / modules:
  - <path>
  - <path>
- Add interfaces / stubs only

GATE:
- <import / build / typecheck command>

EVIDENCE REQUIRED:
- File list changed
- Gate output
```

---

### Step 2 — Core logic A

```text
DO:
- Implement <component A>
- Minimal tests if applicable

GATE:
- <test command OR canonical gate>

EVIDENCE REQUIRED:
- Files changed
- Gate output
```

---

### Step 3 — Core logic B

```text
DO:
- Implement <component B>

GATE:
- <test or canonical gate>

EVIDENCE REQUIRED:
- Files changed
- Gate output
```

---

### Step 4 — Integration

```text
DO:
- Wire components together
- Connect to CLI / entrypoint / orchestrator

GATE:
- <smoke run OR canonical gate>

EVIDENCE REQUIRED:
- Files changed
- Command output
```

---

### Step 5 — Failure / rollback path (if applicable)

```text
DO:
- Implement error handling / rollback logic

GATE:
- <simulated failure OR test>

EVIDENCE REQUIRED:
- Files changed
- Gate output
```

---

### Step 6 — Final verification

```text
DO:
- Run full flow

GATE:
- CANONICAL GATE passes

EVIDENCE REQUIRED:
- Final command output
```

---

## STOP CONDITIONS (important)

```text
STOP IF:
- A gate cannot be satisfied
- Unexpected existing behavior is discovered
- Required external input/credential is missing

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

```text
STEP <N> STATUS: PASS / FAIL

Changed files:
- <path>
- <path>

Gate output:
<pasted output>

Next:
- Proceed to Step <N+1> OR STOP
```
