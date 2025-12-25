-- Phase 1b DDL: File Storage and Processing Tables
-- Run this in Supabase SQL Editor
-- Last Updated: 2025-12-23

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TENANTS
-- ============================================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants(slug);

-- ============================================================
-- TENANT MEMBERS (links users to tenants)
-- ============================================================

CREATE TABLE IF NOT EXISTS tenant_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_tenant_members_user ON tenant_members(user_id);
CREATE INDEX idx_tenant_members_tenant ON tenant_members(tenant_id);

-- ============================================================
-- FILES (metadata only, bytes in R2)
-- ============================================================

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- File metadata
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    
    -- R2 storage
    r2_key TEXT NOT NULL UNIQUE,
    
    -- Access control
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('public', 'private', 'internal')),
    uploaded_by UUID REFERENCES auth.users(id),
    
    -- Processing status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'error')),
    
    -- Optional metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_files_tenant ON files(tenant_id);
CREATE INDEX idx_files_status ON files(status);
CREATE INDEX idx_files_visibility ON files(visibility);
CREATE INDEX idx_files_r2_key ON files(r2_key);
CREATE INDEX idx_files_uploaded_by ON files(uploaded_by);

-- ============================================================
-- FILE DERIVATIVES (processed outputs from files)
-- ============================================================

CREATE TABLE IF NOT EXISTS file_derivatives (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    
    -- Derivative info
    derivative_type TEXT NOT NULL, -- 'transcript', 'ocr_text', 'extracted_text', 'thumbnail', 'waveform'
    content_type TEXT NOT NULL,
    size_bytes BIGINT,
    
    -- R2 storage
    r2_key TEXT NOT NULL UNIQUE,
    
    -- Metadata (e.g., language, duration, page count)
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_derivatives_file ON file_derivatives(file_id);
CREATE INDEX idx_derivatives_type ON file_derivatives(derivative_type);

-- ============================================================
-- PROCESSING JOBS (queue for async processing)
-- ============================================================

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    
    -- Job type
    job_type TEXT NOT NULL, -- 'transcribe', 'ocr', 'extract_text', 'thumbnail', 'waveform'
    
    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    priority INT DEFAULT 0, -- higher = process sooner
    
    -- Worker tracking
    worker_id TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Results
    result_data JSONB,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jobs_status ON processing_jobs(status);
CREATE INDEX idx_jobs_type ON processing_jobs(job_type);
CREATE INDEX idx_jobs_file ON processing_jobs(file_id);
CREATE INDEX idx_jobs_pending ON processing_jobs(status, priority DESC, created_at ASC) 
    WHERE status = 'pending';

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_derivatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- Tenants: users can only see tenants they're members of
CREATE POLICY "Users can view their tenants" ON tenants
    FOR SELECT USING (
        id IN (SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid())
    );

-- Tenant members: users can see members of their tenants
CREATE POLICY "Users can view tenant members" ON tenant_members
    FOR SELECT USING (
        tenant_id IN (SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid())
    );

-- Files: users can see files in their tenants
CREATE POLICY "Users can view tenant files" ON files
    FOR SELECT USING (
        tenant_id IN (SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid())
        OR visibility = 'public'
    );

-- Files: users can insert files in their tenants
CREATE POLICY "Users can upload to tenant" ON files
    FOR INSERT WITH CHECK (
        tenant_id IN (SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid())
    );

-- File derivatives: follow parent file access
CREATE POLICY "Derivatives follow file access" ON file_derivatives
    FOR SELECT USING (
        file_id IN (
            SELECT id FROM files WHERE 
            tenant_id IN (SELECT tenant_id FROM tenant_members WHERE user_id = auth.uid())
            OR visibility = 'public'
        )
    );

-- Processing jobs: service role only (workers use service key)
CREATE POLICY "Service role access for jobs" ON processing_jobs
    FOR ALL USING (
        auth.role() = 'service_role'
    );

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_files_updated_at
    BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Get user's tenants
CREATE OR REPLACE FUNCTION get_user_tenants(user_uuid UUID)
RETURNS SETOF tenants AS $$
BEGIN
    RETURN QUERY
    SELECT t.* FROM tenants t
    JOIN tenant_members tm ON t.id = tm.tenant_id
    WHERE tm.user_id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Claim next pending job (atomic)
CREATE OR REPLACE FUNCTION claim_next_job(
    p_job_types TEXT[],
    p_worker_id TEXT
)
RETURNS processing_jobs AS $$
DECLARE
    v_job processing_jobs;
BEGIN
    -- Find and lock next pending job
    SELECT * INTO v_job
    FROM processing_jobs
    WHERE status = 'pending'
      AND job_type = ANY(p_job_types)
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF v_job.id IS NOT NULL THEN
        -- Claim it
        UPDATE processing_jobs
        SET status = 'processing',
            worker_id = p_worker_id,
            started_at = NOW()
        WHERE id = v_job.id
        RETURNING * INTO v_job;
    END IF;
    
    RETURN v_job;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SAMPLE DATA (optional, for testing)
-- ============================================================

-- Create a test tenant
-- INSERT INTO tenants (name, slug) VALUES ('Test Tenant', 'test');

-- ============================================================
-- VERIFICATION
-- ============================================================

-- Run these to verify tables were created:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- SELECT * FROM pg_policies;
