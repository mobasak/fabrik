# T06 — The operator's window runbook: switch, battery, rollback, Gate S, the infra mail

Depends: T02, T03, T04a, T04b
Parallel: ⚡
Complexity: native
Appetite: 120
Gate: python -m pytest tests/test_alloy_runbook.py -q
Docs: docs/operations/promtail-to-alloy-runbook.md (a new dedicated doc; its INDEX.md and docs/README.md rows are orchestrator-applied)

## Scope
Implements spec § The delta › D2, D3 (window half), D6 and § Lifecycle as one operator runbook,
`docs/operations/promtail-to-alloy-runbook.md`, which the operator runs from the `fleet-alloy` branch worktree and
which no agent step executes except the close's merge request and infra mail (5). Sections: (0) preflight — `ss -ltn` for 12345 on each spoke (spec U2; on a clash the
spoke flag and the Prometheus targets take another free port), the long-running canary container, the Alertmanager
silence on `job="promtail-spokes"`, the expected `target_down` noise from `scripts/sysadmin/proactive-check.sh:147-148`;
(1) per host in the order vps3, vps2, vps1 — D2's steps (a) keep `compose.yaml.pre-alloy` and place the new files,
(b) `docker compose stop promtail`, (c) `docker compose up -d alloy`, (d) the battery V4–V8 and V11 with the exact
Grafana/LogQL queries — with the spoke files rendered the way bootstrap step 11 renders them but without running
step 11; (2) before vps1's step (b), the two read-only checks of D3, phrased as PASS CONDITIONS with the action on a
stray line (W-332b562c note 2: the two-dot `git diff master HEAD -- configs/prometheus configs/gatus` shows the
watcher hunks and the README rename and nothing else; each sync script's `--diff` lists only its own file — a DRIFT or
ORPHAN line on any other file means STOP and reconcile master into the branch before pushing); right after vps1's
step (c), the two `--push` runs with `FABRIK_ROOT=<branch worktree>`, then the silence expires; (3) every 15-minute
V4/V5 window is anchored on step (b) explicitly (W-332b562c note 1); (4) rollback per D6 (restore
`compose.yaml.pre-alloy`, `up -d --remove-orphans`) with its duplicate-span note; (5) the close, once all three hosts pass their battery: the operator's one act is to tell the fleet agent the
battery passed; the fleet agent (spec § Personas — the one step of this document an agent runs, and only after that
signal) then sends `fleet-alloy` for merge (`python3 scripts/merge_request.py request --review <the plan's receipt>`
from the branch worktree, then the live message it prints) and sends the appendix's infra mail; (5b) V9 daily and Gate S, and the follow-up cleanup list of D6; (6) an appendix holding the infra mail — the exact edits for the 4 rule packs,
`.windsurf/rules/CLAIMS.yaml`, `agents-fabrik.md`, the six `commands/_sources/` files and
`docs/reference/prebuilt-app-containers.md` — sent once the window passed its battery. A structural grader keeps
the runbook honest. DO-NOT: execute any step, touch any compose or config file.

## Touches
- docs/operations/promtail-to-alloy-runbook.md — PRIMARY PATH
- tests/test_alloy_runbook.py

## Behavior Contract
- **Given** the runbook, **When** its per-host sections are parsed, **Then** they run vps3, vps2, vps1 in that order and each carries steps (a) to (d) with stop before start and no plain `up -d` between them (spec § The delta › D2)
- **Given** the runbook's hub section, **When** it is parsed, **Then** the two D3 read-only checks precede vps1's step (b), each stated as a pass condition with a STOP action on a stray DRIFT or ORPHAN line, and the two `--push` runs follow step (c) with `FABRIK_ROOT` set to the branch worktree (spec § The delta › D3; W-332b562c)
- **Given** the battery, **When** V4, V5 and V6 are read, **Then** each 15-minute window is anchored on step (b) by name, and V6 writes numbered pre-markers 5 to 10 minutes before step (b) and one switch marker between (b) and (c) to the canary (no `--rm`), requiring each marker exactly once in Loki for that host within 2 minutes of (c) (spec § Validation V4, V5, V6; W-332b562c)
- **Given** the rollback section, **When** it is read, **Then** it restores `compose.yaml.pre-alloy` and runs `up -d --remove-orphans`, never a stop-and-start that leaves the new file in place (spec § The delta › D6)
- **Given** the preflight, **When** it is read, **Then** it opens the Alertmanager silence, starts the canary before step (a) and checks port 12345 with `ss -ltn` on each spoke (spec § The delta › D3; § Open / blocking unknowns U2)
- **Given** the Gate S section, **When** it is read, **Then** it names V8 and V9 green on all three hosts for 14 days as the trigger and lists the cleanup: the promtail service, the `promtail-positions` volume (classified before any change), the `.pre-alloy` files, the two Promtail configs and the `promtail 256` ceiling retired spec-row first (spec § The delta › D6)
- **Given** the close, **When** it is read, **Then** the operator signals the fleet agent that all three hosts passed their battery, and only then does the fleet agent send `fleet-alloy` for merge with `merge_request.py request` and send the infra mail (spec § Personas; § The delta › D8; § Lifecycle)
- **Given** the appendix, **When** its mail body is checked with `mail.py`'s `_structure_gaps`, **Then** it carries every D-035 section and names every infra-owned file of spec § Lifecycle (spec § Lifecycle; scripts/mail.py)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- docs/operations/postgres-major-upgrade-runbook.md
- tests/test_pg18_runbook.py
- scripts/sync_prometheus_to_vps.sh
- scripts/sync_gatus_to_vps.sh
- scripts/sysadmin/proactive-check.sh
- .windsurf/rules/core/40-documentation.md
