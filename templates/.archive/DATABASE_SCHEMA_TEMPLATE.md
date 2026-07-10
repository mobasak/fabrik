# Database Schema — [Project Name]

**Last Updated:** YYYY-MM-DD

> Schema documentation for [Project Name]. Source of truth for SQL is `db/schema.sql` — this doc adds context and rationale.

**Database:** {PostgreSQL (postgres-main) | Supabase PostgreSQL | SQLite}

---

## Tables

### {table_name}

**Purpose:** {What this table stores and why it exists — one sentence.}

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key |
| `created_at` | TIMESTAMPTZ | NO | `NOW()` | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | YES | — | Auto-set by trigger |

<!-- For SQLite projects, use these types instead:
| `id` | TEXT | NO | — | UUID primary key (app-generated) |
| `created_at` | TEXT | NO | — | ISO 8601 timestamp |
-->

**Indexes:**

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_{table}_created` | `created_at` | Sort by creation date |

**Constraints:**

| Constraint | Type | Description |
|-----------|------|-------------|
| `{table}_email_unique` | UNIQUE | One record per email |

<!-- Repeat table block for each table. -->

---

## Relationships

| From | Column | To | Column | Type | On Delete |
|------|--------|----|--------|------|-----------|
| `{child_table}` | `{parent}_id` | `{parent_table}` | `id` | FK | CASCADE |

<!-- Delete this section if no foreign keys. SQLite projects: FK enforcement requires PRAGMA foreign_keys = ON. -->

---

## Migrations

<!-- Append new migrations chronologically. Each block is one change.
     These should mirror what's in db/schema.sql. -->

### Initial schema (YYYY-MM-DD)

```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- columns here
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_{table}_created ON {table_name}(created_at);
```

<!-- SQLite equivalent:
CREATE TABLE IF NOT EXISTS {table_name} (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
-->

### Auto-update trigger (YYYY-MM-DD)

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_{table}_updated_at
    BEFORE UPDATE ON {table_name}
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
```

<!-- SQLite: no trigger support for this pattern — handle in application code. -->

<!-- Append future migrations below:
### {Description} (YYYY-MM-DD)
```sql
ALTER TABLE {table_name} ADD COLUMN {column} {TYPE};
```
-->

---

## Extensions

<!-- PostgreSQL-only. Delete for SQLite projects. Enable only what you use. -->

| Extension | Purpose | Enable |
|-----------|---------|--------|
| `pgvector` | Vector embeddings for semantic search / RAG | `CREATE EXTENSION IF NOT EXISTS vector;` |
| `pg_trgm` | Trigram text search | `CREATE EXTENSION IF NOT EXISTS pg_trgm;` |

<!-- Supabase: extensions enabled via dashboard or SQL editor. Most are pre-available. -->

### pgvector usage

```sql
-- Add embedding column (1536 dims = OpenAI text-embedding-3-small)
ALTER TABLE {table_name} ADD COLUMN embedding vector(1536);

-- Similarity search index
CREATE INDEX idx_{table}_embedding ON {table_name}
    USING ivfflat (embedding vector_cosine_ops);

-- Query nearest neighbors
SELECT * FROM {table_name}
    ORDER BY embedding <=> $1::vector
    LIMIT 10;
```

---

## Conventions

- All timestamps: `TIMESTAMPTZ` (PostgreSQL) or ISO 8601 `TEXT` (SQLite)
- Primary keys: UUID (not serial/autoincrement)
- Schema changes: update `db/schema.sql` first, then this doc
- JSONB for flexible/dynamic data (PostgreSQL only)

---

## Connection Strings

| Environment | Connection |
|-------------|------------|
| Shared VPS | `postgresql://{project}:$DB_PASSWORD@postgres-main:5432/{project}` |
| Supabase | `postgresql://postgres.$PROJECT_REF:$DB_PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres` |
| SQLite (local) | `sqlite:///data/{project}.db` |
| SQLite (Docker) | `sqlite:///app/data/{project}.db` |
