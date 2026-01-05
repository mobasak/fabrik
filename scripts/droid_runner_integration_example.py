#!/usr/bin/env python3
"""
Integration Example: ProcessMonitor with droid_runner.py

This shows how to integrate ProcessMonitor into the existing run_droid_exec_monitored() function.

Key changes:
1. Import ProcessMonitor
2. Add stdin=subprocess.DEVNULL to prevent stdin blocking
3. Create ProcessMonitor instance
4. Call monitor.record_activity() when stdout events received
5. Periodically call monitor.analyze() and log diagnostics
"""

import json
import subprocess
import sys
import time

from process_monitor import ProcessMonitor


def run_droid_exec_monitored_v2(
    prompt: str,
    task_id: str,
    model: str = "claude-opus-4-5-20251101",
    autonomy: str = "low",
    output_format: str = "stream-json",
    session_id: str | None = None,
    cwd: str | None = None,
    warn_after_seconds: int = 300,
):
    """
    Enhanced version with ProcessMonitor integration.

    Changes from original:
    1. Added stdin=subprocess.DEVNULL to Popen
    2. Created ProcessMonitor instance
    3. Call monitor.record_activity() on stdout events
    4. Periodic monitor.analyze() calls with diagnostic logging
    """

    # Build command
    args = ["droid", "exec", "--output-format", output_format, "--model", model, "--auto", autonomy]

    if session_id:
        args.extend(["--session-id", session_id])

    if cwd:
        args.extend(["--cwd", cwd])

    args.append(prompt)

    print(f"[{task_id}] Starting droid exec...", file=sys.stderr)

    # Start process
    # CRITICAL CHANGE: Added stdin=subprocess.DEVNULL
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # ← Prevent deadlock: don't pipe if not reading
        stdin=subprocess.DEVNULL,  # ← Prevent stdin blocking!
        text=True,
        cwd=cwd,
    )

    # Create process monitor
    monitor = ProcessMonitor(
        process,
        warn_threshold=warn_after_seconds,
        check_interval=5,
    )

    # Tracking variables
    start_time = time.time()
    last_check_time = start_time
    events = []
    final_text = ""
    captured_session_id = None

    try:
        # Read streaming events
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # CRITICAL: Record activity in monitor
            monitor.record_activity()

            try:
                event = json.loads(line)
                events.append(event)

                # Process event (same as original)
                if event.get("type") == "system" and event.get("subtype") == "init":
                    captured_session_id = event.get("session_id")
                    print(f"[{task_id}] Session: {captured_session_id}", file=sys.stderr)

                if event.get("type") == "message" and event.get("role") == "assistant":
                    text = event.get("text", "")[:100]
                    print(f"[{task_id}] Progress: {text}...", file=sys.stderr)

                if event.get("type") == "tool_call":
                    tool_name = event.get("toolName", "unknown")
                    print(f"[{task_id}] Tool: {tool_name}", file=sys.stderr)

                if event.get("type") == "completion":
                    final_text = event.get("finalText", "")
                    captured_session_id = event.get("session_id", captured_session_id)
                    duration_ms = event.get("durationMs")
                    print(f"[{task_id}] Completed in {duration_ms}ms", file=sys.stderr)
                    break

                if event.get("type") == "result" and event.get("is_error"):
                    error = event.get("result", "Unknown error")
                    print(f"[{task_id}] Error: {error}", file=sys.stderr)
                    break

            except json.JSONDecodeError:
                continue

            # Periodic monitoring check
            now = time.time()
            if now - last_check_time >= monitor.check_interval:
                diagnosis = monitor.analyze()
                last_check_time = now

                # Log based on state
                if diagnosis["state"] == "SUSPICIOUS":
                    print(f"[{task_id}] ⚠️  SUSPICIOUS: {diagnosis['reason']}", file=sys.stderr)
                    if diagnosis.get("metrics"):
                        m = diagnosis["metrics"]
                        print(
                            f"[{task_id}]     Metrics: CPU={m['avg_cpu']:.2f}%, "
                            f"I/O={m['total_io_bytes']}B, Network={m['any_network']}",
                            file=sys.stderr,
                        )

                elif diagnosis["state"] == "LIKELY_STUCK":
                    print(
                        f"[{task_id}] ❌ LIKELY_STUCK ({diagnosis['confidence']}): {diagnosis['reason']}",
                        file=sys.stderr,
                    )
                    if diagnosis.get("metrics"):
                        m = diagnosis["metrics"]
                        print(
                            f"[{task_id}]     Metrics: CPU={m['avg_cpu']:.2f}%, "
                            f"I/O={m['total_io_bytes']}B, Network={m['any_network']}",
                            file=sys.stderr,
                        )
                    if diagnosis.get("recommendation"):
                        print(f"[{task_id}]     💡 {diagnosis['recommendation']}", file=sys.stderr)

                elif diagnosis["state"] == "CONFIRMED_STUCK":
                    print(f"[{task_id}] 💀 CONFIRMED_STUCK: {diagnosis['reason']}", file=sys.stderr)
                    if diagnosis.get("recommendation"):
                        print(f"[{task_id}]     💡 {diagnosis['recommendation']}", file=sys.stderr)

                    # Optional: Could add auto-kill logic here if enabled
                    # But per requirements, we NEVER auto-kill

        # Wait for process to finish
        process.wait(timeout=30)

        return {
            "task_id": task_id,
            "session_id": captured_session_id,
            "final_text": final_text,
            "duration_ms": int((time.time() - start_time) * 1000),
            "num_events": len(events),
        }

    except Exception as e:
        print(f"[{task_id}] Exception: {e}", file=sys.stderr)
        raise

    finally:
        # Ensure process is terminated
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


# Example usage
if __name__ == "__main__":
    import sys

    result = run_droid_exec_monitored_v2(
        prompt="Analyze the codebase structure",
        task_id="test-123",
        autonomy="low",
    )

    print(f"\nResult: {result}")
