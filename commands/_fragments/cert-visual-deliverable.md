- **⚠️ VISUAL-DELIVERABLE QA — if a journey's deliverable IS a visual artifact, the proof is EYES ON THE
  RENDERED PIXELS.** Structural checks (HTTP 200, the right hexes) prove the pipeline WIRED the right inputs, not that the result looks right.
  For EVERY image/PDF/SVG/favicon/video-frame deliverable: RENDER it (rasterize PDFs + SVGs first), then
  INSPECT the pixels with vision (`fabrik-gui` subagents have vision; fan them across artifact classes,
  adjudicate yourself) against the contract/brand.
  A deliverable nobody looked at is an UNCHECKED row, not a PASS.
