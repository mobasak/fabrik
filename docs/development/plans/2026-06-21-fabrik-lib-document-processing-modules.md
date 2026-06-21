# Plan — fabrik-lib document-processing modules (xlsx-io, docx-io, pdf-extract, ocr, doc-convert, doc-translate)

**Status:** CONVERGED (every step grounded to read evidence; plan carries its proof; `check_convergence.py` green with plan staged)
**Date:** 2026-06-21 · **Author:** Claude Code
**Design spec:** `/opt/fabrik-lib/docs/specs/2026-06-21-document-processing-modules-design.md` (approved)
**Repo for the work:** `/opt/fabrik-lib` (separate repo; `github.com/mobasak/fabrik-lib`). This plan lives in `/opt/fabrik` because that's where `check_convergence.py` inspects.

## Binding rule packs (read via `scripts/select_rules.py`)

Applied as constraints throughout (ACTIVE/relevant-AVAILABLE for Python document libs):
- `core/10-python.md` — `uv` not pip/poetry; Pydantic `BaseSettings` (no import-time `os.getenv`); `list[str]`/`X | None` not `List`/`Optional`; **no `/tmp`** → project `.tmp`.
- `core/45-testing-strategy.md` — `uv run pytest` (not bare `pytest`); structlog/remove, no `print()` in tests.
- `core/40-documentation.md`, `core/15-api-contracts.md` — README per module; the `extract`/`apply` functions are the stable contract (service-layer style).
- `core/66-rag-chunking.md` — `doc-translate` chunking obeys: atomic units intact, 120–1,200-token chunks, boundary overlap (mirrors `mt-router`'s own auto-chunking).
- `core/67-file-api.md` — magic-byte type detection (never trust extension); reject before parse. Storage via `fabrik-lib/storage` not local disk in production.
- Packs N/A to these libraries (no DB/auth/API-server/worker surface): `25-data-postgres`, `35-security-auth`, `30-ops`, `60-watchdog`, `75-workers-jobs`, `90-bootstrap`, `saas/60-saas-ui`, `12-node`, `20-typescript` — see Self-audit.

## Gate model (grounded — names the gate each implementer runs)

`final_gate.py` does **not** reference `/opt/fabrik-lib` (separate repo), and fabrik-lib has no own gate/CI:
```
$ grep -rn 'fabrik-lib' /opt/fabrik/scripts/final_gate.py ; echo "exit=$?"
exit=1          # no match — final_gate does not gate fabrik-lib
$ ls /opt/fabrik-lib/Makefile /opt/fabrik-lib/.github 2>/dev/null || echo "no fabrik-lib CI"
no fabrik-lib CI
```
**Therefore each module's gate = (named test) + (comprehensive static gate):**
`cd /opt/fabrik-lib && uv run pytest <module>/test_<module>.py -q` **AND** `ruff check <module>/ && mypy <module>/`.
The **comprehensive `final_gate.py --json`** (tier-2, **not** `--lean`) is the gate at the **consuming-project integration point** — i.e. when a module is vendored into a fabrik project (e.g. the translation app), that project's `python scripts/final_gate.py --json` must be `"status":"success"`. Each phase names both.

---

## Phase 0 — Shared contract + module skeleton

Establish the `extract`/`apply` contract + `Segment` shape once, as a documented convention + a reusable conformance-test that each format module imports. No shared *code* module (fabrik-lib has none — see Evidence).

### Evidence
- fabrik-lib has **no** shared model/types module; modules compose via plain functions:
```
$ ls -d /opt/fabrik-lib/*/ | grep -iE 'model|types|schema|core|common' || echo NONE
NONE
$ grep -E '^__all__|^from' /opt/fabrik-lib/mt-router/mt_router/__init__.py
from mt_router.router import translate, get_supported_languages
__all__ = ['translate', 'get_supported_languages']
```
- Orchestrator-holds-model precedent: `rag/chunker.py:43` `@dataclass class Chunk` (internal, not exported).
- Module anatomy to copy: `mt-router/` = `mt_router/` (pkg) + `pyproject.toml` + `requirements.txt` + `README.md` + `docs/` (`/opt/fabrik-lib/mt-router/pyproject.toml:1` `[project] name="mt-router"`).

### Steps
1. Write the contract into each module README under `## Contract` (the `extract(src)->[Segment]`, `apply(src,edits)->bytes`, `Segment={id,text,kind,location,meta}` shape).
2. Define a **conformance test pattern** (documented in the design spec + each README, **not** a shared importable module — that would violate vendor-don't-import): three assertions every `test_<module>.py` implements against its own fixture — (a) round-trip `apply(src, {}) == src` byte-for-byte (or normalized), (b) all `Segment.id` unique, (c) `apply(src, {one_id: X})` changes only that segment. Each module copies the pattern; there is no cross-module import.
3. Type-detection convention (per `67-file-api.md`): each module validates magic bytes before parsing and documents rejected-type behavior.

### Gate
Phase 0 produces no code of its own (it defines conventions). Verified by each later module's gate implementing the three conformance assertions — see Phases 1–6 gates.

---

## Phase 1 — `xlsx-io` (xlsx/xls)

### Evidence
- Reuse source — `candle` openpyxl cell read/write (real):
```
$ grep -nE '\.cell\(' /opt/candle/scripts/create_enhanced_tracker.py | head -3
45:        cell = ws.cell(1, col, header)
81:            cell = ws.cell(row, col, value)
130:        ws.cell(row, 5, supplier)
```
- `candle/scripts/create_enhanced_tracker.py:127` shows style preservation (`.font = Font(bold=True, color=...)`).

### Steps
1. `xlsx-io/xlsx_io/__init__.py` exporting `extract`, `apply`.
2. `extract(src)` → `openpyxl.load_workbook`; one `Segment` per non-empty cell: `text=str(cell.value)`, `location=(sheet,row,col)`, `meta={style, is_formula}`. Skip formula cells from `text` (flag in meta) — translating a formula breaks it.
3. `apply(src, edits)` → load, `ws.cell(row,col).value = edits[id]` for matched ids, save to bytes; styles/formulas/validations preserved by openpyxl (do **not** re-create the workbook).
4. `requirements.txt`: `openpyxl`. README with `## Contract`. Row in `/opt/fabrik-lib/README.md` table.

### Gate
`cd /opt/fabrik-lib && uv run pytest xlsx-io/test_xlsx_io.py -q` (round-trip + cell-coordinate reinsert on a fixture .xlsx) · `ruff check xlsx-io/ && mypy xlsx-io/`. Integration: consuming project `final_gate.py --json`.

---

## Phase 2 — `docx-io` (Word)

### Evidence
- Reuse source — `brand-identiy-creator` python-docx run/paragraph (real):
```
$ grep -nE 'add_run|add_paragraph|styles\[' /opt/brand-identiy-creator/src/brand_identity/jobs/templates.py | head -3
168:    style = doc.styles["Normal"]
178:    hp.add_run("{{logo}}  ")
186:        hp2 = hdr.add_paragraph()
```
- **Read:** `brand_identity/jobs/templates.py:178` — `add_run` is the run-text setter `apply` will assign (preserves run formatting; no document rebuild).

### Steps
1. `docx-io/docx_io/__init__.py` → `extract`, `apply`.
2. `extract(src)` walk `document.paragraphs[*].runs[*]` + `tables[*].rows[*].cells[*].paragraphs[*].runs[*]`; one `Segment` per run with non-empty text; `location` = (body/table path + run index), `meta` = run style snapshot.
3. `apply(src, edits)` → set `run.text = edits[id]` for matched ids (preserves run formatting); save to bytes. Do **not** rebuild the document.
4. `requirements.txt`: `python-docx`. README `## Contract`. README-table row.

### Gate
`uv run pytest docx-io/test_docx_io.py -q` (round-trip + run-level reinsert, table cell case) · `ruff check docx-io/ && mypy docx-io/`. Integration: `final_gate.py --json`.

---

## Phase 3 — `ocr` (images + scanned PDFs)

### Evidence
- Tesseract baseline — `archived/file-worker` (real; uses `image_to_string`, **not** `image_to_data` → bbox is net-new):
```
$ grep -nE 'pytesseract|convert_from_path' /opt/archived/file-worker/worker/main.py | head -3
186:    import pytesseract
201:            images = convert_from_path(local_path)
203:                text = pytesseract.image_to_string(img)
```
- Preprocessing — `iterative_image_editor` opencv (real): `flux_kontext_robust.py:152` `cv2.threshold`, `:155` `cv2.findContours`, `:166` `cv2.morphologyEx`.
- Vision fallback pattern — `fabrik-claim-validator/.../pdf_monograph.py:196` `_vision.extract_text_from_image(...)`.
- Cost gate — `fabrik-lib/cost-budget/cost_budget.py:232` `check_caps(...)`, `:101` `record_cost(...)`.
- **Verified the net-new bbox API exists (not assumed):**
```
$ /opt/trade-intelligence/.venv/bin/python -c "import pytesseract; from pytesseract import Output; print(hasattr(pytesseract,'image_to_data'), hasattr(Output,'DICT'))"
True True
```

### Steps
1. `ocr/ocr/__init__.py` → `extract`, `apply`.
2. `extract`: preprocess (deskew/denoise/threshold via cv2) → **`pytesseract.image_to_data(img, output_type=DICT)`** for text **+ per-box bbox + confidence** (net-new vs file-worker). Each box → `Segment(kind="region", meta={bbox,conf})`.
3. Hybrid routing: if mean conf < threshold (value set here at implementation; default 60) → vision-LLM fallback (OpenRouter), **gated by** `cost_budget.check_caps` before the call, `record_cost` after.
4. `apply(src, edits)`: re-render translated text onto the image at each bbox (Pillow draw; font/size inferred from box height). PDFs: `pdf2image.convert_from_path` per page, OCR each.
5. `requirements.txt`: `pytesseract, pdf2image, Pillow, opencv-python-headless, httpx`. README `## Contract` documenting the Tesseract↔vision routing + `TESSERACT_*`/`OPENROUTER_API_KEY` env. README-table row.

### Gate
`uv run pytest ocr/test_ocr.py -q` (bbox extraction on a fixture PNG; vision path mocked) · `ruff check ocr/ && mypy ocr/`. Integration: `final_gate.py --json`.

---

## Phase 4 — `pdf-extract` (native-text PDFs)

### Evidence
- Reuse source — `fabrik-claim-validator` pdfplumber (real; uses `extract_text`/`to_image`, **not** `page.chars` → positional layer is net-new):
```
$ grep -nE 'pdfplumber.open|extract_text|to_image|_vision' /opt/fabrik-claim-validator/src/fabrik_claim_validator/parsers/pdf_monograph.py | head -4
107:            pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
119:                text = (page.extract_text() or "").strip()
178:            img = page.to_image(resolution=200)
196:        return await _vision.extract_text_from_image(image_bytes, prompt, page_num=page_num)
```
- **Read:** `parsers/pdf_monograph.py:107` — `pdfplumber.open`; `extract` layers `page.chars` bboxes on top (net-new; claim-validator is text-only).
- **Verified the net-new API actually exists (not assumed):**
```
$ /opt/fabrik-claim-validator/.venv/bin/python -c "import pdfplumber; print(pdfplumber.__version__, 'chars' in dir(pdfplumber.page.Page), hasattr(pdfplumber.page.Page,'extract_tables'))"
0.11.9 True True
```

### Steps
1. `pdf-extract/pdf_extract/__init__.py` → `extract`, `apply`.
2. `extract`: per page, `page.chars` (char dicts with `x0,top,x1,bottom`) grouped into line/word Segments + `page.extract_tables()` for table regions; `location=(page, bbox)`. **page.chars is documented pdfplumber positional API** (net-new here; claim-validator was text-only).
3. Image-only page detection (claim-validator threshold `<50` chars) → **delegate to `ocr.extract`** (vendored), not re-implemented.
4. `apply(src, edits)`: overlay — white-box the original bbox + draw translated text at coordinates (reportlab/pypdfium2 overlay; exact lib chosen at implementation — see Deferred).
5. `requirements.txt`: `pdfplumber` (+ overlay lib). README `## Contract`. README-table row.

### Gate
`uv run pytest pdf-extract/test_pdf_extract.py -q` (bbox extraction + table region on a fixture PDF) · `ruff check pdf-extract/ && mypy pdf-extract/`. Integration: `final_gate.py --json`.

---

## Phase 5 — `doc-convert` (legacy `.doc`/`.xls`)

### Evidence
- Net-new: **no** legacy-conversion code anywhere in the fleet:
```
$ grep -rliE 'libreoffice|unoconv|soffice|antiword' /opt/*/requirements*.txt /opt/*/src 2>/dev/null | grep -v node_modules || echo "NONE in fleet"
NONE in fleet
```
- **Read:** `.windsurf/rules/core/10-python.md:138` (`TEMP_DIR = PROJECT_ROOT / ".tmp"`) — Phase 5 writes conversions to project `.tmp`, never `/tmp` (binding `10-python` rule).

### Steps
1. `doc-convert/doc_convert/__init__.py` → `to_docx(src)`/`to_xlsx(src)` via `soffice --headless --convert-to`, writing to project `.tmp` (per `10-python.md` — **never `/tmp`**), returning bytes; then caller routes to `docx-io`/`xlsx-io`.
2. README documents the **system** LibreOffice dependency + the in-image-vs-sidecar decision (Deferred). `requirements.txt` notes the system pkg.

### Gate
`uv run pytest doc-convert/test_doc_convert.py -q` (skipif `soffice` absent; conversion of a fixture `.doc`) · `ruff check doc-convert/ && mypy doc-convert/`. Integration: `final_gate.py --json`.

---

## Phase 6 — `doc-translate` (orchestrator)

### Evidence
- Translation engine — `mt-router` real signature:
```
$ sed -n '209,215p' /opt/fabrik-lib/mt-router/mt_router/router.py
def translate(
    text: str,
    target_lang: str,
    source_lang: str | None = None,
    context: dict | None = None,
    glossary: dict | None = None,
) -> TranslationResult:
```
- Storage — `storage/b2_backend.py:53` `save(key, content)->str`, `:67` `read(key)->str`, `:82` `exists(key)->bool`.
- Orchestrator-holds-model precedent — `rag/chunker.py:43` `@dataclass class Chunk`.

### Steps
1. `doc-translate/` (pip-installable, has `pyproject.toml` like mt-router). Internal `@dataclass Document/Segment` model (rag pattern; not exported).
2. `translate_document(src, target_lang, ...)`: magic-byte detect → dispatch to `xlsx-io`/`docx-io`/`pdf-extract`/`ocr` (+ `doc-convert` for legacy) `extract`; for each Segment call `mt_router.translate(seg.text, target_lang, context=..., glossary=...)`; **chunking handled by mt-router** (auto; obey `66-rag-chunking` for any pre-split); `apply` the edits back.
3. GUI hook: expose the `[Segment]` list so callers can override `text` before `apply` (in-place editing).
4. Persist source + output via `fabrik-lib/storage`; gate any vision OCR spend via `cost-budget` (already in `ocr`).
5. `pyproject.toml` deps + vendored modules 1–5; README `## Architecture`/`## Usage`/`## Contract`. README-table row.

### Gate
`uv run pytest doc-translate/test_doc_translate.py -q` (end-to-end on a fixture xlsx: extract→translate(mock mt-router)→apply round-trips structure) · `ruff check doc-translate/ && mypy doc-translate/`. Integration: the translation app's `final_gate.py --json`.

---

## Phase 7 — fabrik-lib wiring

### Evidence
- README table row format (real):
```
$ grep -nE '^\| `(mt-router|storage)/`' /opt/fabrik-lib/README.md
32:| `mt-router/` | Multi-provider translation routing (DeepL, Azure, OpenRouter, SiliconFlow) | Active |
36:| `storage/` | Unified file storage (B2 + Supabase backends, same save/read/exists API, URI-routed) | Active |
```
- **Read:** `/opt/fabrik-lib/README.md:32` — the `| \`name/\` | desc | Active |` row format to mirror for the 6 new module rows.

### Steps
1. Add 6 rows to `/opt/fabrik-lib/README.md` module table + the capability matrix, mirroring the existing format.
2. Link the design spec from the README. Update the "which-module-do-I-need" guidance for document tasks.

### Gate
`grep -c '`xlsx-io/`\|`doc-translate/`' /opt/fabrik-lib/README.md` (rows present) · markdown renders. No code gate.

---

## Self-audit (convergence floor)

Re-checked every step against the embedded Evidence; each item below is closed:

| Claim / risk | Status | Grounding |
|---|---|---|
| Each reuse source actually exists & does what I say | ✓ | path:line + command output in every phase's `### Evidence` |
| `page.chars` / `image_to_data` are net-new (not in the reuse source) | ✓ | claim-validator uses `extract_text` (Phase 4 EV); file-worker uses `image_to_string` (Phase 3 EV) — both confirmed, so bbox layers are correctly flagged net-new |
| No shared-model module invented | ✓ | Phase 0 EV: fabrik-lib has none; mt-router exports functions |
| Gate names are real (not a fabricated final_gate-on-fabrik-lib) | ✓ | Gate-model EV: `grep fabrik-lib final_gate.py` → exit 1; per-module `uv run pytest`+ruff+mypy, final_gate at integration |
| `doc-convert` is genuinely net-new | ✓ | Phase 5 EV: `grep libreoffice…` → NONE in fleet |
| Binding packs identified via the tool, not guessed | ✓ | `select_rules.py` run; constraints applied (uv, Pydantic, `list[X]`, `.tmp`, `uv run pytest`, chunking) |
| Packs marked N/A are justified | ✓ | DB/auth/API-server/worker/UI packs don't apply to vendorable parsing libs (no such surface) |
| mt-router signature used correctly | ✓ | Phase 6 EV: real `translate(text, target_lang, source_lang, context, glossary)` |
| Net-new APIs (`page.chars`, `image_to_data`) actually exist | ✓ | introspected installed libs — Phase 4 EV (pdfplumber 0.11.9 → True True), Phase 3 EV (pytesseract → True True); not assumed |

**Known deferred decisions** (explicitly out of this plan, into per-module implementation): OCR confidence threshold (default 60 stated); PDF `apply` overlay library (reportlab vs pypdfium2); `doc-convert` LibreOffice in-image vs sidecar; per-module test fixture files. These are choices, not unknowns — each is bounded with a stated default/direction.

**Unhandled edge cases surfaced & assigned:** formula cells in xlsx (Phase 1 step 2 flags, never translates); image-only PDF pages (Phase 4 step 3 delegates to `ocr`); legacy `.doc` → routed through `doc-convert` before `docx-io`; vision-spend overrun (Phase 3 step 3 gated by `cost-budget`); **encrypted/password-protected files** → reject at the magic-byte/validation step (per `67-file-api.md`) with a clear error, each module's `extract` (no silent failure); **very large files (OOM risk on the shared VPS)** → each module enforces a max-bytes guard before loading (per `67-file-api.md` streaming/limits), value set per module at implementation.

## Evidence index

All evidence is embedded **per phase** under each `### Evidence` (path:line + a fenced command-output block): Phase 0 (no-shared-model, mt-router `__all__`), Phase 1 (candle `.cell`), Phase 2 (brand-identity `add_run`), Phase 3 (file-worker `pytesseract` + opencv + cost-budget), Phase 4 (claim-validator `pdfplumber`), Phase 5 (legacy-conversion gap), Phase 6 (mt-router `translate` + storage), Phase 7 (README row format). Gate-model evidence under "Gate model".
