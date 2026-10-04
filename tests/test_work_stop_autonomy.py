"""The autonomy Stop ladder (operator ruling 2026-10-04).

"handle them all waiting tasks, feedbacks, kaizen items by one autonomously … only stop if you
cant find answers in our repo" and "also mails should be handled". With `"autonomy": true` in the
main checkout's work-store config, `work.py queue --stop` hands the Stop hook an ORDERED list of
candidates, one per subject: held claims → mail → queued → coordinator rungs → owned items → the
distributor's feedback queues. Without the key, the classic D-521 result is unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
SID = "sid-auto"


def _env(tmp_path: Path, agent: str = "coord") -> dict[str, str]:
    for sub in ("home", "tmp", "tmp/state/command-runs"):
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
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "tmp" / "identity.jsonl"),
        "FABRIK_WORK_PROC": str(tmp_path / "noproc"),
        "CLAUDE_AGENT": agent,
    }


def _git(cwd: Path, env: dict, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, check=True)


def run(args: list[str], env: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _setup(tmp_path: Path, *, autonomy: bool = True) -> tuple[dict, Path]:
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "master", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    r = run(["init", "--distributor", "coord"], env, repo)
    assert r.returncode == 0, r.stderr
    if autonomy:
        cfg = repo / ".fabrik" / "work" / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["autonomy"] = True
        cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return env, repo.resolve()


def _add(repo: Path, env: dict, kind: str, title: str, *extra: str) -> str:
    r = run(["add", "--kind", kind, "--title", title, *extra], env, repo)
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1]).stem


def _assign(repo: Path, env: dict, item: str, owner: str, *extra: str) -> None:
    r = run(["assign", item, "--owner", owner, *extra], env, repo)
    assert r.returncode == 0, r.stderr


def _stop(repo: Path, env: dict, session: str = SID) -> dict:
    r = run(["queue", "--stop", "--session", session, "--cwd", str(repo)], env, repo)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1, r.stdout
    return json.loads(lines[0])


def _mail(env: dict, repo: Path, mid: str, *, agent: str, kind: str = "request") -> None:
    inbox = Path(env["FABRIK_MAIL_ROOT"]) / repo.name / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    head = f"---\nid: {mid}\nfrom: other\nto: {repo.name}\nts: 2026-10-04T10:00:0{mid[-1]}+00:00\n"
    head += f"kind: {kind}\nack: required\nhops: 0\n"
    if agent:
        head += f"agent: {agent}\n"
    (inbox / f"{mid}.md").write_text(head + "---\nbody\n", encoding="utf-8")


def test_a_held_claim_is_continued_not_silenced(tmp_path):
    env, repo = _setup(tmp_path)
    low = _add(repo, env, "task", "later", "--priority", "3")
    high = _add(repo, env, "task", "first", "--priority", "1")
    for item in (low, high):
        _assign(repo, env, item, "coord")
        r = run(["claim", item, "--session", SID], env, repo)
        assert r.returncode == 0, r.stderr
    out = _stop(repo, env)
    assert out["action"] == "continue", out
    assert out["fp"] == f"item:{high}" and high in out["text"], out
    assert [c["fp"] for c in out["candidates"][:2]] == [f"item:{high}", f"item:{low}"]
    assert "work.py done" in out["text"]


def test_many_held_claims_are_counted_in_the_text(tmp_path):
    env, repo = _setup(tmp_path)
    items = [_add(repo, env, "task", f"t{n}") for n in range(6)]
    for item in items:
        _assign(repo, env, item, "coord")
        assert run(["claim", item, "--session", SID], env, repo).returncode == 0
    out = _stop(repo, env)
    assert out["text"].startswith("You hold 6 claims; next (or another held item): "), out
    assert len([c for c in out["candidates"] if c["action"] == "continue"]) == 6
    (tmp_path / "few").mkdir()
    env2, repo2 = _setup(tmp_path / "few")
    one = _add(repo2, env2, "task", "solo")
    _assign(repo2, env2, one, "coord")
    assert run(["claim", one, "--session", SID], env2, repo2).returncode == 0
    assert not _stop(repo2, env2)["text"].startswith("You hold"), "one claim needs no count"


def test_a_held_mail_item_closes_through_mail_ack(tmp_path):
    env, repo = _setup(tmp_path)
    item = _add(repo, env, "task", "from mail")
    path = repo / ".fabrik" / "work" / f"{item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(kind="mail", owner="coord", links={**data.get("links", {}), "mail": "01MAILID"})
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert run(["claim", item, "--session", SID], env, repo).returncode == 0
    out = _stop(repo, env)
    assert out["action"] == "continue" and "mail.py ack 01MAILID" in out["text"], out
    assert "work.py done" not in out["text"]


def test_mail_awaiting_an_answer_is_the_next_step(tmp_path):
    env, repo = _setup(tmp_path)
    _mail(env, repo, "01MAIL1", agent="coord")
    _mail(env, repo, "01MAIL2", agent="fleet")  # another beat's
    _mail(env, repo, "01MAIL3", agent="")  # unaddressed: the distributor's
    _mail(env, repo, "01MAIL4", agent="coord", kind="merge-request")  # the seventh cause's
    out = _stop(repo, env)
    fps = [c["fp"] for c in out["candidates"]]
    assert out["action"] == "mail" and fps[:2] == ["mail:01MAIL1", "mail:01MAIL3"], out
    assert "mail:01MAIL2" not in fps and "mail:01MAIL4" not in fps
    other = _stop(repo, {**env, "CLAUDE_AGENT": "fleet"}, session="sid-fleet")
    assert [c["fp"] for c in other["candidates"]] == ["mail:01MAIL2"], other


def test_an_owned_backlog_item_is_claimed(tmp_path):
    env, repo = _setup(tmp_path)
    item = _add(repo, env, "backlog", "someday mine")
    _assign(repo, env, item, "coord")
    held = _add(repo, env, "backlog", "parked", "--tag", "hold")
    _assign(repo, env, held, "coord")
    out = _stop(repo, env)
    fps = [c["fp"] for c in out["candidates"]]
    assert out["action"] == "owned" and out["fp"] == f"item:{item}", out
    assert f"item:{held}" not in fps, "a held item is never pushed"
    assert f"work.py claim {item}" in out["text"]


def test_the_corpus_owner_is_sent_to_its_feedback_queue(tmp_path):
    env, repo = _setup(tmp_path)
    (repo / "commands" / "_sources").mkdir(parents=True)
    ledger = Path(env["COMMAND_RUN_DIR"]).parent / "command-feedback.jsonl"
    rows = [{"command": "fabrik-x", "ts": float(n), "change": "accurate: fix it"} for n in (1, 2)]
    rows.append({"command": "fabrik-y", "ts": 3.0, "change": "lean: trim"})
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = _stop(repo, env)
    fps = [c["fp"] for c in out["candidates"]]
    assert fps == ["feedback:fabrik-x", "feedback:fabrik-y"], out  # deepest first
    assert "/fabrik-command-improve fabrik-x" in out["text"]
    intel = _stop(repo, {**env, "CLAUDE_AGENT": "intel"}, session="sid-intel")
    assert intel["action"] is None and intel["candidates"] == [], intel


def test_the_fingerprint_names_the_subject_not_a_count(tmp_path):
    env, repo = _setup(tmp_path)
    a = _add(repo, env, "task", "a")
    _assign(repo, env, a, "coord")
    first = _stop(repo, env)
    assert first["fp"] == f"item:{a}", first
    assert run(["claim", a, "--session", SID], env, repo).returncode == 0
    held = _stop(repo, env)
    assert held["action"] == "continue" and held["fp"] == f"item:{a}", (
        "claim and continue of one item are one subject"
    )


def test_without_the_flag_nothing_changes(tmp_path):
    env, repo = _setup(tmp_path, autonomy=False)
    item = _add(repo, env, "task", "mine")
    _assign(repo, env, item, "coord")
    _mail(env, repo, "01MAIL1", agent="coord")
    out = _stop(repo, env)
    assert out["action"] == "claim" and out["fp"] == "claim:few" and "candidates" not in out, out
    assert run(["claim", item, "--session", SID], env, repo).returncode == 0
    assert _stop(repo, env)["action"] is None, "the classic path stays silent under a held claim"


def test_a_feedback_subject_keeps_its_fingerprint_as_the_depth_moves(tmp_path):
    """Round 1 (A-sonnet, executed): the depth in the fingerprint re-armed the subject on every
    answered or filed row, so the ladder never reached its warn-through."""
    env, repo = _setup(tmp_path)
    (repo / "commands" / "_sources").mkdir(parents=True)
    ledger = Path(env["COMMAND_RUN_DIR"]).parent / "command-feedback.jsonl"
    row = {"command": "fabrik-x", "ts": 1.0, "change": "accurate: fix it"}
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    first = _stop(repo, env)["fp"]
    ledger.write_text(json.dumps(row) + "\n" + json.dumps({**row, "ts": 2.0}) + "\n", "utf-8")
    assert _stop(repo, env)["fp"] == first == "feedback:fabrik-x"


def test_triage_keys_on_the_workers_below_the_floor(tmp_path):
    """Round 2 (A-sonnet, C-sonnet): `rung:triage` silenced a NEW worker falling below the floor
    for the rest of the session. The subject is the set of workers, never the counts."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("work_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    calls = iter(
        [
            {"action": "triage", "fp": "triage:w1:few:many", "text": "t"},
            {"action": "triage", "fp": "triage:w1:many:few", "text": "t"},
            {"action": "triage", "fp": "triage:w1,w9:few:few", "text": "t"},
        ]
    )
    env, repo = _setup(tmp_path)
    fps = []
    for _ in range(3):
        classic = next(calls)
        mod._classic_rungs = lambda *a, c=classic, **k: c
        out = mod._autonomy_candidates(
            repo, repo, "s", "coord", False, {}, "coord", {"action": None}
        )
        fps.append(next(c["fp"] for c in out if c["action"] == "triage"))
    assert fps == ["rung:triage:w1", "rung:triage:w1", "rung:triage:w1,w9"], fps


def _claimed(repo: Path, env: dict, title: str, *tags: str, kind: str = "task") -> str:
    item = _add(repo, env, kind, title)
    extra = [a for t in tags for a in ("--tag", t)]
    _assign(repo, env, item, "coord", *extra)
    assert run(["claim", item, "--session", SID], env, repo).returncode == 0
    return item


def _subjects(out: dict) -> list[str]:
    return [c["fp"] for c in out.get("candidates") or []]


def _day(y: int, m: int, d: int):
    import datetime

    return datetime.date(y, m, d)


def _load_work():
    import importlib.util

    spec = importlib.util.spec_from_file_location("work_waits", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_a_held_claim_is_not_pushed(tmp_path):
    """Intel, 2026-10-04: a claimed item that is not due yet kept the Stop hook pushing it. A
    parked claim is told to release, never to finish; live work comes first."""
    env, repo = _setup(tmp_path)
    parked = _claimed(repo, env, "parked", "hold")
    live = _claimed(repo, env, "live")
    out = _stop(repo, env)
    subjects = _subjects(out)
    assert out["fp"] == f"item:{live}", out
    assert f"item:{parked}" not in subjects and f"release:{parked}" in subjects, subjects
    rel = next(c for c in out["candidates"] if c["fp"] == f"release:{parked}")
    assert f"work.py release {parked}" in rel["text"] and "(hold)" in rel["text"], rel


def test_a_dated_wait_lapses_on_its_date(tmp_path):
    env, repo = _setup(tmp_path)
    future = _claimed(repo, env, "not yet", "waits-2999-01-01")
    past = _claimed(repo, env, "due now", "waits-2000-01-01")
    subjects = _subjects(_stop(repo, env))
    assert f"item:{future}" not in subjects and f"release:{future}" in subjects, subjects
    assert f"item:{past}" in subjects, subjects
    wp = _load_work()
    item = {"tags": ["waits-2026-10-09"]}
    assert wp._is_parked(item, today=_day(2026, 10, 8))
    assert not wp._is_parked(item, today=_day(2026, 10, 9)), "live again ON the date"


def test_a_slug_wait_holds_until_removed(tmp_path):
    env, repo = _setup(tmp_path)
    tojlo = _claimed(repo, env, "when Tojlo lands", "waits-tojlo")
    assert f"item:{tojlo}" not in _subjects(_stop(repo, env))
    assert _load_work()._is_parked({"tags": ["waits-tojlo"]}, today=_day(2999, 1, 1))


def test_an_invalid_date_wait_is_refused(tmp_path):
    """A typo in a dated wait would park the item forever as a slug: refused when written."""
    env, repo = _setup(tmp_path)
    item = _add(repo, env, "task", "t")
    for bad in ("waits-2026-13-40", "waits-2026-10-9", "waits-20261009", "waits-"):
        r = run(["assign", item, "--tag", bad], env, repo)
        assert r.returncode != 0 and "waits-" in r.stderr, (bad, r.stderr)
        r = run(["add", "--kind", "task", "--title", "x", "--tag", bad], env, repo)
        assert r.returncode != 0 and "waits-" in r.stderr, ("add", bad, r.stderr)
    assert run(["assign", item, "--tag", "waits-2026-10-09"], env, repo).returncode == 0
    wp = _load_work()
    d = _day(2999, 1, 1)
    assert wp._is_held({"tags": ["runtime"]}, today=d) and not wp._is_parked(
        {"tags": ["runtime"]}, today=d
    )
    assert wp._is_parked({"tags": ["hold"]}, today=d) and not wp._is_held(
        {"tags": ["rules"]}, today=d
    )


def test_a_held_task_is_not_queued(tmp_path):
    env, repo = _setup(tmp_path)
    item = _add(repo, env, "task", "parked work")
    _assign(repo, env, item, "coord", "--tag", "waits-2999-01-01")
    out = _stop(repo, env)
    assert out.get("action") != "claim" and f"item:{item}" not in _subjects(out), out
    r = run(["next"], env, repo)
    assert item not in r.stdout, r.stdout


def test_held_claims_are_counted_in_the_text(tmp_path):
    env, repo = _setup(tmp_path)
    _claimed(repo, env, "parked one", "hold")
    owned = _add(repo, env, "task", "parked two")
    _assign(repo, env, owned, "coord", "--tag", "waits-tojlo")
    _claimed(repo, env, "live")
    assert _stop(repo, env)["parked"] == 2
    theirs = _add(repo, env, "task", "someone else's, parked")
    _assign(repo, env, theirs, "other", "--tag", "hold")
    assert run(["claim", theirs, "--session", SID], env, repo).returncode == 0
    assert _stop(repo, env)["parked"] == 3, "a parked item this session CLAIMED counts too"
    r = run(["queue"], env, repo)
    assert "parked 2" in r.stdout, r.stdout


def test_an_owned_runtime_task_is_pushed(tmp_path):
    """`runtime` keeps an item out of AUTOMATIC assignment only; assigned by hand it is due work."""
    env, repo = _setup(tmp_path)
    item = _add(repo, env, "backlog", "serialising act")
    _assign(repo, env, item, "coord", "--tag", "runtime")
    assert f"item:{item}" in _subjects(_stop(repo, env))
