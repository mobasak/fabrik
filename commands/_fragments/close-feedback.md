## ⚠️ Close-out feedback — PROACTIVE, and owed before you close the run record

**Auto-appended to every `/fabrik-*` command. Running a command means using the machinery, which
makes you the only witness to how it actually behaved this run.** A defect you route around silently
dies in your context when the session ends.

**Before `command_run.py done`, TWO one-line answers are owed. First the decision line:** did this
run MAKE or RECEIVE a decision (an operator ruling, an approval/Status flip, a retirement/adoption,
an architecture/scope choice, "built X at Y", a rejected option worth not re-proposing)? → its row
appended to `docs/DECISIONS.md` in this run's change — a chat-only/read-only run with no change of
its own commits the row standalone, THE ROW IS THE CHANGE (this row is the ONE artifact a read-only
command writes — it supersedes a "writes no artifact" clause, which governs the audit output, not
the ledger) — classified at mint (reversible / ONE-WAY, the
manifesto's Phase-0 triage; a ONE-WAY row grows the § Binding field block, per CLAUDE.md § the
decision ledger) — or state `no decisions this run`. **Then the
feedback line:**

> `FEEDBACK: <what you filed, to whom> | none — <the surfaces this run exercised>`

**A "filed" claim MUST name a durable artifact — the mail id, or a COMMITTED path.** A cross-repo
write to a hub path is not a filing (live case: "filed (5 items)" to a hub file that was never
tracked on any branch — 4 of 5 unrecoverable). No artifact = not filed.

**Then pass it: `done --command <name> --evidence "<proof>" --feedback "<that same line>"`. The close
REFUSES without it** — and the TEXT is persisted and READ: the operator reviews every verdict via
`python3 scripts/enforcement/check_feedback_duty.py --digest` (D-055 — the substance used to be
classified into a token and discarded, which is why five operator asks produced zero visible
reports; write the verdict as a report to a human, because it now reaches one) — — and a refused close leaves the record `running`, which the Stop hook blocks the
turn on. ⚠️ **If your repo's `command_run.py` predates `--feedback` it will ERROR on the unknown argument
instead of refusing** — that is a STALE VENDORED COPY, not an exemption. It happens in **sync-excluded**
repos (fabrik-lib hit it: `01M14V7KH4`), where the box-wide command corpus you are reading is NEWER than
the repo-local script it tells you to run — new instruction + old tool, the same trap that produced
`error: unrecognized arguments: --feedback` on the day the refusal landed. Do NOT drop the verdict: close
with `--evidence` so the record does not stay `running`, **state your `FEEDBACK:` line in the response**
(it is owed to the reader, not to the parser), and file the stale-copy fact upstream so the vendored script
gets re-synced. A verdict you spoke is information; a verdict you skipped because the parser could not take
it is not.

This is not ceremony bolted onto the exit: it is the only moment you still hold the context
to answer, and the duty was measurably inert for as long as it was merely written down (13 closes in
14 days, 12 with no verdict, zero filings — with the text below already present in all 31 commands).

**"none" is a valid verdict ONLY with its surfaces named — a BARE "none" is now REFUSED by the
parser (D-036, the operator's 5th ask made mechanical).** Write `none — surfaces exercised: <what
your run actually touched of the machinery>`; silence and a bare "none" are byte-identical to the
reader, and the close will not accept either. This step is MANDATORY on every run of every command —
the record stays `running` (and the Stop hook blocks the turn) until a substantive verdict lands.

### File it when this run hit any of these

- a command's instruction that was wrong, stale, impossible, or contradicted another command
- an enforcement check that fired on a legitimate pattern (false positive) or stayed silent on a real
  one (false negative) — both are defects, and the false positive is the more corrosive
- a rule pack that contradicted another pack, or that never activated where it was needed
- a script, hook, or scaffold emission that did not behave as its own docs describe
- friction that cost you real time: an ambiguous step, a missing arg, an undocumented prerequisite
- anything you had to WORK AROUND to finish. A workaround is allowed; an unreported workaround is not
- ⚠️ **a later pass, a stronger method, or the operator's re-ask caught something a CONVERGED pass
  of the same command had already stamped.** The false claim was yours; the no-op stamps that
  SURVIVED it are the machinery's, and that half is always filed. This is the trigger agents
  misclassify hardest — "my mistake, fixed in-run" — and it is exactly how two converged
  /fabrik-plan-review passes carrying a false Evidence-table claim produced zero mail
  (trade-intelligence 2026-08-29, surfaced only because the operator re-asked with a different
  method and then pasted the result to infra BY HAND — the duty this bullet exists to replace)
- **you misread the same tool's output more than once in a session** (a `| head`-truncated pipe, a
  silently-failing compound grep). Twice is a tooling-discipline gap in the machinery's guidance,
  not a personal slip — file it with the exact pipeline that misled you

### Route by BEAT, never by convenience (charters: `docs/reference/agents/`)

| To | Owns |
|---|---|
| **infra** | `commands/_sources/`, `.windsurf/rules/`, `scripts/enforcement/`, `.claude/hooks/`, the box mesh, fabrik-mail |
| **fleet** | `specs/services/*.yaml`, deploy/VPS/monitoring, scaffolding, `docs/PROJECT_CATALOG.md` |
| **intel** | models, benchmarks, the flywheel, author-blind review |

```bash
python scripts/mail.py send --to fabrik --to-agent <infra|fleet|intel> --kind finding --ack required
# body on stdin — the D-035 contract (docs/reference/fabrik-mail.md § The message contract):
# WHAT/WHERE/WHEN/WHO/WHY(factual root cause)/HOW/SYSTEMIC(the class) mandatory;
# ABDUCTIVE (alternatives ruled out) when WHY is inferred; INDUCTIVE/DEDUCTIVE/COUNTERFACTUAL where they carry weight
```

Genuinely unsure who owns it ⇒ `--broadcast --ack no` rather than dropping it. **In a PROJECT repo**,
a defect in a SYNCED file additionally follows `/fabrik-upstream` — never edit the synced copy.

### A subagent's finding is YOURS to file

Subagents are ephemeral. A `fabrik-reviewer` that notices a false-positive check, a
`fabrik-researcher` that hits a dead reference, a pool finder that trips over a contradictory rule —
each surfaces it in its return value and then **ceases to exist**. If you do not carry it out, it is
gone, and the subagent cannot mail anything itself.

So: when you adjudicate subagent output, findings about the MACHINERY (not about the code under
review) come to you, and you file them under the routing above. They are the cheapest findings you
will ever get — someone else already did the work of hitting the defect.

**The bar is evidence, not a complaint.** One reproducible `path:line` and the command you ran beats
a paragraph of impression. **And know which fix discharges the duty: fixing your ARTIFACT never
does.** Correcting the false claim, the missed row, the wrong verdict heals YOUR run; the mail heals
the COMMAND that let it survive — both are owed, always. The only fix that replaces the mail is
fixing the MACHINERY itself (a hub agent, in-beat, in the same run — say so in the FEEDBACK line).
A "none" verdict asserts all of the above triggers came up empty — it is a claim, and you are
signing it.
