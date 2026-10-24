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
    cloud_dispatch.py settle (--slug <s> | --all)
    cloud_dispatch.py pause <slug> --reason "<why>" · unpause <slug> · calibrate <slug> --balance <usd>
    cloud_dispatch.py drain --batch <file.json> [--max-open 10] [--dry-run] [--allow-plan-usage]
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

The CREDIT GUARD (operator 2026-10-14: "when credits consumed, it must be paused"; "weekly usage
is different than cloud 250$ credits"). ``settle`` reads a run's raw events
(``GET /v1/code/sessions/<cse>/events``, newest first) with the account's OAuth ACCESS token
(``~/.claude-fleet/<slug>/.credentials.json``, read under the same descriptor checks as the
routine token, never printed) and ledgers a ``kind: settle`` row carrying the newest ``result``
event's cumulative ``total_cost_usd`` (Claude Code's list-price estimate), the token counts and
the last ``rate_limit_info`` verbatim. A standby account's access token lapses within hours and
no script-side refresh exists (the grant is CLI-only), so when ``expiresAt`` has passed and a
settle is owed, ONE in-place ``claude -p ok --max-turns 1 --tools ""`` from the scratch dir rolls
that dir's chain (the capability-probe class; sub-cent of plan, ledgered as ``kind:
token_refresh``, at most once per account per 8 h); a run that still cannot be read is ledgered
``settle_pending`` and the next ``settle --all`` (which ``dispatch`` runs first) retries it.
Spend per account = the latest real-cost settle per fired session, every fired session with no
real cost yet PROVISIONED at the margin from the moment of dispatch (never a free window), plan-usage
rows excluded, on top of a ``calibrate`` row when the operator has copied the web balance
(claude.ai/settings/usage, the only place it is visible): spent = (claimed − balance) + the rows
fired after it. The margin is ``max($10, 10 % of claimed)`` — the estimate is not Anthropic's
ledger and parallel runs pass the check in flight. Pause state is LEDGER rows (``kind:
pause|unpause``, latest wins) under the same flock — never the git-tracked registry, which a
worktree, a checkout or a merge would silently un-pause; the registry holds only the static
``credit: {claimed_usd, expires}`` and an optional ``credit_margin_usd``. An account is paused
when spent ≥ claimed − margin or the run drew on overage (``isUsingOverage`` — recorded, not yet
trusted: the captured probe shows overage DISABLED on these accounts); a plan-reading rise on an
idle account is ADVISORY only (the browser, a CLI fire and ``log`` all move it). ``dispatch`` and
``--pick`` refuse a paused account and any account within 6 h of 00:00 UTC on its ``expires``
date (exit 7, told apart by text); ``--allow-plan-usage`` bypasses both, picks the COOLEST weekly
reading and tags the row ``plan_usage: true`` so its settle never counts against the credit.
Cobra line (D-253): the cheapest way to read "never paused" is to never settle — which is why an
unsettled run is charged at the margin, not at zero.

``drain`` (W-b00d9d72) fires a lead-written batch — a JSON list of ``{"slug", "task" |
"task_file", "files"}`` — after a whole-batch pre-flight that fails CLOSED (exit 8, nothing fired,
nothing ledgered): every task file read and payload rendered; one drain at a time (``flock`` on
``<ledger dir>/cloud-drain.lock``); every git read checked, so a dead network is a refusal and
never "no branches"; local master equal to origin's; every path a file (never ``.``, ``..`` or a
directory), relative, in normal form, off the governance-sync filter (READ from ``command_run``)
and off the deny set (this script, the registry, ``.pre-commit-config.yaml``, ``commands/``,
``scripts/sysadmin/``, any ``conftest.py``), and no ``tests/`` file whose text at master names the
home dir; file sets disjoint within the batch, from every unmerged ``claude/*`` branch's three-dot
diff and from every run fired within a day whose done trailer master does not carry (its ``kind:
drain`` row); open work plus the batch within ``--max-open``. A slug with any row that may have
fired is skipped as ``already fired``, so a stopped batch re-runs safely. Each entry is re-checked
against the ledger, then gets its ``kind: drain`` row and fires through ``dispatch`` with
``--pick`` semantics, its files appended to the task; the first failure
stops the batch. Cobra line (D-253): the cheapest way through the pre-flight is to under-declare
``files``; the counter is the merge rule — a branch whose three-dot diff leaves its declared files
is not merged — and the declared list rides in the worker's own task.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import http.client
import json
import os
import posixpath
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".fabrik" / "cloud-routines.json"
FLEET_ROOT = Path.home() / ".claude-fleet"
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{trigger}/fire"
DONE_TRAILER = "Cloud-Dispatch: done"
TOKEN_FILE = "routine-token"
CREDS_FILE = ".credentials.json"
EVENTS_URL = "https://api.anthropic.com/v1/code/sessions/{sid}/events?limit=200"
PAYLOAD_CLOSE = "</routine-fire-payload"
PAYLOAD_MAX = 65536
WEEK_S = 7 * 86400
CHAIN_GUARD_S = 86400
STALE_STATUS_S = 6 * 3600
EXPIRY_GUARD_S = 6 * 3600  # a run must not straddle 00:00 UTC of the credit's expiry date
MARGIN_FLOOR_USD = 10.0
MARGIN_FRACTION = 0.10
REFRESH_MIN_S = 8 * 3600  # one in-place token refresh per account per 8 h, at most
PLAN_RISE_STEP = 0.01  # the advisory's step, in the event's 0-1 fraction (never claude_rotate's %)
EXIT = {
    "http_401": 3,
    "no_account": 3,
    "http_429": 4,
    "walled": 5,
    "chain_dead": 6,
    "paused": 7,
    "expired": 7,
    "drain_refused": 8,
}

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
        credit = entry.get("credit")
        if credit is not None:
            claimed = _num(credit.get("claimed_usd")) if isinstance(credit, dict) else None
            exp = credit.get("expires") if isinstance(credit, dict) else None
            if claimed is None or claimed < 0:
                raise RegistryError(
                    f"registry {path}: account {slug}: credit.claimed_usd must be a number >= 0"
                )
            try:
                expiry_epoch(exp) if isinstance(exp, str) else None
            except ValueError:
                exp = None
            if exp is None:
                raise RegistryError(
                    f"registry {path}: account {slug}: credit.expires must be YYYY-MM-DD"
                )
    margin = data.get("credit_margin_usd")
    if margin is not None and (_num(margin) is None or _num(margin) < 0):  # type: ignore[operator]
        raise RegistryError(f"registry {path}: credit_margin_usd must be a number >= 0")
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


def _read_private(p: Path, what: str, limit: int = 4096) -> str | None:
    """The text of a private file, or None when it does not exist. The file is opened without
    following links and judged by its open descriptor: a regular file, mode 0600, owned by this
    user, with exactly one link. Anything else is a refusal — the rotation machinery copies
    credential files around, and a secret must never ride that path."""
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:  # O_NOFOLLOW on a symlink
            raise DispatchError(f"error: {p}: a symlink is not accepted as a {what}") from exc
        raise DispatchError(f"error: {p}: cannot open the {what} ({exc.strerror})") from exc
    try:
        st = os.fstat(fd)
        if (
            not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode) != 0o600
            or st.st_uid != os.getuid()
        ):
            raise DispatchError(
                f"error: {p}: the {what} must be a regular file, mode 0600, owned by you"
            )
        if st.st_nlink != 1:
            raise DispatchError(
                f"error: {p}: the {what} has {st.st_nlink} links; exactly one is accepted"
            )
        try:
            return os.read(fd, limit).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DispatchError(f"error: {p}: the {what} is not UTF-8 text") from exc
    finally:
        os.close(fd)


def read_token(slug: str, fleet_root: Path) -> str | None:
    """The routine bearer token for ``slug``, or None when no token file exists: one printable
    line in a private file (``_read_private``); a malformed file is a refusal, never a fallback
    to the paid CLI."""
    p = Path(fleet_root) / slug / TOKEN_FILE
    raw = _read_private(p, "token file")
    if raw is None:
        return None
    raw = raw.strip()
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
        # the hooks' own headless flag, declared so tests/test_hooks_headless_guard.py can hold
        # every declared `claude -p` spawner to it (W-a4272e57). Its effect here is near nil and that is
        # fine: the child runs from `scratch_dir()`, where no project hook loads, and
        # CLAUDE_MESH_HEADLESS above already stands down the orient wake and the arm nag; it
        # covers any FABRIK_HEADLESS reader (mail_notify, mcp_watch) that ever does load
        "FABRIK_HEADLESS": "1",
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
    *,
    allow_plan: bool = False,
) -> tuple[str, str]:
    """The account to fire, with the reason; raises ``DispatchError("no_account: …")`` when none
    qualifies. A paused or expired account never qualifies unless ``allow_plan`` (which also
    inverts the weekly order: plan spend goes to the COOLEST account, credit to the hottest)."""
    now = time.time() if now is None else now
    slugs = list(registry["accounts"])
    rows = _status_rows(status)
    recent = dict.fromkeys(slugs, 0)
    for r in ledger_rows:
        if not isinstance(r, dict):
            continue
        ts = _num(r.get("ts"))
        if "kind" in r:  # settle/pause/calibrate/token_refresh rows are not dispatches
            continue
        if r.get("account") in recent and ts is not None and ts >= now - WEEK_S:
            recent[r["account"]] += 1
    candidates: list[tuple[tuple, str, str]] = []
    for s in slugs:
        has_token = _has_token(s, fleet_root)
        row = rows.get(s)
        if row is not None and row.get("parked"):
            continue
        if not allow_plan and (paused_of(ledger_rows, s) or expired(registry, s, now)):
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
                (0 if has_token else 1, recent[s], weekly if allow_plan else -weekly),
                s,
                f"{'token' if has_token else 'cli'} path, {recent[s]} dispatch(es) this week, weekly {weekly:.0f}%",
            )
        )
    if not candidates:
        raise DispatchError(
            "no_account: no registered account qualifies (parked, paused, expired, stale status, dead "
            "or expiring chain, no token) — pass --account"
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


class LedgerTxn:
    """Read-then-append under ONE exclusive ``flock`` on the ledger, so a decision computed from
    the rows (the spend, the pause) cannot race another session's append between the read and
    the write. ``rows`` is read under the lock; ``append`` writes through the same descriptor."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.rows: list[dict] = []
        self._fh: TextIO | None = None

    def __enter__(self) -> LedgerTxn:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")  # noqa: SIM115 — closed in __exit__
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        self.rows = read_ledger(self.path)
        return self

    def append(self, row: dict) -> None:
        assert self._fh is not None
        self._fh.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
        self._fh.flush()
        self.rows.append(row)

    def __exit__(self, *exc: object) -> None:
        assert self._fh is not None
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        finally:
            self._fh.close()


def append_ledger(path: Path, row: dict) -> None:
    with LedgerTxn(path) as txn:  # one O_APPEND write per row, under the lock
        txn.append(row)


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
        if r.get("slug") == slug and "kind" not in r:
            return r
    return None


# --- credit guard ---------------------------------------------------------------------------------


def _now_row(row: dict) -> dict:
    now = time.time()
    return {**row, "ts": now, "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))}


def read_access_token(slug: str, fleet_root: Path) -> tuple[str | None, bool]:
    """``(access token, fresh)`` from the account's credentials file — ``(None, False)`` when the
    file or the token is absent; ``fresh`` is ``expiresAt`` still ahead of now. Read only, under
    ``_read_private``'s checks; the token is never printed or put in an error."""
    p = Path(fleet_root) / slug / CREDS_FILE
    raw = _read_private(p, "credentials file", limit=65536)
    if raw is None:
        return None, False
    try:
        obj = json.loads(raw)
    except ValueError as exc:
        raise DispatchError(f"error: {p}: the credentials file is not JSON") from exc
    oauth = obj.get("claudeAiOauth") if isinstance(obj, dict) else None
    if not isinstance(oauth, dict):
        return None, False
    tok = oauth.get("accessToken")
    if not isinstance(tok, str) or not _TOKEN.fullmatch(tok):
        return None, False
    exp = _num(oauth.get("expiresAt"))
    return tok, exp is not None and exp / 1000 > time.time()


def _refresh_probe(cfg: Path, scratch: Path) -> bool:
    """One in-place headless turn under the account's own dir — the only path that rolls its
    single-use refresh chain (``claude_rotate._capability_probe``'s class). Sub-cent of plan."""
    try:
        rc, _out = _run_claude(
            ["claude", "-p", "ok", "--output-format", "json", "--max-turns", "1", "--tools", ""],
            _account_env(cfg),
            scratch,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return rc == 0


def _http_get(url: str, headers: dict) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — a fixed https host
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _last_row(rows: list[dict], account: str, kind: str) -> dict | None:
    for r in reversed(rows):
        if isinstance(r, dict) and r.get("kind") == kind and r.get("account") == account:
            return r
    return None


def fetch_run_events(
    slug: str,
    sid: str,
    fleet_root: Path,
    *,
    rows: list[dict] | None = None,
    ledger: Path | None = None,
) -> tuple[list, bool]:
    """The run's raw events (newest first) and whether the token was refreshed on the way. A
    ``DispatchError`` names why it could not be read: ``settle_pending`` (no credentials, token
    expired and not refreshable now), ``http_401``, ``http_429`` or ``http_<n>``; a 401 never
    retries and never probes."""
    if not _SID_CSE.fullmatch(sid):
        raise DispatchError(f"error: {sid} is not a cse_ session id")
    token, fresh = read_access_token(slug, fleet_root)
    if token is None:
        raise DispatchError(f"settle_pending: {slug} has no credentials file; run /login there")
    refreshed = False
    if not fresh:
        now = time.time()
        last = _last_row(rows or [], slug, "token_refresh")
        last_ts = _num((last or {}).get("ts"))
        if last_ts is not None and now - last_ts < REFRESH_MIN_S:
            raise DispatchError(
                f"settle_pending: {slug}'s access token is expired and its refresh probe already ran "
                f"{(now - last_ts) / 3600:.1f} h ago; run /login in that account's dir"
            )
        ok = _refresh_probe(Path(fleet_root) / slug, scratch_dir())
        token, fresh = read_access_token(slug, fleet_root)
        ok = ok and fresh and token is not None
        if ledger is not None:
            append_ledger(ledger, _now_row({"kind": "token_refresh", "account": slug, "ok": ok}))
        if not ok:
            raise DispatchError(
                f"settle_pending: {slug}'s access token is expired and the refresh probe failed — "
                "run /login in that account's dir (CLAUDE_CONFIG_DIR=~/.claude-fleet/"
                f"{slug} claude)"
            )
        refreshed = True
    status, body = _http_get(
        EVENTS_URL.format(sid=sid),
        {
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "Accept": "application/json",
        },
    )
    if status == 401:
        raise DispatchError(
            f"http_401: the access token for {slug} was refused (401); run /login there"
        )
    if status == 429:
        raise DispatchError(
            f"http_429: the events read for {slug} was rate-limited (429); retry later"
        )
    if status != 200:
        raise DispatchError(f"http_{status}: the events read for {slug} failed ({status})")
    try:
        obj = json.loads(body)
    except ValueError as exc:
        raise DispatchError("error: the events body is not JSON") from exc
    data = obj.get("data") if isinstance(obj, dict) else obj
    if not isinstance(data, list):
        raise DispatchError("error: the events body carries no event list")
    return data, refreshed


def _event(ev: object) -> tuple[str | None, dict]:
    if not isinstance(ev, dict):
        return None, {}
    kind = ev.get("event_type") or ev.get("type")
    payload = ev.get("payload")
    return (kind if isinstance(kind, str) else None), (payload if isinstance(payload, dict) else ev)


def settle_run(events: list) -> dict:
    """What the newest events say: the first ``result`` (cumulative cost, token counts) and the
    first ``rate_limit_event`` (plan readings as 0-1 fractions, overage flag, the raw block)."""
    out: dict = {
        "cost_usd": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "plan_5h": None,
        "plan_7d": None,
        "using_overage": None,
        "rate_limit_info": None,
        "finished": False,
    }
    for ev in events:
        kind, payload = _event(ev)
        if kind == "result" and not out["finished"]:
            out["finished"] = True
            out["cost_usd"] = _num(payload.get("total_cost_usd"))
            usage = payload.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            out["input_tokens"] = _num(usage.get("input_tokens"))
            out["output_tokens"] = _num(usage.get("output_tokens"))
            out["cache_read_tokens"] = _num(usage.get("cache_read_input_tokens"))
        elif kind == "rate_limit_event" and out["rate_limit_info"] is None:
            info = payload.get("rate_limit_info")
            if isinstance(info, dict):
                out["rate_limit_info"] = info
                flag = info.get("isUsingOverage")
                out["using_overage"] = flag if isinstance(flag, bool) else None
                win = info.get("unifiedWindows")
                win = win if isinstance(win, dict) else {}
                for key, name in (("plan_5h", "five_hour"), ("plan_7d", "seven_day")):
                    w = win.get(name)
                    out[key] = _num(w.get("utilization")) if isinstance(w, dict) else None
    return out


def claimed_of(registry: dict, account: str) -> float:
    credit = registry["accounts"].get(account, {}).get("credit")
    return _num((credit or {}).get("claimed_usd")) or 0.0 if isinstance(credit, dict) else 0.0


def expires_of(registry: dict, account: str) -> str | None:
    credit = registry["accounts"].get(account, {}).get("credit")
    exp = (credit or {}).get("expires") if isinstance(credit, dict) else None
    return exp if isinstance(exp, str) else None


def margin_of(registry: dict, account: str) -> float:
    explicit = _num(registry.get("credit_margin_usd"))
    if explicit is not None:
        return explicit
    return max(MARGIN_FLOOR_USD, MARGIN_FRACTION * claimed_of(registry, account))


def expiry_epoch(date_str: str) -> int:
    """00:00 UTC of ``YYYY-MM-DD`` — Anthropic's day, never this box's."""
    import calendar

    return calendar.timegm(time.strptime(date_str, "%Y-%m-%d"))


def expired(registry: dict, account: str, now: float | None = None) -> bool:
    exp = expires_of(registry, account)
    if exp is None:
        return False
    now = time.time() if now is None else now
    try:
        return now + EXPIRY_GUARD_S >= expiry_epoch(exp)
    except ValueError as exc:
        raise RegistryError(f"accounts.{account}.credit.expires is not YYYY-MM-DD") from exc


def paused_of(rows: list[dict], account: str) -> dict | None:
    """The pause row in force for ``account`` (the latest pause/unpause row wins), or None."""
    for r in reversed(rows):
        if (
            isinstance(r, dict)
            and r.get("account") == account
            and r.get("kind") in ("pause", "unpause")
        ):
            return r if r["kind"] == "pause" else None
    return None


def _fired_rows(rows: list[dict], account: str | None = None) -> list[dict]:
    """Dispatch rows that reached a run (status ok, a cse_ id), one per session, oldest first."""
    seen: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict) or "kind" in r or r.get("status") != "ok":
            continue
        if account and r.get("account") != account:
            continue
        sid = r.get("session_id")
        if isinstance(sid, str) and sid.startswith("cse_") and sid not in seen:
            seen[sid] = r
    return list(seen.values())


def _real_costs(rows: list[dict], account: str | None = None) -> dict[str, float]:
    """Per session id, the latest settle row's real cost for ``account`` (any account when
    None); a pending/unfinished settle never overrides a real reading."""
    out: dict[str, float] = {}
    for r in rows:
        if (
            isinstance(r, dict)
            and r.get("kind") == "settle"
            and isinstance(r.get("session_id"), str)
            and (account is None or r.get("account") == account)
        ):
            cost = _num(r.get("cost_usd"))
            if cost is not None:
                out[r["session_id"]] = cost
    return out


def unsettled(rows: list[dict], account: str | None = None) -> list[str]:
    """Slugs of fired runs with no real-cost settle yet (provisioned at the margin)."""
    return [str(r.get("slug")) for r in _unsettled_rows(rows, account)]


def _unsettled_rows(rows: list[dict], account: str | None = None) -> list[dict]:
    return [
        r
        for r in _fired_rows(rows, account)
        if r["session_id"] not in _real_costs(rows, r.get("account"))
    ]


def spent_usd(rows: list[dict], account: str, *, margin: float, claimed: float = 0.0) -> float:
    """Credit spent by ``account``: after the latest ``calibrate`` row, (claimed − balance); then
    every session fired after it — its latest real cost, or the margin while unsettled; a
    ``plan_usage`` row never counts."""
    cal = _last_row(rows, account, "calibrate")
    cutoff = _num((cal or {}).get("ts"))
    base = 0.0
    if cal is not None and claimed > 0:
        base = max(0.0, claimed - (_num(cal.get("balance_usd")) or 0.0))
    costs = _real_costs(rows, account)
    total = base
    for r in _fired_rows(rows, account):
        ts = _num(r.get("ts"))
        # a row with no ts is counted (never silently "before the calibration")
        if r.get("plan_usage") or (cutoff is not None and ts is not None and ts <= cutoff):
            continue
        total += costs.get(r["session_id"], margin)
    return round(total, 6)


def credit_left(registry: dict, account: str, rows: list[dict]) -> float:
    claimed = claimed_of(registry, account)
    return round(
        claimed - spent_usd(rows, account, margin=margin_of(registry, account), claimed=claimed), 6
    )


def decide_pause(
    account: str, *, spent: float, claimed: float, margin: float, settle: dict
) -> str | None:
    """The reason to pause ``account`` now, or None: the dollar counter against the claimed
    credit (primary), or a run that drew on overage (recorded, not yet trusted)."""
    if claimed > 0 and spent >= claimed - margin:
        return f"spent {spent:.2f} of {claimed:.2f} (margin {margin:.2f}) — credit exhausted"
    if settle.get("using_overage") is True:
        return "overage: the run drew on overage — the credit is gone"
    return None


def plan_rise_note(
    settle: dict, prev: dict | None, *, account: str, active_slug: str | None
) -> str | None:
    """ADVISORY: the weekly plan reading rose on an idle account between two settles — plan
    quota may be paying. Never a pause (the browser, a CLI fire and ``log`` move it too), and
    blind on the active account and when the active account is unknown."""
    if prev is None or active_slug is None or account == active_slug:
        return None
    now_r, then_r = _num(settle.get("plan_7d")), _num(prev.get("plan_7d"))
    if now_r is None or then_r is None or round(now_r - then_r, 6) < PLAN_RISE_STEP:
        return None
    return (
        f"advisory: the weekly plan reading rose on idle {account}: {then_r:.3f} → {now_r:.3f} — "
        "plan quota may be paying for cloud runs (credit gone?); check claude.ai/settings/usage"
    )


def active_slug() -> str | None:
    """The fleet's active account, from the ``active`` pointer; None when it cannot be read."""
    try:
        return os.path.basename(os.readlink(FLEET_ROOT / "active")) or None
    except OSError:
        return None


def _credit_line(registry: dict, account: str, rows: list[dict]) -> str:
    claimed = claimed_of(registry, account)
    if claimed <= 0:
        return "no credit declared"
    spent = spent_usd(rows, account, margin=margin_of(registry, account), claimed=claimed)
    line = f"spent {spent:.2f} · left {claimed - spent:.2f}"
    pending = unsettled(rows, account)
    if pending:
        line += f" · {len(pending)} unsettled"
    exp = expires_of(registry, account)
    if exp:
        try:
            hours = (expiry_epoch(exp) - EXPIRY_GUARD_S - time.time()) / 3600
        except ValueError:
            hours = None
        line += f" · expires {exp}" + (
            f" (dispatch refused in {hours / 24:.1f} d)" if hours is not None else ""
        )
    paused = paused_of(rows, account)
    if paused:
        line += f" · PAUSED since {paused.get('ts_iso', '?')} ({paused.get('reason', '?')})"
    return line


def _guard_account(
    registry: dict, account: str, rows: list[dict], *, allow_plan: bool
) -> str | None:
    """Refuse a paused or expired account (``DispatchError`` paused/expired → exit 7) unless
    ``allow_plan``, in which case the note to print is returned."""
    paused = paused_of(rows, account)
    is_expired = expired(registry, account)
    if not allow_plan:
        if paused:
            raise DispatchError(
                f"paused: {account} is paused since {paused.get('ts_iso', '?')} — {paused.get('reason', '?')}; "
                f"`unpause {account}` or --allow-plan-usage"
            )
        if is_expired:
            raise DispatchError(
                f"expired: {account}'s credit expires {expires_of(registry, account)} 00:00 UTC and this "
                f"run is within the {EXPIRY_GUARD_S // 3600} h guard; --allow-plan-usage spends plan quota instead"
            )
        return None
    why = "paused" if paused else ("expired" if is_expired else "not paused")
    return (
        f"plan usage: --allow-plan-usage — {account} ({why}) fires on its PLAN quota; the run's cost "
        "will not count against the credit"
    )


def _settle_session(
    args: argparse.Namespace, registry: dict, disp: dict, *, quiet: bool = False
) -> int:
    """Settle one fired dispatch row: a settle row (real cost, or ``settle_pending``), the
    advisory, and the pause row when a trigger fires. Idempotent: the latest real cost wins."""
    account, slug, sid = disp["account"], disp.get("slug"), disp["session_id"]
    out = sys.stderr if quiet else sys.stdout
    rows = read_ledger(args.ledger)
    claimed, margin = claimed_of(registry, account), margin_of(registry, account)
    base = {"kind": "settle", "account": account, "slug": slug, "session_id": sid}
    try:
        events, refreshed = fetch_run_events(
            account, sid, args.fleet_root, rows=rows, ledger=args.ledger
        )
    except DispatchError as exc:
        reason = str(exc)
        if (
            "no credentials file" not in reason
        ):  # nothing was attempted: no row, the provision stands
            append_ledger(
                args.ledger,
                _now_row(
                    {
                        **base,
                        "status": "settle_pending",
                        "reason": reason.split(":", 1)[0],
                        "cost_usd": None,
                    }
                ),
            )
        print(
            f"{slug} {account} {sid} settle_pending — provisional {margin:.2f} at the margin",
            file=out,
        )
        print(f"cloud_dispatch: {reason}", file=sys.stderr)
        return 0
    st = settle_run(events)
    row = {
        **base,
        **st,
        "status": "ok" if st["finished"] else "unfinished",
        "refresh_probe": refreshed,
    }
    row = _now_row(row)
    # the spend and the pause are decided from rows read UNDER the lock the append holds, so a
    # sibling settle on the same account cannot slip its cost between this read and this write
    with LedgerTxn(args.ledger) as txn:
        # `rows` (read before the fetch) stays the PRE-settle view for the advisory's baseline
        spent = spent_usd(txn.rows + [row], account, margin=margin, claimed=claimed)
        row["spent_usd_total"] = spent
        txn.append(row)
        why = None
        if not disp.get("plan_usage"):
            why = decide_pause(account, spent=spent, claimed=claimed, margin=margin, settle=st)
            if why and paused_of(txn.rows, account) is None:
                txn.append(_now_row({"kind": "pause", "account": account, "reason": why}))
            else:
                why = None
    cost = f"{st['cost_usd']:.2f}" if st["cost_usd"] is not None else "pending (unfinished)"
    print(
        f"{slug} {account} {sid} cost {cost} · spent {spent:.2f} · left {claimed - spent:.2f}",
        file=out,
    )
    prev = next(
        (
            r
            for r in reversed(rows)
            if r.get("kind") == "settle"
            and r.get("account") == account
            and _num(r.get("plan_7d")) is not None
        ),
        None,
    )
    note = plan_rise_note(st, prev, account=account, active_slug=active_slug())
    if note:
        print(f"cloud_dispatch: {note}", file=sys.stderr)
    if why:
        print(f"cloud_dispatch: PAUSED {account} — {why}", file=sys.stderr)
    return 0


def _refused_recently(rows: list[dict], sid: str, now: float) -> bool:
    """The latest settle row for ``sid`` is an HTTP refusal (401/429) younger than
    ``REFRESH_MIN_S`` — the automatic sweep backs off; `settle --slug` always retries."""
    for r in reversed(rows):
        if r.get("kind") == "settle" and r.get("session_id") == sid:
            ts = _num(r.get("ts"))
            return (
                r.get("status") == "settle_pending"
                and r.get("reason") in ("http_401", "http_429")
                and ts is not None
                and now - ts < REFRESH_MIN_S
            )
    return False


def _settle_all(args: argparse.Namespace, registry: dict, *, quiet: bool = False) -> int:
    """Settle every fired run with no real cost yet; ``dispatch`` runs this first. A session
    whose token the API refused within the last 8 h is left for `settle --slug` or the next
    window — never a retry on every dispatch."""
    rows = read_ledger(args.ledger)
    now = time.time()
    for disp in _unsettled_rows(rows):
        if disp.get("account") in registry["accounts"] and not _refused_recently(
            rows, disp["session_id"], now
        ):
            _settle_session(args, registry, disp, quiet=quiet)
    return 0


def _cmd_settle(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    if args.all:
        return _settle_all(args, reg)
    disp = next(
        (r for r in reversed(_fired_rows(read_ledger(args.ledger))) if r.get("slug") == args.slug),
        None,
    )
    if disp is None:
        print(
            f"cloud_dispatch: no fired run for slug {args.slug} in {args.ledger}", file=sys.stderr
        )
        return 1
    return _settle_session(args, reg, disp)


def _cmd_pause(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    if args.account not in reg["accounts"]:
        print(f"cloud_dispatch: {args.account} is not in the registry", file=sys.stderr)
        return 1
    kind = "pause" if args.cmd == "pause" else "unpause"
    row = {"kind": kind, "account": args.account}
    if kind == "pause":
        row["reason"] = args.reason
    append_ledger(args.ledger, _now_row(row))
    print(f"{kind}d {args.account}" + (f" — {args.reason}" if kind == "pause" else ""))
    return 0


def _cmd_calibrate(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    if args.account not in reg["accounts"]:
        print(f"cloud_dispatch: {args.account} is not in the registry", file=sys.stderr)
        return 1
    if args.balance < 0:
        print("cloud_dispatch: --balance must be ≥ 0", file=sys.stderr)
        return 1
    append_ledger(
        args.ledger,
        _now_row(
            {"kind": "calibrate", "account": args.account, "balance_usd": float(args.balance)}
        ),
    )
    rows = read_ledger(args.ledger)
    print(f"calibrated {args.account}: {_credit_line(reg, args.account, rows)}")
    return 0


# --- CLI ------------------------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    rows = _status_rows(None if args.no_status else fleet_status())
    ledger_rows = read_ledger(args.ledger)
    print(f"registry {args.registry} · routine {reg.get('routine')} · repo {reg.get('repo')}")
    print(f"ledger {args.ledger}")
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
        print(f"  {'':<12} credit: {_credit_line(reg, s, ledger_rows)}")
    for r in ledger_rows[-args.ledger_tail :] if args.ledger_tail else []:
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
    allow_plan = bool(getattr(args, "allow_plan_usage", False))
    _settle_all(args, reg, quiet=True)  # charge every earlier run before the credit is read
    try:
        ledger_rows = read_ledger(args.ledger)
        if args.account:
            if args.account not in reg["accounts"]:
                raise DispatchError(f"error: {args.account} is not in the registry")
            account, why = args.account, "named"
        else:
            account, why = pick_account(
                reg, fleet_status(), ledger_rows, args.fleet_root, allow_plan=allow_plan
            )
        note = _guard_account(reg, account, ledger_rows, allow_plan=allow_plan)
    except DispatchError as exc:
        print(f"cloud_dispatch: {exc}", file=sys.stderr)
        return EXIT.get(str(exc).split(":", 1)[0], 1)
    if note:
        print(f"cloud_dispatch: {note}", file=sys.stderr)
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
        "plan_usage": allow_plan,
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
        try:
            reg = load_registry(args.registry)
            disp = next(
                (
                    r
                    for r in reversed(_fired_rows(read_ledger(args.ledger)))
                    if r.get("slug") == args.slug
                ),
                None,
            )
            if disp is not None:  # stdout stays the tip sha alone; the cost line goes to stderr
                _settle_session(args, reg, disp, quiet=True)
        except (RegistryError, DispatchError, OSError) as exc:
            print(
                f"cloud_dispatch: the run was not settled ({exc}); run `settle --slug {args.slug}`",
                file=sys.stderr,
            )
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


# --- drain: a pre-flighted batch (W-b00d9d72) ------------------------------------------------------

DRAIN_KEYS = frozenset({"slug", "task", "task_file", "files"})
DRAIN_DENY = frozenset(
    {"scripts/cloud_dispatch.py", ".fabrik/cloud-routines.json", ".pre-commit-config.yaml"}
)
DRAIN_DENY_DIRS = ("commands/", "scripts/sysadmin/")  # the corpus, and the box-local machinery
# A tests/ file whose text at master names one of these reads the home dir, which a cloud VM lacks.
# A substring screen, never a proof: an aliased or imported read escapes it, and the merge rule's
# spot-check is the counter (docs/workstation/cloud-dispatch.md § Draining a batch).
DRAIN_HOME = ("Path.home", "expanduser", "~/.claude", "HOME", "getpwuid")
IN_FLIGHT_S = 86400  # a fired run with no landed work after a day is taken to have died
# A dispatch row with one of these statuses never started a run; every other status may have
# (``error`` and ``http_5xx`` can follow a request the API accepted), so its slug counts as fired.
NOT_FIRED = frozenset({"http_401", "http_429", "walled", "chain_dead"})


def _git_run(*args: str, timeout: float = 120) -> tuple[int, str]:
    run = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )
    return run.returncode, run.stdout


def _git_checked(*args: str) -> str:
    """``_git``'s stdout-only form reads a failed ``ls-remote`` as "no branches" — a false pass for
    every drain guard — so the drain reads git only through this, and a non-zero exit refuses."""
    rc, out = _git_run(*args)
    if rc != 0:
        raise DispatchError(f"drain_refused: git {args[0]} failed (rc {rc})")
    return out


def _sync_pattern() -> re.Pattern:
    """The governance-sync filter, READ from ``command_run`` (graded there against the sync
    wrapper), never copied; command_run fails OPEN on an unreadable filter, the drain fails CLOSED."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from command_run import _sync_filter_source
    finally:
        sys.path.pop(0)
    src = _sync_filter_source()
    try:
        if not src:
            raise re.error("unreadable")
        return re.compile(src)
    except re.error as exc:
        raise DispatchError(
            f"drain_refused: the governance-sync filter cannot be read or compiled ({exc})"
        ) from exc


def _maybe_fired(r: dict) -> bool:
    status = r.get("status")
    return "kind" not in r and isinstance(status, str) and status not in NOT_FIRED


def load_batch(path: Path) -> list[dict]:
    """The batch, each entry checked and given ``_task``: the task text with its files appended,
    rendered once here so a missing task file or an oversized payload refuses before any fire."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DispatchError(f"drain_refused: batch {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise DispatchError("drain_refused: the batch must be a non-empty JSON list")
    seen: set[str] = set()
    for i, e in enumerate(data):
        where = f"drain_refused: batch entry {i}"
        if not isinstance(e, dict):
            raise DispatchError(f"{where} is not an object")
        extra = set(e) - DRAIN_KEYS
        if extra:
            raise DispatchError(f"{where}: unknown key {sorted(extra)}")
        if ("task" in e) == ("task_file" in e) or not isinstance(
            e.get("task", e.get("task_file")), str
        ):
            raise DispatchError(f"{where}: give exactly one of task or task_file, as a string")
        files = e.get("files")
        if not isinstance(files, list) or not files or not all(isinstance(p, str) for p in files):
            raise DispatchError(f"{where}: files must be a non-empty list of repo paths")
        if len(set(files)) != len(files):
            raise DispatchError(f"{where}: files lists a path twice")
        if not valid_slug(e.get("slug")):
            raise DispatchError(f"{where}: slug {e.get('slug')!r} is not a branch name")
        if e["slug"] in seen:
            raise DispatchError(f"{where}: duplicate slug {e['slug']}")
        seen.add(e["slug"])
        try:
            task = (
                Path(e["task_file"]).read_text(encoding="utf-8") if "task_file" in e else e["task"]
            )
        except (OSError, ValueError) as exc:
            raise DispatchError(f"{where}: task_file: {exc}") from exc
        e["_task"] = f"{task.rstrip()}\n\nFiles you may change: {', '.join(files)}\n"
        try:
            render_payload(e["slug"], e["_task"])
        except DispatchError as exc:
            raise DispatchError(f"{where}: {exc}") from exc
    return data


def _unsafe_reason(p: str, sync: re.Pattern) -> str | None:
    if (
        not p
        or p in (".", "..")
        or p != posixpath.normpath(p)
        or p.startswith(("/", "../"))
        or "\\" in p
    ):
        return "not a relative file path in normal form"
    if sync.search(p):
        return "on the governance-sync filter"
    if (
        p in DRAIN_DENY
        or p.startswith(DRAIN_DENY_DIRS)
        or p + "/" in DRAIN_DENY_DIRS
        or posixpath.basename(p) == "conftest.py"
    ):
        return "on the drain's deny set"
    entry = _git_checked("ls-tree", "refs/heads/master", "--", p).split("\t", 1)
    kind = entry[0].split()[1] if len(entry) == 2 and len(entry[0].split()) == 3 else None
    if kind == "tree":
        return "a directory at master, not a file"
    if kind == "blob" and p.startswith("tests/"):
        text = _git_checked("show", f"refs/heads/master:{p}")
        if any(h in text for h in DRAIN_HOME):
            return "a test that reads the home dir"
    return None


def _open_work(rows: list[dict]) -> tuple[str, dict[str, set[str]], dict[str, str]]:
    """``(master sha, {holder: files}, {branch slug: tip})``. A holder is either a ``claude/*``
    branch that is unmerged (its three-dot diff, renames split into both paths) or that a run fired
    within a day still owns, or such a run with no branch yet. A run's declared files (its ``kind:
    drain`` row) join what it holds; a plain dispatch run declares none, so it holds a cap slot
    only. A run has LANDED, and holds nothing, once master carries its ``Cloud-Dispatch: done
    <session>`` trailer — a merged-and-deleted branch would otherwise hold its files for a day."""
    heads: dict[str, str] = {}
    for line in _git_checked(
        "ls-remote", "origin", "refs/heads/master", "refs/heads/claude/*"
    ).splitlines():
        parts = line.split()
        if len(parts) == 2:
            heads[parts[1]] = parts[0]
    origin = heads.pop("refs/heads/master", None)
    local = _git_checked("rev-parse", "--verify", "refs/heads/master").strip()
    if not origin or origin != local:
        raise DispatchError(
            f"drain_refused: local master {local[:12] or '?'} is not origin master "
            f"{(origin or 'absent')[:12]}; fast-forward master in the main checkout first"
        )
    branches = {ref.removeprefix("refs/heads/claude/"): tip for ref, tip in heads.items()}
    now = time.time()
    recent: dict[str, dict] = {}
    for r in rows:
        if _maybe_fired(r) and now - (_num(r.get("ts")) or 0) < IN_FLIGHT_S:
            recent[str(r.get("slug"))] = r
    if recent:
        since = min(_num(r.get("ts")) or now for r in recent.values())
        landed = set(
            re.findall(
                rf"^{re.escape(DONE_TRAILER)} (\S+)",
                _git_checked("log", "refs/heads/master", f"--since=@{int(since)}", "--format=%B"),
                re.M,
            )
        )
        recent = {s: r for s, r in recent.items() if r.get("session_id") not in landed}
    declared: dict[str, set[str]] = {}
    for r in rows:
        if r.get("kind") == "drain" and isinstance(r.get("files"), list):
            declared[str(r.get("slug"))] = set(r["files"])
    held: dict[str, set[str]] = {}
    if branches:
        _git_checked("fetch", "-q", "origin", "+refs/heads/claude/*:refs/cloud-dispatch/claude/*")
    for name, tip in branches.items():
        rc, _ = _git_run("merge-base", "--is-ancestor", tip, "refs/heads/master")
        if rc not in (0, 1):
            raise DispatchError(f"drain_refused: git merge-base failed (rc {rc})")
        if rc == 0 and name not in recent:
            continue
        files = set(declared.get(name, set()))
        if rc == 1:
            out = _git_checked("diff", "--name-only", "--no-renames", "-z", f"{local}...{tip}")
            files |= {p for p in out.split("\0") if p}
        held[f"claude/{name}"] = files
    for slug in recent:
        if slug not in branches:
            held[f"in-flight {slug}"] = set(declared.get(slug, set()))
    return local, held, branches


def _cmd_drain(args: argparse.Namespace) -> int:
    if args.max_open < 1:
        raise DispatchError("drain_refused: --max-open must be at least 1")
    batch = load_batch(args.batch)
    lock_path = Path(args.ledger).parent / "cloud-drain.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DispatchError("drain_refused: another drain holds the lock") from exc
        return _drain_locked(args, batch)


def _drain_locked(args: argparse.Namespace, batch: list[dict]) -> int:
    rows = read_ledger(args.ledger)
    fired_slugs = {r.get("slug") for r in rows if _maybe_fired(r)}
    todo = [e for e in batch if e["slug"] not in fired_slugs]
    sync = _sync_pattern()
    for e in todo:
        for p in e["files"]:
            why = _unsafe_reason(p, sync)
            if why:
                raise DispatchError(f"drain_refused: {e['slug']}: {p!r} is not cloud-safe ({why})")
    _, held, branches = _open_work(rows)
    owner: dict[str, str] = {}
    for e in todo:
        if e["slug"] in branches:
            raise DispatchError(f"drain_refused: claude/{e['slug']} already exists on origin")
        for p in e["files"]:
            if p in owner:
                raise DispatchError(f"drain_refused: {p} is in both {owner[p]} and {e['slug']}")
            owner[p] = e["slug"]
            taken = next((h for h, fs in held.items() if p in fs), None)
            if taken:
                raise DispatchError(f"drain_refused: {e['slug']}: {p} is held by {taken}")
    if len(held) + len(todo) > args.max_open:
        raise DispatchError(
            f"drain_refused: {len(held)} open + {len(todo)} to fire is over the cap of {args.max_open}"
        )
    status: dict[str, str] = {e["slug"]: "already fired" for e in batch if e not in todo}
    rc = 0
    try:
        for e in todo:
            slug = e["slug"]
            if args.dry_run:
                status[slug] = "would fire"
                continue
            if rc != 0:
                break
            if any(r.get("slug") == slug and _maybe_fired(r) for r in read_ledger(args.ledger)):
                status[slug] = "already fired (by another session, after the pre-flight)"
                continue
            append_ledger(
                args.ledger, {**_now_row({}), "kind": "drain", "slug": slug, "files": e["files"]}
            )
            rc = _cmd_dispatch(
                argparse.Namespace(
                    registry=args.registry,
                    fleet_root=args.fleet_root,
                    ledger=args.ledger,
                    slug=slug,
                    task=e["_task"],
                    task_file=None,
                    account=None,
                    force_new=False,
                    allow_plan_usage=args.allow_plan_usage,
                )
            )
            last = last_dispatch(read_ledger(args.ledger), slug) or {}
            if rc == 0:
                status[slug] = "fired"
            elif _maybe_fired(last):
                status[slug] = f"fired? ({last.get('status')} — read the ledger before retrying)"
            else:
                status[slug] = f"refused rc{rc}"
    finally:
        for e in batch:
            print(
                f"cloud_dispatch: drain {e['slug']}: {status.get(e['slug'], 'not reached')}",
                file=sys.stderr,
            )
    return rc


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
    p.add_argument(
        "--allow-plan-usage",
        action="store_true",
        help="fire a paused or expired account on its PLAN quota (the row is tagged; its cost never counts against the credit)",
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
    p = sub.add_parser(
        "settle", parents=[common(True)], help="ledger a run's cost; pause on exhaustion"
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true", help="every fired run with no real cost yet")
    p.set_defaults(fn=_cmd_settle)
    p = sub.add_parser("pause", parents=[common(True)])
    p.add_argument("account")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=_cmd_pause)
    p = sub.add_parser("unpause", parents=[common(True)])
    p.add_argument("account")
    p.set_defaults(fn=_cmd_pause)
    p = sub.add_parser(
        "calibrate",
        parents=[common(True)],
        help="record the web balance (claude.ai/settings/usage)",
    )
    p.add_argument("account")
    p.add_argument(
        "--balance",
        type=float,
        required=True,
        help="the credit balance in USD as the web shows it now",
    )
    p.set_defaults(fn=_cmd_calibrate)
    p = sub.add_parser(
        "drain",
        parents=[common(True)],
        help="pre-flight a batch file of cloud-safe tasks, then fire each by --pick",
    )
    p.add_argument(
        "--batch",
        type=Path,
        required=True,
        help='JSON list of {"slug", "task" | "task_file", "files"}',
    )
    p.add_argument(
        "--max-open",
        type=int,
        default=10,
        help="open branches + in-flight runs + this batch, at most",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="pre-flight only; fire and ledger nothing"
    )
    p.add_argument(
        "--allow-plan-usage", action="store_true", help="as dispatch's flag, for every fire"
    )
    p.set_defaults(fn=_cmd_drain)
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
