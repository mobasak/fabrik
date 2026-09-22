---
activation: glob
globs: ["**/file-api/**", "**/uploads/**", "**/storage/**", "**/presigned/**", "**/multipart/**", "**/clamav/**", "**/file-api*.js", "**/file-api*.ts"]
description: File-handling discipline — S3-compatible storage (B2/R2 default; Supabase Storage legacy), presigned URL contracts, busboy + pipeline streams, magic-byte + polyglot validation, tenant-scoped blake3 dedup, clamd service, KVKK erasure lifecycle
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents (Claude Code + dispatched subagents)
     GOAL: File-handling patterns for the file-api scaffold + any service that uploads, stores, validates, or deletes user files
     AGENT USAGE: Follow verbatim. Composes with 12-node.md (Node runtime). Research basis: docs/reference/research/Node API File Storage Rules.md — superseded where this pack corrects it. -->

# File API Rules

**Activation:** Glob `**/file-api/**`, `**/uploads/**`, `**/storage/**`, `**/presigned/**`, `**/multipart/**`, `**/clamav/**`
**Purpose:** Production patterns for services that upload, store, validate, dedupe, scan, or destroy user files on Fabrik's VPS fleet.
**Scope:** `file-api` scaffold + any service handling binary uploads. Composes with `12-node.md` (Node runtime), `25-data-postgres.md` (metadata schema), `95-multi-tenant-saas.md` (tenant isolation), `app-audit-log.md` (audit chain).
**Research basis:** [`docs/reference/research/Node API File Storage Rules.md`](../../../docs/reference/research/Node%20API%20File%20Storage%20Rules.md) — it misattributes the presigned-URL window to NIST and misquotes the undici benchmark; this pack is the corrected reading.

---

## What the Scaffold Ships — and What It Does Not

`fabrik scaffold --type file-api` emits a **CommonJS Express** service (`src/index.js`, `require()`), and this pack's code is written for that shape. The shipped service is a presigned-URL issuer over one S3-compatible bucket: upload/download URL endpoints, a `confirm` step, tenant-scoped list/get/delete, and `/health` + `/api/health` that run `HeadBucketCommand`. Its env names are `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_REGION`, `R2_FORCE_PATH_STYLE` (used for B2 too), `UPLOAD_URL_EXPIRY_SECONDS`, `DOWNLOAD_URL_EXPIRY_SECONDS`, `MAX_FILE_SIZE_MB`, `ALLOWED_CONTENT_TYPES`.

It does **not** ship: direct streaming uploads, magic-byte validation, blake3 dedup, the clamd scan, the erasure sweeper, or the audit chain — every section below is work the project adds. ⚠️ Shipped behaviours that contradict this pack, the project's to correct until the scaffold is fixed: it authenticates and stores metadata through `@supabase/supabase-js` (the legacy Pattern B — § Architecture); its presigned PUT does not sign `Content-Type` (§ Presigned URLs); its `DELETE` swallows a failed storage delete, then drops the row (§ Data Lifecycle); its S3 client hard-wires the undici handler and the deprecated `@aws-sdk/util-retry` with no measurement (§ AWS SDK); its sanitizer and `uploads/{tenant}/{id}{ext}` keys differ from § Presigned URLs and § Filename sanitization; `.env.example` says B2 requires path-style (it does not) and cites a NIST rule that does not exist; `/health` skips `HeadBucketCommand` when `R2_BUCKET` is unset; both healthchecks target the dependency-checking endpoint with no `/healthz`; `authMiddleware` takes the caller's FIRST tenant membership; `DOWNLOAD_URL_EXPIRY_SECONDS` is uncapped; and `cors()` is open to every origin.

**ESM-only dependencies in a CommonJS service:** `file-type` and `@noble/hashes` are ESM-only. Load them with dynamic `import('…')` INSIDE an async function (or memoise the promise: `const fileTypeP = import('file-type')`) — never `await` at module top level, which a CommonJS file cannot run (`12-node.md`'s "never mix `require()` and `import`" is about static `import`; a dynamic `import()` of an ESM-only dependency is the sanctioned exception in a CJS service). It works on every supported Node line. `require()` of an ES module is unflagged on the LTS lines but throws on any module with top-level `await` (claim `node-require-esm`) — dynamic `import()` has no such edge.

## Architecture & Threat Model

- **Container volumes are ephemeral.** A redeploy destroys local disk, so **all binary persistence goes to an external S3-compatible backend** — never local disk in production.
- **Multi-tenant isolation at the metadata tier.** Every file row carries `tenant_id`; every query is tenant-scoped (`95-multi-tenant-saas.md`, whose RLS helper is `current_tenant_id()`).
- **Auth** (`35-security-auth.md` § API-based systems): a human caller presents the Pattern A JWT minted by `fabrik-lib/fastapi-user-auth` — HS256, required `exp` + `sub`, tenant in the `tid` claim. Validate it with a maintained JWT library, algorithms pinned to `HS256`; derive `tenant_id` from `tid`, never from the request body — a token whose `tid` is null (the IdP allows it) answers 403. ⚠️ HS256 is symmetric: the verification secret can also MINT tokens, so it is an IdP-grade secret. The IdP's `jti` denylist is not visible to this service — logout takes effect at access-token expiry unless the denylist store is shared. Service callers use `X-Internal-Token` (`35` § Internal Service Auth). A project still on Supabase Auth (Pattern B) keeps the shipped `supabase.auth.getUser()` path until it migrates.
- **Threats this pack defends against:** ZIP bombs, image decoder bugs, polyglot files, presigned URL replay, cross-tenant dedup side-channel, OOM via in-memory buffering, a silently truncated upload stored as complete. (Document-renderer SSRF is out of scope because nothing here renders documents — § Polyglot; supply-chain risk in the detection libraries is `12-node.md`'s npm hygiene.)
- **Decoupling principle:** every high-risk binary operation runs **outside the API process** — AV scanning in the `clamd` service, image transforms in a worker (§ Image transforms).

## Storage Backend Selection

Two default backends plus one legacy option. Pick by need; never run two in parallel for the same project.

| Backend | When | Client configuration |
| --- | --- | --- |
| **Backblaze B2** | Default for new file-api services. `fabrik-lib/storage` is the Python face of the same B2 bucket model (`agents-fabrik.md` § Supabase). | `endpoint: https://s3.<region>.backblazeb2.com`, the real region. B2 accepts BOTH virtual-hosted and path-style addressing; `forcePathStyle` is optional. Multipart parts 5 MB–5 GB, ≤ 10,000 parts. |
| **Cloudflare R2** | High-egress workloads or projects already on Cloudflare (R2 egress is free; B2's is free up to 3× stored bytes). | `endpoint: https://<account>.r2.cloudflarestorage.com`, `region: 'auto'`. Multipart parts 5 MiB–5 GiB, ≤ 10,000 parts, and **every non-final part the same size**. Presigned URLs work only on the account endpoint, never a custom domain. |
| **Supabase Storage** (legacy) | **Legacy — migrate to self-hosted.** ONLY a project already on Supabase for auth/DB and not yet migrated; new services use B2/R2. | Endpoint `https://<project_ref>.storage.supabase.co/storage/v1/s3`, `forcePathStyle: true`; per-user access: `accessKeyId` = project ref, `secretAccessKey` = anon key, `sessionToken` = the user's JWT (RLS applies). Generated S3 access keys BYPASS RLS — server-side only. ACL headers (`x-amz-acl`, `x-amz-grant-*`) and versioning are not implemented. |

Numbers and provider rules: claims `r2-s3-limits`, `b2-s3-addressing-limits`, `supabase-storage-s3-auth`.

**Banned:**

- **AWS S3 direct** — no operational advantage over B2/R2 for this fleet.
- **MinIO self-hosted** — operational tax; B2/R2 are already paid for.
- **Local-disk storage in production** — containers redeploy and lose volumes.

**SDK data-integrity defaults.** Current `@aws-sdk/client-s3` sends a CRC checksum on uploads and validates it on downloads by default. B2 and R2 accept it per their current docs; a backend that answers `400 Unsupported header 'x-amz-checksum-…'` gets `requestChecksumCalculation: 'WHEN_REQUIRED'` and `responseChecksumValidation: 'WHEN_REQUIRED'` on THAT client — a per-backend workaround, not a default (claim `aws-sdk-checksum-defaults`).

## AWS SDK for JavaScript — Request Handler & Retry

```js
const { S3Client } = require('@aws-sdk/client-s3');
const { NodeHttpHandler } = require('@smithy/node-http-handler');   // the SDK's own default handler

const s3 = new S3Client({
  region: process.env.R2_REGION || 'auto',
  endpoint: process.env.R2_ENDPOINT,
  forcePathStyle: process.env.R2_FORCE_PATH_STYLE === 'true',
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
  },
  requestHandler: new NodeHttpHandler({
    connectionTimeout: Number(process.env.S3_CONNECT_TIMEOUT_MS || 30_000),   // 58's B2 row: 30 s connect
    requestTimeout: Number(process.env.S3_REQUEST_TIMEOUT_MS || 120_000),     // 58's B2 row: 120 s read
    throwOnRequestTimeout: true,   // without it an elapsed requestTimeout only LOGS a warning — the call hangs (claim `smithy-request-timeout`)
  }),                              // the default handler has no request timeout at all
  maxAttempts: 3,               // standard retry mode: exponential backoff with jitter + a retry quota
});
```

- **Request handler:** the SDK's Node default (`node:http`/`node:https`, keep-alive on) is the default here too. `@smithy/undici-http-handler` is an AWS-published OPTIONAL alternative; its README benchmark reports 35–50% less time in request handling on a local server and tells you to benchmark your own case — adopt it with that measurement, never as a mandate (claim `aws-sdk-undici-handler`).
- **Retry:** the standard mode above is the default. `ConfiguredRetryStrategy` (from `@smithy/util-retry`; `@aws-sdk/util-retry` is deprecated) is standard mode with a CUSTOM backoff — not adaptive. Adaptive mode (`retryMode: 'adaptive'`) adds a per-client rate limiter that can delay first attempts; AWS does not recommend it as a default nor for one client serving many tenants — so not here (claim `aws-sdk-retry-modes`).
- **Circuit breakers:** wrap every call to the `clamd` service and any image worker with a breaker that satisfies `58-resilience.md` § Circuit-Breaker Pattern's invariants. `opossum` meets the half-open ones; its trip rule is a rolling-window error PERCENTAGE, so set `volumeThreshold` — without it (default 0) one failure in a quiet window is 100% and opens the circuit, where 58 wants a count (claim `opossum-trip-rule`):

```js
const CircuitBreaker = require('opossum');

const env = (k, d) => Number(process.env[k] || d);   // 58: every breaker threshold is an env var
const scanBreaker = new CircuitBreaker(scanWithClamd, {
  timeout: env('CLAMD_TIMEOUT_MS', 15_000),              // rejects the CALL — it does not stop the scan (below)
  errorThresholdPercentage: env('CLAMD_CB_ERROR_PCT', 50), // opens ABOVE this percentage
  resetTimeout: env('CLAMD_CB_RESET_MS', 30_000),        // half-open probe after this
  volumeThreshold: env('CLAMD_CB_VOLUME', 5),            // ≥ N calls in the window before the percentage counts
});
// The fallback runs on EVERY failure and timeout, not only when open — name which one it was.
scanBreaker.fallback(() => ({ verdict: 'unscanned', reason: scanBreaker.opened ? 'clamd_circuit_open' : 'clamd_error' }));
scanBreaker.on('open', () => logger.warn('clamd circuit OPEN'));
```

  For Postgres metadata writes, rely on the pool's own behaviour (`58-resilience.md`); a breaker on top of pg is overkill.
- **Idempotency-Key:** clients send an `Idempotency-Key` header; a duplicate key returns the existing metadata row instead of creating a second one.

## Presigned URLs — the default upload topology (≥ 50 MB)

For files above ~50 MB, the client uploads straight to the backend — never proxied through Node. The backend does not enforce single use, so the guardrails live in the application.

### URL issuance

```js
const { PutObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');

// Presign with a client that does NOT add default checksums: otherwise the presigner signs the
// CRC32 of an EMPTY body into the URL (x-amz-checksum-crc32=AAAAAA==), and a backend that
// validates it refuses every real upload.
const presignS3 = new S3Client({ /* same endpoint + credentials as s3 */ requestChecksumCalculation: 'WHEN_REQUIRED' });

async function issueUploadUrl({ key, contentType, contentLength, expiresIn = 900 }) {
  if (expiresIn > 900) throw new Error('expiresIn capped at 900s');   // house policy, below
  const command = new PutObjectCommand({
    Bucket: process.env.R2_BUCKET,
    Key: key,                            // tenant-scoped path (below)
    ContentType: contentType,
    ContentLength: contentLength,
  });
  return getSignedUrl(presignS3, command, {
    expiresIn,
    signableHeaders: new Set(['content-type']),   // the presigner leaves content-type UNSIGNED by default
  });
}
```

**Rules:**

- **`expiresIn ≤ 900` seconds** — house policy. A presigned PUT is a bearer write capability until it expires; SigV4 allows up to 604,800 s (7 days), and 900 s is the presigner's own default. No standard mandates 900 — the old "NIST observation contract" attribution was false (claim `presigned-url-expiry`).
- **`Content-Type` binds only if you sign it.** The presigner adds `content-type` to its unsignable set, so without `signableHeaders: new Set(['content-type'])` a replayed URL accepts any type. `ContentLength`, when set, stays a signed header — but ENFORCEMENT is the backend's: prove it once per backend with a probe — a PUT with a different length, and one with a different body under the same length, must both fail — and record the result in `docs/DEPLOYMENT.md` (claim `presigner-signed-headers`).
- **Presign with a `WHEN_REQUIRED` client.** The SDK's default checksum is computed at presign time over an empty body and signed into the URL; a backend that checks it rejects the real bytes (claim `presign-empty-body-checksum`).
- One URL per upload; single use is enforced **in application logic** (the state machine below).
- **Key naming:** `{tenant_id}/{yyyy}/{mm}/{file_id}-{sanitized_filename}`. Tenant scoping prevents cross-tenant exposure through a policy leak; date partitioning aids lifecycle rules.
- **No ACL headers** — Supabase Storage does not implement `x-amz-acl`; scope access with bucket policies and per-bucket tokens.

### Single-use via DB state machine

```text
client requests URL → INSERT files (status='pending_upload', expires_at=now()+15min)
client PUTs to URL  → object lands in bucket
client calls /finalize → verify the object (HeadObject size = signed length), UPDATE status='scanning'
                    → worker scans, sets 'available' or 'quarantined'
expires_at passed   → sweeper marks 'soft_deleted' with deleted_at = hard_delete_at = now(), delete_reason = 'upload_expired'; the next hard-delete pass removes object + row with an erasure audit row
```

`/finalize` is what retires the upload token at the application layer; without it the row stays `pending_upload` and is garbage-collected. (The scaffold's `confirm` endpoint jumps straight to `ready` with no scan — replace it with this machine.)

### Download presigned URLs

Symmetric: presigned GET. `expiresIn: 300` for private content; `3600` for short-lived public assets; never more than `86400` without a written reason.

## Direct Server Streaming (< 50 MB, or when a proxy is needed)

When the client cannot do the two-step flow, or the server must extract metadata during upload.

```js
const busboy = require('busboy');
const { Upload } = require('@aws-sdk/lib-storage');
const { pipeline } = require('node:stream/promises');

app.post('/upload', requireAuth, (req, res, next) => {
  let settled = false;
  let upload, key;
  const fail = (e) => {                                   // one response, whatever fails first
    if (settled) return;
    settled = true;
    upload?.abort();                                      // stop an in-flight upload
    next(e);
  };
  let bb;
  try {
    bb = busboy({ headers: req.headers, limits: { fileSize: 50 * 1024 * 1024, files: 1 } });
  } catch (e) {
    return fail(new AppError(415, 'NOT_MULTIPART'));   // busboy() THROWS on a non-multipart body
  }
  let sawFile = false;
  bb.on('filesLimit', () => fail(new AppError(400, 'ONE_FILE_ONLY')));   // a 2nd file is otherwise dropped silently
  bb.on('close', () => { if (!sawFile) fail(new AppError(400, 'NO_FILE')); });   // no file part ⇒ never hang
  bb.on('file', (fieldname, fileStream, info) => {
    sawFile = true;
    // info.mimeType is client-claimed — record it, validate by magic bytes after
    key = keyFor(req.tenantId, info.filename);
    upload = new Upload({
      client: s3,
      params: { Bucket: process.env.R2_BUCKET, Key: key, Body: fileStream },
      partSize: 5 * 1024 * 1024,        // 5 MiB — the R2/B2 minimum part size
      queueSize: 4,                     // parallel parts; bounds memory at ~queueSize × partSize
    });
    fileStream.on('limit', () => upload.abort());   // busboy TRUNCATES at fileSize — it never errors
    upload.done()                                    // abort() makes done() REJECT with an AbortError
      .then(() => {
        if (settled) {                                    // the request already failed — no row will point here
          return s3.send(new DeleteObjectCommand({ Bucket: process.env.R2_BUCKET, Key: key }));
        }
        settled = true;
        res.json({ ok: true });
      })
      .catch((e) => fail(e.name === 'AbortError' && fileStream.truncated
        ? new AppError(413, 'FILE_TOO_LARGE') : e));
  });
  pipeline(req, bb).catch(fail);        // pipeline() propagates errors both ways — .pipe() does NOT
});
```

**Mandates:**

- **`busboy` over `multer`/`formidable`.** `multer` is built on busboy, but `multer.memoryStorage()` holds the entire file in memory and its disk storage writes local disk. busboy hands each file over as a stream (claim `busboy-multer-facts`).
- **A `fileSize` breach is a silent truncation.** busboy emits `'limit'` (with `truncated` still false) and sets `stream.truncated` by the time the stream ends — it does not error. Abort the upload on `'limit'`; `upload.done()` then rejects with an `AbortError`, which maps to 413. Without the abort a cut-off file is stored as complete; without the `'close'` check a request with no file part never gets a response; `fileSize` is EXCLUSIVE (a file of exactly the limit is refused). One `fail()` guard keeps a client abort from answering twice, aborts an in-flight upload, and a completed upload whose request already failed (e.g. a second file) deletes its own object — otherwise it is an orphan no row references.
- **Direct streaming stays the < 50 MB exception.** `58-resilience.md`'s "B2 uploads go async, never inline in a handler" is written for the sync `boto3` client; `lib-storage` is async I/O, but a large upload still belongs on the presigned path.
- **`pipeline()` from `node:stream/promises`** — never `.pipe()`, which does not propagate downstream errors and leaks file descriptors (same rule in `12-node.md`).
- **`@aws-sdk/lib-storage` `Upload`** for multipart — it pulls one part per worker as the previous part finishes, which keeps buffering near `queueSize × partSize`. The 5 MiB `partSize` is the minimum on both R2 and B2, and a fixed `partSize` satisfies R2's equal-part rule.

### Incomplete multipart uploads

Orphaned parts are billable. House rule: incomplete multipart uploads are aborted **1 day** after initiation — an `AbortIncompleteMultipartUpload` rule (`DaysAfterInitiation: 1`) on R2, whose built-in default is 7 days; the equivalent rule on B2, set at provisioning. Record it in `docs/DEPLOYMENT.md` (bucket configuration, not code).

## Server-Side Validation

### Magic-byte MIME detection — `file-type`

Client `Content-Type` headers and extensions are arbitrary. Sniff the first bytes with `file-type` (claim `file-type-facts`):

```js
const { fileTypeFromBuffer } = await import('file-type');   // ESM-only — inside an async function in CJS
const sniffed = await fileTypeFromBuffer(headerBuffer);     // headerBuffer = the first 4100 bytes
if (!sniffed || !ALLOWED_MIME.includes(sniffed.mime)) {
  throw new AppError(415, 'UNSUPPORTED_MEDIA', `Detected: ${sniffed?.mime || 'unknown'}`);
}
```

- Read **4100 bytes** — the library's sample size. Its stream API takes a web `ReadableStream` (`Readable.toWeb()`).
- It tells OOXML (docx/xlsx/pptx) apart from ZIP; legacy `.doc`/`.xls`/`.ppt` (CFB) are NOT detected without an extra detector.

**Banned:** `mmmagic` / native `libmagic` bindings — they block the event loop and need native compilation in Docker.

### Polyglot file defense

A polyglot has valid magic bytes for one format while conforming to another internally. Acute risk: ZIP containers (OOXML, EPUB) and PDFs with embedded JavaScript.

- Enforce parity between the sniffed MIME, the allowed-extension list, and the upload class the service accepts.
- For Office, EPUB and PDF: either accept them as opaque blobs and let `clamd` do the deep container inspection, or reject the class if the service does not need it.
- **Never parse Office/PDF/EPUB semantically inside the file-api process** — fragile and CVE-rich.

### Filename sanitization

```js
function sanitizeFilename(raw) {
  let s = raw.normalize('NFC');                                   // canonical Unicode form
  s = s.replace(/[\\/\x00]/g, '');                                // path separators + NUL
  s = s.toLowerCase().replace(/[^a-z0-9._-]/g, '-');              // ASCII-only from here on
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)/i.test(s)) s = '_' + s;   // Windows reserved names
  return s.slice(0, 255);                                         // ASCII: 255 chars = 255 bytes
}
```

- **NFC first** so decomposed Unicode variants cannot slip past the character filter.
- **Strip `/`, `\`, NUL** for path-traversal defence.
- **Block Windows reserved names** even on Linux — files may sync to Windows later.
- **255 bytes max**; the ASCII-only step makes a character slice byte-exact. Keep `original_filename` raw for audit.

## Cryptographic Deduplication (`blake3`, tenant-scoped)

```js
const { blake3 } = await import('@noble/hashes/blake3.js');   // ESM-only (inside an async function); `.js` path required
const hash = Buffer.from(blake3(fileBytes)).toString('hex');
```

- **`blake3` is mandated** — a cryptographic hash at a 128-bit security level for a 32-byte output, and faster than SHA-256 on streams (claim `blake3-security-level`).
- **`xxHash3` and other non-cryptographic hashes are BANNED for dedup** — a malicious tenant can engineer a collision and overwrite a legitimate file.
- **Per-tenant only.** Uniqueness is `(tenant_id, blake3_hash)` among live rows. **Cross-tenant dedup is BANNED** — an instant "upload" for Tenant A proves Tenant B already holds that exact file.
- The hash is known only after the bytes are: computed at `/finalize` from the stored object, or from a client-supplied hash that `/finalize` then verifies. When a live `(tenant_id, hash)` row exists (`available` or `scanning`): delete the just-uploaded object, mark the pending row `soft_deleted` with `deleted_at = now()`, `hard_delete_at = now()` and `delete_reason = 'dedup_discard'` (so it leaves the live indexes and the next hard-delete pass erases it, audit row included), and return the existing row's `id`. A quarantined file has already left the live set (§ State machine), so a re-upload of it is scanned afresh and quarantined again. Never a second live row — the live-row hash index refuses it, and `/finalize` catches its unique violation (23505) as the concurrent-duplicate case.

## Metadata Table (`files`)

```sql
CREATE TABLE files (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          UUID NOT NULL,
  uploader_id        UUID NOT NULL,
  storage_key        TEXT NOT NULL UNIQUE,         -- tenant-scoped path in bucket
  bucket             TEXT NOT NULL,                 -- which backend (b2 / r2 default; supabase legacy)
  original_filename  TEXT NOT NULL,                 -- raw (audited)
  sanitized_filename TEXT NOT NULL,
  mime_type          TEXT NOT NULL,                 -- SERVER-SNIFFED at finalize; client claim until then
  size_bytes         BIGINT NOT NULL,
  blake3_hash        TEXT,                          -- NULL until /finalize — unknowable at pending_upload
  status             TEXT NOT NULL,                 -- pending_upload | scanning | available | quarantined | soft_deleted
  idempotency_key    TEXT,
  uploaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at         TIMESTAMPTZ,                   -- pending_upload sweeper
  deleted_at         TIMESTAMPTZ,
  delete_reason      TEXT,                          -- set WITH deleted_at; the sweeper copies it to file_erasure_audit.reason
  hard_delete_at     TIMESTAMPTZ,                   -- KVKK sweeper
  CHECK ((deleted_at IS NULL) = (delete_reason IS NULL)),   -- a soft-delete without a reason is refused at write time
  CHECK (delete_reason IN ('user_request','retention_policy','quarantine','gdpr_request','upload_expired','dedup_discard'))
);
CREATE UNIQUE INDEX files_tenant_hash_live_uq ON files(tenant_id, blake3_hash)
  WHERE blake3_hash IS NOT NULL AND deleted_at IS NULL;   -- a soft-deleted file can be re-uploaded
CREATE UNIQUE INDEX files_tenant_idem_uq ON files(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX files_tenant_idx ON files(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX files_status_expires_idx ON files(status, expires_at) WHERE status = 'pending_upload';
CREATE INDEX files_hard_delete_idx ON files(hard_delete_at) WHERE deleted_at IS NOT NULL;
-- Owned by the migration role; the app and the scan worker get verbs by grant, rows by the tenant policy.
GRANT SELECT, INSERT, UPDATE, DELETE ON files TO app_role;
GRANT SELECT, UPDATE ON files TO scan_worker_role;           -- quarantine is an UPDATE
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE files FORCE ROW LEVEL SECURITY;
CREATE POLICY files_tenant ON files USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id());
-- Cross-tenant sweepers: a dedicated LOGIN NOSUPERUSER NOBYPASSRLS role, reach scoped by policy
CREATE POLICY files_sweep ON files FOR ALL TO files_sweeper
  USING (deleted_at IS NOT NULL OR status IN ('pending_upload', 'quarantined'));
GRANT SELECT, UPDATE, DELETE ON files TO files_sweeper;   -- the policy scopes ROWS; this grants the VERBS
```

- Per `25-data-postgres.md`: `gen_random_uuid()` IDs; partial indexes as above.
- Per `95-multi-tenant-saas.md`: RLS on `current_tenant_id()` (`app.tenant_id` set per transaction) is the PRIMARY filter; an application-level `tenant_id` predicate is defence in depth on top, never the only guard.
- **The retention and pending-upload sweepers span tenants.** Under `FORCE ROW LEVEL SECURITY` the app role with no tenant set sees ZERO rows — a sweeper run as it erases nothing and reports nothing, so the KVKK disposal silently never happens. Run them as a dedicated `LOGIN NOSUPERUSER NOBYPASSRLS` role (`files_sweeper` above) whose reach comes only from the scoped `files_sweep` policy — `95`'s payments-ingest shape; never the app role, never `BYPASSRLS`. `fabrik apply` mints such a role only for payments ingest today, so the project's migration creates this one.

## Async Pipeline — Image Transforms + ClamAV

### Image transforms → an isolated worker

There is **no Fabrik image-sanitising service**: `image-broker` (retired, `agents-fabrik.md` § Fabrik Microservices) was a stock-photo API, never a decoder sandbox. A project that transforms untrusted images runs the decode in a **separate worker process or container** (`75-workers-jobs.md` discipline), never on the API's request path.

- `sharp` in that worker: reject any side above 8,000 px (house rule, checked from `metadata()` before decoding) and set `limitInputPixels` to match (64,000,000 — the library default is 268,402,689), with `failOn: 'warning'` for untrusted input. Output drops all metadata — EXIF, GPS, ICC — unless `keepMetadata()`/`withMetadata()` is called, and never call them on user uploads; orientation goes with it, so apply `autoOrient`/`.rotate()` first (claim `sharp-untrusted-input-defaults`).
- Inline `sharp` in the API process is acceptable ONLY for trivial low-concurrency work on trusted input (admin avatars).

### Antivirus scanning → the `clamd` service, TCP 3310 INSTREAM

**Why on-premise:** TR data sovereignty — tenant files are never sent to a third-party scanner (VirusTotal etc.).

**Why TCP:** a Unix socket needs a shared volume; TCP works across the `fabrik` network. The official `clamav/clamav` image enables `TCPSocket 3310` (stock `clamd.conf` leaves TCP off).

**Deploy it as its own compose service with its own memory limit.** ClamAV's docs size a clamd container at 4 GiB — loading the signature database takes upwards of 1.2 GiB and a reload doubles it unless `ConcurrentDatabaseReload no` (which blocks scans during reload). It never fits inside the API's limit (the scaffold's is 512M). Use the current LTS image line (claim `clamav-clamd-facts`).

```js
const net = require('node:net');
const { Transform } = require('node:stream');
const { pipeline } = require('node:stream/promises');

async function scanWithClamd(stream) {
  const sock = net.createConnection({ host: 'clamd', port: 3310 });
  sock.setTimeout(Number(process.env.CLAMD_SOCKET_TIMEOUT_MS || 30_000),
    () => sock.destroy(new Error('clamd timeout')));  // the breaker's timeout rejects the call, not the scan
  let reply = '';
  sock.on('data', (d) => { reply += d.toString(); });
  const done = new Promise((resolve, reject) => { sock.on('end', resolve); sock.on('error', reject); });
  done.catch(() => {});                              // observed below; unobserved it crashes the worker on ECONNREFUSED
  sock.write('zINSTREAM\0');
  const frame = new Transform({                      // <4-byte big-endian length><bytes> per chunk
    transform(chunk, _enc, cb) {
      const len = Buffer.alloc(4); len.writeUInt32BE(chunk.length, 0);
      cb(null, Buffer.concat([len, chunk]));
    },
    flush(cb) { cb(null, Buffer.alloc(4)); },         // zero-length chunk ends the stream
  });
  try {
    await pipeline(stream, frame, sock);             // honours backpressure; half-closes the socket, clamd still replies
  } catch (e) { sock.destroy(); throw e; }
  await done;
  reply = reply.replace(/\0$/, '');
  if (/ FOUND$/.test(reply)) return { verdict: 'malicious', detail: reply };
  if (/: OK$/.test(reply)) return { verdict: 'clean' };
  throw new Error(`clamd: ${reply}`);                // incl. "INSTREAM size limit exceeded" — never "clean"
}
```

### State machine

```text
pending_upload → /finalize lands            → scanning
scanning       → clamd verdict = clean      → available
               → clamd verdict = malicious  → quarantined + DeleteObjectCommand
               → clamd error / circuit open → stays scanning, retried by the worker
```

The scan runs in a background worker (`75-workers-jobs.md`), never on the request thread. A malicious verdict fires `DeleteObjectCommand` at once and sets `status='quarantined'`, `deleted_at = hard_delete_at = now()`, `delete_reason = 'quarantine'`; the next hard-delete pass (the sweeper role) removes the row and writes its `file_erasure_audit` row (`reason='quarantine'`) — the scan worker holds no grant on the audit table. The scan job carries its `tenant_id`, and the worker sets `SET LOCAL app.tenant_id` per job before touching `files` — under `FORCE ROW LEVEL SECURITY` a worker with no tenant set sees zero rows and silently scans nothing. A breaker fallback (`unscanned`, either reason) leaves the row in `scanning` for the next cycle. The breaker's timeout rejects the call but not the scan — give the socket its own `sock.setTimeout(…, () => sock.destroy(new Error('clamd timeout')))` inside `scanWithClamd`, or it leaks.

**`StreamMaxLength`** (default 100M) is a limit on the WHOLE stream and MUST be ≥ the API's max upload size; a smaller value makes clamd answer `INSTREAM size limit exceeded`, which the scanner treats as an error, not a verdict. `MaxFileSize` (default 100M) and `MaxScanSize` (default 400M) bound what is scanned inside archives.

## Data Lifecycle & KVKK Compliance

KVKK's deletion regulation (Kişisel Verilerin Silinmesi, Yok Edilmesi veya Anonim Hale Getirilmesi Hakkında Yönetmelik, under Law 6698 Art. 7) binds the TR entity (claim `kvkk-deletion-regulation`):

- **Art. 11(2):** the periodic destruction interval is set in the controller's retention policy and "cannot exceed six months".
- **Art. 7(3):** every deletion, destruction and anonymisation operation is recorded, and the records are kept **at least three years**.

The regulation requires the RECORD; it names no hash or tamper-evidence mechanism. The hash chain below is **house policy**, so an altered erasure record is detectable, not a KVKK text requirement.

### Soft-delete → hard-delete pipeline

```text
user deletes file → UPDATE files SET deleted_at=now(), hard_delete_at=now() + interval '30 days', delete_reason='user_request',
                                     status='soft_deleted'
sweeper (≥ monthly) picks rows where now() > hard_delete_at:
  BEGIN
    SELECT … FROM files WHERE id = $1 FOR UPDATE
    await s3.send(new DeleteObjectCommand({ Bucket, Key: storageKey }))   -- idempotent; a failure aborts the TX
    DELETE FROM files WHERE id = $1
    INSERT INTO file_erasure_audit (…, reason = the row's delete_reason) -- chained, below
  COMMIT
```

**Mandates:**

- The sweeper runs at least monthly — well inside Art. 11's six-month ceiling.
- A data-subject (KVKK/GDPR) erasure request soft-deletes with `delete_reason='gdpr_request'`, a retention-policy job with `'retention_policy'`; the audit `reason` is copied from the row, never inferred at sweep time. The retention job reaches LIVE rows, which the sweeper's policy deliberately cannot see: it runs per tenant as `app_role` with `SET LOCAL app.tenant_id`, iterating the tenants table, like the scan worker.
- **Object delete before row delete, inside the transaction.** A failed `DeleteObjectCommand` aborts and the row survives for the next sweep (the delete is idempotent). Never drop the row after a failed object delete — the backend tracks no orphans, and the scaffold's current `DELETE` does exactly that.
- **Hard delete is final** — no recovery window after `hard_delete_at`.
- **Every erasure writes a `file_erasure_audit` row, retained ≥ 3 years** (Art. 7(3)) — user deletes, retention sweeps, pending-upload expiry and quarantine alike.

### `file_erasure_audit` — same chain algorithm as `app-audit-log.md`

```sql
CREATE TABLE file_erasure_audit (
  id                 UUID PRIMARY KEY,               -- uuid7 from the writer
  ts                 TIMESTAMPTZ NOT NULL,            -- set by the writer, clamped past the tip (below) — never DEFAULT now()
  file_id            UUID NOT NULL,                  -- original files.id (no FK — the row is gone)
  tenant_id          UUID NOT NULL,
  storage_key        TEXT NOT NULL,
  original_filename  TEXT NOT NULL,
  sanitized_filename TEXT NOT NULL,
  size_bytes         BIGINT NOT NULL,
  blake3_hash        TEXT,                           -- NULL for a pending_upload that never finalized
  bucket             TEXT NOT NULL,
  reason             TEXT NOT NULL,                  -- 'user_request' | 'retention_policy' | 'quarantine' | 'gdpr_request' | 'upload_expired' | 'dedup_discard'
  erased_by          UUID,                           -- user or service id; NULL = automated sweeper
  prev_hash          TEXT CHECK (prev_hash IS NULL OR length(prev_hash) = 64),
  current_hash       TEXT NOT NULL CHECK (length(current_hash) = 64)
);
CREATE INDEX file_erasure_audit_ts_idx ON file_erasure_audit(ts);
-- Owned by the migration role, NOT the app role (an owner holds UPDATE/DELETE whatever is revoked from others).
-- Writer (the sweeper role): INSERT + SELECT only. The request-serving app role and the scan worker get NO grant:
-- the rows carry every tenant's filenames and keys, and a tenant RLS would break the global chain tip.
GRANT INSERT, SELECT ON file_erasure_audit TO files_sweeper;
```

The chain is fabrik-lib `app-audit-log`'s — `/opt/fabrik-lib/app-audit-log/audit_log.py` (`record_event`, `_canonical_payload`, `_select_tip`, `AUDIT_CHAIN_LOCK_KEY`) is the authority for the algorithm, the lock and the clamp; `app-audit-log.md` for the vocabulary. Applied to this table, never a second algorithm:

- **App-level hashing** (decision A2 in `/opt/fabrik-lib/app-audit-log/schema.sql`): `current_hash = sha256(canonical JSON)`, where the JSON object carries, in THIS fixed order, `id, ts, file_id, tenant_id, storage_key, original_filename, sanitized_filename, size_bytes, blake3_hash, bucket, reason, erased_by, prev_hash` — `prev_hash` the last KEY (not sorted, not concatenated); UUIDs as lowercase strings, `size_bytes` a JSON integer (a Node pg driver hands BIGINT back as a string — convert it); JSONB sub-objects sorted recursively; nulls present; no whitespace; UTF-8 unescaped; `ts` in UTC as `YYYY-MM-DDTHH:MM:SS.ffffff` + `Z` (six-digit microseconds — Node's `toISOString()` gives three). The module's `_canonical_payload` is the reference. A `BEFORE INSERT` trigger is `app-audit-log.md`'s UPGRADE path, not the requirement.
- **One writer at a time, and an ordering key that agrees:** take `pg_advisory_xact_lock(<this table's own constant>)` around select-tip + insert, AND read the tip's `ts` under the lock and set the new row's `ts` explicitly, clamped strictly past it. The lock alone does not prevent a fork: `now()` is the transaction START, so a writer that waited on the lock (or the S3 delete) holds a `ts` older than a row committed meanwhile — the module documents a six-writer reproduction that forked with the lock held. `SELECT … FOR UPDATE` on a sentinel is not an option — it needs UPDATE, which an append-only role lacks.
- **Verification:** adapt `/opt/fabrik-lib/app-audit-log/`'s `verify_chain()` (Python) to this table's columns and run it quarterly and on regulator request. A Node writer reproduces the canonical JSON byte for byte or the verifier reads every row as broken — writing the sweeper as a Python job that vendors the module avoids that seam.

**Why a sibling table, not the central `audit_log`:** retention sweeps write in bursts that would crowd `auth.*`/`billing.*` queries, and `storage_key`/`blake3_hash`/`bucket` are first-class columns here instead of JSONB paths. A user-level summary of a multi-file erasure (a KVKK/GDPR request) may additionally go to the central log as `gdpr.deletion_purged` (`details={purged_rows}`, its documented shape) via `app-audit-log`'s `record_event` — that pack's vocabulary; never an invented action string or field.

## Health Endpoint

Two endpoints, two jobs (`58-resilience.md` § Health Endpoint Contract, `30-ops.md`): a dep-free `/healthz` LIVENESS probe that the Dockerfile `HEALTHCHECK` and the compose healthcheck target, and `/health` (plus `/api/health`, the verifier's path) as READINESS, verifying the critical dependencies — DB and storage. The scaffold points both healthchecks at the dependency-checking endpoint and has no `/healthz`; add it and repoint them. Readiness:

```js
app.get(['/health', '/api/health'], async (req, res) => {
  if (isShuttingDown) return res.status(503).json({ status: 'draining' });
  try {
    await db.query('SELECT 1');
    await s3.send(new HeadBucketCommand({ Bucket: process.env.R2_BUCKET }),
      { abortSignal: AbortSignal.timeout(5_000) });   // readiness answers fast — not 120 s × 3 attempts
    res.json({ status: 'ok' });
  } catch (e) {
    res.status(503).json({ status: 'degraded', error: e.message });
  }
});
```

**clamd is NOT in `/health`.** Its outage has a defined degradation (files stay `scanning`, the worker retries), so failing readiness on it would turn Gatus red and page for a planned degradation. Surface it as the breaker's `open` event and a metric instead.

## Resilience Integration

All S3, clamd and image-worker calls follow `58-resilience.md`:

- **Timeout:** the S3 handler's connect/request timeouts with `throwOnRequestTimeout: true`; the clamd socket's own timeout beside the breaker's. Every timeout and threshold is an env var (`58-resilience.md` §7a).
- **Retry:** SDK standard mode, `maxAttempts: 3` — record breaker failures per logical operation, not per attempt.
- **Circuit breaker:** on clamd and any image worker; the pg pool handles its own degraded mode.
- **Graceful fallback:** clamd circuit open → the row stays `scanning` and the worker retries next cycle; image-worker circuit open → the transform job is retried later, the upload itself is not failed.

---

## Banned Patterns

| Pattern | Use Instead | Reason |
| --- | --- | --- |
| `multer.memoryStorage()` / full buffering | `busboy` + `pipeline()` + `@aws-sdk/lib-storage` `Upload` | Holds the whole file in the heap; OOM under concurrent load |
| `multer` disk storage / `formidable` in production | `busboy` streaming to the backend | Writes local, ephemeral disk |
| Ignoring busboy's `'limit'` / `truncated` | Abort the `Upload` on `'limit'`; map the `AbortError` to 413 | `fileSize` truncates silently — a cut-off file is stored as complete |
| `stream.pipe()` | `pipeline()` from `node:stream/promises` | `.pipe()` doesn't propagate downstream errors (also banned by `12-node.md`) |
| A custom HTTP handler adopted as a mandate | The SDK default; an alternative handler only with your own benchmark | The published gain is one local benchmark |
| "Adaptive" retry on a multi-tenant client | SDK standard mode (`maxAttempts`) | AWS does not recommend adaptive as a default or across tenants |
| Trusting client `Content-Type` / extension | `file-type` magic-byte sniff on the first 4100 bytes | Headers and extensions are trivially spoofed |
| `mmmagic` / native libmagic | `file-type` (pure JS) | Blocks the event loop + native-compile friction |
| Presigned PUT without `signableHeaders` for `content-type` | `signableHeaders: new Set(['content-type'])` + `ContentLength` + a per-backend enforcement probe | The presigner leaves `content-type` unsigned; the URL accepts any type |
| `expiresIn > 900` on a PUT URL | ≤ 900 s (house policy) | A presigned PUT is a bearer write capability until expiry |
| Reusing presigned PUT URLs | DB state machine with `/finalize` | The backend does not enforce single use |
| Cross-tenant dedup | Live-row unique index on `(tenant_id, blake3_hash)` | Confirms another tenant holds a file |
| `xxHash3` / non-cryptographic dedup hash | `blake3` (`@noble/hashes/blake3.js`) | Collision-engineerable overwrite |
| `blake3_hash NOT NULL` at `pending_upload` | Nullable until `/finalize`; partial unique index | The hash does not exist before the bytes do |
| Image decoding in the API process | An isolated worker; 8,000 px side cap, matched `limitInputPixels`, `failOn: 'warning'` | Decoder bugs, decompression bombs, metadata leaks |
| Delegating image sanitising to `image-broker` | The worker above | `image-broker` was a stock-photo API, and it is retired |
| Synchronous clamd scan in the upload request | Async worker via the state machine | Streaming large files to clamd in-request exhausts the API |
| clamd inside the API container or under its memory limit | Its own compose service, 4 GiB-class limit | The signature database alone needs >1.2 GiB, double on reload |
| Treating any clamd reply without `FOUND` as clean | Parse `: OK` / ` FOUND`; anything else is an error | `INSTREAM size limit exceeded` is neither |
| clamd in `/health`, or `HEALTHCHECK` on the dependency-checking endpoint | Breaker events + a metric; `HEALTHCHECK` on the dep-free `/healthz` | A non-critical dependency would page for a planned state; a `HEALTHCHECK` on a dependency-checking endpoint marks every container unhealthy on one DB blip |
| Commercial AV API (VirusTotal etc.) | `clamd` over TCP 3310 | TR data sovereignty |
| Local-disk storage in production | B2 / R2 (Supabase Storage legacy-only) | Containers redeploy and lose volumes |
| Dropping the row after a failed `DeleteObjectCommand` | Object delete first, inside the TX; failure aborts | The backend tracks no orphans |
| A cross-tenant worker or sweeper with no tenant set and no scoped role | Per-job `SET LOCAL app.tenant_id` (scan worker); a `NOBYPASSRLS` role with a scoped policy (sweepers) | Under `FORCE` RLS it sees zero rows and silently does nothing |
| Soft delete with no hard-delete sweeper | A sweeper at least monthly | KVKK Art. 11: the interval cannot exceed six months |
| File erasure without an audit row | A chained `file_erasure_audit` row kept ≥ 3 years | KVKK Art. 7(3) record + the house tamper-evidence policy |
| A second chain algorithm, a chain writer without the advisory lock, or `ts DEFAULT now()` | fabrik-lib `audit_log.py`'s algorithm + `pg_advisory_xact_lock` + `ts` clamped past the tip + an adapted `verify_chain()` | Concurrent writers fork the chain even under the lock when `ts` is the TX start; a new algorithm drifts from the verifier |

---

## Related Rule Packs

- `12-node.md` — Node runtime, `pipeline()`, CJS-vs-ESM, npm hygiene
- `15-api-contracts.md` — request/response shape, idempotency, error format
- `25-data-postgres.md` — `gen_random_uuid()`, indexing, RLS pattern
- `35-security-auth.md` — Pattern A JWT validation (Pattern B legacy), `X-Internal-Token`, secrets policy
- `55-observability.md` — `/health` checks critical dependencies only
- `58-resilience.md` — timeout / retry / circuit-breaker invariants
- `30-ops.md` — compose conventions the `clamd` service follows (its own memory limit, `fabrik` network)
- `75-workers-jobs.md` — the scan worker, the image worker, the retention and pending-upload sweepers
- `95-multi-tenant-saas.md` — tenant scoping, `current_tenant_id()` RLS
- `app-audit-log.md` — the action vocabulary (`gdpr.*`) and the chain's purpose; its algorithm, lock and clamp live in fabrik-lib `app-audit-log/audit_log.py`

---

## Done When

- [ ] The S3 client uses the SDK's standard retry mode (`maxAttempts`) and connect/request timeouts with `throwOnRequestTimeout: true`; any alternative handler or custom backoff carries its own measurement.
- [ ] R2 clients set `region: 'auto'`; B2 clients use the real region; (legacy) Supabase Storage uses the session-token credentials and sends no ACL headers.
- [ ] A backend that rejects the SDK's default checksum headers gets `WHEN_REQUIRED` on that client only.
- [ ] Presigned PUT URLs: signed by a `WHEN_REQUIRED` client, `expiresIn ≤ 900`, `signableHeaders` includes `content-type`, `ContentLength` set — and a per-backend probe proving a wrong length and a wrong body are refused is recorded in `docs/DEPLOYMENT.md`.
- [ ] Single use via the DB state machine: `pending_upload` → `/finalize` (size verified) → `scanning` → `available`/`quarantined`.
- [ ] Direct uploads use `busboy` + `pipeline()` + `@aws-sdk/lib-storage` `Upload` (5 MiB parts, bounded `queueSize`); a `'limit'` event aborts the upload and answers 413; a non-multipart body answers 415, no file part or a second file 400; one guard ensures a single response.
- [ ] Incomplete multipart uploads are aborted after 1 day by a bucket lifecycle rule (R2's built-in default is 7 days; set the rule explicitly, and the B2 equivalent), recorded in `docs/DEPLOYMENT.md`.
- [ ] MIME validated by `file-type` on the first 4100 bytes (loaded with dynamic `import()`); no `mmmagic`/`libmagic`.
- [ ] Office/EPUB/PDF deep inspection delegated to clamd, or the class rejected; no in-process semantic parsing.
- [ ] Filenames: NFC, path-separator/NUL strip, Windows-reserved block, 255-byte cap; `original_filename` kept raw.
- [ ] Dedup by `blake3` (`@noble/hashes/blake3.js`); `blake3_hash` nullable until `/finalize`; live-row unique index on `(tenant_id, blake3_hash)`; no cross-tenant dedup.
- [ ] Untrusted image decoding runs in an isolated worker: any side over 8,000 px rejected before decode, `limitInputPixels` matched, `failOn: 'warning'`, metadata never kept.
- [ ] clamd runs as its own compose service with its own memory limit, over TCP 3310 INSTREAM; the scanner parses `OK`/`FOUND` and treats any other reply as an error; a malicious verdict quarantines and deletes the object.
- [ ] `StreamMaxLength` ≥ the API's max upload size.
- [ ] A breaker satisfying `58-resilience.md`'s invariants wraps clamd and any image worker (`opossum` with `volumeThreshold` set, thresholds from env, a fallback that names open vs error, and a socket timeout that actually ends the scan).
- [ ] `Idempotency-Key` honoured through a `(tenant_id, idempotency_key)` unique index; a duplicate key returns the existing row.
- [ ] Auth validated server-side (Pattern A: HS256 pinned, `exp`+`sub` required); `tenant_id` from the token's `tid` or the M2M context, never the body.
- [ ] `/healthz` is dep-free and both healthchecks target it; `/health` (readiness) checks DB and storage (`HeadBucketCommand`), and NOT clamd.
- [ ] The hard-delete sweeper runs at least monthly; object delete precedes row delete inside one transaction, and a failed object delete aborts it.
- [ ] The scan worker sets `app.tenant_id` per job and holds only `SELECT, UPDATE` on `files`; the app role holds the table grants (tables owned by the migration role).
- [ ] Every soft-delete path sets `delete_reason` with `deleted_at` (user request, GDPR request, retention policy, upload expiry, dedup discard, quarantine), and the sweeper copies it into the audit row.
- [ ] The sweepers run as a dedicated `NOBYPASSRLS` role with `SELECT, UPDATE, DELETE` on `files` and rows scoped by the `files_sweep` policy — never the app role, which sees nothing under `FORCE`; every erasure path (user delete, pending expiry, dedup, quarantine) sets `hard_delete_at` so the sweeper's pass picks it up; the audit table is owned by the migration role.
- [ ] Every erasure writes a `file_erasure_audit` row (kept ≥ 3 years, INSERT+SELECT only for the sweeper role, no grant to the app role) using fabrik-lib `audit_log.py`'s chain algorithm (the fixed column order above) under `pg_advisory_xact_lock` with `ts` clamped past the tip; an adapted `verify_chain()` runs quarterly.
- [ ] `docs/DEPLOYMENT.md` records the bucket, its lifecycle rule, the presign enforcement probe and the clamd service; `docs/RESILIENCE.md` §7 lists the scan worker and both sweepers with their intervals.
- [ ] Storage credentials in env vars only — never hardcoded; no local-disk persistence in production paths.
