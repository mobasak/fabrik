# Local LLM Infrastructure (Ollama)

**Last Updated:** 2026-03-28

Local AI inference via Ollama on the development machine. Provides zero-cost, offline-capable AI for development workflows without API rate limits or outages.

---

## Table of Contents

1. [Hardware Specs](#hardware-specs)
2. [AI Engineering Team Capabilities](#ai-engineering-team-capabilities)
3. [Ollama Setup](#ollama-setup)
4. [Model Distribution Strategy](#model-distribution-strategy)
5. [The Intelligence vs Speed Tradeoff](#the-intelligence-vs-speed-tradeoff)
6. [Role-to-Model Mapping](#role-to-model-mapping)
7. [Integration with Windsurf / Kilo CLI](#integration-with-windsurf--kilo-cli)
8. [Usage Patterns](#usage-patterns)
9. [Performance Expectations](#performance-expectations)
10. [Benefits for Fabrik Workflow](#benefits-for-fabrik-workflow)
11. [Fallback Strategy](#fallback-strategy)
12. [Database Schema for Local Models](#database-schema-for-local-models)
13. [Agent Interaction Methods](#agent-interaction-methods)
14. [Fabrik Agent Setup and Validation](#fabrik-agent-setup-and-validation)
15. [Global Kilo Configuration](#global-kilo-configuration)
16. [See Also](#see-also)

---

## Hardware Specs

| Component | Specification | AI Role |
|-----------|--------------|---------|
| **CPU** | AMD Ryzen AI 9 | Heavy models (32B, 70B) via RAM |
| **RAM** | 64GB DDR5 | Large model context + Docker containers |
| **GPU** | NVIDIA RTX 5070 (8GB VRAM) | Fast models (≤8GB) |
| **Platform** | WSL2 (Ubuntu 24.04) | Development environment |

---

## AI Engineering Team Capabilities

Based on technical specifications and behavior within the Ollama environment, here is the capabilities matrix for the local AI models:

### Model Capabilities Matrix

| Model Name | `context_window_k` | `has_vision` | `has_tools` | `is_agentic` | `has_reasoning` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **qwen2.5-coder:32b** | 128 | False | True | True | True |
| **llama3.1:70b** | 128 | False | True | True | True |
| **deepseek-coder-v2:16b** | 128 | False | True | True | True |
| **llama3.1:8b** | 128 | False | True | False (Limited) | True (Basic) |

### Detailed Capabilities Breakdown

- **`context_window_k` (128K):** All models technically support 128K tokens, but 64GB RAM creates practical limits. The 70B model uses low-context (32K) to avoid ~20GB KV cache consumption.
- **`has_vision` (False):** These are text-only versions optimized for coding. For vision tasks, use `llama3.2-vision`.
- **`has_tools` (True):** All support Function Calling via Ollama for Kilo CLI and Traycer orchestration.
- **`is_agentic` (Multi-step reasoning):** 32B and 70B models are highly agentic with self-correction. 8B model is best for one-shot tasks.
- **`has_reasoning` (Chain-of-thought):** All use sophisticated attention mechanisms. 70B has highest reasoning density (Senior Architect), 16B DeepSeek specializes in surgical logical reasoning.

### Hardware Alignment Strategy

With RTX 5070 (8GB) + 64GB RAM:
1. **High-Speed Logic:** `llama3.1:8b` and `deepseek-coder-v2:16b` use GPU for instant responses
2. **Deep Reasoning:** `qwen2.5-coder:32b` and `llama3.1:70b` use Ryzen AI 9 + system RAM

---

## Ollama Setup

**Installation:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Endpoint:** `http://localhost:11434` (accessible from WSL and Windows)

**Service status:**
```bash
systemctl --user status ollama  # or: ollama serve
```

---

## Model Distribution Strategy

Distribute load between GPU (fast) and CPU/RAM (heavy) to maximize throughput.

### Hardware Tiers

| Tier | Memory Range | Description | Speed |
|------|--------------|-------------|-------|
| `gpu` | ≤8GB | Fits entirely in VRAM | Instant (~80-100 tok/s) |
| `hybrid-gpu` | 8-16GB | GPU primary, spills to RAM | Fast (~40-60 tok/s) |
| `hybrid-cpu` | 16-32GB | CPU primary, GPU assist | Moderate (~15-25 tok/s) |
| `cpu` | >32GB | Too large for GPU | Slow (~8-12 tok/s) |

### Heavy Agents (CPU/RAM — 64GB)

These models use Ryzen AI 9 cores and system RAM. Run alongside Docker containers.

| Agent Role | Model | Parameters | Hardware | Memory |
|------------|-------|------------|----------|--------|
| **Coder** | `qwen2.5-coder:32b` | 32B | hybrid-cpu | ~19GB (8GB VRAM + 11GB RAM) |
| **Reviewer** | `llama3.1:70b` (Q4_K_M) | 70B | cpu | ~42GB RAM only |

**Commands:**
```bash
ollama pull qwen2.5-coder:32b
ollama pull llama3.1:70b
```

### Fast Agents (GPU/VRAM — 8GB)

These models run on RTX 5070 for instant responses during active coding.

| Agent Role | Model | Parameters | Hardware | Memory |
|------------|-------|------------|----------|--------|
| **Fixer** | `deepseek-coder-v2:16b` | 16B | hybrid-gpu | ~9GB (8GB VRAM + 1GB RAM) |
| **Documentator** | `llama3.1:8b` | 8B | gpu | ~5GB VRAM only |

**Commands:**
```bash
ollama pull deepseek-coder-v2:16b
ollama pull llama3.1:8b
```

---

## The Intelligence vs Speed Tradeoff

### 8B vs 70B: Junior Developer vs Senior Architect

The difference between 8B and 70B models is the difference between a **Speedy Assistant** and a **Senior Architect**.

| Aspect | Llama 3.1 8B | Llama 3.1 70B |
|--------|--------------|---------------|
| **Persona** | Fast Junior Developer | Senior Architect |
| **Parameters** | 8 billion | 70 billion (9x more) |
| **VRAM Needs** | ~5GB (fits in RTX 5070) | ~42GB (quantized) |
| **Where It Runs** | 100% on GPU | Mostly on 64GB RAM (CPU) |
| **Speed** | Instant, like typing | Methodical, 2-5 tok/s |
| **Stability** | Rock solid | High memory pressure |
| **HumanEval** | ~62% | ~80% (+18% accuracy) |

### When Intelligence Matters

**8B excels at pattern matching:**
- Summarizing files
- Writing standard READMEs
- Converting JSON schemas
- Generating .env.example files
- Summarizing VPS logs

**70B excels at multi-step reasoning:**
- Understanding *why* a Docker network bridge fails under load
- Security audits ("Check this Traefik config for vulnerabilities")
- Architecture design ("How should I structure multi-tenant DB for Fabrik?")
- Complex debugging when the 32B Coder produces code that doesn't run

### The Verdict

**You need both.** The 8B keeps you moving fast without heat or noise. The 70B is the "heavy artillery" you bring in when you have a problem you can't solve yourself.

---

## Role-to-Model Mapping

| Role | Model | Hardware | Latency | Use Case |
|------|-------|----------|---------|----------|
| Coder | qwen2.5-coder:32b | hybrid-cpu | Medium | Building Fabrik core, complex orchestration |
| Reviewer | llama3.1:70b | cpu | Slow | Senior architect perspective, catching flaws |
| Fixer | deepseek-coder-v2:16b | hybrid-gpu | Fast | Console errors, quick debugging |
| Documentator | llama3.1:8b | gpu | Instant | READMEs, API docs, CHANGELOG |

---

## Integration with Windsurf / Kilo CLI

### Ollama API Endpoint

All agents access via single endpoint: `http://localhost:11434`

```bash
# Test connection
curl http://localhost:11434/api/tags
```

### Kilo CLI Configuration

Add Ollama as a provider in Kilo:

```bash
# In opencode.json or via CLI
kilo config set providers.ollama.baseUrl "http://localhost:11434"
```

### Windsurf Cascade Integration

Configure in Windsurf settings to use Ollama models for specific tasks.

---

## Usage Patterns

### Background Documentation Updates

Use the 8B model to auto-update `/opt/<project>/docs/` while coding:

```bash
# Example: Generate README updates in background
ollama run llama3.1:8b "Update this README based on the code changes: ..."
```

### Code Review Pipeline

```bash
# Heavy review with 70B model (takes longer, thorough)
ollama run llama3.1:70b "Review this code for architectural issues: ..."
```

### Quick Fixes

```bash
# Fast fix with GPU model
ollama run deepseek-coder-v2:16b "Fix this error: ..."
```

---

## Performance Expectations

| Model | Hardware | Tokens/sec | Memory Usage | Stability |
| llama3.1:8b | gpu | ~80-100 | 5GB VRAM | Rock solid |
| deepseek-coder-v2:16b | hybrid-gpu | ~40-60 | 9GB (8+1) | Stable |
| qwen2.5-coder:32b | hybrid-cpu | ~15-25 | 19GB (8+11) | Stable |
| llama3.1:70b (Q4) | cpu | ~8-12 | 42GB RAM | High memory pressure ⚠️ |

> **⚠️ 70B Stability Note:** The 70B model can cause system instability (BSOD) under high memory pressure. Consider using a low-context configuration or ensuring no other heavy processes are running.

### Stabilizing 70B: Low-Context Configuration

To prevent BSOD when using the 70B model, reduce context window and ensure clean memory state:

```bash
# Create a low-context Modelfile
cat > /tmp/llama70b-stable.Modelfile << 'EOF'
FROM llama3.1:70b

# Reduce context to 4K (default is 128K) - dramatically reduces RAM usage
PARAMETER num_ctx 4096

# Reduce batch size for more stable memory allocation
PARAMETER num_batch 256

# System prompt for focused responses
SYSTEM You are a senior code reviewer. Be concise and focused.
EOF

# Create the stable variant
ollama create llama3.1:70b-stable -f /tmp/llama70b-stable.Modelfile
```

**Before running 70B:**
```bash
# Free up RAM - close browsers, stop non-essential Docker containers
docker stop $(docker ps -q --filter "status=running" | head -5)

# Check available memory (need ~45GB free)
free -h
```

**Memory Budget for 70B:**
| Context | RAM Required | Stability |
|---------|--------------|-----------|
| 128K (default) | ~55GB | ❌ BSOD risk |
| 32K | ~48GB | ⚠️ Marginal |
| 8K | ~44GB | ✅ Stable |
| 4K | ~42GB | ✅ Rock solid |

---

## Benefits for Fabrik Workflow

| Benefit | Description |
|---------|-------------|
| **Zero Cost** | No API bills, unlimited usage |
| **Offline** | Works without internet |
| **No Rate Limits** | No throttling during heavy development |
| **No Outages** | Independent of Anthropic/OpenAI availability |
| **Privacy** | Code never leaves machine |
| **Parallel** | Run multiple models simultaneously |

---

## Fallback Strategy

When local models struggle, escalate to cloud:

1. **First:** Local model (free)
2. **Escalate:** Kilo CLI free tier models
3. **Premium:** Claude/GPT via Kilo (paid)

---

## Database Schema for Local Models




<!-- AUTO-GENERATED:SCHEMA_LOCAL_START -->

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| **Identity** | | | |
|--------|------|---------|-------------|
| id | TEXT |  | PRIMARY KEY |
| name | TEXT |  |  |
| family | TEXT |  |  |
| **Model Specs** | | | |
|--------|------|---------|-------------|
| parameter_size | TEXT |  |  |
| quantization | TEXT |  |  |
| size_bytes | INTEGER |  |  |
| **Hardware Requirements** | | | |
|--------|------|---------|-------------|
| hardware | TEXT | 'auto' |  |
| vram_required_gb | REAL |  |  |
| ram_required_gb | REAL |  |  |
| **Role Assignment** | | | |
|--------|------|---------|-------------|
| assigned_role | TEXT |  |  |
| role_priority | INTEGER | 1 |  |
| **Performance** | | | |
|--------|------|---------|-------------|
| tokens_per_sec | REAL |  |  |
| **Capabilities** | | | |
|--------|------|---------|-------------|
| context_window_k | INTEGER | 32 |  |
| **Status** | | | |
|--------|------|---------|-------------|
| status | TEXT | 'available' |  |
| **Metadata** | | | |
|--------|------|---------|-------------|
| last_used | TIMESTAMP |  |  |
| last_synced | TIMESTAMP | CURRENT_TIMESTAMP |  |
| digest | TEXT |  |  |
| modified_at | TIMESTAMP |  |  |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP |  |
| **Capabilities** | | | |
|--------|------|---------|-------------|
| has_vision | INTEGER | 0 |  |
| has_tools | INTEGER | 0 |  |
| is_agentic | INTEGER | 0 |  |
| is_reasoning | INTEGER | 0 |  |
| **Benchmarks** | | | |
|--------|------|---------|-------------|
| arena_elo | INTEGER |  |  |
| tbench_accuracy | REAL |  |  |
| **Performance** | | | |
|--------|------|---------|-------------|
| time_to_first_token_ms | REAL |  |  |
| **Other** | | | |
|--------|------|---------|-------------|
| humaneval_score | REAL |  |  |
| coding_score | REAL |  |  |

<!-- AUTO-GENERATED:SCHEMA_LOCAL_END -->
### Data Sources

- **Model Info**: Ollama API (`http://localhost:11434/api/tags`)
- **Capabilities**: `LOCAL_MODEL_CAPABILITIES` config in `kilo_agents_db.py`
- **Benchmarks**: Manual configuration (future: EvalPlus integration)

---

## Agent Interaction Methods

### Direct Ollama CLI
```bash
# Talk to specific Fabrik agents
ollama run fabrik-coder-qwen2.5-32b          # Lead Engineer
ollama run fabrik-reviewer-llama3.1-70b      # Senior Reviewer
ollama run fabrik-fixer-deepseek-v2-16b      # Surgical Fixer
ollama run fabrik-docs-llama3.1-8b           # Documentator
```

### API Usage
```bash
# Direct API calls for programmatic access
curl -s http://localhost:11434/api/generate -d '{
  "model": "fabrik-coder-qwen2.5-32b",
  "prompt": "Your question here",
  "stream": false
}' | jq -r '.response'
```

---

## Fabrik Agent Setup and Validation

### Overview

The Fabrik engineering team consists of 4 specialized local AI agents built with custom Modelfiles. These agents enforce consistent behavior, follow project-specific rules, and maintain separation of concerns throughout the development workflow.

### Agent Creation Process

To build your Fabrik engineering team, create four Modelfiles in your Ubuntu (WSL) terminal:

#### **Step 1: Create the Lead Engineer (`fabrik-coder-qwen2.5-32b`)**
This agent handles implementation and must strictly follow the "HARD STOPS".

```bash
# Create Modelfile
nano fabrik-coder.Modelfile

# Paste content:
FROM qwen2.5-coder:32b
PARAMETER temperature 0.2
PARAMETER num_ctx 16384
SYSTEM """
You are the Lead Engineer for Fabrik. You follow the 'HARD STOPS' from AGENTS-compact.md:
- NEVER commit — Traycer commits.
- NEVER bare 'pip install' — use '/opt/<project>/.venv/bin/pip'.
- NEVER Alpine — use '-slim-bookworm'.
- NEVER hardcode localhost/secrets — use 'os.getenv()'.
- NEVER modify files outside task scope.
Tech Stack: Node.js/TypeScript, Next.js, FastAPI, Docker (amd64), PostgreSQL.
"""

# Save/Exit: Ctrl+O, Enter, then Ctrl+X

# Build agent
ollama create fabrik-coder-qwen2.5-32b -f fabrik-coder.Modelfile
```

#### **Step 2: Create the Senior Reviewer (`fabrik-reviewer-llama3.1-70b`)**
This agent performs deep audits with temperature 0 for absolute logic.

```bash
# Create Modelfile
nano fabrik-reviewer.Modelfile

# Paste content:
FROM llama3.1:70b
PARAMETER temperature 0
PARAMETER num_ctx 32768
SYSTEM """
You are the Senior Reviewer for Fabrik. Follow the Reviewer Directives in AGENTS.md:
- R1: Identify bugs, security issues, performance problems. Cite line numbers.
- R2: Evaluate correctness and safety, not just describe code.
- R3: Flag silent failure modes.
- R4: Prioritize: BLOCKER / MAJOR / MINOR.
Reviewer AI never fixes — report findings only.
"""

# Save/Exit: Ctrl+O, Enter, then Ctrl+X

# Build agent
ollama create fabrik-reviewer-llama3.1-70b -f fabrik-reviewer.Modelfile
```

#### **Step 3: Create the Surgical Fixer (`fabrik-fixer-deepseek-v2-16b`)**
This agent uses DeepSeek's specialized logic to fix only reported issues.

```bash
# Create Modelfile
nano fabrik-fixer.Modelfile

# Paste content:
FROM deepseek-coder-v2:16b
PARAMETER temperature 0.1
PARAMETER num_ctx 16384
SYSTEM """
You are the Fabrik Fixer. Follow the Fixer Directives in AGENTS.md:
- F1: Fix ONLY reported issues — no refactoring, no new features.
- F2: State assumptions explicitly if ambiguous.
- F3: Minimal edits — follow existing code style.
- F4: Final pass: check off-by-one errors, null paths, missing imports.
"""

# Save/Exit: Ctrl+O, Enter, then Ctrl+X

# Build agent
ollama create fabrik-fixer-deepseek-v2-16b -f fabrik-fixer.Modelfile
```

#### **Step 4: Create the Documentator (`fabrik-docs-llama3.1-8b`)**
This agent runs entirely in VRAM for fast documentation updates.

```bash
# Create Modelfile
nano fabrik-docs.Modelfile

# Paste content:
FROM llama3.1:8b
PARAMETER temperature 0.7
PARAMETER num_ctx 8192
SYSTEM """
You are the Fabrik Documentator. You update docs at the END OF PHASE:
- Auto-generate: CHANGELOG entries, API docs, env var docs.
- Update CHANGELOG.md for every code change.
- Update README.md features table with status.
Use clean JSDoc and Markdown.
"""

# Save/Exit: Ctrl+O, Enter, then Ctrl+X

# Build agent
ollama create fabrik-docs-llama3.1-8b -f fabrik-docs.Modelfile
```

#### **Step 5: Final Verification**
```bash
# Verify all agents are created
ollama list | grep fabrik
```

You should see all four fabrik agents ready for work.

> **⚠️ Hardware Note**: If you're using the RTX 5070 (8GB VRAM), keep 6GB free for the OS and other applications. This leaves ~2GB VRAM for models, which is why fabrik-docs (8B) runs entirely in VRAM while larger models spill to RAM.

### Agent Validation

To validate that your agents have been "hired" with the correct instructions and parameters, inspect their "DNA" directly from the Ollama registry:

#### **1. Validate the Lead Engineer**
```bash
ollama show fabrik-coder-qwen2.5-32b --modelfile
```
**Check for:**
- `PARAMETER temperature 0.2` ✅
- `PARAMETER num_ctx 16384` ✅
- SYSTEM prompt containing all HARD STOPS ✅

#### **2. Validate the Senior Reviewer**
```bash
ollama show fabrik-reviewer-llama3.1-70b --modelfile
```
**Check for:**
- `PARAMETER temperature 0` ✅
- `PARAMETER num_ctx 32768` ✅
- SYSTEM prompt containing Reviewer Directives (R1-R4) ✅

#### **3. Validate the Surgical Fixer**
```bash
ollama show fabrik-fixer-deepseek-v2-16b --modelfile
```
**Check for:**
- `PARAMETER temperature 0.1` ✅
- `PARAMETER num_ctx 16384` ✅
- SYSTEM prompt containing Fixer Directives (F1-F4) ✅

#### **4. Validate the Documentator**
```bash
ollama show fabrik-docs-llama3.1-8b --modelfile
```
**Check for:**
- `PARAMETER temperature 0.7` ✅
- `PARAMETER num_ctx 8192` ✅
- SYSTEM prompt focused on CHANGELOG and README updates ✅

### Agent Configuration Summary

| Agent | Model | Temperature | Context | Primary Role | Key Directives |
|-------|-------|-------------|---------|-------------|----------------|
| **fabrik-coder** | qwen2.5-coder:32b | 0.2 | 16K | Lead Engineer | HARD STOPS from AGENTS-compact.md |
| **fabrik-reviewer** | llama3.1:70b | 0 | 32K | Senior Reviewer | R1-R4 Reviewer Directives |
| **fabrik-fixer** | deepseek-coder-v2:16b | 0.1 | 16K | Surgical Fixer | F1-F4 Fixer Directives |
| **fabrik-docs** | llama3.1:8b | 0.7 | 8K | Documentator | CHANGELOG/README updates |

### Integration Points

#### IDE Configuration (Windsurf/Cascade)
Configure Windsurf to use appropriate agents based on task type:
- **Implementation**: fabrik-coder-qwen2.5-32b
- **Code Review**: fabrik-reviewer-llama3.1-70b
- **Bug Fixes**: fabrik-fixer-deepseek-v2-16b
- **Documentation**: fabrik-docs-llama3.1-8b

#### Kilo CLI Integration
The agents automatically integrate with Kilo CLI workflows:
- Code reviews use fabrik-reviewer for analysis
- Auto-fix loops use fabrik-fixer for corrections
- Documentation generation uses fabrik-docs

### Hardware Allocation

| Agent | Hardware | Memory Usage | Speed | Stability |
|-------|----------|--------------|-------|-----------|
| fabrik-coder | hybrid-cpu | ~19GB (8GB VRAM + 11GB RAM) | Moderate (~15-25 tok/s) | Stable |
| fabrik-reviewer | cpu | ~42GB RAM | Slow (~8-12 tok/s) | High memory pressure ⚠️ |
| fabrik-fixer | hybrid-gpu | ~9GB (8GB VRAM + 1GB RAM) | Fast (~40-60 tok/s) | Stable |
| fabrik-docs | gpu | ~5GB VRAM | Instant (~80-100 tok/s) | Rock solid |

### Maintenance

#### Updating Agent Instructions
To update an agent's behavior:
1. Edit the corresponding Modelfile
2. Rebuild: `ollama create <agent-name> -f <Modelfile>`
3. Validate: `ollama show <agent-name> --modelfile`

#### Backup Agent Configurations
```bash
# Export all fabrik agent configurations
for agent in fabrik-coder-qwen2.5-32b fabrik-reviewer-llama3.1-70b fabrik-fixer-deepseek-v2-16b fabrik-docs-llama3.1-8b; do
    ollama show $agent --modelfile > ${agent}.Modelfile.backup
done
```

### Fabrik Workflow Integration

#### Code Reviews
```bash
# Review staged changes (uses fabrik-reviewer)
python scripts/kilo_code_review.py staged

# Auto-fix loop (uses fabrik-fixer for fixes)
python scripts/kilo_code_review.py auto-fix src/ --max-iterations 3
```

#### Documentation
```bash
# Update docs at phase end (uses fabrik-docs)
python scripts/kilo_docs_enforcer.py --auto-generate
```

#### Model Selection
```bash
# Check available models and roles
python scripts/kilo-benchmarks/db_models.py

# View local model status
python scripts/kilo-benchmarks/kilo_agents_db.py ollama-status
```

### IDE Integration (Windsurf/Cascade)
- **Manual selection**: Choose model in IDE settings
- **Auto-routing**: System automatically picks agent based on task type
- **Hardware aware**: Automatically uses appropriate model based on available VRAM/RAM

#### Windsurf Configuration
To configure Windsurf IDE to use your local Fabrik agents:

1. **Settings → Models → Local Models**
2. **Add custom model endpoints**:
   - `http://localhost:11434` (Ollama API)
3. **Select default model**: `fabrik-coder-qwen2.5-32b`
4. **Task-based routing** (optional):
   - Code completion: `fabrik-coder-qwen2.5-32b`
   - Code review: `fabrik-reviewer-llama3.1-70b`
   - Bug fixes: `fabrik-fixer-deepseek-v2-16b`
   - Documentation: `fabrik-docs-llama3.1-8b`

#### Windsurf Cascade Slash Commands

In Windsurf Cascade chat, press `/` to see available workflows:

| Command | Description | Speed |
|---------|-------------|-------|
| `/local-coder` | Implement features with qwen32b | ~15-25 tok/s |
| `/local-review` | Deep code review with llama70b | ~8-12 tok/s |
| `/local-fixer` | Fast bug fixes with deepseek16b | ~40-60 tok/s |
| `/local-docs` | Instant documentation with llama8b | ~80-100 tok/s |
| `/kilo-review` | Automated review → fix → re-review loop | Variable |

**Usage:**
1. Type `/` in Cascade chat
2. Select workflow from menu
3. Cascade executes the script automatically

All workflows use hardware-safe local LLMs with zero API cost.

#### Cascade Wrapper Scripts (Direct Invocation)

For command-line or programmatic use, call the wrapper scripts directly:

**Available Wrappers:**
```bash
# Local_Coder_qwen32b - Coding (32B, hybrid-cpu, ~15-25 tok/s)
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "implement feature X"

# Local_Review_llama70b - Interactive code review (70B, CPU, ~8-12 tok/s)
/opt/fabrik/scripts/Local_Review_llama70b.sh "review these changes"

# Local_Fixer_ds16b - Bug fixing (16B, hybrid-gpu, ~40-60 tok/s)
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix this error"

# Local_Documentator_llama3.1-8b - Documentation (8B, GPU, ~80-100 tok/s)
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "update README"

# Kilo_Review - Automated code review workflow
/opt/fabrik/scripts/Kilo_Review.sh staged           # Review staged files
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/    # Review + auto-fix loop
```

**Hardware Safety Features:**
- **Global Sequential Guard**: Prevents multiple models loading simultaneously (uses `/opt/.fabrik_agent.lock`)
- **VRAM Monitoring**: Waits for GPU idle before loading models
- **Fast-Path Optimization**: Documentation agent bypasses lock when 5.5GB VRAM available
- **Automatic Timeouts**: 70B/32B = 600s, 8B/16B = 300s

**Usage in Cascade Workflows:**
```bash
# Example: Piping Cascade context to local agent
echo "Fix the authentication bug in src/api/auth.py" | /opt/fabrik/scripts/Local_Fixer_ds16b.sh

# Example: Direct invocation
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "Generate CHANGELOG entry for today's changes"
```

**Implementation Details:**
- Wrappers call Kilo CLI agent scripts in `~/.traycer/cli-agents/`
- Inherit all hardware safety logic (Global Sequential Guard, VRAM checks, fast-path)
- Set minimal Traycer environment variables for compatibility
- Support both argument and stdin input

### Performance Notes
- **GPU models** (fabrik-docs): Fastest, fits entirely in VRAM, has fast-path bypass
- **Hybrid-GPU** (fabrik-fixer): Fast, minimal RAM spill
- **Hybrid-CPU** (fabrik-coder): Moderate, uses RAM with GPU assist
- **CPU only** (fabrik-reviewer): Slower but handles largest context

---

## Global Kilo Configuration

All Kilo CLI agents (both cloud and local) are controlled by the global configuration file at `~/.config/kilo/opencode.json`. This file specifies which instruction documents are passed to agents.

### Current Configuration

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

### Key Points

- **System-wide effect**: This configuration applies to ALL Kilo CLI agents, regardless of where they're run
- **AGENTS-compact.md only**: Only the compact instructions are passed to CLI agents
- **AGENTS.md restriction**: The full `AGENTS.md` is reserved for Traycer and should NOT be in global config
- **Project override**: Individual projects can override with their own `opencode.json`

### Why This Matters

1. **Token efficiency**: CLI agents get only essential rules, not planning context
2. **Clear separation**: Traycer handles planning, CLI agents handle execution
3. **Consistent behavior**: All CLI agents follow the same core rules

---

## See Also

- **[KILO_MODEL_SELECTION.md](kilo/KILO_MODEL_SELECTION.md)** — Cloud model selection
- **[AI_TAXONOMY.md](AI_TAXONOMY.md)** — AI tool categories
- **[stack.md](stack.md)** — Full infrastructure stack

<!-- AUTO-GENERATED:LOCAL_MODELS_START -->
## Installed Models (Auto-Generated)

**Last Synced:** 2026-04-13 15:32

| Model | Role | Hardware | Size | Context | Vision | Tools | Agentic | ELO | Code |
|-------|------|----------|------|---------|--------|-------|---------|-----|------|
| `fabrik-coder-qwen2.5-32b:latest` | coding | hybrid-cpu | 32B | 16K | - | ✓ | ✓ | 1280 | - |
| `fabrik-reviewer-llama3.1-70b:latest` | reviewing | cpu | 70B | 32K | - | ✓ | ✓ | 1290 | - |
| `fabrik-fixer-deepseek-v2-16b:latest` | fixing | hybrid-gpu | 16B | 16K | - | ✓ | ✓ | 1260 | - |
| `fabrik-docs-llama3.1-8b:latest` | documentation | gpu | 8B | 8K | - | ✓ | - | 1150 | - |
| `qwen2.5-coder:32b` | - | cpu | 32B | 32K | - | - | - | - | - |
| `llama3.1:8b` | - | cpu | 8B | 32K | - | - | - | - | - |
| `deepseek-coder-v2:16b` | - | cpu | 16B | 32K | - | - | - | - | - |
| `llama3.1:70b` | - | cpu | 70B | 32K | - | - | - | - | - |

<!-- AUTO-GENERATED:LOCAL_MODELS_END -->
