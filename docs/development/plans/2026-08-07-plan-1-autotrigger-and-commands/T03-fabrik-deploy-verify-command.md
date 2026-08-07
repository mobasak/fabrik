# T03 — `/fabrik-deploy-verify` command

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas
Gate: python commands/assemble_commands.py --check

## Scope

Author `commands/_sources/fabrik-deploy-verify.md` — post-`fabrik apply` certification closing the
trigger→verify loop — and wire it into the assembler. ALSO update the chain so the command is
discoverable: `commands/_sources/fabrik-release.md`'s terminal line ("Next command: none…") and the
assembler's `fabrik-release` NEXT entry both become "Gate 2 — human approval; after the operator
runs `fabrik apply`, verify with `/fabrik-deploy-verify`" (deploy-verify's own NEXT: none —
terminal). DO-NOT: run any deploy action (verify-only — the sibling of `/fabrik-release`'s
never-ship rule); DO-NOT touch other sources beyond fabrik-release's two chaining lines.

The command's contract: runs AFTER the operator's hub-side `fabrik apply` (the NEXT target from
release's Gate-2). Checklist, every item PASS/FAIL-with-evidence: **DNS** — the spec's `domain`
resolves (compare against two resolving sibling domains — the captcha lesson: absence-vs-outage
discrimination); **health** — `/health` + `/readyz` over HTTPS with real dependency assertions;
**registrars** — what the spec's `shape:` obligated (DB/redis/Gatus/GlitchTip/prometheus rows)
actually exists — inspection via the project's injected `.env` + probe endpoints, never a hub
shell-out from a project; **Gatus** — the probe exists and is green; **logs** — a bounded scan of
recent container logs for crash/restart signatures; **smoke** — the top 3 FEATURES.md journeys
exercised against the LIVE service (read-only journeys only; a mutating journey needs the
operator's explicit go). Spoke-aware throughout (`target_vps:` → mesh-IP semantics per the
templates). **Termination** — verdict table; any FAIL → named route (`/fabrik-review`, rollback
note, or registrar re-apply ask to the operator). TRIGGER + `Stage: 6-release`.

## Touches

- commands/_sources/fabrik-deploy-verify.md
- commands/_sources/fabrik-release.md
- commands/assemble_commands.py

## Behavior Contract

- **Given** an operator-run `fabrik apply`, **When** `/fabrik-deploy-verify` runs, **Then** DNS-vs-siblings, health/readiness, registrar outcomes, Gatus state, and a log scan each get a PASS/FAIL verdict with evidence (commands/_sources/fabrik-deploy-verify.md:1).
- **Given** a healthy-looking deploy with a FEATURES.md, **When** deploy-verify's smoke runs, **Then** the top user journeys from FEATURES rows are exercised against the LIVE service (commands/_sources/fabrik-deploy-verify.md:1).

## Context Files

- commands/_sources/fabrik-release.md (the upstream Gate-2 handoff this verifies; NEXT-map linkage)
- commands/_sources/fabrik-service-test.md (journey-exercising idiom to borrow, scoped down)
- commands/assemble_commands.py (wiring shape)
- templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md (hub/spoke DSN + target_vps semantics)
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md (§11 registrar table = the obligation list)
- docs/reference/MD/ai-prompt-templates.md (Parts A–C)
