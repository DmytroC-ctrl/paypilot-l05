"""Records one multi-turn case from sets/l05.jsonl (MEM-001-RC, MEM-001-AMT, ...) on a profile:
per step the answer, tool calls, the summary and the case entities in the history the model
receives. Usage: record_case.py CASE_ID PROFILE OUT.json  (stand: summarize_after 2, clock 2026-09-15)"""
import json, re, sys, urllib.request
from pathlib import Path

def call(m, p, d=None):
    r = urllib.request.Request("http://localhost:8000" + p,
        data=json.dumps(d).encode() if d is not None else None, method=m,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())

def spans(n):
    yield n
    for c in n.get("children", []):
        yield from spans(c)

case_id, profile, out = sys.argv[1:4]
src = Path(__file__).resolve().parent.parent / "sets" / "l05.jsonl"
case = next(json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l)["id"] == case_id)
TURNS = [t["content"] for t in case["turns"] if t["role"] == "user"]
ENT = {"сума": r"\b240\b", "reason code": r"duplicate[_ ]charge", "TX-0401": r"TX-0401"}
call("PUT", "/api/_test/profile", {"profile": profile})
call("POST", "/api/_test/reset")
call("PUT", "/api/_test/summarize_after", {"steps": 2})
call("PUT", "/api/_test/clock", {"now": "2026-09-15T10:00:00+00:00"})
sid, rows, history = None, [], []
for i, t in enumerate(TURNS, 1):
    r = call("POST", "/chat", {"message": t, "session_id": sid}); sid = r["session_id"]
    sp = list(spans(call("GET", "/api/_test/traces/" + r["request_id"])))
    summ = next((s["attributes"] for s in sp if s["name"] == "agent.summarize"), None)
    tools = [{"name": s["name"][5:], "args": s["attributes"].get("tool.arguments"),
              "result": s["attributes"].get("tool.result")} for s in sp if s["name"].startswith("tool.")]
    kb = [s["attributes"] for s in sp if s["name"].startswith("tool.search_knowledge_base")]
    if summ:
        history = [summ["summary.text"]]
    hist_in = "\n".join(history)
    rows.append({"step": i, "user": t, "answer": r["answer"],
                 "summary": summ["summary.text"] if summ else None,
                 "history_entities_at_input": {k: bool(re.search(v, hist_in, re.I)) for k, v in ENT.items()},
                 "tools": tools, "kb_calls": len(kb), "request_id": r["request_id"]})
    history += [t] + [json.dumps(x["result"], ensure_ascii=False) for x in tools] + [r["answer"]]
json.dump({"case": case_id, "profile": profile, "steps": rows}, open(out, "w"), ensure_ascii=False, indent=1)
print(case_id, profile, out, "ok")
