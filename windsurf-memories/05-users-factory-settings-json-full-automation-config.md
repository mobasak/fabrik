# User's Factory settings.json - Full Automation Config

**Tags:** #factory #droid_exec #settings #configuration

Factory CLI settings file: `/home/ozgur/.factory/settings.json`

Key settings for full automation:
- Model: claude-sonnet-4-5-20250929
- Reasoning: high (specModeReasoningEffort: high)
- Autonomy: auto-high
- Hooks: enabled
- Skills: enabled
- Cloud sync: enabled
- Custom droids: enabled
- Co-authored commits: enabled
- Background processes: allowed

Command allowlist includes: git ops, package managers, python/node, docker, pytest, safe rm paths (/opt/*, ~/.cache/*, etc.)
Command denylist blocks: system destruction (rm -rf /, /etc, /usr, /home), mkfs, dd, shutdown, fork bombs, chmod hazards.
