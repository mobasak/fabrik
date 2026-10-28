# Claude tab router — any repo's agent in one VS Code window

Box-local (W-ea993618 stage 2). The operator's ask: *"i want single vs code looking window for any repos to open any
agents in it opened via claude vs code extension"*.

The Claude extension scopes a new chat tab, and its history list, to the window's **first folder**, so from the fabrik
window no tab can open another repo's agent. The extension does run every chat through one hook,
`claudeCode.claudeProcessWrapper`, set in `~/.vscode-server/data/Machine/settings.json` to
`~/.claude/bin/claude-agent-wrapper.sh`. The router makes that wrapper decide, per tab, **where** and **as whom** the
chat runs.

## What happens when you open a chat tab

A small window, **"Claude — open which agent in this tab?"**, lists:

| Row | What it does |
|---|---|
| `Plain chat in <folder> — as today` (default) | the tab runs exactly as before the router existed |
| `Resume <role> (<repo>) — last <date>` | the role's newest session, in that session's own folder (a builder's worktree included), with `CLAUDE_AGENT=<role>` |
| `New session as <role> in <repo>` | a fresh chat in that repo, bound to the role |
| `New session in <repo>` | a fresh chat in that repo, no role |
| `<role> (<repo>) — live elsewhere (pid N)` | listed, **refused**: that role already runs in another process (one process per session id — coordinator ruling 2026-10-21); the tab runs plain |
| `<role> (<repo>) — cannot bind` | a registered name `whoami_agent.py` would not accept |

Enter or double-click picks; Esc, closing the window, or the **30 s countdown** gives a plain chat. Repos are listed
when they have a known agent: `<repo>/.fabrik/session-agents.json`, the identity store
`~/.claude/state/agent-identity.jsonl` (last row per session wins), the router's own map
`~/.claude/state/tab-router.jsonl`. A listed repo also offers its merge owner (`decisions.py --merge-owner`) as a
role; a merge owner alone does not list a repo.

No window appears for: the extension's `auth status` and config-probe launches, a tab you resume from its own history
list, and a **restored** routed tab — that one is re-rooted silently to its session's folder with its role.

## How it is built

| Piece | Path |
|---|---|
| wrapper (source) | `scripts/sysadmin/claude-agent-wrapper.sh` — installed by copy at `~/.claude/bin/claude-agent-wrapper.sh` |
| router | `scripts/sysadmin/claude_tab_router.py` — the wrapper runs the MAIN checkout's copy, `/opt/fabrik/scripts/sysadmin/claude_tab_router.py` |
| tests | `tests/test_claude_tab_router.py` |
| launch log | `~/.claude/state/wrapper-launch.log` — every launch, plus a `router:` line for each routed one |

Timing: the extension fails a chat whose process has not initialised within **60 s** (`initializeTimeoutMs`), so the
picker's deadline is 30 s and the router runs under `timeout -k 2 35`; it is handed the wrapper's pid and closes if
the tab dies first. The router never reads stdin (the extension's first message stays for the CLI) and writes nothing
the extension sees.

**Fail direction: open.** Any router error, a missing display, or the router not yet present in the main checkout
gives the plain launch of today. A process that is neither started with `CLAUDE_AGENT` nor bound in the identity store
is invisible to the liveness check, so its role can be offered twice; and a role picked in one tab is not "live" until
that tab's session record exists, so a second tab opened within seconds is offered the same role. A `New session as`
binds by `CLAUDE_AGENT` only — no identity-store row until `whoami_agent.py --as`.

## Install

After the change is merged to master (the wrapper calls the main checkout's router), the operator's one-time setup
script installs the wrapper and sets `claudeCode.claudeProcessWrapper` in the VS Code Machine and the code-server User
`settings.json` (the Fabrik Deck's panes, W-42d1ccb5) of each editor installed. The same run also does its other steps
(the user hooks and the archive timer) and refuses as a whole when one of them cannot plan, so read its dry run first —
`operator-setup.md`:

```bash
python3 /opt/fabrik/scripts/sysadmin/operator_setup.py           # dry run
python3 /opt/fabrik/scripts/sysadmin/operator_setup.py --apply
```

## Rollback

- **Fast:** add `"CLAUDE_TAB_ROUTER": "off"` to `claudeCode.environmentVariables` — every tab launches plain.
- **Full:** run the wrapper's undo line from the list `operator_setup.py --apply` printed (its backup is under
  `~/.local/state/fabrik/operator-setup-<timestamp>/`); an older hand install kept its copy in
  `~/.claude/bin/backups/claude-agent-wrapper.sh.*`.

## Acceptance (the operator)

1. In the fabrik window, open a new Claude tab: the picker appears in front without a click.
2. Pick `Resume youtube-coordinator (youtube)`: the tab answers as youtube-coordinator, and its transcript grows under
   `~/.claude/projects/-opt-youtube/`.
3. Esc on a new tab: a plain chat as before.
4. Pick a `live elsewhere` row: refused, plain chat.
5. Reload the window with a routed tab open: it comes back in its own repo, with its history (if the history does not
   render, that is a known extension limit — the session itself still resumes).

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/claude_tab_router.py`
- `scripts/sysadmin/operator_setup.py`
<!-- END related-scripts -->
