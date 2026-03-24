# Property-Based Testing

**Last Updated:** 2026-02-20

Property-based testing (PBT) automatically generates test inputs to verify that code satisfies invariants across a wide range of cases. Unlike example-based tests that check specific inputs, PBT explores the input space systematically, often finding edge cases humans miss.

## When to Use

| Use Case | Suitable | Notes |
|----------|----------|-------|
| Pure functions | ✅ | No side effects, deterministic output |
| Parsers | ✅ | Round-trip: `parse(serialize(x)) == x` |
| Serializers | ✅ | Format invariants |
| Data transformations | ✅ | Length preservation, type consistency |
| I/O operations | ❌ | Non-deterministic, slow |
| Database operations | ❌ | State-dependent, external system |
| API calls | ❌ | Network-dependent |

## Hypothesis Profiles

Profiles control test intensity. Set via `HYPOTHESIS_PROFILE` env var.

| Profile | `max_examples` | `deadline` | Use Case |
|---------|----------------|------------|----------|
| `dev` | 10 | 5000ms | Fast local iteration |
| `ci` | 100 | None | CI pipeline |
| `thorough` | 1000 | None | Pre-release validation |

## Running Tests

```bash
pytest tests/test_properties.py -v

HYPOTHESIS_PROFILE=ci pytest tests/test_properties.py -v

HYPOTHESIS_PROFILE=thorough pytest tests/test_properties.py -v
```

## Target Functions & Invariants

| Function | Module | Invariant |
|----------|--------|-----------|
| `_get_package_name(name)` | `src/fabrik/scaffold.py` | `result == name.replace("-", "_")`, `len(result) == len(name)` |
| `select_model(role, tier)` | `scripts/generate_kilo_agents.py` | Returns valid model ID from agent database |

## Example Test

```python
from hypothesis import given, strategies as st
from src.fabrik.scaffold import _get_package_name

@given(st.text(min_size=0, max_size=100))
def test_get_package_name_replaces_hyphens(name: str) -> None:
    """Property: hyphens are replaced with underscores, length preserved."""
    result = _get_package_name(name)

    assert result == name.replace("-", "_")
    assert len(result) == len(name)
    assert "-" not in result
```

## Adding New Tests

Before adding a property test, verify:

- [ ] Function is **pure** (no side effects)
- [ ] Function has **no I/O** (no file, network, database)
- [ ] There is a **meaningful invariant** to test (not just "doesn't crash")
- [ ] Input space is **bounded** or can be constrained via strategies

## See Also

- `tests/test_properties.py` — Property test implementations
- `tests/conftest.py` — Hypothesis profile configuration
- [Hypothesis documentation](https://hypothesis.readthedocs.io/)
