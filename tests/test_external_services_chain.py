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
    assert (
        "r.unattributed" in gd.SCRIPT
    )  # an unattributed credential is visible on the row, not merely uncounted (BM9)
    assert (
        "provenance unknown at sync time" in gd.SCRIPT and "model-merged" in gd.SCRIPT
    )  # BR8's floor: the node grader below skips without node, and a skip is never the only guard (AT1/BS6)
    assert (
        '<div class="l">unattributed keys</div>' in gd.render([])
    )  # the degraded case in ONE number — a KEY count, labelled as one beside provider counts (BS16/BW9)
    # the href scheme gate's always-on floor (AS5): the node test skips without node, and a skip
    # must not be the only guard on an injection class (AT1)
    assert "const href=u=>/^https?:\\/\\//i.test(String(u||''))?u:null;" in gd.SCRIPT
    # the shipped escaper's floor: every node grader lifts THIS line, none substitutes its own (AY1)
    esc_line = re.search(r"const esc=[^\n]*", gd.SCRIPT).group(0)
    assert all(
        tok in esc_line
        for tok in ("'&':'&amp;'", "'<':'&lt;'", "'>':'&gt;'", "'\"':'&quot;'", "\"'\":'&#39;'")
    ), esc_line  # `'` too (BB9)


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
    esc_line = re.search(r"const esc=[^\n]*", gd.SCRIPT).group(0)  # the SHIPPED escaper (AY1)
    js = (
        esc_line + "\n" + m.group(0) + "\nprocess.stdout.write(cpill('x\"><svg/onload=alert(1)>'));"
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
    # the CALL SITE, executed: the provider cell for a hostile url is plain text, never a link (AU3)
    line = re.search(r"    const url=href\(r\.url\)\?[^\n]*", gd.SCRIPT)
    assert line, "render() does not route the provider link through href()"
    esc_line = re.search(r"const esc=[^\n]*", gd.SCRIPT).group(0)  # the SHIPPED escaper (AY1)
    cell = re.search(r"out\+='<tr><td class=\"prov\">'\+url\+'</td>'", gd.SCRIPT)
    assert cell, "the provider cell does not render `url` (AY2)"
    js2 = (
        esc_line
        + "\n"
        + m.group(0)
        + "\nconst r={url:'javascript:alert(1)',provider:'p'};"
        + line.group(0).strip()
        + "\nlet out='';"
        + cell.group(0)
        + ";process.stdout.write(out);"
    )
    out2 = subprocess.run([node, "-e", js2], capture_output=True, text=True, check=True).stdout
    assert out2 == '<tr><td class="prov">p</td>' and "<a" not in out2, (
        out2
    )  # the CELL, not the helper (AY2)


def test_unattributed_count_renders_on_the_row_when_the_script_runs():
    """BM9 EXECUTED, not string-matched (BQ3): the keys cell is lifted from the row template and
    run under node — an unattributed count renders its pill next to the key count, zero renders
    no pill. The `r.unattributed` source-text assertion stays as the always-on floor."""
    import shutil
    import subprocess

    gd = _load_gen_dashboard()
    m = re.search(
        r"'<td class=\"num mono\">'\+r\.keys\+\(r\.unattributed\?[^\n]*?'</td>'", gd.SCRIPT
    )
    assert m, "keys cell not found in SCRIPT"
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — only the source-text floor assertion ran")
    js = (
        "const cellFor=r=>" + m.group(0) + ";process.stdout.write(cellFor({keys:2,unattributed:1})"
        "+'|'+cellFor({keys:2,unattributed:0}));"
    )
    with_, without = subprocess.run(
        [node, "-e", js], capture_output=True, text=True, check=True
    ).stdout.split("|")
    assert re.fullmatch(
        r'<td class="num mono">2 <span class="pill c-unknown"[^>]*>1 unattributed</span></td>',
        with_,
    ), with_
    assert without == '<td class="num mono">2</td>', without
    # the tooltip names BOTH causes — the unknown-provenance branch sets the kind too, and the
    # live catalog has 0 merged prefixes, so "model-merged" alone blamed a merge that never happened (BR8)
    assert "provenance unknown" in with_ and "model-merged" in with_, with_


def test_registry_sync_is_gated_on_the_scan_and_the_doc_names_every_kind():
    """A failed scan skips the sync like it skips classify and the reconsolidate: a stale file
    re-pages the same cause and, on a catalog error, flips every credential unattributed (BR4).
    And the operator-facing reference doc names every `kind` the schema carries plus the sync's
    exit 2 — it named 3 of 4 and 0 of 1 (BR5)."""
    text = CHAIN.read_text(encoding="utf-8")
    assert re.search(r'if \[ "\$core_failed" -eq 0 \]; then[^\n]*\n\s*_step registry_sync', text), (
        "registry_sync must be gated on the data steps"
    )
    doc = (REPO / "docs" / "reference" / "external-services-registry.md").read_text(
        encoding="utf-8"
    )
    schema = (REPO / "db" / "services_registry_schema.sql").read_text(encoding="utf-8")
    kind_line = re.search(r"kind\s+TEXT[^\n]*", schema).group(0)
    kinds = set(re.findall(r"'([a-z-]+)'", kind_line))
    assert "provenance unknown" in kind_line, kind_line  # the schema names both causes too (BS9)
    assert kinds == {"credential", "config", "code-host", "credential-unattributed"}, kinds
    for k in kinds:
        assert f"`{k}`" in doc, k
    assert re.search(r"2 = `registry_sync`", doc), "the doc must decode the sync's exit 2"
    assert "2 = registry_sync" in text, "the alert body must decode exit 2 too (BS11)"
    assert "1 = the scan REFUSED the catalog" in text, (
        "exit 1 is every catalog refusal — the page must say so (BX5)"
    )
    for step in ("classify_services.py", "gather_envs.py --apply` again", "registry_sync.py"):
        row = next(ln for ln in doc.splitlines() if ln.startswith("| ") and step in ln)
        assert "skipped after a failed scan" in row, (
            row
        )  # the table says it, not only the prose (BS15)


def test_the_chain_script_executes_its_gating(tmp_path):
    """The chain EXECUTED under bash with a fake interpreter (every sibling test regex-matches the
    script; a bash syntax error or a gate that only LOOKS right passed them all — BU1): a failed
    scan skips classify, the reconsolidate, the sync and the dashboard, alerts once, exits 1; a
    clean run writes the dashboard and exits 0."""
    import os
    import subprocess

    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    (root / "libs").mkdir()
    (root / ".env").write_text("", encoding="utf-8")
    log = tmp_path / "calls.log"
    fake = tmp_path / "fake-python"
    fake.write_text(
        "#!/bin/bash\n"
        f'echo "$*" >> "{log}"\n'
        'case "$*" in\n'
        '  *gather_envs.py*) [ "${FAIL_GATHER:-0}" = 1 ] && exit 1 ;;\n'
        '  *classify_services.py*) [ "${FAIL_CLASSIFY:-0}" = 1 ] && exit 1 ;;\n'
        '  *gen_dashboard.py*) echo ok > "${@: -1}" ;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "FABRIK_ROOT": str(root),
        "VENV_PY": str(fake),
        "STEP_TIMEOUT": "30",
        "LOG_FILE": str(tmp_path / "chain.log"),
    }
    dash = root / "external-services-dashboard.html"
    # 1. a failed scan
    r = subprocess.run(
        ["bash", str(CHAIN)], env={**env, "FAIL_GATHER": "1"}, capture_output=True, text=True
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert not dash.exists(), "a failed scan must not write the heartbeat"
    for skipped in ("classify_services.py", "registry_sync.py", "gen_dashboard.py"):
        assert skipped not in calls, (skipped, calls)
    assert calls.count("send_alert(") == 1, calls  # one cause, one alert (AC13/BR4)
    assert "step gather_envs FAILED (exit 1)" in calls
    # 2. a clean run
    log.write_text("", encoding="utf-8")
    r = subprocess.run(["bash", str(CHAIN)], env=env, capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert dash.read_text(encoding="utf-8").strip() == "ok"
    assert (
        calls.count("gather_envs.py") == 2
        and "registry_sync.py" in calls
        and "send_alert(" not in calls
    )
    assert [re.search(r"scripts/(\S+\.py)", ln).group(1) for ln in calls.splitlines()] == [
        "gather_envs.py",
        "classify_services.py",
        "gather_envs.py",
        "registry_sync.py",
        "gen_dashboard.py",
    ]
    # 3. the PAID step fails: alerted, exit 1 — but the data steps run and the heartbeat is
    # written (G9); a one-word edit to the core_failed case list passed every regex sibling (BX6)
    log.write_text("", encoding="utf-8")
    dash.unlink()
    r = subprocess.run(
        ["bash", str(CHAIN)], env={**env, "FAIL_CLASSIFY": "1"}, capture_output=True, text=True
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert dash.exists() and "registry_sync.py" in calls and calls.count("gather_envs.py") == 2
    assert calls.count("send_alert(") == 1 and "step classify_services FAILED (exit 1)" in calls
