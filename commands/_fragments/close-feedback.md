## ⚠️ Close-out feedback — PROACTIVE, and owed before you close the run record

**Auto-appended to every `/fabrik-*` command. Running a command means using the machinery, which
makes you the only witness to how it actually behaved this run.** A defect you route around silently
dies in your context when the session ends.

**Before `command_run.py done`, answer this out loud — one line is enough:**

> `FEEDBACK: <what you filed, to whom> | none — <the surfaces this run exercised>`

**"none" is a valid verdict and it must be STATED, never left as silence.** Silence and "I found
nothing" are byte-identical to the reader, and only one of them is information. Name the surfaces you
actually exercised so the reader knows what your "none" covers.

### File it when this run hit any of these

- a command's instruction that was wrong, stale, impossible, or contradicted another command
- an enforcement check that fired on a legitimate pattern (false positive) or stayed silent on a real
  one (false negative) — both are defects, and the false positive is the more corrosive
- a rule pack that contradicted another pack, or that never activated where it was needed
- a script, hook, or scaffold emission that did not behave as its own docs describe
- friction that cost you real time: an ambiguous step, a missing arg, an undocumented prerequisite
- anything you had to WORK AROUND to finish. A workaround is allowed; an unreported workaround is not

### Route by BEAT, never by convenience (charters: `docs/reference/agents/`)

| To | Owns |
|---|---|
| **infra** | `commands/_sources/`, `.windsurf/rules/`, `scripts/enforcement/`, `.claude/hooks/`, the box mesh, fabrik-mail |
| **fleet** | `specs/services/*.yaml`, deploy/VPS/monitoring, scaffolding, `docs/PROJECT_CATALOG.md` |
| **intel** | models, benchmarks, the flywheel, author-blind review |

```bash
python scripts/mail.py send --to fabrik --to-agent <infra|fleet|intel> --kind finding --ack required
# body on stdin: what you ran · what you expected · what happened · evidence at path:line · your fix direction
```

Genuinely unsure who owns it ⇒ `--broadcast --ack no` rather than dropping it. **In a PROJECT repo**,
a defect in a SYNCED file additionally follows `/fabrik-upstream` — never edit the synced copy.

**The bar is evidence, not a complaint.** One reproducible `path:line` and the command you ran beats
a paragraph of impression. If you already fixed it in your own beat, say so and skip the mail — the
duty is about what you are NOT going to fix yourself.
