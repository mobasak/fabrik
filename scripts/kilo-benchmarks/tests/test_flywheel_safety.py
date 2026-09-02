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
import subprocess
import sys
from pathlib import Path

import pytest

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
    # ⚠️ RETARGETED after the Phase-D cutover (2026-08-15). The ranker moved to the
    # ai-model-catalog engine, so D.1 removed its `_step` from daily_refresh.sh — but the A.0
    # invariant is unchanged, because fabrik's remaining invocation lives in wsl_startup_hook.sh
    # (:184-185), deliberately RETAINED with its alert precisely so this guarantee survived the
    # migration. The alert must exist in AT LEAST ONE live entry point; asserting only against
    # daily_refresh.sh would now red on a correct cutover, and deleting the test would drop the
    # operator's "we should not break flywheel" constraint on the floor.
    entry_points = {
        "daily_refresh.sh": (SCRIPT_DIR / "daily_refresh.sh").read_text(),
        "wsl_startup_hook.sh": (SCRIPT_DIR.parent / "wsl_startup_hook.sh").read_text(),
    }
    alert_lines = [
        ln
        for src in entry_points.values()
        for ln in src.splitlines()
        if ("send_alert" in ln or "pipeline_alert.sh" in ln) and "rank_task_subagents" in ln.lower()
    ]
    assert alert_lines, (
        "no live entry point fires an alert on the rank_task_subagents failure path — the A.0 "
        f"flywheel tripwire is gone. Checked: {sorted(entry_points)}"
    )
    for ln in alert_lines:
        if "pipeline_alert.sh" in ln:
            continue  # a separate script that loads dotenv itself (pipeline_alert.sh:39-46)
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
        for ln in _logical_lines(src.read_text()):
            if ln.lstrip().startswith("#"):
                continue  # a comment mentioning send_alert is not a site
            if "send_alert" in ln or "pipeline_alert.sh" in ln:
                sites.append(ln)
    # An inequality with slack is not a guard: at >= 6 with 8 real sites, BOTH autocommit
    # alerts could be deleted and this still passed. Pin the exact count so removing any site
    # reds — and update it deliberately when a site is added.
    # 12 -> 11 at the Phase-D cutover (2026-08-15): D.1 removed the rank_task_subagents `_step`
    # from daily_refresh.sh (the ranker now runs in the ai-model-catalog engine), taking its alert
    # site with it. fabrik's ranker alert survives in wsl_startup_hook.sh, which this count covers.
    assert len(sites) == 12, (
        f"expected exactly 12 alert sites across the three entry points, found {len(sites)}. "
        f"If you ADDED one, bump this number; if it DROPPED, an alert was deleted."
    )
    for ln in sites:
        ok = "pipeline_alert.sh" in ln or "load_dotenv" in ln
        assert ok, f"alert site can never deliver (no load_dotenv, no helper):\n  {ln[:160]}"


def test_the_heartbeat_alert_bodies_expand_their_paths():
    """Migrating the heartbeat alerts into single quotes stopped `$KB` expanding, so the only
    alert that names the failing path would have read literally `$KB/cache/`."""
    sh = (SCRIPT_DIR / "daily_refresh.sh").read_text()
    for ln in _logical_lines(sh):
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
        for ln in _logical_lines(src.read_text()):
            if "pipeline_alert.sh" not in ln or ln.lstrip().startswith("#"):
                continue
            # Only the redirect attached to the ALERT ITSELF matters. A redirect on a preceding
            # `echo` in the same `|| { …; …; }` group is harmless: a failed redirection kills that
            # command, and the group continues to the next one, so the alert still fires.
            tail = ln.split("pipeline_alert.sh", 1)[1]
            assert '>> "$LOG_FILE"' not in tail and ">> $LOG_FILE" not in tail, (
                f"the ALERT redirects into the log dir it may be reporting as broken:\n  {ln[:190]}"
            )


def _logical_lines(text):
    """Join backslash-continuations into one logical line.

    Both alert-safety tests iterate physical lines and filter on `pipeline_alert.sh in ln`. For a
    MULTI-LINE call site that line is only `bash "$KB/pipeline_alert.sh" \\` — the title, the body,
    and any redirect attached to them live on continuation lines and were never examined. The
    tail extracted for the redirect check was literally " \\". Every multi-line site in
    daily_refresh.sh and autocommit_pipeline_outputs.sh was invisible to the tests named for
    exactly those defects.
    """
    out, buf = [], ""
    for ln in text.splitlines():
        buf += ln
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1] + " "
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _line_redirects_log(lines, idx):
    """Whether the block opened at idx is redirected to the log at all."""
    return any('>> "$LOG_FILE"' in ln for ln in lines[idx:])


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
            i
            for i, ln in enumerate(lines)
            if re.match(r'^\}\s*>>\s*"?\$LOG_FILE"?', ln) and "pipeline_alert.sh" not in ln
        ]
        # ⚠️ `head` must stop at the block OPENER, not the closer. Anchoring on the closer made
        # head span essentially the whole file, so the guard could be relocated INSIDE the block
        # — reproducing the bug exactly — and every assertion still passed. Mutation-tested: the
        # relocated form skips the body, and the closer-anchored test called it green.
        if not closers:
            opener = next((i for i, ln in enumerate(lines) if ln.rstrip() == "{"), None)
            assert opener is None or _line_redirects_log(lines, opener), (
                f"{src.name} opens a compound block at line {opener + 1} but this test found no "
                f"`}} >> $LOG_FILE` closer to anchor on — the file changed shape and the guard "
                f"is no longer being checked. Do not let it skip silently."
            )
            continue
        opener = next((i for i in range(closers[0]) if lines[i].rstrip() == "{"), None)
        assert opener is not None, f"{src.name}: found a block closer but no opener"
        head = "\n".join(lines[:opener])
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


@pytest.mark.parametrize("script", ["kilo-benchmarks/daily_refresh.sh", "wsl_startup_hook.sh"])
def test_every_pipeline_entry_point_probes_the_log_before_redirecting_into_it(script):
    """Both entry points, both redirect shapes — no script gets exempted by falling through.

    The block-scope test above `continue`s on any file with no `} >> $LOG_FILE` closer, which
    silently exempted wsl_startup_hook.sh entirely — a file with the SAME hazard in its
    line-scope form: every step redirects `>> $LOG_FILE`, a failed redirection skips that
    command, so an unwritable log makes the whole boot pipeline no-op step by step including
    the heartbeat, with no alert reachable from inside. A test whose name promises coverage and
    whose control flow skips the file is worse than no test.

    The invariant both must satisfy: prove the log is APPENDABLE before anything redirects to
    it, and degrade to a target that cannot fail rather than run blind.
    """
    src = SCRIPT_DIR.parent / script if "/" not in script else SCRIPT_DIR.parent / script
    text = src.read_text()
    lines = text.splitlines()

    # Skip comments — these files DOCUMENT the hazard in prose, and a comment describing the
    # redirect is not a redirect. Matching one made the test fail on its own explanation.
    first_redirect = next(
        (
            i
            for i, ln in enumerate(lines)
            if not ln.lstrip().startswith("#")
            and ('>> "$LOG_FILE"' in ln or ">> $LOG_FILE" in ln or '>>"$LOG_FILE"' in ln)
            # the probe itself is the thing being asserted, not a violation of it
            and ': >>"$LOG_FILE"' not in ln
        ),
        None,
    )
    assert first_redirect is not None, f"{script}: no $LOG_FILE redirect found — test is stale"
    head = "\n".join(lines[:first_redirect])

    # Two equivalent shapes are allowed: the probe written inline, or a `_log_usable` helper
    # that appends to its argument and is then invoked on $LOG_FILE. Both prove appendability;
    # pinning only the inline spelling would fail a legitimate refactor into a helper.
    inline = ': >>"$LOG_FILE"' in head
    via_helper = ': >>"$1"' in head and '_log_usable "$LOG_FILE"' in head
    assert inline or via_helper, (
        f"{script} redirects to $LOG_FILE at line {first_redirect + 1} without ever proving the "
        f"file is appendable. `mkdir -p` is not that proof — it returns 0 on an existing "
        f"unwritable directory, and every redirect then fails silently"
    )
    assert "/dev/null" in head or "/dev/stderr" in head, (
        f"{script} has no terminal fallback: if the log AND /tmp are unusable, reassigning "
        f"LOG_FILE to another failing path reproduces the silent failure it just detected"
    )
    assert "pipeline_alert.sh" in head, (
        f"{script} detects the unwritable log but never alerts — the failure would surface "
        f"only via the next run's freshness check, if at all"
    )


def _extract_log_guard(path):
    """Lift the writability-guard region out of a pipeline script so it can be RUN.

    The two tests above assert that certain STRINGS appear above the first redirect. That is
    not the invariant. Five mutants which each reproduce the original silent-skip bug exactly
    — inverting the `!`, dropping the LOG_FILE reassignment, appending `|| true` to the probe,
    reassigning LOG_FILE back to the failing path — all keep those tests green, including on
    the test whose own failure message names that last mutation. Only executing the guard and
    observing where LOG_FILE actually lands can tell the difference.
    """
    lines = path.read_text().splitlines()
    start = next(
        i
        for i, ln in enumerate(lines)
        if ln.startswith("_log_usable()") or ln.lstrip().startswith("if ! { mkdir -p")
    )
    # Close on the `fi` at the SAME indentation as the opening `if`. Matching the first `fi`
    # anywhere grabbed the NESTED fallback-ladder's terminator and produced an unbalanced
    # fragment that bash rejected outright — which the harness then read as "the guard chose
    # an empty LOG_FILE". A test harness that mis-extracts fails loudly here rather than
    # silently measuring the wrong thing.
    # ⚠️ Anchor on the `if` that actually gates on the LOG probe, not merely the next `if`.
    # Hoisting the `_log_usable` helper above the rotation loop — a refactor the sibling test
    # explicitly blesses — made this grab the rotation loop's `if`, lift the `for … do` with no
    # `done`, and fail both tests with a confidently wrong diagnosis.
    if_idx = next(
        i for i in range(start, len(lines))
        if lines[i].lstrip().startswith("if ") and "$LOG_FILE" in lines[i]
    )
    indent = lines[if_idx][: len(lines[if_idx]) - len(lines[if_idx].lstrip())]
    # Tolerate a trailing comment or trailing whitespace on the terminator: `fi  # end guard`
    # is the same `fi`, and an exact-string match raises StopIteration and crashes the test
    # rather than measuring anything.
    end = next(
        i for i in range(if_idx + 1, len(lines))
        if lines[i].split("#")[0].rstrip() == f"{indent}fi"
    )
    return "\n".join(lines[start : end + 1])


def _run_log_guard(path, tmp_path, writable):
    """Execute the guard with LOG_FILE pointing at a writable or unwritable target.

    Returns the LOG_FILE the guard settled on, and whether that target is actually appendable.
    """
    cache = tmp_path / "cache"
    cache.mkdir()
    log = cache / "update.log"
    if not writable:
        cache.chmod(0o500)
        # ⚠️ VERIFY THE PRECONDITION, do not assume it. `chmod 500` does not stop ROOT, so in a
        # root container or CI this whole harness would report "the guard handled an unwritable
        # log" while the log was perfectly writable — vacuously green in the environment least
        # likely to be watched. Skip loudly instead of passing quietly.
        if subprocess.run(["bash", "-c", f': >>"{log}" 2>/dev/null'], check=False).returncode == 0:
            cache.chmod(0o700)
            pytest.skip(
                "chmod 500 does not prevent writes for this uid (running as root?) — this "
                "harness cannot construct an unwritable log, so it would test nothing"
            )
        log.unlink(missing_ok=True)
    # Both call sites are stubbed: daily_refresh uses $KB, wsl_startup_hook uses
    # $FABRIK_ROOT/scripts/kilo-benchmarks — the harness must satisfy whichever it extracts.
    stub = tmp_path / "scripts" / "kilo-benchmarks"
    stub.mkdir(parents=True)
    (stub / "pipeline_alert.sh").write_text("#!/bin/sh\nexit 0\n")
    (stub / "pipeline_alert.sh").chmod(0o755)

    # Extract BEFORE touching permissions: a reshaped script raises StopIteration here, and
    # doing it inside the try-block's setup left `cache` at mode 0500 with no finally to restore.
    guard_src = _extract_log_guard(path)
    # Redirect the production /tmp fallback into tmp_path. Running the ladder verbatim created
    # and appended to the REAL /tmp/fabrik_daily_*.log paths the live pipeline falls back to —
    # harmless same-user, but if the suite ever runs as another uid it would leave the pipeline's
    # own fallback unappendable. Nothing prunes those files either.
    guard_src = re.sub(r'"/tmp/fabrik_[^"]*"', f'"{tmp_path}/fallback.log"', guard_src)
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -u\n"
        f'FABRIK_ROOT="{tmp_path}"\n'
        f'KB="{stub}"\n'
        f'LOG_FILE="{log}"\n'
        f"{guard_src}\n"
        'printf "%s" "$LOG_FILE"\n'
    )
    try:
        chosen = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, check=False
        ).stdout.strip()
    finally:
        cache.chmod(0o700)
    appendable = (
        subprocess.run(["bash", "-c", f': >>"{chosen}" 2>/dev/null'], check=False).returncode == 0
    )
    return chosen, appendable, str(log)


@pytest.mark.parametrize("script", ["kilo-benchmarks/daily_refresh.sh", "wsl_startup_hook.sh"])
def test_the_log_guard_actually_redirects_away_from_an_unwritable_log(script, tmp_path):
    """BEHAVIOURAL: run the guard, assert LOG_FILE lands somewhere that really accepts writes."""
    src = SCRIPT_DIR.parent / script
    chosen, appendable, original = _run_log_guard(src, tmp_path, writable=False)
    assert chosen != original, (
        f"{script}: the log was unwritable but the guard left LOG_FILE pointing at it — every "
        f"redirect will fail and the pipeline runs blind or not at all"
    )
    assert appendable, (
        f"{script}: the guard moved LOG_FILE to {chosen!r}, which is ALSO not appendable — "
        f"falling back to a second failing path reproduces the silent failure it just detected"
    )


@pytest.mark.parametrize("script", ["kilo-benchmarks/daily_refresh.sh", "wsl_startup_hook.sh"])
def test_the_log_guard_leaves_a_healthy_log_alone(script, tmp_path):
    """The mirror: an inverted probe would divert a perfectly good log to the fallback."""
    src = SCRIPT_DIR.parent / script
    chosen, appendable, original = _run_log_guard(src, tmp_path, writable=True)
    assert chosen == original, (
        f"{script}: the log was writable but the guard diverted LOG_FILE to {chosen!r} — the "
        f"probe's sense is inverted"
    )
    assert appendable
