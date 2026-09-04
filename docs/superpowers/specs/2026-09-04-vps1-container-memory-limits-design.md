# Bounding the unbounded containers on vps1 — and closing the entrance they came in through

**Status:** CONVERGED
**Date:** 2026-09-04
**Author:** fleet (hub session 1970a0ff)
**Stage:** 1-design · CONVERGED 2026-09-05 by `/fabrik-spec-review` (7 rounds, md5 `1a9b9cb5` stable) · **PART A EXECUTED 2026-09-05** on the operator's authorisation (D-122) — 0 of 32 unbounded, no recreates · next: Part B (compose persistence, per stack at its next deploy)

> **AMENDMENT 1 (2026-09-05, operator decision — D-121).** The operator removed the `ocoron-com`
> WordPress stack (*"remove ocoron containers. we dont have any site to deploy yet"* / *"also it wont
> be wordpress"*). Containers and the stack network are gone; **all four volumes and
> `/opt/ocoron-com/compose.yaml` are preserved**, so the removal is reversible with `up -d`. The
> denominator therefore moved **15 of 37 → 10 of 32**, five ceiling rows are struck, and the total
> falls from 4,288 MiB to **2,752 MiB**. Open unknown 4 is RESOLVED by that decision. Every other
> conclusion — the in-place mechanism, the redis-main COW ceiling, the reversibility correction, the
> Part C check — is unaffected, because none of them depended on which containers were on the list.


> **PART A EXECUTED — 2026-09-05 (D-122).** The operator authorised the write to live production. All ten
> ceilings are applied in place: **0 of 32 containers unbounded**, every kernel cgroup verified carrying its
> value, `oom_kill 0` on all ten, and a 32-row before/after snapshot of (name, container id, `StartedAt`,
> status) diffed IDENTICAL — the operator's binding constraint answered by execution, not argument. The
> mechanism was re-proven first on vps1's own Docker 29.0.2 (scratch container `5641c16f67d7`, same id and
> `StartedAt`, `memory.max=268435456`, `memory.swap.max=0`), closing the honest gap named in
> § Does this delete anything?
>
> **One conclusion of this spec was WRONG and is corrected by the execution.** The § fabrik-lib verdict table
> said the applier was *"BUILD (trivial) — no module wraps Docker container mutation"*. It already existed:
> `scripts/vps_apply_limits.sh`, naming all ten containers, unrun since 2026-05-30. The spec asked whether
> fabrik-lib had the capability and never asked whether the hub already did. Re-running it unmodified would
> have failed on `promtail` (128m target vs a 134.4 MiB working set), silently lowered `prometheus` from
> 1.5 GiB to 1g, and mutated the `coolify` network — renamed one day after that script was last touched.
> It was rewritten in place, not duplicated. **The generalisable lesson: a "BUILD" verdict owes a search of
> the hub's own corpus, not only of fabrik-lib** — the vendor→enhance→build question has three candidates,
> and the spec only looked at two.


> **PART B EXECUTED — 2026-09-05 (D-124).** The durable half is declared: `deploy.resources.limits.memory`
> now sits in all three stacks' compose files, hub-side (`infra/vps1/{traefik,redis,monitoring}/compose.yaml`)
> and on the VPS, backed up first. Verified with Docker's OWN parser rather than a YAML read —
> `docker compose config` on each stack resolves all ten to byte-identical values to what is live, so a
> recreate cannot move a ceiling. **No container was recreated:** `docker compose up -d --dry-run` confirms
> the next deploy of each stack WILL recreate all ten (the config hash changed by design), and that deploy
> is deliberately left to each stack's own schedule, exactly as § Lifecycle says. Pre-flight re-proven live
> first: `redis-main` is on the named volume `redis_redis-data`, traefik is entirely host-bind-backed, and
> nothing on the box auto-runs `compose up` (no cron entry, and `fabrik-autoheal` contains no `up -d`).
>
> The three sources now agree by TEST, not by care: `test_the_compose_files_declare_the_same_ceilings_the_applier_asserts`
> pins the compose declarations against the applier's table (which is itself pinned against this spec's
> ceiling table), so a redeploy that silently moved a ceiling would go red. Red on revert: 10 of 10.

---

## Intake Inventory

This run was invoked on a conversation that began with "check is anything wrong or broken regarding
wsl start scripts". Every item that surfaced is part of this run's denominator.

| I# | Item (operator's or the session's own words) | Disposition | Where |
|---|---|---|---|
| I1 | "all must be fixed who will fix" — the six boot findings | **IN** (partly elsewhere) | Four fixed at `62d0c0c4`; the engine cron handed to the operator; THIS spec covers the memory-limit finding |
| I2 | "i hope this will not delete our existing contaniers." | **IN** | § Does this delete anything? — answered with an executed proof |
| I3 | 15 of 37 containers on vps1 run with `HostConfig.Memory == 0` | **IN** | § Goal, § Chosen approach |
| I4 | `promtail` is on the unbounded list AND is six months end-of-life | **IN** (bounded now, replacement stays separate) | § Rejected alternatives R4 |
| I5 | The `STRATEGIC_BACKLOG.md` row "…run with NO memory limit on vps1" recorded "redis-main and traefik"; the real count is 15 | **IN** | § Lifecycle — the row is CORRECTED (done, this change), title-cited per § Documentation landing sites |
| I6 | 28 of 37 containers also have no CPU limit (`NanoCpus == 0`) — same rule, `core/30-ops.md:186` | **OUT-OF-SCOPE** | A CPU ceiling degrades; a memory ceiling prevents a box-wide kill. Destination: **written** — `STRATEGIC_BACKLOG.md` row "28 of 37 vps1 containers have NO CPU limit…" (2026-09-04), carrying the measured 28/37 |
| I7 | `trytond-worker` at 61.6% and `glitchtip-web` at 47.4% of their existing limits | **OUT-OF-SCOPE** | These are *bounded* — a different problem (a ceiling possibly too LOW, the opposite failure). Destination: **written** — the § Watch item of that same new backlog row |
| I8 | vps1 SSH is intermittent (2 failures then 3 clean connections, box healthy at load 1.00) | **OUT-OF-SCOPE** | Affects HOW this is applied (retries), not WHAT is designed. Destination: named in § Constraints as an application-time hazard; its own fix is a separate fleet item |

**Intake: 8 items — 5 IN, 3 OUT-OF-SCOPE (each with a named destination), 0 ASK.**

---

## Personas

Every duty this spec creates names the role that holds it.

**PRIMARY — the operator**, in their own words: *"i hope this will not delete our existing contaniers."*
That sentence is the design's binding constraint, not a footnote. The operator runs a single shared VPS
carrying live products; their scarce resource is attention, and their stated fear is that a hygiene fix
costs them a running system. **The primary persona's minimal loop:**

1. Read the proposed ceilings and the evidence each is derived from.
2. Give one authorisation to write to live production.
3. Watch the applier print a per-container before/after line.
4. Confirm `docker ps` still shows the same 37 containers with the same uptimes.

**Four steps. That count is the step budget for Part A** — a design that needs the operator to babysit
fifteen individual decisions has failed this persona, however correct its numbers are. **Part B is
deliberately NOT in this budget**: it lands per stack at each stack's own next deploy, carried by
whoever owns that stack, and folding it in here would hide a per-stack sequence inside a number that
looks like four.

**The fleet agent (me).** Holds: measuring the working sets, deriving the ceilings, running the applier,
and the post-application verification. Does NOT hold: the authorisation to write to prod.

**The `fabrik apply` deploy path** — an automated consumer. Already enforces the invariant via
`deployer_ssh._validate_compose()`. It holds nothing new; the whole point is that fifteen containers
never passed through it.

**The recurrence check** — a new automated consumer. Holds: enumerating every DEFINED container
(`docker ps -a`) and flagging `Memory == 0`. It reports; it never mutates. Its output lands where a
human or the daily pipeline already looks.

**The services themselves**, as subjects rather than actors — and they are not one class:

| Class | Members | What a ceiling means |
|---|---|---|
| Self-bounding cache | `redis-main` | Already caps itself at `maxmemory 256M` / `allkeys-lru`; a cgroup ceiling is a second net, never the primary |
| Stateless ingress | `traefik` | Must fail fast and restart clean; a ceiling is pure blast-radius containment |
| Page-cache heavy | `loki`, `promtail` | The cgroup charges file cache, so a ceiling sized on RSS alone will OOM on cache |
| Observability | `grafana`, `alertmanager`, `cadvisor`, the three exporters | Small, stable, and the *last* thing that should take the host down |

---

## Goal

Every container running on vps1 carries a memory ceiling, and a container that arrives without one is
detected rather than discovered during an outage.

## Why this exists

`deploy.resources.limits.memory` is already a Fabrik invariant. `core/30-ops.md:148`, verbatim:

> **`deploy.resources.limits.memory` is mandatory.** A Fabrik invariant enforced by
> `deployer_ssh._validate_compose()` — `fabrik apply` refuses any compose service without a memory
> limit (prevents OOM on the shared VPS). The compose must carry the declaration explicitly.

It is enforced at one entrance. **Ten of thirty-two containers came in through another** (fifteen of thirty-seven before Amendment 1) —
hand-composed infra and the `ocoron-com` stack — so the validator never saw them. Measured live
2026-09-04 (`docker inspect -f '{{.HostConfig.Memory}}'` == 0):

`traefik` · `redis-main` · `loki` · `grafana` · `alertmanager` · `promtail` · `cadvisor` ·
`node-exporter` · `redis-exporter` · `postgres-exporter`

(The five `ocoron-com-*` containers were also on this list until Amendment 1 removed the stack.)

**The concrete pain.** `traefik` is the fleet's ingress. Unbounded, a memory spike there is not a
traefik incident — it is a host-level OOM kill that the kernel resolves by shooting whichever process
it judges worst, taking an arbitrary subset of all 37 containers with it. The netdata guide states the
mechanism plainly: *"A container without a memory limit can consume all available RAM, force the kernel
to reclaim page cache, push the system into swap, and eventually trigger a host-level OOM kill that
takes down the Docker daemon or other critical processes."*

**The deeper failure is the class, not the fifteen.** An invariant enforced on one code path, with a
second path unguarded, is the same shape as the other finding from this same evening: the
ai-model-catalog engine was faithfully *called* at its delivery end and never *scheduled* at its
producing end, and the fleet-synced AI rule packs sat empty for 17 days while a healthy detector
alarmed into a dead channel. **A spec that sets fifteen numbers and stops has fixed the instance and
left the class.** That is why § The recurrence check is not optional garnish.

## Does this delete anything?

**No — and this is proven, not asserted.** Run locally on cgroup v2 / Docker 29.1.3 (vps1 runs 29.0.2):

```
start id : 02aab2333f58  limit=0          started=2026-09-04T20:47:29.320260178Z
after up : 02aab2333f58  limit=268435456  started=2026-09-04T20:47:29.320260178Z  running=true
cgroup   : 268435456        # /sys/fs/cgroup/memory.max, read from inside the container
```

Same container id, same `StartedAt`, `Running=true` throughout, and the kernel's own cgroup file
confirms the new ceiling. `docker update` mutates the live cgroup; it does not recreate, restart, or
remove anything.

⚠️ **The honest gap in this proof: it was run on Docker 29.1.3 locally, and vps1 runs 29.0.2.** The
versions are adjacent and both are cgroup v2, and `docker update --help` on vps1 was confirmed to carry
`-m, --memory` and `--memory-swap` — but a proof executed on one host is evidence about that host. It
was NOT re-run on vps1 at authoring time, deliberately: the operator had not yet authorised any write to
live production, and creating even a throwaway container is a write.

**RESOLVED 2026-09-05 — the probe was run, and it agreed.** On the operator's authorisation, the identical
before/after ran on a scratch `alpine:3.20 sleep` container on vps1's own Docker 29.0.2 *before* any live
container was touched:

```
start id : 5641c16f67d7  limit=0          started=2026-09-04T22:17:52.853349553Z
after up : 5641c16f67d7  limit=268435456  started=2026-09-04T22:17:52.853349553Z  running=true
cgroup   : 268435456        # /sys/fs/cgroup/memory.max, read from inside
swapmax  : 0                # --memory-swap == --memory, so no swap doubling
VERDICT  : SAME CONTAINER ID — no recreate
```

The scratch container was then removed. The version gap named above is closed by execution on the TARGET
host, not by analogy from the local one — and the same property was re-proven across the real run: a
32-row before/after snapshot of (name, container id, `StartedAt`, status) diffed IDENTICAL.

**And even if a container were recreated, no data would be lost**, because every data-bearing container
keeps its state outside itself (verified 2026-09-04):

| Container | State lives in |
|---|---|
| `ocoron-com-db-1` | volume `ocoron-com_db_data` → `/var/lib/mysql` |
| `ocoron-com-wordpress-1` | volume `ocoron-com_wp_html` → `/var/www/html` |
| `redis-main` | volume `redis_redis-data` → `/data` |
| `traefik` | host binds, including `acme.json` (the certificates) |

Named volumes and host binds both survive `docker rm`. **No step in this design deletes a volume**, and
none may be added: volumes are data, and "dangling" is not "disposable" (CLAUDE.md HARD STOP).

## Chosen approach — bound in place first, persist second, then close the entrance

Three parts, deliberately sequenced so the risk drops before the durability work starts.

### Part A — apply live, in place (no recreate)

`docker update --memory <N> --memory-swap <N>` per container. Properties, each grounded:

- **Live.** Proven above: same container, same process, new ceiling.
- **Reversible UPWARD, and only upward — measured, because the draft got this wrong.** Re-running with
  a different value works live in both directions (subject to the decrease rule below). But
  **`docker update --memory=0` does NOT remove a limit**: tested locally, it exits 0 — reporting
  success — while `HostConfig.Memory` and `/sys/fs/cgroup/memory.max` both stay at the old value.
  The draft claimed "`0` restores unbounded", which would have told the operator a ceiling was
  undoable by a command that silently does nothing. **Removing a ceiling entirely requires
  recreating the container** — the one action this design otherwise avoids. In practice this costs
  nothing, because the remedy for a ceiling that turns out too low is to RAISE it, which is live;
  but the operator must not be told a door exists that does not.
- **Safe to set high.** Netdata: *"This works live for increases; decreasing below current usage
  fails."* Every proposed ceiling is far above current usage, so no call can fail that way.
- **`--memory-swap` is set equal to `--memory` deliberately.** Netdata: *"If you only set `--memory`
  and leave `--memory-swap` unset, the default total memory-plus-swap allowed is twice the memory
  limit."* Leaving it unset would silently double every ceiling.

### Part B — persist in the compose files

**This part is mandatory, not optional polish**, because of one grounded fact: *"changes made with
`docker update` do not persist for containers managed by Docker Compose."* Part A survives until the
next `up -d` and no longer. Part B writes `deploy.resources.limits.memory` into each stack's compose so
the ceiling outlives a redeploy — and this is the only part that recreates containers, on the stack
owner's next deploy, with the volume evidence above as its pre-flight.

### Part C — the recurrence check

A check that enumerates every **DEFINED** container (`docker ps -a`, not `docker ps`) and flags
`Memory == 0`, rather than validating only what passes through `fabrik apply`. This is the part that
fixes the class.

**Why `-a` and not just running:** a stopped-but-defined container carries its `HostConfig.Memory`
across a restart, so a check reading only the running set would report green while an unbounded
container sat waiting to be started. Today the distinction is invisible — `docker ps -q` and
`docker ps -aq` both return 37, there are no stopped containers — which is exactly why it would have
been easy to encode the narrower query and never notice.

**Fire rate, measured before shipping** (FIX DIRECTIVE 5): **10 of 32 today, 0 of 32 after Part A** (15 of 37 before Amendment 1).
It fires only on a genuine regression — a new container arriving off the apply path. That is signal,
not wallpaper. Had it existed, it would have caught all fifteen the day each appeared.

### The ceilings

Derived from measured live usage plus class-appropriate margin. Sources agree on the method: size from
observed peak with 25–50% margin for stable services, and never from idle startup.

| Container | Measured | Proposed | Reasoning |
|---|---|---|---|
| `cadvisor` | 323.9 MiB | 512M | Largest of the fifteen; ~58% margin |
| `promtail` | 135.1 MiB | 256M | Page-cache heavy (tails logs) |
| `loki` | 131.0 MiB | 512M | Page-cache heavy; ingest bursts |
| `grafana` | 86.9 MiB | 256M | Dashboard rendering spikes |
| `traefik` | 52.7 MiB | 256M | Ingress — generous, because failing it fails everything |
| `alertmanager` | 33.5 MiB | 128M | Small, stable |
| `postgres-exporter` | 17.3 MiB | 64M | Scrape-only |
| `node-exporter` | 16.5 MiB | 64M | Scrape-only |
| `redis-exporter` | 12.4 MiB | 64M | Scrape-only |
| `redis-main` | 5.2 MiB | 640M | **See below** — it forks |

(The IDLE-derived caveat that stood here applied to `ocoron-com-backup-1`, struck by Amendment 1. No
remaining row is sized from a dormant measurement — every one of the ten is a continuously-running
service measured in steady state.)

Total ceilings: **2,752 MiB = 2.69 GiB, 23% of the 11.63 GiB host** (10 rows, re-derived after Amendment 1; it was 4,288 MiB over 15 rows). Existing limits already total ~19 GiB — limits are
ceilings, not reservations, so overcommit is normal and unchanged by this work.

**`redis-main` is the one that could have gone wrong, and the first draft of this spec got it wrong.**
It caps itself at `maxmemory 268435456` (256 MB) with `allkeys-lru`, currently holding 2.86 MB logical
/ 4.05 MB RSS. The grounded trap: the kernel enforces RSS while Redis tracks logical `used_memory`, and
*"When RSS hits the host or cgroup memory ceiling, the kernel terminates the process even though Redis
believes it is within limits."* A cgroup ceiling at or below `maxmemory` converts graceful LRU eviction
into a hard kill of the fleet's shared cache.

The draft proposed 384M — `maxmemory` plus 128 MB — and **that is too tight in the dangerous
direction.** Measured on the live instance: `appendonly yes` AND `save 3600 1 300 100 60 10000`, with
`aof_enabled:1`. **redis-main persists, so it FORKS** — both BGSAVE and AOF rewrite — and a fork over a
dataset near `maxmemory` can approach *twice* the dataset resident under worst-case copy-on-write,
because every page the parent writes during the save must be duplicated. 384M would have OOM-killed the
fleet's shared cache during a snapshot of a full 256 MB dataset — the precise failure this spec exists
to prevent, introduced by the spec itself.

**640M** = 256 (data) + 256 (worst-case COW) + 128 (fragmentation and allocator overhead). Still
trivial against an 11.63 GiB host. Today's 2.86 MB dataset is nowhere near this, so the ceiling is
insurance against a future full cache, not a present constraint. The backlog row named redis-main a top
risk; it is in fact the best-defended of the fifteen — and simultaneously the only one where a careless
ceiling could cause the outage.

## Rejected alternatives

- **R1 — Compose-only, skip Part A.** Correct in the end state, but leaves the acute exposure standing
  until each stack's next deploy, and forces a recreate as the *first* action rather than the last.
  Rejected: it inverts the risk order for no gain.
- **R2 — `docker update` only, skip Part B.** Cheapest and closes the risk today, but the grounded
  non-persistence fact makes it a ceiling that silently vanishes on the next `up -d`. That is worse
  than no fix, because the check in Part C would then read green while the durable state regressed.
- **R3 — Extend `_validate_compose()` to cover these stacks.** Attractive, and wrong: it validates
  *files handed to `fabrik apply`*. These containers never go through `fabrik apply`. Strengthening the
  guarded entrance does nothing about the unguarded one. Part C observes the *runtime* instead, which is
  the only place both entrances converge.
- **R4 — Replace `promtail` now rather than bound it.** It is six months EOL (2026-03-02) and on this
  list, so folding the replacement in is tempting. Rejected: a log-shipper swap is its own spec with its
  own failure modes, and bundling it would make this change un-revertable in one step. Bound it now at
  256M; the replacement keeps its own backlog row. Do not silently do both.
- **R5 — One uniform ceiling for all fifteen.** Simple and defensible-sounding. Rejected because the
  classes genuinely differ: 64M would kill loki, and 512M for `node-exporter` is a meaningless ceiling
  that would never bound anything.
- **R6 — `--memory-reservation` (soft limit) instead of `--memory`.** A soft limit is advisory and only
  activates under host contention; it cannot bound a runaway. Rejected as not solving the stated risk.

## Lifecycle

- **Adoption.** Part A is a single operator authorisation and one applier run; Part B lands per stack at
  each stack's own next deploy; Part C ships with Part A so the first green reading is evidence.
- **Growth.** The ceilings are derived from *today's* working set. Two named escalation triggers, not
  "we'll see": (1) any container sustaining **>80% of its ceiling** — the netdata warning threshold — is
  re-sized, not silently left to OOM; (2) any nonzero `memory.events`/`oom_kill` count in a bounded
  cgroup is an incident, because it means a ceiling here was wrong.
- **Degradation.** A container that hits its ceiling is OOM-killed and restarted by its restart policy —
  a bounded, single-service failure, which is exactly the outcome this design is buying in place of an
  unbounded host-level kill of an arbitrary subset.
- **Retirement.** The obvious retirement condition — "every container reaches vps1 through
  `fabrik apply`" — is one this design's own R3 says will probably never be met: the `ocoron-com` stack
  and the shared monitoring stack are hand-composed by intent, not by oversight. So the honest
  retirement condition is narrower: **Part A retires the moment Part B lands for a given stack** (the
  in-place ceiling is superseded by the declared one), while **Part C never retires** — it is the
  standing assertion that no fourth entrance opened. A check whose retirement condition is "when the
  problem cannot recur" outlives every design that assumes it can.
- **The backlog row is CORRECTED (done, this change)** — it recorded two containers where fifteen were
  measured, and a 7x-low count in a backlog is a number that gets quoted. It also asserted that setting
  a limit "restarts both containers… and traefik restarting drops every route briefly"; that assumption
  is disproved above and was corrected in the same edit, because it is the belief that made this work
  look like it needed an outage window.

## External dependencies

| Dependency | Grounded fact | Source · fetched |
|---|---|---|
| Docker `update` | Applies to a running container, live; increases work, decreasing below current usage fails; **does not persist for compose-managed containers** | netdata.cloud/guides/docker/docker-memory-limits/ · 2026-09-04 |
| `--memory-swap` | Unset ⇒ memory+swap = 2× the limit; equal to `--memory` ⇒ no swap | same · 2026-09-04 |
| cgroup v2 accounting | Charges page cache, tmpfs and slab, not only RSS — so an RSS-sized ceiling can OOM on cache | golinuxcloud.com/linux-container-memory-limits-cgroups/ · 2026-09-04 |
| Redis vs cgroup | Kernel enforces RSS, Redis tracks logical `used_memory`; a cgroup ceiling below the RSS the policy allows produces a kill instead of an eviction | oneuptime.com (redis maxmemory/eviction) + netdata.cloud/guides/redis/redis-out-of-memory-oom-killed/ · 2026-09-04 |
| Sizing method | Size from observed peak with 25–50% margin; never from idle startup; alert at sustained >80% | thehomeserverblog.com/container-memory-limit-calculator/ + netdata · 2026-09-04 |
| Live topology | 37 running (`docker ps -aq` also 37 — no stopped containers), 15 with `Memory == 0`, 28 with `NanoCpus == 0`, per-container `docker stats` usage, volume/bind backing for the four data-bearing containers | executed against vps1 · 2026-09-04 |
| `redis-main` persistence | `maxmemory 268435456` · `allkeys-lru` · **`appendonly yes`** · **`save 3600 1 300 100 60 10000`** · `aof_enabled:1` — it forks, which is what sets the 640M ceiling | executed against vps1 · 2026-09-04 |

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Reading container state over SSH | **VENDOR as-is** — the deploy path's existing SSH usage | `fabrik apply` already reaches vps1 this way; no new transport |
| Applying the ceilings | **BUILD (trivial)** — a short script driving `docker update` | No module wraps Docker container mutation, and none should: this is ~30 lines of a fixed command over a fixed table. Fails the new-module bar on (b) — no second project type would reuse a vps1-specific applier |
| The recurrence check | **BUILD** — `scripts/enforcement/`-shaped, consistent with the existing check corpus | Every peer check lives there; a new module would fragment the corpus. Fails the fabrik-lib bar on (a): it encodes a Fabrik invariant, which is project-specific by definition |
| Alerting on a finding | **VENDOR as-is** — `libs/alerting` | Proven working this session (`PASS: alert delivered`); no second path needed |

**No `🆕 fabrik-lib candidate`** — every piece is either existing infra or deliberately Fabrik-specific.

## Shape / infra implications

No scaffold type, no `shape:` flags, no new service, no ports, no DB, no new container. This changes the
*runtime configuration of existing containers* plus one check and one applier script in the hub. It is
the rare design with no `specs/services/` footprint at all.

## Documentation landing sites

| What | Where |
|---|---|
| The invariant's second enforcement point | `docs/workstation/` — extend the existing ops surface, not a new doc |
| The ceilings table + their derivation | This spec, referenced from the check's `AFTER-EDIT` header |
| The check itself | `INDEX.md` row + `CHANGELOG.md` |
| The corrected count | `docs/STRATEGIC_BACKLOG.md` — the row now titled "RESOLVED for memory (2026-09-05) — the unbounded containers on vps1; the redis-main EVICTION-POLICY half stays open" (edited in place; cited by TITLE, not line number, because inserting rows above it moves the line. ⚠️ The title CHANGED when Part A landed — a title anchor survives inserted rows but not a rename, which is the tradeoff this row now demonstrates) |
| The CPU gap (I6) + the two near-ceiling containers (I7) | A new `docs/STRATEGIC_BACKLOG.md` row |
| The decision itself | `docs/DECISIONS.md` — a row minted with `decisions.py --next-id` |

## Constraints

| # | Constraint | Source |
|---|---|---|
| C1 | `deploy.resources.limits.memory` is mandatory on every service | `core/30-ops.md:148` (quoted verbatim above) |
| C2 | `cpus` is mandated alongside it | `core/30-ops.md:186` — I6, declared out of scope with a destination |
| C3 | Never propose deleting a docker volume; "dangling" ≠ disposable | CLAUDE.md HARD STOP |
| C4 | Writing to live production infra needs the operator's explicit authorisation, separate from approving this spec | CLAUDE.md § Behavior |
| C5 | vps1 SSH is intermittent (measured: 2 failures then 3 successes, box healthy) — the applier must be idempotent and re-runnable, never assume one clean pass. **How:** the applier is a pure declaration of target ceilings, reading `HostConfig.Memory` per container and issuing `docker update` only where it differs; a container already at target is a no-op line. A dropped connection therefore costs a re-run, never a partial or doubled application, and the check in Part C is the independent verifier that the run landed | measured 2026-09-04 |
| C6 | Never `--oom-kill-disable` | netdata guide · 2026-09-04 |

## Open / blocking unknowns

1. **Peak vs steady-state.** Every measurement is a single `docker stats --no-stream` sample at one
   moment, not a p95 under load. The margins are chosen to absorb that, but the honest statement is that
   these are *steady-state-derived* ceilings. **Resolution:** Prometheus has been scraping these
   containers all along — pull `container_memory_working_set_bytes` history before Part B freezes the
   numbers into compose. Part A's ceilings are generous enough that this is not a blocker for it.
2. ~~**Which stack owns each compose file for Part B.**~~ **RESOLVED 2026-09-05 by tracing the compose
   labels** (`com.docker.compose.project` / `.working_dir`), not by guessing. The ten span exactly THREE
   stacks: `/opt/traefik` (traefik) · `/opt/redis` (redis-main) · `/opt/monitoring` (the other eight).
   Every one has a repo-of-record in the hub at `infra/vps1/<stack>/compose.yaml`, so Part B was a hub
   edit plus a push to the VPS, not an untracked change on the box. **One drift found in passing:** the
   VPS's `/opt/traefik/compose.yaml` is AHEAD of the hub copy by three lines (the Cloudflare DNS-01
   `cf.env` env_file and the `acme-cloudflare.json` bind, from the tenant-wildcard work). Part B did NOT
   reconcile it in either direction — the ceiling was inserted into each copy independently so the drift
   survives untouched — but a hub-driven redeploy of traefik today would DROP the Cloudflare resolver.
   That is its own item, filed to the backlog, not silently fixed here.
3. **`redis-main`'s eviction policy is `allkeys-lru`, which can evict keys that have no TTL.** The
   pre-existing backlog row for this surface warns that the watchdog's pause flags *"must outlive
   pressure"* and argues for a `volatile-*` policy, which evicts only keys carrying a TTL. This spec
   does NOT change the eviction policy and must not be read as blessing the current one. It matters
   here for one reason: a `volatile-*` policy lets untagged keys accumulate past `maxmemory`, which
   would make the 640M ceiling the binding constraint rather than a safety net — so the two decisions
   are coupled and the policy change must not land without re-deriving this ceiling. **Resolution:**
   the policy question stays on its own backlog row; whoever takes it re-reads this table first.
4. **~~Whether `ocoron-com-*` is in fleet scope at all.~~ RESOLVED 2026-09-05 (D-121):** the operator
   removed the stack rather than scoping it. The fifteen did become ten, exactly as this unknown
   predicted. Its volumes and compose file are preserved, so if a site ever returns there it re-enters
   through `fabrik apply` or is re-measured then.
