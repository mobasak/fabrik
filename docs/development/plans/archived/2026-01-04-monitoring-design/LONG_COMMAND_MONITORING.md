> ⚠️ **ARCHIVED** — Design doc superseded by `PROCESS_MONITORING_QUICKSTART.md`. Implementation complete in `scripts/process_monitor.py`.

# Long-Running Command Monitoring Design

> **Context**: `droid_runner.py` wrapper for `droid exec` needs to detect stuck/hung states without killing legitimate long-running tasks

## Problem Statement

When `droid exec` produces no stdout events for extended periods, we need to distinguish:

1. **Legitimate work** - Network I/O, computation, disk operations (SAFE)
2. **Waiting for stdin** - Blocked on user input, will hang forever (DANGEROUS)
3. **Actually hung** - Deadlock, infinite loop, zombie process (STUCK)

## Technical Constraints

- Python 3.12 on Linux/WSL
- `droid exec` runs as subprocess
- Output via `stream-json` (JSONL format)
- Tasks can legitimately run 30+ minutes
- **Cannot provide interactive input** - fully automated workflow
- Must NOT prematurely kill legitimate tasks (100% certainty required)

---

## Process State Analysis

### Linux Process States (from `/proc/[pid]/stat`)

| State | Code | Meaning | Relevance |
|-------|------|---------|-----------|
| Running | `R` | Executing on CPU | Active work |
| Sleeping (Interruptible) | `S` | Waiting for event/I/O | **Most common** - could be stdin OR network |
| Disk Sleep (Uninterruptible) | `D` | Waiting for disk I/O | Legitimate work |
| Stopped | `T` | Stopped by signal | Manual intervention |
| Zombie | `Z` | Process terminated, waiting for parent | Dead |

**Key insight**: Both stdin-waiting and network-waiting show as `S` (sleeping). Cannot distinguish by state alone.

### File Descriptor Analysis

Processes waiting for stdin typically have:
- `stdin` (fd 0) open in read mode
- Blocked `read()` syscall on fd 0
- `/proc/[pid]/fd/0` → `/dev/pts/X` or pipe

However, this is **not sufficient** because:
- Many processes keep stdin open even when not reading
- Detecting active `read()` requires syscall tracing (overhead)

### I/O Activity Patterns

| Scenario | CPU % | I/O Bytes Delta | Network Connections | Process State |
|----------|-------|----------------|---------------------|---------------|
| **Computing** | 50-100% | Low | Stable | R or S |
| **Network request** | 0-5% | Low | Active socket in ESTABLISHED state | S |
| **Disk I/O** | 0-20% | **High** | Stable | S or D |
| **Stdin waiting** | 0% | **Zero** | Stable | S |
| **Hung/deadlock** | 0% | **Zero** | Stable | S or R |

**Critical observation**: Stdin-waiting and hung processes look identical in most metrics!

---

## Detection Strategy

### Multi-Signal Approach

We need to combine multiple signals over time windows to build confidence:

```
if no_stdout_events(300s) AND
   zero_cpu(60s) AND
   zero_io_delta(60s) AND
   no_network_activity(60s) AND
   process_state == 'S' AND
   stdin_fd_open():
   → LIKELY_STDIN_WAITING (confidence: high)

if no_stdout_events(300s) AND
   zero_cpu(60s) AND
   zero_io_delta(60s) AND
   network_connections_stable(60s) AND
   no_recent_syscalls():
   → LIKELY_HUNG (confidence: medium)
```

### Time Windows

| Window | Purpose |
|--------|---------|
| **5s** | Sampling interval for metrics |
| **60s** | Short-term activity window (zero activity = suspicious) |
| **300s** | Long-term inactivity threshold (trigger investigation) |
| **600s** | Maximum investigation period before escalation |

### Confidence Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **Low** | Some signs of stuck, but inconclusive | Log warning, continue monitoring |
| **Medium** | Multiple stuck indicators, likely issue | Log error, notify, continue monitoring |
| **High** | Strong evidence of stuck state | Log critical, recommend manual intervention |
| **Certain** | Definitive stuck (e.g., zombie state) | Log critical, safe to terminate |

**Important**: Even at "High" confidence, we DON'T auto-kill unless explicitly configured.

---

## Metrics to Monitor

### 1. Process-Level CPU Usage

```python
import psutil

def get_cpu_usage(proc: psutil.Process, interval: float = 1.0) -> float:
    """Get CPU usage percentage for process and children."""
    try:
        # Get process + all children
        processes = [proc] + proc.children(recursive=True)

        # Sum CPU percent (normalized to 1 core = 100%)
        total_cpu = sum(p.cpu_percent(interval=interval) for p in processes)
        return total_cpu
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0
```

**Thresholds:**
- `< 1%` for 60s → likely idle or waiting
- `< 0.1%` for 60s → very likely stuck or stdin-waiting

### 2. I/O Counters (Read/Write Bytes)

```python
def get_io_delta(proc: psutil.Process, previous_counters: dict) -> dict:
    """Get I/O byte delta since last check."""
    try:
        current = proc.io_counters()
        delta = {
            'read_bytes': current.read_bytes - previous_counters.get('read_bytes', 0),
            'write_bytes': current.write_bytes - previous_counters.get('write_bytes', 0),
        }
        return delta, {
            'read_bytes': current.read_bytes,
            'write_bytes': current.write_bytes,
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {'read_bytes': 0, 'write_bytes': 0}, previous_counters
```

**Thresholds:**
- `read_bytes + write_bytes < 1KB` for 60s → no disk activity
- Combined with zero CPU → likely stuck

### 3. Network Connections

```python
def has_active_network(proc: psutil.Process) -> tuple[bool, list]:
    """Check for active network connections."""
    try:
        connections = proc.connections(kind='inet')

        # Filter for active states
        active_states = {
            psutil.CONN_ESTABLISHED,
            psutil.CONN_SYN_SENT,
            psutil.CONN_SYN_RECV,
        }

        active = [c for c in connections if c.status in active_states]
        return len(active) > 0, active
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False, []
```

**Interpretation:**
- Active connections in `ESTABLISHED` or `SYN_*` → likely waiting for network
- No active connections + zero I/O + zero CPU → likely stuck or stdin-waiting

### 4. Process Status

```python
def get_process_status(proc: psutil.Process) -> dict:
    """Get detailed process status."""
    try:
        status_info = {
            'status': proc.status(),  # 'running', 'sleeping', 'disk-sleep', 'stopped', 'zombie'
            'num_threads': proc.num_threads(),
            'num_fds': proc.num_fds(),
            'memory_mb': proc.memory_info().rss / 1024 / 1024,
        }
        return status_info
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {'status': 'unknown', 'num_threads': 0, 'num_fds': 0, 'memory_mb': 0}
```

**Indicators:**
- `zombie` → process dead, safe to terminate
- `stopped` → manually paused, requires intervention
- `sleeping` → ambiguous, need other signals

### 5. File Descriptors (stdin detection)

```python
def is_stdin_open(proc: psutil.Process) -> bool:
    """Check if stdin (fd 0) is open."""
    try:
        fds = proc.open_files()
        # Also check /proc/[pid]/fd/0
        fd_path = Path(f"/proc/{proc.pid}/fd/0")
        if fd_path.exists():
            target = os.readlink(fd_path)
            # stdin usually points to /dev/pts/X, /dev/null, or pipe
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
        pass
    return False
```

**Warning**: This alone is NOT sufficient to detect stdin-waiting (many processes keep stdin open).

---

## Detection Algorithm

### State Machine

```
HEALTHY → SUSPICIOUS → LIKELY_STUCK → CONFIRMED_STUCK

HEALTHY:
  - Regular stdout events OR
  - CPU > 1% OR
  - I/O delta > 1KB/s OR
  - Active network connections

SUSPICIOUS (after 300s no stdout):
  - Enter investigation mode
  - Start collecting detailed metrics
  - Log warning

LIKELY_STUCK (after 60s in SUSPICIOUS):
  - CPU < 0.1% AND
  - I/O delta < 1KB AND
  - No active network
  - Log error with diagnosis

CONFIRMED_STUCK (after 600s in LIKELY_STUCK):
  - Sustained zero activity
  - OR zombie/stopped state
  - Log critical, recommend termination
```

### Implementation Pattern

```python
class ProcessMonitor:
    """Monitor subprocess for stuck/hung detection."""

    def __init__(self, proc: subprocess.Popen, check_interval: int = 5):
        self.proc = proc
        self.psutil_proc = psutil.Process(proc.pid)
        self.check_interval = check_interval

        # State
        self.state = "HEALTHY"
        self.last_stdout_time = time.time()
        self.suspicious_since = None
        self.likely_stuck_since = None

        # Metrics history (ring buffers)
        self.cpu_history = deque(maxlen=12)  # 60s at 5s intervals
        self.io_history = deque(maxlen=12)
        self.network_history = deque(maxlen=12)

        # Previous counters for delta calculation
        self.prev_io = {'read_bytes': 0, 'write_bytes': 0}

    def record_stdout_activity(self):
        """Call this when stdout event received."""
        self.last_stdout_time = time.time()
        if self.state != "HEALTHY":
            print(f"[MONITOR] Activity detected, returning to HEALTHY state")
            self.state = "HEALTHY"
            self.suspicious_since = None
            self.likely_stuck_since = None

    def collect_metrics(self) -> dict:
        """Collect current process metrics."""
        metrics = {
            'timestamp': time.time(),
            'cpu_percent': get_cpu_usage(self.psutil_proc, interval=0),
            'status': get_process_status(self.psutil_proc),
        }

        # I/O delta
        io_delta, self.prev_io = get_io_delta(self.psutil_proc, self.prev_io)
        metrics['io_delta'] = io_delta

        # Network
        has_net, connections = has_active_network(self.psutil_proc)
        metrics['has_network'] = has_net
        metrics['num_connections'] = len(connections)

        return metrics

    def analyze(self) -> dict:
        """Analyze current state and return diagnosis."""
        now = time.time()
        seconds_since_stdout = now - self.last_stdout_time

        # Collect current metrics
        current_metrics = self.collect_metrics()
        self.cpu_history.append(current_metrics['cpu_percent'])
        self.io_history.append(sum(current_metrics['io_delta'].values()))
        self.network_history.append(current_metrics['has_network'])

        # Check for immediate definitive states
        if current_metrics['status']['status'] == 'zombie':
            return {
                'state': 'CONFIRMED_STUCK',
                'confidence': 'certain',
                'reason': 'Process is zombie',
                'safe_to_kill': True,
            }

        # Need at least 60s of history
        if len(self.cpu_history) < 12:
            return {
                'state': 'HEALTHY',
                'confidence': 'low',
                'reason': 'Insufficient history',
                'safe_to_kill': False,
            }

        # Calculate activity over last 60s
        avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
        total_io = sum(self.io_history)
        any_network = any(self.network_history)

        # State transitions
        if seconds_since_stdout < 300:
            # Recent stdout activity
            self.state = "HEALTHY"
            return {
                'state': 'HEALTHY',
                'confidence': 'high',
                'reason': f'Recent stdout activity ({int(seconds_since_stdout)}s ago)',
                'safe_to_kill': False,
            }

        # No stdout for 300s - investigate
        if self.state == "HEALTHY":
            self.state = "SUSPICIOUS"
            self.suspicious_since = now
            return {
                'state': 'SUSPICIOUS',
                'confidence': 'low',
                'reason': f'No stdout for {int(seconds_since_stdout)}s, investigating',
                'safe_to_kill': False,
                'metrics': {
                    'avg_cpu': avg_cpu,
                    'total_io_kb': total_io / 1024,
                    'has_network': any_network,
                }
            }

        # In SUSPICIOUS - check for activity
        has_activity = (
            avg_cpu > 1.0 or
            total_io > 1024 or  # > 1KB in 60s
            any_network
        )

        if has_activity:
            return {
                'state': 'SUSPICIOUS',
                'confidence': 'low',
                'reason': 'No stdout but process shows activity',
                'safe_to_kill': False,
                'metrics': {
                    'avg_cpu': avg_cpu,
                    'total_io_kb': total_io / 1024,
                    'has_network': any_network,
                }
            }

        # No activity - escalate to LIKELY_STUCK
        if self.state == "SUSPICIOUS":
            self.state = "LIKELY_STUCK"
            self.likely_stuck_since = now

        suspicious_duration = now - self.suspicious_since

        if suspicious_duration < 60:
            return {
                'state': 'LIKELY_STUCK',
                'confidence': 'medium',
                'reason': f'Zero activity for {int(suspicious_duration)}s (CPU={avg_cpu:.2f}%, I/O={total_io}B)',
                'safe_to_kill': False,
            }

        # Sustained zero activity for 60s+
        if suspicious_duration < 600:
            return {
                'state': 'LIKELY_STUCK',
                'confidence': 'high',
                'reason': f'Sustained zero activity for {int(suspicious_duration)}s',
                'safe_to_kill': False,  # Still not 100% certain
                'recommendation': 'Consider manual intervention',
            }

        # 10+ minutes of zero activity
        self.state = "CONFIRMED_STUCK"
        return {
            'state': 'CONFIRMED_STUCK',
            'confidence': 'high',
            'reason': f'No activity for {int(suspicious_duration)}s (likely hung or stdin-waiting)',
            'safe_to_kill': False,  # User requested 100% certainty - never auto-kill
            'recommendation': 'Manual termination recommended',
        }
```

---

## Integration with droid_runner.py

### Minimal Changes

```python
# In run_droid_exec_monitored():

from collections import deque
import psutil

# After process starts
monitor = ProcessMonitor(process, check_interval=5)
last_check_time = time.time()

# In main loop (before or after reading stdout)
if time.time() - last_check_time >= monitor.check_interval:
    diagnosis = monitor.analyze()
    last_check_time = time.time()

    if diagnosis['state'] != 'HEALTHY':
        confidence = diagnosis['confidence']
        reason = diagnosis['reason']
        print(f"[{task_id}] ⚠️  {diagnosis['state']} ({confidence}): {reason}", file=sys.stderr)

        if diagnosis.get('recommendation'):
            print(f"[{task_id}] 💡 {diagnosis['recommendation']}", file=sys.stderr)

# When stdout event received
for line in process.stdout:
    monitor.record_stdout_activity()  # Reset to HEALTHY
    # ... rest of event processing
```

---

## Recommended Thresholds

### Conservative (Minimize False Positives)

```python
WARN_AFTER_STDOUT_SILENCE = 600  # 10 minutes
STUCK_CPU_THRESHOLD = 0.5        # < 0.5% CPU
STUCK_IO_THRESHOLD = 10240       # < 10KB in 60s
STUCK_DURATION_BEFORE_ESCALATION = 120  # 2 minutes of zero activity
```

### Aggressive (Faster Detection)

```python
WARN_AFTER_STDOUT_SILENCE = 300  # 5 minutes (current)
STUCK_CPU_THRESHOLD = 1.0        # < 1% CPU
STUCK_IO_THRESHOLD = 1024        # < 1KB in 60s
STUCK_DURATION_BEFORE_ESCALATION = 60   # 1 minute of zero activity
```

### Production (Balanced)

```python
WARN_AFTER_STDOUT_SILENCE = 300  # 5 minutes
STUCK_CPU_THRESHOLD = 0.5        # < 0.5% CPU
STUCK_IO_THRESHOLD = 5120        # < 5KB in 60s
STUCK_DURATION_BEFORE_ESCALATION = 90   # 1.5 minutes
```

---

## Stdin Prevention (Best Practice)

### Subprocess Configuration

```python
# CORRECT - prevents stdin blocking
process = subprocess.Popen(
    args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.DEVNULL,  # ← Critical: closes stdin
    text=True,
    cwd=cwd,
)
```

**Why this works:**
- `stdin=subprocess.DEVNULL` closes stdin (fd 0)
- Any attempt to read stdin immediately returns EOF
- Process cannot block waiting for input

### PTY Allocation Considerations

**Do NOT use PTY for automation:**
```python
# WRONG - creates pseudo-terminal
import pty
master, slave = pty.openpty()
process = subprocess.Popen(..., stdin=slave, stdout=master, stderr=master)
```

PTY makes the process think it's interactive, which can:
- Change command behavior (colors, buffering)
- Enable interactive prompts
- Cause unexpected blocking

---

## Network I/O Detection

### HTTP Request Patterns

Long network requests show distinct patterns:

```python
def diagnose_network_wait(monitor: ProcessMonitor) -> str:
    """Provide human-readable diagnosis for network waiting."""
    has_net, connections = has_active_network(monitor.psutil_proc)

    if not has_net:
        return "No active network connections"

    # Group by state
    by_state = {}
    for conn in connections:
        state = conn.status
        by_state[state] = by_state.get(state, 0) + 1

    # Describe
    parts = []
    for state, count in by_state.items():
        parts.append(f"{count} {state}")

    return f"Network: {', '.join(parts)}"
```

**Typical patterns:**
- **HTTP request**: 1 ESTABLISHED connection, low CPU, no stdout for 5-60s
- **Bulk download**: 1 ESTABLISHED, high I/O read, sustained activity
- **Stuck connection**: 1 ESTABLISHED or SYN_SENT for >60s, zero I/O delta

---

## Testing Strategy

### Synthetic Test Cases

```python
# Test 1: Legitimate long computation
droid exec "Calculate Fibonacci(50) iteratively"
# Expected: High CPU, zero network, no false positive

# Test 2: Network request
droid exec "Fetch https://example.com and analyze"
# Expected: Sleeping state, 1 ESTABLISHED connection, no false positive

# Test 3: Large file operation
droid exec "Process 1GB log file"
# Expected: High I/O, sleeping/disk-sleep state, no false positive

# Test 4: Intentional stdin wait (simulated)
echo "read -p 'Enter:' x" | bash
# Expected: Sleeping, zero CPU, zero I/O, stdin open → LIKELY_STUCK
```

### Validation

```bash
# Monitor test process
python -c "
import time
import psutil
proc = psutil.Process(PID)
for _ in range(60):
    print(f'CPU: {proc.cpu_percent(1):.1f}% | I/O: {proc.io_counters()}')
    time.sleep(5)
"
```

---

## Summary

### Key Takeaways

1. **Cannot definitively detect stdin-waiting** without syscall tracing
2. **Use multi-signal approach** - combine CPU, I/O, network, time
3. **Never auto-kill** - even at high confidence (user requirement)
4. **Prevent stdin blocking** - always use `stdin=subprocess.DEVNULL`
5. **Monitor gradually** - HEALTHY → SUSPICIOUS → LIKELY_STUCK → CONFIRMED_STUCK

### Recommended Implementation

1. **Add `stdin=subprocess.DEVNULL`** to subprocess.Popen (prevents 90% of issues)
2. **Implement ProcessMonitor class** with 5s polling
3. **Log warnings** at SUSPICIOUS (300s), errors at LIKELY_STUCK (360s)
4. **Never auto-terminate** - always require manual intervention
5. **Provide detailed diagnosis** with metrics for debugging

### When to Kill (Manual Decision)

Only safe to kill when:
- Process is `zombie` or `stopped` (certain)
- **OR** User explicitly approves after reviewing diagnosis
- **NEVER** auto-kill based on heuristics alone

---

## Next Steps

1. Review this design with team
2. Implement `ProcessMonitor` class in `droid_runner.py`
3. Add `stdin=subprocess.DEVNULL` to prevent blocking
4. Test with synthetic cases
5. Deploy with conservative thresholds
6. Tune based on production data

---

**Author**: Droid (Factory AI)
**Date**: 2026-01-04
**Status**: Design Complete, Ready for Implementation
