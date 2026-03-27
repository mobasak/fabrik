-- Kilo Agents Database Schema
-- Tracks agent rankings with daily historical snapshots
--
-- COLUMN DOCUMENTATION:
-- =====================
--
-- perf_per_dollar ($/Perf):
--   Formula: arena_elo / blended_cost
--   Where blended_cost = (input_cost + output_cost * 3) / 4
--   Meaning: Higher = better value for money
--   Use Case: Find cost-effective models. A $0.10 model with Elo 1400 beats
--             a $15 model with Elo 1500 on this metric.
--
-- is_agentic (agnt):
--   Source: Kilo CLI capabilities.reasoning
--   Values: 1 = can reason step-by-step, 0 = cannot
--   Meaning: Model has reasoning/thinking capabilities
--   Use Case: Critical for complex coding, architecture, debugging tasks.
--             Agentic models can plan multi-step solutions.
--
-- KILO CLI THINKING MODES:
-- ========================
-- Thinking variants are NOT in the model name. Use --variant flag:
--   kilo run -m kilo/google/gemini-2.5-pro --variant max "prompt"
--   kilo run -m kilo/anthropic/claude-sonnet-4.5 --variant high "prompt"
--
-- Available variants: minimal, low, medium, high, max
-- Some models have :thinking suffix for dedicated thinking variants:
--   kilo/anthropic/claude-3.7-sonnet:thinking
--   kilo/qwen/qwen3-max-thinking

-- Current active agents (always reflects latest data)
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,                    -- e.g., "anthropic/claude-opus-4.6"
    api_id TEXT NOT NULL,                   -- exact string for API calls
    name TEXT NOT NULL,                     -- human-readable name
    provider TEXT NOT NULL,                 -- openai / anthropic / google / etc.
    
    -- Pricing (per 1M tokens)
    input_cost_per_m REAL NOT NULL DEFAULT 0,
    output_cost_per_m REAL NOT NULL DEFAULT 0,
    
    -- Capabilities
    context_window_k INTEGER DEFAULT 128,   -- 128 / 200 / 1000
    has_vision BOOLEAN DEFAULT FALSE,       -- multimodal routing
    has_tools BOOLEAN DEFAULT FALSE,        -- agentic routing
    is_agentic BOOLEAN DEFAULT FALSE,       -- multi-step loops (reasoning)
    
    -- Benchmark scores
    arena_elo INTEGER,                      -- from openlm.ai/chatbot-arena
    tbench_accuracy REAL,                   -- from tbench.ai (0-100)
    
    -- Computed/derived
    task_tier INTEGER DEFAULT 2,            -- 1=cheap, 2=balanced, 3=heavy
    perf_per_dollar REAL,                   -- arena_elo / blended_cost
    
    -- Status
    status TEXT DEFAULT 'active',           -- active / discarded / deprecated
    discard_reason TEXT,                    -- why discarded (if applicable)
    blocked INTEGER DEFAULT 0,              -- 1 = excluded from selection (slow/bad)
    block_reason TEXT,                      -- why blocked (e.g., "Too slow (109s)")
    
    -- Metadata
    fallback_model_id TEXT,                 -- FK to cheaper fallback
    last_verified DATE,                     -- pricing goes stale fast
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (fallback_model_id) REFERENCES agents(id)
);

-- Historical snapshots (one row per agent per day)
CREATE TABLE IF NOT EXISTS agent_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    
    -- Ranking at this point in time
    rank INTEGER,
    arena_elo INTEGER,
    tbench_accuracy REAL,
    
    -- Pricing at this point in time
    input_cost_per_m REAL,
    output_cost_per_m REAL,
    
    -- Computed metrics
    perf_per_dollar REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE(agent_id, snapshot_date)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agents_provider ON agents(provider);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_task_tier ON agents(task_tier);
CREATE INDEX IF NOT EXISTS idx_agents_arena_elo ON agents(arena_elo DESC);
CREATE INDEX IF NOT EXISTS idx_history_date ON agent_history(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_history_agent ON agent_history(agent_id);

-- View: Current rankings sorted by Elo
CREATE VIEW IF NOT EXISTS v_current_rankings AS
SELECT 
    ROW_NUMBER() OVER (ORDER BY arena_elo DESC NULLS LAST) as rank,
    id,
    name,
    provider,
    arena_elo,
    tbench_accuracy,
    input_cost_per_m,
    output_cost_per_m,
    context_window_k,
    has_vision,
    has_tools,
    is_agentic,
    task_tier,
    perf_per_dollar,
    status,
    discard_reason
FROM agents
WHERE status = 'active'
ORDER BY arena_elo DESC NULLS LAST;

-- View: All agents ranked (including discarded)
CREATE VIEW IF NOT EXISTS v_all_rankings AS
SELECT 
    ROW_NUMBER() OVER (ORDER BY arena_elo DESC NULLS LAST) as rank,
    id,
    name,
    provider,
    arena_elo,
    tbench_accuracy,
    input_cost_per_m,
    output_cost_per_m,
    status,
    discard_reason
FROM agents
ORDER BY arena_elo DESC NULLS LAST;

-- Agent role assignments (AI-generated)
-- Priority 1-5: best to cheapest adequate
-- Complexity routing happens at runtime via agent_selector.py
CREATE TABLE IF NOT EXISTS agent_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,                      -- coding / reviewing / fixing / documentation / testing
    agent_id TEXT NOT NULL,                  -- FK to agents.id
    priority INTEGER NOT NULL,               -- 1=best, 2=high, 3=balanced, 4=cost-efficient, 5=cheapest
    reason TEXT,                             -- AI explanation for this assignment
    min_elo INTEGER,                         -- recommended minimum elo for this role
    assigned_by TEXT,                        -- model that made the assignment
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE(role, priority)                   -- exactly one agent per role+priority
);

CREATE INDEX IF NOT EXISTS idx_roles_role ON agent_roles(role);
CREATE INDEX IF NOT EXISTS idx_roles_agent ON agent_roles(agent_id);

-- View: Current role assignments with agent details (excludes blocked)
CREATE VIEW IF NOT EXISTS v_role_assignments AS
SELECT
    r.role,
    r.priority,
    a.id as agent_id,
    a.name,
    a.provider,
    a.arena_elo,
    a.tbench_accuracy,
    a.input_cost_per_m,
    a.output_cost_per_m,
    a.context_window_k,
    a.has_vision,
    a.has_tools,
    a.is_agentic,
    a.perf_per_dollar,
    a.blocked,
    a.block_reason,
    r.reason,
    r.assigned_by,
    r.assigned_at
FROM agent_roles r
JOIN agents a ON a.id = r.agent_id
WHERE a.status = 'active' AND a.blocked = 0
ORDER BY r.role, r.priority;

-- Agent role history (archived assignments)
CREATE TABLE IF NOT EXISTS agent_roles_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    priority INTEGER NOT NULL,
    reason TEXT,
    min_elo INTEGER,
    assigned_by TEXT,
    assigned_at TIMESTAMP NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_roles_history_role ON agent_roles_history(role);
CREATE INDEX IF NOT EXISTS idx_roles_history_date ON agent_roles_history(archived_at);

-- =============================================================================
-- LOCAL LLM MODELS (Ollama)
-- =============================================================================
-- Tracks locally-installed models for offline/free AI inference.
-- Synced from Ollama API at localhost:11434
--
-- HARDWARE DISTRIBUTION STRATEGY:
-- Heavy models (32B+): CPU + 64GB RAM
-- Fast models (<16B): GPU + 12GB VRAM

CREATE TABLE IF NOT EXISTS local_models (
    id TEXT PRIMARY KEY,                     -- e.g., "qwen2.5-coder:32b"
    name TEXT NOT NULL,                      -- human-readable name
    family TEXT,                             -- model family (qwen2.5, llama3.1, deepseek, etc.)

    -- Size and quantization
    parameter_size TEXT,                     -- e.g., "32B", "70B", "8B"
    quantization TEXT,                       -- e.g., "Q4_K_M", "Q8_0", "F16"
    size_bytes INTEGER,                      -- disk size in bytes

    -- Hardware assignment
    hardware TEXT DEFAULT 'auto',            -- 'gpu', 'cpu', 'auto'
    vram_required_gb REAL,                   -- estimated VRAM needed
    ram_required_gb REAL,                    -- estimated RAM needed

    -- Role assignment (maps to Fabrik agent roles)
    assigned_role TEXT,                      -- coding / reviewing / fixing / documentation
    role_priority INTEGER DEFAULT 1,         -- 1=primary, 2=fallback

    -- Capabilities (matching Kilo CLI agent tracking)
    context_window_k INTEGER DEFAULT 32,     -- context limit in thousands
    has_vision INTEGER DEFAULT 0,            -- 1 if supports image input
    has_tools INTEGER DEFAULT 0,             -- 1 if supports function/tool calling
    is_agentic INTEGER DEFAULT 0,            -- 1 if suitable for agentic workflows
    is_reasoning INTEGER DEFAULT 0,          -- 1 if has chain-of-thought reasoning

    -- Benchmarks (from public leaderboards or manual testing)
    arena_elo INTEGER,                       -- Chatbot Arena ELO score
    tbench_accuracy REAL,                    -- T-Bench accuracy (0-100)

    -- Performance (local benchmarks)
    tokens_per_sec REAL,                     -- measured on this hardware
    time_to_first_token_ms REAL,             -- latency measurement

    -- Status
    status TEXT DEFAULT 'available',         -- available / downloading / missing
    last_used TIMESTAMP,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    digest TEXT,                             -- Ollama model digest for version tracking
    modified_at TIMESTAMP,                   -- from Ollama API
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_local_models_role ON local_models(assigned_role);
CREATE INDEX IF NOT EXISTS idx_local_models_hardware ON local_models(hardware);
CREATE INDEX IF NOT EXISTS idx_local_models_status ON local_models(status);

-- View: Local models by role assignment
CREATE VIEW IF NOT EXISTS v_local_role_assignments AS
SELECT
    assigned_role as role,
    role_priority as priority,
    id as model_id,
    name,
    family,
    parameter_size,
    quantization,
    hardware,
    context_window_k,
    has_vision,
    has_tools,
    is_agentic,
    is_reasoning,
    arena_elo,
    tokens_per_sec,
    status
FROM local_models
WHERE status = 'available' AND assigned_role IS NOT NULL
ORDER BY assigned_role, role_priority;

-- View: Hardware utilization summary
CREATE VIEW IF NOT EXISTS v_local_hardware_summary AS
SELECT
    hardware,
    COUNT(*) as model_count,
    SUM(CASE WHEN hardware = 'gpu' THEN vram_required_gb ELSE 0 END) as total_vram_gb,
    SUM(CASE WHEN hardware = 'cpu' THEN ram_required_gb ELSE 0 END) as total_ram_gb,
    GROUP_CONCAT(id, ', ') as models
FROM local_models
WHERE status = 'available'
GROUP BY hardware;
