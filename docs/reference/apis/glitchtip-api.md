# GlitchTip API Reference — Live-Captured Contract

**Source:** Phase 4-pre Task 1 live probe against `https://errors.vps1.ocoron.com` (GlitchTip v6.1.5)
**Captured:** 2026-04-18 UTC+3 via `scripts/probes/glitchtip_probe.sh`
**Last Verified:** 2026-07-19 (contract re-verified against the driver + `TestWireShape` tests + live Authelia probe; the HTTP probe's JSON snapshots date from 2026-04-22 — re-run `scripts/probes/glitchtip_probe.sh` to refresh them)
**Artifacts:** `.tmp/phase-4-pre/glitchtip-probe-{create,keys}.json` (regenerate by rerunning the probe)

This document locks the **exact JSON field names the `glitchtip.py` driver (501 lines) must parse**. Any drift between GlitchTip versions silently breaking the driver will be caught by rerunning this probe as a contract test.

> **Lesson 31 (2026-04-22):** DSN injection into the container MUST be verified via `docker inspect "{{.Config.Env}}"` — NOT via `docker exec printenv`. Published images with `ENTRYPOINT ["something"]` reject `docker exec` with exit 126, making `printenv` unreliable for verification. The driver's `verify_dsn_injection()` helper already uses the correct method. See `docs/LESSONS_LEARNT.md` §Lesson 31.

## Authentication

All endpoints require a **Bearer token** with the listed scopes. Tokens are created at:
`https://errors.vps1.ocoron.com/profile/auth-tokens/` → **Create Token**

Required scopes for the Fabrik driver:

- `project:read`
- `project:write`
- `project:admin`
- `team:admin`

Header: `Authorization: Bearer <token>`

Token stored in `/opt/fabrik/.env` as `GLITCHTIP_AUTH_TOKEN` (never committed, validated clean — no pipe or escape characters).

## Endpoint 1: Create Project

**Purpose:** Called by `glitchtip.py::create_project()` for every new Fabrik project.

- **Method:** `POST`
- **Path:** `/api/0/teams/{org_slug}/{team_slug}/projects/`
- **Body:**
  ```json
  {"name": "my-project", "platform": "python"}
  ```
- **Success status:** `201 Created`

### Response shape (verified live)

```json
{
  "name": "fabrik-probe-1776543606",
  "slug": "fabrik-probe-1776543606",
  "id": "2",
  "avatar": {"avatarType": "", "avatarUuid": null},
  "color": "",
  "features": [],
  "hasAccess": true,
  "isBookmarked": false,
  "isInternal": false,
  "isMember": true,
  "isPublic": false,
  "scrubIPAddresses": true,
  "dateCreated": "2026-04-18T20:21:33.793Z",
  "platform": "python",
  "firstEvent": null,
  "eventThrottleRate": 0
}
```

### Fields the driver consumes

| Field       | Type   | Driver use                                                    |
|-------------|--------|---------------------------------------------------------------|
| `slug`      | string | Primary key for subsequent API calls (keys fetch, delete)     |
| `id`        | string | Numeric project ID (appears in DSN path). **Note: string, not int.** |
| `name`      | string | Idempotency check — driver skips create if name already exists |
| `platform`  | string | Echoed back, not mutated                                      |
| `dateCreated` | string | ISO-8601 UTC — logged for audit trail                       |

Other fields are ignored by the driver.

## Endpoint 2: Fetch DSN (Project Keys)

**Purpose:** Called by `glitchtip.py::get_dsn()` after create_project; the DSN is the value the downstream app exports as `SENTRY_DSN` / `GLITCHTIP_DSN`.

- **Method:** `GET`
- **Path:** `/api/0/projects/{org_slug}/{project_slug}/keys/`
- **Success status:** `200 OK`

### Response shape (verified live)

Returns an **array**. First element is the default key (auto-created with the project).

```json
[
  {
    "name": "",
    "rateLimit": null,
    "dateCreated": "2026-04-18T20:21:33.796Z",
    "id": "a98d86d6-0db0-4b34-ac77-668d7f69b58b",
    "dsn": {
      "public":  "http://a98d86d60db04b34ac77668d7f69b58b@localhost:8000/2",
      "secret":  "http://a98d86d60db04b34ac77668d7f69b58b@localhost:8000/2",
      "security":"http://localhost:8000/api/2/security/?glitchtip_key=a98d86d60db04b34ac77668d7f69b58b"
    },
    "label": "",
    "public": "a98d86d6-0db0-4b34-ac77-668d7f69b58b",
    "projectID": 2
  }
]
```

### Fields the driver consumes

| Field         | Type   | Driver use                                           |
|---------------|--------|------------------------------------------------------|
| `[0].dsn.public` | string | The **public DSN** to inject into apps (client-side or server) |
| `[0].dsn.secret` | string | Rarely used in modern SDKs; available for legacy clients |
| `[0].id`      | string | Key UUID — used to revoke or rotate the key later    |
| `[0].projectID` | int  | Numeric project id — for cross-reference with Prometheus labels |

### ⚠️ Known configuration gap (captured by probe)

The DSNs above use `localhost:8000` as the host — wrong for external clients (`GLITCHTIP_DOMAIN` unset
on the live app). **The driver handles this (G7):** `glitchtip.py` unconditionally canonicalizes any
loopback-host DSN to the public `GLITCHTIP_URL` host (`_canonicalize_dsn` / `_assert_routable_dsn`,
`glitchtip.py:98-175`, with a warning log) and raises only if the DSN is still unroutable after the
rewrite. The service-side fix — `GLITCHTIP_DOMAIN=https://errors.vps1.ocoron.com` in the compose
`environment:` block (`specs/infrastructure/glitchtip.yaml` / `/opt/glitchtip/compose.yaml` on vps1,
then `docker compose up -d`) — would make GlitchTip emit correct DSNs at the source; until then the
driver's rewrite is the safety net.

## Endpoint 3: Delete Project (cleanup / rollback)

**Purpose:** Called by `glitchtip.py::delete_project()` for rollback and by the probe for idempotency.

- **Method:** `DELETE`
- **Path:** `/api/0/projects/{org_slug}/{project_slug}/`
- **Body:** (none)
- **Success status:** `204 No Content` (empty response body)

No response fields to parse. Driver checks `response.status_code == 204`.

## Endpoint 4 (absent): Alert-webhook registration

GlitchTip exposes **no API** to register alert webhooks — `/rules/`, `/alert-rules/`, and `/alerts/`
all 404 (probed 2026-06-29; see `glitchtip.py::webhook_registration_reminder`, which surfaces the
manual step). Webhook recipients are created in the GlitchTip **UI** per project (the watchdog
`:8889` ingest hookup is a per-new-project manual step — `cli._emit_glitchtip_webhook_reminder`).

## Organization / Team enumeration (one-time setup)

These are **not** called at provisioning time (org + team are constant per VPS). Only called once during Fabrik setup to capture `GLITCHTIP_ORG_SLUG` + `GLITCHTIP_TEAM_SLUG` into `.env`.

### List teams in org

- **Method:** `GET`
- **Path:** `/api/0/organizations/{org_slug}/teams/`
- **Response (captured live):**
  ```json
  [{"slug": "vps1", "name": null, "id": "1"}]
  ```

Used to discover `TEAM_SLUG=vps1` for the Fabrik VPS.

## Security boundary

GlitchTip is **Authelia full-bypass** (live-verified 2026-07-19: public `GET /` returns 200, no auth
redirect). The Traefik router does carry `authelia-forward@docker`, but the Authelia access-control
rule for `errors.vps1.ocoron.com` is **bypass** — mandated by LESSONS_LEARNT §8.13: forward-auth on a
django-allauth SPA breaks login/signup (XHR gets a 302→HTML instead of JSON). The weekly
`audit_authelia_gates.py` cron encodes this expectation. The chain:

1. **Iptables DOCKER-USER chain** — only 80/443/6001/6002 allowed publicly
2. **Traefik HTTPS termination** — routes `errors.vps1.ocoron.com` → `glitchtip-web:8000` on the `fabrik` Docker network
3. **GlitchTip's own django-allauth login + TOTP** — the effective auth layer (app-layer, per §8.13)
4. **Bearer-token auth** on all `/api/0/*` paths for machine-to-machine calls

**Important for Sentry SDK ingestion:** Fabrik microservices send Sentry-compatible events to the **internal** `http://glitchtip-web:8000` Docker DNS alias, NOT the public `https://errors.vps1.ocoron.com`. The Authelia gate at the public hostname does not affect SDK ingestion — see `docs/infrastructure/vps-urls.md` "Fabrik Microservices — GlitchTip DSN Convention".

## Running the probe (contract test)

```bash
bash /opt/fabrik/scripts/probes/glitchtip_probe.sh
```

Reads `.env` for `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG`. Creates a throwaway `fabrik-probe-<epoch>` project, fetches its DSN, deletes it. Compare stdout against the shapes in this document — any drift means the driver needs updating.

Add `--keep` to skip cleanup when you want to inspect a probe project in the GlitchTip UI.
