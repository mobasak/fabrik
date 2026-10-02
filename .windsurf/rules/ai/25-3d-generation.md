---
activation: glob
globs: ["**/3d/**", "**/3d-gen/**", "**/3d-generation/**", "**/mesh-gen/**", "**/text-to-3d/**", "**/asset-gen/**", "**/glb/**", "**/usdz/**"]
description: 3D asset generation — automated zero-edit mesh pipeline (GLB/FBX/OBJ/STL/3MF/USDZ). Provider routing by asset type (Meshy, Tripo, Rodin, self-hosted TRELLIS), a mandatory headless validation gate with a Claude look at renders, re-roll caps, API before self-host, licence traps named. NOT CAD — simple parametric parts go to Claude-written CAD code or Zoo.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building automated 3D-asset-generation pipelines.
     GOAL: Zero-edit assets only — route by asset type, validate headlessly, cap re-rolls, default to a commercial API over
     self-hosting, never default to weights a licence restricts.
     AGENT USAGE: Pick the provider per § 1 by asset type; run the § 3 gate; cap re-rolls at 3 (§ 4); default to the Meshy or
     Tripo API, self-host only on proven volume (§ 5). Model choice across categories is ai/00-ai-model-selection.md; record
     a project's choice and the rejected alternative in project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as
     ai/00's selection workflow says. See `20-vision.md` (sibling media generation and image understanding) and
     `core/76-gpu-workers.md` (the self-host decision). -->

# 3D Generation Pipeline Rules

Last content verification: 2026-10-02

> **Purpose:** rules for any project that calls AI 3D-generation providers in an automated, no-human-in-the-loop
> pipeline. **Scope:** mesh and asset generation only. NOT CAD.
> **Evidence:** the routing comes from `docs/reference/research/Zero-Edit 3D API Evaluation.md`; where this pack and the
> brief differ, this pack's 2026-10-02 re-verification wins. Cost and yield figures are starting assumptions to replace
> with measured values, and this category changes monthly — confirm a provider's current model and price on its own docs
> page before integrating.

---

## 0. Hard boundaries (never violate)

- **No human edits exist in this pipeline.** Every asset ships as generated or is rejected; there is no "fix it in
  Blender" fallback. The validation gate (§ 3) is mandatory — it is the human eye, replaced by code.
- **Mesh generation never touches CAD or manufacturing.** A generated mesh has no parametric history, dimensions or
  tolerances. A dimensioned part routes to a CAD path instead. A simple part — one body built from sketches, extrudes
  and revolves with holes and fillets — goes to Claude writing parametric CAD code (CadQuery, build123d or OpenSCAD)
  through `claude -p`, called via a vendored `llm-dispatch` as ai/00 requires, then executed and checked like any
  generated code. Anything complex — sweeps, lofts, threads, patterns, several parts, chained dimensions — goes to Zoo's
  Text-to-CAD API (STEP and glTF out; not in the vendor-access catalog, so a key to add). Every model, Claude included,
  fails often on complex topology, and nothing tolerance-critical ships without an engineer.
- **No new GPU pipeline infrastructure before a payable artifact exists.** Self-hosting is an optimization for proven
  volume, not a starting point.

---

## 1. Provider routing (by asset type)

Route per asset type; never use one provider for everything. Keep each provider's model id in an env value
(`core/76-gpu-workers.md`), use the vendor's own alias where it has one (Meshy's `latest`), and set the quality tier
explicitly — Rodin, for one, falls back to an older generation when the tier is omitted.

| Asset type | Primary | Fallback | Why |
| :-- | :-- | :-- | :-- |
| Printable STL / 3MF | **Meshy** | Hi3D (formerly Hitem3D) | A print pipeline in the API: free printability analysis, a repair step that returns watertight output, multi-colour 3MF |
| Game asset (rig-ready) | **Tripo** | Sloyd (T-pose out, rig elsewhere) | Native quad Smart Mesh and auto-rig through the API |
| E-commerce / AR GLB | **Rodin** | Meshy | Photoreal PBR — 2K by default, 4K to 12K from higher tiers and its add-on |
| Hard-surface hero prop | **Rodin** | TRELLIS (hosted) | PBR plus Bang! part segmentation |
| Arch / real-estate viz | **TRELLIS** (hosted: fal or 3D AI Studio) | Rodin | O-Voxel handles complex, non-manifold topology |
| Bulk / no vendor lock-in | **TRELLIS** (hosted: fal or 3D AI Studio) | Step1X-3D (self-host, Apache-2.0, only per § 5) | Open weights you can take in-house later — read the licence trap first |

**Reachability.** Check `/opt/fabrik/docs/reference/kilo/AI_VENDOR_ACCESS.md` before designing around a provider. fal
and WaveSpeed, whose keys the fleet holds, host Rodin, Meshy, Tripo, Hi3D and TRELLIS today — but a hosted route exposes
only the generate call. Meshy's printability, repair and multi-colour steps, Rodin's Bang! and named tiers, and Tripo's
auto-rig need the vendor's own key; Rodin's own API is on its Business plan only (about $120 a month) and charges at
submission. The reach map's "via Higgsfield" route is app-only: Higgsfield's developer API has no 3D.

**Aggregator fallback:** 3D AI Studio's pay-as-you-go API reaches Tripo, Hi3D, TRELLIS and Hunyuan 3D from one key (no
Meshy or Rodin endpoint) — use it to avoid lock-in and to A/B those engines without separate subscriptions.

**Licence trap — open weights are not commercial weights.** TRELLIS's code and weights are MIT, but its documented
install pulls in NVIDIA's nvdiffrast, which is licensed for non-commercial use only — commercial self-hosting needs that
dependency replaced or licensed. Tencent's Hunyuan3D community licence does not apply in the EU, UK or South Korea,
requires Tencent's permission above 1 million monthly active users, and bans training other models on its outputs; it is
not a Fabrik default. Stability's SF3D and SPAR3D are free only below USD 1M annual revenue.

---

## 2. Hard exclusions (never call in an automated pipeline)

- **CSM (Common Sense Machines)** — acquired by Google; its platform and every API shut down on 2026-01-05.
- **Luma Genie** — sunset on 2026-01-01.
- **Hero characters via pure AI** — no zero-edit path exists. Skip them, or flag them to a separate human-QA queue (for
  example Kaedim, a hybrid service with no public API price). **Never auto-ship a generated hero character.**

---

## 3. Validation gate (MANDATORY — runs before any asset enters the pipeline)

Every generation passes an automated, asset-type-specific gate. Fail = reject + re-roll. This replaces the missing human
reviewer.

### 3.1 Printable STL / 3MF
- [ ] Meshy output has been through its analyze, repair and (for colour) multi-colour steps before the gate
- [ ] Watertight volume — the pass/fail: trimesh `is_volume` (every edge shared by two faces, consistent winding,
      outward normals)
- [ ] Slicer smoke test: PrusaSlicer, Bambu Studio or CuraEngine on the command line exits 0 and writes G-code, inside a
      timeout (Bambu Studio's CLI has none of its own); the three report repairs differently, so the slicer never decides
      watertightness
- [ ] Min wall thickness ≥ the printer profile's minimum, measured with Blender's 3D Print Toolbox extension under
      `blender -b`
- Fail any → **reject**

### 3.2 Game asset
- [ ] Poly budget within ceiling (default: ≤10k tris prop, ≤3k background)
- [ ] Full PBR map set present (albedo, normal, roughness, metallic)
- [ ] No baked lighting or shadow in the albedo
- [ ] (If rigged) skeleton detected (Tripo's rig check, free) + skin weights bind without capturing adjacent geometry
      (judged on a posed render, as in the implementation note)
- Fail any → **reject**

### 3.3 E-commerce / AR GLB
- [ ] Within Google Scene Viewer's guidance: under 10 MB, 100,000 triangles at most (30,000-50,000 ideal), 2048 px
      textures, +Y up, 1 unit = 1 m. Apple publishes no file-size limit; its guidance is about 100K polygons and one
      2048 px texture set.
- [ ] Zero floating artifacts ("floaters")
- [ ] Full PBR maps, non-overlapping UV atlas
- [ ] USDZ for Apple viewers converted headlessly (guc, or Blender writing a `.usdz` file)
- Fail any → **reject**

### 3.4 Hard-surface prop
- [ ] Multi-part prompts produce **separable** geometry, not a merged single mesh
- [ ] PBR stack present, mapped to a clean UV atlas
- Fail any → **reject**

> **Implementation note:** gates run headless — the Khronos glTF-Validator CLI for format and references (it does not
> check watertightness or polycount), trimesh for geometry, a slicer CLI for printables, and `blender -b -P` for scripted
> checks and turntable or posed renders. Run the AGPL slicers as separate processes. The checks code cannot see — baked
> lighting, the wrong object, a visible floater, weights dragging nearby geometry — go to Claude through `claude -p`
> (`20-vision.md`'s image-understanding default): `run_agentic` with the Read tool on the render directory, one call per
> asset with 20 renders or fewer, a pass/fail per named defect, and one control question only the renders can answer
> (name the object, count the views) so that a blind answer fails. A generation that cannot be validated automatically is
> a **fail**, never a pass-by-default.

---

## 4. Re-roll & failure handling

- **Re-roll cap: 3 attempts** per job. After the third failure → dead-letter queue, do not retry. No infinite loops burning credits
  or GPU.
- Dead-lettered jobs are logged with the failing gate(s) for prompt tuning.
- Never silently ship a job that exhausted its re-rolls.

---

## 5. Cost & infra discipline

- **Default to a commercial API (Meshy / Tripo).** Zero infra, credit-priced per task; Meshy refunds failed tasks.
  Published price tables can lag the newest models — Tripo's current Smart Mesh model costs about $1.00-1.30 a
  generation, several times the table's older models — so measure cost per usable asset (§ 6), never budget from a
  headline.
- **Do NOT self-host as a starting move.** Self-hosted marginal cost looks near-free on paper but ignores GPU cold
  start, idle time, provisioning billing and your maintenance hours. TRELLIS needs a 24 GB GPU. Treat any "$X/month
  self-host" estimate as a floor missing operational overhead, not a build trigger.
- **Self-hosting trigger:** migrate to TRELLIS or another open model on a rented GPU (`core/76-gpu-workers.md`) **only**
  when (a) a use case has proven paying revenue AND (b) measured volume makes API cost the actual bottleneck — and only
  after the licence trap in § 1 is cleared. Extract the self-host wrapper from working API code, not in advance.

---

## 6. Measurement (replace the assumptions)

These defaults are **guesses to overwrite with logged reality**:

| Metric | Default assumption | Replace with |
| :-- | :-- | :-- |
| Zero-edit yield (blended) | 70% | Measured per provider × asset type |
| Re-roll cap | 3 | Tuned from dead-letter rate |
| Cost per usable asset | the provider's per-task credit price | Measured (incl. re-rolls) |

Log per generation: provider, model, asset type, gate result, attempts, credit or GPU cost. Yield and cost rules above
are only as good as this telemetry.

---

## 7. Per-project conformance

Before this ruleset is applied in a project:
- Confirm the project is registered in the hub's `/opt/fabrik/data/projects.yaml` (the master registry, generated by the
  hub's project sync — don't build for a phantom target).
- Read the project's `.windsurf/rules/` (`core/` + project-type folder) and make this pipeline conform to the same
  constraints the executors plan against.
- This is a glob-activated pack in the `ai/` ruleset (synced from `/opt/fabrik` via `.windsurf/rules`), distinct from
  the owned governance files (`AGENTS.md` / `CLAUDE.md` / `AGENTS-compact.md` / `.windsurfrules`) — never rename it to
  any of those.
