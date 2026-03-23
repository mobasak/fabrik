#!/usr/bin/env python3
"""
Kilo Agents SQLite Database Manager.

Manages agent data with historical tracking:
- Syncs data from Kilo CLI (full metadata)
- Updates benchmark scores from scrapers
- Maintains daily historical snapshots
- Computes derived metrics (perf_per_dollar, task_tier)

Usage:
    python scripts/kilo_agents_db.py init          # Create/reset database
    python scripts/kilo_agents_db.py sync          # Sync from Kilo CLI
    python scripts/kilo_agents_db.py update        # Update benchmarks
    python scripts/kilo_agents_db.py snapshot      # Create daily snapshot
    python scripts/kilo_agents_db.py export        # Export to markdown
"""

import json
import sqlite3
import subprocess
import sys
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
    models = fetch_kilo_models()
    if not models:
        log("No models to sync")
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
    from scrape_benchmarks import scrape_chatbot_arena, scrape_terminal_bench

    log("Updating benchmark scores...")

    arena = scrape_chatbot_arena()
    tbench = scrape_terminal_bench()

    conn = get_connection()
    cursor = conn.cursor()

    # Build lookup maps (normalize names for matching)
    def normalize(name: str) -> str:
        """Normalize model name for matching."""
        n = name.lower().replace(" ", "-").replace("_", "-")
        # Remove common suffixes that vary between sources
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

    arena_map = {}
    for entry in arena:
        for key in get_match_keys(entry.model):
            arena_map[key] = int(entry.score)

    tbench_map = {}
    for entry in tbench:
        for key in get_match_keys(entry.model):
            tbench_map[key] = entry.score

    # Update agents
    cursor.execute("SELECT id, name FROM agents")
    agents = cursor.fetchall()

    elo_updated = 0
    tbench_updated = 0

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

        if elo is not None or accuracy is not None:
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
    log(f"  Updated {elo_updated} Elo, {tbench_updated} TBench scores")


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
    elif command == "all":
        # Full pipeline
        init_db(force)
        sync_from_kilo()
        update_benchmarks()
        create_snapshot()
        export_markdown()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
