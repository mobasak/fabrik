# `.env.example` Format Guide

**Last Updated:** YYYY-MM-DD

This is a meta-template showing the canonical format for `.env.example` files. The documentator uses this to teach agents the correct output format.

---

## Format Rules

- Section headers use `# === Section Name ===`
- Each variable has a comment line above it describing purpose, requirement, and default
- Comment format: `# Description (Required/Optional, Default: value)`
- Variables use `KEY=default_value` format
- Group variables by category
- Blank line between sections

---

## Example `.env.example` File

```env
# === Core Settings ===

# Application port (Optional, Default: 8000)
PORT=8000

# Logging level: DEBUG, INFO, WARNING, ERROR (Optional, Default: INFO)
LOG_LEVEL=INFO

# Log format: text or json (Optional, Default: text)
LOG_FORMAT=text

# === Database ===

# PostgreSQL host (Required in production, Default: localhost)
DB_HOST=localhost

# PostgreSQL port (Optional, Default: 5432)
DB_PORT=5432

# Database name (Required)
DB_NAME=myapp

# Database user (Required)
DB_USER=myapp

# Database password (Required, no default — generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
DB_PASSWORD=

# === External APIs ===

# API key for external service (Required for feature X)
EXTERNAL_API_KEY=

# API base URL (Optional, Default: https://api.example.com)
EXTERNAL_API_URL=https://api.example.com

# === Feature Flags ===

# Enable experimental feature (Optional, Default: false)
ENABLE_FEATURE_X=false

# Enable debug mode (Optional, Default: false)
DEBUG_MODE=false
```

---

## Key Principles

1. **Self-documenting:** Every variable has a comment explaining what it does
2. **Required vs Optional:** Always state whether the variable is required
3. **Defaults:** Show default values so developers know what happens if unset
4. **Secrets:** Never include real secret values — leave empty or add generation instructions
5. **Grouping:** Logical sections make the file scannable
