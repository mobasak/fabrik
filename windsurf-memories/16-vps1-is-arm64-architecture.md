# VPS1 is x86_64 (amd64) architecture

**Tags:** #vps #amd64 #architecture #deployment

VPS1 uses x86_64 (amd64) architecture — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM.
Verified via SSH on 2026-04-05 (`uname -m` → x86_64, `dpkg --print-architecture` → amd64).

**Implications:**
- All Docker images MUST support amd64 (`platform: linux/amd64` in compose.yaml)
- Use `python scripts/container_images.py check-arch <image:tag>` to verify
- Alpine images should be avoided (glibc compatibility, missing pre-built wheels)

**Verification command:**
```bash
python scripts/container_images.py check-arch <image:tag>
```

**Base images that work:**
- `python:3.12-slim-bookworm` ✅
- `node:22-bookworm-slim` ✅
- `debian:bookworm-slim` ✅

**Avoid:** Alpine-based images (glibc compatibility issues, missing pre-built wheels)
