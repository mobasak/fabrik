## ⚠️ Close-out feedback — PROACTIVE, and owed before you close the run record

**Auto-appended to every `/fabrik-*` command. You are the only witness to how the machinery behaved this run;** a defect routed around silently dies with the session.

**Before `command_run.py done`, TWO one-line answers are owed. First the decision line:** did this run MAKE or RECEIVE a decision (an operator ruling, an approval/Status flip, a retirement/adoption, an architecture/scope choice, "built X at Y", a rejected option)? → append its row to `docs/DECISIONS.md` in this run's change; a chat-only/read-only run with no change of its own commits the row standalone, THE ROW IS THE CHANGE (it supersedes a "writes no artifact" clause). Classify it at mint (reversible / ONE-WAY, the manifesto's Phase-0 triage; a ONE-WAY row grows the § Binding field block, per CLAUDE.md § the decision ledger). Otherwise state `no decisions this run`. **Then the feedback line:**

> `FEEDBACK: /<command> · <wall-clock> · rounds <n> (<findings trend>) · tokens <input> input / <output> output (<n>% cached) · confusion: <what in the
> command text was ambiguous or misleading | none> · waste: <steps, turns or tokens spent without
> changing the outcome | none> · change: <axis>: <the ONE concrete edit to this command or a rule that
> would have made this run faster or more accurate | none> · filed: <mail id(s) to infra|fleet|intel|kaizen | none
> — surfaces exercised: <what your run touched>> [· cost: <a PLAIN AMOUNT, e.g. `0.0125` or `$0.30` — prose or `10 usd` is refused, it is summed>]`

**`change:` is AXIS-KEYED — lead the value with ONE axis, then a colon** (`change: lean: the rubric block is loaded in full and never cited — cut it to the matched rows`). The axis is the PROPERTY OF THE COMMAND TEXT your edit improves, not your run's topic: `lean` (it loads weight the run never used) · `fast` (it stalled you) · `accurate` (it told you something untrue or ambiguous) · `waste` (it cost turns or tokens that changed nothing) · `infra` (it is wrong about this box's machinery; NOT the infra BEAT of `filed:`) · `rules` (it contradicts or ignores a rule pack) · `manifesto` (it violates an operating principle). One axis per close — the report groups the queue by it, and a second key after a comma is not read. ⚠️ **The close REFUSES an unkeyed or unknown-axis `change:`** (`change: make it faster` and `change: banana: …` both), names the seven keys, and re-keys your value as the example. `change: none` is a verdict you sign and carries no key.

**Two traps.** (1) **Keep ` · `, `|`, `;` and newlines out of the value:** the close splits on one of those four ONLY when a field label (`confusion|waste|change|filed|cost`) and a colon follow: a ` · waste:` lands a duplicate field and REFUSES the close, a ` · cost:` truncates your sentence SILENTLY and files a phantom cost; a bare semicolon or pipe in your prose is harmless. A `change: waste: …` value must never begin a line. (2) **Never paste the grammar.** `_is_placeholder` strips an axis key before its `<…>` test, so a keyed template (`change: lean: <the ONE concrete edit …>`) is REFUSED exactly like the unkeyed one.

**This fragment is canonical:** `command_run.py`'s `_USAGE_GRAMMAR`, `docs/reference/command-run-protocol.md` and both `CLAUDE.md` FINAL OUTPUT blocks are hand-kept twins; `test_the_usage_grammar_constant_states_the_axis_key_the_fragment_mandates` grades the drift, so read it after rewording the grammar line.

**On an expensive command a SEAT writes the line.** If `python3 /opt/fabrik/scripts/command_feedback_report.py --observer-rank` names the command you are closing, dispatch ONE Sonnet seat to author `change:` from this run's evidence (phases, rounds, the diff, what you hit), because an agent grading its own run reads it worst. If the script or ledger is unreadable, write it yourself: the seat is never a gate and needs no dispatch stamp.

**The four fields are the USAGE report (D-175).** `rounds <n>` and `tokens <i>/<o>` are COUNTED and captured for you, and you get the behavior you measure (CLAUDE.md § THE FIX DIRECTIVE item 5): closing before the quiet round moves both counters the right way while the work gets worse. They report the run, never its goal; the goal is the terminal condition, proved in `done --evidence`.

**`command_run.py` REFUSES a close that lacks any of `confusion:` `waste:` `change:` `filed:` (or leaves one empty, or writes one twice).** The separator is ` · ` (`|`, `;` or a newline also count); a label counts only at a field boundary. Write what you SAW; a run that went cleanly still says so per field (`confusion: none`), and `change: none` is a claim you sign. The close prints the finished `FEEDBACK:` line; paste it as the 7th line of the FINAL OUTPUT block. Every close appends a row to `~/.claude/state/command-feedback.jsonl`, which `python3 scripts/command_feedback_report.py` (hub) turns into the optimisation backlog.

**A "filed" claim MUST name a durable artifact — the mail id, or a COMMITTED path.**

**Then pass it: `done --command <name> --evidence "<proof>" --feedback "<the four fields>"`. The close REFUSES without it, and without the four fields.** The text is READ (`python3 scripts/enforcement/check_feedback_duty.py --digest`), so write a report to a human. A refused close leaves the record `running`, which the Stop hook blocks the turn on. ⚠️ **A `command_run.py` that predates `--feedback` ERRORS on the unknown argument instead of refusing** — that is a STALE VENDORED COPY, not an exemption (sync-excluded repos such as fabrik-lib). Do NOT drop the verdict: close with `--evidence` so the record does not stay `running`, **state your `FEEDBACK:` line in the response**, and file the stale-copy fact upstream.

⚠️ **The class: a subcommand or flag this corpus names that your local `command_run.py` REJECTS is a stale copy, never a licence to skip the step** (`dispatch`, `round --seats`, `--confirmed`). So DO the step's work and state its number in the response (the seats you dispatched, the CONFIRMED count that closed the round), close with what the parser accepts, and file the stale-copy fact. Say the two consequences out loud while it lasts: seats you cannot stamp are INVISIBLE to `dispatch_headroom.py`, so size down and name the gap; a round you cannot close with `--confirmed` cannot record D-206's exit counter, so the convergence verdict lives in your prose and the `--findings 0` rule still binds it.

**"none" is valid ONLY with its surfaces named — a BARE "none" is REFUSED by the parser (D-036).** Write `none — surfaces exercised: <what your run actually touched of the machinery>`. This step is MANDATORY on every run of every command — the record stays `running` (and the Stop hook blocks the turn) until a substantive verdict lands.

### File it when this run hit any of these

- a command's instruction that was wrong, stale, impossible, or contradicted another command
- an enforcement check that fired on a legitimate pattern (false positive) or stayed silent on a real one (false negative)
- a rule pack that contradicted another pack, or never activated where it was needed
- a script, hook, or scaffold emission that did not behave as its own docs describe
- friction that cost you real time: an ambiguous step, a missing arg, an undocumented prerequisite
- anything you had to WORK AROUND to finish. A workaround is allowed; an unreported workaround is not
- ⚠️ **a later pass, a stronger method, or the operator's re-ask caught something a CONVERGED pass of the same command had already stamped.** The false claim was yours; the no-op stamps that SURVIVED it are the machinery's, and that half is always filed.
- **you misread the same tool's output more than once in a session** (a `| head`-truncated pipe, a silently-failing compound grep): file it with the exact pipeline that misled you

### Route by BEAT, never by convenience (charters: `docs/reference/agents/`)

| To | Owns |
|---|---|
| **infra** | rendering, sync and checks of `commands/` and `.windsurf/rules/`, `scripts/enforcement/`, `.claude/hooks/`, the box mesh, fabrik-mail |
| **fleet** | `specs/services/*.yaml`, deploy/VPS/monitoring, scaffolding, `docs/PROJECT_CATALOG.md` |
| **intel** | models, benchmarks, the flywheel, author-blind review |
| **kaizen** | FEEDBACK verdicts, a command's or rule's WORDING (the hub's `commands/_sources/`, `commands/_fragments/` and `.windsurf/rules/`, per `/opt/fabrik/.fabrik/beat-owners.json`), ways of working — the feedback loop (not the code behind it) |

```bash
python scripts/mail.py send --to fabrik --to-agent <infra|fleet|intel|kaizen> --kind finding --ack required
# body on stdin — the D-035 contract (docs/reference/fabrik-mail.md § The message contract):
# WHAT/WHERE/WHEN/WHO/WHY(factual root cause)/HOW/SYSTEMIC(the class) mandatory;
# ABDUCTIVE (alternatives ruled out) when WHY is inferred; INDUCTIVE/DEDUCTIVE/COUNTERFACTUAL where they carry weight
```

Unsure who owns it ⇒ `--broadcast --ack no`. **In a PROJECT repo**, a defect in a SYNCED file additionally follows `/fabrik-upstream` — never edit the synced copy.

### A subagent's finding is YOURS to file

Subagents are ephemeral and cannot mail. So: when you adjudicate subagent output, findings about the MACHINERY (not about the code under review) come to you, and you file them under the routing above, or they are gone.

**The bar is evidence, not a complaint:** one reproducible `path:line` and the command you ran. **Fixing your ARTIFACT never discharges the duty:** correcting the false claim heals YOUR run, the mail heals the COMMAND that let it survive — both are owed, always. Only fixing the MACHINERY itself (a hub agent, in-beat, same run — say so in the FEEDBACK line) replaces the mail. A "none" verdict asserts all of the above triggers came up empty — it is a claim, and you are signing it.
