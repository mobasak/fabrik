"""The D4 prototype the spec states: fires only when the agent hands its own work to a later session/window/context.

Run over the judged context records' deciding quotes (red: STOP-EXCUSE, green: FALSE-MATCH) and over ordinary prose that
merely mentions a session or a context (green fixtures raised by the round-3 review seat, A-O34).
"""
import json, pathlib, re
D = pathlib.Path(__file__).parent
_WHERE = r"(?:fresh|new|clean|separate)\s+(?:session|window|context|chat)"
D4 = re.compile(
    rf"\b(?:in|open|start|use|needs?|wants?|deserves?|requires?)\s+a\s+{_WHERE}\b(?![^.\n]{{0,60}}\b(?:MCP|roster|reload|quota|5h|weekly|reset)\b)"
    rf"|\b(?:a|the)\s+{_WHERE}\s+(?:finishes|runs|should|must|will|checks?|does)\b"
    r"|\bcontext\s+(?:is\s+)?getting\s+(?:long|full|low|tight)\b|\bcompact\s+first\b|\bthis\s+session\s+(?:is|has\s+been)\s+(?:long|running\s+long)\b",
    re.I,
)
v = json.loads((D / "verdict-context.json").read_text())
for want in ("STOP-EXCUSE", "FALSE-MATCH"):
    rows = [r for r in v if r["verdict"] == want]
    print(want, f"{sum(bool(D4.search(r['quote'])) for r in rows)}/{len(rows)} fire", [r["id"] for r in rows if D4.search(r["quote"])])
PROSE = [
    "SessionStart fires on a new session and on resume.",
    "Given the new context from the logs, the fix is in scrape.py.",
    "The hook now reads a new session-recall index.",
    "Context is never a reason to stop, and a fresh session is never the remedy.",
    "the reconstructor handles a new session id correctly",
    "DONE: fixed the clean context test fixture",
    "STATE: tests green; the new chat widget ships",
]
print("ordinary prose", f"{sum(bool(D4.search(s)) for s in PROSE)}/{len(PROSE)} fire")
