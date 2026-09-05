# Session-history retention + durability — design

Status: DRAFT
Date: 2026-09-05
Owner: fleet (box-local infrastructure / DR)
Trigger: operator, this session — "now we must fix this properly", after 11 project dirs were
emptied on 2026-09-03 by a manual ~28 GB disk cleanup and the loss surfaced days later.

## The finding that reframes the problem

The operator's opening framing was "transcripts have no backup". Measured, it is worse and also
narrower than that:

**2,938 sessions from before 2026-08-01 exist ONLY inside session-recall's index. Their raw
JSONL is already gone.** The oldest surviving main transcript on disk is **2026-08-06** — thirty
days, not the 3.7 months the directory's May-dated files suggest (every May/June/July file left on
disk is a *subagent* transcript).

So this is not "add a backup before something bad happens". Something bad already happened, the
survivor is a local Postgres database with **zero backups**, and that database is one `DROP` or one
dead SSD from taking three months of history with it.

## Measured baseline (all re-derived this run; commands in § Evidence)

| Quantity | Value |
|---|---|
| `~/.claude/projects/` total | 266 dirs · 13,928 `*.jsonl` · 8.21 GB of JSONL (12 GB on disk incl. block overhead) |
| MAIN transcripts | 5,807 files · 5.49 GB · oldest **2026-08-06** |
| SUBAGENT transcripts | 8,125 files · 2.71 GB · oldest 2026-05-16 |
| MAIN older than 90 days | **0 files** — the whole main store is inside the window already |
| Size skew | 50% of all bytes live in the **top 14 files** (0.1%); largest single transcript **696.5 MB**; median 154.7 KB |
| Compression (measured, not assumed) | gzip -6 **2.26x**, zstd -12 **4.45x** on 25 mid-size transcripts |
| session-recall index | local PG `127.0.0.1:5432/session_recall` · 10,050 sessions · 2026-05-13 → today |
| Index rows with no JSONL left | **2,938 sessions** (pre-2026-08-01) |
| Backups of either store | **none** |
| Disk headroom | 529 GB free of 1007 GB (45% used) |

Growth is genuinely uncertain and the spec refuses to hide that: MAIN was **0.61 GB in August**
and **4.89 GB in the first five days of September**. That is an 8x/day jump driven by multi-agent
orchestration, and the 696 MB outlier sits inside it. A 90-day window therefore costs somewhere
between ~2 GB (August's rate) and ~90 GB (September's rate). The policy must be sized by a
measured cap, not by a projection — see § Open unknown 1.

## Two mechanisms that make naive fixes wrong

**1. The DR store cannot take this.** `scripts/dr_claude_backup.sh:24` excludes `projects/` as
"~9 GB of session state", and that exclusion is CORRECT: the script is an rsync into a **git**
mirror of `/opt/fabrik-dr-store` pushed daily. Appending gigabytes of append-only JSONL to a git
repo every day is unworkable (pack growth, churn, GitHub limits). Adding `projects/` to that script
is the obvious fix and it is rejected here explicitly so nobody re-proposes it.

**2. Indexing is on-demand, not scheduled — this is the load-bearing defect.**
`/opt/session-recall/server.py:7`: *"all three tools self-heal index freshness by spawning the
incremental indexer."* There is **no cron entry and no watcher** for it (the `rag_*_index.py` cron
lines belong to `/opt/youtube` and are unrelated). Indexing therefore happens only when an agent or
the operator happens to call `search_chats` / `recent_chats` / `get_chat`.

The consequence is the whole ordering constraint of this design: **any retention policy that
deletes JSONL is racing an indexer that may not have run.** A session created and deleted between
two tool calls is lost with no trace in either store. Today this is masked because agents query
session-recall often; a deletion cron would remove the masking.

## EXECUTED 2026-09-05 — the `.jsonl.bak-*` tier (operator-authorised)

Found during review of this DRAFT and resolved the same session. It is recorded here because the
route to it is the lesson, not the gigabytes.

**The first recommendation was WRONG.** The 15 `*.jsonl.bak-*` files (2.41 GB apparent) were
proposed for outright deletion as "provably lossless", on the strength of a SIZE comparison plus a
single spot-check. The operator asked "are you 100% sure", and the real check — `cmp` over the
bytes, then a set comparison of message `uuid`s — refuted it:

- **13 of 15 were not byte-prefixes** of their live counterpart. The files diverge mid-stream
  (one pair first differs at line 855 of 35,243), so the live transcripts had been REWRITTEN in
  place, not merely appended to.
- **293 messages existed only inside the `.bak` files** — 292 of them API-error records
  (`Connection closed mid-response`, `Rate limited`, `Stream idle timeout`) plus one system
  message. Something stripped error entries from the live transcripts on 21–23 July and left the
  pre-strip original beside them. **What performed that rewrite is still unidentified** — nothing
  in `scripts/`, `~/.claude/bin/` or the hooks matches, and no mechanism is asserted here in place
  of that gap. Two suffixes (`.bak-monitor`, `.bak-model`) are not timestamps at all.

**Disposition, executed:** the 293 unique records (376,706 bytes) were salvaged to
`~/.claude/error-salvage/2026-09-05-bak-unique-records.jsonl` with a manifest, verified in BOTH
directions on disk (re-read yields 293 parseable records; every `.bak`'s unique set recomputed
fresh is a subset of the salvage), and only then were all 15 files deleted behind a final
in-invocation guard that re-counted the salvage. `~/.claude/projects` went **12 GB → 8.7 GB**;
all 14,041 live `*.jsonl` remain untouched.

⚠️ **The salvage inherits the very gap this spec exists to close** — `~/.claude/error-salvage/` is
not in any backup path. It is the only copy of those 293 records and belongs in the Tier-4 backup
set below.

**The generalised lesson, which now governs the remaining tiers:** file size is a PROXY; a superset
claim requires comparing content. No transcript in the subagent or main tier is deleted until the
same byte-level and message-set verification has been run over it.

## ⚠️ THE CORRECTION THAT CHANGES THE ARCHITECTURE — session-recall is a MIRROR, not an archive

The first draft of this spec proposed "raw 90 days, text forever in session-recall". **That is
impossible as written**, and the reason is in session-recall's own code.

`ingest/reindex.py:296` — `_reclaim_orphans()`, *"Delete index_state + sessions for files no longer
on disk (finding #19)"* — deletes a session's indexed turns when its JSONL disappears. Deliberate:
the index is defined as a mirror of what is on disk, not a store of record. So a retention policy
that prunes a transcript would have the next index run delete its text behind it.

**A LIVE HAZARD, independent of this spec.** The reclaim runs only under `--full`
(`reindex.py:480`, *"Only on --full (a bounded, deliberate sweep)"*), which is why the 2,938
pre-August sessions still exist: nobody has run it since their files vanished. Measured — **all
2,938 still carry an `index_state` row, so every one is reclaim-eligible.** One
`python -m ingest.reindex --full`, a documented maintenance command, silently finishes what the
2026-09-03 disk cleanup started. That is today's risk, not a future one, and it wants a mail to
`/opt/session-recall` regardless of whether this spec is ever built (cross-repo: not ours to patch).

**Consequence:** the durable tier must be the TRANSCRIPTS, compressed and off-box. The index is a
convenience layer that follows whatever is on disk.

## Approaches

### A — Cold archive as the store of record, index as a mirror (RECOMMENDED)

Four tiers, and the order is a safety property, not a preference:

| Tier | What | Retention | Cleared by |
|---|---|---|---|
| Cold archive | zstd'd MAIN transcripts, off-box | **forever** | never |
| Hot | `~/.claude/projects/*.jsonl` MAIN | 90 days | prune, archive-gated |
| Hot | session-recall PG (mirrors hot) | follows hot | itself |
| Disposable | subagent transcripts (2.71 GB) | 7 days | prune, **no archive** |
| Disposable | pool receipts `/opt/*/.tmp/subagents/` (648 MB) | 14 days + rotate `ledger.jsonl` | prune, no archive |
| Disposable | `tool-results/` (0.33 GB) | with parent session | prune |
| Keep | `fabrik_analytics` (12 MB, 15,435 rows) | forever | `pg_dump` to the archive |

**THE INVARIANT THAT MAKES REPEAT IMPOSSIBLE: the pruner refuses to delete any transcript whose
sha256 is not already in the archive manifest.** Not "archive first, then prune" as a sequence —
the delete is *conditional on* the cold copy existing. If archiving fails, nothing is deleted and
the store simply grows with a warning. Loss stops being policy-dependent and becomes structurally
impossible.

Supporting guards: a `--full` wrapper that refuses unless the archive covers every orphan it would
reclaim; a `README` marker in `~/.claude/projects/` stating the path is data, not cache (aimed at
the failure that actually happened — a human freeing disk space); and a sample restore verified per
run, because an archive nobody has restored is a hope.

**Subagents are a hard cliff and that is accepted.** They are NOT indexed — measured: 10,075
sessions in the index, **0** with an `agent-` id, and `reindex.py:479` globs `*/*.jsonl`, which
never descends into `<session>/subagents/`. So unlike main transcripts, deleting one is absolute:
no text fallback, no `search_chats` hit. The operator accepted this explicitly (*"i dont need
history of subagents"*); it is recorded here so the cost is chosen rather than discovered.

**Pool receipts get 14 days, not 7, because they are READ.** `ledger.py:372` reads receipts back and
`pg_ledger.py:654` uses them to reconcile without touching the INSERT-only `subagent_runs` table;
`scripts/kilo-benchmarks/flush_subagent_outboxes.py` consumes them too. That is a real function, but
it concerns recent unflushed runs, not months. The 124 MB `fabrik/.tmp/subagents/ledger.jsonl` is
pure accumulation and should rotate.

### B — Compress in place, delete nothing

zstd everything older than N days, leave it on disk: 8.21 GB → ~1.8 GB. Fully reversible, no policy
argument, no destination decision. **Rejected as the whole answer**: it survives neither a dead SSD
nor another manual cleanup, and the cleanup is the *measured* failure mode. Retained as a tier
inside A (the archive is compressed by definition).

### C — Mirror raw, uncompressed JSONL to the fleet

Rejected: at September's rate this pushes ~90 GB at a shared, disk-constrained host to preserve
fidelity that 4.45–6.08x compression preserves for a fifth of the space.

## Where the cold archive lives — the three destinations, costed

| Destination | Capacity / cost, measured | Verdict |
|---|---|---|
| **The existing DR store** (`/opt/fabrik-dr-store`, GitHub) | **20 MB today** (12 MB of it `.git`). Adding ~1.2 GB per 90 days is a **60x** step change into a git repo rsync'd and pushed daily | **REJECTED** — and not on cost. `dr_claude_backup.sh:24` excludes `projects/` for exactly this reason; the mechanism is wrong (pack growth, daily churn), not the price |
| **vps1 + Backrest** | `df`: 108 GB total, 49 GB used, **59 GB free**. `backrest` container **Up 5 days**; its own data is 13 MB. Marginal cost **$0** | **RECOMMENDED** — off-box, existing machinery, no new dependency or credential, and years of headroom at ~1.2 GB/90d |
| **Cloudflare R2** | **$0.015/GB-month standard, 10 GB-month free tier, zero egress** (developers.cloudflare.com/r2/pricing, fetched 2026-09-06; page updated 2026-05-28). Our ~1.2 GB archive sits **inside the free tier**; even 50 GB is $0.75/mo | **ESCALATION, not primary** — genuinely off-fleet, so it survives losing vps1 too. Costs a new credential and a new dependency for a failure mode the operator has not named |

**Recommendation: vps1 + Backrest, with R2 named as the one-step escalation** if off-fleet
redundancy is later wanted. R2's zero-egress matters for a restore tier — pulling the archive back
costs nothing — so it is the right *second* copy, not the right first one.

## What a restore actually yields — stated because a backup nobody restored is a hope

- **Raw JSONL restored** → a session the CLI can resume, with tool calls, message ids and usage.
- **Index restored** → role/timestamp/extracted text, readable by a human or an agent, **not**
  resumable and **not** a real transcript. Writing index content back into `projects/` would be a
  reconstruction wearing the costume of a real session; this design forbids it.

⚠️ **Corrected:** an earlier draft said "raw fidelity is the 90-day tier, text fidelity is forever".
The second half is false — the index reclaims orphans, so its text is only as durable as the file
it mirrors. Forever belongs to the COLD ARCHIVE, and a restore from it yields the first row, not the
second: a real transcript, resumable, not a reconstruction.

**Measured, not asserted** (2026-09-06, on a 70.7 MB main transcript): zstd -12 → 11.6 MB
(**6.08x**), 1.5 s to compress, **0.08 s to restore**, and the restored file is **byte-identical**
with a matching sha256. That round trip is what the word "lossless" is doing in this document.

## Open unknowns

0. **RESOLVED this run — where the archive lives:** vps1 + Backrest (59 GB free, container up,
   $0), with Cloudflare R2 ($0 at our size, zero egress) as the named escalation. See the costing
   table above.

1. **Is September's rate the new normal?** 0.61 GB/mo → 4.89 GB/5d is the difference between a
   2 GB and a 90 GB window. Resolution: re-measure MAIN bytes/day over the next 14 days before
   fixing the retention number in code; ship the policy with a **measured size cap** as well as a
   day count, so one 696 MB runaway cannot define the tier.
2. **Does the 90-day count run on mtime or session start?** A resumed old session updates mtime and
   would survive a window it should have left. Resolution: decide against the indexer's
   `started_at`, which is what a human means by "how far back".
3. **What guards the next manual cleanup?** FIX DIRECTIVE 5 applies — measure before shipping a
   detector. Cheapest candidate is a `README` marker in the tree stating the path is data, not
   cache; a refusing cleanup script is the heavier option and needs a fire-rate argument.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "now we must fix this properly" | IN | Approach A, whole document |
| I2 | "i dont need history of subagents" | IN | A step 3 — SUBAGENT 7-day tier; 8,125 files / 2.71 GB |
| I3 | "i need my chat windows history only for sometime such as 90 days" | IN | A step 3 — MAIN 90-day tier |
| I4 | "in session-recall ?" | IN | § Restore — text fidelity forever is the durable layer |
| I5 | "claude code own history how long back should we retain it" | IN | A step 3 + Open unknown 1 (the number is measured, not guessed) |
| I6 | Prior claim: "dr_claude_backup.sh deliberately excludes projects/" | IN | § Two mechanisms (1) — re-verified at `dr_claude_backup.sh:24`, and the naive fix REFUTED |
| I7 | Prior claim: session-recall "stores role, ts, content — not tool calls/ids/usage" | IN | § Restore — re-confirmed, and it is why raw and text are separate tiers |
| I8 | Prior claim: transcripts have "no retention policy" and a cleanup swept them | IN | Re-verified: no automated job deletes main-profile transcripts (`cache-prune.sh` does not touch the path; `claude-reboot-sweep.sh:259` only reads) |
| I9 | The 696 MB single transcript / size skew | IN | Open unknown 1 — the size cap exists because of it |
| I10 | Where to store off-box: VPS/Backrest vs object storage vs DR repo | IN | Approaches A/B/C; C rejected with reasons |
| I11 | SubagentStop completion sound (earlier this session) | OUT-OF-SCOPE | Unrelated surface; awaiting operator go, tracked in that thread |
| I12 | "we should only keep what we need, we cant allow our wsl to be filled like this" | IN | Approach A's tier table — 12 GB → ~5 GB and capped |
| I13 | "we also call pool agents, where is their history? how much disk space" | IN | Approach A — 648 MB in `/opt/*/.tmp/subagents/` + a 12 MB local `fabrik_analytics`; both were absent from the first draft |
| I14 | "how will we reach subagents history? inside claude folder?" | IN | § Approach A — `~/.claude/projects/<slug>/<session-id>/subagents/agent-<id>.jsonl`, and NOT indexed (0 of 10,075) |
| I15 | "what is cold archive zstd'd?" | IN | § What a restore actually yields — measured 6.08x round trip, byte-identical |
| I16 | "we have lost all our chat history for some repos, it must not repeat. be sure." | IN | The archive-gated prune invariant + the `--full` hazard, both in Approach A |
| I17 | The `--full` orphan-reclaim trap (found this run) | IN | § THE CORRECTION — a live hazard today; owed a mail to /opt/session-recall (cross-repo, not ours to patch) |

Intake: 17 items — 16 IN, 1 OUT-OF-SCOPE, 0 ASK.

## Evidence

```
find ~/.claude/projects -name '*.jsonl' ! -path '*/subagents/*' -printf '%TY-%Tm %s\n' | awk ...
  2026-08    0.61 GB   3977 files
  2026-09    4.89 GB   1830 files
oldest MAIN transcript: 2026-08-06

find ~/.claude/projects -name '*.jsonl' -path '*/subagents/*' ...
  subagents:   8125 files     2.71 GB
  MAIN     :   5807 files     5.49 GB
  MAIN older than 90 days:  0 files  0.00 GB

zstd -12 vs gzip -6 on 25 mid-size transcripts (raw 255.6 MB):
  gzip   ratio 2.26x
  zstd   ratio 4.45x

50% of bytes live in the top 14 files (0.1%); largest 696.5 MB; median 154.7 KB

session_recall PG:  10,050 sessions, 2026-05-13 → 2026-09-05
  sessions indexed from BEFORE 2026-08-01 (no JSONL left on disk): 2938

crontab | grep -iE "recall|index"  -> only /opt/youtube rag_* jobs; NO indexer cron
/opt/session-recall/server.py:7    -> "all three tools self-heal index freshness by
                                      spawning the incremental indexer"
grep -rn session_recall scripts/dr_*.sh -> no match; no pg_dump in crontab
```

## Next

`/fabrik-spec-review` to converge this DRAFT before anything is built. Steps 1 and 2 of Approach A
are non-destructive and may be implemented ahead of the review at the operator's word; **step 3
(deletion) must not ship before a restore has been proven from the backup.**
