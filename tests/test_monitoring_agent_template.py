"""T03 — the spoke compose template and bootstrap step 11 ship Alloy.

Plan: docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T03-spoke-stack-and-bootstrap.md
Spec: docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md § The delta D3, D4, D5, D6, D7, D8.

The six Behavior Contract rows, in order:
1. the rendered spoke compose template's `alloy` service pins `grafana/alloy:v1.20.1` with
   `platform: linux/amd64` and `restart: unless-stopped`, and carries a 128M memory limit,
   `cpus: 0.25`, `network_mode: host` and a listen address on the spoke's mesh IP port 12345.
2. `promtail` appears only under the `rollback` profile, and both positions volumes
   (`promtail-positions`, `alloy-data`) are declared.
3. bootstrap step 11's script text renders and ships `alloy.alloy` beside `compose.yaml` and
   `promtail.yaml`, and its verify filter names `alloy`, not `promtail`.
4. both edited bootstrap scripts parse clean under `bash -n`.
5. the infra mirrors for vps2 and vps3 equal the template rendered for that host with the same
   sed placeholder set bootstrap step 11 uses.
6. the spoke restore inventory's § D classifies `monitoring-agent_alloy-data` beside
   `monitoring-agent_promtail-positions`.

Round-1 review fixups (O1-O8) folded in: O2 — step 11 brought the stack up with
`--remove-orphans` without first stopping a still-RUNNING promtail; a profiled-out service's
RUNNING container is not an orphan, so a rerun on an un-switched spoke would start alloy
beside a live promtail (spec D2 forbids the parallel run) — step 11 now runs
`docker compose rm -sf promtail` before `up -d`, asserted here to precede it in the script
text. O3 — the verify step only printed `docker ps` and always logged success; it now fails
closed (`grep -q '^alloy Up' || { err …; return 1; }`) unless a container named `alloy` is
`Up`, asserted at the text level. O1 — the row-3 test below now asserts the exact scp
argument, the exact remote `mv` destination and the exact volume mount, not just substring
presence. O8 — the sed-set comment below cites the function, not line numbers, which drift.
O4 — the restore inventory's monitoring-agent row and UFW-mesh-rule row still named promtail
as the thing being scraped/running; both now name alloy (promtail stays named only as the
rollback-profile service). O5 — the alloy-data row claimed positions "re-derive from the
legacy promtail-positions hand-over", which is false on a restored spoke: that positions
volume is itself not restored (the row above it), so there is nothing to hand over; the row
now says Alloy starts with no stored position and tails from each file's beginning
(`tail_from_end` defaults to false, spec cv-12). O6 — bootstrap-spoke-restore.sh's comment
blamed an unreachable Loki for the restart loop under `--skip-mesh`; Alloy's `loki.write`
retries indefinitely and does not exit on that, so the real cause is `--server.http.listen-
addr` failing to bind a mesh IP that does not exist while wg0 is down — the comment now says
so. O7 — the template's header comment described {{SPOKE_NAME}}/{{HUB_MESH_IP}} as consumed
by promtail only; they are substituted into alloy.alloy.template too (and still into
promtail.yaml.template for the rollback service) — both infra mirrors re-rendered to match.

Round-2 review fixups (O9, T03-S2) folded in: O9 — round 1's own fix for O3 introduced a new
defect: step 11 is called unconditionally in `main()`, after (not inside) the `if ! $SKIP_MESH`
block, and the script runs `set -euo pipefail`. Under `--skip-mesh` there is no wg0, so alloy
cannot bind `--server.http.listen-addr=<mesh IP>:12345` and crash-loops — O3's fail-closed
`return 1` then aborted the whole bootstrap, so steps 12-16 never ran on a drill. The verify now
branches on `$SKIP_MESH`: still fails closed when the mesh is up, but `warn`s and continues
when `--skip-mesh` was passed, naming the follow-up (re-run step 11 once the mesh exists).
`test_step_11_verify_*` below extract the verify tail and run it under `bash -c` with `remote`,
`err`, `warn`, `ok` and `sleep` stubbed — both branches, both outcomes. T03-S2 — nothing graded
the actual UFW rule that makes a spoke's alloy:12345 reachable from vps1 over wg0, only prose
mentioning alloy in a nearby comment; `test_ufw_rule_allows_the_mesh_subnet_and_its_comment_
names_alloy` asserts the real `ufw allow from ${FABRIK_WG_SUBNET}` code line and that the
alloy:12345 mention sits in that rule's own explanatory comment block, not just anywhere in
the file.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "scripts/bootstrap/templates/monitoring-agent.compose.yaml.template"
BOOTSTRAP_VPS = REPO_ROOT / "scripts/bootstrap/bootstrap-vps.sh"
BOOTSTRAP_RESTORE = REPO_ROOT / "scripts/bootstrap/bootstrap-spoke-restore.sh"
RESTORE_INVENTORY = REPO_ROOT / "docs/operations/spoke-restore-inventory.md"

# The same three placeholders bootstrap's step_11_install_monitoring_agents's `sed` blocks
# substitute into every one of the three rendered files (compose.yaml, promtail.yaml,
# alloy.alloy) — cited by function name, not line numbers, because a later edit shifts them.
SPOKES = {
    "vps2": {"SPOKE_NAME": "vps2", "SPOKE_MESH_IP": "10.99.0.2", "HUB_MESH_IP": "10.99.0.1"},
    "vps3": {"SPOKE_NAME": "vps3", "SPOKE_MESH_IP": "10.99.0.3", "HUB_MESH_IP": "10.99.0.1"},
}


def _render(template_text: str, values: dict[str, str]) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def _rendered_services(spoke: str) -> dict:
    text = _render(TEMPLATE.read_text(encoding="utf-8"), SPOKES[spoke])
    doc = yaml.safe_load(text)
    return doc["services"]


def _step_11_text() -> str:
    text = BOOTSTRAP_VPS.read_text(encoding="utf-8")
    return text.split("step_11_install_monitoring_agents()", 1)[1].split("\nstep_12_", 1)[0]


def _step_02_text() -> str:
    text = BOOTSTRAP_VPS.read_text(encoding="utf-8")
    return text.split("step_02_install_firewall_fail2ban()", 1)[1].split("\nstep_03_", 1)[0]


def _step_11_verify_block() -> str:
    """Isolates step 11's post-up verify tail (the `sleep 4` through the function's own
    closing brace) so its `$SKIP_MESH` branch (O9) can be exercised standalone, under a
    stubbed `remote`/`err`/`warn`/`ok`/`sleep`, against a fixture `docker ps` line."""
    step11 = _step_11_text()
    start = step11.index("sleep 4")
    end = step11.index("\n}", start)
    return step11[start:end]


def _run_step_11_verify(
    agent_status: str, skip_mesh: bool, inspect: tuple[str, str]
) -> subprocess.CompletedProcess[str]:
    """`remote` answers the `docker ps` read with `agent_status` and the two `docker inspect`
    reads with `inspect[0]` then `inspect[1]` (a counter file, since each call runs in a
    command-substitution subshell)."""
    block = _step_11_verify_block()
    wrapper = (
        "set -uo pipefail\n"
        f"SKIP_MESH={'true' if skip_mesh else 'false'}\n"
        'CNT=$(mktemp); echo 0 > "$CNT"\n'
        "remote() {\n"
        f"  case \"$*\" in *inspect*) n=$(cat \"$CNT\"); echo $((n+1)) > \"$CNT\";\n"
        f"    if [ \"$n\" = 0 ]; then printf '%s\\n' {shlex.quote(inspect[0])};"
        f" else printf '%s\\n' {shlex.quote(inspect[1])}; fi ;;\n"
        f"  *) printf '%s\\n' {shlex.quote(agent_status)} ;; esac\n"
        "}\n"
        'err() { echo "ERR: $*"; }\n'
        'warn() { echo "WARN: $*"; }\n'
        'ok() { echo "OK: $*"; }\n'
        "sleep() { :; }\n"
        "verify_tail() {\n" + block + "\n}\n"
        "verify_tail; echo RC=$?\n"
    )
    return subprocess.run(
        ["bash", "-c", wrapper], capture_output=True, text=True, timeout=10, check=False
    )


# --- Behavior Contract row 1: the alloy service's pins, limits and listen address ---


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_alloy_service_pins_image_platform_restart(spoke: str) -> None:
    alloy = _rendered_services(spoke)["alloy"]
    assert alloy["image"] == "grafana/alloy:v1.20.1"
    assert alloy["platform"] == "linux/amd64"
    assert alloy["restart"] == "unless-stopped"


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_alloy_service_network_and_limits(spoke: str) -> None:
    alloy = _rendered_services(spoke)["alloy"]
    assert alloy["network_mode"] == "host"
    limits = alloy["deploy"]["resources"]["limits"]
    assert limits["memory"] == "128M"
    assert str(limits["cpus"]) == "0.25"


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_alloy_listens_on_the_spoke_mesh_ip_port_12345(spoke: str) -> None:
    alloy = _rendered_services(spoke)["alloy"]
    expected = f"--server.http.listen-addr={SPOKES[spoke]['SPOKE_MESH_IP']}:12345"
    assert expected in alloy["command"]


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_alloy_storage_path_flag_present(spoke: str) -> None:
    alloy = _rendered_services(spoke)["alloy"]
    assert "--storage.path=/var/lib/alloy/data" in alloy["command"]


def test_template_header_names_alloy_as_a_placeholder_consumer() -> None:
    # O7: the header comment described {{SPOKE_NAME}}/{{HUB_MESH_IP}} as used by promtail
    # only; both are substituted into alloy.alloy.template too (step 11, same sed set).
    header = TEMPLATE.read_text(encoding="utf-8").split("services:", 1)[0]
    assert "alloy.alloy" in header


# --- Behavior Contract row 2: promtail is rollback-only; both positions volumes declared ---


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_promtail_only_under_rollback_profile(spoke: str) -> None:
    promtail = _rendered_services(spoke)["promtail"]
    assert promtail.get("profiles") == ["rollback"]


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_both_positions_volumes_declared(spoke: str) -> None:
    text = _render(TEMPLATE.read_text(encoding="utf-8"), SPOKES[spoke])
    doc = yaml.safe_load(text)
    assert set(doc["volumes"]) == {"promtail-positions", "alloy-data"}


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_alloy_mounts_positions_readonly_and_its_own_data_volume(spoke: str) -> None:
    alloy = _rendered_services(spoke)["alloy"]
    volumes = alloy["volumes"]
    assert "promtail-positions:/run/promtail:ro" in volumes
    assert "alloy-data:/var/lib/alloy/data" in volumes


# --- Behavior Contract row 3: bootstrap step 11 renders+ships alloy.alloy, verify filter is alloy ---


def test_step_11_scp_line_ships_alloy_alloy() -> None:
    # O1: the exact scp argument, not just "alloy.alloy appears somewhere in step 11".
    step11 = _step_11_text()
    scp_line = next(line for line in step11.splitlines() if line.strip().startswith("scp "))
    assert '"${tmpdir}/alloy.alloy"' in scp_line
    # promtail.yaml is still shipped too — the rollback service mounts it.
    assert '"${tmpdir}/promtail.yaml"' in scp_line
    assert '"${tmpdir}/compose.yaml"' in scp_line


def test_step_11_remote_mv_installs_alloy_alloy_to_the_exact_path() -> None:
    # O1: the exact remote destination, not a substring match against the whole step.
    step11 = _step_11_text()
    mv_line = next(
        line for line in step11.splitlines() if "mv /tmp/alloy.alloy" in line
    )
    assert mv_line.strip() == "sudo mv /tmp/alloy.alloy /opt/monitoring-agent/alloy.alloy && \\"
    # the alloy.alloy file (no .yaml extension) must survive the chmod, not just compose/promtail.
    chmod_line = next(line for line in step11.splitlines() if "chmod 644" in line)
    assert "/opt/monitoring-agent/alloy.alloy" in chmod_line


def test_template_mounts_the_exact_rendered_alloy_alloy_path() -> None:
    # O1: the template's own alloy service mounts exactly the path step 11 installs to.
    alloy = _rendered_services("vps2")["alloy"]
    assert "/opt/monitoring-agent/alloy.alloy:/etc/alloy/config.alloy:ro" in alloy["volumes"]


def test_step_11_renders_and_ships_alloy_alloy_template() -> None:
    step11 = _step_11_text()
    assert "alloy.alloy.template" in step11
    # promtail.yaml is still rendered and shipped — the rollback service mounts it.
    assert "promtail.yaml.template" in step11


def test_step_11_stops_promtail_before_bringing_the_stack_up() -> None:
    # O2: a still-RUNNING promtail is not an orphan under a stopped `profiles: [rollback]`
    # service, so `up -d --remove-orphans` alone would start alloy beside a live promtail on
    # a rerun against an un-switched spoke — forbidden by spec D2's no-parallel-run rule.
    step11 = _step_11_text()
    rm_idx = step11.index("docker compose rm -sf promtail")
    up_idx = step11.index("docker compose up -d --remove-orphans")
    assert rm_idx < up_idx
    # the positions volume must survive the rm (no -v / --volumes flag on this line)
    rm_line = next(line for line in step11.splitlines() if "docker compose rm -sf promtail" in line)
    assert " -v" not in rm_line
    assert "--volumes" not in rm_line


def test_step_11_verify_fails_closed_unless_alloy_is_up() -> None:
    # O3: printing `docker ps` and logging success unconditionally is not a verify — the step
    # must fail when alloy is missing or crash-looping.
    step11 = _step_11_text()
    guard = '"${alloy_second}" == "${alloy_first}"'
    assert guard in step11
    guard_tail = step11.split(guard, 1)[1][:700]
    assert "return 1" in guard_tail
    assert "err " in guard_tail


NOT_UP = ("alloy Restarting (1) 2 seconds ago", ("restarting 3", "restarting 4"))
IS_UP = ("alloy Up 5 seconds", ("running 0", "running 0"))


def test_step_11_verify_fails_a_crash_loop_caught_between_restarts() -> None:
    # D7 INFRA-O2: a crash-looping alloy reads "Up Less than a second" on one `docker ps`
    # (seen live on a throwaway --restart unless-stopped container); the second inspect read
    # 15 s later shows the restart count moved, so the step must still fail.
    status, _ = IS_UP
    result = _run_step_11_verify(
        "alloy Up Less than a second", skip_mesh=False, inspect=("running 2", "running 3")
    )
    assert "RC=1" in result.stdout and "ERR:" in result.stdout, (status, result.stdout)


def test_step_11_verify_fails_a_crash_loop_waiting_out_its_backoff() -> None:
    # D7 INFRA-O7: during a restart backoff Docker reads State.Running=true, Status
    # `restarting`, and the count holds still (seen live: `true restarting 9` on successive
    # reads). Two identical `restarting N` reads must still fail the step.
    result = _run_step_11_verify(
        "alloy Restarting (1) 20 seconds ago", skip_mesh=False, inspect=("restarting 9", "restarting 9")
    )
    assert "RC=1" in result.stdout and "ERR:" in result.stdout, result.stdout


def test_step_11_verify_read_gap_outlasts_dockers_backoff_reset() -> None:
    # D7 INFRA-O9: with 6 s between the reads, a loop that ran ~8 s before crashing read
    # `running 2` twice and passed (1 of 6 live rounds). Docker resets the restart backoff
    # after 10 s of uptime, so the gap between the two inspect reads must exceed 10 s.
    block = _step_11_verify_block()
    between = block.split("alloy_first=", 1)[1].split("alloy_second=", 1)[0]
    gaps = [int(w.split()[0]) for w in between.split("sleep ")[1:]]
    assert gaps and sum(gaps) > 10, gaps


def test_step_11_verify_passes_a_rerun_with_old_restarts_on_the_count() -> None:
    # a rerun after a --skip-mesh drill: the container kept its RestartCount, but it is
    # running and the count does not move between the two reads.
    result = _run_step_11_verify("alloy Up 9 seconds", skip_mesh=False, inspect=("running 5", "running 5"))
    assert "RC=0" in result.stdout and "ERR:" not in result.stdout


def test_step_11_verify_still_fails_closed_when_mesh_is_up() -> None:
    # O9 regression guard: the SKIP_MESH branch must not weaken the real (mesh-up) case —
    # a crash-looping alloy with the mesh actually up still aborts the step.
    result = _run_step_11_verify(NOT_UP[0], skip_mesh=False, inspect=NOT_UP[1])
    assert "RC=1" in result.stdout
    assert "ERR:" in result.stdout
    assert "WARN:" not in result.stdout


def test_step_11_verify_warns_and_continues_under_skip_mesh() -> None:
    # O9: round 1's own fix for O3 made this step unconditionally abort under --skip-mesh
    # (no wg0 → alloy can't bind the mesh IP → crash-loop → `return 1` → the rest of
    # bootstrap, steps 12-16, never ran under `set -euo pipefail`). It must warn and
    # continue instead, naming the follow-up.
    result = _run_step_11_verify(NOT_UP[0], skip_mesh=True, inspect=NOT_UP[1])
    assert "RC=0" in result.stdout
    assert "WARN:" in result.stdout
    assert "ERR:" not in result.stdout
    assert "re-run step 11" in result.stdout.lower()


def test_step_11_verify_succeeds_when_alloy_is_up_regardless_of_skip_mesh() -> None:
    # the happy path must stay silent (no warn, no err) whether or not --skip-mesh was passed.
    for skip_mesh in (False, True):
        result = _run_step_11_verify(IS_UP[0], skip_mesh=skip_mesh, inspect=IS_UP[1])
        assert "RC=0" in result.stdout
        assert "ERR:" not in result.stdout
        assert "WARN:" not in result.stdout


def test_step_11_verify_branches_on_skip_mesh_variable() -> None:
    # text-level companion to the three behavioral tests above: the verify tail must
    # actually consult $SKIP_MESH, not just always fail or always warn.
    block = _step_11_verify_block()
    assert "$SKIP_MESH" in block
    elif_idx = block.index("elif $SKIP_MESH")
    return_idx = block.index("return 1")
    assert elif_idx < return_idx, "the SKIP_MESH branch must come before the fail-closed branch"


def test_step_11_verify_filter_names_alloy_not_promtail() -> None:
    step11 = _step_11_text()
    verify_line = next(line for line in step11.splitlines() if "docker ps --filter" in line)
    assert "name=alloy" in verify_line
    assert "name=promtail" not in verify_line


def test_ufw_comment_names_alloy_not_promtail() -> None:
    text = BOOTSTRAP_VPS.read_text(encoding="utf-8")
    assert "alloy:12345" in text
    assert "promtail:9080" not in text


def test_ufw_rule_allows_the_mesh_subnet_and_its_comment_names_alloy() -> None:
    # T03-S2: grade the actual UFW rule's CODE, not just a comment mentioning alloy
    # somewhere in the file — the rule that makes a spoke's alloy:12345 reachable from
    # vps1 over wg0.
    step02 = _step_02_text()
    rule_line = next(
        line for line in step02.splitlines() if "ufw allow from ${FABRIK_WG_SUBNET}" in line
    )
    assert "remote " in rule_line
    # T03-O10: the rule must be live code — a commented-out rule still contains both strings
    assert not rule_line.lstrip().startswith("#"), "the mesh ufw allow rule is commented out"
    # the alloy:12345 mention must sit in THIS rule's own explanatory comment block —
    # the contiguous run of comment lines immediately preceding the rule line.
    lines = step02.splitlines()
    rule_idx = lines.index(rule_line)
    comment_lines: list[str] = []
    i = rule_idx - 1
    while i >= 0 and lines[i].strip().startswith("#"):
        comment_lines.append(lines[i])
        i -= 1
    comment_block = "\n".join(reversed(comment_lines))
    assert comment_block, "the ufw allow rule has no preceding comment block"
    assert "alloy:12345" in comment_block


# --- Behavior Contract row 4: bash -n on both edited bootstrap scripts ---


@pytest.mark.parametrize("script", [BOOTSTRAP_VPS, BOOTSTRAP_RESTORE])
def test_bash_dash_n_parses_clean(script: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(script)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr


def test_spoke_restore_comment_names_alloy_depends_on_loki() -> None:
    text = BOOTSTRAP_RESTORE.read_text(encoding="utf-8")
    assert "alloy depends on vps1's Loki" in text or (
        "alloy depends on" in text and "Loki" in text
    )
    assert "promtail depends on vps1's Loki" not in text


def test_spoke_restore_comment_blames_the_mesh_ip_bind_not_a_loki_retry_loop() -> None:
    # O6: Alloy's loki.write retries indefinitely and does not exit on an unreachable Loki —
    # under --skip-mesh the real restart-loop cause is --server.http.listen-addr failing to
    # bind a mesh IP that does not exist while wg0 is down.
    text = BOOTSTRAP_RESTORE.read_text(encoding="utf-8")
    comment = text.split('Don\'t require "running" state', 1)[1].split("sleep 5", 1)[0]
    assert "listen-addr" in comment
    assert "bind" in comment
    assert "retries" in comment and "not exit" in comment


# --- Behavior Contract row 5: infra mirrors equal the template rendered for that host ---


@pytest.mark.parametrize("spoke", sorted(SPOKES))
def test_infra_mirror_equals_rendered_template(spoke: str) -> None:
    rendered = _render(TEMPLATE.read_text(encoding="utf-8"), SPOKES[spoke])
    mirror_path = REPO_ROOT / "infra" / spoke / "monitoring-agent" / "compose.yaml"
    assert mirror_path.read_text(encoding="utf-8") == rendered


# --- Behavior Contract row 6: spoke restore inventory § D classifies monitoring-agent_alloy-data ---


def test_restore_inventory_classifies_alloy_data_volume() -> None:
    text = RESTORE_INVENTORY.read_text(encoding="utf-8")
    section_d = text.split("## D. Docker named volumes", 1)[1].split("\n## ", 1)[0]
    assert "monitoring-agent_alloy-data" in section_d
    assert "monitoring-agent_promtail-positions" in section_d


def test_restore_inventory_alloy_data_row_is_truthful_about_empty_positions() -> None:
    # O5: the row must not claim positions "re-derive from the legacy promtail-positions
    # hand-over" — that volume is itself not restored (the row above), so a rebuilt spoke has
    # nothing to hand over. The truthful statement is cv-12's tail_from_end default.
    text = RESTORE_INVENTORY.read_text(encoding="utf-8")
    section_d = text.split("## D. Docker named volumes", 1)[1].split("\n## ", 1)[0]
    row = next(line for line in section_d.splitlines() if "monitoring-agent_alloy-data" in line)
    assert "re-derive" not in row
    assert "hand-over" not in row
    assert "not restored" in row
    assert "tail_from_end" in row


def test_restore_inventory_monitoring_agent_dir_row_names_alloy() -> None:
    # O4: the § C directory row named the running stack "node-exporter + cadvisor +
    # promtail"; promtail is rollback-only now, alloy is what actually runs.
    text = RESTORE_INVENTORY.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| `monitoring-agent`"))
    assert "alloy" in row
    assert "rollback" in row


def test_restore_inventory_ufw_row_names_alloy_not_promtail() -> None:
    # O4: the § B UFW-mesh-rule row said the rule exists so Prometheus can scrape promtail;
    # promtail no longer runs by default — alloy does.
    text = RESTORE_INVENTORY.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "mesh trust" in line)
    assert "alloy" in row
    assert "promtail" not in row
