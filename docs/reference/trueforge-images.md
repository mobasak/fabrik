# TrueForge Container Images

**Total Images:** 203+ (live-counted 2026-07-19 via the GitHub Packages API — the registry grows; NEVER trust a static count, run `python scripts/container_images.py trueforge list`)
**Registry:** `oci.trueforge.org/tccr/<name>`
**Source:** https://github.com/trueforge-org/containerforge
**Last Updated:** 2026-07-19 (static 120-row catalog dropped — it had drifted 69% under the live registry; use the live commands below)
**Fabrik usage today:** none — no spec/compose/template references a TrueForge image; this doc is the evaluation reference for when one is considered.

## Quick Commands

```bash
cd /opt/fabrik && source .venv/bin/activate

# List all images
python scripts/container_images.py trueforge list

# Check amd64 support
python scripts/container_images.py check-arch oci.trueforge.org/tccr/<name>

# Get image info
python scripts/container_images.py trueforge info <name>

# Pull an image
python scripts/container_images.py pull oci.trueforge.org/tccr/<name>:<tag>
```

## Container Image Discovery Tool

Fabrik includes a powerful discovery tool for searching and evaluating container images across multiple registries (Docker Hub, LinuxServer.io, TrueForge).

**Location:** `scripts/container_images.py`

### Usage Examples

```bash
# Search Docker Hub
python scripts/container_images.py search nginx

# List tags for an image
python scripts/container_images.py tags postgres

# Check amd64 support for any image (Critical for VPS deployment)
python scripts/container_images.py check-arch redis:7-alpine

# Get detailed image info (stars, pulls, architectures)
python scripts/container_images.py info nginx:alpine

# Get recommendations for common use cases (database, monitoring, etc.)
python scripts/container_images.py recommend database

# Pull image to local WSL (with amd64 check)
python scripts/container_images.py pull postgres:16-alpine

# TrueForge specific commands
python scripts/container_images.py trueforge list    # List all TrueForge images
python scripts/container_images.py trueforge tags <name> # List TrueForge tags
python scripts/container_images.py trueforge info <name> # Get TrueForge image info
```

### Key Features
- **Multi-Registry Support**: Docker Hub, ghcr.io, lscr.io, and TrueForge (oci.trueforge.org).
- **Architecture Validation**: Explicitly checks for `amd64` support, which is mandatory for Fabrik VPS deployments.
- **Supply Chain Visibility**: Shows build provenance and architectures for TrueForge images.
- **Smart Recommendations**: Curated list of lightweight, secure, and amd64-compatible images for common infrastructure needs.

## Image catalog — live, not static

The registry moves too fast for a hand-copied table (120 rows here had become 203+ live). Enumerate live instead:

```bash
python scripts/container_images.py trueforge list          # all packages
python scripts/container_images.py trueforge tags <name>    # tags for one
python scripts/container_images.py trueforge info <name>    # metadata + architectures
python scripts/container_images.py check-arch oci.trueforge.org/tccr/<name>   # amd64 gate (fixed 2026-07-19 — it previously tested arm64 and mislabeled it amd64)
```

## Fabrik-Relevant Images (amd64 Ready)

| Image | Fabrik Use Case |
|-------|-----------------|
| **apprise-api** | ✅ Notification service for all Fabrik projects |
| **postgresql** | ✅ Supply-chain secure PostgreSQL for enterprise |
| **nginx** | ✅ Web server with attestations |
| **caddy** | ✅ Alternative web server with auto-HTTPS |
| **duplicati** | ✅ Backup solution (alternative to LinuxServer) |
| **code-server** | ✅ VS Code in browser for remote development |
| **faster-whisper** | ✅ Speech-to-text for transcription projects |
| **it-tools** | ✅ Developer utilities dashboard |
| **webhook** | ✅ Webhook receiver for automation |
| **renovate** | ✅ Dependency update automation |
| **home-assistant** | ✅ Home automation platform |
| **cloudflareddns** | ✅ Dynamic DNS updates for Cloudflare |

## Supply Chain Security Features

All TrueForge images include:
- **GitHub Actions attestations** - Verifiable build provenance
- **SBOM (Software Bill of Materials)** - Complete dependency inventory
- **Reproducible builds** - Consistent, auditable builds
- **Multi-arch support** - Most images support amd64 (and arm64)
