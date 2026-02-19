# VPS1 is ARM64 architecture

**Tags:** #vps #arm64 #architecture #deployment

VPS1 uses ARM64 (aarch64) architecture.

**Implications:**
- All Docker images MUST support ARM64
- Use `python scripts/container_images.py check-arch <image:tag>` to verify
- Prefer multi-arch images or ARM64-specific builds
- Alpine images may have compatibility issues on ARM64

**Verification command:**
```bash
python scripts/container_images.py check-arch <image:tag>
```

**Base images that work:**
- `python:3.12-slim-bookworm` ✅
- `node:22-bookworm-slim` ✅
- `debian:bookworm-slim` ✅
- `oci.trueforge.org/tccr/ubuntu` ✅

**Avoid:** Alpine-based images on ARM64 (glibc compatibility issues)
