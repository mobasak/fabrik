-- External Services & Credentials Registry — Phase B schema.
-- Local Postgres (fabrik_services). Applied as a ONE-OFF process via psql, never from app startup
-- (12-Factor XII). Idempotent (IF NOT EXISTS) so re-applying is safe.
-- The DB stores value_sha256 (identity), NEVER the raw secret — the secret lives only in
-- secrets/all-envs.env (chmod 600, gitignored).

CREATE TABLE IF NOT EXISTS services (
    id             SERIAL PRIMARY KEY,
    provider       TEXT UNIQUE NOT NULL,
    canonical_name TEXT,
    category       TEXT,
    cost_tier      TEXT,
    url            TEXT,
    status         TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
    id               SERIAL PRIMARY KEY,
    service_id       INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    value_sha256     TEXT NOT NULL,
    aliases          TEXT[] NOT NULL DEFAULT '{}',
    used_by_projects TEXT[] NOT NULL DEFAULT '{}',
    account_email    TEXT,
    kind             TEXT NOT NULL DEFAULT 'credential',  -- 'credential' | 'config' (a vendor-prefixed knob: URL/host/port/model/id) | 'code-host' (a call-site URL) | 'credential-unattributed' (reached the block through a model-merged prefix — never a fetcher input, never counted as a key)
    first_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (service_id, value_sha256)
);

CREATE TABLE IF NOT EXISTS credit_snapshots (
    id         SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    balance    NUMERIC,
    unit       TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id            SERIAL PRIMARY KEY,
    service_id    INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    plan          TEXT,
    price         NUMERIC,
    currency      TEXT,
    billing_cycle TEXT,
    renews_on     DATE,
    account_email TEXT,
    UNIQUE (service_id, plan)
);

CREATE INDEX IF NOT EXISTS idx_services_provider ON services (provider);
CREATE INDEX IF NOT EXISTS idx_api_keys_service ON api_keys (service_id);
CREATE INDEX IF NOT EXISTS idx_credit_snapshots_service_time ON credit_snapshots (service_id, fetched_at);
