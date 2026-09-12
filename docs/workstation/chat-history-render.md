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

1. A reloaded window's panel is rebuilt by the **extension host**, not by a CLI process: the webview sends
   `get_session_request`, `extension.js` reads the `.jsonl` and its loader (function `i11`) walks the
   transcript's **`parentUuid` links from the newest record back to a root**.
2. Every compaction writes a `{"type":"system","subtype":"compact_boundary"}` record whose `parentUuid`
   is **`null`** — a new root — **and** the loader's `compactMetadata` pass then re-parents that boundary's
   preserved messages onto the compaction summary, discarding the real `parentUuid` links they still carry
   into pre-compaction history. The two together end the walk at the boundary; the boundary's
   `logicalParentUuid` back-link is never followed. (Measured: with only the re-parenting pass disabled in
   a simulation the chain grows 8 → 881 on `37887efc` and 2,093 → 9,306 on `1991fa9b`.)
3. So the walk yields the last boundary, its summary, that boundary's preserved messages (3 on both
   sessions measured; 2–43 and 2–160 across their 91 boundaries) and whatever came after: **8 records**
   on agent-2 (compacted 2026-09-09 and idle since) and **2,093** on agent-1 (compacted 2026-09-02), out
   of the **83,161** and **76,867** records the loader parses (116,389 and 105,742 lines on disk). The
   loader then drops `system` and meta records, so the panel receives **4** and about **1,370** messages.

There is no time window ("7 days", "30 days") in that path and no history-depth setting. The loader
API can page (`offset`/`limit`) but nothing wires it — the webview sends neither, has no load-more
control, and its only related string is the error *"Couldn't load this conversation's earlier
messages"* — and paging would not help anyway, because the walk, not the slice, is the limiter. The 5 MB
byte-skip switch `CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP` does not help either: the skip only cuts back to
the last boundary that carries **no** preserved metadata, and all 91 boundaries in these two files carry
it, so the skip is inert here and the full-file walk still returns 8 and 2,093. Reloading, restarting
VS Code, renaming the session or rotating accounts changes nothing (the `restored_owner_mismatch` veto a
rotation triggers gates the remote-control bridge and remote backfill, never the panel —
`session-recall.md` § Why a reloaded window). Rewriting transcripts to re-link the tree is **rejected**
(D-235, restated by D-236): the CLI's own resume reconstruction walks the same `parentUuid` chain to
build the model's context, so a re-linked tree would hand it the whole file.

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
- `INDEX.md` per project: every session newest-first with id, span, compaction count, turn counts and the
  number of unparseable records dropped from that transcript (also a `WARN` per transcript).
- `--name ID-PREFIX=LABEL` names a session's file after the window's session name; the mapping persists
  in `names.json` beside the renders, so later runs without `--name` keep the names. When several
  prefixes match one session the longest wins, whatever order the file was written in; a key shorter
  than the 8-character floor is ignored with a `WARN` on every run until it is fixed (it stays in the
  file, unused — never deleted). A session with no name renders as the first 8
  safe characters of its id (unsafe characters become `-`, leading punctuation is dropped, `session` if
  nothing safe remains), so a transcript whose name starts with a dot never yields a hidden render. One label on two
  sessions never shares a file: the second renders as `<label>-<id8>.md` with a `WARN` on stderr.
- **Incremental:** `.render-state.json` records each transcript's size, mtime and label; a session whose
  size, mtime and label are unchanged is skipped (a renamed session re-renders under its new name), so a
  refresh over 276 sessions costs seconds.
- **Contained failures, at every grain:** a record that is not a JSON object, a compaction record whose
  metadata is not an object, a non-string timestamp or a lone surrogate never crash a render; a transcript
  that cannot be read (permissions, a broken symlink) is a `WARN` and a skip; a project whose output
  folder is blocked is a `WARN` and a skip under `--all`; the exit code is 1 when anything was skipped. A
  state row that lost its shape (a hand-edited or older-schema row) reads silently as "never rendered"
  and the session simply renders again. Every file (render, `INDEX.md`, sidecars) is written through a
  per-process temp file and rename, and a project directory is locked (`.render.lock`, `flock`) so two
  overlapping runs — the cron line and a hand run — never interleave: the second backs off with a `WARN`.
- A project with no transcripts is a named `ERROR` on stderr and exit 1, never a traceback. One unreadable
  transcript (a file mid-write, a permission slip) is a `WARN` on stderr and is skipped — the rest of the
  project and every other project under `--all` still render; the exit code is then 1.
- A `--name` prefix must carry at least 8 id characters, so a prefix does not sweep up unrelated
  sessions; a label starts with a letter or digit and continues with letters, digits, `.`, `_`, `-` (up
  to 120 characters; never `INDEX` or `names`) so it is both a safe file name and a clean markdown link —
  refused on the command
  line and, if hand-edited into `names.json`, replaced by the session id with a `WARN`. Under `--all` a
  `--name` is persisted only in the project where that session lives. A `--project` value is a repo
  path, an `/opt/<name>` shorthand or an existing project key; anything that would resolve outside the
  history root is refused.
- A render outlives its transcript on purpose: if retention or a hand deletes the `.jsonl`, the `.md` stays
  (it is then the last copy of that conversation), drops out of `INDEX.md`, and is never overwritten — a
  later `--name` that lands on its file name renders as `<label>-<id8>.md` instead, and that suffixed
  name is checked again (longer slices of the safe id, then a counter, 104 candidates in all, each
  trimmed to the label rule so the session stays incremental; a session that finds
  no free name is skipped with
  a `WARN` and counts toward the exit code 1, never left spinning; the collision is warned about once,
  when it is first resolved). An old file is unlinked only after its replacement landed.
- A `names.json` or `.render-state.json` that is not a JSON object is moved aside to
  `<name>.bad-<stamp>` with a `WARN`, never silently replaced.

## How to use it from a window

Open the session's `.md` in a VS Code tab beside the chat panel and read down from the compaction
heading you need. Inside the window, tell the agent *"read `~/.claude/state/history/<key>/agent-2.md`
from compaction 46 and resume from there"* — the agent can also search the same history through
session-recall (`search_chats` / `get_chat`), which indexes the same transcripts.

To keep the renders current without thinking about it, add a cron line yourself (crontab writes are
classifier-blocked for agents — `docs/workstation/wsl-startup-inventory.md`):

```
*/30 * * * * python3 /opt/fabrik/scripts/render_chat_history.py --all >>~/.claude/state/history/render.log 2>&1
```

The log, not `/dev/null`: a skipped transcript is a `WARN` line and exit code 1, and cron mails nothing
on this box, so the log is the only place the signal survives.

## Limits

- The transcripts are the source of truth; a session deleted by retention (`cleanupPeriodDays`, raised
  to 3650 by D-233) before it was ever rendered is gone from here too — an existing render survives
  (above). Nothing backs `~/.claude/projects/` up.
- Subagent transcripts (`<session>/subagents/`) are not rendered — only the main conversation.
- Renders are large (the two 300 MB transcripts → 6.7 and 7.9 MB of markdown); VS Code opens them, but
  search inside with the editor's find, not the preview.

## Related

- `docs/workstation/session-recall.md` — the searchable index over the same transcripts.
- `docs/workstation/claude-configuration-inventory.md` — where `~/.claude/projects/` and retention live.
- `docs/DECISIONS.md` D-233 (retention) · D-235 (this render; rewriting transcripts rejected) · D-236
  (the mechanism restated: null-parent boundary **and** the loader's re-parenting pass).

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/render_chat_history.py`
<!-- END related-scripts -->
