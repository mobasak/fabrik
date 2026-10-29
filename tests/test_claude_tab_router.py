"""W-ea993618 stage 2 — the VS Code chat-tab ROUTER (scripts/sysadmin/claude_tab_router.py) and the wrapper that calls
it (scripts/sysadmin/claude-agent-wrapper.sh, installed at ~/.claude/bin/claude-agent-wrapper.sh).

The router is driven against a fixture HOME + /proc + /opt (tests/test_hibernate.py's Box), never the live box; the
wrapper end to end with a fake "binary" that records its cwd, CLAUDE_AGENT, argv and the stdin it receives, and a stub
router (CLAUDE_TAB_ROUTER_CMD) answering a fixed pick, a cancel, a crash or a hang.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from tests.test_hibernate import ROOT, Box, _load

ROUTER = ROOT / "scripts" / "sysadmin" / "claude_tab_router.py"
WRAPPER = ROOT / "scripts" / "sysadmin" / "claude-agent-wrapper.sh"
CHAT = [
    "--output-format",
    "stream-json",
    "--verbose",
    "--input-format",
    "stream-json",
    "--thinking=disabled",
]
SID_YT = "11111111-1111-1111-1111-111111111111"
SID_FLEET = "22222222-2222-2222-2222-222222222222"
SID_SX = "33333333-3333-3333-3333-333333333333"  # session ids are UUIDs (the router rejects others)


@pytest.fixture()
def r():
    return _load("claude_tab_router", ROUTER)


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = Box(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(b.home / ".claude"))
    return b


def _transcript(box: Box, cwd: str, sid: str, mtime: float = 1_790_000_000) -> Path:
    d = (
        box.home
        / ".claude"
        / "projects"
        / cwd.replace("/", "-").replace("_", "-").replace(".", "-")
    )
    d.mkdir(parents=True, exist_ok=True)
    t = d / f"{sid}.jsonl"
    t.write_text(
        json.dumps({"type": "user", "cwd": cwd, "sessionId": sid}) + "\n", encoding="utf-8"
    )
    os.utime(t, (mtime, mtime))
    return t


def _agents(repo: str, mapping: dict[str, str]) -> None:
    (Path(repo) / ".fabrik").mkdir(parents=True, exist_ok=True)
    (Path(repo) / ".fabrik" / "session-agents.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )


# ── the pure parts ───────────────────────────────────────────────────────────────────────────────────────────────


def test_rewrite_args_cases(r, tmp_path):
    new = str(tmp_path)
    argv = [
        "/bin/claude",
        *CHAT,
        "--resume=old",
        "--add-dir=/opt/youtube",
        "--add-dir",
        "/opt/x",
        "--debug",
    ]
    out = r.rewrite_args(argv, {"kind": r.RESUME, "sid": "S1"}, new)
    # every --add-dir dropped (a foreign agent gets no window repo), the old resume replaced, the rest kept in order
    assert out == ["/bin/claude", *CHAT, "--debug", "--resume=S1"]
    out = r.rewrite_args(
        ["/bin/claude", *CHAT, "--resume", "old", "-c"], {"kind": r.NEW_ROLE, "new_sid": "N"}, new
    )
    assert out == ["/bin/claude", *CHAT, "--session-id=N"]
    plain = ["/bin/claude", *CHAT, "--resume=keep", "--add-dir=/opt/youtube"]
    assert r.rewrite_args(plain, {"kind": r.PLAIN}, new) == plain


def test_slug_matches_the_cli_project_directory_names(r):
    assert r.slug("/opt/fabrik/.claude/worktrees/fleet") == "-opt-fabrik--claude-worktrees-fleet"
    assert r.slug("/opt/iterative_image_editor") == "-opt-iterative-image-editor"


# ── the entry list ───────────────────────────────────────────────────────────────────────────────────────────────


def test_entries_from_fixture_box(r, box):
    yt = box.repo("youtube", owner="youtube-coordinator")
    hub = box.repo("fabrik", owner="coordinator")
    box.repo("quiet", owner="nobody-here")  # no git entry and no known agent: not listed
    _agents(yt, {SID_YT: "yt1"})
    _agents(hub, {SID_FLEET: "fleet"})
    # the identity store binds the coordinator's session; last row per sid wins
    box.store += [
        {"session_id": SID_SX, "name": "yt2", "toplevel": yt + "/.git"},
        {"session_id": SID_SX, "name": "youtube-coordinator", "toplevel": yt + "/.git"},
    ]
    (box.home / ".claude" / "state" / "agent-identity.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in box.store), encoding="utf-8"
    )
    _transcript(box, yt, SID_YT, 1_790_000_000)
    _transcript(box, yt, SID_SX, 1_790_000_500)
    rows = r.entries(box.home, box.proc, str(box.opt))
    labels = [x["label"] for x in rows]
    assert any(
        x["kind"] == r.RESUME and x["role"] == "youtube-coordinator" and x["sid"] == SID_SX
        for x in rows
    )
    assert any(
        x["kind"] == r.RESUME and x["role"] == "yt1" and x["sid"] == SID_YT and x["cwd"] == yt
        for x in rows
    )
    assert not any(x.get("role") == "yt2" for x in rows), (
        "SID_SX's LAST binding is youtube-coordinator, not yt2"
    )
    assert "New session in youtube" in labels and "New session in fabrik" in labels
    assert "New session in quiet" not in labels
    # the merge owner joins a listed repo's roles even with no session of its own
    assert any(
        x["kind"] == r.NEW_ROLE and x["role"] == "coordinator" and x["repo"] == hub for x in rows
    )


def test_live_role_is_refused(r, box):
    hub = box.repo("fabrik", owner="coordinator")
    _agents(hub, {SID_FLEET: "fleet"})
    _transcript(box, hub, SID_FLEET)
    box.session(4242, SID_FLEET, hub, "fleet", env_agent="fleet")
    rows = r.entries(box.home, box.proc, str(box.opt))
    fleet = [x for x in rows if x.get("role") == "fleet"]
    assert [x["kind"] for x in fleet] == [r.LIVE] and "live elsewhere (pid 4242)" in fleet[0][
        "label"
    ]
    # a pick of the live row is a plain launch, never a resume
    out = r.route(
        hub,
        ["/bin/claude", *CHAT],
        box.home,
        box.proc,
        str(box.opt),
        chooser=lambda rows, cwd: fleet[0],
    )
    assert out is None
    # the same live process is THIS tab reattaching when it resumes that very sid: not "elsewhere"
    rows = r.entries(box.home, box.proc, str(box.opt), own_sid=SID_FLEET)
    assert {x["kind"] for x in rows if x.get("role") == "fleet"} == {r.RESUME, r.NEW_ROLE}


def test_router_map_session_counts_as_live(r, box):
    yt = box.repo("youtube", owner=None)
    r.record(box.home, "M1", "yt3", yt, yt)
    box.session(
        5151, "M1", yt, "x"
    )  # no CLAUDE_AGENT, no identity row: found by its sid in the router's map
    rows = r.entries(box.home, box.proc, str(box.opt))
    assert [x["kind"] for x in rows if x.get("role") == "yt3"] == [r.LIVE]


def test_unbindable_role_is_not_offered(r, box):
    yt = box.repo("youtube", owner=None)
    _agents(yt, {SID_YT: "Bad Name"})
    _transcript(box, yt, SID_YT)
    rows = r.entries(box.home, box.proc, str(box.opt))
    assert not any(
        x["kind"] in (r.RESUME, r.NEW_ROLE) and x.get("role") == "Bad Name" for x in rows
    )


# ── route ────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_route_resume_pick_and_new_role_records_its_session(r, box):
    yt = box.repo("youtube", owner="youtube-coordinator")
    hub = box.repo("fabrik", owner=None)
    _agents(yt, {SID_YT: "youtube-coordinator"})
    _transcript(box, yt, SID_YT)
    argv = ["/bin/claude", *CHAT, "--add-dir=" + yt]

    def pick(kind):
        return lambda rows, cwd: next(
            x for x in rows if x["kind"] == kind and x.get("role") == "youtube-coordinator"
        )

    out = r.route(hub, argv, box.home, box.proc, str(box.opt), chooser=pick(r.RESUME))
    assert out == [yt, "youtube-coordinator", "/bin/claude", *CHAT, f"--resume={SID_YT}"]
    out = r.route(hub, argv, box.home, box.proc, str(box.opt), chooser=pick(r.NEW_ROLE))
    assert out[:2] == [yt, "youtube-coordinator"] and out[-1].startswith("--session-id=")
    new_sid = out[-1].split("=", 1)[1]
    rows = [
        json.loads(x)
        for x in (box.home / ".claude" / "state" / "tab-router.jsonl").read_text().splitlines()
    ]
    assert rows[-1]["sid"] == new_sid and rows[-1]["role"] == "youtube-coordinator"


def test_restored_foreign_tab_is_rerooted_without_a_picker(r, box):
    yt = box.repo("youtube", owner=None)
    hub = box.repo("fabrik", owner=None)
    _transcript(box, yt, SID_YT)
    r.record(box.home, SID_YT, "yt1", yt, yt)

    def never(rows, cwd):
        raise AssertionError("no picker on a restore")

    argv = ["/bin/claude", *CHAT, f"--resume={SID_YT}", "--add-dir=" + yt]
    assert r.route(hub, argv, box.home, box.proc, str(box.opt), chooser=never) == [
        yt,
        "yt1",
        "/bin/claude",
        *CHAT,
        f"--resume={SID_YT}",
    ]
    # the operator's own history pick (the tab's own project) passes through: no picker, plain launch
    _transcript(box, hub, SID_FLEET)
    assert (
        r.route(
            hub,
            ["/bin/claude", *CHAT, f"--resume={SID_FLEET}"],
            box.home,
            box.proc,
            str(box.opt),
            chooser=never,
        )
        is None
    )


def test_non_chat_launches_never_reach_the_picker(r, box):
    def never(rows, cwd):
        raise AssertionError("picker on a non-chat launch")

    assert (
        r.route(
            "/tmp",
            ["/bin/claude", "auth", "status", "--json"],
            box.home,
            box.proc,
            str(box.opt),
            chooser=never,
        )
        is None
    )


# ── the wrapper, end to end ──────────────────────────────────────────────────────────────────────────────────────


def _wrapper_env(tmp: Path, stub_body: str | None, **extra: str) -> tuple[dict, Path, Path]:
    fake = tmp / "fakeclaude"
    rec = tmp / "launched.json"
    fake.write_text(
        textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, os, sys
        data = sys.stdin.read()
        json.dump({{"cwd": os.getcwd(), "agent": os.environ.get("CLAUDE_AGENT", ""), "argv": sys.argv[1:],
                   "stdin": data}}, open({str(rec)!r}, "w"))
        """),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "PYTEST"))}
    env.update({"CLAUDE_AGENT_WRAPPER_LOG": str(tmp / "wrapper.log"), "HOME": str(tmp)})
    if stub_body is not None:
        stub = tmp / "stub_router.py"
        stub.write_text("import sys, time, os\n" + textwrap.dedent(stub_body), encoding="utf-8")
        env["CLAUDE_TAB_ROUTER_CMD"] = str(stub)
    env.update(extra)
    return env, fake, rec


def _run_wrapper(tmp: Path, env: dict, fake: Path, args: list[str], cwd: Path, timeout: float = 90):
    start = time.monotonic()
    p = subprocess.run(
        ["bash", str(WRAPPER), str(fake), *args],
        cwd=cwd,
        env=env,
        input=b'{"type":"init"}\n',
        capture_output=True,
        timeout=timeout,
    )
    return p, time.monotonic() - start


def test_wrapper_applies_a_resume_pick(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    env, fake, rec = _wrapper_env(
        tmp_path,
        f"""\
        sys.stdin.read()  # R6: a router that reads stdin would eat the CLI's initialize message unless the wrapper withholds it
        sys.stdout.write("\\0".join([{str(target)!r}, "yt1", sys.argv[sys.argv.index("--") + 1], "--x", "--resume=S9"]))
        """,
    )
    p, _ = _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    got = json.loads(rec.read_text())
    assert (
        p.returncode == 0 and p.stdout == b"" and p.stderr == b""
    )  # nothing of the wrapper's own on the pipes
    assert (
        got["cwd"] == str(target)
        and got["agent"] == "yt1"
        and got["argv"] == ["--x", "--resume=S9"]
    )
    assert got["stdin"] == '{"type":"init"}\n', (
        "the initialize message must reach the CLI, not the router"
    )


@pytest.mark.parametrize(
    "body", ["sys.exit(1)\n", "raise SystemExit(3)\n", "sys.stdout.write('half')\nsys.exit(2)\n"]
)
def test_wrapper_falls_back_to_plain_launch(tmp_path, body):
    env, fake, rec = _wrapper_env(tmp_path, body)
    p, _ = _run_wrapper(tmp_path, env, fake, [*CHAT, "--resume=keep"], tmp_path)
    got = json.loads(rec.read_text())
    assert (
        got["cwd"] == str(tmp_path)
        and got["argv"] == [*CHAT, "--resume=keep"]
        and got["agent"] == ""
    )


def test_wrapper_bounds_a_hung_router(tmp_path):
    env, fake, rec = _wrapper_env(tmp_path, "time.sleep(600)\n")
    p, took = _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    assert (
        json.loads(rec.read_text())["argv"] == CHAT and took < 50
    )  # well inside the extension's 60 s


def test_auth_status_and_config_probe_launches_bypass_router(tmp_path):
    env, fake, rec = _wrapper_env(
        tmp_path, "open(os.environ['HOME'] + '/ROUTER_RAN', 'w')\nsys.exit(1)\n"
    )
    _run_wrapper(tmp_path, env, fake, ["auth", "status", "--json"], tmp_path)
    assert not (tmp_path / "ROUTER_RAN").exists()
    env["CLAUDE_CODE_CONFIG_PROBE"] = "1"
    _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    assert not (tmp_path / "ROUTER_RAN").exists()
    env.pop("CLAUDE_CODE_CONFIG_PROBE")
    env["CLAUDE_TAB_ROUTER"] = "off"
    _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    assert not (tmp_path / "ROUTER_RAN").exists()
    env.pop("CLAUDE_TAB_ROUTER")
    _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    assert (tmp_path / "ROUTER_RAN").exists(), "a plain chat launch DOES ask the router"


def test_wrapper_failed_cd_launches_plain(tmp_path):
    env, fake, rec = _wrapper_env(
        tmp_path,
        """\
        sys.stdout.write("\\0".join(["/nonexistent/dir", "yt1", sys.argv[sys.argv.index("--") + 1], "--resume=S9"]))
        """,
    )
    _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    got = json.loads(rec.read_text())
    assert got["cwd"] == str(tmp_path) and got["argv"] == CHAT and got["agent"] == ""


def test_router_exits_when_the_wrapper_dies(r, tmp_path):
    """The picker's watchdog: a dead wrapper pid ends the picker on its next tick."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert r.wrapper_alive(dead.pid) is False
    assert r.wrapper_alive(os.getpid()) is True
    assert r.wrapper_alive(0) is True  # no pid given: never treated as dead


# Review pass 1 (W-ea993618, resumed 2026-10-21): R1, R2, R7 -------------------------------------------------------
def test_restore_of_a_session_live_elsewhere_is_not_rerooted(r, box):
    yt = box.repo("youtube", owner=None)
    hub = box.repo("fabrik", owner=None)
    _transcript(box, yt, SID_YT)
    r.record(box.home, SID_YT, "yt1", yt, yt)
    box.session(
        6161, SID_YT, yt, "yt1", env_agent="yt1"
    )  # the session already runs in another window

    def never(rows, cwd):
        raise AssertionError("no picker on a restore")

    argv = ["/bin/claude", *CHAT, f"--resume={SID_YT}"]
    assert r.route(hub, argv, box.home, box.proc, str(box.opt), chooser=never) is None


def test_a_role_live_in_one_repo_does_not_block_the_same_role_in_another(r, box):
    a = box.repo("alpha", owner="coordinator")
    b = box.repo("beta", owner="coordinator")
    _agents(a, {SID_YT: "builder"})  # entries lists repos the registries know
    _agents(b, {SID_FLEET: "builder"})
    box.session(7171, "S-A", a, "coordinator", env_agent="coordinator")
    rows = r.entries(box.home, box.proc, str(box.opt))
    kinds = {(x["repo"], x["kind"]) for x in rows if x.get("role") == "coordinator"}
    assert (a, r.LIVE) in kinds
    assert (b, r.LIVE) not in kinds and (b, r.NEW_ROLE) in kinds


def test_a_non_uuid_resume_id_never_reaches_the_glob(r, box):
    hub = box.repo("fabrik", owner=None)
    yt = box.repo("youtube", owner=None)
    _transcript(
        box, yt, SID_YT
    )  # a `*` id would glob-match this foreign transcript and re-root the tab
    for bad in ("*", "../x", "a/b", "[x]"):
        argv = ["/bin/claude", *CHAT, f"--resume={bad}"]
        assert (
            r.route(hub, argv, box.home, box.proc, str(box.opt), chooser=lambda rows, cwd: None)
            is None
        )


def test_wrapper_drops_an_inherited_agent_on_a_roleless_pick(tmp_path):
    """R3: a pick with no role (New session in repo) must not run as the window's own agent."""
    target = tmp_path / "repo"
    target.mkdir()
    env, fake, rec = _wrapper_env(
        tmp_path,
        f"""\
        sys.stdout.write("\\0".join([{str(target)!r}, "", sys.argv[sys.argv.index("--") + 1], "--x"]))
        """,
        CLAUDE_AGENT="fleet",
    )
    p, _ = _run_wrapper(tmp_path, env, fake, CHAT, tmp_path)
    got = json.loads(rec.read_text())
    assert p.returncode == 0 and got["cwd"] == str(target)
    assert got["agent"] == "", (
        "an inherited CLAUDE_AGENT would bind the new session to the window's agent"
    )


def test_rewrite_drops_every_value_of_a_variadic_add_dir(r):
    """R4: `claude --help` lists `--add-dir <directories...>`; every value after it belongs to it."""
    argv = ["/bin/claude", "--add-dir", "/opt/a", "/opt/b", "--x", "--add-dir=/opt/c", "/opt/d"]
    out = r.rewrite_args(argv, {"kind": r.RESUME, "sid": SID_YT}, "/opt/yt")
    assert out == ["/bin/claude", "--x", f"--resume={SID_YT}"]


def test_picker_deadline_counts_from_the_router_start(r, monkeypatch):
    """R5: time spent listing repos before the picker opens comes off the 30 s, so the router ends inside the
    wrapper's `timeout 35` instead of being killed mid-countdown."""
    monkeypatch.setattr(r, "_STARTED", 1000.0)
    monkeypatch.setattr(r.time, "monotonic", lambda: 1020.0)  # 20 s already spent on entries()
    assert r.picker_deadline() == 1030.0


# ── W-5f4b0972: every git repo under the opt root offers its coordinator ──────────────────────────────────────────


def _git(repo: str) -> str:
    (Path(repo) / ".git").mkdir(exist_ok=True)
    return repo


def _no_owner_ledger(repo: str) -> str:
    (Path(repo) / "docs" / "DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        "| D-001 | 2026-10-29 | x | an unrelated decision | why | here |\n",
        encoding="utf-8",
    )
    return repo


def _role_rows(rows, repo):
    return [x for x in rows if x["repo"] == repo and x.get("role")]


def test_an_unlisted_git_repo_offers_its_merge_owner(r, box):
    """A repo no registry knows is listed once it is a git repo, and offers its declared merge owner."""
    yt = _git(box.repo("youtube", owner="youtube-coordinator"))
    rows = r.entries(box.home, box.proc, str(box.opt))
    assert "New session in youtube" in [x["label"] for x in rows]
    assert any(
        x["kind"] == r.NEW_ROLE and x["role"] == "youtube-coordinator" and x["cwd"] == yt
        for x in rows
    )


def test_a_repo_without_a_merge_owner_offers_the_default_coordinator(r, box):
    """A ledger with no MERGE OWNER row (exit 3) earns the default `coordinator`, and the row says why."""
    candle = _no_owner_ledger(_git(box.repo("candle", owner=None)))
    roles = _role_rows(r.entries(box.home, box.proc, str(box.opt)), candle)
    assert [(x["kind"], x["role"]) for x in roles] == [(r.NEW_ROLE, "coordinator")]
    assert roles[0]["label"] == "New session as coordinator in candle (no owner row)"


def test_no_default_coordinator_without_a_no_owner_answer(r, box, monkeypatch):
    """Only the ledger's "no owner" answer earns the default: a missing ledger, a failed lookup and a lookup that
    raises all give no coordinator row (never a guessed name), and a folder with no git entry is not listed."""
    _git(box.repo("noledger", owner=None))  # Box writes no ledger for owner=None
    failed = _no_owner_ledger(_git(box.repo("failed", owner=None)))
    boom = _no_owner_ledger(_git(box.repo("boom", owner=None)))
    _no_owner_ledger(box.repo("scratch", owner=None))  # a ledger but no git entry
    # positive control: a real lookup in the same call still names its owner
    ok = _git(box.repo("ok", owner="ok1"))
    real = r.hibernate.merge_owner

    def fake(repo, **kw):
        if repo == failed:
            return "", "lookup failed (exit 2)"
        if repo == boom:
            raise RuntimeError("unexpected")
        return real(repo, **kw)

    monkeypatch.setattr(r.hibernate, "merge_owner", fake)
    rows = r.entries(box.home, box.proc, str(box.opt))
    labels = [x["label"] for x in rows]
    want = {"New session in noledger", "New session in failed", "New session in boom"}
    assert want <= set(labels)
    assert "New session in scratch" not in labels
    assert [x["role"] for x in _role_rows(rows, ok)] == ["ok1"]
    others = [x for x in rows if x.get("role") and x["repo"] != ok]
    assert not others, "no repo but the control may offer a coordinator"


def test_a_hung_lookup_costs_only_its_own_row(r, box, monkeypatch):
    """A lookup still running when the budget ends costs its repo's coordinator row only; entries() returns
    within the budget instead of holding the picker past its deadline."""
    import threading

    slow = _git(box.repo("slow", owner="s1"))
    fast = _git(box.repo("fast", owner="f1"))
    release = threading.Event()

    def fake(repo, **kw):
        if repo == slow:
            release.wait(20)
            return "s1", "late"
        # no subprocess: a loaded box cannot push it past the budget
        return "f1", "the ledger's merge owner"

    monkeypatch.setattr(r.hibernate, "merge_owner", fake)
    # the router's own deadline function, never the global clock (W-1e0f4229): 5 s from now, so the
    # budget (deadline minus the 3 s reserve) is about 2 s
    now = time.monotonic()
    monkeypatch.setattr(r, "picker_deadline", lambda: now + 5.0)
    try:
        t0 = time.monotonic()
        rows = r.entries(box.home, box.proc, str(box.opt))
        took = time.monotonic() - t0
    finally:
        release.set()
    assert took < 4.0, f"entries() waited {took:.1f} s on a hung lookup"
    assert not _role_rows(rows, slow)
    assert [x["role"] for x in _role_rows(rows, fast)] == ["f1"]
    assert "New session in slow" in [x["label"] for x in rows]


def test_a_git_file_lists_the_repo_once_beside_its_known_agents(r, box):
    """A `.git` FILE (a linked layout) lists the repo, and a repo found both by a registry and by its git entry
    appears once: one "New session in" row and one coordinator row."""
    linked = box.repo("linked", owner="lk1")
    (Path(linked) / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    _agents(linked, {SID_YT: "builder"})
    alone = box.repo("alone", owner="al1")  # no registry knows it: only its `.git` file lists it
    (Path(alone) / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    rows = r.entries(box.home, box.proc, str(box.opt))
    assert [x["label"] for x in rows].count("New session in linked") == 1
    assert "New session as al1 in alone" in [x["label"] for x in rows]
    assert [x["role"] for x in rows if x["repo"] == linked and x["kind"] == r.NEW_ROLE] == [
        "builder",
        "lk1",
    ]


def test_a_trailing_slash_repo_key_lists_the_repo_once(r, box):
    """A registry row naming `/opt/x/` and the git entry `/opt/x` are one repo, not two."""
    x = _git(box.repo("x", owner="x1"))
    box.store.append({"session_id": SID_SX, "name": "xb", "toplevel": x + "/"})
    (box.home / ".claude" / "state" / "agent-identity.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in box.store), encoding="utf-8"
    )
    rows = r.entries(box.home, box.proc, str(box.opt))
    assert [x["label"] for x in rows].count("New session in x") == 1
    assert sorted(y["role"] for y in _role_rows(rows, x) if y["kind"] == r.NEW_ROLE) == ["x1", "xb"]


def test_merge_owner_timeout_keyword(r, box, monkeypatch):
    """hibernate.merge_owner hands its timeout to the subprocess and keeps 30 s for every other caller."""
    hub = box.repo("fabrik", owner="coordinator")
    seen = []
    real_run = r.hibernate.subprocess.run

    def spy(*a, **kw):
        seen.append(kw.get("timeout"))
        return real_run(*a, **kw)

    monkeypatch.setattr(r.hibernate.subprocess, "run", spy)
    assert r.hibernate.merge_owner(hub) == ("coordinator", "the ledger's merge owner")
    assert r.hibernate.merge_owner(hub, timeout=5) == ("coordinator", "the ledger's merge owner")
    assert seen == [30, 5]
    assert r.hibernate.DECLARES_NONE in r.hibernate.NO_OWNER
