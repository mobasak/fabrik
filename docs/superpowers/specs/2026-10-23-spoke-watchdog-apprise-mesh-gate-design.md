# Spoke watchdogs alert through a mesh-only Apprise gate — design

Status: DRAFT
Owner: fleet · Work item: W-5dcafaef · supersedes the spoke branch of D-1153 and lifts D-1156 on acceptance

**Profile verdict:** the full section set. `Profile: delta` does not apply, because the gate is a new component.

**Size verdict:** the estimate is about 90 code lines across 5 code and config files:
`src/fabrik/orchestrator/infrastructure.py`, `src/fabrik/drivers/watchdog.py`, `infra/vps1/apprise/compose.yaml`,
`specs/services/spoke-canary.yaml` and `configs/gatus/apps/apprise.yaml`. That is within D-169's bounds, but only
after round 1 of `/fabrik-spec-review` cut the firewall file and the separate nginx conf. The review that had
already started was kept, since it is a superset of the `Size: small` path.

## Personas

- **PRIMARY — the operator.** The work item, filed in their name, states the need:
  *"Mesh-publish apprise for spoke watchdogs, then lift W-37dda1e1's spoke refusal"*. The intent behind it is
  D-052 and D-108: no spoke runs without a watchdog that can reach them. Their loop, counted (step budget **3**):
  1. Answer ONE deploy gate the coordinator boards, covering the gate container on vps1 and the attachment lock
     on Apprise.
  2. A spoke app with a watchdog is applied (spoke-canary is the proof).
  3. A spoke incident reaches their Telegram exactly as a vps1 incident does. Today step 3 is impossible.
- **A spoke watchdog sidecar** (automated, fabrik-lib `watchdog_sidecar`) — the SENDER.
  - It POSTs `{title, body}` to `WATCHDOG_APPRISE_URL` and counts any 2xx as delivered
    (`/opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:561-576`).
  - It holds no Apprise credential and needs none.
  - Like every spoke app since D-904, it carries its own vps1 Postgres DSN.
- **Apprise on vps1** (automated) — the RECEIVER.
  - It holds the notification URLs, which carry the Telegram bot token, and sends.
  - It must never expose its configuration, or a fetch of an arbitrary URL, to a mesh peer.
- **The mesh gate** (`apprise-mesh-gate`, new, automated) — admits exactly `POST /notify/alerts` and forwards it
  to Apprise as exactly that URI, refusing everything else. It holds no secret.
- **Every other mesh peer**, including a compromised spoke container — the adversary the gate is shaped against.
  It may send an alert; it may not read, change, redirect or make Apprise fetch anything.
- **The registrar** (`fabrik apply`, `src/fabrik/orchestrator/infrastructure.py`, fleet's code) — renders the
  spoke URL, runs the login preflight, and refuses a sidecar only for a cause it can name.
- **The coordinator** — boards the deploy gate and relays the operator's answer.
- **fleet** (builder) — builds and tests the code and runs every deploy step only after the operator's go:
  - bringing up the gate;
  - the three probes;
  - the attachment lock and its probe;
  - `ensure-apprise-alerts-config.sh --check`;
  - the spoke-canary apply.
- **The existing vps1 Apprise callers** (automated) — 18 files that keep `http://apprise:8000/...` over the local
  bridge and are untouched. They are:
  - Gatus: `configs/gatus/_base.yaml`, `apps/apprise.yaml`, `core/infra.yaml`;
  - n8n: `configs/n8n/workflows/backup-notification.json`, `uptime-alert.json`;
  - nine `scripts/sysadmin/` files: the daily, weekly, monthly and morning reports, `proactive-check.sh`,
    `fabrik-alert-canary.sh`, `ensure-apprise-alerts-config.sh` and the AI sysadmin's `system-prompt.txt`;
  - Backrest's hook (`src/fabrik/drivers/backrest.py`);
  - every vps1 watchdog (`src/fabrik/drivers/watchdog.py`, `src/fabrik/spec_loader.py`);
  - `libs/alerting/apprise.py`, which execs curl inside the container.

  The count is the grep in § Derivations.

Every feature below traces to the operator (alerts from spokes) or to the adversary row (the allow-list and the
attachment lock).

## Why this exists

D-1153 (2026-10-23) refuses every spoke-targeted watchdog because its sidecar could not alert:

- vps1's Apprise has no mesh port;
- its only route is `notify.vps1.ocoron.com` behind `authelia-forward` (2FA, `infra/vps1/apprise/compose.yaml:23`);
- WireGuard carries no DNS, so `apprise` does not resolve on a spoke.

A spoke app therefore runs with no watchdog, the gap D-052 and D-108 forbid, and spoke-canary opts out by hand
(D-1156) to keep its apply green. The pain is a fleet whose spokes cannot page the operator. The fix gives spoke
sidecars one narrow, deny-by-default path to Apprise over the mesh.

## Goal

A spoke watchdog sidecar's alert reaches Apprise over the WireGuard mesh, through a gate that admits only
`POST /notify/alerts`. The registrar renders that URL for spoke targets, checks the Claude login files the sidecar
mounts, and stops refusing spoke watchdogs. spoke-canary drops its opt-out and is applied as the proof.

## What exists today (executed 2026-10-23)

- **The sidecar URL.** Its default is `http://apprise:8000/notify/alerts` (`src/fabrik/drivers/watchdog.py:546`).
  `target_vps` is resolved at `:560`, and only the redis and postgres URLs are rewritten for a spoke (`:570-571`).
  The rewrite is `_rewrite_shared_infra_host`, anchored on `@host:` and `//host:`; it swaps the host and keeps the
  port (`src/fabrik/orchestrator/infrastructure.py:137-157`, hosts at `:127`, mesh IP at `:121`).
- **The D-1153 refusal.**
  - `_provision_watchdog` records a non-fatal failure for any non-vps1 target, on real and dry runs alike, before
    its dry-run branch (`:1607-1619`).
  - `provision()` withholds the watchdog DB roles and analytics for it (`:764-766`).
  - `fabrik plan` names the refusal (`:455-462`).
  - `_nonfatal` appends to `ctx.registrar_failures`, so the apply exits red (`:672-682`).
- **Tests that assert the refusal.**
  - `tests/test_watchdog_spoke_preflight.py`, five functions at `:29`, `:60`, `:71`, `:82`, `:102`; the last checks
    "refused on spoke vps2" and "D-1153" at `:109`. `:113` asserts a switched-off watchdog is never called
    refused, which stays true.
  - `tests/orchestrator/test_spoke_dsn_mesh.py::TestWatchdogSpokeRouting` (`:276-296`).
  - `test_a_vps1_watchdog_is_unchanged` (`tests/test_watchdog_spoke_preflight.py:46-57`) patches only
    `WatchdogDriver.provision`.
- **The Claude login mounts.** The sidecar bind-mounts `VPS_CLAUDE_HOME` and `VPS_CLAUDE_HOME.json` read-only
  (`src/fabrik/drivers/watchdog.py:143`, `:955-965`), and the driver does not create them. The provider defaults
  are `claude-code`/`openrouter` (`:596-597`).
- **The ssh driver** raises one `RuntimeError("SSH to … failed (rc=N): …")` for every non-zero exit and a
  `TimeoutExpired` for a timeout. With `dry_run=True` it runs nothing (`src/fabrik/drivers/ssh.py:207-241`).
- **Apprise on vps1.**
  - No host port, and the mirror equals the live compose. Both were read 2026-10-23; the live one via
    `ssh -o ProxyJump=vps2 vps 'sudo cat /opt/apprise/compose.yaml'`, secret lines filtered. Only the env var
    NAMES were read: `APPRISE_STATELESS_URLS`, `APPRISE_WORKER_COUNT`.
  - The image is the unpinned `caronc/apprise:latest` (`infra/vps1/apprise/compose.yaml:7`).
  - The fleet's `alerts` stateful key was created on 2026-07-12. Before that, the deployed image answered
    `/notify/alerts` with **204**: accepted, nothing sent (`scripts/sysadmin/ensure-apprise-alerts-config.sh:6-16`,
    `docs/infrastructure/vps-complete-inventory.md:512`).
- **vps1's network state** (live, 2026-10-23).
  - `ss -Hltn`: `10.99.0.1:3100 :5432 :6379 :8000 :9091`, `0.0.0.0:8201`. 8202 is free, and `PORTS.md` uses only
    8201 in 8200-8299.
  - `iptables -S DOCKER-USER`: RETURN for 10/8, 172.16/12, 192.168/16 and ports 80/443/6001/6002, then `-j DROP`.
    So vps1 drops any other published port from a public source. The spokes' `FABRIK_MESH_ONLY_PORTS` list
    (`scripts/bootstrap/bootstrap-config.sh:39-49`) guards only ports a SPOKE publishes.
  - Docker 29.0.2; `docker compose version` 2.40.3; `docker.service` has no `After=wg-quick@wg0` (pre-existing,
    W-cb08c877).
- **The spokes** (live `sudo test -f`, 2026-10-23). `/home/ozgur/.claude.json` and
  `/home/ozgur/.claude/.credentials.json` are present on vps2 and vps3, and vps2 reaches `10.99.0.1:8000`.
- **Gatus** probes Apprise by service name (`configs/gatus/apps/apprise.yaml`) and delivers its own alerts THROUGH
  Apprise (`configs/gatus/_base.yaml:20`).
- **Spoke-targeted specs:** 1 of 69 (§ Derivations).

## External facts (grounded live, 2026-10-23)

| Fact | Source |
|---|---|
| apprise-api routes: `/add`, `/del`, `/move` change config; `/get`, `/json/urls`, `/cfg` reveal it; `/details`, `/status`, `/qr`, `/auth`, the UI and both notify forms share one port. No `/metrics` route is in `api/urls.py` | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/api/urls.py (exa, full file) |
| `APPRISE_CONFIG_LOCK` gates `/get`, `/json/urls`, `/add`, `/del`, `/move`, `/cfg` — not `/notify/` or `/details`; no IP allow-list setting exists | https://raw.githubusercontent.com/caronc/apprise-api/master/README.md , https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/core/settings/__init__.py |
| Stateless `POST /notify/` accepts arbitrary `urls`; keyed `POST /notify/<key>` also accepts `attach`/`attachment` URLs (`_notify_attachments`) | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/api/views.py lines 3473-3505, 3647 (raw curl) |
| `APPRISE_ATTACH_SIZE <= 0` disables attachment parsing (master) | https://raw.githubusercontent.com/caronc/apprise-api/master/apprise_api/api/utils.py line 696 (raw curl) |
| On master, keyed notify with no stored config answers 404 "There was no configuration found" (the deployed image answered 204, per the repo's own measurement above — the image is older than master) | views.py lines 3696-3713 (raw curl) |
| A host-address-bound port "can be accessed via other host interfaces using direct routing to the host address" when IP forwarding is on | https://docs.docker.com/engine/network/port-publishing/ (exa raw) |
| A failed host-IP bind at container start is not retried by the restart policy; on Docker 29 the container can return with only `lo` | https://github.com/moby/moby/issues/39559 , https://github.com/moby/moby/issues/53928 (exa) |
| nginx `limit_except` "Limits allowed HTTP methods inside a location"; a `proxy_pass` with variables resolves a name "using a resolver" | https://nginx.org/en/docs/http/ngx_http_core_module.html#limit_except , https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass (raw curl) |
| Docker's embedded DNS server address is `127.0.0.11` on user-defined networks | https://docs.docker.com/engine/network/ (WebFetch) |
| Compose top-level `configs` with inline `content` | executed: `docker compose up` with a `content:` config on Compose 2.40.3 (the vps1 version), § Derivations |
| Traefik v2.11 entrypoints are "startup configuration"; only the dynamic configuration changes "without restarting"; routers with no entrypoint accept every entrypoint | https://raw.githubusercontent.com/traefik/traefik/v2.11/docs/content/getting-started/configuration-overview.md lines 16-39 , https://raw.githubusercontent.com/traefik/traefik/v2.11/docs/content/routing/routers/index.md (raw curl) |
| `nginx:1.30-trixie` exists (amd64), updated 2026-10-21 | https://hub.docker.com/v2/repositories/library/nginx/tags/1.30-trixie (raw curl) |
| "an application should be configured to deny access by default"; "explicit configuration should be preferred over relying on framework or library defaults" | https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html (WebSearch → exa) |
| Centralise secrets rather than copying them across services | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html (WebSearch → exa) |

## Chosen approach — B: an nginx allow-list gate beside Apprise

The three-seat judge panel received five approaches in alphabetical order with no recommendation. All three ranked
B first, from three angles (security, total cost, rollout blast radius): `B,C,E,A,D` · `B,A,E,D,C` · `B,E,A,D,C`.

**The gate.** A second service, `apprise-mesh-gate`, is added to the live `/opt/apprise/compose.yaml` and its
mirror `infra/vps1/apprise/compose.yaml`:

- `image: nginx:1.30-trixie`
- network `fabrik`
- `ports: - "10.99.0.1:8202:8202"`
- `restart: unless-stopped`
- `deploy.resources.limits.memory: 32M`
- a healthcheck `curl -fsS http://127.0.0.1:8202/healthz`
- no Traefik labels

Its whole policy is a top-level compose `configs:` entry with inline `content:`, mounted at
`/etc/nginx/conf.d/default.conf`. The compose file therefore stays the single artifact, with no separate conf to
copy to the box:

```
server {
    listen 8202;
    client_max_body_size 64k;
    resolver 127.0.0.11 valid=10s;
    set $apprise http://apprise:8000;
    location = /notify/alerts {
        limit_except POST { deny all; }
        proxy_pass $apprise/notify/alerts;
    }
    location = /healthz { return 200; }
    location / { return 403; }
}
```

(In the compose file each `$` is written `$$`.) What each part does:

- The exact `location =` matches the normalised path.
- Because `proxy_pass` names the URI, Apprise always receives exactly `POST /notify/alerts`, with no query string
  and no raw-path variant.
- The resolver re-resolves `apprise` after any Apprise recreate.

All three were executed (§ Derivations).

**The attachment lock.** Apprise gains `APPRISE_ATTACH_SIZE: "0"`, so the one admitted route cannot be made to
fetch a URL. None of the 18 caller files uses attachments (§ Derivations). It is applied as its own deploy step,
because it recreates the Apprise container. That step is proven live by a POST carrying `attach` that must be
refused, and by `ensure-apprise-alerts-config.sh --check` returning 200.

**The spoke URL.**

- A new `_rewrite_mesh_gated_url(url, target_vps)` in `src/fabrik/orchestrator/infrastructure.py` swaps the
  authority `//apprise:8000/` for `//10.99.0.1:8202/` when the target is not vps1. The constants sit beside
  `_HUB_MESH_IP`.
- It is stricter than the shared rewrite: it matches the port and the slash, and has no `@` arm, because the
  Apprise URL carries no userinfo.
- `src/fabrik/drivers/watchdog.py` calls it on `apprise_url` after `target_vps` is resolved (`:560`), beside
  `:570-571`.
- vps1 keeps `http://apprise:8000/notify/alerts`.

**The spoke refusal is lifted.**

- `_provision_watchdog` no longer refuses on target alone (`:1607-1619` removed).
- `provision()` provisions the watchdog roles and analytics for every target again (`:764-766` drops its vps1
  test).
- The `fabrik plan` clause (`:455-462`) is removed.
- D-1153's spoke branch is superseded by this spec's approval row.

**The login preflight, on every target, real runs only.** It runs whenever `llm_provider_primary` or
`llm_provider_fallback` is `claude-code`.

- **Where it sits:** in `_provision_watchdog`, after the dry-run branch (a dry run logs "would check the Claude
  login files on <target>" and makes no ssh) and before the driver import.
- **What it runs:** one call, `ssh(cmd, timeout=30)`, inside `_target_vps_env(ctx)`:

  ```
  sudo -n sh -c 'for f in "$@"; do if test -f "$f"; then echo "present $f"; else echo "missing $f"; fi; done' _ <home>.json <home>/.credentials.json
  ```

  `<home>` is `VPS_CLAUDE_HOME`. Both paths are passed through `shlex.quote`, because the value comes from the
  operator's `FABRIK_VPS_CLAUDE_HOME`.
- **How the result is read:**
  - When sudo works, the script exits 0 whatever it finds, so every `missing <f>` line names the absent file.
  - Any exception from the call is "could not check <target>: <the error's one-line text>" and never reads as
    missing. That covers a `RuntimeError` (sudo refused, an ssh transport failure, rc 255), a `TimeoutExpired`,
    and the `ValueError` subclasses `SshHostError` and `JumpConfigError` (`src/fabrik/drivers/ssh.py:104`,
    `:121`). It is caught as `Exception`, like the driver call below it (`infrastructure.py:1628-1650`).
- **Either failure** records `_nonfatal(ctx, "watchdog", …)` naming the target, which `FABRIK_VPS_SSH_HOST` was
  swapped to, and skips the sidecar. The app stays deployed and the apply ends red, as D-1153's refusal did.
- **Why every target and not only spokes:** the mount requirement is identical on vps1, so one rule with no branch
  closes the class. The cost is one ssh call per real watchdog apply.

**Firewall.** No change. vps1's live `DOCKER-USER` chain already drops 8202 from any public source, and allows it
from 10/8, which covers the mesh. The spokes' drop list guards spoke-published ports only, and no spoke publishes
8202.

**The acceptance.** Remove `watchdog: {enabled: false}` and its D-1156 comment from
`specs/services/spoke-canary.yaml`, then `fabrik apply` it on vps2.

**fabrik-lib / vendor ladder** (checked against `/opt/fabrik-lib/README.md`):

| Capability | Verdict | Why |
|---|---|---|
| Notification send | consume (vps1 Apprise) | already deployed; no new gateway |
| Path/method allow-list | consume (official `nginx` image) | no fabrik-lib module is a reverse proxy; the image needs only a config |
| URL rewrite, login preflight | build (registrar glue, ~40 lines) | registrar logic, not a reusable module; no 🆕 fabrik-lib candidate |
| Sidecar | unchanged (vendored `watchdog_sidecar`) | the URL is env; no upstream change |

**Data flow (invariants).**

- A spoke sidecar resolves nothing by name.
- Its only Apprise touchpoint is `10.99.0.1:8202`, and the gate's only upstream is `apprise:8000` over the vps1
  `fabrik` bridge.
- No request other than `POST /notify/alerts` reaches Apprise, and that one arrives with a fixed URI and no query.
  It is processed with no attachment parsing once U4's refused-`attach` probe has passed.
- No Apprise secret or configuration leaves vps1. The sidecar's own Postgres DSN does travel to the spoke, as every
  spoke app's has since D-904.

**Error and failure handling.**

- **The gate is down:** the sidecar's POST fails and `escalate_apprise` returns False and logs. Gatus's gate
  endpoint pages the operator, because Gatus reaches Apprise directly.
- **Apprise is down:** the gate answers 502. Gatus cannot page either, since it delivers through Apprise. That is
  the existing single point of failure, not widened here, and the alertmanager path is unchanged.
- **A 204 from Apprise** (a lost `alerts` key) counts as delivered in the sidecar. That class is owned by
  W-d9f067f4: the `--check` after any Apprise deploy, and the sidecar treating 204 as failure.
- **A failed preflight** leaves a named red registrar row and no sidecar.
- **The boot race** (wg0 after dockerd) can leave the gate unbound, as it can postgres (W-cb08c877).

**Testing approach** (each new test watched red first):

- **New tests:**
  - the URL rewrite: vps2 → `10.99.0.1:8202`; vps1 unchanged; another host untouched; a userinfo URL untouched;
  - the refusal is gone: the driver is called for vps2, and the roles and analytics are provisioned;
  - the preflight: present; one file missing (named); both missing; `RuntimeError` → "could not check"; a timeout
    → "could not check"; a `JumpConfigError` → "could not check"; an openrouter-only provider skips the check; a dry run makes no ssh;
  - `fabrik plan` text no longer names D-1153.
- **Existing tests, rewritten:**
  - `tests/test_watchdog_spoke_preflight.py`: the refusal tests are inverted into the above, the plan test is
    re-pointed, and `test_a_vps1_watchdog_is_unchanged` patches the preflight;
  - `TestWatchdogSpokeRouting` patches the preflight (its specs default to `claude-code`) and asserts that the
    vps2 driver call runs with the host swapped.
- **The gate's policy** is proven by the probe in § Derivations. The deploy gate's live probes are its production
  proof.

## Rejected alternatives

- **A — publish Apprise directly on `10.99.0.1:8202:8000` with `APPRISE_CONFIG_LOCK`.** Stateless `POST /notify/`
  (send anywhere), `/details` and the UI stay open to every mesh peer. Disabling stateless would break n8n
  (`docs/infrastructure/vps-urls.md:150`), and the posture rests on an app default that OWASP says not to trust.
  It fails the coordinator's constraint.
- **C — an Apprise per spoke.** Three copies of the Telegram token and three rotation points.
- **D — a public Traefik route with an IP allow-list.** An unauthenticated send endpoint on the internet, guarded
  by source IP; a spoke IP change silently kills alerts.
- **E — a Traefik mesh entrypoint.** A startup-configuration change and a restart of the front door for every
  public site. A wg0 bind race would take Traefik down, and every router without an entrypoint label would also
  answer on the mesh port.
- **A host-level listener** (a systemd socat or nginx on vps1's host). It sidesteps Docker's bind race. But it adds
  a host service outside compose and its mirror, a second supervision model, and it still needs the same path
  allow-list. The race is W-cb08c877's to fix for every mesh service at once.
- **Apprise's own `APPRISE_AUTH_REQUIRED`.** It would put a credential in every sidecar's env, gates the whole API
  rather than one route, and still leaves the other routes reachable to anyone holding it.
- **A `WatchdogConfig.apprise_url` override** (the item's optional step). It has no consumer: every spoke uses the
  one gate URL, and `WatchdogConfig` forbids extra keys (`src/fabrik/spec_loader.py:530`). Not built (YAGNI).
- **A preflight on spokes only.** The mount requirement is the same on vps1.
- **Adding 8202 to the spokes' `FABRIK_MESH_ONLY_PORTS`.** It protects nothing: the gate runs on vps1, whose chain
  is default-deny.
- **Exposing every `/notify/<key>`.** Only `alerts` is the fleet convention (`docs/infrastructure/vps-urls.md:149`).
  A second key is one more exact `location`.

## Lifecycle

- **Adoption / first run.** One deploy gate, run by fleet after the operator's go, in this order:
  1. In `/opt/apprise`, copy the mirror's compose (backup first), then `docker compose up -d apprise-mesh-gate`.
     This touches only the new service.
  2. Run three probes:
     - from a vps2 container, `POST /notify/alerts` answers 2xx;
     - `GET /get/alerts` answers 403;
     - a public-source connect to 8202 is dropped.
  3. `docker compose up -d apprise` for the attachment lock. This recreates the one Apprise container, so every
     vps1 caller, Gatus included, loses its alert path for the seconds of the restart; run it at a quiet moment.
     Then a POST with `attach` is refused, and `ensure-apprise-alerts-config.sh --check` answers 200.
  4. Merge the code, then apply spoke-canary with its watchdog on vps2.
- **Rollback**, in reverse order:
  1. Re-add the canary opt-out, revert the code merge so no new spoke sidecar points at the gate, and remove
     spoke-canary's running `<id>-watchdog` sidecar on vps2 by hand. An `enabled: false` re-apply leaves a running
     sidecar in place, and it would keep posting to a dead port.
  2. `docker compose rm -sf apprise-mesh-gate`.
  3. Drop the attachment env and `up -d apprise`.
- **Growth.**
  - Each new spoke-targeted watchdog adds no configuration, and a new spoke needs nothing on the gate.
  - A second notify key adds one `location`.
  - Revisit at more than one key, or at alert volume beyond what one nginx worker serves — not plausible at 1 of 69
    spoke specs.
- **Degradation.** As in Error and failure handling.
- **Retirement.** If Apprise is replaced or alerting moves to a mesh-native bus, remove the gate service, the 8202
  row and the rewrite together. D-1153's refusal returns only if the mesh path is withdrawn.

## Shape / infra implications

- No scaffold type and no `shape:` flag change.
- spoke-canary's `watchdog` block returns to the `WatchdogConfig` defaults.
- New infra: one compose service on vps1 (32M), port 8202 (`PORTS.md`), one Apprise env var and one Gatus endpoint
  (`http://apprise-mesh-gate:8202/healthz`, by service name).
- The gate's `ports:` is an exception to the `.windsurf/rules/core/30-ops.md:357` invariant. It is recorded by the
  approval D-row, beside the postgres, redis and glitchtip precedent (`.windsurf/rules/core/30-ops.md:290`).

## Documentation landing sites

- **`PORTS.md`:** a row for 8202 `apprise-mesh-gate`, mesh only, and `:34`'s Apprise row loses "no host port"
  where it describes the stack.
- **`docs/infrastructure/vps-urls.md`:**
  - `:149` is rewritten: the "vps1 containers only … refused until it is mesh-published, W-37dda1e1" clause is
    replaced by the spoke URL;
  - § Mesh URLs (`:159-171`) gains `http://10.99.0.1:8202/notify/alerts`;
  - the mesh-only port table (`:291-295`) gains 8202.
- **`infra/vps1/apprise/compose.yaml`:** its header comment (`:3-4`, "Nothing needs one") is rewritten.
- **`src/fabrik/orchestrator/infrastructure.py`:** the D-1153 docstring and comments (`:132`, `:764`, `:1601`) are
  rewritten.
- **`configs/gatus/apps/apprise.yaml`:** the gate endpoint.
- **`docs/DECISIONS.md`:** the approval row (it supersedes D-1153's spoke branch and records the 30-ops port
  exception).
- **`CHANGELOG.md`.**

## Constraints Digest

| Quote | Source |
|---|---|
| Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik. | `.windsurf/rules/core/30-ops.md:357` |
| a spoke app reaches them at vps1's **mesh IP** (`10.99.0.1:5432` / `:6379` / `:8000`, published mesh-only, same ports) | `.windsurf/rules/core/30-ops.md:290` |
| `deploy.resources.limits.memory` is mandatory. | `.windsurf/rules/core/30-ops.md:149` |
| Use Debian/Ubuntu, NOT Alpine: | `.windsurf/rules/core/30-ops.md:24` |
| `escalate_apprise` \| POST to Apprise → Telegram \| always allowed | `.windsurf/rules/core/60-watchdog.md:105` |

How the design meets each row:

- **Row 1** binds; the gate's mesh-only `ports:` is an exception, recorded by D-row (Shape / infra implications).
  Row 2 shows the precedent, not a licence.
- **Row 3:** 32M.
- **Row 4:** a Debian `trixie` tag.
- **Row 5:** `escalate_apprise` becomes reachable from spokes.

## Open / blocking unknowns

- **U1 — resolved.** Does `/notify/alerts` deliver on vps1 today? The repo's own measurement says yes, since
  2026-07-12 (`scripts/sysadmin/ensure-apprise-alerts-config.sh:6-16`). The deeper store probe was refused by the
  permission classifier, as a production read and as credential exploration, and both refusals were reported to the
  coordinator. The design does not depend on it, and the deploy gate runs the script's `--check` (step 3).
- **U2 — resolved.** nginx keeps a stale upstream IP with a literal `proxy_pass`; the resolver form does not. Both
  were executed (§ Derivations).
- **U3 — open, pre-existing (W-cb08c877).** Docker is not ordered after wg0 on vps1.
- **U4 — open, measured at deploy.** The attachment lock is proven on master's source. The deployed `latest` image
  is older (it answered 204 where master answers 404), so step 3's refused-`attach` probe is its proof. If the
  probe is not refused, the deploy stops and the finding goes to a new item before the canary apply.

## Derivations

| Claim | Command | Output |
|---|---|---|
| 18 caller files (Personas) | `command grep -rlI "apprise:8000\|notify/alerts" src scripts infra configs templates` (17) + `libs/alerting/apprise.py` (execs curl in the container, `infra/vps1/apprise/compose.yaml:4`) | 17 + 1 |
| no caller uses attachments | `command grep -n -i attach` over those 18 files | 0 lines |
| 1 of 69 spoke specs | `ls specs/services/*.yaml \| wc -l` → 69; `command grep -l "^target_vps: *vps[23]" specs/services/*.yaml` → `specs/services/spoke-canary.yaml` | 69 · 1 |
| the gate policy | a local probe (2026-10-23): `nginx:1.30-trixie` on a docker network with a Python echo stand-in aliased `apprise`, the conf above, `curl` per row | see below |

```
# probe output, summarised by row (gate on 127.0.0.1:18202; the echo upstream prints METHOD PATH)
POST /notify/alerts (json)            200 POST /notify/alerts
POST /notify/alerts?tag=all           200 POST /notify/alerts
GET|HEAD|PUT /notify/alerts           403
POST /notify/alerts/  /notify/  /notify  /NOTIFY/alerts   403
POST /notify/%61lerts  /notify//alerts  /notify/alerts/../alerts   200 POST /notify/alerts
GET /get/alerts  /json/urls/alerts  /details  /metrics  /   403 ; POST /add/alerts 403
GET /healthz                          200
POST 70000-byte body                  413
upstream recreated (10.212.16.2 → .4): resolver form 200 · literal proxy_pass 502
docker compose up with configs.content on Compose 2.40.3: gate healthy, POST 200, /get 403
```

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "allocate a port in PORTS.md" | IN | 8202; Documentation landing sites |
| I2 | "publish it in the live /opt/apprise/compose.yaml (deploy gate)" | CHANGED → IN | published through the gate service in that compose, not Apprise itself (Chosen approach; Rejected A) |
| I3 | "mirror infra/vps1/apprise" | IN | the gate and its inline config live in the mirror compose |
| I4 | "rewrite the sidecar URL for spokes" | IN | Chosen approach — the spoke URL |
| I5 | "add WatchdogConfig.apprise_url if an override is wanted" | OUT-OF-SCOPE | Rejected alternatives (no consumer; YAGNI) |
| I6 | "sudo test -f <home>.json and <home>/.credentials.json" | IN | the login preflight |
| I7 | "only when claude-code is primary or fallback" | IN | the login preflight |
| I8 | "distinct text for an ssh failure vs MISSING" | IN | the login preflight ("could not check" vs a named missing file) |
| I9 | "the target the ssh actually hits" | IN | the login preflight (names the swapped `FABRIK_VPS_SSH_HOST`) |
| I10 | "lift D-1153's refusal" | IN | the spoke refusal is lifted |
| I11 | "remove the D-1156 opt-out … apply the canary as the spoke-watchdog proof" | IN | the acceptance; Lifecycle |
| I12 | "10.99.0.1:8000 is glitchtip; 8000 is in the spokes' FABRIK_MESH_ONLY_PORTS drop list" | IN | port 8202; the drop list is rejected as protecting nothing (Rejected alternatives) |
| I13 | coordinator: "expose only POST /notify/<key> … deny /get, /add, /del, /json/urls and every config route unconditionally" | IN | the gate's policy (only `/notify/alerts`) |
| I14 | coordinator: "record … that the stored-config question was refused as a production read and why the design makes it moot" | IN | U1 |
| I15 | the 204 silent-drop class (session finding) | OUT-OF-SCOPE | W-d9f067f4 (coordinator-retitled: `--check` after deploys, 204 as failure in the sidecar) |
| I16 | vps1 docker.service not ordered after wg0 (session finding) | OUT-OF-SCOPE | W-cb08c877 |
| I17 | W-fc3eddd8 review residue recorded only in W-37dda1e1's note | OUT-OF-SCOPE | W-20a37911 |
| I18 | firecrawl out of credits; brave key invalid (research arms) | OUT-OF-SCOPE | brave: W-12f21514 (awaiting the operator); firecrawl: mailed to infra at close |
| I19 | keyed notify accepts attachment URLs (review finding) | IN | the attachment lock |

Intake: 19 items — 14 IN (one CHANGED), 5 OUT-OF-SCOPE (each named above), 0 ASK.

## Cost

No new paid service. One nginx container at 32M on vps1. About 40 lines of registrar code, about 30 lines of
compose (service plus inline config), one env var, the test rewrites, and the doc edits.

## Validation

The design is accepted when all of the following hold:

- Deploy steps 2-3 pass:
  - a spoke POST to `/notify/alerts` answers 2xx;
  - `/get/alerts` answers 403;
  - a public connect to 8202 is dropped;
  - an `attach` POST is refused;
  - `--check` answers 200.
- spoke-canary applies green on vps2 with its watchdog sidecar running.
- A test alert posted from the vps2 sidecar container lands in Telegram.
- Every test listed under Testing approach was seen red first.
