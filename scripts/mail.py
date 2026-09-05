#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mail.py, docs/reference/fabrik-mail.md, docs/workstation/fabrik-mail.md, .env.example, docs/CONFIGURATION.md
"""fabrik-mail — durable hub↔project AI message store + protocol (stdlib-only).

One neutral-path file mailbox per repo at ``$FABRIK_MAIL_ROOT/<repo>/{inbox,archive}``
(default root ``/opt/fabrik-mail``). A message is one ``.md`` file: YAML-ish frontmatter
(``id from to ts re kind ack hops`` + optional ``agent``) + a markdown body. Subcommands:

    send  --to <repo> --kind <k> [--ack required|no] [--re <id>] [--from <repo>] [--auto]
          [--to-agent <role>] [--broadcast] < body
          (hub-bound sends REQUIRE --to-agent infra|fleet|intel, --broadcast, or a
          kind=reply thread — the addressing guard; see the refusal text)
    list  [--repo <repo>] [--agent <role>]
    read  <id> [--repo <repo>]
    ack   <id> [--repo <repo>] [--disposition done|blocked|wontfix]
    route <id> [--to-agent <role>] [--repo <repo>]   # re-address live mail; empty role clears
    requeue <id> [--repo <repo>]
    digest [--days N]
    sweep [--days N] [--repo <repo>]   # archive stale ack:no mail; obligations never swept
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

# THE PLACEHOLDER EXEMPTION IS REMOVED (round 24). Rounds 19-23 tried five
# successive versions of a "is this password a placeholder?" classifier so that a
# finding could quote a redacted DSN verbatim. EVERY ONE leaked a real credential
# to all ~46 synced repos, and each leak scored `None` — not even a warning:
#   19  shape wildcards: `<any>`, `${any}`, `YOUR...`      → secret in brackets
#   20  substring match: PASS/HERE/NONE inside words       → `CompassionateHeart`
#   21  wrapper trusted on shape alone                     → `<CorrectHorse...>`
#   22  ...and its cost twin: a quadratic scan             → 4.7s per send
#   23  `@` unanchored: placeholder@REAL_SECRET@host       → `my@Zx82Kf9mQpLr7T`
# Deciding "is this string a secret or a label for one?" from the string alone is
# not a winnable classification problem, and every attempt spent a real bypass to
# learn that. The guard is a boundary, so it fails CLOSED with no exceptions: any
# `scheme://user:pass@host` refuses. Quoting evidence costs one keystroke — drop
# the scheme (`user:REDACTED@host`) or break the shape (`postgres:// … @host`) —
# and the refusal is loud, immediate and self-explaining. Do NOT reintroduce a
# classifier here; five rounds of evidence say it will leak.

# High-confidence secret signatures — REFUSE the send.
_SECRET_HIGH = [
    _re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    # P22-2: the `\w*` runs are BOUNDED. Unbounded, this backtracks quadratically —
    # a 64 KB body of `SECRET_` tokens took ~4.7s on send()'s hot path, and every
    # repo in the fleet pays it on every send. (Pre-existing, not introduced by
    # this loop: measured at 4.696s on f338fd5d, before round 10.) An identifier
    # is never 64 chars either side of the keyword, so the bound changes nothing
    # real — `AWS_SECRET_ACCESS_KEY=…` still matches.
    # Two defects, one line, both found 2026-08-29 mailing measured suite results to 18 repos.
    #
    # (1) FALSE POSITIVE — a pytest node ID is shaped exactly like an assignment to the old
    #     pattern: `tests/x.py::TestTokenBucket::test_acquire_tokens` gives TOKEN from the class
    #     name, `::` for the `[:=]`, and `:test_acquire_tokens` as a 19-char `\S{16,}` "value".
    #     The send REFUSED outright, and auth-shaped test names are precisely the failures most
    #     worth mailing. `(?!:)` rejects the first colon of a `::`; the second cannot start a
    #     match because `[\w-]` never consumes the first.
    #
    # (2) PERFORMANCE — the old leading `\b[\w-]{0,64}` was REDUNDANT (the engine may start the
    #     match at the keyword itself, so a prefix needs no explicit run) and quadratic: it
    #     retried up to 64x64 backtracks at every one of ~65k positions. Measured on the
    #     `"PASSWORD-" * 7300` body from test_generic_scheme_scan_stays_fast: **1.42s -> 0.025s**,
    #     a 58x cut on every send fleet-wide. That test was RED at HEAD before this change — it
    #     had been failing unnoticed because the hub does not run its own pytest.
    #     The trailing run is possessive (`{0,64}+`, Python 3.11+) so it cannot backtrack either;
    #     making the LEADING one possessive was tried and rejected — it swallows the keyword and
    #     misses every real secret.
    _re.compile(
        r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)[\w-]{0,64}+\s*[:=](?!:)\s*\S{16,}",
        _re.I,
    ),
    _re.compile(r"\bsk-[A-Za-z0-9-]{16,}"),  # sk-, sk-ant-, sk-proj- (hyphens kept)
    # P16-4: the hyphen form above misses the UNDERSCORE vendor style (Stripe
    # `sk_live_`/`sk_test_`, restricted `rk_`), which then fell in the dead zone
    # between it and the assignment pattern — prose like "my key is sk_live_…"
    # carries no `:`/`=`, so nothing matched at all. `pk_` is the PUBLISHABLE
    # key and is deliberately not listed.
    _re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    _re.compile(r"\bgh[posru]_[A-Za-z0-9]{20,}"),  # classic GitHub tokens
    _re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),  # fine-grained PATs
    _re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    _re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),  # AWS long-term + session
    _re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    _re.compile(r"(?i)\bauthorization:\s*bearer\s+\S{8,}"),  # Bearer header
    _re.compile(
        r"\b[a-z][a-z0-9+.-]{0,31}://[^\s/:@]*:" + r"[^\s/@]+@", _re.I
    ),  # scheme://[user]:pass@host (user optional — redis://:pw@). P16-2: _re.I —
    # the scheme was lower-case-only, so a copy-pasted `Postgres://` DSN (how
    # config templates and docs capitalise it) bypassed the guard entirely.
    # P16-1: the pattern above excludes `/` from the password so it cannot eat a
    # documentation URL (`https://host/path:frag@anchor`) — but that also let any
    # DSN with a `/` in its password through scoring NOTHING, and `/` is routine
    # in base64-derived generated passwords. For the schemes that exist to CARRY
    # credentials, allow it: no doc link uses these, so there is no false-positive
    # surface to trade away.
    # `user:pass@host` and `host:port/path@note` are LEXICALLY IDENTICAL — nothing
    # distinguishes `user:8080/api@db-host` (a credential) from
    # `internal-docs:8080/api@readme` (a doc link). Rounds 16-18 tried three
    # splits and each one leaked at the seam between its own halves.
    # This REVERSES the P17-1 adjudication, deliberately: that round traded a
    # real false NEGATIVE for a SYNTHETIC false positive, on a guard whose entire
    # purpose is that secrets never travel. These schemes exist to CARRY
    # credentials — `scheme://a:b@c` in a DSN scheme is a credential, and the
    # ambiguous doc-link form does not appear in a single one of the 910 real
    # messages in the live store. So: fail CLOSED, and let the rare false
    # positive be a loud refusal the sender can rephrase.
    # (Non-DSN schemes keep the stricter `/`-excluding password class above, so
    # ordinary `https://host/path:frag@anchor` doc links still send.)
    _re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mariadb|rediss?|mongodb(?:\+srv)?|amqps?"
        r"|ftps?|sftp|ssh|smtps?|clickhouse|mssql|oracle|cockroachdb)"
        r"://[^\s/:@]*:" + r"[^\s@]+@",
        _re.I,
    ),
]
# Low-confidence hints — WARN but still deliver (not bare "key", too noisy).
# P16-3: `pwd` was in the HIGH pattern's identifier set but missing here, so a
# short real password under HIGH's 16-char floor (`pwd: hunter2`) scored NOTHING
# while the identical `password:` line was at least caught by this net — the two
# keyword sets had silently diverged.
_SECRET_LOW = _re.compile(r"\b(?:password|passwd|pwd|secret|token|credential|api[_-]?key)\b", _re.I)

# Path-safety: a repo/recipient token is a single /opt directory name; a msg id is a
# 26-char Crockford ULID. Neither may contain a path separator or a `..` component —
# the guard against traversal via unvalidated `to`/`repo`/`msg_id` args (defense in
# depth under the single-operator threat model; a traversal is a loud refusal).
_SAFE_NAME = _re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_ID = _re.compile(r"^[0-9A-Z]{26}$")
# P10-4 + P11-3: what _quarantine actually writes — "<name>.md" or
# "<name>.md.<n>". Excludes `.md.bak` / `.md.resolving.*` / non-.md strays; a
# bare `README.md` dropped into malformed/ is indistinguishable from a real
# copy by name alone and still counts (over-count = the fail-safe direction).
_QUARANTINE_SLOTS = 1000  # P13-8: bound on the numbered-suffix probe
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
    mid: str,
    frm: str,
    to: str,
    ts: str,
    re_: str,
    kind: str,
    ack: str,
    body: str,
    hops: int = 0,
    agent: str = "",
) -> str:
    # `agent` is the INTRA-mailbox addressee (see _safe_agent). Emitted only when
    # set, so a message without one is byte-identical to a pre-2026-08-23 message
    # and every legacy reader is unaffected.
    agent_line = f"agent: {agent}\n" if agent else ""
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
        f"{agent_line}"
        "---\n"
        f"{body}" + ("" if body.endswith("\n") else "\n")
    )


# The hub's shared three-agent mailbox is the ONLY mailbox with beats — the send/route
# guards key on membership here. Project mailboxes keep free-form roles (_safe_agent is
# shape-only). Adding a future beat = extend this tuple (plus the charter file).
HUB_BEATS = ("infra", "fleet", "intel")


def _safe_agent(name: str) -> str:
    """Validate an intra-mailbox addressee (a ROLE, not a repo and not a session).

    The hub runs three agents — infra · fleet · intel — sharing ONE `fabrik`
    mailbox, so intra-hub traffic is `from: fabrik → to: fabrik` with no addressee
    at all. Agents worked around it in PROSE (`[infra→fleet]` body prefixes), and
    some put a role in `from:`, which is not a repo and breaks every routing and
    rate-limit guard that keys on it. 31 of 72 messages in the live fabrik inbox
    were this shape.

    Deliberately NOT per-session sub-addressing (rejected 2026-08-15, and the
    right layer for window-to-window is native cross-session messaging): a ROLE is
    stable, charter-backed (`docs/reference/agents/`), and survives restarts. It is
    a FILTER, never a lock — an unaddressed message stays visible to everyone, so
    nothing can be hidden from an agent by addressing it elsewhere.
    """
    if not name:
        return ""
    if not _SAFE_NAME.fullmatch(name) or name in (".", ".."):
        raise MailRefusedError(f"unsafe agent {name!r}: a plain role name ([A-Za-z0-9._-])")
    return name


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
        for f in d.glob("*.md"):  # P13-1: unsorted — this COUNTS, it never orders;
            # sorted() only materialized the whole archive listing to no end
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


def _subject_tokens(body: str) -> frozenset[str]:
    """Content words of a message's subject line — the duplicate-report key."""
    first = ""
    for line in body.splitlines():
        if line.strip():
            first = line
            break
    first = _re.sub(r"^\s*#+\s*", "", first)
    first = _re.sub(r"^\s*(?:subject|re)\s*:\s*", "", first, flags=_re.I)
    words = _re.findall(r"[A-Za-z_][A-Za-z0-9_.]{2,}", first.lower())
    # Drop the filler that every report shares, or "the/and/for" alone would pair
    # two unrelated subjects.
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "not",
        "but",
        "all",
        "are",
        "was",
        "its",
        "has",
        "have",
        "one",
        "two",
        "you",
        "your",
        "our",
        "can",
        "subject",
        "report",
        "finding",
        "request",
        "issue",
        "bug",
        "fix",
        "fixed",
    }
    return frozenset(w for w in words if w not in stop)


def _warn_if_duplicate(to: str, body: str) -> None:
    """Point a sender at an already-OPEN report of the same thing. Never refuses.

    The cross-repo `command_run.py` corruption was reported NINE times by SIX
    senders, each escalating, because a sender cannot see another repo's inbox and
    nothing surfaced that the defect was already open. Every one of those reports
    was correct and well-written; the waste was purely that nobody could tell.

    WARN, never refuse — and that direction is not a preference, it is a lesson
    paid for the same day: the quota advisory suppressed a repeat and thereby
    suppressed a genuine ESCALATION (86% → 97% went silent). A duplicate report
    is cheap; a silenced escalation is how a defect survives nine reports. So this
    prints a pointer and gets out of the way. Entirely fail-soft: any error here
    must never block a send.
    """
    try:
        want = _subject_tokens(body)
        if len(want) < 3:
            return  # too short to judge — silence beats a false pairing
        inbox = _mail_root() / to / "inbox"
        if not inbox.is_dir():
            return
        for f in sorted(inbox.glob("*.md"), reverse=True)[:200]:
            if f.name.startswith("."):
                continue
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse(raw)
            if fm is None:
                continue
            have = _subject_tokens(raw.split("---", 2)[-1])
            if not have:
                continue
            overlap = len(want & have) / max(1, min(len(want), len(have)))
            if overlap >= 0.7:
                print(
                    f"mail.py: similar open message {fm.get('id')} already in {to}'s inbox "
                    f"(from {fm.get('from')}) — consider --re {fm.get('id')} to thread onto it "
                    "rather than opening a second report",
                    file=sys.stderr,
                )
                return
    except Exception:
        return  # a duplicate hint must NEVER be able to block a send


_STRUCTURED_KINDS = frozenset({"finding", "request", "upstream-feedback"})
_STRUCTURE_KEYS = ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC")


def _structure_gaps(kind: str, body: str) -> list[str]:
    """The D-035 message contract (operator directive 2026-08-30): substantive mail
    carries 5W1H + a FACTUAL root cause (WHY) + SYSTEMIC (the class, never just the
    instance); ABDUCTIVE/INDUCTIVE/DEDUCTIVE/COUNTERFACTUAL sections are optional,
    applied where they fit. Returns the MISSING mandatory keys; [] when compliant or
    exempt (reply/relay/ack traffic). Header match is deliberately loose — a line
    starting with the key (any case, markdown decoration tolerated) followed by ':'.
    Advisory tier: send() WARNS on gaps and never refuses (measured-rollout law)."""
    if kind not in _STRUCTURED_KINDS:
        return []
    # only AUTHORED lines count: skip fenced code blocks (templates) and blockquotes
    # (forwarded/quoted mail) — someone else's structure is not yours; and a header
    # needs CONTENT after the colon (>= 2 non-space chars) — an empty 'WHY:' is not
    # a root cause (author-blind review 2026-08-30).
    authored = []
    fenced = False
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or stripped.startswith(">"):
            continue
        authored.append(line)

    # A SECTION HEADER is: optional markdown decoration, the key at the START of the
    # line, an optional qualifier, then the colon. Every clause below fixes a verdict
    # this checker got WRONG on real mail (all three measured 2026-08-30):
    #   1. the qualifier budget was 24 chars, which rejected the qualified form the
    #      contract itself invites ("WHY (factual root cause, measured):" = 37) and
    #      told a compliant author they were missing sections they had;
    #   2. leading WHITESPACE was allowed, so an INDENTED illustration ("    WHY:")
    #      inside a mail that merely QUOTES the contract satisfied the check — the
    #      worse direction, since it certifies an unstructured mail as compliant;
    #   3. content was required INLINE after the colon, so a section whose body is a
    #      block on the following lines (a command, a list, a table) read as empty.
    # An empty section is still a gap: the look-ahead stops at the next header.
    # A header may end in ` — ` (em/en dash, spaced) as well as `:` — `SYSTEMIC — the class…` is the
    # contract met in substance; the colon-only form reported it missing (site-provisioner
    # 01M1QWM094Z6S0ZYGPKTB4NPY0, 2026-09-05). A bare hyphen is NOT a separator (`WHY-not`).
    # The qualifier is LAZY so the EARLIEST separator wins: greedy, `WHY — see: x` ran past the
    # dash and took the colon inside the content, leaving ` x` as the section (review pass 3).
    keys = "|".join(
        _STRUCTURE_KEYS
    )  # only the contract's own keys may be slash-combined (abc/WHO: never credits WHO)

    def _hdr(k: str):
        # `WHEN/WHO:` credits both keys (01M1H52X); a backtick before the colon means the colon
        # belongs to a `path:line`, not to the header (01M1J0KY: `WHERE — \`x.py:496\`:` passed).
        return _re.compile(
            rf"(?i)^[*#\-]{{0,3}} ?(?:(?:{keys})/)*{k}\b(?:/(?:{keys}))*[^:\n`]{{0,120}}?(?::|\s[—–]\s)(.*)$"
        )

    def substantive(s: str) -> bool:
        return len(_re.sub(r"\s", "", s)) >= 2

    any_header = _re.compile(
        rf"(?i)^[*#\-]{{0,3}} ?(?:(?:{keys})/)*(?:{'|'.join(_STRUCTURE_KEYS)})\b(?:/(?:{keys}))*[^:\n`]{{0,120}}?(?::|\s[—–]\s)"
    )

    gaps = []
    for key in _STRUCTURE_KEYS:
        pat = _hdr(key)
        found = False
        for i, line in enumerate(authored):
            m = pat.match(line)
            if not m:
                continue
            if substantive(m.group(1)):
                found = True
                break
            for nxt in authored[i + 1 :]:  # body on the following lines?
                if not nxt.strip():
                    continue
                if any_header.match(nxt):
                    break  # the very next thing is another header => this one is empty
                found = substantive(nxt)
                break
            if found:
                break
        if not found:
            gaps.append(key)
    return gaps


def send(
    to: str,
    kind: str,
    body: str,
    frm: str | None = None,
    ack: str | None = None,
    re: str | None = None,
    auto: bool = False,
    to_agent: str | None = None,
    broadcast: bool = False,
) -> Path:
    """Publish a message to <to>'s inbox. Raises MailRefusedError on any refusal (nothing written)."""
    frm = frm or _current_repo()
    _safe_name(to, "recipient")
    _safe_name(frm, "sender")
    to_agent = _safe_agent(to_agent or "")
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
    # SAME-REPO is not project→project. The star exists so a project never mails a
    # SIBLING project directly, bypassing the hub's audit trail — a self-send crosses
    # no topology and lands in the repo's OWN inbox, which is precisely the "shared
    # inbox for a repo's concurrent agents" the synced constitution advertises
    # (templates/governance/CLAUDE.md). Refusing it left the commonest multi-agent
    # handoff with NO channel: the shared-tree rule forbids a lane from editing a
    # sibling lane's committed file and says report it instead — and there was nowhere
    # to report to (trade-intelligence 01M14VS0XQ, whose failing e2e ended up visible
    # only in STRATEGIC_BACKLOG.md). The hub-relay workaround does not apply either:
    # asking infra to relay a message from a repo back to itself is a round trip
    # through a third party for a purely local handoff.
    # The free-text `--from` is a LANE name (wef1), not a repo — topology is decided by the repo
    # this process runs in (01M1K6H6, 2026-09-03: `--from wef1 --to web-ecommerce-factory` was
    # refused as project→project while sitting IN web-ecommerce-factory).
    sending_repo = _current_repo()
    same_repo = sending_repo == to
    if not same_repo and frm != to and not _is_hub(frm) and not _is_hub(to):
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
    # D-035 advisory AFTER every unconditional refusal above — printing 'Sent anyway'
    # before a guard that then raises was a false log line (author-blind review
    # 2026-08-30). The auto-path guards below can still HOLD, but a HOLD is not a
    # refusal of the body's structure.
    _gaps = _structure_gaps(kind, body)
    if _gaps:
        print(
            f"[mail-structure advisory, D-035] this {kind} is missing mandatory sections: "
            f"{', '.join(_gaps)} — the 5W1H + factual-WHY + SYSTEMIC contract "
            "(docs/reference/fabrik-mail.md § The message contract). Sent anyway (advisory tier).",
            file=sys.stderr,
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
    # Addressing guard — the hub's shared three-agent mailbox only. Keyed on the LITERAL
    # "fabrik", deliberately never _is_hub(): fabrik-lib's mailbox has no beats and stays
    # unguarded. Runs AFTER the recipient/star checks and the HIGH-secret refusal (D6/E1 —
    # a credential leak is diagnosed as a leak on the FIRST attempt, never masked by an
    # addressing nag) and AFTER parent resolution (a --re reply with a resolvable parent is
    # thread-anchored and exempt). Checks the EFFECTIVE ack, post-ACK_BY_KIND default.
    if to == "fabrik":
        if to_agent and to_agent not in HUB_BEATS:
            raise MailRefusedError(
                f"unknown hub beat {to_agent!r} — a typo'd beat hides mail from every "
                f"`list --agent` view; hub beats: {', '.join(HUB_BEATS)}"
            )
        # Threaded replies are exempt BY KIND (kind=="reply" with a --re), never by
        # parent resolvability: keying on resolvability broke the sanctioned --auto
        # prose-re fail-soft AND let any kind bypass the guard with a forged --re.
        # A reply that DOES resolve its parent inherits the thread's owner, so
        # ownership survives every hop instead of evaporating at the first reply.
        is_thread_reply = kind == "reply" and bool(re)  # "" is no thread ref
        if is_thread_reply and not to_agent and parent is not None:
            inherited = parent.get("agent") or ""
            if inherited in HUB_BEATS:
                to_agent = inherited
        if not to_agent and broadcast and ack == "required":
            raise MailRefusedError(
                "broadcast + ack:required is a contradiction — an obligation nobody owns "
                "can never be acked; address it (--to-agent) or drop the ack (--ack no)"
            )
        if not to_agent and not broadcast and not is_thread_reply:
            raise MailRefusedError(
                "unaddressed hub-bound send — the fabrik mailbox is shared by THREE agents, "
                "so name the owner:\n"
                "  --to-agent infra  (commands · rules packs · enforcement · hooks · "
                "fabrik-mail · workstation)\n"
                "  --to-agent fleet  (VPS · deploy · specs/services · scaffolding · "
                "monitoring)\n"
                "  --to-agent intel  (models · benchmarks · flywheel · reviews)\n"
                "  genuinely all-agents → --broadcast (with --ack no)"
            )
    # AFTER every refusal, BEFORE minting: a hint must never change whether a
    # message is accepted, and must never fire for a send that was going to be
    # refused anyway. Threading onto an existing report is the sender's choice.
    if not re:
        _warn_if_duplicate(to, body)
    mid = _ulid()
    content = _frontmatter(
        mid, frm, to, _now_iso(), re or "", kind, ack, body, hops=hops, agent=to_agent
    )
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


def route(msg_id: str, to_agent: str, repo: str | None = None) -> Path:
    """Set (or clear) the intra-mailbox addressee on a message ALREADY in the inbox.

    ``--to-agent`` only existed at SEND time, so the hub's shared ``fabrik`` mailbox had no
    way to record who owns a message once it had been delivered. Ownership therefore lived
    in body prose (``[infra->fleet]`` subject prefixes), which no filter can read: measured
    2026-08-23, 24 of the 28 live hub messages carried no addressee at all, so
    ``list --agent`` showed all three hub agents the same undifferentiated pile and every
    triage decision had to be re-derived by reading bodies.

    Routing is a FILTER, never a lock (see :func:`_safe_agent`) — re-routing can never hide
    a message, because ``list --agent X`` shows addressed-to-X PLUS everything unaddressed.
    Passing an empty role CLEARS the addressee, so a wrong assignment is always reversible;
    an assignment nobody can undo would be a lock in all but name.

    Frontmatter only: the body is copied byte-for-byte (a body containing its own ``---``
    line must not be mistaken for the header terminator), every other header is preserved,
    and the rewrite lands via ``os.replace`` so a reader never observes a half-written
    message. The inbox is the only legal target — an ARCHIVED message is settled history
    and re-routing it would rewrite the audit trail.
    """
    _safe_id(msg_id)
    repo = repo or _current_repo()
    _safe_name(repo, "repo")
    agent = _safe_agent(to_agent or "")  # raises on an unsafe role BEFORE any mutation
    if repo == "fabrik" and agent and agent not in HUB_BEATS:
        # Same harm as the send guard, one verb later: a typo'd beat hides the message
        # from all three `list --agent` views. Clearing ('') stays legal — reversibility
        # is the point of route-as-filter.
        raise MailRefusedError(
            f"unknown hub beat {agent!r} — hub beats: {', '.join(HUB_BEATS)} (or '' to clear)"
        )
    path = _mail_root() / repo / "inbox" / f"{msg_id}.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise MailRefusedError(
            f"{msg_id}: not in {repo}/inbox — route only re-addresses live mail "
            f"(an archived message is settled history)"
        ) from exc
    if _parse(text) is None:
        raise MailRefusedError(f"{msg_id}: malformed frontmatter — refusing to rewrite it")
    end = text.find("\n---", 4)
    header = [ln for ln in text[4:end].splitlines() if not ln.startswith("agent:")]
    if agent:
        header.append(f"agent: {agent}")
    rebuilt = "---\n" + "".join(f"{ln}\n" for ln in header) + text[end + 1 :]
    if _parse(rebuilt) is None:  # never write something we could not read back
        raise MailRefusedError(f"{msg_id}: rewrite would corrupt the frontmatter — aborted")
    tmp = path.with_suffix(f".md.routing.{os.getpid()}")
    tmp.write_text(rebuilt, encoding="utf-8")
    os.replace(tmp, path)
    return path


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
    # P14-3: the rstrip() was unconditional and applied to the WHOLE file, so a
    # body ending in deliberate blank lines or spaces was truncated on the first
    # requeue even when no ack line existed to strip — silent, durable, and not
    # what this docstring or the reference doc describe. Normalize ONLY when we
    # actually removed a marker.
    stripped = _ACK_LINE.sub("", text)
    cleaned = (stripped.rstrip() + "\n") if stripped != text else text
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
        # P13-8: the slot was picked by check-then-act and taken with os.rename,
        # which OVERWRITES silently — P4-8's "never overwrite an earlier copy"
        # held only while nobody raced. os.link is the module's own atomic
        # EEXIST claim (the _publish invariant); the unlink then completes the
        # move. Same filesystem by construction (siblings under the repo dir).
        n = 0
        created = False
        while True:
            dst = q / (f.name if n == 0 else f"{f.name}.{n}")
            try:
                os.link(f, dst)
                created = True
                break
            except FileExistsError:
                # P14-2: os.rename CONSUMED the source, so a racing peer hit
                # ENOENT and stopped. os.link does not, so both callers can win
                # DIFFERENT slots and park the same message twice. A slot holding
                # our own inode IS our message, already parked by the peer —
                # adopt it rather than minting a duplicate the operator would
                # have to reconcile by hand.
                try:
                    if dst.stat().st_ino == f.stat().st_ino:
                        break
                except OSError:
                    pass
                n += 1
                if n > _QUARANTINE_SLOTS:
                    raise  # bounded: an unbounded probe would hang the digest
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass  # the copy is parked — a peer clearing the source is success
        except OSError:
            # P14-1 rolled back a half-done move; P15-1/P15-2 fix what that arm got
            # wrong once the P14-2 adoption branch could reach it. The ONLY question
            # that matters here is whether a parked copy survives, because the parked
            # glob counts exactly what is on disk:
            #   * we ADOPTED a peer's copy (created=False) — it stays parked, so the
            #     glob counts it once. Reporting failure too made digest count the
            #     SAME message a second time, every run, forever (P15-1) — the very
            #     unbounded inflation P14-1 existed to kill.
            #   * we created the copy and the SOURCE is already gone (a peer removed
            #     it) — our copy is the last instance in existence. Rolling it back
            #     would erase the message from disk entirely and report nothing:
            #     silent data loss (P15-2).
            # Only when we created the copy AND the source survives is a rollback the
            # honest move: the tree returns to exactly as we found it, and the caller
            # counts a failed quarantine (P9-1).
            if created and f.exists():
                try:
                    os.unlink(dst)
                except OSError:
                    pass
                raise
            return True  # a copy is parked — the glob counts it, once
    except FileNotFoundError:
        # P10-7 + P11-1: FileNotFoundError has FOUR causes, only ONE of which is
        # "a peer already parked it" (then the parked glob counts the copy and a
        # failure here would double-count). The others — a peer CLAIMED the
        # corrupt file into archive/ (claim() never parses, and the archive leg
        # skips unparseable rows, so nothing would ever count it again), the
        # destination dir vanished, the file was deleted — must all COUNT, or
        # digest reports a clean mailbox over a malformed message. Distinguish
        # by what is actually on disk.
        # P12-1: the SAME predicate the counting leg uses — a broader glob
        # accepted an operator's `<id>.md~` vim backup as "parked" while the
        # count rejected it, so the message was counted by NEITHER leg.
        if not q.is_dir():
            return False  # P12-3: the destination vanished — count it
        return any(_QUARANTINED_NAME.search(c.name) for c in q.glob(f"{f.name}*") if c.is_file())
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
            # P14-4: a window is only a STRAND once it has outlived any plausible
            # ack. Counting every one ignored the age threshold this function's own
            # docstring promises, so a healthy in-flight ack() racing the digest
            # cron reported a phantom unacked message. Age comes from the window's
            # mtime — the RENAME has no ts of its own — and this leg stays
            # independent of ack:required because D1's point is that a strand is
            # invisible to every OTHER verb regardless of what it asked for.
            for p in archive.glob("*.md.resolving*"):
                if p.name.startswith("."):
                    continue
                try:
                    if time.time() - p.stat().st_mtime >= threshold:
                        unacked += 1
                except OSError:
                    continue  # M10: a concurrent sweep resolved it — never crash the cron
            for f in sorted(archive.glob("*.md")):
                if f.name.startswith("."):
                    continue  # P13-6: the FOURTH glob — this was the one leg
                    # without the guard its three siblings carry (P9-3/P10-5),
                    # and digest never MOVES an archive file, so a hidden backup
                    # with ack:required re-counted as unacked on every single run
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


def sweep(days: int = 14, repo: str | None = None) -> int:
    """Archive stale `ack: no` mail. Returns how many messages moved.

    THE MISSING EXIT PATH. `finding`/`reply`/`relay` default to `ack: no`, and
    nothing ever obliged anyone to archive them — so the inbox was append-only in
    practice and silted up until a human cleared it by hand (38 messages on
    2026-08-23, some resolved back in mid-August and still showing as unread).
    The cost is not the reading: a real defect report arriving behind forty stale
    ones gets skimmed, which is exactly how a cross-repo corruption defect was
    reported nine times before anyone acted.

    Three invariants make this safe to run unattended:
      * an `ack: required` OBLIGATION is NEVER swept, at any age — those are
        closed by a human or an agent doing the work, never by a timer;
      * age is read from the message's own `ts`, not mtime (a restore rewrites
        mtime; `_ts_epoch` is the same clock the digest and rate cap use), and an
        unparseable ts is left ALONE rather than guessed at;
      * archiving is the existing atomic rename, so a message a peer is claiming
        concurrently loses the race harmlessly (ENOENT → skip).

    Nothing is deleted: `archive/` is the audit trail and stays complete.
    """
    root = _mail_root()
    if not root.is_dir():
        return 0
    threshold = max(0, days) * 86400
    now_ts = datetime.now(UTC).timestamp()
    repos = [repo] if repo else _mailbox_names()
    moved = 0
    for name in repos:
        try:
            _safe_name(name, "repo")
        except MailRefusedError:
            continue
        inbox = root / name / "inbox"
        if not inbox.is_dir():
            continue
        for f in sorted(inbox.glob("*.md")):
            if f.name.startswith("."):
                continue  # dotfiles are not messages (symmetric with every other glob)
            try:
                fm = _parse(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue  # a concurrent claim moved it — never crash a sweep
            if fm is None or fm.get("ack") == "required":
                continue  # malformed is digest's business; an obligation is nobody's timer
            ts = _ts_epoch(fm.get("ts", ""))
            if ts is None or now_ts - ts < threshold:
                continue  # unparseable ts → leave it ALONE; fresh → not stale
            dst = root / name / "archive" / f.name
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.rename(f, dst)
                moved += 1
            except OSError:
                continue  # lost a race with a claim/ack — harmless
    return moved


def _mailbox_names() -> list[str]:
    """Every mailbox dir under the root (the digest's discovery rule)."""
    root = _mail_root()
    try:
        return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []


def list_msgs(repo: str, agent: str | None = None) -> list[dict]:
    """List a repo's inbox (quarantining any malformed file), newest sort last.

    P5-2: `_safe_name` like every sibling verb — this is the ONE repo-taking
    entry point that MOVES files, so an unguarded `repo` relocated arbitrary
    *.md under any path (absolute paths escaped the root entirely).

    `agent` FILTERS to what this role should read: messages addressed to it, plus
    every UNADDRESSED message. It is deliberately not a lock — addressing a
    message to `fleet` must never hide it from a human or from a role that
    already knows to look, and an unaddressed message stays everyone's. Omit
    `agent` to see the whole inbox, which is the pre-2026-08-23 behaviour."""
    _safe_name(repo, "repo")
    agent = _safe_agent(agent or "")
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
        if agent and (fm.get("agent") or "") not in ("", agent):
            continue  # addressed to a DIFFERENT role — unaddressed always passes
        out.append(fm)
    return out


def read_msg(msg_id: str, repo: str) -> str:
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    # H3: `malformed/` is scanned too (in the mtime pass below, so the NEWEST
    # quarantined copy wins — P6-8) — a parent quarantined by list/digest
    # between two --auto sends still EXISTS, so the guards stay evaluable (a
    # quarantine must not invert the R3 fail-CLOSED HOLD into a fail-open ALLOW).
    anomalous = False
    for sub in ("inbox", "archive"):
        p = _mail_root() / repo / sub / f"{msg_id}.md"
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
            if p.exists():
                # P17-2: something occupies the slot but is not a file (a stray
                # directory from a bad restore). Falling through treated a parent
                # that structurally EXISTS as MISSING, inverting C2's fail-CLOSED
                # HOLD into a fail-open ALLOW.
                # P18-2: but REMEMBER it, never raise here — raising inside the
                # loop aborted the search at the first anomalous slot, so a stray
                # directory in `inbox/` shadowed a perfectly readable parent in
                # `archive/` (and the window + malformed fallbacks below), turning
                # a working auto-reply into a spurious HOLD. The anomaly only
                # matters if NOTHING readable is found anywhere.
                anomalous = True
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
    if anomalous:
        # P18-2: nothing readable anywhere, but the slot IS occupied — "exists
        # but unreadable", which the --auto path reads as HOLD (C2), never as the
        # fail-soft ALLOW that "missing" earns.
        raise IsADirectoryError(f"{msg_id} in {repo} exists but is not a regular file")
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
    p_send.add_argument(
        "--to-agent",
        dest="to_agent",
        help="intra-mailbox addressee ROLE (infra/fleet/intel) — a filter, never a lock",
    )
    p_send.add_argument(
        "--broadcast",
        action="store_true",
        help="deliberately all-agents hub mail (bypasses the addressing guard when no "
        "--to-agent is given; an unaddressed broadcast refuses ack:required — an "
        "obligation nobody owns cannot be acked; with --to-agent it is a no-op, "
        "as it is off-hub)",
    )

    p_list = sub.add_parser("list", help="list a repo's inbox")
    p_list.add_argument("--repo")
    p_list.add_argument(
        "--agent",
        help="show only mail addressed to this ROLE plus every unaddressed message",
    )

    p_sweep = sub.add_parser(
        "sweep", help="archive stale ack:no mail (obligations are never swept)"
    )
    p_sweep.add_argument("--days", type=int, default=14)
    p_sweep.add_argument("--repo", help="one mailbox; default every mailbox")

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

    p_route = sub.add_parser(
        "route", help="set/clear the intra-mailbox addressee on a message already in the inbox"
    )
    p_route.add_argument("id")
    p_route.add_argument(
        "--to-agent",
        dest="to_agent",
        default="",
        help="role (infra/fleet/intel); omit or pass '' to CLEAR the addressee",
    )
    p_route.add_argument("--repo")

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
                args.to,
                args.kind,
                body,
                frm=args.frm,
                ack=args.ack,
                re=args.re,
                auto=args.auto,
                to_agent=args.to_agent,
                broadcast=args.broadcast,
            )
            if args.broadcast and not args.to_agent and args.to == "fabrik":
                # stderr, deliberately: stdout is the path-only contract callers parse.
                # Gated on the hub — off-hub the flag is a documented no-op.
                print("mail.py: broadcast — delivered unaddressed to all agents", file=sys.stderr)
            print(path)
        elif args.cmd == "list":
            # CLAUDE_AGENT is the role the operator set for this window; an unset
            # var lists EVERYTHING, so nothing is hidden by default.
            who = args.agent or os.environ.get("CLAUDE_AGENT") or None
            for fm in list_msgs(args.repo or _current_repo(), agent=who):
                to_who = f" · @{fm['agent']}" if fm.get("agent") else ""
                print(
                    f"{fm['id']} · {fm.get('from', '?')} · {fm.get('kind', '?')} · "
                    f"ack={fm.get('ack', '?')}{to_who}"
                )
        elif args.cmd == "sweep":
            n = sweep(days=args.days, repo=args.repo)
            print(f"swept {n} stale ack:no message(s) to archive (obligations untouched)")
        elif args.cmd == "read":
            print(read_msg(args.id, args.repo or _current_repo()))
        elif args.cmd == "claim":
            print(claim(args.id, args.repo or _current_repo()))
        elif args.cmd == "ack":
            print(ack(args.id, args.repo or _current_repo(), disposition=args.disposition))
        elif args.cmd == "route":
            path = route(args.id, args.to_agent, repo=args.repo)
            print(f"{path} · @{args.to_agent}" if args.to_agent else f"{path} · addressee cleared")
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
    except OSError as exc:
        # P13-7: FileNotFoundError was the ONLY OSError the ladder caught, so
        # every sibling (EACCES on a rename, EXDEV, ENOSPC, IsADirectoryError
        # from a stray dir in malformed/) escaped as a raw traceback — the CLI's
        # own error convention bypassed exactly when the operator needs it.
        print(f"mail.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
