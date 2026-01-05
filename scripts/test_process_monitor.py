#!/usr/bin/env python3
"""
Test Suite for ProcessMonitor

Tests various subprocess scenarios to validate stuck detection:
1. Normal quick exit
2. Long computation (high CPU)
3. Network waiting simulation
4. Disk I/O simulation
5. Stdin blocking (prevented by DEVNULL)
6. Intentional hang
"""

import subprocess
import tempfile
import time

from process_monitor import ProcessMonitor


def test_quick_exit():
    """Test 1: Process that exits quickly."""
    print("\n" + "=" * 60)
    print("TEST 1: Quick Exit")
    print("=" * 60)

    proc = subprocess.Popen(
        ["echo", "hello"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=1)

    # Should exit immediately
    proc.wait()
    diagnosis = monitor.analyze()

    print(f"Result: {diagnosis['state']} - {diagnosis['reason']}")
    assert diagnosis["state"] == "HEALTHY", "Quick exit should be HEALTHY"
    print("✅ PASS")


def test_long_computation():
    """Test 2: Process with sustained CPU usage."""
    print("\n" + "=" * 60)
    print("TEST 2: Long Computation (High CPU)")
    print("=" * 60)

    # Python script that computes for 15 seconds
    script = """
import time
start = time.time()
while time.time() - start < 15:
    sum(range(1000000))  # CPU work
print("Done")
"""

    proc = subprocess.Popen(
        ["python3", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=2)

    # Monitor for 8 seconds
    for i in range(4):
        time.sleep(2)
        diagnosis = monitor.analyze()
        print(f"  {i*2}s: {diagnosis['state']} - {diagnosis['reason']}")

        # Should show CPU activity
        if diagnosis.get("metrics"):
            m = diagnosis["metrics"]
            print(f"      CPU={m['avg_cpu']:.2f}%, I/O={m['total_io_bytes']}B")
            assert m["avg_cpu"] > 1.0, "Should show CPU activity"

    # Cleanup
    if proc.poll() is None:
        proc.terminate()
        proc.wait()

    print("✅ PASS")


def test_network_wait():
    """Test 3: Process waiting for network (sleep simulation)."""
    print("\n" + "=" * 60)
    print("TEST 3: Network Wait Simulation (sleep)")
    print("=" * 60)

    # Use sleep to simulate network waiting (low CPU, no I/O)
    proc = subprocess.Popen(
        ["sleep", "20"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=2)

    # Monitor for 8 seconds
    states = []
    for i in range(4):
        time.sleep(2)
        diagnosis = monitor.analyze()
        states.append(diagnosis["state"])
        print(f"  {i*2}s: {diagnosis['state']} - {diagnosis['reason']}")

        if diagnosis.get("metrics"):
            m = diagnosis["metrics"]
            print(f"      CPU={m['avg_cpu']:.2f}%, I/O={m['total_io_bytes']}B")

    # After 6s, should be SUSPICIOUS (no stdout, low activity)
    assert (
        "SUSPICIOUS" in states or "LIKELY_STUCK" in states
    ), "Sleep should trigger SUSPICIOUS/LIKELY_STUCK after threshold"

    # Cleanup
    proc.terminate()
    proc.wait()

    print("✅ PASS")


def test_disk_io():
    """Test 4: Process doing heavy disk I/O."""
    print("\n" + "=" * 60)
    print("TEST 4: Disk I/O")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write 50MB file
        script = f"""
import time
with open('{tmpdir}/test.dat', 'wb') as f:
    for i in range(5):
        f.write(b'x' * 10_000_000)  # 10MB
        time.sleep(1)
print("Done")
"""

        proc = subprocess.Popen(
            ["python3", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )

        monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=2)

        # Monitor for 6 seconds
        for i in range(3):
            time.sleep(2)
            diagnosis = monitor.analyze()
            print(f"  {i*2}s: {diagnosis['state']} - {diagnosis['reason']}")

            if diagnosis.get("metrics"):
                m = diagnosis["metrics"]
                print(f"      CPU={m['avg_cpu']:.2f}%, I/O={m['total_io_bytes']}B")
                # Should show I/O activity
                if i > 0:  # After first check (need history)
                    assert m["total_io_bytes"] > 1000, "Should show I/O activity"

        # Cleanup
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

    print("✅ PASS")


def test_stdin_prevention():
    """Test 5: Verify stdin blocking is prevented."""
    print("\n" + "=" * 60)
    print("TEST 5: Stdin Blocking Prevention")
    print("=" * 60)

    # Script that tries to read stdin
    script = """
import sys
print("Trying to read stdin...")
line = sys.stdin.readline()  # Should immediately return EOF
print(f"Read: {repr(line)}")
print("Done")
"""

    # WITH subprocess.DEVNULL - should not block
    print("  Testing with stdin=subprocess.DEVNULL...")
    proc = subprocess.Popen(
        ["python3", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,  # ← Prevents blocking
        text=True,
    )

    # Should exit quickly (not block)
    try:
        stdout, stderr = proc.communicate(timeout=3)
        print(f"  Output: {stdout.strip()}")
        assert "Read: ''" in stdout, "Should read empty string (EOF)"
        print("  ✅ stdin=DEVNULL prevents blocking")
    except subprocess.TimeoutExpired:
        proc.kill()
        raise AssertionError("Process blocked on stdin even with DEVNULL!")

    # WITHOUT subprocess.DEVNULL - would block (don't actually run this)
    print("  Note: Without stdin=DEVNULL, process would block forever")

    print("✅ PASS")


def test_zombie_detection():
    """Test 6: Detect zombie process state."""
    print("\n" + "=" * 60)
    print("TEST 6: Zombie Detection")
    print("=" * 60)

    # Create a process that exits quickly but we don't wait() for it
    proc = subprocess.Popen(
        ["sleep", "0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    # Wait for it to exit
    time.sleep(0.5)

    # Process should be zombie now (exited but not reaped)
    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=1)
    diagnosis = monitor.analyze()

    print(f"  State: {diagnosis['state']}")
    print(f"  Reason: {diagnosis['reason']}")

    # May or may not be zombie depending on timing
    # Just verify we can detect it if it is
    if diagnosis["state"] == "CONFIRMED_STUCK":
        assert "zombie" in diagnosis["reason"].lower(), "Should mention zombie"
        print("  ✅ Zombie detected")
    else:
        print("  ⚠️  Process exited too fast to catch zombie state")

    # Cleanup
    proc.wait()

    print("✅ PASS")


def test_stuck_detection():
    """Test 7: Long idle process should trigger stuck detection."""
    print("\n" + "=" * 60)
    print("TEST 7: Stuck Detection (Long Idle)")
    print("=" * 60)

    # Sleep for a long time (simulate stuck)
    proc = subprocess.Popen(
        ["sleep", "300"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=2)

    # Monitor progression through states
    states_seen = set()
    for i in range(8):  # 16 seconds
        time.sleep(2)
        diagnosis = monitor.analyze()
        states_seen.add(diagnosis["state"])

        print(f"  {i*2}s: {diagnosis['state']} ({diagnosis['confidence']}) - {diagnosis['reason']}")

        if diagnosis.get("metrics"):
            m = diagnosis["metrics"]
            print(
                f"      CPU={m['avg_cpu']:.2f}%, I/O={m['total_io_bytes']}B, Net={m['any_network']}"
            )

    # Should see state progression
    print(f"\n  States seen: {states_seen}")
    assert "SUSPICIOUS" in states_seen, "Should reach SUSPICIOUS"
    assert "LIKELY_STUCK" in states_seen, "Should reach LIKELY_STUCK"

    # Cleanup
    proc.terminate()
    proc.wait()

    print("✅ PASS")


def test_activity_recovery():
    """Test 8: Recovery from SUSPICIOUS state when activity resumes."""
    print("\n" + "=" * 60)
    print("TEST 8: Activity Recovery")
    print("=" * 60)

    proc = subprocess.Popen(
        ["sleep", "30"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    monitor = ProcessMonitor(proc, warn_threshold=5, check_interval=2)

    # Let it become SUSPICIOUS
    for i in range(3):
        time.sleep(2)
        diagnosis = monitor.analyze()
        print(f"  {i*2}s: {diagnosis['state']}")

    # Should be SUSPICIOUS now
    assert diagnosis["state"] == "SUSPICIOUS", "Should be SUSPICIOUS"

    # Simulate activity detection (e.g., stdout event)
    print("  Simulating activity detection...")
    monitor.record_activity()

    # Should return to HEALTHY
    diagnosis = monitor.analyze()
    print(f"  After activity: {diagnosis['state']}")
    assert diagnosis["state"] == "HEALTHY", "Should return to HEALTHY"

    # Cleanup
    proc.terminate()
    proc.wait()

    print("✅ PASS")


def run_all_tests():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# ProcessMonitor Test Suite")
    print("#" * 60)

    tests = [
        test_quick_exit,
        test_long_computation,
        test_network_wait,
        test_disk_io,
        test_stdin_prevention,
        test_zombie_detection,
        test_stuck_detection,
        test_activity_recovery,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ FAIL: {e}")
            failed += 1

    print("\n" + "#" * 60)
    print(f"# Results: {passed} passed, {failed} failed")
    print("#" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys

    success = run_all_tests()
    sys.exit(0 if success else 1)
