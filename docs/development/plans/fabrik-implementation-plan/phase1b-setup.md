# Phase 1b Setup Guide

**Last Updated:** 2025-12-23

This guide walks you through setting up Supabase and Cloudflare R2 for Phase 1b.

---

## 1. Supabase Project Setup

### Step 1: Create Project

1. Go to [supabase.com](https://supabase.com)
2. Sign in with GitHub
3. Click "New Project"
4. Fill in:
   - **Name:** `fabrik-prod` (or your choice)
   - **Database Password:** Generate a strong one, save to `/opt/fabrik/.env`
   - **Region:** Choose closest to VPS (e.g., `us-west-1` for LA VPS)
5. Click "Create new project"

### Step 2: Get API Keys

1. In Supabase dashboard, go to **Settings → API**
2. Copy these values:

```bash
# Add to /opt/fabrik/.env
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_DB_PASSWORD=your-database-password
```

### Step 3: Database Connection String

For direct Postgres access (from VPS workers):

1. Go to **Settings → Database**
2. Copy the connection string:

```bash
# Add to /opt/fabrik/.env
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.xxxxxxxxxxxxx.supabase.co:5432/postgres
```

---

## 2. Cloudflare R2 Setup

### Step 1: Enable R2

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Select your account
3. Click **R2** in sidebar
4. If first time, click "Purchase R2" (free tier: 10GB storage, 1M requests/month)

### Step 2: Create Bucket

1. Click **Create bucket**
2. Name: `fabrik-files` (or your choice)
3. Location hint: `wnam` (Western North America) for LA VPS
4. Click **Create bucket**

### Step 3: Create API Token

1. Go to **R2 → Overview → Manage R2 API Tokens**
2. Click **Create API token**
3. Settings:
   - **Name:** `fabrik-r2-token`
   - **Permissions:** Object Read & Write
   - **Specify bucket(s):** Select your bucket
4. Click **Create API Token**
5. Copy the values:

```bash
# Add to /opt/fabrik/.env
R2_ACCOUNT_ID=abc123def456...
R2_ACCESS_KEY_ID=xxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxx
R2_BUCKET=fabrik-files
```

### Step 4: (Optional) Public Access

For public files (no presigned URL needed):

1. Go to your bucket → **Settings**
2. Under **Public access**, click **Allow Access**
3. Add a custom domain or use the R2.dev subdomain
4. Add to .env:

```bash
R2_PUBLIC_URL=https://files.yourdomain.com
```

---

## 3. Verify Setup

Run this to verify both services are configured:

```bash
cd /opt/fabrik
source .venv/bin/activate
PYTHONPATH=src python3 -c "
from fabrik.drivers.supabase import SupabaseClient
from fabrik.drivers.r2 import R2Client

print('Checking Supabase...')
try:
    sb = SupabaseClient()
    print(f'  ✅ Connected: {sb.url}')
    sb.close()
except Exception as e:
    print(f'  ❌ Error: {e}')

print()
print('Checking R2...')
try:
    r2 = R2Client()
    print(f'  ✅ Endpoint: {r2.endpoint}')
    print(f'  ✅ Bucket: {r2.bucket}')
    r2.close()
except Exception as e:
    print(f'  ❌ Error: {e}')
"
```

---

## 4. Update Fabrik .env

After setup, your `/opt/fabrik/.env` should include:

```bash
# === Supabase (Phase 1b) ===
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_DB_URL=postgresql://postgres:xxx@db.xxxxxxxxxxxxx.supabase.co:5432/postgres

# === Cloudflare R2 (Phase 1b) ===
R2_ACCOUNT_ID=abc123
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET=fabrik-files
R2_PUBLIC_URL=https://files.yourdomain.com
```

**Remember:** Also add these to `/opt/fabrik/.env` per the windsurfrules credential management policy.

---

## 5. Next Steps

After verifying setup:

1. Apply DDL (database tables) - see below
2. Test file upload flow
3. Deploy first file-processing service

---

## Quick Reference

| Service | Dashboard | Docs |
|---------|-----------|------|
| Supabase | [supabase.com/dashboard](https://supabase.com/dashboard) | [supabase.com/docs](https://supabase.com/docs) |
| Cloudflare R2 | [dash.cloudflare.com](https://dash.cloudflare.com) | [developers.cloudflare.com/r2](https://developers.cloudflare.com/r2) |

| Free Tier | Supabase | R2 |
|-----------|----------|-----|
| Storage | 500MB database | 10GB |
| Requests | Unlimited | 1M Class A, 10M Class B |
| Bandwidth | 2GB | Free egress |
