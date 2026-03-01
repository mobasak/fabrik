Phase 5: Create kilo_agent_health.sh utility

Created a health check utility for verifying Kilo CLI agent integrity.

FEATURES:
- Checks agent directory existence
- Counts total agents
- Per-agent validation:
  * Executable permission
  * Correct shebang (#!/bin/sh)
  * TRAYCER_PROMPT handling
  * Exit statement presence
  * Shell syntax check (sh -n)

OUTPUT:
- Visual status per agent (✓ healthy / ❌ issues)
- Detailed issue reporting
- Summary: total/healthy/issues count
- Exit code 0 if healthy, 1 if issues

USAGE:
```bash
bash scripts/kilo_agent_health.sh
```

BENEFITS:
- Quick verification after regeneration
- CI/CD integration ready
- Catches generation errors
- Clear actionable feedback
