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
    assert not any((env["mail_root"] / "fabrik").rglob("*.md")) if (env["mail_root"] / "fabrik").exists() else True


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
    p = mail.send(to="fabrik", kind="request",
                  body="the boss said acked-by: someone should handle this", frm="alpha")
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
        mail.send(to="fabrik", kind="finding", body="Authorization: Bearer abcdef1234567890XYZ", frm="alpha")
    with pytest.raises(mail.MailRefusedError):
        mail.send(to="fabrik", kind="finding", body="db at postgresql://user:s3cretpass@host:5432/db", frm="alpha")


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
        mail.send(to="fabrik", kind="finding", body="cache at redis://:sup3rs3cr3tpw@10.99.0.1:6379/0", frm="alpha")


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
    assert "do X" in back.read_text()            # body survives the strip


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
    import subprocess, sys as _sys, os as _os
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
    r = subprocess.run([_sys.executable, "-c", probe], capture_output=True, text=True,
                       timeout=30, env=env_vars, cwd=str(repo_root))
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
    import os as _os, time as _time
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
    import os as _os, time as _time
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
