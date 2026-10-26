#!/usr/bin/env python3
# AFTER-EDIT: tests/test_session_archive_alert.py | docs/workstation/session-history-retention.md
"""session_archive_alert — mail infra and the coordinator when the nightly chat backup fails (W-36687f76).

Two verbs, both wired into the units in scripts/sysadmin/systemd/:

    failed   session-archive-alert.service, which session-archive.service names in [Unit] OnFailure=. With
             RestartMode=direct it fires ONCE, after Restart= has spent its retries (a plain OnFailure= fired on
             every failed attempt, measured on systemd 255); TimeoutStartSec= turns a hang into that failure.
             Mails the result, the exit status and the unit's journal tail (read by unit: the invocation id
             OnFailure= hands over can be the refused start's own, with no lines).
    check    session-archive.service's ExecStopPost=-. On a SUCCESSFUL run it reports every step whose code is not
             `exited` with status 0, read from systemd's own per-step record (`systemctl --user show -p
             ExecStartPre -p ExecStart`, live only until the unit goes inactive; systemd logs nothing for an
             ignored `-` failure), and the archiver's own summary from this invocation's journal: subagent
             failures, 0 MAIN transcripts eligible, the archive lock held, or no summary at all. Each run reads
             only its own attempt's lines: every Restart= attempt gets a fresh INVOCATION_ID, shared with its
             ExecStopPost= (measured on systemd 255, W-36687f76 review). Any other SERVICE_RESULT exits 0
             silently: a retry follows, or OnFailure= owns it. No SERVICE_RESULT (a hand run) exits 2.

Both verbs exit 0 once their mails are sent and 1 when a send fails. Every read `check` cannot complete is REPORTED,
never skipped — silence is the defect this script exists to end — and a crash in `check` is mailed as "check
crashed". Each mail goes to two recipients, infra (ack required) and the coordinator (ack no), through
scripts/mail.py, the transport rotate_session.py's nightly mail already uses.

The time bound: `check` runs inside the unit's TimeoutStopSec. A check that outlives it turns a good night into
result=timeout, and Restart= would re-run the ARCHIVER — so every subprocess carries its own timeout and
CHECK_BUDGET_S, their worst-case sum, is graded below the unit's TimeoutStopSec.

COBRA (D-253): the cheapest way to satisfy "an alert exists" is a check that reads nothing and never fires, or one
that fires every night until it is ignored. The counters: the tests drive each verb on systemd 255's verbatim rows
and the REAL archiver's output, a clean night is graded silent, and the population behind it (design measure 3:
0 dash-step failures in the retained nights) says a mail is news.

Env (test seams): ARCHIVE_ALERT_SYSTEMCTL (systemctl), ARCHIVE_ALERT_JOURNALCTL (journalctl), ARCHIVE_ALERT_MAIL
(scripts/mail.py), ARCHIVE_ALERT_UNIT (session-archive.service), ARCHIVE_ALERT_POLL_S (10), ARCHIVE_ALERT_RETRY_S (2).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNIT = os.environ.get("ARCHIVE_ALERT_UNIT", "session-archive.service")
TAIL_LINES = 20
TAIL_CHARS = 4000
SHOW_TIMEOUT_S = 10
SHOW_TRIES = 2
RETRY_S = 2.0
JOURNAL_TIMEOUT_S = 5
POLL_S = 10.0
SEND_TIMEOUT_S = 30
POLL_SLEEP_S = 1.0
# the worst case of one `check`: two shows and the pause between, the poll window plus the sleep that can start just
# before its deadline and one journalctl call after it, and four sends (two for the report, two for a crash after it)
CHECK_BUDGET_S = (
    SHOW_TRIES * SHOW_TIMEOUT_S
    + RETRY_S
    + POLL_S
    + POLL_SLEEP_S
    + JOURNAL_TIMEOUT_S
    + 4 * SEND_TIMEOUT_S
)
_UNIT_RE = re.compile(r"[A-Za-z0-9@._:-]+\.service")
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}")

# `{ path=P ; argv[]=A ; ignore_errors=yes|no ; start_time=[T] ; stop_time=[T] ; pid=N ; code=C ; status=S }` —
# systemd 255, verbatim in the tests. The `$` anchor and the greedy argv EACH bind the match to the row's TAIL, so an
# argv holding " ; " or a complete fake tail of its own still parses to the real one; the test kills only both lost.
_STEP_RE = re.compile(
    r"^(?P<key>ExecStartPre|ExecStart)=\{ path=(?P<path>.*?) ; argv\[\]=(?P<argv>.*) ; "
    r"ignore_errors=(?P<ign>yes|no) ; start_time=\[[^\]]*\] ; stop_time=\[[^\]]*\] ; "
    r"pid=\d+ ; code=(?P<code>\S+) ; status=(?P<status>\S+) \}$"
)
_EMPTY = frozenset({"ExecStartPre=", "ExecStart="})
# the archiver's own lines (archive_transcripts.py `_archive`), read back from the journal
_SUMMARY_RE = re.compile(
    r"\d+ new manifest row\(s\), \d+ subagent row\(s\), (\d+) subagent failure\(s\)"
)
_LOCK = "another run holds the archive lock"
_ZERO_ELIGIBLE = "archive_transcripts: 0 MAIN transcript(s) eligible"
_ARCHIVER = "/archive_transcripts.py"


def _env_float(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return default
    return v if math.isfinite(v) and v >= 0 else default


def _run(argv: list[str], timeout: float) -> tuple[int, str, str]:
    """(rc, stdout, stderr); a tool that cannot start or overruns is rc -1, never an exception. Bytes are decoded
    with replacement: journald hands back a unit's raw stdout, and one stray byte must not cost the night its check."""
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _journal(invocation: str) -> tuple[bool, list[str]]:
    """(read, lines) of one invocation's journal; an id that is not 32 hex digits is never queried."""
    if not _INVOCATION_RE.fullmatch(invocation or ""):
        return False, []
    rc, out, _err = _run(
        [
            os.environ.get("ARCHIVE_ALERT_JOURNALCTL", "journalctl"),
            "--user",
            f"_SYSTEMD_INVOCATION_ID={invocation}",
            "-o",
            "cat",
            "--no-pager",
        ],
        JOURNAL_TIMEOUT_S,
    )
    return rc == 0, out.splitlines()


def step_findings(show: str) -> list[str]:
    """Every step row that is not `exited` with leading status 0, and every line outside the grammar. On a
    successful run every row ran, so a `(null)` code is a status systemd lost — reported, not skipped — and so is a
    show with no ExecStart row at all."""
    found = []
    started = False
    for line in show.split("\n"):
        line = line.rstrip("\r")
        if not line or line in _EMPTY:
            continue
        m = _STEP_RE.match(line)
        if m is None:
            found.append(f"step status unreadable: {line[:300]}")
            continue
        started = started or m["key"] == "ExecStart"
        lead = re.match(r"\d+", m["status"])
        if lead is None:
            found.append(f"step status unreadable (status={m['status']}): {m['argv'][:300]}")
        elif m["code"] != "exited" or lead.group() != "0":
            found.append(
                f"step did not exit 0 (code={m['code']} status={m['status']}): {m['argv'][:300]}"
            )
    if not started and not found:
        found.append("no step record: `systemctl show` listed no ExecStart step for this run")
    return found


def summary_findings(read: bool, lines: list[str]) -> tuple[bool, list[str]]:
    """(complete, findings) from the archiver's lines; `complete` once a summary or the lock line is there."""
    if not read:
        return False, ["this run's journal could not be read (journalctl failed)"]
    found = []
    if any(_ZERO_ELIGIBLE in ln for ln in lines):
        found.append(
            "0 MAIN transcript(s) eligible — the projects dir is empty or mis-pointed; nothing was archived"
        )
    if any(_LOCK in ln for ln in lines):
        return True, [
            *found,
            "backup skipped: another run holds the archive lock (a stuck archiver?)",
        ]
    hits = [m for ln in lines if (m := _SUMMARY_RE.search(ln))]
    if not hits:
        return False, [
            *found,
            "the archiver's summary line was not found in this invocation's journal",
        ]
    n = int(hits[-1].group(1))
    if n:
        found.append(
            f"{n} subagent transcript(s) failed to archive (each `FAILED … the pruner keeps it` above it)"
        )
    return True, found


def _send(to_agent: str, ack: str, body: str) -> tuple[bool, str]:
    mail = os.environ.get("ARCHIVE_ALERT_MAIL", str(HERE.parent / "mail.py"))
    cmd = [sys.executable, mail, "send", "--to", "fabrik", "--kind", "finding", "--ack", ack]
    cmd += ["--from", "fabrik", "--to-agent", to_agent]
    try:  # the body file too: a full /tmp fails this send, never the next one
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as fh:
            fh.write(body + "\n")
            fh.flush()
            rc, out, err = _run([*cmd, "--body-file", fh.name], SEND_TIMEOUT_S)
    except (OSError, ValueError) as exc:
        return False, str(exc)
    return rc == 0, (err or out).strip()[-300:]


def _mail(subject: str, fields: list[str]) -> int:
    rc = 0
    for agent, ack in (("infra", "required"), ("coordinator", "no")):
        ok, why = _send(agent, ack, "\n".join([subject, "", *fields]))
        if not ok:
            print(f"session_archive_alert: mail to {agent} failed — {why}", file=sys.stderr)
            rc = 1
    return rc


def _when() -> str:
    return time.strftime("%Y-%m-%d %H:%M %z")


def _unit_tail(unit: str) -> tuple[int, list[str]]:
    """(rc, lines): the unit's last lines, systemd's own included. NOT by MONITOR_INVOCATION_ID: when the retries end
    at the start limit, systemd hands OnFailure= the refused start's FRESH invocation id, which holds no lines
    (measured on systemd 255 — the archiver's lines sit under the attempts' ids). `unit` is validated by the caller."""
    rc, out, _err = _run(
        [
            os.environ.get("ARCHIVE_ALERT_JOURNALCTL", "journalctl"),
            "--user",
            "-u",
            unit,
            "-n",
            str(TAIL_LINES),
            "-o",
            "cat",
            "--no-pager",
        ],
        JOURNAL_TIMEOUT_S,
    )
    return rc, out.splitlines() if rc == 0 else []


def cmd_failed() -> int:
    env = os.environ
    unit = env.get("MONITOR_UNIT") or UNIT
    if not _UNIT_RE.fullmatch(unit):  # never query, nor mail, a name systemd would not hand over
        unit = UNIT
    result = env.get("MONITOR_SERVICE_RESULT") or "unknown"
    code = env.get("MONITOR_EXIT_CODE") or "unknown"
    status = env.get("MONITOR_EXIT_STATUS") or "unknown"
    rc, lines = _unit_tail(unit)
    if rc != 0:
        tail = f"(journalctl could not read the unit's journal: rc {rc})"
    else:
        tail = "\n".join(lines[-TAIL_LINES:])[-TAIL_CHARS:] or f"(no journal lines for {unit})"
    return _mail(
        f"Subject: nightly chat backup FAILED — {unit} ended {result} (code {code}, status {status})",
        [
            f"WHAT: {unit} ended `{result}` (code {code}, status {status}) after Restart= spent its retries: the "
            "run did not finish. If the tail shows the archiver failed, tonight's transcripts are NOT in the "
            "bucket and the pruner did not run.",
            "WHERE: the unit's last journal lines:",
            "```",
            tail,
            "```",
            f"WHEN: {_when()}, when the retries ran out.",
            "WHO: infra owns session-history retention (D-736); the coordinator is told so it can schedule the fix.",
            "WHY: the archive is the only off-box copy of every transcript, and the pruner deletes local copies "
            "after 3 days; a failed night unfixed for three days loses those transcripts for good.",
            f"HOW: `journalctl --user -u {unit} -n 80`; fix the cause, then `systemctl --user reset-failed {unit}` "
            f"(the start limit refuses a bare start until its counter is cleared) and `systemctl --user start {unit}`.",
            "SYSTEMIC: sent by session-archive-alert.service (OnFailure=, W-36687f76); a repeat each night means "
            "the cause is still there.",
        ],
    )


def _check() -> int:
    systemctl = os.environ.get("ARCHIVE_ALERT_SYSTEMCTL", "systemctl")
    found: list[str] = []
    for attempt in range(SHOW_TRIES):
        rc, out, err = _run(
            [systemctl, "--user", "show", UNIT, "-p", "ExecStartPre", "-p", "ExecStart"],
            SHOW_TIMEOUT_S,
        )
        if rc == 0:
            found += step_findings(out)
            break
        if attempt + 1 < SHOW_TRIES:
            time.sleep(_env_float("ARCHIVE_ALERT_RETRY_S", RETRY_S))
    else:
        found.append(f"step status unreadable: `systemctl show` exited {rc}: {err.strip()[-300:]}")

    # a stop mid-run (`systemctl stop`) still ends SERVICE_RESULT=success: the archiver's own row says it
    stopped = any(
        f.startswith(("step did not exit 0", "step status unreadable (")) and _ARCHIVER in f
        for f in found
    )

    invocation = os.environ.get("INVOCATION_ID", "")
    if not _INVOCATION_RE.fullmatch(invocation):
        found.append(
            f"INVOCATION_ID unset or malformed ({invocation[:40]!r}) — this run's journal was not read"
        )
    else:
        # journald ingests the unit's stdout asynchronously: poll until the summary (or the lock line) is in
        deadline = time.monotonic() + _env_float("ARCHIVE_ALERT_POLL_S", POLL_S)
        while True:
            complete, summary = summary_findings(*_journal(invocation))
            if complete or time.monotonic() >= deadline:
                break
            time.sleep(POLL_SLEEP_S)
        found += summary
    if not found:
        return 0
    if stopped:
        subject = f"Subject: nightly chat backup STOPPED — the archive did not complete ({UNIT})"
        what = "WHAT: the archive did not complete — the run ended `success`, but the archiver's step did not exit 0:"
    else:
        subject = f"Subject: nightly chat backup PARTIAL — {len(found)} problem(s) on a successful {UNIT} run"
        what = "WHAT: the archive step succeeded, but:"
    return _mail(
        subject,
        [
            what,
            *(f"- {f}" for f in found),
            f"WHERE: {UNIT}, invocation {os.environ.get('INVOCATION_ID') or 'unknown'}.",
            f"WHEN: {_when()}, as the run ended.",
            "WHO: infra owns session-history retention (D-736); the coordinator is told so it can schedule the fix.",
            "WHY: a `-` step's failure and the archiver's partial nights exit 0, and systemd logs nothing for them.",
            f"HOW: `journalctl --user -u {UNIT} -n 80` for this run's lines; `prune_transcripts.py --status` for the pruner.",
            "SYSTEMIC: sent by session-archive.service's ExecStopPost (W-36687f76); a repeat each night means the "
            "cause is still there.",
        ],
    )


def cmd_check() -> int:
    result = os.environ.get("SERVICE_RESULT")
    if not result:
        print(
            "session_archive_alert check: no SERVICE_RESULT — not run by systemd's ExecStopPost=",
            file=sys.stderr,
        )
        return 2
    if result != "success":
        return 0
    try:
        return _check()
    except Exception as exc:  # noqa: BLE001 — the last resort: a checker that dies silently is the defect itself
        _mail(
            f"Subject: nightly chat backup check CRASHED — {UNIT}",
            [
                f"WHAT: session_archive_alert.py check crashed: {type(exc).__name__}: {exc}",
                f"WHERE: {UNIT}'s ExecStopPost=, invocation {os.environ.get('INVOCATION_ID') or 'unknown'}.",
                f"WHEN: {_when()}.",
                "WHO: infra.",
                "WHY: tonight's partial failures, if any, were not checked.",
                f"HOW: `journalctl --user -u {UNIT} -n 80`.",
                "SYSTEMIC: a defect in the checker itself (W-36687f76).",
            ],
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["failed"]:
        return cmd_failed()
    if args == ["check"]:
        return cmd_check()
    print("usage: session_archive_alert.py failed|check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
