# Chat-history render — the full per-project Claude Code history the VS Code panel cannot show

**Last Updated:** 2026-09-11 (D-235; measured against the Claude Code VS Code extension 2.1.258 and two live trade-intelligence sessions)

> **What this is:** a box-local script, `scripts/render_chat_history.py`, that turns every Claude Code
> transcript of a project into readable markdown — one file per session, every compaction a dated
> heading — under `~/.claude/state/history/<project-key>/`. It is the "load more" button the Claude Code
> VS Code panel does not have. The panel itself is Anthropic's closed extension and nothing on this box
> changes what it renders.

---

## Why the panel shows so little after a reload

Measured 2026-09-11 by reading the extension's own loader and simulating it on two 300 MB transcripts:

1. A reloaded window runs `claude --resume <session>` and rebuilds the view by walking the transcript's
   **`parentUuid` links from the newest record back to a root**.
2. Every compaction writes a `{"type":"system","subtype":"compact_boundary"}` record whose `parentUuid`
   is **`null`** — a new root. The compaction summary hangs off it; the pre-compaction records are linked
   only through `logicalParentUuid`, which the walk never follows.
3. So the panel renders: the last boundary, its summary, the three preserved messages, and whatever
   came after. On the two sessions measured that was **8 records** (agent-2, compacted 2026-09-09 and
   idle since) and **2,093 records** (agent-1, compacted 2026-09-02).

There is no time window ("7 days", "30 days") in that path, no history-depth setting, no load-more
control (the only related string in the webview is the error *"Couldn't load this conversation's
earlier messages"*), and the 5 MB byte-skip switch `CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP` does not help —
the walk stops at the boundary even over the full file. Reloading, restarting VS Code, renaming the
session or rotating accounts changes nothing (the `restored_owner_mismatch` veto a rotation triggers gates only the remote-control bridge reattach — `session-recall.md` § Why a reloaded window). Rewriting transcripts to re-link the tree is **rejected**
(D-235): the same tree feeds the model's context on resume and would overflow it on the next turn.

A **live** window is different: it keeps whatever it streamed since it was opened, which is why an
un-reloaded window can still show text from before its last compaction.

## What the script does

```
python3 /opt/fabrik/scripts/render_chat_history.py --project /opt/trade-intelligence \
    --name 1991fa9b=agent-1 --name 37887efc=agent-2
python3 /opt/fabrik/scripts/render_chat_history.py --project trade-intelligence   # /opt/<name> shorthand
python3 /opt/fabrik/scripts/render_chat_history.py --all                          # every project with transcripts
```

- Reads `~/.claude/projects/<project-key>/*.jsonl` — the ONE transcript store every rotated account shares
  (`~/.claude-fleet/<acct>/projects` are symlinks to it), so history is account-independent.
- Writes `~/.claude/state/history/<project-key>/<session-name>.md` — human turns and Claude's text only;
  tool calls, tool results, `<system-reminder>` injections, task notifications and hook output stripped;
  `<command-name>` invocations shown as `` `/command` ``; each compaction summary folded in a `<details>`
  block; every `## ⟲ Compaction #N — <timestamp>` heading dated, the LAST one carrying the note
  *"A reloaded VS Code window starts HERE"*.
- `INDEX.md` per project: every session newest-first with id, span, compaction count and turn counts.
- `--name ID-PREFIX=LABEL` names a session's file after the window's session name; the mapping persists
  in `names.json` beside the renders, so later runs without `--name` keep the names. One label on two
  sessions never shares a file: the second renders as `<label>-<id8>.md` with a `WARN` on stderr.
- **Incremental:** `.render-state.json` records each transcript's size and mtime; an unchanged session is
  skipped, so a refresh over 276 sessions costs seconds.
- A project with no transcripts is a named `ERROR` on stderr and exit 1, never a traceback.

## How to use it from a window

Open the session's `.md` in a VS Code tab beside the chat panel and read down from the compaction
heading you need. Inside the window, tell the agent *"read `~/.claude/state/history/<key>/agent-2.md`
from compaction 46 and resume from there"* — the agent can also search the same history through
session-recall (`search_chats` / `get_chat`), which indexes the same transcripts.

To keep the renders current without thinking about it, add a cron line yourself (crontab writes are
classifier-blocked for agents — `docs/workstation/wsl-startup-inventory.md`):

```
*/30 * * * * python3 /opt/fabrik/scripts/render_chat_history.py --all >/dev/null 2>&1
```

## Limits

- The transcripts are the source of truth; a session deleted by retention (`cleanupPeriodDays`, raised
  to 3650 by D-233) is gone from here too. Nothing backs `~/.claude/projects/` up.
- Subagent transcripts (`<session>/subagents/`) are not rendered — only the main conversation.
- Renders are large (a 300 MB transcript → ~10 MB markdown); VS Code opens them, but search inside with
  the editor's find, not the preview.

## Related

- `docs/workstation/session-recall.md` — the searchable index over the same transcripts.
- `docs/workstation/claude-configuration-inventory.md` — where `~/.claude/projects/` and retention live.
- `docs/DECISIONS.md` D-233 (retention) · D-235 (this render; rewriting transcripts rejected).

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/render_chat_history.py`
<!-- END related-scripts -->
