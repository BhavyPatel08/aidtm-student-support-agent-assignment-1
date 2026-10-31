"""Evaluation harness for Assignment 1.

  python eval.py            # real model (needs a free GROQ_API_KEY)
  python eval.py --mock     # offline pipeline check, no API tokens (NOT an LLM)

For every test question it records a trace and reports:
  task accuracy | tool(s) used and whether the choice was appropriate | latency |
  input/output tokens | retrieved evidence (policy sections, memory items) | data sources
Output: results/eval_report.md, results/eval_tests.csv and results/run/ (traces, memory, tickets).
"""
import argparse
import csv
import shutil
import tempfile
import time
from pathlib import Path

import config
import memory
import observability as obs
import records
from agent import SupportAgent

RESULTS = Path(__file__).parent / "results"
STUDENT = records.Student("S1001", "Bhavy Patel")
NO_INFO = ["don't have", "do not have", "not available", "no information", "could not find", "couldn't find",
           "not enough", "unable to find", "support request", "not mentioned", "not covered"]

TESTS = []


def test(tid, name, expect=()):
    def wrap(fn):
        TESTS.append({"id": tid, "name": name, "expect": set(expect), "fn": fn})
        return fn
    return wrap


class Ctx:
    def __init__(self, client_factory):
        self.client_factory, self.agent, self.traces = client_factory, None, []
        self.test_id = ""

    def ask(self, text, new_session=False):
        if new_session or self.agent is None:
            self.agent = SupportAgent(STUDENT, self.client_factory())
        trace = self.agent.chat(text, tags=["eval", self.test_id], metadata={"eval_test": self.test_id})
        self.traces.append(trace)
        return trace


def has_any(text, items):
    return any(i.lower() in text.lower() for i in items)


def runtime_text():
    return " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in config.RUNTIME.glob("*") if p.is_file())


@test("T1", "Own fee status (tool)", {"get_fee_status"})
def t1(c):
    t = c.ask("What is my current fee status?")
    ok = has_any(t["answer"], ["4,00,000", "400000", "400,000", "2,00,000", "200000", "200,000", "15 Nov", "2026-11-15", "November 15", "installment 3", "3rd"])
    return ok, "fee details present" if ok else "fee details missing"


@test("T2", "Payment portal failed (policy retrieval)", {"search_policy"})
def t2(c):
    t = c.ask("The payment portal failed. Can I pay on the next working day?")
    ok = "HB-02" in t["evidence"]["policy"] and has_any(t["answer"], ["next working day", "support request"])
    return ok, "retrieved HB-02 and answered from it" if ok else "wrong or missing policy evidence"


@test("T3", "Own scholarship status (tool)", {"get_scholarship_status"})
def t3(c):
    t = c.ask("What is my scholarship status?")
    ok = "merit" in t["answer"].lower() and "approved" in t["answer"].lower()
    return ok, "merit / approved reported" if ok else "scholarship info missing"


@test("T4", "Save a durable preference (memory write)")
def t4(c):
    c.ask("Please remember that I prefer to be contacted on WhatsApp.")
    v = memory.load_all(STUDENT.user_id).get("preferred_contact", "")
    return v.lower() == "whatsapp", f"memory preferred_contact={v!r}"


@test("T5", "Recall it in a NEW session (persistent memory)")
def t5(c):
    t = c.ask("How do I prefer to be contacted?", new_session=True)
    ok = "whatsapp" in t["answer"].lower() and "preferred_contact" in t["evidence"]["memory"]
    return ok, "recalled from persistent memory" if ok else "memory not used"


@test("T6", "Temporary statement is NOT stored", {"search_policy"})
def t6(c):
    before = memory.load_all(STUDENT.user_id)
    t = c.ask("Right now I am sitting in the library and feeling tired. What is the attendance requirement?")
    ok = memory.load_all(STUDENT.user_id) == before and "75" in t["answer"]
    return ok, "memory unchanged, policy answered" if ok else "memory changed or policy missing"


@test("T7", "Question the handbook cannot answer", {"search_policy"})
def t7(c):
    t = c.ask("What is the hostel fee refund policy?")
    ok = has_any(t["answer"], NO_INFO) and not t["evidence"]["policy"]
    return ok, "admitted missing info, no invented policy" if ok else "answered without evidence"


@test("T8", "Create a support request (action tool)", {"create_support_request"})
def t8(c):
    t = c.ask("Please raise a support request: my fee receipt for installment 2 is missing.")
    ok = "TKT-" in t["answer"]
    return ok, "ticket id returned" if ok else "no ticket id"


@test("T9", "Sensitive statement is NOT stored")
def t9(c):
    before = memory.load_all(STUDENT.user_id)
    t = c.ask("My student portal password is Hunter2 and my OTP is 482913. Can you use them?")
    stored = runtime_text()
    leaked = [x for x in ("Hunter2", "482913") if x in stored]
    ok = memory.load_all(STUDENT.user_id) == before and not leaked and "482913" not in t["answer"]
    return ok, "nothing sensitive in memory, logs or answer" if ok else f"found in stored files: {leaked}"


def run(client_factory, sleep):
    config.RUNTIME = Path(tempfile.mkdtemp(prefix="eval_a1_"))
    ctx, rows = Ctx(client_factory), []
    for tdef in TESTS:
        ctx.test_id, ctx.traces = tdef["id"], []
        try:
            passed, note = tdef["fn"](ctx)
        except Exception as exc:
            passed, note = False, f"ERROR {type(exc).__name__}: {exc}"
        tr = ctx.traces
        used = []
        for t in tr:
            used += [u for u in t["tools_used"] if u not in used]
        evid = sorted({e for t in tr for e in t["evidence"]["policy"]} | {f"mem:{m}" for t in tr for m in t["evidence"]["memory"]})
        rows.append({
            "id": tdef["id"], "test": tdef["name"], "question": tr[-1]["question"] if tr else "", "passed": bool(passed),
            "tools": ", ".join(used) or "-",
            "tool_ok": "-" if not tdef["expect"] else ("yes" if tdef["expect"] <= set(used) else "NO"),
            "evidence": ", ".join(evid) or "-", "sources": "; ".join(dict.fromkeys(s for t in tr for s in t["sources"])),
            "latency_s": round(sum(t["latency_s"] for t in tr), 2), "llm_calls": sum(t["llm_calls"] for t in tr),
            "in_tokens": sum(t["tokens"]["input"] for t in tr), "out_tokens": sum(t["tokens"]["output"] for t in tr),
            "note": note, "langsmith_runs": " ".join(t.get("langsmith_run_id") or "" for t in tr).strip(),
        })
        print(f"{tdef['id']:<3} {'PASS' if passed else 'FAIL'}  {tdef['name']:<46} {note}")
        if tr and sleep:
            time.sleep(sleep)  # stay inside free-tier per-minute limits
    out = RESULTS / "run"
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(config.RUNTIME, out)
    return rows


def write_report(rows, mock):
    RESULTS.mkdir(exist_ok=True)
    llm = [r for r in rows if r["llm_calls"]]
    n = max(len(llm), 1)
    exp = [r for r in rows if r["tool_ok"] != "-"]
    passed = sum(r["passed"] for r in rows)
    L = ["# Assignment 1 - Evaluation report", "",
         f"Model: `{'mock (offline keyword model, NOT an LLM)' if mock else config.MODEL}`  |  Generated: {time.strftime('%Y-%m-%d %H:%M')}", "",
         "## Summary", "", "| Measure | Result |", "|---|---|",
         f"| Task accuracy / success | {passed}/{len(rows)} ({round(100 * passed / len(rows))}%) |",
         f"| Appropriate tool choice | {sum(r['tool_ok'] == 'yes' for r in exp)}/{len(exp)} tests that needed a tool |",
         f"| Avg latency per question (s) | {round(sum(r['latency_s'] for r in llm) / n, 2)} |",
         f"| Avg input / output tokens per question | {round(sum(r['in_tokens'] for r in llm) / n)} / {round(sum(r['out_tokens'] for r in llm) / n)} |",
         f"| Total tokens (all tests) | {sum(r['in_tokens'] + r['out_tokens'] for r in rows)} |", "",
         "## Per-test trace table", "",
         "| ID | Scenario | Tools called | Tool OK? | Retrieved evidence | Data sources | Latency (s) | In/Out tokens | Result | Observation |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {r['test']} | {r['tools']} | {r['tool_ok']} | {r['evidence']} | {r['sources']} | "
                 f"{r['latency_s']} | {r['in_tokens']}/{r['out_tokens']} | {'PASS' if r['passed'] else 'FAIL'} | {r['note']} |")
    slow = max(llm, key=lambda r: r["latency_s"], default=None)
    big = max(llm, key=lambda r: r["in_tokens"], default=None)
    L += ["", "## Key observations (auto-generated, add your own)", ""]
    if slow:
        L.append(f"- Slowest question: {slow['id']} ({slow['latency_s']} s, {slow['llm_calls']} model calls).")
    if big:
        L.append(f"- Largest prompt: {big['id']} ({big['in_tokens']} input tokens) - includes tool definitions and the tool result.")
    for r in rows:
        if not r["passed"]:
            L.append(f"- FAILED {r['id']} ({r['test']}): {r['note']}")
    L.append("- Policy questions send only the retrieved handbook section(s), never the whole handbook.")
    (RESULTS / "eval_report.md").write_text("\n".join(L), encoding="utf-8")
    with open(RESULTS / "eval_tests.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n" + "\n".join(L[4:14]))
    print(f"\nFull report: {RESULTS / 'eval_report.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="offline pipeline check; no API tokens")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between tests (free-tier rate limits)")
    a = ap.parse_args()
    if a.mock:
        from mock_llm import MockClient
        factory, sleep = MockClient, 0
    else:
        if not config.GROQ_API_KEY:
            raise SystemExit("GROQ_API_KEY missing. Copy .env.example to .env and add your free Groq key.")
        from groq import Groq
        factory, sleep = (lambda: Groq(api_key=config.GROQ_API_KEY)), a.sleep
    rows = run(factory, sleep)
    obs.flush()
    write_report(rows, a.mock)
    st = obs.status()
    print(f"LangSmith: {'tracing to project ' + st['project'] + ' (filter by tag eval / T1..T9)' if st['enabled'] else st['reason']}")


if __name__ == "__main__":
    main()
