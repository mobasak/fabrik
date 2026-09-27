#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/KILO_AGENT_MANAGEMENT.md
# RETIRED 2026-07-19 — Kilo CLI stack retired (operator directive: LLM access = Claude Max OAuth + OpenRouter only). Zero runtime callers; kept for history — do not use.
"""
Kilo auto-router — runtime entry point Traycer calls instead of role-pinned
agent scripts.

This is the file where the architecture's value finally materializes. Without
it, every ticket still hits whichever model the .sh script filename happens
to encode. Here, a ticket comes in and we:

  1. Classify it via classify_ticket.py (rule-based, no LLM)
  2. Resolve the role + priority to a concrete Kilo model via db_models.py
  3. Apply the same-family cross-role guard if --exclude-provider is set
  4. Open a ticket_outcomes row (telemetry start)
  5. Exec `kilo run --model <chosen> --auto ...`
  6. Update the ticket_outcomes row with duration on completion

Distinguished from `kilo_dispatch.py`: that file is the Cascade-to-Kilo bridge
that runs a SPECIFIC pre-chosen agent script. This file is the auto-router
that PICKS the agent based on the ticket content.

Usage from Traycer (typical):

    # In coding-auto.sh that Traycer dispatches:
    python /opt/fabrik/scripts/kilo_auto_route.py \\
        --ticket-id "$TRAYCER_TASK_ID" \\
        --auto-classify

Usage with explicit role (non-coding):

    python kilo_auto_route.py --role reviewing --ticket-id T-123 \\
        --exclude-provider google      # cross-family guard

Two-step ticket flow (code, then review without sharing provider):

    coder_role=coding_complex
    coder_provider=$(python kilo_auto_route.py --role $coder_role --print-provider)
    python kilo_auto_route.py --role $coder_role --ticket-id "$ID-code"
    python kilo_auto_route.py --role reviewing --ticket-id "$ID-review" \\
        --exclude-provider "$coder_provider"
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BENCHMARKS_DIR = SCRIPT_DIR / "kilo-benchmarks"
sys.path.insert(0, str(BENCHMARKS_DIR))

from classify_ticket import classify_ticket  # noqa: E402
from db_models import (  # noqa: E402
    get_model_avoiding_provider,
    get_model_for_priority,
)
from kilo_telemetry import (  # noqa: E402
    complete_ticket,
    parse_kilo_json_stream,
    start_ticket,
)


def log(msg: str) -> None:
    print(f"[kilo-auto-route] {msg}", file=sys.stderr)


def read_prompt() -> str:
    """Pull the ticket prompt from Traycer env or stdin."""
    tmp = os.environ.get("TRAYCER_PROMPT_TMP_FILE")
    if tmp and Path(tmp).exists():
        return Path(tmp).read_text()
    env_prompt = os.environ.get("TRAYCER_PROMPT")
    if env_prompt:
        return env_prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kilo auto-router — classify, route, run, log")
    p.add_argument(
        "--ticket-id",
        default=os.environ.get("TRAYCER_TASK_ID"),
        help="Stable id (defaults to $TRAYCER_TASK_ID, else a uuid)",
    )
    p.add_argument("--title", default=None, help="Ticket title (first line of prompt if omitted)")
    p.add_argument("--description", default=None, help="Body (defaults to $TRAYCER_PROMPT)")
    p.add_argument(
        "--files", type=int, default=1, help="estimated_files for classifier (default 1)"
    )
    p.add_argument(
        "--lines", type=int, default=0, help="estimated_lines for classifier (default 0)"
    )

    p.add_argument(
        "--role",
        default=None,
        help="Skip auto-classification and dispatch to this role directly "
        "(coding_simple | coding_complex | reviewing | fixing | documentation | testing)",
    )
    p.add_argument(
        "--auto-classify",
        action="store_true",
        help="Classify into coding_simple|coding_complex (default if --role omitted)",
    )
    p.add_argument(
        "--priority", type=int, default=1, help="Starting priority (default 1 = cheapest qualified)"
    )
    p.add_argument(
        "--exclude-provider",
        default=None,
        help="Cross-family guard: avoid this provider when resolving the role",
    )

    p.add_argument(
        "--format",
        default="json",
        help="kilo run --format value. Default 'json' enables cost capture from "
        "step_finish events. Use 'default' to disable parsing and stream raw "
        "output (telemetry cost_usd will stay NULL in that mode).",
    )
    p.add_argument(
        "--no-thinking",
        action="store_true",
        help="Omit --thinking (default: thinking on for coding_complex + reviewing)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print chosen model + kilo command, do not execute"
    )
    p.add_argument(
        "--print-provider",
        action="store_true",
        help="Print the chosen agent's provider and exit (no kilo invocation). "
        "Use to feed --exclude-provider into a subsequent reviewer dispatch.",
    )
    return p.parse_args()


def resolve_role_and_model(
    args: argparse.Namespace, prompt: str
) -> tuple[str, str, str | None, int, str]:
    """Decide role/model/priority/resolution_reason for the ticket."""
    title = args.title or (prompt.splitlines()[0] if prompt else "")
    description = args.description if args.description is not None else prompt

    if args.role:
        role = args.role
        classifier_confidence = "explicit-role"
    else:
        ticket = {
            "title": title,
            "description": description,
            "estimated_files": args.files,
            "estimated_lines": args.lines,
        }
        role, classifier_confidence = classify_ticket(ticket)

    if args.exclude_provider:
        model, resolved_priority, guard_reason = get_model_avoiding_provider(
            role, args.exclude_provider, max_priority=5
        )
        resolution_reason = f"same-family-guard:{guard_reason}"
        if model is None or resolved_priority is None:
            model = get_model_for_priority(role, args.priority)
            resolved_priority = args.priority
            resolution_reason = "fallback-after-guard-empty"
    else:
        model = get_model_for_priority(role, args.priority)
        resolved_priority = args.priority
        resolution_reason = f"priority-{args.priority}"

    return role, classifier_confidence, model, resolved_priority, resolution_reason


def model_id_to_provider(model_id: str | None) -> str | None:
    """Extract provider segment from a Kilo model id like 'kilo/google/gemini-3.1-pro-preview'."""
    if not model_id:
        return None
    parts = model_id.split("/")
    # kilo / provider / model[/...]
    if len(parts) >= 3 and parts[0] == "kilo":
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return None


def build_kilo_command(model_id: str, prompt: str, fmt: str, thinking: bool) -> list[str]:
    cmd = ["kilo", "run", "--format", fmt, "--auto"]
    if thinking:
        cmd.append("--thinking")
    cmd.extend(["--model", model_id, prompt])
    return cmd


def main() -> int:
    args = parse_args()
    prompt = read_prompt()

    if not prompt and not args.description and not args.dry_run and not args.print_provider:
        log("ERROR: no prompt found (set $TRAYCER_PROMPT, pipe via stdin, or pass --description)")
        return 2

    ticket_id = args.ticket_id or f"adhoc-{uuid.uuid4().hex[:8]}"

    role, confidence, model_id, priority_used, resolution_reason = resolve_role_and_model(
        args, prompt
    )
    if not model_id:
        log(f"ERROR: no agent assigned for role={role} (run role_mapper.py first?)")
        return 3

    if args.print_provider:
        provider = model_id_to_provider(model_id)
        print(provider or "")
        return 0

    log(
        f"ticket={ticket_id} role={role} confidence={confidence} "
        f"model={model_id} priority={priority_used} resolution={resolution_reason}"
    )

    try:
        start_ticket(
            ticket_id=ticket_id,
            role_called=role,
            classifier_confidence=f"{confidence}|{resolution_reason}",
            priority_used=priority_used,
            agent_used=model_id,
        )
    except Exception as e:
        log(f"WARNING: telemetry start failed: {e}")

    thinking_default = role in ("coding_complex", "reviewing")
    thinking = (not args.no_thinking) and thinking_default

    cmd = build_kilo_command(model_id, prompt, args.format, thinking)

    if args.dry_run:
        log("--dry-run: would execute:")
        print(" ".join(shlex.quote(c) for c in cmd))
        try:
            complete_ticket(ticket_id=ticket_id, duration_seconds=0.0, agent_used=model_id)
        except Exception:
            pass
        return 0

    start = time.monotonic()
    cost_usd: float | None = None
    parse_warning: str | None = None

    try:
        if args.format == "json":
            # Capture-and-parse: Kilo emits concatenated JSON objects; we sum
            # cost from step_finish events and re-emit text events to stdout
            # so Traycer / the caller sees the model's response unchanged.
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            rc = result.returncode
            parsed = parse_kilo_json_stream(result.stdout)

            # Emit text to stdout for Traycer / user
            if parsed["text"]:
                sys.stdout.write(parsed["text"])
                if not parsed["text"].endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()

            # Forward any Kilo stderr so errors aren't swallowed
            if result.stderr:
                sys.stderr.write(result.stderr)

            if parsed["had_step_finish"]:
                cost_usd = parsed["cost_usd"]
            else:
                # No step_finish event → run was incomplete; don't claim $0 cost
                parse_warning = "no step_finish events in Kilo output — cost telemetry stays NULL"
                if parsed["error"]:
                    parse_warning += f"; kilo error: {parsed['error']}"
        else:
            # Legacy / streaming path: hand stdout to caller directly,
            # no cost capture. Use for interactive runs where streaming matters.
            result = subprocess.run(cmd, check=False)
            rc = result.returncode
    except FileNotFoundError:
        log("ERROR: `kilo` executable not found in PATH")
        try:
            complete_ticket(
                ticket_id=ticket_id, duration_seconds=time.monotonic() - start, agent_used=model_id
            )
        except Exception:
            pass
        return 127

    duration = time.monotonic() - start

    if parse_warning:
        log(f"WARNING: {parse_warning}")

    try:
        complete_ticket(
            ticket_id=ticket_id,
            cost_usd=cost_usd,
            duration_seconds=round(duration, 2),
            agent_used=model_id,
        )
    except Exception as e:
        log(f"WARNING: telemetry complete failed: {e}")

    cost_str = f"${cost_usd:.4f}" if cost_usd is not None else "n/a"
    log(f"ticket={ticket_id} exit={rc} duration={duration:.1f}s cost={cost_str}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
