# Rules Currency Pass — the standard every `.windsurf/rules` pack is evaluated against

**Status:** live · **Dispatched by:** operator, 2026-09-01 · **Rulings:** D-061, D-062, D-063, D-064, D-065

Written because the bar was not reproducible: its fullest statement lived in one agent's memory,
outside this repo, while it governed a fleet-synced corpus — and the pass had drifted from it twice
before anyone could check (files 10 and 13 shipped without their research leg; file 15 skipped four
bar items). A standard that only one session can read is not a standard.

## The goal (operator, verbatim)

An **"always uptodate, correct, lean, efficient, low maintenance, free, resilient, traceable,
logged, fastest, agile, best practise ruleset."**

## The per-file DONE BAR — all of it, every file

A file is not done until every row is satisfied or explicitly N/A with a stated reason.

| # | Requirement | Ruling |
|---|---|---|
| 1 | Evaluated against `docs/reference/operating-manifesto.md` | D-043 |
| 2 | **Live web research — never model memory.** The FULL arsenal, not one engine: exa · firecrawl · brave-search · WebSearch · WebFetch. **≥2 DIFFERENT tools on any contested or currency-critical claim** | D-062 |
| 3 | **In-repo grounding**, including `docs/infrastructure/` whenever the pack touches a deploy/VPS surface — and its load-bearing rows VERIFIED against the live fleet, because docs rot both ways | operator 2026-09-01 |
| 4 | **Author-blind SUBAGENT second opinion on the pack's rules**, verdicts adjudicated and recorded — never silently absorbed. Runs on **Fable 5**; fall back to **Opus 5** only on quota. ⚠️ **It GATES the commit — it does not trail it.** Measured over this pass: 5 of 6 opinions returned before their commit and their findings landed in it; the one dispatched-then-committed-past refuted TWO things already pushed, so the fix needed a second commit and the wrong text existed on master in between. If the opinion is still running, the file is not done — wait. | D-063 |
| 5 | **After ANY multi-point fix: grep the file's own vocabulary and sweep the CLASS, not the instances** | FIX-directive verb 2 |
| 6 | Zero unmarked version literals under the widened `_LOOSE` sweep | D-062 |
| 7 | A pinned test where warranted | D-062 |
| 8 | External claims registered in `.windsurf/rules/CLAIMS.yaml` with verify hints + windows | D-061 |
| 9 | Cross-pack classes deferred to the OWNING pack's turn and recorded in the backlog ledger — never a solo flip that sets packs against each other | D-062 |
| 10 | **D-065 fleet-AI lens** on deploy-surface packs: check the rules ENFORCE `OPERATIONS.md`/`DEPLOYMENT.md` currency, not merely mention the files | D-065 |

## Version literals — banned in EVERY shape, with three dispositions

The ban covers docker tags (`python:3.14`), name-version prose (`Node 24`, `Debian 13`) **and**
obsolete floors (`Python 3.9+`). Learned at file 1: a docker-tag-only sweep passed a file still
carrying four prose literals.

- **Delete as noise** — obsolete floors every fleet runtime already clears; the guidance must stand without the qualifier.
- **Reword version-free** — breaking-boundary references that stay true across future majors.
- **Marker span** — literals agents copy verbatim (Dockerfile pins): `<!--v:key-->literal<!--/v-->`, value owned by `.windsurf/rules/versions.yaml`, injected by `rules_render_versions.py`, refreshed weekly by `rules_currency_watch.py`. The most-reversible D-062 implementation.

⚠️ **A span is not cosmetic — verify the literal it yields EXISTS.** File 14 wrapped a Debian
codename; both resulting image tags were checked live on Docker Hub before commit. A span that
renders an unpullable image is worse than the literal it replaced.

## Standing method rules, each bought with a defect

- **A single-engine miss is "not found by one engine", never grounds to delete** (bought at file 2: one engine missed a true citation, it was wrongly deleted, and only the second opinion's different search restored it). Ungroundable-but-plausible → CLAIMS.yaml with a verify hint. Deletion is only for POSITIVELY refuted claims.
- **⚠️ A bounded search is never a negative.** File 15 reported a safety defect from grepping one repo for a SPEC field name that the module never spells (it reads the exported env var). The claim was false, reached the pack as a safety warning, and was retracted only because the second opinion refuted it. **When asserting "X does not exist", state where you looked and follow the data path end to end.**
- **The corpus is a months-deep curated asset — maintain, don't rewrite.** Human-paging tripwires alone are "bandating"; the solve is machinery that cannot go stale.

## The evidence test (how to audit whether a file actually got the bar)

For each row in `CLAIMS.yaml`, find the commit that **introduced OR substantively reworked** it and
check it was that file's own turn:

```bash
git log --format=%h -S 'id: <claim-id>' -- .windsurf/rules/CLAIMS.yaml | tail -1
```

⚠️ **Two known limits, both bought by getting them wrong.** `-S` is blind to IN-PLACE edits, so a
turn that strengthens an inherited row scores zero (this wrongly condemned file 11, whose own turn
had rewritten a claim to source level). And a bare id collides with the register's own supersede
convention (`X` matches `X-v2`). Diff-based checking is the fix. **The count is a SCREEN for
outliers, not a certificate of depth** — one research thread split across N rows buys N points, and
a pack of purely internal conventions legitimately registers zero.

## Scope and ledger

`core/` first, then ALL rules folders, to completion. Progress, cross-pack classes and deferred
findings: `docs/STRATEGIC_BACKLOG.md` § Rules currency pass.
