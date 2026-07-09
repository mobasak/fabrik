# AFTER-EDIT: none
"""Tests for claude_rotate — usage-limit detection + bounded, no-loop, N-account rotation.

The highest-risk behaviour in the sysadmin-rotation plan (Phase A): the
quota-detect → rotate → retry decision. A wrong branch here either burns a standby
account on a dead-creds 401 or never recovers from a real usage-limit; an unbounded
loop exhausts every account. These tests pin that control flow for N accounts
(mob/ob/can/…). ``subprocess.run``, ``_list_accounts``, ``_active_account`` and
``_rotate_active_account`` (the filesystem swap) are mocked so the suite is
hermetic (no dependence on the real ``~/.claude``); the real code under test is the
regex matching and the rotation-count / retry control flow.
"""

import json
import os
import pathlib
import subprocess
import time

import claude_rotate  # co-located; pytest prepends this dir to sys.path

# Grounded usage-limit renders (claude-auto-retry README + Anthropic errors docs, 2026-07-07)
USAGE_LIMIT_STRINGS = [
    "Claude usage limit reached. Resets at 3pm",
    "You've hit your weekly limit · resets 3pm",
    "You've hit your session limit · resets 3:45pm",
    "You've hit your Opus limit · resets 3:45pm",
    "5-hour limit reached - resets 3pm",
    "You're out of extra usage · resets 3pm",
]
NON_LIMIT_STRINGS = [
    "401 Invalid authentication credentials",
    "Everything succeeded, here is your answer.",
    "",
]


def _cp(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=["claude"], returncode=rc, stdout=stdout, stderr=stderr)


def _accounts(*names):
    return [pathlib.Path("/fake/manager-accounts") / n for n in names]


def _walk_rotator(order, log):
    """Fake _rotate_active_account: return the first name in *order* not already in avoid,
    honouring the real signature (rotates to an untried OTHER account)."""

    def _rot(avoid=frozenset()):
        for n in order:
            if n not in avoid:
                log.append(n)
                return n
        return None

    return _rot


def test_is_usage_limit_matches_all_grounded():
    for s in USAGE_LIMIT_STRINGS:
        assert claude_rotate.is_usage_limit(s), f"should match: {s!r}"


def test_is_usage_limit_rejects_401_and_benign():
    for s in NON_LIMIT_STRINGS:
        assert not claude_rotate.is_usage_limit(s), f"should NOT match: {s!r}"


def test_is_auth_401_matches_only_the_401():
    assert claude_rotate.is_auth_401("401 Invalid authentication credentials")
    assert not claude_rotate.is_auth_401("You've hit your session limit · resets 3pm")
    assert not claude_rotate.is_auth_401(
        "all good, line 401 of the file"
    )  # bare '401' is not an auth error


def test_run_claude_rotates_once_on_limit_then_ok(monkeypatch):
    outputs = [
        _cp(stdout="You've hit your session limit · resets 3:45pm", rc=1),
        _cp(stdout='{"result":"ok"}', rc=0),
    ]
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return outputs[len(calls) - 1]

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], rotations))

    r = claude_rotate.run_claude(
        ["claude", "-p", "hi"], timeout=120, cwd="/opt/fabrik", env={"X": "1"}
    )

    assert r.returncode == 0 and "ok" in r.stdout
    assert len(rotations) == 1, "exactly one rotation to the other account"
    assert len(calls) == 2, "original call + one retry"


def test_run_claude_never_rotates_on_401(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stderr="401 Invalid authentication credentials", rc=1)

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], rotations))

    r = claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert r.returncode == 1 and "401" in r.stderr
    assert len(rotations) == 0, "dead creds → alert path, never rotate"
    assert len(calls) == 1, "no retry on 401"


def test_run_claude_rotates_on_limit_string_regardless_of_exit_code(monkeypatch):
    # DELIBERATE: rotation triggers on the usage-limit STRING regardless of exit code — never
    # missing a real limit is the core guarantee, and Claude's exit code on a limit isn't
    # reliably known. The accepted cost is a bounded false-positive when a *successful* answer
    # (rc 0) quotes a limit phrase: it rotates (bounded by the account count), never loops.
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="Claude usage limit reached. Resets at 3pm", rc=0)

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], rotations))

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(rotations) == 1, "a limit string rotates even at rc 0 (never-miss); bounded to N-1"
    assert len(calls) == 2, "original + one retry, then the bound stops it (no loop)"


def test_run_claude_two_accounts_bounded_no_loop(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="You've hit your session limit · resets 3pm", rc=1)

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], rotations))

    r = claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(rotations) == 1, "2 accounts → at most one rotation, no loop"
    assert len(calls) == 2, "original + exactly one retry, then give up"
    assert claude_rotate.is_usage_limit(r.stdout), "returns the (still-limited) retry result"


def test_run_claude_three_accounts_walks_each_other_once(monkeypatch):
    """N-account support: mob active + ob + can all limited → rotate through ob AND can
    (each other account exactly once), 2 rotations, 3 attempts, then stop — never loops."""
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="You've hit your session limit · resets 3pm", rc=1)

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob", "can"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(
        claude_rotate, "_rotate_active_account", _walk_rotator(["ob", "can"], rotations)
    )

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert rotations == ["ob", "can"], "tried both OTHER accounts, each once, in order"
    assert len(calls) == 3, "original + 2 retries (one per other account)"


def test_run_claude_three_accounts_stops_at_first_ok(monkeypatch):
    """3 accounts, second attempt succeeds → exactly one rotation, no further walk."""
    outputs = [
        _cp(stdout="You've hit your session limit · resets 3pm", rc=1),
        _cp(stdout='{"result":"ok"}', rc=0),
    ]
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return outputs[len(calls) - 1]

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob", "can"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(
        claude_rotate, "_rotate_active_account", _walk_rotator(["ob", "can"], rotations)
    )

    r = claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert r.returncode == 0 and "ok" in r.stdout
    assert rotations == ["ob"], "stopped at first working account — did not walk to can"
    assert len(calls) == 2


def test_run_claude_passes_cwd_and_env_through(monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen.update(kw)
        return _cp(stdout="ok", rc=0)

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    claude_rotate.run_claude(
        ["claude", "-p", "x"],
        timeout=99,
        cwd="/opt/fabrik",
        env={"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
    )
    assert seen["cwd"] == "/opt/fabrik"
    assert seen["env"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert seen["timeout"] == 99


# --- control-flow branches the mocked suite above doesn't exercise -------------------


def test_run_claude_401_wins_over_usage_limit(monkeypatch):
    """Output that is BOTH a usage-limit render AND a 401 → the 401 guard must suppress
    rotation (dead creds can't be fixed by rotating). Exercises the `is_auth_401` operand
    that a pure-401 string never reaches (is_usage_limit is already False there)."""
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(
            stdout="hit your session limit · resets 3pm\n401 Invalid authentication credentials",
            rc=1,
        )

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], rotations))

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(rotations) == 0, "401 present → never rotate, even alongside a usage-limit string"
    assert len(calls) == 1, "no retry when a 401 is in the output"


def test_run_claude_single_account_never_rotates(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="hit your session limit · resets 3pm", rc=1)

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob"))  # 1 account

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(calls) == 1, "0/1 account → nothing to rotate to, early return"


def test_run_claude_active_not_in_snapshots_tries_all_n(monkeypatch):
    """start is None (active org matches no snapshot — e.g. an account whose snapshot
    isn't captured yet): the bound is N, so BOTH snapshots are tried, not N-1."""
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="hit your session limit · resets 3pm", rc=1)

    rotations = []
    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(
        claude_rotate, "_active_account", lambda: None
    )  # active not among snapshots
    monkeypatch.setattr(
        claude_rotate, "_rotate_active_account", _walk_rotator(["mob", "ob"], rotations)
    )

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(rotations) == 2, "start None → bound is N, both snapshots tried"
    assert len(calls) == 3


def test_run_claude_gives_up_when_rotator_returns_none(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append(kw)
        return _cp(stdout="hit your session limit · resets 3pm", rc=1)

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob", "can"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", lambda avoid=frozenset(): None)

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})

    assert len(calls) == 1, "rotator returns None (no untried account) → break, no retry"


def test_run_claude_preserves_piped_stdin_across_rotation(monkeypatch):
    # A piped-stdin caller (proactive-check.sh `<<< "$CONTEXT"`) must have its context
    # re-supplied on the rotation RETRY. A REAL pipe (one-shot: a 2nd read returns "") makes
    # this load-bearing — a regression that re-read stdin per attempt would show ["CTX", ""].
    r_fd, w_fd = os.pipe()
    os.write(w_fd, b"ANOMALY-CONTEXT")
    os.close(w_fd)
    monkeypatch.setattr(claude_rotate.sys, "stdin", os.fdopen(r_fd, "r"))
    outputs = [
        _cp(stdout="You've hit your session limit · resets 3pm", rc=1),
        _cp(stdout='{"result":"ok"}', rc=0),
    ]
    seen_input = []

    def fake_run(argv, **kw):
        seen_input.append(kw.get("input"))
        return outputs[len(seen_input) - 1]

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])
    monkeypatch.setattr(claude_rotate, "_rotate_active_account", _walk_rotator(["ob"], []))

    claude_rotate.run_claude(["claude", "-p", "x"], timeout=1, cwd="/x", env={}, buffer_stdin=True)

    assert seen_input == ["ANOMALY-CONTEXT", "ANOMALY-CONTEXT"], (
        f"stdin must be buffered ONCE + re-supplied on the retry, not lost; got {seen_input}"
    )


def test_run_claude_does_not_read_a_tty_stdin(monkeypatch):
    class _Tty:
        def isatty(self):
            return True

        def read(self):
            raise AssertionError("must not read a tty/interactive stdin")

    monkeypatch.setattr(claude_rotate.sys, "stdin", _Tty())
    seen = []

    def fake_run(argv, **kw):
        seen.append(kw.get("input"))
        return _cp(stdout="ok", rc=0)

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={}, buffer_stdin=True)

    assert seen == [None], "a tty stdin must not be read (input=None)"


def test_read_piped_stdin_bounded_on_never_eof(monkeypatch):
    # partial data but the write end stays OPEN (no EOF): must return the partial data within
    # the budget, NOT block forever (the docstring's bounded-read claim).
    r_fd, w_fd = os.pipe()
    os.write(w_fd, b"PARTIAL")  # data written, write end deliberately left open
    monkeypatch.setattr(claude_rotate.sys, "stdin", os.fdopen(r_fd, "r"))
    t0 = time.monotonic()
    out = claude_rotate._read_piped_stdin(max_wait_s=0.3)
    elapsed = time.monotonic() - t0
    os.close(w_fd)
    assert out == "PARTIAL", f"must return the partial data; got {out!r}"
    assert elapsed < 1.5, f"must be bounded (returned in {elapsed:.2f}s), not block"


def test_read_piped_stdin_reassembles_bursty_producer(monkeypatch):
    # a producer writing in bursts with a gap > the select granularity must NOT be truncated
    # at the first burst (the `continue`-not-`break` fix) — reassemble until EOF, within budget.
    import threading

    r_fd, w_fd = os.pipe()

    def _produce():
        os.write(w_fd, b"BURST1-")
        time.sleep(0.25)  # gap larger than the 0.2s select poll granularity
        os.write(w_fd, b"BURST2")
        os.close(w_fd)  # EOF

    monkeypatch.setattr(claude_rotate.sys, "stdin", os.fdopen(r_fd, "r"))
    t = threading.Thread(target=_produce)
    t.start()
    out = claude_rotate._read_piped_stdin(max_wait_s=2.0)
    t.join()
    assert out == "BURST1-BURST2", f"bursty producer must reassemble, not truncate; got {out!r}"


def test_read_piped_stdin_none_on_idle_empty_pipe(monkeypatch):
    r_fd, w_fd = os.pipe()  # open, nothing written, no EOF
    monkeypatch.setattr(claude_rotate.sys, "stdin", os.fdopen(r_fd, "r"))
    out = claude_rotate._read_piped_stdin(max_wait_s=0.3)
    os.close(w_fd)
    assert out is None, "an idle empty pipe (no data ever ready) → None"


def test_run_claude_default_does_not_touch_stdin(monkeypatch):
    # The direct authoritative path (bot.py / aro-wake) leaves buffer_stdin=False → the shared
    # process stdin is NEVER read (no cross-thread read, no behavior change), even if piped.
    r_fd, w_fd = os.pipe()
    os.write(w_fd, b"SHOULD-NOT-BE-READ")
    os.close(w_fd)
    monkeypatch.setattr(claude_rotate.sys, "stdin", os.fdopen(r_fd, "r"))
    seen = []

    def fake_run(argv, **kw):
        seen.append(kw.get("input"))
        return _cp(stdout="ok", rc=0)

    monkeypatch.setattr(claude_rotate.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_rotate, "_list_accounts", lambda: _accounts("mob", "ob"))
    monkeypatch.setattr(claude_rotate, "_active_account", lambda: _accounts("mob")[0])

    claude_rotate.run_claude(["claude"], timeout=1, cwd="/x", env={})  # buffer_stdin defaults False

    assert seen == [None], "default path must NOT read/buffer stdin (input=None)"


# --- real-filesystem coverage of the security/atomicity swap (was fully mocked) -------


def _write_creds(path, org):
    path.write_text(
        json.dumps(
            {
                "claudeAiOauth": {"accessToken": "FAKE-" + org, "refreshToken": "FAKE"},
                "organizationUuid": org,
            }
        )
    )
    os.chmod(path, 0o600)


def _setup_fake_claude(tmp_path, monkeypatch, orgs):
    """Point claude_rotate's module paths at a throwaway ~/.claude under tmp_path."""
    claude_dir = tmp_path / ".claude"
    accounts_dir = claude_dir / "manager-accounts"
    accounts_dir.mkdir(parents=True)
    for name, org in orgs.items():
        d = accounts_dir / name
        d.mkdir()
        _write_creds(d / ".credentials.json", org)
    active = claude_dir / ".credentials.json"
    monkeypatch.setattr(claude_rotate, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(claude_rotate, "ACCOUNTS_DIR", accounts_dir)
    monkeypatch.setattr(claude_rotate, "ACTIVE_CREDS", active)
    monkeypatch.setattr(claude_rotate, "BACKUP_CREDS", claude_dir / ".credentials.json.prev")
    monkeypatch.setattr(claude_rotate, "ROTATE_LOCK", claude_dir / ".claude-rotate.lock")
    return claude_dir, accounts_dir, active


def test_rotate_real_fs_swaps_backs_up_and_stays_0600(tmp_path, monkeypatch):
    claude_dir, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")  # active = mob

    new = claude_rotate._rotate_active_account()

    assert new == "ob-dir", "rotated to the OTHER org's snapshot"
    assert claude_rotate._read_org(active) == "org-ob", "active is now the ob account"
    backup = claude_dir / ".credentials.json.prev"
    assert backup.exists() and claude_rotate._read_org(backup) == "org-mob", "outgoing backed up"
    assert oct(active.stat().st_mode & 0o777) == "0o600", "active stays 0600"
    assert oct(backup.stat().st_mode & 0o777) == "0o600", (
        "backup written 0600 (no world-readable window)"
    )
    assert not (claude_dir / ".credentials.json.tmp").exists(), "no leftover tmp"


def test_rotate_org_filter_excludes_active_and_avoid(tmp_path, monkeypatch):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")  # active = mob

    # avoid ob-dir → the only other account is excluded; mob is active-org (org filter) → no target
    assert claude_rotate._rotate_active_account(avoid=frozenset({"ob-dir"})) is None
    assert claude_rotate._read_org(active) == "org-mob", "active untouched when no eligible target"


def test_dir_fsync_failure_does_not_fail_rotation(tmp_path, monkeypatch):
    # the post-replace directory fsync is best-effort: a failure must NOT undo/fail a swap that
    # already completed. Inject the failure via the dir-fsync's O_RDONLY os.open.
    _, _, active = _setup_fake_claude(tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"})
    _write_creds(active, "org-mob")
    real_open = os.open

    def flaky_open(path, flags, *a, **k):
        if flags == os.O_RDONLY:  # the dir-fsync open (creds writes use O_WRONLY|O_CREAT|…)
            raise OSError("EIO on directory open")
        return real_open(path, flags, *a, **k)

    monkeypatch.setattr(claude_rotate.os, "open", flaky_open)

    new = claude_rotate._rotate_active_account()

    assert new == "ob-dir", "dir-fsync failure must not fail the (already-completed) rotation"
    assert claude_rotate._read_org(active) == "org-ob", "the atomic swap completed"


def test_rotate_fail_soft_on_fs_error_leaves_active_intact(tmp_path, monkeypatch):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")

    def boom(dst, data):
        raise OSError("disk full")

    monkeypatch.setattr(claude_rotate, "_secure_write", boom)

    assert claude_rotate._rotate_active_account() is None, "FS error → fail-soft, returns None"
    assert claude_rotate._read_org(active) == "org-mob", "active creds left intact on failure"


def test_rotate_fail_soft_at_replace_boundary_cleans_tmp(tmp_path, monkeypatch):
    """Inject the failure AT os.replace (the mutating step): active must stay intact and the
    leftover tmp creds copy must be cleaned up — stronger than a pre-replace injection."""
    claude_dir, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")

    def boom_replace(src, dst):
        raise OSError("EXDEV cross-device")

    monkeypatch.setattr(claude_rotate.os, "replace", boom_replace)

    assert claude_rotate._rotate_active_account() is None, "replace failure → fail-soft None"
    assert claude_rotate._read_org(active) == "org-mob", "active intact — replace never applied"
    assert not (claude_dir / ".credentials.json.tmp").exists(), "leftover tmp creds cleaned up"


# --- manual account-management CLI (WSL: switch account, then reload the workspace) --


def _write_profile(acc_dir, email):
    (acc_dir / "profile.json").write_text(json.dumps({"account": {"email_address": email}}))


def test_cli_list_marks_active(tmp_path, monkeypatch, capsys):
    _, accounts_dir, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")
    _write_profile(accounts_dir / "mob-dir", "mob@ocoron.com")

    rc = claude_rotate.main(["--list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "* mob-dir" in out and "ob-dir" in out
    assert "mob@ocoron.com" in out


def test_cli_switch_sets_active_and_prints_reload_hint(tmp_path, monkeypatch, capsys):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")

    rc = claude_rotate.main(["--switch", "ob"])  # prefix match → ob-dir
    out = capsys.readouterr().out

    assert rc == 0
    assert claude_rotate._read_org(active) == "org-ob"
    assert "Reload the VS Code workspace" in out


def test_cli_switch_unknown_account_errors_without_touching_active(tmp_path, monkeypatch):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")

    assert claude_rotate.main(["--switch", "nope"]) == 1
    assert claude_rotate._read_org(active) == "org-mob", "active unchanged on bad name"


def test_cli_next_cycles_to_other_account(tmp_path, monkeypatch, capsys):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"}
    )
    _write_creds(active, "org-mob")

    rc = claude_rotate.main(["--next"])

    assert rc == 0
    assert claude_rotate._read_org(active) == "org-ob"


def test_find_account_by_name_email_and_prefix(tmp_path, monkeypatch):
    _, accounts_dir, _ = _setup_fake_claude(
        tmp_path, monkeypatch, {"can-ocoron-com-s-organization": "org-can"}
    )
    _write_profile(accounts_dir / "can-ocoron-com-s-organization", "can@ocoron.com")

    assert (
        claude_rotate._find_account("can-ocoron-com-s-organization").name
        == "can-ocoron-com-s-organization"
    )
    assert claude_rotate._find_account("can@ocoron.com").name == "can-ocoron-com-s-organization"
    assert claude_rotate._find_account("can").name == "can-ocoron-com-s-organization"  # prefix
    assert claude_rotate._find_account("zzz") is None


def test_find_account_empty_and_ambiguous_prefix_return_none(tmp_path, monkeypatch):
    claude_rotate_setup = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "mob2-dir": "org-mob2"}
    )
    del claude_rotate_setup
    assert claude_rotate._find_account("") is None, "empty name never matches (no arbitrary pick)"
    assert claude_rotate._find_account("mob") is None, "ambiguous prefix → None, not arbitrary"
    assert claude_rotate._find_account("mob2").name == "mob2-dir", "unambiguous prefix resolves"


def test_account_email_tolerates_non_object_profile(tmp_path, monkeypatch):
    _, accounts_dir, _ = _setup_fake_claude(tmp_path, monkeypatch, {"mob-dir": "org-mob"})
    (accounts_dir / "mob-dir" / "profile.json").write_text('["not", "an", "object"]')
    assert claude_rotate._account_email(accounts_dir / "mob-dir") == "?", (
        "non-object JSON → '?', no crash"
    )


def test_account_email_non_dict_account_field_falls_back(tmp_path, monkeypatch):
    _, accounts_dir, _ = _setup_fake_claude(tmp_path, monkeypatch, {"mob-dir": "org-mob"})
    # `account` present but a plain string → inner-guard falls back to the top-level `email`
    (accounts_dir / "mob-dir" / "profile.json").write_text(
        '{"account": "plain@string", "email": "fallback@x.com"}'
    )
    assert claude_rotate._account_email(accounts_dir / "mob-dir") == "fallback@x.com"


def test_find_account_never_resolves_question_mark_sentinel(tmp_path, monkeypatch):
    # two profile-less accounts → both _account_email() == "?"; "?" must not match either
    _setup_fake_claude(tmp_path, monkeypatch, {"mob-dir": "org-mob", "ob-dir": "org-ob"})
    assert claude_rotate._find_account("?") is None, "the '?' sentinel never resolves an account"


def test_cli_switch_empty_or_ambiguous_errors_without_touching_active(tmp_path, monkeypatch):
    _, _, active = _setup_fake_claude(
        tmp_path, monkeypatch, {"mob-dir": "org-mob", "mob2-dir": "org-mob2"}
    )
    _write_creds(active, "org-mob")
    assert claude_rotate.main(["--switch", ""]) == 1, "empty target rejected"
    assert claude_rotate.main(["--switch", "mob"]) == 1, "ambiguous prefix rejected"
    assert claude_rotate._read_org(active) == "org-mob", (
        "active identity never changed on a bad switch"
    )
