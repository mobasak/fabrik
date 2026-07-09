#!/usr/bin/env python3
"""Inject GATEWAY_COUNTS marker blocks into the 7 LLM-bearing
`.windsurf/rules/ai/NN-*.md` packs with live counts from `kilo_agents.db`.

Why a sibling to `category_export_markdown.py`:
  - That script owns the OPENROUTER_ROUTES marker pair (per-category P1/P2/P3
    fallback chain) + the `Last content verification:` stamp. Its self-heal
    logic carries strong invariants (Pass A-12 fixes vs. orphan markers, prose
    mentions, BOM frontmatter, etc.) and we don't want to risk regressing it.
  - GATEWAY_COUNTS is a parallel, independent concern: aggregate counts of
    routable models by gateway (Kilo CLI / OpenRouter / DashScope / SiliconFlow / ModelScope)
    per category, so the rules text never quotes a stale "Kilo has 235 models"
    number while the catalog drifts.
  - Both run in `daily_refresh.sh`. This script runs AFTER
    `category_export_markdown.py` so the per-pack `Last content verification:`
    stamp it leaves is already today.

Self-heal contract (mirrors the OR-routes marker, simpler because this block
has no body that operators might author):
  - Valid START/END pair → REPLACE in place.
  - Missing / orphaned markers → STRIP every dangling marker line, APPEND
    a fresh block at EOF.
  - Atomic single `write_text` per pack — never partial.

Counts are scoped to `status='active'` and to the per-category capability
columns (`has_reasoning`, `has_vision`, `is_translation_capable`, etc.).
Master pack 00 carries the aggregate table.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FABRIK_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
RULES_DIR = FABRIK_ROOT / ".windsurf" / "rules" / "ai"

MARKER_START_TEMPLATE = (
    "<!-- GATEWAY_COUNTS:START — last-refreshed: {date} "
    "(auto-managed by update_gateway_counts.py) -->"
)
MARKER_START_PREFIX = "<!-- GATEWAY_COUNTS:START"
MARKER_END = "<!-- GATEWAY_COUNTS:END -->"

REAL_START_RE = re.compile(
    rf"^[^\S\n]*{re.escape(MARKER_START_PREFIX)}[^\n]*?-->",
    re.MULTILINE,
)
REAL_END_RE = re.compile(
    rf"^[^\S\n]*{re.escape(MARKER_END)}[^\n]*?$",
    re.MULTILINE,
)
ORPHAN_START_LINE_RE = re.compile(
    rf"^[^\S\n]*{re.escape(MARKER_START_PREFIX)}[^\n]*?-->\n?",
    re.MULTILINE,
)
ORPHAN_END_LINE_RE = re.compile(
    rf"^[^\S\n]*{re.escape(MARKER_END)}[^\n]*?$\n?",
    re.MULTILINE,
)


def _log(msg: str) -> None:
    print(f"[update_gateway_counts] {msg}")


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def query_counts(db_path: Path) -> dict[str, int | dict[str, int]]:
    """Return per-gateway and per-capability counts from `agents`. Only
    `status='active'` rows count — deprecated models are not routable."""
    conn = sqlite3.connect(db_path)
    try:

        def n(sql: str) -> int:
            return int(conn.execute(sql).fetchone()[0])

        out: dict[str, int | dict[str, int]] = {
            "or_total": n("SELECT count(*) FROM agents WHERE via_openrouter=1 AND status='active'"),
            "kilo_total": n("SELECT count(*) FROM agents WHERE via_kilo=1 AND status='active'"),
            "or_kilo_both": n(
                "SELECT count(*) FROM agents WHERE via_openrouter=1 AND via_kilo=1 AND status='active'"
            ),
            "or_only": n(
                "SELECT count(*) FROM agents WHERE via_openrouter=1 AND (via_kilo IS NULL OR via_kilo=0) AND status='active'"
            ),
            "kilo_only": n(
                "SELECT count(*) FROM agents WHERE via_kilo=1 AND (via_openrouter IS NULL OR via_openrouter=0) AND status='active'"
            ),
            "dashscope": n("SELECT count(*) FROM agents WHERE via_dashscope=1 AND status='active'"),
            "siliconflow": n(
                "SELECT count(*) FROM agents WHERE via_siliconflow=1 AND status='active'"
            ),
            "modelscope": n(
                "SELECT count(*) FROM agents WHERE via_modelscope=1 AND status='active'"
            ),
            "with_vision": n("SELECT count(*) FROM agents WHERE has_vision=1 AND status='active'"),
            "with_tools": n("SELECT count(*) FROM agents WHERE has_tools=1 AND status='active'"),
            "with_reasoning": n(
                "SELECT count(*) FROM agents WHERE has_reasoning=1 AND status='active'"
            ),
            "with_translation": n(
                "SELECT count(*) FROM agents WHERE is_translation_capable=1 AND status='active'"
            ),
            "with_stt": n("SELECT count(*) FROM agents WHERE is_stt_capable=1 AND status='active'"),
        }
        # Per-category counts driven by agent_categories (when present)
        cats: dict[str, int] = {}
        rows = conn.execute(
            "SELECT c.category, count(DISTINCT a.id) FROM agent_categories c "
            "JOIN agents a ON a.id = c.agent_id "
            "WHERE a.status = 'active' GROUP BY c.category"
        ).fetchall()
        for cat, cnt in rows:
            cats[cat] = int(cnt)
        out["categories"] = cats
        return out
    finally:
        conn.close()


def _kv(label: str, n: int) -> str:
    return f"{label}: **{n:,}**"


def render_block(category: str, counts: dict, today: str) -> str:
    """Per-pack rendering. Each pack gets a category-scoped block."""
    cats = counts.get("categories", {}) or {}
    or_total = counts["or_total"]
    kilo_total = counts["kilo_total"]
    both = counts["or_kilo_both"]
    or_only = counts["or_only"]
    kilo_only = counts["kilo_only"]
    ds = counts["dashscope"]
    sf = counts["siliconflow"]
    ms = counts["modelscope"]

    lines = [
        f"*Live gateway counts (active models, {today} UTC; auto-refreshed from `kilo_agents.db`):*",
        "",
    ]

    if category == "master":
        lines.append("| Gateway | Active routable models | Notes |")
        lines.append("|---|---|---|")
        lines.append(
            f"| **OpenRouter** | {or_total:,} | of which **{both:,}** dual-routed with Kilo, **{or_only:,}** OR-only |"
        )
        lines.append(
            f"| **Kilo CLI** | {kilo_total:,} | of which **{both:,}** dual-routed with OR, **{kilo_only:,}** Kilo-only |"
        )
        lines.append(
            f"| **DashScope** (direct) | {ds:,} | specialist routes (e.g. `qwen-mt-turbo`) |"
        )
        lines.append(f"| **SiliconFlow** (direct) | {sf:,} | specialist routes (e.g. Hunyuan) |")
        lines.append(
            f"| **ModelScope** (direct) | {ms:,} | Zhipu GLM direct + Tencent Hunyuan Hy3 + Xiaomi MiMo + Qwen/DeepSeek/MiniMax/Kimi overlap |"
        )
        lines.append("")
        lines.append(
            "Capability counts (any-gateway): "
            f"reasoning **{counts['with_reasoning']:,}** · "
            f"tools/function-calling **{counts['with_tools']:,}** · "
            f"vision-input **{counts['with_vision']:,}** · "
            f"translation-scored **{counts['with_translation']:,}** · "
            f"STT-capable **{counts['with_stt']:,}**."
        )
        return "\n".join(lines)

    if category == "speech-audio":
        lines.append(_kv("STT-capable across all gateways", counts["with_stt"]))
        lines.append("")
        lines.append(
            "Direct-vendor specialists (Soniox, Whisper API, gpt-4o-transcribe, Deepgram) are NOT in this DB — they live in their own `stt_quality` JSON and the bake-off browser's Audio/Vision tab. Gateway LLMs are last-resort."
        )
        return "\n".join(lines)

    if category == "vision":
        lines.append(_kv("vision-input across all gateways", counts["with_vision"]))
        lines.append("")
        lines.append(
            "These are vision *understanding* models. Image *generation* (Recraft / FLUX) is not gateway-routed."
        )
        return "\n".join(lines)

    if category == "language":
        n_lang = cats.get("language", 0)
        lines.append(_kv("language-tagged (any gateway)", n_lang))
        lines.append(_kv("translation-scored (any gateway)", counts["with_translation"]))
        lines.append("")
        lines.append(
            "Sweet-spot dedicated MT: `qwen-mt-turbo` via DashScope (top-3 on FR/PT/DE/ID/AR, weaker on HU/RO/UR/KO; see the Translation tab in the bake-off browser)."
        )
        return "\n".join(lines)

    if category == "multimodal":
        lines.append(_kv("vision-input across all gateways", counts["with_vision"]))
        lines.append("")
        lines.append(
            "Multimodal overlaps with Vision (category 2) — see the Audio/Vision tab in the bake-off browser for the audio-in subset."
        )
        return "\n".join(lines)

    if category == "agentic":
        lines.append(_kv("reasoning-capable across all gateways", counts["with_reasoning"]))
        lines.append(_kv("tool/function-calling across all gateways", counts["with_tools"]))
        lines.append("")
        lines.append(
            "All major frontier reasoning models (o3, Claude reasoning, Gemini 3.x thinking, GLM-5.2) are on both Kilo and OpenRouter — pick the cheaper rate per model."
        )
        return "\n".join(lines)

    if category == "code":
        n_code = cats.get("code", 0)
        lines.append(_kv("code-tagged across all gateways", n_code))
        lines.append("")
        lines.append(
            "See the Coding tab in the bake-off browser; sort by Best Code descending to compare SWE-bench + Aider + DA-code signals per row."
        )
        return "\n".join(lines)

    return ""


def replace_block(text: str, body: str, today: str) -> tuple[str, str]:
    """Self-heal marker block injection. Returns (new_text, action).
    action ∈ {"noop", "replaced", "seeded"}."""
    new_start_line = MARKER_START_TEMPLATE.format(date=today)
    full_block = f"{new_start_line}\n{body.rstrip()}\n{MARKER_END}"

    start_m = REAL_START_RE.search(text)
    end_m = REAL_END_RE.search(text, start_m.end()) if start_m else None

    if start_m and end_m and end_m.start() > start_m.start():
        head = text[: start_m.start()]
        end_line_end = text.find("\n", end_m.start())
        tail = "" if end_line_end == -1 else text[end_line_end + 1 :]
        head = ORPHAN_START_LINE_RE.sub("", head)
        head = ORPHAN_END_LINE_RE.sub("", head)
        tail = ORPHAN_START_LINE_RE.sub("", tail)
        tail = ORPHAN_END_LINE_RE.sub("", tail)
        new_text = head + full_block + ("\n" + tail if tail else "\n")
        return new_text, ("noop" if new_text == text else "replaced")

    cleaned = ORPHAN_START_LINE_RE.sub("", text)
    cleaned = ORPHAN_END_LINE_RE.sub("", cleaned)
    prefix = "" if cleaned.endswith("\n") else "\n"
    new_text = cleaned + prefix + "\n" + full_block + "\n"
    return new_text, "seeded"


PACK_TO_CATEGORY = {
    "00-ai-model-selection.md": "master",
    "10-speech-audio.md": "speech-audio",
    "20-vision.md": "vision",
    "30-language.md": "language",
    "40-multimodal.md": "multimodal",
    "50-agentic.md": "agentic",
    "60-code.md": "code",
}


def run(db_path: Path = DB_PATH, rules_dir: Path = RULES_DIR) -> dict[str, str]:
    counts = query_counts(db_path)
    today = _today()
    results: dict[str, str] = {}
    for pack_name, category in PACK_TO_CATEGORY.items():
        pack_path = rules_dir / pack_name
        if not pack_path.exists():
            _log(f"WARN: {pack_path} missing — skipping")
            results[pack_name] = "missing"
            continue
        body = render_block(category, counts, today)
        if not body:
            _log(f"WARN: empty body for category {category!r} — skipping {pack_name}")
            results[pack_name] = "empty"
            continue
        text = pack_path.read_text(encoding="utf-8")
        new_text, action = replace_block(text, body, today)
        if new_text != text:
            pack_path.write_text(new_text, encoding="utf-8")
        results[pack_name] = action
        _log(f"{pack_name}: {action}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--rules-dir", type=Path, default=RULES_DIR)
    args = parser.parse_args()
    results = run(args.db, args.rules_dir)
    _log(f"summary: {results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
