# Mypy Drivers Fix Execution Plan

**Last Updated:** 2026-01-13
**Status:** ✅ COMPLETE

---

## TASK: Eliminate mypy errors in Fabrik drivers

## GOAL
Reduce mypy error count to zero within `src/fabrik` with emphasis on driver modules (`coolify`, `wordpress`, `uptime_kuma`, `cloudflare`, and `src/fabrik/wordpress/*`).

## DONE WHEN (all true)
- [x] `mypy src/fabrik` reports 0 errors (verified: "Success: no issues found in 53 source files")
- [x] Targeted driver modules have accurate type hints matching runtime behavior
- [x] Necessary `from __future__ import annotations` added where forward refs needed
- [x] Dynamic areas explicitly typed with `Any` only when unavoidable

## OUT OF SCOPE
- Refactors unrelated to typing or driver modules
- Behavior changes beyond type correctness
- Documentation rewrites beyond required updates

## CONSTRAINTS
- Language: Python 3.12
- Follow existing coding style and patterns in drivers
- Avoid adding new dependencies
- Preserve runtime behavior while tightening types

## STEPS
1. Run baseline `mypy src/fabrik` to capture current errors
2. Fix typing issues in driver modules (coolify, wordpress, uptime_kuma, cloudflare, `src/fabrik/wordpress/*`)
3. Add future annotations and `Any` where necessary for dynamic data
4. Re-run mypy to confirm zero errors
5. Run enforcement/validators per project rules

## OWNER
- Droid Exec (Factory AI)

## LINKS
- Related modules: `src/fabrik/drivers/coolify.py`, `src/fabrik/drivers/wordpress.py`, `src/fabrik/drivers/uptime_kuma.py`, `src/fabrik/drivers/cloudflare.py`, `src/fabrik/wordpress/`
