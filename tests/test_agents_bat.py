"""`agents_bat.py` (W-bb6c9d9a, D-1042): one self-contained "<Repo> Agents.bat" per /opt repo with an agent registry.

Driven by subprocess against a tmp /opt and a tmp desktop — the operator's real desktop is never touched. No Windows
runner exists here, so the .bat TEXT is the subject: every cmd.exe trap the design names is asserted on it, and the
fragment JSON it writes is parsed back out of the echo block.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

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


def _run(*args: str, distro: str | None = "Ubuntu-24.04") -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin"}
    if distro is not None:
        env["WSL_DISTRO_NAME"] = distro
    return subprocess.run(
        [sys.executable, str(GEN), *args], capture_output=True, text=True, timeout=30, env=env
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
    out = _run("--opt", str(opt), "--desktop", str(desk), distro=None)
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
