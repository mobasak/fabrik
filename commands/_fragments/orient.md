## Orient — the four things every run executes before its first phase (D-335 § 5 item 7)

Right after `start`, ONE Bash call, its output READ, then ONE line in the reply — before phase 1's first read:

```bash
python3 /opt/fabrik/scripts/sysadmin/mcp_health.py --repo .
python3 /opt/fabrik/scripts/select_rules.py --project-root . --changed <the surface's paths>
command grep -n "^## " /opt/fabrik/agents-fabrik.md
command grep -n "^## " /opt/fabrik/docs/reference/operating-manifesto.md
```

`ORIENT: mcp <live>/<assigned> · rules <n> of <N> matched (<pack names, or none>) · infra <agents-fabrik.md sections read> · manifesto <Phase n>`

The paths are hub-absolute because `mcp_health.py` and the manifesto live only in the hub. `<the surface's paths>` is the FILE LIST the run record's `--surface` names (`$(git diff --name-only <range>)`, a plan's Touches, a spec's files); a range or directory matches 0 packs at rc 0, so re-run with paths, never `none`. A surface with no paths yet runs it bare: a PLANNING command then reads every ACTIVE pack (`CLAUDE.md` § Orient 4, binding), every other command the ACTIVE packs whose description matches the work. An assigned-but-dead MCP is FIX-FIRST (`CLAUDE.md` § Behavior), named on that line, never a silent fallback. Read the listed packs before the first edit; cite the infra and manifesto sections `path:line` where the run relies on them. COBRA (D-253): every field is an EXECUTED output (the assigned count, the pack count with its denominator, the section names); an empty field has skipped a step.
