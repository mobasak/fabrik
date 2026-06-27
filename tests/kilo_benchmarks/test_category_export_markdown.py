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


def test_full_surface_pass2_ff_rejects_path_traversal(tmp_path, capsys):
    """Full-surface Pass 2 F-F: `pack_file: ../precious.md` used to
    overwrite the victim file because the only existence check happened
    inside inject_pack — escapes were resolved before the allowlist.
    Now every resolved pack_path is required to live under
    `<fabrik_root>/.windsurf/rules/ai/`."""
    fake_root = tmp_path / "sub"
    fake_root.mkdir()
    victim = tmp_path / "precious.md"
    victim.write_text("# precious\nDO NOT TOUCH\n")
    victim_mtime = victim.stat().st_mtime

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({
        "categories": {
            "evil": {"pack_file": "../precious.md"},
        }
    }))
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"categories": {"evil": {"routes": [], "reason": ""}}}))

    results = export.run(config_path=cfg, routes_json_path=routes, fabrik_root=fake_root)
    assert results["evil"]["status"] == "rejected_path_escape", results
    assert victim.read_text() == "# precious\nDO NOT TOUCH\n", "victim was modified!"
    assert victim.stat().st_mtime == victim_mtime
    out = capsys.readouterr().out
    assert "escapes" in out


def test_full_surface_pass2_ff_allows_canonical_pack_path(tmp_path):
    """Pass 2 F-F: the guard must not reject legitimate paths under
    `<fabrik_root>/.windsurf/rules/ai/`."""
    fake_root = tmp_path
    rules_dir = fake_root / ".windsurf" / "rules" / "ai"
    rules_dir.mkdir(parents=True)
    pack = rules_dir / "30-language.md"
    pack.write_text("# Language\n\nbody\n")

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({
        "categories": {
            "language": {"pack_file": ".windsurf/rules/ai/30-language.md"},
        }
    }))
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"categories": {"language": _entry([_route("x/y")])}}))

    results = export.run(config_path=cfg, routes_json_path=routes, fabrik_root=fake_root)
    assert results["language"]["status"] == "wrote", results


def test_full_surface_pass3_f2_bom_does_not_bypass_frontmatter():
    """Pass 3 F2: UTF-8 BOM at file start used to bypass YAML frontmatter
    detection (Pass A F1 regression) — `\\A---` doesn't match BOM-prefixed
    text, so `_frontmatter_end_index` returned 0 and the stamp landed
    inside the description. YAML_FRONTMATTER_RE now accepts optional BOM."""
    p = Path(tempfile.mkdtemp()) / "p.md"
    p.write_bytes("﻿---\ntitle: A\ndescription: 'Foo # Bar'\n---\n# Real H1\n\nbody\n".encode("utf-8"))
    export.inject_pack(p, "language", _entry([_route("x/y")]))
    text = p.read_text(encoding="utf-8")
    fm_close = text.find("\n---\n", 5) + 5
    stamp_pos = text.find("Last content verification:")
    assert stamp_pos > fm_close, (
        f"BOM bypass: stamp at {stamp_pos} landed inside BOM-prefixed "
        f"frontmatter ending at {fm_close}"
    )


def test_full_surface_pass3_f5_single_digit_date_canonicalized(capsys):
    """Pass 3 F5: hand-edited single-digit dates like `2026-6-27` used to
    bypass the writer's `\\d{2}-\\d{2}` requirement → fresh stamp got
    APPENDED while the bad line stayed in body as a permanent orphan.
    Writer regex now allows `\\d{1,2}`; `date.fromisoformat()` rejects
    the value, the WARN line fires, and the malformed stamp is
    rewritten in place."""
    p = Path(tempfile.mkdtemp()) / "p.md"
    p.write_text("# X\nLast content verification: 2026-6-27\n\nbody\n")
    export.inject_pack(p, "language", _entry([_route("x/y")]))
    import re
    stamps = re.findall(r"(?i)last content verification:[^\n]*", p.read_text())
    assert len(stamps) == 1
    assert stamps[0] == f"Last content verification: {TODAY}"
    out = capsys.readouterr().out
    assert "WARN" in out and "2026-6-27" in out


def test_full_surface_pass3_f6_end_marker_in_prose_above_block():
    """Pass 3 F6: a prose mention of `<!-- OPENROUTER_ROUTES:END -->`
    above the legitimate marker block used to make `find()` return the
    prose END position. `end_idx <= start_idx` then tripped, routing the
    valid block through self-heal — discarding the prior block's body
    and leaving fragments. Now we search for END only AFTER the START,
    so the pair is coherent and the prose mention gets stripped by the
    orphan-line pass."""
    p = Path(tempfile.mkdtemp()) / "p.md"
    p.write_text(
        "# X\nSee the <!-- OPENROUTER_ROUTES:END --> marker below.\n\n"
        "<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-01-01 -->\n"
        "OLD CONTENT\n<!-- OPENROUTER_ROUTES:END -->\nTail\n"
    )
    res = export.inject_pack(p, "language", _entry([_route("x/y")]))
    text = p.read_text()
    # The marker action must be 'replaced' (the valid pair was recognized).
    assert res["marker"] == "replaced", f"got {res}"
    # Pass 12: count REAL markers via line-anchored regex (line begins
    # with horizontal whitespace + marker + closes HTML comment on
    # same line). The prose mention is preserved as documentation and
    # contains the substring but is NOT a real marker line.
    assert len(export.REAL_START_RE.findall(text)) == 1
    assert len(export.REAL_END_RE.findall(text)) == 1
    # The original block's "OLD CONTENT" must be replaced.
    assert "OLD CONTENT" not in text
    # The tail content must survive.
    assert "Tail" in text
    # The prose mention should ALSO survive (Pass 12: orphan strip
    # only matches real marker lines, not inline-code mentions).
    assert "See the" in text


def test_full_surface_pass5_f2_per_pack_exception_does_not_halt_loop(tmp_path, capsys):
    """Pass 5 F2: a per-pack UnicodeDecodeError used to abort the
    orchestrator loop, leaving downstream packs silently unprocessed
    while the hook's `|| echo failed (non-fatal)` masked the abort.
    Now each per-pack exception is caught, logged, recorded as
    `status: failed`, and the loop continues."""
    fake_root = tmp_path
    rules = fake_root / ".windsurf" / "rules" / "ai"
    rules.mkdir(parents=True)
    (rules / "30-language.md").write_text("# A\n\nbody\n")
    (rules / "60-code.md").write_text("# B\n\nbody\n")
    bad = rules / "20-vision.md"
    bad.write_bytes(b"# C\n\nbody\n\x80\x80\xfe\n")  # invalid utf-8

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({"categories": {
        "vision":   {"pack_file": ".windsurf/rules/ai/20-vision.md"},
        "language": {"pack_file": ".windsurf/rules/ai/30-language.md"},
        "code":     {"pack_file": ".windsurf/rules/ai/60-code.md"},
    }}, sort_keys=False))
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"categories": {
        "vision":   _entry([_route("x/y")]),
        "language": _entry([_route("x/y")]),
        "code":     _entry([_route("x/y")]),
    }}))

    results = export.run(config_path=cfg, routes_json_path=routes, fabrik_root=fake_root)
    assert results["vision"]["status"] == "failed"
    assert "UnicodeDecodeError" in results["vision"]["error"]
    assert results["language"]["status"] == "wrote"
    assert results["code"]["status"] == "wrote"
    out = capsys.readouterr().out
    assert "vision: FAILED" in out


def test_full_surface_pass11_marker_block_range_skips_prose_end():
    """Pass 11: `_marker_block_range` used `text.find(MARKER_END)` with
    no offset → first occurrence (e.g. a prose mention "see the
    `<!-- OPENROUTER_ROUTES:END -->` line below") tripped the
    `end <= start` guard, function returned None, and `_refresh_stamp`
    fell through to the unprotected path — mutating an in-block stamp
    line. Pass C's protection was silently disabled.

    This regresses the SAME bug class as Pass 3 F6 in
    `_replace_or_append_markers`, but in a different function with
    its own copy of the find-without-offset anti-pattern."""
    p = Path(tempfile.mkdtemp()) / "p.md"
    p.write_text(
        "# Pack\n\n"
        "Doc note: this pack auto-manages an "
        "`<!-- OPENROUTER_ROUTES:END -->` block at the bottom.\n\n"
        "<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-06-27 "
        "(auto-managed by category_export_markdown.py) -->\n"
        "*Auto-generated content*\n"
        "Last content verification: 2020-01-01\n"
        "Tail body\n"
        "<!-- OPENROUTER_ROUTES:END -->\n"
    )
    res = export.inject_pack(p, "language", _entry([_route("x/y")]))
    text = p.read_text()
    # The block_range must be detected (Pass 11 + Pass 12 fix) so the
    # stamp regex skips the in-block "Last content verification:" line
    # and instead writes a NEW canonical stamp under the H1.
    real_start_m = export.REAL_START_RE.search(text)
    real_end_m = export.REAL_END_RE.search(text)
    assert real_start_m is not None and real_end_m is not None
    canonical = text.find(f"Last content verification: {TODAY}")
    assert canonical != -1
    assert canonical < real_start_m.start(), (
        f"in-block stamp protection silently disabled: canonical "
        f"stamp at {canonical} but real marker block starts at "
        f"{real_start_m.start()}"
    )
    block = text[real_start_m.start():real_end_m.end()]
    import re
    in_block_stamps = re.findall(r"(?i)last content verification:[^\n]*", block)
    assert in_block_stamps == [], (
        f"in-block stamps not cleared: {in_block_stamps}"
    )
    # Pass 12: prose mention preserved as documentation; only ONE REAL
    # marker pair (line-anchored).
    assert len(export.REAL_START_RE.findall(text)) == 1
    assert len(export.REAL_END_RE.findall(text)) == 1
    assert "Doc note" in text  # prose preserved


def test_full_surface_pass12_start_marker_in_prose_above_block():
    """Pass 12: the symmetric counterpart to Pass 3 F6 / Pass 11.
    `text.find(MARKER_START_PREFIX)` returned the FIRST occurrence; if a
    pack contained prose mentioning the START marker (e.g. inline code
    `\\`<!-- OPENROUTER_ROUTES:START\\`` in doc text), the find call
    landed on the prose, NOT the real block. `_replace_or_append_markers`
    then sliced head at the prose position, fusing the prose prefix with
    the rebuilt START line and silently destroying any content between
    the prose mention and the real block (including legitimate stamps).

    Pass 12 fixes both `_replace_or_append_markers` and
    `_marker_block_range` via line-anchored `REAL_START_RE` / `REAL_END_RE`
    which require the marker to be at line beginning with at most
    horizontal whitespace, closing the HTML comment on the same line —
    so inline-code/quoted mentions are rejected at the matching layer.
    The orphan-strip regexes were ALSO tightened to the same shape so
    they no longer eat prose lines that contain marker substrings."""
    p = Path(tempfile.mkdtemp()) / "p.md"
    p.write_text(
        "# Pack\n\n"
        "Doc note: pack manages `<!-- OPENROUTER_ROUTES:START` block.\n\n"
        "Last content verification: 2020-01-01\n\n"
        "<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-06-27 "
        "(auto-managed by category_export_markdown.py) -->\n"
        "Body\n"
        "<!-- OPENROUTER_ROUTES:END -->\n"
    )
    res = export.inject_pack(p, "language", _entry([_route("x/y")]))
    text = p.read_text()
    # Doc note preserved (not fused into the rebuilt marker).
    assert "Doc note: pack manages" in text
    # Real marker count == 1+1 (the prose substring doesn't count).
    assert len(export.REAL_START_RE.findall(text)) == 1
    assert len(export.REAL_END_RE.findall(text)) == 1
    # The stale 2020-01-01 stamp must be canonicalized to today.
    assert "2020-01-01" not in text
    assert f"Last content verification: {TODAY}" in text
