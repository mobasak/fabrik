# Review — fail-closed test-DB guard + check_undeclared_imports fix (2026-07-24)

Surface: base HEAD bf8b2f208261eb4c4fb4b14e2f4b35885c9e92fe (review then fixed the working tree on top).
Scope: commits f2c254ee (claudeck docs + INDEX), 39211268 (require_throwaway conftest + ci_test), bf8b2f20
(check_undeclared_imports) — plus callers/callees. Review fixes committed as the follow-up commit on this date.

## Rubric (from `review_rubric.py --changed …`, injected verbatim into every finder)

```
FLOOR: core/35-security-auth (fail-closed invariant; no secrets in code; env-only config)
       core/25-data-postgres (no SQLite-as-backing-service; explicit FK behavior)
       core/30-ops (no host ports; immutable releases; migrations never at startup)
12-FACTOR all twelve axes · MATCHED: core/45-testing-strategy (Behavior Contract; destructive-test guard)
```

Finder fleet: R1 = 3 pool (deepseek-v3.2-exp, gemini-3-flash, qwen3-max via `fanout("review", mode="read_only")`,
all `set_quality`-scored) + 1 native Opus `fabrik-reviewer` (authoritative). R2 = 2 pool. R3 = 1 pool. R4 = 1 pool
(confirming). All pool rows recorded + scored.

## Pass Ledger

```
Pass 1 — finders: pool×3 (logic/regex · guard-semantics · test-quality) + native Opus (blast-radius/fail-closed/contracts/12F/docs)
         | found: 21 raised (9 distinct CONFIRMED/PLAUSIBLE after dedup+triage) | fixed: 7 | → not done
Pass 2 — finders: pool×2 on the fix delta | found: 12 raised | fixed: 1 (query-host CI-escape crack) | → not done
Pass 3 — finders: pool×1 on the guard micro-delta | found: 8 raised | fixed: 0 (all refuted, fail-closed held) | → not done (raised ≠ 0)
Pass 4 — finders: pool×1 confirming pass, positively-asserted-defects-only | found: 0 | fixed: 0 | → EXIT
```

## Coverage Checklist (adjudicated)

| Class | Verdict | Evidence |
|---|---|---|
| Logic/off-by-one/regex in check_undeclared_imports | FIXED(4) | ships_scripts `\.` over-match; `_PIP_CONT` line-continuation; exact `requirements.txt` token; surrogateescape decode — each with a mechanical regex-matrix run + regression test (tests/test_check_undeclared_imports.py) |
| Fail-open vs fail-closed on every gate/guard | FIXED(2)+CLEAN | CI escape → localhost-only; `?host=` query smuggle closed (`hosts <= _LOCAL_HOSTS`); `_git_tracked` fail-open verified correct (absence never causes false-negative deploy break) |
| Fleet blast radius / false-positive risk | FIXED(3)+CLEAN | `pip install .` now suppresses pyproject-only class (e2e test); post-fix sweep: TI/claim-validator/tryton still fire true positives, youtube clean |
| Cross-file contract (3→4 tuple) | CLEAN | sole caller is `final_gate.py:832` subprocess (exit-code contract); Opus grepped whole repo, no tuple unpack |
| Guard semantics (require_throwaway) | FIXED(4) | IGNORECASE; `strip("/")`; CI=localhost-only; query-host — each with regression test (tests/test_scaffold_test_db_guard.py, 8 tests) |
| Generator parity ci.yml ↔ ci_local.sh | CLEAN | parity asserted in test_ci_scaffold + test_scaffold_test_db_guard behavior-4; `pg_isready` verified unaffected by POSTGRES_DB (maintenance DB always exists) |
| Test quality | CLEAN | qwen pass: all 5 new R1 tests fail-on-revert, no mock theatre; venv-walk fragility claim REFUTED (system-python case still discriminates) |
| Behavior-without-a-test | FIXED | every review fix ships its regression test; suite 51 passed |
| Boundary/sentinel/prefix collisions | REFUTED(6) | `backtest` ≠ `_test$`; query `?x=_test` stays out of `.path`; `%5F` not decoded; empty/multi-segment names → refuse (fail-closed); alternate IPv6 loopback forms → refuse (friction, not exposure) |
| Cost/quota/limit accounting edges | CLEAN | subprocess bounded (30s, fail-open); no accounting surface in diff |
| 12-Factor axes | CLEAN | Opus greppable sweep: none present; `postgres:postgres` is a noqa'd throwaway CI credential |
| Security-auth floor | CLEAN | no secrets emitted; guard fail-closed proven across R1–R4 adversarial URL shapes |
| Docs accuracy (claudeck doc + INDEX) | CLEAN | Opus verified all three INDEX entries exist + git-tracked |

## Disposition ledger (every raised candidate → terminal state)

FIXED (9 distinct, each with regression test, all in the review-fix commit):
1. `_dockerfile_ships_scripts` `\.` matched any `COPY ./<subdir>` → false scans (R1 pool-0 + Opus#2)
2. `_git_tracked` decode `errors="ignore"` dropped exotic filenames → `surrogateescape` (R1 pool-0)
3. Guard marker case-sensitive → IGNORECASE (PG unquoted names case-insensitive) (R1 pool-1 + Opus#8)
4. CI=true escape unlocked ANY host → localhost-only (R1 pool-1 + Opus#5)
5. `[^\n]*` couldn't cross `\`-continuation → `_PIP_CONT` (Opus#3)
6. No `pip install .` awareness → `_dockerfile_installs_pyproject` suppresses pyproject-only (Opus#4)
7. `\S*requirements\.txt` matched `prod-requirements.txt` → exact root token (Opus#7)
8. Trailing slash defeated marker → `strip("/")` (Opus#8)
9. `?host=remote` smuggled past empty-netloc CI escape → all hosts (netloc + parse_qsl) must be local (R2 pool-0)
Also FIXED: error message "Dockerfile/CI" wording → "deploy image installs only -r requirements.txt" (Opus#4b).

REFUTED (proof recorded): chained-`&&` pip regex (backtracking — mechanically verified True); `COPY scripts .`
(matches via `[/\s]`); PEP 508 name-start regex; `-c` constraints (pin, don't declare); query-param `_test`
bypass (path-only); no-path URL (refuses); `backtest`/`scratchpad` (don't match `$`-anchored suffix);
`research_scratch` wipe (suffix DECLARES disposability — the convention's contract); unix-socket/IPv6-alt/
whitespace/percent/uppercase-host variants (ALL land on refuse — fail-closed); `uv pip install -r` uncovered
(substring-matches `pip install`); poetry/multi-stage/vanilla Dockerfiles (degrade to pre-change union — never
a new wrong verdict); editable vendored first-party false-positive (EMPIRICAL: youtube `mt_router` origin
resolves to `/opt/youtube/libs/mt-router/...`, `_module_is_local` True, sweep clean); venv-walk test fragility
(system-python case still discriminates); per-file `.resolve()` cost (bounded, fail-open); node_modules marker.

REFUTED-as-design (recorded decision): the guard is opt-in (Opus#6) — auto-enforcing would false-fire on every
non-destructive DB test (a fixture cannot know a test's intent); enforcement channel is the rule-pack
anti-pattern row + Done-When checklist + the review rubric, matching how other conventions bind.

Count: 21+12+8+0 raised → 10 FIXED + rest REFUTED (dups noted inline); no row unresolved, no parking lot.

## Gates

`pytest tests/test_check_undeclared_imports.py tests/test_scaffold_test_db_guard.py tests/test_ci_scaffold.py`
→ 51 passed, 1 skipped. `ruff` + `mypy` clean on all touched files. `final_gate --lean`: sole red is the
pre-existing repo-wide Lint Ratchet (68→104, sibling benchmark scripts — inherited, not this surface).
Post-fix fleet re-verification: trade-intelligence (curl_cffi), fabrik-claim-validator (asyncpg+pdfplumber),
tryton-crm (polib) still detected; youtube clean.
