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
# The venv running this suite: the helper fixtures link it in as `<root>/.venv`. Never `REPO / ".venv"` —
# a merge or probe worktree has no `.venv` of its own, and three tests then read "no interpreter".
VENV = Path(sys.prefix)
DAILY = REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh"
REGISTRY = REPO / ".fabrik" / "liveness-registry.json"


CHAIN = REPO / "scripts" / "external_services_chain.sh"
HOOK = REPO / "scripts" / "wsl_startup_hook.sh"


def _steps(text: str) -> list[str]:
    return re.findall(r"^\s*(?:if )?_step (\S+)", text, re.M)  # the dashboard step is an `if` (CY1)


def test_the_chain_is_one_script_in_order_with_a_gated_heartbeat():
    text = CHAIN.read_text(encoding="utf-8")
    # D-1046 retired the pool-only classify step and its reconsolidate re-run: a category comes
    # from a hand-written service_catalog.json entry, so neither the step nor its budget remains
    assert _steps(text) == ["gather_envs", "registry_sync", "gen_dashboard"]
    code_only = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "classify_services" not in code_only and "CLASSIFY_TIMEOUT" not in text
    assert re.search(r"_step registry_sync.*--fetch-credits", text)
    step_fn = re.search(r"^_step\(\) \{[^\n]*\n(.*?)^\}", text, re.M | re.S).group(
        1
    )  # scoped INSIDE _step (DO2)
    assert 'local budget="$STEP_TIMEOUT"' in step_fn and 'timeout -k 30 "$budget"' in step_fn
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
    # the DATA steps the dashboard depends on — every step but the dashboard itself
    core = re.search(r'case "\$label" in ([^)]*)\) core_failed=1', text).group(1)
    assert set(core.split("|")) == {"gather_envs", "registry_sync"}
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
    # The probe runs in a SUBDIRECTORY of tmp_path, never tmp_path itself: conftest's autouse
    # pins (`_isolated_sound_lock_dir`, `_isolated_kaizen_events_dir`, `_isolated_opt_dir`,
    # `_isolated_command_run_dir`) each create a directory under the SAME tmp_path, so
    # `os.listdir(tmp_path)` has not been empty since those pins landed 2026-09-16 — the
    # assertion below failed for that unrelated reason on every run, which left the real
    # 2026-09-02 defect (a `--help` that writes a file) UNGRADED behind a permanent red.
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(gd, "_read", lambda: pytest.fail("--help must not touch the registry"))
    with pytest.raises(SystemExit) as exc:
        gd.main(["--help"])
    assert exc.value.code == 0
    assert os.listdir(work) == [], "gen_dashboard --help wrote a file (the 2026-09-02 defect)"


def test_gen_dashboard_writes_the_named_output(tmp_path, monkeypatch):
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "_read", lambda: ([], None))
    monkeypatch.setattr(gd, "render", lambda rows, **kw: "<p>ok</p>")
    out = tmp_path / "dash.html"
    assert gd.main([str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "<p>ok</p>"
    assert not (tmp_path / "dash.html.tmp").exists()  # written atomically via tmp + os.replace


def test_gen_dashboard_write_is_atomic(tmp_path, monkeypatch):
    """The page goes to a tmp path and is `os.replace`d into place; a write that dies mid-stream
    leaves the old file untouched (a half-written dashboard is never served). Discriminating: the pre-fix
    `out.write_text(render(rows))` makes no `os.replace` call and truncates the target (H9)."""
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "_read", lambda: ([], None))
    monkeypatch.setattr(gd, "render", lambda rows, **kw: "<p>new</p>")
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


def test_registry_sync_is_gated_on_the_scan_and_the_doc_names_every_kind():
    """A failed scan skips the sync (and the dashboard): a stale file
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
    assert "1 gather: inputs refused" in body and "1 elsewhere" in body, body
    assert "3 registry" not in body, (
        body
    )  # exit 3 never reaches this alert (the dedicated exit-3 alert carries its own body): a legend clause about a state the message cannot describe was dead text (F67-12)
    assert "output path unusable" in body, body  # exit 1 is complete for the scan (CC5/CJ4)
    # Telegram's legacy Markdown fallback rejects an unbalanced `*`/`_`: the body's own text carries
    # none (the label and the log path are the only variables), and it stays within the alerting
    # contract's ~500 chars (CC5)
    fixed = re.sub(r"\$\{?[A-Za-z_]+\}?", "", body)
    assert "*" not in fixed and "_" not in fixed, fixed
    # every step is a DATA step now (D-1046 retired the paid classify step, the one label whose
    # failure left the heartbeat fresh), so the heartbeat clause is one for every label
    hb_default = re.search(r'local hb="([^"]*)"', text)
    assert hb_default and "$hb" in body, "the heartbeat clause"
    assert "DEAD" in hb_default.group(1) and "classify_services" not in text
    assert "*" not in hb_default.group(1) and "_" not in hb_default.group(1), hb_default.group(1)
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
            hb = hb_default.group(1)

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
    for step in ("registry_sync.py", "gen_dashboard.py"):
        row = next(ln for ln in doc.splitlines() if ln.startswith("| ") and step in ln)
        assert "skipped after a failed scan" in row, (
            row
        )  # the table says it, not only the prose (BS15)


def test_the_chain_script_executes_its_gating(tmp_path):
    """The chain EXECUTED under bash with a fake interpreter (every sibling test regex-matches the
    script; a bash syntax error or a gate that only LOOKS right passed them all — BU1): a failed
    scan skips the sync and the dashboard, alerts once, exits 1; a clean run writes the
    dashboard and exits 0, and never runs the classifier (D-1046)."""
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
        '  *gen_dashboard.py*) [ "${FAIL_DASHBOARD:-0}" = 1 ] && exit 7; echo ok > "${@: -1}" ;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    # a fake `timeout` on PATH logs the budget each step ran under: every step's budget is proven
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
        calls.count("gather_envs.py") == 1
        and "registry_sync.py" in calls
        and "send_alert(" not in calls
    )
    assert [re.search(r"scripts/(\S+\.py)", ln).group(1) for ln in calls.splitlines()] == [
        "gather_envs.py",
        "registry_sync.py",
        "gen_dashboard.py",
    ]  # no classify, no reconsolidate (D-1046)
    by_step: dict[str, list[str]] = {}
    for b, script in (ln.split() for ln in budgets.read_text(encoding="utf-8").splitlines()):
        by_step.setdefault(Path(script).name, []).append(b)
    assert set(by_step) == {"gather_envs.py", "registry_sync.py", "gen_dashboard.py"}, by_step
    assert {b for v in by_step.values() for b in v} == {"30"}, by_step
    # 3. the DASHBOARD step fails: exit 1, one alert, no dashboard, no stamp — the gate the stamp
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
    # 4. the stamp cannot be written (`.tmp` is a FILE): every step ran, the dashboard stands, the
    # failure is ALERTED and exits 1 — it was the only silent failure in the script (DA3)
    log.write_text("", encoding="utf-8")

    shutil.rmtree(root / ".tmp")
    (root / ".tmp").write_text("", encoding="utf-8")
    r = subprocess.run(["bash", str(CHAIN)], env=env, capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8")
    assert r.returncode == 1 and dash.exists() and not stamp.exists(), (r.returncode, calls)
    assert calls.count("send_alert(") == 1 and "heartbeat NOT stamped" in calls, calls
    assert "heartbeat NOT stamped" in r.stdout
    (root / ".tmp").unlink()
    # 5. `date` fails: a bare `> "$HEARTBEAT"` truncated the stamp BEFORE date ran — a fresh EMPTY
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
        "gd._read = lambda: ([], None)\n",
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

    monkeypatch.setattr(gd, "_read", dead)
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
        try:
            proc = subprocess.run(
                ["bash", str(harness)], capture_output=True, text=True, timeout=60
            )
        finally:
            chain.chmod(
                0o644
            )  # on ANY exit — a timeout left a mode-0 file in pytest's tmp tree (B65-11, FF1)
        out = proc.stdout + proc.stderr + log.read_text(encoding="utf-8")
        assert "did NOT start" in alerts.read_text(encoding="utf-8") and "exit 126" in out, (
            name,
            out,
        )
        assert "cd to FABRIK_ROOT failed" in alerts.read_text(encoding="utf-8"), (
            name,
            alerts.read_text(encoding="utf-8"),
        )  # a failed `cd` is exit 126 too, and the body said only "missing or unreadable" (M-C7, FF1)
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
    monkeypatch.setattr(
        gd, "_read", lambda: ([{"provider": "x"}], None)
    )  # every other key absent
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
        "max(last_seen)": [
            (fresh,)
        ],  # BEFORE `FROM api_keys`: the fake answers by FIRST substring match
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
    rows, synced_at = gd._read()
    assert rows[0]["balance"] == 12.5 and rows[0]["credit_at"] == old.timestamp(), rows
    assert synced_at == fresh.timestamp()
    page = gd.render(rows, synced_at=synced_at, now=now.timestamp())
    assert "⚠ 12.5 usd (5d old)" in page, "the flagged credit is the renderer's, not the reader's"


def test_a_non_delivered_alert_is_said_where_the_caller_logs(tmp_path):
    """`send_alert` returns False with no log line when alerting is disabled (no token, a fresh
    .env) or the title is deduplicated: `pipeline_alert.sh` — the ONE signal for a chain that
    never started — exited 0 with zero output. Now it says so on stderr (FB10)."""

    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    (root / ".venv").symlink_to(VENV, target_is_directory=True)
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


def _row(provider, **over):
    base = {
        "provider": provider,
        "category": "c",
        "cost": "paid",
        "url": "",
        "status": "active",
        "keys": 1,
        "unattributed": 0,
        "projects": [],
        "account": "",
        "balance": None,
        "unit": "",
        "credit_at": None,
        "renews": "",
        "price": "",
    }
    return {**base, **over}


def _count(page: str, name: str) -> str:
    m = re.search(rf'<tr data-count="{name}"><th scope="row">[^<]*</th><td[^>]*>(\d+)</td>', page)
    assert m, (name, page[:200])
    return m.group(1)


def test_a_stale_credit_never_counts_as_tracked_and_the_page_explains_the_flag():
    """The headline `credit tracked` counted a `⚠` cell; nothing on the page said what `⚠` means (FC4)."""
    gd = _load_gen_dashboard()
    now = 1_800_000_000.0
    rows = [
        _row("a", balance=1.0, unit="usd", credit_at=now - 5 * 86400),
        _row("b", balance=2.0, unit="usd", credit_at=now - 3600),
    ]
    page = gd.render(rows, synced_at=now - 60, now=now)
    assert "⚠ 1 usd (5d old)" in page and "No secret values" in page
    assert f"⚠ credit = older than {gd.STALE_AFTER_H} h" in page
    assert _count(page, "credit_tracked") == "1" and _count(page, "credit_stale") == "1"


def test_the_chains_own_alert_says_why_it_was_not_delivered_and_survives_a_bad_env(
    tmp_path, request
):
    """The chain's `_alert` had no grader (B-C8): run the real function with a throwaway root
    carrying the one alerting package and no delivery vars — the cause is named; an unreadable
    `.env` is said instead of a traceback that swallowed the alert (M-C2/FC6); the root travels
    as argv, so a `'` in it is not a SyntaxError (M-C13)."""

    root = tmp_path / "ro'ot"
    (root / "libs").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    (root / ".env").write_text("", encoding="utf-8")
    (root / ".env").chmod(
        0
    )  # unreadable: dotenv raises PermissionError (a missing path returns False)
    request.addfinalizer(lambda: (root / ".env").chmod(0o644))  # restored on ANY exit (B65-11, FF1)
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
    chain.write_text(
        "#!/usr/bin/env bash\nexit 131\n", encoding="utf-8"
    )  # SIGQUIT — outside the five codes the first fix enumerated (FE6)
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
        body = alerts.read_text(encoding="utf-8")
        assert "was KILLED" in body, (name, body)
        assert "signal 3" in body and "$((" not in body, (
            name,
            body,
        )  # the hook's arithmetic sat INSIDE single quotes: Telegram read `signal $((_rc > 128 ? …))` (M-C1, FF1)


def test_a_zero_step_budget_never_disables_the_timeout():
    """`STEP_TIMEOUT=0` passed every guard and turned timeout(1) off — the only hang protection (D10/FC6)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    head = text[: text.index("LOG_FILE=")]
    proc = subprocess.run(
        ["bash", "-c", head + '\necho "$STEP_TIMEOUT"'],
        env={**os.environ, "STEP_TIMEOUT": "0"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "900", (proc.stdout, proc.stderr)


def test_import_alerting_from_the_kilo_directory_is_libs_alerting():
    """A same-named SHIM in scripts/kilo-benchmarks/alerting self-imported when loaded as
    `alerting` from that directory (`from alerting import *` found the half-initialised shim) and
    every `except ImportError` caller — the freshness heartbeat alert — went silent; the first
    grader loaded the shim under a name no caller uses (M-1/D-1, FD6). The directory is gone
    (D-112); the resolution is asserted OUT of process, from the callers' own cwd and path."""
    assert not (REPO / "scripts" / "kilo-benchmarks" / "alerting").exists()
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env.update(
        {"ALERT_ENABLED": "0", "FABRIK_NO_AUTOLOAD": "1"}
    )  # an explicit env cannot inherit the conftest mute (B67-9)
    env["FABRIK_NO_AUTOLOAD"] = "1"
    kb = REPO / "scripts" / "kilo-benchmarks"
    for cwd, code in (
        (
            kb,
            "import sys; sys.path.insert(0, '.'); import check_daily_refresh_freshness; import alerting; print(alerting.__file__)",
        ),
        (
            kb,
            f"import sys; sys.path.append({str(REPO / 'libs')!r}); sys.path.insert(0, '.'); import check_daily_refresh_freshness; import alerting; assert sys.path[0] == {str(REPO / 'libs')!r}, sys.path[:3]; print(alerting.__file__)",
        ),  # libs already LATER on sys.path: the conditional insert left SCRIPT_DIR ahead of it (F-9, FE7)
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
        assert text.count("129|1[3-8][0-9]|19[0-2])") == 1, (
            "both callers alert on EVERY signal death (128+N, N in 1..64), not five enumerated codes (FE6) and not the plain exits 124/125/128/193-255 (FF1)"
        )
        assert "124|137)" not in text and "124|129|130|137|143)" not in text
        assert "12[4-9]|" not in text and "_rc > 128 ? _rc - 128 : 0" not in text
    assert "export FABRIK_ROOT" in daily
    assert 'cd "$FABRIK_ROOT" || {' in (REPO / "scripts" / "external_services_chain.sh").read_text(
        encoding="utf-8"
    )


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
    guard = re.search(
        r'if ! \{ mkdir -p "\$\(dirname "\$LOG_FILE"\)" 2>/dev/null && : 2>/dev/null >>"\$LOG_FILE"; \}; then',
        hook,
    )
    assert guard, (
        "the hook's log-directory guard moved — this grader slices it, never restates it (B65-10, FF1)"
    )
    ro.chmod(0o555)
    try:
        proc = subprocess.run(
            ["bash", "-c", f'LOG_FILE="{ro}/x.log"\n{guard.group(0)} echo GUARDED; fi'],
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        ro.chmod(0o755)
    if os.geteuid() == 0:
        pytest.skip("running as root — permissions are not enforced")
    assert proc.stdout.strip() == "GUARDED" and proc.stderr == "", (proc.stdout, proc.stderr)


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
    assert (
        snippet.index('mv -T "$logfile"') < snippet.rindex('mv -T "${logfile}.1" "${logfile}.2"')
    )  # the ROTATION's promotion (the last one); the earlier one finishes a stranded rotation first (FF1)
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
    assert any(
        p.name.startswith("update.log.1.notalog.") and p.is_dir() for p in tmp_path.iterdir()
    ), sorted(p.name for p in tmp_path.iterdir())  # the squatter was moved aside (FE4)
    log.write_text("LIVE2\n")
    proc = run()
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    assert (tmp_path / "update.log.1").read_text() == "LIVE2\n"
    assert (tmp_path / "update.log.2").read_text() == "LIVE\n", (
        "the older generation is promoted, never lost"
    )
    assert "Log rotated" in log.read_text()
    # the two squatter shapes the first grader never staged: a directory at `.2` with a file at `.1`
    # (the promotion failed and `.1` was overwritten — GEN lost) and a directory at `.1.new` (no
    # rotation, silently); both are moved aside as `*.notalog.<epoch>` (FE4)
    (tmp_path / "update.log.2").unlink()
    (tmp_path / "update.log.2").mkdir()
    (tmp_path / "update.log.1").write_text("GEN1\n")
    log.write_text("LIVE3\n")
    proc = run()
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    assert (tmp_path / "update.log.1").read_text() == "LIVE3\n" and (
        tmp_path / "update.log.2"
    ).read_text() == "GEN1\n", sorted(p.name for p in tmp_path.iterdir())
    assert any(
        p.name.startswith("update.log.2.notalog.") and p.is_dir() for p in tmp_path.iterdir()
    )
    (tmp_path / "update.log.1.new").mkdir()
    log.write_text("LIVE4\n")
    proc = run()
    assert (tmp_path / "update.log.1").read_text() == "LIVE4\n", sorted(
        p.name for p in tmp_path.iterdir()
    )


def test_every_alert_call_inside_the_hooks_outer_string_reaches_the_log():
    """Three sibling `pipeline_alert.sh` calls inside the boot hook's `nohup bash -c "…"` string
    had no redirect: their `NOT delivered` diagnostics landed in a stray `nohup.out` in whatever
    directory the login shell sat in (D5/FC6)."""
    text = HOOK.read_text(encoding="utf-8")
    start = text.index('nohup bash -c "')
    outer = text[start : text.index('\n    " >/dev/null 2>&1 &', start)]
    calls = [ln for ln in outer.splitlines() if "pipeline_alert.sh" in ln]
    assert len(calls) == 7 and all(ln.count("pipeline_alert.sh") == 1 for ln in calls), (
        calls
    )  # exact, ONE call per physical line: the three sibling calls, the did-NOT-start and KILLED alerts (two on one line counted once — a lost redirect on the second was invisible, B65-4), the heartbeat-write alert (M-C8), and the cost-sidecar refresh alert (2026-09-05, Phase C) — `>=` accepted a deleted site (B-9, FD8)
    for ln in calls:
        assert '>> \\"$LOG_FILE\\" 2>&1' in ln, ln


def test_the_stale_credit_count_and_the_nan_balance():
    """The `credit stale` NUMBER was never asserted (hardcoding 0 passed); a NaN balance rendered
    as a number and counted as tracked (K64-10/14, FD7)."""
    gd = _load_gen_dashboard()
    now = 1_800_000_000.0
    page = gd.render(
        [
            _row("a", balance=1.0, unit="usd", credit_at=now - 5 * 86400),
            _row("b", balance=2.0, unit="usd", credit_at=now - 60),
            _row("c", balance=3.0, unit="usd", credit_at=now - 6 * 86400),
            _row("d", balance=float("nan"), unit="usd", credit_at=now - 60),
        ],
        synced_at=now,
        now=now,
    )
    assert _count(page, "credit_stale") == "2" and _count(page, "credit_tracked") == "1"
    assert "nan usd" not in page.lower()
    from decimal import Decimal

    assert (
        gd.credit_cell(float("nan"), "usd", None) == ""
        and gd.credit_cell(Decimal("NaN"), "usd", None) == ""
    )
    assert (
        gd.credit_cell(Decimal("Infinity"), "usd", None) == ""
        and gd.credit_cell(float("-inf"), "usd", None) == ""
    )  # NUMERIC accepts Infinity too (FE1)
    assert gd.credit_cell(Decimal("12.5"), "usd", None) == "12.5 usd"


def test_the_chain_alerts_a_credit_phase_failure_without_failing_the_step(tmp_path):
    """registry_sync exit 3 (registry written, credit phase failed) was a stderr WARNING nobody was
    paged for; the chain now alerts it and still renders the dashboard (G-C6/E2-C10, FD7)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    fn = text[text.index("_step() {") : text.index("\n}\n", text.index("_step() {")) + 3]
    harness = tmp_path / "h.sh"
    harness.write_text(
        "STEP_TIMEOUT=30\nchain_failed=0\ncore_failed=0\n"
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


def test_the_chains_cd_failure_is_a_did_not_start_and_a_keyless_env_is_said(tmp_path):
    """`cd … || exit 1` was a silent exit 1 both callers read as a step failure the chain would
    have alerted itself; `_alert` never said a missing/keyless `.env` while the helper did (FE4)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    head = text[: text.index("VENV_PY=")]
    proc = subprocess.run(
        ["bash", "-c", head + "\necho reached"],
        env={"PATH": os.environ["PATH"], "FABRIK_ROOT": str(tmp_path / "nowhere")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (
        proc.returncode == 126 and "cannot cd to" in proc.stdout and "reached" not in proc.stdout
    ), (proc.returncode, proc.stdout, proc.stderr)
    fn = text[text.index("_alert() {") : text.index("_step() {")]
    root = tmp_path / "root"
    (root / "libs").mkdir(parents=True)

    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    harness = tmp_path / "h.sh"
    harness.write_text(
        f'FABRIK_ROOT="{root}"\nVENV_PY="{sys.executable}"\n' + fn + '\n_alert "t3" "b" warning\n',
        encoding="utf-8",
    )
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env.update(
        {"ALERT_ENABLED": "0", "FABRIK_NO_AUTOLOAD": "1"}
    )  # an explicit env cannot inherit the conftest mute (B67-9)
    env["FABRIK_NO_AUTOLOAD"] = "1"
    proc = subprocess.run(
        ["bash", str(harness)], env=env, capture_output=True, text=True, timeout=60, cwd=root
    )
    assert (
        "[chain] .env missing or without usable keys at" in proc.stdout
        and "alert NOT delivered" in proc.stdout
    ), (proc.stdout, proc.stderr)
    assert "dashboard step still runs" in text and "the dashboard is rendered" not in text


def test_the_helper_names_a_directory_interpreter_a_keyless_env_and_an_explicit_mute(tmp_path):
    """Five FD6 hunks had no grader (M-C3): a DIRECTORY at the helper's interpreter path, the
    `no usable keys in` wording, and — new — an explicit `ALERT_ENABLED=0` named as the cause
    instead of "no TELEGRAM_*" (FE6)."""

    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    (root / ".venv").symlink_to(VENV, target_is_directory=True)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    helper = REPO / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env.update({"FABRIK_ROOT": str(root), "FABRIK_NO_AUTOLOAD": "1", "ALERT_ENABLED": "0"})
    (root / ".env").write_text("# comment only\n", encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(helper), "t5", "b"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    both = (
        proc.stdout + proc.stderr
    )  # the helper merges python's stderr into its stdout (`2>&1`); the guard line goes to stderr
    assert (
        "[pipeline_alert] no usable keys in" in both
        and "NOT delivered (ALERT_ENABLED=0 is set)" in both
    ), both
    # the DIAGNOSIS failing must read as `reason unavailable`, never as the send failing (FD6) —
    # ungraded until B65-5 (FF1): the copied package's `_is_enabled` raises only when the helper's
    # own top-level diagnosis calls it, never from inside `send_alert`
    init = root / "libs" / "alerting" / "__init__.py"
    init.write_text(
        init.read_text(encoding="utf-8")
        + "\n_real_is_enabled = _is_enabled\n\n\ndef _is_enabled():\n    import sys as _s\n\n    if _s._getframe(1).f_code.co_name == '<module>':\n        raise RuntimeError('diagnosis broken')\n    return _real_is_enabled()\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(helper), "t5b", "b"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    both = proc.stdout + proc.stderr
    assert "NOT delivered (reason unavailable): t5b" in both and "send failed" not in both, both
    shutil.rmtree(root / "libs" / "alerting")
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    (root / ".venv").unlink()
    (root / ".venv" / "bin" / "python").mkdir(
        parents=True
    )  # a directory at the interpreter path passes `-x`
    proc = subprocess.run(
        ["bash", str(helper), "t6", "b"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    both = proc.stdout + proc.stderr
    assert "NOT delivered (no interpreter at" in both and "Is a directory" not in both, both
    assert proc.returncode == 0


def test_the_chain_cwd_and_the_daily_export_are_executed_not_spelled(tmp_path):
    """`cd "$FABRIK_ROOT"` and `export FABRIK_ROOT` were pinned as substrings only — commenting
    either out with the substring kept stayed green (M-C3, FE6)."""
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    head = text[: text.index("VENV_PY=")]
    proc = subprocess.run(
        ["bash", "-c", head + "\npwd"],
        env={"PATH": os.environ["PATH"], "FABRIK_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0 and proc.stdout.strip() == str(tmp_path.resolve()), (
        proc.stdout,
        proc.stderr,
    )
    daily = (REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").read_text(encoding="utf-8")
    dhead = daily[daily.index("set -u") : daily.index("LOG_FILE=")]
    proc = subprocess.run(
        ["bash", "-c", dhead + "\nbash -c 'echo \"${FABRIK_ROOT:-unset}\"'"],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "/opt/fabrik", (
        proc.stdout,
        proc.stderr,
    )  # a CHILD process sees it: exported, not merely assigned
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    i = hook.index("pipeline log unwritable")
    assert '>>"$LOG_FILE" 2>&1 & )' in hook[i : i + 900], (
        "the unwritable-log alert's diagnostics reach the re-pointed log (positive pin, not the absence of one literal)"
    )


def test_the_freshness_checker_says_a_non_delivery_and_never_autoloads_the_cwd_env(tmp_path):
    """Both legs returned `bool(send_alert(...))` and said NOTHING on False — the one alert for
    "the pipeline stopped running" was a silent no-op whenever alerting was disabled; the boot hook
    ran it from /opt/session-recall, where the package's cwd autoload read THAT repo's .env; an
    unreadable selection doc was "missing", a non-alert status (M-C1/C2/C6, FE6).

    ⚠ The checker loads ITS OWN repo's `.env` by design (`SCRIPT_DIR.parents[1] / ".env"`), so it
    runs here from a THROWAWAY copy of the tree with no `.env` at all — the first draft of this
    grader ran the real script and DELIVERED two real Telegram alerts (disclosed, FE6)."""
    import shutil

    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "kilo-benchmarks" / "check_daily_refresh_freshness.py",
        root / "scripts" / "kilo-benchmarks",
    )
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    assert not (root / ".env").exists()
    checker = root / "scripts" / "kilo-benchmarks" / "check_daily_refresh_freshness.py"
    stamp = tmp_path / "stamp.txt"
    stamp.write_text("2020-01-01T00:00:00+00:00\n", encoding="utf-8")
    doc = tmp_path / "SELECTION.md"
    doc.write_text("Last refresh: 2020-01-01\n", encoding="utf-8")
    cwd = tmp_path / "other-repo"
    cwd.mkdir()
    (cwd / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=canary-not-a-real-token\nTELEGRAM_CHAT_ID=1\nALERT_VPS_HOST=nowhere.invalid\n",
        encoding="utf-8",
    )
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env["ALERT_ENABLED"] = "0"
    args = [
        sys.executable,
        str(checker),
        "--timestamp-file",
        str(stamp),
        "--selection-doc",
        str(doc),
    ]
    proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert (
        "[heartbeat] alert NOT delivered (ALERT_ENABLED=0 is set): kilo-benchmarks daily refresh is stale"
        in proc.stderr
    ), proc.stderr
    assert (
        "[heartbeat] alert NOT delivered (ALERT_ENABLED=0 is set): TASK_SUBAGENT_SELECTION.md is stale"
        in proc.stderr
    ), proc.stderr
    env.pop(
        "ALERT_ENABLED"
    )  # the throwaway root has no .env: only the cwd canary could arm alerting — and it must not
    proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    assert (
        "alert fired" not in proc.stdout
        and "alerting disabled — no TELEGRAM_*/ALERT_VPS_HOST" in proc.stderr
    ), (
        "the cwd's canary .env was autoloaded — the checker must opt out of the package's cwd autoload",
        proc.stdout,
        proc.stderr,
    )
    doc.chmod(0)
    try:
        if os.access(doc, os.R_OK):
            pytest.skip("running as root — permissions are not enforced")
        env["ALERT_ENABLED"] = "0"
        proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
        assert (
            "selection doc: unreadable" in proc.stdout
            and "TASK_SUBAGENT_SELECTION.md is unreadable" in proc.stderr
        ), (proc.stdout, proc.stderr)
    finally:
        doc.chmod(0o644)
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    assert "( cd /opt/session-recall && timeout 600 .venv/bin/python -m ingest.reindex )" in hook, (
        "the session-recall step runs in a SUBSHELL so its cd never leaks"
    )


def test_the_root_conftest_mutes_alerting_for_every_child(monkeypatch):
    """504 of 526 spawns inherit the parent environment; the hub's `.env` arms delivery — two graders
    DELIVERED real alerts (FC6, FE6). The root conftest mutes the test process itself, so every
    child inherits silence; a test that needs "armed" un-mutes itself (B65-9, FF1)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_root_conftest", REPO / "conftest.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setenv("ALERT_ENABLED", "1")
    monkeypatch.setenv("FABRIK_NO_AUTOLOAD", "0")
    spec.loader.exec_module(mod)  # importing it mutes — the module runs the mute at import
    assert os.environ["ALERT_ENABLED"] == "0" and os.environ["FABRIK_NO_AUTOLOAD"] == "1"
    monkeypatch.setenv("ALERT_ENABLED", "1")
    mod.mute_alerting()
    assert os.environ["ALERT_ENABLED"] == "0"
    proc = subprocess.run(  # env=None: the child inherits the muted parent
        [sys.executable, "-c", "import os; print(os.environ.get('ALERT_ENABLED'))"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "0"
    proc = subprocess.run(  # an EXPLICIT env cannot inherit it: 16 of 631 spawns carried no mute (B67-9) — every hand-built env MUST carry the two keys itself
        [sys.executable, "-c", "import os; print(os.environ.get('ALERT_ENABLED'))"],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip() == "None", "documented: the conftest reaches env=None children only"
    src = Path(__file__).read_text(encoding="utf-8")
    hand_built = [
        m.start() for m in re.finditer(r"\n    env = \{k: os\.environ\[k\] for k in", src)
    ]
    for pos in hand_built:
        assert '"ALERT_ENABLED": "0"' in src[pos : pos + 400], src[pos : pos + 200]


def test_the_dashboard_modules_insert_their_directory_once():
    """`gen_dashboard.py` inserted `scripts/` on every load — 7 → 24 entries over this suite, the class
    FD8 guarded at two other sites (B65-7, FF1); it now also needs `scripts/sysadmin` (the page layer)
    and must hold both once, and never import the board's own module (it runs as `__main__`)."""
    import importlib.util

    scripts = str(REPO / "scripts")
    sysadmin = str(REPO / "scripts" / "sysadmin")
    before = list(sys.path)
    try:
        for _ in range(2):
            _load_gen_dashboard()
        for name in (
            "classify_services",
            "registry_sync",
        ):  # the other two round-66 modules: unguarded at 2 of 4 sites (B67-8)
            for _ in range(2):
                spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
        assert sys.path.count(scripts) == max(1, before.count(scripts)), sys.path[:6]
        assert sys.path.count(sysadmin) == max(1, before.count(sysadmin)), sys.path[:6]
        assert sys.path.count(str(REPO)) == max(1, before.count(str(REPO))), sys.path[:6]
    finally:
        sys.path[:] = before
        for name in ("classify_services", "registry_sync"):
            sys.modules.pop(name, None)
    # a fresh interpreter: both directories exactly once, and the board's module never imported
    gen = str(REPO / "scripts" / "gen_dashboard.py")
    probe = (
        "import sys, importlib.util as u\n"
        f"sys.path[:] = [p for p in sys.path if p not in ({scripts!r}, {sysadmin!r})]\n"
        f"sp = u.spec_from_file_location('gen_dashboard', {gen!r})\n"
        "m = u.module_from_spec(sp); sys.modules['gen_dashboard'] = m\n"
        "sp.loader.exec_module(m); sp.loader.exec_module(m)\n"
        f"print(sys.path.count({scripts!r}), sys.path.count({sysadmin!r}), 'quota_dashboard' in sys.modules)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=60, check=True
    ).stdout.split()
    assert out == ["1", "1", "False"], out


def test_a_venv_without_python_dotenv_reads_the_env_file_through_the_stdlib_loader(tmp_path):
    """FE6 gave the helper and the chain the package's stdlib loader; the checker kept
    `except ImportError: pass` and blamed missing tokens; none of the three fallbacks had a grader
    (M-C2, M-C6b, B65-5, FF1). A shadow `dotenv.py` in each script's own import path raises
    ImportError; the throwaway `.env` carries ONLY the mute, so nothing can arm."""
    root = tmp_path / "root"
    kb = root / "scripts" / "kilo-benchmarks"
    kb.mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    (root / ".env").write_text("ALERT_ENABLED=0\n", encoding="utf-8")
    shadow = "raise ImportError('python-dotenv is not installed in this venv')\n"
    (kb / "dotenv.py").write_text(shadow, encoding="utf-8")
    (root / "dotenv.py").write_text(
        shadow, encoding="utf-8"
    )  # the helper and the chain run their python with cwd = root, and '' leads their sys.path
    (root / ".venv").symlink_to(VENV, target_is_directory=True)
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env["FABRIK_ROOT"] = str(root)
    env["FABRIK_NO_AUTOLOAD"] = "1"
    env.pop("ALERT_ENABLED", None)
    # the checker
    shutil.copy(REPO / "scripts" / "kilo-benchmarks" / "check_daily_refresh_freshness.py", kb)
    stamp = tmp_path / "stamp.txt"
    stamp.write_text("2020-01-01T00:00:00+00:00\n", encoding="utf-8")
    doc = tmp_path / "SELECTION.md"
    doc.write_text("Last refresh: 2020-01-01\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(kb / "check_daily_refresh_freshness.py"),
            "--timestamp-file",
            str(stamp),
            "--selection-doc",
            str(doc),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, (proc.stdout, proc.stderr)
    assert proc.stderr.count("alert NOT delivered (ALERT_ENABLED=0 is set)") == 2, proc.stderr
    # the helper
    proc = subprocess.run(
        ["bash", str(REPO / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"), "t-dotenv", "b"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    both = proc.stdout + proc.stderr
    assert "[pipeline_alert] .env not loaded: ImportError" in both, both
    assert "NOT delivered (ALERT_ENABLED=0 is set): t-dotenv" in both, both
    # the chain's own `_alert`
    text = (REPO / "scripts" / "external_services_chain.sh").read_text(encoding="utf-8")
    fn = text[text.index("_alert() {") : text.index("_step() {")]
    harness = tmp_path / "h.sh"
    harness.write_text(
        f'FABRIK_ROOT="{root}"\nVENV_PY="{sys.executable}"\n'
        + fn
        + '\n_alert "t-chain" "b" warning\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(harness)], cwd=root, env=env, capture_output=True, text=True, timeout=60
    )
    assert "[chain] .env not loaded: ImportError" in proc.stdout, (proc.stdout, proc.stderr)
    assert "alert NOT delivered (ALERT_ENABLED=0 is set): t-chain" in proc.stdout, proc.stdout


def test_an_unreadable_parent_directory_is_a_typed_status_on_both_checker_legs(tmp_path):
    """`Path.exists()` raises EACCES on an unreadable PARENT (pathlib swallows only
    ENOENT/ENOTDIR/EBADF/ELOOP): the doc leg died with a traceback and the stamp leg took both
    legs down as `check failed` — no typed line, no alert (M-C3, FF1)."""
    root = tmp_path / "root"
    kb = root / "scripts" / "kilo-benchmarks"
    kb.mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "kilo-benchmarks" / "check_daily_refresh_freshness.py", kb)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    stamp_dir, doc_dir = tmp_path / "sd", tmp_path / "dd"
    stamp_dir.mkdir()
    doc_dir.mkdir()
    (stamp_dir / "stamp.txt").write_text("2020-01-01T00:00:00+00:00\n", encoding="utf-8")
    (doc_dir / "SELECTION.md").write_text("Last refresh: 2020-01-01\n", encoding="utf-8")
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env.update({"ALERT_ENABLED": "0", "FABRIK_NO_AUTOLOAD": "1"})
    args = [
        sys.executable,
        str(kb / "check_daily_refresh_freshness.py"),
        "--timestamp-file",
        str(stamp_dir / "stamp.txt"),
        "--selection-doc",
        str(doc_dir / "SELECTION.md"),
    ]
    doc_dir.chmod(0)
    try:
        if os.access(doc_dir / "SELECTION.md", os.R_OK):
            pytest.skip("running as root — permissions are not enforced")
        proc = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=120)
        assert "Traceback" not in proc.stderr and proc.returncode == 0, (proc.stdout, proc.stderr)
        assert "selection doc: unreadable" in proc.stdout, proc.stdout
        assert "TASK_SUBAGENT_SELECTION.md is unreadable" in proc.stderr, proc.stderr
    finally:
        doc_dir.chmod(0o755)
    stamp_dir.chmod(0)
    try:
        proc = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=120)
        assert "Traceback" not in proc.stderr and "check failed" not in proc.stdout, (
            proc.stdout,
            proc.stderr,
        )
        assert "[heartbeat] UNREADABLE (PermissionError" in proc.stdout, proc.stdout
        assert "kilo-benchmarks daily refresh heartbeat is unreadable" in proc.stderr, proc.stderr
        assert "FIRST RUN" not in proc.stdout  # an unreadable stamp is never a quiet first run
    finally:
        stamp_dir.chmod(0o755)
    (stamp_dir / "stamp.txt").chmod(
        0
    )  # the FILE itself (parent readable): `read_text` raised and read as first_run before FF3 — this leg was ungraded (M67-C4)
    try:
        proc = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=120)
        assert "[heartbeat] UNREADABLE (PermissionError" in proc.stdout, proc.stdout
        assert "heartbeat is unreadable" in proc.stderr and "FIRST RUN" not in proc.stdout, (
            proc.stdout,
            proc.stderr,
        )
    finally:
        (stamp_dir / "stamp.txt").chmod(0o644)


def test_the_hook_finishes_a_stranded_rotation_before_it_starts_the_next(tmp_path):
    """A REGULAR `.1.new` is the live log a previous rotation stranded; the plain `mv -T` then
    overwrote it — a generation lost with no line, the FE4 say-it fix printed once to a login
    shell (M-C4, FF1)."""
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    start = hook.index("        # promote .1")
    snippet = hook[start : hook.index("        fi\n", start) + 11]
    log = tmp_path / "update.log"
    log.write_text("LIVE\n")
    (tmp_path / "update.log.1.new").write_text("STRANDED\n")
    (tmp_path / "update.log.1").write_text("GEN1\n")
    (tmp_path / "update.log.2").write_text("GEN0\n")
    proc = subprocess.run(
        ["bash", "-c", f'logfile="{log}"\n{snippet}'], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    assert (tmp_path / "update.log.1").read_text() == "LIVE\n"
    assert (tmp_path / "update.log.2").read_text() == "STRANDED\n", (
        "the stranded live log is the NEWER generation — it is kept, the oldest goes"
    )
    assert not (tmp_path / "update.log.1.new").exists()


def test_the_hooks_heartbeat_write_failure_alerts_like_daily_refreshs(tmp_path):
    """daily_refresh alerts a failed heartbeat write; the boot path only echoed it and relied on
    the next freshness check — which M-C2/M-C3 show could itself be mute (M-C8, FF1)."""
    root = tmp_path / "root"
    kb = root / "scripts" / "kilo-benchmarks"
    (kb / "cache").mkdir(parents=True)
    stub = kb / "pipeline_alert.sh"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf \'%s|%s\\n\' "$1" "$2" >> "$ALERTS"\n', encoding="utf-8"
    )
    alerts, log = tmp_path / "alerts.txt", tmp_path / "log.txt"
    alerts.write_text("", encoding="utf-8")
    log.write_text("", encoding="utf-8")
    block = (
        _caller_block(
            HOOK.read_text(encoding="utf-8"),
            '        [ \\"$LOG_FILE\\" = /dev/null ] ||',
            "        echo '=== Pipeline complete",
        )
        .replace("\\$", "$")
        .replace('\\"', '"')
    )
    assert "heartbeat timestamp write FAILED" in block, block
    harness = tmp_path / "h.sh"
    harness.write_text(
        f'FABRIK_ROOT="{root}"\nLOG_FILE="{log}"\nexport ALERTS="{alerts}"\n' + block + "\n",
        encoding="utf-8",
    )
    (kb / "cache").chmod(0o555)
    try:
        if os.access(kb / "cache", os.W_OK):
            pytest.skip("running as root — permissions are not enforced")
        proc = subprocess.run(["bash", str(harness)], capture_output=True, text=True, timeout=60)
    finally:
        (kb / "cache").chmod(0o755)
    assert "heartbeat timestamp write FAILED" in alerts.read_text(encoding="utf-8"), (
        proc.stdout,
        proc.stderr,
        log.read_text(encoding="utf-8"),
    )
    assert "heartbeat write FAILED" in log.read_text(encoding="utf-8")
    assert proc.stderr == "", (
        proc.stderr
    )  # `> file 2>/dev/null` failed BEFORE fd 2 moved: `Permission denied` went to the login shell's nohup.out (M67-C2, FG1)


def test_the_curated_env_loader_carries_every_key_the_alerting_package_reads():
    """`ALERT_APPRISE_CONTAINER` is read by apprise.py and was not in the stdlib loader's curated
    list — under the fallback a non-default container name was dropped (M-C9, FF1)."""
    sys.path.insert(0, str(REPO / "libs"))
    before_mods = set(sys.modules)
    try:
        from alerting._dotenv import DOTENV_KEYS
    finally:
        sys.path.remove(str(REPO / "libs"))
        for k in [
            k
            for k in sys.modules
            if (k == "alerting" or k.startswith("alerting.")) and k not in before_mods
        ]:
            del sys.modules[
                k
            ]  # the B65-8 leak class, reintroduced by this round-66 grader (B67-10)
    read = set()
    for py in (REPO / "libs" / "alerting").glob("*.py"):
        read.update(
            re.findall(
                r"""(?:getenv|environ\.get|environ)\(?\[?['"]((?:ALERT|TELEGRAM)_[A-Z0-9_]+)['"]""",  # every read shape and a digit in a key name (B67-6)
                py.read_text(encoding="utf-8"),
            )  # every read shape, not only double-quoted getenv (M67-C9)
        )
    assert read and read <= set(DOTENV_KEYS), sorted(read - set(DOTENV_KEYS))


def test_a_negative_backfilled_balance_and_an_infinite_price_render_empty(monkeypatch):
    """`_finite` refuses a negative at fetch time; a backfilled row rendered `-5 usd`. The `price`
    ±Infinity guard had no grader (G66-C13, K66-2, FF1)."""
    gd = _load_gen_dashboard()
    assert gd.credit_cell(-5.0, "usd", None) == "" and gd.credit_cell(5.0, "usd", None) == "5 usd"
    assert gd.credit_cell(0.0, "usd", None) == "0 usd", (
        "an exhausted credit is a balance, not a NULL — `bal <= 0` survived every grader (K67-3)"
    )
    from decimal import Decimal

    answers = {
        "FROM services": [("apify", "Apify", "scraping", "paid", "https://apify.com", "active")],
        "information_schema": [(1,)],
        "FROM api_keys": [],
        "credit_snapshots": [],
        "FROM subscriptions": [("apify", Decimal("Infinity"), "usd", None)],
    }

    class _Cur:
        def __init__(self):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, *a):
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
    assert rows[0]["price"] == "", rows[0]
    answers["FROM subscriptions"] = [("apify", Decimal("12.50"), "usd", None)]
    assert "12.5" in gd.load()[0]["price"]
    answers["FROM subscriptions"] = [("apify", Decimal("0"), "usd", None)]
    assert gd.load()[0]["price"] == "0 usd", (
        "a free plan declared for its renewal date is a PRICE, not a NULL — `price >= 0` survived every grader (K68-4, FH1)"
    )
    from datetime import date

    answers["FROM subscriptions"] = [
        ("apify", None, None, date(2026, 1, 1))
    ]  # a renewal declared without a price (`--price` omitted; the upsert COALESCEs) — `math.isfinite(None)` would 500 every page (K67-4)
    row = gd.load()[0]
    assert row["price"] == "" and row["renews"] == "2026-01-01", row
    answers["FROM subscriptions"] = [("apify", Decimal("-5"), "usd", None)]
    assert gd.load()[0]["price"] == "", gd.load()[0]  # a negative price is no price (K67-6)


def test_the_log_cap_never_enters_a_squatter_directory_and_ages_it_out(tmp_path):
    """`ls -1t cache/update.log.*` listed a `*.notalog.*` DIRECTORY's contents, never the directory:
    the FE4 squatters were never pruned (G66-C14, FF1). Files only; squatters go after a week."""
    import time

    daily = (REPO / "scripts" / "kilo-benchmarks" / "daily_refresh.sh").read_text(encoding="utf-8")
    start = daily.index("    # FILES only, never a `*.notalog.*` directory")
    block = daily[
        start : daily.index("    done\n", daily.index("env_watcher.log.*.notalog.*", start)) + 9
    ]
    executable = [ln for ln in block.splitlines() if not ln.lstrip().startswith("#")]
    assert block.count("find ") == 2 and not any("-mtime" in ln for ln in executable), (
        block
    )  # the squatter's age comes from the stamp in its NAME: `mv -T` keeps the renamed directory's own mtime (G67-2)
    lines = [block]
    assert not any(
        ln.lstrip().startswith("ls -1t") and "update.log" in ln for ln in daily.splitlines()
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    now = time.time()
    for i in range(5):
        p = cache / f"update.log.{i}"
        p.write_text(f"gen{i}\n")
        os.utime(p, (now - i * 100, now - i * 100))
    fresh = (
        cache / f"update.log.1.notalog.{int(now) * 1_000_000_000}"
    )  # a squatter set aside TODAY — its own mtime is 30 days old (an old operator directory)
    fresh.mkdir()
    (fresh / "inner.txt").write_text("keep\n")
    os.utime(fresh, (now - 30 * 86400, now - 30 * 86400))
    old = (
        cache / f"update.log.2.notalog.{int(now - 9 * 86400) * 1_000_000_000}"
    )  # set aside nine days ago, touched today
    old.mkdir()
    proc = subprocess.run(
        [
            "bash",
            "-c",
            f'KB="{tmp_path}"\nFABRIK_ROOT="{tmp_path}"\nmkdir -p "{tmp_path}/.tmp"\n'
            + "\n".join(lines),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
    assert sorted(p.name for p in cache.iterdir()) == [
        "update.log.0",
        "update.log.1",
        fresh.name,
        "update.log.2",
    ], sorted(p.name for p in cache.iterdir())
    assert (fresh / "inner.txt").exists()


def test_an_unreadable_hub_env_file_is_said_by_the_checker_and_both_legs_still_run(tmp_path):
    """With python-dotenv PRESENT, an unreadable hub `.env` (a lost permission bit) raised out of
    `load_dotenv` at import: one traceback in a log nobody tails, both legs silent — the helper
    and the chain say it and fall through to the stdlib loader; the checker's `.env` leg was
    never swept (M67-C1, FG1)."""
    root = tmp_path / "root"
    kb = root / "scripts" / "kilo-benchmarks"
    kb.mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "kilo-benchmarks" / "check_daily_refresh_freshness.py", kb)
    shutil.copytree(REPO / "libs" / "alerting", root / "libs" / "alerting")
    (root / ".env").write_text("ALERT_ENABLED=0\n", encoding="utf-8")
    (root / ".env").chmod(0)
    if os.access(root / ".env", os.R_OK):
        pytest.skip("running as root — permissions are not enforced")
    stamp = tmp_path / "stamp.txt"
    stamp.write_text("2020-01-01T00:00:00+00:00\n", encoding="utf-8")
    doc = tmp_path / "SELECTION.md"
    doc.write_text("Last refresh: 2020-01-01\n", encoding="utf-8")
    env = {
        k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ
    }
    env.update({"ALERT_ENABLED": "0", "FABRIK_NO_AUTOLOAD": "1"})
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(kb / "check_daily_refresh_freshness.py"),
                "--timestamp-file",
                str(stamp),
                "--selection-doc",
                str(doc),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        (root / ".env").chmod(0o644)
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, (proc.stdout, proc.stderr)
    assert "[heartbeat] .env not loaded: PermissionError" in proc.stderr, proc.stderr
    assert proc.stderr.count("alert NOT delivered (ALERT_ENABLED=0 is set)") == 2, proc.stderr


def test_the_killed_class_boundaries_are_executed_in_both_callers(tmp_path):
    """The 129–192 class was graded by a substring pin only: `128|129|…` survives the pin. Both
    callers' `case` blocks are EXECUTED at 124/125/128/193/255 (the generic line, no alert) and
    at 129/192 (KILLED, the signal named) (M67-C5, FG1)."""
    root = tmp_path / "root"
    (root / "scripts" / "kilo-benchmarks").mkdir(parents=True)
    stub = root / "scripts" / "kilo-benchmarks" / "pipeline_alert.sh"
    stub.write_text(
        '#!/usr/bin/env bash\nprintf \'%s|%s\\n\' "$1" "$2" >> "$ALERTS"\n', encoding="utf-8"
    )
    chain = root / "scripts" / "external_services_chain.sh"
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
    for code, killed, signal in (
        (124, False, None),
        (125, False, None),
        (128, False, None),
        (129, True, 1),
        (192, True, 64),
        (193, False, None),
        (255, False, None),
    ):
        chain.write_text(f"#!/usr/bin/env bash\nexit {code}\n", encoding="utf-8")
        for name, block in (("daily_refresh", daily_block), ("wsl_startup_hook", hook_block)):
            alerts.write_text("", encoding="utf-8")
            log.write_text("", encoding="utf-8")
            harness = tmp_path / f"{name}.sh"
            harness.write_text(
                'set -u\n_step() { local label="$1"; shift; "$@"; }\n'
                f'FABRIK_ROOT="{root}"\nKB="{root}/scripts/kilo-benchmarks"\nLOG_FILE="{log}"\nexport ALERTS="{alerts}"\n'
                + block
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["bash", str(harness)], capture_output=True, text=True, timeout=60
            )
            body = alerts.read_text(encoding="utf-8")
            out = proc.stdout + proc.stderr + log.read_text(encoding="utf-8")
            if killed:
                assert "was KILLED" in body and f"signal {signal}" in body, (code, name, body)
            else:
                assert body == "" and f"exit {code}" in out, (code, name, body, out)


def test_two_squatters_of_one_generation_inside_a_second_get_distinct_names(tmp_path):
    """`notalog.$(date +%s)` collided inside one second: the second `mv -T` onto an existing
    directory failed silently and the rotation was skipped that lap; the nanosecond suffix (FF9)
    was ungraded (M67-C6, FG1)."""
    hook = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    start = hook.index("        # promote .1")
    snippet = hook[start : hook.index("        fi\n", start) + 11]
    log = tmp_path / "update.log"
    for i in range(3):
        log.write_text(f"LIVE{i}\n")
        if (tmp_path / "update.log.1").is_file():
            (
                tmp_path / "update.log.1"
            ).unlink()  # the previous lap promoted the live log there; a fresh squatter takes its place
        (tmp_path / "update.log.1").mkdir()
        proc = subprocess.run(
            ["bash", "-c", f'logfile="{log}"\n{snippet}'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0 and proc.stderr == "", (proc.stdout, proc.stderr)
        assert (tmp_path / "update.log.1").read_text() == f"LIVE{i}\n"
    squatters = [p.name for p in tmp_path.iterdir() if ".notalog." in p.name]
    assert len(squatters) == 3 and len(set(squatters)) == 3, squatters


def test_the_boot_hooks_nohup_carries_its_own_redirect():
    """`nohup bash -c "…" &` with no redirect prints `nohup: appending output to 'nohup.out'` to the
    operator's terminal and mints that file in whatever cwd the login shell sat in — the D5/FC6
    stray-nohup.out class at the one site the redirect sweep missed. Every line INSIDE the string
    already redirects to `$LOG_FILE` (0 of 38 output-producing lines lack one; the 8 without are
    `if`/`fi`/`case`/`esac`/subshell delimiters), so nohup has nothing left to save.

    Source-shaped by necessity: nohup only creates the file when its stdout is a TTY, so an
    executed twin needs a pty — the shape is what the fix is (S-3, FH7)."""
    hook = HOOK.read_text(encoding="utf-8")
    start = hook.index('nohup bash -c "')
    m = re.search(r'\n    "[^\n]*', hook[start:])  # LOCATE the terminator generically, then assert
    assert m, "the nohup string has no closing line"  # its shape — searching for the shape and
    tail = m.group(0).strip()  # asserting it is present proves nothing
    assert tail == '" >/dev/null 2>&1 &', (
        f"the nohup invocation must carry its own redirect, found: {tail!r}"
    )
    assert hook.count('nohup bash -c "') == 1, "one nohup site — a second would need the same"
    block = hook[start : start + m.start()]
    writers = [
        ln
        for ln in block.splitlines()[1:]
        if ln.strip()
        and not ln.strip().startswith("#")
        and ">" not in ln
        and ln.strip() not in ("(", ")", "fi", "esac", "do", "done", "else", "then", "{", "}")
        and not ln.strip().startswith(("if ", "case ", "for ", "while ", "elif ", "until "))
    ]
    assert writers == [], (
        f"a line inside the nohup string writes with no redirect of its own: {writers[:3]}"
    )


# ---------------------------------------------------------------- the static file (W-3e9e2f4c, T03)
@pytest.fixture
def pinned_zone():
    """TZ pinned for the test and restored after: the document prints a zone offset."""
    import time

    old = os.environ.get("TZ")
    os.environ["TZ"] = "Etc/GMT-3"  # POSIX sign: this is UTC+03:00
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


_SYNCED = 1_792_236_600.0  # 2026-10-17 11:30 UTC = 14:30 at +03:00
_NOW = _SYNCED + 3600


_NAMES = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
]
_COSTS = [
    "paid",
    "freemium",
    "free",
    "?",
    "paid",
    "freemium",
    "paid",
    "free",
    "self-host",
    "free",
    "self-host",
    "?",
    "paid",
]
_CATS = ["?"] * 4 + ["ai", "ai", "infra", "infra", "data", "mail", "maps", "pay", "vcs"]


def _fixture_rows() -> list[dict]:
    """Thirteen rows whose twelve counted stats are twelve DIFFERENT numbers, so a stat that reads
    another stat's formula cannot pass: total 13 · paid or freemium 6 · free or self-host 5 · untriaged 4
    · categories 7 · projects 12 · credit tracked 9 · credit stale 1 · renewals set 10 · with credentials
    11 · unattributed keys 2 · needing attention 3 (india stale credit, echo unattributed, golf retiring)."""
    rows = []
    for i, name in enumerate(_NAMES):
        r = _row(
            name,
            category=_CATS[i],
            cost=_COSTS[i],
            url=f"https://{name}.test",
            keys=0 if i in (0, 12) else 1,
            projects=[f"p{i:02d}"] if i else [],
            renews=f"2026-11-0{i % 9 + 1}" if i >= 3 else "",
        )
        if 2 <= i <= 11:
            rows_balance = 3.0 if name == "india" else float(i)
            r.update(
                balance=rows_balance,
                unit="usd",
                credit_at=_NOW - (5 * 86400 if name == "india" else 3600),
            )
        rows.append(r)
    by = {r["provider"]: r for r in rows}
    by["echo"].update(unattributed=2)
    by["golf"].update(status="retiring")
    by["juliet"].update(
        balance=12.5, account="me@x.test", price="10 usd", renews="2026-12-01", projects=["p09"]
    )
    return rows


_DOC_PROBLEMS = (
    r"\bsrc\s*=",
    r"<script",
    r"<link",
    r"<iframe",
    r"@import",
    r"\burl\s*\(",
    r"javascript:",
)


def _document_problems(page: str) -> list[str]:
    """Everything that makes a file not self-contained, whatever the quoting."""
    found = [pat for pat in _DOC_PROBLEMS if re.search(pat, page, re.I)]
    for m in re.finditer(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", page, re.I):
        target = next(g for g in m.groups() if g is not None)
        if not re.match(r"https?://", target, re.I):
            found.append(f"href={target!r}")
    return found


def test_the_static_file_is_a_scriptless_self_contained_document(pinned_zone):
    gd = _load_gen_dashboard()
    page = gd.render(_fixture_rows(), synced_at=_SYNCED, now=_NOW)
    assert page.startswith('<!doctype html>\n<html lang="en">')
    assert "<title>External services</title>" in page and "<h1>External services</h1>" in page
    assert 'name="viewport"' in page
    assert _document_problems(page) == []
    assert page.count("href=") >= 13, "every provider links"
    assert (
        "--c-slate-900" in page
        and (gd.dashboard_ui.STATIC_DIR / "app.css").read_text(encoding="utf-8") in page
    ), "app.css is inlined whole"
    assert "Registry synced 2026-10-17 14:30 +03:00" in page
    assert "Snapshot written 2026-10-17 15:30 +03:00" in page
    never = gd.render(_fixture_rows(), synced_at=None, now=_NOW)
    assert "Registry never synced" in never and "Registry synced" not in never


# each guard pattern -> a shape ONLY that pattern flags (no href, no src, no other token beside it)
_ONLY_THIS = {
    r"\bsrc\s*=": '<img SRC="https://x.test/a.png">',
    r"<script": "<SCRIPT>1</SCRIPT>",
    r"<link": '<LINK rel="stylesheet" href="https://cdn.test/x.css">',
    r"<iframe": "<IFRAME></IFRAME>",
    r"@import": "<style>@IMPORT 'x.css';</style>",
    r"\burl\s*\(": "<style>a{background:URL (x.png)}</style>",
    r"javascript:": "<p>JavaScript:void(0)</p>",
}
_BAD_HREFS = {
    "<a href=ftp://x>x</a>": "ftp://x",
    '<a HREF = "/relative">x</a>': "/relative",
    '<a href="//host.test/x">x</a>': "//host.test/x",
    "<a href=x.html>x</a>": "x.html",
}


def test_the_self_containment_check_sees_every_shape_it_guards():
    clean = '<a href="https://x.test">x</a><a href=http://y.test>y</a>'
    assert _document_problems(clean) == []
    assert set(_ONLY_THIS) == set(_DOC_PROBLEMS), "every guard pattern owns a shape"
    for pattern, shape in _ONLY_THIS.items():
        assert _document_problems(shape) == [pattern], (pattern, shape)
    both = _document_problems("<a href='javascript:alert(1)'>x</a>")
    assert both == [r"javascript:", "href='javascript:alert(1)'"], both
    for shape, target in _BAD_HREFS.items():
        assert _document_problems(shape) == [f"href={target!r}"], shape


def test_the_section_prints_each_stamp_and_the_legend_exactly_once(pinned_zone):
    gd = _load_gen_dashboard()
    page = gd.render(_fixture_rows(), synced_at=_SYNCED, now=_NOW)
    assert page.count("Registry synced") == 1 and page.count("Snapshot written") == 1
    assert page.count("No secret values") == 1 and page.count("<h1") == 1
    assert page.rstrip().endswith("</html>") and page.index("No secret values") > page.index(
        "Registry synced"
    )


def _table_row(page: str, name: str) -> tuple[str, list[str]]:
    """The provider's own ``<tr>``: its name cell (with the detail block) and its other cells."""
    rows = [r for r in re.findall(r"<tr>(.*?)</tr>", page, re.S) if f"{name}</a>" in r]
    assert len(rows) == 1, (name, len(rows))
    head, _, rest = rows[0].partition("</th>")
    return head, re.findall(r"<td[^>]*>(.*?)</td>", rest, re.S)


def test_every_one_of_todays_ten_stats_and_columns_has_its_home(pinned_zone):
    gd = _load_gen_dashboard()
    page = gd.render(_fixture_rows(), synced_at=_SYNCED, now=_NOW)
    summary = dict(re.findall(r'<li data-count="(\w+)">[^<]*?(\d+)</li>', page))
    assert summary == {
        "attention": "3",
        "paid": "6",
        "free": "5",
        "untriaged": "4",
        "total": "13",
    }, summary
    more = {
        n: _count(page, n)
        for n in (
            "categories",
            "projects",
            "credit_tracked",
            "credit_stale",
            "renewals",
            "credentials",
            "unattributed",
        )
    }
    assert more == {
        "categories": "7",
        "projects": "12",
        "credit_tracked": "9",
        "credit_stale": "1",
        "renewals": "10",
        "credentials": "11",
        "unattributed": "2",
    }, more
    everything = {**summary, **more}
    assert len(set(everything.values())) == len(everything), "every stat has its own number"
    for col in ("Provider", "Cost", "Status", "Keys", "Funding", "Used by"):
        assert '<th scope="col"' in page and f">{col}</th>" in page, col
    assert re.search(r"<summary>ai · 2 providers[^<]*</summary>", page)  # Category: its table
    # one row, read inside its own cells: cost · status · keys · funding · used by
    head, cells = _table_row(page, "juliet")
    assert 'href="https://juliet.test"' in head
    assert cells[0] == "Free" and cells[1] == "Active" and cells[2] == "1"
    assert cells[3] == "12.5 usd" and cells[4] == "p09", cells
    for detail in (  # Account, Price, Renews and Used by: the row's own detail block
        "Account: me@x.test",
        "Price: 10 usd",
        "Renewal: 2026-12-01",
        "Used by: p09",
    ):
        assert f"<li>{detail}</li>" in head, detail
    assert _table_row(page, "india")[1][3] == "⚠ 3 usd (5d old)"  # a stale credit, in Funding
    assert "Retiring" in _table_row(page, "golf")[1][1]  # Status
    keys = _table_row(page, "echo")[1][2]
    assert keys.startswith("1 ") and "2 unattributed" in keys, keys  # Keys + unattributed
    # the untriaged queue entry keeps its link, key count and projects, in its own list item
    entry = next(
        li.split("</li>")[0] for li in page.split("<li") if "bravo" in li and "href=" in li
    )
    assert 'href="https://bravo.test"' in entry and "1 key" in entry, entry
    assert "Used by: p01" in entry, entry
    assert "No secret values, a credential count only. ⚠ credit = older than 48 h." in page


def test_the_reader_closes_its_connection_on_both_paths(monkeypatch):
    gd = _load_gen_dashboard()
    closed: list[bool] = []

    class _Conn:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(gd.registry_db, "connect", lambda: _Conn())
    monkeypatch.setattr(gd.inventory, "load", lambda conn: ([{"provider": "x"}], 5.0))
    assert gd._read()[0] == [{"provider": "x"}] and closed == [True]
    assert gd.load() == [{"provider": "x"}] and closed == [True, True]

    def boom(conn):
        raise RuntimeError("query failed")

    monkeypatch.setattr(gd.inventory, "load", boom)
    with pytest.raises(RuntimeError):
        gd._read()
    assert closed == [True, True, True]


def test_the_static_file_reads_no_classifier_stamp():
    """D-1046 retired the classifier's source rule: gen_dashboard no longer stats
    classify_last.json, and the section takes no classifier time (a caller still passing one is
    a TypeError, never a silently ignored argument)."""
    gd = _load_gen_dashboard()
    assert not hasattr(gd, "_classified_at") and not hasattr(gd, "CLASSIFY_STAMP")
    with pytest.raises(TypeError):
        gd.render([], synced_at=_SYNCED, classified_at=_NOW, now=_NOW)


def test_a_render_that_raises_leaves_the_previous_file_and_one_typed_line(
    monkeypatch, capsys, tmp_path
):
    gd = _load_gen_dashboard()
    out = tmp_path / "dash.html"
    out.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(gd, "_read", lambda: ([_row("a")], None))

    def boom(rows, **kw):
        raise ValueError("cannot render")

    monkeypatch.setattr(gd, "render", boom)
    assert gd.main([str(out)]) == 1
    printed = capsys.readouterr().out
    assert printed.count("\n") == 1 and "ERROR: registry unreadable" in printed
    assert out.read_text(encoding="utf-8") == "previous"
    monkeypatch.setattr(gd, "_read", lambda: (_ for _ in ()).throw(RuntimeError("dead")))
    assert gd.main([str(out)]) == 1 and out.read_text(encoding="utf-8") == "previous"


def test_main_writes_the_whole_document_through_the_real_renderer(monkeypatch, tmp_path):
    gd = _load_gen_dashboard()
    monkeypatch.setattr(gd, "_read", lambda: (_fixture_rows(), _SYNCED))
    out = tmp_path / "dash.html"
    assert gd.main([str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert "alpha" in page and "Registry synced" in page and "<script" not in page


_RETIRED_NAME = re.compile(r"(?<![A-Za-z0-9_])dashboard_server(?![A-Za-z0-9_])")


def _naming_the_retired_server(roots: list[Path], skip: Path) -> list[str]:
    """Every file under ``roots`` that names the module `dashboard_server` as a word (the board's own
    `quota_dashboard_server` stem is a different word and does not match)."""
    hits = []
    for root in roots:
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f == skip or "__pycache__" in f.parts:
                continue
            if _RETIRED_NAME.search(f.read_bytes().decode("utf-8", errors="replace")):
                hits.append(str(f))
    return hits


def test_the_retirement_scan_finds_a_real_hit_and_skips_only_the_named_file(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("import dashboard_server\n", encoding="utf-8")
    (tmp_path / "scripts" / "b.sh").write_text("python scripts/dashboard_server.py\n")
    (tmp_path / "scripts" / "c.js").write_text("require('./dashboard_server')\n")
    (tmp_path / "scripts" / "d.sql").write_text("-- dashboard_server\n")
    (tmp_path / "scripts" / "launcher").write_text("exec dashboard_server\n")  # no suffix at all
    (tmp_path / "scripts" / "__pycache__").mkdir()
    (tmp_path / "scripts" / "__pycache__" / "x.py").write_text("dashboard_server\n")
    (tmp_path / "tests" / "test_quota_dashboard_server.py").write_text("quota_dashboard_server\n")
    mine = tmp_path / "tests" / "me.py"
    mine.write_text("dashboard_server\n", encoding="utf-8")
    roots = [tmp_path / "scripts", tmp_path / "tests"]
    assert _naming_the_retired_server(roots, skip=mine) == [
        str(tmp_path / "scripts" / name) for name in ("a.py", "b.sh", "c.js", "d.sql", "launcher")
    ]
    assert len(_naming_the_retired_server(roots, skip=tmp_path / "nothing")) == 6


def test_the_server_is_retired_and_the_chain_still_runs_the_generator():
    assert not (REPO / "scripts" / "dashboard_server.py").exists()
    assert (
        _naming_the_retired_server(
            [REPO / "scripts", REPO / "tests"], skip=Path(__file__).resolve()
        )
        == []
    )
    chain = CHAIN.read_text(encoding="utf-8")
    assert (
        '_step gen_dashboard "$VENV_PY" "$FABRIK_ROOT/scripts/gen_dashboard.py" "$DASHBOARD"'
        in chain
    )
    assert (
        'date -u +%FT%TZ > "$HEARTBEAT.tmp.$$" && mv -fT "$HEARTBEAT.tmp.$$" "$HEARTBEAT"' in chain
    )


# ---- wave-review fixup 1
def test_credit_cell_never_accepts_what_the_inventory_refuses(pinned_zone, monkeypatch):
    import datetime as dt
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    gd = _load_gen_dashboard()
    wall = 1_800_000_000.0
    monkeypatch.setattr(gd, "time", SimpleNamespace(time=lambda: wall))
    balances = [
        True,
        False,
        Decimal("1234567.5"),
        Decimal("NaN"),
        Decimal("-1"),
        5,
        5.5,
        "5",
        None,
        float("inf"),
    ]
    fetched_at = [
        dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
        dt.datetime(2020, 1, 1),  # naive: local time, as the inventory reads it
        dt.datetime.fromtimestamp(wall - 3600, dt.UTC),
        None,
    ]
    nows = [
        (float("nan"), wall),
        (float("inf"), wall),
        (float("-inf"), wall),
        (-5.0, wall),
        (True, wall),
        (None, wall),
        (10**400, wall),
        (1e300, wall),
        (10**20, wall),
        (gd.inventory._EDGE_S + 1e6, wall),
        ("1800000000", wall),
        (date(2026, 1, 1), wall),
        (Decimal("1800000000"), wall),
        (gd.inventory._EDGE_S - 1, gd.inventory._EDGE_S - 1),
        (dt.datetime(2027, 1, 1), dt.datetime(2027, 1, 1).timestamp()),  # naive: local time
        (wall + 86400, wall + 86400),
        (dt.datetime.fromtimestamp(wall + 86400, dt.UTC), wall + 86400),
    ]
    seen = set()
    for bal in balances:
        for at in fetched_at:
            for now, effective in nows:
                want = gd.inventory.credit_cell(bal, "USD", at, effective)
                got = gd.credit_cell(bal, "USD", at, now)
                assert got == want, (bal, at, now, got, want)
                seen.add(want)
    assert "" in seen and any(x.startswith("⚠") for x in seen) and "5 USD" in seen
    assert gd.credit_cell(True, "USD", None) == "" and gd.credit_cell(False, "USD", None) == ""
    assert gd.credit_cell(
        5, "usd", dt.datetime(2020, 1, 1, tzinfo=dt.UTC), now=float("nan")
    ).startswith("⚠")


class _RegistryConn:
    """The reader's fake connection: answers by FIRST substring match, `max(last_seen)` before `FROM api_keys`."""

    def __init__(self, last_seen):
        self.answers = {
            "FROM services": [
                ("alpha", "Alpha", "ai", "paid", "https://alpha.test", "active"),
                ("bravo", "Bravo", None, None, None, None),  # untriaged
            ],
            "information_schema": [(1,)],
            "max(last_seen)": [(last_seen,)],
            "FROM api_keys": [],
            "credit_snapshots": [],
            "FROM subscriptions": [],
        }

    def cursor(self):
        conn = self

        class _Cur:
            rows: list = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, *a):
                self.rows = next(v for k, v in conn.answers.items() if k in sql)

            def fetchall(self):
                return list(self.rows)

            def fetchone(self):
                return self.rows[0] if self.rows else None

        return _Cur()

    def close(self):
        pass


_STALL = "The classifier has not run for over 48 hours and 1 provider waits for a category."
_NEVER = "The classifier has no recorded run and 1 provider waits for a category."


def _write_through_main(monkeypatch, tmp_path, *, stamp_age_s):
    """`main()` over the fake registry, with the clock at _NOW and a LEFTOVER classifier stamp
    (classify_last.json from before D-1046) aged as asked — the page must ignore it."""
    import datetime as dt
    from types import SimpleNamespace

    gd = _load_gen_dashboard()
    tmp_path.mkdir(parents=True)
    monkeypatch.setattr(gd, "REPO", tmp_path)
    monkeypatch.setattr(gd, "time", SimpleNamespace(time=lambda: _NOW))
    last_seen = dt.datetime.fromtimestamp(_SYNCED, dt.UTC)
    monkeypatch.setattr(gd.registry_db, "connect", lambda: _RegistryConn(last_seen))
    if stamp_age_s is not None:
        stamp = tmp_path / ".tmp" / "external-services" / "classify_last.json"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text("{}", encoding="utf-8")
        os.utime(stamp, (_NOW - stamp_age_s, _NOW - stamp_age_s))
    out = tmp_path / "dash.html"
    assert gd.main([str(out)]) == 0
    return out.read_text(encoding="utf-8")


def test_the_registry_sync_time_reaches_the_written_file_and_no_classifier_entry_does(
    pinned_zone, monkeypatch, tmp_path
):
    stalled = _write_through_main(monkeypatch, tmp_path / "a", stamp_age_s=5 * 86400)
    assert "Registry synced 2026-10-17 14:30 +03:00" in stalled, "the reader's max(last_seen)"
    never = _write_through_main(monkeypatch, tmp_path / "b", stamp_age_s=None)
    for page in (stalled, never):  # D-1046: an old stamp, or none, raises no entry
        assert _STALL not in page and _NEVER not in page and "The classifier" not in page


def test_an_untriaged_provider_raises_no_classifier_entry(pinned_zone):
    """The queue that used to raise the stalled-classifier entry renders without one (D-1046)."""
    gd = _load_gen_dashboard()
    page = gd.render([_row("a", category="?", cost="?")], synced_at=_SYNCED, now=_NOW)
    assert _STALL not in page and _NEVER not in page and "The classifier" not in page


def test_a_stylesheet_that_would_close_its_style_element_is_one_typed_line(
    monkeypatch, capsys, tmp_path
):
    gd = _load_gen_dashboard()
    for css in ("a{}</style><script>1</script>", "a{}</STYLE ><b>"):
        d = tmp_path / str(abs(hash(css)))
        d.mkdir()
        (d / "app.css").write_text(css, encoding="utf-8")
        monkeypatch.setattr(gd.dashboard_ui, "STATIC_DIR", d)
        with pytest.raises(ValueError):
            gd.render([], now=_NOW)
        out = tmp_path / "dash.html"
        out.write_text("previous", encoding="utf-8")
        monkeypatch.setattr(gd, "_read", lambda: ([], None))
        assert gd.main([str(out)]) == 1
        printed = capsys.readouterr().out
        assert printed.count("\n") == 1 and "ERROR: registry unreadable" in printed
        assert out.read_text(encoding="utf-8") == "previous"
