"""A builder's prompt block carries the coordinator's LIVE peer address (W-9bf5a363).

The hub coordinator runs in the code-server extension, where every rotation starts a new process
with an auto-generated peer name, and no program can rename a session (only `/rename` or `--name`,
typed by a human). Builders that messaged a name kept in their notes reached nobody (infra-3's
rotate request to `fabrik-ec` sat 14 h). So every builder prompt resolves the coordinator's live
session names (`mail.py who`) and prints them.

Every test drives the REAL `prompt_block` over a real repo: a coordinator-mode store (or not) with a
real pool worktree, so the builder gate is the shipped one. Only the live-name resolver is stubbed,
except in the test that drives the real `_sessions_of` to its subprocess.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
SID = "sid-builder"


def _work():
    spec = importlib.util.spec_from_file_location("work_peer_name", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mode: bool, role: str = "coord"):
    """A repo whose store names `role` its distributor, `coordinator_mode` set or not, committed,
    then one pool worktree `.claude/worktrees/w1` carrying that commit. Returns (main, w1)."""
    for k, v in {
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "mail"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "identity.jsonl"),
        "FABRIK_WORK_PROC": str(tmp_path / "proc"),  # an empty /proc: no live windows rekey a tree
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    (tmp_path / "home").mkdir()
    (tmp_path / "proc").mkdir()
    main = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(main)], check=True)
    (main / "README").write_text("seed\n", encoding="utf-8")
    _git(main, "add", "README")
    _git(main, "commit", "-q", "-m", "seed")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "init", "--distributor", "coord"],
        cwd=main,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    cfg_path = main / ".fabrik" / "work" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["distributor"] = role
    if mode:
        cfg["coordinator_mode"] = True
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    _git(main, "add", ".fabrik")
    _git(main, "commit", "-q", "-m", "store")
    w1 = main / ".claude" / "worktrees" / "w1"
    _git(main, "worktree", "add", "-q", "-b", "w-w1", str(w1))
    return main.resolve(), w1.resolve()


def _block(w, tree: Path, names, monkeypatch) -> tuple[str, list[dict]]:
    """The REAL prompt_block for `tree` with only the live-name resolver stubbed; returns the block
    and every resolver call (agent and keyword args)."""
    calls: list[dict] = []

    def fake_sessions_of(agent, main, **kw):
        calls.append({"agent": agent, **kw})
        if isinstance(names, Exception):
            raise names
        return list(names)

    monkeypatch.setattr(w, "_sessions_of", fake_sessions_of)
    return w.prompt_block(tree, SID), calls


def _peer_lines(block: str) -> list[str]:
    return [ln for ln in block.splitlines() if ln.startswith("work: coordinator (")]


def test_a_builder_is_given_the_coordinators_live_address(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=True)
    w = _work()
    block, calls = _block(w, w1, ["fabrik-a5"], monkeypatch)
    assert _peer_lines(block) == ["work: coordinator (coord) → SendMessage to=fabrik-a5"], block
    assert calls == [{"agent": "coord", "timeout": 1.0}], calls
    # the line's text moves exactly when the address does (what the prompt hook's dedup compares)
    again, _ = _block(w, w1, ["fabrik-a5"], monkeypatch)
    moved, _ = _block(w, w1, ["fabrik-ec"], monkeypatch)
    assert _peer_lines(again) == _peer_lines(block)
    assert _peer_lines(moved) == ["work: coordinator (coord) → SendMessage to=fabrik-ec"]


def test_several_live_names_are_all_listed_and_never_cut(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=True)
    w = _work()
    block, _ = _block(w, w1, ["coordinator", "fabrik-a5"], monkeypatch)
    lines = _peer_lines(block)
    assert len(lines) == 1, block
    assert lines[0] == (
        "work: coordinator (coord) → SendMessage to=coordinator · to=fabrik-a5"
        " (several windows answer for it — one may be stale)"
    )
    # five 64-character names cannot all fit in one prompt line: whole names only, the rest counted
    long = [chr(ord("a") + i) * 64 for i in range(5)]
    wide, _ = _block(w, w1, long, monkeypatch)
    (line,) = _peer_lines(wide)
    assert len(line) <= 300, line
    shown = re.findall(r"to=(\S+)", line)
    assert shown and all(name in long for name in shown), line  # every printed name is WHOLE
    assert f" … and {5 - len(shown)} more" in line and line.endswith("one may be stale)"), line


def test_no_line_for_the_coordinator_outside_mode_or_with_no_live_window(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=True)
    w = _work()
    # the main checkout (the coordinator's own tree) is not a builder: no line, resolver unpaid
    own, calls = _block(w, main, ["fabrik-a5"], monkeypatch)
    assert _peer_lines(own) == [] and calls == [], (own, calls)
    # a builder with no live (or no bound) coordinator window gets no line
    none_live, _ = _block(w, w1, [], monkeypatch)
    assert _peer_lines(none_live) == [], none_live


def test_a_headless_builder_gets_no_line_and_pays_no_lookup(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=True)
    w = _work()
    monkeypatch.setattr(w, "_print_mode", lambda: True)
    block, calls = _block(w, w1, ["fabrik-a5"], monkeypatch)
    assert _peer_lines(block) == [] and calls == [], (block, calls)


def test_no_line_in_a_repo_outside_coordinator_mode(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=False)
    w = _work()
    block, calls = _block(w, w1, ["fabrik-a5"], monkeypatch)
    assert _peer_lines(block) == [] and calls == [], (block, calls)


@pytest.mark.parametrize("role", ["", "-x", "Coord", "a b"])
def test_a_role_that_is_not_an_agent_name_adds_no_line(tmp_path, monkeypatch, role):
    main, w1 = _make(tmp_path, monkeypatch, mode=True, role=role)
    w = _work()
    monkeypatch.setattr(
        w, "_builder", lambda tree, session="": "w1"
    )  # a bad role must not name one
    block, calls = _block(w, w1, ["fabrik-a5"], monkeypatch)
    assert _peer_lines(block) == [] and calls == [], (block, calls)


def test_unsafe_names_dropped_and_errors_fail_open(tmp_path, monkeypatch):
    main, w1 = _make(tmp_path, monkeypatch, mode=True)
    w = _work()
    hostile = ["evil`name", "a b", "x" * 65, "a;rm", "café", "y" * 64]
    block, _ = _block(w, w1, hostile, monkeypatch)
    assert _peer_lines(block) == [f"work: coordinator (coord) → SendMessage to={'y' * 64}"], block
    only_bad, _ = _block(w, w1, ["evil`name"], monkeypatch)
    assert _peer_lines(only_bad) == [], only_bad
    # a resolver that raises costs only this line: the rest of the block still renders
    base, _ = _block(w, w1, [], monkeypatch)
    broken, _ = _block(w, w1, OSError("boom"), monkeypatch)
    assert broken == base, (broken, base)


def test_the_real_resolver_passes_its_timeout_and_a_timeout_is_no_names(tmp_path, monkeypatch):
    w = _work()
    seen: list[float] = []

    def slow_run(argv, **kw):
        seen.append(kw.get("timeout"))
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))

    monkeypatch.setattr(w.subprocess, "run", slow_run)
    assert w._sessions_of("coord", tmp_path, timeout=1.0) == []
    assert w._sessions_of("coord", tmp_path) == []
    assert seen == [1.0, 5], seen  # the prompt path's cap reaches subprocess; others keep 5 s
