Phase 4: Add script validation and backup to generate_kilo_agents.py

Added two new functions to improve safety and reliability:

1. validate_script(script_path) - Validates generated shell scripts
   - Checks for correct shebang (#!/bin/sh)
   - Verifies exit statement presence
   - Confirms TRAYCER_PROMPT handling
   - Runs shell syntax check (sh -n)
   - Returns list of issues (empty if valid)

2. backup_existing_agents(output_dir) - Backs up before regeneration
   - Creates timestamped backup directory
   - Uses shutil.copytree for full backup
   - Returns backup path or None
   - Only runs when not in dry-run mode

Integration:
- Backup called at start of main() before regenerating agents
- Validation called after each script is written
- Validation issues printed as warnings but don't block generation

Benefits:
- Safe rollback if generation fails
- Early detection of generation errors
- Prevents deployment of broken scripts
- Timestamped backups for audit trail
