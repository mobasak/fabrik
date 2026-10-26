## Orient — the four things every run executes before its first phase

After `start`: ONE Bash call, output READ, then ONE reply line before phase 1's first read:

```bash
python3 /opt/fabrik/scripts/sysadmin/mcp_health.py --repo . # MCPs (~3 s)
python3 /opt/fabrik/scripts/select_rules.py --project-root . --changed <the surface's paths> # rules
command grep -n "^## " /opt/fabrik/agents-fabrik.md # infra — sections touched
command grep -n "^## " /opt/fabrik/docs/reference/operating-manifesto.md # manifesto — Phase
```

`ORIENT: mcp <live>/<assigned> · rules <n> of <N> matched (<pack names, or none>) · infra <agents-fabrik.md sections read> · manifesto <Phase n>`

Hub-absolute paths on purpose: the rendered command runs from every repo; two of the four live only in the hub (`mcp_health.py`, the manifesto are in no project; `--repo .` / `--project-root .` point the scripts at the repo you are in).

`<the surface's paths>` is the FILE LIST `--surface` names — `$(git diff --name-only <range>)`, a plan's Touches, a spec's files; a range or directory passed as-is matches 0 packs at rc 0, a re-run with paths, never `none`. A surface with no paths (a spec from an idea) runs it bare: a PLANNING command reads every ACTIVE pack (`CLAUDE.md` § Orient 4, binding); every other command reads ACTIVE packs whose description matches the work.

Executed, never recalled — an assigned-but-dead MCP is FIX-FIRST (`CLAUDE.md` § Behavior), named on that line, never a silent fallback; the listed packs are READ before the first edit; infra and manifesto sections named are then read, cited `path:line`. COBRA (D-253): the cheapest pass at "one ORIENT line" is writing it from memory, so every field is an EXECUTED output; an empty field has skipped a step, not saved one.
