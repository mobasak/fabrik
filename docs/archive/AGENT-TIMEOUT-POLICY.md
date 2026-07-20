# Traycer Agent Timeout Policy

**Last Updated:** 2026-03-16
**Default Timeout:** 120 minutes (7200 seconds)

---

## Current Configuration

All Traycer CLI agents are configured with a **120-minute default timeout**.

### Timeout Values by Tier

| Tier | Default Timeout | Override Env Var |
|------|----------------|------------------|
| All Tiers | 120 minutes | `KILO_TIMEOUT` |

---

## Rationale

### Why 120 Minutes?

1. **Large document reviews** - Architectural docs (500+ lines) with multi-pass review
2. **Complex implementations** - Features requiring multiple file edits + tests
3. **Token-heavy tasks** - 300k+ token processing across multiple models
4. **Escalation chains** - 4+ model attempts in review workflow

### Previous Timeout Issues

**2026-03-16 12:31** - Initial agents had 30-minute timeout
**Problem:** WordPress integration doc (984 lines) timed out during Kilo review
**Root cause:** Multi-pass review (2x general + security) × 4 models = exceeded 30 min

**2026-03-16 13:14** - Increased to 60 minutes
**Problem:** Still insufficient for very large documents with full escalation

**2026-03-16 14:24** - Increased to 120 minutes
**Status:** ✅ Sufficient for all current use cases

---

## Override Mechanism

Set custom timeout via environment variable:

```bash
# 240 minutes (4 hours) for extremely complex tasks
export KILO_TIMEOUT=14400

# Run agent
~/.traycer/cli-agents/T4-Pro10-gpt54-code-max-i250-o1500.sh
```

---

## Implementation

### Location

**File:** `/opt/fabrik/scripts/generate_kilo_agents.py`
**Line:** 357

```python
# Timeout protection (default 120 minutes)
TIMEOUT="${{KILO_TIMEOUT:-7200}}"
```

### Generated Agents

All agents in `~/.traycer/cli-agents/` inherit this timeout:
- 14 active agents
- 39 disabled agents (also use 120-min default)

### Regeneration

To apply timeout changes:
```bash
python /opt/fabrik/scripts/generate_kilo_agents.py
```

This regenerates all 53 agent scripts with the new timeout.

---

## Monitoring

### Agent Debug Log

Timeout events are logged to `~/.traycer/agent-debug.log`:

```bash
[2026-03-16T14:25:00+03:00] Agent started: T4-Pro10-gpt54-code-max
[2026-03-16T14:25:45+03:00] Timeout: 7200 seconds
```

### Exit Code

Timeout triggers exit code **124**:
```json
{"error": "timeout", "duration": 7200, "agent": "T4-Pro10-gpt54-code-max-i250-o1500"}
```

---

## Cost Implications

Longer timeouts do NOT increase cost directly:
- Cost = tokens consumed, not time elapsed
- Timeout is a safety ceiling, not a minimum duration
- Most tasks complete in 2-10 minutes regardless of timeout

**Example:** A 5-minute task costs the same with 60-min or 120-min timeout.

---

## When to Adjust

### Increase Timeout If:
- Consistent timeout failures on valid tasks
- Epic-level planning (multi-phase features)
- Batch operations (50+ files)
- Deep security audits

### Decrease Timeout If:
- Running low-priority background tasks
- Want fail-fast behavior for experiments
- Concerned about runaway processes

---

## Related Configuration

| Setting | Default | Override |
|---------|---------|----------|
| Agent timeout | 120 min | `KILO_TIMEOUT` |
| Session title | Phase ID | `TRAYCER_PHASE_ID` |
| Debug mode | Off | `KILO_DEBUG=1` |
| Cost tracking | Off | `KILO_TRACK_COST=1` |

---

## Testing

Verify timeout setting:
```bash
grep "TIMEOUT=" ~/.traycer/cli-agents/*.sh | head -1
# Expected: TIMEOUT="${KILO_TIMEOUT:-7200}"
```

Test timeout behavior:
```bash
KILO_DEBUG=1 ~/.traycer/cli-agents/T4-Pro10-gpt54-code-max-i250-o1500.sh
# Should log: [DEBUG] Timeout: 7200 seconds
```

---

## History

| Date | Timeout | Reason |
|------|---------|--------|
| 2026-03-16 12:31 | 30 min | Initial generation |
| 2026-03-16 13:14 | 60 min | Fix timeout failures |
| 2026-03-16 14:24 | 120 min | Support large docs + escalation |

---

**Recommendation:** Keep 120 minutes as default. Override per-task if needed via `KILO_TIMEOUT`.
