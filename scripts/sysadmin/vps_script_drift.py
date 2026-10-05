#!/usr/bin/env python3
# AFTER-EDIT: docs/infrastructure/vps-ai-sysadmin.md, scripts/sysadmin/weekly_catchup.sh, docs/workstation/kaizen.md, tests/test_vps_script_drift.py
"""Read-only drift check: is every VPS still running the hub's committed scripts? (W-c792a205)

The fleet executes hub scripts from ``/opt/fabrik/scripts/sysadmin/`` — the cron set in
``scripts/bootstrap/templates/sysadmin-cron.template``, the scripts those targets call, the bot — and
``/usr/local/bin/fabrik-autoheal``. Those copies arrive only through the hand-run
``scripts/sync-vps-sysadmin.sh``, so a hub edit is inert until someone deploys it, and on 2026-09-05 one was
inert for six days while ``detect_reversals.py`` failed 1,597 times on a lost exec bit. This script DETECTS;
it never pushes. Deploying stays the operator-approved run of the sync (a VPS write).

What it compares
  * Reference = the COMMITTED ``HEAD`` of whatever branch is checked out in ``FABRIK_ROOT`` (default
    ``/opt/fabrik``, the main checkout on master), via git — never the working tree, so a sibling's uncommitted
    edit is not "the hub's version". Consequence: a host synced from a dirty tree reads as DRIFT until that
    work is committed (production is running uncommitted code). Committed symlinks are not compared.
  * Tier 1 drives the signature and the mail: every ``/opt/fabrik/scripts/sysadmin/<f>`` the
    cron template names, ``TIER1_DEPENDENCIES`` (what those targets call, plus the bot), the two audit scripts
    cron calls (``AUDIT_TARGETS``) and ``scripts/vps-autoheal.sh`` (deployed as fabrik-autoheal).
  * Tier 2 is every other committed file under ``scripts/sysadmin/``: printed and counted, never mailed —
    it churns daily and most of it never runs on a VPS. A tier-2 difference still makes the exit 1.
  * Per host, ONE read-only ``ssh -o BatchMode=yes`` session prints ``<mode> <md5> <path>`` per regular file
    (``find -exec``, so a path with spaces survives; ``stat -L``), or ``UNREADABLE - <path>`` when the mode or
    the md5 cannot be read. ssh rc 255 or a timeout is "unreachable"; any other rc still has its stdout parsed.

Lines: ``DRIFT <host> <path>`` (content differs) · ``MISSING <host> <path>`` (committed, absent on the host)
· ``MODE <host> <path>`` (committed executable, host copy lacks owner-exec — the 2026-09-05 shape)
· ``UNREADABLE <host> <path>`` (present, but the host could not read it or lacks stat/md5sum — unverified)
· ``CRONMISSING <host> <path>`` / ``CRONEXTRA <host> <path>`` (W-73feca74: the host's ``/etc/cron.d/vps-sysadmin``
  — rendered by bootstrap step 14 on a spoke, by hand on the hub, never by the sync — schedules a different SET of
  ``/opt/fabrik/scripts/`` paths than the COMMITTED template's non-comment lines; paths, never bytes, since minutes
  differ per host; ``CRONMISSING <host> /etc/cron.d/vps-sysadmin`` when the file is absent, ``CRONUNREADABLE`` when
  it cannot be read, ``CRONUNVERIFIED`` when the listing never reached its CRON-END sentinel). Cron lines are tier 1. Not compared: the cron user, the schedule, and
  ``/usr/local/bin/fabrik-autoheal`` (a live host may schedule it outside this file).
Exit: 0 clean (every host reached, nothing differs) · 1 any difference, either tier · 2 any host unreachable
· 3 the check itself failed (git, state, an unexpected error).
``--stamp <path>`` touches <path> only when the run reached one of the verdicts 0-2. The rider keys its daily
stamp on that file and never on the exit code, because Python itself exits 2 for a missing script and 1 for a
syntax error, and both look like verdicts.

``--mail`` (watermark JSON at ``FABRIK_DRIFT_STATE``, default ``~/.claude/state/vps-script-drift.json``):
the fleet signature is the sorted tier-1 lines of every host; an unreachable host keeps its previous lines, so
a flapping host never changes it. A new signature, or one unchanged for ``RENUDGE_DAYS``, mails fleet
(``ack: required``); the watermark advances only after the send succeeds and is cleared only on exit 0. A host
unreachable on ``UNREACHABLE_RUNS`` consecutive runs mails once, so the check cannot go silently blind. The
state is written atomically and a host no longer in ``FABRIK_DRIFT_HOSTS`` is dropped from it.

COBRA (D-253): the cheapest way to quiet this check without deploying is to ack the mail and leave the drift
— the RENUDGE_DAYS re-mail is the counter; the next cheapest is moving a file out of tier 1, which
``tests/test_vps_script_drift.py::test_template_targets_covered`` refuses for every cron target (a NEW callee
of a target must still be added to TIER1_DEPENDENCIES by hand — the mirror the design names).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

HOSTS_DEFAULT = ("vps", "vps2", "vps3")
TEMPLATE = Path("scripts/bootstrap/templates/sysadmin-cron.template")
AUTOHEAL_REPO = "scripts/vps-autoheal.sh"
AUTOHEAL_REMOTE = "/usr/local/bin/fabrik-autoheal"
# Rendered from TEMPLATE by bootstrap step 14 on a spoke, by hand on the hub; sync-vps-sysadmin.sh never
# touches it, so a template edit is inert until someone reinstalls it (W-73feca74).
CRON_REMOTE = "/etc/cron.d/vps-sysadmin"
REMOTE_BASE = "/opt/fabrik/"
# What the cron targets call (claude-run.sh:18,58; claude-keepalive-rotate.sh:27; proactive-check.sh's
# Telegram leg) plus the bot the systemd unit runs — the executed closure the template alone does not name.
TIER1_DEPENDENCIES = (
    "scripts/sysadmin/claude-run.sh",
    "scripts/sysadmin/claude_rotate.py",
    "scripts/sysadmin/quota_governor.py",
    "scripts/sysadmin/send-telegram.sh",
    "scripts/sysadmin/keepalive-status.sh",
    "scripts/sysadmin/system-prompt.txt",
    "scripts/sysadmin/bot.py",
)
# weekly-security.sh:20 and monthly-backup-verify.sh:28 run these with sudo bash.
AUDIT_TARGETS = ("scripts/audit/03-security.sh", "scripts/audit/06-backup.sh")
RENUDGE_DAYS = 7
UNREACHABLE_RUNS = 3
SSH_TIMEOUT = 60
MAIL_TIMEOUT = 60
# One line per file. Paths arrive as argv (find -exec … {} +), never through word-splitting, so a name with
# spaces survives; a file whose mode or md5 cannot be read prints UNREADABLE rather than a false DRIFT. No
# single quote may appear in _LIST_FILES: it is wrapped in one below.
_LIST_FILES = (
    'for f; do m=$(stat -L -c %a "$f" 2>/dev/null); h=$(md5sum 2>/dev/null < "$f"); h=${h%% *}; '
    'if [ -n "$m" ] && [ -n "$h" ]; then printf "%s %s %s\\n" "$m" "$h" "$f"; '
    'else printf "UNREADABLE - %s\\n" "$f"; fi; done'
)
REMOTE_CMD = (
    "find /opt/fabrik/scripts/sysadmin /opt/fabrik/scripts/audit -type f "
    "! -path '*/__pycache__/*' ! -name '*.pyc' -exec sh -c '"
    + _LIST_FILES
    + "' sh {} + 2>/dev/null; "
    "[ -e " + AUTOHEAL_REMOTE + " ] && sh -c '" + _LIST_FILES + "' sh " + AUTOHEAL_REMOTE + "; "
    # the installed cron file: every line prefixed CRON (comments are filtered in Python, one function for both
    # sides) read with sh builtins only, then CRON-END; or one CRON-ABSENT / CRON-UNREADABLE line. Without
    # CRON-END the half did not finish, which parse_cron reports as unverified, never as every job missing.
    # CRON-END follows only a successful redirect into a regular file: a directory or a failed open reads
    # CRON-UNREADABLE. (A read error part-way through a regular file cannot be told from EOF — stated limit.)
    "if [ -e "
    + CRON_REMOTE
    + " ]; then if [ -f "
    + CRON_REMOTE
    + " ] && [ -r "
    + CRON_REMOTE
    + " ]; then "
    '{ while IFS= read -r l || [ -n "$l" ]; do printf "CRON %s\\n" "$l"; done; } < '
    + CRON_REMOTE
    + " && echo CRON-END || echo CRON-UNREADABLE; else echo CRON-UNREADABLE; fi; else echo CRON-ABSENT; fi; true"
)
UNREADABLE = ("", "")
_MODE_RE = re.compile(r"[0-7]{1,4}")  # `stat -c %a` drops leading zeros: mode 044 prints "44"
_MD5_RE = re.compile(r"[0-9a-f]{32}")


def _root() -> Path:
    return Path(os.environ.get("FABRIK_ROOT", "/opt/fabrik"))


def _now() -> float:
    return float(os.environ.get("FABRIK_DRIFT_NOW") or time.time())


def _state_path() -> Path:
    default = Path.home() / ".claude" / "state" / "vps-script-drift.json"
    return Path(os.environ.get("FABRIK_DRIFT_STATE") or default)


def template_text(root: Path) -> str:
    """The COMMITTED cron template (HEAD), never the working tree: a sibling's uncommitted edit is not the hub's."""
    return subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{TEMPLATE.as_posix()}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def template_targets(root: Path) -> list[str]:
    """Repo paths of every executable the cron template names (comments included — a path is a path)."""
    text = template_text(root)
    out = {
        f"scripts/sysadmin/{m}"
        for m in re.findall(r"/opt/fabrik/scripts/sysadmin/([^\s>|;]+)", text)
    }
    if AUTOHEAL_REMOTE in text:
        out.add(AUTOHEAL_REPO)
    return sorted(out)


# Only hub scripts: /usr/local/bin/fabrik-autoheal may be scheduled outside this file on a live host, and a
# redirect target or a quote is not a scheduled path.
_CRON_PATH_RE = re.compile(r"/opt/fabrik/scripts/[^\s>|;&\"'`(),:]+")
# PATH=, SHELL=, MAILTO=: an environment line carries no job
_CRON_ENV_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=")  # cron allows spaces around =
# cron hands the command to sh, where a whitespace-preceded # starts a comment: a path after it never runs
_CRON_TAIL_COMMENT_RE = re.compile(r"\s#.*$")


def _strip_tail_comment(line: str) -> str:
    """Drop a trailing shell comment, unless the line quotes something: a # inside quotes is data."""
    return line if ('"' in line or "'" in line) else _CRON_TAIL_COMMENT_RE.sub("", line)


def cron_paths(text: str) -> set[str]:
    """The hub paths a cron file SCHEDULES: those named on non-comment lines. Compared as a set, never bytes —
    the minute fields differ per host ({{DIGEST_MINUTE}}, {{KEEPALIVE_MINUTE}}) and the template's comments
    name paths too."""
    return {
        m
        for line in text.split("\n")
        if line.strip() and not line.lstrip().startswith("#") and not _CRON_ENV_RE.match(line)
        for m in _CRON_PATH_RE.findall(_strip_tail_comment(line))
        if "{{" not in m  # a templated path cannot match a rendered one
    }


def parse_cron(text: str) -> list[str] | None:
    """REMOTE_CMD's cron half -> the host's cron lines (comments included), None when the file is absent,
    ["CRON-UNREADABLE"] when it exists but cannot be read, ["CRON-UNVERIFIED"] when the half never reached
    CRON-END (a cut session or a failed reader)."""
    # split on \n only: str.splitlines also breaks on form feeds and other separators that are data in a cron line
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    if "CRON-ABSENT" in lines:
        return None
    if "CRON-UNREADABLE" in lines:
        return ["CRON-UNREADABLE"]
    if "CRON-END" not in lines:
        return ["CRON-UNVERIFIED"]
    return [ln[len("CRON ") :] for ln in lines if ln.startswith("CRON ")]


def compare_cron(host: str, expected: set[str], remote: list[str] | None) -> list[str]:
    if remote is None:
        return [f"CRONMISSING {host} {CRON_REMOTE}"]
    if remote == ["CRON-UNREADABLE"]:
        return [f"CRONUNREADABLE {host} {CRON_REMOTE}"]
    if remote == ["CRON-UNVERIFIED"]:
        return [f"CRONUNVERIFIED {host} {CRON_REMOTE}"]
    got = cron_paths("\n".join(remote))
    return [f"CRONMISSING {host} {p}" for p in sorted(expected - got)] + [
        f"CRONEXTRA {host} {p}" for p in sorted(got - expected)
    ]


def tier1_paths(root: Path) -> list[str]:
    return sorted(
        set(template_targets(root)) | set(TIER1_DEPENDENCIES) | set(AUDIT_TARGETS) | {AUTOHEAL_REPO}
    )


def committed_files(root: Path) -> dict[str, tuple[str, bool]]:
    """repo path -> (md5 of the committed blob, committed executable?) for the compared set."""
    ls = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-tree",
            "-r",
            "HEAD",
            "--",
            "scripts/sysadmin",
            *AUDIT_TARGETS,
            AUTOHEAL_REPO,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    entries = []
    for line in ls.splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind != "blob" or mode == "120000" or "/__pycache__/" in path or path.endswith(".pyc"):
            continue  # a symlink's blob is its target text, not a script the host runs
        entries.append((path, mode, sha))
    blobs = "".join(f"{sha}\n" for _, _, sha in entries).encode()
    raw = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=blobs,
        capture_output=True,
        check=True,
    ).stdout
    out: dict[str, tuple[str, bool]] = {}
    pos = 0
    for path, mode, _sha in entries:
        header_end = raw.index(b"\n", pos)
        header = raw[pos:header_end].split()
        if len(header) != 3 or header[1] != b"blob":
            # "<sha> missing": the committed tree names a blob the object store lacks — refuse, never skip
            raise RuntimeError(
                f"git cat-file: {path}: {raw[pos:header_end].decode(errors='replace')}"
            )
        size = int(header[2])
        body = raw[header_end + 1 : header_end + 1 + size]
        pos = header_end + 1 + size + 1
        out[path] = (hashlib.md5(body, usedforsecurity=False).hexdigest(), mode == "100755")
    return out


def remote_listing(host: str) -> tuple[dict[str, tuple[str, str]], list[str] | None] | None:
    """(repo path -> (octal mode, md5), active cron lines or None) on the host, or None when unreachable."""
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, REMOTE_CMD],
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode == 255:
        return None
    return parse_listing(proc.stdout), parse_cron(proc.stdout)


def parse_listing(
    text: str, base: str = REMOTE_BASE, autoheal: str = AUTOHEAL_REMOTE
) -> dict[str, tuple[str, str]]:
    """REMOTE_CMD's output -> repo path -> (octal mode, md5), or UNREADABLE. Malformed lines are dropped."""
    out: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        parts = line.split(" ", 2)
        if len(parts) != 3:
            continue
        mode, md5, path = parts
        if mode == "UNREADABLE":
            entry = UNREADABLE
        elif _MODE_RE.fullmatch(mode) and _MD5_RE.fullmatch(md5):
            entry = (mode, md5)
        else:
            continue
        if path == autoheal:
            out[AUTOHEAL_REPO] = entry
        elif path.startswith(base):
            out[path[len(base) :]] = entry
    return out


def compare(
    host: str, expected: dict[str, tuple[str, bool]], remote: dict[str, tuple[str, str]]
) -> list[str]:
    lines = []
    for path, (md5, exe) in sorted(expected.items()):
        if path not in remote:
            lines.append(f"MISSING {host} {path}")
            continue
        if remote[path] == UNREADABLE:
            lines.append(f"UNREADABLE {host} {path}")
            continue
        mode, rmd5 = remote[path]
        if rmd5 != md5:
            lines.append(f"DRIFT {host} {path}")
        elif exe and not (int(mode, 8) & 0o100):
            lines.append(f"MODE {host} {path}")
    return lines


def _send(body: str) -> bool:
    cmd = os.environ.get("FABRIK_DRIFT_MAIL")
    argv = [cmd] if cmd else [sys.executable, str(_root() / "scripts" / "mail.py")]
    argv += [
        "send",
        "--to",
        "fabrik",
        "--to-agent",
        "fleet",
        "--kind",
        "finding",
        "--ack",
        "required",
    ]
    try:
        proc = subprocess.run(
            argv, input=body, text=True, capture_output=True, timeout=MAIL_TIMEOUT
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"vps_script_drift: mail send failed: {exc}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        print(f"vps_script_drift: mail send failed rc={proc.returncode}", file=sys.stderr)
    return proc.returncode == 0


def _drift_body(tier1: list[str], tier2_count: int, unreachable: list[str]) -> str:
    lines = [
        "Subject: VPS SCRIPT DRIFT — hosts are not running the hub's committed scripts",
        "",
        "vps_script_drift.py (daily rider on weekly_catchup.sh) compared the hub's committed HEAD with what the",
        "fleet executes. These executed (tier-1) files differ:",
        "",
        *[f"- {x}" for x in tier1],
        "",
        f"Other synced files under scripts/sysadmin/ that differ (not executed on a VPS, not mailed): {tier2_count}.",
    ]
    if unreachable:
        lines.append(
            f"Unreachable this run (their last known lines are kept): {', '.join(unreachable)}."
        )
    lines += [
        "",
        "Deploying is the operator-approved run of scripts/sync-vps-sysadmin.sh (a VPS write; it pushes the main",
        "checkout's working tree wholesale, so check for sibling WIP first). DRIFT can also mean a host is running",
        "uncommitted code that someone synced. MODE means the host copy lost its exec bit (cron cannot run it).",
        f"CRONMISSING/CRONEXTRA mean the host's {CRON_REMOTE} schedules a different set of hub scripts than",
        "scripts/bootstrap/templates/sysadmin-cron.template. Reinstall THAT FILE ONLY (a VPS write): render the",
        "template with the host's two minute slots (the sed in bootstrap-vps.sh step 14) and `sudo install -m 644",
        "-o root -g root` it — never re-run step 14 whole on a live host: it also overwrites .env.sysadmin.",
        f"CRONUNREADABLE/CRONUNVERIFIED mean the check could not read {CRON_REMOTE} or the listing was cut",
        "short: re-run the check before touching the host.",
        f"This mail repeats every {RENUDGE_DAYS} days while the same drift persists.",
    ]
    return "\n".join(lines) + "\n"


def run(mail: bool) -> int:
    root = _root()
    hosts = os.environ.get("FABRIK_DRIFT_HOSTS", " ".join(HOSTS_DEFAULT)).split()
    expected = committed_files(root)
    tier1 = set(tier1_paths(root))
    cron_expected = cron_paths(template_text(root))
    state_file = _state_path()
    state = _load_state(state_file)
    # A host dropped from FABRIK_DRIFT_HOSTS leaves the state with it.
    host_state = {h: v for h, v in state["hosts"].items() if h in hosts and isinstance(v, list)}
    unreach_runs = {
        h: v for h, v in state["unreachable_runs"].items() if h in hosts and isinstance(v, int)
    }
    unreach_mailed = {h: v for h, v in state["unreachable_mailed"].items() if h in hosts}

    printed: list[str] = []
    unreachable: list[str] = []
    tier2_count = 0
    for host in hosts:
        listing = remote_listing(host)
        if listing is None:
            unreachable.append(host)
            unreach_runs[host] = unreach_runs.get(host, 0) + 1
            print(f"UNREACHABLE {host}")
            continue
        unreach_runs[host] = 0
        unreach_mailed.pop(host, None)
        remote, cron = listing
        lines = compare(host, expected, remote)
        cron_lines = compare_cron(
            host, cron_expected, cron
        )  # the cron set decides what runs: tier 1
        printed += lines + cron_lines
        host_state[host] = [x for x in lines if x.split(" ", 2)[2] in tier1] + cron_lines
        tier2_count += sum(1 for x in lines if x.split(" ", 2)[2] not in tier1)

    for line in printed:
        print(line)
    fleet_tier1 = sorted({x for h in hosts for x in host_state.get(h, [])})
    print(
        f"vps_script_drift: {len(fleet_tier1)} tier-1 and {tier2_count} tier-2 differences across "
        f"{len(hosts)} hosts ({len(unreachable)} unreachable)"
    )
    rc = 2 if unreachable else (1 if printed else 0)
    if not mail:
        return rc

    if rc == 0:
        if state_file.exists():
            state_file.unlink()
        return 0
    now = _now()
    signature = hashlib.sha256("\n".join(fleet_tier1).encode()).hexdigest() if fleet_tier1 else ""
    if not signature:
        # tier-1 is clean (only tier-2 or unreachable): forget the last mailed signature, so the same
        # tier-1 drift coming back later mails again instead of waiting out RENUDGE_DAYS.
        state.pop("signature", None)
        state.pop("mailed_at", None)
    if signature and (
        signature != state.get("signature")
        or now - _num(state.get("mailed_at")) >= RENUDGE_DAYS * 86400
    ):
        if _send(_drift_body(fleet_tier1, tier2_count, unreachable)):
            state["signature"], state["mailed_at"] = signature, now
    for host in unreachable:
        if unreach_runs.get(host, 0) >= UNREACHABLE_RUNS and not unreach_mailed.get(host):
            body = (
                f"Subject: VPS SCRIPT DRIFT check cannot reach {host}\n\n"
                f"vps_script_drift.py has failed to ssh to {host} (BatchMode) on {unreach_runs[host]} consecutive "
                "daily runs, so drift on that host is no longer being checked. Check the hub's key and the host's "
                "known_hosts entry.\n"
            )
            if _send(body):
                unreach_mailed[host] = True
    state.update(
        {
            "hosts": host_state,
            "unreachable_runs": unreach_runs,
            "unreachable_mailed": unreach_mailed,
        }
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_name(state_file.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(
        tmp, state_file
    )  # atomic: a crash mid-write cannot leave a half state that resets the counters
    return rc


def _num(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _load_state(path: Path) -> dict:
    """The watermark, with every section a dict; an unreadable or mis-shaped file is reported and reset."""
    try:
        state = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError) as exc:
        print(f"vps_script_drift: state {path} unreadable ({exc}); starting fresh", file=sys.stderr)
        state = {}
    if not isinstance(state, dict):
        print(f"vps_script_drift: state {path} is not an object; starting fresh", file=sys.stderr)
        state = {}
    for key in ("hosts", "unreachable_runs", "unreachable_mailed"):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    return state


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    stamp = args[args.index("--stamp") + 1] if "--stamp" in args[:-1] else None
    try:
        rc = run(mail="--mail" in args)
    except Exception:  # noqa: BLE001 — any failure of the check itself is exit 3, distinct from a verdict
        traceback.print_exc()
        return 3
    if stamp:
        Path(stamp).parent.mkdir(parents=True, exist_ok=True)
        Path(stamp).touch()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
