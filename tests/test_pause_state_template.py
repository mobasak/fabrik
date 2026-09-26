"""The scaffolded pause_state.py fails OPEN when Redis is down — declared, counted and logged once.

The template ships into every python-api, python-api-gpu, saas-skeleton and file-worker project
(W-e3c97977, mail 01M1GGBFSHSNBRDH961QYZ1XQK). Before this, every Redis error read as "not
paused" with no counter and no log line, so the guard disabled itself invisibly.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest
import structlog

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "scaffold" / "python" / "pause_state.py"
)


class _DownRedis:
    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise ConnectionError("redis-main unreachable")

        return _fail


class _UpRedis:
    def __init__(self):
        self.store = {}

    def keys(self, pattern):
        return [k for k in self.store if k.startswith(pattern.rstrip("*"))]

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0


@pytest.fixture
def load(monkeypatch):
    """Import a fresh copy of the template with `redis.from_url` returning the given client."""

    def _load(client, prometheus=None):
        fake = types.ModuleType("redis")
        fake.calls = []

        def from_url(*a, **k):
            fake.calls.append(k)
            return client

        fake.from_url = from_url
        monkeypatch.setitem(sys.modules, "redis", fake)
        # the real prometheus_client default registry refuses a second metric of the same name
        monkeypatch.setitem(sys.modules, "prometheus_client", prometheus)
        spec = importlib.util.spec_from_file_location("pause_state_under_test", TEMPLATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return _load


def test_redis_down_reads_not_paused_and_counts_every_failure(load):
    ps = load(_DownRedis())

    assert ps.is_globally_paused() is None
    ps.set_global_pause("network", "blip", 30)
    ps.clear_global_pause("network")

    assert ps.degraded_count() == 3


def test_degraded_state_logs_once_on_entry_and_once_on_recovery(load):
    client = _DownRedis()
    ps = load(client)

    with structlog.testing.capture_logs() as logs:
        for _ in range(5):
            ps.is_globally_paused()
        ps.__dict__["_redis"] = lambda: _UpRedis()
        ps.is_globally_paused()
        ps.is_globally_paused()

    events = [e["event"] for e in logs]
    assert events.count("pause_redis_degraded") == 1, events
    assert events.count("pause_redis_recovered") == 1, events
    degraded = next(e for e in logs if e["event"] == "pause_redis_degraded")
    assert degraded["posture"].startswith("fail-open")


def test_missing_redis_package_is_counted_not_silent(load, monkeypatch):
    ps = load(_UpRedis())
    monkeypatch.setitem(sys.modules, "redis", None)  # `import redis` now raises ImportError

    assert ps.is_globally_paused() is None
    assert ps.degraded_count() == 1


def test_redis_up_pauses_and_clears_without_counting(load):
    ps = load(_UpRedis())

    ps.set_global_pause("network", "dns blip", 30)
    assert ps.is_globally_paused() == "network:dns blip"
    ps.clear_global_pause("network")
    assert ps.is_globally_paused() is None
    assert ps.degraded_count() == 0


class _FlakyRedis(_UpRedis):
    """Fails every other command — an intermittently timing-out Redis."""

    def __init__(self):
        super().__init__()
        self.n = 0

    def keys(self, pattern):
        self.n += 1
        if self.n % 2:
            raise TimeoutError("flap")
        return super().keys(pattern)


def _fake_prometheus(raise_on_register=False):
    mod = types.ModuleType("prometheus_client")
    mod.incs = []
    mod.registries = []

    class Counter:
        def __init__(self, name, doc, labels, registry=None):
            if raise_on_register:
                raise ValueError(f"Duplicated timeseries in CollectorRegistry: {name}")
            mod.registries.append(registry)

        def labels(self, **kw):
            mod.incs.append(kw)
            return types.SimpleNamespace(inc=lambda: None)

    mod.Counter = Counter
    return mod


def test_a_flapping_redis_logs_at_most_one_degrade_and_one_recovery(load):
    ps = load(_FlakyRedis())

    with structlog.testing.capture_logs() as logs:
        for _ in range(10):
            ps.is_globally_paused()

    events = [e["event"] for e in logs]
    assert events.count("pause_redis_degraded") == 1, events
    assert events.count("pause_redis_recovered") == 1, events
    assert ps.degraded_count() == 5


@pytest.mark.parametrize("call", ["set", "clear"])
def test_a_successful_write_ends_the_degraded_state(load, call):
    ps = load(_DownRedis())
    ps.is_globally_paused()
    ps.__dict__["_redis"] = lambda: _UpRedis()

    with structlog.testing.capture_logs() as logs:
        if call == "set":
            ps.set_global_pause("network", "blip", 30)
        else:
            ps.clear_global_pause("network")

    assert "pause_redis_recovered" in [e["event"] for e in logs]


def test_the_op_label_names_where_it_failed(load, monkeypatch):
    prom = _fake_prometheus()
    ps = load(_DownRedis(), prometheus=prom)
    ps.is_globally_paused()
    ps.set_global_pause("network", "blip", 30)
    ps.clear_global_pause("network")
    assert prom.incs == [{"op": "read"}, {"op": "set"}, {"op": "clear"}]

    ps = load(_UpRedis(), prometheus=_fake_prometheus())
    monkeypatch.setitem(sys.modules, "redis", None)
    with structlog.testing.capture_logs() as logs:
        ps.is_globally_paused()
    assert logs[0]["op"] == "client"


def test_a_second_registration_is_logged_not_silent(load):
    with structlog.testing.capture_logs() as logs:
        ps = load(_DownRedis(), prometheus=_fake_prometheus(raise_on_register=True))

    assert "pause_redis_metric_unavailable" in [e["event"] for e in logs]
    ps.is_globally_paused()
    assert ps.degraded_count() == 1


def test_the_client_is_built_once_with_timeouts(load):
    ps = load(_UpRedis())
    ps.is_globally_paused()
    ps.is_globally_paused()

    calls = sys.modules["redis"].calls
    assert len(calls) == 1
    assert calls[0]["socket_connect_timeout"] > 0
    assert calls[0]["socket_timeout"] > 0


def test_the_counter_lands_on_the_registry_metrics_serves(tmp_path, monkeypatch):
    """In a scaffolded package pause_state sits beside metrics.py, whose REGISTRY /metrics serves."""
    prom = _fake_prometheus()
    monkeypatch.setitem(sys.modules, "prometheus_client", prom)
    pkg = tmp_path / "svcpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "metrics.py").write_text("REGISTRY = object()\n")
    (pkg / "pause_state.py").write_text(TEMPLATE.read_text())
    monkeypatch.syspath_prepend(str(tmp_path))

    import svcpkg.metrics
    import svcpkg.pause_state  # noqa: F401

    assert prom.registries == [svcpkg.metrics.REGISTRY]


def test_saas_server_requirements_carry_redis_for_pause_state():
    """saas-skeleton ships pause_state.py through _scaffold_fastapi_backend; its redis line was
    added for the jti denylist, and dropping that feature must not drop the pause guard's client."""
    import fabrik.scaffold as scaffold

    assert "redis>=" in scaffold._SAAS_SERVER_REQUIREMENTS


def test_state_transitions_and_their_logs_run_under_the_lock(load):
    """Threads share the degraded state; each transition and its log line must be atomic, and
    the client must be built once, not once per racing thread."""
    ps = load(_DownRedis())
    held = []

    class RecordingLock:
        depth = 0

        def __enter__(self):
            RecordingLock.depth += 1

        def __exit__(self, *exc):
            RecordingLock.depth -= 1

    ps.__dict__["_lock"] = RecordingLock()
    real_warning = ps.logger.warning
    ps.__dict__["logger"] = types.SimpleNamespace(
        warning=lambda event, **kw: (
            held.append((event, RecordingLock.depth)),
            real_warning(event, **kw),
        )
    )
    built_under_lock = []
    fake = sys.modules["redis"]
    real_from_url = fake.from_url
    fake.from_url = lambda *a, **k: (
        built_under_lock.append(RecordingLock.depth),
        real_from_url(*a, **k),
    )[1]

    ps.is_globally_paused()
    ps.__dict__["_client"] = _UpRedis()
    ps.is_globally_paused()

    assert held and all(depth > 0 for _, depth in held), held
    assert built_under_lock == [1], built_under_lock


def test_a_healthy_call_never_takes_the_lock(load):
    """The lock is held across log writes; a healthy call must not wait on a blocked one."""
    ps = load(_UpRedis())
    ps.is_globally_paused()  # builds and caches the client
    entries = []

    class CountingLock:
        def __enter__(self):
            entries.append(1)

        def __exit__(self, *exc):
            return None

    ps.__dict__["_lock"] = CountingLock()
    ps.is_globally_paused()
    ps.set_global_pause("network", "blip", 30)
    ps.clear_global_pause("network")

    assert entries == []


@pytest.mark.parametrize("emitter", ["_scaffold_python_api", "_scaffold_file_worker"])
def test_every_type_that_ships_pause_state_declares_redis(emitter, tmp_path, monkeypatch):
    """python-api and file-worker shipped pause_state.py with no redis requirement, so
    `import redis` failed and the pause never engaged in any of their projects."""
    import subprocess

    import fabrik.scaffold as scaffold

    # the python-api emitter probes for a local dev database with `sudo psql`; never run it here
    monkeypatch.setattr(
        scaffold.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "")
    )
    project_dir = tmp_path / "svc"
    (project_dir / "tests").mkdir(parents=True)  # create_project lays tests/ before the emitter
    getattr(scaffold, emitter)(project_dir, "svc", "a service")

    shipped = list(project_dir.rglob("pause_state.py"))
    requirements = (project_dir / "requirements.txt").read_text().splitlines()
    assert shipped, "the emitter no longer ships pause_state.py; this guard is moot"
    assert any(line.startswith("redis") for line in requirements), requirements
