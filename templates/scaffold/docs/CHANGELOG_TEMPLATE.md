# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), adapted for Fabrik workflow.

**Entries written by:** Coding agents (gate-enforced per task).

---

## [Unreleased]

### Added — New Features (YYYY-MM-DD)

- Feature description with file/function names

### Changed — Modifications (YYYY-MM-DD)

- Change description with affected components

### Fixed — Bug Fixes (YYYY-MM-DD)

- Fix description with issue reference

### Removed — Deprecations (YYYY-MM-DD)

- Removed feature with migration path

### Security — Security Updates (YYYY-MM-DD)

- Security fix with severity level

---

## [X.Y.Z] - YYYY-MM-DD

### Added — Feature Name (YYYY-MM-DD)

- Add `function_name()` in `src/module.py` to handle X
- Add new endpoint `/api/resource` for Y operation

### Changed — Breaking Changes (YYYY-MM-DD)

- Rename `old_function()` to `new_function()` in `src/core.py`
- Update response format for `/api/users` endpoint

### Fixed — Critical Bugs (YYYY-MM-DD)

- Fix race condition in `worker.py` causing data loss
- Fix authentication bypass in `/api/admin` endpoints

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
