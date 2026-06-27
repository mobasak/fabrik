#!/usr/bin/env python3
"""Inject OPENROUTER_ROUTES marker blocks into the 7 LLM-bearing
`.windsurf/rules/ai/NN-*.md` packs + write/refresh the canonical
`Last content verification: YYYY-MM-DD` stamp atomically.

Phase 4 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §10).

Self-heal pattern lifted verbatim from `embedding_export_markdown.py:
209-247` (shipped in commit `f3c8222`): if the START/END marker pair
is missing from a host file, the body is APPENDED with fresh markers
rather than raising.

Pack stamping divergence from the embedding mirror (Pass 2B Finding 1):
this script ALSO writes/updates the canonical `Last content verification:
YYYY-MM-DD` line per pack — the embedding-side packs (in `core/`)
aren't covered by `check_ai_pack_freshness.py`, but the ai/* packs ARE,
so freshness must move in lockstep with the marker refresh. The marker
block and the stamp line are written in a single atomic
`pack_path.write_text(new_content)` call — never partial.

Pass A defect log (2026-06-27):

  F1 — H1-finder landed inside YAML frontmatter when a description
       contained '# '. Fixed by skipping past frontmatter before the
       H1 scan.
  F2 — VERIFICATION_RE was anchored + case-sensitive; the consumer
       (`check_ai_pack_freshness.py:25-28`) is `re.IGNORECASE` and
       unanchored. A manually-written 'last content verification: ...'
       line slipped past the writer and got duplicated. Now matches
       the consumer's contract exactly.
  F3 — A pack with only one marker (orphan) made `_replace_or_append`
       APPEND a second block while leaving the orphan in place;
       subsequent runs accumulated more orphans. Fixed by stripping
       every dangling marker line before deciding append-vs-replace.
  F4/F5 — Marker-rebuild logic was duplicated between
       `_replace_or_append_markers` (returning flags) and `inject_pack`
       (rebuilding the buffer inline). Now `_replace_or_append_markers`
       returns `(new_text, seeded)` and `inject_pack` is one straight
       line per stage.
  F6 — Plan §10.3(d) promised a WARN on malformed dates; added.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).parent
FABRIK_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "ai_category_configs.yaml"
ROUTES_JSON_PATH = SCRIPT_DIR / "openrouter_routes.json"

MARKER_START_TEMPLATE = (
    "<!-- OPENROUTER_ROUTES:START — last-refreshed: {date} "
    "(auto-managed by category_export_markdown.py) -->"
)
MARKER_START_PREFIX = "<!-- OPENROUTER_ROUTES:START"
MARKER_END = "<!-- OPENROUTER_ROUTES:END -->"

# Pass A F3 fix: orphan-marker line stripper. Matches any LINE containing
# the START prefix or the END string, end-anchored to catch the full HTML
# comment so partial strings inside markdown body aren't touched.
ORPHAN_START_LINE_RE = re.compile(rf"^.*{re.escape(MARKER_START_PREFIX)}.*$\n?", re.MULTILINE)
ORPHAN_END_LINE_RE = re.compile(rf"^.*{re.escape(MARKER_END)}.*$\n?", re.MULTILINE)

# Pass A F2 fix: match the consumer's regex (`check_ai_pack_freshness.py:
# 25-28`) exactly — case-insensitive, unanchored, captures the date.
# Optional trailing text is allowed but rewritten away on replace so the
# canonical line stays canonical.
VERIFICATION_RE = re.compile(
    r"^[^\S\n]*Last content verification:\s*(\d{4}-\d{2}-\d{2})[^\n]*$",
    re.MULTILINE | re.IGNORECASE,
)
VERIFICATION_FORMAT = "Last content verification: {date}"

YAML_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _log(msg: str) -> None:
    print(f"[category_export_markdown] {msg}")


def _utc_today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def render_routes_block(category: str, entry: dict[str, Any]) -> str:
    today = _utc_today_iso()
    routes = entry.get("routes", [])
    reason = entry.get("reason", "")

    lines = [
        f"*Auto-generated {today} (UTC) by `category_route_mapper.py` "
        "→ injected here by `category_export_markdown.py`. Edits between "
        "the markers will be overwritten on the next daily run.*",
        "",
    ]

    if not routes:
        placeholder = (
            "*No eligible models today — floors too strict or catalog too "
            "thin. See `cache/update.log` for details."
        )
        placeholder += f" Reason: {reason}*" if reason else "*"
        lines.append(placeholder)
        return "\n".join(lines)

    lines.append("| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |")
    lines.append("|---|---|---|---|---|")
    for r in routes:
        cost_in = r.get("input_cost_per_m")
        cost_str = "free" if cost_in == 0 else f"${cost_in:.2f}"
        ctx = r.get("context_window_k", "?")
        status = "free" if cost_in == 0 else ("GA" if r.get("is_ga") else "preview")
        lines.append(f"| P{r['priority']} | `{r['id']}` | {cost_str} | {ctx}k | {status} |")
    lines.append("")
    lines.append(
        "To consume via a Fabrik spec: `llm_provider: openrouter` + "
        "`llm_model: <P1 id>`. Fallback chain via the OpenRouter "
        "`models: [P1, P2, P3]` request parameter."
    )
    return "\n".join(lines)


def _replace_or_append_markers(
    text: str,
    body: str,
    today: str,
) -> tuple[str, bool]:
    """Self-heal marker injection. Returns (new_text, seeded_flag).

    Contract:
      - If a valid START/END pair (in that order) is found, REPLACE the
        block in place — old body is overwritten, no orphans left.
      - Otherwise (no pair, partial pair, swapped pair), STRIP every
        dangling marker line then APPEND a fresh block at EOF.

    Pass A F3 fix: the previous version trusted `find()` and left orphan
    markers in the text. We now use line-level regex stripping so a
    half-marker (or a swapped pair) is normalized first — no
    accumulation across runs.
    """
    new_start_line = MARKER_START_TEMPLATE.format(date=today)
    full_block = f"{new_start_line}\n{body.rstrip(chr(10))}\n{MARKER_END}"

    start_idx = text.find(MARKER_START_PREFIX)
    end_idx = text.find(MARKER_END)
    has_valid_pair = start_idx != -1 and end_idx != -1 and end_idx > start_idx

    if has_valid_pair:
        head = text[:start_idx]
        end_line_end = text.find("\n", end_idx)
        tail = "" if end_line_end == -1 else text[end_line_end + 1 :]
        # Make sure no stray markers live outside the pair.
        head = ORPHAN_START_LINE_RE.sub("", head)
        head = ORPHAN_END_LINE_RE.sub("", head)
        tail = ORPHAN_START_LINE_RE.sub("", tail)
        tail = ORPHAN_END_LINE_RE.sub("", tail)
        new_text = head + full_block + ("\n" + tail if tail else "\n")
        return new_text, False

    # Strip every orphan marker line, then append fresh.
    cleaned = ORPHAN_START_LINE_RE.sub("", text)
    cleaned = ORPHAN_END_LINE_RE.sub("", cleaned)
    prefix = "" if cleaned.endswith("\n") else "\n"
    new_text = cleaned + prefix + "\n" + full_block + "\n"
    return new_text, True


def _frontmatter_end_index(text: str) -> int:
    """Return the char index right after the YAML frontmatter, or 0 if
    none. Pass A F1 fix: H1 detection must skip frontmatter — a
    description like `description: A # B` would otherwise pull the stamp
    inside the YAML block."""
    match = YAML_FRONTMATTER_RE.match(text)
    return match.end() if match else 0


def _marker_block_range(text: str) -> tuple[int, int] | None:
    """Return (start, end_exclusive) char indices of the
    OPENROUTER_ROUTES marker block (including both marker lines), or
    None if no valid pair exists. Pass C fix: stamp scanning must skip
    this range — body content may legitimately contain text matching
    the stamp regex (e.g. operator-authored `notes:` that happens to
    include 'Last content verification:')."""
    start = text.find(MARKER_START_PREFIX)
    end = text.find(MARKER_END)
    if start == -1 or end == -1 or end <= start:
        return None
    end_line_end = text.find("\n", end)
    end_excl = len(text) if end_line_end == -1 else end_line_end + 1
    return start, end_excl


def _refresh_stamp(text: str, today: str) -> tuple[str, str]:
    """Insert or replace the `Last content verification: YYYY-MM-DD` line.

    Returns (new_text, action): 'inserted' | 'replaced' | 'unchanged'.

    Pass A F2 fix: regex now matches the consumer's exact contract
    (case-insensitive, unanchored capture), so a manually-written
    `last content verification:` line is detected and REPLACED — not
    silently duplicated.

    Pass A F6 fix: malformed dates (e.g. `2026-99-99`) match the
    YYYY-MM-DD shape but fail `date.fromisoformat()`. Emit a WARN log
    line so the daily log records the normalization (plan §10.3(d)
    contract), then replace as if stale.

    Pass B Finding 1 fix: when a pack contains MULTIPLE legacy stamps
    (hand-edits, merge artifacts), the previous version only replaced
    the first occurrence — leaving stragglers. Now collects ALL matches,
    canonicalizes the FIRST in place, and DELETES the rest, leaving the
    file with exactly one stamp per the contract.

    Pass C fix: matches landing INSIDE the OPENROUTER_ROUTES marker
    block are now ignored — the body region is auto-generated and may
    contain stamp-like substrings via the operator-authored `notes:`
    field flowing through `entry['reason']`. Plan §10.3 step 2(b)
    requires the stamp to land directly under the H1, not inside the
    marker block.
    """
    new_line = VERIFICATION_FORMAT.format(date=today)
    block_range = _marker_block_range(text)
    all_matches = list(VERIFICATION_RE.finditer(text))
    matches = [
        m
        for m in all_matches
        if block_range is None or not (block_range[0] <= m.start() < block_range[1])
    ]
    if matches:
        for m in matches:
            try:
                date.fromisoformat(m.group(1))
            except ValueError:
                _log(
                    f"WARN: existing stamp has malformed date '{m.group(1)}' "
                    f"— replacing with {today}"
                )
        first = matches[0]
        # Pass B Finding 1: nuke EVERY stamp (including the first), then
        # re-insert exactly one canonical line at the first's position.
        # Build the new text by walking matches in reverse so prior
        # start/end indices stay valid.
        new_text = text
        for m in reversed(matches):
            new_text = new_text[: m.start()] + new_text[m.end() :]
        new_text = new_text[: first.start()] + new_line + new_text[first.start() :]
        if new_text == text:
            return text, "unchanged"
        # 'replaced' if first stamp moved (or extra stamps dropped);
        # `len(matches) > 1` is also a replaced state.
        return new_text, "replaced"

    # No stamp — insert one. Skip frontmatter, then land right after the
    # first H1 if one exists, else file-top.
    fm_end = _frontmatter_end_index(text)
    body_region = text[fm_end:]
    h1_pos_in_body = body_region.find("# ")
    if h1_pos_in_body == -1:
        return new_line + "\n\n" + text, "inserted"
    h1_pos = fm_end + h1_pos_in_body
    h1_end = text.find("\n", h1_pos)
    if h1_end == -1:
        return text + "\n" + new_line + "\n", "inserted"
    return (
        text[: h1_end + 1] + "\n" + new_line + "\n" + text[h1_end + 1 :],
        "inserted",
    )


def inject_pack(pack_path: Path, category: str, entry: dict[str, Any]) -> dict[str, str]:
    """Apply the marker block + freshness stamp to ONE pack.

    Atomic single-write contract (Pass 1D D6): both edits land in one
    `pack_path.write_text(new_content)` call.

    Pass A F4 cleanup: `_replace_or_append_markers` now returns the
    rebuilt buffer directly, so `inject_pack` is one straight pipeline
    of three functions (no inline rebuild duplication).
    """
    if not pack_path.exists():
        _log(f"WARN: {pack_path} does not exist — skipping")
        return {"status": "missing"}

    today = _utc_today_iso()
    text = pack_path.read_text(encoding="utf-8")

    body = render_routes_block(category, entry)
    marker_updated_text, seeded = _replace_or_append_markers(text, body, today)
    final_text, stamp_action = _refresh_stamp(marker_updated_text, today)

    if final_text == text:
        return {"status": "noop", "marker": "noop", "stamp": "noop"}
    pack_path.write_text(final_text, encoding="utf-8")
    return {
        "status": "wrote",
        "marker": "seeded" if seeded else "replaced",
        "stamp": stamp_action,
    }


def run(
    config_path: Path | str = CONFIG_PATH,
    routes_json_path: Path | str = ROUTES_JSON_PATH,
    fabrik_root: Path | str = FABRIK_ROOT,
) -> dict[str, dict[str, str]]:
    cfg = yaml.safe_load(Path(config_path).read_text())
    categories = cfg.get("categories", {})

    routes_payload = json.loads(Path(routes_json_path).read_text())
    payload_cats = routes_payload.get("categories", {})

    results: dict[str, dict[str, str]] = {}
    for category, cat_cfg in categories.items():
        pack_rel = cat_cfg.get("pack_file")
        if not pack_rel:
            _log(f"WARN: category {category!r} has no pack_file — skipping")
            results[category] = {"status": "skipped_no_pack"}
            continue
        pack_path = Path(fabrik_root) / pack_rel

        entry = payload_cats.get(
            category,
            {"routes": [], "reason": "category absent from routes JSON"},
        )

        results[category] = inject_pack(pack_path, category, entry)
        _log(f"{category}: {results[category]}")

    return results


if __name__ == "__main__":
    if not CONFIG_PATH.exists():
        _log(f"ERROR: {CONFIG_PATH} does not exist.")
        sys.exit(1)
    if not ROUTES_JSON_PATH.exists():
        _log(f"ERROR: {ROUTES_JSON_PATH} does not exist. Run category_route_mapper.py first.")
        sys.exit(1)
    run()
