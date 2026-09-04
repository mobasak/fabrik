# AFTER-EDIT: scripts/vps_apply_limits.sh | scripts/sysadmin/proactive-check.sh
"""The vps1 memory-ceiling applier — every safety rule here was a live hazard in the
version this replaces (last touched 2026-05-30, never run since).

Measured on vps1 2026-09-04: 10 of 32 containers had `HostConfig.Memory == 0`, some since
2026-07-08, while a script naming all ten sat in the repo. Running that script would have:

  * FAILED on promtail   — target 128m against a live working set of 134.4 MiB, and
                           `docker update` refuses a decrease below current usage;
  * SILENTLY LOWERED prometheus from a live 1.5 GiB ceiling to 1 GiB (and its CPU
                           allowance from 2.0 to 1.0);
  * mutated container NETWORKING on the `coolify` network, renamed to `fabrik` on
                           2026-05-31 — one day after that script was last touched.

So these tests are not about arithmetic. They pin the three properties that make an applier
safe to point at live production: it never lowers a ceiling, it does not mutate unless told
to, and it counts DEFINED containers rather than running ones.

The harness fakes `sudo docker` on PATH against a text fixture, so the real command surface
(`inspect -f`, `ps -aq`, `update --memory`) is exercised without a Docker daemon.

Point VPS_LIMITS_SCRIPT at any candidate to grade it — that is how the red-on-revert proof
runs the OLD script through this suite without ever mutating the working tree.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("VPS_LIMITS_SCRIPT", REPO / "scripts" / "vps_apply_limits.sh"))

# name -> (container id, HostConfig.Memory in bytes)
MIB = 1024 * 1024
LIVE_TODAY = {
    "cadvisor": 0, "loki": 0, "promtail": 0, "grafana": 0, "traefik": 0,
    "alertmanager": 0, "postgres-exporter": 0, "node-exporter": 0,
    "redis-exporter": 0, "redis-main": 0,
    "prometheus": 1536 * MIB,          # the container the old script would have shrunk
    "postgres-main": 2048 * MIB,
}

FAKE_DOCKER = r'''#!/usr/bin/env python3
import os, sys
STATE = os.environ["FAKE_DOCKER_STATE"]
CALLS = os.environ["FAKE_DOCKER_CALLS"]

def load():
    out = {}
    for line in open(STATE):
        line = line.strip()
        if line:
            name, cid, mem = line.split()
            # mem stays a STRING: the harness must be able to represent an UNREADABLE limit
            # (the exact input that used to defeat the never-lower guard), not crash on it.
            out[name] = [cid, mem]
    return out

def save(d):
    with open(STATE, "w") as fh:
        for name, (cid, mem) in d.items():
            fh.write(f"{name} {cid} {mem}\n")

a = sys.argv[1:]
with open(CALLS, "a") as fh:
    fh.write(" ".join(a) + "\n")
d = load()

if a[0] == "ps":
    for name, (cid, _m) in d.items():
        print(cid)
    sys.exit(0)

if a[0] == "inspect":
    if a[1] == "-f":
        fmt, ref = a[2], a[3]
        hit = None
        for name, (cid, mem) in d.items():
            if ref in (name, cid):
                hit = (name, cid, mem); break
        if hit is None:
            sys.exit(1)
        name, cid, mem = hit
        print({"{{.HostConfig.Memory}}": str(mem),
               "{{.Name}}": "/" + name,
               "{{.Id}}": cid}[fmt])
        sys.exit(0)
    sys.exit(0 if a[1] in d else 1)

if a[0] == "update":
    forced = os.environ.get("FAKE_DOCKER_UPDATE_ERROR", "")
    if forced:
        print(forced, file=sys.stderr); sys.exit(1)
    warn = os.environ.get("FAKE_DOCKER_UPDATE_WARNING", "")
    if warn:
        print(warn, file=sys.stderr)   # writes to stderr but SUCCEEDS
    mem = None; target = None
    i = 1
    while i < len(a):
        if a[i] == "--memory": mem = a[i + 1]; i += 2
        elif a[i] == "--memory-swap": i += 2
        elif a[i].startswith("--"): i += 2
        else: target = a[i]; i += 1
    want = int(mem.rstrip("m")) * 1024 * 1024
    try:
        cur = int(d[target][1])
    except ValueError:
        cur = 0
    # Docker refuses a decrease below the container's current usage. The fixture has no
    # usage, so model the stricter real-world rule: refuse ANY decrease.
    if cur and want < cur:
        print("cannot decrease", file=sys.stderr); sys.exit(1)
    d[target][1] = str(want)
    save(d)
    sys.exit(0)

sys.exit(0)
'''


@pytest.fixture
def env(tmp_path):
    """A fake `sudo docker` on PATH, plus a mutable container-state fixture."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "docker").write_text(FAKE_DOCKER)
    (bindir / "docker").chmod(0o755)
    (bindir / "sudo").write_text('#!/bin/bash\nexec "$@"\n')
    (bindir / "sudo").chmod(0o755)

    state = tmp_path / "state.txt"
    calls = tmp_path / "calls.txt"
    calls.write_text("")

    def write_state(mapping):
        state.write_text(
            "".join(f"{n} c{i:012d} {m}\n" for i, (n, m) in enumerate(mapping.items()))
        )

    write_state(LIVE_TODAY)

    def run(*args, update_error: str = "", update_warning: str = ""):
        e = dict(os.environ)
        e["PATH"] = f"{bindir}:{os.environ['PATH']}"
        e["FAKE_DOCKER_STATE"] = str(state)
        e["FAKE_DOCKER_CALLS"] = str(calls)
        e["FAKE_DOCKER_UPDATE_ERROR"] = update_error
        e["FAKE_DOCKER_UPDATE_WARNING"] = update_warning
        return subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=e, timeout=20
        )

    def limits():
        return {
            ln.split()[0]: int(ln.split()[2])
            for ln in state.read_text().splitlines() if ln.strip()
        }

    ns = type("Env", (), {})()
    ns.run, ns.limits, ns.write_state = run, limits, write_state
    ns.updates = lambda: [
        ln for ln in calls.read_text().splitlines() if ln.startswith("update")
    ]
    return ns


def test_it_does_not_mutate_unless_asked(env):
    """DRY RUN BY DEFAULT. A script that points at live production and mutates on a bare
    invocation is one tab-completion away from an unreviewed change."""
    before = env.limits()
    r = env.run()

    assert r.returncode == 0, r.stderr
    assert env.updates() == [], f"a bare run issued mutations: {env.updates()}"
    assert env.limits() == before
    assert "would SET" in r.stdout


def test_apply_sets_every_unbounded_container(env):
    r = env.run("--apply")

    assert r.returncode == 0, r.stderr
    got = env.limits()
    assert got["redis-main"] == 640 * MIB, "redis-main FORKS on BGSAVE/AOF — 640M is the COW ceiling"
    assert got["promtail"] == 256 * MIB, "promtail is page-cache heavy; 128m is below its working set"
    assert got["traefik"] == 256 * MIB
    assert got["cadvisor"] == 512 * MIB
    assert "0 of 12 containers unbounded" in r.stdout


def test_it_never_lowers_an_existing_ceiling(env):
    """THE hazard. prometheus runs with a live 1.5 GiB ceiling; nothing in this applier's
    table may cut it. The predecessor would have — silently, with a ✅."""
    env.write_state({**LIVE_TODAY, "loki": 1024 * MIB})  # already above the 512M target

    r = env.run("--apply")

    assert env.limits()["loki"] == 1024 * MIB, "an existing higher ceiling was LOWERED"
    assert env.limits()["prometheus"] == 1536 * MIB, "an unmanaged container was touched"
    assert not any("loki" in u for u in env.updates()), "issued a needless call on a compliant container"
    assert "OK" in r.stdout and "already ≥ target" in r.stdout


def test_a_ceiling_below_target_is_raised_not_skipped(env):
    """Never-lowering must not degrade into never-acting: a too-LOW ceiling is still a defect."""
    env.write_state({**LIVE_TODAY, "traefik": 64 * MIB})

    r = env.run("--apply")

    assert env.limits()["traefik"] == 256 * MIB
    assert "RAISE" in r.stdout


def test_rerunning_after_a_full_pass_is_a_silent_no_op(env):
    """Spec C5: vps1 SSH is intermittent, so a re-run must cost nothing and never double-apply."""
    env.run("--apply")
    calls_after_first = len(env.updates())

    r = env.run("--apply")

    assert len(env.updates()) == calls_after_first, "a second pass re-issued calls"
    assert "set=0 raised=0 ok=10" in r.stdout
    assert r.returncode == 0


def test_check_mode_fails_while_anything_is_unbounded(env):
    """Part C. The check must be usable as a gate — a green exit while a container is
    unbounded is the exact silence this whole change exists to end."""
    red = env.run("--check")
    assert red.returncode == 1, "reported success with 10 unbounded containers"
    assert "10 of 12 containers unbounded" in red.stdout

    env.run("--apply")
    green = env.run("--check")
    assert green.returncode == 0, green.stdout
    assert "every defined container has a memory ceiling" in green.stdout


def test_it_counts_defined_containers_not_running_ones(env):
    """`docker ps -aq`, not `-q`. A stopped-but-defined container keeps HostConfig.Memory
    across a restart, so a check reading only the running set reports green while an
    unbounded container waits to be started."""
    src = SCRIPT.read_text()
    assert "ps -aq" in src
    assert "$D ps -q" not in src and "docker ps -q" not in src


def test_an_unknown_flag_is_refused_rather_than_treated_as_a_dry_run(env):
    """A typo'd `--aply` must not silently become the safe path AND must not become the
    dangerous one — it must stop."""
    r = env.run("--aply")

    assert r.returncode == 64
    assert env.updates() == []


def test_the_recurrence_check_is_wired_into_the_fleet_health_sweep():
    """A check nobody runs is a comment. proactive-check.sh runs every 15 minutes on each
    host and already carries the sibling `oom_kill` trigger, so it is where this belongs."""
    sweep = (REPO / "scripts" / "sysadmin" / "proactive-check.sh").read_text()

    assert "container_no_memory_limit" in sweep, "the recurrence check is not wired anywhere"
    # A dead daemon must not read as a clean bill of health: `docker ps -aq` on an unreachable
    # daemon returns empty and exits nonzero, which is indistinguishable from "no containers".
    # Without this branch the check reports GREEN on a host whose Docker is gone, and its silence
    # is supposed to carry information.
    assert "docker_daemon_unreachable" in sweep, "a dead docker daemon would report green"
    assert 'if ! _ids=$(sudo docker ps -aq' in sweep, "the daemon failure is not detected at all"
    assert "docker ps -aq" in sweep, "the sweep reads only running containers"
    # It must land in ANOMALIES, which is what actually reaches the operator.
    assert 'ANOMALIES+="container_no_memory_limit' in sweep


def _spec_ceilings() -> dict[str, int]:
    """Parse the spec's ceiling table into {container: MiB}.

    The predecessor of this helper asserted `f"{mib}M" in spec`, which is why it existed at all:
    that disjunct matched "512M" ANYWHERE in a 380-line document, so changing the spec's cadvisor
    row from 512M to 256M — a genuine spec-vs-script divergence — left the test GREEN. Proven by
    mutation during the review that added this. A test that cannot fail is worse than no test,
    because it is counted as coverage.
    """
    spec = (REPO / "docs" / "superpowers" / "specs"
            / "2026-09-04-vps1-container-memory-limits-design.md").read_text()
    rows = re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|[^|]*\|\s*(\d+)M\s*\|", spec, re.M)
    return {name: int(mib) for name, mib in rows}


def _script_ceilings() -> dict[str, int]:
    """Parse the applier's own table, so both sides are read rather than hardcoded here."""
    out, inside = {}, False
    for ln in SCRIPT.read_text().splitlines():
        if ln.startswith("CEILINGS="):
            inside = True
            continue
        if inside:
            if ln.startswith('"'):
                break
            body = ln.split("#")[0].strip()
            if body:
                name, mib = body.split()[:2]
                out[name] = int(mib)
    return out


def test_the_ceilings_match_the_converged_spec():
    """The numbers are reviewed in the spec, not chosen in the script. Both tables are PARSED and
    compared as sets of pairs, so any divergence in either direction is red."""
    spec, script = _spec_ceilings(), _script_ceilings()

    assert script, "the applier's ceiling table did not parse — the test cannot grade anything"
    missing = sorted(set(script) - set(spec))
    assert not missing, f"applier bounds containers the spec never reviewed: {missing}"

    mismatched = {n: (script[n], spec[n]) for n in script if spec[n] != script[n]}
    assert not mismatched, f"script vs spec ceiling disagreement (script, spec): {mismatched}"

    # The ten the spec actually decided must all be carried, or the applier silently under-covers.
    assert len(script) == 10, f"expected the spec's ten ceilings, parsed {len(script)}: {sorted(script)}"


def test_an_unreadable_limit_is_skipped_rather_than_overwritten(env):
    """FAIL CLOSED. `[ "" -ge N ]` ERRORS rather than returning false, so an empty limit read used
    to fall straight through to an update at the table's target — which, on a container whose real
    ceiling was higher, would have LOWERED it. Docker offers no never-lower guarantee of its own
    (it refuses only a decrease below current usage), so this comparison is the only thing there is.
    """
    env.write_state({**LIVE_TODAY, "traefik": "garbage"})

    r = env.run("--apply")

    assert "UNREADABLE" in r.stdout, "acted on a container whose limit it could not read"
    assert not any("traefik" in u for u in env.updates()), "issued an update on an unreadable limit"
    assert r.returncode == 1, "an unreadable limit must not exit clean"


def test_a_failure_reports_dockers_own_message_not_a_guessed_cause(env):
    """The failure line used to ASSERT 'a decrease below current usage is refused' while discarding
    stderr entirely — a plausible invented mechanism, which is the hardest kind of wrong to catch."""
    marker = "SENTINEL: the daemon's own words"

    r = env.run("--apply", update_error=marker)

    assert marker in r.stdout, "the failure line invented a cause instead of quoting Docker"
    assert "a decrease below current usage is refused" not in r.stdout


def test_a_warning_on_stderr_is_not_mistaken_for_a_failure(env):
    """`docker update --memory-swap` provokes "WARNING: Your kernel does not support swap limit
    capabilities" on many kernels — while SUCCEEDING. An earlier fix here captured stderr to stop the
    script inventing a failure cause, and in doing so began branching on "stderr is non-empty", which
    would turn every successful apply on such a kernel into a red run. Branch on the exit code."""
    warning = "WARNING: Your kernel does not support swap limit capabilities"

    r = env.run("--apply", update_warning=warning)

    assert r.returncode == 0, f"a warning was treated as failure:\n{r.stdout}"
    assert "FAILED" not in r.stdout
    assert env.limits()["redis-main"] == 640 * MIB, "the update did not actually land"
    assert warning in r.stdout, "the warning was swallowed instead of surfaced"


def test_the_compose_files_declare_the_same_ceilings_the_applier_asserts():
    """PART B. `docker update` does not persist for compose-managed containers, so the in-place
    ceilings survive only until the next `up -d`. The durable half is a
    `deploy.resources.limits.memory` declaration in each stack's compose — and it has to agree with
    the applier and the spec, or a redeploy silently MOVES a ceiling instead of preserving it.

    Three sources must say the same thing: the spec (reviewed), the applier (live enforcement), and
    the compose (what survives a recreate). This pins the third against the first two.
    """
    import yaml

    composes = {
        "infra/vps1/traefik/compose.yaml": ["traefik"],
        "infra/vps1/redis/compose.yaml": ["redis-main"],
        "infra/vps1/monitoring/compose.yaml": [
            "loki", "promtail", "alertmanager", "node-exporter",
            "cadvisor", "grafana", "postgres-exporter", "redis-exporter",
        ],
    }
    expected = _script_ceilings()

    declared: dict[str, int] = {}
    for rel, names in composes.items():
        path = REPO / rel
        assert path.exists(), f"{rel} is GONE — the stack lost its repo-of-record"
        doc = yaml.safe_load(path.read_text())
        services = doc.get("services") or {}
        for name in names:
            assert name in services, (
                f"{rel} no longer defines service {name!r} (has: {sorted(services)}) — "
                "renamed or removed, and its ceiling went with it"
            )
            svc = services[name]
            limits = svc.get("deploy", {}).get("resources", {}).get("limits", {})
            mem = limits.get("memory")
            assert mem, f"{rel}:{name} declares NO memory limit — a redeploy unbounds it again"
            # THE UNIT IS LOAD-BEARING. Compose reads a bare integer as BYTES, so `memory: 256`
            # is 256 bytes and would OOM-kill the container instantly — yet a naive
            # `int(str(mem).rstrip("M"))` parses it to 256 and compares EQUAL to an expected
            # 256 MiB, passing the test on a catastrophic misconfiguration. Demand the suffix.
            assert re.fullmatch(r"\d+M", str(mem)), (
                f"{rel}:{name} memory is {mem!r}; this table is written in whole MiB with an "
                "explicit M suffix. A bare integer means BYTES to compose, and a differing unit "
                "would compare equal to the applier's number while meaning something else"
            )
            # container_name is what the applier and `docker inspect` key on, not the service key
            declared[svc.get("container_name", name)] = int(str(mem).rstrip("M"))

    assert declared == expected, (
        "compose declarations disagree with the applier's table "
        f"(compose, applier): { {k: (declared.get(k), expected.get(k)) for k in set(declared) | set(expected) if declared.get(k) != expected.get(k)} }"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
def test_the_script_is_syntactically_valid():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
