# AIDTM Student Support Agent - Assignment 1

**Agentic AI Engineering - Assignment 1: Intelligent Student Support Agent**
PGDM (Big Data Analytics) Batch 2025-27

| | Link |
|---|---|
| Explanatory video | (https://drive.google.com/file/d/1LkI3WlEFap9JtsX5WdfE_L7NQCMsJBHZ/view?usp=sharing) |
| Assignment 2 repository (safe, production-aware version of this agent) | https://github.com/BhavyPatel08/aidtm-student-support-agent-assignment-2.git |

> All students, fees and handbook text are **sample data** made for this assignment. No real data or credentials are in this repository.

## 1. What it is

One chat-style interface where a student asks about fees, scholarships, course changes and support requests. **The same agent decides** whether to answer directly, use a tool, retrieve handbook policy, or use remembered information.

```
Student (chat UI)                         observability.py -> LangSmith (optional)
      |                                          ^
  app.py  (Streamlit; pick which student is asking)
      |
  agent.py   1 capture durable preferences     3 LOOP:  model --asks for tool--> code runs tool
             2 select context                            ^                          |
               (question + last 2 turns +                '------ result back -------'
                only the relevant memory)        4 build the trace (tools, evidence, tokens, latency)
      |
  tools.py ----- records.py   fees / scholarship / profile  (students.json)
           |---- rag.py       handbook retrieval, top-2 sections only  (student_handbook.md)
           |---- memory.py    persistent memory + sensitive-data guard (memory.json)
           '---- tickets      support requests (tickets.json)
```

## 2. Requirements -> where they are implemented

| Assignment requirement | Implementation |
|---|---|
| Working agent loop; tool result used before answering | `agent.py` `SupportAgent._run_turn`: model picks a tool, code executes it, result is fed back, model answers. Max 5 steps |
| At least two useful tools | `get_fee_status`, `get_scholarship_status`, `get_student_record`, `create_support_request`, `search_policy`, `remember` (`tools.py`) |
| Persistent memory across sessions; no temporary / sensitive data | `memory.py` -> `data/runtime/memory.json`. Only whitelisted durable keys (programme, preferred contact / language / name, study interest). Temporary words ("today", "right now") and sensitive patterns (OTP, password, PIN, card ...) are rejected **in code** |
| Retrieval from one handbook, only relevant parts | `rag.py` splits `data/student_handbook.md` by section; TF-IDF + a coverage check returns the top-2 sections, and **nothing** when the handbook cannot answer |
| Context selection | Model receives: short system prompt + last 2 turns + **only the memory relevant to this question** + tool results. Never the whole handbook, never all memory |
| Missing info, tool errors, unanswerable questions | Structured errors (`MISSING_INFO`, `INVALID_REQUEST`, `NOT_FOUND`, `TOOL_ERROR`, `UNKNOWN_TOOL`); bad JSON arguments and the step limit are handled; "no policy found" -> the agent says so and offers a support request |
| Trace for each run | Every question is saved to `data/runtime/traces.jsonl`, shown in the app (**Trace details** and the *Traces & evaluation* page) and, if enabled, sent to LangSmith |
| Task accuracy | `python eval.py` -> pass/fail per test, accuracy overall |
| Tools used + appropriateness | Eval table columns *Tools called* and *Tool OK?* |
| Latency | Measured end to end per question |
| Token usage | Input / output tokens from the Groq API for every model call, plus an estimated split of where the input tokens went |
| Retrieved evidence | Policy section ids (e.g. `HB-02`) and memory keys used for each answer; also *data sources* such as `students.json#fees` |

### The five suggested demonstration scenarios (all are tests in `eval.py`)
1. "What is my current fee status?" -> `get_fee_status` (T1)
2. "The payment portal failed. Can I pay on the next working day?" -> `search_policy`, section `HB-02` (T2)
3. A **new session** asks about a fact told earlier -> answered from persistent memory (T4 + T5)
4. A temporary or sensitive statement is **not** stored (T6 temporary, T9 password/OTP)
5. A question the handbook cannot answer -> the agent says it does not have the information (T7)

## 3. Setup

Needs Python 3.10+ and a **free** Groq API key from https://console.groq.com (no card needed).

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # Windows: copy .env.example .env
# open .env and paste your key into GROQ_API_KEY   (.env is git-ignored - never commit it)
```

## 4. Run

| Goal | Command |
|---|---|
| Start the app | `streamlit run app.py` |
| Try the app with no API key | start the app and switch on **Demo mode** in the sidebar |
| Run the tests (no key needed) | `pytest -q` |
| Run the evaluation with the real model | `python eval.py` |
| Offline check of the evaluation pipeline | `python eval.py --mock` |

In the app: choose the student in the sidebar (Assignment 1 has no login - that is Assignment 2). **New session (keeps memory)** starts a fresh conversation but keeps the saved memory, which is how to demonstrate persistence. Reset everything by deleting `data/runtime/`.

## 5. Evaluation

`python eval.py` runs 9 test questions, records a trace for each, and writes **`results/eval_report.md`** (summary + per-test trace table + observations), `results/eval_tests.csv` and `results/run/` (the traces, memory and tickets of that run). The report is also shown in the app's *Traces & evaluation* page.

Paste your own final numbers here after running with the real model:

| Measure | Result |
|---|---|
| Task accuracy / success | _/9 |
| Appropriate tool choice | _/6 |
| Avg latency per question (s) | |
| Avg input / output tokens per question | |
| Key observations | |

Free-tier limits change. If you hit a rate limit use `python eval.py --sleep 6`.

## 6. LangSmith tracing (optional)

Every question becomes one nested trace in project **`aidtm-college-helpdesk`**: memory lookup, each Groq call (exact messages, tokens), each tool call and each handbook retrieval (section + score). Two lines in `.env` switch it on - see [docs/LANGSMITH.md](docs/LANGSMITH.md). Off by default; the app works without it. Passwords/OTPs are removed before anything is traced and emails/phones are masked.

## 7. Project structure
```
app.py                  Streamlit UI: chat, traces & evaluation, memory & data
agent.py                Agent loop, context selection, tracing, token breakdown
tools.py                6 tools
memory.py               Persistent memory + sensitive-data guard
rag.py                  Retrieval over ONE handbook file
records.py              Student records
observability.py        Optional LangSmith tracing with privacy masking
mock_llm.py             Offline keyword stand-in for the model (demo / testing only, not an LLM)
eval.py                 Evaluation harness
scroll_component/       Keeps the chat box fitted to the window
tests/                  37 tests, no API key needed
data/                   students.json, student_handbook.md  (sample data)
docs/                   LangSmith guide, video script, submission guide
results/                Evaluation output (generated by you, committed)
static/, .streamlit/    Campus photo and theme
```

## 8. Known limitations
- Assignment 1 deliberately has **no login, authorization, approval or audit**. The agent is bound to the student chosen in the sidebar. Those controls are Assignment 2.
- Retrieval is keyword TF-IDF (free, no embeddings); heavily paraphrased questions can miss. The threshold in `config.py` favours "I do not know" over inventing policy.
- Sensitive-data detection is pattern based; unusual formats may slip through.
