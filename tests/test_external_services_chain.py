#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/daily_refresh.sh .fabrik/liveness-registry.json scripts/gen_dashboard.py
"""The external-services chain is ONE schedule, end to end, with a heartbeat.

Regression guards for the 2026-09-02 finding: gather_envs ran daily while registry_sync and
gen_dashboard sat behind a cron line that was never installed — registry + dashboard frozen
on build day for 46 days, and the liveness audit had no surface to miss. Each test pins one
of the three fixes (wiring · heartbeat · single entry point) plus the `--help`-wrote-a-file
defect in gen_dashboard.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DAILY = REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh"
REGISTRY = REPO / ".fabrik" / "liveness-registry.json"


CHAIN = REPO / "scripts" / "external_services_chain.sh"
HOOK = REPO / "scripts" / "wsl_startup_hook.sh"


def _steps(text: str) -> list[str]:
    return re.findall(r"^\s*_step (\S+)", text, re.M)


def test_the_chain_is_one_script_in_order_with_a_gated_heartbeat():
    text = CHAIN.read_text(encoding="utf-8")
    assert _steps(text) == [
        "gather_envs",
        "classify_services",
        "gather_envs_reconsolidate",
        "registry_sync",
        "gen_dashboard",
    ]
    assert re.search(r"_step classify_services.*--max-per-run \d+", text), (
        "daily classify must be bounded"
    )
    assert re.search(r"_step registry_sync.*--fetch-credits", text)
    # the dashboard (the liveness heartbeat) is written ONLY when every DATA step succeeded
    gated = re.search(r'if \[ "\$core_failed" -eq 0 \]; then\n\s*_step gen_dashboard', text)
    assert gated, "gen_dashboard must be gated on the data steps or a half-dead chain reads LIVE"
    # the paid classify step is NOT a core step: its failure alerts, never ages the heartbeat (G9)
    core = re.search(r'case "\$label" in ([^)]*)\) core_failed=1', text).group(1)
    assert set(core.split("|")) == {"gather_envs", "gather_envs_reconsolidate", "registry_sync"}
    assert (
        'timeout -k 30 "$STEP_TIMEOUT"' in text and "send_alert(" in text
    )  # SIGKILL after SIGTERM (AF13)
    assert "137 = SIGKILL" in text  # the -k path exits 137, and the alert must decode it (AJ9)
    # the paid classify step AND the reconsolidate are skipped after a failed scan (Z9, AC13)
    assert re.search(
        r'if \[ "\$core_failed" -eq 0 \]; then[^\n]*\n\s*_step gather_envs_reconsolidate', text
    )
    assert re.search(
        r'if \[ "\$core_failed" -eq 0 \]; then[^\n]*\n\s*_step classify_services', text
    )


def _shell_code(text: str) -> str:
    """The script minus its comments — full-line and trailing — with a quote-aware scan, so a
    `#` inside a quoted string keeps the rest of the line (AJ8/AM9)."""
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        quote, escaped, dollar, kept = None, False, False, []
        for i, ch in enumerate(ln):
            if escaped:  # `\"` inside a double-quoted string does not close it (AP4)
                escaped = False
            elif (quote == '"' or (quote == "'" and dollar)) and ch == "\\":
                escaped = True  # ANSI-C `$'…\'…'` honours backslashes too (AS6)
            elif quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote, dollar = ch, i > 0 and ln[i - 1] == "$"
            elif ch == "#" and (i == 0 or ln[i - 1].isspace()):
                break
            kept.append(ch)
        out.append("".join(kept))
    return "\n".join(out)


def test_both_entry_points_run_the_same_chain_script_and_inline_no_step():
    # the stripper itself, discriminated both ways (a naive `\s+#.*$` strip fails the first)
    assert "gather_envs.py" in _shell_code('echo "step #1"; python scripts/gather_envs.py')
    assert "chain.sh" not in _shell_code("true  # scripts/external_services_chain.sh")
    assert "chain.sh" not in _shell_code("# scripts/external_services_chain.sh\ntrue")
    assert "gather_envs.py" in _shell_code(r'echo "a \" # b"; python scripts/gather_envs.py')  # AP4
    assert "gather_envs.py" in _shell_code(
        r"echo $'don\'t # care'; python scripts/gather_envs.py"
    )  # AS6
    for entry in (DAILY, HOOK):
        text = entry.read_text(encoding="utf-8")
        # against CODE, not text — a comment naming the script (full-line OR trailing) is not an
        # invocation (AJ8)
        code = _shell_code(text)
        assert "scripts/external_services_chain.sh" in code, f"{entry.name} does not run the chain"
        for step in (
            "gather_envs.py",
            "classify_services.py",
            "registry_sync.py",
            "gen_dashboard.py",
        ):
            assert step not in code, f"{entry.name} inlines {step} — the chain has ONE definition"


def test_no_second_entry_point_advertises_an_uninstalled_cron():
    assert not (REPO / "scripts" / "refresh_service_inventory.py").exists()
    assert "refresh_service_inventory" not in DAILY.read_text(encoding="utf-8")


def test_liveness_registry_declares_the_chain_heartbeat():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = [s for s in reg["surfaces"] if s["id"] == "external-services-chain"]
    assert len(rows) == 1
    s = rows[0]
    assert s["kind"] == "cron" and "daily_refresh.sh" in s["cron_match"]
    assert s["evidence"]["type"] == "log"
    assert s["evidence"]["path"].endswith("external-services-dashboard.html")
    assert 24 <= s["max_age_hours"] <= 48  # a daily run, with slack for a late cron


def _load_gen_dashboard():
    spec = importlib.util.spec_from_file_location(
        "gen_dashboard", REPO / "scripts" / "gen_dashboard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_dashboard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gen_dashboard_help_writes_no_file(tmp_path, monkeypatch):
    gd = _load_gen_dashboard()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gd, "load", lambda: pytest.fail("--help must not touch the registry"))
    with pytest.raises(SystemExit) as exc:
        gd.main(["--help"])
    assert exc.value.code == 0
    assert os.listdir(tmp_path) == [], "gen_dashboard --help wrote a file (the 2026-09-02 defect)"


def test_gen_dashboard_writes_the_named_output(tmp_path, monkeypatch):
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "load", lambda: [])
    monkeypatch.setattr(gd, "render", lambda rows: "<p>ok</p>")
    out = tmp_path / "dash.html"
    assert gd.main([str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "<p>ok</p>"
    assert not (tmp_path / "dash.html.tmp").exists()  # written atomically via tmp + os.replace


def test_gen_dashboard_write_is_atomic(tmp_path, monkeypatch):
    """The page goes to a tmp path and is `os.replace`d into place; a write that dies mid-stream
    leaves the old file untouched (the mtime IS the heartbeat). Discriminating: the pre-fix
    `out.write_text(render(rows))` makes no `os.replace` call and truncates the target (H9)."""
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "load", lambda: [])
    monkeypatch.setattr(gd, "render", lambda rows: "<p>new</p>")
    out = tmp_path / "dash.html"
    out.write_text("old", encoding="utf-8")
    replaced: list[tuple[str, str]] = []
    real_replace = gd.os.replace

    def spy(a, b):
        replaced.append((str(a), str(b)))
        return real_replace(a, b)

    monkeypatch.setattr(gd.os, "replace", spy)
    assert gd.main([str(out)]) == 0
    assert (
        str(out.with_name("dash.html.tmp")),
        str(out),
    ) in replaced  # ours is among the calls (AF11: the spy is process-wide)
    assert out.read_text(encoding="utf-8") == "<p>new</p>"

    class _BoomError(Exception): ...

    orig_write = gd.Path.write_text

    def failing_write(self, *a, **k):
        if self.name.endswith(".tmp"):
            orig_write(self, "half", encoding="utf-8")  # the tmp EXISTS when the write dies (AF4)
            raise _BoomError()
        return orig_write(self, *a, **k)

    monkeypatch.setattr(gd.Path, "write_text", failing_write)
    with pytest.raises(_BoomError):
        gd.main([str(out)])
    assert out.read_text(encoding="utf-8") == "<p>new</p>"  # the old page survived the crash
    assert not out.with_name("dash.html.tmp").exists()  # and no tmp is left behind (AC14)


def test_dashboard_data_cannot_break_out_of_its_script_tag():
    """A registry string carrying `</script>` (provider/url are model-authored upstream) is
    escaped for the inline script and still round-trips as the same JSON value (AM4)."""
    gd = _load_gen_dashboard()
    row = {"provider": "evil</script><script>alert(1)</script>", "url": "https://x/?a=1&b=<2>"}
    out = gd.json_for_script([row])
    assert "</script>" not in out and "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out) == [row]
    # the runtime side: `cpill` builds a class attribute from model-authored cost/status — the
    # token is restricted to [A-Za-z0-9-], never interpolated raw (AP1)
    assert "String(v).replace(/[^A-Za-z0-9]+/g,'-')" in gd.SCRIPT
    assert "'unknown':v.replace('_','-')" not in gd.SCRIPT


def test_cpill_class_token_is_sanitized_when_the_script_runs():
    """The AP1 guard EXECUTED, not string-matched (AQ1): the `cpill` one-liner is lifted from the
    page script and run under node with a hostile cost — the class token it builds is
    `[A-Za-z0-9-]` only. The source-text assertion in the script-tag test stays as the floor."""
    import shutil
    import subprocess

    gd = _load_gen_dashboard()
    m = re.search(r"const cpill=[^\n]*", gd.SCRIPT)
    assert m, "cpill one-liner not found in SCRIPT"
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — only the source-text floor assertion ran")
    js = (
        "const esc=s=>String(s).replace(/[&<>\"']/g,c=>'&#'+c.charCodeAt(0)+';');"
        + m.group(0)
        + "\nprocess.stdout.write(cpill('x\"><svg/onload=alert(1)>'));"
    )
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout
    # the WHOLE output must be one span whose class token is [A-Za-z0-9-] and whose text holds
    # no raw angle bracket — a captured-prefix check stopped at the injected quote and passed
    assert re.fullmatch(r'<span class="pill c-[A-Za-z0-9-]+">[^<>]*</span>', out), out


def test_href_gate_rejects_non_http_schemes_when_the_script_runs():
    """The render-time scheme gate for the provider link, EXECUTED under node (AS5): a
    `javascript:` or `data:` url from a hand-edited catalog never becomes a live link."""
    import shutil
    import subprocess

    gd = _load_gen_dashboard()
    m = re.search(r"const href=[^\n]*", gd.SCRIPT)
    assert m, "href gate not found in SCRIPT"
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH")
    js = (
        m.group(0)
        + "\nprocess.stdout.write(JSON.stringify([href('javascript:alert(1)'),href('data:text/html,x'),href('https://ok.test/a'),href('?'),href(null)]));"
    )
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [None, None, "https://ok.test/a", None, None], out
