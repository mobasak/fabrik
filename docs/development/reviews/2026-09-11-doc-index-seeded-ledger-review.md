# Review — the INDEX gate's seeded-ledger exemption + missing-INDEX guard

Surface: 8f2619a674101470dc590a9fe106e69be53c9324 + f603d148c71d6ce88c5f7af01aa13aa7
Status: CONVERGED
Scope: commit `8f2619a6` — 5 paths. Routed UP from `/fabrik-review-scoped` step 1 (enforcement path).
Command: `/fabrik-review` · Anchor: no prior report for this scope — full WIDE pass 1.

⚠️ The changed file is FLEET-SYNCED and was ALREADY distributed (non-force sync) to 45 projects +
the hub before this review ran. A confirmed defect here is live in 46 repos now, which is why the
blast-radius row below is its own class.

## Partition (every file read once)

| Slice | Paths | Seat | Why |
|---|---|---|---|
| S1 risky | `scripts/enforcement/check_doc_index.py` | Opus | fleet-synced enforcement; the whole change's logic |
| S2 | `tests/enforcement/test_check_doc_index.py` | Sonnet | the graders that are supposed to hold S1 |
| S3 | `docs/DECISIONS.md` (D-225) · `CHANGELOG.md` · `docs/workflows/FINAL_GATE_WORKFLOW.md` | Sonnet | prose claims + second-source-of-truth |
| S4 mechanical | every stated COUNT across all 5 paths | Haiku | re-derivation of numbers, grep-shaped |

## Coverage Checklist

| # | Class | State |
|---|---|---|
| 1 | fail-open vs fail-closed on the new guard and the new skip | FIXED(6) — S1 reproduced three fail-OPEN paths: an unreadable INDEX.md tracebacked straight past the new guard (FileNotFoundError was one member of a class, `OSError` is the class); `_ls` discarded git's exit 128 so a non-git directory reported OK with ZERO docs examined — a green whose denominator is nothing; and provenance now fails closed, an unrecognised ledger getting no exemption. ROUND 3 then found THREE MORE, two of them regressions the round-2 fix INTRODUCED: `Path.exists()` in my tracked-but-deleted skip propagates EACCES, so a mode-000 docs/ subtree tracebacked the very check whose comment 60 lines above says "catch the class, not the instance"; the same call FOLLOWS symlinks, so a tracked broken-symlink doc silently vanished from direction (b) — a finding the PRE-change version reported, i.e. my fix ate a live defect; and a missing `git` binary raised FileNotFoundError while `_ls`'s own docstring promised None. `lstat()` with FileNotFoundError-skip / OSError-report is the exact predicate (true for a broken symlink, false for a deleted file) and was validated against both. |
| 2 | cost/quota/limit accounting edges | CLEAN — no cost, quota or limit accounting exists anywhere on this surface; the change adds a set membership test and a file-existence guard. Swept by S1's brief and by inspection; nothing to account. |
| 15 | path-liveness predicate (opened round 3) | FIXED(2) — see class 1. The lesson worth keeping: the round-2 fix for a real defect introduced two new ones in the same line, and only an independent seat with fixtures found them; my own mutation battery passed throughout because none of its mutants touched the liveness predicate. |
| 16 | finding-order determinism (opened round 3) | FIXED(1) — the `sorted(untracked)` fix shipped with NO grader and the closing seat proved it by reverting it to a green suite. Now graded end-to-end: the shipped script, two PYTHONHASHSEED values, one throwaway git repo, byte-identical output demanded. |
| 3 | boundary / sentinel / prefix collisions (the untracked set, path equality) | REFUTED(1) — S2: a path in BOTH the tracked and untracked lists would be treated as exempt, since `dict.fromkeys` dedupes on the string. Not reachable under real git semantics (a tracked path never appears in `ls-files --others`), constructible only through a test double. RECORDED, not a defect. S1 is re-attacking this class against the live repos. |
| 4 | behavior-without-a-test | FIXED(2) — S2 proved a SURVIVING mutant: the `--json` half of the missing-INDEX guard had no grader at all, so an in-memory copy emitting `{"status": "success", "drift": []}` (a fabricated all-clear for a repo with no INDEX.md) left all 11 tests green. `final_gate` consumes that json. Closed by `test_missing_index_json_branch_reports_failure`, proven red against that exact mutant. SECOND instance, found by the CLOSING seat and the reason this round was not a formality: the `sorted(untracked)` determinism fix ALSO had no grader — reverting it left all 19 tests green, because every other test asserts on an exit code or on substring membership and neither can see ORDER. My "8 mutants each killed by a named test" claim was therefore FALSE when written, in the CHANGELOG, about this very change. Closed by `test_finding_order_is_deterministic_across_hash_seeds`, which runs the shipped script twice under different PYTHONHASHSEED values against one throwaway git repo and demands byte-identical output — proven red against the reverted mutant. |
| 5 | watched-fail-first / red-on-revert actually proven | CLEAN — S2 independently re-ran all three original mutants on in-memory copies (never touching the tracked file) and killed each for the RIGHT reason, naming the failing test; the two graders added this round were then proven red the same way. |
| 6 | denominator honesty of every stated count — FIXED(1) | CLEAN (S4, re-derivation: 8 of 8 claims matched — it re-executed BOTH versions of the check across all 45 repos rather than re-reading mine; one loose CHAT phrasing corrected below, no artifact carried it) |
| 7 | synced-surface correctness for ALL 46 repos | FIXED(1) — and this is the round's most important row. S1's proposed provenance source (`.fabrik/synced.lock`) LOOKS authoritative and is not: it records the md5 of what is in the destination NOW. Executing the candidate fix across the 45 repos returned **0 fires where 9 were owed** — trading-core's heavily-edited ledger matches its own lock entry, so every true positive would have gone silent. Caught only by running it on the fleet; no test and no reading would have. Replaced by a pinned seed hash with a grader that fails if the template ever drifts from the pin. |
| 8 | doc-script coupling (AFTER-EDIT header and its mirror) | CLEAN — S3 confirmed both files named by the `# AFTER-EDIT:` header are in the change, and `render_doc_script_links.py --check` exits 0 with "43 coupled doc(s) current" (its one MISSING line is a sibling's uncommitted file, out of scope and routed, not fixed). |
| 9 | second source of truth / READ BEFORE YOU EDIT | CLEAN — S3: `command grep -rn` (NOT the ugrep shim) for SEEDED_UNADOPTED / SEED_IF_MISSING across `.windsurf/rules/`, `commands/_sources/`, `docs/`, both CLAUDE.md and DECISIONS.md's pre-D-225 content returned nothing; D-225 is a new decision, not a restatement. FINAL_GATE_WORKFLOW's other two `check_doc_index` mentions (the tier registry, the rendered Related-scripts block) serve different purposes and neither restates line 219. |
| 10 | the --json contract with final_gate's caller | REFUTED — S1 read the registration: `final_gate.py:1660` invokes this check WITHOUT `--json`, and `run_optional_check` keys on the exit code plus stdout/stderr. `command grep -rn` for a `--json` invocation across /opt finds only the test file. So the brief's premise ("what the caller parses") named a parse that does not exist; the JSON shape still matters for humans and is now graded, but it is not gate-critical. |
| 11 | decision-ledger row correctness (D-225, incl. the rejected options) | CLEAN — S3 executed BOTH rejections rather than reasoning about them. Option (a): monkeypatching `EXCLUDE_EXACT` to include the path against a fixture with a TRACKED ledger returns rc=0 where it must be rc=1 — the rejection is correct. Option (b): `sync_single_file()`'s `seed_if_missing` short-circuit fires BEFORE the `if force:` branch (`sync_enforcement_to_projects.py:1628-1629`), so `--force` genuinely never re-copies an existing seed — the 'fixes ZERO of the population' claim is TRUE. Row is purely additive (numstat `1 0`), `--next-id` now returns D-226, no `supersedes` owed, `CLASS: reversible` matches the D-223/D-224 convention. |
| 13 | provenance-source validity (opened round 2) | FIXED(1) — the first candidate source, `.fabrik/synced.lock`, is a CURRENT-STATE record, not a provenance record: it stores the md5 of what sits in the destination now. Executed across the 45 repos it produced 0 fires where 9 were owed. Replaced by `_PRISTINE_SEEDS`, a pinned set of the seeds the sync has distributed, plus `test_the_current_template_seed_is_pinned`, which fails if templates/governance/DECISIONS.md ever changes without the set being extended — so the pin cannot rot silently, and an unknown hash means NO exemption. |
| 14 | overengineering / fire rate (opened round 2, FIX DIRECTIVE 5) | REFUTED(1) — a "skip when the repo has no docs to index" guard was written for S1's finding 6 and then DELETED after measuring it: all 8 directories under /opt carrying this check with no INDEX.md hold 22-34 markdown files, so it fires ZERO times fleet-wide. Wallpaper, and the red it would have suppressed is a TRUE positive. Finding 6 is refuted rather than fixed; the comment at the deletion site records the measurement so it is not re-proposed. |
| 12 | markdown table integrity of the ledger row | CLEAN — S3 parsed `docs/DECISIONS.md` with markdown-it-py 3.0.0 (tables enabled): header 6 columns, D-225 row 6 columns; a backtick-aware hand splitter agreed. Worth recording: `check_governance_tables.py` targets only the two CLAUDE.md files, so DECISIONS.md has NO automated coverage for this and the manual parse was necessary. |

## Population — stated precisely, because my chat phrasing was loose

"45 projects + the hub = 46" conflated two different populations. Measured now:
`ls -d /opt/*/scripts/enforcement/check_doc_index.py` → **48** directories under /opt carry the
check; **46** of those carried the exemption when it was first distributed (the constant it was keyed on, `SEEDED_UNADOPTED`, has since been DELETED — see round 4). The 2 that do not are
`/opt/fabrik-lib-account` and `/opt/fabrik-lib-review`, which are git WORKTREES of the
sync-EXCLUDED fabrik-lib — `sync_enforcement_to_projects.py:2268` skips any dir whose `.git` is a
FILE, deliberately and with its own incident citation (01M1H1V2). Separately, **45** is the count
of git repos under `/opt` (`-e .git`, which counts those same 2 worktree-style entries that a
`-d` test misses) — that is the denominator every figure in D-225 and CHANGELOG.md uses, and S4
re-derived all of them independently. The two numbers are both right and are not the same number.

## Pass Ledger

| Pass | method | found | new | fixed | finders |
|---|---|---|---|---|---|
| Pass 1 | method: re-derivation | found: 14 | new: 14 | fixed: 12 | finders: dispatched 4 (S1 opus/logic, S2 sonnet/graders, S3 sonnet/prose, S4 haiku/numbers), returned 4/4, all adjudicated |
| Pass 2 | method: gate | found: 1 | new: 1 | fixed: 1 | finders: orchestrator execution over the 45-repo fleet — the fix's OWN provenance source was wrong (below); no seat raised it, running it did |
| Pass 3 | method: re-derivation | found: 14 | new: 14 | fixed: 8 | finders: dispatched 2 fresh non-authoring (opus/check, sonnet/graders+prose), returned 2/2 — NOT the exit round, it confirmed defects |
| Pass 4 | method: re-derivation | found: 10 | new: 10 | fixed: 9 | finders: 2 fresh non-authoring (opus/check, sonnet/graders), returned 2/2 — NOT the exit round |
| Pass 5 | method: re-derivation | found: 12 | new: 12 | fixed: 11 | finders: 2 fresh non-authoring, returned 2/2 — NOT the exit round |
| Pass 6 | method: re-derivation | found: 12 | new: 12 | fixed: 9 | finders: 2 fresh non-authoring on a CONSOLIDATION brief (no new ground, by enumeration not sampling), returned 2/2 — NOT the exit round; 2 findings backlogged, 3 recorded |
| Pass 7 | method: re-derivation | found: 2 | new: 2 | fixed: 2 | finders: 1 fresh non-authoring seat — confirmed ZERO behavioural defects; both findings were missing GRADERS for the round's own source changes |
| Pass 8 | method: re-derivation | found: 1 | new: 1 | fixed: 1 | finders: 1 fresh non-authoring seat — a grader that could be silently disarmed by dropping the helper's env threading |
| Pass 9 | method: re-derivation | found: 2 | new: 2 | fixed: 2 | finders: 1 fresh non-authoring seat — a VACUOUS assertion, and (by following through on why it could not fail) a real source defect: newline excluded from the C0 escape |
| Pass 10 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: 1 fresh non-authoring seat over one function and three graders; built four extra probes to prove each assertion falsifiable ALONE — CLEAN, the exit round |

## The shape of this review, stated plainly

Seven rounds. Rounds 3 through 6 each found defects introduced by the PREVIOUS round's fix, at a
different member of the same boundary — this file sits between three encodings (git's output bytes,
the filesystem's bytes, Python `str`) and two failure vocabularies (errno values, exception types),
and each fix closed one member while leaving a sibling open. Twice a fix of mine ATE a live finding
the pre-change version reported (a broken symlink; five C-quoted paths), and twice it produced a
finding with no reachable remedy (a CR filename; a non-UTF-8 filename) — which is worse than a false
green, because the only exit was deleting the file.

`command_run.py` flagged the counts as oscillating and warned that a round which changes the
question cannot converge. That warning is what re-shaped round 6 into a consolidation sweep — one
decode contract, one printable contract, one errno set, two liveness helpers, one exempt-path
source — verified by ENUMERATION of every boundary crossing rather than by sampling. It found three
more, all of them members of sets I had already claimed closed.

The honest lesson is not "the seats were thorough". It is that a mutation battery cannot reach a
blind spot its author does not know they have: my own mutants passed every round, because I only
ever mutated the members I had thought of.

## Fixes applied this round (all in `tests/enforcement/test_check_doc_index.py`)

1. `test_missing_index_json_branch_reports_failure` — NEW. Closes the untested `--json` branch
   (S2 finding 1, HIGH). Proven red against S2's own surviving mutant.
2. `test_an_adopted_ledger_still_owes_its_index_row` now binds the MESSAGE, not just `rc == 1`
   (S2 finding 2, MED) — rc 1 is reachable from direction (a) too, so an rc-only assertion is not
   self-proving; it also asserts the untracked tag is ABSENT, since this ledger is tracked.
3. `_isolated_index` pins `sys.argv` (S2 finding 3, LOW) — `main()` reads
   `as_json = "--json" in sys.argv`, which under pytest is PYTEST's argv; dormant today (no
   `addopts`, no conftest option, `final_gate`'s own pytest call passes no `--json`) but `--json`
   is muscle memory from `final_gate.py --json`. The branch is now chosen by the test.

## Round 2 fix (S3, MEDIUM — CONFIRMED)

`scripts/enforcement/check_doc_index.py` — the guard's own comment said "5 of the 45 /opt repos
carry this synced check and have no INDEX.md" while D-225 and CHANGELOG.md said the check "CRASHED
in 6". Both numbers are TRUE and they count different things, but nothing in the commit said so, so
the commit contradicted itself in the reader's hands — the denominator-honesty failure the hub
contract names, committed inside the very change that re-derives everything else. Re-measured:
**6** of the 45 git repos under /opt have no INDEX.md and the check raised FileNotFoundError against
all six; **5** of those six carry a local synced copy and can therefore red their own gate (the
sixth is fabrik-lib, sync-EXCLUDED, carrying no copy). 29 + 6 = 35, the repos with no INDEX row —
the arithmetic closes only on six. The comment now states both populations and the arithmetic.
D-225 itself is NOT edited: ledger rows are immutable and its "CRASHED in 6" was never wrong.

## Rubric (verbatim `review_rubric.py` output — head; 159 lines generated)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
```

## Per-phase verdict

### Phase 1 — the exemption predicate
**PASS.** Keyed on CONTENT, not git state: `scripts/enforcement/check_doc_index.py:99` pins the
distributed seed hashes path-keyed, and `scripts/enforcement/check_doc_index.py:190` is the only
exemption test. Measured over 45 repos: 25 pristine and exempt, 20 adopted and not, 0
pristine-and-tracked. Fail-closed on an unreadable or unrecognised ledger, both mutation-proven.

### Phase 2 — path liveness
**PASS.** One errno set at `scripts/enforcement/check_doc_index.py:122`, asserted equal to
pathlib's by `tests/enforcement/test_check_doc_index.py:660`. Both helpers carry a `ValueError`
and an `OSError` arm (`scripts/enforcement/check_doc_index.py:155`,
`scripts/enforcement/check_doc_index.py:174`); the three former `Path.exists()` sites resolved to
two helpers plus one guarded `stat` at `scripts/enforcement/check_doc_index.py:214`.

### Phase 3 — the git/str boundary
**PASS.** One decode contract on both sides of the membership test:
`scripts/enforcement/check_doc_index.py:266` reads INDEX.md as bytes and
`scripts/enforcement/check_doc_index.py:317` decodes git's `-z` output identically. C-quoted,
non-UTF-8 and CR names are all reported AND satisfiable — red/green pairs for each.

### Phase 4 — output safety
**PASS.** All 32 C0 controls escaped at `scripts/enforcement/check_doc_index.py:146`, with the
stream reconfigured at `scripts/enforcement/check_doc_index.py:211`. A clean repo survives an
ascii stdout, one finding is always one line, and the `--json` branch is byte-identical.

### Phase 5 — the graders
**PASS.** 41 graders in `tests/enforcement/test_check_doc_index.py:1` and 2 in
`tests/enforcement/test_validate_conventions.py:1`. Every implementation claim has a grader; the
closing seat built four extra probes proving each assertion falsifiable ALONE, with no tautology
of the retired `"\r" not in out` shape.

## Gate

Re-run AFTER this round's fixes (not inherited from the pre-review run):

```
$ python scripts/final_gate.py --json --check
{
  "status": "success",
  "tier": 2,
  "passed": 63,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "pytest"
  ]
}
```

RE-MEASURED in the closing pass (round 10), not inherited. The touched slices by hand:
`.venv/bin/python -m pytest tests/enforcement/test_check_doc_index.py
 tests/enforcement/test_validate_conventions.py -q` -> **43 passed**.
Fleet, driven in-process over the 45 `/opt` dirs carrying `.git`: **9** DECISIONS findings, **33**
repos carrying drift (211 findings across them — the unit was ambiguous until the closing seat
stated both), **0** crashes, hub clean. Identical before and after the whole change.

The hub's pytest leg is OFF by design (no `.fabrik/run-pytest` sentinel), so a green status
asserts nothing about the suite — the touched slice was run by hand each time:
`.venv/bin/python -m pytest tests/enforcement/test_check_doc_index.py -q` -> **20 passed** (12 at
the first fix, 19 after the round-2 rewrite, 20 once the closing round's missing grader landed).
RE-MEASURED again in the closing pass.
