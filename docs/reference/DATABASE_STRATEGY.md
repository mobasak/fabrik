# Database Strategy

**Version:** 1.0.0
**Last Updated:** 2025-12-13

---

## Overview

This document defines the database strategy for all projects, covering environment selection, migration policy, and vector storage options.

---

## Environment Selection

| Environment | Database | Use Case | When to Use |
|-------------|----------|----------|-------------|
| **Local dev** | PostgreSQL (WSL) | Development, testing | Always for local work |
| **Production (small)** | PostgreSQL (VPS) | Simple projects, full control | <10k users, simple queries |
| **Production (scale)** | Supabase | Managed, auth included | Need managed service, auth, realtime |

### Decision Tree

```
New Project?
├── Need managed auth + realtime? → Supabase
├── Simple CRUD, full control needed? → VPS PostgreSQL
├── AI/ML heavy with embeddings? → Supabase (has pgvector) or VPS + pgvector
└── Just prototyping? → Local WSL PostgreSQL
```

---

## PostgreSQL Environments

### Local Development (WSL)

```bash
# Install (Ubuntu/WSL)
sudo apt install postgresql postgresql-contrib

# Start service
sudo service postgresql start

# Create dev database
sudo -u postgres createdb myproject_dev
sudo -u postgres createuser --interactive myproject_user
```

**Connection string:**
```
DATABASE_URL=postgresql://myproject_user:password@localhost:5432/myproject_dev
```

### Production (VPS)

```bash
# Install
sudo apt install postgresql postgresql-contrib

# Secure: Edit pg_hba.conf for auth
# Enable: SSL for remote connections
# Backup: Daily pg_dump via cron
```

**Connection string:**
```
DATABASE_URL=postgresql://user:password@localhost:5432/myproject_prod
```

### Supabase

- Dashboard: https://supabase.com/dashboard
- Built-in: Auth, realtime, storage, edge functions
- Has: pgvector for embeddings

**Connection string:** Found in Supabase dashboard → Settings → Database

---

## Migration Policy

### Core Principles

1. **Migrations are FORWARD-ONLY**
   - Never edit or delete existing migration files
   - To "undo" a migration, create a NEW migration that reverses changes

2. **Always test locally first**
   - Run migration on WSL PostgreSQL before production
   - Verify data integrity after migration

3. **Backup before production migrations**
   - `pg_dump` before ANY production schema change
   - Keep backup for 7 days minimum

### Migration Workflow

```bash
# 1. Create migration (Alembic example)
alembic revision --autogenerate -m "add_users_table"

# 2. Review generated migration file
# 3. Test locally
alembic upgrade head

# 4. Verify
psql -d myproject_dev -c "\d users"

# 5. Backup production
pg_dump myproject_prod > backup_$(date +%Y%m%d).sql

# 6. Apply to production
alembic upgrade head

# 7. Verify production
```

### Rollback Strategy

**DO NOT** use `alembic downgrade`. Instead:

```python
# If migration 003_add_column.py added a column incorrectly:
# Create 004_fix_column.py that corrects it

def upgrade():
    # Fix the issue
    op.drop_column('users', 'wrong_column')
    op.add_column('users', sa.Column('correct_column', sa.String(100)))

def downgrade():
    # Reverse the fix (rarely used)
    pass
```

### Migration File Naming

```
migrations/versions/
├── 001_initial_schema.py
├── 002_add_users_table.py
├── 003_add_user_email_index.py
└── 004_add_subscriptions_table.py
```

---

## Vector Storage

### When to Use Vector Storage

- Semantic search (find similar content)
- AI embeddings storage
- Recommendation systems
- RAG (Retrieval Augmented Generation)

### Options

| Option | Best For | Vectors Limit |
|--------|----------|---------------|
| **pgvector** (PostgreSQL extension) | <1M vectors, integrated with existing DB | ~1M |
| **Supabase** (has pgvector built-in) | Managed, easy setup | ~1M |
| **Pinecone** | >1M vectors, dedicated service | Unlimited (paid) |
| **Weaviate** | Self-hosted, advanced features | Unlimited |
| **Qdrant** | Self-hosted, fast | Unlimited |

### pgvector Setup (Local/VPS)

```sql
-- Install extension
CREATE EXTENSION vector;

-- Create table with vector column
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536)  -- OpenAI ada-002 dimensions
);

-- Create index for fast similarity search
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### pgvector Queries

```sql
-- Find 5 most similar documents
SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;
```

### Supabase Vector Setup

```sql
-- Enable in Supabase SQL editor
CREATE EXTENSION IF NOT EXISTS vector;

-- Same table/index creation as above
```

---

## Backup Strategy

### Local Development

No automated backups needed. Use git for schema (migrations).

### VPS Production

```bash
# /etc/cron.daily/backup-postgres
#!/bin/bash
BACKUP_DIR=/var/backups/postgres
DATE=$(date +%Y%m%d)
pg_dump myproject_prod | gzip > $BACKUP_DIR/myproject_$DATE.sql.gz

# Keep 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

### Supabase

- Automatic daily backups (Pro plan)
- Point-in-time recovery available
- Manual backup: Dashboard → Database → Backups

### Backup Verification (MANDATORY)

Test restore quarterly:

```bash
# Create test database
createdb myproject_restore_test

# Restore backup
gunzip -c backup_20251213.sql.gz | psql myproject_restore_test

# Verify data
psql myproject_restore_test -c "SELECT COUNT(*) FROM users;"

# Clean up
dropdb myproject_restore_test
```

---

## Connection Pooling

### When Needed

- >10 concurrent database connections
- Serverless deployments (cold starts)
- High-traffic APIs

### Options

| Tool | Use Case |
|------|----------|
| **SQLAlchemy pool** | Built-in, simple apps |
| **PgBouncer** | VPS production, many connections |
| **Supabase Pooler** | Built-in for Supabase projects |

### SQLAlchemy Pool Config

```python
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # Connections to keep open
    max_overflow=10,       # Extra connections when busy
    pool_timeout=30,       # Wait time for connection
    pool_recycle=1800,     # Recycle connections after 30min
)
```

---

## Quick Reference

### Local Dev Setup

```bash
# WSL PostgreSQL
sudo service postgresql start
createdb myproject_dev
```

### Production Checklist

- [ ] Backup automation configured
- [ ] Backup restore tested
- [ ] Connection pooling enabled (if needed)
- [ ] Indexes on frequently queried columns
- [ ] SSL enabled for remote connections
- [ ] Credentials in environment variables (not code)

### Common Commands

```bash
# Connect to database
psql -d myproject_dev

# List tables
\dt

# Describe table
\d tablename

# Dump database
pg_dump myproject_prod > backup.sql

# Restore database
psql myproject_new < backup.sql
```

---

## Related Documents

- [CONFIGURATION.md](../CONFIGURATION.md) - Environment variables
- [PYTHON_PRODUCTION_STANDARDS.md](../../templates/PYTHON_PRODUCTION_STANDARDS.md) - Database code patterns
