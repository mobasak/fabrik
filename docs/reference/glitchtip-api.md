# GlitchTip API Reference — Live-Captured Contract

**Source:** Phase 4-pre Task 1 live probe against `https://errors.vps1.ocoron.com` (GlitchTip v6.1.5)
**Captured:** 2026-04-18 UTC+3 via `scripts/probes/glitchtip_probe.sh`
**Artifacts:** `.tmp/phase-4-pre/glitchtip-probe-{create,keys}.json` (regenerate by rerunning the probe)

This document locks the **exact JSON field names the `glitchtip.py` driver (Phase 4f) must parse**. Any drift between GlitchTip versions silently breaking the driver will be caught by rerunning this probe as a contract test.

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

The DSNs above use `localhost:8000` as the host — this is **wrong** for external clients. GlitchTip's Coolify service is missing the `GLITCHTIP_DOMAIN` environment variable (expected value: `https://errors.vps1.ocoron.com`).

**Fix (future work):** Add `GLITCHTIP_DOMAIN=https://errors.vps1.ocoron.com` to the GlitchTip compose environment via Coolify UI → Environment Variables → redeploy. After that, DSNs will be emitted as `https://...@errors.vps1.ocoron.com/2`.

The driver must either:

1. Accept the DSN as-is and let the user fix the service config, OR
2. Post-process the DSN to replace the host if `GLITCHTIP_URL_OVERRIDE` is set.

Option 1 is preferred — cleaner; misconfiguration is visible rather than masked.

## Endpoint 3: Delete Project (cleanup / rollback)

**Purpose:** Called by `glitchtip.py::delete_project()` for rollback and by the probe for idempotency.

- **Method:** `DELETE`
- **Path:** `/api/0/projects/{org_slug}/{project_slug}/`
- **Body:** (none)
- **Success status:** `204 No Content` (empty response body)

No response fields to parse. Driver checks `response.status_code == 204`.

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

GlitchTip's `errors.vps1.ocoron.com` is **fully bypassed** in Authelia (same tier as `pdf`, `browser`, `dns` microservices). The security boundary is:

1. **Iptables DOCKER-USER chain** — only 80/443/6001/6002 allowed publicly
2. **Traefik HTTPS termination** — routes `errors.vps1.ocoron.com` → `glitchtip-web:8000` on the `coolify` Docker network
3. **GlitchTip's own django-allauth auth** — TOTP 2FA enforced for admin users
4. **Bearer-token auth** on all `/api/0/*` paths for machine-to-machine calls

Authelia forward-auth is **intentionally not** in this chain for GlitchTip — see `docs/LESSONS_LEARNT.md §8.13` for the rationale.

## Running the probe (contract test)

```bash
bash /opt/fabrik/scripts/probes/glitchtip_probe.sh
```

Reads `.env` for `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG`. Creates a throwaway `fabrik-probe-<epoch>` project, fetches its DSN, deletes it. Compare stdout against the shapes in this document — any drift means the driver needs updating.

Add `--keep` to skip cleanup when you want to inspect a probe project in the GlitchTip UI.
