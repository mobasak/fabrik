# Archived 2026-06-17 — orphan/retired specs

Verified unreferenced (no code/test/doc/Makefile refs; not auto-discovered — infra
specs are applied by explicit path), then archived (not deleted):

- **`authelia-coolify.yaml`** — the old Coolify-era *compose-format* file (starts with
  `services:`), superseded by the current fabrik-spec `specs/infrastructure/authelia.yaml`
  (`name:`/`type:`/`shape:`). Coolify decommissioned 2026-05-30.
- **`minio.yaml`** — MinIO is retired / not deployed on the fleet (object storage uses
  Backblaze B2 + Cloudflare R2 directly). No `minio` container on any of the 3 VPS.

(`specs/services/translator.yaml` is NOT archived — the translator *service* is retired,
but the spec is kept as a live test fixture referenced by `cli.py` + `tests/`.)
