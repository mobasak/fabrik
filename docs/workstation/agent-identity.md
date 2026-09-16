# Agent identity — naming a session that is already running

**Box-local.** How an agent gets a name, why a window `/rename` is not one, and what to do with two
or three windows in one repo. Design: `docs/superpowers/specs/2026-09-16-multi-agent-self-naming-identity-design.md`
(D-267, D-268).

## The problem, in one measurement

Identity has always resolved from `CLAUDE_AGENT`, a **launch-time** environment variable. A window
`/rename` changes the label in the UI and reaches nothing else. Measured 2026-09-16 on three live
`trade-intelligence` windows the operator had named `agent-1`, `agent-2`, `agent-3`:

```
pid 48200 · CLAUDE_AGENT=<UNSET>
pid 49965 · CLAUDE_AGENT=<UNSET>
pid 49985 · CLAUDE_AGENT=<UNSET>
```

…and **0 of that repo's last 40 commits** carried an `Agent-Name` trailer, while 40 of 40 carried
`Agent-Role`. Three agents, one checkout, nothing able to say which of them did anything.

## Naming a session

**A window that is already running** — no relaunch, the chat history survives:

```bash
python3 /opt/fabrik/scripts/whoami_agent.py --as agent-2
python3 /opt/fabrik/scripts/whoami_agent.py --who      # prints the resolved name
```

**A window you are about to open** — still the better path when you have the choice:

```bash
CLAUDE_AGENT=agent-2 claude -n agent-2-<repo>
```

Both are valid; the env var always wins over a binding, so a named launch never needs the command.

## How it resolves

`CLAUDE_AGENT` (when well-formed) → this session's **binding** → `""`. A malformed env value falls
through to the binding, which changes nothing for anyone actually named — a malformed value already
resolved to `""` before this existed.

The binding is keyed on `CLAUDE_CODE_SESSION_ID`, which — unlike `CLAUDE_AGENT` — **is** exported
into every shell a live session runs, and **git hooks inherit it** (executed: a `commit-msg` hook
printed the sid while `CLAUDE_AGENT` was empty). ⚠️ The `claude` process itself does **not** carry
it, so the session's pid is found by walking `/proc` ancestry, never by matching the sid.

Store: `$AGENT_IDENTITY_FILE`, else `~/.claude/state/agent-identity.jsonl`. `$HOME`-keyed, not
`$CLAUDE_CONFIG_DIR`-keyed, so a session pinned to another account slug shares it. Append-only, last
row wins per session, rows trimmed at 30 days by the writer — nothing else prunes that directory.

## What it refuses, and why

- **A name outside `^[a-z0-9-]{1,32}$`.** `Agent-2`, `agent_2` and `agent.2` are accepted by
  `mail.py` but rejected by `command_run.py` and `agent_role.py`, so such a name would bind and then
  be silently dropped downstream — one session with two identities and no error anywhere.
- **A name a LIVE session already holds in this repo** (scoped to the git toplevel, not the cwd — a
  plain `cd` defeated a cwd-scoped check). `--force` overrides and records that it did.
- **Re-binding one session id to a different name**, without `--force`. A Task subagent inherits its
  dispatcher's session id, so this would otherwise let a seat silently re-identify the session that
  dispatched it.

## What it does NOT do — read this before relying on it

- **It is not a lock against `--force`.** A bind is serialized (an `flock` around the whole
  read-modify-write, so a concurrent sibling can neither double-bind nor be erased by the 30-day
  trim), but `--force` deliberately overrides a live holder. Nothing downstream catches two
  sessions on one name: `check_commit_trailers.py` reads `CLAUDE_AGENT` **directly** and never
  consults this binding at all — so for a session named with `--as` its mismatch check does not
  merely lack cross-session state, it **does not fire**. Routed to
  `docs/STRATEGIC_BACKLOG.md`, owner infra.
- **A binding with no session pid reserves nothing.** If the `/proc` ancestry walk cannot find the
  `claude` ancestor, the row carries no pid and cannot hold the name against a sibling. The bind
  says so in its success message rather than implying protection it does not have.
- **The SessionStart hooks bind late.** `agent_role.py` (the role charter) and `session_orient.py`
  (the unnamed-session advisory) both run at session start, so naming yourself mid-flight takes
  effect for them at the NEXT start. Attribution in run records is immediate.
- **The mandated shared-append commit path fires no git hook.** `git commit-tree` + `git update-ref`
  — which `CLAUDE.md` requires for `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`
  and `INDEX.md` — runs none of the four commit hooks (executed). On that path you call
  `--who` yourself while composing the message, and write the `Agent-Name:` trailer by hand.

## Working with 2–3 agents in one repo today

1. Name each window once, with the command above.
2. Write `Agent-Name: <yours>` in every commit's trailer block — by hand; no hook injects it.
3. Never `git commit -- <paths>` on the four shared-append files; use the private-index recipe in
   `CLAUDE.md` § Behavior.
4. Take a plan-lock before touching a path a sibling might.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/whoami_agent.py`
<!-- END related-scripts -->
