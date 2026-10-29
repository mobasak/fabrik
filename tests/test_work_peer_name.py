"""A builder's prompt block carries the coordinator's LIVE peer address (W-9bf5a363).

The hub coordinator runs in the code-server extension, where every rotation starts a new process
with an auto-generated peer name, and no program can rename a session (only `/rename` or `--name`,
typed by a human). Builders that messaged a name kept in their notes reached nobody (infra-3's
rotate request to `fabrik-ec` sat 14 h). So every builder prompt resolves the coordinator's live
session names (`mail.py who`) and prints them; the line's text changes exactly when the address
does, which makes the prompt hook's unchanged-block dedup re-show it at each rotation.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
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


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repo whose store names `coord` its distributor; git reads no user config."""
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
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    (tmp_path / "home").mkdir()
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(repo)], check=True)
    (repo / "README").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True)
    r = subprocess.run(
        ["python3", str(SCRIPT), "init", "--distributor", "coord"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return repo.resolve()


def _block(w, repo: Path, *, builder: str, names, monkeypatch) -> tuple[str, list[dict]]:
    """prompt_block with the builder role and the live-name resolver stubbed; returns the block and
    every resolver call (agent and keyword args), so the 1 s cap is asserted, not assumed."""
    calls: list[dict] = []

    def fake_sessions_of(agent, main, **kw):
        calls.append({"agent": agent, **kw})
        if isinstance(names, Exception):
            raise names
        return list(names)

    monkeypatch.setattr(w, "_builder", lambda tree, session="": builder)
    monkeypatch.setattr(w, "_sessions_of", fake_sessions_of)
    return w.prompt_block(repo, SID), calls


def _peer_lines(block: str) -> list[str]:
    return [ln for ln in block.splitlines() if ln.startswith("work: coordinator (")]


def test_a_builder_is_given_the_coordinators_live_address(store, monkeypatch):
    w = _work()
    block, calls = _block(w, store, builder="w1", names=["fabrik-a5"], monkeypatch=monkeypatch)
    assert _peer_lines(block) == ["work: coordinator (coord) → SendMessage to=fabrik-a5"], block
    assert calls == [{"agent": "coord", "timeout": 1.0}], calls
    # the address does not change → neither does the line (the dedup stays silent); it does → it does
    again, _ = _block(w, store, builder="w1", names=["fabrik-a5"], monkeypatch=monkeypatch)
    moved, _ = _block(w, store, builder="w1", names=["fabrik-ec"], monkeypatch=monkeypatch)
    assert _peer_lines(again) == _peer_lines(block)
    assert _peer_lines(moved) == ["work: coordinator (coord) → SendMessage to=fabrik-ec"]


def test_several_live_names_are_all_listed(store, monkeypatch):
    w = _work()
    block, _ = _block(
        w, store, builder="w1", names=["coordinator", "fabrik-a5"], monkeypatch=monkeypatch
    )
    lines = _peer_lines(block)
    assert len(lines) == 1, block
    line = lines[0]
    assert line.startswith("work: coordinator (coord) → SendMessage to=coordinator · to=fabrik-a5")
    assert "several windows answer for it" in line and "stale" in line


def test_no_line_for_the_coordinator_outside_mode_or_with_no_live_window(store, monkeypatch):
    w = _work()
    # the coordinator itself (and any non-builder) gets no line, and the resolver is never paid for
    own, calls = _block(w, store, builder="", names=["fabrik-a5"], monkeypatch=monkeypatch)
    assert _peer_lines(own) == [] and calls == [], (own, calls)
    # no live (or no bound) coordinator window → no line
    none_live, _ = _block(w, store, builder="w1", names=[], monkeypatch=monkeypatch)
    assert _peer_lines(none_live) == [], none_live
    # outside coordinator mode the REAL `_builder` names nobody, so the resolver is never called
    w2 = _work()
    called: list[str] = []
    monkeypatch.setattr(w2, "_sessions_of", lambda agent, main, **kw: called.append(agent) or ["x"])
    plain = w2.prompt_block(store, SID)
    assert _peer_lines(plain) == [] and called == [], (plain, called)


def test_unsafe_names_dropped_and_resolver_capped_and_errors_fail_open(store, monkeypatch):
    w = _work()
    hostile = ["evil`name", "a b", "x" * 65, "ok-name_1.2"]
    block, _ = _block(w, store, builder="w1", names=hostile, monkeypatch=monkeypatch)
    assert _peer_lines(block) == ["work: coordinator (coord) → SendMessage to=ok-name_1.2"], block
    only_bad, _ = _block(w, store, builder="w1", names=["evil`name"], monkeypatch=monkeypatch)
    assert _peer_lines(only_bad) == [], only_bad
    # a resolver that raises costs only this line: the rest of the block still renders
    base, _ = _block(w, store, builder="w1", names=[], monkeypatch=monkeypatch)
    broken, _ = _block(w, store, builder="w1", names=OSError("boom"), monkeypatch=monkeypatch)
    assert broken == base, (broken, base)
