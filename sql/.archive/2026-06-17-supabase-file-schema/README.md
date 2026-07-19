# Archived 2026-06-17 — Phase-1b Supabase file/job schema

`phase1b_ddl.sql` (dated 2025-12-23) is the **Supabase** DDL for a multi-tenant
file-storage + async-processing schema: `tenants`, `tenant_members`, `files`,
`file_derivatives`, `processing_jobs` (+ RLS on `auth.users`, `claim_next_job()`,
R2-backed object storage).

**Why archived (not deleted):** no live service uses it today —
- the `file-api` service that deployed it is **retired** (not on any of the 3 VPS),
- `src/fabrik/drivers/supabase.py` (`SupabaseClient`, which operates on these tables)
  is exported from `drivers/__init__.py` but **not consumed by any live code path**,
- the doc that cited it (`docs/archive/file-api-deployment.md`) is flagged
  "pre-migration vintage".

Kept as the schema-of-record in case a Supabase-backed SaaS is revived (the saas/mobile
rule packs still describe Supabase + RLS as a supported backend pattern). If revived,
this is the DDL to apply in the Supabase SQL editor.
