"""Grader for the Promtail -> Alloy operator runbook (plan 2026-10-08-plan-1, ticket T06).

The runbook is ``docs/operations/promtail-to-alloy-runbook.md``. These tests parse it by HEADING and split
each section into prose and fenced blocks, so a word in the wrong section, or only in a comment, does not
satisfy them.

Seam (spine § Interfaces, T02/T03/T04a -> T06): every name the runbook relies on exists in the files it
points at — the `alloy` service and port in the hub compose and spoke template, job `alloy` in
prometheus.yml, endpoint `alloy` in the Gatus config, the two sync scripts, and step 11's three `sed`
substitutions.

Cheapest way to satisfy this grader without the outcome (CLAUDE.md § FIX DIRECTIVE 5): write the tokens it
looks for into prose or fences that are never meant to be run. The counter-measure is the full
/fabrik-review the plan assigns T06 and the T07 rehearsals — the grader proves structure and seams, a
reviewer proves the commands are the right commands.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "operations" / "promtail-to-alloy-runbook.md"
HUB_COMPOSE = ROOT / "infra" / "vps1" / "monitoring" / "compose.yaml"
SPOKE_TEMPLATE = (
    ROOT / "scripts" / "bootstrap" / "templates" / "monitoring-agent.compose.yaml.template"
)
PROMETHEUS = ROOT / "configs" / "prometheus" / "prometheus.yml"
GATUS = ROOT / "configs" / "gatus" / "apps" / "observability-agents.yaml"
BOOTSTRAP_VPS = ROOT / "scripts" / "bootstrap" / "bootstrap-vps.sh"
WORKTREE = "/opt/fabrik/.claude/worktrees/fleet-alloy"
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Section:
    level: int
    title: str
    prose: list[str] = field(default_factory=list)
    fences: list[str] = field(default_factory=list)
    children: list[Section] = field(default_factory=list)

    def all_prose(self) -> str:
        return "\n".join(self.prose + [c.all_prose() for c in self.children])

    def all_fences(self) -> str:
        return "\n".join(self.fences + [c.all_fences() for c in self.children])


def _parse() -> list[Section]:
    roots: list[Section] = []
    stack: list[Section] = []
    fence: list[str] | None = None
    for line in RUNBOOK.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            if fence is None:
                fence = []
            else:
                if stack:
                    stack[-1].fences.append("\n".join(fence))
                fence = None
            continue
        if fence is not None:
            fence.append(line)
            continue
        m = HEADING.match(line)
        if m:
            sec = Section(len(m.group(1)), m.group(2))
            while stack and stack[-1].level >= sec.level:
                stack.pop()
            (stack[-1].children if stack else roots).append(sec)
            stack.append(sec)
            continue
        if stack:
            stack[-1].prose.append(line)
    return roots


def _h2(prefix: str) -> Section:
    doc = _parse()[0]
    hits = [s for s in doc.children if s.title.startswith(prefix)]
    assert len(hits) == 1, (
        f"expected one '## {prefix}' section, got {[s.title for s in doc.children]}"
    )
    return hits[0]


def _child(sec: Section, prefix: str) -> Section:
    hits = [c for c in sec.children if c.title.startswith(prefix)]
    assert len(hits) == 1, (
        f"expected one '### {prefix}' under '{sec.title}', got {[c.title for c in sec.children]}"
    )
    return hits[0]


def _child_titles(sec: Section) -> list[str]:
    return [c.title for c in sec.children]


def _mail_body() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.index("<!-- infra-mail:begin -->") + len("<!-- infra-mail:begin -->")
    return text[start : text.index("<!-- infra-mail:end -->")]


# --- Behavior Contract row 1: hosts in order, steps (a)-(d), stop before start, no plain up -d ---


def test_hosts_run_vps3_then_vps2_then_vps1() -> None:
    doc = _parse()[0]
    hosts = [s.title for s in doc.children if re.match(r"^[1-3]\. vps[1-3]$", s.title)]
    assert hosts == ["1. vps3", "2. vps2", "3. vps1"]


def test_each_full_host_section_carries_steps_a_to_d_in_order() -> None:
    for prefix in ("1. vps3", "3. vps1"):
        titles = _child_titles(_h2(prefix))
        steps = [t[:3] for t in titles if re.match(r"^\([a-d]\)", t)]
        assert steps == ["(a)", "(b)", "(c)", "(d)"], (prefix, titles)
    vps2 = _h2("2. vps2").all_prose()
    for step in ("(a)", "(b)", "(c)", "(d)"):
        assert step in vps2, f"vps2 does not name step {step}"


def test_stop_precedes_start_and_no_plain_up_between_a_and_c() -> None:
    for prefix in ("1. vps3", "3. vps1"):
        host = _h2(prefix)
        stop = _child(host, "(b)").all_fences()
        start = _child(host, "(c)").all_fences()
        assert "docker compose stop promtail" in stop
        assert "docker compose up -d alloy" in start
        for step in ("(a)", "(b)"):
            fences = _child(host, step).all_fences()
            assert not re.search(r"up -d(?! alloy)", fences), f"{prefix} {step} runs a plain up -d"


# --- row 2: the D3 checks before vps1's (b), the pushes after (c) ---


def test_hub_d3_checks_sit_between_a_and_b_as_stop_conditions() -> None:
    hub = _h2("3. vps1")
    titles = _child_titles(hub)
    i_a = next(i for i, t in enumerate(titles) if t.startswith("(a)"))
    i_chk = next(i for i, t in enumerate(titles) if t.startswith("D3 read-only checks"))
    i_b = next(i for i, t in enumerate(titles) if t.startswith("(b)"))
    assert i_a < i_chk < i_b
    chk = _child(hub, "D3 read-only checks")
    assert "git diff --stat master HEAD -- configs/prometheus configs/gatus" in chk.all_fences()
    assert "master...HEAD" not in chk.all_fences(), "the check must be two-dot"
    for script in ("sync_prometheus_to_vps.sh --diff", "sync_gatus_to_vps.sh --diff"):
        assert f"FABRIK_ROOT={WORKTREE} bash scripts/{script}" in chk.all_fences()
    prose = chk.all_prose()
    assert "STOP" in prose and "DRIFT or ORPHAN" in prose
    assert "Pass" in prose


def test_hub_pushes_follow_c_with_the_branch_worktree_root() -> None:
    hub = _h2("3. vps1")
    titles = _child_titles(hub)
    i_c = next(i for i, t in enumerate(titles) if t.startswith("(c)"))
    i_push = next(i for i, t in enumerate(titles) if t.startswith("Watcher push"))
    i_d = next(i for i, t in enumerate(titles) if t.startswith("(d)"))
    assert i_c < i_push < i_d
    push = _child(hub, "Watcher push").all_fences()
    for script in ("sync_prometheus_to_vps.sh --push", "sync_gatus_to_vps.sh --push"):
        assert f"FABRIK_ROOT={WORKTREE} bash scripts/{script}" in push


# --- row 3: V4/V5/V6 anchored on step (b); V6 markers ---


def test_battery_windows_are_anchored_on_step_b() -> None:
    battery = _child(_h2("1. vps3"), "(d)")
    prose = battery.all_prose()
    assert "anchored on step (b)" in prose
    for v in ("V4", "V5", "V6", "V7", "V8", "V11"):
        assert f"**{v}" in prose, f"battery misses {v}"
    v4v5 = battery.all_fences()
    assert "start=${B}000000000" in v4v5 and "$((B+900))" in v4v5 and "$((B-900))" in v4v5


def test_v6_markers_pre_switch_and_exactly_once() -> None:
    host = _h2("1. vps3")
    assert "5 to 10 minutes before step (b)" in host.all_prose()
    assert "alloy-pre-$TS-$H-" in "\n".join(host.fences)
    assert "alloy-switch-$TS-$H" in _child(host, "(b)").all_fences()
    battery = _child(host, "(d)").all_prose()
    assert "exactly once" in battery and "2 minutes" in battery
    canary = _h2("0. Preflight").all_fences()
    assert (
        "--name alloy-canary" in canary
        and "--rm" not in canary.split("alloy-canary")[0].splitlines()[-1]
    )


# --- row 4: rollback restores the file and runs up -d --remove-orphans ---


def test_rollback_restores_the_file_and_never_stop_starts() -> None:
    rb = _h2("4. Rollback")
    fences = rb.all_fences()
    assert (
        fences.count(
            "cp compose.yaml.pre-alloy compose.yaml && sudo docker compose up -d --remove-orphans"
        )
        == 2
    )
    assert "docker compose stop alloy" not in fences
    assert "Never roll back by stopping Alloy" in rb.all_prose()
    assert "Duplicate span" in rb.all_prose()


# --- row 5: preflight silence, canary before (a), ss -ltn on each spoke ---


def test_preflight_silence_canary_and_port_check() -> None:
    pre = _h2("0. Preflight")
    fences = pre.all_fences()
    assert "amtool silence add" in fences and 'job=\\"promtail-spokes\\"' in fences
    assert "ss -ltn" in fences and "12345" in fences and "for h in vps2 vps3" in fences
    assert "proactive-check.sh:147-148" in pre.all_prose()
    doc = _parse()[0]
    titles = [s.title for s in doc.children]
    assert titles.index("0. Preflight") < titles.index("1. vps3")


# --- row 6: Gate S trigger and cleanup list ---


def test_gate_s_trigger_and_cleanup_list() -> None:
    gate = _h2("6. V9 daily and Gate S").all_prose()
    assert "V8 and V9 green on all three hosts for 14 days" in gate
    for item in (
        "the `promtail` service",
        "the `promtail-positions` volume — classified first",
        "the `compose.yaml.pre-alloy` files",
        "configs/promtail/promtail-config.yaml",
        "scripts/bootstrap/templates/promtail.yaml.template",
        "the memory-limits spec row first",
    ):
        assert item in gate, f"Gate S cleanup misses: {item}"


# --- row 7: the close — operator signal, then the agent's merge request and mail ---


def test_close_is_signal_then_merge_request_then_mail() -> None:
    close = _h2("5. The close")
    prose = close.all_prose()
    assert prose.index("tell the fleet agent") < prose.index("only after that")
    assert "merge_request.py request --review" in close.all_fences()
    assert "mail.py send --to fabrik --to-agent infra --kind finding" in prose


# --- row 8: the appendix mail passes D-035 and names every infra-owned file ---


def test_infra_mail_passes_the_d035_structure_check() -> None:
    spec = importlib.util.spec_from_file_location(
        "fabrik_mail_for_runbook", ROOT / "scripts" / "mail.py"
    )
    assert spec and spec.loader
    mail = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mail)
    assert mail._structure_gaps("finding", _mail_body()) == []


def test_infra_mail_names_every_infra_owned_file() -> None:
    body = _mail_body()
    for path in (
        ".windsurf/rules/core/55-observability.md",
        ".windsurf/rules/core/12-node.md",
        ".windsurf/rules/core/10-python.md",
        ".windsurf/rules/core/60-watchdog.md",
        ".windsurf/rules/CLAIMS.yaml",
        "agents-fabrik.md",
        "docs/reference/prebuilt-app-containers.md",
        "fabrik-deploy-verify.md",
        "fabrik-plan-after-chat.md",
        "fabrik-review.md",
        "fabrik-spec.md",
        "fabrik-spec-review.md",
        "fabrik-vision.md",
    ):
        assert path in body, f"infra mail misses {path}"


# --- command-shape guards (wave-3 review round 1: a token grader passed a runbook with broken commands) ---


def test_hub_uses_ssh_alias_vps_and_loki_label_vps1() -> None:
    hub_vars = _h2("3. vps1").fences[0]
    assert "S=vps; H=vps1" in hub_vars
    for prefix in ("1. vps3", "3. vps1"):
        for line in _h2(prefix).all_fences().splitlines():
            assert 'ssh "$H"' not in line, f"{prefix}: ssh must target $S, not the label $H"


def test_alloy_status_filter_is_anchored_and_v6_reads_only_the_canary() -> None:
    for prefix in ("1. vps3", "3. vps1"):
        start = _child(_h2(prefix), "(c)").all_fences()
        assert "--filter name=^alloy$" in start, f"{prefix}: name=alloy also matches alloy-canary"
    battery = _child(_h2("1. vps3"), "(d)").all_fences()
    assert 'container_name=\\"alloy-canary\\"' in battery
    labels_line = next(line for line in battery.splitlines() if "/loki/api/v1/labels" in line)
    assert "query={host=" in labels_line, "V4 must be scoped to this host"


def test_silence_expire_selects_by_matcher_and_hub_v8_is_runnable() -> None:
    push = _child(_h2("3. vps1"), "Watcher push").all_fences()
    assert "comment=" not in push
    assert "amtool silence query" in push and 'job=\\"promtail-spokes\\"' in push
    hub_battery = _child(_h2("3. vps1"), "(d)").all_fences()
    assert "--network fabrik curlimages/curl:latest" in hub_battery
    assert "http://alloy:12345/-/ready" in hub_battery
    assert 'up{job=\\"alloy\\"}' in hub_battery


# --- seam: every name the runbook relies on exists where it points ---


def test_seam_names_exist_in_the_compose_files_and_configs() -> None:
    hub = yaml.safe_load(HUB_COMPOSE.read_text(encoding="utf-8"))
    assert "alloy" in hub["services"] and hub["services"]["promtail"]["profiles"] == ["rollback"]
    assert "--server.http.listen-addr=0.0.0.0:12345" in hub["services"]["alloy"]["command"]
    assert "/opt/monitoring/configs/alloy:/etc/alloy:ro" in hub["services"]["alloy"]["volumes"]
    assert "alloy:" in SPOKE_TEMPLATE.read_text(encoding="utf-8")
    assert "/opt/monitoring-agent/alloy.alloy" in SPOKE_TEMPLATE.read_text(encoding="utf-8")
    jobs = [
        j["job_name"]
        for j in yaml.safe_load(PROMETHEUS.read_text(encoding="utf-8"))["scrape_configs"]
    ]
    assert "alloy" in jobs and "promtail-spokes" not in jobs
    endpoints = [e["name"] for e in yaml.safe_load(GATUS.read_text(encoding="utf-8"))["endpoints"]]
    assert "alloy" in endpoints
    for script in (
        "sync_prometheus_to_vps.sh",
        "sync_gatus_to_vps.sh",
        "merge_request.py",
        "mail.py",
    ):
        assert (ROOT / "scripts" / script).exists(), script


def test_seam_spoke_render_uses_step_11s_three_substitutions() -> None:
    runbook = _h2("1. vps3").all_fences()
    step11 = BOOTSTRAP_VPS.read_text(encoding="utf-8")
    for placeholder in ("{{SPOKE_NAME}}", "{{SPOKE_MESH_IP}}", "{{HUB_MESH_IP}}"):
        assert f"s|{placeholder}|" in runbook
        assert f"s|{placeholder}|" in step11
    for template in ("monitoring-agent.compose.yaml", "promtail.yaml", "alloy.alloy"):
        assert template in runbook
        assert f"templates/{template}.template" in step11
