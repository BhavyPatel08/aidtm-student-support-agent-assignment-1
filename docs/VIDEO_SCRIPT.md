# Video script - Assignment 1 (about 10-11 minutes)

Before recording: `pip install -r requirements.txt`, add your key to `.env` (do not show the file on screen), delete `data/runtime/`, run `python eval.py` once so `results/eval_report.md` exists, then `streamlit run app.py` (sidebar: Demo mode OFF).
Keep `README.md`, VS Code and (optionally) LangSmith open in other windows. Say the **bold** parts in your own words; SHOW = on-screen action.

## 0:00 - Introduction (30 s)
"I built an Intelligent Student Support Agent for AIDTM. It is one chat interface where the same agent decides whether to answer directly, call a tool, retrieve handbook policy, or use remembered information."

## 0:30 - Architecture (1 min 30 s)  - SHOW the diagram in README.md
- "Streamlit UI -> `agent.py` runs the agent loop -> the model can call 6 tools in `tools.py`: fee status, scholarship status, student record, support request, policy search and a memory tool."
- "Data: `students.json`; policy: one handbook file; memory: a JSON file that survives restarts."
- "The LLM is Groq's free `openai/gpt-oss-20b`. In this version the agent is bound to the student picked in the sidebar; login and permissions are Assignment 2."

## 2:00 - Agent flow in code (1 min 30 s)  - SHOW `agent.py` -> `_run_turn`
1. "Step 1 saves durable preferences. Step 2 does context selection. Step 3 is the loop."
2. "In the loop the model is called; if it asks for a tool, my code runs the tool, the result goes back as a tool message, and the model then answers. Maximum five steps so it can never loop forever."
3. "At the end I build the trace: tools, evidence, data sources, tokens from the API, latency."

## 3:30 - Live demo (3 min)  - SHOW the app; open **Trace details** under each answer
1. **"What is my current fee status?"** -> "It called `get_fee_status` and answered from `students.json#fees`. The line under the answer shows tool, latency and tokens."
2. **"The payment portal failed. Can I pay on the next working day?"** -> "Policy question, so it used `search_policy`. Only section HB-02 was retrieved - not the whole handbook."
3. **"Please remember that I prefer to be contacted on WhatsApp."** Then click **New session (keeps memory)** and ask **"How do I prefer to be contacted?"** -> "New session, empty chat - the answer comes from persistent memory; the trace shows memory item `preferred_contact`."
4. **"Right now I am sitting in the library and feeling tired. What is the attendance requirement?"** -> "The temporary statement was not saved; the policy question was answered from HB-08."
5. **"My student portal password is Hunter2 and my OTP is 482913."** -> "Credentials are removed before the model sees them and are never stored."
6. **"What is the hostel fee refund policy?"** -> "The handbook has nothing on this: retrieval returned no section and the agent says it does not have the information instead of inventing policy."
SHOW the **Memory & data** page: only `preferred_contact` is stored.

## 6:30 - Memory, retrieval, context handling (1 min 30 s)  - SHOW code
- `memory.py` `save()`: "Whitelisted durable keys only; temporary words and sensitive patterns are rejected in code."
- `memory.py` `select_relevant()`: "Only memory related to the current question is sent to the model."
- `rag.py` `search()`: "Handbook split by section; TF-IDF scores each one; a coverage check makes off-topic questions return nothing."
- "So the model gets: system prompt, last two turns, only relevant memory, and tool results - never the whole document."

## 8:00 - Tracing and evaluation (2 min)  - SHOW `results/eval_report.md` (or the app's *Traces & evaluation* page)
- "`eval.py` runs 9 test questions and records a trace for each."
- Read the summary: **task accuracy X out of 9**, **appropriate tool choice**, **average latency**, **average input/output tokens**.
- Show the per-test table: tools called, whether the choice was appropriate, retrieved evidence (HB-02), data sources, latency, tokens.
- "Observation: <one honest observation - e.g. policy questions use more input tokens because of the retrieved text; or one test that failed and why>."

## 10:00 - LangSmith (1 min)  - SHOW smith.langchain.com -> project `aidtm-college-helpdesk`
Open one trace: tree, `tool:search_policy` (HB-02 + score), a `groq_chat_completion` (messages in, tokens out), `data_sources`, `token_breakdown`. "This proves where each answer came from and where every token was spent." (docs/LANGSMITH.md)

## 11:00 - Close (20 s)
"Everything is in the public GitHub repository with a README for setup. Assignment 2 continues this same agent with privacy, approval and audit."

---
Rubric self-check: architecture ✔ agent flow ✔ tools ✔ memory ✔ retrieval ✔ context handling ✔ tracing ✔ evaluation (accuracy, latency, tokens) ✔ code walkthrough ✔ working demo ✔
