"""Behavior-contract tests for the `merge-request` mail kind (plan 2026-09-30-plan-1 T01a).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1,
§ Contract deltas, § Validation V7b, § U4 (O34 + the blocked-reason rule, W-8a6a5644).

Everything drives the REAL filesystem and a REAL scratch git repository — the merge-SHA
guard is only as good as the git answers it reads, so none of them is stubbed. The caller is
simulated through CLAUDE_AGENT (conftest already pins CLAUDE_CODE_SESSION_ID unset and the
identity store to an empty tmp file, so nothing else can resolve a name).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

_MAIL_PY = Path(__file__).resolve().parent.parent / "scripts" / "mail.py"


def _load_mail():
    spec = importlib.util.spec_from_file_location("fabrik_mail_mr", _MAIL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mail = _load_mail()

OWNER = "infra"  # the addressee (a hub beat: the shared `fabrik` mailbox only accepts those)
OTHER = "fleet"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    mail_root = tmp_path / "mail"
    opt_root = tmp_path / "opt"
    mail_root.mkdir()
    for name in ("alpha", "beta"):
        hook = opt_root / name / ".claude" / "hooks" / "mail_notify.py"
        hook.parent.mkdir(parents=True)
        hook.write_text("# stub hook\n")
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(opt_root))
    monkeypatch.setattr(mail, "_is_hub_repo", lambda: False)
    monkeypatch.setattr(mail, "_mail_store", lambda *a, **k: None)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return {"mail_root": mail_root}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A scratch repo: master with one commit, branch `feat` one commit ahead (the head)."""
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(k, "t")
    for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "t@example.invalid")
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    (r / "a.txt").write_text("a\n")
    _git(r, "add", "a.txt")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "checkout", "-q", "-b", "feat")
    (r / "b.txt").write_text("b\n")
    _git(r, "add", "b.txt")
    _git(r, "commit", "-q", "-m", "feature work")
    head = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-q", "master")
    monkeypatch.chdir(r)
    return {"path": r, "head": head}


def _send_mr(head: str = "0" * 40, agent: str = OWNER, ack: str | None = None) -> str:
    body = (
        "branch: feat\n"
        f"head: {head}\n"
        "base: master\n"
        "item: none\n"
        "review: docs/review.md\n"
        "doorbell: none\n"
        "sent: 2026-10-01T00:00:00+00:00\n"
    )
    p = mail.send(
        to="fabrik", to_agent=agent, kind="merge-request", body=body, frm="alpha", ack=ack
    )
    return p.name.removesuffix(".md")


def _inbox(env, mid: str) -> Path:
    return env["mail_root"] / "fabrik" / "inbox" / f"{mid}.md"


def _archive(env, mid: str) -> Path:
    return env["mail_root"] / "fabrik" / "archive" / f"{mid}.md"


def test_tests_the_worktree_copy_of_mail_py():
    """W-83ff5917: a shared venv can resolve the MAIN checkout — prove the module under test."""
    print("mail under test:", mail.__file__)
    assert Path(mail.__file__).resolve() == _MAIL_PY


# --- row 1: ack default -------------------------------------------------------------------
def test_cli_send_merge_request_defaults_to_ack_required(env, tmp_path, capsys):
    body = tmp_path / "body.txt"
    body.write_text("branch: feat\nhead: " + "0" * 40 + "\nbase: master\n")
    rc = mail.main(
        [
            "send",
            "--to",
            "fabrik",
            "--to-agent",
            OWNER,
            "--kind",
            "merge-request",
            "--from",
            "alpha",
            "--body-file",
            str(body),
        ]
    )
    assert rc == 0, capsys.readouterr()
    delivered = Path(capsys.readouterr().out.strip().splitlines()[-1])
    header = delivered.read_text(encoding="utf-8").split("\n---", 1)[0]
    assert "\nack: required" in header, header
    assert "\nkind: merge-request" in header, header


# --- row 2: addressee guard -----------------------------------------------------------------
def test_claim_and_ack_by_a_non_addressee_are_refused(env, monkeypatch):
    mid = _send_mr()
    for caller in (OTHER, None):  # a different agent, and an unresolvable caller (fail closed)
        if caller is None:
            monkeypatch.delenv("CLAUDE_AGENT", raising=False)
        else:
            monkeypatch.setenv("CLAUDE_AGENT", caller)
        with pytest.raises(mail.MailRefusedError, match="addressed to"):
            mail.claim(mid, "fabrik")
        assert _inbox(env, mid).is_file(), "a refused claim must leave the message in the inbox"
        with pytest.raises(mail.MailRefusedError, match="addressed to"):
            mail.ack(mid, "fabrik", disposition="wontfix")
        assert _inbox(env, mid).is_file(), "a refused ack must leave the message in the inbox"
        assert not _archive(env, mid).exists()
    # the addressee claims; a non-addressee's ack of the CLAIMED message is refused too
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    mail.claim(mid, "fabrik")
    monkeypatch.setenv("CLAUDE_AGENT", OTHER)
    with pytest.raises(mail.MailRefusedError, match="addressed to"):
        mail.ack(mid, "fabrik", disposition="wontfix")
    assert "disposition:" not in _archive(env, mid).read_text(encoding="utf-8")


def test_cli_claim_by_non_addressee_exits_refused(env, monkeypatch, capsys):
    mid = _send_mr()
    monkeypatch.setenv("CLAUDE_AGENT", OTHER)
    assert mail.main(["claim", mid, "--repo", "fabrik"]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert _inbox(env, mid).is_file()


# --- row 3: ack done needs a real merge SHA ------------------------------------------------
def test_ack_done_requires_a_real_merge_of_the_head(env, repo, monkeypatch):
    r, head = repo["path"], repo["head"]
    mid = _send_mr(head=head)
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)

    def refused(sha, match):
        with pytest.raises(mail.MailRefusedError, match=match):
            mail.ack(mid, "fabrik", disposition="done", merge_sha=sha)
        assert _inbox(env, mid).is_file(), f"refusal ({match}) must leave the message in place"

    # 1. no --merge-sha at all
    refused(None, "--merge-sha")
    # 2. an unknown object
    refused("f" * 40, "not a commit")
    # 3. a real merge of the head naming the request — but on a side branch, not in base
    _git(r, "checkout", "-q", "-b", "side")
    _git(r, "merge", "-q", "--no-ff", "-m", f"merge feat ({mid})", "feat")
    stray = _git(r, "rev-parse", "HEAD")
    _git(r, "checkout", "-q", "master")
    refused(stray, "not an ancestor of base")
    # 4. an EMPTY commit on base naming the request — no head in its history (O34)
    _git(r, "commit", "-q", "--allow-empty", "-m", f"merge-request {mid} done")
    empty = _git(r, "rev-parse", "HEAD")
    refused(empty, "head")
    # 5. the real merge commit, but its message does not carry the request id
    _git(r, "merge", "-q", "--no-ff", "-m", "merge feat", "feat")
    anonymous = _git(r, "rev-parse", "HEAD")
    refused(anonymous, "request id")
    # 6. the real merge commit naming the request — accepted, and the SHA is recorded
    _git(r, "reset", "-q", "--hard", empty)
    _git(r, "merge", "-q", "--no-ff", "-m", f"merge feat ({mid})", "feat")
    good = _git(r, "rev-parse", "HEAD")
    arch = mail.ack(mid, "fabrik", disposition="done", merge_sha=good[:12])
    text = arch.read_text(encoding="utf-8")
    assert "disposition: done" in text
    assert f"merge-sha: {good}" in text, "the FULL merge SHA is recorded on the ack line"
    assert mail._ACK_LINE.search(text), "the ack line still parses as resolved"


def test_cli_ack_done_passes_merge_sha(env, repo, monkeypatch, capsys):
    r, head = repo["path"], repo["head"]
    mid = _send_mr(head=head)
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    assert mail.main(["ack", mid, "--repo", "fabrik"]) == 2  # done is the default disposition
    assert _inbox(env, mid).is_file()
    _git(r, "merge", "-q", "--no-ff", "-m", f"merge feat ({mid})", "feat")
    good = _git(r, "rev-parse", "HEAD")
    assert mail.main(["ack", mid, "--repo", "fabrik", "--merge-sha", good]) == 0
    assert f"merge-sha: {good}" in _archive(env, mid).read_text(encoding="utf-8")


# --- row 4: blocked needs a reason ------------------------------------------------------------
def test_ack_blocked_requires_a_reason(env, monkeypatch):
    mid = _send_mr()
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    for reason in (None, "", "   "):
        with pytest.raises(mail.MailRefusedError, match="--reason"):
            mail.ack(mid, "fabrik", disposition="blocked", reason=reason)
        assert _inbox(env, mid).is_file()
    arch = mail.ack(
        mid, "fabrik", disposition="blocked", reason="step (c) merge conflict\nin a.txt"
    )
    text = arch.read_text(encoding="utf-8")
    assert "reason: step (c) merge conflict in a.txt · disposition: blocked" in text, text
    assert mail._ACK_LINE.search(text)


def test_cli_ack_blocked_writes_the_reason(env, monkeypatch):
    mid = _send_mr()
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    assert mail.main(["ack", mid, "--repo", "fabrik", "--disposition", "blocked"]) == 2
    assert _inbox(env, mid).is_file()
    assert (
        mail.main(
            ["ack", mid, "--repo", "fabrik", "--disposition", "blocked", "--reason", "gate red"]
        )
        == 0
    )
    assert "reason: gate red" in _archive(env, mid).read_text(encoding="utf-8")


def test_ack_wontfix_requires_a_reason(env, monkeypatch):
    """A wontfix of a merge-request is a refusal, and a refusal carries its reason (§ The delta 5(h))."""
    mid = _send_mr()
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    for reason in (None, "", " \t "):
        with pytest.raises(mail.MailRefusedError, match="--reason"):
            mail.ack(mid, "fabrik", disposition="wontfix", reason=reason)
        assert _inbox(env, mid).is_file()
    arch = mail.ack(mid, "fabrik", disposition="wontfix", reason="not ours: fleet's branch")
    assert "reason: not ours: fleet's branch · disposition: wontfix" in arch.read_text(
        encoding="utf-8"
    )


def _crash_mid_ack(env, mid: str) -> Path:
    """Simulate an ack that died between `rename(dst, win)` and the rename back: the message
    sits ONLY in a stale window (older than the 60 s sweep threshold)."""
    win = env["mail_root"] / "fabrik" / "archive" / f"{mid}.md.resolving.999999"
    os.rename(_archive(env, mid), win)
    old = win.stat().st_mtime - 1000
    os.utime(win, (old, old))
    return win


def test_guards_hold_when_the_message_sits_in_a_stale_window(env, monkeypatch):
    """S1: a claim-then-crash leaves the message only in `archive/<id>.md.resolving.<pid>`; the
    guards must judge it there too, not skip it and let the sweep restore-then-ack it."""
    mid = _send_mr()
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)
    mail.claim(mid, "fabrik")
    win = _crash_mid_ack(env, mid)
    monkeypatch.setenv("CLAUDE_AGENT", OTHER)  # a non-addressee, no --merge-sha
    with pytest.raises(mail.MailRefusedError, match="addressed to"):
        mail.ack(mid, "fabrik", disposition="done")
    monkeypatch.setenv("CLAUDE_AGENT", OWNER)  # the addressee, still without --merge-sha
    with pytest.raises(mail.MailRefusedError, match="--merge-sha"):
        mail.ack(mid, "fabrik", disposition="done")
    with pytest.raises(mail.MailRefusedError, match="--reason"):
        mail.ack(mid, "fabrik", disposition="blocked")
    assert win.is_file() and not _archive(env, mid).exists(), "a refusal moves nothing"
    # a guarded ack by the addressee still recovers the window and resolves it
    arch = mail.ack(mid, "fabrik", disposition="blocked", reason="step (b) preflight")
    assert "reason: step (b) preflight · disposition: blocked" in arch.read_text(encoding="utf-8")
    assert not win.exists()


# --- row 5: every other kind is unchanged -----------------------------------------------------
@pytest.mark.parametrize("kind", ["request", "finding", "relay", "upstream-feedback"])
def test_other_kinds_claim_and_ack_are_unchanged(env, monkeypatch, kind):
    for caller in (OTHER, None):
        if caller is None:
            monkeypatch.delenv("CLAUDE_AGENT", raising=False)
        else:
            monkeypatch.setenv("CLAUDE_AGENT", caller)
        body = "WHO: a\nWHAT: b\nWHEN: c\nWHERE: d\nWHY: e\nHOW: f\nSYSTEMIC: g\n"
        p = mail.send(to="fabrik", to_agent=OWNER, kind=kind, body=body, frm="alpha")
        mid = p.name.removesuffix(".md")
        mail.claim(mid, "fabrik")  # a non-addressee / unresolved caller may claim other kinds
        arch = mail.ack(mid, "fabrik", disposition="done")  # no --merge-sha needed
        assert "disposition: done" in arch.read_text(encoding="utf-8")
        p2 = mail.send(to="fabrik", to_agent=OWNER, kind=kind, body=body, frm="alpha")
        arch2 = mail.ack(p2.name.removesuffix(".md"), "fabrik", disposition="blocked")
        assert "disposition: blocked" in arch2.read_text(encoding="utf-8")  # no --reason needed


def test_merge_sha_on_another_kind_is_refused(env):
    p = mail.send(to="fabrik", to_agent=OWNER, kind="request", body="x", frm="alpha")
    mid = p.name.removesuffix(".md")
    with pytest.raises(mail.MailRefusedError, match="merge-request"):
        mail.ack(mid, "fabrik", disposition="done", merge_sha="abc")
    assert _inbox(env, mid).is_file()
