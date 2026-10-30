"""`agents_bat.py` (W-bb6c9d9a, D-1042): one self-contained "<Repo> Agents.bat" per /opt repo with an agent registry.

Driven by subprocess against a tmp /opt and a tmp desktop — the operator's real desktop is never touched. No Windows
runner exists here, so the .bat TEXT is the subject: every cmd.exe trap the design names is asserted on it, and the
fragment JSON it writes is parsed back out of the echo block.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "sysadmin" / "agents_bat.py"
REG = {"610c3b1c-a5ef-4ba0-a662-f3f87399a58b": "fabrik-lib-dev1"}


def _opt(tmp: Path, *repos: str, bare: tuple[str, ...] = ()) -> Path:
    opt = tmp / "opt"
    for name in repos:
        (opt / name / ".fabrik").mkdir(parents=True)
        (opt / name / ".fabrik" / "session-agents.json").write_text(
            json.dumps(REG), encoding="utf-8"
        )
    for name in bare:
        (opt / name).mkdir(parents=True)
    opt.mkdir(exist_ok=True)
    return opt


# agents_up.sh is the authority on which repos have a grid (W-89474fc1); these tests are about the .bat, so a stand-in
# answers it: a repo with a registry or a `.grid` file has one pane. `test_bats_follow_agents_up` runs the real one.
FAKE_UP = """#!/bin/sh
[ -f "$2/.fabrik/session-agents.json" ] || [ -f "$2/.grid" ] || exit 2
echo "session x"
echo "pane x"
"""
_FAKE: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _fake_agents_up(tmp_path_factory: pytest.TempPathFactory) -> None:
    folder = tmp_path_factory.mktemp("agents-up")
    up = folder / "agents_up.sh"
    up.write_text(FAKE_UP, encoding="utf-8")
    _FAKE["bin"], _FAKE["home"] = str(up), str(folder)


def _run(
    *args: str,
    distro: str | None = "Ubuntu-24.04",
    up: str | None = None,
    cwd: Path | None = None,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    # HOME is a test folder, so nothing here can read the operator's identity store
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _FAKE["home"],
        "AGENTS_UP_BIN": up or _FAKE["bin"],
        **extra,
    }
    if distro is not None:
        env["WSL_DISTRO_NAME"] = distro
    return subprocess.run(
        [sys.executable, str(GEN), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=cwd,
    )


def _bat(desk: Path, name: str) -> str:
    raw = (desk / name).read_bytes()
    assert raw.isascii(), name
    assert all(ln.endswith(b"\r") for ln in raw.split(b"\n")[:-1]) and raw.endswith(b"\r\n"), (
        "every line ends CRLF"
    )
    return raw.decode("ascii")


def test_one_bat_per_registry_repo(tmp_path: Path) -> None:
    """A repo with a registry gets "<Repo> Agents.bat", only its first letter upper-cased; a repo without one gets
    nothing."""
    opt = _opt(tmp_path, "fabrik-lib", "myRepo", bare=("plain-repo",))
    desk = tmp_path / "desk"
    desk.mkdir()
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 0, out.stderr
    assert sorted(p.name for p in desk.iterdir()) == ["Fabrik-lib Agents.bat", "MyRepo Agents.bat"]


def test_print_mode_writes_nothing(tmp_path: Path) -> None:
    """Without --desktop it only reports each target and its text."""
    opt = _opt(tmp_path, "fabrik-lib")
    before = sorted(p for p in tmp_path.rglob("*"))
    out = _run("--opt", str(opt))
    assert out.returncode == 0, out.stderr
    assert "Fabrik-lib Agents.bat" in out.stdout and "agents_up.sh /opt/fabrik-lib" in out.stdout, (
        out.stdout
    )
    assert sorted(p for p in tmp_path.rglob("*")) == before
    # a --desktop that does not exist is refused, never created
    gone = tmp_path / "no-such-desk"
    out = _run("--opt", str(opt), "--desktop", str(gone))
    assert out.returncode == 2 and not gone.exists(), out.stderr
    # ... also when no repo has a registry, so a mistyped --desktop never reads as success
    empty = tmp_path / "empty-opt"
    empty.mkdir()
    out = _run("--opt", str(empty), "--desktop", str(gone))
    assert out.returncode == 2 and "not a folder" in out.stderr and not gone.exists(), out.stderr
    # a dry run of the real command, --replace included, reads the same as the real run: no false refusal
    out = _run("--opt", str(opt), "--replace", "Fabrik-lib Agents.bat")
    assert out.returncode == 0, out.stderr


def test_the_bat_text(tmp_path: Path) -> None:
    """Every cmd.exe trap the design names, read off the generated text."""
    opt = _opt(tmp_path, "fabrik-lib")
    desk = tmp_path / "desk"
    desk.mkdir()
    assert _run("--opt", str(opt), "--desktop", str(desk)).returncode == 0
    text = _bat(desk, "Fabrik-lib Agents.bat")
    lines = text.split("\r\n")
    assert lines[0] == "@echo off"
    assert any(ln.startswith("rem ") and "agents_bat.py" in ln for ln in lines), (
        "the generator marker"
    )
    # rem lines carry no cmd metacharacter
    assert all(not re.search(r"[&|<>^()%]", ln) for ln in lines if ln.startswith("rem ")), text
    # %...% appears only as this .bat's own variables
    assert set(re.findall(r"%[^%\s]*%", text)) <= {"%LOCALAPPDATA%", "%FRAG%"}, text
    # a digit before > is a handle redirect that would eat the 9 in "size": 9
    assert not re.search(r"[0-9]\s*>", text), text
    # the folder is created silently and only when missing
    assert 'if not exist "%FRAG%\\" mkdir "%FRAG%"' in lines, text
    # one redirect-first block writes the temp file; no echo inside it holds a ")"
    start = lines.index('> "%FRAG%\\fabrik-lib.json.tmp" (')
    end = lines.index(")", start)
    assert all(")" not in ln for ln in lines[start + 1 : end]), lines[start:end]
    assert 'move /y "%FRAG%\\fabrik-lib.json.tmp" "%FRAG%\\fabrik-lib.json" >nul' in lines, text
    # the launch: explicit, space-free arguments after wsl.exe, the literal /opt path
    launch = [ln for ln in lines if ln.startswith('start "" wt.exe ')]
    assert len(launch) == 1, text
    tail = launch[0].split(" wsl.exe ", 1)[1].split(" ")
    assert tail == [
        "--distribution",
        "Ubuntu-24.04",
        "--exec",
        "bash",
        "-l",
        "/opt/fabrik/scripts/sysadmin/agents_up.sh",
        "/opt/fabrik-lib",
    ], launch[0]
    assert ' -M -w new new-tab -p "Fabrik-lib Agents grid"' in launch[0], launch[0]
    assert ";" not in launch[0], "wt.exe splits its commands on ;"


def test_the_fragment_is_valid_json(tmp_path: Path) -> None:
    """The echo block, as cmd writes it (each `echo X` line becomes `X`), parses to one complete visible profile."""
    opt = _opt(tmp_path, "fabrik-lib")
    desk = tmp_path / "desk"
    desk.mkdir()
    assert _run("--opt", str(opt), "--desktop", str(desk)).returncode == 0
    lines = _bat(desk, "Fabrik-lib Agents.bat").split("\r\n")
    start = lines.index('> "%FRAG%\\fabrik-lib.json.tmp" (')
    end = lines.index(")", start)
    body = "\n".join(ln.strip().removeprefix("echo ") for ln in lines[start + 1 : end])
    profile = json.loads(body)["profiles"][0]
    # its own name: the operator's hand-made "Fabrik-lib Agents" profile may still be in settings.json
    assert profile["name"] == "Fabrik-lib Agents grid"
    assert profile["tabTitle"] == "Fabrik-lib Agents"
    assert profile["font"] == {"size": 9}
    assert profile.get("hidden", False) is False
    assert profile["commandline"] == (
        "wsl.exe --distribution Ubuntu-24.04 --exec bash -l /opt/fabrik/scripts/sysadmin/agents_up.sh /opt/fabrik-lib"
    )


def test_existing_files(tmp_path: Path) -> None:
    """A file the generator wrote is rewritten; an identical one is left as it is; a foreign one is refused (exit 2,
    untouched, the other targets still written) unless that one file is named by --replace."""
    opt = _opt(tmp_path, "fabrik-lib", "other")
    desk = tmp_path / "desk"
    desk.mkdir()
    foreign = desk / "Fabrik-lib Agents.bat"
    foreign.write_bytes(b'@echo off\r\nstart "" wt.exe -M -p "Fabrik-lib Agents"\r\n')
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 2 and "Fabrik-lib Agents.bat" in out.stderr, out.stderr
    assert foreign.read_bytes().startswith(b"@echo off\r\nstart"), "a foreign file is never touched"
    assert (desk / "Other Agents.bat").exists(), "the other targets are still written"
    # --replace names a different file: still refused
    out = _run("--opt", str(opt), "--desktop", str(desk), "--replace", "Other Agents.bat")
    assert out.returncode == 2 and foreign.read_bytes().startswith(b"@echo off\r\nstart"), (
        out.stderr
    )
    out = _run("--opt", str(opt), "--desktop", str(desk), "--replace", "Fabrik-lib Agents.bat")
    assert out.returncode == 0, out.stderr
    assert "agents_bat.py" in foreign.read_text(encoding="ascii")
    # identical: left alone (mtime unchanged); marked but different: rewritten
    stamp = foreign.stat().st_mtime_ns
    assert _run("--opt", str(opt), "--desktop", str(desk)).returncode == 0
    assert foreign.stat().st_mtime_ns == stamp
    assert _run("--opt", str(opt), "--desktop", str(desk), distro="Ubuntu-22.04").returncode == 0
    assert "--distribution Ubuntu-22.04 " in foreign.read_text(encoding="ascii")


def test_unsafe_names_are_refused(tmp_path: Path) -> None:
    """A repo or distro name reaches cmd, JSON and bash text: anything outside [A-Za-z0-9][A-Za-z0-9._-]* is refused,
    as is no distro at all and two repos the case-blind desktop cannot tell apart."""
    desk = tmp_path / "desk"
    desk.mkdir()
    opt = _opt(tmp_path, "fabrik-lib")
    for bad in ("-x", "Ubuntu 24", "a&b"):
        out = _run("--opt", str(opt), "--desktop", str(desk), distro=bad)
        assert out.returncode == 2 and not any(desk.iterdir()), (bad, out.stderr)
    out = _run("--opt", str(opt), "--desktop", str(desk), "--distro", "")
    assert out.returncode == 2 and not any(desk.iterdir()), out.stderr
    weird = _opt(tmp_path / "w", "ok-repo", "bad&repo")
    out = _run("--opt", str(weird), "--desktop", str(desk))
    assert out.returncode == 2 and "bad&repo" in out.stderr, out.stderr
    assert [p.name for p in desk.iterdir()] == ["Ok-repo Agents.bat"], (
        "the safe repo is still written"
    )
    clash = _opt(tmp_path / "c", "foo", "Foo")
    desk2 = tmp_path / "desk2"
    desk2.mkdir()
    out = _run("--opt", str(clash), "--desktop", str(desk2))
    assert out.returncode == 2 and not any(desk2.iterdir()), out.stderr


def test_a_target_that_cannot_be_written_is_refused_and_the_rest_written(tmp_path: Path) -> None:
    """A folder (or a locked file) at a target is reported with exit 2, never a traceback, and the other repos are
    still written; a temp file never stays behind."""
    opt = _opt(tmp_path, "aaa", "zzz")
    desk = tmp_path / "desk"
    (desk / "Aaa Agents.bat").mkdir(parents=True)
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 2 and "Traceback" not in out.stderr, out.stderr
    assert "Aaa Agents.bat" in out.stderr, out.stderr
    assert (desk / "Zzz Agents.bat").is_file()
    assert not list(desk.glob("*.tmp"))


def test_replace_is_per_file_case_blind_and_must_match(tmp_path: Path) -> None:
    """--replace matches the desktop's case-blind names; one that names no target is an error, so a typo never
    reads as success; the marker counts only as the second line, so a hand-made file quoting it is still foreign."""
    opt = _opt(tmp_path, "fabrik-lib")
    desk = tmp_path / "desk"
    desk.mkdir()
    foreign = desk / "Fabrik-lib Agents.bat"
    quoted = "@echo off\r\nrem copied from rem generated by /opt/fabrik/scripts/sysadmin/agents_bat.py\r\n"
    foreign.write_bytes(quoted.encode("ascii"))
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 2 and b"copied from" in foreign.read_bytes(), out.stderr
    out = _run("--opt", str(opt), "--desktop", str(desk), "--replace", "fabrik-lib agents.bat")
    assert out.returncode == 0 and b"copied from" not in foreign.read_bytes(), out.stderr
    out = _run("--opt", str(opt), "--desktop", str(desk), "--replace", "Typo Agents.bat")
    assert out.returncode == 2 and "typo agents.bat" in out.stderr.lower(), out.stderr


def test_windows_device_names_and_trailing_dots_are_refused(tmp_path: Path) -> None:
    """`con.json.tmp` is the console on Windows and `foo.` loses its dot, so neither may name a repo or a distro."""
    desk = tmp_path / "desk"
    desk.mkdir()
    opt = _opt(tmp_path, "con", "nul.x", "foo.", "fine")
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 2, out.stderr
    assert sorted(p.name for p in desk.iterdir()) == ["Fine Agents.bat"], out.stderr
    for bad in ("COM1", "Ubuntu."):
        out = _run("--opt", str(opt), "--desktop", str(desk), distro=bad)
        assert out.returncode == 2 and "distro" in out.stderr, (bad, out.stderr)


def test_a_failed_rename_leaves_no_temp_file(tmp_path: Path, monkeypatch) -> None:
    """A target Windows holds open (OneDrive, an antivirus scan) fails the rename: the error reaches main's refusal
    and no stray `.tmp` stays on the desktop. Linux cannot lock a file that way, so the rename is made to fail here."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location("agents_bat", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def locked(src: object, dst: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", locked)
    desk = tmp_path / "desk"
    desk.mkdir()
    target = desk / "Fabrik-lib Agents.bat"
    try:
        mod._write(target, mod.bat_text("fabrik-lib", "Ubuntu-24.04"), replace=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("the rename error must reach the caller")
    assert list(desk.iterdir()) == [], list(desk.iterdir())


def test_bats_follow_agents_up(tmp_path: Path) -> None:
    """W-89474fc1: a .bat is written exactly for the repos agents_up.sh accepts (exit 0 and a pane) — a registry repo,
    or one whose grid comes from its whoami bindings — and a repo with neither a registry nor a worktree folder is
    never asked. A generated .bat whose repo no longer qualifies is reported, never deleted."""
    opt = _opt(tmp_path, "reg", bare=("bound", "nogrid", "plain"))
    for name in ("bound", "nogrid"):
        (opt / name / ".claude" / "worktrees").mkdir(parents=True)
    (opt / "bound" / ".grid").write_text("", encoding="utf-8")
    (opt / "plain" / ".grid").write_text(
        "", encoding="utf-8"
    )  # a grid file alone: never asked, no worktree folder
    desk = tmp_path / "desk"
    desk.mkdir()
    stale = desk / "Gone Agents.bat"
    stale.write_bytes(
        b"@echo off\r\nrem generated by /opt/fabrik/scripts/sysadmin/agents_bat.py\r\n"
    )
    out = _run("--opt", str(opt), "--desktop", str(desk))
    assert out.returncode == 0, out.stderr
    assert sorted(p.name for p in desk.iterdir()) == [
        "Bound Agents.bat",
        "Gone Agents.bat",
        "Reg Agents.bat",
    ]
    assert (
        f"{stale} was generated for a repo whose grid agents_up no longer accepts" in out.stderr
    ), out.stderr
    # end to end with the REAL launcher: a repo with no registry whose two builders are bound in their worktrees
    real = ROOT / "scripts" / "sysadmin" / "agents_up.sh"
    shop = opt / "shop"
    shop.mkdir()
    subprocess.run(["git", "init", "-q", str(shop)], check=True, capture_output=True)
    rows = []
    for i, name in enumerate(("s1", "s2")):
        wt = shop / ".claude" / "worktrees" / name
        wt.mkdir(parents=True)
        (wt / ".git").write_text(f"gitdir: {shop}/.git/worktrees/{name}\n", encoding="utf-8")
        sid = f"{i + 7}" * 8 + "-1111-4111-8111-" + "1" * 12
        rows.append(
            {
                "session_id": sid,
                "name": name,
                "toplevel": str(shop.resolve() / ".git"),
                "at": 2_000_000_000,
            }
        )
    store = tmp_path / "store.jsonl"
    store.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = _run("--opt", str(opt), up=str(real), AGENT_IDENTITY_FILE=str(store))
    assert out.returncode == 0, out.stderr
    assert re.findall(r"^== (.+)$", out.stdout, re.M) == ["Shop Agents.bat"], out.stdout


def test_a_missing_opt_folder_is_refused(tmp_path: Path) -> None:
    """An --opt that is not a folder says so and exits 2 — never a traceback."""
    out = _run("--opt", str(tmp_path / "nowhere"))
    assert (
        out.returncode == 2 and "is not a folder" in out.stderr and "Traceback" not in out.stderr
    ), out.stderr


# --- --tabbed (W-b9ad80ae T05, D5): one generated "All Agents (tabbed).bat" -------------------------------------
TABBED = "All Agents (tabbed).bat"
AGENTS_UP = "/opt/fabrik/scripts/sysadmin/agents_up.sh"
MARK_LINE = "rem generated by /opt/fabrik/scripts/sysadmin/agents_bat.py"


def _fake_tmux(tmp: Path, **sessions: str) -> dict[str, str]:
    """A fake `tmux list-windows -t =<S> -F ...` on PATH: a session with a data file answers its lines, any other
    session fails (rc 1) like a session that is down. The real tmux server is never reached."""
    folder = tmp / "fakebin"
    data = tmp / "fake-tmux-data"
    folder.mkdir(exist_ok=True)
    data.mkdir(exist_ok=True)
    exe = folder / "tmux"
    exe.write_text(
        # the exact-match `=` is required (tmux reads a bare name as a prefix/glob); HANG makes a read never return
        '#!/bin/sh\n[ "$1" = list-windows ] || exit 9\ncase "$3" in =*) ;; *) exit 3;; esac\n'
        '[ -f "$FAKE_TMUX_DIR/HANG" ] && exec sleep 5\n'
        'f="$FAKE_TMUX_DIR/${3#=}"\n[ -f "$f" ] || exit 1\ncat "$f"\n',
        encoding="utf-8",
    )
    exe.chmod(0o755)
    assert os.access(exe, os.X_OK), "the fake tmux must be executable"
    for name, windows in sessions.items():
        (data / name).write_text(windows, encoding="utf-8")
    return {"PATH": f"{folder}:/usr/bin:/bin", "FAKE_TMUX_DIR": str(data)}


def _tabbed_tabs(text: str) -> list[str]:
    lines = [ln for ln in text.split("\r\n") if ln.startswith('start "" wt.exe ')]
    assert len(lines) == 1, text
    assert lines[0].startswith('start "" wt.exe -M -w fabrik-agents new-tab '), lines[0]
    return lines[0].split(" ; ")


def test_tabbed_one_tab_per_window(tmp_path: Path) -> None:
    """Two repos, one with windows agents / agents-2 / scratch: three tabs in ONE named wt line, none for scratch."""
    opt = _opt(tmp_path, "aaa", "bbb")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, aaa="agents\nagents-2\nscratch\n", bbb="agents\n")
    out = _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm)
    assert out.returncode == 0, out.stderr
    assert [p.name for p in desk.iterdir()] == [TABBED], list(desk.iterdir())
    text = _bat(desk, TABBED)
    lines = text.split("\r\n")
    assert lines[0] == "@echo off" and lines[1] == MARK_LINE
    tabs = _tabbed_tabs(text)
    tail = "wsl.exe --distribution Ubuntu-24.04 --exec bash -l " + AGENTS_UP
    assert len(tabs) == 3, tabs
    assert tabs[0].endswith(f"{tail} /opt/aaa") and '--title "Aaa Agents"' in tabs[0], tabs[0]
    assert tabs[1].startswith("new-tab ") and tabs[1].endswith(f"{tail} --window 2 /opt/aaa"), tabs[
        1
    ]
    assert '--title "Aaa Agents 2"' in tabs[1], tabs[1]
    assert tabs[2].endswith(f"{tail} /opt/bbb"), tabs[2]
    assert "scratch" not in text
    # each repo's fragment block is present once, shared with the per-repo .bat
    assert text.count('> "%FRAG%\\aaa.json.tmp" (') == 1 and text.count("move /y") == 2, text


@pytest.mark.parametrize(
    "listing",
    [
        None,  # session down: list-windows fails
        "",  # prints nothing
        "agents\n",
        "agents\nagents-1\nagents-02\nagents-x\nagents-2b\nxagents-3\nscratch\n",  # none matches the rule
    ],
)
def test_tabbed_a_repo_without_overflow_windows_gets_one_tab(
    tmp_path: Path, listing: str | None
) -> None:
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, **({} if listing is None else {"aaa": listing}))
    out = _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm)
    assert out.returncode == 0, out.stderr
    assert len(_tabbed_tabs(_bat(desk, TABBED))) == 1


def test_tabbed_window_names_two_digits_and_order(tmp_path: Path) -> None:
    """agents-2 .. agents-9 and agents-10+ qualify; duplicates collapse; tabs go in numeric order."""
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, aaa="agents-10\nagents-3\nagents-9\nagents-3\nagents-12\n")
    assert _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm).returncode == 0
    tabs = _tabbed_tabs(_bat(desk, TABBED))
    nums = [re.search(r"--window (\d+) ", t).group(1) for t in tabs[1:]]
    assert nums == ["3", "9", "10", "12"], tabs


def _load_mod():
    import importlib.util

    spec = importlib.util.spec_from_file_location("agents_bat", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env(monkeypatch, tm: dict[str, str], **more: str) -> None:
    for k, v in {**tm, "HOME": _FAKE["home"], "AGENTS_UP_BIN": _FAKE["bin"], **more}.items():
        monkeypatch.setenv(k, v)


def test_tabbed_distro_is_the_decks_resolver_called_once(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """WSL_DISTRO_NAME unset: the distro `wslpath -w /` names is used in every wsl.exe, the note prints once, and
    --distro overrides (its empty value refuses)."""
    mod = _load_mod()
    deck = mod._load_deck()
    fake = tmp_path / "wslpath"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' '\\\\wsl.localhost\\Derived-1\\'\n", encoding="utf-8"
    )
    fake.chmod(0o755)
    assert os.access(fake, os.X_OK)
    monkeypatch.setattr(deck, "WSLPATH", str(fake))
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    opt = _opt(tmp_path, "aaa", "bbb")
    desk = tmp_path / "desk"
    desk.mkdir()
    _env(monkeypatch, _fake_tmux(tmp_path))
    assert mod.main(["--opt", str(opt), "--desktop", str(desk), "--tabbed"]) == 0
    err = capsys.readouterr().err
    assert err.count("derived as Derived-1") == 1, err
    text = _bat(desk, TABBED)
    assert text.count("--distribution Derived-1 ") >= 2 and "Ubuntu" not in text, text
    # --distro wins over the derivation; '' refuses
    assert (
        mod.main(["--opt", str(opt), "--desktop", str(desk), "--tabbed", "--distro", "Other-2"])
        == 0
    )
    assert "--distribution Other-2 " in _bat(desk, TABBED)
    assert mod.main(["--opt", str(opt), "--desktop", str(desk), "--tabbed", "--distro", ""]) == 2


def test_tabbed_foreign_file_is_refused_unless_replaced(tmp_path: Path) -> None:
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path)
    mine = desk / TABBED
    mine.write_bytes(b'@echo off\r\nstart "" wt.exe -M -w new new-tab\r\n')
    out = _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm)
    assert out.returncode == 2 and mine.read_bytes().startswith(b"@echo off\r\nstart"), out.stderr
    out = _run(
        "--opt", str(opt), "--desktop", str(desk), "--tabbed", "--replace", TABBED.lower(), **tm
    )
    assert out.returncode == 0, out.stderr
    assert _bat(desk, TABBED).split("\r\n")[1] == MARK_LINE
    # now carries the marker: a plain rerun is fine without --replace
    assert _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm).returncode == 0


def test_tabbed_remembers_the_desktop(tmp_path: Path) -> None:
    opt = _opt(tmp_path, "aaa")
    (tmp_path / "cwd1" / "D").mkdir(parents=True)
    (tmp_path / "cwd2").mkdir()
    tm = _fake_tmux(tmp_path)
    # nothing remembered: print mode, one-line note, exit 0
    out = _run("--opt", str(opt), "--tabbed", cwd=tmp_path / "cwd2", **tm)
    assert out.returncode == 0 and "no desktop remembered" in out.stderr, out.stderr
    assert f"== {TABBED}" in out.stdout
    # a relative --desktop is stored absolute; another cwd then writes there
    out = _run("--opt", str(opt), "--tabbed", "--desktop", "D", cwd=tmp_path / "cwd1", **tm)
    assert out.returncode == 0, out.stderr
    (tmp_path / "cwd1" / "D" / TABBED).unlink()
    out = _run("--opt", str(opt), "--tabbed", cwd=tmp_path / "cwd2", **tm)
    assert out.returncode == 0, out.stderr
    assert (tmp_path / "cwd1" / "D" / TABBED).is_file()
    assert not (tmp_path / "cwd2" / "D").exists()
    # the remembered folder is deleted since: print mode + note, exit 0
    (tmp_path / "cwd1" / "D" / TABBED).unlink()
    (tmp_path / "cwd1" / "D").rmdir()
    out = _run("--opt", str(opt), "--tabbed", cwd=tmp_path / "cwd2", **tm)
    assert out.returncode == 0 and "is not a folder" in out.stderr, out.stderr
    assert f"== {TABBED}" in out.stdout


def test_tabbed_concurrent_runs_leave_one_whole_file(tmp_path: Path) -> None:
    opt = _opt(tmp_path, "aaa", "bbb")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, aaa="agents\nagents-2\n")
    env = {
        **tm,
        "HOME": _FAKE["home"],
        "AGENTS_UP_BIN": _FAKE["bin"],
        "WSL_DISTRO_NAME": "Ubuntu-24.04",
    }
    cmd = [sys.executable, str(GEN), "--opt", str(opt), "--desktop", str(desk), "--tabbed"]
    procs = [
        subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [(*p.communicate(timeout=60), p.returncode) for p in procs]
    assert [r[2] for r in results] == [0, 0], results
    assert [p.name for p in desk.iterdir()] == [TABBED], list(desk.iterdir())
    assert len(_tabbed_tabs(_bat(desk, TABBED))) == 3


def test_tabbed_lock_wait_is_bounded(tmp_path: Path, monkeypatch, capsys) -> None:
    import fcntl

    mod = _load_mod()
    monkeypatch.setattr(mod, "LOCK_WAIT", 0.3)
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    _env(monkeypatch, _fake_tmux(tmp_path), WSL_DISTRO_NAME="U1")
    lockdir = Path(_FAKE["home"]) / ".config" / "fabrik"
    lockdir.mkdir(parents=True)
    fd = os.open(lockdir / "agents-desktop.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert mod.main(["--opt", str(opt), "--desktop", str(desk), "--tabbed"]) == 2
        assert "lock" in capsys.readouterr().err
        assert list(desk.iterdir()) == []
    finally:
        os.close(fd)
    assert mod.main(["--opt", str(opt), "--desktop", str(desk), "--tabbed"]) == 0


def test_tabbed_the_lock_is_not_held_while_agents_up_runs(tmp_path: Path) -> None:
    """The slow `agents_up.sh --print` runs outside the lock: the stand-in takes `flock -n` on the lock file while it
    runs and records whether it got it (0 = yes)."""
    opt = _opt(tmp_path, "aaa", "bbb")
    desk = tmp_path / "desk"
    desk.mkdir()
    lockdir = Path(_FAKE["home"]) / ".config" / "fabrik"
    lockdir.mkdir(parents=True)
    lock = lockdir / "agents-desktop.lock"
    lock.write_text("", encoding="utf-8")
    rec = tmp_path / "rec"
    up = tmp_path / "slow_up.sh"
    up.write_text(
        FAKE_UP.replace(
            'echo "session x"',
            f'flock -n "{lock}" true; echo "$?" >> "{rec}"; sleep 0.2\necho "session x"',
        ),
        encoding="utf-8",
    )
    out = _run(
        "--opt", str(opt), "--desktop", str(desk), "--tabbed", up=str(up), **_fake_tmux(tmp_path)
    )
    assert out.returncode == 0, out.stderr
    assert rec.read_text().split() == ["0", "0"], rec.read_text()


def test_write_failure_leaves_no_temp_in_tabbed_mode_either(tmp_path: Path, monkeypatch) -> None:
    mod = _load_mod()

    def locked(src: object, dst: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", locked)
    desk = tmp_path / "desk"
    desk.mkdir()
    with pytest.raises(PermissionError):
        mod._write(
            desk / TABBED, mod.tabbed_text(["aaa"], {"aaa": [2]}, "Ubuntu-24.04"), replace=False
        )
    assert list(desk.iterdir()) == []


def _fake_wslpath(tmp: Path, text: str, rc: int = 0) -> str:
    fake = tmp / "wslpath"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' '{text}'\nexit {rc}\n", encoding="utf-8")
    fake.chmod(0o755)
    assert os.access(fake, os.X_OK)
    return str(fake)


def test_per_repo_mode_defaults_the_distro_to_the_resolver(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """F1: both modes default to the Deck's resolver, called once; --distro '' still refuses; a resolver that finds
    nothing refuses; the text is byte-identical to an explicit --distro of the same name."""
    mod = _load_mod()
    deck = mod._load_deck()
    monkeypatch.setattr(deck, "WSLPATH", _fake_wslpath(tmp_path, "\\\\wsl.localhost\\Derived-1\\"))
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    _env(monkeypatch, _fake_tmux(tmp_path))
    opt = _opt(tmp_path, "aaa", "bbb")
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    assert mod.main(["--opt", str(opt), "--desktop", str(d1)]) == 0
    assert capsys.readouterr().err.count("derived as Derived-1") == 1
    assert mod.main(["--opt", str(opt), "--desktop", str(d2), "--distro", "Derived-1"]) == 0
    for name in ("Aaa Agents.bat", "Bbb Agents.bat"):
        assert (d1 / name).read_bytes() == (d2 / name).read_bytes()
        assert b"--distribution Derived-1 " in (d1 / name).read_bytes()
    assert mod.main(["--opt", str(opt), "--desktop", str(d1), "--distro", ""]) == 2
    monkeypatch.setattr(deck, "WSLPATH", _fake_wslpath(tmp_path, "garbage", rc=1))
    assert mod.main(["--opt", str(opt)]) == 2


def test_a_refused_run_keeps_the_remembered_desktop(tmp_path: Path) -> None:
    """F2: the desktop is remembered only after a run wrote its file(s): a --desktop run that exits 2 leaves the
    earlier one in place, in both modes."""
    opt = _opt(tmp_path, "aaa")
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    tm = _fake_tmux(tmp_path)
    assert _run("--opt", str(opt), "--tabbed", "--desktop", str(d1), **tm).returncode == 0
    (d2 / TABBED).write_bytes(b"@echo off\r\nrem foreign\r\n")
    (d2 / "Aaa Agents.bat").write_bytes(b"@echo off\r\nrem foreign\r\n")
    for mode in (["--tabbed"], []):
        out = _run("--opt", str(opt), *mode, "--desktop", str(d2), **tm)
        assert out.returncode == 2, out.stderr
        (d1 / TABBED).unlink()
        assert _run("--opt", str(opt), "--tabbed", **tm).returncode == 0
        assert (d1 / TABBED).is_file(), mode
        assert (d2 / TABBED).read_bytes().startswith(b"@echo off\r\nrem foreign")
    # a successful run elsewhere does move it
    assert (
        _run(
            "--opt", str(opt), "--tabbed", "--desktop", str(d2), "--replace", TABBED, **tm
        ).returncode
        == 0
    )
    (d2 / TABBED).unlink()
    assert _run("--opt", str(opt), "--tabbed", **tm).returncode == 0
    assert (d2 / TABBED).is_file()


def test_a_run_that_wrote_nothing_keeps_the_remembered_desktop(tmp_path: Path) -> None:
    """N1: zero qualifying repos (a mistyped --opt) exits 0 but wrote nothing: D2 is not remembered, in either mode;
    a run that finds its file already current still counts."""
    opt = _opt(tmp_path, "aaa")
    empty = tmp_path / "empty-opt"
    empty.mkdir()
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    tm = _fake_tmux(tmp_path)
    assert _run("--opt", str(opt), "--tabbed", "--desktop", str(d1), **tm).returncode == 0
    for mode in (["--tabbed"], []):
        assert _run("--opt", str(empty), *mode, "--desktop", str(d2), **tm).returncode == 0
        (d1 / TABBED).unlink()
        assert _run("--opt", str(opt), "--tabbed", **tm).returncode == 0
        assert (d1 / TABBED).is_file() and not list(d2.iterdir()), mode
    # already current counts as confirmed
    assert _run("--opt", str(opt), "--tabbed", "--desktop", str(d2), **tm).returncode == 0
    assert _run("--opt", str(opt), "--tabbed", "--desktop", str(d2), **tm).returncode == 0
    (d2 / TABBED).unlink()
    assert _run("--opt", str(opt), "--tabbed", **tm).returncode == 0
    assert (d2 / TABBED).is_file()


@pytest.mark.parametrize("cause", ["unsafe-repo", "unmatched-replace"])
def test_t10_f13_a_partial_run_that_wrote_its_file_remembers_the_desktop(
    tmp_path: Path, cause: str
) -> None:
    """T10 F13: a --desktop run that wrote a file but exits 2 for another reason (an unsafe repo name skipped, a
    --replace naming no target) still remembers the desktop, so later add/remove regenerations have a target."""
    opt = _opt(tmp_path, "good", *(["bad name"] if cause == "unsafe-repo" else []))
    desk = tmp_path / "desk"
    desk.mkdir()
    extra = ["--replace", "Nothing Here.bat"] if cause == "unmatched-replace" else []
    out = _run("--opt", str(opt), "--desktop", str(desk), *extra)
    assert out.returncode == 2, out.stderr
    assert (desk / "Good Agents.bat").is_file(), list(desk.iterdir())
    if (
        cause == "unsafe-repo"
    ):  # the follow-up run is a clean one: only the remembered desktop is under test
        (opt / "bad name" / ".fabrik" / "session-agents.json").unlink()
        (opt / "bad name" / ".fabrik").rmdir()
        (opt / "bad name").rmdir()
    tm = _fake_tmux(tmp_path)
    assert _run("--opt", str(opt), "--tabbed", **tm).returncode == 0
    assert (desk / TABBED).is_file(), list(desk.iterdir())


def test_confirmed_files_do_not_leak_between_main_calls(tmp_path: Path, monkeypatch) -> None:
    """P2: `main` resets what the run confirmed, so a second in-process call that finds no repo does not inherit the
    first call's confirmation and move the remembered desktop."""
    mod = _load_mod()
    opt = _opt(tmp_path, "aaa")
    empty = tmp_path / "empty-opt"
    empty.mkdir()
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    _env(monkeypatch, _fake_tmux(tmp_path), WSL_DISTRO_NAME="U1")
    assert mod.main(["--opt", str(opt), "--tabbed", "--desktop", str(d1)]) == 0
    assert mod.main(["--opt", str(empty), "--tabbed", "--desktop", str(d2)]) == 0
    assert list(d2.iterdir()) == []
    (d1 / TABBED).unlink()
    assert mod.main(["--opt", str(opt), "--tabbed"]) == 0
    assert (d1 / TABBED).is_file() and list(d2.iterdir()) == []


def test_tabbed_session_follows_a_symlinked_repo(tmp_path: Path) -> None:
    """F3: agents_up.sh names the session from `pwd -P`: /opt/foo -> /data/bar is session `bar`."""
    real = _opt(tmp_path / "data", "bar") / "bar"
    opt = tmp_path / "opt"
    opt.mkdir()
    (opt / "foo").symlink_to(real)
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, bar="agents\nagents-2\n")
    out = _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm)
    assert out.returncode == 0, out.stderr
    tabs = _tabbed_tabs(_bat(desk, TABBED))
    assert len(tabs) == 2 and tabs[1].endswith("--window 2 /opt/foo"), tabs


def test_tabbed_window_names_are_not_trimmed(tmp_path: Path) -> None:
    """F4: only the line end (\\n, \\r\\n) goes; a name with surrounding spaces is not `agents-<n>`."""
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, aaa=" agents-2 \nagents-4 \n agents-5\nagents-3\r\nagents-6\x0b\n")
    assert _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm).returncode == 0
    tabs = _tabbed_tabs(_bat(desk, TABBED))
    assert [re.search(r"--window (\d+) ", t).group(1) for t in tabs[1:]] == ["3"], tabs


def test_tabbed_session_name_is_sanitised_and_exact(tmp_path: Path) -> None:
    """F5: `my.repo` is session `my-repo` (agents_up.sh keeps [A-Za-z0-9_-]); the fake tmux refuses a target
    without the exact-match `=`."""
    opt = _opt(tmp_path, "my.repo")
    desk = tmp_path / "desk"
    desk.mkdir()
    tm = _fake_tmux(tmp_path, **{"my-repo": "agents\nagents-2\n"})
    assert _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", **tm).returncode == 0
    tabs = _tabbed_tabs(_bat(desk, TABBED))
    assert len(tabs) == 2 and tabs[1].endswith("--window 2 /opt/my.repo"), tabs


def test_tabbed_a_hung_tmux_read_is_bounded(tmp_path: Path, monkeypatch) -> None:
    """F6: each read under the lock is capped at <= 2 s; a timed-out read gives the repo its first tab only."""
    mod = _load_mod()
    assert mod.TMUX_TIMEOUT <= 2
    monkeypatch.setattr(mod, "TMUX_TIMEOUT", 0.3)
    tm = _fake_tmux(tmp_path, aaa="agents\nagents-2\n")
    (Path(tm["FAKE_TMUX_DIR"]) / "HANG").write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", tm["PATH"])
    monkeypatch.setenv("FAKE_TMUX_DIR", tm["FAKE_TMUX_DIR"])
    assert mod._windows(str(tmp_path), "aaa") == []


def test_tabbed_an_unusable_config_dir_names_itself(tmp_path: Path) -> None:
    """F7: the lock/config path that failed is named, not the desktop target; still exit 2."""
    opt = _opt(tmp_path, "aaa")
    desk = tmp_path / "desk"
    desk.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    (home / ".config").write_text("a file where the config folder should be", encoding="utf-8")
    tm = _fake_tmux(tmp_path)
    out = _run("--opt", str(opt), "--desktop", str(desk), "--tabbed", HOME=str(home), **tm)
    assert out.returncode == 2 and "Traceback" not in out.stderr, out.stderr
    assert ".config/fabrik" in out.stderr and "left as it is" not in out.stderr, out.stderr
    assert list(desk.iterdir()) == []


def test_write_uses_a_unique_temp_name(tmp_path: Path) -> None:
    """Never the fixed `<name>.tmp`: a stale one of that name must survive untouched."""
    mod = _load_mod()
    desk = tmp_path / "desk"
    desk.mkdir()
    stale = desk / "Aaa Agents.bat.tmp"
    stale.write_bytes(b"someone else's")
    assert mod._write(desk / "Aaa Agents.bat", mod.bat_text("aaa", "U1"), replace=False) == 0
    assert stale.read_bytes() == b"someone else's"
    assert sorted(p.name for p in desk.iterdir()) == ["Aaa Agents.bat", "Aaa Agents.bat.tmp"]


# --- --list (W-6e656dac T04, Interface G): the boot sweep's repo list --------------------------------------------
def test_list_prints_every_registered_repo_without_the_probe(tmp_path: Path) -> None:
    """`--list` prints the absolute path of every repo with a registry or a .claude/worktrees folder, one per line,
    sorted — WITHOUT asking agents_up.sh (a bus that does not answer yet at boot must never empty it), with no distro
    to resolve, and writing nothing. The repos are created out of name order (T04 F8), so a list that is not sorted
    cannot pass by the filesystem's creation order."""
    opt = _opt(tmp_path, "zulu", "reg", bare=("plain", "mike", "bound"))
    (opt / "mike" / ".claude" / "worktrees").mkdir(parents=True)
    (opt / "bound" / ".claude" / "worktrees").mkdir(parents=True)
    probe = tmp_path / "probe-ran"
    up = tmp_path / "refusing_up.sh"
    up.write_text(f'#!/bin/sh\ntouch "{probe}"\nexit 2\n', encoding="utf-8")
    before = sorted(p for p in tmp_path.rglob("*"))
    rel = os.path.relpath(opt, tmp_path)
    out = _run("--list", "--opt", rel, distro=None, up=str(up), cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        str(opt / "bound"),
        str(opt / "mike"),
        str(opt / "reg"),
        str(opt / "zulu"),
    ], out.stdout
    assert all(os.path.isabs(ln) for ln in out.stdout.splitlines())
    assert not probe.exists(), "--list ran the agents_up.sh --print probe"
    assert sorted(p for p in tmp_path.rglob("*")) == before


def test_list_takes_no_write_mode(tmp_path: Path) -> None:
    """`--list` is its own mode: with --desktop, --tabbed or --replace it is refused (exit 2) by its own guard, never
    half of both. The guard's text is asserted (T04 F1): argparse's "unrecognized arguments: --list" would also put
    `--list` in stderr with exit 2."""
    opt = _opt(tmp_path, "reg")
    desk = tmp_path / "desk"
    desk.mkdir()
    for extra in (("--desktop", str(desk)), ("--tabbed",), ("--replace", "x")):
        out = _run("--list", "--opt", str(opt), *extra)
        assert out.returncode == 2, (extra, out.stderr)
        assert "is its own mode" in out.stderr and "unrecognized" not in out.stderr, (extra, out.stderr)
        assert "Traceback" not in out.stderr and out.stdout == "", (extra, out.stdout)
        assert list(desk.iterdir()) == []


def test_list_skips_an_unreadable_folder_and_lists_the_rest(tmp_path: Path) -> None:
    """T04 F6: one child of --opt that cannot be read is skipped with a stderr line naming it; every other registered
    repo is still listed and the exit is 0 (the boot sweep reads an empty list as `builders-none`)."""
    if os.geteuid() == 0:
        pytest.skip("root reads a chmod-000 folder, so the unreadable-folder failure cannot be staged (T04 G5)")
    opt = _opt(tmp_path, "aaa", "zzz", bare=("locked",))
    (opt / "locked" / ".claude" / "worktrees").mkdir(parents=True)
    (opt / "locked").chmod(0o000)
    try:
        out = _run("--list", "--opt", str(opt))
    finally:
        (opt / "locked").chmod(0o755)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [str(opt / "aaa"), str(opt / "zzz")], out.stdout
    assert str(opt / "locked") in out.stderr and "Traceback" not in out.stderr, out.stderr


def test_list_skips_a_folder_name_holding_a_newline(tmp_path: Path) -> None:
    """T04 F3: a repo folder whose name holds a newline would print as two lines, and the sweep would run
    `agents_up.sh --detach` on a truncated path — it is skipped with a stderr line."""
    opt = _opt(tmp_path, "aaa", "x\ny")
    out = _run("--list", "--opt", str(opt))
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [str(opt / "aaa")], out.stdout
    assert "newline" in out.stderr and "Traceback" not in out.stderr, out.stderr


def test_list_names_an_unreadable_newline_folder_on_one_line(tmp_path: Path) -> None:
    """T04 residue 5: the boot sweep notes --list's stderr line by line, so an unreadable folder whose name holds a
    newline must still be ONE `cannot read … skipped` line — every stderr line is an `agents_bat:` line."""
    if os.geteuid() == 0:
        pytest.skip(
            "root reads a chmod-000 folder, so the unreadable-folder failure cannot be staged (T04 G5)"
        )
    opt = _opt(tmp_path, "aaa", bare=("lo\nck",))
    (opt / "lo\nck" / ".claude" / "worktrees").mkdir(parents=True)
    (opt / "lo\nck").chmod(0o000)
    try:
        out = _run("--list", "--opt", str(opt))
    finally:
        (opt / "lo\nck").chmod(0o755)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [str(opt / "aaa")], out.stdout
    lines = out.stderr.splitlines()
    assert lines and all(ln.startswith("agents_bat: ") for ln in lines), lines
    assert any("cannot read" in ln and ln.endswith("; skipped") for ln in lines), lines


def test_list_prints_a_symlinked_repo_once(tmp_path: Path) -> None:
    """T04 residue 5: a symlink under --opt to a registered repo is the SAME repo (agents_up resolves `pwd -P`, so
    both spellings build one grid) — it is listed once, the other spelling skipped with a `; skipped` line."""
    opt = _opt(tmp_path, "real")
    (opt / "alias").symlink_to(opt / "real")
    out = _run("--list", "--opt", str(opt))
    assert out.returncode == 0, out.stderr
    assert len(out.stdout.splitlines()) == 1, out.stdout
    assert "same repo as" in out.stderr and out.stderr.rstrip().endswith("; skipped"), out.stderr


def test_list_of_a_missing_opt_is_refused(tmp_path: Path) -> None:
    out = _run("--list", "--opt", str(tmp_path / "nowhere"))
    assert out.returncode == 2 and "is not a folder" in out.stderr and out.stdout == "", out.stderr
