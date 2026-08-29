#!/usr/bin/env python3
# AFTER-EDIT: tests/test_claude_broker.py | scripts/sysadmin/quota_governor.py
"""Completion-only container broker — subscription-billed Claude for Docker workloads.

Containers hold NO ob@ creds and never reach the operator's full-tool claude. They POST a prompt to
this loopback broker, which runs `claude -p --tools ""` (the documented "disable all tools" form —
`claude --help`, v2.1.238) via the host entrypoint and returns ONLY the completion. Controls:

  (a) per-caller shared-token auth (401 without a valid token);
  (b) per-caller window budget — a stdlib JSON file (~/.claude/state/broker-budgets.json) keyed
      caller → {five_hour:{count,resets_at_epoch}, seven_day:{…}}, reset from the LIVE `--status`
      window epoch (None epoch → never reset, never `now >= None`); over-budget → 429;
  (c) an audit line per job (caller, prompt HASH, out length) — never the raw prompt;
  (d) class forced to `routine` server-side → QuotaGovernor.route("routine", caller): a job under the
      reserve sheds to the pool (never dropped), never self-labelled by the caller.

FAIL-CLOSED: the broker serves ONLY when the tool-disable form is the pinned `--tools ""`; anything
else refuses (503) rather than run an unrestricted operator-tool claude for a container. No new
dependency (stdlib only; the optional pool import is guarded).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class _Router(Protocol):
    """The QuotaGovernor surface the broker consumes (Phase A)."""

    def route(self, kind: str, *, caller: str | None = None) -> str: ...


_DIR = Path(__file__).resolve().parent
_STATE = Path(os.path.expanduser("~/.claude/state"))
_ENTRYPOINT = _DIR / "claude-run.sh"
_TOOL_DISABLE = ("--tools", "")  # `claude --help`: use "" to disable ALL tools
_WINDOWS = ("five_hour", "seven_day")
# a model name is `claude-opus-4-8` etc. — must START with an alphanumeric (never a hyphen) so a
# container-controlled `model` value can never be a `--`-leading token some arg parsers would read as
# a flag. A hyphen is allowed only INSIDE the name. (Defence-in-depth on top of the `--` prompt
# sentinel; the model sits in the value slot BEFORE `--`.)
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MAX_BODY = 1_000_000  # 1 MB — cap the request body so a huge Content-Length can't OOM the host


def _default_run_claude(argv: list[str]) -> str:
    import subprocess

    # the broker has ALREADY routed this job through the governor (forced routine) — bypass the
    # claude-run.sh gate so it isn't double-gated (which could shed a job the broker meant for ob@).
    env = {**os.environ, "CLAUDE_GOVERNOR_KIND": "bypass"}
    out = subprocess.run(argv, capture_output=True, text=True, timeout=600, check=True, env=env)
    return out.stdout


def _default_pool(prompt: str, model: str | None) -> str:
    """Single-shot pool completion (guarded import — no-ops to a clear error if unavailable)."""
    try:
        from libs.subagents import fanout  # noqa: PLC0415
    except ImportError:
        return "[pool unavailable — libs.subagents not vendored]"
    batch = fanout("code", [prompt], repo=".", project="claude-broker", mode="read_only")
    for r in batch:
        return getattr(r, "text", None) or str(r)
    return ""


def _default_audit(line: dict) -> None:
    print(json.dumps(line), flush=True)


class Broker:
    """Pure request handler; the HTTP server (`serve`) is a thin wrapper over `handle`."""

    def __init__(
        self,
        *,
        tokens: dict[str, dict],
        governor: _Router,
        budgets_path: Path,
        status_fn: Callable[[], dict],
        now_fn: Callable[[], float],
        run_claude_fn: Callable[[str, str | None], str] | None = None,
        pool_fn: Callable[[str, str | None], str] | None = None,
        tool_disable_args: tuple[str, ...] = _TOOL_DISABLE,
        audit_fn: Callable[[dict], None] | None = None,
    ) -> None:
        self.tokens = tokens
        self.governor = governor
        self.budgets_path = Path(budgets_path)
        self._status_fn = status_fn
        self._now = now_fn
        self.tool_disable_args = tuple(tool_disable_args)
        self._run_claude_fn = run_claude_fn or self._default_run_claude_arg
        self._pool_fn = pool_fn or _default_pool
        self._audit = audit_fn or _default_audit

    # ---- request handling ---------------------------------------------------

    def handle(self, body: dict, token: str | None) -> tuple[int, dict]:
        caller_cfg = self.tokens.get(token) if token else None
        if not caller_cfg:
            return 401, {"error": "unauthorized"}
        # FAIL-CLOSED: never run claude unless the tool-disable form is exactly the pinned deny.
        if not self._tool_disable_ok():
            return 503, {"error": "tool-disable form unverified — refusing to serve"}
        if not isinstance(body, dict):
            return 400, {"error": "body must be a JSON object"}
        caller = caller_cfg.get("caller")
        if not caller:
            return 500, {"error": "misconfigured token (no caller)"}

        epochs = self._status_epochs()
        budgets = self._read_budgets()
        state = self._caller_state(budgets, caller, epochs)
        if self._is_over(state, caller_cfg):
            budgets[caller] = state
            self._write_budgets(budgets)  # persist any rollover even when we refuse
            return 429, {"error": "budget exceeded"}

        model = body.get("model")
        if model is not None and not _MODEL_RE.match(str(model)):
            return 400, {"error": "invalid model"}

        dest = self.governor.route("routine", caller=caller)  # class forced server-side
        prompt = str(body.get("prompt", ""))
        # The attempt spends ob@ quota whether it SUCCEEDS or FAILS — so count + audit it either way,
        # and never let a completion error escape as an uncaught exception (a caller could otherwise
        # burn quota with error-producing prompts while staying under-budget and un-audited).
        try:
            text = (
                self._pool_fn(prompt, model)
                if dest == "pool"
                else self._run_claude_fn(prompt, model)
            )
            code, resp, out_len = 200, {"completion": text, "via": dest}, len(text)
        except Exception as exc:  # noqa: BLE001 — a failed completion is a spent attempt, not a crash
            code, resp, out_len = 502, {"error": "completion failed", "via": dest}, 0
            self._alert_error(caller, exc)
        for w in _WINDOWS:
            state[w]["count"] = int(state[w].get("count", 0)) + 1
        budgets[caller] = state
        self._write_budgets(budgets)
        self._audit(
            {
                "caller": caller,
                "prompt_hash": _hash(prompt),
                "out_len": out_len,
                "via": dest,
                "status": code,
            }
        )
        return code, resp

    def _alert_error(self, caller: str, exc: Exception) -> None:
        # best-effort; the audit line already records the failure — this is just extra signal
        with contextlib.suppress(Exception):
            self._audit(
                {"caller": caller, "event": "completion_error", "error": type(exc).__name__}
            )

    # ---- claude invocation (pinned tool-disable) ----------------------------

    def _claude_argv(self, prompt: str, model: str | None) -> list[str]:
        argv = [str(_ENTRYPOINT), "-p", *self.tool_disable_args]
        if model:
            argv += ["--model", str(model)]
        # POSIX end-of-options: the container-controlled prompt is a bare positional and could
        # otherwise be parsed as a flag (e.g. `--allow-dangerously-skip-permissions`) — `--` forces
        # everything after it to be treated as the prompt, closing the confused-deputy bypass.
        argv += ["--", prompt]
        return argv

    def _default_run_claude_arg(self, prompt: str, model: str | None) -> str:
        return _default_run_claude(self._claude_argv(prompt, model))

    def _tool_disable_ok(self) -> bool:
        return self.tool_disable_args == _TOOL_DISABLE

    # ---- budget (stdlib JSON file, window-reset from live --status) ----------

    def _status_epochs(self) -> dict[str, float | None]:
        """The active account's per-window reset epochs from `--status` (None on any failure)."""
        out: dict[str, float | None] = dict.fromkeys(_WINDOWS)
        try:
            payload = self._status_fn()
            active = payload.get("active")
            for acc in payload.get("accounts", []):
                if isinstance(acc, dict) and active in (acc.get("slugs") or []):
                    for w in _WINDOWS:
                        win = acc.get(w)
                        if isinstance(win, dict):
                            e = win.get("resets_at_epoch")
                            out[w] = float(e) if isinstance(e, (int, float)) else None
                    break
        except Exception:  # noqa: BLE001 — telemetry failure just means "no reset info this cycle"
            pass
        return out

    def _caller_state(self, budgets: dict, caller: str, epochs: dict) -> dict:
        """The caller's window state, rolling over any window whose reset epoch has passed.

        A window stored with a `None` epoch (created during a transient `--status` outage) ADOPTS
        the fresh epoch on recovery — otherwise a capped caller would stay wedged at `None` forever
        and never roll over even after telemetry returns healthy.
        """
        state = budgets.get(caller) or {}
        now = self._now()
        for w in _WINDOWS:
            win = state.get(w) or {"count": 0, "resets_at_epoch": epochs[w]}
            stored = win.get("resets_at_epoch")
            effective = stored if isinstance(stored, (int, float)) else epochs[w]
            if isinstance(effective, (int, float)) and now >= effective:
                win = {"count": 0, "resets_at_epoch": epochs[w]}  # rolled over
            else:
                win = {
                    "count": int(win.get("count", 0)),
                    "resets_at_epoch": effective,
                }  # None→fresh
            state[w] = win
        return state

    def _is_over(self, state: dict, cfg: dict) -> bool:
        for w in _WINDOWS:
            limit = cfg.get(f"{w}_limit")
            if isinstance(limit, int) and state[w]["count"] >= limit:
                return True
        return False

    def _read_budgets(self) -> dict:
        try:
            return json.loads(self.budgets_path.read_text())
        except (OSError, ValueError):
            return {}

    def _write_budgets(self, budgets: dict) -> None:
        self.budgets_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.budgets_path.with_suffix(f".{os.getpid()}.json.tmp")
        tmp.write_text(json.dumps(budgets))
        os.replace(tmp, self.budgets_path)


def _hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest()[:16]


def _safe_content_length(raw: str | None) -> int | None:
    """Parse a Content-Length header → the byte count, or None to REJECT (413).

    None on: missing→0 is fine, but a non-integer, a NEGATIVE value (which would make
    `rfile.read(-1)` read unbounded to EOF and OOM the host), or a value over `_MAX_BODY`.
    """
    try:
        n = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return None
    if n < 0 or n > _MAX_BODY:
        return None
    return n


def _load_tokens() -> dict[str, dict]:
    """Per-caller tokens from ~/.claude/broker-tokens.json (mode 600) — {token: {caller, …limits}}."""
    path = Path(os.path.expanduser("~/.claude/broker-tokens.json"))
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def serve(host: str = "127.0.0.1", port: int = 8790) -> None:  # pragma: no cover — thin I/O wrapper
    """Run the loopback broker. Reads `X-Broker-Token` + a JSON `{prompt, model?}` body."""
    import sys
    import time
    from http.server import BaseHTTPRequestHandler, HTTPServer

    sys.path.insert(0, str(_DIR))
    from quota_governor import QuotaGovernor  # noqa: PLC0415

    broker = Broker(
        tokens=_load_tokens(),
        governor=QuotaGovernor(),
        budgets_path=_STATE / "broker-budgets.json",
        status_fn=_governor_status,
        now_fn=time.time,
    )

    class _H(BaseHTTPRequestHandler):
        def _reply(self, code: int, resp: dict) -> None:
            payload = json.dumps(resp).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):  # noqa: N802
            length = _safe_content_length(self.headers.get("Content-Length"))
            if length is None:  # missing/non-integer/negative/over-cap → refuse before any read
                self._reply(413, {"error": "invalid or too-large body"})
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                body = {}
            try:
                code, resp = broker.handle(body, self.headers.get("X-Broker-Token"))
            except Exception:  # noqa: BLE001 — never leak a stack trace to a container; 500 + move on
                code, resp = 500, {"error": "internal error"}
            self._reply(code, resp)

        def log_message(self, *a):  # silence default stderr logging
            pass

    HTTPServer((host, port), _H).serve_forever()


def _governor_status() -> dict:  # pragma: no cover — used only by serve()
    import sys

    sys.path.insert(0, str(_DIR))
    from quota_governor import _default_status_fn  # noqa: PLC0415

    return _default_status_fn()
