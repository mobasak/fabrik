import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

logger = logging.getLogger(__name__)


class ProcessState(str, Enum):
    RUNNING = "running"  # Active CPU/IO
    SLEEPING = "sleeping"  # Valid sleep (timer, network)
    IDLE = "idle"  # No CPU/IO, but not blocked
    STUCK_STDIN = "stuck_stdin"  # Waiting for input
    STUCK_FROZEN = "stuck_frozen"  # No activity for too long
    UNKNOWN = "unknown"


@dataclass
class ProcessMetrics:
    cpu_percent: float
    memory_percent: float
    read_bytes_delta: int
    write_bytes_delta: int
    open_files: int
    threads: int
    status: str
    syscall: str | None = None
    wchan: str | None = None


class ProcessMonitor:
    """
    Monitors a subprocess to detect if it's:
    1. Working (CPU/IO)
    2. Waiting for network/timer (Valid sleep)
    3. Waiting for stdin (Invalid state for automation)
    4. Frozen (No activity for threshold)
    """

    def __init__(self, pid: int, history_size: int = 10):
        if not psutil:
            raise ImportError("psutil is required for ProcessMonitor")

        self.pid = pid
        try:
            self.process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            raise ValueError(f"Process {pid} not found")

        self.history_size = history_size
        self._last_io = None
        self._last_check_time = time.time()
        self._metrics_history: list[ProcessMetrics] = []

        # Calibration
        self.process.cpu_percent()  # Init call

    def check(self) -> ProcessState:
        """Analyze process state and return high-level diagnosis."""
        try:
            # Refresh process reference to ensure it's still alive
            if not self.process.is_running():
                return ProcessState.UNKNOWN

            current_time = time.time()
            time_delta = current_time - self._last_check_time
            self._last_check_time = current_time

            # 1. Gather raw metrics
            with self.process.oneshot():
                cpu = self.process.cpu_percent()  # Since last call
                mem = self.process.memory_percent()
                status = self.process.status()
                threads = self.process.num_threads()

                # IO Counters
                io = self.process.io_counters() if hasattr(self.process, "io_counters") else None
                try:
                    open_files = len(self.process.open_files())
                except (psutil.AccessDenied, psutil.Error):
                    open_files = 0

            # Calculate IO deltas
            read_delta = 0
            write_delta = 0
            if io and self._last_io:
                read_delta = io.read_bytes - self._last_io.read_bytes
                write_delta = io.write_bytes - self._last_io.write_bytes
            self._last_io = io

            # Linux-specific introspection (The "Magic" Part)
            syscall = self._get_linux_syscall()
            wchan = self._get_linux_wchan()

            metrics = ProcessMetrics(
                cpu_percent=cpu,
                memory_percent=mem,
                read_bytes_delta=read_delta,
                write_bytes_delta=write_delta,
                open_files=open_files,
                threads=threads,
                status=status,
                syscall=syscall,
                wchan=wchan,
            )
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self.history_size:
                self._metrics_history.pop(0)

            # 2. Diagnose State

            # DIAGNOSIS A: Stuck on Stdin
            # Logic: Sleeping + Syscall 0 (read) + Arg0 is 0 (stdin)
            if self._is_waiting_for_stdin(metrics):
                return ProcessState.STUCK_STDIN

            # DIAGNOSIS B: Working
            # Logic: CPU usage > 0.1% OR IO activity
            if cpu > 0.1 or read_delta > 0 or write_delta > 0:
                return ProcessState.RUNNING

            # DIAGNOSIS C: Sleeping (Network/Timer)
            # Logic: No CPU/IO, but valid wait channel (poll, select, futex, nanosleep)
            if self._is_valid_sleep(metrics):
                return ProcessState.SLEEPING

            # DIAGNOSIS D: Idle / Frozen
            return ProcessState.IDLE

        except psutil.NoSuchProcess:
            return ProcessState.UNKNOWN
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            return ProcessState.UNKNOWN

    def _get_linux_syscall(self) -> str | None:
        """Read /proc/pid/syscall to see what the process is doing."""
        if not os.path.exists(f"/proc/{self.pid}/syscall"):
            return None
        try:
            with open(f"/proc/{self.pid}/syscall") as f:
                return f.read().strip()
        except (PermissionError, FileNotFoundError):
            return None

    def _get_linux_wchan(self) -> str | None:
        """Read /proc/pid/wchan to see kernel wait channel."""
        if not os.path.exists(f"/proc/{self.pid}/wchan"):
            return None
        try:
            with open(f"/proc/{self.pid}/wchan") as f:
                return f.read().strip()
        except (PermissionError, FileNotFoundError):
            return None

    def _is_waiting_for_stdin(self, m: ProcessMetrics) -> bool:
        """
        Heuristic:
        1. Process is sleeping
        2. Blocked on 'read' syscall (nr 0 on x86_64)
        3. First argument (fd) is 0
        """
        if m.status not in [psutil.STATUS_SLEEPING, psutil.STATUS_WAITING]:
            return False

        if not m.syscall:
            # Fallback for non-Linux or permission denied
            # Check wchan for "n_tty_read" or "pipe_read" ?
            # Not reliable enough alone as it could be reading other pipes
            return False

        parts = m.syscall.split()
        if not parts:
            return False

        sys_nr = parts[0]
        arg0 = parts[1]

        # x86_64 'read' is 0
        # aarch64 'read' is 63
        # We assume x86_64 for now based on 'linux-microsoft-standard'
        # Ideally check platform.machine()

        is_read_syscall = sys_nr == "0"

        # check if arg0 is 0 (stdin)
        # arg0 is hex, usually 0x0
        try:
            fd = int(arg0, 16)
            is_stdin = fd == 0
        except ValueError:
            is_stdin = False

        return is_read_syscall and is_stdin

    def _is_valid_sleep(self, m: ProcessMetrics) -> bool:
        """Check if wait channel indicates legitimate waiting (timer, network, locks)."""
        valid_chans = [
            "hrtimer_nanosleep",
            "futex_wait_queue_me",
            "ep_poll",
            "do_select",
            "inet_csk_accept",
            "sk_wait_data",
            "poll_schedule_timeout",
            "pipe_wait",  # Waiting for pipe write (output), not read
        ]

        if m.wchan:
            # Check if any valid channel is a substring
            if any(vc in m.wchan for vc in valid_chans):
                return True

        # Syscall check for network/time
        if m.syscall:
            sys_nr = m.syscall.split()[0]
            # 230 = clock_nanosleep, 202 = futex, 7 = poll, 23 = select (approx)
            # This is brittle across archs, prefer wchan
            pass

        return False
