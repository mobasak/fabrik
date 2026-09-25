"""Behavior contract for the work store's PROMPT BLOCK (plan 2026-09-25-plan-1, ticket T02b; spec
D1, D4, D6, V3, V4).

``prompt_block`` prints, in order: the unnamed-window line (D6), the obligation lines (D1), the
awaiting items, this session's claims, one ``on it:`` line per OTHER session holding live claims
(D4), and the ready count — every live claim exactly once. Every test runs against a throwaway git
repo under ``tmp_path`` with an explicit env — never the hub's own store, ``/opt/fabrik-mail`` or
``~/.claude/state``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"

BLOCK = (
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now · B — hold for one more smoke pass\n"
    "- Recommendation: A — the certification gauntlet already passed."
)
UNNAMED = (
    "work: this window has no agent name — owned items cannot reach it; "
    "run python3 scripts/whoami_agent.py --as <name>"
)


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A hermetic process env (in-process calls read it), the window UNNAMED unless a test names
    it: no CLAUDE_AGENT, no session id, an empty identity store under tmp."""
    for sub in ("home", "tmp", "mail", "state/runs"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    out = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "state" / "runs"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "state" / "agent-identity.jsonl"),
    }
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in out.items():
        monkeypatch.setenv(key, value)
    return out


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def _repo(tmp_path: Path, env: dict[str, str], *, store: bool = True) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    repo = work.resolve()
    if store:
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "init", "--distributor", "intel"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, r.stderr
    return repo


def _make(work: ModuleType, repo: Path, title: str, kind: str = "backlog", **fields) -> str:
    links = fields.pop("links", {})
    item = work._new_item(kind=kind, title=title, next_action="", links=links, priority=2)
    item.update(fields)
    work._create_item(repo, item)
    return str(item["id"])


def _claim(work: ModuleType, repo: Path, item_id: str, session: str, agent: str = "") -> dict:
    claim = {"agent": agent, "session": session, "at": time.time(), "lease_s": 7200, "token": 1}
    work._write_claim(repo, item_id, claim)
    return claim


def _mail(inbox: Path, name: str, *, ts: str, ack: str = "required") -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(
        f"---\nid: {name.removesuffix('.md')}\nfrom: fabrik-lib\nto: repo\nts: {ts}\nre:\n"
        f"kind: request\nack: {ack}\nhops: 0\n---\nbody\n",
        encoding="utf-8",
    )


# ── V3: the whole block, in order, every live claim once ────────────────────────────────────


def test_the_block_shows_mail_awaiting_your_claims_each_other_session_and_ready_minus_next(
    tmp_path, env, monkeypatch
):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    ts = (datetime.now(UTC) - timedelta(hours=5, minutes=10)).isoformat()
    _mail(tmp_path / "mail" / "repo" / "inbox", "01AAAAAAAAAAAAAAAAAAAAAAAA.md", ts=ts)
    dec = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="sess-ask")
    mine = _make(work, repo, "mine")
    b1, b2 = _make(work, repo, "b one"), _make(work, repo, "b two")
    c1 = _make(work, repo, "c one")
    free = _make(work, repo, "free")
    _make(work, repo, "keep going", kind="next", links={"session": "sess-other"})
    my_claim = _claim(work, repo, mine, "sess-me-0001", agent="infra")
    for item_id in sorted([b2, b1], reverse=True):  # written out of order; printed sorted
        _claim(work, repo, item_id, "sess-bbbb-2222", agent="fleet")
    _claim(work, repo, c1, "sess-cccc-3333")
    lines = work.prompt_block(repo, "sess-me-0001").splitlines()
    end = work._iso(work._claim_end(my_claim))
    assert lines == [
        "work: mail: 1 need an answer (oldest 5 h) — python3 scripts/mail.py list",
        f"work: awaiting operator — {dec} (gate): Deploy the certified build to production now?",
        f"work: your claim — {mine}: mine (token 1, lease until {end})",
        f"work: on it: sess-bbb (fleet) — {', '.join(sorted([b1, b2]))}",
        f"work: on it: sess-ccc (unnamed) — {c1}",
        "work: 1 ready — `work.py next`",
    ], lines
    block = "\n".join(lines)
    for item_id in (mine, b1, b2, c1):
        assert block.count(item_id) == 1, item_id
    assert free not in block  # the ready count is a count, never a list


def test_another_sessions_claim_is_on_its_on_it_line_never_a_your_claim_line(
    tmp_path, env, monkeypatch
):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    a = _make(work, repo, "alpha")
    _claim(work, repo, a, "S1", agent="fleet")
    for session in ("S2", ""):  # a session-less caller owns no claim: every one is "on it"
        lines = work.prompt_block(repo, session).splitlines()
        assert lines == [f"work: on it: S1 (fleet) — {a}"], (session, lines)
    assert work.prompt_block(repo, "S1").splitlines()[0].startswith(f"work: your claim — {a}: ")


def test_an_on_it_line_over_line_max_shows_whole_ids_and_says_how_many_more(
    tmp_path, env, monkeypatch
):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    ids = sorted(_make(work, repo, f"t{i}") for i in range(40))
    for item_id in ids:
        _claim(work, repo, item_id, "sess-many", agent="fleet")
    (line,) = work.prompt_block(repo, "me").splitlines()
    assert len(line) <= work.LINE_MAX, line
    head = "work: on it: sess-man (fleet) — "
    assert line.startswith(head), line
    listed, _, more = line[len(head) :].rpartition(" … and ")
    shown = listed.split(", ")
    assert shown == ids[: len(shown)], line  # every shown id whole, in order
    assert more.endswith(" more") and len(shown) + int(more.removesuffix(" more")) == 40, line


def test_an_on_it_line_that_fits_is_unchanged_by_the_fitting(tmp_path, env, monkeypatch):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    ids = sorted(_make(work, repo, f"t{i}") for i in range(3))
    for item_id in ids:
        _claim(work, repo, item_id, "sess-few", agent="fleet")
    assert work.prompt_block(repo, "me") == f"work: on it: sess-few (fleet) — {', '.join(ids)}"


# ── a live claim on a closed or resolved item prints nowhere (ready's ``(yours)`` rule) ─────


def test_a_live_claim_on_a_resolved_or_closed_item_prints_no_claim_line(tmp_path, env, monkeypatch):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    done = _make(work, repo, "done one", status="done")
    marked = _make(work, repo, "marked closed")
    mine, theirs = _make(work, repo, "mine"), _make(work, repo, "theirs")
    for item_id in (done, mine):  # done: this session's lease its close failed to end
        _claim(work, repo, item_id, "S1", agent="infra")
    _claim(work, repo, theirs, "S2", agent="fleet")
    _claim(work, repo, marked, "S2", agent="fleet")  # marked: another session's stale lease
    real_closed = work._closed_ids
    monkeypatch.setattr(work, "_closed_ids", lambda r: real_closed(r) | {marked})
    block = work.prompt_block(repo, "S1")
    assert done not in block and marked not in block, block
    mine_claim = work._claim_of(repo, mine)
    # the open items' lines are byte-identical to the unfiltered block's
    assert block.splitlines() == [
        f"work: your claim — {mine}: mine (token 1, lease until "
        f"{work._iso(work._claim_end(mine_claim))})",
        f"work: on it: S2 (fleet) — {theirs}",
    ], block


# ── a non-string session is compared as a string in both loops ──────────────────────────────


def test_a_non_string_claim_session_prints_on_exactly_one_line(tmp_path, env, monkeypatch):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    a = _make(work, repo, "alpha")
    claim = {"agent": "fleet", "session": 42, "at": time.time(), "lease_s": 7200, "token": 1}
    work._write_claim(repo, a, claim)
    mine = work.prompt_block(repo, "42").splitlines()
    assert len(mine) == 1 and mine[0].startswith(f"work: your claim — {a}: alpha "), mine
    assert work.prompt_block(repo, "S2").splitlines() == [f"work: on it: 42 (fleet) — {a}"]


# ── the unchanged inputs ────────────────────────────────────────────────────────────────────


def test_own_claims_only_prints_no_on_it_line_and_the_old_lines_byte_for_byte(
    tmp_path, env, monkeypatch
):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    work = _work_module()
    dec = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="S9")
    a = _make(work, repo, "alpha")
    _make(work, repo, "beta")
    _make(work, repo, "gamma")
    claim = _claim(work, repo, a, "S1", agent="infra")
    block = work.prompt_block(repo, "S1")
    assert block == (
        f"work: awaiting operator — {dec} (gate): Deploy the certified build to production now?\n"
        f"work: your claim — {a}: alpha (token 1, lease until "
        f"{work._iso(work._claim_end(claim))})\n"
        "work: 2 ready — `work.py next`"
    ), block
    assert "on it:" not in block


# ── D6: the unnamed window ──────────────────────────────────────────────────────────────────


def test_an_unnamed_window_is_told_so_first_and_a_named_one_on_an_empty_store_gets_nothing(
    tmp_path, env, monkeypatch
):
    repo = _repo(tmp_path, env)
    work = _work_module()
    assert work.prompt_block(repo, "S1") == UNNAMED
    # the line comes FIRST, ahead of the obligation lines
    ts = datetime.now(UTC).isoformat()
    _mail(tmp_path / "mail" / "repo" / "inbox", "01BBBBBBBBBBBBBBBBBBBBBBBB.md", ts=ts)
    assert work.prompt_block(repo, "S1").splitlines() == [
        UNNAMED,
        "work: mail: 1 need an answer (oldest 0 h) — python3 scripts/mail.py list",
    ]
    for p in (tmp_path / "mail" / "repo" / "inbox").iterdir():
        p.unlink()
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert work.prompt_block(repo, "S1") == ""
    # a binding names the window too: no CLAUDE_AGENT, the session bound in the identity store
    monkeypatch.delenv("CLAUDE_AGENT")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-bound")
    Path(env["AGENT_IDENTITY_FILE"]).write_text(
        json.dumps({"session_id": "sess-bound", "name": "fleet"}) + "\n", encoding="utf-8"
    )
    assert work.prompt_block(repo, "sess-bound") == ""


def test_a_window_bound_to_the_passed_session_is_named_when_the_hook_has_no_session_env(
    tmp_path, env, monkeypatch
):
    """The hook hands prompt_block the payload's session; its process may carry no
    CLAUDE_CODE_SESSION_ID, so the binding is read for the passed session."""
    repo = _repo(tmp_path, env)
    work = _work_module()
    rows = [
        {"session_id": "sess-bound", "name": "intel"},
        {"session_id": "sess-other", "name": "fleet"},
        {"session_id": "sess-bound", "name": "infra"},  # the LAST row for the session wins
        {"session_id": "sess-bad", "name": "Not A Name"},
    ]
    Path(env["AGENT_IDENTITY_FILE"]).write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    assert work.prompt_block(repo, "sess-bound") == ""
    assert work._agent_name(session="sess-bound") == "infra"
    # unchanged: a caller passing no session, an unbound or badly named one, stays unnamed
    assert work._agent_name() == ""
    assert work.prompt_block(repo, "sess-none") == UNNAMED
    assert work.prompt_block(repo, "sess-bad") == UNNAMED
    # unchanged: CLAUDE_CODE_SESSION_ID, when set, wins over the passed session
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-unbound")
    assert work.prompt_block(repo, "sess-bound") == UNNAMED
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess-other")
    assert work._agent_name(session="sess-bound") == "fleet"


def test_a_store_less_repo_stays_empty_even_in_an_unnamed_window(tmp_path, env):
    repo = _repo(tmp_path, env, store=False)
    assert _work_module().prompt_block(repo, "S1") == ""


# ── V4: the budget on a hub-sized inbox and ledger ──────────────────────────────────────────


def test_the_block_returns_in_under_half_a_second_on_a_hub_sized_inbox_and_ledger(
    tmp_path, env, monkeypatch
):
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    repo = _repo(tmp_path, env)
    (repo / "commands" / "_sources").mkdir(parents=True)  # the corpus repo: the feedback line
    work = _work_module()
    inbox = tmp_path / "mail" / "repo" / "inbox"
    now = datetime.now(UTC)
    for i in range(60):
        ts = (now - timedelta(hours=i)).isoformat()
        _mail(inbox, f"01M{i:023d}.md", ts=ts, ack="required" if i % 4 else "no")
    rows = []
    for i in range(500):
        rows.append({"command": f"fabrik-c{i % 12}", "change": f"lean: edit {i}", "ts": 1.7e9 + i})
    ledger = tmp_path / "state" / "command-feedback.jsonl"
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for i in range(12):
        item_id = _make(work, repo, f"item {i}")
        if i % 3 == 0:
            _claim(work, repo, item_id, f"sess-{i:04d}-xx", agent="fleet")
    monkeypatch.setattr(work, "_SIBLING_CACHE", {})  # a hook is a fresh process: pay the imports
    t0 = time.perf_counter()
    block = work.prompt_block(repo, "sess-me")
    elapsed = time.perf_counter() - t0
    lines = block.splitlines()
    assert lines[0] == "work: mail: 45 need an answer (oldest 2 d) — python3 scripts/mail.py list"
    assert lines[1].startswith("work: feedback queues: fabrik-c0 42 · "), lines
    assert sum(ln.startswith("work: on it: ") for ln in lines) == 4, lines
    assert elapsed < 0.5, f"prompt_block took {elapsed:.3f} s"
    print(f"V4 prompt_block wall time: {elapsed * 1000:.1f} ms")
