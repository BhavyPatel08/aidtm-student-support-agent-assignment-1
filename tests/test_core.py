"""Tools, memory and retrieval. No LLM and no API tokens needed."""
import json

import pytest

import memory, rag, records, tools

S1 = records.Student("S1001", "Bhavy Patel")
S2 = records.Student("S1002", "Aarav Shah")


# ---------------------------------------------------------------- tools
def test_data_tools_are_bound_to_the_selected_student():
    assert tools.execute(S1, "get_fee_status", {})[0]["fees"]["status"] == "Installment 3 pending"
    assert tools.execute(S2, "get_fee_status", {})[0]["fees"]["status"] == "Paid up to date"
    assert tools.execute(S1, "get_scholarship_status", {})[0]["scholarship"]["name"] == "Merit Scholarship"
    rec = tools.execute(S2, "get_student_record", {})[0]
    assert rec["name"] == "Aarav Shah" and "Artificial Intelligence" in rec["programme"]


def test_model_cannot_choose_another_student():
    for schema in tools.TOOL_SCHEMAS:
        assert "student_id" not in schema["function"]["parameters"]["properties"]
    res, _ = tools.execute(S1, "get_fee_status", {"student_id": "S1002"})   # an extra argument is simply ignored
    assert res["student_id"] == "S1001"


def test_support_request_and_errors():
    res, info = tools.execute(S1, "create_support_request", {"category": "fees", "description": "receipt missing"})
    assert res["ticket_id"] == "TKT-0001" and info["decision"] == "allowed"
    assert tools.load_tickets()[0]["student"] == "S1001"
    assert tools.execute(S1, "create_support_request", {"category": "fees", "description": "x"})[0]["error"] == "MISSING_INFO"
    assert tools.execute(S1, "create_support_request", {"category": "weird", "description": "something broke"})[0]["ticket_id"] == "TKT-0002"
    assert tools.execute(S1, "no_such_tool", {})[0]["error"] == "UNKNOWN_TOOL"
    assert tools.execute(S1, "search_policy", {})[0]["error"] == "MISSING_INFO"


def test_credentials_never_stored_in_tickets():
    tools.execute(S1, "create_support_request", {"category": "technical", "description": "login fails, my OTP is 482913"})
    assert "482913" not in json.dumps(tools.load_tickets())


def test_tool_crash_becomes_structured_error(monkeypatch):
    monkeypatch.setitem(tools._HANDLERS, "get_fee_status", lambda s, a: 1 / 0)
    res, info = tools.execute(S1, "get_fee_status", {})
    assert res["error"] == "TOOL_ERROR" and info["decision"] == "error"


def test_missing_student_record():
    res, _ = tools.execute(records.Student("S9999", "Nobody"), "get_fee_status", {})
    assert res["error"] == "NOT_FOUND"


# ---------------------------------------------------------------- memory
@pytest.mark.parametrize("text", ["My OTP is 482913", "my password is hunter2", "CVV 123", "card 4111 1111 1111 1111", "aadhaar 1234 5678 9012"])
def test_sensitive_detected_and_redacted(text):
    assert memory.contains_sensitive(text) and "REDACTED" in memory.redact(text)


def test_phone_number_is_not_sensitive():
    assert not memory.contains_sensitive("my phone is +91 98888 77777")


def test_memory_guard():
    assert memory.save("S1001", "preferred_contact", "WhatsApp")[0]
    assert not memory.save("S1001", "preferred_contact", "otp 482913")[0]       # sensitive
    assert not memory.save("S1001", "password", "hunter2")[0]                    # key not allowed
    assert not memory.save("S1001", "programme", "in the library today")[0]      # temporary
    assert not memory.save("S1001", "preferred_name", "x\ny")[0]                 # not a short single line
    assert memory.load_all("S1001") == {"preferred_contact": "WhatsApp"}


def test_memory_is_per_student_and_selected_by_relevance():
    memory.save("S1001", "preferred_contact", "WhatsApp")
    memory.save("S1001", "programme", "PGDM Big Data Analytics")
    memory.save("S1002", "preferred_contact", "Email")
    assert memory.select_relevant("S1001", "How should you contact me?") == {"preferred_contact": "WhatsApp"}
    assert memory.select_relevant("S1001", "What is the attendance rule?") == {}
    assert memory.select_relevant("S1002", "contact me") == {"preferred_contact": "Email"}


def test_explicit_preferences_are_extracted():
    assert ("preferred_contact", "WhatsApp") in memory.extract_candidates("Please remember I prefer to be contacted on WhatsApp.")
    assert ("preferred_language", "Hindi") in memory.extract_candidates("I prefer replies in Hindi")
    assert memory.extract_candidates("I am in the library right now") == []


# ---------------------------------------------------------------- retrieval
def test_retrieval_relevant_and_unanswerable():
    assert rag.search("The payment portal failed, can I pay on the next working day?")[0]["id"] == "HB-02"
    assert rag.search("what is the attendance requirement")[0]["id"] == "HB-08"
    assert rag.search("how do I change my elective")[0]["id"] == "HB-05"
    assert rag.search("what is the hostel fee refund policy") == []
    assert rag.search("tell me about parking") == []
    assert len(rag.search("late fee amount")) <= 2
