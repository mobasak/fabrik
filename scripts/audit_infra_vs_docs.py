#!/usr/bin/env python3
"""Probe-vs-doc audit for the VPS fleet.

Runs a fixed set of presence-probes against vps1/vps2/vps3 via SSH and emits:

1. YAML report → docs/infrastructure/probe-reports/infra-probe-YYYYMMDD-HHMM.yaml  (tracked; commit alongside doc edits per Lesson 69)
2. Markdown table → stdout  (paste-ready for vps-status.md § Verification log)

Designed to close the gap exposed on 2026-05-31 evening: three doc-audit passes
claimed UFW was active on vps2/vps3 because each grepped for failure symptoms.
None ran `dpkg -l ufw`. Symptom-grep cannot find an absence — this script does
presence-probing instead.

Lesson 69 in docs/LESSONS_LEARNT.md.

Usage:
    scripts/audit_infra_vs_docs.py                  # run probes, write report
    scripts/audit_infra_vs_docs.py --check          # lint: every infra doc must
                                                    # have a 'Last probe report:' link
    scripts/audit_infra_vs_docs.py --hosts vps,vps2 # probe a subset
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "infrastructure" / "probe-reports"
INFRA_DOCS = [
    # Plan W6 § Acceptance originally listed 4 docs; we extended to 6, then to
    # 7 with vps-hub-rebuild.md (2026-06-01, DR-in-hours track) since it makes
    # provenance-bearing claims about backup-snapshot freshness + service
    # counts that age out fast if a future drill doesn't re-anchor them.
    # Linter enforces fresh-report citation on all 7.
    REPO_ROOT / "docs/infrastructure/vps-complete-inventory.md",
    REPO_ROOT / "docs/infrastructure/vps-status.md",
    REPO_ROOT / "docs/infrastructure/vps-urls.md",
    REPO_ROOT / "docs/infrastructure/vps-bootstrap-plan.md",
    REPO_ROOT / "docs/infrastructure/vps-ai-sysadmin.md",
    REPO_ROOT / "docs/infrastructure/vps-residue-policy.md",
    REPO_ROOT / "docs/infrastructure/vps-hub-rebuild.md",
    REPO_ROOT / "docs/infrastructure/vps-fleet-architecture.md",
    REPO_ROOT / "docs/infrastructure/vps-spoke-rebuild.md",
]

# Probes are plain strings (NOT f-strings) — the Docker `{{.Names}}` format must
# pass through unmodified.
PROBES: dict[str, str] = {
    "container_count": "sudo docker ps --format '{{.Names}}' | wc -l",
    "ufw_installed": "dpkg -l ufw 2>/dev/null | awk '/^ii/ {print $2}' || true",
    "ufw_active": "sudo systemctl is-active ufw 2>/dev/null || echo not-installed",
    "ufw_rule_count_v4": "sudo ufw status 2>/dev/null | grep -cE '^[0-9]+/(tcp|udp) +ALLOW' || echo 0",
    "fail2ban_active": "sudo systemctl is-active fail2ban 2>/dev/null || echo not-installed",
    "fail2ban_total_ban": "sudo fail2ban-client status sshd 2>/dev/null | awk '/Total banned/ {print $NF}' || echo n/a",
    "listening_public": "sudo ss -tnlp 2>/dev/null | awk 'NR>1 {print $4}' | grep -E '^(0\\.0\\.0\\.0|\\*):' | sort -u | tr '\\n' ',' | sed 's/,$//'",
    "listening_mesh": "sudo ss -tnlp 2>/dev/null | awk 'NR>1 {print $4}' | grep '^10\\.99\\.' | sort -u | tr '\\n' ',' | sed 's/,$//'",
    "docker_user_rules": "sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -cE 'DROP|ACCEPT' || echo 0",
    "iptables_backend": "sudo update-alternatives --display iptables 2>&1 | grep -oE 'iptables-(nft|legacy)' | head -1 || echo unknown",
    "wg_peers_alive": "sudo wg show wg0 latest-handshakes 2>/dev/null | awk '{age=systime()-$2; if (age<300) c++} END {print c+0}' || echo 0",
    "kernel": "uname -r",
    "uptime_s": "cut -d. -f1 /proc/uptime",
    "disk_root_pct": 'df / 2>/dev/null | awk \'NR==2 {gsub("%",""); print $5}\'',
    "ram_used_mb": "free -m 2>/dev/null | awk '/^Mem:/ {print $3}'",
    "ram_total_mb": "free -m 2>/dev/null | awk '/^Mem:/ {print $2}'",
    "docker_network_fabrik": "sudo docker network inspect fabrik --format '{{.Name}}' 2>/dev/null || echo missing",
}

HOSTS_DEFAULT = ["vps", "vps2", "vps3"]


def _run_ssh(host: str, cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a command on a host via SSH alias. Returns (rc, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", host, cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:  # noqa: BLE001
        return 1, "", repr(e)


_MARKER = "===W6PROBE-MARKER==="  # unlikely to appear in any probe output


def probe_host(host: str) -> dict[str, str]:
    """Run all PROBES against a host in a SINGLE SSH session and demux the output.

    Performance: this collapses ~17 sequential ssh calls (each paying TCP+TLS
    handshake + auth + shell startup) into 1 ssh call running 17 commands in
    one remote shell. Empirical speedup ~10x for 17 probes; brings the audit
    runtime from ~75s (51 connections across 3 hosts) under the plan's <10s
    target. Lesson 70.

    Each probe's output is preceded by a marker line that names the probe;
    the demuxer reassembles the per-probe dict on the parser side. Each
    probe is `|| true`-guarded so a failure in one doesn't truncate the
    rest of the session.
    """
    parts: list[str] = []
    for name, cmd in PROBES.items():
        # Force a newline BEFORE the marker so probes whose output has no
        # trailing newline (e.g. `tr '\n' ',' | sed 's/,$//'`) don't cause
        # the next marker to concatenate onto the same line as the prior
        # probe's last byte. Without the leading \n, listening_public-style
        # probes silently leaked the marker into their value. Lesson 71.
        parts.append(f"printf '\\n%s\\n' '{_MARKER}{name}'")
        parts.append(f"({cmd}) 2>&1 || true")
    parts.append(f"printf '\\n%s\\n' '{_MARKER}END'")
    bundled = "\n".join(parts)

    rc, out, _err = _run_ssh(host, bundled, timeout=60)
    if rc != 0 and not out:
        # Total failure — return error placeholders for every probe.
        return dict.fromkeys(PROBES, f"ERR ssh rc={rc}")

    # Demux
    results: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in out.split("\n"):
        if line.startswith(_MARKER):
            # Close out the previous probe (if any)
            if current is not None:
                results[current] = "\n".join(buf).strip() or "(empty)"
            tag = line[len(_MARKER) :].strip()
            current = tag if tag != "END" else None
            buf = []
        elif current is not None:
            buf.append(line)
    # In case the trailing marker was lost, flush whatever remains.
    if current is not None and current not in results:
        results[current] = "\n".join(buf).strip() or "(empty)"

    # Fill any probe the host didn't return (shouldn't happen, but be defensive).
    for name in PROBES:
        if name not in results:
            results[name] = "ERR: missing from bundled output"
    return results


def _legacy_probe_host_per_call(host: str) -> dict[str, str]:
    """Legacy per-probe-per-ssh implementation, kept for fallback. Slow.

    Retained only so a future bug in the demuxer can be sanity-checked by
    swapping `probe_host = _legacy_probe_host_per_call` at the call site.
    """
    results: dict[str, str] = {}
    for name, cmd in PROBES.items():
        rc, out, err = _run_ssh(host, cmd)
        if rc == 0:
            results[name] = out or "(empty)"
        else:
            results[name] = f"ERR rc={rc}: {err or out}"[:200]
    return results


def emit_yaml(report: dict, path: Path) -> None:
    """Write the report as YAML without depending on PyYAML."""
    lines = [
        f"# Infrastructure probe report — {report['timestamp']}",
        "# Generated by scripts/audit_infra_vs_docs.py",
        f"timestamp: {report['timestamp']}",
        "hosts:",
    ]
    for host, data in report["hosts"].items():
        lines.append(f"  {host}:")
        for k, v in data.items():
            # Quote values containing special chars (JSON quoting is YAML-safe)
            vs = json.dumps(str(v)) if any(c in str(v) for c in [":", "#", "\n", "'"]) else str(v)
            lines.append(f"    {k}: {vs}")
    path.write_text("\n".join(lines) + "\n")


def emit_markdown(report: dict) -> str:
    """Render the report as a Markdown table for direct paste into vps-status.md."""
    hosts = list(report["hosts"].keys())
    probes = list(PROBES.keys())
    lines = [
        f"### Probe report — {report['timestamp']}",
        "",
        "| Probe | " + " | ".join(hosts) + " |",
        "| :--- | " + " | ".join([":---"] * len(hosts)) + " |",
    ]
    for p in probes:
        row = [p]
        for h in hosts:
            v = str(report["hosts"][h].get(p, "?"))
            # Truncate cells that are very long (e.g., big lists of listening sockets)
            if len(v) > 60:
                v = v[:57] + "..."
            row.append(v)
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def check_doc_headers() -> int:
    """Lint: every infra doc must have a `Last probe report:` line pointing
    to a real file under docs/infrastructure/probe-reports/. Returns count of warnings."""
    pattern = re.compile(
        r"\*\*Last probe report:\*\*\s*\[`?((?:\.\./)*(?:docs/infrastructure/)?probe-reports/infra-probe-[^\)`]+\.yaml)`?\]"
    )
    warnings = 0
    for doc in INFRA_DOCS:
        if not doc.exists():
            print(f"WARN: doc not found: {doc}")
            warnings += 1
            continue
        content = doc.read_text()
        m = pattern.search(content)
        if not m:
            print(f"WARN: {doc.relative_to(REPO_ROOT)} missing 'Last probe report:' header")
            warnings += 1
            continue
        # Resolve relative to the doc's directory (markdown link semantics)
        cited = (doc.parent / m.group(1)).resolve()
        if not cited.exists():
            try:
                rel = cited.relative_to(REPO_ROOT)
            except ValueError:
                rel = cited
            print(f"WARN: {doc.relative_to(REPO_ROOT)} cites {rel} but file does not exist")
            warnings += 1
    return warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--hosts", default=",".join(HOSTS_DEFAULT), help="Comma-separated list of SSH host aliases"
    )
    ap.add_argument(
        "--check", action="store_true", help="Lint mode: verify infra docs cite a probe report"
    )
    ap.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help=f"Output directory for YAML report (default: {DATA_DIR})",
    )
    args = ap.parse_args()

    if args.check:
        n = check_doc_headers()
        if n:
            print(f"\n{n} doc header warning(s).")
            return 1
        print("OK: every infra doc cites a probe report file that exists.")
        return 0

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%MZ")

    print(f"# Probing {len(hosts)} host(s): {hosts}", file=sys.stderr)
    report = {"timestamp": timestamp, "hosts": {}}
    for h in hosts:
        print(f"# probing {h}...", file=sys.stderr)
        report["hosts"][h] = probe_host(h)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = data_dir / f"infra-probe-{timestamp}.yaml"
    emit_yaml(report, yaml_path)
    try:
        display = yaml_path.relative_to(REPO_ROOT)
    except ValueError:
        display = yaml_path  # --data-dir outside repo: log absolute path
    print(f"# wrote {display}", file=sys.stderr)
    print()
    print(emit_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
