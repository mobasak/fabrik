# Troubleshooting Guide

Common issues and solutions for [Project Name].

## Quick Diagnostics

Run these commands first to identify issues:

```bash
# Check service health
curl http://localhost:8000/health

# View recent logs
tail -f logs/app.log

# Run tests
pytest tests/ -v
```

---

## Common Issues

### Issue: Service won't start

**Symptoms:**

- `uvicorn` command fails
- Port already in use error
- Import errors

**Cause:**

Missing dependencies, port conflicts, or incorrect Python version.

**Solution:**

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Check port availability
lsof -i :8000

# Try different port
uvicorn src.<package_name>.main:app --reload --port 8001
```

**Prevention:**

Always use a virtual environment and check port availability before starting.

---

### Issue: Health check returns 503

**Symptoms:**

```json
{
  "service": "project-name",
  "status": "error",
  "error": "..."
}
```

**Cause:**

Critical imports failing (FastAPI, Uvicorn, Pydantic not installed).

**Solution:**

```bash
# Install missing dependencies
pip install fastapi uvicorn pydantic

# Verify installation
python -c "import fastapi, uvicorn, pydantic; print('OK')"
```

**Prevention:**

Always run `pip install -r requirements.txt` after creating a new project.

---

### Issue: Tests fail with import errors

**Symptoms:**

```
ModuleNotFoundError: No module named 'src'
```

**Cause:**

Incorrect import path - tests should import from the package name, not `src`.

**Solution:**

```bash
# Correct import
from <package_name>.main import app

# Incorrect import
from src.main import app  # WRONG
```

**Prevention:**

Use the package name (e.g., `trading_core`) not `src` in imports.

---

## Error Messages

### "ImportError: No module named 'fastapi'"

**Meaning:** FastAPI not installed or virtual environment not activated.

**Solution:**

```bash
source .venv/bin/activate
pip install fastapi
```

### "Address already in use"

**Meaning:** Port 8000 is already in use by another process.

**Solution:**

```bash
# Find process using port
lsof -i :8000

# Kill process or use different port
uvicorn src.<package_name>.main:app --reload --port 8001
```

### "ModuleNotFoundError: No module named 'src'"

**Meaning:** Incorrect import path in tests.

**Solution:**

Update test imports to use package name:
```python
from <package_name>.main import app
```

---

## Performance Issues

### Slow Response Times

**Possible causes:**

1. Blocking I/O operations - Use async/await
2. Database queries not optimized - Add indexes
3. Logging too verbose - Set LOG_LEVEL=WARNING

**Solutions:**

```bash
# Enable debug logging to identify bottlenecks
LOG_LEVEL=DEBUG uvicorn src.<package_name>.main:app --reload
```

### High Memory Usage

**Solutions:**

1. Check for memory leaks in long-running processes
2. Reduce worker processes
3. Monitor with `htop` or `top`

---

## Getting More Help

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG uvicorn src.<package_name>.main:app --reload
```

### Collect Debug Info

```bash
# System info
uname -a
python --version

# Test health endpoint
curl -v http://localhost:8000/health

# Run tests with verbose output
pytest tests/ -vv
```

### Report Issues

Include:

1. Error message (full text)
2. Command that caused the error
3. Debug log output
4. System info (OS, versions)
5. Steps to reproduce
