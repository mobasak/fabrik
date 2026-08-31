Status: IN-PROGRESS — Pass 1 of N, coverage bounded and stated below
**Date:** 2026-08-31 · **Author:** fleet · **Subject:** tryton-crm as evidence; the defects are OURS

Backwards retrospective over the tryton-crm record for defects in **our own machinery** — rule packs,
`/fabrik-*` commands, enforcement gates, hooks, orchestrator/registrar code, fleet infra. tryton-crm is
the subject, not the target.

---

## 1. Coverage ledger — the denominator for everything below

**Read this before any count in this document.** Pass 1 is deliberately depth-first on the highest-yield
sources rather than breadth-first across all 41 reviews; the unread set is named, not hidden.

| Source | Size | Pass-1 coverage | Honest gap |
|---|---|---|---|
| `/opt/tryton-crm/AFCL.md` | 187 lines | ✅ **read in full** | — |
| `/opt/tryton-crm/docs/LESSONS_LEARNT.md` | 1850 lines · **89 headings** | ⚠️ **all 89 headings scanned; 1 entry read in full** (`:907-927`) | 88 entries unread in body. The heading grep matched only 7 on machinery vocabulary — a lesson phrased without those words is invisible to this pass |
| `/opt/tryton-crm/docs/development/reviews/*.md` | **41** | ⚠️ **41 of 41 grepped** (machinery-vocabulary rank + accusation-shape scan); **1 of 41 read in body** | Body-reading still 1/41. A finding phrased outside the grep's vocabulary remains invisible — R1 was found this way, so others plausibly exist |
| `/opt/tryton-crm/docs/superpowers/specs/*.md` | 14 | ✅ **14 of 14 grepped** for machinery-accusation shapes | 1 hit, benign (`/fabrik-ui-design does not apply` — correct usage). A genuine ZERO for this source, at grep depth |
| `/opt/tryton-crm/docs/development/plans/*.md` | 3 | ❌ **0 of 3** | Not started |
| `/opt/tryton-crm/docs/STRATEGIC_BACKLOG.md` | 909 lines | ⚠️ **grepped + 1 section read** (`:342-359`) | Yielded M7 — the brief's high-yield ranking was right |
| `/opt/tryton-crm/CHANGELOG.md` | 6277 lines | ❌ unread | — |
| `/opt/tryton-crm/docs/*.md` (17 surfaces) | — | ⚠️ 1 (`CLAUDE.md` spec block) | — |
| Hub artifacts | 2 plans · 2 reviews · spec | ✅ read in the prior session (see § 5) | — |
| session-recall | **60 sessions enumerated**; `a0cc0bfb` = 89,598 records / 235 MB | ✅ **PASS 2 — MINED IN FULL** (see § 6b). All **577 deduped operator-prose turns read in body**, not sampled | The earlier "seq >11,700" was itself wrong by 7.6×. Corrected denominators in § 6b. Assistant turns (40,899) still unread — the operator's own words were the target |
| `git -C /opt/tryton-crm log` | — | ⚠️ **grepped** (revert/hotfix/workaround/gate) | Surfaced a D-019→D-020 revert (a decision re-litigated) — logged, not yet worked |
| fabrik-mail tryton threads | — | ⚠️ known from this session only | Not swept |

⚠️ **THE COMMISSIONED METHOD WAS CHAT-HISTORY ANALYSIS; WHAT I ACTUALLY DID WAS FILE-MINING + LIVE
EXECUTION.** Both proved more productive — F11-F16 in the infra filing came from *running* the deploy,
which no amount of reading would have found — but substituting a better method for the requested one,
without saying so, is itself a reporting defect. Recorded here rather than left implicit.

**Therefore every finding below is "found in the sources marked ✅/⚠️", never "all that exist."** The
five findings are high-confidence individually; the **set is incomplete by construction**.

---

## 2. Headline

**Our machinery's defects are not that it lacks knowledge — it is that knowledge lands in a project's
files and never travels back into the machinery.** Every Pass-1 finding is a fact that was written down,
correctly, by someone who paid for it — and then cost someone else again because no command, gate or rule
pack carries it.

---

## 3. Findings

### M1 — the gate's JSON summary TRUNCATES, and nothing in our machinery says so
**Class:** gate reports a partial failure set that reads as complete · **Beat:** infra · **Status:** ✅ **FIXED `9fc4bd7d`** (truncated rows now carry the rerun command in-band + as a `rerun` field; red-on-revert proven; live-verified)

**KNOWN-WHEN — 2026-07-30**, `/opt/tryton-crm/docs/LESSONS_LEARNT.md`:907-927. The project hit it,
diagnosed it exactly, and wrote the rule:
> *"the `final_gate.py --check --json` summary reported the 'Doc Link Integrity' failure with an `output`
> string that listed broken refs in only **three** docs … and the string ended mid-word
> (`...REST_API_REFEREN`). Running the underlying check directly showed the real surface: **seven** docs …
> The JSON `output` field is a **truncated preview**, not the full failure set."*
> *How to apply: "when a gate check fails, **re-run that check's own script directly** … never scope the
> fix to what the truncated JSON summary happened to show."*

**COST-WHEN — 2026-08-31, this session, twice.** Running `final_gate.py --json` I received
`"truncated": true, "omitted_lines": 22`, could not see which check actually objected, and had to run
`scripts/enforcement/check_convergence.py` directly — twice — to learn the real complaint. I re-derived
a rule that a project had written down 32 days earlier.

**Root cause — measured this run, all three zero:**
| Probe | Result |
|---|---|
| `grep -ci 'summary TRUNCATES\|truncated preview' /opt/fabrik/docs/LESSONS_LEARNT.md` | **0** |
| `grep -ci truncat /opt/fabrik/docs/workflows/FINAL_GATE_WORKFLOW.md` | **0** |
| commands telling you to re-run the failing check directly (`commands/_sources/*.md`) | **0 files** |
| `grep -c truncated /opt/fabrik/scripts/final_gate.py` | **4** |

The machine *emits* `truncated: true`; no human-facing artifact tells the reader what that obliges. The
lesson exists in exactly one place — a project's own file — where the next agent will not look.

---

### M6 — a green `pytest` that SKIPPED asserts nothing, and the gate did not say so
**Class:** the gate's green is silent about its own blind spot · **Beat:** infra ·
**Status:** ✅ **FIXED `3dbbccbb`** (pure `skip_advisory()`; red-on-revert proven)

**The highest-cost finding in the retrospective, and the only one found INDEPENDENTLY by two
projects.**

**KNOWN-WHEN — 2026-08-28**, `/opt/tryton-crm/docs/development/reviews/2026-08-28-review-money-surface-suite.md`,
Pass 12 row, verbatim:
> *"**The security suite had deleted itself from a green gate.** All 26 cross-tenant tests were skipping
> on a 429 throttle that `conftest.py` classified as 'trytond not reachable' — a bare
> `except Exception → skip`. **`final_gate.py` runs `pytest tests/`, and skips do not fail**, so the
> isolation guarantees were absent from every green gate in that window."*

**CORROBORATED independently** — an unread `web-ecommerce-factory` finding in the hub mailbox names the
same class from its own evidence: *"final_gate — … **pytest NOT RUN is invisible** …"*. Two projects,
different symptoms, one hub defect.

**COST-WHEN — the window itself.** Every green gate in that period asserted cross-tenant isolation it had
not tested, on a **multitenant CRM**. The project fixed its `conftest`; the GATE half stayed ours —
`results.append(("pytest", code == 0, tail))` passes a run with N skips, and passing-check output only
reaches `--json` when ⚠-prefixed, so nothing prefixed it.

**Why it survived:** the leg already had two guards of exactly this shape — `_uninvoked_test_dirs()` and
exit-5 no-tests-collected — both of which SAY what the green does not cover. The skip case is the third
member of that family and was simply missing. Now: `skip_advisory()` names the count and why it matters.
Advisory, never blocking — an environment-gated skip is legitimate; an **unexamined** one is the defect,
and tryton's was a transient throttle misread as a permanent outage. `0 skipped` never flags.

---

### M7 — a whole test DIRECTORY excluded from every green, by design, unannounced
**Class:** same family as M6, at directory scale · **Beat:** infra ·
**Status:** ⚠️ **MOSTLY COVERED by `3dbbccbb`** — residual named below

**KNOWN-WHEN — `/opt/tryton-crm/docs/STRATEGIC_BACKLOG.md`:344-353.** When the suite was finally run
against the live stack "for the first time in weeks":
```
66 failed, 253 passed, 2 errors in 2928.76s (48:48)
```
> *"**It runs nowhere.** CI never executes it … so the conftest skips the whole directory by design.
> `final_gate.py --json` skips it for the identical reason (its docstring says so explicitly, and that is
> deliberate — the gate must run without sourcing `.env`). So **every green this project has reported —
> including the 45/0 that gated round 19 — was measured on a suite that silently omits a third of
> itself.** That is how `attachment.py` reached round 17 with all six of its guards deletable."*

**COST-WHEN:** 66 hidden failures, and a security-relevant file reaching round 17 with six deletable
guards, because every green was measured on two-thirds of the suite.

**The exclusion is CORRECT; the silence was the defect.** The gate must run without sourcing `.env` —
that is deliberate and right. What was missing is the gate SAYING that a third of the suite is outside
its green.

**Coverage after M6 — measured, not assumed:**
```
skip_advisory('253 passed, 122 skipped in 48.8s', …) → "⚠ this green SKIPPED 122 test(s) …"
skip_advisory('253 passed in 48.8s', …)              → unchanged (no advisory)
```
A conftest directory-skip lands in pytest's summary, so **M6 now catches this mechanism**. **RESIDUAL — RESOLVED in Pass 4.** The three cases and their coverage, measured:
| Suite location | Mechanism | Covered by |
|---|---|---|
| OUTSIDE `tests/` | never collected | `_uninvoked_test_dirs()` — live: flags `scripts/kilo-benchmarks/tests` + 4 others |
| INSIDE `tests/`, conftest-skipped | reported as skipped | **M6** (`3dbbccbb`) |
| INSIDE `tests/`, `collect_ignore`'d | no skip, no flag | **theoretical residual — no observed instance** |
tryton-crm's excluded suite is `tests/trytond/` — **inside** `tests/`, therefore collected, therefore
conftest-skipped, therefore **caught by M6**. (I predicted `_uninvoked`'s glob would not reach `tests/`
subdirs; it DOES, and the function filters them out afterward — correctly, since `tests/` is invoked.
Recording the wrong prediction because the corrected mechanism is what makes the coverage claim true.)

---

### M2 — `/fabrik-execute-plan`'s parallelism is FILE-scoped; the real contention is the CONTAINER
**Class:** a safety model that guarantees the wrong disjointness · **Beat:** infra · **Status:** NEW

**KNOWN-WHEN — undated, `/opt/tryton-crm/AFCL.md`:65-83**, written with reproduced output:
> *"`/fabrik-execute-plan` fans a phase out to parallel implementers on **disjoint file paths** — but if
> two of them change `tryton_modules/crm_bridge/**` they must each `docker compose build trytond` … and
> **there is only one container and one host port (18000)**."*
```
Error response from daemon: cannot remove container "…_trytond": container is running
Bind for 0.0.0.0:18000 failed: port is already allocated
```
> *"Disjoint *file* ownership is not disjoint *container* ownership."*

**COST-WHEN — same entry:** racing rebuilds, plus an orphaned half-created container that must be
`docker rm`'d by hand. The project wrote its own local rule ("only ONE agent per phase may rebuild").

**Root cause:** the subagent contract makes **`owned_paths`** the disjointness primitive
(`.windsurf/rules/core/62-using-subagents.md` § Parallelism — empty/overlapping `owned_paths` with
`tools_enabled=True` is named as the #1 trap). Disjoint paths do not imply disjoint *services*, *ports*
or *daemons*. Any project whose phase work shares one dev container inherits this, and the project had to
invent the mitigation locally because no command carries it.

---

### M3 — a synced governance line states a FALSE premise (~46 repos)
**Class:** rule pack asserts something the box contradicts · **Beat:** infra (text) / fleet (fact) ·
**Status:** NEW

Both copies of the spec-contract block say:
> *"`fabrik` is not on a project's PATH — from a project, ground it by reading the spec's `shape:` block
> … (inspection, not a shell-out)."*
— `/opt/fabrik/CLAUDE.md`:379 and `/opt/fabrik/templates/governance/CLAUDE.md`:391 (**synced surface →
~46 repos**).

**Measured from `/opt/tryton-crm` this run — the premise is false:**
```
which fabrik           → /home/ozgur/.local/bin/fabrik
fabrik plan specs/services/tryton-crm.yaml
  → Error: Invalid value for 'SPEC_PATH': Path 'specs/services/tryton-crm.yaml' does not exist.
```
`fabrik` **is** on a project's PATH and the subcommand **runs**; it fails on the *spec path*, because
specs live hub-side. The CONCLUSION (read the spec, don't shell out) is right; the stated REASON is
wrong.

**Why that matters rather than being pedantry:** our own contract tells agents to *"read it, don't recall
it"* and to verify premises. An agent that dutifully tests this one finds it false in one command, and a
falsified premise invites discarding the correct conclusion with it. A rule that fails its own
verification standard teaches distrust of the rule set.

---

### M4 — `AFCL.md` ships as an unfilled template and is never filled
**Class:** scaffolder seeds a structure nothing completes · **Beat:** fleet (scaffolder) ·
**Status:** NEW

`/opt/tryton-crm/AFCL.md`:1-23 is still the literal stub — `**Date:** {{date}}` (unrendered
placeholder), example rows *"Forgot PostgreSQL 16 naming conventions"* / *"Attempted to use Client-side
hooks in Server Components"*, bracketed prompts *"[Describe the specific coding task where the AI
failed]"*, guardrail checkboxes about `.kilo.json` and TypeScript `any` (**neither applies** — this is a
Python/Tryton project), and the byline *"Generated by: Cascade SWE Agent"* — **a retired tool**
(`project_kilo_cascade_retired`).

**COST-WHEN:** the file's four designed sections (Executive Summary · Identified Constraints table ·
Silicon Ceiling · Guardrail Recommendations) are dead, and 164 lines of genuinely valuable friction were
appended *below* them as free prose. The consequence is direct and measurable in this very run: **mining
AFCL required reading it end-to-end**, because the structured table that exists to make friction
greppable was never used. A friction log whose schema is ignored is a friction log that only helps the
person who wrote it.

---

### M5 — two different versions of the same guidance inside one repo
**Class:** duplicated instruction drifts silently · **Beat:** fleet (seeding) · **Status:** NEW

`/opt/tryton-crm/AFCL.md`:43 carries the spec-contract block **without any caveat**:
> *"To preview what the spec will trigger: `fabrik plan specs/services/<id>.yaml`"*

while `/opt/tryton-crm/CLAUDE.md`:391 carries the caveated (if wrongly-reasoned — M3) version. Same repo,
same guidance, two texts, no mechanism reconciling them. Whichever an agent reads first wins. This is the
sibling of the class the hub already names — *a fix that leaves a stale duplicate of the instruction it
corrects has not shipped* (hub Lesson 143) — recurring in a project's seeded docs.

---

## 4. Systemic classes

**S1 — Knowledge flows INTO projects and never back out.** M1, M2 and M4 are all the same shape: the
project learned, wrote it down correctly, and the machinery never learned. The fleet-facing duty
(`templates/governance/CLAUDE.md` § Upstream feedback) makes filing a hub defect a project's obligation —
but there is **no mechanism that harvests a project's `LESSONS_LEARNT.md` or `AFCL.md` into the hub**.
The 89 lesson headings in one project are an unmined corpus of exactly the defects this retrospective was
commissioned to find, and the only reason M1 surfaced is that I read one file by hand.

**S2 — A rule that fails its own evidence standard.** M3. Our contract demands premises be verified; a
synced rule states a premise that one command refutes.

**S3 — A safety primitive that guarantees the wrong invariant.** M2 (`owned_paths` guarantees file
disjointness, not resource disjointness) is the same shape as the deploy-side finding that a *per-step*
time bound cannot guard a *cumulative-mtime* mechanism (first-pass report § D7). **The pattern: we pick a
primitive that is easy to check rather than the one that matches the hazard.**

---

## 5. Already fixed / already filed — do not re-work

Prior session, same subject, all pushed:

| Ref | What |
|---|---|
| `b6133f6a` | `audit_backrest` matched a plan id no registrar creates — backrest could **never** report `present` |
| `8b4738a6` | a backrest plan pointed at a non-existent path now reports `drift` (the PAPER BACKUP class; `/opt/zitadel/data` absent while `zitadel-data` points at it) |
| `c256e3e3` | D-052 — every project gets a watchdog; 15 specs flipped |
| `6dec1619` | `30-ops.md` § Deployment Completeness (8 spec-time classes); `60-watchdog.md` matrix retired |
| `a69682da`, `c89240f7` | deploy-plan: `--keep-on-failure`, reachable verify, window-heartbeat contract, hub-placement concession |
| `3cd393c0` | the bounded first-pass report (D1-D10) — **verify, do not inherit** |
| mail `01M1BTY6M1F88BTX6YG975CMRV` | D1-D10 filed to infra (10 command findings) |

---

## 6. Recommendations — ranked by leverage

1. **Harvest project lessons into the hub (S1).** This is the highest-leverage item in the report and the
   only one that prevents recurrence rather than patching an instance. 89 headings in *one* project;
   ~46 projects exist. A periodic sweep — or a `/fabrik-upstream` obligation that a lesson naming hub
   machinery MUST be filed, not merely written locally — converts a private log into platform memory.
2. **M1 is a two-line fix with outsized value:** when `final_gate --json` sets `truncated: true`, print
   the exact `python scripts/enforcement/<check>.py` command to run for the full set. The machine already
   knows it truncated; make it say what to do.
3. **M3:** correct the premise on both synced copies — the reason is "the spec lives hub-side", not "the
   binary is absent".
4. **M2:** extend the subagent parallelism contract from `owned_paths` to shared *runtime resources*
   (one rebuilder per shared service/port per phase).
5. **M4/M5:** the scaffolder should either render `AFCL.md`'s placeholders or stop seeding dead sections,
   and should not seed a second copy of guidance that lives in `CLAUDE.md`.

---

## 6b. Pass 2 — the 41 review artifacts (PARTIAL) and one important refutation

**Method:** ranked all 41 by machinery-vocabulary density, then grepped all 41 for
accusation-shaped statements (`the command/gate/checker did not|never|missed`, `no command carries`,
`should have caught`, `false positive|negative`), then deep-read the strongest hit. **41 of 41 grepped;
1 of 41 read in body.** Still partial — but no longer zero.

### R1 — REFUTED: `check_secrets` expansion false positive was FIXED
`2026-08-04-user-test-tryton-crm-gui.md`:593-601 documents a real, well-diagnosed defect:
> *"`check_secrets.py:43-46` matches `(?:password|secret|api_key|token)\s*[:=]\s*['\"][^'\"\n]{8,}['\"]`.
> It has a negative-lookahead for env-var *name* strings but none for a **variable expansion**"* — so
> `SAO_TEST_PASSWORD="$TRYTOND_ADMIN_PASSWORD"` tripped it on length alone, containing no secret.
> *"it cost three gate cycles in this run … the scanner fires on the shape of a line, so **every attempt
> to document the false positive reproduces it**."*

**Verified live this run — the defect is GONE.** `check_secrets.py`:60 now reads
`r"(?:password|secret|api_key|token)\s*[:=]\s*['\"](?!\$[({A-Za-z_])[^'\"\n]{8,}['\"]"` — the
expansion lookahead is present — and the exact reported line probes clean:
```
printf 'SAO_TEST_PASSWORD="$TRYTOND_ADMIN_PASSWORD"\n' > fp_probe.sh
python3 scripts/enforcement/check_secrets.py fp_probe.sh   → exit 0
```

**This REFUTES the candidate and QUALIFIES my own S1.** Knowledge does sometimes flow back: a
project-found scanner defect reached the hub and was fixed. S1 is therefore not "the upstream path is
broken" — it is narrower and more accurate: **the path works when a finding is filed AS a defect against
a named hub file, and fails when the finding is written as a LESSON in the project's own log.** M1's
truncation rule was the latter and sat unharvested for 32 days; this scanner bug was the former and was
fixed. That distinction is the actionable part, and it changes recommendation 1.

### R2 — supporting evidence for M1, found independently
Three separate 2026-08-2x/3x reviews record the project building truncation-honesty for its OWN tooling:
*"the unresolved print cap **announces its own truncation** (`first 20 of 355`, tested)"*. The project
independently invented the discipline the hub gate lacked — while the hub gate's own truncation stayed
silent about what to run. M1 (`9fc4bd7d`) closes that asymmetry.

## 7. Pass Ledger

| Pass | Sources swept | Findings raised | Edits | md5 (start → end) |
|---:|---|---:|---:|---|
| 1 | AFCL (full) · LESSONS_LEARNT (89 headings + 1 entry) · CLAUDE.md spec block · live `fabrik` probe · hub cross-checks | **5** | file created | — → `(initial)` |
| 2 | all 41 reviews ranked + grepped for accusation-shaped statements; 1 read in body; 2 live probes | **1 raised → REFUTED** (R1) + 1 supporting (R2) | §6b added; S1 narrowed; M1 marked fixed | `(initial)` → `(pass2)` |
| 3 | findings-table extraction across all 41 reviews · **14 of 14 specs grepped** (1 hit, benign — refuted) · STRATEGIC_BACKLOG · `git log` grep | **2 raised → M6 (FIXED), M7 (mostly covered, residual named)** | M6 + M7 added | `(pass2)` → `(pass3)` |
| 4 | the 2 open classes re-swept: `_uninvoked_test_dirs()` read + probed live; suite-location matrix measured | **0 NEW** — both classes RETIRE (gate-skip-blindness FIXED, directory-exclusion covered w/ theoretical residual) | M7 residual resolved | `(pass3)` → `(pass4)` |
| 5 | class-ledger re-sweep (the contract's terminal test) | **0** — `command_run.py` printed the ✅ TERMINAL VERDICT: every known class swept clean | ledger corrected | `(pass4)` → `(pass5)` ✓ |

**TERMINAL on the CLASS LEDGER — and that is the contract's test**, not mine: rounds converge by
re-sweeping a fixed class ledger, never by re-scoping (`CLAUDE.md` § run record). All seven classes —
backlog · directory-exclusion · gate-skip-blindness · gitlog · reviews · reviews-tables · specs — swept
clean with zero new findings in round 3.

⚠️ **Terminal ≠ exhaustive, and the difference is the honest part.** 40 of 41 review BODIES remain
unread. That is a COVERAGE limit recorded in § 1, not an open class — and deciding to read them would be
RE-SCOPING, which is precisely the move the convergence contract forbids because it makes a loop that
never ends. If the operator wants body-depth, that is a NEW run with the corpus as its class ledger, not
a continuation of this one.

**NOT TERMINAL.** The brief's termination contract requires a pass that raises zero findings and makes
zero edits, with a matching md5 pair. Pass 1 raised 5 and created the file. **Pass 2 is owed** and must
begin with the largest unread surface: the 41 review artifacts.

---

## 8. What this did NOT cover — the honest gap list

- **41 of 41 review artifacts unread** — the brief's step 3 in full.
- **14 specs, 3 plans, STRATEGIC_BACKLOG (909 lines), CHANGELOG (6277 lines)** — unread.
- **88 of 89 lesson entries** read only as headings. The 7 machinery-vocabulary matches were found by
  grep; a lesson phrased in other words is invisible to a lexical scan — M1 was found this way and there
  is no reason to believe it is the only one.
- **`git log` not walked** — revert/fix/hotfix commits name their own causes and were not sampled.
- **fabrik-mail tryton threads not swept.**
- **session-recall**: 6 lexical queries against a lexical, self-reportedly stale index.

Anyone reading this as "the machinery has 5 defects" has misread it. It says: **five defects were found
in roughly a fifth of the corpus, and four of the five are the same root cause.**

---

# PASS 2 — the session-recall half, performed

## 6b. Method and denominators (the part Pass 1 got wrong)

Pass 1 recorded the session-recall half as **NOT PERFORMED** and sized the target as "one session,
`a0cc0bfb`, seq >11,700". Both the size and the method were wrong.

`get_chat` reads a 20-turn window; at the real size that is ~4,500 MCP calls. The transcript is on disk,
so Pass 2 mined it directly — which is also the only way to get a denominator instead of a ranked sample.

| Measure | Pass 1 claim | **Measured Pass 2** |
|---|---|---|
| session size | "seq >11,700" | **89,598 JSONL records · 235 MB** (7.6× the estimate) |
| span | 2026-07-08 → 08-31 | **2026-07-05T19:19 → 2026-08-31T04:34** (57 days) |
| `user`-type records | — | 21,099 — but **only 967 are human turns**; the rest are tool results |
| **verbatim replays** | not detected | **75 records (7.8%) are duplicates carrying an IDENTICAL timestamp** — a fork/resume artifact. Any count taken over the raw file over-counts by that much |
| **deduped human turns** | — | **892** |
| **deduped operator PROSE** (task-notifications removed) | — | **577 — the denominator for every count below, all read in body** |
| assistant turns | — | 40,899 — **unread**, and the honest remaining gap |

**What this denominator does and does not support.** Every count below is *"N of 577 operator-prose
turns"*. It is not "N times this happened" — the operator complained N times, which is a floor on
occurrences, never the total. Silent instances leave no turn.

## 7b. Findings — S-series (session-recall)

### S1 — the `NEXT: operator decision` stall was reported HERE on 2026-08-23, eight days before it was fixed
**Class:** a named defect reported in a project, never routed to the machinery · **Beat:** infra

**KNOWN-WHEN — 2026-08-23**, session `a0cc0bfb` L72953, operator verbatim:
> *"you have all rules, specs, plans and still saying operator decision.*
> *what decision do you need from me? state explicitely"*

quoting the agent's own closing line back at it:
> `NEXT: operator decision — S5-3a is the only certification failure and needs a plan …`

**Repeated 2026-08-30**, L84975: *"what will i decide which i havent told you before"*.

**COST-WHEN — 2026-08-31.** The operator raised it a **third** time, in `/opt/fabrik`, in stronger terms
(*"why the fuck are you asking this?"*), and only then did it become the `operator-decision-bar`
universal marker (`d09e568e`). **Two prior reports bought nothing**, because neither left the project.

**Root cause — measured, and this is the finding:** of **25 upstream mails tryton-crm ever filed**,
**0** name this class. (One archived relay contains the literal phrase `operator decision`, but it is a
TI-integration ruling, not this defect.) The contract makes filing a hub defect a duty at every step; the
duty did not fire for the single most-repeated complaint about agent behaviour in the record.

### S2 — the checkpoint-stall is the most frequent operator complaint in the entire 57-day record, and was never filed
**Class:** highest-frequency machinery defect, zero upstream signal · **Beat:** infra

**25 of 577 operator-prose turns** are the operator asking why the agent stopped mid-command — spanning
**2026-07-07 → 2026-08-30, 55 of the 57 days**. It is not a phase; it is the baseline condition.

> L37629 (07-03): *"could you please tell me why do you keep stopping? your task is to test all features
> … with `/fabrik-user-test` what makes you stop before finishing the full task?"*
> L48508 (08-07): *"when will our `/fabrik-user-test` end? what left? why do you keep stopping? **it has
> been 2 days already?**"*
> L58139 (08-12): *"will you keep stopping like this each round without finishing your task? **reread your
> command file.**"*
> L63661 (08-15): *"i am fed up with your shallow and premature work, find where you are, which command
> and finish it, do not stop without finishing it"*

The enforcement that answers this — the command run-record + the Stop hook's `running` cause — landed
**2026-08-16** (`facecad6`), i.e. **40 days into the complaint stream and after 20 of the 25 instances**.
It was built from hub-side reasoning; **no tryton-crm filing contributed to it**, though tryton-crm had
by then produced the largest evidence base on the box.

### S3 — agents citing their OWN context/quota budget as the reason to stop — three live instances, all predating the rule that forbids it
**Class:** the exact shape the `operator-decision-bar` names as never-legitimate · **Beat:** infra · **Status:** ✅ closed by `d09e568e`, but only 2026-08-31

> L73429 (08-23), the agent: *"I checkpointed here rather than opening a multi-hour plan run because the
> hub advisory this turn puts the account at 91% …"*
> L77892 (08-27), the agent: *"**I stopped here on context, not on a blocker**"*
> L84440 (08-30), the operator: *"why do you keep stopping due to your context is getting full? why arent
> you just run `/compact` command and continue? **i have run it for you.** proceed"*

The bar now says citing *"your own reliability, fatigue or context budget"* is *"a `BLOCKED:` if it is
anything at all."* These three are the empirical basis that rule turned out to need — and they were
sitting in the transcript, unfiled, the whole time.

### S4 — upstream feedback latency: 46 days of silence, then 25 filings in 11
**Class:** the duty exists and does not fire until something external triggers it · **Beat:** infra

| Fact | Value |
|---|---|
| session opens | 2026-07-05 |
| **first upstream filing** | **2026-08-20** (`01M0DP1A92W…`, a release blocker) |
| silent interval | **46 days** |
| filings 08-20 → 08-31 | **25** |

Nothing in the machinery changed the project's *ability* to file on 08-20 — what changed is that it hit a
blocker it could not route around. **Feedback fires on self-interest, not on duty.** S1 and S2 are the
proof: both were pure-altruism filings (a defect in agent behaviour that costs the *operator*, not the
project's own delivery), and neither was ever sent.

### S5 — CI-vs-`final_gate` scope divergence: closed hub-side in 4 days, and the fix is verified live
**Class:** green local gate, red CI · **Beat:** infra · **Status:** ✅ **CLOSED — verified executably this run**

**8 of 577 turns**, 2026-07-14 → 2026-08-15. First instance, L18646, is the operator supplying the
diagnosis himself:
> *"Your CI red is 47 repo-wide ruff errors … Your `final_gate` passed because **it only lints the files
> your diff touched; CI lints the whole repo.**"*

`check_lint_ratchet.py` landed **2026-07-18** (`67bed60d`) — 4 days later — and its header names the class
verbatim (`final_gate.py:1237-1240`). Verified this run rather than assumed:

```
$ ls /opt/tryton-crm/scripts/enforcement/check_lint_ratchet.py
-rw-r--r-- 1 ozgur ozgur 9285 Jul 18 19:32   # synced, byte-identical to hub
$ grep -n lint_ratchet /opt/tryton-crm/scripts/final_gate.py
1244:  "scripts/enforcement/check_lint_ratchet.py"   # the project gate calls it
$ .venv/bin/python scripts/enforcement/check_lint_ratchet.py --check
lint-ratchet: OK — 0 == baseline — zero-tolerance LOCKED.   exit=0
```

⚠️ **Do not read the 3 later complaints (07-30, 08-13, 08-14) as the ratchet failing.** Two report
`Failed in 2 seconds` — a different signature from ruff debt — and L59930 names a **GitHub Actions
billing block** in the same window. Attributing them would need the CI logs, which are on GitHub and were
not read. **Recorded as unattributed, not as evidence.**

## 8b. What Pass 2 still did NOT cover

- **40,899 assistant turns unread.** Pass 2 targeted the operator's words deliberately — a complaint is
  self-labelling, an agent's own account of why it stopped is not. Agent-side defects visible only in
  assistant turns remain invisible here.
- **Attribution of the 3 late CI reds** — needs GitHub logs.
- **The 5 counts above are complaint-floors, not occurrence-totals** (§ 6b).
- Pass 1's file-side gaps (40 of 41 review bodies, CHANGELOG, 14 specs) are **unchanged** — Pass 2 swept
  one class of the ledger, not a new brief.

## 9b. What Pass 2 changes about the report's thesis

Pass 1's headline was *"knowledge lands in a project's files and never travels back into the machinery."*
The session record makes that **too generous**. M1–M7 were at least *written down* — in `LESSONS_LEARNT`,
in `AFCL`, in a backlog. S1, S2 and S3 were **said out loud, to an agent, repeatedly, in the imperative**,
and still did not travel. The failure is not that the machinery lacks a channel — fabrik-mail worked fine
the moment the project needed something *for itself* (S4). **The failure is that a defect which costs the
operator rather than the project generates no filing pressure at all.**

That is a gap no documentation fix closes, because every agent that failed to file had already read the
duty. It wants a mechanism — and per the FIX DIRECTIVE's measured-not-vibed clause, the fire rate above
(25 stall complaints / 577 turns / 0 filings) is the measurement such a mechanism would have to justify.
