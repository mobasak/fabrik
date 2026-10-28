"""Coverage for fabrik.monitor — ProcessMonitor diagnosis, using a fake psutil (hermetic)."""

import types
from unittest import mock

import pytest

from fabrik import monitor
from fabrik.monitor import ProcessMetrics, ProcessMonitor, ProcessState


class _Error(Exception):
    pass


class _NoSuchProcessError(_Error):
    pass


class _AccessDeniedError(_Error):
    pass


class FakeProc:
    def __init__(self, cpu=0.0, status="sleeping", io=None, files=None, running=True):
        self._cpu = cpu
        self._status = status
        self._io = io
        self._files = files if files is not None else []
        self._running = running
        self.raise_on = {}

    def cpu_percent(self):
        if "cpu_percent" in self.raise_on:
            raise self.raise_on["cpu_percent"]
        return self._cpu

    def is_running(self):
        return self._running

    def oneshot(self):
        return mock.MagicMock()

    def memory_percent(self):
        return 1.5

    def status(self):
        return self._status

    def num_threads(self):
        return 4

    def io_counters(self):
        return self._io

    def open_files(self):
        if "open_files" in self.raise_on:
            raise self.raise_on["open_files"]
        return self._files


def _io(r, w):
    return types.SimpleNamespace(read_bytes=r, write_bytes=w)


@pytest.fixture
def fake_psutil(monkeypatch):
    ps = types.SimpleNamespace(
        NoSuchProcess=_NoSuchProcessError,
        AccessDenied=_AccessDeniedError,
        Error=_Error,
        STATUS_SLEEPING="sleeping",
        STATUS_WAITING="waiting",
        Process=mock.MagicMock(),
    )
    monkeypatch.setattr(monitor, "psutil", ps)
    return ps


def make(fake_psutil, proc=None, syscall=None, wchan=None, **kw):
    proc = proc or FakeProc(**kw)
    fake_psutil.Process.side_effect = None
    fake_psutil.Process.return_value = proc
    mon = ProcessMonitor(123)
    mon._get_linux_syscall = lambda: syscall
    mon._get_linux_wchan = lambda: wchan
    return mon, proc


def metrics(status="sleeping", syscall=None, wchan=None):
    return ProcessMetrics(0.0, 0.0, 0, 0, 0, 1, status, syscall, wchan)


def test_enum_values_and_str():
    assert ProcessState.STUCK_STDIN.value == "stuck_stdin"
    assert ProcessState("running") is ProcessState.RUNNING
    assert ProcessState.UNKNOWN == "unknown"


def test_metrics_defaults():
    m = ProcessMetrics(1.0, 2.0, 3, 4, 5, 6, "running")
    assert m.syscall is None and m.wchan is None


def test_init_without_psutil_raises(monkeypatch):
    monkeypatch.setattr(monitor, "psutil", None)
    with pytest.raises(ImportError):
        ProcessMonitor(1)


def test_init_no_such_process(fake_psutil):
    fake_psutil.Process.side_effect = _NoSuchProcessError()
    with pytest.raises(ValueError, match="Process 99 not found"):
        ProcessMonitor(99)


def test_init_calibrates_cpu(fake_psutil):
    proc = mock.MagicMock()
    fake_psutil.Process.return_value = proc
    mon = ProcessMonitor(5, history_size=3)
    proc.cpu_percent.assert_called_once()
    assert mon.pid == 5 and mon.history_size == 3 and mon._metrics_history == []


def test_check_not_running_is_unknown(fake_psutil):
    mon, _ = make(fake_psutil, running=False)
    assert mon.check() is ProcessState.UNKNOWN


def test_check_running_on_cpu(fake_psutil):
    mon, _ = make(fake_psutil, cpu=5.0, io=_io(0, 0))
    assert mon.check() is ProcessState.RUNNING


def test_check_cpu_threshold_not_exceeded(fake_psutil):
    mon, _ = make(fake_psutil, cpu=0.1, io=_io(0, 0))
    assert mon.check() is ProcessState.IDLE


def test_check_running_on_read_io_delta(fake_psutil):
    mon, proc = make(fake_psutil, io=_io(100, 100))
    assert mon.check() is ProcessState.IDLE  # first call: no delta baseline
    proc._io = _io(200, 100)
    assert mon.check() is ProcessState.RUNNING
    assert mon._metrics_history[-1].read_bytes_delta == 100


def test_check_running_on_write_io_delta(fake_psutil):
    mon, proc = make(fake_psutil, io=_io(0, 0))
    mon.check()
    proc._io = _io(0, 50)
    assert mon.check() is ProcessState.RUNNING
    assert mon._metrics_history[-1].write_bytes_delta == 50


def test_check_no_io_counters(fake_psutil):
    mon, _ = make(fake_psutil, io=None)
    assert mon.check() is ProcessState.IDLE


def test_check_stuck_stdin(fake_psutil):
    mon, _ = make(fake_psutil, syscall="0 0x0 0x7ff 0x400 0x0 0x0 0x0 0x1 0x2")
    assert mon.check() is ProcessState.STUCK_STDIN


def test_stdin_beats_running(fake_psutil):
    mon, _ = make(fake_psutil, cpu=50.0, syscall="0 0x0 0x1")
    assert mon.check() is ProcessState.STUCK_STDIN


def test_check_sleeping_valid_wchan(fake_psutil):
    mon, _ = make(fake_psutil, wchan="do_select")
    assert mon.check() is ProcessState.SLEEPING


def test_check_idle_unknown_wchan(fake_psutil):
    mon, _ = make(fake_psutil, wchan="something_else")
    assert mon.check() is ProcessState.IDLE


def test_check_open_files_counted(fake_psutil):
    mon, _ = make(fake_psutil, files=[1, 2, 3])
    mon.check()
    assert mon._metrics_history[-1].open_files == 3
    assert mon._metrics_history[-1].threads == 4
    assert mon._metrics_history[-1].memory_percent == 1.5


@pytest.mark.parametrize("exc", [_AccessDeniedError, _Error])
def test_open_files_error_gives_zero(fake_psutil, exc):
    mon, proc = make(fake_psutil)
    proc.raise_on["open_files"] = exc()
    assert mon.check() is ProcessState.IDLE
    assert mon._metrics_history[-1].open_files == 0


def test_check_no_such_process_midway(fake_psutil):
    mon, proc = make(fake_psutil)
    proc.raise_on["cpu_percent"] = _NoSuchProcessError()
    assert mon.check() is ProcessState.UNKNOWN


def test_check_generic_error_logged(fake_psutil, caplog):
    mon, proc = make(fake_psutil)
    proc.raise_on["cpu_percent"] = RuntimeError("boom")
    with caplog.at_level("ERROR"):
        assert mon.check() is ProcessState.UNKNOWN
    assert "Monitor error: boom" in caplog.text


def test_history_is_bounded(fake_psutil):
    mon, _ = make(fake_psutil)
    mon.history_size = 3
    for _ in range(6):
        mon.check()
    assert len(mon._metrics_history) == 3


def test_check_updates_last_check_time(fake_psutil):
    mon, _ = make(fake_psutil)
    mon._last_check_time = 0
    mon.check()
    assert mon._last_check_time > 0


# ---- /proc readers ----


@pytest.mark.parametrize(
    "name,method", [("syscall", "_get_linux_syscall"), ("wchan", "_get_linux_wchan")]
)
def test_proc_read_missing_returns_none(fake_psutil, monkeypatch, name, method):
    proc = FakeProc()
    fake_psutil.Process.return_value = proc
    mon = ProcessMonitor(123)
    monkeypatch.setattr(monitor.os.path, "exists", lambda p: False)
    assert getattr(mon, method)() is None


@pytest.mark.parametrize(
    "name,method", [("syscall", "_get_linux_syscall"), ("wchan", "_get_linux_wchan")]
)
def test_proc_read_returns_stripped(fake_psutil, monkeypatch, name, method):
    fake_psutil.Process.return_value = FakeProc()
    mon = ProcessMonitor(123)
    seen = []
    monkeypatch.setattr(monitor.os.path, "exists", lambda p: seen.append(p) or True)
    with mock.patch("builtins.open", mock.mock_open(read_data="  value\n")):
        assert getattr(mon, method)() == "value"
    assert seen == [f"/proc/123/{name}"]


@pytest.mark.parametrize("exc", [PermissionError, FileNotFoundError])
@pytest.mark.parametrize("method", ["_get_linux_syscall", "_get_linux_wchan"])
def test_proc_read_errors_return_none(fake_psutil, monkeypatch, exc, method):
    fake_psutil.Process.return_value = FakeProc()
    mon = ProcessMonitor(123)
    monkeypatch.setattr(monitor.os.path, "exists", lambda p: True)
    with mock.patch("builtins.open", side_effect=exc()):
        assert getattr(mon, method)() is None


# ---- heuristics ----


@pytest.fixture
def mon(fake_psutil):
    fake_psutil.Process.return_value = FakeProc()
    return ProcessMonitor(1)


@pytest.mark.parametrize(
    "status,syscall,expected",
    [
        ("sleeping", "0 0x0 0x1", True),
        ("waiting", "0 0x0 0x1", True),
        ("running", "0 0x0 0x1", False),
        ("sleeping", None, False),
        ("sleeping", "", False),
        ("sleeping", "   ", False),
        ("sleeping", "1 0x0 0x1", False),  # write, not read
        ("sleeping", "0 0x3 0x1", False),  # fd 3
        ("sleeping", "0 zzz 0x1", False),  # unparsable fd
        ("sleeping", "0 0x00 0x1", True),
    ],
)
def test_is_waiting_for_stdin(mon, status, syscall, expected):
    assert mon._is_waiting_for_stdin(metrics(status, syscall)) is expected


@pytest.mark.xfail(
    strict=True,
    raises=IndexError,
    reason="monitor.py:182 parts[1] IndexError on a one-token syscall string",
)
def test_is_waiting_for_stdin_single_token_syscall(mon):
    assert mon._is_waiting_for_stdin(metrics("sleeping", "running")) is False


@pytest.mark.parametrize(
    "chan",
    [
        "hrtimer_nanosleep",
        "futex_wait_queue_me",
        "ep_poll",
        "do_select",
        "inet_csk_accept",
        "sk_wait_data",
        "poll_schedule_timeout",
        "pipe_wait",
        "x_do_select_y",
    ],
)
def test_valid_sleep_wchans(mon, chan):
    assert mon._is_valid_sleep(metrics(wchan=chan)) is True


@pytest.mark.parametrize("wchan", [None, "", "0", "n_tty_read", "schedule"])
def test_invalid_sleep_wchans(mon, wchan):
    assert mon._is_valid_sleep(metrics(wchan=wchan)) is False


def test_valid_sleep_ignores_syscall(mon):
    assert mon._is_valid_sleep(metrics(syscall="230 0x0")) is False
