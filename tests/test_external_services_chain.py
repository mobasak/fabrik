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
        assert 'FABRIK_ROOT="$FABRIK_ROOT"' in line, line


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
    assert len(alerts) == 2 and body in [b for _t, b in alerts], (
        alerts
    )  # the pin: two alerts, both graded
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
        except SyntaxError:
            continue
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
    results = [(pr.wait(timeout=60), pr.stderr.read()) for pr in procs]
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


def test_both_callers_alert_when_the_chain_never_started():
    """`bash chain.sh` exiting 126/127 (missing, not executable) runs NONE of the chain's own
    alerts, yet both callers said "already alerted". Each caller now alerts that case itself (EY7)."""
    for src, name in (
        (DAILY.read_text(encoding="utf-8"), "daily_refresh"),
        (HOOK.read_text(encoding="utf-8"), "wsl_startup_hook"),
    ):
        start = (
            src.index('bash "$FABRIK_ROOT/scripts/external_services_chain.sh"')
            if 'bash "$FABRIK_ROOT/scripts/external_services_chain.sh"' in src
            else src.index("bash $FABRIK_ROOT/scripts/external_services_chain.sh")
        )
        block = src[start : start + 900]
        assert "126|127" in block and "pipeline_alert.sh" in block and "did NOT start" in block, (
            name,
            block,
        )
