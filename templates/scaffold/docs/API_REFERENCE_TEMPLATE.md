# API Reference: {module_name}

**Last Updated:** YYYY-MM-DD

API documentation for the `{module_name}` module.

**⚙️ AUTO-GENERATED:** New functions/classes are documented by `kilo_docs_enforcer.py` (Documentator agent, Step 4 in mandatory workflow). Manual edits are preserved.

---

## Overview

[Brief description of what this module provides and when to use it.]

---

## Functions

### `function_name`

**Signature:**

```python
def function_name(param1: str, param2: int = 0) -> dict:
```

**Description:** [What this function does, in one sentence.]

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param1` | `str` | Yes | — | Description of param1 |
| `param2` | `int` | No | `0` | Description of param2 |

**Returns:**

- `dict` — Description of return value structure

**Raises:**

- `ValueError` — When param1 is empty
- `RuntimeError` — When external service is unavailable

**Example:**

```python
from module_name import function_name

result = function_name("input", param2=42)
print(result)  # {"status": "ok", "value": 42}
```

---

## Classes

### `ClassName`

**Description:** [What this class represents and when to use it.]

**Constructor:**

```python
class ClassName:
    def __init__(self, config: dict) -> None:
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `config` | `dict` | Yes | — | Configuration dictionary |

**Methods:**

#### `.method_name()`

```python
def method_name(self, arg: str) -> bool:
```

**Description:** [What this method does.]

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `arg` | `str` | Yes | — | Description of arg |

**Returns:**

- `bool` — `True` if operation succeeded

**Example:**

```python
obj = ClassName(config={"key": "value"})
success = obj.method_name("test")
```

---

## Related Functions

| Function | Module | Description |
|----------|--------|-------------|
| `related_func` | `other_module` | Brief description |
| `helper_func` | `utils` | Brief description |

---

## See Also

- [Module Reference](MODULE_REFERENCE_TEMPLATE.md)
- [Configuration Guide](CONFIGURATION.md)
