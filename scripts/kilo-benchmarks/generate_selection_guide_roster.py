#!/usr/bin/env python3
"""
Regenerate the "Current Roster" section of KILO_AGENT_SELECTION_GUIDE.md
from live data (assignments.json + kilo_agents.db).

Called after compute_assignments.py in the pipeline. Preserves all
stable content (philosophy, tradeoffs, overrides) and only rewrites
the volatile roster block between markers.

Usage:
    python scripts/kilo-benchmarks/generate_selection_guide_roster.py
"""

import json
import sqlite3
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FABRIK_DIR = SCRIPT_DIR.parent.parent
GUIDE_FILE = FABRIK_DIR / "docs" / "reference" / "kilo" / "KILO_AGENT_SELECTION_GUIDE.md"
ASSIGNMENTS_FILE = SCRIPT_DIR / "assignments.json"
DB_FILE = SCRIPT_DIR / "kilo_agents.db"
ROLE_CONFIGS_FILE = SCRIPT_DIR / "role_configs.yaml"

# Markers in the guide file
START_MARKER = "<!-- ROSTER:START (auto-generated — do not edit below this line) -->"
END_MARKER = "<!-- ROSTER:END -->"


def load_assignments() -> list[dict]:
    with open(ASSIGNMENTS_FILE) as f:
        data = json.load(f)
    return data.get("assignments", [])


def load_agent_data(agent_ids: list[str]) -> dict[str, dict]:
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    agents = {}
    for aid in agent_ids:
        row = db.execute("SELECT * FROM agents WHERE id = ?", (aid,)).fetchone()
        if row:
            agents[aid] = dict(row)
    db.close()
    return agents


def load_role_floors() -> dict[str, dict]:
    """Parse role_configs.yaml for floor values (simple YAML parsing, no dependency)."""
    floors = {}
    current_role = None
    try:
        with open(ROLE_CONFIGS_FILE) as f:
            for line in f:
                stripped = line.strip()
                # Detect role name (indented exactly 2 spaces under 'roles:')
                if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                    current_role = stripped.rstrip(":")
                    floors[current_role] = {}
                elif current_role and line.startswith("    ") and ":" in stripped:
                    key, _, val = stripped.partition(":")
                    key = key.strip()
                    val = val.strip().split("#")[0].strip()  # remove comments
                    if key in ("quality_floor", "speed_floor", "cost_cap", "primary_metric"):
                        floors[current_role][key] = val
    except FileNotFoundError:
        pass
    return floors


def format_cost(cost_per_m: float) -> str:
    if cost_per_m <= 0:
        return "free"
    if cost_per_m < 0.1:
        return f"~${cost_per_m:.3f}/M"
    if cost_per_m < 10:
        return f"~${cost_per_m:.2f}/M"
    return f"~${cost_per_m:.0f}/M"


def short_name(agent_id: str) -> str:
    """anthropic/claude-opus-4.6 → Claude Opus 4.6"""
    _, _, name = agent_id.rpartition("/")
    return name.replace("-", " ").title()


# Agent scripts on disk
def load_disk_agents() -> dict[str, str]:
    """Map role prefix → list of model descriptions from actual agent scripts."""
    agents_dir = Path.home() / ".traycer" / "cli-agents"
    result = {}
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*.sh")):
            result[f.name] = str(f)
    return result


def generate_roster() -> str:
    assignments = load_assignments()
    if not assignments:
        return "*No assignments found. Run `compute_assignments.py` first.*\n"

    all_ids = list({a["agent_id"] for a in assignments})
    agents = load_agent_data(all_ids)
    floors = load_role_floors()

    # Group by role
    roles: dict[str, list[dict]] = {}
    for a in assignments:
        role = a["role"]
        if role not in roles:
            roles[role] = []
        roles[role].append(a)

    role_descriptions = {
        "coding": "General coding — routed here when ticket isn't classified yet",
        "coding_simple": "Fast, cheap, routine — single-file changes, renames, boilerplate",
        "coding_complex": "Multi-file, architectural, complex logic — the hard stuff",
        "fixing": "Bug fixes, error resolution, debugging",
        "reviewing": "Code review — find bugs, security issues, design problems",
        "documentation": "Docs, READMEs, changelogs — writing, not reasoning",
        "testing": "Test generation, coverage analysis",
    }

    lines = []
    lines.append(f"*Auto-generated on {date.today()} from `assignments.json` + `kilo_agents.db`.*\n")

    for role, assigns in roles.items():
        desc = role_descriptions.get(role, "")
        lines.append(f"### {role}{' — ' + desc if desc else ''}\n")

        # Floor info
        if role in floors:
            fl = floors[role]
            floor_parts = []
            if "primary_metric" in fl:
                pm = fl["primary_metric"]
                qf = fl.get("quality_floor", "?")
                floor_parts.append(f"{pm} ≥ {qf}")
            if "speed_floor" in fl:
                floor_parts.append(f"speed ≥ {fl['speed_floor']} tok/s")
            if "cost_cap" in fl and fl["cost_cap"] != "null":
                floor_parts.append(f"cost cap ${fl['cost_cap']}/M")
            if floor_parts:
                lines.append(f"**Floor:** {', '.join(floor_parts)}\n")

        lines.append("| Priority | Model | ELO | TBench | Cost (in/out per M) | Reason |")
        lines.append("|---|---|---|---|---|---|")

        for a in sorted(assigns, key=lambda x: x.get("priority", 99)):
            aid = a["agent_id"]
            agent = agents.get(aid, {})
            elo = agent.get("arena_elo") or "—"
            tbench = agent.get("tbench_accuracy")
            tbench_str = f"{tbench:.1f}" if tbench else "—"
            in_cost = format_cost(agent.get("input_cost_per_m", 0))
            out_cost = format_cost(agent.get("output_cost_per_m", 0))
            reason = a.get("reason", "")[:80]
            lines.append(
                f"| P{a.get('priority', '?')} | **{short_name(aid)}** | {elo} | {tbench_str} | {in_cost} / {out_cost} | {reason} |"
            )

        lines.append("")

    return "\n".join(lines)


def update_guide():
    if not GUIDE_FILE.exists():
        print(f"Guide file not found: {GUIDE_FILE}")
        return

    content = GUIDE_FILE.read_text()

    if START_MARKER not in content or END_MARKER not in content:
        print(f"Markers not found in {GUIDE_FILE}. Add these lines:")
        print(f"  {START_MARKER}")
        print(f"  {END_MARKER}")
        return

    roster = generate_roster()

    before = content[: content.index(START_MARKER) + len(START_MARKER)]
    after = content[content.index(END_MARKER) :]

    new_content = before + "\n\n" + roster + "\n" + after
    GUIDE_FILE.write_text(new_content)
    print(f"Updated roster in {GUIDE_FILE}")


if __name__ == "__main__":
    update_guide()
