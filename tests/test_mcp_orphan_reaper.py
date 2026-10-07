"""Graders for scripts/sysadmin/mcp_orphan_reaper.py (operator mail 01M4AR32MY, 2026-10-07).

The reaper runs from a SessionEnd hook and the WSL startup hook, so every decision it makes is
graded on a SYNTHETIC process table — the live /proc is never read here, and nothing is killed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "mcp_orphan_reaper.py"
DEFS = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "mcp_defs.json"


@pytest.fixture(scope="module")
def reaper():
    spec = importlib.util.spec_from_file_location("mcp_orphan_reaper", SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod  # a dataclass resolves its module through sys.modules
    spec.loader.exec_module(mod)
    return mod


CLAUDE = "/home/ozgur/.vscode-server/extensions/anthropic.claude-code-2.1.280-linux-x64/resources/native-binary/claude --output-format stream-json"
ROOT = "/home/ozgur/.vscode-server/bin/1b6a1881/node /home/ozgur/.vscode-server/bin/1b6a1881/out/server-main.js --host=127.0.0.1"
JVM = "java -classpath /home/ozgur/.maestro/lib/* maestro.cli.AppKt mcp"
BRAVE = "node /home/ozgur/.nvm/versions/node/v24.18.0/bin/brave-search-mcp-server --transport stdio"


def table(reaper, rows):
    return [reaper.Proc(pid, ppid, age, args) for pid, ppid, age, args in rows]


def test_every_stdio_server_in_the_catalog_has_exactly_one_signature(reaper):
    sigs = reaper.signatures(DEFS)
    servers = json.loads(DEFS.read_text())["mcpServers"]
    stdio = {k: v for k, v in servers.items() if v.get("type", "stdio") == "stdio"}
    assert stdio, "the catalog lost its stdio servers"
    cmds = [cmd for cmd, _ in sigs]
    for name, entry in stdio.items():
        cmd = str(entry["command"])
        assert cmds.count(cmd) == 1, (name, cmd)
    assert ("maestro.cli.AppKt", None) in sigs, (
        "the JVM the maestro wrapper execs carries the class name, not the wrapper path"
    )
    http = [k for k, v in servers.items() if v.get("type") == "http"]
    for name in http:
        assert servers[name].get("url", "") not in cmds, name
    # a bare launcher name is matched as a whole token PLUS its image: `docker` never means `dockerd`
    docker = [s for s in sigs if s[0] == "docker"]
    assert docker == [("docker", "mcp/grafana")], docker
    assert not reaper.matches(
        "/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock", sigs
    )
    assert reaper.matches(
        "docker run --rm -i -e GRAFANA_URL -e GRAFANA_SERVICE_ACCOUNT_TOKEN mcp/grafana -t stdio",
        sigs,
    )
    assert not reaper.matches(
        "node /home/ozgur/.nvm/versions/node/v24.18.0/bin/brave-search-mcp-server-but-not --transport stdio",
        sigs,
    )


def test_a_reparented_old_mcp_server_is_an_orphan_but_a_live_sessions_child_is_not(reaper):
    procs = table(
        reaper,
        [
            (1, 0, 999999, "/sbin/init"),
            (1075, 1, 400000, ROOT),
            (4737, 1396, 3000, CLAUDE),
            (5051, 4737, 2900, JVM),  # live: parent is the claude binary
            (62001, 1075, 54000, JVM),  # orphan: reparented to the vscode-server root
            (62002, 1, 54000, BRAVE),  # orphan: reparented to init
            (6714, 1, 400000, "/usr/lib/systemd/systemd --user"),
            (62004, 6714, 54000, BRAVE),  # orphan: reparented to the user systemd subreaper
            (7000, 1, 400000, "tmux: server"),
            (62005, 7000, 54000, JVM),  # orphan: reparented to a tmux server
            (7100, 1, 400000, "/usr/bin/tmux-plugin-x --daemon"),
            (
                62006,
                7100,
                54000,
                JVM,
            ),  # NOT an orphan: a near-miss name is not a subreaper (pass-2 finding)
            (62003, 1075, 30, JVM),  # too young — mid-handshake, never touched
            (
                70000,
                1075,
                54000,
                "python3 /opt/fabrik/scripts/sysadmin/mcp_health.py",
            ),  # not a server
        ],
    )
    got = {p.pid for p in reaper.select_orphans(procs, reaper.signatures(DEFS), 120)}
    assert got == {62001, 62002, 62004, 62005}


def test_a_server_whose_parent_is_unknown_but_alive_is_left_alone(reaper):
    """The operator's claude.ai WSL bridge and a health probe parent their own servers: neither
    is a subreaper, so neither child is an orphan — the test is REPARENTING, never 'no claude
    ancestor'."""
    procs = table(
        reaper,
        [
            (1, 0, 999999, "/sbin/init"),
            (8000, 1, 5000, "node /home/ozgur/bridge/wsl-mcp-bridge.js"),
            (8001, 8000, 4900, JVM),
            (9000, 1, 5000, "python3 /opt/fabrik/scripts/sysadmin/mcp_health.py"),
            (9001, 9000, 4900, BRAVE),
        ],
    )
    assert reaper.select_orphans(procs, reaper.signatures(DEFS), 120) == []


def test_dry_run_kills_nothing_and_hook_mode_exits_zero_on_an_empty_table(
    reaper, monkeypatch, capsys
):
    monkeypatch.setattr(reaper, "_read_procs", lambda: [])
    killed: list = []
    monkeypatch.setattr(reaper, "_kill", lambda v, g: killed.append(v) or [])
    assert reaper.main([]) == 0
    assert reaper.main(["--hook"]) == 0
    assert killed == []
    monkeypatch.setattr(
        reaper,
        "_read_procs",
        lambda: table(reaper, [(1, 0, 9, "/sbin/init"), (77, 1, 9999, JVM)]),
    )
    assert reaper.main([]) == 0  # dry run: lists, never kills
    assert killed == []
    assert "DRY RUN" in capsys.readouterr().out


def test_apply_sends_term_then_kill_only_to_survivors(reaper, monkeypatch, tmp_path):
    sent: list[tuple[int, int]] = []
    alive = {77: True}

    def fake_kill(pid, sig):
        sent.append((pid, sig))
        if sig == reaper.signal.SIGKILL:
            alive[pid] = False

    monkeypatch.setattr(reaper.os, "kill", fake_kill)
    monkeypatch.setattr(reaper, "_alive", lambda pid: alive.get(pid, False))
    monkeypatch.setattr(reaper, "LOG", tmp_path / "reaper.log")
    victim = reaper.Proc(77, 1, 9999, JVM)
    rows = reaper._kill([victim], grace_s=0.3)
    assert [s for _, s in sent] == [reaper.signal.SIGTERM, reaper.signal.SIGKILL]
    assert rows == [(victim, "SIGKILL")]
    reaper._log(rows, "test")
    assert "pid=77" in (tmp_path / "reaper.log").read_text()


def test_an_unreadable_uptime_returns_an_empty_table_and_says_so(reaper, tmp_path, capsys):
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "stat").write_text(
        "1 (init) S 0 1 1 0 -1 4194560 0 0 0 0 0 0 0 0 20 0 1 0 5 0 0\n"
    )
    (tmp_path / "1" / "cmdline").write_bytes(b"/sbin/init\0")
    assert reaper._read_procs(tmp_path) == []
    assert "uptime" in capsys.readouterr().err


def test_report_writes_one_resume_line_with_before_after_and_host_count(
    reaper, monkeypatch, tmp_path
):
    """Operator follow-up (a) / D-642: the WSL startup hook's --report line is the measurement behind
    D-634's kill criterion — orphans before and after the reap, and the host-side wsl.exe count."""
    tables = [
        table(
            reaper, [(1, 0, 9, "/sbin/init"), (77, 1, 9999, JVM), (78, 1, 9999, BRAVE)]
        ),  # before
        table(reaper, [(1, 0, 9, "/sbin/init")]),  # after the reap
    ]
    monkeypatch.setattr(reaper, "_read_procs", lambda: tables.pop(0))
    monkeypatch.setattr(reaper, "_kill", lambda v, g: [(p, "SIGTERM") for p in v])
    monkeypatch.setattr(reaper, "_host_wsl_count", lambda: 4)
    monkeypatch.setattr(reaper, "LOG", tmp_path / "reaper.log")
    assert reaper.main(["--hook", "--report"]) == 0
    lines = (tmp_path / "reaper.log").read_text().splitlines()
    resume = [ln for ln in lines if " resume " in ln]
    assert len(resume) == 1, lines
    assert "before=2 after=0 wsl_exe=4 reaped=77,78" in resume[0]


def test_report_without_the_windows_side_says_na_and_zero_orphans_still_reports(
    reaper, monkeypatch, tmp_path
):
    monkeypatch.setattr(reaper, "_read_procs", lambda: [])
    monkeypatch.setattr(reaper, "TASKLIST", tmp_path / "missing-tasklist.exe")
    monkeypatch.setattr(reaper, "LOG", tmp_path / "reaper.log")
    assert reaper.main(["--hook", "--report"]) == 0
    text = (tmp_path / "reaper.log").read_text()
    assert "resume before=0 after=0 wsl_exe=n/a reaped=-" in text


def test_host_wsl_count_parses_tasklist_rows(reaper, monkeypatch, tmp_path):
    fake = tmp_path / "tasklist.exe"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' '' 'wsl.exe   1 Console 1 7,664 K' 'wsl.exe   2 Console 1 8 K' 'other.exe 3 Console 1 1 K'\n"
    )
    fake.chmod(0o755)
    monkeypatch.setattr(reaper, "TASKLIST", fake)
    assert reaper._host_wsl_count() == 2


def test_a_dry_run_report_writes_no_resume_line(reaper, monkeypatch, tmp_path, capsys):
    """B-S1/B-S2 (review 2026-10-07): a resume line comes only from a real reap (--apply/--hook) —
    a bare --report never writes one, with or without orphans, so the log never mixes dry runs
    with real resumes."""
    monkeypatch.setattr(reaper, "LOG", tmp_path / "reaper.log")
    monkeypatch.setattr(reaper, "_read_procs", lambda: [])
    assert reaper.main(["--report"]) == 0
    monkeypatch.setattr(
        reaper, "_read_procs", lambda: table(reaper, [(1, 0, 9, "/sbin/init"), (77, 1, 9999, JVM)])
    )
    assert reaper.main(["--report"]) == 0
    assert not (tmp_path / "reaper.log").exists()
    # the note is printed on BOTH dry-run branches — zero orphans and some (pass-2 finding B-NEW1)
    assert capsys.readouterr().err.count("writes nothing on a dry run") == 2
