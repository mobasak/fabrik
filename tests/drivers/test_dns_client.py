"""Tests for the DNSClient site-provisioner driver — defaults + resolution paths."""

from __future__ import annotations

import contextlib
import json
from unittest.mock import patch

import pytest

from fabrik.drivers.dns import DNSClient


def test_default_container_network_is_fabrik(monkeypatch):
    """Default network is 'fabrik' (not Coolify-era 'coolify').

    Regression: until 2026-06-08, the default was 'coolify', which caused
    `docker inspect site-provisioner --format '{{...coolify...}}'` to return
    an empty value (template parse error: 'no entry for key "IPAddress"') —
    breaking `fabrik vultr destroy --reverse-fleet-add` DNS unwind in a fresh
    operator environment that hadn't set the env override. site-provisioner
    is on the `fabrik` network post-Coolify migration.
    """
    monkeypatch.delenv("SITE_PROVISIONER_CONTAINER_NETWORK", raising=False)
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")
    assert client._container_network == "fabrik"


def test_container_network_env_override_wins(monkeypatch):
    """Operator can override the default network via env var."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER_NETWORK", "some-other-net")
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")
    assert client._container_network == "some-other-net"


def test_container_resolution_uses_chosen_network(monkeypatch):
    """`_resolve_container_url` injects the configured network into the
    docker-inspect template — not a hardcoded value.
    """
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER_NETWORK", "fabrik")
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    captured_cmds: list[list[str]] = []

    class _Result:
        def __init__(self, stdout: str, rc: int = 0) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = rc

    def _fake_run(argv, **kwargs):
        captured_cmds.append(argv)
        joined = " ".join(argv)
        # First subprocess call: container name listing; second: inspect template
        if "docker ps" in joined:
            return _Result("site-provisioner\n")
        if "docker inspect" in joined:
            return _Result("10.0.1.26\n")
        return _Result("")

    with patch("fabrik.drivers.dns.subprocess.run", side_effect=_fake_run):
        client = DNSClient(api_key="test", ssh_host="vps")
        url = client._resolve_container_url()

    assert url == "http://10.0.1.26:8001"
    # The configured network name must appear in the inspect template — not
    # 'coolify' (which was the Coolify-era default that broke post-migration).
    inspect_cmd = " ".join(
        next((cmd for cmd in captured_cmds if "docker inspect" in " ".join(cmd)), [])
    )
    assert "fabrik" in inspect_cmd
    assert "coolify" not in inspect_cmd


# ---------------------------------------------------------------------------
# G4: delete_record idempotency when site-provisioner returns
# `500 Internal Server Error` body for "record not found".
# Live regression from the vps4 drill 2026-06-08: the second destroy against
# already-cleaned vps4 emitted `dns: error: SSH proxy returned non-JSON:
# Internal Server Error` — even though `dig` confirmed the records were
# already gone. The fix swallows the specific shape inside `delete_record`.
# ---------------------------------------------------------------------------


def test_delete_record_swallows_internal_server_error_for_idempotency(monkeypatch):
    """The not-found case (site-provisioner returns 500 plaintext) is success."""
    from fabrik.drivers.dns import ProvisionerHTTPError

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")

    def _boom(*a, **k):
        raise ProvisionerHTTPError("HTTP 500", status=500, body="Internal Server Error")

    with patch.object(client, "_request", side_effect=_boom):
        result = client.delete_record("ocoron.com", "A", "vps4")
    assert result == {"status": "absent"}


def test_delete_record_propagates_unrelated_ssh_errors(monkeypatch):
    """Anything that isn't the 'Internal Server Error + non-JSON' shape
    must still bubble up. A real SSH failure is NOT silently swallowed."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")

    def _real_failure(*a, **k):
        raise RuntimeError("SSH proxy request failed: connection refused")

    with patch.object(client, "_request", side_effect=_real_failure):
        with pytest.raises(RuntimeError, match="connection refused"):
            client.delete_record("ocoron.com", "A", "vps4")


class TestRequestViaSsh:
    """W-6a96f699 (review P2-13): the SSH proxy's failure and timeout text."""

    KEY = "s3cr3tvalue-api-key"

    def _client(self, monkeypatch):
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        return DNSClient(api_key=self.KEY, ssh_host="vps")

    def test_failure_names_host_and_jump_and_leaks_no_secret(self, monkeypatch):
        """The remote shell echoes a broken command line — `-H "X-API-Key: …"` included — and
        `_redact` cannot mask a header; the jump named is the one the call used."""
        import os
        from unittest.mock import MagicMock

        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        client = self._client(monkeypatch)
        stderr = (
            "bash: -c: line 1: syntax error near unexpected token `)'\n"
            f'bash: -c: line 1: `curl -s -X GET -H "X-API-Key: {self.KEY}" )\'\n'
            "DB_PASSWORD=hunter2secret\n"
        )

        def run(argv, **_kw):
            os.environ["FABRIK_SSH_JUMP_VPS"] = "vps3"  # a later read would name vps3
            return MagicMock(returncode=1, stdout="", stderr=stderr)

        with patch("subprocess.run", side_effect=run) as mock_run:
            with pytest.raises(RuntimeError) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert mock_run.call_args[0][0][:5] == ["ssh", "-T", "-o", "ProxyJump=vps2", "vps"]
        msg = str(info.value)
        assert "'vps'" in msg and "via jump 'vps2'" in msg and "rc=1" in msg
        assert self.KEY not in msg and "hunter2secret" not in msg
        assert "syntax error" in msg  # the cause survives the cleaning

    def test_a_timeout_carries_no_command(self, monkeypatch):
        import subprocess

        client = self._client(monkeypatch)
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)

        def run(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout", 30))

        with patch("subprocess.run", side_effect=run):
            with pytest.raises(subprocess.TimeoutExpired) as info:
                client._request_via_ssh("GET", "http://x/y")
        e = info.value
        assert self.KEY not in str(e) and self.KEY not in repr(e)
        assert e.__context__ is None and e.__cause__ is None
        assert e.cmd == ["ssh", "vps", "<command redacted>"]

    def test_a_timeout_names_the_jump_and_keeps_a_fractional_budget(self, monkeypatch):
        """Review C-S3/C-H4: the command-free timeout still names the jump; 0.5 s stays 0.5 s
        (int() made it 0 — an instant timeout)."""
        import subprocess

        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        client = DNSClient(api_key=self.KEY, ssh_host="vps", timeout=0.5)
        seen = {}

        def run(argv, **kw):
            seen["timeout"] = kw["timeout"]
            raise subprocess.TimeoutExpired(argv, kw["timeout"])

        with patch("subprocess.run", side_effect=run):
            with pytest.raises(subprocess.TimeoutExpired) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert seen["timeout"] == 0.5
        assert info.value.cmd == ["ssh", "-o", "ProxyJump=vps2", "vps", "<command redacted>"]

    @pytest.mark.parametrize(
        "url", ["https://h/api/domains/a'; id; echo 'b", "https://h/x$(id)", 'https://h/x"; id']
    )
    def test_the_remote_command_quotes_every_word(self, url, monkeypatch):
        """Review C-H1: a `'` in a domain broke out of the hand-quoted URL and the rest ran on the
        VPS; the remote shell must see the URL as one word."""
        import shlex
        from unittest.mock import MagicMock

        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        client = self._client(monkeypatch)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}\n200", stderr="")
            client._request_via_ssh("POST", url, body={"v": "it's; $(id)"})
        words = shlex.split(mock_run.call_args[0][0][-1])
        assert words[-5] == url and words[-4:-2] == ["-K", "-"]  # the config comes on stdin
        assert words[-2:] == ["-w", "\n%{http_code}"]  # the status rides the reply's last line

    def test_no_secret_or_body_reaches_the_argv_or_a_log(self, monkeypatch, caplog):
        """W-894fdc5f: the key and the body (registrant contact data for register_domain) rode the
        local ssh argv — readable in ps and /proc while the call ran. They go to the remote curl
        as a `-K -` config on stdin; nothing logs either."""
        from unittest.mock import MagicMock

        client = self._client(monkeypatch)
        body = {"contact": {"EmailAddress": "owner@example.com", "Phone": "+1.5550100"}}
        with caplog.at_level("DEBUG"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="{}\n200", stderr="")
                client._request_via_ssh("POST", "https://h/api/domains/register", body=body)
        argv, kw = mock_run.call_args[0][0], mock_run.call_args[1]
        joined = " ".join(argv)
        for secret in (self.KEY, "owner@example.com", "+1.5550100"):
            assert secret not in joined
            assert secret not in caplog.text
        assert argv[:2] == ["ssh", "-T"]  # no pty: a forced RequestTTY would echo the config back
        assert "-n" not in argv and kw.get("stdin") is None
        assert f'header = "X-API-Key: {self.KEY}"' in kw["input"]
        assert "data-raw = " in kw["input"] and "owner@example.com" in kw["input"]

    @pytest.mark.parametrize(
        "key",
        [
            "plainkey123",
            'k"; id; echo "',
            "back\\slash\\nkey",
            "tab\\tend\\",
            "sp ace'and$(x)",
            # a non-ASCII key never reaches here: DNSClient's httpx client refuses it at
            # construction (header values are ASCII); the body carries the non-ASCII case
        ],
    )
    def test_a_real_curl_receives_the_exact_key_and_body(self, key, monkeypatch):
        """The remote command run through `sh -c` with the same stdin, by a real curl, against a
        local server: the key and the body arrive byte-exact, hostile values included."""
        import http.server
        import shutil
        import socket
        import subprocess
        import threading

        curl = shutil.which("curl")
        if curl is None:
            pytest.fail("curl is required: this grader proves the -K config grammar end to end")
        seen = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                seen["key"] = self.headers.get("X-API-Key")
                seen["body"] = self.rfile.read(n)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, *_a):
                pass

        try:

            class V6(http.server.HTTPServer):
                address_family = socket.AF_INET6

            server, host = V6(("::1", 0), Handler), "[::1]"
        except OSError:  # no IPv6 loopback in this environment
            server, host = http.server.HTTPServer(("127.0.0.1", 0), Handler), "127.0.0.1"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        real_run = subprocess.run
        body = {"v": 'it\'s "q" \\ $(id) é'}

        def as_the_remote_shell(argv, **kw):
            return real_run(
                ["sh", "-c", argv[-1]],
                input=kw["input"],
                encoding="utf-8",
                capture_output=True,
                timeout=20,
                check=False,
                env=_isolated_curl_env(),
            )

        try:
            monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
            monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
            client = DNSClient(api_key=key, ssh_host="vps")
            with patch("subprocess.run", side_effect=as_the_remote_shell):
                out = client._request_via_ssh(
                    "POST", f"http://{host}:{server.server_address[1]}/x", body=body
                )
        finally:
            server.shutdown()
        assert out == {"ok": True}
        assert seen["key"].encode("latin-1") == key.encode("utf-8")  # http.server decodes latin-1
        assert seen["body"] == json.dumps(body).encode()

    @pytest.mark.parametrize("bad", ["a\nb", "a\rb", "a\x00b", "trailing\r"])
    def test_a_key_with_a_line_break_or_nul_is_refused_before_ssh(self, bad, monkeypatch):
        """curl truncates a header at a raw newline in a -K config, silently (measured); a CRLF
        .env leaves `\r`. Refused — and the message never carries the value, because the
        orchestrator's DNS fallback logs it."""
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        client = DNSClient(api_key="SECRETPART" + bad, ssh_host="vps")
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ValueError) as info:
                client._request_via_ssh("GET", "https://h/x")
            mock_run.assert_not_called()
        assert "SECRETPART" not in str(info.value) and "SECRETPART" not in repr(info.value)
        assert "X-API-Key" in str(info.value)

    def test_an_empty_stderr_says_so(self, monkeypatch):
        from unittest.mock import MagicMock

        client = self._client(monkeypatch)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=255, stdout="", stderr="")
            with pytest.raises(RuntimeError, match=r"failed \(rc=255\): no stderr$"):
                client._request_via_ssh("GET", "https://h/x")

    def test_a_reply_that_is_not_utf8_is_a_cleaned_error_not_a_decode_crash(self, monkeypatch):
        """Review pass 1: a UnicodeDecodeError from the reply escaped every handler, and its repr
        carries the raw bytes — a reply echoing the key would ship it. The reply is decoded with
        `errors="replace"` and reaches the cleaned non-JSON error. Real `sh`, the client's own
        `subprocess.run` keywords."""
        import subprocess

        client = self._client(monkeypatch)
        real_run = subprocess.run

        def reply_with_a_bad_byte(argv, **kw):
            kw.pop("input", None)
            return real_run(["sh", "-c", f"printf '\\377 {self.KEY}\\n200'"], **kw)

        with patch("subprocess.run", side_effect=reply_with_a_bad_byte):
            with pytest.raises(RuntimeError, match="non-JSON") as info:
                client._request_via_ssh("GET", "https://h/x")
        assert self.KEY not in str(info.value)

    def test_a_non_json_reply_leaks_no_secret(self, monkeypatch):
        """Review C-H3: an error page echoing the request reached the RuntimeError uncleaned."""
        from unittest.mock import MagicMock

        client = self._client(monkeypatch)
        page = f"<html>X-API-Key: {self.KEY} DB_PASSWORD=hunter2secret</html>"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=page + "\n200", stderr="")
            with pytest.raises(RuntimeError) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert self.KEY not in str(info.value) and "hunter2secret" not in str(info.value)
        assert "non-JSON" in str(info.value)

    @pytest.mark.parametrize("status", ["200", "500"], ids=["non-json-branch", "http-error-branch"])
    @pytest.mark.parametrize("offset", [185, 190, 199])
    def test_a_key_straddling_the_cut_leaks_no_prefix(self, offset, status, monkeypatch):
        """Review pass 2 (C2-1): cleaning after the 200-character cut left a straddling key's
        prefix unmasked — in both branches that cut a reply (W-8bb683e6)."""
        from unittest.mock import MagicMock

        client = self._client(monkeypatch)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="x" * offset + self.KEY + "tail\n" + status, stderr=""
            )
            with pytest.raises(RuntimeError) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert self.KEY[:6] not in str(info.value)


def _dead(kind):
    """A `subprocess.run` stand-in whose ssh path dies at the named call."""
    import subprocess
    from unittest.mock import MagicMock

    def run(argv, **kw):
        run.stdins.append(kw.get("stdin"))
        n = len(run.stdins)
        if kind == "timeout-1" or (kind == "timeout-2" and n == 2):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout", 30))
        if kind == "no-ssh":
            raise FileNotFoundError(2, "No such file or directory", "ssh")
        if kind == "not-executable":
            raise PermissionError(13, "Permission denied", "ssh")
        if kind == "signal-1" or (kind == "signal-2" and n == 2):
            return MagicMock(returncode=-9, stdout="", stderr="")
        if kind == "rc255-1" or (kind == "rc255-2" and n == 2):
            return MagicMock(
                returncode=255,
                stdout="",
                stderr="ssh: connect to host vps port 22: Connection refused",
            )
        return MagicMock(returncode=0, stdout="site-provisioner-1\n", stderr="")

    run.stdins = []
    return run


_DEAD_KINDS = [
    "timeout-1",
    "timeout-2",
    "no-ssh",
    "not-executable",
    "rc255-1",
    "rc255-2",
    "signal-1",
    "signal-2",
]


@pytest.mark.parametrize("kind", _DEAD_KINDS)
def test_a_dead_ssh_path_without_an_internal_url_is_raised_not_swallowed(kind, monkeypatch):
    """W-894fdc5f (review C-H5): a dead ssh path is not a container "miss" — swallowed, it sent the
    request on to the public URL, which this box cannot reach, and named the wrong failure."""
    import subprocess

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    run = _dead(kind)
    with patch("subprocess.run", side_effect=run):
        with pytest.raises(RuntimeError, match=r"ssh to 'vps' is dead") as info:
            client._resolve_container_url()
    msg = str(info.value)
    assert "docker" not in msg and info.value.__context__ is None  # no command anywhere
    assert run.stdins and all(s is subprocess.DEVNULL for s in run.stdins)
    assert len(run.stdins) == (2 if kind.endswith("-2") else 1)


@pytest.mark.parametrize("kind", _DEAD_KINDS)
def test_a_dead_ssh_path_with_an_internal_url_falls_back_to_it(kind, monkeypatch, caplog):
    """Review pass 1 (C1): with SITE_PROVISIONER_INTERNAL_URL set, a dead resolve path must not
    take the static internal route away — it is logged and the internal URL is used."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.setenv("SITE_PROVISIONER_INTERNAL_URL", "http://10.0.1.25:8001")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    with caplog.at_level("WARNING"), patch("subprocess.run", side_effect=_dead(kind)):
        assert client._resolve_container_url() is None
    assert "is dead" in caplog.text and "SITE_PROVISIONER_INTERNAL_URL" in caplog.text


@pytest.mark.parametrize("internal_url", [None, "http://10.0.1.25:8001"])
@pytest.mark.parametrize(
    "answers",
    [
        [(1, "", "sudo: a password is required")],  # call 1 fails the ordinary way
        [(0, "", "")],  # no such container
        [(0, "site-provisioner-1\n", ""), (1, "", "Error: No such object")],  # call 2 misses
        [(0, "site-provisioner-1\n", ""), (0, "<no value>\n", "")],  # not on that network
    ],
)
def test_an_ordinary_miss_is_still_a_miss(answers, internal_url, monkeypatch):
    """Review pass 2 (O-N1): only a DEAD path raises; a container that is simply not there still
    returns None, so the caller's fallback runs — whether or not an internal URL is set."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    if internal_url:
        monkeypatch.setenv("SITE_PROVISIONER_INTERNAL_URL", internal_url)
    else:
        monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    replies = [MagicMock(returncode=rc, stdout=out, stderr=err) for rc, out, err in answers]
    with patch("subprocess.run", side_effect=replies):
        assert client._resolve_container_url() is None


def test_a_fractional_budget_and_the_jump_are_read_once(monkeypatch):
    """Review pass 2 (H-N1, O-N3): int() made a 0.5 s budget an instant timeout, now fatal under the
    dead-path rule; and the message must name the jump the argv used, read once."""
    import os
    import subprocess

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
    client = DNSClient(api_key="k", ssh_host="vps", timeout=0.5)
    seen = {}

    def run(argv, **kw):
        seen["timeout"] = kw["timeout"]
        seen["argv"] = argv
        os.environ["FABRIK_SSH_JUMP_VPS"] = "bad value;"  # a second read would refuse it
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    with patch("subprocess.run", side_effect=run):
        with pytest.raises(RuntimeError, match=r"via jump 'vps2' is dead \(no answer in 0.5s\)"):
            client._resolve_container_url()
    assert seen["timeout"] == 0.5
    assert seen["argv"][:3] == ["ssh", "-o", "ProxyJump=vps2"]


# W-9a560686: text the remote side of ssh controls — its stderr, and the container name docker prints — reached the
# resolve and request errors and logs raw: a CR/LF forged a log line, and the miss warnings skipped `_redact`.
_HOSTILE = (
    "Permission denied TOKEN=abc\r\nINJECTED forged log line API_KEY=sk-live-123\x00 café"
    + chr(0x2028)
    + "next"
    + chr(0x85)
    + "nel\n"
)


def _assert_one_line_masked(messages):
    assert messages
    for m in messages:
        assert len(m.splitlines()) == 1, repr(m)  # no CR, LF, U+2028, U+0085 split it
        assert "\\r\\nINJECTED forged log line" in m, (
            m
        )  # escaped, never stripped; masked BEFORE repr,
        # since after it the escaped CR/LF is no longer whitespace and the mask swallows the forged line
        assert "<redacted>" in m and "sk-live-123" not in m, m
        assert "café" in m, m  # printable non-ASCII kept as itself


def _resolve_messages(
    call, rc, stderr, internal, monkeypatch, caplog, stdout1="site-provisioner-1\n"
):
    import logging
    from unittest.mock import MagicMock

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    if internal:
        monkeypatch.setenv("SITE_PROVISIONER_INTERNAL_URL", internal)
    else:
        monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        if len(calls) < call:
            return MagicMock(returncode=0, stdout=stdout1, stderr="")
        return MagicMock(returncode=rc, stdout="", stderr=stderr)

    messages = []
    with (
        caplog.at_level(logging.WARNING, logger="fabrik.drivers.dns"),
        patch("subprocess.run", side_effect=run),
    ):
        if rc == 255 and not internal:
            with pytest.raises(RuntimeError) as info:
                client._resolve_container_url()
            messages.append(str(info.value))
        else:
            assert client._resolve_container_url() is None
    messages += [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    return messages, calls


@pytest.mark.parametrize("internal", [None, "http://10.0.0.5:8000"])
@pytest.mark.parametrize("rc", [255, 1], ids=["dead", "miss"])
@pytest.mark.parametrize("call", [1, 2])
def test_ssh_stderr_reaches_every_resolve_message_on_one_line_masked(
    call, rc, internal, monkeypatch, caplog
):
    messages, calls = _resolve_messages(call, rc, _HOSTILE, internal, monkeypatch, caplog)
    assert len(calls) == call
    _assert_one_line_masked(messages)


@pytest.mark.parametrize("stderr", ["", " \r\n\t"])
@pytest.mark.parametrize("internal", [None, "http://10.0.0.5:8000"])
@pytest.mark.parametrize("rc", [255, 1], ids=["dead", "miss"])
@pytest.mark.parametrize("call", [1, 2])
def test_an_empty_stderr_reads_no_stderr_in_every_resolve_message(
    call, rc, internal, stderr, monkeypatch, caplog
):
    messages, _ = _resolve_messages(call, rc, stderr, internal, monkeypatch, caplog)
    assert messages and all("no stderr" in m and len(m.splitlines()) == 1 for m in messages), (
        messages
    )


@pytest.mark.parametrize(
    "stdout1",
    ["c1\rFORGED LINE x;id\n", "site provisioner\n", "x;id\n", "-rm\n", "a$(id)\n"],
)
def test_a_hostile_container_name_is_a_miss_never_a_command(stdout1, monkeypatch, caplog):
    """The name docker printed went unquoted into the second remote command: `c1\\rFORGED x;id` ran `;id` on the VPS."""
    messages, calls = _resolve_messages(2, 0, "", None, monkeypatch, caplog, stdout1=stdout1)
    assert len(calls) == 1, calls  # the second command never ran
    assert messages and all(len(m.splitlines()) == 1 for m in messages), messages


def test_a_docker_container_name_still_reaches_the_second_command(monkeypatch, caplog):
    messages, calls = _resolve_messages(
        2, 1, "", None, monkeypatch, caplog, stdout1="site-provisioner.1_a-b\n"
    )
    assert len(calls) == 2 and "site-provisioner.1_a-b" in calls[1][-1]


@pytest.mark.parametrize("where", ["failure", "non-json"])
def test_request_errors_carry_remote_text_on_one_line(where, monkeypatch):
    from unittest.mock import MagicMock

    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="the-key-0123456789", ssh_host="vps")
    reply = (
        MagicMock(returncode=255, stdout="", stderr=_HOSTILE)
        if where == "failure"
        else MagicMock(returncode=0, stdout=_HOSTILE, stderr="")
    )
    with patch("subprocess.run", return_value=reply):
        with pytest.raises(RuntimeError) as info:
            client._request_via_ssh("GET", "http://x/y")
    _assert_one_line_masked([str(info.value)])


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.5\nFORGED evil.example",
        "attacker.example/x?",
        "10.0.0.5:9999",
        "10.0.0.5 extra",
        "fe80::1%@attacker.example",  # a scope id ip_address() accepts
        "fd00::5",  # the IPv4-only field never holds one; unbracketed it is no URL
    ],
)
def test_an_inspect_reply_that_is_not_an_ip_is_a_miss_never_a_target(ip, monkeypatch, caplog):
    """The IP docker printed became the request's target host (`attacker.example/x?` sent the key there)."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    replies = [
        MagicMock(returncode=0, stdout="site-provisioner-1\n", stderr=""),
        MagicMock(returncode=0, stdout=ip + "\n", stderr=""),
    ]
    with patch("subprocess.run", side_effect=replies):
        assert client._resolve_container_url() is None
    assert client._resolved_url_cache is None
    warnings = [r.getMessage() for r in caplog.records if "printed no IP address" in r.getMessage()]
    assert len(warnings) == 1 and len(warnings[0].splitlines()) == 1, warnings


@pytest.mark.parametrize(
    "ip, url", [("10.0.0.5", "http://10.0.0.5:8001"), ("172.18.0.12", "http://172.18.0.12:8001")]
)
def test_an_inspect_reply_that_is_an_ip_still_resolves(ip, url, monkeypatch):
    from unittest.mock import MagicMock

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k", ssh_host="vps")
    replies = [
        MagicMock(returncode=0, stdout="site-provisioner-1\n", stderr=""),
        MagicMock(returncode=0, stdout=ip + "\n", stderr=""),
    ]
    with patch("subprocess.run", side_effect=replies):
        assert client._resolve_container_url().startswith(url)


def test_a_whitespace_led_reply_is_not_called_empty(monkeypatch):
    """The 200-character cut ran before the strip, so 205 spaces then text read `empty reply`."""
    from unittest.mock import MagicMock

    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k-0123456789", ssh_host="vps")
    reply = MagicMock(returncode=0, stdout=" " * 205 + "Internal Server Error\n200", stderr="")
    with patch("subprocess.run", return_value=reply):
        with pytest.raises(RuntimeError, match=r"non-JSON: 'Internal Server Error'$"):
            client._request_via_ssh("GET", "http://x/y")


@pytest.mark.parametrize("body", ["Internal Server Error", "\nInternal Server Error\r\n"])
def test_delete_record_reads_the_plaintext_500_as_absent(body, monkeypatch):
    """End to end: the provisioner's 500 + plaintext reply, as curl hands it back with its trailing status
    line, reads as the already-absent shape `delete_record` swallows (the unit test above injects it)."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k-0123456789", ssh_host="vps")
    client._resolved_url_cache = "http://10.0.0.5:8000"
    reply = MagicMock(returncode=0, stdout=body + "\n500", stderr="")
    with patch("subprocess.run", return_value=reply):
        assert client.delete_record("ocoron.com", "A", "vps4") == {"status": "absent"}


# --- W-8bb683e6: an HTTP error through the SSH proxy raises, as the direct path's raise_for_status does ---
@contextlib.contextmanager
def _serve(status: int, body: bytes, *, ctype: str = "application/json"):
    """A local HTTP server answering every request with ``status`` and ``body``; yields its base url and
    closes its socket and thread on exit."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def _answer(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n:
                self.rfile.read(n)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a):
            pass

    for verb in ("GET", "POST", "DELETE"):  # http.server dispatches on `do_<VERB>`
        setattr(Handler, f"do_{verb}", Handler._answer)

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)  # bound and listening on return
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _isolated_curl_env() -> dict[str, str]:
    """The environment every real-curl grader runs in: no proxy variables and no ~/.curlrc, so a box
    with `http_proxy` set still reaches the local server."""
    import os

    env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
    env.update(NO_PROXY="*", no_proxy="*", CURL_HOME="/nonexistent-curl-home")
    return env


def _through_a_real_curl(monkeypatch, *, container: str | None = None):
    """A client, and a subprocess.run stand-in that runs the remote command in a local `sh -c` (a real curl).

    curl must FAIL the run when absent, never skip it: these are the graders of the real reply format.
    It runs in `_isolated_curl_env()`."""
    import shutil
    import subprocess

    if shutil.which("curl") is None:
        pytest.fail("curl is required: these graders drive the real curl reply format")
    real_run = subprocess.run
    env = _isolated_curl_env()

    def as_the_remote_shell(argv, **kw):
        return real_run(
            ["sh", "-c", argv[-1]],
            input=kw["input"],
            encoding="utf-8",
            capture_output=True,
            timeout=20,
            check=False,
            env=env,
        )

    if container:  # read at construction: a delete_record test routes through the container path
        monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", container)
    else:
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    return DNSClient(api_key="s3cr3tvalue-api-key", ssh_host="vps"), as_the_remote_shell


@pytest.mark.parametrize("status", [302, 401, 404, 422, 500, 503])
def test_an_http_error_through_the_proxy_raises_with_its_status(status, monkeypatch):
    """`curl -s` exits 0 on a 4xx/5xx, so the provisioner's error body was returned as the call's success.
    A 3xx is no success either: curl does not follow it (no -L), as raise_for_status refuses it."""
    from fabrik.drivers.dns import ProvisionerHTTPError

    client, shell = _through_a_real_curl(monkeypatch)
    with _serve(status, b'{"success": false, "message": "rejected"}') as base:
        with patch("subprocess.run", side_effect=shell):
            with pytest.raises(ProvisionerHTTPError) as caught:
                client._request_via_ssh("POST", f"{base}/api/x", body={"a": 1})
    assert caught.value.status == status
    assert f"HTTP {status}" in str(caught.value) and "rejected" in str(caught.value)
    assert isinstance(caught.value, RuntimeError), (
        "every caller catching RuntimeError still catches it"
    )


def test_a_2xx_reply_returns_its_json(monkeypatch):
    client, shell = _through_a_real_curl(monkeypatch)
    with _serve(200, b'{"success": true, "id": 7}') as base:
        with patch("subprocess.run", side_effect=shell):
            assert client._request_via_ssh("GET", f"{base}/api/x") == {"success": True, "id": 7}


def test_curls_own_error_reaches_the_exception(monkeypatch):
    """`-S`: with `-s` alone curl prints nothing on its own failure, and the error named no cause."""
    client, shell = _through_a_real_curl(monkeypatch)
    with patch("subprocess.run", side_effect=shell):
        with pytest.raises(RuntimeError, match=r"failed \(rc=3\).*curl: \(3\)"):
            client._request_via_ssh(
                "GET", "http://127.0.0.1:99999/x"
            )  # port out of range: rc 3 at once


@pytest.mark.parametrize("stdout", ["{}", '{"ok": true}\nnot-a-status', "", "200"])
def test_a_reply_without_a_status_raises(stdout, monkeypatch):
    """A reply whose last line is not curl's 3-digit status is never parsed as a body — a bare `200` with no
    newline included (it is a body, not a body plus its status line)."""
    from unittest.mock import MagicMock

    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k-0123456789", ssh_host="vps")
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=stdout, stderr="")):
        with pytest.raises(RuntimeError, match="no HTTP status"):
            client._request_via_ssh("GET", "http://x/y")


def test_a_failed_transfer_is_read_by_its_exit_code_before_its_status(monkeypatch):
    """An aborted transfer still prints its partial body and a status line; the rc check comes first."""
    from unittest.mock import MagicMock

    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    client = DNSClient(api_key="k-0123456789", ssh_host="vps")
    reply = MagicMock(returncode=28, stdout='{"partial": tr\n200', stderr="curl: (28) timed out")
    with patch("subprocess.run", return_value=reply):
        with pytest.raises(RuntimeError, match=r"failed \(rc=28\)"):
            client._request_via_ssh("GET", "http://x/y")


@pytest.mark.parametrize(
    "status,body,absent",
    [
        (500, b"Internal Server Error", True),
        (500, b'{"detail": "boom"}', False),
        (403, b"Internal Server Error", False),
        (404, b'{"detail": "Not Found"}', False),
    ],
    ids=["500-plaintext-absent", "500-other-raises", "403-raises", "404-route-miss-raises"],
)
def test_delete_record_treats_the_500_not_found_as_absent(status, body, absent, monkeypatch):
    """The provisioner answers a delete of an absent record with 500 + plaintext: still absent, keyed on the
    status. Any other HTTP error propagates — a 404 too, which is a missing route, not a missing record."""
    from fabrik.drivers.dns import ProvisionerHTTPError

    client, shell = _through_a_real_curl(monkeypatch, container="site-provisioner")
    with _serve(status, body, ctype="text/plain") as base:
        client._resolved_url_cache = base
        with patch("subprocess.run", side_effect=shell):
            if absent:
                assert client.delete_record("ocoron.com", "A", "vps4") == {"status": "absent"}
            else:
                with pytest.raises(ProvisionerHTTPError):
                    client.delete_record("ocoron.com", "A", "vps4")


@pytest.mark.parametrize(
    "echo,secret",
    [
        (
            "key s3cr3tvalue-api-key rejected",  # no name, no `=`: only the by-value mask hides it
            "s3cr3tvalue-api-key",
        ),  # the client's own key, bare: masked by value
        (
            "x-api-key: f0reign-key-0123456789",
            "f0reign-key-0123456789",
        ),  # a foreign key, by its name
        ("Authorization: Bearer f0reign-token-0123456789", "f0reign-token-0123456789"),
        ('{"x-api-key": "f0reign-key-0123456789"}', "f0reign-key-0123456789"),  # a JSON echo
        (
            "{'Authorization': 'Bearer f0reign-tok-0123456789'}",
            "f0reign-tok-0123456789",
        ),  # a repr echo
        ("authorization=f0reign-tok-0123456789", "f0reign-tok-0123456789"),
    ],
    ids=["own-key-bare", "foreign-key", "bearer-token", "json-echo", "repr-echo", "equals-echo"],
)
def test_an_http_error_body_leaks_no_secret(echo, secret, monkeypatch):
    """An error page that echoes the request — a key or token included — reaches the exception cleaned."""
    from fabrik.drivers.dns import ProvisionerHTTPError

    client, shell = _through_a_real_curl(monkeypatch)
    with _serve(400, f"bad request: {echo}".encode(), ctype="text/plain") as base:
        with patch("subprocess.run", side_effect=shell):
            with pytest.raises(ProvisionerHTTPError) as caught:
                client._request_via_ssh("GET", f"{base}/api/x")
    assert secret not in str(caught.value) and secret not in caught.value.body
    assert caught.value.status == 400 and "<redacted>" in caught.value.body


@pytest.mark.parametrize("copier", ["copy", "deepcopy", "pickle"])
def test_a_provisioner_http_error_survives_a_copy(copier):
    """Keyword-only fields with no default broke copy and pickle (`RuntimeError` rebuilds from args)."""
    import copy
    import pickle

    from fabrik.drivers.dns import ProvisionerHTTPError

    err = ProvisionerHTTPError("returned HTTP 500: 'x'", status=500, body="x")
    clone = {
        "copy": copy.copy,
        "deepcopy": copy.deepcopy,
        "pickle": lambda e: pickle.loads(pickle.dumps(e)),
    }[copier](err)
    assert (clone.status, clone.body, str(clone)) == (500, "x", "returned HTTP 500: 'x'")
