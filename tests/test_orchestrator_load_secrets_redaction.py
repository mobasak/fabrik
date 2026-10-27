"""`_load_secrets` must not leak bytes of a non-UTF-8 secrets file into its error or its log."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

import fabrik.orchestrator as orch_mod
from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import ValidationError

LEAKS = ("\\xff", "xff", "0xff", "ab", "cd", "\xff")


def _chain(exc: BaseException):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def _project(tmp_path, monkeypatch):
    project = tmp_path / "my-app"
    project.mkdir()
    real_path = Path

    def fake_path(*parts):
        if len(parts) == 1 and str(parts[0]).startswith("/opt/"):
            return project
        return real_path(*parts)

    monkeypatch.setattr(orch_mod, "Path", fake_path)
    return project


def test_invalid_utf8_env_error_carries_path_and_offset_only(tmp_path, monkeypatch) -> None:
    env_file = _project(tmp_path, monkeypatch) / ".env"
    env_file.write_bytes(b"API_KEY=ab\xff\xfecd\n")

    orch = DeploymentOrchestrator()
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    spec = {"id": "my-app", "name": "my-app", "secrets": {"from_env": ["API_KEY"]}}

    with pytest.raises(ValidationError) as info:
        orch._load_secrets(ctx, spec)

    for e in _chain(info.value):
        text = f"{e!s} {e!r}".replace(str(env_file), "")
        for leak in LEAKS:
            assert leak not in text
        assert not isinstance(e, UnicodeDecodeError)
    assert str(env_file) in str(info.value)
    # b"API_KEY=ab" is 10 bytes; \xff is the first undecodable byte
    assert "byte offset 10" in str(info.value)


def test_invalid_utf8_from_file_secret_warns_with_path_and_offset_only(
    tmp_path, monkeypatch, caplog
) -> None:
    _project(tmp_path, monkeypatch)
    secret_file = tmp_path / "token.txt"
    secret_file.write_bytes(b"ab\xff\xfecd\n")

    orch = DeploymentOrchestrator()
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    spec = {"id": "my-app", "secrets": {"from_file": {"MY_TOKEN": str(secret_file)}}}

    with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator"):
        orch._load_secrets(ctx, spec)

    lines = [r.getMessage() for r in caplog.records if "MY_TOKEN" in r.getMessage()]
    assert lines, caplog.text
    for line in lines:
        text = line.replace(str(secret_file), "")
        for leak in LEAKS:
            assert leak not in text
        assert "byte offset 2" in line


_LOCALE_PROBE = """
import sys
from pathlib import Path
import fabrik.orchestrator as orch_mod
from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext
project = Path(sys.argv[1])
real = Path
orch_mod.Path = lambda *p: project if len(p) == 1 and str(p[0]).startswith("/opt/") else real(*p)
ctx = DeploymentContext(spec_path=real("test.yaml"))
secrets = {"from_env": ["API_KEY"], "from_file": {"FILE_KEY": str(project / "token.txt")}}
DeploymentOrchestrator()._load_secrets(ctx, {"id": "x", "secrets": secrets})
print(ctx.secrets["API_KEY"].encode("utf-8").hex(), ctx.secrets.get("FILE_KEY", "").encode().hex())
"""


def test_utf8_secrets_are_read_as_utf8_under_an_ascii_locale(tmp_path) -> None:
    project = tmp_path / "x"
    project.mkdir()
    (project / ".env").write_bytes("API_KEY=şifre\n".encode())
    (project / "token.txt").write_bytes("gizli-ğ\n".encode())
    src = Path(orch_mod.__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LC_", "PYTHON"))}
    env.update(LANG="C", LC_ALL="C", PYTHONCOERCECLOCALE="0", PYTHONPATH=str(src))
    probe = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", _LOCALE_PROBE, str(project)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert probe.returncode == 0, probe.stderr[-800:]
    assert probe.stdout.split() == ["şifre".encode().hex(), "gizli-ğ".encode().hex()]
