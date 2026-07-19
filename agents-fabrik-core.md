# Fabrik Platform Core (high-frequency facts — @import-ed into CLAUDE.md)

<!-- The full canonical map is agents-fabrik.md (Reads-fetched at plan time). This file carries ONLY the
facts needed in most turns (spec 2026-07-18 § Constraints: @import criterion = frequency-of-need). -->

- **Fleet:** vps1 (LA, hub) + vps2/vps3 (Coventry, spokes) on WireGuard `10.99.0.0/24`. Shared infra
  (postgres-main, redis-main, glitchtip, authelia, loki, meilisearch) is **hub-only**; spokes reach it at
  `10.99.0.1:<port>`. Every spec declares `target_vps:` (default `vps1`).
- **Backing services (container DNS, never localhost):** `postgres-main:5432` · `redis-main:6379` — all
  containers on the external `fabrik` network; **Traefik routes** (no host `ports:`); every service
  declares `deploy.resources.limits.memory`.
- **Deploy = trigger, don't execute:** projects can't self-deploy (no fleet creds by design). The hub runs
  `fabrik apply specs/services/<id>.yaml` (SSH + Docker Compose); the VPS `git pull`s from GitHub — commit
  → push → redeploy. The spec's `shape:` block is canonical: code matches IT.
- **Two dev envs, one code:** WSL dev (`.venv`, PG on localhost via env) ↔ VPS Docker (`postgres-main`,
  compose) — same code runs unmodified; host names are env-layer, never code logic.
- **Front door (three tiers):** feature-scale → `/fabrik-spec` pipeline · epic →
  `docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik` · multi-epic vision →
  `docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik` (EXISTING mode for existing projects). Test:
  needs tickets + dispatched agents ⇒ epic/vision; one operator-carried plan ⇒ feature-scale.
- **Discipline delivery (north-star § Enforcement Model):** plan-time `python scripts/select_rules.py`
  (ACTIVE packs); review-time `python scripts/review_rubric.py --changed <paths>` (injected rubric +
  mandatory-core floor); completion `python scripts/final_gate.py --json`.
- **Full map (plan-time read, not auto-loaded):** `agents-fabrik.md` — topology detail, services,
  microservices, active projects, scaffold types, planning constraints. Ports: `PORTS.md`. Owned external
  services (HUB-side planning only — not synced to projects): `/opt/fabrik/scripts/service_catalog.json` (secret-free).
