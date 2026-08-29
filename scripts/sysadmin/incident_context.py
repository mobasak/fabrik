#!/usr/bin/env python3
# AFTER-EDIT: tests/test_incident_context.py | scripts/sysadmin/quota_governor.py
"""Incident context marshaller — the HOST side of the pool-diagnosis path.

When ob@ is capped, an incident can't run the autonomous fix on ob@; the governor routes it to
`pool-diagnose` instead. But a single-shot `fanout(mode="read_only")` pool worker has NO file tools
(it can't fetch live context itself). So this marshaller, running on the HOST:

  1. assembles a bundle — the GlitchTip webhook + BOUNDED `docker logs` tails (default 200 lines,
     env `INCIDENT_LOG_TAIL_LINES`) + host state (`docker ps` + `systemctl`);
  2. writes it durably to ~/.claude/state/incidents/<id>.json (audit + operator inspection);
  3. INLINES the bundle content into the worker's prompt and dispatches a single-shot read-only pool
     worker (it reasons over the inlined text, never a path);
  4. mesh-notify's the operator with the proposal — and NEVER auto-applies it (operator-gated).

All I/O (docker, host state, the pool, the notifier) is injected so it is unit-testable and touches
no live state under test. No new dependency (stdlib; the pool import is guarded).
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

_STATE = Path(os.path.expanduser("~/.claude/state"))
_DEFAULT_TAIL = int(os.getenv("INCIDENT_LOG_TAIL_LINES", "200"))


def _default_docker_logs(container: str, lines: int) -> str:
    try:
        out = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:  # noqa: BLE001 — a log-fetch failure is just missing context, not fatal
        return f"[docker logs {container} unavailable: {type(exc).__name__}]"


def _default_state() -> str:
    parts = []
    for cmd in (
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        ["systemctl", "--failed", "--no-legend"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            parts.append(f"$ {' '.join(cmd)}\n{out.stdout}")
        except Exception as exc:  # noqa: BLE001
            parts.append(f"$ {' '.join(cmd)}\n[unavailable: {type(exc).__name__}]")
    return "\n".join(parts)


def _default_pool(prompt: str, *, mode: str = "read_only") -> str:
    """Single-shot read-only pool diagnosis over the INLINED bundle (guarded import)."""
    _ = mode  # the diagnosis is ALWAYS read-only single-shot; the kwarg exists for the call contract
    try:
        from libs.subagents import fanout  # noqa: PLC0415
    except ImportError:
        return "[pool unavailable — libs.subagents not vendored; bundle written for manual review]"
    batch = fanout("review", [prompt], repo=".", project="incident-diagnose", mode="read_only")
    for r in batch:
        return getattr(r, "text", None) or str(r)
    return ""


def _default_notify(subject: str, detail: str) -> None:
    try:
        sound = Path(os.path.expanduser("~/.claude/bin/claude-sound.sh"))
        if sound.exists():
            subprocess.run(
                [
                    str(sound),
                    "mesh-notify",
                    "incident-diagnose",
                    str(Path.cwd()),
                    f"{subject}: {detail}",
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
    except Exception:  # noqa: BLE001 — an alert failure must never break the diagnosis path
        pass


class IncidentMarshaller:
    """Assemble → persist → inline-into-a-read-only-worker → notify. Never auto-applies."""

    def __init__(
        self,
        *,
        incidents_dir: Path | None = None,
        log_tail_lines: int | None = None,
        docker_logs_fn: Callable[[str, int], str] | None = None,
        state_fn: Callable[[], str] | None = None,
        pool_fn: Callable[..., str] | None = None,
        notify_fn: Callable[[str, str], None] | None = None,
        apply_fn: Callable[[dict], None] | None = None,
    ) -> None:
        self.incidents_dir = Path(incidents_dir) if incidents_dir else _STATE / "incidents"
        self.log_tail_lines = log_tail_lines if log_tail_lines is not None else _DEFAULT_TAIL
        self._logs = docker_logs_fn or _default_docker_logs
        self._state = state_fn or _default_state
        self._pool = pool_fn or _default_pool
        self._notify = notify_fn or _default_notify
        # apply_fn is DELIBERATELY never invoked — the design has no auto-apply path. It is retained
        # only so a test can assert (count == 0) that no code path applies a fix without the operator.
        self._apply_fn = apply_fn

    def build_bundle(self, webhook: dict, *, containers: list[str]) -> dict:
        return {
            "webhook": webhook,
            "log_tails": {c: self._logs(c, self.log_tail_lines) for c in containers},
            "state": self._state(),
        }

    def write_bundle(self, incident_id: str, bundle: dict) -> Path:
        self.incidents_dir.mkdir(parents=True, exist_ok=True)
        path = self.incidents_dir / f"{incident_id}.json"
        tmp = path.with_suffix(f".{os.getpid()}.json.tmp")
        tmp.write_text(json.dumps(bundle, indent=2))
        os.replace(tmp, path)
        return path

    def diagnose(self, incident_id: str, webhook: dict, *, containers: list[str]) -> dict:
        # 1-2: assemble + persist the bundle BEFORE any dispatch (durable, and the worker is single-
        # shot read-only so it can't fetch this itself — it must arrive inlined in the prompt).
        bundle = self.build_bundle(webhook, containers=containers)
        path = self.write_bundle(incident_id, bundle)
        # 3: inline the bundle content into a single-shot read-only worker (NOT a path to read).
        prompt = self._diagnosis_prompt(incident_id, bundle)
        diagnosis = self._pool(prompt, mode="read_only")
        # 4: hand the operator the proposal — NEVER auto-apply (operator-gated).
        self._notify(
            "incident diagnosis (operator-gated — NOT applied)", f"{incident_id}: {diagnosis[:400]}"
        )
        return {
            "incident_id": incident_id,
            "bundle_path": str(path),
            "diagnosis": diagnosis,
            "applied": False,
        }

    def run_incident(
        self, webhook: dict, *, containers: list[str], governor: object | None = None
    ) -> dict:
        """TERMINAL incident entry — the call site the watchdog/error-webhook invokes.

        Routes the incident through the governor (`route("incident")`):
        - `ob@` (headroom + single-flight free): return `{"action":"run_on_obat", governor, ...}` so the
          caller runs the autonomous fix on ob@ and then calls `governor.release_incident()`;
        - otherwise (`pool-diagnose` — ob@ capped or a fix in flight): marshal a READ-ONLY pool
          diagnosis over the inlined bundle and hand the operator the proposal (never auto-applied).

        The fix is thus NEVER dropped: it runs on ob@ when it can, and is diagnosed + escalated when it
        can't. `governor` is injectable for tests; the default is a real `QuotaGovernor`.
        """
        gov = governor if governor is not None else _default_governor()
        incident_id = str(
            webhook.get("id") or webhook.get("event_id") or webhook.get("issue") or "incident"
        )
        dest = gov.route("incident", caller="watchdog")  # type: ignore[attr-defined]
        if dest == "ob@":
            return {"action": "run_on_obat", "incident_id": incident_id, "governor": gov}
        result = self.diagnose(incident_id, webhook, containers=containers)
        return {"action": "pool_diagnosed", **result}

    @staticmethod
    def _diagnosis_prompt(incident_id: str, bundle: dict) -> str:
        return (
            f"You are diagnosing incident {incident_id} for the Fabrik VPS fleet. ob@ is quota-capped, "
            "so you are a READ-ONLY diagnostician: reason ONLY over the bundle inlined below and return "
            "a concise root-cause + a proposed fix for a human operator to apply. Do NOT assume you can "
            "run commands or read files — everything you have is here.\n\n"
            "=== WEBHOOK ===\n" + json.dumps(bundle["webhook"], indent=2) + "\n\n"
            "=== HOST STATE ===\n" + str(bundle["state"]) + "\n\n"
            "=== CONTAINER LOG TAILS ===\n"
            + "\n".join(f"--- {c} ---\n{t}" for c, t in bundle["log_tails"].items())
        )


def _default_governor() -> object:
    """A real QuotaGovernor (co-located under scripts/sysadmin/)."""
    import sys

    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from quota_governor import QuotaGovernor  # noqa: PLC0415

    return QuotaGovernor()


def _main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover — CLI entry for the webhook source
    """CLI the watchdog / GlitchTip webhook source invokes: reads the webhook JSON on stdin.

    echo '<webhook json>' | incident_context.py diagnose --containers svc,worker [--incident-id id]
    """
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Incident context marshaller")
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("diagnose")
    d.add_argument("--containers", default="", help="comma-separated container names")
    d.add_argument("--incident-id", default=None)
    args = p.parse_args(argv)
    if args.cmd != "diagnose":
        p.print_help()
        return 2
    try:
        webhook = json.load(sys.stdin)
    except (ValueError, OSError):
        webhook = {}
    if args.incident_id:
        webhook.setdefault("id", args.incident_id)
    containers = [c.strip() for c in args.containers.split(",") if c.strip()]
    out = IncidentMarshaller().run_incident(webhook, containers=containers)
    # never print a governor object; report the routing action + any bundle path/diagnosis
    print(json.dumps({k: v for k, v in out.items() if k != "governor"}))
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI entry
    raise SystemExit(_main())
