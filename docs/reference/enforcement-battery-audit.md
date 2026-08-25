# Enforcement battery audit — "when a check cannot ask its question, what does it report?"

**Date:** 2026-08-25 · **Trigger:** transdoc, mail `01M0PRGR3JCNTGHQ9J608DXGA0` — *"audit the whole
enforcement battery against one question. I found six instances without looking systematically.
Expect more."*

## Method — executable, not a read-through

Reading 59 checks and reasoning about them is exactly the proxy this audit exists to distrust. Instead
the question was asked mechanically: **give every check a repo where its subject does not exist, and
record what it says.**

```
$ mkdir empty && cd empty && git init && echo "# empty" > README.md && git commit -am init
$ cp -r /opt/fabrik/scripts/enforcement scripts/     # checks derive ROOT from __file__, NOT cwd
$ for f in scripts/enforcement/check_*.py; do python "$f"; echo "exit $?"; done
```

The copy step is load-bearing and was learned the hard way: most checks resolve their root via
`Path(__file__).resolve().parents[2]`, so running them with a different `cwd` audits **/opt/fabrik**
while appearing to audit the empty repo. `tests/enforcement/test_check_imports_resolvable.py` documents
the same trap for the same reason.

## Result

| | count |
|---|---|
| checks in the battery | 59 (56 runnable standalone) |
| exit 0 in an empty repo | 49 |
| exit 1 in an empty repo (asked a question, got an answer) | 10 |
| exit 0 and **silent** | 20 |
| exit 0 and an **affirmative success claim** | 17 |
| …of those, stating a **denominator** | **1** |

## The finding — it is not "these checks are broken"

Most of the 17 reach the **right verdict**: their subject is absent, so there is nothing to fail on.
The defect is in what they *say*. A reader — human or agent — sees

```
check_doc_links: OK — zero broken references in the live tree
✓ command corpus: web-tool names, chain targets, script paths, trailer models — all sound
✅ Test coverage check PASSED (no src/ changes)
```

and concludes the check **examined something and found it clean**. In the fixture above,
`check_doc_links` scanned a single README with no links at all. The sentence is true and the
impression is false.

**`OK` is indistinguishable from `OK, I examined nothing`.** That is the whole class, and it is the
same shape as the three defects already fixed this week — `check_command_corpus` red-gating every
project it was synced to, `check_imports_resolvable` walking `src/app/tests` in repos that have none,
`check_vendored_drift` never comparing rules packs.

### The exemplar to copy

Exactly one check already does it right:

```
check_traycer_chain: PASS - 0 files, all 3 classes clean
```

`0 files` is the whole fix. A reader instantly knows this verdict covers nothing, and no follow-up
question is needed.

### The rule

> **A success line must state its denominator.** Not `OK`, but `OK — N <subjects> examined`. When N is
> 0, say so; a check with nothing to examine should report NOT-APPLICABLE, never success.

Two checks already satisfy the spirit by naming the reason instead of a count, which is equally
honest and is fine:

- `check_hooks_index` → `(not the hub — hooks-index check skipped)`
- `check_test_proposal` → `INFO: No plans directory found - skipping Behavior Contract check`

## Not findings — verified before claiming

- **`check_android_env`** prints `PASS: Android Environment verified at …`. It examines the HOST's
  `ANDROID_HOME` env var, not the repo, so passing in an empty repo is correct for what it is. Listing
  it as a defect would have been the same over-claiming this audit exists to catch.
- The **20 silent** exit-0 checks are not implicated: silence on an absent subject is honest. Only an
  affirmative claim is.

## Progress

**Done (5 of 13, plus 3 that came free):**

| check | success line now reads |
|---|---|
| `check_doc_links` | `OK — 0 broken of 1849 refs across 215 docs` |
| `check_docker` · `check_health` · `check_watchdog` | `… across 2553 file(s) walked` |
| `check_vps_docs` | `… across 3 VPS doc(s)` |

`_check_runner.py` carries the count for **seven** checks, not the four first estimated — `check_ports`,
`check_env_contract` and `check_deps_sync` gained it for free from the same edit.

**Two units, deliberately.** The runner says **walked**, not *examined*: it hands every repo file to
`check_file` and each check's own dispatch decides what applies, so walk size is what that layer can
honestly attest. `check_vps_docs` does **not** walk the repo at all — its subject is the fixed
`VPS_DOCS` list — so it names *VPS doc(s)*. Forcing the runner's unit there would have been a
borrowed number the check never earned. **The rule is that a success line names ITS OWN denominator,
not that every check reports the same one.**

## Closed — re-swept 2026-08-25

Re-running the identical empty-repo sweep after the fixes:

| | before | after |
|---|---|---|
| affirmative success claims | 17 | 21 (more checks now reach a verdict) |
| …**bare** (no denominator, no reason) | **16** | **0** |

Every success line now either **states a count** or **names its reason**. Both forms satisfy the
rule; requiring a number everywhere would have been worse, because several checks are honestly
reporting *why* there was nothing rather than *how much* of nothing:

```
check_imports_resolvable   NOT APPLICABLE: none of src/app/tests exist in this repo
check_compose_services     ✅ Compose services check PASSED (no compose files)
check_test_coverage        ✅ Test coverage check PASSED (no src/ changes)
check_hooks_index          (not the hub — hooks-index check skipped)
check_retired_terms        OK — 0 unmarked retired-tech mentions across 0 live doc(s)
check_review_coverage      OK — 0 unproven coverage claims across 0 changed review artifact(s)
check_duplicates           PASS — 1.3% of 205 duplicated line(s), 12 block(s), threshold 7.0%
```

**Three of the eight "remaining" turned out to need nothing** — `check_openapi_sync`
(`no new routes`), `check_phase_tests` (`no active plan window…`) and `check_test_coverage`
(`no src/ changes`) already named their reason. Editing them would have been churn against
non-defects, which is the failure mode this audit exists to avoid.

**A classifier caveat worth keeping.** Three successive regexes used to *count* the remaining bare
lines each produced false positives — `[0-9]+ (file|doc)` cannot match `0 live doc(s)` or
`1 changed file(s)`, and none of them knew `NOT APPLICABLE` was compliant. The final count was made
by reading all 21 lines. **An audit of misleading output is itself easy to mislead;** when the
population is small enough to read, read it.
