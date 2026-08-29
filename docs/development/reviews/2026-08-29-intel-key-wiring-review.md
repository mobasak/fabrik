# Review — spare-key wiring (NVIDIA ×3 + Mistral ×3 + monthly cap)

Surface: HEAD d725f9fa (`.env.example` + `docs/CONFIGURATION.md`, 21 lines) + the gitignored
`.env` edits (6 keys + cap var) + the fabrik-lib pooling ask (`01M159RZK7`). Prior turn's larger
surface (the canary plan, `0bfdb98c..cfff4744`) is already covered by its Surface-anchored
whole-plan review (`2026-08-28-plan-1-canary-grounding-review.md`, found: 0) and is unchanged
since — not re-reviewed here.

Finders: **native-only, declared (NO-POOL: secrets carve-out)** — the surface is secret-adjacent
(`.env` content); secret material never goes to pool APIs. Orchestrator adjudication with
executable probes.

## Rubric

`review_rubric.py` FLOOR classes (docs + env surface matches no code packs); the load-bearing
rows here are the security-auth secret-handling mandates + the standing recurrence classes.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Secret handling | CLEAN — keys live ONLY in the gitignored `.env` (backed up first: `backups/.env.backup.20260829-*`); the pushed commit scanned for key material (the single `nvapi-` hit is a pre-existing format comment); neither mail carries a key |
| Probe evidence (proxy-never-evidence) | CLEAN — all six keys probed LIVE: NVIDIA 2–4 HTTP 200 ×3; Mistral 2–4 HTTP 401 ×3 + key 1 re-probed 401 (methodology sanity) — the 401s reported honestly, documented at the consumer surface, named as the operator's console item |
| Cost/quota accounting | FIXED(1) — `MISTRAL_MONTHLY_CAP_USD=10` was provisioned with NO consumer (stored-and-never-read; an advisory cap on a paid API). Mitigated: all Mistral keys 401 → zero spend possible. Fix: backlog row [intel] naming the resolution (route the first consumer's spend through the cost-budget seam; monthly + total, never per-call) |
| Sibling-WIP boundary | CLEAN — `providers.py` (the sibling's untracked NVIDIA train) read, never edited; multi-key rotation filed upstream (`01M159RZK7`) instead of forked |
| Doc truth | CLEAN — both CONFIGURATION sections re-read post-render; claims match the probes and the .env state; `.env.example` placeholders carry no values |
| Fail-open vs fail-closed | CLEAN — the 401 state is documented so no consumer trusts the Mistral keys silently; NVIDIA spares are opt-in by explicit env selection |
| Boundary/sentinel/prefix | CLEAN — numbered-var convention collides with nothing (`grep _API_KEY_[234]` unique); the plural `*_API_KEYS` convention deliberately not reused (the provider seam reads a scalar) |
| Behavior-without-a-test | CLEAN — no code shipped; the wiring is env+docs; the executable proof is the six live probes |

## Pass ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 | native (secrets carve-out) + 8 executable probes | 1 | 1 | 1 (cap-consumer backlog row) |
| Pass 2 | fresh re-read of both rendered docs + commit secret re-scan + backlog row verified | 0 | 0 | 0 |

Flywheel: no pool rows this review — NO-POOL declared (secrets carve-out; the one sanctioned
all-native case).

## Proofs (this run)

```
$ git show d725f9fa | grep -iE "nvapi-|[A-Za-z0-9]{32}"  → only the pre-existing "# nvapi-*" format comment
$ curl …integrate.api.nvidia.com/v1/models  (keys 2,3,4)  → 200 200 200
$ curl …api.mistral.ai/v1/models  (keys 1,2,3,4)          → 401 401 401 401
$ crontab -l | grep -c canary_grounding                    → 0 (canary cron not yet installed)
```

## Correction (2026-08-29, later the same day)

The Proofs block above is partially INVALID and is retained for the record: `.env` was
unsourceable (three unquoted values aborted `source` at line ~100), so the "NVIDIA 200 ×3" ran
against a PUBLIC endpoint with EMPTY keys (bogus/no-auth also 200 — `/v1/models` does not gate)
and the "Mistral 401 ×4" was the empty-key artifact. Re-verified with grep-read real values
against GATED endpoints: NVIDIA keys 2–4 → chat completions HTTP 200 ×3 (genuinely live);
Mistral keys ×4 → HTTP **402** (credits exhausted — matching the operator's ground truth).
`.env` quoting fixed (4 values), full `source` now clean. The false-verification class
(public endpoint as key probe + probes reading unset env silently) goes to LESSONS_LEARNT.
