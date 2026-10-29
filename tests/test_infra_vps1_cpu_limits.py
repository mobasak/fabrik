# AFTER-EDIT: none
"""W-91a4a715, W-1e9cd280 — every service in the hub's infra repo-of-record composes (every `infra/vps*/`
host: vps1 and the vps2/vps3 spokes) declares a memory and a CPU limit.

`.windsurf/rules/core/30-ops.md` mandates `deploy.resources.limits.memory` + `cpus`. `fabrik apply`'s
`deployer_ssh._validate_compose()` enforces them for app deploys, but `infra/` never passes through
`fabrik apply`, so nothing graded either half here: 22 vps1 services ran with no CPU cap (cAdvisor,
2026-10-29) and both spoke traefiks carried no limit at all. The tier values are the decision rows'
tables (D-1324, D-1357), not pinned here a second time. The file keeps its vps1 name because
`scripts/sysadmin/vps1_cpu_limits.py` cites it as the home of the cpus grammar.

The grammar is strict and fails closed: PyYAML reads `yes` as a bool (float() gives 1.0) and `0_5` as
int 5. docker compose 2.40.3 refuses `yes` but reads `0_5`, quoted or bare, as 5 CPUs — so a lenient
float() would grade GREEN a file the VPS cannot apply, or one whose typo grants ten times the cap.
Parses YAML only; never touches a live host.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
INFRA = REPO / "infra"
# CPUs per host: count by (instance) (node_cpu_seconds_total{mode="idle"}) on the hub Prometheus,
# 2026-10-29 — node-exporter:9100 6, 10.99.0.2:9100 (vps2) 4, 10.99.0.3:9100 (vps3) 4. A host directory
# missing here fails the population test, never grades open.
HOST_CPUS = {"vps1": 6, "vps2": 4, "vps3": 4}
# D-1324's protection is that no single container takes more than 2 CPUs, and never more than half its
# host — so a whole-host cap (`6` on vps1, `2.0` on a 2-CPU host), which limits nothing, is refused.
MAX_CPUS = 2.0


def host_max_cpus(host: str) -> float:
    """The cpus ceiling on `host`: 2.0, or half the host when that is smaller."""
    return min(MAX_CPUS, HOST_CPUS[host] / 2)

# (file relative to infra/, exact service set) -> the item that removes the exception.
EXCEPTIONS: dict[tuple[str, frozenset[str]], str] = {
    (
        "vps1/ocoron-com/compose.yaml",
        frozenset({"wordpress", "nginx", "db", "redis", "backup"}),
    ): "W-78649ed2",  # no deploy.resources at all — memory and CPU sized together there
}

_DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?")
# The only memory spelling these composes use (census of all 33 values, 2026-10-29: 64M..3G). Compose
# accepts more (`1g`, `512mb`, a bare byte count); this grade is stricter on purpose and fails closed.
_MEMORY = re.compile(r"[1-9][0-9]*[MG]")


def cpu_limit_problem(value: object, ceiling: float = MAX_CPUS) -> str | None:
    """Return why `value` is not a usable `deploy.resources.limits.cpus` under `ceiling`, or None."""
    if value is None:
        return "no deploy.resources.limits.cpus"
    if isinstance(value, bool):
        return f"cpus {value!r} is a YAML boolean, not a CPU count"
    if isinstance(value, (int, float)) or isinstance(value, str) and _DECIMAL.fullmatch(value):
        number = float(value)
    else:
        return f"cpus {value!r} is not a plain decimal"
    if not 0 < number <= ceiling:
        return f"cpus {value!r} is outside 0 < cpus <= {ceiling}"
    return None


def memory_limit_problem(value: object) -> str | None:
    """Return why `value` is not a usable `deploy.resources.limits.memory`, or None when it is."""
    if value is None:
        return "no deploy.resources.limits.memory"
    if isinstance(value, str) and _MEMORY.fullmatch(value):
        return None
    return f"memory {value!r} is not a plain size like 256M or 2G"


def _duplicate_key(node: yaml.Node, seen: set[int] | None = None) -> str | None:
    """The first mapping key compose would refuse anywhere in the document: one that occurs twice (PyYAML
    keeps one silently and `_child` reads the first) or a mapping/sequence used as a key (compose's
    "invalid map key", even once) — either is a file-level failure."""
    seen = set() if seen is None else seen
    if id(node) in seen:
        return None
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        keys: set[str] = set()
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                return f"non-scalar key at line {key_node.start_mark.line + 1}"
            if key_node.value in keys:
                return f"duplicate key {key_node.value!r} at line {key_node.start_mark.line + 1}"
            keys.add(key_node.value)
            found = _duplicate_key(value_node, seen)
            if found:
                return found
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            found = _duplicate_key(item, seen)
            if found:
                return found
    return None


def _child(node: yaml.Node | None, key: str) -> yaml.Node | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return value_node
    return None


def _limit_scalar(service: yaml.Node, limit: str) -> object:
    """A limits value as the YAML TEXT spelled it: a quoted scalar stays a str; a plain one keeps its
    raw text unless it resolved to a bool — so a bare `0_5` (int 5 to PyYAML) is graded as "0_5"."""
    node: yaml.Node | None = service
    for key in ("deploy", "resources", "limits", limit):
        node = _child(node, key)
    if node is None:
        return None
    if not isinstance(node, yaml.ScalarNode):
        return [node]  # a mapping or sequence — not a limit value
    if node.tag == "tag:yaml.org,2002:bool":
        return True
    if node.tag == "tag:yaml.org,2002:null":
        return None
    return node.value


def compose_problems(text: str, ceiling: float = MAX_CPUS) -> dict[str, str]:
    """Map each service of one compose text to its limit problems (services with none are omitted)."""
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    duplicate = _duplicate_key(root) if root is not None else None
    if duplicate:
        return {"<file>": duplicate}
    services = _child(root, "services")
    if not isinstance(services, yaml.MappingNode) or not services.value:
        return {"<file>": "no services mapping"}
    problems: dict[str, str] = {}
    for name_node, service in services.value:
        found = [
            problem
            for problem in (
                memory_limit_problem(_limit_scalar(service, "memory")),
                cpu_limit_problem(_limit_scalar(service, "cpus"), ceiling),
            )
            if problem
        ]
        if found:
            problems[str(name_node.value)] = "; ".join(found)
    return problems


def _composes(root: Path = INFRA) -> list[Path]:
    # Every host directory (vps1, vps2, … — a new spoke is picked up) and every compose spelling at any
    # depth (compose.yml, docker-compose.yaml, a nested stack), so nothing added is silently skipped.
    return sorted(
        path
        for host in root.glob("vps*")
        if host.is_dir()
        for path in host.rglob("*.y*ml")
        if "compose" in path.name
    )


def test_every_compose_spelling_on_every_host_is_in_the_population(tmp_path: Path) -> None:
    """Given stacks named compose.yml, docker-compose.yaml and a nested compose.yaml on two hosts, and a
    compose outside any host directory, when the population is collected, then exactly the host ones are
    graded."""
    names = ["vps1/a/compose.yml", "vps1/b/docker-compose.yaml", "vps7/c/d/compose.yaml"]
    for name in [*names, "shared/compose.yaml"]:
        (tmp_path / name).parent.mkdir(parents=True)
        (tmp_path / name).write_text("services: {}\n")
    assert [p.relative_to(tmp_path).as_posix() for p in _composes(tmp_path)] == names


def test_the_population_spans_every_host() -> None:
    """Given the repo, when infra/ is globbed, then vps1 holds its 16 stack composes and each spoke its 3
    (a moved directory must not turn every assertion below into a pass over nothing)."""
    hosts: dict[str, int] = {}
    for path in _composes():
        host = path.relative_to(INFRA).parts[0]
        hosts[host] = hosts.get(host, 0) + 1
    assert hosts.get("vps1", 0) >= 16
    assert hosts.get("vps2", 0) >= 3
    assert hosts.get("vps3", 0) >= 3
    assert set(hosts) <= set(HOST_CPUS), f"add {sorted(set(hosts) - set(HOST_CPUS))} to HOST_CPUS"


@pytest.mark.parametrize(("host", "ceiling"), [("vps1", 2.0), ("vps2", 2.0), ("vps3", 2.0)])
def test_each_host_ceiling_is_two_or_half_the_host(host: str, ceiling: float) -> None:
    """Given each known host, when its cpus ceiling is derived, then it is 2.0 or half its CPUs if smaller."""
    assert host_max_cpus(host) == ceiling


def test_a_small_host_refuses_a_whole_host_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a 2-CPU host, when a service declares cpus 2.0 (the whole host), then it is refused, and 1.0
    passes — the ceiling is half the host there, not D-1324's flat 2.0."""
    monkeypatch.setitem(HOST_CPUS, "vps9", 2)
    text = "services:\n  a:\n    deploy: {resources: {limits: {memory: 64M, cpus: '%s'}}}\n"
    assert compose_problems(text % "2.0", host_max_cpus("vps9")) == {"a": "cpus '2.0' is outside 0 < cpus <= 1.0"}
    assert compose_problems(text % "1.0", host_max_cpus("vps9")) == {}


def test_every_infra_service_declares_memory_and_cpu_limits() -> None:
    """Given every infra/vps*/ compose, when each service is read, then each declares a plain-size
    deploy.resources.limits.memory and a usable cpus, except the exact excepted service sets."""
    excepted = {file for file, _ in EXCEPTIONS}
    failures = {}
    for path in _composes():
        rel = path.relative_to(INFRA).as_posix()
        if rel in excepted:
            continue
        problems = compose_problems(path.read_text(), host_max_cpus(rel.split("/")[0]))
        if problems:
            failures[rel] = problems
    assert failures == {}


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        "0",
        -1,
        "-1",
        7,
        "6.5",
        "6",
        "2.01",
        3,
        True,
        "yes",
        "0_5",
        " 1 ",
        "1e0",
        "0x2",
        "half",
        [1],
        {"a": 1},
    ],
)
def test_bad_cpu_values_are_refused(value: object) -> None:
    """Given a cpus value that is absent, zero, negative, above D-1324's 2-CPU ceiling (a whole-host
    `6` included), a boolean, an underscore/whitespace/exponent/hex spelling or other text, when
    graded, then it is refused."""
    assert cpu_limit_problem(value) is not None


@pytest.mark.parametrize("value", [0.25, 1, "0.5", "2.0", "2"])
def test_good_cpu_values_are_accepted(value: object) -> None:
    """Given a plain positive decimal no greater than 2.0, when graded, then it passes."""
    assert cpu_limit_problem(value) is None


@pytest.mark.parametrize(
    "value",
    [None, True, 256, "", "0M", "064M", "256", "256m", "1g", "512Mi", "512MB", " 64M", "64M ", "1.5G", [1]],
)
def test_bad_memory_values_are_refused(value: object) -> None:
    """Given a memory value that is absent, a boolean, a bare number, zero, zero-padded, lower-case, a
    two-letter or binary unit, padded or fractional, or a sequence, when graded, then it is refused."""
    assert memory_limit_problem(value) is not None


@pytest.mark.parametrize("value", ["64M", "256M", "1536M", "2G", "3G"])
def test_good_memory_values_are_accepted(value: object) -> None:
    """Given a plain positive whole number of M or G, when graded, then it passes."""
    assert memory_limit_problem(value) is None


@pytest.mark.parametrize(
    "text",
    [
        "services:\n  a:\n    deploy: {resources: {limits: {cpus: '1', cpus: '1'}}}\n",
        "services:\n  a:\n    deploy: {resources: {limits: {cpus: '1'}}}\n    deploy: {}\n",
        "services:\n  a:\n    deploy: {resources: {limits: {cpus: '1'}}}\n  a:\n    image: x\n",
        "services:\n  a:\n    deploy: {resources: {limits: {cpus: '1'}}}\nservices:\n  b: {image: x}\n",
    ],
)
def test_a_duplicate_key_fails_the_file(text: str) -> None:
    """Given a compose with a key repeated at any level (compose refuses it; PyYAML keeps one silently),
    when graded, then the file fails naming the duplicate — even when the copy read first is valid."""
    problems = compose_problems(text)
    assert list(problems) == ["<file>"]
    assert problems["<file>"].startswith("duplicate key")


@pytest.mark.parametrize("key", ["[k]", "{k: 1}"])
def test_a_non_scalar_key_fails_the_file(key: str) -> None:
    """Given a compose with a sequence or mapping used as a key — once (compose: "invalid map key") or
    twice — when graded, then the file fails, though its limits lines are valid."""
    once = f"services:\n  a:\n    deploy: {{resources: {{limits: {{memory: 64M, cpus: '1'}}}}}}\n    {key}: v\n"
    twice = once + f"    {key}: w\n"
    for text in (once, twice):
        problems = compose_problems(text)
        assert list(problems) == ["<file>"]
        assert problems["<file>"].startswith("non-scalar key")


def test_yaml_spellings_are_graded_on_their_scalar_text() -> None:
    """Given compose text, when PyYAML parses a bare `yes` (compose refuses it) or `0_5` (compose reads
    it as 5 CPUs), or a service has cpus but no memory, then the grader still refuses the service and
    names it."""
    text = (
        "services:\n  a:\n    deploy: {resources: {limits: {memory: 64M, cpus: yes}}}\n"
        "  b:\n    deploy: {resources: {limits: {memory: 64M, cpus: 0_5}}}\n"
        "  c:\n    deploy: {resources: {limits: {memory: 64M}}}\n"
        "  d:\n    image: x\n"
        "  e:\n    deploy: {resources: {limits: {cpus: '0.5'}}}\n"
        "  f:\n    deploy: {resources: {limits: {memory: 64M, cpus: '0.5'}}}\n"
    )
    problems = compose_problems(text)
    assert set(problems) == {"a", "b", "c", "d", "e"}
    assert problems["e"] == "no deploy.resources.limits.memory"
    assert problems["d"] == "no deploy.resources.limits.memory; no deploy.resources.limits.cpus"


def test_a_file_without_a_services_mapping_fails() -> None:
    """Given a YAML file with no `services:` mapping, when graded, then the file itself fails."""
    assert compose_problems("x: 1\n") == {"<file>": "no services mapping"}


@pytest.mark.parametrize(
    ("rel", "service", "marker", "problem"),
    [
        ("vps1/gatus/compose.yaml", "gatus", "cpus:", "no deploy.resources.limits.cpus"),
        ("vps2/traefik/compose.yaml", "traefik", "cpus:", "no deploy.resources.limits.cpus"),
        ("vps3/traefik/compose.yaml", "traefik", "memory:", "no deploy.resources.limits.memory"),
    ],
)
def test_a_real_compose_with_a_limit_line_removed_is_refused(rel: str, service: str, marker: str, problem: str) -> None:
    """Given a real block-style infra compose (the hub and a spoke), when its `cpus:` or `memory:` line is
    deleted, then the grader names that service — so the real-file scan is not green only because it reads
    nothing."""
    text = (INFRA / rel).read_text()
    assert compose_problems(text) == {}
    stripped = "".join(line for line in text.splitlines(keepends=True) if marker not in line)
    assert stripped != text
    assert compose_problems(stripped) == {service: problem}


def test_exception_is_exact_and_expires() -> None:
    """Given each exception, when its file is read, then the file exists, its service set is exactly
    the excepted one, and every excepted service still lacks its limits — so the exception neither covers
    a new service nor outlives its fix."""
    for (rel, services), item in EXCEPTIONS.items():
        path = INFRA / rel
        assert path.is_file(), f"{rel} is gone — drop its exception ({item})"
        doc = yaml.safe_load(path.read_text())
        assert set(doc["services"]) == services, (
            f"{rel} services changed — re-size or re-scope ({item})"
        )
        assert set(compose_problems(path.read_text())) == services, (
            f"{rel} now declares limits on some service — drop or narrow its exception ({item})"
        )
