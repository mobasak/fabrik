---
activation: glob
globs: ["**/3d/**", "**/3d-gen/**", "**/3d-generation/**", "**/mesh-gen/**", "**/text-to-3d/**", "**/asset-gen/**", "**/glb/**", "**/usdz/**"]
description: 3D asset generation — automated zero-edit mesh/asset pipeline (GLB/FBX/OBJ/STL/USDZ). Provider routing by asset type (Meshy/Tripo/Rodin/TRELLIS 2), mandatory headless validation gate, re-roll caps, API-before-self-host discipline. NOT CAD. Backed by docs/reference/research-files/Zero-Edit 3D API Evaluation.md.
trigger: glob
---
<!-- CONSUMER: Coding agents building automated 3D-asset-generation pipelines + Traycer (tech-plan)
     GOAL: Zero-edit assets only — route by asset type, validate headlessly, cap re-rolls, default to commercial API over self-host.
     TRAYCER USAGE: Context File for any 3D-mesh / asset-generation ticket. Provider-routing + validation-gate sections shape the tech-plan.
     AGENT USAGE: Pick provider per §1 by asset type; run the mandatory §3 validation gate; cap re-rolls at 3 (§4); default to Meshy/Tripo API, self-host only on proven volume (§5). See `20-vision.md` (sibling media-gen) + `core/76-gpu-workers.md` (self-host decision). -->

# 3D Generation Pipeline Rules

> **Purpose:** Reference ruleset for any project that calls AI 3D-generation
> providers in an automated, no-human-in-the-loop pipeline.
> **Scope:** Mesh/asset generation only (GLB/FBX/OBJ/STL/USDZ). NOT CAD.
> **Status of numbers:** Provider picks are evidence-backed; cost/yield figures
> are **starting assumptions to be replaced with measured values**. Verify any
> single provider's current model + pricing from its own docs page before
> integrating — this category changes monthly.

---

## 0. Hard boundaries (never violate)

- **No human edits exist in this pipeline.** Every asset is shipped as-generated
  or rejected. There is no "fix it in Blender" fallback. Therefore the
  validation gate (§3) is mandatory — it is the human eye, replaced by code.
- **Mesh-gen never touches CAD / manufacturing.** Generated meshes are surface
  B-Reps with no parametric history, dimensions, or tolerances. Any
  machinery / mechanical-part / dimensioned-drawing requirement routes to a
  separate Text-to-CAD path (Zoo Text-to-CAD), never to a mesh provider.
- **No new GPU pipeline infrastructure before a payable artifact exists.**
  Self-hosting is an optimization for proven volume, not a starting point.

---

## 1. Provider routing (by asset type)

Route per asset type. Never use one provider for everything.

| Asset type | Primary | Fallback | Why |
| :-- | :-- | :-- | :-- |
| Printable STL / 3MF | **Meshy** | Hitem3D | ~97% slicer pass, native multi-color 3MF, Bambu-validated |
| Game asset (rig-ready) | **Tripo** | Sloyd (if in template lib) | Quad "Smart Mesh" + working auto-rig — only one clearing rigging |
| E-commerce / AR GLB | **Rodin** | Meshy | 4K PBR photoreal, pay-on-download |
| Hard-surface hero prop | **Rodin** | TRELLIS 2 | 4K PBR + "Bang!" multi-part segmentation |
| Arch / real-estate viz | **TRELLIS 2** (self-host) | 3D AI Studio (API) | O-Voxel handles complex/non-manifold topology |
| Bulk / no vendor lock-in | **TRELLIS 2** (self-host) | Hunyuan3D 2.1 | MIT license, fully scriptable |

**Aggregator fallback for all of the above:** 3D AI Studio API (~$15/mo) routes
to multiple underlying models from one key — use to avoid lock-in and to A/B
engines without separate subscriptions.

---

## 2. Hard exclusions (never call in an automated pipeline)

- **CSM (Common Sense Machines)** — acquired by Google (Jan 2026); deprecation /
  SLA risk for a recurring-revenue pipeline.
- **Stability SF3D** — outputs albedo-only with baked-in lighting; unusable in
  engines/AR (baked shadows conflict with dynamic lighting).
- **Luma (Genie)** — NeRF/Splat → coarse noisy meshes; demands retopology.
- **Hero characters via pure AI** — no zero-edit path exists in 2026. Either skip,
  or flag to a separate human-QA queue (e.g. Kaedim). **Never auto-ship a
  generated hero character.**

---

## 3. Validation gate (MANDATORY — runs before any asset enters the pipeline)

Every generation passes an automated, asset-type-specific gate. Fail = reject +
re-roll. This replaces the missing human reviewer.

### 3.1 Printable STL / 3MF
- [ ] Watertight / manifold (zero non-manifold edges, zero holes, zero inverted normals)
- [ ] Slicer dry-run passes with **no auto-repair warnings** (Bambu Studio / Cura headless)
- [ ] Min wall thickness ≥ extrusion tolerance
- Fail any → **reject**

### 3.2 Game asset
- [ ] Poly budget within ceiling (default: ≤10k tris prop, ≤3k background)
- [ ] Full PBR map set present (albedo, normal, roughness, metallic)
- [ ] No baked lighting/shadow in albedo
- [ ] (If rigged) skeleton detected + skin weights bind without capturing adjacent geo
- Fail any → **reject**

### 3.3 E-commerce / AR GLB
- [ ] File size < 10 MB
- [ ] Zero floating artifacts ("floaters")
- [ ] Correct scale + orientation for target AR viewer (Y-up / Z-up)
- [ ] Full PBR maps, non-overlapping UV atlas
- Fail any → **reject**

### 3.4 Hard-surface prop
- [ ] Multi-part prompts produce **separable** geometry, not a merged single mesh
- [ ] PBR stack present, mapped to clean UV atlas
- Fail any → **reject**

> **Implementation note:** gates run headless (slicer CLI, glTF-validator,
> mesh-analysis lib). A generation that cannot be validated automatically is
> treated as a **fail**, never a pass-by-default.

---

## 4. Re-roll & failure handling

- **Re-roll cap: 3 attempts** per job. After 3 fails → dead-letter queue, do not
  retry. No infinite loops burning credits/GPU.
- Dead-lettered jobs are logged with the failing gate(s) for prompt tuning.
- Never silently ship a job that exhausted its re-rolls.

---

## 5. Cost & infra discipline

- **Default to commercial API (Meshy / Tripo).** Zero infra, predictable cost.
- **Do NOT self-host as a starting move.** Self-hosted marginal cost looks near-free
  on paper but ignores GPU cold-start, idle, provisioning billing, and your
  maintenance hours. Treat any "$X/month self-host" estimate as a floor missing
  operational overhead, not a build trigger.
- **Self-hosting trigger:** migrate to TRELLIS 2 / Hunyuan on rented GPU **only**
  when (a) a use case has proven paying revenue AND (b) measured volume makes API
  cost the actual bottleneck. Extract the self-host wrapper from working API code,
  not in advance.

---

## 6. Measurement (replace the assumptions)

These defaults are **guesses to overwrite with logged reality**:

| Metric | Default assumption | Replace with |
| :-- | :-- | :-- |
| Zero-edit yield (blended) | 70% | Measured per provider × asset type |
| Re-roll cap | 3 | Tuned from dead-letter rate |
| Cost per usable asset | per §1 report figures | Measured (incl. re-rolls) |

Log per generation: provider, asset type, gate result, attempts, credit/GPU cost.
Yield and cost rules above are only as good as this telemetry.

---

## 7. Per-project conformance

Before this ruleset is applied in a project:
- Confirm the project is registered in `data/projects.yaml` (the master registry — don't build for a phantom target).
- Read the project's `.windsurf/rules/` (`core/` + project-type folder) and make
  this pipeline conform to the same constraints the executors plan against.
- This is a glob-activated pack in the `ai/` ruleset (synced from `/opt/fabrik`
  via `.windsurf/rules`), distinct from the owned governance files
  (`AGENTS.md` / `CLAUDE.md` / `AGENTS-compact.md` / `.windsurfrules`) — never
  rename it to any of those.

---

*Last reviewed: 2026-06-25. 3D-gen versioning moves monthly — re-verify provider
models/pricing from official docs at integration time.*
