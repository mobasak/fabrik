"""box_budget_check.py — the rotation unit's self-heal and the inotify budget alert (W-09957e81).

Every sink is a tmp seam: systemctl is a fake script driven by a JSON file, mail.py is a fake under the
pinned FABRIK_OPT_DIR that records each send, /proc is a built tree, and the canary is stubbed. Nothing
here can reach the operator's live unit or mailbox.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "box_budget_check.py"
spec = importlib.util.spec_from_file_location("box_budget_check", SCRIPT)
bb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bb)

FAKE_SYSTEMCTL = """#!/usr/bin/env python3
import json, os, sys
st = json.load(open(os.environ["FAKE_SYSTEMCTL_STATE"]))
args = [a for a in sys.argv[1:] if a != "--user"]
with open(os.environ["FAKE_SYSTEMCTL_STATE"] + ".calls", "a") as f:
    f.write(" ".join(args) + "\\n")
verb = args[0]
if verb == "is-enabled":
    print(st["enabled"]); sys.exit(0 if st["enabled"] == "enabled" else 1)
if verb == "show":
    unit = args[-1]
    u = st["units"].get(unit, {})
    for k in ("ActiveState", "SubState", "Result"):
        print(f"{k}={u.get(k, '')}")
    sys.exit(0)
if verb == "reset-failed":
    sys.exit(0)
if verb == "start":
    if st.get("start_ok", True):
        st["units"]["fabrik-rotate.path"].update(ActiveState="active", SubState="waiting", Result="success")
        json.dump(st, open(os.environ["FAKE_SYSTEMCTL_STATE"], "w"))
        sys.exit(0)
    sys.exit(1)
if verb == "is-active":
    a = st["units"]["fabrik-rotate.path"]["ActiveState"]
    print(a); sys.exit(0 if a == "active" else 3)
sys.exit(4)
"""

FAKE_MAIL = """import json, os, sys
rec = os.environ["FAKE_MAIL_LOG"]
with open(rec, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "body": sys.stdin.read()}) + "\\n")
sys.exit(int(os.environ.get("FAKE_MAIL_RC", "0")))
"""


@pytest.fixture
def box(tmp_path, monkeypatch):
    ctl = tmp_path / "systemctl"
    ctl.write_text(FAKE_SYSTEMCTL)
    ctl.chmod(0o755)
    st = tmp_path / "ctl.json"
    mail = tmp_path / "opt" / "fabrik" / "scripts" / "mail.py"
    mail.parent.mkdir(parents=True)
    mail.write_text(FAKE_MAIL)
    proc = tmp_path / "proc"
    (proc / "sys" / "fs" / "inotify").mkdir(parents=True)
    (proc / "sys" / "fs" / "inotify" / "max_user_watches").write_text("1000\n")
    (proc / "sys" / "fs" / "inotify" / "max_user_instances").write_text("10\n")
    for k, v in {
        "BOX_BUDGET_SYSTEMCTL": ctl,
        "FAKE_SYSTEMCTL_STATE": st,
        "FABRIK_OPT_DIR": tmp_path / "opt",
        "FAKE_MAIL_LOG": tmp_path / "mail.jsonl",
        "BOX_BUDGET_PROC": proc,
        "BOX_BUDGET_STATE": tmp_path / "state" / "box-budget.json",
        "BOX_BUDGET_LOG": tmp_path / "state" / "box-budget.log",
    }.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.setattr(bb, "_canary", lambda: "ok")
    now = [1_000_000.0]
    monkeypatch.setattr(bb, "_now", lambda: now[0])
    world = {"tmp": tmp_path, "proc": proc, "now": now, "st": st}
    set_unit(world, "active")
    return world


def set_unit(world, active, *, enabled="enabled", result="success", start_ok=True):
    world["st"].write_text(
        json.dumps(
            {
                "enabled": enabled,
                "start_ok": start_ok,
                "units": {
                    "fabrik-rotate.path": {
                        "ActiveState": active,
                        "SubState": "x",
                        "Result": result,
                    },
                    "fabrik-rotate.service": {
                        "ActiveState": "inactive",
                        "SubState": "dead",
                        "Result": "exit-code",
                    },
                },
            }
        )
    )


def holder(world, pid, watches, instances=1, cmd="code-server watcher"):
    p = world["proc"] / str(pid)
    (p / "fd").mkdir(parents=True)
    (p / "fdinfo").mkdir()
    (p / "cmdline").write_bytes(cmd.encode().replace(b" ", b"\0"))
    per = [watches // instances + (1 if i < watches % instances else 0) for i in range(instances)]
    for i, n in enumerate(per):
        os.symlink("anon_inode:inotify", p / "fd" / str(10 + i))
        (p / "fdinfo" / str(10 + i)).write_text(
            "pos:\t0\nflags:\t00\n"
            + "".join(f"inotify wd:{j} ino:1 sdev:2 mask:3\n" for j in range(n))
        )


def mails(world):
    f = world["tmp"] / "mail.jsonl"
    return [json.loads(ln) for ln in f.read_text().splitlines()] if f.exists() else []


def calls(world):
    f = Path(str(world["st"]) + ".calls")
    return f.read_text().splitlines() if f.exists() else []


def log(world):
    f = world["tmp"] / "state" / "box-budget.log"
    return f.read_text() if f.exists() else ""


def test_failed_unit_is_restarted_and_mailed_once(box, capsys):
    set_unit(box, "failed", result="resources")
    assert bb.main([]) == 0
    assert "reset-failed fabrik-rotate.path fabrik-rotate.service" in calls(box)
    assert "start fabrik-rotate.path" in calls(box)
    m = mails(box)
    assert len(m) == 1 and m[0]["argv"][m[0]["argv"].index("--ack") + 1] == "no"
    assert "--to-agent" in m[0]["argv"] and "coordinator" in m[0]["argv"]
    assert (
        "Result=resources" in m[0]["body"] and "exit-code" in m[0]["body"]
    )  # the service's Result too
    # dies again 10 minutes later: same episode, healed again, no second mail
    box["now"][0] += 600
    set_unit(box, "failed", result="resources")
    bb.main([])
    assert len(mails(box)) == 1
    # healthy for 59 min: still open; a death now stays inside the episode
    box["now"][0] += 59 * 60
    bb.main([])
    assert (
        json.loads((box["tmp"] / "state" / "box-budget.json").read_text())["unit"]["state"]
        == "healed"
    )
    # an hour of health since the last bad reading closes it; the next death mails again
    box["now"][0] += 2 * 60
    bb.main([])
    assert "unit" not in json.loads((box["tmp"] / "state" / "box-budget.json").read_text())
    set_unit(box, "failed", result="resources")
    bb.main([])
    assert len(mails(box)) == 2
    assert (
        capsys.readouterr().out == ""
    )  # the tick child writes its log, never the inherited stdout


def test_failed_restart_escalates_and_recovers_once(box):
    set_unit(box, "failed", result="resources")
    bb.main([])  # healed: ack no
    set_unit(box, "failed", result="resources", start_ok=False)
    box["now"][0] += 300
    bb.main([])  # the first failed heal of an episode that had only healed escalates
    box["now"][0] += 300
    bb.main([])  # still failing: logged, not mailed
    acks = [m["argv"][m["argv"].index("--ack") + 1] for m in mails(box)]
    assert acks == ["no", "required"]
    assert "could NOT restart" in mails(box)[1]["body"]
    assert log(box).count("restart FAILED") == 2
    # fixed by hand: the episode closes after an hour of health with one recovered mail
    set_unit(box, "active")
    box["now"][0] += 3601
    bb.main([])
    assert [m["argv"][m["argv"].index("--ack") + 1] for m in mails(box)] == ["no", "required", "no"]
    assert "recovered" in mails(box)[2]["body"]


@pytest.mark.parametrize(
    ("active", "enabled", "note"),
    [
        ("active", "enabled", ""),
        ("failed", "disabled", "left alone"),
        ("inactive", "masked", "left alone"),
        ("activating", "enabled", "transitional"),
        ("deactivating", "enabled", "transitional"),
    ],
)
def test_unit_states_left_alone(box, active, enabled, note):
    set_unit(box, active, enabled=enabled)
    bb.main([])
    assert not [c for c in calls(box) if c.split()[0] in ("reset-failed", "start")]
    assert mails(box) == []
    assert note in log(box)


def test_unreadable_systemctl_does_nothing(box, monkeypatch):
    monkeypatch.setenv("BOX_BUDGET_SYSTEMCTL", str(box["tmp"] / "absent-systemctl"))
    bb.main([])
    assert mails(box) == [] and "unreadable" in log(box)


def test_inotify_amber_once_with_hysteresis_and_canary(box, monkeypatch):
    holder(box, 4242, 860, cmd="node code-server fileWatcher")
    holder(box, 4343, 10, cmd="vite")
    bb.main([])
    m = mails(box)
    assert len(m) == 1 and m[0]["argv"][m[0]["argv"].index("--ack") + 1] == "required"
    assert "870/1000" in m[0]["body"] and "pid 4242: 860 watches" in m[0]["body"]
    # 82%: between the lines — the episode stays open and silent
    (box["proc"] / "sys" / "fs" / "inotify" / "max_user_watches").write_text("1060\n")
    bb.main([])
    assert len(mails(box)) == 1
    assert json.loads((box["tmp"] / "state" / "box-budget.json").read_text())["inotify"] == "amber"
    # back over the line without ever dropping below 80%: the same episode, no second mail
    (box["proc"] / "sys" / "fs" / "inotify" / "max_user_watches").write_text("1000\n")
    bb.main([])
    assert len(mails(box)) == 1
    # below 80%: closed; back to 87%: a new episode mails
    (box["proc"] / "sys" / "fs" / "inotify" / "max_user_watches").write_text("1100\n")
    bb.main([])
    assert "inotify" not in json.loads((box["tmp"] / "state" / "box-budget.json").read_text())
    (box["proc"] / "sys" / "fs" / "inotify" / "max_user_watches").write_text("1000\n")
    bb.main([])
    assert len(mails(box)) == 2
    # the canary is the authority on exhaustion, whatever the scan saw
    (box["proc"] / "sys" / "fs" / "inotify" / "max_user_watches").write_text("100000\n")
    bb.main([])  # load ~1%: closes
    monkeypatch.setattr(bb, "_canary", lambda: "watches")
    bb.main([])
    assert len(mails(box)) == 3 and "ENOSPC" in mails(box)[2]["body"]


def test_instance_ratio_ranks_holders_by_instances(box):
    holder(box, 7001, 5, instances=9, cmd="many-instances")
    holder(box, 7002, 50, instances=1, cmd="many-watches")
    bb.main([])
    body = mails(box)[0]["body"]
    assert "instances 10/10" in body
    assert body.index("pid 7001") < body.index("pid 7002")


def test_unknown_scan_opens_nothing_unless_the_canary_says_exhausted(box, monkeypatch):
    p = box["proc"] / "999"
    p.mkdir()  # no fd/ table: unreadable
    bb.main([])
    assert mails(box) == [] and "inotify unknown" in log(box)
    monkeypatch.setattr(bb, "_canary", lambda: "instances")
    bb.main([])
    assert len(mails(box)) == 1 and "EMFILE" in mails(box)[0]["body"]


def test_failed_send_retries_corrupt_state_and_log_only(box, monkeypatch, capsys):
    set_unit(box, "failed", result="resources")
    monkeypatch.setenv("FAKE_MAIL_RC", "1")
    bb.main([])
    assert not (box["tmp"] / "state" / "box-budget.json").exists() or "unit" not in json.loads(
        (box["tmp"] / "state" / "box-budget.json").read_text()
    )
    monkeypatch.setenv("FAKE_MAIL_RC", "0")
    set_unit(box, "failed", result="resources")
    bb.main([])  # retried: this time it lands
    assert len(mails(box)) == 2
    # corrupt state reads as no episode: one duplicate mail, never a lost alert
    (box["tmp"] / "state" / "box-budget.json").write_text("{not json")
    set_unit(box, "failed", result="resources")
    bb.main([])
    assert len(mails(box)) == 3
    assert capsys.readouterr().out == ""
    assert log(box).count("box-budget:") >= 3


def test_report_exit_codes_and_no_side_effects(box, monkeypatch, capsys):
    holder(box, 4242, 100)
    assert bb.main(["--report"]) == 0
    out = capsys.readouterr().out
    assert "100/1000" in out and "fabrik-rotate.path" in out
    set_unit(box, "failed", result="resources")
    assert bb.main(["--report"]) == 2
    assert not [c for c in calls(box) if c.split()[0] in ("reset-failed", "start")]
    assert mails(box) == [] and not (box["tmp"] / "state" / "box-budget.json").exists()
    set_unit(box, "active")
    (box["proc"] / "777").mkdir()
    for d in box["proc"].iterdir():
        if d.name == "4242":
            import shutil

            shutil.rmtree(d)
    assert bb.main(["--report"]) == 1  # nothing readable: unknown
    assert bb.main(["--bogus"]) == 2


def test_the_real_canary_answers_ok_on_this_box(tmp_path, monkeypatch):
    monkeypatch.setenv("BOX_BUDGET_STATE", str(tmp_path / "s.json"))
    assert bb._canary() in ("ok", "watches", "instances", "unknown")


def test_script_runs_as_a_subprocess_with_a_bare_env(box):
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    for k in (
        "BOX_BUDGET_SYSTEMCTL",
        "FAKE_SYSTEMCTL_STATE",
        "FABRIK_OPT_DIR",
        "FAKE_MAIL_LOG",
        "BOX_BUDGET_PROC",
        "BOX_BUDGET_STATE",
        "BOX_BUDGET_LOG",
    ):
        env[k] = os.environ[k]
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert "box-budget:" not in r.stdout
