# Migration Guide: v{from_version} to v{to_version}

**Last Updated:** YYYY-MM-DD

This guide covers migrating from v{from_version} to v{to_version}.

---

## Breaking Changes

### Change 1: [Brief description]

**Before (v{from_version}):**

```python
# Old usage
result = old_function(arg1, arg2)
```

**After (v{to_version}):**

```python
# New usage
result = new_function(arg1, arg2, new_required_param)
```

**Why:** [Explain the reason for the breaking change]

---

## Migration Steps

Follow these steps in order. Each step is atomic — complete it fully before moving to the next.

1. **Update dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run database migrations** (if applicable)
   ```bash
   alembic upgrade head
   ```

3. **Update configuration**
   - Add new env vars to `.env` (see `.env.example`)
   - Remove deprecated env vars

4. **Update code references**
   - Replace `old_function()` with `new_function()`
   - Update import paths as needed

5. **Verify**
   ```bash
   pytest tests/ -v
   curl http://localhost:8000/health
   ```

---

## Rollback Procedure

If migration fails, restore the previous version:

1. **Restore code:**
   ```bash
   git checkout v{from_version}
   ```

2. **Restore database** (if migrations were applied):
   ```bash
   alembic downgrade -{n_steps}
   ```

3. **Restore configuration:**
   ```bash
   cp .env.backup .env
   ```

4. **Restart service:**
   ```bash
   docker compose restart
   ```

---

## Affected Components

| Component | Change Type | Impact |
|-----------|------------|--------|
| `src/module.py` | API signature changed | High — all callers must update |
| `compose.yaml` | New env var required | Medium — deployment config update |
| `db/schema.sql` | New column added | Low — backward compatible |

---

## Timeline

| Milestone | Date |
|-----------|------|
| Deprecation announced | YYYY-MM-DD |
| Migration window opens | YYYY-MM-DD |
| Old API removed | YYYY-MM-DD |

---

## Need Help?

- Check [Troubleshooting](docs/TROUBLESHOOTING.md) for common migration issues
- Review [CHANGELOG](CHANGELOG.md) for full change details
