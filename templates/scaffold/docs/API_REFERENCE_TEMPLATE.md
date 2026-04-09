# API Reference — [Project Name]

**Last Updated:** YYYY-MM-DD

> Detailed API documentation. For quick integration, see [QUICKSTART.md](QUICKSTART.md) first.
> For auto-generated interactive docs, see the live OpenAPI endpoint at `/docs`.

<!-- This file is for detailed reference when QUICKSTART.md's compact tables aren't enough
     and OpenAPI's auto-generated docs need supplemental context.
     Create this manually — it is NOT scaffolded automatically. -->

---

## REST API

### Base URLs

| Environment | URL |
|-------------|-----|
| Production | `https://{project}.vps1.ocoron.com` |
| Docker-internal | `http://{project-name}:{PORT}` |
| Local dev | `http://localhost:{PORT}` |

### Authentication

<!-- Copy from QUICKSTART.md or reference it. Keep in sync. -->

```
No authentication required. Internal Docker network trust.
```

---

### {Endpoint Group 1}

#### `POST /api/v1/{resource}`

{What this endpoint does — one sentence.}

**Request:**

```json
{
  "field_1": "value",
  "field_2": 123,
  "optional_field": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `field_1` | string | Yes | — | {Description} |
| `field_2` | int | Yes | — | {Description} |
| `optional_field` | bool | No | `true` | {Description} |

**Response (200):**
```json
{
  "success": true,
  "id": "abc-123",
  "result": "..."
}
```

**Response (400):**

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "field_1 is required",
    "details": {"field": "field_1"}
  }
}
```

**Notes:**

- Idempotent: {Yes / No}
- {Any additional behavior: async, side effects, rate limits}

---

#### `GET /api/v1/{resource}/:id`

{What this endpoint does.}

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include` | string | — | Comma-separated related resources to include |

**Response (200):**
```json
{
  "id": "abc-123",
  "field_1": "value",
  "created_at": "2026-04-09T12:00:00Z"
}
```

**Response (404):**

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource abc-123 not found"
  }
}
```

---

#### `DELETE /api/v1/{resource}/:id`

**Response (200):**
```json
{"success": true, "deleted": "abc-123"}
```

---

### {Endpoint Group 2}

<!-- Repeat the pattern above for each endpoint group.
     Group by domain, not by HTTP method. -->

---

## Python SDK

<!-- Include this section only if the project exposes a Python SDK
     that other projects import directly (not via HTTP).
     Delete this entire section for HTTP-only services. -->

### Installation

```python
import sys
sys.path.insert(0, "/opt/{project-name}")
from {package_name} import {ClassName}
```

### `{ClassName}`

{What this class does — one sentence.}

```python
from {package_name} import {ClassName}

client = {ClassName}(config={"key": "value"})
```

#### `.{method_name}()`

```python
def {method_name}(self, param1: str, param2: int = 0) -> dict:
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param1` | str | Yes | — | {Description} |
| `param2` | int | No | `0` | {Description} |

**Returns:** `dict` — `{"status": "ok", "value": ...}`

**Raises:**
- `ValueError` — when `param1` is empty
- `httpx.HTTPStatusError` — when upstream API returns error

**Example:**

```python
result = client.{method_name}("input", param2=42)
```

<!-- Repeat for each public method. Only document public API, not internals. -->

---

## Error Reference

<!-- Comprehensive error code table. Supplements the compact table in QUICKSTART.md. -->

| Code | HTTP Status | Meaning | Recovery |
|------|-------------|---------|----------|
| `VALIDATION_FAILED` | 400 | Request body failed validation | Check `error.details` for field-level errors |
| `NOT_FOUND` | 404 | Resource doesn't exist | Verify ID. Create resource first if needed. |
| `CONFLICT` | 409 | Duplicate resource | Fetch existing resource or use PUT to update |
| `RATE_LIMITED` | 429 | Too many requests | Wait per `Retry-After` header |
| `INTERNAL_ERROR` | 500 | Server error | Retry once. If persistent, check service logs. |
| `DEPENDENCY_DOWN` | 503 | Upstream dependency unreachable | Check `/health` for details |

<!-- Add project-specific error codes. -->

---

## See Also

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](QUICKSTART.md) | Integration contract — compact endpoint tables, SDK modules, Docker wiring |
| [FEATURES.md](FEATURES.md) | Feature-level documentation |
| [CONFIGURATION.md](CONFIGURATION.md) | All environment variables |
| `/docs` (live) | Auto-generated OpenAPI interactive docs |
