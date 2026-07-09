# AFTER-EDIT: none
"""Tests for claude-run.sh — the unified Claude entrypoint: routes EVERY sysadmin claude
call through claude_rotate.py (usage-limit rotation) AS the operator account, so root cron
scripts and ozgur services share one credential home.

The direct (no-sudo) branch is exercised end-to-end (CLAUDE_OPERATOR_USER == the test user);
the root→operator sudo branch is exercised via a PATH-shimmed fake `sudo` that records its
argv; the CLAUDE_BIN fallback resolution is exercised with CLAUDE_BIN unset + a controlled PATH."""
import getpass
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/sysadmin/claude-run.sh"


def _framed_claude(tmp_path, rc=0):
    """A fake `claude` that frames EACH argv element as <A>…</A> so a test can count args
    and detect word-splitting (a split multiline arg would produce extra <A> blocks)."""
    fakebin = tmp_path / "fakeclaude"
    fakebin.write_text(f"#!/usr/bin/env bash\nprintf '<A>%s</A>\\n' \"$@\"\nexit {rc}\n")
    fakebin.chmod(0o755)
    return fakebin


def _run(tmp_path, args, rc=0, extra_env=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)  # no ~/.claude/manager-accounts → claude_rotate <2 accounts → no rotation
    env = {
        **os.environ,
        "CLAUDE_OPERATOR_USER": getpass.getuser(),  # == current user → the direct (no-sudo) branch
        "CLAUDE_BIN": str(_framed_claude(tmp_path, rc)),
        "HOME": str(home),
        "CLAUDE_ROTATE_PYTHON": "python3",
        **(extra_env or {}),
    }
    return subprocess.run(["bash", str(WRAPPER), *args], env=env, capture_output=True, text=True)


def test_syntax_valid():
    r = subprocess.run(["bash", "-n", str(WRAPPER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_args_pass_through_verbatim_no_word_splitting(tmp_path):
    # A multi-line --system-prompt value MUST stay ONE arg. Framed output lets us count args:
    # a `"$@"`→`$@` word-splitting regression would shatter the multiline value into 3 args.
    args = ["-p", "--model", "opus", "PROMPT-TEXT", "--system-prompt", "multi\nline\nprompt"]
    out = _run(tmp_path, args).stdout
    assert out.count("<A>") == len(args), f"arg count changed (word-splitting?); got {out!r}"
    assert "<A>multi\nline\nprompt</A>" in out, "the multi-line --system-prompt value must stay ONE arg"
    assert "<A>--system-prompt</A>\n<A>multi\nline\nprompt</A>" in out, "value must follow its flag intact"


def test_exit_code_passes_through(tmp_path):
    assert _run(tmp_path, ["-p", "x"], rc=0).returncode == 0
    assert _run(tmp_path, ["-p", "x"], rc=7).returncode == 7


def test_routes_through_claude_rotate(tmp_path):
    # functional: the framed output only appears if claude_rotate actually ran the fake claude
    assert "<A>-p</A>" in _run(tmp_path, ["-p", "ping"]).stdout
    assert "claude_rotate.py" in WRAPPER.read_text(), "wrapper routes through claude_rotate.py"


def test_generous_default_timeout_forwarded(tmp_path):
    # F3: the wrapper defaults CLAUDE_ROTATE_TIMEOUT to 300 (not claude_rotate's 120) and
    # forwards it via `env`, so a long analysis isn't newly cut off. Assert via the sudo argv.
    out = _sudo_argv(tmp_path, ["-p", "x"])
    assert "CLAUDE_ROTATE_TIMEOUT=300" in out, "default 300s must be forwarded"
    out99 = _sudo_argv(tmp_path, ["-p", "x"], extra_env={"CLAUDE_ROTATE_TIMEOUT": "99"})
    assert "CLAUDE_ROTATE_TIMEOUT=99" in out99, "an explicit override must be forwarded"


def _sudo_argv(tmp_path, args, extra_env=None):
    """Run the wrapper with CLAUDE_OPERATOR_USER != current user + a fake `sudo` on PATH that
    echoes its argv; return that argv text."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text("#!/usr/bin/env bash\nprintf 'SUDOARG:%s\\n' \"$@\"\n")
    (bindir / "sudo").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "CLAUDE_OPERATOR_USER": "operator-xyz",  # != current user → the sudo branch
        "CLAUDE_BIN": str(_framed_claude(tmp_path)),
        "CLAUDE_ROTATE_PYTHON": "python3",
        **(extra_env or {}),
    }
    return subprocess.run(["bash", str(WRAPPER), *args], env=env, capture_output=True, text=True).stdout


def test_root_branch_invokes_sudo_as_operator_with_args(tmp_path):
    out = _sudo_argv(tmp_path, ["-p", "--model", "opus", "hello"])
    # the sudo invocation: sudo -u operator-xyz -H env CLAUDE_ROTATE_TIMEOUT=… python3 <rotate> <bin> <args>
    for expect in ("SUDOARG:-u", "SUDOARG:operator-xyz", "SUDOARG:-H", "SUDOARG:env", "SUDOARG:-p", "SUDOARG:hello"):
        assert expect in out, f"{expect} missing from the sudo argv; got {out!r}"


def test_resolves_claude_bin_from_path_when_unset(tmp_path):
    # F4: with CLAUDE_BIN unset, the wrapper must resolve `claude` from PATH (command -v).
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "claude").write_text("#!/usr/bin/env bash\nprintf 'RESOLVED:%s\\n' \"$@\"\n")
    (bindir / "claude").chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_BIN"}
    env.update(
        {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "CLAUDE_OPERATOR_USER": getpass.getuser(),
            "HOME": str(home),
            "CLAUDE_ROTATE_PYTHON": "python3",
        }
    )
    r = subprocess.run(["bash", str(WRAPPER), "-p", "hi"], env=env, capture_output=True, text=True)
    assert "RESOLVED:-p" in r.stdout, f"must resolve claude from PATH when CLAUDE_BIN unset; got {r.stdout!r}"


def test_malformed_timeout_falls_back_not_crash(tmp_path):
    # C1: a non-integer CLAUDE_ROTATE_TIMEOUT must be sanitized to 300, not forwarded raw
    # (claude_rotate does int() → would crash). Assert via the sudo argv.
    out = _sudo_argv(tmp_path, ["-p", "x"], extra_env={"CLAUDE_ROTATE_TIMEOUT": "abc"})
    assert "CLAUDE_ROTATE_TIMEOUT=300" in out, "garbage timeout must fall back to 300"
    assert "CLAUDE_ROTATE_TIMEOUT=abc" not in out, "raw garbage must NOT be forwarded"


def test_direct_branch_actually_applies_timeout(tmp_path):
    # C2: prove the DIRECT branch forwards the timeout end-to-end — a fake claude that sleeps
    # longer than a low timeout must be killed by claude_rotate (non-zero exit), and complete
    # under a generous timeout.
    slow = tmp_path / "slowclaude"
    slow.write_text("#!/usr/bin/env bash\nsleep 3\necho done\n")
    slow.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    base = {
        **os.environ,
        "CLAUDE_OPERATOR_USER": getpass.getuser(),
        "CLAUDE_BIN": str(slow),
        "HOME": str(home),
        "CLAUDE_ROTATE_PYTHON": "python3",
    }
    timed_out = subprocess.run(
        ["bash", str(WRAPPER), "-p", "x"], env={**base, "CLAUDE_ROTATE_TIMEOUT": "1"},
        capture_output=True, text=True,
    )
    assert timed_out.returncode != 0, "a 1s timeout must kill the 3s fake claude (direct branch forwards it)"
    fast = subprocess.run(
        ["bash", str(WRAPPER), "-p", "x"], env={**base, "CLAUDE_ROTATE_TIMEOUT": "10"},
        capture_output=True, text=True,
    )
    assert fast.returncode == 0 and "done" in fast.stdout, "a 10s timeout must let the 3s fake claude finish"


def test_root_path_uses_sudo_as_operator_structurally():
    src = WRAPPER.read_text()
    assert 'sudo -u "$OPERATOR" -H' in src
    assert "id -un" in src


# --- Phase B: the 4 root cron scripts route their claude call through claude-run.sh -------

_ROOT_SCRIPTS = ["proactive-check.sh", "morning-report.sh", "weekly-security.sh", "monthly-backup-verify.sh"]
_HAVE_FALLBACK = ["morning-report.sh", "weekly-security.sh", "monthly-backup-verify.sh"]


def test_four_root_scripts_route_through_claude_run_not_bare_claude():
    for s in _ROOT_SCRIPTS:
        src = (ROOT / "scripts/sysadmin" / s).read_text()
        assert 'claude-run.sh" -p' in src, f"{s} must invoke claude via claude-run.sh"
        assert "$(claude -p" not in src, f"{s} still has a bare `claude -p` invocation"


def test_four_scripts_apprise_uses_fabrik_network_not_coolify():
    # The escalation transport must use the live docker network. `coolify` was renamed to
    # `fabrik` on 2026-05-31 (AGENTS.md) — a stale `--network coolify` makes the `docker run`
    # fail silently (2>/dev/null, exit unchecked), so the fail-closed escalation never delivers.
    for s in _ROOT_SCRIPTS:
        src = (ROOT / "scripts/sysadmin" / s).read_text()
        assert "--network coolify" not in src, f"{s} uses the removed 'coolify' docker network"
        assert "--network fabrik" in src, f"{s} must send Apprise via the 'fabrik' network"


def test_proactive_apprise_send_is_observable_on_failure():
    # the fail-closed escalation relies on Apprise actually delivering — a silent drop would
    # defeat it, so APPRISE_SEND must check the docker-run exit and log a failure.
    src = (ROOT / "scripts/sysadmin/proactive-check.sh").read_text()
    assert "if ! sudo docker run" in src, "APPRISE_SEND must check the docker-run exit (not swallow it)"
    assert "APPRISE_SEND FAILED" in src, "a delivery failure must be logged (observable)"


def test_four_root_scripts_syntax_valid():
    for s in _ROOT_SCRIPTS:
        r = subprocess.run(["bash", "-n", str(ROOT / "scripts/sysadmin" / s)], capture_output=True, text=True)
        assert r.returncode == 0, f"{s}: {r.stderr}"


def test_root_scripts_keep_their_claude_failed_fallback():
    # the wiring must not disturb the surrounding capture + failure-handling logic
    for s in _HAVE_FALLBACK:
        src = (ROOT / "scripts/sysadmin" / s).read_text()
        assert "Claude failed" in src, f"{s} lost its '⚠️ … Claude failed' fallback"
        assert '-z "$RESULT"' in src, f"{s} fallback must be gated on an empty RESULT"


def test_wrapper_runs_claude_from_operator_accessible_cwd_not_caller_cwd(tmp_path):
    # F#1 regression guard: a root cron job starts in /root (0700); the wrapper must cd to an
    # operator-accessible dir so claude_rotate's subprocess chdir doesn't PermissionError after
    # the UID switch. Prove claude runs from the operator home (or /tmp), NOT the caller's cwd.
    fakebin = tmp_path / "fc"
    fakebin.write_text("#!/usr/bin/env bash\necho \"CWD=$(pwd)\"\n")
    fakebin.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()
    op_home = os.path.expanduser(f"~{getpass.getuser()}")
    env = {
        **os.environ,
        "CLAUDE_OPERATOR_USER": getpass.getuser(),
        "CLAUDE_BIN": str(fakebin),
        "HOME": str(home),
        "CLAUDE_ROTATE_PYTHON": "python3",
    }
    r = subprocess.run(
        ["bash", str(WRAPPER), "-p", "x"], env=env, cwd=str(caller_cwd), capture_output=True, text=True
    )
    assert f"CWD={op_home}" in r.stdout or "CWD=/tmp" in r.stdout, f"claude must run from a safe cwd; got {r.stdout!r}"
    assert f"CWD={caller_cwd}" not in r.stdout, "must NOT inherit the caller's (maybe inaccessible) cwd"


def test_proactive_check_fails_closed_on_empty_claude_result():
    # F#1 fail-open fix: an empty RESULT (claude failed) must escalate, NOT be conflated with
    # the ALL_CLEAR verdict and silently dismiss the detected anomalies.
    src = (ROOT / "scripts/sysadmin/proactive-check.sh").read_text()
    assert 'if [ -z "$RESULT" ]; then' in src, "empty RESULT must be handled on its own"
    assert "Claude analysis FAILED" in src, "empty RESULT must escalate to the operator"
    assert '[ -z "$RESULT" ] || [ "$RESULT" = "ALL_CLEAR" ]' not in src, "the fail-open conflation must be gone"
