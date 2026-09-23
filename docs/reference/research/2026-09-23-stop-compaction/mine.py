"""Mine the box's Claude Code transcripts for premature-stop shapes and compaction outcomes.

Population: every top-level <projects>/<slug>/<session>.jsonl (subagent transcripts live deeper and are
excluded), entries timestamped >= SINCE. A TURN END is the last assistant text entry before the next REAL
user message (a text block that is not a tool result, not a compact summary, not a command/caveat wrapper).
For each turn end we record the shapes below and the operator's reply that followed it.
"""

from __future__ import annotations

import collections
import random
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / ".claude-fleet" / "active" / "projects"
SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-08-09"
OUT = Path(__file__).parent

spec = importlib.util.spec_from_file_location("fgs", "/opt/fabrik/.claude/hooks/final_gate_stop.py")
fgs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fgs)

NEXT_LINE = re.compile(r"^\s*\**NEXT:\**(.*)$", re.M)
OPDEC = re.compile(
    r"operator decision|your call|await\w*\s+(?:your|the operator)|on your (?:yes|word|go|approval)"
    r"|say the word|if you want|your go\b|your approval|yours to (?:decide|choose)|you decide",
    re.I,
)
MENU = re.compile(
    r"(?:^|\s)\(?a\)\s.{3,}?(?:^|\s)\(?b\)\s|\boption\s+(?:A|1)\b.{3,}?\boption\s+(?:B|2)\b"
    r"|^\s*(?:A|1)[.)]\s.+\n(?:.*\n){0,6}?\s*(?:B|2)[.)]\s",
    re.I | re.S | re.M,
)
QUESTION_ASK = re.compile(
    r"\b(?:which (?:do you|would you|one)|do you (?:want|prefer|agree)|would you (?:like|prefer)"
    r"|should (?:I|we)|shall (?:I|we)|want me to|let me know (?:if|whether|which)|can you confirm"
    r"|okay to|ok to|proceed\?|go ahead\?|confirm (?:that|whether)|your preference)\b",
    re.I,
)
CONTEXT_EXCUSE = re.compile(
    r"\b(?:context (?:window |budget )?(?:is |getting |running )(?:long|full|large|low|tight|heavy)"
    r"|(?:low|limited|remaining) context|context (?:budget|limit|pressure|headroom)"
    r"|fresh (?:window|session|chat|context)|new (?:window|session|chat) (?:for|to)"
    r"|(?:before|after) (?:a |the )?compact|compact (?:first|this|the chat|now)"
    r"|out of context|context is (?:nearly|almost) (?:full|exhausted))",
    re.I,
)
GO_AHEAD = re.compile(
    r"^\W*(?:yes|yep|yeah|ok|okay|go|go ahead|proceed|continue|do it|allowed|approved|agreed|sure"
    r"|evet|tamam|devam|y|k|go on|carry on|right|correct|fine)\b",
    re.I,
)
CONFUSED = re.compile(
    r"why (?:are|do|did) you (?:ask|stop)|(?:do not|don't|dont) understand|what (?:do|will|should) i decide"
    r"|nothing to decide|why (?:do )?you ask|you (?:already )?(?:have|know) (?:the|all)|obvious"
    r"|dont ask|don't ask|do not ask|stop asking|why did you stop|you stopped|keep going|don't stop|dont stop",
    re.I,
)
CORRECTION = re.compile(
    r"\b(?:you forgot|we were|that'?s not what|not what (?:i|we)|diverg|wrong task|lost track"
    r"|you lost|already (?:did|done)|again\?|we already|remember)\b",
    re.I,
)
WRAPPER = re.compile(r"^\s*(?:<command-|<local-command|Caveat:|<system-reminder>|\[Request interrupted)")


def user_text(entry: dict) -> str | None:
    msg = entry.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        t = c
    elif isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        t = "\n".join(str(b.get("text") or "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    else:
        return None
    if not t.strip() or WRAPPER.match(t):
        return None
    return t


def asst_text(entry: dict) -> str:
    c = (entry.get("message") or {}).get("content")
    if not isinstance(c, list):
        return ""
    return "\n".join(str(b.get("text") or "") for b in c if isinstance(b, dict) and b.get("type") == "text")


def detector(text: str) -> str | None:
    """The shipped hook's regexes over the message tail, minus the midrun/dispatch context (unknowable here)."""
    tail = text[-600:]
    for name, pat in (
        ("promise", fgs._PROMISE_VERB_RE),
        ("obligation", fgs._OBLIGATION_RE),
        ("continuation", fgs._CONTINUATION_CLAIM_RE),
        ("next_round", fgs._NEXT_ROUND_RE),
        ("permission", fgs._PERMISSION_RE),
    ):
        for m in pat.finditer(tail):
            if name == "promise" and not fgs._ACTION_OBJECT_RE.search(tail[m.end() : m.end() + 60]):
                continue
            if fgs._GATE_EXEMPT_GLOBAL_RE.search(text) or fgs._line_exempt(tail, m):
                return f"{name}:exempt"
            return name
    return None


rows = []
compactions = []
files = sorted(p for p in ROOT.glob("*/*.jsonl"))
for path in files:
    repo = path.parent.name
    last_text = None  # (text, ts) of the last assistant text since the last real user msg
    pending = None  # the recorded turn-end awaiting its operator reply
    headless = False
    post_compact = None
    try:
        fh = path.open("rb")
    except OSError:
        continue
    with fh:
        for raw in fh:
            if b'"type"' not in raw:
                continue
            try:
                e = json.loads(raw)
            except Exception:
                continue
            if e.get("isSidechain"):
                continue
            ts = str(e.get("timestamp") or "")
            et = e.get("type")
            if et == "system" and e.get("subtype") == "compact_boundary":
                if ts >= SINCE:
                    md = e.get("compactMetadata") or {}
                    post_compact = {
                        "repo": repo,
                        "session": path.stem,
                        "ts": ts,
                        "trigger": md.get("trigger"),
                        "preTokens": md.get("preTokens"),
                        "pre_next": (NEXT_LINE.findall(last_text[0])[-1].strip()[:240] if last_text and NEXT_LINE.findall(last_text[0]) else None),
                        "summary_tail": None,
                        "first_after": None,
                        "reply_after": None,
                    }
                    compactions.append(post_compact)
                continue
            if et == "user":
                if e.get("isCompactSummary"):
                    if post_compact is not None and post_compact["summary_tail"] is None:
                        post_compact["summary_tail"] = (user_text(e) or "")[-900:]
                    continue
                if e.get("entrypoint") == "sdk-cli":
                    headless = True
                t = user_text(e)
                if t is None:
                    continue
                if last_text and last_text[1] >= SINCE:
                    rec = {"repo": repo, "session": path.stem, "ts": last_text[1], "text": last_text[0], "headless": headless}
                    rec["reply"] = t[:300]
                    rows.append(rec)
                    if post_compact is not None and post_compact["first_after"] is not None and post_compact["reply_after"] is None:
                        post_compact["reply_after"] = t[:300]
                last_text = None
                continue
            if et == "assistant":
                t = asst_text(e)
                if t.strip():
                    last_text = (t, ts)
                    if post_compact is not None and post_compact["first_after"] is None and ts >= post_compact["ts"]:
                        post_compact["first_after"] = t[-900:]
    if last_text and last_text[1] >= SINCE:
        rows.append({"repo": repo, "session": path.stem, "ts": last_text[1], "text": last_text[0], "headless": headless, "reply": None})

stats = collections.Counter()
per_repo = collections.defaultdict(collections.Counter)
samples = collections.defaultdict(list)
seen = collections.Counter()
rng = random.Random(20260923)
for r in rows:
    if r["headless"]:
        stats["headless_turn_ends"] += 1
        continue
    text = r["text"]
    tail = text[-700:]
    nexts = NEXT_LINE.findall(text)
    nxt = nexts[-1] if nexts else ""
    f = {
        "turn_ends": True,
        "next_line": bool(nxt),
        "next_opdec": bool(OPDEC.search(nxt)),
        "next_opdec_grounded": bool(OPDEC.search(nxt) and (fgs._GATE_CLASS_RE.search(nxt) or fgs._GATE_EXEMPT_NAMED_RE.search(nxt))),
        "ends_question": "?" in "\n".join(l for l in tail.splitlines()[-6:] if not l.lstrip().startswith(("STATE:", "GATE:", "DONE:", "FEEDBACK:"))),
        "asks": bool(QUESTION_ASK.search(tail)),
        "menu": bool(MENU.search(tail)),
        "context_excuse": bool(CONTEXT_EXCUSE.search(text)),
    }
    det = detector(text)
    f["detector_fires"] = bool(det) and not det.endswith(":exempt")
    f["detector_exempted"] = bool(det) and det.endswith(":exempt")
    stop_shape = f["next_opdec"] or f["asks"] or f["menu"] or f["context_excuse"]
    f["stop_shape"] = stop_shape
    f["stop_shape_undetected"] = stop_shape and not f["detector_fires"]
    reply = r["reply"] or ""
    f["reply_go_ahead"] = bool(reply) and len(reply) < 120 and bool(GO_AHEAD.match(reply))
    f["reply_confused"] = bool(CONFUSED.search(reply))
    f["stop_then_go"] = stop_shape and f["reply_go_ahead"]
    f["stop_then_confused"] = stop_shape and f["reply_confused"]
    for k, v in f.items():
        if v:
            stats[k] += 1
            per_repo[r["repo"]][k] += 1
    for k in ("stop_then_go", "stop_then_confused", "context_excuse", "next_opdec", "menu"):
        if f[k]:
            seen[k] += 1
            item = {"repo": r["repo"], "session": r["session"], "ts": r["ts"], "tail": text[-1500:], "reply": reply[:300]}
            if len(samples[k]) < 400:
                samples[k].append(item)
            else:
                j = rng.randrange(seen[k])
                if j < 400:
                    samples[k][j] = item

comp = collections.Counter()
for c in compactions:
    comp[f"trigger_{c['trigger']}"] += 1
    if c["reply_after"] and CORRECTION.search(c["reply_after"]):
        comp["reply_after_correction"] += 1
    if c["first_after"] and (OPDEC.search(c["first_after"]) or QUESTION_ASK.search(c["first_after"][-700:])):
        comp["first_after_asks"] += 1

(OUT / "stats2.json").write_text(json.dumps({
    "since": SINCE,
    "files": len(files),
    "turn_end_rows": len(rows),
    "stats": stats,
    "compactions": comp,
    "compactions_n": len(compactions),
    "per_repo_top": sorted(((k, dict(v)) for k, v in per_repo.items()), key=lambda kv: -kv[1].get("turn_ends", 0))[:25],
}, indent=1, default=dict))
(OUT / "samples2.json").write_text(json.dumps(samples, indent=1))
(OUT / "compactions2.json").write_text(json.dumps(compactions, indent=1))
print(json.dumps({"files": len(files), "rows": len(rows), "stats": stats, "compactions": comp, "n_comp": len(compactions)}, default=dict))
