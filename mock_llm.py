"""Offline stand-in for the model (keyword rules, NOT an LLM).
Used only for `python eval.py --mock` and the app's Demo mode, to try everything without API tokens."""
import json
import re
from types import SimpleNamespace as NS


def _resp(content=None, calls=None, prompt_text=""):
    tcs = [NS(id=f"m{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(calls or [])]
    pt = max(len(prompt_text) // 4, 1)
    return NS(choices=[NS(message=NS(content=content, tool_calls=tcs or None))],
              usage=NS(prompt_tokens=pt, completion_tokens=30, total_tokens=pt + 30))


def _final(tool_json: dict) -> str:
    if tool_json.get("error"):
        return "I could not complete that: " + tool_json.get("message", "error")
    if "ticket_id" in tool_json:
        return f"I raised support request {tool_json['ticket_id']}. Expect a reply in 2 working days."
    if "fees" in tool_json:
        f = tool_json["fees"]
        return (f"Status: {f['status']}. Outstanding Rs. {f['outstanding']}. "
                f"Installment {f['next_installment']['number']} of Rs. {f['next_installment']['amount']} is due {f['next_installment']['due_date']}.")
    if "scholarship" in tool_json:
        s = tool_json["scholarship"]
        return f"{s['name']}: {s['status']}."
    if "programme" in tool_json:
        return f"You are in {tool_json['programme']} (batch {tool_json['batch']})."
    if "results" in tool_json:
        if not tool_json["results"]:
            return "I don't have that information in the handbook. I can raise a support request for you."
        return tool_json["results"][0]["text"]
    return "Done."


class MockClient:
    def __init__(self):
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        msgs = kw["messages"]
        prompt = json.dumps(msgs)
        last = msgs[-1]
        if last["role"] == "tool":
            return _resp(_final(json.loads(last["content"])), prompt_text=prompt)
        q = last["content"]
        ql = q.lower()
        memo = next((m["content"] for m in msgs if m["role"] == "system" and m["content"].startswith("Remembered")), "")
        if memo and "contact" in ql:
            return _resp("You prefer: " + memo.split(": ", 1)[1], prompt_text=prompt)
        if "remember" in ql:
            return _resp("Noted.", prompt_text=prompt)
        if "scholarship" in ql:
            return _resp(calls=[("get_scholarship_status", {})], prompt_text=prompt)
        if "fee status" in ql or "my record" in ql:
            return _resp(calls=[("get_fee_status", {})], prompt_text=prompt)
        if "which programme" in ql or "my programme" in ql:
            return _resp(calls=[("get_student_record", {})], prompt_text=prompt)
        if "support request" in ql and "raise" in ql:
            return _resp(calls=[("create_support_request", {"category": "fees", "description": q})], prompt_text=prompt)
        focus = [p.strip() for p in re.split(r"(?<=[.?!])\s+", q) if p.strip()][-1]
        return _resp(calls=[("search_policy", {"query": focus})], prompt_text=prompt)
