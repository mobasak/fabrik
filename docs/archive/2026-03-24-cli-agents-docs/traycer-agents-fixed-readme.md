# Traycer CLI Agents

**Date:** 2026-03-24 (Updated)
**Location:** `~/.traycer/cli-agents/`
**Generator:** `/opt/fabrik/scripts/generate_kilo_agents.py`

## Current Naming Convention

**Format:** `{role}-{priority}-{model}-{variant}-o{OUT}-ppd{PPD}.sh`

**Examples:**
```
code&fix-1-opus46-max-o2500-ppd076.sh      # Opus 4.6 (coding #1, fixing #1)
coding-2-gpt54-max-o1500-ppd123.sh         # GPT-5.4 (coding #2)
fixing-2-gemini31pro-max-o1200-ppd161.sh   # Gemini 3.1 Pro (fixing #2)
coding-3-gemini31pro-high-o1200-ppd161.sh  # Gemini 3.1 Pro (coding #3)
fixing-3-gpt54-high-o1500-ppd123.sh        # GPT-5.4 (fixing #3)
code&fix-4-gpt53codex-high-o1400-ppd---.sh # GPT-5.3-Codex (coding #4, fixing #4)
```

## Regenerating Agents

```bash
# From kilo_agents.db (source of truth)
python /opt/fabrik/scripts/generate_kilo_agents.py

# Dry run
python /opt/fabrik/scripts/generate_kilo_agents.py --dry-run
```

## WSL Startup Automation

Agents regenerate automatically on WSL startup via `wsl_startup_hook.sh`.

## Legacy Note

The old `scripts/traycer_agents_fixed/` directory with tier-based naming (`Balanced01-*`, `Economy01-*`) is deprecated. The current role-priority format is authoritative.
