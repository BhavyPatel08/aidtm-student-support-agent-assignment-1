"""Tools the agent can call (Assignment 1).
Every data tool is bound to the student currently being helped - the model cannot pick another student."""
import datetime
import json

import config
import memory
import observability as obs
import rag
import records

CATEGORIES = {"fees", "scholarship", "course", "technical", "other"}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_student_record",
        "description": "Get this student's profile: programme, batch, email, phone, courses.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_fee_status",
        "description": "Get this student's fee status: total, paid, outstanding, next installment and due date.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_scholarship_status",
        "description": "Get this student's scholarship name, status and amount.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "search_policy",
        "description": "Search the student handbook for rules and policies (fees, late fee, portal failure, scholarships, course change, attendance, privacy).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "create_support_request",
        "description": "Create a support ticket for this student (use for requests the agent cannot do itself, e.g. course or contact changes).",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "enum": sorted(CATEGORIES)},
            "description": {"type": "string"}}, "required": ["category", "description"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": "Save a durable preference or fact for future sessions. Keys: programme, preferred_contact, preferred_language, preferred_name, study_interest. Never for temporary or sensitive information.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
]

# Where each tool gets its data from (shown in traces: "where did this answer come from?")
TOOL_SOURCES = {
    "get_student_record": "students.json#profile", "get_fee_status": "students.json#fees",
    "get_scholarship_status": "students.json#scholarship", "search_policy": "student_handbook.md",
    "create_support_request": "tickets.json (write)", "remember": "memory.json (write)",
}


# ------------------------------------------------------------------ tool implementations
def _reader(build):
    def handler(student, args):
        rec = records.get(student.user_id)
        if rec is None:
            return {"error": "NOT_FOUND", "message": "No record found for this student."}, {"decision": "error"}
        return {"student_id": student.user_id, **build(rec)}, {"decision": "allowed"}
    return handler


_get_record = _reader(lambda r: {"name": r["name"], "programme": r["programme"], "batch": r["batch"],
                                 "email": r["email"], "phone": r["phone"], "courses": r["courses"]})
_get_fees = _reader(lambda r: {"fees": r["fees"]})
_get_scholarship = _reader(lambda r: {"scholarship": r["scholarship"]})


def _search_policy(student, args):
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "MISSING_INFO", "message": "Provide a search query."}, {"decision": "error"}
    hits = rag.search(query)
    if not hits:
        return ({"results": [], "message": "No relevant policy text found."},
                {"decision": "allowed", "evidence": []})
    return (
        {"results": [{"id": h["id"], "title": h["title"], "text": h["text"]} for h in hits]},
        {"decision": "allowed", "evidence": [{"id": h["id"], "score": round(h["score"], 3)} for h in hits]},
    )


def tickets_path():
    return config.runtime_path("tickets.json")


def load_tickets() -> list:
    p = tickets_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _create_support_request(student, args):
    category = str(args.get("category", "other")).lower()
    category = category if category in CATEGORIES else "other"
    description = memory.redact(str(args.get("description", "")).strip())  # never store credentials in a ticket
    if len(description) < 5:
        return {"error": "MISSING_INFO", "message": "Ask the student to describe the problem."}, {"decision": "error"}
    tickets = load_tickets()
    tid = f"TKT-{len(tickets) + 1:04d}"
    tickets.append({"ticket_id": tid, "student": student.user_id, "category": category, "description": description,
                    "status": "open", "created": datetime.datetime.now().isoformat(timespec="seconds")})
    tickets_path().write_text(json.dumps(tickets, indent=2, ensure_ascii=False), encoding="utf-8")
    return ({"ticket_id": tid, "status": "open", "expected_response": "2 working days"}, {"decision": "allowed"})


def _remember(student, args):
    ok, reason = memory.save(student.user_id, str(args.get("key", "")), str(args.get("value", "")))
    result = {"saved": True} if ok else {"saved": False, "reason": reason}
    return result, {"decision": "allowed" if ok else "blocked"}


_HANDLERS = {
    "get_student_record": _get_record,
    "get_fee_status": _get_fees,
    "get_scholarship_status": _get_scholarship,
    "search_policy": _search_policy,
    "create_support_request": _create_support_request,
    "remember": _remember,
}


def execute(student, name: str, args):
    """Run one tool call inside a LangSmith span (a no-op when tracing is off).
    Never raises: errors become structured results the model can explain to the student."""
    run_type = "retriever" if name == "search_policy" else "tool"
    args = args if isinstance(args, dict) else {}
    shown = {k: v for k, v in args.items() if not (name == "remember" and k == "value")}  # never trace what is being remembered
    with obs.span(f"tool:{name}", run_type, inputs={"args": shown, "student": student.user_id},
                  tags=["tool", name], metadata={"data_source": TOOL_SOURCES.get(name, "unknown")}) as sp:
        handler = _HANDLERS.get(name)
        if handler is None:
            result, info = {"error": "UNKNOWN_TOOL", "message": f"No tool named {name}."}, {"decision": "error"}
        else:
            try:
                result, info = handler(student, args)
            except Exception as exc:  # tool failure handling
                result = {"error": "TOOL_ERROR", "message": "The tool failed. Tell the student and offer a support request."}
                info = {"decision": "error", "exception": type(exc).__name__}
        if name == "search_policy":
            scores = [e["score"] for e in info.get("evidence", [])]
            docs = [{"page_content": r["text"], "metadata": {"source": "student_handbook.md", "section": r["id"],
                                                             "title": r["title"], "score": sc}}
                    for r, sc in zip(result.get("results", []), scores)]
            sp.end(outputs={"documents": docs, "decision": info["decision"]}, metadata={"decision": info["decision"]})
        else:
            sp.end(outputs={"decision": info["decision"], "result": result}, metadata={"decision": info["decision"]})
    return result, info
