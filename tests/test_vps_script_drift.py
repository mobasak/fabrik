"""Graders for scripts/sysadmin/vps_script_drift.py and its weekly_catchup.sh rider (W-c792a205).

Every test runs the REAL script as a subprocess against a throwaway git repo standing in for the hub
root, with a stub ``ssh`` on PATH that prints a per-host fixture (or exits 255 for an unreachable host)
and a stub mail command that records what it was asked to send. No VPS is contacted.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

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


def remote_listing(overrides: dict[str, tuple[str, str] | None] | None = None) -> str:
    """What a fully synced host prints: '<mode> <md5> <abs path>' per file."""
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
    return "\n".join(out) + "\n"


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
    assert not any(x.startswith(("DRIFT", "MISSING", "MODE")) for x in r.stdout.splitlines())
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


def _catchup_env(tmp: Path, collector_rc: int) -> tuple[dict, Path]:
    root = tmp / "root"
    sysadmin = root / "scripts" / "sysadmin"
    sysadmin.mkdir(parents=True)
    log = tmp / "calls.log"
    for name, rc in (
        ("kaizen_collect_v2.py", collector_rc),
        ("feedback_relay.py", 0),
        ("rules_currency_watch.py", 0),
        ("vps_script_drift.py", 1),
    ):
        (sysadmin / name).write_text(
            f"import sys\nopen({str(log)!r}, 'a').write({name!r} + '\\n')\nsys.exit({rc})\n"
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
