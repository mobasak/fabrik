import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "sleep"

print(f"Starting in mode: {mode}")
sys.stdout.flush()

if mode == "stdin":
    print("Waiting for input...")
    sys.stdout.flush()
    try:
        data = sys.stdin.read(1)  # Block reading 1 char
        print(f"Got data: {data}")
    except Exception as e:
        print(f"Error: {e}")

elif mode == "sleep":
    print("Sleeping...")
    sys.stdout.flush()
    time.sleep(30)
    print("Done sleeping")

elif mode == "busy":
    print("Busy waiting...")
    sys.stdout.flush()
    end = time.time() + 30
    while time.time() < end:
        pass
    print("Done busy")

elif mode == "network":
    print("Simulating network wait (socket recv)...")
    sys.stdout.flush()
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    s.listen(1)
    # Block on accept
    conn, addr = s.accept()
