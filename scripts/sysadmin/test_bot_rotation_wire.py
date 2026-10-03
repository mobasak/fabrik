# AFTER-EDIT: none
"""Phase B wiring tests: the vendored twins are byte-identical, every host `claude` call
site routes through claude_rotate.run_claude (not a bare subprocess.run), the keepalive
shim writes the right content token for each outcome, and the cron template calls the shim."""

import json
import os
import pathlib
import shlex
import subprocess
import sys

import pytest

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
        i for i, ln in enumerate(lines) if ln.startswith((f"def {name}(", f"async def {name}("))
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


# --- shim behaviour: run the REAL shim against a STUBBED probe, assert the content token per
#     outcome. The shim no longer calls `claude` (the ping was retired 2026-08-30, f532047f8): it
#     classifies the JSON of the free `claude_rotate.py --probe-current --json` probe. The stub is a
#     CLAUDE_ROTATE_PYTHON wrapper that answers that one invocation with a fixture and runs the
#     real python for the shim's classifier, so no test reads the box's live account or the network
#     (the old fake-`claude` harness did both, and four of its ping-era cases were red at HEAD —
#     W-301ad93d). ------------------------------------------------------------------------------


def _run_shim(tmp_path, probe_stdout: str) -> tuple[int, str]:
    fixture = tmp_path / "probe.json"
    fixture.write_text(probe_stdout)
    fakepy = tmp_path / "fakepython"
    fakepy.write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do [ "$a" = "--probe-current" ] && { cat '
        f"{shlex.quote(str(fixture))}; exit 0; }}; done\n"
        f'exec {shlex.quote(sys.executable)} "$@"\n'  # the interpreter running pytest
    )
    fakepy.chmod(0o755)
    log = tmp_path / "keepalive.log"
    env = {**os.environ, "CLAUDE_KEEPALIVE_LOG": str(log), "CLAUDE_ROTATE_PYTHON": str(fakepy)}
    r = subprocess.run(["bash", str(SHIM)], env=env, capture_output=True, text=True, timeout=60)
    return r.returncode, log.read_text().strip()


def _probe(*extra, **row) -> str:
    """The shape `claude_rotate.py --probe-current --json` emits: active "current", one row."""
    return json.dumps({"active": "current", "accounts": [{"slugs": ["current"], **row}, *extra]})


def _ok(tmp_path, probe: str) -> None:
    rc, token = _run_shim(tmp_path, probe)
    assert rc == 0 and token.startswith("KEEPALIVE_OK"), (rc, token)


def _fail(tmp_path, probe: str, reason: str) -> None:
    rc, token = _run_shim(tmp_path, probe)
    assert rc == 1 and token.startswith(f"KEEPALIVE_FAIL:{reason} "), (rc, token)


def test_shim_ok_on_a_live_reading(tmp_path):
    _ok(tmp_path, _probe(five_hour={"utilization": 12.0}, source="live"))


def test_shim_ok_on_a_freshly_cached_reading(tmp_path):
    _ok(tmp_path, _probe(five_hour={"utilization": 12.0}, source="cache", age_s=60))


def test_shim_ok_at_the_freshness_bound(tmp_path):
    _ok(tmp_path, _probe(five_hour={"utilization": 12.0}, source="cache", age_s=7200))


@pytest.mark.parametrize("age", [7201, 9000, None, -5, True], ids=str)
def test_shim_fails_a_stale_or_unproven_cache(tmp_path, age):
    # a dead token stops both the live probe AND the cache refresh, so the cache only ages; an age
    # that is missing, negative or not a number proves nothing
    row = {"five_hour": {"utilization": 12.0}, "source": "cache"}
    if age is not None:
        row["age_s"] = age
    _fail(tmp_path, _probe(**row), "stale_unproven")


@pytest.mark.parametrize(
    "five_hour",
    [None, {}, {"utilization": "12"}, {"utilization": True}, {"utilization": float("nan")}],
    ids=str,
)
def test_shim_fails_a_reading_without_a_numeric_utilization(tmp_path, five_hour):
    # None + "unavailable" is the producer's real dead-token shape (claude_rotate.py _cmd_probe_current)
    _fail(tmp_path, _probe(five_hour=five_hour, source="unavailable"), "probe_incomplete")


def test_shim_reads_the_active_row_not_the_first(tmp_path):
    first = {"slugs": ["other"], "five_hour": {"utilization": 1.0}, "source": "live"}
    probe = json.dumps(
        {"active": "current", "accounts": [first, {"slugs": ["current"], "five_hour": {}}]}
    )
    _fail(tmp_path, probe, "probe_incomplete")


def test_shim_never_reports_another_account_healthy(tmp_path):
    other = {"slugs": ["other"], "five_hour": {"utilization": 1.0}, "source": "live"}
    _fail(tmp_path, json.dumps({"active": "current", "accounts": [other]}), "no_active_account")


def test_shim_fails_an_unparseable_probe(tmp_path):
    _fail(tmp_path, "not json", "probe_error")


def test_shim_fails_when_no_account_answers(tmp_path):
    _fail(tmp_path, json.dumps({"active": "current", "accounts": []}), "no_active_account")
