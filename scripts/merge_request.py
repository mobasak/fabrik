#!/usr/bin/env python3
# AFTER-EDIT: tests/test_merge_request_send.py, tests/test_merge_request_merge.py, tests/test_merge_request_work_items.py, tests/test_governance_template_split.py, docs/reference/multi-agent-operating-model.md
"""merge_request — finishing work in a linked worktree sends ONE merge request; the merge owner
merges it through ONE data-safe path (stdlib-only).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1-5, 8 and
§ Data-safety invariants.

    merge_request.py request --review <path> [--item <W-id>] [--base <branch>]
    merge_request.py merge [<id>]        # the merge owner: the oldest request addressed to it
    merge_request.py merge --queue       # 2+ waiting: their owner tests outside the lock, then each
    merge_request.py resume <id>         # continue a request from its recorded phase
    merge_request.py retry <id>          # re-run a REFUSED request whose branch is unchanged

``merge``, ``resume`` and ``retry`` are documented at their functions below; ``request`` here.

Run INSIDE a linked worktree, on a pushed branch. Every check below runs BEFORE anything is sent,
and each failure refuses with exit 1:
  * ``--item`` is not a work item id (``W-`` and 8 lowercase hex);
  * the caller's agent is unresolvable (``whoami_agent.resolve_agent_name``: CLAUDE_AGENT, else this
    session's binding) — a request names who asked;
  * outside a linked worktree, or on a detached HEAD;
  * ``--review`` (the closing run record or review receipt — spec § The delta 1, "verified to
    exist") is not a single-line path to an existing regular file; it may live ANYWHERE (a run
    record sits outside the repo) and is stored as its absolute realpath;
  * the branch is not pushed AS ITSELF: ``refs/heads/<branch>`` on the push remote
    (``branch.<b>.pushRemote``, else ``remote.pushDefault``, else ``branch.<b>.remote``, else
    ``origin``; a local ``.`` is refused) must equal HEAD.
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
  * the caller IS the merge owner (agent names compare casefolded and stripped);
  * the branch is more than ``MAX_BEHIND`` (500) commits behind the base's REMOTE tip (W-527c1ce0,
    D-1381) — the tip is fetched once when this clone lacks it, and the refusal prints the
    ``git fetch <remote> refs/heads/<base>`` and ``git merge FETCH_HEAD`` to run (never a rebase:
    the branch is pushed; the full ref never resolves to a same-named tag, and FETCH_HEAD works
    whatever the clone's fetch refspec tracks).

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
request would follow); check the inbox and finish by hand every step stderr lists after
``not done:`` — after an owner-send partial that is confirming the message landed, the distributor
copy and the ``--item`` release, none of which ran.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

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
# A branch more than this many commits behind the REMOTE base tip is refused before anything is
# sent (W-527c1ce0, D-1381): the panel tied the line to the ledger-conflict refusals, which grow with
# the gap, and 25 of the 51 refusals in 14 days were red tests on a stale base. Cobra (D-253): the
# cheapest way past it is merging the base in once just before the request and never between items;
# the item-boundary merge line in CLAUDE.md § EXIT is the counter, and the refusal still fires on any
# branch that drifts past the line again.
MAX_BEHIND = 500


def _resend(base: str, branch: str = "your branch") -> str:
    """The REQUESTER's remedy for a refused merge (W-9c2f371a, fabrik-lib 01M3TVN8): `request`
    requires the branch pushed, so a rebase could be republished only with --force, a universal
    HARD STOP. Merging the base in pushes fast-forward and keeps every SHA a receipt cites."""
    return (
        f"merge {base} into {branch} (`git merge {base}`), resolve, push, then run "
        "`merge_request.py request` again — never a rebase: the branch is already pushed"
    )


class RefusedError(Exception):
    """A refusal: printed on stderr, exit 1, nothing sent."""


class TimedOutError(RefusedError):
    """A child process ran past its timeout. Before the owner send it is a plain refusal; from
    the owner send on, the child MAY have acted, so the caller reads it as PARTIAL."""


class UnreachableError(RefusedError):
    """The remote could not be reached: a fetch timed out, or failed for any reason but a missing
    ref. In step (a) the request DEFERS (claimed, nothing replied; the next run retries it); after
    the CAS it is PARTIAL — never a refusal, never a parked record (W-d0bbb94d)."""


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
            pass_fds=tuple(
                _LEASE_FDS
            ),  # a leg's lease lives as long as its tests, not just this process
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


def _capped_run() -> str:
    """The box's capped runner: FABRIK_CAPPED_RUN, else this tree's own, else the hub's absolute
    path — a project's synced copy of this script has no runner beside it (the runner is hub-only)."""
    sibling = Path(__file__).resolve().parent / "capped_run.sh"
    return os.getenv("FABRIK_CAPPED_RUN") or (
        str(sibling) if sibling.is_file() else "/opt/fabrik/scripts/capped_run.sh"
    )


def _capped(argv: list[str], timeout: int, mem: str | None = None) -> list[str]:
    """``argv`` under the box's capped runner — a cgroup memory ceiling and a time limit, so a
    runaway owner test is a red, never a host outage (W-162398ef). ``mem`` (the base's declared
    ceiling, ``_declared_mem``) is passed as ``--mem``; without it the runner's own default holds.
    No runner → ``argv`` as is."""
    runner = _capped_run()
    if os.access(runner, os.X_OK):
        flags = ["--timeout", str(int(timeout)), *(["--mem", mem] if mem else [])]
        return [runner, *flags, "--", *argv]
    print(
        f"merge_request: WARNING — {runner} is missing; owner tests run UNCAPPED (no memory ceiling)",
        file=sys.stderr,
    )
    return list(argv)


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
    """``whoami_agent.resolve_agent_name()`` via a guarded sibling import; without the module, a
    ``CLAUDE_AGENT`` in the agent-name grammar; else ""."""
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        import whoami_agent  # noqa: PLC0415

        name = whoami_agent.resolve_agent_name()
        return name if isinstance(name, str) else ""
    except ImportError:
        # A repo that does not vendor whoami_agent.py names the caller with CLAUDE_AGENT alone,
        # as the merge-request contract tells it (01M3TTTCTW); only a valid agent name counts.
        env = os.environ.get("CLAUDE_AGENT", "").strip()
        return env if _AGENT_NAME_RE.fullmatch(env) else ""
    except (Exception, SystemExit):
        return ""


_AGENT_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")


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
    """The remote ``git push`` would push this branch to: ``branch.<b>.pushRemote``, else
    ``remote.pushDefault``, else ``branch.<b>.remote``, else ``origin`` — a triangular setup
    (fetch from upstream, push to a fork) is checked where the branch actually went."""
    remote = ""
    for key in (f"branch.{branch}.pushRemote", "remote.pushDefault", f"branch.{branch}.remote"):
        remote = _run(["git", "config", key], GIT_TIMEOUT_S, cwd=cwd).stdout.strip()
        if remote:
            break
    if remote == ".":
        # Name the key that produced `.`: a `push -u` remedy rewrites branch.<b>.remote only, so
        # a `.` in pushRemote or pushDefault would refuse the next run identically.
        kind = "local upstream" if key == f"branch.{branch}.remote" else "local push remote"
        raise RefusedError(
            f"branch {branch!r} has a {kind} — {key} is '.', which is not pushed; fix that key "
            f"(git config --unset {key}, or git config {key} <the real push remote>), push "
            f"{branch} there, then request"
        )
    return remote or "origin"


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


def _check_behind(cwd: Path, remote: str, base: str, tip: str) -> None:
    """Refuse a branch more than MAX_BEHIND commits behind ``tip``, the base's REMOTE sha — what the
    owner merges onto, never a stale local ``<remote>/<base>``. A tip this clone has not fetched is
    fetched once; a fetch failure or a still-missing object refuses (fail closed: a refusal costs a
    re-run, a stale branch let through costs the owner a build and a test leg)."""
    present = _run(["git", "cat-file", "-e", f"{tip}^{{commit}}"], GIT_TIMEOUT_S, cwd=cwd)
    if present.returncode != 0:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            res = _run(
                ["git", "fetch", "-q", "--no-tags", remote, HEADS + base],
                REMOTE_TIMEOUT_S,
                cwd=cwd,
                env=env,
            )
        except TimedOutError as exc:
            raise RefusedError(
                f"{exc} — run `git fetch {remote} refs/heads/{base}` yourself, then request again"
            ) from None
        if res.returncode != 0:
            raise RefusedError(
                f"cannot fetch {remote} {base} to count how far behind it this branch is: "
                f"{res.stderr.strip() or res.returncode}"
            )
    res = _run(["git", "rev-list", "--count", f"HEAD..{tip}"], GIT_TIMEOUT_S, cwd=cwd)
    if res.returncode != 0 or not res.stdout.strip().isdigit():
        raise RefusedError(
            f"cannot count how far behind {remote}/{base} this branch is: "
            f"{res.stderr.strip() or res.returncode}"
        )
    behind = int(res.stdout.strip())
    if behind > MAX_BEHIND:
        raise RefusedError(
            f"this branch is {behind} commits behind {remote}/{base} (the limit is {MAX_BEHIND}) "
            f"— run `git fetch {remote} refs/heads/{base}`, then `git merge FETCH_HEAD`, resolve, push, "
            "then run `merge_request.py request` again — never a rebase: the branch is already "
            "pushed. Merge the base at every item boundary and this never fires"
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


def _review_value(raw: str, cwd: Path) -> str:
    """``--review`` as an ABSOLUTE realpath: an existing regular file ANYWHERE (spec § The delta
    1 — a command run record lives outside the repo). The loop is same-machine and the owner
    reads it before the worktree is removed, so the absolute path stays valid for its reader."""
    if not _one_line(raw):
        raise RefusedError("--review is one path on one line (it becomes a body field)")
    path = (cwd / raw).resolve()
    if not path.is_file():
        raise RefusedError(f"--review {raw} is not an existing regular file (run record/receipt)")
    if not _one_line(str(path)):
        raise RefusedError(f"--review {raw} resolves to a path with a line break")
    return str(path)


def _partial(step: str, exc: BaseException, mailbox: str, undone: list[str]) -> None:
    """Exit-4 stderr: what failed, and EVERY step left undone, so the operator finishes by hand."""
    print(
        f"merge_request: PARTIAL — {step} failed ({exc}); the owner's request may already be in "
        f"{mailbox}'s inbox — do NOT re-run request; check the inbox. not done: "
        + "; ".join(undone),
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
    review = _review_value(args.review, cwd)
    remote = _remote_name(cwd, branch)
    refs, remote_head = _remote_refs(cwd, remote)
    _check_pushed(remote, refs, branch, head)
    base = _resolve_base(cwd, args.base, config, remote, refs, remote_head)
    if base == branch:
        raise RefusedError(f"branch {branch!r} IS the base — nothing to merge")
    owner = _merge_owner(main)
    if _norm(owner) == _norm(caller):
        raise RefusedError(f"{caller} is the merge owner — the owner merges, it does not request")
    # after the owner checks, so an undeclared repo gets its adopt hint before any fetch
    _check_behind(cwd, remote, base, refs[HEADS + base])
    raw_dist = config.get("distributor")
    distributor = raw_dist.strip() if isinstance(raw_dist, str) else ""
    copy = bool(distributor) and _norm(distributor) not in (_norm(owner), _norm(caller))

    if getattr(args, "pretest", False):  # after every check, strictly before any send
        print(_pretest(main, Path(common), owner, base, branch, head), file=sys.stderr)
    mailbox = main.name
    sent = _now()

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
    copy_step = f"send the distributor copy ({distributor})"
    release_step = f"release {args.item}"
    try:
        path = _send(mailbox, owner, owner_body, False, cwd)
    except (TimedOutError, PartialError) as exc:
        # The message id is unknown, so nothing after it runs: every later step is left listed.
        undone = ["confirm the owner message landed (check the inbox)"]
        undone += [copy_step] if copy else []
        undone += [release_step] if args.item else []
        _partial("the owner send", exc, mailbox, undone)
        return EXIT_PARTIAL
    print(path)
    ring(owner_names, path.stem)

    # From here the owner's request IS written: every failure is PARTIAL, never a refusal.
    rc = 0
    if copy:
        sending = False
        try:
            names = _who(distributor, cwd)
            copy_body = _body(fields(names), distributor, "copy")
            sending = True
            copy_path = _send(mailbox, distributor, copy_body, True, cwd)
            print(copy_path)
            ring(names, copy_path.stem)
        except Exception as exc:
            # Mirrors the owner-send rule: a timeout or an exit 0 without a path MAY have written
            # the copy, so the remedy is to confirm it — a re-send would duplicate it. Only a
            # failure before the send, or mail.py's clean refusal (nothing written), re-sends.
            maybe_written = sending and isinstance(exc, (TimedOutError, PartialError))
            step = (
                f"confirm the distributor copy to {distributor} landed (check the inbox)"
                if maybe_written
                else copy_step
            )
            _partial(f"the distributor copy to {distributor}", exc, mailbox, [step])
            rc = EXIT_PARTIAL  # the release below still runs and reports itself
    if args.item:
        try:
            res = _run(
                [sys.executable, str(WORK_PY), "release", args.item], TOOL_TIMEOUT_S, cwd=cwd
            )
            if res.returncode != 0:
                raise RefusedError(res.stderr.strip() or res.stdout.strip() or str(res.returncode))
            print(res.stdout.strip())
        except Exception as exc:
            _partial(f"`work.py release {args.item}`", exc, mailbox, [release_step])
            rc = EXIT_PARTIAL
    return rc


# --- merge / resume: the owner's ONE merge path (spec § The delta 5) ----------------------------
LEDGERS = frozenset(
    {
        "CHANGELOG.md",
        "docs/DECISIONS.md",
        "INDEX.md",
        "docs/STRATEGIC_BACKLOG.md",
        "docs/LESSONS_LEARNT.md",
    }
)
DECISIONS = "docs/DECISIONS.md"
MAX_REBUILDS = 3  # (d): the build is redone in full at most this many times, then it refuses
TEST_TIMEOUT_S = 1800
# One owner-test budget per INVOCATION (W-347cd0c3): every rebuild after a failed CAS (up to
# MAX_REBUILDS + 1 builds) and the catch-up re-run the whole leg, so a per-leg limit alone bounds no
# merge. Two full legs: a build and one rebuild. The documented wrapper (capped_run --timeout 6300)
# covers it plus LEG_ADMIT_WAIT_S, PUSH_TIMEOUT_S, SYNC_TIMEOUT_S and 300 s for the builds, preflights,
# carry and reply.
MERGE_TEST_BUDGET_S = 2 * TEST_TIMEOUT_S
LEG_FLOOR_S = 60  # under a minute left, no leg starts: a stub run tells nothing and holds the lock
# A repo whose one leg outgrows TEST_TIMEOUT_S declares its own in the BASE's .fabrik/merge-tests (a
# branch cannot raise it): `# merge-test-timeout: <seconds>` on a line of its own, the first such line
# read, clamped to [LEG_FLOOR_S, MERGE_TEST_BUDGET_S] — so the budget, and the documented wrapper,
# still bound the run; a longer leg leaves less of the budget for a rebuild (W-1fb11ec8, wef's ~5240-test
# leg past 1800 s on 2026-10-24).
_LEG_DECL_RE = re.compile(r"(?m)^#[ \t]*merge-test-timeout:[ \t]*([0-9]+)[ \t\r]*$")
# The same for the leg's MEMORY ceiling (W-e64a7b8e): a leg runs in ONE capped_run scope, and the hub's
# runs 8 pytest shards in it — a 244-file selection measured 6,009 MiB, past capped_run's 4G default, and
# died at exit 137. `# merge-test-mem: <n>M|<n>G` on a line of its own, read from the BASE only, the
# first such line read, clamped to [LEG_MEM_FLOOR_MIB, LEG_MEM_MAX_MIB]. The MAX is capped_run.sh's
# slice total (FABRIK_TEST_SLICE_MAX, 12G) minus one run at its default (FABRIK_TEST_MEM_MAX, 4G): one
# leg at the ceiling leaves room for one default-sized sibling (two legs at it can exceed the slice) —
# revisit it when either default changes. The floor mirrors LEG_FLOOR_S: a tiny value is clamped up,
# never ignored, and the 137 refusal then names it. Cobra (D-253): the cheapest way past "legs fit" is a
# larger declared value; the MAX bounds it, and a leg past it is still a named ceiling kill.
_LEG_MEM_RE = re.compile(r"(?m)^#[ \t]*merge-test-mem:[ \t]*([0-9]+)([MG])[ \t\r]*$")
LEG_MEM_FLOOR_MIB = 256
LEG_MEM_MAX_MIB = 8192
# capped_run.sh's own verdict lines for a kill at the ceiling and at the time limit (capped_run.sh:160,
# :163); each ends with " — " and the whole argv, which for a script leg is the multi-line script
_CEILING_KILL = "capped_run: killed at the memory ceiling ("
_TIME_KILL = "capped_run: stopped at the "
# a line that LOOKS like the declaration (any value) — the grammar refused it when _LEG_MEM_RE did not
# match; prose that merely names the header is not one
_LEG_MEM_LIKE_RE = re.compile(r"(?m)^[ \t]*#[ \t]*merge-test-mem[ \t]*:")
PUSH_TIMEOUT_S = 600
SYNC_TIMEOUT_S = 900
EXIT_OK = 0
# (g) runs only in the hub; both are module constants so a test replaces them IN-PROCESS and no
# environment variable can point a production run at another tree.
HUB_CHECKOUT = Path("/opt/fabrik")
SYNC_ARGV = [sys.executable, "scripts/sync_enforcement_to_projects.py", "--force"]
# Throwaway-worktree and carry git calls run with no hooks: a post-merge/post-checkout hook in
# the hub syncs the fleet or rewrites files, which must never fire from a scratch build.
NO_HOOKS = ("-c", "core.hooksPath=/dev/null")
_L_OURS, _L_BASE, _L_THEIRS = "fabrik-merge-ours", "fabrik-merge-base", "fabrik-merge-theirs"
_MARKER_RE = re.compile(r"(?m)^(?:<{7}|\|{7}|={7}|>{7})(?: |$)")
_D_ROW_RE = re.compile(r"(?m)^\| D-(\d+)")
_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
DONE_PHASES = ("replied",)


def on_phase(name: str) -> None:
    """TEST SEAM — a no-op in production, called at ``after-build``, ``before-cas``,
    ``before-carry`` and ``before-push``. Tests REPLACE this function in-process to move a ref or
    edit a path at that exact point; there is deliberately no environment variable or flag that
    reaches it, so a production run has no injection path."""
    del name


class BudgetSpentError(RefusedError):
    """This invocation's owner-test budget ran out — not a test verdict; a new run (``retry`` or
    ``resume``) has a new budget."""


class NotWaitingError(RefusedError):
    """``merge <id>``: no such request waits in the inbox (another run took it, or it never came)."""


class ConflictError(RefusedError):
    """A build conflict the auto-resolve may not settle; ``paths`` names where."""

    def __init__(self, paths: list[str], message: str) -> None:
        super().__init__(message)
        self.paths = paths


class MergePartialError(Exception):
    """The merge is committed locally but a later step (push, reply, ack) did not finish: exit 4,
    finish with ``resume <id>``."""


class _Ctx:
    """One merge run: the main checkout, its git common dir, the owner and the mailbox."""

    def __init__(self, main: Path, common: Path, owner: str) -> None:
        self.main = main
        self.common = common
        self.owner = owner
        self.mailbox = main.name
        self.records = common / "fabrik-merge"
        self.notes: list[str] = []
        # remotes a fetch could not reach THIS run: a request on one defers without another fetch,
        # and the inbox is served only for requests on other remotes (one timeout per remote)
        self.unreachable: set[str] = set()
        # every owner-test leg of this invocation draws on one budget (_leg_timeout)
        self.test_deadline = time.monotonic() + MERGE_TEST_BUDGET_S
        self.leg_limit = TEST_TIMEOUT_S
        self.leg_t0 = 0.0  # when the current leg started, after its admission wait
        self.admit_spent = 0.0  # seconds this invocation waited for box-wide admission
        self.full_leg = TEST_TIMEOUT_S  # a full leg: TEST_TIMEOUT_S, or the base's declared one
        self.leg_mem: str | None = (
            None  # the base's declared memory ceiling, or capped_run's default
        )
        self.pretesting = False  # `request --pretest`: never skip on a pretest record
        self.tests_deferred = False  # the leg moved past the CAS (`_after_merge_due`, D-1186)
        self.after_base = ""  # the after-merge runner's leg only: the last tested tip (D-1186)
        self.catching_up = False  # `_merge_into_base(catch_up=True)`: its leg never defers


def _declared_leg(script: str) -> int:
    """The base script's ``# merge-test-timeout:`` value, clamped; TEST_TIMEOUT_S without one."""
    m = _LEG_DECL_RE.search(script)
    if not m:
        return TEST_TIMEOUT_S
    digits = m.group(1).lstrip("0") or "0"
    if len(digits) > 9:  # past any budget, and int() refuses a string over 4300 digits
        return MERGE_TEST_BUDGET_S
    return max(LEG_FLOOR_S, min(int(digits), MERGE_TEST_BUDGET_S))


# D-1186's pre-committed relief valve (W-3237ba45): past a declared rate of merges a day, a merge
# lands after build, preflight and CAS, and the SAME selected leg runs after it, in one background
# run over every merge landed since the last tested tip (`after-merge-runner`). A red there files a
# P0 on the cause merge's author, and that author's next request is refused until the P0 is the item
# it carries (`_after_merge_block`). The base opts in with `# merge-tests-after-merge-above: <n>` alone
# on its line (merges per day over the last 7 days); without it every merge keeps its leg (D-1211).
# Cobra (D-253): the cheapest way past the leg is a rate kept above the line on purpose — the rate is
# read from the merge records themselves, and every landed tree is still tested, only later.
_AFTER_DECL_RE = re.compile(
    r"(?m)^#[ \t]*merge-tests-after-merge-above:[ \t]*([0-9]{1,4})[ \t\r]*$"
)
AFTER_RATE_DAYS = 7
AFTER_DIR = "after-merge"
AFTER_TAG = "after-merge-red"


def _merge_rate(ctx: _Ctx, now: float | None = None) -> float:
    """Merges a day over the last AFTER_RATE_DAYS: the merged records whose file changed in that
    window (a record is rewritten at its reply, the last step of a merge)."""
    now = time.time() if now is None else now
    since = now - AFTER_RATE_DAYS * 86400
    n = 0
    for f in ctx.records.glob("*.json"):
        try:
            if f.stat().st_mtime < since:
                continue
            if json.loads(f.read_text(encoding="utf-8")).get("outcome") == "merged":
                n += 1
        except (OSError, ValueError):
            continue
    return n / AFTER_RATE_DAYS


def _after_merge_due(ctx: _Ctx, script: str) -> str:
    """The reason this merge's leg runs after the CAS, or "" when it runs before it."""
    m = _AFTER_DECL_RE.search(script)
    if not m or ctx.pretesting or ctx.catching_up:
        return ""
    line, rate = int(m.group(1)), _merge_rate(ctx)
    if rate <= line:
        return ""
    return (
        f"deferred to the after-merge run (D-1186: {rate:.1f} merges/day over {AFTER_RATE_DAYS} "
        f"days > {line}); the landed tree is tested in the background, a red files a P0 on its author"
    )


def _declared_mem(script: str) -> str | None:
    """The base script's ``# merge-test-mem:`` value in MiB (``"<n>M"``), clamped; None without
    one, so capped_run's own default holds."""
    m = _LEG_MEM_RE.search(script)
    if not m:
        return None
    digits = m.group(1).lstrip("0") or "0"
    if len(digits) > 9:  # past any ceiling, and int() refuses a string over 4300 digits
        return f"{LEG_MEM_MAX_MIB}M"
    mib = int(digits) * (1024 if m.group(2) == "G" else 1)
    return f"{max(LEG_MEM_FLOOR_MIB, min(mib, LEG_MEM_MAX_MIB))}M"


def _mem_lines_ignored(script: str) -> bool:
    """Whether a line shaped like the declaration (``# merge-test-mem:`` and any value) fails the
    grammar — before a valid one too, which then wins silently unless this says so."""
    for m in _LEG_MEM_LIKE_RE.finditer(script):
        end = script.find("\n", m.start())
        line = script[m.start() : len(script) if end < 0 else end + 1]
        if not _LEG_MEM_RE.match(line):
            return True
    return False


def _leg_timeout(ctx: _Ctx) -> int:
    """The next leg's limit: a full leg, or what is left of the budget; under LEG_FLOOR_S left no
    leg starts (BudgetSpentError)."""
    left = int(ctx.test_deadline - time.monotonic())
    if left < LEG_FLOOR_S:
        raise BudgetSpentError(
            f"the owner-test budget of this run ({MERGE_TEST_BUDGET_S}s) is spent — no leg started, "
            "not a test verdict"
        )
    return min(ctx.full_leg, left)


def _lit_env() -> dict:
    """Pathspecs are LITERAL: a merged file named ``*.md`` must never glob."""
    return {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}


def _gitc(cwd: Path, *args: str, timeout: int = GIT_TIMEOUT_S) -> str:
    """``git`` in ``cwd`` with literal pathspecs and no hooks; raises on failure."""
    argv = ["git", *NO_HOOKS, *args]
    res = _run(argv, timeout, cwd=cwd, env=_lit_env())
    if res.returncode != 0:
        raise RefusedError(
            f"git {' '.join(args[:3])} failed: {res.stderr.strip() or res.returncode}"
        )
    return res.stdout


def _run_bytes(
    argv: list[str], timeout: int, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(  # noqa: S603 — fixed argv, no shell
            argv,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimedOutError(f"{' '.join(argv[:3])} timed out after {timeout}s") from exc


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


def _encode(text: str) -> bytes:
    return text.encode("utf-8", "surrogateescape")


def _rev(cwd: Path, ref: str) -> str:
    res = _run(["git", "rev-parse", "-q", "--verify", f"{ref}^{{commit}}"], GIT_TIMEOUT_S, cwd=cwd)
    return res.stdout.strip() if res.returncode == 0 else ""


def _is_ancestor(cwd: Path, older: str, newer: str) -> bool:
    res = _run(["git", "merge-base", "--is-ancestor", older, newer], GIT_TIMEOUT_S, cwd=cwd)
    return res.returncode == 0


def _blob(cwd: Path, sha: str) -> str:
    res = _run_bytes(["git", "cat-file", "blob", sha], GIT_TIMEOUT_S, cwd=cwd)
    if res.returncode != 0:
        raise RefusedError(f"git cat-file blob {sha} failed: {_decode(res.stderr).strip()}")
    return _decode(res.stdout)


# --- the mail store (this tree's mail.py, imported once) -------------------------------------
_MAIL: ModuleType | None = None


def _mail() -> ModuleType:
    """THIS tree's ``mail.py`` as a module: ``list_msgs``, ``_parse`` and ``_body_fields`` are
    read from the one implementation, never re-parsed here."""
    global _MAIL
    if _MAIL is None:
        spec = importlib.util.spec_from_file_location("fabrik_mail_for_merge", MAIL_PY)
        if spec is None or spec.loader is None:
            raise RefusedError(f"cannot import {MAIL_PY}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MAIL = mod
    return _MAIL


def _mail_cli(ctx: _Ctx, *args: str, stdin_text: str | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(MAIL_PY), *args]
    return _run(argv, TOOL_TIMEOUT_S, cwd=ctx.main, stdin_text=stdin_text)


def _split_message(text: str) -> tuple[dict, dict]:
    """(frontmatter, script-written body fields) of a delivered message."""
    mail = _mail()
    fm = mail._parse(text) or {}
    body = text[text.find("\n---", 4) + 4 :] if fm else ""
    return fm, mail._body_fields(body)


def _owner_requests(ctx: _Ctx) -> list[dict]:
    """Inbox ``merge-request``s whose ``agent:`` IS the owner and ``ack: required``, oldest first.
    ``list_msgs`` also returns every UNADDRESSED message, so the exact filter lives here: the
    coordinator's ``ack: no`` copy and an unaddressed request are never picked (V7)."""
    owner = _norm(ctx.owner)
    picked = [
        fm
        for fm in _mail().list_msgs(ctx.mailbox, None)
        if fm.get("kind") == "merge-request"
        and _norm(fm.get("agent") or "") == owner
        and (fm.get("ack") or "") == "required"
    ]
    return sorted(picked, key=lambda fm: fm.get("id", ""))


# --- records and the lock -------------------------------------------------------------------
def _proc_start(pid: int) -> str | None:
    """Field 22 (starttime) of ``/proc/<pid>/stat``, split after the LAST ``)`` — a comm may
    carry spaces and parentheses. None when the process is gone or unreadable."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rest = text[text.rfind(")") + 1 :].split()
    return rest[19] if len(rest) > 19 else None


def _claimer() -> dict:
    """The record's claimer: this run's OWN pid and its start time (O36), and the session."""
    pid = os.getpid()
    return {
        "session": os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
        "pid": pid,
        "start": _proc_start(pid),
    }


def _save(ctx: _Ctx, rec: dict) -> None:
    """Atomic record write: a temp file in the same directory, then ``os.replace``."""
    ctx.records.mkdir(parents=True, exist_ok=True)
    path = ctx.records / f"{rec['id']}.json"
    tmp = ctx.records / f".{rec['id']}.json.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())  # the bytes are on disk BEFORE the rename publishes them
    os.replace(tmp, path)
    dir_fd = os.open(ctx.records, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _load(ctx: _Ctx, msg_id: str) -> dict | None:
    try:
        rec = json.loads((ctx.records / f"{msg_id}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RefusedError(f"record {msg_id} is unreadable: {exc}") from exc
    return rec if isinstance(rec, dict) else None


def _stranded(rec: dict) -> bool:
    """Short of ``replied`` AND its process is gone: the pid is dead, or alive with a different
    start time (a reused pid). A record naming THIS run's own pid and start is not stranded."""
    if rec.get("phase") in DONE_PHASES:
        return False
    pid, start = rec.get("pid"), rec.get("start")
    if isinstance(pid, int) and pid > 0 and start is not None:
        return _proc_start(pid) != start
    return True


@contextlib.contextmanager
def _merge_lock(common: Path) -> Iterator[None]:
    """``flock(LOCK_EX|LOCK_NB)`` on ``<common>/fabrik-merge.lock`` for the WHOLE run; a second
    run exits at once, before it claims, builds or writes anything (invariant 6)."""
    fd = os.open(common / "fabrik-merge.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RefusedError(
                f"another merge run holds {common / 'fabrik-merge.lock'} — nothing claimed"
            ) from None
        yield
    finally:
        os.close(fd)


# --- snapshots ------------------------------------------------------------------------------
def _merged_paths(cwd: Path, old: str, new: str) -> list[tuple[str, str]]:
    """(status, path) of every path ``old..new`` touches, renames split into delete + add."""
    out = _gitc(cwd, "diff", "--name-status", "--no-renames", "-z", old, new)
    parts = out.split("\0")
    pairs = [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2) if parts[i]]
    for _, path in pairs:
        if "\n" in path:
            raise RefusedError(f"merged path {path!r} carries a line break — refused")
    return pairs


def _tree_blobs(cwd: Path, commit: str, paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    out = _gitc(cwd, "ls-tree", "-r", "-z", "--full-tree", commit, "--", *paths)
    blobs: dict[str, str] = {}
    for entry in out.split("\0"):
        meta, sep, path = entry.partition("\t")
        if sep:
            blobs[path] = meta.split()[2]
    return blobs


def _index_blobs(cwd: Path, paths: list[str]) -> dict[str, str]:
    """Index entry per path; an unmerged entry reads ``unmerged``."""
    if not paths:
        return {}
    out = _gitc(cwd, "ls-files", "-s", "-z", "--", *paths)
    idx: dict[str, str] = {}
    for entry in out.split("\0"):
        meta, sep, path = entry.partition("\t")
        if not sep:
            continue
        _, sha, stage = meta.split()
        idx[path] = "unmerged" if stage != "0" or idx.get(path) == "unmerged" else sha
    return idx


def _worktree_hashes(cwd: Path, paths: list[str]) -> dict[str, str | None]:
    """Blob hash of each path as it stands on disk (None absent, ``dir`` a directory)."""
    out: dict[str, str | None] = {}
    regular: list[str] = []
    for path in paths:
        f = cwd / path
        if not os.path.lexists(f):
            out[path] = None
        elif f.is_symlink():
            res = _run(
                ["git", "hash-object", "--stdin"], GIT_TIMEOUT_S, cwd=cwd, stdin_text=os.readlink(f)
            )
            out[path] = res.stdout.strip()  # a symlink's blob IS its target text
        elif f.is_dir():
            out[path] = "dir"
        else:
            regular.append(path)
    if regular:
        res = _run(
            ["git", "hash-object", "--stdin-paths"],
            GIT_TIMEOUT_S,
            cwd=cwd,
            stdin_text="\n".join(regular) + "\n",
        )
        hashes = res.stdout.split()
        if res.returncode != 0 or len(hashes) != len(regular):
            raise RefusedError(f"git hash-object failed: {res.stderr.strip() or res.returncode}")
        out.update(zip(regular, hashes, strict=True))
    return out


def _snapshot(cwd: Path, paths: list[str]) -> dict[str, list]:
    """``{path: [worktree hash, index entry]}`` of the main checkout — the (a) snapshot."""
    wt = _worktree_hashes(cwd, paths)
    idx = _index_blobs(cwd, paths)
    return {p: [wt.get(p), idx.get(p)] for p in paths}


# --- the 3-way ledger merge and its pure-insertion resolver (b) -----------------------------
def _max_d(lines: list[str]) -> int:
    return max((int(m) for m in _D_ROW_RE.findall("".join(lines))), default=-1)


def _resolve_insertions(path: str, text: str) -> str:
    """Keep BOTH sides of every conflict whose base section is EMPTY (both sides are pure
    insertions at the same point) — newest D-row first for DECISIONS, ours then theirs
    elsewhere. A conflict where a side edits an existing line refuses. The result is checked
    for a line-anchored conflict marker before it is trusted."""
    out: list[str] = []
    state = ""
    ours: list[str] = []
    orig: list[str] = []
    theirs: list[str] = []
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n")
        if not state and bare == f"<<<<<<< {_L_OURS}":
            state, ours, orig, theirs = "o", [], [], []
        elif state == "o" and bare == f"||||||| {_L_BASE}":
            state = "b"
        elif state == "b" and bare == "=======":
            state = "t"
        elif state == "t" and bare == f">>>>>>> {_L_THEIRS}":
            if orig:
                raise RefusedError(f"{path}: a side edits an existing line at a conflict")
            first, second = ours, theirs
            if path == DECISIONS and _max_d(theirs) >= _max_d(ours):
                first, second = theirs, ours
            if first and not first[-1].endswith("\n"):
                first = [*first[:-1], first[-1] + "\n"]
            out += first + second
            state = ""
        elif state:
            {"o": ours, "b": orig, "t": theirs}[state].append(line)
        else:
            out.append(line)
    if state:
        raise RefusedError(f"{path}: an unterminated conflict")
    result = "".join(out)
    if _MARKER_RE.search(result):
        raise RefusedError(f"{path}: a conflict marker remains after the auto-resolve — refused")
    return result


def _merge3(path: str, ours: str, orig: str, theirs: str) -> str:
    """``git merge-file -p --diff3`` of three texts; a conflict is auto-resolved only when it is
    a pure insertion (``_resolve_insertions``), otherwise this refuses."""
    with tempfile.TemporaryDirectory(prefix="fabrik-merge3-") as tmp:
        files = []
        for name, text in (("ours", ours), ("base", orig), ("theirs", theirs)):
            f = Path(tmp) / name
            f.write_bytes(_encode(text))
            files.append(str(f))
        argv = ["git", "merge-file", "-p", "--diff3", "-L", _L_OURS, "-L", _L_BASE, "-L", _L_THEIRS]
        res = _run_bytes([*argv, *files], GIT_TIMEOUT_S)
    if res.returncode < 0 or res.returncode > 127:
        raise RefusedError(f"{path}: git merge-file failed: {_decode(res.stderr).strip()}")
    merged = _decode(res.stdout)
    return merged if res.returncode == 0 else _resolve_insertions(path, merged)


def _merge_ledger(base: str, ours: str, theirs: str, path: str) -> None:
    """``merge-ledger %O %A %B %P``: git's merge driver for the ledgers (W-53360407, D-1386).
    Resolves the three files with ``_merge3`` and writes the result over ``ours`` atomically; any
    refusal or error leaves ``ours`` untouched and no temp file behind, so the installer's ``||``
    fallback (``git merge-file``) re-merges it into ordinary markers. For DECISIONS it also refuses
    a D-id the result holds more often than ours, once it is held twice — ``_build``'s landing
    check, moved to the first merge that can see the clash. A path that is not one of ``LEDGERS``
    refuses. An entry both sides carry beside different insertions (a cherry-pick onto two branches
    that each add their own entry) lands twice, as it does at landing: the resolver's class,
    W-f6ede574 — line-count rules here refused shared structure."""
    if path not in LEDGERS:
        raise RefusedError(
            f"{path}: not a ledger this driver merges ({', '.join(sorted(LEDGERS))})"
        )
    ours_text = _decode(Path(ours).read_bytes())
    result = _merge3(
        path, ours_text, _decode(Path(base).read_bytes()), _decode(Path(theirs).read_bytes())
    )
    if path == DECISIONS:
        held = collections.Counter(_D_ROW_RE.findall(ours_text))
        clash = {
            n
            for n, c in collections.Counter(_D_ROW_RE.findall(result)).items()
            if c > max(1, held[n])
        }
        if clash:
            ids = ", ".join(f"D-{n}" for n in sorted(clash, key=int))
            raise RefusedError(f"{ids} would appear twice in {DECISIONS} — re-mint one side")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(ours)), prefix=".merge-ledger-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_encode(result))
        os.replace(tmp, ours)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# --- (a)-(d): build, preflight, tests, CAS --------------------------------------------------
@contextlib.contextmanager
def _throwaway(ctx: _Ctx, rec: dict, commit: str, prefix: str | None = None) -> Iterator[Path]:
    """A detached worktree at ``commit`` under a scratch parent, named after the main checkout
    (``<tmp>/<repo basename>``) with a ``fabrik-lib`` link beside it when the main checkout's
    parent holds one (what the repo's tests reach as ``../fabrik-lib``). Removed and pruned on
    EVERY exit, success or refusal. ``prefix`` is ``_PRETEST_PREFIX`` for a pretest, which the
    owner's sweep (``_THROWAWAY_DIR_RE``) never matches: a pretest runs outside the merge lock."""
    parent = Path(tempfile.mkdtemp(prefix=prefix or _THROWAWAY_PREFIX))
    wt = parent / ctx.main.name
    rec["worktree"] = str(wt)
    _save(ctx, rec)
    try:
        with _worktree_lock(ctx):
            _gitc(
                ctx.main,
                "worktree",
                "add",
                "--detach",
                "-q",
                str(wt),
                commit,
                timeout=TOOL_TIMEOUT_S,
            )
        lib = ctx.main.parent / "fabrik-lib"
        link = parent / "fabrik-lib"
        # In the repo NAMED fabrik-lib the worktree already IS `<tmp>/fabrik-lib`, so its tests'
        # `../fabrik-lib` resolves to the commit under test and no link is made (01M3TW5MF2).
        if lib.is_dir() and link != wt:
            # a `fabrik-lib` sibling that IS this checkout (an alias of its realpath) points the
            # throwaway's `../fabrik-lib` at the commit under test, never the live checkout
            link.symlink_to(wt if lib.resolve() == ctx.main.resolve() else lib)
        yield wt
    finally:
        _remove_throwaway(ctx, wt, _PRETEST_DIR_RE if prefix == _PRETEST_PREFIX else None)
        rec.pop("worktree", None)
        _save(ctx, rec)


_THROWAWAY_PREFIX = "fabrik-merge-"
# ``tempfile.mkdtemp`` appends 8 characters from this alphabet (CPython's _RandomNameSequence).
_THROWAWAY_DIR_RE = re.compile(r"^fabrik-merge-[a-z0-9_]{8}$")
_PRETEST_PREFIX = "fabrik-pretest-"
_PRETEST_DIR_RE = re.compile(r"^fabrik-pretest-[a-z0-9_]{8}$")


def _owned_throwaway(ctx: _Ctx, wt: Path, dir_re: re.Pattern | None = None) -> bool:
    """O12: a worktree THIS tool created, and nothing wider — ``<temp root>/<mkdtemp dir>/<repo
    basename>``, the mkdtemp dir sitting DIRECTLY under the temp root ``_throwaway`` uses."""
    parent = wt.parent
    return (
        wt.name == ctx.main.name
        and bool((dir_re or _THROWAWAY_DIR_RE).fullmatch(parent.name))
        and parent.parent.resolve() == Path(tempfile.gettempdir()).resolve()
    )


def _remove_throwaway(ctx: _Ctx, wt: Path, dir_re: re.Pattern | None = None) -> None:
    """Remove and prune one throwaway; the rmtree is ONLY the mkdtemp dir, and only when the
    path is one this tool created (``_owned_throwaway``) — never anything wider."""
    if not _owned_throwaway(ctx, wt, dir_re):
        return
    with _worktree_lock(ctx):
        _run(
            ["git", *NO_HOOKS, "worktree", "remove", "--force", str(wt)],
            TOOL_TIMEOUT_S,
            cwd=ctx.main,
        )
    shutil.rmtree(wt.parent, ignore_errors=True)  # outside the lock: a big tree blocks no add
    with _worktree_lock(ctx):
        _run(["git", "worktree", "prune"], GIT_TIMEOUT_S, cwd=ctx.main)


@contextlib.contextmanager
def _worktree_lock(ctx: _Ctx) -> Iterator[None]:
    """A BLOCKING ``flock`` on ``<common>/fabrik-worktrees.lock`` around one ``git worktree``
    add, remove or prune (W-0c8c43f1). ``prune`` deletes any registration whose ``gitdir`` is not
    written yet, so a sibling process's ``add`` between its ``mkdir`` and its ``gitdir`` write
    fails (Fable's probe: 317 failures in 2387 adds beside a prune loop, 2 in 1971 against
    ``remove`` alone). Every writer of the registrations in this file takes it; git itself and
    other tools do not, so a by-hand ``git worktree prune`` keeps the old race. Fail direction: a
    lock that cannot be opened raises, which refuses the merge — never an unlocked add."""
    try:
        fd = os.open(ctx.common / "fabrik-worktrees.lock", os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        raise RefusedError(f"cannot open the worktree lock: {exc}") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


# A work-item file: `work.py` writes one key per line in sorted order, so two sides changing DISJOINT
# keys that sort side by side collide in git's line merge (W-5f3617e6); `work.py merge-item` merges
# them key-wise against the base instead.
MERGE_ITEM_CONFLICT_RC = 3  # `work.py merge-item`'s conflict exit (`MERGE_CONFLICT_RC` there)
_WORK_ITEM_RE = re.compile(r"\.fabrik/work/W-[0-9a-f]{8}\.json")


def _conflict_stages(wt: Path, path: str) -> dict[str, str]:
    """``{stage: blob sha}`` of ``path``'s unmerged index entries (1 base, 2 ours, 3 theirs)."""
    stages: dict[str, str] = {}
    for entry in _gitc(wt, "ls-files", "-u", "-z", "--", path).split("\0"):
        meta, sep, _ = entry.partition("\t")
        if sep:
            _, sha, stage = meta.split()
            stages[stage] = sha
    return stages


def _merge_work_item(wt: Path, path: str, base: str) -> None:
    """Resolve one conflicted work-item file with ``work.py merge-item`` and stage it. A key both
    sides changed to different values, or a file deleted on one side, is the REQUESTER's conflict
    and refuses naming it; a merge-item that fails any other way is a refusal, never a guess —
    including a synced repo whose ``work.py`` predates the verb (argparse exits 2), which refused
    this conflict before as well; the two files travel on the same sync."""
    stages = _conflict_stages(wt, path)
    if "2" not in stages or "3" not in stages:
        raise ConflictError([path], f"{path}: deleted on one side — {_resend(base)}")
    with tempfile.TemporaryDirectory(prefix="fabrik-merge-item-") as tmp:
        files = {}
        for name, stage in (("base", "1"), ("ours", "2"), ("theirs", "3")):
            files[name] = Path(tmp) / f"{name}.json"
            files[name].write_bytes(_encode(_blob(wt, stages[stage]) if stage in stages else ""))
        res = _run(
            [sys.executable, str(WORK_PY), "merge-item", *(str(files[n]) for n in files)],
            TOOL_TIMEOUT_S,
            cwd=wt,
        )
        detail = (res.stderr.strip() or res.stdout.strip()).removeprefix("work: ")
        if res.returncode == MERGE_ITEM_CONFLICT_RC:
            raise ConflictError([path], f"{path}: {detail} — {_resend(base)}")
        if res.returncode != 0:
            raise RefusedError(f"{path}: work.py merge-item failed (rc {res.returncode}): {detail}")
        merged = files["ours"].read_bytes()
        try:
            item_id = json.loads(merged).get("id")
        except (ValueError, AttributeError):
            item_id = None
        if item_id != Path(path).stem:  # never stage an item whose id is not its file's name
            raise RefusedError(
                f"{path}: the merged item's id is {item_id!r}, not {Path(path).stem}"
            )
        (wt / path).write_bytes(merged)
    _gitc(wt, "add", "--", path)


def _build(ctx: _Ctx, wt: Path, other: str, message: str, base: str) -> str:
    """(a)+(b): merge ``other`` into the throwaway's HEAD with ``message``; only pure-insertion
    conflicts on the five ledgers and key-wise-mergeable work-item files are auto-resolved, and any
    other conflicted path refuses first. Returns the merge commit."""
    res = _run(
        # --no-log: merge.log=true appends a shortlog after -m and the trailer block parses as none
        ["git", *NO_HOOKS, "merge", "--no-ff", "--no-edit", "--no-log", "-q", "-m", message, other],
        TOOL_TIMEOUT_S,
        cwd=wt,
    )
    if res.returncode != 0:
        conflicted = [
            p for p in _gitc(wt, "diff", "--name-only", "-z", "--diff-filter=U").split("\0") if p
        ]
        if not conflicted:
            raise RefusedError(f"git merge failed: {res.stderr.strip() or res.stdout.strip()}")
        items = [p for p in conflicted if _WORK_ITEM_RE.fullmatch(p)]
        others = sorted(p for p in conflicted if p not in LEDGERS and p not in items)
        if others:
            raise ConflictError(others, f"conflict in {', '.join(others)} — {_resend(base)}")
        for path in items:
            _merge_work_item(wt, path, base)
        for path in (p for p in conflicted if p in LEDGERS):
            stages = _conflict_stages(wt, path)
            if "2" not in stages or "3" not in stages:
                raise ConflictError([path], f"{path}: deleted on one side — {_resend(base)}")
            orig = _blob(wt, stages["1"]) if "1" in stages else ""
            try:
                text = _merge3(path, _blob(wt, stages["2"]), orig, _blob(wt, stages["3"]))
            except RefusedError as exc:
                # the REQUESTER's conflict: only here does the remedy name their branch (W-9c2f371a)
                raise ConflictError([path], f"{exc} — {_resend(base)}") from exc
            (wt / path).write_bytes(_encode(text))
            _gitc(wt, "add", "--", path)
        # The request's own message, never `--no-edit`: that reuses git's MERGE_MSG, whose
        # `# Conflicts:` comment block `commit` keeps verbatim when no editor runs (V9).
        _gitc(wt, "commit", "-q", "-m", message, timeout=TOOL_TIMEOUT_S)
    new = _gitc(wt, "rev-parse", "HEAD").strip()
    # O9: a merge that makes two DECISIONS rows share an id is refused; ids already duplicated
    # on the base are not this request's doing.
    clash = _dup_ids(_show(wt, new, DECISIONS)) - _dup_ids(_show(wt, f"{new}^1", DECISIONS))
    if clash:
        ids = ", ".join(f"D-{n}" for n in sorted(clash, key=int))
        raise RefusedError(f"{ids} collides in {DECISIONS} — re-mint and resend")
    return new


def _show(cwd: Path, commit: str, path: str) -> str:
    """``path`` at ``commit``, or "" when it is absent there."""
    res = _run_bytes(["git", "show", f"{commit}:{path}"], GIT_TIMEOUT_S, cwd=cwd)
    return _decode(res.stdout) if res.returncode == 0 else ""


def _dup_ids(text: str) -> set[str]:
    """The ``| D-NNN |`` ids that open more than one DECISIONS row."""
    seen: set[str] = set()
    dups: set[str] = set()
    for n in _D_ROW_RE.findall(text):
        (dups if n in seen else seen).add(n)
    return dups


def _main_on(ctx: _Ctx, base: str) -> bool:
    res = _run(["git", "symbolic-ref", "-q", "HEAD"], GIT_TIMEOUT_S, cwd=ctx.main)
    return res.returncode == 0 and res.stdout.strip() == HEADS + base


def _refuse_linked_base(ctx: _Ctx, base: str) -> None:
    """A base checked out in a LINKED worktree would be left behind by the CAS: refuse."""
    entries = _git("worktree", "list", "--porcelain", cwd=ctx.main).split("\n\n")
    for entry in entries[1:]:
        lines = entry.splitlines()
        if f"branch {HEADS}{base}" in lines:
            where = next(
                (ln[len("worktree ") :] for ln in lines if ln.startswith("worktree ")), "?"
            )
            raise RefusedError(f"{base} is checked out in the linked worktree {where} — refused")


def _preflight(
    ctx: _Ctx, base: str, old: str, new: str
) -> tuple[list[tuple[str, str]], dict, bool]:
    """(a): snapshot every merged path in the main checkout and refuse — nothing changed — on an
    untracked collision, a dirty non-ledger path, a dirty path the merge deletes or renames, a
    staged difference from HEAD, or a dirty ledger whose 3-way carry conflicts (a pure insertion
    resolves; an edit of an existing line refuses here, BEFORE the CAS). Returns (merged paths,
    snapshot, whether the main checkout was on base — only then is it preflighted)."""
    merged = _merged_paths(ctx.main, old, new)
    if not _main_on(ctx, base):
        return merged, {}, False
    paths = [p for _, p in merged]
    snap = _snapshot(ctx.main, paths)
    old_b = _tree_blobs(ctx.main, old, paths)
    new_b = _tree_blobs(ctx.main, new, paths)
    for status, path in merged:
        wt, idx = snap[path]
        head = old_b.get(path)
        if idx == "unmerged" or idx != head:
            raise RefusedError(f"{path} is staged differently from HEAD in the main checkout")
        if head is None:
            parts = Path(path).parts
            blocked = [
                "/".join(parts[:i])
                for i in range(1, len(parts))
                if os.path.lexists(ctx.main.joinpath(*parts[:i]))
                and not ctx.main.joinpath(*parts[:i]).is_dir()
            ]
            if wt is not None or blocked:
                raise RefusedError(f"{path} is untracked in the main checkout — collision")
            continue
        if wt == head:
            continue
        if status == "D":
            raise RefusedError(f"{path} is dirty in the main checkout and the merge deletes it")
        if path not in LEDGERS:
            raise RefusedError(f"{path} is dirty in the main checkout (not a ledger)")
        if wt is None or wt == "dir" or (ctx.main / path).is_symlink() or path not in new_b:
            raise RefusedError(f"{path} is dirty in the main checkout in a way no carry can merge")
        current = _decode((ctx.main / path).read_bytes())
        try:
            _merge3(path, current, _blob(ctx.main, head), _blob(ctx.main, new_b[path]))
        except RefusedError as exc:
            # the OWNER's uncommitted ledger work conflicts, not the branch (W-9c2f371a)
            raise RefusedError(
                f"{exc} — the owner's uncommitted {path} in the main checkout conflicts with the "
                "merge; the owner commits or moves it aside, and the branch needs no change"
            ) from exc
    return merged, snap, True


# The touched-tests fallback carries the merged ``src`` through this shim rather than a PYTHONPATH
# entry: every PYTHONPATH entry precedes the stdlib, so a project package named like a stdlib
# module (``src/copy/``) shadowed it and no test ran. The shim puts ``src`` after the stdlib but
# before site-packages (where an editable install of the main checkout lives), and rides the env
# into every child process the tests spawn.
_SITECUSTOMIZE = """\
import os, site, sys
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]
_src = os.environ.get("FABRIK_MERGE_SRC", "")
if _src:
    _site = set(site.getsitepackages())
    if site.ENABLE_USER_SITE:
        _site.add(site.getusersitepackages())
    sys.path[:] = [p for p in sys.path if p != _src]
    _at = next((i for i, p in enumerate(sys.path) if p in _site), len(sys.path))
    sys.path.insert(_at, _src)
del sys.modules["sitecustomize"]
try:
    import sitecustomize  # noqa: F401 — chain to the interpreter's own (Debian, a venv)
except ImportError:
    pass
"""


# Both owner-test legs run BEFORE the merge lands, so before the merge owner's merge-time render of
# the corpus into ~/.claude (`commands/assemble_commands.py`, run from merged master by hand — CLAUDE.md
# § Behavior; this script renders nothing): this tells the tests so, and the hub's tests/conftest.py skips its `live_box` tests —
# the ones comparing that installed corpus to the tree, which cannot match yet (W-c3177526). Inert
# in a repo whose conftest does not read it.
_MERGE_CHECK_ENV = {"FABRIK_MERGE_CHECK": "1"}


def _fallback_env(wt: Path, shim: Path) -> dict:
    """The fallback's env: the shim ALONE on ``PYTHONPATH`` — the caller's entries would precede the
    stdlib and could name the main checkout's own ``src``, so the import root comes from the
    throwaway, never the caller. It is the throwaway's ``src``, or its root when ``src`` is itself
    a package (imported as ``src.x``). ``FABRIK_MERGE_CHECK=1`` rides along (``_MERGE_CHECK_ENV``)."""
    root = wt if (wt / "src" / "__init__.py").exists() else wt / "src"
    return {
        **os.environ,
        **_MERGE_CHECK_ENV,
        "PYTHONPATH": str(shim),
        "FABRIK_MERGE_SRC": str(root),
    }


def _copy_worktree_include(ctx: _Ctx, wt: Path, old: str) -> str | None:
    """Copy the base's ``.worktreeinclude`` set from the main checkout into the build tree.

    The build tree is a fresh checkout, so a gitignored ``.env`` was absent and a pydantic-settings
    app failed at import — a correct request refused (brand-identiy-creator 01M46NZMP4F08KBP7WC8KF1Z37).
    Claude Code copies this same set into every new linked worktree, so the owner's tests now see
    what a worktree sees, read by the app's own loader rather than a second ``.env`` parser
    (D-610). The list comes from the BASE, never the branch; a file the tree already holds (tracked)
    is never overwritten; a path that leaves the checkout, or a symlink, is skipped. The build tree
    lives in a private mkdtemp directory and is removed after the merge.

    Every synced project IGNORES ``.worktreeinclude`` (the synced .gitignore block writes it, the sync
    owns it), so the base never holds it there: an ignored, regular list is then read from the main
    checkout's working tree — never the branch's (brand-identiy-creator 01M48K5ZGYWBX1F4S8K8GQ32E0).
    A TRACKED list still governs from the base only (``check-ignore`` without ``--no-index`` answers 1
    for a tracked path). With no readable list the copy returns a NOTE instead of passing silently;
    the caller puts it in the refusal and on stderr."""
    res = _run(["git", "show", f"{old}:.worktreeinclude"], GIT_TIMEOUT_S, cwd=ctx.main)
    text = res.stdout if res.returncode == 0 else None
    listed_file = ctx.main / ".worktreeinclude"
    if text is None and listed_file.is_file() and not listed_file.is_symlink():
        ignored = _run(
            ["git", "check-ignore", "-q", ".worktreeinclude"], GIT_TIMEOUT_S, cwd=ctx.main
        )
        if ignored.returncode == 0:
            try:
                text = listed_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                text = None
    if text is None:
        # no sha in the text: the base moves between rebuilds, and the caller dedups by text
        return (
            "`.worktreeinclude` is neither tracked at the base nor an ignored regular file in the "
            "main checkout — nothing copied into the build tree"
        )
    main = ctx.main.resolve()
    for line in text.splitlines():
        rel = line.strip()
        if not rel or rel.startswith("#"):
            continue
        listed = main / rel
        target = listed.resolve()
        if listed.is_symlink() or not target.is_relative_to(main) or target == main:
            continue  # a symlink, an absolute path or `..`: never read outside the checkout
        # walk the LISTED path, never the resolved one, so each copy lands where it was listed
        files = (
            [listed] if listed.is_file() else (sorted(listed.rglob("*")) if listed.is_dir() else [])
        )
        for f in files:
            if f.is_symlink() or not f.is_file() or not f.resolve().is_relative_to(main):
                continue
            dst = wt / f.relative_to(main)
            if dst.exists():
                continue  # tracked in the merged tree: the merge's copy wins
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
            except OSError:
                continue  # a tracked FILE where the list has a directory: the merge's tree wins
    return None


def _owner_tests(ctx: _Ctx, wt: Path, old: str, merged: list[tuple[str, str]]) -> str:
    """(c): the OWNER's command — ``.fabrik/merge-tests`` read from the BASE, never the branch —
    with the throwaway's ``src`` first on ``PYTHONPATH`` (a contract owner commands rely on; one
    whose ``src`` holds a stdlib-named package runs ``env -u PYTHONPATH …`` itself). Else pytest
    over the merged ``tests/`` files the diff touched, under the main checkout's ``.venv`` python
    when it has one, the merged ``src`` placed after the stdlib by the shim above. A red test
    refuses. Both legs first get the base's ``.worktreeinclude`` set (``_copy_worktree_include``),
    and both run with ``FABRIK_MERGE_CHECK=1`` (``_MERGE_CHECK_ENV``).

    The refusal carries what ``_base_alone`` needs to run the same leg on the base by itself
    (``base_alone``), or why it must not (``base_alone_skip``: a run that timed out or was killed
    would only hold the merge lock as long again) — W-c751bca6."""
    note = _copy_worktree_include(ctx, wt, old)
    if note and note not in ctx.notes:  # once per merge: this runs per rebuild and per catch-up
        ctx.notes.append(note)
    script = _base_merge_tests(ctx, old)
    ctx.full_leg = _declared_leg(script)
    ctx.leg_mem = _declared_mem(script)
    # said in the leg's own verdict, so the merge reply, a pretest and a queue child all carry it
    mem_note = (
        "; NOTE: the base's .fabrik/merge-tests has a merge-test-mem line outside the grammar "
        "(`# merge-test-mem: <n>M|<n>G` alone on its line) — ignored, capped_run's default ceiling holds"
        if _mem_lines_ignored(script)
        else ""
    )
    touched: list[str] = []
    if not script:
        touched = [
            p
            for status, p in merged
            if status != "D"
            and p.startswith("tests/")
            and Path(p).name.startswith("test_")
            and p.endswith(".py")
        ]
        if not touched:
            return "no owner tests ran (no .fabrik/merge-tests, no touched tests/)"
    ignored = ""
    if script:
        pretested, ignored = _pretested(ctx, wt, script)
        if pretested:
            return pretested
        deferred = _after_merge_due(ctx, script)
        if deferred:
            ctx.tests_deferred = True
            return deferred
    spent = (
        f"the owner-test budget of this run ({MERGE_TEST_BUDGET_S}s) ran out during the leg "
        f"(stopped at {{}}s) — not a test verdict"
    )
    try:
        run, label = _run_owner_leg(ctx, wt, script, touched)
    except TimedOutError as exc:
        if ctx.leg_limit < ctx.full_leg:
            raise BudgetSpentError(spent.format(ctx.leg_limit)) from exc
        exc.base_old = old  # type: ignore[attr-defined]
        exc.base_alone_skip = "the merged run timed out"  # type: ignore[attr-defined]
        raise
    # a 124 is the budget's only when the leg ran its whole shortened limit: the owner's own
    # `timeout` (or a plain `exit 124`) inside the leg exits sooner and stays a red
    shortened = ctx.leg_limit < ctx.full_leg
    if run.returncode == 124 and shortened and time.monotonic() - ctx.leg_t0 >= ctx.leg_limit:
        raise BudgetSpentError(spent.format(ctx.leg_limit))  # no base_old: no base-alone run
    if run.returncode != 0:
        verdict = _capped_verdict(run.returncode, run.stderr)
        tail = verdict or " ".join((run.stdout + run.stderr).strip().splitlines()[-3:])
        why = f"; NOTE: {note}" if note else ""
        red = RefusedError(
            f"owner tests red ({label}, exit {run.returncode}): {tail}{why}{mem_note}"
        )
        red.base_old = old  # type: ignore[attr-defined]
        red.base_alone = {"script": script, "touched": touched}  # type: ignore[attr-defined]
        if run.returncode in _KILLED_EXITS:
            # callers wrap this in their own "(…)" and the verdict carries one: no third level
            red.base_alone_skip = (  # type: ignore[attr-defined]
                f"the merged run timed out or was killed, exit {run.returncode}"
                + (f" — {verdict}" if verdict else "")
            )
        raise red
    return f"{label}: green{ignored}{mem_note}"


# --- request --pretest: the owner tests run ONCE per change (W-1fb11ec8) ----------------------
# A builder ran the suite before requesting and the merge ran it again under the serial lock
# (web-ecommerce-factory 2026-10-24: 18-28 min each). The requester's run of the merge the owner
# would build is recorded by its merged TREE, so a moved base cannot match a stale record.
PRETEST_DIR = (
    "pretest"  # a subdirectory: `_resume_stranded`/`_parked` glob only `fabrik-merge/*.json`
)
_TREE_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
# The paths a base move may change without a re-test: the three ledgers no repo's tests read as input
# (wef's tests/scripts/test_cross_repo_cites.py globs docs/*.md and INDEX.md but excludes exactly
# these) and work-item files. Narrower than LEDGERS on purpose: INDEX.md and STRATEGIC_BACKLOG are
# test inputs there. Measured on wef's last 21 merges: 15 match with this set, 16 with LEDGERS.
PRETEST_SKIP = frozenset({"CHANGELOG.md", DECISIONS, "docs/LESSONS_LEARNT.md"})
# A pretest leg shorter than this is re-run rather than trusted: a suite worth skipping takes minutes
# (wef 18-28 min), and a leg that "passed" in seconds is a stub runner or an empty selection.
PRETEST_FLOOR_S = LEG_FLOOR_S


def _pretest_path(records: Path, head: str) -> Path:
    return records / PRETEST_DIR / f"{head}.json"


def _script_sha(script: str) -> str:
    return hashlib.sha256(script.encode("utf-8")).hexdigest()


def _runner_sha() -> str:
    """This running script's own bytes: a record written by a ``merge_request.py`` other than the
    one the owner runs (a branch that edits it runs its own copy) is never trusted."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _pretested(ctx: _Ctx, wt: Path, script: str) -> tuple[str, str]:
    """``(summary, "")`` when the requester's pretest ran this base's ``script`` green on a tree that
    differs from the merged one only in PRETEST_SKIP paths and work items, else ``("", why)`` — ``why`` empty
    when there is no record, else ``"; pretest record ignored (<why>)"`` for the reply. COBRA: the
    cheapest pass is a record written by hand; it must still name this exact tree, and the reply
    names the trusted run, so the owner sees the skip."""
    if ctx.pretesting:
        return "", ""  # a pretest runs the leg it records; it never skips it
    second = _run(["git", "rev-parse", "-q", "--verify", "HEAD^2"], GIT_TIMEOUT_S, cwd=wt)
    head = second.stdout.strip()
    if second.returncode or not head:
        return "", ""  # not a two-parent merge (or no request head): nothing to look up
    path = _pretest_path(
        ctx.common / "fabrik-merge", head
    )  # never the pretest ctx's redirected records
    if not path.is_file():
        return "", ""

    def ignored(why: str) -> tuple[str, str]:
        return "", f"; pretest record ignored ({why})"

    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return ignored(f"unreadable: {' '.join(str(exc).split())}")
    if not isinstance(rec, dict) or rec.get("green") is not True:
        return ignored("not a green record")
    if rec.get("head") != head:
        return ignored("it names another head")
    tree = rec.get("tree")
    if not isinstance(tree, str) or not _TREE_RE.fullmatch(tree):
        return ignored("no tree id")
    if rec.get("script_sha256") != _script_sha(script):
        return ignored("the base's .fabrik/merge-tests changed since")
    if rec.get("runner_sha256") != _runner_sha():
        return ignored("written by a merge_request.py other than this one")
    seconds = rec.get("seconds")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < PRETEST_FLOOR_S
    ):
        # a suite that finished in under a minute (a stub runner, FABRIK_CAPPED_RUN=/bin/true) is
        # cheap to re-run and is not trusted as the change's one run
        return ignored(f"its leg ran {seconds!r}s, under {PRETEST_FLOOR_S}s")
    diff = _run(
        ["git", "diff", "--name-only", "-z", "--no-renames", tree, "HEAD^{tree}"],
        GIT_TIMEOUT_S,
        cwd=wt,
    )
    if diff.returncode:
        return ignored("its tree is not in this repo")
    paths = [p for p in diff.stdout.split("\0") if p]
    code = [p for p in paths if p not in PRETEST_SKIP and not _WORK_ITEM_RE.fullmatch(p)]
    if code:
        return ignored(f"{len(code)} non-ledger path(s) differ, e.g. {code[0]}")
    return (
        f".fabrik/merge-tests (base copy): green on the requester's pretest "
        f"(tree {tree[:12]}, {int(seconds)}s, {len(paths)} ledger path(s) differ)",
        "",
    )


def _pretest(main: Path, common: Path, owner: str, base: str, branch: str, head: str) -> str:
    """``request --pretest``: step (c)'s owner tests on the merge the owner would build, in a
    throwaway at the LOCAL base (the ref ``merge`` reads, shared through the common dir). Green
    writes ``fabrik-merge/pretest/<head>.json``; any other end removes it and raises, so nothing is
    sent. Returns the line to print."""
    ctx = _Ctx(main, common, owner)
    ctx.records = ctx.records / PRETEST_DIR  # the throwaway's bookkeeping lands beside the record
    ctx.pretesting = True
    old = _rev(main, HEADS + base)
    if not old:
        raise RefusedError(f"--pretest: the local base {base} does not exist")
    script = _base_merge_tests(ctx, old)
    if not script:
        return f"--pretest: nothing to pretest (the base {base} has no .fabrik/merge-tests)"
    _sweep_pretests(ctx)
    path = ctx.records / f"{head}.json"
    path.unlink(missing_ok=True)
    # the throwaway's bookkeeping is this RUN's file (pid + start, so a killed run's leftovers are
    # swept); a concurrent pretest of the same head has its own and never deletes this one
    rec: dict = {"id": f"{head}.run-{os.getpid()}", **_claimer()}
    killed = (
        "the pretest timed out or was killed ({}) — not a test verdict; run it again, "
        "or request without --pretest"
    )
    saved = os.environ.get("FABRIK_MERGE_TESTS_RECORDS")
    try:
        with tempfile.TemporaryDirectory(prefix="merge-pretest-records-") as private:
            os.environ["FABRIK_MERGE_TESTS_RECORDS"] = private
            with _throwaway(ctx, rec, old, _PRETEST_PREFIX) as wt:
                new = _build(ctx, wt, head, f"pretest {branch}", base)
                summary, seconds = _pretest_leg(ctx, wt, old, new, killed)
                tree = _gitc(wt, "rev-parse", f"{new}^{{tree}}").strip()
        (ctx.records / f"{rec['id']}.json").unlink(missing_ok=True)
        _save(ctx, _pretest_record(head, old, tree, script, seconds, _runner_sha()))
    except BaseException:
        path.unlink(missing_ok=True)
        (ctx.records / f"{head}.run-{os.getpid()}.json").unlink(missing_ok=True)
        raise
    finally:
        if saved is None:
            os.environ.pop("FABRIK_MERGE_TESTS_RECORDS", None)
        else:
            os.environ["FABRIK_MERGE_TESTS_RECORDS"] = saved
    return f"--pretest: {summary} in {seconds}s on {base} at {old[:12]} (tree {tree[:12]})"


def _pretest_leg(ctx: _Ctx, wt: Path, old: str, new: str, killed: str) -> tuple[str, int]:
    """The owner tests on ``new`` (checked out in ``wt``, built on ``old``), read from ``old`` as the
    locked merge reads them from its base. The one leg both pretest writers run — ``request
    --pretest`` and ``merge --queue``'s children — so their records cannot drift. A timeout or a
    kill is "not a test verdict" (``killed``, formatted with the cause); a red raises as
    ``_owner_tests`` does. Returns (summary, seconds)."""
    t0 = time.monotonic()
    try:
        summary = _owner_tests(ctx, wt, old, _merged_paths(ctx.main, old, new))
    except TimedOutError as exc:
        raise RefusedError(killed.format("the outer bound")) from exc
    except RefusedError as exc:
        skip = getattr(exc, "base_alone_skip", None)
        if skip:
            raise RefusedError(killed.format(skip)) from exc
        raise
    return summary, round(time.monotonic() - t0)


def _pretest_record(
    head: str, old: str, tree: str, script: str, seconds: int, runner: str, **extra
) -> dict:
    """The green record ``_pretested`` trusts; ``extra`` keys (``stacked_on``) it never reads."""
    return {
        "id": head,
        "head": head,
        "base_old": old,
        "tree": tree,
        "script_sha256": _script_sha(script),
        "runner_sha256": runner,
        "seconds": seconds,
        "green": True,
        "at": _now(),
        **extra,
    }


def _sweep_pretests(ctx: _Ctx, base_tip: str = "") -> None:
    """A pretest SIGKILLed mid-leg leaves its throwaway registered and its bookkeeping record (the
    owner's sweep never takes ``fabrik-pretest-`` dirs, so nothing else would): remove each whose
    process is gone. A green record carries no ``worktree`` and is kept — unless ``base_tip`` is
    given and its head is already in it: that request merged, and nothing reads the record again
    (``merge --queue`` writes one per request, W-0c8c43f1)."""
    for path in sorted(ctx.records.glob("*.json")) if ctx.records.is_dir() else []:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(rec, dict):
            continue
        head = rec.get("head")
        if (
            base_tip
            and rec.get("green") is True
            and isinstance(head, str)
            and _SHA_RE.fullmatch(head)
            and _is_ancestor(ctx.main, head, base_tip)
        ):
            path.unlink(missing_ok=True)
            continue
        if not isinstance(rec.get("worktree"), str):
            continue
        if rec.get("start") is None or not _stranded(rec):
            continue  # a live pretest by another session, or one whose liveness cannot be read
        _remove_throwaway(ctx, Path(rec["worktree"]), _PRETEST_DIR_RE)
        path.unlink(missing_ok=True)


# capped_run.sh's own verdicts: 124 its time limit, 137 its memory ceiling (scripts/capped_run.sh)
_KILLED_EXITS = (124, 137)


def _capped_verdict(rc: int, stderr: str) -> str:
    """capped_run's own verdict for a killed leg, cut before its " — <argv>" part (the argv of a
    script leg is the multi-line script, which would otherwise fill a 3-line tail): for 137 its
    ``killed at the memory ceiling (<mem> per run, <max> for <slice>)`` line, for 124 its ``stopped at
    the <n>s time limit`` line — the LAST such line, since capped_run prints its own after the leg
    ends and a nested run may print one earlier (W-e64a7b8e). A 137 with none is a SIGKILL inside the
    leg, said so; any other case, or a 124 with none, is "" and the caller keeps its tail."""
    prefix = {137: _CEILING_KILL, 124: _TIME_KILL}.get(rc)
    if prefix is None:
        return ""
    for line in reversed(stderr.splitlines()):
        if line.startswith(prefix):
            return line.split(" — ", 1)[0].rstrip()
    if rc == 137:
        return "a SIGKILL inside the leg; capped_run reported no memory-ceiling kill"
    return ""


def _base_merge_tests(ctx: _Ctx, old: str) -> str:
    """The base's ``.fabrik/merge-tests``, or "" when the base has none."""
    res = _run(["git", "show", f"{old}:.fabrik/merge-tests"], GIT_TIMEOUT_S, cwd=ctx.main)
    return res.stdout if res.returncode == 0 and res.stdout.strip() else ""


def _leg_env(ctx: _Ctx, env: dict) -> dict:
    """The leg's env with ``FABRIK_MERGE_TESTS_BASE`` set only by the after-merge runner
    (``ctx.after_base``): one inherited from a caller's shell would move a normal merge's base."""
    env = {k: v for k, v in env.items() if k != "FABRIK_MERGE_TESTS_BASE"}
    if ctx.after_base:
        env["FABRIK_MERGE_TESTS_BASE"] = ctx.after_base
    return env


# --- box-wide leg admission (W-fbd1d4b9 part c, D-1381) -----------------------------------------
# Every repo's merge legs share capped_run.sh's ONE test slice (FABRIK_TEST_SLICE_MAX, 12G) and the box's
# cores. Measured 2026-10-29..31 from the user journal: of the 242 minutes any of 53 legs ran, two or more
# ran together for 189 (up to six — hub pretests, queue children and web-ecommerce-factory's legs); hub
# legs beside 1.5+ others took a median 10.9 min, against 1.05 alone. So a leg starts only when the
# DECLARED memory of the legs already running plus its own fits the slice: an 8G hub leg runs beside one
# 4G leg, never beside another 8G one. Each running leg holds a flock on its own lease file under
# LEG_ADMIT_DIR (box-wide, every repo); a holder that dies drops its lock with its process, so a lease
# nobody holds is stale by construction and is deleted. The wait sits OUTSIDE the leg's budget clock
# (`ctx.test_deadline` moves by the seconds waited) and is bounded by LEG_ADMIT_WAIT_S, after which the
# leg starts anyway and says so — a stuck holder must not stall every merge on the box (fail-open, said).
# The allowance is per INVOCATION, so one merge run's rebuilds, catch-up and base-alone legs wait at most
# LEG_ADMIT_WAIT_S together, which LANDING_WORST_S and the documented wrappers count once.
# Cobra (D-253): the cheapest way past admission is a smaller declared `# merge-test-mem:`; capped_run
# kills a leg past its own declaration at that ceiling, so under-declaring trades the wait for a red.
LEG_ADMIT_WAIT_S = 900  # per INVOCATION (ctx.admit_spent): every leg of one merge run shares it
LEG_ADMIT_POLL_S = 5.0
_LEASE_FDS: dict[int, Path] = {}  # this process's held lease fds; a forked child closes them


def _drop_inherited_leases() -> None:
    """In a forked child: close the inherited lease fds, so the lease ends with the PARENT's leg."""
    for fd in list(_LEASE_FDS):
        with contextlib.suppress(OSError):
            os.close(fd)
    _LEASE_FDS.clear()


os.register_at_fork(after_in_child=_drop_inherited_leases)


def _admit_dir() -> Path:
    return Path(os.environ.get("FABRIK_MERGE_LEG_DIR") or Path.home() / ".claude/state/merge-legs")


def _size_mib(value: str | None, default: int) -> int:
    """capped_run.sh's size grammar (`<n>K|M|G`) in MiB; ``default`` for anything else."""
    m = re.fullmatch(r"([1-9][0-9]{0,8})([KMG])", (value or "").strip())
    if not m:
        return default
    n = int(m.group(1))
    return max(1, n // 1024) if m.group(2) == "K" else n * (1024 if m.group(2) == "G" else 1)


def _held_leases(adir: Path) -> list[dict]:
    """The leases a live leg holds; a lease file nobody holds (its leg died) is deleted. Called
    under the admission lock, so no lease is half-written while it reads."""
    held = []
    for path in sorted(adir.glob("lease-*.json")):
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            continue
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                try:
                    rec = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    rec = {}
                mib = rec.get("mib") if isinstance(rec, dict) else None
                held.append(rec if isinstance(mib, int) and mib > 0 else {"mib": LEG_MEM_MAX_MIB})
                continue
            with contextlib.suppress(OSError):  # one undeletable entry must not disable admission
                path.unlink(missing_ok=True)  # nobody holds it: its leg is gone
        finally:
            os.close(fd)
    return held


@contextlib.contextmanager
def _admitted(ctx: _Ctx):
    """Hold a box-wide lease for one leg; yields the note the leg's label carries ("" when no wait)."""
    mine = _size_mib(ctx.leg_mem, _size_mib(os.environ.get("FABRIK_TEST_MEM_MAX"), 4096))
    cap = _size_mib(os.environ.get("FABRIK_TEST_SLICE_MAX"), 12288)
    adir = _admit_dir()
    t0 = time.monotonic()
    note = ""
    lease_fd = -1
    lease = adir / f"lease-{os.getpid()}-{secrets.token_hex(4)}.json"
    try:
        adir.mkdir(parents=True, exist_ok=True)
        while lease_fd < 0:
            over = ctx.admit_spent + time.monotonic() - t0 >= LEG_ADMIT_WAIT_S
            lock_fd = os.open(adir / "admission.lock", os.O_RDWR | os.O_CREAT, 0o644)
            try:
                try:  # never blocking: a hung lock holder must not outlast the bounded wait
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    if over:
                        note = (
                            f"; admission: its lock was held past the {LEG_ADMIT_WAIT_S}s wait, "
                            "started anyway"
                        )
                        break
                else:
                    held = _held_leases(adir)
                    used = sum(int(r["mib"]) for r in held)
                    if not held or used + mine <= cap or over:
                        lease_fd = os.open(lease, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
                        _LEASE_FDS[lease_fd] = lease
                        fcntl.flock(lease_fd, fcntl.LOCK_EX)
                        rec = {"mib": mine, "pid": os.getpid(), "repo": str(ctx.main)}
                        os.write(lease_fd, json.dumps(rec).encode())
                        if over and held and used + mine > cap:
                            note = (
                                f"; admission: started after the {LEG_ADMIT_WAIT_S}s wait with "
                                f"{len(held)} leg(s) holding {used} MiB of the {cap} MiB test slice"
                            )
                        break
            finally:
                os.close(lock_fd)
            time.sleep(LEG_ADMIT_POLL_S)
    except OSError as exc:  # no admission is not a red: the leg runs, and says it ran unadmitted
        note = f"; admission: not checked ({exc.strerror or exc})"
    except BaseException:  # an interrupt before the leg starts must not keep the slot
        _release_lease(lease_fd, lease)
        raise
    waited = time.monotonic() - t0
    ctx.admit_spent += waited
    ctx.test_deadline += waited  # the wait is outside the leg's budget clock
    if waited >= 1 and not note:
        note = f"; admitted after a {int(waited)}s wait for the box's test slice"
    try:
        yield note
    finally:
        _release_lease(lease_fd, lease)


def _release_lease(lease_fd: int, lease: Path) -> None:
    if lease_fd >= 0 and _LEASE_FDS.pop(lease_fd, None) is not None:
        lease.unlink(missing_ok=True)
        os.close(lease_fd)


def _run_owner_leg(
    ctx: _Ctx, wt: Path, script: str, touched: list[str]
) -> tuple[subprocess.CompletedProcess, str]:
    """One run of the owner's tests in ``wt``, admitted box-wide first (``_admitted``): ``script``
    (the base's merge-tests) when given, else pytest over ``touched``. Returns the finished process and
    its label. Its limit is ``_leg_timeout``'s, kept on ``ctx.leg_limit`` so the caller can tell a spent
    budget from a red."""
    with _admitted(ctx) as note:
        run, label = _run_owner_leg_admitted(ctx, wt, script, touched)
    return run, label + note


def _run_owner_leg_admitted(
    ctx: _Ctx, wt: Path, script: str, touched: list[str]
) -> tuple[subprocess.CompletedProcess, str]:
    limit = ctx.leg_limit = _leg_timeout(ctx)
    ctx.leg_t0 = time.monotonic()  # after admission: a 124 is measured from the leg's own start
    if script:
        pythonpath = os.pathsep.join(
            p for p in (str(wt / "src"), os.environ.get("PYTHONPATH", "")) if p
        )
        env = _leg_env(ctx, {**os.environ, **_MERGE_CHECK_ENV, "PYTHONPATH": pythonpath})
        argv, label = ["sh", "-e", "-c", script], ".fabrik/merge-tests (base copy)"
        # the outer bound only catches a runner that itself hangs; the runner stops the tests first
        return _run(_capped(argv, limit, ctx.leg_mem), limit + 60, cwd=wt, env=env), label
    venv = ctx.main / ".venv" / "bin" / "python"
    py = str(venv) if os.access(venv, os.X_OK) else sys.executable
    label = f"pytest {' '.join(touched)} under {py}"
    with tempfile.TemporaryDirectory(prefix="merge-shim-") as shim:
        Path(shim, "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
        env = _leg_env(ctx, _fallback_env(wt, Path(shim)))
        run = _run(
            _capped([py, "-m", "pytest", "-q", *touched], limit),
            limit + 60,
            cwd=wt,
            env=env,
        )
    return run, label


def _base_alone(ctx: _Ctx, rec: dict, old: str, red: RefusedError) -> str:
    """The owner-tests refusal's verdict on the BASE by itself (W-c751bca6): the same leg, once,
    in a fresh throwaway at ``old`` with nothing merged. "owner tests red" read the same for a red
    base and a red branch, so the owner could not tell a request worth retrying from one the
    requester must change. One run is weak evidence (a flaky test reads either way), so the
    wording hedges. Never raises: a check that cannot run is the "not checked" clause, so it can
    never change the refusal or the exit code."""
    skip = getattr(red, "base_alone_skip", None)
    if skip:
        return f"; on base alone: not checked ({skip})"
    spec = getattr(red, "base_alone", None) or {}
    try:
        with _throwaway(ctx, rec, old) as wt:
            _copy_worktree_include(ctx, wt, old)
            touched = [p for p in spec.get("touched", []) if (wt / p).is_file()]
            if not spec.get("script") and not touched:
                return "; on base alone: not checked (every touched test file is new in the branch)"
            run, _label = _run_owner_leg(ctx, wt, spec.get("script", ""), touched)
    except Exception as exc:  # noqa: BLE001 — a verdict that cannot be reached is said, never raised
        return (
            f"; on base alone: not checked (the check could not run: {' '.join(str(exc).split())})"
        )
    if run.returncode == 0:
        return (
            "; on base alone (one run): green — the failure needs the branch's change (or is flaky)"
        )
    if run.returncode in _KILLED_EXITS:
        verdict = _capped_verdict(run.returncode, run.stderr)
        said = f"exit {run.returncode}: {verdict}" if verdict else f"exit {run.returncode}"
        return f"; on base alone: not checked (the base run timed out or was killed, {said})"
    tail = " ".join((run.stdout + run.stderr).strip().splitlines()[-3:])
    said = f"exit {run.returncode}: {tail}" if tail else f"exit {run.returncode}"
    return (
        f"; on base alone (one run): red too ({said}) — likely a base-side "
        f"fault: fix the base, then `merge_request.py retry {rec['id']}`"
    )


def _merge_into_base(
    ctx: _Ctx, rec: dict, other: str, message: str, *, catch_up: bool
) -> tuple[str, str, dict, str, bool]:
    """(a)-(d) for one merge of ``other`` into the local base: build, preflight, tests, re-hash,
    CAS — rebuilt IN FULL up to MAX_REBUILDS times when a merged path changed, the base moved,
    or the main checkout moved onto or off the base after the preflight (O8). Returns (old, new,
    snapshot, tests summary, preflighted); refuses with nothing outside the throwaway changed."""
    base = rec["base"]
    last = ""
    for attempt in range(MAX_REBUILDS + 1):
        old = _rev(ctx.main, HEADS + base)
        if not old:
            raise RefusedError(f"local base {base} does not exist")
        with _throwaway(ctx, rec, old) as wt:
            new = _build(ctx, wt, other, message, base)
            on_phase("after-build")
            merged, snap, on_base = _preflight(ctx, base, old, new)
            # per attempt: a rebuild may run the leg the last attempt deferred; a catch-up never
            # defers, since no owed entry would ever name its merge (review r1 A-6, A-8)
            ctx.tests_deferred = False
            ctx.catching_up = catch_up
            tests = _owner_tests(ctx, wt, old, merged)
            if not catch_up:
                # saved with the pre-CAS record, so a crash before the post-CAS save still owes the
                # after-merge run on resume (review r1 A-7)
                rec.update(phase="built", building=new, tests_after_merge=ctx.tests_deferred)
                _save(ctx, rec)
            on_phase("before-cas")
            if _main_on(ctx, base) != on_base:
                last = "the main checkout moved onto or off the base after the preflight"
                ctx.notes.append(f"(d) attempt {attempt + 1}: {last} — back to (a)")
                continue
            if _snapshot(ctx.main, list(snap)) != snap:
                last = "a merged path changed in the main checkout after the snapshot"
                ctx.notes.append(f"(d) attempt {attempt + 1}: {last} — back to (a)")
                continue
            res = _run(
                # the reflog takes the subject: update-ref folds the trailer lines into one line
                [
                    "git",
                    "update-ref",
                    "-m",
                    f"merge_request: {message.splitlines()[0]}",
                    HEADS + base,
                    new,
                    old,
                ],
                GIT_TIMEOUT_S,
                cwd=ctx.main,
            )
            if res.returncode == 0:
                return old, new, snap, tests, on_base
            last = f"the local base {base} moved during the build"
            ctx.notes.append(f"(d) attempt {attempt + 1}: {last} — rebuilding")
    raise RefusedError(f"(d) {last} on {MAX_REBUILDS + 1} builds — refused, base untouched")


# --- (e) carry ------------------------------------------------------------------------------
def _carry(
    ctx: _Ctx, base: str, old: str, new: str, snap: dict | None
) -> tuple[list[str], list[str]]:
    """Bring the main checkout's merged paths from ``old`` to ``new``, IDEMPOTENTLY: a path whose
    index already holds ``new`` (or HEAD's blob) is done. A path is NOT CARRIED — the owner's
    copy kept, its index entry realigned to the merge, and the path listed for the reply — when
    its working copy changed since the (a) snapshot (``snap``; None on a resume without one) or
    since the carry's own hash (re-taken per path IMMEDIATELY before writing it), when its
    ledger 3-way carry conflicts or makes a DECISIONS id collide, or when it is a dirty
    NON-ledger path. A dirty LEDGER is 3-way merged and written whether or not a snapshot exists
    (with ``snap=None`` — a resume of a head already in base — the 3-way keeps the owner's WIP
    on top of the merge, the safe outcome). Returns (carried paths, not-carried lines)."""
    if not _main_on(ctx, base):
        return [], [f"(every merged path): the main checkout is not on {base} — nothing carried"]
    merged = _merged_paths(ctx.main, old, new)
    paths = [p for _, p in merged]
    head = _gitc(ctx.main, "rev-parse", "HEAD").strip()
    now = _snapshot(ctx.main, paths)
    old_b = _tree_blobs(ctx.main, old, paths)
    new_b = _tree_blobs(ctx.main, new, paths)
    head_b = new_b if head == new else _tree_blobs(ctx.main, head, paths)
    carried: list[str] = []
    reset: list[str] = []
    skipped: list[str] = []

    def keep(path: str, why: str) -> None:
        skipped.append(
            f"{path}: {why} — your copy is kept and its index entry is the merge; a later "
            "`git commit -a` would revert the merge there"
        )

    for _, path in merged:
        wt, idx = now[path]
        if idx == new_b.get(path) or (idx == head_b.get(path) and head != new):
            continue  # already carried, or consistent with a later base
        if idx != old_b.get(path):
            skipped.append(f"{path}: the index holds a staged change — left as is, index untouched")
            continue
        reset.append(path)
        if snap is not None and path in snap and wt != snap[path][0]:
            keep(path, "edited in the main checkout after the snapshot")
            continue
        text = None
        if wt == old_b.get(path):
            pass  # clean: checked out (or removed) below
        elif path in LEDGERS and isinstance(wt, str) and wt != "dir" and path in new_b:
            try:
                current = _decode((ctx.main / path).read_bytes())
                text = _merge3(
                    path, current, _blob(ctx.main, old_b[path]), _blob(ctx.main, new_b[path])
                )
            except RefusedError as exc:
                keep(path, f"its 3-way carry conflicts ({exc})")
                continue
            if path == DECISIONS:
                clash = _dup_ids(text) - _dup_ids(current) - _dup_ids(_blob(ctx.main, new_b[path]))
                if clash:
                    ids = ", ".join(f"D-{n}" for n in sorted(clash, key=int))
                    keep(path, f"{ids} collides between your WIP and the merge — re-mint yours")
                    continue
        else:
            keep(path, "dirty in the main checkout")
            continue
        # O4: re-hash THIS path immediately before writing it. The residual window is the few
        # syscalls between this hash and the write below; an editor saving inside it is not
        # detectable without a lock the owner's editor does not take.
        if _worktree_hashes(ctx.main, [path]).get(path) != wt:
            keep(path, "edited in the main checkout during the carry")
            continue
        target = ctx.main / path
        if text is not None:
            tmp = target.with_name(f".{target.name}.fabrik-merge.{os.getpid()}")
            tmp.write_bytes(_encode(text))
            shutil.copymode(target, tmp)
            os.replace(tmp, target)
        elif path in new_b:
            _gitc(ctx.main, "checkout", new, "--", path)
        else:
            with contextlib.suppress(FileNotFoundError):
                target.unlink()
            parent = target.parent
            while parent != ctx.main and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()  # a directory the merge emptied goes with its last file
                parent = parent.parent
        carried.append(path)
    if reset:
        _gitc(ctx.main, "reset", "-q", new, "--", *reset)
    return sorted(carried), skipped


# --- (f) push, (g) sync, (h) reply + ack ---------------------------------------------------
def _push(ctx: _Ctx, rec: dict, remote: str) -> tuple[bool, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    ref = HEADS + rec["base"]
    res = _run(
        ["git", "push", "--porcelain", remote, f"{ref}:{ref}"],
        PUSH_TIMEOUT_S,
        cwd=ctx.main,
        env=env,
    )
    return res.returncode == 0, (res.stderr.strip() or res.stdout.strip())


_MISSING_REF = "couldn't find remote ref"


def _fetch(ctx: _Ctx, remote: str, refspec: str, what: str) -> None:
    """One remote fetch. A missing ref on a reachable remote is a ``RefusedError``; a timeout or
    any other failure (DNS, transport, a gone path — git exits 128 for all of them) is an
    ``UnreachableError``, which defers rather than refuses."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}  # C: the classified stderr
    try:
        res = _run(["git", "fetch", "-q", remote, refspec], REMOTE_TIMEOUT_S, cwd=ctx.main, env=env)
    except TimedOutError as exc:
        raise UnreachableError(str(exc)) from exc
    if res.returncode != 0:
        why = f"git fetch {remote} {what} failed: {res.stderr.strip() or res.returncode}"
        if _MISSING_REF in res.stderr:
            raise RefusedError(why)
        raise UnreachableError(why)


def _fetch_base(ctx: _Ctx, remote: str, base: str) -> str:
    track = f"refs/remotes/{remote}/{base}"
    _fetch(ctx, remote, f"+{HEADS}{base}:{track}", base)
    sha = _rev(ctx.main, track)
    if not sha:
        raise RefusedError(f"{remote} has no {HEADS}{base}")
    return sha


def _sync_filter(text: str) -> str:
    """The ``governance-sync`` hook's ``files:`` regex, read from ``.pre-commit-config.yaml``
    text (stdlib-only: the one key of the one hook, single- or double-quoted)."""
    in_hook = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- id:"):
            in_hook = s[len("- id:") :].strip() == "governance-sync"
        elif in_hook and s.startswith("files:"):
            value = s[len("files:") :].strip()
            if len(value) >= 2 and value[0] == value[-1] == "'":
                return value[1:-1].replace("''", "'")
            if len(value) >= 2 and value[0] == value[-1] == '"':
                return json.loads(value)
            return value
    return ""


def _sync(ctx: _Ctx, rec: dict) -> str:
    """(g): in the HUB only, OWE the fleet sync when the re-derived merged file list matches the
    governance-sync filter (read from the merged base, never hard-coded), then kick the background
    runner — the sync itself runs OUTSIDE the merge lock (W-4f4ac600, the block comment below this
    function). Every hub call kicks, so a debt a killed run left is run by the next landing."""
    if ctx.main.resolve() != HUB_CHECKOUT.resolve():
        return "sync: not the hub — none owed"
    merge = rec["merge_sha"]
    files = [
        p
        for p in _gitc(ctx.main, "diff", "--name-only", "-z", f"{merge}^1", merge).split("\0")
        if p
    ]
    res = _run(["git", "show", f"{merge}:.pre-commit-config.yaml"], GIT_TIMEOUT_S, cwd=ctx.main)
    pattern = _sync_filter(res.stdout) if res.returncode == 0 else ""
    hits: list[str] = []
    if not pattern:
        line = (
            "sync: NOT RUN — the governance-sync files: filter is unreadable or empty; run "
            "scripts/sync_enforcement_to_projects.py --force yourself"
        )
    else:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            line = f"sync: NOT RUN — the governance-sync filter does not compile ({exc})"
        else:
            hits = [p for p in files if rx.search(p)]
            line = "sync: no governance-sync path merged — none owed"
    state = ctx.records
    try:
        if hits:
            _owe_sync(state, f"{merge} {len(hits)} path(s), request {rec['id']}")
        kicked = _kick_sync(ctx.main, state)
    except OSError as exc:  # the push already landed: a sync we cannot owe is reported, not raised
        return (
            f"sync: FAILED to owe or start ({exc}) — run "
            "scripts/sync_enforcement_to_projects.py --force"
        )
    if not hits:
        return line if kicked is None else f"{line}; {kicked}"
    line = (
        f"sync: owed for {len(hits)} governance-sync path(s) — runs outside the merge lock "
        f"(log {state / SYNC_LOG})"
    )
    return line if kicked is None else f"{line}; {kicked}"


# --- (g) the hub's governance sync, OUTSIDE the merge lock (W-4f4ac600) -----------------------
# The sync ran inside the lock and held every landing that owed one ~4 min (01M64FJ6AT: push
# 00:59:53, reply 01:04:04) — and `merge --queue` lands one `merge()` at a time, so the queue waited
# it out too. Now a landing OWES it (one O_APPEND line in SYNC_OWED) and KICKS a detached runner
# (`merge_request.py sync-runner`): it takes SYNC_LOCK itself — this process never opens it, so no
# queue leg forked later can inherit it — and loops while holding it: `covers` = SYNC_OWED's size
# in BYTES, read BEFORE the sync starts (every owed line is already in HEAD, and the sync ships each
# tracked file from its HEAD blob — sync_enforcement_to_projects.py `_head_source`, T12.17 — so a
# sync started after a line covers it); exit when SYNC_DONE ≥ covers, else run SYNC_ARGV and, on
# exit 0, write SYNC_DONE = max(current, covers). A line owed DURING a sync (another landing, any
# process) is covered by the runner's next turn; a failure stops the runner with the debt still
# owed and its outcome in SYNC_STATUS, and the next kick retries it. `main()` drains in a
# `finally`: it waits for THIS process's runner up to SYNC_TIMEOUT_S and prints the outcome,
# never changing the verb's exit code (a failed sync never did). SYNC_STATUS is not `*.json`: the
# record globs (`ctx.records.glob("*.json")`) would read it as a merge record.
# COBRA (D-253): the cheapest way to release the lock fast is never to run the sync; a debt stays
# owed until a sync that STARTED after it exits 0, and every drain prints what happened.
SYNC_OWED = "sync-owed.log"
SYNC_DONE = "sync-done"
SYNC_LOCK = "sync.lock"
SYNC_LOG = "sync.log"
SYNC_STATUS = "sync-status.txt"
SYNC_LOCK_WAIT_S = 2 * SYNC_TIMEOUT_S  # a runner waits out one other runner's sync and its rerun
_SYNC_RUN: dict = {}  # this process's runner: {"proc", "state", "main"} (one per process)


def _owed_size(state: Path) -> int:
    try:
        return (state / SYNC_OWED).stat().st_size
    except FileNotFoundError:
        return 0


def _done_size(state: Path) -> int:
    try:
        return int((state / SYNC_DONE).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0  # absent or unreadable: toward running the sync again


def _sync_status(state: Path) -> dict:
    try:
        raw = json.loads((state / SYNC_STATUS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):  # never mask the write's own error
            tmp.unlink(missing_ok=True)
        raise


def _owe_sync(state: Path, why: str) -> None:
    """One owed line, appended in ONE write (O_APPEND): a torn line still grows the byte count."""
    state.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {' '.join(why.split())}\n"
    fd = os.open(state / SYNC_OWED, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


# The runner's OWN scope (W-73d00b05): start_new_session leaves the process group, not the cgroup,
# and capped_run.sh's EXIT trap stops its scope when merge_request.py exits — a runner alive then
# died with its sync, and the drain's "still running in the background" was false. So the runner
# starts in a transient user scope inside the fleet slice (capped_run's own parent, fabrik-agents
# .slice), collected when it ends, its life bounded by SYNC_RUNNER_MAX_S, its memory by
# SYNC_RUNNER_MEM (capped_run's per-run default, what it had inside the merge's scope); bare where
# no such scope can start (no systemd-run, no user bus — as capped_run runs uncapped there). The
# probe is that exact start with `-- true`, kept for the process once it passes and asked again at
# the next kick while it fails (`_scope_ok`): a manager that answers yet refuses a
# property fails the probe, never the runner. Cobra (D-253): the cheapest pass is a bare start that
# the wrapper kills; the probe's own exit decides, and `sync-done` is what the graders read.
_SCOPE: dict = {}  # {"ok": bool} — this process's probe answer
SYNC_RUNNER_MEM = "4G"


def _runner_env(env: dict) -> dict:
    """The env the runner and its probe start with: XDG_RUNTIME_DIR filled from the user bus when
    absent (capped_run.sh:112-114 — cron and stripped hook envs lack it)."""
    bus = Path(f"/run/user/{os.getuid()}")
    if not env.get("XDG_RUNTIME_DIR") and (bus / "bus").is_socket():
        env = {**env, "XDG_RUNTIME_DIR": str(bus)}
    return env


def _scope_flags(unit: str) -> list[str]:
    return [
        "systemd-run",
        "--user",
        "--scope",
        "-q",
        "--collect",
        "--slice=fabrik-agents.slice",
        f"--unit={unit}-{os.getpid()}-{secrets.token_hex(4)}",
        "-p",
        f"RuntimeMaxSec={SYNC_RUNNER_MAX_S}",
        "-p",
        f"MemoryMax={SYNC_RUNNER_MEM}",
        "-p",
        "MemorySwapMax=0",
        "-p",
        "TimeoutStopSec=5",
    ]


def _scope_ok(env: dict) -> bool:
    """Only a green probe is kept: a failed one (a bus that dropped for a moment) is asked again
    at the next kick, so one blip never sends a whole queue run's runners bare."""
    if not _SCOPE.get("ok"):
        try:
            probe = subprocess.run(  # noqa: S603 — fixed argv, no shell
                [*_scope_flags("fabrik-sync-probe"), "--", "true"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=10,
                env=env,
                check=False,
            )
            _SCOPE["ok"] = probe.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _SCOPE["ok"] = False
    return _SCOPE["ok"]


def _runner_scope(argv: list[str], env: dict) -> list[str]:
    """``argv`` in its own bounded transient scope when one can start, else unchanged (bare)."""
    if not _scope_ok(env):
        return argv
    return [*_scope_flags("fabrik-sync-runner"), "--", *argv]


def _kick_sync(main: Path, state: Path) -> str | None:
    """Start the runner when a debt is owed and THIS process has none alive (a live one loops and
    covers it). Returns an evidence fragment, or None when there is nothing to say."""
    run = _SYNC_RUN.get("proc")
    if run is not None and run.poll() is None:
        return None  # its next turn covers the new debt
    if _owed_size(state) <= _done_size(state):
        return None
    note = None
    last = _sync_status(state)
    if last.get("rc") not in (None, 0):
        note = (
            f"the last background sync FAILED (exit {last.get('sync_rc', last.get('rc'))}) — "
            "retrying"
        )
    argv = [sys.executable, str(Path(__file__).resolve()), "sync-runner", "--state", str(state)]
    env = _runner_env(dict(os.environ))
    try:
        proc = subprocess.Popen(  # noqa: S603 — fixed argv, no shell
            _runner_scope([*argv, "--", *SYNC_ARGV], env),
            cwd=main,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return (
            f"sync: FAILED to start ({exc}) — run scripts/sync_enforcement_to_projects.py --force"
        )
    # `started`: a status written before this start is another runner's (a scoped start can exit 1
    # before the runner runs, writing none), so the drain never reads it as this one's reason
    _SYNC_RUN.update(proc=proc, state=state, main=main, started=time.time())
    return note


def _sync_once(argv: list[str], state: Path, lock_fd: int) -> tuple[int, str]:
    """One sync, its output to SYNC_LOG (truncated: the last run's tail lives in SYNC_STATUS),
    bounded by SYNC_TIMEOUT_S; past it the sync's whole process group is killed. The sync holds
    the runner's SYNC_LOCK fd too, so a runner killed mid-sync leaves the lock held until the
    orphaned sync ends — the next runner waits for it instead of starting a second one."""
    log = state / SYNC_LOG
    with open(log, "wb") as out:
        try:
            proc = subprocess.Popen(  # noqa: S603 — fixed argv, no shell
                argv,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(lock_fd,),
            )
        except OSError as exc:
            return 127, f"cannot run {argv[0]}: {exc}"
        try:
            rc = proc.wait(timeout=SYNC_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, 9)
            proc.wait()
            return 124, f"timed out after {SYNC_TIMEOUT_S}s"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        lines = []
    return rc, " ".join(lines[-2:])


def _sync_runner(state: Path, argv: list[str]) -> int:
    """``sync-runner`` (internal, listed by ``--help``; started by ``_kick_sync``): hold SYNC_LOCK, sync until the owed
    log is covered. Exit 0 covered, or retired at SYNC_RUNNER_SOFT_S with the debt still owed ·
    1 a sync failed · 2 sync-done did not persist · 3 the lock
    stayed held past its wait (``main`` adds 70: the runner itself crashed)."""
    state.mkdir(parents=True, exist_ok=True)
    fd = os.open(state / SYNC_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    started = time.monotonic()
    try:
        deadline = started + SYNC_LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    _write_atomic(
                        state / SYNC_STATUS,
                        json.dumps(
                            {"at": time.time(), "rc": 3, "tail": "the sync lock stayed held"}
                        ),
                    )
                    return 3
                time.sleep(1)
        while True:
            covers = _owed_size(state)
            if covers <= _done_size(state):
                return 0
            if time.monotonic() - started >= SYNC_RUNNER_SOFT_S:
                # every process's debts feed one live runner, so no merge run's wall bounds it:
                # past its own bound it starts no sync (one started would be cut by the scope's
                # backstop) and leaves the debt to the next kick (W-73d00b05)
                _write_atomic(
                    state / SYNC_STATUS,
                    json.dumps(
                        {
                            "at": time.time(),
                            "covers": _done_size(state),
                            "rc": 0,
                            "tail": "runner retired at its bound; the debt stays owed",
                        }
                    ),
                )
                return 0
            rc, tail = _sync_once(argv, state, fd)
            if rc != 0:  # rc = this runner's exit (the drain matches it); sync_rc = the sync's
                _write_atomic(
                    state / SYNC_STATUS,
                    json.dumps(
                        {"at": time.time(), "covers": covers, "rc": 1, "sync_rc": rc, "tail": tail}
                    ),
                )
                return 1
            _write_atomic(state / SYNC_DONE, f"{max(_done_size(state), covers)}\n")
            if _done_size(state) < covers:
                # sync-done did not persist: looping would re-run a 47-repo sync forever
                _write_atomic(
                    state / SYNC_STATUS,
                    json.dumps(
                        {
                            "at": time.time(),
                            "covers": covers,
                            "rc": 2,
                            "tail": f"{SYNC_DONE} did not persist",
                        }
                    ),
                )
                return 2
            _write_atomic(
                state / SYNC_STATUS, json.dumps({"at": time.time(), "covers": covers, "rc": 0})
            )
    finally:
        os.close(fd)


# --- the after-merge leg (D-1186's relief valve, W-3237ba45) ---------------------------------
AFTER_OWED = "owed.jsonl"  # one line per landed merge whose leg was deferred, in landing order
AFTER_DONE = "done.txt"  # one request id per line the runner covered
AFTER_TESTED = "tested.txt"  # the last tip a runner leg ran on: the next leg's base
AFTER_STATUS = "status.json"
AFTER_LOCK = "runner.lock"
AFTER_RUNNER_MAX_S = MERGE_TEST_BUDGET_S + 900


def _after_dir(records: Path) -> Path:
    return records / AFTER_DIR


def _owe_after_merge(ctx: _Ctx, rec: dict) -> str:
    """Append the landed merge to the owed list (one O_APPEND write) and start the runner when none
    is alive; the evidence line the reply carries."""
    d = _after_dir(ctx.records)
    d.mkdir(parents=True, exist_ok=True)
    entry = {
        k: rec.get(k)
        for k in ("id", "merge_sha", "old_base", "requester", "branch", "item", "base")
    }
    fd = os.open(d / AFTER_OWED, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    note = _kick_after(ctx)
    if note:
        return note
    return (
        f"after-merge: owed — the background leg tests {rec['merge_sha'][:12]} ({d / AFTER_STATUS})"
    )


def _kick_after(ctx: _Ctx) -> str:
    """Start an ``after-merge-runner`` in its own bounded scope (bare where none can start); a live
    one holds the runner lock and the new one exits at once. Returns "" or the failure said."""
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "after-merge-runner",
        "--main",
        str(ctx.main),
    ]
    env = _runner_env(dict(os.environ))
    if _scope_ok(env):
        flags = _scope_flags("fabrik-after-merge")
        flags[flags.index(f"RuntimeMaxSec={SYNC_RUNNER_MAX_S}")] = (
            f"RuntimeMaxSec={AFTER_RUNNER_MAX_S}"
        )
        argv = [*flags, "--", *argv]
    try:
        subprocess.Popen(  # noqa: S603 — fixed argv, no shell
            argv,
            cwd=ctx.main,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return (
            f"after-merge: owed, but the runner FAILED to start ({exc}) — the next merge starts it, "
            f"or run `merge_request.py after-merge-runner --main {ctx.main}`"
        )
    return ""


def _open_after_reds(main: Path) -> list[dict]:
    """The open after-merge P0 items in the main checkout's store (tag AFTER_TAG)."""
    out = []
    for f in sorted((main / ".fabrik" / "work").glob("W-*.json")):
        try:
            item = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if AFTER_TAG in (item.get("tags") or []) and item.get("status") not in ("done", "dropped"):
            out.append(item)
    return out


# the title `_file_after_red` writes names the author: a tag cannot hold a 30-32 character agent
# name (`by-` + 32 > the store's 32-character tag rule, review r1 A-1), the title can
_AFTER_TITLE_RE = re.compile(r"after-merge red: merge [0-9a-f]{12} by ([a-z0-9-]{1,32}) \(")


def _author_tag(requester: str | None) -> str:
    """The tag that names an after-merge red's author (``work.py add`` has no owner: assigning is the
    distributor's), or "" when the name cannot be a tag."""
    tag = f"by-{_norm(requester or '')}"
    return tag if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", tag) and requester else ""


def _after_merge_block(ctx: _Ctx, rec: dict) -> None:
    """Refuse a request whose requester authored an open after-merge red (read from the item's
    title), unless it carries that item (the fix). The refusal names the merge and the tests."""
    who = _norm(rec.get("requester") or "")
    for item in _open_after_reds(ctx.main):
        m = _AFTER_TITLE_RE.match(str(item.get("title") or ""))
        if who and m and _norm(m.group(1)) == who and rec.get("item") != item.get("id"):
            raise RefusedError(
                f"{rec.get('requester')} authored the open after-merge red {item.get('id')} "
                f"({item.get('title')}) — fix it first and request with `--item {item.get('id')}`"
            )


def _after_cause(ctx: _Ctx, todo: list[dict], ids: list[str], script_env: dict) -> dict:
    """The first owed merge, in landing order, at which a red id fails (one plain pytest of the red
    ids per merge, in one throwaway); the last when none reproduces (a red that needs the whole run)."""
    if len(todo) == 1 or not ids:
        return todo[-1]
    try:
        return _after_cause_search(ctx, todo, ids, script_env)
    except Exception:  # noqa: BLE001 — the cause is a pointer, never the verdict: fall back
        return todo[-1]


def _after_cause_search(ctx: _Ctx, todo: list[dict], ids: list[str], script_env: dict) -> dict:
    main = ctx.main
    py = main / ".venv" / "bin" / "python"
    py_s = str(py) if os.access(py, os.X_OK) else sys.executable
    parent = Path(tempfile.mkdtemp(prefix=_PRETEST_PREFIX))
    wt = parent / main.name
    try:
        with _worktree_lock(ctx):
            _gitc(
                main,
                "worktree",
                "add",
                "--detach",
                "-q",
                str(wt),
                todo[0]["merge_sha"],
                timeout=TOOL_TIMEOUT_S,
            )
        for entry in todo:
            _gitc(wt, "checkout", "-q", "--detach", entry["merge_sha"])
            here = [i for i in ids if (wt / i.split("::")[0]).is_file()]
            if not here:
                continue
            run = _run(
                _capped(
                    [py_s, "-m", "pytest", "-q", "-p", "no:cacheprovider", *here], TEST_TIMEOUT_S
                ),
                TEST_TIMEOUT_S + 60,
                cwd=wt,
                env={**script_env, "PYTHONPATH": str(wt / "src")},
            )
            # 1 a test failed, 2 a collection error (a red id can be one); 3-5 are no verdict
            if run.returncode in (1, 2):
                return entry
        return todo[-1]
    finally:
        _run(["git", "worktree", "remove", "--force", str(wt)], GIT_TIMEOUT_S, cwd=main)
        shutil.rmtree(parent, ignore_errors=True)


def _file_after_red(main: Path, cause: dict, ids: list[str], base: str, top: str) -> str:
    """File the P0 on the cause merge's author; returns the item id, or "" with the failure said."""
    shown = ", ".join(ids[:6]) + (f" (+{len(ids) - 6} more)" if len(ids) > 6 else "")
    title = (
        f"after-merge red: merge {cause['merge_sha'][:12]} by {_norm(cause.get('requester') or '')} (request "
        f"{cause['id']}, branch {cause.get('branch')}) turned {shown} red, tested "
        f"{base[:12]}..{top[:12]}; {cause.get('requester')}'s next merge is refused until a request "
        "carries this item"
    )
    work = HERE / "work.py"
    add = _run(
        [
            sys.executable,
            str(work),
            "--repo",
            str(main),
            "add",
            "--kind",
            "task",
            "--title",
            title,
            "--priority",
            "0",
            "--tag",
            AFTER_TAG,
            *(
                ["--tag", _author_tag(cause["requester"])]
                if _author_tag(cause.get("requester"))
                else []
            ),
            "--next",
            f"fix the red after merge {cause['merge_sha'][:12]}, then request with --item",
        ],
        GIT_TIMEOUT_S,
        cwd=main,
    )
    m = re.search(r"\bW-[0-9a-f]{8}\b", add.stdout + add.stderr)
    return m.group(0) if add.returncode == 0 and m else ""


def _after_status(d: Path, **fields) -> None:
    _write_atomic(d / AFTER_STATUS, json.dumps({"at": time.time(), **fields}, sort_keys=True))


def _after_todo(d: Path) -> list[dict]:
    """The owed merges not yet covered, in landing order (a duplicate line is covered once)."""
    try:
        owed = [
            json.loads(x)
            for x in (d / AFTER_OWED).read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
    except FileNotFoundError:
        owed = []
    try:
        done = set((d / AFTER_DONE).read_text(encoding="utf-8").split())
    except FileNotFoundError:
        done = set()
    todo: list[dict] = []
    for e in owed:
        if isinstance(e, dict) and e.get("id") and e.get("merge_sha") and e.get("old_base"):
            if e.get("id") not in done and all(e.get("id") != t.get("id") for t in todo):
                todo.append(e)
    return todo


def _after_merge_runner(main: Path) -> int:
    """``after-merge-runner`` (internal; started by ``_kick_after``): ONE leg per process, so its
    scope's RuntimeMaxSec bounds exactly one leg (review r1 A-3). Under ``runner.lock`` it sweeps a
    dead runner's throwaway (A-4), runs the base's ``.fabrik/merge-tests`` once on the newest owed
    merge against the last tested tip (``ctx.after_base``), so one leg covers every merge landed
    since, and on a verdict marks them covered and moves the tested tip. After releasing the lock
    it reads the owed list again and starts a successor while anything is owed — a merge owed
    between its last read and its exit is never left waiting (A-5). Exit 0 covered, nothing owed,
    or another runner holds the lock · 1 a leg without a verdict or a red it could not file (left
    owed, ``status.json`` says why)."""
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=main))
    ctx = _Ctx(main, common, "")
    d = _after_dir(ctx.records)
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / AFTER_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0  # the live runner re-reads the owed list after it releases the lock
        rc = _after_merge_leg(ctx, d)
    finally:
        os.close(fd)
    if rc == 0 and _after_todo(d):
        note = _kick_after(ctx)
        if note:
            _after_status(d, rc=4, tail=note)
            return 1
    return rc


def _after_merge_leg(ctx: _Ctx, d: Path) -> int:
    """One leg over every merge owed now; see ``_after_merge_runner``."""
    main = ctx.main
    actx = _Ctx(main, ctx.common, "")
    actx.records = d / "runs"
    _sweep_pretests(actx)
    todo = _after_todo(d)
    if not todo:
        return 0
    try:
        tested = (d / AFTER_TESTED).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        tested = ""
    top = todo[-1]["merge_sha"]
    if not tested or not _is_ancestor(main, tested, top):
        tested = todo[0]["old_base"]
    script = _base_merge_tests(ctx, tested)
    covered = [e["id"] for e in todo]
    ids: list[str] = []
    keep = os.environ.get("FABRIK_MERGE_TESTS_RECORDS")
    with tempfile.TemporaryDirectory(prefix="merge-after-records-") as private:
        os.environ["FABRIK_MERGE_TESTS_RECORDS"] = private
        try:
            ctx.test_deadline = time.monotonic() + MERGE_TEST_BUDGET_S
            ctx.full_leg = _declared_leg(script)
            ctx.leg_mem = _declared_mem(script)
            ctx.after_base = tested
            run_rec: dict = {"id": f"after-{top[:12]}.run-{os.getpid()}", **_claimer()}
            with _throwaway(actx, run_rec, top, _PRETEST_PREFIX) as wt:
                _copy_worktree_include(ctx, wt, tested)
                run, _label = _run_owner_leg(ctx, wt, script, [])
            (actx.records / f"{run_rec['id']}.json").unlink(missing_ok=True)
            rec_file = Path(private) / f"merge-tests-{tested}.txt"
            if rec_file.is_file():
                ids = [
                    line.split("\t")[0]
                    for line in rec_file.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")
                ]
        finally:
            if keep is None:
                os.environ.pop("FABRIK_MERGE_TESTS_RECORDS", None)
            else:
                os.environ["FABRIK_MERGE_TESTS_RECORDS"] = keep
    tail = " ".join((run.stdout + run.stderr).strip().splitlines()[-2:])[:500]
    where = {"tested": tested, "top": top, "covers": covered, "tail": tail}
    if run.returncode == 1 and ids:
        cause = _after_cause(ctx, todo, ids, dict(os.environ))
        if not (main / ".fabrik" / "work" / "config.json").is_file():  # work.py's own _has_store
            # no work store to file into (a synced repo without one): the red is covered and
            # said in status.json, never left owed for every later merge to re-run (r2 A2-2)
            item = "none — this repo has no .fabrik/work store"
        else:
            item = _file_after_red(main, cause, ids, tested, top)
        if not item:  # an unfiled red would read pre-existing once tested.txt moved past it
            _after_status(d, rc=2, red=ids, cause=cause["id"], **where)
            return 1
        verdict = {"rc": 1, "red": ids, "cause": cause["id"], "item": item}
    elif run.returncode == 0:
        verdict = {"rc": 0}
    else:
        _after_status(d, rc=3, **where)
        return 1
    _write_atomic(d / AFTER_TESTED, top + "\n")
    with open(d / AFTER_DONE, "a", encoding="utf-8") as fh:
        fh.write("".join(i + "\n" for i in covered))
    _after_status(d, **where, **verdict)
    return 0


def _drain_sync() -> None:
    """After the verb, the merge lock released: wait for THIS process's runner and print its
    outcome, SYNC_TIMEOUT_S in all. A runner that exited 0 while a debt is still owed (one owed
    between its last check and its exit, or in another process) gets ONE more runner, which covers
    it or finds another process's sync covering it. Never changes the exit code."""
    proc = _SYNC_RUN.pop("proc", None)
    if proc is None:
        return
    state, main = _SYNC_RUN.pop("state"), _SYNC_RUN.pop("main")
    started = _SYNC_RUN.pop("started", 0.0)
    deadline = time.monotonic() + SYNC_TIMEOUT_S
    for rerun in (False, True):
        try:
            proc.wait(timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            print(
                f"merge_request: sync: still running in the background (pid {proc.pid}) — "
                f"{state / SYNC_STATUS} has its outcome",
                file=sys.stderr,
            )
            return
        if proc.returncode != 0:
            break
        if _owed_size(state) <= _done_size(state) or rerun:
            later = (
                ""
                if _owed_size(state) <= _done_size(state)
                else ("; a debt owed since is still open — the next merge run's sync covers it")
            )
            print(f"merge_request: sync: ran (log {state / SYNC_LOG}){later}", file=sys.stderr)
            return
        note = _kick_sync(main, state)
        proc = _SYNC_RUN.pop("proc", None)
        _SYNC_RUN.clear()
        if proc is None:  # nothing left to start, or the start failed (its note says so)
            if note and note.startswith("sync: FAILED"):  # the debt owed since stays open
                print(
                    f"merge_request: {note}; the earlier sync ran (log {state / SYNC_LOG})",
                    file=sys.stderr,
                )
            else:
                print(f"merge_request: sync: ran (log {state / SYNC_LOG})", file=sys.stderr)
            return
    last = _sync_status(state)
    rc = proc.returncode  # the runner's own exit; the status file may be an older run's
    fresh = isinstance(last.get("at"), (int, float)) and last["at"] >= started
    if fresh and last.get("rc") == rc:
        rc, tail = last.get("sync_rc", rc), last.get("tail", "")
    else:
        tail = "the runner recorded no reason"
    print(
        f"merge_request: sync: FAILED (exit {rc}: {tail}) — run "
        "scripts/sync_enforcement_to_projects.py --force; the debt stays owed and the next "
        "merge run retries it",
        file=sys.stderr,
    )


def _recipients(ctx: _Ctx, rec: dict) -> list[str]:
    """The requester, then the coordinator (``.fabrik/work/config.json`` ``distributor``) when
    it is a different agent and not the owner."""
    requester = rec.get("requester", "")
    out = [requester] if requester else []
    try:
        raw = _work_config(ctx.main).get("distributor")
    except RefusedError:
        raw = None
    dist = raw.strip() if isinstance(raw, str) else ""
    if dist and _norm(dist) not in {_norm(requester), _norm(ctx.owner)}:
        out.append(dist)
    return out


def _reply_body(rec: dict) -> str:
    lines = [
        f"request: {rec['id']}",
        f"branch: {rec.get('branch', '?')}",
        f"outcome: {rec['outcome']}",
    ]
    retries = rec.get("retries") or []
    if retries:  # a reader holding two replies `re:` one id tells the current one by this line
        lines.append(
            f"retry: {len(retries)} — supersedes the refused reply ({retries[-1].get('reason', '?')})"
        )
    skipped = rec.get("not_carried", [])
    if rec["outcome"] == "merged":
        lines += [f"merge: {rec['merge_sha']}", f"base: {rec['base']}"]
        if skipped:
            lines.append(f"carry: {len(skipped)} path(s) NOT carried into the main checkout")
    else:
        lines += [f"reason: {rec.get('reason', '?')}"]
    lines += [f"evidence: {e}" for e in rec.get("evidence", [])]
    if skipped:
        lines += ["", "not carried:"] + [f"- WARNING: {w}" for w in skipped]
    item = rec.get("item") or "none"
    lines += ["", f"item: {item}"]
    if rec["outcome"] == "merged" and item != "none":
        lines.append(
            f"coordinator: python3 scripts/work.py done {item} --evidence {rec['merge_sha']}"
        )
    elif rec["outcome"] != "merged":
        lines.append(
            "HOW — do what the reason names; when it names a change to your branch, make it, "
            "push, re-review, and run merge_request.py request again with the updated receipt — "
            "never a rebase or a force-push: the branch is already pushed. When it says the base "
            "alone is red too, change nothing and send nothing: the owner fixes the base and "
            "runs merge_request.py retry on this request. When it names the owner-test budget of "
            "the run, change nothing and send nothing either: the owner runs merge_request.py retry."
        )
    body = "\n".join(lines) + "\n"
    return body.replace("acked-by:", "acked by:")  # a body never carries a verbatim ack line


def _reply_and_ack(ctx: _Ctx, rec: dict) -> None:
    """(h): reply to the requester and the coordinator, then ack ``done --merge-sha`` or
    ``blocked --reason``. Each reply is recorded as sent, so a resume never sends it twice."""
    sent = rec.setdefault("replied_to", [])
    body = _reply_body(rec)
    for agent in _recipients(ctx, rec):
        if agent in sent:
            continue
        res = _mail_cli(
            ctx,
            "send",
            "--to",
            ctx.mailbox,
            "--to-agent",
            agent,
            "--kind",
            "reply",
            "--re",
            rec["id"],
            stdin_text=body,
        )
        if res.returncode != 0:
            raise MergePartialError(
                f"reply to {agent} failed: {res.stderr.strip() or res.returncode}"
            )
        sent.append(agent)
        _save(ctx, rec)
        print(res.stdout.strip())
    archived = _mail_root() / ctx.mailbox / "archive" / f"{rec['id']}.md"
    try:
        acked = bool(
            _mail()._ACK_LINE.search(archived.read_text(encoding="utf-8", errors="replace"))
        )
    except OSError:
        acked = False
    if not acked:
        if rec["outcome"] == "merged":
            args = ["--disposition", "done", "--merge-sha", rec["merge_sha"]]
        else:
            args = ["--disposition", "blocked", "--reason", rec.get("reason", "refused")]
        res = _mail_cli(ctx, "ack", rec["id"], "--repo", ctx.mailbox, *args)
        if res.returncode != 0:
            raise MergePartialError(
                f"ack of {rec['id']} failed: {res.stderr.strip() or res.returncode}"
            )
    rec["phase"] = "replied"
    _save(ctx, rec)


def _mail_root() -> Path:
    return Path(os.environ.get("FABRIK_MAIL_ROOT", "/opt/fabrik-mail"))


# --- the driver -----------------------------------------------------------------------------
def _find_merge(ctx: _Ctx, rec: dict) -> str:
    """The request's existing merge commit in base: its message names the request id and its
    history holds the head (resume when ``head`` is already in base — never a second merge)."""
    out = _gitc(
        ctx.main,
        "log",
        "--format=%H",
        "-F",
        f"--grep=— request {rec['id']}, item ",
        HEADS + rec["base"],
    )
    for sha in out.split():
        if _is_ancestor(ctx.main, rec["head"], sha):
            return sha
    return ""


def _signed(ctx: _Ctx, subject: str, context: str) -> str:
    """``subject`` plus ONE Agent Provenance Trailer paragraph (W-e914202a): the merge is the
    owner's act, so Agent-Role orchestrator and the owner's Agent-Name — left out, with a note,
    when the owner is outside the agent-name grammar. A multi-line value refuses: it would end
    the paragraph or forge a trailer. No Merged-From: scratch_sweep reads it over merge commits,
    where a reused branch name would read "merged" for ever."""
    name = _norm(ctx.owner) if ctx.owner.isascii() else ""
    lines = ["Agent-Role: orchestrator"]
    if _AGENT_NAME_RE.fullmatch(name):
        lines.append(f"Agent-Name: {name}")
    else:
        note = f"owner {ctx.owner!r} is outside the agent-name grammar — merge signed without Agent-Name"
        if note not in ctx.notes:  # once per run: a rebuild signs again
            ctx.notes.append(note)
    lines.append(f"Agent-Context: {context}")
    for value in (subject, context):
        if not value or not _one_line(value):
            raise RefusedError(f"merge message value {value!r} is not one line — not signed")
    return "\n".join([subject, "", *lines])


# Only what merge itself does: it never sees the requester's gate (`--review` is a path).
GATE_DUTY = (
    "gate: merge does not run final_gate — gating the merged result is the caller's duty; "
    "merge itself runs only the owner tests"
)


def _gate_line(rec: dict) -> str:
    """GATE_DUTY plus the request merge's owner-test summary (W-e914202a) — recorded by whichever
    run built it; a catch-up's summary rides its own evidence line."""
    tests = next(
        (e[len("tests: ") :] for e in reversed(rec.get("evidence", [])) if e.startswith("tests: ")),
        f"none recorded (resumed an existing merge {rec.get('merge_sha')})",
    )
    return f"{GATE_DUTY}; owner tests of the request merge: {tests}"


def _merge_message(ctx: _Ctx, rec: dict) -> str:
    item = rec.get("item") or "none"
    return _signed(
        ctx,
        f"merge({ctx.owner}): {rec['branch']} — request {rec['id']}, item {item}",
        f"merge_request.py merged branch {rec['branch']} for request {rec['id']}, item {item}",
    )


def _validate_request(rec: dict) -> None:
    for key in ("branch", "head", "base", "requester"):
        value = rec.get(key) or ""
        if not value or not _one_line(value):
            raise RefusedError(f"the request body has no usable {key!r} field")
    if not _SHA_RE.fullmatch(rec["head"]):
        raise RefusedError(f"the request head {rec['head']!r} is not a full commit SHA")
    item = rec.get("item") or "none"
    if item != "none" and not ITEM_RE.fullmatch(item):
        raise RefusedError(f"the request item {item!r} is not a work item id")
    # O2: both names reach git argv (a fetch refspec, a ref) — a leading '-' is an option, a ':'
    # or '..' a refspec; only a name `git check-ref-format --branch` echoes back unchanged passes.
    for key in ("base", "branch"):
        name = rec[key]
        res = _run(["git", "check-ref-format", "--branch", name], GIT_TIMEOUT_S)
        if name.startswith("-") or res.returncode != 0 or res.stdout.strip() != name:
            raise RefusedError(f"the request {key} {name!r} is not a branch name")


def _ensure_head(ctx: _Ctx, rec: dict, remote: str) -> None:
    if _rev(ctx.main, rec["head"]):
        return
    try:
        _fetch(ctx, remote, HEADS + rec["branch"], rec["branch"])
    except UnreachableError:
        raise
    except RefusedError:
        pass  # the branch is not on the remote: the refusal below names it
    if not _rev(ctx.main, rec["head"]):
        raise RefusedError(
            f"the request head {rec['head'][:12]} is not in this repo or on {remote}"
        )


def _merge_request_steps(ctx: _Ctx, rec: dict, remote: str) -> None:
    """(a)-(d) for the request itself; on success the record holds ``merged``."""
    step = "(a) preflight"
    rec.pop("deferred", None)
    ctx.tests_deferred = False
    try:
        _validate_request(rec)
        _after_merge_block(ctx, rec)
        _refuse_linked_base(ctx, rec["base"])
        _ensure_head(ctx, rec, remote)
        local = _rev(ctx.main, HEADS + rec["base"])
        if not local:
            raise RefusedError(f"local base {rec['base']} does not exist")
        if _is_ancestor(ctx.main, rec["head"], local):
            sha = _find_merge(ctx, rec)
            if not sha:
                raise RefusedError(
                    f"head {rec['head'][:12]} is already in {rec['base']} but no merge commit "
                    f"names request {rec['id']}"
                )
            rec.update(
                phase="merged",
                merge_sha=sha,
                old_base=_rev(ctx.main, f"{sha}^1"),
                snapshot=None,
                carried_to=_rev(ctx.main, f"{sha}^1"),
            )
            rec.setdefault("evidence", []).append(f"already merged as {sha} — no second merge")
            _save(ctx, rec)
            return
        origin = _fetch_base(ctx, remote, rec["base"])  # a START condition only (O35)
        if not _is_ancestor(ctx.main, origin, local):
            raise RefusedError(
                f"{remote}/{rec['base']} ({origin[:12]}) is ahead of the local base "
                f"({local[:12]}) — the owner pulls first"
            )
        step = "(a)-(d) build, preflight, tests, CAS"
        try:
            old, new, snap, tests, on_base = _merge_into_base(
                ctx, rec, rec["head"], _merge_message(ctx, rec), catch_up=False
            )
        except RefusedError as exc:
            # the request leg only: a catch-up's refusal parks for `resume`, so it gets no verdict;
            # the merge throwaway is already removed here, so the base-alone one is never nested
            if isinstance(exc, BudgetSpentError):
                raise BudgetSpentError(
                    f"{exc}; the owner retries with `merge_request.py retry {rec['id']}`"
                ) from exc
            if not hasattr(exc, "base_old") or isinstance(exc, UnreachableError):
                raise
            raise RefusedError(f"{exc}{_base_alone(ctx, rec, exc.base_old, exc)}") from exc
    except UnreachableError as exc:
        rec["deferred"] = f"{step}: {' '.join(str(exc).split())}"  # phase stays as it was
        _save(ctx, rec)
        return
    except RefusedError as exc:
        rec.update(
            phase="refused", outcome="refused", reason=f"{step}: {' '.join(str(exc).split())}"
        )
        _save(ctx, rec)
        return
    rec.update(
        phase="merged",
        merge_sha=new,
        old_base=old,
        snapshot=snap,
        carried_to=old,
        preflighted=on_base,
    )
    if ctx.tests_deferred:
        rec["tests_after_merge"] = True
    else:
        rec.pop("tests_after_merge", None)  # the last attempt ran its leg
    rec.pop("building", None)
    rec.setdefault("evidence", []).extend(
        [f"merge commit {new} on {rec['base']} ({old[:12]} → {new[:12]})", f"tests: {tests}"]
    )
    _save(ctx, rec)


def _carry_step(ctx: _Ctx, rec: dict) -> None:
    """(e): carry from the last carried commit to the local base, the snapshot applying only
    to the request's own merge."""
    on_phase("before-carry")
    base_tip = _rev(ctx.main, HEADS + rec["base"])
    start = rec.get("carried_to") or rec["old_base"]
    own = start == rec["old_base"]
    snap = rec.get("snapshot") if own else None
    if base_tip and start != base_tip:
        if own and rec.get("preflighted") is False:
            # O8: the main checkout was not on base at the preflight — never carry into it.
            skipped = [
                f"(every merged path): the main checkout was not on {rec['base']} at the "
                "preflight — nothing carried; check `git status` there"
            ]
        else:
            carried, skipped = _carry(ctx, rec["base"], start, base_tip, snap)
            rec.setdefault("evidence", []).append(
                f"carry: {len(carried)} path(s) into the main checkout"
            )
        rec.setdefault("not_carried", []).extend(skipped)
    rec.update(phase="carried", carried_to=base_tip)
    _save(ctx, rec)


def _catch_up(ctx: _Ctx, rec: dict, remote: str) -> None:
    """O35: origin moved during the run — merge origin's base INTO the local base through the
    same (a)-(e) (EXEMPT from (a)'s origin-ahead start refusal), never a rebase or a stash. The
    request's merge commit stays in history unchanged."""
    origin = _fetch_base(ctx, remote, rec["base"])
    local = _rev(ctx.main, HEADS + rec["base"])
    if _is_ancestor(ctx.main, origin, local):
        return
    message = _signed(
        ctx,
        f"merge({ctx.owner}): catch up {remote}/{rec['base']} after request {rec['id']}",
        f"merge_request.py catch-up of {remote}/{rec['base']} after request {rec['id']}",
    )
    old, new, snap, tests, on_base = _merge_into_base(ctx, rec, origin, message, catch_up=True)
    rec.setdefault("evidence", []).append(
        f"catch-up merge {new} of {remote}/{rec['base']} (tests: {tests})"
    )
    rec.update(carried_to=old)
    _save(ctx, rec)
    if on_base:
        try:
            _, skipped = _carry(ctx, rec["base"], old, new, snap)
        except RefusedError as exc:
            # O13: the catch-up CAS already landed — this is a CARRY failure, not a refused
            # catch-up, and nothing is to be merged by hand. ``carried_to`` stays ``old``, so the
            # next resume re-carries (idempotently) before it pushes.
            try:  # O15: a second git failure must not escape and park the record
                paths = ", ".join(p for _, p in _merged_paths(ctx.main, old, new)) or "(none)"
            except RefusedError as why:
                paths = f"unknown ({' '.join(str(why).split())})"
            raise MergePartialError(
                f"the catch-up merge {new} of {remote}/{rec['base']} is committed locally, but "
                f"its carry into the main checkout failed ({' '.join(str(exc).split())}); not "
                f"carried: {paths}; push pending — finish with `merge_request.py resume "
                f"{rec['id']}`"
            ) from exc
    else:
        skipped = [f"(catch-up paths): the main checkout was not on {rec['base']} — not carried"]
    rec.setdefault("not_carried", []).extend(skipped)
    rec.update(carried_to=new)
    _save(ctx, rec)


_STEPS_LEFT = {
    "merged": "carry, push, sync, reply, ack",
    "carried": "push, sync, reply, ack",
    "pushed": "sync, reply, ack",
    "synced": "reply, ack",
}


def _catch_up_refused(ctx: _Ctx, rec: dict, remote: str, exc: RefusedError) -> str:
    """The OWNER's instruction for a refused catch-up — never the requester's 'rebase and
    resend': the request is merged locally; origin and local base diverged."""
    base = rec["base"]
    resume_cmd = f"`merge_request.py resume {rec['id']}`"
    if isinstance(exc, ConflictError):
        return (
            f"origin and local {base} diverged in {', '.join(exc.paths)}; merge {remote}/{base} "
            f"into {base} by hand, then {resume_cmd}"
        )
    why = " ".join(str(exc).split())
    if isinstance(exc, BudgetSpentError):
        return f"the catch-up merge of {remote}/{base} into {base} stopped ({why}); {resume_cmd} again (a new run, a new budget)"
    return (
        f"the catch-up merge of {remote}/{base} into {base} refused ({why}); merge "
        f"{remote}/{base} into {base} by hand, then {resume_cmd}"
    )


def _after_cas(ctx: _Ctx, rec: dict, remote: str, resuming: bool) -> None:
    """(e)-(h): every step after the CAS. The merge is committed; nothing here undoes it."""
    if GATE_DUTY not in rec.get("evidence", []):  # the reply carries it (W-e914202a)
        rec.setdefault("evidence", []).append(GATE_DUTY)
        _save(ctx, rec)
    if rec["phase"] == "catchup-refused":
        rec["phase"] = "carried"  # only an explicit resume reaches here: retry the catch-up
    if rec["phase"] == "merged":
        _carry_step(ctx, rec)
    if rec["phase"] == "carried" and rec.get("carried_to") != _rev(ctx.main, HEADS + rec["base"]):
        _carry_step(ctx, rec)  # a resume after a crash between a CAS and its carry
    if rec["phase"] == "carried":
        on_phase("before-push")
        ok, detail = _push(ctx, rec, remote)
        if not ok and resuming:
            try:
                _catch_up(ctx, rec, remote)
            except UnreachableError as exc:
                raise MergePartialError(
                    f"the catch-up could not reach {remote} ({' '.join(str(exc).split())}); the "
                    f"merge {rec['merge_sha']} is committed locally, nothing parked — finish with "
                    f"`merge_request.py resume {rec['id']}`"
                ) from exc
            except RefusedError as exc:
                rec.update(phase="catchup-refused", reason=_catch_up_refused(ctx, rec, remote, exc))
                _save(ctx, rec)
                raise MergePartialError(rec["reason"]) from exc
            ok, detail = _push(ctx, rec, remote)
        if not ok:
            raise MergePartialError(
                f"push of {rec['base']} to {remote} rejected ({detail}) — the merge "
                f"{rec['merge_sha']} is committed locally; finish with `merge_request.py resume "
                f"{rec['id']}`"
            )
        rec.setdefault("evidence", []).append(f"pushed {rec['base']} to {remote} (fast-forward)")
        rec["phase"] = "pushed"
        _save(ctx, rec)
    if rec["phase"] == "pushed":
        rec.setdefault("evidence", []).append(_sync(ctx, rec))
        rec["phase"] = "synced"
        _save(ctx, rec)
    if rec["phase"] == "synced":
        if rec.get("tests_after_merge") and not rec.get("after_merge_owed"):
            rec.setdefault("evidence", []).append(_owe_after_merge(ctx, rec))
            rec["after_merge_owed"] = True
            _save(ctx, rec)
        rec["outcome"] = "merged"
        _reply_and_ack(ctx, rec)


def _drive(ctx: _Ctx, rec: dict, *, resuming: bool) -> int:
    """Run one claimed request from its recorded phase to ``replied``."""
    remote = "origin"
    try:
        remote = _remote_name(ctx.main, rec["base"]) if rec.get("base") else remote
    except RefusedError as exc:
        if rec["phase"] not in ("claimed", "built"):
            raise MergePartialError(f"{exc} — {_STEPS_LEFT.get(rec['phase'], '')} left") from exc
        rec.update(phase="refused", outcome="refused", reason=f"(a) preflight: {exc}")
        _save(ctx, rec)
    if rec["phase"] in ("claimed", "built"):
        if remote in ctx.unreachable:
            rec["deferred"] = f"(a) preflight: {remote} was unreachable earlier in this run"
            _save(ctx, rec)
        else:
            _merge_request_steps(ctx, rec, remote)  # a start: the origin-ahead refusal applies
        if rec.get("deferred"):
            ctx.unreachable.add(remote)
            print(
                f"merge_request: DEFERRED {rec['id']} — {rec['deferred']}; nothing replied; "
                "the next merge run retries it",
                file=sys.stderr,
            )
            return EXIT_REFUSED
    if rec["phase"] == "refused":
        _reply_and_ack(ctx, rec)
        for note in ctx.notes:
            print(f"merge_request: {note}", file=sys.stderr)
        print(f"merge_request: REFUSED {rec['id']} — {rec['reason']}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        _after_cas(ctx, rec, remote, resuming)
    except RefusedError as exc:
        # O3: once the CAS has succeeded, every failure (a push or a mail timeout, a git error)
        # is PARTIAL — the merge stays committed and the remaining steps are named.
        left = _STEPS_LEFT.get(rec["phase"], "the remaining steps")
        raise MergePartialError(
            f"{' '.join(str(exc).split())} — the merge {rec.get('merge_sha')} is committed "
            f"locally; left: {left}; finish with `merge_request.py resume {rec['id']}`"
        ) from exc
    finally:  # merged or PARTIAL alike: a note is never swallowed by the exit it took
        for note in ctx.notes:
            print(f"merge_request: {note}", file=sys.stderr)
    print(f"merged {rec['id']} as {rec.get('merge_sha')}")
    print(_gate_line(rec))
    for line in rec.get("not_carried", []):
        print(f"merge_request: NOT CARRIED — {line}", file=sys.stderr)
    return EXIT_OK


def _new_record(ctx: _Ctx, msg_id: str, fields: dict, phase: str = "claimed") -> dict:
    rec = {
        "id": msg_id,
        "phase": phase,
        **{k: fields.get(k, "") for k in ("branch", "head", "base", "item", "requester", "review")},
        **_claimer(),
    }
    _save(ctx, rec)
    return rec


def _mail_claim(ctx: _Ctx, rec: dict) -> dict:
    """``mail.py claim`` for a ``claiming`` record (the addressee check and the inbox→archive
    rename are mail.py's); a refusal removes the record — nothing was claimed."""
    res = _mail_cli(ctx, "claim", rec["id"], "--repo", ctx.mailbox)
    if res.returncode != 0:
        (ctx.records / f"{rec['id']}.json").unlink(missing_ok=True)
        raise RefusedError(
            f"mail.py claim {rec['id']} refused: {res.stderr.strip() or res.returncode}"
        )
    rec["phase"] = "claimed"
    _save(ctx, rec)
    return rec


def _remote_of_request(ctx: _Ctx, fm: dict) -> str | None:
    """The push remote of an inbox request's base, read from its body — None when it cannot be
    read or resolved (the request is then claimed and refused or merged as before)."""
    if not ctx.unreachable:
        return None
    try:
        text = (_mail_root() / ctx.mailbox / "inbox" / f"{fm.get('id')}.md").read_text(
            encoding="utf-8", errors="replace"
        )
        base = _split_message(text)[1].get("base") or ""
        return _remote_name(ctx.main, base) if base else None
    except (OSError, RefusedError):
        return None


def _claim(ctx: _Ctx, msg_id: str) -> dict:
    """O5: the record is written (phase ``claiming``) BEFORE ``mail.py claim`` runs, so a crash
    between the two leaves a record a resume can finish; the request leaves the inbox before
    anything is built."""
    inbox = _mail_root() / ctx.mailbox / "inbox" / f"{msg_id}.md"
    try:
        text = inbox.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RefusedError(f"{msg_id} is no longer in the inbox: {exc}") from exc
    _, fields = _split_message(text)
    return _mail_claim(ctx, _new_record(ctx, msg_id, fields, phase="claiming"))


def _continue_claiming(ctx: _Ctx, rec: dict) -> dict | None:
    """A ``claiming`` record: its message in the archive → the claim landed, continue; still in
    the inbox → claim it again; in neither → nothing to do, the record is removed."""
    box = _mail_root() / ctx.mailbox
    archived = box / "archive" / f"{rec['id']}.md"
    if archived.is_file():
        if rec.get("retries") and _acked(archived):
            # a retry that stopped before its requeue: its mail still carries the refusal's ack,
            # and continuing as claimed would skip the merge's `done --merge-sha` ack (W-c751bca6)
            return _reopen(ctx, rec)
        rec["phase"] = "claimed"
        _save(ctx, rec)
        return rec
    inbox = box / "inbox" / f"{rec['id']}.md"
    if inbox.is_file():
        if rec.get("retries") and _acked(inbox):
            raise _stale_ack(rec["id"])  # a requeue that left the ack in place (_reopen)
        return _mail_claim(ctx, rec)
    print(
        f"merge_request: {rec['id']} is in neither inbox nor archive — record removed",
        file=sys.stderr,
    )
    (ctx.records / f"{rec['id']}.json").unlink(missing_ok=True)
    return None


def _sweep_throwaways(ctx: _Ctx) -> None:
    """O7: under the lock no throwaway is live, so every registered worktree a crashed run left
    is removed and pruned — whatever phase its record holds — but only one ``_owned_throwaway``
    accepts (O12): a same-named directory anywhere else on disk is never touched."""
    out = _run(["git", "worktree", "list", "--porcelain"], GIT_TIMEOUT_S, cwd=ctx.main).stdout
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
            if path != ctx.main and _owned_throwaway(ctx, path):
                _remove_throwaway(ctx, path)
    with _worktree_lock(ctx):
        _run(["git", "worktree", "prune"], GIT_TIMEOUT_S, cwd=ctx.main)


def _context(cwd: Path) -> _Ctx:
    main = _main_checkout(cwd)
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd))
    if main.resolve() == common.resolve():
        raise RefusedError(f"this repo keeps a separate git dir ({common}) — no mailbox to resolve")
    owner = _merge_owner(main)
    caller = _caller_agent()
    if _norm(caller) != _norm(owner):
        raise RefusedError(
            f"{caller or '(unresolved caller)'} is not the merge owner {owner} — only the owner merges"
        )
    return _Ctx(main, common, owner)


def _parked(ctx: _Ctx) -> list[dict]:
    """Every readable record parked at ``catchup-refused`` (unreadable ones are warned about by
    ``_resume_stranded``)."""
    out: list[dict] = []
    for path in sorted(ctx.records.glob("*.json")) if ctx.records.is_dir() else []:
        try:
            rec = _load(ctx, path.stem)
        except RefusedError:
            continue
        if rec is not None and rec.get("phase") == "catchup-refused" and "id" in rec:
            out.append(rec)
    return out


def _resume_stranded(ctx: _Ctx) -> int:
    rc = EXIT_OK
    if not ctx.records.is_dir():
        return rc
    for path in sorted(ctx.records.glob("*.json")):
        try:
            rec = _load(ctx, path.stem)  # O6: an unreadable record never blocks the run
            if rec is None or not isinstance(rec.get("id"), str) or "phase" not in rec:
                raise RefusedError(f"record {path.name} is unreadable: not a merge record")
        except RefusedError as exc:
            print(f"merge_request: WARNING — {exc}; skipped", file=sys.stderr)
            continue
        if not _stranded(rec):
            continue
        if rec["phase"] == "catchup-refused":
            print(
                f"merge_request: skipping {rec['id']} (catch-up refused: {rec.get('reason')}); "
                f"only `merge_request.py resume {rec['id']}` retries it",
                file=sys.stderr,
            )
            continue
        print(
            f"merge_request: resuming stranded request {rec['id']} from {rec['phase']}",
            file=sys.stderr,
        )
        rec.update(_claimer())
        _save(ctx, rec)
        try:
            if rec["phase"] == "claiming" and _continue_claiming(ctx, rec) is None:
                continue
            rc = max(rc, _drive(ctx, rec, resuming=True))
        except MergePartialError as exc:
            print(f"merge_request: PARTIAL — {exc}", file=sys.stderr)
            rc = EXIT_PARTIAL  # reported; the inbox is still served
        except RefusedError as exc:
            print(f"merge_request: REFUSED {rec['id']} — {exc}", file=sys.stderr)
            rc = max(rc, EXIT_REFUSED)
    return rc


# --- merge --queue: the queue's owner tests run OUTSIDE the merge lock (W-0c8c43f1) -----------
# A queue of N requests waited N legs one after another under the lock (hub 2026-10-24: 36-129 min,
# ~940 s a leg). The queue builds the waiting requests as a STACKED chain in merge order — S0 the
# local base, Sk request k merged onto S(k-1) — runs each leg in a forked child, at most --jobs at
# once, and records each green tree as `request --pretest` does. It then lands each request through
# the unchanged locked `merge <id>`, whose `_pretested` skips the leg on a matching tree, so the lock
# covers the build, CAS, carry, push, sync and reply only. Sk's tree equals the tree the locked merge
# builds on M(k-1) when requests 1..k-1 landed in order (same merge-base, deterministic `_build`; both
# design critics executed it, ledger conflicts included). Any other order, or a base moved by code,
# mismatches and that merge runs its leg as before: never a skip on a tree no leg passed.
QUEUE_POLL_S = 2.0
# One leg at a time, at the owner script's own width: each leg keeps the per-leg limit
# (TEST_TIMEOUT_S, or the base's declared one) sized for that width, so two legs at half width
# each ran twice as long against it — every queue leg died at 1800 s on 2026-10-27 (4-shard shards
# 603-1643 s; one 8-shard leg's shards 253-842 s). A later leg forks only once the first request
# lands on a record (or has no tree to test), so it overlaps that landing, never the first's own
# leg; `--jobs N` lets N such
# later legs run at once, each at full width — only where the box has N legs' worth of free CPUs.
QUEUE_JOBS = 1
QUEUE_MAX = 4  # requests per pass; each lands within the wall below or waits for the next run
QUEUE_WAIT_S = 1800  # how long the queue waits for a merge it did not start to finish
# One landing may first wait QUEUE_WAIT_S for a merge lock another run holds (`_land`), then run a
# whole locked merge with its own leg (its record did not match): the D-1205 wrapper's 6300 s, its
# box-wide admission allowance (LEG_ADMIT_WAIT_S) included. The
# queue's documented wrapper is QUEUE_WALL_S (+100 for rund), and a landing starts only while that
# whole worst case still fits, so the wrapper never kills a merge mid-step. A merge's resume of
# OTHER stranded records is not in it, exactly as it is not in the D-1205 wrapper.
LANDING_WORST_S = (
    QUEUE_WAIT_S + MERGE_TEST_BUDGET_S + LEG_ADMIT_WAIT_S + PUSH_TIMEOUT_S + SYNC_TIMEOUT_S + 300
)
# The wall also holds the chain build and the first wave: a leg of the longest limit any base may
# declare (_declared_leg clamps to MERGE_TEST_BUDGET_S) still leaves a worst-case landing. A wall
# with LANDING_WORST_S + 1800 landed nothing after a wave that used its limit (2026-10-27, elapsed
# ~1818 s at the check). A leg forks only while it AND a landing after it fit (_leg_fits — budgeted
# at TIMED_MARGIN x the longest green queue leg the run timed for that owner script once one is,
# W-1fb11ec8), and every
# leg a wall return joins (one per --jobs slot) ends inside the wall whatever it was budgeted at,
# because LANDING_WORST_S outweighs the longest declarable leg plus LEG_OVERHEAD_S. QUEUE_BUILD_S holds the chain
# build before the first fork plus LEG_OVERHEAD_S: a child's own setup (its throwaway worktree, the
# script read) and the leg's outer bound (+60). The _live_merge wait before a chain build (up to
# QUEUE_WAIT_S) is not in it: after it the first request may land through its locked leg instead.
QUEUE_BUILD_S = 300
LEG_OVERHEAD_S = 120
QUEUE_WALL_S = LANDING_WORST_S + MERGE_TEST_BUDGET_S + QUEUE_BUILD_S
# The sync runner's bounds (W-73d00b05, `_runner_scope`): it starts no sync past SOFT — one lock wait
# plus the longest process that keeps owing debts while it lives, a queue run — and its scope's
# RuntimeMaxSec backstop is SOFT + one whole sync + 60 s, so a runner that retires at SOFT is never
# the one the backstop kills mid-sync.
SYNC_RUNNER_SOFT_S = SYNC_LOCK_WAIT_S + QUEUE_WALL_S
SYNC_RUNNER_MAX_S = SYNC_RUNNER_SOFT_S + SYNC_TIMEOUT_S + 60


@contextlib.contextmanager
def _queue_lock(ctx: _Ctx) -> Iterator[None]:
    """``flock(LOCK_EX|LOCK_NB)`` on ``fabrik-merge/pretest/queue.lock``: one queue at a time. The
    forked leg children inherit the descriptor, so a killed parent still holds the lock until its
    children exit, and no second queue writes the same records beside them (Opus 6)."""
    (ctx.records / PRETEST_DIR).mkdir(parents=True, exist_ok=True)
    fd = os.open(ctx.records / PRETEST_DIR / "queue.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RefusedError("another merge --queue is running — nothing claimed") from None
        yield
    finally:
        os.close(fd)


def _pretest_ctx(ctx: _Ctx) -> _Ctx:
    pctx = _Ctx(ctx.main, ctx.common, ctx.owner)
    pctx.records = ctx.records / PRETEST_DIR
    pctx.pretesting = True
    return pctx


def _queue_entries(ctx: _Ctx, limit: int, landed: set[str] = frozenset()) -> list[dict]:
    """The waiting requests in the order ``merge`` takes them (``_owner_requests``), the first
    ``limit``. Read BEFORE the base (Opus 3): a merge landing between the two reads then shows as a
    base whose tree the chain does not hold, never as a request silently missing from it. ``ok`` is
    False for one the chain cannot build (an invalid body, a head not in this repo — the queue never
    fetches, which would race the locked merge's own fetch): it still lands, in order, through the
    locked merge, which refuses it or tests it itself."""
    out: list[dict] = []
    for fm in [fm for fm in _owner_requests(ctx) if fm.get("id") not in landed][:limit]:
        try:
            text = (_mail_root() / ctx.mailbox / "inbox" / f"{fm['id']}.md").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue  # claimed between the listing and the read
        fields = _split_message(text)[1]
        entry = {
            "id": fm["id"],
            **{k: fields.get(k, "") for k in ("branch", "head", "base", "item", "requester")},
        }
        entry["ok"], entry["why"] = True, ""
        try:
            _validate_request(entry)
            if not _rev(ctx.main, entry["head"]):
                raise RefusedError(f"head {entry['head'][:12]} is not in this repo")
        except RefusedError as exc:
            entry["ok"], entry["why"] = False, " ".join(str(exc).split())
        out.append(entry)
    return out


def _build_chain(ctx: _Ctx, entries: list[dict], base_tip: str) -> list[dict]:
    """Each entry with ``on`` (the chain tip it was built onto) and ``at`` (its stacked merge, or
    None when it cannot be built: invalid, another base, already in the tip, or a conflict). A
    request that will not build is SKIPPED and the chain continues from the same tip, because the
    locked merge refuses it and the next request lands on that tip (Opus 5)."""
    pctx = _pretest_ctx(ctx)
    rec: dict = {"id": f"queue.run-{os.getpid()}", **_claimer()}
    out: list[dict] = []
    base = entries[0]["base"] if entries else ""
    try:
        with _throwaway(pctx, rec, base_tip, _PRETEST_PREFIX) as wt:
            tip = base_tip
            for e in entries:
                el = {**e, "on": tip, "at": None}
                if not e["ok"] or e["base"] != base:
                    el["why"] = e["why"] or f"base {e['base']} is not the queue's {base}"
                elif _is_ancestor(ctx.main, e["head"], tip):
                    el["why"] = "already in the chain's tip"
                else:
                    try:
                        el["at"] = _build(pctx, wt, e["head"], f"queue pretest {e['branch']}", base)
                        tip = el["at"]
                    except RefusedError as exc:
                        el["why"] = " ".join(str(exc).split())
                        _run(["git", "merge", "--abort"], GIT_TIMEOUT_S, cwd=wt)
                        _gitc(wt, "reset", "-q", "--hard", tip)
                out.append(el)
    finally:
        (pctx.records / f"{rec['id']}.json").unlink(missing_ok=True)
    return out


def _skip_only_diff(cwd: Path, a: str, b: str) -> list[str] | None:
    """The paths two trees differ in OUTSIDE PRETEST_SKIP and work items — ``_pretested``'s
    tolerance — or None when git cannot compare them."""
    diff = _run(["git", "diff", "--name-only", "-z", "--no-renames", a, b], GIT_TIMEOUT_S, cwd=cwd)
    if diff.returncode:
        return None
    paths = [p for p in diff.stdout.split("\0") if p]
    return [p for p in paths if p not in PRETEST_SKIP and not _WORK_ITEM_RE.fullmatch(p)]


def _record_matches(ctx: _Ctx, el: dict, script: str, runner: str) -> bool:
    """A green record for ``el``'s head that the locked merge of ``el`` would trust already exists:
    its leg is not run again (Opus 1). The fields ``_pretested`` reads, checked the same way."""
    try:
        rec = json.loads(
            (ctx.records / PRETEST_DIR / f"{el['head']}.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    seconds = rec.get("seconds") if isinstance(rec, dict) else None
    if (
        not isinstance(rec, dict)
        or rec.get("green") is not True
        or rec.get("head") != el["head"]
        or not isinstance(rec.get("tree"), str)
        or not _TREE_RE.fullmatch(rec["tree"])
        or rec.get("script_sha256") != _script_sha(script)
        or rec.get("runner_sha256") != runner
        or isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < PRETEST_FLOOR_S
    ):
        return False
    return _skip_only_diff(ctx.main, rec["tree"], f"{el['at']}^{{tree}}") == []


def _tried_key(ctx: _Ctx, el: dict) -> tuple[str, str]:
    """``(head, stacked tree)``: a chain rebuild makes new elements and new stacked commits, but the
    same request on the same stack keeps its tree, so a failed leg is not forked again; one re-stacked
    onto a changed base (an earlier request refused) has a new tree and earns a fresh queue leg. An
    unreadable tree keys on the commit — a re-fork allowed, never a leg skipped. Cached on the
    element: the queue polls every QUEUE_POLL_S, and a rebuilt chain makes new elements."""
    if "tried_key" not in el:
        try:
            tree = _gitc(ctx.main, "rev-parse", f"{el['at']}^{{tree}}").strip()
        except RefusedError:
            tree = el["at"]
        el["tried_key"] = (el["head"], tree)
    return el["tried_key"]


def _leg_seconds(ctx: _Ctx, el: dict, script: str, runner: str) -> float:
    """The measured seconds of the queue leg that wrote ``el``'s matching record, else 0: a record
    the requester's own ``request --pretest`` wrote (no ``queued_as`` of this element) says nothing
    about the queue leg that just exited, and a red, killed or timed-out leg writes none."""
    if not _record_matches(ctx, el, script, runner):
        return 0.0
    try:
        rec = json.loads(
            (ctx.records / PRETEST_DIR / f"{el['head']}.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValueError):
        return 0.0
    if not isinstance(rec, dict) or rec.get("queued_as") != el["id"]:
        return 0.0
    seconds = rec.get("seconds")  # re-validated: the file may have been rewritten since the match
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return 0.0
    return float(seconds) if math.isfinite(seconds) and seconds > 0 else 0.0


def _run_leg(ctx: _Ctx, el: dict, runner: str) -> int:
    """One request's leg on its stacked merge ``el['at']`` (built on ``el['on']``); the body of a
    queue child. Green writes the record (atomically, ``_save``); nothing is unlinked first, so a
    valid record is never removed by a run that fails (Opus 1). 0 green, 1 anything else."""
    pctx = _pretest_ctx(ctx)
    script = _base_merge_tests(pctx, el["on"])
    rec: dict = {"id": f"{el['head']}.run-{os.getpid()}", **_claimer()}
    killed = (
        f"the queue's leg for {el['id']} timed out or was killed ({{}}) — not a test verdict; its "
        "locked merge runs the leg itself"
    )
    saved = os.environ.get("FABRIK_MERGE_TESTS_RECORDS")
    try:
        with tempfile.TemporaryDirectory(prefix="merge-pretest-records-") as private:
            os.environ["FABRIK_MERGE_TESTS_RECORDS"] = private
            with _throwaway(pctx, rec, el["at"], _PRETEST_PREFIX) as wt:
                summary, seconds = _pretest_leg(pctx, wt, el["on"], el["at"], killed)
                tree = _gitc(wt, "rev-parse", f"{el['at']}^{{tree}}").strip()
        _save(
            pctx,
            _pretest_record(
                el["head"], el["on"], tree, script, seconds, runner, queued_as=el["id"]
            ),
        )
    except RefusedError as exc:
        print(f"merge_request: queue leg {el['id']}: {' '.join(str(exc).split())}", file=sys.stderr)
        return 1
    finally:
        (pctx.records / f"{rec['id']}.json").unlink(missing_ok=True)
        if saved is None:
            os.environ.pop("FABRIK_MERGE_TESTS_RECORDS", None)
        else:
            os.environ["FABRIK_MERGE_TESTS_RECORDS"] = saved
    print(f"merge_request: queue leg {el['id']}: {summary} in {seconds}s", file=sys.stderr)
    return 0


def _leg_child(ctx: _Ctx, el: dict, runner: str) -> None:
    sys.exit(_run_leg(ctx, el, runner))


def _live_merge(ctx: _Ctx, mine: set[str]) -> str | None:
    """The id of a merge record ANOTHER live process is driving (short of ``replied``, its pid and
    start alive), or None. Never one this queue landed (``mine``) or one THIS process drives: a
    landing's ``merge`` resumes OTHER stranded records under its own pid, and one it leaves short of
    ``replied`` (a deferred remote, a failed reply) would read as live forever."""
    for path in sorted(ctx.records.glob("*.json")) if ctx.records.is_dir() else []:
        if path.stem in mine:
            continue
        try:
            rec = _load(ctx, path.stem)
        except RefusedError:
            continue
        own = rec and rec.get("pid") == os.getpid() and rec.get("start") == _proc_start(os.getpid())
        if rec and not own and rec.get("phase") not in DONE_PHASES and not _stranded(rec):
            return path.stem
    return None


def _land(msg_id: str) -> int:
    """``merge <id>`` — the unchanged locked path — waiting out a merge another process holds."""
    deadline = time.monotonic() + QUEUE_WAIT_S
    while True:
        try:
            return merge(argparse.Namespace(id=msg_id, queue=False, landing=True))
        except RefusedError as exc:
            if isinstance(exc, NotWaitingError):
                # another run took it between the queue's listing and this landing: not this
                # queue's to report, and the rest of the queue still lands
                print(f"merge_request: queue: {msg_id} was taken by another run", file=sys.stderr)
                return EXIT_OK
            if "another merge run holds" not in str(exc) or time.monotonic() > deadline:
                raise
            time.sleep(QUEUE_POLL_S)


TIMED_MARGIN = 1.5  # one hub leg ran 1037 s and 1365 s on the same commit under load (D-1312)


def _leg_fits(started: float, script: str, timed: float = 0.0) -> bool:
    """A leg forked now, plus LEG_OVERHEAD_S — its setup (an estimate: no deadline bounds it) and
    the leg's 60 s outer bound — can still be followed by a worst-case landing; else the leg cannot
    lead to a landing this run, and the wall return would only wait on it. The leg is budgeted at
    TIMED_MARGIN x ``timed``, the longest green queue leg this run already timed for this owner
    script (W-1fb11ec8: 697 s
    live against the hub's declared 2700 s, which closed the window at 1080 s of the 11100 s wall),
    capped at its whole limit (``_declared_leg``), and at that limit while nothing is timed. Either
    way the leg itself ends inside the wall: one forked at the last fit second that runs its whole
    limit ends by ``QUEUE_WALL_S - LANDING_WORST_S + limit``, and a landing's worst case outweighs
    any limit a base may declare plus LEG_OVERHEAD_S. A leg longer than the budget finishes after
    the last landing start: its request lands one run later on its record, and this run's children
    keep ``queue.lock`` until it ends."""
    limit = _declared_leg(script)
    leg = (min(TIMED_MARGIN * timed, limit) if timed > 0 else limit) + LEG_OVERHEAD_S
    return time.monotonic() - started + leg + LANDING_WORST_S <= QUEUE_WALL_S


def _past_wall(started: float, waiting: int) -> bool:
    """True, with the line saying so, when a landing's worst case no longer fits QUEUE_WALL_S."""
    if time.monotonic() - started + LANDING_WORST_S <= QUEUE_WALL_S:
        return False
    print(
        f"merge_request: queue: {waiting} request(s) still wait, and one more landing may not fit "
        f"the queue's {QUEUE_WALL_S}s wall — run `merge_request.py merge --queue` again",
        file=sys.stderr,
    )
    return True


def _queue(args: argparse.Namespace) -> int:
    """``merge --queue``: see the block comment above. Exit: the worst of the landings (0 all
    merged, 1 one refused, 4 one left partial — the queue stops there)."""
    ctx = _context(Path.cwd())
    jobs, limit = args.jobs, args.max
    started = time.monotonic()
    runner = _runner_sha()  # once, before any carry can rewrite this file (Opus 9)
    fork = multiprocessing.get_context("fork")
    running: dict[str, tuple] = {}  # head -> (its leg child, its element, its script)
    # the longest green queue leg this run timed, its recorded seconds, per owner script (_leg_fits):
    # a landing that changes `.fabrik/merge-tests` starts the next script at its declared limit
    timed: dict[str, float] = {}
    # every (head, stacked tree) a queue leg already ran for this run (_tried_key): a chain rebuild
    # makes new elements, so `leg_done` alone re-forked a failed leg after every landing
    tried: set[tuple[str, str]] = set()
    landed: set[str] = set()
    rc = EXIT_OK
    with _queue_lock(ctx):
        try:
            while True:
                deadline = time.monotonic() + QUEUE_WAIT_S
                while (live := _live_merge(ctx, landed)) and time.monotonic() < deadline:
                    time.sleep(QUEUE_POLL_S)  # a merge this queue did not start: wait it out
                if live:
                    raise RefusedError(f"merge {live} is still running after {QUEUE_WAIT_S}s")
                entries = _queue_entries(ctx, limit, landed)
                if not entries:
                    return rc
                base_tip = _rev(ctx.main, HEADS + entries[0]["base"])
                script = _base_merge_tests(ctx, base_tip) if base_tip else ""
                if _past_wall(started, len(entries)):
                    return rc
                if not base_tip or not script or _after_merge_due(ctx, script):
                    # no base, no owner tests, or the leg runs after the merge (D-1186): nothing
                    # runs outside the lock before landing; land in order
                    landed.add(entries[0]["id"])
                    rc = max(rc, _land(entries[0]["id"]))
                    if rc == EXIT_PARTIAL:
                        return rc
                    continue
                _sweep_pretests(_pretest_ctx(ctx), base_tip)
                chain = _build_chain(ctx, entries, base_tip)
                if _rev(ctx.main, HEADS + entries[0]["base"]) != base_tip:
                    continue  # the base moved while the chain was built: build it again
                first = chain[0]
                while True:
                    for head, (child, leg_el, leg_script) in list(running.items()):
                        if not child.is_alive():
                            child.join()
                            del running[head]
                            if child.exitcode == 0:
                                seconds = _leg_seconds(ctx, leg_el, leg_script, runner)
                                timed[leg_script] = max(timed.get(leg_script, 0.0), seconds)
                    # a later leg forks only once the first request lands on a record (or has no
                    # tree to test): else its locked merge runs its own leg, and a queue leg
                    # beside it halves both
                    first_on_record = first["at"] is None or _record_matches(
                        ctx, first, script, runner
                    )
                    # one budget answer per poll, read by the fork gate AND the landing test, so
                    # the two can never disagree about whether a leg still fits (review r1 B2)
                    fits = _leg_fits(started, script, timed.get(script, 0.0))
                    for el in chain:
                        if len(running) >= jobs:
                            break
                        if el["at"] is None or el["head"] in running:
                            continue
                        if (
                            _record_matches(ctx, el, script, runner)
                            or el.get("leg_done")
                            or _tried_key(ctx, el) in tried
                        ):
                            continue
                        if (el is not first and not first_on_record) or not fits:
                            break
                        child = fork.Process(target=_leg_child, args=(ctx, el, runner))
                        child.start()
                        running[el["head"]] = (child, el, script)
                        el["leg_done"] = True  # one leg per element per chain build
                        tried.add(_tried_key(ctx, el))  # and one per request and stack per run
                    if first["at"] is None or (
                        first["head"] not in running
                        and (
                            first.get("leg_done")
                            or _tried_key(ctx, first)
                            in tried  # no 2nd queue leg: its locked one runs
                            or _record_matches(ctx, first, script, runner)
                            or not fits
                        )
                    ):
                        # ready to land: its leg is over (green, red or killed), its record is
                        # reused, it is untestable, or no leg fits any more — without a record
                        # its locked merge runs its own leg, while a landing fits
                        break
                    time.sleep(QUEUE_POLL_S)
                if _past_wall(started, len(entries)):
                    return rc
                landed.add(first["id"])
                code = _land(first["id"])
                rc = max(rc, code)
                if code == EXIT_PARTIAL:
                    return rc
                # every later element was built on a tip that may not have landed: the next pass
                # rebuilds the chain on the new base and reuses each record that still matches
        finally:
            for child, *_ in running.values():
                child.join()  # a stale leg finishes; its record names a tree that never lands


def merge(args: argparse.Namespace) -> int:
    """``merge [<id>]`` — the merge owner's ONLY merge path (spec § The delta 5).

    Holds an exclusive ``flock`` on ``<git common dir>/fabrik-merge.lock`` for the whole run (a
    second run exits at once: nothing claimed, built or recorded); resumes every STRANDED record
    in ``<git common dir>/fabrik-merge/`` first (short of ``replied``, its pid dead or alive with
    a different start time); then takes the oldest inbox ``merge-request`` whose ``agent:`` IS
    the owner (``decisions.py --merge-owner``) with ``ack: required`` — or ``<id>`` — and claims
    it before building. Steps: (a) preflight in a throwaway worktree with a snapshot of every
    merged path; (b) pure-insertion ledger conflicts only; (c) the owner's tests; (d) re-hash and
    CAS the local base, rebuilding up to MAX_REBUILDS times; (e) carry; (f) fast-forward push;
    (g) the hub's governance sync, OWED here and run by a background runner outside the lock
    (W-4f4ac600; this run's end waits for it and prints its outcome); (h) reply to requester and
    coordinator, then ack.

    Exit: 0 merged (or nothing waiting) · 1 refused (acked ``blocked`` with the reason), DEFERRED
    (the remote was unreachable: claimed, nothing replied, retried by the next run), or the
    lock was held · 4 committed locally but not finished — run ``resume <id>``.
    Cobra note (D-253): the cheapest way past D-B is to ack without merging; ``mail.py ack done``
    refuses a merge SHA that is not in base, does not name the request, or lacks its head."""
    if getattr(args, "queue", False):
        if args.id:
            raise RefusedError("merge --queue takes no request id: it lands the queue in order")
        return _queue(args)
    ctx = _context(Path.cwd())
    with _merge_lock(ctx.common):
        _sweep_throwaways(ctx)
        try:
            rc = _resume_stranded(ctx)
            parked = _parked(ctx)
            if parked:
                # O11: origin is ahead of the local base while a catch-up is parked, so every
                # request would be refused "origin ahead" and its requester told to resend —
                # the inbox waits untouched until the owner resolves the parked one.
                for rec in parked:
                    base = rec.get("base") or "<base>"
                    try:  # O16: the remote the push goes to, resolved as the push resolves it
                        remote = _remote_name(ctx.main, base) if rec.get("base") else "origin"
                    except RefusedError:
                        remote = "<push remote>"
                    # the parked reason is _catch_up_refused's own instruction (a budget stop is a
                    # plain resume, never a hand merge); a record parked without one keeps the default
                    how = rec.get("reason") or (
                        f"merge {remote}/{base} into {base} by hand, then `merge_request.py resume "
                        f"{rec['id']}`"
                    )
                    print(
                        f"merge_request: request {rec['id']} is parked at catchup-refused — "
                        f"{how}; nothing claimed from the inbox until then",
                        file=sys.stderr,
                    )
                return EXIT_PARTIAL
            waiting = _owner_requests(ctx)
            if args.id:
                waiting = [fm for fm in waiting if fm.get("id") == args.id]
                if not waiting:
                    raise NotWaitingError(
                        f"no merge-request {args.id} addressed to {ctx.owner} in the inbox"
                    )
            if not waiting:
                print(f"no merge-request waiting for {ctx.owner} in {ctx.mailbox}")
                return rc
            if len(waiting) >= 2 and not args.id and not getattr(args, "landing", False):
                print(
                    f"merge_request: {len(waiting)} requests wait — `merge_request.py merge --queue` "
                    "runs their owner tests outside the merge lock (W-0c8c43f1)",
                    file=sys.stderr,
                )
            waiting = [fm for fm in waiting if _remote_of_request(ctx, fm) not in ctx.unreachable]
            if not waiting:
                print(
                    "merge_request: every waiting request is on a remote this run could not reach "
                    f"({', '.join(sorted(ctx.unreachable))}) — nothing claimed",
                    file=sys.stderr,
                )
                return rc
            rec = _claim(ctx, waiting[0]["id"])
            return max(rc, _drive(ctx, rec, resuming=False))
        finally:
            _sweep_throwaways(ctx)


def resume(args: argparse.Namespace) -> int:
    """``resume <id>`` — continue a request from its recorded phase (a record from a crash, a
    rejected push, a failed reply). With no record, the message is read (claimed first when it
    still sits in the inbox). A request whose ``head`` is already in base skips to (e)-(h) with
    its existing merge commit, found by the request id — never a second merge. A rejected push is
    finished by a catch-up merge of origin's base, exempt from the origin-ahead start refusal."""
    ctx = _context(Path.cwd())
    with _merge_lock(ctx.common):
        _sweep_throwaways(ctx)
        try:
            return _resume_locked(ctx, args.id)
        finally:
            _sweep_throwaways(ctx)


def _resume_locked(ctx: _Ctx, msg_id: str) -> int:
    rec = _load(ctx, msg_id)
    if rec is not None and rec.get("phase") == "claiming":
        rec.update(_claimer())
        rec = _continue_claiming(ctx, rec)
    if rec is None:
        box = _mail_root() / ctx.mailbox
        if (box / "inbox" / f"{msg_id}.md").is_file():
            rec = _claim(ctx, msg_id)
        else:
            path = box / "archive" / f"{msg_id}.md"
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise RefusedError(f"no request {msg_id} in {ctx.mailbox}: {exc}") from exc
            fm, fields = _split_message(text)
            addressee = _norm(fm.get("agent") or "")
            if fm.get("kind") != "merge-request" or addressee != _norm(ctx.owner):
                raise RefusedError(f"{msg_id} is not a merge-request addressed to {ctx.owner}")
            rec = _new_record(ctx, msg_id, fields)
    if rec.get("phase") in DONE_PHASES:
        print(f"{msg_id} is already replied ({rec.get('outcome', '?')})")
        return EXIT_OK
    rec.update(_claimer())
    _save(ctx, rec)
    return _drive(ctx, rec, resuming=True)


def retry(args: argparse.Namespace) -> int:
    """``retry <id>`` — re-run a REFUSED request from step (a), its branch unchanged (W-c751bca6).

    A refusal the base caused (owner tests red on the base alone, a file the throwaway lacked)
    used to cost the requester a re-send of an identical request: ``resume`` answers "already
    replied" and ``merge`` finds nothing waiting. ``retry`` refuses, with the record and the mail
    untouched, unless the record is ``replied`` with outcome ``refused``; no OTHER request for
    the same branch or head waits in the inbox or holds a record short of ``replied`` (a re-sent
    request supersedes this one — retrying it would merge the head and refuse the re-sent one
    "already in base"); and the branch on the push remote, read by ``ls-remote`` and never a local
    or tracking ref, still points at the recorded head (moved = superseded by the requester). An
    unreachable remote is a refusal here, never a deferral: nothing is claimed to defer.

    On pass the mail is re-opened with ``mail.py requeue`` (archive → inbox, its stale ``blocked``
    ack stripped) and claimed afresh, so a retried merge is acked ``done --merge-sha`` and checked
    like any other; the new record carries ``retries`` (each earlier refusal, timestamped) and the
    reply says it supersedes the refused one. The record is written ``claiming`` BEFORE the
    requeue, so a crash anywhere in between leaves a record the next run finishes.
    Exit: as ``merge``. Cobra note (D-253): the cheap way to a green retry is to mark the record
    merged; it runs every step from (a) and the ack's merge-SHA check runs on it."""
    ctx = _context(Path.cwd())
    with _merge_lock(ctx.common):
        _sweep_throwaways(ctx)
        try:
            return _retry_locked(ctx, args.id)
        finally:
            _sweep_throwaways(ctx)


def _retry_locked(ctx: _Ctx, msg_id: str) -> int:
    rec = _load(ctx, msg_id)
    if rec is None:
        raise RefusedError(f"no record of request {msg_id} — nothing was refused to retry")
    if rec.get("phase") not in DONE_PHASES or rec.get("outcome") != "refused":
        raise RefusedError(
            f"{msg_id} is {rec.get('phase', '?')} / {rec.get('outcome', 'no outcome')} — only a "
            f"refused request is retried; one short of `replied` is `merge_request.py resume "
            f"{msg_id}`, and a merged one has nothing to retry"
        )
    _validate_request(rec)  # its branch and head reach git argv below
    other = _superseding_request(ctx, rec)
    if other:
        raise RefusedError(
            f"request {other} for branch {rec['branch']} waits — a re-sent request supersedes "
            f"{msg_id}: `merge_request.py merge {other}` instead"
        )
    local = _rev(ctx.main, HEADS + rec["base"])
    if local and _rev(ctx.main, rec["head"]) and _is_ancestor(ctx.main, rec["head"], local):
        raise RefusedError(
            f"the head {rec['head'][:12]} of {msg_id} is already in {rec['base']} — merged under "
            "another request; nothing to retry"
        )
    remote = _remote_name(ctx.main, rec["base"])
    tip = _remote_tip(ctx, remote, rec["branch"])
    if tip is None:
        raise RefusedError(
            f"the branch {rec['branch']} is gone from {remote} — nothing to retry; the requester "
            "sends a new request"
        )
    if tip != rec["head"]:
        raise RefusedError(
            f"the branch {rec['branch']} moved to {tip[:12]} on {remote} since request {msg_id} "
            f"named {rec['head'][:12]}: the requester superseded it — they send a new request "
            "with its receipt"
        )
    retries = [*rec.get("retries", []), {"at": _now(), "reason": rec.get("reason", "")}]
    fresh = {
        "id": msg_id,
        "phase": "claiming",
        **{k: rec.get(k, "") for k in ("branch", "head", "base", "item", "requester", "review")},
        "retries": retries,
        **_claimer(),
    }
    _save(ctx, fresh)  # BEFORE the requeue: a crash between the two is re-opened by the next run
    try:
        fresh = _reopen(ctx, fresh)
    except RefusedError:
        if (_mail_root() / ctx.mailbox / "archive" / f"{msg_id}.md").is_file():
            _save(ctx, rec)  # the mail never moved: the refused record is restored as it was
        raise
    print(
        f"merge_request: retrying {msg_id} — it was refused: {rec.get('reason', '?')}",
        file=sys.stderr,
    )
    return _drive(ctx, fresh, resuming=False)


def _reopen(ctx: _Ctx, rec: dict) -> dict:
    """A retry's re-open: ``mail.py requeue`` (archive → inbox, the old ack stripped), then a
    fresh claim. Checks the requeued copy carries no ack: ``requeue`` leaves an undecodable
    message's ack in place, which would skip the merge's own ack."""
    res = _mail_cli(ctx, "requeue", rec["id"], "--repo", ctx.mailbox)
    if res.returncode != 0:
        raise RefusedError(
            f"mail.py requeue {rec['id']} failed: {res.stderr.strip() or res.returncode}; "
            "nothing changed"
        )
    if _acked(_mail_root() / ctx.mailbox / "inbox" / f"{rec['id']}.md"):
        raise _stale_ack(rec["id"])
    return _mail_claim(ctx, rec)


def _stale_ack(msg_id: str) -> RefusedError:
    """A retry's mail back in the inbox still carrying the refusal's ack: claiming it would merge
    and then skip the merge's own ack. The record stays ``claiming``, so every later run refuses
    here too (``_continue_claiming``) until the ack line is stripped by hand."""
    return RefusedError(
        f"{msg_id} still carries its old ack after `mail.py requeue` (undecodable bytes?) — "
        f"strip the `acked-by:` line by hand, then `merge_request.py resume {msg_id}`"
    )


def _acked(path: Path) -> bool:
    try:
        return bool(_mail()._ACK_LINE.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _superseding_request(ctx: _Ctx, rec: dict) -> str | None:
    """The id of ANOTHER merge-request for ``rec``'s branch or head that is still open: waiting
    in the inbox, or holding a record short of ``replied``. None when there is none."""

    def same(fields: dict) -> bool:
        return fields.get("branch") == rec["branch"] or fields.get("head") == rec["head"]

    box = _mail_root() / ctx.mailbox / "inbox"
    for fm in _owner_requests(ctx):
        other = fm.get("id", "")
        if other == rec["id"]:
            continue
        try:
            text = (box / f"{other}.md").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # claimed by another run between the listing and the read: its record shows
        if same(_split_message(text)[1]):
            return other
    for path in sorted(ctx.records.glob("*.json")) if ctx.records.is_dir() else []:
        if path.stem == rec["id"]:
            continue
        try:
            other = _load(ctx, path.stem)
        except RefusedError:
            continue
        if other and other.get("phase") not in DONE_PHASES and same(other):
            return path.stem
    return None


def _remote_tip(ctx: _Ctx, remote: str, branch: str) -> str | None:
    """``refs/heads/<branch>`` on ``remote`` as the remote says it NOW (``ls-remote``), or None
    when the remote has no such branch. Unreachable → a refusal: nothing is claimed yet."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    ref = HEADS + branch
    try:
        res = _run(["git", "ls-remote", remote, ref], REMOTE_TIMEOUT_S, cwd=ctx.main, env=env)
    except TimedOutError as exc:
        raise RefusedError(f"could not reach {remote} ({exc}); nothing changed") from exc
    if res.returncode != 0:
        raise RefusedError(
            f"could not reach {remote} (git ls-remote: {res.stderr.strip() or res.returncode}); "
            "nothing changed"
        )
    for line in res.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name == ref:
            return sha
    return None


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} is under 1")
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="merge_request.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("request", help="send the merge request for this worktree's branch")
    p.add_argument("--review", required=True, help="the closing run record or review receipt")
    p.add_argument("--item", help="the work item (W-xxxxxxxx) this branch finishes")
    p.add_argument("--base", help="the branch to merge into (default: config, else remote HEAD)")
    p.add_argument(
        "--pretest",
        action="store_true",
        help="run the base's .fabrik/merge-tests on the merge first and send only on green "
        "(a base without one is sent untested, with a note) (W-1fb11ec8)",
    )
    pm = sub.add_parser("merge", help="the merge owner: merge the oldest request addressed to it")
    pm.add_argument("id", nargs="?", help="a specific request id (keeps a plan's epic order)")
    pm.add_argument(
        "--queue",
        action="store_true",
        help="land the waiting requests in order, their owner tests run first OUTSIDE the merge "
        "lock on a stacked chain (W-0c8c43f1)",
    )
    pm.add_argument("--jobs", type=_positive_int, default=QUEUE_JOBS, help="--queue: legs at once")
    pm.add_argument(
        "--max", type=_positive_int, default=QUEUE_MAX, help="--queue: requests per pass"
    )
    pr = sub.add_parser("resume", help="continue a request from its recorded phase")
    pr.add_argument("id")
    pt = sub.add_parser("retry", help="re-run a refused request whose branch is unchanged")
    pt.add_argument("id")
    # internal: the background after-merge leg a deferred merge owes (D-1186, W-3237ba45)
    pa = sub.add_parser("after-merge-runner")
    pa.add_argument("--main", required=True, type=Path)
    # internal: the background governance sync a hub landing kicks (W-4f4ac600)
    ps = sub.add_parser("sync-runner")
    ps.add_argument("--state", required=True, type=Path)
    ps.add_argument("sync_argv", nargs=argparse.REMAINDER)
    # internal: git's merge driver for the ledgers, registered by install_post_commit_hook.sh
    pl = sub.add_parser("merge-ledger")
    for name in ("base", "ours", "theirs", "path"):
        pl.add_argument(name)
    args = ap.parse_args(argv)
    if args.cmd == "merge-ledger":  # before the verb table: main()'s sync drain never follows it
        try:
            _merge_ledger(args.base, args.ours, args.theirs, args.path)
        except Exception as exc:  # the || fallback turns this into git's ordinary markers
            print(f"merge_request: REFUSED — {exc}", file=sys.stderr)
            return EXIT_REFUSED
        return 0
    if args.cmd == "after-merge-runner":
        try:
            return _after_merge_runner(args.main)
        except Exception as exc:  # the status file is the runner's only reader
            with contextlib.suppress(OSError):
                common = Path(
                    _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=args.main)
                )
                _after_status(
                    _after_dir(common / "fabrik-merge"), rc=70, tail=f"runner crashed: {exc!r}"
                )
            return 70
    if args.cmd == "sync-runner":
        sync_argv = args.sync_argv[1:] if args.sync_argv[:1] == ["--"] else args.sync_argv
        if not sync_argv:
            ap.error("sync-runner needs the sync argv after --")
        try:
            return _sync_runner(args.state, sync_argv)
        except Exception as exc:  # recorded for the drain, whose stderr is the only reader
            with contextlib.suppress(OSError):
                _write_atomic(
                    args.state / SYNC_STATUS,
                    json.dumps({"at": time.time(), "rc": 70, "tail": f"runner crashed: {exc!r}"}),
                )
            return 70
    verb = {"request": request, "merge": merge, "resume": resume, "retry": retry}[args.cmd]
    try:
        return verb(args)
    except RefusedError as exc:
        print(f"merge_request: REFUSED — {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except MergePartialError as exc:
        print(f"merge_request: PARTIAL — {exc}", file=sys.stderr)
        return EXIT_PARTIAL
    finally:
        # the merge lock is released by now; a PARTIAL or REFUSED run drains too, and a drain that
        # cannot read its state never replaces the verb's exit code
        try:
            _drain_sync()
        except OSError as exc:
            print(
                f"merge_request: sync: unknown ({exc}) — the debt stays owed; run "
                "scripts/sync_enforcement_to_projects.py --force if no merge run follows",
                file=sys.stderr,
            )


if __name__ == "__main__":
    sys.exit(main())
