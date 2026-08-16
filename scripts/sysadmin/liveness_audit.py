#!/usr/bin/env python3
# AFTER-EDIT: tests/test_liveness_audit.py | docs/workstation/liveness.md | .fabrik/liveness-registry.json | scripts/sysadmin/kaizen_metrics.py | INDEX.md
"""LIVENESS AUDIT — we verify correctness at write-time and never verify liveness at run-time.

Every failure this file exists to catch had passed code review and had tests. None of them
had proof it was RUNNING:

  * kaizen was declared "binding -- weekly" in two charters and ran 0 times in 4 days.
  * 6 of 11 Tier-3 gate checks reported PASS while asserting nothing (no `__main__`).
  * The Claude-config DR backup had never once run from cron -- its `>> /var/log/...`
    redirect was uncreatable by this user, so the shell aborted before the script.
  * Alert delivery was dead fleet-wide; every quota/keepalive/CI/watchdog alert reached
    nobody.
  * The fabrik-mail digest the doc promised "so nothing rots silently" had no cron line.

Three proofs, one report:

  PROOF 1  HEARTBEAT    did it fire?   registered surface vs. its evidence age
  PROOF 2  VACUITY      can it fail?   every gate check vs. a deliberately-bad canary
  PROOF 3  DOC-CLAIM    is it true?    machine-checkable doc claims vs. the live box

THE THREE-STATE RULE (the reason this file is not a rumour mill)
---------------------------------------------------------------
On 2026-08-16 an orchestrator's own probes lied three times, and each lie reached the
operator as fact:

  1. `grep -c "arg=sweep" ~/.claude/sound-debug.log` printed nothing, rc=1 -> "the reboot
     sweep has NEVER run". Truth: the file holds one invalid UTF-8 byte, GNU grep called it
     BINARY and suppressed every match. `grep -a` shows 21 events, including that morning's.
  2. `ls specs/services/ | grep apprise` -> nothing -> "Apprise was never fabrik-managed".
     Truth: the spec is `specs/infrastructure/apprise.yaml`. One directory, generalised.
  3. `ssh vps docker ps` -> EMPTY -> "no apprise container, not even stopped". Truth: the
     ssh user is not in the `docker` group; every call failed with permission denied and
     printed NOTHING to stdout. With sudo: 31 containers, apprise healthy, HTTP 200.

In all three, ABSENCE OF EVIDENCE arrived as EVIDENCE OF ABSENCE. So every probe here
validates its own INSTRUMENT against a positive control BEFORE it is allowed to report an
absence, and the verdict space has three states -- LIVE / DEAD / UNKNOWN -- never two. A
probe that cannot prove its instrument works reports UNKNOWN with the fault NAMED. It may
never report DEAD. `finding()` is the single constructor and it enforces this; there is no
other way to build a Finding.

Corollaries wired in below:
  * Evidence files are read as BYTES and decoded with errors="replace". This module NEVER
    shells out to `grep` for evidence (failure 1).
  * A missing file whose parent directory is absent or unreadable is UNKNOWN, not DEAD
    (failure 2 in miniature: the thing may simply not be where we looked).
  * A `/tmp` evidence path is declared `volatile` in the registry; its absence is UNKNOWN,
    because /tmp is cleared on boot and silence there proves nothing.
  * Remote docker probes use `sudo docker` and treat a permission failure as UNKNOWN
    (failure 3).

This is a REPORT, not a gate. It exits 0 by default -- a monitoring layer that blocks work
gets disabled, and then it monitors nothing. `--strict` is the opt-in CI mode.

Usage:
    python scripts/sysadmin/liveness_audit.py                  # human table
    python scripts/sysadmin/liveness_audit.py --json           # machine report
    python scripts/sysadmin/liveness_audit.py --proof heartbeat
    python scripts/sysadmin/liveness_audit.py --strict         # exit 1 on any DEAD/INERT/STALE
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ".fabrik/liveness-registry.json"

# The audit's own crontab proposal. PRINTED, never installed -- 06:40 lands the fresh
# liveness report just before kaizen's 06:45 measurement reads it.
PROPOSED_CRON = (
    "40 6 * * 1 cd /opt/fabrik && .venv/bin/python scripts/sysadmin/liveness_audit.py --json "
    ">> $HOME/.claude/liveness.log 2>&1"
)


class Verdict(str, Enum):
    """Three states. Two states is how absence of evidence becomes evidence of absence."""

    LIVE = "LIVE"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Instrument:
    """A probe's measuring device, and whether it has been PROVEN to work right now.

    `ok=False` is not a soft warning: no finding built on an unproven instrument may claim
    either presence or absence. See `finding()`.
    """

    name: str
    ok: bool
    fault: str = ""

    @staticmethod
    def proven(name: str) -> Instrument:
        return Instrument(name=name, ok=True)

    @staticmethod
    def broken(name: str, fault: str) -> Instrument:
        return Instrument(name=name, ok=False, fault=fault or "instrument unproven")


@dataclass
class Finding:
    proof: str
    id: str
    kind: str
    verdict: Verdict
    detail: str
    instrument: str
    instrument_fault: str = ""
    # A machine-readable sub-class of a DEAD verdict: overdue | unscheduled | not-listening
    # | wrong-state | absent | inert | stale-doc. Empty for LIVE/UNKNOWN.
    reason_class: str = ""
    doc: str = ""

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["verdict"] = self.verdict.value
        return out


def finding(
    *,
    proof: str,
    id: str,
    kind: str,
    instrument: Instrument,
    verdict: Verdict,
    detail: str,
    reason_class: str = "",
    doc: str = "",
) -> Finding:
    """THE THREE-STATE RULE, in code. The ONLY constructor for a Finding.

    An unproven instrument cannot prove presence either, so ANY instrument fault collapses
    the verdict to UNKNOWN and carries the fault forward by name. This one function is what
    would have stopped all three of 2026-08-16's false findings before they were reported.
    """
    if not instrument.ok:
        return Finding(
            proof=proof,
            id=id,
            kind=kind,
            verdict=Verdict.UNKNOWN,
            detail=detail,
            instrument=instrument.name,
            instrument_fault=instrument.fault or "instrument unproven",
            reason_class="",
            doc=doc,
        )
    return Finding(
        proof=proof,
        id=id,
        kind=kind,
        verdict=verdict,
        detail=detail,
        instrument=instrument.name,
        instrument_fault="",
        reason_class=reason_class if verdict is Verdict.DEAD else "",
        doc=doc,
    )


# --------------------------------------------------------------------------- instruments

# A crontab entry: @-shortcut, or five schedule fields followed by a command.
CRON_LINE = re.compile(
    r"^(?:@(?:reboot|yearly|annually|monthly|weekly|daily|midnight|hourly)"
    r"|[\d*/,\-]+(?:\s+[\d*/,\-A-Za-z]+){4})\s+\S"
)
# "2026-08-16 07:32:34  arg=sweep ..." -- the leading stamp of a dated log line.
LOG_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}):(\d{2}):(\d{2}))?")
_UNIT_STATES = {
    "enabled",
    "enabled-runtime",
    "disabled",
    "static",
    "masked",
    "masked-runtime",
    "alias",
    "indirect",
    "generated",
    "transient",
    "linked",
    "linked-runtime",
}

# The positive control for the evidence-reading path. The \xff is an INVALID UTF-8 byte,
# deliberately placed BEFORE the marker: a reader that mishandles it (as GNU grep does)
# fails to find the marker, and the whole log instrument is then declared broken rather
# than every log being reported DEAD.
_CONTROL_BYTES = b"liveness positive control \xff\xfe\n1970-01-01 00:00:00 marker=positive-control\n"


def read_text(path: Path) -> str:
    """Read evidence as BYTES, decode lossily. Never `grep`; never strict UTF-8."""
    return path.read_bytes().decode("utf-8", errors="replace")


def age_hours(path: Path, now: float | None = None) -> float:
    import time

    now = time.time() if now is None else now
    return (now - path.stat().st_mtime) / 3600.0


class Box:
    """Every read of the live box, each gated behind a proven positive control.

    Instruments are computed once and cached: a broken instrument must produce the SAME
    UNKNOWN for every probe that depends on it, not a flapping mixture.
    """

    def __init__(self, home: Path | None = None, settings_paths: list[Path] | None = None):
        self.home = home or Path.home()
        self._settings_paths = settings_paths
        self._cache: dict[str, Any] = {}

    def _memo(self, key: str, fn: Any) -> Any:
        if key not in self._cache:
            try:
                self._cache[key] = fn()
            except Exception as exc:  # never raise out of a probe
                self._cache[key] = (Instrument.broken(key, f"{type(exc).__name__}: {exc}"), None)
        return self._cache[key]

    # -- log/file evidence ------------------------------------------------------------
    def log_instrument(self) -> Instrument:
        """Positive control: round-trip a file we KNOW is fresh, through the real reader.

        Proves three things at once before any log is called stale: stat works and the
        clock is sane, the reader survives an invalid UTF-8 byte, and content after that
        byte is still findable. If this fails, every log-backed probe is UNKNOWN.
        """

        def build() -> tuple[Instrument, None]:
            name = "log-reader"
            with tempfile.TemporaryDirectory() as td:
                probe = Path(td) / "control.log"
                probe.write_bytes(_CONTROL_BYTES)
                text = read_text(probe)
                if "marker=positive-control" not in text:
                    return (
                        Instrument.broken(
                            name,
                            "the evidence reader lost content after an invalid UTF-8 byte "
                            "(the GNU-grep binary-suppression class)",
                        ),
                        None,
                    )
                age = age_hours(probe)
            if age > (5 / 60.0):
                return (
                    Instrument.broken(name, f"a just-written file measured {age:.2f}h old (clock)"),
                    None,
                )
            if age < -(1 / 60.0):
                return (Instrument.broken(name, f"a just-written file measured {age:.2f}h (future)"), None)
            return (Instrument.proven(name), None)

        return self._memo("log", build)[0]

    def evidence_age(self, raw: str, volatile: bool) -> tuple[Instrument, float | None]:
        """Age of an evidence file in hours, or an instrument fault explaining why not.

        A MISSING file is only real absence when we can prove we looked in a place that
        exists and is readable -- otherwise it is failure 2 in miniature.
        """
        base = self.log_instrument()
        if not base.ok:
            return base, None
        path = self.expand(raw)
        name = f"log-reader[{raw}]"
        parent = path.parent
        if not path.exists():
            if not parent.is_dir():
                return Instrument.broken(name, f"parent directory {parent} does not exist"), None
            if not os.access(parent, os.R_OK | os.X_OK):
                return Instrument.broken(name, f"parent directory {parent} is not readable"), None
            if volatile:
                return (
                    Instrument.broken(
                        name,
                        f"{parent} is volatile (cleared on boot); an absent file there proves "
                        "nothing about whether the job ran",
                    ),
                    None,
                )
            return Instrument.proven(name), None  # genuine, provable absence
        if not os.access(path, os.R_OK):
            return Instrument.broken(name, f"{path} exists but is not readable by this user"), None
        try:
            return Instrument.proven(name), age_hours(path)
        except OSError as exc:
            return Instrument.broken(name, f"stat failed on {path}: {exc}"), None

    def marker_age(self, raw: str, marker: str) -> tuple[Instrument, float | None, int]:
        """Age of the LAST dated line carrying `marker`, plus how many lines carry it.

        This is the reboot-sweep probe, and the direct answer to failure 1.
        """
        inst, _ = self.evidence_age(raw, volatile=False)
        if not inst.ok:
            return inst, None, 0
        path = self.expand(raw)
        if not path.exists():
            return inst, None, 0
        hits = [ln for ln in read_text(path).splitlines() if marker in ln]
        if not hits:
            return inst, None, 0
        for line in reversed(hits):
            when = _stamp_age(line)
            if when is not None:
                return inst, when, len(hits)
        return (
            Instrument.broken(
                f"log-reader[{raw}]",
                f"{len(hits)} line(s) carry {marker!r} but none is timestamped, so the "
                "evidence cannot be aged",
            ),
            None,
            len(hits),
        )

    # -- crontab ----------------------------------------------------------------------
    def crontab(self) -> tuple[Instrument, list[str]]:
        def build() -> tuple[Instrument, list[str]]:
            name = "crontab -l"
            if shutil.which("crontab") is None:
                return Instrument.broken(name, "crontab binary not on PATH"), []
            proc = _run(["crontab", "-l"])
            if proc is None:
                return Instrument.broken(name, "crontab -l could not be executed"), []
            if proc.returncode != 0:
                return (
                    Instrument.broken(
                        name, f"crontab -l exited {proc.returncode}: {proc.stderr.strip()[:160]}"
                    ),
                    [],
                )
            lines = [ln for ln in proc.stdout.splitlines() if CRON_LINE.match(ln)]
            if not lines:
                # An empty crontab is indistinguishable from a broken read, and calling
                # every cron DEAD off a blank page is exactly failure 2.
                return Instrument.broken(name, "crontab -l returned no parseable cron entries"), []
            return Instrument.proven(name), lines

        return self._memo("cron", build)

    def crontab_raw(self) -> str:
        proc = _run(["crontab", "-l"])
        return proc.stdout if proc and proc.returncode == 0 else ""

    # -- listening ports --------------------------------------------------------------
    def ports(self) -> tuple[Instrument, set[int]]:
        def build() -> tuple[Instrument, set[int]]:
            name = "ss -ltn"
            if shutil.which("ss") is None:
                return Instrument.broken(name, "ss binary not on PATH"), set()
            proc = _run(["ss", "-ltn"])
            if proc is None or proc.returncode != 0:
                detail = proc.stderr.strip()[:160] if proc else "not executable"
                return Instrument.broken(name, f"ss -ltn failed: {detail}"), set()
            found: set[int] = set()
            for line in proc.stdout.splitlines()[1:]:
                cols = line.split()
                if len(cols) < 4:
                    continue
                _, _, port = cols[3].rpartition(":")
                if port.isdigit():
                    found.add(int(port))
            if not found:
                return Instrument.broken(name, "ss -ltn listed no listening sockets at all"), set()
            return Instrument.proven(name), found

        return self._memo("ports", build)

    # -- systemd ----------------------------------------------------------------------
    def systemd(self) -> Instrument:
        def build() -> tuple[Instrument, None]:
            name = "systemctl"
            if shutil.which("systemctl") is None:
                return Instrument.broken(name, "systemctl not on PATH"), None
            # Positive control: a unit that must exist on any systemd box.
            proc = _run(["systemctl", "is-enabled", "cron.service"])
            if proc is None or proc.stdout.strip() not in _UNIT_STATES:
                got = (proc.stdout + proc.stderr).strip()[:120] if proc else "not executable"
                return Instrument.broken(name, f"control unit cron.service returned {got!r}"), None
            return Instrument.proven(name), None

        return self._memo("systemd", build)[0]

    def unit_state(self, unit: str) -> tuple[Instrument, tuple[str, str] | None]:
        """(is-enabled, is-active) for a unit — SYSTEM manager first, then the USER manager.

        A user unit queried at system level answers `not-found`, which reads exactly like
        "this unit does not exist". That is failure 3 again: one manager searched,
        generalised to absence. `ai.traycer.host.service` is `not-found` system-wide and
        `enabled` under `--user`. If the user bus is unreachable we cannot rule the user
        manager out, so the verdict is UNKNOWN, never DEAD.
        """
        base = self.systemd()
        if not base.ok:
            return base, None
        name = f"systemctl[{unit}]"
        enabled = _run(["systemctl", "is-enabled", unit])
        active = _run(["systemctl", "is-active", unit])
        if enabled is None or active is None:
            return Instrument.broken(name, "systemctl could not be executed"), None
        sys_enabled = enabled.stdout.strip() or enabled.stderr.strip()[:80]
        sys_active = active.stdout.strip() or active.stderr.strip()[:80]
        if sys_enabled in _UNIT_STATES:
            return Instrument.proven(name), (sys_enabled, sys_active)

        u_enabled = _run(["systemctl", "--user", "is-enabled", unit])
        u_active = _run(["systemctl", "--user", "is-active", unit])
        if u_enabled is None or u_active is None:
            return Instrument.broken(name, "the user systemd manager could not be queried"), None
        got = u_enabled.stdout.strip() or u_enabled.stderr.strip()[:120]
        if got in _UNIT_STATES:
            return Instrument.proven(f"{name}(--user)"), (got, u_active.stdout.strip() or "unknown")
        if "not-found" not in got:
            return (
                Instrument.broken(
                    name,
                    f"system manager says {sys_enabled!r} and the user bus is unreachable "
                    f"({got!r}), so the unit cannot be ruled out",
                ),
                None,
            )
        return Instrument.proven(name), (sys_enabled, sys_active)

    # -- Claude hooks -----------------------------------------------------------------
    def settings_files(self) -> list[Path]:
        if self._settings_paths is not None:
            return self._settings_paths
        return [
            self.home / ".claude" / "settings.json",
            self.home / ".claude" / "settings.local.json",
            REPO_ROOT / ".claude" / "settings.json",
            REPO_ROOT / ".claude" / "settings.local.json",
        ]

    def hooks(self) -> tuple[Instrument, list[str]]:
        def build() -> tuple[Instrument, list[str]]:
            name = "claude settings hooks"
            commands: list[str] = []
            parsed = 0
            for path in self.settings_files():
                if not path.is_file():
                    continue
                try:
                    data = json.loads(read_text(path))
                except (json.JSONDecodeError, OSError):
                    continue
                parsed += 1
                for entries in (data.get("hooks") or {}).values():
                    for entry in entries or []:
                        for hook in entry.get("hooks") or []:
                            cmd = hook.get("command")
                            if isinstance(cmd, str):
                                commands.append(cmd)
            if not parsed:
                return Instrument.broken(name, "no readable settings.json among the 4 hook layers"), []
            if not commands:
                return Instrument.broken(name, "settings parsed but declared no hook commands"), []
            return Instrument.proven(name), commands

        return self._memo("hooks", build)

    # -- misc -------------------------------------------------------------------------
    def expand(self, raw: str) -> Path:
        return Path(os.path.expandvars(str(raw).replace("~", str(self.home), 1)))


def _run(cmd: list[str], timeout: int = 30, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _stamp_age(line: str, now: dt.datetime | None = None) -> float | None:
    m = LOG_STAMP.match(line.strip())
    if not m:
        return None
    now = now or dt.datetime.now()
    try:
        day = dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    hh, mm, ss = (int(m.group(i)) if m.group(i) else 0 for i in (2, 3, 4))
    try:
        when = dt.datetime.combine(day, dt.time(hh, mm, ss))
    except ValueError:
        return None
    return (now - when).total_seconds() / 3600.0


# ------------------------------------------------------------------ PROOF 1: heartbeat


def load_registry(path: Path) -> tuple[dict[str, Any], str]:
    try:
        return json.loads(read_text(path)), ""
    except FileNotFoundError:
        return {}, f"no registry at {path}"
    except (json.JSONDecodeError, OSError) as exc:
        return {}, f"registry at {path} is unreadable: {exc}"


def proof_heartbeat(box: Box, registry: dict[str, Any], registry_fault: str) -> dict[str, Any]:
    """Did it fire? Registered surface vs. the age of its evidence."""
    findings: list[Finding] = []
    surfaces = registry.get("surfaces") or []
    if registry_fault or not surfaces:
        broken = Instrument.broken(
            "registry", registry_fault or "registry declares no surfaces — nothing is monitored"
        )
        findings.append(
            finding(
                proof="heartbeat",
                id="(registry)",
                kind="registry",
                instrument=broken,
                verdict=Verdict.DEAD,
                detail="the heartbeat proof has no surfaces to check",
            )
        )
        return {"findings": [f.as_dict() for f in findings], "unregistered": {}, "summary": _tally(findings)}

    cron_inst, cron_lines = box.crontab()

    for surface in surfaces:
        findings.append(_heartbeat_one(box, surface, cron_inst, cron_lines))

    return {
        "findings": [f.as_dict() for f in findings],
        "unregistered": _unregistered(box, registry, cron_inst, cron_lines),
        "summary": _tally(findings),
    }


def _heartbeat_one(
    box: Box, surface: dict[str, Any], cron_inst: Instrument, cron_lines: list[str]
) -> Finding:
    sid = str(surface.get("id", "?"))
    kind = str(surface.get("kind", "?"))
    doc = str(surface.get("doc", ""))
    evidence = surface.get("evidence") or {}
    etype = str(evidence.get("type", "none"))
    make = lambda inst, verdict, detail, rc="": finding(  # noqa: E731 - local partial
        proof="heartbeat", id=sid, kind=kind, instrument=inst, verdict=verdict,
        detail=detail, reason_class=rc, doc=doc,
    )

    # A cron surface is DEAD the moment its schedule is gone, whatever the stale log says.
    if kind == "cron":
        match = str(surface.get("cron_match", ""))
        if not cron_inst.ok:
            return make(cron_inst, Verdict.UNKNOWN, f"cannot read the crontab to look for {match!r}")
        if not any(match in line for line in cron_lines):
            return make(
                cron_inst,
                Verdict.DEAD,
                f"no active crontab line matches {match!r} ({len(cron_lines)} entries read)",
                "unscheduled",
            )

    if etype == "none":
        return make(
            Instrument.broken(f"{sid}:evidence", "no evidence channel declared for this surface"),
            Verdict.UNKNOWN,
            "scheduled, but nothing it writes can be observed — unfalsifiable by construction",
        )

    if etype == "port":
        inst, listening = box.ports()
        port = int(evidence.get("port", 0))
        if not inst.ok:
            return make(inst, Verdict.UNKNOWN, f"cannot enumerate listening sockets for port {port}")
        if port in listening:
            return make(inst, Verdict.LIVE, f"port {port} is listening")
        return make(inst, Verdict.DEAD, f"port {port} is not listening", "not-listening")

    if etype == "unit":
        unit = str(evidence.get("unit", ""))
        expect = str(evidence.get("expect", "enabled"))
        inst, state = box.unit_state(unit)
        if not inst.ok or state is None:
            return make(inst, Verdict.UNKNOWN, f"cannot read the state of {unit}")
        enabled, active = state
        if enabled == expect:
            return make(inst, Verdict.LIVE, f"{unit} is {enabled} / {active}")
        return make(inst, Verdict.DEAD, f"{unit} is {enabled} / {active}, expected {expect}", "wrong-state")

    if etype == "hook":
        inst, commands = box.hooks()
        needle = str(evidence.get("command_contains", ""))
        if not inst.ok:
            return make(inst, Verdict.UNKNOWN, f"cannot read hook configuration to find {needle!r}")
        if any(needle in c for c in commands):
            return make(inst, Verdict.LIVE, f"a hook command contains {needle!r}")
        return make(inst, Verdict.DEAD, f"no hook command contains {needle!r}", "absent")

    if etype in ("log", "log_marker"):
        raw = str(evidence.get("path", ""))
        limit = float(surface.get("max_age_hours", 24))
        if etype == "log_marker":
            marker = str(evidence.get("marker", ""))
            inst, age, hits = box.marker_age(raw, marker)
            if not inst.ok:
                return make(inst, Verdict.UNKNOWN, f"cannot age {marker!r} in {raw}")
            if age is None:
                return make(
                    inst, Verdict.DEAD, f"{raw} carries no line with {marker!r}", "absent"
                )
            where = f"last {marker!r} in {raw} is {age:.1f}h old ({hits} occurrence(s))"
        else:
            inst, age = box.evidence_age(raw, bool(evidence.get("volatile")))
            if not inst.ok:
                return make(inst, Verdict.UNKNOWN, f"cannot age {raw}")
            if age is None:
                return make(
                    inst,
                    Verdict.DEAD,
                    f"{raw} does not exist, though its directory does — the job has never "
                    "written evidence",
                    "absent",
                )
            where = f"{raw} is {age:.1f}h old"
        if age <= limit:
            return make(inst, Verdict.LIVE, f"{where}, within {limit:g}h")
        return make(inst, Verdict.DEAD, f"{where}, over its {limit:g}h budget", "overdue")

    return make(
        Instrument.broken(f"{sid}:evidence", f"unknown evidence type {etype!r}"),
        Verdict.UNKNOWN,
        "the registry declares an evidence type this audit cannot probe",
    )


def _unregistered(
    box: Box, registry: dict[str, Any], cron_inst: Instrument, cron_lines: list[str]
) -> dict[str, Any]:
    """Surfaces PRESENT on the box but ABSENT from the registry. Unregistered = unmonitored."""
    owned_needles = (registry.get("ownership") or {}).get("cron_owned_substrings") or []
    matches = [
        str(s.get("cron_match", "")) for s in registry.get("surfaces") or [] if s.get("cron_match")
    ]
    out: dict[str, Any] = {}

    if not cron_inst.ok:
        out["cron"] = {"instrument_fault": cron_inst.fault, "owned": [], "foreign_count": None}
    else:
        owned, foreign = [], 0
        for line in cron_lines:
            if any(n in line for n in owned_needles):
                if not any(m and m in line for m in matches):
                    owned.append(" ".join(line.split())[:160])
            else:
                foreign += 1
        out["cron"] = {
            "instrument_fault": "",
            "owned": sorted(set(owned)),
            "foreign_count": foreign,
            "total": len(cron_lines),
        }

    hook_inst, commands = box.hooks()
    if not hook_inst.ok:
        out["hooks"] = {"instrument_fault": hook_inst.fault, "unregistered": []}
    else:
        needles = [
            str((s.get("evidence") or {}).get("command_contains", ""))
            for s in registry.get("surfaces") or []
            if (s.get("evidence") or {}).get("type") == "hook"
        ]
        unreg = sorted({c[:160] for c in commands if not any(n and n in c for n in needles)})
        out["hooks"] = {"instrument_fault": "", "unregistered": unreg, "total": len(commands)}

    return out


# -------------------------------------------------------------------- PROOF 2: vacuity

# A gate check registered in final_gate.py: run_optional_check("scripts/enforcement/x.py", ...)
_REGISTERED = re.compile(r'run_optional_check\(\s*"(scripts/enforcement/[a-z_0-9]+\.py)"')

# Canaries — a deliberately-bad fixture per check, and the invocation form that reaches it.
#   form "root":   the `_check_runner` script contract — `<script> --root <fixture>`, cwd=fixture
#   form "module": the same runner in module form — `python -m scripts.enforcement.X --root ...`
#                  from the repo root (relative-import checks crash any other way)
#   form "gitcwd": a throwaway git repo (the diff-scoped checks read `git ls-files --others`)
#   "strict": the check reports this class at WARN level, so `--strict` — its documented
#             activation switch — is what turns the finding into a non-zero exit.
# The compose/env fixtures are the ones tests/test_check_activation_anti_vacuity.py already
# proved RED; reused rather than reinvented so the two agree by construction.
CANARIES: dict[str, dict[str, Any]] = {
    "check_docker": {
        "form": "root",
        "files": {
            "compose.yaml": "services:\n  app:\n    platform: linux/arm64\n    build:\n      context: .\n"
        },
        "expect": "platform: linux/arm64 shipped to an x86_64 VPS",
    },
    "check_env_contract": {
        "form": "module",
        "files": {
            ".env.example": "API_KEY=\n",
            "compose.yaml": "services:\n  app:\n    environment:\n      - PW=${POSTGRES_PASSWORD}\n",
        },
        "expect": "a compose-required var missing from .env.example",
    },
    "check_ports": {
        "form": "root",
        "strict": True,
        "files": {"app.py": "PORT = 9999\n"},
        "expect": "a service port neither in PORTS.md nor in the Python range",
    },
    "check_deps_sync": {
        "form": "module",
        "strict": True,
        "files": {
            "requirements.txt": "httpx==0.27.0\n",
            "pyproject.toml": '[project]\nname = "x"\nversion = "0.1"\ndependencies = ["requests"]\n',
        },
        "expect": "requirements.txt and pyproject.toml declaring different packages",
    },
    "check_watchdog": {
        "form": "root",
        "strict": True,
        "files": {"compose.yaml": "services:\n  app:\n    image: python:3.12\n"},
        "expect": "a composed service with no watchdog script",
    },
    "check_health": {
        "form": "root",
        "strict": True,
        "files": {"api.py": '@app.get("/health")\nasync def health():\n    return {"status": "ok"}\n'},
        "expect": "a /health endpoint that pings no dependency",
    },
    "check_secrets": {
        "form": "gitcwd",
        # noqa - AWS's own published documentation key, and the POINT of the fixture: it is
        # written into a throwaway git repo so `check_secrets` can be proven able to fail.
        # `check_secrets` flagging this very line is the check working correctly on itself.
        "files": {"leak.py": 'AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLEKEYXX"\n'},  # noqa
        "expect": "a hardcoded secret in the diff",
    },
}


def discover_registered_checks(gate: Path) -> tuple[Instrument, list[str]]:
    """Which checks final_gate.py actually registers, read from its source."""
    name = "final_gate registry parse"
    if not gate.is_file():
        return Instrument.broken(name, f"no final_gate.py at {gate}"), []
    names = sorted({Path(p).stem for p in _REGISTERED.findall(read_text(gate))})
    if len(names) < 5:
        # The parser, not the gate, is the likely fault: refuse to call anything inert.
        return (
            Instrument.broken(name, f"only {len(names)} registered check(s) parsed out of final_gate.py"),
            names,
        )
    return Instrument.proven(name), names


def _materialise(files: dict[str, str], root: Path) -> None:
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def run_canary(name: str, canary: dict[str, Any], repo_root: Path) -> tuple[Instrument, bool]:
    """Run a check against a deliberately-bad fixture. True == it went red (it CAN fail).

    Control first: the same check on a CLEAN tree must exit 0 without a traceback. If the
    invocation itself is broken we have measured our harness, not the check -- UNKNOWN.
    """
    script = repo_root / "scripts" / "enforcement" / f"{name}.py"
    inst_name = f"canary[{name}]"
    if not script.is_file():
        return Instrument.broken(inst_name, f"no such check script: {script}"), False
    form = str(canary.get("form", "root"))
    strict = bool(canary.get("strict"))

    def invoke(fixture: Path) -> subprocess.CompletedProcess[str] | None:
        argv, cwd = _argv(name, form, script, fixture, repo_root, strict)
        return _run(argv, cwd=cwd)

    with tempfile.TemporaryDirectory() as td:
        clean = Path(td) / "clean"
        clean.mkdir()
        if form == "gitcwd" and _run(["git", "init", "-q", str(clean)]) is None:
            return Instrument.broken(inst_name, "git is unavailable for a diff-scoped canary"), False
        control = invoke(clean)
        if control is None:
            return Instrument.broken(inst_name, "the check could not be executed at all"), False
        blob = control.stdout + control.stderr
        if "Traceback (most recent call last)" in blob:
            return (
                Instrument.broken(inst_name, f"the check crashed on a clean tree: {blob.strip()[:180]}"),
                False,
            )
        if control.returncode != 0:
            return (
                Instrument.broken(
                    inst_name,
                    f"the check exits {control.returncode} on an EMPTY tree, so a red canary "
                    "would prove nothing",
                ),
                False,
            )

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad"
        bad.mkdir()
        if form == "gitcwd" and _run(["git", "init", "-q", str(bad)]) is None:
            return Instrument.broken(inst_name, "git is unavailable for a diff-scoped canary"), False
        _materialise(canary.get("files") or {}, bad)
        red = invoke(bad)
        if red is None:
            return Instrument.broken(inst_name, "the check could not be executed on the canary"), False
        if "Traceback (most recent call last)" in (red.stdout + red.stderr):
            return Instrument.broken(inst_name, "the check crashed on the canary fixture"), False
    return Instrument.proven(inst_name), red.returncode != 0


def _argv(
    name: str, form: str, script: Path, fixture: Path, repo_root: Path, strict: bool
) -> tuple[list[str], Path]:
    """The invocation form that actually reaches the check, and the cwd it needs."""
    if form == "module":
        argv = [sys.executable, "-m", f"scripts.enforcement.{name}", "--root", str(fixture)]
        cwd = repo_root
    elif form == "gitcwd":
        argv, cwd = [sys.executable, str(script)], fixture
    else:
        argv, cwd = [sys.executable, str(script), "--root", str(fixture)], fixture
    if strict:
        argv.append("--strict")
    return argv, cwd


def proof_vacuity(repo_root: Path) -> dict[str, Any]:
    """Can it fail? A check that stays green on its own canary asserts nothing."""
    inst, names = discover_registered_checks(repo_root / "scripts" / "final_gate.py")
    findings: list[Finding] = []
    wired = set(names)
    # The deliberately-UNWIRED diagnostics are audited too: a hand-runnable check that
    # silently exits 0 is the same trap wearing a different hat.
    for name in sorted(wired | set(CANARIES)):
        kind = "check" if name in wired else "check(unwired)"
        canary = CANARIES.get(name)
        if canary is None:
            findings.append(
                finding(
                    proof="vacuity",
                    id=name,
                    kind=kind,
                    instrument=Instrument.broken(
                        f"canary[{name}]",
                        "no canary authored — this check is UNPROVEN, which is neither green "
                        "nor red",
                    ),
                    verdict=Verdict.UNKNOWN,
                    detail="registered in final_gate.py, never proven able to fail",
                )
            )
            continue
        cinst, went_red = run_canary(name, canary, repo_root)
        how = " under --strict" if canary.get("strict") else ""
        findings.append(
            finding(
                proof="vacuity",
                id=name,
                kind=kind,
                instrument=cinst if inst.ok else inst,
                verdict=Verdict.LIVE if went_red else Verdict.DEAD,
                detail=(
                    f"canary went RED{how} on {canary['expect']}"
                    if went_red
                    else f"canary stayed GREEN{how} on {canary['expect']} — the check asserts nothing"
                ),
                reason_class="inert",
            )
        )
    return {
        "findings": [f.as_dict() for f in findings],
        "registered": len(names),
        "registry_instrument_fault": inst.fault,
        "summary": _tally(findings),
    }


# ----------------------------------------------------------------- PROOF 3: doc claims

_FENCE = re.compile(r"^\s*```")
_LOOPBACK_PORT = re.compile(r"(?:localhost|127\.0\.0\.1):(\d{2,5})\b")
_UNIT_TOKEN = re.compile(r"`([A-Za-z0-9_.@-]+\.service)`")
# "calendar-orchestration (Sun 02:00)". The token must carry a separator (-, _, ., /) so
# prose words never become claims: "the weekly cron line (Sun 02:00, ...)" used to be read
# as a scheduled job called "line".
_SCHEDULED_NAME = re.compile(
    r"`?([A-Za-z][\w./-]*[-_./][\w./-]*)`?\s*"
    r"\((Sun|Mon|Tue|Wed|Thu|Fri|Sat|daily|weekly|hourly|nightly)[^)]*\)"
)
_HOOK_TOKEN = re.compile(r"`([A-Za-z0-9_.-]+\.(?:sh|js|py))`")
# A fenced block introduced as a PROPOSAL is not a claim about the live box. Docs
# legitimately show a line to install; reporting one as stale would train the reader to
# ignore this proof. (This file's own docs/workstation/liveness.md prints such a block.)
_PROPOSAL = ("not installed", "proposed", "propose", "example", "would be", "suggested", "to install")
# The state words a doc uses about a unit. Presence of ANY of these makes the doc explicit;
# absence means the doc is merely listing the unit, which reads as "this thing runs".
_STATE_WORDS = (
    "enabled", "disabled", "active", "inactive", "failed", "masked", "static", "removed", "retired",
)
# A unit that no longer exists satisfies a doc that says it is off or gone. "not-found" is
# not a doc defect when the doc's own words are "removed dead <unit>".
_ABSENT_OK = {"disabled", "inactive", "masked", "removed", "retired"}


@dataclass
class Claim:
    doc: str
    line: int
    ctype: str
    text: str
    payload: str
    extra: str = ""


def extract_claims(path: Path, rel: str) -> list[Claim]:
    """Machine-checkable claims only. Anything ambiguous is deliberately NOT a claim."""
    claims: list[Claim] = []
    lines = read_text(path).splitlines()
    in_fence = False
    seen: set[tuple[str, str]] = set()

    def add(ctype: str, payload: str, i: int, text: str, extra: str = "") -> None:
        if (ctype, payload) in seen:
            return
        seen.add((ctype, payload))
        claims.append(Claim(doc=rel, line=i + 1, ctype=ctype, text=text.strip()[:200], payload=payload, extra=extra))

    proposal_block = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            if not in_fence:
                lead = " ".join(lines[max(0, i - 3) : i]).lower()
                proposal_block = any(m in lead for m in _PROPOSAL)
            in_fence = not in_fence
            continue
        window = line + " " + (lines[i + 1] if i + 1 < len(lines) else "")
        if in_fence:
            if CRON_LINE.match(line.strip()) and not proposal_block:
                add("cron_line", " ".join(line.split()), i, line)
            continue
        for port in _LOOPBACK_PORT.findall(line):
            if 1024 <= int(port) <= 65535:
                add("port", port, i, line)
        for unit in _UNIT_TOKEN.findall(line):
            said = ",".join(w for w in _STATE_WORDS if w in window.lower())
            add("unit", unit, i, line, extra=said)
        for token, _when in _SCHEDULED_NAME.findall(line):
            add("scheduled_name", token, i, line)
        if "hook" in line.lower():
            for tok in _HOOK_TOKEN.findall(line):
                add("hook_file", tok, i, line)
    return claims


def _find_script(box: Box, basename: str) -> str:
    """Bounded lookup for a script by basename. Never a whole-disk walk."""
    roots = [
        box.home / ".claude" / "bin",
        box.home / ".claude" / "hooks",
        box.home / ".claude",
        REPO_ROOT / ".claude" / "hooks",
        REPO_ROOT / "scripts",
        REPO_ROOT / "scripts" / "sysadmin",
        REPO_ROOT / "scripts" / "enforcement",
        REPO_ROOT,
    ]
    for root in roots:
        candidate = root / basename
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ""


def _cron_command(entry: str) -> str:
    parts = entry.split()
    if not parts:
        return ""
    n = 1 if parts[0].startswith("@") else 5
    return " ".join(parts[n:])


def verify_claim(box: Box, claim: Claim, cron_inst: Instrument, cron_lines: list[str]) -> Finding:
    make = lambda inst, verdict, detail, rc="": finding(  # noqa: E731 - local partial
        proof="doc_claim", id=f"{claim.doc}:{claim.line}", kind=claim.ctype, instrument=inst,
        verdict=verdict, detail=detail, reason_class=rc, doc=claim.doc,
    )

    if claim.ctype in ("cron_line", "scheduled_name"):
        if not cron_inst.ok:
            return make(cron_inst, Verdict.UNKNOWN, f"cannot read the crontab to check {claim.payload!r}")
        normalised = [" ".join(c.split()) for c in cron_lines]
        if claim.ctype == "cron_line":
            if claim.payload in normalised:
                return make(cron_inst, Verdict.LIVE, "quoted cron line is installed verbatim")
            want = _cron_command(claim.payload)
            drifted = [c for c in normalised if want and _cron_command(c) == want]
            if drifted:
                return make(
                    cron_inst, Verdict.DEAD,
                    f"schedule drift — doc says {claim.payload.split()[0]}, box says {drifted[0].split()[0]}",
                    "stale-doc",
                )
            return make(cron_inst, Verdict.DEAD, "no active crontab line runs this", "stale-doc")
        segments = [s for s in re.split(r"[/]", claim.payload) if len(s) >= 4]
        if any(any(seg in c for c in normalised) for seg in segments or [claim.payload]):
            return make(cron_inst, Verdict.LIVE, f"an active crontab line runs {claim.payload!r}")
        return make(
            cron_inst, Verdict.DEAD,
            f"the doc schedules {claim.payload!r} but no active crontab line mentions it",
            "stale-doc",
        )

    if claim.ctype == "port":
        inst, listening = box.ports()
        if not inst.ok:
            return make(inst, Verdict.UNKNOWN, f"cannot enumerate sockets to check port {claim.payload}")
        if int(claim.payload) in listening:
            return make(inst, Verdict.LIVE, f"port {claim.payload} is listening as documented")
        return make(inst, Verdict.DEAD, f"doc claims localhost:{claim.payload}; nothing is listening", "stale-doc")

    if claim.ctype == "unit":
        inst, state = box.unit_state(claim.payload)
        if not inst.ok or state is None:
            return make(inst, Verdict.UNKNOWN, f"cannot read the state of {claim.payload}")
        enabled, active = state
        said = [w for w in claim.extra.split(",") if w]
        if said:
            # The doc named states explicitly. It is TRUE if any named state is one the box
            # actually reports. MCP_HTTP_TRANSPORT.md says two units are `enabled` and lose
            # the port race, ending `failed`/`inactive` — all three words are correct, and a
            # naive "any negative word means disabled" reading called both docs stale.
            ok = any(w in (enabled, active) for w in said)
            if not ok and enabled == "not-found":
                ok = bool(_ABSENT_OK.intersection(said))
            phrase = "/".join(said)
        else:
            ok = enabled in ("enabled", "enabled-runtime", "static", "generated", "indirect", "alias")
            phrase = "a running unit (no state qualified)"
        if ok:
            return make(inst, Verdict.LIVE, f"{claim.payload} is {enabled}/{active}; doc says {phrase}")
        return make(
            inst, Verdict.DEAD, f"{claim.payload} is {enabled}/{active}; doc says {phrase}", "stale-doc"
        )

    if claim.ctype == "hook_file":
        inst, commands = box.hooks()
        if not inst.ok:
            return make(inst, Verdict.UNKNOWN, f"cannot read hook configuration for {claim.payload}")
        if any(claim.payload in c for c in commands):
            return make(inst, Verdict.LIVE, f"{claim.payload} is wired as a hook command")
        # This oracle reads ONE of the four hook layers (settings.json). Git hooks, the
        # .bashrc chain and project configs are hooks too, so a file that EXISTS but is not
        # in settings.json is beyond this instrument — UNKNOWN, not a stale doc.
        where = _find_script(box, claim.payload)
        if where:
            return make(
                Instrument.broken(
                    "claude settings hooks",
                    f"this audit reads only the settings.json hook layer; {claim.payload} "
                    f"exists at {where} and may be wired by git hooks, the .bashrc chain, "
                    "or a project config",
                ),
                Verdict.UNKNOWN,
                f"doc names {claim.payload} near a hook",
            )
        return make(
            inst, Verdict.DEAD, f"doc names {claim.payload}; no hook runs it and no such file exists",
            "stale-doc",
        )

    return make(
        Instrument.broken("claim-parser", f"unhandled claim type {claim.ctype!r}"),
        Verdict.UNKNOWN, "claim extracted but not verifiable",
    )


def proof_doc_claims(box: Box, docs_dir: Path) -> dict[str, Any]:
    """Is the doc true? Every workstation doc, enumerated -- a truncated listing already
    produced a false n=12 where the real count is 19."""
    if not docs_dir.is_dir():
        broken = Instrument.broken("docs-enumeration", f"no docs directory at {docs_dir}")
        f = finding(
            proof="doc_claim", id="(docs)", kind="enumeration", instrument=broken,
            verdict=Verdict.DEAD, detail="nothing to check",
        )
        return {"findings": [f.as_dict()], "docs": 0, "claims": 0, "summary": _tally([f])}

    docs = sorted(docs_dir.glob("*.md"))
    cron_inst, cron_lines = box.crontab()
    findings: list[Finding] = []
    claims = 0
    for path in docs:
        for claim in extract_claims(path, str(path.relative_to(docs_dir.parents[1]))):
            claims += 1
            findings.append(verify_claim(box, claim, cron_inst, cron_lines))
    return {
        "findings": [f.as_dict() for f in findings],
        "docs": len(docs),
        "doc_names": [p.name for p in docs],
        "claims": claims,
        "summary": _tally(findings),
    }


# ------------------------------------------------------------------------------ report


def _tally(findings: list[Finding]) -> dict[str, int]:
    out = {v.value: 0 for v in Verdict}
    for f in findings:
        out[f.verdict.value] += 1
    return out


@dataclass
class Report:
    generated: str
    repo_root: str
    registry: str
    proofs: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        total = {v.value: 0 for v in Verdict}
        for block in self.proofs.values():
            for k, n in (block.get("summary") or {}).items():
                total[k] = total.get(k, 0) + n
        return total

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated": self.generated,
            "repo_root": self.repo_root,
            "registry": self.registry,
            "summary": self.summary(),
            "proofs": self.proofs,
            "proposed_cron": PROPOSED_CRON,
        }

    def failures(self) -> int:
        return sum(
            1
            for block in self.proofs.values()
            for f in block.get("findings", [])
            if f["verdict"] == Verdict.DEAD.value
        )

    def crashed(self) -> int:
        """Proofs that raised. They report UNKNOWN (they proved nothing), but `--strict`
        must still bite: a silently skipped proof is how a monitor learns to say all-clear."""
        return sum(
            1
            for block in self.proofs.values()
            for f in block.get("findings", [])
            if f["kind"] == "proof"
        )


def audit(repo_root: Path, registry_path: Path, proofs: set[str], box: Box | None = None) -> Report:
    """Run the requested proofs. NEVER raises: a crashed proof is itself an UNKNOWN."""
    box = box or Box()
    report = Report(
        generated=dt.datetime.now().isoformat(timespec="seconds"),
        repo_root=str(repo_root),
        registry=str(registry_path),
    )
    registry, fault = load_registry(registry_path)
    jobs = {
        "heartbeat": lambda: proof_heartbeat(box, registry, fault),
        "vacuity": lambda: proof_vacuity(repo_root),
        "doc_claim": lambda: proof_doc_claims(box, repo_root / "docs" / "workstation"),
    }
    for name, job in jobs.items():
        if name not in proofs:
            continue
        try:
            report.proofs[name] = job()
        except Exception as exc:  # a proof that dies reports UNKNOWN, never a false all-clear
            crashed = finding(
                proof=name, id=f"({name})", kind="proof",
                instrument=Instrument.broken(name, f"{type(exc).__name__}: {exc}"),
                verdict=Verdict.DEAD, detail="the proof itself raised; its verdicts are unknown",
            )  # -> UNKNOWN by the three-state rule; `Report.crashed()` is what makes it bite
            report.proofs[name] = {"findings": [crashed.as_dict()], "summary": _tally([crashed])}
    return report


_ICON = {"LIVE": "LIVE   ", "DEAD": "DEAD   ", "UNKNOWN": "UNKNOWN"}


def render(report: Report) -> str:
    out: list[str] = [
        f"LIVENESS AUDIT — {report.generated}   registry: {report.registry}",
        "Three states. UNKNOWN means the INSTRUMENT could not be proven — never read it as DEAD.",
        "",
    ]
    titles = {
        "heartbeat": "PROOF 1 — HEARTBEAT (did it fire?)",
        "vacuity": "PROOF 2 — VACUITY CANARY (can it fail?)",
        "doc_claim": "PROOF 3 — DOC-CLAIM BINDING (is the doc true?)",
    }
    for key, title in titles.items():
        block = report.proofs.get(key)
        if block is None:
            continue
        s = block.get("summary", {})
        out.append(f"{title}   LIVE={s.get('LIVE', 0)} DEAD={s.get('DEAD', 0)} UNKNOWN={s.get('UNKNOWN', 0)}")
        out.append("-" * 100)
        for f in block.get("findings", []):
            tail = f["detail"]
            if f["instrument_fault"]:
                tail = f"{tail} [instrument: {f['instrument_fault']}]"
            rc = f"({f['reason_class']}) " if f["reason_class"] else ""
            out.append(f"  {_ICON[f['verdict']]}  {f['id']:<44.44} {rc}{tail}")
        if key == "heartbeat":
            unreg = block.get("unregistered") or {}
            cron = unreg.get("cron") or {}
            if cron.get("instrument_fault"):
                out.append(f"  UNREGISTERED cron: UNKNOWN [instrument: {cron['instrument_fault']}]")
            else:
                out.append(
                    f"  UNREGISTERED owned cron lines: {len(cron.get('owned', []))}"
                    f"  (of {cron.get('total')} entries; {cron.get('foreign_count')} belong to other repos)"
                )
                for line in cron.get("owned", []):
                    out.append(f"      ! {line}")
            hooks = unreg.get("hooks") or {}
            if hooks.get("instrument_fault"):
                out.append(f"  UNREGISTERED hooks: UNKNOWN [instrument: {hooks['instrument_fault']}]")
            else:
                out.append(f"  UNREGISTERED hook commands: {len(hooks.get('unregistered', []))}")
                for line in hooks.get("unregistered", []):
                    out.append(f"      ! {line}")
        if key == "vacuity":
            out.append(f"  registered checks parsed from final_gate.py: {block.get('registered')}")
        if key == "doc_claim":
            out.append(f"  docs enumerated: {block.get('docs')}   claims extracted: {block.get('claims')}")
        out.append("")
    total = report.summary()
    out.append(
        f"TOTAL  LIVE={total.get('LIVE', 0)}  DEAD={total.get('DEAD', 0)}  "
        f"UNKNOWN={total.get('UNKNOWN', 0)}"
    )
    out.append("")
    out.append("Proposed (NOT installed) — weekly, 5 minutes before kaizen's 06:45 measurement:")
    out.append(f"  {PROPOSED_CRON}")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Prove that this box's scheduled surfaces, gate checks and docs are ALIVE.")
    p.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    p.add_argument("--strict", action="store_true", help="exit 1 when anything is DEAD (opt-in CI mode)")
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    p.add_argument("--registry", type=Path, default=None, help=f"default: <repo-root>/{DEFAULT_REGISTRY}")
    p.add_argument(
        "--proof",
        default="heartbeat,vacuity,doc_claim",
        help="comma-separated subset of heartbeat,vacuity,doc_claim",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    registry = args.registry or (repo_root / DEFAULT_REGISTRY)
    proofs = {p.strip() for p in str(args.proof).split(",") if p.strip()}
    report = audit(repo_root, registry, proofs)
    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return 1 if (args.strict and (report.failures() or report.crashed())) else 0


if __name__ == "__main__":
    raise SystemExit(main())
