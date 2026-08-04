#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/kilo/TASK_SUBAGENT_SELECTION.md (if a winner is promoted) | none else
"""Bake-off: which cheap OpenRouter VISION model can stand in for the `claude -p haiku`
primary in `describe` — image -> {alt_text, seo_slug} as JSON, accurate (not generic), fast, cheap.

WHY: the haiku primary cannot run in a deployed/headless container (no Claude subscription) and
is ~17s/image, too slow for large batches. This measures the metered OpenRouter fallbacks on the
four axes that actually decide it:

  1. JSON validity  — does it honour a json_schema response_format every time? (a fallback that
                      needs hand-parsing is not a fallback)
  2. ACCURACY       — does the alt-text describe THIS image (judged by a vision model that sees
                      the same image), not a plausible-sounding generic product sentence
  3. SPECIFICITY    — the "not generic" axis, scored two ways: the judge's 0-5, plus a mechanical
                      generic-phrase detector (no judge can be the only witness)
  4. latency + cost — measured per call from real usage, not from a price table

Usage:
  python microbench_vision_describe.py --dry-run              # show the plan, spend nothing
  python microbench_vision_describe.py --limit 6              # small real run
  python microbench_vision_describe.py --models a,b --judge google/gemini-3-flash-preview

Secrets: OPENROUTER_API_KEY from the env (or /opt/fabrik/.env). Never logged.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FABRIK_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_IMAGE_ROOT = Path("/opt/iterative_image_editor")

# Cheap + fast + vision + structured-output candidates (from the live catalog: has_vision=1,
# via_openrouter=1, active, input <= $0.25/M). Prices are read back from the API response, not
# trusted from here — this list only decides WHO runs.
DEFAULT_MODELS = [
    "google/gemini-2.5-flash-lite",
    "qwen/qwen3.5-flash-02-23",
    "amazon/nova-lite-v1",
    "bytedance-seed/seed-1.6-flash",
    "mistralai/mistral-small-3.2-24b-instruct",
    "openai/gpt-5-nano",
    "google/gemini-3.1-flash-lite",
]
DEFAULT_JUDGE = "google/gemini-3-flash-preview"

# The op's real contract (EN-only per the current describe shape).
SCHEMA = {
    "type": "object",
    "properties": {
        "alt_text": {"type": "string"},
        "seo_slug": {"type": "string"},
    },
    "required": ["alt_text", "seo_slug"],
    "additionalProperties": False,
}

PROMPT = (
    "You write accessibility + SEO metadata for e-commerce product images.\n"
    "Return JSON with exactly two fields:\n"
    '  "alt_text": a WCAG 1.1.1 equivalent-purpose alt string, <=125 chars, ENGLISH. Describe THIS '
    "specific image: name the actual object, its material/finish, colour, and notable form. "
    'Never start with "image of"/"photo of". Never write a generic filler sentence.\n'
    '  "seo_slug": a kebab-case filename stem, <=60 chars, lowercase a-z0-9 and hyphens only, '
    "descriptive of the product (no stopwords, no dates, no camera jargon).\n"
    "Be concrete and specific. If you cannot identify the object, describe precisely what is visible."
)

# Mechanical "generic" detector — the independent witness to the judge's specificity score.
GENERIC_PATTERNS = [
    r"\bimage of\b", r"\bphoto(graph)? of\b", r"\bpicture of\b",
    r"\ba product\b", r"\bthe product\b", r"\ban object\b", r"\ban item\b",
    r"\bon a (plain|white|neutral) background\b",
    r"\bproduct (shot|photo|image)\b", r"\bclose[- ]?up (shot|view)\b",
    r"\bsome kind of\b", r"\bappears to be\b", r"\bvarious\b",
]


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        env = FABRIK_ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set — cannot run (see /opt/fabrik/.env)")
    return key


def data_uri(path: Path, max_px: int = 1024) -> str:
    """Downscale then inline. Vision cost/latency scale with resolution, so a fair bake-off
    sends what a production `describe` would send, not a 1.7MB original."""
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            raw = buf.getvalue()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()
    except Exception:  # noqa: BLE001 — fall back to the original bytes
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _post(body: dict, key: str, timeout: float = 120.0) -> tuple[dict | None, str | None]:
    payload = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        import httpx  # noqa: PLC0415

        r = httpx.post(OPENROUTER_URL, content=payload, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:180]}"
        return r.json(), None
    except ImportError:
        import urllib.error  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        req = urllib.request.Request(OPENROUTER_URL, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return json.loads(resp.read().decode()), None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}: {e.read()[:180]!r}"
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def _usd(resp: dict) -> float:
    """Real cost for THIS call. OpenRouter returns it directly when available; otherwise 0.0
    (never guess from a stale price table — that is how a bake-off lies about cost)."""
    usage = resp.get("usage") or {}
    for k in ("cost", "total_cost"):
        if isinstance(usage.get(k), (int, float)):
            return float(usage[k])
    return 0.0


def _extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.I | re.M).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except ValueError:
                return None
    return None


#: The PRIMARY this bake-off is finding a stand-in for. `claude -p` is agentic: it reads the
#: image off disk itself (no data-uri). Billed to the Max subscription, so it has no per-call
#: USD — its cost axis is QUOTA + the ~17s/image latency that motivates a fallback at all.
HAIKU_ID = "claude-code/haiku"


def _describe_haiku(image: Path) -> dict:
    import subprocess  # noqa: PLC0415

    prompt = (
        f"Read the image at {image} and return ONLY a JSON object (no prose, no fences) with "
        f'exactly these keys: "alt_text", "seo_slug".\n\n{PROMPT}'
    )
    out = {"model": HAIKU_ID, "image": image.name, "latency_s": 0.0, "usd": 0.0,
           "json_ok": False, "alt_text": "", "seo_slug": "", "error": None}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603
            [os.path.expanduser("~/.local/bin/claude"), "-p", prompt,
             "--model", "haiku", "--allowed-tools", "Read"],
            capture_output=True, text=True, timeout=180, cwd=str(image.parent),
        )
    except Exception as e:  # noqa: BLE001
        out["latency_s"] = round(time.monotonic() - t0, 2)
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    out["latency_s"] = round(time.monotonic() - t0, 2)
    if proc.returncode != 0:
        out["error"] = f"claude -p rc={proc.returncode}: {proc.stderr[:160]}"
        return out
    obj = _extract_json(proc.stdout)
    if obj and isinstance(obj.get("alt_text"), str) and isinstance(obj.get("seo_slug"), str):
        out.update(json_ok=True, alt_text=obj["alt_text"].strip(), seo_slug=obj["seo_slug"].strip())
    else:
        out["error"] = f"unparseable: {proc.stdout[:120]}"
    return out


def describe_once(model: str, image: Path, key: str) -> dict:
    if model == HAIKU_ID:
        return _describe_haiku(image)
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri(image)}},
                ],
            }
        ],
        # 1500, not 400: REASONING models (gpt-5-nano) spend completion tokens thinking before
        # emitting content. A tight cap makes them finish_reason="length" with content=None —
        # which looks exactly like "can't do JSON" but is the harness starving them. Measured:
        # gpt-5-nano burned 384/400 on reasoning and emitted nothing.
        "max_tokens": 1500,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "describe", "strict": True, "schema": SCHEMA},
        },
        "usage": {"include": True},
    }
    t0 = time.monotonic()
    resp, err = _post(body, key)
    latency = time.monotonic() - t0
    out = {"model": model, "image": image.name, "latency_s": round(latency, 2),
           "usd": 0.0, "json_ok": False, "alt_text": "", "seo_slug": "", "error": err}
    if err or not resp:
        # A model that rejects json_schema is a REAL result (it disqualifies as a drop-in
        # fallback), so record it rather than retrying into a different shape.
        return out
    try:
        choice = resp["choices"][0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        # Some providers return the answer in `reasoning` with content=None even on a clean
        # finish_reason="stop" (measured: qwen3.5-flash emitted valid JSON there). Reading only
        # `content` scores a WORKING model 0/10 — a harness artifact, not a model failure.
        if not content and msg.get("reasoning"):
            content = msg["reasoning"]
            out["via_reasoning_field"] = True
    except (KeyError, IndexError, TypeError):
        out["error"] = "no choices/content in response"
        return out
    out["usd"] = _usd(resp)
    out["finish_reason"] = choice.get("finish_reason")
    obj = _extract_json(content if isinstance(content, str) else json.dumps(content))
    if obj and isinstance(obj.get("alt_text"), str) and isinstance(obj.get("seo_slug"), str):
        out.update(json_ok=True, alt_text=obj["alt_text"].strip(), seo_slug=obj["seo_slug"].strip())
    else:
        out["error"] = (f"unparseable (finish={choice.get('finish_reason')}): "
                        f"{str(content)[:100]}")
    return out


def generic_hits(alt: str) -> list[str]:
    low = (alt or "").lower()
    return [p for p in GENERIC_PATTERNS if re.search(p, low)]


def slug_valid(slug: str) -> bool:
    return bool(slug) and bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)) and len(slug) <= 60


JUDGE_PROMPT = (
    "You are grading ALT-TEXT for the attached product image. The alt-text was written by another "
    "model that saw this same image.\n\nALT-TEXT: {alt}\nSEO-SLUG: {slug}\n\n"
    "Return JSON with:\n"
    '  "accuracy": 0-5 — is every claim in the alt-text actually TRUE of this image? '
    "(5 = fully correct; 0 = describes a different object)\n"
    '  "specificity": 0-5 — does it name the ACTUAL object/material/colour/form, or is it a '
    "generic sentence that would fit thousands of product photos? (5 = precisely identifying; "
    "0 = pure filler like 'a product on a white background')\n"
    '  "slug_ok": true/false — does the slug describe THIS product usefully for SEO?\n'
    '  "note": <=15 words on the main flaw, or "none".\n'
    "Grade strictly. A fluent but generic sentence must score low on specificity."
)

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "accuracy": {"type": "integer"}, "specificity": {"type": "integer"},
        "slug_ok": {"type": "boolean"}, "note": {"type": "string"},
    },
    "required": ["accuracy", "specificity", "slug_ok", "note"],
    "additionalProperties": False,
}


def judge_once(row: dict, image: Path, judge: str, key: str) -> dict:
    if not row.get("json_ok"):
        return {"accuracy": 0, "specificity": 0, "slug_ok": False, "note": "no valid JSON"}
    body = {
        "model": judge,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": JUDGE_PROMPT.format(alt=row["alt_text"], slug=row["seo_slug"])},
            {"type": "image_url", "image_url": {"url": data_uri(image)}},
        ]}],
        "max_tokens": 300, "temperature": 0,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "grade", "strict": True, "schema": JUDGE_SCHEMA}},
        "usage": {"include": True},
    }
    resp, err = _post(body, key)
    if err or not resp:
        return {"accuracy": -1, "specificity": -1, "slug_ok": False, "note": f"judge failed: {err}"}
    try:
        obj = _extract_json(resp["choices"][0]["message"]["content"]) or {}
    except (KeyError, IndexError, TypeError):
        obj = {}
    return {
        "accuracy": int(obj.get("accuracy", -1)),
        "specificity": int(obj.get("specificity", -1)),
        "slug_ok": bool(obj.get("slug_ok", False)),
        "note": str(obj.get("note", ""))[:80],
    }


def pick_images(root: Path, limit: int) -> list[Path]:
    """Pick a SUBJECT-DIVERSE set — the whole point is separating "accurate" from "generic", and
    N shots of one candle cannot do that. Rules: dedupe byte-identical files (the corpus has exact
    dups, e.g. candle_test == candle_45); cap the same product family; spread generated picks
    across distinct sub-dirs. Masks/grids/sources are excluded — not published assets."""
    import hashlib  # noqa: PLC0415

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    seen_hash: set[str] = set()
    family_count: dict[str, int] = {}
    picks: list[Path] = []

    def _family(p: Path) -> str:
        """Group by SUBJECT, not by path. `output/batch/modelNNN/t1_flux.png` is one scene rendered
        by many generator models — the stem, not the parent dir, is the subject there (else the
        prior generator bake-off floods the sample with the same two scenes)."""
        parts = {q.name.lower() for q in p.parents}
        if "batch" in parts or re.fullmatch(r"model\d+", p.parent.name.lower()):
            return f"batch:{p.stem.lower()}"
        stem = re.split(r"[_\-.]", p.stem.lower())[0]
        return stem if len(stem) > 3 and not re.fullmatch(r"[0-9a-f]{6,}", stem) else p.parent.name

    def _take(p: Path, family_cap: int) -> bool:
        if p.suffix.lower() not in exts:
            return False
        try:
            h = hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324 — dedupe only, not security
        except OSError:
            return False
        if h in seen_hash:
            return False
        fam = _family(p)
        if family_count.get(fam, 0) >= family_cap:
            return False
        seen_hash.add(h)
        family_count[fam] = family_count.get(fam, 0) + 1
        picks.append(p)
        return True

    inp = root / "input"
    if inp.is_dir():  # real packshots: what `describe` actually runs on. Max 2 per product.
        for p in sorted(inp.iterdir()):
            if "normalized" not in p.name and len(picks) < limit:
                _take(p, family_cap=2)

    out = root / "output"
    if out.is_dir():  # generated product scenes, spread across distinct sub-dirs
        # Exclude non-publishable artifacts: masks, grids, sources, and COMPOSITES. Verified by
        # eye: `output/example/_preview_before_after.png` is a side-by-side before/after, not a
        # product photo — alt-text for a comparison collage would poison the accuracy score.
        # Convention in this repo: a leading `_` on the FILE name = internal artifact.
        bad = ("mask", "_grid", "grid", "_source", "comp", "preview", "before_after",
               "collage", "montage", "_ref", "sheet")
        gen = [p for p in sorted(out.rglob("*"))
               if p.suffix.lower() in exts
               and not p.name.startswith("_")
               and not (p.stem.isupper() and len(p.stem) > 8)  # e.g. THREE_PROVIDER.png
               and not any(x in p.name.lower() for x in bad)
               and ".edit-cache" not in str(p) and ".photofit" not in str(p)]
        by_dir: dict[Path, list[Path]] = {}
        for p in gen:
            by_dir.setdefault(p.parent, []).append(p)
        # round-robin across dirs so we sample many subjects, not many shots of one
        while len(picks) < limit and any(by_dir.values()):
            for d in list(by_dir):
                if len(picks) >= limit:
                    break
                bucket = by_dir[d]
                if bucket:
                    _take(bucket.pop(0), family_cap=1)
                else:
                    by_dir.pop(d, None)
    return picks[:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OpenRouter vision bake-off for `describe`.")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--judge", default=DEFAULT_JUDGE)
    ap.add_argument("--images-root", default=str(DEFAULT_IMAGE_ROOT))
    ap.add_argument("--limit", type=int, default=8, help="images per model")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--include-haiku", action="store_true",
                    help="also run the `claude -p haiku` PRIMARY as the baseline bar to clear")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(Path(__file__).parent / "cache" / "vision_describe_bench.json"))
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.include_haiku and HAIKU_ID not in models:
        models.append(HAIKU_ID)
    images = pick_images(Path(args.images_root), args.limit)
    if not images:
        raise SystemExit(f"no images found under {args.images_root}")

    _log(f"models={len(models)} images={len(images)} calls={len(models)*len(images)}"
         f"{' (+judge)' if not args.no_judge else ''}")
    for i in images:
        _log(f"  img: {i.relative_to(args.images_root) if str(i).startswith(args.images_root) else i}")
    if args.dry_run:
        for m in models:
            _log(f"  model: {m}")
        _log("dry-run — no API calls made, nothing spent.")
        return 0

    key = _api_key()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(describe_once, m, img, key): (m, img)
                for m in models for img in images}
        for f in as_completed(futs):
            m, img = futs[f]
            try:
                rows.append(f.result())
            except Exception as e:  # noqa: BLE001
                rows.append({"model": m, "image": img.name, "json_ok": False,
                             "error": f"{type(e).__name__}: {e}", "latency_s": 0, "usd": 0.0,
                             "alt_text": "", "seo_slug": ""})
    by_name = {i.name: i for i in images}
    if not args.no_judge:
        _log("judging…")
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(judge_once, r, by_name[r["image"]], args.judge, key): r for r in rows}
            for f in as_completed(futs):
                try:
                    futs[f].update(f.result())
                except Exception as e:  # noqa: BLE001
                    futs[f].update({"accuracy": -1, "specificity": -1, "slug_ok": False,
                                    "note": f"judge error: {type(e).__name__}"})
    for r in rows:
        r["generic_hits"] = len(generic_hits(r.get("alt_text", "")))
        r["slug_valid"] = slug_valid(r.get("seo_slug", ""))
        r["alt_len"] = len(r.get("alt_text", ""))

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    print(f"\n{'model':42} {'json':>5} {'acc':>5} {'spec':>5} {'gen':>4} {'slug':>5} "
          f"{'p50s':>6} {'usd/img':>9}")
    print("-" * 96)
    ranked = []
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        if not rs:
            continue
        ok = [r for r in rs if r.get("json_ok")]
        jr = [r for r in ok if r.get("accuracy", -1) >= 0]
        acc = statistics.mean([r["accuracy"] for r in jr]) if jr else 0.0
        spec = statistics.mean([r["specificity"] for r in jr]) if jr else 0.0
        lat = statistics.median([r["latency_s"] for r in rs]) if rs else 0.0
        usd = statistics.mean([r["usd"] for r in ok]) if ok else 0.0
        gen = sum(r["generic_hits"] for r in ok)
        slug = sum(1 for r in ok if r["slug_valid"])
        ranked.append((acc + spec, m, acc, spec))
        print(f"{m:42} {len(ok)}/{len(rs):<3} {acc:5.2f} {spec:5.2f} {gen:4} "
              f"{slug:>2}/{len(ok):<2} {lat:6.2f} {usd:9.5f}")
    print("-" * 96)
    for _s, m, a, sp in sorted(ranked, reverse=True)[:1]:
        print(f"top by accuracy+specificity: {m}  (acc {a:.2f}, spec {sp:.2f})")
    print(f"\nrows -> {outp}")
    errs = [r for r in rows if r.get("error")]
    if errs:
        print(f"\n{len(errs)} error(s); first 5:")
        for r in errs[:5]:
            print(f"  {r['model']:38} {r['image']:28} {str(r['error'])[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
