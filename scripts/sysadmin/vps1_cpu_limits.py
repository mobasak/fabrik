#!/usr/bin/env python3
# AFTER-EDIT: docs/SERVICES.md
"""vps1 CPU limits, D-1324's live step: apply the hub's caps to the running containers and their live composes.

Operator-run (the coordinator's deploy gate for W-91a4a715). Run from the hub main checkout:

    cd /opt/fabrik && python3 -I scripts/sysadmin/vps1_cpu_limits.py            # dry run: reads only
    cd /opt/fabrik && python3 -I scripts/sysadmin/vps1_cpu_limits.py --apply    # two blocks, each asks for `yes`

The caps come from the hub repo-of-record composes (infra/vps1/*/compose.yaml, graded by
tests/test_infra_vps1_cpu_limits.py). Per container, read with one `docker inspect`:
- runtime: unlimited (NanoCpus, CpuQuota and CpuPeriod all 0) -> UPDATE with `docker update --cpus` (no restart);
  already at the table value -> OK; any other CPU setting -> DIFFERS, reported and never changed (the engine
  refuses NanoCpus beside a CpuQuota, measured) · not found -> MISSING.
- file: for UPDATE and OK only, the live compose named by the container's own config_files label, which must be one
  /opt/<dir>/compose.yaml — the only file fabrik-compose-boot.sh reads — else MANUAL. The `cpus:` line is computed on
  the hub by insert_cpus() and written with an old-hash check, a backup, a new-hash check and an atomic mv; compose's
  own `config` is run before and after, and the whole config must be unchanged apart from those cpus keys, else the
  backup is restored. The config JSON is never printed: it holds the interpolated .env.

Never `up`, `restart`, `stop`, `rm`, `create` or `kill`: the edited file takes over at the next `up -d` or reboot,
and an `up -d` after the edit recreates the container (measured). Re-runnable: an applied cap reads OK and an inserted
line is a no-op. Exit 1 when anything was DIFFERS, MISSING, MANUAL or REFUSED.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

import yaml

SSH = ["ssh", "-o", "ProxyJump=vps2", "-o", "ConnectTimeout=20", "vps"]
HUB = Path(__file__).resolve().parents[2]
INFRA_VPS1 = HUB / "infra" / "vps1"
STAMP = time.strftime("%Y%m%d-%H%M%S")

# D-1324: no container takes more than 2 of vps1's 6 CPUs; the grammar is tests/test_infra_vps1_cpu_limits.py's.
MAX_CPUS = Decimal("2.0")
_DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?")
# exactly the set the boot glob /opt/*/compose.yaml reads: one absolute path, a non-dot directory, no override
_BOOT_FILE = re.compile(r"/opt/[^/.][^/]*/compose\.yaml")
# a service-level CPU key beside limits.cpus: compose accepts the file, the engine refuses it at create (measured)
_CPU_KEYS = (
    "cpus",
    "cpu_quota",
    "cpu_period",
    "cpu_count",
    "cpu_percent",
    "cpu_rt_runtime",
    "cpu_rt_period",
)
# YAML line breaks other than \n: they would shift PyYAML's line marks against a split on \n
_OTHER_BREAKS = ("\r", "\x85", "\u2028", "\u2029")

# argv: F old-sha256 new-sha256 stamp; the new bytes on stdin. Exits 3 when F changed since it was read, 4 when the
# bytes that arrived are not the ones sent, 5 when F is not a plain single-link file or the backup name is taken.
WRITE_SH = r"""set -eu
f=$1; old=$2; new=$3; stamp=$4
{ [ -f "$f" ] && [ ! -L "$f" ]; } || { echo "not a regular file: $f" >&2; exit 5; }
[ "$(stat -c %h "$f")" = 1 ] || { echo "hard-linked: $f" >&2; exit 5; }
[ "$(sha256sum < "$f" | cut -d' ' -f1)" = "$old" ] || { echo "changed since it was read: $f" >&2; exit 3; }
b="$f.cpu-bak-$stamp"
[ ! -e "$b" ] || { echo "backup name taken: $b" >&2; exit 5; }
t=$(mktemp "$(dirname "$f")/.compose.yaml.XXXXXX")
trap 'rm -f "$t"' EXIT
cat > "$t"
[ "$(sha256sum < "$t" | cut -d' ' -f1)" = "$new" ] || { echo "the bytes that arrived differ: $f" >&2; exit 4; }
cp -p "$f" "$b"
chmod --reference="$f" "$t"
chown --reference="$f" "$t"
mv "$t" "$f"
echo "$b"
"""
# argv: F backup old-sha256
RESTORE_SH = r"""set -eu
cp -p "$2" "$1"
[ "$(sha256sum < "$1" | cut -d' ' -f1)" = "$3" ] || { echo "restored file does not match: $1" >&2; exit 6; }
"""


class RefusedError(Exception):
    """One file or container is left alone; the reason goes into the summary."""


def die(msg: str) -> None:
    print(f"\nSTOP: {msg}", file=sys.stderr)
    sys.exit(1)


def gate(title: str, plan: str) -> None:
    print(f"\n=== {title} ===\n{plan}")
    try:
        answer = input("Type yes to run this block: ").strip()
    except EOFError:
        answer = ""
    if answer != "yes":
        die(f"not confirmed: {title} — nothing in this block ran")


class TransportError(Exception):
    """ssh could not deliver a command or its answer (timeout, no ssh, ssh's own rc 255): the remote state is unknown."""


def allowed(cmd: str) -> bool:
    """The ONLY command shapes this gate sends — an allowlist, so nothing that ups, restarts, removes or recreates a
    container can be sent by any spelling."""
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return False
    # the remote shell runs the raw string, so it must be exactly the quoted form of its tokens: a `;`, `&&`, `|`,
    # `$(` or backtick glued onto a token is a second command the token check would not see
    if shlex.join(argv) != cmd:
        return False
    if argv[:2] != ["sudo", "-n"]:
        return False
    a = argv[2:]
    return (
        (a[:4] == ["docker", "inspect", "--type", "container"] and len(a) > 4)
        or (
            len(a) == 5 and a[:3] == ["docker", "update", "--cpus"] and cpus_value(a[3]) is not None
        )
        or (
            len(a) == 7
            and a[:3] == ["docker", "compose", "-f"]
            and a[4:] == ["config", "--format", "json"]
        )
        or (len(a) == 2 and a[0] in ("cat", "sha256sum"))
        or (
            a[:2] == ["sh", "-c"]
            and a[3:4] == ["sh"]
            # WRITE_SH takes F old new stamp, RESTORE_SH takes F backup old
            and ((a[2] == WRITE_SH and len(a) == 8) or (a[2] == RESTORE_SH and len(a) == 7))
        )
    )


def run(
    cmd: str, stdin: bytes | None = None, timeout: int = 120
) -> subprocess.CompletedProcess[bytes]:
    """Run cmd on vps1. Bytes both ways, so a file is hashed and written exactly as it is. Raises TransportError
    when ssh could not deliver it, so a caller holding a written file can still restore it."""
    if not allowed(cmd):
        die(f"refusing a command this gate never sends: {cmd}")
    try:
        r = subprocess.run(SSH + [cmd], input=stdin, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TransportError(f"timed out after {timeout}s: {cmd}") from None
    except OSError as exc:
        raise TransportError(f"could not start ssh: {exc}") from None
    if r.returncode == 255:
        raise TransportError(f"ssh failed (rc 255): {_err(r)}")
    return r


def _err(r: subprocess.CompletedProcess[bytes]) -> str:
    return r.stderr.decode("utf-8", "replace").strip() or f"rc {r.returncode}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cpus_value(text: object) -> Decimal | None:
    """The CPU count a cpus scalar's TEXT spells, or None when it is not a plain decimal in (0, MAX_CPUS]."""
    if not isinstance(text, str) or not _DECIMAL.fullmatch(text):
        return None
    value = Decimal(text)
    # docker counts whole nanoCPUs, so a finer text could never read back equal (NanoCpus == cpus * 10**9)
    fraction = text.partition(".")[2]
    return value if 0 < value <= MAX_CPUS and len(fraction) <= 9 else None


def _child(node: yaml.Node | None, key: str) -> yaml.Node | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return value_node
    return None


def _entry(node: yaml.Node | None, key: str) -> tuple[yaml.Node, yaml.Node] | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return key_node, value_node
    return None


def _scalar_text(node: yaml.Node | None) -> object:
    """A scalar as the YAML text spelled it (a resolved bool stays True, so it never reads as a number)."""
    if not isinstance(node, yaml.ScalarNode):
        return node
    if node.tag == "tag:yaml.org,2002:bool":
        return True
    return node.value


def _limits(service: yaml.Node | None) -> yaml.Node | None:
    return _child(_child(_child(service, "deploy"), "resources"), "limits")


def _bad_key(node: yaml.Node, seen: set[int] | None = None) -> str | None:
    """A duplicate or non-scalar mapping key anywhere: compose refuses both, PyYAML keeps one silently."""
    seen = set() if seen is None else seen
    if id(node) in seen:
        return None
    seen.add(id(node))
    children: list[yaml.Node] = []
    if isinstance(node, yaml.MappingNode):
        keys: set[str] = set()
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                return f"non-scalar key at line {key_node.start_mark.line + 1}"
            if key_node.value in keys:
                return f"duplicate key {key_node.value!r} at line {key_node.start_mark.line + 1}"
            keys.add(key_node.value)
            children.append(value_node)
    elif isinstance(node, yaml.SequenceNode):
        children = list(node.value)
    for child in children:
        found = _bad_key(child, seen)
        if found:
            return found
    return None


def _references(root: yaml.Node) -> Counter[int]:
    """How many places in the document point at each node: an anchored node reached through an alias counts once
    per place, so a count above 1 is a node an edit would change in more than one place."""
    refs: Counter[int] = Counter()
    seen: set[int] = set()

    def walk(node: yaml.Node) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, yaml.MappingNode):
            children = [v for _, v in node.value]
        elif isinstance(node, yaml.SequenceNode):
            children = list(node.value)
        else:
            children = []
        for child in children:
            refs[id(child)] += 1
            walk(child)

    walk(root)
    return refs


def _compose(text: str) -> yaml.Node:
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise RefusedError(f"not valid YAML: {str(exc).splitlines()[0]}") from None
    if root is None:
        raise RefusedError("empty file")
    bad = _bad_key(root)
    if bad:
        raise RefusedError(bad)
    return root


def load_table(root: Path = INFRA_VPS1) -> dict[str, tuple[Decimal, str]]:
    """{container_name: (cpus, cpus text)} from every hub vps1 compose that declares cpus."""
    table: dict[str, tuple[Decimal, str]] = {}
    for path in sorted(p for p in root.rglob("*.y*ml") if "compose" in p.name):
        rel = path.relative_to(root).as_posix()
        try:
            services = _child(_compose(path.read_text(encoding="utf-8")), "services")
        except RefusedError as exc:
            raise RefusedError(f"{rel}: {exc}") from None
        if not isinstance(services, yaml.MappingNode):
            raise RefusedError(f"{rel}: no services mapping")
        for name_node, service in services.value:
            cpus = _child(_limits(service), "cpus")
            if cpus is None:
                continue
            text = _scalar_text(cpus)
            value = cpus_value(text)
            if value is None:
                raise RefusedError(
                    f"{rel}: service {name_node.value} has cpus {text!r}, not a plain decimal in (0, 2.0]"
                )
            container = _scalar_text(_child(service, "container_name"))
            if not isinstance(container, str) or not container:
                raise RefusedError(f"{rel}: service {name_node.value} has no container_name")
            if container in table:
                raise RefusedError(f"{rel}: container_name {container} is used twice")
            table[container] = (value, str(text))
    if not table:
        raise RefusedError(f"no capped service under {root}")
    return table


def runtime_plan(
    table: dict[str, tuple[Decimal, str]], inspect_stdout: bytes
) -> dict[str, tuple[str, dict]]:
    """{name: (UPDATE|OK|DIFFERS|MISSING, inspect record)}. docker inspect exits 1 when any name is missing but
    still prints the containers it found, so only stdout counts, and it must be a JSON list."""
    try:
        records = json.loads(inspect_stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RefusedError("docker inspect printed no JSON") from None
    if not isinstance(records, list):
        raise RefusedError("docker inspect did not print a JSON list")
    found = {str(r.get("Name", "")).lstrip("/"): r for r in records if isinstance(r, dict)}
    plan: dict[str, tuple[str, dict]] = {}
    for name, (value, _text) in table.items():
        record = found.get(name)
        if record is None:
            plan[name] = ("MISSING", {})
            continue
        host = record.get("HostConfig")
        if not isinstance(host, dict):
            plan[name] = ("MISSING", {})  # not a container (inspect also passes --type container)
            continue
        nano, quota, period = (int(host.get(k) or 0) for k in ("NanoCpus", "CpuQuota", "CpuPeriod"))
        if nano == quota == period == 0:
            plan[name] = ("UPDATE", record)
        elif nano == value * 10**9 and quota == 0:
            plan[name] = ("OK", record)
        else:
            plan[name] = ("DIFFERS", record)
    return plan


def boot_file(record: dict) -> str | None:
    """The live compose a container came from, when it is one the boot reads; else None (MANUAL)."""
    labels = (record.get("Config") or {}).get("Labels") or {}
    path = labels.get("com.docker.compose.project.config_files")
    return path if isinstance(path, str) and _BOOT_FILE.fullmatch(path) else None


def insert_cpus(
    data: bytes, wanted: dict[str, tuple[str, Decimal, str]]
) -> tuple[bytes, list[str]]:
    """Insert `cpus: '<text>'` under each wanted service's limits.memory line; return (new bytes, the services
    that got the line).

    `wanted` is {service: (container_name, cpus, cpus text)}. Raises RefusedError for anything the insert cannot prove
    safe; returns `data` unchanged (and no services) when every service already has an equal cpus."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise RefusedError("not UTF-8") from None
    if any(b in text for b in _OTHER_BREAKS):
        raise RefusedError("line breaks other than \\n (CRLF, NEL or a Unicode separator)")
    root = _compose(text)
    services = _child(root, "services")
    if not isinstance(services, yaml.MappingNode):
        raise RefusedError("no services mapping")
    refs = _references(root)
    inserts: list[tuple[int, str]] = []
    inserted: list[str] = []
    for name, (container, value, value_text) in sorted(wanted.items()):
        service = _child(services, name)
        if not isinstance(service, yaml.MappingNode):
            raise RefusedError(f"service {name} is not in the file (stale label)")
        if _scalar_text(_child(service, "container_name")) != container:
            raise RefusedError(f"service {name}'s container_name is not {container} (stale label)")
        for key in _CPU_KEYS:
            if _child(service, key) is not None:
                raise RefusedError(f"service {name} has a service-level {key}")
        # a merge key can carry a CPU key or a limits that the walk below would not see
        deploy = _child(service, "deploy")
        for where, node in (
            ("service", service),
            ("deploy", deploy),
            ("resources", _child(deploy, "resources")),
            ("limits", _limits(service)),
        ):
            if _child(node, "<<") is not None:
                raise RefusedError(f"service {name}'s {where} has a << merge key")
        limits = _limits(service)
        if not isinstance(limits, yaml.MappingNode):
            raise RefusedError(f"service {name} has no deploy.resources.limits mapping")
        if limits.flow_style:
            raise RefusedError(f"service {name}'s limits is a flow mapping")
        # an alias of the limits OR of any node above it (the service, its deploy, its resources) would carry the
        # inserted line into every place that alias is used
        chain = (
            service,
            _child(service, "deploy"),
            _child(_child(service, "deploy"), "resources"),
            limits,
        )
        if any(refs[id(n)] > 1 for n in chain) or not (
            service.start_mark.line <= limits.start_mark.line
            and limits.end_mark.line <= service.end_mark.line
        ):
            raise RefusedError(f"service {name}'s limits is shared through an anchor or alias")
        existing = _child(limits, "cpus")
        if existing is not None:
            current = _scalar_text(existing)
            if cpus_value(current) != value:
                raise RefusedError(
                    f"service {name} already has cpus {current!r}, the table says {value_text}"
                )
            continue
        memory = _entry(limits, "memory")
        if memory is None:
            raise RefusedError(f"service {name}'s limits has no memory")
        key_node, value_node = memory
        line = key_node.start_mark.line
        if (
            not isinstance(value_node, yaml.ScalarNode)
            or value_node.style in ("|", ">")
            or value_node.tag == "tag:yaml.org,2002:null"
            or value_node.start_mark.line != line
            or value_node.end_mark.line != line
        ):
            raise RefusedError(f"service {name}'s memory is not a one-line value")
        inserts.append((line, " " * key_node.start_mark.column + f"cpus: '{value_text}'"))
        inserted.append(name)
    if not inserts:
        return data, []
    lines = text.split("\n")
    for line, new in sorted(inserts, reverse=True):
        lines.insert(line + 1, new)
    new_text = "\n".join(lines)
    # self-check: every wanted service reads its cpus, and nothing else in the document moved
    expected = yaml.safe_load(text)
    for name, (_container, _value, value_text) in wanted.items():
        expected["services"][name]["deploy"]["resources"]["limits"].setdefault("cpus", value_text)
    new_services = _child(_compose(new_text), "services")
    for name, (_container, value, value_text) in wanted.items():
        if cpus_value(_scalar_text(_child(_limits(_child(new_services, name)), "cpus"))) != value:
            raise RefusedError(
                f"self-check: service {name} does not read cpus {value_text} after the insert"
            )
    if yaml.safe_load(new_text) != expected:
        raise RefusedError("self-check: the insert changed more than the cpus keys")
    return new_text.encode("utf-8"), inserted


def _config(path: str) -> dict:
    r = run(f"sudo -n docker compose -f {shlex.quote(path)} config --format json")
    if r.returncode != 0:
        # never forward compose's stderr: it echoes interpolated .env values (measured)
        raise RefusedError(
            f"docker compose config failed (rc {r.returncode}); run it on vps1 to see why"
        )
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RefusedError("docker compose config printed no JSON") from None
    if not isinstance(doc, dict):
        raise RefusedError("docker compose config did not print a JSON object")
    return doc


def config_problem(before: dict, after: dict, edited: dict[str, str]) -> str | None:
    """Why AFTER is not BEFORE plus exactly the edited cpus keys; names paths only, never values."""
    stripped = copy.deepcopy(after)
    for name, value_text in edited.items():
        try:
            limits = stripped["services"][name]["deploy"]["resources"]["limits"]
            got = limits.pop("cpus")
        except (KeyError, TypeError):
            return f"services.{name}.deploy.resources.limits.cpus is absent after the edit"
        if not isinstance(got, (int, float)) or Decimal(str(got)) != Decimal(value_text):
            return f"services.{name}.deploy.resources.limits.cpus does not read {value_text}"
    if stripped != before:
        diff = sorted(k for k in set(before) | set(stripped) if before.get(k) != stripped.get(k))
        return f"the config changed beyond the cpus keys (top-level keys: {', '.join(diff)})"
    return None


def _remote_sha(path: str) -> str | None:
    try:
        r = run(f"sudo -n sha256sum {shlex.quote(path)}")
    except TransportError:
        return None
    words = r.stdout.decode("utf-8", "replace").split()
    return words[0] if r.returncode == 0 and words else None


def _restore(path: str, backup: str, old_sha: str, problem: str) -> None:
    """Put the backup back and raise RefusedError; stop the run when even that cannot be confirmed."""
    try:
        r = run(
            f"sudo -n sh -c {shlex.quote(RESTORE_SH)} sh {shlex.quote(path)} {shlex.quote(backup)} {old_sha}"
        )
        why = None if r.returncode == 0 else _err(r)
    except TransportError as exc:
        why = str(exc)
    if why is not None:
        die(
            f"{path}: {problem}; and the restore FAILED ({why}) — restore it by hand: cp -p {backup} {path}"
        )
    raise RefusedError(f"{problem}; restored from {backup}")


def apply_file(path: str, data: bytes, new: bytes, edited: dict[str, str]) -> str:
    """Write one live compose under compose's own before/after check; return the backup path. Raises RefusedError,
    after restoring the backup whenever the file was replaced (a dropped ssh included)."""
    try:
        before = _config(path)
    except TransportError as exc:
        raise RefusedError(f"not written: compose config not reached ({exc})") from None
    for name in edited:
        resolved = (before.get("services") or {}).get(name) or {}
        found = [k for k in _CPU_KEYS if k in resolved]
        if found:  # as compose resolves it: merges, extends and interpolation included
            raise RefusedError(f"not written: service {name} resolves a service-level {found[0]}")
    old_sha, new_sha = sha256(data), sha256(new)
    backup = f"{path}.cpu-bak-{STAMP}"
    try:
        r = run(
            f"sudo -n sh -c {shlex.quote(WRITE_SH)} sh {shlex.quote(path)} {old_sha} {new_sha} {STAMP}",
            stdin=new,
        )
        # WRITE_SH's own refusals (3, 4, 5): each exits before the mv, so F is untouched
        if r.returncode in (3, 4, 5):
            raise RefusedError(f"not written ({_err(r)}); the file is unchanged")
        why = None if r.returncode == 0 else _err(r)
        dropped = False
    except TransportError as exc:
        why, dropped = str(exc), True
    if why is not None:
        now = _remote_sha(path)
        if now == old_sha and not dropped:
            raise RefusedError(f"not written ({why}); the file is unchanged")
        if now == old_sha:
            # ssh dropped mid-write: the remote write may still finish after this read
            raise RefusedError(
                f"not confirmed ({why}): the file read unchanged, but the write may still land — re-run the dry "
                f"run to see its state ({backup} holds the original if it was taken)"
            )
        if now != new_sha:
            die(
                f"{path}: the write failed ({why}) and the file's state is unconfirmed (sha256 {now}); "
                f"its original sha256 is {old_sha}, and {backup} holds it if it exists"
            )
    try:
        problem = config_problem(before, _config(path), edited)
    except (RefusedError, TransportError) as exc:
        problem = str(exc)
    if problem is None:
        return backup
    _restore(path, backup, old_sha, problem)
    raise AssertionError("unreachable")


def acceptance_query(names: list[str]) -> str:
    pattern = "|".join(sorted(names))
    return f'container_spec_cpu_quota{{name=~"{pattern}"}} / container_spec_cpu_period{{name=~"{pattern}"}}'


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except TransportError as exc:
        die(f"ssh: {exc} — re-run the dry run to read the current state")
    raise AssertionError("unreachable")


def _table(names: list[str], runtime: dict[str, str], files: dict[str, str]) -> None:
    print("container                runtime   file")
    for name in names:
        print(f"{name:<24} {runtime[name]:<9} {files.get(name, '')}")


def _main(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply", action="store_true", help="run the changes (default: dry run, reads only)"
    )
    args = parser.parse_args(argv)
    try:
        table = load_table()
    except RefusedError as exc:
        die(f"hub table: {exc}")
    names = sorted(table)
    r = run("sudo -n docker inspect --type container " + " ".join(shlex.quote(n) for n in names))
    try:
        plan = runtime_plan(table, r.stdout)
    except RefusedError as exc:
        die(f"{exc}: {_err(r)}")
    problems: list[str] = []
    file_result: dict[str, str] = {}
    by_file: dict[str, dict[str, tuple[str, Decimal, str]]] = {}
    for name in names:
        state, record = plan[name]
        if state in ("DIFFERS", "MISSING"):
            problems.append(f"{name}: {state}")
            file_result[name] = "left out"
            continue
        path = boot_file(record)
        service = ((record.get("Config") or {}).get("Labels") or {}).get(
            "com.docker.compose.service"
        )
        if path is None or not isinstance(service, str):
            problems.append(f"{name}: MANUAL — its compose is not one /opt/<dir>/compose.yaml")
            file_result[name] = "MANUAL"
            continue
        by_file.setdefault(path, {})[service] = (name, *table[name])

    edits: dict[str, tuple[bytes, bytes, dict[str, str]]] = {}
    containers_of: dict[str, list[str]] = {}
    for path, wanted in sorted(by_file.items()):
        containers = [c for c, _v, _t in wanted.values()]
        r = run(f"sudo -n cat {shlex.quote(path)}")
        try:
            if r.returncode != 0:
                raise RefusedError(f"could not read it: {_err(r)}")
            new, inserted = insert_cpus(r.stdout, wanted)
        except RefusedError as exc:
            problems.append(f"{path}: REFUSED — {exc}")
            file_result.update(dict.fromkeys(containers, "REFUSED"))
            continue
        if not inserted:
            file_result.update(dict.fromkeys(containers, "OK"))
            continue
        edits[path] = (r.stdout, new, {svc: wanted[svc][2] for svc in inserted})
        containers_of[path] = containers
        file_result.update(dict.fromkeys(containers, "edit"))

    runtime = {n: plan[n][0] for n in names}
    _table(names, runtime, file_result)
    for path, (_old, _new, edited) in sorted(edits.items()):
        print(f"{path}: inserts cpus for {', '.join(sorted(edited))}")

    updates = [n for n in names if plan[n][0] == "UPDATE"]
    if args.apply:
        if updates:
            gate(
                "runtime caps (docker update --cpus, no restart)",
                "\n".join(f"docker update --cpus {table[n][1]} {n}" for n in updates),
            )
            for name in updates:
                r = run(f"sudo -n docker update --cpus {table[name][1]} {shlex.quote(name)}")
                if r.returncode != 0:
                    die(f"docker update {name} failed: {_err(r)}")
            r = run(
                "sudo -n docker inspect --type container "
                + " ".join(shlex.quote(n) for n in updates)
            )
            try:
                after = runtime_plan({n: table[n] for n in updates}, r.stdout)
            except RefusedError as exc:
                die(f"re-inspect: {exc}")
            wrong = [n for n in updates if after[n][0] != "OK"]
            if wrong:
                die(f"after docker update these do not read their cap: {', '.join(wrong)}")
            runtime.update(dict.fromkeys(updates, "updated"))
            print(f"runtime: {len(updates)} container(s) now read their cap (NanoCpus, CpuQuota 0)")
        if edits:
            gate(
                "live compose files (backup, insert cpus, compose config before and after)",
                "\n".join(
                    f"{p}: {', '.join(sorted(e))}" for p, (_o, _n, e) in sorted(edits.items())
                ),
            )
            for path, (old, new, edited) in sorted(edits.items()):
                try:
                    backup = apply_file(path, old, new, edited)
                    print(f"{path}: written, backup {backup}")
                    file_result.update(dict.fromkeys(containers_of[path], "written"))
                except RefusedError as exc:
                    problems.append(f"{path}: REFUSED — {exc}")
                    file_result.update(dict.fromkeys(containers_of[path], "REFUSED"))
        print("\nResult:")
        _table(names, runtime, file_result)
    print(
        "\nNothing was started, stopped or recreated. The edited files take over at the next `up -d` or reboot "
        "(an `up -d` now recreates those containers)."
    )
    print(f"Acceptance (D-1324), in Prometheus:\n  {acceptance_query(names)}")
    print(
        "The re-inspect above is this script's own proof; if cAdvisor still shows no quota after a scrape "
        "interval, its cached container spec may be stale until the container or cAdvisor is recreated."
    )
    if not args.apply:
        print("\nDry run: nothing was changed. Re-run with --apply.")
    if problems:
        print("\nNeeds the operator:\n" + "\n".join(f"  {p}" for p in problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
