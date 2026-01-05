# Testing Guide

**Last Updated:** 2026-01-04

This document describes how to run and write tests for Fabrik.

---

## Quick Start

```bash
# Activate virtual environment
cd /opt/fabrik
source .venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_health.py

# Run and stop on first failure
pytest -x --tb=short
```

---

## Test Structure

```
/opt/fabrik/
├── tests/                      # Main test directory
│   ├── __init__.py
│   └── monitoring_poc/         # Monitoring proof-of-concept tests
├── scripts/
│   └── test_process_monitor.py # Process monitor tests
```

---

## Running Tests

### Unit Tests

```bash
# All unit tests
pytest tests/

# With coverage report
pytest tests/ --cov=src/fabrik --cov-report=term-missing

# Specific module
pytest tests/test_drivers.py -v
```

### Script Tests

```bash
# Process monitor tests
python scripts/test_process_monitor.py

# Run specific test
python -c "from scripts.test_process_monitor import test_quick_exit; test_quick_exit()"
```

### Integration Tests

```bash
# Test health endpoints (requires services running)
curl http://localhost:8000/health

# Test droid runner
python scripts/droid_runner.py run --prompt "What is 2+2?" --auto low -o json
```

---

## Writing Tests

### Test File Naming

- Unit tests: `test_<module>.py`
- Integration tests: `test_<feature>_integration.py`
- Place in `tests/` directory mirroring `src/` structure

### Test Function Naming

```python
def test_<what>_<condition>_<expected>():
    """Test that <what> does <expected> when <condition>."""
    pass

# Examples:
def test_dns_client_add_record_success():
    ...

def test_health_endpoint_returns_ok():
    ...

def test_config_missing_env_uses_default():
    ...
```

### Basic Test Template

```python
"""Tests for <module>."""
import pytest
from fabrik.<module> import <Class>


class TestClassName:
    """Tests for ClassName."""

    def test_method_success(self):
        """Test method returns expected result."""
        obj = Class()
        result = obj.method()
        assert result == expected

    def test_method_error_handling(self):
        """Test method handles errors gracefully."""
        obj = Class()
        with pytest.raises(ValueError):
            obj.method(invalid_input)


# Fixtures
@pytest.fixture
def sample_config():
    """Provide sample configuration."""
    return {
        "key": "value",
    }


def test_with_fixture(sample_config):
    """Test using fixture."""
    assert sample_config["key"] == "value"
```

### Async Test Template

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

### FastAPI Test Template

```python
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_endpoint():
    """Test /health returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

---

## Test Categories

### 1. Driver Tests

Test external API integrations:

```python
# tests/test_drivers/test_cloudflare.py
def test_cloudflare_list_zones(mock_cloudflare_api):
    """Test listing Cloudflare zones."""
    client = CloudflareClient()
    zones = client.list_zones()
    assert len(zones) > 0
```

### 2. WordPress Tests

Test WordPress automation:

```python
# tests/test_wordpress/test_deployer.py
def test_wordpress_spec_validation():
    """Test WordPress spec YAML validation."""
    spec = load_spec("test-site.yaml")
    assert spec.is_valid()
```

### 3. CLI Tests

Test command-line interface:

```python
# tests/test_cli.py
from click.testing import CliRunner
from fabrik.cli import main

def test_cli_version():
    """Test --version flag."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
```

---

## Mocking External Services

### Mock HTTP Requests

```python
import responses

@responses.activate
def test_api_call():
    """Test with mocked HTTP response."""
    responses.add(
        responses.GET,
        "https://api.example.com/data",
        json={"result": "success"},
        status=200
    )

    result = call_api()
    assert result["result"] == "success"
```

### Mock Environment Variables

```python
import os
from unittest.mock import patch

def test_config_from_env():
    """Test config reads from environment."""
    with patch.dict(os.environ, {"DB_HOST": "testhost"}):
        config = load_config()
        assert config.db_host == "testhost"
```

---

## Code Quality Checks

```bash
# Lint with ruff
ruff check .

# Type check with mypy
mypy src/

# Format check
ruff format --check .

# Fix formatting
ruff format .
```

---

## CI/CD Integration

Tests run automatically on:
- Pull requests (via `droid-review.yml`)
- Push to main (via `daily-maintenance.yml`)

### Pre-commit Checks

```bash
# Before committing
pytest tests/ -x
ruff check .
mypy src/
```

---

## Troubleshooting Tests

### Common Issues

| Issue | Solution |
|-------|----------|
| Import errors | Ensure `pip install -e .` was run |
| Missing fixtures | Check `conftest.py` for shared fixtures |
| Async test hangs | Add `@pytest.mark.asyncio` decorator |
| Mock not working | Verify mock path matches import path |

### Debug Mode

```bash
# Run with debug output
pytest -v --tb=long

# Drop into debugger on failure
pytest --pdb

# Show print statements
pytest -s
```

---

## Test Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| `fabrik/drivers/` | 80% | TBD |
| `fabrik/wordpress/` | 70% | TBD |
| `fabrik/cli/` | 60% | TBD |
| `scripts/` | 50% | TBD |

---

## Related Documentation

- [QUICKSTART.md](QUICKSTART.md) — Getting started
- [CONFIGURATION.md](CONFIGURATION.md) — Environment setup
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues
