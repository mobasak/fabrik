"""Behavior contract for the Stop harvest's NEXT rules (plan 2026-09-25-plan-1, ticket T05a).

``on_harvest`` sorts the turn's NEXT with ``classify_next`` and the first rule decides: a hold
claims nothing; a line naming an item claims the first open, ready item no other live session
holds; free text the register accepted (``next_anchored``) becomes the session's one ``next``
item; and every harvest closes ``next`` items idle for 7 days. Every test runs against a
throwaway git repo under ``tmp_path`` — never the hub's own store.
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


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "tmp" / "state" / "agent-identity.jsonl"),
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


@pytest.fixture
def store(tmp_path, monkeypatch):
    """(module, repo, env): a repo with an initialised store; the process env made hermetic."""
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    repo = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    repo = repo.resolve()
    _ok(["init", "--distributor", "intel"], env, repo)
    return _work_module(), repo, env


def _add(repo: Path, env: dict[str, str], title: str = "T") -> str:
    out = _ok(["add", "--kind", "backlog", "--title", title], env, repo)
    return Path(out.strip().splitlines()[-1]).stem


def _file(repo: Path, item_id: str) -> Path:
    return repo / ".fabrik" / "work" / f"{item_id}.json"


def _item(repo: Path, item_id: str) -> dict:
    return json.loads(_file(repo, item_id).read_text(encoding="utf-8"))


def _set(repo: Path, item_id: str, **fields: object) -> None:
    data = _item(repo, item_id)
    data.update(fields)
    _file(repo, item_id).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", "utf-8")


def _claim(repo: Path, item_id: str) -> dict | None:
    p = repo / ".git" / "fabrik-work" / "claims" / f"{item_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _live_session(repo: Path, item_id: str) -> str | None:
    c = _claim(repo, item_id)
    if not c or c["at"] + c["lease_s"] <= time.time():
        return None
    return c["session"]


def _next_items(repo: Path, session: str | None = None) -> list[dict]:
    out = []
    for p in sorted((repo / ".fabrik" / "work").glob("W-*.json")):
        it = json.loads(p.read_text(encoding="utf-8"))
        if it.get("kind") == "next" and (session is None or it["links"].get("session") == session):
            out.append(it)
    return out


def _open_next(repo: Path, session: str) -> list[dict]:
    return [it for it in _next_items(repo, session) if it["status"] == "open"]


def _snapshot(repo: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in (repo / ".fabrik" / "work").glob("W-*.json")}


def _iso_days_ago(days: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ── classify_next ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("line", "want"),
    [
        ("none — terminal", "hold"),
        ("None — terminal", "hold"),
        ("BLOCKED: x", "hold"),
        ("blocked: missing infra", "hold"),
        ("awaiting operator decision — start W-992909ca now", "hold"),
        ("operator decision: start W-992909ca now", "hold"),
        ("Operator  Decision: start W-992909ca", "hold"),
        ("**none** — terminal", "hold"),
        ("_none_", "hold"),
        ("`none`", "hold"),
        ("(none)", "hold"),
        ("- none — terminal", "hold"),
        ("**BLOCKED**: missing infra", "hold"),
        ("the operator decisions log", "hold"),
        ("operator-decision: start W-992909ca", "hold"),
        ("W-992909ca continue", "names-item"),
        ("continue W-992909ca then W-0858e5c2", "names-item"),
        ("W-abcdef12 — continue", "names-item"),
        ("continue W-abcdef12.", "names-item"),
        ("(W-abcdef12)", "names-item"),
        ("W-abcdef12, W-12345678", "names-item"),
        ("read https://x/notes/W-abcdef12/details", "free-text"),
        ("open /repo/W-abcdef12/notes.md", "free-text"),
        ("edit W-abcdef12.json", "free-text"),
        ("see .W-abcdef12 backup", "free-text"),
        ("open https://x/y?item=W-abcdef12 now", "free-text"),
        ("see ?item=W-abcdef12", "free-text"),
        ("jump to #W-abcdef12", "free-text"),
        ("set key=W-abcdef12", "free-text"),
        ("under x/W-abcdef12", "free-text"),
        ("W-abcdef12.json", "free-text"),
        ("read W-abcdef12/notes.md", "free-text"),
        ("**W-abcdef12** next", "names-item"),
        ("`W-abcdef12`", "names-item"),
        ("W-abcdef12: write it", "names-item"),
        ("W-abcdef12; then docs", "names-item"),
        ("[W-abcdef12] continue", "names-item"),
        ('"W-abcdef12" next', "names-item"),
        ("'W-abcdef12' next", "names-item"),
        ("<W-abcdef12> next", "names-item"),
        ("{W-abcdef12} next", "names-item"),
        ("work on —W-abcdef12", "names-item"),
        ("W-ABCDEF12 continue", "free-text"),
        ("fix the flake", "free-text"),
        ("Nonexistent thing", "free-text"),
        ("nonetheless ship it", "free-text"),
        ("BLOCKEDx is a word", "free-text"),
        ("the build is blocked on CI", "free-text"),
        ("run the none-safe path", "free-text"),
        ("the operators decision log", "free-text"),
    ],
)
def test_classify_next_sorts_every_line_by_the_ticket_precedence(store, line, want):
    work, _repo, _env_ = store
    assert work.classify_next(line) == want


# ── the Behavior Contract ─────────────────────────────────────────────────────────────────────


def test_three_free_text_stops_leave_one_next_item_with_the_last_text_and_a_repeat_writes_nothing(
    store,
):
    work, repo, _env_ = store
    for text in ("fix the flake", "write the census", "ship the census"):
        work.on_harvest(repo, session="S1", next_text=text, next_anchored=True)
        time.sleep(0.002)  # distinct next_at per Stop
    mine = _open_next(repo, "S1")
    assert len(mine) == 1 and len(_next_items(repo)) == 1
    item = mine[0]
    assert item["next"] == "ship the census" and item["title"] == "ship the census"
    assert item["creator"] == "S1" and item["owner"] == "" and item["priority"] == 2
    assert item["next_at"] > item["created"]
    before, mtime = _file(repo, item["id"]).read_bytes(), _file(repo, item["id"]).stat().st_mtime_ns
    work.on_harvest(repo, session="S1", next_text="ship  the\ncensus", next_anchored=True)
    assert _file(repo, item["id"]).read_bytes() == before
    assert _file(repo, item["id"]).stat().st_mtime_ns == mtime
    # rule 4: free text the register did NOT accept changes nothing
    snap = _snapshot(repo)
    work.on_harvest(repo, session="S1", next_text="something else entirely")
    assert _snapshot(repo) == snap


def test_a_next_naming_an_open_item_claims_it_and_supersedes_the_next_item(store):
    work, repo, env = store
    x = _add(repo, env)
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (nxt,) = _open_next(repo, "S1")
    # next_anchored omitted, as today's callers do: rule 2 still claims
    work.on_harvest(repo, session="S1", next_text=f"{x} — continue")
    assert _item(repo, x)["next"] == f"{x} — continue"
    assert _live_session(repo, x) == "S1"
    closed = _item(repo, nxt["id"])
    assert closed["status"] == "dropped" and closed["note"] == "superseded"
    assert _open_next(repo, "S1") == []
    # a later accepted free text opens a NEW next item
    work.on_harvest(repo, session="S1", next_text="then the docs", next_anchored=True)
    (again,) = _open_next(repo, "S1")
    assert again["id"] != nxt["id"]


def test_only_the_first_qualifying_id_is_updated_and_claimed(store):
    work, repo, env = store
    awaiting = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m0", session="S0")
    assert awaiting and _item(repo, awaiting)["status"] == "awaiting-operator"
    y, z = _add(repo, env, "Y"), _add(repo, env, "Z")
    before_awaiting, before_z = _file(repo, awaiting).read_bytes(), _file(repo, z).read_bytes()
    work.on_harvest(repo, session="S1", next_text=f"answer {awaiting}, then {y} and {z}")
    assert _file(repo, awaiting).read_bytes() == before_awaiting
    assert _claim(repo, awaiting) is None
    assert _item(repo, y)["next"] == f"answer {awaiting}, then {y} and {z}"
    assert _live_session(repo, y) == "S1"
    assert _file(repo, z).read_bytes() == before_z and _claim(repo, z) is None


def test_a_next_naming_only_unavailable_items_claims_nothing_but_supersedes(store):
    work, repo, env = store
    held, done = _add(repo, env, "held"), _add(repo, env, "closed")
    awaiting = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m0", session="S0")
    _ok(["claim", held, "--session", "OTHER"], env, repo)
    _set(repo, done, status="dropped", note="gone")
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (nxt,) = _open_next(repo, "S1")
    held_claim = _claim(repo, held)
    snap = {k: v for k, v in _snapshot(repo).items() if k != f"{nxt['id']}.json"}
    work.on_harvest(repo, session="S1", next_text=f"{held} then {done} then {awaiting}")
    assert {k: v for k, v in _snapshot(repo).items() if k != f"{nxt['id']}.json"} == snap
    assert _claim(repo, held) == held_claim
    assert _claim(repo, done) is None and _claim(repo, awaiting) is None
    assert _item(repo, nxt["id"])["note"] == "superseded"
    # an operator-decision hold naming an OPEN item claims nothing either
    x = _add(repo, env, "X")
    work.on_harvest(repo, session="S1", next_text="also free", next_anchored=True)
    (nxt2,) = _open_next(repo, "S1")
    before = _file(repo, x).read_bytes()
    work.on_harvest(repo, session="S1", next_text=f"awaiting operator decision — start {x} now")
    assert _file(repo, x).read_bytes() == before and _claim(repo, x) is None
    assert _item(repo, nxt2["id"])["status"] == "dropped"


def test_an_operator_decision_next_never_rewrites_or_claims_the_item_it_names(store):
    work, repo, env = store
    x = _add(repo, env, "X")
    before = _file(repo, x).read_bytes()
    work.on_harvest(repo, session="S1", next_text=f"operator decision: start {x} now")
    assert _file(repo, x).read_bytes() == before
    assert _claim(repo, x) is None


def test_any_harvest_closes_next_items_idle_seven_days_falling_back_to_created(store):
    work, repo, env = store
    work.on_harvest(repo, session="S2", next_text="old thread", next_anchored=True)
    work.on_harvest(repo, session="S3", next_text="older thread", next_anchored=True)
    work.on_harvest(repo, session="S4", next_text="fresh thread", next_anchored=True)
    (a,), (b,), (fresh,) = _open_next(repo, "S2"), _open_next(repo, "S3"), _open_next(repo, "S4")
    _set(repo, a["id"], next_at=_iso_days_ago(8))
    _set(repo, b["id"], next_at="", created=_iso_days_ago(8))
    work.on_harvest(repo, session="S9")  # another session's quiet Stop
    for it in (a, b):
        got = _item(repo, it["id"])
        assert (got["status"], got["note"]) == ("dropped", "idle 7 days"), got
    assert _item(repo, fresh["id"])["status"] == "open"


def test_one_unjudgeable_next_item_never_stops_the_idle_close_for_the_rest(store, monkeypatch):
    work, repo, _env_ = store
    for s in ("S2", "S3"):
        work.on_harvest(repo, session=s, next_text=f"thread of {s}", next_anchored=True)
    (a,), (b,) = _open_next(repo, "S2"), _open_next(repo, "S3")
    for it in (a, b):
        _set(repo, it["id"], next_at=_iso_days_ago(9))
    real = work._close_next

    def flaky(repo_, item, session, note):
        if item["id"] == min(a["id"], b["id"]):
            raise OSError("disk says no")
        return real(repo_, item, session, note)

    monkeypatch.setattr(work, "_close_next", flaky)
    work.on_harvest(repo, session="S9")
    first, second = sorted((a["id"], b["id"]))
    assert _item(repo, first)["status"] == "open"
    assert _item(repo, second)["status"] == "dropped"


def test_nosession_and_an_empty_session_never_claim_and_never_create(store):
    work, repo, env = store
    x = _add(repo, env, "X")
    for session in ("nosession", ""):
        snap = _snapshot(repo)
        work.on_harvest(repo, session=session, next_text=f"{x} — continue")
        work.on_harvest(repo, session=session, next_text="fix the flake", next_anchored=True)
        assert _snapshot(repo) == snap
        assert _claim(repo, x) is None
    assert _next_items(repo) == []


# ── what each rule must leave UNCHANGED ───────────────────────────────────────────────────────


def test_a_harvest_without_a_next_changes_no_item(store):
    work, repo, env = store
    x = _add(repo, env, "X")
    _ok(["claim", x, "--session", "S1"], env, repo)
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    snap, at = _snapshot(repo), _claim(repo, x)["at"]  # type: ignore[index]
    time.sleep(0.01)
    work.on_harvest(repo, session="S1")
    work.on_harvest(repo, session="S1", next_text="", next_anchored=True)
    assert _snapshot(repo) == snap
    assert _claim(repo, x)["at"] > at  # type: ignore[index]  # only the renewal happened


def test_the_decision_item_survives_when_the_rules_and_the_idle_close_raise(store, monkeypatch):
    work, repo, env = store
    x = _add(repo, env, "X")

    def boom(*_a, **_k):
        raise RuntimeError("rule failure")

    monkeypatch.setattr(work, "_apply_next_rules", boom)
    monkeypatch.setattr(work, "_close_idle_next", boom)
    got = work.on_harvest(
        repo, session="S1", block=BLOCK, msg_digest="m1", next_text=f"{x} go", next_anchored=True
    )
    assert got and _item(repo, got)["kind"] == "decision"
    assert _item(repo, got)["status"] == "awaiting-operator"


# ── review round 1 ───────────────────────────────────────────────────────────────────────────


def _bind(env: dict[str, str], session: str, name: str) -> None:
    path = Path(env["AGENT_IDENTITY_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"session_id": session, "name": name}) + "\n", encoding="utf-8")


def test_an_id_inside_a_path_or_url_names_no_item_and_supersedes_nothing(store):
    work, repo, env = store
    x = _add(repo, env, "X")
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (nxt,) = _open_next(repo, "S1")
    before = _file(repo, x).read_bytes()
    for line in (f"read https://x/notes/{x}/details", f"open /repo/{x}/notes.md", f"{x}.json"):
        work.on_harvest(repo, session="S1", next_text=line)  # not anchored: rule 4
    assert _file(repo, x).read_bytes() == before and _claim(repo, x) is None
    assert _item(repo, nxt["id"])["status"] == "open"
    # a bare id makes the line rule 2; the path-shaped one is still never a target
    work.on_harvest(repo, session="S1", next_text=f"open /repo/{x}/notes.md for W-00000000")
    assert _file(repo, x).read_bytes() == before and _claim(repo, x) is None
    # unchanged: a sentence-final id still names (and claims) it
    work.on_harvest(repo, session="S1", next_text=f"continue {x}.")
    assert _live_session(repo, x) == "S1"


def test_rule_two_records_the_sessions_bound_agent_and_the_cli_record_is_unchanged(store):
    work, repo, env = store
    _bind(env, "S1", "fleet")
    x = _add(repo, env, "X")
    work.on_harvest(repo, session="S1", next_text=f"{x} continue")
    claim = _claim(repo, x)
    assert claim is not None and claim["agent"] == "fleet"
    # unchanged: the CLI's record resolves the agent with no session, as before
    rec = work._claim_record(None, "S1", 1.0)
    assert rec is not None and rec[0]["agent"] == work._agent_name() == ""


def test_rule_three_creates_the_item_with_its_owner_and_next_at(store):
    work, repo, env = store
    _bind(env, "S1", "intel")
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (item,) = _open_next(repo, "S1")
    assert item["owner"] == "intel" and item["next_at"] == item["created"]


def test_rule_two_never_claims_a_next_item_by_id(store):
    work, repo, _env_ = store
    work.on_harvest(repo, session="S2", next_text="their thread", next_anchored=True)
    work.on_harvest(repo, session="S1", next_text="my thread", next_anchored=True)
    (theirs,), (mine,) = _open_next(repo, "S2"), _open_next(repo, "S1")
    before = _file(repo, theirs["id"]).read_bytes()
    work.on_harvest(repo, session="S1", next_text=f"{theirs['id']} then {mine['id']}")
    assert _file(repo, theirs["id"]).read_bytes() == before
    assert _claim(repo, theirs["id"]) is None and _claim(repo, mine["id"]) is None
    assert _item(repo, mine["id"])["note"] == "superseded"  # its own: closed, never claimed


def test_a_failed_claim_write_leaves_the_items_next_alone_and_still_supersedes(
    store, monkeypatch, capsys
):
    work, repo, env = store
    x = _add(repo, env, "X")
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (nxt,) = _open_next(repo, "S1")
    before = _file(repo, x).read_bytes()
    capsys.readouterr()

    def refuse(*_a, **_k):
        raise OSError("claims dir is read-only")

    monkeypatch.setattr(work, "_write_claim", refuse)
    work.on_harvest(repo, session="S1", next_text=f"{x} continue")
    err = capsys.readouterr().err
    assert "named item not claimed — OSError" in err and "its next not written" not in err
    assert _file(repo, x).read_bytes() == before
    assert _item(repo, nxt["id"])["note"] == "superseded"


def test_a_failed_next_write_after_the_claim_says_the_claim_stands(store, monkeypatch, capsys):
    work, repo, env = store
    x = _add(repo, env, "X")
    work.on_harvest(repo, session="S1", next_text="fix the flake", next_anchored=True)
    (nxt,) = _open_next(repo, "S1")
    before = _file(repo, x).read_bytes()
    real = work._write_item

    def refuse_x(repo_, item, **k):
        if item.get("id") == x:
            raise OSError("item file is read-only")
        return real(repo_, item, **k)

    monkeypatch.setattr(work, "_write_item", refuse_x)
    capsys.readouterr()
    work.on_harvest(repo, session="S1", next_text=f"{x} continue")
    err = capsys.readouterr().err
    assert f"named item {x} claimed, its next not written — OSError" in err
    assert "not claimed" not in err
    assert _live_session(repo, x) == "S1"
    assert _file(repo, x).read_bytes() == before
    assert _item(repo, nxt["id"])["note"] == "superseded"


def test_a_successful_rule_two_harvest_prints_nothing(store, capsys):
    work, repo, env = store
    x = _add(repo, env, "X")
    capsys.readouterr()
    work.on_harvest(repo, session="S1", next_text=f"{x} continue")
    assert capsys.readouterr().err == ""
    assert _live_session(repo, x) == "S1"


def test_a_next_item_closed_in_another_tree_is_never_closed_again(store):
    work, repo, _env_ = store
    work.on_harvest(repo, session="S2", next_text="old thread", next_anchored=True)
    work.on_harvest(repo, session="S3", next_text="plain thread", next_anchored=True)
    (a,), (b,) = _open_next(repo, "S2"), _open_next(repo, "S3")
    for it in (a, b):
        _set(repo, it["id"], next_at=_iso_days_ago(8))
    marker = repo / ".git" / "fabrik-work" / "closed" / f"{a['id']}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    fields = {
        "agent": "",
        "at": time.time(),
        "decision": "",
        "evidence": "",
        "id": a["id"],
        "note": "elsewhere",
        "session": "OTHER",
        "status": "dropped",
        "tree": "/elsewhere/wt",
    }
    marker.write_text(json.dumps(fields), encoding="utf-8")
    held, item_before = marker.read_bytes(), _file(repo, a["id"]).read_bytes()
    work.on_harvest(repo, session="S2", next_text="none — terminal")
    assert marker.read_bytes() == held
    assert _file(repo, a["id"]).read_bytes() == item_before
    # unchanged: the markerless idle item still closes at 7 days
    got = _item(repo, b["id"])
    assert (got["status"], got["note"]) == ("dropped", "idle 7 days")


def test_the_seven_day_boundary_is_strictly_greater(store, monkeypatch):
    work, repo, _env_ = store
    for s in ("S2", "S3"):
        work.on_harvest(repo, session=s, next_text=f"thread {s}", next_anchored=True)
    (exact,), (over,) = _open_next(repo, "S2"), _open_next(repo, "S3")
    now = float(int(time.time()))  # whole seconds: the ISO round trip is exact

    def iso(t: float) -> str:
        return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    _set(repo, exact["id"], next_at=iso(now - 7 * 86400))
    _set(repo, over["id"], next_at=iso(now - 7 * 86400 - 1))
    monkeypatch.setattr(time, "time", lambda: now)
    work.on_harvest(repo, session="S9")
    assert _item(repo, exact["id"])["status"] == "open"
    assert _item(repo, over["id"])["status"] == "dropped"
