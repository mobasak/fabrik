## Orient — the four things every run executes before its first phase (D-335 § 5 item 7)

Right after `start`, ONE Bash call, its output READ, then ONE line in the reply — before phase 1's first read:

```bash
python3 /opt/fabrik/scripts/sysadmin/mcp_health.py --repo .                                    # MCPs — this repo's assigned vs live (~3 s)
python3 /opt/fabrik/scripts/select_rules.py --project-root . --changed <the surface's paths>   # rules — the packs this surface activates
command grep -n "^## " /opt/fabrik/agents-fabrik.md                                            # infra — the sections the surface touches
command grep -n "^## " /opt/fabrik/docs/reference/operating-manifesto.md                       # manifesto — the Phase this run is
```

`ORIENT: mcp <live>/<assigned> · rules <n> of <N> matched (<pack names, or none>) · infra <agents-fabrik.md sections read> · manifesto <Phase n>`

Hub-absolute paths on purpose: the rendered command runs from every repo on the box and two of the four live only in
the hub (`mcp_health.py`, the manifesto are in no project; `--repo .` / `--project-root .` point the scripts at the
repo you are in). `<the surface's paths>` is the FILE LIST the run record's `--surface` names — `$(git diff
--name-only <range>)` for a diff range, a plan's Touches, a spec's files; a range or a directory passed as-is
matches 0 packs at rc 0 and is a re-run with paths, never `none`. A surface with no paths yet (a spec from an idea)
runs it bare: a PLANNING command then reads every ACTIVE pack (`CLAUDE.md` § Orient 4, binding); every other
command reads the ACTIVE packs whose description matches the work. Executed, never recalled — an assigned-but-dead
MCP is FIX-FIRST (`CLAUDE.md` § Behavior) and is named on that line, never a silent fallback; the packs listed are
READ before the first edit; the infra and manifesto sections named are the ones then read and cited `path:line`
where the run relies on them. COBRA (D-253): the cheapest way to satisfy "one ORIENT line" is to write it from
memory, so every field is an EXECUTED output — the assigned count, the pack count with its denominator, the
section names — and a recalled line reads wrong on the next run; an empty field has skipped a step, not saved one.
