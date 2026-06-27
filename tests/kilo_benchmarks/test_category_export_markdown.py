"""Tests for `scripts/kilo-benchmarks/category_export_markdown.py`.

Phase 4 of the OpenRouter routing plan. Synthetic pack fixtures —
NEVER mutates real packs under `.windsurf/rules/ai/`.

Coverage map (plan §10.5 + G4.1-G4.5):
  - test_marker_self_heal_absent      → marker missing → APPENDED
  - test_marker_replaces_existing     → marker present → REPLACED, single block
  - test_stamp_inserted_when_absent   → no `Last content verification` → INSERTED
  - test_stamp_replaced_when_stale    → stale date → updated to today
  - test_stamp_unchanged_when_today   → idempotency: today's date stays put
  - test_stamp_replaced_when_malformed → `2026-99-99` style → replace not raise
  - test_atomic_write                 → single write per call (no torn state)
  - test_idempotent_two_runs          → mtime stable on second call
  - test_zero_eligible_writes_placeholder → empty `routes` → placeholder line
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


export = _load("category_export_markdown")
TODAY = datetime.now(UTC).date().isoformat()


def _entry(routes: list[dict] | None = None, reason: str = "") -> dict:
    return {"routes": routes or [], "reason": reason}


def _route(name: str, cost: float = 0.5, ctx: int = 32) -> dict:
    return {
        "priority": 1,
        "id": name,
        "provider": "test",
        "input_cost_per_m": cost,
        "context_window_k": ctx,
        "is_ga": True,
    }


def _pack(text: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "test-pack.md"
    tmp.write_text(text, encoding="utf-8")
    return tmp


def test_marker_self_heal_absent():
    pack = _pack("# Test Pack\n\nSome existing body.\n")
    result = export.inject_pack(pack, "language", _entry([_route("a/m1")]))
    assert result["marker"] == "seeded"
    text = pack.read_text()
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1
    assert "a/m1" in text


def test_marker_replaces_existing():
    seeded = (
        "# Test Pack\n\nBody\n\n"
        f"<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-01-01 -->\nOLD TABLE\n"
        "<!-- OPENROUTER_ROUTES:END -->\n\nTail\n"
    )
    pack = _pack(seeded)
    result = export.inject_pack(pack, "code", _entry([_route("b/m2", cost=0.0)]))
    assert result["marker"] == "replaced"
    text = pack.read_text()
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1
    assert "OLD TABLE" not in text
    assert "b/m2" in text
    assert "free" in text  # cost=0 renders as "free"
    assert "Tail" in text  # tail preserved


def test_stamp_inserted_when_absent():
    pack = _pack("# Test Pack\n\nBody\n")
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    assert f"Last content verification: {TODAY}" in text


def test_stamp_replaced_when_stale():
    pack = _pack(
        "# Test Pack\nLast content verification: 2020-01-01\n\nBody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    assert "2020-01-01" not in text
    assert f"Last content verification: {TODAY}" in text


def test_stamp_unchanged_when_today():
    pack = _pack(
        f"# Test Pack\nLast content verification: {TODAY}\n\nBody\n"
    )
    # First run seeds markers (so file IS modified), but the stamp itself
    # already matches today → stamp_action should be 'unchanged'.
    text_before_run = pack.read_text()
    res = export.inject_pack(pack, "language", _entry([_route("x/y")]))
    assert res["stamp"] == "unchanged"
    # Today's stamp count is unchanged (not duplicated).
    assert pack.read_text().count(f"Last content verification: {TODAY}") == 1
    _ = text_before_run


def test_stamp_replaced_when_malformed():
    """Plan §10 Pass 2B Finding 10: malformed-shape dates like
    `2026-99-99` match the YYYY-MM-DD regex but fail
    `date.fromisoformat()`. The marker writer treats them as stale and
    replaces with today — surface invalid dates downstream via
    `check_ai_pack_freshness.py`, not in this writer."""
    pack = _pack(
        "# Test Pack\nLast content verification: 2026-99-99\n\nBody\n"
    )
    res = export.inject_pack(pack, "language", _entry([_route("x/y")]))
    assert res["stamp"] == "replaced"
    text = pack.read_text()
    assert "2026-99-99" not in text
    assert f"Last content verification: {TODAY}" in text


def test_atomic_write():
    """Plan §10 Pass 1D D6: marker block + stamp must land in ONE
    write_text call. We monkey-patch write_text and assert call count == 1
    per inject_pack invocation."""
    pack = _pack("# Test Pack\n\nBody\n")
    real_write = Path.write_text
    calls: list[Path] = []

    def counting_write(self, *args, **kwargs):
        calls.append(self)
        return real_write(self, *args, **kwargs)

    with patch.object(Path, "write_text", counting_write):
        export.inject_pack(pack, "language", _entry([_route("x/y")]))

    writes_to_pack = [c for c in calls if c == pack]
    assert len(writes_to_pack) == 1, (
        f"expected exactly 1 write_text() call to the pack, got {len(writes_to_pack)}"
    )


def test_idempotent_two_runs():
    pack = _pack("# Test Pack\n\nBody\n")
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    after_first = pack.read_text()
    mtime_first = pack.stat().st_mtime_ns

    res = export.inject_pack(pack, "language", _entry([_route("x/y")]))
    after_second = pack.read_text()

    assert after_first == after_second
    assert res["status"] == "noop"
    assert pack.stat().st_mtime_ns == mtime_first  # no rewrite on noop


def test_zero_eligible_writes_placeholder():
    pack = _pack("# Test Pack\n\nBody\n")
    export.inject_pack(pack, "code", _entry(routes=[], reason="floors too strict"))
    text = pack.read_text()
    assert "No eligible models today" in text
    assert "floors too strict" in text
    # Marker still wraps even when body is a placeholder.
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1


def test_run_e2e_with_fake_packs(tmp_path):
    """G4.4: end-to-end against a fake fabrik root. Verifies the orchestrator
    walks every category in the YAML and rewrites only the named packs."""
    fake_root = tmp_path
    rules_dir = fake_root / ".windsurf" / "rules" / "ai"
    rules_dir.mkdir(parents=True)
    cat_pack = rules_dir / "30-language.md"
    cat_pack.write_text("# Language\n\nbody\n")

    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump({
        "categories": {
            "language": {"pack_file": ".windsurf/rules/ai/30-language.md"},
        }
    }))

    routes_path = tmp_path / "routes.json"
    routes_path.write_text(json.dumps({
        "categories": {
            "language": {"routes": [_route("p/q")], "reason": ""},
        }
    }))

    results = export.run(
        config_path=cfg_path,
        routes_json_path=routes_path,
        fabrik_root=fake_root,
    )
    assert results["language"]["status"] == "wrote"
    text = cat_pack.read_text()
    assert "p/q" in text
    assert f"Last content verification: {TODAY}" in text


def test_pass_a_f1_stamp_skips_yaml_frontmatter():
    """Pass A F1: H1-finder used to land inside YAML frontmatter when a
    description contained '# ' (e.g. `description: A # B`). Verify the
    stamp lands AFTER the frontmatter, not inside it."""
    pack = _pack(
        "---\nactivation: glob\ndescription: A # B # C\n---\n"
        "# Real H1\n\nbody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    fm_end = text.find("\n---\n", 4) + 5
    stamp_pos = text.find("Last content verification:")
    assert stamp_pos > fm_end, (
        f"stamp at {stamp_pos} landed inside frontmatter (ends {fm_end})"
    )
    # Frontmatter itself is intact: still exactly TWO `---` lines at top.
    assert text.count("\n---\n") == 1
    assert text.startswith("---\n")


def test_pass_a_f2_canonicalizes_lowercase_stamp():
    """Pass A F2: writer regex was case-sensitive while consumer is
    case-insensitive — a lowercase stamp was being duplicated."""
    pack = _pack(
        "# X\nlast content verification: 2020-01-01\n\nbody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    import re
    all_stamps = re.findall(r"(?i)last content verification:[^\n]*", text)
    assert len(all_stamps) == 1, f"expected 1 stamp, got {len(all_stamps)}: {all_stamps}"
    assert f"Last content verification: {TODAY}" in text


def test_pass_a_f2_canonicalizes_trailing_text_stamp():
    """Pass A F2: a stamp with trailing text (`(manual)`) used to be
    invisible to the writer, causing duplication."""
    pack = _pack(
        "# X\nLast content verification: 2020-01-01 (manual)\n\nbody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    import re
    all_stamps = re.findall(r"(?i)last content verification:[^\n]*", text)
    assert len(all_stamps) == 1
    assert f"Last content verification: {TODAY}" in text
    assert "(manual)" not in text.split("Last content verification:")[1].splitlines()[0]


def test_pass_a_f3_orphan_end_marker_does_not_accumulate():
    """Pass A F3: a single orphan END marker was being preserved across
    runs, with each run appending a fresh block. Two runs should still
    converge to exactly 1 START + 1 END."""
    pack = _pack(
        "# X\n\n<!-- OPENROUTER_ROUTES:END -->\nbody\n"
    )
    for _ in range(2):
        export.inject_pack(pack, "language", _entry([_route("a/m")]))
    text = pack.read_text()
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1


def test_pass_a_f3_orphan_start_marker_does_not_accumulate():
    pack = _pack(
        "# X\n\n<!-- OPENROUTER_ROUTES:START — orphaned -->\nbody\n"
    )
    for _ in range(2):
        export.inject_pack(pack, "language", _entry([_route("a/m")]))
    text = pack.read_text()
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1


def test_pass_a_f3_swapped_pair_does_not_accumulate():
    pack = _pack(
        "# X\n<!-- OPENROUTER_ROUTES:END -->\nold\n"
        "<!-- OPENROUTER_ROUTES:START — orphan -->\nbody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("a/m")]))
    text = pack.read_text()
    assert text.count("OPENROUTER_ROUTES:START") == 1
    assert text.count("OPENROUTER_ROUTES:END") == 1


def test_pass_c_stamp_skips_marker_block_region():
    """Pass C Finding: when body content contains a stamp-like line
    (via operator-authored `notes:` field), `_refresh_stamp` used to
    canonicalize THAT line — placing the stamp inside the auto-managed
    marker block instead of under the H1 (plan §10.3 step 2(b))."""
    pack = _pack("# Pack\n\nbody\n")
    bad_entry = {
        "routes": [],
        "reason": "\nLast content verification: 2020-01-01",
    }
    export.inject_pack(pack, "language", bad_entry)
    text = pack.read_text()
    start = text.find("OPENROUTER_ROUTES:START")
    end = text.find("OPENROUTER_ROUTES:END")
    canonical_stamp_pos = text.find(f"Last content verification: {TODAY}")
    assert canonical_stamp_pos != -1
    # Canonical stamp must land BEFORE the marker block — not inside it.
    assert canonical_stamp_pos < start, (
        f"stamp at {canonical_stamp_pos} landed inside or after marker block "
        f"[{start}, {end}]"
    )


def test_pass_b_f1_multi_stamp_collapses_to_one():
    """Pass B Finding 1: previous fix only canonicalized the FIRST stamp;
    extras lingered. Now ALL stamps collapse to a single canonical line
    at the first stamp's position."""
    pack = _pack(
        "# X\nLast content verification: 2020-01-01\n\nbody\n"
        "Last content verification: 2019-12-31\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    text = pack.read_text()
    import re
    stamps = re.findall(r"(?i)last content verification:[^\n]*", text)
    assert len(stamps) == 1
    assert stamps[0] == f"Last content verification: {TODAY}"


def test_pass_a_f6_malformed_date_emits_warn(capsys):
    """Pass A F6: plan §10.3(d) promised a WARN when a malformed date
    is normalized — must surface in the daily log."""
    pack = _pack(
        "# X\nLast content verification: 2026-99-99\n\nbody\n"
    )
    export.inject_pack(pack, "language", _entry([_route("x/y")]))
    out = capsys.readouterr().out
    assert "WARN" in out and "2026-99-99" in out


def test_run_warns_on_missing_pack(tmp_path, capsys):
    """G4.4 negative path: pack listed in YAML but absent on disk → WARN,
    no crash, no other packs affected."""
    fake_root = tmp_path
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump({
        "categories": {
            "language": {"pack_file": ".windsurf/rules/ai/missing.md"},
        }
    }))
    routes_path = tmp_path / "routes.json"
    routes_path.write_text(json.dumps({"categories": {"language": _entry()}}))

    results = export.run(
        config_path=cfg_path,
        routes_json_path=routes_path,
        fabrik_root=fake_root,
    )
    assert results["language"]["status"] == "missing"
    captured = capsys.readouterr()
    assert "does not exist" in captured.out
