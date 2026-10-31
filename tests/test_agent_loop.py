"""Agent loop tested with a scripted fake model (no network, no tokens)."""
import json
from types import SimpleNamespace as NS

import config, memory, records
from agent import SupportAgent


def reply(content=None, calls=None, pt=100, ct=20):
    tool_calls = [NS(id=f"c{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(calls or [])]
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls or None))],
              usage=NS(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct))


class FakeClient:
    def __init__(self, script):
        self.script, self.seen = list(script), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.seen.append(json.dumps(kw["messages"]))
        return self.script.pop(0)


S = records.Student("S1001", "Bhavy Patel")


def test_tool_then_answer_with_trace():
    client = FakeClient([reply(calls=[("get_fee_status", {})]), reply("Your outstanding fee is Rs. 4,00,000.")])
    t = SupportAgent(S, client).chat("What is my current fee status?")
    assert t["tools_used"] == ["get_fee_status"] and t["llm_calls"] == 2
    assert t["tokens"] == {"input": 200, "output": 40, "total": 240}
    assert "400000" in client.seen[1]                      # the tool result reached the model before it answered
    assert t["sources"] == ["students.json#fees"] and t["latency_s"] >= 0


def test_direct_answer_without_tool():
    t = SupportAgent(S, FakeClient([reply("Hello! How can I help?")])).chat("hi")
    assert t["tools_used"] == [] and t["llm_calls"] == 1
    assert t["sources"] == ["model_only (no tool, document or memory used)"]


def test_policy_evidence_recorded_and_only_relevant_text_sent():
    client = FakeClient([reply(calls=[("search_policy", {"query": "payment portal failed next working day"})]), reply("Yes, if you raise a request.")])
    t = SupportAgent(S, client).chat("Portal failed, can I pay next working day?")
    assert t["evidence"]["policy"] == ["HB-02"] and t["sources"] == ["student_handbook.md#HB-02"]
    assert "Attendance" not in client.seen[1] and "Scholarships" not in client.seen[1]   # the rest of the handbook is NOT sent


def test_unanswerable_policy_question():
    client = FakeClient([reply(calls=[("search_policy", {"query": "hostel fee refund"})]), reply("I don't have that information.")])
    t = SupportAgent(S, client).chat("What is the hostel fee refund policy?")
    assert t["evidence"]["policy"] == [] and "no relevant section" in t["sources"][0]


def test_memory_persists_across_sessions_and_is_selected():
    SupportAgent(S, FakeClient([reply("Noted.")])).chat("Please remember I prefer to be contacted on WhatsApp.")
    assert memory.load_all("S1001")["preferred_contact"] == "WhatsApp"
    c2 = FakeClient([reply("By WhatsApp.")])
    t = SupportAgent(S, c2).chat("How should you contact me?")          # brand-new agent = new session
    assert t["evidence"]["memory"] == ["preferred_contact"] and "WhatsApp" in c2.seen[0]
    assert "memory.json#preferred_contact" in t["sources"]


def test_unrelated_question_gets_no_memory():
    memory.save("S1001", "preferred_contact", "WhatsApp")
    c = FakeClient([reply("75 percent.")])
    t = SupportAgent(S, c).chat("What is the attendance rule?")
    assert t["evidence"]["memory"] == [] and "WhatsApp" not in c.seen[0]


def test_only_last_two_turns_are_sent():
    ag = SupportAgent(S, FakeClient([reply(f"answer {i}") for i in range(4)] + [reply("final")]))
    for i in range(4):
        ag.chat(f"question {i}")
    ag.chat("latest")
    sent = ag.client.seen[-1]
    assert "question 3" in sent and "question 0" not in sent


def test_credentials_are_removed_before_the_model_sees_them():
    client = FakeClient([reply("Please never share passwords or OTPs.")])
    t = SupportAgent(S, client).chat("My password is Hunter2 and my OTP is 482913")
    assert "sensitive_input_redacted" in t["flags"]
    assert "Hunter2" not in "".join(client.seen) and "482913" not in "".join(client.seen)
    assert "credential" in client.seen[0]                      # the model is told what happened
    assert "REDACTED" in t["question"] and memory.load_all("S1001") == {}


def test_sensitive_statement_not_stored_anywhere():
    client = FakeClient([reply(calls=[("remember", {"key": "password", "value": "Hunter2"})]), reply("Please never share passwords.")])
    t = SupportAgent(S, client).chat("My password is Hunter2 and my OTP is 482913")
    assert memory.load_all("S1001") == {} and t["steps"][0]["decision"] == "blocked"
    for p in config.RUNTIME.glob("*"):
        assert "482913" not in p.read_text() and "Hunter2" not in p.read_text()


def test_step_limit_and_bad_json_arguments():
    bad = NS(choices=[NS(message=NS(content="", tool_calls=[NS(id="x", function=NS(name="get_fee_status", arguments="{oops"))]))], usage=None)
    t = SupportAgent(S, FakeClient([bad] * config.MAX_TOOL_STEPS)).chat("fees?")
    assert "step_limit_reached" in t["flags"] and t["steps"][0]["decision"] == "error"


def test_model_asking_for_unknown_tool_is_handled():
    client = FakeClient([reply(calls=[("delete_everything", {})]), reply("Sorry, I cannot do that.")])
    t = SupportAgent(S, client).chat("do something odd")
    assert t["steps"][0]["decision"] == "error" and "UNKNOWN_TOOL" in client.seen[1]


def test_trace_is_saved_locally():
    SupportAgent(S, FakeClient([reply("ok")])).chat("hello")
    line = json.loads((config.RUNTIME / "traces.jsonl").read_text().splitlines()[0])
    assert line["user"] == "S1001" and "tokens" in line and "sources" in line
