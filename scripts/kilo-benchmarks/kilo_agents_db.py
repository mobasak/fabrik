#!/usr/bin/env python3
"""
Kilo Agents SQLite Database Manager.

Manages agent data with historical tracking:
- Syncs ALL models from Kilo CLI with FULL capabilities:
  • Vision support (image input)
  • Tool/function calling
  • Reasoning/thinking modes
  • Context window size
  • Input/output costs per 1M tokens
- Syncs 4 custom local agents from Ollama (fabrik-coder, fabrik-fixer, fabrik-reviewer, fabrik-docs)
- Updates benchmark scores from scrapers (Arena ELO, TBench)
- Maintains daily historical snapshots
- Computes derived metrics (perf_per_dollar, task_tier)

Usage:
    python scripts/kilo_agents_db.py init          # Create/reset database
    python scripts/kilo_agents_db.py sync          # Sync from Kilo CLI
    python scripts/kilo_agents_db.py update        # Update benchmarks
    python scripts/kilo_agents_db.py snapshot      # Create daily snapshot
    python scripts/kilo_agents_db.py export        # Export to markdown
    python scripts/kilo_agents_db.py ollama-sync   # Sync 4 custom local agents
    python scripts/kilo_agents_db.py ollama-status # Show local model status
    python scripts/kilo_agents_db.py all           # Full pipeline (Kilo + Ollama)
"""

import json
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
FABRIK_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
SCHEMA_PATH = SCRIPT_DIR / "kilo_agents.sql"
SELECTED_JSON = SCRIPT_DIR / "kilo_selected_agents.json"
MASTER_MD = FABRIK_ROOT / "docs" / "traycer" / "kilo_selected_agents.md"


def log(msg: str) -> None:
    print(f"[kilo-db] {msg}")


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False) -> None:
    """Initialize database from schema."""
    if DB_PATH.exists() and not force:
        log(f"Database exists at {DB_PATH}")
        log("Use --force to recreate")
        return

    if DB_PATH.exists():
        DB_PATH.unlink()
        log("Removed existing database")

    conn = get_connection()
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    log(f"Created database at {DB_PATH}")


def fetch_kilo_models() -> list[dict[str, Any]]:
    """Fetch all models from Kilo CLI with full metadata."""
    log("Fetching models from Kilo CLI...")
    try:
        result = subprocess.run(
            ["kilo", "models", "--verbose"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout

        # Parse the verbose output (model ID followed by JSON blocks)
        # Each model starts with "kilo/..." line followed by a JSON object
        models = []
        lines = output.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for start of JSON object
            if line.strip() == "{":
                # Collect all lines until we have a complete JSON object
                json_lines = ["{"]
                brace_count = 1
                i += 1

                while i < len(lines) and brace_count > 0:
                    json_lines.append(lines[i])
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    i += 1

                # Parse the JSON
                json_str = "\n".join(json_lines)
                try:
                    model = json.loads(json_str)
                    if "id" in model:
                        models.append(model)
                except json.JSONDecodeError:
                    pass
            else:
                i += 1

        log(f"  Found {len(models)} models")
        return models

    except subprocess.TimeoutExpired:
        log("  Timeout fetching Kilo models")
        return []
    except Exception as e:
        log(f"  Error: {e}")
        return []


def compute_task_tier(
    input_cost: float, output_cost: float, context_k: int, is_agentic: bool
) -> int:
    """
    Compute task tier based on cost and capabilities.
    1 = cheap (< $0.50 blended)
    2 = balanced ($0.50 - $5.00 blended)
    3 = heavy (> $5.00 blended or premium features)
    """
    # Blended cost estimate (assuming 1:3 input:output ratio)
    blended = (input_cost + 3 * output_cost) / 4

    if blended < 0.5:
        return 1
    elif blended < 5.0:
        return 2
    else:
        return 3


def compute_perf_per_dollar(elo: int | None, input_cost: float, output_cost: float) -> float | None:
    """Compute performance per dollar (higher is better)."""
    if elo is None:
        return None
    blended = (input_cost + 3 * output_cost) / 4
    if blended <= 0:
        return float(elo)  # Free model
    return round(elo / blended, 2)


def extract_variant(model_id: str, name: str) -> str:
    """
    Extract thinking variant from model ID or name.

    Returns: 'standard', 'thinking', or 'thinking-extended'

    Examples:
        'anthropic/claude-opus-4.6:thinking' -> 'thinking'
        'Claude Opus 4.6 Thinking' -> 'thinking'
        'Claude Opus 4.5 (thinking-32k)' -> 'thinking-extended'
        'anthropic/claude-opus-4.6' -> 'standard'
    """
    combined = f"{model_id} {name}".lower()

    # Check for extended thinking variants
    if "thinking-32k" in combined or "thinking-extended" in combined:
        return "thinking-extended"

    # Check for thinking suffix in api_id (e.g., :thinking)
    if ":thinking" in model_id.lower():
        return "thinking"

    # Check for thinking in name
    if "thinking" in combined:
        return "thinking"

    return "standard"


def sync_from_kilo() -> None:
    """Sync agent data from Kilo CLI."""
    log("Syncing agents from Kilo CLI...")

    # Add missing columns to agents table (migration)
    conn = get_connection()
    cursor = conn.cursor()
    columns_to_add = [
        ("humaneval_score", "REAL"),
        ("coding_score", "REAL"),
    ]
    schema_changed = False
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type}")
            schema_changed = True
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()

    # Update documentation if schema changed
    if schema_changed:
        generate_schema_docs("agents")

    models = fetch_kilo_models()
    if not models:
        log("  No models found")
        return

    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    for model in models:
        model_id = model.get("id", "")
        if not model_id:
            continue

        api_id = model.get("api", {}).get("id", model_id)
        name = model.get("name", model_id)

        # Extract provider from model ID (e.g., "anthropic/claude-opus-4.6" -> "anthropic")
        provider = model_id.split("/")[0] if "/" in model_id else "unknown"

        # Pricing (convert to per 1M tokens)
        cost = model.get("cost", {})
        input_cost = cost.get("input", 0) * 1_000_000
        output_cost = cost.get("output", 0) * 1_000_000

        # Capabilities
        caps = model.get("capabilities", {})
        context_k = model.get("limit", {}).get("context", 128000) // 1000
        has_vision = caps.get("input", {}).get("image", False)
        has_tools = caps.get("toolcall", False)
        is_agentic = caps.get("reasoning", False)

        # Compute derived fields
        task_tier = compute_task_tier(input_cost, output_cost, context_k, is_agentic)
        variant = extract_variant(model_id, name)

        # Check if exists
        cursor.execute("SELECT id FROM agents WHERE id = ?", (model_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                """
                UPDATE agents SET
                    api_id = ?,
                    name = ?,
                    provider = ?,
                    input_cost_per_m = ?,
                    output_cost_per_m = ?,
                    context_window_k = ?,
                    has_vision = ?,
                    has_tools = ?,
                    is_agentic = ?,
                    task_tier = ?,
                    variant = ?,
                    last_verified = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    api_id,
                    name,
                    provider,
                    input_cost,
                    output_cost,
                    context_k,
                    has_vision,
                    has_tools,
                    is_agentic,
                    task_tier,
                    variant,
                    date.today().isoformat(),
                    model_id,
                ),
            )
            updated += 1
        else:
            cursor.execute(
                """
                INSERT INTO agents (
                    id, api_id, name, provider,
                    input_cost_per_m, output_cost_per_m,
                    context_window_k, has_vision, has_tools, is_agentic,
                    task_tier, variant, last_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id,
                    api_id,
                    name,
                    provider,
                    input_cost,
                    output_cost,
                    context_k,
                    has_vision,
                    has_tools,
                    is_agentic,
                    task_tier,
                    variant,
                    date.today().isoformat(),
                ),
            )
            inserted += 1

    conn.commit()
    conn.close()
    log(f"  Inserted {inserted}, updated {updated} agents")


def update_benchmarks() -> None:
    """Update benchmark scores from scrapers."""
    from scrape_benchlm import build_benchlm_map, fetch_benchlm_coding
    from scrape_benchmarks import scrape_chatbot_arena, scrape_terminal_bench

    log("Updating benchmark scores...")

    arena = scrape_chatbot_arena()
    tbench = scrape_terminal_bench()
    benchlm_entries = fetch_benchlm_coding()
    benchlm_map = build_benchlm_map(benchlm_entries) if benchlm_entries else {}

    conn = get_connection()
    cursor = conn.cursor()

    # OpenRouter routing suffixes — see plan
    # docs/development/plans/2026-06-27-plan-openrouter-routing.md §6.1.
    # Stripping these is what closes the BENCHMARK_SOURCES.md §4.5 gap
    # (38 `:free` models had zero benchmark scores because their base-id
    # leaderboard row never joined).
    openrouter_routing_suffixes = (
        ":free",
        ":nitro",
        ":floor",
        ":beta",
        ":online",
        ":thinking",
    )

    # Build lookup maps (normalize names for matching)
    def normalize(name: str | None) -> str:
        """Normalize model name for matching against leaderboard entries.

        Defensive: returns "" for non-string or empty (Phase 0 review Pass A
        Finding 1; tightened in Pass B Finding 1 to isinstance so falsy
        non-strings don't silently degrade). Propagated to this sibling
        normalizer per the Pass 4 reverse-audit lesson — both writers must
        guard nulls the same way.
        """
        if not isinstance(name, str) or not name:
            return ""
        n = name.lower().replace(" ", "-").replace("_", "-")
        # Strip OpenRouter routing suffixes repeatedly — `x/y:free:online`
        # collapses fully to `x/y` so the base model's leaderboard row joins
        # to the routed variant (Phase 0 of the OpenRouter routing plan).
        changed = True
        while changed:
            changed = False
            for suffix in openrouter_routing_suffixes:
                if n.endswith(suffix):
                    n = n[: -len(suffix)]
                    changed = True
        # Remove common version/preview suffixes that vary between sources
        for suffix in ["-preview", "-exp", "-001", "-002", "-003", "-customtools"]:
            if n.endswith(suffix):
                n = n[: -len(suffix)]
        return n

    def get_match_keys(name: str) -> list[str]:
        """Generate multiple match keys for a model name."""
        keys = [name.lower(), normalize(name)]
        # Also try without provider prefix
        if "/" in name:
            short = name.split("/")[-1]
            keys.extend([short.lower(), normalize(short)])
        # Also try extracting core model name (e.g., "Google: Gemini 3.1 Pro" -> "gemini-3.1-pro")
        if ":" in name:
            short = name.split(":")[-1].strip()
            keys.extend([short.lower(), normalize(short)])
        return keys

    # Build arena_map with MAX ELO per model
    arena_map = {}
    for entry in arena:
        elo = int(entry.score)
        for key in get_match_keys(entry.model):
            if key not in arena_map or elo > arena_map[key]:
                arena_map[key] = elo  # Keep BEST ELO per model

    # Build tbench_map with MAX score per model (different agents get different scores)
    tbench_map = {}
    for entry in tbench:
        for key in get_match_keys(entry.model):
            if key not in tbench_map or entry.score > tbench_map[key]:
                tbench_map[key] = entry.score  # Keep BEST score per model

    # Update agents
    cursor.execute("SELECT id, name FROM agents")
    agents = cursor.fetchall()

    elo_updated = 0
    tbench_updated = 0
    benchlm_updated = 0

    for agent in agents:
        agent_id = agent["id"]
        agent_name = agent["name"]

        # Generate all possible match keys for this agent
        match_keys = get_match_keys(agent_id) + get_match_keys(agent_name)

        # Check arena
        elo = None
        for key in match_keys:
            if key in arena_map:
                elo = arena_map[key]
                break

        # Check tbench
        accuracy = None
        for key in match_keys:
            if key in tbench_map:
                accuracy = tbench_map[key]
                break

        # Check BenchLM
        swe_pro = None
        weighted = None
        lcb = None
        for key in match_keys:
            if key in benchlm_map:
                benchlm_data = benchlm_map[key]
                swe_pro = benchlm_data.get("swe_bench_pro")
                weighted = benchlm_data.get("weighted_coding")
                lcb = benchlm_data.get("livecodebench")
                break

        if elo is not None or accuracy is not None or swe_pro is not None:
            # Get current costs for perf_per_dollar calculation
            cursor.execute(
                "SELECT input_cost_per_m, output_cost_per_m FROM agents WHERE id = ?",
                (agent_id,),
            )
            row = cursor.fetchone()
            perf = None
            if row and elo:
                perf = compute_perf_per_dollar(
                    elo, row["input_cost_per_m"], row["output_cost_per_m"]
                )

            update_parts = []
            params = []

            if elo is not None:
                update_parts.append("arena_elo = ?")
                params.append(elo)
                elo_updated += 1

            if accuracy is not None:
                update_parts.append("tbench_accuracy = ?")
                params.append(accuracy)
                tbench_updated += 1

            if swe_pro is not None:
                update_parts.append("swe_bench_pro = ?")
                params.append(swe_pro)
                benchlm_updated += 1

            if weighted is not None:
                update_parts.append("weighted_coding = ?")
                params.append(weighted)
                benchlm_updated += 1

            if lcb is not None:
                update_parts.append("livecodebench = ?")
                params.append(lcb)
                benchlm_updated += 1

            if perf is not None:
                update_parts.append("perf_per_dollar = ?")
                params.append(perf)

            update_parts.append("updated_at = CURRENT_TIMESTAMP")
            params.append(agent_id)

            cursor.execute(
                f"UPDATE agents SET {', '.join(update_parts)} WHERE id = ?",
                params,
            )

    conn.commit()
    conn.close()
    log(f"  Updated {elo_updated} Elo, {tbench_updated} TBench, {benchlm_updated} BenchLM scores")


def create_snapshot() -> None:
    """Create daily historical snapshot."""
    today = date.today().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # Check if snapshot exists for today
    cursor.execute("SELECT COUNT(*) FROM agent_history WHERE snapshot_date = ?", (today,))
    if cursor.fetchone()[0] > 0:
        log(f"Snapshot for {today} already exists, skipping")
        conn.close()
        return

    # Create snapshot from current rankings view
    cursor.execute(
        """
        INSERT INTO agent_history (
            agent_id, snapshot_date, rank, arena_elo, tbench_accuracy,
            input_cost_per_m, output_cost_per_m, perf_per_dollar
        )
        SELECT
            id, ?, rank, arena_elo, tbench_accuracy,
            input_cost_per_m, output_cost_per_m, perf_per_dollar
        FROM v_current_rankings
        """,
        (today,),
    )

    rows = cursor.rowcount
    conn.commit()
    conn.close()
    log(f"Created snapshot for {today} with {rows} agents")


def export_markdown() -> None:
    """Export current rankings to markdown."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM v_current_rankings
        ORDER BY rank
        LIMIT 60
        """
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        log("No data to export")
        return

    # Build markdown table
    lines = [
        "# Kilo Agents Master Table",
        "",
        f"**Last Updated:** {datetime.now().isoformat()}",
        "**Source:** [openlm.ai/chatbot-arena](https://openlm.ai/chatbot-arena/) | [tbench.ai](https://www.tbench.ai/leaderboard/terminal-bench/2.0)",
        "",
        f"## Top {len(rows)} Agents Ranked by Chatbot Arena Elo",
        "",
        "| Rank | Model | Provider | Elo | TBench% | In$/M | Out$/M | Ctx | Vision | Tools | Agentic | Tier | $/Perf | Status |",
        "|------|-------|----------|-----|---------|-------|--------|-----|--------|-------|---------|------|--------|--------|",
    ]

    for row in rows:
        rank = row["rank"]
        model = row["id"].split("/")[-1] if "/" in row["id"] else row["id"]
        provider = row["provider"]
        elo = row["arena_elo"] or "~"
        tbench = f"{row['tbench_accuracy']:.1f}" if row["tbench_accuracy"] else "~"
        in_cost = f"${row['input_cost_per_m']:.2f}" if row["input_cost_per_m"] else "$0"
        out_cost = f"${row['output_cost_per_m']:.2f}" if row["output_cost_per_m"] else "$0"
        ctx = f"{row['context_window_k']}K"
        vision = "✓" if row["has_vision"] else ""
        tools = "✓" if row["has_tools"] else ""
        agentic = "✓" if row["is_agentic"] else ""
        tier = row["task_tier"]
        perf = f"{row['perf_per_dollar']:.0f}" if row["perf_per_dollar"] else "~"
        status = "✅" if row["status"] == "active" else "❌"

        lines.append(
            f"| {rank} | **{model}** | {provider} | {elo} | {tbench} | {in_cost} | {out_cost} | {ctx} | {vision} | {tools} | {agentic} | {tier} | {perf} | {status} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Column Legend")
    lines.append("")
    lines.append("- **Elo**: Chatbot Arena rating (higher = better)")
    lines.append("- **TBench%**: Terminal Bench 2.0 accuracy")
    lines.append("- **Ctx**: Context window in thousands of tokens")
    lines.append("- **Vision**: Supports image input")
    lines.append("- **Tools**: Supports tool/function calling")
    lines.append("- **Agentic**: Has reasoning/thinking capabilities")
    lines.append("- **Tier**: 1=cheap, 2=balanced, 3=heavy")
    lines.append("- **$/Perf**: Performance per dollar (Elo / blended cost)")
    lines.append("")

    MASTER_MD.write_text("\n".join(lines))
    log(f"Exported {len(rows)} agents to {MASTER_MD}")


# =============================================================================
# LOCAL LLM (OLLAMA) FUNCTIONS
# =============================================================================

OLLAMA_API = "http://localhost:11434"
LOCAL_LLM_DOC = FABRIK_ROOT / "docs" / "reference" / "LOCAL_LLM_INFRASTRUCTURE.md"

# Known model capabilities - used to populate DB when syncing from Ollama
# Sources: model cards, Chatbot Arena (arena_elo only)
#
# HARDWARE STRATEGY (RTX 5070 = 8GB VRAM, 64GB RAM):
#   - gpu: Fits entirely in VRAM (≤8GB) → fastest
#   - hybrid-gpu: GPU primary, spills to RAM (8-16GB) → fast
#   - hybrid-cpu: CPU primary, uses GPU assist (16-32GB) → moderate
#   - cpu: Too large for GPU benefit (>32GB) → RAM only
#
# MEMORY ESTIMATES (Q4 quantization):
#   - 7B  → ~4GB    - 8B  → ~5GB    - 13B → ~8GB
#   - 14B → ~8GB    - 16B → ~9GB    - 32B → ~19GB
#   - 70B → ~42GB
LOCAL_MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {
    # === FABRIK AGENTS ===
    # Agent 1: The Lead Engineer (primary implementation)
    "fabrik-coder-qwen2.5-32b:latest": {
        "role": "coding",
        "priority": 1,
        "hardware": "hybrid-cpu",
        "context_window_k": 16,
        "has_vision": 0,
        "has_tools": 1,
        "is_agentic": 1,
        "is_reasoning": 1,
        "arena_elo": 1280,
        "notes": "~19GB: fills 8GB VRAM, spills 11GB to RAM. Lead Engineer for Fabrik implementation",
    },
    # Agent 2: The Senior Reviewer (reviews staged changes)
    "fabrik-reviewer-llama3.1-70b:latest": {
        "role": "reviewing",
        "priority": 1,
        "hardware": "cpu",
        "context_window_k": 32,
        "has_vision": 0,
        "has_tools": 1,
        "is_agentic": 1,
        "is_reasoning": 0,
        "arena_elo": 1290,
        "notes": "~42GB RAM only. Senior Reviewer for Fabrik - reports findings only",
    },
    # Agent 3: The Surgical Fixer (fixes only reported issues)
    "fabrik-fixer-deepseek-v2-16b:latest": {
        "role": "fixing",
        "priority": 1,
        "hardware": "hybrid-gpu",
        "context_window_k": 16,
        "has_vision": 0,
        "has_tools": 1,
        "is_agentic": 1,
        "is_reasoning": 1,
        "arena_elo": 1260,
        "notes": "~9GB: almost fits in VRAM, ~1GB spills to RAM. Surgical Fixer for reported issues only",
    },
    # Agent 4: The Documentator (updates docs at end of phase)
    "fabrik-docs-llama3.1-8b:latest": {
        "role": "documentation",
        "priority": 1,
        "hardware": "gpu",
        "context_window_k": 8,
        "has_vision": 0,
        "has_tools": 1,
        "is_agentic": 0,
        "is_reasoning": 1,
        "arena_elo": 1150,
        "notes": "~5GB: fits entirely in VRAM. Documentator for Fabrik - updates docs at phase end",
    },
}


def fetch_ollama_models() -> list[dict[str, Any]]:
    """Fetch installed models from Ollama API."""
    log("Fetching models from Ollama API...")
    try:
        req = urllib.request.Request(f"{OLLAMA_API}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            log(f"  Found {len(models)} local models")
            return models
    except urllib.error.URLError as e:
        log(f"  Ollama not running or unreachable: {e}")
        return []
    except Exception as e:
        log(f"  Error fetching Ollama models: {e}")
        return []


def parse_model_size(name: str, size_bytes: int) -> tuple[str, str, str]:
    """
    Parse model name to extract family, parameter size, and quantization.

    Examples:
        'qwen2.5-coder:32b' -> ('qwen2.5-coder', '32B', None)
        'llama3.1:70b-instruct-q4_K_M' -> ('llama3.1', '70B', 'Q4_K_M')
    """
    family = name.split(":")[0] if ":" in name else name

    # Extract parameter size from name
    param_size = None
    for part in name.lower().replace(":", "-").split("-"):
        if part.endswith("b") and part[:-1].replace(".", "").isdigit():
            param_size = part.upper()
            break

    # Estimate from size if not in name
    if not param_size and size_bytes:
        gb = size_bytes / (1024**3)
        if gb < 5:
            param_size = "~7B"
        elif gb < 10:
            param_size = "~13B"
        elif gb < 25:
            param_size = "~32B"
        elif gb < 50:
            param_size = "~70B"
        else:
            param_size = ">70B"

    # Extract quantization
    quant = None
    name_lower = name.lower()
    for q in ["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q8_0", "f16", "f32"]:
        if q in name_lower:
            quant = q.upper()
            break

    return family, param_size or "?", quant


def estimate_memory(param_size: str, quant: str | None) -> tuple[float, float]:
    """
    Estimate VRAM and RAM requirements based on model size.
    Returns (vram_gb, ram_gb).
    """
    # Parse numeric size
    size_str = param_size.replace("~", "").replace(">", "").replace("B", "").replace("b", "")
    try:
        params_b = float(size_str)
    except ValueError:
        return (4.0, 8.0)  # Default estimate

    # Base memory = params * 2 bytes (FP16) or params * 0.5 bytes (Q4)
    if quant and "Q4" in quant:
        base_gb = params_b * 0.5
    elif quant and "Q8" in quant:
        base_gb = params_b * 1.0
    else:
        base_gb = params_b * 2.0  # Assume FP16

    # Add overhead (~20%)
    total_gb = base_gb * 1.2

    # Models < 16B can fit in 12GB VRAM (RTX 5070)
    if params_b <= 16:
        return (total_gb, 0.0)
    else:
        return (0.0, total_gb)


def sync_from_ollama() -> None:
    """Sync local models from Ollama API."""
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            family TEXT,
            parameter_size TEXT,
            quantization TEXT,
            size_bytes INTEGER,
            hardware TEXT DEFAULT 'auto',
            vram_required_gb REAL,
            ram_required_gb REAL,
            assigned_role TEXT,
            role_priority INTEGER DEFAULT 1,
            context_window_k INTEGER DEFAULT 32,
            has_vision INTEGER DEFAULT 0,
            has_tools INTEGER DEFAULT 0,
            is_agentic INTEGER DEFAULT 0,
            is_reasoning INTEGER DEFAULT 0,
            arena_elo INTEGER,
            tbench_accuracy REAL,
            humaneval_score REAL,
            coding_score REAL,
            tokens_per_sec REAL,
            time_to_first_token_ms REAL,
            status TEXT DEFAULT 'available',
            last_used TIMESTAMP,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            digest TEXT,
            modified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add missing columns (migration for existing tables)
    columns_to_add = [
        ("has_vision", "INTEGER DEFAULT 0"),
        ("has_tools", "INTEGER DEFAULT 0"),
        ("is_agentic", "INTEGER DEFAULT 0"),
        ("is_reasoning", "INTEGER DEFAULT 0"),
        ("arena_elo", "INTEGER"),
        ("tbench_accuracy", "REAL"),
        ("humaneval_score", "REAL"),
        ("coding_score", "REAL"),
        ("time_to_first_token_ms", "REAL"),
    ]
    schema_changed = False
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE local_models ADD COLUMN {col_name} {col_type}")
            schema_changed = True
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()

    # Update documentation if schema changed
    if schema_changed:
        generate_schema_docs("local_models")

    # Fetch models from Ollama
    models = fetch_ollama_models()
    if not models:
        conn.close()
        return

    inserted = 0
    updated = 0

    for model in models:
        model_name = model.get("name", "")
        if not model_name:
            continue

        size_bytes = model.get("size", 0)
        digest = model.get("digest", "")
        modified_at = model.get("modified_at", "")

        # Parse model info
        family, param_size, quant = parse_model_size(model_name, size_bytes)
        vram_gb, ram_gb = estimate_memory(param_size, quant)

        # Get capabilities from config (or defaults)
        caps = LOCAL_MODEL_CAPABILITIES.get(model_name, {})
        assigned_role = caps.get("role")
        role_priority = caps.get("priority", 1)
        hardware = caps.get("hardware", "auto")
        context_window_k = caps.get("context_window_k", 32)
        has_vision = caps.get("has_vision", 0)
        has_tools = caps.get("has_tools", 0)
        is_agentic = caps.get("is_agentic", 0)
        is_reasoning = caps.get("is_reasoning", 0)
        arena_elo = caps.get("arena_elo")

        # Auto-assign hardware if not configured (RTX 5070 = 8GB VRAM)
        if hardware == "auto":
            if vram_gb > 0 and vram_gb <= 8:
                hardware = "gpu"  # Fits entirely in VRAM
            elif vram_gb > 8 and vram_gb <= 16:
                hardware = "hybrid-gpu"  # GPU primary, spills to RAM
            elif ram_gb > 0 and ram_gb <= 32:
                hardware = "hybrid-cpu"  # CPU primary, GPU assist
            else:
                hardware = "cpu"  # RAM only

        # Check if exists
        cursor.execute("SELECT id FROM local_models WHERE id = ?", (model_name,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                """
                UPDATE local_models SET
                    name = ?, family = ?, parameter_size = ?, quantization = ?,
                    size_bytes = ?, hardware = ?, vram_required_gb = ?, ram_required_gb = ?,
                    assigned_role = ?, role_priority = ?, context_window_k = ?,
                    has_vision = ?, has_tools = ?, is_agentic = ?, is_reasoning = ?,
                    arena_elo = ?,
                    status = 'available', digest = ?, modified_at = ?,
                    last_synced = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    model_name,
                    family,
                    param_size,
                    quant,
                    size_bytes,
                    hardware,
                    vram_gb if vram_gb > 0 else None,
                    ram_gb if ram_gb > 0 else None,
                    assigned_role,
                    role_priority,
                    context_window_k,
                    has_vision,
                    has_tools,
                    is_agentic,
                    is_reasoning,
                    arena_elo,
                    digest,
                    modified_at,
                    model_name,
                ),
            )
            updated += 1
        else:
            cursor.execute(
                """
                INSERT INTO local_models (
                    id, name, family, parameter_size, quantization, size_bytes,
                    hardware, vram_required_gb, ram_required_gb,
                    assigned_role, role_priority, context_window_k,
                    has_vision, has_tools, is_agentic, is_reasoning,
                    arena_elo,
                    digest, modified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_name,
                    model_name,
                    family,
                    param_size,
                    quant,
                    size_bytes,
                    hardware,
                    vram_gb if vram_gb > 0 else None,
                    ram_gb if ram_gb > 0 else None,
                    assigned_role,
                    role_priority,
                    context_window_k,
                    has_vision,
                    has_tools,
                    is_agentic,
                    is_reasoning,
                    arena_elo,
                    digest,
                    modified_at,
                ),
            )
            inserted += 1

    # Mark missing models
    installed_names = [m.get("name", "") for m in models]
    if installed_names:
        placeholders = ",".join("?" * len(installed_names))
        cursor.execute(
            f"UPDATE local_models SET status = 'missing' WHERE id NOT IN ({placeholders})",
            installed_names,
        )

    conn.commit()
    conn.close()
    log(f"  Inserted {inserted}, updated {updated} local models")


def export_local_models() -> None:
    """Export local models status to LOCAL_LLM_INFRASTRUCTURE.md."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='local_models'")
    if not cursor.fetchone():
        log("No local_models table found. Run 'ollama-sync' first.")
        conn.close()
        return

    cursor.execute(
        """
        SELECT * FROM local_models
        WHERE status = 'available'
        ORDER BY
            CASE assigned_role
                WHEN 'coding' THEN 1
                WHEN 'reviewing' THEN 2
                WHEN 'fixing' THEN 3
                WHEN 'documentation' THEN 4
                ELSE 5
            END,
            role_priority
        """
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        log("No local models found")
        return

    # Build auto-generated section
    section_lines = [
        "<!-- AUTO-GENERATED:LOCAL_MODELS_START -->",
        "## Installed Models (Auto-Generated)",
        "",
        f"**Last Synced:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| Model | Role | Hardware | Size | Context | Vision | Tools | Agentic | ELO | Code |",
        "|-------|------|----------|------|---------|--------|-------|---------|-----|------|",
    ]

    for row in rows:
        model_id = row["id"]
        role = row["assigned_role"] or "-"
        hardware = row["hardware"] or "auto"
        param_size = row["parameter_size"] or "?"
        ctx = f"{row['context_window_k']}K" if row["context_window_k"] else "-"
        vision = "✓" if row["has_vision"] else "-"
        tools = "✓" if row["has_tools"] else "-"
        agentic = "✓" if row["is_agentic"] else "-"
        elo = str(row["arena_elo"]) if row["arena_elo"] else "-"
        code = f"{row['coding_score']:.0f}" if row["coding_score"] else "-"
        section_lines.append(
            f"| `{model_id}` | {role} | {hardware} | {param_size} | {ctx} | {vision} | {tools} | {agentic} | {elo} | {code} |"
        )

    section_lines.append("")
    section_lines.append("<!-- AUTO-GENERATED:LOCAL_MODELS_END -->")

    # Update the file if it exists
    if LOCAL_LLM_DOC.exists():
        content = LOCAL_LLM_DOC.read_text()
        start_marker = "<!-- AUTO-GENERATED:LOCAL_MODELS_START -->"
        end_marker = "<!-- AUTO-GENERATED:LOCAL_MODELS_END -->"

        if start_marker in content and end_marker in content:
            # Replace existing section
            start_idx = content.index(start_marker)
            end_idx = content.index(end_marker) + len(end_marker)
            new_content = content[:start_idx] + "\n".join(section_lines) + content[end_idx:]
        else:
            # Append section at the end
            new_content = content.rstrip() + "\n\n" + "\n".join(section_lines) + "\n"

        LOCAL_LLM_DOC.write_text(new_content)
        log(f"Updated {LOCAL_LLM_DOC} with {len(rows)} models")
    else:
        # Print to stdout if file doesn't exist
        log(f"File not found: {LOCAL_LLM_DOC}")
        log("Printing to stdout instead:")
        for line in section_lines:
            print(line)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]
    force = "--force" in sys.argv

    if command == "init":
        init_db(force)
    elif command == "sync":
        if not DB_PATH.exists():
            init_db()
        sync_from_kilo()
    elif command == "update":
        if not DB_PATH.exists():
            log("Database not found. Run 'init' first.")
            return 1
        update_benchmarks()
    elif command == "snapshot":
        if not DB_PATH.exists():
            log("Database not found. Run 'init' first.")
            return 1
        create_snapshot()
    elif command == "export":
        if not DB_PATH.exists():
            log("Database not found. Run 'init' first.")
            return 1
        export_markdown()
    elif command == "ollama-sync":
        if not DB_PATH.exists():
            init_db()
        sync_from_ollama()
    elif command == "ollama-status":
        export_local_models()
    elif command == "schema-docs":
        # Generate schema documentation
        generate_schema_docs("agents")
        generate_schema_docs("local_models")
    elif command == "all":
        # Full pipeline (Kilo CLI + local Ollama agents)
        init_db(force)
        sync_from_kilo()
        update_benchmarks()
        sync_from_ollama()
        create_snapshot()
        export_markdown()
        export_local_models()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1

    return 0


def generate_schema_docs(table_name: str) -> None:
    """Generate markdown table documentation from actual database schema."""
    from pathlib import Path

    conn = get_connection()
    cursor = conn.cursor()

    # Get real schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    # Group columns by category
    categories = {
        "Identity": ["id", "api_id", "name", "provider", "family"],
        "Pricing": ["input_cost_per_m", "output_cost_per_m"],
        "Model Specs": ["parameter_size", "quantization", "size_bytes"],
        "Hardware Requirements": ["hardware", "vram_required_gb", "ram_required_gb"],
        "Performance": ["tokens_per_sec", "time_to_first_token_ms"],
        "Role Assignment": ["assigned_role", "role_priority"],
        "Capabilities": [
            "context_window_k",
            "has_vision",
            "has_tools",
            "is_agentic",
            "is_reasoning",
        ],
        "Benchmarks": ["arena_elo", "tbench_accuracy"],
        "Derived Metrics": ["task_tier", "perf_per_dollar"],
        "Status": ["status", "discard_reason", "blocked", "block_reason"],
        "Metadata": [
            "fallback_model_id",
            "last_verified",
            "variant",
            "created_at",
            "updated_at",
            "last_used",
            "last_synced",
            "digest",
            "modified_at",
        ],
    }

    # Build markdown table
    lines = []
    current_cat = None
    for col in columns:
        cid, name, col_type, not_null, default, pk = col

        # Find category
        cat = "Other"
        for category, cols in categories.items():
            if name in cols:
                cat = category
                break

        # Add category header
        if cat != current_cat:
            lines.append(f"| **{cat}** | | | |")
            lines.append("|--------|------|---------|-------------|")
            current_cat = cat

        # Format row
        pk_str = "PRIMARY KEY" if pk else ""
        default_str = str(default) if default is not None else ""

        lines.append(f"| {name} | {col_type} | {default_str} | {pk_str} |")

    markdown = "\n".join(lines)

    # Update appropriate file
    if table_name == "agents":
        update_file = Path("/opt/fabrik/docs/workflows/KILO_AGENT_MANAGEMENT.md")
        marker_start = "<!-- AUTO-GENERATED:SCHEMA_AGENTS_START -->"
        marker_end = "<!-- AUTO-GENERATED:SCHEMA_AGENTS_END -->"
    elif table_name == "local_models":
        update_file = Path("/opt/fabrik/docs/reference/LOCAL_LLM_INFRASTRUCTURE.md")
        marker_start = "<!-- AUTO-GENERATED:SCHEMA_LOCAL_START -->"
        marker_end = "<!-- AUTO-GENERATED:SCHEMA_LOCAL_END -->"
    else:
        log(f"  Unknown table for schema docs: {table_name}")
        return

    if not update_file.exists():
        log(f"  Documentation file not found: {update_file}")
        return

    # Read and update file
    content = update_file.read_text()
    if marker_start in content and marker_end in content:
        start_idx = content.index(marker_start)
        end_idx = content.index(marker_end) + len(marker_end)
        new_content = (
            content[:start_idx]
            + f"\n{marker_start}\n\n| Column | Type | Default | Description |\n|--------|------|---------|-------------|\n{markdown}\n\n{marker_end}"
            + content[end_idx:]
        )
        update_file.write_text(new_content)
        log(f"  Updated schema documentation for {table_name}")
    else:
        log(f"  Schema markers not found in {update_file}")

    conn.close()


if __name__ == "__main__":
    sys.exit(main())
