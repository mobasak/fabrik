"""Escalation-digest tests (plan 2026-08-25-plan-1-mail-dispatcher, Phase B).

Fully sandboxed: FABRIK_MAIL_ROOT tmp redirect, `_resolve_sender` monkeypatched —
no test touches the live mailbox, crontab, or Telegram (importing mail_escalate
never imports libs.alerting — the lazy seam is itself under test).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "mail_escalate", _REPO / "scripts" / "sysadmin" / "mail_escalate.py"
)
me = importlib.util.module_from_spec(_spec)
sys.modules["mail_escalate"] = me
_spec.loader.exec_module(me)

DAYS = 3 * 86400


def _msg(
    root: Path,
    repo: str,
    name: str,
    *,
    ack="required",
    agent="",
    ts=None,
    body="b",
    acked=False,
    sub="inbox",
):
    ts = ts or dt.datetime.now(dt.UTC).isoformat()
    d = root / repo / sub
    d.mkdir(parents=True, exist_ok=True)
    agent_line = f"agent: {agent}\n" if agent else ""
    tail = "\nacked-by: fabrik · disposition: done\n" if acked else ""
    (d / f"{name}.md").write_text(
        f"---\nid: {name}\nfrom: {repo}\nto: fabrik\nts: {ts}\nre: \nkind: request\nack: {ack}\n{agent_line}---\n{body}\n{tail}",
        encoding="utf-8",
    )
    return d / f"{name}.md"


def _old_ts(days: float) -> str:
    return (dt.datetime.now(dt.UTC) - dt.timedelta(days=days)).isoformat()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    root = tmp_path / "mail"
    root.mkdir()
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(root))
    monkeypatch.delenv("FABRIK_MAIL_ESCALATE_DAYS", raising=False)
    monkeypatch.setattr(me, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(me, "DAY_STAMP", tmp_path / "state" / "day-stamp")
    monkeypatch.setattr(me, "DAY_STAMP_AGENT", tmp_path / "state" / "day-stamp-agent")
    return root


def test_addressed_but_unacked_still_escalates(env):
    """The population is UNACKED, never unaddressed — an agent-routed message that
    nobody acked MUST appear (the escalation blind spot the reviews killed)."""
    _msg(env, "fabrik", "01AAAAAAAAAAAAAAAAAAAAAAAA", agent="infra", ts=_old_ts(4))
    obs = me.collect_obligations(env)
    assert [o.ulid for o in obs] == ["01AAAAAAAAAAAAAAAAAAAAAAAA"]
    assert obs[0].agent == "infra"


def test_archive_strand_and_resolving_window_are_included(env):
    _msg(env, "fabrik", "01BBBBBBBBBBBBBBBBBBBBBBBB", ts=_old_ts(5), sub="archive")
    w = env / "fabrik" / "archive" / "01CCCCCCCCCCCCCCCCCCCCCCCC.md.resolving.1"
    w.write_text("x", encoding="utf-8")
    old = time.time() - 4 * 86400
    os.utime(w, (old, old))
    kinds = {o.kind for o in me.collect_obligations(env)}
    assert kinds == {"strand", "window"}


def test_resolved_archive_mail_is_not_a_strand(env):
    _msg(env, "fabrik", "01DDDDDDDDDDDDDDDDDDDDDDDD", ts=_old_ts(5), sub="archive", acked=True)
    assert me.collect_obligations(env) == []


def test_all_mailboxes_are_scanned_not_just_the_hub(env):
    _msg(env, "transdoc", "01EEEEEEEEEEEEEEEEEEEEEEEE", ts=_old_ts(4))
    assert [o.repo for o in me.collect_obligations(env)] == ["transdoc"]


def test_dotfiles_never_escalate_in_any_leg(env):
    """P13-6 proper: the ARCHIVE dotfile is the leg that would escalate forever."""
    for sub in ("inbox", "archive"):
        f = _msg(env, "fabrik", "01FFFFFFFFFFFFFFFFFFFFFFFF", ts=_old_ts(4), sub=sub)
        f.rename(f.with_name("." + f.name))
    w = env / "fabrik" / "archive" / ".01XFFFFFFFFFFFFFFFFFFFFFFF.md.resolving.1"
    w.write_text("x", encoding="utf-8")
    old = time.time() - 4 * 86400
    os.utime(w, (old, old))
    assert me.collect_obligations(env) == []


def test_threshold_is_inclusive_at_exactly_n_days(env):
    _msg(env, "fabrik", "01GGGGGGGGGGGGGGGGGGGGGGGG", ts=_old_ts(3.0001))
    _msg(env, "fabrik", "01HHHHHHHHHHHHHHHHHHHHHHHH", ts=_old_ts(2.9))
    assert [o.ulid for o in me.collect_obligations(env)] == ["01GGGGGGGGGGGGGGGGGGGGGGGG"]


def test_aged_comparator_is_inclusive_at_the_exact_boundary():
    """Wall-clock can never hit the boundary exactly — the comparator is unit-pinned so
    the `>=` → `>` mutation dies (both scan legs route through _aged)."""
    assert me._aged(86400.0, 86400.0) is True
    assert me._aged(86399.999, 86400.0) is False


def test_env_override_and_garbage_fallback(env, monkeypatch):
    """The documented override mechanism, proven: DAYS=10 spares a 5-day-old message;
    garbage warns and uses the default 3 (so the same message escalates)."""
    _msg(env, "fabrik", "01RRRRRRRRRRRRRRRRRRRRRRRR", ts=_old_ts(5))
    monkeypatch.setenv("FABRIK_MAIL_ESCALATE_DAYS", "10")
    assert me.collect_obligations(env) == []
    monkeypatch.setenv("FABRIK_MAIL_ESCALATE_DAYS", "abc")
    assert [o.ulid for o in me.collect_obligations(env)] == ["01RRRRRRRRRRRRRRRRRRRRRRRR"]


def test_ack_no_never_escalates(env):
    _msg(env, "fabrik", "01JJJJJJJJJJJJJJJJJJJJJJJJ", ack="no", ts=_old_ts(10))
    assert me.collect_obligations(env) == []


def test_broken_ts_escalates_and_renders_sanely(env):
    _msg(env, "fabrik", "01KKKKKKKKKKKKKKKKKKKKKKKK", ts="not-a-timestamp")
    obs = me.collect_obligations(env)
    assert len(obs) == 1
    assert me._fmt_age(obs[0].age_days) == ">999d"


def test_digest_caps_rows_and_the_count_line_survives(env):
    items = [
        me.Obligation(
            ulid=f"01M{i:023d}",
            repo="repo_`x`",
            sender="x_y*z",
            agent="[a]",
            age_days=5 + i,
            kind="inbox",
        )
        for i in range(50)
    ]
    text = me.build_digest(items)
    assert "+30 more (50 total)" in text
    assert len(text) <= 3900
    for meta in "_*[]`":
        assert meta not in text, f"Markdown metachar {meta!r} must be sanitized (all fields)"


def test_budget_trim_drops_rows_and_recounts_from_the_final_set(monkeypatch):
    """The trim loop is unreachable at the real budget with MAX_ROWS=20 (by construction) —
    proven live under an artificial budget so the drop-the-loop mutation dies and the
    count-from-final-set order is pinned."""
    monkeypatch.setattr(me, "BODY_BUDGET", 300)
    items = [
        me.Obligation(
            ulid=f"01M{i:023d}", repo="fabrik", sender="s", agent="-", age_days=5 + i, kind="inbox"
        )
        for i in range(20)
    ]
    text = me.build_digest(items)
    rows = text.splitlines()
    assert len(rows) < 21, "rows must have been trimmed"
    kept = len(rows) - 1
    assert f"+{20 - kept} more (20 total)" in rows[-1], rows[-1]


def test_digest_leads_with_the_oldest(env):
    _msg(env, "fabrik", "01YOUNGYOUNGYOUNGYOUNGYYYY", ts=_old_ts(4))
    _msg(env, "fabrik", "01OLDESTOLDESTOLDESTOLDEST", ts=_old_ts(40))
    items = me.collect_obligations(env)
    text = me.build_digest(items)
    assert text.splitlines()[0].startswith("01OLDESTOLDESTOLDESTOLDEST"), (
        "the longest-rotted obligation must lead the digest"
    )


def test_the_real_agent_leg_delivers_an_addressed_ack_no_finding(env, monkeypatch, tmp_path):
    """The REAL `_deliver_to_agent`, not a monkeypatch — the three claims its docstring makes are
    each one argv token, and every other test in this file patches the function away, so three
    mutations survived the whole suite: `--ack no` -> `--ack required` (re-opens the recursion the
    docstring calls load-bearing), dropping `--to-agent infra` (mail.py REFUSES an unaddressed
    hub-bound send, rc 2 — the leg dead on arrival, silently, into a cron log nobody reads), and
    `--to fabrik` -> a bad repo (same). A claim in a docstring that no grader executes is a claim
    that can silently become false (review round 1)."""
    assert me._deliver_to_agent("Subject: probe\n\nWHAT: a probe row\n") is True
    delivered = sorted((env / "fabrik" / "inbox").glob("*.md"))
    assert delivered, "the real agent leg wrote nothing into the sandbox mailbox"
    fm = delivered[-1].read_text(encoding="utf-8")
    assert "\nack: no\n" in fm, f"--ack no is load-bearing and did not land:\n{fm[:400]}"
    assert "\nagent: infra\n" in fm, f"--to-agent infra did not land:\n{fm[:400]}"
    assert "\nto: fabrik\n" in fm, f"--to fabrik did not land:\n{fm[:400]}"


def test_an_ack_no_window_is_not_an_obligation(env):
    """The delta's HEADLINE fix and it had no grader: both existing window tests write the literal
    "x" into the `.md.resolving` file, so `_mail._parse` returns None and the new `ack` filter is
    never reached — deleting the filter entirely passed the whole suite. A window IS the message,
    so this one writes real frontmatter (review round 2)."""
    old = _old_ts(9)
    arch = env / "fabrik" / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "01DIGESTDIGESTDIGESTDIGEST.md.resolving.1").write_text(
        f"---\nid: 01DIGESTDIGESTDIGESTDIGEST\nfrom: fabrik\nto: fabrik\nts: {old}\n"
        "kind: finding\nack: no\nagent: infra\n---\nrows\n",
        encoding="utf-8",
    )
    (arch / "01REALREALREALREALREALREAL.md.resolving.2").write_text(
        f"---\nid: 01REALREALREALREALREALREAL\nfrom: x\nto: fabrik\nts: {old}\n"
        "kind: finding\nack: required\n---\nbody\n",
        encoding="utf-8",
    )
    for f in arch.glob("*.resolving.*"):
        os.utime(f, (time.time() - 9 * 86400,) * 2)
    got = {o.ulid for o in me.collect_obligations(env)}
    assert "01DIGESTDIGESTDIGESTDIGEST" not in got, "the digest counted ITSELF — permanently"
    assert "01REALREALREALREALREALREAL" in got, "a real obligation window must still count"


def test_a_lock_failure_that_is_not_contention_proceeds_rather_than_silencing(
    env, monkeypatch, capsys
):
    """The lock must fail OPEN. A bare `except OSError` covered `mkdir`/`open` too, so an unwritable
    state dir printed "another run holds the lock" and returned 0 — the digest silenced FOREVER
    behind a message that reads as benign contention, while every other leg in this module fails
    open by design ("a duplicate beats permanent silence")."""
    _msg(env, "fabrik", "01LOCKLOCKLOCKLOCKLOCKLOCK", ts=_old_ts(9))
    delivered: list = []
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: delivered.append(body) or True)

    def boom(*a, **k):
        raise PermissionError(13, "state dir is read-only")

    # module-global shadow, NOT the process-wide builtins dict: a bare `open()` resolves module
    # globals before builtins, so this reaches main()'s lock and nothing else in the interpreter.
    monkeypatch.setattr(me, "open", boom, raising=False)
    assert me.main() == 0
    out = capsys.readouterr().out
    assert "proceeding UNLOCKED" in out, out[:300]
    assert delivered, "a non-contention lock failure must NOT silence the digest"


def test_a_second_concurrent_run_is_excluded_by_the_scripts_own_lock(env, monkeypatch, capsys):
    """The `flock` lives in the operator-installed CRON LINE, which guards cron against cron and
    nothing else. Since the agent leg exists, a hand run does not merely cost an extra Telegram —
    it DELIVERS a duplicate `finding` into the hub inbox and stamps the day, so the next cron run
    is suppressed and the real digest is never produced. Removing the flock passed the suite."""
    import fcntl as _fcntl

    _msg(env, "fabrik", "01CONCURRENTCONCURRENTCON", ts=_old_ts(9))
    me.STATE_DIR.mkdir(parents=True, exist_ok=True)
    holder = open(me.STATE_DIR / "run.lock", "w")  # noqa: SIM115 — held for the assertion
    # SHARED on purpose: a LOCK_EX holder excludes a LOCK_SH acquirer too, so an EX->SH
    # regression in the script would pass against an EX holder. Only an EXCLUSIVE acquire is
    # excluded by a SHARED holder, which is exactly the property under test (review round 3).
    _fcntl.flock(holder, _fcntl.LOCK_SH | _fcntl.LOCK_NB)
    delivered: list = []
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: delivered.append(body) or True)
    try:
        # ⚠️ BOUNDED. A LOCK_NB regression deadlocks against the lock THIS test holds, so an
        # unbounded call wedges the suite instead of failing it — and pytest-timeout is not
        # installed here, so nothing else bounds it (review round 3).
        rc: list = []
        worker = threading.Thread(target=lambda: rc.append(me.main()), daemon=True)
        worker.start()
        worker.join(10)
        assert not worker.is_alive(), "main() blocked on the lock — LOCK_NB is gone"
        assert rc == [0]
    finally:
        _fcntl.flock(holder, _fcntl.LOCK_UN)
        holder.close()
    out = capsys.readouterr().out
    assert "another run holds the lock" in out, out[:300]
    assert not delivered, "a concurrent run delivered a DUPLICATE into the measured mailbox"
    assert not me.DAY_STAMP_AGENT.exists(), "and it would have stamped the day out from under cron"


def test_the_agent_leg_attributes_the_digest_to_the_hub_whatever_the_cwd(
    env, monkeypatch, tmp_path
):
    """`mail.py` derives the `from:` field from the cwd's git worktree, so an inherited cwd would
    attribute the hub's own digest to whatever repo the caller stood in. pytest's cwd is already
    the repo root, so the existing real-leg grader could not see this — the test must LEAVE it."""
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert me._deliver_to_agent("Subject: probe\n\nWHAT: a row\n") is True
    delivered = sorted((env / "fabrik" / "inbox").glob("*.md"))
    assert delivered, "the real agent leg wrote nothing"
    fm = delivered[-1].read_text(encoding="utf-8")
    assert f"\nfrom: {me._REPO_ROOT.name}\n" in fm, (
        f"the digest was attributed to the caller's cwd, not the hub:\n{fm[:300]}"
    )


def test_a_skipped_leg_is_logged_as_skipped_not_ok(env, monkeypatch, capsys):
    """`ok`/`agent_ok` are seeded from the STAMP, so three of the four daily runs printed
    `send=OK · agent=OK` having sent nothing — the same shape as the failure this whole change
    exists to end ("logged send=OK while the inbox grew to 132"). The cron log is the only evidence
    a cron leaves."""
    _msg(env, "fabrik", "01SKIPSKIPSKIPSKIPSKIPSKIP", ts=_old_ts(9))
    me.STATE_DIR.mkdir(parents=True, exist_ok=True)
    me.DAY_STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    assert me.main() == 0
    out = capsys.readouterr().out
    assert "send=skipped" in out, f"a stamp-suppressed leg must not read as OK:\n{out[:300]}"
    assert "agent=OK" in out, out[:300]


def test_the_agent_digest_carries_a_subject_and_the_message_contract(env, monkeypatch):
    """The agent used to receive a bare column of ULIDs: no subject, and zero of the seven D-035
    sections the hub enforces on every other sender — `mail.py`'s advisory went to stderr, which
    the success path discarded, so it was unobservable (review round 1)."""
    body = me._agent_body(
        "fabrik-mail: 3 unacked obligation(s)", "01AAA · r · s · 9d · - (inbox)", 3
    )
    assert body.startswith("Subject: "), body[:80]
    for section in ("WHAT", "WHO", "WHERE", "WHEN", "WHY", "HOW", "SYSTEMIC"):
        assert f"{section}:" in body, f"D-035 section {section} missing from the delivered digest"
    assert "01AAA · r · s · 9d · - (inbox)" in body, "the rows must survive the preamble"
    # ⚠️ EVERY mail.py command the digest prints must carry `--repo`, as a CLASS rather than the
    # three instances. This script scans every mailbox and 94% of rows are not the hub's, so a
    # command without it fails — and for `route` the refusal reads "an archived message is settled
    # history", which tells the reader the obligation is closed when it is not (review round 3).
    import re as _re

    cmds = _re.findall(r"`mail\.py (\w+) <id>([^`]*)`", body)
    assert cmds, f"no mail.py commands found in the digest body:\n{body[:400]}"
    for verb, rest in cmds:
        assert "--repo <repo>" in rest, f"`mail.py {verb} <id>{rest}` omits --repo"


def test_the_digest_also_reaches_an_agent_not_only_the_operator(env, monkeypatch, capsys):
    """THE reason this backlog grew to 132 with a 10-day-old oldest while this cron ran every 6h
    and reported `send=OK`: the only delivery leg is a Telegram to the OPERATOR, whose standing
    directive is "i dont read anything, you read". `feedback_relay.py` learned this already — its
    docstring says the digest "was operator-facing, and the operator does not read dashboards …
    This relay makes an AGENT the reader". mail_escalate never got that leg, so nobody who could
    ACT was ever told. The digest must also land in the `fabrik` inbox addressed to `infra`, where
    the handle-now law binds the session that opens it.

    ⚠️ `ack: no` is load-bearing: an `ack: required` digest would count itself as an obligation on
    the next run and the number would never fall."""
    _msg(env, "fabrik", "01OLDESTOLDESTOLDESTOLDEST", ts=_old_ts(40))
    sent: list = []
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: sent.append((t, b)) or True))
    mailed: list = []
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: mailed.append(body) or True)
    assert me.main() == 0
    assert mailed, "the digest never reached an agent mailbox — operator-only delivery is the bug"
    assert "01OLDESTOLDESTOLDESTOLDEST" in mailed[0], mailed[0][:300]


def test_the_agent_leg_alone_is_enough_to_stamp_the_day(env, monkeypatch, capsys):
    """The mailbox leg is LOCAL — no ssh, no DNS — while the Telegram leg goes over the network and
    has failed individual RUNS (2026-09-12: two of that day's runs, an ssh timeout then a name-
    resolution failure, before the third succeeded — no day in the log is fully undelivered). Each
    leg carries its OWN stamp and is retried independently, so the agent gets the day's digest even
    when the operator leg is down, and vice versa."""
    _msg(env, "fabrik", "01NNNNNNNNNNNNNNNNNNNNNNNN", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: False))  # Telegram down
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    assert me.main() == 0
    # ⚠️ its OWN stamp. A single shared stamp let a Telegram success suppress the whole day, so one
    # transient agent-leg failure cost the agent that day's digest entirely and the later runs all
    # printed "already sent today" — inverting this change's own purpose (review round 1).
    assert me.DAY_STAMP_AGENT.exists(), "the agent leg delivered — its own day must be stamped"
    assert not me.DAY_STAMP.exists(), "the operator leg FAILED — it must be retried, not suppressed"


def test_total_delivery_failure_leaves_no_stamp(env, monkeypatch, capsys):
    """Both legs down must still retry in <=6h — the pre-existing contract, kept."""
    _msg(env, "fabrik", "01NNNNNNNNNNNNNNNNNNNNNNNN", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: False))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: False)
    assert me.main() == 0
    assert not me.DAY_STAMP.exists(), "no leg delivered — a stamp would silence the whole day"


def test_fmt_age_caps_finite_values_too():
    assert me._fmt_age(1200.0) == ">999d"
    assert me._fmt_age(12.4) == "12d"


def test_day_stamp_only_after_success_and_carries_local_date(env, monkeypatch, capsys):
    _msg(env, "fabrik", "01NNNNNNNNNNNNNNNNNNNNNNNN", ts=_old_ts(4))
    sent = []
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: sent.append((t, b)) or False))
    # since the agent leg was added, "no stamp" means NO leg delivered — pin both, or a live
    # agent leg delivers, stamps the day honestly, and this reads as a regression
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: False)
    assert me.main() == 0
    assert not me.DAY_STAMP.exists(), "no leg delivered — a stamp would silence the whole day"
    assert "FAILED" in capsys.readouterr().out
    (title, body) = sent[0]
    assert "1 unacked obligation" in title, title
    assert "01NNNNNNNNNNNNNNNNNNNNNNNN" in body and "fabrik" in body, body
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    assert me.main() == 0
    assert me.DAY_STAMP.read_text(encoding="utf-8").strip() == dt.date.today().isoformat()


def test_todays_stamp_suppresses_a_second_send(env, monkeypatch):
    _msg(env, "fabrik", "01PPPPPPPPPPPPPPPPPPPPPPPP", ts=_old_ts(4))
    me.STATE_DIR.mkdir(parents=True, exist_ok=True)
    me.DAY_STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")
    me.DAY_STAMP_AGENT.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    def boom():
        raise AssertionError("must not resolve a sender today")

    def boom_agent(_body):
        raise AssertionError("must not deliver to the agent today")

    monkeypatch.setattr(me, "_resolve_sender", boom)
    monkeypatch.setattr(me, "_deliver_to_agent", boom_agent)
    assert me.main() == 0


def test_one_stamped_leg_does_not_suppress_the_other(env, monkeypatch, capsys):
    """The per-leg stamp's whole point: the OPERATOR leg already went out today, so it must not
    re-send — and the AGENT leg, which has not, must still run. Under the single shared stamp the
    agent silently lost the day (review round 1)."""
    _msg(env, "fabrik", "01RRRRRRRRRRRRRRRRRRRRRRRR", ts=_old_ts(4))
    me.STATE_DIR.mkdir(parents=True, exist_ok=True)
    me.DAY_STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    def boom():
        raise AssertionError("the operator leg is already stamped — it must not re-send")

    delivered: list = []
    monkeypatch.setattr(me, "_resolve_sender", boom)
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: delivered.append(body) or True)
    assert me.main() == 0
    assert delivered, "the agent leg was suppressed by the OPERATOR's stamp"
    assert me.DAY_STAMP_AGENT.exists()


def test_no_obligations_means_no_send(env, monkeypatch, capsys):
    monkeypatch.setattr(me, "_resolve_sender", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    assert me.main() == 0
    assert "0 aged obligations" in capsys.readouterr().out


def test_importing_the_module_never_imports_libs_alerting():
    assert "libs.alerting" not in sys.modules, (
        "the lazy seam exists so a test process never runs alerting's import-time dotenv load"
    )


def test_stamp_carries_the_send_moment_local_date_even_across_utc_midnight(env, monkeypatch):
    """The plan's TZ row: a run at 22:30 UTC on this +03 box is 01:30 LOCAL next day —
    the stamp must carry the LOCAL date so the next run's dedup reads it correctly."""
    _msg(env, "fabrik", "01QQQQQQQQQQQQQQQQQQQQQQQQ", ts=_old_ts(4))

    class _FakeDate(dt.date):
        @classmethod
        def today(cls):
            # what date.today() returns at 22:30 UTC on a +03 box: the NEXT local day
            return dt.date(2026, 8, 27)

    monkeypatch.setattr(me._dt, "date", _FakeDate)
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    # ⚠️ PIN THE AGENT LEG. Every other main() test does; this one was missed, so it spawned a
    # REAL `mail.py send` subprocess on every suite run — and the only thing keeping that out of
    # the live /opt/fabrik-mail store was the `env` fixture's FABRIK_MAIL_ROOT redirect, not the
    # `_resolve_sender` patch the module docstring credits. A test that writes to the live store
    # if one fixture line changes is not "fully sandboxed" (review round 1).
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    assert me.main() == 0
    assert me.DAY_STAMP.read_text(encoding="utf-8").strip() == "2026-08-27"


def test_send_raising_is_fail_soft(env, monkeypatch, capsys):
    """The contract-falsifier the review caught: a RAISING sender must never crash the
    cron — exit 0, loud, no stamp."""
    _msg(env, "fabrik", "01SSSSSSSSSSSSSSSSSSSSSSSS", ts=_old_ts(4))

    def exploder(t, b):
        raise RuntimeError("apprise leg exploded")

    monkeypatch.setattr(me, "_resolve_sender", lambda: exploder)
    # the AGENT leg is pinned down too: the no-stamp rule is about TOTAL failure, and since
    # the agent leg was added a live one would deliver and legitimately stamp the day
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: False)
    assert me.main() == 0
    out = capsys.readouterr().out
    assert "send raised RuntimeError" in out and "FAILED" in out
    assert not me.DAY_STAMP.exists()


def test_stamp_write_failure_after_delivery_warns_never_crashes(env, monkeypatch, capsys):
    """The duplicate-storm falsifier: delivered send + unwritable stamp path must warn
    and exit 0 (a loud duplicate next run beats a crash-loop)."""
    _msg(env, "fabrik", "01TTTTTTTTTTTTTTTTTTTTTTTT", ts=_old_ts(4))
    me.DAY_STAMP.mkdir(parents=True)  # a DIRECTORY occupying the stamp slot
    me.DAY_STAMP_AGENT.mkdir(parents=True)  # both slots, so the warning path is the one under test
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    assert me.main() == 0
    assert "day-stamp write failed" in capsys.readouterr().out


def test_one_unreadable_mailbox_does_not_silence_the_rest(env, monkeypatch, capsys):
    _msg(env, "fabrik", "01UUUUUUUUUUUUUUUUUUUUUUUU", ts=_old_ts(4))

    real = me._scan_repo

    def boom(repo_dir, threshold):
        if repo_dir.name == "broken":
            raise OSError("permission denied")
        return real(repo_dir, threshold)

    (env / "broken" / "inbox").mkdir(parents=True)
    monkeypatch.setattr(me, "_scan_repo", boom)
    obs = me.collect_obligations(env)
    assert [o.ulid for o in obs] == ["01UUUUUUUUUUUUUUUUUUUUUUUU"]
    assert "skipping broken" in capsys.readouterr().out


def test_the_digest_says_what_shape_the_count_is(env):
    """⚠️ `83 row(s)` reads as 83 work items. Measured 2026-09-20 on the live store, it was EIGHT
    distinct facts: 41 of the 83 were ONE fabrik-lib broadcast sitting in 41 different mailboxes,
    and 39 more were the hub's own sends. An agent handed the bare number sizes the job an order
    of magnitude wrong, and the digest's own SYSTEMIC line already warns that the count is not the
    population — it just never said what the population was.

    Grouping by SENDER is free (the field is already on `Obligation`, no extra read) and it is
    exactly the broadcast signature: one sender, N rows, N distinct mailboxes.
    """
    items = [
        me.Obligation(
            ulid=f"01M{i:023d}",
            repo=f"repo{i}",
            sender="fabrik-lib",
            agent="-",
            age_days=20.0,
            kind="inbox",
        )
        for i in range(41)
    ] + [
        me.Obligation(
            ulid=f"01N{i:023d}",
            repo=f"other{i}",
            sender="fabrik",
            agent="-",
            age_days=9.0,
            kind="inbox",
        )
        for i in range(3)
    ]
    shape = me._shape_line(items)
    assert "fabrik-lib" in shape and "41" in shape, shape
    assert "41 mailbox" in shape, f"a broadcast is N rows across N mailboxes — say so: {shape}"
    assert "fabrik" in shape, shape
    # and it reaches the delivered body, which is the only place an agent reads
    body = me._agent_body("t", "01AAA · r · s · 9d · - (inbox)", len(items), items)
    assert "SHAPE:" in body, "the shape must be a labelled section, not buried in prose"
    assert shape in body, body[:400]


def test_the_shape_line_says_nothing_clever_about_a_single_row(env):
    """One obligation from one sender is not a broadcast, and the line must not imply it is."""
    one = [
        me.Obligation(
            ulid="01M" + "0" * 23, repo="r", sender="s", agent="-", age_days=9.0, kind="inbox"
        )
    ]
    shape = me._shape_line(one)
    assert "broadcast" not in shape.lower(), shape
    assert "1" in shape and "s" in shape, shape


# ── the OWNER leg: each agent takes care of its own mail (operator ruling 2026-09-20) ──────────


def test_each_overdue_obligation_is_escalated_to_its_own_repos_mailbox(env):
    """⚠️ THE WHOLE POINT. Before this leg the digest had ONE destination — the hub mailbox
    addressed to `infra` — so the agent bound by the handle-now law was handed other repos' work
    and could discharge none of it. Measured on the live store 2026-09-20: of 83 rows, ZERO were
    obligations on the hub. Operator ruling: "each agent should take care of its own mails."
    """
    _msg(env, "youtube", "01Y" + "0" * 23, ts=_old_ts(9))
    _msg(env, "youtube", "01Y" + "1" * 23, ts=_old_ts(8))
    _msg(env, "transdoc", "01T" + "0" * 23, ts=_old_ts(7))
    items = me.collect_obligations(env)
    assert len(items) == 3

    sent, failed = me._deliver_to_owners(items, "2026-09-20")
    assert failed == 0, failed
    assert sent == 2, f"one message per OWNING repo, not one per row: {sent}"

    yt = sorted((env / "youtube" / "inbox").glob("*.md"))
    td = sorted((env / "transdoc" / "inbox").glob("*.md"))
    # each repo's own overdue rows are already in its inbox; the escalation is the extra one
    assert len(yt) == 3 and len(td) == 2, (len(yt), len(td))
    body = max(yt, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    assert "01Y" + "0" * 23 in body and "01Y" + "1" * 23 in body, "youtube's own rows"
    assert "01T" + "0" * 23 not in body, "another repo's rows must NOT be in youtube's escalation"


def test_the_owner_escalation_is_never_itself_an_obligation(env):
    """⚠️ THE COBRA, and it is the same one the agent leg's docstring already names. The cheapest
    way to satisfy "escalate to owners" WITHOUT the outcome is to send a message nobody acks — and
    if that message were `ack: required` it would be counted by the very next run, so the number
    could never fall and the mechanism would feed itself, 40 mailboxes at a time.
    """
    _msg(env, "youtube", "01Y" + "0" * 23, ts=_old_ts(9))
    before = len(me.collect_obligations(env))
    me._deliver_to_owners(me.collect_obligations(env), "2026-09-20")
    # the escalation is fresh, so age alone would not count it yet — assert the FIELD, which is
    # what makes it true a week from now too
    newest = max((env / "youtube" / "inbox").glob("*.md"), key=lambda p: p.stat().st_mtime)
    assert "\nack: no\n" in newest.read_text(encoding="utf-8"), (
        "an ack=required escalation becomes an obligation on the next run and the count never falls"
    )
    assert len(me.collect_obligations(env)) == before, "the escalation must not grow the count"


def test_a_repo_is_escalated_at_most_once_a_day(env):
    """The cron runs every 6 hours. Without a per-repo day stamp the fleet takes four copies of
    the same list daily, which is how a useful signal becomes noise nobody reads."""
    _msg(env, "youtube", "01Y" + "0" * 23, ts=_old_ts(9))
    items = me.collect_obligations(env)
    first, _ = me._deliver_to_owners(items, "2026-09-20")
    second, _ = me._deliver_to_owners(items, "2026-09-20")
    assert (first, second) == (1, 0), (first, second)
    # a NEW day escalates again — the obligation is still open and still owed
    third, _ = me._deliver_to_owners(items, "2026-09-21")
    assert third == 1, third


def test_the_hub_is_not_double_delivered_its_own_rows(env):
    """infra's digest already carries every row including the hub's, so a per-repo delivery to
    `fabrik` would put the same obligations in the same mailbox twice."""
    _msg(env, "fabrik", "01F" + "0" * 23, ts=_old_ts(9))
    _msg(env, "youtube", "01Y" + "0" * 23, ts=_old_ts(9))
    sent, _ = me._deliver_to_owners(me.collect_obligations(env), "2026-09-20")
    assert sent == 1, "only youtube — the hub reads infra's digest"
    assert len(list((env / "fabrik" / "inbox").glob("*.md"))) == 1, "no self-delivery"


def test_the_owner_leg_still_runs_on_a_day_the_other_two_legs_already_fired(env, monkeypatch):
    """⚠️ THE WIRING, which is the half that goes ungraded. `main`'s early exit short-circuits on
    the operator+agent stamps, and those fire on the day's FIRST run while the cron runs four
    times. Leave the owner leg out of that condition and it never runs on almost any day — the
    mechanism ships, the tests pass, and no repo is ever told."""
    _msg(env, "youtube", "01Y" + "0" * 23, ts=_old_ts(9))
    import datetime as _dt

    today = _dt.date.today().isoformat()
    me.STATE_DIR.mkdir(parents=True, exist_ok=True)
    me.DAY_STAMP.write_text(today + "\n", encoding="utf-8")
    me.DAY_STAMP_AGENT.write_text(today + "\n", encoding="utf-8")
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda *a, **k: True)

    assert me.main() == 0
    sent = sorted((env / "youtube" / "inbox").glob("*.md"))
    assert len(sent) == 2, (
        "the owner leg must run even though the operator and agent legs already fired today — "
        f"youtube's inbox holds {len(sent)} file(s), so it was never told"
    )
    # ...and a SECOND run the same day tells it nothing more
    assert me.main() == 0
    assert len(sorted((env / "youtube" / "inbox").glob("*.md"))) == 2, "one per repo per day"


def test_a_repo_whose_name_contains_an_underscore_is_actually_reachable(env):
    """⚠️ THE MIRROR I DID NOT STATE when the owner leg turned `Obligation.repo` into an ADDRESS.

    `repo` is sanitised at collection — `_sanitize` translates `_` to a space, because `_` is a
    markdown metachar and every field is rendered into a message body. That is correct for
    DISPLAY and fatal for ROUTING: `mail.py` refuses `llm batch processor` as an unsafe recipient,
    so the three repos on this box whose directory carries an underscore were never told, and the
    run logged `owners=41 sent/3 failed` every time.

    Worse than the miss: I read those sanitised names as EVIDENCE of three shadow mailboxes
    holding stranded mail, filed it as a finding, and asked to move files that do not exist. The
    directories `Reference Creator`, `llm batch processor` and `scratch bhd` are ABSENT from the
    mail root; only `Reference_Creator`, `llm_batch_processor` and `scratch_bhd` exist.
    """
    _msg(env, "llm_batch_processor", "01L" + "0" * 23, ts=_old_ts(9))
    items = me.collect_obligations(env)
    assert len(items) == 1
    assert items[0].repo == "llm batch processor", "display stays sanitised — that part was right"
    assert items[0].repo_key == "llm_batch_processor", "routing must carry the REAL directory name"

    sent, failed = me._deliver_to_owners(items, "2026-09-20")
    assert (sent, failed) == (1, 0), f"an underscore repo must be reachable: {(sent, failed)}"
    got = sorted((env / "llm_batch_processor" / "inbox").glob("*.md"))
    assert len(got) == 2, f"the escalation must land in the REAL mailbox: {[p.name for p in got]}"
    assert not (env / "llm batch processor").exists(), "and must not invent a space-named one"
    # the body still renders the display form, which is what made this look like evidence
    body = max(got, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    assert "llm batch processor" in body, "display form in the prose is correct and stays"


# ── the agent leg carries the HUB's own obligations only (operator ruling 2026-09-24, D-388) ──
# D-310 gave every owning repo its own rows but kept infra's digest as the FLEET summary, so infra
# still received ~90 rows a day it could not discharge (01M309X11…, 01M33GWWD…, 01M3639JX…).


def test_a_foreign_repos_obligation_reaches_its_owner_and_never_the_agent_leg(
    env, monkeypatch, capsys
):
    _msg(env, "fabrik", "01HUBHUBHUBHUBHUBHUBHUBHUB", ts=_old_ts(9))
    _msg(env, "someproject", "01FOREIGNFOREIGNFOREIGNFOR", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    mailed: list = []
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: mailed.append(body) or True)
    owners: list = []
    monkeypatch.setattr(
        me, "_deliver_one_owner", lambda repo, body: owners.append((repo, body)) or True
    )
    assert me.main() == 0
    assert len(mailed) == 1 and "01HUBHUBHUBHUBHUBHUBHUBHUB" in mailed[0]
    assert "01FOREIGNFOREIGNFOREIGNFOR" not in mailed[0], (
        "a row infra cannot discharge reached infra"
    )
    assert "Fleet-wide there are 2" in mailed[0], "the fleet total stays visible as one line"
    assert [r for r, _ in owners] == ["someproject"]


def test_a_day_the_hub_owns_nothing_sends_infra_nothing_and_stamps_the_leg(
    env, monkeypatch, capsys
):
    _msg(env, "someproject", "01FOREIGNFOREIGNFOREIGNFOR", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    mailed: list = []
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: mailed.append(body) or True)
    monkeypatch.setattr(me, "_deliver_one_owner", lambda repo, body: True)
    assert me.main() == 0
    assert mailed == []
    assert me.DAY_STAMP_AGENT.exists(), "nothing to send is a completed leg, not a retry every 6 h"


def test_hub_ownership_holds_for_every_population_and_the_log_names_an_empty_day(
    env, monkeypatch, capsys
):
    """A hub STRAND is the hub's own, a foreign repo with an underscore in its name is not, and a
    day the hub DOES own a row logs `agent=OK` (the empty day is the next test) (review round 1)."""
    _msg(env, "fabrik", "01HUBSTRANDHUBSTRANDHUBSTR", ts=_old_ts(9), sub="archive")
    _msg(env, "some_proj", "01UNDERSCOREUNDERSCOREUND", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    mailed: list = []
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: mailed.append(body) or True)
    owners: list = []
    monkeypatch.setattr(me, "_deliver_one_owner", lambda repo, body: owners.append(repo) or True)
    assert me.main() == 0
    assert len(mailed) == 1 and "01HUBSTRANDHUBSTRANDHUBSTR" in mailed[0]
    assert "01UNDERSCOREUNDERSCOREUND" not in mailed[0] and owners == ["some_proj"]
    assert "agent=OK" in capsys.readouterr().out


def test_an_empty_hub_day_logs_none_owned(env, monkeypatch, capsys):
    _msg(env, "someproject", "01FOREIGNFOREIGNFOREIGNFOR", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    monkeypatch.setattr(me, "_deliver_one_owner", lambda repo, body: True)
    assert me.main() == 0
    out = capsys.readouterr().out
    assert "agent=none-owned" in out and "agent=OK" not in out


def test_the_hub_is_its_mailbox_name_not_the_checkouts_folder_name(env, monkeypatch, capsys):
    """Run from a checkout not named `fabrik` (a worktree, a copy), the hub's rows must still reach
    infra and the hub must still be excluded from the owner roll-call — the folder name used to be
    the identity, so every such run saw zero hub rows (review round 2)."""
    monkeypatch.setattr(me, "_REPO_ROOT", me._REPO_ROOT.parent / "fabrik-wt")
    _msg(env, "fabrik", "01HUBWORKTREEHUBWORKTREEHU", ts=_old_ts(9))
    _msg(env, "someproject", "01FOREIGNFOREIGNFOREIGNFOR", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    mailed: list = []
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: mailed.append(body) or True)
    owners: list = []
    monkeypatch.setattr(me, "_deliver_one_owner", lambda repo, body: owners.append(repo) or True)
    assert me.main() == 0
    assert len(mailed) == 1 and "01HUBWORKTREEHUBWORKTREEHU" in mailed[0]
    assert owners == ["someproject"], "the hub must never be told as an ordinary owner"
    today = me._dt.date.today().isoformat()
    assert me._owners_done(today), "the hub's own row must not keep the roll-call open"


def test_a_repo_whose_display_name_reads_as_the_hub_keeps_the_roll_call_open(
    env, monkeypatch, capsys
):
    """`fabrik_` renders as `fabrik`; keyed on the display name, `_owners_done` counted it as the hub
    and suppressed the retry of its failed delivery for the rest of the day (review round 3)."""
    _msg(env, "fabrik_", "01LOOKALIKELOOKALIKELOOKAL", ts=_old_ts(9))
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
    monkeypatch.setattr(me, "_deliver_to_agent", lambda body: True)
    monkeypatch.setattr(me, "_deliver_one_owner", lambda repo, body: False)  # its delivery fails
    assert me.main() == 0
    assert not me._owners_done(me._dt.date.today().isoformat()), "an untold owner must be retried"
