"""Behavior contract for the work store's VIEW (plan 2026-09-25-plan-1, ticket T02a; spec D1, D4).

``obligations`` reads the mailbox and the command-feedback queues LIVE (never copied, never a
file moved); ``ready`` is crisp by default (yours, owned, awaiting, then the top 10 others) and
``ready --all`` is the old full list; ``kind: next`` items are their session's and never ready;
``status`` carries the distributor's lines. Every test runs against a throwaway git repo under
``tmp_path`` with an explicit env — never the hub's own store, ``/opt/fabrik-mail`` or
``~/.claude/state``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
CFR = REPO / "scripts" / "command_feedback_report.py"


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp", "mail", "state/runs"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return {
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
    }


def _as(env: dict[str, str], agent: str | None = None, session: str | None = None) -> dict:
    out = {k: v for k, v in env.items() if k not in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID")}
    if agent:
        out["CLAUDE_AGENT"] = agent
    if session:
        out["CLAUDE_CODE_SESSION_ID"] = session
    return out


def _apply(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    """Make this process's environment exactly ``env`` for the in-process calls."""
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _repo(tmp_path: Path, env: dict[str, str], *, store: bool = True) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    repo = work.resolve()
    if store:
        _ok(["init", "--distributor", "intel"], env, repo)
    return repo


def _add(repo: Path, env: dict[str, str], title: str, priority: int = 2) -> str:
    out = _ok(
        ["add", "--kind", "backlog", "--title", title, "--priority", str(priority)], env, repo
    )
    return Path(out.strip().splitlines()[-1]).stem


def _edit(repo: Path, item_id: str, **fields: object) -> None:
    p = repo / ".fabrik" / "work" / f"{item_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ids(stdout: str) -> list[str]:
    return [ln.split()[0] for ln in stdout.splitlines() if ln.startswith("W-")]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _make(
    work: ModuleType,
    repo: Path,
    kind: str,
    title: str,
    links: dict[str, str] | None = None,
    **fields: object,
) -> str:
    """A ``kind`` item written through the module's own constructors (``add`` refuses next and
    mail) — ``fields`` land on the item before it is created."""
    links = links or {}
    item = work._new_item(kind=kind, title=title, next_action="", links=links, priority=2)
    item.update(fields)
    work._create_item(repo, item)
    return str(item["id"])


def _mail(inbox: Path, name: str, *, ack: str, ts: str) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    p = inbox / name
    p.write_text(
        "---\n"
        f"id: {name.removesuffix('.md')}\n"
        "from: fabrik-lib\n"
        "to: repo\n"
        f"ts: {ts}\n"
        "re:\n"
        "kind: request\n"
        f"ack: {ack}\n"
        "hops: 0\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    return p


# ── D1: obligations ─────────────────────────────────────────────────────────────────────────


def test_obligations_counts_ack_required_mail_by_the_oldest_epoch_and_moves_nothing(
    tmp_path, monkeypatch
):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, store=False)
    wt = tmp_path / "linked"
    _git(repo, env, "worktree", "add", "-q", "-b", "side", str(wt))
    _apply(monkeypatch, env)
    now = datetime.now(UTC)
    inbox = tmp_path / "mail" / "repo" / "inbox"  # named by the MAIN checkout, not "linked"
    # the OLDER message carries the lexically LARGER stamp (a +14:00 offset): a string minimum
    # of the raw stamps picks the younger one and reads 2 d, the epoch minimum reads 3 d
    older = (now - timedelta(days=3)).astimezone(timezone(timedelta(hours=14)))
    younger = (now - timedelta(days=2, hours=15)).replace(tzinfo=None)
    _mail(inbox, "01AAAAAAAAAAAAAAAAAAAAAAAA.md", ack="required", ts=older.isoformat())
    _mail(inbox, "01BBBBBBBBBBBBBBBBBBBBBBBB.md", ack="required", ts=younger.isoformat())
    _mail(
        inbox, "01CCCCCCCCCCCCCCCCCCCCCCCC.md", ack="no", ts=(now - timedelta(days=9)).isoformat()
    )
    _mail(inbox, ".01DDDDDDDDDDDDDDDDDDDDDDDD.md", ack="required", ts=now.isoformat())
    bad = inbox / "01EEEEEEEEEEEEEEEEEEEEEEEE.md"
    bad.write_text("not a frontmatter block\n", encoding="utf-8")
    before = sorted(p.name for p in inbox.iterdir())
    lines = _work_module().obligations(wt.resolve())
    assert lines == ["mail: 2 need an answer (oldest 3 d) — python3 scripts/mail.py list"], lines
    assert sorted(p.name for p in inbox.iterdir()) == before  # nothing moved, nothing quarantined
    assert bad.read_text(encoding="utf-8") == "not a frontmatter block\n"


def test_obligations_states_an_age_under_a_day_in_hours_and_no_mail_is_no_line(
    tmp_path, monkeypatch
):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, store=False)
    _apply(monkeypatch, env)
    work = _work_module()
    assert work.obligations(repo) == []  # no mailbox at all
    inbox = tmp_path / "mail" / "repo" / "inbox"
    _mail(inbox, "01FFFFFFFFFFFFFFFFFFFFFFFF.md", ack="no", ts=datetime.now(UTC).isoformat())
    assert work.obligations(repo) == []  # ack: no is information, never counted
    ts = (datetime.now(UTC) - timedelta(hours=5, minutes=10)).isoformat()
    _mail(inbox, "01GGGGGGGGGGGGGGGGGGGGGGGG.md", ack="required", ts=ts)
    assert work.obligations(repo) == [
        "mail: 1 need an answer (oldest 5 h) — python3 scripts/mail.py list"
    ]


def _cfr() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_test_view_cfr", CFR)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_obligations_feedback_line_is_the_three_deepest_real_queue_depths(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, store=False)
    _apply(monkeypatch, env)
    ledger = tmp_path / "state" / "command-feedback.jsonl"  # COMMAND_RUN_DIR's parent
    rows = []
    ts = 1_700_000_000.0
    for cmd, n in (("fabrik-review", 5), ("fabrik-task", 4), ("fabrik-spec", 3), ("fabrik-x", 1)):
        for _ in range(n):
            ts += 1
            rows.append({"command": cmd, "change": f"lean: edit {ts}", "ts": ts})
    rows.append({"command": "fabrik-x", "change": "none", "ts": ts + 1})
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    work = _work_module()
    # no commands/_sources — not the corpus repo — no feedback line
    assert work.obligations(repo) == []
    (repo / "commands" / "_sources").mkdir(parents=True)
    depths = _cfr().queue_depths()  # the REAL reader, against the same default ledger
    assert depths == {"fabrik-review": 5, "fabrik-task": 4, "fabrik-spec": 3, "fabrik-x": 1}
    assert work.obligations(repo) == [
        "feedback queues: fabrik-review 5 · fabrik-task 4 · fabrik-spec 3"
        " — /fabrik-command-improve <command>"
    ]
    ledger.unlink()  # a missing ledger is an empty mapping — no line
    assert work.obligations(repo) == []


# ── D4: ready ───────────────────────────────────────────────────────────────────────────────


def test_ready_is_yours_owned_awaiting_then_ten_others_and_all_is_the_old_list(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    me = _as(env, agent="infra", session="sess-me")
    claimed = _add(repo, env, "claimed", priority=3)
    owned = _add(repo, env, "owned", priority=3)
    awaiting = _add(repo, env, "awaiting", priority=3)
    others = [_add(repo, env, f"other {i:02d}", priority=i % 2) for i in range(14)]
    _edit(repo, owned, owner="infra")
    _edit(repo, awaiting, status="awaiting-operator")
    _ok(["claim", claimed], me, repo)
    out = _ok(["ready"], me, repo).splitlines()
    ordered_others = [o for o in others if others.index(o) % 2 == 0] + [
        o for o in others if others.index(o) % 2 == 1
    ]
    assert out[0].startswith(claimed) and out[0].endswith(" (yours)"), out
    assert _ids("\n".join(out)) == [claimed, owned, awaiting, *ordered_others[:10]], out
    assert out[-1] == "… and 4 more — work.py ready --all", out
    assert len(out) == 14
    every = _ok(["ready", "--all"], me, repo)
    assert _ids(every) == [*ordered_others, owned], every
    assert "(yours)" not in every and "more" not in every


# ── kind: next is its session's ─────────────────────────────────────────────────────────────


def test_a_next_item_is_never_ready_but_status_lists_it(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _apply(monkeypatch, env)
    work = _work_module()
    nxt = _make(
        work,
        repo,
        "next",
        "keep going",
        links={"session": "sess-a"},
        next_at=_iso(datetime.now(UTC)),
    )
    me = _as(env, session="sess-b")
    assert nxt not in _ok(["ready"], me, repo)
    assert nxt not in _ok(["ready", "--all"], me, repo)
    assert nxt not in _ok(["next"], me, repo)
    assert "ready" not in work.prompt_block(repo, "sess-b")  # the prompt's count skips it too
    assert nxt in _ok(["status"], me, repo)


# ── D4: status ──────────────────────────────────────────────────────────────────────────────


def test_status_prints_claims_per_session_stale_next_unowned_and_aged_mail(tmp_path, monkeypatch):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _apply(monkeypatch, env)
    work = _work_module()
    old = _iso(datetime.now(UTC) - timedelta(days=15))
    for i in range(51):
        _make(work, repo, "mail", f"mail {i}", links={"mail": f"01M{i:023d}"}, created=old)
    young = _make(work, repo, "mail", "young mail", links={"mail": "01YOUNG"})
    stale = _make(
        work,
        repo,
        "next",
        "stale",
        links={"session": "sessionAAAA-1"},
        next_at=_iso(datetime.now(UTC) - timedelta(days=7)),
    )
    fresh = _make(
        work,
        repo,
        "next",
        "fresh",
        links={"session": "sessionBBBB-2"},
        next_at=_iso(datetime.now(UTC)),
    )
    six = [_add(repo, env, f"a{i}") for i in range(6)]
    one = _add(repo, env, "b")
    owned = _add(repo, env, "owned")
    _edit(repo, owned, owner="fleet")
    for item in six:
        _ok(["claim", item], _as(env, agent="infra", session="sessionAAAA-1"), repo)
    _ok(["claim", one], _as(env, session="sessionBBBB-2"), repo)
    out = _ok(["status"], env, repo).splitlines()
    # 52 mail + 7 backlog items are open with no owner; the next items are sessions', not counted
    assert "UNOWNED          59 open item(s) with no owner" in out, out
    assert "CLAIMS           sessionA (infra) 6 — over 5" in out, out
    assert "CLAIMS           sessionB (unnamed) 1" in out, out
    assert f"STALE NEXT       {stale} sessionA set 7 d ago" in out, out
    assert not any(ln.startswith("STALE NEXT") and fresh in ln for ln in out), out
    assert "AGED MAIL        51 open mail item(s) created more than 14 days ago — over 50" in out
    assert young in "\n".join(out)
    head = [ln.split()[0] for ln in out[:5]]
    assert head == ["UNOWNED", "CLAIMS", "CLAIMS", "STALE", "AGED"], out[:6]
