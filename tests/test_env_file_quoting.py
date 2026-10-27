"""The deployed ``.env`` codec speaks compose's dotenv grammar (W-2ae286e2, D-row in DECISIONS).

THE DEFECT: ``_format_env`` never escaped ``$``, so a secret ``a$b`` shipped as ``K=a$b`` and
compose (2.40.3, measured) delivered ``a`` — through ``env_file`` and through ``${K}`` interpolation
alike. The reader disagreed with compose on hand-written lines, and every reader feeds a
read-modify-write, so each disagreement is a value written back corrupted.

Input domain: literal values (secrets, registrar values) and spec ``env:`` templates (``${…}``).
The container tests EXECUTE compose on the local ``python:3.12-slim`` image (never pulled); they
skip when docker or that image is absent, and every other test is pure.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fabrik.env_file import EnvTemplate, format_env_line
from fabrik.orchestrator.deployer_ssh import _format_env, _parse_env

IMAGE = "python:3.12-slim"


def _have_image() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = ["docker", "image", "inspect", IMAGE]
    return subprocess.run(probe, capture_output=True, check=False).returncode == 0


needs_compose = pytest.mark.skipif(not _have_image(), reason=f"docker or local {IMAGE} absent")

LITERALS = {
    "DOLLAR": "a$b",
    "BRACE": "a${X}b",
    "QUOTE_BS": 'x"y\\z',
    "APOS_DOLLAR": "it's $5",
    "JSON": json.dumps({"k": "v$1", "n": "a\\nb"}),
    "NEWLINE": "line1\nline2",
    "TAB": "a\tb",
    "DOLLAR_BS": "p\\$q",
    "TRAIL_SPACE": "pad  ",
}


def _container_env(tmp_path: Path, env_text: str, keys: list[str]) -> dict[str, dict[str, str]]:
    """Run one container with ``env_file: .env`` and, per key, ``I_<key>: ${<key>}``."""
    (tmp_path / ".env").write_text(env_text)
    interp = "".join(f"      I_{k}: ${{{k}}}\n" for k in keys)
    (tmp_path / "compose.yaml").write_text(
        f"services:\n  s:\n    image: {IMAGE}\n    env_file: [.env]\n    environment:\n{interp}"
    )
    code = "import os,json;print(json.dumps(dict(os.environ)))"
    out = subprocess.run(
        ["docker", "compose", "run", "--rm", "-T", "s", "python", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert out.returncode == 0, out.stderr
    seen = json.loads(out.stdout.strip().splitlines()[-1])
    return {k: {"env_file": seen.get(k), "interp": seen.get(f"I_{k}")} for k in keys}


@needs_compose
def test_literal_values_reach_the_container_unchanged(tmp_path: Path) -> None:
    got = _container_env(tmp_path, _format_env(LITERALS), list(LITERALS))
    for key, want in LITERALS.items():
        assert got[key] == {"env_file": want, "interp": want}, (key, _format_env({key: want}))


@needs_compose
def test_spec_templates_still_interpolate(tmp_path: Path) -> None:
    from fabrik.env_file import EnvTemplate

    env = {
        "A": "secret",
        "LOG_LEVEL": EnvTemplate("${LOG_LEVEL:-INFO}"),
        "PW": EnvTemplate("${A}Aa1!"),
        "NAME": EnvTemplate("${NAME:-a b}"),
    }
    text = _format_env(env)
    assert "LOG_LEVEL=${LOG_LEVEL:-INFO}\n" in text, text  # bare, byte-identical to before
    got = _container_env(tmp_path, text, ["LOG_LEVEL", "PW", "NAME"])
    assert got["LOG_LEVEL"]["env_file"] == "INFO"
    assert got["PW"]["env_file"] == "secretAa1!"
    assert got["NAME"]["env_file"] == "a b"


def _types(env: dict[str, str]) -> dict[str, tuple[str, str]]:
    return {k: (type(v).__name__, str(v)) for k, v in env.items()}


def test_format_then_parse_round_trips() -> None:
    from fabrik.env_file import EnvTemplate

    env: dict[str, str] = {**LITERALS, "T1": EnvTemplate("${LOG_LEVEL:-INFO}")}
    env["T2"] = EnvTemplate('${X:-"q" r}')
    once = _parse_env(_format_env(env))
    twice = _parse_env(_format_env(once))
    want = _types(env)
    assert _types(once) == want
    assert _types(twice) == want
    # a template read from a hand-written line is written back byte-identical
    for line in ('K="${X:-\\"q\\"}"', 'K="\\$x ${Y}"', "K=a$$b", "K=${A}${B} # c"):
        parsed = _parse_env(line + "\n")
        assert type(parsed["K"]) is EnvTemplate, line
        assert _format_env(parsed) == line.split(" #")[0] + "\n", line


@pytest.mark.parametrize(
    ("text", "expected", "kind"),
    [
        ("K='a$b'", "a$b", "str"),
        ("K='it\\'s'", "it's", "str"),
        ("K='a\nb'", "a\nb", "str"),
        ('K="a\\$b"', "a$b", "str"),
        ('K="a\\nb\\tc\\rd"', "a\nb\tc\rd", "str"),
        ('K="x\\"y\\\\z"', 'x"y\\z', "str"),
        ('K="a\\xb"', "a\\xb", "str"),
        ('K="a\nb"', "a\nb", "str"),
        ("K=ab #c", "ab", "str"),
        ("K=ab\t#c", "ab\t#c", "str"),
        ("K=a#b", "a#b", "str"),
        ('K="v" junk', "v", "str"),
        ("K=a\rb", "a\rb", "str"),
        ("K=ab\r", "ab", "str"),
        ("export K=v", "v", "str"),
        ("K=a=b", "a=b", "str"),
        ("K=", "", "str"),
        ("K=a$b", "a$b", "EnvTemplate"),
        ('K="a${X}b"', "a${X}b", "EnvTemplate"),
    ],
)
def test_parse_matches_compose_on_hand_written_lines(text: str, expected: str, kind: str) -> None:
    parsed = _parse_env(text + "\nNEXT=1\n")
    assert (type(parsed["K"]).__name__, parsed["K"]) == (kind, expected)
    assert parsed["NEXT"] == "1"


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ('K="abc\nJ=1\n', "unterminated"),
        ("K='abc\n", "unterminated"),
        ('A=1\nK="x\\"\n', "unterminated"),
        ('K="a" "b"\n', "after the closing quote"),
        ("K='a' 'b'\n", "after the closing quote"),
    ],
)
def test_a_line_compose_refuses_fails_closed(text: str, why: str) -> None:
    with pytest.raises(ValueError, match=why):
        _parse_env(text)


def test_a_parse_error_names_key_and_line_never_the_value() -> None:
    secret = "postgres://own:S3cretPassw0rd@h/db"
    with pytest.raises(ValueError) as caught:
        _parse_env(f'A=1\nDATABASE_URL_OWNER="{secret}\n')
    message = str(caught.value)
    assert "DATABASE_URL_OWNER" in message and "line 2" in message
    assert "S3cret" not in message and "postgres" not in message


def _stripping_ssh(root: Path):
    """A fake ssh that runs the reader's own shell text through a local ``sh`` with /opt/my-app
    mapped to *root*, and strips stdout as the real driver does (drivers/ssh.py ``.strip()``)."""

    def fake_ssh(cmd: str, timeout: int = 10) -> str:
        if "echo present" in cmd:
            return "present\nowner"
        local = cmd.removeprefix("sudo ").replace("/opt/my-app/", "./")
        run = subprocess.run(["sh", "-c", local], cwd=root, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        return run.stdout.strip()

    return fake_ssh


def test_env_never_absorbs_the_owner_file(tmp_path: Path) -> None:
    """An unterminated quote in .env must abort the merged read, never swallow .env.owner."""
    from fabrik.orchestrator.deployer_ssh import _read_env_file
    from fabrik.orchestrator.exceptions import DeployError

    ssh = _stripping_ssh(tmp_path)
    (tmp_path / ".env.owner").write_text('DATABASE_URL_OWNER="postgres://o:p@h/db"\n')
    (tmp_path / ".env").write_text('APP="broken\n')
    with pytest.raises(DeployError, match="unterminated"):
        _read_env_file("/opt/my-app", ssh)
    (tmp_path / ".env").write_text("APP=ok\nDATABASE_URL_OWNER=stale\n")
    merged = _read_env_file("/opt/my-app", ssh)
    assert merged == {"APP": "ok", "DATABASE_URL_OWNER": "postgres://o:p@h/db"}


def test_a_broken_owner_file_is_named_as_the_owner_file(tmp_path: Path) -> None:
    from fabrik.orchestrator.deployer_ssh import _read_env_file
    from fabrik.orchestrator.exceptions import DeployError

    (tmp_path / ".env").write_text("APP=ok\n")
    (tmp_path / ".env.owner").write_text('DATABASE_URL_OWNER="postgres://o:s3cret@h/db\n')
    with pytest.raises(DeployError) as caught:
        _read_env_file("/opt/my-app", _stripping_ssh(tmp_path))
    message = str(caught.value)
    assert "/opt/my-app/.env.owner" in message and "DATABASE_URL_OWNER at line 1" in message
    assert "s3cret" not in message


@pytest.mark.parametrize(
    ("env", "owner", "expected"),
    [
        ("", "O=2\n", {"O": "2"}),  # empty .env: the separator is the stripped output's first line
        ("A=1\n", "", {"A": "1"}),  # empty .env.owner: the separator is its last line
        ("A=1", "O=2", {"A": "1", "O": "2"}),  # neither file ends in a newline
        ("\n\n", "\n", {}),  # whitespace only
        # a hand-written .env value holding the separator line: the LAST one splits
        (
            "X='a\n__fabrik_env_owner_follows__\nb'\n",
            "O=2\n",
            {"X": "a\n__fabrik_env_owner_follows__\nb", "O": "2"},
        ),
    ],
)
def test_the_merged_read_survives_the_drivers_strip(
    tmp_path: Path, env: str, owner: str, expected: dict[str, str]
) -> None:
    from fabrik.orchestrator.deployer_ssh import _read_env_file

    (tmp_path / ".env").write_text(env)
    (tmp_path / ".env.owner").write_text(owner)
    assert _read_env_file("/opt/my-app", _stripping_ssh(tmp_path)) == expected


def test_build_env_escapes_secrets_not_spec_templates() -> None:
    from fabrik.env_file import EnvTemplate
    from fabrik.orchestrator.context import DeploymentContext
    from fabrik.orchestrator.deployer_ssh import SSHDeployer

    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    ctx.spec = {"name": "my-app", "env": {"LOG_LEVEL": "${LOG_LEVEL:-INFO}", "PLAIN": "x"}}
    ctx.secrets = {"API_KEY": "a$b"}
    ctx.minted_secrets = {}
    env = SSHDeployer()._build_env(ctx, "my-app", existing=None)
    assert type(env["LOG_LEVEL"]) is EnvTemplate
    assert type(env["API_KEY"]) is str and type(env["PLAIN"]) is str
    text = _format_env(env)
    assert "LOG_LEVEL=${LOG_LEVEL:-INFO}\n" in text
    assert "API_KEY='a$b'\n" in text


def test_hub_secret_readers_return_the_literal_value(tmp_path, monkeypatch) -> None:
    import fabrik.orchestrator as orch
    from fabrik.orchestrator.context import DeploymentContext

    project = tmp_path / "opt" / "demo"
    project.mkdir(parents=True)
    (project / ".env").write_text("TOKEN=\"abc def\"\nKEY='k$1'\nexport PLAIN=p # note\nBARE=b$2\n")
    pem = tmp_path / "pem.txt"
    pem.write_text("line1\nline2\n")
    real_path = orch.Path
    monkeypatch.setattr(
        orch, "Path", lambda p: real_path(str(p).replace("/opt/", f"{tmp_path}/opt/", 1))
    )
    o = orch.DeploymentOrchestrator(
        validator=MagicMock(),
        secrets_manager=MagicMock(),
        deployer=MagicMock(),
        verifier=MagicMock(),
        rollback_manager=MagicMock(),
        infrastructure_provisioner=MagicMock(),
    )
    ctx = DeploymentContext(spec_path=Path("x.yaml"))
    spec = {
        "id": "demo",
        "secrets": {
            "from_env": ["TOKEN", "KEY", "PLAIN", "BARE"],
            "from_file": {"PEM": str(pem)},
        },
    }
    o._load_secrets(ctx, spec)
    assert ctx.secrets == {
        "TOKEN": "abc def",
        "KEY": "k$1",
        "PLAIN": "p",
        "BARE": "b$2",
        "PEM": "line1\nline2",
    }
    # a secret is literal: a bare `$` in the hub file is not carried as a compose template
    assert all(type(v) is str for v in ctx.secrets.values())


def test_a_malformed_hub_env_stops_the_deploy(tmp_path, monkeypatch) -> None:
    """One bad line used to drop every from_env secret behind a warning; it now refuses, naming
    the key and line, never the value."""
    import fabrik.orchestrator as orch
    from fabrik.orchestrator.context import DeploymentContext
    from fabrik.orchestrator.exceptions import ValidationError

    project = tmp_path / "opt" / "demo"
    project.mkdir(parents=True)
    (project / ".env").write_text('GOOD=1\nTOKEN="s3cret-value\n')
    real_path = orch.Path
    monkeypatch.setattr(
        orch, "Path", lambda p: real_path(str(p).replace("/opt/", f"{tmp_path}/opt/", 1))
    )
    o = orch.DeploymentOrchestrator(
        validator=MagicMock(),
        secrets_manager=MagicMock(),
        deployer=MagicMock(),
        verifier=MagicMock(),
        rollback_manager=MagicMock(),
        infrastructure_provisioner=MagicMock(),
    )
    ctx = DeploymentContext(spec_path=Path("x.yaml"))
    spec = {"id": "demo", "secrets": {"from_env": ["GOOD", "TOKEN"]}}
    with pytest.raises(ValidationError, match="TOKEN at line 2") as caught:
        o._load_secrets(ctx, spec)
    assert "s3cret" not in str(caught.value)


def test_env_example_lines_are_quoted() -> None:
    from fabrik.spec_loader import Spec
    from fabrik.template_renderer import TemplateRenderer

    spec = Spec.model_validate(
        {
            "id": "demo-svc",
            "template": "python-api",
            "domain": "demo.vps1.ocoron.com",
            "env": {"MOTD": "hello\nINJECTED=1", "LOG_LEVEL": "${LOG_LEVEL:-INFO}"},
            "resources": {"memory": "512M", "cpu": "0.5"},
        }
    )
    example = TemplateRenderer().render(spec, secrets={}, dry_run=True)[".env.example"]
    assert 'MOTD="hello\\nINJECTED=1"' in example.splitlines()
    assert not any(line.startswith("INJECTED=") for line in example.splitlines())
    assert "LOG_LEVEL=${LOG_LEVEL:-INFO}" in example.splitlines()
    assert _parse_env(example)["MOTD"] == "hello\nINJECTED=1"


# W-8495d72f: runc refuses a container whose environment holds a NUL ("invalid environment variable
# K: contains nul byte"), compose's dotenv has no escape for one, and a lone surrogate crashes the VPS
# writer mid-write — so the codec refuses both before any .env is written, as D-1269 does for compose.
UNWRITABLE = [
    pytest.param("K", "s3cret\x00", id="plain"),
    pytest.param("K", "s3 cret\x00", id="double-quoted"),
    pytest.param("K", "s3cret$\x00", id="single-quoted-dollar"),
    pytest.param("K", EnvTemplate("${X}s3cret\x00"), id="template"),
    pytest.param("K", EnvTemplate("clean", "s3cret\x00"), id="template-source-only"),
    pytest.param("K\x00", "s3cret", id="key"),
    pytest.param("K", "s3cret\udc80", id="lone-surrogate"),
]


@pytest.mark.parametrize(("key", "value"), UNWRITABLE)
def test_an_unwritable_line_is_refused_naming_the_key_never_the_value(key: str, value: str) -> None:
    with pytest.raises(ValueError) as caught:
        format_env_line(key, value)
    message = str(caught.value)
    assert repr(key) in message and "s3cret" not in message
    with pytest.raises(ValueError):
        _format_env({"A": "ok", key: value})


@pytest.mark.parametrize(
    ("merged", "file", "key"),
    [
        ({"DATABASE_URL_OWNER": "postgres://o:p@h/db", "APP": "s3cret\x00"}, ".env", "APP"),
        (
            {"DATABASE_URL_OWNER": "postgres://o:s3cret\x00@h/db", "APP": "ok"},
            ".env.owner",
            "DATABASE_URL_OWNER",
        ),
    ],
)
def test_an_unwritable_value_writes_no_env_file(merged: dict[str, str], file: str, key: str) -> None:
    """Either half holding a NUL stops the writer before its FIRST write, naming that half's file."""
    from fabrik.orchestrator.deployer_ssh import _write_env_files
    from fabrik.orchestrator.exceptions import DeployError

    writes: list[str] = []
    with pytest.raises(DeployError) as caught:
        _write_env_files("/opt/my-app", merged, lambda path, name, content: writes.append(name))
    assert writes == []
    message = str(caught.value)
    assert f"/opt/my-app/{file}:" in message and repr(key) in message and "s3cret" not in message


def test_git_sha_persist_fails_open_on_a_nul_value(monkeypatch, caplog) -> None:
    """The redeploy's GIT_SHA write keeps failing OPEN: logged, nothing written, no traceback."""
    from fabrik.orchestrator import deployer_ssh

    writes: list[str] = []
    monkeypatch.setattr(deployer_ssh, "_read_env_file", lambda path, ssh: {"APP": "s3cret\x00"})
    monkeypatch.setattr(deployer_ssh, "_write_file_to_vps", lambda *a: writes.append(a[1]))
    deployer_ssh._persist_git_sha("my-app", "a" * 40, None)
    assert writes == []
    assert "GIT_SHA not updated for my-app" in caplog.text and "'APP'" in caplog.text
