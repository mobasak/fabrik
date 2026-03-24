# Database Schema

**Last Updated:** YYYY-MM-DD

Database schema documentation for [Project Name].

---

## Tables

### table_name

**Purpose:** [What this table stores and why]

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key |
| `name` | VARCHAR(255) | NO | — | Display name |
| `status` | VARCHAR(50) | NO | `'active'` | Record status |
| `created_at` | TIMESTAMPTZ | NO | `NOW()` | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | YES | — | Last modification |

---

## Indexes

| Table | Index Name | Columns | Type | Purpose |
|-------|-----------|---------|------|---------|
| `table_name` | `idx_table_name_status` | `status` | btree | Filter by status |
| `table_name` | `idx_table_name_created` | `created_at` | btree | Sort by creation date |

---

## Relationships

| From Table | From Column | To Table | To Column | Type | On Delete |
|-----------|-------------|----------|-----------|------|-----------|
| `orders` | `user_id` | `users` | `id` | FK | CASCADE |
| `order_items` | `order_id` | `orders` | `id` | FK | CASCADE |

---

## Migration SQL

### Creating Tables

```sql
-- YYYY-MM-DD: Create table_name
CREATE TABLE IF NOT EXISTS table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_table_name_status ON table_name(status);
CREATE INDEX idx_table_name_created ON table_name(created_at);
```

### Altering Tables

```sql
-- YYYY-MM-DD: Add column to table_name
ALTER TABLE table_name ADD COLUMN new_column VARCHAR(100);

-- YYYY-MM-DD: Add index
CREATE INDEX idx_table_name_new_column ON table_name(new_column);
```

---

## Data Integrity

### Constraints

| Table | Constraint | Type | Description |
|-------|-----------|------|-------------|
| `users` | `email` | UNIQUE | One account per email |
| `orders` | `total_amount` | CHECK | `total_amount >= 0` |

### Triggers

| Table | Trigger | Event | Description |
|-------|---------|-------|-------------|
| `table_name` | `set_updated_at` | BEFORE UPDATE | Auto-set `updated_at` |

```sql
-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON table_name
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
```

---

## Notes

- All timestamps use `TIMESTAMPTZ` (timezone-aware)
- UUIDs preferred over sequential IDs for primary keys
- Schema changes must be documented in `db/schema.sql`
