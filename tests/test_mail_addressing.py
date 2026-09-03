"""Addressing-enforcement guard tests (plan 2026-08-25-plan-1-mail-dispatcher, Phase A).

The guard makes accidentally-unaddressed HUB-bound mail impossible at send time while
leaving every other path untouched: project mailboxes, fabrik-lib, threaded replies,
deliberate --broadcast. Sandboxed via the same env fixture pattern as test_mail.py —
no test touches the live store.
"""

from __future__ import annotations

import importlib.util
import re as _re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MAIL_PY = _REPO / "scripts" / "mail.py"

spec = importlib.util.spec_from_file_location("fabrik_mail_addr", _MAIL_PY)
mail = importlib.util.module_from_spec(spec)
sys.modules["fabrik_mail_addr"] = mail
spec.loader.exec_module(mail)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    mail_root = tmp_path / "mail"
    opt_root = tmp_path / "opt"
    mail_root.mkdir()
    opt_root.mkdir()
    hook = opt_root / "alpha" / ".claude" / "hooks" / "mail_notify.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# hook\n", encoding="utf-8")
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(opt_root))
    return {"mail_root": mail_root}


# --- the guard: library path (the importable bypass is closed) -----------------


def test_unaddressed_hub_send_is_refused_and_writes_nothing(env):
    with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
        mail.send(to="fabrik", kind="finding", body="x", frm="alpha")
    assert not list((env["mail_root"]).rglob("*.md")), "refusal must write NOTHING"


def test_each_beat_and_broadcast_pass(env):
    for beat in ("infra", "fleet", "intel"):
        assert mail.send(to="fabrik", kind="finding", body=beat, frm="alpha", to_agent=beat).is_file()
    assert mail.send(to="fabrik", kind="finding", body="all", frm="alpha", broadcast=True).is_file()


def test_typoed_beat_is_refused_on_hub_sends(env):
    with pytest.raises(mail.MailRefusedError, match="unknown hub beat"):
        mail.send(to="fabrik", kind="finding", body="x", frm="alpha", to_agent="devops")


def test_broadcast_with_ack_required_is_a_refused_contradiction(env):
    with pytest.raises(mail.MailRefusedError, match="contradiction"):
        mail.send(to="fabrik", kind="finding", body="x", frm="alpha", broadcast=True, ack="required")
    # the EFFECTIVE ack counts: kind=request defaults to ack:required
    with pytest.raises(mail.MailRefusedError, match="contradiction"):
        mail.send(to="fabrik", kind="request", body="x", frm="alpha", broadcast=True)
    assert mail.send(
        to="fabrik", kind="request", body="x", frm="alpha", broadcast=True, ack="no"
    ).is_file()


def test_broadcast_plus_to_agent_means_to_agent_wins(env):
    p = mail.send(
        to="fabrik", kind="finding", body="x", frm="alpha", to_agent="fleet", broadcast=True
    )
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "fleet"


def test_non_hub_mailboxes_are_untouched(env):
    # the guard keys on the LITERAL "fabrik" — fabrik-lib has no beats, projects neither
    assert mail.send(to="fabrik-lib", kind="finding", body="x", frm="fabrik").is_file()
    assert mail.send(to="alpha", kind="finding", body="x", frm="fabrik").is_file()


def test_reply_with_resolvable_parent_is_exempt(env):
    # the real flow: the hub asked ALPHA something; alpha's reply back to the hub
    # threads on the parent sitting in ALPHA's own mailbox — no beat needed.
    parent = mail.send(to="alpha", kind="request", body="q", frm="fabrik")
    pid = parent.stem
    assert mail.send(to="fabrik", kind="reply", body="a", frm="alpha", re=pid).is_file()


def test_prose_re_reply_is_exempt_preserving_the_auto_fail_soft(env):
    """The exemption keys on KIND, never resolvability — a prose/legacy --re reply is the
    sanctioned --auto fail-soft path and must not be re-refused as an addressing problem."""
    assert mail.send(to="fabrik", kind="reply", body="a", frm="alpha", re="prose ref, no parent").is_file()


def test_non_reply_kinds_cannot_bypass_via_a_forged_re(env):
    """kind=request with a resolvable --re is NOT a thread reply — the guard still fires
    (the forged-re bypass the kind-keying exists to close)."""
    parent = mail.send(to="alpha", kind="request", body="q", frm="fabrik")
    with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
        mail.send(to="fabrik", kind="request", body="x", frm="alpha", re=parent.stem)


def test_reply_inherits_the_threads_owner_from_the_parent(env):
    """A resolvable reply keeps the thread OWNED: the parent's agent: is inherited."""
    parent = mail.send(to="alpha", kind="request", body="q", frm="fabrik")
    # forge the parent's addressee the way a hub-side thread would carry it
    text = parent.read_text(encoding="utf-8")
    parent.write_text(text.replace("---\n", "---\nagent: fleet\n", 1), encoding="utf-8")
    reply = mail.send(to="fabrik", kind="reply", body="a", frm="alpha", re=parent.stem)
    assert mail._parse(reply.read_text(encoding="utf-8")).get("agent") == "fleet"


def test_route_off_hub_accepts_free_form_roles(env):
    """Blast-radius twin for route: project mailboxes keep free-form roles — the beat
    check keys on the LITERAL repo "fabrik" only."""
    mid = mail.send(to="alpha", kind="finding", body="b", frm="fabrik").stem
    assert mail.route(mid, "devops", repo="alpha").is_file()


def test_oversize_and_bad_kind_still_outrank_the_addressing_guard(env):
    """Ordering pins beyond the secret check: earlier refusals keep their own diagnosis."""
    with pytest.raises(mail.MailRefusedError, match="64 KB"):
        mail.send(to="fabrik", kind="finding", body="x" * 70000, frm="alpha")
    with pytest.raises(mail.MailRefusedError, match="unknown kind"):
        mail.send(to="fabrik", kind="bogus", body="x", frm="alpha")


def test_secret_refusal_outranks_the_addressing_guard(env):
    # E1: an unaddressed hub send CARRYING a secret is diagnosed as a LEAK first
    with pytest.raises(mail.MailRefusedError, match="secret"):
        mail.send(
            to="fabrik", kind="finding", frm="alpha",
            body="postgres://user:hunter2secret@db:5432/x",
        )


# --- the CLI: exit codes + output contracts ------------------------------------


def test_cli_refusal_exits_2_with_the_beat_guide_on_stderr(env, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("body"))
    rc = mail.main(["send", "--to", "fabrik", "--kind", "finding", "--from", "alpha"])
    assert rc == 2
    err = capsys.readouterr().err
    for beat in ("infra", "fleet", "intel"):
        assert beat in err, f"the guide must name {beat}"


def test_cli_broadcast_keeps_stdout_path_only(env, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("body"))
    rc = mail.main(
        ["send", "--to", "fabrik", "--kind", "finding", "--from", "alpha", "--broadcast"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.strip().splitlines() if ln]
    assert len(lines) == 1 and lines[0].endswith(".md"), "stdout stays path-only"
    assert "broadcast" in captured.err, "the broadcast note belongs on stderr"


def test_hold_still_exits_3_not_2(env, capsys, monkeypatch):
    """MailHoldError subclasses MailRefusedError — the guard must not shadow the
    HOLD branch (a refused auto-reply is exit 3, never 2)."""
    parent = mail.send(to="fabrik", kind="finding", body="p", frm="alpha", to_agent="infra")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("body"))
    rc = mail.main(
        ["send", "--to", "fabrik", "--kind", "reply", "--from", "fabrik",
         "--re", parent.stem, "--auto"]
    )
    assert rc == 3, capsys.readouterr().err


# --- route hardening -----------------------------------------------------------


def test_route_refuses_a_typoed_beat_on_the_hub_mailbox(env):
    mid = mail.send(to="fabrik", kind="finding", body="b", frm="alpha", broadcast=True).stem
    with pytest.raises(mail.MailRefusedError, match="unknown hub beat"):
        mail.route(mid, "inrfa", repo="fabrik")
    assert mail._parse(mail.read_msg(mid, "fabrik")).get("agent") is None


def test_route_clear_stays_legal_on_the_hub_mailbox(env):
    mid = mail.send(to="fabrik", kind="finding", body="b", frm="alpha", to_agent="infra").stem
    mail.route(mid, "", repo="fabrik")
    assert mail._parse(mail.read_msg(mid, "fabrik")).get("agent") is None


# --- static caller pins (the census lesson: callers are READ, never grep'd) ----

_ROTATE_SYSADMIN = _REPO / "scripts" / "sysadmin" / "claude_rotate.py"
_ROTATE_AROWAKE = _REPO / "scripts" / "aro-wake" / "claude_rotate.py"
_KAIZEN = _REPO / "scripts" / "sysadmin" / "kaizen_collect_v2.py"


def test_drain_mail_sends_broadcast_in_both_twin_copies():
    for copy in (_ROTATE_SYSADMIN, _ROTATE_AROWAKE):
        src = copy.read_text(encoding="utf-8")
        m = _re.search(r"def _drain_mail.*?(?=\ndef |\Z)", src, _re.S)
        assert m, f"{copy.name}: _drain_mail not found"
        assert '"--broadcast"' in m.group(0), (
            f"{copy.name}: _drain_mail argv must carry --broadcast"
        )


def test_rotate_twin_copies_are_byte_identical():
    assert _ROTATE_SYSADMIN.read_bytes() == _ROTATE_AROWAKE.read_bytes(), (
        "the header's twin invariant: sysadmin and aro-wake copies must stay byte-identical"
    )


def test_kaizen_sends_one_addressed_obligation_per_beat():
    """The kaizen hand-off is each beat's PASS TRIGGER (infra.md/fleet.md) — it must stay
    an ADDRESSED ack:required obligation per beat, never a sweepable ownerless broadcast."""
    src = _KAIZEN.read_text(encoding="utf-8")
    m = _re.search(r'for beat in \("infra", "fleet"\):.*?"send",.*?\]', src, _re.S)
    assert m, "kaizen per-beat addressed send loop not found"
    argv = " ".join(m.group(0).split())  # formatting-insensitive: the source is ruff-formatted one arg per line
    assert '"--to-agent", beat' in argv, argv
    assert '"--broadcast"' not in argv and '"--ack"' not in argv, (
        "the obligation must keep kind-default ack:required and never broadcast: " + argv
    )


def test_a_lane_may_mail_its_own_repo(monkeypatch, env):
    """01M1K6H6 (wef1, 2026-09-03): `--from wef1 --to web-ecommerce-factory` was refused as
    project→project because the guard compared the free-text lane name to the recipient. The
    SENDING REPO decides topology: a lane in web-ecommerce-factory mailing web-ecommerce-factory is
    the same-repo handoff the constitution advertises."""
    monkeypatch.setattr(mail, "_current_repo", lambda: "web-ecommerce-factory")
    monkeypatch.setattr(mail, "_valid_recipient", lambda to: True)
    p = mail.send("web-ecommerce-factory", "finding", "WHAT: a\nWHERE: b\nWHEN: c\nWHO: d\nWHY: e\nHOW: f\nSYSTEMIC: g\n", ack="no", frm="wef1")
    assert p.parent.name == "inbox" and "web-ecommerce-factory" in str(p)
    with pytest.raises(mail.MailRefusedError):  # a lane in one project still cannot mail ANOTHER project
        mail.send("youtube", "finding", "x", ack="no", frm="wef1")
