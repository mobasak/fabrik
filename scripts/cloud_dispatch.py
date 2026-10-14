#!/usr/bin/env python3
# AFTER-EDIT: tests/test_cloud_dispatch.py, docs/workstation/cloud-dispatch.md, .fabrik/cloud-routines.json
"""Dispatch a task to a fleet account's claude.ai routine as a CLOUD subagent (D-857).

A local subagent spends the dispatching account's subscription; a cloud session spends that
account's promotional cloud credit first ($250 per Max account, expiring 2026-11-04). The one
scriptable way to start a cloud session is to fire a routine, so every fleet account carries one
routine ``fabrik-cloud-worker`` whose trigger id lives in ``.fabrik/cloud-routines.json``. This
script fires it, waits for the worker's branch and reads its log. Operator or hub session only —
it reads ``~/.claude-fleet``, which a review seat may not.

    cloud_dispatch.py list [--no-status] [--ledger-tail N]
    cloud_dispatch.py dispatch --slug <s> (--account <slug> | --pick) (--task "<text>" | --task-file <f>) [--force-new]
    cloud_dispatch.py wait --slug <s> [--since <sha>] [--timeout 1800] [--interval 15]
    cloud_dispatch.py log --account <slug> --session <id>
    (``--registry``, ``--fleet-root`` and ``--ledger`` go before or after the verb.)

Two fire paths. ``api``: when ``~/.claude-fleet/<slug>/routine-token`` exists (a 0600 regular file
with one link, holding the routine's bearer token as one printable line, minted once on
claude.ai/code/routines → Edit → Add trigger → API) the fire is one HTTPS POST and costs no local
quota; a 401 exits 3, a 429 exits 4, any other failure exits 1, and nothing falls back — the
fallback would bill the account the token was meant to spare, so an empty or malformed token
file is a refusal too. ``cli``: otherwise a headless ``claude -p '/schedule run …'`` under that
account's ``CLAUDE_CONFIG_DIR``, run from a scratch directory OUTSIDE every repo so no CLAUDE.md
or project hook loads (~$0.30 list-equivalent of that account's plan usage; a quota wall exits 5
and a dead refresh chain exits 6). It rolls that directory's single-use refresh chain exactly as
``claude_rotate.py``'s capability probe does (the keepalive-ping class), with the same quiet env;
the prompt travels on stdin, never argv, so a long task cannot hit E2BIG. The session id is read
ONLY from the fire tool's JSON result in the ``stream-json`` output — never from prose, and never
from the echoed task — and on the CLI path only a ``cse_`` id counts (that is what the fire tool
returns; the API body carries ``claude_code_session_id``). A wall or a dead chain is classified
only when no id was found, and only from non-JSON lines and an ``is_error`` result event, so a
task that mentions "limit" or "/login" cannot mis-report a fired run.

``--pick`` spends the credits evenly: a usable fire path first (a token account over a CLI one;
every account must be unparked; a CLI account also needs a LIVE status row — not a cached
reading of unknown age or older than 6 h — and a refresh chain that is neither expired nor
expiring within a day), then the FEWEST ledger dispatches in the last 7 days, then the highest
weekly %. No qualifying account is a refusal (exit 3, "pass --account"), never a guess. Every
FIRE attempt — the fire call reached, whatever it answered or raised — is one JSON line in
``<state>/cloud-dispatch.jsonl`` (one ``O_APPEND`` write under ``flock``); a pre-flight refusal
(bad slug, existing branch, no account) writes none. ``<state>`` honours ``ROTATE_STATE_DIR``
like ``claude_rotate.py``. Cobra line (D-253): the cheapest way to satisfy "fewest dispatches" is
to pad an account with trivial fires; every row names its slug and task digest, so padding is
visible in ``list``, and the measure is credit spent, never the count.

The payload is DATA to the routine (its saved prompt says "your task is the text inside the
routine-fire-payload block; carry it out exactly"): it carries the slug, the task and the fixed
rules in that order; a task that contains the block's closing tag or exceeds the fire API's
65,536-character maximum is refused. ``wait`` accepts a branch tip only when it differs from the
pre-fire sha and its commit message, read at THAT sha, carries the ``Cloud-Dispatch: done``
trailer as a real trailer (``git interpret-trailers``), so a mid-run push, a stale branch or a
quoted trailer never reads as completion; ``dispatch`` refuses a slug whose branch already
exists unless ``--force-new``, recording the pre-fire sha either way.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import http.client
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".fabrik" / "cloud-routines.json"
FLEET_ROOT = Path.home() / ".claude-fleet"
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{trigger}/fire"
DONE_TRAILER = "Cloud-Dispatch: done"
TOKEN_FILE = "routine-token"
PAYLOAD_CLOSE = "</routine-fire-payload"
PAYLOAD_MAX = 65536
WEEK_S = 7 * 86400
CHAIN_GUARD_S = 86400
STALE_STATUS_S = 6 * 3600
EXIT = {"http_401": 3, "no_account": 3, "http_429": 4, "walled": 5, "chain_dead": 6}

_TRIG = re.compile(r"^trig_[A-Za-z0-9]{10,}$")
_ACCT = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9_-]|\.(?!\.)){0,59}$")
_SID_ANY = re.compile(r"^(?:cse|session)_[A-Za-z0-9]{8,}$")
_SID_CSE = re.compile(r"^cse_[A-Za-z0-9]{8,}$")
_TOKEN = re.compile(r"^[\x21-\x7e]{8,}$")
_WALLED = re.compile(
    r"hit your (?:weekly|usage|5-hour|session) limit|usage limit reached|rate_limit_error", re.I
)
_CHAIN_DEAD = re.compile(
    r"oauth (?:session|token) (?:expired|revoked)|not logged in|run /login|authentication_error",
    re.I,
)

RULES = (
    "You are a dispatched cloud worker for the fabrik hub, NOT a hub agent: never claim work items, "
    "never answer the Stop hook's work queue, never read or send fabrik-mail.",
    "Work only inside this clone. If the task needs the test suite, first run "
    "`python3 -m pip install -q pytest` (and `python3 -m pip install -q -e .` when the imports need it).",
    "Commit your work and push it to the branch `claude/{slug}`; never push to master.",
    f"The LAST commit's message must end with the trailer line `{DONE_TRAILER} <your session id, or unknown>`.",
    "Finish with a summary naming the branch, the commit hash and whether the push succeeded.",
)


class RegistryError(Exception):
    """The registry is malformed; the message names the field."""


class DispatchError(Exception):
    """A dispatch cannot proceed; ``str(exc)`` starts with its status word and never carries a token."""


# --- registry -------------------------------------------------------------------------------------


def load_registry(path: Path = REGISTRY) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RegistryError(f"registry {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise RegistryError(f"registry {path}: version must be 1")
    accounts = data.get("accounts")
    if not isinstance(accounts, dict) or not accounts:
        raise RegistryError(f"registry {path}: accounts must be a non-empty object")
    for slug, entry in accounts.items():
        if not isinstance(slug, str) or not _ACCT.fullmatch(slug):
            raise RegistryError(f"registry {path}: account {slug!r} is not a fleet slug")
        trig = entry.get("trigger") if isinstance(entry, dict) else None
        if not isinstance(trig, str) or not _TRIG.fullmatch(trig):
            raise RegistryError(f"registry {path}: account {slug}: trigger must match trig_<id>")
    return data


# --- payload --------------------------------------------------------------------------------------


def valid_slug(slug: object) -> bool:
    """A slug git accepts as the branch ``claude/<slug>``: the regex plus git's own refusals of a
    component ending in ``.`` or ``.lock``."""
    return (
        isinstance(slug, str)
        and _SLUG.fullmatch(slug) is not None
        and not slug.endswith(".")
        and not slug.endswith(".lock")
    )


def render_payload(slug: str, task: str) -> str:
    if not valid_slug(slug):
        raise DispatchError(
            f"error: slug {slug!r} is not a branch name: [a-z0-9][a-z0-9._-]{{0,59}}, no '..', "
            "no trailing '.' or '.lock'"
        )
    if PAYLOAD_CLOSE in task:
        raise DispatchError(
            f"error: the task contains `{PAYLOAD_CLOSE}`, which would end the payload block early"
        )
    rules = "\n".join(f"- {r.format(slug=slug)}" for r in RULES)
    payload = f"TASK slug {slug}.\n\n{task.strip()}\n\nRules:\n{rules}\n"
    if len(payload) > PAYLOAD_MAX:
        raise DispatchError(
            f"error: the payload is {len(payload)} characters; the fire API accepts at most {PAYLOAD_MAX}"
        )
    return payload


# --- fire paths -----------------------------------------------------------------------------------


def read_token(slug: str, fleet_root: Path) -> str | None:
    """The routine bearer token for ``slug``, or None when no token file exists. The file is
    opened without following links and judged by its open descriptor: a regular file, mode 0600,
    owned by this user, with exactly one link, holding one printable line. Anything else is a
    refusal — the rotation machinery copies credential files around, and a token must never
    ride that path or fall back to the paid CLI."""
    p = Path(fleet_root) / slug / TOKEN_FILE
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:  # O_NOFOLLOW on a symlink
            raise DispatchError(f"error: {p}: a symlink is not accepted as a token file") from exc
        raise DispatchError(f"error: {p}: cannot open the token file ({exc.strerror})") from exc
    try:
        st = os.fstat(fd)
        if (
            not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode) != 0o600
            or st.st_uid != os.getuid()
        ):
            raise DispatchError(
                f"error: {p}: the token file must be a regular file, mode 0600, owned by you"
            )
        if st.st_nlink != 1:
            raise DispatchError(
                f"error: {p}: the token file has {st.st_nlink} links; exactly one is accepted"
            )
        try:
            raw = os.read(fd, 4096).decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise DispatchError(f"error: {p}: the token file is not UTF-8 text") from exc
    finally:
        os.close(fd)
    if not _TOKEN.fullmatch(raw):
        raise DispatchError(
            f"error: {p}: the token must be one printable line of at least 8 characters"
        )
    return raw


def fire_path(slug: str, fleet_root: Path = FLEET_ROOT) -> str:
    return "api" if read_token(slug, fleet_root) else "cli"


def _http_post(url: str, headers: dict, body: str) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — a fixed https host
            return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), dict(exc.headers or {})


def fire_api(
    slug: str, trigger: str, payload: str, fleet_root: Path = FLEET_ROOT
) -> tuple[str, str | None]:
    """Fire through the routine's API trigger. Returns ``(session_id, url)``."""
    token = read_token(slug, fleet_root)
    if not token:
        raise DispatchError(f"error: {slug}: no token file")
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        status, text, resp_headers = _http_post(
            FIRE_URL.format(trigger=trigger), headers, json.dumps({"text": payload})
        )
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        raise DispatchError(f"error: fire request failed for {slug}: {type(exc).__name__}") from exc
    if status == 401:
        raise DispatchError(
            f"http_401: routine token rejected for {slug}; regenerate it on claude.ai/code/routines"
        )
    if status == 429:
        raise DispatchError(
            f"http_429: fire limit reached for {slug}; Retry-After {resp_headers.get('Retry-After', '?')} s"
        )
    if not 200 <= status < 300:
        raise DispatchError(f"http_{status}: fire failed for {slug}: {text[:300]}")
    sid = parse_session_id(text)
    if not sid:
        raise DispatchError(f"unparsed: fire answered {status} without a session id: {text[:300]}")
    url = None
    try:
        url = json.loads(text).get("claude_code_session_url")
    except (ValueError, AttributeError):
        pass
    return sid, url


def _run_claude(argv: list[str], env: dict, cwd: Path, stdin_text: str = "") -> tuple[int, str]:
    run = subprocess.run(
        argv,
        env=env,
        cwd=cwd,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return run.returncode, run.stdout + run.stderr


def _account_env(cfg: Path) -> dict:
    env = {
        **os.environ,
        "CLAUDE_CONFIG_DIR": str(cfg),
        "CLAUDE_QUOTA_HOME": str(cfg),
        "CLAUDE_MESH_HEADLESS": "1",
        "CLAUDE_SOUND_NO_REVIVE": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    return env


def scratch_dir() -> Path:
    """Where a headless turn runs: under the state dir, outside every git repo, so no CLAUDE.md
    or project hook loads (the hub's would cost ~$2.65 per turn and offer the worker its queue)."""
    p = state_dir() / "cloud-dispatch-scratch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fire_cli(
    slug: str,
    trigger: str,
    payload: str,
    fleet_root: Path = FLEET_ROOT,
    scratch: Path | None = None,
) -> str | None:
    """Fire through a headless ``claude -p '/schedule run …'`` under the account's config dir.
    Returns the ``cse_`` session id, or None with the raw tail in ``fire_cli.last_output``; a wall
    or a dead chain, judged only when no id came back, raises. Every subprocess failure is a
    ``DispatchError`` so the attempt is ledgered."""
    scratch = Path(scratch) if scratch else scratch_dir()
    scratch.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"/schedule run the routine with trigger id {trigger} NOW, passing this run text verbatim as the "
        f"text field, then print only the session id the run call returned; do not wait for the run:\n\n{payload}"
    )
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"]
    try:
        _rc, out = _run_claude(
            argv, _account_env(Path(fleet_root) / slug), scratch, stdin_text=prompt
        )
    except subprocess.TimeoutExpired as exc:
        raise DispatchError(
            f"error: the headless fire for {slug} exceeded {exc.timeout:.0f}s"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchError(
            f"error: the headless fire for {slug} could not run: {type(exc).__name__}"
        ) from exc
    fire_cli.last_output = out[-800:]  # type: ignore[attr-defined]
    sid = parse_session_id(out, cli=True)
    if sid:
        return sid
    refusal = _refusal_text(out)
    if _WALLED.search(refusal):
        raise DispatchError(f"walled: {slug} is at its usage limit; the CLI fire was refused")
    if _CHAIN_DEAD.search(refusal):
        raise DispatchError(f"chain_dead: {slug} needs a /login; the CLI fire was refused")
    return None


def _refusal_text(out: str) -> str:
    """The parts of a headless turn's output a refusal lands in: lines that are not JSON events
    (stderr, the CLI's own errors) and the ``result`` event's text when it is flagged an error.
    The echoed prompt and the model's prose are excluded on purpose."""
    parts = []
    for line in out.splitlines():
        s = line.strip()
        if not s.startswith("{"):
            parts.append(s)
            continue
        try:
            obj = json.loads(s)
        except ValueError:
            parts.append(s)
            continue
        if isinstance(obj, dict) and obj.get("type") == "result" and obj.get("is_error"):
            parts.append(str(obj.get("result", "")))
    return "\n".join(parts)


def parse_session_id(text: str, *, cli: bool = False) -> str | None:
    """The fire's session id — a ``session_id``/``claude_code_session_id`` field in a JSON body,
    or in a stream-json ``tool_result`` (its ``content`` may itself be a JSON string). Never from
    prose: an id named in the task text is echoed in the ``tool_use`` input and must not count.
    On the CLI path only ``cse_…`` is accepted — the fire tool's shape."""
    pat = _SID_CSE if cli else _SID_ANY
    stripped = text.strip()
    if stripped.startswith("{") and "\n" not in stripped:
        try:
            return _sid_in(json.loads(stripped), pat, in_result=True)
        except ValueError:
            return None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        found = _sid_in(obj, pat, in_result=False)
        if found:
            return found
    return None


def _sid_in(obj: object, pat: re.Pattern, *, in_result: bool) -> str | None:
    """Walk a JSON value; ids count only inside a ``tool_result`` block (or the whole object when
    ``in_result``, the API body case), never inside ``tool_use`` input."""
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            return None
        here = in_result or obj.get("type") == "tool_result"
        if here:
            for key in ("claude_code_session_id", "session_id"):
                val = obj.get(key)
                if isinstance(val, str) and pat.fullmatch(val):
                    return val
        for val in obj.values():
            found = _sid_in(val, pat, in_result=here)
            if found:
                return found
    elif isinstance(obj, list):
        for val in obj:
            found = _sid_in(val, pat, in_result=in_result)
            if found:
                return found
    elif isinstance(obj, str) and in_result and obj.lstrip().startswith(("{", "[")):
        try:
            return _sid_in(json.loads(obj), pat, in_result=True)
        except ValueError:
            return None
    return None


# --- pick -----------------------------------------------------------------------------------------


def fleet_status() -> dict | None:
    """``claude_rotate.py --status --json`` (a live probe), or None when it cannot be read."""
    try:
        run = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sysadmin" / "claude_rotate.py"),
                "--status",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        data = json.loads(run.stdout) if run.returncode == 0 else None
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _status_rows(status: dict | None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for row in (status or {}).get("accounts") or []:
        if not isinstance(row, dict):
            continue
        for s in row.get("slugs") or []:
            if isinstance(s, str):
                rows[s] = row
    return rows


def _num(val: object) -> float | None:
    try:
        return float(val) if val is not None and not isinstance(val, bool) else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _has_token(slug: str, fleet_root: Path) -> bool:
    try:
        return bool(read_token(slug, fleet_root))
    except DispatchError:
        return False


def pick_account(
    registry: dict,
    status: dict | None,
    ledger_rows: list[dict],
    fleet_root: Path,
    now: float | None = None,
) -> tuple[str, str]:
    """The account to fire, with the reason; raises ``DispatchError("no_account: …")`` when none qualifies."""
    now = time.time() if now is None else now
    slugs = list(registry["accounts"])
    rows = _status_rows(status)
    recent = dict.fromkeys(slugs, 0)
    for r in ledger_rows:
        if not isinstance(r, dict):
            continue
        ts = _num(r.get("ts"))
        if r.get("account") in recent and ts is not None and ts >= now - WEEK_S:
            recent[r["account"]] += 1
    candidates: list[tuple[tuple, str, str]] = []
    for s in slugs:
        has_token = _has_token(s, fleet_root)
        row = rows.get(s)
        if row is not None and row.get("parked"):
            continue
        if not has_token:
            if row is None:
                continue
            age = _num(row.get("age_s"))
            if row.get("source") != "live" and (age is None or age > STALE_STATUS_S):
                continue
            exp = _num(row.get("refresh_expires_epoch"))
            if exp is None or exp - now < CHAIN_GUARD_S:
                continue
        seven = (row or {}).get("seven_day")
        weekly = _num(seven.get("utilization")) if isinstance(seven, dict) else None
        weekly = -1.0 if weekly is None else weekly
        candidates.append(
            (
                (0 if has_token else 1, recent[s], -weekly),
                s,
                f"{'token' if has_token else 'cli'} path, {recent[s]} dispatch(es) this week, weekly {weekly:.0f}%",
            )
        )
    if not candidates:
        raise DispatchError(
            "no_account: no registered account qualifies (parked, stale status, dead or expiring chain, "
            "no token) — pass --account"
        )
    candidates.sort()
    _key, s, why = candidates[0]
    return s, why


# --- wait -----------------------------------------------------------------------------------------


def _git(*args: str, timeout: float = 60) -> str:
    run = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )
    return run.stdout


def _ls_remote(branch: str) -> str:
    return _git("ls-remote", "--heads", "origin", branch)


def _tip_message(branch: str, sha: str) -> str:
    """The commit message at ``sha`` on ``branch``: fetched into a private ref (never FETCH_HEAD,
    which another wait in the same repo can overwrite between fetch and read) and read at the
    exact sha ``ls-remote`` reported, so the message and the sha belong to the same commit."""
    _git("fetch", "-q", "origin", f"+refs/heads/{branch}:refs/cloud-dispatch/{branch}", timeout=120)
    return _git("log", "-1", "--format=%B", sha, timeout=30)


def has_done_trailer(message: str) -> bool:
    """True when the message carries ``Cloud-Dispatch: done …`` as a real git trailer, or as its
    last non-empty line (the rule says "end with the trailer line"; a worker that writes it right
    under the subject with no blank line is obeying it, though git would not parse it). A trailer
    quoted inside an earlier line never counts."""
    lines = [ln.rstrip() for ln in message.splitlines() if ln.strip()]
    if lines and lines[-1].startswith(DONE_TRAILER):
        return True
    run = subprocess.run(
        ["git", "interpret-trailers", "--parse"],
        input=message,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return any(line.startswith(DONE_TRAILER) for line in run.stdout.splitlines())


_HEX = re.compile(r"^[0-9a-f]{7,40}$")


def same_commit(sha: str, since: str | None) -> bool:
    """``since`` names the same commit as ``sha`` — a full or abbreviated (≥ 7 hex) sha."""
    return bool(since) and _HEX.fullmatch(str(since)) is not None and sha.startswith(str(since))


def wait_for_branch(
    slug: str, timeout: float = 1800, interval: float = 15, since: str | None = None
) -> str | None:
    """The sha of ``claude/<slug>`` once its tip differs from ``since`` (the pre-fire sha) and its
    commit message carries the done trailer; None on timeout."""
    branch = f"claude/{slug}"
    interval = max(1.0, float(interval))
    deadline = time.monotonic() + max(0.0, float(timeout))
    while True:
        out = _ls_remote(branch)
        if out.strip():
            sha = out.split()[0]
            if not same_commit(sha, since) and has_done_trailer(_tip_message(branch, sha)):
                return sha
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


# --- ledger ---------------------------------------------------------------------------------------


def state_dir() -> Path:
    return Path(os.environ.get("ROTATE_STATE_DIR") or (Path.home() / ".claude" / "state"))


def append_ledger(path: Path, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as fh:  # one O_APPEND write per row
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def read_ledger(path: Path) -> list[dict]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def last_dispatch(rows: list[dict], slug: str) -> dict | None:
    for r in reversed(rows):
        if r.get("slug") == slug:
            return r
    return None


# --- CLI ------------------------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    rows = _status_rows(None if args.no_status else fleet_status())
    print(f"registry {args.registry} · routine {reg.get('routine')} · repo {reg.get('repo')}")
    for s, entry in reg["accounts"].items():
        row = rows.get(s)
        seven = (row or {}).get("seven_day")
        weekly = seven.get("utilization") if isinstance(seven, dict) else None
        standing = (
            "no status"
            if row is None
            else (
                "PARKED"
                if row.get("parked")
                else f"weekly {weekly if weekly is not None else '?'}%"
            )
        )
        try:
            path = fire_path(s, args.fleet_root)
        except DispatchError as exc:
            path = f"token REFUSED ({exc})"
        print(
            f"  {s:<12} {entry['trigger']}  {path:<5} {standing}  github: {entry.get('github', '?')}"
        )
    for r in read_ledger(args.ledger)[-args.ledger_tail :] if args.ledger_tail else []:
        print(
            f"  ledger {r.get('ts_iso', '?')} {r.get('account')} {r.get('slug')} {r.get('status')} "
            f"{r.get('session_id')} {r.get('url') or ''}"
        )
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    task = Path(args.task_file).read_text(encoding="utf-8") if args.task_file else args.task
    try:
        payload = render_payload(args.slug, task)
    except DispatchError as exc:
        print(f"cloud_dispatch: {exc}", file=sys.stderr)
        return 1
    branch = f"claude/{args.slug}"
    try:
        existing = _ls_remote(branch).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"cloud_dispatch: error: cannot read origin ({type(exc).__name__})", file=sys.stderr)
        return 1
    pre_sha = existing.split()[0] if existing else None
    if existing and not args.force_new:
        print(
            f"cloud_dispatch: {branch} already exists on origin ({pre_sha}); pick another slug or pass --force-new",
            file=sys.stderr,
        )
        return 1
    try:
        if args.account:
            if args.account not in reg["accounts"]:
                raise DispatchError(f"error: {args.account} is not in the registry")
            account, why = args.account, "named"
        else:
            account, why = pick_account(
                reg, fleet_status(), read_ledger(args.ledger), args.fleet_root
            )
    except DispatchError as exc:
        print(f"cloud_dispatch: {exc}", file=sys.stderr)
        return EXIT.get(str(exc).split(":", 1)[0], 1)
    trigger = reg["accounts"][account]["trigger"]
    row = {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "account": account,
        "trigger": trigger,
        "slug": args.slug,
        "branch": branch,
        "pre_fire_sha": pre_sha,
        "picked": why,
        "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest()[:16],
        "session_id": None,
        "url": None,
        "via": None,
        "status": None,
    }
    try:
        via = fire_path(account, args.fleet_root)
        row["via"] = via
        if via == "api":
            row["session_id"], row["url"] = fire_api(account, trigger, payload, args.fleet_root)
        else:
            row["session_id"] = fire_cli(account, trigger, payload, args.fleet_root)
            if not row["session_id"]:
                print(
                    "cloud_dispatch: no session id in the fire output; tail:\n"
                    f"{getattr(fire_cli, 'last_output', '')}",
                    file=sys.stderr,
                )
        row["status"] = "ok" if row["session_id"] else "unparsed"
        rc = 0 if row["session_id"] else 1
    except DispatchError as exc:
        msg = str(exc)
        row["status"] = msg.split(":", 1)[0]
        print(f"cloud_dispatch: {msg}", file=sys.stderr)
        rc = EXIT.get(row["status"], 1)
    append_ledger(args.ledger, row)
    print(json.dumps(row, sort_keys=True))
    return rc


def _cmd_wait(args: argparse.Namespace) -> int:
    since = args.since
    if since is not None and not _HEX.fullmatch(since):
        print("cloud_dispatch: --since must be a 7-40 hex sha", file=sys.stderr)
        return 1
    if since is None:
        last = last_dispatch(read_ledger(args.ledger), args.slug)
        since = (last or {}).get("pre_fire_sha")
    try:
        sha = wait_for_branch(args.slug, timeout=args.timeout, interval=args.interval, since=since)
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"cloud_dispatch: error: git failed while waiting ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1
    if sha:
        print(sha)
        return 0
    print(
        f"cloud_dispatch: claude/{args.slug} carried no `{DONE_TRAILER}` tip newer than "
        f"{since or 'none'} within {args.timeout:g}s; read the run with `log`",
        file=sys.stderr,
    )
    return 2


def _cmd_log(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    if args.account not in reg["accounts"]:
        print(f"cloud_dispatch: {args.account} is not in the registry", file=sys.stderr)
        return 1
    if not _SID_ANY.fullmatch(args.session):
        print("cloud_dispatch: --session must be a cse_/session_ id", file=sys.stderr)
        return 1
    prompt = (
        f"/schedule read the run log of session {args.session} with get_run_log and print it verbatim: "
        "the env lines, every tool_use and tool_result line, and the final result. Do not fire anything."
    )
    try:
        rc, out = _run_claude(
            ["claude", "-p", "--output-format", "json"],
            _account_env(Path(args.fleet_root) / args.account),
            scratch_dir(),
            stdin_text=prompt,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"cloud_dispatch: error: the headless log read could not run ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1
    try:
        print(json.loads(out.strip().splitlines()[-1]).get("result", out))
    except (ValueError, IndexError):
        print(out)
    return 0 if rc == 0 else 1


def main(argv: list[str] | None = None) -> int:
    def common(sub: bool) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(add_help=False)
        d = argparse.SUPPRESS if sub else None
        p.add_argument("--registry", type=Path, default=d)
        p.add_argument("--fleet-root", type=Path, default=d)
        p.add_argument(
            "--ledger", type=Path, default=d, help="default: <state>/cloud-dispatch.jsonl"
        )
        return p

    ap = argparse.ArgumentParser(
        prog="cloud_dispatch.py",
        description=__doc__.split("\n\n", 1)[0],
        parents=[common(False)],
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", parents=[common(True)])
    p.add_argument(
        "--no-status", action="store_true", help="registry only; skip the live fleet probe"
    )
    p.add_argument("--ledger-tail", type=int, default=5)
    p.set_defaults(fn=_cmd_list)
    p = sub.add_parser("dispatch", parents=[common(True)])
    p.add_argument("--slug", required=True, help="the branch is claude/<slug>")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--account")
    g.add_argument("--pick", action="store_true")
    g2 = p.add_mutually_exclusive_group(required=True)
    g2.add_argument("--task")
    g2.add_argument("--task-file")
    p.add_argument(
        "--force-new",
        action="store_true",
        help="fire even when claude/<slug> already exists on origin",
    )
    p.set_defaults(fn=_cmd_dispatch)
    p = sub.add_parser("wait", parents=[common(True)])
    p.add_argument("--slug", required=True)
    p.add_argument(
        "--since",
        default=None,
        help="the pre-fire sha to wait past (default: the ledger's last row for the slug)",
    )
    p.add_argument("--timeout", type=float, default=1800)
    p.add_argument("--interval", type=float, default=15)
    p.set_defaults(fn=_cmd_wait)
    p = sub.add_parser("log", parents=[common(True)])
    p.add_argument("--account", required=True)
    p.add_argument("--session", required=True)
    p.set_defaults(fn=_cmd_log)
    args = ap.parse_args(argv)
    args.registry = args.registry or REGISTRY
    args.fleet_root = args.fleet_root or FLEET_ROOT
    args.ledger = args.ledger or state_dir() / "cloud-dispatch.jsonl"
    try:
        return args.fn(args)
    except RegistryError as exc:
        print(f"cloud_dispatch: {exc}", file=sys.stderr)
        return 1
    except DispatchError as exc:
        print(f"cloud_dispatch: {exc}", file=sys.stderr)
        return EXIT.get(str(exc).split(":", 1)[0], 1)


if __name__ == "__main__":
    sys.exit(main())
