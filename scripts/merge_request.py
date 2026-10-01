#!/usr/bin/env python3
# AFTER-EDIT: tests/test_merge_request_send.py, docs/reference/multi-agent-operating-model.md
"""merge_request — finishing work in a linked worktree sends ONE merge request (stdlib-only).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1-4, 8.

    merge_request.py request --review <path> [--item <W-id>] [--base <branch>]

Run INSIDE a linked worktree, on a pushed branch. Every check below runs BEFORE anything is sent,
and each failure refuses with exit 1:
  * ``--item`` is not a work item id (``W-`` and 8 lowercase hex);
  * the caller's agent is unresolvable (``whoami_agent.resolve_agent_name``: CLAUDE_AGENT, else this
    session's binding) — a request names who asked;
  * outside a linked worktree, or on a detached HEAD;
  * ``--review`` (the closing run record or review receipt) is not a regular file inside the
    worktree or the main checkout (stored repo-relative in the body);
  * the branch is not pushed AS ITSELF: ``refs/heads/<branch>`` on the remote
    (``branch.<b>.remote``, else ``origin``; a local ``.`` upstream is refused) must equal HEAD.
    ``branch.<b>.merge`` is ignored — a branch cut from origin/master tracks master. An unreachable
    remote refuses with the git error;
  * the base — ``--base``, else config ``base_branch``, else the remote's HEAD (``ls-remote
    --symref``), else refuse with "pass --base" — is not one line, fails ``git check-ref-format
    --branch``, is absent from the remote, or IS the branch;
  * the repo has no ``docs/DECISIONS.md`` or the owner resolver
    (``python3 /opt/fabrik/scripts/decisions.py --merge-owner <main checkout>``, overridable with
    ``$FABRIK_DECISIONS_PY``) answers UNDECLARED (exit 3) — with the ``docs_updater.py --adopt``
    command; any OTHER resolver failure (missing, exit 1, unreadable output) is named as a resolver
    failure, never read as UNDECLARED;
  * the caller IS the merge owner (agent names compare casefolded and stripped).

Then it sends one ``merge-request`` (``ack: required``) to the merge owner and, when
``.fabrik/work/config.json``'s ``distributor`` is a different agent (and not the caller), a copy
with ``ack: no`` to the distributor — no config, or a distributor equal to the owner, is one
message. The mailbox is the MAIN checkout's directory basename, derived exactly as ``mail.py``'s
``_main_checkout`` does (the first ``git worktree list --porcelain`` entry). Each body is written
HERE, never by the caller, as ``field: value`` lines that ``mail.py``'s ``_body_fields`` reads:
``branch head base item review doorbell sent requester``; a value with a line break is refused.
``doorbell`` is that recipient's live session names from ``mail.py who <agent>`` (``none`` when
there are none), and for every name stdout carries one line:

    SendMessage to=<name>: merge request <msg id> from <agent> for <branch>

— a line to copy into the native ``SendMessage`` tool (the doorbell; the mail is the durable
record). Each delivered mail path is printed before its doorbell lines. With ``--item`` the
caller's live claim on that work item is released (``work.py release <id>``) AFTER the sends.

Exit codes: 0 sent · 1 refused (nothing sent) · 2 usage · 4 PARTIAL — the owner's request MAY
already be written (its send timed out or answered oddly) or WAS sent and a later step failed (the
distributor's ``who`` or copy, the ``--item`` release). On 4: do NOT re-run ``request`` (a second
request would follow); check the inbox and finish the named step by hand.
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
HEADS = "refs/heads/"


class RefusedError(Exception):
    """A refusal: printed on stderr, exit 1, nothing sent."""


class TimedOutError(RefusedError):
    """A child process ran past its timeout. Before the owner send it is a plain refusal; from
    the owner send on, the child MAY have acted, so the caller reads it as PARTIAL."""


class PartialError(Exception):
    """The owner's request may already be written: exit 4, never re-run."""


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
        raise TimedOutError(f"{' '.join(argv[:3])} timed out after {timeout}s") from exc
    except OSError as exc:
        raise RefusedError(f"cannot run {argv[0]}: {exc}") from exc


def _git(*args: str, cwd: Path | None = None, timeout: int = GIT_TIMEOUT_S) -> str:
    res = _run(["git", *args], timeout, cwd=cwd)
    if res.returncode != 0:
        raise RefusedError(f"git {' '.join(args)} failed: {res.stderr.strip() or res.returncode}")
    return res.stdout.strip()


def _norm(agent: str) -> str:
    return agent.strip().casefold()


def _one_line(value: str) -> bool:
    return value.splitlines() == [value]


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
    """The MAIN checkout — the first ``worktree`` entry of ``git worktree list --porcelain``,
    the derivation ``mail.py``'s ``_main_checkout`` uses (pinned equal by a test). Where mail.py
    falls back to the cwd on a git failure, this refuses: a guessed mailbox is a lost request."""
    out = _git("worktree", "list", "--porcelain", cwd=cwd)
    for line in out.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree ") :].strip())
    raise RefusedError("git worktree list named no main checkout")


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


def _remote_name(cwd: Path, branch: str) -> str:
    res = _run(["git", "config", f"branch.{branch}.remote"], GIT_TIMEOUT_S, cwd=cwd)
    remote = res.stdout.strip() or "origin"
    if remote == ".":
        raise RefusedError(
            f"branch {branch!r} has a local upstream (remote '.') — that is not pushed; "
            f"git push -u origin {branch}, then request"
        )
    return remote


def _remote_refs(cwd: Path, remote: str) -> tuple[dict[str, str], str]:
    """(``{ref: sha}``, the remote HEAD's branch or "") from ONE ``git ls-remote --symref``."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    res = _run(["git", "ls-remote", "--symref", remote], REMOTE_TIMEOUT_S, cwd=cwd, env=env)
    if res.returncode != 0:
        raise RefusedError(
            f"remote {remote!r} cannot be reached: {res.stderr.strip() or res.returncode}"
        )
    refs: dict[str, str] = {}
    head = ""
    for line in res.stdout.splitlines():
        left, _, name = line.partition("\t")
        if left.startswith("ref: ") and name.strip() == "HEAD":
            target = left[len("ref: ") :].strip()
            head = target[len(HEADS) :] if target.startswith(HEADS) else ""
        elif name:
            refs[name.strip()] = left.strip()
    if head and HEADS + head not in refs:
        head = ""  # a dangling remote HEAD names no branch
    return refs, head


def _check_pushed(remote: str, refs: dict[str, str], branch: str, head: str) -> None:
    """Refuse unless ``refs/heads/<branch>`` on the remote IS local HEAD (V1)."""
    ref = HEADS + branch
    tip = refs.get(ref, "")
    if not tip:
        raise RefusedError(
            f"branch {branch!r} is not pushed ({remote} has no {ref}) — "
            f"git push -u {remote} {branch}, then request"
        )
    if tip != head:
        raise RefusedError(
            f"{remote} {ref} is at {tip[:12]}, local HEAD is {head[:12]} — push the branch so "
            "the remote tip IS the head you ask to merge"
        )


def _resolve_base(
    cwd: Path, args_base: str | None, config: dict, remote: str, refs: dict, remote_head: str
) -> str:
    raw = config.get("base_branch")
    base = args_base or (raw.strip() if isinstance(raw, str) else "") or remote_head
    if not base:
        raise RefusedError(f"no base: no config base_branch and {remote} has no HEAD — pass --base")
    if not _one_line(base) or base.startswith("-"):
        raise RefusedError(f"base {base!r} is not a branch name")
    res = _run(["git", "check-ref-format", "--branch", base], GIT_TIMEOUT_S, cwd=cwd)
    if res.returncode != 0 or res.stdout.strip() != base:
        raise RefusedError(f"base {base!r} is not a branch name (git check-ref-format --branch)")
    if HEADS + base not in refs:
        raise RefusedError(f"base {base!r} does not exist on {remote} ({HEADS}{base})")
    return base


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
    """The script-written body; a value with a line break would forge a later field."""
    for key, value in fields.items():
        if value and not _one_line(value):
            raise RefusedError(f"body field {key!r} carries a line break — refused")
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
    """``mail.py send`` with the body on STDIN; returns the delivered path (stdout's contract).
    A non-zero exit is mail.py's refusal (nothing written: RefusedError); a timeout or an exit 0
    without a delivered path MAY have written (TimedOutError / PartialError)."""
    argv = [sys.executable, str(MAIL_PY), "send", "--to", repo, "--to-agent", agent]
    argv += ["--kind", "merge-request"] + (["--ack", "no"] if ack_no else [])
    res = _run(argv, TOOL_TIMEOUT_S, cwd=cwd, stdin_text=body)
    if res.returncode != 0:
        raise RefusedError(
            f"mail.py send to {agent} refused (exit {res.returncode}): "
            f"{res.stderr.strip() or res.stdout.strip() or 'no output'}"
        )
    out = res.stdout.strip().splitlines()
    path = out[-1].strip() if out else ""
    if not path.endswith(".md"):
        raise PartialError(f"mail.py send to {agent} exited 0 without a delivered path: {path!r}")
    return Path(path)


def _review_value(raw: str, cwd: Path, roots: list[Path]) -> str:
    """``--review`` as a repo-relative path: a regular file inside the worktree or main checkout."""
    if not _one_line(raw):
        raise RefusedError("--review is one path on one line (it becomes a body field)")
    path = (cwd / raw).resolve()
    if not path.is_file():
        raise RefusedError(f"--review {raw} is not a regular file (the closing record or receipt)")
    for root in roots:
        try:
            return str(path.relative_to(root.resolve()))
        except ValueError:
            continue
    raise RefusedError(f"--review {raw} resolves outside the worktree and the main checkout")


def _partial(step: str, exc: BaseException, mailbox: str) -> None:
    print(
        f"merge_request: PARTIAL — {step} failed ({exc}); the owner's request may already be in "
        f"{mailbox}'s inbox — do NOT re-run request; check the inbox and finish this step by hand",
        file=sys.stderr,
    )


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
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    if main.resolve() == Path(common).resolve():
        raise RefusedError(
            f"this repo keeps a separate git dir ({common}): git names it as the main checkout, "
            f"so mail.py would address mailbox {main.name!r} — no mailbox or ledger to resolve"
        )
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch == "HEAD":
        raise RefusedError("detached HEAD — a request names a branch")
    head = _git("rev-parse", "HEAD", cwd=cwd)
    config = _work_config(toplevel)
    review = _review_value(args.review, cwd, [toplevel, main])
    remote = _remote_name(cwd, branch)
    refs, remote_head = _remote_refs(cwd, remote)
    _check_pushed(remote, refs, branch, head)
    base = _resolve_base(cwd, args.base, config, remote, refs, remote_head)
    if base == branch:
        raise RefusedError(f"branch {branch!r} IS the base — nothing to merge")
    owner = _merge_owner(main)
    if _norm(owner) == _norm(caller):
        raise RefusedError(f"{caller} is the merge owner — the owner merges, it does not request")
    raw_dist = config.get("distributor")
    distributor = raw_dist.strip() if isinstance(raw_dist, str) else ""
    copy = bool(distributor) and _norm(distributor) not in (_norm(owner), _norm(caller))

    mailbox = main.name
    sent = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fields(names: list[str]) -> dict[str, str]:
        return {
            "branch": branch,
            "head": head,
            "base": base,
            "item": args.item or "none",
            "review": review,
            "doorbell": ", ".join(names) or "none",
            "sent": sent,
            "requester": caller,
        }

    def ring(names: list[str], msg_id: str) -> None:
        for name in names:
            print(f"SendMessage to={name}: merge request {msg_id} from {caller} for {branch}")

    # Strictly BEFORE the owner send: any failure is a refusal, nothing sent.
    owner_names = _who(owner, cwd)
    owner_body = _body(fields(owner_names), owner, "owner")
    try:
        path = _send(mailbox, owner, owner_body, False, cwd)
    except TimedOutError as exc:
        _partial("the owner send", exc, mailbox)
        return EXIT_PARTIAL
    except PartialError as exc:
        _partial("the owner send", exc, mailbox)
        return EXIT_PARTIAL
    print(path)
    ring(owner_names, path.stem)

    # From here the owner's request IS written: every failure is PARTIAL, never a refusal.
    rc = 0
    if copy:
        try:
            names = _who(distributor, cwd)
            copy_path = _send(
                mailbox, distributor, _body(fields(names), distributor, "copy"), True, cwd
            )
            print(copy_path)
            ring(names, copy_path.stem)
        except Exception as exc:
            _partial(f"the distributor copy to {distributor}", exc, mailbox)
            rc = EXIT_PARTIAL
    if args.item:
        try:
            res = _run(
                [sys.executable, str(WORK_PY), "release", args.item], TOOL_TIMEOUT_S, cwd=cwd
            )
            if res.returncode != 0:
                raise RefusedError(res.stderr.strip() or res.stdout.strip() or str(res.returncode))
            print(res.stdout.strip())
        except Exception as exc:
            _partial(f"`work.py release {args.item}`", exc, mailbox)
            rc = EXIT_PARTIAL
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="merge_request.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("request", help="send the merge request for this worktree's branch")
    p.add_argument("--review", required=True, help="the closing run record or review receipt")
    p.add_argument("--item", help="the work item (W-xxxxxxxx) this branch finishes")
    p.add_argument("--base", help="the branch to merge into (default: config, else remote HEAD)")
    args = ap.parse_args(argv)
    try:
        return request(args)
    except RefusedError as exc:
        print(f"merge_request: REFUSED — {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
