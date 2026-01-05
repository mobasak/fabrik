import os
import subprocess
import sys
import time

import psutil

target_script = os.path.join(os.path.dirname(__file__), "target.py")


def monitor(mode):
    print(f"\n--- Monitoring mode: {mode} ---")
    # Start process with PIPE stdin to simulate non-interactive runner
    p = subprocess.Popen(
        [sys.executable, target_script, mode],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give it a moment to start and enter state
    time.sleep(2)

    try:
        proc = psutil.Process(p.pid)
        print(f"Status: {proc.status()}")
        print(f"CPU: {proc.cpu_percent(interval=0.5)}")

        # Linux specific checks
        try:
            with open(f"/proc/{p.pid}/wchan") as f:
                wchan = f.read().strip()
            print(f"Wchan: {wchan}")
        except FileNotFoundError:
            print("Wchan: N/A")

        try:
            with open(f"/proc/{p.pid}/syscall") as f:
                syscall = f.read().strip()
                syscall_nr = syscall.split()[0]
                print(f"Syscall: {syscall}")
        except FileNotFoundError:
            print("Syscall: N/A")

        # Check file descriptors if possible
        try:
            fds = proc.open_files()
            print(f"Open files: {len(fds)}")
        except Exception as e:
            print(f"FDs error: {e}")

    except psutil.NoSuchProcess:
        print("Process died early")
    finally:
        p.terminate()
        p.wait()


modes = ["stdin", "sleep", "busy", "network"]
for m in modes:
    monitor(m)
