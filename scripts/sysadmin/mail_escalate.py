#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/fabrik-mail.md, docs/reference/fabrik-mail.md | tests/test_mail_escalate.py
"""fabrik-mail escalation digest — the destination-side half of the addressing plan.

Sender-side enforcement (the mail.py addressing guard) makes NEW hub mail carry an owner;
what enforcement cannot solve is recipients not ACTING. This cron scans EVERY mailbox for
aged ``ack: required`` obligations in three populations (digest()'s unacked legs — the
``malformed/`` quarantine population stays digest()'s business):

  1. inbox messages (regardless of ``agent:`` — the population is UNACKED, never unaddressed);
  2. archive STRANDS — claimed into archive but never resolved (no ``acked-by:`` line);
  3. stranded ``*.md.resolving*`` windows, aged by mtime (invisible to every other verb) — and
     FILTERED on the window's own ``ack:``, because a window IS the message and this script's own
     ``ack: no`` digest would otherwise become a permanent obligation the moment an agent's
     ``mail.py ack`` of it is SIGKILLed mid-rename.

and delivers on TWO INDEPENDENT LEGS, each at most once per LOCAL calendar day and each with its
OWN day-stamp written ONLY after ITS OWN successful send: the OPERATOR leg
(``libs.alerting.send_alert`` — Apprise primary + diagnosis, Telegram in practice) and the AGENT
leg (``_deliver_to_agent`` — into the hub mailbox addressed to ``infra``, which is the leg that
produces action; see its docstring). One shared stamp let a success on one leg suppress the other
for the whole day, which inverted the point of having two. The run holds its own ``flock`` so a
hand run cannot deliver a duplicate and stamp the day out from under the cron. Failure is fail-soft: exit 0, loud on OUR stdout
(the library logger has no handler — never rely on it). The one accepted duplicate window:
a stamp WRITE failure after a delivered send warns loudly and re-sends next run — a
duplicate beats a crash-loop and beats silence.

⚠️ THE MEASURE AND ITS CHEAPEST EVASION (FIX DIRECTIVE 5 / D-253 — you get the behaviour you
measure). This counts AGED UNACKED OBLIGATIONS. It deliberately does NOT count inbox depth:
depth falls to ``mail.py sweep``, which archives by AGE, and shortening its ``--days`` to force
a tidy number is already an operator-banned move. Obligations are never swept, so the count can
only fall by ACKing. **The cheapest way to satisfy this measure without doing the work is
therefore an ack that resolves nothing** — ``ack --disposition done`` on a message nobody read.
Nothing here can prevent that, and a check that tried would just move the lie. What holds it
honest instead is that an ack is ATTRIBUTED and DURABLE: the disposition is written into the
message and the message is archived carrying it, so a false ``done`` is auditable forever
against the finding it claims to have closed. If this count ever falls sharply without commits
behind it, read the archive, not the number.

Cron (operator-installed; the env prefix IS the override point — cron reads no .env):
  0 */6 * * * /bin/sh -c 'mkdir -p $HOME/.claude/state/mail-escalate && cd /opt/fabrik && FABRIK_MAIL_ESCALATE_DAYS=3 flock -n $HOME/.claude/state/mail-escalate/cron.lock python3 scripts/sysadmin/mail_escalate.py' >> /var/log/fabrik-mail-escalate.log 2>&1
"""

from __future__ import annotations

import datetime as _dt
import fcntl
import re as _re
import subprocess as _subprocess
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
# ⚠️ ONE STAMP PER LEG. A single shared stamp meant a Telegram success suppressed the whole day,
# so ONE transient failure of the agent leg cost the agent that day's digest entirely — the 06:00,
# 12:00 and 18:00 runs all printed "already sent today" and never retried the leg that reaches
# someone who can ACT. That inverts this change's own thesis (review round 1). Each leg is a
# separate recipient and gets a separate suppression key.
DAY_STAMP_AGENT = STATE_DIR / "day-stamp-agent"
# The hub's own mail.py — absolute, because this runs from cron with no cwd guarantee
_MAIL_PY = _REPO_ROOT / "scripts" / "mail.py"
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
    # ⚠️ DISPLAY vs ADDRESS. `repo` is sanitised at collection (`_sanitize` translates `_` to a
    # space, because every field is rendered into a markdown body) and is safe to PRINT and unsafe
    # to ROUTE ON. `repo_key` is the real directory name under the mail root, and is the only
    # thing `mail.py send --to` may be handed. Splitting them is not a refinement: the owner leg
    # shipped using `repo` as an address, `mail.py` correctly refused `llm batch processor`, and
    # the three underscore repos on this box were never told — while the sanitised names read
    # convincingly enough as "shadow mailboxes" that they were filed as a finding.
    repo_key: str = ""


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
    repo = _sanitize(repo_dir.name)  # sanitized AT COLLECTION like every other field — DISPLAY
    repo_key = repo_dir.name  # the real directory name — the only safe ROUTING key (see Obligation)
    if not inbox.is_dir() and not archive.is_dir():
        return out  # a stray non-mailbox dir
    if inbox.is_dir():
        for f in sorted(inbox.glob("*.md")):
            if f.name.startswith("."):
                continue  # dotfile guard (P13-6 class): a .vim backup must never escalate
            ob = _from_file(f, repo, threshold, repo_key=repo_key, kind="inbox")
            if ob:
                out.append(ob)
    if archive.is_dir():
        for f in sorted(archive.glob("*.md")):
            if f.name.startswith("."):
                continue  # P13-6 proper: an archive dotfile would escalate FOREVER
            ob = _from_file(f, repo, threshold, repo_key=repo_key, kind="strand", need_unresolved=True)
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
                # ⚠️ A window IS the message — its frontmatter is right there. Read it and skip a
                # non-obligation. Without this the leg ages purely by mtime, so THIS SCRIPT'S OWN
                # `ack: no` digest becomes an obligation the moment an agent's `mail.py ack` is
                # SIGKILLed between the two renames (a harness timeout, an OOM) — and permanently,
                # because ack()'s stale-window sweeper only fires on a LATER ack of the same id and
                # nobody acks a dead digest twice. The count would then rise on its own, one row per
                # day, which is the opposite of what this script measures (review round 1).
                try:
                    _wfm = _mail._parse(w.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    _wfm = None
                if _wfm is not None and _wfm.get("ack") != "required":
                    continue
                out.append(
                    Obligation(
                        ulid=_sanitize(w.name.split(".md")[0], 26),
                        repo=repo,
                        sender="?",
                        agent="",
                        age_days=age / 86400.0,
                        kind="window",
                        repo_key=repo_key,
                    )
                )
    return out


def _from_file(
    f: Path,
    repo: str,
    threshold: float,
    *,
    kind: str,
    repo_key: str = "",
    need_unresolved: bool = False,
) -> Obligation | None:
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
        repo_key=repo_key,
    )


def _fmt_age(days: float) -> str:
    return (
        ">999d" if not days < 999 else f"{days:.0f}d"
    )  # inf-safe: broken ts escalates, renders sanely


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


def _shape_line(items: list[Obligation]) -> str:
    """What the count IS, in one line — senders, and which of them are broadcasts.

    ⚠️ `83 row(s)` reads as 83 work items. Measured on the live store 2026-09-20 it was EIGHT
    distinct facts: 41 of the 83 were ONE fabrik-lib broadcast sitting in 41 different mailboxes,
    39 more were the hub's own sends, and NONE was an obligation on the hub that received the
    digest. An agent handed the bare number sizes the job by an order of magnitude and then finds
    it cannot discharge a single row. The SYSTEMIC line already warned that the count is not the
    population; it never said what the population was.

    Grouped by SENDER because that field is already on `Obligation` — no extra read, no new
    failure mode — and because it is exactly the broadcast signature: one sender, N rows, N
    distinct mailboxes. A sender whose rows span FEWER mailboxes than rows is not called a
    broadcast, and a single row is never called one.
    """
    by_sender: dict[str, list[Obligation]] = {}
    for ob in items:
        by_sender.setdefault(ob.sender, []).append(ob)
    parts = []
    for sender, obs in sorted(by_sender.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        boxes = len({o.repo for o in obs})
        tag = ""
        if len(obs) > 1 and boxes == len(obs):
            tag = f" — one BROADCAST across {boxes} mailboxes, not {len(obs)} separate items"
        elif len(obs) > 1:
            tag = f" across {boxes} mailbox(es)"
        parts.append(f"{len(obs)}× from {_sanitize(sender)}{tag}")
    return "; ".join(parts) if parts else "no rows"


def _agent_body(title: str, rows: str, n: int, items: list[Obligation] | None = None) -> str:
    """The digest as a MESSAGE, not a bare column of ULIDs.

    ⚠️ The first cut handed `_deliver_to_agent` the rows alone. The delivered mail therefore had no
    subject and failed every section of the D-035 contract this hub enforces on every other sender —
    `mail.py` printed the advisory to stderr, which `_deliver_to_agent` discards on the success
    path, so the violation was structurally unobservable and shipped 365 times a year. An agent
    opening it saw ULIDs and no instruction, while being bound by the handle-now law (review
    round 1).
    """
    return (
        f"Subject: {title}\n\n"
        "WHAT: the fabrik-mail obligations below are past the escalation threshold "
        f"(`FABRIK_MAIL_ESCALATE_DAYS`, default 3). {n} row(s), oldest first.\n"
        + (f"SHAPE: {_shape_line(items)}.\n" if items else "")
        +
        "WHO: `scripts/sysadmin/mail_escalate.py` (hub cron, every 6h) -> infra.\n"
        "WHERE: the rows are `id · repo · sender · age · agent (population)`. ⚠️ Column 2 is the "
        "MAILBOX and most rows are NOT the hub's, so every command needs it: read one with "
        "`python3 scripts/mail.py read <id> --repo <repo>` — without `--repo` mail.py defaults to "
        "the cwd's repo and the read fails (and a bare `ack` leaves a stray archive dir behind).\n"
        "WHEN: generated this run; each row's age is measured from the message's own `ts` "
        "(a `window` row is aged by mtime, because a rename carries no ts).\n"
        "WHY: an obligation nobody acks is work nobody owns. This digest exists because the "
        "operator-facing Telegram leg reaches someone whose standing directive is that they do "
        "not read it — an AGENT bound by the handle-now law is the reader that closes the loop.\n"
        "HOW: handle each per CLAUDE.md — read -> validate the cited path:line -> SIZE it -> do "
        "the work -> review -> reply -> `mail.py ack <id> --repo <repo> --disposition "
        "done|blocked|wontfix`. Not yours? `mail.py ack <id> --repo <repo> --disposition wontfix` naming the "
        "owner, or `mail.py route <id> --repo <repo> --to-agent infra|fleet|intel`. Never sweep.\n"
        "SYSTEMIC: the count falls only by ACKing — `sweep` never touches obligations. If it "
        "drops sharply with no commits behind it, read the archive, not the number.\n\n"
        f"{rows}"
    )


def _deliver_to_agent(body: str) -> bool:
    """Deliver the digest INTO the hub mailbox, addressed to ``infra`` — the leg that reaches
    someone who can ACT.

    ⚠️ THE REASON THIS EXISTS. The Telegram leg reports to the OPERATOR, whose standing directive
    is "i dont read anything, you read". This cron ran every 6 hours and logged ``send=OK`` while
    the hub inbox grew to 132 messages with a 10-day-old oldest obligation: the alert was landing
    where nobody who could act would read it. ``feedback_relay.py`` had already learned exactly
    this ("the digest was operator-facing, and the operator does not read dashboards … This relay
    makes an AGENT the reader") and this script never got the same leg. A session that opens the
    delivered message is bound by the handle-now law, which is the whole point.

    ⚠️ ``--ack no`` is LOAD-BEARING: an ``ack: required`` digest would be counted as an obligation
    by the very next run, so the number could never fall and the digest would feed itself. That
    covers the inbox and strand populations, which filter on ``ack``. ⚠️ It did NOT cover the third:
    the ``*.md.resolving*`` window leg aged purely by mtime and read no frontmatter, so a digest
    whose ``mail.py ack`` was SIGKILLed mid-rename became a permanent obligation. That leg now reads
    the window's own frontmatter and skips a non-obligation — without it this docstring's claim was
    false for 1 of 3 populations (review round 1).

    Fail-soft like every other leg: never raise into the cron.
    """
    try:
        proc = _subprocess.run(
            [
                sys.executable,
                str(_MAIL_PY),
                "send",
                "--to",
                "fabrik",
                "--to-agent",
                "infra",
                "--kind",
                "finding",
                "--ack",
                "no",
            ],
            input=body,
            text=True,
            capture_output=True,
            timeout=60,
            # `mail.py` derives the `from:` field from the cwd's git worktree, so an inherited cwd
            # would attribute the hub's own digest to whatever repo the caller stood in (R2).
            cwd=str(_REPO_ROOT),
        )
    except Exception as exc:  # noqa: BLE001 — the cron must never die on a delivery leg
        print(f"mail-escalate: agent leg raised {type(exc).__name__}: {exc}")
        return False
    if proc.returncode != 0:
        print(f"mail-escalate: agent leg failed rc={proc.returncode}: {proc.stderr.strip()[:200]}")
        return False
    # ⚠️ Print stderr on SUCCESS too. `mail.py` reports the D-035 structure advisory and the
    # "this is already open" duplicate pointer on stderr at rc 0, and discarding them made both
    # structurally invisible for the only caller that runs daily (review round 1).
    if proc.stderr.strip():
        print(f"mail-escalate: agent leg note: {proc.stderr.strip()[:400]}")
    return True


# ── the OWNER leg ─────────────────────────────────────────────────────────────────────────────
#
# ⚠️ WHY THIS EXISTS (operator ruling 2026-09-20: "each agent should take care of its own mails").
# Until now the digest had ONE destination: the hub mailbox addressed to `infra`. Measured on the
# live store that day, of its 83 rows ZERO were obligations on the hub — every one sat in another
# repo's inbox, 41 of them a single fabrik-lib broadcast. So the reader bound by the handle-now law
# was handed work it structurally could not discharge, and the only escape the digest offered
# (`ack --disposition wontfix naming the owner`) would have CLOSED 83 obligations the owning repos
# had never seen. That destroys the signal instead of discharging it, which is why the count only
# ever grew.
#
# ⚠️ THE COBRA (D-253) — the agent leg's cobra, one order of magnitude larger. The cheapest way to
# satisfy "escalate to owners" WITHOUT the outcome is to send a message nobody reads: the count
# does not fall and the fleet gains ~40 messages a day. Three things bound it. (1) `--ack no` is
# LOAD-BEARING: an `ack: required` escalation is counted by the very next run, so the mechanism
# would feed itself in forty mailboxes at once and the number could never fall. (2) One message per
# repo per DAY, stamped, because the cron runs every 6 h and four identical copies a day is how a
# signal becomes noise. (3) The hub digest still reports the FLEET total, so a fleet that ignores
# its escalations shows up as a count that does not fall — visible, not hidden by the fan-out.
_OWNER_MAX_ROWS = 30


def _owners_done(today: str) -> bool:
    """Has every repo that currently owns an overdue obligation already been told today?

    ⚠️ The early exit in `main` short-circuits on the operator+agent stamps. Without this the
    owner leg would never run on any day those two had already fired — which, since they fire on
    the day's FIRST run and the cron runs four times, is almost every day.
    """
    try:
        items = collect_obligations(_mail._mail_root())
    except Exception:  # noqa: BLE001 — never crash the cron on a scan; assume work remains
        return False
    repos = {o.repo for o in items if o.repo != _REPO_ROOT.name}
    return all(_stamped(_owner_stamp(r), today) for r in repos)


def _owner_stamp(repo: str) -> Path:
    """One stamp per repo per day. The name is sanitised to a filesystem-safe token because `repo`
    comes from a directory name under the mail root and this path is WRITTEN."""
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in repo)[:60]
    return STATE_DIR / f"day-stamp-owner-{safe}"


def _owner_body(repo: str, obs: list[Obligation], fleet_total: int) -> str:
    """That repo's OWN overdue obligations, as a D-035 message — never the fleet's list."""
    rows = "\n".join(
        f"{_sanitize(o.ulid, 26)} · {_sanitize(o.sender)} · {_fmt_age(o.age_days)} "
        f"· {_sanitize(o.agent, 10)} ({_sanitize(o.kind, 8)})"
        for o in obs[:_OWNER_MAX_ROWS]
    )
    more = len(obs) - min(len(obs), _OWNER_MAX_ROWS)
    tail = f"\n+{more} more ({len(obs)} total)" if more else ""
    return (
        f"Subject: {len(obs)} unacked obligation(s) in YOUR mailbox are past the threshold\n\n"
        f"WHAT: {len(obs)} message(s) in `{_sanitize(repo)}`'s own inbox carry `ack: required` and "
        "are older than the escalation threshold (`FABRIK_MAIL_ESCALATE_DAYS`, default 3), listed "
        f"below oldest first. Fleet-wide there are {fleet_total}; these are YOURS.\n"
        "WHO: `scripts/sysadmin/mail_escalate.py` on the hub, delivering to the OWNING repo — the "
        "hub cannot discharge your obligations, and acking them from there would close messages "
        "you have never seen (operator ruling 2026-09-20: each agent handles its own mail).\n"
        "WHERE: the rows are `id · sender · age · agent (population)`. You are already IN this "
        "mailbox, so no `--repo` is needed: `python3 scripts/mail.py read <id>`.\n"
        "WHEN: generated this run; each row's age comes from the message's own `ts` (a `window` "
        "row is aged by mtime, because a rename carries no ts).\n"
        "WHY: an obligation nobody acks is work nobody owns. This message is `ack: no` on purpose "
        "— it is a pointer, not a new obligation — so ACKing the rows below is the only thing that "
        "makes the count fall.\n"
        "HOW: per CLAUDE.md — read -> validate the cited path:line -> SIZE it -> do the work -> "
        "review -> reply -> `python3 scripts/mail.py ack <id> --disposition done|blocked|wontfix`. "
        "Not yours? `ack --disposition wontfix` naming the owner, or relay it. Never sweep: "
        "`sweep` archives by AGE and closes nothing.\n"
        "SYSTEMIC: you are seeing this because the digest used to go only to the hub, where nobody "
        "could act on it. If a row is stale or was resolved outside fabrik-mail, ack it `wontfix` "
        "with that reason — an unacked obligation is indistinguishable from ignored work, and the "
        "fleet count is the only thing anyone watches.\n\n"
        f"{rows}{tail}"
    )


def _deliver_to_owners(items: list[Obligation], today: str) -> tuple[int, int]:
    """Fan the rows out to the repos that own them. Returns ``(sent, failed)``.

    Skips `fabrik`: infra's digest already carries every row including the hub's, so a per-repo
    delivery there would put the same obligations in the same mailbox twice.
    """
    by_repo: dict[str, list[Obligation]] = {}
    for ob in items:
        key = ob.repo_key or ob.repo  # `repo_key` is the real dir; `repo` is display-sanitised
        if key == _REPO_ROOT.name:
            continue
        by_repo.setdefault(key, []).append(ob)
    sent = failed = 0
    for repo, obs in sorted(by_repo.items()):
        stamp = _owner_stamp(repo)
        if _stamped(stamp, today):
            continue  # already told today; the cron runs every 6 h
        # route on the KEY, render the sanitised display name in the body
        if _deliver_one_owner(repo, _owner_body(obs[0].repo or repo, obs, len(items))):
            sent += 1
            _stamp(stamp, today, f"owner:{repo}")
        else:
            failed += 1
    return sent, failed


def _deliver_one_owner(repo: str, body: str) -> bool:
    """One `mail.py send` into that repo's mailbox. Fail-soft: one repo's failure never costs the
    others theirs, and never raises into the cron."""
    try:
        proc = _subprocess.run(
            [sys.executable, str(_MAIL_PY), "send", "--to", repo, "--kind", "finding",
             "--ack", "no"],
            input=body,
            text=True,
            capture_output=True,
            timeout=60,
            # as the agent leg: `mail.py` derives `from:` from the cwd's git worktree
            cwd=str(_REPO_ROOT),
        )
    except Exception as exc:  # noqa: BLE001 — the cron must never die on a delivery leg
        print(f"mail-escalate: owner leg for {repo} raised {type(exc).__name__}: {exc}")
        return False
    if proc.returncode != 0:
        print(
            f"mail-escalate: owner leg for {repo} failed rc={proc.returncode}: {proc.stderr[:200]}"
        )
        return False
    return True


def _resolve_sender():
    """Lazy production resolution (see the _send seam note at module top)."""
    from libs.alerting import send_alert  # noqa: PLC0415

    return send_alert


def _stamped(path: Path, today: str) -> bool:
    try:
        return path.read_text(encoding="utf-8").strip() == today
    except OSError:
        return False  # absent OR unreadable → proceed (a duplicate beats permanent silence)


def _stamp(path: Path, today: str, leg: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(today + "\n", encoding="utf-8")  # only after success
    except OSError as exc:
        # delivered but unstamped: the next run re-sends — a LOUD duplicate beats a crash-loop
        # (and beats stamp-before-send silently suppressing a day).
        print(f"mail-escalate: WARNING — {leg} day-stamp write failed ({exc}); next run re-sends")


def main() -> int:
    today = _dt.date.today().isoformat()  # LOCAL calendar date — cron fires local; a UTC
    # stamp would double-send across the 21:00-00:00 window on this +03 box
    # ⚠️ SELF-LOCK. The `flock` lives in the operator-installed CRON LINE, which guards cron
    # against cron and nothing else. Since the agent leg was added, a hand run does not merely
    # cost an extra Telegram — it DELIVERS a duplicate `finding` into the hub inbox and stamps
    # the day, so the next cron run is suppressed and the real digest is never produced. The
    # lock belongs to the script (review round 1).
    # ⚠️ CONTENTION ONLY. A bare `except OSError` here covers `mkdir` and `open` too, so an
    # unwritable state dir, ENOSPC, or a stray file at either path printed "another run holds the
    # lock" and returned 0 — the digest silenced FOREVER behind a message that reads as benign
    # contention, and nothing self-heals. Every other leg in this module fails OPEN by design
    # ("a duplicate beats permanent silence"); this one inverted that (review round 2).
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _lock_fd = open(STATE_DIR / "run.lock", "w")  # noqa: SIM115 — held for the process
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("mail-escalate: another run holds the lock — skipped")
        return 0
    except OSError as exc:
        print(f"mail-escalate: WARNING — lock unavailable ({exc}); proceeding UNLOCKED")
    operator_done = _stamped(DAY_STAMP, today)
    agent_done = _stamped(DAY_STAMP_AGENT, today)
    if operator_done and agent_done and _owners_done(today):
        print(f"mail-escalate: already sent today — suppressed ({today})")
        return 0  # the print keeps the log's mtime fresh for the liveness budget
    items = collect_obligations(_mail._mail_root())
    if not items:
        print(f"mail-escalate: 0 aged obligations — no send ({today})")
        return 0
    rows = build_digest(items)
    title = f"fabrik-mail: {len(items)} unacked obligation(s) aged past the threshold"
    ok = operator_done
    if not operator_done:
        try:
            sender = _send or _resolve_sender()
            ok = bool(sender(title, rows))
        except Exception as exc:  # noqa: BLE001 — fail-soft IS the contract: never crash the cron
            print(f"mail-escalate: send raised {type(exc).__name__}: {exc}")
            ok = False
        if ok:
            _stamp(DAY_STAMP, today, "operator")
    # THE leg that reaches someone who can act (see `_deliver_to_agent`), retried INDEPENDENTLY
    # of the operator leg — one transient local failure must not cost the agent the whole day.
    # It is also LOCAL (no ssh, no DNS) where the operator leg goes over the network: on
    # 2026-09-12 that leg failed TWICE before succeeding on the day's third run.
    agent_ok = agent_done
    if not agent_done:
        agent_ok = _deliver_to_agent(_agent_body(title, rows, len(items), items))
        if agent_ok:
            _stamp(DAY_STAMP_AGENT, today, "agent")

    # THE OWNER leg — each repo is told about its OWN rows, because the hub cannot discharge them
    # (operator ruling 2026-09-20). Independent of the two legs above for the same reason they are
    # independent of each other, and self-stamping per repo so a partial failure retries only the
    # repos it missed.
    owner_sent, owner_failed = _deliver_to_owners(items, today)

    # ⚠️ A SKIPPED leg is not an OK leg. `ok`/`agent_ok` are seeded from the STAMP, so three of the
    # four daily runs printed `send=OK · agent=OK` having sent nothing — the same shape as the
    # failure this whole change exists to end ("logged send=OK while the inbox grew to 132"). The
    # log is the only evidence a cron leaves; it must distinguish delivered from suppressed.
    def _verdict(done: bool, result: bool) -> str:
        return "skipped" if done else ("OK" if result else "FAILED")

    print(
        f"mail-escalate: {len(items)} obligation(s) · "
        f"send={_verdict(operator_done, ok)} · agent={_verdict(agent_done, agent_ok)} · "
        f"owners={owner_sent} sent/{owner_failed} failed ({today})"
    )
    return 0  # fail-soft: the no-stamp retry in <=6h is the recovery; stdout is the visibility


if __name__ == "__main__":
    sys.exit(main())
