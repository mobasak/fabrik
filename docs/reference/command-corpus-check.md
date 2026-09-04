# Command-corpus integrity check

**What it is:** the gate check that keeps the `/fabrik-*` command corpus honest — every
reference a command makes must point at something that exists. Tool:
`scripts/enforcement/check_command_corpus.py` · Gate row: *Command Corpus (references
resolve — BLOCKING)*, Tier 2 · Tests: `tests/test_check_command_corpus.py`.

## Why it exists

The corpus is the instruction set every agent on this box runs on. When a command names
something that no longer exists, **nothing fails loudly**: the agent follows the
instruction, gets a degraded result, and reports success. It is the same failure shape as
a gate check that asserts nothing — a green signal with no substance behind it.

The founding case, found by the 2026-08-16 corpus audit:

```
fanout("research", …, web_tools=["exa","brave","firecrawl","context7"])
```

Those are **provider** names. `libs/subagents/web_tools.py::WEB_TOOL_NAMES` accepts only
**tool** names, and `loop.py` filters advertised schemas by that set — an unknown name
yields an empty list, whereupon `merged.pop("tools")` runs the agent with **no tools at
all**. Four commands (`/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-after-chat`,
`/fabrik-plan-review`) dispatched their "live search" grounders that way. The grounders
returned confident prose, the results table looked normal, and every spec and plan
grounded that way was ungrounded. No gate, test, or review caught it while the text stood.

## What it proves

Eight mechanically decidable facts — no judgement, no network:

| # | Check | Caught live |
|---|---|---|
| 1 | `web_tools=[...]` names only tools in `WEB_TOOL_NAMES` (imported live, never copied) | 4 commands, the founding case |
| 2 | Every `/fabrik-x` · `/design-review` chain reference resolves to a real source | — |
| 3 | Every `scripts/**.py` a command tells an agent to run exists | — |
| 4 | `Co-Authored-By:` in commit templates matches CLAUDE.md's canonical trailer | 6 templates naming a retired model |
| 5 | Every command opens a run record (shared fragment or a bespoke `start` block) | 24 of 27 opened none |

Predicates **6** (agent definitions), **7** (runnable close) and **8** (caller claims) were added later
and each has its own section below.

BLOCKING, because each is true/false with no tolerance band — and each was found violated
in a corpus that looked healthy.

## The orchestrator corpus (added 2026-08-16)

The Traycer workflow commands (`fab-mega-*`, `fab-ettw-*`) keep their canonical bodies under
`docs/orchestrator/**` — outside `commands/_sources/` — which is exactly how the whole set
escaped this audit: none of their docs was among the audited files, zero of the four mega
wrappers opened a run record, and a dead `scripts/` reference sat in three mega docs, all while
the check reported "all sound".

The audit now also walks `docs/orchestrator/_traycer-skills/*/SKILL.md` (hub-only; silently N/A
in projects) and, per wrapper:

- resolves the canonical doc the wrapper names and runs predicates 1–4 over it;
- requires a wrapper that **names no doc**, or names a **missing** one, to fail — a wrapper
  aiming agents at nothing is the founding failure shape;
- requires `command_run.py start` in **every** wrapper — no banner condition. The first
  version required it only of GENERATED wrappers, which meant deleting the banner line
  exempted a wrapper from the one thing the predicate proves (reproduced 2026-08-18). The
  whole set (4 mega + 13 ettw) is generated from `ORCH_SOURCES` now, so the honest rule has
  no carve-out; a new hand-written wrapper fails until added to the table, which is the fix.
- refuses a wrapper whose doc pointer escapes `docs/orchestrator/` (path traversal via `..`),
  and — in the hub (assembler present) — flags a missing `_traycer-skills/` tree instead of
  going silently N/A.

Scripts referenced by the **orchestrator docs** resolve against the hub root **or**
`templates/**` (files only — a directory named like a script is not a delivery): those docs
tell agents working *in a project* to run scripts the scaffold delivers (e.g.
`scripts/validate_i18n.py` from `templates/i18n-kit/`), and hub-rooting alone called five live
references dead. The fallback is **scoped to orchestrator docs** — a hub COMMAND source's
`scripts/` reference stays hub-rooted, or a genuinely deleted hub script whose name survives
in a scaffold template would read as alive.

The section runs only **behind the hub gate** (a non-empty command corpus): the first version
audited orchestrator docs before that branch, so a project-shaped tree carrying
`_traycer-skills/` reached the `libs.subagents` import and crashed a BLOCKING gate with a
ModuleNotFoundError, plus 28 bogus chain-ref failures against an empty command set —
reproduced 2026-08-18, fixed the same day.

**The hub/project split for the web-tool module (2026-09-03, review rows DU1 → DY1 → EA1):**
`_live_web_tool_names` never lets an import failure escape as a traceback; what the failure
MEANS is the caller's decision. In a project there is no command corpus, so `audit()` returns
before this branch (nothing prints under `--quiet`; bare, the `all sound across 0 file(s)` line) —
the skip advisory `⚠ predicate skipped — …` is a HUB verdict for a module that is absent. In the hub
(the assembler exists) a `libs/subagents/web_tools.py` that is present but unusable — a raise
inside it, a renamed or EMPTY `WEB_TOOL_NAMES` after a vendor sync — is a **blocking problem**
(`present but unusable (<Exc>) — fix the module, do not skip`): the round that guarded the
import first turned that into a green whose advisory `--json` never showed. The import runs the
whole `libs.subagents` package graph, so a failure raised in a SIBLING file (a peer session's
half-saved `agent.py` on the shared tree) is attributed to that file and stays an advisory —
it is not this check's surface and must not red every session's gate under `web_tools.py`'s
name. Flags: `--quiet` suppresses only the clean-path ✓ denominator line (the gate passes it,
as it does for the sibling Script Coupling Header row, so a green row never carries a
content-free line fleet-wide); the ⚠ lines always print on both exits — first on the passing exit
(the `--json` `warnings` array admits only ⚠-first output), after the `✗` block on the failing one.
The target's OWN health is asked of the file before the import — one read and one `compile()` —
so a NUL-corrupted, unreadable, directory-shaped, dangling-symlinked or syntactically broken
`web_tools.py` — or one whose parent directory cannot be read — is a hub problem with certainty,
never a verdict inferred from a traceback (certainty about the SOURCE's health; the names the
predicate then uses come from the import, so a bytecode cache whose header still matches a
same-second, same-size rewrite is the measured residual — 0 today). An import that fails is attributed by what CPython DID, not by a model of it: a
`sys.meta_path` recorder watches the import — which module CPython starts, which one is
EXECUTING when an exception is raised, which name it could not find — and the blame is the
module that was executing (the innermost record holding that very exception object; a failure
an importer swallowed is a different object and never counts). Five review rounds of an
AST-derived import closure each found a new way a module CPython never loads could steal the
target's blame (a submodule the package `__init__` binds, a conditional branch, a `try` body a
handler swallows, a sourceless package, a `__getattr__` package); the recorder makes every one
moot by construction. It records `create_module` as well as `exec_module` — an extension
module's init function runs in the former, and a mis-built `.so` had blamed its importer. The
target itself raising ⇒ a block; a sibling raising ⇒ an advisory naming the sibling; an
exception that leaves the import STATEMENT after the target FINISHED executing — it is in
`sys.modules`; CPython drops a module whose exec raised — is the target's own (a PEP 562
module-level `__getattr__` raising anything but `AttributeError`; the first guard asked whether
nothing anywhere had failed or gone missing, which the live closure's swallowed optional imports
made permanently false) — a blank blame there was a
fail-open advisory with predicate 1 silently not run; a torn or non-code bytecode cache is named
with its remedy (delete that module's `__pycache__`; a sourceless `.pyc` is the artifact to
replace) when CPython's own validators say it would have LOADED that cache — a healthy sourceless
module that merely raises is reported as its own failure, never as a cache; a name CPython could not find is the importer's own defect when
the name is ours (a typo'd package root, a submodule that does not exist — or a directory or
dangling symlink AT that path, which is then the broken module), and an advisory naming the
importer and the missing DISTRIBUTION otherwise (asked by the full dotted name under a namespace
root such as `google.`, so `google.protobuf` missing is not masked by the present root); a
renamed constant (`cannot import name`, raised by this check's own import statement) is the
target's. CPython stops at the first broken module, so exactly one is named; fixing it may reveal
the next — the recorder never guesses beyond what ran. A runtime `OSError` (a data file the
module opens) is the module's own. A `sys.exit()` at import is the module's failure, never this
process's exit code; `KeyboardInterrupt` propagates. The import runs inside the gate's process:
both its streams are captured at the file-descriptor level ONLY (an `os.write(1, …)` or a
stderr banner had led the gate row; a Python-level StringIO layer made a module's legitimate
`sys.stderr.buffer` / `.fileno()` raise inside the module), every resource is acquired inside the
`try` and released in order, the recorder's loader wrappers are unwound after the probe (they had
stayed on every loaded module's `__spec__.loader` for the life of the process), its stack is per
thread, and any bytes written are reported as a `⚠ advisory —` line, distinct
from a skipped predicate (the audit ran; a chatty module is not incomplete coverage), and the
package's `.env` autoload is switched off so the gate never loads the CWD's secrets. Every failure text is bounded (500 chars), safe when
`str(exc)` itself raises, and scrubbed of the repo prefix and of the operator's home (`~/…`)
before it is printed.

**The important negative:** path-shaped look-alikes are *not* chain references.
`/opt/fabrik-lib`, `/run/fabrik-autoheal/pause` and `docs/reference/fabrik-mail.md` all
contain a `fabrik-<word>` token. A naive matcher reports four broken chains that were
never broken, and a check that cries wolf gets ignored — which is how a real break then
ships. The boundary lookarounds in `_CHAIN_RE` encode this, and
`test_path_lookalikes_are_not_chain_references` locks it.

### Predicate 5 in detail — why coverage was the whole problem

`CLAUDE.md` makes opening a run record the first act of any `/fabrik-*` invocation, and the Stop
hook's fifth cause refuses to end a turn while a record says `running`. That machinery existed and
was wired into **3 of 27** commands. For the other 24 the pinned `RUN:` line, the class ledger, the
non-convergence detector and the hook were all disarmed — which is precisely the "agents stop
without finishing the command" complaint the record was built to answer.

The fix is a shared `{{include:run-record}}` fragment whose two values — the command's name and its
phase count — are **computed at render time** by `assemble_commands.py::_phase_count`, never
hand-written per command. Hand-authored parameters for 24 commands would drift the moment a phase
was added, and a wrong phase count makes the pinned line lie about where the run is. `_phase_count`
trusts explicit `## Phase N` headings only once there are at least two of them: `/fabrik-release`
declares a lone `Phase 0` and then branches into VPS/MOBILE/STORE sections, so the literal count
would claim the run was finished with most of it still ahead.

**A module that leaves a stream DEAD no longer takes the verdict down.** A bare `sys.stdout.detach()`,
a dunder-only rebind, `close()`, `buffer.detach()` — round 66 restored those as the binding and the
gate's own verdict `print` raised (exit 120, no output). The probe now rebuilds a fresh wrapper over
the restored fd and says so: `⚠ advisory — web-tool names: a module left the process's stdout unusable
at import — the verdict prints through a fresh wrapper over the restored fd`. A stream the CALLER
launched closed (`>&-`) is left closed — nothing to rebuild (round 68).

**Predicate 7's comment rule.** A trailing shell comment is cut from a FENCED close only, and a `#`
starts one only outside quotes and at column 0 or after whitespace, `;`, `|`, `&`, `(`, `)`, `<`, `>`.
A `\` escapes the next character outside single quotes (`$'it\'s'` is one word), and a line continues
only on an ODD trailing run of backslashes.

## Predicate 6 — agent definitions (added 2026-08-27)

The four subagent definitions lived ONLY in `~/.claude/agents/`: hand-authored, box-local, absent from git, owned by no generator, and outside this audit. So the check vouched for 31 commands and 31 skills while the agents those commands **dispatch** were unreviewable — the same shape as the orchestrator-corpus blind spot above, one layer down.

They are now generated from `commands/_agents/*.md` by `assemble_commands.py` (with `--check` drift detection and banner-scoped orphan pruning), and predicate 6 requires of each: frontmatter present, a `name:` that MATCHES the filename (a mismatch registers an agent nobody can dispatch by either), and a `description:` (the dispatcher selects on it, so an agent without one is invisible to model-native routing).

HUB-ONLY, like every other predicate here: a project has no `_agents/` dir and stays silent.

## Predicate 7 — an advertised close must be a RUNNABLE close (added 2026-08-28)

`scripts/command_run.py done|blocked|handoff` REFUSES without `--feedback`. Every place the corpus
PRINTS that command is in-product documentation an agent copies verbatim — so a printed close missing
the flag instructs a command the tool then refuses, leaving the record `running` and the Stop hook
holding the turn open. That is the worst shape a fail-closed change can take: the machinery tells you
the way out, and the way out does not work.

Measured the day the refusal landed: **36 such sites** — `commands/_fragments/run-record.md`, the 17
orchestrator wrappers GENERATED from it, and the Stop hook's own remedy. The hand fix reached 2 of
them; only a mechanical sweep found the rest, which is precisely why this is a predicate and not a
review note.

The window is the close's OWN text: it starts at the close command and is cut at the span's
closing backtick on the same line (prose or a neighbouring table cell after it never counts); an
inline-code span left open on the close line runs to the line that closes it (cut there), a `\`
continuation runs while lines end in `\` (up to twelve lines), and it stops at the next close
command. Predicate 7 audits the 17 generated orchestrator wrappers too — they carry 34 of the
corpus's 47 close sites and were read into the coverage denominator but audited by no predicate
until pass 63. The first version used a flat
4-line window, which admitted the PROSE that documents the flag ("`--feedback` is REQUIRED")
and a neighbouring close's flag — 21 of 47 live close sites, the run-record fragment first,
passed with their own flag deleted (pass 62). A single-line window would flag every
correctly-fixed site, since the real fragment wraps the flag onto a continuation line. Every close
on a line is graded (the next close bounds the window); a backtick inside an ARGUMENT of a fenced or
plain-prose close is the command's own text — only a span's closer cuts (a fenced `--evidence` with
backticks was a blocking false positive one edit away); a fenced close's trailing `#` comment is not
the command — but a `#` inside a QUOTED argument is (`--evidence "PR #42 merged"`); a span left
unclosed within twelve lines grades the close on its own line (round 64). Fences are tracked by ONE
CommonMark rule (`_fence_step`) on the claim side, the honour side and predicate 7 alike — a bare
toggle let a nested or info-string fence invert the state for the rest of a file (round 65).

Predicate 5 (the run record) matches `command_run.py` … `start` across whitespace and a `\`
line continuation — a wrapped start opens a record too, and the bare substring test had red it; an
HTML-commented `start` is illustration and `start-run` is not `start`, while a FENCED start stays
legitimate (3 of 33 live sources write their bespoke start block fenced — measured before the
fence exclusion was rejected).
Chain references admit digits anywhere after the prefix (`/fabrik-oauth2-setup`, `/fabrik-2fa`);
a caller claim inside a fenced block is an example, like a fenced `#` in the call-sites form —
fences are real CommonMark fences (`~~~` too, closed only by a same-char run at least as long) and a
heading may carry up to three leading spaces; a claim is honoured by a TOKEN in the caller's
UNFENCED, comment-stripped source, never a substring (`/fabrik-review-scoped` contains `/fabrik-review`); the trailer key is
read case-insensitively, as git reads it; an agent's `name:` may be quoted, spaced before its colon (`name : x`) or followed by a comment (a `#`
inside the quotes is part of the name; a TAB before `#` is a comment), an unclosed frontmatter is
refused rather than read as the whole file, and a BOM is not "no frontmatter"; a `web_tools` literal checked only to its 2 000-char bound says so.

## Predicate 8 — a CLAIMED caller must actually CALL (added 2026-08-29)

`/fabrik-generate-tests` advertised itself as *"auto-called by … `/fabrik-review` reactively"* while
`fabrik-review.md` carried **zero** references to it. Two harms, and the second is the one that matters:
the reader is told a call happens that never does, and the false name was CONCEALING why — `/fabrik-review`
had reproduced the command's entire five-step pipeline inline, so one contract was being maintained in two
files and a fix to the canonical one could never reach the other. Nothing in this check noticed either half.
It surfaced only because the operator asked, in passing, which command was calling it.

**What counts as a claim** — surveyed from the corpus, not guessed. Two forms:

- a verb of invocation: `auto-called by /fabrik-x`, `invoked by`, `dispatched by`, `cited by`, `fired from`
- a section headed `## Where this auto-fires (N call sites)` — every `/fabrik-x` in it, until the next
  heading at the same or a higher level closes the section (fenced blocks are skipped, so a `#` shell
  comment inside the section cannot silently end it). The heading match is **`call site(s)` or
  `auto-fires` only**: a looser draft also caught `## Where this runs`, which in `/fabrik-deploy-plan`
  and its review is about which REPO you run the command from — not who calls it.

**What does NOT count, deliberately.** A bare cross-reference asserts nothing: successor pointers, `SKIP:`
routes and "see also" name other commands constantly. Measured across the live corpus (33 sources; `_CHAIN_RE` over `_unfenced` text, resolving, non-self —
re-derived with the shipped module in pass 65): **498** such mentions, **35.9%** (179) with no
back-reference, over 188 unique (source, name) pairs of which 92 have no back-reference (the first sentence read as if 92 were the pair total, F66-5). Grading those would put 179 findings on the board the
day it landed and teach every reader to skip this check's output — so the predicate reads only the claim
forms, of which the corpus makes **3** (all in `fabrik-generate-tests.md`). Small denominator, zero
noise, and it caught the one that was false.

⚠️ **Every number above is derived with the SHIPPED `_CHAIN_RE` + `_claimed_callers`.** The first
version of this section quoted 439 / 17.5% / 77 / 5 from a throwaway prototype whose regex differed
from the one that shipped — measured facts about code nobody would ever run. The review of this
predicate caught it. Re-derive against the module; never re-quote a prototype.

The direction matters: only a claim of BEING CALLED is checkable, because only it asserts something about
a file other than its own. Proven red against the pre-fix corpus at `1a1efac8^` and silent at HEAD.

**When it fires, look for a copy.** The wrong label is the cheap half; a command that names another as its
caller when it does not call it is often a command that CONTAINS it instead. The fix is both halves —
correct the claim, then extract the shared contract into `commands/_fragments/` so both render the same
bytes. A "keep these in step" comment is a contract with no grader.

## Anti-vacuity

`--selftest` is hermetic: its canary and good-fixture audits pass their own (empty) agent
directory, never the live `commands/_agents/` — a real defect there once read as "FALSE POSITIVE
on known-good input". It feeds a known-bad corpus through the same predicates and requires **each** to
fire, then a known-good one and requires silence. The `N of M problem emitters … executed` figure is
MEASURED: the selftest traces itself and counts the `problems.append(` lines its canaries actually
reached, against every such line in the file (a signature count had credited two signatures to one
emitter and none to an unexercised one):

```console
$ python3 scripts/enforcement/check_command_corpus.py --selftest
✓ selftest: 17 canaries over 8 of the eight predicates (12 of 18 problem emitters in this file executed) fire on bad input and stay silent on good input
```

In a PROJECT (the script is synced fleet-wide, the vendored `libs/subagents/web_tools.py` is
not — ABSENT, never present-but-broken: a hub whose module raises keeps all six and fails
loudly) the six web-tool canaries are not applicable and say so; a project whose `CLAUDE.md`
carries no `Co-Authored-By` example likewise marks the trailer canary N/A. A hub whose module is
present but BROKEN prints the failure first (`⚠ predicate 1 cannot run: …`) so the VACUOUS lines
that follow are read as the module's fault, not the check's; the known-good fixture takes its tool
names from the live set and cites only files every tree has — one `N/A: 6 web-tool canaries
skipped …` line, exit 0 — instead of six `VACUOUS` lines and exit 1:

```
$ python3 scripts/enforcement/check_command_corpus.py --selftest
N/A: 6 web-tool canaries skipped — no vendored libs/subagents/web_tools.py under this repo (a project); predicate 1 runs in the hub
✓ selftest: 11 canaries over 7 of the eight predicates (11 of 18 problem emitters in this file executed) fire on bad input and stay silent on good input (N/A: web-tool names)
```

It was also proven **discriminating on the real defect**: reverting the `web_tools` fix in
a throwaway copy of the corpus turns the check red with the exact provider names named.

Both properties matter. A check that cannot fail is not a check, and a check that only
fails on synthetic fixtures has not been shown to catch the thing it was built for. See
`docs/workstation/liveness.md` for the general three-proof discipline this follows.

## Citation style it enforces by example

Two classes of citation rot were fixed alongside it and should not be reintroduced:

- **Never cite `CHANGELOG.md:<line>`.** The file is prepend-ordered, so a line number is
  wrong by the next entry. Eight citations in `/fabrik-decommission` had drifted ~2 700
  lines, pointing at unrelated text inside a *destructive* runbook. Cite the dated entry
  title instead.
- **Prefer a section anchor to a line range** when citing another command; two
  `/fabrik-deploy-verify` self-citations had slid three lines.

## Related

- `docs/reference/ticket-breadth.md` — the sibling advisory check on plan sets
- `docs/workstation/liveness.md` — heartbeat / vacuity-canary / doc-claim-binding proofs
- `.windsurf/rules/core/62-using-subagents.md` — the canonical `web_tools` recipe
