# Spec Pipeline Templates

**Last Updated:** 2026-03-24

Complete workflow for going from idea → scope → spec → implementation.
Traycer is the primary orchestrator (see `AGENTS.md` Stage 0).

## The Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 0.1: Idea Discovery                                      │
│ Traycer: /discover <idea>                                      │
│ Kilo:    kilo run "Discover idea: <idea>"                     │
│ Output:  specs/<project>/00-idea.md                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 0.2: Scope Definition                                    │
│ Traycer: /scope <project>                                      │
│ Kilo:    kilo run "Define scope for <project>"                │
│ Output:  specs/<project>/01-scope.md                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 0.3: Full Specification (SSoT)                           │
│ Traycer: /spec <project>                                       │
│ Kilo:    kilo run "Generate spec for <project>"               │
│ Output:  specs/<project>/02-spec.md                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ EXECUTION: Phased YOLO / Epic (existing Fabrik workflow)       │
│ Traycer converts 02-spec.md into phased implementation plan    │
│ Enforcement: Traycer rejects tasks if 02-spec.md is missing   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Traycer-led (preferred)
/discover "Voice-controlled home automation for elderly users"
/scope "home-automation"
/spec "home-automation"
# Traycer then converts spec into Phased YOLO or Epic plan

# Kilo CLI alternative
kilo run "Discover idea: Voice-controlled home automation for elderly users"
kilo run "Define scope for home-automation"
kilo run "Generate spec for home-automation"
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `00-idea-prompt.md` | Discovery prompt for idea capture |
| `01-scope-prompt.md` | Scope definition prompt (IN/OUT boundaries) |
| `02-spec-prompt.md` | Full specification generation prompt |

## Output Structure

```
specs/
└── <project-name>/
    ├── 00-idea.md      # Raw idea exploration
    ├── 01-scope.md     # IN/OUT boundaries
    └── 02-spec.md      # Complete specification
```

## Traycer Integration (Primary)

Traycer is the **planning authority** (see `AGENTS.md` Stage 0). It orchestrates the pipeline:

1. **Discovery Mode:** `/discover <idea>` — interviews the owner using `00-idea-prompt.md`
2. **Boundary Mode:** `/scope <project>` — locks MVP boundaries respecting ~50h/week capacity
3. **SSoT Mode:** `/spec <project>` — generates full spec with auto-injected Fabrik Stack Defaults
4. **Execution Mode:** Converts `02-spec.md` into `Phased YOLO` or `Epic` plan

**Enforcement:** Traycer rejects implementation tasks if `specs/<project>/02-spec.md` is missing or incomplete.

### Stack Auto-Injection (Stage 0.3)

During spec generation, Traycer auto-injects these Fabrik defaults into the Stack Profile:

| Component | Default | Override When |
|-----------|---------|---------------|
| Frontend | Next.js 14 + TypeScript + Tailwind | — |
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Database | PostgreSQL 16 (Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Base images | `-slim-bookworm` | Never Alpine |
| Platform | `linux/amd64` | Always amd64 |
| Hosting | Coolify on x86_64 VPS | — |

## Why This Works

| Problem | Solution |
|---------|----------|
| AI forgets context | Fresh session per stage, full context in prompt |
| Scope creep | Explicit IN/OUT boundaries in 01-scope.md |
| Inconsistent decisions | Single source of truth (02-spec.md) |
| AI doesn't know when to stop | Clear acceptance criteria |
| AI builds in vacuum | Plan Quality Gate requires 02-spec.md |
| Owner misalignment | Solo-dev capacity forced in scope stage |
