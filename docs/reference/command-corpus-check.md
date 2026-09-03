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
same-second, same-size rewrite is the measured residual — 0 today). A failure whose last real
frame is the checker itself (a corrupt bytecode cache: EOFError inside frozen importlib) is the
target's too — the only import in the checker is the target's. A failure the file did not cause
is attributed to the file it was raised in: an `ImportError` at the import site by `exc.path` (a
renamed constant names the target; a broken sibling's import names the sibling); any exception
whose `filename` names a real `.py` by that (a compile-time SyntaxError in a sibling strips the
import frames; a PermissionError carries the file it could not open — a DATA file the module
opened is the module's own failure and stays with the frame); everything else by the last
traceback frame (a runtime SyntaxError from `compile()` of a string says `<string>` and keeps its
frames). The hub decision compares file IDENTITY with `libs/subagents/web_tools.py` — never a name
suffix (`libs/web_tools.py` is a separate module). The constant must be a non-empty collection of
non-empty `str` — any real collection, `dict` keys included; a bare str or bytes, `None`, a
generator or a non-str member is the same hub problem, named by shape. A failure raised outside
the repo is named by file (with its package for an `__init__.py`), never by absolute path; an
in-repo file behind a symlinked `libs/` still reads repo-relative; a pseudo path (`<frozen …>`)
is never rendered as a repo file, whatever the cwd.

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

The window is **4 lines**, because the real fragment wraps the flag onto a continuation line — a
single-line window would flag every correctly-fixed site.

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
routes and "see also" name other commands constantly. Measured across the live corpus: **460** such
mentions, **17.8%** of them with no back-reference. Grading those would put 82 findings on the board the
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

`--selftest` feeds a known-bad corpus through the same predicates and requires **each** to
fire, then a known-good one and requires silence:

```console
$ python3 scripts/enforcement/check_command_corpus.py --selftest
✓ selftest: 13 canaries over the eight predicates fire on bad input and stay silent on good input
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
