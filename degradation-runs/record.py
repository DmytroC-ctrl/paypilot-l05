"""Records the 7-step CONV-002 (C-07) dialog on one profile: per step the agent
answer, the tool calls (the retrieval context of the step), the summary and which
case entities are in the history the model receives. Usage: record.py PROFILE OUT.json"""
import json, re, sys, urllib.request

def call(m, p, d=None):
    r = urllib.request.Request("http://localhost:8000" + p,
        data=json.dumps(d).encode() if d is not None else None, method=m,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())

TURNS = [
 "I'm CUS-0004. Transaction TX-0401, 240.00 EUR: the goods never arrived. Which reason code applies?",
 "Can I dispute it?",
 "What is my daily card limit?",
 "And the FX spread if I pay in USD?",
 "Fine. Back to that charge — what do I do next?",
 "240 euro, as I said at the start.",
 "And I still have time to file, right?",
]
ENT = {"сума": r"240", "дата": r"20 July|July 20|2026-07-20",
       "reason code": r"goods[_ ]not[_ ]received", "вікно": r"\b90\b"}

def spans(n):
    yield n
    for c in n.get("children", []):
        yield from spans(c)

profile, out = sys.argv[1], sys.argv[2]
call("PUT", "/api/_test/profile", {"profile": profile})
call("POST", "/api/_test/reset")
call("PUT", "/api/_test/summarize_after", {"steps": 2})
call("PUT", "/api/_test/clock", {"now": "2026-09-15T10:00:00+00:00"})
sid, rows, history = None, [], []
for i, t in enumerate(TURNS, 1):
    r = call("POST", "/chat", {"message": t, "session_id": sid}); sid = r["session_id"]
    tree = call("GET", "/api/_test/traces/" + r["request_id"])
    sp = list(spans(tree))
    summ = next((s["attributes"] for s in sp if s["name"] == "agent.summarize"), None)
    tools = [{"name": s["name"][5:], "args": s["attributes"].get("tool.arguments"),
              "result": s["attributes"].get("tool.result")} for s in sp if s["name"].startswith("tool.")]
    if summ:
        history = [summ["summary.text"]]
    hist_in = "\n".join(history)
    rows.append({"step": i, "user": t, "answer": r["answer"],
                 "summary": summ["summary.text"] if summ else None,
                 "history_entities_at_input": {k: bool(re.search(v, hist_in, re.I)) for k, v in ENT.items()},
                 "tools": tools, "request_id": r["request_id"]})
    history += [t] + [json.dumps(x["result"], ensure_ascii=False) for x in tools] + [r["answer"]]
json.dump({"profile": profile, "session_id": sid, "steps": rows}, open(out, "w"), ensure_ascii=False, indent=1)
print(profile, out, "ok")
