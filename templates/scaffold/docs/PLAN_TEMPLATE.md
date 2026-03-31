# Plan Template

**Project:** [PROJECT_NAME]
**Created:** YYYY-MM-DD
**Author:** [Traycer / Your Name]
**Status:** Draft / In Progress / Completed

---

## Objective

[One-sentence summary of what this plan achieves]

---

## Plan Quality Gate ✅

**Before handing off to Coder, confirm ALL items:**

- [ ] **Functional spec** — Exact behavior defined, not just goals
- [ ] **Edge cases** — Boundaries, null paths, failure states documented
- [ ] **Required env vars** — New or changed variables listed with defaults
- [ ] **DB changes** — Schema changes, migrations, indexes specified
- [ ] **Docs impact** — CHANGELOG category, README features table updates
- [ ] **Out of scope** — Explicitly stated what is NOT included

**If any item is unchecked, DO NOT proceed to implementation.**

---

## Functional Specification

### What This Does

[Detailed description of exact behavior]

### What This Does NOT Do (Out of Scope)

- Explicitly list what is deferred or not included
- Prevents scope creep

---

## Edge Cases & Failure Modes

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty input | Return 400 with error message |
| Database unavailable | Retry 3x, then return 503 |
| Invalid auth token | Return 401 |
| Rate limit exceeded | Return 429 with retry-after header |

---

## Environment Variables

### New Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `NEW_API_KEY` | string | Yes | — | API key for external service |
| `TIMEOUT_SECONDS` | int | No | `30` | Request timeout |

### Changed Variables

| Variable | Old Default | New Default | Reason |
|----------|-------------|-------------|--------|
| `MAX_RETRIES` | `3` | `5` | Increased for reliability |

**Action:** Update `.env.example` with inline comments.

---

## Database Changes

### Schema Changes

```sql
-- YYYY-MM-DD: Add user preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
```

### Migrations

- [ ] Migration script created: `db/migrations/YYYY_MM_DD_add_user_preferences.sql`
- [ ] Migration tested on dev database
- [ ] Rollback script prepared (if needed)

**Action:** Document in `docs/database/schema.md`.

---

## Documentation Impact

### CHANGELOG.md

**Category:** Added / Changed / Fixed / Removed / Security

**Entry:**
```
### Added — User Preferences API (YYYY-MM-DD)
- Add `POST /api/preferences` endpoint to store user settings
- Add `GET /api/preferences` endpoint to retrieve settings
- Add `user_preferences` table with JSONB storage
```

### README.md

**Update:** Features table, add row for "User Preferences Management"

### API Reference

**New docs:** `docs/reference/preferences.md` — document `/api/preferences` endpoints

---

## Testing Requirements

### Unit Tests

- [ ] Test `save_preferences()` with valid input
- [ ] Test `save_preferences()` with invalid user_id
- [ ] Test `get_preferences()` with existing user
- [ ] Test `get_preferences()` with non-existent user

### Integration Tests

- [ ] Test POST /api/preferences → 201 response
- [ ] Test GET /api/preferences → 200 with data
- [ ] Test authentication required for both endpoints

---

## Implementation Phases

### Phase 1: Database Setup

1. Create migration script
2. Apply to dev database
3. Verify schema with `\d user_preferences`

### Phase 2: API Endpoints

1. Implement `POST /api/preferences`
2. Implement `GET /api/preferences`
3. Add authentication middleware
4. Write tests

### Phase 3: Documentation

1. Update CHANGELOG.md (written by agent, gate-enforced)
2. Update README.md features table (if new feature)
3. Update API reference (if new endpoints)

---

## Agent Execution Contract (4 Steps)

**Authority:** `AGENTS-compact.md`

| Step | Action | Status |
|------|--------|--------|
| 1 — IMPLEMENT | Changes scoped to current task + internal audit | ⏳ |
| 2 — QUALITY GATE | `python scripts/final_gate.py --lean --json` → fix until `"status": "success"` | ⏳ |
| 3 — CHANGELOG | Add one entry under `## [Unreleased]` (gate enforces) | ⏳ |
| 4 — EXIT 0 | Gate auto-stages. Do not commit or stage manually | ⏳ |

**Optional tools (use only if explicitly requested):**
- Kilo Review: `python scripts/kilo_code_review.py staged --plan "..." --output json`
- Documentator: `python scripts/kilo_docs_enforcer.py --auto-generate --verbose`

---

## Success Criteria

- [ ] All edge cases handled
- [ ] All tests pass
- [ ] Documentation complete (auto-generated + manual)
- [ ] Final gate passes
- [ ] Kilo review verdict: PASS
- [ ] Spec compliance confirmed by Traycer

**Only when all criteria met → proceed to commit.**
