"""The saas chat limiter's Lua script, run against a real throwaway redis-server (W-ab242b11 slice 2).

The emitted ``server/src/<pkg>/chat.py`` checks every rate bucket before it increments any, in one
``EVAL`` (spec § Chosen approach, Limits). An in-process fake cannot prove that, and
``.windsurf/rules/core/45-testing-strategy.md:176-177`` bans one for a backing service, so this file
starts a real ``redis-server`` with TCP off (``--port 0``), a unix socket in a short temp dir, and no
persistence, and kills it in teardown (D-1013). The script text is read from a fresh scaffold by AST,
never imported, so the hub needs none of the emitted backend's dependencies.

Calling convention: ``KEYS`` are the bucket keys; ``ARGV`` is ``limit, window_ms`` per key, in key
order. The reply is ``[0, 0]`` when every bucket passed and was incremented, else
``[<1-based index of the refusing bucket>, <its TTL in ms>]``.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import redis

import fabrik.scaffold as scaffold

WINDOW_MS = 60_000


def _rate_lua(project: Path) -> str:
    """The ``RATE_LUA`` string constant of the emitted chat module, read by AST."""
    chat = next(project.glob("server/src/*/chat.py"))
    for node in ast.parse(chat.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "RATE_LUA" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"no RATE_LUA constant in {chat}")


@pytest.fixture(scope="module")
def lua(tmp_path_factory: pytest.TempPathFactory) -> str:
    if not (scaffold.FABRIK_LIB_DIR / "app-audit-log").is_dir():
        pytest.skip("fabrik-lib/app-audit-log is not beside FABRIK_ROOT; the saas backend scaffold needs it")
    base = tmp_path_factory.mktemp("limiter")
    scaffold.create_project(
        name="p-chat", description="d", base=base, project_type="saas-skeleton", generate_spec=False
    )
    return _rate_lua(base / "p-chat")


@pytest.fixture
def client() -> redis.Redis:
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is not installed on this box; the limiter is proven only on a real server")
    workdir = tempfile.mkdtemp(prefix="rl", dir="/tmp")  # short, so the socket path stays under 108 bytes
    sock = f"{workdir}/redis.sock"
    proc = subprocess.Popen(
        [binary, "--port", "0", "--unixsocket", sock, "--unixsocketperm", "700",
         "--save", "", "--appendonly", "no", "--dir", workdir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        conn = redis.Redis(unix_socket_path=sock)
        deadline = time.monotonic() + 10
        while True:
            try:
                conn.ping()
                break
            except (redis.ConnectionError, FileNotFoundError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        yield conn
        conn.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(workdir, ignore_errors=True)


def _call(client: redis.Redis, lua: str, buckets: list[tuple[str, int]]) -> list[int]:
    keys = [key for key, _ in buckets]
    args: list[int] = []
    for _, limit in buckets:
        args += [limit, WINDOW_MS]
    return [int(x) for x in client.eval(lua, len(keys), *keys, *args)]


def test_a_request_under_every_limit_increments_every_bucket(client, lua):
    assert _call(client, lua, [("a", 5), ("b", 5)]) == [0, 0]
    assert client.get("a") == b"1" and client.get("b") == b"1"


def test_a_refused_request_spends_no_other_bucket(client, lua):
    assert _call(client, lua, [("a", 5), ("b", 1)]) == [0, 0]
    index, _ = _call(client, lua, [("a", 5), ("b", 1)])
    assert index == 2  # the second bucket refused
    assert client.get("a") == b"1", "a refused request must not have spent the first bucket"
    assert client.get("b") == b"1"


def test_the_first_increment_sets_the_window(client, lua):
    _call(client, lua, [("a", 5)])
    assert 0 < client.pttl("a") <= WINDOW_MS


def test_a_refusal_returns_its_bucket_and_a_ttl_of_at_least_one_second(client, lua):
    _call(client, lua, [("a", 1)])
    index, ttl_ms = _call(client, lua, [("a", 1)])
    assert index == 1
    assert 1000 <= ttl_ms <= WINDOW_MS


@pytest.mark.parametrize("stored", ["5", "7"])  # at, and above, the limit
def test_a_key_at_or_above_its_limit_without_a_ttl_gets_the_full_window_back(client, lua, stored):
    client.set("a", stored)  # a manual write or a restore: no TTL
    assert client.pttl("a") == -1
    index, ttl_ms = _call(client, lua, [("a", 5)])
    assert index == 1
    assert WINDOW_MS - 1000 <= ttl_ms <= WINDOW_MS, "the returned TTL is the re-armed one, the full window"
    assert client.pttl("a") > 0


def test_a_key_below_its_limit_without_a_ttl_gets_one_on_increment(client, lua):
    client.set("a", "1")
    assert _call(client, lua, [("a", 5)]) == [0, 0]
    assert client.get("a") == b"2"
    assert client.pttl("a") > 0
