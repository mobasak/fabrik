"""`_load_secrets` must not leak bytes of a non-UTF-8 .env into its error."""

from __future__ import annotations

from pathlib import Path

import pytest

import fabrik.orchestrator as orch_mod
from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import ValidationError


def _chain(exc: BaseException):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def test_invalid_utf8_env_error_carries_path_and_offset_only(tmp_path, monkeypatch) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    env_file = project / ".env"
    env_file.write_bytes(b"API_KEY=ab\xff\xfecd\n")

    real_path = Path

    def fake_path(*parts):
        if len(parts) == 1 and str(parts[0]).startswith("/opt/"):
            return project
        return real_path(*parts)

    monkeypatch.setattr(orch_mod, "Path", fake_path)

    orch = DeploymentOrchestrator()
    ctx = DeploymentContext(spec_path=real_path("test.yaml"))
    spec = {"id": "my-app", "name": "my-app", "secrets": {"from_env": ["API_KEY"]}}

    with pytest.raises(ValidationError) as info:
        orch._load_secrets(ctx, spec)

    offset = 10  # b"API_KEY=ab" is 10 bytes; \xff is the first undecodable byte
    for e in _chain(info.value):
        text = f"{e!s} {e!r}"
        for leak in ("\\xff", "xff", "0xff", "ab", "cd", "\xff"):
            if leak == "ab" and str(env_file) in text:
                continue
            assert leak not in text.replace(str(env_file), "")
        assert not isinstance(e, UnicodeDecodeError)
    assert str(env_file) in str(info.value)
    assert str(offset) in str(info.value)
