# Process Monitoring Quick Start

> **TL;DR**: Use `ProcessMonitor` to detect stuck `droid exec` processes without killing legitimate long-running tasks.

## Installation

```bash
# Install dependency
pip install psutil

# Verify
python3 -c "import psutil; print(f'psutil {psutil.__version__} installed')"
```

## Quick Integration (3 Steps)

### 1. Import ProcessMonitor

```python
from scripts.process_monitor import ProcessMonitor
```

### 2. Add stdin=DEVNULL to subprocess (CRITICAL!)

```python
# BEFORE (can block on stdin):
process = subprocess.Popen(
    args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# AFTER (prevents stdin blocking):
process = subprocess.Popen(
    args,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.DEVNULL,  # ← Add this!
    text=True,
)
```

### 3. Create monitor and integrate

```python
# Create monitor after starting process
monitor = ProcessMonitor(process, warn_threshold=300, check_interval=5)

# In your stdout reading loop
for line in process.stdout:
    # When event received, record activity
    monitor.record_activity()

    # Process event...
    event = json.loads(line)
    # ... your existing code ...

# Periodically check status (every 5s)
last_check = time.time()
if time.time() - last_check >= monitor.check_interval:
    diagnosis = monitor.analyze()

    if diagnosis['state'] != 'HEALTHY':
        print(f"⚠️  {diagnosis['state']}: {diagnosis['reason']}")

    last_check = time.time()
```

## Complete Example

See `/opt/fabrik/scripts/droid_runner_integration_example.py` for full integration.

## Configuration

### Conservative (Low False Positives)

```python
monitor = ProcessMonitor(
    process,
    warn_threshold=600,      # 10 minutes before warning
    check_interval=5,         # Check every 5 seconds
    history_window=60,        # Keep 60s of metrics
)
```

### Balanced (Recommended)

```python
monitor = ProcessMonitor(
    process,
    warn_threshold=300,      # 5 minutes before warning
    check_interval=5,
    history_window=60,
)
```

### Aggressive (Fast Detection)

```python
monitor = ProcessMonitor(
    process,
    warn_threshold=120,      # 2 minutes before warning
    check_interval=3,
    history_window=60,
)
```

## Understanding the Output

### States

| State | Meaning | Action |
|-------|---------|--------|
| **HEALTHY** | Regular activity detected | None |
| **SUSPICIOUS** | No activity for warn_threshold seconds | Log warning, continue monitoring |
| **LIKELY_STUCK** | Sustained zero CPU/I/O/network | Log error with metrics |
| **CONFIRMED_STUCK** | Very long idle OR zombie state | Recommend manual termination |

### Confidence Levels

| Level | Meaning |
|-------|---------|
| **low** | Some signs, but inconclusive |
| **medium** | Multiple indicators, likely issue |
| **high** | Strong evidence of stuck state |
| **certain** | Definitive (e.g., zombie process) |

### Example Output

```
[task-123] ⚠️  SUSPICIOUS: No activity for 305s, investigating
[task-123]     Metrics: CPU=0.00%, I/O=0B, Network=False

[task-123] ❌ LIKELY_STUCK (high): Sustained zero activity for 385s
[task-123]     Metrics: CPU=0.00%, I/O=0B, Network=False
[task-123]     💡 Consider manual intervention

[task-123] 💀 CONFIRMED_STUCK: No activity for 615s (likely hung or stdin-waiting)
[task-123]     💡 Manual termination recommended
```

## Testing

Run the test suite to verify everything works:

```bash
python3 scripts/test_process_monitor.py
```

Expected output:
```
# ProcessMonitor Test Suite
============================================================

TEST 1: Quick Exit
✅ PASS

TEST 2: Long Computation (High CPU)
✅ PASS

TEST 3: Network Wait Simulation (sleep)
✅ PASS

...

# Results: 8 passed, 0 failed
```

## Diagnostic Demo

Test on a long-running command:

```bash
# Monitor a sleep command
python3 scripts/process_monitor.py sleep 60

# Expected progression:
# ✅ HEALTHY           | Recent activity (0s ago)
# ⚠️  SUSPICIOUS       | No activity for 10s, investigating
# ❌ LIKELY_STUCK      | Zero activity for 12s (CPU=0.00%, I/O=0B)
# 💀 CONFIRMED_STUCK   | No activity for 65s (likely hung or stdin-waiting)
```

## Key Metrics Explained

### CPU Percent
- **> 1%**: Active computation
- **< 0.5%**: Idle or waiting
- **0%**: Sleeping (could be network wait, stdin wait, or hung)

### I/O Bytes Delta
- **> 5KB/s**: Disk activity (reading/writing files)
- **< 1KB/s**: No disk activity
- **0**: No file operations

### Network Activity
- **True**: Active network connections (HTTP requests, etc.)
- **False**: No network or only idle connections

### Interpretation

| CPU | I/O | Network | Likely Meaning |
|-----|-----|---------|----------------|
| High | Low | Any | Computation |
| Low | High | Any | Disk operations |
| Low | Low | True | Network request (legitimate wait) |
| Zero | Zero | False | **Stuck or stdin-waiting** |

## Why stdin=DEVNULL Matters

**Without it:**
```python
proc = subprocess.Popen(["bash", "-c", "read -p 'Enter: '"], stdout=PIPE)
# ☠️ Process blocks forever waiting for input
```

**With it:**
```python
proc = subprocess.Popen(
    ["bash", "-c", "read -p 'Enter: '"],
    stdout=PIPE,
    stdin=subprocess.DEVNULL,  # ← Closes stdin
)
# ✅ read command immediately gets EOF, script continues
```

**Test it:**
```bash
# Blocks forever (Ctrl+C to exit)
echo "read x" | bash

# Returns immediately
echo "read x" | bash </dev/null
```

## FAQ

### Q: Why doesn't it auto-kill stuck processes?

**A**: Per user requirements, we need 100% certainty before killing. Even at "CONFIRMED_STUCK", there's a small chance of false positive (e.g., very slow network). Human judgment is required.

### Q: How to distinguish network wait from stdin wait?

**A**: Network waiting shows active connections in `ESTABLISHED` state. Check with `monitor.get_network_diagnosis()`. Both show zero CPU/I/O, but network has active sockets.

### Q: What if my task legitimately takes 30+ minutes?

**A**: As long as it produces stdout events periodically (tool calls, progress updates), the monitor will stay in HEALTHY state. Use higher `warn_threshold` for very long tasks.

### Q: Can I auto-kill in development/testing?

**A**: Yes, but implement carefully:
```python
diagnosis = monitor.analyze()
if diagnosis['state'] == 'CONFIRMED_STUCK' and AUTO_KILL_ENABLED:
    if diagnosis.get('safe_to_kill'):  # Only for zombie/stopped
        process.kill()
    elif user_approved:  # Require confirmation for others
        process.terminate()
```

### Q: Does this work on Windows?

**A**: Yes, `psutil` is cross-platform. File descriptor checks may behave differently, but core CPU/I/O/network monitoring works.

### Q: Performance impact?

**A**: Minimal. Default check_interval=5s means:
- 0.2 checks/second
- ~1ms per check (reading `/proc` files)
- Negligible CPU/memory overhead

## Troubleshooting

### "psutil.NoSuchProcess" errors

**Cause**: Process exited between checks
**Solution**: Already handled in ProcessMonitor - returns safe defaults

### False positives (process marked stuck but isn't)

**Solutions**:
1. Increase `warn_threshold` (default 300s → 600s)
2. Lower activity thresholds in `_calculate_activity_score()`
3. Ensure `monitor.record_activity()` is called for ALL stdout events

### False negatives (stuck process not detected)

**Solutions**:
1. Decrease `warn_threshold` (300s → 120s)
2. Raise activity thresholds (require more I/O to count as active)
3. Verify `stdin=subprocess.DEVNULL` is set

### Process keeps running after termination

**Check**:
```python
# Ensure proper cleanup
if process.poll() is None:
    process.terminate()
    process.wait(timeout=5)
    if process.poll() is None:
        process.kill()  # Force kill if still alive
```

## Additional Resources

- **Design Document**: `/opt/fabrik/docs/reference/LONG_COMMAND_MONITORING.md`
- **Full Implementation**: `/opt/fabrik/scripts/process_monitor.py`
- **Integration Example**: `/opt/fabrik/scripts/droid_runner_integration_example.py`
- **Test Suite**: `/opt/fabrik/scripts/test_process_monitor.py`

## Next Steps

1. Review design document for detailed rationale
2. Run test suite to validate setup
3. Integrate ProcessMonitor into droid_runner.py
4. Test with real droid exec workloads
5. Tune thresholds based on observations

---

**Author**: Droid (Factory AI)
**Date**: 2026-01-04
**Status**: Production Ready
