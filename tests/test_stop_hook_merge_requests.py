"""The Stop hook holds a merge owner with a waiting request (T04; spec 2026-09-30-merge-request-loop
§ The delta 6 D-B/D-C, § The delta 8, § Validation V8).

Every case drives the REAL hook (`main`) over a throwaway main checkout with a clean tree, so the
only cause that can speak is the seventh. Requests are written with `scripts/mail.py`'s own
`_frontmatter`, records with `scripts/merge_request.py`'s own `_new_record`/`_save` (the
Interfaces seam: this ticket reads records T03's code writes). Resolvers are stubbed by argv
unless a test names the real ones — and the real ones are THIS tree's copies, never `/opt/fabrik`.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest

_TREE = Path(__file__).resolve().parents[1]
_HOOK = _TREE / ".claude" / "hooks" / "final_gate_stop.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("fgs_merge_requests", _HOOK)
mail = _load("mail_for_fgs_merge_requests", _TREE / "scripts" / "mail.py")
mr = _load("merge_request_for_fgs", _TREE / "scripts" / "merge_request.py")

SID = "sid-merge-owner"
OWNER = "beta"


def _say(text: str, rc: int = 0) -> tuple[str, ...]:
    """A resolver stub: prints `text`, exits `rc` (extra argv — the repo root — is ignored)."""
    return (sys.executable, "-c", f"import sys; print({text!r}); sys.exit({rc})")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path: Path) -> None:
    """No hook side effect reaches the operator's real state; git reads no user config."""
    assert Path(hook.__file__).resolve() == _HOOK.resolve(), (
        "the hook under test is not THIS tree's"
    )
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("THREAD_ANCHOR_DIR", str(tmp_path / "threads"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(tmp_path / "identity.jsonl"))
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(tmp_path / "mail"))
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(hook, "_MERGE_OWNER_ARGV", _say(OWNER))
    monkeypatch.setattr(hook, "_WHOAMI_ARGV", _say(OWNER))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()


def _repo(tmp_path: Path, owner_row: str | None = None) -> Path:
    """A clean main checkout named `repo` with the hook's `scripts/final_gate.py` sentinel."""
    main = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(main)], check=True, timeout=30)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(main, "config", *cfg)
    (main / "scripts").mkdir()
    (main / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    (main / "docs").mkdir()
    ledger = "| ID | Date | Who | Decision | Why | Ref |\n|---|---|---|---|---|---|\n"
    if owner_row:
        ledger += f"| D-001 | 2026-10-01 | test | MERGE OWNER: {owner_row} | fixture | none |\n"
    (main / "docs" / "DECISIONS.md").write_text(ledger, encoding="utf-8")
    (main / ".gitignore").write_text(".fabrik/\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _request(tmp_path: Path, mid: str, agent: str = OWNER, ack: str = "required") -> Path:
    inbox = tmp_path / "mail" / "repo" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    text = mail._frontmatter(
        mid,
        "worker",
        "repo",
        "2026-10-01T00:00:00Z",
        "",
        "merge-request",
        ack,
        "branch: b\n",
        agent=agent,
    )
    f = inbox / f"{mid}.md"
    f.write_text(text, encoding="utf-8")
    return f


def _ctx(main: Path) -> object:
    return mr._Ctx(main, main / ".git", OWNER)


def _record(main: Path, mid: str, phase: str, **override: object) -> dict:
    """A record written by T03's own code — `_new_record` stamps THIS live process as claimer."""
    ctx = _ctx(main)
    rec = mr._new_record(ctx, mid, {"branch": "b", "base": "master"}, phase=phase)
    if override:
        rec.update(override)
        mr._save(ctx, rec)
    return rec


def _drive(monkeypatch, cwd: Path, lam: str | None = None) -> tuple[dict | None, str]:
    payload: dict = {"cwd": str(cwd), "session_id": SID}
    if lam is not None:
        payload["last_assistant_message"] = lam
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert hook.main([]) == 0
    text = out.getvalue().strip()
    return (json.loads(text) if text else None), err.getvalue()


def _slots(tmp_path: Path) -> list[str]:
    p = hook._counter_path(SID)
    assert Path(p).parent == tmp_path
    return p.read_text().split(",") if p.exists() else []


def test_a_waiting_request_blocks_the_owner_and_warns_through_at_cap(monkeypatch, tmp_path):
    """V8: an unclaimed request addressed to the owner blocks with the merge command; the fourth
    Stop warns through and re-arms."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQAAAA")
    for attempt in range(1, hook.CAP + 1):
        out, _ = _drive(monkeypatch, main)
        assert out is not None and out["decision"] == "block", attempt
        assert f"attempt {attempt}/{hook.CAP}" in out["reason"]
        assert "python3 scripts/merge_request.py merge" in out["reason"]
        assert "01MREQAAAA" in out["reason"]
        assert _slots(tmp_path)[6] == str(attempt)
    out, err = _drive(monkeypatch, main)
    assert out is None, "the cause must warn through after CAP blocks"
    assert "merge request still waits" in err
    assert not _slots(tmp_path) or _slots(tmp_path)[6] == "0"


def test_the_coordinators_copy_and_another_agents_request_do_not_block(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    _request(tmp_path, "01MCOPYAAA", agent=OWNER, ack="no")
    _request(tmp_path, "01MOTHERAA", agent="gamma")
    out, _ = _drive(monkeypatch, main)
    assert out is None


@pytest.mark.parametrize("shape", ["dead-pid", "reused-pid", "no-pid"])
def test_a_stranded_record_blocks_with_resume(monkeypatch, tmp_path, shape):
    """A record short of `replied` whose process is gone — dead, or a pid alive under a different
    start time, or never recorded — blocks with `resume <id>`."""
    main = _repo(tmp_path)
    if shape == "dead-pid":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        start = mr._proc_start(child.pid)
        child.kill()
        child.wait(timeout=10)
        _record(main, "01MSTRAND1", "built", pid=child.pid, start=start)
    elif shape == "reused-pid":
        _record(main, "01MSTRAND1", "built", pid=os.getpid(), start="1")
    else:
        _record(main, "01MSTRAND1", "claiming", pid=None)
    out, _ = _drive(monkeypatch, main)
    assert out is not None and out["decision"] == "block"
    assert "python3 scripts/merge_request.py resume 01MSTRAND1" in out["reason"]


@pytest.mark.parametrize("phase", ["built", "replied"])
def test_a_live_or_replied_record_does_not_block(monkeypatch, tmp_path, phase):
    """A record naming a live process with its own start time is a run in flight, not stranded;
    a `replied` record is done whatever its pid says."""
    main = _repo(tmp_path)
    rec = _record(main, "01MLIVEAAA", phase)
    assert rec["pid"] == os.getpid() and rec["start"] == mr._proc_start(os.getpid())
    if phase == "replied":
        _record(main, "01MLIVEAAA", phase, pid=None)
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_a_parked_catchup_names_the_hand_merge_and_resume(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQBBBB")
    _record(
        main,
        "01MPARKED1",
        "catchup-refused",
        pid=None,
        reason="origin/master moved: merge origin/master into master",
    )
    out, _ = _drive(monkeypatch, main)
    assert out is not None
    reason = out["reason"]
    assert "PARKED at catchup-refused" in reason
    assert "python3 scripts/merge_request.py resume 01MPARKED1" in reason
    assert "origin/master moved" in reason
    assert "after the parked request above is resolved" in reason


def test_silent_in_a_linked_worktree(monkeypatch, tmp_path):
    """Same inbox name, same records dir, a linked worktree: silent."""
    main = _repo(tmp_path)
    wt = (
        tmp_path / "wts" / "repo"
    )  # basename `repo`: the inbox name matches, only the git-dir differs
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    _request(tmp_path, "01MREQCCCC")
    _record(main, "01MSTRAND2", "built", pid=None)
    out, _ = _drive(monkeypatch, wt)
    assert out is None
    out, _ = _drive(monkeypatch, main)  # the control: the main checkout IS held
    assert out is not None


@pytest.mark.parametrize(
    "owner_argv, caller_argv",
    [
        pytest.param(_say("UNDECLARED", 3), _say(OWNER), id="undeclared"),
        pytest.param(_say(OWNER), _say("alpha"), id="non-owner"),
        pytest.param(_say(OWNER), _say("", 1), id="unknown-caller"),
        pytest.param(("/nonexistent/decisions.py",), _say(OWNER), id="owner-resolver-missing"),
    ],
)
def test_silent_for_undeclared_non_owner_or_a_failed_resolver(
    monkeypatch, tmp_path, owner_argv, caller_argv
):
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQDDDD")
    _record(main, "01MSTRAND3", "built", pid=None)
    monkeypatch.setattr(hook, "_MERGE_OWNER_ARGV", owner_argv)
    monkeypatch.setattr(hook, "_WHOAMI_ARGV", caller_argv)
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_no_subprocess_at_all_when_nothing_waits(monkeypatch, tmp_path):
    """(f) The per-Stop path forks nothing — not a resolver, not even `git rev-parse` — when the
    inbox and the records dir are empty; a cwd in a subdirectory still finds the checkout."""
    main = _repo(tmp_path)
    calls: list[list[str]] = []

    def forbidden(cmd, *a, **k):
        calls.append(list(cmd))  # recorded, not raised: the duty's own except would swallow it
        raise AssertionError(f"subprocess on the empty path: {cmd}")

    monkeypatch.setattr(hook.subprocess, "run", forbidden)
    assert hook._merge_owner_duty(main, SID) is None
    assert hook._merge_owner_duty(main / "scripts", SID) is None
    assert calls == [], calls


@pytest.mark.parametrize("bound, blocks", [("beta", True), ("alpha", False)])
def test_the_real_resolvers_bind_the_owner_through_the_identity_file(
    monkeypatch, tmp_path, bound, blocks
):
    """A ledger with ONE `MERGE OWNER: beta` row, and a session bound only through the identity
    file (no CLAUDE_AGENT): `beta` is held, `alpha` is not."""
    main = _repo(tmp_path, owner_row="beta")
    monkeypatch.setattr(
        hook,
        "_MERGE_OWNER_ARGV",
        (sys.executable, str(_TREE / "scripts" / "decisions.py"), "--merge-owner"),
    )
    monkeypatch.setattr(
        hook, "_WHOAMI_ARGV", (sys.executable, str(_TREE / "scripts" / "whoami_agent.py"), "--who")
    )
    (tmp_path / "identity.jsonl").write_text(
        json.dumps({"session_id": SID, "name": bound}) + "\n", encoding="utf-8"
    )
    _request(tmp_path, "01MREQEEEE", agent="beta")
    out, _ = _drive(monkeypatch, main)
    assert (out is not None) is blocks
    if blocks:
        assert "merge owner (beta)" in out["reason"]


def test_a_resolver_that_cannot_start_is_silence(monkeypatch, tmp_path):
    """`subprocess.run` raising FileNotFoundError for the resolver: silent, never a crash."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQFFFF")
    real = hook.subprocess.run

    def no_python(cmd, *a, **k):
        if cmd and cmd[0] == sys.executable:
            raise FileNotFoundError(cmd[0])
        return real(cmd, *a, **k)

    monkeypatch.setattr(hook.subprocess, "run", no_python)
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_a_six_field_counter_reads_and_an_unrelated_block_keeps_the_merge_count(
    monkeypatch, tmp_path
):
    """A 6-field counter from before this change reads with the new slot 0 and its gate/commit
    counts kept; the merge cause reaches CAP after 3 blocks and warns through, and a stall block
    in between neither resets nor advances its slot."""
    main = _repo(tmp_path)
    ctr = hook._counter_path(SID)
    ctr.write_text("2,1,0,0,0,0")
    assert hook._read_counters(ctr) == (2, 1, 0, 0, 0, 0, 0)
    _request(tmp_path, "01MREQGGGG")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 1/3" in out["reason"]
    assert _slots(tmp_path) == ["2", "1", "0", "0", "0", "0", "1"]
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 2/3" in out["reason"]
    stall, _ = _drive(monkeypatch, main, lam="I'll run /fabrik-review on the diff now.")
    assert stall is not None and "MERGE REQUEST" not in stall["reason"], stall
    assert _slots(tmp_path)[6] == "2", "an unrelated block reset or advanced the merge slot"
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 3/3" in out["reason"]
    out, err = _drive(monkeypatch, main)
    assert out is None and "merge request still waits" in err


# --- review round 1 (S1, O1-O6, O8) ------------------------------------------------------------


def test_a_subdirectory_still_finds_the_main_checkout(tmp_path):
    """The `.git` walk from a subdirectory reaches the checkout (the hook itself only enforces
    from the repo root, `main()`'s `scripts/final_gate.py` check)."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQSUB1")
    reason = hook._merge_owner_duty(main / "scripts", SID)
    assert reason is not None and "01MREQSUB1" in reason


def test_the_production_owner_argv_with_a_missing_script_is_silence(monkeypatch, tmp_path):
    """(a) The production shape `(python, <missing>/decisions.py, --merge-owner)` exits non-zero."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQMISS")
    monkeypatch.setattr(
        hook,
        "_MERGE_OWNER_ARGV",
        (sys.executable, str(tmp_path / "missing" / "decisions.py"), "--merge-owner"),
    )
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_a_fifo_in_the_inbox_never_hangs_the_hook(tmp_path):
    """(b) `open()` on a FIFO with no writer blocks forever; the hook must not open it."""
    main = _repo(tmp_path)
    inbox = tmp_path / "mail" / "repo" / "inbox"
    inbox.mkdir(parents=True)
    fifo = inbox / "01MFIFOAAA.md"
    os.mkfifo(fifo)
    _request(tmp_path, "01MREQFIFO")
    result: list[object] = []
    t = threading.Thread(target=lambda: result.append(hook._merge_owner_duty(main, SID)))
    t.daemon = True
    t.start()
    t.join(timeout=15)
    hung = t.is_alive()
    if hung:  # release the blocked reader so the thread can exit
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(fd)
        t.join(timeout=5)
    assert not hung, "the hook blocked on a FIFO in the inbox"
    assert result and isinstance(result[0], str) and "01MREQFIFO" in result[0]


def test_a_deeply_nested_record_skips_only_itself(monkeypatch, tmp_path):
    """(c) A record json.loads cannot parse (RecursionError) must not hide a waiting request."""
    main = _repo(tmp_path)
    records = main / ".git" / "fabrik-merge"
    records.mkdir()
    (records / "01MDEEPAAA.json").write_text("[" * 200_000 + "]" * 200_000, encoding="utf-8")
    _request(tmp_path, "01MREQDEEP")
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "01MREQDEEP" in out["reason"]


def test_a_frontmatter_mail_py_rejects_is_not_waiting(monkeypatch, tmp_path):
    """(d) Parser parity: a bare line in the frontmatter makes `mail._parse` return None
    (`list_msgs` quarantines it, `merge` never sees it), so the hook must not wait on it."""
    main = _repo(tmp_path)
    inbox = tmp_path / "mail" / "repo" / "inbox"
    inbox.mkdir(parents=True)
    text = (
        "---\nid: 01MBAREAAA\nbareline\nkind: merge-request\nack: required\nagent: beta\n---\nx\n"
    )
    (inbox / "01MBAREAAA.md").write_text(text, encoding="utf-8")
    assert mail._parse(text) is None
    out, _ = _drive(monkeypatch, main)
    assert out is None


@pytest.mark.parametrize(
    "stem, rid",
    [
        pytest.param("01MSTEMAAA", "01MOTHERID", id="id-not-stem"),
        pytest.param("01M`whoami`", "01M`whoami`", id="backtick-id"),
    ],
)
def test_a_record_with_a_foreign_or_unsafe_id_is_skipped(monkeypatch, tmp_path, stem, rid):
    """(e) The id is pasted into a command in the block text: it must be the file's own stem and
    a mail-id shape, else the record is skipped."""
    main = _repo(tmp_path)
    records = main / ".git" / "fabrik-merge"
    records.mkdir()
    rec = {"id": rid, "phase": "built", "pid": None, "start": None}
    (records / f"{stem}.json").write_text(json.dumps(rec), encoding="utf-8")
    out, _ = _drive(monkeypatch, main)
    assert out is None


def test_a_non_owner_caller_never_runs_the_owner_resolver(monkeypatch, tmp_path):
    """(g) Only requests, none addressed to the caller: the caller resolver answers and the owner
    resolver is never started."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQELSE", agent="gamma")
    marker = tmp_path / "owner-ran"
    monkeypatch.setattr(
        hook,
        "_MERGE_OWNER_ARGV",
        (sys.executable, "-c", f"open({str(marker)!r}, 'w').close(); print('gamma')"),
    )
    monkeypatch.setattr(hook, "_WHOAMI_ARGV", _say("alpha"))
    out, _ = _drive(monkeypatch, main)
    assert out is None
    assert not marker.exists(), "the owner resolver ran for a caller no request names"


# --- review round 2 (O9): the walk agrees with git's own discovery ----------------------------


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE"])
def test_a_git_env_override_is_silence(monkeypatch, tmp_path, var):
    """A `GIT_DIR`/`GIT_COMMON_DIR`/`GIT_WORK_TREE` in the hook's environment makes git look
    elsewhere than the `.git` walk would; the cause stays silent rather than guess."""
    main = _repo(tmp_path)
    _request(tmp_path, "01MREQENVA")
    assert hook._merge_owner_duty(main, SID) is not None  # the control: held without the var
    monkeypatch.setenv(var, str(main / ".git"))
    assert hook._merge_owner_duty(main, SID) is None


def test_a_git_dir_without_head_is_not_a_checkout(tmp_path):
    """A `.git` directory git rejects (no `HEAD` file) is not a repository: silent."""
    stub = tmp_path / "stub" / "repo"  # basename `repo`: the fixture inbox name matches
    (stub / ".git").mkdir(parents=True)
    _request(tmp_path, "01MREQSTUB")
    assert hook._merge_owner_duty(stub, SID) is None
