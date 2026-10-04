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


_FOLLOWING_IO = {"touch", "write_text", "write_bytes", "read_text", "read_bytes", "stat", "open"}


def _functions():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    return {fn.name: fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)}


def test_no_listed_function_does_symlink_following_file_io_at_all():
    """The drain write lives deep in `_tick_inner` and the advisory write in
    `_fleet_active_wall_advisory`; a source-level check keeps every listed function off the
    symlink-following Path calls on ANY receiver — not just one named `*stamp*`, which an alias
    walked straight past (review round 1) — so stamp IO there can only go through the helpers."""
    fns = _functions()
    assert not (_LEGACY_FUNCS - set(fns)), _LEGACY_FUNCS - set(fns)
    hits = [
        f"{name}:{node.lineno} {ast.unparse(node)}"
        for name in _LEGACY_FUNCS
        for node in ast.walk(fns[name])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _FOLLOWING_IO
    ]
    assert hits == []


def test_a_planted_symlink_at_the_advisory_stamp_is_removed_not_followed(state, tmp_path):
    """The advisory's latch reads the stamp with `exists()` and `_promised_resume`, both of which
    follow a link: a link to a file promising a far-future resume kept the fleet silent."""
    link = cr._fleet_exhaustion_stamp()
    body = cr._stamp_body(str(int(time.time()) + 10**8), "walled")
    victim = _plant(link, tmp_path, body)
    cr._drop_planted_stamp(link)
    assert not link.exists() and not link.is_symlink()
    assert victim.read_text() == body, "the link's target was touched"
    regular = link
    cr._touch_stamp(regular, time.time(), "0\nwalled\n")
    cr._drop_planted_stamp(regular)
    assert regular.is_file(), "a real stamp must never be removed"


def test_the_advisory_drops_a_planted_link_before_it_reads_the_stamp():
    fn = _functions()["_fleet_active_wall_advisory"]
    drop = [
        n.lineno
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "_drop_planted_stamp"
    ]
    reads = [
        n.lineno
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Attribute) and n.func.attr in {"exists", "is_file"})
            or ast.unparse(n.func) in {"_promised_resume", "_stamp_tier", "_regular_stamp_mtime"}
        )
    ]
    assert drop and reads and min(drop) < min(reads)
