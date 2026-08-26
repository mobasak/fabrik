#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/fabrik-mail.md, docs/reference/fabrik-mail.md | tests/test_mail_escalate.py
"""fabrik-mail escalation digest — the destination-side half of the addressing plan.

Sender-side enforcement (the mail.py addressing guard) makes NEW hub mail carry an owner;
what enforcement cannot solve is recipients not ACTING. This cron scans EVERY mailbox for
aged ``ack: required`` obligations in three populations (digest()'s unacked legs — the
``malformed/`` quarantine population stays digest()'s business):

  1. inbox messages (regardless of ``agent:`` — the population is UNACKED, never unaddressed);
  2. archive STRANDS — claimed into archive but never resolved (no ``acked-by:`` line);
  3. stranded ``*.md.resolving*`` windows, aged by mtime (invisible to every other verb).

and sends AT MOST ONE Telegram per LOCAL calendar day via ``libs.alerting.send_alert`` (the
package entry — Apprise primary leg + diagnosis; day-stamp written ONLY after a successful
send, with the send-moment's local date). Failure is fail-soft: exit 0, loud on OUR stdout
(the library logger has no handler — never rely on it). The one accepted duplicate window:
a stamp WRITE failure after a delivered send warns loudly and re-sends next run — a
duplicate beats a crash-loop and beats silence.

Cron (operator-installed; the env prefix IS the override point — cron reads no .env):
  0 */6 * * * /bin/sh -c 'mkdir -p $HOME/.claude/state/mail-escalate && cd /opt/fabrik && FABRIK_MAIL_ESCALATE_DAYS=3 flock -n $HOME/.claude/state/mail-escalate/cron.lock python3 scripts/sysadmin/mail_escalate.py' >> /var/log/fabrik-mail-escalate.log 2>&1
"""

from __future__ import annotations

import datetime as _dt
import re as _re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# A scripts/sysadmin/ invocation has neither the repo root nor scripts/ on sys.path —
# and the _import_alerting precedent (mail.py:1307) is ONE level shallower; the depth
# here is parents[2]. `cd /opt/fabrik` in the cron line serves ONLY the alerting
# dotenv walk, never imports.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mail as _mail  # noqa: E402  (scripts/mail.py — the protocol's own parsers)

STATE_DIR = Path.home() / ".claude" / "state" / "mail-escalate"
DAY_STAMP = STATE_DIR / "day-stamp"
MAX_ROWS = 20
BODY_BUDGET = 3900  # under telegram.py's own 4096 title+body truncation
_CTRL = _re.compile(r"[\x00-\x1f\x7f]")
_MD_META = str.maketrans(dict.fromkeys("_*[]`", " "))  # Markdown fallback-leg 400 risk

# The plan-pinned injection seam: tests set _send; production resolves lazily so importing
# this module NEVER imports libs.alerting (whose import-time dotenv load would pull live
# TELEGRAM keys into a test process).
_send = None


@dataclass(frozen=True)
class Obligation:
    ulid: str
    repo: str
    sender: str
    agent: str
    age_days: float
    kind: str  # inbox | strand | window


def _sanitize(text: str, cap: int = 40) -> str:
    return _CTRL.sub("", str(text)).translate(_MD_META)[:cap].strip() or "?"


def _threshold_seconds() -> float:
    # the _env_cap precedent: a non-numeric or below-minimum value warns and uses the
    # DEFAULT (3) — a bare int() would crash on garbage and =0 would escalate everything.
    return _mail._env_cap("FABRIK_MAIL_ESCALATE_DAYS", 3, minimum=1) * 86400.0


def _aged(age_seconds: float, threshold: float) -> bool:
    """INCLUSIVE at the boundary — the same `>=` digest() uses (mail.py:1076)."""
    return age_seconds >= threshold


def collect_obligations(root: Path) -> list[Obligation]:
    threshold = _threshold_seconds()
    out: list[Obligation] = []
    if not root.is_dir():
        return out
    try:
        repo_dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return out
    for repo_dir in repo_dirs:
        try:
            out.extend(_scan_repo(repo_dir, threshold))
        except OSError as exc:
            # partial scan beats abort: one unreadable mailbox must not silence the rest
            print(f"mail-escalate: WARNING — skipping {repo_dir.name}: {exc}")
    out.sort(key=lambda o: -o.age_days)  # oldest first — the longest-rotted lead the digest
    return out


def _scan_repo(repo_dir: Path, threshold: float) -> list[Obligation]:
    out: list[Obligation] = []
    inbox = repo_dir / "inbox"
    archive = repo_dir / "archive"
    repo = _sanitize(repo_dir.name)  # sanitized AT COLLECTION like every other field
    if not inbox.is_dir() and not archive.is_dir():
        return out  # a stray non-mailbox dir
    if inbox.is_dir():
        for f in sorted(inbox.glob("*.md")):
            if f.name.startswith("."):
                continue  # dotfile guard (P13-6 class): a .vim backup must never escalate
            ob = _from_file(f, repo, threshold, kind="inbox")
            if ob:
                out.append(ob)
    if archive.is_dir():
        for f in sorted(archive.glob("*.md")):
            if f.name.startswith("."):
                continue  # P13-6 proper: an archive dotfile would escalate FOREVER
            ob = _from_file(f, repo, threshold, kind="strand", need_unresolved=True)
            if ob:
                out.append(ob)
        for w in sorted(archive.glob("*.md.resolving*")):
            if w.name.startswith("."):
                continue
            try:
                age = time.time() - w.stat().st_mtime  # a rename has no ts of its own
            except OSError:
                continue
            if _aged(age, threshold):
                out.append(
                    Obligation(
                        ulid=_sanitize(w.name.split(".md")[0], 26),
                        repo=repo,
                        sender="?",
                        agent="",
                        age_days=age / 86400.0,
                        kind="window",
                    )
                )
    return out


def _from_file(f: Path, repo: str, threshold: float, *, kind: str, need_unresolved: bool = False) -> Obligation | None:
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None  # a concurrent claim/ack moved it — never crash the cron
    fm = _mail._parse(text)
    if fm is None or fm.get("ack") != "required":
        return None  # malformed frontmatter is digest()'s quarantine business, not ours
    if need_unresolved and _mail._ACK_LINE.search(text):
        return None  # resolved — not a strand
    age = _mail._age_seconds(fm.get("ts", ""))
    if not _aged(age, threshold):
        return None
    return Obligation(
        ulid=_sanitize(fm.get("id", f.stem), 26),
        repo=repo,
        sender=_sanitize(fm.get("from", "?")),
        agent=_sanitize(fm.get("agent", "") or "-", 10),
        age_days=age / 86400.0,
        kind=kind,
    )


def _fmt_age(days: float) -> str:
    return ">999d" if not days < 999 else f"{days:.0f}d"  # inf-safe: broken ts escalates, renders sanely


def build_digest(items: list[Obligation]) -> str:
    rows: list[str] = []
    for ob in items[:MAX_ROWS]:
        # sanitize here TOO (defense-in-depth): the invariant must hold even for an
        # Obligation built outside collect_obligations.
        rows.append(
            f"{_sanitize(ob.ulid, 26)} · {_sanitize(ob.repo)} · {_sanitize(ob.sender)} · "
            f"{_fmt_age(ob.age_days)} · {_sanitize(ob.agent, 10)} ({_sanitize(ob.kind, 8)})"
        )
    while rows and sum(len(r) + 1 for r in rows) > BODY_BUDGET - 80:
        rows.pop()  # fewer than 20 if the budget demands — the count line always survives
    more = len(items) - len(rows)
    tail = f"+{more} more ({len(items)} total)" if more > 0 else f"({len(items)} total)"
    return "\n".join([*rows, tail])


def _resolve_sender():
    """Lazy production resolution (see the _send seam note at module top)."""
    from libs.alerting import send_alert  # noqa: PLC0415

    return send_alert


def main() -> int:
    today = _dt.date.today().isoformat()  # LOCAL calendar date — cron fires local; a UTC
    # stamp would double-send across the 21:00-00:00 window on this +03 box
    try:
        if DAY_STAMP.read_text(encoding="utf-8").strip() == today:
            print(f"mail-escalate: already sent today — suppressed ({today})")
            return 0  # the print keeps the log's mtime fresh for the liveness budget
    except OSError:
        pass  # absent OR unreadable → proceed (a duplicate beats permanent silence)
    items = collect_obligations(_mail._mail_root())
    if not items:
        print(f"mail-escalate: 0 aged obligations — no send ({today})")
        return 0
    body = build_digest(items)
    title = f"fabrik-mail: {len(items)} unacked obligation(s) aged past the threshold"
    try:
        sender = _send or _resolve_sender()
        ok = bool(sender(title, body))
    except Exception as exc:  # noqa: BLE001 — fail-soft IS the contract: never crash the cron
        print(f"mail-escalate: send raised {type(exc).__name__}: {exc}")
        ok = False
    print(f"mail-escalate: {len(items)} obligation(s) · send={'OK' if ok else 'FAILED'} ({today})")
    if ok:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            DAY_STAMP.write_text(today + "\n", encoding="utf-8")  # only after success
        except OSError as exc:
            # delivered but unstamped: the next run re-sends — a LOUD duplicate beats a
            # crash-loop (and beats stamp-before-send silently suppressing a day).
            print(f"mail-escalate: WARNING — day-stamp write failed ({exc}); next run will re-send")
    return 0  # fail-soft: the no-stamp retry in <=6h is the recovery; stdout is the visibility


if __name__ == "__main__":
    sys.exit(main())
