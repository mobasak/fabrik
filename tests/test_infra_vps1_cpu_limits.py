# AFTER-EDIT: none
"""W-91a4a715 — every service in the hub's vps1 repo-of-record composes declares a CPU limit.

`.windsurf/rules/core/30-ops.md` mandates `deploy.resources.limits.memory` + `cpus`; the memory half is
enforced at deploy time by `deployer_ssh._validate_compose()`, but `infra/vps1/` never passes through
`fabrik apply`, so nothing graded the `cpus` half and 22 of these services ran unlimited on vps1
(cAdvisor, 2026-10-29). The tier values are the decision row's table, not pinned here a second time.

The grammar is strict and fails closed: PyYAML reads `yes` as a bool (float() gives 1.0) and `0_5` as
int 5, while compose rejects both — a lenient float() would grade a file GREEN that the VPS cannot
apply. Parses YAML only; never touches a live host.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
INFRA_VPS1 = REPO / "infra" / "vps1"
# vps1 has 6 CPUs (count(node_cpu_seconds_total{mode="idle"}) on node-exporter:9100, 2026-10-29); D-1324's
# protection is that no single container takes more than 2 of them, so a cap above 2.0 — up to a whole-host
# `6`, which limits nothing — is refused, not just one above the host.
MAX_CPUS = 2.0

# (file relative to infra/vps1, exact service set) -> the item that removes the exception.
EXCEPTIONS: dict[tuple[str, frozenset[str]], str] = {
    (
        "ocoron-com/compose.yaml",
        frozenset({"wordpress", "nginx", "db", "redis", "backup"}),
    ): "W-78649ed2",  # no deploy.resources at all — memory and CPU sized together there
}

_DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?")


def cpu_limit_problem(value: object) -> str | None:
    """Return why `value` is not a usable `deploy.resources.limits.cpus`, or None when it is."""
    if value is None:
        return "no deploy.resources.limits.cpus"
    if isinstance(value, bool):
        return f"cpus {value!r} is a YAML boolean, not a CPU count"
    if isinstance(value, (int, float)) or isinstance(value, str) and _DECIMAL.fullmatch(value):
        number = float(value)
    else:
        return f"cpus {value!r} is not a plain decimal"
    if not 0 < number <= MAX_CPUS:
        return f"cpus {value!r} is outside 0 < cpus <= {MAX_CPUS}"
    return None


def _duplicate_key(node: yaml.Node, seen: set[int] | None = None) -> str | None:
    """The first mapping key that occurs twice anywhere in the document. PyYAML keeps one silently and
    `_child` reads the first, while compose refuses the file — so a duplicate is a file-level failure."""
    seen = set() if seen is None else seen
    if id(node) in seen:
        return None
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        keys: set[str] = set()
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode):
                if key_node.value in keys:
                    return (
                        f"duplicate key {key_node.value!r} at line {key_node.start_mark.line + 1}"
                    )
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


def _cpus_scalar(service: yaml.Node) -> object:
    """The cpus value as the YAML TEXT spelled it: a quoted scalar stays a str; a plain one keeps its
    raw text unless it resolved to a bool — so a bare `0_5` (int 5 to PyYAML) is graded as "0_5"."""
    node = service
    for key in ("deploy", "resources", "limits", "cpus"):
        node = _child(node, key)
    if node is None:
        return None
    if not isinstance(node, yaml.ScalarNode):
        return [node]  # a mapping or sequence — not a CPU count
    if node.tag == "tag:yaml.org,2002:bool":
        return True
    if node.tag == "tag:yaml.org,2002:null":
        return None
    return node.value


def compose_problems(text: str) -> dict[str, str]:
    """Map each service of one compose text to its CPU-limit problem (services with none are omitted)."""
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    duplicate = _duplicate_key(root) if root is not None else None
    if duplicate:
        return {"<file>": duplicate}
    services = _child(root, "services")
    if not isinstance(services, yaml.MappingNode) or not services.value:
        return {"<file>": "no services mapping"}
    problems: dict[str, str] = {}
    for name_node, service in services.value:
        problem = cpu_limit_problem(_cpus_scalar(service))
        if problem:
            problems[str(name_node.value)] = problem
    return problems


def _composes() -> list[Path]:
    return sorted(INFRA_VPS1.glob("*/compose.yaml"))


def test_the_population_is_not_empty() -> None:
    """Given the repo, when infra/vps1 is globbed, then it holds the 16 stack composes (a moved
    directory must not turn every assertion below into a pass over nothing)."""
    assert len(_composes()) >= 16


def test_every_infra_vps1_service_declares_a_cpu_limit() -> None:
    """Given every infra/vps1/*/compose.yaml, when each service is read, then each declares a
    usable deploy.resources.limits.cpus, except the exact excepted service sets."""
    excepted = {file for file, _ in EXCEPTIONS}
    failures = {}
    for path in _composes():
        rel = path.relative_to(INFRA_VPS1).as_posix()
        if rel in excepted:
            continue
        problems = compose_problems(path.read_text())
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


def test_yaml_spellings_reach_the_grader_as_compose_would_refuse_them() -> None:
    """Given compose text, when PyYAML parses a bare `yes` or `0_5`, then the grader still refuses
    the service and names it."""
    text = (
        "services:\n  a:\n    deploy: {resources: {limits: {memory: 64M, cpus: yes}}}\n"
        "  b:\n    deploy: {resources: {limits: {memory: 64M, cpus: 0_5}}}\n"
        "  c:\n    deploy: {resources: {limits: {memory: 64M}}}\n"
        "  d:\n    image: x\n"
    )
    assert set(compose_problems(text)) == {"a", "b", "c", "d"}
    assert compose_problems("x: 1\n") == {"<file>": "no services mapping"}


def test_exception_is_exact_and_expires() -> None:
    """Given each exception, when its file is read, then the file exists, its service set is exactly
    the excepted one, and every excepted service still lacks cpus — so the exception neither covers a
    new service nor outlives its fix."""
    for (rel, services), item in EXCEPTIONS.items():
        path = INFRA_VPS1 / rel
        assert path.is_file(), f"{rel} is gone — drop its exception ({item})"
        doc = yaml.safe_load(path.read_text())
        assert set(doc["services"]) == services, (
            f"{rel} services changed — re-size or re-scope ({item})"
        )
        assert set(compose_problems(path.read_text())) == services, (
            f"{rel} now declares cpus on some service — drop or narrow its exception ({item})"
        )
