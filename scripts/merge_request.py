#!/usr/bin/env python3
# AFTER-EDIT: tests/test_merge_request_send.py, docs/reference/multi-agent-operating-model.md
"""merge_request — finishing work in a linked worktree sends ONE merge request (stdlib-only).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1-4, 8.

    merge_request.py request --review <path> [--item <W-id>] [--base <branch>]

Run INSIDE a linked worktree, on a pushed branch. In order, it refuses (exit 1, nothing sent):
  * when the caller's agent is unresolvable (``whoami_agent.resolve_agent_name``: CLAUDE_AGENT,
    else this session's binding) — a request names who asked;
  * outside a linked worktree, on a detached HEAD, or on the base branch itself;
  * when ``--review`` (the closing run record or review receipt) does not exist;
  * unless ``git ls-remote <remote> <upstream ref>`` equals local HEAD — not pushed, pushed but
    behind/ahead, or a remote that cannot be reached (the git error is printed);
  * when the repo has no ``docs/DECISIONS.md`` or the owner resolver
    (``python3 /opt/fabrik/scripts/decisions.py --merge-owner <main checkout>``, overridable with
    ``$FABRIK_DECISIONS_PY``) answers UNDECLARED (exit 3) — with the ``docs_updater.py --adopt``
    command; any OTHER resolver failure (missing, exit 1, unreadable output) is named as a resolver
    failure, never read as UNDECLARED;
  * when the caller IS the merge owner (the owner merges; it never requests).

Then it sends one ``merge-request`` (``ack: required``) to the merge owner and, when
``.fabrik/work/config.json``'s ``distributor`` is a different agent (and not the caller itself),
a copy with ``ack: no`` to the distributor — no config, or a distributor equal to the owner, is
one message. The mailbox is the MAIN checkout's directory basename (resolved from the git common
dir, never the worktree's own name). Each body is written HERE, never by the caller, as
``field: value`` lines that ``mail.py``'s ``_body_fields`` reads: ``branch head base item review
doorbell sent requester``. ``doorbell`` is that recipient's live session names from
``mail.py who <agent>`` (``none`` when there are none), and for every name stdout carries one line:

    SendMessage to=<name>: merge request <msg id> from <agent> for <branch>

— a line to copy into the native ``SendMessage`` tool (the doorbell; the mail is the durable
record). The delivered mail paths are printed first, one per line. With ``--item`` the caller's
live claim on that work item is released (``work.py release <id>``) AFTER the sends.

Exit codes: 0 sent · 1 refused (nothing sent) · 2 usage · 4 the owner's request WAS sent but a
follow-up failed — the distributor copy or the ``--item`` release; do NOT re-run ``request`` (it
would send a second request), finish the named step by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIL_PY = HERE / "mail.py"
WORK_PY = HERE / "work.py"
DEFAULT_DECISIONS_PY = "/opt/fabrik/scripts/decisions.py"
GIT_TIMEOUT_S = 30
REMOTE_TIMEOUT_S = 60
TOOL_TIMEOUT_S = 60
EXIT_REFUSED = 1
EXIT_PARTIAL = 4
ITEM_RE = re.compile(r"^W-[0-9a-f]{8}$")


class RefusedError(Exception):
    """A refusal: printed on stderr, exit 1, nothing sent."""


def _run(
    argv: list[str],
    timeout: int,
    cwd: Path | None = None,
    env: dict | None = None,
    stdin_text: str | None = None,
):
    """One child process: bounded by ``timeout``, stdin closed unless ``stdin_text`` is given."""
    io: dict = {"input": stdin_text} if stdin_text is not None else {"stdin": subprocess.DEVNULL}
    try:
        return subprocess.run(  # noqa: S603 — fixed argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=False,
            **io,
        )
    except subprocess.TimeoutExpired as exc:
        raise RefusedError(f"{' '.join(argv[:3])} timed out after {timeout}s") from exc
    except OSError as exc:
        raise RefusedError(f"cannot run {argv[0]}: {exc}") from exc


def _git(*args: str, cwd: Path | None = None, timeout: int = GIT_TIMEOUT_S) -> str:
    res = _run(["git", *args], timeout, cwd=cwd)
    if res.returncode != 0:
        raise RefusedError(f"git {' '.join(args)} failed: {res.stderr.strip() or res.returncode}")
    return res.stdout.strip()


def _caller_agent() -> str:
    """``whoami_agent.resolve_agent_name()`` via the guarded sibling import mail.py uses; ""."""
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        import whoami_agent  # noqa: PLC0415

        name = whoami_agent.resolve_agent_name()
        return name if isinstance(name, str) else ""
    except (Exception, SystemExit):
        return ""


def _main_checkout(cwd: Path) -> Path:
    """The MAIN checkout: the parent of the absolute git common dir (a linked worktree's own
    toplevel lies about the repo's name)."""
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd))
    return common.resolve().parent


def _is_linked_worktree(cwd: Path) -> bool:
    git_dir = _git("rev-parse", "--path-format=absolute", "--git-dir", cwd=cwd)
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    return Path(git_dir).resolve() != Path(common).resolve()


def _work_config(toplevel: Path) -> dict:
    path = toplevel / ".fabrik" / "work" / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise RefusedError(f"cannot read {path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _check_pushed(cwd: Path, branch: str, head: str) -> None:
    """Refuse unless the branch's remote tip equals local HEAD (V1)."""
    remote = _run(["git", "config", f"branch.{branch}.remote"], GIT_TIMEOUT_S, cwd=cwd)
    remote_name = remote.stdout.strip() or "origin"
    merge = _run(["git", "config", f"branch.{branch}.merge"], GIT_TIMEOUT_S, cwd=cwd)
    ref = merge.stdout.strip() or f"refs/heads/{branch}"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    res = _run(["git", "ls-remote", remote_name, ref], REMOTE_TIMEOUT_S, cwd=cwd, env=env)
    if res.returncode != 0:
        raise RefusedError(
            f"remote {remote_name!r} cannot be reached: {res.stderr.strip() or res.returncode}"
        )
    tip = ""
    for line in res.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name.strip() == ref:
            tip = sha.strip()
    if not tip:
        raise RefusedError(
            f"branch {branch!r} is not pushed ({remote_name} has no {ref}) — "
            f"git push -u {remote_name} {branch}, then request"
        )
    if tip != head:
        raise RefusedError(
            f"{remote_name}/{branch} is at {tip[:12]}, local HEAD is {head[:12]} — push the "
            "branch so the remote tip IS the head you ask to merge"
        )


def _adopt_hint(main: Path) -> str:
    return (
        f"repo {main.name} declares no merge owner — adopt first: "
        "python scripts/docs_updater.py --adopt <owner>[,<agent>…] (spec § The delta 8)"
    )


def _merge_owner(main: Path) -> str:
    """The declared merge owner; UNDECLARED and resolver failures refuse DIFFERENTLY."""
    if not (main / "docs" / "DECISIONS.md").is_file():
        raise RefusedError(_adopt_hint(main) + " — no docs/DECISIONS.md")
    resolver = os.environ.get("FABRIK_DECISIONS_PY") or DEFAULT_DECISIONS_PY
    if not Path(resolver).is_file():
        raise RefusedError(f"owner resolver {resolver} is missing — cannot resolve the owner")
    res = _run([sys.executable, resolver, "--merge-owner", str(main)], TOOL_TIMEOUT_S)
    out = res.stdout.strip()
    if res.returncode == 3:
        raise RefusedError(_adopt_hint(main))
    if res.returncode != 0 or not out or len(out.split()) != 1:
        detail = res.stderr.strip() or out or "no output"
        raise RefusedError(
            f"owner resolver {resolver} --merge-owner failed (exit {res.returncode}): {detail}"
        )
    return out


def _who(agent: str, cwd: Path) -> list[str]:
    res = _run([sys.executable, str(MAIL_PY), "who", agent], TOOL_TIMEOUT_S, cwd=cwd)
    if res.returncode != 0:
        print(
            f"merge_request: mail.py who {agent} failed ({res.stderr.strip() or res.returncode})"
            " — doorbell: none",
            file=sys.stderr,
        )
        return []
    return [n.strip() for n in res.stdout.splitlines() if n.strip()]


def _body(fields: dict[str, str], recipient: str, role: str) -> str:
    lines = [f"{k}: {v}" for k, v in fields.items()]
    lines += [
        "",
        f"WHAT — merge request for branch {fields['branch']} at {fields['head']} into "
        f"{fields['base']}, from {fields['requester']}.",
        (
            f"WHY — {recipient} is this repo's merge owner: run "
            "`python3 scripts/merge_request.py merge` (ack: required)."
            if role == "owner"
            else f"WHY — {recipient} is the work distributor: a copy (ack: no) to keep the "
            "item current when the owner replies."
        ),
    ]
    return "\n".join(lines) + "\n"


def _send(repo: str, agent: str, body: str, ack_no: bool, cwd: Path) -> Path:
    """``mail.py send`` with the body on STDIN; returns the delivered path (stdout's contract)."""
    argv = [sys.executable, str(MAIL_PY), "send", "--to", repo, "--to-agent", agent]
    argv += ["--kind", "merge-request"] + (["--ack", "no"] if ack_no else [])
    res = _run(argv, TOOL_TIMEOUT_S, cwd=cwd, stdin_text=body)
    path = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
    if res.returncode != 0 or not path.endswith(".md"):
        raise RefusedError(
            f"mail.py send to {agent} failed (exit {res.returncode}): "
            f"{(res.stderr.strip() or res.stdout.strip() or 'no output')}"
        )
    return Path(path)


def _review_value(raw: str, cwd: Path, toplevel: Path) -> str:
    if len(raw.splitlines()) != 1:
        raise RefusedError("--review is one path on one line (it becomes a body field)")
    path = (cwd / raw).resolve()
    if not path.exists():
        raise RefusedError(f"--review {raw} does not exist (the closing run record or receipt)")
    try:
        return str(path.relative_to(toplevel.resolve()))
    except ValueError:
        return str(path)


def request(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    if args.item is not None and not ITEM_RE.fullmatch(args.item):
        raise RefusedError(f"--item {args.item!r} is not a work item id (W- and 8 lowercase hex)")
    caller = _caller_agent()
    if not caller:
        raise RefusedError("caller agent unresolved — set CLAUDE_AGENT or bind this session")
    if not _is_linked_worktree(cwd):
        raise RefusedError("run `request` inside a LINKED worktree, not the main checkout")
    toplevel = Path(_git("rev-parse", "--show-toplevel", cwd=cwd))
    main = _main_checkout(cwd)
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch == "HEAD":
        raise RefusedError("detached HEAD — a request names a branch")
    head = _git("rev-parse", "HEAD", cwd=cwd)
    config = _work_config(toplevel)
    base = (
        args.base
        or str(config.get("base_branch") or "").strip()
        or _git("symbolic-ref", "--short", "HEAD", cwd=main)
    )
    if branch == base:
        raise RefusedError(f"branch {branch!r} IS the base — nothing to merge")
    review = _review_value(args.review, cwd, toplevel)
    _check_pushed(cwd, branch, head)
    owner = _merge_owner(main)
    if owner == caller:
        raise RefusedError(f"{caller} is the merge owner — the owner merges, it does not request")
    distributor = str(config.get("distributor") or "").strip()
    recipients = [("owner", owner)]
    if distributor and distributor not in (owner, caller):
        recipients.append(("distributor", distributor))

    sent = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    doorbells: list[tuple[str, str, str]] = []  # (session name, recipient, msg id)
    rc = 0
    for role, agent in recipients:
        names = _who(agent, cwd)
        fields = {
            "branch": branch,
            "head": head,
            "base": base,
            "item": args.item or "none",
            "review": review,
            "doorbell": ", ".join(names) or "none",
            "sent": sent,
            "requester": caller,
        }
        try:
            path = _send(main.name, agent, _body(fields, agent, role), role != "owner", cwd)
        except RefusedError as exc:
            if role == "owner":
                raise  # nothing sent yet: a plain refusal
            print(
                f"merge_request: the owner's request WAS delivered; the distributor copy to "
                f"{agent} failed ({exc}) — send it by hand; do NOT re-run request",
                file=sys.stderr,
            )
            rc = EXIT_PARTIAL
            continue
        print(path)
        doorbells += [(n, agent, path.stem) for n in names]
    for name, _agent, msg_id in doorbells:
        print(f"SendMessage to={name}: merge request {msg_id} from {caller} for {branch}")
    if args.item:
        res = _run([sys.executable, str(WORK_PY), "release", args.item], TOOL_TIMEOUT_S, cwd=cwd)
        if res.returncode != 0:
            print(
                f"merge_request: request SENT, but `work.py release {args.item}` failed "
                f"({res.stderr.strip() or res.stdout.strip() or res.returncode}) — release it "
                "by hand; do NOT re-run request",
                file=sys.stderr,
            )
            return EXIT_PARTIAL
        print(res.stdout.strip())
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="merge_request.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("request", help="send the merge request for this worktree's branch")
    p.add_argument("--review", required=True, help="the closing run record or review receipt")
    p.add_argument("--item", help="the work item (W-xxxxxxxx) this branch finishes")
    p.add_argument("--base", help="the branch to merge into (default: config base_branch)")
    args = ap.parse_args(argv)
    try:
        return request(args)
    except RefusedError as exc:
        print(f"merge_request: REFUSED — {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
