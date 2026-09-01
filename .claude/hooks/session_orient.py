#!/usr/bin/env python3
# AFTER-EDIT: tests/test_session_orient_hook.py
"""SessionStart orientation (Fabrik-synced, stdlib-only, fail-open).

Every session starts with an explicit orientation block so the agent is AWARE
of what is connected to it before any work: the governing CLAUDE.md (hub
contract in /opt/fabrik, synced template copy in projects — the text branches
on repo identity), the persistent MEMORY.md index, the session-recall MCP
tools, and the enforcement mesh (Stop hook, prompt router, final_gate).
CLAUDE.md and MEMORY.md are harness-auto-loaded — this hook does not re-read
them; it BINDS the agent to act on them and surfaces their state. Fail-open:
any error exits 0 (a broken orientation must never block a session).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
from pathlib import Path

# Read at most this much of MEMORY.md when counting entries (bound reads by
# bytes — a pathological index must not spike every SessionStart).
_MEMORY_READ_BYTES = 256 * 1024

# --- Kaizen M1 event stream (additive sensor, fail-open at the IMPORT layer) ---
# The emitter lives at ONE place per box, so both candidates are tried: this repo's own
# copy first, then the hub's. The degraded state is the module being unimportable at
# BOTH — a box that has no kaizen_events at all — and there the hook must behave
# EXACTLY as it did before the sensor existed. Hence the guarded import (never an
# ImportError reaching a session) and a second guard at every emit site. Paths are
# APPENDED (stdlib always wins) and only when absent (idempotent under re-import).
kaizen_events = None
try:
    for _p in (
        str(Path(__file__).resolve().parents[2] / "scripts" / "sysadmin"),
        "/opt/fabrik/scripts/sysadmin",
    ):
        if _p not in sys.path:
            sys.path.append(_p)
    import kaizen_events  # type: ignore[no-redef]
except Exception:
    kaizen_events = None

# SessionStart's whole budget is 10s (.claude/settings.json). A hung git probe must
# cost this hook milliseconds, not the orientation itself.
_PROBE_TIMEOUT_S = 2.0


@contextlib.contextmanager
def _quiet():
    """Mute stderr for the duration — hook-side, so `kaizen_events` keeps its own
    honest `_warn` channel for every OTHER caller. A hook's stderr is part of its
    observable output, and the sensor must not add a byte to it."""
    try:
        devnull = open(os.devnull, "w")  # noqa: SIM115 - closed in the finally below
    except OSError:  # pragma: no cover - /dev/null is always there
        yield
        return
    try:
        with contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()


def _kaizen(event: str, sid: object, probe_cwd: str | None = None, **fields: object) -> None:
    """Fire-and-forget event. Module absent or ANY failure → silent no-op.

    ``emit`` already swallows everything, but the outermost guard lives HERE so a
    future emitter that does raise still cannot cost a session its orientation.
    ``probe_cwd`` pins exposure to the PAYLOAD's project rather than this process's
    cwd — a hook subprocess has no guarantee the two agree.
    """
    if not kaizen_events:
        return
    try:
        with _quiet():
            exp = kaizen_events.exposure(cwd=probe_cwd, probe_timeout_s=_PROBE_TIMEOUT_S)
            kaizen_events.emit(
                event, kaizen_events.resolve_sid(sid), exposure_override=exp, **fields
            )
    except Exception:
        pass


def _instrumented(cwd: str) -> bool:
    """Does a Stop hook run here? The sensors must instrument ONE universe.

    `final_gate_stop.py` returns early when `scripts/final_gate.py` is absent, so a
    `session_start` emitted outside that universe is a session the collector can never
    see closed — a fabricated hole in exactly the metric this stream exists to measure.
    """
    try:
        return (Path(cwd) / "scripts" / "final_gate.py").exists()
    except OSError:
        return False


def _memory_line(cwd: str) -> str:
    # Harness project-key convention: '/' AND '.' become '-'
    # (ground truth: ~/.claude/projects/-opt-…--rec-…-jpg style keys).
    proj_key = cwd.replace("/", "-").replace(".", "-")
    idx = (
        Path(os.environ.get("HOME", str(Path.home())))
        / ".claude/projects"
        / proj_key
        / "memory/MEMORY.md"
    )
    try:
        if idx.is_file():
            with open(idx, encoding="utf-8", errors="replace") as f:
                head = f.read(_MEMORY_READ_BYTES)
            entries = sum(1 for line in head.splitlines() if line.lstrip().startswith("- "))
            more = "+" if len(head) == _MEMORY_READ_BYTES else ""
            return (
                f"- **Memory:** your MEMORY.md index is loaded ({entries}{more} entries). Recalled"
                " facts in system-reminders are background truth-at-write-time — verify named"
                " files/flags still exist. Save new durable facts per the memory contract; update,"
                " don't duplicate."
            )
    except OSError:
        pass
    return (
        "- **Memory:** no memory index yet for this project — when you learn a durable fact"
        " (operator preference, project constraint, feedback), write it per the memory contract."
    )


def _identity_line(cwd: str) -> str:
    """Hub-only advisory (D-034): an UNNAMED hub session is always a mistake — three
    sessions share this tree and the role hook binds only through CLAUDE_AGENT (a
    window /rename never reaches hooks; a full day was once mis-signed). Project
    repos (no manifest file) and named sessions get nothing."""
    try:
        is_hub = (Path(cwd) / "scripts" / "fabrik_synced_manifest.py").is_file()
        if is_hub and not os.environ.get("CLAUDE_AGENT", "").strip():
            return (
                "- ⚠️ **CLAUDE_AGENT is UNSET — this hub session is UNNAMED.** Three sessions"
                " share this tree; the role charter, beat routing and Agent-Name trailers all"
                " key on the env var (a window rename never reaches hooks — the mis-signed-day"
                " class). Ask the operator which role this window is, or work without beat"
                " claims until named.\n"
            )
    except Exception:
        pass
    return ""


def _mcp_line(cwd: str) -> str:
    """The session's ASSIGNED MCP set + catalog pointer + fix-first duty (operator
    directive 2026-08-30, D-032). Reads the repo's emitted .mcp.json at runtime;
    fail-safe: any problem degrades to the universal-set line, never crashes."""
    assigned = "the universal set (no repo .mcp.json here)"
    try:
        import json as _json

        raw = (Path(cwd) / ".mcp.json").read_text()
        try:
            servers = _json.loads(raw).get("mcpServers", {})
            names = sorted(servers) if isinstance(servers, dict) else []
        except Exception:
            # a BROKEN file is not an ABSENT file — fix-first applies to the config too
            names = []
            assigned = "⚠️ .mcp.json EXISTS but is malformed/unreadable — fix it first (re-run the emitter)"
        if names:
            shown = names[:40]
            assigned = " · ".join(shown) + (f" · (+{len(names) - 40} more)" if len(names) > 40 else "")
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return (
        f"- **Your ASSIGNED MCPs (this repo):** {assigned} — plus the user-level universal set."
        " The FULL catalog + every ruling: `/opt/fabrik/docs/workstation/mcp-roster.md` (box-local,"
        " absolute path works from every repo); need a server this repo lacks? cite the roster row"
        " and ask the operator — never hand-edit `.mcp.json` (hub-emitted; the ruling changes first)."
        " **An MCP that fails to connect is FIXED FIRST, before the task** — known classes: corrupted"
        " `~/.npm/_npx/<hash>` entry → clear that ONE entry, never the whole `_npx`; cold-spawn herd"
        " timeout → reload the window; postgres-pro needs a CONNECTING `DATABASE_URL` in the repo"
        " `.env` (then re-run `python3 /opt/fabrik/scripts/sysadmin/emit_mcp_project_config.py"
        " --repo <this repo>`).\n"
    )


def _governance_line(cwd: str) -> str:
    # Repo identity is CONTENT-based (same discipline as /fabrik-upstream): the
    # hub is wherever the synced-manifest module sits at toplevel — never a
    # hardcoded path.
    if (Path(cwd) / "scripts/fabrik_synced_manifest.py").is_file():
        return (
            "- **Governance (HUB):** this is the platform repo — CLAUDE.md HERE is the hub"
            " agents' own contract: canonical and yours to edit (a synced-surface commit"
            " distributes fleet-wide; the project-facing template lives at"
            " templates/governance/CLAUDE.md). Obey it fully; every task-completing output owes"
            " the RULES ACTIVE line and ends with the 7-line FINAL OUTPUT block (incl."
            " DONE:/NEXT:)."
        )
    return (
        "- **Governance:** this project's CLAUDE.md is already loaded into your context. It is"
        " Fabrik-SYNCED (distributed from the hub's templates/governance/CLAUDE.md) — obey it"
        " fully; NEVER edit the local copy (the next sync overwrites it; changes go upstream via"
        " /fabrik-upstream). Every task-completing output owes the RULES ACTIVE line and ends"
        " with the 7-line FINAL OUTPUT block (incl. DONE:/NEXT:)."
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # C-locale must degrade, not swallow
        # stdin too: a non-ASCII cwd/transcript path under LC_ALL=C would otherwise raise
        # UnicodeDecodeError and silently drop the WHOLE payload (review finding).
        sys.stdin.reconfigure(errors="replace")
    except Exception:
        pass
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}  # [] / "x" / 42 payloads must not swallow the whole block
    cwd = str(data.get("cwd") or os.getcwd())
    # sid lands inside a command the agent is told to RUN — allowlist it to the
    # same class every mesh script sanitizes to ([A-Za-z0-9_-], first 64).
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or ""))[:64]

    # Pane auto-continue (operator directive: always on in interactive sessions):
    # the self-watch is the ONLY pane-safe revival mechanism (the headless
    # reviver against a pane forks a second writer — spec-disqualified), and a
    # Monitor can only be armed BY the agent — so the ORIENT block orders it
    # with the concrete session id. Skipped when: headless (the reviver exports
    # CLAUDE_MESH_HEADLESS=1 — no pane to wake) or source=compact (same process,
    # the already-armed Monitor SURVIVES compaction — proven live 2026-08-09;
    # re-ordering there breeds duplicate watchers).
    arm_line = ""
    if sid and os.environ.get("CLAUDE_MESH_HEADLESS") != "1" \
            and data.get("source") != "compact" \
            and Path(os.environ.get("HOME", str(Path.home()))) \
            .joinpath(".claude/bin/claude-selfwatch.sh").is_file():
        arm_line = (
            "- **ARM YOUR SELF-WATCH NOW (first tool action, operator-mandated):** call "
            f"Monitor(persistent: true, command: \"bash ~/.claude/bin/claude-selfwatch.sh {sid}\","
            " description: \"resume-mesh self-watch\") — it wakes THIS pane automatically when a"
            " turn dies on a healed API error or a lost waker. Zero cost while silent; skip ONLY"
            " if this session already armed it. The Monitor event IS the wake channel — NEVER a"
            " `nohup ... &` Bash arm: its wake line lands in /dev/null and the watch still"
            " consumes the death marker (a wef session revived 13 times became unrevivable the"
            " day it re-armed that way, 2026-08-30). Each watch fires ONCE — RE-ARM the same way"
            " first-thing after every delivered wake.\n"
        )

    # Reboot sweep (plan 2026-08-10-plan-1, Phase D): a launcher that exports
    # CLAUDE_MESH_AUTONOMOUS=1 marks its session as machine-driven work worth resuming
    # after a reboot. INDEPENDENT of the pane arm-gate above — the sweep's whole
    # population is headless runs, so gating the marker on the arm would unmark exactly
    # the sessions it serves. Panes never set the env, so they are structurally excluded.
    if sid and os.environ.get("CLAUDE_MESH_AUTONOMOUS") == "1":
        try:
            # PERSISTENT state dir, never the /tmp lock dir (plan 2026-08-13-plan-1): a VM
            # termination (standby cut, host kill) wipes /tmp and with it every sweep
            # eligibility — the marker must outlive the VM for the @reboot sweep to revive
            # the session. The sweep reads this dir first, legacy lock dir second.
            locks = Path(os.environ.get("MESH_STATE_DIR")
                         or Path(os.environ.get("HOME", str(Path.home())))
                         / ".claude" / "state" / "autonomous")
            locks.mkdir(mode=0o700, parents=True, exist_ok=True)
            # 0600 at CREATE time: the marker carries cwd + transcript path (project
            # names, task slugs) and the default umask would make it world-readable.
            payload = json.dumps({
                "sid": sid,
                "cwd": cwd,
                "transcript_path": str(data.get("transcript_path") or ""),
                "marked_at": int(time.time()),
            })
            fd = os.open(locks / f"{sid}.autonomous",
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(payload)
        except OSError:
            pass  # fail-open: an unmarkable session is un-swept, never a broken start

    print(
        "## ORIENT (binding — read before acting)\n"
        + arm_line
        + _governance_line(cwd)
        + "\n"
        + _memory_line(cwd)
        + "\n"
        + _identity_line(cwd)
        + _mcp_line(cwd)
        + "- **Decision-shaped question? LEDGER FIRST:** grep `docs/DECISIONS.md` (fleet-wide:"
        " `python3 /opt/fabrik/scripts/decisions.py <term>`) BEFORE any wider hunt — a prior ruling,"
        " retirement, or rejected option is a structured row there, and structured beats lexical."
        " A decision made or received this run gets its row in the same change.\n"
        "- **session-recall is CONNECTED:** `search_chats` (keyword) · `recent_chats` (recency) ·"
        " `get_chat` (read one). MANDATORY before answering when resuming work, when the user"
        " references a prior decision not in this conversation (AFTER the ledger), or after"
        " compaction — never claim no previous conversation exists without searching first.\n"
        "- **Enforcement mesh wired to this session:** the Stop hook blocks unfinished exits — SIX"
        " causes: gate red on YOUR files · your work uncommitted · committed-but-UNPUSHED (the"
        " task-end law: push your own work; never --force) · promise/permission stalls · a command"
        " run record still `running` · spontaneous CODE edits with no run record at all (plain-chat"
        " work owes /fabrik-review-scoped — running it creates the record that clears the block); the prompt router suggests the owning /fabrik-* skill;"
        " `python scripts/final_gate.py --json` is the completion gate. Work WITH them — they are"
        " the definition of done, not obstacles.\n"
        "- **Before ANY claim about hooks, the mesh, death/revival or sounds, READ"
        " `/opt/fabrik/docs/workstation/hooks-index.md`** — it is the authority and it is box-local"
        " (absolute path works from every repo). An infra agent stated four false things about this"
        " subsystem in one answer on 2026-08-16 by checking `~/.claude/state/` and the project hook"
        " config and reporting absence as fact; the mesh writes to"
        " `/tmp/claude-sound-locks-$(id -u)/`. Searching one plausible location is not evidence."
    )

    # Kaizen M1 — LAST, deliberately. This hook IS the session's birth certificate, but
    # the ORIENT block above is its actual product: emitting first put the whole block
    # behind a sensor that can be slow or throw. Two guards, both about not lying to the
    # collector: only where a Stop hook also runs (symmetric universe), and only on a
    # real session BIRTH — a resume/compact is the same session continuing, which is why
    # the --baseline path special-cases them too. An ABSENT source is treated as a
    # startup: a harness that stops sending the field must degrade to over-counting, not
    # to a silently dead metric. The RAW payload id is passed, never the flattened `sid`
    # above — flattening is many-to-one, and the emitter's own sanitizer is injective.
    if _instrumented(cwd) and str(data.get("source") or "startup") == "startup":
        _kaizen(
            "session_start",
            data.get("session_id"),
            probe_cwd=cwd,
            cwd=cwd,
            source=str(data.get("source") or ""),
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
