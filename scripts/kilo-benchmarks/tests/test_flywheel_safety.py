# AFTER-EDIT: docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md (Phase A.0 gates)
"""Phase A.0 — the flywheel-safety invariant, made testable.

Guards the operator's binding constraint ("we should not break flywheel") across the
extraction. Three properties, all load-bearing:

1. A BROKEN read (subprocess/psql failure) is distinguishable from a genuinely EMPTY one —
   ``_query_rows`` returns ``("error", [])`` vs ``("ok", [])``. Without this, the daily stub
   advances its "Last refresh" date on a lie and broken looks identical to healthy-but-empty.
2. A broken read exits **1** from ``main()`` — the tripwire.
3. A genuinely-empty-but-reachable flywheel exits **0** — an empty table is not a failure.

These are simulated (monkeypatched subprocess), so the suite runs anywhere — it must NOT
depend on a live database or on passwordless sudo. The live positive-proof assertion is a
separate operational gate (A.0 gate 1 / B.4a), deliberately not a unit test.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rank_task_subagents as rts  # noqa: E402


class _Result:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_broken_read_is_distinguishable_from_empty(monkeypatch):
    """A psql/sudo failure yields state 'error' — never a bare empty list."""
    monkeypatch.setattr(
        rts.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(OSError("sudo: command not found")),
    )
    state, rows = rts._query_rows()
    assert state == "error", "a failed read MUST report state='error', not masquerade as empty"
    assert rows == []


def test_nonzero_psql_exit_is_error_state(monkeypatch):
    """psql exiting non-zero is a broken read, not an empty one."""
    monkeypatch.setattr(
        rts.subprocess, "run", lambda *a, **k: _Result(returncode=2, stderr="FATAL: no such db")
    )
    state, rows = rts._query_rows()
    assert state == "error"
    assert rows == []


def test_reachable_but_empty_is_ok_state(monkeypatch):
    """An empty-but-reachable flywheel is 'ok' — an empty table is not a failure."""
    monkeypatch.setattr(rts.subprocess, "run", lambda *a, **k: _Result(returncode=0, stdout=""))
    state, rows = rts._query_rows()
    assert state == "ok", "a clean query over an empty table must NOT report 'error'"
    assert rows == []


def test_broken_read_exits_nonzero(monkeypatch):
    """THE TRIPWIRE: main() returns 1 when the read is broken."""
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "stub")
    monkeypatch.setattr(rts, "_atomic_write", lambda *a, **k: None)
    rc = rts.main()
    assert rc == 1, "a BROKEN flywheel read must exit 1 — this is the only signal a caller gets"


def test_healthy_read_exits_zero(monkeypatch):
    """The mirror: a healthy read must not trip the wire."""
    monkeypatch.setattr(rts, "_query_rows", lambda: ("ok", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "stub")
    monkeypatch.setattr(rts, "_atomic_write", lambda *a, **k: None)
    assert rts.main() == 0


def test_daily_refresh_does_not_swallow_the_tripwire():
    """The un-mute: daily_refresh.sh must not discard the ranker's exit code.

    `_step` propagates rc correctly, but a bare `|| echo "... (non-fatal)"` at the call site
    turns exit 1 into a log line nobody reads — the file has no `set -e`, redirects to a
    logfile, and the crontab has no MAILTO, so propagation alone surfaces to no one.
    """
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    lines = [ln for ln in sh.splitlines() if "rank_task_subagents" in ln and "_step" not in ln]
    swallowed = [
        ln for ln in lines if "|| echo" in ln and "non-fatal" in ln and "alert" not in ln.lower()
    ]
    assert not swallowed, (
        "daily_refresh.sh swallows the rank_task_subagents tripwire into a log line: "
        f"{swallowed!r} — route the failure to send_alert instead (A.0 gate 3)"
    )


def test_the_alert_can_actually_fire_not_just_exist():
    """A grep for the absence of `|| echo` proves nothing about DELIVERY.

    `alerting/` does not load dotenv, and `_is_enabled()` reads TELEGRAM_BOT_TOKEN /
    ALERT_VPS_HOST from the process env. The token lives only in `.env`, so a
    `python -c "from alerting import send_alert; ..."` invocation that does NOT load dotenv
    first is a SILENT no-op — the exact failure this gate exists to prevent, reproduced
    inside the fix. The working idiom is `check_daily_refresh_freshness.py:39-43`:
    load_dotenv BEFORE importing alerting.
    """
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    alert_lines = [
        ln for ln in sh.splitlines() if "send_alert" in ln and "rank_task_subagents" in ln.lower()
    ]
    assert alert_lines, "the rank_task_subagents failure path must fire an alert"
    for ln in alert_lines:
        assert "load_dotenv" in ln, (
            "alert invocation does not load_dotenv before importing alerting, so "
            "alerting._is_enabled() is False and the alert silently never delivers: " + ln[:120]
        )


def test_alerting_is_enabled_once_dotenv_is_loaded(monkeypatch):
    """End-to-end: with the alert's env present, alerting reports itself live.

    ⚠️ Does NOT call load_dotenv on the real .env. That would load all 447 lines into
    os.environ for the whole pytest session, and six sibling modules in this directory branch
    on OPENROUTER_API_KEY / ANTHROPIC_API_KEY — a full-suite run would wake key-gated paths
    that were previously skipped, potentially making live metered calls. It would also couple
    the assertion to THIS box's .env, so the test reds for environmental reasons once Phase B
    copies tests/ into the engine repo. Inject just the one key instead.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-not-a-real-secret")
    import alerting

    assert alerting._is_enabled(), (
        "alerting reports DISABLED even with TELEGRAM_BOT_TOKEN present — the un-mute is a no-op"
    )


def test_broken_read_does_not_overwrite_a_good_doc(monkeypatch, tmp_path):
    """THE REAL GUARD: a broken read must not publish the stub over yesterday's good doc.

    Alerting alone is fail-open with a receipt — daily_refresh git-commits and pushes whatever
    main() wrote, fleet-syncing it to 49 vendored pick_models copies.
    """
    good = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    good.write_text("GOOD CONTENT FROM YESTERDAY", encoding="utf-8")
    monkeypatch.setattr(rts, "OUTPUT_PATH", good)
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "AGGREGATION FAILED stub")
    assert rts.main() == 1
    assert good.read_text() == "GOOD CONTENT FROM YESTERDAY", (
        "the broken-read stub overwrote a good doc — it will be committed and fleet-synced"
    )


def test_first_run_still_writes_when_no_doc_exists(monkeypatch, tmp_path):
    """The mirror: an ABSENT doc is worse than a labelled stub, so a first run still writes."""
    missing = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    monkeypatch.setattr(rts, "OUTPUT_PATH", missing)
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "AGGREGATION FAILED stub")
    assert rts.main() == 1
    assert missing.exists(), "first run must still emit the labelled stub"


def test_a_stub_on_disk_is_not_worth_preserving(monkeypatch, tmp_path):
    """The keep-guard's blind spot: "keep the existing doc" is only right if it is GOOD.

    After a first-run failure the stub IS on disk, so every later broken run would preserve
    it forever while daily_refresh.sh's alert body asserts "the fleet is on yesterday-good,
    not poisoned" — the exact opposite of the truth.
    """
    stub = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    stub.write_text("AGGREGATION FAILED — yesterday's stub", encoding="utf-8")
    monkeypatch.setattr(rts, "OUTPUT_PATH", stub)
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "AGGREGATION FAILED — today's stub")
    assert rts.main() == 1
    assert "today's stub" in stub.read_text(), (
        "a stub was preserved as if it were a good doc — the guard needs stub detection"
    )


def test_an_unreadable_doc_does_not_skip_the_keep_guard(monkeypatch, tmp_path):
    """Round-4 fix #8 had no test at all.

    An OSError from the stub-detection read (permissions, or a race with daily_refresh's git
    commit) raised out of main() BEFORE the keep-guard ran — skipping the very protection the
    block exists to apply, so the stub would be published over yesterday's good doc.
    """
    doc = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    doc.write_text("GOOD CONTENT FROM YESTERDAY", encoding="utf-8")
    monkeypatch.setattr(rts, "OUTPUT_PATH", doc)
    monkeypatch.setattr(rts, "_query_rows", lambda: ("error", []))
    monkeypatch.setattr(rts, "render", lambda *a, **k: "AGGREGATION FAILED stub")

    real_read = type(doc).read_text

    def boom(self, *a, **k):
        if self == doc:
            raise PermissionError("simulated")
        return real_read(self, *a, **k)

    monkeypatch.setattr(type(doc), "read_text", boom)
    assert rts.main() == 1
    monkeypatch.undo()
    assert doc.read_text() == "GOOD CONTENT FROM YESTERDAY", (
        "an unreadable doc skipped the keep-guard and the stub was published over it"
    )


def test_every_daily_refresh_alert_can_actually_deliver():
    """The heartbeat pair alerted NOBODY from June until 2026-08-15.

    `test_the_alert_can_actually_fire_not_just_exist` filters on
    `"rank_task_subagents" in ln.lower()`, so it only ever saw the ranker line — which is
    exactly why the two heartbeat `send_alert` calls could sit there with no `load_dotenv`
    (making `alerting._is_enabled()` False) for months. Check EVERY alert site.
    """
    # EVERY pipeline entry point, not just daily_refresh.sh — the heartbeat pair stayed broken
    # for months precisely because the existing test filtered on "rank_task_subagents".
    sources = [
        SCRIPT_DIR / "daily_refresh.sh",
        SCRIPT_DIR.parent / "wsl_startup_hook.sh",
        SCRIPT_DIR / "autocommit_pipeline_outputs.sh",
    ]
    sites = []
    for src in sources:
        for ln in src.read_text().splitlines():
            if ln.lstrip().startswith("#"):
                continue  # a comment mentioning send_alert is not a site
            if "send_alert" in ln or "pipeline_alert.sh" in ln:
                sites.append(ln)
    # An inequality with slack is not a guard: at >= 6 with 8 real sites, BOTH autocommit
    # alerts could be deleted and this still passed. Pin the exact count so removing any site
    # reds — and update it deliberately when a site is added.
    assert len(sites) == 10, (
        f"expected exactly 10 alert sites across the three entry points, found {len(sites)}. "
        f"If you ADDED one, bump this number; if it DROPPED, an alert was deleted."
    )
    for ln in sites:
        ok = "pipeline_alert.sh" in ln or "load_dotenv" in ln
        assert ok, f"alert site can never deliver (no load_dotenv, no helper):\n  {ln[:160]}"


def test_the_heartbeat_alert_bodies_expand_their_paths():
    """Migrating the heartbeat alerts into single quotes stopped `$KB` expanding, so the only
    alert that names the failing path would have read literally `$KB/cache/`."""
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    for ln in sh.splitlines():
        if "pipeline_alert.sh" not in ln:
            continue
        # Splitting on `'` alternates outside/inside single quotes; only the ODD chunks are
        # single-quoted, and only those suppress expansion.
        for chunk in ln.split("'")[1::2]:
            assert "$" not in chunk, (
                f"single-quoted alert body will emit a literal variable:\n  {ln[:170]}"
            )


def test_no_alert_redirects_into_the_directory_it_reports_as_broken():
    """A failed redirection means bash never runs the command at all.

    The heartbeat cache-dir alert reports that `$KB/cache/` could not be created — and an
    earlier version redirected its own output to `$KB/cache/update.log`, INSIDE that very
    directory. The guard condition and the redirect failure are perfectly correlated, so the
    alert became unreachable by construction. The redirect was also redundant: the enclosing
    block already ends `} >> "$LOG_FILE" 2>&1`.
    """
    for src in (SCRIPT_DIR / "daily_refresh.sh", SCRIPT_DIR.parent / "wsl_startup_hook.sh"):
      for ln in src.read_text().splitlines():
        if "pipeline_alert.sh" not in ln or ln.lstrip().startswith("#"):
            continue
        # Only the redirect attached to the ALERT ITSELF matters. A redirect on a preceding
        # `echo` in the same `|| { …; …; }` group is harmless: a failed redirection kills that
        # command, and the group continues to the next one, so the alert still fires.
        tail = ln.split("pipeline_alert.sh", 1)[1]
        assert ">> \"$LOG_FILE\"" not in tail and ">> $LOG_FILE" not in tail, (
            f"the ALERT redirects into the log dir it may be reporting as broken:\n  {ln[:190]}"
        )


def test_block_scope_log_redirect_cannot_silently_skip_the_whole_pipeline():
    """A COMPOUND command's failed redirection skips its ENTIRE body — silently, exit 1.

    daily_refresh.sh wraps its whole pipeline in `{ … } >> "$LOG_FILE" 2>&1`. LOG_FILE lives
    in $KB/cache/, so if that directory cannot be created bash skips every step AND the
    in-block "heartbeat cache dir creation FAILED" guard never even evaluates — the one alert
    that would have reported it. The line-scope version of this defect was fixed earlier and
    is pinned by test_no_alert_redirects_into_the_directory_it_reports_as_broken, but that
    test skips any line without `pipeline_alert.sh` in it, so the block-scope closer was
    invisible to it. This is the instance that matters: it takes down the whole run, not one
    alert.

    The invariant: any script closing a block with `} >> "$LOG_FILE"` must make that redirect
    unfailable BEFORE the block opens — an unguarded `mkdir -p` is not enough, because it
    fails in exactly the same scenario. It needs a fallback that reassigns LOG_FILE.
    """
    for src in (SCRIPT_DIR / "daily_refresh.sh", SCRIPT_DIR.parent / "wsl_startup_hook.sh"):
        lines = src.read_text().splitlines()
        closers = [
            i for i, ln in enumerate(lines)
            if re.match(r'^\}\s*>>\s*"?\$LOG_FILE"?', ln) and "pipeline_alert.sh" not in ln
        ]
        if not closers:
            continue
        head = "\n".join(lines[: closers[0]])
        # ⚠️ Assert the probe is an APPEND, not a `mkdir -p`. `mkdir -p` returns 0 on an
        # existing-but-unwritable directory, so a mkdir-based guard reports success while the
        # redirect still fails and still skips the entire body — the guard would be decorative
        # in exactly the scenario it exists for. Empirically reproduced with `chmod 500`.
        assert re.search(r'_log_usable\(\)\s*\{[^}]*:\s*>>"?\$1', head), (
            f"{src.name} must prove the log is WRITABLE by appending to it before the block "
            f"opens. `mkdir -p` alone is not that proof: it succeeds on an existing unwritable "
            f"directory, and the whole pipeline body is then skipped in silence"
        )
        assert re.search(r'if\s+!\s+_log_usable "\$LOG_FILE"', head), (
            f"{src.name} defines the writability probe but does not gate on it"
        )
        assert "_fallback" in head and "/dev/stderr" in head, (
            f"{src.name} needs a terminal fallback that CANNOT fail: if both the real log and "
            f"/tmp are unusable, reassigning LOG_FILE to another failing path reproduces the "
            f"silent skip. Redirect to /dev/stderr rather than let the body be skipped"
        )
