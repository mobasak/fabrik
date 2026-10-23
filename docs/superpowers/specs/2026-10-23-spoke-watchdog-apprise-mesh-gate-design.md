# Spoke watchdogs alert through a mesh-only Apprise gate — design

Status: DRAFT
Owner: fleet · Work item: W-5dcafaef · supersedes the spoke branch of D-1153 and lifts D-1156 on acceptance

Profile verdict: full section set. `Profile: delta` does not apply, because the gate service is a new component.
Size verdict: not small. The estimate is about 90 code lines, but it spans 7 code and config files (two Python
modules, a compose, an nginx conf, a bootstrap script, a spec and a Gatus file), which is over D-169's 5-file
bound. So the full `/fabrik-spec-review` chain applies.

## Personas

- **PRIMARY — the operator.** The work item, filed in their name, states the need:
  *"Mesh-publish apprise for spoke watchdogs, then lift W-37dda1e1's spoke refusal"*. The intent behind it is
  D-052 and D-108 (no spoke runs without a watchdog that can reach them). Their loop, counted (step budget **3**):
  (1) answer ONE deploy gate the coordinator boards (bring up the gate container on vps1 and refresh the spokes'
  firewall rule); (2) a spoke app with a watchdog is applied (spoke-canary is the proof); (3) a spoke incident
  reaches their Telegram exactly as a vps1 incident does. Today step 3 is impossible.
- **A spoke watchdog sidecar** (automated, `fabrik-lib` `watchdog_sidecar`) — the SENDER. It POSTs
  `{title, body}` to `WATCHDOG_APPRISE_URL` and counts only a 2xx as delivered
  (`/opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:561-576`). It holds no credentials and must hold none.
- **Apprise on vps1** (automated) — the RECEIVER. It holds the notification URLs, which carry the Telegram bot
  token. Duty: send. It must never expose its configuration to a mesh peer.
- **The mesh gate** (`apprise-mesh-gate`, new, automated) — duty: admit exactly `POST /notify/alerts` from the mesh
  and refuse everything else. It holds no secret.
- **Every other mesh peer** (spoke hosts, their containers, a compromised spoke container) — the adversary
  this gate is shaped against: may send an alert, may not read, change or redirect anything.
- **The registrar** (`fabrik apply`, `src/fabrik/orchestrator/infrastructure.py`, fleet's code) — duty: render the
  spoke URL, run the login preflight, and refuse a watchdog only for a cause it can name.
- **The coordinator** — duty: boards the deploy gate (the live vps1 compose and the spoke firewall refresh) and the
  production-data probe for named unknown U1; relays the operator's answers.
- **fleet** (builder) — duty: builds and tests the code, writes the gate's mirror and runbook lines, and runs the
  rollout only after the operator's go.
- **n8n, Backrest, Gatus and every vps1 watchdog** (existing automated Apprise callers on vps1) — must be
  untouched: they keep `http://apprise:8000/...` over the local bridge.

Every feature below traces to the operator (alerts from spokes) or to the adversary row (the allow-list); nothing
is scaffold gravity.

## Why this exists

D-1153 (2026-10-23) refuses every spoke-targeted watchdog because its sidecar could not alert. vps1's Apprise has
no mesh port; its only route is `notify.vps1.ocoron.com` behind `authelia-forward` (2FA,
`infra/vps1/apprise/compose.yaml:23`); and WireGuard carries no DNS, so `apprise` does not resolve on a spoke. A
spoke app therefore runs with no watchdog, the gap D-052 and D-108 forbid. spoke-canary opts out by hand (D-1156)
to keep its apply green. The pain is a fleet whose spokes cannot page the operator. The fix gives spoke sidecars
one narrow, deny-by-default path to Apprise over the mesh.

## Goal

A spoke watchdog sidecar's alert reaches Apprise over the WireGuard mesh, through a gate that admits only
`POST /notify/alerts`. The registrar renders that URL for spoke targets, checks the Claude login files the sidecar
mounts, and stops refusing spoke watchdogs. spoke-canary drops its opt-out and is applied as the proof.

## What exists today (executed 2026-10-23)

- The sidecar URL default is `http://apprise:8000/notify/alerts` (`src/fabrik/drivers/watchdog.py:546`). Only the
  postgres and redis URLs are rewritten for a spoke (`src/fabrik/drivers/watchdog.py:569-571`), through
  `_rewrite_shared_infra_host`, which swaps the HOST and keeps the port
  (`src/fabrik/orchestrator/infrastructure.py:137-157`, hosts at `:127`, mesh IP at `:121`).
- D-1153 refusal: `_provision_watchdog` records a non-fatal failure for any non-vps1 target and never calls the
  driver (`src/fabrik/orchestrator/infrastructure.py:1607-1619`). `provision()` withholds the watchdog roles and
  analytics for it (`:764-766`). `fabrik plan` names the refusal (`:455-462`).
- The sidecar bind-mounts `VPS_CLAUDE_HOME` and `VPS_CLAUDE_HOME.json` read-only
  (`src/fabrik/drivers/watchdog.py:143`, `:955-965`), and the driver does not create them.
- Apprise publishes no host port; mirror == live compose (both read 2026-10-23, live via `ssh -o ProxyJump=vps2 vps
  'sudo cat /opt/apprise/compose.yaml'` with secret lines filtered; env names only: `APPRISE_STATELESS_URLS`,
  `APPRISE_WORKER_COUNT`; `PortBindings {}`).
- vps1 listening sockets (live `ss -Hltn`, 2026-10-23): `10.99.0.1:3100 :5432 :6379 :8000 :9091`, `0.0.0.0:8201`; 8202
  is free, and `PORTS.md` shows only 8201 used in 8200-8299.
- vps1's `DOCKER-USER` (live `iptables -S DOCKER-USER`, 2026-10-23): RETURN for 10/8, 172.16/12, 192.168/16 and
  ports 80/443/6001/6002, then `-j DROP`. So a new published port is reachable from the mesh only. The spokes use the
  `FABRIK_MESH_ONLY_PORTS` drop list (`scripts/bootstrap/bootstrap-config.sh:39-49`, which has no 8202).
- Both spokes hold the login files (live `sudo test -f`, 2026-10-23): `/home/ozgur/.claude.json` and
  `/home/ozgur/.claude/.credentials.json` are present on vps2 and vps3. vps2 reaches `10.99.0.1:8000` over the mesh.
- vps1 runs Docker 29.0.2, and `docker.service` has no `After=wg-quick@wg0` (live `systemctl cat docker`,
  2026-10-23). That is a pre-existing gap for every mesh-bound service, filed as W-cb08c877.
- Gatus probes Apprise by service name (`configs/gatus/apps/apprise.yaml`).

## External facts (grounded live, 2026-10-23)

| Fact | Source |
|---|---|
| apprise-api serves every route on one port: `/add`, `/del`, `/move` change config; `/get`, `/json/urls` reveal URLs; `/cfg`, `/details`, `/metrics`, `/status`, `/qr`, `/auth`, UI | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/api/urls.py (WebFetch) |
| `APPRISE_CONFIG_LOCK` 403s `/get`, `/json/urls`, `/add`, `/del`, `/move`, but not `/notify/`, `/details` or `/metrics`; no IP allow-list setting exists | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/core/settings/__init__.py , https://raw.githubusercontent.com/caronc/apprise-api/master/README.md |
| Stateless `POST /notify/` accepts arbitrary `urls` in the payload | README above |
| `POST /notify/<key>` with nothing stored answers 404 "There was no configuration found", with no fallback to `APPRISE_STATELESS_URLS` | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/api/views.py (WebFetch summary, one tool — see U1) |
| Hash-mode store path is `sha224(salt+key)[0:2]` under the config dir | `gh api repos/caronc/apprise-api/contents/apprise_api/api/utils.py` lines 1127-1135 |
| A port published to a host address "can be accessed via other host interfaces using direct routing to the host address" when IP forwarding is on | https://docs.docker.com/engine/network/port-publishing/ (exa) |
| In `DOCKER-USER` "the iptables flags you use can only match internal IP addresses and ports of containers", so a drop list keyed on host ports needs host port == container port | https://docs.docker.com/engine/network/firewall-iptables/ (exa) |
| A host-IP bind that fails at container start is not retried by the restart policy; on Docker 29 the container can come back with only `lo` | https://github.com/moby/moby/issues/39559 , https://github.com/moby/moby/issues/53928 (exa) |
| nginx `limit_except` "Limits allowed HTTP methods inside a location" | https://nginx.org/en/docs/http/ngx_http_core_module.html#limit_except (raw curl) |
| `proxy_pass` with a variable resolves the name "using a resolver" per request, not once at start | https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass (raw curl) |
| Traefik v2.11 entrypoints are static configuration; routers match `Method`, `Path`, `ClientIP` | https://raw.githubusercontent.com/traefik/traefik/v2.11/docs/content/routing/routers/index.md lines 243-247 (raw curl) |
| `nginx:1.30-trixie` exists (amd64), updated 2026-10-21 | https://hub.docker.com/v2/repositories/library/nginx/tags/1.30-trixie (raw curl) |
| "an application should be configured to deny access by default"; "explicit configuration should be preferred over relying on framework or library defaults" | https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html (WebSearch → exa) |
| Centralise secrets rather than copying them across services | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html (WebSearch → exa) |

## Chosen approach — B: an nginx allow-list gate beside Apprise

The three-seat judge panel was given five approaches in alphabetical order, with no recommendation. All three
seats ranked B first, on three different angles (security, TCO, rollout blast radius):
`B,C,E,A,D` · `B,A,E,D,C` · `B,E,A,D,C`.

**Architecture.**

- **The gate.** A second service, `apprise-mesh-gate`, joins the live `/opt/apprise/compose.yaml` and its mirror
  `infra/vps1/apprise/compose.yaml`. It runs `nginx:1.30-trixie` on the `fabrik` network with
  `ports: - "10.99.0.1:8202:8202"`. Host port and container port are equal, so a spoke `DOCKER-USER` drop keyed on
  8202 matches. Other settings: `restart: unless-stopped`, memory limit 32M, a healthcheck on `/healthz`, and no
  Traefik labels. It mounts a read-only `nginx.conf` (mirror path `infra/vps1/apprise/mesh-gate.conf`).
- **Its whole policy:**
  - `listen 8202;`
  - `resolver 127.0.0.11 valid=10s;` plus `set $apprise http://apprise:8000;`, so Docker DNS re-resolves Apprise
    after any recreate.
  - `location = /notify/alerts { limit_except POST { deny all; } proxy_pass $apprise; }` — an exact match, so
    `/notify/`, `/notify/alerts/` and every other key fall through.
  - `location = /healthz { return 200; }`
  - `location / { return 403; }`
  - `client_max_body_size 64k`.

  The sidecar's body is a title and a short text. Nothing reveals or changes config, and Apprise's upgrades cannot
  widen the surface.
- **Apprise itself is unchanged.** It keeps no host port, its Traefik route and its 2FA, so n8n, Backrest, Gatus and
  every vps1 watchdog are untouched.
- **The spoke URL.** `WatchdogDriver` renders `http://10.99.0.1:8202/notify/alerts` for a non-vps1 target. A new
  mapping in `src/fabrik/orchestrator/infrastructure.py`, `_MESH_GATED_HOSTS = {"apprise:8000": "10.99.0.1:8202"}`,
  is applied by a sibling of `_rewrite_shared_infra_host`. A sibling is needed because the shared function keeps the
  port, and this one cannot. It is anchored on `//apprise:8000/` exactly as the shared rewrite is anchored, and
  `src/fabrik/drivers/watchdog.py:546` calls it beside `:569-571`. vps1 keeps `http://apprise:8000/notify/alerts`.
- **The spoke refusal is lifted.** `_provision_watchdog` no longer refuses on target alone
  (`src/fabrik/orchestrator/infrastructure.py:1607-1619`). `provision()` provisions the watchdog roles and analytics
  for every target again (`:764-766`). The `fabrik plan` clause at `:455-462` is removed.
- **The login preflight, on every target.** It replaces the refusal. It runs whenever `llm_provider_primary` or
  `llm_provider_fallback` is `claude-code` (the defaults are `claude-code`/`openrouter`,
  `src/fabrik/drivers/watchdog.py:596-597`):
  - It runs one ssh inside `_target_vps_env(ctx)`: `sudo test -f <home>.json && sudo test -f
    <home>/.credentials.json`, where `<home>` is `VPS_CLAUDE_HOME`.
  - If a file is missing, it records a non-fatal failure that names the file and the ssh host actually used, and
    skips the sidecar.
  - If the ssh call itself fails (non-zero from the transport, or a timeout), it records a separate failure whose
    text says the host could not be checked. "Missing" is never claimed in that case.
  - Both cases leave the app deployed and the apply red, as D-1153's refusal did.

  Why every target and not only spokes: the mount requirement is identical on vps1, so one rule with no branch
  closes the class. The cost is one ssh call per watchdog apply.
- **Firewall.** 8202 joins `FABRIK_MESH_ONLY_PORTS` (`scripts/bootstrap/bootstrap-config.sh:39-49`). A live spoke
  picks it up through `scripts/sysadmin/install-docker-user-rules.sh <host>` (deploy step). vps1's default-deny
  `DOCKER-USER` already covers it.
- **The acceptance.** Remove `watchdog: {enabled: false}` and its D-1156 comment from
  `specs/services/spoke-canary.yaml`, then `fabrik apply` it on vps2.

**fabrik-lib / vendor ladder.** Every capability was checked against `/opt/fabrik-lib/README.md`:

| Capability | Verdict | Why |
|---|---|---|
| Notification send | consume (vps1 Apprise) | already deployed; no new gateway |
| Path/method allow-list | consume (official `nginx` image) | no fabrik-lib module is a reverse proxy; the official image needs only a conf |
| URL rewrite, login preflight | build (registrar glue, ~40 lines) | registrar logic, not a reusable module; no 🆕 fabrik-lib candidate |
| Sidecar | unchanged (vendored `watchdog_sidecar`) | the URL is env; no upstream change |

**Data flow (invariants).** A spoke sidecar resolves nothing by name. Its only Apprise touchpoint is
`10.99.0.1:8202`, and the gate's only upstream is `apprise:8000` over the vps1 `fabrik` bridge. A request other
than `POST /notify/alerts` never reaches Apprise. No secret leaves vps1.

**Error and failure handling.**

- If the gate is down, the sidecar's POST fails, `escalate_apprise` returns False and logs. That is the same posture
  as an Apprise outage on vps1. Gatus's gate check pages the operator.
- If Apprise is down, the gate returns 502 and the sidecar behaves the same way.
- A failed preflight leaves a named red registrar failure.
- The boot race (wg0 after dockerd) can leave the gate unbound, as it can postgres. W-cb08c877 owns the fix; until
  then, the post-reboot check in the runbook names the gate.

**Testing approach.** Each item below is a test watched red first:

- The spoke URL rewrite: vps2 gives `10.99.0.1:8202`, vps1 is unchanged, and a custom host is untouched.
- The refusal is gone: the driver is called for vps2, and roles and analytics are provisioned.
- The preflight's four paths: present, missing (each file named), ssh failure, and an openrouter-only provider
  skipping the check.
- `fabrik plan` text no longer names D-1153.
- The gate conf is checked by a test that runs `nginx -t` in the pinned image, if the box allows docker in tests.
  Otherwise the deploy gate's three live probes (below) are its proof.

## Rejected alternatives

- **A — publish Apprise directly on `10.99.0.1:8202:8000` with `APPRISE_CONFIG_LOCK`.** It leaves stateless
  `POST /notify/` (send anywhere, server fetches attachments), `/details`, `/metrics` and the UI open to every mesh
  peer. Disabling stateless mode would break n8n (`docs/infrastructure/vps-urls.md:150`), and the posture rests on an
  app default OWASP says not to trust. It fails the coordinator's constraint, and no judge ranked it first.
- **C — an Apprise per spoke.** Three copies of the Telegram token, three rotation points and duplicated
  functionality. It fails three of the reality challenges.
- **D — a public Traefik route with an IP allow-list.** It puts an unauthenticated send endpoint on the internet,
  guarded by source IP. A spoke IP change silently kills alerts, and a label slip can shadow the 2FA router on the
  same Host.
- **E — a Traefik mesh entrypoint.** It needs a static-config change and a restart of the front door for every
  public site. A wg0 bind race would take Traefik down. In v2, every router without an `entrypoints` label would
  also attach to the mesh port.
- **A `WatchdogConfig.apprise_url` override** (the item's optional step). There is no consumer: every spoke uses the
  one gate URL, and `WatchdogConfig` forbids extra keys (`src/fabrik/spec_loader.py`, `class WatchdogConfig`). Not
  built (YAGNI); add it when a second gateway exists.
- **A preflight on spokes only.** It is the same mount requirement on vps1, and a branch would leave vps1 unchecked.
- **Exposing every `/notify/<key>`.** Only `alerts` is the fleet convention (`docs/infrastructure/vps-urls.md:149`).
  A second key is one more exact `location`, added when it exists.

## Lifecycle

- **Adoption / first run.** The deploy gate brings up `apprise-mesh-gate` alone
  (`docker compose up -d apprise-mesh-gate` in `/opt/apprise`; Apprise is not recreated). Three probes then run:
  - from a vps2 container, `POST /notify/alerts` answers 2xx;
  - `GET /get/alerts` answers 403;
  - a public-source connect to 8202 is dropped.

  Then the spokes' rules are refreshed, the code merges, and spoke-canary is applied with its watchdog. Rollback is
  `docker compose rm -sf apprise-mesh-gate` plus re-adding the opt-out; nothing else is touched.
- **Growth.**
  - Each new spoke-targeted watchdog adds no configuration.
  - A new spoke needs `FABRIK_MESH_ONLY_PORTS` (already in bootstrap).
  - A second notify key adds one `location`.
  - Trigger to revisit: more than one key, or alert volume beyond what one nginx worker serves. That is not
    plausible at 1 of 69 spoke specs (measured 2026-10-23).
- **Degradation.** The gate or Apprise down means alerts are lost on the spoke, with a sidecar warning in the log,
  and Gatus pages. A preflight failure means a named red registrar row and no sidecar. The wg0 boot race means the
  gate is unbound until recreated (W-cb08c877).
- **Retirement.** If Apprise is replaced, or alerting moves to a mesh-native bus, remove the gate service, the 8202
  row and the rewrite mapping together. D-1153's refusal comes back only if the mesh path is withdrawn.

## Shape / infra implications

- No scaffold type and no `shape:` flag change.
- spoke-canary's `watchdog` block returns to the defaults (`enabled` true, budget 1.0 USD / 200 invocations per
  `WatchdogConfig`).
- New infra: one compose service on vps1 (32M), one port 8202 (`PORTS.md`), one Gatus endpoint, and one entry in
  `FABRIK_MESH_ONLY_PORTS`.

## Documentation landing sites

- `PORTS.md`: a row for 8202 `apprise-mesh-gate`, mesh only.
- `docs/infrastructure/vps-urls.md`: `:149` loses "vps1 containers only"; § Mesh URLs (`:159-171`) gains
  `http://10.99.0.1:8202/notify/alerts`.
- `infra/vps1/apprise/compose.yaml` and `infra/vps1/apprise/mesh-gate.conf`: self-documenting comments.
- `configs/gatus/apps/apprise.yaml`: the gate endpoint.
- `docs/DECISIONS.md`: the approval row superseding D-1153's spoke refusal.
- `CHANGELOG.md`, and `INDEX.md` for the new conf file.

## Constraints Digest

| Quote | Source |
|---|---|
| Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik. | `.windsurf/rules/core/30-ops.md:357` |
| a spoke app reaches them at vps1's **mesh IP** (`10.99.0.1:5432` / `:6379` / `:8000`, published mesh-only, same ports) | `.windsurf/rules/core/30-ops.md:290` |
| `deploy.resources.limits.memory` is mandatory. | `.windsurf/rules/core/30-ops.md:149` |
| Use Debian/Ubuntu, NOT Alpine: | `.windsurf/rules/core/30-ops.md:24` |
| `escalate_apprise` \| POST to Apprise → Telegram \| always allowed | `.windsurf/rules/core/60-watchdog.md:105` |

How the design meets each row:

- The gate's `ports:` is the infra mesh-only exception, the same pattern as glitchtip's `10.99.0.1:8000:8000`. It is
  not an app port, and the public internet never reaches it, so row 1 is honoured in the form row 2 already permits.
- The memory limit is 32M (row 3).
- The image is a Debian `trixie` tag, not `alpine` (row 4).
- `escalate_apprise` stays the always-allowed alert path, now reachable from spokes (row 5).

## Open / blocking unknowns

- **U1 (open; production-data gate W-d9f067f4).** Does vps1's Apprise hold a stored config under key `alerts`? Per
  the source facts above, no stored key means `/notify/alerts` answers 404 on vps1 today too. The allowed listing
  shows `/config/0e` only, and the hash for `alerts` would be `/config/22`.
  - The deeper probe (file names and hashes) was refused by the permission classifier as a production read and as
    credential exploration. Both refusals are reported to the coordinator. The read-only confirmation (`docker exec
    apprise curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/status/alerts`) is boarded to the operator.
  - This design does not depend on the answer. The gate admits `/notify/alerts` either way, and no config route is
    reachable.
  - If the answer is 404, W-d9f067f4 (create the key, or move the convention) ships first. Until then a spoke alert
    is as dead as a vps1 alert.
- **U2 (resolved).** Does nginx keep a stale Apprise IP after a recreate? Yes, with a literal `proxy_pass`. The design
  uses `resolver 127.0.0.11` and a variable (nginx proxy docs, cited above).
- **U3 (open, pre-existing, W-cb08c877).** Docker does not order its start after wg0 on vps1. The gate shares the
  risk with every mesh service.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "allocate a port in PORTS.md" | IN | Architecture (8202); Documentation landing sites |
| I2 | "publish it in the live /opt/apprise/compose.yaml (deploy gate)" | CHANGED → IN | published through the gate service, not Apprise itself (Chosen approach; Rejected A) |
| I3 | "mirror infra/vps1/apprise" | IN | Architecture; Documentation landing sites |
| I4 | "rewrite the sidecar URL for spokes" | IN | Architecture — the spoke URL |
| I5 | "add WatchdogConfig.apprise_url if an override is wanted" | OUT-OF-SCOPE | Rejected alternatives (no consumer; YAGNI) |
| I6 | "sudo test -f <home>.json and <home>/.credentials.json" | IN | Architecture — the login preflight |
| I7 | "only when claude-code is primary or fallback" | IN | Architecture — the login preflight |
| I8 | "distinct text for an ssh failure vs MISSING" | IN | Architecture — the login preflight |
| I9 | "the target the ssh actually hits" | IN | Architecture — the login preflight (names the ssh host used) |
| I10 | "lift D-1153's refusal" | IN | Architecture — the spoke refusal is lifted |
| I11 | "remove the D-1156 opt-out … apply the canary as the spoke-watchdog proof" | IN | Architecture — the acceptance; Lifecycle |
| I12 | "10.99.0.1:8000 is glitchtip; 8000 is in the spokes' FABRIK_MESH_ONLY_PORTS drop list" | IN | port 8202 and its drop-list entry (Architecture — Firewall) |
| I13 | coordinator: "expose only POST /notify/<key> … deny /get, /add, /del, /json/urls and every config route unconditionally" | IN | the gate's policy |
| I14 | coordinator: "record … that the stored-config question was refused as a production read and why the design makes it moot" | IN | Open unknowns U1 |
| I15 | `/notify/alerts` may 404 on vps1 today (session finding) | OUT-OF-SCOPE | W-d9f067f4 (filed by the coordinator, P1, fleet) |
| I16 | vps1 docker.service not ordered after wg0 (session finding) | OUT-OF-SCOPE | W-cb08c877 |
| I17 | W-fc3eddd8 review residue (stale vps1 sidecar, port-less URL rewrite, glitchtip create_project) recorded only in W-37dda1e1's note | OUT-OF-SCOPE | W-20a37911 |
| I18 | firecrawl out of credits; brave key invalid (research arms) | OUT-OF-SCOPE | brave: W-12f21514 (awaiting the operator); firecrawl: mailed to infra at close |

Intake: 18 items — 12 IN (one CHANGED), 6 OUT-OF-SCOPE (each named above), 0 ASK.

## Cost

No new paid service. One nginx container at 32M on vps1. Build is about 40 lines of registrar code, a 12-line nginx
conf, a compose service and the doc edits.

## Validation

The design is accepted when all of the following hold:

- The gate's three live probes pass (2xx for a spoke POST to `/notify/alerts`, 403 for `/get/alerts`, a public
  connect dropped).
- spoke-canary applies green on vps2 with its watchdog sidecar running.
- A test alert posted from the vps2 sidecar container lands, provided U1 answers 200, or W-d9f067f4 has shipped.
- Every test listed under Testing approach was seen red first.
