#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mail.py, docs/reference/fabrik-mail.md, docs/workstation/fabrik-mail.md, .env.example, docs/CONFIGURATION.md
"""fabrik-mail — durable hub↔project AI message store + protocol (stdlib-only).

One neutral-path file mailbox per repo at ``$FABRIK_MAIL_ROOT/<repo>/{inbox,archive}``
(default root ``/opt/fabrik-mail``). A message is one ``.md`` file: YAML-ish frontmatter
(``id from to ts re kind ack hops``) + a markdown body. Subcommands:

    send  --to <repo> --kind <k> [--ack required|no] [--re <id>] [--from <repo>] [--auto] < body
    list  [--repo <repo>]
    read  <id> [--repo <repo>]
    ack   <id> [--repo <repo>] [--disposition done|blocked|wontfix]
    requeue <id> [--repo <repo>]
    digest [--days N]
    claim <id> [--repo <repo>]
    should-reply <id> [--repo <repo>]   # advisory loop-safety pre-check (ALLOW 0 / HOLD 3)

Protocol invariants (the conventions doc, docs/reference/fabrik-mail.md, is canonical):
  * publish = tmp-then-EXCLUSIVE-create (``os.link`` → ``EEXIST`` on collision, never overwrite)
  * id = hand-rolled Crockford-base32 ULID (lexical order == value order; NO new dependency)
  * ack/claim = atomic-by-rename (``os.rename``; the ENOENT loser stops)
  * star topology: project→project refused (route via the hub)
  * secrets never travel: high-confidence secret patterns REFUSE the send
  * stdout/stderr only, no logfiles (12-Factor XI); config via env (12-Factor III)
"""

from __future__ import annotations

import argparse
import os
import re as _re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# --- constants ---------------------------------------------------------------
# Crockford base32, ASCII-ascending so lexical order == numeric value order.
# (base64.b32encode's RFC-4648 A-Z2-7 is NOT order-preserving — see the tests.)
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LEN = 26  # 128 bits encoded MSB-first, left-padded

HUB_NODES = frozenset({"fabrik", "fabrik-lib"})  # the star center + its first-class node
KINDS = frozenset({"request", "finding", "relay", "reply", "upstream-feedback"})
ACK_BY_KIND = {  # default ack per kind
    "request": "required",
    "upstream-feedback": "required",
    "finding": "no",
    "relay": "no",
    "reply": "no",
}
MAX_BODY = 64 * 1024  # a mail is a pointer, not a payload
MAX_RE = 512  # a threading ref is an id or a short prose pointer (P3-7)

# Loop-safety defaults (spec 2026-08-15-fabrik-mail-loop-safety-design; env-overridable).
# Read at CALL time via _env_cap so a per-thread override needs no restart.
HOP_CAP = 3  # refuse an auto-reply when parent.hops >= this (thread depth budget)
RATE_CAP = 5  # refuse when >= this many messages from the sender within the window
RATE_WINDOW_S = 3600  # the per-sender rate window, seconds


def _env_cap(name: str, default: int, minimum: int = 0) -> int:
    """Int env override, else the default. For the CAPS an explicit 0 is an
    operator INTENT (refuse all auto-replies), never a silent fall-back (C6);
    the rate WINDOW takes minimum=1 — a 0 window makes `0 <= age < 0` never
    true, silently DISABLING the circuit breaker (fail-open, the inversion of
    the caps' semantics). Below-minimum/garbage values warn and use the
    DEFAULT (not the minimum) — wider window, stricter breaker."""
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        print(f"mail.py: {name}={raw!r} is not an int — using default {default}", file=sys.stderr)
        return default
    if v < minimum:
        print(
            f"mail.py: {name}={v} is below the minimum {minimum} — using default {default}",
            file=sys.stderr,
        )
        return default
    return v


DISPOSITIONS = (
    "done",
    "blocked",
    "wontfix",
)  # SSOT — argparse choices, _ACK_LINE, and ack() all derive from this

# High-confidence secret signatures — REFUSE the send.
_SECRET_HIGH = [
    _re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    _re.compile(r"\b\w*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\w*\s*[:=]\s*\S{16,}", _re.I),
    _re.compile(r"\bsk-[A-Za-z0-9-]{16,}"),  # sk-, sk-ant-, sk-proj- (hyphens kept)
    _re.compile(r"\bgh[posru]_[A-Za-z0-9]{20,}"),  # classic GitHub tokens
    _re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),  # fine-grained PATs
    _re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    _re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),  # AWS long-term + session
    _re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    _re.compile(r"(?i)\bauthorization:\s*bearer\s+\S{8,}"),  # Bearer header
    _re.compile(
        r"\b[a-z][a-z0-9+.-]*://[^\s/:@]*:[^\s/@]+@"
    ),  # scheme://[user]:pass@host (user optional — redis://:pw@)
]
# Low-confidence hints — WARN but still deliver (not bare "key", too noisy).
_SECRET_LOW = _re.compile(r"\b(?:password|passwd|secret|token|credential|api[_-]?key)\b", _re.I)

# Path-safety: a repo/recipient token is a single /opt directory name; a msg id is a
# 26-char Crockford ULID. Neither may contain a path separator or a `..` component —
# the guard against traversal via unvalidated `to`/`repo`/`msg_id` args (defense in
# depth under the single-operator threat model; a traversal is a loud refusal).
_SAFE_NAME = _re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_ID = _re.compile(r"^[0-9A-Z]{26}$")
# P10-4: what _quarantine actually writes — "<name>.md" or "<name>.md.<n>". A
# stray `.md.bak` / `.md.resolving.*` / `README.md` must not inflate the count.
_QUARANTINED_NAME = _re.compile(r"\.md(\.\d+)?$")
# A REAL ack line (appended by ack()) — matched precisely so a body that merely
# contains the words "acked-by:" cannot fool the digest's claimed-but-crashed scan.
_ACK_LINE = _re.compile(r"(?m)^acked-by: .+ · disposition: (?:" + "|".join(DISPOSITIONS) + r")\s*$")


def _safe_name(name: str, what: str) -> str:
    if name in ("", ".", "..") or not _SAFE_NAME.fullmatch(name):
        raise MailRefusedError(
            f"unsafe {what} {name!r}: must be a plain repo name ([A-Za-z0-9._-], no path separators / `..`)"
        )
    return name


def _safe_id(msg_id: str) -> str:
    if not _SAFE_ID.fullmatch(msg_id):
        raise MailRefusedError(f"unsafe message id {msg_id!r}: must be a 26-char Crockford ULID")
    return msg_id


class MailRefusedError(Exception):
    """A loud, nothing-written refusal (invalid recipient, star violation, secret, oversize)."""


class MailHoldError(MailRefusedError):
    """A loop-safety HOLD on an --auto send (benign: the guard did its job —
    exit 3, distinct from a real refusal's exit 2, so an unattended wrapper can
    stop quietly without string-matching stderr). Subclasses MailRefusedError
    so every existing catch still works."""


# --- env / paths -------------------------------------------------------------
def _mail_root() -> Path:
    return Path(os.environ.get("FABRIK_MAIL_ROOT", "/opt/fabrik-mail"))


def _opt_root() -> Path:
    # base for the machinery-presence recipient check; env-overridable for tests.
    return Path(os.environ.get("FABRIK_OPT_ROOT", "/opt"))


def _current_repo() -> str:
    """This repo's identity = the git main-checkout basename (worktrees lie)."""
    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        for line in out.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree ") :].strip()).name
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().name


# --- ULID --------------------------------------------------------------------
def _crockford(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_CROCKFORD[rem])
    return "".join(reversed(chars))  # MSB-first, left-padded


def _ulid() -> str:
    ms = (time.time_ns() // 1_000_000) & ((1 << 48) - 1)  # 48-bit ms timestamp
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    return _crockford((ms << 80) | rand, _ULID_LEN)


# --- validation --------------------------------------------------------------
def _is_hub(name: str) -> bool:
    return name in HUB_NODES


def _valid_recipient(to: str) -> bool:
    """Machinery-presence: fabrik/fabrik-lib (hardcoded), OR the surfacing hook is on disk."""
    if _is_hub(to):
        return True
    return (_opt_root() / to / ".claude" / "hooks" / "mail_notify.py").is_file()


def _body_has_bare_ack_line(body: str) -> bool:
    """A body carrying a VERBATIM ack line would poison the claim/ack/digest scans (a
    claimed message becomes permanently un-ackable and digest-invisible — closer C3).
    Refuse at send; quoting a resolved thread is fine with an indent ("> acked-by: …")."""
    # P4-1 + P6-1: the UNION of two views, because the guard and its consumers
    # disagree in BOTH directions. read_text() translates \r (and \r\n) to \n,
    # so the raw body alone missed a \r-separated ack line; but read_text does
    # NOT translate \v \f \x85 U+2028/2029 \x1c-\x1e, so the normalized view
    # alone SPLITS an ack line containing one of those and misses it while every
    # consumer still matches — and the CROSS case (a \r delimiter with one of
    # those inside the line) fell between both (P7-1). So match the CONSUMER's
    # exact view (which strictly contains the raw body) ∪ the fully-normalized
    # one — over-strict is fail-closed.
    consumer_view = body.replace("\r\n", "\n").replace("\r", "\n")  # what read_text() yields
    return bool(_ACK_LINE.search(consumer_view)) or bool(
        _ACK_LINE.search("\n".join(body.splitlines()))
    )


def _secret_level(body: str) -> str | None:
    for rx in _SECRET_HIGH:
        if rx.search(body):
            return "high"
    if _SECRET_LOW.search(body):
        return "low"
    return None


# --- publish -----------------------------------------------------------------
def _publish(inbox: Path, msg_id: str, content: str) -> Path:
    """tmp-then-O_EXCL create: raises FileExistsError on an existing id, never overwrites."""
    target = inbox / f"{msg_id}.md"
    root = _mail_root().resolve()
    if root not in target.resolve().parents:  # belt-and-suspenders containment (F1/F2)
        raise MailRefusedError(f"refusing to publish outside the mail root: {target}")
    inbox.mkdir(parents=True, exist_ok=True)
    tmp = inbox / f".{msg_id}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:
        os.link(tmp, target)  # EEXIST if target already exists — the collision guard
    except FileExistsError:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)
    return target


def _now_iso() -> str:
    # message mint time — from time.time_ns() so tests can control it
    return datetime.fromtimestamp(time.time_ns() / 1e9, tz=UTC).isoformat()


def _frontmatter(
    mid: str, frm: str, to: str, ts: str, re_: str, kind: str, ack: str, body: str, hops: int = 0
) -> str:
    return (
        "---\n"
        f"id: {mid}\n"
        f"from: {frm}\n"
        f"to: {to}\n"
        f"ts: {ts}\n"
        f"re: {re_ or ''}\n"
        f"kind: {kind}\n"
        f"ack: {ack}\n"
        f"hops: {hops}\n"
        "---\n"
        f"{body}" + ("" if body.endswith("\n") else "\n")
    )


def _ts_epoch(ts: str) -> float | None:
    """Epoch seconds for a frontmatter ts — a NAIVE ts reads as UTC (C4: the
    emitter always writes UTC; box-local interpretation shifted legacy naive
    stamps by the UTC offset). None when unparseable."""
    try:
        dt_ = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if dt_.tzinfo is None:
        dt_ = dt_.replace(tzinfo=UTC)
    return dt_.timestamp()


def _fm_hops(fm: dict) -> int:
    """Parent thread depth — fail-soft: missing/malformed reads as 0 (legacy),
    and the value is CLAMPED to >= 0 (R4: one corrupt negative value must not
    disable the hop cap for a whole subtree)."""
    try:
        return max(0, int(fm.get("hops", "0") or 0))
    except (TypeError, ValueError):
        return 0


def _recent_from_count(
    repo: str, sender: str, window_s: int, now_ts: float, root: Path | None = None
) -> int:
    """Messages from ``sender`` in ``repo``'s inbox+archive younger than the
    window. The mailbox IS the state (zero-infra, 12F-VI) — the digest walk
    pattern but READ-ONLY: a malformed file is SKIPPED, never quarantined
    (digest owns that repair); an unreadable file is skipped; age == window is
    OUT of the window. In practice is_dir() + glob swallow most dir errors —
    the caller's OSError fail-soft remains as defense-in-depth, not a hot path."""
    base = (root or _mail_root()) / repo
    total = 0
    for sub in ("inbox", "archive"):
        d = base / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.startswith("."):
                continue  # P10-5: dotfiles are not messages — the THIRD glob,
                # symmetric with digest and list_msgs
            # (An mtime prefilter was tried and REMOVED — E2: mtime and ts
            # diverge under cp -p/rsync/restores and synthetic now_ts, silently
            # under-counting the breaker. The O(N) walk is the accepted cost.)
            # C5 (accepted): a message inside an ack's resolving window
            # (<id>.md.resolving.<pid>) escapes this glob for milliseconds —
            # a transient UNDER-count, i.e. the fail-soft direction.
            try:
                fm = _parse(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if fm is None or fm.get("from") != sender:
                continue
            ts = _ts_epoch(fm.get("ts", ""))
            if ts is None:
                continue  # unparseable ts → not counted (under-count = fail-soft)
            age = now_ts - ts
            if 0 <= age < window_s:  # C4: a future-dated ts is corruption, never "recent"
                total += 1
    return total


def should_auto_reply(
    parent_fm: dict, self_repo: str, *, now_ts: float | None = None, root: Path | None = None
) -> tuple[bool, str]:
    """The four loop-safety guards, evaluated against the PARENT being replied
    to. Order: self → terminal-kind → hop-cap → rate-cap → ALLOW; first trip
    wins and names the reason. Fail-soft: an uncomputable rate count ALLOWs
    with a stderr note (a loop is lower-risk than a wedged channel)."""
    _safe_name(self_repo, "repo")  # L9: keep the traversal guard on this public entry
    sender = parent_fm.get("from", "")
    if sender == self_repo:
        return (
            False,
            f"self-guard: parent is from {self_repo} itself — never auto-reply to your own message",
        )
    # R2: key on the KIND, never the ack proxy — --ack is a free override, so
    # a reply minted with ack:required would otherwise beget replies forever.
    if parent_fm.get("kind", "") not in ("request", "upstream-feedback") or (
        parent_fm.get("ack", "") != "required"
    ):
        return False, (
            f"terminal kind: parent is {parent_fm.get('kind', '?')!r} (ack: "
            f"{parent_fm.get('ack', '?')}) — only ack:required request/upstream-feedback "
            "messages are auto-replied"
        )
    hops = _fm_hops(parent_fm)
    hop_cap = _env_cap("FABRIK_MAIL_HOP_CAP", HOP_CAP)
    if hops >= hop_cap:
        return (
            False,
            f"hop cap: parent at depth {hops} >= {hop_cap} — surface the thread to the operator",
        )
    now_ts = now_ts if now_ts is not None else datetime.now(UTC).timestamp()
    try:
        recent = _recent_from_count(
            self_repo,
            sender,
            _env_cap("FABRIK_MAIL_RATE_WINDOW_S", RATE_WINDOW_S, minimum=1),
            now_ts,
            root,
        )
    except OSError as exc:
        print(f"mail.py: rate count unavailable ({exc!r}) — fail-soft ALLOW", file=sys.stderr)
        return True, "ALLOW (rate state unreadable — fail-soft)"
    # F3 (accepted): read-then-act with no lock — concurrent senders can
    # overshoot the cap by the concurrency degree (hub runs up to 3 sessions);
    # the NEXT send trips, so the bound is "cap ± concurrency", never unbounded.
    rate_cap = _env_cap("FABRIK_MAIL_RATE_CAP", RATE_CAP)
    if recent >= rate_cap:
        return False, (
            f"rate cap: {recent} message(s) from {sender} within the window >= {rate_cap} — "
            "circuit-broken; surface to the operator"
        )
    return True, "ALLOW"


def send(
    to: str,
    kind: str,
    body: str,
    frm: str | None = None,
    ack: str | None = None,
    re: str | None = None,
    auto: bool = False,
) -> Path:
    """Publish a message to <to>'s inbox. Raises MailRefusedError on any refusal (nothing written)."""
    frm = frm or _current_repo()
    _safe_name(to, "recipient")
    _safe_name(frm, "sender")
    if ack and ack not in ("required", "no"):  # vocabulary check subsumes any separator
        # P3-1: `ack` is the SECOND raw-interpolated frontmatter value (the CLI
        # constrains it by argparse choices; the library path did not). A line
        # break forges `from` (defeating the self-guard) or plants an acked-by
        # line (permanently un-ackable + digest-invisible). Vocabulary check.
        raise MailRefusedError(f"unsafe ack {ack!r}: must be exactly 'required' or 'no'")
    if re is not None and len(re.splitlines()) > 1:
        # H1 + P2-1: `re` is the one deliberately-unvalidated frontmatter value
        # (prose refs, R1). A LINE BREAK in it forges arbitrary frontmatter — a
        # `from:` (defeating the self-guard + rate attribution) or an `acked-by:`
        # line (poisoning claim/ack/digest, the C3 class the body is guarded
        # against). The test is `splitlines()` itself — the same separator set
        # `_parse` honours (and `ack` above gets the same treatment) (\n \r \v \f \x1c-\x1e \x85 \u2028 \u2029), never a
        # narrower \n/\r check the parser would disagree with.
        raise MailRefusedError("unsafe --re: a threading ref is a single line (no line breaks)")
    if re is not None and len(re) > MAX_RE:
        # P3-7: a mail is a pointer — an unbounded re: bloats every mailbox walk
        # (rate count, digest, list) for the life of the message. Checked AFTER
        # the line-break guard so the security refusal always names itself.
        raise MailRefusedError(f"unsafe --re: over the {MAX_RE}-char threading-ref cap")
    if kind not in KINDS:
        raise MailRefusedError(f"unknown kind {kind!r} (allowed: {', '.join(sorted(KINDS))})")
    if len(body.encode("utf-8")) > MAX_BODY:
        raise MailRefusedError(
            f"body over the 64 KB cap ({len(body.encode('utf-8'))} B) — a mail is a pointer, not a payload"
        )
    if _body_has_bare_ack_line(body):
        raise MailRefusedError(
            "refusing send: body contains a VERBATIM ack line (it would poison claim/ack/digest "
            "scans) — quote resolved threads with an indent: '> acked-by: …'"
        )
    if not _valid_recipient(to):
        raise MailRefusedError(
            f"invalid recipient {to!r}: not fabrik/fabrik-lib and no /opt/{to}/.claude/hooks/mail_notify.py (a repo that can't surface mail)"
        )
    if not _is_hub(frm) and not _is_hub(to):
        raise MailRefusedError(
            f"star-topology refusal: {frm}→{to} is project→project; route via the hub (--to fabrik)"
        )
    # E1: the HIGH-secret refusal outranks every guard HOLD — a credential-
    # bearing send must never be classified as a benign loop-guard stop (only
    # the LOW-confidence warn stays after the guards, so a refused auto-reply
    # never prints "sending anyway" — R11).
    level = _secret_level(body)
    if level == "high":
        raise MailRefusedError(
            "refusing send: body contains a high-confidence secret — messages never carry credentials"
        )
    # D6: the recipient/star checks above run BEFORE the guards — a real
    # misconfiguration (exit 2) must never be masked by a benign HOLD (exit 3).
    # Loop-safety (spec 2026-08-15): resolve the parent ONCE; hops measures
    # thread depth on EVERY --re (human or auto); only --auto consumes guards.
    # The resolution catches MailRefusedError too (R1): legacy threads carry
    # PROSE re: values — a non-ULID --re fail-softs to hops=0, never refuses.
    parent: dict | None = None
    parent_raw: str | None = None
    parent_unreadable = False
    if re:
        try:
            parent_raw = read_msg(re, frm)
        except (MailRefusedError, FileNotFoundError):
            parent_raw = None  # non-ULID (prose re, R1) or genuinely missing — fail-soft
        except OSError:
            parent_unreadable = True  # C2: EXISTS but unreadable ≠ missing
        parent = _parse(parent_raw) if parent_raw is not None else None
    hops = (_fm_hops(parent) + 1) if parent is not None else 0
    if auto:
        if not re:
            raise MailRefusedError(
                "--auto requires --re: an auto-reply with no parent has nothing to guard against"
            )
        if parent_unreadable:
            raise MailHoldError(
                f"auto-reply HOLD — parent {re!r} exists but is unreadable; "
                "guards cannot be evaluated"
            )
        if parent is None and parent_raw is not None:
            # R3: the parent EXISTS but cannot be parsed — the guards cannot be
            # evaluated; refusing beats replying blind (only a MISSING parent
            # is the sanctioned fail-soft ALLOW).
            raise MailHoldError(
                f"auto-reply HOLD — parent {re!r} exists but is unparseable; "
                "guards cannot be evaluated"
            )
        if parent is None:
            print(
                f"mail.py: --auto with unresolvable --re {re!r} — fail-soft ALLOW (hops=0)",
                file=sys.stderr,
            )
        else:
            ok, reason = should_auto_reply(parent, frm)
            if not ok:
                raise MailHoldError(f"auto-reply HOLD — {reason}")
    if level == "low":
        print(
            "mail.py: WARNING — low-confidence secret-like text in body; sending anyway (use <PASTE …> pointers for real secrets)",
            file=sys.stderr,
        )
    ack = ack or ACK_BY_KIND[kind]
    mid = _ulid()
    content = _frontmatter(mid, frm, to, _now_iso(), re or "", kind, ack, body, hops=hops)
    return _publish(_mail_root() / to / "inbox", mid, content)


# --- claim / ack / requeue ----------------------------------------------------
def claim(msg_id: str, repo: str) -> Path:
    """Claim WITHOUT resolving: the rename lock alone, no acked-by line.

    The honest claim-first-then-work verb (fabrik-lib finding 01KZTGCCZH…): the atomic
    inbox→archive rename is the race lock (the loser's ENOENT stops it — mirrors Agent
    Teams' file-locked task claiming), and the file carries NO disposition until the
    work is actually done (``ack`` appends it in place later; ``requeue`` re-opens).
    """
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    base = _mail_root() / repo
    src = base / "inbox" / f"{msg_id}.md"
    dst = base / "archive" / f"{msg_id}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)  # FileNotFoundError if already claimed — the race lock
    return dst


def _append_ack_line(dst: Path, repo: str, disposition: str) -> None:
    """Append the ack line WITHOUT O_CREAT — if the archived file vanished between ack's
    rename and this append (a concurrent requeue won the race), fail LOUDLY instead of
    silently creating an archive file that holds only an ack line."""
    fd = os.open(dst, os.O_WRONLY | os.O_APPEND)  # FileNotFoundError if requeued meanwhile
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(f"\nacked-by: {repo} · ts: {_now_iso()} · disposition: {disposition}\n")


def ack(msg_id: str, repo: str, disposition: str = "done") -> Path:
    """Claim + resolve — EVERY resolve goes through a per-process rename-locked window.

    Unified after three closer rounds (C1/E1/E2): the direct append-at-path branch let a
    requeue-then-re-claim interleave land a disposition on another agent's fresh claim, and
    a shared window name + message-mtime age gate let a second acker steal a live window
    (renames preserve mtime). Now: optional inbox→archive claim rename, then
    archive/<id>.md → archive/<id>.md.resolving.<pid> (unique — no other process ever
    targets it), ``utime`` stamps the WINDOW's open time, append, rename back. A concurrent
    ack/claim/requeue during the window gets ENOENT (no archive/<id>.md exists). A message
    already RESOLVED (ack line present) raises — the double-ack loser semantics hold.
    """
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    if disposition not in DISPOSITIONS:
        raise MailRefusedError(
            f"unknown disposition {disposition!r} (allowed: {', '.join(DISPOSITIONS)})"
        )
    base = _mail_root() / repo
    src = base / "inbox" / f"{msg_id}.md"
    dst = base / "archive" / f"{msg_id}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(src, dst)  # claim if still in inbox — the race lock (loser: ENOENT later)
    except FileNotFoundError:
        pass
    # stale-window sweep (closer D1, re-grounded per E1): windows are stamped with their
    # OPEN time via utime below, so mtime here IS the window's age (a crash between rename
    # and utime leaves the older message mtime → sweeps EARLIER, which is the safe
    # direction: the file is complete, the append is the only mid-write instant). Only
    # FileNotFoundError is tolerated (closer E3) — a real EACCES/ENOSPC must surface.
    # Sweep ALL stale orphans (closer F1: N crashes → N windows; recovering one and leaving
    # the rest made permanent digest noise): the newest stale one is recovered when <id>.md
    # is missing, every other stale one is UNLINKED (they are pre-append copies of the same
    # message — redundant once one survives). Only FileNotFoundError is tolerated (E3).
    stale: list[Path] = []
    for orphan in dst.parent.glob(f"{msg_id}.md.resolving.*"):
        try:
            if time.time() - orphan.stat().st_mtime > 60:
                stale.append(orphan)
        except FileNotFoundError:
            continue  # the live resolver finished mid-check — fine

    def _mtime_or_zero(o: Path) -> float:
        try:
            return o.stat().st_mtime
        except FileNotFoundError:
            return 0.0  # swept by a concurrent acker mid-sort — uniform ENOENT tolerance

    stale.sort(key=_mtime_or_zero)
    if stale:
        newest = stale.pop()
        if dst.exists():
            stale.append(newest)  # already resolved elsewhere — the orphan is redundant too
        else:
            os.rename(newest, dst)
        for o in stale:
            try:
                os.unlink(o)
            except FileNotFoundError:
                pass
    win = dst.parent / f"{msg_id}.md.resolving.{os.getpid()}"
    # stamp BEFORE the rename (closer F2): the fresh mtime travels with the rename
    # atomically, so no instant exists where a window file carries the message's old mtime
    # (rename-then-stamp left a two-syscall theft window). FileNotFoundError here means
    # unclaimed/absent/mid-window — the caller's error, raised by the rename below anyway.
    try:
        os.utime(dst)
    except FileNotFoundError:
        pass
    os.rename(dst, win)  # FileNotFoundError → unclaimed/absent/mid-window: the caller's error
    try:
        if _ACK_LINE.search(win.read_text(encoding="utf-8", errors="replace")):
            raise FileNotFoundError(f"{msg_id} already resolved")
        _append_ack_line(win, repo, disposition)
    finally:
        os.rename(win, dst)
    return dst


def requeue(msg_id: str, repo: str) -> Path:
    """Move a claimed-but-unresolved message back to inbox for a live agent to re-process.

    Strips any trailing ack/claim marker (`acked-by: … disposition: …`) so the re-opened
    message never carries a STALE disposition into the next reader's inbox — the claim-before-
    work pattern acks up front (the rename is the lock), and a requeue re-opens it cleanly.
    """
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    base = _mail_root() / repo
    src = base / "archive" / f"{msg_id}.md"
    dst = base / "inbox" / f"{msg_id}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)
    raw = dst.read_bytes()
    try:
        text = raw.decode("utf-8")
        lossless = True
    except UnicodeDecodeError:
        # P5-3: an undecodable body is left BYTE-INTACT — a lossy rewrite would
        # permanently substitute U+FFFD in the durable store.
        text, lossless = raw.decode("utf-8", errors="replace"), False
    cleaned = _ACK_LINE.sub("", text).rstrip() + "\n"
    if cleaned != text and lossless:
        dst.write_text(cleaned, encoding="utf-8")
    elif cleaned != text:
        print(
            f"mail.py: {msg_id} has undecodable bytes — ack line left in place (byte-safe)",
            file=sys.stderr,
        )
    return dst


# --- frontmatter parse -------------------------------------------------------
def _parse(text: str) -> dict | None:
    """Parse the leading ``---`` frontmatter block. Returns None if malformed."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            return None
        k, _, v = line.partition(":")
        if not k.strip():  # a line like ": value" — no key
            return None
        fields[k.strip()] = v.strip()
    if not fields.get("id", "").strip() or not fields.get("kind", "").strip():
        return None  # id/kind must be present AND non-empty
    return fields


def _age_seconds(ts: str) -> float:
    """Age vs now — ONE ts convention with the rate guard (D2): naive reads as
    UTC via _ts_epoch, so a legacy naive stamp cannot be simultaneously
    in-window for the rate guard and past the digest threshold."""
    t = _ts_epoch(ts)
    return float("inf") if t is None else datetime.now(UTC).timestamp() - t


# --- digest ------------------------------------------------------------------
def _quarantine(inbox: Path, f: Path) -> bool:
    """Move a malformed file aside. P4-2: fail-soft — a file claimed out from
    under us between the read and this rename must never crash the caller (the
    daily digest would skip every later mailbox and never alert). P4-8: never
    OVERWRITE an earlier quarantined copy (the module's own publish invariant) —
    a repeat corruption lands beside it with a numbered suffix."""
    q = inbox.parent / "malformed"
    try:
        q.mkdir(parents=True, exist_ok=True)
        dst = q / f.name
        n = 1
        while dst.exists():
            dst = q / f"{f.name}.{n}"
            n += 1
        os.rename(f, dst)
    except FileNotFoundError:
        # P10-7: a peer (list_msgs racing digest) already parked it — the copy
        # is counted once by the parked glob; counting a "failure" here too
        # would double-count that file for one run.
        return True
    except OSError as exc:
        print(f"mail.py: quarantine skipped for {f.name} ({exc!r})", file=sys.stderr)
        return False
    return True


def digest(days: int = 3) -> dict:
    """Scan every mailbox: count unacked (ack:required, over the age threshold) + quarantined."""
    root = _mail_root()
    threshold = days * 86400
    unacked = 0
    quarantined = 0
    if not root.is_dir():
        return {"unacked": 0, "quarantined": 0, "repos": []}
    repos: list[str] = []
    for repo_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")
    ):  # P10-6: a .git/.tmp dir is not a mailbox
        repos.append(repo_dir.name)
        inbox = repo_dir / "inbox"
        archive = repo_dir / "archive"
        if inbox.is_dir():
            for f in sorted(inbox.glob("*.md")):
                if f.name.startswith("."):
                    continue  # P9-3: editor swaps / dotfiles are not messages —
                    # skipped symmetrically with the count leg, never parked
                try:
                    raw = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue  # M10: a concurrent claim moved it — never crash the cron
                fm = _parse(raw)
                if fm is None:
                    # P8-1: a SUCCESSFUL move is counted once, by the parked glob
                    # below (counting here too double-counted every file moved
                    # this run). P9-1: a FAILED move is counted HERE — the file
                    # stays in the inbox, never reaches the glob, and a silent 0
                    # would report a clean mailbox over a malformed message.
                    if not _quarantine(inbox, f):
                        quarantined += 1
                    continue
                if fm.get("ack") == "required" and _age_seconds(fm.get("ts", "")) >= threshold:
                    unacked += 1  # required, still unclaimed in inbox
        # P7-6: a quarantined message stays visible — its obligation must not
        # vanish from the operator's only visibility leg after one alert.
        parked = repo_dir / "malformed"
        if parked.is_dir():
            # P8-5: the quarantine namer only ever writes "<id>.md" or
            # "<id>.md.<n>" — a stray dotfile/editor swap must not inflate the
            # operator-facing count.
            quarantined += sum(
                1
                for f in parked.glob("*.md*")
                if f.is_file()
                and not f.name.startswith(".")  # editor swaps / dotfiles are not messages
                and _QUARANTINED_NAME.search(f.name)  # "<name>.md" or "<name>.md.<n>" ONLY
            )
        if archive.is_dir():
            # stranded resolve windows (closer D1) — invisible to every verb until swept;
            # surface them, never report a clean mailbox over an invisible message
            unacked += sum(1 for _ in archive.glob("*.md.resolving*"))
            for f in sorted(archive.glob("*.md")):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue  # M10: concurrent move — skip, never crash the cron
                fm = _parse(text)
                if fm is None:
                    continue
                if (
                    fm.get("ack") == "required"
                    and not _ACK_LINE.search(text)
                    and _age_seconds(fm.get("ts", "")) >= threshold
                ):
                    unacked += (
                        1  # claimed-but-crashed (no REAL acked-by line — body prose can't fake it)
                    )
    return {"unacked": unacked, "quarantined": quarantined, "repos": repos}


def list_msgs(repo: str) -> list[dict]:
    """List a repo's inbox (quarantining any malformed file), newest sort last.

    P5-2: `_safe_name` like every sibling verb — this is the ONE repo-taking
    entry point that MOVES files, so an unguarded `repo` relocated arbitrary
    *.md under any path (absolute paths escaped the root entirely)."""
    _safe_name(repo, "repo")
    inbox = _mail_root() / repo / "inbox"
    out: list[dict] = []
    if not inbox.is_dir():
        return out
    for f in sorted(inbox.glob("*.md")):
        if f.name.startswith("."):
            continue  # P9-3: dotfiles are not messages (symmetric with digest)
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # M10: concurrent claim moved it — skip
        fm = _parse(raw)
        if fm is None:
            _quarantine(inbox, f)
            continue
        out.append(fm)
    return out


def read_msg(msg_id: str, repo: str) -> str:
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    # H3: `malformed/` is scanned too (in the mtime pass below, so the NEWEST
    # quarantined copy wins — P6-8) — a parent quarantined by list/digest
    # between two --auto sends still EXISTS, so the guards stay evaluable (a
    # quarantine must not invert the R3 fail-CLOSED HOLD into a fail-open ALLOW).
    for sub in ("inbox", "archive"):
        p = _mail_root() / repo / sub / f"{msg_id}.md"
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            # M4 (TOCTOU): a concurrent ack renamed it into the resolving window
            # between is_file() and read — fall through to the glob, never fold
            # a live-but-moving parent into "missing" (which fail-soft-ALLOWs).
            pass
    # G2: a message inside an ack's resolving window (<id>.md.resolving.<pid>)
    # still EXISTS — reading it keeps --auto's guards evaluable. Newest by mtime
    # (M7) so a live window's appended content wins over a stale orphan.
    windows: list[Path] = []
    for sub in ("inbox", "archive"):
        windows.extend((_mail_root() / repo / sub).glob(f"{msg_id}.md.resolving.*"))
    # P6-8: repeat corruption numbers the quarantined copies (.1, .2). Ordered
    # by mtime = content-write time (os.rename preserves it, so this is NOT
    # quarantine order — P7-4); the freshest CONTENT is the best available
    # evidence for the guards.
    windows.extend((_mail_root() / repo / "malformed").glob(f"{msg_id}.md*"))

    def _mtime(f: Path) -> float:
        # P2-2: fail-soft — a window vanishing mid-sort must not abort the read
        # (sorted() evaluates every key first), which would fold a still-live
        # sibling into the fail-soft ALLOW M4 exists to prevent.
        try:
            return f.stat().st_mtime
        except OSError:
            return 0.0

    for p in sorted(windows, key=_mtime, reverse=True):
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"no message {msg_id} in {repo}")


# --- CLI ---------------------------------------------------------------------
def _is_hub_repo() -> bool:
    # content-based hub identity (same discipline as session_orient.py)
    return (Path.cwd() / "scripts" / "fabrik_synced_manifest.py").is_file()


def _import_alerting():
    """Resolve the hub's vendored alerting module from a SCRIPT invocation.

    ``python scripts/mail.py digest`` runs with ``sys.path[0] == scripts/`` — ``libs``
    lives at the repo root, one level up — so the lazy import died as
    ModuleNotFoundError and the operator's only visibility leg silently skipped
    (fleet finding 01KZTMZ19…). Insert the repo root FIRST, then import.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.alerting import send_alert  # lazy: hub-only, vendored there

    return send_alert


def _deliver_digest(d: dict) -> None:
    """Hub-guarded, lazy alerting import. Project-side prints locally, never ImportErrors."""
    if d["unacked"] == 0 and d["quarantined"] == 0:
        print("fabrik-mail digest: nothing unacked.")
        return
    title = "fabrik-mail: unacked traffic"
    body = f"{d['unacked']} unacked · {d['quarantined']} quarantined across {len(d['repos'])} mailboxes"
    print(f"{title} — {body}")
    if _is_hub_repo():
        try:
            send_alert = _import_alerting()
            send_alert(title, body, severity="warning")
        except Exception as exc:  # never let the digest crash on the alerting leg
            print(f"mail.py: digest alert delivery skipped ({exc})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mail.py", description="fabrik-mail store + protocol")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_send = sub.add_parser("send", help="publish a message (body on stdin)")
    p_send.add_argument("--to", required=True)
    p_send.add_argument("--kind", required=True, choices=sorted(KINDS))
    p_send.add_argument("--ack", choices=["required", "no"])
    p_send.add_argument("--re")
    p_send.add_argument("--from", dest="frm")
    p_send.add_argument(
        "--auto",
        action="store_true",
        help="unattended reply: enforce the loop-safety guards (requires --re)",
    )

    p_list = sub.add_parser("list", help="list a repo's inbox")
    p_list.add_argument("--repo")

    p_read = sub.add_parser("read", help="print a message")
    p_read.add_argument("id")
    p_read.add_argument("--repo")

    p_claim = sub.add_parser(
        "claim", help="claim WITHOUT resolving (rename lock only, no ack line)"
    )
    p_claim.add_argument("id")
    p_claim.add_argument("--repo")

    p_ack = sub.add_parser("ack", help="claim + resolve a message")
    p_ack.add_argument("id")
    p_ack.add_argument("--repo")
    p_ack.add_argument("--disposition", default="done", choices=list(DISPOSITIONS))

    p_req = sub.add_parser("requeue", help="move a claimed message back to inbox")
    p_req.add_argument("id")
    p_req.add_argument("--repo")

    p_dig = sub.add_parser("digest", help="report unacked + quarantined traffic")
    p_dig.add_argument("--days", type=int, default=3)

    p_sr = sub.add_parser(
        "should-reply", help="advisory loop-safety pre-check: ALLOW (exit 0) / HOLD (exit 3)"
    )
    p_sr.add_argument("id")
    p_sr.add_argument("--repo")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "send":
            body = sys.stdin.read()
            path = send(
                args.to, args.kind, body, frm=args.frm, ack=args.ack, re=args.re, auto=args.auto
            )
            print(path)
        elif args.cmd == "list":
            for fm in list_msgs(args.repo or _current_repo()):
                print(
                    f"{fm['id']} · {fm.get('from', '?')} · {fm.get('kind', '?')} · ack={fm.get('ack', '?')}"
                )
        elif args.cmd == "read":
            print(read_msg(args.id, args.repo or _current_repo()))
        elif args.cmd == "claim":
            print(claim(args.id, args.repo or _current_repo()))
        elif args.cmd == "ack":
            print(ack(args.id, args.repo or _current_repo(), disposition=args.disposition))
        elif args.cmd == "requeue":
            print(requeue(args.id, args.repo or _current_repo()))
        elif args.cmd == "digest":
            _deliver_digest(digest(days=args.days))
        elif args.cmd == "should-reply":
            repo = args.repo or _current_repo()
            try:
                _safe_name(repo, "repo")  # P3-2: an unsafe repo is fail-CLOSED
            except MailRefusedError as exc:
                print(f"HOLD: unsafe repo — {exc}")
                return 3
            try:
                parent_fm = _parse(read_msg(args.id, repo))
            except MailRefusedError:
                print("ALLOW (unresolvable id — not a ULID; fail-soft)")
                return 0
            except FileNotFoundError:
                print("ALLOW (no such parent — fail-soft)")
                return 0
            except OSError:
                print("HOLD: parent exists but is unreadable — guards cannot be evaluated")
                return 3
            if parent_fm is None:
                print("HOLD: parent exists but is unparseable — guards cannot be evaluated")
                return 3
            ok, reason = should_auto_reply(parent_fm, repo)
            print("ALLOW" if ok else f"HOLD: {reason}")
            return 0 if ok else 3
    except MailHoldError as exc:
        print(f"mail.py: {exc}", file=sys.stderr)
        return 3
    except MailRefusedError as exc:
        print(f"mail.py: REFUSED — {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"mail.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
