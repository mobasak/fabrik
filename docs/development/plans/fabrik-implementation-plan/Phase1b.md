> **Phase 1 Navigation:** [1a: Foundation](Phase1.md) | [1b: Cloud](Phase1b.md) | [1c: DNS](Phase1c.md) | [1d: WordPress](Phase1d.md) | [Phase 2 →](Phase2.md)

## Phase 1b: Cloud Infrastructure (Supabase + R2)

**Last Updated:** 2025-12-27

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Set up Supabase project | ✅ Done |
| 2 | Set up Cloudflare R2 bucket | ✅ Done |
| 3 | Create Supabase driver | ✅ Done |
| 4 | Create R2 driver | ✅ Done |
| 5 | Apply DDL (tenants, files, jobs, derivatives) | ✅ Done (sql/phase1b_ddl.sql) |
| 6 | Update Fabrik spec schema for `storage: r2` | ✅ Done (already in spec_loader.py) |
| 7 | Create Node API template (presigned URLs) | ✅ Done (templates/file-api) |
| 8 | Create Python worker template | ✅ Done (templates/file-worker) |
| 9 | Deploy first file-processing service | ✅ Done (local test passed) |
| 10 | Verify end-to-end flow | ✅ Done |

**Completion: 10/10 tasks (100%)** ✅

---

### Context and Goal
We have an existing VPS in Los Angeles running multiple apps (mixed Node/Python/PHP). VPS disk is limited (110GB). We need to store **user-uploaded files** (audio + PDFs) without consuming VPS HDD, while supporting:

* public files
* private files (user/tenant permissioned)
* internal files (admin/staff only)
  We also need a scalable pipeline to process these files: PDF text extraction, OCR, transcription, waveform, etc.

We want a design that starts simple (one VPS API) and scales later without re-architecture.

### High-level architecture (control plane vs data plane)

* **Supabase Auth + Supabase Postgres**: identity + metadata + permissions + job queue tables. Auth issues JWTs; Postgres stores file metadata, derivative metadata, tenant membership, and processing job state.
* **Cloudflare R2**: object storage for the raw bytes of uploaded files and all derived outputs (transcripts, OCR text, extracted text, thumbnails, waveforms). We do not store file bytes on VPS disk.
* **VPS (LA)**: the “control plane” backend API that:

  1. validates Supabase JWT and enforces authorization
  2. generates **presigned R2 URLs** for upload and download
  3. writes/updates metadata in Supabase Postgres
  4. creates processing jobs
* **Python worker(s) on VPS**: the “processing plane” that:

  * polls jobs from Postgres
  * locks a job safely
  * downloads original file from R2
  * runs processors (PDF extract/OCR/transcription)
  * uploads outputs back to R2
  * writes `file_derivatives` rows and updates job status

This splits responsibilities cleanly: Node API handles auth/presigning/DB; Python handles CPU-heavy processing.

### Why presigned URLs (and why not upload via VPS)

We use presigned URLs so clients (web/mobile) upload directly to R2. Benefits:

* no VPS disk usage for uploads
* no VPS bandwidth bottleneck for large files
* VPS only handles small control requests (init/finalize/download URL)
  Presigned URLs are time-limited “bearer links”, so all permission checks happen **before** issuing them.

### Multi-tenant readiness

We use a tenant-based schema (tenants + tenant_members). Even if we start “one tenant per user”, this avoids schema changes later if we add organizations/workspaces. Every file/job row includes `tenant_id`.

### File visibility rules

* `public`: can be served publicly (initially can still use presigned GET; later can use public URL/custom domain).
* `private`: only file owner or privileged roles within tenant.
* `internal`: only tenant roles `admin/internal/owner`.

These rules are enforced in the Node API endpoints that mint download URLs.

### Data model (what we store)

We store metadata in Postgres, bytes in R2:

* `files`: one row per uploaded file with `r2_key_original`, mime, size, owner, tenant_id, visibility, status.
* `file_derivatives`: one row per derived output (kind + r2 key).
* `jobs`: processing tasks with locking fields (`locked_at`, `locked_by`), attempts, retry scheduling, payload/result JSON.
* `tenants` and `tenant_members`: membership and roles.

### Phase plan and definition of DONE

#### Phase 1: Upload pipeline works end-to-end

Goal: prove we can store files in R2 without consuming VPS disk.

Implementation:

1. Node API endpoint `POST /v1/files/init-upload`

   * verifies Supabase JWT
   * checks membership/role
   * creates a `files` row with status `uploading`
   * generates `r2_key_original`
   * returns presigned PUT URL + required headers
2. Client uploads directly to R2 using presigned PUT (`Content-Type` must match the signed one).
3. Node API endpoint `POST /v1/files/finalize`

   * verifies Supabase JWT and permission
   * confirms object exists in R2 (HEAD)
   * sets file status `ready` then enqueues processing jobs and sets `processing`

DONE for Phase 1:

* A test client can: `init-upload → PUT → finalize`
* R2 contains the object at the expected key
* Postgres has a `files` row with status updated accordingly

#### Phase 2: Background job system works

Goal: prove we can run asynchronous processing safely.

Implementation:

* Python worker polls `jobs` where status `queued/retry` and `run_after <= now()`.
* Uses `FOR UPDATE SKIP LOCKED` to atomically lock one job.
* Runs placeholder processing (initially) and uploads a small derivative to R2.
* Inserts a `file_derivatives` row.
* Updates job status to `done` (or `retry` on failure with backoff).

DONE for Phase 2:

* After `finalize`, jobs appear in `jobs`.
* Worker picks jobs, updates status to `running` then `done`.
* `file_derivatives` rows are created.
* Derived objects exist in R2 under `derived/` path.
* `files.status` becomes `ready` when all jobs finished (or `failed` if any job failed and no active jobs remain).

#### Phase 3: Replace placeholders with real processors incrementally

Goal: production-grade processing, added safely one processor at a time.

Order:

1. PDF text extraction (lowest complexity; high value)
2. OCR (only for image-based PDFs or images)
3. Transcription for audio
4. Add waveform, thumbnails, etc.

DONE for Phase 3 (incremental):

* Each processor produces a correct derivative object and metadata row.
* Failures retry and do not break the entire pipeline.

### Non-goals for now (keep scope controlled)

* No multi-region API deployment yet.
* No RLS policies yet (optional later).
* No public CDN/custom domain tuning yet (can be added later).
* No complicated queue system (we use Postgres job table first).

### Implementation constraints

* Node is the primary API runtime (Express or Fastify). Keep endpoints small and deterministic.
* Python worker should be robust: retries, backoff, job locking.
* Do not store file bytes on VPS disk beyond minimal temporary buffers (prefer streaming).

### Deliverable expectation from the agent

Produce working code + scripts to:

* apply DB schema (DDL)
* run Node API locally and on VPS
* run Python worker
* include minimal test steps (curl commands) to verify phase 1 and 2 end-to-end

---

Below is the **final, production-ready Postgres DDL** for your system, aligned with:

* Supabase Postgres
* multi-tenant-ready
* background job processing
* R2 object storage
* future scaling (new processors, new derivatives)

You can paste this **as-is** into the **Supabase SQL Editor**.

---

# ✅ PostgreSQL DDL (Authoritative)

## 0. Extensions

```sql
create extension if not exists pgcrypto;
```

---

## 1. ENUM types

```sql
do $$ begin
  create type visibility_t as enum ('public','private','internal');
exception when duplicate_object then null; end $$;

do $$ begin
  create type file_status_t as enum (
    'uploading',
    'ready',
    'processing',
    'failed',
    'deleted'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type member_role_t as enum (
    'owner',
    'admin',
    'member',
    'internal'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type job_status_t as enum (
    'queued',
    'running',
    'done',
    'failed',
    'retry'
  );
exception when duplicate_object then null; end $$;
```

---

## 2. Tenants

```sql
create table if not exists tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);
```

---

## 3. Tenant members

```sql
create table if not exists tenant_members (
  tenant_id uuid not null references tenants(id) on delete cascade,
  user_id uuid not null, -- references auth.users(id)
  role member_role_t not null default 'member',
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);

create index if not exists tenant_members_user_idx
  on tenant_members(user_id);
```

---

## 4. Files (original uploads)

```sql
create table if not exists files (
  id uuid primary key default gen_random_uuid(),

  tenant_id uuid not null
    references tenants(id) on delete cascade,

  owner_user_id uuid not null,

  visibility visibility_t not null default 'private',

  r2_key_original text not null unique,

  mime text not null,
  size_bytes bigint not null default 0,
  sha256 text null,

  status file_status_t not null default 'uploading',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists files_tenant_created_idx
  on files (tenant_id, created_at desc);

create index if not exists files_owner_idx
  on files (owner_user_id);
```

---

## 5. File derivatives (outputs of processing)

```sql
create table if not exists file_derivatives (
  id uuid primary key default gen_random_uuid(),

  file_id uuid not null
    references files(id) on delete cascade,

  kind text not null, -- transcript | ocr_text | pdf_text | waveform | thumbnail | etc.

  r2_key text not null unique,

  mime text not null,
  size_bytes bigint not null default 0,

  created_at timestamptz not null default now()
);

create index if not exists file_derivatives_file_idx
  on file_derivatives(file_id);
```

---

## 6. Jobs (background processing queue)

```sql
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),

  tenant_id uuid not null
    references tenants(id) on delete cascade,

  file_id uuid not null
    references files(id) on delete cascade,

  type text not null, -- transcribe | ocr | extract_pdf | waveform | etc.

  status job_status_t not null default 'queued',

  attempts int not null default 0,

  run_after timestamptz not null default now(),

  locked_at timestamptz null,
  locked_by text null,

  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- efficient job pickup
create index if not exists jobs_pick_idx
  on jobs (status, run_after, locked_at)
  where status in ('queued','retry');

create index if not exists jobs_file_idx
  on jobs (file_id);
```

---

## 7. updated_at trigger (files + jobs)

```sql
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_files_updated_at on files;
create trigger trg_files_updated_at
before update on files
for each row execute function set_updated_at();

drop trigger if exists trg_jobs_updated_at on jobs;
create trigger trg_jobs_updated_at
before update on jobs
for each row execute function set_updated_at();
```

---

## 8. Bootstrap helper (optional but recommended)

Create **one-person tenant** when a user signs up.

```sql
-- example helper (call from backend after signup)
-- creates tenant + membership in one transaction

-- parameters:
--   :user_id uuid
--   :tenant_name text

with t as (
  insert into tenants (name)
  values (:tenant_name)
  returning id
)
insert into tenant_members (tenant_id, user_id, role)
select t.id, :user_id, 'owner'
from t;
```

---

# ✅ What this DDL guarantees

* **No file bytes in Postgres**
* **Strict separation**: metadata vs storage
* **Safe background job processing**
* **Multi-tenant from day one**
* **Unlimited future processors** without schema changes
* **Works with Supabase Auth + JWT**

---

).


## Node API scaffold (VPS) — Express + Postgres + R2 presigned URLs

### Folder structure

```
api/
  package.json
  .env.example
  src/
    server.js
    db.js
    auth.js
    r2.js
    routes/
      files.js
      internal.js
```

---

## 1) `package.json`

```json
{
  "name": "vps-file-api",
  "version": "1.0.0",
  "type": "module",
  "main": "src/server.js",
  "scripts": {
    "dev": "node --watch src/server.js",
    "start": "node src/server.js"
  },
  "dependencies": {
    "@aws-sdk/client-s3": "^3.700.0",
    "@aws-sdk/s3-request-presigner": "^3.700.0",
    "dotenv": "^16.4.5",
    "express": "^4.19.2",
    "jose": "^5.9.6",
    "pg": "^8.13.1",
    "zod": "^3.23.8"
  }
}
```

---

## 2) `.env.example`

```bash
# Server
PORT=3000
BASE_URL=http://localhost:3000

# Supabase JWT verification (recommended: JWKS)
SUPABASE_PROJECT_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_JWT_AUD=authenticated

# Postgres (Supabase DB connection string)
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres

# R2
R2_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxx
R2_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxx
R2_BUCKET=user-files

# Optional: if you later add a public domain for public objects
R2_PUBLIC_BASE_URL=
```

---

## 3) `src/db.js`

```js
import pg from "pg";

export const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30_000,
});
```

---

## 4) `src/auth.js` (Supabase JWT verification via JWKS)

This verifies the JWT from Supabase using your project’s JWKS endpoint.

```js
import { createRemoteJWKSet, jwtVerify } from "jose";

const projectUrl = process.env.SUPABASE_PROJECT_URL;
if (!projectUrl) throw new Error("Missing SUPABASE_PROJECT_URL");

const jwksUrl = new URL(`${projectUrl}/auth/v1/.well-known/jwks.json`);
const JWKS = createRemoteJWKSet(jwksUrl);

export async function requireAuth(req, res, next) {
  try {
    const h = req.headers.authorization || "";
    const token = h.startsWith("Bearer ") ? h.slice(7) : null;
    if (!token) return res.status(401).json({ error: "missing_token" });

    const { payload } = await jwtVerify(token, JWKS, {
      audience: process.env.SUPABASE_JWT_AUD || "authenticated",
    });

    // Supabase user id is in `sub`
    req.user = { id: payload.sub, jwt: payload };
    return next();
  } catch (e) {
    return res.status(401).json({ error: "invalid_token" });
  }
}
```

---

## 5) `src/r2.js`

```js
import { S3Client } from "@aws-sdk/client-s3";

export const r2 = new S3Client({
  region: "auto",
  endpoint: `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
  },
});
```

---

## 6) `src/routes/files.js`

Implements:

* `POST /v1/files/init-upload`
* `POST /v1/files/finalize`
* `GET /v1/files/:file_id/download`

```js
import crypto from "crypto";
import express from "express";
import { z } from "zod";
import { pool } from "../db.js";
import { r2 } from "../r2.js";
import {
  PutObjectCommand,
  GetObjectCommand,
  HeadObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

export const filesRouter = express.Router();

const InitUploadSchema = z.object({
  tenant_id: z.string().uuid(),
  filename: z.string().min(1).max(256),
  mime: z.string().min(1).max(200),
  visibility: z.enum(["public", "private", "internal"]).default("private"),
  size_bytes: z.number().int().nonnegative().max(5_000_000_000),
});

async function getRole(tenantId, userId) {
  const { rows } = await pool.query(
    `select role from tenant_members where tenant_id=$1 and user_id=$2`,
    [tenantId, userId]
  );
  return rows[0]?.role || null;
}

filesRouter.post("/init-upload", async (req, res) => {
  const parsed = InitUploadSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: "bad_request", details: parsed.error.flatten() });
  }
  const { tenant_id, filename, mime, visibility, size_bytes } = parsed.data;

  const role = await getRole(tenant_id, req.user.id);
  if (!role) return res.status(403).json({ error: "not_a_member" });

  if (visibility === "internal" && !["owner", "admin", "internal"].includes(role)) {
    return res.status(403).json({ error: "insufficient_role" });
  }

  const ext = (filename.split(".").pop() || "bin").toLowerCase().replace(/[^a-z0-9]/g, "");
  const fileId = crypto.randomUUID();
  const key = `t/${tenant_id}/u/${req.user.id}/${fileId}.${ext}`;

  await pool.query(
    `insert into files (id, tenant_id, owner_user_id, visibility, r2_key_original, mime, size_bytes, status)
     values ($1,$2,$3,$4,$5,$6,$7,'uploading')`,
    [fileId, tenant_id, req.user.id, visibility, key, mime, size_bytes]
  );

  const cmd = new PutObjectCommand({
    Bucket: process.env.R2_BUCKET,
    Key: key,
    ContentType: mime, // client must match on PUT
  });

  const uploadUrl = await getSignedUrl(r2, cmd, { expiresIn: 60 * 5 });

  res.json({
    file_id: fileId,
    r2_key: key,
    upload_url: uploadUrl,
    required_headers: { "Content-Type": mime },
    expires_in_seconds: 300,
  });
});

const FinalizeSchema = z.object({
  file_id: z.string().uuid(),
});

filesRouter.post("/finalize", async (req, res) => {
  const parsed = FinalizeSchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "bad_request" });

  const { file_id } = parsed.data;

  const { rows } = await pool.query(`select * from files where id=$1`, [file_id]);
  if (!rows.length) return res.status(404).json({ error: "not_found" });
  const file = rows[0];

  const role = await getRole(file.tenant_id, req.user.id);
  const isOwner = file.owner_user_id === req.user.id;
  const isElevated = ["owner", "admin", "internal"].includes(role || "");
  if (!isOwner && !isElevated) return res.status(403).json({ error: "forbidden" });

  // Ensure object exists in R2
  try {
    await r2.send(new HeadObjectCommand({ Bucket: process.env.R2_BUCKET, Key: file.r2_key_original }));
  } catch {
    return res.status(400).json({ error: "object_not_found_in_storage" });
  }

  // Mark ready then enqueue jobs and mark processing
  await pool.query(`update files set status='ready' where id=$1`, [file_id]);

  // Minimal job set (refine later based on mime)
  const jobTypes = ["extract_pdf", "ocr", "transcribe", "waveform"];
  const created = [];
  for (const t of jobTypes) {
    const { rows: j } = await pool.query(
      `insert into jobs (tenant_id, file_id, type, status)
       values ($1,$2,$3,'queued')
       returning id, type, status`,
      [file.tenant_id, file_id, t]
    );
    created.push(j[0]);
  }

  await pool.query(`update files set status='processing' where id=$1`, [file_id]);

  res.json({ ok: true, jobs: created });
});

filesRouter.get("/:file_id/download", async (req, res) => {
  const fileId = req.params.file_id;

  const { rows } = await pool.query(`select * from files where id=$1`, [fileId]);
  if (!rows.length) return res.status(404).json({ error: "not_found" });
  const file = rows[0];

  const role = await getRole(file.tenant_id, req.user.id);
  const isOwner = file.owner_user_id === req.user.id;
  const isElevated = ["owner", "admin", "internal"].includes(role || "");

  if (file.visibility === "internal" && !isElevated) return res.status(403).json({ error: "forbidden" });
  if (file.visibility === "private" && !isOwner && !isElevated) return res.status(403).json({ error: "forbidden" });

  // Public: optional shortcut if you later expose a public base URL
  if (file.visibility === "public" && process.env.R2_PUBLIC_BASE_URL) {
    return res.json({ download_url: `${process.env.R2_PUBLIC_BASE_URL}/${file.r2_key_original}` });
  }

  const cmd = new GetObjectCommand({ Bucket: process.env.R2_BUCKET, Key: file.r2_key_original });
  const url = await getSignedUrl(r2, cmd, { expiresIn: 60 * 10 });

  res.json({ download_url: url, expires_in_seconds: 600 });
});
```

---

## 7) `src/routes/internal.js` (admin/internal only)

Example: reprocess file.

```js
import express from "express";
import { pool } from "../db.js";

export const internalRouter = express.Router();

async function getRole(tenantId, userId) {
  const { rows } = await pool.query(
    `select role from tenant_members where tenant_id=$1 and user_id=$2`,
    [tenantId, userId]
  );
  return rows[0]?.role || null;
}

internalRouter.post("/files/:file_id/reprocess", async (req, res) => {
  const fileId = req.params.file_id;

  const { rows } = await pool.query(`select tenant_id from files where id=$1`, [fileId]);
  if (!rows.length) return res.status(404).json({ error: "not_found" });

  const tenantId = rows[0].tenant_id;
  const role = await getRole(tenantId, req.user.id);
  if (!["owner", "admin", "internal"].includes(role || "")) {
    return res.status(403).json({ error: "forbidden" });
  }

  const jobTypes = ["extract_pdf", "ocr", "transcribe", "waveform"];
  const created = [];
  for (const t of jobTypes) {
    const { rows: j } = await pool.query(
      `insert into jobs (tenant_id, file_id, type, status)
       values ($1,$2,$3,'queued')
       returning id, type, status`,
      [tenantId, fileId, t]
    );
    created.push(j[0]);
  }

  await pool.query(`update files set status='processing' where id=$1`, [fileId]);

  res.json({ ok: true, jobs: created });
});
```

---

## 8) `src/server.js`

```js
import "dotenv/config";
import express from "express";
import { requireAuth } from "./auth.js";
import { filesRouter } from "./routes/files.js";
import { internalRouter } from "./routes/internal.js";

const app = express();
app.use(express.json({ limit: "2mb" }));

app.get("/health", (req, res) => res.json({ ok: true }));

app.use("/v1/files", requireAuth, filesRouter);
app.use("/v1/internal", requireAuth, internalRouter);

const port = Number(process.env.PORT || 3000);
app.listen(port, () => console.log(`API listening on :${port}`));
```

---

# Minimal end-to-end test (Phase 1)

Assumes you already have:

* a Supabase user + JWT access token
* a tenant + tenant_members row for that user
* `.env` filled

### 1) Init upload

```bash
curl -sS -X POST http://localhost:3000/v1/files/init-upload \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id":"'"$TENANT_ID"'",
    "filename":"test.pdf",
    "mime":"application/pdf",
    "visibility":"private",
    "size_bytes": 1234
  }' | jq
```

Copy `upload_url` and `file_id`.

### 2) PUT bytes to R2 (direct)

```bash
curl -sS -X PUT "$UPLOAD_URL" \
  -H "Content-Type: application/pdf" \
  --data-binary @./test.pdf
```

### 3) Finalize

```bash
curl -sS -X POST http://localhost:3000/v1/files/finalize \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id":"'"$FILE_ID"'"}' | jq
```

---

## Python worker scaffold (VPS) — Postgres job queue + R2 I/O + retries

This worker:

* polls `jobs` (`queued`/`retry`)
* locks one job safely (`FOR UPDATE SKIP LOCKED`)
* downloads original from R2
* runs a placeholder processor per job type (you will replace each with real logic)
* uploads derivative to R2
* inserts `file_derivatives`
* marks job done or retry (exponential backoff)
* updates `files.status` to `ready` when all jobs are finished (or `failed` if any failed)

### Folder structure

```
worker/
  requirements.txt
  .env.example
  worker.py
  processors/
    __init__.py
    pdf_extract.py
    ocr.py
    transcribe.py
    waveform.py
```

---

## 1) `requirements.txt`

```txt
boto3==1.35.90
psycopg[binary]==3.2.3
python-dotenv==1.0.1
```

---

## 2) `.env.example`

```bash
SUPABASE_DB_URL=postgresql://USER:PASSWORD@HOST:5432/postgres

R2_ACCOUNT_ID=xxxxxxxxxxxxxxxxxxxx
R2_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxx
R2_BUCKET=user-files

WORKER_POLL_SECONDS=1.5
JOB_STALE_LOCK_MINUTES=15
MAX_ATTEMPTS=10
```

---

## 3) `processors/__init__.py`

```python
from .pdf_extract import run_extract_pdf
from .ocr import run_ocr
from .transcribe import run_transcribe
from .waveform import run_waveform

PROCESSORS = {
    "extract_pdf": run_extract_pdf,
    "ocr": run_ocr,
    "transcribe": run_transcribe,
    "waveform": run_waveform,
}
```

---

## 4) Placeholder processors (replace later)

### `processors/pdf_extract.py`

```python
def run_extract_pdf(original_bytes: bytes, mime: str) -> tuple[bytes, str, str]:
    # TODO: replace with real PDF text extraction
    out = b"PDF_TEXT_PLACEHOLDER\n"
    return out, "text/plain", "pdf_text"
```

### `processors/ocr.py`

```python
def run_ocr(original_bytes: bytes, mime: str) -> tuple[bytes, str, str]:
    # TODO: replace with real OCR
    out = b"OCR_TEXT_PLACEHOLDER\n"
    return out, "text/plain", "ocr_text"
```

### `processors/transcribe.py`

```python
def run_transcribe(original_bytes: bytes, mime: str) -> tuple[bytes, str, str]:
    # TODO: replace with real transcription
    out = b"TRANSCRIPT_PLACEHOLDER\n"
    return out, "text/plain", "transcript"
```

### `processors/waveform.py`

```python
import json

def run_waveform(original_bytes: bytes, mime: str) -> tuple[bytes, str, str]:
    # TODO: replace with real waveform generation
    payload = {"waveform": [0, 1, 0, -1], "note": "placeholder"}
    out = json.dumps(payload).encode("utf-8")
    return out, "application/json", "waveform"
```

---

## 5) `worker.py` (main loop)

```python
import os
import time
import json
import socket
import datetime
from dotenv import load_dotenv

import psycopg
import boto3

from processors import PROCESSORS

load_dotenv()

DB_URL = os.environ["SUPABASE_DB_URL"]
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]

POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "1.5"))
STALE_LOCK_MIN = int(os.environ.get("JOB_STALE_LOCK_MINUTES", "15"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "10"))

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)

def s3_get_bytes(key: str) -> bytes:
    obj = s3.get_object(Bucket=R2_BUCKET, Key=key)
    return obj["Body"].read()

def s3_put_bytes(key: str, data: bytes, content_type: str) -> int:
    s3.put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
    return len(data)

def pick_and_lock_job(conn) -> dict | None:
    """
    Atomically claim one job using FOR UPDATE SKIP LOCKED.
    Also treats old locks as stale.
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            f"""
            with cte as (
              select id
              from jobs
              where status in ('queued','retry')
                and run_after <= now()
                and attempts < %s
                and (
                  locked_at is null
                  or locked_at < now() - interval '{STALE_LOCK_MIN} minutes'
                )
              order by run_after asc, created_at asc
              for update skip locked
              limit 1
            )
            update jobs j
            set status='running',
                locked_at=now(),
                locked_by=%s,
                updated_at=now()
            from cte
            where j.id = cte.id
            returning j.*;
            """,
            (MAX_ATTEMPTS, WORKER_ID),
        )
        return cur.fetchone()

def mark_job_done(conn, job_id: str, result: dict):
    with conn.cursor() as cur:
        cur.execute(
            """
            update jobs
            set status='done',
                result=%s::jsonb,
                updated_at=now()
            where id=%s
            """,
            (json.dumps(result), job_id),
        )

def mark_job_failed(conn, job_id: str, error_msg: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            update jobs
            set status='failed',
                result=jsonb_set(result, '{last_error}', to_jsonb(%s::text), true),
                updated_at=now()
            where id=%s
            """,
            (error_msg[:800], job_id),
        )

def mark_job_retry(conn, job_id: str, error_msg: str):
    """
    Exponential backoff in minutes: min(2^attempts, 60)
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("select attempts from jobs where id=%s", (job_id,))
        row = cur.fetchone()
        attempts = int(row["attempts"]) if row else 0
        delay_min = min(2 ** max(attempts, 0), 60)

    with conn.cursor() as cur2:
        cur2.execute(
            """
            update jobs
            set status='retry',
                attempts=attempts+1,
                run_after=now() + (%s || ' minutes')::interval,
                result=jsonb_set(result, '{last_error}', to_jsonb(%s::text), true),
                locked_at=null,
                locked_by=null,
                updated_at=now()
            where id=%s
            """,
            (delay_min, error_msg[:800], job_id),
        )

def insert_derivative(conn, file_id: str, kind: str, r2_key: str, mime: str, size_bytes: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into file_derivatives (file_id, kind, r2_key, mime, size_bytes)
            values (%s,%s,%s,%s,%s)
            on conflict (r2_key) do nothing
            """,
            (file_id, kind, r2_key, mime, size_bytes),
        )

def update_file_status_if_complete(conn, file_id: str):
    """
    If no active jobs remain, mark files.ready unless any job failed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              sum(case when status in ('queued','retry','running') then 1 else 0 end) as active,
              sum(case when status = 'failed' then 1 else 0 end) as failed
            from jobs
            where file_id=%s
            """,
            (file_id,),
        )
        active, failed = cur.fetchone()

        if active == 0:
            new_status = "failed" if (failed or 0) > 0 else "ready"
            cur.execute(
                "update files set status=%s, updated_at=now() where id=%s",
                (new_status, file_id),
            )

def process_one_job(conn, job: dict):
    job_id = job["id"]
    file_id = job["file_id"]
    job_type = job["type"]

    # Load file info
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            "select tenant_id, r2_key_original, mime from files where id=%s",
            (file_id,),
        )
        file_row = cur.fetchone()
        if not file_row:
            raise RuntimeError("file_not_found")

    tenant_id = file_row["tenant_id"]
    original_key = file_row["r2_key_original"]
    mime = file_row["mime"]

    # Download original bytes (for big files, swap to streaming/tempfile later)
    original_bytes = s3_get_bytes(original_key)

    # Choose processor
    fn = PROCESSORS.get(job_type)
    if not fn:
        # Unknown job type: mark done (or fail). Here: fail to surface misconfig.
        raise RuntimeError(f"unknown_job_type:{job_type}")

    # Run processor -> returns (bytes, out_mime, derivative_kind)
    out_bytes, out_mime, derivative_kind = fn(original_bytes, mime)

    # Upload derivative
    derivative_key = f"t/{tenant_id}/derived/{file_id}/{derivative_kind}"

    # Add extensions for common types (optional)
    if out_mime == "text/plain":
        derivative_key += ".txt"
    elif out_mime == "application/json":
        derivative_key += ".json"

    size = s3_put_bytes(derivative_key, out_bytes, out_mime)

    # Write derivative metadata
    insert_derivative(conn, file_id, derivative_kind, derivative_key, out_mime, size)

    # Mark job done
    mark_job_done(conn, job_id, {"ok": True, "derived_key": derivative_key, "bytes": size})

    # Potentially finalize file status
    update_file_status_if_complete(conn, file_id)

def main():
    print(f"[worker] starting id={WORKER_ID} poll={POLL_SECONDS}s stale_lock={STALE_LOCK_MIN}m max_attempts={MAX_ATTEMPTS}")
    with psycopg.connect(DB_URL, autocommit=False) as conn:
        while True:
            try:
                job = pick_and_lock_job(conn)
                if not job:
                    conn.commit()
                    time.sleep(POLL_SECONDS)
                    continue

                try:
                    process_one_job(conn, job)
                    conn.commit()
                except Exception as e:
                    # If attempts exceeded, mark failed; else retry
                    err = str(e)

                    # Reload attempts
                    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                        cur.execute("select attempts from jobs where id=%s", (job["id"],))
                        row = cur.fetchone()
                        attempts = int(row["attempts"]) if row else 0

                    if attempts + 1 >= MAX_ATTEMPTS:
                        mark_job_failed(conn, job["id"], err)
                        update_file_status_if_complete(conn, job["file_id"])
                    else:
                        mark_job_retry(conn, job["id"], err)

                    conn.commit()

            except KeyboardInterrupt:
                print("[worker] stopping")
                return
            except Exception:
                conn.rollback()
                time.sleep(2.0)

if __name__ == "__main__":
    main()
```

---

# Run instructions (VPS)

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with real values

python worker.py
```

---

# Phase 2 verification (what to check)

After you upload + finalize a file:

1. In Postgres:

* `select * from jobs order by created_at desc limit 10;`

  * should move `queued -> running -> done`

2. `select * from file_derivatives order by created_at desc limit 10;`

* should have new rows

3. In R2:

* objects should exist at:

  * `t/<tenant_id>/derived/<file_id>/pdf_text.txt` (etc.)

---

# Notes for later upgrades (not now)

* Switch from `s3_get_bytes` to streaming/temp files for large audio.
* Add per-mime job creation (only queue OCR for image-based PDFs; only transcribe for audio).
* Add dedupe via `sha256`.
* Add RLS policies in Supabase.

Below is a **clean, copy-paste test kit** to validate the whole system step-by-step.

Assumptions:

* API running at `http://localhost:3000`
* You already have:

  * a Supabase user
  * a **valid Supabase access token (JWT)**
  * Node API + Python worker running
  * DDL applied

---

# 0) Environment variables (local shell)

```bash
export API_BASE=http://localhost:3000
export ACCESS_TOKEN="PASTE_SUPABASE_ACCESS_TOKEN"
export USER_ID="PASTE_SUPABASE_USER_ID"
```

---

# 1) Bootstrap tenant (ONE TIME)

Create a tenant and membership for the user.

```sql
-- run in Supabase SQL editor
with t as (
  insert into tenants (name)
  values ('Test Tenant')
  returning id
)
insert into tenant_members (tenant_id, user_id, role)
select t.id, :'USER_ID', 'owner'
from t
returning tenant_id;
```

Copy returned `tenant_id`.

```bash
export TENANT_ID="PASTE_TENANT_ID"
```

Verify:

```sql
select * from tenant_members where user_id = :'USER_ID';
```

---

# 2) Init upload (Node API → R2 presign)

```bash
curl -sS -X POST $API_BASE/v1/files/init-upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"$TENANT_ID\",
    \"filename\": \"test.pdf\",
    \"mime\": \"application/pdf\",
    \"visibility\": \"private\",
    \"size_bytes\": 12345
  }" | tee /tmp/init.json
```

Extract values:

```bash
export FILE_ID=$(jq -r .file_id /tmp/init.json)
export UPLOAD_URL=$(jq -r .upload_url /tmp/init.json)
```

Verify DB:

```sql
select id, status, r2_key_original
from files
where id = :'FILE_ID';
-- status should be 'uploading'
```

---

# 3) PUT file directly to R2

Use any PDF (or dummy file):

```bash
echo "hello pdf" > test.pdf

curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: application/pdf" \
  --data-binary @test.pdf
```

Expected:

* HTTP 200 / 204
* **no VPS disk usage**

---

# 4) Finalize upload (enqueue jobs)

```bash
curl -sS -X POST $API_BASE/v1/files/finalize \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_id\": \"$FILE_ID\"
  }" | jq
```

Verify DB:

```sql
select status from files where id = :'FILE_ID';
-- should be 'processing'

select type, status from jobs where file_id = :'FILE_ID';
-- should be queued
```

---

# 5) Worker picks jobs (Phase 2)

Watch worker logs:

```bash
python worker.py
```

Expected transitions:

```sql
select type, status from jobs where file_id = :'FILE_ID';
-- queued → running → done
```

Derivatives:

```sql
select kind, r2_key from file_derivatives where file_id = :'FILE_ID';
```

File status:

```sql
select status from files where id = :'FILE_ID';
-- should be 'ready'
```

---

# 6) Download original (private, presigned GET)

```bash
curl -sS $API_BASE/v1/files/$FILE_ID/download \
  -H "Authorization: Bearer $ACCESS_TOKEN" | tee /tmp/dl.json
```

```bash
curl -L "$(jq -r .download_url /tmp/dl.json)" -o downloaded.pdf
cat downloaded.pdf
```

---

# 7) Permission test (negative)

Create another user (or use a different JWT):

```bash
export OTHER_ACCESS_TOKEN="OTHER_USER_JWT"

curl -i $API_BASE/v1/files/$FILE_ID/download \
  -H "Authorization: Bearer $OTHER_ACCESS_TOKEN"
```

Expected:

```
HTTP/1.1 403 Forbidden
```

---

# 8) Internal reprocess (admin-only)

```bash
curl -sS -X POST $API_BASE/v1/internal/files/$FILE_ID/reprocess \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

Verify new jobs:

```sql
select type, status from jobs where file_id = :'FILE_ID'
order by created_at desc;
```

---

# 9) Failure test (optional)

Kill worker mid-job → restart → verify retry:

```sql
select id, status, attempts, run_after
from jobs
where file_id = :'FILE_ID';
```

Expected:

* status → `retry`
* attempts increments
* job eventually resumes

---

# ✅ DONE checklist

You are done when:

* [ ] `init-upload → PUT → finalize` works
* [ ] VPS disk usage does **not** increase
* [ ] Jobs are processed by Python worker
* [ ] `file_derivatives` rows appear
* [ ] Permissions enforced correctly
* [ ] Retry logic works

---
## Deployment steps (VPS, Ubuntu assumed)

### Prereqs

* Domain optional but recommended: `api.yourdomain.com`
* Ports: expose 80/443 (reverse proxy) and keep Node on localhost (3000)
* You already created:

  * Supabase project (Auth + Postgres)
  * R2 bucket + API keys

---

# A) Prepare directories

```bash
sudo mkdir -p /opt/apps/file-api
sudo mkdir -p /opt/apps/file-worker
sudo chown -R $USER:$USER /opt/apps
```

---

# B) Deploy Node API (Express)

## 1) Install Node + system deps

Use Node 20+.

```bash
node -v || true
# If Node missing, install via your preferred method (nvm or distro packages).
```

## 2) Copy code to VPS

Upload your `api/` folder into:

```
/opt/apps/file-api
```

## 3) Create `.env`

```bash
cd /opt/apps/file-api
cp .env.example .env
nano .env
```

Fill:

* `SUPABASE_PROJECT_URL`
* `DATABASE_URL` (Supabase Postgres connection string)
* `R2_*`
* `R2_BUCKET`
* `PORT=3000`

## 4) Install dependencies

```bash
cd /opt/apps/file-api
npm install
```

## 5) Smoke test locally

```bash
npm run start
# In another shell:
curl -sS http://127.0.0.1:3000/health
```

Stop it (Ctrl+C).

---

## 6) Run Node API as a systemd service

Create service file:

```bash
sudo tee /etc/systemd/system/file-api.service > /dev/null <<'EOF'
[Unit]
Description=File API (Node)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/apps/file-api
EnvironmentFile=/opt/apps/file-api/.env
ExecStart=/usr/bin/node /opt/apps/file-api/src/server.js
Restart=always
RestartSec=2
User=root

# Hardening (optional)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable file-api
sudo systemctl start file-api
sudo systemctl status file-api --no-pager
```

Logs:

```bash
journalctl -u file-api -f
```

---

# C) Reverse proxy (Nginx) + TLS

## 1) Install Nginx

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

## 2) Configure Nginx

Create site:

```bash
sudo tee /etc/nginx/sites-available/file-api > /dev/null <<'EOF'
server {
  listen 80;
  server_name api.yourdomain.com;

  location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF
```

Enable:

```bash
sudo ln -sf /etc/nginx/sites-available/file-api /etc/nginx/sites-enabled/file-api
sudo nginx -t
sudo systemctl reload nginx
```

## 3) Add TLS (Let’s Encrypt)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

Verify:

```bash
curl -sS https://api.yourdomain.com/health
```

---

# D) Deploy Python worker

## 1) Copy code

Upload `worker/` folder into:

```
/opt/apps/file-worker
```

## 2) Create venv + install

```bash
cd /opt/apps/file-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Create `.env`

```bash
cp .env.example .env
nano .env
```

Fill:

* `SUPABASE_DB_URL` (same as Node `DATABASE_URL`)
* `R2_*`, `R2_BUCKET`

## 4) Test worker manually

```bash
source .venv/bin/activate
python worker.py
```

Stop after you see it run.

---

## 5) Run worker as systemd service

```bash
sudo tee /etc/systemd/system/file-worker.service > /dev/null <<'EOF'
[Unit]
Description=File Worker (Python)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/apps/file-worker
EnvironmentFile=/opt/apps/file-worker/.env
ExecStart=/opt/apps/file-worker/.venv/bin/python /opt/apps/file-worker/worker.py
Restart=always
RestartSec=2
User=root

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable file-worker
sudo systemctl start file-worker
sudo systemctl status file-worker --no-pager
```

Logs:

```bash
journalctl -u file-worker -f
```

---

# E) Production checks

## 1) Confirm API reachable

```bash
curl -sS https://api.yourdomain.com/health
```

## 2) Run your Phase 1 test kit against the HTTPS base URL

```bash
export API_BASE=https://api.yourdomain.com
# then run init-upload → PUT → finalize tests
```

## 3) Confirm worker is processing jobs

```bash
sudo systemctl status file-worker --no-pager
journalctl -u file-worker -n 100 --no-pager
```

---

# F) Minimal ops hygiene (recommended)

## Log rotation (journald already limits, but ensure persistence if needed)

```bash
sudo journalctl --vacuum-time=7d
```

## Auto-restart already set via systemd.

## Backups

* R2 is your file store; ensure you have a retention policy.
* For DB: use Supabase backups or periodic dumps (optional).

---

# DONE checklist

* [ ] `https://api.yourdomain.com/health` returns `{ok:true}`
* [ ] `init-upload → PUT → finalize` works against prod URL
* [ ] No file bytes stored on VPS disk
* [ ] Worker processes jobs and creates `file_derivatives`
* [ ] Permissions enforced for download endpoint

If you want, I can provide:

* a hardened Nginx config (rate limits for init-upload/finalize),
* a `/v1/tenants/bootstrap` endpoint,
* and a minimal “admin/internal role” management endpoint.
