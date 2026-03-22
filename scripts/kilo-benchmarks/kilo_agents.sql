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
CREATE TABLE IF NOT EXISTS agent_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,                      -- coding / reviewing / fixing / documentation / testing
    agent_id TEXT NOT NULL,                  -- FK to agents.id
    priority INTEGER DEFAULT 1,              -- 1=primary, 2=fallback, 3=emergency
    reason TEXT,                             -- AI explanation for this assignment
    min_elo INTEGER,                         -- recommended minimum elo for this role
    assigned_by TEXT,                        -- model that made the assignment
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE(role, priority)                   -- only one agent per role+priority
);

CREATE INDEX IF NOT EXISTS idx_roles_role ON agent_roles(role);
CREATE INDEX IF NOT EXISTS idx_roles_agent ON agent_roles(agent_id);

-- View: Current role assignments with agent details
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
    r.reason,
    r.assigned_by,
    r.assigned_at
FROM agent_roles r
JOIN agents a ON a.id = r.agent_id
WHERE a.status = 'active'
ORDER BY r.role, r.priority;
