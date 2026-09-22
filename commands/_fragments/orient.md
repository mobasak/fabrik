## Orient — the four things every run executes before its first phase (D-335 § 5 item 7)

Right after `start`, ONE Bash call, its output READ, then ONE line in the reply — before phase 1's first read:

```bash
python3 scripts/sysadmin/mcp_health.py                          # MCPs — assigned vs live (2–3 s)
python3 scripts/select_rules.py --changed <the surface's paths>  # rules — the packs this surface activates
command grep -n "^## " agents-fabrik.md                          # infra — the sections the surface touches
command grep -n "^## " docs/reference/operating-manifesto.md     # manifesto — the Phase this run is
```

`ORIENT: mcp <live>/<assigned> · rules <packs, or none> · infra <agents-fabrik.md sections read> · manifesto <Phase n>`

Executed, never recalled: an assigned-but-dead MCP is FIX-FIRST (`CLAUDE.md` § Behavior) and is named on that
line, never a silent fallback; the packs listed are READ before the first edit; the infra and manifesto sections
named are the ones then read and cited `path:line` where the run relies on them. A surface with no paths yet (a
spec from an idea) runs `select_rules.py` bare and reads the ACTIVE packs whose description matches the work. A
reply whose `ORIENT:` line has an empty field has skipped a step, not saved one.
