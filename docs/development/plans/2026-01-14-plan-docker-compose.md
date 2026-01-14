# Containerize Fabrik for Coolify

**Created:** 2026-01-14
**Status:** 🚧 IN_PROGRESS

## Goal
Provide production-ready Dockerfile and compose.yaml for Fabrik, using env-driven configuration and a health endpoint that exercises real external dependencies (Coolify, DNS manager) to satisfy Coolify deployment requirements.

## DONE WHEN
- [ ] Dockerfile uses `python:3.12-slim-bookworm`, installs app dependencies, runs as non-root, and relies solely on environment variables (no hardcoded hosts)
- [ ] compose.yaml targets Coolify (external `coolify` network), exposes the service port, injects required env vars, and includes a healthcheck hitting the app's `/health`
- [ ] A runtime health handler checks live dependencies (Coolify API + DNS manager) and reports failure with non-200 status when unreachable or misconfigured
- [ ] `.env.example` includes any new runtime variables or defaults needed for the container
- [ ] Required validators/tests run and pass

## Out of Scope
- Adding new deployment targets beyond Coolify
- Refactoring existing CLI commands or orchestrator logic
- Documentation beyond plan/index updates required for this task

## Steps
1. Review existing scaffolds/templates and env expectations for Docker/Compose and health checks
2. Design Dockerfile structure (multi-stage), runtime entrypoint, and dependency-aware health endpoint strategy
3. Implement Dockerfile, compose.yaml, and health handler; update `.env.example` if needed
4. Run validators/tests and adjust for lint or convention issues
5. Final verification: ensure healthcheck covers dependencies and compose aligns with Coolify conventions
