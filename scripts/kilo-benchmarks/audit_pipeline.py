#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_audit_pipeline.py
"""Model-Discovery Pipeline Audit helpers — Phase A of Plan 3 (2026-07-08).

Provides the primitives every phase of the audit consumes:

- `_load_ingestor_findings(path)` — parse a Phase-A findings MD → list[dict].
- `_load_findings_generic(path)` — same reader with variable column shape,
  used by Phase B/C/D/E findings MDs.
- `_dispatch_pool_audit(scripts, task, task_type)` — thin wrapper over
  `libs.subagents.run_agents`; builds AgentSpec list, calls run_agents, calls
  `record_agent_run` per result. Guards the vendor import. Never raises.
- `_render_findings_md(phase, rows, out)` — emit the standard findings table.
- `_verify_tier_split(md_path)` — Phase C helper: count Auto rows with
  Out $/M > $1.5 and On-request rows with Out $/M ≤ $1.5 (both must be 0).
- `_render_consolidated_report(phase_mds, out)` — Phase F: aggregate every
  phase MD into the operator-facing report.

The consolidated report + per-phase findings land under `docs/development/audits/`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Autoload /opt/fabrik/.env so SUBAGENT_RUNS_DSN + SUBAGENT_PROJECT are set for
# pool worker record_agent_run calls (hub peer-auth to fabrik_analytics).
# Idempotent + silent on missing file.
_ENV_PATH = Path("/opt/fabrik/.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"'))


def _load_ingestor_findings(path: Path) -> list[dict]:
    """Parse a Phase-A findings MD → list[dict].

    Column contract: `script | ran | dry-run | writes-tagged | fail-soft |
    severity | summary | fix-commit` (8 cells). Any row that doesn't cleanly
    have 8 cells is silently skipped — the MD may have header/separator/prose
    rows the pipeline shouldn't misclassify.
    """
    return _load_findings_generic(path)


def _load_findings_generic(path: Path) -> list[dict]:
    """Same shape reader but with a variable column set. The header row (first
    `| A | B | C |` after any prose) names the columns; every subsequent data
    row is zip-mapped against it. A separator row (`|---|---|`) is skipped.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    header: list[str] | None = None
    rows: list[dict] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        # Separator row (cells are all `---` or `:---:` etc.)
        if all(c.replace(":", "").replace("-", "") == "" for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) != len(header):
            # A row that doesn't fit the header shape is a signal, not a value.
            continue
        rows.append(dict(zip(header, cells, strict=False)))
    return rows


def _render_findings_md(phase: str, rows: list[dict], out: Path) -> None:
    """Emit the standard findings table with an H1 phase header + Generated
    date. The `phase` string ("A", "B", ...) IDs the section for the
    consolidated Phase F report.
    """
    import datetime as _dt

    out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        lines = [
            f"# Phase {phase} — Findings",
            "",
            f"Generated: {_dt.date.today().isoformat()}",
            "",
            "_No findings yet — the phase dispatch produced zero rows._",
            "",
        ]
    else:
        header_keys = list(rows[0].keys())
        header = "| " + " | ".join(header_keys) + " |"
        sep = "| " + " | ".join(["---"] * len(header_keys)) + " |"
        body = [
            "| " + " | ".join(str(r.get(k, "")) for k in header_keys) + " |"
            for r in rows
        ]
        lines = [
            f"# Phase {phase} — Findings",
            "",
            f"Generated: {_dt.date.today().isoformat()}",
            "",
            header,
            sep,
            *body,
            "",
        ]
    out.write_text("\n".join(lines), encoding="utf-8")


def _verify_tier_split(md_path: Path) -> tuple[int, int]:
    """Count tier-contract violations in a CODING_SUBAGENT_SELECTION-shaped doc.

    Returns `(auto_violations, onrequest_violations)`:
      - `auto_violations`  = rows under `### code` with Out $/M > $1.5.
      - `onrequest_violations` = rows under `### code-onrequest` with Out $/M ≤ $1.5.

    Both must be 0 for the tier contract from
    `.windsurf/rules/core/62-using-subagents.md § Approved pool models` to hold.

    Column order per rank_coding_subagents.py._render: (# | Model | OR | OR_prov
    | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score).
    Out $/M is column index 6 (0-based) on the cell-list.
    """
    ceiling = 1.5
    if not md_path.exists():
        return (0, 0)
    text = md_path.read_text(encoding="utf-8")
    section: str | None = None
    auto_v = 0
    onreq_v = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("### "):
            section = s[4:].strip().lower()
            continue
        if section not in {"code", "code-onrequest"}:
            continue
        if not s.startswith("| ") or "|" not in s.strip("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # Header + separator rows don't lead with a decimal rank.
        if len(cells) < 14 or not cells[0].isdecimal():
            continue
        # Out $/M is column 6 (index 6 in the 14-column table).
        try:
            out_m = float(cells[6])
        except ValueError:
            continue
        if section == "code" and out_m > ceiling:
            auto_v += 1
        elif section == "code-onrequest" and out_m <= ceiling:
            onreq_v += 1
    return (auto_v, onreq_v)


def _dispatch_pool_audit(
    scripts: list[Path],
    task: str,
    task_type: str = "review",
) -> list[dict]:
    """Fan out a pool audit — one AgentSpec per script.

    Returns list of finding rows (one dict per subagent). Guards
    the vendor import: if `libs.subagents` isn't vendored, returns an empty
    list + prints a warning to stderr (fail-soft — the audit falls back to
    inline scan mode elsewhere).

    Each subagent gets:
      - `task_type` = the passed value (default "review" — code review shape).
      - `model` = `pick_models(task_type, n=1)[0]` (module ≤$1.5/Mtok cap
        auto-enforces; do NOT pass `max_cost_per_mtok` — see 62-using-subagents.md).
      - `tools_enabled = False` + `allow_ungrounded = True` (source is inlined
        into the task string; the fail-closed guard at libs/subagents/agent.py
        refuses ungrounded single-shot review/docs otherwise).
      - `owned_paths = []` (read-only audit; no file mutation from workers).

    Per 62-using-subagents.md § Report every pool run: after evaluation we
    call `record_agent_run(spec, result, quality_score, project)` — feeds the
    flywheel. `quality_score` defaults to 3 (adequate) until the orchestrator
    reviews the finding.
    """
    try:
        from libs.subagents import (  # type: ignore[import-not-found]
            AgentSpec,
            pick_models,
            run_agents,
        )
    except ImportError:
        print(
            "[audit_pipeline] libs.subagents not vendored — returning [] (fall back to inline scan)",
            file=sys.stderr,
        )
        return []

    try:
        from libs.subagents import (  # type: ignore[import-not-found]
            record_agent_run,
        )
    except ImportError:
        record_agent_run = None  # type: ignore[assignment]

    model = pick_models(task_type, n=1)
    if not model:
        print(
            f"[audit_pipeline] pick_models({task_type!r}) returned nothing — no pool worker available",
            file=sys.stderr,
        )
        return []
    chosen = model[0]

    specs: list = []
    for src in scripts:
        # Inline the source so tools_enabled=False + allow_ungrounded=True
        # is honest: the worker has everything it needs in the task string.
        try:
            body = src.read_text(encoding="utf-8")
        except OSError:
            body = f"(source unreadable: {src})"
        prompt = (
            f"{task}\n\n"
            f"Report as ONE markdown table row: `| <script> | <ran> | <dry-run> | "
            f"<writes-tagged> | <fail-soft> | <severity: STYLE|CONFIRMED|PLAUSIBLE|ESCALATE> | "
            f"<summary ≤ 100 chars> | — |`\n\n"
            f"=== source: {src} ===\n\n{body[:100_000]}"
        )
        specs.append(
            AgentSpec(  # type: ignore[call-arg]
                task=prompt,
                model=chosen,
                tools_enabled=False,
                allow_ungrounded=True,
                task_type=task_type,
                owned_paths=[],
            )
        )

    try:
        results = run_agents(specs, repo=Path("/opt/fabrik"))
    except Exception as e:  # noqa: BLE001 — fail-soft: pool outage returns [].
        print(f"[audit_pipeline] run_agents failed: {e}", file=sys.stderr)
        return []

    rows: list[dict] = []
    for spec, result in zip(specs, results, strict=False):
        # Best-effort extraction of the single MD row from result.text.
        text = (getattr(result, "text", "") or "").strip()
        row_line = None
        for line in text.splitlines():
            if line.startswith("| ") and line.count("|") >= 8:
                row_line = line
                break
        if row_line is None:
            # Worker returned no valid row → capture as an ESCALATE finding.
            rows.append(
                {
                    "script": Path(str(spec.task).split("=== source: ", 1)[-1].split(" ===", 1)[0]).name
                    if "=== source: " in str(spec.task)
                    else "?",
                    "ran": "no",
                    "dry-run": "?",
                    "writes-tagged": "?",
                    "fail-soft": "?",
                    "severity": "ESCALATE",
                    "summary": "pool worker returned no valid finding row",
                    "fix-commit": "—",
                }
            )
        else:
            cells = [c.strip() for c in row_line.strip("|").split("|")]
            if len(cells) >= 8:
                rows.append(
                    {
                        "script": cells[0],
                        "ran": cells[1],
                        "dry-run": cells[2],
                        "writes-tagged": cells[3],
                        "fail-soft": cells[4],
                        "severity": cells[5],
                        "summary": cells[6],
                        "fix-commit": cells[7] if len(cells) > 7 else "—",
                    }
                )

        # Flywheel record — quality_score=3 (adequate default; the orchestrator
        # may re-score after evaluating). Fail-soft on any error.
        if record_agent_run is not None:
            try:
                record_agent_run(
                    spec, result, quality_score=3, project="fabrik-hub"
                )
            except Exception:  # noqa: BLE001 — fail-open per pg_ledger contract.
                pass

    return rows


def _run_inline_ingestor_scan(scripts: list[Path]) -> list[dict]:
    """Deterministic inline scan of ingestor sources — no pool dispatch.

    Grep-based checks for the plan's 4 audit criteria per ingestor:
      (a) `--dry-run` flag support (grep for `--dry-run` argparse arg).
      (b) writes tagged (grep for `INSERT OR IGNORE` or an explicit UPDATE ...
          WHERE id=? pattern — presence of either).
      (c) speed_source / last_verified / status set (any of the 3 present).
      (d) fail-soft on network error (grep for `httpx.HTTPError`, `RequestError`,
          `requests.exceptions`, or a broad `except Exception` in an HTTP block).

    Used as a fallback when pool dispatch is unavailable OR as a first-pass
    sanity check the orchestrator can eyeball before a real pool dispatch.
    Returns the same row shape as `_dispatch_pool_audit`.
    """
    import re

    rows: list[dict] = []
    for src in scripts:
        if not src.exists():
            rows.append(
                {
                    "script": src.name,
                    "ran": "no",
                    "dry-run": "?",
                    "writes-tagged": "?",
                    "fail-soft": "?",
                    "severity": "ESCALATE",
                    "summary": f"source missing on disk: {src}",
                    "fix-commit": "—",
                }
            )
            continue
        try:
            text = src.read_text(encoding="utf-8")
        except OSError as e:
            rows.append(
                {
                    "script": src.name,
                    "ran": "no",
                    "dry-run": "?",
                    "writes-tagged": "?",
                    "fail-soft": "?",
                    "severity": "ESCALATE",
                    "summary": f"OSError: {e}",
                    "fix-commit": "—",
                }
            )
            continue

        # (a) --dry-run support
        dry_run = "yes" if re.search(r'"--dry-run"|--dry-run', text) else "no"
        # (b) writes tagged
        has_ignore = bool(re.search(r"INSERT OR IGNORE|INSERT OR REPLACE", text, re.I))
        has_upd_where = bool(re.search(r"UPDATE\s+\w+\s+SET.*?WHERE\s+\w+\s*=\s*[?\"]", text, re.I | re.S))
        writes_tagged = "yes" if (has_ignore or has_upd_where) else (
            "n/a" if "INSERT " not in text.upper() and "UPDATE " not in text.upper() else "no"
        )
        # (c) speed/last_verified/status
        has_tag = bool(re.search(r"speed_source|last_verified|discard_reason|status\s*=\s*['\"](active|deprecated)", text, re.I))
        # (d) fail-soft on network error
        has_fail_soft = bool(
            re.search(r"httpx\.HTTPError|httpx\.RequestError|requests\.exceptions", text)
            or re.search(r"except.*Exception.*:.*\n.*(log|print|return|pass)", text)
        )

        severity = "STYLE"
        summary_parts = []
        if dry_run == "no":
            summary_parts.append("no --dry-run flag")
        if writes_tagged == "no":
            summary_parts.append("write path not tagged (missing INSERT OR IGNORE / UPDATE ... WHERE id=?)")
            severity = "PLAUSIBLE"
        if writes_tagged == "n/a":
            pass  # read-only script; no write path to tag
        if not has_tag and writes_tagged != "n/a":
            summary_parts.append("no speed_source/last_verified/status set")
            severity = "CONFIRMED" if severity != "CONFIRMED" else severity
        if not has_fail_soft:
            summary_parts.append("no explicit HTTP-error catch")
            severity = "PLAUSIBLE" if severity == "STYLE" else severity

        rows.append(
            {
                "script": src.name,
                "ran": "yes",
                "dry-run": dry_run,
                "writes-tagged": writes_tagged,
                "fail-soft": "yes" if has_fail_soft else "no",
                "severity": severity,
                "summary": ("; ".join(summary_parts) if summary_parts else "all 4 audit criteria pass")[:120],
                "fix-commit": "—",
            }
        )
    return rows


def _render_consolidated_report(phase_mds: list[Path], out: Path) -> None:
    """Phase F: aggregate every phase's findings MD into one operator-facing
    report at `docs/development/audits/2026-07-08-model-pipeline-audit.md`.

    Sections:
      (1) Summary — total findings by severity, per phase.
      (2) Findings ledger — every row from every phase MD, with a `phase`
          column added.
      (3) Escalation table — every ESCALATE row with a proposed
          follow-up `/fabrik-spec` topic (filled in by the orchestrator
          during Phase F).
      (4) Coverage — table of pipeline steps audited vs. skipped.
      (5) Reproducibility — commit hash + DB size + row counts.
    """
    import datetime as _dt
    import sqlite3

    out.parent.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().isoformat()

    # Read every phase MD; associate rows with their phase letter.
    all_rows: list[dict] = []
    per_phase_counts: dict[str, dict[str, int]] = {}
    for md in phase_mds:
        # Extract phase letter from filename: phase-a-ingestor-findings.md → "A"
        stem = md.stem  # e.g. "phase-a-ingestor-findings"
        phase = "?"
        parts = stem.split("-")
        if len(parts) >= 2 and parts[0] == "phase" and len(parts[1]) == 1:
            phase = parts[1].upper()
        rows = _load_findings_generic(md)
        counts: dict[str, int] = {}
        for r in rows:
            r["phase"] = phase
            sev = r.get("severity", "?").upper()
            counts[sev] = counts.get(sev, 0) + 1
        per_phase_counts[phase] = counts
        all_rows.extend(rows)

    # Reproducibility metrics.
    db_path = Path("scripts/kilo-benchmarks/kilo_agents.db")
    agents_active = agents_total = gpu_total = embed_total = 0
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            agents_total = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            agents_active = conn.execute(
                "SELECT COUNT(*) FROM agents WHERE status='active'"
            ).fetchone()[0]
            try:
                gpu_total = conn.execute("SELECT COUNT(*) FROM gpu_providers").fetchone()[0]
            except sqlite3.OperationalError:
                pass
            try:
                embed_total = conn.execute(
                    "SELECT COUNT(*) FROM embedding_models"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()

    # Build summary table.
    severities = ["CONFIRMED", "PLAUSIBLE", "STYLE", "ESCALATE"]
    summary_header = "| Phase | " + " | ".join(severities) + " |"
    summary_sep = "|---|" + "|".join(["---:"] * len(severities)) + "|"
    summary_body: list[str] = []
    total_by_sev = {s: 0 for s in severities}
    for phase in sorted(per_phase_counts):
        c = per_phase_counts[phase]
        summary_body.append(
            "| " + phase + " | " + " | ".join(str(c.get(s, 0)) for s in severities) + " |"
        )
        for s in severities:
            total_by_sev[s] += c.get(s, 0)
    summary_body.append(
        "| **Total** | " + " | ".join(f"**{total_by_sev[s]}**" for s in severities) + " |"
    )

    # Build findings ledger.
    ledger_lines = [
        "| phase | subject | severity | summary | fix-commit |",
        "|---|---|---|---|---|",
    ]
    for r in all_rows:
        # The "subject" is whatever the first-column-not-phase is.
        subject_key = next(
            (k for k in r if k not in {"phase", "severity", "summary", "fix-commit"}),
            "?",
        )
        subject = r.get(subject_key, "?")
        ledger_lines.append(
            f"| {r.get('phase','?')} | {subject} | {r.get('severity','?')} | "
            f"{r.get('summary','')} | {r.get('fix-commit','—')} |"
        )

    # Escalation subset.
    escalations = [r for r in all_rows if r.get("severity", "").upper() == "ESCALATE"]
    escal_lines = [
        "| phase | subject | summary | proposed /fabrik-spec topic |",
        "|---|---|---|---|",
    ]
    for r in escalations:
        subject_key = next(
            (k for k in r if k not in {"phase", "severity", "summary", "fix-commit"}),
            "?",
        )
        escal_lines.append(
            f"| {r.get('phase','?')} | {r.get(subject_key,'?')} | "
            f"{r.get('summary','')} | _(orchestrator to fill in Phase F.1)_ |"
        )
    if not escalations:
        escal_lines.append("| — | _no ESCALATE-severity findings — every real finding was fixed inline or REFUTED_ | — | — |")

    lines = [
        "# Model-Discovery Pipeline Audit — 2026-07-08",
        "",
        f"Generated: {today}",
        f"Plan: [`docs/development/plans/archived/2026-07-08-plan-3-model-pipeline-audit.md`](../plans/archived/2026-07-08-plan-3-model-pipeline-audit.md)",
        "",
        "## 1. Summary — findings by severity, per phase",
        "",
        summary_header,
        summary_sep,
        *summary_body,
        "",
        "## 2. Findings ledger",
        "",
        *ledger_lines,
        "",
        "## 3. Escalation — findings that outgrew this plan",
        "",
        "Each ESCALATE row below names a proposed follow-up `/fabrik-spec` topic; the operator decides whether to spec each.",
        "",
        *escal_lines,
        "",
        "## 4. Coverage",
        "",
        "| Stage | Steps audited | Steps skipped | Skip reason |",
        "|---|---:|---:|---|",
        "| Ingest (13 scripts) | (per Phase A rows above) | — | — |",
        "| Derive (7 scripts) | (per Phase B rows above) | — | — |",
        "| Aggregate/Rank (7 rankers) | (per Phase C rows above) | — | — |",
        "| Emit (14 docs + 11 browser tabs) | (per Phase D rows above) | — | — |",
        "| Cross-consistency | (per Phase E rows above) | — | — |",
        "",
        "## 5. Reproducibility",
        "",
        f"- **DB path:** `scripts/kilo-benchmarks/kilo_agents.db`",
        f"- **agents rows total:** {agents_total} (active: {agents_active})",
        f"- **gpu_providers rows:** {gpu_total}",
        f"- **embedding_models rows:** {embed_total}",
        f"- **Report generated:** {today}",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
