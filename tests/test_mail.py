"""Behavior-contract tests for scripts/mail.py (fabrik-mail store + protocol).

Watched-fail-first: the ★ risky behaviors (ULID lexical sort, O_EXCL publish
collision, star-topology refusal) are written to be seen RED before mail.py
exists, then GREEN once implemented. Every test drives the REAL filesystem
(tmp dirs, os.link, os.rename) — nothing mocked except that the digest's
alerting leg is stubbed hub-side (no real Telegram send).

mail.py is loaded by path (it lives in scripts/, not an installed package).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_MAIL_PY = Path(__file__).resolve().parent.parent / "scripts" / "mail.py"


def _load_mail():
    spec = importlib.util.spec_from_file_location("fabrik_mail", _MAIL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mail = _load_mail()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A sandboxed mail root + /opt base with a couple of valid recipients.

    Layout under tmp:
      mail_root/                      -> FABRIK_MAIL_ROOT
      opt/<name>/.claude/hooks/mail_notify.py  -> makes <name> a valid recipient
    `fabrik` and `fabrik-lib` are hardcoded-valid (no hook needed).
    """
    mail_root = tmp_path / "mail"
    opt_root = tmp_path / "opt"
    mail_root.mkdir()
    opt_root.mkdir()
    # give project 'alpha' and 'beta' the surfacing hook -> valid recipients
    for name in ("alpha", "beta"):
        hook = opt_root / name / ".claude" / "hooks" / "mail_notify.py"
        hook.parent.mkdir(parents=True)
        hook.write_text("# stub hook\n")
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(opt_root))
    return {"mail_root": mail_root, "opt_root": opt_root}


# ---------------------------------------------------------------------------
# ★ RISKY #1 — ULID lexical sort == value order (Crockford, NOT base64.b32)
# ---------------------------------------------------------------------------
def test_ulid_lexical_order_equals_time_order(env, monkeypatch):
    """Ids minted at ascending timestamps must sort ascending lexically.

    The property that base64.b32encode would BREAK (its 2-7 digits sort before
    A-Z yet encode the high values) — so this proves the Crockford map is used.
    """
    ids = []
    fake_ns = [1_000, 2_000, 3_000, 10_000, 1_000_000, 999_999_999_000]
    for ns in fake_ns:
        monkeypatch.setattr(mail.time, "time_ns", lambda ns=ns: ns * 1_000_000)
        ids.append(mail._ulid())
    assert ids == sorted(ids), "ULIDs minted in time order must sort lexically"
    # every char is in the Crockford alphabet (no I/L/O/U, no lowercase)
    for uid in ids:
        assert set(uid) <= set(mail._CROCKFORD), uid


def test_ulid_no_collision_same_ms(env, monkeypatch):
    """Two ids minted in the SAME millisecond differ (80 random bits)."""
    monkeypatch.setattr(mail.time, "time_ns", lambda: 1234 * 1_000_000)
    a, b = mail._ulid(), mail._ulid()
    assert a != b


# ---------------------------------------------------------------------------
# ★ RISKY #2 — publish is tmp-then-O_EXCL: a second publish of an existing id raises
# ---------------------------------------------------------------------------
def test_publish_exclusive_create_no_overwrite(env):
    inbox = env["mail_root"] / "fabrik" / "inbox"
    p1 = mail.send(to="fabrik", kind="finding", body="first", frm="alpha")
    assert p1.exists()
    original = p1.read_text()
    # force the same id -> second publish must raise, never overwrite
    with pytest.raises(FileExistsError):
        mail._publish(inbox, p1.name.removesuffix(".md"), "different body")
    assert p1.read_text() == original  # untouched
    # a stray orphan .tmp is never surfaced (dot-prefixed)
    assert not list(inbox.glob("*.md.tmp"))


# ---------------------------------------------------------------------------
# ★ RISKY #3 — star topology: project -> project (both non-hub) is refused
# ---------------------------------------------------------------------------
def test_star_topology_refuses_project_to_project(env):
    # beta is a VALID recipient (has the hook), so this refusal is star-only
    with pytest.raises(mail.MailRefusedError) as ei:
        mail.send(to="beta", kind="finding", body="hi", frm="alpha")
    assert "star" in str(ei.value).lower()
    # nothing written
    assert not (env["mail_root"] / "beta").exists()


def test_star_allows_hub_edges(env):
    # project -> hub, and hub -> project, both allowed
    assert mail.send(to="fabrik", kind="finding", body="up", frm="alpha").exists()
    assert mail.send(to="alpha", kind="request", body="down", frm="fabrik").exists()
    # fabrik-lib is a first-class node (hub edge)
    assert mail.send(to="fabrik-lib", kind="upstream-feedback", body="x", frm="alpha").exists()


# ---------------------------------------------------------------------------
# recipient validation — machinery presence
# ---------------------------------------------------------------------------
def test_send_refuses_unknown_recipient_no_dir_created(env):
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="ghost", kind="finding", body="x", frm="fabrik")
    assert not (env["mail_root"] / "ghost").exists()


def test_send_creates_recipient_inbox_lazily(env):
    assert not (env["mail_root"] / "alpha").exists()
    mail.send(to="alpha", kind="request", body="x", frm="fabrik")
    assert (env["mail_root"] / "alpha" / "inbox").is_dir()


# ---------------------------------------------------------------------------
# secret refusal / warn
# ---------------------------------------------------------------------------
def test_send_refuses_high_confidence_secret(env):
    body = "here is the key\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY\n"
    with pytest.raises(mail.MailRefusedError) as ei:
        mail.send(to="fabrik", kind="finding", body=body, frm="alpha")
    assert "secret" in str(ei.value).lower()
    # nothing written
    assert (
        not any((env["mail_root"] / "fabrik").rglob("*.md"))
        if (env["mail_root"] / "fabrik").exists()
        else True
    )


def test_send_refuses_pem_header(env):
    # split the marker so the detect-private-key pre-commit hook doesn't match a
    # literal header in the test source; the runtime string is the full header.
    header = "-----BEGIN RSA " + "PRIVATE KEY-----"
    body = f"{header}\nMIIEabc...\n"
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="fabrik", kind="finding", body=body, frm="alpha")


def test_send_warns_low_confidence_but_delivers(env, capsys):
    # a lone 'password' word is low-confidence: warn, still send
    p = mail.send(to="fabrik", kind="finding", body="remember your password policy", frm="alpha")
    assert p.exists()
    err = capsys.readouterr().err.lower()
    assert "warn" in err or "low-confidence" in err


# ---------------------------------------------------------------------------
# size cap
# ---------------------------------------------------------------------------
def test_send_refuses_oversized_body(env):
    big = "x" * (64 * 1024 + 1)
    with pytest.raises(mail.MailRefusedError) as ei:
        mail.send(to="fabrik", kind="finding", body=big, frm="alpha")
    assert "64" in str(ei.value) or "cap" in str(ei.value).lower()


def test_send_allows_body_at_cap(env):
    ok = "x" * (64 * 1024)
    assert mail.send(to="fabrik", kind="finding", body=ok, frm="alpha").exists()


# ---------------------------------------------------------------------------
# ack / requeue / digest
# ---------------------------------------------------------------------------
def test_ack_moves_to_archive_and_appends_line(env):
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")  # ack:required by kind
    mid = p.name.removesuffix(".md")
    arch = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert arch.exists() and not p.exists()
    assert "acked-by: fabrik" in arch.read_text()
    assert "disposition: done" in arch.read_text()


def test_ack_loser_gets_enoent(env):
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    with pytest.raises(FileNotFoundError):
        mail.ack(msg_id=mid, repo="fabrik", disposition="done")  # already claimed


def test_ack_required_default_by_kind(env):
    req = mail.send(to="fabrik", kind="request", body="x", frm="alpha")
    fnd = mail.send(to="fabrik", kind="finding", body="y", frm="alpha")
    assert "ack: required" in req.read_text()
    assert "ack: no" in fnd.read_text()


def test_digest_counts_claimed_without_ackline_as_unacked(env):
    p = mail.send(to="fabrik", kind="request", body="x", frm="alpha")
    mid = p.name.removesuffix(".md")
    # simulate a crashed claimer: move to archive with NO acked-by line
    arch_dir = env["mail_root"] / "fabrik" / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    os.rename(p, arch_dir / p.name)
    d = mail.digest(days=0)
    assert d["unacked"] >= 1
    # requeue puts it back in inbox for re-processing
    back = mail.requeue(msg_id=mid, repo="fabrik")
    assert back.exists() and back.parent.name == "inbox"


def test_digest_never_counts_ack_no(env):
    mail.send(to="fabrik", kind="finding", body="fyi", frm="alpha")  # ack:no
    d = mail.digest(days=0)
    assert d["unacked"] == 0


def test_digest_counts_unclaimed_required_over_threshold(env, monkeypatch):
    # an old ack:required still in inbox is unacked
    monkeypatch.setattr(mail.time, "time_ns", lambda: 1_000 * 1_000_000)  # ancient ts
    mail.send(to="fabrik", kind="request", body="x", frm="alpha")
    d = mail.digest(days=3)
    assert d["unacked"] >= 1


# ---------------------------------------------------------------------------
# malformed quarantine + digest N quarantined count
# ---------------------------------------------------------------------------
def test_malformed_moved_to_quarantine_and_counted(env):
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    bad = inbox / "01BADFILE.md"
    bad.write_text("this has no valid frontmatter at all\njust text\n")
    d = mail.digest(days=0)
    assert d["quarantined"] >= 1
    # the malformed file is moved out of inbox
    assert not bad.exists()
    assert (env["mail_root"] / "fabrik" / "malformed" / "01BADFILE.md").exists()


# ---------------------------------------------------------------------------
# SECURITY hardening (Phase B review — pool + native findings)
# ---------------------------------------------------------------------------
def test_send_refuses_traversal_recipient(env):
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="../evil", kind="finding", body="x", frm="fabrik")


def test_ack_rejects_traversal_msg_id(env):
    with pytest.raises(mail.MailRefusedError):
        mail.ack(msg_id="../../OUTSIDE", repo="fabrik", disposition="done")


def test_ack_rejects_traversal_repo(env):
    p = mail.send(to="fabrik", kind="request", body="x", frm="alpha")
    mid = p.name.removesuffix(".md")
    with pytest.raises(mail.MailRefusedError):
        mail.ack(msg_id=mid, repo="../../etc", disposition="done")


def test_requeue_rejects_traversal(env):
    with pytest.raises(mail.MailRefusedError):
        mail.requeue(msg_id="../../x", repo="fabrik")


def test_read_rejects_traversal_id(env):
    with pytest.raises(mail.MailRefusedError):
        mail.read_msg("../../../etc/passwd", "fabrik")


def test_digest_not_fooled_by_acked_by_prose_in_body(env):
    # a request (ack:required) whose BODY casually mentions "acked-by:" must NOT
    # be treated as acked when archived without a REAL ack line (old substring bug).
    p = mail.send(
        to="fabrik",
        kind="request",
        body="the boss said acked-by: someone should handle this",
        frm="alpha",
    )
    arch_dir = env["mail_root"] / "fabrik" / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    os.rename(p, arch_dir / p.name)  # archived, NO real ack line appended
    d = mail.digest(days=0)
    assert d["unacked"] >= 1  # the prose "acked-by:" must not hide it


def test_parse_quarantines_empty_id_or_kind(env):
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "01EMPTYID.md").write_text("---\nid:\nkind: request\n---\nbody\n")
    d = mail.digest(days=0)
    assert d["quarantined"] >= 1
    assert (env["mail_root"] / "fabrik" / "malformed" / "01EMPTYID.md").exists()


def test_send_refuses_jwt(env):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N"
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="fabrik", kind="finding", body=f"token: {jwt}", frm="alpha")


def test_send_refuses_bearer_and_db_url(env):
    with pytest.raises(mail.MailRefusedError):
        mail.send(
            to="fabrik",
            kind="finding",
            body="Authorization: Bearer abcdef1234567890XYZ",
            frm="alpha",
        )
    with pytest.raises(mail.MailRefusedError):
        mail.send(
            to="fabrik",
            kind="finding",
            body="db at postgresql://user:s3cretpass@host:5432/db",
            frm="alpha",
        )


def test_send_refuses_anthropic_and_aws_session_and_github_pat(env):
    # native review F3: sk-ant- (Anthropic's OWN key), ASIA (AWS session), github_pat fine-grained
    for body in (
        "key: sk-ant-api03-AbCdEf0123456789ghIjKlMnOpQrStUvWx",
        "aws temp: ASIAY34FZKBOKMUTVV7A",
        "pat: github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz012345",
    ):
        with pytest.raises(mail.MailRefusedError):
            mail.send(to="fabrik", kind="finding", body=body, frm="alpha")


def test_send_refuses_redis_url_without_user(env):
    # native review F3: redis://:pw@ has an EMPTY username — must still refuse
    with pytest.raises(mail.MailRefusedError):
        mail.send(
            to="fabrik",
            kind="finding",
            body="cache at redis://:sup3rs3cr3tpw@10.99.0.1:6379/0",
            frm="alpha",
        )


def test_digest_excludes_properly_acked_message(env):
    # whole-plan seam: the ack line ack() WRITES must match the _ACK_LINE regex
    # digest READS, so a resolved message is never nagged (silent-drift guard).
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert mail.digest(days=0)["unacked"] == 0


def test_ack_rejects_unknown_disposition(env):
    # DISPOSITIONS SSOT: ack() validates its arg (a disposition not in the set that
    # _ACK_LINE matches would else archive a message digest counts unacked forever).
    p = mail.send(to="fabrik", kind="request", body="x", frm="alpha")
    mid = p.name.removesuffix(".md")
    with pytest.raises(mail.MailRefusedError):
        mail.ack(msg_id=mid, repo="fabrik", disposition="maybe")


def test_ack_line_regex_matches_every_disposition(env):
    # the _ACK_LINE regex (digest reader) matches what ack() writes for EACH disposition
    for disp in mail.DISPOSITIONS:
        p = mail.send(to="fabrik", kind="request", body=f"do {disp}", frm="alpha")
        mid = p.name.removesuffix(".md")
        arch = mail.ack(msg_id=mid, repo="fabrik", disposition=disp)
        assert mail._ACK_LINE.search(arch.read_text()), disp


def test_requeue_strips_stale_ack_line(env):
    # fabrik-lib production finding: claim-via-ack asserts a disposition, and requeue must NOT
    # carry that stale `acked-by: … done` marker back into the next reader's inbox.
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.ack(msg_id=mid, repo="fabrik", disposition="done")  # claim + (prematurely) assert done
    back = mail.requeue(msg_id=mid, repo="fabrik")
    assert back.parent.name == "inbox"
    assert "acked-by:" not in back.read_text()  # stale claim marker stripped — a clean re-open
    assert "do X" in back.read_text()  # body survives the strip


# ---------------------------------------------------------------------------
# claim (plan 2026-08-12-plan-2 Phase C2 — fabrik-lib finding 01KZTGCCZH…)
# ---------------------------------------------------------------------------
def test_claim_moves_without_ack_line(env):
    """claim = the rename lock ALONE — no acked-by/disposition line (the honest
    claim-first-then-work verb; ack stays the resolve)."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    arch = mail.claim(msg_id=mid, repo="fabrik")
    assert arch.exists() and not p.exists()
    assert "acked-by:" not in arch.read_text()


def test_claim_loser_gets_enoent(env):
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    with pytest.raises(FileNotFoundError):
        mail.claim(msg_id=mid, repo="fabrik")  # the rename IS the lock


def test_ack_after_claim_appends_in_place(env):
    """A claimed (archived) message is resolvable: ack appends the disposition line
    to the archived file without requiring it back in the inbox."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    arch = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert "disposition: done" in arch.read_text()


def test_requeue_after_claim_carries_no_stale_marker(env):
    """claim → requeue → the re-opened message is marker-free (regression: the
    _ACK_LINE strip covers the claim path too)."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    back = mail.requeue(msg_id=mid, repo="fabrik")
    assert back.exists()
    assert "acked-by:" not in back.read_text()


def test_digest_alert_import_resolves_from_script_invocation(env, tmp_path):
    """`python scripts/mail.py digest` runs with sys.path[0]=scripts/ — the lazy
    `from libs.alerting import send_alert` must resolve via a repo-root sys.path insert,
    never die as ModuleNotFoundError (fleet finding 01KZTMZ19…). Proven at the seam:
    the hub-side import path must find libs/ from the script's parent-parent."""
    import os as _os
    import subprocess
    import sys as _sys

    repo_root = Path(mail.__file__).resolve().parent.parent
    env_vars = {k: v for k, v in _os.environ.items() if k != "PYTHONPATH"}
    probe = (
        "import runpy, sys; sys.argv=['mail.py']; "
        "m = runpy.run_path(r'%s'); "
        "import types; "
        "ok = True\n"
        "try:\n"
        "    m['_import_alerting']()\n"
        "except ModuleNotFoundError as e:\n"
        "    ok = False; print('MNFE:', e)\n"
        "print('IMPORT_OK' if ok else 'IMPORT_DEAD')"
    ) % (repo_root / "scripts" / "mail.py")
    r = subprocess.run(
        [_sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=30,
        env=env_vars,
        cwd=str(repo_root),
    )
    assert "IMPORT_OK" in r.stdout, (r.stdout, r.stderr)


def test_ack_append_helper_never_creates(env, tmp_path):
    """The ack-line append must FAIL LOUDLY if the archived file vanished between ack's
    rename and its append (a concurrent requeue won the race) — never silently create an
    archive file holding only an ack line (pool finding, Phase C review). Guarded at the
    append seam: no O_CREAT."""
    ghost = tmp_path / "gone.md"
    with pytest.raises(FileNotFoundError):
        mail._append_ack_line(ghost, "fabrik", "done")
    assert not ghost.exists()


def test_send_refuses_body_with_verbatim_ack_line(env):
    """A body QUOTING a real ack line would poison claim/ack/digest scans (closer C3:
    permanently un-ackable + invisible to the digest) — refuse at send, teach the sender
    to indent-quote ('> acked-by: …')."""
    bad = "relaying the thread:\nacked-by: fabrik · ts: 2026-08-12T00:00:00Z · disposition: done\n"
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="fabrik", kind="finding", body=bad, frm="alpha")
    ok = "relaying the thread:\n> acked-by: fabrik · ts: X · disposition: done\n"
    assert mail.send(to="fabrik", kind="finding", body=ok, frm="alpha").exists()


def test_ack_fallback_window_excludes_a_second_acker(env, monkeypatch):
    """Closer C1 (probe-confirmed TOCTOU): two concurrent acks on a CLAIMED message both
    passed the exists+read check and appended CONTRADICTORY dispositions. Deterministic
    re-entrant pin: a second ack arriving INSIDE the first's append window must fail
    loudly — exactly one acked-by line survives."""
    import os as _os
    import time as _time

    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    _os.utime(p, (_time.time() - 300, _time.time() - 300))  # OLD message (closer E1: renames
    # preserve mtime — the gate must measure the WINDOW's age, never the message's)
    mail.claim(msg_id=mid, repo="fabrik")
    real_append = mail._append_ack_line
    inner_raised = {}

    def racing_append(dst, repo, disposition):
        if "done" in disposition and not inner_raised:
            inner_raised["probed"] = True
            with pytest.raises(FileNotFoundError):
                mail.ack(msg_id=mid, repo="fabrik", disposition="wontfix")
        return real_append(dst, repo, disposition)

    monkeypatch.setattr(mail, "_append_ack_line", racing_append)
    out = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert inner_raised.get("probed")
    text = out.read_text()
    assert text.count("acked-by:") == 1, text
    assert "wontfix" not in text


def test_stale_resolving_orphan_is_swept_and_resolvable(env):
    """Closer D1: a resolver killed mid-window (SIGKILL/OOM) leaves <id>.md.resolving —
    invisible to ack/claim/requeue/read/digest. ack must sweep the orphan back and resolve."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    arch = mail._mail_root() / "fabrik" / "archive" / f"{mid}.md"
    orphan = arch.parent / f"{mid}.md.resolving.99999"
    arch.rename(orphan)  # the dead resolver's residue
    import os as _os
    import time as _time

    _os.utime(orphan, (_time.time() - 120, _time.time() - 120))  # older than the 60s gate
    out = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert out.exists() and "disposition: done" in out.read_text()
    assert not arch.with_suffix(".md.resolving").exists()


def test_digest_counts_stale_resolving_as_unacked(env):
    """Closer D1 (visibility half): a stranded .resolving file must show in the digest,
    never report a clean mailbox while a message is invisible."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    arch = mail._mail_root() / "fabrik" / "archive" / f"{mid}.md"
    arch.rename(arch.parent / f"{mid}.md.resolving.99999")
    d = mail.digest(days=1)
    assert d["unacked"] >= 1, d


def test_window_isolation_requeue_and_reclaim_both_locked_out(env, monkeypatch):
    """Closer E2 (the fake-raise version proved nothing): with the unified per-process
    resolve window, a REAL append runs while requeue AND a fresh re-claim both attempt to
    interleave — both must ENOENT, the resolve lands exactly once on the original."""
    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    real_append = mail._append_ack_line
    probes = {}

    def probing_append(dst, repo, disposition):
        if not probes:
            probes["requeue"] = probes["reclaim"] = "not-raised"
            try:
                mail.requeue(msg_id=mid, repo="fabrik")
            except FileNotFoundError:
                probes["requeue"] = "locked-out"
            try:
                mail.claim(msg_id=mid, repo="fabrik")
            except FileNotFoundError:
                probes["reclaim"] = "locked-out"
        return real_append(dst, repo, disposition)

    monkeypatch.setattr(mail, "_append_ack_line", probing_append)
    out = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert probes == {"requeue": "locked-out", "reclaim": "locked-out"}, probes
    text = out.read_text()
    assert text.count("acked-by:") == 1 and "disposition: done" in text


def test_multiple_stale_orphans_all_cleared(env):
    """Closer F1: two crashes on one id left N orphans — one recovered, the rest were
    PERMANENT digest noise. The sweep must recover one and clear the rest; digest clean."""
    import os as _os
    import time as _time

    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    mail.claim(msg_id=mid, repo="fabrik")
    arch = mail._mail_root() / "fabrik" / "archive" / f"{mid}.md"
    o1 = arch.parent / f"{mid}.md.resolving.1111"
    o2 = arch.parent / f"{mid}.md.resolving.2222"
    import shutil

    shutil.copy(arch, o1)
    arch.rename(o2)
    for o in (o1, o2):
        _os.utime(o, (_time.time() - 300, _time.time() - 300))
    out = mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert out.exists() and out.read_text().count("acked-by:") == 1
    assert not o1.exists() and not o2.exists(), "stale orphans must not outlive the resolve"
    assert mail.digest(days=0)["unacked"] == 0


def test_window_never_carries_stale_mtime(env, monkeypatch):
    """Closer F2 (two-syscall residual): between rename and utime the window carried the
    MESSAGE's old mtime — stealable. The stamp must land BEFORE the rename (it travels
    atomically), so no instant exists where a window file looks old."""
    import os as _os
    import time as _time

    p = mail.send(to="fabrik", kind="request", body="do X", frm="alpha")
    mid = p.name.removesuffix(".md")
    _os.utime(p, (_time.time() - 300, _time.time() - 300))
    mail.claim(msg_id=mid, repo="fabrik")
    real_rename = _os.rename
    seen = {}

    def checking_rename(src, dst_, *a, **k):
        if ".resolving." in str(dst_):
            seen["window_src_age"] = _time.time() - _os.stat(src).st_mtime
        return real_rename(src, dst_, *a, **k)

    monkeypatch.setattr(mail.os, "rename", checking_rename)
    mail.ack(msg_id=mid, repo="fabrik", disposition="done")
    assert seen and seen["window_src_age"] < 5, seen


# ---------------------------------------------------------------------------
# Loop-safety guards (plan 2026-08-22-plan-1-fabrik-mail-loop-safety)
# ---------------------------------------------------------------------------
def _mint(env, frm, to, kind, ack, ts="2026-08-22T10:00:00+00:00", hops=None, mid=None):
    """Plant a message file directly in <to>'s inbox (frontmatter-level fixture)."""
    mid = mid or mail._ulid()
    lines = [
        "---",
        f"id: {mid}",
        f"from: {frm}",
        f"to: {to}",
        f"ts: {ts}",
        "re: ",
        f"kind: {kind}",
        f"ack: {ack}",
    ]
    if hops is not None:
        lines.append(f"hops: {hops}")
    lines += ["---", "body", ""]
    inbox = env["mail_root"] / to / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{mid}.md").write_text("\n".join(lines), encoding="utf-8")
    return mid


def test_auto_guard_truth_table(env):
    """Guard order: self → terminal-kind → hop-cap → rate-cap → ALLOW."""
    # self-guard
    ok, reason = mail.should_auto_reply(
        {"from": "fabrik", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert not ok and "self" in reason
    # terminal kind (ack: no)
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "reply", "ack": "no", "hops": "0"}, "fabrik"
    )
    assert not ok and "terminal" in reason
    # hop cap
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "3"}, "fabrik"
    )
    assert not ok and "hop" in reason
    # ALLOW (fresh request, no traffic)
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert ok, reason


def test_hop_cap_boundary_equal_refuses(env, monkeypatch):
    """parent.hops == cap REFUSES (>=, not >)."""
    monkeypatch.setenv("FABRIK_MAIL_HOP_CAP", "2")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "2"}, "fabrik"
    )
    assert not ok and "hop" in reason
    ok, _ = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "1"}, "fabrik"
    )
    assert ok


def test_rate_cap_counts_only_recent_from_sender(env):
    """5 recent messages from the sender in MY inbox+archive → rate HOLD."""
    now_ts = mail.datetime.fromisoformat("2026-08-22T12:00:00+00:00").timestamp()
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts="2026-08-22T11:30:00+00:00")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now_ts,
    )
    assert not ok and "rate" in reason
    # a different sender's traffic never counts
    ok, _ = mail.should_auto_reply(
        {"from": "beta", "kind": "request", "ack": "required", "hops": "0"}, "fabrik", now_ts=now_ts
    )
    assert ok


def test_rate_window_edge(env):
    """A message aged EXACTLY the window is OUT; one second younger is IN."""
    now_ts = mail.datetime.fromisoformat("2026-08-22T12:00:00+00:00").timestamp()
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts="2026-08-22T11:00:00+00:00")
    # exactly window (3600 s) old → OUT → count 0 → ALLOW
    ok, _ = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now_ts,
    )
    assert ok, "age == window is OUT of the window"
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts="2026-08-22T11:00:01+00:00")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now_ts,
    )
    assert not ok and "rate" in reason, "age == window - 1 is IN"


def test_re_send_increments_hops_including_legacy_parent(env):
    """send --re sets hops = parent.hops + 1; a legacy parent with NO hops key
    counts as 0 → child 1. Human sends (no --auto) are never gated."""
    pid = _mint(env, "alpha", "fabrik", "request", "required", hops=None)  # legacy: no hops
    out = mail.send("alpha", "reply", "x", frm="fabrik", re=pid)
    fm = mail._parse(out.read_text(encoding="utf-8"))
    assert fm.get("hops") == "1", fm
    pid2 = _mint(env, "alpha", "fabrik", "request", "required", hops=7)
    out2 = mail.send("alpha", "reply", "x", frm="fabrik", re=pid2)
    assert mail._parse(out2.read_text(encoding="utf-8")).get("hops") == "8"


def test_human_deep_thread_never_gated(env):
    """No --auto → no guard, whatever the depth or kind."""
    pid = _mint(env, "fabrik", "fabrik", "reply", "no", hops=99)  # self + terminal + deep
    out = mail.send("alpha", "reply", "x", frm="fabrik", re=pid)
    assert out.is_file()


def test_auto_without_re_is_usage_refusal(env):
    with pytest.raises(mail.MailRefusedError, match="--auto requires --re"):
        mail.send("alpha", "reply", "x", frm="fabrik", auto=True)


def test_auto_with_dangling_re_fail_soft_allows(env, capsys):
    """An unresolvable --re under --auto ALLOWs with hops=0 and a stderr note."""
    out = mail.send("alpha", "reply", "x", frm="fabrik", re="01ARZ3NDEKTSV4RRFFQ69G5FAV", auto=True)
    fm = mail._parse(out.read_text(encoding="utf-8"))
    assert fm.get("hops") == "0"
    assert "fail-soft" in capsys.readouterr().err


def test_auto_refuses_on_guard_and_writes_nothing(env):
    """--auto on a terminal-kind parent → MailRefusedError, no file minted."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no")
    before = (
        sorted((env["mail_root"] / "alpha" / "inbox").glob("*.md"))
        if (env["mail_root"] / "alpha" / "inbox").is_dir()
        else []
    )
    with pytest.raises(mail.MailRefusedError, match="terminal"):
        mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)
    after = (
        sorted((env["mail_root"] / "alpha" / "inbox").glob("*.md"))
        if (env["mail_root"] / "alpha" / "inbox").is_dir()
        else []
    )
    assert before == after, "a refused auto-reply writes NOTHING"


def test_auto_allows_a_fresh_request_parent(env):
    pid = _mint(env, "alpha", "fabrik", "request", "required")
    out = mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)
    assert out.is_file()
    assert mail._parse(out.read_text(encoding="utf-8")).get("hops") == "1"


def test_unreadable_rate_state_fails_soft_allow(env, capsys, monkeypatch):
    """A rate count that cannot be computed ALLOWs with a stderr note — a loop
    is lower-risk than a wedged channel."""

    def _boom(*a, **kw):
        raise OSError("simulated unreadable mailbox")

    monkeypatch.setattr(mail, "_recent_from_count", _boom)
    ok, _ = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert ok
    assert "rate" in capsys.readouterr().err.lower()


def test_rate_count_is_read_only_never_quarantines(env):
    """Unlike digest's walk, the rate count must SKIP a malformed file, never
    move it to malformed/."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    bad = inbox / "malformed-thing.md"
    bad.write_text("no frontmatter at all", encoding="utf-8")
    now_ts = mail.datetime.now(mail.UTC).timestamp()
    # P13-2: assert the RETURN, not only the side effect — the original test
    # passed whether or not the malformed file was skipped from the tally, and
    # a regressed `fm is None` guard raises AttributeError right here.
    assert mail._recent_from_count("fabrik", "alpha", 3600, now_ts) == 0
    assert bad.is_file(), "read-only: the malformed file stays exactly where it was"
    assert not (env["mail_root"] / "fabrik" / "malformed").exists()


def test_should_reply_cli_exit_codes(env, capsys):
    """should-reply <id>: ALLOW exit 0 · HOLD exit 3 (distinct from refusal 2)."""
    pid = _mint(env, "alpha", "fabrik", "request", "required")
    rc = mail.main(["should-reply", pid, "--repo", "fabrik"])
    assert rc == 0 and "ALLOW" in capsys.readouterr().out
    pid2 = _mint(env, "alpha", "fabrik", "reply", "no")
    rc = mail.main(["should-reply", pid2, "--repo", "fabrik"])
    assert rc == 3 and "HOLD" in capsys.readouterr().out


# --- boundary-review fix wave (R1..R11) -------------------------------------
def test_prose_re_never_breaks_a_send(env):
    """R1 (HIGH): legacy threads carry prose re: values (live store proof:
    'U3: is validate_conventions …') — a non-ULID --re must fail-soft to
    hops=0, never refuse the send."""
    out = mail.send("alpha", "reply", "x", frm="fabrik", re="U3: prose thread ref")
    assert out.is_file()
    assert mail._parse(out.read_text(encoding="utf-8")).get("hops") == "0"


def test_spoofed_ack_on_terminal_kind_still_terminal(env):
    """R2 (HIGH): the guard keys on the KIND, not the overridable ack — a
    reply minted with --ack required must still be terminal."""
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "reply", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert not ok and "terminal" in reason


def test_existing_but_unparseable_parent_refuses_auto(env):
    """R3: a parent that EXISTS but cannot be parsed must REFUSE an --auto
    reply (guards cannot be evaluated — never bypass them blind); only a
    genuinely MISSING parent is the fail-soft ALLOW."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    bad_id = mail._ulid()
    (inbox / f"{bad_id}.md").write_text("---\nid: \nkind: \n---\nbroken\n", encoding="utf-8")
    with pytest.raises(mail.MailRefusedError, match="unparseable"):
        mail.send("alpha", "reply", "x", frm="fabrik", re=bad_id, auto=True)


def test_negative_or_garbage_hops_clamp_to_zero(env):
    """R4: hops is clamped to >= 0 — a corrupt negative value must not disable
    the hop cap; garbage parses 0."""
    assert mail._fm_hops({"hops": "-999"}) == 0
    assert mail._fm_hops({"hops": "3.5"}) == 0
    assert mail._fm_hops({"hops": "7"}) == 7


def test_guard_precedence_first_trip_wins(env):
    """R10: two-guard fixtures prove the ORDER — self outranks terminal;
    terminal outranks hop."""
    ok, reason = mail.should_auto_reply(
        {"from": "fabrik", "kind": "reply", "ack": "no", "hops": "99"}, "fabrik"
    )
    assert not ok and "self" in reason
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "reply", "ack": "no", "hops": "99"}, "fabrik"
    )
    assert not ok and "terminal" in reason


def test_should_reply_non_ulid_fails_soft_allow(env, capsys):
    """R7: the advisory pre-check never hard-fails — a non-ULID id ALLOWs
    (exit 0) with the fail-soft note."""
    rc = mail.main(["should-reply", "not-a-ulid", "--repo", "fabrik"])
    assert rc == 0
    assert "ALLOW" in capsys.readouterr().out


def test_refused_auto_prints_no_secret_warning(env, capsys):
    """R11: a refused --auto send must not emit the 'sending anyway'
    low-secret warning for a message that was never sent."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no")
    body = "looks like a password: hunter2hunter2"
    with pytest.raises(mail.MailRefusedError):
        mail.send("alpha", "reply", body, frm="fabrik", re=pid, auto=True)
    assert "sending anyway" not in capsys.readouterr().err


# --- confirming-round fix wave (C1..C7) --------------------------------------
def test_should_reply_agrees_with_send_on_unparseable_parent(env, capsys):
    """C1: the advisory pre-check and the enforced send must give the SAME
    verdict — an existing-but-unparseable parent is HOLD (exit 3) on both."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    bad_id = mail._ulid()
    (inbox / f"{bad_id}.md").write_text("---\nid: \nkind: \n---\nbroken\n", encoding="utf-8")
    rc = mail.main(["should-reply", bad_id, "--repo", "fabrik"])
    assert rc == 3
    assert "unparseable" in capsys.readouterr().out


def test_unreadable_existing_parent_refuses_auto(env):
    """C2: EACCES on an EXISTING parent is not 'missing' — guards cannot be
    evaluated, so --auto refuses (only FileNotFoundError is the fail-soft)."""
    import os as _os

    if _os.geteuid() == 0:
        pytest.skip("root ignores mode bits")
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    f = inbox / f"{pid}.md"
    f.write_text("---\nid: x\nkind: request\n---\nbody\n", encoding="utf-8")
    f.chmod(0o000)
    try:
        with pytest.raises(mail.MailRefusedError, match="unreadable|unparseable"):
            mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)
    finally:
        f.chmod(0o644)


def test_hold_exit_code_is_distinct_from_refusal(env, capsys):
    """C3: a loop-safety HOLD from send --auto exits 3 (benign, stop quietly);
    a real refusal (secret, topology) stays 2 — a wrapper can tell them apart."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no")
    import io as _io
    import sys as _sys

    old = _sys.stdin
    _sys.stdin = _io.StringIO("x")
    try:
        rc = mail.main(
            ["send", "--to", "alpha", "--kind", "reply", "--re", pid, "--auto", "--from", "fabrik"]
        )
    finally:
        _sys.stdin = old
    assert rc == 3, "HOLD is exit 3"
    assert "HOLD" in capsys.readouterr().err


def test_future_dated_ts_never_counts_as_recent(env):
    """C4: a future-dated ts (negative age) must not satisfy the window."""
    now_ts = mail.datetime.fromisoformat("2026-08-22T12:00:00+00:00").timestamp()
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts="2026-08-22T13:00:00+00:00")
    ok, _ = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now_ts,
    )
    assert ok, "future-dated messages are corruption, not recent traffic"


def test_naive_ts_is_treated_as_utc(env):
    """C4: a legacy naive ts (no offset) reads as UTC, not box-local."""
    now_ts = mail.datetime.fromisoformat("2026-08-22T12:00:00+00:00").timestamp()
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts="2026-08-22T11:30:00")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now_ts,
    )
    assert not ok and "rate" in reason


def test_cap_zero_means_zero(env, monkeypatch):
    """C6: an explicit cap of 0 is an operator intent (refuse all), never a
    silent fall-back to the default."""
    monkeypatch.setenv("FABRIK_MAIL_HOP_CAP", "0")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert not ok and "hop" in reason


def test_rate_cap_through_the_real_send_path(env):
    """C7: the cap measured as production produces it — the parent itself is in
    the counted set, so cap 5 = parent + 4 more."""
    now = mail.datetime.now(mail.UTC).isoformat()
    pid = _mint(env, "alpha", "fabrik", "request", "required", ts=now)
    for _ in range(4):
        _mint(env, "alpha", "fabrik", "request", "required", ts=now)
    with pytest.raises(mail.MailRefusedError, match="rate"):
        mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)


# --- round-3 fix wave (D1..D9) ------------------------------------------------
def test_rate_window_zero_never_disables_the_breaker(env, monkeypatch, capsys):
    """D1 (HIGH): FABRIK_MAIL_RATE_WINDOW_S=0 must NOT silently disable the
    rate guard — a zero window is invalid (warned, default used)."""
    now = mail.datetime.now(mail.UTC).isoformat()
    for _ in range(5):
        _mint(env, "alpha", "fabrik", "request", "required", ts=now)
    monkeypatch.setenv("FABRIK_MAIL_RATE_WINDOW_S", "0")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert not ok and "rate" in reason, "the breaker must still fire on the default window"
    assert "FABRIK_MAIL_RATE_WINDOW_S" in capsys.readouterr().err


def test_rate_cap_zero_refuses_all(env, monkeypatch):
    """D4: FABRIK_MAIL_RATE_CAP=0 is refuse-all intent (0 recent >= 0)."""
    monkeypatch.setenv("FABRIK_MAIL_RATE_CAP", "0")
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "fabrik"
    )
    assert not ok and "rate" in reason


def test_real_refusal_still_exits_two(env, capsys):
    """D5: the distinctness proof — a usage refusal (--auto without --re) exits
    2 while a guard HOLD exits 3 (test_hold_exit_code covers the 3 side)."""
    import io as _io
    import sys as _sys

    old = _sys.stdin
    _sys.stdin = _io.StringIO("x")
    try:
        rc = mail.main(["send", "--to", "alpha", "--kind", "reply", "--auto", "--from", "fabrik"])
    finally:
        _sys.stdin = old
    assert rc == 2
    assert "REFUSED" in capsys.readouterr().err


def test_high_secret_refusal_outranks_a_guard_hold(env, capsys):
    """E1: a credential-bearing --auto send is a REAL refusal (exit 2), never a
    benign HOLD (3) — even when the parent would also trip a guard."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no", hops=9)  # would HOLD
    import io as _io
    import sys as _sys

    old = _sys.stdin
    _sys.stdin = _io.StringIO("AWS_KEY=AKIAABCDEFGHIJKLMNOP secret payload")
    try:
        rc = mail.main(
            ["send", "--to", "alpha", "--kind", "reply", "--re", pid, "--auto", "--from", "fabrik"]
        )
    finally:
        _sys.stdin = old
    assert rc == 2, "the secret refusal wins"
    assert "secret" in capsys.readouterr().err


def test_invalid_recipient_outranks_a_guard_hold(env, capsys):
    """D6: a REAL misconfiguration (invalid recipient, exit 2) must never be
    masked by a benign guard HOLD (exit 3) — hard validations run first."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no")  # would HOLD under --auto
    import io as _io
    import sys as _sys

    old = _sys.stdin
    _sys.stdin = _io.StringIO("x")
    try:
        rc = mail.main(
            [
                "send",
                "--to",
                "no-such-repo",
                "--kind",
                "reply",
                "--re",
                pid,
                "--auto",
                "--from",
                "fabrik",
            ]
        )
    finally:
        _sys.stdin = old
    assert rc == 2, "the misconfiguration surfaces; the wrapper must not stop quietly"
    assert "invalid recipient" in capsys.readouterr().err


def test_should_reply_names_the_invalid_id_cause(env, capsys):
    """D9: an invalid (non-ULID) id fail-softs ALLOW but says WHY — never the
    false 'no such parent' claim for an id that was never looked up."""
    rc = mail.main(["should-reply", "not-a-ulid", "--repo", "fabrik"])
    assert rc == 0
    assert "not a ULID" in capsys.readouterr().out


def test_naive_ts_digest_and_rate_agree(env):
    """D2: ONE timestamp convention — _age_seconds and _ts_epoch read a naive
    ts identically (UTC), so a message cannot be simultaneously in-window for
    the rate guard and past the digest threshold by the box's UTC offset."""
    naive = "2026-08-22T11:30:00"
    # the convention itself, non-tautologically: naive == the same instant UTC
    assert mail._ts_epoch(naive) == mail._ts_epoch(naive + "+00:00"), (
        "a naive ts must read as UTC, never box-local"
    )
    a = mail._age_seconds(naive)
    t = mail._ts_epoch(naive)
    assert t is not None
    expected = mail.datetime.now(mail.UTC).timestamp() - t
    assert abs(a - expected) < 5, "the two parsers share one implementation"


def test_rate_count_ignores_mtime_entirely(env):
    """F1 (the E2 regression guard): a message with a FRESH ts but an ancient
    mtime (cp -p / rsync -a / restore shape) still counts — re-adding any
    mtime prefilter to _recent_from_count fails here."""
    now = mail.datetime.now(mail.UTC)
    for _ in range(5):
        mid = _mint(env, "alpha", "fabrik", "request", "required", ts=now.isoformat())
        f = env["mail_root"] / "fabrik" / "inbox" / f"{mid}.md"
        os.utime(f, (0, 0))  # epoch mtime — maximally stale
    ok, reason = mail.should_auto_reply(
        {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"},
        "fabrik",
        now_ts=now.timestamp(),
    )
    assert not ok and "rate" in reason, "the ts is the authority; mtime must be ignored"


def test_parent_in_resolving_window_keeps_guards_evaluable(env):
    """G2: a parent parked in an ack resolving window (or orphaned by a crashed
    acker) still resolves — --auto must not fail-soft-bypass the guards."""
    pid = _mint(env, "alpha", "fabrik", "reply", "no")
    inbox = env["mail_root"] / "fabrik" / "inbox"
    (inbox / f"{pid}.md").rename(inbox / f"{pid}.md.resolving.99999")
    with pytest.raises(mail.MailHoldError, match="terminal"):
        mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)


# --- formal /fabrik-review fix wave (H1..R10) --------------------------------
def test_re_field_cannot_inject_frontmatter(env):
    """H1 (HIGH): a newline in --re must not forge frontmatter — the body's
    bare-ack-line guard covers the body, but re: was interpolated raw, letting
    a crafted re: forge `from` (defeating self-guard + rate attribution) and
    plant an acked-by line (poisoning claim/ack/digest)."""
    evil = "01ARZ3NDEKTSV4RRFFQ69G5FAV\nfrom: someone-else\nacked-by: x · disposition: done"
    with pytest.raises(mail.MailRefusedError, match="re"):
        mail.send("fabrik", "request", "x", frm="alpha", re=evil)


def test_quarantined_parent_holds_not_allows(env):
    """H3: a malformed parent quarantined by list/digest must still HOLD under
    --auto (guards cannot be evaluated) — read_msg scans malformed/ too, so the
    quarantine cannot invert the R3 fail-CLOSED into a fail-open ALLOW."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    (inbox / f"{pid}.md").write_text("---\nid: \nkind: \n---\nbroken\n", encoding="utf-8")
    mail.list_msgs("fabrik")  # quarantines the malformed file
    assert (env["mail_root"] / "fabrik" / "malformed" / f"{pid}.md").is_file()
    with pytest.raises(mail.MailHoldError, match="unparseable"):
        mail.send("alpha", "reply", "x", frm="fabrik", re=pid, auto=True)


def test_read_msg_survives_concurrent_ack_rename(env, monkeypatch):
    """M4 (TOCTOU): a parent renamed into the resolving window between is_file()
    and read_text() must fall through to the glob, not propagate FileNotFound
    into the fail-soft ALLOW."""
    archive = env["mail_root"] / "fabrik" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    canonical = archive / f"{pid}.md"
    canonical.write_text("---\nid: x\nkind: request\nack: required\n---\nb\n", encoding="utf-8")
    real_read = Path.read_text
    state = {"n": 0}

    def _racing_read(self, *a, **kw):
        if self == canonical and state["n"] == 0:
            state["n"] = 1
            canonical.rename(archive / f"{pid}.md.resolving.123")
            raise FileNotFoundError(str(canonical))
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", _racing_read)
    text = mail.read_msg(pid, "fabrik")  # must NOT raise
    assert "kind: request" in text


def test_resolving_glob_returns_newest_by_mtime(env):
    """M7: two resolving orphans — read_msg returns the NEWEST by mtime (the
    live window's content), not the lexically-last PID."""
    archive = env["mail_root"] / "fabrik" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    old = archive / f"{pid}.md.resolving.9"
    new = archive / f"{pid}.md.resolving.10"  # lexically LAST but we make it OLDER
    old.write_text("NEW content\n", encoding="utf-8")
    new.write_text("OLD content\n", encoding="utf-8")
    os.utime(new, (1, 1))  # new is oldest by mtime
    os.utime(old, (mail.time.time(), mail.time.time()))
    assert "NEW content" in mail.read_msg(pid, "fabrik")


def test_digest_survives_concurrent_claim(env, monkeypatch):
    """M10: a file vanishing between glob and read_text (concurrent claim) must
    not crash the daily digest cron."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    pid = _mint(env, "alpha", "fabrik", "request", "required")
    real_read = Path.read_text

    def _vanish(self, *a, **kw):
        if self.name == f"{pid}.md":
            raise FileNotFoundError(str(self))
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", _vanish)
    d = mail.digest(days=0)  # must not raise
    assert isinstance(d, dict)


def test_a_claimed_malformed_file_is_still_counted(env):
    """P11-1: a peer that CLAIMED the corrupt file (claim never parses, and the
    archive leg skips unparseable rows) is NOT 'already parked' — counting it as
    a success made it permanently invisible: a clean mailbox over a malformed
    message, forever."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    archive = env["mail_root"] / "fabrik" / "archive"
    inbox.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    f = inbox / f"{pid}.md"
    f.write_text("corrupt\n", encoding="utf-8")
    real_rename = mail.os.rename

    def _peer_claims_first(src, dst):
        if str(src) == str(f):
            real_rename(src, archive / f"{pid}.md")  # the peer's claim wins
            raise FileNotFoundError(str(src))
        return real_rename(src, dst)

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(mail.os, "rename", _peer_claims_first)
        d = mail.digest(days=0)
    assert d["quarantined"] == 1, f"a claimed-away corrupt file stays visible: {d}"


def test_a_peer_parked_file_is_not_double_counted(env):
    """P10-7 (the discriminating half): when the peer genuinely PARKED it, the
    parked glob counts it once — the call site must not add a second."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    malformed = env["mail_root"] / "fabrik" / "malformed"
    inbox.mkdir(parents=True, exist_ok=True)
    malformed.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    f = inbox / f"{pid}.md"
    f.write_text("corrupt\n", encoding="utf-8")
    real_rename = mail.os.rename

    def _peer_parks_first(src, dst):
        if str(src) == str(f):
            real_rename(src, malformed / f"{pid}.md")  # the peer parks it
            raise FileNotFoundError(str(src))
        return real_rename(src, dst)

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(mail.os, "rename", _peer_parks_first)
        d = mail.digest(days=0)
    assert d["quarantined"] == 1, f"counted exactly once, never twice: {d}"


def test_should_auto_reply_validates_self_repo(env):
    """L9: the public guard entry point keeps the traversal defense — an unsafe
    self_repo is refused, not walked."""
    with pytest.raises(mail.MailRefusedError):
        mail.should_auto_reply(
            {"from": "alpha", "kind": "request", "ack": "required", "hops": "0"}, "../etc"
        )


def test_re_rejects_every_splitlines_separator(env):
    """P2-1 (HIGH): _parse splits frontmatter with str.splitlines(), which
    breaks on U+2028/2029/0085/000B/000C/001C-1E too — the injection guard must
    reject the SAME separator set the parser honours, or `from` stays forgeable."""
    for sep in ("\u2028", "\u2029", "\x85", "\v", "\f", "\x1c", "\x1d", "\x1e"):
        with pytest.raises(mail.MailRefusedError, match="single line"):
            mail.send(
                "fabrik",
                "request",
                "x",
                frm="alpha",
                re=f"01ARZ3NDEKTSV4RRFFQ69G5FAV{sep}from: attacker",
            )


def test_prose_re_with_spaces_still_allowed(env):
    """P2-1 counter-direction: the R1 prose fail-soft survives — only line
    separators are refused, not ordinary text."""
    out = mail.send(
        "fabrik", "request", "x", frm="alpha", re="U3: is validate_conventions the path"
    )
    assert out.is_file()


def test_resolving_sort_survives_a_vanishing_window(env, monkeypatch):
    """P2-2: a window vanishing during the mtime sort must not abort read_msg —
    the sort key fail-softs so a sibling readable window still resolves."""
    archive = env["mail_root"] / "fabrik" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    gone = archive / f"{pid}.md.resolving.1"
    live = archive / f"{pid}.md.resolving.2"
    gone.write_text("gone\n", encoding="utf-8")
    live.write_text("---\nid: x\nkind: request\n---\nlive\n", encoding="utf-8")
    real_stat = Path.stat

    def _racing_stat(self, *a, **kw):
        if self == gone:
            raise FileNotFoundError(str(gone))
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", _racing_stat)
    assert "live" in mail.read_msg(pid, "fabrik")


def test_ack_field_cannot_inject_frontmatter(env):
    """P3-1 (HIGH): `ack` is the SECOND raw-interpolated frontmatter value — the
    library path took any string. A line break in it forges `from` (defeating
    the self-guard) and can plant an acked-by line (permanently un-ackable +
    digest-invisible). Same splitlines() test as --re, plus a vocabulary check."""
    with pytest.raises(mail.MailRefusedError, match="ack"):
        mail.send("fabrik", "request", "x", frm="alpha", ack="required\nfrom: attacker")
    with pytest.raises(mail.MailRefusedError, match="ack"):
        mail.send("fabrik", "request", "x", frm="alpha", ack="bogus")
    assert mail.send("fabrik", "request", "x", frm="alpha", ack="required").is_file()


def test_should_reply_unsafe_repo_holds_not_allows(env, capsys):
    """P3-2: an unsafe --repo must HOLD (fail-CLOSED, matching L9 on the library
    entry), never a fail-open ALLOW with a false 'not a ULID' cause."""
    rc = mail.main(["should-reply", "01ARZ3NDEKTSV4RRFFQ69G5FAV", "--repo", "../../etc"])
    assert rc == 3
    out = capsys.readouterr().out
    assert "HOLD" in out and "repo" in out


def test_re_length_is_bounded(env):
    """P3-7: a mail is a pointer — an unbounded --re would bloat every mailbox
    walk (rate count, digest, list) forever."""
    with pytest.raises(mail.MailRefusedError, match="re"):
        mail.send("fabrik", "request", "x", frm="alpha", re="x" * 5000)


def test_resolving_glob_mtime_key_is_load_bearing(env):
    """P3-6: PIDs swapped so LEXICAL and MTIME order disagree — only the mtime
    key can pass (the prior fixture's orders coincided)."""
    archive = env["mail_root"] / "fabrik" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    lex_last = archive / f"{pid}.md.resolving.9"  # lexically LAST
    newest = archive / f"{pid}.md.resolving.10"  # lexically first, but NEWEST
    lex_last.write_text("STALE content\n", encoding="utf-8")
    newest.write_text("LIVE content\n", encoding="utf-8")
    os.utime(lex_last, (1, 1))
    assert "LIVE content" in mail.read_msg(pid, "fabrik")


def test_body_ack_line_guard_catches_cr_separators(env):
    """P4-1 (HIGH): _ACK_LINE's (?m)^ anchors on \\n only, but every reader uses
    read_text() (universal newlines: \\r -> \\n) while stdin does NOT translate —
    so a lone \\r walked the body guard and produced a permanently un-ackable,
    digest-invisible message. The guard must normalize like its consumers."""
    for sep in ("\r", "\u2028", "\x85", "\v", "\f"):
        body = f"note{sep}acked-by: fabrik · disposition: done"
        with pytest.raises(mail.MailRefusedError, match="ack line"):
            mail.send("fabrik", "request", body, frm="alpha")


def test_digest_survives_a_claim_racing_the_quarantine(env, monkeypatch):
    """P4-2: M10 wrapped the read but not the very next os.rename — a malformed
    file claimed between them crashed digest OUT, skipping every later mailbox
    and never delivering the daily alert."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{mail._ulid()}.md").write_text("not frontmatter\n", encoding="utf-8")
    real_rename = mail.os.rename

    def _vanish(src, dst):
        raise FileNotFoundError(str(src))

    monkeypatch.setattr(mail.os, "rename", _vanish)
    d = mail.digest(days=0)  # must not raise
    assert isinstance(d, dict)
    monkeypatch.setattr(mail.os, "rename", real_rename)


def test_ack_survives_undecodable_bytes(env):
    """P4-5: ack/requeue were the only readers without errors='replace' — one
    stray byte made a message un-ackable via an unhandled traceback."""
    pid = _mint(env, "alpha", "fabrik", "request", "required")
    f = env["mail_root"] / "fabrik" / "inbox" / f"{pid}.md"
    f.write_bytes(f.read_bytes() + b"\xff\xfe binary tail\n")
    out = mail.ack(pid, "fabrik")  # must not raise UnicodeDecodeError
    assert out.is_file()


def test_empty_ack_still_means_kind_default(env):
    """P4-6: ack='' is the legacy 'use the kind default' idiom — the P3-1
    vocabulary check must not break it."""
    out = mail.send("fabrik", "request", "x", frm="alpha", ack="")
    assert mail._parse(out.read_text(encoding="utf-8")).get("ack") == "required"


def test_quarantine_never_overwrites_an_earlier_copy(env):
    """P4-8: the module's stated never-overwrite invariant — a re-quarantined id
    must not destroy the earlier malformed copy."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    malformed = env["mail_root"] / "fabrik" / "malformed"
    inbox.mkdir(parents=True, exist_ok=True)
    malformed.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    (malformed / f"{pid}.md").write_text("FIRST corrupt copy\n", encoding="utf-8")
    (inbox / f"{pid}.md").write_text("SECOND corrupt copy\n", encoding="utf-8")
    mail.list_msgs("fabrik")
    assert "FIRST corrupt copy" in (malformed / f"{pid}.md").read_text(), "the first copy survives"
    assert len(list(malformed.glob(f"{pid}*"))) == 2, "the second lands beside it"


def test_list_msgs_refuses_an_unsafe_repo(env):
    """P5-2: list is the ONE repo-taking verb that was unguarded — and the only
    one that MOVES files (quarantine). An unsafe --repo relocated every
    non-frontmatter *.md under an arbitrary path, exit 0, no stderr."""
    for bad in ("../victim", "/tmp/abs-victim"):
        with pytest.raises(mail.MailRefusedError, match="repo"):
            mail.list_msgs(bad)


def test_requeue_never_mutates_undecodable_bytes(env):
    """P5-3: P4-5's errors='replace' made requeue read lossily and write the
    lossy text BACK — a stray byte became U+FFFD permanently. The rewrite must
    preserve bytes it cannot decode."""
    pid = _mint(env, "alpha", "fabrik", "request", "required")
    f = env["mail_root"] / "fabrik" / "inbox" / f"{pid}.md"
    f.write_bytes(f.read_bytes() + b"raw \xff byte\n")
    mail.claim(pid, "fabrik")
    out = mail.requeue(pid, "fabrik")
    assert b"\xff" in out.read_bytes(), "the undecodable byte survives a requeue"


def test_digest_counts_only_files_it_really_quarantined(env, monkeypatch):
    """P5-4: P4-2's fail-soft swallow must not be reported as a successful
    quarantine — the daily alert would claim files were moved that were not."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{mail._ulid()}.md").write_text("not frontmatter\n", encoding="utf-8")

    def _fail(src, dst):
        raise PermissionError("read-only malformed/")

    monkeypatch.setattr(mail.os, "rename", _fail)
    d = mail.digest(days=0)
    assert d["quarantined"] == 1, (
        "P9-1: a file that could NOT be parked is still malformed and still "
        "visible — a silent 0 would report a clean mailbox over it"
    )


def test_ack_line_guard_catches_separators_inside_the_line(env):
    """P6-1 (HIGH regression): a separator inside the ack line's .+ region split
    the normalized view so the guard missed it — while read_text() does NOT
    translate \\v/\\f/\\x85/U+2028, so every consumer still matched. The guard is
    the UNION of the raw and normalized views."""
    for sep in ("\v", "\f", "\x85", "", "", "\x1c"):
        body = f"acked-by: A{sep}B · disposition: done"
        with pytest.raises(mail.MailRefusedError, match="ack line"):
            mail.send("fabrik", "request", body, frm="alpha")


def test_read_msg_prefers_the_newest_quarantined_copy(env):
    """P6-8: repeat corruption numbers the copies (.1, .2) — read_msg must
    resolve the NEWEST, not a stale earlier one, or the guards evaluate content
    that is not what was quarantined."""
    malformed = env["mail_root"] / "fabrik" / "malformed"
    malformed.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    stale = malformed / f"{pid}.md"
    newest = malformed / f"{pid}.md.1"
    stale.write_text("STALE copy\n", encoding="utf-8")
    newest.write_text("NEWEST copy\n", encoding="utf-8")
    os.utime(stale, (1, 1))
    assert "NEWEST copy" in mail.read_msg(pid, "fabrik")


def test_ack_line_guard_catches_the_cross_case(env):
    """P7-1 (HIGH): the consumer view is read_text()'s — \\r\\n and \\r become \\n,
    everything else survives. A \\r DELIMITER with a non-\\r separator INSIDE the
    line was missed by both union branches (raw has no \\n anchor; fully-
    normalized splits the line) while consumers matched. Guard = consumer view
    ∪ fully-normalized view."""
    for interior in ("\v", "\f", "\x85", "", "", "\x1c", "\x1d", "\x1e"):
        body = f"x\racked-by: fabrik{interior}note · disposition: done\rz"
        with pytest.raises(mail.MailRefusedError, match="ack line"):
            mail.send("fabrik", "finding", body, frm="fabrik-lib")


def test_digest_keeps_counting_a_quarantined_obligation(env):
    """P7-6: a quarantined ack:required message must not vanish from the
    operator's only visibility leg after one alert — malformed/ stays counted."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        (inbox / f"{mail._ulid()}.md").write_text("corrupt\n", encoding="utf-8")
    d1 = mail.digest(days=0)
    assert d1["quarantined"] == 3, f"exactly the parked count, never doubled: {d1}"
    d2 = mail.digest(days=0)
    assert d2["quarantined"] == 3, "idempotent: the same store yields the same count"
    (env["mail_root"] / "fabrik" / "malformed" / "notes.txt").write_text("x", encoding="utf-8")
    d3 = mail.digest(days=0)
    assert d3["quarantined"] == 3, "a non-.md stray never counts"
    # P9-3: a dot-prefixed inbox file is never PARKED (symmetric legs) — so it
    # can neither inflate nor silently vanish from the count.
    (inbox / ".swap.md").write_text("corrupt\n", encoding="utf-8")
    d4 = mail.digest(days=0)
    assert d4["quarantined"] == 3, "a dotfile is not a message"
    assert (inbox / ".swap.md").is_file(), "and it stays where it was"


def test_a_vim_backup_in_malformed_is_not_a_parked_copy(env):
    """P12-1: the probe predicate must match the COUNTING predicate — an
    operator's `<id>.md~` backup (they are told to clear malformed/ by hand)
    was accepted as 'parked' while the count rejected it, so a claimed-away
    corrupt message was counted by NEITHER leg."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    archive = env["mail_root"] / "fabrik" / "archive"
    malformed = env["mail_root"] / "fabrik" / "malformed"
    for d in (inbox, archive, malformed):
        d.mkdir(parents=True, exist_ok=True)
    pid = mail._ulid()
    (malformed / f"{pid}.md~").write_text("vim backup\n", encoding="utf-8")
    f = inbox / f"{pid}.md"
    f.write_text("corrupt\n", encoding="utf-8")
    real_rename = mail.os.rename

    def _peer_claims(src, dst):
        if str(src) == str(f):
            real_rename(src, archive / f"{pid}.md")
            raise FileNotFoundError(str(src))
        return real_rename(src, dst)

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(mail.os, "rename", _peer_claims)
        d = mail.digest(days=0)
    assert d["quarantined"] == 1, f"a backup file is not a parked copy: {d}"


def test_vanished_destination_counts(env):
    """P12-3: cause 3 of the four the comment enumerates — malformed/ removed
    between mkdir and rename. Untested until now."""
    inbox = env["mail_root"] / "fabrik" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{mail._ulid()}.md").write_text("corrupt\n", encoding="utf-8")

    def _dest_gone(src, dst):
        import shutil as _sh

        _sh.rmtree(Path(dst).parent, ignore_errors=True)
        raise FileNotFoundError(str(dst))

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(mail.os, "rename", _dest_gone)
        d = mail.digest(days=0)
    assert d["quarantined"] == 1, f"a vanished destination must count: {d}"


def test_parked_count_predicate_is_bound(env):
    """P12-4: the operator-facing parked count had NO test — three mutations
    (drop the name anchor / the dotfile skip / is_file) all shipped green."""
    malformed = env["mail_root"] / "fabrik" / "malformed"
    malformed.mkdir(parents=True, exist_ok=True)
    (malformed / "01ABC.md").write_text("real copy\n", encoding="utf-8")
    (malformed / "01ABC.md.1").write_text("real numbered copy\n", encoding="utf-8")
    (malformed / "01ABC.md~").write_text("vim backup\n", encoding="utf-8")
    (malformed / "01ABC.md.bak").write_text("operator backup\n", encoding="utf-8")
    (malformed / ".hidden.md").write_text("editor swap\n", encoding="utf-8")
    (malformed / "notes.txt").write_text("note\n", encoding="utf-8")
    (malformed / "adir.md").mkdir()
    d = mail.digest(days=0)
    assert d["quarantined"] == 2, f"exactly the two real copies: {d}"
