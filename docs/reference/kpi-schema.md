# KPI Event Schema

**Last Updated:** 2026-02-20

This document defines the schema for KPI events stored in `.droid/kpis.jsonl`.

## Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["event_id", "event_type", "timestamp", "task_id"],
  "properties": {
    "event_id": {
      "type": "string",
      "description": "UUID v4 or v5 unique identifier"
    },
    "event_type": {
      "type": "string",
      "enum": ["task_start", "task_end", "review_start", "review_end", "error"]
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp"
    },
    "task_id": {
      "type": "string",
      "description": "UUID linking start/end events"
    },
    "session_id": {
      "type": "string",
      "description": "Optional session identifier"
    },
    "model": {
      "type": "string",
      "description": "Model name used for the task"
    },
    "tokens_input": {
      "type": "integer",
      "description": "Input tokens consumed"
    },
    "tokens_output": {
      "type": "integer",
      "description": "Output tokens generated"
    },
    "duration_seconds": {
      "type": "number",
      "description": "Task duration in seconds"
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure", "error"]
    },
    "error_message": {
      "type": "string",
      "description": "Sanitized error message (no PII)"
    }
  }
}
```

## Example Events

```jsonl
{"event_id": "550e8400-e29b-41d4-a716-446655440000", "event_type": "task_start", "timestamp": "2026-02-19T10:30:00Z", "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
{"event_id": "550e8400-e29b-41d4-a716-446655440001", "event_type": "task_end", "timestamp": "2026-02-19T10:35:00Z", "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "model": "claude-sonnet-4-6", "tokens_input": 1500, "tokens_output": 800, "duration_seconds": 300.5, "status": "success"}
{"event_id": "550e8400-e29b-41d4-a716-446655440002", "event_type": "error", "timestamp": "2026-02-19T11:00:00Z", "task_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012", "error_message": "API rate limit exceeded"}
```

## PII Handling

| Field | Policy | Retention |
|-------|--------|-----------|
| `prompt_text` | **NEVER STORED** | N/A |
| `error_message` | Sanitized (paths, traces, secrets stripped) | 30 days |
| `task_id` | Rotated periodically | 90 days |
| `session_id` | Rotated periodically | 90 days |

## Retention Commands

```bash
# Remove events older than 90 days
python scripts/kpi_tracker.py prune --older-than 90d

# Sanitize error_message fields (strip paths, traces, secrets)
python scripts/kpi_tracker.py sanitize --field error_message
```

## Valid Event Types

| Type | Description |
|------|-------------|
| `task_start` | Task execution begins |
| `task_end` | Task execution completes |
| `review_start` | Code review begins |
| `review_end` | Code review completes |
| `error` | Error event |

## See Also

- `scripts/kpi_tracker.py` — CLI tool for KPI management
- `.droid/kpis.jsonl` — Event storage location
