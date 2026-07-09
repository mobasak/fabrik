"""Integration tests for claude-refresh-standbys.sh — the daily standby-token refresh routine.

Uses a throwaway HOME (so both the script's $HOME/.claude AND claude_rotate.py's Path.home()/.claude
point at the same tmp fleet) + a fake `claude` binary that simulates a token refresh on ping (and a
401 for one account), then asserts the routine re-snapshots LIVE accounts, leaves the DEAD one
untouched, restores the original active, and reports the dead account.
"""

import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/sysadmin/claude-refresh-standbys.sh"


def _creds(token):
    return json.dumps({"claudeAiOauth": {"accessToken": token, "refreshToken": "R-" + token}})


def _token(path):
    return json.loads(pathlib.Path(path).read_text())["claudeAiOauth"]["accessToken"]


def _setup(tmp_path, accounts):
    home = tmp_path / "home"
    claude = home / ".claude"
    accts = claude / "manager-accounts"
    accts.mkdir(parents=True)
    for name, tok in accounts.items():
        d = accts / name
        d.mkdir()
        (d / ".credentials.json").write_text(_creds(tok))
        os.chmod(d / ".credentials.json", 0o600)
    return home, claude, accts


def _write_active(claude, token):
    active = claude / ".credentials.json"
    active.write_text(_creds(token))
    os.chmod(active, 0o600)
    return active


def _fake_claude(tmp_path):
    # `claude -p ping`: read the live active token; a TOKEN-B account 401s (dead), any other refreshes
    # its token in place (append -R, simulating Claude's in-place OAuth refresh) and prints pong.
    binp = tmp_path / "bin" / "claude"
    binp.parent.mkdir(parents=True)
    binp.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "p = os.path.expanduser('~/.claude/.credentials.json')\n"
        "d = json.load(open(p))\n"
        "tok = d['claudeAiOauth']['accessToken']\n"
        "if 'TOKEN-B' in tok:\n"
        "    sys.stderr.write('Failed to authenticate. API Error: 401 Invalid authentication credentials\\n')\n"
        "    sys.exit(1)\n"
        "d['claudeAiOauth']['accessToken'] = tok + '-R'\n"
        "json.dump(d, open(p, 'w')); os.chmod(p, 0o600)\n"
        "print('pong')\n"
    )
    os.chmod(binp, 0o755)
    return binp


def _run(script_env, tmp_path):
    return subprocess.run(["bash", str(SCRIPT)], env=script_env, capture_output=True, text=True)


def test_script_syntax_valid():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_refresh_cycles_live_accounts_flags_dead_and_restores_active(tmp_path):
    home, claude, accts = _setup(
        tmp_path, {"acct-a": "TOKEN-A", "acct-b": "TOKEN-B", "acct-c": "TOKEN-C"}
    )
    active = _write_active(claude, "TOKEN-A")  # active = acct-a
    binp = _fake_claude(tmp_path)
    log = tmp_path / "refresh.log"
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_DIR": str(claude),
        "CLAUDE_BIN": str(binp),
        "CLAUDE_REFRESH_LOG": str(log),
        "CLAUDE_REFRESH_PING_TIMEOUT": "30",
        # neutralize the dead-account Telegram alert in tests (no real POST)
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_OWNER_ID": "",
    }
    r = _run(env, tmp_path)

    assert r.returncode == 1, f"exit 1 because a dead account exists\n{r.stderr}"
    # live accounts re-snapshotted with the refreshed token
    assert _token(accts / "acct-a" / ".credentials.json") == "TOKEN-A-R", "acct-a snapshot refreshed"
    assert _token(accts / "acct-c" / ".credentials.json") == "TOKEN-C-R", "acct-c snapshot refreshed"
    # DEAD account's snapshot LEFT UNTOUCHED (nothing to refresh)
    assert _token(accts / "acct-b" / ".credentials.json") == "TOKEN-B", "dead acct-b snapshot untouched"
    # original active restored (acct-a), now carrying its refreshed token
    assert _token(active) == "TOKEN-A-R", "active restored to orig acct-a (refreshed)"
    # log records the dead account + the refreshed count
    logtext = log.read_text()
    assert "REFRESH_DEAD" in logtext and "acct-b:dead_401" in logtext
    assert "refreshed=2/3" in logtext


def test_refresh_all_live_reports_ok(tmp_path):
    home, claude, accts = _setup(tmp_path, {"acct-a": "TOKEN-A", "acct-c": "TOKEN-C"})
    _write_active(claude, "TOKEN-A")
    binp = _fake_claude(tmp_path)
    log = tmp_path / "refresh.log"
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_DIR": str(claude),
        "CLAUDE_BIN": str(binp),
        "CLAUDE_REFRESH_LOG": str(log),
        "CLAUDE_REFRESH_PING_TIMEOUT": "30",
    }
    r = _run(env, tmp_path)
    assert r.returncode == 0, r.stderr
    assert log.read_text().startswith("REFRESH_OK 2/2"), log.read_text()


def test_refresh_no_accounts_skips(tmp_path):
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "manager-accounts").mkdir(parents=True)
    log = tmp_path / "refresh.log"
    env = {**os.environ, "HOME": str(home), "CLAUDE_DIR": str(claude), "CLAUDE_REFRESH_LOG": str(log)}
    r = _run(env, tmp_path)
    assert r.returncode == 0
    assert "REFRESH_SKIP:no_accounts" in log.read_text()
