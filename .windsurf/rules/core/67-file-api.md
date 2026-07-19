---
activation: glob
globs: ["**/file-api/**", "**/uploads/**", "**/storage/**", "**/presigned/**", "**/multipart/**", "**/clamav/**", "**/file-api*.js", "**/file-api*.ts"]
description: File-handling discipline (2026) — S3-compatible storage routing (B2/R2 default; Supabase Storage legacy), undici handler, adaptive retry, presigned URL contracts, busboy + pipeline streams, magic-byte + polyglot validation, blake3 dedup, clamd sidecar, KVKK lifecycle
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code, Windsurf Cascade, Kilo CLI)
     GOAL: File-handling patterns for the file-api scaffold + any service that uploads, stores, validates, or deletes user files
     TRAYCER USAGE: Injects as Context File for file-api scaffolds + any ticket touching uploads / storage / presigned URLs / KVKK erasure.
     AGENT USAGE: Follow verbatim. Composes with 12-node.md (Node runtime). Research basis: docs/reference/research-files/Node API File Storage Rules.md (cited). -->

# File API Rules (2026)

**Activation:** Glob `**/file-api/**`, `**/uploads/**`, `**/storage/**`, `**/presigned/**`, `**/multipart/**`, `**/clamav/**`
**Purpose:** Production patterns for services that upload, store, validate, dedupe, scan, or destroy user files on Fabrik's VPS fleet.
**Scope:** `file-api` scaffold + any service handling binary uploads. Composes with `12-node.md` (Node runtime), `25-data-postgres.md` (metadata schema), `95-multi-tenant-saas.md` (tenant isolation), `app-audit-log.md` (KVKK audit).
**Research basis:** [`docs/reference/research-files/Node API File Storage Rules.md`](../../../docs/reference/research-files/Node%20API%20File%20Storage%20Rules.md)

---

## Architecture & Threat Model

- **Container volumes are ephemeral.** A redeploy destroys local disk; Backrest doesn't index large mutable blobs efficiently. **Therefore all binary persistence is to an external S3-compatible backend** — never local disk in production.
- **Multi-tenant isolation enforced at the metadata tier.** Every file row carries `tenant_id`; cross-tenant access is banned at the DB level (see `95-multi-tenant-saas.md`).
- **Auth:** Pattern A FastAPI-issued Bearer JWT for end-user uploads (`fabrik-lib/fastapi-user-auth`, per `agents-fabrik.md § Supabase`), `X-Internal-Token` for M2M (see `35-security-auth.md` + Node implementation in `12-node.md`). Legacy Supabase Auth (Pattern B) Bearer JWTs validate the same way for a project not yet migrated.
- **Threats this pack defends against:** SSRF via PDF rendering, ZIP bombs, ImageMagick coder vulns, polyglot files, presigned URL replay, cross-tenant dedup side-channel, OOM via in-memory buffering, supply-chain tampering of file-type detection.
- **Decoupling principle:** every high-risk binary mutation is **physically isolated** in its own container. Image manipulation → `image-broker` microservice. AV scanning → `clamd` sidecar.

## Storage Backend Selection

Two default backends (B2/R2) plus one legacy option. Pick by need; never run multiple in parallel for the same project.

| Backend | When | SDK Configuration |
| --- | --- | --- |
| **Backblaze B2** | Default for new file-api services. Cheap egress, simple billing. Pairs with `fabrik-lib/storage` (B2 backend, URI-routed) per `agents-fabrik.md § Supabase`. | `endpoint: https://s3.<region>.backblazeb2.com`, **`forcePathStyle: true`** (B2 requires path-style — virtual-hosted bucket DNS fails). |
| **Cloudflare R2** | High-egress workloads or projects already on Cloudflare. Zero egress fees. | `endpoint: https://<account>.r2.cloudflarestorage.com`, **`region: 'auto'`** (R2 ignores explicit regions; global routing). 5 MiB min chunk, 10000 max parts. |
| **Supabase Storage** (legacy) | **Legacy — migrate to self-hosted.** ONLY a project already on Supabase for auth/DB and not yet migrated. New services use B2/R2 (`fabrik-lib/storage`); do not adopt Supabase Storage for new work. | Inject user's JWT into the `sessionToken` field — enforces RLS at the storage layer. Do NOT pass `x-amz-acl` headers (rejected by Supabase Storage API). |

**Banned:**

- **AWS S3 direct** — TR-entity billing friction; no operational advantage over B2/R2.
- **MinIO self-hosted** — operational tax; we already pay for B2/R2.
- **Local-disk storage in production** — containers redeploy and lose volumes; Backrest doesn't efficiently index large mutable blobs.

The `file-api` scaffold ships with `@aws-sdk/client-s3` + `@aws-sdk/s3-request-presigner`. Write code S3-compatible; swap endpoint via env vars (`STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_KEY_ID`, `STORAGE_SECRET`, `STORAGE_REGION`).

## AWS SDK v3 — HTTP Handler & Retry Strategy

### Mandatory: `@smithy/undici-http-handler`

The default `@smithy/node-http-handler` has inefficient keep-alive mechanics under concurrent multipart load. Switch to undici:

```js
import { S3Client } from '@aws-sdk/client-s3';
import { UndiciHttpHandler } from '@smithy/undici-http-handler';
import { ConfiguredRetryStrategy } from '@aws-sdk/util-retry';

export const s3 = new S3Client({
  region: process.env.STORAGE_REGION || 'auto',
  endpoint: process.env.STORAGE_ENDPOINT,
  forcePathStyle: process.env.STORAGE_FORCE_PATH_STYLE === 'true',  // true for B2
  credentials: {
    accessKeyId: process.env.STORAGE_KEY_ID,
    secretAccessKey: process.env.STORAGE_SECRET,
  },
  requestHandler: new UndiciHttpHandler({
    connectionTimeout: 5_000,
    requestTimeout: 60_000,
    // Pooled keep-alive — defaults are sane
  }),
  // Adaptive retry: client-side token bucket + exponential backoff with jitter
  retryStrategy: new ConfiguredRetryStrategy(
    3,  // maxAttempts
    (attempt) => 100 + Math.random() * 2 ** attempt * 100,  // delay ms with jitter
  ),
});
```

**Why undici:** 35–45% lower per-request latency under parallel load. Connection pooling is the default; no manual `Agent` tuning required for most workloads.

**Why adaptive retry:** legacy retry strategies cause thundering herds during transient outages. Adaptive mode introduces a token bucket that throttles before requests leave the container.

### Circuit breakers (`opossum`) around external calls

Wrap every call to the `image-broker` microservice and the `clamd` sidecar — without this, a hung dependency exhausts the Node event loop.

```js
import CircuitBreaker from 'opossum';

const scanBreaker = new CircuitBreaker(scanWithClamd, {
  timeout: 15_000,                  // fail fast at 15s
  errorThresholdPercentage: 50,     // open at 50% failures
  resetTimeout: 30_000,             // half-open probe after 30s
});

scanBreaker.fallback(() => ({ verdict: 'unscanned', reason: 'clamd_circuit_open' }));
scanBreaker.on('open', () => logger.warn('clamd circuit OPEN'));
```

For Postgres metadata writes, prefer wrapping at the pool level (per `58-resilience.md`); opossum on top of pg is overkill.

### Idempotency-Key for retries

Clients supply `Idempotency-Key` header (often derived from blake3 of the file). Server stores it; duplicate keys return the existing metadata row instead of creating a new one. Required to prevent duplicate rows on transient network retries.

## Presigned URLs — the default upload topology (≥ 50 MB)

For files above ~50 MB, delegate uploads directly to the storage backend — never proxy through Node. The 2026 security posture requires application-layer guardrails because S3 itself has no single-use enforcement.

### URL issuance

```js
import { PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

async function issueUploadUrl({tenantId, contentType, contentLength, key, expiresIn = 900}) {
  // expiresIn ≤ 900 (15 min) — NIST observation-contract guidance
  if (expiresIn > 900) throw new Error('expiresIn capped at 900s');

  const command = new PutObjectCommand({
    Bucket: process.env.STORAGE_BUCKET,
    Key: key,                          // tenant-scoped path (below)
    ContentType: contentType,          // MUST be in signature
    ContentLength: contentLength,      // MUST be in signature — pins exact size
  });

  // The signature now mathematically binds the client to (key, type, length).
  // An attacker who replays the URL with a different payload gets rejected.
  return getSignedUrl(s3, command, { expiresIn });
}
```

**Rules:**

- `expiresIn ≤ 900` seconds (15 min). NIST SP 800-63B treats these URLs as observation contracts (bearer tokens) — longer windows widen the interception surface.
- **`ContentType` AND `ContentLength` MUST be in the signature** — without these, an attacker can replay the URL with a malicious payload of any size.
- One URL per upload. Single-use is enforced **in application logic** (S3 doesn't enforce it).
- **Key naming:** `{tenant_id}/{yyyy}/{mm}/{file_id}-{sanitized_filename}`. Tenant scoping prevents cross-tenant exposure through ACL leak; date partitioning aids lifecycle policies.
- **Do NOT pass `x-amz-acl`** — Supabase Storage rejects it outright; rely on bucket policies + IAM/R2 token scoping.

### Single-use via DB state machine

```text
client requests URL → INSERT files (status='pending_upload', expires_at=now()+15min)
client PUTs to URL → file lands in bucket
client calls /finalize → UPDATE files SET status='scanning'
                      → worker picks up, scans, updates to 'available' or 'quarantined'
expires_at exceeded → sweeper marks 'soft_deleted' + deletes orphaned bucket object
```

The `/finalize` endpoint is what invalidates the upload token at the application layer. Without `/finalize` the row stays `pending_upload` and gets garbage-collected.

### Download presigned URLs

Symmetric: issue presigned GET. Default `expiresIn: 300` for private content (5 min); `3600` for short-lived public assets. Never `> 86400` (1 day) without explicit written reason.

## Direct Server Streaming (< 50 MB or when proxy needed)

When the client can't do the two-step presigned flow, or when you need server-side metadata extraction during upload.

### `busboy` v2 + `pipeline()` + `@aws-sdk/lib-storage` Upload

```js
import busboy from 'busboy';
import { Upload } from '@aws-sdk/lib-storage';
import { pipeline } from 'node:stream/promises';

app.post('/upload', requireAuth, (req, res, next) => {
  const bb = busboy({
    headers: req.headers,
    limits: { fileSize: 50 * 1024 * 1024 },   // hard per-route cap
  });

  bb.on('file', async (fieldname, fileStream, info) => {
    // info: { filename, encoding, mimeType } — mimeType is from client, do NOT trust
    const key = keyFor(req.tenantId, info.filename);

    const upload = new Upload({
      client: s3,
      params: {
        Bucket: process.env.STORAGE_BUCKET,
        Key: key,
        Body: fileStream,
        ContentType: info.mimeType,    // record; validate via magic bytes after
      },
      partSize: 5 * 1024 * 1024,       // 5 MiB — R2 minimum (B2 accepts smaller)
      queueSize: 4,                     // parallel parts; cap memory per concurrent req
    });

    try {
      await upload.done();
      res.json({ ok: true, key });
    } catch (e) {
      next(e);
    }
  });

  // pipeline() propagates errors both ways — .pipe() does NOT
  pipeline(req, bb).catch(next);
});
```

**Mandates:**

- **`busboy` v2 over `multer`/`formidable`.** `multer.memoryStorage()` and disk-buffering setups buffer the entire file before write — instant OOM under concurrent load. `busboy` is raw unbuffered multipart parsing.
- **`pipeline()` from `node:stream/promises`** — never `.pipe()`. Legacy pipe doesn't propagate downstream errors; if the S3 upload fails, the read stream hangs and leaks file descriptors. (Identical rule in `12-node.md`.)
- **`@aws-sdk/lib-storage` `Upload` class** for multipart — it manages backpressure natively, pausing the readable when internal buffers approach the high-water mark.
- **`partSize: 5 * 1024 * 1024`** (5 MiB) for R2 compatibility (R2 enforces 5 MiB minimum chunks, except the final chunk). B2 is more permissive but 5 MiB is a safe default.
- **`queueSize`** caps parallel parts; tune by memory budget. Default 4 keeps memory under 25 MiB per concurrent request.

### Bucket lifecycle: abort incomplete multipart uploads

Configure backend lifecycle policy to abort incomplete multipart uploads after **24 hours**. Without this, orphaned parts accumulate as invisible billable storage. (Configured at bucket provisioning time, not in code — document in deploy plan.)

## Server-Side Validation

### Magic-byte MIME detection — `file-type` v19+ only

Client-provided `Content-Type` headers and filename extensions are arbitrary; never trust them. Use the pure-JS `file-type` package on the initial stream buffer:

```js
import { fileTypeFromBuffer } from 'file-type';

// Read first 4096 bytes from the stream's beginning into a buffer
const sniffed = await fileTypeFromBuffer(headerBuffer);
if (!sniffed || !ALLOWED_MIME.includes(sniffed.mime)) {
  throw new AppError(415, 'UNSUPPORTED_MEDIA', `Detected: ${sniffed?.mime || 'unknown'}`);
}
```

**Banned:** `mmmagic`, `libmagic` C-bindings — block the event loop and require native compilation in Docker.

### Polyglot file defense

Magic byte validation is necessary but NOT sufficient. A polyglot file has valid magic bytes for one format while internally conforming to another. Acute risk areas:

- **MS Office (.docx, .xlsx)** — ZIP-based; sniff identifies them as ZIP, missing the Office semantic structure.
- **EPUB** — also ZIP-based; same trap.
- **PDF with embedded JavaScript** — magic bytes say PDF, payload includes executable JS that exploits parser bugs.

**Defense:** enforce strict parity between detected MIME, parsed internal structure, and the allowed extension list. For Office and EPUB:

- Either accept as opaque blobs (skip deep parsing) and let `clamd` do the deep inspection
- Or reject the upload class entirely if your service doesn't need them

**Never attempt deep semantic parsing of Office/PDF/EPUB inside the file-api Node process** — fragile, CVE-rich. Delegate to `clamd` (deep ZIP scanning) and image-broker (image format normalization).

### Filename sanitization (OWASP-aligned)

```js
import { normalize } from 'node:string_decoder';

function sanitizeFilename(raw) {
  // 1. Unicode NFC normalization — visually identical chars map to same bytes
  let s = raw.normalize('NFC');
  // 2. Strip directory separators + null byte (path traversal defense)
  s = s.replace(/[\\/\x00]/g, '');
  // 3. Lowercase ASCII-ish, replace unsafe chars
  s = s.toLowerCase().replace(/[^a-z0-9._-]/g, '-');
  // 4. Block Windows reserved names — defensive even on Linux (sync to Win envs)
  const reserved = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)/i;
  if (reserved.test(s)) s = '_' + s;
  // 5. Truncate to 255 BYTES (not chars) for PG + backend key limits
  const buf = Buffer.from(s, 'utf8');
  if (buf.length > 255) s = buf.slice(0, 255).toString('utf8');
  return s;
}
```

Rules:

- **NFC normalization** prevents blocklist bypass via decomposed Unicode variants.
- **Strip `/`, `\`, `\0`** for path traversal defense.
- **Block Windows reserved names** (CON, PRN, AUX, NUL, COM1–9, LPT1–9) even on Linux — files may sync to Windows environments later.
- **255-BYTE max** (not characters) — matches Postgres `VARCHAR(255)` byte semantics and most backend object-key limits.

## Cryptographic Deduplication (`blake3`, tenant-scoped)

```js
import { blake3 } from '@noble/hashes/blake3';

// During /finalize, compute hash from stored object (or client-supplied x-content-hash header)
const hash = Buffer.from(blake3(fileBuffer)).toString('hex');
```

**Algorithm choice:**

- **`blake3` is mandated.** Cryptographic collision resistance (full 256-bit security) + outperforms SHA-256 on stream processing.
- **`xxHash3` is BANNED for dedup.** Non-cryptographic — malicious tenant can engineer a collision, overwriting a legitimate file with their malicious payload.

**Scope:**

- Composite unique constraint: `UNIQUE (tenant_id, blake3_hash)` on the `files` table.
- **Cross-tenant dedup is BANNED** — privacy side-channel: instantaneous "upload" for Tenant A reveals that Tenant B already possesses the exact file (probabilistic confirmation of confidential documents).
- Per-tenant dedup is fine and saves storage — when (tenant_id, hash) exists with `status='available'`, return the existing storage key instead of issuing a new upload URL.

## Metadata Table (`files`)

```sql
CREATE TABLE files (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  uploader_id     UUID NOT NULL,
  storage_key     TEXT NOT NULL UNIQUE,         -- tenant-scoped path in bucket
  bucket          TEXT NOT NULL,                 -- which backend (b2 / r2 default; supabase legacy)
  original_filename TEXT NOT NULL,               -- raw (audited)
  sanitized_filename TEXT NOT NULL,              -- NFC-normalized, sanitized
  mime_type       TEXT NOT NULL,                 -- SERVER-SNIFFED, not client-claimed
  size_bytes      BIGINT NOT NULL,
  blake3_hash     TEXT NOT NULL,
  status          TEXT NOT NULL,                 -- pending_upload | scanning | available | quarantined | soft_deleted
  idempotency_key TEXT,
  uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ,                   -- for pending_upload sweeper
  deleted_at      TIMESTAMPTZ,
  hard_delete_at  TIMESTAMPTZ,                   -- for KVKK sweeper
  CONSTRAINT files_tenant_hash_uq UNIQUE (tenant_id, blake3_hash)
);
CREATE INDEX files_tenant_idx ON files(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX files_status_expires_idx ON files(status, expires_at) WHERE status = 'pending_upload';
CREATE INDEX files_hard_delete_idx ON files(hard_delete_at) WHERE deleted_at IS NOT NULL;
```

- Per `25-data-postgres.md`: use `gen_random_uuid()` for IDs; index strategy follows the same partial-index pattern.
- Per `95-multi-tenant-saas.md`: every query MUST be tenant-scoped — `WHERE tenant_id = current_tenant()`. RLS is the safety net, not the primary filter.

## Async Pipeline — Image Broker + ClamAV

### Image processing → delegate to `image-broker`

- **Inline `sharp` is acceptable ONLY for trivial low-concurrency thumbnail generation** (e.g., admin dashboard avatars). Default to "trivial = forbidden, delegate".
- For anything user-facing or high-concurrency: delegate to the `image-broker` microservice. It assumes the risk of parsing headers, enforcing dimensional limits (reject > 8000 px any side — decompression-bomb defense), and stripping all EXIF metadata (geo-coordinates, device IDs).
- **Image-broker availability:** per `agents-fabrik.md § Fabrik Microservices`, image-broker is currently retired/not-deployed. New file-api projects that need image processing must either: (a) re-deploy image-broker first (re-build from `templates/file-api/` cousin + spec), or (b) vendor `/opt/fabrik-lib/image-broker/` as a copy per the `fabrik-lib` discipline. Do NOT inline `sharp` as a workaround.

### Antivirus scanning → `clamd` sidecar, TCP :3310 INSTREAM

**Why on-premise:** TR data sovereignty rules forbid transmitting tenant files to third-party (VirusTotal, etc.) for scanning.

**Why TCP over Unix socket:** sidecar deployments are incompatible with shared-volume mounts on dynamic container orchestration. TCP works across the `fabrik` Docker network.

```js
import net from 'node:net';

async function scanWithClamd(stream) {
  const sock = net.createConnection({ host: 'clamd', port: 3310 });
  return new Promise((resolve, reject) => {
    sock.write('zINSTREAM\0');
    stream.on('data', (chunk) => {
      const lenBuf = Buffer.alloc(4);
      lenBuf.writeUInt32BE(chunk.length, 0);
      sock.write(lenBuf);
      sock.write(chunk);
    });
    stream.on('end', () => {
      sock.write(Buffer.from([0, 0, 0, 0]));   // zero-length terminator
    });
    let response = '';
    sock.on('data', (d) => { response += d.toString(); });
    sock.on('end', () => {
      if (response.includes('FOUND')) resolve({ verdict: 'malicious', detail: response });
      else if (response.includes('OK')) resolve({ verdict: 'clean' });
      else reject(new Error(`clamd unknown response: ${response}`));
    });
    sock.on('error', reject);
  });
}
```

### State machine

```text
pending_upload   → /finalize call lands     → scanning
scanning         → clamd verdict = clean    → available
                 → clamd verdict = malicious → quarantined + DeleteObjectCommand
                 → clamd circuit open       → stays scanning, retried later by worker
```

The scan runs in a background worker (per `75-workers-jobs.md`), not on the request thread. On `Verdict.Malicious`, the worker immediately fires `DeleteObjectCommand` to purge the object AND sets `status='quarantined'` for audit.

### `clamd.conf` tuning

`StreamMaxLength` in the clamd sidecar config MUST be ≥ the API's max upload size. Setting `StreamMaxLength 200M` for a 100 MB max-upload service is safe; setting it lower causes false-rejection `INSTREAM size limit exceeded`.

## Data Lifecycle & KVKK Compliance

The TR LLC operates under KVKK (Personal Data Protection Law). KVKK Article 7 + By-Law Article 11 mandate periodic erasure of expired personal data — including file metadata AND the underlying binary blob.

### Soft-delete → hard-delete pipeline

```text
user deletes file     → UPDATE files SET deleted_at=now(), hard_delete_at=now() + 30 days,
                                          status='soft_deleted'
30 days pass          → sweeper picks up where now() > hard_delete_at
hard-delete TX        → BEGIN
                          DELETE FROM files WHERE id = $1
                          await s3.send(new DeleteObjectCommand({Bucket, Key: storageKey}))
                          INSERT INTO file_erasure_audit (...)
                        COMMIT
```

**Mandates:**

- KVKK By-Law Article 11: periodic disposal interval **cannot exceed 6 months**. Sweeper runs at least every 30 days.
- **Dual-action transaction:** PG row purge + sync `DeleteObjectCommand` to the storage backend. Storage backends do NOT track orphans; failure to delete the object = compliance violation + bloated bill.
- **Hard-delete is FINAL** — no recovery window after `hard_delete_at` passes.
- **Audit log retention: 3 YEARS minimum** per KVKK By-Law Article 7(3). Use the `file_erasure_audit` tamper-evident table (schema below).
- **Tamper-evident hash chain mandatory** per KVKK By-Law Article 7(3) ("destruction must be verifiable"). REVOKE UPDATE/DELETE alone proves the row wasn't touched through normal channels — it does NOT prove a privileged process didn't alter the row contents. The hash chain (`prev_hash` + `current_hash` per row) makes any alteration cryptographically detectable. Mirrors the canonical pattern in `core/app-audit-log.md` § Hash-Chain Verification.

### `file_erasure_audit` schema (hash-chained, mirrors `app-audit-log.md`)

```sql
CREATE TABLE file_erasure_audit (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts                TIMESTAMPTZ NOT NULL DEFAULT now(),
  file_id           UUID NOT NULL,                   -- original files.id (not FK — files row is gone)
  tenant_id         UUID NOT NULL,
  storage_key       TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  sanitized_filename TEXT NOT NULL,
  size_bytes        BIGINT NOT NULL,
  blake3_hash       TEXT NOT NULL,                   -- of the file content at erasure time
  bucket            TEXT NOT NULL,
  reason            TEXT NOT NULL,                   -- 'user_request' | 'retention_policy' | 'quarantine' | 'gdpr_request'
  erased_by         UUID,                            -- user_id or service_id; NULL = automated sweeper
  -- Hash chain (KVKK Art. 7(3) tamper-evidence)
  prev_hash         TEXT,                            -- current_hash of the previous row (NULL for genesis row)
  current_hash      TEXT NOT NULL                    -- sha256(prev_hash || canonicalised(row content))
);
-- Append-only (REVOKE keeps normal channels from mutating)
REVOKE UPDATE, DELETE ON file_erasure_audit FROM PUBLIC;
-- Genesis row check + hash continuity
CREATE INDEX file_erasure_audit_ts_idx ON file_erasure_audit(ts);
```

**Hash computation** (BEFORE INSERT trigger, same pattern as `app-audit-log.md` § Hash-Chain Verification):

1. `prev_hash := (SELECT current_hash FROM file_erasure_audit ORDER BY ts DESC LIMIT 1)` — NULL on first row.
2. `current_hash := encode(digest(coalesce(prev_hash, '') || canonicalise(NEW), 'sha256'), 'hex')` via `pgcrypto`.
3. `canonicalise(NEW)` = deterministic concatenation of `(file_id, tenant_id, storage_key, sanitized_filename, size_bytes, blake3_hash, bucket, reason, erased_at, coalesce(erased_by::text, ''))` — stable column order, no whitespace, no JSON.

**Verification** (run quarterly + on regulator request):

- `verify_chain()`: walk rows in `ts` order; recompute each `current_hash` from stored `prev_hash` + row content; report any mismatches.
- Mirrors `app-audit-log.md` § Hash-Chain Verification (same algorithm, same retention discipline) — coding agents implementing this should vendor the verifier from `/opt/fabrik-lib/app-audit-log/` and adapt it to the `file_erasure_audit` schema rather than reinvent it.

**Why a sibling table (not the central `audit_log`):**

- High volume — every soft-delete + every hard-delete writes a row; bursts during retention sweeps. Keeping them out of the central `audit_log` protects its query performance for `auth.*` / `billing.*` / `admin.*` events.
- File-specific fields (`storage_key`, `blake3_hash`, `bucket`) are first-class columns here for direct query; if recorded in `audit_log` they'd live in the `details` JSONB and require JSON path queries.
- Same tamper-evident contract: append-only + hash chain + 3-year retention + REVOKE — KVKK Article 7(3) compliance is identical.

Operators MAY additionally record higher-level erasure decisions (e.g., a manually-fulfilled GDPR/KVKK SAR covering many files) into the central `audit_log` via `al.record_event(action="gdpr.user_data_erased", details={user_id, file_count, ...})` from `/opt/fabrik-lib/app-audit-log/`. The per-file `file_erasure_audit` rows provide the granular proof; the central event provides the user-level summary.

## Health Endpoint

`/health` must verify the storage backend reachability — not just process liveness (mandate per `55-observability.md`):

```js
import { HeadBucketCommand } from '@aws-sdk/client-s3';

app.get('/health', async (req, res) => {
  if (isShuttingDown) return res.status(503).json({ status: 'draining' });
  try {
    await db.query('SELECT 1');
    await s3.send(new HeadBucketCommand({ Bucket: process.env.STORAGE_BUCKET }));
    // clamd reachability check (cheap — connect/disconnect)
    await new Promise((resolve, reject) => {
      const sock = net.createConnection({ host: 'clamd', port: 3310 });
      sock.on('connect', () => { sock.end(); resolve(); });
      sock.on('error', reject);
    });
    res.json({ status: 'ok' });
  } catch (e) {
    res.status(503).json({ status: 'degraded', error: e.message });
  }
});
```

## Resilience integration

All S3, clamd, image-broker calls follow `58-resilience.md`:

- Timeout: undici `requestTimeout: 60_000`; opossum `timeout: 15_000` for clamd/image-broker.
- Retry: `ConfiguredRetryStrategy` adaptive mode (above). Max 3 attempts. Exponential backoff with jitter.
- Circuit breaker: opossum on image-broker + clamd; pg pool handles its own degraded-mode behavior.
- Graceful fallback: clamd-circuit-open → keep status='scanning', retry next sweeper cycle. image-broker-circuit-open → reject upload with `503 IMAGE_BROKER_UNAVAILABLE`.

---

## Banned Patterns

| Pattern | Use Instead | Reason |
| --- | --- | --- |
| `multer.memoryStorage()` / full buffering | `busboy` v2 + `pipeline()` + `@aws-sdk/lib-storage` `Upload` | Full buffering exhausts V8 heap; immediate OOM under concurrent load |
| `stream.pipe()` | `pipeline()` from `node:stream/promises` | `.pipe()` doesn't propagate downstream errors; hung streams leak FDs (also banned by `12-node.md`) |
| Default `NodeHttpHandler` in AWS SDK v3 | `UndiciHttpHandler` with pooled keep-alive | 35–45% perf penalty under parallel load |
| Trusting client `Content-Type` / extension | `file-type` v19+ magic-byte sniff on first 4 KB | Headers and extensions are trivially spoofed |
| `mmmagic` / native libmagic | `file-type` pure-JS package | Blocks event loop + Docker native-compile friction |
| Cross-tenant dedup | `UNIQUE (tenant_id, blake3_hash)` | Privacy side-channel: confirms cross-tenant file presence |
| `xxHash3` / non-cryptographic hash for dedup | `blake3` (`@noble/hashes/blake3`) | Collision-engineerable; allows overwrite of legitimate files |
| Inline `sharp` for non-trivial image work | Delegate to `image-broker` microservice | libvips OOM + decompression-bomb risk + EXIF leakage |
| `multer` / `formidable` for multipart | `busboy` v2 | Buffering by default; busboy is raw unbuffered parsing |
| Reusing presigned PUT URLs | DB-backed state machine with `/finalize` | S3 doesn't enforce single-use; reuse-until-expiry is the default attack surface |
| `expiresIn > 900` for PUT URLs | ≤ 900 (15 min) per NIST SP 800-63B observation contracts | Longer windows widen interception/replay surface |
| Presigned signature without `ContentType` + `ContentLength` | Both fields in `PutObjectCommand` | Without them, attacker can replay URL with arbitrary payload size/type |
| `x-amz-acl` headers (e.g., on Supabase Storage) | Bucket policies + IAM/R2 token scoping | Supabase Storage rejects the header outright |
| Synchronous clamd scan during the upload request | Async worker via state machine (`scanning` → `available` / `quarantined`) | Streaming large files to clamd in-request exhausts API threads |
| Commercial AV API (VirusTotal etc.) | `clamd` sidecar TCP :3310 INSTREAM | TR data sovereignty — no third-party file transmission |
| Unix-socket clamd communication | TCP :3310 over `fabrik` network | Shared-volume mounts are incompatible with sidecar orchestration |
| Local-disk storage in production | B2 / R2 (Supabase Storage legacy-only) | Containers redeploy and lose volumes; Backrest can't index large mutable blobs |
| Hard-delete user file without storage-side `DeleteObjectCommand` | Dual-action transaction (PG row + SDK delete) | Storage backends don't track orphans; KVKK compliance violation |
| Pure soft-delete with no hard-delete sweeper | Sweeper at ≤ 6 month interval per KVKK By-Law Article 11 | KVKK mandate; non-compliance + bloated storage bill |
| File erasure without audit row | `file_erasure_audit` hash-chained row, retained 3 years | KVKK By-Law Article 7(3); legal-evidence trail |
| `file_erasure_audit` without `prev_hash` + `current_hash` columns | Hash-chained schema mirroring `app-audit-log.md` (BEFORE INSERT trigger via `pgcrypto` digest) | REVOKE alone is not tamper-evident; KVKK Art. 7(3) requires verifiable destruction |
| Reinventing a verifier instead of vendoring | Vendor `/opt/fabrik-lib/app-audit-log/` `verify_chain()` and adapt to `file_erasure_audit` | Identical algorithm; reinvention drifts |

---

## Related Rule Packs

- `12-node.md` — Node runtime, Express/Fastify, `pipeline()`, `crypto.timingSafeEqual()`, npm hygiene
- `15-api-contracts.md` — request/response shape, idempotency, error format
- `25-data-postgres.md` — `gen_random_uuid()`, indexing, RLS pattern
- `35-security-auth.md` — Pattern A FastAPI Bearer JWT (Supabase Pattern B legacy), M2M `X-Internal-Token`, secrets policy
- `55-observability.md` — `/health` real-dep check (now must include `HeadBucketCommand`), `/metrics`
- `58-resilience.md` — timeout / retry / opossum circuit breakers
- `30-ops.md` — `clamd` + `image-broker` sidecar declarations in compose, fabrik network membership
- `75-workers-jobs.md` — AV scan worker, KVKK retention sweeper, pending-upload sweeper
- `95-multi-tenant-saas.md` — tenant_id scoping, RLS, per-tenant rate limiting
- `app-audit-log.md` — immutable audit table pattern, REVOKE strategy
- `cost-budget.md` — bucket lifecycle (24h multipart abort) prevents invisible billable orphans

---

## Done When

- [ ] `S3Client` instantiated via `@smithy/undici-http-handler` with adaptive `ConfiguredRetryStrategy`.
- [ ] Cloudflare R2 clients set `region: 'auto'`; Backblaze B2 clients set `forcePathStyle: true`; (legacy) Supabase Storage injects user JWT via `sessionToken`.
- [ ] Presigned PUT URLs cap `expiresIn: 900` AND include `ContentType` + `ContentLength` in the signature.
- [ ] Single-use enforcement via DB state machine: `pending_upload` → `/finalize` → `scanning` → `available`/`quarantined`.
- [ ] (legacy Supabase Storage only) No `x-amz-acl` headers on requests.
- [ ] Direct uploads use `busboy` v2 + `pipeline()` from `node:stream/promises` + `@aws-sdk/lib-storage` `Upload` (`partSize: 5MiB`, `queueSize` bounded).
- [ ] Bucket lifecycle policy aborts incomplete multipart uploads after 24h.
- [ ] MIME validation via `file-type` v19+ magic-byte sniff on first 4 KB; no `mmmagic` or `libmagic`.
- [ ] Polyglot defense: Office/EPUB/PDF deep inspection delegated to clamd; no in-process semantic parsing.
- [ ] Filename sanitization: NFC normalization, path-traversal strip, Windows-reserved-name block, 255-byte truncation.
- [ ] Content-hash via `blake3` (`@noble/hashes/blake3`); composite unique `UNIQUE (tenant_id, blake3_hash)`; cross-tenant dedup blocked.
- [ ] Image processing delegated to `image-broker` (or vendored from `fabrik-lib`); no inline `sharp` for production paths.
- [ ] Antivirus via `clamd` sidecar over TCP :3310 INSTREAM; verdict updates `files.status` to `available`/`quarantined`; quarantine triggers `DeleteObjectCommand`.
- [ ] `clamd.conf` `StreamMaxLength` ≥ API max upload size.
- [ ] opossum circuit breakers around `image-broker` and `clamd` calls; 15s timeout, 50% error threshold.
- [ ] `Idempotency-Key` header honored; duplicate keys return existing row.
- [ ] Auth + tenant scoping enforced server-side; `tenant_id` derived from JWT/M2M context, NEVER from request body.
- [ ] `/health` verifies storage backend (`HeadBucketCommand`) AND clamd reachability AND DB.
- [ ] KVKK hard-delete sweeper runs at ≤ 6-month interval; dual-action TX (PG row + SDK `DeleteObjectCommand`).
- [ ] `file_erasure_audit` hash-chained table (`prev_hash` + `current_hash` via BEFORE INSERT trigger, `pgcrypto` digest) populated on every erasure; retained ≥ 3 years; UPDATE/DELETE revoked; `verify_chain()` vendored from `/opt/fabrik-lib/app-audit-log/` and adapted to this schema; quarterly chain-verification scheduled. KVKK Art. 7(3) tamper-evident.
- [ ] Storage credentials in env vars only (`STORAGE_KEY_ID`, `STORAGE_SECRET`) — never hardcoded.
- [ ] No local-disk persistence in production code paths.
