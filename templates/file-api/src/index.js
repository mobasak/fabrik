/**
 * File API - Presigned URL service for R2
 *
 * Endpoints:
 *   POST /api/files/upload-url - Get presigned upload URL
 *   POST /api/files/download-url - Get presigned download URL
 *   GET  /api/files - List files for tenant
 *   GET  /api/files/:id - Get file metadata
 *   DELETE /api/files/:id - Delete file
 *   GET  /health - Health check
 */

const path = require('path');
const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand, HeadBucketCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');
const { UndiciHttpHandler } = require('@smithy/undici-http-handler');
const { ConfiguredRetryStrategy } = require('@aws-sdk/util-retry');
const { v4: uuidv4 } = require('uuid');
const logger = require('./logger');

const app = express();
app.use(cors());
app.use(express.json());

// Config
const PORT = process.env.PORT || 3000;
const MAX_FILE_SIZE = parseInt(process.env.MAX_FILE_SIZE_MB || '100') * 1024 * 1024;
const ALLOWED_TYPES = (process.env.ALLOWED_CONTENT_TYPES || 'application/pdf,audio/mpeg').split(',');
// 67-file-api mandate: presigned PUT URLs are bearer tokens (NIST SP 800-63B
// observation contracts) — cap at 900s (15 min) regardless of env override.
const UPLOAD_EXPIRY = Math.min(parseInt(process.env.UPLOAD_URL_EXPIRY_SECONDS || '900'), 900);
const DOWNLOAD_EXPIRY = parseInt(process.env.DOWNLOAD_URL_EXPIRY_SECONDS || '3600');

// Supabase client
// B32: only create the client when env vars are present. The shipped
// template previously called ``createClient(undefined, undefined)`` at
// module load, which throws ``Error: supabaseUrl is required`` and
// prevents the process from ever binding port 3000 — Traefik then 404s
// every request, including the healthcheck. Surfaced by proof-run on
// 2026-04-28. When Supabase isn't configured, ``supabase`` stays null and
// the auth-protected routes return a clear 503 at request time (see
// ``authMiddleware``). The healthcheck doesn't touch Supabase.
const supabase = (process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY)
  ? createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY)
  : null;

// R2 client.
// 67-file-api mandate: undici handler (35-45% lower latency under parallel
// load) + adaptive ConfiguredRetryStrategy (token-bucket backoff with jitter,
// prevents thundering herds on transient backend outages). R2 ignores explicit
// regions (region: 'auto'); set forcePathStyle=true via env for Backblaze B2.
const r2 = new S3Client({
  region: process.env.R2_REGION || 'auto',
  endpoint: process.env.R2_ENDPOINT,
  forcePathStyle: process.env.R2_FORCE_PATH_STYLE === 'true',
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
  },
  requestHandler: new UndiciHttpHandler({
    connectionTimeout: 5000,
    requestTimeout: 60000,
  }),
  retryStrategy: new ConfiguredRetryStrategy(
    3,
    (attempt) => 100 + Math.random() * 2 ** attempt * 100,
  ),
});

const R2_BUCKET = process.env.R2_BUCKET;

// Middleware: Extract user from Supabase JWT
async function authMiddleware(req, res, next) {
  // B32: 503 (instead of crashing) when Supabase isn't configured.
  if (!supabase) {
    return res.status(503).json({
      error: 'Supabase not configured',
      detail: 'Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to enable auth-protected routes',
    });
  }
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing authorization header' });
  }

  const token = authHeader.substring(7);
  const { data: { user }, error } = await supabase.auth.getUser(token);

  if (error || !user) {
    return res.status(401).json({ error: 'Invalid token' });
  }

  req.user = user;

  // Get user's tenant (first one for now)
  const { data: membership } = await supabase
    .from('tenant_members')
    .select('tenant_id, role')
    .eq('user_id', user.id)
    .limit(1)
    .single();

  if (!membership) {
    return res.status(403).json({ error: 'User has no tenant access' });
  }

  req.tenantId = membership.tenant_id;
  req.userRole = membership.role;

  next();
}

// Health check
// B33: serve at both ``/health`` (template's original path) and
// ``/api/health`` (the path emitted by ``spec_generator`` for file-api).
// Without ``/api/health`` the orchestrator's verifier hits 404 and the
// deploy is rolled back even when the container is up.
async function healthHandler(req, res) {
  const checks = {
    supabase_configured: Boolean(process.env.SUPABASE_URL),
    r2_configured: Boolean(R2_BUCKET),
  };
  let healthy = true;
  // Real-dep check (67-file-api + 55-observability): verify storage backend
  // reachability, not just process liveness. Skipped when R2 isn't configured
  // (local dev) so the probe still passes before credentials are wired.
  if (R2_BUCKET) {
    try {
      await r2.send(new HeadBucketCommand({ Bucket: R2_BUCKET }));
      checks.storage = 'ok';
    } catch (err) {
      checks.storage = `error: ${err.message}`;
      healthy = false;
    }
  } else {
    checks.storage = 'not_configured';
  }
  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'healthy' : 'degraded',
    timestamp: new Date().toISOString(),
    ...checks,
  });
}
app.get('/health', healthHandler);
app.get('/api/health', healthHandler);

// Get presigned upload URL
app.post('/api/files/upload-url', authMiddleware, async (req, res) => {
  try {
    const { filename, contentType, size } = req.body;

    // Validate
    if (!filename || !contentType || !size) {
      return res.status(400).json({ error: 'filename, contentType, and size are required' });
    }

    if (!ALLOWED_TYPES.includes(contentType)) {
      return res.status(400).json({ error: `Content type not allowed. Allowed: ${ALLOWED_TYPES.join(', ')}` });
    }

    if (size > MAX_FILE_SIZE) {
      return res.status(400).json({ error: `File too large. Max: ${MAX_FILE_SIZE / 1024 / 1024}MB` });
    }

    // Generate unique key with sanitized filename (prevent path traversal)
    const safeFilename = filename.replace(/[^a-z0-9.]/gi, '_').toLowerCase();
    const ext = path.extname(safeFilename);
    const fileId = uuidv4();
    const r2Key = `uploads/${req.tenantId}/${fileId}${ext}`;

    // Create file record in Supabase (pending status)
    const { data: fileRecord, error: dbError } = await supabase
      .from('files')
      .insert({
        id: fileId,
        tenant_id: req.tenantId,
        filename: filename,
        content_type: contentType,
        size_bytes: size,
        r2_key: r2Key,
        visibility: 'private',
        uploaded_by: req.user.id,
        status: 'pending',
      })
      .select()
      .single();

    if (dbError) {
      logger.error({ event: 'db_error', error: dbError.message });
      return res.status(500).json({ error: 'Failed to create file record' });
    }

    // Generate presigned URL
    const command = new PutObjectCommand({
      Bucket: R2_BUCKET,
      Key: r2Key,
      ContentType: contentType,
      ContentLength: size,
    });

    const uploadUrl = await getSignedUrl(r2, command, { expiresIn: UPLOAD_EXPIRY });

    res.json({
      fileId: fileRecord.id,
      uploadUrl,
      r2Key,
      expiresIn: UPLOAD_EXPIRY,
    });
  } catch (err) {
    logger.error({ event: 'upload_url_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Confirm upload complete
app.post('/api/files/:id/confirm', authMiddleware, async (req, res) => {
  try {
    const { id } = req.params;

    // Update status to ready
    const { data, error } = await supabase
      .from('files')
      .update({ status: 'ready' })
      .eq('id', id)
      .eq('tenant_id', req.tenantId)
      .select()
      .single();

    if (error || !data) {
      return res.status(404).json({ error: 'File not found' });
    }

    // Optionally create processing job
    const { createJob } = req.body;
    if (createJob) {
      await supabase.from('processing_jobs').insert({
        file_id: id,
        job_type: createJob,
        status: 'pending',
        priority: 0,
      });
    }

    res.json(data);
  } catch (err) {
    logger.error({ event: 'confirm_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get presigned download URL
app.post('/api/files/download-url', authMiddleware, async (req, res) => {
  try {
    const { fileId } = req.body;

    if (!fileId) {
      return res.status(400).json({ error: 'fileId is required' });
    }

    // Get file record
    const { data: file, error } = await supabase
      .from('files')
      .select('*')
      .eq('id', fileId)
      .eq('tenant_id', req.tenantId)
      .single();

    if (error || !file) {
      return res.status(404).json({ error: 'File not found' });
    }

    // Generate presigned URL
    const command = new GetObjectCommand({
      Bucket: R2_BUCKET,
      Key: file.r2_key,
    });

    const downloadUrl = await getSignedUrl(r2, command, { expiresIn: DOWNLOAD_EXPIRY });

    res.json({
      fileId: file.id,
      filename: file.filename,
      contentType: file.content_type,
      downloadUrl,
      expiresIn: DOWNLOAD_EXPIRY,
    });
  } catch (err) {
    logger.error({ event: 'download_url_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// List files
app.get('/api/files', authMiddleware, async (req, res) => {
  try {
    const { status, limit = 50, offset = 0 } = req.query;

    let query = supabase
      .from('files')
      .select('*', { count: 'exact' })
      .eq('tenant_id', req.tenantId)
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (status) {
      query = query.eq('status', status);
    }

    const { data, error, count } = await query;

    if (error) {
      return res.status(500).json({ error: 'Database error' });
    }

    res.json({ files: data, total: count });
  } catch (err) {
    logger.error({ event: 'list_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get file by ID
app.get('/api/files/:id', authMiddleware, async (req, res) => {
  try {
    const { id } = req.params;

    const { data, error } = await supabase
      .from('files')
      .select('*, file_derivatives(*), processing_jobs(*)')
      .eq('id', id)
      .eq('tenant_id', req.tenantId)
      .single();

    if (error || !data) {
      return res.status(404).json({ error: 'File not found' });
    }

    res.json(data);
  } catch (err) {
    logger.error({ event: 'get_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Delete file
app.delete('/api/files/:id', authMiddleware, async (req, res) => {
  try {
    const { id } = req.params;

    // Get file first
    const { data: file, error: fetchError } = await supabase
      .from('files')
      .select('r2_key')
      .eq('id', id)
      .eq('tenant_id', req.tenantId)
      .single();

    if (fetchError || !file) {
      return res.status(404).json({ error: 'File not found' });
    }

    // Delete from R2
    try {
      const command = new DeleteObjectCommand({
        Bucket: R2_BUCKET,
        Key: file.r2_key,
      });
      await r2.send(command);
    } catch (r2Error) {
      logger.error({ event: 'r2_delete_error', error: r2Error.message });
      // Continue anyway - DB record deletion is more important
    }

    // Delete from Supabase (cascades to derivatives and jobs)
    const { error: deleteError } = await supabase
      .from('files')
      .delete()
      .eq('id', id);

    if (deleteError) {
      return res.status(500).json({ error: 'Failed to delete file record' });
    }

    res.json({ success: true, deleted: id });
  } catch (err) {
    logger.error({ event: 'delete_error', error: err.message });
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Start server
app.listen(PORT, () => {
  logger.info({ event: 'service_starting', port: PORT });
});
