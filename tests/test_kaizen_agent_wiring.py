"""Graders for the fourth hub agent, `kaizen` (operator ruling 2026-10-06): the feedback loop's
owner. One test per behaviour of the wiring — mail addressee, the Stop ladder's feedback rung,
`--reject`, the relay's recipient, the one-wake feedback watcher, its per-prompt check, and the
charter injection. Count them with `pytest --collect-only`; a number here rots.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "scripts" / "work.py"
REPORT = ROOT / "scripts" / "command_feedback_report.py"
RELAY = ROOT / "scripts" / "sysadmin" / "feedback_relay.py"
ARM = ROOT / "scripts" / "sysadmin" / "feedback_watch_arm.sh"
CHECK = ROOT / "scripts" / "sysadmin" / "selfwatch_check.py"
ROLE_HOOK = ROOT / ".claude" / "hooks" / "agent_role.py"
SID = "11111111-2222-3333-4444-555555555555"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# --- 1. mail: kaizen is a hub beat -----------------------------------------------------------
def test_mail_accepts_kaizen_as_a_hub_beat(tmp_path, monkeypatch):
    mail = _load(ROOT / "scripts" / "mail.py", "kz_mail")
    (tmp_path / "mail").mkdir()
    (tmp_path / "opt").mkdir()
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(tmp_path / "mail"))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(tmp_path / "opt"))
    monkeypatch.setattr(mail, "_is_hub_repo", lambda: False)
    monkeypatch.setattr(mail, "_mail_store", lambda *a, **k: None)
    assert "kaizen" in mail.HUB_BEATS
    path = mail.send(to="fabrik", kind="finding", body="a verdict", frm="fabrik", to_agent="kaizen")
    mid = path.name.removesuffix(".md")
    assert mid in {m["id"] for m in mail.list_msgs("fabrik", agent="kaizen")}
    with pytest.raises(mail.MailRefusedError) as exc:
        mail.send(to="fabrik", kind="finding", body="x", frm="fabrik")
    assert "kaizen" in str(exc.value), "the unaddressed-send guide must list the fourth beat"


# --- 2. the Stop ladder: the feedback rung follows config feedback_owner ----------------------
def _wenv(tmp_path: Path, agent: str) -> dict[str, str]:
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


def _wrun(args: list[str], env: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORK), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _stop(repo: Path, env: dict, session: str) -> dict:
    c = _wrun(["commit-items"], env, repo)
    assert c.returncode == 0, c.stderr
    r = _wrun(["queue", "--stop", "--session", session, "--cwd", str(repo)], env, repo)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_feedback_rung_follows_feedback_owner(tmp_path):
    env = _wenv(tmp_path, "coord")
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(repo)], env=env, check=True)
    (repo / "README").write_text("seed\n")
    subprocess.run(["git", "add", "README"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, env=env, check=True)
    assert _wrun(["init", "--distributor", "coord"], env, repo).returncode == 0
    # tracked, as the hub's is: a linked worktree must see it, or its feedback rung has no corpus
    (repo / "commands" / "_sources").mkdir(parents=True)
    (repo / "commands" / "_sources" / ".keep").write_text("")
    subprocess.run(["git", "add", "commands"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "corpus"], cwd=repo, env=env, check=True)
    ledger = Path(env["COMMAND_RUN_DIR"]).parent / "command-feedback.jsonl"
    ledger.write_text(json.dumps({"command": "fabrik-x", "ts": 1.0, "change": "lean: a"}) + "\n")
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text())
    data.update({"autonomy": True, "feedback_owner": "kaizen"})
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    repo = repo.resolve()
    # kaizen works in a linked worktree like intel/fleet, and routable backlog waits in the pool
    wt = repo / ".claude" / "worktrees" / "kaizen"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "kaizen", str(wt)], cwd=repo, env=env, check=True
    )
    r = _wrun(["add", "--kind", "task", "--title", "someone's backlog"], env, repo)
    assert r.returncode == 0, r.stderr
    kz = _stop(repo, {**env, "CLAUDE_AGENT": "kaizen"}, "sid-kz")
    fps = [c["fp"] for c in kz["candidates"]]
    assert fps and fps[0] == "feedback:fabrik-x", kz  # first: no doorbell, no claim rung before it
    assert kz["action"] == "feedback", kz
    # the owner's own worktree names it even with CLAUDE_AGENT unset (pass 1, A-S3): the pool's
    # name fallback no longer covers a tree `_workers` dropped, so the ladder gets its own
    unset = {k: v for k, v in env.items() if k != "CLAUDE_AGENT"}
    wt_stop = _wrun(["commit-items"], unset, repo)
    assert wt_stop.returncode == 0, wt_stop.stderr
    r = _wrun(["queue", "--stop", "--session", "sid-kz2", "--cwd", str(wt)], unset, wt)
    assert r.returncode == 0, r.stderr
    kz2 = json.loads(r.stdout.strip().splitlines()[-1])
    assert kz2["agent"] == "kaizen" and kz2["candidates"][0]["fp"] == "feedback:fabrik-x", kz2
    coord = _stop(repo, env, "sid-coord")
    assert "feedback:fabrik-x" not in [c["fp"] for c in coord.get("candidates", [])], coord
    # MIRROR: no key → the distributor keeps the rung exactly as before
    del data["feedback_owner"]
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    coord2 = _stop(repo, env, "sid-coord2")
    assert "feedback:fabrik-x" in [c["fp"] for c in coord2["candidates"]], coord2


# --- 3. --reject clears a verdict without a commit -------------------------------------------
def _row(cmd: str, ts: float, change: str) -> dict:
    return {
        "ts": ts,
        "sid": "s",
        "repo": "/opt/x",
        "command": cmd,
        "state": "done",
        "wall_s": 10,
        "rounds": 2,
        "findings": [1, 0],
        "phases": 3,
        "confusion": "none",
        "waste": "none",
        "change": change,
        "filed": "none — surfaces exercised: x",
    }


def test_reject_clears_a_verdict_without_a_commit(tmp_path):
    m = _load(REPORT, "kz_cfr")
    ledger = tmp_path / "ledger.jsonl"
    rows = [_row("fabrik-review", 1.0, "lean: cut step 7"), _row("fabrik-review", 2.0, "lean: b")]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    index = tmp_path / "command-feedback-answered.jsonl"  # beside the ledger: where `queue` reads
    reason = "the step it names was removed in D-330; nothing to cut"
    written, msg = m.reject(
        "fabrik-review", ["1.0"], reason, tmp_path, index, ledger=ledger, by="kaizen"
    )
    assert written == 1, msg
    assert "1.0" not in m.queue(rows, "fabrik-review", ledger=ledger)
    assert m.queue_depths(ledger, answered_path=index) == {"fabrik-review": 1}
    rec = json.loads(index.read_text().strip().splitlines()[-1])
    assert rec["commit"] == "rejected" and rec["reason"] == reason and rec["by"] == "kaizen"
    head = m.queue(rows, "fabrik-review", ledger=ledger).splitlines()[0]
    assert "1 rejected" in head, head  # COBRA: a reject-heavy queue is visible
    short, msg = m.reject("fabrik-review", ["2.0"], "nah", tmp_path, index, ledger=ledger)
    assert short == 0 and "REFUSED" in msg
    bad, msg = m.reject("fabrik-review", ["9.9"], reason, tmp_path, index, ledger=ledger)
    assert bad == 0 and "REFUSED" in msg
    cli = subprocess.run(
        [
            sys.executable,
            str(REPORT),
            "--ledger",
            str(ledger),
            "--reject",
            "fabrik-review",
            "--rows",
            "2.0",
            "--reason",
            reason,
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert cli.returncode == 0, cli.stderr + cli.stdout
    assert m.queue_depths(ledger, answered_path=index) == {}
    depths = subprocess.run(
        [sys.executable, str(REPORT), "--ledger", str(ledger), "--depths"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert depths.returncode == 0 and json.loads(depths.stdout) == {}, depths.stdout + depths.stderr
    # --depths and --reject run ALONE (pass 1, B-S1/B-S2): a write flag beside --depths is refused,
    # never silently skipped; a report flag beside --reject is refused
    mixed = subprocess.run(
        [
            sys.executable,
            str(REPORT),
            "--ledger",
            str(ledger),
            "--depths",
            "--reject",
            "fabrik-review",
            "--rows",
            "1.0",
            "--reason",
            reason,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert mixed.returncode == 2 and "REFUSED" in mixed.stdout, mixed.stdout
    rj = subprocess.run(
        [
            sys.executable,
            str(REPORT),
            "--ledger",
            str(ledger),
            "--reject",
            "fabrik-review",
            "--rows",
            "1.0",
            "--reason",
            reason,
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert rj.returncode == 2 and "REFUSED" in rj.stdout, rj.stdout
    # a handle two rows share is disclosed, as mark_answered discloses it (B-S3)
    dup = tmp_path / "dup.jsonl"
    dup.write_text(
        "\n".join(json.dumps(_row("fabrik-x", 7.0, f"lean: {i}")) for i in (1, 2)) + "\n"
    )
    n, m2 = m.reject(
        "fabrik-x", ["7.0"], reason, tmp_path, tmp_path / "dup-answered.jsonl", ledger=dup
    )
    assert n == 1 and "more than one ledger row" in m2, m2


# --- 4. the relay addresses kaizen -----------------------------------------------------------
def test_relay_addresses_kaizen(tmp_path, monkeypatch):
    relay = _load(RELAY, "kz_relay")
    stub = tmp_path / "mail.py"
    argv_log = tmp_path / "argv.json"
    stub.write_text(
        f"import json,sys\nopen({str(argv_log)!r},'w').write(json.dumps(sys.argv[1:]))\n"
    )
    monkeypatch.setattr(relay, "MAIL", stub)
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r.json").write_text(
        json.dumps(
            {
                "state": "done",
                "updated_ts": time.time(),
                "updated_at": "2026-10-06T00:00:00",
                "repo_root": "/opt/x",
                "command": "fabrik-review",
                "feedback": "filed",
                "feedback_text": "confusion: none · waste: none · change: lean: x · filed: y",
            }
        )
    )
    assert relay.main(["--runs", str(runs), "--watermark", str(tmp_path / "wm")]) == 0
    argv = json.loads(argv_log.read_text())
    assert argv[argv.index("--to-agent") + 1] == "kaizen", argv


# --- 5. the one-wake feedback watcher ------------------------------------------------------------
def _held(lock: Path) -> bool:
    with lock.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def _wenv5(tmp: Path, ledger: Path, series: Path, inbox: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp),
        "CLAUDE_SOUND_LOCKDIR": str(tmp / "locks"),
        "FEEDBACK_LEDGER": str(ledger),
        "KAIZEN_SERIES_DIR": str(series),
        "FABRIK_HUB_INBOX": str(inbox),
        "FEEDBACK_WATCH_POLL": "1",
        "FEEDBACK_WATCH_MIN_S": "0",
        "FEEDBACK_REPORT": str(REPORT),
    }


def _arm(tmp: Path, ledger: Path, series: Path, inbox: Path) -> subprocess.Popen:
    return subprocess.Popen(
        ["bash", str(ARM), "S1"],
        env=_wenv5(tmp, ledger, series, inbox),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _wait_lock(lock: Path, held: bool, seconds: float = 5.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if lock.exists() and _held(lock) == held:
            return
        time.sleep(0.05)
    raise AssertionError(f"lock {lock} never became held={held}")


def _wait_ready(lock: Path, seconds: float = 10.0) -> None:
    """The watcher's arm-time snapshot is done: whatever lands from here on is news. Without this
    wait a mail written between the lock and the snapshot is judged 'already present' (round 1)."""
    ready = lock.with_name(lock.name.replace(".lock", ".ready"))
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if ready.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"{ready} never appeared")


def test_feedback_watch_wakes_once_when_a_queue_rises(tmp_path):
    ledger = tmp_path / "command-feedback.jsonl"
    ledger.write_text(json.dumps(_row("fabrik-x", 1.0, "lean: a")) + "\n")
    series = tmp_path / "series"
    series.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (tmp_path / "locks").mkdir()
    lock = tmp_path / "locks" / "S1.feedbackwatch.lock"
    p = _arm(tmp_path, ledger, series, inbox)
    _wait_lock(lock, True)
    _wait_ready(lock)
    dup = subprocess.run(
        ["bash", str(ARM), "S1"],
        env=_wenv5(tmp_path, ledger, series, inbox),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert dup.returncode == 0 and "already armed" in dup.stdout, dup.stdout + dup.stderr
    # noise that must NOT wake it: a `change: none` row, another beat's mail, a removal
    with ledger.open("a") as fh:
        fh.write(json.dumps(_row("fabrik-x", 1.5, "none")) + "\n")
    (inbox / "01INFRA.md").write_text(
        "---\nid: 01INFRA\nkind: finding\nack: required\nagent: infra\n---\nx\n"
    )
    (inbox / "01INFRA.md").unlink()
    time.sleep(1.0)
    assert p.poll() is None, p.stdout.read() if p.stdout else ""
    # the signal: a real verdict raises a queue
    with ledger.open("a") as fh:
        fh.write(json.dumps(_row("fabrik-y", 2.0, "accurate: say which seat")) + "\n")
    out, err = p.communicate(timeout=15)
    assert p.returncode == 0, err
    assert "/fabrik-command-improve fabrik-y" in out and "re-arm" in out, out
    assert not _held(lock), "one wake per arm: the lock must be free after the wake"


def test_feedback_watch_wakes_on_kaizen_mail(tmp_path):
    ledger = tmp_path / "command-feedback.jsonl"
    ledger.write_text("")
    series = tmp_path / "series"
    series.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (tmp_path / "locks").mkdir()
    p = _arm(tmp_path, ledger, series, inbox)
    _wait_lock(tmp_path / "locks" / "S1.feedbackwatch.lock", True)
    _wait_ready(tmp_path / "locks" / "S1.feedbackwatch.lock")
    (inbox / "01KZ.md").write_text(
        "---\nid: 01KZ\nkind: request\nack: required\nagent: kaizen\n---\nx\n"
    )
    out, err = p.communicate(timeout=15)
    assert p.returncode == 0 and "mail.py claim 01KZ" in out, out + err


# --- 6. the per-prompt check orders the arm for kaizen windows only ------------------------------
def _check(tmp_path: Path, agent: str | None, feedback_held: bool, cwd: str = "/opt/fabrik") -> str:
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    # HERMETIC: a fresh HOME with no `~/.claude/bin/claude-selfwatch.sh` — the kaizen order must
    # not depend on the self-watch binary (pass 1, A-S1/A-S2); a trailing slash on the hub root
    # must not break the gate (D-S5)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    e = {
        **os.environ,
        "CLAUDE_SOUND_LOCKDIR": str(locks),
        "FABRIK_HUB_ROOT": "/opt/fabrik/",
        "HOME": str(home),
        "AGENT_IDENTITY_FILE": str(tmp_path / "identity.jsonl"),
    }
    (tmp_path / "identity.jsonl").write_text("")
    for k in ("CLAUDE_MESH_HEADLESS", "FABRIK_HEADLESS", "CLAUDE_AGENT"):
        e.pop(k, None)
    if agent:
        e["CLAUDE_AGENT"] = agent
    # the self-watch itself is ARMED in every case (the normal state of a live window), so the
    # only line that can print is the feedback-watch order — Opus #6: the branch must run before
    # the self-watch's early return
    fds = [os.open(str(locks / f"{SID}.selfwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)]
    fcntl.flock(fds[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
    if feedback_held:
        fds.append(
            os.open(str(locks / f"{SID}.feedbackwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
        )
        fcntl.flock(fds[-1], fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        proc = subprocess.run(
            [sys.executable, str(CHECK)],
            env=e,
            capture_output=True,
            text=True,
            input=json.dumps({"session_id": SID, "cwd": cwd}),
            timeout=30,
        )
    finally:
        for fd in fds:
            os.close(fd)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_feedback_watch_order_only_for_kaizen_in_the_hub(tmp_path):
    out = _check(tmp_path, "kaizen", feedback_held=False)
    assert "feedback_watch_arm.sh" in out and SID in out, out
    assert "feedback_watch_arm.sh" in _check(
        tmp_path, "kaizen", False, cwd="/opt/fabrik/.claude/worktrees/kaizen"
    )
    assert _check(tmp_path, "kaizen", feedback_held=True) == ""
    assert _check(tmp_path, "kaizen", False, cwd="/opt/tryton-crm") == "", (
        "a project window named kaizen is not the hub's"
    )
    assert _check(tmp_path, "infra", feedback_held=False) == ""
    assert _check(tmp_path, None, feedback_held=False) == ""


# --- 7. the charter is injected -----------------------------------------------------------------
def test_kaizen_charter_is_injected():
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_AGENT"}
    env.update({"CLAUDE_AGENT": "kaizen", "CLAUDE_PROJECT_DIR": str(ROOT)})
    r = subprocess.run(
        [sys.executable, str(ROLE_HOOK)], capture_output=True, text=True, timeout=30, env=env
    )
    assert r.returncode == 0 and "AGENT ROLE: kaizen" in r.stdout and "Mandate" in r.stdout
