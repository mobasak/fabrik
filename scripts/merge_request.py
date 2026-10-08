#!/usr/bin/env python3
# AFTER-EDIT: tests/test_merge_request_send.py, tests/test_merge_request_merge.py, docs/reference/multi-agent-operating-model.md
"""merge_request — finishing work in a linked worktree sends ONE merge request; the merge owner
merges it through ONE data-safe path (stdlib-only).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 1-5, 8 and
§ Data-safety invariants.

    merge_request.py request --review <path> [--item <W-id>] [--base <branch>]
    merge_request.py merge [<id>]        # the merge owner: the oldest request addressed to it
    merge_request.py resume <id>         # continue a request from its recorded phase

``merge`` and ``resume`` are documented at ``merge()`` below; ``request`` here.

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
request would follow); check the inbox and finish by hand every step stderr lists after
``not done:`` — after an owner-send partial that is confirming the message landed, the distributor
copy and the ``--item`` release, none of which ran.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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


# --- (a)-(d): build, preflight, tests, CAS --------------------------------------------------
@contextlib.contextmanager
def _throwaway(ctx: _Ctx, rec: dict, commit: str) -> Iterator[Path]:
    """A detached worktree at ``commit`` under a scratch parent, named after the main checkout
    (``<tmp>/<repo basename>``) with a ``fabrik-lib`` link beside it when the main checkout's
    parent holds one (what the repo's tests reach as ``../fabrik-lib``). Removed and pruned on
    EVERY exit, success or refusal."""
    parent = Path(tempfile.mkdtemp(prefix=_THROWAWAY_PREFIX))
    wt = parent / ctx.main.name
    rec["worktree"] = str(wt)
    _save(ctx, rec)
    try:
        _gitc(
            ctx.main, "worktree", "add", "--detach", "-q", str(wt), commit, timeout=TOOL_TIMEOUT_S
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
        _remove_throwaway(ctx, wt)
        rec.pop("worktree", None)
        _save(ctx, rec)


_THROWAWAY_PREFIX = "fabrik-merge-"
# ``tempfile.mkdtemp`` appends 8 characters from this alphabet (CPython's _RandomNameSequence).
_THROWAWAY_DIR_RE = re.compile(r"^fabrik-merge-[a-z0-9_]{8}$")


def _owned_throwaway(ctx: _Ctx, wt: Path) -> bool:
    """O12: a worktree THIS tool created, and nothing wider — ``<temp root>/<mkdtemp dir>/<repo
    basename>``, the mkdtemp dir sitting DIRECTLY under the temp root ``_throwaway`` uses."""
    parent = wt.parent
    return (
        wt.name == ctx.main.name
        and bool(_THROWAWAY_DIR_RE.fullmatch(parent.name))
        and parent.parent.resolve() == Path(tempfile.gettempdir()).resolve()
    )


def _remove_throwaway(ctx: _Ctx, wt: Path) -> None:
    """Remove and prune one throwaway; the rmtree is ONLY the mkdtemp dir, and only when the
    path is one this tool created (``_owned_throwaway``) — never anything wider."""
    if not _owned_throwaway(ctx, wt):
        return
    _run(["git", *NO_HOOKS, "worktree", "remove", "--force", str(wt)], TOOL_TIMEOUT_S, cwd=ctx.main)
    shutil.rmtree(wt.parent, ignore_errors=True)
    _run(["git", "worktree", "prune"], GIT_TIMEOUT_S, cwd=ctx.main)


def _build(ctx: _Ctx, wt: Path, other: str, message: str, base: str) -> str:
    """(a)+(b): merge ``other`` into the throwaway's HEAD with ``message``; only pure-insertion
    conflicts on the five ledgers are auto-resolved. Returns the merge commit."""
    res = _run(
        ["git", *NO_HOOKS, "merge", "--no-ff", "--no-edit", "-q", "-m", message, other],
        TOOL_TIMEOUT_S,
        cwd=wt,
    )
    if res.returncode != 0:
        conflicted = [
            p for p in _gitc(wt, "diff", "--name-only", "-z", "--diff-filter=U").split("\0") if p
        ]
        if not conflicted:
            raise RefusedError(f"git merge failed: {res.stderr.strip() or res.stdout.strip()}")
        others = sorted(p for p in conflicted if p not in LEDGERS)
        if others:
            raise ConflictError(others, f"conflict in {', '.join(others)} — {_resend(base)}")
        for path in conflicted:
            stages: dict[str, str] = {}
            for entry in _gitc(wt, "ls-files", "-u", "-z", "--", path).split("\0"):
                meta, sep, _ = entry.partition("\t")
                if sep:
                    _, sha, stage = meta.split()
                    stages[stage] = sha
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


def _fallback_env(wt: Path, shim: Path) -> dict:
    """The fallback's env: the shim ALONE on ``PYTHONPATH`` — the caller's entries would precede the
    stdlib and could name the main checkout's own ``src``, so the import root comes from the
    throwaway, never the caller. It is the throwaway's ``src``, or its root when ``src`` is itself
    a package (imported as ``src.x``)."""
    root = wt if (wt / "src" / "__init__.py").exists() else wt / "src"
    return {**os.environ, "PYTHONPATH": str(shim), "FABRIK_MERGE_SRC": str(root)}


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
    refuses. Both legs first get the base's ``.worktreeinclude`` set (``_copy_worktree_include``)."""
    note = _copy_worktree_include(ctx, wt, old)
    if note and note not in ctx.notes:  # once per merge: this runs per rebuild and per catch-up
        ctx.notes.append(note)
    res = _run(["git", "show", f"{old}:.fabrik/merge-tests"], GIT_TIMEOUT_S, cwd=ctx.main)
    if res.returncode == 0 and res.stdout.strip():
        pythonpath = os.pathsep.join(
            p for p in (str(wt / "src"), os.environ.get("PYTHONPATH", "")) if p
        )
        env = {**os.environ, "PYTHONPATH": pythonpath}
        argv, label = ["sh", "-e", "-c", res.stdout], ".fabrik/merge-tests (base copy)"
        run = _run(argv, TEST_TIMEOUT_S, cwd=wt, env=env)
    else:
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
        venv = ctx.main / ".venv" / "bin" / "python"
        py = str(venv) if os.access(venv, os.X_OK) else sys.executable
        label = f"pytest {' '.join(touched)} under {py}"
        with tempfile.TemporaryDirectory(prefix="merge-shim-") as shim:
            Path(shim, "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
            env = _fallback_env(wt, Path(shim))
            run = _run([py, "-m", "pytest", "-q", *touched], TEST_TIMEOUT_S, cwd=wt, env=env)
    if run.returncode != 0:
        tail = " ".join((run.stdout + run.stderr).strip().splitlines()[-3:])
        why = f"; NOTE: {note}" if note else ""
        raise RefusedError(f"owner tests red ({label}, exit {run.returncode}): {tail}{why}")
    return f"{label}: green"


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
            tests = _owner_tests(ctx, wt, old, merged)
            if not catch_up:
                rec.update(phase="built", building=new)
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
                ["git", "update-ref", "-m", f"merge_request: {message}", HEADS + base, new, old],
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


def _fetch_base(ctx: _Ctx, remote: str, base: str) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    track = f"refs/remotes/{remote}/{base}"
    res = _run(
        ["git", "fetch", "-q", remote, f"+{HEADS}{base}:{track}"],
        REMOTE_TIMEOUT_S,
        cwd=ctx.main,
        env=env,
    )
    if res.returncode != 0:
        raise RefusedError(
            f"git fetch {remote} {base} failed: {res.stderr.strip() or res.returncode}"
        )
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
    """(g): in the HUB only, run the fleet sync when the re-derived merged file list matches the
    governance-sync filter (read from the merged base, never hard-coded)."""
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
    if not pattern:
        return (
            "sync: NOT RUN — the governance-sync files: filter is unreadable or empty; run "
            "scripts/sync_enforcement_to_projects.py --force yourself"
        )
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"sync: NOT RUN — the governance-sync filter does not compile ({exc})"
    hits = [p for p in files if rx.search(p)]
    if not hits:
        return "sync: no governance-sync path merged — none owed"
    try:
        run = _run(list(SYNC_ARGV), SYNC_TIMEOUT_S, cwd=ctx.main)
    except RefusedError as exc:
        return f"sync: FAILED ({exc}) — run scripts/sync_enforcement_to_projects.py --force"
    if run.returncode != 0:
        tail = " ".join((run.stderr or run.stdout).strip().splitlines()[-2:])
        return f"sync: FAILED (exit {run.returncode}: {tail}) — run scripts/sync_enforcement_to_projects.py --force"
    return f"sync: ran for {len(hits)} governance-sync path(s)"


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
            "never a rebase or a force-push: the branch is already pushed."
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


def _merge_message(ctx: _Ctx, rec: dict) -> str:
    return f"merge({ctx.owner}): {rec['branch']} — request {rec['id']}, item {rec.get('item') or 'none'}"


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
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    _run(
        ["git", "fetch", "-q", remote, HEADS + rec["branch"]],
        REMOTE_TIMEOUT_S,
        cwd=ctx.main,
        env=env,
    )
    if not _rev(ctx.main, rec["head"]):
        raise RefusedError(
            f"the request head {rec['head'][:12]} is not in this repo or on {remote}"
        )


def _merge_request_steps(ctx: _Ctx, rec: dict, remote: str) -> None:
    """(a)-(d) for the request itself; on success the record holds ``merged``."""
    step = "(a) preflight"
    try:
        _validate_request(rec)
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
        old, new, snap, tests, on_base = _merge_into_base(
            ctx, rec, rec["head"], _merge_message(ctx, rec), catch_up=False
        )
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
    message = f"merge({ctx.owner}): catch up {remote}/{rec['base']} after request {rec['id']}"
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
    return (
        f"the catch-up merge of {remote}/{base} into {base} refused ({why}); merge "
        f"{remote}/{base} into {base} by hand, then {resume_cmd}"
    )


def _after_cas(ctx: _Ctx, rec: dict, remote: str, resuming: bool) -> None:
    """(e)-(h): every step after the CAS. The merge is committed; nothing here undoes it."""
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
        _merge_request_steps(ctx, rec, remote)  # a start: the origin-ahead refusal applies
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
    if (box / "archive" / f"{rec['id']}.md").is_file():
        rec["phase"] = "claimed"
        _save(ctx, rec)
        return rec
    if (box / "inbox" / f"{rec['id']}.md").is_file():
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
    (g) the hub's governance sync; (h) reply to requester and coordinator, then ack.

    Exit: 0 merged (or nothing waiting) · 1 refused (acked ``blocked`` with the reason, or the
    lock was held) · 4 committed locally but not finished — run ``resume <id>``.
    Cobra note (D-253): the cheapest way past D-B is to ack without merging; ``mail.py ack done``
    refuses a merge SHA that is not in base, does not name the request, or lacks its head."""
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
                    print(
                        f"merge_request: request {rec['id']} is parked at catchup-refused — "
                        f"merge {remote}/{base} into {base} by hand, then `merge_request.py resume "
                        f"{rec['id']}`; nothing claimed from the inbox until then",
                        file=sys.stderr,
                    )
                return EXIT_PARTIAL
            waiting = _owner_requests(ctx)
            if args.id:
                waiting = [fm for fm in waiting if fm.get("id") == args.id]
                if not waiting:
                    raise RefusedError(
                        f"no merge-request {args.id} addressed to {ctx.owner} in the inbox"
                    )
            if not waiting:
                print(f"no merge-request waiting for {ctx.owner} in {ctx.mailbox}")
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="merge_request.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("request", help="send the merge request for this worktree's branch")
    p.add_argument("--review", required=True, help="the closing run record or review receipt")
    p.add_argument("--item", help="the work item (W-xxxxxxxx) this branch finishes")
    p.add_argument("--base", help="the branch to merge into (default: config, else remote HEAD)")
    pm = sub.add_parser("merge", help="the merge owner: merge the oldest request addressed to it")
    pm.add_argument("id", nargs="?", help="a specific request id (keeps a plan's epic order)")
    pr = sub.add_parser("resume", help="continue a request from its recorded phase")
    pr.add_argument("id")
    args = ap.parse_args(argv)
    verb = {"request": request, "merge": merge, "resume": resume}[args.cmd]
    try:
        return verb(args)
    except RefusedError as exc:
        print(f"merge_request: REFUSED — {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except MergePartialError as exc:
        print(f"merge_request: PARTIAL — {exc}", file=sys.stderr)
        return EXIT_PARTIAL


if __name__ == "__main__":
    sys.exit(main())
