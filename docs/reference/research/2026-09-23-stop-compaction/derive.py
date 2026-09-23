"""Re-derive every judged number in the stop-and-compaction spec from the committed verdict files."""
import collections
import json
import pathlib

D = pathlib.Path(__file__).parent
o = json.loads((D / "verdict-opdec.json").read_text())
c = json.loads((D / "verdict-context.json").read_text())
k = json.loads((D / "verdict-compact.json").read_text())
f = [r for r in o if r["verdict"] == "FALSE"]
print("opdec", len(o), dict(collections.Counter(r["verdict"] for r in o)))
print("opdec FALSE shapes", dict(collections.Counter(r["shape"] for r in f)), "reply_unneeded YES", sum(r["reply_unneeded"] == "YES" for r in f))
print("context", len(c), dict(collections.Counter(r["verdict"] for r in c)))
for t in ("auto", "manual"):
    print("compact", t, sum(r["trigger"] == t for r in k), dict(collections.Counter(r["verdict"] for r in k if r["trigger"] == t)))
print("compact run_live", dict(collections.Counter((r["run_live"], r["verdict"]) for r in k)))
print("opdec repos", dict(collections.Counter(r["repo"] for r in o).most_common(5)))
ev = json.loads((D / "stop-events-2026-09-23.json").read_text())["counts"]
print("stop events", {k: v for k, v in ev.items() if "promise-stall" in k or k == "stop_pass|None|clean"})
