> ⚠️ **ARCHIVED** — Design doc superseded by `PROCESS_MONITORING_QUICKSTART.md`. Implementation complete in `scripts/process_monitor.py`.

# Droid Runner Monitoring Design

## Context

The `droid_runner.py` script wraps the `droid exec` CLI to execute AI coding tasks. A critical challenge is reliably distinguishing between:
1. **Working State**: legitimate heavy computation or I/O.
2. **Valid Wait**: waiting for network, timers, or locks.
3. **Invalid Wait**: blocked on stdin (hanging forever in non-interactive mode).
4. **Frozen**: deadlocked or zombie.

This design leverages Linux process introspection (via `psutil` and `/proc` filesystem) to provide robust, zero-configuration detection of these states.

## Detection Strategy

### 1. Stdin Block Detection (The "Smoking Gun")

On Linux, when a process attempts to read from a pipe (like stdin) and no data is available, it blocks. This state is visible in the kernel via:
- **Syscall**: The process is executing the `read` system call (syscall number 0 on x86_64).
- **Arguments**: The first argument to `read` is the file descriptor `0` (stdin).
- **State**: The process status is `sleeping` (interruptible sleep).

**Heuristic**:
```python
is_stuck_on_stdin = (
    state == "sleeping" AND
    syscall == "read" AND
    arg0 == 0
)
```

This is superior to simple CPU timeouts because it positively identifies *why* the process is sleeping.

### 2. Valid vs Invalid Sleep

We can distinguish legitimate waiting (e.g., `time.sleep`, network requests) from stuck states by checking the **Wait Channel** (`wchan`) and syscalls.

| State | Syscall | Wchan (Kernel Function) | Diagnosis |
|-------|---------|-------------------------|-----------|
| **Stdin Wait** | `read(0, ...)` | `pipe_read`, `n_tty_read` | ❌ **STUCK** |
| **Timer** | `nanosleep`, `select` | `hrtimer_nanosleep` | ✅ **Valid Sleep** |
| **Network** | `poll`, `accept`, `recv` | `ep_poll`, `inet_csk_accept`, `sk_wait_data` | ✅ **Valid Sleep** |
| **Busy** | (none) | `0` / (running) | ✅ **Working** |

## Implementation

The solution is implemented in `src/fabrik/monitor.py`.

### Class: `ProcessMonitor`

**Usage:**

```python
from fabrik.monitor import ProcessMonitor, ProcessState

monitor = ProcessMonitor(pid=12345)

while True:
    state = monitor.check()

    if state == ProcessState.STUCK_STDIN:
        print("ERROR: Process is waiting for input!")
        process.kill()
        break

    elif state == ProcessState.RUNNING:
        print("Working...")

    elif state == ProcessState.SLEEPING:
        print("Waiting (Network/Timer)...")

    time.sleep(5)
```

### Metrics Collected

The `ProcessMetrics` data class captures:
- `cpu_percent`: CPU usage (instantaneous).
- `read/write_bytes_delta`: I/O activity since last check.
- `syscall`: Current system call (Linux only).
- `wchan`: Current kernel wait channel (Linux only).

## Integration Guide for `droid_runner.py`

To integrate this into the runner:

1. **Import**:
   ```python
   from fabrik.monitor import ProcessMonitor, ProcessState
   ```

2. **Initialize**:
   Inside `run_droid_exec_monitored`, after `process = subprocess.Popen(...)`:
   ```python
   monitor = ProcessMonitor(process.pid)
   ```

3. **Check Loop**:
   In the main event loop (or a separate thread/timer):
   ```python
   # Check every 5-10 seconds
   if time.time() - last_check > 5:
       state = monitor.check()
       if state == ProcessState.STUCK_STDIN:
           print(f"[{task_id}] 🛑 DETECTED STDIN WAIT - Terminating")
           process.terminate()
           record.status = TaskStatus.STUCK
           break
   ```

## Limitations

1. **Platform Support**: The deep introspection (`syscall`, `wchan`) is **Linux-only**. On macOS/Windows, it falls back to basic CPU/IO monitoring (less precise).
2. **Privileges**: Reading `/proc/{pid}/syscall` requires the same user or root. Since `droid_runner` spawns the process, it owns it, so permissions are fine.
3. **Architecture**: Syscall numbers vary by arch (x86_64 vs ARM64). The current implementation assumes x86_64 syscall `0` for read. For ARM64 compatibility, check `platform.machine()` (read is `63` on aarch64).

## Configuration

**Thresholds:**
- **Stuck Timeout**: 300s (5 mins) of `IDLE` state (no CPU, no I/O, no events).
- **Stdin Stuck**: Immediate termination (confirmed invalid state).
