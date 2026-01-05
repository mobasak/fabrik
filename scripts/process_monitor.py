#!/usr/bin/env python3
"""
Process Monitor - Detect stuck/hung subprocess states.

Monitors subprocess for stuck detection using multi-signal approach:
- CPU usage (process + children)
- I/O activity (disk read/write bytes)
- Network connections
- Process state (sleeping, running, zombie, etc.)
- Time since last activity

Usage:
    monitor = ProcessMonitor(subprocess_obj)

    # When stdout event received
    monitor.record_activity()

    # Periodic check (every 5s)
    diagnosis = monitor.analyze()
    if diagnosis['state'] != 'HEALTHY':
        print(f"Warning: {diagnosis['reason']}")
"""

import subprocess
import time
from collections import deque
from dataclasses import dataclass

try:
    import psutil
except ImportError:
    print("Error: psutil required. Install with: pip install psutil")
    raise


@dataclass
class ProcessMetrics:
    """Snapshot of process metrics at a point in time."""

    timestamp: float
    cpu_percent: float
    io_read_bytes: int
    io_write_bytes: int
    has_active_network: bool
    num_network_connections: int
    process_status: str  # 'running', 'sleeping', 'disk-sleep', 'zombie', etc.
    num_threads: int
    num_fds: int
    memory_mb: float


class ProcessMonitor:
    """
    Monitor subprocess for stuck/hung detection.

    States:
        HEALTHY      - Regular activity detected
        SUSPICIOUS   - No activity for warn_threshold seconds
        LIKELY_STUCK - Sustained zero activity (CPU, I/O, network)
        CONFIRMED_STUCK - Very high confidence stuck (zombie, or 10+ min idle)

    Args:
        proc: subprocess.Popen object to monitor
        warn_threshold: Seconds of inactivity before warning (default: 300)
        check_interval: Seconds between metric collection (default: 5)
        history_window: Seconds of history to keep (default: 60)
    """

    def __init__(
        self,
        proc: subprocess.Popen,
        warn_threshold: int = 300,
        check_interval: int = 5,
        history_window: int = 60,
    ):
        self.proc = proc
        self.check_interval = check_interval
        self.warn_threshold = warn_threshold

        # Convert to psutil.Process for rich monitoring
        try:
            self.psutil_proc = psutil.Process(proc.pid)
        except psutil.NoSuchProcess:
            raise ValueError(f"Process {proc.pid} does not exist")

        # State tracking
        self.state = "HEALTHY"
        self.last_activity_time = time.time()
        self.suspicious_since: float | None = None
        self.likely_stuck_since: float | None = None

        # Metrics history (ring buffers)
        history_size = history_window // check_interval
        self.metrics_history: deque[ProcessMetrics] = deque(maxlen=history_size)

        # Previous I/O counters for delta calculation
        self._prev_io_counters = None

    def record_activity(self):
        """
        Record activity detected (e.g., stdout event received).
        Resets state to HEALTHY.
        """
        self.last_activity_time = time.time()
        if self.state != "HEALTHY":
            self.state = "HEALTHY"
            self.suspicious_since = None
            self.likely_stuck_since = None

    def _get_cpu_usage(self) -> float:
        """Get CPU usage for process and all children."""
        try:
            processes = [self.psutil_proc] + self.psutil_proc.children(recursive=True)
            # cpu_percent() with interval=None uses previous call for delta
            # First call returns 0.0, subsequent calls return actual percentage
            total_cpu = sum(p.cpu_percent(interval=None) for p in processes if p.is_running())
            return total_cpu
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def _get_io_counters(self) -> tuple[int, int]:
        """Get current I/O read/write bytes."""
        try:
            io = self.psutil_proc.io_counters()
            return io.read_bytes, io.write_bytes
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0, 0

    def _has_active_network(self) -> tuple[bool, int]:
        """Check for active network connections."""
        try:
            connections = self.psutil_proc.connections(kind="inet")

            # Filter for active states
            active_states = {
                psutil.CONN_ESTABLISHED,
                psutil.CONN_SYN_SENT,
                psutil.CONN_SYN_RECV,
            }

            active = [c for c in connections if c.status in active_states]
            return len(active) > 0, len(active)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False, 0

    def _get_process_status(self) -> dict[str, any]:
        """Get detailed process status."""
        try:
            return {
                "status": self.psutil_proc.status(),
                "num_threads": self.psutil_proc.num_threads(),
                "num_fds": self.psutil_proc.num_fds(),
                "memory_mb": self.psutil_proc.memory_info().rss / 1024 / 1024,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {
                "status": "unknown",
                "num_threads": 0,
                "num_fds": 0,
                "memory_mb": 0,
            }

    def collect_metrics(self) -> ProcessMetrics:
        """Collect current process metrics snapshot."""
        now = time.time()

        # Get all metrics
        cpu = self._get_cpu_usage()
        io_read, io_write = self._get_io_counters()
        has_net, num_net = self._has_active_network()
        status_info = self._get_process_status()

        metrics = ProcessMetrics(
            timestamp=now,
            cpu_percent=cpu,
            io_read_bytes=io_read,
            io_write_bytes=io_write,
            has_active_network=has_net,
            num_network_connections=num_net,
            process_status=status_info["status"],
            num_threads=status_info["num_threads"],
            num_fds=status_info["num_fds"],
            memory_mb=status_info["memory_mb"],
        )

        # Store in history
        self.metrics_history.append(metrics)

        return metrics

    def _calculate_activity_score(self) -> dict[str, any]:
        """
        Calculate activity score from recent metrics history.

        Returns dict with:
            - avg_cpu: Average CPU % over history
            - total_io_bytes: Total I/O bytes over history
            - any_network: Whether any network activity seen
            - has_activity: Overall activity boolean
        """
        if len(self.metrics_history) < 2:
            return {
                "avg_cpu": 0.0,
                "total_io_bytes": 0,
                "any_network": False,
                "has_activity": False,
            }

        # Calculate deltas
        oldest = self.metrics_history[0]
        newest = self.metrics_history[-1]

        # Average CPU
        avg_cpu = sum(m.cpu_percent for m in self.metrics_history) / len(self.metrics_history)

        # Total I/O delta
        io_delta = (newest.io_read_bytes - oldest.io_read_bytes) + (
            newest.io_write_bytes - oldest.io_write_bytes
        )

        # Any network activity
        any_network = any(m.has_active_network for m in self.metrics_history)

        # Activity thresholds
        has_activity = (
            avg_cpu > 0.5  # > 0.5% CPU
            or io_delta > 5120  # > 5KB I/O
            or any_network  # Active network
        )

        return {
            "avg_cpu": avg_cpu,
            "total_io_bytes": io_delta,
            "any_network": any_network,
            "has_activity": has_activity,
        }

    def analyze(self) -> dict[str, any]:
        """
        Analyze current state and return diagnosis.

        Returns dict with:
            - state: Current state (HEALTHY, SUSPICIOUS, LIKELY_STUCK, CONFIRMED_STUCK)
            - confidence: Confidence level (low, medium, high, certain)
            - reason: Human-readable explanation
            - safe_to_kill: Whether safe to terminate (always False per requirements)
            - recommendation: Optional action recommendation
            - metrics: Optional detailed metrics
        """
        now = time.time()

        # Collect current metrics
        current = self.collect_metrics()

        # Check for definitive states
        if current.process_status == "zombie":
            return {
                "state": "CONFIRMED_STUCK",
                "confidence": "certain",
                "reason": "Process is zombie (terminated but not reaped)",
                "safe_to_kill": True,  # Zombie is truly dead
                "recommendation": "Safe to terminate",
            }

        if current.process_status == "stopped":
            return {
                "state": "CONFIRMED_STUCK",
                "confidence": "certain",
                "reason": "Process is stopped (paused by signal)",
                "safe_to_kill": False,
                "recommendation": "Resume with SIGCONT or terminate",
            }

        # Calculate time since last activity
        seconds_since_activity = now - self.last_activity_time

        # Recent activity - return to healthy
        if seconds_since_activity < self.warn_threshold:
            self.state = "HEALTHY"
            self.suspicious_since = None
            self.likely_stuck_since = None
            return {
                "state": "HEALTHY",
                "confidence": "high",
                "reason": f"Recent activity ({int(seconds_since_activity)}s ago)",
                "safe_to_kill": False,
            }

        # Need sufficient history for analysis
        if len(self.metrics_history) < 2:
            return {
                "state": "HEALTHY",
                "confidence": "low",
                "reason": "Insufficient metrics history",
                "safe_to_kill": False,
            }

        # Calculate activity score
        activity = self._calculate_activity_score()

        # Transition to SUSPICIOUS
        if self.state == "HEALTHY":
            self.state = "SUSPICIOUS"
            self.suspicious_since = now
            return {
                "state": "SUSPICIOUS",
                "confidence": "low",
                "reason": f"No activity for {int(seconds_since_activity)}s, investigating",
                "safe_to_kill": False,
                "metrics": activity,
            }

        # Check if process has activity (even without stdout events)
        if activity["has_activity"]:
            return {
                "state": "SUSPICIOUS",
                "confidence": "low",
                "reason": (
                    f'No stdout for {int(seconds_since_activity)}s but process active '
                    f'(CPU={activity["avg_cpu"]:.2f}%, I/O={activity["total_io_bytes"]}B, '
                    f'Net={activity["any_network"]})'
                ),
                "safe_to_kill": False,
                "metrics": activity,
            }

        # No activity - escalate to LIKELY_STUCK
        if self.state == "SUSPICIOUS":
            self.state = "LIKELY_STUCK"
            self.likely_stuck_since = now

        suspicious_duration = now - self.suspicious_since

        # Short period of zero activity
        if suspicious_duration < 60:
            return {
                "state": "LIKELY_STUCK",
                "confidence": "medium",
                "reason": (
                    f'Zero activity for {int(suspicious_duration)}s '
                    f'(CPU={activity["avg_cpu"]:.2f}%, I/O={activity["total_io_bytes"]}B)'
                ),
                "safe_to_kill": False,
                "metrics": activity,
            }

        # Sustained zero activity (60s-600s)
        if suspicious_duration < 600:
            return {
                "state": "LIKELY_STUCK",
                "confidence": "high",
                "reason": f"Sustained zero activity for {int(suspicious_duration)}s",
                "safe_to_kill": False,
                "recommendation": "Consider manual intervention",
                "metrics": activity,
            }

        # Very long zero activity (10+ minutes)
        self.state = "CONFIRMED_STUCK"
        return {
            "state": "CONFIRMED_STUCK",
            "confidence": "high",
            "reason": (
                f"No activity for {int(suspicious_duration)}s "
                f"(likely hung or waiting for stdin)"
            ),
            "safe_to_kill": False,  # Never auto-kill per requirements
            "recommendation": "Manual termination recommended",
            "metrics": activity,
        }

    def get_network_diagnosis(self) -> str:
        """Get human-readable network connection diagnosis."""
        try:
            connections = self.psutil_proc.connections(kind="inet")
            if not connections:
                return "No network connections"

            # Group by state
            by_state = {}
            for conn in connections:
                state = conn.status
                by_state[state] = by_state.get(state, 0) + 1

            # Format
            parts = []
            for state, count in sorted(by_state.items()):
                parts.append(f"{count} {state}")

            return f"Network: {', '.join(parts)}"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "Network: unknown"

    def is_process_alive(self) -> bool:
        """Check if process is still alive."""
        return self.proc.poll() is None


def demo():
    """Demo usage of ProcessMonitor."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python process_monitor.py <command> [args...]")
        print("Example: python process_monitor.py sleep 600")
        sys.exit(1)

    # Start subprocess
    cmd = sys.argv[1:]
    print(f"Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,  # Prevent stdin blocking
        text=True,
    )

    # Create monitor
    monitor = ProcessMonitor(proc, warn_threshold=10, check_interval=2)

    print(f"Monitoring PID {proc.pid}...")
    print("Press Ctrl+C to stop\n")

    try:
        while monitor.is_process_alive():
            time.sleep(monitor.check_interval)

            diagnosis = monitor.analyze()

            # Print diagnosis
            state_emoji = {
                "HEALTHY": "✅",
                "SUSPICIOUS": "⚠️ ",
                "LIKELY_STUCK": "❌",
                "CONFIRMED_STUCK": "💀",
            }
            emoji = state_emoji.get(diagnosis["state"], "❓")

            print(f"{emoji} {diagnosis['state']:15} | {diagnosis['reason']}")

            if diagnosis.get("metrics"):
                m = diagnosis["metrics"]
                print(
                    f"   Metrics: CPU={m['avg_cpu']:.2f}%, I/O={m['total_io_bytes']}B, Net={m['any_network']}"
                )

            if diagnosis.get("recommendation"):
                print(f"   💡 {diagnosis['recommendation']}")

            print()

        print(f"\nProcess exited with code: {proc.returncode}")

    except KeyboardInterrupt:
        print("\n\nInterrupted. Terminating process...")
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    demo()
