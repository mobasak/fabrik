# [Project Name] — Operations

<!--
  ONGOING-OPERATOR PLAYBOOK. Sits between DEPLOYMENT.md (first-time setup) and
  TROUBLESHOOTING.md (symptom-driven debug). This is where you document the
  recurring knowledge that decays fastest:

    1. Living data feeds — auto-refreshing reference data + how to fix it
    2. Vendor knowledge log — what you asked the vendor and what they said
    3. Recurring operator tasks — cadence-based playbooks (rotation, top-up, renewal)
    4. Manual recovery / bypass — what to do when automation fails or quota runs out

  RELATIONSHIP TO OTHER DOCS (keep these boundaries):
    - RESILIENCE.md  → dependency pause-state design (the machinery)
    - SERVICES.md    → vendor inventory + cost/quota/rate-limit snapshot
    - TROUBLESHOOTING.md → "service won't start / 503 / port conflict" debug
    - DEPLOYMENT.md  → fabrik apply / redeploy / destroy mechanics
    - THIS FILE      → "the alarm fired — what do I, the operator, do now?"

  HOW TO FILL: every section below is OPTIONAL. Delete sections your project
  doesn't need. A project with no living data feeds, no paid vendors, and no
  account-rotation needs may legitimately ship a one-paragraph OPERATIONS.md
  ("This project has no recurring operator tasks; alarms route to
  TROUBLESHOOTING.md"). Don't pad.
-->

## 1. Living Data Feeds

<!--
  For each auto-refreshing reference data source the project depends on:
  tariffs, exchange rates, vendor catalogs, geo databases, regulation files,
  upstream API schemas, model versions. Copy the per-feed block per source.
  Skip this section entirely if all your data comes from explicit API calls
  on the request path (no scheduled refresh).
-->

### Feed: `[feed_name]`

**Guarantee:** [What this feed promises — e.g. "never silently serves a stale rate" — and the preconditions for the guarantee. Standing conditions usually include: the refresher service is running, the health endpoint is registered in Gatus, someone watches the alarm, credentials are valid.]

**Refresh machinery:**
- **Runs:** [`scripts/x/refresh_loop.sh` daily / cron every Nh / on webhook from vendor]
- **Sources:** [list of source URLs or endpoints + env vars that point to them]
- **Change detection:** [content-hash / Last-Modified / ETag / vendor change-feed]
- **On change:** [re-parse → reload → effective-date]
- **On failure:** [keep last-good and record `error` / `monitored-stale` run — never silently drop]
- **State table:** `[table_name]` (`source`, `status`, `message`, `content_hash`, `fetched_at`)
- **Health gate:** `/health/[feed]` → 200 when all sources fresh; 503 when any stale/errored

**Is it alive? (one query)**
```sql
-- One-shot liveness query — paste into psql / Grafana
SELECT source,
       max(fetched_at) FILTER (WHERE status IN ('ok','unchanged')) AS last_ok,
       (array_agg(status ORDER BY fetched_at DESC))[1]            AS last_status,
       count(*)                                                    AS runs
FROM [tr_x_source_runs] GROUP BY source ORDER BY source;
```

Healthy = every source has `last_ok` within [N days] and `last_status` in (`ok`, `unchanged`). A **missing** source = never ran (activate it — see below). An **old** `last_ok` = the refresher stalled.

**Diagnosis — `/health/[feed]` is 503, now what?**

Read the failing source's latest `[tr_x_source_runs].message`, then:

| Source(s) | Message looks like | Likely cause | Fix |
|---|---|---|---|
| `any` | `fetch: HTTPError 404` / timeout | source URL moved | re-point the env var ([`X_URL`]), redeploy |
| `[source]` | `[parser error pattern]` | source replaced or format-drifted | inspect fetched bytes; update parser or URL; force a reload |
| `[source]` | `auth error` / `401` | API token expired | regenerate token (`[provider command]`), update `.env`, redeploy |
| `[source]` | `status = monitored-stale` | change-detect saw a delta the auto-applier couldn't safely absorb | follow the **manual override** path below |
<!-- Add one row per realistic failure mode. The point is to make 3am
     diagnosis a lookup, not a debugging session. -->

> **Force a reload after a parser change:** content-hash change-detect is blind to a transform change — a byte-identical source won't re-load. Re-run the source's refresh manually or bump the source so the hash differs.

**Manual override path** (when the automated apply refuses to absorb a change):

```sql
-- Example: rate transition. Close the open row, open the new one.
UPDATE [rate_table] SET effective_to = '[YYYY-MM-DD]'
 WHERE code = '[code]' AND effective_to IS NULL;
INSERT INTO [rate_table] (code, value, effective_from, effective_to, source_ref, note)
VALUES ('[code]', [value], '[YYYY-MM-DD]', NULL,
        '[official decree/citation]', 'transcribed from source — never inferred');
```

**What the automation CANNOT absorb alone** (needs engineering time, not a runbook entry):
- [A new category/levy type / schema change]
- [Annual nomenclature update — codes split/merge]
- [A new regime requiring parser + schema work]

In all of these the engine [over-collects / alarms / degrades safely] — **it never silently fails** — but a human writes the new logic.

---

## 2. Vendor Knowledge Log

<!--
  Persist what you asked each vendor and what they said. The cost of NOT having
  this: 6 months later someone re-asks "do they charge for failed retries?",
  the vendor takes 4 days to respond, in the meantime you guess wrong and ship
  a billing surprise. Three states: ✅ Resolved, ⚠️ Open, ✅ Confirmed-by-testing.
  Skip this section if all your vendors are public APIs with no support
  relationship (Cloudflare, Stripe, etc. where the docs are authoritative).

  BOUNDARY vs SERVICES.md: SERVICES is the *current snapshot* (rate limit,
  cost, failure signature, status). THIS section is the *temporal log* (what
  did we ask on what date and what was the answer). Don't restate snapshot
  data here — link to SERVICES instead.
-->

### Vendor: `[Vendor Name]` — last contact `[YYYY-MM-DD]`

**Account contact:** [name / email / Slack channel / support portal URL]

#### ✅ Resolved (Supplier Response — `[YYYY-MM-DD]`)

**Q: [The question we asked]**
A: [Their exact answer, quoted or paraphrased verbatim. Note any caveats or "depending on…" clauses they added.]
- **Impact on us:** [How this changed our integration]
- **Verified in code:** [`path/file.py:Lxx` — where we acted on this]

**Q: [Next question]**
A: [Answer]
- **Impact on us:** [...]

#### ⚠️ Still Open

**Q: [Question outstanding] — asked `[YYYY-MM-DD]`, owner `[name]`**
- **Why it matters:** [What's blocked or at risk until answered]
- **Workaround:** [What we're doing in the meantime, and its cost/risk]
- **Follow-up plan:** [When to chase / escalation path]

#### ✅ Confirmed via testing (`[YYYY-MM-DD]`)

When the vendor didn't answer, we determined this empirically:

- **Rate limits:** [Observed: X req/min before 429. Sustained over Y minutes. Test script: `tests/vendor/x.py`]
- **Credit consumption:** [Observed: 1 credit per call regardless of result size. Failed calls do/don't bill.]
- **Data freshness:** [Observed: data updated [interval] vs vendor claim of [interval]]

#### Key clarifications (cross-reference)

| Topic | What the docs say | What's actually true | Source |
|---|---|---|---|
| [field name] | [doc claim] | [empirical truth] | [test path / vendor email date] |
<!-- Add rows whenever the vendor's docs contradict observed behavior — these
     are the gotchas that bite new engineers. -->

---

## 3. Recurring Operator Tasks

<!--
  Cadence-based playbooks. One entry per task that recurs without an explicit
  trigger from the system. If the task is alarm-triggered, document it under
  §1 (data feed alarms) or §4 (manual recovery) instead.

  BOUNDARY vs RESILIENCE.md §7 ("Proactive Monitoring Schedule"): RESILIENCE
  §7 owns the *automated machinery* — Beat job names, intervals, TTLs, the
  detection logic that fires a pause. THIS section is the *manual fallback
  playbook* — what the operator does when a Beat job missed its window or
  the automation refuses to absorb an edge case. Don't restate intervals
  here; link to RESILIENCE §7 and focus on the manual steps + verification.

  Examples that belong here:
    - API key rotation (every 90 days)
    - Prepaid credit top-up (when balance < $X)
    - Vendor subscription renewal (annual)
    - Account rotation before quota exhaustion (weekly)
    - Backup verification (monthly restore drill)
    - Cost reconciliation (monthly close)
-->

### Task: [Task name]

- **Cadence:** [link to RESILIENCE §7 row OR "manual: weekly / monthly / when balance < $X"]
- **Owner:** [name / role / on-call rotation]
- **Trigger:** [calendar reminder / Beat task alert / vendor email / manual]
- **Pre-conditions:** [what must be true before running — e.g. "no active deploy"]
- **Steps:**
  1. [Numbered step — exact command or click path]
  2. [...]
  3. [Verification: what to check that proves the task succeeded]
- **Rollback:** [If something goes wrong mid-task, how to revert]
- **Last run:** [YYYY-MM-DD — outcome — operator]

<!-- Repeat per task. Strong tasks have copy-paste commands and a verification
     step. Weak tasks just say "rotate the key" — useless at 3am. -->

---

## 4. Manual Recovery / Bypass

<!--
  What to do when the automation can't help and you need to act manually. One
  entry per scenario: vendor outage, quota exhausted, account banned, key
  compromised, cron stalled, decree-update-too-novel-for-auto-apply. The point
  is to convert "panic + tribal knowledge" into "lookup + execute".
-->

### Scenario: [Vendor X is down / quota exhausted / account banned]

**Detection signal:** [What alarm or symptom told you this is happening]

**Immediate impact:** [What stops working — user-facing AND internal]

**Bypass:**
1. [First action — usually a circuit-breaker flip or fallback vendor switch]
2. [...]
3. [How to verify the bypass is working]

**Recovery:**
- **Short-term** (today): [...]
- **Medium-term** (this week): [...]
- **Permanent fix** (this sprint): [...]

**Cost of bypass:** [Money/data quality/users impacted while running degraded]

---

## 5. Account / Quota Rotation

<!--
  Only fill this if you scrape, hit rate limits, or run multi-account vendor
  pools. Otherwise delete the section. Document each account that participates
  in the rotation: primary, backups, archived (with the reason they were
  retired — usually "banned" or "quota tier downgraded").
-->

### Active accounts (rotation pool)

#### Account: `[handle]` (primary, created `[YYYY-MM-DD]`)
- **Vendor:** [name]
- **Credentials in:** `.env` as `[ENV_VAR]`
- **Quota tier:** [free / paid / enterprise — what's included]
- **Current usage:** [percentage of quota used this period]
- **Health signal:** [how to know it's not yet banned/throttled — e.g. "test call returns 200"]

#### Account: `[backup-handle]` (backup, created `[YYYY-MM-DD]`)
- [Same fields. Triggered when primary [hits N%] / returns [signature]]

### Archived (do not reuse)

- **`[old-handle]`** — banned `[YYYY-MM-DD]` for `[reason: automated detection / TOS violation / abuse complaint]`. Lessons: [what behavior triggered the ban, encoded in current safety rules below]

### Safety rules (enforced in `[script path]`)

These are the rules the active account stays within to avoid joining the archive:

1. [Concrete rule — e.g. "Max 3 pages per feed per run (`ED_MAX_PAGES=3`)"]
2. [Concrete rule — e.g. "Randomized delays 8–20s between requests (`ED_DELAY_MIN`/`ED_DELAY_MAX`)"]
3. [Concrete rule — e.g. "Persistent browser profile retains cookies/TLS session"]
4. [Concrete rule — e.g. "UA rotation from pool of 5 real Chrome UAs per session"]
5. [Concrete rule — e.g. "One scrape window per day — no retry loops"]
<!-- Each rule should map to a code reference; otherwise it's aspirational. -->

---

## 6. Bottom line

<!--
  One paragraph: under what conditions does this project "stay operational"?
  Name the standing requirements (running services, watched alarms, valid
  credentials, human-on-call when automation hits an edge case).
-->

"[Project] is operational" is true **only** while:
1. [Standing condition 1 — e.g. "the [refresher] sidecar is deployed and running"]
2. [Standing condition 2 — e.g. "the [/health/feed] Gatus alarm is registered and watched"]
3. [Standing condition 3 — e.g. "someone acts when a source drifts or an account is rotated"]

The machinery converts the dangerous failure mode (silent staleness, silent over-charge, silent ban) into a loud one. **The human closes the loop.**

---

**Related:**
[`docs/CONFIGURATION.md`](CONFIGURATION.md) (env vars + credential setup) ·
[`docs/SERVICES.md`](SERVICES.md) (vendor inventory + rate limits) ·
[`docs/RESILIENCE.md`](RESILIENCE.md) (pause-state machinery) ·
[`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md) (symptom-first debug) ·
[`docs/LESSONS_LEARNT.md`](LESSONS_LEARNT.md) (what we learned the hard way)
