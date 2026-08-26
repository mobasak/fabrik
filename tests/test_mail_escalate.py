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


def _msg(root: Path, repo: str, name: str, *, ack="required", agent="", ts=None, body="b", acked=False, sub="inbox"):
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
        me.Obligation(ulid=f"01M{i:023d}", repo="repo_`x`", sender="x_y*z", agent="[a]", age_days=5 + i, kind="inbox")
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
        me.Obligation(ulid=f"01M{i:023d}", repo="fabrik", sender="s", agent="-", age_days=5 + i, kind="inbox")
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


def test_fmt_age_caps_finite_values_too():
    assert me._fmt_age(1200.0) == ">999d"
    assert me._fmt_age(12.4) == "12d"


def test_day_stamp_only_after_success_and_carries_local_date(env, monkeypatch, capsys):
    _msg(env, "fabrik", "01NNNNNNNNNNNNNNNNNNNNNNNN", ts=_old_ts(4))
    sent = []
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: sent.append((t, b)) or False))
    assert me.main() == 0
    assert not me.DAY_STAMP.exists(), "a FAILED send must leave no stamp (retry in <=6h)"
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
    def boom():
        raise AssertionError("must not resolve a sender today")

    monkeypatch.setattr(me, "_resolve_sender", boom)
    assert me.main() == 0


def test_no_obligations_means_no_send(env, monkeypatch, capsys):
    monkeypatch.setattr(me, "_resolve_sender", lambda: (_ for _ in ()).throw(AssertionError))
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
    assert me.main() == 0
    assert me.DAY_STAMP.read_text(encoding="utf-8").strip() == "2026-08-27"


def test_send_raising_is_fail_soft(env, monkeypatch, capsys):
    """The contract-falsifier the review caught: a RAISING sender must never crash the
    cron — exit 0, loud, no stamp."""
    _msg(env, "fabrik", "01SSSSSSSSSSSSSSSSSSSSSSSS", ts=_old_ts(4))

    def exploder(t, b):
        raise RuntimeError("apprise leg exploded")

    monkeypatch.setattr(me, "_resolve_sender", lambda: exploder)
    assert me.main() == 0
    out = capsys.readouterr().out
    assert "send raised RuntimeError" in out and "FAILED" in out
    assert not me.DAY_STAMP.exists()


def test_stamp_write_failure_after_delivery_warns_never_crashes(env, monkeypatch, capsys):
    """The duplicate-storm falsifier: delivered send + unwritable stamp path must warn
    and exit 0 (a loud duplicate next run beats a crash-loop)."""
    _msg(env, "fabrik", "01TTTTTTTTTTTTTTTTTTTTTTTT", ts=_old_ts(4))
    me.DAY_STAMP.mkdir(parents=True)  # a DIRECTORY occupying the stamp slot
    monkeypatch.setattr(me, "_resolve_sender", lambda: (lambda t, b: True))
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
