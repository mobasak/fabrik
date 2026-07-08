# AFTER-EDIT: none
"""Phase B wiring tests: the vendored twins are byte-identical, every host `claude` call
site routes through claude_rotate.run_claude (not a bare subprocess.run), the keepalive
shim writes the right content token for each outcome, and the cron template calls the shim."""

import os
import pathlib
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]  # /opt/fabrik
SYS_TWIN = ROOT / "scripts/sysadmin/claude_rotate.py"
ARO_TWIN = ROOT / "scripts/aro-wake/claude_rotate.py"
BOT = ROOT / "scripts/sysadmin/bot.py"
ARO_MAIN = ROOT / "scripts/aro-wake/main.py"
SHIM = ROOT / "scripts/sysadmin/claude-keepalive-rotate.sh"
CRON = ROOT / "scripts/bootstrap/templates/sysadmin-cron.template"


def _func_body(src: str, name: str) -> str:
    """Return the source of the top-level `def name(`/`async def name(` function body, so
    assertions target the exact call site. Matches the name exactly (the trailing `(` stops
    `def _run_claude_v2` binding to `_run_claude`), skips a possibly multi-line signature,
    and ends the body at the first dedent to column 0 (so trailing comments / the next
    function are never folded in)."""
    lines = src.splitlines()
    start = next(
        i
        for i, ln in enumerate(lines)
        if ln.startswith((f"def {name}(", f"async def {name}("))
    )
    # Skip the signature (possibly multi-line) up to and including the line that ends in ':'.
    sig_end = start
    while sig_end < len(lines) and not lines[sig_end].rstrip().endswith(":"):
        sig_end += 1
    body = []
    for ln in lines[sig_end + 1 :]:
        if ln.strip() == "":
            body.append(ln)
            continue
        if not ln[:1].isspace():  # dedent to column 0 → end of the function body
            break
        body.append(ln)
    return "\n".join(body)


def test_twins_are_byte_identical():
    assert SYS_TWIN.read_bytes() == ARO_TWIN.read_bytes(), "vendored twins must be byte-identical"


def test_bot_run_claude_routes_through_rotation_not_bare_subprocess():
    src = BOT.read_text()
    assert "import claude_rotate" in src
    body = _func_body(src, "_run_claude")
    assert "claude_rotate.run_claude(" in body, "bot._run_claude must call the rotation wrapper"
    assert "subprocess.run(" not in body, (
        "the claude call must go through the wrapper, not bare subprocess"
    )


def test_aro_wake_run_claude_routes_through_rotation_not_bare_subprocess():
    src = ARO_MAIN.read_text()
    assert "import claude_rotate" in src
    body = _func_body(src, "_run_claude")
    assert "claude_rotate.run_claude(" in body, (
        "aro-wake._run_claude must call the rotation wrapper"
    )
    assert "subprocess.run(" not in body, (
        "the claude call must go through the wrapper, not bare subprocess"
    )


def test_cron_template_uses_shim_not_bare_claude():
    src = CRON.read_text()
    assert "claude-keepalive-rotate.sh" in src, "cron keepalive must call the shim"
    assert '/usr/bin/claude -p "ping" > /var/log/claude-keepalive.log' not in src, (
        "bare ping replaced"
    )


def test_keepalive_shim_syntax_valid():
    r = subprocess.run(["bash", "-n", str(SHIM)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# --- shim behaviour: run the REAL shim with a fake `claude` binary + empty HOME (no
#     manager-accounts → no rotation), assert the content token per outcome ------------


def _run_shim(tmp_path, fake_output: str, fake_rc: int) -> str:
    fakebin = tmp_path / "fakeclaude"
    fakebin.write_text(
        f"#!/usr/bin/env bash\nprintf '%s' {shlex.quote(fake_output)}\nexit {fake_rc}\n"
    )
    fakebin.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()  # no ~/.claude/manager-accounts → claude_rotate finds <2 accounts → no rotation
    log = tmp_path / "keepalive.log"
    env = {
        **os.environ,
        "HOME": str(home),
        "CLAUDE_BIN": str(fakebin),
        "CLAUDE_KEEPALIVE_LOG": str(log),
        "CLAUDE_ROTATE_PYTHON": "python3",
    }
    subprocess.run(["bash", str(SHIM)], env=env, capture_output=True, text=True)
    return log.read_text().strip()


def test_shim_ok_on_healthy_ping(tmp_path):
    assert _run_shim(tmp_path, '{"result":"pong"}', 0).startswith("KEEPALIVE_OK")


def test_shim_fail_on_401(tmp_path):
    assert _run_shim(tmp_path, "401 Invalid authentication credentials", 1).startswith(
        "KEEPALIVE_FAIL:401_auth"
    )


def test_shim_fail_on_usage_limit(tmp_path):
    assert _run_shim(tmp_path, "You've hit your session limit · resets 3pm", 1).startswith(
        "KEEPALIVE_FAIL:usage_limit"
    )


def test_shim_ok_on_benign_401_substring(tmp_path):
    # RC=0, a "401" substring but no auth wording → must be OK, not a spurious FAIL:unknown
    token = _run_shim(tmp_path, "I checked port 401 and it is closed.", 0)
    assert token.startswith("KEEPALIVE_OK"), f"benign 401 substring must not FAIL: {token!r}"


def test_shim_fail_on_nonzero_exit_without_markers(tmp_path):
    token = _run_shim(tmp_path, "some transient error", 3)
    assert token.startswith("KEEPALIVE_FAIL:exit_3"), token


def test_shim_fail_on_middot_limit_render_rc0(tmp_path):
    # branch-5-only usage-limit render ("limit · resets") with RC=0 — the rotation core rotates
    # on it, so the shim must NOT report OK (regex-parity regression guard vs the 4-branch bug)
    token = _run_shim(tmp_path, "You've reached your limit · resets 3pm", 0)
    assert token.startswith("KEEPALIVE_FAIL:usage_limit"), f"middot render must FAIL, got {token!r}"
