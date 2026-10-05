"""Graders for scripts/sysadmin/vps_script_drift.py and its weekly_catchup.sh rider (W-c792a205).

Every test runs the REAL script as a subprocess against a throwaway git repo standing in for the hub
root, with a stub ``ssh`` on PATH that prints a per-host fixture (or exits 255 for an unreachable host)
and a stub mail command that records what it was asked to send. No VPS is contacted.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "vps_script_drift.py"
CATCHUP = REPO / "scripts" / "sysadmin" / "weekly_catchup.sh"

TEMPLATE = textwrap.dedent(
    """\
    # comment line naming /opt/fabrik/scripts/sysadmin/not-a-target.sh is still a target by path
    */15 * * * * root /opt/fabrik/scripts/sysadmin/proactive-check.sh >> /var/log/x.log 2>&1
    */5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py >> /var/log/x.log 2>&1
    * * * * * root /usr/local/bin/fabrik-autoheal
    """
)

# path -> (content, executable)
FILES = {
    "scripts/sysadmin/proactive-check.sh": ("#!/bin/sh\necho check\n", True),
    "scripts/sysadmin/detect_reversals.py": ("#!/usr/bin/env python3\nprint('r')\n", True),
    "scripts/sysadmin/not-a-target.sh": ("#!/bin/sh\n", True),
    "scripts/sysadmin/claude-run.sh": ("#!/bin/sh\nrun\n", True),
    "scripts/sysadmin/claude_rotate.py": ("print('rotate')\n", False),
    "scripts/sysadmin/quota_governor.py": ("print('gov')\n", False),
    "scripts/sysadmin/send-telegram.sh": ("#!/bin/sh\n", True),
    "scripts/sysadmin/keepalive-status.sh": ("#!/bin/sh\n", True),
    "scripts/sysadmin/system-prompt.txt": ("prompt\n", False),
    "scripts/sysadmin/bot.py": ("print('bot')\n", True),
    "scripts/sysadmin/hub_only_kaizen.py": ("print('hub only')\n", False),
    "scripts/audit/03-security.sh": ("#!/bin/sh\n", True),
    "scripts/audit/06-backup.sh": ("#!/bin/sh\n", True),
    "scripts/vps-autoheal.sh": ("#!/bin/sh\nheal\n", True),
}


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324 — content fingerprint, not security


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def make_hub(tmp: Path) -> Path:
    root = tmp / "hub"
    (root / "scripts/bootstrap/templates").mkdir(parents=True)
    (root / "scripts/bootstrap/templates/sysadmin-cron.template").write_text(TEMPLATE)
    for rel, (content, exe) in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        p.chmod(0o755 if exe else 0o644)
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "hub")
    return root


_SYNCED = object()


def _cron_block(cron) -> str:
    """The cron half of a host's listing: its active cron lines as CRON lines, or CRON-ABSENT."""
    if cron is None:
        return "CRON-ABSENT\n"
    text = TEMPLATE if cron is _SYNCED else cron
    lines = text.splitlines()
    return "".join(f"CRON {ln}\n" for ln in lines) + "CRON-END\n"


def remote_listing(overrides: dict[str, tuple[str, str] | None] | None = None, cron=_SYNCED) -> str:
    """What a fully synced host prints: '<mode> <md5> <abs path>' per file, then its cron lines (the template's,
    unless ``cron`` is other text, or ``None`` for an absent cron file)."""
    overrides = overrides or {}
    out = []
    for rel, (content, exe) in FILES.items():
        if rel in overrides:
            ov = overrides[rel]
            if ov is None:
                continue
            mode, body = ov
            content_md5 = _md5(body)
        else:
            mode, content_md5 = ("755" if exe else "644"), _md5(content)
        path = (
            "/usr/local/bin/fabrik-autoheal"
            if rel == "scripts/vps-autoheal.sh"
            else f"/opt/fabrik/{rel}"
        )
        out.append(f"{mode} {content_md5} {path}")
    return "\n".join(out) + "\n" + _cron_block(cron)


def make_env(tmp: Path, root: Path, hosts: dict[str, str | None], now: int | None = None) -> dict:
    """hosts: host -> listing text, or None for unreachable."""
    fx = tmp / "fixtures"
    fx.mkdir(exist_ok=True)
    for h, listing in hosts.items():
        (fx / f"{h}.down").unlink(missing_ok=True)
        if listing is None:
            (fx / f"{h}.down").write_text("")
        else:
            (fx / h).write_text(listing)
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    ssh = bindir / "ssh"
    ssh.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import sys, pathlib
            args = sys.argv[1:]
            host = None
            i = 0
            while i < len(args):
                if args[i] == "-o":
                    i += 2
                    continue
                if args[i].startswith("-"):
                    i += 1
                    continue
                host = args[i]
                break
            fx = pathlib.Path({str(fx)!r})
            if host is None or (fx / (host + ".down")).exists():
                sys.stderr.write("ssh: connect to host " + str(host) + ": Connection refused\\n")
                sys.exit(255)
            sys.stdout.write((fx / host).read_text())
            """
        )
    )
    ssh.chmod(0o755)
    mail = bindir / "mail-stub"
    mail.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import sys, json, os, pathlib
            log = pathlib.Path({str(tmp / "mail.log")!r})
            if os.environ.get("MAIL_STUB_FAIL") == "1":
                sys.exit(1)
            rec = {{"argv": sys.argv[1:], "body": sys.stdin.read()}}
            with log.open("a") as f:
                f.write(json.dumps(rec) + "\\n")
            """
        )
    )
    mail.chmod(0o755)
    env = dict(os.environ)
    env.update(
        {
            "PATH": f"{bindir}:{env['PATH']}",
            "FABRIK_ROOT": str(root),
            "FABRIK_DRIFT_HOSTS": " ".join(hosts),
            "FABRIK_DRIFT_STATE": str(tmp / "state.json"),
            "FABRIK_DRIFT_MAIL": str(mail),
        }
    )
    if now is not None:
        env["FABRIK_DRIFT_NOW"] = str(now)
    return env


def run(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=120
    )


def mails(tmp: Path) -> list[dict]:
    log = tmp / "mail.log"
    if not log.exists():
        return []
    return [json.loads(x) for x in log.read_text().splitlines() if x.strip()]


# ── Behaviour 1: tier-1 differences are reported, exit 1 ─────────────────────────────────────────


def test_drift_reported(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(
        tmp_path,
        root,
        {
            "vps": remote_listing(
                {"scripts/sysadmin/proactive-check.sh": ("755", "#!/bin/sh\nold\n")}
            )
        },
    )
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "DRIFT vps scripts/sysadmin/proactive-check.sh" in r.stdout


def test_missing_reported(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(tmp_path, root, {"vps2": remote_listing({"scripts/audit/06-backup.sh": None})})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "MISSING vps2 scripts/audit/06-backup.sh" in r.stdout


def test_mode_drift_reported(tmp_path):
    # The measured 2026-09-05 outage: same bytes, exec bit lost on the host.
    root = make_hub(tmp_path)
    body = FILES["scripts/sysadmin/detect_reversals.py"][0]
    env = make_env(
        tmp_path,
        root,
        {"vps": remote_listing({"scripts/sysadmin/detect_reversals.py": ("644", body)})},
    )
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "MODE vps scripts/sysadmin/detect_reversals.py" in r.stdout
    assert "DRIFT vps scripts/sysadmin/detect_reversals.py" not in r.stdout


def test_autoheal_compared(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(
        tmp_path,
        root,
        {"vps3": remote_listing({"scripts/vps-autoheal.sh": ("755", "#!/bin/sh\nold heal\n")})},
    )
    r = run(env)
    assert r.returncode == 1
    assert "DRIFT vps3 scripts/vps-autoheal.sh" in r.stdout


# ── Behaviour 2: tier 2 is shown, never mailed ───────────────────────────────────────────────────


def test_tier2_not_mailed(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(
        tmp_path,
        root,
        {"vps": remote_listing({"scripts/sysadmin/hub_only_kaizen.py": ("644", "changed\n")})},
    )
    r = run(env, "--mail")
    assert r.returncode == 1
    assert "DRIFT vps scripts/sysadmin/hub_only_kaizen.py" in r.stdout
    assert mails(tmp_path) == []


# ── Behaviour 3: clean exits 0 and clears the watermark ─────────────────────────────────────────


def test_clean_exits_zero(tmp_path):
    root = make_hub(tmp_path)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"signature": "old", "mailed_at": 1, "hosts": {}}))
    env = make_env(tmp_path, root, {"vps": remote_listing(), "vps2": remote_listing()})
    r = run(env, "--mail")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not any(
        x.startswith(("DRIFT", "MISSING", "MODE", "CRON")) for x in r.stdout.splitlines()
    )
    assert not state.exists() or json.loads(state.read_text()).get("signature") in (None, "")
    assert mails(tmp_path) == []


# ── Behaviour 4: an unreachable host ─────────────────────────────────────────────────────────────


def test_unreachable_keeps_signature(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/proactive-check.sh": ("755", "old\n")})
    env = make_env(tmp_path, root, {"vps": remote_listing(), "vps2": drift}, now=1000)
    assert run(env, "--mail").returncode == 1
    assert len(mails(tmp_path)) == 1
    # vps2 drops out: no new signature, no new mail, exit 2
    env = make_env(tmp_path, root, {"vps": remote_listing(), "vps2": None}, now=2000)
    r = run(env, "--mail")
    assert r.returncode == 2, r.stdout + r.stderr
    assert len(mails(tmp_path)) == 1
    # vps2 returns with the same drift: still the same signature, still no mail
    env = make_env(tmp_path, root, {"vps": remote_listing(), "vps2": drift}, now=3000)
    assert run(env, "--mail").returncode == 1
    assert len(mails(tmp_path)) == 1


def test_unreachable_mails_after_three(tmp_path):
    root = make_hub(tmp_path)
    for i, expect in ((1, 0), (2, 0), (3, 1), (4, 1)):
        env = make_env(tmp_path, root, {"vps": remote_listing(), "vps3": None}, now=1000 * i)
        r = run(env, "--mail")
        assert r.returncode == 2
        assert len(mails(tmp_path)) == expect, (i, r.stdout, r.stderr)
    assert "vps3" in mails(tmp_path)[0]["body"]


# ── Behaviour 5: mail once per signature, re-nudge after 7 days, failure keeps watermark ─────────


def test_mail_once_per_signature(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    env = make_env(tmp_path, root, {"vps": drift}, now=1000)
    run(env, "--mail")
    run(env, "--mail")
    sent = mails(tmp_path)
    assert len(sent) == 1
    argv = sent[0]["argv"]
    for flag in ("--to-agent", "fleet", "--ack", "required", "--kind", "finding"):
        assert flag in argv
    assert "scripts/sysadmin/claude_rotate.py" in sent[0]["body"]
    assert "sync-vps-sysadmin.sh" in sent[0]["body"]


def test_persisting_drift_renudges(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    run(make_env(tmp_path, root, {"vps": drift}, now=1000), "--mail")
    run(make_env(tmp_path, root, {"vps": drift}, now=1000 + 6 * 86400), "--mail")
    assert len(mails(tmp_path)) == 1
    run(make_env(tmp_path, root, {"vps": drift}, now=1000 + 7 * 86400 + 1), "--mail")
    assert len(mails(tmp_path)) == 2


def test_mail_failure_keeps_watermark(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    env = make_env(tmp_path, root, {"vps": drift}, now=1000)
    env["MAIL_STUB_FAIL"] = "1"
    run(env, "--mail")
    assert mails(tmp_path) == []
    env.pop("MAIL_STUB_FAIL")
    run(env, "--mail")
    assert len(mails(tmp_path)) == 1


# ── Behaviour 6: committed HEAD is the reference; every template target is tier 1 ─────────────────


def test_working_tree_wip_ignored(tmp_path):
    root = make_hub(tmp_path)
    (root / "scripts/sysadmin/proactive-check.sh").write_text("#!/bin/sh\nuncommitted wip\n")
    env = make_env(tmp_path, root, {"vps": remote_listing()})
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr


def test_template_targets_covered():
    # Against the REAL hub tree: every cron-template target is tier 1, and every tier-1 path exists.
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import vps_script_drift as d
    finally:
        sys.path.pop(0)
    targets = d.template_targets(REPO)
    tier1 = d.tier1_paths(REPO)
    assert targets, "no targets parsed from sysadmin-cron.template"
    assert set(targets) <= set(tier1)
    missing = [p for p in tier1 if not (REPO / p).is_file()]
    assert missing == [], missing


# ── Behaviour 7: weekly_catchup.sh — stamp only on collector success; rider at most daily ────────


def _catchup_env(tmp: Path, collector_rc: int, drift_rc: int = 1) -> tuple[dict, Path]:
    root = tmp / "root"
    sysadmin = root / "scripts" / "sysadmin"
    sysadmin.mkdir(parents=True)
    log = tmp / "calls.log"
    for name, rc in (
        ("kaizen_collect_v2.py", collector_rc),
        ("feedback_relay.py", 0),
        ("rules_currency_watch.py", 0),
        ("vps_script_drift.py", drift_rc),
    ):
        (sysadmin / name).write_text(
            f"import sys, pathlib\nopen({str(log)!r}, 'a').write({name!r} + '\\n')\n"
            # the real script touches --stamp only on a verdict (exit 0-2)
            f"if {rc} < 3 and '--stamp' in sys.argv:\n"
            "    pathlib.Path(sys.argv[sys.argv.index('--stamp') + 1]).touch()\n"
            f"sys.exit({rc})\n"
        )
    home = tmp / "home"
    home.mkdir()
    env = dict(os.environ)
    env.update({"HOME": str(home), "FABRIK_ROOT": str(root), "FABRIK_PY": sys.executable})
    return env, home / ".claude" / "state"


def test_collector_failure_withholds_stamp(tmp_path):
    env, state = _catchup_env(tmp_path, collector_rc=1)
    r = subprocess.run(
        ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert not (state / "daily-kaizen_collect_v2.py.stamp").exists()
    calls = (tmp_path / "calls.log").read_text().split()
    assert "feedback_relay.py" in calls  # riders still run


def test_drift_rider_daily_stamp(tmp_path):
    env, state = _catchup_env(tmp_path, collector_rc=1)
    for _ in range(2):
        subprocess.run(
            ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
        )
    calls = (tmp_path / "calls.log").read_text().split()
    assert calls.count("kaizen_collect_v2.py") == 2  # the failing collector retries
    assert calls.count("vps_script_drift.py") == 1  # the drift rider does not
    assert (state / "daily-vps_script_drift.stamp").exists()


def test_collector_success_stamps(tmp_path):
    env, state = _catchup_env(tmp_path, collector_rc=0)
    r = subprocess.run(
        ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr  # the rider's rc 1 (a verdict) does not leak
    assert (state / "daily-kaizen_collect_v2.py.stamp").exists()


def test_drift_rider_failure_withholds_stamp(tmp_path):
    # rc 3 is the check itself failing: no stamp, so the next hourly run retries it.
    env, state = _catchup_env(tmp_path, collector_rc=0, drift_rc=3)
    r = subprocess.run(
        ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (state / "daily-vps_script_drift.stamp").exists()
    assert "vps_script_drift.py reached no verdict (rc=3)" in r.stderr


def test_drift_rider_missing_script_withholds_stamp(tmp_path):
    # python exits 2 for a missing file: verdict-shaped, but the check never ran.
    env, state = _catchup_env(tmp_path, collector_rc=0)
    (Path(env["FABRIK_ROOT"]) / "scripts/sysadmin/vps_script_drift.py").unlink()
    r = subprocess.run(
        ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (state / "daily-vps_script_drift.stamp").exists()
    assert "reached no verdict (rc=2)" in r.stderr


# ── Behaviour 8: REMOTE_CMD itself, run by a real shell; malformed input never crashes ───────────


def _module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import vps_script_drift as d
    finally:
        sys.path.pop(0)
    return d


def _host_tree(tmp: Path) -> tuple[Path, str]:
    """A fake host root: <tmp>/host/opt/fabrik/scripts/sysadmin + autoheal, no scripts/audit (a spoke)."""
    d = _module()
    host = tmp / "host"
    sysadmin = host / "opt/fabrik/scripts/sysadmin"
    (sysadmin / "__pycache__").mkdir(parents=True)
    (sysadmin / "with space.sh").write_text("spaced\n")
    (sysadmin / "with space.sh").chmod(0o755)
    (sysadmin / "plain.py").write_text("plain\n")
    (sysadmin / "plain.py").chmod(0o644)
    (sysadmin / "__pycache__/x.cpython-312.pyc").write_bytes(b"\0")
    (sysadmin / "link.sh").symlink_to("plain.py")
    autoheal = host / "usr/local/bin/fabrik-autoheal"
    autoheal.parent.mkdir(parents=True)
    autoheal.write_text("#!/bin/sh\nheal\n")
    autoheal.chmod(0o755)
    cmd = d.REMOTE_CMD.replace("/opt/fabrik/", f"{host}/opt/fabrik/").replace(
        d.AUTOHEAL_REMOTE, str(autoheal)
    )
    return host, cmd


def _parse(host: Path, text: str) -> dict:
    d = _module()
    return d.parse_listing(
        text, base=f"{host}/opt/fabrik/", autoheal=f"{host}/usr/local/bin/fabrik-autoheal"
    )


def test_remote_cmd_real_shell(tmp_path):
    host, cmd = _host_tree(tmp_path)
    r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60)
    got = _parse(host, r.stdout)
    assert got["scripts/sysadmin/with space.sh"] == ("755", _md5("spaced\n")), r.stdout
    assert got["scripts/sysadmin/plain.py"] == ("644", _md5("plain\n"))
    assert got["scripts/vps-autoheal.sh"] == ("755", _md5("#!/bin/sh\nheal\n"))
    assert not any("__pycache__" in k or k.endswith("link.sh") for k in got), got


def test_remote_cmd_unreadable_file(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    d = _module()
    host, cmd = _host_tree(tmp_path)
    (host / "opt/fabrik/scripts/sysadmin/plain.py").chmod(0)
    r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60)
    assert _parse(host, r.stdout)["scripts/sysadmin/plain.py"] == d.UNREADABLE, r.stdout


def test_remote_cmd_without_md5sum(tmp_path):
    d = _module()
    host, cmd = _host_tree(tmp_path)
    bindir = tmp_path / "nomd5"
    bindir.mkdir()
    for tool in ("find", "stat", "sh"):
        (bindir / tool).symlink_to(shutil.which(tool))
    r = subprocess.run(
        [shutil.which("sh"), "-c", cmd],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": str(bindir)},
    )
    got = _parse(host, r.stdout)
    assert got and all(v == d.UNREADABLE for v in got.values()), r.stdout + r.stderr


def test_unreadable_reported(tmp_path):
    root = make_hub(tmp_path)
    listing = remote_listing({"scripts/sysadmin/bot.py": None})
    listing += "UNREADABLE - /opt/fabrik/scripts/sysadmin/bot.py\n"
    listing += "garbage\n\n abc  /opt/fabrik/scripts/sysadmin/x\n"  # malformed lines are dropped
    env = make_env(tmp_path, root, {"vps": listing})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UNREADABLE vps scripts/sysadmin/bot.py" in r.stdout
    assert "MISSING vps scripts/sysadmin/bot.py" not in r.stdout


def test_committed_symlink_not_compared(tmp_path):
    root = make_hub(tmp_path)
    (root / "scripts/sysadmin/alias.sh").symlink_to("claude-run.sh")
    _git(root, "add", "scripts/sysadmin/alias.sh")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "link")
    env = make_env(tmp_path, root, {"vps": remote_listing()})
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize(
    "bad", ["{not json", "[1, 2]", '{"hosts": [], "unreachable_runs": {"vps3": "x"}}']
)
def test_corrupt_state_starts_fresh(tmp_path, bad):
    root = make_hub(tmp_path)
    (tmp_path / "state.json").write_text(bad)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    env = make_env(tmp_path, root, {"vps": drift, "vps3": None}, now=1000)
    r = run(env, "--mail")
    assert r.returncode == 2, r.stdout + r.stderr
    assert len(mails(tmp_path)) == 1
    saved = json.loads((tmp_path / "state.json").read_text())
    assert saved["unreachable_runs"] == {"vps": 0, "vps3": 1}


def test_removed_host_pruned(tmp_path):
    root = make_hub(tmp_path)
    (tmp_path / "state.json").write_text(
        json.dumps({"hosts": {"old": ["DRIFT old x"]}, "unreachable_runs": {"old": 2}})
    )
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    run(make_env(tmp_path, root, {"vps": drift}, now=1000), "--mail")
    saved = json.loads((tmp_path / "state.json").read_text())
    assert "old" not in saved["hosts"] and "old" not in saved["unreachable_runs"]


def test_mail_command_missing_is_not_a_crash(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    env = make_env(tmp_path, root, {"vps": drift}, now=1000)
    env["FABRIK_DRIFT_MAIL"] = str(tmp_path / "no-such-mailer")
    r = run(env, "--mail")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "signature" not in json.loads((tmp_path / "state.json").read_text())


def test_check_failure_exits_three(tmp_path):
    not_a_repo = tmp_path / "plain"
    (not_a_repo / "scripts/bootstrap/templates").mkdir(parents=True)
    (not_a_repo / "scripts/bootstrap/templates/sysadmin-cron.template").write_text(TEMPLATE)
    env = make_env(tmp_path, not_a_repo, {"vps": remote_listing()})
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)
    r = run(env)
    assert r.returncode == 3, r.stdout + r.stderr


def test_mail_body_names_renudge_days(tmp_path):
    root = make_hub(tmp_path)
    drift = remote_listing({"scripts/sysadmin/claude_rotate.py": ("644", "old\n")})
    run(make_env(tmp_path, root, {"vps": drift}, now=1000), "--mail")
    assert f"every {_module().RENUDGE_DAYS} days" in mails(tmp_path)[0]["body"]


def test_stamp_written_only_on_a_verdict(tmp_path):
    root = make_hub(tmp_path)
    stamp = tmp_path / "s" / "drift.stamp"
    env = make_env(tmp_path, root, {"vps": None})
    assert run(env, "--stamp", str(stamp)).returncode == 2
    assert stamp.exists()  # unreachable is a verdict
    stamp.unlink()
    env["FABRIK_ROOT"] = str(tmp_path / "no-such-hub")
    assert run(env, "--stamp", str(stamp)).returncode == 3
    assert not stamp.exists()


def test_short_modes_parse():
    # `stat -c %a` drops leading zeros: 044 prints "44", 000 prints "0".
    d = _module()
    got = d.parse_listing(f"44 {_md5('x')} /opt/fabrik/a\n0 {_md5('y')} /opt/fabrik/b\n")
    assert got == {"a": ("44", _md5("x")), "b": ("0", _md5("y"))}


# ── Behaviour 9: the installed cron file schedules the template's hub paths (W-73feca74) ─────────

_RETIRED = "0 1 * * * root /opt/fabrik/scripts/sysadmin/retired.sh >> /var/log/x.log 2>&1\n"


def test_cron_missing_job_reported(tmp_path):
    root = make_hub(tmp_path)
    cron = "".join(ln + "\n" for ln in TEMPLATE.splitlines() if "detect_reversals" not in ln)
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=cron)})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CRONMISSING vps /opt/fabrik/scripts/sysadmin/detect_reversals.py" in r.stdout


def test_cron_extra_job_reported(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=TEMPLATE + _RETIRED)})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CRONEXTRA vps /opt/fabrik/scripts/sysadmin/retired.sh" in r.stdout


def test_cron_file_absent_reported(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=None)})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CRONMISSING vps /etc/cron.d/vps-sysadmin" in r.stdout


def test_cron_minutes_and_comments_ignored(tmp_path):
    """Per-host minutes differ, env lines carry no job, and a path named only in a comment is not scheduled."""
    root = make_hub(tmp_path)
    cron = (
        'SHELL=/bin/sh\nMAILTO=""\n'
        "# 0 2 * * * root /opt/fabrik/scripts/sysadmin/retired.sh\n"
        "*/7 * * * * root /opt/fabrik/scripts/sysadmin/proactive-check.sh >> /var/log/x.log 2>&1\n"
        "*/3 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py >> /var/log/x.log 2>&1\n"
        "* * * * * root /usr/local/bin/fabrik-autoheal\n"
    )
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=cron)})
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CRON" not in r.stdout.replace("vps_script_drift:", "")


def test_cron_difference_is_mailed(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=TEMPLATE + _RETIRED)})
    r = run(env, "--mail")
    assert r.returncode == 1, r.stdout + r.stderr
    sent = mails(tmp_path)
    assert (
        len(sent) == 1
        and "CRONEXTRA vps /opt/fabrik/scripts/sysadmin/retired.sh" in sent[0]["body"]
    )
    assert "/etc/cron.d/vps-sysadmin schedules a different set" in sent[0]["body"], sent[0]["body"]
    assert "never re-run step 14 whole" in sent[0]["body"], sent[0]["body"]


def test_remote_cmd_cron_half_real_shell(tmp_path):
    d = _module()
    host, cmd = _host_tree(tmp_path)
    cron = host / "etc/cron.d/vps-sysadmin"
    cron.parent.mkdir(parents=True)
    cron.write_text(
        "# a comment naming /opt/fabrik/scripts/sysadmin/old.sh\n"
        "   # an indented comment\n"
        "SHELL=/bin/sh\n"
        "*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py >> /var/log/x.log 2>&1\n"
    )
    cmd = cmd.replace(d.CRON_REMOTE, str(cron))
    out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60).stdout
    assert d.parse_cron(out) == [
        "# a comment naming /opt/fabrik/scripts/sysadmin/old.sh",
        "   # an indented comment",
        "SHELL=/bin/sh",
        "*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py >> /var/log/x.log 2>&1",
    ], out
    assert out.rstrip().endswith("CRON-END"), out
    assert d.cron_paths("\n".join(d.parse_cron(out))) == {
        "/opt/fabrik/scripts/sysadmin/detect_reversals.py"
    }
    assert _parse(host, out), "the script listing still parses with the cron lines appended"
    cron.unlink()
    out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60).stdout
    assert d.parse_cron(out) is None, out


def test_cron_reference_is_the_committed_template(tmp_path):
    """An uncommitted template edit in the hub checkout is not the hub's cron set."""
    root = make_hub(tmp_path)
    tpl = root / "scripts/bootstrap/templates/sysadmin-cron.template"
    tpl.write_text(tpl.read_text() + _RETIRED)
    env = make_env(tmp_path, root, {"vps": remote_listing()})
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cron_file_unreadable_reported(tmp_path):
    root = make_hub(tmp_path)
    listing = remote_listing(cron="").rstrip("\n") + "\nCRON-UNREADABLE\n"
    env = make_env(tmp_path, root, {"vps": listing})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CRONUNREADABLE vps /etc/cron.d/vps-sysadmin" in r.stdout
    assert "CRONMISSING" not in r.stdout


def test_cron_autoheal_and_quotes_not_misread(tmp_path):
    """fabrik-autoheal may be scheduled outside this file, and a quoted path is the same path."""
    root = make_hub(tmp_path)
    cron = (
        '*/15 * * * * root bash -c "/opt/fabrik/scripts/sysadmin/proactive-check.sh" >> /var/log/x.log 2>&1\n'
        "*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py >> /opt/fabrik/logs/r.log 2>&1\n"
    )
    env = make_env(tmp_path, root, {"vps": remote_listing(cron=cron)})
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cron_half_cut_short_is_unverified_not_every_job_missing(tmp_path):
    """No CRON-END (a cut session, a failed reader): one CRONUNVERIFIED line, never a CRONMISSING per template job."""
    root = make_hub(tmp_path)
    listing = remote_listing().replace("CRON-END\n", "")
    env = make_env(tmp_path, root, {"vps": listing})
    r = run(env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CRONUNVERIFIED vps /etc/cron.d/vps-sysadmin" in r.stdout
    assert "CRONMISSING" not in r.stdout


def test_remote_cmd_cron_half_needs_only_shell_builtins(tmp_path):
    """The cron half reads the file with sh builtins: a host without sed or grep still reports, and a last line
    without a newline is kept."""
    d = _module()
    host, cmd = _host_tree(tmp_path)
    cron = host / "etc/cron.d/vps-sysadmin"
    cron.parent.mkdir(parents=True)
    cron.write_text(
        "*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py\n"
        "0 3 * * 0 root /opt/fabrik/scripts/sysadmin/weekly-maintenance.sh"
    )
    cmd = cmd.replace(d.CRON_REMOTE, str(cron))
    bindir = tmp_path / "shonly"
    bindir.mkdir()
    for tool in ("find", "stat", "sh", "md5sum"):
        (bindir / tool).symlink_to(shutil.which(tool))
    out = subprocess.run(
        [shutil.which("sh"), "-c", cmd],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": str(bindir)},
    ).stdout
    assert d.cron_paths("\n".join(d.parse_cron(out))) == {
        "/opt/fabrik/scripts/sysadmin/detect_reversals.py",
        "/opt/fabrik/scripts/sysadmin/weekly-maintenance.sh",
    }, out


def _cron_half(tmp: Path, target: Path) -> str:
    d = _module()
    _host, cmd = _host_tree(tmp)
    cmd = cmd.replace(d.CRON_REMOTE, str(target))
    return subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60).stdout


def test_remote_cmd_cron_path_not_a_file_is_unreadable(tmp_path):
    """A directory at the cron path makes the reader fail: CRONUNREADABLE, never one CRONMISSING per job."""
    d = _module()
    target = tmp_path / "cron-dir"
    target.mkdir()
    out = _cron_half(tmp_path, target)
    assert d.parse_cron(out) == ["CRON-UNREADABLE"], out


def test_remote_cmd_unreadable_cron_file(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    d = _module()
    target = tmp_path / "vps-sysadmin"
    target.write_text("*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py\n")
    target.chmod(0)
    out = _cron_half(tmp_path, target)
    assert d.parse_cron(out) == ["CRON-UNREADABLE"], out


def test_cron_paths_ignores_env_lines_comments_and_templated_paths():
    d = _module()
    text = (
        "PATH=/opt/fabrik/scripts/sysadmin:/usr/bin:/bin\n"
        "SHELL = /opt/fabrik/scripts/sysadmin/sh\n"
        '0 4 * * * root echo "a #b" /opt/fabrik/scripts/sysadmin/q.sh\n'
        "0 1 * * * root /opt/fabrik/scripts/{{HOST_NAME}}/x.sh\n"
        "0 2 * * * root /opt/fabrik/scripts/sysadmin/a.sh,/opt/fabrik/scripts/sysadmin/b.sh\n"
        "0 3 * * * root /opt/fabrik/scripts/sysadmin/c.sh # was /opt/fabrik/scripts/sysadmin/old.sh\n"
        "0 4 * * * root /opt/fabrik/scripts/sysadmin/d.sh # it's done, was /opt/fabrik/scripts/sysadmin/old2.sh\n"
        "0 5 * * * root cat % /opt/fabrik/scripts/sysadmin/stdin-only.sh\n"
        '0 7 * * * root echo "50%" /opt/fabrik/scripts/sysadmin/after-quoted-pct.sh\n'
        "0 6 * * * root /opt/fabrik/scripts/sysadmin/r.sh 50\\% done\n"
        '"FOO"=/opt/fabrik/scripts/sysadmin/z.sh\n'
    )
    assert d.cron_paths(text) == {
        "/opt/fabrik/scripts/sysadmin/a.sh",
        "/opt/fabrik/scripts/sysadmin/b.sh",
        "/opt/fabrik/scripts/sysadmin/c.sh",
        "/opt/fabrik/scripts/sysadmin/d.sh",
        "/opt/fabrik/scripts/sysadmin/q.sh",
        "/opt/fabrik/scripts/sysadmin/r.sh",
    }


def test_parse_cron_splits_on_newlines_only():
    """A form feed inside a cron line is data, not a line break that could fake a CRON-ABSENT."""
    d = _module()
    assert d.parse_cron("CRON 0 1 * * * root echo hi\x0cCRON-ABSENT\nCRON-END\n") == [
        "0 1 * * * root echo hi\x0cCRON-ABSENT"
    ]


def test_cron_unverified_mail_says_recheck(tmp_path):
    root = make_hub(tmp_path)
    env = make_env(tmp_path, root, {"vps": remote_listing().replace("CRON-END\n", "")})
    r = run(env, "--mail")
    assert r.returncode == 1, r.stdout + r.stderr
    body = mails(tmp_path)[0]["body"]
    assert "CRONUNREADABLE/CRONUNVERIFIED" in body, body


def test_remote_cmd_failed_redirect_is_unreadable(tmp_path):
    """A redirect that fails after the regular-file test passed (the file vanished): CRON-UNREADABLE, not CRON-END."""
    d = _module()
    good = tmp_path / "vps-sysadmin"
    good.write_text("*/5 * * * * root /opt/fabrik/scripts/sysadmin/detect_reversals.py\n")
    _host, cmd = _host_tree(tmp_path)
    cmd = cmd.replace(d.CRON_REMOTE, str(good))
    assert cmd.count("} < " + str(good)) == 1, cmd
    cmd = cmd.replace("} < " + str(good), "} < " + str(tmp_path / "gone"))
    out = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=60).stdout
    assert d.parse_cron(out) == ["CRON-UNREADABLE"], out
