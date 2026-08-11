#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mail.py, docs/reference/fabrik-mail.md
"""fabrik-mail — durable hub↔project AI message store + protocol (stdlib-only).

One neutral-path file mailbox per repo at ``$FABRIK_MAIL_ROOT/<repo>/{inbox,archive}``
(default root ``/opt/fabrik-mail``). A message is one ``.md`` file: YAML-ish frontmatter
(``id from to ts re kind ack``) + a markdown body. Subcommands:

    send  --to <repo> --kind <k> [--ack required|no] [--re <id>] [--from <repo>] < body
    list  [--repo <repo>]
    read  <id> [--repo <repo>]
    ack   <id> [--repo <repo>] [--disposition done|blocked|wontfix]
    requeue <id> [--repo <repo>]
    digest [--days N]

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

# High-confidence secret signatures — REFUSE the send.
_SECRET_HIGH = [
    _re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    _re.compile(r"\b\w*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\w*\s*[:=]\s*\S{16,}", _re.I),
    _re.compile(r"\bsk-[A-Za-z0-9-]{16,}"),               # sk-, sk-ant-, sk-proj- (hyphens kept)
    _re.compile(r"\bgh[posru]_[A-Za-z0-9]{20,}"),          # classic GitHub tokens
    _re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),        # fine-grained PATs
    _re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    _re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),         # AWS long-term + session
    _re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    _re.compile(r"(?i)\bauthorization:\s*bearer\s+\S{8,}"),  # Bearer header
    _re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]*:[^\s/@]+@"),  # scheme://[user]:pass@host (user optional — redis://:pw@)
]
# Low-confidence hints — WARN but still deliver (not bare "key", too noisy).
_SECRET_LOW = _re.compile(r"\b(?:password|passwd|secret|token|credential|api[_-]?key)\b", _re.I)

# Path-safety: a repo/recipient token is a single /opt directory name; a msg id is a
# 26-char Crockford ULID. Neither may contain a path separator or a `..` component —
# the guard against traversal via unvalidated `to`/`repo`/`msg_id` args (defense in
# depth under the single-operator threat model; a traversal is a loud refusal).
_SAFE_NAME = _re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_ID = _re.compile(r"^[0-9A-Z]{26}$")
# A REAL ack line (appended by ack()) — matched precisely so a body that merely
# contains the words "acked-by:" cannot fool the digest's claimed-but-crashed scan.
_ACK_LINE = _re.compile(r"(?m)^acked-by: .+ · disposition: (?:done|blocked|wontfix)\s*$")


def _safe_name(name: str, what: str) -> str:
    if name in ("", ".", "..") or not _SAFE_NAME.fullmatch(name):
        raise MailRefusedError(f"unsafe {what} {name!r}: must be a plain repo name ([A-Za-z0-9._-], no path separators / `..`)")
    return name


def _safe_id(msg_id: str) -> str:
    if not _SAFE_ID.fullmatch(msg_id):
        raise MailRefusedError(f"unsafe message id {msg_id!r}: must be a 26-char Crockford ULID")
    return msg_id


class MailRefusedError(Exception):
    """A loud, nothing-written refusal (invalid recipient, star violation, secret, oversize)."""


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
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        for line in out.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree "):].strip()).name
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
    rand = int.from_bytes(os.urandom(10), "big")          # 80 random bits
    return _crockford((ms << 80) | rand, _ULID_LEN)


# --- validation --------------------------------------------------------------
def _is_hub(name: str) -> bool:
    return name in HUB_NODES


def _valid_recipient(to: str) -> bool:
    """Machinery-presence: fabrik/fabrik-lib (hardcoded), OR the surfacing hook is on disk."""
    if _is_hub(to):
        return True
    return (_opt_root() / to / ".claude" / "hooks" / "mail_notify.py").is_file()


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


def _frontmatter(mid: str, frm: str, to: str, ts: str, re_: str, kind: str, ack: str, body: str) -> str:
    return (
        "---\n"
        f"id: {mid}\n"
        f"from: {frm}\n"
        f"to: {to}\n"
        f"ts: {ts}\n"
        f"re: {re_ or ''}\n"
        f"kind: {kind}\n"
        f"ack: {ack}\n"
        "---\n"
        f"{body}"
        + ("" if body.endswith("\n") else "\n")
    )


def send(to: str, kind: str, body: str, frm: str | None = None,
         ack: str | None = None, re: str | None = None) -> Path:
    """Publish a message to <to>'s inbox. Raises MailRefusedError on any refusal (nothing written)."""
    frm = frm or _current_repo()
    _safe_name(to, "recipient")
    _safe_name(frm, "sender")
    if kind not in KINDS:
        raise MailRefusedError(f"unknown kind {kind!r} (allowed: {', '.join(sorted(KINDS))})")
    if len(body.encode("utf-8")) > MAX_BODY:
        raise MailRefusedError(f"body over the 64 KB cap ({len(body.encode('utf-8'))} B) — a mail is a pointer, not a payload")
    level = _secret_level(body)
    if level == "high":
        raise MailRefusedError("refusing send: body contains a high-confidence secret — messages never carry credentials")
    if level == "low":
        print("mail.py: WARNING — low-confidence secret-like text in body; sending anyway (use <PASTE …> pointers for real secrets)", file=sys.stderr)
    if not _valid_recipient(to):
        raise MailRefusedError(f"invalid recipient {to!r}: not fabrik/fabrik-lib and no /opt/{to}/.claude/hooks/mail_notify.py (a repo that can't surface mail)")
    if not _is_hub(frm) and not _is_hub(to):
        raise MailRefusedError(f"star-topology refusal: {frm}→{to} is project→project; route via the hub (--to fabrik)")
    ack = ack or ACK_BY_KIND[kind]
    mid = _ulid()
    content = _frontmatter(mid, frm, to, _now_iso(), re or "", kind, ack, body)
    return _publish(_mail_root() / to / "inbox", mid, content)


# --- ack / requeue -----------------------------------------------------------
def ack(msg_id: str, repo: str, disposition: str = "done") -> Path:
    """Claim + resolve: rename inbox→archive (ENOENT loser stops), then append the ack line."""
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    base = _mail_root() / repo
    src = base / "inbox" / f"{msg_id}.md"
    dst = base / "archive" / f"{msg_id}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)  # FileNotFoundError if already claimed — the race lock
    with open(dst, "a", encoding="utf-8") as fh:
        fh.write(f"\nacked-by: {repo} · ts: {_now_iso()} · disposition: {disposition}\n")
    return dst


def requeue(msg_id: str, repo: str) -> Path:
    """Move a claimed-but-unresolved message back to inbox for a live agent to re-process."""
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    base = _mail_root() / repo
    src = base / "archive" / f"{msg_id}.md"
    dst = base / "inbox" / f"{msg_id}.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)
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
    try:
        return datetime.now(UTC).timestamp() - datetime.fromisoformat(ts).timestamp()
    except (ValueError, TypeError):
        return float("inf")  # unparseable ts → surface it, never hide


# --- digest ------------------------------------------------------------------
def _quarantine(inbox: Path, f: Path) -> None:
    q = inbox.parent / "malformed"
    q.mkdir(parents=True, exist_ok=True)
    os.rename(f, q / f.name)


def digest(days: int = 3) -> dict:
    """Scan every mailbox: count unacked (ack:required, over the age threshold) + quarantined."""
    root = _mail_root()
    threshold = days * 86400
    unacked = 0
    quarantined = 0
    if not root.is_dir():
        return {"unacked": 0, "quarantined": 0, "repos": []}
    repos: list[str] = []
    for repo_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        repos.append(repo_dir.name)
        inbox = repo_dir / "inbox"
        archive = repo_dir / "archive"
        if inbox.is_dir():
            for f in sorted(inbox.glob("*.md")):
                fm = _parse(f.read_text(encoding="utf-8", errors="replace"))
                if fm is None:
                    _quarantine(inbox, f)
                    quarantined += 1
                    continue
                if fm.get("ack") == "required" and _age_seconds(fm.get("ts", "")) >= threshold:
                    unacked += 1  # required, still unclaimed in inbox
        if archive.is_dir():
            for f in sorted(archive.glob("*.md")):
                text = f.read_text(encoding="utf-8", errors="replace")
                fm = _parse(text)
                if fm is None:
                    continue
                if (fm.get("ack") == "required" and not _ACK_LINE.search(text)
                        and _age_seconds(fm.get("ts", "")) >= threshold):
                    unacked += 1  # claimed-but-crashed (no REAL acked-by line — body prose can't fake it)
    return {"unacked": unacked, "quarantined": quarantined, "repos": repos}


def list_msgs(repo: str) -> list[dict]:
    """List a repo's inbox (quarantining any malformed file), newest sort last."""
    inbox = _mail_root() / repo / "inbox"
    out: list[dict] = []
    if not inbox.is_dir():
        return out
    for f in sorted(inbox.glob("*.md")):
        fm = _parse(f.read_text(encoding="utf-8", errors="replace"))
        if fm is None:
            _quarantine(inbox, f)
            continue
        out.append(fm)
    return out


def read_msg(msg_id: str, repo: str) -> str:
    _safe_id(msg_id)
    _safe_name(repo, "repo")
    for sub in ("inbox", "archive"):
        p = _mail_root() / repo / sub / f"{msg_id}.md"
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError(f"no message {msg_id} in {repo}")


# --- CLI ---------------------------------------------------------------------
def _is_hub_repo() -> bool:
    # content-based hub identity (same discipline as session_orient.py)
    return (Path.cwd() / "scripts" / "fabrik_synced_manifest.py").is_file()


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
            from libs.alerting import send_alert  # lazy: hub-only, vendored there
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

    p_list = sub.add_parser("list", help="list a repo's inbox")
    p_list.add_argument("--repo")

    p_read = sub.add_parser("read", help="print a message")
    p_read.add_argument("id")
    p_read.add_argument("--repo")

    p_ack = sub.add_parser("ack", help="claim + resolve a message")
    p_ack.add_argument("id")
    p_ack.add_argument("--repo")
    p_ack.add_argument("--disposition", default="done", choices=["done", "blocked", "wontfix"])

    p_req = sub.add_parser("requeue", help="move a claimed message back to inbox")
    p_req.add_argument("id")
    p_req.add_argument("--repo")

    p_dig = sub.add_parser("digest", help="report unacked + quarantined traffic")
    p_dig.add_argument("--days", type=int, default=3)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "send":
            body = sys.stdin.read()
            path = send(args.to, args.kind, body, frm=args.frm, ack=args.ack, re=args.re)
            print(path)
        elif args.cmd == "list":
            for fm in list_msgs(args.repo or _current_repo()):
                print(f"{fm['id']} · {fm.get('from','?')} · {fm.get('kind','?')} · ack={fm.get('ack','?')}")
        elif args.cmd == "read":
            print(read_msg(args.id, args.repo or _current_repo()))
        elif args.cmd == "ack":
            print(ack(args.id, args.repo or _current_repo(), disposition=args.disposition))
        elif args.cmd == "requeue":
            print(requeue(args.id, args.repo or _current_repo()))
        elif args.cmd == "digest":
            _deliver_digest(digest(days=args.days))
    except MailRefusedError as exc:
        print(f"mail.py: REFUSED — {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"mail.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
