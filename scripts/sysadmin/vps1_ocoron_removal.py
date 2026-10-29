#!/usr/bin/env python3
# AFTER-EDIT: none
"""Remove the ocoron.com stack from vps1 (D-1333: "we will deploy ocoron.com at cloudflare not to our vps. remove it
entirely from our vps").

Operator-run, from the hub main checkout, AFTER the updated sysadmin prompt is on vps1 (`bash
scripts/sync-vps-sysadmin.sh`; the bot it drives was told to keep this stack up, and `--apply` refuses while vps1's
copy still names `ocoron-com-` containers):

    python3 -I scripts/sysadmin/vps1_ocoron_removal.py                         # dry run: reads only
    python3 -I scripts/sysadmin/vps1_ocoron_removal.py --apply                 # down + out of the boot glob + images
    python3 -I scripts/sysadmin/vps1_ocoron_removal.py --delete-volumes ID …   # only ids the dry run printed

The stack is every container whose compose project is ocoron-com, whose name starts ocoron-com, or whose Traefik
rule routes ocoron.com or www.ocoron.com; its projects are read from those containers, never assumed. `--apply` runs
`docker compose -p <project> down` (no -v: volumes stay), then moves /opt/ocoron-com/compose.yaml aside, because
fabrik-compose-boot.sh runs `up -d` on every /opt/*/compose.yaml at boot (that is how D-121's down came undone), then
removes the images no container still uses (no -f: the daemon refuses an image in use). Volumes and the
/opt/ocoron-com directory are data (the volume HARD STOP): the dry run classifies each by what it holds, its size and
its users (any container mounting it, a bind below /opt/ocoron-com included), and only `--delete-volumes` with ids
from that list deletes them. Config files that still mention the site are listed for review, never edited.
Exit 1 on any STOP.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time

SSH = ["ssh", "-o", "ProxyJump=vps2", "-o", "ConnectTimeout=20", "vps"]
PROJECT = "ocoron-com"
DATA_DIR = "/opt/ocoron-com"
COMPOSE = f"{DATA_DIR}/compose.yaml"
PROMPT = "/opt/fabrik/scripts/sysadmin/system-prompt.txt"  # vps1's deployed copy (scripts/sync-vps-sysadmin.sh)
STAMP = time.strftime("%Y%m%d-%H%M%S")
CONFIG_ROOTS = (
    "/opt/monitoring/configs",
    "/opt/authelia/config",
    "/opt/backrest/config",
    "/opt/traefik",
    "/etc/cron.d",
    "/var/spool/cron/crontabs",
    "/etc/systemd/system",
    "/etc/logrotate.d",
)
# GNU grep ERE: the apex or www host, or the stack's own name; never another service's *.ocoron.com host or an
# @ocoron.com address (cases pinned in tests/test_vps1_ocoron_removal.py)
SITE_ERE = r"(^|[^A-Za-z0-9.@-])(www\.)?ocoron\.com($|[^A-Za-z0-9.-])|ocoron-com([^A-Za-z0-9.]|$)"
KNOWN_BENIGN = (
    "the Gatus status-page title, the promtail drop filter for the backup container and an Authelia session cookie "
    "domain match by design"
)
_HOST_RULE = re.compile(r"Host\(\s*`(www\.)?ocoron\.com`")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
# a local volume's own directory under any docker root: `<root>/volumes/<name>/_data`; no segment may start with
# `.`, so `..` and `.` cannot appear
_VOLUME_DATA = re.compile(
    r"(/[A-Za-z0-9_-][A-Za-z0-9_.-]*)+/volumes/[A-Za-z0-9][A-Za-z0-9_.-]*/_data"
)

# argv: F stamp. Moves F out of the boot glob. rc 4: F absent (already aside) · rc 5: a symlink, not a regular file,
# or the target name is taken.
RENAME_SH = r"""set -eu
f=$1; t="$1.removed-$2"
[ -e "$f" ] || [ -L "$f" ] || exit 4
{ [ -f "$f" ] && [ ! -L "$f" ]; } || { echo "not a regular file: $f" >&2; exit 5; }
[ ! -e "$t" ] && [ ! -L "$t" ] || { echo "target name taken: $t" >&2; exit 5; }
mv -- "$f" "$t"
echo "$t"
"""


class StopError(Exception):
    """The run stops; the message says what is left in which state."""


class TransportError(StopError):
    """ssh could not deliver a command or its answer: the remote state is unknown."""


def _name(value: str) -> bool:
    return bool(_NAME.fullmatch(value))


def _data_path(path: str) -> bool:
    """The data dir, or a local volume's own _data directory: the only paths du and find are sent."""
    return path == DATA_DIR or bool(_VOLUME_DATA.fullmatch(path))


def allowed(cmd: str) -> bool:
    """The ONLY command shapes this script sends — an allowlist, so no other removal can go out by any spelling."""
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return False
    # the remote shell runs the raw string, so it must be exactly the quoted form of its tokens
    if shlex.join(argv) != cmd or argv[:2] != ["sudo", "-n"]:
        return False
    a = argv[2:]
    return (
        a == ["docker", "ps", "-aq", "--no-trunc"]
        or (
            a[:3] == ["docker", "inspect", "--type"]
            and a[3:4] == ["container"]
            and len(a) > 4
            and all(_HEX64.fullmatch(x) for x in a[4:])
        )
        or (
            len(a) == 7
            and a[:4] == ["docker", "network", "ls", "--filter"]
            and a[4].startswith("label=com.docker.compose.project=")
            and _name(a[4].partition("project=")[2])
            and a[5:] == ["--format", "{{.Name}}"]
        )
        or a == ["docker", "volume", "ls", "--format", "{{.Name}}"]
        or a == ["docker", "info", "--format", "{{.DockerRootDir}}"]
        or (
            a[:3] == ["docker", "volume", "inspect"] and len(a) > 3 and all(_name(x) for x in a[3:])
        )
        or (len(a) == 3 and a[:2] == ["du", "-sb"] and _data_path(a[2]))
        or (
            len(a) == 6
            and a[0] == "find"
            and _data_path(a[1])
            and a[2:] == ["-maxdepth", "2", "-printf", "%y %P\n"]
        )
        or a in (["test", "-f", COMPOSE], ["test", "-d", DATA_DIR], ["uptime", "-s"])
        or a == ["grep", "-rnIoE", SITE_ERE, *CONFIG_ROOTS]
        or a == ["grep", "-cE", "ocoron-com-", PROMPT]
        or (
            len(a) == 4 + len(CONFIG_ROOTS)
            and a[:3] == ["grep", "-rlIF", "--"]
            and (_name(a[3]) or a[3] == DATA_DIR)
            and tuple(a[4:]) == CONFIG_ROOTS
        )
        or (len(a) == 5 and a[:3] == ["docker", "compose", "-p"] and _name(a[3]) and a[4] == "down")
        or a == ["sh", "-c", RENAME_SH, "sh", COMPOSE, STAMP]
        or (len(a) == 4 and a[:3] == ["docker", "image", "rm"] and bool(_IMAGE_ID.fullmatch(a[3])))
        or (len(a) == 4 and a[:3] == ["docker", "volume", "rm"] and _name(a[3]))
        or a == ["rm", "-rf", "--one-file-system", "--", DATA_DIR]
    )


def sudo(*argv: str) -> str:
    return shlex.join(["sudo", "-n", *argv])


def run(cmd: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    """Run cmd on vps1. Refuses any shape `allowed` does not list before ssh starts."""
    if not allowed(cmd):
        raise StopError(f"refusing a command this script never sends: {cmd}")
    try:
        r = subprocess.run(
            SSH + [cmd], capture_output=True, text=True, errors="replace", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise TransportError(f"timed out after {timeout}s: {cmd}") from None
    except OSError as exc:
        raise TransportError(f"could not start ssh: {exc}") from None
    if r.returncode == 255:
        raise TransportError(f"ssh failed (rc 255): {r.stderr.strip() or 'no message'}")
    return r


def must(cmd: str) -> str:
    r = run(cmd)
    if r.returncode != 0:
        raise StopError(f"rc {r.returncode} from {cmd}: {r.stderr.strip() or 'no message'}")
    return r.stdout


def classify(find_out: str) -> tuple[str, list[str]]:
    """(class, signatures) from `find <dir> -maxdepth 2 -printf '%y %P\\n'` output."""
    entries = []
    for line in find_out.splitlines():
        kind, _, rel = line.partition(" ")
        if rel:
            entries.append((kind, rel, rel.rsplit("/", 1)[-1]))
    if not entries:
        return "empty", []
    rules = (
        (
            "mysql",
            lambda k, r, b: b in ("ibdata1", "aria_log_control") or (k == "d" and r == "mysql"),
        ),
        ("wordpress", lambda k, r, b: b == "wp-config.php" or (k == "d" and b == "wp-content")),
        ("redis", lambda k, r, b: b == "dump.rdb" or b.startswith("appendonly")),
        ("backup", lambda k, r, b: k == "f" and b.endswith((".sql.gz", ".sql", ".tar.gz", ".zip"))),
    )
    for cls, hit in rules:
        sigs = [r for k, r, b in entries if hit(k, r, b)]
        if sigs:
            return cls, sigs[:5]
    return "unknown", [r for _, r, _ in entries[:5]]


def _containers() -> list[dict]:
    ids = must(sudo("docker", "ps", "-aq", "--no-trunc")).split()
    if not ids:
        return []
    bad = [i for i in ids if not _HEX64.fullmatch(i)]
    if bad:
        raise StopError(f"docker ps printed an id that is not 64 hex: {bad[0]!r}")
    # inspect exits 1 when a container vanished between the two calls but still prints the rest: stdout counts
    out = run(sudo("docker", "inspect", "--type", "container", *ids)).stdout
    try:
        records = json.loads(out)
    except json.JSONDecodeError:
        raise StopError("docker inspect printed no JSON") from None
    if not isinstance(records, list):
        raise StopError("docker inspect did not print a JSON list")
    return [r for r in records if isinstance(r, dict)]


def _labels(record: dict) -> dict:
    labels = (record.get("Config") or {}).get("Labels") or {}
    return labels if isinstance(labels, dict) else {}


def in_stack(record: dict) -> bool:
    labels = _labels(record)
    name = str(record.get("Name", "")).lstrip("/")
    return (
        labels.get("com.docker.compose.project") == PROJECT
        or name.startswith(PROJECT)
        or any(
            k.startswith("traefik.http.routers.") and _HOST_RULE.search(str(v))
            for k, v in labels.items()
        )
    )


def users_of(records: list[dict], volume: str | None = None, path: str | None = None) -> list[str]:
    """Containers (any project, stopped included) mounting the named volume, or anything at or below path."""
    found = []
    for r in records:
        for m in r.get("Mounts") or []:
            if not isinstance(m, dict):
                continue
            src = str(m.get("Source", ""))
            if (volume is not None and m.get("Type") == "volume" and m.get("Name") == volume) or (
                path is not None and (src == path or src.startswith(path + "/"))
            ):
                found.append(str(r.get("Name", "")).lstrip("/"))
                break
    return sorted(found)


def _size(path: str) -> str:
    r = run(sudo("du", "-sb", path))
    return r.stdout.split()[0] + " B" if r.returncode == 0 and r.stdout.split() else "UNREADABLE"


def _class(path: str) -> tuple[str, list[str]]:
    r = run(sudo("find", path, "-maxdepth", "2", "-printf", "%y %P\n"))
    if r.returncode != 0:
        return "UNREADABLE", [r.stderr.strip()[:200]]
    return classify(r.stdout)


def inventory() -> dict:
    """Everything the run decides on, read-only."""
    records = _containers()
    stack = [r for r in records if in_stack(r)]
    projects = sorted({_labels(r).get("com.docker.compose.project", "") for r in stack} - {""})
    unlabelled = sorted(
        str(r.get("Name", "")).lstrip("/")
        for r in stack
        if not _labels(r).get("com.docker.compose.project")
    )
    bad = [p for p in projects if not _name(p)]
    if bad:
        raise StopError(
            f"a stack container carries a project label this script cannot name: {bad[0]!r}"
        )
    networks = []
    for p in projects or [PROJECT]:
        networks += must(
            sudo(
                "docker",
                "network",
                "ls",
                "--filter",
                f"label=com.docker.compose.project={p}",
                "--format",
                "{{.Name}}",
            )
        ).split()
    stack_mounts = {
        m.get("Name")
        for r in stack
        for m in r.get("Mounts") or []
        if isinstance(m, dict) and m.get("Type") == "volume"
    }
    names = must(sudo("docker", "volume", "ls", "--format", "{{.Name}}")).split()
    volume_names = sorted(
        n for n in names if _name(n) and (n.startswith(PROJECT + "_") or n in stack_mounts)
    )
    volumes = []
    if volume_names:
        root = must(sudo("docker", "info", "--format", "{{.DockerRootDir}}")).strip()
        try:
            meta = {
                v.get("Name"): v
                for v in json.loads(must(sudo("docker", "volume", "inspect", *volume_names)))
            }
        except (json.JSONDecodeError, AttributeError):
            raise StopError("docker volume inspect printed no JSON list") from None
        for v in volume_names:
            mount = str((meta.get(v) or {}).get("Mountpoint", ""))
            if mount != f"{root}/volumes/{v}/_data" or not _data_path(mount):
                volumes.append(
                    {
                        "id": v,
                        "class": "UNREADABLE",
                        "signs": [f"mountpoint {mount!r}"],
                        "size": "UNREADABLE",
                        "users": users_of(records, volume=v),
                    }
                )
                continue
            cls, signs = _class(mount)
            volumes.append(
                {
                    "id": v,
                    "class": cls,
                    "signs": signs,
                    "size": _size(mount),
                    "users": users_of(records, volume=v),
                }
            )
    data_dir = None
    if run(sudo("test", "-d", DATA_DIR)).returncode == 0:
        cls, signs = _class(DATA_DIR)
        data_dir = {
            "id": DATA_DIR,
            "class": cls,
            "signs": signs,
            "size": _size(DATA_DIR),
            "users": users_of(records, path=DATA_DIR),
        }
    glob_rc = run(sudo("test", "-f", COMPOSE)).returncode
    refs = run(sudo("grep", "-rnIoE", SITE_ERE, *CONFIG_ROOTS))
    prompt = run(sudo("grep", "-cE", "ocoron-com-", PROMPT))
    return {
        "stack": [
            {
                "name": str(r.get("Name", "")).lstrip("/"),
                "state": (r.get("State") or {}).get("Status"),
                "created": r.get("Created"),
                "image": r.get("Image"),
            }
            for r in stack
        ],
        "projects": projects,
        "unlabelled": unlabelled,
        "networks": networks,
        "volumes": volumes,
        "data_dir": data_dir,
        "in_boot_glob": glob_rc == 0,
        "refs": [ln.strip() for ln in refs.stdout.splitlines() if ln.strip()],
        "refs_unreadable": refs.returncode > 1 and refs.stderr.strip(),
        "prompt": prompt.stdout.strip() if prompt.returncode in (0, 1) else "UNREADABLE",
        "booted": run(sudo("uptime", "-s")).stdout.strip(),
    }


def report(inv: dict) -> None:
    print(f"vps1 booted: {inv['booted'] or 'UNREADABLE'}")
    print(f"\nstack containers ({len(inv['stack'])}):")
    for c in inv["stack"]:
        print(f"  {c['name']}  {c['state']}  created {c['created']}  image {c['image']}")
    if inv["unlabelled"]:
        print(
            f"  not in a compose project (this script cannot take them down): {', '.join(inv['unlabelled'])}"
        )
    print(f"projects: {', '.join(inv['projects']) or 'none'}")
    print(f"networks ({len(inv['networks'])}): {', '.join(inv['networks']) or 'none'}")
    print(
        f"{COMPOSE} in the boot glob: {'YES — the next reboot starts the stack' if inv['in_boot_glob'] else 'no'}"
    )
    print(f"vps1 sysadmin prompt lines naming ocoron-com- containers: {inv['prompt']}")
    print(
        "\ndata (volume HARD STOP — deleted only by --delete-volumes with these exact ids; users = Docker mounts "
        "only, Backrest reads volumes through a parent bind):"
    )
    for d in inv["volumes"] + ([inv["data_dir"]] if inv["data_dir"] else []):
        users = ", ".join(d["users"]) or "none"
        print(f"  {d['id']}  class {d['class']}  size {d['size']}  users {users}")
        print(f"    signatures: {', '.join(d['signs']) or '-'}")
    if not inv["volumes"] and not inv["data_dir"]:
        print("  none")
    print(f"\nREVIEW — config lines still naming the site (never edited here; {KNOWN_BENIGN}):")
    for ln in inv["refs"]:
        print(f"  {ln}")
    if not inv["refs"]:
        print("  none")
    if inv["refs_unreadable"]:
        print(f"  UNREADABLE: {inv['refs_unreadable'][:400]}")


def gate(title: str, plan: str) -> None:
    print(f"\n=== {title} ===\n{plan}")
    try:
        answer = input("Type yes to run this block: ").strip()
    except EOFError:
        answer = ""
    if answer != "yes":
        raise StopError(f"not confirmed: {title} — nothing in this block ran")


def apply() -> None:
    inv = inventory()
    report(inv)
    if inv["prompt"] != "0":
        raise StopError(
            "vps1's sysadmin prompt still names ocoron-com- containers (or is unreadable): deploy the "
            "updated prompt first with `bash scripts/sync-vps-sysadmin.sh`, so its bot does not restart "
            "what this removes"
        )
    if inv["unlabelled"]:
        raise StopError(
            f"stack containers outside any compose project: {', '.join(inv['unlabelled'])} — remove "
            "them by hand, then re-run"
        )
    if not inv["stack"] and not inv["networks"] and not inv["in_boot_glob"]:
        print(
            "\nnothing to take down: no stack container, no network, compose.yaml not in the boot glob"
        )
    else:
        images = sorted({c["image"] for c in inv["stack"] if c["image"]})
        downs = [sudo("docker", "compose", "-p", p, "down") for p in inv["projects"]]
        gate(
            "take the ocoron-com stack down",
            "\n".join(
                [
                    *downs,
                    f"move {COMPOSE} aside to compose.yaml.removed-{STAMP} (out of the boot glob)",
                    *(
                        f"docker image rm {i} (refused by docker while anything uses it)"
                        for i in images
                    ),
                    "while Cloudflare's ocoron.com record still points at vps1, the site turns into a Traefik 404 now",
                ]
            ),
        )
        for cmd in downs:
            print(must(cmd) or f"ok: {cmd}")
        r = run(sudo("sh", "-c", RENAME_SH, "sh", COMPOSE, STAMP))
        if r.returncode == 4:
            print(f"{COMPOSE}: already aside")
        elif r.returncode != 0:
            raise StopError(
                f"the stack is DOWN but {COMPOSE} is still in the boot glob — the next reboot restores "
                f"it; move it out of /opt/*/compose.yaml by hand: {r.stderr.strip() or f'rc {r.returncode}'}"
            )
        else:
            print(f"moved aside: {r.stdout.strip()}")
        for image in images:
            ri = run(sudo("docker", "image", "rm", image))
            print(
                f"image {image}: {'removed' if ri.returncode == 0 else 'kept — ' + ri.stderr.strip()[:200]}"
            )
    after = inventory()
    left = [c["name"] for c in after["stack"]] + after["networks"]
    if left or after["in_boot_glob"]:
        raise StopError(
            f"still present after the down: {', '.join(left) or COMPOSE + ' in the boot glob'}"
        )
    ids = [d["id"] for d in after["volumes"]] + (
        [after["data_dir"]["id"]] if after["data_dir"] else []
    )
    print("\nstack removed: 0 containers, 0 networks, compose.yaml out of the boot glob.")
    if ids:
        print("data left (review the classes above, then, only on the operator's word):")
        print(
            f"  python3 -I scripts/sysadmin/vps1_ocoron_removal.py --delete-volumes {' '.join(ids)}"
        )


def delete_volumes(ids: list[str]) -> None:
    inv = inventory()
    report(inv)
    if inv["stack"] or inv["networks"]:
        raise StopError("the stack is still up: run --apply first")
    if inv["in_boot_glob"]:
        raise StopError(
            f"{COMPOSE} is in the boot glob, so a reboot would recreate the volumes: run --apply first"
        )
    known = {d["id"]: d for d in inv["volumes"] + ([inv["data_dir"]] if inv["data_dir"] else [])}
    wanted = list(dict.fromkeys(ids))
    unknown = [i for i in wanted if i not in known]
    if unknown:
        raise StopError(f"not in this inventory, nothing deleted: {', '.join(unknown)}")
    used = [f"{i} (used by {', '.join(known[i]['users'])})" for i in wanted if known[i]["users"]]
    if used:
        raise StopError(f"still in use, nothing deleted: {'; '.join(used)}")
    lines = []
    for i in wanted:
        lines.append(f"{i}  class {known[i]['class']}  size {known[i]['size']}")
        # a Backrest plan (or any config) still naming the id fails once it is gone: shown, the operator decides
        r = run(sudo("grep", "-rlIF", "--", i, *CONFIG_ROOTS))
        lines += [f"    WARN still named in: {path}" for path in r.stdout.split()]
        if r.returncode > 1:
            lines.append(f"    WARN config search UNREADABLE: {r.stderr.strip()[:200]}")
    gate("delete data — cannot be undone", "\n".join(lines))
    failed = []
    for i in wanted:
        cmd = (
            sudo("rm", "-rf", "--one-file-system", "--", DATA_DIR)
            if i == DATA_DIR
            else sudo("docker", "volume", "rm", i)
        )
        r = run(cmd)
        print(f"{i}: {'deleted' if r.returncode == 0 else 'FAILED — ' + r.stderr.strip()[:200]}")
        if r.returncode != 0:
            failed.append(i)
    if failed:
        raise StopError(f"not deleted: {', '.join(failed)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="take the stack down and out of the boot glob"
    )
    mode.add_argument(
        "--delete-volumes", nargs="+", metavar="ID", help="delete these volumes / the data dir"
    )
    args = ap.parse_args(argv)
    try:
        if args.apply:
            apply()
        elif args.delete_volumes:
            delete_volumes(args.delete_volumes)
        else:
            report(inventory())
            print("\ndry run: nothing changed. Next: --apply (after the prompt sync).")
    except StopError as exc:
        print(f"\nSTOP: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
