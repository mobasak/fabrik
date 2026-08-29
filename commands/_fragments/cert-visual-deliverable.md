- **⚠️ VISUAL-DELIVERABLE QA — if a journey's deliverable IS a visual artifact, the proof is EYES ON THE
  RENDERED PIXELS.** Structural checks (file exists, format header, HTTP 200, the right hexes in the
  JSON/CSS, the source SVG's bytes present inside the composed output) prove the pipeline WIRED the right
  inputs — they do NOT prove the rendered result looks right (live defect: every structural check green
  while a logo could be clipped, card text overflowing the bleed, contrast broken, fonts silently falling
  back — "content-verified is NOT visually QA'd"). For EVERY image/PDF/SVG/favicon/video-frame deliverable:
  RENDER it (rasterize PDFs + SVGs first), then INSPECT the pixels with vision (`fabrik-gui` subagents have
  vision; fan them across artifact classes, adjudicate yourself) against the contract/brand: logo
  integrity/clipping, palette fidelity, typography actually rendering as the specified face (not a
  fallback), layout defects, contrast on every surface. A deliverable nobody looked at is an UNCHECKED row,
  not a PASS.
