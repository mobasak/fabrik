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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DAILY = REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh"
REGISTRY = REPO / ".fabrik" / "liveness-registry.json"


CHAIN = REPO / "scripts" / "external_services_chain.sh"
HOOK = REPO / "scripts" / "wsl_startup_hook.sh"


def _steps(text: str) -> list[str]:
    return re.findall(r"^\s*(?:if )?_step (\S+)", text, re.M)  # the dashboard step is an `if` (CY1)


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
    # the paid step's budget covers its units: 10 per run, up to 7 model calls + web searches each,
    # ALL in parallel — and a kill here LOSES the slice (the cursor moved before the dispatch, AC5) (DM1)
    budget = re.search(r'^CLASSIFY_TIMEOUT="\$\{CLASSIFY_TIMEOUT:-(\d+)\}"', text, re.M)
    # one unit's wall clock is the pool's default (1800 s) + 30 s of outer grace: the budget must
    # EXCEED it, or the kill lands exactly when a hung unit would have returned (DO1)
    wall = re.search(
        r"^\s*wall_clock_s: float = (\d+)",
        (REPO / "libs" / "subagents" / "agent.py").read_text(encoding="utf-8"),
        re.M,
    )
    assert wall and budget and int(budget.group(1)) > int(wall.group(1)) + 30, (budget, wall)
    step_fn = re.search(r"^_step\(\) \{[^\n]*\n(.*?)^\}", text, re.M | re.S).group(
        1
    )  # scoped INSIDE _step (DO2)
    assert re.search(r'\[ "\$label" = classify_services \] && budget="\$CLASSIFY_TIMEOUT"', step_fn)
    assert 'timeout -k 30 "$budget"' in step_fn
    # the dashboard is written ONLY when every DATA step succeeded, and the liveness heartbeat is
    # stamped ONLY after the dashboard step succeeded — by this script, never by the dashboard's
    # own mtime (a manual gen_dashboard.py run refreshed that while the cron slept, CY1)
    gated = re.search(
        r'if \[ "\$core_failed" -eq 0 \]; then\n\s*if _step gen_dashboard [^\n]*; then\n(?:\s*#[^\n]*\n)*'
        r'\s*if mkdir -p [^\n]*&& date -u [^\n]*> "\$HEARTBEAT\.tmp\.\$\$" && mv -fT "\$HEARTBEAT\.tmp\.\$\$" "\$HEARTBEAT"; then',
        text,
    )
    assert gated, "gen_dashboard must be gated on the data steps and the heartbeat stamped after it"
    # one writer, and it is the RENAME: a bare `> "$HEARTBEAT"` truncates before `date` runs, so a
    # failed write left a fresh empty stamp that read LIVE (DA3)
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert code.count('mv -fT "$HEARTBEAT.tmp.$$" "$HEARTBEAT"') == 1, "one atomic writer"
    assert '> "$HEARTBEAT"' not in code, "no direct (truncating) writer"
    # the paid classify step is NOT a core step: its failure alerts, never ages the heartbeat (G9)
    core = re.search(r'case "\$label" in ([^)]*)\) core_failed=1', text).group(1)
    assert set(core.split("|")) == {"gather_envs", "gather_envs_reconsolidate", "registry_sync"}
    assert (
        'timeout -k 30 "$budget"' in text and "send_alert(" in text
    )  # SIGKILL after SIGTERM (AF13)
    assert "137 SIGKILL" in text  # the -k path exits 137, and the alert must decode it (AJ9)
    alert_line = next(
        ln
        for ln in text.splitlines()
        if ln.lstrip().startswith('_alert "external-services chain: step')
    )
    assert "125-127 wrapper" in alert_line, (
        alert_line
    )  # in the BODY the operator reads, not anywhere in the file (EU3/EY7)
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
    # both callers hand the chain THEIR root — the chain's own default merely coincided (EW5)
    for src in (DAILY.read_text(encoding="utf-8"), HOOK.read_text(encoding="utf-8")):
        line = next(
            ln for ln in src.splitlines() if "bash" in ln and "external_services_chain.sh" in ln
        )
        assert re.search(r'FABRIK_ROOT=(?:\\?")?\$FABRIK_ROOT(?:\\?")?', line), (
            line
        )  # unquoted inside the hook's `bash -c "…"` string (EZ2)


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
    # the evidence is the chain's own stamp, never the dashboard file (any manual run refreshes that)
    assert "dashboard" not in s["evidence"]["path"]
    stamp = re.search(
        r'^HEARTBEAT="\$FABRIK_ROOT(/[^"]+)"', CHAIN.read_text(encoding="utf-8"), re.M
    )
    assert stamp and s["evidence"]["path"] == "/opt/fabrik" + stamp.group(1), (
        s["evidence"]["path"],
        stamp and stamp.group(1),
    )
    assert 24 <= s["max_age_hours"] <= 48  # a daily run, with slack for a late cron
    # the auditor audits ITSELF: its installed weekly cron line lacks `cd /opt/fabrik`: its only
    # scheduled attempt failed with nothing watching the watcher (DA1)
    me = [s for s in reg["surfaces"] if s["id"] == "liveness-audit"]
    assert len(me) == 1 and me[0]["cron_match"] == "liveness_audit.py", me
    assert me[0]["evidence"]["type"] == "log_marker"
    la = (REPO / "scripts" / "sysadmin" / "liveness_audit.py").read_text(encoding="utf-8")
    marker = re.search(r'^SELF_MARKER = "([^"]+)"', la, re.M)
    assert marker and me[0]["evidence"]["marker"] == marker.group(1), (me[0]["evidence"], marker)
    assert (
        168 < me[0]["max_age_hours"] < 336
    )  # 168 h weekly + late-cron slack; a MISSED Monday (336 h) must read DEAD
    assert re.search(
        r'PROPOSED_CRON = \(\n\s*"[\d*/, \-]+ cd /opt/fabrik &&(?: exec)? \.venv/bin/python ', la
    ), "the proposed cron line must cd into the repo first — a relative .venv path is what broke it"
    # the doc's fenced "install this verbatim" line and the script's constant are two sources of
    # truth for the one line DA1 is still open on — bound here (DG2)
    proposed = re.search(r'PROPOSED_CRON = \(\n((?:\s*"[^"]*"\n)+)\s*\)', la)
    assert proposed, "PROPOSED_CRON literal"
    constant = "".join(re.findall(r'"([^"]*)"', proposed.group(1)))
    doc = (REPO / "docs" / "workstation" / "liveness.md").read_text(encoding="utf-8")
    fenced = re.search(r"### Proposed cron[^\n]*\n(?:[^`][^\n]*\n|\n)*```cron\n([^\n]+)\n```", doc)
    assert fenced and fenced.group(1).strip() == constant.strip(), (
        fenced and fenced.group(1),
        constant,
    )


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
    leaves the old file untouched (a half-written dashboard is never served). Discriminating: the pre-fix
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
        str(out.with_name(f"dash.html.tmp.{gd.os.getpid()}")),
        str(out),
    ) in replaced  # ours is among the calls (AF11: the spy is process-wide); PID-named (EW4)
    assert out.read_text(encoding="utf-8") == "<p>new</p>"

    class _BoomError(Exception): ...

    orig_write = gd.Path.write_text

    def failing_write(self, *a, **k):
        if ".tmp." in self.name:  # PID-named since EW4
            orig_write(self, "half", encoding="utf-8")  # the tmp EXISTS when the write dies (AF4)
            raise _BoomError()
        return orig_write(self, *a, **k)

    monkeypatch.setattr(gd.Path, "write_text", failing_write)
    with pytest.raises(_BoomError):
        gd.main([str(out)])
    assert out.read_text(encoding="utf-8") == "<p>new</p>"  # the old page survived the crash
    assert not list(out.parent.glob("dash.html.tmp*"))  # and no tmp is left behind (AC14)


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
    index_row = next(
        ln
        for ln in (REPO / "INDEX.md").read_text(encoding="utf-8").splitlines()
        if "services_registry_schema.sql" in ln
    )
    assert all(re.search(rf"(?<![a-z-]){re.escape(k)}(?![a-z-])", index_row) for k in kinds), (
        index_row
    )  # INDEX's schema row names every value (CM7/CP4)
    assert re.search(r"2 = `registry_sync`", doc), "the doc must decode the sync's exit 2"
    assert "125" in doc and "126" in doc and "127" in doc, (
        "the doc must decode the timeout wrapper's own codes (EW3)"
    )
    assert "2 the sync could not read the catalog" in text, (
        "the alert body must decode exit 2 too (BS11)"
    )
    body = re.search(
        r'_alert "external-services chain: step \$label FAILED \(exit \$rc\)" "([^"]*)"', text
    )
    assert body, "the step-failure alert not found"
    body = body.group(1)
    assert "1 gather steps: inputs refused" in body and "1 elsewhere" in body, body
    assert "output path unusable" in body, body  # exit 1 is complete for the scan (CC5/CJ4)
    # Telegram's legacy Markdown fallback rejects an unbalanced `*`/`_`: the body's own text carries
    # none (the label and the log path are the only variables), and it stays within the alerting
    # contract's ~500 chars (CC5)
    fixed = re.sub(r"\$\{?[A-Za-z_]+\}?", "", body)
    assert "*" not in fixed and "_" not in fixed, fixed
    # the heartbeat clause is rendered PER LABEL: the paid step never ages the heartbeat, so its
    # alert must not send the operator hunting a dead chain that is fresh (G9/DA2)
    hb_default = re.search(r'local hb="([^"]*)"', text)
    hb_classify = re.search(r'\[ "\$label" = classify_services \] && hb="([^"]*)"', text)
    assert hb_default and hb_classify and "$hb" in body, "the per-label heartbeat clause"
    assert "DEAD" in hb_default.group(1) and "unaffected" in hb_classify.group(1)
    for clause in (hb_default.group(1), hb_classify.group(1)):
        assert "*" not in clause and "_" not in clause, clause
    # the contract (`libs/alerting`: body up to ~500 chars) is measured on the RENDERED body — every
    # step label and the production log path — not on the template with its variables erased (CD5)
    # every label the SCRIPT declares (never a hand-kept tuple — a renamed step passed it, CM2) ×
    # every log path either ENTRY POINT can pass in (the hook has its own literal, CM2) — and EACH
    # entry point must contribute one (an entry point that stopped setting it passed silently, CP4)
    log_paths = []
    for entry in (DAILY, HOOK):
        text_e = entry.read_text(encoding="utf-8")
        root = re.search(r'^FABRIK_ROOT="([^"]+)"', text_e, re.M)
        assert root, f"{entry.name} must set FABRIK_ROOT"
        tails = re.findall(r'^\s*LOG_FILE="\$FABRIK_ROOT(/[^"]+)"', text_e, re.M)
        assert tails, f"{entry.name} sets no LOG_FILE under FABRIK_ROOT"
        log_paths += [root.group(1) + tail for tail in tails]
    # EVERY alert body the script sends is graded — the heartbeat alert (DA3) sat outside the
    # step-alert regex and could grow past 500 or carry a `_` unnoticed (DC2)
    alerts = re.findall(r'_alert "([^"]*)" "([^"]*)"', text)
    assert len(alerts) == 3 and body in [b for _t, b in alerts], (
        alerts
    )  # the pin: three alerts (step failure, heartbeat, the post-commit credit failure — FD7), all graded
    heartbeat = re.search(r'^HEARTBEAT="\$FABRIK_ROOT(/[^"]+)"', text, re.M).group(1)
    for _t, b in alerts:
        fixed_b = re.sub(r"\$\{?[A-Za-z_]+\}?", "", b)
        assert "*" not in fixed_b and "_" not in fixed_b, fixed_b
    # parity is a property of the MESSAGE Telegram builds — `*{title}*\n{body}` — rendered per
    # label: today it holds because `$label` sits once in the title and once in the body (the two
    # underscores cancel); a copy-edit dropping one passed the template-level check (DE1)
    for label in _steps(text):
        for log_path in log_paths:
            hb = hb_classify.group(1) if label == "classify_services" else hb_default.group(1)

            def _render(tpl: str, label=label, log_path=log_path, hb=hb) -> str:
                return (
                    tpl.replace("$label", label)
                    .replace("$rc", "137")
                    .replace("$LOG_FILE", log_path)
                    .replace("$hb", hb)
                    .replace("$HEARTBEAT", "/opt/fabrik" + heartbeat)
                )

            for t, b in alerts:
                rendered = _render(b)
                assert len(rendered) <= 500, (label, log_path, len(rendered))
                message = f"*{_render(t)}*\n{rendered}"  # libs/alerting/telegram.py
                assert message.count("_") % 2 == 0, (label, log_path, message.count("_"))
                assert message.count("*") == 2, (label, log_path, message)
    # the doc's exit-1 count is COUNTED against its own clauses, never pinned as a phrase (CJ4 fixed
    # the instance; a fifth clause under "one of four" passed a substring pin — CM2)
    sentence = re.search(r"exit 1 — one of (\w+): (.*?); never a degraded", doc, re.S)
    assert sentence, "the failure-visibility sentence"
    words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    # boundaries at paren depth 0 only: `,`, `;` and the word `or` — alternatives WITHIN a cause go
    # in parentheses; a fifth cause joined by a bare `or`/`;` once passed a comma-only split (CP4)
    depth, clauses, buf = 0, [], ""
    flat = re.sub(r"\s+", " ", sentence.group(2))  # a reflow never hides a boundary (CS3)
    i = 0
    while i < len(flat):
        ch = flat[i]
        depth = max(
            depth + (ch == "(") - (ch == ")"), 0
        )  # an unbalanced `)` never kills every later boundary (CS3)
        joiner = re.match(r" (or|and) ", flat[i:])
        if depth == 0 and ch in ",;":
            clauses.append(buf)
            buf = ""
        elif depth == 0 and joiner:
            clauses.append(buf)
            buf = ""
            i += len(joiner.group(0)) - 1
        else:
            buf += ch
        i += 1
    clauses.append(buf)
    assert depth == 0, (
        "unbalanced parens in the failure-visibility sentence",
        flat,
    )  # an unbalanced `(` hid a cause (CU4)
    assert len([c for c in clauses if c.strip()]) == words[sentence.group(1)], (
        sentence.group(1),
        clauses,
    )
    assert "cannot read or write its own output path" in doc, "the doc's step-1 cell (CC5)"
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
        '  *gen_dashboard.py*) [ "${FAIL_DASHBOARD:-0}" = 1 ] && exit 7; echo ok > "${@: -1}" ;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    # a fake `timeout` on PATH logs the budget each step ran under: the classify budget is proven
    # by execution, not by a text pin (DO2)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    budgets = tmp_path / "budgets.log"
    (bin_dir / "timeout").write_text(
        "#!/bin/bash\n"
        f'for a in "$@"; do case "$a" in *.py) echo "$3 $a" >> "{budgets}"; break;; esac; done\n'  # "<budget> <script path>" — the FIRST .py argv word, never a fixed position (DS3); the last argv word had collapsed the two gather runs (DQ2)
        "shift 3\n"
        'exec "$@"\n',
        encoding="utf-8",
    )
    (bin_dir / "timeout").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FABRIK_ROOT": str(root),
        "VENV_PY": str(fake),
        "STEP_TIMEOUT": "30",
        "CLASSIFY_TIMEOUT": "4321",
        "LOG_FILE": str(tmp_path / "chain.log"),
    }
    dash = root / "external-services-dashboard.html"
    stamp = root / ".tmp" / "external-services" / "chain-heartbeat"
    # 1. a failed scan
    r = subprocess.run(
        ["bash", str(CHAIN)], env={**env, "FAIL_GATHER": "1"}, capture_output=True, text=True
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert not dash.exists() and not stamp.exists(), "a failed scan must not write the heartbeat"
    for skipped in ("classify_services.py", "registry_sync.py", "gen_dashboard.py"):
        assert skipped not in calls, (skipped, calls)
    assert calls.count("send_alert(") == 1, calls  # one cause, one alert (AC13/BR4)
    assert "step gather_envs FAILED (exit 1)" in calls and "liveness DEAD" in calls
    # 2. a clean run
    log.write_text("", encoding="utf-8")
    budgets.write_text("", encoding="utf-8")  # the failed scan above logged its own budget
    r = subprocess.run(["bash", str(CHAIN)], env=env, capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert dash.read_text(encoding="utf-8").strip() == "ok"
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp.read_text(encoding="utf-8").strip()
    ), "the heartbeat is stamped by the chain after a clean run"
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
    by_step: dict[str, list[str]] = {}
    for b, script in (ln.split() for ln in budgets.read_text(encoding="utf-8").splitlines()):
        by_step.setdefault(Path(script).name, []).append(b)
    assert by_step["classify_services.py"] == ["4321"], by_step
    assert by_step["gather_envs.py"] == ["30", "30"], by_step  # BOTH gather runs, never collapsed
    assert {b for k, v in by_step.items() if k != "classify_services.py" for b in v} == {"30"}, (
        by_step
    )
    # 3. the PAID step fails: alerted, exit 1 — but the data steps run and the heartbeat is
    # written (G9); a one-word edit to the core_failed case list passed every regex sibling (BX6)
    log.write_text("", encoding="utf-8")
    dash.unlink()
    stamp.unlink()
    r = subprocess.run(
        ["bash", str(CHAIN)], env={**env, "FAIL_CLASSIFY": "1"}, capture_output=True, text=True
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert dash.exists() and stamp.exists() and "registry_sync.py" in calls
    assert calls.count("gather_envs.py") == 2
    assert calls.count("send_alert(") == 1 and "step classify_services FAILED (exit 1)" in calls
    assert "liveness DEAD" not in calls and "heartbeat unaffected" in calls, calls  # DA2
    # 4. the DASHBOARD step fails: exit 1, one alert, no dashboard, no stamp — the gate the stamp
    # sits behind, executed in the failing direction (a regex-only proof, DA3)
    log.write_text("", encoding="utf-8")
    dash.unlink()
    stamp.unlink()
    r = subprocess.run(
        ["bash", str(CHAIN)], env={**env, "FAIL_DASHBOARD": "1"}, capture_output=True, text=True
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1 and not dash.exists() and not stamp.exists(), (r.returncode, calls)
    assert calls.count("send_alert(") == 1 and "step gen_dashboard FAILED (exit 7)" in calls
    # 5. the stamp cannot be written (`.tmp` is a FILE): every step ran, the dashboard stands, the
    # failure is ALERTED and exits 1 — it was the only silent failure in the script (DA3)
    log.write_text("", encoding="utf-8")
    import shutil

    shutil.rmtree(root / ".tmp")
    (root / ".tmp").write_text("", encoding="utf-8")
    r = subprocess.run(["bash", str(CHAIN)], env=env, capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1 and dash.exists() and not stamp.exists(), (r.returncode, calls)
    assert calls.count("send_alert(") == 1 and "heartbeat NOT stamped" in calls, calls
    assert "heartbeat NOT stamped" in r.stdout
    (root / ".tmp").unlink()
    # 6. `date` fails: a bare `> "$HEARTBEAT"` truncated the stamp BEFORE date ran — a fresh EMPTY
    # stamp that read LIVE. The previous stamp must survive untouched, no tmp left behind (DA3)
    stamp.parent.mkdir(parents=True)
    stamp.write_text("2026-08-01T00:00:00Z\n", encoding="utf-8")
    os.utime(stamp, (1_700_000_000, 1_700_000_000))
    bad = tmp_path / "bad-bin"
    bad.mkdir()
    (bad / "date").write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    (bad / "date").chmod(0o755)
    log.write_text("", encoding="utf-8")
    r = subprocess.run(
        ["bash", str(CHAIN)],
        env={**env, "PATH": f"{bad}:{env['PATH']}"},
        capture_output=True,
        text=True,
    )
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1 and "heartbeat NOT stamped" in calls, (r.returncode, calls)
    assert stamp.read_text(encoding="utf-8").strip() == "2026-08-01T00:00:00Z"
    assert int(stamp.stat().st_mtime) == 1_700_000_000, "a failed write must not freshen the stamp"
    assert list(stamp.parent.glob("chain-heartbeat.tmp.*")) == []
    # 7. a DIRECTORY at the stamp path: `mv -f` would move the tmp INSIDE it and the audit would age
    # the directory's own mtime — LIVE forever; `-T` refuses, alerted, exit 1 (DC2)
    log.write_text("", encoding="utf-8")
    stamp.unlink()
    stamp.mkdir()
    r = subprocess.run(["bash", str(CHAIN)], env=env, capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1 and "heartbeat NOT stamped" in calls, (r.returncode, calls)
    assert stamp.is_dir() and list(stamp.iterdir()) == [], list(stamp.iterdir())
    assert list(stamp.parent.glob("chain-heartbeat.tmp.*")) == []


def _tracked_python_files() -> list[Path]:
    """Every tracked `.py` under scripts/ and libs/ — `git ls-files`, so an untracked vendored venv
    (`scripts/kilo-benchmarks/.lcb-venv`, 1712 files) is never swept; outside a git checkout, the
    same walk minus dot-directories (DO2)."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z", "scripts", "libs"],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout.decode(errors="surrogateescape")
        files = [
            REPO / p
            for p in out.split("\0")
            if p.endswith(".py") and "/.archive/" not in f"/{p}" and "/archived/" not in f"/{p}"
        ]  # archives are dead code: a stale literal there must not red the live suite (DQ2)
        if files:
            return files
    except (OSError, subprocess.SubprocessError):
        pass
    return [
        p
        for d in ("scripts", "libs")
        for p in (REPO / d).rglob("*.py")
        if not any(part.startswith(".") for part in p.relative_to(REPO).parts)
    ]


def _web_tools_literals(source: str) -> list[list[str] | None]:
    """Every `web_tools=` keyword in the file: the literal's names, or None when it is not a literal
    (a name, an attribute, a call the walk cannot evaluate). AST, not a regex: a bare `{…}` set, a
    `frozenset(sorted(…))`, a union and a following `system="…"` all defeated the regex (DO2)."""
    import ast

    def names(node: ast.AST) -> list[str] | None:
        if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
            out: list[str] = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.append(elt.value)
                else:
                    inner = names(elt)
                    if inner is None:
                        return None
                    out.extend(inner)
            return out
        if isinstance(node, ast.Call) and node.args:
            return names(node.args[0])  # frozenset(…), set(…), sorted(…)
        if isinstance(node, ast.BinOp):
            left, right = names(node.left), names(node.right)
            return None if left is None or right is None else left + right
        return None

    found: list[list[str] | None] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "web_tools":
                    found.append(names(kw.value))
    return found


def test_every_web_tools_literal_names_real_tools_not_providers():
    """`web_tools=` takes TOOL names (`web_search`, `web_search_brave`, `web_scrape`, `web_crawl`,
    `docs_lookup`); the pool loop advertises only names it knows. The classifier passed the
    PROVIDER names `{"exa", "brave"}`, so its paid "research" units ran with NO web tools — one
    turn of model recall each, 10 of 10 on the first production run, the root of the `argusmedia`
    misfile (DK1). The corpus gate checks the `commands/` markdown plus the assembler, per line;
    this is the same check over every tracked Python caller in scripts/ and libs/ (archives
    excluded), parsed, never pattern-matched (DO2/DQ2)."""
    if str(REPO) not in sys.path:  # unguarded, a duplicate per run (L64-2, FD8)
        sys.path.insert(0, str(REPO))
    from libs.subagents.web_tools import WEB_TOOL_NAMES

    literals = 0
    for path in _tracked_python_files():
        rel = f"/{path.relative_to(REPO)}"
        if (
            "/tests/" in rel
            or "/.archive/" in rel
            or "/archived/" in rel
            or path.name == "check_command_corpus.py"
        ):
            continue
        try:
            found = _web_tools_literals(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue  # a sibling's mid-`git mv` leaves a tracked path with no file (shared tree, FC8)
        for names in found:
            if names is None:
                continue
            literals += 1
            bad = [n for n in names if n not in WEB_TOOL_NAMES]
            assert not bad, (str(path.relative_to(REPO)), bad, sorted(WEB_TOOL_NAMES))
    assert literals >= 1, "the classifier's literal must be in the sweep"
    classifier = (REPO / "scripts" / "classify_services.py").read_text(encoding="utf-8")
    pinned = _fanout_web_tools(
        classifier
    )  # the `fanout(` call's own literal, never a positional guess (DQ2)
    assert pinned and "web_search" in pinned, "the classifier's units must SEARCH (DK1)"
    assert "recover_caps=False" in classifier, (
        "a zero-output cap is a retry, never a serial re-dispatch on top of the step budget (DO1)"
    )


def _fanout_web_tools(source: str) -> list[str] | None:
    """The `web_tools=` literal of the FIRST `fanout(` call in the file (DQ2)."""
    import ast

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "fanout":
            for kw in node.keywords:
                if kw.arg == "web_tools":
                    got = _web_tools_literals(ast.unparse(node))
                    return got[0] if got else None
    return None


def test_the_pin_reads_the_fanout_call_not_the_first_literal():
    """A decoy literal before the `fanout(` call must not be the one pinned (DS3)."""
    src = 'cfg = dict(web_tools=["exa"])\nfanout("research", web_tools=["web_search"])\n'
    assert _fanout_web_tools(src) == ["web_search"]


def test_the_sweep_parses_every_literal_shape():
    """The parser the sweep relies on, over the shapes the regexes lost (DO2)."""
    src = (
        'a(web_tools=["web_search"], system="research")\n'
        'b(web_tools={"web_search", "exa"})\n'
        'c(web_tools=frozenset({"web_search"} | {"brave"}))\n'
        'd(web_tools=frozenset(sorted({"docs_lookup"})))\n'
        "e(web_tools=spec.web_tools)\n"
        "f(web_tools=None)\n"
    )
    got = _web_tools_literals(src)
    assert got == [
        ["web_search"],
        ["web_search", "exa"],
        ["web_search", "brave"],
        ["docs_lookup"],
        None,
        None,
    ], got


def test_gen_dashboard_two_writers_both_succeed_and_a_bad_out_path_is_one_typed_line(tmp_path):
    """Two concurrent invocations on ONE output path (a manual refresh overlapping the cron's
    step) shared a tmp name; the faster writer's pre-write unlink made the slower one's
    `os.replace` raise a raw FileNotFoundError. PID-named tmps: both exit 0 and the page is one
    whole document. A directory (or a missing parent) at `out` is one `ERROR:` line and exit 1,
    never a traceback (EW4)."""
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts" / "gen_dashboard.py"
    stub = tmp_path / "sitecustomize.py"  # slow the render so the two writers overlap
    stub.write_text(
        "import time, pathlib\n"
        "import gen_dashboard as gd\n"
        "_w = pathlib.Path.write_text\n"
        "def slow(self, *a, **k):\n"  # the tmp EXISTS while the writer sleeps — the window the race needs
        "    r = _w(self, *a, **k)\n"
        "    time.sleep(0.7)\n"
        "    return r\n"
        "pathlib.Path.write_text = slow\n"
        "gd.load = lambda: []\n",
        encoding="utf-8",
    )
    out = tmp_path / "dash.html"
    env = {**os.environ, "PYTHONPATH": f"{tmp_path}{os.pathsep}{script.parent}"}
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import sitecustomize, gen_dashboard as gd, sys; sys.exit(gd.main([{str(out)!r}]))",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    try:
        results = [(pr.wait(timeout=60), pr.stderr.read()) for pr in procs]
    finally:
        for pr in procs:  # a timeout must not leak two writers and their pipes (FB11)
            if pr.poll() is None:
                pr.kill()
            pr.stdout.close()
            pr.stderr.close()
    assert all(rc == 0 for rc, _ in results), results
    assert out.read_text(encoding="utf-8").rstrip().endswith("</html>"), out.read_text()[-80:]
    assert not list(tmp_path.glob("dash.html.tmp*")), list(tmp_path.iterdir())
    bad = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sitecustomize, gen_dashboard as gd, sys; sys.exit(gd.main([{str(tmp_path)!r}]))",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert bad.returncode == 1 and "ERROR:" in bad.stdout and "Traceback" not in bad.stderr, (
        bad.stdout,
        bad.stderr,
    )


def test_gen_dashboard_reports_a_dead_registry_as_one_typed_line(monkeypatch, capsys, tmp_path):
    """`load()` raising (a connection refused) left `main()` with a raw traceback; the write side
    had been brought to one typed line and exit 1 — the read side now matches (EY6)."""
    gd = _load_gen_dashboard()

    def dead():
        raise RuntimeError("connection refused (simulated)")

    monkeypatch.setattr(gd, "load", dead)
    assert gd.main([str(tmp_path / "dash.html")]) == 1
    out = capsys.readouterr().out
    assert "ERROR: registry unreadable" in out and "nothing written" in out, out
    assert not (tmp_path / "dash.html").exists()


def _caller_block(src: str, start_marker: str, end_marker: str) -> str:
    start = src.index(start_marker)
    return src[start : src.index(end_marker, start)]


def test_both_callers_parse_and_alert_when_the_chain_never_started(tmp_path):
    """EXECUTED, not text-matched: the round-60 text grader passed a hook block that did not even
    PARSE (a `"` inside the outer `bash -c "…"` string broke every interactive shell that sources
    the hook) and an `_rc=$?` captured inside `if ! cmd; then` — always 0, the 126/127 branch dead
    in both callers. Each caller's block runs here in a harness whose chain script is MISSING:
    the stub alert must be called with "did NOT start" and the log line must say exit 127 (EZ2)."""
    import subprocess

    for path in (DAILY, HOOK):  # each file separately: `bash -n a b` checks only `a`
        assert (
            subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True).returncode
            == 0
        ), path
    root = (
        tmp_path / "root dir"
    )  # a SPACE: the hook's block expanded bare `$LOG_FILE`/`$FABRIK_ROOT` into the inner shell's text (FB10)
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    stub = root / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf \'%s|%s\\n\' "$1" "$2" >> "$ALERTS"\n', encoding="utf-8"
    )
    alerts = tmp_path / "alerts.txt"
    log = tmp_path / "log.txt"
    log.write_text("", encoding="utf-8")
    daily_block = _caller_block(
        DAILY.read_text(encoding="utf-8"), '  _rc=0\n  _step "external_services_chain"', "\n\n"
    )
    hook_block = (
        _caller_block(
            HOOK.read_text(encoding="utf-8"),
            '        _rc=0; env LOG_FILE=\\"$LOG_FILE\\"',
            "        # Auto-commit",
        )
        .replace("\\$", "$")
        .replace('\\"', '"')  # what the outer `bash -c "…"` string hands the inner shell
    )
    for name, block in (("daily_refresh", daily_block), ("wsl_startup_hook", hook_block)):
        alerts.write_text("", encoding="utf-8")
        harness = tmp_path / f"{name}.sh"
        harness.write_text(
            'set -u\n_step() { local label="$1"; shift; "$@"; }\n'
            f'FABRIK_ROOT="{root}"\nKB="{root}/scripts/kilo-benchmarks"\nLOG_FILE="{log}"\nexport ALERTS="{alerts}"\n'
            + block
            + "\n",
            encoding="utf-8",
        )
        proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr + log.read_text(encoding="utf-8")
        assert "did NOT start" in alerts.read_text(encoding="utf-8"), (
            name,
            alerts.read_text(encoding="utf-8"),
            out,
        )
        assert "exit 127" in out, (name, out)
        # the 126 half: the script PRESENT but unreadable (a lost permission bit) — the other branch of `126|127` (FB3)
        chain = root / "scripts" / "external_services_chain.sh"
        chain.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        chain.chmod(0)
        if os.access(chain, os.R_OK):
            pytest.skip("running as root — permissions are not enforced")
        alerts.write_text("", encoding="utf-8")
        log.write_text("", encoding="utf-8")
        proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr + log.read_text(encoding="utf-8")
        chain.chmod(0o644)
        assert "did NOT start" in alerts.read_text(encoding="utf-8") and "exit 126" in out, (
            name,
            out,
        )
        # the NEGATIVE path: a chain that started and failed normally (exit 3) must NOT get the caller's alert
        chain.write_text("#!/usr/bin/env bash\nexit 3\n", encoding="utf-8")
        alerts.write_text("", encoding="utf-8")
        log.write_text("", encoding="utf-8")
        proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr + log.read_text(encoding="utf-8")
        chain.unlink()
        assert alerts.read_text(encoding="utf-8") == "" and "exit 3" in out, (name, out)


def test_gen_dashboard_reports_a_row_the_template_cannot_render_as_one_typed_line(
    monkeypatch, capsys, tmp_path
):
    """EY6 wrapped `load()` only; a row shape `render()` cannot take (a column drift) was still a
    raw traceback (EZ4)."""
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "load", lambda: [{"provider": "x"}])  # every other key absent
    assert gd.main([str(tmp_path / "dash.html")]) == 1
    assert "ERROR: registry unreadable" in capsys.readouterr().out
    assert not (tmp_path / "dash.html").exists()


def test_the_dashboard_flags_a_credit_balance_nobody_has_fetched_in_two_laps(monkeypatch):
    """A failed fetch (a revoked key, a renamed vendor field, an outage) inserts no snapshot, so
    the dashboard kept rendering the LAST balance forever — a dead credential and a healthy one
    were the same cell (FB9)."""
    import datetime as dt

    gd = _load_gen_dashboard()
    now = dt.datetime(2026, 9, 3, 6, 0, tzinfo=dt.UTC)
    fresh = now - dt.timedelta(hours=20)
    old = now - dt.timedelta(days=5)
    assert gd.credit_cell(12.5, "usd", fresh, now) == "12.5 usd"
    assert gd.credit_cell(12.5, "usd", old, now) == "⚠ 12.5 usd (5d old)"
    assert gd.credit_cell(3, None, None, now) == "3"
    assert (
        gd.credit_cell(None, "usd", old, now) == ""
    )  # a nullable column: a NULL balance was a TypeError that took the whole step down (FC4)
    assert (
        gd.credit_cell(1, "usd", now - dt.timedelta(hours=48), now) == "1 usd"
    )  # the boundary, both sides (B-C12)
    assert gd.credit_cell(1, "usd", now - dt.timedelta(hours=48, seconds=1), now).startswith(
        "⚠ 1 usd"
    )

    answers = {
        "FROM services": [("apify", "Apify", "scraping", "paid", "https://apify.com", "active")],
        "information_schema": [(1,)],
        "FROM api_keys": [],
        "credit_snapshots": [("apify", 12.5, "usd", old)],
        "FROM subscriptions": [],
    }

    class _Cur:
        def __init__(self):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, *a):
            if "credit_snapshots" in sql:
                assert "fetched_at DESC, id DESC" in sql, (
                    sql
                )  # the latest row wins, ties broken (E2-C8/FC4)
            self.rows = next(v for k, v in answers.items() if k in sql)

        def fetchall(self):
            return list(self.rows)

        def fetchone(self):
            return self.rows[0] if self.rows else None

    class _Conn:
        def cursor(self):
            return _Cur()

        def close(self):
            pass

    monkeypatch.setattr(gd.registry_db, "connect", lambda: _Conn())
    rows = gd.load()
    assert rows[0]["credit"].startswith("⚠ 12.5 usd (") and "d old)" in rows[0]["credit"], rows


def test_a_non_delivered_alert_is_said_where_the_caller_logs(tmp_path):
    """`send_alert` returns False with no log line when alerting is disabled (no token, a fresh
    .env) or the title is deduplicated: `pipeline_alert.sh` — the ONE signal for a chain that
    never started — exited 0 with zero output. Now it says so on stderr (FB10)."""
    import shutil

    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    (root / ".venv").symlink_to(REPO / ".venv", target_is_directory=True)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")  # the ONE package (FC6)
    # a MINIMAL environment, never a filtered copy of the test process's: an earlier suite imports
    # `libs.subagents`, whose package autoload puts the hub's whole `.env` into `os.environ`, and a
    # name-list filter is one key short of a real delivery (FC6)
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env["FABRIK_ROOT"] = str(root)
    env["FABRIK_NO_AUTOLOAD"] = (
        "1"  # belt and braces: the helper opts out itself; a test must NEVER reach the hub's real .env and deliver (FC6)
    )
    proc = subprocess.run(
        [
            "bash",
            str(REPO / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"),
            "CRITICAL: probe",
            "body",
        ],
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "NOT delivered (alerting disabled — no TELEGRAM_*/ALERT_VPS_HOST" in proc.stdout, (
        proc.stdout,
        proc.stderr,
    )  # the cause is NAMED, on the stream the heredoc merges (FC6); `returncode == 0` is a hardcoded exit and proves nothing
    # a MISSING interpreter is the other silent non-delivery: the heredoc never ran (H-F3/FC6)
    bare = tmp_path / "bare"
    bare.mkdir()
    proc = subprocess.run(
        [
            "bash",
            str(REPO / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"),
            "CRITICAL: probe",
            "body",
        ],
        env={**env, "FABRIK_ROOT": str(bare)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "NOT delivered (no interpreter at" in proc.stderr, (proc.stdout, proc.stderr)


def test_the_live_twin_renders_through_the_dashboards_own_helpers():
    """`dashboard_server.py` carried a pre-repair copy of the escaper (no `'`), an unsanitised
    pill class and no scheme gate — a live `<img onerror>` on :8770 (K 1–3/FC4). One source:
    the page is assembled from gen_dashboard.HELPERS."""
    import importlib.util

    gd = _load_gen_dashboard()
    spec = importlib.util.spec_from_file_location(
        "dashboard_server", REPO / "scripts" / "dashboard_server.py"
    )
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    assert "__HELPERS__" in ds.PAGE and "const esc=" not in ds.PAGE and "href(r.url)" in ds.PAGE
    # the SERVED page, through the handler — the first grader re-did the substitution itself and a
    # deleted `.replace("__HELPERS__", …)` shipped a blank dashboard green (H-1/K64-3, FD7)
    sent: dict[str, bytes] = {}

    class _Probe(ds.Handler):
        def __init__(self, path):  # no socket: only the routing + substitution is exercised
            self.path = path

        def _send(self, body, ctype):
            sent[ctype] = body

    _Probe("/").do_GET()
    page = sent["text/html; charset=utf-8"].decode("utf-8")
    assert gd.HELPERS in page and "'&#39;'" in gd.HELPERS and "/^https?:" in gd.HELPERS
    assert not re.findall(r"__[A-Z_]+__", page), re.findall(r"__[A-Z_]+__", page)
    assert page.count("const esc=") == 1
    assert "credit stale" in page and f"older than {gd.STALE_AFTER_H} h" in page
    assert "unattributed keys" in page and "unattributed</span>" in page, (
        "the twin dropped the BM9 degraded-case signal (K64-7)"
    )
    assert "<option value=\"'+esc(c)+'\"" in page, (
        "an <option> without value= strips whitespace and filters zero rows (K64-15)"
    )
    assert _helpers_shape(gd.HELPERS)
    assert "Localhost-only" not in (REPO / "scripts" / "dashboard_server.py").read_text(
        encoding="utf-8"
    )


def test_a_stale_credit_never_counts_as_tracked_and_the_page_explains_the_flag(monkeypatch):
    """The headline `credit tracked` counted a `⚠` cell; nothing on the page said what `⚠` means (FC4)."""
    gd = _load_gen_dashboard()
    rows = [
        {
            "provider": "a",
            "category": "c",
            "cost": "paid",
            "url": "",
            "status": "active",
            "keys": 1,
            "unattributed": 0,
            "projects": [],
            "account": "",
            "credit": "⚠ 1 usd (5d old)",
            "renews": "",
            "price": "",
        },
        {
            "provider": "b",
            "category": "c",
            "cost": "paid",
            "url": "",
            "status": "active",
            "keys": 1,
            "unattributed": 0,
            "projects": [],
            "account": "",
            "credit": "2 usd",
            "renews": "",
            "price": "",
        },
    ]
    html = gd.render(rows)
    assert "credit stale" in html and f"older than {gd.STALE_AFTER_H} h" in html
    i = html.index("credit tracked")
    assert html[i - 80 : i].count(">1<") == 1, html[i - 120 : i]


def test_the_chains_own_alert_says_why_it_was_not_delivered_and_survives_a_bad_env(tmp_path):
    """The chain's `_alert` had no grader (B-C8): run the real function with a throwaway root
    carrying the one alerting package and no delivery vars — the cause is named; an unreadable
    `.env` is said instead of a traceback that swallowed the alert (M-C2/FC6); the root travels
    as argv, so a `'` in it is not a SyntaxError (M-C13)."""
    import shutil

    root = tmp_path / "ro'ot"
    (root / "libs").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    (root / ".env").write_text("", encoding="utf-8")
    (root / ".env").chmod(
        0
    )  # unreadable: dotenv raises PermissionError (a missing path returns False)
    if os.access(root / ".env", os.R_OK):
        pytest.skip("running as root — permissions are not enforced")
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    fn = text[text.index("_alert() {") : text.index("_step() {")]
    harness = tmp_path / "h.sh"
    harness.write_text(
        f'FABRIK_ROOT="{root}"\nVENV_PY="{sys.executable}"\n' + fn + '\n_alert "t1" "b" warning\n',
        encoding="utf-8",
    )
    env = {  # a MINIMAL environment — the name-list filter was one key short of a real delivery (B-2, FD6)
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env["FABRIK_NO_AUTOLOAD"] = "1"
    proc = subprocess.run(
        ["bash", str(harness)], env=env, capture_output=True, text=True, timeout=60, cwd=root
    )
    assert (
        "[chain] .env not loaded:" in proc.stdout
        and "[chain] alert NOT delivered (alerting disabled (no TELEGRAM_*/ALERT_VPS_HOST in the environment)): t1"
        in proc.stdout
    ), (proc.stdout, proc.stderr)


def test_a_killed_chain_is_alerted_by_both_callers(tmp_path):
    """124/137 — the chain PROCESS killed by timeout or OOM — was logged and never alerted: its own
    step alert cannot run, and the callers special-cased 126/127 only (D6/FC6)."""
    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    stub = root / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf \'%s|%s\\n\' "$1" "$2" >> "$ALERTS"\n', encoding="utf-8"
    )
    chain = root / "scripts" / "external_services_chain.sh"
    chain.write_text("#!/usr/bin/env bash\nexit 137\n", encoding="utf-8")
    alerts, log = tmp_path / "alerts.txt", tmp_path / "log.txt"
    daily_block = _caller_block(
        DAILY.read_text(encoding="utf-8"), '  _rc=0\n  _step "external_services_chain"', "\n\n"
    )
    hook_block = (
        _caller_block(
            HOOK.read_text(encoding="utf-8"),
            '        _rc=0; env LOG_FILE=\\"$LOG_FILE\\"',
            "        # Auto-commit",
        )
        .replace("\\$", "$")
        .replace('\\"', '"')
    )
    for name, block in (("daily_refresh", daily_block), ("wsl_startup_hook", hook_block)):
        alerts.write_text("", encoding="utf-8")
        log.write_text("", encoding="utf-8")
        harness = tmp_path / f"{name}.sh"
        harness.write_text(
            'set -u\n_step() { local label="$1"; shift; "$@"; }\n'
            + f'FABRIK_ROOT="{root}"\nKB="{root}/scripts/kilo-benchmarks"\nLOG_FILE="{log}"\nexport ALERTS="{alerts}"\n'
            + block
            + "\n",
            encoding="utf-8",
        )
        subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
        assert "was KILLED" in alerts.read_text(encoding="utf-8"), (
            name,
            alerts.read_text(encoding="utf-8"),
        )


def test_a_zero_step_budget_never_disables_the_timeout():
    """`STEP_TIMEOUT=0` passed every guard and turned timeout(1) off — the only hang protection (D10/FC6)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    head = text[: text.index("LOG_FILE=")]
    proc = subprocess.run(
        ["bash", "-c", head + '\necho "$STEP_TIMEOUT $CLASSIFY_TIMEOUT"'],
        env={**os.environ, "STEP_TIMEOUT": "0", "CLASSIFY_TIMEOUT": "abc"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "900 2100", (proc.stdout, proc.stderr)


def test_import_alerting_from_the_kilo_directory_is_libs_alerting():
    """A same-named SHIM in scripts/kilo-benchmarks/alerting self-imported when loaded as
    `alerting` from that directory (`from alerting import *` found the half-initialised shim) and
    every `except ImportError` caller — the freshness heartbeat alert — went silent; the first
    grader loaded the shim under a name no caller uses (M-1/D-1, FD6). The directory is gone
    (D-110); the resolution is asserted OUT of process, from the callers' own cwd and path."""
    assert not (REPO / "scripts" / "kilo-benchmarks" / "alerting").exists()
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env["FABRIK_NO_AUTOLOAD"] = "1"
    kb = REPO / "scripts" / "kilo-benchmarks"
    for cwd, code in (
        (
            kb,
            "import sys; sys.path.insert(0, '.'); import check_daily_refresh_freshness; import alerting; print(alerting.__file__)",
        ),
        (
            kb / "tests",
            "import sys; sys.path.insert(0, '.'); import conftest; import alerting; print(alerting.__file__)",
        ),
    ):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (cwd, proc.stderr[-800:])
        assert (
            Path(proc.stdout.strip()).resolve()
            == (REPO / "libs" / "alerting" / "__init__.py").resolve()
        ), proc.stdout


def test_the_chains_alert_says_when_its_interpreter_is_missing(tmp_path):
    """`_alert` claimed "alerting" while `timeout` failed to run a missing venv python and every
    alert was lost (D-6/M-4, FD6); a DIRECTORY at the interpreter path is the same silence."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    fn = text[text.index("_alert() {") : text.index("_step() {")]
    (tmp_path / "dirpy").mkdir()
    for py in (tmp_path / "no-venv" / "python", tmp_path / "dirpy"):
        harness = tmp_path / "h.sh"
        harness.write_text(
            f'FABRIK_ROOT="{tmp_path}"\nVENV_PY="{py}"\n' + fn + '\n_alert "t9" "b" warning\n',
            encoding="utf-8",
        )
        proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
        assert (
            "[chain] alert NOT delivered (no interpreter at" in proc.stdout and "t9" in proc.stdout
        ), (proc.stdout, proc.stderr)
        assert proc.stderr == "", proc.stderr


def test_a_signal_death_of_the_chain_is_alerted_by_both_callers(tmp_path):
    """The killed-chain branch matched `124|137` only: SIGHUP (129), SIGINT (130) and SIGTERM (143) —
    the realistic deaths of a boot-path pipeline — logged a line nobody was paged for (D-4, FD6)."""
    daily = (REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").read_text(encoding="utf-8")
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    for text in (daily, hook):
        assert text.count("124|129|130|137|143)") == 1, "both callers alert on every signal death"
        assert "124|137)" not in text
    assert "export FABRIK_ROOT" in daily
    assert 'cd "$FABRIK_ROOT" || exit 1' in (
        REPO / "scripts" / "external_services_chain.sh"
    ).read_text(encoding="utf-8")


def test_the_hooks_stderr_redirect_precedes_the_append_and_its_stamps_are_inner(tmp_path):
    """`: >>FILE 2>/dev/null` printed "Permission denied" into the login shell before fd 2 moved
    (D-5); both `=== … ===` stamps were expanded by the OUTER shell, so every daily log reported a
    0-second pipeline (D-8); the unwritable-log alert's own diagnostics went to /dev/null (D-7) (FD6)."""
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    assert ': 2>/dev/null >>"$LOG_FILE"' in hook and ': 2>/dev/null >>"$_fallback"' in hook
    assert ': >>"$LOG_FILE" 2>/dev/null' not in hook
    assert hook.count("'\\$(date '+%Y-%m-%d %H:%M:%S')' ==='") == 2, (
        "both stamps are expanded by the inner shell"
    )
    assert ">/dev/null 2>&1 & )" not in hook
    daily = (REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").read_text(encoding="utf-8")
    assert ': 2>/dev/null >>"$1"' in daily
    # the order is executable, not just spelled: an unwritable target prints NOTHING
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        proc = subprocess.run(
            [
                "bash",
                "-c",
                f'if ! {{ mkdir -p "{ro}" 2>/dev/null && : 2>/dev/null >>"{ro}/x.log"; }}; then echo GUARDED; fi',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        ro.chmod(0o755)
    if proc.stdout.strip() == "GUARDED":  # not root
        assert proc.stderr == "", proc.stderr


def test_the_hook_rotation_never_loses_a_generation_and_never_enters_a_directory(tmp_path):
    """`.1 → .2` ran BEFORE `log → .1`; on an unwritable dir the promotion alone succeeded and the
    oldest generation vanished. `mv` without `-T` moved the live log INTO a directory named `.1`
    (D-12, the chain's DC2 class) (FD6)."""
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    start = hook.index("        # promote .1")
    snippet = hook[start : hook.index("        fi\n", start) + 11]
    assert (
        'mv -T "$logfile" "${logfile}.1.new"' in snippet
        and 'mv -T "${logfile}.1" "${logfile}.2"' in snippet
    )
    assert snippet.index('mv -T "$logfile"') < snippet.index('mv -T "${logfile}.1" "${logfile}.2"')
    log = tmp_path / "update.log"
    log.write_text("LIVE\n")
    (tmp_path / "update.log.1").mkdir()
    run = lambda: subprocess.run(  # noqa: E731
        ["bash", "-c", f'logfile="{log}"\n{snippet}'], capture_output=True, text=True, timeout=30
    )
    proc = run()
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    # a directory in the way: `-T` moves the directory aside as `.2`; the live log lands in `.1`
    # as a FILE — never inside the directory (the pre-fix `mv` put update.log.1/update.log there)
    assert (
        not (tmp_path / "update.log.2" / "update.log").exists()
        and not (tmp_path / "update.log.1").is_dir()
    )
    assert (tmp_path / "update.log.1").read_text() == "LIVE\n", sorted(
        p.name for p in tmp_path.rglob("*")
    )
    assert "Log rotated" in log.read_text()
    shutil.rmtree(tmp_path / "update.log.2")
    log.write_text("LIVE2\n")
    proc = run()
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    assert (tmp_path / "update.log.1").read_text() == "LIVE2\n"
    assert (tmp_path / "update.log.2").read_text() == "LIVE\n", (
        "the older generation is promoted, never lost"
    )
    assert "Log rotated" in log.read_text()


def test_every_alert_call_inside_the_hooks_outer_string_reaches_the_log():
    """Three sibling `pipeline_alert.sh` calls inside the boot hook's `nohup bash -c "…"` string
    had no redirect: their `NOT delivered` diagnostics landed in a stray `nohup.out` in whatever
    directory the login shell sat in (D5/FC6)."""
    text = HOOK.read_text(encoding="utf-8")
    start = text.index('nohup bash -c "')
    outer = text[start : text.index('\n    " &', start)]
    calls = [ln for ln in outer.splitlines() if "pipeline_alert.sh" in ln]
    assert len(calls) == 4, (
        calls
    )  # exact: the three sibling calls + the killed-chain alert — `>=` accepted a deleted site (B-9, FD8)
    for ln in calls:
        assert '>> \\"$LOG_FILE\\" 2>&1' in ln, ln


def _helpers_shape(helpers: str) -> bool:
    """The shared slice is exactly the four helper consts — a widened slice dragged `render()` into
    the twin and defined it twice, quietly (K64-12, FD7)."""
    consts = re.findall(r"^const (\w+)=", helpers, flags=re.M)
    return (
        consts == ["esc", "href", "cpill", "cell"]
        and "function render" not in helpers
        and "<script>" not in helpers
    )


def test_the_live_twins_500_never_puts_the_exception_on_the_wire(monkeypatch, capsys):
    """`send_error(500, str(exc))` wrote libpq's newline-bearing text into the STATUS LINE (response
    splitting), raised UnicodeEncodeError inside the except on a `—` (zero bytes sent), and told
    every LAN client the WireGuard host + role name (K64-1/2/5, FD7)."""
    import importlib.util

    _load_gen_dashboard()
    spec = importlib.util.spec_from_file_location(
        "dashboard_server", REPO / "scripts" / "dashboard_server.py"
    )
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    errors: list[tuple[int, str]] = []

    class _Probe(ds.Handler):
        def __init__(self, path):
            self.path = path

        def send_error(self, code, message=None, explain=None):
            errors.append((code, message))

    def boom():
        raise RuntimeError(
            'connection to server at "10.99.0.1", port 5432 failed\r\nX-Injected: yes — ⚠ café'
        )

    monkeypatch.setattr(ds.gen_dashboard, "load", boom)
    _Probe("/api/services").do_GET()
    assert errors == [(500, "registry query failed")], errors
    err = capsys.readouterr().err
    assert "dashboard: RuntimeError:" in err and "10.99.0.1" in err and "\r" not in err
    import pytest as _pytest

    with _pytest.raises(SystemExit) as exc:
        ds.main(["abc"])
    assert exc.value.code == 2
    with _pytest.raises(SystemExit):
        ds.main(["99999"])


def test_the_stale_credit_count_and_the_nan_balance(monkeypatch):
    """The `credit stale` NUMBER was never asserted (hardcoding 0 passed); a NaN balance rendered
    as a number and counted as tracked (K64-10/14, FD7)."""
    gd = _load_gen_dashboard()
    row = {
        "provider": "a",
        "category": "c",
        "cost": "paid",
        "url": "",
        "status": "active",
        "keys": 1,
        "unattributed": 0,
        "projects": [],
        "account": "",
        "credit": "⚠ 1 usd (5d old)",
        "renews": "",
        "price": "",
    }
    html = gd.render(
        [
            row,
            {**row, "provider": "b", "credit": "2 usd"},
            {**row, "provider": "c", "credit": "⚠ 3 usd (6d old)"},
        ]
    )
    m = re.search(r'<div class="n">(\d+)</div><div class="l">credit stale</div>', html)
    assert m and m.group(1) == "2", html[
        html.index("credit stale") - 120 : html.index("credit stale")
    ]
    m = re.search(r'<div class="n">(\d+)</div><div class="l">credit tracked</div>', html)
    assert m and m.group(1) == "1"
    from decimal import Decimal

    assert (
        gd.credit_cell(float("nan"), "usd", None) == ""
        and gd.credit_cell(Decimal("NaN"), "usd", None) == ""
    )
    assert gd.credit_cell(Decimal("12.5"), "usd", None) == "12.5 usd"


def test_the_chain_alerts_a_credit_phase_failure_without_failing_the_step(tmp_path):
    """registry_sync exit 3 (registry written, credit phase failed) was a stderr WARNING nobody was
    paged for; the chain now alerts it and still renders the dashboard (G-C6/E2-C10, FD7)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    fn = text[text.index("_step() {") : text.index("\n}\n", text.index("_step() {")) + 3]
    harness = tmp_path / "h.sh"
    harness.write_text(
        "STEP_TIMEOUT=30\nCLASSIFY_TIMEOUT=30\nchain_failed=0\ncore_failed=0\n"
        '_alert() { echo "ALERT: $1 [$3]"; }\n'
        + fn
        + '\n_step registry_sync bash -c "exit 3"\necho "chain_failed=$chain_failed core_failed=$core_failed"\n'
        '_step gather_envs bash -c "exit 3"\necho "chain_failed=$chain_failed"\n',
        encoding="utf-8",
    )
    proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
    out = proc.stdout
    assert (
        "ALERT: external-services chain: credit fetch failed after the registry commit [warning]"
        in out
    ), out
    assert "chain_failed=0 core_failed=0" in out, out
    assert out.rstrip().endswith("chain_failed=1"), (
        out
    )  # exit 3 from any OTHER step is still a failure
