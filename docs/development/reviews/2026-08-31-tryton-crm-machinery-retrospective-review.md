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
| session-recall | — | ⚠️ **6 lexical queries + `recent_chats(n=25)`** | Index is lexical-only and warned stale on every call; **22 of 25** recent tryton-crm sessions are near-identical UI-QA *subagent* runs, so top-N is mostly noise |
| `git -C /opt/tryton-crm log` | — | ⚠️ **grepped** (revert/hotfix/workaround/gate) | Surfaced a D-019→D-020 revert (a decision re-litigated) — logged, not yet worked |
| fabrik-mail tryton threads | — | ⚠️ known from this session only | Not swept |

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
A conftest directory-skip lands in pytest's summary, so **M6 now catches this mechanism**. **RESIDUAL,
stated rather than glossed:** a directory never *collected* (excluded by path/testpaths rather than
skipped) still reports nothing and stays invisible. The existing `_uninvoked_test_dirs()` guard covers
part of that case; whether it covers all of it is NOT verified here and is Pass-4 work.

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
| 4 | **OWED** — Pass 3 raised 2, so it cannot be terminal | — | — | — |

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
