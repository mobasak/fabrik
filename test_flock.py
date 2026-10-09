import sys, os, importlib.util, tempfile, fcntl
spec = importlib.util.spec_from_file_location("cr_pin", os.path.join(os.path.dirname(__file__), "claude_rotate_pin.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)
print("module file:", cr.__file__)

tmp = tempfile.mkdtemp()
import pathlib
cr._fleet_root = lambda: pathlib.Path(tmp)
cr._rotate_state_dir = lambda: pathlib.Path(tmp)

def boom(*a, **k):
    raise OSError(11, "Resource temporarily unavailable")
real_flock = fcntl.flock
fcntl.flock = boom

try:
    result = cr._parked_update("a@ocoron.com", True, repair=False)
    print("RESULT (no exception):", result)
except Exception as e:
    print("RAISED:", type(e).__name__, e)
finally:
    fcntl.flock = real_flock
