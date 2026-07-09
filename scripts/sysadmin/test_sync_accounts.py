# AFTER-EDIT: none
"""Tests for sync-claude-accounts-to-fleet.sh — N-host fan-out (per-host completeness),
mkdir-before-scp ordering, active-creds refresh, unsafe-dirname skip, empty-hosts guard,
the real (non-DRY_RUN) error/continue/exit-code path, and a static no-token-leak guard.
Fixtures use fake creds (organizationUuid only) and DRY_RUN or fake ssh/scp — no network."""
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/sysadmin/sync-claude-accounts-to-fleet.sh"


def _make_claude_dir(tmp_path, names=("mob-dir", "ob-dir")):
    claude_dir = tmp_path / ".claude"
    accts = claude_dir / "manager-accounts"
    for n in names:
        (accts / n).mkdir(parents=True)
        (accts / n / ".credentials.json").write_text(f'{{"organizationUuid":"org-{n}"}}')
    (claude_dir / ".credentials.json").write_text('{"organizationUuid":"org-mob-dir"}')
    return claude_dir


def _dry_run(tmp_path, hosts="vps vps2 vps3", claude_dir=None, sync_active=False):
    claude_dir = claude_dir or _make_claude_dir(tmp_path)
    env = {
        **os.environ,
        "DRY_RUN": "1",
        "CLAUDE_DIR": str(claude_dir),
        "CLAUDE_FLEET_HOSTS": hosts,
        "CLAUDE_FLEET_SYNC_LOG": str(tmp_path / "sync.log"),
    }
    if sync_active:
        env["SYNC_ACTIVE"] = "1"
    r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    return r


def test_script_syntax_valid():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_dry_run_each_host_gets_its_own_mkdir_and_scp(tmp_path):
    out = _dry_run(tmp_path, hosts="vps vps2 vps3").stdout
    lines = out.splitlines()
    for host in ("vps", "vps2", "vps3"):
        assert any(f"ozgur@{host} mkdir" in ln for ln in lines), f"{host} missing its own mkdir"
        assert any("scp" in ln and f"ozgur@{host}:" in ln for ln in lines), f"{host} missing its own scp"


def test_dry_run_adds_a_new_host(tmp_path):
    out = _dry_run(tmp_path, hosts="vps vps2 vps3 vps4").stdout
    assert any("ozgur@vps4 mkdir" in ln for ln in out.splitlines()), "extending CLAUDE_FLEET_HOSTS adds the VPS"


def test_dry_run_mkdirs_before_scp(tmp_path):
    lines = _dry_run(tmp_path).stdout.splitlines()
    first_mkdir = next(i for i, ln in enumerate(lines) if "mkdir -p" in ln)
    first_scp = next(i for i, ln in enumerate(lines) if "DRY_RUN: scp" in ln)
    assert first_mkdir < first_scp, "remote mkdir must precede scp"


def test_dry_run_pushes_snapshots_but_not_active_by_default(tmp_path):
    # Default sync pushes the manager-account SNAPSHOTS (safe) but must NOT touch each host's
    # ACTIVE creds — overwriting the active repoints the fleet's sysadmin identity to whatever
    # the WSL box is on and clobbers the host's self-refreshed token (SYNC_ACTIVE opt-in only).
    out = _dry_run(tmp_path).stdout
    assert "manager-accounts/mob-dir/.credentials.json" in out
    assert "manager-accounts/ob-dir/.credentials.json" in out
    # the active-creds scp target is `:.claude/.credentials.json` with NO manager-accounts/ prefix
    active_lines = [ln for ln in out.splitlines() if ln.rstrip().endswith(":.claude/.credentials.json")]
    assert not active_lines, f"active creds must NOT be pushed by default, got: {active_lines}"


def test_dry_run_sync_active_opt_in_pushes_active_with_backup(tmp_path):
    out = _dry_run(tmp_path, sync_active=True).stdout
    active_lines = [ln for ln in out.splitlines() if ln.rstrip().endswith(":.claude/.credentials.json")]
    assert active_lines, "SYNC_ACTIVE=1 must push the active creds"
    assert any(".credentials.json.sync-bak" in ln for ln in out.splitlines()), (
        "SYNC_ACTIVE=1 must back up each host's outgoing active first"
    )


def test_unsafe_account_dirname_is_skipped(tmp_path):
    claude_dir = _make_claude_dir(tmp_path, names=("good-dir",))
    bad = claude_dir / "manager-accounts" / "bad;name"  # ';' is a shell metacharacter
    bad.mkdir()
    (bad / ".credentials.json").write_text('{"organizationUuid":"org-bad"}')

    out = _dry_run(tmp_path, hosts="vps", claude_dir=claude_dir).stdout + \
        _dry_run(tmp_path, hosts="vps", claude_dir=claude_dir).stderr
    cmd_lines = [ln for ln in out.splitlines() if ln.startswith("DRY_RUN:")]
    assert not any("bad;name" in ln for ln in cmd_lines), "unsafe dir must never reach a remote command"
    assert any("good-dir" in ln for ln in cmd_lines), "safe dir still synced"


def test_whitespace_only_hosts_errors_not_silent_noop(tmp_path):
    r = _dry_run(tmp_path, hosts="   ")
    assert r.returncode == 1, "whitespace-only host list must error, not silently sync nothing"


def test_missing_snapshots_errors(tmp_path):
    claude_dir = tmp_path / ".claude"
    (claude_dir / "manager-accounts").mkdir(parents=True)  # empty → no snapshots
    r = _dry_run(tmp_path, claude_dir=claude_dir)
    assert r.returncode == 1


def test_real_run_error_path_continues_and_exits_nonzero(tmp_path):
    """Non-DRY_RUN with fake failing ssh/scp on PATH → exercises the real error branches:
    a host failure is logged, the loop continues, and the exit code is non-zero."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in ("ssh", "scp"):
        p = bindir / tool
        p.write_text("#!/usr/bin/env bash\nexit 7\n")
        p.chmod(0o755)
    claude_dir = _make_claude_dir(tmp_path)
    env = {
        **os.environ,
        "DRY_RUN": "0",
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "CLAUDE_DIR": str(claude_dir),
        "CLAUDE_FLEET_HOSTS": "vps vps2",
        "CLAUDE_FLEET_SYNC_LOG": str(tmp_path / "sync.log"),
    }
    r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    combined = r.stdout + r.stderr
    assert r.returncode != 0, "a failed host must yield a non-zero exit"
    assert "ERROR" in combined
    assert "vps" in combined and "vps2" in combined, "loop must continue past the first failed host"


def test_real_run_scp_failure_sets_nonzero_and_no_false_ok(tmp_path):
    """ssh (mkdir) succeeds but scp fails → exercises the scp-failure branch: host flagged
    (host_ok=0, rc=1), no false 'OK' logged. (The mkdir-failure path is covered above.)"""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "ssh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bindir / "scp").write_text("#!/usr/bin/env bash\nexit 7\n")
    (bindir / "ssh").chmod(0o755)
    (bindir / "scp").chmod(0o755)
    claude_dir = _make_claude_dir(tmp_path)
    env = {
        **os.environ,
        "DRY_RUN": "0",
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "CLAUDE_DIR": str(claude_dir),
        "CLAUDE_FLEET_HOSTS": "vps",
        "CLAUDE_FLEET_SYNC_LOG": str(tmp_path / "sync.log"),
    }
    r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    combined = r.stdout + r.stderr
    assert r.returncode != 0, "scp failure must yield a non-zero exit"
    assert "scp of snapshot" in combined, "the scp-failure branch must be reached + logged"
    assert "OK:" not in combined, "must not falsely claim OK when scp failed"


def test_real_run_chmod_belt_failure_is_warn_not_host_failure(tmp_path):
    """ssh succeeds for mkdir but FAILS for the find/chmod belt step; scp succeeds → the host
    still syncs OK (the belt-step failure is a non-fatal WARN, since scp -p already set 0600),
    and a host with no active-creds file must NOT be false-flagged (find matches nothing → 0)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # fail only on the find/chmod belt command; succeed for the mkdir command
    (bindir / "ssh").write_text('#!/usr/bin/env bash\ncase "$*" in *find*) exit 1;; *) exit 0;; esac\n')
    (bindir / "scp").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bindir / "ssh").chmod(0o755)
    (bindir / "scp").chmod(0o755)
    claude_dir = _make_claude_dir(tmp_path)
    env = {
        **os.environ,
        "DRY_RUN": "0",
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "CLAUDE_DIR": str(claude_dir),
        "CLAUDE_FLEET_HOSTS": "vps",
        "CLAUDE_FLEET_SYNC_LOG": str(tmp_path / "sync.log"),
    }
    r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    combined = r.stdout + r.stderr
    assert r.returncode == 0, "belt-step WARN must not fail the run (sync succeeded via scp -p)"
    assert "WARN" in combined and "belt-step" in combined, "belt failure surfaced as a WARN"
    assert "OK:" in combined, "host still reported OK"


def test_missing_classifier_pages_in_proactive_check():
    # F2-2 guard: proactive-check.sh must emit the anomaly in the ELSE of the classifier
    # `-f` guard (fail-CLOSED) — not the if-branch (which would be fail-open / dead code).
    src = (ROOT / "scripts/sysadmin/proactive-check.sh").read_text()
    m = re.search(
        r'-f "\$\(dirname "\$0"\)/keepalive-status\.sh".*?\belse\b.*?oauth_keepalive_classifier_missing',
        src,
        re.DOTALL,
    )
    assert m, "classifier-missing anomaly must be in the else-branch of the -f guard (fail-closed)"


def test_script_never_reads_cred_content_into_output():
    """Static guard: no line reads a credentials file's CONTENT into stdout/log — only scp
    ever touches the bytes. Catches a future `cat`/`jq` diagnostic leak the DRY_RUN tests can't."""
    reader_cmds = ("cat ", "jq ", "head ", "tail ", "grep ", "awk ", "printf ")
    for line in SCRIPT.read_text().splitlines():
        s = line.strip()
        if s.startswith("#") or "credentials.json" not in s:
            continue
        assert not any(c in s for c in reader_cmds), f"creds content must never be read into output: {s}"
