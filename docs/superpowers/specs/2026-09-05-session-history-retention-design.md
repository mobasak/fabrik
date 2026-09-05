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

## Approaches

### A — Scheduled index + off-box index backup, then bounded raw retention (RECOMMENDED)

Order matters and is the point:

1. **Make indexing scheduled.** A cron running the incremental indexer (candidate: every 15 min)
   so index freshness never depends on someone searching. Non-destructive, and it is the
   prerequisite for everything else.
2. **Back up the index off-box.** `pg_dump` of `session_recall`, compressed, into the existing
   fabrik DR path or the VPS Backrest plan. The index is text-only and small relative to raw; this
   is the copy that already carries 2,938 otherwise-lost sessions. Non-destructive.
3. **Only then, bound raw retention.** MAIN 90 days (the operator's stated need), SUBAGENT 7 days
   (the operator: *"i dont need history of subagents"*). Deletion is the one irreversible step and
   it goes last, behind a proven-restorable backup.

Cost: one cron, one dump, ~1.2 GB compressed for the 90-day main window at the measured 4.45x.
Nothing is deleted on day one — every main transcript is already inside 90 days.

### B — Compress-in-place, delete nothing

zstd every transcript older than N days, leave it on disk. 8.21 GB → ~1.8 GB. Simple, fully
reversible, no policy argument. But it does not survive a dead SSD or another manual cleanup, and
the cleanup is the *measured* failure mode. Rejected as the whole answer; viable as a tier inside A.

### C — Mirror raw JSONL to the VPS fleet

Symmetric DR, matches the fleet rule. Rejected as the primary: the VPS is shared and
disk-constrained, September's rate could push ~90 GB at it, and the raw fidelity being preserved is
worth less than the index it would sit beside. Reconsider only if § Open unknown 1 resolves toward
raw-fidelity being a hard requirement.

## What a restore actually yields — stated because a backup nobody restored is a hope

- **Raw JSONL restored** → a session the CLI can resume, with tool calls, message ids and usage.
- **Index restored** → role/timestamp/extracted text, readable by a human or an agent, **not**
  resumable and **not** a real transcript. Writing index content back into `projects/` would be a
  reconstruction wearing the costume of a real session; this design forbids it.

The operator's stated need ("my chat windows history ... in session-recall") is satisfied by the
second. That is what makes A affordable: raw fidelity is the 90-day tier, text fidelity is forever.

## Open unknowns

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

Intake: 11 items — 10 IN, 1 OUT-OF-SCOPE, 0 ASK.

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
