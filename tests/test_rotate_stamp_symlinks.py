"""The rotation tick's sibling stamps refuse symlinks, as `_write_stamp`/`_stamp_holds` do (W-d33d74a1).

The drain, identity-probe, refresh and fleet-advisory stamps fall back to the shared temp dir when the
state dir is unreachable, and they were written with `touch`/`write_text` (which follow a symlink) and
aged with `stat` (which follows one too). A link planted at a stamp's path then had the tick write the
link's TARGET, or read its mtime/content as the stamp's.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "scripts" / "sysadmin" / "claude_rotate.py"
spec = importlib.util.spec_from_file_location("claude_rotate_stamps", SRC)
cr = importlib.util.module_from_spec(spec)
sys.modules["claude_rotate_stamps"] = cr
spec.loader.exec_module(cr)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    return cr._rotate_state_dir()


def _plant(link: Path, tmp_path: Path, body: str = "victim@ocoron.com\n") -> Path:
    victim = tmp_path / "victim"
    victim.write_text(body)
    old = time.time() - 10 * 86400
    os.utime(victim, (old, old))
    link.symlink_to(victim)
    return victim


def test_touch_stamp_never_writes_through_a_symlink(tmp_path):
    link = tmp_path / "stamp"
    victim = _plant(link, tmp_path)
    before = (victim.read_text(), victim.stat().st_mtime)
    with pytest.raises(OSError):
        cr._touch_stamp(link, time.time(), "x\n")
    with pytest.raises(OSError):
        cr._touch_stamp(link, time.time())
    assert (victim.read_text(), victim.stat().st_mtime) == before


def test_touch_stamp_without_content_keeps_the_stored_verdict(tmp_path):
    stamp = tmp_path / "stamp"
    cr._touch_stamp(stamp, 1000.0, "kept@ocoron.com\n")
    cr._touch_stamp(stamp, 2000.0)
    assert stamp.read_text() == "kept@ocoron.com\n"
    assert stamp.stat().st_mtime == 2000.0
    assert stamp.stat().st_mode & 0o777 == 0o600


def test_a_symlinked_identity_stamp_is_neither_read_nor_written(state, tmp_path):
    link = cr._identity_probe_stamp("ob")
    victim = _plant(link, tmp_path)
    assert cr._identity_probe_result("ob") is None, "the verdict was read through the link"
    assert cr._identity_probe_due(["ob"], time.time()), "a link's mtime held the probe budget"
    cr._identity_probe_record("ob", "new@ocoron.com", time.time())
    assert victim.read_text() == "victim@ocoron.com\n"


def test_a_symlinked_refresh_stamp_is_neither_aged_nor_touched(state, tmp_path, monkeypatch):
    link = cr._fleet_refresh_stamp("ob@ocoron.com")
    victim = _plant(link, tmp_path)
    fresh = time.time()
    os.utime(victim, (fresh, fresh))
    assert cr._refresh_ping_due("ob@ocoron.com", fresh), "a link's fresh mtime suppressed the ping"
    cr._touch_refresh_stamp("ob@ocoron.com")
    assert victim.stat().st_mtime == pytest.approx(fresh)


def test_a_symlinked_drain_stamp_does_not_suppress_the_broadcast(state, tmp_path):
    link = cr._drain_stamp_path()
    victim = _plant(link, tmp_path)
    fresh = time.time()
    os.utime(victim, (fresh, fresh))
    assert cr._regular_stamp_mtime(link) is None
    assert cr._regular_stamp_mtime(victim) == pytest.approx(fresh)


_LEGACY_FUNCS = {
    "_tick_inner",
    "_identity_probe_due",
    "_identity_probe_record",
    "_identity_probe_result",
    "_refresh_ping_due",
    "_touch_refresh_stamp",
    "_fleet_active_wall_advisory",
}


def test_no_listed_function_touches_writes_or_stats_a_stamp_through_a_path_call():
    """The drain write lives deep in `_tick_inner` and the advisory write in
    `_fleet_active_wall_advisory`; a source-level check keeps every listed function off the
    symlink-following calls (`.touch()`, `.write_text(`, `.stat()`, `.read_text(`) on a stamp."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    hits = []
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name in _LEGACY_FUNCS):
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"touch", "write_text", "stat", "read_text"}
                and "stamp" in ast.unparse(node.func.value)
            ):
                hits.append(f"{fn.name}:{node.lineno} {ast.unparse(node)}")
    assert hits == []
