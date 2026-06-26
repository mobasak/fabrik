#!/usr/bin/env python3
"""
Update the embedding sections inside the EXISTING chat-side markdown files:

  - docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md
        Replace content between EMBEDDING_ROSTER:START / END markers with
        today's winners per role.
  - docs/reference/kilo/KILO_MODEL_CAPABILITIES.md
        Replace content between EMBEDDING_CATALOG:START / END markers with
        the full embedding models catalog.

Marker-based partial update (same pattern as `generate_selection_guide_roster.py`).
The rest of each file (chat roster, philosophy, tradeoffs, provider tables) is
preserved unchanged.

Runs after `embedding_role_mapper.py` in `wsl_startup_hook.sh`. Reads
`embedding_roles` (live winners) + `embedding_models` (catalog) + the role
configs YAML. No network, no LLM.

Usage:
    python scripts/kilo-benchmarks/embedding_export_markdown.py
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).parent
FABRIK_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CONFIG_PATH = SCRIPT_DIR / "embedding_role_configs.yaml"

DOCS_DIR = FABRIK_ROOT / "docs" / "reference" / "kilo"
SELECTION_GUIDE_PATH = DOCS_DIR / "KILO_AGENT_SELECTION_GUIDE.md"
CAPABILITIES_PATH = DOCS_DIR / "KILO_MODEL_CAPABILITIES.md"
RAG_SEARCH_PATH = FABRIK_ROOT / ".windsurf" / "rules" / "core" / "65-rag-search.md"

ROSTER_START = "<!-- EMBEDDING_ROSTER:START"
ROSTER_END = "<!-- EMBEDDING_ROSTER:END -->"
CATALOG_START = "<!-- EMBEDDING_CATALOG:START"
CATALOG_END = "<!-- EMBEDDING_CATALOG:END -->"
WINNERS_START = "<!-- EMBEDDING_WINNERS:START"
WINNERS_END = "<!-- EMBEDDING_WINNERS:END -->"


def _utc_today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def _fmt_cost(cost: float) -> str:
    """Render input cost in $/M tokens. Sentinel pricing → '?' so a
    broken row is visible in the docs instead of silently rendering '$0'."""
    if cost is None or cost < 0:
        return "?"
    if cost == 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}/M"
    return f"${cost:.2f}/M"


def _fmt_dim(dim: int | None) -> str:
    return f"{dim:,}" if dim else "—"


def _fmt_bool_flag(value: int) -> str:
    return "✓" if value else "—"


def _fmt_tier(tier: int) -> str:
    return {1: "1 (bulk)", 2: "2 (mid)", 3: "3 (frontier)"}.get(tier, str(tier))


# ─── Selection guide ───────────────────────────────────────────────────────


def _render_role_section(role: str, role_cfg: dict[str, Any], rows: list[sqlite3.Row]) -> str:
    floors = []
    if role_cfg.get("min_quality_tier", 1) > 1:
        floors.append(f"`quality_tier ≥ {role_cfg['min_quality_tier']}`")
    if role_cfg.get("min_context_window_k", 1) > 1:
        floors.append(f"`context_window_k ≥ {role_cfg['min_context_window_k']}k`")
    if role_cfg.get("require_multilingual"):
        floors.append("`is_multilingual = true`")
    if role_cfg.get("require_code_tuned"):
        floors.append("`is_code_tuned = true`")
    if not role_cfg.get("allow_free", False):
        floors.append("free-tier excluded")
    if role_cfg.get("stability_required", True):
        floors.append("GA only (no preview / beta / experimental)")

    floor_line = ", ".join(floors) if floors else "(no floors)"

    # YAML block-scalar `notes` can span multiple lines. Collapse all
    # whitespace to single spaces, then take the first sentence as the
    # role's one-line description.
    notes = " ".join((role_cfg.get("notes") or "").split())
    desc = notes.split(". ")[0].rstrip(".") if notes else ""

    lines = [
        f"### {role} — {desc}" if desc else f"### {role}",
        "",
        f"**Slots:** {role_cfg.get('slots', 1)}  ·  **Floors:** {floor_line}",
        "",
    ]

    if not rows:
        lines.append("> ⚠️  No eligible model satisfies these floors today.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Priority | Model | Provider | Cost (input/M) | Context | Dimensions | Tier | Multilingual | Code-tuned |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for r in rows:
        lines.append(
            "| P{prio} | `{id}` | {provider} | {cost} | {ctx}k | {dim} | {tier} | {ml} | {code} |".format(
                prio=r["priority"],
                id=r["model_id"],
                provider=r["provider"],
                cost=_fmt_cost(r["input_cost_per_m"]),
                ctx=r["context_window_k"],
                dim=_fmt_dim(r["dimensions"]),
                tier=_fmt_tier(r["quality_tier"]),
                ml=_fmt_bool_flag(r["is_multilingual"]),
                code=_fmt_bool_flag(r["is_code_tuned"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _render_roster_block(
    role_configs: dict[str, dict[str, Any]],
    winners_by_role: dict[str, list[sqlite3.Row]],
) -> str:
    """Body that goes between EMBEDDING_ROSTER:START and EMBEDDING_ROSTER:END.
    Excludes the markers themselves — those are owned by the host file."""
    today = _utc_today_iso()
    out: list[str] = [
        f"*Auto-generated on {today} (UTC) from `embedding_roles` + "
        "`embedding_role_configs.yaml`. Edits between the markers will be "
        "overwritten on the next daily run.*",
        "",
        "**Selection algorithm** (see `embedding_selector.select_for_role`): "
        "apply hard floors, sort survivors by `input_cost_per_m ASC`, "
        "`quality_tier DESC`, `context_window_k DESC`, `id ASC`, take top-N "
        "where N = `slots`. Pinned winners also persisted in `embedding_roles` "
        "(SQLite), `embedding_assignments.json`, `kilo_embeddings_final.json` "
        "(Traycer), and `embedding_roles_history` (one snapshot per UTC day).",
        "",
    ]
    for role_name, role_cfg in role_configs.items():
        rows = winners_by_role.get(role_name, [])
        out.append(_render_role_section(role_name, role_cfg, rows))
    return "\n".join(out)


# ─── Capabilities catalog ──────────────────────────────────────────────────


def _render_catalog_block(rows: list[sqlite3.Row]) -> str:
    """Body that goes between EMBEDDING_CATALOG:START and EMBEDDING_CATALOG:END."""
    today = _utc_today_iso()
    out: list[str] = [
        f"*Auto-generated on {today} (UTC) from the `embedding_models` table. "
        f"Sorted by `input_cost_per_m ASC, id ASC`. **Total: {len(rows)} models.***",
        "",
        "| Provider | Model | Cost (input/M) | Context | Dimensions | Tier | Multilingual | Code-tuned | GA | Status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            "| {provider} | `{id}` | {cost} | {ctx}k | {dim} | {tier} | {ml} | {code} | {ga} | {status} |".format(
                provider=r["provider"],
                id=r["id"],
                cost=_fmt_cost(r["input_cost_per_m"]),
                ctx=r["context_window_k"],
                dim=_fmt_dim(r["dimensions"]),
                tier=_fmt_tier(r["quality_tier"]),
                ml=_fmt_bool_flag(r["is_multilingual"]),
                code=_fmt_bool_flag(r["is_code_tuned"]),
                ga=_fmt_bool_flag(r["is_ga"]),
                status=r["status"] if not r["blocked"] else f"blocked: {r['block_reason'] or ''}",
            )
        )
    out.extend(
        [
            "",
            "**Legend.** *Tier* = cost-proxy quality tier (1=bulk, 2=mid, 3=frontier; "
            "replace with MIRACL/MTEB-derived score once benchmark scrapers ship). "
            "*Context* in thousands of tokens. *Dimensions* dash = OpenRouter doesn't "
            "advertise it (backfillable). *Multilingual / Code-tuned / GA* = auto-derived "
            "from id substrings (see `embedding_models_db.py`).",
        ]
    )
    return "\n".join(out)


def _replace_between_markers(
    file_path: Path, start_marker: str, end_marker: str, new_body: str
) -> bool:
    """Replace the content between (but not including) the marker lines.

    Self-healing: if the markers are absent, append a fresh section with
    markers + body at the end of the file rather than crashing. The
    chat-pipeline regenerates `KILO_MODEL_CAPABILITIES.md` and
    `KILO_AGENT_SELECTION_GUIDE.md` wholesale, which drops these embedding
    markers; without self-heal, this script would fail every daily run
    after a chat-pipeline refresh.

    Returns True if the file was modified, False if it was already up to date.
    """
    text = file_path.read_text()
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        # Markers absent (or out of order) — append a fresh section. The chat
        # generators don't know about embedding markers, so we re-seed them here.
        prefix = "" if text.endswith("\n") else "\n"
        full_start = f"{start_marker} (auto-managed by embedding_export_markdown.py) -->"
        section = f"{prefix}\n{full_start}\n{new_body.rstrip(chr(10))}\n{end_marker}\n"
        file_path.write_text(text + section)
        print(f"[embedding_export_markdown] re-seeded {start_marker} block in {file_path}")
        return True

    line_end = text.find("\n", start_idx)
    if line_end == -1:
        raise RuntimeError(f"malformed start marker line in {file_path}")
    head = text[: line_end + 1]
    tail = text[end_idx:]
    new_text = head + new_body.rstrip("\n") + "\n" + tail
    if new_text == text:
        return False
    file_path.write_text(new_text)
    return True


# ─── Main ──────────────────────────────────────────────────────────────────


def run(db_path: Path | str = DB_PATH) -> dict[str, Path]:
    """Update embedding sections inside the existing chat-side markdown files.
    Returns the paths touched."""
    role_configs = yaml.safe_load(CONFIG_PATH.read_text())["roles"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        winners_rows = conn.execute(
            """
            SELECT r.role, r.priority, r.model_id, r.score_used,
                   m.provider, m.input_cost_per_m, m.context_window_k,
                   m.dimensions, m.quality_tier, m.is_multilingual, m.is_code_tuned
            FROM embedding_roles r
            JOIN embedding_models m ON m.id = r.model_id
            ORDER BY r.role, r.priority
            """
        ).fetchall()
        catalog_rows = conn.execute(
            "SELECT * FROM embedding_models ORDER BY input_cost_per_m ASC, id ASC"
        ).fetchall()
    finally:
        conn.close()

    winners_by_role: dict[str, list[sqlite3.Row]] = {}
    for r in winners_rows:
        winners_by_role.setdefault(r["role"], []).append(r)

    roster_body = _render_roster_block(role_configs, winners_by_role)
    catalog_body = _render_catalog_block(catalog_rows)

    _replace_between_markers(SELECTION_GUIDE_PATH, ROSTER_START, ROSTER_END, roster_body)
    _replace_between_markers(CAPABILITIES_PATH, CATALOG_START, CATALOG_END, catalog_body)

    # Also inject compact winners table into the RAG search rule pack
    if RAG_SEARCH_PATH.exists():
        role_labels = {
            "multilingual_primary": (
                "Default (TR+EN)",
                "Most projects — use ONE model for BOTH ingest and query",
            ),
            "frontier_reference": (
                "Premium quality",
                "Separate pipeline — only when max recall needed AND budget allows full re-embed",
            ),
            "code_embedding": (
                "Code-specific",
                "Separate pipeline — IDE semantic search, codebase retrieval",
            ),
        }
        lines = [
            "| Role | Use when | Model | Cost | Context |",
            "|---|---|---|---|---|",
        ]
        for role, rows in winners_by_role.items():
            label, use_when = role_labels.get(role, (role, ""))
            for i, r in enumerate(rows):
                role_col = f"**{label}**" if i == 0 else f"**{label} fallback**"
                lines.append(
                    f"| {role_col} | {use_when if i == 0 else 'Fallback if P1 unavailable'} "
                    f"| `{r['model_id']}` | ${r['input_cost_per_m']}/M | {r['context_window_k']}k |"
                )
        winners_body = "\n".join(lines)
        _replace_between_markers(RAG_SEARCH_PATH, WINNERS_START, WINNERS_END, winners_body)
        print(f"[embedding_export_markdown] updated {RAG_SEARCH_PATH}")

    print(f"[embedding_export_markdown] updated {SELECTION_GUIDE_PATH}")
    print(f"[embedding_export_markdown] updated {CAPABILITIES_PATH}")
    return {
        "selection_guide": SELECTION_GUIDE_PATH,
        "capabilities": CAPABILITIES_PATH,
        "rag_search": RAG_SEARCH_PATH,
    }


if __name__ == "__main__":
    run()
    sys.exit(0)
