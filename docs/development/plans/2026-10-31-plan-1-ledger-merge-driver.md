# Plan — the ledger merge driver (W-53360407)

Status: IN-PROGRESS
Profile: small
**Owner:** infra-2
**Spec:** `docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (CONVERGED, D-1386; review receipt `docs/development/reviews/2026-10-30-ledger-merge-driver-spec-review.md`). The spec cites code at `51716046f`. This plan cites it at `b938c583e`, after master was merged in. The resolver functions are byte-identical between the two; only their line numbers moved (§ Evidence E2).
**Base:** `b938c583e` (branch `w-53360407-entry-files`). Code files: `scripts/merge_request.py`, `scripts/install_post_commit_hook.sh`, `.gitattributes`. New test: `tests/test_merge_ledger_driver.py`; extended test: `tests/test_workitem_merge_driver.py` (the installer's driver tests, panel concern). Docs: `docs/reference/multi-agent-operating-model.md`, `docs/workstation/hooks-index.md`, `CHANGELOG.md`, `docs/LESSONS_LEARNT.md`, `INDEX.md`.
**Prototype (executed):** `.tmp/runs/b61d3ce0-aa4e-4a4f-8800-4588107e6a30/fabrik-plan-after-chat-2026-10-31T00-45-06-0300/proto/` holds three files:
- `verb.py`, 22 lines: the verb's body;
- `test_merge_ledger_driver.py`: the draft tests;
- `d5.py`: the spec's D5 replay.

## What this plan is

The spec's delta, built in two code phases and a Finish:
- **Phase A:** the `merge-ledger` verb and its tests.
- **Phase B:** the installer's driver registration and the anchored `.gitattributes` lines, plus docs.
- **Phase C:** the whole-plan review, the replay grader, the ledgers and the merge request.

About 60 code lines over 3 code files, executed inline by the orchestrator (`/fabrik-plan-after-chat`'s `Profile: small`). Operator 2026-10-31: *"ok now i want the perfect merge implementation for all repos now. implement tonight"*. The coordinator added that small MRs which land tonight beat one big one.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § The delta 1-3: the verb, the driver string, `.gitattributes` | IN | Phases A, B |
| I2 | spec § Validation, each test leg: red-first with its rebase leg, DECISIONS order, refusal, duplicate-id, bootstrap, no-regression | IN | Phase A steps 3-4 |
| I3 | spec § Validation replay grader (D5, at least 58 builder merges cleared, no duplicated line) | IN | Phase C step 2 |
| I4 | spec § Validation tripwire (counter, threshold above 6, check date 14 days after landing, owner the coordinator) | IN | Phase C step 5 hands it to the coordinator with the landing date |
| I5 | spec § Validation Counter B pass (merges clean under plain git that the driver makes conflict, builder and owner) | IN | Phase C step 2 (panel, Opus concern 1); W-6614b62e keeps only the two-base residue |
| I6 | spec § The delta 4: the readers left unchanged (`check_convergence`, `decisions.py --reserve-id`, the changelog gate) | IN | Phase C step 4 runs the gate and the decisions check over the built tree |
| I7 | spec § Documentation landing sites (the op-model "always conflict" sentence, the hooks-index row) | IN | Phase B step 3 |
| I8 | spec Intake I7: `.fabrik/work` same-item conflicts | OUT-OF-SCOPE | W-7a1411b3 |
| I9 | operator: "implement tonight"; coordinator: "small MRs that land tonight" | IN | Phase C step 5, the merge request |
| I10 | rollout to project repos ("all repos") | OUT-OF-SCOPE | W-480cdb61. The verb ships fleet-wide with the sync, so the rollout is installer-only |

## Global Constraints (every phase inherits these)

- `scripts/merge_request.py` is fleet-synced (`scripts/fabrik_synced_manifest.py:52`). The new verb is inert in a repo with no `merge=ledger` attribute, and nothing else in the file changes.
- Tests run through `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest …` (D-935), never bare.
- Commit with explicit pathspecs and Agent Provenance Trailers. Never `--amend`. Push after each phase.
- A hub worktree commit distributes nothing; the change ships when the coordinator merges it.

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Format: Entry under ## [Unreleased] | `.windsurf/rules/core/40-documentation.md:132` |

## Phase A — the `merge-ledger` verb

Appetite: 40

**Produces:** `scripts/merge_request.py`'s `merge-ledger` subcommand. Phase B's driver string calls it as `python3 scripts/merge_request.py merge-ledger %O %A %B %P`.

**Steps** (sequential):
1. Add `_merge_ledger(base, ours, theirs, path)` beside `_merge3` (`scripts/merge_request.py:1048`), from `proto/verb.py`:
   - read the three files as bytes through `_decode` (`:778`);
   - run `_merge3`;
   - for `DECISIONS` (`:545`), refuse when `_dup_ids(result) - _dup_ids(ours)` is non-empty (`_dup_ids`, `:1266`). This is the spec's "a D-id twice that ours did not already hold twice", the same check `_build` applies at landing. The prototype's `proto/verb.py:9` subtracted theirs's duplicates too; that looser form is NOT carried over, and the Phase A duplicate-id tests exercise the spec's form;
   - write through `tempfile.mkstemp(dir=<dir of ours>, prefix=".merge-ledger-")` and `os.replace`, unlinking the temp on any exception.
2. Register the subparser beside `sync-runner`'s (`:4184`) and dispatch it before the verb table (`:4213`), as `after-merge-runner` (`:4188`) and `sync-runner` (`:4200`) are, so `main()`'s `try`/`finally` drain never runs after the rename. On any `Exception`, print `merge_request: REFUSED — <reason>` to stderr and return 1; on success return 0.
3. Add `tests/test_merge_ledger_driver.py` from the prototype, with these changes:
   - drop its placeholder `test_the_driver_runs_at_the_worktree_top`, and replace it with a test that commits a copy of `scripts/merge_request.py` into the scratch repo under `scripts/`, registers the installer's `LEDGER_DRIVER` string literally, and runs the clean-insertion merge from a `git worktree add` linked worktree, the shape of `_build`'s throwaway (panel, Opus concern 4);
   - add a `git rebase` leg to the red-first test, asserting the rebase is clean;
   - rewrite the no-regression test so BOTH sides change the SAME ledger at far-apart lines: git calls a driver only for a file changed on both sides, and plain git merges such edits cleanly. Log the driver's own exit (a wrapper script that appends `$?` to a file) and assert that exit was 0, the merged blob is byte-identical to the same merge with no driver configured, and the merge exited 0;
   - rewrite the refusal test's fixture so the edit of a landed row sits next to the other side's insertion (ours edits `| D-2 |` and appends a row, theirs appends a row after `| D-2 |`). The prototype's fixture put the edit two lines from the insertion, so `git merge-file` took it cleanly and the verb exited 0; and merge the same pair through git with the driver registered, asserting the merge exits non-zero and the file holds markers with both sides;
   - add to the duplicate-id test the verb's own exit 1 with `%A` byte-identical, run directly as the refusal test does, plus one case that tells the spec's rule from the prototype's looser one: base holds `| D-5 |`, ours adds `| D-7 |`, theirs adds a second `| D-5 |` row; the verb must exit 1 (the looser rule exits 0 there);
   - add a test that patches `os.replace` to raise, then asserts `%A` is untouched and no `.merge-ledger-` temp file is left (the only path that unlinks one).
4. RED then GREEN, using the prototype tests against `b938c583e` with no verb (§ Evidence E1):
   - 5 tests fail on `invalid choice: 'merge-ledger'`;
   - the control and the bootstrap leg pass by design (the bootstrap leg runs its own pre-verb script and proves the driver ran by its `invalid choice` stderr);
   - step 3's rewritten no-regression and refusal tests are watched red against the verb-less tree. The temp-file test calls `_merge_ledger` in-process (a subprocess cannot see a patched `os.replace`) and is watched red against the verb with its unlink removed. The D-5/D-7 duplicate case is watched red against `proto/verb.py`'s looser rule (panel, Opus concern 5).
   After step 2, all pass.
5. Gate: `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_merge_ledger_driver.py tests/test_merge_request_merge.py -q`; `/opt/fabrik/.venv/bin/python -m ruff check scripts/merge_request.py`; and `/opt/fabrik/.venv/bin/python -m mypy --cache-dir <scratch> scripts/merge_request.py` reports no error beyond the base's two, pinned by message, not line, since the build moves them: `"RefusedError" has no attribute "base_old"` and `Incompatible default for argument "landed"` (at `:3030` and `:3489` before the build). Those are pre-existing: `pyproject.toml:102` excludes `scripts/` from mypy, and a path named on the command line overrides that exclude (panel, Fable concern 1).

**Behavior Contract (Phase A):**
- Concurrent insertions in CHANGELOG and DECISIONS merge clean through git with the driver, by merge and by rebase (red without it).
- DECISIONS puts the higher D-id first whichever side is ours.
- An edit of a landed row next to the other side's insertion returns rc 1 with ours byte-identical, and through git the merge leaves markers.
- A failure after the temp file is made leaves ours untouched and no temp file behind.
- A duplicate D-id refuses, and git leaves markers with both rows when the rows conflict as text.
- A tree whose `merge_request.py` predates the verb falls back to markers, with `invalid choice` on stderr.
- A merge clean without the driver stays clean and byte-identical, and the driver itself exited 0.

## Phase B — registration, attributes, docs

Appetite: 30

**Consumes:** Phase A's verb.

**Steps** (sequential):
1. `scripts/install_post_commit_hook.sh`:
   - add `LEDGER_DRIVER='python3 scripts/merge_request.py merge-ledger %O %A %B %P || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B'` and two `set_config` calls beside `:86-87`;
   - at `:84`, replace the clause "the work-item merge driver is not registered" with "that merge driver is not registered" (`$1` already names the key; panel, Opus concern 7);
   - widen the mirror regex at `:98` to `merge=(workitem|ledger)`;
   - keep `BEGIN_MARK`/`END_MARK` (`:94-95`) byte-identical.
2. `.gitattributes`: add five root-anchored lines:
   - `/CHANGELOG.md merge=ledger`
   - `/docs/DECISIONS.md merge=ledger`
   - `/INDEX.md merge=ledger`
   - `/docs/STRATEGIC_BACKLOG.md merge=ledger`
   - `/docs/LESSONS_LEARNT.md merge=ledger`

   Put them under a comment naming W-53360407 and the spec.
3. Docs:
   - `docs/reference/multi-agent-operating-model.md` § Ledgers and ids across branches (`:162-164`): replace "two branches that both prepend a row to the same table always conflict at merge" with "two branches that both prepend a row to the same table conflict at merge under plain git; in a hub worktree the installer's `merge=ledger` driver (`merge_request.py merge-ledger`, W-53360407) resolves concurrent insertions inside the merge, an edit of a landed row still conflicts, and any driver failure falls back to markers" (panel, Fable concern 4);
   - `docs/workstation/hooks-index.md:214`, after "**It also registers the work-item merge driver** (W-c230cb2e)" (bold in the file): insert "and the ledger merge driver (W-53360407: `merge.ledger.name`/`.driver`, every `merge=ledger` line mirrored in the same block)";
   - `scripts/install_post_commit_hook.sh:2`'s `AFTER-EDIT` header gains `tests/test_workitem_merge_driver.py`, the suite that covers its driver lines (panel, Opus concern 2).
4. Add the installer test to `tests/test_workitem_merge_driver.py`, using its `_bare_repo` seam (`:125`), which copies the BUILT `.gitattributes` into the scratch repo before the installer runs. Never run the installer against the shared config before landing: `ROOT=/opt/fabrik` (`scripts/install_post_commit_hook.sh:14`) is the main checkout. The test asserts:
   - `merge.ledger.driver` equals the Phase B string;
   - the mirror holds the five `merge=ledger` lines between the unchanged BEGIN/END marks, with the `merge=workitem` line still inside;
   - `git check-attr merge` prints `ledger` for each of the five ledger paths (the positive control; on the base tree it prints `unspecified`);
   - `git check-attr merge sub/CHANGELOG.md` prints `unspecified`.

   Gate: that file plus the two the `AFTER-EDIT` header named before this change (`tests/enforcement/test_governance_sync_postcommit.py`, `tests/test_merge_sync.py`), under `/opt/fabrik/scripts/capped_run.sh` (panel, Opus concerns 2-3 and Fable concern 2).

**Behavior Contract (Phase B):**
- The installer registers `merge.ledger.*` and mirrors the ledger lines into `info/attributes` without orphaning the work-item block.
- A nested `sub/CHANGELOG.md` gets no `merge=ledger`.

## Phase C — Finish

Appetite: 45

**Steps** (sequential):
1. Run the one heavy review (`Profile: small`'s D7 floor): `/fabrik-review` over the whole-plan diff, one receipt.
2. Precondition, printed into the receipt: `git -C /opt/fabrik check-attr merge CHANGELOG.md` prints `unspecified`. Run the replay BEFORE the coordinator lands this branch. The plain-git baseline is a second `git clone --shared` checked out at `b938c583e`, with no `merge=ledger` line and the work-item driver registered as the installer does (a clone copies no config, and D5's figures were taken with that driver present), never the shared main checkout (panel, Fable concern 3, Opus concern 6). Then run the replay on a fresh `git clone --shared` of the hub at the Phase C tip. In the clone:
   - write the five `merge=ledger` lines into `.git/info/attributes`;
   - set `merge.ledger.driver` to the Phase B string, but naming the BUILT script by absolute path (`python3 /opt/fabrik/.claude/worktrees/infra-2/scripts/merge_request.py merge-ledger …`). D5 checks out each historical parent, and those trees have no verb, so the tree-relative string would fall back everywhere;
   - register the work-item driver as the installer does.

   Then run `proto/d5.py <clone> <baseline clone> "2026-10-17 00:00" "2026-10-31 00:00"` and record its output in the receipt. Expected: `driver-clears` ≥ 58 and no `dup` line. If `ledger-only` is not 70 (a fresh clone sees only refs that still exist), say so and judge the clear rate (58 of 67) instead of the absolute count.

   Then the Counter B pass: `d5.py` with its builder filter and its clean-merge skip removed, counting merges clean in the baseline that the driver leaves conflicted on a ledger. Expected `counter-b 0`; any other reading blocks the merge request (spec § Validation Counter B; panel, Opus concern 1).
3. Ledgers:
   - `CHANGELOG.md`: one `### Added — ledger merge driver (2026-10-31)` entry;
   - `docs/LESSONS_LEARNT.md`: the replica-versus-real-git lesson;
   - `INDEX.md`: the new test file;
   - no new D-row, because D-1386 holds the decision.
4. Run `final_gate.py --check --json` green over the built tree. It carries the changelog gate and the Decision Ledger check, the spec's unchanged readers (I6). Then push.
5. Run `python3 scripts/merge_request.py request --review <the /fabrik-review receipt> --item W-53360407` and send the `SendMessage` lines it prints. The coordinator's session holds SendMessage, so mail them if that is held. The report to the coordinator names the landing as the tripwire's start, its check date 14 days later, the counter, and the threshold above 6 (I4).

## Evidence

**E1. The prototype's tests minus its placeholder, against `b938c583e`, no verb** (run 2026-10-31 under `capped_run.sh`, copy in `.tmp/runs/b61d3ce0-aa4e-4a4f-8800-4588107e6a30/fabrik-plan-review-2026-10-31T00-46-42-0300/red/`):

```text
FAILED tests/test_merge_ledger_driver.py::test_the_driver_merges_both_insertions_clean
FAILED tests/test_merge_ledger_driver.py::test_decisions_puts_the_higher_id_first_whichever_side_is_ours[| D-1390 | o |-| D-1391 | t |]
FAILED tests/test_merge_ledger_driver.py::test_decisions_puts_the_higher_id_first_whichever_side_is_ours[| D-1391 | o |-| D-1390 | t |]
FAILED tests/test_merge_ledger_driver.py::test_a_duplicate_id_refuses_and_leaves_both_rows_in_markers
FAILED tests/test_merge_ledger_driver.py::test_an_edit_of_a_landed_row_refuses_with_rc_1_and_ours_untouched
5 failed, 3 passed in 6.43s
```

**E2. The resolver is unchanged since the spec's base**, so the spec's behaviour claims carry over. The anchors moved:

```text
$ diff <(git show 51716046f:scripts/merge_request.py | sed -n '/^def _resolve_insertions/,/^# --- (a)-(d)/p') <(sed -n '/^def _resolve_insertions/,/^# --- (a)-(d)/p' scripts/merge_request.py) && echo "resolver+merge3 UNCHANGED"
resolver+merge3 UNCHANGED
```

The current anchors at `b938c583e`: `_decode` `scripts/merge_request.py:778`, `_merge3` `:1048`, `_dup_ids` `:1266`, the `sync-runner` parser `:4184`, the verb table `:4213`.

**E3.** The prototype verb, run in a scratch repo on 2026-10-31:
- it merged two conflicting insertions clean, with D-1391 above D-1390;
- it refused a duplicate D-1391 and left markers;
- it refused an edit of a landed row;
- it left no temp file behind.

## Self-audit

- 3 code files and about 60 code lines, so `Profile: small` holds. The test-line budget runs over the ~1.5× target (about 130 lines), accepted because each test is one spec § Validation leg.
- Every spec § Validation leg maps to a test: Phase A's for the verb, the rebase leg included, and Phase B's for the installer. Two legs have no test of their own. One is `_build` raising no `ConflictError` on a merge that is clean without the driver: it follows from the no-regression test, because `_build` enters its conflict path only when its `git merge` exits non-zero (`scripts/merge_request.py:1223`), and that test asserts the merge exits 0 with the driver registered. The other is the Counter B pass (I5), which is a Phase C step 2 replay check with an `expected counter-b 0` gate, not a test of its own.

## Coverage Checklist

| Class | Verdict | Where |
|---|---|---|
| core/35-security-auth (floor) | CLEAN | no auth, secret or credential surface: a local git merge driver over repo files |
| core/25-data-postgres (floor) | CLEAN | no database |
| core/30-ops (floor) | CLEAN | no service, port or compose; the installer runs on each WSL shell as today |
| 12-FACTOR (floor) | CLEAN | no config, log or process-model change; the driver is a one-shot subprocess git starts |
| core/10-python (matched) | FIXED | round 1: bytes through `_decode`/`_encode`, temp-file unlink on failure, dispatch outside `main()`'s drain |
| core/45-testing-strategy (matched) | FIXED | rounds 1-3: refusal fixture made adjacent, no-regression made to invoke the driver, rebase leg, temp-file leg, discriminating duplicate case |
| anchors | FIXED | round 1: re-cut at `b938c583e` (E2) |
| evidence | FIXED | round 1: E1 red run, E2 fenced probe |
| intake | FIXED | rounds 1-2: tripwire hand-off, unchanged readers, W-7a1411b3, step 5 pointer |
| steps | FIXED | rounds 1-2: duplicate rule, installer seam, D5 clone registration |
| gates | FIXED | round 1: absolute `capped_run.sh` and interpreter paths |
| facts | CLEAN | no external fact beyond the CONVERGED spec's, which its own review re-verified |

Review rubric (`python3 scripts/review_rubric.py --changed scripts/merge_request.py scripts/install_post_commit_hook.sh .gitattributes tests/test_merge_ledger_driver.py`):

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (mode `AUTH_REFRESH_ROTATION`: `delete` by default, `grace` opt-in — § Token Lifecycle), JWT `jti` denylist revocation, an opt-in `email` access-token claim (`AUTH_EMAIL_CLAIM`, client-visible), and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- **Rotation mode is `AUTH_REFRESH_ROTATION` — set it, never hand-roll a grace window.** By default `AUTH_REFRESH_ROTATION=delete`: delete-on-use through `DELETE … RETURNING`, so any second presentation of the same token — a concurrent refresh or a retry after a lost response — gets a generic 401. Opt-in, `AUTH_REFRESH_ROTATION=grace`: a retry inside `AUTH_REFRESH_ROTATION_GRACE_SECONDS` gets the same successor while that successor is still the family's live head (so does a thief: reuse detection is off inside the window) and a plain 401 once it is not, and an unexpired replay after the window revokes the token family (every session of the user under `AUTH_REFRESH_REUSE_SCOPE=user`). `grace` needs the module's schema columns, an `UPDATE` grant on `refresh_tokens` and a transactional (non-autocommit) session, and switching back to `delete` needs the README's cleanup `DELETE` first — read its costs in the module README's § Gotchas before enabling it.
- Deleting the refresh token ends the session — no new access tokens issue. Under `grace` a session is a token family: revoke the whole family, never one row (as `POST /auth/logout` does when it is handed the refresh token), and a sessions screen lists only `rotated_at IS NULL` rows. For instant revocation of the outstanding access token, the vendored lib SHIPS the JWT `jti` denylist (short-TTL, Redis) — wire it, don't rebuild it; it is part of the canonical lifecycle, not an optional bolt-on.
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
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- `POST /auth/passwordless/request` is ALREADY capped per email and per IP in Redis by the library (`AUTH_PASSWORDLESS_REQUEST_CAP`, `AUTH_PASSWORDLESS_IP_REQUEST_CAP`): tune those, add no second limiter, and never answer it with 429 — it returns 202 either way, so throttling never reveals an account. `POST /auth/passwordless/verify` has a per-code attempt cap (`AUTH_PASSWORDLESS_ATTEMPT_CAP`) but no per-IP bound; the project adds that bucket.
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/merge_request.py, tests/test_merge_ledger_driver.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/45-testing-strategy.md  (hit: tests/test_merge_ledger_driver.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 81 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `AUTH_REFRESH_ROTATION` `delete` `grace` `jti` `email` `AUTH_EMAIL_CLAIM` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `AUTH_REFRESH_ROTATION` `AUTH_REFRESH_ROTATION=delete` `DELETE … RETURNING` `AUTH_REFRESH_ROTATION=grace` `AUTH_REFRESH_ROTATION_GRACE_SECONDS`
- `grace` `POST /auth/logout` `rotated_at IS NULL` `jti`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `POST /auth/passwordless/request` `AUTH_PASSWORDLESS_REQUEST_CAP` `AUTH_PASSWORDLESS_IP_REQUEST_CAP` `POST /auth/passwordless/verify`
- `expo-secure-store`
```

## Pass Ledger

| Pass | seats · scope | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice A: constraints, phases, contracts, digest) + sonnet×1 (slice B: header, intake, evidence, self-audit) · shape: agent-tool · full pass | found: 19, new: 19, confirmed: 14, fixed: 14, unexecuted: 0 | method: citation — full pass; seats executed the prototype tests red and green and the installer seam | 04f7a28e… → f582154c… |
| Pass 2 | the round-1 seats on their own slices · the round-1 fix hunks | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — anchors re-read at HEAD, E2 probe re-run, refusal fixture executed through `_merge3`, installer copy run through its seam | f582154c… → 13c0e195… |
| Pass 3 | the round-1 seats on their own slices · the round-2 fixed set | found: 2, new: 2, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — spec vs loose duplicate rule executed (spec {5}, loose set()); `_build` :1223 guard read; scope-growth stop fired | 13c0e195… → 6603f9d0… |
| Pass 4 | opus×1 (slice A owner) · the round-3 fix only; standing clean since pass 3: slice B | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the discriminating fixture executed: `_merge3` keeps both rows, spec rule {5}, loose rule set() | 6603f9d0… → 6603f9d0… ✓ |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners of slices A and B) · the Opus+Fable panel revision | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0 | method: re-derivation — the clone's config probed (`--shared` copies none), mypy run on the untouched file (2 errors, by message), the hooks-index anchor grepped (bold), the Self-audit read against I5 | 6603f9d0… → 637f3e35… |
| Pass 6 | opus×1 (slice A owner) · the round-5 fixed set only; standing clean since pass 5: slice B and every other class | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the three fixed sentences re-checked: clone config probe, mypy messages matched word for word, the bold hooks-index anchor grepped (1 match) | 637f3e35… → 637f3e35… ✓ |

Plan-approval panel: opus="VERDICT: sound-with-changes — docs/development/plans/2026-10-31-plan-1-ledger-merge-driver.md" fable="VERDICT: sound-with-changes — docs/development/plans/2026-10-31-plan-1-ledger-merge-driver.md" → both-approve (every concern ACCEPTED, folded in pass 5 and verified by passes 5-6).
