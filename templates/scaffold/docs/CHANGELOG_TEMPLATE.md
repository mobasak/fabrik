# Changelog — [Project Name]

**Last Updated:** YYYY-MM-DD

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added — (YYYY-MM-DD)

- Initial project scaffolded

---

<!-- Entry format:

### Category — Title (YYYY-MM-DD)
- Action verb + file/function/endpoint + what changed

Categories: Added, Changed, Fixed, Removed, Security

Examples:
  ### Added — DNS provisioning endpoint (2026-04-09)
  - Add `POST /api/v1/zones/{domain}/provision` with DNSSEC and WAF support
  - Add `DnsManagerClient` Python SDK module

  ### Fixed — Health check false positives (2026-04-09)
  - Fix `/health` returning 200 when Redis is unreachable

  ### Security — API key validation (2026-04-09)
  - Add rate limiting on auth endpoints to prevent brute force

  ### Changed — Response format update (2026-04-09)
  - Change error responses from flat strings to `{"error": {"code", "message", "details"}}` shape
  - BREAKING: Remove `status_text` field from all responses

-->

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Incompatible API changes
- **MINOR** (0.X.0): New functionality, backwards compatible
- **PATCH** (0.0.X): Bug fixes, backwards compatible

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| X.Y.Z | YYYY-MM-DD | Brief summary |
| X.Y.Y | YYYY-MM-DD | Brief summary |

---

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Incompatible API changes
- **MINOR** (0.X.0): New functionality, backwards compatible
- **PATCH** (0.0.X): Bug fixes, backwards compatible

---

## Workflow Integration

**Step 3: CHANGELOG** in the agent completion contract requires one entry per task.

**Enforcement:** `python scripts/final_gate.py --lean --json` checks for changelog presence (Tier 1).

**Format required:**
```
### Category — Title (YYYY-MM-DD)
- Action verb + function/file + description
```

**Categories:** Added, Changed, Fixed, Removed, Security

Agents write entries manually. Gate enforces presence but not content quality.
