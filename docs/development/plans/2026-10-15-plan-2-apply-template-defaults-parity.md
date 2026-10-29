# Plan — fabrik apply loads specs the way fabrik plan does

Status: EXECUTED
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-15-apply-template-defaults-parity-design.md` (Size: small; flips to CONVERGED
with this plan at `/fabrik-plan-review`'s approval gate). Work item: W-989653a7. Decisions: D-733, D-907.

## Global Constraints

- Python 3 with type hints on every function signature (`.windsurf/rules/core/10-python.md:160`).
- One test per user-observable behaviour, each seen red before green (`.windsurf/rules/core/45-testing-strategy.md:20-22`).
- No VPS mutation, no `fabrik apply`/`fabrik plan` as a gate (hub-side CLI; gates are pytest and inspection).
- Spec values win over template defaults on every key (`_deep_merge`, `src/fabrik/spec_loader.py:1071-1091`).
- Shared-tree discipline: explicit pathspecs, provenance trailers, never `git add -A`, never stash.
- 12-Factor non-negotiables inherited (no logfiles, config in env vars, no secrets in code); this change touches
  none of them — it reads YAML files in the hub repo only.

## Constraints Digest

| Quote | Source |
|---|---|
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |
| Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. | `.windsurf/rules/core/45-testing-strategy.md:20` |
| A green test never seen red is unverified — a suite can pass with its guard deleted. | `.windsurf/rules/core/45-testing-strategy.md:22` |
| is never the only thing between the agent and an irreversible act. | `.windsurf/rules/ai/50-agentic.md:49` |
| tune the caps (daily_budget_usd, daily_invocations_cap), never the switch | `.windsurf/rules/core/60-watchdog.md:27` |
| Never invent a step. Never skip a step. | `.windsurf/rules/core/self-healing.md:11` |
| Fenced code blocks only — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` |

ai/50-agentic, core/60-watchdog and core/self-healing match by glob only (`src/fabrik/orchestrator/`, `tests/orchestrator/`,
`specs/services/`): this plan adds no agent loop, changes no `watchdog:` block and no healing ladder, so their rows bind
as "nothing to violate" — adjudicated in the Coverage Checklist. core/40-documentation matches the review receipt.

## Context Ledger

- Packs: the six MATCHED above plus the FLOOR set the rubric injects (`core/35-security-auth`, `core/25-data-postgres`,
  `core/30-ops`, 12-Factor) — none of their surfaces is touched (no auth, DB, ops or runtime config change).
- fabrik-lib: none (spec § fabrik-lib verdict).
- `shape.*` flags read: `exposes_metrics`, `is_public` (pinned / overridden in Phase B); `infra.gatus` (the negative
  override, `src/fabrik/spec_loader.py:906-920`).
- The apply path writes `spec["env"]` into the VPS `.env` (`src/fabrik/orchestrator/deployer_ssh.py:898-903`) — which is
  why apply merges the template's `shape:` block only (D-908).

## Phase A — pins first, then one merge helper on the apply path

✅ EXECUTED 2026-10-17 (2935ce9f6; review fixes 6dae6d526)

Appetite: 50

**Files:** `specs/services/translator.yaml`, `specs/services/longephedia-vault.yaml`,
`specs/services/fabrik-citation-verifier.yaml`, `specs/services/fabrik-claim-validator.yaml` (pins — they land FIRST,
in this phase, because under today's raw loader they change nothing on apply and only make `fabrik plan` honest; so no
commit of this plan ever leaves a live spec unpinned behind the merging loader — D-733's "same change") ·
`src/fabrik/spec_loader.py` (the helper, `load_spec` calls it) · `src/fabrik/orchestrator/validator.py`
(`SpecValidator.load_spec` returns the shape-merged dict) · `src/fabrik/orchestrator/infrastructure.py`
(`_shared_db_siblings`, the other raw reader of spec files on the apply path, `:575-612`) ·
`tests/orchestrator/test_validator.py` (unit graders) · `tests/orchestrator/test_shared_db_siblings.py` (new). The
inline executor (this plan is `Profile: small`, so the orchestrator codes it) also writes the `CHANGELOG.md` entry
(step 6) and the root `INDEX.md` row (Finish step 1) — governance files, which `check_plan_tickets.py::GOVERNANCE_FILES`
keeps out of File Scope.

**Interfaces — Produces:** `fabrik.spec_loader.merge_template_defaults(raw: dict[str, Any], templates_dir: Path | None =
None, keys: tuple[str, ...] | None = None) -> dict[str, Any]` — reads `<templates_dir>/<raw["template"]>/defaults.yaml`
when `raw["template"]` is a non-empty `str` and the resolved FILE path lies inside the resolved `templates_dir`
(`Path.is_relative_to`, the same escape `src/fabrik/orchestrator/validator.py:250-258` refuses for the template
directory) and parses to a mapping; keeps only the top-level keys named in `keys` (all keys when `None`); returns
`_deep_merge(defaults, raw)` (the spec wins), otherwise `raw` unchanged. `templates_dir` defaults to
`FABRIK_ROOT / "templates"`. **Consumed by:** `spec_loader.load_spec` (`src/fabrik/spec_loader.py:1051-1066`, all
keys — behaviour unchanged except that a template escaping `templates_dir` now merges nothing),
`SpecValidator.load_spec` (`src/fabrik/orchestrator/validator.py:183-207`, `keys=("shape",)`), whose production
caller is `SpecValidator.load_and_validate` (`validator.py:340`) ← `Orchestrator`
(`src/fabrik/orchestrator/__init__.py:137`, `:481`), and `_shared_db_siblings`
(`src/fabrik/orchestrator/infrastructure.py:600-609`, `keys=("shape",)` on each sibling's data before it reads
`shape.needs_database`).

**Behavior Contract (Phase A):**
- **Given** a spec with `template: python-api` and no `shape:` block **When** `SpecValidator(templates_dir=<tmp>).load_spec` loads it and `<tmp>/python-api/defaults.yaml` sets `shape.exposes_metrics: true` **Then** the returned dict carries `shape.exposes_metrics: true`
- **Given** a spec that sets `shape.exposes_metrics: false` **When** it is loaded through the validator over the same defaults **Then** the returned value is `false` (the spec wins)
- **Given** `<tmp>/python-api/defaults.yaml` also sets `env.LOG_LEVEL: INFO` and the spec has no `env:` **When** the validator loads it **Then** the returned dict has no `env.LOG_LEVEL` (apply never writes a template env key)
- **Given** a spec whose `template` resolves outside `templates_dir` (`../evil`) with a `defaults.yaml` there **When** `merge_template_defaults` runs **Then** the raw spec is returned unchanged
- **Given** a sibling spec in the same directory whose `needs_database: true` comes only from its template, naming the same database **When** `_shared_db_siblings` scans for a shared database **Then** it reports that sibling

Steps:
1. Pin the four live specs: inside each one's `shape:` block add `exposes_metrics: false` with a one-line comment
   (`# no /metrics route in this repo's code (grep 2026-10-15, D-907) — delete this line to opt in once it serves
   one`; translator's reads `# D-907: /metrics unverified, the repo is not on the hub — delete to opt in`, because no
   grep of its code was possible); translator.yaml gets `infra:\n  gatus: false` with the comment `# D-907: no Gatus
   check until the owner confirms translator.vps1.ocoron.com/health — delete to opt in`.
2. Write the five graders first — rows 1-4 in `tests/orchestrator/test_validator.py`, each with its own `tmp_path`
   templates dir, named `test_template_defaults_*`; row 5 in `tests/orchestrator/test_shared_db_siblings.py`, named
   `test_shared_db_*`, over a `tmp_path` spec directory whose sibling uses `template: saas-skeleton` (the only template
   whose defaults set `needs_database: true`; the sibling scan reads the real `templates/`, so a tmp templates dir
   would be ignored there) — importing `merge_template_defaults` INSIDE the test bodies (a module-top import would
   fail collection for all).
   Run `.venv/bin/python -m pytest tests/orchestrator/test_validator.py tests/orchestrator/test_shared_db_siblings.py -q -k "template_defaults or shared_db"`
   → rows 1, 4 and 5 FAIL (row 1: the raw loader returns no `shape`; row 4: `ImportError`, no helper yet; row 5: the
   raw sibling read misses the template's `needs_database`); rows 2 and 3 pass on the raw loader and are seen red on
   mutants (b) and (c) in step 5.
3. In `src/fabrik/spec_loader.py`, add `Any` to the `typing` import (line 10 imports only `Literal`), move the merge
   block of `load_spec` (`:1051-1066`) into `merge_template_defaults` (typed, docstring citing G-B1a, D-733 and
   D-908), with the containment check and the `keys` filter, and make `load_spec` call `raw = merge_template_defaults(raw)`.
4. In `src/fabrik/orchestrator/validator.py::SpecValidator.load_spec`, after the mapping check, `return
   merge_template_defaults(spec, self.templates_dir, keys=("shape",))`; in
   `src/fabrik/orchestrator/infrastructure.py::_shared_db_siblings`, pass each sibling's `data` through
   `merge_template_defaults(data, keys=("shape",))` before it reads `shape` — inside the existing `try` at
   `infrastructure.py:599-605`, so a malformed sibling template still raises `AppRoleRefusalError` — and update the two
   docstrings that say the apply path reads the RAW spec (`infrastructure.py:232`, `:519`) (imports from `fabrik.spec_loader`, which
   imports only `fabrik.config` from the package — `spec_loader.py:8-15` — so no cycle; the step-5 pytest run is the
   import proof, because a bare `.venv/bin/python -c` in this worktree imports `/opt/fabrik/src`, not the edit).
5. Gate: `.venv/bin/python -m pytest tests/orchestrator tests/test_spec_loader.py tests/test_reconcile_all_deployed_set.py tests/test_state.py -q` → all pass.
   Then red-on-revert for this phase's graders, in a throwaway worktree: `git worktree add <run scratch>/probe-a HEAD`,
   then copy Phase A's edited and new files into it (a HEAD checkout lacks this phase's uncommitted edits), every
   grader run from inside it, one mutant at a time, restored after each: (b) `_deep_merge(raw, defaults)` (arguments swapped) → row 2 fails; (c)
   `keys=None` in the validator → row 3 fails; (e) the containment check removed → row 4 fails (its
   `../evil/defaults.yaml` now merges); (f) the sibling merge line removed → row 5 fails. Re-run green.
6. Add `### Fixed — fabrik apply resolves the same registrars as fabrik plan (2026-10-15)` atop `CHANGELOG.md`
   `[Unreleased]`; stage Phase A's files with it; `python3 scripts/enforcement/check_doc_sync.py` → exit 0 (it reads the
   staged diff and refuses a staged `.py` change without `CHANGELOG.md`).
7. `/fabrik-review-scoped` on Phase A's diff (the `Profile: small` per-phase review) → its coverage-adjudicated exit;
   commit Phase A (explicit paths + trailers, `Agent-Phase: A`).

## Phase B — the parity graders

✅ EXECUTED 2026-10-17 (ce84cebf8; review fixes 7df3c97b4, 9ac74a948)

Appetite: 30

**Files:** `tests/orchestrator/test_apply_plan_parity.py` (new: the parity, validate-parity, kind-agreement, frozen
pin and template allow-list graders).

**Interfaces — Consumes:** `merge_template_defaults` via `SpecValidator.load_spec` (Phase A);
`resolve_applicability` (`src/fabrik/orchestrator/infrastructure.py:261`); `destroyer._spec_to_dict`
(`src/fabrik/orchestrator/destroyer.py:116-125`); `spec_loader.load_spec`; `SpecValidator.validate`
(`src/fabrik/orchestrator/validator.py:209`).

**Behavior Contract (Phase B):**
- **Given** every spec in `specs/services/` **When** its registrars are resolved from `SpecValidator().load_spec` and from `_spec_to_dict(spec_loader.load_spec)` **Then** the two resolutions are equal, reason strings included
- **Given** every spec in `specs/services/` **When** `SpecValidator.validate` runs on the raw and on the shape-merged dict **Then** both raise the same error or neither raises
- **Given** the four live specs translator, longephedia-vault, fabrik-citation-verifier and fabrik-claim-validator **When** apply resolves their registrars **Then** each one's set of running registrars equals a frozen expectation (today's: translator glitchtip, grafana, postgres, watchdog; longephedia-vault gatus, glitchtip, grafana, watchdog; fabrik-citation-verifier backrest, gatus, glitchtip, grafana, postgres, watchdog; fabrik-claim-validator gatus, glitchtip, grafana, postgres, watchdog)
- **Given** every spec in `specs/services/` **When** its top-level `kind` is compared with its template's `shape.kind` **Then** none differs without a `shape.kind` of its own
- **Given** every `templates/*/defaults.yaml` **When** its `shape:` keys are read **Then** they are a subset of the allow-list of the nine keys templates set today (`exposes_metrics`, `has_bearer_api`, `has_persistent_data`, `has_search_feature`, `is_admin_dashboard`, `is_public`, `kind`, `needs_cache`, `needs_database`) and none sets `is_admin_dashboard: true` or `uses_claude_cli`

Steps:
1. Write `tests/orchestrator/test_apply_plan_parity.py` with the five graders, parametrized over
   `sorted((REPO / "specs" / "services").glob("*.yaml"))` where `REPO = Path(__file__).resolve().parents[2]` (cwd-proof),
   with a module-level assertion that the list is non-empty; a raise from either loader is a FAILURE, never a skip
   (0 of 69 specs is refused today). The validate-parity and kind-agreement checks are helpers (`_validate_mismatch`,
   `_kind_disagrees`) so their positive controls can call them.
2. Gate: `.venv/bin/python -m pytest tests/orchestrator -q` → all pass;
   `python3 scripts/enforcement/check_spec_db_match.py` → no new warning.
3. Red-on-revert, in a throwaway worktree (`git worktree add <run scratch>/probe-b HEAD`, every grader run from inside
   it), one mutant at a time, restored after each: (a) Phase A's validator line reverted to `return spec` → the parity
   grader fails on 12 specs (11 by booleans plus translator by reason string; measured on a pinned scratch copy) — the
   frozen pin grader stays green under (a), because the pins land first and the frozen sets are what the raw loader
   resolves with them; (d) one pin deleted → the frozen pin grader fails for that spec; (g)
   `is_admin_dashboard: true` written into one template's defaults → the allow-list grader fails. Re-run green.
   Kept positive controls for the two graders no live spec can redden (every one of the 69 carries a domain or an
   explicit kind, and none disagrees with its template's kind): `_validate_mismatch` on a synthetic spec — `name:
   synth`, top-level `kind: worker`, `template: python-api`, no `shape:`, no `domain:` — reports a mismatch (raw
   validates; shape-merged raises `Missing required field: domain`); `_kind_disagrees` on the same spec reports a
   disagreement. Both are test cases in the same file asserting the report.
4. Stage Phase B's file; `python3 scripts/enforcement/check_doc_sync.py` → exit 0.
5. `/fabrik-review-scoped` on Phase B's diff → its coverage-adjudicated exit; commit Phase B (explicit paths +
   trailers, `Agent-Phase: B`).

## Finish

1. Root `INDEX.md` rows for `tests/orchestrator/test_apply_plan_parity.py` and `tests/orchestrator/test_shared_db_siblings.py`.
2. The ONE heavy round: `/fabrik-review` over the whole-plan diff (the `/fabrik-execute-plan` D7 floor: ≥1 Opus
   authoritative seat + one Sonnet and one Haiku seat per failure-class group, seats from
   `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>`, stamped first), receipt
   `docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md`;
   `python3 scripts/enforcement/check_doc_sync.py --range <phase A parent>..HEAD` → exit 0.
3. `python scripts/final_gate.py --check --json` → `"status": "success"`, and
   `python scripts/enforcement/check_convergence.py` → clean. A green gate is necessary, not sufficient: the proof
   is the parity grader's red-on-revert.
4. Flip this plan to `Status: EXECUTED`; merge request to the coordinator.

## File Scope (owned paths)

- src/fabrik/spec_loader.py
- src/fabrik/orchestrator/validator.py
- src/fabrik/orchestrator/infrastructure.py
- tests/orchestrator/test_validator.py
- tests/orchestrator/test_shared_db_siblings.py
- tests/orchestrator/test_apply_plan_parity.py
- specs/services/translator.yaml
- specs/services/longephedia-vault.yaml
- specs/services/fabrik-citation-verifier.yaml
- specs/services/fabrik-claim-validator.yaml
- docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md

## Evidence

Phase A — the two loaders, read: `src/fabrik/spec_loader.py:1051-1066` (merge), `src/fabrik/orchestrator/validator.py:183-207`
(raw). Phase B — the parity probe over every spec, executed 2026-10-15:

```
DIFF fabrik-citation-verifier.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-claim-validator.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-file-worker.yaml {'backrest': 'apply=False plan=True'}
DIFF longephedia-vault.yaml {'prometheus': 'apply=False plan=True'}
DIFF translator.yaml {'gatus': 'apply=False plan=True', 'prometheus': 'apply=False plan=True'}
... (10 test/gate fixture DIFF lines elided)
15 of 69 specs differ
```

The shape-only merge (D-908), prototyped on the validator, nothing written:

```
$ .venv/bin/python <run scratch>/proto_shape.py
69 specs; registrar diffs (bool+reason) 0; env changed 0; validate() outcome changed 0
```

A FULL merge on apply would instead add template `env:` keys to all 69 specs (round-1 Opus seat, `gain.py`: e.g.
`gmail-account-creator` gaining file-worker's `JOB_TYPES`), which `deployer_ssh.py:898-903` would write into each
app's `.env`. Phase B step 3's revert count, measured on a pinned scratch copy (`revert_count.py`):

```
boolean 11 ['fabrik-e2e-test', 'fabrik-file-worker', 'fabrik-smoke-test', 'fabrik-test-node-api', 'fabrik-test-python-api', 'gate-saas', 'gate-test', 'test-no-db', 'test-pg-no-db', 'test-pg-with-db', 'test-with-db']
full 12 ['translator']
```

Reader census (the function whose behaviour changes is `SpecValidator.load_spec`; `spec_loader.load_spec` changes only
for a template escaping `templates_dir`):

```
$ command grep -rn "\.load_spec(\|load_and_validate(" src scripts --include=*.py | command grep -v "def "
src/fabrik/orchestrator/validator.py:340:        spec = self.load_spec(spec_path)
src/fabrik/orchestrator/__init__.py:137:            spec, spec_hash, warnings = self.validator.load_and_validate(spec_path)
src/fabrik/orchestrator/__init__.py:481:        spec, spec_hash, warnings = self.validator.load_and_validate(spec_path)
$ command grep -rln "load_and_validate\|SpecValidator" tests --include=*.py
tests/orchestrator/test_integration.py
tests/orchestrator/test_refresh_infrastructure.py
tests/orchestrator/test_pre_provision_db.py
tests/orchestrator/test_validator.py
tests/orchestrator/test_e2e_rollback.py
tests/test_reconcile_all_deployed_set.py
tests/test_state.py
```

All seven test files run in Phase A step 5 (`tests/orchestrator` covers five; the other two are named in its gate).
External grounding (Prometheus `up`/scrape-status, Helm, Terraform, HashiCorp drift) is in the spec and its ledger
`docs/reference/research/2026-10-15-apply-template-defaults-ledger.md`.

## Coverage Checklist

| Class | Verdict |
|---|---|
| core/10-python.md — type hints on every signature | FIXED r1 (Phase A step 3 types the helper and adds the missing `Any` import, `spec_loader.py:10`) |
| core/45-testing-strategy.md — one test per behaviour, seen red | FIXED panel (Phase A's mutants (b), (c), (e), (f) run inside Phase A before its commit; Phase B's (a), (d), (g); the validate-parity and kind-agreement graders carry kept positive controls) |
| core/40-documentation.md — the review receipt | CLEAN (heading levels unskipped in the receipt and this plan; fenced blocks only) |
| core/60-watchdog.md, core/self-healing.md, ai/50-agentic.md — matched by glob on specs/ and orchestrator/; no watchdog or agentic surface changes | CLEAN (no `watchdog:` key, agent loop or healing ladder in the File Scope's edits) |
| Recurrence: fail-open/fail-closed | FIXED r1 (a loader raise is a parity FAILURE, never a skip; an escaping template merges nothing and leaves the raw spec) |
| Recurrence: cost/quota accounting | CLEAN (no metered call; two native seats stamped with dispatch --seats 2) |
| Recurrence: boundary/sentinel/prefix | FIXED r1 (empty parametrize asserted non-empty; containment on the resolved file path; template `.` finds no defaults) |
| Recurrence: behavior-without-a-test | FIXED r1 (env stays raw and validate() parity each gain a grader; a full merge would have changed every spec's `.env` untested) |

`$ python3 scripts/review_rubric.py --changed src/fabrik/spec_loader.py src/fabrik/orchestrator/validator.py src/fabrik/orchestrator/infrastructure.py tests/orchestrator/test_validator.py tests/orchestrator/test_shared_db_siblings.py tests/orchestrator/test_apply_plan_parity.py specs/services/translator.yaml specs/services/longephedia-vault.yaml specs/services/fabrik-citation-verifier.yaml specs/services/fabrik-claim-validator.yaml docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md` (all eleven File Scope paths, run from the repo root, 2026-10-15):

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

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
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
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

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/infrastructure.py, src/fabrik/orchestrator/validator.py, tests/orchestrator/test_apply_plan_parity.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: src/fabrik/orchestrator/infrastructure.py, src/fabrik/orchestrator/validator.py, src/fabrik/spec_loader.py)
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

### core/40-documentation.md  (hit: docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_apply_plan_parity.py, tests/orchestrator/test_shared_db_siblings.py, tests/orchestrator/test_validator.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
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

### core/60-watchdog.md  (hit: specs/services/fabrik-citation-verifier.yaml, specs/services/fabrik-claim-validator.yaml, specs/services/longephedia-vault.yaml)
- AGENT USAGE: Vendor watchdog/emitter/ into projects that need watchdog catch. Never call the sidecar from main app — emit incidents to the inbox instead. Don't put secrets in details. -->
| any `kind` — `service`, `worker`, `wordpress`, `static` | **on** | tune the caps (`daily_budget_usd`, `daily_invocations_cap`), never the switch |
- ⚠️ **This table previously claimed a shape-driven default** (`python-api`/`node-api` conditional on `is_admin_dashboard` OR `has_persistent_data`; `static-site`/`docusaurus` off). That was **never what the resolver did** — `resolve_applicability` is a one-line unconditional `watchdog_cfg.get("enabled", True)` with **no `kind` test at all** (`orchestrator/infrastructure.py`:359-373, whose own comment says the matrix here "stays operator discipline, not encoded behaviour"). So the table described a discipline, not a behavior, and the discipline is now superseded. Anything relying on the old rows — including a spec comment justifying an opt-out — is stale.
**Make it project-specific** — set `watchdog.project_system_prompt_file: docs/WATCHDOG_PROMPT.md` (project-relative Markdown, ≤32 KB). The driver injects its contents as `WATCHDOG_SYSTEM_PROMPT`; the sidecar appends it as a `## This project` section *after* the canonical veteran-sysadmin prompt (rails never replaced). Use it to teach the watchdog THIS app's architecture, failure modes, what "healthy" means, and hands-off zones. **Fail-soft:** a missing / unreadable / oversized / absolute / `..`-escaping path is ignored (logged warning) and the sidecar runs the canonical prompt only — a prompt-file problem never disables the watchdog or blocks the deploy, and a bad path is never read. Commit the prompt file to the repo before `fabrik apply` (the driver reads it hub-side at render).
- `/opt/<project_id>/` (RO) — the project tree for `Read`/`Grep`/`Glob`. This is the `/project` mount the fix lane reads conventions from (`.windsurf/rules/*` + `CLAUDE.md` are gitignored, so a bare clone would lose them); code changes materialize into a writable scratch worktree, never the RO mount.
- Per-project by design: each sidecar's DSN reaches ONLY its own DB (a compromised RO cred can't read another tenant). Password lifecycle mirrors `DATABASE_URL`: a fresh password is minted + injected only when a role is newly created; an existing role is preserved (no rotation), so its `.env` DSN stays valid and a cached-image re-apply never breaks a running sidecar. The batch runs under `\set ON_ERROR_STOP on` (failures raise, never false-succeed); grants are re-applied every apply (idempotent — covers newly-added tables); `ALTER DEFAULT PRIVILEGES` targets the real DB owner (looked up from `pg_database.datdba`, omitted when unresolvable), so it works on postgres-owned legacy DBs. Roles are non-owner / non-superuser (least privilege) — on `FORCE ROW LEVEL SECURITY` tables the RO lane sees only policy-permitted rows; a multi-tenant app needing cross-tenant diagnosis adds a policy for `{db}_wd_ro` upstream. Teardown: `drop_database` also drops the two roles (`DROP ROLE IF EXISTS`, on both the DB-present and already-gone paths) so a drop+recreate never orphans them; a provisioning failure surfaces as a `watchdog-db-roles` entry in the deploy resource summary (not just a log warning). (Distinct from the shared, manual `scripts/provision_watchdog_ro.py` escape hatch, which this supersedes for the auto path.)
- 4. Per incident: cost-cap check (ops-only path — see the ⚠️ below) → LLM diagnose (Claude Code primary, OpenRouter fallback) → action dispatch → **if code-class and Tier-D enabled: generate+test fix → Telegram-gate → apply via deploy adapter → verify/rollback → record**; else record → escalate if Tier C. ⚠️ With `auto_code_fix` on, the coordinator diagnoses with no cap check and records neither the diagnosis nor its fix runs — the daily caps do not bound Tier D (`core/cost-budget.md` § The Watchdog's Caps; filed to fabrik-lib).
**Tier A** — no `auto_tier_b` needed. `restart_container` is always offered; `clear_file_cache` and `pause_worker` only once listed in `watchdog.llm_actions`; `scale_concurrency` is never offered (fabrik-lib SB-103). Bounded by the daily caps (`daily_budget_usd`, `daily_invocations_cap`) on the ops-only path; `per_incident_budget_usd` is accepted and ignored (§ Cost behavior).
| `scale_concurrency` | env edit + `compose up -d <main>` | Never offered to the model (fabrik-lib SB-103) — not an `llm_actions` entry; CONST_CASE env-key validation |
- ⚠️ **`drop_queue_items` and `rotate_locks` are NO LONGER Tier A** — the module moved them to the Tier-C **approved-write lane** (`actions.py::TIER_C_WRITE_HANDLERS`), fail-closed behind TWO gates: `WATCHDOG_ALLOW_DB_WRITES` (default OFF) and a provisioned `WATCHDOG_DB_URL_RW`. Absent either, the handler returns `skipped`, not a mutation. § Architecture already said this ("Consumed only by the Tier-C approved-write lane"); this table had not caught up, so the pack promised two automatic DB-mutating actions that are impossible by default. Both are also never offered to the model (fabrik-lib SB-103, `actions.py::NEVER_OFFERED`), so today neither runs even with both gates open.
| `install_log_drop_rule` | Add regex drop to promtail via hub update service | Never offered to the model (being retired, fabrik-lib SB-095) — not an `llm_actions` entry; refuses too-broad patterns (`.*`, `.+`, `^.*$`) |
**Tier D** — code-remediation, **off by default**, opt-in like B/C and **human-gated**. This is the only tier that can change running code, and it never does so silently.
| `create_fix_pr` | the dispatch key the coordinator's code-class fork reads (`coordinator.py::_is_code_fix`), routing the incident to REMEDIATE — there is no separate Tier-D action key, and the fork runs only for a trigger-bus signal (`trigger_sources` + `critical_paths`, [self-healing § Tier D](self-healing.md)); the always-on poll path never offers it (`agent.py` builds its menu with `code_fix_enabled=False`, so `check_proposal` refuses a reply naming it — fabrik-lib D-412); on the trigger-bus lane the chain is: generate a fix on `watchdog/<incident_id>` → tests pass (**HARD gate**) → secret-scan the diff → blast-radius guard → Telegram the diff with **Approve / Reject / STOP** → on approval **OR** silence past `code_fix_window_sec` → `deploy_adapter.apply(branch)` → VERIFY health → **auto-rollback on regression** | Isolated clone only (never the RO `/project` mount); deploy mechanism **injected** (no in-place src edit); every apply/rollback written to the `deploys` audit table; push restrictions apply to the **LLM's own bash** (hook + settings deny-list: no main/master, no force-push, no `git config`/`rebase`/`reset --hard`/`tag`); the **deploy adapter is the sole sanctioned main-push path** — it merges the fix branch into `deploy_branch` (default `main`) and uses `--force-with-lease` ONLY on rollback |
- ⚠️ **We chose the MINORITY convention on silence, deliberately — know what it rests on.** The prevailing pattern in published autonomous-remediation designs is **"silence is denial"**: an approval request that times out resolves to REJECTION, and an unanswered approval never converts into consent. Ours is the inverse — `TIMEOUT` routes through the same branch as `APPROVE` and the fix deploys. That is defensible here for a specific reason: this fleet is unattended, so silence-as-denial would mean a green-tested fix for a live incident simply never lands, and the incident continues. But the inversion is only safe while THREE things hold, and all three are load … (wrapped further — read the pack)
- **No response within `code_fix_window_sec`** (default **300 s**, spec range 60–3600; D-378) → treated as approval and applied. A fix that silence can auto-apply has already passed the tests, the secret scan and the blast-radius guard; it deploys only after a pre-apply snapshot marker is recorded, and rolls back to the previous code ref when post-apply health (or the opt-in golden check) regresses — so the default is short. Rollback catches a health regression and, where a golden file covers it, a known-answer regression; a wrong fix that passes both is never caught, so a project that wants a longer human review sets the field explicitly. It IS the operator-bound terminal (see [self-healing](self-healing.md) acceptance checklist), not a fully-autonomous layer.
- **Per-incident cost.** ⚠️ NOT enforced by a `--max-budget-usd` flag — that is explicitly banned (`llm_client.py`: *"no $ caps on sysadmin"*, per the operator directive that per-call caps break the diagnose loop), and `per_incident_cap_usd` is accepted for API compatibility but not enforced at the call site. Spend is OBSERVED (`total_cost_usd` from the Claude envelope) and bounded by the daily caps, not clipped mid-incident. OpenRouter fallback timeout is 60s.
- **Bypassing the PreToolUse hook.** Hook + claude-settings allow-list + sandbox.filesystem + docker.sock scoping are 4-layer defense-in-depth. If you "just need" to let Claude run an arbitrary `bash` command, the right move is to add the command to claude-settings.json — never `chmod -x` the hook.
- **Editing `/opt/<id>/src` in-place from the sidecar.** In-place src editing from the sidecar is still **banned** — code changes go through the isolated workspace + injected deploy adapter. **Without Tier-D opt-in, watchdog never merges** (operator merges, via the PR workspace at `/var/lib/watchdog/proposed/<project_id>/` pushed to `watchdog/<incident_id>`). **With Tier-D**, watchdog MAY apply a tested, secret-scanned, blast-radius-clean fix via the deploy adapter after explicit Telegram approval or a configured silence window, with auto-rollback armed and a STOP kill-switch.
- fleet-AI blind spot — the deploy agent cannot reason about a container it has never been told about.
- ⚠️ Measured 2026-09-01: `tryton-crm` runs `tryton-crm-watchdog` (up, healthy) and **neither** its `OPERATIONS.md` nor its `DEPLOYMENT.md` mentions a watchdog at all. So this is the live default, not a hypothetical.

### core/self-healing.md  (hit: specs/services/fabrik-citation-verifier.yaml, specs/services/fabrik-claim-validator.yaml, specs/services/longephedia-vault.yaml)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `scale_concurrency`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
| 11 | **Postgres allocation registry drift** (HUB-side, not a service: a database in `pg_database` with no `allocations.json` entry) | the hourly drift cron (`scripts/audit_all_registrars.py`) finds a database no registry row claims | Additive reconcile (`src/fabrik/registry_reconcile.py`, D-500): registers it in-lock, never overwrites or deletes; `report` (writes nothing) unless the cron line sets `FABRIK_REGISTRY_RECONCILE=apply` | Refuse, never guess, and write nothing: a name two specs claim is counted as `fabrik_registry_heal_total{outcome="shared"}`; any other refusal (an incomplete claim map, an unresolved owner, an error) as `fabrik_registry_heal_failed{spec_id,db,reason}` | `FabrikRegistryHealFailed` (a `heal_failed` refusal standing 2 h; a shared claim alerts on neither) or `FabrikAuditStale` (no clean audit run in 3 h, or none recorded) — `configs/prometheus/rules/fabrik-drift.yml` |
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- **What the sidecar can execute today:** the model returns each action with its params, and `check_proposal` refuses anything off the offered menu, or with a bad or missing param, before a side effect (fabrik-lib D-412). The model's menu is `restart_container` + `escalate_apprise` until the spec lists more in `watchdog.llm_actions` (fabrik-lib D-412): `clear_file_cache` and `pause_worker` (Tier A) run once listed; `wipe_redis_cache` and `reset_db_pool` (Tier B, port defaulting to 8000) run once listed AND `auto_tier_b: true`. `scale_concurrency`, `drop_queue_items`, `rotate_locks` and `install_log_drop_rule` are never offered, and `create_fix_pr` has its own lane (`propose_fix_prs`) — this ladder names three of the never-offered ones (`scale_concurrency` and `drop_queue_items` in row 2, `rotate_locks` in row 8): in those rows the watchdog step resolves to Tier C escalate plus the deadman restart. Treat each row's first response as the step that actually heals.
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it is unreachable today, above, so until upstream carries parameters the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.
- [ ] The per-project ladder does not count on a watchdog step that is never offered (`scale_concurrency`, `drop_queue_items`, `rotate_locks`): each such row's healing step is the app's own first response, and the doc says the watchdog step escalates. If the approved-write lane is wanted once it is reachable, the project `.env` sets `WATCHDOG_ALLOW_DB_WRITES=true` and the RW DSN is provisioned.
# promote-to-check_* tail ELIDED (21 lines) — the full output is regenerated by the invocation above
```

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rule/grammar/grounding sections) + sonnet×1 (phases + narrative sections) · all axes · shape: agent-tool | found: 17, new: 16, confirmed: 16, fixed: 16, unexecuted: 0, edits: 24 | method: citation — full pass over both documents; held after execution: full merge writes template env into all 69 `.env` files (HIGH → D-908, shape-only merge), revert count 15→12 after pins, vacuous worktree import check, staged-only doc-sync step, spec-wins and env rows never seen red (mutants added), missing `Any` import, module-top import kills collection, empty-parametrize and loader-raise skip, dispatch_headroom path, state-dir count, D1 containment wording, validate() parity row, evidence elision, rubric over 4 of 9 paths, containment cite 250-258; refuted: Size: small over-count (YAML pins and tests are not code files, D-169); duplicate: the import check (both seats) | plan 9541363324443acf2470ffd316c1a5d5 → ae174b76ef0b7fb6985d2267791b8487 · spec 6b485cd886e5db7dc0bedb1a5ceec478 → 19668612f39f13253102dc0dd04ffee7 |
| Pass 2 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-1 fix hunks + one hop · shape: agent-tool | found: 4, new: 4, confirmed: 2, fixed: 2, unexecuted: 0, edits: 6 | method: re-derivation — both seats re-executed the shape-only prototype (69 specs, registrar diffs 0, env 0, validate() 0), the pinned revert count 12, mutants (a)-(d) and the registrar-key and template-key enumerations; held after execution (own-fix: round 1): the validate()-parity grader is never seen red by any mutant (a positive control on a synthetic spec added, executed: raw ok, merged raises Missing required field: domain) and Phase A row 4 is red only for the missing helper (containment-removed mutant (e) added); recorded: translator's pin comment claimed a grep its absent repo cannot have (wording corrected in Phase B step 2) and the scratch-copy pytest needs -o pythonpath=src (seat machinery) | plan 12ac757e5aad0d258b196d24f2d4865a → 51f8fdc20ca3815bcf74eb1d0fd30554 · spec 19668612f39f13253102dc0dd04ffee7 → 0af1692cd3bb20c5400d3995bde2aa75 |
| Pass 3 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-2 hunks + one hop · shape: agent-tool | found: 4, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 5 | method: re-derivation — both seats re-executed mutant (e), the positive control, plan's kind behaviour and the none-of-69 count; held after execution (own-fix: round 2): the control's synthetic spec lacked `name`, so both sides raised `Missing required field: name` (now `name: synth`, and `template: python-api` in the spec's copy — the Sonnet seat's in-hunk note, a duplicate), and 'the validate()-parity grader fails the build' overclaimed for a worker spec with `expose.http: false` (raw [] / merged []) — replaced by a kind-agreement assertion, executed 69 specs, disagreeing 0; recorded: the Pass-2 end md5 predates its own row's insertion (the ledger-in-plan rule) and plan-vs-apply validate() may differ for such a spec (acknowledged in hunk 3) | plan 86df418a2ff56355d1487a5d0814ffb0 → 06cd3a61db3b36ca71e7295d2ca6c34a · spec 0af1692cd3bb20c5400d3995bde2aa75 → a80160301ba90502eb1f34d4f1632ce4 |
| Pass 4 | opus×1 + sonnet×1 (round-1 slice owners) · closing re-verification of the round-3 fixed set (scope-growth stop in force) · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both seats re-executed the positive control (raw ok / merged Missing required field: domain), the kind-agreement count (69 specs, 0 disagreeing) and the round-3 counter-example (flagged although validate() passes both sides); standing clean since passes 1-3: citations, counts, executability, interfaces, mirror, spec-coverage, doc-sync, test-redness, env-blast-radius, worktree-import, grader-can-fail; flip gates run on a flipped throwaway worktree: check_convergence rc 0 (positive control: a planted UNCHECKED row → rc 1 naming this plan), check_spec_convergence 1 examined 0 findings, check_rule_grounding 6 examined 0 findings | plan 4c84dbecd9e551a33ea3db827b34324b → 4c84dbecd9e551a33ea3db827b34324b ✓ · spec a80160301ba90502eb1f34d4f1632ce4 → a80160301ba90502eb1f34d4f1632ce4 ✓ |
| Pass 5 | opus×1 + sonnet×1 (round-1 slice owners) · the ONE delta round over the design-approval panel's ten ACCEPTED changes · shape: agent-tool | found: 6, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 8 | method: re-derivation — both seats re-executed the frozen registrar sets (4/4 under raw, raw+pins, merged+pins and plan), the template key census (nine keys, no is_admin_dashboard true, no uses_claude_cli), the row-5 red claim (raw [] → merged ['sib.yaml']) and the pins-under-raw-loader no-op (4/4); held after execution (own-fix: the panel fold): mutant (a) cannot redden the frozen pin grader (pins land first), Phase A step 5's HEAD worktree lacks the uncommitted edits, the 10-python checklist row pointed at the renumbered step, the rubric omitted the two paths the panel added, and D2's reader list missed the Authelia bearer bypass (infrastructure.py:1395-1408, accepted as saas-skeleton's intent; 3 admin specs, raw equals merged); executor notes folded: fixed test names, the sibling merge inside the existing try, the two raw-spec docstrings | plan 42cf4745ca609c2f48e0294b13f8190c → d2eb7c5f81b9fd6afc1aad2246e481c4 · spec 7bdab68dc7fe6937e22e2254c530a26b → 01daa7d440a4b13cb28cc3da0812c579 |
| Pass 6 | opus×1 + sonnet×1 (round-1 slice owners) · closing re-verification of the round-5 fixed set (scope-growth stop in force) · shape: agent-tool | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both seats re-executed the frozen pin grader under mutant (a) (rawpin True 4/4), the eleven-path rubric (10 section headers identical), the Authelia bearer-bypass cite and the 3-admin-spec count, the try and docstring cites, the test-name filter and the saas-skeleton census; recorded — measured (own-fix residue after the scope-growth stop, destination Phase A step 4 at execution, W-989653a7): a non-mapping sibling file would raise AttributeError from the helper before the isinstance skip at infrastructure.py:606 (0 of 84 spec files is a non-mapping) — the builder guards the merge with `if isinstance(data, dict):`; recorded: the two infrastructure ranges 600-609 and 599-605 name different things (wording) | plan bcb6cf77d34abbec30c171039db851f7 → bcb6cf77d34abbec30c171039db851f7 ✓ · spec 01daa7d440a4b13cb28cc3da0812c579 → 01daa7d440a4b13cb28cc3da0812c579 ✓ |

## Self-audit

- (a) Coverage — spec § The delta D1 → Phase A step 3; D2 (validator and sibling scan) → Phase A step 4; D3 → Phase A
  step 1; the all-specs invariants (registrars, validate(), kind agreement) and the template allow-list → Phase B's
  graders; § Validation's unit, env, sibling, frozen-pin and red-on-revert graders → Phase A steps 2 and 5, Phase B
  steps 1 and 3. No gap.
- (b) Signatures — `merge_template_defaults(raw, templates_dir=None, keys=None)` is named identically in the spec,
  Phase A's Produces and Phase B's Consumes; the validator passes `keys=("shape",)`.
- Grounding passes: the parity probe, the full-merge and shape-only prototypes, the pinned revert count (executed);
  round 1's two seats re-ran the Phase A gate on a patched copy (893 passed, 1 skipped — Sonnet seat).

## Residual unknowns

- Resolved: the four D-822 specs need no pin (spec I2); `compute_spec_hash` is stored, never compared
  (`src/fabrik/state.py:217`).
- Resolved: `tests/test_spec_loader.py` and the other six `SpecValidator` test files pass with the merge patched in
  (round 1, Sonnet seat: 893 passed, 1 skipped over Phase A step 5's gate set).
- Resolved: a full template merge on apply is rejected (D-908) — it would write template `env:` keys into all 69
  deployed `.env` files.
- Resolved as guarded: a spec with a top-level `kind` that differs from its template's `shape.kind`, and no
  `shape.kind` of its own, takes the template's kind on apply — as `fabrik plan` already does — and may then fail
  `validate()` for a missing `domain` (positive control above). None of the 69 specs is in that shape (round 3,
  Opus seat: `kind.py` → `guarded-shape 0`); the parity file's kind-agreement assertion (Phase B step 1) fails the
  build the day one is, whether or not `validate()` then refuses it.
- Resolved (design-approval panel): the only other raw reader of spec files on the apply path,
  `_shared_db_siblings` (`infrastructure.py:600-609`), shape-merges each sibling too (Phase A row 5); the shape
  readers outside the registrar decision — `src/fabrik/orchestrator/verifier.py:85` and `:141`, `src/fabrik/orchestrator/__init__.py:296`, `src/fabrik/orchestrator/deployer_ssh.py:826`,
  `infrastructure.py:525`, and `_provision_authelia` (`infrastructure.py:726`, `:1395-1408`), which adds an Authelia
  `^/api/` bypass when merged `shape.has_bearer_api` is true — saas-skeleton's defaults set it true, which is that
  template's intent (no admin-dashboard spec today gains it: 3 admin specs, raw equals merged) — change no live
  service today, and the template allow-list grader stops a new template key reaching them unreviewed.
- Open, outside this plan: translator's `/health` and `/metrics` — resolution: the owner deletes the pins (spec
  § Open/blocking unknowns).
