# Spec Pipeline Templates

**Last Updated:** 2026-01-08

Complete workflow for going from idea → scope → spec → implementation.

## The Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Idea Discovery                                        │
│ Command: droid exec idea "Your product idea"                   │
│ Output: specs/<project>/00-idea.md                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Scope Definition                                       │
│ Command: droid exec scope "<project>"                           │
│ Output: specs/<project>/01-scope.md                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: Full Specification                                     │
│ Command: droid exec spec "<project>"                            │
│ Output: specs/<project>/02-spec.md                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4: Implementation (existing Fabrik workflow)              │
│ Command: droid exec plan / droid exec code                      │
│ Or: Use Traycer for phased execution                            │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Capture your idea
droid exec idea "Voice-controlled home automation for elderly users"

# 2. Define scope boundaries
droid exec scope "home-automation"

# 3. Generate full spec
droid exec spec "home-automation"

# 4. Continue with implementation
droid exec plan "Implement home-automation per spec"
# OR use Traycer for phased execution
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

## Traycer Integration (Optional)

If using Traycer.ai for enhanced planning:

1. Point Traycer to `specs/<project>/02-spec.md`
2. Use templates from `templates/traycer/` for:
   - Plan generation
   - Task execution
   - Verification

See `templates/traycer/README.md` for details.

## Why This Works

| Problem | Solution |
|---------|----------|
| AI forgets context | Fresh session per stage, full context in prompt |
| Scope creep | Explicit IN/OUT boundaries in 01-scope.md |
| Inconsistent decisions | Single source of truth (02-spec.md) |
| AI doesn't know when to stop | Clear acceptance criteria |
